"""Regression tests for the bugs fixed in 0.2.0.

Each test here fails against 0.1.0. They are deliberately falsifiable: none of
them passes just because a call returned without raising.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import List

from zero2route3d import (
    EnvironmentalSurfaceSampler,
    GlobalDemFetcher,
    MobilityProfile,
    RoutingEngine3D,
    UnknownProfileError,
    Waypoint,
    get_profile,
    resolve_profile,
    solve_3d_route,
)
from zero2route3d.kinematics import haversine_distance_2d
from zero2route3d.network_source import NetworkSourceManager, RoadSegment

LINE_COORDS = [(27.1000 + 0.004 * i, 38.4000 + 0.003 * i, 5.0 + i) for i in range(11)]


def line_segments() -> List[RoadSegment]:
    return [
        RoadSegment(p1=a, p2=b, length_m=haversine_distance_2d(a, b), highway_type="residential")
        for a, b in zip(LINE_COORDS, LINE_COORDS[1:])
    ]


def line_feature_collection(**properties: object) -> dict:
    props = {"highway": "residential"}
    props.update(properties)  # type: ignore[arg-type]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": props,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [list(c) for c in LINE_COORDS],
                },
            }
        ],
    }


class TestGeoJsonNetworkInput(unittest.TestCase):
    """A GeoJSON network is the documented primary input; it must actually load."""

    def test_extract_from_geojson_builds_segments(self) -> None:
        segments = NetworkSourceManager().extract_from_geojson(line_feature_collection())
        self.assertEqual(len(segments), len(LINE_COORDS) - 1)
        self.assertAlmostEqual(segments[0].p1[2], LINE_COORDS[0][2], places=3)
        self.assertEqual(segments[0].highway_type, "residential")

    def test_reversed_oneway_is_stored_in_travel_direction(self) -> None:
        forward = NetworkSourceManager().extract_from_geojson(line_feature_collection())
        reverse = NetworkSourceManager().extract_from_geojson(line_feature_collection(oneway="-1"))
        self.assertTrue(reverse[0].is_oneway)
        # oneway=-1 runs against the digitisation order, so p1/p2 must be swapped.
        self.assertEqual(reverse[0].p1, forward[0].p2)
        self.assertEqual(reverse[0].p2, forward[0].p1)

    def test_route_from_geojson_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "net.geojson"
            path.write_text(json.dumps(line_feature_collection()), encoding="utf-8")
            route = solve_3d_route(LINE_COORDS[0][:2], LINE_COORDS[-1][:2], network=path)
        self.assertTrue(route.is_network_matched)
        self.assertGreater(route.statistics.total_distance_m, 1000.0)

    def test_unusable_network_input_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            solve_3d_route((27.1, 38.4), (27.2, 38.5), network="does_not_exist.geojson")
        with self.assertRaises(ValueError):
            solve_3d_route((27.1, 38.4), (27.2, 38.5), network=12345)


class TestProfileResolution(unittest.TestCase):
    def test_unknown_profile_key_is_rejected_by_the_api(self) -> None:
        # 0.1.0 silently routed this as a pedestrian.
        with self.assertRaises(UnknownProfileError):
            solve_3d_route(
                LINE_COORDS[0][:2],
                LINE_COORDS[-1][:2],
                network=line_segments(),
                profile="commuter_bike",
            )

    def test_profile_instance_is_honoured_not_replaced(self) -> None:
        wheelchair = get_profile("wheelchair")
        route = solve_3d_route(
            LINE_COORDS[0][:2],
            LINE_COORDS[-1][:2],
            network=line_segments(),
            profile=wheelchair,
        )
        self.assertEqual(route.profile_key, "wheelchair")

    def test_custom_profile_survives_the_engine(self) -> None:
        custom = MobilityProfile(
            key="cargo_trike",
            name="Cargo Trike",
            category="micromobility",
            base_speed_kmh=12.0,
            max_slope_pct=8.0,
            stair_allowed=False,
            stair_penalty=100.0,
            slope_sensitivity=2.0,
            heat_sensitivity=0.3,
            green_preference=0.2,
            surface_smoothness_req=0.7,
        )
        self.assertIs(resolve_profile(custom), custom)

        engine = RoutingEngine3D()
        engine.build_graph(line_segments())
        result = engine.calculate_route(
            [Waypoint(*LINE_COORDS[0][:2]), Waypoint(*LINE_COORDS[-1][:2])],
            profile_key=custom,
        )
        self.assertEqual(result.profile_key, "cargo_trike")

    def test_strict_get_profile_lists_valid_keys(self) -> None:
        with self.assertRaises(UnknownProfileError) as ctx:
            get_profile("no_such_profile", strict=True)
        self.assertIn("wheelchair", str(ctx.exception))
        # Non-strict keeps the historical fallback.
        self.assertEqual(get_profile("no_such_profile").key, "adult")


class TestMissingElevationIsNotSeaLevel(unittest.TestCase):
    """Runs against an isolated cache so a developer's warm cache cannot mask a regression."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._saved_cache_file = GlobalDemFetcher._CACHE_FILE
        GlobalDemFetcher._CACHE_FILE = Path(self._tmp.name) / "elevation_cache.json"
        GlobalDemFetcher.clear_cache()

    def tearDown(self) -> None:
        GlobalDemFetcher.clear_cache()
        GlobalDemFetcher._CACHE_FILE = self._saved_cache_file
        self._tmp.cleanup()

    def test_sampler_returns_none_without_a_dem(self) -> None:
        sampler = EnvironmentalSurfaceSampler()
        self.assertFalse(sampler.has_elevation_source)
        # 0.1.0 returned 0.0 here, which is a real elevation somewhere.
        self.assertIsNone(sampler.sample_elevation(27.1428, 38.4237))

    def test_seeded_cache_is_served_without_network(self) -> None:
        accepted = GlobalDemFetcher.seed_cache({(27.1428, 38.4237): 123.5})
        self.assertEqual(accepted, 1)
        self.assertAlmostEqual(GlobalDemFetcher.get_fast_elevation(27.1428, 38.4237), 123.5)
        self.assertIsNone(GlobalDemFetcher.get_fast_elevation(1.0, 1.0))

    def test_batch_fetch_slots_stay_aligned(self) -> None:
        GlobalDemFetcher.seed_cache({(27.1428, 38.4237): 88.0})
        values = GlobalDemFetcher.fetch_elevations_for_coords(
            [(27.1428, 38.4237), (float("nan"), 38.0)], timeout_sec=1.0
        )
        self.assertEqual(len(values), 2)
        self.assertAlmostEqual(values[0], 88.0)
        self.assertIsNone(values[1])

    def test_flat_network_without_dem_is_not_reported_as_measured_terrain(self) -> None:
        flat = [(27.10 + 0.004 * i, 38.40 + 0.003 * i, 0.0) for i in range(6)]
        segments = [
            RoadSegment(p1=a, p2=b, length_m=haversine_distance_2d(a, b))
            for a, b in zip(flat, flat[1:])
        ]
        route = solve_3d_route(flat[0][:2], flat[-1][:2], network=segments)
        self.assertEqual(route.statistics.elevation_gain_m, 0.0)
        self.assertEqual(route.statistics.max_slope_pct, 0.0)


