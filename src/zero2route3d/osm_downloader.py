"""OpenStreetMap road network, building footprint, tree, and park fetcher for 02Route 3D."""

from __future__ import annotations

import contextlib
import http.client
import json
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

USER_AGENT = "02Route3D-QGIS-Plugin/0.1.0 (https://github.com/YusufEminoglu/zero2route3d)"
DEFAULT_TIMEOUT_S = 30


@dataclass
class OsmBuilding:
    """Real OSM building footprint with height and levels."""

    building_id: str
    polygon: List[Tuple[float, float]]  # [(lon, lat), ...]
    height_m: float = 12.0
    levels: int = 4
    building_type: str = "yes"


@dataclass
class OsmRoad:
    """Real OSM road centerline with highway type and name."""

    road_id: str
    geometry: List[Tuple[float, float]]  # [(lon, lat), ...]
    highway_type: str = "residential"
    name: str = ""
    oneway: bool = False
    maxspeed: Optional[float] = None


@dataclass
class OsmTree:
    """Real OSM standalone tree or tree-row point."""

    tree_id: str
    lon: float
    lat: float
    species: str = "tree"
    height_m: float = 8.0
    canopy_radius_m: float = 3.0
    tree_type: str = "deciduous"  # 'deciduous', 'broadleaf', 'conifer', 'pine'


@dataclass
class OsmPark:
    """Real OSM park, garden, wood, or greenery polygon."""

    park_id: str
    polygon: List[Tuple[float, float]]  # [(lon, lat), ...]
    park_type: str = "park"
    name: str = ""


