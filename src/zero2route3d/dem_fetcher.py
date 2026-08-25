"""Global Digital Elevation Model (DEM) acquisition & real-world elevation sampler.

Provides automated fetching from the Open-Elevation API with local disk caching.
When the service is unavailable, unresolved values remain marked as missing
instead of being replaced with invented topography.
"""

from __future__ import annotations

import contextlib
import json
import math
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Raster NoData value. Distinct from 0.0, which is a legal elevation: filling
# unresolved samples with zero produces a flat sea-level plateau that downstream
# slope code cannot tell apart from real terrain.
NODATA = -9999.0


class GlobalDemFetcher:
    """Acquires and caches real elevation samples from the Open-Elevation API.

    The service (https://open-elevation.com) is the only elevation source used
    here. No Copernicus or SRTM product is queried directly.
    """

    _CACHE_FILE = Path(tempfile.gettempdir()) / "zero2route3d_cache" / "elevation_cache.json"
    _MEMORY_CACHE: Dict[str, float] = {}
    _MAX_CACHE_ENTRIES = 20_000
    _DISK_CACHE_LOADED = False

    @classmethod
    def _cache_key(cls, lon: float, lat: float) -> str:
        return f"{round(lon, 5):.5f},{round(lat, 5):.5f}"

    @classmethod
    def _load_disk_cache(cls) -> None:
        if cls._DISK_CACHE_LOADED:
            return
        cls._DISK_CACHE_LOADED = True
        if not cls._CACHE_FILE.exists():
            return
        with contextlib.suppress(Exception):
            data = json.loads(cls._CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    try:
                        val = float(v)
                    except (ValueError, TypeError):
                        continue
                    if math.isfinite(val):
                        cls._MEMORY_CACHE[str(k)] = val

    @classmethod
    def _save_disk_cache(cls) -> None:
        with contextlib.suppress(Exception):
            if len(cls._MEMORY_CACHE) > cls._MAX_CACHE_ENTRIES:
                keep = list(cls._MEMORY_CACHE.items())[-cls._MAX_CACHE_ENTRIES :]
                cls._MEMORY_CACHE = dict(keep)
            cls._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_file = cls._CACHE_FILE.with_suffix(".tmp")
            temp_file.write_text(json.dumps(cls._MEMORY_CACHE, indent=2), encoding="utf-8")
            temp_file.replace(cls._CACHE_FILE)

    @classmethod
    def clear_cache(cls, remove_disk_file: bool = False) -> None:
        """Drop every cached elevation sample; optionally delete the on-disk cache too."""
        cls._MEMORY_CACHE = {}
        cls._DISK_CACHE_LOADED = False
        if remove_disk_file:
            with contextlib.suppress(Exception):
                cls._CACHE_FILE.unlink()

    @classmethod
    def cached_sample_count(cls) -> int:
        """Number of elevation samples currently held in memory."""
        cls._load_disk_cache()
        return len(cls._MEMORY_CACHE)

    @classmethod
    def seed_cache(cls, samples: Dict[Tuple[float, float], float]) -> int:
        """Pre-populate the cache with known ``(lon, lat) -> elevation_m`` samples.

        Useful for offline and reproducible runs: seeded points are then served by
        :meth:`get_fast_elevation` without any network access. Returns the number
        of samples accepted.
        """
        cls._load_disk_cache()
        accepted = 0
        for coord, value in samples.items():
            try:
                lon, lat, elevation = float(coord[0]), float(coord[1]), float(value)
            except (TypeError, ValueError, IndexError, OverflowError):
                continue
            if not (math.isfinite(lon) and math.isfinite(lat) and math.isfinite(elevation)):
                continue
            cls._MEMORY_CACHE[cls._cache_key(lon, lat)] = elevation
            accepted += 1
        return accepted

    @classmethod
    def fetch_elevations_for_coords(
        cls, coords: Sequence[Tuple[float, float]], timeout_sec: float = 3.0
    ) -> List[Optional[float]]:
        """Fetch real elevations in metres for a sequence of (lon, lat) WGS84 points.

        Every input gets exactly one output slot. A slot is None when the elevation
        could not be resolved -- 0.0 is a real elevation and must never stand in for
        a failed lookup.
        """
        cls._load_disk_cache()
        results: List[Optional[float]] = [None] * len(coords)
        missing_pairs: List[Tuple[int, float, float]] = []

        for idx, pt in enumerate(coords):
            if not pt or len(pt) < 2:
                continue
            try:
                lon, lat = float(pt[0]), float(pt[1])
            except (TypeError, ValueError, OverflowError):
                continue
            if not math.isfinite(lon) or not math.isfinite(lat):
                continue

            key = cls._cache_key(lon, lat)
            if key in cls._MEMORY_CACHE:
                results[idx] = cls._MEMORY_CACHE[key]
            else:
                missing_pairs.append((idx, lon, lat))

        if not missing_pairs:
            return results

        # Batch fetch from the Open-Elevation API in chunks of up to 150 items.
        chunk_size = 150
        timeout_val = (
            max(1.0, float(timeout_sec)) if math.isfinite(timeout_sec) and timeout_sec > 0 else 3.0
        )
        any_success = False

        for i in range(0, len(missing_pairs), chunk_size):
            chunk = missing_pairs[i : i + chunk_size]
            chunk_locations = [
                {"latitude": round(lat, 6), "longitude": round(lon, 6)} for _, lon, lat in chunk
            ]

            try:
                import http.client

                payload = json.dumps({"locations": chunk_locations})
                conn = http.client.HTTPSConnection("api.open-elevation.com", timeout=timeout_val)
                try:
                    headers = {
                        "Content-Type": "application/json",
                        "User-Agent": "zero2route3d-sdk",
                    }
                    conn.request("POST", "/api/v1/lookup", body=payload, headers=headers)
                    resp = conn.getresponse()
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        ele_list = data.get("results", [])
                        if len(ele_list) == len(chunk):
                            parsed_values: List[float] = []
                            for item in ele_list:
                                if not isinstance(item, dict) or "elevation" not in item:
                                    break
                                try:
                                    ele_val = float(item["elevation"])
                                except (TypeError, ValueError, OverflowError):
                                    break
                                if not math.isfinite(ele_val):
                                    break
                                parsed_values.append(ele_val)
                            if len(parsed_values) == len(chunk):
                                for (m_idx, lon_val, lat_val), ele_val in zip(chunk, parsed_values):
                                    results[m_idx] = ele_val
                                    cls._MEMORY_CACHE[cls._cache_key(lon_val, lat_val)] = ele_val
                                any_success = True
                finally:
                    conn.close()
            except Exception:
                # Unresolved coordinates keep their None slot. Never synthesize
                # terrain from coordinate math, and never fall back to 0.0 --
                # which is a real elevation somewhere.
                continue

        if any_success:
            cls._save_disk_cache()

        return results

    @classmethod
    def get_fast_elevation(cls, lon: float, lat: float) -> Optional[float]:
        """Elevation for a coordinate from the cache only, or None if unknown.

        Returns None rather than 0.0 so that "no elevation data here" stays
        distinguishable from "this point is at sea level". Never touches the
        network, so it is safe to call inside a routing hot loop.
        """
        if not math.isfinite(lon) or not math.isfinite(lat):
            return None
        cls._load_disk_cache()
        return cls._MEMORY_CACHE.get(cls._cache_key(lon, lat))

    @classmethod
    def get_elevation_single(
        cls, lon: float, lat: float, timeout_sec: float = 3.0
    ) -> Optional[float]:
        """Elevation for one coordinate, querying Open-Elevation on a cache miss.

        Returns None when the point cannot be resolved. Prefer
        :meth:`fetch_elevations_for_coords` for more than a handful of points --
        it batches them into a single request.
        """
        if not math.isfinite(lon) or not math.isfinite(lat):
            return None
        cached = cls.get_fast_elevation(lon, lat)
        if cached is not None:
            return cached
        return cls.fetch_elevations_for_coords([(lon, lat)], timeout_sec=timeout_sec)[0]
