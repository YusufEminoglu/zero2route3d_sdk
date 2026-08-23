"""Command Line Interface (CLI) for zero2route3d.

Provides standalone terminal commands for routing, isochrone generation,
HMM map matching, mobility profile inspection, and 3D format export.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .api import solve_3d_isochrones, solve_3d_route
from .mobility_profiles import PROFILES, list_profile_keys


def _parse_coords(coord_str: str) -> tuple[float, float]:
    parts = [float(x.strip()) for x in coord_str.split(",")]
    if len(parts) < 2:
        raise ValueError(f"Expected 'lon,lat', got '{coord_str}'")
    return (parts[0], parts[1])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="zero2route3d",
        description="02Route 3D — Headless 3D Spatial Mobility & Kinematic Routing Engine",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: profiles
    p_profiles = subparsers.add_parser("profiles", help="List all 15 calibrated mobility profiles")
    p_profiles.add_argument(
        "--category",
        choices=["all", "pedestrian", "micromobility", "vehicle", "emergency"],
        default="all",
    )

    # Command: route
    p_route = subparsers.add_parser(
        "route", help="Compute 3D least-cost kinematic route between two points"
    )
    p_route.add_argument("--origin", required=True, help="Origin coordinates as 'lon,lat'")
    p_route.add_argument("--dest", required=True, help="Destination coordinates as 'lon,lat'")
    p_route.add_argument("--network", required=True, help="Path to road network GeoJSON file")
    p_route.add_argument(
        "--profile", default="adult", choices=list_profile_keys(), help="Mobility profile key"
    )
    p_route.add_argument("--out-geojson", help="Output GeoJSON filepath")
    p_route.add_argument("--out-dxf", help="Output AutoCAD DXF 3D Polyline filepath")
    p_route.add_argument("--out-html", help="Output Three.js 3D WebGL HTML viewer filepath")

    # Command: isochrone
    p_iso = subparsers.add_parser(
        "isochrone", help="Compute 3D anisotropic isochrone wavefront bands"
    )
    p_iso.add_argument("--center", required=True, help="Center coordinates as 'lon,lat'")
    p_iso.add_argument("--network", required=True, help="Path to road network GeoJSON file")
    p_iso.add_argument(
        "--intervals", default="5,10,15", help="Comma-separated time intervals in minutes"
    )
    p_iso.add_argument("--profile", default="adult", choices=list_profile_keys())
    p_iso.add_argument("--out-geojson", help="Output GeoJSON filepath")

    args = parser.parse_args(argv)

    if args.command == "profiles":
        print(f"=== 02Route 3D Mobility Profiles Catalog (v{__version__}) ===")
        print(
            f"{'Key':<16} {'Name':<24} {'Category':<14} {'Speed':<10} {'Max Slope':<10} {'Stairs Policy'}"
        )
        print("-" * 85)
        for k, prof in PROFILES.items():
            stairs = "Allowed" if prof.stair_allowed else "Forbidden"
            print(
                f"{k:<16} {prof.name:<24} {prof.category:<14} {prof.base_speed_kmh:<4.1f} km/h  {prof.max_slope_pct:<5.1f}%     {stairs}"
            )
        return 0

    if args.command == "route":
        orig = _parse_coords(args.origin)
        dest = _parse_coords(args.dest)
        print(f"Calculating 3D route from {orig} to {dest} [Profile: {args.profile}]...")
        result = solve_3d_route(orig, dest, network=args.network, profile=args.profile)

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

        if args.out_dxf:
            from .profile_dxf import export_route_to_dxf_3d

            export_route_to_dxf_3d(result.coordinates_3d, args.out_dxf)
            print(f"  Saved DXF 3D:     {args.out_dxf}")

        if args.out_html:
            from .html_bundler import StandaloneHtmlBundler

            bundler = StandaloneHtmlBundler()
            bundler.bundle_to_file(result.to_geojson_feature(), args.out_html)
            print(f"  Saved 3D Studio:  {args.out_html}")

        return 0

    if args.command == "isochrone":
        center = _parse_coords(args.center)
        intervals = [float(x.strip()) for x in args.intervals.split(",")]
        print(f"Computing 3D isochrones from {center} with intervals {intervals} min...")
        iso_res = solve_3d_isochrones(
            center, network=args.network, profile=args.profile, time_intervals_min=intervals
        )

        print(f"Reachable nodes: {iso_res.total_reachable_nodes}")
        for band in iso_res.bands:
            print(
                f"  Band {band.cutoff_minutes:4.1f} min: {len(band.boundary_hull_coordinates)} hull vertices, area {band.area_sqkm:.2f} km²"
            )

        if args.out_geojson:
            Path(args.out_geojson).write_text(
                json.dumps(iso_res.to_geojson(), indent=2), encoding="utf-8"
            )
            print(f"  Saved GeoJSON:    {args.out_geojson}")

        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
