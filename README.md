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

### 1. Biomechanical Kinematics & Walking Speed

```python
from zero2route3d import tobler_walking_speed, minetti_energy_cost, cycling_energy_cost

# Walking speed on a +8% incline (km/h)
speed = tobler_walking_speed(slope_decimal=0.08, base_speed_kmh=5.0)
print(f"Uphill walking speed: {speed:.2f} km/h")

# Metabolic energy cost (Joules per kg per meter)
energy_j_kg_m = minetti_energy_cost(gradient_decimal=0.08)
print(f"Energy cost: {energy_j_kg_m:.2f} J/(kg*m)")
```

### 2. 3D Least-Cost Routing

```python
from zero2route3d import RoutingEngine3D, RoadSegment, get_profile

# Initialize 3D routing engine
engine = RoutingEngine3D()

# Define 3D network segments: RoadSegment(id, p1=(lon, lat, elev), p2=(lon, lat, elev), ...)
engine.add_segment(RoadSegment("seg_1", (27.138, 38.419, 10.0), (27.140, 38.421, 25.0), length_m=280.0, highway_type="residential"))
engine.add_segment(RoadSegment("seg_2", (27.140, 38.421, 25.0), (27.145, 38.425, 40.0), length_m=520.0, highway_type="secondary"))

# Solve for Wheelchair ADA profile (strictly penalizes slopes > 5% and stairs)
profile = get_profile("wheelchair")
route = engine.solve_route(
    start_pt=(27.138, 38.419, 10.0),
    end_pt=(27.145, 38.425, 40.0),
    profile=profile
)

print(f"Distance: {route.total_distance_m:.1f} m")
print(f"Travel Time: {route.total_time_sec / 60:.1f} min")
print(f"Cumulative Ascent: {route.elevation_gain_m:.1f} m")
```

### 3. Multi-Objective 4D Pareto Frontier (NAMOA*)

```python
from zero2route3d import ParetoMultiObjectiveRouter, RoadSegment, get_profile

router = ParetoMultiObjectiveRouter()
router.add_segment(RoadSegment("e1", (27.10, 38.40, 5.0), (27.12, 38.42, 35.0), length_m=400.0))

profile = get_profile("commuter_bike")
result = router.solve_pareto_frontier(
    start_pt=(27.10, 38.40, 5.0),
    end_pt=(27.12, 38.42, 35.0),
    profile=profile
)

for sol in result.solutions:
    print(f"Solution: Time={sol.costs.time_sec:.1f}s, Climb={sol.costs.climb_m:.1f}m, Heat={sol.costs.heat_dose:.1f}, Calories={sol.costs.calories_kcal:.1f} kcal")
```

### 4. 3D GPS Map Matching (HMM Viterbi)

```python
from zero2route3d import HMMMapMatcher3D, GPXPoint, RoadSegment

matcher = HMMMapMatcher3D(gps_sigma=8.0, beta=5.0)
matcher.add_segment(RoadSegment("main_st", (27.10, 38.40, 10.0), (27.12, 38.40, 12.0), length_m=200.0))

raw_gps = [
    GPXPoint(lon=27.1001, lat=38.4002, elevation=10.5, timestamp=0.0),
    GPXPoint(lon=27.1102, lat=38.4001, elevation=11.0, timestamp=30.0),
    GPXPoint(lon=27.1198, lat=38.3999, elevation=12.2, timestamp=60.0),
]

match_result = matcher.match_track(raw_gps)
print(f"Matched points: {len(match_result.matched_points)}, Mean confidence: {match_result.mean_confidence:.2f}")
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
