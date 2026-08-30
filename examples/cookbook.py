# -*- coding: utf-8 -*-
"""zero2route3d Cookbook — Hazard Evacuation, Truck Clearance & Micromobility."""

import zero2route3d

# 1. 3D Emergency Hazard Evacuation
origins = [{"id": "District_1", "population": 150, "coords": (50.0, 50.0, 5.0)}]
musters = [{"id": "Safe_Shelter", "coords": (300.0, 300.0, 20.0), "capacity": 1000}]
hazards = [zero2route3d.DynamicHazardZone("Flood", (150.0, 150.0, 0.0), expansion_speed_ms=1.0, current_radius_m=40.0)]
evac = zero2route3d.solve_3d_evacuation_routes(origins, musters, hazards)
print(f"Evacuation Time: {evac.mean_evacuation_time_min:.1f} min")

# 2. Truck Bridge Clearance
route = [(0, 0, 0), (200, 0, 0)]
obstacles = [zero2route3d.BridgeClearanceObstacle("B1", (100, 5, 0), max_underpass_height_m=4.0, max_weight_limit_tons=40.0)]
truck_res = zero2route3d.solve_heavy_vehicle_route3d(route, obstacles)
print(f"Truck Route Feasible: {truck_res.is_route_feasible}")

# 3. Micromobility Vibration Comfort
vibe = zero2route3d.evaluate_micro_mobility_comfort([500.0], ["asphalt_smooth"])
print(f"Bikeability Score: {vibe.overall_bikeability_score:.1f}/100")
