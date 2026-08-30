# -*- coding: utf-8 -*-
"""Unit tests for zero2route3d Rounds 2 and 3 features."""

from __future__ import annotations

import unittest

from zero2route3d import (
    BiomechanicalKinematicsTracker,
    BiomechanicalTrailSummary,
    MicroMobilityRouteScore,
    TurnByTurn3DRouteGuide,
    WeatherRouteSummary,
    compute_apparent_wind_resistance,
    evaluate_micro_mobility_comfort,
    generate_3d_turn_by_turn_cues,
)


class TestZero2Route3DRounds2And3(unittest.TestCase):
    def test_micromobility_comfort_and_vibrations(self) -> None:
        segs = [200.0, 500.0, 300.0]
        surfaces = ["asphalt_smooth", "cobblestone", "paved_tiles"]
        score = evaluate_micro_mobility_comfort(segs, surfaces, speeds_kmh=20.0, wheel_diameter_inches=8.5)

        self.assertIsInstance(score, MicroMobilityRouteScore)
        self.assertEqual(score.total_distance_km, 1.0)
        self.assertGreater(score.mean_vibration_rms, 0.0)
        self.assertGreater(len(score.segments), 0)

        d = score.to_dict()
        self.assertIn("overall_bikeability_score", d)

    def test_dynamic_weather_wind_routing(self) -> None:
        waypoints = [(0.0, 0.0), (1000.0, 0.0), (2000.0, 0.0)]
        weather = compute_apparent_wind_resistance(
            waypoints,
            vehicle_speed_kmh=30.0,
            wind_speed_ms=10.0,
            wind_direction_degrees=90.0,  # East headwind
            is_raining=True,
        )

        self.assertIsInstance(weather, WeatherRouteSummary)
        self.assertAlmostEqual(weather.total_distance_km, 2.0, delta=0.1)
        self.assertGreater(weather.total_wind_energy_penalty_kwh, 0.0)
        self.assertEqual(weather.segments[0].rain_braking_distance_factor, 1.45)

    def test_biomechanics_trail_tracker(self) -> None:
        pts_3d = [(0.0, 0.0, 100.0), (1000.0, 0.0, 250.0), (2000.0, 0.0, 200.0)]
        tracker = BiomechanicalKinematicsTracker(athlete_mass_kg=75.0)
        trail = tracker.analyze_trail(pts_3d, base_speed_kmh=6.0)

        self.assertIsInstance(trail, BiomechanicalTrailSummary)
        self.assertAlmostEqual(trail.total_distance_km, 2.0, delta=0.1)
        self.assertGreater(trail.total_calories_burned_kcal, 0.0)
        self.assertGreater(trail.mean_heart_rate_bpm, 55)

        d = trail.to_dict()
        self.assertIn("total_calories_kcal", d)

    def test_voice_guidance_3d_turn_cues(self) -> None:
        pts = [
            (0.0, 0.0, 10.0),
            (100.0, 0.0, 10.0),
            (100.0, 100.0, 25.0),  # Right turn + climb
            (200.0, 100.0, 10.0),
        ]
        guide = generate_3d_turn_by_turn_cues(pts)

        self.assertIsInstance(guide, TurnByTurn3DRouteGuide)
        self.assertGreater(guide.total_steps, 2)
        self.assertEqual(guide.instructions[0].maneuver_type, "DEPART")
        self.assertEqual(guide.instructions[-1].maneuver_type, "ARRIVE")

        d = guide.to_dict()
        self.assertIn("total_steps", d)
