"""Biomechanical, vehicle, and microclimate kinematic models for 3D route analysis.

Includes:
- Geodesic 3D distance with elevation delta
- Tobler's Hiking Function for slope-aware pedestrian velocity
- Minetti (2002) metabolic energy expenditure equation
- Aerodynamic drag & wind resistance equations
- Surface rolling resistance coefficients (C_rr)
- Senior fatigue and metabolic degradation over distance
- Solar aspect and dynamic sun angle irradiance model
- UTCI-equivalent thermal comfort and heat stress formulas
- Cyclist climbing power and grade resistance curves
- E-Scooter traction and battery drain models
- Road hierarchy vehicle speed modeling
- AnimatedAvatar for multi-modal simulation interpolation
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class AnimatedAvatar:
    """State and precomputed kinematics for a single moving profile on canvas."""

    profile_key: str
    profile_name: str
    color_hex: str
    coordinates_3d: List[Tuple[float, float, float]]
    cumulative_distances_m: List[float] = field(default_factory=list)
    timestamps_s: List[float] = field(default_factory=list)
    total_duration_s: float = 0.0
    total_distance_m: float = 0.0
    marker: Optional[Any] = None

    def interpolate_position(self, target_time_s: float) -> Tuple[float, float, float]:
        """Interpolate (lon, lat, elevation) at given elapsed simulation time."""
        if not self.coordinates_3d:
            return 0.0, 0.0, 0.0
        if (
            not math.isfinite(target_time_s)
            or target_time_s <= 0.0
            or len(self.coordinates_3d) == 1
        ):
            return self.coordinates_3d[0]
        if target_time_s >= self.total_duration_s:
            return self.coordinates_3d[-1]

        if not self.timestamps_s or len(self.timestamps_s) < len(self.coordinates_3d):
            return self.coordinates_3d[0]

        # Binary search for interval
        idx = bisect.bisect_right(self.timestamps_s, target_time_s)
        if idx <= 0:
            return self.coordinates_3d[0]
        if idx >= len(self.coordinates_3d):
            return self.coordinates_3d[-1]

        t0 = self.timestamps_s[idx - 1]
        t1 = self.timestamps_s[idx]
        dt = t1 - t0
        alpha = (target_time_s - t0) / dt if dt > 1e-6 else 0.0
        alpha = max(0.0, min(1.0, alpha))

        p0 = self.coordinates_3d[idx - 1]
        p1 = self.coordinates_3d[idx]

        lon = p0[0] + alpha * (p1[0] - p0[0])
        lat = p0[1] + alpha * (p1[1] - p0[1])
        ele = p0[2] + alpha * (p1[2] - p0[2])
        return lon, lat, ele


# Surface rolling resistance coefficients (C_rr)
ROLLING_RESISTANCE: Dict[str, float] = {
    "asphalt": 0.004,
    "concrete": 0.005,
    "paved": 0.006,
    "paving_stones": 0.012,
    "cobblestone": 0.018,
    "gravel": 0.022,
    "compacted": 0.015,
    "dirt": 0.030,
    "ground": 0.035,
    "grass": 0.045,
    "sand": 0.080,
}


def haversine_distance_2d(coord1: Sequence[float], coord2: Sequence[float]) -> float:
    """Calculate the geodesic 2D distance in meters between two (lon, lat) points."""
    if not coord1 or not coord2 or len(coord1) < 2 or len(coord2) < 2:
        return 0.0

    lon1, lat1 = float(coord1[0]), float(coord1[1])
    lon2, lat2 = float(coord2[0]), float(coord2[1])

    if not (
        math.isfinite(lon1) and math.isfinite(lat1) and math.isfinite(lon2) and math.isfinite(lat2)
    ):
        return 0.0

    if abs(lon1 - lon2) < 1e-11 and abs(lat1 - lat2) < 1e-11:
        return 0.0

    radius = 6371008.8  # WGS84 mean earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    a = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return radius * c


def haversine_distance_3d(coord1: Sequence[float], coord2: Sequence[float]) -> float:
    """Calculate the 3D distance in meters considering elevation (Z coordinate)."""
    d_2d = haversine_distance_2d(coord1, coord2)
    z1 = float(coord1[2]) if len(coord1) > 2 and math.isfinite(float(coord1[2])) else 0.0
    z2 = float(coord2[2]) if len(coord2) > 2 and math.isfinite(float(coord2[2])) else 0.0
    dz = z2 - z1
    return math.hypot(d_2d, dz)


def tobler_walking_speed(slope_fraction: float, base_speed_kmh: float = 5.0) -> float:
    """Compute walking speed (km/h) as a function of slope (dh / dx) using Tobler's curve.

    Standard Tobler formula: W = 6.0 * exp(-3.5 * |s + 0.05|) km/h where s is slope fraction.
    Scaled relative to the specific profile's base walking speed.
    """
    s_val = float(slope_fraction) if math.isfinite(slope_fraction) else 0.0
    s = max(-0.60, min(0.60, s_val))
    b_spd = float(base_speed_kmh) if math.isfinite(base_speed_kmh) and base_speed_kmh > 0 else 5.0
    scale = max(0.2, b_spd / 5.0)
    speed = 6.0 * math.exp(-3.5 * abs(s + 0.05)) * scale
    return max(0.5, min(8.0, speed))


def minetti_energy_cost(
    slope_fraction: float,
    mass_kg: float = 70.0,
    distance_m: float = 100.0,
) -> Tuple[float, float]:
    """Calculate metabolic energy expenditure using Minetti (2002) polynomial.

    Returns:
        Tuple of (energy_in_joules, energy_in_kilocalories).
    """
    s_val = float(slope_fraction) if math.isfinite(slope_fraction) else 0.0
    s = max(-0.50, min(0.50, s_val))
    m = float(mass_kg) if math.isfinite(mass_kg) and mass_kg > 0 else 70.0
    d = float(distance_m) if math.isfinite(distance_m) and distance_m >= 0 else 0.0

    cost_j_kg_m = 280.5 * (s**5) - 58.7 * (s**4) - 76.8 * (s**3) + 51.9 * (s**2) + 19.6 * s + 2.5
    # Minetti's polynomial is fitted over -0.45 <= i <= +0.45; outside that range it
    # turns non-physical. Clamp to the smallest cost the fit itself produces rather
    # than to an invented floor.
    cost_j_kg_m = max(0.6, cost_j_kg_m)
    total_joules = cost_j_kg_m * m * d
    total_kcal = total_joules / 4184.0
    return total_joules, total_kcal


def senior_fatigue_decay(distance_m: float, accumulated_climb_m: float) -> float:
    """Calculate velocity decay multiplier (1.0 down to 0.45) for elderly pedestrians due to fatigue."""
    d = float(distance_m) if math.isfinite(distance_m) and distance_m >= 0 else 0.0
    climb = (
        float(accumulated_climb_m)
        if math.isfinite(accumulated_climb_m) and accumulated_climb_m >= 0
        else 0.0
    )
    dist_km = d / 1000.0
    fatigue_score = (dist_km * 0.12) + (climb / 100.0 * 0.25)
    decay = math.exp(-0.35 * fatigue_score)
    return max(0.45, min(1.0, decay))


def aerodynamic_drag_power(
    velocity_kmh: float,
    frontal_area_m2: float = 0.55,
    drag_coeff: float = 0.88,
    air_density: float = 1.225,
) -> float:
    """Calculate aerodynamic power resistance in Watts (P_aero = 0.5 * rho * C_d * A * v^3)."""
    v_kmh = float(velocity_kmh) if math.isfinite(velocity_kmh) and velocity_kmh >= 0 else 0.0
    v_ms = max(0.0, v_kmh / 3.6)
    return 0.5 * air_density * drag_coeff * frontal_area_m2 * (v_ms**3)


def rolling_resistance_force(
    mass_kg: float,
    slope_fraction: float,
    surface_type: str = "asphalt",
) -> float:
    """Calculate rolling friction resistance force in Newtons (F_roll = C_rr * m * g * cos(theta))."""
    m = float(mass_kg) if math.isfinite(mass_kg) and mass_kg > 0 else 70.0
    s = float(slope_fraction) if math.isfinite(slope_fraction) else 0.0
    c_rr = ROLLING_RESISTANCE.get(str(surface_type).lower(), 0.005)
    theta = math.atan(abs(s))
    g = 9.80665
    return c_rr * m * g * math.cos(theta)


def cycling_energy_cost(
    slope_fraction: float,
    mass_kg: float = 70.0,
    distance_m: float = 0.0,
    bike_mass_kg: float = 15.0,
    surface: str = "asphalt",
    gross_efficiency: float = 0.24,
) -> Tuple[float, float]:
    """Metabolic energy for cycling a segment, from a real power balance.

    Mechanical work is the sum of the gravitational, rolling and aerodynamic terms
    over the segment; metabolic energy is that work divided by cycling gross
    efficiency (~0.20-0.25 in the literature). Descents recover no metabolic energy
    but still cost basal effort, so the result is floored at zero work.

    Returns (joules, kilocalories).
    """
    s_val = float(slope_fraction) if math.isfinite(slope_fraction) else 0.0
    s = max(-0.30, min(0.30, s_val))
    rider = float(mass_kg) if math.isfinite(mass_kg) and mass_kg > 0 else 70.0
    bike = float(bike_mass_kg) if math.isfinite(bike_mass_kg) and bike_mass_kg > 0 else 15.0
    d = float(distance_m) if math.isfinite(distance_m) and distance_m >= 0 else 0.0
    eff = (
        float(gross_efficiency)
        if math.isfinite(gross_efficiency) and 0.05 < gross_efficiency < 1.0
        else 0.24
    )
    total_mass = rider + bike

    theta = math.atan(s)
    g = 9.80665

    f_grav = total_mass * g * math.sin(theta)
    f_roll = rolling_resistance_force(total_mass, s, surface)

    speed_kmh = cyclist_speed(s, total_mass_kg=total_mass, surface=surface)
    p_aero = aerodynamic_drag_power(speed_kmh)
    v_ms = max(0.1, speed_kmh / 3.6)
    f_aero = p_aero / v_ms

    f_total = f_grav + f_roll + f_aero
    mechanical_j = max(0.0, f_total) * d
    metabolic_j = mechanical_j / eff
    return metabolic_j, metabolic_j / 4184.0


def cyclist_speed(
    slope_fraction: float,
    base_speed_kmh: float = 18.0,
    rider_power_watts: float = 160.0,
    total_mass_kg: float = 85.0,
    surface: str = "asphalt",
) -> float:
    """Calculate physics-based bicycle speed (km/h) accounting for gradient, rolling resistance, and drag."""
    s_val = float(slope_fraction) if math.isfinite(slope_fraction) else 0.0
    s = max(-0.25, min(0.25, s_val))
    b_spd = float(base_speed_kmh) if math.isfinite(base_speed_kmh) and base_speed_kmh > 0 else 18.0
    p_watts = (
        float(rider_power_watts)
        if math.isfinite(rider_power_watts) and rider_power_watts > 0
        else 160.0
    )
    m_kg = float(total_mass_kg) if math.isfinite(total_mass_kg) and total_mass_kg > 0 else 85.0

    if s < -0.02:
        # Downhill with coasting limit
        speed = b_spd * (1.0 + abs(s) * 2.2)
        return min(45.0, speed)

    # Uphill power balance: P = (F_gravity + F_roll + F_aero) * v
    g = 9.80665
    f_grav = m_kg * g * math.sin(math.atan(s))
    f_roll = rolling_resistance_force(m_kg, s, surface)
    f_resist = max(1.0, f_grav + f_roll)

    # Effective speed from mechanical power: v = P / F
    v_ms = p_watts / f_resist
    speed_kmh = v_ms * 3.6
    return max(3.5, min(b_spd * 1.5, speed_kmh))


def scooter_speed(slope_fraction: float, base_speed_kmh: float = 20.0) -> float:
    """Calculate micromobility/e-scooter speed (km/h) with motor torque reduction on slopes."""
    s_val = float(slope_fraction) if math.isfinite(slope_fraction) else 0.0
    s = max(-0.20, min(0.20, s_val))
    b_spd = float(base_speed_kmh) if math.isfinite(base_speed_kmh) and base_speed_kmh > 0 else 20.0

    if s > 0.12:
        return 4.0  # grade exceeds motor climbing capability
    if s > 0:
        speed = b_spd * max(0.25, 1.0 - (s / 0.14) ** 1.5)
        return max(4.0, speed)
    return min(25.0, b_spd * (1.0 + abs(s) * 0.5))


def vehicle_free_flow_speed(
    hierarchy_rank: int,
    lanes: int = 2,
    slope_pct: float = 0.0,
    base_vehicle_speed_kmh: float = 50.0,
) -> float:
    """Modelled vehicle speed in km/h based on functional road classification, vehicle profile, lanes, and grade."""
    base_speeds = {
        1: 80.0,  # Motorway / Primary Arterial
        2: 60.0,  # Secondary Arterial
        3: 45.0,  # Collector / Major Urban
        4: 30.0,  # Local Residential Street
        5: 20.0,  # Narrow Alley / Service Way
    }
    road_speed = base_speeds.get(hierarchy_rank, 30.0)
    v_base = (
        float(base_vehicle_speed_kmh)
        if math.isfinite(base_vehicle_speed_kmh) and base_vehicle_speed_kmh > 0
        else 50.0
    )
    speed = road_speed * (v_base / 50.0)
    l_count = int(lanes) if math.isfinite(lanes) and lanes > 0 else 2
    speed += min(10.0, max(0, l_count - 2) * 4.0)
    s_pct = float(slope_pct) if math.isfinite(slope_pct) else 0.0
    routed_slope = min(35.0, max(0.0, abs(s_pct)))
    speed *= max(0.50, 1.0 - (routed_slope / 100.0) * 0.85)
    return max(10.0, speed)


def solar_irradiance_aspect_factor(
    aspect_deg: float,
    slope_pct: float,
    sun_azimuth_deg: float = 180.0,  # Solar noon south
    sun_elevation_deg: float = 55.0,
) -> float:
    """Calculate relative solar irradiance factor (0.0 to 1.0) based on slope angle and sun position."""
    s_pct = float(slope_pct) if math.isfinite(slope_pct) else 0.0
    asp_deg = float(aspect_deg) if math.isfinite(aspect_deg) else 180.0
    sun_az = float(sun_azimuth_deg) if math.isfinite(sun_azimuth_deg) else 180.0
    sun_el = float(sun_elevation_deg) if math.isfinite(sun_elevation_deg) else 55.0

    slope_rad = math.atan(abs(s_pct) / 100.0)
    aspect_rad = math.radians(asp_deg)
    sun_az_rad = math.radians(sun_az)
    sun_el_rad = math.radians(sun_el)

    # Cosine of incidence angle
    cos_inc = math.sin(sun_el_rad) * math.cos(slope_rad) + math.cos(sun_el_rad) * math.sin(
        slope_rad
    ) * math.cos(sun_az_rad - aspect_rad)
    if not math.isfinite(cos_inc):
        return 0.5
    return max(0.0, min(1.0, cos_inc))


def universal_thermal_comfort_utci(
    temp_c: float,
    relative_humidity_pct: float = 50.0,
    wind_speed_ms: float = 1.0,
    mean_radiant_temp_c: float = 35.0,
) -> float:
    """Approximation of Universal Thermal Climate Index (UTCI in Celsius).

    Returns normalized thermal strain score (0.0 = comfortable/cool, 1.0 = severe heat stress).
    """
    t_c = float(temp_c) if math.isfinite(temp_c) else 25.0
    mrt = float(mean_radiant_temp_c) if math.isfinite(mean_radiant_temp_c) else 35.0
    w_ms = float(wind_speed_ms) if math.isfinite(wind_speed_ms) and wind_speed_ms >= 0 else 1.0

    # Simplified empirical UTCI offset
    utci = t_c + 0.33 * (mrt - t_c) - 0.70 * math.sqrt(max(0.1, w_ms))
    if not math.isfinite(utci):
        return 0.5
    # Normalize: 18C = 0.0 (no stress), 38C+ = 1.0 (extreme heat stress)
    norm_stress = (utci - 18.0) / 20.0
    return max(0.0, min(1.0, norm_stress))
