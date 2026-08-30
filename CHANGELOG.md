# Changelog

All notable changes to this project will be documented in this file.

## [0.10.0] - 2026-08-30
### Added
- **Freight & High-Speed Rail Adhesion Limits Simulator (`rail_gradient_adhesion_limits.py`)**: Added `evaluate_rail_tractive_adhesion` calculating Curtius-Kniffler wheel-rail friction limits, grade climbability, and slip risk.
- **Multi-Truck Autonomous Platooning Fuel Simulator (`autonomous_platooning_fuel_savings.py`)**: Added `simulate_truck_platooning_benefits` modeling aerodynamic drag reduction, diesel fuel economy, and CO2 abatement.

## [0.9.0] - 2026-08-30
### Added
- **Emergency Helicopter Air Ambulance (HEMS) 3D Landing Zone Evaluator (`emergency_air_ambulance_landing.py`)**: Added `evaluate_helicopter_landing_zones` assessing 1:8 slope obstacle intrusion surfaces and safe approach headings.
- **Highway Hydroplaning & Water Film Depth Risk Simulator (`aquaplaning_hydroplaning_risk.py`)**: Added `evaluate_road_hydroplaning_risk` modeling Gallaway water film accumulation and dynamic critical hydroplaning speed.

## [0.8.0] - 2026-08-30
### Added
- **Heavy Vehicle Powertrain Coolant Thermal Soak Simulator (`thermal_engine_heat_soak.py`)**: Added `simulate_powertrain_thermal_load` computing coolant temperature rise, fan activation times, and thermal stress on steep mountain climbs.
- **Dynamic 4D Time-Dependent Isochrone Engine (`time_dependent_isochrones.py`)**: Added `solve_time_dependent_isochrones` adjusting polygon reachability contours dynamically according to rush-hour congestion profiles.

## [0.7.0] - 2026-08-30
### Added
- **Superload & Wind Turbine Blade Swept Path Kinematic Turning Envelope (`heavy_haulage_swept_path.py`)**: Added `calculate_swept_path_envelope` computing offtracking widths and curb encroachment risks.
- **Dynamic 3D Vehicle Eco-Routing & Carbon Footprint Estimator (`co2_emission_routing.py`)**: Added `calculate_route_co2_emissions` modeling rolling resistance, aerodynamic drag, and elevation gradient load.

## [0.6.0] - 2026-08-30
### Added
- **3D Urban Air Mobility (UAM) & Drone Delivery Air Corridor Router (`drone_airspace_corridor.py`)**: Added `solve_3d_drone_flight_corridor` with 4-stage 3D flight trajectory, vertical building clearance, and battery range limits.
- **Downhill Gradient Thermal Brake Fade & Runaway Ramp Safety (`gradient_braking_safety.py`)**: Added `evaluate_steep_descent_brake_fade` modeling brake drum thermodynamic energy dissipation.

## [0.5.0] - 2026-08-30
### Added
- **Multi-Criteria Dynamic Emergency Evacuation Router (`hazard_evacuation.py`)**: Added `solve_3d_evacuation_routes` with expanding hazard buffer avoidance and tobler-adjusted slope hiking times.
- **3D Heavy Vehicle / Truck Bridge Clearance Router (`truck_clearance.py`)**: Added `solve_heavy_vehicle_route3d` verifying overhead bridge clearances, axle load limits, maximum road grades, and HazMat tunnel exclusions.