class OsmDataFetcher:
    """Fetches real roads, building footprints, trees, and park greenery from OpenStreetMap Overpass API."""

    @staticmethod
    def fetch_roads_and_buildings(
        bbox: Tuple[float, float, float, float],
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> Tuple[List[OsmRoad], List[OsmBuilding]]:
        """Fetch roads and buildings in bbox: (min_lon, min_lat, max_lon, max_lat)."""
        roads, buildings, _, _ = OsmDataFetcher.fetch_full_urban_environment(
            bbox, timeout_s=timeout_s
        )
        return roads, buildings

    @staticmethod
    def fetch_full_urban_environment(
        bbox: Tuple[float, float, float, float],
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> Tuple[List[OsmRoad], List[OsmBuilding], List[OsmTree], List[OsmPark]]:
        """Fetch roads, buildings, trees, and parks in bbox: (min_lon, min_lat, max_lon, max_lat)."""
        if not bbox or len(bbox) < 4:
            return [], [], [], []

        min_lon, min_lat, max_lon, max_lat = (
            float(bbox[0]),
            float(bbox[1]),
            float(bbox[2]),
            float(bbox[3]),
        )
        if not (
            math.isfinite(min_lon)
            and math.isfinite(min_lat)
            and math.isfinite(max_lon)
            and math.isfinite(max_lat)
        ):
            return [], [], [], []

        if min_lon >= max_lon or min_lat >= max_lat:
            return [], [], [], []

        to_sec = (
            max(1, int(timeout_s))
            if math.isfinite(timeout_s) and timeout_s > 0
            else DEFAULT_TIMEOUT_S
        )

        query = f"""
        [out:json][timeout:{to_sec}];
        (
          way["highway"~"primary|secondary|tertiary|residential|service|footway|cycleway|living_street|pedestrian|path|track|unclassified"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["building"]({min_lat},{min_lon},{max_lat},{max_lon});
          relation["building"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["natural"="tree"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["natural"~"tree_row|wood|scrub|heath"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["leisure"~"park|garden|pitch"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["landuse"~"grass|forest|recreation_ground|village_green|meadow"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out body geom;
        """.strip()

        roads: List[OsmRoad] = []
        buildings: List[OsmBuilding] = []
        trees: List[OsmTree] = []
        parks: List[OsmPark] = []

        with contextlib.suppress(Exception):
            import urllib.parse

            body = urllib.parse.urlencode({"data": query}).encode("utf-8")
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
            }
            conn = http.client.HTTPSConnection("overpass-api.de", timeout=to_sec)
            try:
                conn.request("POST", "/api/interpreter", body=body, headers=headers)
                resp = conn.getresponse()
                if resp.status == 200:
                    raw_bytes = resp.read()
                    data = json.loads(raw_bytes.decode("utf-8"))

                    for elem in data.get("elements", []):
                        tags = elem.get("tags", {})
                        elem_id = str(elem.get("id", ""))
                        elem_type = elem.get("type", "")

                        # 1. Real Road Network
                        if "highway" in tags and elem_type == "way":
                            geom = elem.get("geometry", [])
                            coords = []
                            for pt in geom:
                                try:
                                    lon_val = float(pt["lon"])
                                    lat_val = float(pt["lat"])
                                    if math.isfinite(lon_val) and math.isfinite(lat_val):
                                        coords.append((lon_val, lat_val))
                                except (KeyError, ValueError, TypeError):
                                    continue

                            if len(coords) >= 2:
                                roads.append(
                                    OsmRoad(
                                        road_id=elem_id,
                                        geometry=coords,
                                        highway_type=str(tags.get("highway", "residential")),
                                        name=str(tags.get("name", "")),
                                        oneway=tags.get("oneway") in ("yes", "1", "true"),
                                    )
                                )

                        # 2. Real Buildings
                        elif "building" in tags:
                            geom = elem.get("geometry", [])
                            coords = []
                            for pt in geom:
                                try:
                                    lon_val = float(pt["lon"])
                                    lat_val = float(pt["lat"])
                                    if math.isfinite(lon_val) and math.isfinite(lat_val):
                                        coords.append((lon_val, lat_val))
                                except (KeyError, ValueError, TypeError):
                                    continue

                            if len(coords) >= 3:
                                levels = 4
                                height_m = 12.0
                                if "building:levels" in tags:
                                    with contextlib.suppress(ValueError, TypeError):
                                        levels = max(1, int(float(tags["building:levels"])))
                                        height_m = levels * 3.2
                                elif "height" in tags:
                                    with contextlib.suppress(ValueError, TypeError):
                                        h_str = str(tags["height"]).replace("m", "").strip()
                                        height_m = max(3.0, float(h_str))
                                        levels = max(1, int(height_m / 3.2))

                                buildings.append(
                                    OsmBuilding(
                                        building_id=elem_id,
                                        polygon=coords,
                                        height_m=height_m,
                                        levels=levels,
                                        building_type=str(tags.get("building", "yes")),
                                    )
                                )

                        # 3. Real Standalone Tree Nodes
                        elif tags.get("natural") == "tree" and elem_type == "node":
                            try:
                                t_lon = float(elem.get("lon", tags.get("lon", 0.0)))
                                t_lat = float(elem.get("lat", tags.get("lat", 0.0)))
                            except (ValueError, TypeError):
                                continue

                            if (
                                math.isfinite(t_lon)
                                and math.isfinite(t_lat)
                                and t_lon != 0.0
                                and t_lat != 0.0
                            ):
                                t_species = tags.get(
                                    "species", tags.get("genus", tags.get("taxon", "tree"))
                                )
                                t_leaf = tags.get("leaf_type", "").lower()
                                t_type = (
                                    "conifer"
                                    if (
                                        "needle" in t_leaf
                                        or "conifer" in t_leaf
                                        or "pine" in t_species.lower()
                                    )
                                    else "deciduous"
                                )
                                t_height = 8.0
                                if "height" in tags:
                                    with contextlib.suppress(ValueError, TypeError):
                                        t_height = max(
                                            3.0,
                                            min(
                                                35.0,
                                                float(str(tags["height"]).replace("m", "").strip()),
                                            ),
                                        )
                                t_radius = max(1.5, min(8.0, t_height * 0.38))
                                if "diameter_crown" in tags:
                                    with contextlib.suppress(ValueError, TypeError):
                                        t_radius = max(
                                            1.5,
                                            min(
                                                10.0,
                                                float(
                                                    str(tags["diameter_crown"])
                                                    .replace("m", "")
                                                    .strip()
                                                )
                                                * 0.5,
                                            ),
                                        )

                                trees.append(
                                    OsmTree(
                                        tree_id=elem_id,
                                        lon=t_lon,
                                        lat=t_lat,
                                        species=str(t_species),
                                        height_m=t_height,
                                        canopy_radius_m=t_radius,
                                        tree_type=t_type,
                                    )
                                )

                        # 4. Real Tree Rows
                        elif tags.get("natural") == "tree_row" and elem_type == "way":
                            geom = elem.get("geometry", [])
                            for idx, pt in enumerate(geom):
                                with contextlib.suppress(Exception):
                                    t_lon = float(pt["lon"])
                                    t_lat = float(pt["lat"])
                                    if math.isfinite(t_lon) and math.isfinite(t_lat):
                                        trees.append(
                                            OsmTree(
                                                tree_id=f"{elem_id}_{idx}",
                                                lon=t_lon,
                                                lat=t_lat,
                                                species="tree_row",
                                                height_m=7.5,
                                                canopy_radius_m=2.6,
                                                tree_type="deciduous",
                                            )
                                        )

                        # 5. Real Parks, Gardens, Grass and Greenery Polygons
                        elif (
                            "leisure" in tags
                            or "landuse" in tags
                            or tags.get("natural") in ("wood", "scrub", "heath")
                        ) and elem_type == "way":
                            geom = elem.get("geometry", [])
                            coords = []
                            for pt in geom:
                                try:
                                    lon_val = float(pt["lon"])
                                    lat_val = float(pt["lat"])
                                    if math.isfinite(lon_val) and math.isfinite(lat_val):
                                        coords.append((lon_val, lat_val))
                                except (KeyError, ValueError, TypeError):
                                    continue

                            if len(coords) >= 3:
                                p_type = str(
                                    tags.get(
                                        "leisure", tags.get("landuse", tags.get("natural", "park"))
                                    )
                                )
                                p_name = str(tags.get("name", ""))
                                parks.append(
                                    OsmPark(
                                        park_id=elem_id,
                                        polygon=coords,
                                        park_type=p_type,
                                        name=p_name,
                                    )
                                )
            finally:
                conn.close()

        return roads, buildings, trees, parks
