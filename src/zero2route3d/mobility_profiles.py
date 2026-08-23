"""Mobility profiles catalog and parameter specifications for 3D route planning.

Provides 15 specialized profiles across pedestrian, accessibility, micromobility,
and vehicular transport modes, with custom profile building and JSON preset export.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MobilityProfile:
    """Configuration and physiological/kinematic constraints for a mobility mode."""

    key: str
    name: str
    category: str  # 'pedestrian', 'micromobility', 'vehicle'
    base_speed_kmh: float
    max_slope_pct: float  # Slope beyond which path is strictly impassable or heavily penalised
    stair_allowed: bool
    stair_penalty: float  # Resistance multiplier for stairs (1.0 = normal, 100.0+ = forbidden)
    slope_sensitivity: float  # Exponent/multiplier for slope resistance
    heat_sensitivity: float  # 0.0 to 1.0: priority on avoiding high surface temperature (LST)
    green_preference: float  # 0.0 to 1.0: bonus for tree shade and greenery
    surface_smoothness_req: float  # 0.0 (all-terrain) to 1.0 (requires smooth paved surface)
    hierarchy_weights: Dict[int, float] = field(
        default_factory=dict
    )  # Hierarchy rank (1-5) multipliers
    description: str = ""
    icon_name: str = "adult"

    def calculate_edge_resistance(
        self,
        length_m: float,
        slope_pct: float,
        is_steps: bool = False,
        surface_quality: float = 0.8,
        hierarchy_rank: int = 4,
        lst_normalized: Optional[float] = None,
        green_normalized: Optional[float] = None,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Calculate generalized impedance (cost) for traversing a segment under this profile."""
        len_m = float(length_m) if math.isfinite(length_m) and length_m > 0 else 0.01
        s_pct = float(slope_pct) if math.isfinite(slope_pct) else 0.0
        sq = max(0.0, min(1.0, float(surface_quality))) if math.isfinite(surface_quality) else 0.8
        # A missing environmental raster is *absent*, not average. Substituting a
        # mid-range constant would silently shift every edge cost, so None keeps the
        # thermal term exactly neutral instead.
        lst = (
            max(0.0, min(1.0, float(lst_normalized)))
            if lst_normalized is not None and math.isfinite(lst_normalized)
            else None
        )
        grn = (
            max(0.0, min(1.0, float(green_normalized)))
            if green_normalized is not None and math.isfinite(green_normalized)
            else None
        )

        weights = custom_weights or {}
        w_slope = weights.get("slope", self.slope_sensitivity)
        w_heat = weights.get("heat", self.heat_sensitivity)
        w_green = weights.get("green", self.green_preference)

        w_slope = (
            float(w_slope) if math.isfinite(w_slope) and w_slope >= 0 else self.slope_sensitivity
        )
        w_heat = float(w_heat) if math.isfinite(w_heat) and w_heat >= 0 else self.heat_sensitivity
        w_green = (
            float(w_green) if math.isfinite(w_green) and w_green >= 0 else self.green_preference
        )

        # 1. Slope Penalty
        abs_slope = abs(s_pct)
        max_s = max(1.0, self.max_slope_pct) if math.isfinite(self.max_slope_pct) else 25.0
        if abs_slope > max_s:
            if self.category != "pedestrian":
                return float("inf")
            slope_mult = 1.0 + (abs_slope / max_s) ** 3 * 20.0 * w_slope
        else:
            slope_mult = 1.0 + (abs_slope / 10.0) * w_slope * 1.5

        # 2. Steps / Stairs Penalty
        if is_steps:
            if not self.stair_allowed:
                return float("inf")
            stair_mult = max(1.0, float(self.stair_penalty))
        else:
            stair_mult = 1.0

        # 3. Surface Smoothness Penalty
        if sq < self.surface_smoothness_req:
            roughness_gap = self.surface_smoothness_req - sq
            smooth_mult = 1.0 + roughness_gap * 4.0
        else:
            smooth_mult = 1.0

        # 4. Thermal & Environmental Microclimate Resistance
        if lst is None and grn is None:
            thermal_mult = 1.0
        else:
            thermal_cost = 1.0
            if lst is not None:
                thermal_cost += lst * w_heat * 1.8
            if grn is not None:
                thermal_cost -= grn * w_green * 0.4
            thermal_mult = max(0.6, thermal_cost)

        # 5. Road Hierarchy Multiplier
        hier_mult = self.hierarchy_weights.get(hierarchy_rank, 1.0)
        if not math.isfinite(hier_mult) or hier_mult <= 0:
            hier_mult = 1.0

        cost = len_m * slope_mult * stair_mult * smooth_mult * thermal_mult * hier_mult
        if math.isinf(cost):
            return float("inf")
        if not math.isfinite(cost) or cost <= 0:
            return 0.01
        return max(0.01, cost)

    def travel_time_seconds(
        self,
        length_m: float,
        slope_pct: float = 0.0,
        hierarchy_rank: int = 4,
    ) -> float:
        """Estimate physically consistent travel time for one network edge."""
        from .kinematics import (
            cyclist_speed,
            scooter_speed,
            tobler_walking_speed,
            vehicle_free_flow_speed,
        )

        length = float(length_m) if math.isfinite(length_m) and length_m >= 0 else 0.0
        slope = float(slope_pct) if math.isfinite(slope_pct) else 0.0
        slope_fraction = slope / 100.0
        if self.category == "pedestrian":
            speed_kmh = tobler_walking_speed(slope_fraction, self.base_speed_kmh)
        elif self.key in {"bicycle", "mtb"}:
            speed_kmh = cyclist_speed(slope_fraction, self.base_speed_kmh)
        elif self.key == "scooter":
            speed_kmh = scooter_speed(slope_fraction, self.base_speed_kmh)
        else:
            speed_kmh = vehicle_free_flow_speed(
                hierarchy_rank, slope_pct=slope, base_vehicle_speed_kmh=self.base_speed_kmh
            )
        speed_mps = max(0.2, speed_kmh * 1000.0 / 3600.0)
        return length / speed_mps

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MobilityProfile:
        return cls(**data)


