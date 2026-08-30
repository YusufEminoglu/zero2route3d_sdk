# -*- coding: utf-8 -*-
"""Unit tests for zero2route3d Round 8 features (Air Ambulance LZ & Hydroplaning Risk)."""

from __future__ import annotations

import unittest

from zero2route3d import (
    HelicopterApproachSlope,
    HydroplaningRiskResult,
    LandingZoneResult,
    PavementCrossSlopeProfile,
    evaluate_helicopter_landing_zones,
    evaluate_road_hydroplaning_risk,
)


class TestZero2Route3DRound8(unittest.TestCase):
    def test_helicopter_landing_zone_evaluator(self) -> None:
        tlof = (0.0, 0.0, 10.0)
        # Clear field with distant obstacle
        obstacles = [(100.0, 0.0, 15.0), (300.0, 0.0, 25.0)]
        cfg = HelicopterApproachSlope(slope_ratio=8.0)

        res = evaluate_helicopter_landing_zones(tlof, obstacles, approach_config=cfg)

        self.assertIsInstance(res, LandingZoneResult)
        self.assertEqual(res.touchdown_point_3d, tlof)
        self.assertGreater(len(res.safe_approach_headings), 0)

        d = res.to_dict()
        self.assertIn("safe_landing", d)
        self.assertIn("tlof_pos", d)
        self.assertIn("safe_headings", d)

    def test_pavement_hydroplaning_risk(self) -> None:
        pave = PavementCrossSlopeProfile(drainage_path_length_m=8.0, cross_slope_pct=2.0, macrotexture_depth_mm=1.2)
        res = evaluate_road_hydroplaning_risk(vehicle_speed_kmh=110.0, rainfall_intensity_mm_hr=60.0, pavement=pave)

        self.assertIsInstance(res, HydroplaningRiskResult)
        self.assertGreater(res.water_film_depth_mm, 0.0)
        self.assertGreater(res.critical_hydroplaning_speed_kmh, 50.0)

        d = res.to_dict()
        self.assertIn("water_film_mm", d)
        self.assertIn("hydroplaning_speed_kmh", d)
        self.assertIn("is_risk", d)
