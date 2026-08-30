# -*- coding: utf-8 -*-
"""Unit tests for zero2route3d Round 4 features (Hazard Evacuation & Truck Clearance)."""

from __future__ import annotations

import unittest

from zero2route3d import (
    BridgeClearanceObstacle,
    DynamicHazardZone,
    EvacuationRouteResult,
    TruckRestrictionProfile,
    TruckRouteFeasibilityResult,
    solve_3d_evacuation_routes,
    solve_heavy_vehicle_route3d,
)


class TestZero2Route3DRound4(unittest.TestCase):
    def test_dynamic_hazard_evacuation(self) -> None:
        origins = [
            {"id": "Neighborhood_A", "population": 120, "coords": (100.0, 100.0, 10.0)},
            {"id": "Neighborhood_B", "population": 80, "coords": (300.0, 100.0, 15.0)},
        ]
        musters = [
            {"id": "Safe_Shelter_1", "coords": (0.0, 500.0, 30.0), "capacity": 500},
            {"id": "Safe_Shelter_2", "coords": (500.0, 500.0, 25.0), "capacity": 500},
        ]
        hazards = [
            DynamicHazardZone(
                hazard_id="Flood_Surge",
                origin_point=(200.0, 250.0, 5.0),
                expansion_speed_ms=1.5,
                current_radius_m=80.0,
            )
        ]

        result = solve_3d_evacuation_routes(origins, musters, hazards)
        self.assertIsInstance(result, EvacuationRouteResult)
        self.assertEqual(result.total_population_evacuated, 200)
        self.assertEqual(len(result.routes), 2)
        self.assertGreater(result.mean_evacuation_time_min, 0.0)

        d = result.to_dict()
        self.assertIn("total_evacuees", d)

    def test_heavy_vehicle_truck_clearance(self) -> None:
        route_pts = [
            (0.0, 0.0, 10.0),
            (500.0, 0.0, 10.0),   # Pass near obstacle
            (1000.0, 0.0, 30.0),  # Hill section
        ]
        obstacles = [
            BridgeClearanceObstacle(
                obstacle_id="Bridge_Overpass_1",
                position=(510.0, 5.0, 10.0),
                max_underpass_height_m=3.80,  # 3.8m limit
                max_weight_limit_tons=45.0,
            )
        ]

        # Truck height 4.2m should fail height restriction
        profile = TruckRestrictionProfile(vehicle_height_m=4.20, gross_vehicle_weight_tons=38.0)
        eval_res = solve_heavy_vehicle_route3d(route_pts, obstacles, truck_profile=profile)

        self.assertIsInstance(eval_res, TruckRouteFeasibilityResult)
        self.assertFalse(eval_res.is_route_feasible)
        self.assertEqual(eval_res.height_violations_count, 1)

        # Smaller delivery van (3.2m height) should pass
        van_profile = TruckRestrictionProfile(vehicle_height_m=3.20, gross_vehicle_weight_tons=12.0)
        van_res = solve_heavy_vehicle_route3d(route_pts, obstacles, truck_profile=van_profile)
        self.assertTrue(van_res.is_route_feasible)
        self.assertEqual(van_res.height_violations_count, 0)
