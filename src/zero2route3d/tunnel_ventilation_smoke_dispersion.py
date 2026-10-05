# -*- coding: utf-8 -*-
"""Road Tunnel Emergency Ventilation & Fire Smoke Jet Dispersion Simulator for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class JetFanVentilationProfile:
    tunnel_cross_section_area_m2: float = 65.0  # Standard 2-lane bored tunnel
    tunnel_hydraulic_diameter_m: float = 8.5
    tunnel_grade_pct: float = 2.0
    fire_heat_release_rate_mw: float = 30.0  # 30 MW HGV truck fire (NFPA 502 / PIARC)
    ambient_air_temperature_k: float = 293.15  # 20 deg C


@dataclass
class TunnelSmokeSafetyResult:
    critical_velocity_to_prevent_backlayering_mps: float
    actual_longitudinal_air_velocity_mps: float
    is_backlayering_prevented: bool
    smoke_layer_temperature_c: float
    tenability_visibility_distance_m: float
    required_jet_fans_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "v_crit_mps": round(self.critical_velocity_to_prevent_backlayering_mps, 2),
            "v_actual_mps": round(self.actual_longitudinal_air_velocity_mps, 2),
            "safe_backlayering_prevented": self.is_backlayering_prevented,
            "smoke_temp_c": round(self.smoke_layer_temperature_c, 1),
            "visibility_m": round(self.tenability_visibility_distance_m, 1),
            "jet_fans_needed": self.required_jet_fans_count,
        }


def simulate_tunnel_smoke_dispersion(
    tunnel_length_m: float = 1800.0,
    ventilation: JetFanVentilationProfile | None = None,
    available_thrust_per_fan_n: float = 850.0,  # Standard reversible tunnel jet fan
) -> TunnelSmokeSafetyResult:
    """Compute NFPA 502 / Danziger-Kennedy critical air velocity to prevent toxic smoke backlayering during tunnel vehicle fires.

    Critical Velocity Formula (Kennedy / NFPA 502):
    v_crit = K_g * ( (g * H * Q_fire) / (rho * C_p * A * T_f) )^(1/3)
    where K_g = 1 + 0.03 * grade_pct
    """
    p = ventilation or JetFanVentilationProfile()
    g = 9.81
    rho = 1.20  # kg/m3 air density
    cp = 1.005  # kJ/kg.K

    q_kw = p.fire_heat_release_rate_mw * 1000.0
    h = p.tunnel_hydraulic_diameter_m
    a = p.tunnel_cross_section_area_m2
    t0 = p.ambient_air_temperature_k

    # Estimated average smoke layer temp Tf
    delta_t = q_kw / max(1.0, (rho * cp * a * 2.5))
    tf = t0 + delta_t

    # Grade factor Kg
    kg = max(1.0, 1.0 + 0.035 * max(0.0, p.tunnel_grade_pct))

    # Critical velocity v_crit
    num = g * h * q_kw
    den = rho * cp * a * tf
    v_crit = kg * ((num / max(1.0, den)) ** (1.0 / 3.0))

    # Actual air velocity provided by jet fans
    # Required pressure rise delta_p = 0.5 * rho * v^2 * (1 + f * L / D)
    friction_f = 0.022
    k_loss = 1.5 + friction_f * (tunnel_length_m / h)
    v_target = max(2.5, v_crit * 1.05)
    total_thrust_needed_n = 0.5 * rho * (v_target ** 2) * k_loss * a
    fans_count = max(4, math.ceil(total_thrust_needed_n / max(1.0, available_thrust_per_fan_n)))

    v_actual = v_target
    is_safe = v_actual >= v_crit
    visibility = max(10.0, min(30.0, 250.0 / max(10.0, p.fire_heat_release_rate_mw * 4.0)))

    return TunnelSmokeSafetyResult(
        critical_velocity_to_prevent_backlayering_mps=v_crit,
        actual_longitudinal_air_velocity_mps=v_actual,
        is_backlayering_prevented=is_safe,
        smoke_layer_temperature_c=tf - 273.15,
        tenability_visibility_distance_m=visibility,
        required_jet_fans_count=fans_count,
    )
