"""High-level, single-call functional API for zero2route3d.

Enables fast, one-line spatial mobility calculations directly from coordinates,
GeoJSON files, or GeoPandas DataFrames without manual engine instantiation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .environmental_raster import EnvironmentalSurfaceSampler, MCDAWeights
from .isochrone_engine import IsochroneEngine3D, IsochroneResult
from .map_matching_3d import GPXPoint, HMMMapMatcher3D, MapMatching3DResult
from .mobility_profiles import MobilityProfile
from .network_source import NetworkSourceManager, RoadSegment
from .pareto_router import ParetoFrontierResult, ParetoMultiObjectiveRouter
from .routing_engine import RouteResult3D, RoutingEngine3D, Waypoint


def _load_network(
    network_input: Union[str, Path, Sequence[RoadSegment], Sequence[Dict[str, Any]], Any],
) -> List[RoadSegment]:
    """Parse road segments from filepath, GeoJSON dict, list, or GeoDataFrame."""
    if (
        isinstance(network_input, list)
        and network_input
        and isinstance(network_input[0], RoadSegment)
    ):
        return list(network_input)

    mgr = NetworkSourceManager()
    if isinstance(network_input, (str, Path)):
        p = Path(network_input)
        if p.exists() and p.suffix.lower() in (".json", ".geojson"):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return mgr.extract_from_geojson(data)

    if isinstance(network_input, dict):
        return mgr.extract_from_geojson(network_input)

    # Check for geopandas DataFrame
    if hasattr(network_input, "geometry") and hasattr(network_input, "iterfeatures"):
        from .integrations import from_geodataframe

        return from_geodataframe(network_input)

    return []


def solve_3d_route(
    origin: Union[Tuple[float, float], Tuple[float, float, float], Waypoint],
    destination: Union[Tuple[float, float], Tuple[float, float, float], Waypoint],
    network: Union[str, Path, Sequence[RoadSegment], Dict[str, Any], Any],
    profile: Union[str, MobilityProfile] = "adult",
    dem_sampler: Optional[EnvironmentalSurfaceSampler] = None,
    mcda_weights: Optional[MCDAWeights] = None,
    intermediate_stops: Optional[Sequence[Union[Tuple[float, float], Waypoint]]] = None,
    optimize_stops_order: bool = False,
) -> RouteResult3D:
    """Solve a multi-criteria 3D least-cost route in a single call.

    Args:
        origin: Start (lon, lat) or (lon, lat, elev) or Waypoint.
        destination: End (lon, lat) or (lon, lat, elev) or Waypoint.
        network: Road network GeoJSON filepath, dictionary, GeoDataFrame, or RoadSegment list.
        profile: Profile key (e.g. 'adult', 'wheelchair', 'commuter_bike') or MobilityProfile instance.
        dem_sampler: Optional environmental/elevation raster sampler.
        mcda_weights: Optional AHP multi-criteria weighting configuration.
        intermediate_stops: Optional intermediate waypoints.
        optimize_stops_order: Solve TSP tour over intermediate stops if True.

    Returns:
        RouteResult3D containing 3D coordinates, elevation profile, and rich kinematic statistics.
    """
    segments = _load_network(network)
    engine = RoutingEngine3D(sampler=dem_sampler, weights=mcda_weights)
    engine.build_graph(segments)

    def to_wp(pt: Any, name: str) -> Waypoint:
        if isinstance(pt, Waypoint):
            return pt
        if isinstance(pt, (tuple, list)):
            return Waypoint(
                lon=float(pt[0]),
                lat=float(pt[1]),
                elevation_m=float(pt[2]) if len(pt) > 2 else 0.0,
                name=name,
            )
        raise ValueError(f"Invalid waypoint: {pt}")

    waypoints = [to_wp(origin, "Origin")]
    if intermediate_stops:
        for idx, stop in enumerate(intermediate_stops, start=1):
            waypoints.append(to_wp(stop, f"Stop {idx}"))
    waypoints.append(to_wp(destination, "Destination"))

    prof_key = profile.name.lower() if isinstance(profile, MobilityProfile) else str(profile)
    return engine.calculate_route(
        waypoints, profile_key=prof_key, optimize_tsp=optimize_stops_order
    )


def solve_3d_isochrones(
    center: Union[Tuple[float, float], Waypoint],
    network: Union[str, Path, Sequence[RoadSegment], Dict[str, Any], Any],
    profile: Union[str, MobilityProfile] = "adult",
    time_intervals_min: Sequence[float] = (5.0, 10.0, 15.0),
    dem_sampler: Optional[EnvironmentalSurfaceSampler] = None,
) -> IsochroneResult:
    """Compute anisotropic 3D isochrone travel-time wavefront bands from a center point."""
    segments = _load_network(network)
    engine = RoutingEngine3D(sampler=dem_sampler)
    engine.build_graph(segments)

    origin_wp = (
        center
        if isinstance(center, Waypoint)
        else Waypoint(lon=float(center[0]), lat=float(center[1]), name="Center")
    )
    prof_key = profile.name.lower() if isinstance(profile, MobilityProfile) else str(profile)

    iso_engine = IsochroneEngine3D(engine)
    return iso_engine.compute_isochrones(
        origin_wp, profile_key=prof_key, time_intervals_min=time_intervals_min
    )


def solve_4d_pareto_frontier(
    origin: Union[Tuple[float, float], Waypoint],
    destination: Union[Tuple[float, float], Waypoint],
    network: Union[str, Path, Sequence[RoadSegment], Dict[str, Any], Any],
    profile: Union[str, MobilityProfile] = "commuter_bike",
    dem_sampler: Optional[EnvironmentalSurfaceSampler] = None,
) -> ParetoFrontierResult:
    """Compute non-dominated 4D Pareto frontier trade-offs across Time, Climb, Heat, and Calories."""
    segments = _load_network(network)
    sampler = dem_sampler or EnvironmentalSurfaceSampler()
    engine = RoutingEngine3D(sampler=sampler)
    engine.build_graph(segments)

    start_wp = (
        origin
        if isinstance(origin, Waypoint)
        else Waypoint(lon=float(origin[0]), lat=float(origin[1]))
    )
    end_wp = (
        destination
        if isinstance(destination, Waypoint)
        else Waypoint(lon=float(destination[0]), lat=float(destination[1]))
    )

    start_node = engine.find_nearest_node((start_wp.lon, start_wp.lat))
    end_node = engine.find_nearest_node((end_wp.lon, end_wp.lat))

    if start_node is None or end_node is None:
        raise ValueError("Could not snap origin or destination to network graph.")

    pareto_router = ParetoMultiObjectiveRouter(engine.nodes, engine.adj, sampler)
    prof_key = profile.name.lower() if isinstance(profile, MobilityProfile) else str(profile)
    return pareto_router.solve_pareto_frontier(start_node, end_node, profile_key=prof_key)


def match_gps_track_3d(
    gpx_points: Sequence[Union[GPXPoint, Tuple[float, float], Tuple[float, float, float]]],
    network: Union[str, Path, Sequence[RoadSegment], Dict[str, Any], Any],
    gps_sigma: float = 12.0,
    beta: float = 5.0,
) -> MapMatching3DResult:
    """Match noisy GPS/GPX track coordinates onto the 3D road network via HMM Viterbi decoding."""
    segments = _load_network(network)
    engine = RoutingEngine3D()
    engine.build_graph(segments)

    pts: List[GPXPoint] = []
    for p in gpx_points:
        if isinstance(p, GPXPoint):
            pts.append(p)
        elif isinstance(p, (tuple, list)):
            pts.append(
                GPXPoint(
                    lon=float(p[0]),
                    lat=float(p[1]),
                    elevation_raw_m=float(p[2]) if len(p) > 2 else 0.0,
                )
            )

    matcher = HMMMapMatcher3D(engine.nodes, engine.adj, gps_sigma=gps_sigma, beta=beta)
    return matcher.match_gps_track(pts)
