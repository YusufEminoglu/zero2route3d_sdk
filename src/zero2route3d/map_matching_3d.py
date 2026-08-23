"""Real-Time GPS Track & GPX 3D Map Matching Engine.

Implements:
1. Hidden Markov Model (HMM) with Newson-Krumm emission & transition probabilities.
2. Viterbi Trellis Dynamic Programming for optimal topological path decoding.
3. Sub-pixel 3D elevation reconstruction and slope synthesis from high-res DEM.
4. Comprehensive GPX 1.1 parser and matched track telemetry exporter.

Author: Yusuf Eminoglu
"""

from __future__ import annotations

import contextlib
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .kinematics import haversine_distance_2d
from .micro_elevation import MicroElevationEngine


@dataclass
class GPXPoint:
    """Raw or filtered GPS track point."""

    lon: float
    lat: float
    elevation_raw_m: float = 0.0
    timestamp_iso: str = ""
    speed_ms: Optional[float] = None
    hdop: Optional[float] = None


@dataclass
class MatchedTrackPoint3D:
    """Topologically snapped 3D track point with reconstructed kinematics."""

    lon: float
    lat: float
    elevation_m: float
    snapped_edge_u: int
    snapped_edge_v: int
    lateral_residual_m: float
    reconstructed_slope_pct: float
    speed_kmh: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lon": round(self.lon, 6),
            "lat": round(self.lat, 6),
            "elevation_m": round(self.elevation_m, 2),
            "residual_m": round(self.lateral_residual_m, 2),
            "slope_pct": round(self.reconstructed_slope_pct, 2),
            "speed_kmh": round(self.speed_kmh, 1),
        }


@dataclass
class MapMatching3DResult:
    """Complete map-matched 3D trajectory result with diagnostics."""

    matched_points: List[MatchedTrackPoint3D]
    matched_nodes_path: List[int]
    total_raw_points: int
    mean_snapping_error_m: float
    total_matched_distance_m: float
    elevation_gain_m: float
    status_message: str

    def to_gpx(self) -> str:
        """Export snapped 3D trajectory to GPX 1.1 with rich telemetry extensions."""
        trkpts = []
        for p in self.matched_points:
            trkpts.append(
                f'      <trkpt lat="{p.lat:.6f}" lon="{p.lon:.6f}">\n'
                f"        <ele>{p.elevation_m:.2f}</ele>\n"
                f"        <extensions>\n"
                f"          <residual_m>{p.lateral_residual_m:.2f}</residual_m>\n"
                f"          <slope_pct>{p.reconstructed_slope_pct:.1f}</slope_pct>\n"
                f"        </extensions>\n"
                f"      </trkpt>"
            )
        pts_xml = "\n".join(trkpts)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="02Route 3D Map Matcher" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>02Route 3D Matched Trajectory</name></metadata>
  <trk>
    <name>3D Snapped Track</name>
    <trkseg>
{pts_xml}
    </trkseg>
  </trk>
