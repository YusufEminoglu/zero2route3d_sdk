"""Regression and coverage tests for the low-coverage modules.

Network access is always mocked; QGIS-only code paths run against a tiny fake
``qgis.core`` module so their pure arithmetic can be checked headless.
"""

from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple
from unittest import mock

import numpy as np
import pytest

from zero2route3d.kinematics import haversine_distance_2d
from zero2route3d.network_source import NetworkSourceError, NetworkSourceManager, RoadSegment
from zero2route3d.routing_engine import RoutingEngine3D, Waypoint


def _seg(a: Tuple[float, float, float], b: Tuple[float, float, float], highway: str) -> RoadSegment:
    """Build a RoadSegment with the hierarchy rank the OSM parser would assign."""
    return RoadSegment(
        p1=a,
        p2=b,
        length_m=haversine_distance_2d(a, b),
        highway_type=highway,
        hierarchy_rank=NetworkSourceManager._highway_to_hierarchy(highway),
    )


class _FakeResponse:
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self._body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body


class _FakeConnection:
    """Stand-in for http.client.HTTPSConnection that records requests."""

    responses: List[_FakeResponse] = []
    requests: List[Tuple[str, str, str]] = []
    closed = 0

    def __init__(self, host: str, timeout: float = 0) -> None:
        self.host = host

    def request(self, method: str, path: str, body: Any = None, headers: Any = None) -> None:
        _FakeConnection.requests.append((self.host, method, path))

    def getresponse(self) -> _FakeResponse:
        return _FakeConnection.responses.pop(0)

    def close(self) -> None:
        _FakeConnection.closed += 1


@pytest.fixture
def fake_http() -> Any:
    _FakeConnection.responses = []
    _FakeConnection.requests = []
    _FakeConnection.closed = 0
    with mock.patch("http.client.HTTPSConnection", _FakeConnection):
        yield _FakeConnection


# ---------------------------------------------------------------------------
# routing_engine: A* heuristic must stay admissible
# ---------------------------------------------------------------------------


def test_astar_finds_cheaper_motorway_detour_for_car() -> None:
    a, b, c = (29.0, 41.0, 0.0), (29.01, 41.0, 0.0), (29.005, 41.008, 0.0)
    engine = RoutingEngine3D()
    engine.build_graph([_seg(a, b, "residential"), _seg(a, c, "motorway"), _seg(c, b, "motorway")])

    from zero2route3d.mobility_profiles import PROFILES

    coords, ok = engine.compute_segment_route((29.0, 41.0), (29.01, 41.0), PROFILES["car"])

    # The motorway detour is longer but cheaper for a car; the plain great-circle
    # heuristic overestimated it and A* settled on the direct residential street.
    car = PROFILES["car"]
    direct = car.calculate_edge_resistance(haversine_distance_2d(a, b), 0.0, hierarchy_rank=4)
    detour = 2 * car.calculate_edge_resistance(haversine_distance_2d(a, c), 0.0, hierarchy_rank=1)
    assert detour < direct
    assert ok
    assert (29.005, 41.008, 0.0) in coords


# ---------------------------------------------------------------------------
# dem_fetcher / environmental_raster: NumPy coordinate arrays
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_dem_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    from zero2route3d.dem_fetcher import GlobalDemFetcher

    monkeypatch.setattr(GlobalDemFetcher, "_CACHE_FILE", tmp_path / "elevation_cache.json")
    monkeypatch.setattr(GlobalDemFetcher, "_MEMORY_CACHE", {})
    monkeypatch.setattr(GlobalDemFetcher, "_DISK_CACHE_LOADED", False)
    return GlobalDemFetcher


def test_dem_fetcher_accepts_numpy_coordinate_array(isolated_dem_cache: Any) -> None:
    fetcher = isolated_dem_cache
    fetcher.seed_cache({(29.0, 41.0): 100.0})
    values = fetcher.fetch_elevations_for_coords(np.array([[29.0, 41.0]]))
    assert values == [100.0]


def test_prefetch_elevations_accepts_numpy_coordinate_array() -> None:
    from zero2route3d.environmental_raster import EnvironmentalSurfaceSampler

    sampler = EnvironmentalSurfaceSampler()
    with mock.patch(
        "zero2route3d.dem_fetcher.GlobalDemFetcher.fetch_elevations_for_coords",
        return_value=[5.0],
    ):
        assert sampler.prefetch_elevations(np.array([[29.0, 41.0]])) == 1
    assert sampler.sample_elevation(29.0, 41.0) == 5.0


