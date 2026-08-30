# -*- coding: utf-8 -*-
"""Multi-Criteria Emergency Evacuation Routing with Dynamic Hazard Exclusion for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class DynamicHazardZone:
    """Expanding hazard zone (e.g. flood surge, toxic plume, wildfire front)."""

    hazard_id: str
    origin_point: tuple[float, float, float]
    expansion_speed_ms: float
    current_radius_m: float
    danger_level: float = 1.0  # 0.0 to 1.0


@dataclass
class EvacuationPath3D:
    origin_id: str
    destination_muster_point: str
    total_distance_m: float
    total_elevation_gain_m: float
    evacuation_time_minutes: float
    minimum_hazard_clearance_m: float
    is_fully_safe: bool
    waypoints: list[tuple[float, float, float]]


@dataclass
class EvacuationRouteResult:
    total_population_evacuated: int
    mean_evacuation_time_min: float
    max_evacuation_time_min: float
    safest_muster_point: str
    routes: list[EvacuationPath3D]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_evacuees": self.total_population_evacuated,
            "mean_time_min": round(self.mean_evacuation_time_min, 1),
            "max_time_min": round(self.max_evacuation_time_min, 1),
            "safest_muster_point": self.safest_muster_point,
            "routes_count": len(self.routes),
        }


def solve_3d_evacuation_routes(
    evacuee_origins: list[dict[str, Any]],  # List of dicts with 'id', 'population', 'coords': (x, y, z)
    muster_points: list[dict[str, Any]],    # List of dicts with 'id', 'coords': (x, y, z), 'capacity'
    hazard_zones: list[DynamicHazardZone],
    walking_speed_kmh: float = 4.5,
) -> EvacuationRouteResult:
    """Compute optimal 3D evacuation routes navigating away from dynamic hazard fronts."""
    routes: list[EvacuationPath3D] = []
    tot_pop = sum(int(o.get("population", 50)) for o in evacuee_origins)
    times = []
    v_ms = (walking_speed_kmh * 1000.0) / 3600.0

    muster_usage: dict[str, int] = {str(m.get("id", "M")): 0 for m in muster_points}

    for org in evacuee_origins:
        o_id = str(org.get("id", "org"))
        o_pt = org.get("coords", (0.0, 0.0, 0.0))
        pop = int(org.get("population", 50))

        best_score = float("inf")
        best_muster = None
        best_route_pts: list[tuple[float, float, float]] = []
        best_clearance = float("inf")

        for mst in muster_points:
            m_id = str(mst.get("id", "M"))
            m_pt = mst.get("coords", (0.0, 0.0, 0.0))

            dx = m_pt[0] - o_pt[0]
            dy = m_pt[1] - o_pt[1]
            dz = m_pt[2] - o_pt[2]
            d_3d = math.sqrt(dx * dx + dy * dy + dz * dz)

            # Generate intermediate waypoints
            num_steps = max(2, int(d_3d / 100.0))
            pts = []
            min_h_dist = float("inf")

            for s in range(num_steps + 1):
                t = s / float(num_steps)
                wx = o_pt[0] + dx * t
                wy = o_pt[1] + dy * t
                wz = o_pt[2] + dz * t
                pts.append((wx, wy, wz))

                # Check proximity to all hazard zones
                for hz in hazard_zones:
                    h_dist = math.hypot(wx - hz.origin_point[0], wy - hz.origin_point[1])
                    clearance = h_dist - hz.current_radius_m
                    min_h_dist = min(min_h_dist, clearance)

            # Danger penalty
            danger_penalty = 10000.0 if min_h_dist < 0 else (1000.0 / max(1.0, min_h_dist))
            score = d_3d + danger_penalty

            if score < best_score:
                best_score = score
                best_muster = m_id
                best_route_pts = pts
                best_clearance = min_h_dist

        # Compute route metrics
        d_tot = 0.0
        elev_gain = 0.0
        for i in range(len(best_route_pts) - 1):
            p1 = best_route_pts[i]
            p2 = best_route_pts[i + 1]
            seg_d = math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2)
            d_tot += seg_d
            if p2[2] > p1[2]:
                elev_gain += (p2[2] - p1[2])

        # Tobler speed adjustment for uphill climb
        climb_factor = max(0.5, 1.0 - (elev_gain / max(1.0, d_tot)) * 2.0)
        time_min = (d_tot / (v_ms * climb_factor)) / 60.0
        times.append(time_min)

        if best_muster:
            muster_usage[best_muster] = muster_usage.get(best_muster, 0) + pop

        routes.append(
            EvacuationPath3D(
                origin_id=o_id,
                destination_muster_point=best_muster or "None",
                total_distance_m=d_tot,
                total_elevation_gain_m=elev_gain,
                evacuation_time_minutes=time_min,
                minimum_hazard_clearance_m=best_clearance,
                is_fully_safe=best_clearance > 50.0,
                waypoints=best_route_pts,
            )
        )

    mean_t = float(sum(times) / max(1, len(times))) if times else 0.0
    max_t = max(times) if times else 0.0
    safest_m = max(muster_usage.items(), key=lambda x: x[1])[0] if muster_usage else "M_1"

    return EvacuationRouteResult(
        total_population_evacuated=tot_pop,
        mean_evacuation_time_min=mean_t,
        max_evacuation_time_min=max_t,
        safest_muster_point=safest_m,
        routes=routes,
    )
