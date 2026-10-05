# -*- coding: utf-8 -*-
"""Biomechanical Trail Running, Caloric Expenditure & Heart Rate Kinematics for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class BiomechanicalSegmentResult:
    distance_m: float
    slope_percent: float
    speed_kmh: float
    energy_cost_j_kg_m: float  # Minetti metabolic cost (J / kg / m)
    metabolic_equivalent_mets: float  # METs (1 MET = 3.5 ml O2 / kg / min)
    calories_burned_kcal: float
    estimated_heart_rate_bpm: int
    fatigue_index: float  # 0.0 to 1.0


@dataclass
class BiomechanicalTrailSummary:
    total_distance_km: float
    total_elevation_gain_m: float
    total_elevation_loss_m: float
    total_calories_burned_kcal: float
    mean_metabolic_mets: float
    mean_heart_rate_bpm: int
    peak_heart_rate_bpm: int
    hr_zone_distribution_percent: dict[str, float]  # Zone 1 (Recovery) to Zone 5 (Anaerobic)
    segments: list[BiomechanicalSegmentResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_distance_km": round(self.total_distance_km, 3),
            "elevation_gain_m": round(self.total_elevation_gain_m, 1),
            "elevation_loss_m": round(self.total_elevation_loss_m, 1),
            "total_calories_kcal": round(self.total_calories_burned_kcal, 1),
            "mean_mets": round(self.mean_metabolic_mets, 1),
            "mean_heart_rate_bpm": self.mean_heart_rate_bpm,
            "peak_heart_rate_bpm": self.peak_heart_rate_bpm,
            "hr_zones": {k: round(v, 1) for k, v in self.hr_zone_distribution_percent.items()},
        }


def _minetti_cost_of_running(slope_fraction: float) -> float:
    """Minetti et al. (2002) energy cost of human walking/running on slopes (J / kg / m).

    C_r(i) = 155.4 * i^5 - 30.4 * i^4 - 43.3 * i^3 + 46.3 * i^2 + 19.5 * i + 3.6
    """
    i = max(-0.45, min(0.45, slope_fraction))
    cost = (
        155.4 * (i ** 5)
        - 30.4 * (i ** 4)
        - 43.3 * (i ** 3)
        + 46.3 * (i ** 2)
        + 19.5 * i
        + 3.6
    )
    return max(1.8, cost)


class BiomechanicalKinematicsTracker:
    """Computes high-precision metabolic energy, calories, and cardiac load for 3D athletes."""

    def __init__(
        self,
        athlete_mass_kg: float = 72.0,
        pack_weight_kg: float = 4.0,
        athlete_age: int = 32,
        resting_hr_bpm: int = 55,
    ) -> None:
        self.mass = athlete_mass_kg
        self.pack = pack_weight_kg
        self.total_mass = self.mass + self.pack
        self.age = athlete_age
        self.hr_rest = resting_hr_bpm
        self.hr_max = 220 - self.age

    def analyze_trail(
        self,
        waypoints_3d: Sequence[tuple[float, float, float]],
        base_speed_kmh: float = 5.2,
    ) -> BiomechanicalTrailSummary:
        n = len(waypoints_3d)
        if n < 2:
            return BiomechanicalTrailSummary(0.0, 0.0, 0.0, 0.0, 0.0, self.hr_rest, self.hr_rest, {}, [])

        tot_dist_m = 0.0
        elev_gain = 0.0
        elev_loss = 0.0
        tot_kcal = 0.0
        hr_list: list[int] = []
        met_list: list[float] = []
        segments: list[BiomechanicalSegmentResult] = []

        zone_counts = {"Z1_Warmup": 0, "Z2_Aerobic": 0, "Z3_Tempo": 0, "Z4_Threshold": 0, "Z5_Anaerobic": 0}

        for idx in range(n - 1):
            p1 = waypoints_3d[idx]
            p2 = waypoints_3d[idx + 1]

            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            dz = p2[2] - p1[2]
            d_horiz = math.hypot(dx, dy)
            d_3d = math.sqrt(d_horiz ** 2 + dz ** 2)
            if d_3d <= 1e-4:
                continue

            if dz > 0:
                elev_gain += dz
            else:
                elev_loss += abs(dz)

            slope_frac = dz / max(1e-4, d_horiz)
            slope_pct = slope_frac * 100.0

            # Speed adjustment based on Tobler / slope
            speed_factor = math.exp(-3.5 * abs(slope_frac + 0.05))
            v_kmh = max(1.5, base_speed_kmh * speed_factor)
            v_ms = (v_kmh * 1000.0) / 3600.0
            dur_s = d_3d / v_ms

            # Energy cost (J / kg / m)
            c_r = _minetti_cost_of_running(slope_frac)
            segment_energy_j = c_r * self.total_mass * d_3d
            segment_kcal = segment_energy_j / 4184.0
            tot_kcal += segment_kcal

            # METs: 1 MET = 1.0 kcal / kg / hr
            dur_hr = dur_s / 3600.0
            mets = (segment_kcal / self.mass) / max(1e-4, dur_hr)
            met_list.append(mets)

            # Heart rate estimation: HR = HR_rest + %VO2max * (HR_max - HR_rest)
            vo2_frac = min(1.0, mets / 14.0)  # Assuming VO2max around 14 METs
            hr_bpm = int(self.hr_rest + vo2_frac * (self.hr_max - self.hr_rest))
            hr_bpm = max(self.hr_rest, min(self.hr_max, hr_bpm))
            hr_list.append(hr_bpm)

            # HR Zone classification
            hr_pct = (hr_bpm / self.hr_max) * 100.0
            if hr_pct < 60:
                zone_counts["Z1_Warmup"] += 1
            elif hr_pct < 70:
                zone_counts["Z2_Aerobic"] += 1
            elif hr_pct < 80:
                zone_counts["Z3_Tempo"] += 1
            elif hr_pct < 90:
                zone_counts["Z4_Threshold"] += 1
            else:
                zone_counts["Z5_Anaerobic"] += 1

            fatigue = min(1.0, (tot_kcal / 1200.0) + (idx / n) * 0.30)
            tot_dist_m += d_3d

            segments.append(
                BiomechanicalSegmentResult(
                    distance_m=round(d_3d, 1),
                    slope_percent=round(slope_pct, 1),
                    speed_kmh=round(v_kmh, 1),
                    energy_cost_j_kg_m=round(c_r, 2),
                    metabolic_equivalent_mets=round(mets, 1),
                    calories_burned_kcal=round(segment_kcal, 2),
                    estimated_heart_rate_bpm=hr_bpm,
                    fatigue_index=round(fatigue, 2),
                )
            )

        tot_segs = max(1, len(segments))
        zone_pct = {k: (v / tot_segs) * 100.0 for k, v in zone_counts.items()}

        return BiomechanicalTrailSummary(
            total_distance_km=tot_dist_m / 1000.0,
            total_elevation_gain_m=elev_gain,
            total_elevation_loss_m=elev_loss,
            total_calories_burned_kcal=tot_kcal,
            mean_metabolic_mets=float(sum(met_list) / len(met_list)) if met_list else 0.0,
            mean_heart_rate_bpm=int(sum(hr_list) / len(hr_list)) if hr_list else self.hr_rest,
            peak_heart_rate_bpm=max(hr_list) if hr_list else self.hr_rest,
            hr_zone_distribution_percent=zone_pct,
            segments=segments,
        )