def test_dem_fetcher_network_batch_and_disk_cache(isolated_dem_cache: Any, fake_http: Any) -> None:
    fetcher = isolated_dem_cache
    fake_http.responses = [
        _FakeResponse(200, {"results": [{"elevation": 12.5}, {"elevation": 0.0}]})
    ]
    values = fetcher.fetch_elevations_for_coords([(29.0, 41.0), (29.1, 41.1), (float("nan"), 1)])
    assert values == [12.5, 0.0, None]
    assert fake_http.requests == [("api.open-elevation.com", "POST", "/api/v1/lookup")]
    assert fake_http.closed == 1
    assert json.loads(fetcher._CACHE_FILE.read_text(encoding="utf-8"))["29.00000,41.00000"] == 12.5

    # A fresh process reloads from disk and never touches the network.
    fetcher.clear_cache()
    assert fetcher.get_fast_elevation(29.0, 41.0) == 12.5
    assert fetcher.get_elevation_single(29.1, 41.1) == 0.0
    assert fetcher.cached_sample_count() == 2


def test_dem_fetcher_rejects_mismatched_or_invalid_response(
    isolated_dem_cache: Any, fake_http: Any
) -> None:
    fetcher = isolated_dem_cache
    fake_http.responses = [
        _FakeResponse(200, {"results": [{"elevation": 1.0}]}),  # wrong length
        _FakeResponse(200, {"results": [{"elevation": "nan"}]}),
        _FakeResponse(503, b"busy"),
    ]
    coords = [(29.0, 41.0), (29.1, 41.1)]
    assert fetcher.fetch_elevations_for_coords(coords) == [None, None]
    assert fetcher.fetch_elevations_for_coords([(30.0, 40.0)]) == [None]
    assert fetcher.get_elevation_single(31.0, 40.0) is None
    assert not fetcher._CACHE_FILE.exists()


# ---------------------------------------------------------------------------
# qml_generator
# ---------------------------------------------------------------------------


def test_qml_honours_line_color_hex() -> None:
    from zero2route3d.qml_generator import generate_route_qml_style

    qml = generate_route_qml_style(line_color_hex="#ff0000")
    assert 'value="255,0,0,255"' in qml
    assert 'value="255,0,0,90"' in qml
    # A named profile still selects its palette colour; invalid hex falls back.
    assert "245,158,11,255" in generate_route_qml_style("child", line_color_hex="#ff0000")
    assert "14,165,233,255" in generate_route_qml_style(line_color_hex="not-a-colour")
    assert "1,2,3,4" in generate_route_qml_style(line_color_hex="#01020304")


def test_qml_uppercase_extension_is_written(tmp_path: Path) -> None:
    from zero2route3d.qml_generator import generate_route_qml_style

    target = tmp_path / "nested" / "Route.QML"
    qml = generate_route_qml_style(str(target), line_width_mm=2.0)
    assert target.read_text(encoding="utf-8") == qml
    assert 'name="line_width" value="4.0"' in qml


# ---------------------------------------------------------------------------
# micro_elevation (QGIS path, run against a fake qgis.core)
# ---------------------------------------------------------------------------


def _install_fake_qgis(monkeypatch: pytest.MonkeyPatch) -> None:
    class QgsPointXY:
        def __init__(self, x: float, y: float) -> None:
            self._x, self._y = float(x), float(y)

        def x(self) -> float:
            return self._x

        def y(self) -> float:
            return self._y

    class QgsCoordinateReferenceSystem:
        def __init__(self, auth: str) -> None:
            self.auth = auth

        def __eq__(self, other: object) -> bool:
            return isinstance(other, QgsCoordinateReferenceSystem) and other.auth == self.auth

        def __ne__(self, other: object) -> bool:
            return not self.__eq__(other)

        def isGeographic(self) -> bool:  # noqa: N802
            return self.auth == "EPSG:4326"

    core = types.ModuleType("qgis.core")
    core.QgsPointXY = QgsPointXY  # type: ignore[attr-defined]
    core.QgsCoordinateReferenceSystem = QgsCoordinateReferenceSystem  # type: ignore[attr-defined]
    core.QgsCoordinateTransform = None  # type: ignore[attr-defined]
    core.QgsProject = None  # type: ignore[attr-defined]
    qgis = types.ModuleType("qgis")
    qgis.core = core  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "qgis", qgis)
    monkeypatch.setitem(sys.modules, "qgis.core", core)


