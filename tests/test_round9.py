# -*- coding: utf-8 -*-
"""Unit tests for zero2route3d Round 9 features (Rail Adhesion Limits & Autonomous Platooning)."""

from __future__ import annotations

import unittest

from zero2route3d import (
    LocomotiveTractionProfile,
    PlatoonAerodynamicConfig,
    PlatoonFuelResult,
    RailAdhesionResult,
    RailSurfaceCondition,
    evaluate_rail_tractive_adhesion,
    simulate_truck_platooning_benefits,
)


class TestZero2Route3DRound9(unittest.TestCase):
    def test_rail_gradient_adhesion_limits(self) -> None:
        loco = LocomotiveTractionProfile(locomotive_weight_tonnes=120.0, maximum_power_kw=6400.0, operating_speed_kmh=60.0)
        res = evaluate_rail_tractive_adhesion(gradient_pct=1.8, locomotive=loco, rail_condition=RailSurfaceCondition.DRY_CLEAN)

        self.assertIsInstance(res, RailAdhesionResult)
        self.assertGreater(res.curtius_kniffler_adhesion_coeff, 0.15)
        self.assertGreater(res.maximum_tractive_effort_kn, 0.0)
        self.assertGreater(res.maximum_negotiable_gradient_pct, 0.0)

        d = res.to_dict()
        self.assertIn("adhesion_mu", d)
        self.assertIn("max_tractive_kn", d)

    def test_autonomous_truck_platooning(self) -> None:
        cfg = PlatoonAerodynamicConfig(platoon_size_trucks=3, inter_vehicle_gap_meters=10.0, trip_distance_km=500.0)
        res = simulate_truck_platooning_benefits(cfg)

        self.assertIsInstance(res, PlatoonFuelResult)
        self.assertGreater(res.lead_truck_fuel_saved_pct, 0.0)
        self.assertGreater(res.trailing_trucks_avg_fuel_saved_pct, res.lead_truck_fuel_saved_pct)
        self.assertGreater(res.total_diesel_saved_liters, 0.0)
        self.assertGreater(res.total_co2_avoided_kg, 0.0)

        d = res.to_dict()
        self.assertIn("overall_saved_pct", d)
        self.assertIn("diesel_saved_liters", d)
