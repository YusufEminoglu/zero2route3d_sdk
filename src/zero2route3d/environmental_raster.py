"""Multi-criteria environmental raster cost surfaces and spatial sampling.

Supports sampling digital elevation models (DEM), slope/aspect derivation,
solar irradiance, Land Surface Temperature (LST), and tree canopy/greenery indices.

Rasters may be supplied either as QGIS raster layers (when running inside QGIS)
or, headless, as GeoTIFF file paths -- see :class:`EnvironmentalSurfaceSampler`.
"""

from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .kinematics import haversine_distance_2d, solar_irradiance_aspect_factor
from .raster_source import GeoTiffRasterSource, open_raster_source

RasterInput = Union[str, Path, GeoTiffRasterSource, Any]


@dataclass
class MCDAWeights:
    """Weights configuration for Multi-Criteria Decision Analysis (AHP)."""

    weight_distance: float = 1.0
    weight_slope: float = 1.0
    weight_heat: float = 0.5
    weight_green: float = 0.5
    weight_safety: float = 0.5
    weight_solar: float = 0.3
    weight_extra: float = 0.5

    def __init__(
        self,
        weight_distance: float = 1.0,
        weight_slope: float = 1.0,
        weight_heat: float = 0.5,
        weight_green: float = 0.5,
        weight_safety: float = 0.5,
        weight_solar: float = 0.3,
        weight_extra: float = 0.5,
        **kwargs: Any,
    ) -> None:
        def _clean_w(val: Any, default: float) -> float:
            try:
                f = float(val)
                return max(0.0, f) if math.isfinite(f) else default
            except (ValueError, TypeError):
                return default

        self.weight_distance = _clean_w(kwargs.get("distance", weight_distance), 1.0)
        self.weight_slope = _clean_w(kwargs.get("slope", weight_slope), 1.0)
        self.weight_heat = _clean_w(kwargs.get("heat", weight_heat), 0.5)
        self.weight_green = _clean_w(kwargs.get("green", weight_green), 0.5)
        self.weight_safety = _clean_w(kwargs.get("safety", weight_safety), 0.5)
        self.weight_solar = _clean_w(kwargs.get("solar", weight_solar), 0.3)
        self.weight_extra = _clean_w(kwargs.get("extra", weight_extra), 0.5)

    def normalized_dict(self) -> Dict[str, float]:
        """Return dictionary of normalized weight coefficients summing to 1.0."""
        total = (
            self.weight_distance
            + self.weight_slope
            + self.weight_heat
            + self.weight_green
            + self.weight_safety
            + self.weight_solar
        )
        if not math.isfinite(total) or total <= 0:
            return {
                "distance": 0.2,
                "slope": 0.2,
                "heat": 0.2,
                "green": 0.2,
                "safety": 0.1,
                "solar": 0.1,
            }
        return {
            "distance": self.weight_distance / total,
            "slope": self.weight_slope / total,
            "heat": self.weight_heat / total,
            "green": self.weight_green / total,
            "safety": self.weight_safety / total,
            "solar": self.weight_solar / total,
        }