class _FakeRasterLayer:
    """Unit-square EPSG:4326 raster, 0.01 degree pixels, value = fn(pixel centre)."""

    def __init__(self, fn: Callable[[float, float], float]) -> None:
        self.fn = fn

    def crs(self) -> Any:
        return sys.modules["qgis.core"].QgsCoordinateReferenceSystem("EPSG:4326")

    def dataProvider(self) -> Any:  # noqa: N802
        layer = self

        class Provider:
            def sample(self, pt: Any, band: int) -> Tuple[float, bool]:
                return layer.fn(pt.x(), pt.y()), True

        return Provider()

    def extent(self) -> Any:
        class Extent:
            def contains(self, pt: Any) -> bool:
                return 0.0 <= pt.x() <= 1.0 and 0.0 <= pt.y() <= 1.0

            def xMinimum(self) -> float:  # noqa: N802
                return 0.0

            def yMaximum(self) -> float:  # noqa: N802
                return 1.0

        return Extent()

    def rasterUnitsPerPixelX(self) -> float:  # noqa: N802
        return 0.01

    def rasterUnitsPerPixelY(self) -> float:  # noqa: N802
        return 0.01


def test_micro_elevation_interpolates_at_pixel_centres(monkeypatch: pytest.MonkeyPatch) -> None:
    from zero2route3d.micro_elevation import MicroElevationEngine

    _install_fake_qgis(monkeypatch)
    # A plane rising 1000 m per degree eastwards: bicubic must reproduce it exactly.
    east = MicroElevationEngine(_FakeRasterLayer(lambda x, y: x * 1000.0))
    assert east.sample_micro_gradient(0.505, 0.5).elevation_m == pytest.approx(505.0)
    grad = east.sample_micro_gradient(0.5137, 0.5)
    assert grad.elevation_m == pytest.approx(513.7)
    assert grad.aspect_degrees == pytest.approx(270.0)  # rises east, faces west

    north = MicroElevationEngine(_FakeRasterLayer(lambda x, y: y * 1000.0))
    grad = north.sample_micro_gradient(0.5, 0.5137)
    assert grad.elevation_m == pytest.approx(513.7)
    assert grad.aspect_degrees == pytest.approx(180.0, abs=1e-6)
    assert grad.slope_pct == pytest.approx(100000.0 / 111320.0)

    profile = north.reconstruct_3d_profile([(0.5, 0.5), (0.5, 0.5005)], 10.0)
    assert profile[0][2] == pytest.approx(500.0)
    assert profile[-1][2] == pytest.approx(500.5)


def test_micro_elevation_without_dem_and_idw() -> None:
    from zero2route3d.micro_elevation import IDWSurfaceInterpolator, MicroElevationEngine

    flat = MicroElevationEngine().sample_micro_gradient(29.0, 41.0)
    assert (flat.elevation_m, flat.slope_pct) == (0.0, 0.0)

    idw = IDWSurfaceInterpolator()
    pts = [(0.0, 0.0, 10.0), (2.0, 0.0, 30.0)]
    assert idw.interpolate_point(1.0, 0.0, pts) == pytest.approx(20.0)
    assert idw.interpolate_point(0.0, 0.0, pts) == 10.0
    assert idw.interpolate_point(5.0, 0.0, pts, max_search_radius=0.5) == 30.0
    assert idw.interpolate_point(5.0, 0.0, []) == 0.0


# ---------------------------------------------------------------------------
# raster_source: out-of-coverage samples
# ---------------------------------------------------------------------------


def test_geotiff_without_nodata_returns_none_outside_grid(tmp_path: Path) -> None:
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    from zero2route3d.environmental_raster import EnvironmentalSurfaceSampler
    from zero2route3d.raster_source import GeoTiffRasterSource

    def write(path: Path, west: float, value: float) -> None:
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=10,
            height=10,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(west, 41.0, 0.01, 0.01),
        ) as dataset:  # deliberately no NoData value
            dataset.write(np.full((10, 10), value, dtype="float32"), 1)

    first, second = tmp_path / "a.tif", tmp_path / "b.tif"
    write(first, 29.0, 123.0)
    write(second, 29.1, 456.0)

    with GeoTiffRasterSource(first) as source:
        assert source.sample(29.05, 40.95) == 123.0
        assert source.sample_many([(30.5, 40.95), (29.05, 45.0), (29.05, 40.95)]) == [
            None,
            None,
            123.0,
        ]

    # Outside the first DEM the sampler must fall through to the second one
    # instead of accepting rasterio's 0 fill value as sea level.
    sampler = EnvironmentalSurfaceSampler(dem_layers=[str(first), str(second)])
    assert sampler.sample_elevation(29.15, 40.95) == 456.0


# ---------------------------------------------------------------------------
# profile_dxf
# ---------------------------------------------------------------------------


