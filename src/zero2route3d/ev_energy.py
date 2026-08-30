# -*- coding: utf-8 -*-
"""3D Electric Vehicle (EV) Energy Consumption & Regenerative Braking Optimizer for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class EVBatteryProfile:
    """Vehicle parameters and battery specification."""

    vehicle_name: str = "Standard EV Sedan"
    battery_capacity_kwh: float = 75.0
    initial_soc_percent: float = 90.0  # State of Charge (0 - 100%)
    vehicle_mass_kg: float = 1950.0  # Mass including payload
    drag_coefficient_cd: float = 0.24  # Aerodynamic drag coeff
    frontal_area_m2: float = 2.30  # Frontal area
    rolling_resistance_crr: float = 0.010  # Tire rolling resistance
    drivetrain_efficiency: float = 0.90  # Electric motor & inverter eff
    regenerative_efficiency: float = 0.75  # Regen braking recovery factor
    auxiliary_power_kw: float = 1.50  # Climate control / HVAC / electronics
    max_regen_power_kw: float = 60.0  # Max regen power limit


@dataclass
class EVSegmentEnergy:
    """Energy calculation on a single 3D route segment."""

    segment_index: int
    distance_m: float
    elevation_start: float
    elevation_end: float
    slope_percent: float
    speed_kmh: float
    duration_s: float
    mechanical_energy_kwh: float
    net_battery_energy_kwh: float  # Negative when regenerating
    soc_end_percent: float
    is_regenerating: bool


@dataclass
class EVRouteEnergyResult:
    """Complete route-level EV energy consumption analysis."""

    profile: EVBatteryProfile
    total_distance_km: float
    total_duration_min: float
    initial_soc_percent: float
    final_soc_percent: float
    total_consumed_kwh: float
    total_regenerated_kwh: float
    net_energy_kwh: float
    efficiency_wh_per_km: float
    is_depleted: bool
    depletion_distance_km: float | None
    segments: list[EVSegmentEnergy]

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_name": self.profile.vehicle_name,
            "total_distance_km": round(self.total_distance_km, 3),
            "total_duration_min": round(self.total_duration_min, 2),
            "initial_soc_percent": round(self.initial_soc_percent, 1),
            "final_soc_percent": round(self.final_soc_percent, 1),
            "total_consumed_kwh": round(self.total_consumed_kwh, 3),
            "total_regenerated_kwh": round(self.total_regenerated_kwh, 3),
            "net_energy_kwh": round(self.net_energy_kwh, 3),
            "efficiency_wh_per_km": round(self.efficiency_wh_per_km, 1),
            "is_depleted": self.is_depleted,
            "depletion_distance_km": round(self.depletion_distance_km, 3) if self.depletion_distance_km else None,
        }


class EVEnergySimulator:
    """Physics-based 3D powertrain model simulating EV power balance across topographies."""

    def __init__(self, profile: EVBatteryProfile | None = None) -> None:
        self.profile = profile or EVBatteryProfile()

    def simulate_route(
        self,
        waypoints_3d: Sequence[tuple[float, float, float]],
        target_speeds_kmh: Sequence[float] | float = 60.0,
    ) -> EVRouteEnergyResult:
        """Simulate energy balance along a 3D polyline.

        Args:
            waypoints_3d: List of (x, y, z) coordinates where z is elevation in meters.
            target_speeds_kmh: Speed in km/h for each segment, or scalar constant.
        """
        n_pts = len(waypoints_3d)
        if n_pts < 2:
            return EVRouteEnergyResult(
                profile=self.profile,
                total_distance_km=0.0,
                total_duration_min=0.0,
                initial_soc_percent=self.profile.initial_soc_percent,
                final_soc_percent=self.profile.initial_soc_percent,
                total_consumed_kwh=0.0,
                total_regenerated_kwh=0.0,
                net_energy_kwh=0.0,
                efficiency_wh_per_km=0.0,
                is_depleted=False,
                depletion_distance_km=None,
                segments=[],
            )

        p = self.profile
        g = 9.80665  # Gravity m/s^2
        rho_air = 1.225  # Air density kg/m^3

        current_battery_kwh = p.battery_capacity_kwh * (p.initial_soc_percent / 100.0)
        current_soc = p.initial_soc_percent

        segments: list[EVSegmentEnergy] = []
        total_dist_m = 0.0
        total_time_s = 0.0
        total_consumed = 0.0
        total_regen = 0.0
        is_depleted = False
        depletion_dist: float | None = None

        for i in range(n_pts - 1):
            p1 = waypoints_3d[i]
            p2 = waypoints_3d[i + 1]

            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            dz = p2[2] - p1[2]
            d_horiz = math.hypot(dx, dy)
            d_3d = math.sqrt(d_horiz ** 2 + dz ** 2)

            if d_3d <= 1e-4:
                continue

            speed_kmh = (
                target_speeds_kmh[i]
                if isinstance(target_speeds_kmh, (list, tuple))
                else float(target_speeds_kmh)
            )
            v_ms = max(1.0, (speed_kmh * 1000.0) / 3600.0)
            duration_s = d_3d / v_ms

            theta = math.atan2(dz, max(1e-4, d_horiz))
            slope_pct = (dz / max(1e-4, d_horiz)) * 100.0

            # 1. Resistive Forces (N)
            f_roll = p.rolling_resistance_crr * p.vehicle_mass_kg * g * math.cos(theta)
            f_aero = 0.5 * rho_air * p.drag_coefficient_cd * p.frontal_area_m2 * (v_ms ** 2)
            f_gravity = p.vehicle_mass_kg * g * math.sin(theta)  # positive uphill, negative downhill

            total_traction_force_n = f_roll + f_aero + f_gravity
            mechanical_power_w = total_traction_force_n * v_ms
            mechanical_energy_kwh = (mechanical_power_w * duration_s) / (3600.0 * 1000.0)

            # 2. Battery Power & Energy (including auxiliaries)
            aux_energy_kwh = (p.auxiliary_power_kw * duration_s) / 3600.0

            if mechanical_power_w >= 0:
                # Traction mode
                battery_energy_kwh = (mechanical_energy_kwh / p.drivetrain_efficiency) + aux_energy_kwh
                total_consumed += battery_energy_kwh
                is_regen = False
            else:
                # Downhill regenerative braking mode
                regen_power_kw = min(p.max_regen_power_kw, abs(mechanical_power_w / 1000.0))
                recovered_kwh = (regen_power_kw * duration_s / 3600.0) * p.regenerative_efficiency * p.drivetrain_efficiency
                battery_energy_kwh = -recovered_kwh + aux_energy_kwh
                if battery_energy_kwh < 0:
                    total_regen += abs(battery_energy_kwh)
                else:
                    total_consumed += battery_energy_kwh
                is_regen = True

            current_battery_kwh -= battery_energy_kwh
            current_battery_kwh = max(0.0, min(p.battery_capacity_kwh, current_battery_kwh))
            current_soc = (current_battery_kwh / p.battery_capacity_kwh) * 100.0

            total_dist_m += d_3d
            total_time_s += duration_s

            if current_battery_kwh <= 0.0 and not is_depleted:
                is_depleted = True
                depletion_dist = total_dist_m / 1000.0

            segments.append(
                EVSegmentEnergy(
                    segment_index=i,
                    distance_m=round(d_3d, 2),
                    elevation_start=round(p1[2], 2),
                    elevation_end=round(p2[2], 2),
                    slope_percent=round(slope_pct, 2),
                    speed_kmh=round(speed_kmh, 1),
                    duration_s=round(duration_s, 2),
                    mechanical_energy_kwh=round(mechanical_energy_kwh, 4),
                    net_battery_energy_kwh=round(battery_energy_kwh, 4),
                    soc_end_percent=round(current_soc, 2),
                    is_regenerating=is_regen,
                )
            )

        total_dist_km = total_dist_m / 1000.0
        net_energy = total_consumed - total_regen
        wh_km = (net_energy * 1000.0) / max(0.01, total_dist_km)

        return EVRouteEnergyResult(
            profile=p,
            total_distance_km=total_dist_km,
            total_duration_min=total_time_s / 60.0,
            initial_soc_percent=p.initial_soc_percent,
            final_soc_percent=current_soc,
            total_consumed_kwh=total_consumed,
            total_regenerated_kwh=total_regen,
            net_energy_kwh=net_energy,
            efficiency_wh_per_km=wh_km,
            is_depleted=is_depleted,
            depletion_distance_km=depletion_dist,
            segments=segments,
        )


def solve_ev_energy_route(
    waypoints_3d: Sequence[tuple[float, float, float]],
    vehicle_type: str = "sedan",
    initial_soc_percent: float = 90.0,
    speed_kmh: float = 60.0,
) -> EVRouteEnergyResult:
    """Convenience helper to compute EV 3D energy consumption."""
    profiles = {
        "sedan": EVBatteryProfile(vehicle_name="Electric Sedan", battery_capacity_kwh=75.0, vehicle_mass_kg=1950.0, drag_coefficient_cd=0.23),
        "suv": EVBatteryProfile(vehicle_name="Electric SUV", battery_capacity_kwh=90.0, vehicle_mass_kg=2400.0, drag_coefficient_cd=0.29),
        "van": EVBatteryProfile(vehicle_name="Electric Cargo Van", battery_capacity_kwh=68.0, vehicle_mass_kg=2800.0, drag_coefficient_cd=0.34),
        "bus": EVBatteryProfile(vehicle_name="Electric Transit Bus", battery_capacity_kwh=350.0, vehicle_mass_kg=13500.0, drag_coefficient_cd=0.65, frontal_area_m2=7.5),
    }
    prof = profiles.get(vehicle_type.lower(), profiles["sedan"])
    prof.initial_soc_percent = initial_soc_percent

    sim = EVEnergySimulator(prof)
    return sim.simulate_route(waypoints_3d, target_speeds_kmh=speed_kmh)
