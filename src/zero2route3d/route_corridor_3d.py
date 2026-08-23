"""3D Route Corridor extractor: buffers multi-route paths by 30m and extracts real 3D OSM buildings and 3D volumetric trees."""

from __future__ import annotations

import contextlib
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .kinematics import haversine_distance_2d
from .osm_downloader import OsmBuilding, OsmPark, OsmTree


def point_to_segment_distance_meters(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """Distance in meters from point P(px,py) to segment AB in WGS84."""
    if not (
        math.isfinite(px)
        and math.isfinite(py)
        and math.isfinite(ax)
        and math.isfinite(ay)
        and math.isfinite(bx)
        and math.isfinite(by)
    ):
        return float("inf")

    # Convert local dx, dy to approximate meters
    cos_lat = math.cos(math.radians((ay + by) * 0.5))
    dx = (bx - ax) * 111320.0 * cos_lat
    dy = (by - ay) * 110540.0
    seg_len_sq = dx * dx + dy * dy
    if not math.isfinite(seg_len_sq) or seg_len_sq <= 1e-9:
        return haversine_distance_2d((px, py), (ax, ay))

    p_dx = (px - ax) * 111320.0 * cos_lat
    p_dy = (py - ay) * 110540.0
    num = p_dx * dx + p_dy * dy
    if not math.isfinite(num):
        return haversine_distance_2d((px, py), (ax, ay))

    t = max(0.0, min(1.0, num / seg_len_sq))

    proj_x = ax + t * (bx - ax)
    proj_y = ay + t * (by - ay)
    return haversine_distance_2d((px, py), (proj_x, proj_y))


def point_to_linestring_distance_meters(
    px: float, py: float, linestring: Sequence[Tuple[float, float]]
) -> float:
    """Minimum distance in meters from point P to a polyline."""
    if not linestring:
        return float("inf")
    if len(linestring) == 1:
        return haversine_distance_2d((px, py), linestring[0])

    min_d = float("inf")
    for i in range(len(linestring) - 1):
        d = point_to_segment_distance_meters(
            px, py, linestring[i][0], linestring[i][1], linestring[i + 1][0], linestring[i + 1][1]
        )
        if d < min_d:
            min_d = d
    return min_d


def point_to_multi_linestrings_distance_meters(
    px: float, py: float, linestrings: Sequence[Sequence[Tuple[float, float]]]
) -> float:
    """Minimum distance in meters from point P to any polyline in the collection."""
    if not linestrings:
        return float("inf")
    min_d = float("inf")
    for line in linestrings:
        d = point_to_linestring_distance_meters(px, py, line)
        if d < min_d:
            min_d = d
    return min_d


def get_closest_route_elevation(
    px: float, py: float, route_coords: Sequence[Tuple[float, float, ...]]
) -> float:
    """Find the ground elevation of the closest point along a 3D route polyline."""
    if not route_coords:
        return 0.0
    if len(route_coords) == 1:
        return (
            float(route_coords[0][2])
            if len(route_coords[0]) > 2 and math.isfinite(float(route_coords[0][2]))
            else 0.0
        )

    min_d = float("inf")
    closest_z = (
        float(route_coords[0][2])
        if len(route_coords[0]) > 2 and math.isfinite(float(route_coords[0][2]))
        else 0.0
    )

    for i in range(len(route_coords) - 1):
        p1 = route_coords[i]
        p2 = route_coords[i + 1]
        z1 = float(p1[2]) if len(p1) > 2 and math.isfinite(float(p1[2])) else 0.0
        z2 = float(p2[2]) if len(p2) > 2 and math.isfinite(float(p2[2])) else 0.0
        d = point_to_segment_distance_meters(px, py, p1[0], p1[1], p2[0], p2[1])
        if d < min_d:
            min_d = d
            closest_z = (z1 + z2) * 0.5
    return closest_z


def get_closest_multi_route_elevation(
    px: float,
    py: float,
    all_routes: Sequence[Sequence[Tuple[float, float, ...]]],
    green_sampler: Optional[Any] = None,
) -> float:
    """Find ground elevation using the green_sampler DEM if available, or closest multi-route elevation."""
    if green_sampler is not None and hasattr(green_sampler, "sample_elevation"):
        with contextlib.suppress(Exception):
            elev = green_sampler.sample_elevation(px, py)
            if math.isfinite(elev) and elev != 0.0:
                return float(elev)

    if not all_routes:
        return 0.0

    min_d = float("inf")
    best_z = 0.0
    for route in all_routes:
        if not route:
            continue
        for i in range(len(route) - 1):
            p1 = route[i]
            p2 = route[i + 1]
            z1 = float(p1[2]) if len(p1) > 2 and math.isfinite(float(p1[2])) else 0.0
            z2 = float(p2[2]) if len(p2) > 2 and math.isfinite(float(p2[2])) else 0.0
            d = point_to_segment_distance_meters(px, py, p1[0], p1[1], p2[0], p2[1])
            if d < min_d:
                min_d = d
                best_z = (z1 + z2) * 0.5
    return best_z


def filter_corridor_assets_multi_route(
    routes_coords: Sequence[Any],
    buildings: Sequence[OsmBuilding],
    buffer_meters: float = 30.0,
    green_sampler: Optional[Any] = None,
    osm_trees: Optional[Sequence[OsmTree]] = None,
    osm_parks: Optional[Sequence[OsmPark]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Multi-route corridor asset extractor.

    Buffers across ALL active route paths (30m buffer default) to extract:
    1. Real 3D OSM buildings within the multi-route buffer with calculated base elevations and levels.
    2. Real & volumetric 3D trees placed along greenery / park / corridor zones within the 30m buffer.

    Returns:
        (corridor_buildings, corridor_trees)
    """
    if not routes_coords:
        return [], []

    # Handle input flexibility: routes_coords can be a list of routes or a single route
    cleaned_routes: List[List[Tuple[float, float, float]]] = []
    if len(routes_coords) > 0:
        first_elem = routes_coords[0]
        if (
            isinstance(first_elem, (list, tuple))
            and len(first_elem) > 0
            and isinstance(first_elem[0], (int, float))
        ):
            route_list = [routes_coords]
        else:
            route_list = list(routes_coords)
    else:
        return [], []

    for r in route_list:
        if not r or len(r) < 2:
            continue
        valid_pts = []
        for c in r:
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                lon_v = float(c[0])
                lat_v = float(c[1])
                ele_v = float(c[2]) if len(c) > 2 and math.isfinite(float(c[2])) else 0.0
                if math.isfinite(lon_v) and math.isfinite(lat_v):
                    valid_pts.append((lon_v, lat_v, ele_v))
        if len(valid_pts) >= 2:
            cleaned_routes.append(valid_pts)

    if not cleaned_routes:
        return [], []

    buf_m = float(buffer_meters) if math.isfinite(buffer_meters) and buffer_meters >= 0 else 30.0
    all_lines_2d = [[(p[0], p[1]) for p in r] for r in cleaned_routes]

    # Global bounding box across all routes
    all_lons = [p[0] for line in all_lines_2d for p in line]
    all_lats = [p[1] for line in all_lines_2d for p in line]
    margin_deg = (buf_m + 35.0) / 75000.0
    min_rx = min(all_lons) - margin_deg
    max_rx = max(all_lons) + margin_deg
    min_ry = min(all_lats) - margin_deg
    max_ry = max(all_lats) + margin_deg

    # -------------------------------------------------------------
    # 1. Extract 3D Buildings within 30m multi-route buffer
    # -------------------------------------------------------------
    corridor_buildings: List[Dict[str, Any]] = []
    building_centroids: List[Tuple[float, float, float]] = []  # (lon, lat, radius_m)
    seen_building_ids = set()

    for b in buildings or []:
        if not b.polygon or len(b.polygon) < 3:
            continue

        b_id = str(b.building_id)
        if b_id in seen_building_ids:
            continue

        valid_poly = [
            (float(p[0]), float(p[1]))
            for p in b.polygon
            if len(p) >= 2 and math.isfinite(float(p[0])) and math.isfinite(float(p[1]))
        ]
        if len(valid_poly) < 3:
            continue

        c_lon = sum(p[0] for p in valid_poly) / len(valid_poly)
        c_lat = sum(p[1] for p in valid_poly) / len(valid_poly)

        # Fast AABB skip
        if c_lon < min_rx or c_lon > max_rx or c_lat < min_ry or c_lat > max_ry:
            continue

        d = point_to_multi_linestrings_distance_meters(c_lon, c_lat, all_lines_2d)
        if d <= buf_m + 15.0:  # Include footprint extent
            seen_building_ids.add(b_id)
            base_z = get_closest_multi_route_elevation(c_lon, c_lat, cleaned_routes, green_sampler)
            h_m = float(b.height_m) if math.isfinite(b.height_m) and b.height_m > 0 else 12.0
            lvls = int(b.levels) if b.levels > 0 else 4

            # Calculate approximate footprint radius for tree collision avoidance
            max_poly_rad = max(haversine_distance_2d((c_lon, c_lat), p) for p in valid_poly)
            building_centroids.append((c_lon, c_lat, max_poly_rad + 3.0))

            corridor_buildings.append(
                {
                    "id": b_id,
                    "coordinates": [[round(p[0], 6), round(p[1], 6)] for p in valid_poly],
                    "height_m": round(h_m, 1),
                    "levels": lvls,
                    "type": b.building_type,
                    "base_elevation_m": round(base_z, 2),
                }
            )

    # -------------------------------------------------------------
    # 2. Extract Real & Volumetric 3D Trees in 30m corridor buffer
    # -------------------------------------------------------------
    corridor_trees: List[Dict[str, Any]] = []
    placed_tree_positions: List[Tuple[float, float]] = []

    # 2.1 First place real OSM trees & tree rows
    if osm_trees:
        for t in osm_trees:
            if not (math.isfinite(t.lon) and math.isfinite(t.lat)):
                continue
            d = point_to_multi_linestrings_distance_meters(t.lon, t.lat, all_lines_2d)
            if d > buf_m + 5.0 or d < 1.0:
                continue

            # Check building collision
            collides_bld = any(
                haversine_distance_2d((t.lon, t.lat), (b_lon, b_lat)) < b_rad
                for b_lon, b_lat, b_rad in building_centroids
            )
            if collides_bld:
                continue

            # Check tree-to-tree spacing
            if any(
                haversine_distance_2d((t.lon, t.lat), pos) < 5.0 for pos in placed_tree_positions
            ):
                continue

            tree_z = get_closest_multi_route_elevation(t.lon, t.lat, cleaned_routes, green_sampler)
            corridor_trees.append(
                {
                    "id": f"osm_tree_{t.tree_id}",
                    "coordinates": [round(t.lon, 6), round(t.lat, 6)],
                    "base_elevation_m": round(tree_z, 2),
                    "height_m": round(t.height_m, 1),
                    "canopy_radius_m": round(t.canopy_radius_m, 1),
                    "trunk_height_m": round(t.height_m * 0.3, 1),
                    "trunk_radius_m": round(max(0.18, t.canopy_radius_m * 0.08), 2),
                    "tree_type": t.tree_type,
                    "species": t.species,
                    "greenery_index": 0.85,
                }
            )
            placed_tree_positions.append((t.lon, t.lat))

    # 2.2 Place trees inside real OSM park/greenery polygons in corridor
    if osm_parks:
        for p in osm_parks:
            if not p.polygon or len(p.polygon) < 3:
                continue
            poly_lons = [pt[0] for pt in p.polygon]
            poly_lats = [pt[1] for pt in p.polygon]
            c_lon = sum(poly_lons) / len(poly_lons)
            c_lat = sum(poly_lats) / len(poly_lats)
            d = point_to_multi_linestrings_distance_meters(c_lon, c_lat, all_lines_2d)
            if d <= buf_m + 10.0:
                # Add park trees
                for pt in p.polygon:
                    pt_lon, pt_lat = pt[0], pt[1]
                    dist_to_route = point_to_multi_linestrings_distance_meters(
                        pt_lon, pt_lat, all_lines_2d
                    )
                    if 4.0 <= dist_to_route <= buf_m:
                        if not any(
                            haversine_distance_2d((pt_lon, pt_lat), pos) < 8.0
                            for pos in placed_tree_positions
                        ):
                            if not any(
                                haversine_distance_2d((pt_lon, pt_lat), (b_lon, b_lat)) < b_rad
                                for b_lon, b_lat, b_rad in building_centroids
                            ):
                                tree_z = get_closest_multi_route_elevation(
                                    pt_lon, pt_lat, cleaned_routes, green_sampler
                                )
                                corridor_trees.append(
                                    {
                                        "id": f"park_tree_{len(corridor_trees) + 1}",
                                        "coordinates": [round(pt_lon, 6), round(pt_lat, 6)],
                                        "base_elevation_m": round(tree_z, 2),
                                        "height_m": 9.0,
                                        "canopy_radius_m": 3.8,
                                        "trunk_height_m": 2.2,
                                        "trunk_radius_m": 0.32,
                                        "tree_type": "broadleaf",
                                        "species": p.name or "park",
                                        "greenery_index": 0.9,
                                    }
                                )
                                placed_tree_positions.append((pt_lon, pt_lat))

    # 2.3 Lateral procedural corridor greenery where trees are sparse
    lateral_offsets = [-24.0, -16.0, -9.0, 9.0, 16.0, 24.0]
    step_interval_m = 18.0

    for route in cleaned_routes:
        for i in range(len(route) - 1):
            p1 = route[i]
            p2 = route[i + 1]
            seg_dist = haversine_distance_2d((p1[0], p1[1]), (p2[0], p2[1]))
            if seg_dist < 2.0:
                continue

            num_steps = max(1, int(round(seg_dist / step_interval_m)))
            cos_mid_lat = math.cos(math.radians((p1[1] + p2[1]) * 0.5))

            # Direction vector in approximate meters
            dx_m = (p2[0] - p1[0]) * 111320.0 * cos_mid_lat
            dy_m = (p2[1] - p1[1]) * 110540.0
            seg_len = math.sqrt(dx_m * dx_m + dy_m * dy_m)
            if seg_len < 1e-6:
                continue

            # Unit normal vector (perpendicular to road direction)
            nx = -dy_m / seg_len
            ny = dx_m / seg_len

            for s in range(num_steps):
                t = (s + 0.5) / num_steps
                center_lon = p1[0] + t * (p2[0] - p1[0])
                center_lat = p1[1] + t * (p2[1] - p1[1])

                for offset_m in lateral_offsets:
                    if abs(offset_m) > buf_m:
                        continue

                    # Offset in degrees
                    cand_lon = center_lon + (nx * offset_m) / (
                        111320.0 * math.cos(math.radians(center_lat))
                    )
                    cand_lat = center_lat + (ny * offset_m) / 110540.0

                    # 1. Check distance to route paths: must be >= 4.5m and <= 30m
                    dist_to_route = point_to_multi_linestrings_distance_meters(
                        cand_lon, cand_lat, all_lines_2d
                    )
                    if dist_to_route < 4.5 or dist_to_route > buf_m + 2.0:
                        continue

                    # 2. Check collision with building footprints
                    collides_building = False
                    for b_lon, b_lat, b_rad in building_centroids:
                        if haversine_distance_2d((cand_lon, cand_lat), (b_lon, b_lat)) < b_rad:
                            collides_building = True
                            break
                    if collides_building:
                        continue

                    # 3. Check spacing against already placed trees (min 9m spacing)
                    collides_tree = False
                    for t_pos in placed_tree_positions:
                        if haversine_distance_2d((cand_lon, cand_lat), t_pos) < 9.0:
                            collides_tree = True
                            break
                    if collides_tree:
                        continue

                    # 4. Greenery sampling (if green_sampler is available)
                    green_val = 0.55
                    if green_sampler is not None and hasattr(green_sampler, "sample_greenery"):
                        try:
                            green_val = float(green_sampler.sample_greenery(cand_lon, cand_lat))
                        except Exception:
                            green_val = 0.55

                    if green_val < 0.15:
                        continue

                    # 5. Deterministic hash variation for realistic tree morphology
                    coord_key = (round(cand_lon, 5), round(cand_lat, 5))
                    h_val = abs(hash(coord_key))

                    # Tree dimensions modulated by greenery and hash
                    height_m = round(5.5 + (h_val % 45) * 0.12 + green_val * 2.8, 1)
                    canopy_radius_m = round(2.0 + (h_val % 25) * 0.09 + green_val * 1.3, 1)
                    trunk_height_m = round(1.5 + (h_val % 18) * 0.08, 1)
                    trunk_radius_m = round(0.20 + (h_val % 12) * 0.015, 2)
                    tree_types = ["deciduous", "broadleaf", "conifer", "pine"]
                    tree_type = tree_types[h_val % len(tree_types)]

                    tree_z = get_closest_multi_route_elevation(
                        cand_lon, cand_lat, cleaned_routes, green_sampler
                    )

                    tree_id = f"tree_{len(corridor_trees) + 1}"
                    placed_tree_positions.append((cand_lon, cand_lat))

                    corridor_trees.append(
                        {
                            "id": tree_id,
                            "coordinates": [round(cand_lon, 6), round(cand_lat, 6)],
                            "base_elevation_m": round(tree_z, 2),
                            "height_m": height_m,
                            "canopy_radius_m": canopy_radius_m,
                            "trunk_height_m": trunk_height_m,
                            "trunk_radius_m": trunk_radius_m,
                            "tree_type": tree_type,
                            "greenery_index": round(green_val, 2),
                        }
                    )

    return corridor_buildings, corridor_trees


def filter_buildings_in_corridor(
    route_coords: Sequence[Tuple[float, float, float]],
    buildings: Sequence[OsmBuilding],
    buffer_meters: float = 30.0,
) -> List[Dict[str, Any]]:
    """Extract real OSM buildings that fall within the specified corridor buffer around the route."""
    blds, _ = filter_corridor_assets_multi_route(
        [route_coords], buildings, buffer_meters=buffer_meters
    )
    return blds