def test_dxf_export_accepts_numpy_coordinates(tmp_path: Path) -> None:
    from zero2route3d.profile_dxf import export_route_to_dxf_3d

    target = tmp_path / "route.dxf"
    export_route_to_dxf_3d(np.array([[29.0, 41.0, 10.0], [29.001, 41.0, 12.0]]), target)
    text = target.read_text(encoding="utf-8")
    assert text.count("VERTEX") == 4  # 2 route + 2 profile vertices
    assert "30\n12.00\n" in text
    assert text.rstrip().endswith("EOF")


def test_dxf_export_empty_and_without_profile(tmp_path: Path) -> None:
    from zero2route3d.profile_dxf import export_route_to_dxf_3d

    empty = tmp_path / "empty.dxf"
    export_route_to_dxf_3d([], empty)
    assert "ENTITIES" in empty.read_text(encoding="utf-8")

    plain = tmp_path / "plain.dxf"
    export_route_to_dxf_3d(
        [(29.0, 41.0), (29.001, 41.0, float("nan"))], plain, include_profile_section=False
    )
    text = plain.read_text(encoding="utf-8")
    assert text.count("VERTEX") == 2
    assert "PROFILE_GRID\n66" not in text


# ---------------------------------------------------------------------------
# route_corridor_3d
# ---------------------------------------------------------------------------


def test_corridor_base_elevation_interpolated_at_closest_point() -> None:
    from zero2route3d.route_corridor_3d import (
        get_closest_multi_route_elevation,
        get_closest_route_elevation,
    )

    route = [(29.0, 41.0, 0.0), (29.01, 41.0, 100.0)]
    assert get_closest_route_elevation(29.0, 41.0001, route) == pytest.approx(0.0)
    assert get_closest_route_elevation(29.009, 41.0001, route) == pytest.approx(90.0)
    assert get_closest_multi_route_elevation(29.0025, 41.0001, [route]) == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# evacuation
# ---------------------------------------------------------------------------


def test_evacuation_detects_hazard_between_route_vertices() -> None:
    from zero2route3d.evacuation import EvacuationRouter, EvacuationRoutingError

    a, b = (29.0, 41.0, 0.0), (29.02, 41.0, 0.0)
    engine = RoutingEngine3D()
    engine.build_graph([_seg(a, b, "residential")])
    router = EvacuationRouter(engine)
    router.add_hazard_zone(29.01, 41.0, 200.0)

    plan = router.calculate_evacuation_route(Waypoint(29.0, 41.0), [Waypoint(29.02, 41.0)])
    assert len(plan.route_result.coordinates_3d) == 2  # a single long edge
    assert plan.hazard_clearance_dist_m < 1.0
    assert plan.risk_score > 0.0
    assert plan.to_dict()["risk_score"] > 0.0

    with pytest.raises(EvacuationRoutingError):
        router.calculate_evacuation_route(Waypoint(29.0, 41.0), [])
    with pytest.raises(EvacuationRoutingError):
        router.add_hazard_zone(29.0, 41.0, 0.0)
    with pytest.raises(EvacuationRoutingError):
        router.add_hazard_zone(float("nan"), 41.0, 10.0)
    with pytest.raises(EvacuationRoutingError):
        router.calculate_evacuation_route(Waypoint(29.0, 41.0), [Waypoint(10.0, 10.0)])


# ---------------------------------------------------------------------------
# emergency_air_ambulance_landing
# ---------------------------------------------------------------------------


def test_helicopter_headings_are_compass_bearings() -> None:
    from zero2route3d.emergency_air_ambulance_landing import evaluate_helicopter_landing_zones

    all_headings = {i * 45.0 for i in range(8)}
    north = evaluate_helicopter_landing_zones((0.0, 0.0, 0.0), [(0.0, 200.0, 100.0)])
    assert all_headings - set(north.safe_approach_headings) == {0.0}
    east = evaluate_helicopter_landing_zones((0.0, 0.0, 0.0), [(200.0, 0.0, 100.0)])
    assert all_headings - set(east.safe_approach_headings) == {90.0}
    assert east.critical_obstacles_count == 1
    assert not east.is_safe_for_landing


def test_helicopter_obstacle_in_tlof_counted_once() -> None:
    from zero2route3d.emergency_air_ambulance_landing import evaluate_helicopter_landing_zones

    res = evaluate_helicopter_landing_zones(
        (0.0, 0.0, 0.0), [(5.0, 5.0, 10.0), (900.0, 0.0, 500.0)]
    )
    assert res.critical_obstacles_count == 1
    assert res.safe_approach_headings == []
    assert res.max_obstacle_intrusion_m == 10.0


# ---------------------------------------------------------------------------
# ski_resort_piste_gradient_routing
# ---------------------------------------------------------------------------


