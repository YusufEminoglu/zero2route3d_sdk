# -*- coding: utf-8 -*-
"""3D Heavy Vehicle / Truck Height Clearance & Axle Load Restriction Router for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class TruckRestrictionProfile:
    """Dimensions and regulatory limits of a commercial truck / heavy vehicle."""

    vehicle_height_m: float = 4.20  # Total vehicle height including trailer
    vehicle_width_m: float = 2.55
    vehicle_length_m: float = 16.50
    gross_vehicle_weight_tons: float = 40.0
    axle_count: int = 5
    max_gradient_percent: float = 9.0  # Max hill climb limit for heavy freight
    is_hazardous_materials: bool = False


@dataclass
class BridgeClearanceObstacle:
    obstacle_id: str
    position: tuple[float, float, float]
    max_underpass_height_m: float
    max_weight_limit_tons: float
    is_hazmat_prohibited: bool = False


@dataclass
class TruckRouteFeasibilityResult:
    is_route_feasible: bool
    total_distance_km: float
    max_encountered_slope_percent: float
    height_violations_count: int
    weight_violations_count: int
    slope_violations_count: int
    hazmat_violations_count: int
    violation_details: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.is_route_feasible,
            "total_distance_km": round(self.total_distance_km, 3),
            "max_slope_pct": round(self.max_encountered_slope_percent, 1),
            "height_violations": self.height_violations_count,
            "weight_violations": self.weight_violations_count,
            "slope_violations": self.slope_violations_count,
            "hazmat_violations": self.hazmat_violations_count,
        }


def solve_heavy_vehicle_route3d(
    waypoints_3d: Sequence[tuple[float, float, float]],
    obstacles: Sequence[BridgeClearanceObstacle],
    truck_profile: TruckRestrictionProfile | None = None,
) -> TruckRouteFeasibilityResult:
    """Verify 3D route compliance against overhead bridge clearances, weight ratings, and road grades."""
    truck = truck_profile or TruckRestrictionProfile()
    n = len(waypoints_3d)
    if n < 2:
        return TruckRouteFeasibilityResult(True, 0.0, 0.0, 0, 0, 0, 0, [])

    tot_dist_m = 0.0
    max_slope = 0.0
    violations = []
    h_viols = 0
    w_viols = 0
    s_viols = 0
    haz_viols = 0

    # 1. Slope & Grade Checks along path
    for i in range(n - 1):
        p1 = waypoints_3d[i]
        p2 = waypoints_3d[i + 1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        d_horiz = math.hypot(dx, dy)
        d_3d = math.sqrt(d_horiz ** 2 + dz ** 2)
        tot_dist_m += d_3d

        slope_pct = (abs(dz) / max(1.0, d_horiz)) * 100.0
        max_slope = max(max_slope, slope_pct)

        if slope_pct > truck.max_gradient_percent:
            s_viols += 1
            violations.append({
                "type": "EXCESSIVE_SLOPE",
                "segment_index": i,
                "slope_pct": round(slope_pct, 1),
                "limit_pct": truck.max_gradient_percent,
            })

    # 2. Obstacle Proximity & Physical Clearance Checks
    for obs in obstacles:
        # Check if route passes within 25m of obstacle
        for i in range(n - 1):
            p1 = waypoints_3d[i]
            p2 = waypoints_3d[i + 1]
            dist_to_obs = math.hypot(obs.position[0] - p1[0], obs.position[1] - p1[1])
            if dist_to_obs < 30.0:
                if truck.vehicle_height_m > obs.max_underpass_height_m:
                    h_viols += 1
                    violations.append({
                        "type": "HEIGHT_RESTRICTION",
                        "obstacle_id": obs.obstacle_id,
                        "truck_height_m": truck.vehicle_height_m,
                        "clearance_limit_m": obs.max_underpass_height_m,
                    })

                if truck.gross_vehicle_weight_tons > obs.max_weight_limit_tons:
                    w_viols += 1
                    violations.append({
                        "type": "WEIGHT_RESTRICTION",
                        "obstacle_id": obs.obstacle_id,
                        "truck_tons": truck.gross_vehicle_weight_tons,
                        "bridge_limit_tons": obs.max_weight_limit_tons,
                    })

                if truck.is_hazardous_materials and obs.is_hazmat_prohibited:
                    haz_viols += 1
                    violations.append({
                        "type": "HAZMAT_PROHIBITION",
                        "obstacle_id": obs.obstacle_id,
                    })
                break

    is_feasible = (h_viols == 0 and w_viols == 0 and s_viols == 0 and haz_viols == 0)

    return TruckRouteFeasibilityResult(
        is_route_feasible=is_feasible,
        total_distance_km=tot_dist_m / 1000.0,
        max_encountered_slope_percent=max_slope,
        height_violations_count=h_viols,
        weight_violations_count=w_viols,
        slope_violations_count=s_viols,
        hazmat_violations_count=haz_viols,
        violation_details=violations,
    )
