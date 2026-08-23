"""Geospatial ecosystem integrations: GeoPandas, Shapely, NetworkX, and Rasterio.

Allows seamless conversion between 02Route 3D objects and standard Python GIS libraries.
All dependencies are lazily loaded with graceful fallbacks.
"""

from __future__ import annotations

import contextlib
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .kinematics import haversine_distance_2d
from .network_source import RoadSegment


def to_shapely_linestring(coordinates_3d: Sequence[Sequence[float]]) -> Any:
    """Convert 3D coordinate sequence to a shapely.geometry.LineString (Z-aware)."""
    try:
        import shapely.geometry

        return shapely.geometry.LineString([c[:3] for c in coordinates_3d])
    except ImportError as exc:
        raise ImportError(
            "shapely is required for geometric conversion. Install via 'pip install shapely'."
        ) from exc


def from_geodataframe(
    gdf: Any,
    id_column: Optional[str] = None,
    highway_column: Optional[str] = "highway",
    surface_column: Optional[str] = "surface",
    oneway_column: Optional[str] = "oneway",
) -> List[RoadSegment]:
    """Extract 02Route 3D RoadSegment objects from a geopandas.GeoDataFrame of LineStrings."""
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise ImportError("geopandas is required. Install via 'pip install geopandas'.") from exc

    if not isinstance(gdf, gpd.GeoDataFrame):
        raise TypeError("Expected geopandas.GeoDataFrame instance.")

    segments: List[RoadSegment] = []

    for _idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        lines = (
            [geom]
            if geom.geom_type == "LineString"
            else (geom.geoms if geom.geom_type == "MultiLineString" else [])
        )
        for line in lines:
            coords = list(line.coords)
            if len(coords) < 2:
                continue

            highway_val = (
                str(row.get(highway_column, "residential"))
                if highway_column in row
                else "residential"
            )
            surface_val = (
                str(row.get(surface_column, "asphalt")) if surface_column in row else "asphalt"
            )
            oneway_raw = row.get(oneway_column, False) if oneway_column in row else False
            is_oneway = bool(oneway_raw in (True, 1, "yes", "true", "1", "-1"))
            is_steps = "step" in highway_val.lower()

            for i in range(len(coords) - 1):
                p1_raw = coords[i]
                p2_raw = coords[i + 1]

                p1: Tuple[float, float, float] = (
                    float(p1_raw[0]),
                    float(p1_raw[1]),
                    float(p1_raw[2]) if len(p1_raw) > 2 and math.isfinite(p1_raw[2]) else 0.0,
                )
                p2: Tuple[float, float, float] = (
                    float(p2_raw[0]),
                    float(p2_raw[1]),
                    float(p2_raw[2]) if len(p2_raw) > 2 and math.isfinite(p2_raw[2]) else 0.0,
                )

                length_m = haversine_distance_2d(p1, p2)

                seg = RoadSegment(
                    p1=p1,
                    p2=p2,
                    length_m=length_m,
                    highway_type=highway_val,
                    surface=surface_val,
                    is_oneway=is_oneway,
                    is_steps=is_steps,
                )
                segments.append(seg)

    return segments


def to_geodataframe(
    items: Union[List[RoadSegment], Any],
    crs: str = "EPSG:4326",
) -> Any:
    """Convert RoadSegment list or RouteResult3D into a geopandas.GeoDataFrame with 3D LineStrings."""
    try:
        import geopandas as gpd
        import shapely.geometry
    except ImportError as exc:
        raise ImportError("geopandas and shapely are required for GeoDataFrame creation.") from exc

    records: List[Dict[str, Any]] = []

    # Check if input is RouteResult3D
    if hasattr(items, "coordinates_3d") and hasattr(items, "statistics"):
        coords = items.coordinates_3d
        if len(coords) >= 2:
            geom = shapely.geometry.LineString(coords)
            records.append(
                {
                    "geometry": geom,
                    "distance_m": items.statistics.total_distance_m,
                    "duration_min": items.statistics.total_duration_min,
                    "climb_m": items.statistics.elevation_gain_m,
                    "descent_m": items.statistics.elevation_loss_m,
                    "max_slope_pct": items.statistics.max_slope_pct,
                    "profile": items.statistics.profile_name,
                }
            )
    elif isinstance(items, list):
        for seg in items:
            if isinstance(seg, RoadSegment):
                geom = shapely.geometry.LineString([seg.p1, seg.p2])
                records.append(
                    {
                        "geometry": geom,
                        "length_m": seg.length_m,
                        "highway_type": seg.highway_type,
                        "surface": seg.surface,
                        "is_oneway": seg.is_oneway,
                        "is_steps": seg.is_steps,
                    }
                )

    return gpd.GeoDataFrame(records, crs=crs)