def test_ski_average_slope_is_length_weighted() -> None:
    from zero2route3d import classify_ski_pistes_and_route

    coarse = classify_ski_pistes_and_route([(0, 0, 100), (1000, 0, 50), (1002, 0, 49)])
    fine = classify_ski_pistes_and_route([(0, 0, 100), (500, 0, 75), (1000, 0, 50), (1002, 0, 49)])
    assert coarse.average_slope_pct == pytest.approx(51.0 / 1002.0 * 100.0)
    assert fine.average_slope_pct == pytest.approx(coarse.average_slope_pct)
    assert classify_ski_pistes_and_route([(0, 0, 0), (0, 0, -5)]).average_slope_pct == 0.0


# ---------------------------------------------------------------------------
# voice_guidance
# ---------------------------------------------------------------------------


def test_turn_cue_uses_distance_to_the_turn_and_contiguous_steps() -> None:
    from zero2route3d import generate_3d_turn_by_turn_cues

    guide = generate_3d_turn_by_turn_cues([(0, 0, 0), (0, 100, 0), (300, 100, 0), (300, 400, 0)])
    steps = guide.instructions
    assert [s.step_index for s in steps] == [1, 2, 3, 4]
    assert steps[1].maneuver_type == "TURN_RIGHT"
    assert steps[1].instruction_text_en == "In 100 meters, turn right."
    assert steps[1].distance_to_next_m == 300.0
    assert steps[2].maneuver_type == "TURN_LEFT"
    assert steps[2].instruction_text_en == "In 300 meters, turn left."
    assert steps[-1].maneuver_type == "ARRIVE"
    assert guide.total_steps == 4


# ---------------------------------------------------------------------------
# integrations
# ---------------------------------------------------------------------------


def test_geodataframe_segments_carry_hierarchy_and_crs() -> None:
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import LineString

    from zero2route3d.integrations import from_geodataframe

    gdf = gpd.GeoDataFrame(
        {
            "highway": ["motorway", "steps"],
            "oneway": ["-1", "no"],
            "geometry": [
                LineString([(29.0, 41.0), (29.001, 41.0)]),
                LineString([(29.001, 41.0, 5.0), (29.002, 41.0, 7.0)]),
            ],
        },
        crs="EPSG:4326",
    )
    segs = from_geodataframe(gdf)
    assert [(s.highway_type, s.hierarchy_rank) for s in segs] == [("motorway", 1), ("steps", 5)]
    assert segs[0].is_oneway and segs[0].p1[0] == 29.001  # reversed one-way
    assert segs[1].is_steps and segs[1].p2[2] == 7.0

    utm = gpd.GeoDataFrame(
        {"highway": ["primary"]},
        geometry=[LineString([(500000.0, 4540000.0), (500100.0, 4540000.0)])],
        crs="EPSG:32635",
    )
    seg = from_geodataframe(utm)[0]
    assert seg.p1[0] == pytest.approx(27.0)
    assert seg.length_m == pytest.approx(100.0, abs=0.5)

    with pytest.raises(TypeError):
        from_geodataframe([1, 2])


def test_networkx_export_keeps_engine_highway_tag() -> None:
    pytest.importorskip("networkx")
    from zero2route3d.integrations import to_networkx_digraph

    a, b = (29.0, 41.0, 0.0), (29.001, 41.0, 2.0)
    engine = RoutingEngine3D()
    engine.build_graph([_seg(a, b, "motorway")])
    graph = to_networkx_digraph(engine)
    assert {d["highway_type"] for *_e, d in graph.edges(data=True)} == {"motorway"}

    from_segments = to_networkx_digraph([_seg(a, b, "primary")])
    assert from_segments.number_of_edges() == 2
    slopes = sorted(d["slope_pct"] for *_e, d in from_segments.edges(data=True))
    assert slopes[0] == pytest.approx(-slopes[1])


# ---------------------------------------------------------------------------
# solar_shadow
# ---------------------------------------------------------------------------


def test_street_across_the_sun_is_shaded_and_parallel_is_sunlit() -> None:
    from zero2route3d.solar_shadow import (
        calculate_solar_position,
        compute_shade_exposure_along_route,
    )

    lat, hour = 38.4, 18.0
    sun = calculate_solar_position(lat, hour)

    def street(offset_deg: float) -> List[Tuple[float, float, float]]:
        bearing = math.radians(sun.azimuth_deg + offset_deg)
        step = 0.002
        return [
            (27.0, lat, 0.0),
            (
                27.0 + step * math.sin(bearing) / math.cos(math.radians(lat)),
                lat + step * math.cos(bearing),
                0.0,
            ),
        ]

    for offset in (0.0, 180.0):
        assert compute_shade_exposure_along_route(street(offset), hour, 1.0).shaded_pct == 0.0
    for offset in (80.0, 90.0, 100.0, 270.0):
        assert compute_shade_exposure_along_route(street(offset), hour, 1.0).shaded_pct == 100.0


