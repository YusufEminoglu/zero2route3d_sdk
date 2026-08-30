# -*- coding: utf-8 -*-
"""Unit tests for EV 3D energy simulation and GTFS transit routing in zero2route3d."""

from __future__ import annotations

import unittest

from zero2route3d import (
    EVBatteryProfile,
    EVEnergySimulator,
    EVRouteEnergyResult,
    GTFSFeedReader,
    TimetableTransitRouter,
    TransitJourneyResult,
    solve_ev_energy_route,
)


class TestEVEnergyAndGTFS(unittest.TestCase):
    def test_ev_energy_simulation_uphill_and_downhill(self) -> None:
        # Route with uphill climb then steep downhill descent
        waypoints_3d = [
            (0.0, 0.0, 100.0),
            (5000.0, 0.0, 600.0),    # 5 km climb +500m
            (10000.0, 0.0, 100.0),   # 5 km descent -500m (regen braking)
            (15000.0, 0.0, 100.0),   # 5 km flat
        ]

        prof = EVBatteryProfile(
            battery_capacity_kwh=75.0,
            initial_soc_percent=80.0,
            vehicle_mass_kg=2000.0,
            regenerative_efficiency=0.80,
        )
        sim = EVEnergySimulator(prof)
        res = sim.simulate_route(waypoints_3d, target_speeds_kmh=60.0)

        self.assertIsInstance(res, EVRouteEnergyResult)
        self.assertAlmostEqual(res.total_distance_km, 15.0, delta=0.2)
        self.assertGreater(res.total_consumed_kwh, 0.0)
        self.assertGreater(res.total_regenerated_kwh, 0.0)
        self.assertFalse(res.is_depleted)

        # Downhill segment (index 1) should show regeneration
        self.assertTrue(res.segments[1].is_regenerating)
        self.assertLess(res.segments[1].net_battery_energy_kwh, 0.0)

        d = res.to_dict()
        self.assertIn("efficiency_wh_per_km", d)
        self.assertIn("total_regenerated_kwh", d)

    def test_solve_ev_energy_convenience_helper(self) -> None:
        pts = [(0.0, 0.0, 10.0), (1000.0, 0.0, 15.0), (2000.0, 0.0, 10.0)]
        res_sedan = solve_ev_energy_route(pts, vehicle_type="sedan", initial_soc_percent=95.0)
        self.assertEqual(res_sedan.initial_soc_percent, 95.0)
        self.assertGreater(res_sedan.final_soc_percent, 0.0)

    def test_gtfs_timetable_transit_routing(self) -> None:
        feed = GTFSFeedReader()
        feed.add_stop("S1", "Kadıköy Ferry Pier", lat=40.991, lon=29.023)
        feed.add_stop("S2", "Beşiktaş Ferry Pier", lat=41.042, lon=29.006)
        feed.add_stop("S3", "Kabataş Tramway", lat=41.035, lon=28.993)

        feed.add_route("R1", "F1", "Kadıköy - Beşiktaş Ferry", route_type=4)
        feed.add_trip_stop("T1", "S1", "08:15:00", "08:20:00", seq=1)
        feed.add_trip_stop("T1", "S2", "08:45:00", "08:45:00", seq=2)

        router = TimetableTransitRouter(feed, walking_speed_kmh=4.5)

        # Query from origin near Kadıköy to destination near Beşiktaş
        origin = (40.992, 29.024)
        dest = (41.043, 29.007)

        journey = router.route_timetable(
            origin_lat_lon=origin,
            destination_lat_lon=dest,
            departure_time_str="08:10:00",
            max_access_walk_meters=1500.0,
        )

        self.assertIsInstance(journey, TransitJourneyResult)
        self.assertGreater(len(journey.legs), 1)

        d = journey.to_dict()
        self.assertIn("total_transit_time_min", d)
        self.assertEqual(len(d["legs"]), len(journey.legs))
