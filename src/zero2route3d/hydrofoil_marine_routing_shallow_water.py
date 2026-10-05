# -*- coding: utf-8 -*-
"""Hydrofoil Marine Dynamic Foil Lift & Shallow-Water Bathymetric Router for zero2route3d."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class HydrofoilVesselProfile:
    displacement_tonnes: float = 45.0
    foilborne_takeoff_speed_knots: float = 22.0  # Speed at which hull lifts above water
    cruise_speed_knots: float = 38.0
    hullborne_draft_m: float = 2.8
    foilborne_draft_m: float = 1.4  # Shallow draft when foils are lifting hull
    hydrofoil_lift_drag_ratio: float = 12.5


@dataclass
class HydrofoilRouteResult:
    total_voyage_nautical_miles: float
    estimated_travel_time_hours: float
    foilborne_distance_pct: float
    minimum_under_keel_clearance_m: float
    shallow_water_squat_risk_detected: bool
    fuel_consumption_liters: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "voyage_nm": round(self.total_voyage_nautical_miles, 2),
            "time_hours": round(self.estimated_travel_time_hours, 2),
            "foilborne_pct": round(self.foilborne_distance_pct, 1),
            "min_ukc_m": round(self.minimum_under_keel_clearance_m, 2),
            "squat_risk": self.shallow_water_squat_risk_detected,
            "fuel_liters": round(self.fuel_consumption_liters, 1),
        }


def simulate_hydrofoil_marine_route(
    route_waypoints_lat_lon_depth: Sequence[tuple[float, float, float]],  # (lat, lon, bathymetric_depth_m)
    vessel: HydrofoilVesselProfile | None = None,
) -> HydrofoilRouteResult:
    """Simulate coastal hydrofoil marine passage, hydrodynamic lift transition, and shallow water squat clearance."""
    vp = vessel or HydrofoilVesselProfile()
    pts = list(route_waypoints_lat_lon_depth)
    if len(pts) < 2:
        return HydrofoilRouteResult(0.0, 0.0, 0.0, 10.0, False, 0.0)

    tot_dist_nm = 0.0
    foilborne_dist_nm = 0.0
    min_ukc = 999.0
    squat_risk = False

    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i + 1]
        # Great-circle distance approx (nm)
        d_lat = (p2[0] - p1[0]) * 60.0
        d_lon = (p2[1] - p1[1]) * 60.0 * math.cos(math.radians((p1[0] + p2[0]) / 2.0))
        leg_nm = math.hypot(d_lat, d_lon)
        tot_dist_nm += leg_nm

        depth = min(p1[2], p2[2])
        # Under-keel clearance
        effective_draft = vp.foilborne_draft_m if leg_nm > 1.0 else vp.hullborne_draft_m
        ukc = depth - effective_draft
        min_ukc = min(min_ukc, ukc)

        # Shallow water squat effect occurs when depth / draft < 1.5
        if depth / max(0.5, effective_draft) < 1.4:
            squat_risk = True

        if leg_nm > 0.5 and depth > 4.0:
            foilborne_dist_nm += leg_nm

    foil_pct = (foilborne_dist_nm / max(0.01, tot_dist_nm)) * 100.0
    avg_speed = vp.cruise_speed_knots if foil_pct > 50.0 else vp.foilborne_takeoff_speed_knots * 0.8
    duration_h = tot_dist_nm / max(1.0, avg_speed)

    # Specific fuel consumption (liters/nm ~ displacement / (L/D))
    fuel_l = tot_dist_nm * (vp.displacement_tonnes / max(1.0, vp.hydrofoil_lift_drag_ratio)) * 3.8

    return HydrofoilRouteResult(
        total_voyage_nautical_miles=tot_dist_nm,
        estimated_travel_time_hours=duration_h,
        foilborne_distance_pct=min(100.0, foil_pct),
        minimum_under_keel_clearance_m=max(0.0, min_ukc),
        shallow_water_squat_risk_detected=squat_risk,
        fuel_consumption_liters=fuel_l,
    )
