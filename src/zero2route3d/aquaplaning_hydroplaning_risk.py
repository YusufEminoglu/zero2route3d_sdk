# -*- coding: utf-8 -*-
"""Highway Hydroplaning & Water Film Depth Risk Simulator (Gallaway / AASHTO) for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class PavementCrossSlopeProfile:
    drainage_path_length_m: float = 7.5  # 2 lanes width drainage path
    cross_slope_pct: float = 2.0  # 2.0% normal cross slope
    macrotexture_depth_mm: float = 1.0  # Mean Texture Depth (MTD) in mm
    tire_pressure_kpa: float = 220.0  # ~32 psi
    tire_tread_depth_mm: float = 4.0  # 8mm new, 1.6mm legal limit


@dataclass
class HydroplaningRiskResult:
    rainfall_intensity_mm_hr: float
    water_film_depth_mm: float
    critical_hydroplaning_speed_kmh: float
    current_travel_speed_kmh: float
    is_hydroplaning_risk: bool
    safety_margin_kmh: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rain_intensity_mm_hr": round(self.rainfall_intensity_mm_hr, 1),
            "water_film_mm": round(self.water_film_depth_mm, 2),
            "hydroplaning_speed_kmh": round(self.critical_hydroplaning_speed_kmh, 1),
            "travel_speed_kmh": round(self.current_travel_speed_kmh, 1),
            "is_risk": self.is_hydroplaning_risk,
            "safety_margin_kmh": round(self.safety_margin_kmh, 1),
        }


def evaluate_road_hydroplaning_risk(
    vehicle_speed_kmh: float = 90.0,
    rainfall_intensity_mm_hr: float = 50.0,  # Heavy downpour
    pavement: PavementCrossSlopeProfile | None = None,
) -> HydroplaningRiskResult:
    """Compute pavement water film thickness (Gallaway formula) and AASHTO dynamic hydroplaning speed threshold.
    
    Gallaway Formula for Water Film Thickness (WFT in mm):
    WFT = 0.00338 * (TXD^0.11) * (L^0.43) * (I^0.59) * (S^-0.42) - TXD
    
    Critical Hydroplaning Speed (Horne / Gallaway):
    V_p = 6.35 * sqrt(Tire_Pressure_kPa) * (Tread_Factor)
    """
    p = pavement or PavementCrossSlopeProfile()

    l_ft = p.drainage_path_length_m * 3.28084
    i_in_hr = rainfall_intensity_mm_hr / 25.4
    s_frac = max(0.005, p.cross_slope_pct / 100.0)
    txd_in = p.macrotexture_depth_mm / 25.4

    # Gallaway water film thickness in inches:
    # WFT_in = 0.00338 * (TXD^0.11) * (L^0.43) * (I^0.59) * (S^-0.42) - TXD
    raw_depth_in = (
        0.00338
        * (max(1e-4, txd_in) ** 0.11)
        * (max(1.0, l_ft) ** 0.43)
        * (max(0.1, i_in_hr) ** 0.59)
        * (s_frac ** -0.42)
    )
    wft_in = max(0.0, raw_depth_in - txd_in)
    wft_mm = wft_in * 25.4

    # Critical Dynamic Hydroplaning Speed:
    # NASA / Horne formula: V_p = 6.35 * sqrt(p_kpa) [km/h] modified for water film & tread depth
    base_v_p = 6.35 * math.sqrt(p.tire_pressure_kpa)
    tread_factor = min(1.0, max(0.65, p.tire_tread_depth_mm / 8.0))

    # Water film degradation factor
    film_factor = 1.0 if wft_mm < 1.0 else max(0.70, 1.0 - (wft_mm - 1.0) * 0.08)

    crit_speed = base_v_p * tread_factor * film_factor

    is_risk = vehicle_speed_kmh >= crit_speed
    margin = crit_speed - vehicle_speed_kmh

    return HydroplaningRiskResult(
        rainfall_intensity_mm_hr=rainfall_intensity_mm_hr,
        water_film_depth_mm=wft_mm,
        critical_hydroplaning_speed_kmh=crit_speed,
        current_travel_speed_kmh=vehicle_speed_kmh,
        is_hydroplaning_risk=is_risk,
        safety_margin_kmh=margin,
    )
