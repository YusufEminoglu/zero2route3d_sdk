# -*- coding: utf-8 -*-
"""Alpine Ski Resort Piste Gradient Classifier & Gravity Downhill Router for zero2route3d."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class PisteDifficultyProfile:
    green_beginner_max_slope_pct: float = 15.0  # Easy green slope
    blue_intermediate_max_slope_pct: float = 25.0  # Intermediate blue slope
    red_advanced_max_slope_pct: float = 40.0  # Difficult red slope
    # Above 40% slope is classified as Black / Expert


@dataclass
class SkiPisteRouteResult:
    total_descent_distance_m: float
    vertical_drop_m: float
    average_slope_pct: float
    max_slope_pct: float
    overall_piste_classification: str  # GREEN, BLUE, RED, BLACK
    descent_duration_minutes: float
    has_uphill_traverses: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "descent_dist_m": round(self.total_descent_distance_m, 1),
            "vertical_drop_m": round(self.vertical_drop_m, 1),
            "avg_slope_pct": round(self.average_slope_pct, 1),
            "max_slope_pct": round(self.max_slope_pct, 1),
            "difficulty": self.overall_piste_classification,
            "duration_min": round(self.descent_duration_minutes, 1),
            "uphill_traverses": self.has_uphill_traverses,
        }


def classify_ski_pistes_and_route(
    piste_waypoints_xyz: Sequence[tuple[float, float, float]],  # (x, y, elevation_z)
    skier_skill_level: str = "INTERMEDIATE",
    profile: PisteDifficultyProfile | None = None,
) -> SkiPisteRouteResult:
    """Classify FIS alpine ski slope difficulty and compute gravitational downhill descent trajectories."""
    prof = profile or PisteDifficultyProfile()
    pts = list(piste_waypoints_xyz)
    if len(pts) < 2:
        return SkiPisteRouteResult(0.0, 0.0, 0.0, 0.0, "GREEN", 0.0, False)

    tot_dist = 0.0
    vert_drop = 0.0
    slopes: list[float] = []
    has_uphill = False

    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i + 1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p1[2] - p2[2]  # Positive when descending

        h_dist = math.hypot(dx, dy)
        dist_3d = math.hypot(h_dist, dz)
        tot_dist += dist_3d

        if dz < -0.2:
            has_uphill = True

        vert_drop += max(0.0, dz)

        slope_pct = (abs(dz) / max(1.0, h_dist)) * 100.0 if h_dist > 0 else 0.0
        slopes.append(slope_pct)

    avg_slope = sum(slopes) / max(1, len(slopes))
    max_slope = max(slopes) if slopes else 0.0

    # Classify overall slope difficulty
    if max_slope <= prof.green_beginner_max_slope_pct:
        difficulty = "GREEN"
        speed_ms = 7.0
    elif max_slope <= prof.blue_intermediate_max_slope_pct:
        difficulty = "BLUE"
        speed_ms = 11.0
    elif max_slope <= prof.red_advanced_max_slope_pct:
        difficulty = "RED"
        speed_ms = 15.0
    else:
        difficulty = "BLACK"
        speed_ms = 19.0

    duration_min = (tot_dist / max(1.0, speed_ms)) / 60.0

    return SkiPisteRouteResult(
        total_descent_distance_m=tot_dist,
        vertical_drop_m=vert_drop,
        average_slope_pct=avg_slope,
        max_slope_pct=max_slope,
        overall_piste_classification=difficulty,
        descent_duration_minutes=duration_min,
        has_uphill_traverses=has_uphill,
    )
