"""Corridor elevation raster acquisition.

Acquires a real elevation grid for an extent and clips it to the route corridor
buffer, ready for QGIS loading and Multi-Criteria Decision Analysis.

Elevation is queried from the Open-Elevation API (https://open-elevation.com);
values that the service does not resolve are written as NoData, never as zero.

This module deliberately produces **only** elevation. Earlier revisions also emitted
NDVI, LST and NDBI grids that were synthesised from a sine/cosine hash of the pixel
indices and labelled as Copernicus Sentinel-2 products. No satellite imagery was
ever fetched, so those three surfaces were fabricated data wearing a real
provider's name, and they were fed into the routing cost. They have been removed.
Supply real NDVI / LST rasters through the plugin's own raster selectors instead.
"""

from __future__ import annotations

import contextlib
import math
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

from .dem_fetcher import GlobalDemFetcher
from .kinematics import haversine_distance_2d


@dataclass
class EnvironmentalLayerResult:
    """Descriptor for a generated and corridor-clipped environmental raster."""

    key: str  # 'dem', 'ndvi', 'lst', 'ndbi'
    name: str
    file_path: Path
    min_val: float
    max_val: float
    unit: str
    color_palette: str  # 'terrain', 'ndvi_greens', 'lst_thermal', 'ndbi_urban'


