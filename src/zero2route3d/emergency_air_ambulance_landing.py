# -*- coding: utf-8 -*-
"""Emergency Helicopter Air Ambulance (HEMS) 3D Landing Zone (LZ) & Obstacle Clearance Evaluator for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class HelicopterApproachSlope:
    slope_ratio: float = 8.0  # 1:8 approach slope standard (ICAO Annex 14 / FAA Heliport)
    approach_bearing_deg: float = 0.0  # Primary landing direction
    funnel_divergence_angle_deg: float = 15.0  # 15 deg splay on approach path
    safety_buffer_radius_m: float = 30.0  # Minimum touchdown and lift-off (TLOF) radius


@dataclass
class LandingZoneResult:
    is_safe_for_landing: bool
    touchdown_point_3d: tuple[float, float, float]
    max_obstacle_intrusion_m: float
    clearance_margin_m: float
    safe_approach_headings: list[float]
    critical_obstacles_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe_landing": self.is_safe_for_landing,
            "tlof_pos": [round(c, 2) for c in self.touchdown_point_3d],
            "max_intrusion_m": round(self.max_obstacle_intrusion_m, 2),
            "clearance_margin_m": round(self.clearance_margin_m, 2),
            "safe_headings": [round(h, 1) for h in self.safe_approach_headings],
            "critical_obstacles": self.critical_obstacles_count,
        }


def evaluate_helicopter_landing_zones(
    potential_tlof_point_3d: tuple[float, float, float],
    surrounding_obstacles_3d: Sequence[tuple[float, float, float]],  # (x, y, z_top)
    approach_config: HelicopterApproachSlope | None = None,
    evaluation_radius_m: float = 500.0,
) -> LandingZoneResult:
    """Evaluate 3D terrain and structural obstacles against ICAO 1:8 approach/climb surface cones."""
    cfg = approach_config or HelicopterApproachSlope()
    t_x, t_y, t_z = potential_tlof_point_3d

    safe_headings: list[float] = []
    max_intrusion = 0.0
    critical_count = 0

    # Test 8 cardinal / intercardinal approach angles
    headings_to_test = [i * 45.0 for i in range(8)]

    for heading in headings_to_test:
        rad = math.radians(heading)
        fwd_x = math.cos(rad)
        fwd_y = math.sin(rad)

        heading_safe = True

        for ob_x, ob_y, ob_z in surrounding_obstacles_3d:
            dx = ob_x - t_x
            dy = ob_y - t_y
            dist_2d = math.hypot(dx, dy)

            if dist_2d > evaluation_radius_m:
                continue

            # Within immediate TLOF safety circle: must have zero obstacle above ground
            if dist_2d <= cfg.safety_buffer_radius_m:
                if ob_z > t_z + 0.5:
                    heading_safe = False
                    critical_count += 1
                    max_intrusion = max(max_intrusion, ob_z - t_z)
                continue

            # Check if obstacle falls within approach funnel sector
            dot = (dx * fwd_x + dy * fwd_y) / max(1e-4, dist_2d)
            angle_diff_deg = math.degrees(math.acos(max(-1.0, min(1.0, dot))))

            if angle_diff_deg <= cfg.funnel_divergence_angle_deg:
                # Allowed elevation along 1:8 slope: z_allow = t_z + dist_2d / slope_ratio
                z_allowed = t_z + (dist_2d - cfg.safety_buffer_radius_m) / cfg.slope_ratio
                if ob_z > z_allowed:
                    heading_safe = False
                    intrusion = ob_z - z_allowed
                    max_intrusion = max(max_intrusion, intrusion)
                    critical_count += 1

        if heading_safe:
            safe_headings.append(heading)

    is_safe = (len(safe_headings) >= 1) and (max_intrusion == 0.0)
    clearance_margin = 0.0 if not is_safe else 15.0 - max_intrusion

    return LandingZoneResult(
        is_safe_for_landing=is_safe,
        touchdown_point_3d=potential_tlof_point_3d,
        max_obstacle_intrusion_m=max_intrusion,
        clearance_margin_m=clearance_margin,
        safe_approach_headings=safe_headings,
        critical_obstacles_count=critical_count,
    )
