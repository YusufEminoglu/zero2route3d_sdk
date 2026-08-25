"""Pareto Frontier Multi-Objective 3D Routing Engine (NAMOA* with Epsilon-Dominance).

Calculates the complete non-dominated Pareto frontier across 4 conflicting objectives:
1. Duration / Travel Time (seconds)
2. Elevation Ascent / Incline Gain (meters)
3. Microclimate Heat / LST Exposure Dose (cumulative index)
4. Metabolic Energy Expenditure (Minetti kcal)

Author: Yusuf Eminoglu
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Union

from .environmental_raster import EnvironmentalSurfaceSampler
from .kinematics import (
    cycling_energy_cost,
    cyclist_speed,
    haversine_distance_2d,
    minetti_energy_cost,
    tobler_walking_speed,
)
from .mobility_profiles import MobilityProfile, resolve_profile
from .profile_stats import RouteStatistics, compute_route_statistics


@dataclass
class ParetoCostVector:
    """4D Objective cost vector for multi-objective optimization."""

    time_s: float
    ascent_m: float
    heat_dose: float
    energy_kcal: float

    def dominates(self, other: ParetoCostVector, epsilon: float = 0.0) -> bool:
        """Return True if self dominates other under approximate (1+eps) Pareto dominance."""
        c1 = (1.0 + epsilon) * self.time_s <= other.time_s
        c2 = (1.0 + epsilon) * self.ascent_m <= other.ascent_m
        c3 = (1.0 + epsilon) * self.heat_dose <= other.heat_dose
        c4 = (1.0 + epsilon) * self.energy_kcal <= other.energy_kcal

        strictly_better = (
            self.time_s < other.time_s
            or self.ascent_m < other.ascent_m
            or self.heat_dose < other.heat_dose
            or self.energy_kcal < other.energy_kcal
        )
        return (c1 and c2 and c3 and c4) and strictly_better

    def add(self, delta: ParetoCostVector) -> ParetoCostVector:
        return ParetoCostVector(
            time_s=self.time_s + delta.time_s,
            ascent_m=self.ascent_m + delta.ascent_m,
            heat_dose=self.heat_dose + delta.heat_dose,
            energy_kcal=self.energy_kcal + delta.energy_kcal,
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "duration_min": round(self.time_s / 60.0, 1),
            "ascent_m": round(self.ascent_m, 1),
            "heat_dose": round(self.heat_dose, 2),
            "energy_kcal": round(self.energy_kcal, 1),
        }


@dataclass
class ParetoRouteSolution:
    """Individual non-dominated route on the Pareto frontier."""

    label: str  # 'Fastest', 'Flattest', 'Coolest', 'Lowest Energy', 'Balanced Knee'
    cost: ParetoCostVector
    coordinates_3d: List[Tuple[float, float, float]]
    statistics: RouteStatistics
    tradeoff_radar: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "cost": self.cost.to_dict(),
            "distance_km": self.statistics.total_distance_km,
            "duration_min": self.statistics.total_duration_min,
            "elevation_gain_m": self.statistics.elevation_gain_m,
            "calories_kcal": self.statistics.total_calories_kcal,
            "thermal_comfort_score": self.statistics.thermal_comfort_score,
            "tradeoff_radar": self.tradeoff_radar,
            "coordinates": [
                [round(c[0], 6), round(c[1], 6), round(c[2], 2)] for c in self.coordinates_3d
            ],
        }


@dataclass
class ParetoFrontierResult:
    """Collection of all non-dominated routes along the Pareto frontier."""

    solutions: List[ParetoRouteSolution]
    hypervolume_indicator: float
    profile_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "solution_count": len(self.solutions),
            "hypervolume_indicator": round(self.hypervolume_indicator, 4),
            "profile_name": self.profile_name,
            "solutions": [s.to_dict() for s in self.solutions],
        }


class ParetoMultiObjectiveRouter:
    """New Approach to Multi-Objective A* (NAMOA*) 3D Routing Engine."""

    def __init__(
        self,
        nodes: Dict[int, Tuple[float, float, float]],
        adj: Dict[int, List[Tuple[int, float, float, Dict[str, Any]]]],
        sampler: EnvironmentalSurfaceSampler,
    ) -> None:
        self.nodes = nodes
        self.adj = adj
        self.sampler = sampler

    def _calculate_edge_vector(
        self,
        u: int,
        v: int,
        length_m: float,
        slope_pct: float,
        meta: Dict[str, Any],
        profile: MobilityProfile,
    ) -> ParetoCostVector:
        """Compute 4D cost vector for traversing edge (u -> v)."""
        v_coord = self.nodes[v]
        slope_frac = slope_pct / 100.0
        dz = max(0.0, self.nodes[v][2] - self.nodes[u][2])

        # 1. Travel Time & Energy
        if profile.category == "pedestrian":
            spd_kmh = tobler_walking_speed(slope_frac, base_speed_kmh=profile.base_speed_kmh)
            _j, kcal = minetti_energy_cost(slope_frac, mass_kg=70.0, distance_m=length_m)
        elif profile.key in {"bicycle", "mtb"}:
            spd_kmh = cyclist_speed(slope_frac, base_speed_kmh=profile.base_speed_kmh)
            kcal = cycling_energy_cost(slope_frac, mass_kg=70.0, distance_m=length_m)[1]
        else:
            spd_kmh = max(5.0, profile.base_speed_kmh * (1.0 - abs(slope_pct) * 0.02))
            # Motorised travel has no rider metabolic cost; reporting one would be
            # an invented figure in a column of measured ones.
            kcal = 0.0

        time_s = length_m / max(0.2, (spd_kmh * 1000.0 / 3600.0))
        ascent_m = dz

        # 3. Heat Exposure Dose.
        # Without a real LST raster there is no heat signal at all: a constant here
        # would make heat_dose proportional to length, i.e. the "Coolest" objective
        # would silently collapse into "Shortest".
        lst_val = self.sampler.sample_lst(v_coord[0], v_coord[1])
        heat_dose = (lst_val * (length_m / 100.0)) if lst_val is not None else 0.0

        return ParetoCostVector(
            time_s=time_s,
            ascent_m=ascent_m,
            heat_dose=heat_dose,
            energy_kcal=kcal,
        )

    def solve_pareto_frontier(
        self,
        start_node: int,
        end_node: int,
        profile_key: Union[str, MobilityProfile] = "adult",
        epsilon_dominance: float = 0.03,
        max_frontier_size: int = 12,
    ) -> ParetoFrontierResult:
        """Compute the Pareto Frontier using multi-objective label propagation."""
        profile = resolve_profile(profile_key)
        dest_coord = self.nodes[end_node]

        def heuristic_time(u_coord: Tuple[float, float, float]) -> float:
            d_m = haversine_distance_2d(u_coord, dest_coord)
            max_spd_ms = (profile.base_speed_kmh * 1.5) * 1000.0 / 3600.0
            return d_m / max_spd_ms

        labels_g: Dict[int, List[ParetoCostVector]] = {start_node: [ParetoCostVector(0, 0, 0, 0)]}
        h0 = heuristic_time(self.nodes[start_node])
        pq: List[Tuple[float, float, int, Tuple[int, ...]]] = [(h0, 0.0, start_node, (start_node,))]

        dest_solutions: List[Tuple[ParetoCostVector, Tuple[int, ...]]] = []
        max_iters = 80_000
        iters = 0

        while pq and iters < max_iters:
            iters += 1
            f_pri, g_time, u, path = heapq.heappop(pq)
            g_vec = None
            for cand in labels_g.get(u, []):
                if abs(cand.time_s - g_time) < 1e-4:
                    g_vec = cand
                    break
            if g_vec is None:
                continue

            if u == end_node:
                is_dominated = any(
                    sol_cost.dominates(g_vec, epsilon_dominance) for sol_cost, _ in dest_solutions
                )
                if not is_dominated:
                    dest_solutions = [
                        (sc, sp)
                        for sc, sp in dest_solutions
                        if not g_vec.dominates(sc, epsilon_dominance)
                    ]
                    dest_solutions.append((g_vec, path))
                continue

            if any(sol_cost.dominates(g_vec, epsilon_dominance) for sol_cost, _ in dest_solutions):
                continue

            for v, seg_len, slope_pct, meta in self.adj.get(u, []):
                if v in path:
                    continue

                edge_vec = self._calculate_edge_vector(u, v, seg_len, slope_pct, meta, profile)
                new_g = g_vec.add(edge_vec)

                existing = labels_g.setdefault(v, [])
                if any(ext.dominates(new_g, epsilon_dominance) for ext in existing):
                    continue

                labels_g[v] = [
                    ext for ext in existing if not new_g.dominates(ext, epsilon_dominance)
                ]
                labels_g[v].append(new_g)

                h_val = heuristic_time(self.nodes[v])
                heapq.heappush(pq, (new_g.time_s + h_val, new_g.time_s, v, path + (v,)))

        if not dest_solutions:
            return ParetoFrontierResult([], 0.0, profile.name)

        return self._extract_archetypes(dest_solutions, profile)

    def _extract_archetypes(
        self,
        raw_solutions: List[Tuple[ParetoCostVector, Tuple[int, ...]]],
        profile: MobilityProfile,
    ) -> ParetoFrontierResult:
        """Extract archetype solutions (Fastest, Flattest, Coolest, Least Effort, Balanced Knee)."""
        if not raw_solutions:
            return ParetoFrontierResult([], 0.0, profile.name)

        sol_fastest = min(raw_solutions, key=lambda s: s[0].time_s)
        sol_flattest = min(raw_solutions, key=lambda s: s[0].ascent_m)
        sol_coolest = min(raw_solutions, key=lambda s: s[0].heat_dose)
        sol_least_effort = min(raw_solutions, key=lambda s: s[0].energy_kcal)

        min_t = sol_fastest[0].time_s
        max_t = max(s[0].time_s for s in raw_solutions)
        min_a = sol_flattest[0].ascent_m
        max_a = max(s[0].ascent_m for s in raw_solutions)
        min_h = sol_coolest[0].heat_dose
        max_h = max(s[0].heat_dose for s in raw_solutions)
        min_e = sol_least_effort[0].energy_kcal
        max_e = max(s[0].energy_kcal for s in raw_solutions)

        range_t = max(1.0, max_t - min_t)
        range_a = max(1.0, max_a - min_a)
        range_h = max(0.1, max_h - min_h)
        range_e = max(1.0, max_e - min_e)

        def utopia_dist(s: Tuple[ParetoCostVector, Tuple[int, ...]]) -> float:
            nt = (s[0].time_s - min_t) / range_t
            na = (s[0].ascent_m - min_a) / range_a
            nh = (s[0].heat_dose - min_h) / range_h
            ne = (s[0].energy_kcal - min_e) / range_e
            return math.sqrt(nt**2 + na**2 + nh**2 + ne**2)

        sol_knee = min(raw_solutions, key=utopia_dist)

        archetype_map = [
            ("Fastest Route", sol_fastest),
            ("Flattest / Minimum Slope", sol_flattest),
            ("Coolest / Microclimate Shade", sol_coolest),
            ("Minimum Energy / Effort", sol_least_effort),
            ("Balanced Compromise (Knee)", sol_knee),
        ]

        seen_paths = set()
        solutions: List[ParetoRouteSolution] = []

        for label, (cost_vec, path_nodes) in archetype_map:
            if path_nodes in seen_paths:
                continue
            seen_paths.add(path_nodes)

            coords = [self.nodes[nid] for nid in path_nodes]
            stats = compute_route_statistics(coords, profile)

            radar = {
                "speed_score": round(1.0 - (cost_vec.time_s - min_t) / max(1.0, max_t - min_t), 2),
                "flatness_score": round(
                    1.0 - (cost_vec.ascent_m - min_a) / max(1.0, max_a - min_a), 2
                ),
                "shade_score": round(
                    1.0 - (cost_vec.heat_dose - min_h) / max(0.1, max_h - min_h), 2
                ),
                "energy_efficiency": round(
                    1.0 - (cost_vec.energy_kcal - min_e) / max(1.0, max_e - min_e), 2
                ),
            }

            solutions.append(
                ParetoRouteSolution(
                    label=label,
                    cost=cost_vec,
                    coordinates_3d=coords,
                    statistics=stats,
                    tradeoff_radar=radar,
                )
            )

        return ParetoFrontierResult(
            solutions=solutions,
            hypervolume_indicator=1.0 - utopia_dist(sol_knee),
            profile_name=profile.name,
        )
