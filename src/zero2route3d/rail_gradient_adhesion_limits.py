# -*- coding: utf-8 -*-
"""Freight & High-Speed Rail Adhesion Limits & Tractive Effort Simulator for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence


class RailSurfaceCondition(str, Enum):
    DRY_CLEAN = "DRY_CLEAN"
    WET_RAIL = "WET_RAIL"
    LEAF_CONTAMINATED = "LEAF_CONTAMINATED"
    FROST_ICING = "FROST_ICING"


@dataclass
class LocomotiveTractionProfile:
    locomotive_weight_tonnes: float = 120.0  # e.g., Co-Co 6-axle electric loco
    axle_load_tonnes: float = 20.0
    maximum_power_kw: float = 6400.0  # 6.4 MW
    trailing_train_tonnes: float = 2400.0  # Heavy freight train
    operating_speed_kmh: float = 60.0


@dataclass
class RailAdhesionResult:
    curtius_kniffler_adhesion_coeff: float
    maximum_tractive_effort_kn: float
    maximum_negotiable_gradient_pct: float
    is_wheel_slip_risk: bool
    tractive_power_utilization_pct: float
    braking_distance_margin_m: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "adhesion_mu": round(self.curtius_kniffler_adhesion_coeff, 3),
            "max_tractive_kn": round(self.maximum_tractive_effort_kn, 1),
            "max_gradient_pct": round(self.maximum_negotiable_gradient_pct, 2),
            "wheel_slip_risk": self.is_wheel_slip_risk,
            "power_utilization_pct": round(self.tractive_power_utilization_pct, 1),
        }


def evaluate_rail_tractive_adhesion(
    gradient_pct: float = 1.8,  # 18 permille climb
    locomotive: LocomotiveTractionProfile | None = None,
    rail_condition: RailSurfaceCondition = RailSurfaceCondition.DRY_CLEAN,
) -> RailAdhesionResult:
    """Compute wheel-rail Curtius-Kniffler adhesion coefficient, tractive limits, and maximum grade climbability."""
    loco = locomotive or LocomotiveTractionProfile()
    v = max(1.0, loco.operating_speed_kmh)

    # Curtius-Kniffler empirical formula for base adhesion mu(v):
    # mu(v) = 7.5 / (v + 44) + 0.161
    base_mu = (7.5 / (v + 44.0)) + 0.161

    # Environmental degradation factors
    degradation_factors = {
        RailSurfaceCondition.DRY_CLEAN: 1.0,
        RailSurfaceCondition.WET_RAIL: 0.72,
        RailSurfaceCondition.LEAF_CONTAMINATED: 0.45,
        RailSurfaceCondition.FROST_ICING: 0.50,
    }
    mu = base_mu * degradation_factors.get(rail_condition, 1.0)

    # Adhesion tractive effort limit: F_adh = mu * M_loco * g
    g = 9.81
    f_adhesion_kn = mu * loco.locomotive_weight_tonnes * g

    # Tractive effort from power: F_power = P / v
    v_mps = v / 3.6
    f_power_kn = loco.maximum_power_kw / max(1.0, v_mps)
    available_tractive_kn = min(f_adhesion_kn, f_power_kn)

    # Train resistance on grade: R_grade = (M_total * g * (i_permille / 1000)) + Rolling_Res
    tot_mass = loco.locomotive_weight_tonnes + loco.trailing_train_tonnes
    r_grade_kn = tot_mass * g * (gradient_pct / 100.0)
    r_roll_kn = tot_mass * g * 0.0025  # Davis rolling resistance ~2.5 N/kN
    tot_resistance_kn = r_grade_kn + r_roll_kn

    # Maximum negotiable gradient: i_max = ((F_adh - R_roll) / (M_tot * g)) * 100
    max_grad = ((available_tractive_kn - r_roll_kn) / max(1.0, tot_mass * g)) * 100.0

    is_slip = tot_resistance_kn > f_adhesion_kn
    power_util = (tot_resistance_kn / max(1.0, f_power_kn)) * 100.0

    return RailAdhesionResult(
        curtius_kniffler_adhesion_coeff=mu,
        maximum_tractive_effort_kn=available_tractive_kn,
        maximum_negotiable_gradient_pct=max(0.0, max_grad),
        is_wheel_slip_risk=is_slip,
        tractive_power_utilization_pct=min(100.0, max(0.0, power_util)),
        braking_distance_margin_m=max(0.0, 1000.0 - (v ** 2) / (2 * mu * g * 0.5)),
    )
