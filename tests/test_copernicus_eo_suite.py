"""Offline tests for the corridor elevation raster writer and corridor mask."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zero2route3d.copernicus_eo_suite import CopernicusEOSuite, _distance_to_segment_m
from zero2route3d.dem_fetcher import NODATA, GlobalDemFetcher


def _read_ifd(path: Path) -> dict[int, tuple[int, int, int]]:
    """Return ``{tag: (type, count, value_or_offset)}`` from a little-endian TIFF."""
    data = path.read_bytes()
    assert data[:4] == b"II\x2a\x00"
    (ifd_offset,) = struct.unpack_from("<I", data, 4)
    (count,) = struct.unpack_from("<H", data, ifd_offset)
    entries = {}
    for index in range(count):
        tag, kind, n, value = struct.unpack_from("<HHII", data, ifd_offset + 2 + index * 12)
        entries[tag] = (kind, n, value)
    return entries


class TestPurePythonGeoTiff(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "dem.tif"
        self.grid = [[100.5, 200.25], [NODATA, 300.0]]
        self.transform = (29.0, 0.5, 0.0, 41.0, 0.0, -0.5)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_declares_float_samples_crs_and_nodata(self) -> None:
        stats = CopernicusEOSuite._write_pure_python_geotiff(
            self.path, self.grid, 2, 2, self.transform, NODATA
        )
        self.assertEqual(stats, (100.5, 300.0))

        tags = _read_ifd(self.path)
        self.assertEqual(list(tags), sorted(tags))
        self.assertEqual(tags[339][2], 3)  # SampleFormat = IEEE float
        self.assertIn(34735, tags)  # GeoKeyDirectory (EPSG:4326)
        kind, count, offset = tags[42113]
        raw = self.path.read_bytes()[offset : offset + count]
        self.assertEqual(float(raw.rstrip(b"\0").decode("ascii")), NODATA)

        pixel_offset = tags[273][2]
        values = struct.unpack_from("<4f", self.path.read_bytes(), pixel_offset)
        self.assertEqual(list(values), [100.5, 200.25, NODATA, 300.0])

    def test_rasterio_reads_values_crs_and_nodata(self) -> None:
        try:
            import rasterio
        except ImportError:
            self.skipTest("rasterio not installed")
        CopernicusEOSuite._write_pure_python_geotiff(
            self.path, self.grid, 2, 2, self.transform, NODATA
        )
        with rasterio.open(self.path) as dataset:
            self.assertEqual(dataset.dtypes[0], "float32")
            self.assertEqual(dataset.crs.to_epsg(), 4326)
            self.assertEqual(dataset.nodata, NODATA)
            self.assertEqual(dataset.read(1).tolist(), [[100.5, 200.25], [NODATA, 300.0]])


class TestCorridorMask(unittest.TestCase):
    def test_distance_to_segment_uses_interior_points(self) -> None:
        start, end = (29.0, 41.0), (29.02, 41.0)
        self.assertLess(_distance_to_segment_m((29.01, 41.0), start, end), 1.0)
        self.assertAlmostEqual(_distance_to_segment_m(start, start, start), 0.0)
        # ~111 m north of the segment midpoint.
        self.assertAlmostEqual(
            _distance_to_segment_m((29.01, 41.001), start, end), 111.2, delta=1.0
        )

    def test_cells_between_distant_vertices_stay_inside_corridor(self) -> None:
        width, height, res = 21, 3, 0.001
        grid = [[1.0] * width for _ in range(height)]
        CopernicusEOSuite._apply_corridor_mask(
            [grid], 29.0, 40.9985, res, width, height, [(29.0, 41.0), (29.021, 41.0)], 30.0
        )
        self.assertEqual(grid[1], [1.0] * width)  # the row the route runs along
        self.assertEqual(grid[0], [NODATA] * width)  # ~111 m away, outside 30 m + margin
        self.assertEqual(grid[2], [NODATA] * width)


class TestFetchAndClip(unittest.TestCase):
    def test_end_to_end_with_stubbed_elevations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)

            def fake_fetch(coords, timeout_sec=3.0):
                return [None if i == 0 else 50.0 + i for i in range(len(coords))]

            with (
                mock.patch.object(CopernicusEOSuite, "get_output_dir", return_value=out_dir),
                mock.patch.object(
                    GlobalDemFetcher, "fetch_elevations_for_coords", side_effect=fake_fetch
                ),
            ):
                results = CopernicusEOSuite.fetch_and_clip_multispectral_stack(
                    (29.01, 41.01, 29.0, 41.0), resolution_deg=0.001
                )

            self.assertEqual(len(results), 1)
            layer = results[0]
            self.assertEqual(layer.key, "dem")
            self.assertTrue(layer.file_path.is_file())
            self.assertEqual(layer.file_path.parent, out_dir)
            self.assertEqual(layer.min_val, 51.0)
            self.assertGreater(layer.max_val, layer.min_val)


if __name__ == "__main__":
    unittest.main()