# -------------------------------------------------------------------------
# 15 Standard & Specialized Mobility Profiles
# -------------------------------------------------------------------------

PROFILES: Dict[str, MobilityProfile] = {
    "adult": MobilityProfile(
        key="adult",
        name="Standard Adult",
        category="pedestrian",
        base_speed_kmh=5.0,
        max_slope_pct=25.0,
        stair_allowed=True,
        stair_penalty=1.2,
        slope_sensitivity=1.0,
        heat_sensitivity=0.4,
        green_preference=0.4,
        surface_smoothness_req=0.2,
        hierarchy_weights={1: 2.5, 2: 1.8, 3: 1.2, 4: 1.0, 5: 0.9},
        description="Standard adult pedestrian with normal walking speed and moderate slope tolerance.",
        icon_name="adult",
    ),
    "senior": MobilityProfile(
        key="senior",
        name="Senior / Elderly",
        category="pedestrian",
        base_speed_kmh=3.2,
        max_slope_pct=10.0,
        stair_allowed=True,
        stair_penalty=8.0,
        slope_sensitivity=2.8,
        heat_sensitivity=0.85,
        green_preference=0.9,
        surface_smoothness_req=0.6,
        hierarchy_weights={1: 4.0, 2: 2.5, 3: 1.5, 4: 1.0, 5: 0.8},
        description="Reduced walking pace, high slope avoidance, strong preference for shaded and cool paths.",
        icon_name="senior",
    ),
    "child": MobilityProfile(
        key="child",
        name="Child / Safe Walk",
        category="pedestrian",
        base_speed_kmh=3.5,
        max_slope_pct=12.0,
        stair_allowed=True,
        stair_penalty=2.0,
        slope_sensitivity=1.5,
        heat_sensitivity=0.7,
        green_preference=0.8,
        surface_smoothness_req=0.4,
        hierarchy_weights={1: 8.0, 2: 4.0, 3: 1.8, 4: 1.0, 5: 0.7},
        description="Prioritizes quiet residential streets, green parks, and avoids heavy arterial traffic.",
        icon_name="child",
    ),
    "stroller": MobilityProfile(
        key="stroller",
        name="Stroller / Pram",
        category="pedestrian",
        base_speed_kmh=4.0,
        max_slope_pct=6.0,
        stair_allowed=False,
        stair_penalty=100.0,
        slope_sensitivity=3.0,
        heat_sensitivity=0.6,
        green_preference=0.7,
        surface_smoothness_req=0.8,
        hierarchy_weights={1: 3.5, 2: 2.0, 3: 1.3, 4: 1.0, 5: 0.9},
        description="Strictly avoids steps; enforces smooth pavement and gentle ramps (max 6% grade).",
        icon_name="stroller",
    ),
    "wheelchair": MobilityProfile(
        key="wheelchair",
        name="Wheelchair / Barrier-Free",
        category="pedestrian",
        base_speed_kmh=3.8,
        max_slope_pct=5.0,
        stair_allowed=False,
        stair_penalty=1000.0,
        slope_sensitivity=4.0,
        heat_sensitivity=0.6,
        green_preference=0.6,
        surface_smoothness_req=0.9,
        hierarchy_weights={1: 3.0, 2: 1.8, 3: 1.2, 4: 1.0, 5: 0.9},
        description="Strict universal accessibility: zero stairs, max 5% slope tolerance, smooth continuous surfaces.",
        icon_name="wheelchair",
    ),
    "jogger": MobilityProfile(
        key="jogger",
        name="Runner / Fitness Jogger",
        category="pedestrian",
        base_speed_kmh=9.5,
        max_slope_pct=20.0,
        stair_allowed=True,
        stair_penalty=1.5,
        slope_sensitivity=0.8,
        heat_sensitivity=0.6,
        green_preference=0.85,
        surface_smoothness_req=0.3,
        hierarchy_weights={1: 6.0, 2: 3.0, 3: 1.5, 4: 1.0, 5: 0.7},
        description="Running pace, seeks park pathways, tree shade, and undulating terrain for exercise.",
        icon_name="jogger",
    ),
    "bicycle": MobilityProfile(
        key="bicycle",
        name="City & Commuter Bicycle",
        category="micromobility",
        base_speed_kmh=18.0,
        max_slope_pct=15.0,
        stair_allowed=False,
        stair_penalty=50.0,
        slope_sensitivity=1.8,
        heat_sensitivity=0.3,
        green_preference=0.5,
        surface_smoothness_req=0.6,
        hierarchy_weights={1: 10.0, 2: 1.6, 3: 1.1, 4: 0.9, 5: 1.0},
        description="Grade-aware cycling routing prioritizing dedicated paths, secondary streets, and moderate slopes.",
        icon_name="bicycle",
    ),
    "mtb": MobilityProfile(
        key="mtb",
        name="Mountain / Gravel Bike",
        category="micromobility",
        base_speed_kmh=16.0,
        max_slope_pct=28.0,
        stair_allowed=True,
        stair_penalty=5.0,
        slope_sensitivity=0.9,
        heat_sensitivity=0.2,
        green_preference=0.8,
        surface_smoothness_req=0.1,
        hierarchy_weights={1: 15.0, 2: 2.0, 3: 1.2, 4: 0.9, 5: 0.6},
        description="All-terrain offroad cycling, tolerates steep trails, dirt paths, and steps.",
        icon_name="mtb",
    ),
    "scooter": MobilityProfile(
        key="scooter",
        name="E-Scooter / Micromobility",
        category="micromobility",
        base_speed_kmh=20.0,
        max_slope_pct=12.0,
        stair_allowed=False,
        stair_penalty=100.0,
        slope_sensitivity=2.5,
        heat_sensitivity=0.3,
        green_preference=0.3,
        surface_smoothness_req=0.85,
        hierarchy_weights={1: 10.0, 2: 2.0, 3: 1.2, 4: 0.9, 5: 1.0},
        description="Requires smooth pavement and low curb transitions; limits climbing angles to motor torque bounds.",
        icon_name="scooter",
    ),
    "car": MobilityProfile(
        key="car",
        name="Passenger Car",
        category="vehicle",
        base_speed_kmh=50.0,
        max_slope_pct=25.0,
        stair_allowed=False,
        stair_penalty=1000.0,
        slope_sensitivity=0.5,
        heat_sensitivity=0.0,
        green_preference=0.0,
        surface_smoothness_req=0.5,
        hierarchy_weights={1: 0.6, 2: 0.8, 3: 1.0, 4: 1.5, 5: 2.5},
        description="Vehicular routing prioritizing high-capacity arterials and motorways with realistic speed hierarchy.",
        icon_name="car",
    ),
    "delivery_van": MobilityProfile(
        key="delivery_van",
        name="Delivery Courier Van",
        category="vehicle",
        base_speed_kmh=42.0,
        max_slope_pct=18.0,
        stair_allowed=False,
        stair_penalty=1000.0,
        slope_sensitivity=0.9,
        heat_sensitivity=0.0,
        green_preference=0.0,
        surface_smoothness_req=0.6,
        hierarchy_weights={1: 0.7, 2: 0.8, 3: 1.0, 4: 1.2, 5: 2.0},
        description="Last-mile courier and delivery logistics prioritizing navigable streets and efficient access.",
        icon_name="delivery_van",
    ),
    "truck": MobilityProfile(
        key="truck",
        name="Heavy Goods / Logistics Truck",
        category="vehicle",
        base_speed_kmh=40.0,
        max_slope_pct=7.0,
        stair_allowed=False,
        stair_penalty=1000.0,
        slope_sensitivity=3.5,
        heat_sensitivity=0.0,
        green_preference=0.0,
        surface_smoothness_req=0.7,
        hierarchy_weights={1: 0.5, 2: 0.7, 3: 1.2, 4: 3.0, 5: 10.0},
        description="Heavy commercial vehicles: strict 7% grade limit, wide turning radii, avoids narrow urban corridors.",
        icon_name="truck",
    ),
    "paramedic": MobilityProfile(
        key="paramedic",
        name="Emergency / First Responder",
        category="vehicle",
        base_speed_kmh=65.0,
        max_slope_pct=22.0,
        stair_allowed=False,
        stair_penalty=1000.0,
        slope_sensitivity=0.4,
        heat_sensitivity=0.0,
        green_preference=0.0,
        surface_smoothness_req=0.4,
        hierarchy_weights={1: 0.5, 2: 0.6, 3: 0.8, 4: 1.0, 5: 1.5},
        description="Fastest emergency response routing across major corridors with priority access.",
        icon_name="paramedic",
    ),
    "sightseer": MobilityProfile(
        key="sightseer",
        name="Scenic & Panoramic Walk",
        category="pedestrian",
        base_speed_kmh=4.2,
        max_slope_pct=20.0,
        stair_allowed=True,
        stair_penalty=1.0,
        slope_sensitivity=0.5,
        heat_sensitivity=0.4,
        green_preference=1.0,
        surface_smoothness_req=0.3,
        hierarchy_weights={1: 8.0, 2: 4.0, 3: 2.0, 4: 1.0, 5: 0.6},
        description="Tourist and leisure walking prioritizing viewpoint ridges, historic alleys, and parks.",
        icon_name="sightseer",
    ),
    "night_walk": MobilityProfile(
        key="night_walk",
        name="Safe & Illuminated Night Walk",
        category="pedestrian",
        base_speed_kmh=4.8,
        max_slope_pct=15.0,
        stair_allowed=True,
        stair_penalty=3.0,
        slope_sensitivity=1.2,
        heat_sensitivity=0.0,
        green_preference=0.2,
        surface_smoothness_req=0.7,
        hierarchy_weights={1: 1.2, 2: 1.0, 3: 1.0, 4: 1.4, 5: 4.0},
        description="Night safety profile staying on lit, active main urban streets and avoiding isolated dark paths.",
        icon_name="night_walk",
    ),
}