# ---------------------------------------------------------------------------
# osm_downloader (mocked Overpass)
# ---------------------------------------------------------------------------


def _overpass_payload() -> Dict[str, Any]:
    line = [{"lon": 29.0, "lat": 41.0}, {"lon": 29.001, "lat": 41.0}]
    ring = [
        {"lon": 29.0, "lat": 41.0},
        {"lon": 29.0002, "lat": 41.0},
        {"lon": 29.0002, "lat": 41.0002},
        {"lon": 29.0, "lat": 41.0},
    ]
    return {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "tags": {"highway": "primary", "name": "A", "oneway": "yes"},
                "geometry": line,
            },
            {"type": "way", "id": 2, "tags": {"highway": "path"}, "geometry": line[:1]},
            {
                "type": "way",
                "id": 3,
                "tags": {"building": "yes", "building:levels": "5"},
                "geometry": ring,
            },
            {
                "type": "way",
                "id": 4,
                "tags": {"building": "house", "height": "7 m"},
                "geometry": ring,
            },
            {
                "type": "way",
                "id": 5,
                "tags": {"building": "yes", "building:levels": "x"},
                "geometry": ring + [{"lon": "bad"}],
            },
            {
                "type": "node",
                "id": 6,
                "lon": 29.0001,
                "lat": 41.0001,
                "tags": {
                    "natural": "tree",
                    "leaf_type": "needleleaved",
                    "height": "20",
                    "diameter_crown": "6",
                },
            },
            {
                "type": "node",
                "id": 7,
                "lon": 29.0002,
                "lat": 41.0001,
                "tags": {"natural": "tree", "species": "Quercus"},
            },
            {"type": "way", "id": 8, "tags": {"natural": "tree_row"}, "geometry": line},
            {"type": "way", "id": 9, "tags": {"leisure": "park", "name": "P"}, "geometry": ring},
            {"type": "way", "id": 10, "tags": {"natural": "wood"}, "geometry": ring},
        ]
    }


def test_osm_downloader_parses_overpass_response(fake_http: Any) -> None:
    from zero2route3d.osm_downloader import OsmDataFetcher

    fake_http.responses = [_FakeResponse(200, _overpass_payload())]
    roads, buildings, trees, parks = OsmDataFetcher.fetch_full_urban_environment(
        (29.0, 41.0, 29.01, 41.01), timeout_s=float("nan")
    )
    assert fake_http.requests == [("overpass-api.de", "POST", "/api/interpreter")]
    assert fake_http.closed == 1

    assert [(r.road_id, r.highway_type, r.name, r.oneway) for r in roads] == [
        ("1", "primary", "A", True)
    ]
    by_id = {b.building_id: b for b in buildings}
    assert (by_id["3"].levels, by_id["3"].height_m) == (5, pytest.approx(16.0))
    assert (by_id["4"].levels, by_id["4"].height_m, by_id["4"].building_type) == (2, 7.0, "house")
    assert (by_id["5"].levels, by_id["5"].height_m) == (4, 12.0)

    conifer, oak = trees[0], trees[1]
    assert (conifer.tree_type, conifer.height_m, conifer.canopy_radius_m) == ("conifer", 20.0, 3.0)
    assert (oak.species, oak.tree_type, oak.height_m) == ("Quercus", "deciduous", 8.0)
    assert [t.tree_id for t in trees[2:]] == ["8_0", "8_1"]
    assert [(p.park_type, p.name) for p in parks] == [("park", "P"), ("wood", "")]


def test_osm_downloader_invalid_bbox_and_http_error(fake_http: Any) -> None:
    from zero2route3d.osm_downloader import OsmDataFetcher

    assert OsmDataFetcher.fetch_full_urban_environment((29.0, 41.0, 28.0, 42.0)) == ([], [], [], [])
    assert OsmDataFetcher.fetch_full_urban_environment((29.0, float("inf"), 30.0, 42.0)) == (
        [],
        [],
        [],
        [],
    )
    assert OsmDataFetcher.fetch_full_urban_environment(()) == ([], [], [], [])
    assert fake_http.requests == []

    fake_http.responses = [_FakeResponse(429, b"slow down")]
    assert OsmDataFetcher.fetch_roads_and_buildings((29.0, 41.0, 29.01, 41.01)) == ([], [])
    assert fake_http.closed == 1


# ---------------------------------------------------------------------------
# network_source (mocked Photon / Overpass)
# ---------------------------------------------------------------------------


@pytest.fixture
def network_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NetworkSourceManager:
    monkeypatch.setattr(NetworkSourceManager, "CACHE_DIR", tmp_path / "cache")
    return NetworkSourceManager()


