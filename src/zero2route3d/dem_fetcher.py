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
from typing import Dict, List, Sequence, Tuple


class GlobalDemFetcher:
    """Acquires and caches real-world 30m Copernicus/SRTM topography for coordinates."""

    _CACHE_FILE = Path(tempfile.gettempdir()) / "zero2route3d_cache" / "elevation_cache.json"
    _MEMORY_CACHE: Dict[str, float] = {}
    _MAX_CACHE_ENTRIES = 20_000

    @classmethod
    def _load_disk_cache(cls) -> None:
        if not cls._MEMORY_CACHE and cls._CACHE_FILE.exists():
            with contextlib.suppress(Exception):
                text = cls._CACHE_FILE.read_text(encoding="utf-8")
                data = json.loads(text)
                if isinstance(data, dict):
                    for k, v in data.items():
                        try:
                            val = float(v)
                            if math.isfinite(val):
                                cls._MEMORY_CACHE[str(k)] = val
                        except (ValueError, TypeError):
                            continue

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
    def fetch_elevations_for_coords(
        cls, coords: Sequence[Tuple[float, float]], timeout_sec: float = 3.0
    ) -> List[float]:
        """Fetch real elevations in meters for a sequence of (lon, lat) WGS84 points."""
        cls._load_disk_cache()
        results: List[float] = [0.0] * len(coords)
        missing_pairs: List[Tuple[int, float, float]] = []

        for idx, pt in enumerate(coords):
            if not pt or len(pt) < 2:
                results[idx] = 0.0
                continue
            lon, lat = float(pt[0]), float(pt[1])
            if not math.isfinite(lon) or not math.isfinite(lat):
                results[idx] = 0.0
                continue

            key = f"{round(lon, 5):.5f},{round(lat, 5):.5f}"
            if key in cls._MEMORY_CACHE:
                results[idx] = cls._MEMORY_CACHE[key]
            else:
                missing_pairs.append((idx, lon, lat))

        if missing_pairs:
            # Batch fetch from Open-Elevation API in chunks of up to 150 items
            chunk_size = 150
            timeout_val = (
                max(1.0, float(timeout_sec))
                if math.isfinite(timeout_sec) and timeout_sec > 0
                else 3.0
            )
            unresolved_indices: List[Tuple[int, float, float]] = []
            any_success = False

            for i in range(0, len(missing_pairs), chunk_size):
                chunk = missing_pairs[i : i + chunk_size]
                chunk_locations = [
                    {"latitude": round(lat, 6), "longitude": round(lon, 6)} for _, lon, lat in chunk
                ]
                success_chunk = False

                try:
                    import http.client

                    payload = json.dumps({"locations": chunk_locations})
                    conn = http.client.HTTPSConnection(
                        "api.open-elevation.com", timeout=timeout_val
                    )
                    try:
                        headers = {
                            "Content-Type": "application/json",
                            "User-Agent": "02Route3D-QGIS",
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
                                    for (m_idx, lon_val, lat_val), ele_val in zip(
                                        chunk, parsed_values
                                    ):
                                        results[m_idx] = ele_val
                                        key = f"{round(lon_val, 5):.5f},{round(lat_val, 5):.5f}"
                                        cls._MEMORY_CACHE[key] = ele_val
                                    success_chunk = True
                                    any_success = True
                    finally:
                        conn.close()
                except Exception:
                    success_chunk = False

                if not success_chunk:
                    unresolved_indices.extend(chunk)

            if any_success:
                cls._save_disk_cache()

            # Keep unresolved coordinates at the explicit missing-value
            # sentinel.  Never synthesize terrain from coordinate math.
            if unresolved_indices:
                for m_idx, _lon_val, _lat_val in unresolved_indices:
                    results[m_idx] = 0.0

        return results

    @classmethod
    def get_fast_elevation(cls, lon: float, lat: float) -> float:
        """Instant zero-latency elevation query using only the real cache."""
        if not math.isfinite(lon) or not math.isfinite(lat):
            return 0.0
        cls._load_disk_cache()
        key = f"{round(lon, 5):.5f},{round(lat, 5):.5f}"
        if key in cls._MEMORY_CACHE:
            return cls._MEMORY_CACHE[key]
        return 0.0

    @classmethod
    def get_elevation_single(cls, lon: float, lat: float) -> float:
        """Sample or query elevation for a single coordinate."""
        if not math.isfinite(lon) or not math.isfinite(lat):
            return 0.0
        cls._load_disk_cache()
        key = f"{round(lon, 5):.5f},{round(lat, 5):.5f}"
        if key in cls._MEMORY_CACHE:
            return cls._MEMORY_CACHE[key]

        return cls.get_fast_elevation(lon, lat)
