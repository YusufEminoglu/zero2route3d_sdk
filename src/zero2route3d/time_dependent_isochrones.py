# -*- coding: utf-8 -*-
"""Dynamic Congestion 4D Time-Dependent Isochrone Reachability Engine for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class HourlyCongestionFactor:
    hour_of_day: int
    speed_reduction_factor: float  # e.g., 0.65 for morning rush hour (speed = 65% of freeflow)


@dataclass
class DynamicIsochroneRing:
    cutoff_minutes: float
    effective_radius_m: float
    polygon_coordinates: list[tuple[float, float]]


@dataclass
class DynamicIsochroneResult:
    departure_hour: int
    freeflow_base_speed_kmh: float
    congested_effective_speed_kmh: float
    rings: list[DynamicIsochroneRing]

    def to_dict(self) -> dict[str, Any]:
        return {
            "departure_hour": self.departure_hour,
            "base_speed_kmh": round(self.freeflow_base_speed_kmh, 1),
            "congested_speed_kmh": round(self.congested_effective_speed_kmh, 1),
            "rings_count": len(self.rings),
            "max_reach_m": round(self.rings[-1].effective_radius_m, 1) if self.rings else 0.0,
        }


def solve_time_dependent_isochrones(
    origin_point: tuple[float, float],
    departure_hour: int = 8,  # 8 AM morning peak
    cutoff_minutes_intervals: Sequence[float] = (10.0, 20.0, 30.0),
    freeflow_speed_kmh: float = 50.0,
    hourly_congestion_profile: Sequence[HourlyCongestionFactor] | None = None,
    num_polygon_vertices: int = 16,
) -> DynamicIsochroneResult:
    """Compute time-dependent dynamic isochrone reachability rings modulated by diurnal traffic congestion curves."""
    # Default diurnal congestion curve (1.0 = freeflow, 0.60 = rush hour)
    default_curve = {
        7: 0.75, 8: 0.60, 9: 0.70,  # AM peak
        12: 0.85, 13: 0.85,          # Lunch
        17: 0.55, 18: 0.50, 19: 0.65 # PM peak
    }

    if hourly_congestion_profile:
        profile_map = {cf.hour_of_day: cf.speed_reduction_factor for cf in hourly_congestion_profile}
        speed_factor = profile_map.get(departure_hour, 1.0)
    else:
        speed_factor = default_curve.get(departure_hour, 0.95)

    eff_speed_kmh = freeflow_speed_kmh * speed_factor
    speed_mps = (eff_speed_kmh * 1000.0) / 3600.0

    ox, oy = origin_point
    rings: list[DynamicIsochroneRing] = []

    for t_min in cutoff_minutes_intervals:
        dist_m = speed_mps * (t_min * 60.0)

        # Generate smooth circular/elliptical polygon envelope in meters (or lat/lon approximated)
        poly = []
        for i in range(num_polygon_vertices + 1):
            angle = (2.0 * math.pi * i) / num_polygon_vertices
            px = ox + dist_m * math.cos(angle)
            py = oy + dist_m * math.sin(angle)
            poly.append((round(px, 2), round(py, 2)))

        rings.append(
            DynamicIsochroneRing(
                cutoff_minutes=t_min,
                effective_radius_m=dist_m,
                polygon_coordinates=poly,
            )
        )

    return DynamicIsochroneResult(
        departure_hour=departure_hour,
        freeflow_base_speed_kmh=freeflow_speed_kmh,
        congested_effective_speed_kmh=eff_speed_kmh,
        rings=rings,
    )
