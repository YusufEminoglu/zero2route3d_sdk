"""Multi-modal trip planning and intermodal route chaining engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from .kinematics import haversine_distance_2d
from .mobility_profiles import MobilityProfile, get_profile
from .routing_engine import RouteResult3D, RoutingEngine3D, Waypoint


@dataclass
class MultiModalLeg:
    """Individual segment in a multi-modal journey (e.g. walk -> transit -> walk)."""

    leg_index: int
    mode_name: str
    profile: MobilityProfile
    start_point: Waypoint
    end_point: Waypoint
    route_result: RouteResult3D
    transfer_penalty_min: float = 3.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leg_index": self.leg_index,
            "mode_name": self.mode_name,
            "profile_name": self.profile.name,
            "distance_km": self.route_result.statistics.total_distance_km,
            "duration_min": self.route_result.statistics.total_duration_min,
            "transfer_penalty_min": self.transfer_penalty_min,
            "total_leg_time_min": round(
                self.route_result.statistics.total_duration_min + self.transfer_penalty_min, 1
            ),
            "climb_m": self.route_result.statistics.elevation_gain_m,
        }


@dataclass
class MultiModalJourney:
    """Complete multi-modal chained trip with multiple transport modes."""

    legs: List[MultiModalLeg]
    total_distance_km: float
    total_duration_min: float
    total_climb_m: float
    total_calories_kcal: float
    transfer_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_distance_km": round(self.total_distance_km, 2),
            "total_duration_min": round(self.total_duration_min, 1),
            "total_climb_m": round(self.total_climb_m, 1),
            "total_calories_kcal": round(self.total_calories_kcal, 0),
            "transfer_count": self.transfer_count,
            "legs": [leg.to_dict() for leg in self.legs],
        }


class MultiModalRouter:
    """Chains multiple transport modes across intermediate hubs and transit stops."""

    def __init__(self, routing_engine: RoutingEngine3D) -> None:
        self.engine = routing_engine

    def calculate_multimodal_trip(
        self,
        origin: Waypoint,
        destination: Waypoint,
        transit_hubs: Sequence[Waypoint],
        access_mode: str = "adult",
        main_mode: str = "bicycle",
        egress_mode: str = "adult",
    ) -> MultiModalJourney:
        """Calculate a 3-leg journey: Access -> Main Transit/Bike -> Egress."""
        if not transit_hubs or len(transit_hubs) < 2:
            # Fallback to direct routing if no hubs
            res = self.engine.calculate_route([origin, destination], profile_key=access_mode)
            single_leg = MultiModalLeg(
                leg_index=1,
                mode_name="Direct Access",
                profile=get_profile(access_mode),
                start_point=origin,
                end_point=destination,
                route_result=res,
                transfer_penalty_min=0.0,
            )
            return MultiModalJourney(
                legs=[single_leg],
                total_distance_km=res.statistics.total_distance_km,
                total_duration_min=res.statistics.total_duration_min,
                total_climb_m=res.statistics.elevation_gain_m,
                total_calories_kcal=res.statistics.total_calories_kcal,
                transfer_count=0,
            )

        # Select closest transit hub to origin and destination
        hub_access = min(
            transit_hubs,
            key=lambda h: haversine_distance_2d((origin.lon, origin.lat), (h.lon, h.lat)),
        )
        hub_egress = min(
            transit_hubs,
            key=lambda h: haversine_distance_2d((destination.lon, destination.lat), (h.lon, h.lat)),
        )

        legs: List[MultiModalLeg] = []

        # Leg 1: Walk to Hub
        res1 = self.engine.calculate_route([origin, hub_access], profile_key=access_mode)
        legs.append(
            MultiModalLeg(
                1,
                "Access Walk",
                get_profile(access_mode),
                origin,
                hub_access,
                res1,
                transfer_penalty_min=2.0,
            )
        )

        # Leg 2: Main Transit / Bike Leg
        res2 = self.engine.calculate_route([hub_access, hub_egress], profile_key=main_mode)
        legs.append(
            MultiModalLeg(
                2,
                "Transit / Bike Ride",
                get_profile(main_mode),
                hub_access,
                hub_egress,
                res2,
                transfer_penalty_min=3.0,
            )
        )

        # Leg 3: Egress Walk to Final Destination
        res3 = self.engine.calculate_route([hub_egress, destination], profile_key=egress_mode)
        legs.append(
            MultiModalLeg(
                3,
                "Egress Walk",
                get_profile(egress_mode),
                hub_egress,
                destination,
                res3,
                transfer_penalty_min=0.0,
            )
        )

        tot_dist = sum(leg.route_result.statistics.total_distance_km for leg in legs)
        tot_time = sum(
            leg.route_result.statistics.total_duration_min + leg.transfer_penalty_min
            for leg in legs
        )
        tot_climb = sum(leg.route_result.statistics.elevation_gain_m for leg in legs)
        tot_kcal = sum(leg.route_result.statistics.total_calories_kcal for leg in legs)

        return MultiModalJourney(
            legs=legs,
            total_distance_km=tot_dist,
            total_duration_min=tot_time,
            total_climb_m=tot_climb,
            total_calories_kcal=tot_kcal,
            transfer_count=len(legs) - 1,
        )