</gpx>"""


class HMMMapMatcher3D:
    """Hidden Markov Model (HMM) 3D Map Matching with Viterbi decoding."""

    def __init__(
        self,
        nodes: Dict[int, Tuple[float, float, float]],
        adj: Dict[int, List[Tuple[int, float, float, Dict[str, Any]]]],
        micro_elevation: Optional[MicroElevationEngine] = None,
        sigma_z: float = 4.07,
        beta: float = 3.0,
    ) -> None:
        self.nodes = nodes
        self.adj = adj
        self.micro_elevation = micro_elevation or MicroElevationEngine()
        self.sigma_z = sigma_z
        self.beta = beta

    def _project_point_to_edge(
        self,
        pt: Tuple[float, float],
        u: int,
        v: int,
    ) -> Tuple[Tuple[float, float], float, float]:
        """Project (lon, lat) onto segment (u -> v). Returns (snapped_pt, distance_m, fraction)."""
        if u not in self.nodes or v not in self.nodes:
            return (pt[0], pt[1]), float("inf"), 0.0

        p1 = self.nodes[u]
        p2 = self.nodes[v]

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        seg_len_sq = dx * dx + dy * dy

        if not math.isfinite(seg_len_sq) or seg_len_sq < 1e-12:
            d = haversine_distance_2d(pt, p1)
            return (p1[0], p1[1]), d, 0.0

        num = (pt[0] - p1[0]) * dx + (pt[1] - p1[1]) * dy
        if not math.isfinite(num):
            d = haversine_distance_2d(pt, p1)
            return (p1[0], p1[1]), d, 0.0

        t = max(0.0, min(1.0, num / seg_len_sq))
        snap_lon = p1[0] + t * dx
        snap_lat = p1[1] + t * dy
        d_m = haversine_distance_2d(pt, (snap_lon, snap_lat))
        return (snap_lon, snap_lat), d_m, t

    def _emission_log_prob(self, dist_m: float) -> float:
        """Log emission probability under Gaussian sensor error model."""
        sigma = max(1e-4, float(self.sigma_z)) if math.isfinite(self.sigma_z) else 4.07
        d = float(dist_m) if math.isfinite(dist_m) and dist_m >= 0 else 100.0
        return -0.5 * ((d / sigma) ** 2) - math.log(math.sqrt(2.0 * math.pi) * sigma)

    def _transition_log_prob(self, great_circle_dist_m: float, network_dist_m: float) -> float:
        """Log transition probability under exponential network difference model."""
        beta = max(1e-4, float(self.beta)) if math.isfinite(self.beta) else 3.0
        d_gc = (
            float(great_circle_dist_m)
            if math.isfinite(great_circle_dist_m) and great_circle_dist_m >= 0
            else 0.0
        )
        d_net = (
            float(network_dist_m) if math.isfinite(network_dist_m) and network_dist_m >= 0 else 0.0
        )
        delta = abs(d_gc - d_net)
        return -(delta / beta) - math.log(beta)

    def match_gps_track(
        self,
        raw_points: Sequence[GPXPoint],
        search_radius_m: float = 35.0,
    ) -> MapMatching3DResult:
        """Execute Viterbi HMM decoding to match noisy GPS track onto topological 3D graph."""
        if not self.nodes:
            return MapMatching3DResult(
                [], [], len(raw_points) if raw_points else 0, 0.0, 0.0, 0.0, "Graph is empty."
            )

        valid_raw = [
            p
            for p in raw_points
            if p and math.isfinite(float(p.lon)) and math.isfinite(float(p.lat))
        ]
        if len(valid_raw) < 2:
            return MapMatching3DResult(
                [],
                [],
                len(raw_points) if raw_points else 0,
                0.0,
                0.0,
                0.0,
                "Insufficient GPS points.",
            )

        s_rad = max(1.0, float(search_radius_m)) if math.isfinite(search_radius_m) else 35.0
        candidates_per_time: List[List[Dict[str, Any]]] = []

        for pt in valid_raw:
            cands = []
            pt_coord = (pt.lon, pt.lat)
            for u in self.nodes:
                for v, length_m, _slope, _meta in self.adj.get(u, []):
                    snap_pt, d_m, frac = self._project_point_to_edge(pt_coord, u, v)
                    if d_m <= s_rad:
                        cands.append(
                            {
                                "u": u,
                                "v": v,
                                "snap_lon": snap_pt[0],
                                "snap_lat": snap_pt[1],
                                "dist_m": d_m,
                                "frac": frac,
                                "edge_len": length_m,
                            }
                        )
            if not cands:
                nearest_node = min(
                    self.nodes, key=lambda n: haversine_distance_2d(pt_coord, self.nodes[n])
                )
                n_coord = self.nodes[nearest_node]
                cands.append(
                    {
                        "u": nearest_node,
                        "v": nearest_node,
                        "snap_lon": n_coord[0],
                        "snap_lat": n_coord[1],
                        "dist_m": haversine_distance_2d(pt_coord, n_coord),
                        "frac": 0.0,
                        "edge_len": 1.0,
                    }
                )
            candidates_per_time.append(cands[:10])

        T = len(valid_raw)
        viterbi_log = [{} for _ in range(T)]
        backpointer = [{} for _ in range(T)]

        for c_idx, cand in enumerate(candidates_per_time[0]):
            viterbi_log[0][c_idx] = self._emission_log_prob(cand["dist_m"])

        for t in range(1, T):
            pt_prev = (valid_raw[t - 1].lon, valid_raw[t - 1].lat)
            pt_curr = (valid_raw[t].lon, valid_raw[t].lat)
            d_gc = haversine_distance_2d(pt_prev, pt_curr)

            for c_curr_idx, c_curr in enumerate(candidates_per_time[t]):
                best_prob = -float("inf")
                best_prev = 0
                e_prob = self._emission_log_prob(c_curr["dist_m"])

                for c_prev_idx, c_prev in enumerate(candidates_per_time[t - 1]):
                    d_net = haversine_distance_2d(
                        (c_prev["snap_lon"], c_prev["snap_lat"]),
                        (c_curr["snap_lon"], c_curr["snap_lat"]),
                    )
                    t_prob = self._transition_log_prob(d_gc, d_net)
                    total_p = viterbi_log[t - 1].get(c_prev_idx, -float("inf")) + t_prob + e_prob

                    if total_p > best_prob:
                        best_prob = total_p
                        best_prev = c_prev_idx

                viterbi_log[t][c_curr_idx] = best_prob
                backpointer[t][c_curr_idx] = best_prev

        if viterbi_log[T - 1]:
            best_last_idx = max(viterbi_log[T - 1], key=viterbi_log[T - 1].get)
        else:
            best_last_idx = 0

        optimal_cands = [candidates_per_time[T - 1][best_last_idx]]
        curr_idx = best_last_idx

        for t in range(T - 1, 0, -1):
            curr_idx = backpointer[t].get(curr_idx, 0)
            optimal_cands.append(candidates_per_time[t - 1][curr_idx])

        optimal_cands.reverse()

        matched_points: List[MatchedTrackPoint3D] = []
        total_residual = 0.0
        total_dist = 0.0
        elevation_gain = 0.0
        prev_z: Optional[float] = None
        node_path: List[int] = []

        for idx, cand in enumerate(optimal_cands):
            lon = cand["snap_lon"]
            lat = cand["snap_lat"]
            grad = self.micro_elevation.sample_micro_gradient(lon, lat)
            z = grad.elevation_m
            residual = cand["dist_m"]
            total_residual += residual

            if prev_z is not None:
                dz = z - prev_z
                if dz > 0:
                    elevation_gain += dz
                seg_d = haversine_distance_2d(
                    (optimal_cands[idx - 1]["snap_lon"], optimal_cands[idx - 1]["snap_lat"]),
                    (lon, lat),
                )
                total_dist += seg_d

            prev_z = z
            node_path.append(cand["u"])

            spd_ms = valid_raw[idx].speed_ms
            speed_val = (
                spd_ms * 3.6
                if spd_ms is not None and math.isfinite(spd_ms) and spd_ms > 0
                else 15.0
            )

            matched_points.append(
                MatchedTrackPoint3D(
                    lon=lon,
                    lat=lat,
                    elevation_m=z,
                    snapped_edge_u=cand["u"],
                    snapped_edge_v=cand["v"],
                    lateral_residual_m=residual,
                    reconstructed_slope_pct=grad.slope_pct,
                    speed_kmh=speed_val,
                )
            )

        mean_err = total_residual / max(1, len(matched_points))
        return MapMatching3DResult(
            matched_points=matched_points,
            matched_nodes_path=node_path,
            total_raw_points=len(raw_points),
            mean_snapping_error_m=mean_err,
            total_matched_distance_m=total_dist,
            elevation_gain_m=elevation_gain,
            status_message=f"Successfully snapped {T} GPS observations with mean residual {mean_err:.1f}m.",
        )

    @staticmethod
    def parse_gpx_string(gpx_xml_content: str) -> List[GPXPoint]:
        """Parse raw GPX string into structured sequence of GPXPoints using safe regex."""
        points: List[GPXPoint] = []
        with contextlib.suppress(Exception):
            pattern = re.compile(
                r"<trkpt\s+[^>]*lat=[\"']([^\"']+)[\"']\s+[^>]*lon=[\"']([^\"']+)[\"'][^>]*>(.*?)</trkpt>",
                re.DOTALL | re.IGNORECASE,
            )
            pattern_reverse = re.compile(
                r"<trkpt\s+[^>]*lon=[\"']([^\"']+)[\"']\s+[^>]*lat=[\"']([^\"']+)[\"'][^>]*>(.*?)</trkpt>",
                re.DOTALL | re.IGNORECASE,
            )
            matches = list(pattern.finditer(gpx_xml_content))
            if not matches:
                matches = list(pattern_reverse.finditer(gpx_xml_content))

            for m in matches:
                lat = float(m.group(1))
                lon = float(m.group(2))
                inner = m.group(3)

                ele = 0.0
                m_ele = re.search(r"<ele>([^<]+)</ele>", inner, re.IGNORECASE)
                if m_ele:
                    ele = float(m_ele.group(1))

                time_iso = ""
                m_time = re.search(r"<time>([^<]+)</time>", inner, re.IGNORECASE)
                if m_time:
                    time_iso = m_time.group(1).strip()

                points.append(
                    GPXPoint(lon=lon, lat=lat, elevation_raw_m=ele, timestamp_iso=time_iso)
                )
        return points
