"""3D Network-based Isochrone and Accessibility Catchment Engine."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple, Union

from .input_validation import normalize_time_intervals
from .mobility_profiles import MobilityProfile, resolve_profile
from .routing_engine import RoutingEngine3D, Waypoint

_EARTH_RADIUS_M = 6371000.0


def convex_hull_2d(points: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Monotone-chain convex hull of (lon, lat) points, counter-clockwise, no repeat.

    Dependency-free so isochrone geometry does not require shapely.
    """
    unique = sorted({(float(x), float(y)) for x, y in points})
    if len(unique) < 3:
        return unique

    def cross(o: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Tuple[float, float]] = []
    for pt in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], pt) <= 0:
            lower.pop()
        lower.append(pt)

    upper: List[Tuple[float, float]] = []
    for pt in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], pt) <= 0:
            upper.pop()
        upper.append(pt)

    return lower[:-1] + upper[:-1]


def _ring_area_m2(ring: Sequence[Tuple[float, float]]) -> float:
    """Shoelace area of a lon/lat ring, on a local equirectangular projection."""
    if len(ring) < 3:
        return 0.0
    mean_lat_rad = math.radians(sum(lat for _lon, lat in ring) / len(ring))
    scale_x = _EARTH_RADIUS_M * math.cos(mean_lat_rad) * math.pi / 180.0
    scale_y = _EARTH_RADIUS_M * math.pi / 180.0

    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(ring, list(ring[1:]) + [ring[0]]):
        total += (lon1 * scale_x) * (lat2 * scale_y) - (lon2 * scale_x) * (lat1 * scale_y)
    return abs(total) * 0.5


@dataclass
class IsochroneBand:
    """Individual time contour band (e.g. 0-5 min, 5-10 min)."""

    time_cutoff_min: float
    reachable_node_count: int
    approx_area_ha: float
    #: Convex hull of the reachable nodes, counter-clockwise, first point not repeated.
    boundary_points: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def area_sqkm(self) -> float:
        """Catchment area in square kilometres."""
        return self.approx_area_ha / 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_cutoff_min": self.time_cutoff_min,
            "reachable_node_count": self.reachable_node_count,
            "approx_area_ha": round(self.approx_area_ha, 2),
            "area_sqkm": round(self.area_sqkm, 4),
            "boundary_points_count": len(self.boundary_points),
        }

    def to_geojson_feature(self) -> Dict[str, Any]:
        """Convex-hull catchment as a GeoJSON Polygon Feature (empty geometry if degenerate)."""
        ring = list(self.boundary_points)
        geometry: Any = None
        if len(ring) >= 3:
            closed = ring + [ring[0]]
            geometry = {
                "type": "Polygon",
                "coordinates": [[[round(lon, 6), round(lat, 6)] for lon, lat in closed]],
            }
        return {"type": "Feature", "geometry": geometry, "properties": self.to_dict()}


@dataclass
class IsochroneResult:
    """Complete multi-tier 3D accessibility service area result."""

    origin: Waypoint
    profile: MobilityProfile
    bands: List[IsochroneBand]
    total_reachable_nodes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": {"lon": self.origin.lon, "lat": self.origin.lat, "name": self.origin.name},
            "profile_name": self.profile.name,
            "total_reachable_nodes": self.total_reachable_nodes,
            "bands": [b.to_dict() for b in self.bands],
        }

    def to_geojson(self) -> Dict[str, Any]:
        """All catchment bands as one GeoJSON FeatureCollection, widest band first.

        Ordering matters for rendering: drawing the widest polygon first lets the
        tighter bands paint on top of it instead of being hidden underneath.
        """
        ordered = sorted(self.bands, key=lambda b: b.time_cutoff_min, reverse=True)
        return {
            "type": "FeatureCollection",
            "properties": {
                "origin": {"lon": self.origin.lon, "lat": self.origin.lat},
                "profile_key": self.profile.key,
                "profile_name": self.profile.name,
                "total_reachable_nodes": self.total_reachable_nodes,
            },
            "features": [band.to_geojson_feature() for band in ordered],
        }


class IsochroneEngine3D:
    """Generates 3D multi-interval travel-time catchment zones from a topological graph."""

    def __init__(self, routing_engine: RoutingEngine3D) -> None:
        self.engine = routing_engine

    def compute_isochrones(
        self,
        origin: Waypoint,
        profile_key: Union[str, MobilityProfile] = "adult",
        time_intervals_min: Sequence[float] = (5.0, 10.0, 15.0, 20.0, 30.0),
    ) -> IsochroneResult:
        """Propagate Dijkstra wavefront along 3D graph up to maximum time interval."""
        profile = resolve_profile(profile_key)
        intervals_min = normalize_time_intervals(time_intervals_min)
        if not intervals_min:
            return IsochroneResult(origin, profile, [], 0)
        start_node = self.engine.find_nearest_node((origin.lon, origin.lat))

        if start_node is None or not self.engine.nodes:
            return IsochroneResult(origin, profile, [], 0)

        max_cutoff_s = max(intervals_min) * 60.0
        sorted_intervals_s = [t * 60.0 for t in intervals_min]

        # Dijkstra queue: (travel_time_seconds, node_id)
        pq: List[Tuple[float, int]] = [(0.0, start_node)]
        min_times: Dict[int, float] = {start_node: 0.0}
        visited = set()

        while pq:
            t_curr, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)

            if t_curr > max_cutoff_s:
                continue

            for v, seg_len, slope_pct, meta in self.engine.adj.get(u, []):
                if v in visited:
                    continue

                cost = profile.calculate_edge_resistance(
                    length_m=seg_len,
                    slope_pct=slope_pct,
                    is_steps=meta.get("is_steps", False),
                    hierarchy_rank=meta.get("hierarchy", 4),
                )
                if not math.isfinite(cost):
                    continue

                seg_time_s = profile.travel_time_seconds(
                    seg_len,
                    slope_pct=slope_pct,
                    hierarchy_rank=meta.get("hierarchy", 4),
                )
                tentative_t = t_curr + seg_time_s

                if tentative_t < min_times.get(v, float("inf")) and tentative_t <= max_cutoff_s:
                    min_times[v] = tentative_t
                    heapq.heappush(pq, (tentative_t, v))

        bands: List[IsochroneBand] = []
        for cutoff_s in sorted_intervals_s:
            cutoff_min = cutoff_s / 60.0
            nodes_in_band = [nid for nid, t in min_times.items() if t <= cutoff_s]
            pts = [(self.engine.nodes[nid][0], self.engine.nodes[nid][1]) for nid in nodes_in_band]

            # A real convex hull of the reachable nodes, and its real area. The
            # previous version stored the first 50 nodes in dictionary order and
            # called them a boundary, then reported pi*r^2 times a fudge factor.
            hull = convex_hull_2d(pts)
            area_ha = _ring_area_m2(hull) / 10000.0

            bands.append(
                IsochroneBand(
                    time_cutoff_min=cutoff_min,
                    reachable_node_count=len(nodes_in_band),
                    approx_area_ha=area_ha,
                    boundary_points=hull,
                )
            )

        return IsochroneResult(
            origin=origin,
            profile=profile,
            bands=bands,
            total_reachable_nodes=len(min_times),
        )
