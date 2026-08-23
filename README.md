# zero2route3d-sdk

[![CI](https://github.com/YusufEminoglu/zero2route3d_sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/YusufEminoglu/zero2route3d_sdk/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/zero2route3d-sdk.svg)](https://pypi.org/project/zero2route3d-sdk/)
[![Python version support](https://img.shields.io/pypi/pyversions/zero2route3d-sdk.svg)](https://pypi.org/project/zero2route3d-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64.svg)](https://docs.astral.sh/ruff/)

**zero2route3d-sdk** is a Python library for **3D spatial mobility modeling, biomechanical human kinematics, and multi-criteria routing analytics**.

Built for urban planners, mobility researchers, and geospatial developers, it brings physiological human movement equations, terrain-aware 3D graph algorithms, and environmental microclimate impedance surfaces together into a pure-Python, headless package powered by NumPy and SciPy.

---

## 🌟 Key Capabilities

1. **Biomechanical Kinematics & Energy Modeling:**
   - Empirical slope-speed curves via **Tobler's hiking function** ($W(s) = 6.0 \cdot e^{-3.5|s+0.05|}$).
   - Exact metabolic energy expenditure via **Minetti's 5th-order polynomial equations** ($J / (kg \cdot m)$).
   - Aerodynamic drag, rolling resistance, and mechanical efficiency for commuter bikes, cargo bikes, and e-scooters.
   - Universal Thermal Comfort Index (**UTCI**) and solar irradiance aspect factors.

2. **15 Calibrated Mobility Profiles:**
   - Pedestrian (*Adult, Senior, Child*).
   - Universal accessibility (*Wheelchair ADA, Stroller*).
   - Micromobility (*Commuter Bike, Cargo Bike, E-Bike, E-Scooter, Runner, Hiker*).
   - Vehicles & Emergency (*Emergency EMS, Fire Truck, Logistics Van, Electric Car*).

3. **Multi-Objective 4D Pareto Optimization (NAMOA*):**
   - Finds non-dominated Pareto frontiers balancing **Travel Time, Cumulative Climb, Thermal Heat Dose, and Metabolic Calories**.

4. **3D Topological Routing & Isochrones:**
   - 3D graph construction with elevation draping, turn penalties, and barrier avoidance.
   - Anisotropic 3D isochrone wavefront propagation.

5. **3D Hidden Markov Model (HMM) Map Matching:**
   - Robust Viterbi decoding matching noisy GPS/GPX tracks to 3D networks.

6. **Micro-Elevation & Solar Ray-Tracing:**
   - Keys' 16-point bicubic convolution spline interpolation with analytical $\mathcal{C}^1$ slope/aspect derivatives.
   - Solar position calculation (azimuth/elevation) and building shadow casting.

7. **Spatial Justice & Evacuation:**
   - Enhanced 2-Step Floating Catchment Area (**E2SFCA**) healthcare/amenity accessibility.
   - Gini coefficients, Lorenz curves, and Palma spatial equity ratios.
   - Dynamic hazard zone evacuation routing and safe haven allocation.

8. **Headless & Multi-Format I/O:**
   - Runs everywhere: Jupyter Notebooks, FastAPI/Flask backends, Docker containers, CLI scripts.
   - Exports to GeoJSON 3D, GPX 1.1, AutoCAD DXF (AC1009/AC1015) 3D Polylines, and standalone Three.js 60 FPS WebGL 3D Cockpit HTML bundles.

---

## 📦 Installation

Install the core library from PyPI:

```bash
pip install zero2route3d-sdk
```

Or install with optional geospatial acceleration libraries:

```bash
pip install "zero2route3d-sdk[geo]"
```

---

## 🚀 Quickstart

### 1. High-Level One-Line Routing & Isochrones

```python
import zero2route3d as zr3d

# Solve 3D Least-Cost Route in 1 line
route = zr3d.solve_3d_route(
    origin=(27.11, 38.41),
    destination=(27.14, 38.44),
    network="izmir_network.geojson",  # Or GeoDataFrame / list of RoadSegments
    profile="wheelchair"              # 15 calibrated profiles
)

print(f"Distance: {route.statistics.total_distance_km:.2f} km")
print(f"Duration: {route.statistics.total_duration_min:.1f} min")
print(f"Climb: +{route.statistics.elevation_gain_m:.1f} m")

# Save or display interactive 3D WebGL Cockpit
route.to_html("route_viewer.html")

# Plot publication-grade elevation & metabolic energy profile with Matplotlib
route.plot(show_energy=True, save_path="profile.png")

# Convert to 3D LineStringZ GeoDataFrame for GIS workflows
gdf = route.to_geodataframe()
```

### 2. Multi-Objective 4D Pareto Frontier (NAMOA*)

```python
import zero2route3d as zr3d

pareto_result = zr3d.solve_4d_pareto_frontier(
    origin=(27.11, 38.41),
    destination=(27.14, 38.44),
    network="izmir_network.geojson",
    profile="commuter_bike"
)

for idx, sol in enumerate(pareto_result.solutions, start=1):
    print(f"Solution #{idx}: Time={sol.costs.time_sec/60:.1f}m, Climb={sol.costs.climb_m:.1f}m, Calories={sol.costs.calories_kcal:.0f}kcal")

# Plot 2D Pareto trade-off curve
zr3d.plot_pareto_frontier_2d(pareto_result, save_path="pareto_curve.png")
```

### 3. GeoPandas & NetworkX Ecosystem Bridges

```python
from zero2route3d import to_geodataframe, to_networkx_digraph, from_geodataframe
import geopandas as gpd

# Load standard GeoDataFrame of road centerlines
gdf = gpd.read_file("streets.geojson")

# Convert GeoDataFrame into 3D RoadSegment graph
segments = from_geodataframe(gdf)

# Convert 3D routing graph into NetworkX DiGraph with slope & kinematic weights
nx_digraph = to_networkx_digraph(segments)
```

### 4. Command Line Interface (CLI)

```bash
# Inspect all 15 mobility profiles
zero2route3d profiles

# Run headless 3D route calculation from terminal
zero2route3d route --origin 27.11,38.41 --dest 27.14,38.44 --network streets.geojson --profile wheelchair --out-geojson route.geojson --out-dxf route.dxf --out-html viewer.html

# Compute 3D travel time isochrone bands
zero2route3d isochrone --center 27.12,38.42 --intervals 5,10,15 --network streets.geojson --out-geojson isochrones.geojson
```

---

## 📚 Mobility Profiles Catalog

| Key | Profile Name | Base Speed | Max Slope | Stairs Policy | Target Use-Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `adult` | Standard Adult | 5.0 km/h | 25.0% | Allowed (1.2×) | Everyday urban walking |
| `senior` | Senior / Elderly | 3.2 km/h | 10.0% | Heavy Penalty (8.0×) | Age-friendly routing |
| `child` | Child / Elementary | 3.8 km/h | 12.0% | Heavy Penalty (5.0×) | Safe routes to school |
| `wheelchair` | Wheelchair ADA | 3.5 km/h | 5.0% | **Forbidden** (1000×) | Barrier-free ADA routing |
| `stroller` | Stroller / Pram | 4.0 km/h | 8.0% | **Forbidden** (500×) | Family-friendly walking |
| `cargo_bike` | Cargo Bike | 14.0 km/h | 8.0% | **Forbidden** (1000×) | Urban freight & logistics |
| `commuter_bike`| Commuter Bike | 18.0 km/h | 15.0% | Heavy Penalty (20.0×) | Daily bicycle commuting |
| `ebike` | Electric Assist Bike| 22.0 km/h | 22.0% | Heavy Penalty (20.0×) | Topography-immune cycling |
| `escooter` | E-Scooter | 16.0 km/h | 10.0% | **Forbidden** (1000×) | First/last-mile micromobility |
| `runner` | Jogger / Runner | 10.0 km/h | 30.0% | Allowed (1.0×) | Fitness & athletic routing |
| `hiker` | Mountain Hiker | 4.5 km/h | 50.0% | Allowed (1.0×) | Trail & topographic hiking |
| `emergency_ems`| Ambulance EMS | 50.0 km/h | 20.0% | **Forbidden** (1000×) | Rapid emergency response |
| `emergency_fire`| Fire Engine Heavy | 40.0 km/h | 16.0% | **Forbidden** (1000×) | Heavy emergency vehicles |
| `logistics_van`| Delivery Van | 45.0 km/h | 18.0% | **Forbidden** (1000×) | Courier & parcel delivery |
| `electric_car` | Electric EV | 50.0 km/h | 25.0% | **Forbidden** (1000×) | Regenerative braking routing |

---

## 🧪 Development & Testing

Clone the repository and install in editable mode:

```bash
git clone https://github.com/YusufEminoglu/zero2route3d_sdk.git
cd zero2route3d_sdk
pip install -e ".[dev]"
```

Run test suite with coverage:

```bash
pytest tests/ -v --cov=zero2route3d
```

Run linter and type checker:

```bash
ruff check .
ruff format --check src tests
mypy src
```

---

## 📄 License & Citation

Distributed under the **MIT License**. See `LICENSE` for details.

If you use this library in scientific research, please cite:

```bibtex
@software{eminoglu2026zero2route3d,
  author = {Eminoğlu, Yusuf},
  title = {zero2route3d-sdk: Headless 3D spatial mobility, biomechanical human kinematics, and multi-criteria routing engine},
  year = {2026},
  url = {https://github.com/YusufEminoglu/zero2route3d_sdk}
}
```