PROFILE_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "pedestrian": {
        "title": "Pedestrian & Active Walking",
        "icon": "🚶",
        "keys": ["adult", "senior", "child", "jogger", "sightseer", "night_walk"],
    },
    "accessibility": {
        "title": "Barrier-Free & Universal Access",
        "icon": "♿",
        "keys": ["wheelchair", "stroller"],
    },
    "micromobility": {
        "title": "Micromobility & Cycling",
        "icon": "🚲",
        "keys": ["bicycle", "mtb", "scooter"],
    },
    "vehicle": {
        "title": "Vehicular & Logistics",
        "icon": "🚗",
        "keys": ["car", "delivery_van", "truck", "paramedic"],
    },
}

PROFILE_COLORS: Dict[str, str] = {
    "adult": "#0284c7",
    "senior": "#059669",
    "child": "#f59e0b",
    "jogger": "#10b981",
    "sightseer": "#84cc16",
    "night_walk": "#6366f1",
    "wheelchair": "#8b5cf6",
    "stroller": "#d946ef",
    "bicycle": "#06b6d4",
    "mtb": "#14b8a6",
    "scooter": "#3b82f6",
    "car": "#ef4444",
    "delivery_van": "#f97316",
    "truck": "#78716c",
    "paramedic": "#e11d48",
}


