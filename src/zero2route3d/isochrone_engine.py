"""3D Network-based Isochrone and Accessibility Catchment Engine."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple

from .input_validation import normalize_time_intervals
from .kinematics import haversine_distance_2d
from .mobility_profiles import MobilityProfile, get_profile
from .routing_engine import RoutingEngine3D, Waypoint


@dataclass
class IsochroneBand:
    """Individual time contour band (e.g. 0-5 min, 5-10 min)."""

    time_cutoff_min: float
    reachable_node_count: int
    approx_area_ha: float
    boundary_points: List[Tuple[float, float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_cutoff_min": self.time_cutoff_min,
            "reachable_node_count": self.reachable_node_count,
            "approx_area_ha": round(self.approx_area_ha, 2),
            "boundary_points_count": len(self.boundary_points),
        }


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


class IsochroneEngine3D:
    """Generates 3D multi-interval travel-time catchment zones from a topological graph."""

    def __init__(self, routing_engine: RoutingEngine3D) -> None:
        self.engine = routing_engine

    def compute_isochrones(
        self,
        origin: Waypoint,
        profile_key: str = "adult",
        time_intervals_min: Sequence[float] = (5.0, 10.0, 15.0, 20.0, 30.0),
    ) -> IsochroneResult:
        """Propagate Dijkstra wavefront along 3D graph up to maximum time interval."""
        profile = get_profile(profile_key)
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

            # Approximate convex hull / bounding radius area
            if pts:
                max_rad_m = max(haversine_distance_2d((origin.lon, origin.lat), p) for p in pts)
                area_m2 = (
                    math.pi * (max_rad_m**2) * 0.45
                )  # 0.45 shape fill factor for urban network
                area_ha = area_m2 / 10000.0
            else:
                area_ha = 0.0

            bands.append(
                IsochroneBand(
                    time_cutoff_min=cutoff_min,
                    reachable_node_count=len(nodes_in_band),
                    approx_area_ha=area_ha,
                    boundary_points=pts[:50],  # sample boundary
                )
            )

        return IsochroneResult(
            origin=origin,
            profile=profile,
            bands=bands,
            total_reachable_nodes=len(min_times),
        )
