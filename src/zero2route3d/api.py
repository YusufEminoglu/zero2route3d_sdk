"""High-level, single-call functional API for zero2route3d.

Enables fast, one-line spatial mobility calculations directly from coordinates,
GeoJSON files, or GeoPandas DataFrames without manual engine instantiation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .environmental_raster import EnvironmentalSurfaceSampler, MCDAWeights
from .isochrone_engine import IsochroneEngine3D, IsochroneResult
from .map_matching_3d import GPXPoint, HMMMapMatcher3D, MapMatching3DResult
from .mobility_profiles import MobilityProfile, resolve_profile
from .network_source import NetworkSourceManager, RoadSegment
from .pareto_router import ParetoFrontierResult, ParetoMultiObjectiveRouter
from .routing_engine import RouteResult3D, RoutingEngine3D, Waypoint

#: Anything the helpers below accept as a road network.
NetworkInput = Union[str, Path, Sequence[RoadSegment], Dict[str, Any], Any]
#: A registered profile key, or a ready-made (possibly custom) MobilityProfile.
ProfileInput = Union[str, MobilityProfile]

__all__ = [
    "NetworkInput",
    "ProfileInput",
    "match_gps_track_3d",
    "solve_3d_isochrones",
    "solve_3d_route",
    "solve_4d_pareto_frontier",
]


def _load_network(network_input: NetworkInput) -> List[RoadSegment]:
    """Parse road segments from a filepath, GeoJSON dict, segment list or GeoDataFrame.

    Raises ValueError / FileNotFoundError for input that cannot be interpreted.
    Returning an empty network instead would push the failure downstream, where
    it resurfaces as a misleading "could not snap origin to network graph".
    """
    if isinstance(network_input, (list, tuple)) and network_input:
        if all(isinstance(item, RoadSegment) for item in network_input):
            return list(network_input)
        raise ValueError(
            "A network given as a sequence must contain RoadSegment objects; got "
            f"{type(network_input[0]).__name__}."
        )

    mgr = NetworkSourceManager()
    if isinstance(network_input, (str, Path)):
        path = Path(network_input)
        if not path.exists():
            raise FileNotFoundError(f"Network file not found: {path}")
        if path.suffix.lower() not in (".json", ".geojson"):
            raise ValueError(
                f"Unsupported network file type '{path.suffix}'. Provide a "
                ".geojson/.json file, a GeoJSON dict, a GeoDataFrame, or a list "
                "of RoadSegment objects."
            )
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return mgr.extract_from_geojson(data)

    if isinstance(network_input, dict):
        return mgr.extract_from_geojson(network_input)

    # geopandas.GeoDataFrame, duck-typed so geopandas stays an optional import.
    if hasattr(network_input, "geometry") and hasattr(network_input, "iterfeatures"):
        from .integrations import from_geodataframe

        return from_geodataframe(network_input)

    raise ValueError(
        f"Unsupported network input of type {type(network_input).__name__}. Provide "
        "a GeoJSON path or dict, a geopandas.GeoDataFrame, or a list of RoadSegment "
        "objects."
    )


def _build_engine(
    network: NetworkInput,
    dem_sampler: Optional[EnvironmentalSurfaceSampler] = None,
    mcda_weights: Optional[MCDAWeights] = None,
    fetch_online_dem: bool = False,
) -> RoutingEngine3D:
    """Load a network into a routing engine, optionally warming the elevation cache."""
    segments = _load_network(network)
    if not segments:
        raise ValueError("The supplied network contains no usable road segments.")

    sampler = dem_sampler or EnvironmentalSurfaceSampler()
    if fetch_online_dem and not sampler.has_elevation_source:
        coords = sorted(
            {(round(pt[0], 5), round(pt[1], 5)) for seg in segments for pt in (seg.p1, seg.p2)}
        )
        sampler.prefetch_elevations(coords)

    engine = RoutingEngine3D(sampler=sampler, weights=mcda_weights)
    engine.build_graph(segments)
    return engine


def _to_waypoint(pt: Any, name: str = "") -> Waypoint:
    """Coerce a (lon, lat[, elev]) tuple or a Waypoint into a Waypoint."""
    if isinstance(pt, Waypoint):
        return pt
    if isinstance(pt, (tuple, list)) and len(pt) >= 2:
        return Waypoint(
            lon=float(pt[0]),
            lat=float(pt[1]),
            elevation_m=float(pt[2]) if len(pt) > 2 else 0.0,
            name=name,
        )
    raise ValueError(f"Invalid waypoint {pt!r}: expected (lon, lat[, elevation]) or a Waypoint.")


def solve_3d_route(
    origin: Union[Tuple[float, float], Tuple[float, float, float], Waypoint],
    destination: Union[Tuple[float, float], Tuple[float, float, float], Waypoint],
    network: NetworkInput,
    profile: ProfileInput = "adult",
    dem_sampler: Optional[EnvironmentalSurfaceSampler] = None,
    mcda_weights: Optional[MCDAWeights] = None,
    intermediate_stops: Optional[Sequence[Union[Tuple[float, float], Waypoint]]] = None,
    optimize_stops_order: bool = False,
    fetch_online_dem: bool = False,
) -> RouteResult3D:
    """Solve a multi-criteria 3D least-cost route in a single call.

    Args:
        origin: Start (lon, lat) or (lon, lat, elev) or Waypoint.
        destination: End (lon, lat) or (lon, lat, elev) or Waypoint.
        network: Road network GeoJSON filepath, dictionary, GeoDataFrame, or RoadSegment list.
        profile: Profile key (e.g. 'adult', 'wheelchair', 'bicycle') or a MobilityProfile
            instance -- including a custom one, which is now honoured rather than
            silently replaced by the default profile.
        dem_sampler: Optional environmental/elevation raster sampler.
        mcda_weights: Optional AHP multi-criteria weighting configuration.
        intermediate_stops: Optional intermediate waypoints.
        optimize_stops_order: Solve TSP tour over intermediate stops if True.
        fetch_online_dem: Query Open-Elevation once for every network node when no
            DEM raster is configured. Needs network access; without it (and without
            a DEM) the route is computed on flat terrain.

    Returns:
        RouteResult3D containing 3D coordinates, elevation profile, and rich kinematic statistics.

    Raises:
        ValueError: if the network or the profile cannot be interpreted.
    """
    resolved_profile = resolve_profile(profile, strict=True)
    engine = _build_engine(network, dem_sampler, mcda_weights, fetch_online_dem)

    waypoints = [_to_waypoint(origin, "Origin")]
    if intermediate_stops:
        for idx, stop in enumerate(intermediate_stops, start=1):
            waypoints.append(_to_waypoint(stop, f"Stop {idx}"))
    waypoints.append(_to_waypoint(destination, "Destination"))

    return engine.calculate_route(
        waypoints, profile_key=resolved_profile, optimize_tsp=optimize_stops_order
    )


def solve_3d_isochrones(
    center: Union[Tuple[float, float], Waypoint],
    network: NetworkInput,
    profile: ProfileInput = "adult",
    time_intervals_min: Sequence[float] = (5.0, 10.0, 15.0),
    dem_sampler: Optional[EnvironmentalSurfaceSampler] = None,
    fetch_online_dem: bool = False,
) -> IsochroneResult:
    """Compute anisotropic 3D isochrone travel-time wavefront bands from a center point."""
    resolved_profile = resolve_profile(profile, strict=True)
    engine = _build_engine(network, dem_sampler, None, fetch_online_dem)

    origin_wp = _to_waypoint(center, "Center")

    iso_engine = IsochroneEngine3D(engine)
    return iso_engine.compute_isochrones(
        origin_wp, profile_key=resolved_profile, time_intervals_min=time_intervals_min
    )


def solve_4d_pareto_frontier(
    origin: Union[Tuple[float, float], Waypoint],
    destination: Union[Tuple[float, float], Waypoint],
    network: NetworkInput,
    profile: ProfileInput = "bicycle",
    dem_sampler: Optional[EnvironmentalSurfaceSampler] = None,
    fetch_online_dem: bool = False,
) -> ParetoFrontierResult:
    """Compute non-dominated 4D Pareto frontier trade-offs across Time, Climb, Heat, and Calories."""
    resolved_profile = resolve_profile(profile, strict=True)
    engine = _build_engine(network, dem_sampler, None, fetch_online_dem)

    start_wp = _to_waypoint(origin, "Origin")
    end_wp = _to_waypoint(destination, "Destination")

    start_node = engine.find_nearest_node((start_wp.lon, start_wp.lat))
    end_node = engine.find_nearest_node((end_wp.lon, end_wp.lat))

    if start_node is None or end_node is None:
        raise ValueError("Could not snap origin or destination to network graph.")

    pareto_router = ParetoMultiObjectiveRouter(engine.nodes, engine.adj, engine.sampler)
    return pareto_router.solve_pareto_frontier(start_node, end_node, profile_key=resolved_profile)


def match_gps_track_3d(
    gpx_points: Sequence[Union[GPXPoint, Tuple[float, float], Tuple[float, float, float]]],
    network: NetworkInput,
    sigma_z: float = 4.07,
    beta: float = 3.0,
) -> MapMatching3DResult:
    """Match noisy GPS/GPX track coordinates onto the 3D road network via HMM Viterbi decoding.

    Args:
        gpx_points: GPXPoint objects or (lon, lat[, elevation]) tuples.
        network: Road network, in any form accepted by the other helpers.
        sigma_z: GPS emission standard deviation in metres.
        beta: Transition-probability scale for route-vs-crow-fly distance.
    """
    engine = _build_engine(network)

    pts: List[GPXPoint] = []
    for p in gpx_points:
        if isinstance(p, GPXPoint):
            pts.append(p)
        elif isinstance(p, (tuple, list)) and len(p) >= 2:
            pts.append(
                GPXPoint(
                    lon=float(p[0]),
                    lat=float(p[1]),
                    elevation_raw_m=float(p[2]) if len(p) > 2 else 0.0,
                )
            )
        else:
            raise ValueError(f"Invalid GPS point {p!r}: expected (lon, lat[, elevation]).")

    matcher = HMMMapMatcher3D(engine.nodes, engine.adj, sigma_z=sigma_z, beta=beta)
    return matcher.match_gps_track(pts)
