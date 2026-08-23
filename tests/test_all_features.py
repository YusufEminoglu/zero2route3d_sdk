"""Comprehensive test suite for zero2route3d SDK."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from zero2route3d import (
    AccessibilityEquityEngine,
    AHPEngine,
    CopernicusDemTileSource,
    EnvironmentalSurfaceSampler,
    EvacuationRouter,
    GPXPoint,
    HMMMapMatcher3D,
    IsochroneEngine3D,
    MultiModalRouter,
    OsmBuilding,
    ParetoMultiObjectiveRouter,
    RoutingEngine3D,
    StandaloneHtmlBundler,
    SupplyFacility,
    Waypoint,
    ZoneAccessibilityRecord,
    aerodynamic_drag_power,
    calculate_solar_position,
    compute_shade_exposure_along_route,
    densify_3d_linestring,
    export_route_to_dxf_3d,
    filter_buildings_in_corridor,
    generate_cue_sheet,
    get_profile,
    haversine_distance_2d,
    haversine_distance_3d,
    list_profile_keys,
    minetti_energy_cost,
    rolling_resistance_force,
    senior_fatigue_decay,
    smooth_elevation_series,
    solve_tsp_order,
    tobler_walking_speed,
    universal_thermal_comfort_utci,
)
from zero2route3d.dem_fetcher import GlobalDemFetcher
from zero2route3d.kinematics import AnimatedAvatar
from zero2route3d.micro_elevation import BicubicSurfaceInterpolator, IDWSurfaceInterpolator
from zero2route3d.network_source import RoadSegment


def fixture_network_segments() -> list[RoadSegment]:
    coordinates = [
        (27.1000, 38.4000, 5.0),
        (27.1000, 38.4100, 6.0),
        (27.1100, 38.4100, 8.0),
        (27.1100, 38.4200, 10.0),
        (27.1200, 38.4200, 12.0),
        (27.1200, 38.4300, 13.0),
        (27.1300, 38.4300, 14.0),
        (27.1300, 38.4400, 16.0),
        (27.1400, 38.4400, 18.0),
        (27.1400, 38.4500, 19.0),
        (27.1500, 38.4500, 20.0),
    ]
    return [
        RoadSegment(p1=a, p2=b, length_m=haversine_distance_2d(a, b), highway_type="residential")
        for a, b in zip(coordinates, coordinates[1:])
    ]


class TestZero2Route3DSDK(unittest.TestCase):
    def test_haversine_2d_and_3d(self) -> None:
        p1 = (27.1428, 38.4237, 10.0)
        p2 = (27.1438, 38.4237, 25.0)
        d2 = haversine_distance_2d(p1, p2)
        d3 = haversine_distance_3d(p1, p2)
        self.assertGreater(d2, 70.0)
        self.assertGreater(d3, d2)
        self.assertAlmostEqual(d3, (d2**2 + 15.0**2) ** 0.5, places=1)

    def test_tobler_and_kinematics(self) -> None:
        flat_spd = tobler_walking_speed(0.0, base_speed_kmh=5.0)
        uphill_spd = tobler_walking_speed(0.15, base_speed_kmh=5.0)
        downhill_spd = tobler_walking_speed(-0.05, base_speed_kmh=5.0)
        self.assertGreater(flat_spd, uphill_spd)
        self.assertGreater(downhill_spd, uphill_spd)

    def test_minetti_energy(self) -> None:
        _j_flat, kcal_flat = minetti_energy_cost(0.0, mass_kg=70.0, distance_m=1000.0)
        _j_up, kcal_up = minetti_energy_cost(0.10, mass_kg=70.0, distance_m=1000.0)
        self.assertGreater(kcal_up, kcal_flat)
        self.assertGreater(kcal_flat, 10.0)

    def test_aerodynamic_and_rolling_resistance(self) -> None:
        drag = aerodynamic_drag_power(velocity_kmh=25.0)
        self.assertGreater(drag, 10.0)
        f_roll = rolling_resistance_force(mass_kg=85.0, slope_fraction=0.05, surface_type="asphalt")
        self.assertGreater(f_roll, 2.0)

    def test_senior_fatigue_and_utci(self) -> None:
        fatigue = senior_fatigue_decay(distance_m=4000.0, accumulated_climb_m=150.0)
        self.assertLess(fatigue, 0.9)
        self.assertGreater(fatigue, 0.4)

        stress_score = universal_thermal_comfort_utci(temp_c=34.0, mean_radiant_temp_c=45.0)
        self.assertGreater(stress_score, 0.5)

    def test_ahp_pairwise_matrix(self) -> None:
        engine = AHPEngine(["slope", "heat", "green"])
        engine.set_pairwise_comparison("slope", "heat", 3.0)
        engine.set_pairwise_comparison("slope", "green", 2.0)
        engine.set_pairwise_comparison("heat", "green", 0.5)
        res = engine.calculate()
        self.assertTrue(res.is_consistent)
        self.assertLess(res.consistency_ratio, 0.10)
        self.assertGreater(res.weights["slope"], res.weights["heat"])

    def test_tsp_solver(self) -> None:
        pts = [
            (27.0, 38.0, 0.0),
            (27.5, 38.0, 0.0),
            (27.2, 38.0, 0.0),
            (27.9, 38.0, 0.0),
        ]
        order = solve_tsp_order(pts, fix_start=True, fix_end=True)
        self.assertEqual(order[0], 0)
        self.assertEqual(order[-1], 3)
        self.assertEqual(order[1], 2)
        self.assertEqual(order[2], 1)

    def test_profiles_catalog(self) -> None:
        keys = list_profile_keys()
        self.assertIn("adult", keys)
        self.assertIn("wheelchair", keys)
        self.assertIn("stroller", keys)
        self.assertIn("truck", keys)
        self.assertIn("paramedic", keys)

        wheelchair = get_profile("wheelchair")
        self.assertFalse(wheelchair.stair_allowed)
        self.assertLessEqual(wheelchair.max_slope_pct, 6.0)

    def test_densification_and_smoothing(self) -> None:
        coords = [(27.0, 38.0, 10.0), (27.01, 38.0, 20.0)]
        densified = densify_3d_linestring(coords, sample_interval_m=10.0)
        self.assertGreater(len(densified), 20)

        elevs = [10.0, 12.0, 50.0, 14.0, 15.0]
        smoothed = smooth_elevation_series(elevs, window_size=3)
        self.assertLess(smoothed[2], 50.0)

    def test_cue_sheet_generation(self) -> None:
        coords = [
            (27.000, 38.000, 10.0),
            (27.005, 38.000, 12.0),
            (27.005, 38.005, 14.0),
            (27.010, 38.005, 15.0),
        ]
        cues = generate_cue_sheet(coords, get_profile("adult"))
        self.assertGreaterEqual(len(cues), 2)
        self.assertEqual(cues[0].direction, "depart")
        self.assertEqual(cues[-1].direction, "arrive")

    def test_routing_graph_and_od_matrix(self) -> None:
        segments = fixture_network_segments()
        engine = RoutingEngine3D()
        engine.build_graph(segments)

        w1 = Waypoint(lon=27.11, lat=38.41, name="Orig1")
        w2 = Waypoint(lon=27.14, lat=38.44, name="Dest1")
        res = engine.calculate_route([w1, w2], profile_key="adult")

        self.assertTrue(res.is_network_matched)
        self.assertGreater(len(res.coordinates_3d), 2)
        self.assertGreater(res.statistics.total_distance_m, 100.0)

        matrix = engine.calculate_od_matrix([w1], [w2], profile_key="adult")
        self.assertEqual(len(matrix), 1)
        self.assertGreater(matrix[0]["distance_m"], 100.0)

    def test_multimodal_router(self) -> None:
        segments = fixture_network_segments()
        engine = RoutingEngine3D()
        engine.build_graph(segments)

        router = MultiModalRouter(engine)
        w_orig = Waypoint(lon=27.11, lat=38.41, name="Home")
        w_dest = Waypoint(lon=27.14, lat=38.44, name="Office")
        hubs = [
            Waypoint(lon=27.12, lat=38.42, name="Station 1"),
            Waypoint(lon=27.13, lat=38.43, name="Station 2"),
        ]

        journey = router.calculate_multimodal_trip(
            w_orig, w_dest, hubs, access_mode="adult", main_mode="bicycle", egress_mode="adult"
        )
        self.assertEqual(len(journey.legs), 3)
        self.assertGreater(journey.total_distance_km, 0.5)
        self.assertGreater(journey.transfer_count, 1)

    def test_isochrone_engine(self) -> None:
        segments = fixture_network_segments()
        engine = RoutingEngine3D()
        engine.build_graph(segments)

        iso_engine = IsochroneEngine3D(engine)
        origin = Waypoint(lon=27.12, lat=38.42, name="Center")
        iso_res = iso_engine.compute_isochrones(
            origin, profile_key="adult", time_intervals_min=(5.0, 10.0, 15.0)
        )
        self.assertEqual(len(iso_res.bands), 3)
        self.assertGreater(iso_res.total_reachable_nodes, 0)

    def test_micro_elevation_and_bicubic(self) -> None:
        bicubic = BicubicSurfaceInterpolator()
        patch_4x4 = [
            [10.0, 12.0, 14.0, 16.0],
            [12.0, 15.0, 18.0, 20.0],
            [14.0, 18.0, 22.0, 25.0],
            [16.0, 20.0, 25.0, 30.0],
        ]
        grad = bicubic.interpolate_patch_4x4(patch_4x4, 0.5, 0.5, 10.0, 10.0)
        self.assertGreater(grad.elevation_m, 15.0)
        self.assertGreater(grad.slope_pct, 0.0)

        idw = IDWSurfaceInterpolator()
        pts = [(0.0, 0.0, 10.0), (10.0, 0.0, 20.0), (0.0, 10.0, 30.0)]
        z_mid = idw.interpolate_point(5.0, 5.0, pts)
        self.assertGreater(z_mid, 12.0)
        self.assertLess(z_mid, 28.0)

    def test_pareto_multi_objective_router(self) -> None:
        segments = fixture_network_segments()
        engine = RoutingEngine3D()
        engine.build_graph(segments)

        sampler = EnvironmentalSurfaceSampler()
        pareto_router = ParetoMultiObjectiveRouter(engine.nodes, engine.adj, sampler)
        node_keys = list(engine.nodes.keys())
        res = pareto_router.solve_pareto_frontier(node_keys[0], node_keys[-1], profile_key="adult")
        self.assertGreaterEqual(res.to_dict()["solution_count"], 1)

    def test_accessibility_equity_scorecard(self) -> None:
        zones = [
            ZoneAccessibilityRecord("Z1", "Downtown", 27.12, 38.42, 5000),
            ZoneAccessibilityRecord("Z2", "Suburbs", 27.18, 38.48, 8000),
            ZoneAccessibilityRecord("Z3", "Periphery", 27.25, 38.55, 3000),
        ]
        facilities = [
            SupplyFacility("F1", "Central Metro", 27.125, 38.425, 100),
            SupplyFacility("F2", "District Hospital", 27.130, 38.430, 50),
        ]
        equity_engine = AccessibilityEquityEngine(catchment_radius_m=3000.0)
        eq_res = equity_engine.compute_e2sfca(zones, facilities)
        self.assertGreaterEqual(eq_res.gini_coefficient, 0.0)
        self.assertLessEqual(eq_res.gini_coefficient, 1.0)
        self.assertGreater(len(eq_res.lorenz_curve), 2)

    def test_map_matching_3d(self) -> None:
        segments = fixture_network_segments()
        engine = RoutingEngine3D()
        engine.build_graph(segments)

        matcher = HMMMapMatcher3D(engine.nodes, engine.adj)
        gpx_pts = [
            GPXPoint(lon=27.1105, lat=38.4102, elevation_raw_m=10.0),
            GPXPoint(lon=27.1208, lat=38.4205, elevation_raw_m=15.0),
            GPXPoint(lon=27.1302, lat=38.4309, elevation_raw_m=20.0),
        ]
        match_res = matcher.match_gps_track(gpx_pts)
        self.assertGreaterEqual(len(match_res.matched_points), 2)
        gpx_xml = match_res.to_gpx()
        self.assertIn("<trkpt", gpx_xml)

    def test_corridor_building_filter(self) -> None:
        route_coords = [
            (27.1400, 38.4200, 10.0),
            (27.1450, 38.4250, 15.0),
            (27.1500, 38.4300, 20.0),
        ]
        blds = [
            OsmBuilding(
                "b1",
                [(27.1402, 38.4201), (27.1404, 38.4201), (27.1404, 38.4203)],
                height_m=16.0,
                levels=5,
            ),
            OsmBuilding(
                "b2_far",
                [(27.2000, 38.5000), (27.2010, 38.5000), (27.2010, 38.5010)],
                height_m=12.0,
                levels=4,
            ),
        ]
        corridor = filter_buildings_in_corridor(route_coords, blds, buffer_meters=50.0)
        self.assertEqual(len(corridor), 1)
        self.assertEqual(corridor[0]["id"], "b1")
        self.assertEqual(corridor[0]["height_m"], 16.0)

    def test_animated_avatar_interpolation(self) -> None:
        avatar = AnimatedAvatar(
            profile_key="car",
            profile_name="Passenger Car",
            color_hex="#ef4444",
            coordinates_3d=[(27.0, 38.0, 10.0), (27.1, 38.0, 10.0), (27.2, 38.0, 10.0)],
            cumulative_distances_m=[0.0, 8000.0, 16000.0],
            timestamps_s=[0.0, 100.0, 200.0],
            total_duration_s=200.0,
            total_distance_m=16000.0,
        )

        p_start = avatar.interpolate_position(0.0)
        self.assertAlmostEqual(p_start[0], 27.0)

        p_mid = avatar.interpolate_position(50.0)
        self.assertAlmostEqual(p_mid[0], 27.05, places=2)

        p_end = avatar.interpolate_position(250.0)
        self.assertAlmostEqual(p_end[0], 27.2)

    def test_global_dem_fetcher(self) -> None:
        pts = [(27.1428, 38.4237), (27.1500, 38.4300)]
        elevations = GlobalDemFetcher.fetch_elevations_for_coords(pts)
        self.assertEqual(len(elevations), 2)
        self.assertGreaterEqual(elevations[0], 0.0)

        single = GlobalDemFetcher.get_elevation_single(27.1428, 38.4237)
        self.assertGreaterEqual(single, 0.0)

    def test_dxf_export_edge_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dxf = Path(tmpdir) / "empty_route.dxf"
            export_route_to_dxf_3d([], out_dxf)
            self.assertTrue(out_dxf.exists())

            out_dxf2 = Path(tmpdir) / "single_route.dxf"
            export_route_to_dxf_3d([(27.1, 38.4, 15.0)], out_dxf2)
            self.assertTrue(out_dxf2.exists())

    def test_html_standalone_bundler(self) -> None:
        bundler = StandaloneHtmlBundler()
        geojson_mock = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [27.1428, 38.4237, 10.0],
                    [27.1450, 38.4250, 20.0],
                ],
            },
            "properties": {
                "distance_km": 0.35,
                "duration_min": 4.5,
                "elevation_gain_m": 10.0,
                "profile_name": "Standard Adult",
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            out_html = Path(tmpdir) / "standalone_studio.html"
            bundler.bundle_to_file(geojson_mock, out_html)
            self.assertTrue(out_html.exists())
            content = out_html.read_text(encoding="utf-8")
            self.assertIn("02Route 3D Studio", content)
            self.assertIn("27.1428", content)

    def test_solar_shadow_and_exposure_calculator(self) -> None:
        sun_morning = calculate_solar_position(38.4, solar_hour=8.0)
        sun_noon = calculate_solar_position(38.4, solar_hour=12.0)
        sun_evening = calculate_solar_position(38.4, solar_hour=19.0)

        self.assertGreater(sun_noon.elevation_deg, sun_morning.elevation_deg)
        self.assertGreater(sun_noon.elevation_deg, sun_evening.elevation_deg)
        self.assertGreater(sun_noon.direct_irradiance_w_m2, sun_morning.direct_irradiance_w_m2)

        coords_3d = [(27.14, 38.42, 10.0), (27.145, 38.425, 12.0), (27.15, 38.43, 15.0)]
        shade_rep = compute_shade_exposure_along_route(
            coords_3d, solar_hour=13.0, building_density_factor=0.8
        )
        self.assertTrue(0.0 <= shade_rep.direct_sun_pct <= 100.0)
        self.assertTrue(0.0 <= shade_rep.shaded_pct <= 100.0)

    def test_evacuation_multi_destination_routing(self) -> None:
        segments = fixture_network_segments()
        engine = RoutingEngine3D()
        engine.build_graph(segments)

        router = EvacuationRouter(engine)
        origin = Waypoint(lon=27.11, lat=38.41, name="Evacuee Home")
        shelters = [
            Waypoint(lon=27.13, lat=38.43, name="Shelter East"),
            Waypoint(lon=27.15, lat=38.45, name="Shelter North"),
        ]

        evac_res = router.calculate_evacuation_route(origin, shelters, profile_key="adult")
        self.assertGreater(len(evac_res.route_result.coordinates_3d), 2)
        self.assertIn(evac_res.muster_point.name, ("Shelter East", "Shelter North"))
        self.assertGreater(evac_res.egress_time_min, 0.0)

    def test_copernicus_dem_tile_source(self) -> None:
        tile = CopernicusDemTileSource.tile_id(27.14, 38.42)
        self.assertEqual(tile, "N38_00_E027_00")
        url = CopernicusDemTileSource.tile_url(27.14, 38.42)
        self.assertIn("copernicus-dem-30m.s3.amazonaws.com", url)
        self.assertIn("N38_00_E027_00", url)

        tiles = CopernicusDemTileSource.tiles_for_bbox([27.0, 38.0, 27.8, 38.8])
        self.assertEqual(len(tiles), 1)

    def test_high_level_api_solve_route_and_isochrones(self) -> None:
        from zero2route3d import solve_3d_isochrones, solve_3d_route

        segments = fixture_network_segments()

        route = solve_3d_route((27.11, 38.41), (27.14, 38.44), network=segments, profile="adult")
        self.assertTrue(route.is_network_matched)
        self.assertGreater(route.statistics.total_distance_m, 100.0)

        iso = solve_3d_isochrones(
            (27.12, 38.42), network=segments, profile="adult", time_intervals_min=[5, 10]
        )
        self.assertEqual(len(iso.bands), 2)

    def test_cli_execution(self) -> None:
        import io
        import sys

        from zero2route3d.cli import main

        saved_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            exit_code = main(["profiles"])
            out = sys.stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Mobility Profiles Catalog", out)
            self.assertIn("wheelchair", out)
        finally:
            sys.stdout = saved_stdout

    def test_geopandas_and_networkx_integrations(self) -> None:
        from zero2route3d.integrations import (
            from_geodataframe,
            to_geodataframe,
            to_networkx_digraph,
        )

        segments = fixture_network_segments()

        # NetworkX conversion
        nx_graph = to_networkx_digraph(segments)
        self.assertGreater(len(nx_graph.nodes), 5)
        self.assertGreater(len(nx_graph.edges), 5)

        # GeoDataFrame conversion
        gdf = to_geodataframe(segments)
        self.assertEqual(len(gdf), len(segments))
        self.assertIn("highway_type", gdf.columns)

        # Re-import from GeoDataFrame
        reimported = from_geodataframe(gdf)
        self.assertEqual(len(reimported), len(segments))


if __name__ == "__main__":
    unittest.main()
