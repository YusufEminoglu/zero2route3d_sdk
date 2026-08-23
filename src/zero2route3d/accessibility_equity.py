"""Urban Mobility Accessibility Equity Scorecard Engine.

Implements:
1. Enhanced Two-Step Floating Catchment Area (E2SFCA) with continuous Gaussian decay.
2. Spatial Gini Coefficient & Lorenz Curve generation for accessibility justice.
3. Theil Index entropy decomposition for spatial disparities.
4. Automated equity classification (Transit Deserts, Vulnerable, Oasis).

Author: Yusuf Eminoglu
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


@dataclass
class ZoneAccessibilityRecord:
    """Individual zone demographic and computed spatial accessibility indicators."""

    zone_id: str
    name: str
    lon: float
    lat: float
    population: float
    accessibility_score: float = 0.0
    equity_tier: str = "Undetermined"
    percentile_rank: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "lon": self.lon,
            "lat": self.lat,
            "population": self.population,
            "accessibility_score": round(self.accessibility_score, 4),
            "equity_tier": self.equity_tier,
            "percentile_rank": round(self.percentile_rank, 1),
        }


@dataclass
class SupplyFacility:
    """Public service destination / facility (e.g. hospital, metro station, school)."""

    facility_id: str
    name: str
    lon: float
    lat: float
    capacity: float


@dataclass
class EquityScorecardResult:
    """Comprehensive Spatial Equity & Transport Justice Analytical Report."""

    gini_coefficient: float
    palma_ratio: float  # Top 10% / Bottom 40% accessibility ratio
    theil_index: float
    mean_accessibility: float
    median_accessibility: float
    lorenz_curve: List[Dict[str, float]]
    zones: List[ZoneAccessibilityRecord]
    tier_distribution: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gini_coefficient": round(self.gini_coefficient, 4),
            "palma_ratio": round(self.palma_ratio, 2),
            "theil_index": round(self.theil_index, 4),
            "mean_accessibility": round(self.mean_accessibility, 4),
            "median_accessibility": round(self.median_accessibility, 4),
            "tier_distribution": self.tier_distribution,
            "lorenz_curve": self.lorenz_curve,
            "zone_count": len(self.zones),
        }


class AccessibilityEquityEngine:
    """Spatial accessibility computation and distributional justice scorecard."""

    def __init__(self, catchment_radius_m: float = 1500.0) -> None:
        self.catchment_radius_m = catchment_radius_m

    def gaussian_decay(self, distance_m: float) -> float:
        """Continuous Gaussian distance friction function."""
        if distance_m > self.catchment_radius_m:
            return 0.0
        d_0 = self.catchment_radius_m
        numerator = math.exp(-0.5 * ((distance_m / d_0) ** 2)) - math.exp(-0.5)
        denominator = 1.0 - math.exp(-0.5)
        return max(0.0, numerator / denominator)

    def compute_e2sfca(
        self,
        demand_zones: Sequence[ZoneAccessibilityRecord],
        supply_facilities: Sequence[SupplyFacility],
        distance_func: Optional[Callable[[Tuple[float, float], Tuple[float, float]], float]] = None,
    ) -> EquityScorecardResult:
        """Execute Enhanced Two-Step Floating Catchment Area (E2SFCA) algorithm."""
        from .kinematics import haversine_distance_2d

        dist_fn = distance_func or (lambda p1, p2: haversine_distance_2d(p1, p2))
        zones_list = [
            ZoneAccessibilityRecord(
                zone_id=z.zone_id,
                name=z.name,
                lon=z.lon,
                lat=z.lat,
                population=z.population,
            )
            for z in demand_zones
        ]

        # Step 1: Compute Provider-to-Population Ratio (R_j)
        facility_ratios: Dict[str, float] = {}
        for fac in supply_facilities:
            weighted_demand = 0.0
            for z in zones_list:
                d = dist_fn((fac.lon, fac.lat), (z.lon, z.lat))
                if d <= self.catchment_radius_m:
                    w = self.gaussian_decay(d)
                    weighted_demand += z.population * w

            if weighted_demand > 0:
                facility_ratios[fac.facility_id] = fac.capacity / weighted_demand
            else:
                facility_ratios[fac.facility_id] = 0.0

        # Step 2: Compute Accessibility Score (A_i) for each Demand Zone
        for z in zones_list:
            acc_score = 0.0
            for fac in supply_facilities:
                d = dist_fn((z.lon, z.lat), (fac.lon, fac.lat))
                if d <= self.catchment_radius_m:
                    w = self.gaussian_decay(d)
                    acc_score += facility_ratios[fac.facility_id] * w
            z.accessibility_score = acc_score

        # Step 3: Equity Diagnostics (Gini, Lorenz Curve, Theil Index)
        sorted_zones = sorted(zones_list, key=lambda x: x.accessibility_score)
        total_pop = sum(z.population for z in sorted_zones) or 1.0
        total_acc_weighted = sum(z.population * z.accessibility_score for z in sorted_zones) or 1.0

        cum_pop = 0.0
        cum_acc = 0.0
        lorenz_points: List[Dict[str, float]] = [{"pop_share": 0.0, "acc_share": 0.0}]
        gini_sum = 0.0
        prev_p = 0.0
        prev_a = 0.0

        for idx, z in enumerate(sorted_zones):
            z.percentile_rank = (idx + 1) / len(sorted_zones) * 100.0
            cum_pop += z.population
            cum_acc += z.population * z.accessibility_score

            p_curr = cum_pop / total_pop
            a_curr = cum_acc / total_acc_weighted

            gini_sum += (p_curr - prev_p) * (a_curr + prev_a)
            prev_p = p_curr
            prev_a = a_curr

            if idx % max(1, len(sorted_zones) // 20) == 0 or idx == len(sorted_zones) - 1:
                lorenz_points.append({"pop_share": round(p_curr, 4), "acc_share": round(a_curr, 4)})

        gini = max(0.0, min(1.0, 1.0 - gini_sum))

        # Theil Index
        mean_acc = total_acc_weighted / total_pop
        theil = 0.0
        for z in sorted_zones:
            if z.accessibility_score > 0 and mean_acc > 0:
                ratio = z.accessibility_score / mean_acc
                theil += (z.population / total_pop) * ratio * math.log(ratio)
        theil = max(0.0, theil)

        # Palma Ratio
        bottom_40_acc = sum(
            z.accessibility_score * z.population for z in sorted_zones if z.percentile_rank <= 40.0
        )
        top_10_acc = sum(
            z.accessibility_score * z.population for z in sorted_zones if z.percentile_rank >= 90.0
        )
        palma = (top_10_acc / max(0.001, bottom_40_acc)) if bottom_40_acc > 0 else 1.0

        # Tier Categorization
        tier_counts = {"Transit Desert": 0, "Underserved": 0, "Adequate": 0, "Mobility Oasis": 0}
        median_acc = sorted_zones[len(sorted_zones) // 2].accessibility_score

        for z in sorted_zones:
            if z.accessibility_score <= 0.0001:
                z.equity_tier = "Transit Desert"
            elif z.accessibility_score < median_acc * 0.5:
                z.equity_tier = "Underserved"
            elif z.accessibility_score < median_acc * 1.5:
                z.equity_tier = "Adequate"
            else:
                z.equity_tier = "Mobility Oasis"
            tier_counts[z.equity_tier] += 1

        return EquityScorecardResult(
            gini_coefficient=gini,
            palma_ratio=palma,
            theil_index=theil,
            mean_accessibility=mean_acc,
            median_accessibility=median_acc,
            lorenz_curve=lorenz_points,
            zones=sorted_zones,
            tier_distribution=tier_counts,
        )
