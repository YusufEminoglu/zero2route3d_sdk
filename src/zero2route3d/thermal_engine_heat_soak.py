# -*- coding: utf-8 -*-
"""Heavy Vehicle Powertrain Coolant & Transmission Thermal Soak Simulator for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class EngineHeatProfile:
    displacement_liters: float = 12.8  # Heavy-duty diesel
    rated_power_kw: float = 370.0  # 500 HP
    coolant_capacity_liters: float = 45.0
    radiator_heat_rejection_kw: float = 160.0
    ambient_air_temp_c: float = 35.0
    max_safe_coolant_temp_c: float = 105.0


@dataclass
class PowertrainThermalResult:
    is_thermal_overheating_risk: bool
    peak_coolant_temp_c: float
    fan_activation_duration_sec: float
    cumulative_thermal_stress_index: float
    temperature_profile_c: list[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overheating_risk": self.is_thermal_overheating_risk,
            "peak_temp_c": round(self.peak_coolant_temp_c, 1),
            "fan_duration_s": round(self.fan_activation_duration_sec, 1),
            "thermal_stress": round(self.cumulative_thermal_stress_index, 2),
        }


def simulate_powertrain_thermal_load(
    route_segments_distance_elevation: Sequence[tuple[float, float]],  # (seg_dist_m, seg_elevation_gain_m)
    vehicle_gross_weight_tonnes: float = 40.0,
    vehicle_speed_kmh: float = 45.0,
    engine_profile: EngineHeatProfile | None = None,
) -> PowertrainThermalResult:
    """Compute engine waste heat generation vs radiator dissipation on steep mountain ascents (Lumped capacitance model)."""
    eng = engine_profile or EngineHeatProfile()
    segs = list(route_segments_distance_elevation)
    if not segs:
        return PowertrainThermalResult(False, eng.ambient_air_temp_c, 0.0, 0.0, [])

    g = 9.81
    m_kg = vehicle_gross_weight_tonnes * 1000.0
    v_ms = vehicle_speed_kmh / 3.6

    # Coolant thermal mass: C_th = m_coolant * c_p (~4.18 kJ/kg.K)
    c_th_kj_k = eng.coolant_capacity_liters * 4.18  # kJ / deg C

    current_t_c = max(85.0, eng.ambient_air_temp_c + 50.0)  # Operating temp ~85C
    temps: list[float] = []
    fan_time_s = 0.0
    stress_idx = 0.0

    for dist_m, elev_gain_m in segs:
        dt_s = dist_m / max(1.0, v_ms)
        grade = elev_gain_m / max(1.0, dist_m)

        # Power required at wheels: P_wheels = m * g * v * sin(theta) + roll + aero
        p_grade_kw = (m_kg * g * max(0.0, grade) * v_ms) / 1000.0
        p_roll_kw = (0.008 * m_kg * g * v_ms) / 1000.0
        p_engine_kw = min(eng.rated_power_kw, p_grade_kw + p_roll_kw)

        # Waste heat rejected to coolant (~30% of fuel input = ~65% of mechanical power)
        q_waste_kw = p_engine_kw * 0.65

        # Radiator cooling capacity: Q_rad = U * A * (T_coolant - T_ambient) * (v_air factor)
        delta_t = max(0.0, current_t_c - eng.ambient_air_temp_c)
        cooling_power_kw = eng.radiator_heat_rejection_kw * (delta_t / 60.0) * math.sqrt(v_ms / 10.0)

        # Fan kick-in at 95C
        if current_t_c > 95.0:
            cooling_power_kw *= 1.45
            fan_time_s += dt_s

        # Net thermal rate: dT/dt = (Q_waste - Q_rad) / C_th
        q_net_kw = q_waste_kw - cooling_power_kw
        dt_temp = (q_net_kw * dt_s) / c_th_kj_k

        current_t_c = max(80.0, current_t_c + dt_temp)
        temps.append(round(current_t_c, 1))

        if current_t_c > 100.0:
            stress_idx += (current_t_c - 100.0) * (dt_s / 60.0)

    peak_t = max(temps) if temps else current_t_c
    overheating = (peak_t > eng.max_safe_coolant_temp_c)

    return PowertrainThermalResult(
        is_thermal_overheating_risk=overheating,
        peak_coolant_temp_c=peak_t,
        fan_activation_duration_sec=fan_time_s,
        cumulative_thermal_stress_index=stress_idx,
        temperature_profile_c=temps,
    )
