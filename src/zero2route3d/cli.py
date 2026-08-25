"""Command Line Interface (CLI) for zero2route3d.

Provides standalone terminal commands for routing, isochrone generation,
mobility profile inspection, and 3D format export.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from . import __version__
from .api import solve_3d_isochrones, solve_3d_route
from .mobility_profiles import PROFILE_CATEGORIES, PROFILES, list_profile_keys


def _parse_coords(coord_str: str) -> Tuple[float, float]:
    """Parse a 'lon,lat' argument, raising an argparse-friendly error on bad input."""
    parts = [chunk.strip() for chunk in str(coord_str).split(",")]
    if len(parts) < 2:
        raise argparse.ArgumentTypeError(f"Expected 'lon,lat', got '{coord_str}'.")
    try:
        lon, lat = float(parts[0]), float(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Expected numeric 'lon,lat', got '{coord_str}'."
        ) from None
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise argparse.ArgumentTypeError(
            f"Coordinates out of range: lon={lon}, lat={lat} (expected WGS84 lon,lat)."
        )
    return (lon, lat)


def _parse_intervals(value: str) -> List[float]:
    """Parse a comma-separated list of positive minute values."""
    try:
        intervals = [float(chunk.strip()) for chunk in str(value).split(",") if chunk.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Expected comma-separated minutes, got '{value}'."
        ) from None
    if not intervals or any(minutes <= 0 for minutes in intervals):
        raise argparse.ArgumentTypeError("Isochrone intervals must be positive minute values.")
    return intervals


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zero2route3d",
        description="02Route 3D - Headless 3D Spatial Mobility & Kinematic Routing Engine",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    p_profiles = subparsers.add_parser(
        "profiles", help=f"List all {len(PROFILES)} calibrated mobility profiles"
    )
    p_profiles.add_argument(
        "--category",
        choices=["all", *sorted(PROFILE_CATEGORIES)],
        default="all",
        help="Restrict the listing to one profile category.",
    )

    p_route = subparsers.add_parser(
        "route", help="Compute 3D least-cost kinematic route between two points"
    )
    p_route.add_argument(
        "--origin", required=True, type=_parse_coords, help="Origin coordinates as 'lon,lat'"
    )
    p_route.add_argument(
        "--dest", required=True, type=_parse_coords, help="Destination coordinates as 'lon,lat'"
    )
    p_route.add_argument("--network", required=True, help="Path to road network GeoJSON file")
    p_route.add_argument(
        "--profile", default="adult", choices=list_profile_keys(), help="Mobility profile key"
    )
    p_route.add_argument(
        "--dem", help="Optional DEM GeoTIFF used to sample real elevations along the route"
    )
    p_route.add_argument(
        "--fetch-dem",
        action="store_true",
        help="Query Open-Elevation for network elevations when no --dem is given (needs network).",
    )
    p_route.add_argument("--out-geojson", help="Output GeoJSON filepath")
    p_route.add_argument("--out-gpx", help="Output GPX 1.1 track filepath")
    p_route.add_argument("--out-dxf", help="Output AutoCAD DXF 3D Polyline filepath")
    p_route.add_argument("--out-html", help="Output self-contained interactive HTML report")

    p_iso = subparsers.add_parser(
        "isochrone", help="Compute 3D anisotropic isochrone wavefront bands"
    )
    p_iso.add_argument(
        "--center", required=True, type=_parse_coords, help="Center coordinates as 'lon,lat'"
    )
    p_iso.add_argument("--network", required=True, help="Path to road network GeoJSON file")
    p_iso.add_argument(
        "--intervals",
        default="5,10,15",
        type=_parse_intervals,
        help="Comma-separated time intervals in minutes",
    )
    p_iso.add_argument("--profile", default="adult", choices=list_profile_keys())
    p_iso.add_argument("--dem", help="Optional DEM GeoTIFF for real elevation sampling")
    p_iso.add_argument(
        "--fetch-dem",
        action="store_true",
        help="Query Open-Elevation for network elevations when no --dem is given (needs network).",
    )
    p_iso.add_argument("--out-geojson", help="Output GeoJSON filepath")

    return parser


def _make_sampler(dem_path: Optional[str]) -> Optional[object]:
    if not dem_path:
        return None
    from .environmental_raster import EnvironmentalSurfaceSampler

    return EnvironmentalSurfaceSampler(dem=dem_path)


def _cmd_profiles(args: argparse.Namespace) -> int:
    if args.category == "all":
        keys = list_profile_keys()
        heading = "all categories"
    else:
        keys = list(PROFILE_CATEGORIES[args.category]["keys"])
        heading = str(PROFILE_CATEGORIES[args.category]["title"])

    print(f"=== 02Route 3D Mobility Profiles - {heading} (v{__version__}) ===")
    header = (
        f"{'Key':<16} {'Name':<24} {'Category':<15} "
        f"{'Speed':<12} {'Max Slope':<11} {'Stairs Policy'}"
    )
    print(header)
    print("-" * len(header))
    for key in keys:
        prof = PROFILES.get(key)
        if prof is None:
            continue
        stairs = "Allowed" if prof.stair_allowed else "Forbidden"
        print(
            f"{prof.key:<16} {prof.name:<24} {prof.category:<15} "
            f"{prof.base_speed_kmh:>5.1f} km/h {prof.max_slope_pct:>8.1f}%   {stairs}"
        )
    return 0


def _cmd_route(args: argparse.Namespace) -> int:
    print(f"Calculating 3D route from {args.origin} to {args.dest} [Profile: {args.profile}]...")
    result = solve_3d_route(
        args.origin,
        args.dest,
        network=args.network,
        profile=args.profile,
        dem_sampler=_make_sampler(args.dem),  # type: ignore[arg-type]
        fetch_online_dem=args.fetch_dem,
    )

    if not result.is_network_matched:
        print(f"Error: {result.status_message}", file=sys.stderr)
        return 1

    stats = result.statistics
    print("Success!")
    print(f"  Distance:         {stats.total_distance_km:.2f} km")
    print(f"  Duration:         {stats.total_duration_min:.1f} min")
    print(f"  Elevation Gain:   +{stats.elevation_gain_m:.1f} m")
    print(f"  Elevation Loss:   -{stats.elevation_loss_m:.1f} m")
    print(f"  Max Slope:        {stats.max_slope_pct:.1f}%")
    print(f"  Calories:         {stats.total_calories_kcal:.0f} kcal")

    if args.out_geojson:
        Path(args.out_geojson).write_text(
            json.dumps(result.to_geojson_feature(), indent=2), encoding="utf-8"
        )
        print(f"  Saved GeoJSON:    {args.out_geojson}")

    if args.out_gpx:
        Path(args.out_gpx).write_text(result.to_gpx(), encoding="utf-8")
        print(f"  Saved GPX:        {args.out_gpx}")

    if args.out_dxf:
        result.to_dxf(args.out_dxf)
        print(f"  Saved DXF 3D:     {args.out_dxf}")

    if args.out_html:
        result.to_html(args.out_html)
        print(f"  Saved report:     {args.out_html}")

    return 0


def _cmd_isochrone(args: argparse.Namespace) -> int:
    print(f"Computing 3D isochrones from {args.center} with intervals {args.intervals} min...")
    iso_res = solve_3d_isochrones(
        args.center,
        network=args.network,
        profile=args.profile,
        time_intervals_min=args.intervals,
        dem_sampler=_make_sampler(args.dem),  # type: ignore[arg-type]
        fetch_online_dem=args.fetch_dem,
    )

    print(f"Reachable nodes: {iso_res.total_reachable_nodes}")
    for band in iso_res.bands:
        print(
            f"  Band {band.time_cutoff_min:5.1f} min: "
            f"{band.reachable_node_count:6d} nodes, "
            f"{len(band.boundary_points):4d} hull vertices, "
            f"area {band.area_sqkm:.2f} km2"
        )

    if args.out_geojson:
        Path(args.out_geojson).write_text(
            json.dumps(iso_res.to_geojson(), indent=2), encoding="utf-8"
        )
        print(f"  Saved GeoJSON:    {args.out_geojson}")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "profiles": _cmd_profiles,
        "route": _cmd_route,
        "isochrone": _cmd_isochrone,
    }
    handler = handlers.get(args.command or "")
    if handler is None:
        parser.print_help()
        return 2

    try:
        return handler(args)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
