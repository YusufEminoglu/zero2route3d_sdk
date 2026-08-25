"""Headless GeoTIFF point sampling for DEM, LST and greenery rasters.

QGIS raster layers are only available inside QGIS. This module gives the SDK an
equivalent, QGIS-free source backed by ``rasterio``, so a plain
``EnvironmentalSurfaceSampler(dem="dem.tif")`` samples real terrain in a script,
a notebook or a container.

Coordinates are always supplied in WGS84 (EPSG:4326) and reprojected into the
raster's own CRS before reading, so a UTM or national-grid GeoTIFF works without
the caller having to convert anything.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

__all__ = ["GeoTiffRasterSource", "RasterSourceError", "open_raster_source"]


class RasterSourceError(RuntimeError):
    """Raised when a raster file cannot be opened or sampled."""


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


class GeoTiffRasterSource:
    """Lazily opened, reprojecting point sampler for a single-band raster file.

    The dataset handle is opened on first use and held open for the lifetime of
    the object, so repeated sampling inside a routing loop does not pay the file
    open cost every time. Call :meth:`close` (or use it as a context manager) to
    release the handle.
    """

    def __init__(
        self,
        path: Union[str, Path],
        band: int = 1,
        nodata: Optional[float] = None,
    ) -> None:
        self.path = Path(path)
        self.band = max(1, int(band))
        self._explicit_nodata = _finite(nodata)
        self._dataset: Any = None
        self._closed = False
        self._transformer: Any = None
        self._needs_reprojection: Optional[bool] = None
        self._value_range: Optional[Tuple[float, float]] = None

    # -- lifecycle ---------------------------------------------------------

    def _open(self) -> Any:
        if self._dataset is not None:
            return self._dataset
        if self._closed:
            raise RasterSourceError(f"Raster source for '{self.path}' is already closed.")
        try:
            import rasterio
        except ImportError as exc:  # pragma: no cover - depends on the install extras
            raise RasterSourceError(
                "rasterio is required to sample GeoTIFF rasters. "
                "Install it with 'pip install zero2route3d-sdk[geo]'."
            ) from exc

        if not self.path.exists():
            raise RasterSourceError(f"Raster file not found: {self.path}")

        try:
            self._dataset = rasterio.open(str(self.path))
        except Exception as exc:
            raise RasterSourceError(f"Could not open raster '{self.path}': {exc}") from exc

        if self.band > self._dataset.count:
            count = self._dataset.count
            self.close()
            raise RasterSourceError(
                f"Raster '{self.path}' has {count} band(s); band {self.band} was requested."
            )
        return self._dataset

    def close(self) -> None:
        """Release the underlying dataset handle."""
        if self._dataset is not None:
            try:
                self._dataset.close()
            except Exception:
                pass
        self._dataset = None
        self._closed = True

    def __enter__(self) -> GeoTiffRasterSource:
        self._open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"GeoTiffRasterSource(path={str(self.path)!r}, band={self.band})"

    # -- coordinates -------------------------------------------------------

    def _to_raster_crs(self, coords: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
        dataset = self._open()
        if self._needs_reprojection is None:
            crs = dataset.crs
            self._needs_reprojection = bool(crs) and crs.to_epsg() != 4326
        if not self._needs_reprojection:
            return [(float(lon), float(lat)) for lon, lat in coords]

        from rasterio.warp import transform as warp_transform

        xs = [float(lon) for lon, _lat in coords]
        ys = [float(lat) for _lon, lat in coords]
        out_xs, out_ys = warp_transform("EPSG:4326", dataset.crs, xs, ys)
        return list(zip(out_xs, out_ys))

    # -- sampling ----------------------------------------------------------

    def sample(self, lon: float, lat: float) -> Optional[float]:
        """Return the raster value at a WGS84 coordinate, or None outside coverage."""
        return self.sample_many([(lon, lat)])[0]

    def sample_many(self, coords: Iterable[Tuple[float, float]]) -> List[Optional[float]]:
        """Sample many WGS84 coordinates in one pass; None marks NoData or out-of-bounds."""
        # `coords` may be a generator, so materialize it before sizing the result.
        requested = list(coords)
        results: List[Optional[float]] = [None] * len(requested)

        pairs: List[Tuple[float, float]] = []
        valid_slots: List[int] = []
        for idx, pt in enumerate(requested):
            lon = _finite(pt[0]) if pt is not None and len(pt) >= 2 else None
            lat = _finite(pt[1]) if pt is not None and len(pt) >= 2 else None
            if lon is None or lat is None:
                continue
            pairs.append((lon, lat))
            valid_slots.append(idx)

        if not pairs:
            return results

        dataset = self._open()
        nodata = self._explicit_nodata
        if nodata is None:
            nodata = _finite(dataset.nodata)

        projected = self._to_raster_crs(pairs)
        try:
            samples = dataset.sample(projected, indexes=self.band)
            for slot, value in zip(valid_slots, samples):
                number = _finite(value[0] if hasattr(value, "__len__") else value)
                if number is None:
                    continue
                if nodata is not None and math.isclose(number, nodata, rel_tol=0.0, abs_tol=1e-6):
                    continue
                results[slot] = number
        except Exception as exc:
            raise RasterSourceError(f"Could not sample raster '{self.path}': {exc}") from exc
        return results

    def value_range(self) -> Optional[Tuple[float, float]]:
        """Real (min, max) of the band, read once and cached, for normalization."""
        if self._value_range is not None:
            return self._value_range
        dataset = self._open()
        try:
            import numpy as np

            data = dataset.read(self.band, masked=True)
            if data.count() == 0:
                return None
            minimum = float(np.min(data))
            maximum = float(np.max(data))
        except Exception:
            return None
        if not (math.isfinite(minimum) and math.isfinite(maximum)) or maximum <= minimum:
            return None
        self._value_range = (minimum, maximum)
        return self._value_range


def open_raster_source(
    source: Union[str, Path, GeoTiffRasterSource, None],
    band: int = 1,
) -> Optional[GeoTiffRasterSource]:
    """Coerce a path (or an existing source) into a :class:`GeoTiffRasterSource`.

    Returns None for None, and passes non-path objects (e.g. QGIS raster layers)
    straight through as None so callers can fall back to their own handling.
    """
    if source is None:
        return None
    if isinstance(source, GeoTiffRasterSource):
        return source
    if isinstance(source, (str, Path)):
        return GeoTiffRasterSource(source, band=band)
    return None
