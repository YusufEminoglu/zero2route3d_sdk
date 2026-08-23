"""Public Copernicus DEM GLO-30 tile URL and extent helpers."""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple


class CopernicusDemError(ValueError):
    """Raised when a Copernicus DEM request extent is invalid or too large."""


class CopernicusDemTileSource:
    """Build URLs for the public one-degree Copernicus DEM COG tiles."""

    BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"

    @classmethod
    def tile_id(cls, lon: float, lat: float) -> str:
        try:
            lon_value = float(lon)
            lat_value = float(lat)
        except (TypeError, ValueError, OverflowError) as exc:
            raise CopernicusDemError("Copernicus tile coordinates must be numeric.") from exc
        if not (math.isfinite(lon_value) and math.isfinite(lat_value)):
            raise CopernicusDemError("Copernicus tile coordinates must be finite.")
        if not (-180.0 <= lon_value <= 180.0 and -90.0 <= lat_value <= 90.0):
            raise CopernicusDemError("Copernicus tile coordinates are outside WGS84 bounds.")

        lat_index = math.floor(lat_value)
        lon_index = math.floor(lon_value)
        north_south = "N" if lat_index >= 0 else "S"
        east_west = "E" if lon_index >= 0 else "W"
        return f"{north_south}{abs(lat_index):02d}_00_{east_west}{abs(lon_index):03d}_00"

    @classmethod
    def tile_url(cls, lon: float, lat: float) -> str:
        tile = cls.tile_id(lon, lat)
        prefix = f"Copernicus_DSM_COG_10_{tile}_DEM"
        return f"{cls.BASE_URL}/{prefix}/{prefix}.tif"

    @classmethod
    def tiles_for_bbox(
        cls,
        bbox: Sequence[float],
        max_tiles: int = 16,
    ) -> List[Tuple[int, int, str]]:
        if not bbox or len(bbox) < 4:
            raise CopernicusDemError("A four-coordinate extent is required for Copernicus DEM.")
        min_lon, min_lat, max_lon, max_lat = (float(value) for value in bbox[:4])
        if not all(math.isfinite(value) for value in (min_lon, min_lat, max_lon, max_lat)):
            raise CopernicusDemError("The Copernicus DEM extent contains invalid coordinates.")
        if min_lon > max_lon:
            min_lon, max_lon = max_lon, min_lon
        if min_lat > max_lat:
            min_lat, max_lat = max_lat, min_lat
        min_lon = max(-180.0, min(180.0, min_lon))
        max_lon = max(-180.0, min(180.0, max_lon))
        min_lat = max(-90.0, min(90.0, min_lat))
        max_lat = max(-90.0, min(90.0, max_lat))

        lon_start = math.floor(min_lon)
        lon_end = math.floor(max_lon if max_lon < 180.0 else 179.999999)
        lat_start = math.floor(min_lat)
        lat_end = math.floor(max_lat if max_lat < 90.0 else 89.999999)
        tiles = []
        for lat_index in range(lat_start, lat_end + 1):
            for lon_index in range(lon_start, lon_end + 1):
                url = cls.tile_url(lon_index + 0.1, lat_index + 0.1)
                tiles.append((lon_index, lat_index, url))
        if len(tiles) > max(1, int(max_tiles)):
            raise CopernicusDemError(
                f"The extent spans {len(tiles)} Copernicus DEM tiles; zoom to a smaller area "
                f"(maximum {max_tiles})."
            )
        return tiles
