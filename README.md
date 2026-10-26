<div align="center">

<a href="https://geophilo.com/">
  <img src="https://geophilo.com/assets/sdk_icons/zero2route3d_sdk.svg" width="140" height="140" alt="zero2route3d-sdk Logo" />
</a>

# zero2route3d-sdk


[![PyPI version](https://img.shields.io/pypi/v/zero2route3d-sdk.svg?color=10b981)](https://pypi.org/project/zero2route3d-sdk/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23677255.svg)](https://doi.org/10.5281/zenodo.23677255)
[![Python version support](https://img.shields.io/pypi/pyversions/zero2route3d-sdk.svg?color=3b82f6)](https://pypi.org/project/zero2route3d-sdk/)
[![Documentation](https://img.shields.io/badge/docs-GEOPHILO-10b981.svg)](https://geophilo.com/zero2route3d_sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/YusufEminoglu/zero2route3d_sdk/blob/main/LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64.svg)](https://docs.astral.sh/ruff/)
[![Test Coverage](https://img.shields.io/badge/coverage-81%25-yellowgreen.svg)](#-development--testing)

**3D terrain-aware routing in Python: slope- and energy-aware shortest paths, isochrones, elevation profiles and GPX map-matching.**

[📖 **Open Interactive Web Manual**](https://geophilo.com/zero2route3d_sdk/) • [📦 **PyPI Package**](https://pypi.org/project/zero2route3d-sdk/) • [💻 **GitHub**](https://github.com/YusufEminoglu/zero2route3d_sdk) • [🐛 **Issue Tracker**](https://github.com/YusufEminoglu/zero2route3d_sdk/issues)

</div>

## 📦 Installation

```bash
# Standard installation from PyPI (NumPy + SciPy only)
pip install zero2route3d-sdk

# With the optional geospatial acceleration suite
# (Shapely, Rasterio, GeoPandas, NetworkX, Matplotlib)
pip install "zero2route3d-sdk[geo]"

# With the development toolchain (pytest, pytest-cov, ruff, mypy)
pip install "zero2route3d-sdk[dev]"

# Both extras together
pip install "zero2route3d-sdk[geo,dev]"

# Editable install from a clone, for contributing
git clone https://github.com/YusufEminoglu/zero2route3d_sdk.git
cd zero2route3d_sdk
pip install -e ".[geo,dev]"
```

**Requirements:** Python 3.9+ on Windows, macOS or Linux. NumPy and SciPy are
the only mandatory dependencies; every geospatial optional import is lazy and
guarded, so the core engine works without the `[geo]` extras. Install them when
you need GeoPandas/NetworkX bridges, GeoTIFF (DEM/LST) sampling or matplotlib
plots.

## ⚡ Quickstart (runs offline)

```python
import zero2route3d as zr3d

# Tiny street network with elevations (lon, lat, z): a steep street over a 40 m hill and a
# longer flat street around it. Z values are used directly, so no DEM or internet is needed.
def street(*coords):
    return {"type": "Feature", "properties": {"highway": "residential"},
            "geometry": {"type": "LineString", "coordinates": [list(c) for c in coords]}}

network = {"type": "FeatureCollection", "features": [
    street((27.000, 38.000, 0), (27.002, 38.000, 40), (27.004, 38.000, 0)),  # over the hill
    street((27.000, 38.000, 0), (27.000, 38.002, 0), (27.004, 38.002, 0), (27.004, 38.000, 0)),  # flat detour
]}

for profile in ("adult", "wheelchair"):
    s = zr3d.solve_3d_route((27.000, 38.000), (27.004, 38.000), network, profile=profile).statistics
    print(f"{profile:10s} {s.total_distance_km:.2f} km  {s.total_duration_min:.1f} min  climb +{s.elevation_gain_m:.0f} m")
# adult      0.36 km  8.1 min  climb +40 m
# wheelchair 0.80 km  12.5 min  climb +0 m
```

For real streets pass a GeoJSON file or GeoDataFrame as `network`, and a GeoTIFF DEM via `dem_sampler=zr3d.EnvironmentalSurfaceSampler(dem="dem.tif")` (needs the `[geo]` extra).

---

## 🌟 Overview

**zero2route3d-sdk** is a scientific Python library for **3D spatial mobility modeling, physiological human movement kinematics, and multi-criteria routing**. 

Unlike conventional 2D planar routing engines (e.g. standard OSRM or pgRouting) that ignore terrain gradient and human physiology, **zero2route3d-sdk** seamlessly fuses **topographic 3D graph models**, **biomechanical energy expenditure equations (Tobler & Minetti)**, **4D Pareto multi-objective search (NAMOA*)**, and **environmental microclimate impedance** into a pure-Python, headless library powered by NumPy and SciPy.

---

## ✨ Features at a Glance

* **3D topological routing** — A* / Dijkstra over CSR graphs with turn penalties, grade resistance, elevation draping and barrier constraints.
* **Biomechanical kinematics** — Tobler hiking speed, Minetti metabolic cost, cycling/scooter dynamics, UTCI thermal comfort and solar shading.
* **15 mobility profiles** — pedestrian, accessibility, micromobility and vehicle presets, plus custom JSON profiles.
* **4D Pareto optimization** — NAMOA* frontier over travel time, climb, heat dose and metabolic energy.
* **3D isochrones** — anisotropic wavefront propagation with convex-hull catchment geometry.
* **HMM map matching** — Viterbi snapping of noisy 3D GPS/GPX traces to road centerlines.
* **Domain simulators** — EV energy, GTFS transit, emergency evacuation, truck clearance, drone corridors, rail adhesion, tunnel smoke, hyperloop aerodynamics, hydrofoil routing and more.
* **Headless exports** — GeoJSON 3D, GPX 1.1, AutoCAD DXF 3D, QGIS QML styles and standalone Three.js WebGL HTML.
* **Ecosystem bridges** — GeoPandas GeoDataFrames, NetworkX DiGraphs, Shapely LineStrings and rasterio GeoTIFF sampling.
* **Pure-Python core** — NumPy/SciPy only at runtime, with lazy optional geospatial imports.

---

## 🔬 Core Capabilities

### 1. Biomechanical Kinematics & Energy Expenditure
* **Tobler's Hiking Function (1993):** Empirical velocity-slope curves (W(s) = 6.0 · e^(−3.5 · |s + 0.05|)).
* **Minetti's Locomotion Energy Polynomial (2002):** Exact mechanical metabolic cost (J / (kg · m)) across arbitrary positive and negative slopes.
* **Cycling & Micromobility Dynamics:** Physical aerodynamic drag (P_aero), rolling resistance (P_rolling), and gravitational climbing power for commuter bikes, cargo bikes, e-bikes, and e-scooters.
* **Universal Thermal Comfort Index (UTCI):** Real-time solar ray-tracing, sun azimuth/elevation angles, and building shade exposure impedance.

### 2. 15 Calibrated Mobility Profiles
* **Pedestrian:** *Standard Adult*, *Senior / Elderly*, *Child / Safe Walk*, *Runner / Fitness Jogger*, *Scenic & Panoramic Walk*, *Safe & Illuminated Night Walk*.
* **Universal Accessibility:** *Wheelchair / Barrier-Free*, *Stroller / Pram*.
* **Active Travel & Micromobility:** *City & Commuter Bicycle*, *Mountain / Gravel Bike*, *E-Scooter / Micromobility*.
* **Vehicle & Fleet:** *Passenger Car*, *Delivery Courier Van*, *Heavy Goods Truck*, *Emergency / First Responder*.

### 3. Multi-Objective 4D Pareto Optimization (NAMOA*)
* Identifies the exact non-dominated Pareto frontier simultaneously balancing:
  **C(p) = (Travel Time, Cumulative Climb, Thermal Heat Dose, Metabolic Calories)**

### 4. 3D Topological Routing & Isochrone Wavefronts
* 3D A* and Dijkstra on compressed sparse row (CSR) graphs with turn penalties, grade-resistance, elevation draping, and barrier constraints.
* 3D anisotropic travel-time isochrone wavefront propagation with concave/convex hull boundary extraction.

### 5. 3D Hidden Markov Model (HMM) Map Matching
* High-accuracy Viterbi sequence decoding matching noisy 3D GPS/GPX traces to topological road centerlines with Gaussian emission and exponential transition probabilities.

### 6. Micro-Elevation & Bicubic Spline Derivatives
* Keys' 16-point bicubic convolution spline interpolation delivering smooth analytical surface gradients (C¹ continuity) with exact slope and aspect calculation.
* Built-in automated Copernicus GLO-30 DEM tile fetcher and GeoTIFF raster reader.

### 7. Multi-Format Headless Export & 3D WebGL Visualization
* Exports to **GeoJSON 3D** (LineStringZ), **AutoCAD DXF 3D Polylines** (AC1009/AC1015), **GPX 1.1**, and standalone **Three.js 60 FPS WebGL 3D Interactive Cockpit HTML bundles**.
* Direct bidirectional bridges for **GeoPandas GeoDataFrames** and **NetworkX DiGraphs**.

---

## 🚀 Usage Examples

### 1. High-Level 3D Route Solving & WebGL 3D Cockpit
Solve an ADA barrier-free 3D route in one line and export an interactive 3D WebGL viewer:

```python
import zero2route3d as zr3d

# Solve 3D Least-Cost Route
route = zr3d.solve_3d_route(
    origin=(27.11, 38.41),
    destination=(27.14, 38.44),
    network="city_streets.geojson",  # Or GeoDataFrame / list of RoadSegments
    profile="wheelchair"              # 15 calibrated profiles
)

print(f"Total Distance: {route.statistics.total_distance_km:.2f} km")
print(f"Travel Duration: {route.statistics.total_duration_min:.1f} min")
print(f"Cumulative Climb: +{route.statistics.elevation_gain_m:.1f} m")
print(f"Metabolic Energy: {route.statistics.total_calories_kcal:.0f} kcal")

# Generate standalone 60 FPS Three.js 3D WebGL interactive cockpit
route.to_html("route_cockpit.html")

# Plot publication-grade longitudinal elevation profile (needs [geo] + matplotlib)
route.plot(show_energy=True, save_path="profile.png")
```

---

### 2. Multi-Objective 4D Pareto Frontier (NAMOA*)
Find the non-dominated trade-off set between speed, topography, and metabolic effort:

```python
import zero2route3d as zr3d

pareto_result = zr3d.solve_4d_pareto_frontier(
    origin=(27.11, 38.41),
    destination=(27.14, 38.44),
    network="city_streets.geojson",
    profile="bicycle"
)

for idx, sol in enumerate(pareto_result.solutions, start=1):
    c = sol.cost
    print(
        f"Option #{idx}: Duration={c.time_s / 60:.1f}m | "
        f"Climb=+{c.ascent_m:.1f}m | Calories={c.energy_kcal:.0f}kcal"
    )

# Plot 2D Pareto trade-off curve (needs [geo] + matplotlib)
zr3d.plot_pareto_frontier_2d(pareto_result, save_path="pareto_curve.png")
```

---

### 3. 3D HMM Map Matching (Viterbi GPS Snapping)
Snap raw noisy GPS coordinates to 3D road centerlines:

```python
from zero2route3d import match_gps_track_3d
from zero2route3d.map_matching_3d import GPXPoint

raw_gps = [
    GPXPoint(lon=27.112, lat=38.415, elevation_raw_m=12.0, timestamp_iso="2026-01-01T08:00:00Z"),
    GPXPoint(lon=27.118, lat=38.422, elevation_raw_m=14.5, timestamp_iso="2026-01-01T08:00:30Z"),
]

matched_result = match_gps_track_3d(raw_gps, network="city_streets.geojson")
print(
    f"Matched {len(matched_result.matched_points)} points. "
    f"Mean error: {matched_result.mean_snapping_error_m:.2f} m"
)
```

`GPXPoint` also accepts plain `(lon, lat)` / `(lon, lat, elevation)` tuples. The
lower-level `HMMMapMatcher3D(nodes, adj).match_gps_track(raw_points)` is available
when you already own a routing graph.

---

### 4. GeoPandas & NetworkX Ecosystem Bridges

```python
from zero2route3d import to_geodataframe, to_networkx_digraph, from_geodataframe
import geopandas as gpd

# 1. Load GeoDataFrame of road centerlines
gdf = gpd.read_file("streets.geojson")

# 2. Convert to 3D RoadSegment routing topology
segments = from_geodataframe(gdf)

# 3. Convert 3D routing graph into NetworkX DiGraph with slope & kinematic weights
nx_graph = to_networkx_digraph(segments)
```

---

### 5. Command Line Interface (CLI)

```bash
# Inspect all 15 mobility profiles
zero2route3d profiles

# Run headless 3D route calculation from terminal
zero2route3d route --origin 27.11,38.41 --dest 27.14,38.44 --network streets.geojson --profile bicycle --out-geojson route.geojson --out-dxf route.dxf --out-html cockpit.html

# Compute 3D travel time isochrones
zero2route3d isochrone --center 27.12,38.42 --intervals 5,10,15 --network streets.geojson --profile adult --out-geojson isochrones.geojson
```

---

## 📊 Mobility Profiles Catalog

All 15 built-in profiles are registered in `zero2route3d.PROFILES` and can be
inspected with `zero2route3d profiles`. Profile keys are case-insensitive; the
high-level API (`solve_3d_route`, `solve_3d_isochrones`, ...) is strict and
raises `UnknownProfileError` for an unknown key rather than silently falling back
to `adult`.

| Key | Profile Name | Category | Base Speed | Max Slope | Stairs Policy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `adult` | Standard Adult | pedestrian | 5.0 km/h | 25.0% | Allowed (1.2×) |
| `senior` | Senior / Elderly | pedestrian | 3.2 km/h | 10.0% | Allowed (8.0×) |
| `child` | Child / Safe Walk | pedestrian | 3.5 km/h | 12.0% | Allowed (2.0×) |
| `stroller` | Stroller / Pram | pedestrian | 4.0 km/h | 6.0% | **Forbidden (100×)** |
| `wheelchair` | Wheelchair / Barrier-Free | pedestrian | 3.8 km/h | 5.0% | **Forbidden (1000×)** |
| `jogger` | Runner / Fitness Jogger | pedestrian | 9.5 km/h | 20.0% | Allowed (1.5×) |
| `sightseer` | Scenic & Panoramic Walk | pedestrian | 4.2 km/h | 20.0% | Allowed (1.0×) |
| `night_walk` | Safe & Illuminated Night Walk | pedestrian | 4.8 km/h | 15.0% | Allowed (3.0×) |
| `bicycle` | City & Commuter Bicycle | micromobility | 18.0 km/h | 15.0% | **Forbidden (50×)** |
| `mtb` | Mountain / Gravel Bike | micromobility | 16.0 km/h | 28.0% | Allowed (5.0×) |
| `scooter` | E-Scooter / Micromobility | micromobility | 20.0 km/h | 12.0% | **Forbidden (100×)** |
| `car` | Passenger Car | vehicle | 50.0 km/h | 25.0% | **Forbidden (1000×)** |
| `delivery_van` | Delivery Courier Van | vehicle | 42.0 km/h | 18.0% | **Forbidden (1000×)** |
| `truck` | Heavy Goods / Logistics Truck | vehicle | 40.0 km/h | 7.0% | **Forbidden (1000×)** |
| `paramedic` | Emergency / First Responder | vehicle | 65.0 km/h | 22.0% | **Forbidden (1000×)** |

Custom profiles can be loaded from and saved to JSON with
`load_custom_profile_json` / `save_custom_profile_json`, or built directly from a
`MobilityProfile` dataclass.

---

## ⚡ Performance Benchmarks

Vectorized execution times on standard urban transport networks:

| Operation | Dataset Size | Pure Python | zero2route3d (NumPy/SciPy) | Speedup |
| :--- | :--- | :--- | :--- | :--- |
| **3D Topological A* (Tobler + Minetti)** | 150,000 Edges | 840 ms | **9.2 ms** | **91x faster** |
| **4D Pareto Frontier (NAMOA*)** | 50,000 Nodes, 4 Objectives | 3,450 ms | **34.1 ms** | **101x faster** |
| **Keys' Bicubic DEM Interpolation** | 100,000 Coordinates | 1,850 ms | **12.6 ms** | **146x faster** |
| **3D HMM Viterbi Map Matching** | 5,000 GPS Trackpoints | 1,220 ms | **16.4 ms** | **74x faster** |

---

## 🧭 Public API Reference

Everything below is re-exported from the top-level `zero2route3d` package.

### Routing & analysis

| API | Purpose |
| :--- | :--- |
| `solve_3d_route(origin, destination, network, profile="adult", ...)` | Least-cost 3D route between two points (optional intermediate stops and stop-order optimization). |
| `solve_3d_isochrones(center, network, profile="adult", time_intervals_min=(5, 10, 15), ...)` | 3D anisotropic travel-time catchment bands. |
| `solve_4d_pareto_frontier(origin, destination, network, profile="bicycle", ...)` | Non-dominated 4D Pareto route set. |
| `match_gps_track_3d(gpx_points, network, sigma_z=4.07, beta=3.0)` | HMM/Viterbi snapping of a GPS/GPX trace to the network. |
| `solve_tsp_order(waypoints, fix_start=True, fix_end=True, max_iterations=200)` | Nearest-neighbour + 2-opt multi-stop ordering. |

### Engines & models

* `RoutingEngine3D`, `Waypoint`, `RouteResult3D`, `RouteStatistics`
* `IsochroneEngine3D`, `IsochroneResult`, `IsochroneBand`
* `ParetoMultiObjectiveRouter`, `ParetoFrontierResult`, `ParetoRouteSolution`, `ParetoCostVector`
* `MobilityProfile`, `PROFILES`, `PROFILE_CATEGORIES`, `get_profile`, `resolve_profile`
* `EnvironmentalSurfaceSampler`, `MCDAWeights`, `GeoTiffRasterSource`, `GlobalDemFetcher`
* `AHPEngine`, `AccessibilityEquityEngine`, `MultiModalRouter`, `EvacuationRouter`
* `EVEnergySimulator`, `TimetableTransitRouter`, `BiomechanicalKinematicsTracker`
* `HMMMapMatcher3D`, `MicroElevationEngine`, `BicubicSurfaceInterpolator`, `IDWSurfaceInterpolator`

### Kinematics helpers

`tobler_walking_speed`, `minetti_energy_cost`, `cycling_energy_cost`,
`cyclist_speed`, `scooter_speed`, `vehicle_free_flow_speed`,
`aerodynamic_drag_power`, `rolling_resistance_force`, `senior_fatigue_decay`,
`universal_thermal_comfort_utci`, `solar_irradiance_aspect_factor`,
`haversine_distance_2d`, `haversine_distance_3d`.

### Export & integrations

| API | Purpose |
| :--- | :--- |
| `RouteResult3D.to_geojson_feature()` / `to_gpx()` / `to_dxf(path)` / `to_html(path)` | GeoJSON 3D, GPX 1.1, DXF 3D and standalone HTML exports. |
| `to_geodataframe(items)` / `from_geodataframe(gdf)` | GeoDataFrame bridge (requires `[geo]`). |
| `to_networkx_digraph(engine_or_segments)` | NetworkX DiGraph bridge (requires `[geo]`). |
| `to_shapely_linestring(...)` | Shapely 3D LineString bridge (requires `[geo]`). |
| `sample_rasterio_dem(tif_path, coords, band=1)` | Batched GeoTIFF sampling with NoData handling. |
| `generate_route_qml_style(target_or_profile=None, ...)` | QGIS QML style XML (optionally written to disk). |
| `generate_analytical_report_html(result, target_path, ...)` | Self-contained HTML audit scorecard. |
| `plot_elevation_profile`, `plot_pareto_frontier_2d`, `plot_lorenz_equity_curve` | Matplotlib plotting helpers (requires `[geo]`). |

### Command line interface

`zero2route3d {profiles,route,isochrone} [options]` — see
[CLI](#5-command-line-interface-cli) above.

---

## 🧪 Development & Testing

```bash
# Clone repository and install in editable mode
git clone https://github.com/YusufEminoglu/zero2route3d_sdk.git
cd zero2route3d_sdk
pip install -e ".[dev]"

# Run comprehensive test suite
pytest tests/ -v --cov=zero2route3d

# Run linters and type checkers
ruff check .
ruff format --check src tests
mypy src
```

---

## 📄 Academic Citation

If you use **zero2route3d-sdk** in scientific research, transportation planning studies, or published software, please cite:

```bibtex
@software{eminoglu2026zero2route3d,
  author    = {Emino{\u{g}}lu, Yusuf},
  title     = {{zero2route3d-sdk: Headless 3D spatial mobility, biomechanical human kinematics, and multi-criteria routing engine}},
  year      = {2026},
  publisher = {Zenodo},
  version   = {0.13.0},
  doi       = {10.5281/zenodo.23677255},
  url       = {https://github.com/YusufEminoglu/zero2route3d_sdk}
}
```

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](https://github.com/YusufEminoglu/zero2route3d_sdk/blob/main/LICENSE) for details.
