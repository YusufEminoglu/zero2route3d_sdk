"""Solar position, dynamic shadow casting, and shade exposure along 3D route."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

from .kinematics import haversine_distance_2d


@dataclass
class SolarPosition:
    """Calculated solar azimuth and elevation angles."""

    solar_hour: float  # 0.0 to 24.0 (e.g. 14.5 = 14:30)
    azimuth_deg: float  # 0=North, 90=East, 180=South, 270=West
    elevation_deg: float  # 0=Horizon, 90=Zenith
    direct_irradiance_w_m2: float


@dataclass
class ShadeExposureReport:
    """Detailed solar exposure metrics along a 3D path."""

    solar_position: SolarPosition
    direct_sun_pct: float
    shaded_pct: float
    total_solar_exposure_kwh: float
    comfort_category: str  # 'Cool & Shaded', 'Balanced', 'Intense Sun'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "solar_hour": self.solar_position.solar_hour,
            "azimuth_deg": round(self.solar_position.azimuth_deg, 1),
            "elevation_deg": round(self.solar_position.elevation_deg, 1),
            "direct_sun_pct": round(self.direct_sun_pct, 1),
            "shaded_pct": round(self.shaded_pct, 1),
            "total_solar_exposure_kwh": round(self.total_solar_exposure_kwh, 2),
            "comfort_category": self.comfort_category,
        }


def calculate_solar_position(
    lat_deg: float,
    solar_hour: float = 13.0,
    day_of_year: int = 172,  # Summer solstice ~ June 21
) -> SolarPosition:
    """Compute solar azimuth and elevation angle based on latitude and hour of day."""
    # Solar declination angle
    declination_deg = 23.45 * math.sin(math.radians((360.0 / 365.0) * (284 + day_of_year)))
    dec_rad = math.radians(declination_deg)
    lat_rad = math.radians(lat_deg)

    # Hour angle (15 deg per hour from solar noon at 12:00)
    hour_angle_deg = (solar_hour - 12.0) * 15.0
    h_rad = math.radians(hour_angle_deg)

    # Solar elevation angle
    sin_el = math.sin(lat_rad) * math.sin(dec_rad) + math.cos(lat_rad) * math.cos(
        dec_rad
    ) * math.cos(h_rad)
    sin_el = max(-1.0, min(1.0, sin_el))
    elevation_rad = math.asin(sin_el)
    elevation_deg = math.degrees(elevation_rad)

    # Solar azimuth angle
    if elevation_deg > 0:
        cos_az = (math.sin(dec_rad) - math.sin(lat_rad) * math.sin(elevation_rad)) / max(
            0.001, math.cos(lat_rad) * math.cos(elevation_rad)
        )
        cos_az = max(-1.0, min(1.0, cos_az))
        azimuth_rad = math.acos(cos_az)
        azimuth_deg = math.degrees(azimuth_rad)
        if hour_angle_deg > 0:
            azimuth_deg = 360.0 - azimuth_deg
    else:
        elevation_deg = 0.0
        azimuth_deg = 180.0

    # Solar direct beam irradiance model
    irradiance = 1000.0 * math.sin(math.radians(elevation_deg)) if elevation_deg > 0 else 0.0

    return SolarPosition(
        solar_hour=solar_hour,
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        direct_irradiance_w_m2=max(0.0, irradiance),
    )


def compute_shade_exposure_along_route(
    coords_3d: Sequence[Tuple[float, float, float]],
    solar_hour: float = 14.0,
    building_density_factor: float = 0.6,
) -> ShadeExposureReport:
    """Analyze the proportion of shade vs direct sun along a 3D path at a given time of day."""
    if not coords_3d:
        sun = calculate_solar_position(38.4, solar_hour)
        return ShadeExposureReport(sun, 0.0, 100.0, 0.0, "Shaded")

    mean_lat = sum(c[1] for c in coords_3d) / len(coords_3d)
    sun = calculate_solar_position(mean_lat, solar_hour=solar_hour)

    if sun.elevation_deg <= 0:
        return ShadeExposureReport(sun, 0.0, 100.0, 0.0, "Night / Twilight")

    sun_rad = math.radians(sun.azimuth_deg)
    sun_el_rad = math.radians(sun.elevation_deg)
    sun_shadow_len_factor = 1.0 / max(0.1, math.tan(sun_el_rad))

    sunlit_length = 0.0
    shaded_length = 0.0

    for i in range(len(coords_3d) - 1):
        p1 = coords_3d[i]
        p2 = coords_3d[i + 1]
        seg_len = haversine_distance_2d(p1, p2)

        # Orientation angle of street segment
        dx = (p2[0] - p1[0]) * math.cos(math.radians((p1[1] + p2[1]) * 0.5))
        dy = p2[1] - p1[1]
        street_bearing = math.atan2(dx, dy)

        # Angle between sun ray and street orientation
        angle_diff = abs(street_bearing - sun_rad) % (math.pi / 2.0)
        canyon_shading_prob = (
            math.sin(angle_diff) * building_density_factor * min(1.0, sun_shadow_len_factor * 0.35)
        )

        if canyon_shading_prob > 0.45:
            shaded_length += seg_len
        else:
            sunlit_length += seg_len

    tot = sunlit_length + shaded_length
    sun_pct = (sunlit_length / tot * 100.0) if tot > 0 else 50.0
    shade_pct = (shaded_length / tot * 100.0) if tot > 0 else 50.0

    # Solar kWh exposure (assuming standard walking pace ~ 12 min/km)
    hours_exposure = (tot / 1000.0) * 0.20
    kwh = (sun.direct_irradiance_w_m2 * (sun_pct / 100.0) * hours_exposure) / 1000.0

    if shade_pct > 65.0:
        category = "Cool & Shaded (High Comfort)"
    elif shade_pct > 35.0:
        category = "Balanced Sun & Shade"
    else:
        category = "Intense Sun (High Thermal Strain)"

    return ShadeExposureReport(
        solar_position=sun,
        direct_sun_pct=sun_pct,
        shaded_pct=shade_pct,
        total_solar_exposure_kwh=kwh,
        comfort_category=category,
    )
