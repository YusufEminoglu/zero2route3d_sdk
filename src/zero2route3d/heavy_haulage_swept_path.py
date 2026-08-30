# -*- coding: utf-8 -*-
"""Superload / Wind Turbine Blade Swept Path Kinematic Turning Envelope & Collision Checker for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class SuperloadVehicleProfile:
    total_length_m: float = 65.0  # e.g., 65m wind turbine blade transporter
    tractor_wheelbase_m: float = 4.5
    trailer_wheelbase_m: float = 48.0
    overall_width_m: float = 3.5
    front_overhang_m: float = 2.0
    rear_overhang_m: float = 12.0
    max_steering_angle_deg: float = 35.0


@dataclass
class SweptPathResult:
    is_path_negotiable: bool
    max_swept_width_m: float
    total_corridor_area_m2: float
    curb_encroachments_count: int
    outer_swept_envelope_polygon: list[tuple[float, float]]
    inner_swept_envelope_polygon: list[tuple[float, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "negotiable": self.is_path_negotiable,
            "max_swept_width_m": round(self.max_swept_width_m, 2),
            "corridor_area_m2": round(self.total_corridor_area_m2, 1),
            "encroachments": self.curb_encroachments_count,
        }


def calculate_swept_path_envelope(
    road_centerline_2d: Sequence[tuple[float, float]],
    road_curb_half_width_m: float = 6.0,
    vehicle_profile: SuperloadVehicleProfile | None = None,
) -> SweptPathResult:
    """Simulate kinematic offtracking swept path envelope for oversized freight and superloads (AASHTO / Western US models)."""
    veh = vehicle_profile or SuperloadVehicleProfile()
    pts = list(road_centerline_2d)
    if len(pts) < 2:
        return SweptPathResult(True, veh.overall_width_m, 0.0, 0, [], [])

    outer_env: list[tuple[float, float]] = []
    inner_env: list[tuple[float, float]] = []

    max_swept_w = veh.overall_width_m
    encroachments = 0

    for i in range(len(pts) - 1):
        p1 = pts[i]
        p2 = pts[i + 1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-4:
            continue

        nx = -dy / seg_len
        ny = dx / seg_len

        # Estimate curve radius from adjacent segments
        curv_radius = 500.0  # default large radius
        if 0 < i < len(pts) - 1:
            p0 = pts[i - 1]
            # Menger curvature approximation
            a = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            b = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            c = math.hypot(p2[0] - p0[0], p2[1] - p0[1])
            s = (a + b + c) / 2.0
            area = math.sqrt(max(0.0, s * (s - a) * (s - b) * (s - c)))
            if a * b * c > 1e-4 and area > 1e-4:
                curv_radius = (a * b * c) / (4.0 * area)

        # Offtracking formula: OT = R - \sqrt{R^2 - L^2}
        if curv_radius < 500.0 and curv_radius > veh.trailer_wheelbase_m:
            offtracking = curv_radius - math.sqrt(curv_radius**2 - veh.trailer_wheelbase_m**2)
        else:
            offtracking = (veh.trailer_wheelbase_m**2) / (2.0 * max(10.0, curv_radius))

        swept_w = veh.overall_width_m + offtracking
        max_swept_w = max(max_swept_w, swept_w)

        half_w_out = swept_w / 2.0
        half_w_in = -swept_w / 2.0

        if (swept_w / 2.0) > road_curb_half_width_m:
            encroachments += 1

        outer_env.append((p1[0] + nx * half_w_out, p1[1] + ny * half_w_out))
        inner_env.append((p1[0] + nx * half_w_in, p1[1] + ny * half_w_in))

    # Add last point
    p_last = pts[-1]
    p_prev = pts[-2]
    dx = p_last[0] - p_prev[0]
    dy = p_last[1] - p_prev[1]
    sl = math.hypot(dx, dy)
    if sl > 1e-4:
        nx = -dy / sl
        ny = dx / sl
        outer_env.append((p_last[0] + nx * (veh.overall_width_m / 2.0), p_last[1] + ny * (veh.overall_width_m / 2.0)))
        inner_env.append((p_last[0] - nx * (veh.overall_width_m / 2.0), p_last[1] - ny * (veh.overall_width_m / 2.0)))

    # Compute enclosed polygon area
    full_poly = outer_env + list(reversed(inner_env))
    tot_area = 0.0
    for j in range(len(full_poly) - 1):
        tot_area += full_poly[j][0] * full_poly[j + 1][1] - full_poly[j + 1][0] * full_poly[j][1]
    tot_area = abs(tot_area) * 0.5

    negotiable = (encroachments == 0)

    return SweptPathResult(
        is_path_negotiable=negotiable,
        max_swept_width_m=max_swept_w,
        total_corridor_area_m2=tot_area,
        curb_encroachments_count=encroachments,
        outer_swept_envelope_polygon=outer_env,
        inner_swept_envelope_polygon=inner_env,
    )
