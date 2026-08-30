# -*- coding: utf-8 -*-
"""Multi-Lingual 3D Turn-by-Turn Voice Navigation & Spatial Maneuver Generator for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class ManeuverInstruction3D:
    step_index: int
    maneuver_type: str  # 'DEPART', 'TURN_LEFT', 'TURN_RIGHT', 'SLIGHT_LEFT', 'SLIGHT_RIGHT', 'UTURN', 'STEEP_CLIMB', 'STEEP_DESCENT', 'ARRIVE'
    distance_to_next_m: float
    slope_percent: float
    elevation_delta_m: float
    instruction_text_tr: str
    instruction_text_en: str
    instruction_text_de: str
    auditory_cue: str  # Voice synthesize prompt


@dataclass
class TurnByTurn3DRouteGuide:
    total_steps: int
    total_distance_km: float
    instructions: list[ManeuverInstruction3D]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_steps": self.total_steps,
            "total_distance_km": round(self.total_distance_km, 3),
            "instructions": [
                {
                    "step": ins.step_index,
                    "maneuver": ins.maneuver_type,
                    "dist_m": round(ins.distance_to_next_m, 1),
                    "slope_pct": round(ins.slope_percent, 1),
                    "text_tr": ins.instruction_text_tr,
                    "text_en": ins.instruction_text_en,
                }
                for ins in self.instructions
            ],
        }


def generate_3d_turn_by_turn_cues(
    waypoints_3d: Sequence[tuple[float, float, float]],
    street_names: Sequence[str] | None = None,
) -> TurnByTurn3DRouteGuide:
    """Generate 3D elevation and turn-angle aware auditory navigation cues."""
    n = len(waypoints_3d)
    if n < 2:
        return TurnByTurn3DRouteGuide(0, 0.0, [])

    instructions: list[ManeuverInstruction3D] = []
    tot_dist = 0.0

    # First departure step
    p0 = waypoints_3d[0]
    p1 = waypoints_3d[1]
    d0 = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    dz0 = p1[2] - p0[2]

    instructions.append(
        ManeuverInstruction3D(
            step_index=1,
            maneuver_type="DEPART",
            distance_to_next_m=d0,
            slope_percent=(dz0 / max(1.0, d0)) * 100.0,
            elevation_delta_m=dz0,
            instruction_text_tr="Rotaya başlayın ve düz devam edin.",
            instruction_text_en="Start your route and proceed straight ahead.",
            instruction_text_de="Starten Sie Ihre Route und fahren Sie geradeaus.",
            auditory_cue="Start route.",
        )
    )
    tot_dist += d0

    for i in range(1, n - 1):
        prev_p = waypoints_3d[i - 1]
        curr_p = waypoints_3d[i]
        next_p = waypoints_3d[i + 1]

        # Ingress and egress headings
        h1 = math.atan2(curr_p[0] - prev_p[0], curr_p[1] - prev_p[1])
        h2 = math.atan2(next_p[0] - curr_p[0], next_p[1] - curr_p[1])

        turn_angle_rad = h2 - h1
        while turn_angle_rad > math.pi:
            turn_angle_rad -= 2 * math.pi
        while turn_angle_rad < -math.pi:
            turn_angle_rad += 2 * math.pi
        turn_deg = math.degrees(turn_angle_rad)

        seg_dist = math.hypot(next_p[0] - curr_p[0], next_p[1] - curr_p[1])
        dz = next_p[2] - curr_p[2]
        slope_pct = (dz / max(1.0, seg_dist)) * 100.0
        tot_dist += seg_dist

        # Turn type
        if turn_deg > 45:
            m_type = "TURN_RIGHT"
            tr = f"{int(seg_dist)} metre sonra sağa dönün."
            en = f"In {int(seg_dist)} meters, turn right."
            de = f"In {int(seg_dist)} Metern rechts abbiegen."
        elif turn_deg < -45:
            m_type = "TURN_LEFT"
            tr = f"{int(seg_dist)} metre sonra sola dönün."
            en = f"In {int(seg_dist)} meters, turn left."
            de = f"In {int(seg_dist)} Metern links abbiegen."
        elif slope_pct > 10.0:
            m_type = "STEEP_CLIMB"
            tr = f"Dik yokuş tırmanışı: %{int(slope_pct)} eğim."
            en = f"Steep climb ahead: {int(slope_pct)}% incline."
            de = f"Steiler Anstieg: {int(slope_pct)}% Steigung."
        elif slope_pct < -10.0:
            m_type = "STEEP_DESCENT"
            tr = f"Dik iniş: %{int(abs(slope_pct))} eğim, hızınızı kontrol edin."
            en = f"Steep descent ahead: {int(abs(slope_pct))}% slope, control speed."
            de = f"Steiles Gefälle: {int(abs(slope_pct))}%, Geschwindigkeit kontrollieren."
        else:
            m_type = "STRAIGHT"
            tr = "Düz devam edin."
            en = "Continue straight."
            de = "Geradeaus weiterfahren."

        instructions.append(
            ManeuverInstruction3D(
                step_index=i + 1,
                maneuver_type=m_type,
                distance_to_next_m=seg_dist,
                slope_percent=slope_pct,
                elevation_delta_m=dz,
                instruction_text_tr=tr,
                instruction_text_en=en,
                instruction_text_de=de,
                auditory_cue=en,
            )
        )

    # Arrival
    instructions.append(
        ManeuverInstruction3D(
            step_index=n + 1,
            maneuver_type="ARRIVE",
            distance_to_next_m=0.0,
            slope_percent=0.0,
            elevation_delta_m=0.0,
            instruction_text_tr="Hedefinize ulaştınız.",
            instruction_text_en="You have arrived at your destination.",
            instruction_text_de="Sie haben Ihr Ziel erreicht.",
            auditory_cue="Arrived.",
        )
    )

    return TurnByTurn3DRouteGuide(
        total_steps=len(instructions),
        total_distance_km=tot_dist / 1000.0,
        instructions=instructions,
    )
