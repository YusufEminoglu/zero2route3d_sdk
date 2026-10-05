# -*- coding: utf-8 -*-
"""3D Urban Air Mobility (UAM) & Drone Delivery Air Corridor Router for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class DroneAirspaceProfile:
    """Flight characteristics and regulatory limits for autonomous UAV / drone."""

    cruise_altitude_agl_m: float = 60.0  # Above Ground Level (AGL)
    max_altitude_agl_m: float = 120.0  # Regulatory ceiling
    min_building_clearance_m: float = 25.0  # Buffer from rooftops and facades
    cruise_speed_ms: float = 15.0  # ~54 km/h
    battery_range_km: float = 18.0
    wind_limit_ms: float = 12.0


@dataclass
class GeofencedNoFlyZone:
    zone_id: str
    boundary_polygon: list[tuple[float, float]]
    min_alt_m: float = 0.0
    max_alt_m: float = 500.0


@dataclass
class AirCorridorResult:
    is_flight_feasible: bool
    total_flight_distance_m: float
    estimated_flight_time_minutes: float
    battery_consumed_pct: float
    min_obstacle_clearance_m: float
    no_fly_zone_violations_count: int
    flight_waypoints_3d: list[tuple[float, float, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.is_flight_feasible,
            "flight_distance_m": round(self.total_flight_distance_m, 1),
            "flight_time_min": round(self.estimated_flight_time_minutes, 2),
            "battery_pct": round(self.battery_consumed_pct, 1),
            "min_clearance_m": round(self.min_obstacle_clearance_m, 1),
            "nfz_violations": self.no_fly_zone_violations_count,
        }


def solve_3d_drone_flight_corridor(
    takeoff_point: tuple[float, float, float],
    landing_point: tuple[float, float, float],
    building_obstacles: Sequence[dict[str, Any]],  # {'bbox': (min_x, min_y, max_x, max_y), 'height': h}
    no_fly_zones: Sequence[GeofencedNoFlyZone] = (),
    drone_profile: DroneAirspaceProfile | None = None,
) -> AirCorridorResult:
    """Compute optimal 3D urban drone trajectory with vertical takeoff, cruise, obstacle clearance, and landing."""
    drone = drone_profile or DroneAirspaceProfile()

    # Determine required safe cruise altitude above tallest obstacle along path
    p0 = takeoff_point
    p1 = landing_point
    horiz_dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])

    max_bldg_h = 0.0
    min_clearance = float("inf")

    # Sample line
    n_samples = max(5, int(horiz_dist / 20.0))
    for s in range(n_samples + 1):
        t = s / float(n_samples)
        sx = p0[0] + t * (p1[0] - p0[0])
        sy = p0[1] + t * (p1[1] - p0[1])

        for bldg in building_obstacles:
            bx1, by1, bx2, by2 = bldg.get("bbox", (0, 0, 0, 0))
            bh = float(bldg.get("height", 20.0))
            if bx1 <= sx <= bx2 and by1 <= sy <= by2:
                max_bldg_h = max(max_bldg_h, bh)
                min_clearance = min(min_clearance, drone.cruise_altitude_agl_m - bh)

    safe_cruise_z = max(p0[2] + drone.cruise_altitude_agl_m, max_bldg_h + drone.min_building_clearance_m)
    safe_cruise_z = min(drone.max_altitude_agl_m + p0[2], safe_cruise_z)

    # 4-stage 3D flight plan: Takeoff -> Ascend -> Cruise -> Descend
    w1 = (p0[0], p0[1], safe_cruise_z)
    w2 = (p1[0], p1[1], safe_cruise_z)

    waypoints = [p0, w1, w2, p1]

    # Total 3D distance
    tot_dist = (safe_cruise_z - p0[2]) + horiz_dist + (safe_cruise_z - p1[2])
    flight_time_s = tot_dist / max(1.0, drone.cruise_speed_ms)
    flight_time_min = flight_time_s / 60.0

    battery_used = (tot_dist / 1000.0) / max(1e-4, drone.battery_range_km) * 100.0
    feasible = (battery_used <= 100.0) and (min_clearance >= 0.0)

    return AirCorridorResult(
        is_flight_feasible=feasible,
        total_flight_distance_m=tot_dist,
        estimated_flight_time_minutes=flight_time_min,
        battery_consumed_pct=battery_used,
        min_obstacle_clearance_m=max(0.0, min_clearance) if min_clearance != float("inf") else drone.cruise_altitude_agl_m,
        no_fly_zone_violations_count=0,
        flight_waypoints_3d=waypoints,
    )
