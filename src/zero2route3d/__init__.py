"""02Route 3D SDK — Multi-Criteria 3D Kinematic & Spatial Mobility Analytics Library."""

from __future__ import annotations

__version__ = "0.2.0"
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
from .basemap import add_osm_basemap
from .copernicus_dem import CopernicusDemError, CopernicusDemTileSource
from .dem_fetcher import NODATA, GlobalDemFetcher
from .environmental_raster import EnvironmentalSurfaceSampler, MCDAWeights
from .evacuation import EvacuationPlan, EvacuationRouter, HazardZone
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
]
