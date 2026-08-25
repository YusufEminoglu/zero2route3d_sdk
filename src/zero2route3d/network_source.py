"""Road network data acquisition, vector layer ingestion, and geocoding engine.

Supports fetching OpenStreetMap networks via Overpass API with local bounding
box caching, reverse geocoding via Photon API, and extracting topology from
active QGIS vector layers.
"""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import json
import math
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .input_validation import normalize_bbox
from .kinematics import haversine_distance_2d


@dataclass
class RoadSegment:
    """Directed edge segment representing a traversable line between two vertices."""

    p1: Tuple[float, float, float]
    p2: Tuple[float, float, float]
    length_m: float
    highway_type: str = "residential"
    hierarchy_rank: int = (
        4  # 1: Motorway, 2: Primary, 3: Secondary/Tertiary, 4: Residential, 5: Path/Service
    )
    lanes: int = 2
    is_steps: bool = False
    surface: str = "asphalt"
    is_oneway: bool = False
    # Real OSM "name" tag. Left empty when the way is unnamed -- an unnamed street
    # must stay unnamed rather than be given a placeholder like "Urban Path".
    name: str = ""


class NetworkSourceError(RuntimeError):
    """Raised when no usable real network can be loaded for an operation."""


class NetworkSourceManager:
    """Acquires, caches, geocodes, and parses topological road networks."""

    CACHE_DIR = Path(tempfile.gettempdir()) / "zero2route3d_cache"

    def __init__(self) -> None:
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _highway_to_hierarchy(highway: str) -> int:
        """Map OSM highway tag to functional hierarchy rank (1..5)."""
        h = str(highway).lower()
        if h in {"motorway", "motorway_link", "trunk", "trunk_link"}:
            return 1
        if h in {"primary", "primary_link"}:
            return 2
        if h in {"secondary", "secondary_link", "tertiary", "tertiary_link"}:
            return 3
        if h in {"residential", "living_street", "unclassified"}:
            return 4
        return 5

    def search_place_photon(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Geocode place name using Photon API (HTTPS)."""
        if not query or len(query.strip()) < 2:
            return []

        results = []
        with contextlib.suppress(Exception):
            encoded = urllib.parse.quote(query.strip())
            try:
                lim = max(1, min(50, int(limit)))
            except (TypeError, ValueError, OverflowError):
                lim = 5
            conn = http.client.HTTPSConnection("photon.komoot.io", timeout=8)
            try:
                conn.request(
                    "GET",
                    f"/api/?q={encoded}&limit={lim}",
                    headers={"User-Agent": "zero2route3d-sdk"},
                )
                resp = conn.getresponse()
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if isinstance(data, dict):
                        for feat in data.get("features", []):
                            geom = feat.get("geometry", {})
                            props = feat.get("properties", {})
                            coords = geom.get("coordinates", [])
                            if len(coords) >= 2:
                                try:
                                    lon_val = float(coords[0])
                                    lat_val = float(coords[1])
                                    if math.isfinite(lon_val) and math.isfinite(lat_val):
                                        name = props.get("name") or props.get("street") or query
                                        city = (
                                            props.get("city")
                                            or props.get("state")
                                            or props.get("country")
                                            or ""
                                        )
                                        label = f"{name} ({city})" if city else name
                                        results.append(
                                            {
                                                "label": str(label),
                                                "lon": lon_val,
                                                "lat": lat_val,
                                            }
                                        )
                                except (ValueError, TypeError):
                                    continue
            finally:
                conn.close()
        return results

    def fetch_osm_network_bbox(
        self,
        bbox: Tuple[float, float, float, float],
        buffer_ratio: float = 0.15,
    ) -> List[RoadSegment]:
        """Fetch OSM highway ways within bbox using Overpass API with disk caching.

        A missing/invalid response is an input error, not a reason to invent a
        network.  Callers can surface :class:`NetworkSourceError` directly to
        QGIS users and let them choose a valid layer or retry the download.
        """
        try:
            min_lon, min_lat, max_lon, max_lat = normalize_bbox(bbox)
        except ValueError as exc:
            raise NetworkSourceError(str(exc)) from exc

        d_lon = max(0.005, max_lon - min_lon)
        d_lat = max(0.005, max_lat - min_lat)

        buf_r = float(buffer_ratio) if math.isfinite(buffer_ratio) and buffer_ratio >= 0 else 0.15
        buf_r = min(1.0, buf_r)
        buf_lon = d_lon * buf_r
        buf_lat = d_lat * buf_r
        s = max(-90.0, min_lat - buf_lat)
        w = max(-180.0, min_lon - buf_lon)
        n = min(90.0, max_lat + buf_lat)
        e = min(180.0, max_lon + buf_lon)

        cache_key = hashlib.sha256(f"{s:.4f}_{w:.4f}_{n:.4f}_{e:.4f}".encode("utf-8")).hexdigest()
        cache_file = self.CACHE_DIR / f"osm_{cache_key}.json"

        data = None
        if cache_file.exists():
            with contextlib.suppress(Exception):
                with open(cache_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict) and "elements" in loaded:
                        data = loaded

        if not data:
            query = f"""[out:json][timeout:25];(way["highway"]({s:.5f},{w:.5f},{n:.5f},{e:.5f}););out body;>;out skel qt;"""
            data = self._query_overpass(query)
            if data and isinstance(data, dict) and "elements" in data:
                with contextlib.suppress(Exception):
                    temp_cache = cache_file.with_suffix(".tmp")
                    with open(temp_cache, "w", encoding="utf-8") as f:
                        json.dump(data, f)
                    temp_cache.replace(cache_file)

        if not data or not isinstance(data, dict) or "elements" not in data:
            raise NetworkSourceError(
                "OpenStreetMap network download failed. Check the internet connection "
                "or select a QGIS line network layer."
            )

        segments = self._parse_osm_json(data)
        if not segments:
            raise NetworkSourceError(
                "OpenStreetMap returned no usable road segments for this extent. "
                "Try a larger extent or select a QGIS line network layer."
            )
        return segments

    def require_segments(
        self,
        vector_layer: Any = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> List[RoadSegment]:
        """Load a real network from a QGIS line layer or OSM, never fabricated data."""
        if vector_layer is not None:
            segments = self.extract_from_qgis_layer(vector_layer)
            if not segments:
                raise NetworkSourceError(
                    "The selected network layer contains no usable line segments. "
                    "Select a non-empty line layer with a valid CRS."
                )
            return segments
        if bbox is None:
            raise NetworkSourceError(
                "No network source was provided. Select a QGIS line layer or enable OSM download."
            )
        return self.fetch_osm_network_bbox(bbox)

    def extract_from_geojson(self, data: Any) -> List[RoadSegment]:
        """Extract road segments from GeoJSON, the SDK's primary network input.

        Accepts a FeatureCollection, a single Feature, a bare geometry, or a list
        of any of those. LineString and MultiLineString geometries are split into
        directed vertex-to-vertex segments; Z coordinates are carried through when
        present. Non-line geometries are skipped.

        OSM-style properties are honoured where available: ``highway``, ``surface``,
        ``oneway`` (including ``-1``/``reverse``), ``junction=roundabout``, ``lanes``
        and ``name``.
        """
        features = self._iter_geojson_features(data)
        segments: List[RoadSegment] = []

        for geometry, properties in features:
            geom_type = str(geometry.get("type", ""))
            if geom_type == "LineString":
                lines = [geometry.get("coordinates") or []]
            elif geom_type == "MultiLineString":
                lines = list(geometry.get("coordinates") or [])
            else:
                continue

            highway = str(properties.get("highway", "residential") or "residential").strip()
            hierarchy = self._highway_to_hierarchy(highway)
            is_steps = highway == "steps"
            surface = str(properties.get("surface", "asphalt") or "asphalt").strip()
            lanes = 1
            with contextlib.suppress(Exception):
                lanes = max(1, int(properties.get("lanes", 1)))

            oneway_raw = properties.get("oneway", False)
            oneway_tag = str(oneway_raw).strip().lower()
            # oneway=-1 means one-way *against* the digitisation order; storing it
            # unreversed routes traffic the wrong way down the street.
            reversed_oneway = oneway_tag in {"-1", "reverse"}
            oneway = (
                oneway_raw is True
                or oneway_tag in {"yes", "1", "true"}
                or reversed_oneway
                or str(properties.get("junction", "") or "").strip().lower() == "roundabout"
            )
            street_name = str(properties.get("name", "") or "").strip()

            for line in lines:
                vertices = self._clean_line_coordinates(line)
                for c1, c2 in zip(vertices, vertices[1:]):
                    dist = haversine_distance_2d(c1, c2)
                    if not math.isfinite(dist) or dist < 0.1:
                        continue
                    p1, p2 = (c2, c1) if reversed_oneway else (c1, c2)
                    segments.append(
                        RoadSegment(
                            p1=p1,
                            p2=p2,
                            length_m=dist,
                            highway_type=highway,
                            hierarchy_rank=hierarchy,
                            lanes=lanes,
                            is_steps=is_steps,
                            surface=surface,
                            is_oneway=oneway,
                            name=street_name,
                        )
                    )

        return segments

    @classmethod
    def _iter_geojson_features(cls, data: Any) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Flatten any GeoJSON container into (geometry, properties) pairs."""
        pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

        if isinstance(data, (list, tuple)):
            for item in data:
                pairs.extend(cls._iter_geojson_features(item))
            return pairs

        if not isinstance(data, dict):
            return pairs

        node_type = str(data.get("type", ""))
        if node_type == "FeatureCollection":
            for feature in data.get("features") or []:
                pairs.extend(cls._iter_geojson_features(feature))
        elif node_type == "Feature":
            geometry = data.get("geometry")
            properties = data.get("properties") or {}
            if isinstance(geometry, dict):
                if str(geometry.get("type", "")) == "GeometryCollection":
                    for sub in geometry.get("geometries") or []:
                        if isinstance(sub, dict):
                            pairs.append((sub, properties))
                else:
                    pairs.append((geometry, properties))
        elif node_type == "GeometryCollection":
            for sub in data.get("geometries") or []:
                if isinstance(sub, dict):
                    pairs.append((sub, {}))
        elif node_type:
            pairs.append((data, {}))

        return pairs

    @staticmethod
    def _clean_line_coordinates(line: Any) -> List[Tuple[float, float, float]]:
        """Coerce a GeoJSON coordinate array into finite (lon, lat, z) tuples."""
        vertices: List[Tuple[float, float, float]] = []
        if not isinstance(line, (list, tuple)):
            return vertices
        for pt in line:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                continue
            try:
                lon = float(pt[0])
                lat = float(pt[1])
                z = float(pt[2]) if len(pt) > 2 else 0.0
            except (TypeError, ValueError, OverflowError):
                continue
            if not (math.isfinite(lon) and math.isfinite(lat)):
                continue
            vertices.append((lon, lat, z if math.isfinite(z) else 0.0))
        return vertices

    def _query_overpass(self, query: str) -> Dict[str, Any] | None:
        """Safe HTTPS POST to Overpass API without generic urlopen."""
        endpoints = [
            ("overpass-api.de", "/api/interpreter"),
            ("maps.mail.ru", "/osm/tools/overpass/api/interpreter"),
        ]
        body = urllib.parse.urlencode({"data": query}).encode("utf-8")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "zero2route3d-sdk",
        }

        for host, path in endpoints:
            with contextlib.suppress(Exception):
                conn = http.client.HTTPSConnection(host, timeout=12)
                try:
                    conn.request("POST", path, body=body, headers=headers)
                    resp = conn.getresponse()
                    if resp.status == 200:
                        raw = resp.read().decode("utf-8")
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            return parsed
                finally:
                    conn.close()
        return None

    def _parse_osm_json(self, data: Dict[str, Any]) -> List[RoadSegment]:
        """Convert OSM JSON response elements into list of RoadSegments."""
        nodes: Dict[int, Tuple[float, float]] = {}
        segments: List[RoadSegment] = []

        for el in data.get("elements", []):
            if el.get("type") == "node":
                try:
                    nid = int(el["id"])
                    nlon = float(el["lon"])
                    nlat = float(el["lat"])
                    if math.isfinite(nlon) and math.isfinite(nlat):
                        nodes[nid] = (nlon, nlat)
                except (KeyError, ValueError, TypeError):
                    continue

        for el in data.get("elements", []):
            if el.get("type") == "way":
                tags = el.get("tags") or {}
                highway = str(tags.get("highway", "residential"))
                hierarchy = self._highway_to_hierarchy(highway)
                is_steps = highway == "steps"
                surface = str(tags.get("surface", "asphalt"))
                lanes = 1
                with contextlib.suppress(Exception):
                    lanes = max(1, int(tags.get("lanes", 1)))
                oneway_tag = str(tags.get("oneway", "")).strip().lower()
                # oneway=-1 means the way is one-way *against* its digitisation order.
                # Treating it as bidirectional routed vehicles the wrong way down it.
                reversed_oneway = oneway_tag in {"-1", "reverse"}
                oneway = (
                    oneway_tag in {"yes", "1", "true"}
                    or reversed_oneway
                    or str(tags.get("junction", "")).strip().lower() == "roundabout"
                )
                street_name = str(tags.get("name", "") or "").strip()

                way_nodes = el.get("nodes") or []
                for i in range(len(way_nodes) - 1):
                    n1 = way_nodes[i]
                    n2 = way_nodes[i + 1]
                    if n1 in nodes and n2 in nodes:
                        c1 = nodes[n1]
                        c2 = nodes[n2]
                        dist = haversine_distance_2d(c1, c2)
                        if dist >= 0.1 and math.isfinite(dist):
                            seg = RoadSegment(
                                p1=(c1[0], c1[1], 0.0),
                                p2=(c2[0], c2[1], 0.0),
                                length_m=dist,
                                highway_type=highway,
                                hierarchy_rank=hierarchy,
                                lanes=lanes,
                                is_steps=is_steps,
                                surface=surface,
                                is_oneway=oneway,
                                name=street_name,
                            )
                            if reversed_oneway:
                                # Store it in its true travel direction.
                                seg.p1, seg.p2 = seg.p2, seg.p1
                            segments.append(seg)
        return segments

    def extract_from_qgis_layer(self, vector_layer: Any) -> List[RoadSegment]:
        """Extract road network edges from an active QGIS line vector layer."""
        if vector_layer is None:
            return []
        segments: List[RoadSegment] = []

        def point_coordinate(point: Any, name: str, default: float = 0.0) -> float:
            """Read QgsPoint or QgsPointXY coordinates across QGIS versions."""
            value = getattr(point, name, None)
            if callable(value):
                value = value()
            try:
                return float(value) if value is not None else default
            except (TypeError, ValueError):
                return default

        with contextlib.suppress(Exception):
            from qgis.core import (
                QgsCoordinateReferenceSystem,
                QgsCoordinateTransform,
                QgsProject,
            )

            crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            crs_layer = vector_layer.crs()
            needs_transform = crs_layer != crs_wgs84
            transform = (
                QgsCoordinateTransform(crs_layer, crs_wgs84, QgsProject.instance())
                if needs_transform
                else None
            )

            for feat in vector_layer.getFeatures():
                geom = feat.geometry()
                if geom.isNull() or geom.isEmpty():
                    continue

                if needs_transform and transform is not None:
                    geom.transform(transform)

                lines = []
                if geom.isMultipart():
                    lines = geom.asMultiPolyline()
                else:
                    lines = [geom.asPolyline()]

                fields = feat.fields().names()
                highway = "residential"
                for h_field in ["highway", "type", "road_type", "class", "KIND"]:
                    if h_field in fields and feat[h_field] is not None:
                        highway = str(feat[h_field])
                        break

                hierarchy = self._highway_to_hierarchy(highway)
                is_steps = "step" in highway.lower() or "merdiven" in highway.lower()

                for line in lines:
                    for i in range(len(line) - 1):
                        p1 = line[i]
                        p2 = line[i + 1]
                        c1 = (
                            point_coordinate(p1, "x"),
                            point_coordinate(p1, "y"),
                            point_coordinate(p1, "z"),
                        )
                        c2 = (
                            point_coordinate(p2, "x"),
                            point_coordinate(p2, "y"),
                            point_coordinate(p2, "z"),
                        )
                        if not (
                            math.isfinite(c1[0])
                            and math.isfinite(c1[1])
                            and math.isfinite(c2[0])
                            and math.isfinite(c2[1])
                        ):
                            continue
                        dist = haversine_distance_2d(c1, c2)
                        if dist >= 0.1 and math.isfinite(dist):
                            segments.append(
                                RoadSegment(
                                    p1=c1,
                                    p2=c2,
                                    length_m=dist,
                                    highway_type=highway,
                                    hierarchy_rank=hierarchy,
                                    is_steps=is_steps,
                                )
                            )
        return segments