def test_photon_search_parses_features(
    network_manager: NetworkSourceManager, fake_http: Any
) -> None:
    fake_http.responses = [
        _FakeResponse(
            200,
            {
                "features": [
                    {
                        "geometry": {"coordinates": [27.14, 38.42]},
                        "properties": {"name": "Konak", "city": "Izmir"},
                    },
                    {"geometry": {"coordinates": [27.0, "x"]}, "properties": {}},
                    {"geometry": {"coordinates": [27.2, 38.5]}, "properties": {}},
                ]
            },
        )
    ]
    results = network_manager.search_place_photon("  konak ", limit="many")  # type: ignore[arg-type]
    assert results == [
        {"label": "Konak (Izmir)", "lon": 27.14, "lat": 38.42},
        {"label": "  konak ", "lon": 27.2, "lat": 38.5},
    ]
    assert fake_http.requests[0][2] == "/api/?q=konak&limit=5"
    assert network_manager.search_place_photon("k") == []


def test_fetch_osm_network_parses_and_caches(
    network_manager: NetworkSourceManager, fake_http: Any
) -> None:
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "nodes": [1, 2, 3],
                "tags": {"highway": "primary", "oneway": "-1", "lanes": "3", "name": "Main"},
            },
            {"type": "way", "id": 2, "nodes": [3, 99], "tags": {"highway": "steps"}},
            {"type": "node", "id": 1, "lon": 29.0, "lat": 41.0},
            {"type": "node", "id": 2, "lon": 29.001, "lat": 41.0},
            {"type": "node", "id": 3, "lon": 29.002, "lat": 41.0},
            {"type": "node", "id": 4, "lon": "bad", "lat": 41.0},
        ]
    }
    fake_http.responses = [_FakeResponse(200, payload)]
    bbox = (29.0, 41.0, 29.002, 41.001)
    segments = network_manager.fetch_osm_network_bbox(bbox)
    assert len(segments) == 2
    first = segments[0]
    # oneway=-1 is stored in its real travel direction.
    assert first.p1[:2] == (29.001, 41.0) and first.p2[:2] == (29.0, 41.0)
    assert (first.is_oneway, first.lanes, first.name, first.hierarchy_rank) == (True, 3, "Main", 2)

    # Second call is served from the disk cache; no further HTTP request.
    assert len(network_manager.fetch_osm_network_bbox(bbox)) == 2
    assert len(fake_http.requests) == 1


def test_fetch_osm_network_failures_raise(
    network_manager: NetworkSourceManager, fake_http: Any
) -> None:
    with pytest.raises(NetworkSourceError):
        network_manager.fetch_osm_network_bbox((29.0, float("nan"), 28.0, 40.0))

    # Both Overpass endpoints fail.
    fake_http.responses = [_FakeResponse(500, b""), _FakeResponse(200, b"not json")]
    with pytest.raises(NetworkSourceError, match="download failed"):
        network_manager.fetch_osm_network_bbox((30.0, 41.0, 30.01, 41.01))
    assert [r[0] for r in fake_http.requests] == ["overpass-api.de", "maps.mail.ru"]

    fake_http.responses = [_FakeResponse(200, {"elements": []})]
    with pytest.raises(NetworkSourceError, match="no usable road segments"):
        network_manager.fetch_osm_network_bbox((31.0, 41.0, 31.01, 41.01))

    with pytest.raises(NetworkSourceError, match="No network source"):
        network_manager.require_segments()


def test_require_segments_from_bbox(network_manager: NetworkSourceManager) -> None:
    sentinel = [_seg((29.0, 41.0, 0.0), (29.001, 41.0, 0.0), "residential")]
    with mock.patch.object(NetworkSourceManager, "fetch_osm_network_bbox", return_value=sentinel):
        assert network_manager.require_segments(bbox=(29.0, 41.0, 29.1, 41.1)) is sentinel


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------


def _write_network(path: Path) -> None:
    coords = [
        [27.1000, 38.4000, 5.0],
        [27.1000, 38.4100, 6.0],
        [27.1100, 38.4100, 8.0],
        [27.1100, 38.4200, 10.0],
    ]
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": {"highway": "residential"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_cli_profiles(capsys: pytest.CaptureFixture[str]) -> None:
    from zero2route3d.cli import main

    assert main(["profiles", "--category", "vehicle"]) == 0
    out = capsys.readouterr().out
    assert "car" in out and "adult " not in out
    assert main(["profiles"]) == 0
    assert "wheelchair" in capsys.readouterr().out
    assert main([]) == 2


