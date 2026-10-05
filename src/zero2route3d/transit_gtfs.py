# -*- coding: utf-8 -*-
"""Dynamic GTFS & Timetable-Aware Multimodal Public Transit Router for 02Route 3D."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class GTFSStop:
    stop_id: str
    stop_name: str
    lat: float
    lon: float
    elevation: float = 0.0


@dataclass
class GTFSTripStopTime:
    trip_id: str
    stop_id: str
    arrival_time_s: int  # Seconds from midnight (e.g. 08:30:00 = 30600)
    departure_time_s: int
    stop_sequence: int


@dataclass
class GTFSRoute:
    route_id: str
    short_name: str
    long_name: str
    route_type: int  # 0=Tram, 1=Subway, 2=Rail, 3=Bus, 4=Ferry


@dataclass
class TransitLeg:
    """A single scheduled transit or access leg in a multimodal journey."""

    mode: str  # 'WALK', 'BUS', 'SUBWAY', 'TRAM', 'FERRY'
    from_stop_id: str
    to_stop_id: str
    from_stop_name: str
    to_stop_name: str
    departure_time_s: int
    arrival_time_s: int
    duration_min: float
    distance_m: float
    route_name: str = ""
    trip_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "from_stop": self.from_stop_name,
            "to_stop": self.to_stop_name,
            "departure": _format_seconds_to_time(self.departure_time_s),
            "arrival": _format_seconds_to_time(self.arrival_time_s),
            "duration_min": round(self.duration_min, 1),
            "distance_m": round(self.distance_m, 1),
            "route": self.route_name,
        }


@dataclass
class TransitJourneyResult:
    """Complete timetable-optimal journey."""

    origin: tuple[float, float]
    destination: tuple[float, float]
    departure_time: str
    arrival_time: str
    total_duration_min: float
    total_transit_time_min: float
    total_walking_time_min: float
    total_transfers: int
    legs: list[TransitLeg]

    def to_dict(self) -> dict[str, Any]:
        return {
            "departure_time": self.departure_time,
            "arrival_time": self.arrival_time,
            "total_duration_min": round(self.total_duration_min, 1),
            "total_transit_time_min": round(self.total_transit_time_min, 1),
            "total_walking_time_min": round(self.total_walking_time_min, 1),
            "total_transfers": self.total_transfers,
            "legs": [leg.to_dict() for leg in self.legs],
        }


def _time_str_to_seconds(time_str: str) -> int:
    """Convert 'HH:MM:SS' to seconds from midnight."""
    parts = [int(p) for p in time_str.strip().split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 3600 + parts[1] * 60
    return 0


def _format_seconds_to_time(seconds: int) -> str:
    """Format seconds from midnight to 'HH:MM:SS'."""
    h = (seconds // 3600) % 24
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _haversine_meters(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Haversine distance in meters between (lat, lon) pairs."""
    r = 6371000.0
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    return 2.0 * r * math.asin(math.sqrt(max(0.0, min(1.0, a))))


class GTFSFeedReader:
    """Lightweight in-memory GTFS Schedule parser."""

    def __init__(self) -> None:
        self.stops: dict[str, GTFSStop] = {}
        self.routes: dict[str, GTFSRoute] = {}
        self.stop_times: dict[str, list[GTFSTripStopTime]] = {}  # trip_id -> stop_times sorted by sequence

    def add_stop(self, stop_id: str, name: str, lat: float, lon: float, elevation: float = 0.0) -> None:
        self.stops[stop_id] = GTFSStop(stop_id=stop_id, stop_name=name, lat=lat, lon=lon, elevation=elevation)

    def add_route(self, route_id: str, short_name: str, long_name: str, route_type: int = 3) -> None:
        self.routes[route_id] = GTFSRoute(route_id=route_id, short_name=short_name, long_name=long_name, route_type=route_type)

    def add_trip_stop(self, trip_id: str, stop_id: str, arrival_time: str, departure_time: str, seq: int) -> None:
        arr_s = _time_str_to_seconds(arrival_time)
        dep_s = _time_str_to_seconds(departure_time)
        st = GTFSTripStopTime(trip_id=trip_id, stop_id=stop_id, arrival_time_s=arr_s, departure_time_s=dep_s, stop_sequence=seq)
        if trip_id not in self.stop_times:
            self.stop_times[trip_id] = []
        self.stop_times[trip_id].append(st)
        self.stop_times[trip_id].sort(key=lambda item: item.stop_sequence)


