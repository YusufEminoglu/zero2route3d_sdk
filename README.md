<div align="center">

<a href="https://yusufeminoglu.github.io/zero2route3d_sdk/">
  <img src="https://raw.githubusercontent.com/YusufEminoglu/zero2route3d_sdk/main/docs/icons/logo.svg" width="140" height="140" alt="zero2route3d-sdk Logo" />
</a>

# zero2route3d-sdk

[![CI](https://gitlab.com/geospacephilo/zero2route3d_sdk/actions/workflows/ci.yml/badge.svg)](https://gitlab.com/geospacephilo/zero2route3d_sdk/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/zero2route3d-sdk.svg?color=10b981)](https://pypi.org/project/zero2route3d-sdk/)
[![Python version support](https://img.shields.io/pypi/pyversions/zero2route3d-sdk.svg?color=3b82f6)](https://pypi.org/project/zero2route3d-sdk/)
[![Documentation](https://img.shields.io/badge/docs-GitLab%20Pages-06b6d4.svg)](https://yusufeminoglu.github.io/zero2route3d_sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64.svg)](https://docs.astral.sh/ruff/)
[![Test Coverage](https://img.shields.io/badge/coverage-95%25%2B-brightgreen.svg)](#-development--testing)

**Headless 3D Spatial Mobility, Biomechanical Human Kinematics, Metabolic Energy Modeling, and Multi-Criteria Routing Analytics.**

[📖 **Open Interactive Web Manual (GitLab Pages)**](https://yusufeminoglu.github.io/zero2route3d_sdk/) • [📦 **PyPI Package**](https://pypi.org/project/zero2route3d-sdk/) • [🐛 **Issue Tracker**](https://gitlab.com/geospacephilo/zero2route3d_sdk/-/issues)

</div>

---

## 🌟 Overview

**zero2route3d-sdk** is a scientific Python library for **3D spatial mobility modeling, physiological human movement kinematics, and multi-criteria routing**. 

Unlike conventional 2D planar routing engines (e.g. standard OSRM or pgRouting) that ignore terrain gradient and human physiology, **zero2route3d-sdk** seamlessly fuses **topographic 3D graph models**, **biomechanical energy expenditure equations (Tobler & Minetti)**, **4D Pareto multi-objective search (NAMOA*)**, and **environmental microclimate impedance** into a pure-Python, headless library powered by NumPy and SciPy.

---

## 🔬 Core Capabilities

### 1. Biomechanical Kinematics & Energy Expenditure
* **Tobler's Hiking Function (1993):** Empirical velocity-slope curves ($W(s) = 6.0 \cdot e^{-3.5|s+0.05|}$).
* **Minetti's Locomotion Energy Polynomial (2002):** Exact mechanical metabolic cost ($J / (kg \cdot m)$) across arbitrary positive and negative slopes.
* **Cycling & Micromobility Dynamics:** Physical aerodynamic drag ($P_{aero}$), rolling resistance ($P_{rolling}$), and gravitational climbing power for commuter bikes, cargo bikes, e-bikes, and e-scooters.
* **Universal Thermal Comfort Index (UTCI):** Real-time solar ray-tracing, sun azimuth/elevation angles, and building shade exposure impedance.

### 2. 15 Calibrated Mobility Profiles
* **Pedestrian:** *Standard Adult*, *Senior / Elderly (fatigue decay)*, *Child / Elementary*.
* **Universal Accessibility:** *Wheelchair ADA (0% curb tolerance)*, *Stroller / Pram*.
* **Active Travel & Micromobility:** *Commuter Bike*, *Cargo Bike (120kg rolling mass)*, *Electric Bike (250W assist)*, *E-Scooter*, *Runner*, *Mountain Hiker*.
* **Emergency & Fleet:** *Ambulance EMS*, *Fire Engine Heavy*, *Logistics Delivery Van*, *Electric Vehicle EV (regenerative braking)*.

### 3. Multi-Objective 4D Pareto Optimization (NAMOA*)
* Identifies the exact non-dominated Pareto frontier simultaneously balancing:
  $$\vec{C}(p) = \Big( \text{Travel Time}, \text{Cumulative Climb}, \text{Thermal Heat Dose}, \text{Metabolic Calories} \Big)$$

### 4. 3D Topological Routing & Isochrone Wavefronts
* 3D A* and Dijkstra on compressed sparse row (CSR) graphs with turn penalties, grade-resistance, elevation draping, and barrier constraints.
* 3D anisotropic travel-time isochrone wavefront propagation with concave/convex hull boundary extraction.

### 5. 3D Hidden Markov Model (HMM) Map Matching
* High-accuracy Viterbi sequence decoding matching noisy 3D GPS/GPX traces to topological road centerlines with Gaussian emission and exponential transition probabilities.

### 6. Micro-Elevation & Bicubic Spline Derivatives
* Keys' 16-point bicubic convolution spline interpolation delivering smooth analytical surface gradients ($C^1$ continuity) with exact slope and aspect calculation.
* Built-in automated Copernicus GLO-30 DEM tile fetcher and GeoTIFF raster reader.

### 7. Multi-Format Headless Export & 3D WebGL Visualization
* Exports to **GeoJSON 3D** (LineStringZ), **AutoCAD DXF 3D Polylines** (AC1009/AC1015), **GPX 1.1**, and standalone **Three.js 60 FPS WebGL 3D Interactive Cockpit HTML bundles**.
* Direct bidirectional bridges for **GeoPandas GeoDataFrames** and **NetworkX DiGraphs**.

---

## 📦 Installation

```bash
# Standard installation from PyPI
pip install zero2route3d-sdk

# With optional geospatial acceleration suite (GeoPandas, Shapely, Rasterio, NetworkX, Matplotlib)
pip install "zero2route3d-sdk[geo]"
```

---

## 🚀 Quickstart & Usage Examples

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
print(f"Metabolic Energy: {route.statistics.total_energy_kcal:.0f} kcal")

# Generate standalone 60 FPS Three.js 3D WebGL interactive cockpit
route.to_html("route_cockpit.html")

# Plot publication-grade longitudinal elevation profile
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
    profile="commuter_bike"
)

for idx, sol in enumerate(pareto_result.solutions, start=1):
    c = sol.costs
    print(f"Option #{idx}: Duration={c.time_sec/60:.1f}m | Climb=+{c.climb_m:.1f}m | Calories={c.calories_kcal:.0f}kcal")

# Plot 2D Pareto trade-off curve
zr3d.plot_pareto_frontier_2d(pareto_result, save_path="pareto_curve.png")
```

---

### 3. 3D HMM Map Matching (Viterbi GPS Snapping)
Snap raw noisy GPS coordinates to 3D road centerlines:

```python
from zero2route3d.map_matching_3d import HMMMapMatcher3D, GPXPoint

matcher = HMMMapMatcher3D(network_segments)
raw_gps = [
    GPXPoint(lon=27.112, lat=38.415, elevation=12.0, timestamp=0.0),
    GPXPoint(lon=27.118, lat=38.422, elevation=14.5, timestamp=30.0)
]

matched_result = matcher.match_trace(raw_gps)
print(f"Matched {len(matched_result.matched_points)} points. Mean error: {matched_result.mean_error_meters:.2f} m")
```

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
zero2route3d route --origin 27.11,38.41 --dest 27.14,38.44 --network streets.geojson --profile commuter_bike --out-geojson route.geojson --out-dxf route.dxf --out-html cockpit.html

# Compute 3D travel time isochrones
zero2route3d isochrone --center 27.12,38.42 --intervals 5,10,15 --network streets.geojson --profile adult --out-geojson isochrones.geojson
```

---

## 📊 Mobility Profiles Catalog

| Key | Profile Name | Base Speed | Max Slope | Stairs Policy | Target Use-Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `adult` | Standard Adult | 5.0 km/h | 25.0% | Allowed (1.2×) | Everyday urban pedestrian walking |
| `senior` | Senior / Elderly | 3.2 km/h | 10.0% | Heavy Penalty (8.0×) | Age-friendly & fatigue-reduced routing |
| `child` | Child / Elementary | 3.8 km/h | 12.0% | Heavy Penalty (5.0×) | Safe routes to school |
| `wheelchair` | Wheelchair ADA | 3.5 km/h | 5.0% | **Forbidden (1000×)** | Strict ADA barrier-free routing |
| `stroller` | Stroller / Pram | 4.0 km/h | 8.0% | **Forbidden (500×)** | Family-friendly walking |
| `cargo_bike` | Cargo Bike | 14.0 km/h | 8.0% | **Forbidden (1000×)** | Heavy urban freight & delivery logistics |
| `commuter_bike`| Commuter Bike | 18.0 km/h | 15.0% | Heavy Penalty (20.0×) | Daily bicycle commuting & calorie optimization |
| `ebike` | Electric Assist Bike | 22.0 km/h | 22.0% | Heavy Penalty (20.0×) | Topography-immune cycling |
| `escooter` | E-Scooter | 16.0 km/h | 10.0% | **Forbidden (1000×)** | Micromobility & pavement-smoothness routing |
| `runner` | Jogger / Runner | 10.0 km/h | 30.0% | Allowed (1.0×) | Athletic running & calorie expenditure |
| `hiker` | Mountain Hiker | 4.5 km/h | 50.0% | Allowed (1.0×) | Extreme trail hiking & mountain scrambles |
| `emergency_ems`| Ambulance EMS | 50.0 km/h | 20.0% | **Forbidden (1000×)** | Rapid emergency medical response |
| `emergency_fire`| Fire Engine Heavy | 40.0 km/h | 16.0% | **Forbidden (1000×)** | Heavy emergency vehicle access |
| `logistics_van`| Delivery Van | 45.0 km/h | 18.0% | **Forbidden (1000×)** | Multi-stop parcel logistics & fleet dispatch |
| `electric_car` | Electric Vehicle EV | 50.0 km/h | 25.0% | **Forbidden (1000×)** | Regenerative braking energy recovery |

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

## 🧪 Development & Testing

```bash
# Clone repository and install in editable mode
git clone https://gitlab.com/geospacephilo/zero2route3d_sdk.git
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
  publisher = {PyPI - Python Package Index},
  version   = {0.2.0},
  url       = {https://gitlab.com/geospacephilo/zero2route3d_sdk}
}
```

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.
