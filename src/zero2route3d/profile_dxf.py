"""AutoCAD DXF 3D Polyline and Longitudinal Profile Exporter.

Generates standard ASCII DXF (R12/2000) files containing 3D polyline route geometry
and cross-sectional elevation profile drawings for CAD / BIM interoperability.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence, Union

from .kinematics import haversine_distance_2d


def export_route_to_dxf_3d(
    coords_3d: Sequence[Sequence[float]],
    target_path: Union[str, Path],
    include_profile_section: bool = True,
    profile_vertical_scale: float = 5.0,
    layer_name: str = "3D_ROUTE",
) -> None:
    """Write 3D route coordinates to standard AutoCAD DXF file."""
    out_path = Path(target_path)

    def finite(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    out_path.parent.mkdir(parents=True, exist_ok=True)
    clean_coords = [
        (
            finite(pt[0]),
            finite(pt[1]),
            finite(pt[2]) if len(pt) > 2 else 0.0,
        )
        for pt in coords_3d
        if pt and len(pt) >= 2
    ]

    if not clean_coords:
        lines = [
            "0",
            "SECTION",
            "2",
            "HEADER",
            "9",
            "$ACADVER",
            "1",
            "AC1009",
            "0",
            "ENDSEC",
            "0",
            "SECTION",
            "2",
            "ENTITIES",
            "0",
            "ENDSEC",
            "0",
            "EOF",
        ]
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines = [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$ACADVER",
        "1",
        "AC1009",  # AutoCAD R12 compatibility
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "TABLES",
        "0",
        "TABLE",
        "2",
        "LAYER",
        "70",
        "2",
        "0",
        "LAYER",
        "2",
        layer_name,
        "70",
        "0",
        "62",
        "4",  # Cyan color
        "6",
        "CONTINUOUS",
        "0",
        "LAYER",
        "2",
        "PROFILE_GRID",
        "70",
        "0",
        "62",
        "1",  # Red color
        "6",
        "CONTINUOUS",
        "0",
        "ENDTAB",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
    ]

    # 1. 3D Polyline Entity
    lines.extend(
        [
            "0",
            "POLYLINE",
            "8",
            layer_name,
            "66",
            "1",  # Vertices follow
            "70",
            "8",  # 3D Polyline flag
            "10",
            "0.0",
            "20",
            "0.0",
            "30",
            "0.0",
        ]
    )

    for pt in clean_coords:
        lines.extend(
            [
                "0",
                "VERTEX",
                "8",
                layer_name,
                "70",
                "32",  # 3D Polyline vertex
                "10",
                f"{pt[0]:.6f}",
                "20",
                f"{pt[1]:.6f}",
                "30",
                f"{pt[2]:.2f}",
            ]
        )

    lines.extend(["0", "SEQEND"])

    # 2. Longitudinal Profile Drawing in Model Space (Offset to the side)
    scale = (
        float(profile_vertical_scale)
        if math.isfinite(profile_vertical_scale) and profile_vertical_scale > 0
        else 5.0
    )
    if include_profile_section and len(clean_coords) >= 2:
        accum_dist = 0.0
        min_elev = min(p[2] for p in clean_coords)

        # Baseline offset for profile drawing
        x_base = clean_coords[0][0]
        y_base = clean_coords[0][1] - 0.02

        profile_pts = []
        for i in range(len(clean_coords)):
            if i > 0:
                d = haversine_distance_2d(clean_coords[i - 1], clean_coords[i])
                accum_dist += d
            dz = clean_coords[i][2] - min_elev
            px = x_base + (accum_dist / 111320.0)
            py = y_base + ((dz * scale) / 110574.0)
            profile_pts.append((px, py, 0.0))

        # Profile Polyline
        lines.extend(
            [
                "0",
                "POLYLINE",
                "8",
                "PROFILE_GRID",
                "66",
                "1",
                "70",
                "0",
                "10",
                "0.0",
                "20",
                "0.0",
                "30",
                "0.0",
            ]
        )

        for p in profile_pts:
            lines.extend(
                [
                    "0",
                    "VERTEX",
                    "8",
                    "PROFILE_GRID",
                    "10",
                    f"{p[0]:.6f}",
                    "20",
                    f"{p[1]:.6f}",
                    "30",
                    "0.0",
                ]
            )

        lines.extend(["0", "SEQEND"])

    # Close Entities & File
    lines.extend(
        [
            "0",
            "ENDSEC",
            "0",
            "EOF",
        ]
    )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
