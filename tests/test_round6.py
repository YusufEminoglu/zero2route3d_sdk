# -*- coding: utf-8 -*-
"""Unit tests for zero2route3d Round 6 features (Superload Swept Path & CO2 Eco-Routing)."""

from __future__ import annotations

import unittest

from zero2route3d import (
    EmissionAssessmentResult,
    SuperloadVehicleProfile,
    SweptPathResult,
    VehicleEmissionProfile,
    calculate_route_co2_emissions,
    calculate_swept_path_envelope,
)


class TestZero2Route3DRound6(unittest.TestCase):
    def test_superload_swept_path_envelope(self) -> None:
        # Sharp curve centerline
        road = [(0.0, 0.0), (50.0, 0.0), (80.0, 40.0), (80.0, 100.0)]
        veh = SuperloadVehicleProfile(trailer_wheelbase_m=40.0, overall_width_m=3.5)

        res = calculate_swept_path_envelope(road, road_curb_half_width_m=8.0, vehicle_profile=veh)

        self.assertIsInstance(res, SweptPathResult)
        self.assertGreater(res.max_swept_width_m, 3.5)
        self.assertGreater(res.total_corridor_area_m2, 0.0)
        self.assertGreater(len(res.outer_swept_envelope_polygon), 0)

        d = res.to_dict()
        self.assertIn("max_swept_width_m", d)
        self.assertIn("corridor_area_m2", d)

    def test_co2_emission_routing(self) -> None:
        path = [(0.0, 0.0, 10.0), (500.0, 0.0, 20.0), (1000.0, 0.0, 50.0)]
        prof = VehicleEmissionProfile(curb_weight_kg=1800.0)

        emissions = calculate_route_co2_emissions(path, average_speed_kmh=70.0, vehicle_profile=prof)

        self.assertIsInstance(emissions, EmissionAssessmentResult)
        self.assertGreater(emissions.total_co2_kg, 0.0)
        self.assertGreater(emissions.total_fuel_consumed_liters, 0.0)
        self.assertGreater(emissions.steep_gradient_emission_penalty_kg, 0.0)

        d = emissions.to_dict()
        self.assertIn("total_co2_kg", d)
        self.assertIn("gradient_penalty_kg", d)
