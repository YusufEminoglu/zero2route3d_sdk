"""Multi-criteria environmental raster cost surfaces and spatial sampling.

Supports sampling digital elevation models (DEM), slope/aspect derivation,
solar irradiance, Land Surface Temperature (LST), and tree canopy/greenery indices.
"""

from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .kinematics import haversine_distance_2d, solar_irradiance_aspect_factor


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
    """Samples environmental parameters from active QGIS raster layers or real cached data."""

    def __init__(
        self,
        dem_layer: Optional[Any] = None,
        dem_layers: Optional[Sequence[Any]] = None,
        lst_layer: Optional[Any] = None,
        green_layer: Optional[Any] = None,
        additional_layers: Optional[Sequence[Any]] = None,
        sun_azimuth_deg: float = 180.0,
        sun_elevation_deg: float = 55.0,
        weights: Optional[MCDAWeights] = None,
    ) -> None:
        self.dem_layer = dem_layer
        self.dem_layers: List[Any] = list(dem_layers or [])
        if dem_layer is not None and dem_layer not in self.dem_layers:
            self.dem_layers.insert(0, dem_layer)
        self.lst_layer = lst_layer
        self.green_layer = green_layer
        self.additional_layers: List[Any] = list(additional_layers or [])
        self.sun_azimuth_deg = sun_azimuth_deg if math.isfinite(sun_azimuth_deg) else 180.0
        self.sun_elevation_deg = sun_elevation_deg if math.isfinite(sun_elevation_deg) else 55.0
        self.weights = weights or MCDAWeights()
        self._dem_cache: Dict[Tuple[float, float], float] = {}
        self._lst_cache: Dict[Tuple[float, float], float] = {}
        self._green_cache: Dict[Tuple[float, float], float] = {}
        self._additional_range_cache: Dict[str, Tuple[float, float]] = {}

    def set_additional_layers(self, layers: Sequence[Any]) -> None:
        """Replace the unlimited MCDA raster stack without rebuilding the sampler."""
        self.additional_layers = [layer for layer in layers if layer is not None]
        self._additional_range_cache.clear()

    def sample_elevation(self, lon: float, lat: float) -> float:
        """Sample elevation in meters at given WGS84 coordinate."""
        if not math.isfinite(lon) or not math.isfinite(lat):
            return 0.0

        coord_key = (round(lon, 5), round(lat, 5))
        if coord_key in self._dem_cache:
            return self._dem_cache[coord_key]

        elevation = 0.0

        for dem_layer in self.dem_layers:
            with contextlib.suppress(Exception):
                from qgis.core import (
                    QgsCoordinateReferenceSystem,
                    QgsCoordinateTransform,
                    QgsPointXY,
                    QgsProject,
                )

                pt = QgsPointXY(lon, lat)
                crs_src = QgsCoordinateReferenceSystem("EPSG:4326")
                crs_dest = dem_layer.crs()
                if crs_src != crs_dest:
                    transform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
                    pt = transform.transform(pt)

                val, success = dem_layer.dataProvider().sample(pt, 1)
                if success and val is not None and math.isfinite(val) and val > -9999:
                    elevation = float(val)
                    self._dem_cache[coord_key] = elevation
                    return elevation

        # Fast zero-latency cached elevation.  A missing DEM is represented by
        # zero and must not be mistaken for a generated terrain surface.
        from .dem_fetcher import GlobalDemFetcher

        elevation = GlobalDemFetcher.get_fast_elevation(lon, lat)
        if not math.isfinite(elevation):
            elevation = 0.0
        self._dem_cache[coord_key] = elevation
        return elevation

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

        Returns None when no LST raster is configured or the point cannot be
        sampled. Callers must treat None as "no data" and drop the criterion --
        never as an average value, which would fabricate a thermal surface.
        """
        if not math.isfinite(lon) or not math.isfinite(lat):
            return None

        coord_key = (round(lon, 5), round(lat, 5))
        if coord_key in self._lst_cache:
            return self._lst_cache[coord_key]

        if self.lst_layer is not None:
            with contextlib.suppress(Exception):
                from qgis.core import (
                    QgsCoordinateReferenceSystem,
                    QgsCoordinateTransform,
                    QgsPointXY,
                    QgsProject,
                )

                pt = QgsPointXY(lon, lat)
                crs_src = QgsCoordinateReferenceSystem("EPSG:4326")
                crs_dest = self.lst_layer.crs()
                if crs_src != crs_dest:
                    transform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
                    pt = transform.transform(pt)

                val, success = self.lst_layer.dataProvider().sample(pt, 1)
                if success and val is not None and math.isfinite(val):
                    normalized = (float(val) - 20.0) / 30.0
                    normalized = max(0.0, min(1.0, normalized))
                    self._lst_cache[coord_key] = normalized
                    return normalized
        self._lst_cache[coord_key] = None
        return None

    def sample_greenery(self, lon: float, lat: float) -> Optional[float]:
        """Sample green tree canopy / NDVI (0.0 = bare/concrete, 1.0 = lush canopy).

        Returns None when no greenery raster is configured -- see sample_lst.
        """
        if not math.isfinite(lon) or not math.isfinite(lat):
            return None

        coord_key = (round(lon, 5), round(lat, 5))
        if coord_key in self._green_cache:
            return self._green_cache[coord_key]

        if self.green_layer is not None:
            with contextlib.suppress(Exception):
                from qgis.core import (
                    QgsCoordinateReferenceSystem,
                    QgsCoordinateTransform,
                    QgsPointXY,
                    QgsProject,
                )

                pt = QgsPointXY(lon, lat)
                crs_src = QgsCoordinateReferenceSystem("EPSG:4326")
                crs_dest = self.green_layer.crs()
                if crs_src != crs_dest:
                    transform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
                    pt = transform.transform(pt)

                val, success = self.green_layer.dataProvider().sample(pt, 1)
                if success and val is not None and math.isfinite(val):
                    normalized = max(0.0, min(1.0, float(val)))
                    self._green_cache[coord_key] = normalized
                    return normalized
        self._green_cache[coord_key] = None
        return None

    def _additional_layer_range(self, layer: Any) -> Optional[Tuple[float, float]]:
        """Read a raster's real min/max statistics once for normalization."""
        try:
            layer_id = str(layer.id())
        except Exception:
            layer_id = str(id(layer))
        if layer_id in self._additional_range_cache:
            return self._additional_range_cache[layer_id]
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
            with contextlib.suppress(Exception):
                from qgis.core import (
                    QgsCoordinateReferenceSystem,
                    QgsCoordinateTransform,
                    QgsPointXY,
                    QgsProject,
                )

                point = QgsPointXY(lon, lat)
                source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                layer_crs = layer.crs()
                if source_crs != layer_crs:
                    transform = QgsCoordinateTransform(source_crs, layer_crs, QgsProject.instance())
                    point = transform.transform(point)
                raw_value, success = layer.dataProvider().sample(point, 1)
                if (
                    not success
                    or raw_value is None
                    or not math.isfinite(raw_value)
                    or raw_value <= -9999
                ):
                    continue
                value_range = self._additional_layer_range(layer)
                if value_range is None:
                    continue
                minimum, maximum = value_range
                values.append(
                    max(0.0, min(1.0, (float(raw_value) - minimum) / (maximum - minimum)))
                )
        return values
