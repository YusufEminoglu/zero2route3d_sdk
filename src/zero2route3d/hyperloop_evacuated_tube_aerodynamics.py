# -*- coding: utf-8 -*-
"""High-Speed Evacuated Tube Hyperloop Aerodynamic Blockage (Kantrowitz Limit) Simulator for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class TubeBlockageConfig:
    tube_internal_diameter_m: float = 4.0
    pod_frontal_area_m2: float = 3.8
    tube_internal_pressure_pa: float = 100.0  # 0.1% atmospheric (near-vacuum)
    pod_cruising_speed_kmh: float = 950.0  # ~264 m/s (High subsonic)
    gas_specific_heat_ratio_gamma: float = 1.40
    pod_drag_coefficient_cd: float = 0.20


@dataclass
class HyperloopAeroResult:
    kantrowitz_limit_mach_number: float
    actual_flight_mach_number: float
    is_choked_flow_limit_exceeded: bool
    aerodynamic_drag_force_n: float
    traction_power_required_kw: float
    blockage_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "kantrowitz_mach": round(self.kantrowitz_limit_mach_number, 3),
            "actual_mach": round(self.actual_flight_mach_number, 3),
            "choked_flow": self.is_choked_flow_limit_exceeded,
            "drag_force_n": round(self.aerodynamic_drag_force_n, 1),
            "traction_power_kw": round(self.traction_power_required_kw, 1),
            "blockage_ratio": round(self.blockage_ratio, 3),
        }


def simulate_hyperloop_pod_aerodynamics(
    config: TubeBlockageConfig | None = None,
    ambient_temperature_k: float = 293.15,
) -> HyperloopAeroResult:
    """Compute Kantrowitz aerodynamic limit and low-pressure pod drag forces in evacuated transport tubes.
    
    Kantrowitz Limit Mach Number M_kan:
    A_bypass / A_tube = (1 - BR)
    M_kan = [ (2 / (gamma - 1)) * ( (1 / (1 - BR))^((gamma - 1)/gamma) - 1 ) ]^0.5
    """
    cfg = config or TubeBlockageConfig()
    gamma = cfg.gas_specific_heat_ratio_gamma
    r_gas = 287.05  # J/kg.K

    # Tube cross section
    a_tube = math.pi * ((cfg.tube_internal_diameter_m / 2.0) ** 2)
    a_pod = cfg.pod_frontal_area_m2
    blockage_ratio = min(0.95, max(0.05, a_pod / a_tube))
    bypass_ratio = 1.0 - blockage_ratio

    # Speed of sound in low-pressure air
    a_sound = math.sqrt(gamma * r_gas * ambient_temperature_k)
    v_pod_mps = cfg.pod_cruising_speed_kmh / 3.6
    actual_mach = v_pod_mps / a_sound

    # Kantrowitz choked flow Mach limit
    term = (1.0 / bypass_ratio) ** ((gamma - 1.0) / gamma) - 1.0
    if term > 0:
        m_kantrowitz = math.sqrt((2.0 / (gamma - 1.0)) * term)
    else:
        m_kantrowitz = 0.50

    is_choked = actual_mach > m_kantrowitz

    # Air density in evacuated tube (Ideal gas: rho = P / (R * T))
    rho_tube = cfg.tube_internal_pressure_pa / (r_gas * ambient_temperature_k)

    # Aerodynamic drag F_drag = 0.5 * rho * v^2 * Cd * A * compressibility_correction
    prandtl_glauert = 1.0 / max(0.2, math.sqrt(max(0.05, 1.0 - min(0.95, actual_mach ** 2))))
    choke_penalty = 3.5 if is_choked else 1.0
    drag_n = 0.5 * rho_tube * (v_pod_mps ** 2) * cfg.pod_drag_coefficient_cd * a_pod * prandtl_glauert * choke_penalty

    power_kw = (drag_n * v_pod_mps) / 1000.0

    return HyperloopAeroResult(
        kantrowitz_limit_mach_number=m_kantrowitz,
        actual_flight_mach_number=actual_mach,
        is_choked_flow_limit_exceeded=is_choked,
        aerodynamic_drag_force_n=drag_n,
        traction_power_required_kw=power_kw,
        blockage_ratio=blockage_ratio,
    )
