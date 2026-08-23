"""Traveling Salesperson Problem (TSP) multi-stop tour optimizer.

Provides Nearest Neighbour heuristic + 2-Opt local search optimization to reorder
intermediate waypoints for minimal total 3D distance and elevation climb.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from .kinematics import haversine_distance_3d


def solve_tsp_order(
    waypoints: Sequence[Tuple[float, float, float]],
    fix_start: bool = True,
    fix_end: bool = True,
    max_iterations: int = 200,
) -> List[int]:
    """Return indices of waypoints ordered for minimum total path length using 2-Opt.

    Args:
        waypoints: List of (lon, lat, ele) tuples.
        fix_start: If True, index 0 remains the first point.
        fix_end: If True, index N-1 remains the final destination.
    """
    n = len(waypoints)
    if n <= 3:
        return list(range(n))

    # Initial order via Nearest-Neighbour
    unvisited = set(range(1, n - 1 if fix_end else n))
    current = 0 if fix_start else 0
    route = [current]

    while unvisited:
        nearest = min(
            unvisited,
            key=lambda idx: haversine_distance_3d(waypoints[current], waypoints[idx]),
        )
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    if fix_end:
        route.append(n - 1)

    def total_distance(r: List[int]) -> float:
        return sum(
            haversine_distance_3d(waypoints[r[i]], waypoints[r[i + 1]]) for i in range(len(r) - 1)
        )

    # 2-Opt Local Search
    best_route = list(route)
    best_dist = total_distance(best_route)
    improved = True
    iters = 0

    start_idx = 1 if fix_start else 0
    end_idx = n - 2 if fix_end else n - 1

    while improved and iters < max_iterations:
        improved = False
        iters += 1
        for i in range(start_idx, end_idx):
            for j in range(i + 1, end_idx + 1):
                # 2-opt swap: reverse slice between i and j
                new_route = best_route[:i] + best_route[i : j + 1][::-1] + best_route[j + 1 :]
                new_dist = total_distance(new_route)
                if new_dist < best_dist - 0.01:
                    best_route = new_route
                    best_dist = new_dist
                    improved = True
                    break
            if improved:
                break

    return best_route
