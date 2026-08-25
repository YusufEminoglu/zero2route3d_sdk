"""Headless GeoTIFF sampling: the SDK must read real terrain without QGIS.

Skipped when the optional ``[geo]`` extras are not installed.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Tuple

from zero2route3d import EnvironmentalSurfaceSampler, GeoTiffRasterSource, solve_3d_route
from zero2route3d.integrations import sample_rasterio_dem
from zero2route3d.kinematics import haversine_distance_2d
from zero2route3d.network_source import RoadSegment

rasterio = None
try:  # pragma: no cover - optional [geo] extras
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]

# A 10x10 ramp over 27.10..27.20 E, 38.40..38.50 N: elevation increases eastwards.
WEST, SOUTH, CELL, SIZE = 27.10, 38.40, 0.01, 10
NODATA = -9999.0


def write_ramp_dem(path: Path, crs: str = "EPSG:4326") -> None:
    """Write a small ramp DEM whose value equals 100 + 10 * column index."""
    data = np.zeros((SIZE, SIZE), dtype="float32")
    for row in range(SIZE):
        for col in range(SIZE):
            data[row, col] = 100.0 + 10.0 * col
    data[0, 0] = NODATA  # a genuine NoData cell, top-left

    transform = from_origin(WEST, SOUTH + SIZE * CELL, CELL, CELL)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=SIZE,
        width=SIZE,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=NODATA,
    ) as dataset:
        dataset.write(data, 1)


def cell_center(col: int, row: int) -> Tuple[float, float]:
    """WGS84 centre of a grid cell, with row 0 at the top."""
    lon = WEST + (col + 0.5) * CELL
    lat = SOUTH + SIZE * CELL - (row + 0.5) * CELL
    return lon, lat


@unittest.skipIf(rasterio is None, "rasterio is not installed ([geo] extras)")
class TestGeoTiffSampling(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dem_path = Path(self._tmp.name) / "ramp.tif"
        write_ramp_dem(self.dem_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_source_reads_real_values_and_reports_nodata(self) -> None:
        with GeoTiffRasterSource(self.dem_path) as source:
            self.assertAlmostEqual(source.sample(*cell_center(3, 5)), 130.0, places=3)
            self.assertAlmostEqual(source.sample(*cell_center(9, 0)), 190.0, places=3)
            # The NoData cell must not come back as a number.
            self.assertIsNone(source.sample(*cell_center(0, 0)))
            # Outside the raster there is no data either.
            self.assertIsNone(source.sample(20.0, 10.0))
            self.assertEqual(source.value_range(), (100.0, 190.0))

    def test_sampler_accepts_a_geotiff_path(self) -> None:
        sampler = EnvironmentalSurfaceSampler(dem=self.dem_path)
        self.assertTrue(sampler.has_elevation_source)
        self.assertAlmostEqual(sampler.sample_elevation(*cell_center(2, 4)), 120.0, places=3)
        self.assertIsNone(sampler.sample_elevation(*cell_center(0, 0)))

    def test_route_picks_up_real_elevations(self) -> None:
        # A west-to-east line climbs the ramp by 10 m per cell.
        coords = [cell_center(col, 5) for col in range(1, 9)]
        segments = [
            RoadSegment(
                p1=(a[0], a[1], 0.0),
                p2=(b[0], b[1], 0.0),
                length_m=haversine_distance_2d(a, b),
            )
            for a, b in zip(coords, coords[1:])
        ]
        sampler = EnvironmentalSurfaceSampler(dem=self.dem_path)
        route = solve_3d_route(coords[0], coords[-1], network=segments, dem_sampler=sampler)

        self.assertTrue(route.is_network_matched)
        self.assertGreater(route.statistics.elevation_gain_m, 50.0)
        self.assertGreater(route.statistics.max_elevation_m, route.statistics.min_elevation_m)

    def test_projected_raster_is_reprojected_not_missed(self) -> None:
        projected = Path(self._tmp.name) / "ramp_3857.tif"
        with rasterio.open(self.dem_path) as src:
            from rasterio.warp import Resampling, calculate_default_transform, reproject

            transform, width, height = calculate_default_transform(
                src.crs, "EPSG:3857", src.width, src.height, *src.bounds
            )
            profile = src.profile.copy()
            profile.update(crs="EPSG:3857", transform=transform, width=width, height=height)
            with rasterio.open(projected, "w", **profile) as dst:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs="EPSG:3857",
                    resampling=Resampling.nearest,
                )

        # 0.1.0 fed WGS84 degrees straight into a Web Mercator raster, so every
        # sample fell outside the grid and silently became 0.0.
        with GeoTiffRasterSource(projected) as source:
            value = source.sample(*cell_center(5, 5))
        self.assertIsNotNone(value)
        self.assertAlmostEqual(value, 150.0, delta=10.0)

    def test_sample_rasterio_dem_marks_missing_data(self) -> None:
        values = sample_rasterio_dem(
            self.dem_path,
            [cell_center(4, 4), cell_center(0, 0), (20.0, 10.0)],
        )
        self.assertEqual(len(values), 3)
        self.assertAlmostEqual(values[0], 140.0, places=3)
        self.assertIsNone(values[1])
        self.assertIsNone(values[2])


if __name__ == "__main__":
    unittest.main()