class EnvironmentalSurfaceSampler:
    """Samples environmental parameters from GeoTIFF files or QGIS raster layers.

    Every raster argument accepts either a GeoTIFF path (headless, via rasterio)
    or a live QGIS raster layer. Paths are the normal choice for SDK use::

        sampler = EnvironmentalSurfaceSampler(dem="izmir_dem.tif", lst="lst.tif")

    When no DEM is configured at all, :meth:`sample_elevation` falls back to the
    :class:`~zero2route3d.dem_fetcher.GlobalDemFetcher` cache and returns None for
    points it has never seen. Call :meth:`prefetch_elevations` to fill that cache
    from Open-Elevation in one batched request.
    """

    def __init__(
        self,
        dem_layer: Optional[RasterInput] = None,
        dem_layers: Optional[Sequence[RasterInput]] = None,
        lst_layer: Optional[RasterInput] = None,
        green_layer: Optional[RasterInput] = None,
        additional_layers: Optional[Sequence[RasterInput]] = None,
        sun_azimuth_deg: float = 180.0,
        sun_elevation_deg: float = 55.0,
        weights: Optional[MCDAWeights] = None,
        dem: Optional[RasterInput] = None,
        lst: Optional[RasterInput] = None,
        green: Optional[RasterInput] = None,
        lst_range_c: Tuple[float, float] = (20.0, 50.0),
    ) -> None:
        dem_layer = dem if dem is not None else dem_layer
        lst_layer = lst if lst is not None else lst_layer
        green_layer = green if green is not None else green_layer

        self.dem_layer = self._coerce_raster(dem_layer)
        self.dem_layers: List[Any] = [
            self._coerce_raster(layer) for layer in (dem_layers or []) if layer is not None
        ]
        if self.dem_layer is not None and self.dem_layer not in self.dem_layers:
            self.dem_layers.insert(0, self.dem_layer)
        self.lst_layer = self._coerce_raster(lst_layer)
        self.green_layer = self._coerce_raster(green_layer)
        self.additional_layers: List[Any] = [
            self._coerce_raster(layer) for layer in (additional_layers or []) if layer is not None
        ]
        self.sun_azimuth_deg = sun_azimuth_deg if math.isfinite(sun_azimuth_deg) else 180.0
        self.sun_elevation_deg = sun_elevation_deg if math.isfinite(sun_elevation_deg) else 55.0
        self.weights = weights or MCDAWeights()
        low_c, high_c = float(lst_range_c[0]), float(lst_range_c[1])
        self.lst_range_c: Tuple[float, float] = (
            (low_c, high_c)
            if math.isfinite(low_c) and math.isfinite(high_c) and high_c > low_c
            else (20.0, 50.0)
        )
        self._dem_cache: Dict[Tuple[float, float], Optional[float]] = {}
        self._lst_cache: Dict[Tuple[float, float], Optional[float]] = {}
        self._green_cache: Dict[Tuple[float, float], Optional[float]] = {}
        self._additional_range_cache: Dict[str, Tuple[float, float]] = {}

    @staticmethod
    def _coerce_raster(source: Optional[RasterInput]) -> Any:
        """Wrap GeoTIFF paths in a GeoTiffRasterSource; pass QGIS layers straight through."""
        coerced = open_raster_source(source)
        return coerced if coerced is not None else source

    @staticmethod
    def _sample_raster(layer: Any, lon: float, lat: float) -> Optional[float]:
        """Sample one raster at a WGS84 coordinate, whichever kind of raster it is."""
        if layer is None:
            return None

        if isinstance(layer, GeoTiffRasterSource):
            try:
                return layer.sample(lon, lat)
            except Exception:
                return None

        with contextlib.suppress(Exception):
            from qgis.core import (
                QgsCoordinateReferenceSystem,
                QgsCoordinateTransform,
                QgsPointXY,
                QgsProject,
            )

            pt = QgsPointXY(lon, lat)
            crs_src = QgsCoordinateReferenceSystem("EPSG:4326")
            crs_dest = layer.crs()
            if crs_src != crs_dest:
                transform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
                pt = transform.transform(pt)

            val, success = layer.dataProvider().sample(pt, 1)
            if success and val is not None and math.isfinite(val) and val > -9999:
                return float(val)
        return None

    def set_additional_layers(self, layers: Sequence[RasterInput]) -> None:
        """Replace the unlimited MCDA raster stack without rebuilding the sampler."""
        self.additional_layers = [
            self._coerce_raster(layer) for layer in layers if layer is not None
        ]
        self._additional_range_cache.clear()

    @property
    def has_elevation_source(self) -> bool:
        """True when at least one DEM raster is configured on this sampler."""
        return bool(self.dem_layers)

    def prefetch_elevations(
        self,
        coords: Sequence[Tuple[float, float]],
        timeout_sec: float = 10.0,
    ) -> int:
        """Fill the elevation cache for many coordinates in one Open-Elevation request.

        Only meaningful when no DEM raster is configured. Returns the number of
        points that were resolved. Requires network access; unresolved points stay
        unknown rather than silently becoming sea level.
        """
        if self.has_elevation_source or not coords:
            return 0
        from .dem_fetcher import GlobalDemFetcher

        values = GlobalDemFetcher.fetch_elevations_for_coords(coords, timeout_sec=timeout_sec)
        resolved = 0
        for (lon, lat), value in zip(coords, values):
            if value is None:
                continue
            self._dem_cache[(round(lon, 5), round(lat, 5))] = float(value)
            resolved += 1
        return resolved

    def sample_elevation(self, lon: float, lat: float) -> Optional[float]:
        """Sample elevation in metres at a WGS84 coordinate, or None if unknown.

        Returns None -- not 0.0 -- when no DEM covers the point. Zero is a valid
        elevation, so substituting it silently flattens terrain: slopes computed
        against real neighbours become cliffs, and a whole network with no DEM
        looks perfectly flat and therefore fully ADA-compliant.
        """
        if not math.isfinite(lon) or not math.isfinite(lat):
            return None

        coord_key = (round(lon, 5), round(lat, 5))
        if coord_key in self._dem_cache:
            return self._dem_cache[coord_key]

        for dem_layer in self.dem_layers:
            elevation = self._sample_raster(dem_layer, lon, lat)
            if elevation is not None:
                self._dem_cache[coord_key] = elevation
                return elevation

        # Fall back to the cached Open-Elevation samples; None stays None.
        from .dem_fetcher import GlobalDemFetcher

        cached = GlobalDemFetcher.get_fast_elevation(lon, lat)
        if cached is not None and not math.isfinite(cached):
            cached = None
        self._dem_cache[coord_key] = cached
        return cached

    def sample_slope_and_aspect(
        self,
        p1: Sequence[float],
        p2: Sequence[float],
    ) -> Tuple[float, float, float]:
        """Compute directional slope (%), aspect angle (deg), and solar irradiance factor (0..1)."""
        if not p1 or not p2 or len(p1) < 2 or len(p2) < 2:
            return 0.0, 0.0, 0.5

        lon1, lat1 = float(p1[0]), float(p1[1])
        lon2, lat2 = float(p2[0]), float(p2[1])
        if not (
            math.isfinite(lon1)
            and math.isfinite(lat1)
            and math.isfinite(lon2)
            and math.isfinite(lat2)
        ):
            return 0.0, 0.0, 0.5

        dist_2d = haversine_distance_2d(p1, p2)
        if not math.isfinite(dist_2d) or dist_2d < 0.1:
            return 0.0, 0.0, 0.5

        z1 = (
            float(p1[2])
            if len(p1) > 2 and math.isfinite(float(p1[2]))
            else self.sample_elevation(lon1, lat1)
        )
        z2 = (
            float(p2[2])
            if len(p2) > 2 and math.isfinite(float(p2[2]))
            else self.sample_elevation(lon2, lat2)
        )
        if z1 is None or z2 is None:
            # No elevation data here: report a flat, zero-slope segment with a
            # neutral solar factor rather than inventing a gradient.
            return 0.0, 0.0, 1.0

        dz = z2 - z1
        if not math.isfinite(dz):
            dz = 0.0

        slope_pct = (dz / dist_2d) * 100.0
        if not math.isfinite(slope_pct):
            slope_pct = 0.0

        mean_lat = (lat1 + lat2) * 0.5
        dx = (lon2 - lon1) * math.cos(math.radians(mean_lat))
        dy = lat2 - lat1
        bearing_rad = math.atan2(dx, dy)
        aspect_deg = (math.degrees(bearing_rad) + 360.0) % 360.0

        solar_factor = solar_irradiance_aspect_factor(
            aspect_deg=aspect_deg,
            slope_pct=slope_pct,
            sun_azimuth_deg=self.sun_azimuth_deg,
            sun_elevation_deg=self.sun_elevation_deg,
        )

        return slope_pct, aspect_deg, solar_factor

    def sample_lst(self, lon: float, lat: float) -> Optional[float]:
        """Sample Land Surface Temperature (normalized 0.0 = cool, 1.0 = hot).

        Raw raster values are read as degrees Celsius and rescaled with the
        ``lst_range_c`` window given to the constructor (20-50 C by default).

        Returns None when no LST raster is configured or the point cannot be
        sampled. Callers must treat None as "no data" and drop the criterion --
        never as an average value, which would fabricate a thermal surface.
        """
        if not math.isfinite(lon) or not math.isfinite(lat):
            return None

        coord_key = (round(lon, 5), round(lat, 5))
        if coord_key in self._lst_cache:
            return self._lst_cache[coord_key]

        normalized: Optional[float] = None
        raw = self._sample_raster(self.lst_layer, lon, lat)
        if raw is not None:
            low_c, high_c = self.lst_range_c
            normalized = max(0.0, min(1.0, (raw - low_c) / (high_c - low_c)))

        self._lst_cache[coord_key] = normalized
        return normalized

    def sample_greenery(self, lon: float, lat: float) -> Optional[float]:
        """Sample green tree canopy / NDVI (0.0 = bare/concrete, 1.0 = lush canopy).

        NDVI rasters in the native -1..1 range are rescaled to 0..1; rasters
        already stored as 0..1 fractions pass through unchanged.

        Returns None when no greenery raster is configured -- see sample_lst.
        """
        if not math.isfinite(lon) or not math.isfinite(lat):
            return None

        coord_key = (round(lon, 5), round(lat, 5))
        if coord_key in self._green_cache:
            return self._green_cache[coord_key]

        normalized: Optional[float] = None
        raw = self._sample_raster(self.green_layer, lon, lat)
        if raw is not None:
            # NDVI is defined on -1..1; anything below zero is water or bare rock.
            normalized = max(0.0, min(1.0, raw))

        self._green_cache[coord_key] = normalized
        return normalized

    def _additional_layer_range(self, layer: Any) -> Optional[Tuple[float, float]]:
        """Read a raster's real min/max statistics once for normalization."""
        try:
            layer_id = str(layer.id())
        except Exception:
            layer_id = str(id(layer))
        if layer_id in self._additional_range_cache:
            return self._additional_range_cache[layer_id]

        if isinstance(layer, GeoTiffRasterSource):
            with contextlib.suppress(Exception):
                value_range = layer.value_range()
                if value_range is not None:
                    self._additional_range_cache[layer_id] = value_range
                    return value_range
            return None

        with contextlib.suppress(Exception):
            from qgis.core import QgsRasterBandStats

            flags = QgsRasterBandStats.Min | QgsRasterBandStats.Max
            stats = layer.dataProvider().bandStatistics(1, flags, layer.extent(), 0)
            minimum = float(stats.minimumValue)
            maximum = float(stats.maximumValue)
            if math.isfinite(minimum) and math.isfinite(maximum) and maximum > minimum:
                self._additional_range_cache[layer_id] = (minimum, maximum)
                return minimum, maximum
        return None

    def sample_additional_resistance(self, lon: float, lat: float) -> List[float]:
        """Sample every configured MCDA raster and normalize each to 0..1.

        Invalid or unavailable layers are skipped explicitly; they never become
        an invented 0.5 surface and therefore cannot silently affect routing.
        """
        if not (math.isfinite(lon) and math.isfinite(lat)):
            return []
        values: List[float] = []
        for layer in self.additional_layers:
            raw_value = self._sample_raster(layer, lon, lat)
            if raw_value is None:
                continue
            value_range = self._additional_layer_range(layer)
            if value_range is None:
                continue
            minimum, maximum = value_range
            values.append(max(0.0, min(1.0, (raw_value - minimum) / (maximum - minimum))))
        return values
