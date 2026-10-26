"""Tests for under-covered public utility helpers.

These cover validation edge cases, the QML style writer, the analytical HTML
report generator and the local WebGL file server.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from zero2route3d.copernicus_dem import CopernicusDemError, CopernicusDemTileSource
from zero2route3d.input_validation import (
    deduplicate_adjacent_coordinates,
    finite_number,
    normalize_bbox,
    normalize_time_intervals,
    validate_waypoint_coordinates,
    value_at,
)
from zero2route3d.profile_stats import CueInstruction, RouteStatistics
from zero2route3d.qml_generator import generate_route_qml_style
from zero2route3d.report_generator import generate_analytical_report_html
from zero2route3d.routing_engine import RouteResult3D, Waypoint
from zero2route3d.tsp_solver import solve_tsp_order


class TestFiniteNumber(unittest.TestCase):
    def test_returns_float_for_numeric_input(self) -> None:
        self.assertEqual(finite_number("3.5"), 3.5)

    def test_falls_back_for_non_finite_and_invalid_input(self) -> None:
        self.assertEqual(finite_number(float("nan"), 7.0), 7.0)
        self.assertEqual(finite_number(float("inf"), 7.0), 7.0)
        self.assertEqual(finite_number("not-a-number", 7.0), 7.0)
        self.assertEqual(finite_number(None, 7.0), 7.0)


class TestNormalizeBbox(unittest.TestCase):
    def test_swaps_reversed_axes(self) -> None:
        min_lon, min_lat, max_lon, max_lat = normalize_bbox((10.0, 20.0, 5.0, 15.0))
        self.assertEqual((min_lon, max_lon), (5.0, 10.0))
        self.assertEqual((min_lat, max_lat), (15.0, 20.0))

    def test_expands_degenerate_span(self) -> None:
        min_lon, min_lat, max_lon, max_lat = normalize_bbox((27.0, 38.0, 27.0, 38.0), 0.01)
        self.assertAlmostEqual(max_lon - min_lon, 0.01)
        self.assertAlmostEqual(max_lat - min_lat, 0.01)

    def test_rejects_short_invalid_and_out_of_range_extents(self) -> None:
        with self.assertRaises(ValueError):
            normalize_bbox((1.0, 2.0, 3.0))
        with self.assertRaises(ValueError):
            normalize_bbox((1.0, 2.0, float("nan"), 4.0))
        with self.assertRaises(ValueError):
            normalize_bbox((200.0, 0.0, 201.0, 1.0))
        with self.assertRaises(ValueError):
            normalize_bbox((0.0, -100.0, 1.0, 1.0))


class TestNormalizeTimeIntervals(unittest.TestCase):
    def test_sorts_deduplicates_and_filters(self) -> None:
        intervals = normalize_time_intervals([15, 5, 5, -2, 0, "10", float("nan")])
        self.assertEqual(intervals, [5.0, 10.0, 15.0])

    def test_caps_count_and_maximum(self) -> None:
        intervals = normalize_time_intervals([1, 2, 3, 4, 5], max_intervals=3, max_minutes=4)
        self.assertEqual(intervals, [1.0, 2.0, 3.0])

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(normalize_time_intervals([]), [])


class TestValidateWaypoints(unittest.TestCase):
    def test_valid_waypoints_return_none(self) -> None:
        self.assertIsNone(validate_waypoint_coordinates([Waypoint(27.0, 38.0)]))

    def test_reports_empty_invalid_and_out_of_range(self) -> None:
        self.assertIsNotNone(validate_waypoint_coordinates([]))
        self.assertIn("invalid", validate_waypoint_coordinates([Waypoint(float("nan"), 38.0)]))
        self.assertIn("WGS84", validate_waypoint_coordinates([Waypoint(500.0, 38.0)]))
        self.assertIsNotNone(validate_waypoint_coordinates([Waypoint(0.0, 0.0)] * 501))


class TestDeduplicateCoordinates(unittest.TestCase):
    def test_removes_duplicates_and_invalid_rows(self) -> None:
        coords = [
            (27.0, 38.0, 5.0),
            (27.0, 38.0, 5.0),
            (None, 38.0),
            (27.0, 38.0, 9.0),
            (27.001, 38.0, 5.0),
        ]
        cleaned = deduplicate_adjacent_coordinates(coords, tolerance_m=1.0)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(cleaned[0][2], 9.0)
        self.assertEqual(cleaned[1][0], 27.001)


class TestPerSegmentValues(unittest.TestCase):
    def test_value_at_accepts_scalars_and_any_sequence(self) -> None:
        self.assertEqual(value_at(18.0, 3), 18.0)
        self.assertEqual(value_at(np.int64(20), 0), 20.0)
        self.assertEqual(value_at([10.0, 20.0], 1), 20.0)
        self.assertEqual(value_at(np.array([10.0, 20.0]), 1), 20.0)

    def test_speed_arrays_match_speed_lists(self) -> None:
        from zero2route3d.ev_energy import EVEnergySimulator
        from zero2route3d.micromobility_kinetics import evaluate_micro_mobility_comfort

        lengths, surfaces = [100.0, 200.0], ["asphalt_smooth", "gravel"]
        self.assertEqual(
            evaluate_micro_mobility_comfort(lengths, surfaces, np.array([15.0, 20.0])).to_dict(),
            evaluate_micro_mobility_comfort(lengths, surfaces, [15.0, 20.0]).to_dict(),
        )
        route = [(0.0, 0.0, 0.0), (100.0, 0.0, 1.0), (200.0, 0.0, 2.0)]
        sim = EVEnergySimulator()
        self.assertEqual(
            sim.simulate_route(route, target_speeds_kmh=np.array([50.0, 60.0])).to_dict(),
            sim.simulate_route(route, target_speeds_kmh=[50.0, 60.0]).to_dict(),
        )


class TestCopernicusDemTiles(unittest.TestCase):
    def test_tile_id_handles_southern_and_western_hemispheres(self) -> None:
        self.assertEqual(CopernicusDemTileSource.tile_id(-73.9, -33.4), "S34_00_W074_00")

    def test_tile_id_rejects_invalid_coordinates(self) -> None:
        with self.assertRaises(CopernicusDemError):
            CopernicusDemTileSource.tile_id("a", 0.0)
        with self.assertRaises(CopernicusDemError):
            CopernicusDemTileSource.tile_id(0.0, float("inf"))
        with self.assertRaises(CopernicusDemError):
            CopernicusDemTileSource.tile_id(181.0, 0.0)

    def test_tiles_for_bbox_normalises_and_limits(self) -> None:
        tiles = CopernicusDemTileSource.tiles_for_bbox((27.9, 38.9, 27.1, 38.1))
        self.assertEqual(len(tiles), 1)
        self.assertEqual((tiles[0][0], tiles[0][1]), (27, 38))
        self.assertTrue(tiles[0][2].endswith(".tif"))
        with self.assertRaises(CopernicusDemError):
            CopernicusDemTileSource.tiles_for_bbox((-10.0, -10.0, 10.0, 10.0))
        with self.assertRaises(CopernicusDemError):
            CopernicusDemTileSource.tiles_for_bbox((1.0, 2.0))
        with self.assertRaises(CopernicusDemError):
            CopernicusDemTileSource.tiles_for_bbox((0.0, 0.0, float("nan"), 1.0))


class TestTspSolver(unittest.TestCase):
    def test_few_points_are_returned_unchanged(self) -> None:
        self.assertEqual(solve_tsp_order([(0.0, 0.0, 0.0)]), [0])
        self.assertEqual(solve_tsp_order([(0.0, 0.0, 0.0), (1.0, 1.0, 0.0)]), [0, 1])

    def test_fixed_endpoints_are_preserved(self) -> None:
        points = [
            (27.0, 38.0, 0.0),
            (27.009, 38.0, 0.0),
            (27.001, 38.0, 0.0),
            (27.002, 38.0, 0.0),
            (27.010, 38.0, 0.0),
        ]
        order = solve_tsp_order(points, fix_start=True, fix_end=True)
        self.assertEqual(order[0], 0)
        self.assertEqual(order[-1], 4)
        self.assertEqual(sorted(order), list(range(len(points))))

    def test_unfixed_endpoints_still_return_every_index(self) -> None:
        points = [(27.0 + 0.001 * i, 38.0, 0.0) for i in range(6)]
        order = solve_tsp_order(points, fix_start=False, fix_end=False)
        self.assertEqual(sorted(order), list(range(len(points))))


class TestQmlGenerator(unittest.TestCase):
    def test_profile_colour_is_embedded(self) -> None:
        xml = generate_route_qml_style("wheelchair")
        self.assertIn("139,92,246,255", xml)
        self.assertIn("<qgis", xml)

    def test_invalid_width_falls_back(self) -> None:
        xml = generate_route_qml_style(line_width_mm=float("nan"))
        self.assertIn('value="1.2"', xml)

    def test_qml_path_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "style.qml"
            xml = generate_route_qml_style(target)
            self.assertTrue(target.is_file())
            self.assertEqual(target.read_text(encoding="utf-8"), xml)


class TestAnalyticalReport(unittest.TestCase):
    def _result(self) -> RouteResult3D:
        stats = RouteStatistics(
            total_distance_m=1000.0,
            total_duration_s=600.0,
            elevation_gain_m=25.0,
            elevation_loss_m=5.0,
            min_elevation_m=10.0,
            max_elevation_m=35.0,
            max_slope_pct=8.0,
            avg_slope_pct=3.0,
            total_calories_kcal=42.0,
            thermal_comfort_score=0.7,
            slope_distribution={"0-3%": 60.0, "3-6%": 40.0},
            cue_sheet=[
                CueInstruction(
                    step_number=1,
                    instruction="Continue straight.",
                    direction="straight",
                    distance_m=100.0,
                    elevation_delta_m=2.0,
                    slope_pct=2.0,
                    street_name="Main Street",
                )
            ],
        )
        from zero2route3d.mobility_profiles import get_profile

        return RouteResult3D(
            coordinates_3d=[(27.0, 38.0, 10.0), (27.01, 38.01, 35.0)],
            statistics=stats,
            profile=get_profile("adult"),
        )

    def test_report_is_written_with_route_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.html"
            generate_analytical_report_html(self._result(), target, report_title="Audit")
            html = target.read_text(encoding="utf-8")
            self.assertIn("Audit", html)
            self.assertIn("Continue straight.", html)
            self.assertIn("PASSED", html)


class TestLocalServer(unittest.TestCase):
    def test_missing_directory_raises(self) -> None:
        from zero2route3d.local_server import Route3DLocalServer

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                Route3DLocalServer(Path(tmp) / "missing")

    def test_start_and_stop_lifecycle(self) -> None:
        from zero2route3d.local_server import Route3DLocalServer

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "index.html").write_text("<html></html>", encoding="utf-8")
            server = Route3DLocalServer(Path(tmp), start_port=0, end_port=0)
            self.assertFalse(server.is_running)
            self.assertEqual(server.url, "")
            url = server.start()
            try:
                self.assertTrue(server.is_running)
                self.assertTrue(url.endswith("/index.html"))
                self.assertGreater(server.port or 0, 0)
                self.assertEqual(server.url, url)
            finally:
                server.stop()
            self.assertFalse(server.is_running)


if __name__ == "__main__":
    unittest.main()