class TestStandaloneReport(unittest.TestCase):
    def test_report_is_self_contained_and_carries_the_route(self) -> None:
        route = solve_3d_route(LINE_COORDS[0][:2], LINE_COORDS[-1][:2], network=line_segments())
        document = route.to_html()

        # 0.1.0 emitted a shell with empty <style> and <script> blocks because it
        # looked for plugin assets that the SDK never shipped.
        self.assertGreater(len(document), 4000)
        self.assertIn("<svg", document)
        self.assertIn("scrubber", document)
        self.assertIn("ROUTE = {", document)
        self.assertNotIn("<style>\n\n  </style>", document)
        # No external asset may be referenced.
        self.assertNotIn('src="http', document)
        self.assertNotIn('href="http', document)

    def test_report_writes_to_disk_once(self) -> None:
        route = solve_3d_route(LINE_COORDS[0][:2], LINE_COORDS[-1][:2], network=line_segments())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "report.html"
            document = route.to_html(out)
            self.assertTrue(out.exists())
            self.assertEqual(out.read_text(encoding="utf-8"), document)


class TestMultiModalHubSelection(unittest.TestCase):
    def test_access_and_egress_hubs_are_distinct(self) -> None:
        from zero2route3d import MultiModalRouter

        engine = RoutingEngine3D()
        engine.build_graph(line_segments())
        router = MultiModalRouter(engine)

        # Both endpoints sit closest to the same hub; 0.1.0 picked it twice and
        # charged a transfer penalty for a zero-length main leg.
        hubs = [
            Waypoint(lon=LINE_COORDS[1][0], lat=LINE_COORDS[1][1], name="Hub A"),
            Waypoint(lon=LINE_COORDS[9][0], lat=LINE_COORDS[9][1], name="Hub B"),
        ]
        journey = router.calculate_multimodal_trip(
            Waypoint(lon=LINE_COORDS[0][0], lat=LINE_COORDS[0][1]),
            Waypoint(lon=LINE_COORDS[2][0], lat=LINE_COORDS[2][1]),
            transit_hubs=hubs,
        )
        self.assertEqual(len(journey.legs), 3)
        self.assertIsNot(journey.legs[1].start_point, journey.legs[1].end_point)


class TestEnergyModelMatchesTheProfile(unittest.TestCase):
    def test_motorised_route_is_not_charged_walking_calories(self) -> None:
        import matplotlib

        matplotlib.use("Agg")
        from zero2route3d import plot_elevation_profile

        car_route = solve_3d_route(
            LINE_COORDS[0][:2], LINE_COORDS[-1][:2], network=line_segments(), profile="car"
        )
        figure = plot_elevation_profile(car_route, show_energy=True)
        # A car has no metabolic cost, so no energy axis may be drawn.
        self.assertEqual(len(figure.axes), 1)

        walk_route = solve_3d_route(
            LINE_COORDS[0][:2], LINE_COORDS[-1][:2], network=line_segments(), profile="adult"
        )
        self.assertEqual(len(plot_elevation_profile(walk_route, show_energy=True).axes), 2)

    def test_pareto_plot_rejects_an_unknown_metric(self) -> None:
        import matplotlib

        matplotlib.use("Agg")
        from zero2route3d import plot_pareto_frontier_2d, solve_4d_pareto_frontier

        frontier = solve_4d_pareto_frontier(
            LINE_COORDS[0][:2], LINE_COORDS[-1][:2], network=line_segments()
        )
        # 0.1.0 quietly plotted calories for any unrecognised metric name.
        with self.assertRaises(ValueError):
            plot_pareto_frontier_2d(frontier, x_metric="distance_km")


if __name__ == "__main__":
    unittest.main()
