# -*- coding: utf-8 -*-
"""Multi-Truck Autonomous Aerodynamic Platooning Fuel Economy Simulator for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class PlatoonAerodynamicConfig:
    platoon_size_trucks: int = 3
    inter_vehicle_gap_meters: float = 12.0  # Safe CACC gap (~0.4s to 0.6s headway)
    cruising_speed_kmh: float = 85.0
    trip_distance_km: float = 450.0
    baseline_fuel_consumption_l_100km: float = 31.0


@dataclass
class PlatoonFuelResult:
    lead_truck_fuel_saved_pct: float
    trailing_trucks_avg_fuel_saved_pct: float
    overall_platoon_fuel_saved_pct: float
    total_diesel_saved_liters: float
    total_co2_avoided_kg: float
    economic_cost_savings_usd: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "lead_saved_pct": round(self.lead_truck_fuel_saved_pct, 1),
            "trailing_saved_pct": round(self.trailing_trucks_avg_fuel_saved_pct, 1),
            "overall_saved_pct": round(self.overall_platoon_fuel_saved_pct, 1),
            "diesel_saved_liters": round(self.total_diesel_saved_liters, 1),
            "co2_avoided_kg": round(self.total_co2_avoided_kg, 1),
            "cost_savings_usd": round(self.economic_cost_savings_usd, 2),
        }


def simulate_truck_platooning_benefits(
    config: PlatoonAerodynamicConfig | None = None,
    diesel_price_usd_per_liter: float = 1.35,
) -> PlatoonFuelResult:
    """Compute CFD aerodynamic drag reduction coefficients and diesel fuel economy yield in Cooperative ACC platoons.

    Aerodynamic drag reduction delta_Cd vs gap d (meters):
    - Lead truck: receives base pressure wake push -> ~4-7% savings at 10-15m gap
    - Follower trucks: drafting slipstream -> ~10-18% savings at 10-15m gap
    """
    cfg = config or PlatoonAerodynamicConfig()
    n = max(2, cfg.platoon_size_trucks)
    gap = max(4.0, cfg.inter_vehicle_gap_meters)

    # Empirical CFD regression for aerodynamic saving as function of gap:
    # delta_Cd_lead ~= 0.08 * exp(-0.04 * gap)
    lead_savings_pct = max(2.0, min(10.0, 9.5 * math.exp(-0.035 * gap)))

    # delta_Cd_follower ~= 0.22 * exp(-0.045 * gap)
    trailing_savings_pct = max(5.0, min(22.0, 20.0 * math.exp(-0.040 * gap)))

    # Weighted overall platoon savings
    total_savings_pct = (lead_savings_pct + (n - 1) * trailing_savings_pct) / float(n)

    # Fuel calculations
    baseline_liters_per_truck = (cfg.trip_distance_km / 100.0) * cfg.baseline_fuel_consumption_l_100km
    total_baseline_liters = baseline_liters_per_truck * n

    liters_saved = total_baseline_liters * (total_savings_pct / 100.0)
    co2_kg = liters_saved * 2.68  # 2.68 kg CO2 per liter diesel
    cost_saved = liters_saved * diesel_price_usd_per_liter

    return PlatoonFuelResult(
        lead_truck_fuel_saved_pct=lead_savings_pct,
        trailing_trucks_avg_fuel_saved_pct=trailing_savings_pct,
        overall_platoon_fuel_saved_pct=total_savings_pct,
        total_diesel_saved_liters=liters_saved,
        total_co2_avoided_kg=co2_kg,
        economic_cost_savings_usd=cost_saved,
    )