def test_cli_route_and_isochrone(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from zero2route3d.cli import main

    network = tmp_path / "net.geojson"
    _write_network(network)
    out_geojson, out_gpx, out_dxf = tmp_path / "r.geojson", tmp_path / "r.gpx", tmp_path / "r.dxf"
    code = main(
        [
            "route",
            "--origin", "27.1,38.4",
            "--dest", "27.11, 38.42",
            "--network", str(network),
            "--out-geojson", str(out_geojson),
            "--out-gpx", str(out_gpx),
            "--out-dxf", str(out_dxf),
        ]
    )  # fmt: skip
    assert code == 0
    assert "Success!" in capsys.readouterr().out
    assert json.loads(out_geojson.read_text(encoding="utf-8"))["geometry"]["type"] == "LineString"
    assert "<gpx" in out_gpx.read_text(encoding="utf-8")
    assert "POLYLINE" in out_dxf.read_text(encoding="utf-8")

    iso_out = tmp_path / "iso.geojson"
    code = main(
        [
            "isochrone",
            "--center", "27.1,38.4",
            "--network", str(network),
            "--intervals", "5, 10",
            "--out-geojson", str(iso_out),
        ]
    )  # fmt: skip
    assert code == 0
    assert len(json.loads(iso_out.read_text(encoding="utf-8"))["features"]) == 2

    # Missing network file is a handled error, not a traceback.
    assert main(["route", "--origin", "1,1", "--dest", "2,2", "--network", "nope.geojson"]) == 1
    assert "Error:" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["route", "--origin", "27.1", "--dest", "1,1", "--network", "x"],
        ["route", "--origin", "a,b", "--dest", "1,1", "--network", "x"],
        ["route", "--origin", "200,1", "--dest", "1,1", "--network", "x"],
        ["isochrone", "--center", "1,1", "--network", "x", "--intervals", "5,-1"],
        ["isochrone", "--center", "1,1", "--network", "x", "--intervals", "a"],
    ],
)
def test_cli_rejects_bad_arguments(argv: List[str]) -> None:
    from zero2route3d.cli import main

    with pytest.raises(SystemExit) as excinfo:
        main(argv)
    assert excinfo.value.code == 2


def test_cli_route_without_connection_returns_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from zero2route3d.cli import main

    network = tmp_path / "net.geojson"
    _write_network(network)
    code = main(["route", "--origin", "10,10", "--dest", "27.11,38.42", "--network", str(network)])
    assert code == 1
    assert "Error:" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# map_matching_3d: GPX parsing
# ---------------------------------------------------------------------------


def test_parse_gpx_handles_self_closing_points_and_bad_values() -> None:
    from zero2route3d.map_matching_3d import HMMMapMatcher3D

    parse = HMMMapMatcher3D.parse_gpx_string
    self_closing = '<gpx><trk><trkseg><trkpt lat="38.4" lon="27.1"/><trkpt lat="38.5" lon="27.2"/>'
    assert [(p.lat, p.lon) for p in parse(self_closing)] == [(38.4, 27.1), (38.5, 27.2)]

    mixed = '<trkpt lat="38.4" lon="27.1"/><trkpt lat="38.5" lon="27.2"><ele>5</ele></trkpt>'
    assert [(p.lat, p.lon, p.elevation_raw_m) for p in parse(mixed)] == [
        (38.4, 27.1, 0.0),
        (38.5, 27.2, 5.0),
    ]

    messy = (
        '<trkpt lat="1" lon="2"><ele>x</ele></trkpt>'
        '<trkpt lon="4" lat="3"><time> 2026-01-01T00:00:00Z </time></trkpt>'
        '<trkpt lat="zz" lon="1"></trkpt>'
    )
    points = parse(messy)
    assert [(p.lat, p.lon, p.elevation_raw_m) for p in points] == [(1.0, 2.0, 0.0), (3.0, 4.0, 0.0)]
    assert points[1].timestamp_iso == "2026-01-01T00:00:00Z"


def test_find_nearest_node_at_high_latitude() -> None:
    lat = 70.0
    origin = (20.0005, lat + 0.00001)
    east = (20.0005 + 1500.0 / (111320.0 * math.cos(math.radians(lat))), origin[1], 0.0)
    north = (20.0005, lat + 2200.0 / 111320.0, 0.0)
    engine = RoutingEngine3D()
    engine.build_graph(
        [
            _seg(east, (east[0] + 0.001, east[1], 0.0), "residential"),
            _seg(north, (north[0] + 0.001, north[1], 0.0), "residential"),
        ]
    )
    nearest = engine.find_nearest_node(origin)
    assert nearest is not None
    assert haversine_distance_2d(origin, engine.nodes[nearest]) == pytest.approx(1500.0, abs=5.0)
