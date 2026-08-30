# -*- coding: utf-8 -*-
"""Unit tests for zero2route3d Round 11 features (Ski Piste Classifier & Hydrofoil Marine Router)."""

from __future__ import annotations

import unittest

from zero2route3d import (
    HydrofoilRouteResult,
    HydrofoilVesselProfile,
    PisteDifficultyProfile,
    SkiPisteRouteResult,
    classify_ski_pistes_and_route,
    simulate_hydrofoil_marine_route,
)


class TestZero2Route3dRound11(unittest.TestCase):
    def test_ski_piste_gradient_routing(self) -> None:
        pts = [
            (0.0, 0.0, 2500.0),
            (100.0, 100.0, 2450.0),
            (200.0, 250.0, 2380.0),
            (350.0, 400.0, 2250.0),
        ]
        prof = PisteDifficultyProfile(blue_intermediate_max_slope_pct=25.0)

        res = classify_ski_pistes_and_route(pts, profile=prof)

        self.assertIsInstance(res, SkiPisteRouteResult)
        self.assertGreater(res.total_descent_distance_m, 300.0)
        self.assertEqual(res.vertical_drop_m, 250.0)
        self.assertIn(res.overall_piste_classification, ["GREEN", "BLUE", "RED", "BLACK"])
        self.assertFalse(res.has_uphill_traverses)

        d = res.to_dict()
        self.assertIn("descent_dist_m", d)
        self.assertIn("difficulty", d)

    def test_hydrofoil_marine_routing(self) -> None:
        route = [
            (41.00, 28.98, 12.0),
            (41.05, 29.02, 25.0),
            (41.10, 29.06, 18.0),
        ]
        vessel = HydrofoilVesselProfile(displacement_tonnes=50.0, cruise_speed_knots=40.0)

        res = simulate_hydrofoil_marine_route(route, vessel=vessel)

        self.assertIsInstance(res, HydrofoilRouteResult)
        self.assertGreater(res.total_voyage_nautical_miles, 5.0)
        self.assertGreater(res.estimated_travel_time_hours, 0.0)
        self.assertGreater(res.foilborne_distance_pct, 50.0)
        self.assertGreater(res.minimum_under_keel_clearance_m, 5.0)

        d = res.to_dict()
        self.assertIn("voyage_nm", d)
        self.assertIn("foilborne_pct", d)
        self.assertIn("fuel_liters", d)
