# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
