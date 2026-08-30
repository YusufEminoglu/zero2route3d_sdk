# -*- coding: utf-8 -*-
"""Unit tests for zero2route3d Round 7 features (Powertrain Thermal Soak & Time-Dependent Isochrones)."""

from __future__ import annotations

import unittest

from zero2route3d import (
    DynamicIsochroneResult,
    EngineHeatProfile,
    HourlyCongestionFactor,
    PowertrainThermalResult,
    simulate_powertrain_thermal_load,
    solve_time_dependent_isochrones,
)


class TestZero2Route3DRound7(unittest.TestCase):
    def test_powertrain_thermal_soak(self) -> None:
        # Steep mountain climb: 5 segments of 500m with 40m gain each (8% grade)
        segs = [(500.0, 40.0)] * 5
        eng = EngineHeatProfile(displacement_liters=13.0, radiator_heat_rejection_kw=150.0)

        res = simulate_powertrain_thermal_load(segs, vehicle_gross_weight_tonnes=38.0, engine_profile=eng)

        self.assertIsInstance(res, PowertrainThermalResult)
        self.assertGreater(res.peak_coolant_temp_c, 85.0)
        self.assertEqual(len(res.temperature_profile_c), 5)

        d = res.to_dict()
        self.assertIn("peak_temp_c", d)
        self.assertIn("fan_duration_s", d)

    def test_time_dependent_isochrones(self) -> None:
        origin = (0.0, 0.0)
        # Rush hour vs midnight
        res_am = solve_time_dependent_isochrones(origin, departure_hour=8, cutoff_minutes_intervals=(15.0, 30.0))
        res_night = solve_time_dependent_isochrones(origin, departure_hour=2, cutoff_minutes_intervals=(15.0, 30.0))

        self.assertIsInstance(res_am, DynamicIsochroneResult)
        self.assertIsInstance(res_night, DynamicIsochroneResult)
        self.assertEqual(len(res_am.rings), 2)
        self.assertLess(res_am.congested_effective_speed_kmh, res_night.congested_effective_speed_kmh)
        self.assertLess(res_am.rings[-1].effective_radius_m, res_night.rings[-1].effective_radius_m)

        d = res_am.to_dict()
        self.assertIn("congested_speed_kmh", d)
        self.assertIn("max_reach_m", d)
