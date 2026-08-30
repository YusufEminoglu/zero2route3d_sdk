# -*- coding: utf-8 -*-
"""Downhill Gradient Thermal Brake Fade & Runaway Ramp Safety Analyzer for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class BrakeThermalProfile:
    vehicle_mass_kg: float = 24000.0  # 24-ton commercial truck
    brake_drum_mass_kg: float = 120.0
    initial_brake_temp_c: float = 80.0
    max_safe_brake_temp_c: float = 300.0  # Above this, brake fade occurs
    specific_heat_capacity_j_kg_k: float = 500.0  # Cast iron brakes


@dataclass
class DescentSafetyResult:
    is_descent_safe: bool
    peak_brake_temperature_c: float
    total_potential_energy_mj: float
    temperature_rise_c: float
    brake_fade_risk_level: str  # 'LOW', 'MODERATE', 'CRITICAL_RUNAWAY'
    recommended_safe_descent_speed_kmh: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_safe": self.is_descent_safe,
            "peak_brake_temp_c": round(self.peak_brake_temperature_c, 1),
            "temp_rise_c": round(self.temperature_rise_c, 1),
            "potential_energy_mj": round(self.total_potential_energy_mj, 2),
            "fade_risk": self.brake_fade_risk_level,
            "recommended_speed_kmh": round(self.recommended_safe_descent_speed_kmh, 1),
        }


def evaluate_steep_descent_brake_fade(
    descent_distance_m: float,
    elevation_drop_m: float,
    descent_speed_kmh: float = 60.0,
    vehicle_profile: BrakeThermalProfile | None = None,
) -> DescentSafetyResult:
    """Simulate kinetic and gravitational potential energy dissipation into vehicle braking system."""
    veh = vehicle_profile or BrakeThermalProfile()

    # Potential energy: \Delta E_p = m * g * \Delta h
    g = 9.81
    delta_h = max(0.0, elevation_drop_m)
    pe_joules = veh.vehicle_mass_kg * g * delta_h
    pe_mj = pe_joules / 1e6

    # Portion absorbed by brakes vs engine compression/aerodynamics (~65% by friction brakes on heavy descents)
    brake_energy_absorbed = pe_joules * 0.65

    # Temperature rise: \Delta T = Q / (m_drum * c_p)
    thermal_mass = veh.brake_drum_mass_kg * veh.specific_heat_capacity_j_kg_k
    temp_rise = brake_energy_absorbed / max(1.0, thermal_mass)

    peak_temp = veh.initial_brake_temp_c + temp_rise

    # Risk level classification
    if peak_temp <= 180.0:
        risk = "LOW"
        rec_speed = descent_speed_kmh
    elif peak_temp <= veh.max_safe_brake_temp_c:
        risk = "MODERATE"
        rec_speed = min(40.0, descent_speed_kmh * 0.7)
    else:
        risk = "CRITICAL_RUNAWAY"
        rec_speed = min(25.0, descent_speed_kmh * 0.4)

    is_safe = (peak_temp <= veh.max_safe_brake_temp_c)

    return DescentSafetyResult(
        is_descent_safe=is_safe,
        peak_brake_temperature_c=peak_temp,
        total_potential_energy_mj=pe_mj,
        temperature_rise_c=temp_rise,
        brake_fade_risk_level=risk,
        recommended_safe_descent_speed_kmh=rec_speed,
    )
