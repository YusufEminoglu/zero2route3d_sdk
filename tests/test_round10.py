# -*- coding: utf-8 -*-
"""Unit tests for zero2route3d Round 10 features (Tunnel Smoke Safety & Hyperloop Aerodynamics)."""

from __future__ import annotations

import unittest

from zero2route3d import (
    HyperloopAeroResult,
    JetFanVentilationProfile,
    TubeBlockageConfig,
    TunnelSmokeSafetyResult,
    simulate_hyperloop_pod_aerodynamics,
    simulate_tunnel_smoke_dispersion,
)


class TestZero2Route3DRound10(unittest.TestCase):
    def test_tunnel_ventilation_smoke_dispersion(self) -> None:
        prof = JetFanVentilationProfile(tunnel_cross_section_area_m2=60.0, fire_heat_release_rate_mw=25.0)
        res = simulate_tunnel_smoke_dispersion(tunnel_length_m=1500.0, ventilation=prof)

        self.assertIsInstance(res, TunnelSmokeSafetyResult)
        self.assertGreater(res.critical_velocity_to_prevent_backlayering_mps, 1.5)
        self.assertGreater(res.actual_longitudinal_air_velocity_mps, 2.0)
        self.assertTrue(res.is_backlayering_prevented)
        self.assertGreater(res.required_jet_fans_count, 0)

        d = res.to_dict()
        self.assertIn("v_crit_mps", d)
        self.assertIn("jet_fans_needed", d)

    def test_hyperloop_evacuated_tube_aerodynamics(self) -> None:
        cfg = TubeBlockageConfig(tube_internal_diameter_m=4.0, pod_frontal_area_m2=3.5, pod_cruising_speed_kmh=800.0)
        res = simulate_hyperloop_pod_aerodynamics(cfg)

        self.assertIsInstance(res, HyperloopAeroResult)
        self.assertGreater(res.kantrowitz_limit_mach_number, 0.0)
        self.assertGreater(res.actual_flight_mach_number, 0.5)
        self.assertGreater(res.aerodynamic_drag_force_n, 0.0)
        self.assertGreater(res.traction_power_required_kw, 0.0)

        d = res.to_dict()
        self.assertIn("kantrowitz_mach", d)
        self.assertIn("drag_force_n", d)