class TimetableTransitRouter:
    """Connection Scan / Timetable search routing engine."""

    def __init__(self, feed: GTFSFeedReader, walking_speed_kmh: float = 4.5) -> None:
        self.feed = feed
        self.walk_speed_ms = (walking_speed_kmh * 1000.0) / 3600.0

    def route_timetable(
        self,
        origin_lat_lon: tuple[float, float],
        destination_lat_lon: tuple[float, float],
        departure_time_str: str = "08:00:00",
        max_access_walk_meters: float = 1200.0,
    ) -> TransitJourneyResult:
        """Find the earliest-arrival journey between coordinates using scheduled transit.

        Args:
            origin_lat_lon: (lat, lon) of starting point.
            destination_lat_lon: (lat, lon) of destination.
            departure_time_str: Desired departure time 'HH:MM:SS'.
            max_access_walk_meters: Max walking distance to nearest transit stops.
        """
        dep_s = _time_str_to_seconds(departure_time_str)

        # 1. Direct walk baseline
        direct_walk_dist = _haversine_meters(origin_lat_lon, destination_lat_lon)
        direct_walk_time_s = int(direct_walk_dist / max(0.5, self.walk_speed_ms))

        best_journey = TransitJourneyResult(
            origin=origin_lat_lon,
            destination=destination_lat_lon,
            departure_time=departure_time_str,
            arrival_time=_format_seconds_to_time(dep_s + direct_walk_time_s),
            total_duration_min=direct_walk_time_s / 60.0,
            total_transit_time_min=0.0,
            total_walking_time_min=direct_walk_time_s / 60.0,
            total_transfers=0,
            legs=[
                TransitLeg(
                    mode="WALK",
                    from_stop_id="ORIGIN",
                    to_stop_id="DESTINATION",
                    from_stop_name="Origin",
                    to_stop_name="Destination",
                    departure_time_s=dep_s,
                    arrival_time_s=dep_s + direct_walk_time_s,
                    duration_min=direct_walk_time_s / 60.0,
                    distance_m=direct_walk_dist,
                    route_name="Walking Path",
                )
            ],
        )

        # 2. Find nearby boarding stops within walk threshold
        boarding_stops: list[tuple[GTFSStop, float, int]] = []  # (stop, dist, walk_time_s)
        for s in self.feed.stops.values():
            dist = _haversine_meters(origin_lat_lon, (s.lat, s.lon))
            if dist <= max_access_walk_meters:
                w_time = int(dist / max(0.5, self.walk_speed_ms))
                boarding_stops.append((s, dist, w_time))

        # Find nearby alighting stops within walk threshold of destination
        alighting_stops: list[tuple[GTFSStop, float, int]] = []
        for s in self.feed.stops.values():
            dist = _haversine_meters((s.lat, s.lon), destination_lat_lon)
            if dist <= max_access_walk_meters:
                w_time = int(dist / max(0.5, self.walk_speed_ms))
                alighting_stops.append((s, dist, w_time))

        if not boarding_stops or not alighting_stops:
            return best_journey

        # 3. Scan trips matching boarding and alighting
        best_arr_time_s = dep_s + direct_walk_time_s

        for b_stop, b_dist, b_walk_s in boarding_stops:
            earliest_board_s = dep_s + b_walk_s

            for a_stop, a_dist, a_walk_s in alighting_stops:
                if b_stop.stop_id == a_stop.stop_id:
                    continue

                for trip_id, st_list in self.feed.stop_times.items():
                    # Check if both stops are on this trip in sequence
                    b_st = None
                    a_st = None
                    for st in st_list:
                        if st.stop_id == b_stop.stop_id and st.departure_time_s >= earliest_board_s:
                            b_st = st
                        elif b_st is not None and st.stop_id == a_stop.stop_id:
                            a_st = st
                            break

                    if b_st and a_st:
                        final_arr_s = a_st.arrival_time_s + a_walk_s
                        if final_arr_s < best_arr_time_s:
                            best_arr_time_s = final_arr_s
                            # Build legs
                            leg1_walk = TransitLeg(
                                mode="WALK",
                                from_stop_id="ORIGIN",
                                to_stop_id=b_stop.stop_id,
                                from_stop_name="Origin",
                                to_stop_name=b_stop.stop_name,
                                departure_time_s=dep_s,
                                arrival_time_s=dep_s + b_walk_s,
                                duration_min=b_walk_s / 60.0,
                                distance_m=b_dist,
                                route_name="Access Walk",
                            )
                            transit_duration = (a_st.arrival_time_s - b_st.departure_time_s) / 60.0
                            transit_dist = _haversine_meters((b_stop.lat, b_stop.lon), (a_stop.lat, a_stop.lon))
                            leg2_transit = TransitLeg(
                                mode="TRANSIT",
                                from_stop_id=b_stop.stop_id,
                                to_stop_id=a_stop.stop_id,
                                from_stop_name=b_stop.stop_name,
                                to_stop_name=a_stop.stop_name,
                                departure_time_s=b_st.departure_time_s,
                                arrival_time_s=a_st.arrival_time_s,
                                duration_min=transit_duration,
                                distance_m=transit_dist,
                                route_name=f"Trip {trip_id}",
                                trip_id=trip_id,
                            )
                            leg3_egress = TransitLeg(
                                mode="WALK",
                                from_stop_id=a_stop.stop_id,
                                to_stop_id="DESTINATION",
                                from_stop_name=a_stop.stop_name,
                                to_stop_name="Destination",
                                departure_time_s=a_st.arrival_time_s,
                                arrival_time_s=final_arr_s,
                                duration_min=a_walk_s / 60.0,
                                distance_m=a_dist,
                                route_name="Egress Walk",
                            )

                            total_dur = (final_arr_s - dep_s) / 60.0
                            total_walk = (b_walk_s + a_walk_s) / 60.0

                            best_journey = TransitJourneyResult(
                                origin=origin_lat_lon,
                                destination=destination_lat_lon,
                                departure_time=departure_time_str,
                                arrival_time=_format_seconds_to_time(final_arr_s),
                                total_duration_min=total_dur,
                                total_transit_time_min=transit_duration,
                                total_walking_time_min=total_walk,
                                total_transfers=0,
                                legs=[leg1_walk, leg2_transit, leg3_egress],
                            )

        return best_journey
