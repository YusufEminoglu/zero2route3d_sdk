# -*- coding: utf-8 -*-
"""Micro-Mobility E-Scooter & E-Bike Kinetic Stability & Vibrational Roughness Analyzer for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class VibrationalComfortResult:
    """ISO 2631-1 whole-body vibration comfort evaluation along route segments."""

    surface_roughness_iri_m_per_km: float
    rms_acceleration_m_s2: float
    vibration_dose_value_vdv: float
    comfort_classification: str  # 'Comfortable', 'A Little Uncomfortable', 'Fairly Uncomfortable', 'Extremely Uncomfortable'
    stability_loss_risk_score: float  # 0.0 (safe) to 1.0 (fall risk on curb/pothole)


@dataclass
class MicroMobilityRouteScore:
    total_distance_km: float
    mean_vibration_rms: float
    uncomfortable_segments_count: int
    fall_risk_hotspots_count: int
    overall_bikeability_score: float  # 0 to 100
    segments: list[VibrationalComfortResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_distance_km": round(self.total_distance_km, 3),
            "mean_vibration_rms": round(self.mean_vibration_rms, 3),
            "uncomfortable_segments": self.uncomfortable_segments_count,
            "fall_risk_hotspots": self.fall_risk_hotspots_count,
            "overall_bikeability_score": round(self.overall_bikeability_score, 1),
        }


def evaluate_micro_mobility_comfort(
    segment_lengths_m: Sequence[float],
    surface_types: Sequence[str],  # 'asphalt_smooth', 'asphalt_rough', 'cobblestone', 'gravel', 'paved_tiles'
    speeds_kmh: Sequence[float] | float = 18.0,
    wheel_diameter_inches: float = 8.5,  # 8.5" for e-scooter, 28" for road bike
) -> MicroMobilityRouteScore:
    """Evaluate vibration and kinetic stability for micromobility vehicles according to ISO 2631-1."""
    iri_lookup = {
        "asphalt_smooth": 1.5,
        "asphalt_rough": 3.8,
        "paved_tiles": 5.2,
        "gravel": 8.0,
        "cobblestone": 12.5,
    }

    n = len(segment_lengths_m)
    results: list[VibrationalComfortResult] = []
    tot_dist_m = sum(segment_lengths_m)
    uncomfortable_cnt = 0
    risk_cnt = 0
    rms_list: list[float] = []

    # Small wheels amplify roughness vibrations inversely proportional to radius
    wheel_amplification = math.sqrt(28.0 / max(5.0, wheel_diameter_inches))

    for i in range(n):
        d_m = segment_lengths_m[i]
        st = surface_types[i] if i < len(surface_types) else "asphalt_smooth"
        v_kmh = speeds_kmh[i] if isinstance(speeds_kmh, (list, tuple)) else float(speeds_kmh)
        v_ms = (v_kmh * 1000.0) / 3600.0

        iri = iri_lookup.get(st.lower(), 2.5)

        # Approximate vertical RMS acceleration a_w (m/s^2) = 0.08 * IRI * (v/10)^0.7 * wheel_factor
        a_rms = 0.08 * iri * ((v_ms / 2.78) ** 0.7) * wheel_amplification

        # Duration
        dur_s = d_m / max(0.5, v_ms)
        vdv = a_rms * (dur_s ** 0.25)

        # ISO 2631-1 Comfort scale
        if a_rms < 0.315:
            comfort = "Not Uncomfortable"
        elif a_rms < 0.63:
            comfort = "A Little Uncomfortable"
        elif a_rms < 1.0:
            comfort = "Fairly Uncomfortable"
            uncomfortable_cnt += 1
        else:
            comfort = "Extremely Uncomfortable"
            uncomfortable_cnt += 1

        # Fall risk score (combination of roughness + speed + small wheels)
        risk = min(1.0, (iri / 15.0) * (v_kmh / 25.0) * (wheel_amplification / 1.8))
        if risk >= 0.60:
            risk_cnt += 1

        rms_list.append(a_rms)
        results.append(
            VibrationalComfortResult(
                surface_roughness_iri_m_per_km=iri,
                rms_acceleration_m_s2=round(a_rms, 3),
                vibration_dose_value_vdv=round(vdv, 3),
                comfort_classification=comfort,
                stability_loss_risk_score=round(risk, 3),
            )
        )

    mean_rms = sum(rms_list) / max(1, len(rms_list))
    bikeability = max(0.0, 100.0 - (mean_rms * 45.0) - (risk_cnt * 5.0))

    return MicroMobilityRouteScore(
        total_distance_km=tot_dist_m / 1000.0,
        mean_vibration_rms=mean_rms,
        uncomfortable_segments_count=uncomfortable_cnt,
        fall_risk_hotspots_count=risk_cnt,
        overall_bikeability_score=bikeability,
        segments=results,
    )