def get_profile(key: str) -> MobilityProfile:
    """Retrieve profile by key, falling back to 'adult' if unknown."""
    return PROFILES.get(key.lower(), PROFILES["adult"])


def get_profile_color(key: str) -> str:
    """Return the designated HEX color for a profile key."""
    return PROFILE_COLORS.get(key.lower(), "#0ea5e9")


def list_profile_keys() -> List[str]:
    """Return all registered profile keys."""
    return list(PROFILES.keys())


def list_profile_keys_for_group(group_key: str) -> List[str]:
    """Return profile keys belonging to a category group ('all', 'pedestrian', 'accessibility', 'micromobility', 'vehicle')."""
    if group_key.lower() == "all":
        return list_profile_keys()
    if group_key.lower() in PROFILE_CATEGORIES:
        return PROFILE_CATEGORIES[group_key.lower()]["keys"]
    return [group_key.lower()] if group_key.lower() in PROFILES else ["adult"]


def save_custom_profile_json(profile: MobilityProfile, target_path: Path) -> None:
    """Save custom profile to JSON preset file."""
    target_path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")


def load_custom_profile_json(source_path: Path) -> MobilityProfile:
    """Load custom profile from JSON preset file."""
    data = json.loads(source_path.read_text(encoding="utf-8"))
    return MobilityProfile.from_dict(data)