## [0.4.0] - 2026-08-30
### Added
- **Micro-Mobility E-Scooter & E-Bike Vibrational Comfort (`micromobility_kinetics.py`)**: Added ISO 2631-1 vibration evaluation, IRI surface roughness mapping, and fall risk analysis.
- **Dynamic Weather & Wind Field Resistance Routing (`weather_routing.py`)**: Added `compute_apparent_wind_resistance` calculating vector apparent aerodynamic drag and wet pavement braking multipliers.
- **Biomechanical Athlete Caloric & Heart Rate Tracker (`biomechanics.py`)**: Added `BiomechanicalKinematicsTracker` with Minetti slope energy cost, METs, and heart rate zone distribution.
- **Multi-Lingual 3D Voice Guidance & Turn-by-Turn Maneuvers (`voice_guidance.py`)**: Added `generate_3d_turn_by_turn_cues` with elevation change warnings in TR, EN, and DE.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2026-08-30
### Added
- **Electric Vehicle (EV) 3D Battery State-of-Charge & Regenerative Braking Simulator (`ev_energy.py`)**:
  - Physics-based vehicle dynamics with rolling resistance, aerodynamic drag, gravitational slope resistance, and auxiliary HVAC power.
  - Downhill regenerative braking recovery calculation ($\eta_{regen}$) with segment-by-segment SoC (%) tracking and depletion warnings (`EVEnergySimulator`, `solve_ev_energy_route`).
- **Dynamic GTFS & Timetable-Aware Multimodal Public Transit Router (`transit_gtfs.py`)**:
  - In-memory GTFS timetable reader (`GTFSFeedReader`) supporting stops, routes, and scheduled trip stop-times.
  - Connection scan routing (`TimetableTransitRouter`) producing exact-time multimodal itineraries combining access/egress walking and scheduled transit lines.

## [0.2.0] - 2026-08-25
### Added
- Added `GeoTiffRasterSource` for headless rasterio-backed GeoTIFF sampling with WGS84-to-raster CRS reprojection.
- Added GeoTIFF DEM integration for `EnvironmentalSurfaceSampler` and `sample_rasterio_dem`.
- Added file/path GeoJSON network loading for high-level routing calls.
- Added focused 0.2.0 regression tests for network input, profile resolution, DEM fallback behavior, report generation, multimodal routing, and plotting validation.

### Changed
- Made unknown profile keys fail strictly in high-level APIs while preserving the legacy non-strict `get_profile` fallback.
- Preserved caller-supplied `MobilityProfile` instances through routing engines.
- Improved standalone route HTML output so generated reports include their route data, styles, and scripts without external assets.
- Kept missing DEM/elevation samples as `None` instead of silently treating them as sea level.

### Fixed
- Fixed GeoJSON `oneway=-1` handling so reversed one-way segments are stored in their travel direction.
- Fixed DEM batch fetch alignment when invalid coordinates or cache misses are present.
- Fixed multimodal hub selection so access and egress hubs cannot collapse into the same main-leg endpoint.
- Fixed motorized elevation plots so they do not show pedestrian calorie axes.
- Fixed Pareto plotting to reject unsupported metric names instead of silently substituting calories.

## [0.1.0] - 2026-08-24
### Added
- Initial standalone release of `zero2route3d-sdk`.
- Biomechanical kinematics engine: Tobler's walking speed, Minetti metabolic energy polynomials, cycling aerodynamics, rolling resistance, scooter power, and senior fatigue decay.
- 15 Calibrated mobility profiles spanning pedestrian, micromobility, vehicle, and emergency modes.
- 3D Topological graph routing engine with Dijkstra and A* pathfinding.
- NAMOA* 4D Multi-objective Pareto frontier router (Time, Climb, Heat Dose, Calories).
- 3D Anisotropic Isochrone wavefront simulation engine.
- 3D Hidden Markov Model (HMM) Viterbi map-matching for noisy GPS/GPX tracks.
- Keys' 16-point bicubic convolution spline micro-elevation interpolator.
- Solar shadow raytracing and thermal irradiance analysis.
- Multi-Criteria Decision Analysis (AHP) with consistency ratio validation ($CR \le 0.10$).
- Enhanced 2-Step Floating Catchment Area (E2SFCA) accessibility equity engine with Gini, Lorenz, and Palma scorecards.
- Dynamic hazard zone evacuation routing and safe haven allocation.
- Standalone Three.js 60 FPS WebGL 3D Cockpit HTML bundler.
- AutoCAD DXF 3D Polyline and longitudinal profile drawing exporter.
- Copernicus GLO-30 DEM COG tile fetcher.
