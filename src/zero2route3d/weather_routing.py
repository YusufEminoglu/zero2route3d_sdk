# -*- coding: utf-8 -*-
"""Dynamic Wind Field & Rain Pavement Friction Weather Routing Engine for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class HeadwindResistanceResult:
    """Aerodynamic apparent wind power penalty and speed correction on a route segment."""

    segment_heading_degrees: float
    true_wind_speed_ms: float
    true_wind_direction_degrees: float
    apparent_wind_speed_ms: float
    apparent_wind_angle_degrees: float
    aerodynamic_power_w: float
    power_penalty_vs_calm_w: float  # Positive = headwind penalty, Negative = tailwind boost
    rain_braking_distance_factor: float  # Multiplier on wet pavement (e.g. 1.35x)


@dataclass
class WeatherRouteSummary:
    total_distance_km: float
    total_wind_energy_penalty_kwh: float
    mean_apparent_wind_speed_ms: float
    tailwind_assistance_ratio: float
    headwind_struggle_ratio: float
    segments: list[HeadwindResistanceResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_distance_km": round(self.total_distance_km, 3),
            "wind_energy_penalty_kwh": round(self.total_wind_energy_penalty_kwh, 3),
            "mean_apparent_wind_ms": round(self.mean_apparent_wind_speed_ms, 2),
            "tailwind_assistance_ratio": round(self.tailwind_assistance_ratio, 3),
            "headwind_struggle_ratio": round(self.headwind_struggle_ratio, 3),
        }


def compute_apparent_wind_resistance(
    waypoints: Sequence[tuple[float, float]],
    vehicle_speed_kmh: float = 25.0,
    wind_speed_ms: float = 8.0,
    wind_direction_degrees: float = 90.0,  # Wind blowing FROM East (90°)
    is_raining: bool = False,
    drag_area_cd_a: float = 0.40,  # Cyclist Cd*A (m^2)
) -> WeatherRouteSummary:
    """Calculate vector apparent wind resistance across all road polyline segments."""
    n = len(waypoints)
    if n < 2:
        return WeatherRouteSummary(0.0, 0.0, 0.0, 0.0, 0.0, [])

    v_ms = (vehicle_speed_kmh * 1000.0) / 3600.0
    rho_air = 1.225  # kg/m^3
    wind_rad = math.radians(wind_direction_degrees)
    # Wind vector components (direction wind is blowing TO: + 180)
    w_vec_x = -wind_speed_ms * math.sin(wind_rad)
    w_vec_y = -wind_speed_ms * math.cos(wind_rad)

    segments: list[HeadwindResistanceResult] = []
    tot_dist_m = 0.0
    tot_penalty_j = 0.0
    apparent_winds = []
    tailwind_dist = 0.0
    headwind_dist = 0.0

    # Calm aerodynamic baseline power: P_calm = 0.5 * rho * CdA * v^3
    p_calm = 0.5 * rho_air * drag_area_cd_a * (v_ms ** 3)

    for i in range(n - 1):
        p1 = waypoints[i]
        p2 = waypoints[i + 1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        seg_dist = math.hypot(dx, dy)
        if seg_dist <= 1e-4:
            continue

        seg_heading_rad = math.atan2(dx, dy)
        seg_heading_deg = (math.degrees(seg_heading_rad) + 360.0) % 360.0

        # Vehicle travel vector
        v_vec_x = v_ms * math.sin(seg_heading_rad)
        v_vec_y = v_ms * math.cos(seg_heading_rad)

        # Apparent wind vector experienced by the moving body: V_air = V_vehicle - V_wind
        v_air_x = v_vec_x - w_vec_x
        v_air_y = v_vec_y - w_vec_y
        app_speed = math.hypot(v_air_x, v_air_y)
        apparent_winds.append(app_speed)

        # Yaw angle between vehicle motion direction and relative oncoming air flow
        air_dir = math.atan2(v_air_x, v_air_y)
        yaw_angle = abs(air_dir - seg_heading_rad)
        while yaw_angle > math.pi:
            yaw_angle -= 2 * math.pi
        yaw_deg = math.degrees(abs(yaw_angle))

        # Aerodynamic resistive force in direction of motion: F_drag = 0.5 * rho * CdA * V_air^2 * cos(yaw)
        # Power P = F_drag * V_vehicle
        f_drag = 0.5 * rho_air * drag_area_cd_a * (app_speed ** 2) * math.cos(math.radians(yaw_deg))
        p_aero = max(0.0, f_drag * v_ms)
        penalty_w = p_aero - p_calm

        dur_s = seg_dist / max(1.0, v_ms)
        tot_penalty_j += penalty_w * dur_s
        tot_dist_m += seg_dist

        if penalty_w > 0:
            headwind_dist += seg_dist
        else:
            tailwind_dist += seg_dist

        rain_factor = 1.45 if is_raining else 1.0

        segments.append(
            HeadwindResistanceResult(
                segment_heading_degrees=round(seg_heading_deg, 1),
                true_wind_speed_ms=wind_speed_ms,
                true_wind_direction_degrees=wind_direction_degrees,
                apparent_wind_speed_ms=round(app_speed, 2),
                apparent_wind_angle_degrees=round(yaw_deg, 1),
                aerodynamic_power_w=round(p_aero, 1),
                power_penalty_vs_calm_w=round(penalty_w, 1),
                rain_braking_distance_factor=rain_factor,
            )
        )

    tot_km = tot_dist_m / 1000.0
    tot_kwh = tot_penalty_j / (3600.0 * 1000.0)

    return WeatherRouteSummary(
        total_distance_km=tot_km,
        total_wind_energy_penalty_kwh=tot_kwh,
        mean_apparent_wind_speed_ms=float(sum(apparent_winds) / max(1, len(apparent_winds))),
        tailwind_assistance_ratio=tailwind_dist / max(1.0, tot_dist_m),
        headwind_struggle_ratio=headwind_dist / max(1.0, tot_dist_m),
        segments=segments,
    )