def to_networkx_digraph(engine_or_segments: Any) -> Any:
    """Convert 02Route 3D graph or segment list into a networkx.DiGraph with kinematic edge weights."""
    try:
        import networkx as nx
    except ImportError as exc:
        raise ImportError("networkx is required. Install via 'pip install networkx'.") from exc

    g = nx.DiGraph()

    if hasattr(engine_or_segments, "nodes") and hasattr(engine_or_segments, "adj"):
        for node_id, coord in engine_or_segments.nodes.items():
            g.add_node(
                node_id, lon=coord[0], lat=coord[1], elevation_m=coord[2] if len(coord) > 2 else 0.0
            )

        for u, neighbors in engine_or_segments.adj.items():
            for v, length_m, slope_pct, meta in neighbors:
                g.add_edge(
                    u,
                    v,
                    length_m=length_m,
                    slope_pct=slope_pct,
                    highway_type=meta.get("highway_type", "residential"),
                    surface=meta.get("surface", "asphalt"),
                    is_steps=meta.get("is_steps", False),
                )
    elif isinstance(engine_or_segments, list):
        for seg in engine_or_segments:
            if isinstance(seg, RoadSegment):
                n1 = f"n_{round(seg.p1[0], 5)}_{round(seg.p1[1], 5)}"
                n2 = f"n_{round(seg.p2[0], 5)}_{round(seg.p2[1], 5)}"
                g.add_node(
                    n1,
                    lon=seg.p1[0],
                    lat=seg.p1[1],
                    elevation_m=seg.p1[2] if len(seg.p1) > 2 else 0.0,
                )
                g.add_node(
                    n2,
                    lon=seg.p2[0],
                    lat=seg.p2[1],
                    elevation_m=seg.p2[2] if len(seg.p2) > 2 else 0.0,
                )
                slope = (
                    ((seg.p2[2] - seg.p1[2]) / seg.length_m) * 100.0
                    if seg.length_m > 0 and len(seg.p1) > 2 and len(seg.p2) > 2
                    else 0.0
                )

                g.add_edge(
                    n1,
                    n2,
                    length_m=seg.length_m,
                    slope_pct=slope,
                    highway_type=seg.highway_type,
                    surface=seg.surface,
                    is_steps=seg.is_steps,
                )
                if not seg.is_oneway:
                    g.add_edge(
                        n2,
                        n1,
                        length_m=seg.length_m,
                        slope_pct=-slope,
                        highway_type=seg.highway_type,
                        surface=seg.surface,
                        is_steps=seg.is_steps,
                    )

    return g


def sample_rasterio_dem(tif_path: str, coords: Sequence[Tuple[float, float]]) -> List[float]:
    """Sample elevations directly from a GeoTIFF using rasterio with windowed reading."""
    try:
        import rasterio
    except ImportError as exc:
        raise ImportError(
            "rasterio is required for GeoTIFF sampling. Install via 'pip install rasterio'."
        ) from exc

    results: List[float] = []
    with rasterio.open(tif_path) as dataset:
        for lon, lat in coords:
            with contextlib.suppress(Exception):
                for val in dataset.sample([(lon, lat)]):
                    v = float(val[0])
                    results.append(v if math.isfinite(v) and v > -9999 else 0.0)
                    break
                else:
                    results.append(0.0)
                continue
            results.append(0.0)

    return results