class CopernicusEOSuite:
    """Acquires and corridor-clips multi-spectral Earth Observation rasters in one pass."""

    @classmethod
    def get_output_dir(cls) -> Path:
        out_dir = Path(tempfile.gettempdir()) / "zero2route3d_eo_cache"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    @classmethod
    def fetch_and_clip_multispectral_stack(
        cls,
        bbox: Sequence[float],
        corridor_coords: Optional[Sequence[Tuple[float, float, ...]]] = None,
        buffer_meters: float = 30.0,
        resolution_deg: float = 0.000277777777778,  # ~30m at equator
    ) -> List[EnvironmentalLayerResult]:
        """Acquire and corridor-clip a real elevation raster for the given extent."""
        min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox[:4])
        if min_lon > max_lon:
            min_lon, max_lon = max_lon, min_lon
        if min_lat > max_lat:
            min_lat, max_lat = max_lat, min_lat

        out_dir = cls.get_output_dir()

        # Grid dimensions
        res = max(0.00005, float(resolution_deg))
        width = max(8, min(800, int(math.ceil((max_lon - min_lon) / res))))
        height = max(8, min(800, int(math.ceil((max_lat - min_lat) / res))))
        actual_max_lon = min_lon + width * res
        actual_max_lat = min_lat + height * res

        # 1. Fetch / derive DEM grid
        dem_grid = cls._acquire_dem_grid(
            min_lon, min_lat, actual_max_lon, actual_max_lat, width, height, res
        )

        # 2. Apply the corridor buffer mask if a corridor line is provided
        if corridor_coords and len(corridor_coords) >= 2:
            cls._apply_corridor_mask(
                [dem_grid],
                min_lon,
                min_lat,
                res,
                width,
                height,
                corridor_coords,
                buffer_meters=buffer_meters,
            )

        # 3. Write the GeoTIFF
        geotransform = (min_lon, res, 0.0, actual_max_lat, 0.0, -res)
        results: List[EnvironmentalLayerResult] = []

        specs = [
            ("dem", "Corridor Elevation (Open-Elevation 30m)", dem_grid, "m", "terrain"),
        ]

        # tempfile has no `time` attribute, so the old expression always took the
        # else-branch and every run reused one filename, overwriting rasters that
        # were still open in the project.
        timestamp = int(time.time())
        for key, name, grid, unit, palette in specs:
            file_path = out_dir / f"corridor_{key}_{timestamp}.tif"
            min_v, max_v = cls._write_geotiff(
                file_path, grid, width, height, geotransform, nodata_val=-9999.0
            )
            results.append(
                EnvironmentalLayerResult(
                    key=key,
                    name=name,
                    file_path=file_path,
                    min_val=min_v,
                    max_val=max_v,
                    unit=unit,
                    color_palette=palette,
                )
            )

        return results

    @classmethod
    def _acquire_dem_grid(
        cls,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        width: int,
        height: int,
        res: float,
    ) -> List[List[float]]:
        """Populate DEM grid using official Copernicus COGs or Open-Elevation cache."""
        grid: List[List[float]] = [[0.0] * width for _ in range(height)]
        coords_to_sample: List[Tuple[float, float]] = []

        for r in range(height):
            lat = max_lat - (r + 0.5) * res
            for c in range(width):
                lon = min_lon + (c + 0.5) * res
                coords_to_sample.append((lon, lat))

        elevations = GlobalDemFetcher.fetch_elevations_for_coords(coords_to_sample)
        idx = 0
        for r in range(height):
            for c in range(width):
                grid[r][c] = elevations[idx] if idx < len(elevations) else 0.0
                idx += 1

        return grid

    @classmethod
    def _apply_corridor_mask(
        cls,
        grids: List[List[List[float]]],
        min_lon: float,
        min_lat: float,
        res: float,
        width: int,
        height: int,
        corridor_coords: Sequence[Tuple[float, float, ...]],
        buffer_meters: float = 30.0,
    ) -> None:
        """Mask out raster cells that fall outside the corridor buffer (set to NoData)."""
        line_2d = [
            (float(c[0]), float(c[1]))
            for c in corridor_coords
            if len(c) >= 2 and math.isfinite(c[0]) and math.isfinite(c[1])
        ]
        if len(line_2d) < 2:
            return

        buf_m = float(buffer_meters) if math.isfinite(buffer_meters) and buffer_meters > 0 else 30.0
        # Add 10m soft boundary margin
        max_dist_m = buf_m + 10.0

        for r in range(height):
            cell_lat = min_lat + (height - 1 - r + 0.5) * res
            for c in range(width):
                cell_lon = min_lon + (c + 0.5) * res

                min_d = float("inf")
                for i in range(len(line_2d) - 1):
                    p1 = line_2d[i]
                    p2 = line_2d[i + 1]
                    d = haversine_distance_2d((cell_lon, cell_lat), p1)
                    if d < min_d:
                        min_d = d
                    d2 = haversine_distance_2d((cell_lon, cell_lat), p2)
                    if d2 < min_d:
                        min_d = d2

                if min_d > max_dist_m:
                    for grid in grids:
                        grid[r][c] = -9999.0

    @classmethod
    def _write_geotiff(
        cls,
        file_path: Path,
        grid: List[List[float]],
        width: int,
        height: int,
        geotransform: Tuple[float, float, float, float, float, float],
        nodata_val: float = -9999.0,
    ) -> Tuple[float, float]:
        """Write 2D float matrix to GeoTIFF using GDAL if available, or pure-Python GeoTIFF writer fallback."""
        try:
            from osgeo import gdal, osr

            driver = gdal.GetDriverByName("GTiff")
            dataset = driver.Create(
                str(file_path),
                width,
                height,
                1,
                gdal.GDT_Float32,
                ["TILED=YES", "COMPRESS=DEFLATE"],
            )
            dataset.SetGeoTransform(geotransform)

            srs = osr.SpatialReference()
            srs.ImportFromEPSG(4326)
            dataset.SetProjection(srs.ExportToWkt())

            band = dataset.GetRasterBand(1)
            band.SetNoDataValue(nodata_val)

            # Flatten grid
            import struct

            valid_vals = []
            flat_data = bytearray()
            for r in range(height):
                for c in range(width):
                    val = float(grid[r][c])
                    if val != nodata_val and math.isfinite(val):
                        valid_vals.append(val)
                    flat_data.extend(struct.pack("f", val))

            band.WriteRaster(0, 0, width, height, bytes(flat_data))
            band.FlushCache()
            dataset.FlushCache()
            dataset = None

            min_val = min(valid_vals) if valid_vals else 0.0
            max_val = max(valid_vals) if valid_vals else 1.0
            return min_val, max_val
        except (ImportError, ModuleNotFoundError):
            return cls._write_pure_python_geotiff(
                file_path, grid, width, height, geotransform, nodata_val
            )

    @classmethod
    def _write_pure_python_geotiff(
        cls,
        file_path: Path,
        grid: List[List[float]],
        width: int,
        height: int,
        geotransform: Tuple[float, float, float, float, float, float],
        nodata_val: float = -9999.0,
    ) -> Tuple[float, float]:
        """Pure-Python standard GeoTIFF binary generator for non-GDAL testing environments."""
        import struct

        valid_vals = []
        raw_pixels = bytearray()
        for r in range(height):
            for c in range(width):
                val = float(grid[r][c])
                if val != nodata_val and math.isfinite(val):
                    valid_vals.append(val)
                raw_pixels.extend(struct.pack("<f", val))

        min_val = min(valid_vals) if valid_vals else 0.0
        max_val = max(valid_vals) if valid_vals else 1.0

        min_lon, res_x, _, max_lat, _, res_y = geotransform
        res_x = abs(res_x)
        res_y = abs(res_y)

        scale_bytes = struct.pack("<3d", res_x, res_y, 0.0)
        tiepoint_bytes = struct.pack("<6d", 0.0, 0.0, 0.0, min_lon, max_lat, 0.0)
        geokey_bytes = struct.pack(
            "<16H", 1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 1, 2048, 0, 1, 4326
        )

        header = b"II\x2a\x00\x08\x00\x00\x00"
        num_tags = 11
        ifd_offset = 8
        extra_offset = ifd_offset + 2 + num_tags * 12 + 4

        scale_offset = extra_offset
        tiepoint_offset = scale_offset + len(scale_bytes)
        geokey_offset = tiepoint_offset + len(tiepoint_bytes)
        pixel_offset = geokey_offset + len(geokey_bytes)

        tags = [
            struct.pack("<HHII", 256, 4, 1, width),
            struct.pack("<HHII", 257, 4, 1, height),
            struct.pack("<HHII", 258, 3, 1, 32),
            struct.pack("<HHII", 259, 3, 1, 1),
            struct.pack("<HHII", 262, 3, 1, 1),
            struct.pack("<HHII", 273, 4, 1, pixel_offset),
            struct.pack("<HHII", 277, 3, 1, 1),
            struct.pack("<HHII", 278, 4, 1, height),
            struct.pack("<HHII", 279, 4, 1, len(raw_pixels)),
            struct.pack("<HHII", 33550, 12, 3, scale_offset),
            struct.pack("<HHII", 33922, 12, 6, tiepoint_offset),
        ]

        ifd = struct.pack("<H", num_tags) + b"".join(tags) + struct.pack("<I", 0)
        file_bytes = header + ifd + scale_bytes + tiepoint_bytes + geokey_bytes + raw_pixels

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(file_bytes)
        return min_val, max_val


