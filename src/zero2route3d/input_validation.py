"""Small, dependency-free validation helpers shared by routing workflows."""

from __future__ import annotations

import math
from typing import Any, Iterable, List, Optional, Sequence, Tuple


def finite_number(value: Any, default: float = 0.0) -> float:
    """Return a finite float or a safe default."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def normalize_bbox(
    bbox: Sequence[Any],
    minimum_span: float = 0.005,
) -> Tuple[float, float, float, float]:
    """Validate and normalize ``(min_lon, min_lat, max_lon, max_lat)``."""
    if not bbox or len(bbox) < 4:
        raise ValueError("A bounding box needs four coordinates.")
    values = [finite_number(value, float("nan")) for value in bbox[:4]]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("The bounding box contains invalid coordinates.")
    min_lon, min_lat, max_lon, max_lat = values
    if not (-180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0):
        raise ValueError("Longitude must be between -180 and 180 degrees.")
    if not (-90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
        raise ValueError("Latitude must be between -90 and 90 degrees.")
    if min_lon > max_lon:
        min_lon, max_lon = max_lon, min_lon
    if min_lat > max_lat:
        min_lat, max_lat = max_lat, min_lat
    span = max(0.0001, finite_number(minimum_span, 0.005))
    if max_lon - min_lon < span:
        center = (min_lon + max_lon) / 2.0
        min_lon, max_lon = center - span / 2.0, center + span / 2.0
    if max_lat - min_lat < span:
        center = (min_lat + max_lat) / 2.0
        min_lat, max_lat = center - span / 2.0, center + span / 2.0
    return min_lon, min_lat, max_lon, max_lat


def normalize_time_intervals(
    intervals: Iterable[Any],
    max_intervals: int = 12,
    max_minutes: float = 24.0 * 60.0,
) -> List[float]:
    """Return sorted, unique, positive time cutoffs within a safe bound."""
    cleaned = {
        round(value, 3)
        for raw in intervals
        for value in [finite_number(raw, -1.0)]
        if 0.0 < value <= max_minutes
    }
    return sorted(cleaned)[: max(1, int(max_intervals))]


def validate_waypoint_coordinates(waypoints: Sequence[Any]) -> Optional[str]:
    """Validate waypoint count and WGS84 coordinate ranges."""
    if not waypoints:
        return "At least two waypoints are required."
    if len(waypoints) > 500:
        return "A route can contain at most 500 waypoints."
    for index, waypoint in enumerate(waypoints, start=1):
        lon = finite_number(getattr(waypoint, "lon", float("nan")), float("nan"))
        lat = finite_number(getattr(waypoint, "lat", float("nan")), float("nan"))
        if not (math.isfinite(lon) and math.isfinite(lat)):
            return f"Waypoint {index} has invalid coordinates."
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            return f"Waypoint {index} is outside the WGS84 coordinate range."
    return None


def deduplicate_adjacent_coordinates(
    coords: Sequence[Sequence[float]],
    tolerance_m: float = 0.05,
) -> List[Tuple[float, float, float]]:
    """Remove consecutive coordinates that represent the same map position."""
    from .kinematics import haversine_distance_2d

    result: List[Tuple[float, float, float]] = []
    tolerance = max(0.0, finite_number(tolerance_m, 0.05))
    for coord in coords:
        if not coord or len(coord) < 2:
            continue
        lon = finite_number(coord[0], float("nan"))
        lat = finite_number(coord[1], float("nan"))
        if not (math.isfinite(lon) and math.isfinite(lat)):
            continue
        z = finite_number(coord[2], 0.0) if len(coord) > 2 else 0.0
        point = (lon, lat, z)
        if not result or haversine_distance_2d(result[-1], point) > tolerance:
            result.append(point)
        elif abs(z - result[-1][2]) > 0.01:
            result[-1] = point
    return result
