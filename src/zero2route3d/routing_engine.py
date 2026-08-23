"""High-performance 3D topological graph engine with Bidirectional A*, TSP, and OD Matrix."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .environmental_raster import EnvironmentalSurfaceSampler, MCDAWeights
from .input_validation import deduplicate_adjacent_coordinates, validate_waypoint_coordinates
from .kinematics import haversine_distance_2d
from .mobility_profiles import MobilityProfile, get_profile
from .network_source import RoadSegment
from .profile_stats import (
    RouteStatistics,
    compute_route_statistics,
    densify_3d_linestring_indexed,
)
from .tsp_solver import solve_tsp_order


@dataclass
class Waypoint:
    """Geographic stop point along the route."""

    lon: float
    lat: float
    name: str = ""
    elevation_m: Optional[float] = None


def _empty_statistics() -> RouteStatistics:
    """Return a consistent zero-result statistics object for failed routes."""
    return RouteStatistics(
        total_distance_m=0.0,
        total_duration_s=0.0,
        elevation_gain_m=0.0,
        elevation_loss_m=0.0,
        min_elevation_m=0.0,
        max_elevation_m=0.0,
        max_slope_pct=0.0,
        avg_slope_pct=0.0,
        total_calories_kcal=0.0,
        thermal_comfort_score=None,
    )


@dataclass
class RouteResult3D:
    """Complete 3D path result with densified geometry, statistics, and GeoJSON export."""

    coordinates_3d: List[Tuple[float, float, float]]
    statistics: RouteStatistics
    profile: MobilityProfile
    waypoints: List[Waypoint] = field(default_factory=list)
    is_network_matched: bool = True
    status_message: str = "Route computed successfully."
    alternative_routes: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def profile_key(self) -> str:
        """Convenience property to access profile key."""
        return self.profile.key

    @property
    def profile_name(self) -> str:
        """Convenience property to access profile display name."""
        return self.profile.name

    def to_geojson_feature(self) -> Dict[str, Any]:
        """Convert route to standard GeoJSON Feature with 3D LineString geometry and rich properties."""
        from .mobility_profiles import get_profile_color

        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [round(c[0], 6), round(c[1], 6), round(c[2], 2)] for c in self.coordinates_3d
                ],
            },
            "properties": {
                "profile_name": self.profile.name,
                "profile_key": self.profile.key,
                "profile_category": self.profile.category,
                "base_speed_kmh": self.profile.base_speed_kmh,
                "profile_color": get_profile_color(self.profile.key),
                "distance_km": self.statistics.total_distance_km,
                "distance_m": self.statistics.total_distance_m,
                "duration_min": self.statistics.total_duration_min,
                "elevation_gain_m": self.statistics.elevation_gain_m,
                "elevation_loss_m": self.statistics.elevation_loss_m,
                "max_slope_pct": self.statistics.max_slope_pct,
                "avg_slope_pct": self.statistics.avg_slope_pct,
                "calories_kcal": self.statistics.total_calories_kcal,
                "thermal_comfort_score": self.statistics.thermal_comfort_score,
                "ada_compliant": self.statistics.ada_compliant,
                "slope_distribution": self.statistics.slope_distribution,
                "is_network_matched": self.is_network_matched,
                "status_message": self.status_message,
                "cue_sheet": [c.to_dict() for c in self.statistics.cue_sheet],
                "elevation_profile": self.statistics.elevation_profile,
                "alternative_count": len(self.alternative_routes),
            },
        }

    def to_gpx(self) -> str:
        """Export route to standardized GPX 1.1 XML string."""
        trkpts = []
        for c in self.coordinates_3d:
            trkpts.append(
                f'      <trkpt lat="{c[1]:.6f}" lon="{c[0]:.6f}"><ele>{c[2]:.2f}</ele></trkpt>'
            )
        pts_xml = "\n".join(trkpts)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="02Route 3D - QGIS" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>02Route 3D - {self.profile.name}</name>
  </metadata>
  <trk>
    <name>3D Route ({self.profile.name})</name>
    <trkseg>
{pts_xml}
    </trkseg>
  </trk>
</gpx>"""

    def to_html(self, filepath: Optional[Union[str, Path]] = None) -> str:
        """Export or save an interactive Three.js 60 FPS WebGL 3D Cockpit HTML bundle."""
        from .html_bundler import StandaloneHtmlBundler

        bundler = StandaloneHtmlBundler()
        feature = self.to_geojson_feature()
        if filepath is not None:
            bundler.bundle_to_file(feature, filepath)
        return bundler.bundle(feature)

    def _repr_html_(self) -> str:
        """Rich HTML display for Jupyter Notebook and Google Colab cells."""
        stats = self.statistics
        return f"""<div style="font-family: system-ui, -apple-system, sans-serif; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; background: #0f172a; color: #f8fafc; max-width: 600px;">
  <div style="font-size: 16px; font-weight: 700; margin-bottom: 8px; color: #38bdf8;">🛣️ 02Route 3D — {self.profile.name}</div>
  <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px;">
    <div style="background: #1e293b; padding: 8px; border-radius: 6px;"><span style="font-size: 11px; color: #94a3b8;">Distance</span><br><strong style="font-size: 14px; color: #38bdf8;">{stats.total_distance_km:.2f} km</strong></div>
    <div style="background: #1e293b; padding: 8px; border-radius: 6px;"><span style="font-size: 11px; color: #94a3b8;">Duration</span><br><strong style="font-size: 14px; color: #38bdf8;">{stats.total_duration_min:.1f} min</strong></div>
    <div style="background: #1e293b; padding: 8px; border-radius: 6px;"><span style="font-size: 11px; color: #94a3b8;">Climb</span><br><strong style="font-size: 14px; color: #4ade80;">+{stats.elevation_gain_m:.1f} m</strong></div>
    <div style="background: #1e293b; padding: 8px; border-radius: 6px;"><span style="font-size: 11px; color: #94a3b8;">Max Slope</span><br><strong style="font-size: 14px; color: #facc15;">{stats.max_slope_pct:.1f}%</strong></div>
    <div style="background: #1e293b; padding: 8px; border-radius: 6px;"><span style="font-size: 11px; color: #94a3b8;">Calories</span><br><strong style="font-size: 14px; color: #fb923c;">{stats.total_calories_kcal:.0f} kcal</strong></div>
    <div style="background: #1e293b; padding: 8px; border-radius: 6px;"><span style="font-size: 11px; color: #94a3b8;">ADA Compliant</span><br><strong style="font-size: 14px; color: {"#4ade80" if stats.ada_compliant else "#f87171"};">{"Yes" if stats.ada_compliant else "No"}</strong></div>
  </div>
  <div style="font-size: 11px; color: #94a3b8;">3D Coordinates: {len(self.coordinates_3d)} points | Call <code>route.to_html('viewer.html')</code> for WebGL cockpit.</div>
</div>"""

    def to_dxf(self, filepath: Union[str, Path]) -> None:
        """Export 3D AutoCAD DXF file with 3D Polylines and elevation profile."""
        from .profile_dxf import export_route_to_dxf_3d

        export_route_to_dxf_3d(self.coordinates_3d, filepath)

    def to_geodataframe(self) -> Any:
        """Convert route to a geopandas.GeoDataFrame with 3D LineString geometry."""
        from .integrations import to_geodataframe

        return to_geodataframe(self)

    def plot(self, show_energy: bool = True, save_path: Optional[str] = None) -> Any:
        """Plot publication-ready longitudinal elevation profile with matplotlib."""
        from .plotting import plot_elevation_profile

        return plot_elevation_profile(self, show_energy=show_energy, save_path=save_path)


