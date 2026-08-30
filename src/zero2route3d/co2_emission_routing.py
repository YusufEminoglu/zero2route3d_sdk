# -*- coding: utf-8 -*-
"""Dynamic Vehicle Eco-Routing & 3D Carbon Footprint Emission Estimator for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class VehicleEmissionProfile:
    powertrain_type: str = "DIESEL_EURO6"  # 'DIESEL_EURO6', 'PETROL_EURO6', 'HYBRID', 'BEV'
    curb_weight_kg: float = 1600.0
    aerodynamic_drag_coefficient: float = 0.32
    frontal_area_m2: float = 2.2
    rolling_resistance_coefficient: float = 0.012
    base_fuel_rate_l_per_100km: float = 6.5
    co2_grams_per_liter: float = 2640.0  # grams CO2 / liter diesel


@dataclass
class EmissionAssessmentResult:
    total_co2_kg: float
    total_fuel_consumed_liters: float
    average_co2_g_per_km: float
    energy_expended_kwh: float
    steep_gradient_emission_penalty_kg: float
    is_eco_optimal: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_co2_kg": round(self.total_co2_kg, 2),
            "fuel_liters": round(self.total_fuel_consumed_liters, 2),
            "co2_g_per_km": round(self.average_co2_g_per_km, 1),
            "energy_kwh": round(self.energy_expended_kwh, 2),
            "gradient_penalty_kg": round(self.steep_gradient_emission_penalty_kg, 2),
        }


def calculate_route_co2_emissions(
    path_3d_coordinates: Sequence[tuple[float, float, float]],
    average_speed_kmh: float = 60.0,
    vehicle_profile: VehicleEmissionProfile | None = None,
) -> EmissionAssessmentResult:
    """Compute physical vehicle tractive resistance, fuel consumption, and CO2 emissions along 3D route."""
    veh = vehicle_profile or VehicleEmissionProfile()
    pts = list(path_3d_coordinates)
    if len(pts) < 2:
        return EmissionAssessmentResult(0.0, 0.0, 0.0, 0.0, 0.0, True)

    g = 9.81
    rho_air = 1.225  # kg/m3 air density
    v_ms = average_speed_kmh / 3.6

    tot_dist_m = 0.0
    tot_work_joules = 0.0
    gradient_work_joules = 0.0

    for i in range(len(pts) - 1):
        p1 = pts[i]
        p2 = pts[i + 1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]

        seg_dist = math.hypot(dx, dy, dz)
        tot_dist_m += seg_dist

        # Forces
        # 1. Rolling resistance: F_roll = C_rr * m * g
        f_roll = veh.rolling_resistance_coefficient * veh.curb_weight_kg * g

        # 2. Aerodynamic drag: F_aero = 0.5 * \rho * C_d * A * v^2
        f_aero = 0.5 * rho_air * veh.aerodynamic_drag_coefficient * veh.frontal_area_m2 * (v_ms**2)

        # 3. Gradient resistance: F_grade = m * g * sin(\theta) ~ m * g * (dz / seg_dist)
        sin_theta = dz / max(1e-4, seg_dist)
        f_grade = veh.curb_weight_kg * g * sin_theta

        f_total = f_roll + f_aero + max(0.0, f_grade)
        work_seg = f_total * seg_dist

        tot_work_joules += work_seg
        if dz > 0:
            gradient_work_joules += (f_grade * seg_dist)

    # Internal combustion engine / powertrain efficiency (~30% thermal efficiency for diesel)
    engine_efficiency = 0.30
    fuel_energy_density_j_per_l = 36.0e6  # 36 MJ / liter diesel

    fuel_needed_liters = (tot_work_joules / max(0.1, engine_efficiency)) / fuel_energy_density_j_per_l
    co2_total_kg = (fuel_needed_liters * veh.co2_grams_per_liter) / 1000.0

    grad_fuel = (gradient_work_joules / max(0.1, engine_efficiency)) / fuel_energy_density_j_per_l
    grad_co2_kg = (grad_fuel * veh.co2_grams_per_liter) / 1000.0

    dist_km = tot_dist_m / 1000.0
    g_per_km = (co2_total_kg * 1000.0) / max(0.01, dist_km)
    kwh_total = tot_work_joules / 3.6e6

    return EmissionAssessmentResult(
        total_co2_kg=co2_total_kg,
        total_fuel_consumed_liters=fuel_needed_liters,
        average_co2_g_per_km=g_per_km,
        energy_expended_kwh=kwh_total,
        steep_gradient_emission_penalty_kg=grad_co2_kg,
        is_eco_optimal=(g_per_km < 150.0),
    )
