"""02Route 3D SDK — Multi-Criteria 3D Kinematic & Spatial Mobility Analytics Library."""

from __future__ import annotations

__version__ = "0.9.0"
__author__ = "Yusuf Eminoğlu"
__email__ = "yusufeminoglu@gmail.com"

from .accessibility_equity import (
    AccessibilityEquityEngine,
    EquityScorecardResult,
    SupplyFacility,
    ZoneAccessibilityRecord,
)
from .ahp_engine import AHPEngine, AHPResult
from .api import (
    match_gps_track_3d,
    solve_3d_isochrones,
    solve_3d_route,
    solve_4d_pareto_frontier,
)
from .aquaplaning_hydroplaning_risk import (
    HydroplaningRiskResult,
    PavementCrossSlopeProfile,
    evaluate_road_hydroplaning_risk,
)
from .basemap import add_osm_basemap
from .biomechanics import (
    BiomechanicalKinematicsTracker,
    BiomechanicalSegmentResult,
    BiomechanicalTrailSummary,
)
from .copernicus_dem import CopernicusDemError, CopernicusDemTileSource
from .co2_emission_routing import (
    EmissionAssessmentResult,
    VehicleEmissionProfile,
    calculate_route_co2_emissions,
)
from .dem_fetcher import NODATA, GlobalDemFetcher
from .drone_airspace_corridor import (
    AirCorridorResult,
    DroneAirspaceProfile,
    GeofencedNoFlyZone,
    solve_3d_drone_flight_corridor,
)
from .emergency_air_ambulance_landing import (
    HelicopterApproachSlope,
    LandingZoneResult,
    evaluate_helicopter_landing_zones,
)
from .environmental_raster import EnvironmentalSurfaceSampler, MCDAWeights
from .ev_energy import (
    EVBatteryProfile,
    EVEnergySimulator,
    EVRouteEnergyResult,
    EVSegmentEnergy,
    solve_ev_energy_route,
)
from .evacuation import EvacuationPlan, EvacuationRouter, HazardZone
from .gradient_braking_safety import (
    BrakeThermalProfile,
    DescentSafetyResult,
    evaluate_steep_descent_brake_fade,
)
from .hazard_evacuation import (
    DynamicHazardZone,
    EvacuationPath3D,
    EvacuationRouteResult,
    solve_3d_evacuation_routes,
)
from .heavy_haulage_swept_path import (
    SuperloadVehicleProfile,
    SweptPathResult,
    calculate_swept_path_envelope,
)
from .html_bundler import StandaloneHtmlBundler
from .micromobility_kinetics import (
    MicroMobilityRouteScore,
    VibrationalComfortResult,
    evaluate_micro_mobility_comfort,
)
from .transit_gtfs import (
    GTFSFeedReader,
    GTFSRoute,
    GTFSStop,
    TimetableTransitRouter,
    TransitJourneyResult,
    TransitLeg,
)
from .thermal_engine_heat_soak import (
    EngineHeatProfile,
    PowertrainThermalResult,
    simulate_powertrain_thermal_load,
)
from .time_dependent_isochrones import (
    DynamicIsochroneRing,
    DynamicIsochroneResult,
    HourlyCongestionFactor,
    solve_time_dependent_isochrones,
)
from .truck_clearance import (
    BridgeClearanceObstacle,
    TruckRestrictionProfile,
    TruckRouteFeasibilityResult,
    solve_heavy_vehicle_route3d,
)
from .voice_guidance import (
    ManeuverInstruction3D,
    TurnByTurn3DRouteGuide,
    generate_3d_turn_by_turn_cues,
)
from .weather_routing import (
    HeadwindResistanceResult,
    WeatherRouteSummary,
    compute_apparent_wind_resistance,
)
from .html_bundler import StandaloneHtmlBundler
from .integrations import (
    from_geodataframe,
    sample_rasterio_dem,
    to_geodataframe,
    to_networkx_digraph,
    to_shapely_linestring,
)
from .isochrone_engine import IsochroneBand, IsochroneEngine3D, IsochroneResult
from .kinematics import (
    aerodynamic_drag_power,
    cycling_energy_cost,
    cyclist_speed,
    haversine_distance_2d,
    haversine_distance_3d,
    minetti_energy_cost,
    rolling_resistance_force,
    scooter_speed,
    senior_fatigue_decay,
    solar_irradiance_aspect_factor,
    tobler_walking_speed,
    universal_thermal_comfort_utci,
    vehicle_free_flow_speed,
)
from .map_matching_3d import (
    GPXPoint,
    HMMMapMatcher3D,
    MapMatching3DResult,
    MatchedTrackPoint3D,
)
from .micro_elevation import (
    BicubicSurfaceInterpolator,
    IDWSurfaceInterpolator,
    MicroElevationEngine,
    SurfaceGradient3D,
)
from .mobility_profiles import (
    PROFILE_CATEGORIES,
    PROFILES,
    MobilityProfile,
    UnknownProfileError,
    get_profile,
    get_profile_color,
    list_profile_keys,
    list_profile_keys_for_group,
    load_custom_profile_json,
    resolve_profile,
    save_custom_profile_json,
)
from .multimodal import MultiModalJourney, MultiModalLeg, MultiModalRouter
from .network_source import NetworkSourceError, NetworkSourceManager, RoadSegment
from .osm_downloader import OsmBuilding, OsmDataFetcher
from .pareto_router import (
    ParetoCostVector,
    ParetoFrontierResult,
    ParetoMultiObjectiveRouter,
    ParetoRouteSolution,
)
from .plotting import (
    plot_elevation_profile,
    plot_lorenz_equity_curve,
    plot_pareto_frontier_2d,
)
from .profile_dxf import export_route_to_dxf_3d
from .profile_stats import (
    CueInstruction,
    RouteStatistics,
    compute_route_statistics,
    densify_3d_linestring,
    generate_cue_sheet,
    smooth_elevation_series,
)
from .qml_generator import generate_route_qml_style
from .raster_source import GeoTiffRasterSource, RasterSourceError
from .report_generator import generate_analytical_report_html
from .route_corridor_3d import filter_buildings_in_corridor
from .routing_engine import RouteResult3D, RoutingEngine3D, Waypoint
from .solar_shadow import (
    ShadeExposureReport,
    SolarPosition,
    calculate_solar_position,
    compute_shade_exposure_along_route,
)
from .tsp_solver import solve_tsp_order

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "AccessibilityEquityEngine",
    "EquityScorecardResult",
    "SupplyFacility",
    "ZoneAccessibilityRecord",
    "AHPEngine",
    "AHPResult",
    "add_osm_basemap",
    "solve_3d_route",
    "solve_3d_isochrones",
    "solve_4d_pareto_frontier",
    "match_gps_track_3d",
    "to_geodataframe",
    "from_geodataframe",
    "to_networkx_digraph",
    "to_shapely_linestring",
    "sample_rasterio_dem",
    "plot_elevation_profile",
    "plot_pareto_frontier_2d",
    "plot_lorenz_equity_curve",
    "CopernicusDemError",
    "CopernicusDemTileSource",
    "GlobalDemFetcher",
    "GeoTiffRasterSource",
    "RasterSourceError",
    "NODATA",
    "EnvironmentalSurfaceSampler",
    "MCDAWeights",
    "EvacuationPlan",
    "EvacuationRouter",
    "HazardZone",
    "StandaloneHtmlBundler",
    "IsochroneBand",
    "IsochroneEngine3D",
    "IsochroneResult",
    "GPXPoint",
    "HMMMapMatcher3D",
    "MapMatching3DResult",
    "MatchedTrackPoint3D",
    "BicubicSurfaceInterpolator",
    "IDWSurfaceInterpolator",
    "MicroElevationEngine",
    "SurfaceGradient3D",
    "MultiModalJourney",
    "MultiModalLeg",
    "MultiModalRouter",
    "ParetoCostVector",
    "ParetoFrontierResult",
    "ParetoMultiObjectiveRouter",
    "ParetoRouteSolution",
    "export_route_to_dxf_3d",
    "generate_analytical_report_html",
    "generate_route_qml_style",
    "calculate_solar_position",
    "compute_shade_exposure_along_route",
    "ShadeExposureReport",
    "SolarPosition",
    "aerodynamic_drag_power",
    "cyclist_speed",
    "haversine_distance_2d",
    "haversine_distance_3d",
    "cycling_energy_cost",
    "minetti_energy_cost",
    "rolling_resistance_force",
    "scooter_speed",
    "senior_fatigue_decay",
    "solar_irradiance_aspect_factor",
    "tobler_walking_speed",
    "universal_thermal_comfort_utci",
    "vehicle_free_flow_speed",
    "PROFILES",
    "PROFILE_CATEGORIES",
    "MobilityProfile",
    "UnknownProfileError",
    "get_profile",
    "get_profile_color",
    "list_profile_keys",
    "list_profile_keys_for_group",
    "resolve_profile",
    "load_custom_profile_json",
    "save_custom_profile_json",
    "NetworkSourceManager",
    "NetworkSourceError",
    "RoadSegment",
    "OsmBuilding",
    "OsmDataFetcher",
    "filter_buildings_in_corridor",
    "CueInstruction",
    "RouteStatistics",
    "compute_route_statistics",
    "densify_3d_linestring",
    "generate_cue_sheet",
    "smooth_elevation_series",
    "RouteResult3D",
    "RoutingEngine3D",
    "Waypoint",
    "solve_tsp_order",
    # Electric Vehicle 3D Powertrain & Energy
    "EVBatteryProfile",
    "EVEnergySimulator",
    "EVRouteEnergyResult",
    "EVSegmentEnergy",
    "solve_ev_energy_route",
    # Dynamic GTFS Timetable Transit Router
    "GTFSFeedReader",
    "GTFSStop",
    "GTFSRoute",
    "TimetableTransitRouter",
    "TransitJourneyResult",
    "TransitLeg",
    # Micro-Mobility Kinetics
    "evaluate_micro_mobility_comfort",
    "MicroMobilityRouteScore",
    "VibrationalComfortResult",
    # Weather Routing
    "compute_apparent_wind_resistance",
    "WeatherRouteSummary",
    "HeadwindResistanceResult",
    # Biomechanics
    "BiomechanicalKinematicsTracker",
    "BiomechanicalTrailSummary",
    "BiomechanicalSegmentResult",
    # Voice Guidance
    "generate_3d_turn_by_turn_cues",
    "TurnByTurn3DRouteGuide",
    "ManeuverInstruction3D",
    # Dynamic Hazard Evacuation
    "solve_3d_evacuation_routes",
    "EvacuationRouteResult",
    "EvacuationPath3D",
    "DynamicHazardZone",
    # 3D Truck Clearance Router
    "solve_heavy_vehicle_route3d",
    "TruckRouteFeasibilityResult",
    "TruckRestrictionProfile",
    "BridgeClearanceObstacle",
    # 3D Drone Flight Air Corridor Router
    "solve_3d_drone_flight_corridor",
    "AirCorridorResult",
    "DroneAirspaceProfile",
    "GeofencedNoFlyZone",
    # Downhill Brake Fade & Runaway Safety
    "evaluate_steep_descent_brake_fade",
    "DescentSafetyResult",
    "BrakeThermalProfile",
    # Superload Swept Path Envelope
    "calculate_swept_path_envelope",
    "SweptPathResult",
    "SuperloadVehicleProfile",
    # Eco-Routing & CO2 Emissions
    "calculate_route_co2_emissions",
    "EmissionAssessmentResult",
    "VehicleEmissionProfile",
    # Powertrain Thermal Soak Simulator
    "simulate_powertrain_thermal_load",
    "PowertrainThermalResult",
    "EngineHeatProfile",
    # Time-Dependent Dynamic Isochrones
    "solve_time_dependent_isochrones",
    "DynamicIsochroneResult",
    "DynamicIsochroneRing",
    "HourlyCongestionFactor",
    # Emergency Air Ambulance 3D Landing Zone
    "evaluate_helicopter_landing_zones",
    "LandingZoneResult",
    "HelicopterApproachSlope",
    # Pavement Hydroplaning & Water Film Depth
    "evaluate_road_hydroplaning_risk",
    "HydroplaningRiskResult",
    "PavementCrossSlopeProfile",
]