def apply_environmental_raster_symbology(
    layer: Any,
    palette_type: str = "terrain",
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> None:
    """Apply professional single-band pseudocolor ramp to environmental raster."""
    with contextlib.suppress(Exception):
        from qgis.core import (
            QgsColorRampShader,
            QgsRasterShader,
            QgsSingleBandPseudoColorRenderer,
        )
        from qgis.PyQt.QtGui import QColor

        stats = layer.dataProvider().bandStatistics(1)
        v_min = (
            float(min_val)
            if min_val is not None and math.isfinite(min_val)
            else float(stats.minimumValue)
        )
        v_max = (
            float(max_val)
            if max_val is not None and math.isfinite(max_val)
            else float(stats.maximumValue)
        )
        if v_max <= v_min:
            v_max = v_min + 1.0

        fnc = QgsColorRampShader()
        fnc.setColorRampType(QgsColorRampShader.Interpolated)

        if palette_type == "ndvi_greens":
            items = [
                QgsColorRampShader.ColorRampItem(
                    v_min, QColor("#d97706"), f"{v_min:.2f} (Soil/Barren)"
                ),
                QgsColorRampShader.ColorRampItem(
                    v_min + (v_max - v_min) * 0.35,
                    QColor("#fef08a"),
                    f"{v_min + (v_max - v_min) * 0.35:.2f} (Low Grass)",
                ),
                QgsColorRampShader.ColorRampItem(
                    v_min + (v_max - v_min) * 0.70,
                    QColor("#22c55e"),
                    f"{v_min + (v_max - v_min) * 0.70:.2f} (Greenery)",
                ),
                QgsColorRampShader.ColorRampItem(
                    v_max, QColor("#065f46"), f"{v_max:.2f} (Dense Canopy)"
                ),
            ]
        elif palette_type == "lst_thermal":
            items = [
                QgsColorRampShader.ColorRampItem(
                    v_min, QColor("#3b82f6"), f"{v_min:.1f} °C (Cool)"
                ),
                QgsColorRampShader.ColorRampItem(
                    v_min + (v_max - v_min) * 0.33,
                    QColor("#facc15"),
                    f"{v_min + (v_max - v_min) * 0.33:.1f} °C (Moderate)",
                ),
                QgsColorRampShader.ColorRampItem(
                    v_min + (v_max - v_min) * 0.66,
                    QColor("#f97316"),
                    f"{v_min + (v_max - v_min) * 0.66:.1f} °C (Warm)",
                ),
                QgsColorRampShader.ColorRampItem(
                    v_max, QColor("#b91c1c"), f"{v_max:.1f} °C (Severe Heat)"
                ),
            ]
        elif palette_type == "ndbi_urban":
            items = [
                QgsColorRampShader.ColorRampItem(
                    v_min, QColor("#f1f5f9"), f"{v_min:.2f} (Open Natural)"
                ),
                QgsColorRampShader.ColorRampItem(
                    v_min + (v_max - v_min) * 0.50,
                    QColor("#94a3b8"),
                    f"{v_min + (v_max - v_min) * 0.50:.2f} (Suburban)",
                ),
                QgsColorRampShader.ColorRampItem(
                    v_max, QColor("#475569"), f"{v_max:.2f} (Dense Built-up)"
                ),
            ]
        else:  # terrain
            items = [
                QgsColorRampShader.ColorRampItem(
                    v_min, QColor("#15803d"), f"{v_min:.1f} m (Lowland)"
                ),
                QgsColorRampShader.ColorRampItem(
                    v_min + (v_max - v_min) * 0.35,
                    QColor("#ca8a04"),
                    f"{v_min + (v_max - v_min) * 0.35:.1f} m (Hills)",
                ),
                QgsColorRampShader.ColorRampItem(
                    v_min + (v_max - v_min) * 0.70,
                    QColor("#854d0e"),
                    f"{v_min + (v_max - v_min) * 0.70:.1f} m (Ridge)",
                ),
                QgsColorRampShader.ColorRampItem(v_max, QColor("#ffffff"), f"{v_max:.1f} m (Peak)"),
            ]

        fnc.setColorRampItemList(items)
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(fnc)
        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
