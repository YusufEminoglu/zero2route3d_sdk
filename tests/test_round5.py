# -*- coding: utf-8 -*-
"""Unit tests for zero2route3d Round 5 features (3D Drone Corridor & Brake Fade Safety)."""

from __future__ import annotations

import unittest

from zero2route3d import (
    AirCorridorResult,
    BrakeThermalProfile,
    DescentSafetyResult,
    DroneAirspaceProfile,
    evaluate_steep_descent_brake_fade,
    solve_3d_drone_flight_corridor,
)


class TestZero2Route3DRound5(unittest.TestCase):
    def test_drone_airspace_flight_corridor(self) -> None:
        p_start = (0.0, 0.0, 10.0)
        p_end = (1000.0, 0.0, 15.0)
        obstacles = [
            {"bbox": (400.0, -50.0, 600.0, 50.0), "height": 45.0}
        ]

        corridor = solve_3d_drone_flight_corridor(p_start, p_end, obstacles)
        self.assertIsInstance(corridor, AirCorridorResult)
        self.assertTrue(corridor.is_flight_feasible)
        self.assertGreater(corridor.total_flight_distance_m, 1000.0)
        self.assertEqual(len(corridor.flight_waypoints_3d), 4)
        self.assertGreater(corridor.min_obstacle_clearance_m, 0.0)

        d = corridor.to_dict()
        self.assertIn("flight_time_min", d)
        self.assertIn("battery_pct", d)

    def test_steep_descent_brake_fade_safety(self) -> None:
        # 1000m descent with 250m elevation drop (~25% steep mountain grade)
        res_heavy = evaluate_steep_descent_brake_fade(
            descent_distance_m=1000.0,
            elevation_drop_m=250.0,
            descent_speed_kmh=60.0,
            vehicle_profile=BrakeThermalProfile(vehicle_mass_kg=30000.0),
        )

        self.assertIsInstance(res_heavy, DescentSafetyResult)
        self.assertGreater(res_heavy.peak_brake_temperature_c, 80.0)
        self.assertGreater(res_heavy.total_potential_energy_mj, 0.0)
        self.assertIn(res_heavy.brake_fade_risk_level, ("LOW", "MODERATE", "CRITICAL_RUNAWAY"))

        d = res_heavy.to_dict()
        self.assertIn("peak_brake_temp_c", d)
        self.assertIn("recommended_speed_kmh", d)