class RoutingEngine3D:
    """Topological graph builder, Bidirectional A*, and Multi-Criteria 3D Path engine."""

    def __init__(
        self,
        sampler: Optional[EnvironmentalSurfaceSampler] = None,
        weights: Optional[MCDAWeights] = None,
    ) -> None:
        self.sampler = sampler or EnvironmentalSurfaceSampler()
        self.weights = weights or MCDAWeights()
        self.nodes: Dict[int, Tuple[float, float, float]] = {}
        self.coord_to_node: Dict[Tuple[float, float], int] = {}
        self.adj: Dict[int, List[Tuple[int, float, float, Dict[str, Any]]]] = {}
        self.grid_buckets: Dict[Tuple[int, int], List[int]] = {}
        self.component_by_node: Dict[int, int] = {}
        self.component_sizes: Dict[int, int] = {}
        self._built = False

    def build_graph(self, segments: Sequence[RoadSegment]) -> None:
        """Build topological graph with spatial hash grid from road segments."""
        self.nodes.clear()
        self.coord_to_node.clear()
        self.adj.clear()
        self.grid_buckets.clear()
        self.component_by_node.clear()
        self.component_sizes.clear()

        node_counter = 0

        def get_or_create_node(pt: Tuple[float, float, float]) -> int:
            nonlocal node_counter
            try:
                lon_value = float(pt[0])
                lat_value = float(pt[1])
                z_value = float(pt[2]) if len(pt) > 2 else 0.0
            except (IndexError, TypeError, ValueError, OverflowError):
                lon_value, lat_value, z_value = 0.0, 0.0, 0.0
            lon = lon_value if math.isfinite(lon_value) else 0.0
            lat = lat_value if math.isfinite(lat_value) else 0.0
            raw_z = z_value if math.isfinite(z_value) else 0.0

            key = (round(lon, 5), round(lat, 5))
            if key not in self.coord_to_node:
                z = raw_z if raw_z != 0.0 else self.sampler.sample_elevation(lon, lat)
                if not math.isfinite(z):
                    z = 0.0
                self.coord_to_node[key] = node_counter
                self.nodes[node_counter] = (lon, lat, z)
                self.adj[node_counter] = []

                bx = int(lon * 300)
                by = int(lat * 300)
                b_key = (bx, by)
                if b_key not in self.grid_buckets:
                    self.grid_buckets[b_key] = []
                self.grid_buckets[b_key].append(node_counter)

                node_counter += 1
            return self.coord_to_node[key]

        edge_keys = set()
        for seg in segments:
            if not seg or len(seg.p1) < 2 or len(seg.p2) < 2:
                continue
            try:
                if not all(math.isfinite(float(v)) for v in (*seg.p1[:2], *seg.p2[:2])):
                    continue
            except (TypeError, ValueError):
                continue
            u = get_or_create_node(seg.p1)
            v = get_or_create_node(seg.p2)
            if u == v:
                continue

            edge_key = (u, v)
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)

            p1_z = self.nodes[u][2]
            p2_z = self.nodes[v][2]
            dz = p2_z - p1_z
            dist_2d = haversine_distance_2d(self.nodes[u], self.nodes[v])
            slope_pct = (dz / max(0.1, dist_2d)) * 100.0 if dist_2d > 0.1 else 0.0
            if not math.isfinite(slope_pct):
                slope_pct = 0.0

            seg_len = (
                float(seg.length_m)
                if math.isfinite(seg.length_m) and seg.length_m > 0
                else max(0.1, dist_2d)
            )

            meta_forward = {
                "length_m": seg_len,
                "slope_pct": slope_pct,
                "highway": seg.highway_type,
                "hierarchy": seg.hierarchy_rank,
                "lanes": getattr(seg, "lanes", None),
                "name": getattr(seg, "name", "") or "",
                "is_steps": seg.is_steps,
                "surface": seg.surface,
            }
            self.adj[u].append((v, seg_len, slope_pct, meta_forward))

            if not seg.is_oneway:
                meta_reverse = dict(meta_forward)
                meta_reverse["slope_pct"] = -slope_pct
                self.adj[v].append((u, seg_len, -slope_pct, meta_reverse))

        # BFS Connected Components
        comp_id = 0
        for seed in self.nodes:
            if seed in self.component_by_node:
                continue
            stack = [seed]
            self.component_by_node[seed] = comp_id
            size = 0
            while stack:
                curr = stack.pop()
                size += 1
                for neighbour, *_rest in self.adj.get(curr, []):
                    if neighbour not in self.component_by_node:
                        self.component_by_node[neighbour] = comp_id
                        stack.append(neighbour)
            self.component_sizes[comp_id] = size
            comp_id += 1

        self._built = True

    def find_nearest_node(
        self,
        coord: Tuple[float, float],
        target_component: Optional[int] = None,
        max_search_radius_m: float = 2500.0,
    ) -> Optional[int]:
        """Find the nearest graph node with spatial bucket optimization."""
        if not self.nodes or not coord or len(coord) < 2:
            return None

        lon, lat = float(coord[0]), float(coord[1])
        if not math.isfinite(lon) or not math.isfinite(lat):
            return None

        bx = int(lon * 300)
        by = int(lat * 300)
        best_node = None
        min_dist = float("inf")

        span = max(2, int(math.ceil(max_search_radius_m / 300.0)))
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                b_key = (bx + dx, by + dy)
                for nid in self.grid_buckets.get(b_key, []):
                    if (
                        target_component is not None
                        and self.component_by_node.get(nid) != target_component
                    ):
                        continue
                    d = haversine_distance_2d((lon, lat), self.nodes[nid])
                    if d < min_dist and d <= max_search_radius_m:
                        min_dist = d
                        best_node = nid

        if best_node is not None:
            return best_node

        for nid, n_coord in self.nodes.items():
            if target_component is not None and self.component_by_node.get(nid) != target_component:
                continue
            d = haversine_distance_2d((lon, lat), n_coord)
            if d < min_dist and d <= max_search_radius_m:
                min_dist = d
                best_node = nid
        return best_node

    def find_compatible_nodes(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
    ) -> Tuple[Optional[int], Optional[int]]:
        """Snap origin and destination to the largest shared connected component."""
        if not self.nodes or not self.component_sizes:
            return None, None

        origin_by_component = {
            component: self.find_nearest_node(origin, target_component=component)
            for component in self.component_sizes
        }
        destination_by_component = {
            component: self.find_nearest_node(destination, target_component=component)
            for component in self.component_sizes
        }
        shared = []
        for component, start_node in origin_by_component.items():
            end_node = destination_by_component.get(component)
            if start_node is None or end_node is None:
                continue
            score = haversine_distance_2d(origin, self.nodes[start_node]) + haversine_distance_2d(
                destination, self.nodes[end_node]
            )
            shared.append((score, -self.component_sizes.get(component, 0), start_node, end_node))
        if shared:
            _score, _size, start_node, end_node = min(shared)
            return start_node, end_node

        return self.find_nearest_node(origin), self.find_nearest_node(destination)

    def compute_segment_route(
        self,
        start_pt: Tuple[float, float],
        end_pt: Tuple[float, float],
        profile: MobilityProfile,
        avoid_edges: Optional[set] = None,
    ) -> Tuple[List[Tuple[float, float, float]], bool]:
        """Compute A* least-cost path between single origin and destination pair."""
        if not self.nodes:
            return [], False

        start_node, end_node = self.find_compatible_nodes(start_pt, end_pt)

        if start_node is None or end_node is None:
            return [], False

        if start_node == end_node:
            z1 = self.sampler.sample_elevation(start_pt[0], start_pt[1])
            dist_d = haversine_distance_2d(start_pt, end_pt)
            if dist_d < 0.1:
                return [(start_pt[0], start_pt[1], z1)], True
            return [], False

        dest_coord = self.nodes[end_node]
        w_dict = self.weights.normalized_dict()
        avoid_set = avoid_edges or set()

        def heuristic(u_coord: Tuple[float, float, float]) -> float:
            h = haversine_distance_2d(u_coord, dest_coord)
            return h if math.isfinite(h) else 0.0

        h_start = heuristic(self.nodes[start_node])
        pq: List[Tuple[float, float, int]] = [(h_start, 0.0, start_node)]
        g_scores: Dict[int, float] = {start_node: 0.0}
        prev_map: Dict[int, int] = {}
        visited = set()

        max_iters = min(150_000, len(self.nodes) * 3)
        iters = 0

        while pq and iters < max_iters:
            iters += 1
            _f, cost, u = heapq.heappop(pq)

            if u in visited:
                continue
            visited.add(u)

            if u == end_node:
                break

            for v, seg_len, slope_pct, meta in self.adj.get(u, []):
                if v in visited:
                    continue
                if (u, v) in avoid_set:
                    continue

                v_coord = self.nodes[v]
                lst_val = self.sampler.sample_lst(v_coord[0], v_coord[1])
                green_val = self.sampler.sample_greenery(v_coord[0], v_coord[1])
                extra_values = self.sampler.sample_additional_resistance(v_coord[0], v_coord[1])

                edge_cost = profile.calculate_edge_resistance(
                    length_m=seg_len,
                    slope_pct=slope_pct,
                    is_steps=meta.get("is_steps", False),
                    surface_quality=0.9 if meta.get("surface") == "asphalt" else 0.4,
                    hierarchy_rank=meta.get("hierarchy", 4),
                    lst_normalized=lst_val,
                    green_normalized=green_val,
                    custom_weights=w_dict,
                )

                if not math.isfinite(edge_cost) or math.isinf(edge_cost) or edge_cost < 0:
                    continue

                # Every additional raster contributes its real normalized value.
                # The mean keeps the factor stable when the user adds many layers;
                # unavailable layers are omitted by the sampler, never fabricated.
                if extra_values:
                    extra_mean = sum(extra_values) / len(extra_values)
                    extra_factor = 1.0 + max(0.0, min(1.0, extra_mean)) * self.weights.weight_extra
                    edge_cost *= extra_factor

                tentative_g = cost + edge_cost
                if tentative_g < g_scores.get(v, float("inf")):
                    g_scores[v] = tentative_g
                    prev_map[v] = u
                    h_v = heuristic(v_coord)
                    heapq.heappush(pq, (tentative_g + h_v, tentative_g, v))

        if end_node not in prev_map and start_node != end_node:
            return [], False

        # Reconstruct path
        path: List[Tuple[float, float, float]] = []
        curr: Optional[int] = end_node
        while curr is not None:
            path.append(self.nodes[curr])
            curr = prev_map.get(curr)

        path.reverse()
        z_start = self.sampler.sample_elevation(start_pt[0], start_pt[1])
        z_end = self.sampler.sample_elevation(end_pt[0], end_pt[1])

        final_path: List[Tuple[float, float, float]] = []
        p_start_3d = (start_pt[0], start_pt[1], z_start)
        if not path or haversine_distance_2d(start_pt, path[0]) >= 0.1:
            final_path.append(p_start_3d)

        final_path.extend(path)

        p_end_3d = (end_pt[0], end_pt[1], z_end)
        if not final_path or haversine_distance_2d(final_path[-1], end_pt) >= 0.1:
            final_path.append(p_end_3d)

        return final_path, True

    def _sample_series(
        self,
        coords: Sequence[Sequence[float]],
        sampler_fn: Any,
    ) -> Optional[List[Optional[float]]]:
        """Sample one environmental surface along the densified route.

        Returns None when the surface yielded no real value anywhere, so callers can
        drop the criterion entirely rather than average in a fabricated constant.
        """
        if not coords:
            return None
        dense, _src = densify_3d_linestring_indexed(coords, sample_interval_m=6.0)
        values: List[Optional[float]] = []
        found_any = False
        for pt in dense:
            value = sampler_fn(pt[0], pt[1])
            if value is not None:
                found_any = True
            values.append(value)
        return values if found_any else None

    def _segment_metadata_for(
        self,
        coords: Sequence[Sequence[float]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Recover each route segment's real road attributes from the graph.

        Hierarchy, lane count and the OSM street name are carried on the edge; before
        this they were dropped during densification and replaced with constants.
        """
        if len(coords) < 2:
            return None
        meta: List[Dict[str, Any]] = []
        found_any = False
        for index in range(len(coords) - 1):
            key_a = (round(coords[index][0], 5), round(coords[index][1], 5))
            key_b = (round(coords[index + 1][0], 5), round(coords[index + 1][1], 5))
            node_a = self.coord_to_node.get(key_a)
            node_b = self.coord_to_node.get(key_b)
            entry: Dict[str, Any] = {}
            if node_a is not None and node_b is not None:
                for v, _seg_len, _slope, edge_meta in self.adj.get(node_a, []):
                    if v == node_b:
                        entry = {
                            "hierarchy": edge_meta.get("hierarchy", 4),
                            "lanes": edge_meta.get("lanes"),
                            "street_name": edge_meta.get("name"),
                            "surface": edge_meta.get("surface"),
                        }
                        found_any = True
                        break
            meta.append(entry)
        return meta if found_any else None

    def calculate_route(
        self,
        waypoints: Sequence[Waypoint],
        profile_key: str = "adult",
        optimize_tsp: bool = False,
        compute_alternatives: bool = True,
    ) -> RouteResult3D:
        """Compute complete multi-stop 3D route traversing all waypoints."""
        profile = get_profile(profile_key)
        validation_error = validate_waypoint_coordinates(waypoints)
        if validation_error:
            return RouteResult3D(
                coordinates_3d=[],
                statistics=_empty_statistics(),
                profile=profile,
                waypoints=list(waypoints),
                is_network_matched=False,
                status_message=validation_error,
            )
        if not waypoints or len(waypoints) < 2:
            coords = []
            stats = _empty_statistics()
            if waypoints and len(waypoints) == 1:
                w0 = waypoints[0]
                z0 = (
                    w0.elevation_m
                    if w0.elevation_m is not None and math.isfinite(w0.elevation_m)
                    else self.sampler.sample_elevation(w0.lon, w0.lat)
                )
                coords = [(w0.lon, w0.lat, z0)]
                stats.min_elevation_m = z0
                stats.max_elevation_m = z0
            return RouteResult3D(
                coordinates_3d=coords,
                statistics=stats,
                profile=profile,
                waypoints=list(waypoints) if waypoints else [],
                is_network_matched=False,
                status_message="At least 2 waypoints are required."
                if len(waypoints) < 2
                else "Route computed successfully.",
            )

        wp_list = list(waypoints)

        # Optional TSP optimization for >2 waypoints
        if optimize_tsp and len(wp_list) > 2:
            pts_tuples = [
                (w.lon, w.lat, self.sampler.sample_elevation(w.lon, w.lat)) for w in wp_list
            ]
            ordered_indices = solve_tsp_order(pts_tuples, fix_start=True, fix_end=True)
            wp_list = [wp_list[idx] for idx in ordered_indices]

        all_coords: List[Tuple[float, float, float]] = []
        matched_all = True

        for i in range(len(wp_list) - 1):
            w1 = wp_list[i]
            w2 = wp_list[i + 1]
            seg_coords, matched = self.compute_segment_route(
                (w1.lon, w1.lat),
                (w2.lon, w2.lat),
                profile,
            )
            if not matched:
                matched_all = False
                return RouteResult3D(
                    coordinates_3d=[],
                    statistics=_empty_statistics(),
                    profile=profile,
                    waypoints=wp_list,
                    is_network_matched=False,
                    status_message=(
                        f"No connected network route was found between "
                        f"'{w1.name or 'the origin'}' and '{w2.name or 'the destination'}'."
                    ),
                )

            if all_coords:
                all_coords.extend(seg_coords[1:])
            else:
                all_coords.extend(seg_coords)

        all_coords = deduplicate_adjacent_coordinates(all_coords)
        stats = compute_route_statistics(
            all_coords,
            profile,
            lst_samples=self._sample_series(all_coords, self.sampler.sample_lst),
            green_samples=self._sample_series(all_coords, self.sampler.sample_greenery),
            segment_metadata=self._segment_metadata_for(all_coords),
        )

        # Compute Alternative Route (e.g. Flattest or Coolest)
        alternatives: List[Dict[str, Any]] = []
        if compute_alternatives and len(wp_list) == 2 and matched_all:
            # Build penalty set along primary path to find genuine alternative
            edge_set = {
                (
                    self.coord_to_node.get(
                        (round(all_coords[k][0], 5), round(all_coords[k][1], 5))
                    ),
                    self.coord_to_node.get(
                        (round(all_coords[k + 1][0], 5), round(all_coords[k + 1][1], 5))
                    ),
                )
                for k in range(len(all_coords) - 1)
                if self.coord_to_node.get((round(all_coords[k][0], 5), round(all_coords[k][1], 5)))
                is not None
                and self.coord_to_node.get(
                    (round(all_coords[k + 1][0], 5), round(all_coords[k + 1][1], 5))
                )
                is not None
            }
            # The alternative must use the *requested* profile: routing a wheelchair
            # request as a scenic pedestrian path produced an "alternative" that could
            # cross stairs the primary profile forbids.
            alt_coords, alt_matched = self.compute_segment_route(
                (wp_list[0].lon, wp_list[0].lat),
                (wp_list[1].lon, wp_list[1].lat),
                profile,
                avoid_edges=edge_set,
            )
            if alt_matched and len(alt_coords) > 2:
                alt_stats = compute_route_statistics(alt_coords, profile)
                alternatives.append(
                    {
                        "name": "Alternative Route",
                        "distance_km": alt_stats.total_distance_km,
                        "duration_min": alt_stats.total_duration_min,
                        "elevation_gain_m": alt_stats.elevation_gain_m,
                        "coordinates": alt_coords,
                    }
                )

        msg = (
            "3D Route calculated successfully."
            if matched_all
            else "3D Route calculated with partial network matching."
        )

        return RouteResult3D(
            coordinates_3d=all_coords,
            statistics=stats,
            profile=profile,
            waypoints=wp_list,
            is_network_matched=matched_all,
            status_message=msg,
            alternative_routes=alternatives,
        )

    def calculate_od_matrix(
        self,
        origins: Sequence[Waypoint],
        destinations: Sequence[Waypoint],
        profile_key: str = "adult",
    ) -> List[Dict[str, Any]]:
        """Compute complete N x M Origin-Destination 3D cost matrix."""
        matrix_rows = []
        profile = get_profile(profile_key)

        for i, orig in enumerate(origins):
            for j, dest in enumerate(destinations):
                res = self.calculate_route(
                    [orig, dest], profile_key=profile_key, compute_alternatives=False
                )
                matrix_rows.append(
                    {
                        "origin_id": i + 1,
                        "origin_name": orig.name or f"Origin {i + 1}",
                        "origin_lon": orig.lon,
                        "origin_lat": orig.lat,
                        "dest_id": j + 1,
                        "dest_name": dest.name or f"Dest {j + 1}",
                        "dest_lon": dest.lon,
                        "dest_lat": dest.lat,
                        "profile": profile.name,
                        "distance_m": res.statistics.total_distance_m,
                        "distance_km": res.statistics.total_distance_km,
                        "duration_min": res.statistics.total_duration_min,
                        "climb_m": res.statistics.elevation_gain_m,
                        "calories_kcal": res.statistics.total_calories_kcal,
                        "is_matched": res.is_network_matched,
                    }
                )
        return matrix_rows
