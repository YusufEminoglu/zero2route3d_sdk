"""QGIS QML Layer Style Generator for 3D Route and Elevation Symbology."""

from __future__ import annotations

import contextlib
import math
from pathlib import Path
from typing import Any, List, Optional, Union


def generate_route_qml_style(
    target_or_profile: Optional[Union[Path, str]] = None,
    layer_title: str = "3D Route",
    line_width_mm: float = 1.2,
    line_color_hex: str = "#0ea5e9",
) -> str:
    """Generate a standard QGIS 3.x/4.x compatible QML style XML string and optionally save to file."""
    # Profile-specific color mapping
    colors = {
        "adult": "14,165,233,255",
        "child": "245,158,11,255",
        "senior": "16,185,129,255",
        "wheelchair": "139,92,246,255",
        "commuter": "6,182,212,255",
        "road_bike": "59,130,246,255",
        "ebike": "168,85,247,255",
        "cargo_bike": "234,88,12,255",
        "scooter": "20,184,166,255",
        "car": "239,68,68,255",
        "paramedic": "225,29,72,255",
    }

    prof_key = "adult"
    target_file: Optional[Path] = None

    if isinstance(target_or_profile, Path):
        target_file = target_or_profile
    elif isinstance(target_or_profile, str):
        if target_or_profile.endswith(".qml"):
            target_file = Path(target_or_profile)
        else:
            prof_key = target_or_profile.lower()

    core_color = colors.get(prof_key, "14,165,233,255")
    parts = core_color.split(",")
    if len(parts) == 4:
        glow_color = f"{parts[0]},{parts[1]},{parts[2]},90"
    else:
        glow_color = core_color

    w_mm = float(line_width_mm) if math.isfinite(line_width_mm) and line_width_mm > 0 else 1.2
    glow_width = f"{w_mm * 2.0:.1f}"
    core_width = f"{w_mm:.1f}"

    qml_content = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="AllStyleCategories">
  <renderer-v2 type="singleSymbol" enableorderby="0" forceraster="0" referencescale="-1">
    <symbols>
      <symbol type="line" name="0" alpha="1" clip_to_extent="1" force_rhr="0">
        <data_defined_properties>
          <Option type="Map">
            <Option type="QString" name="name" value=""/>
            <Option name="properties"/>
            <Option type="QString" name="type" value="collection"/>
          </Option>
        </data_defined_properties>
        <!-- Outer Glow Layer -->
        <layer enabled="1" class="SimpleLine" locked="0" pass="0">
          <Option type="Map">
            <Option type="QString" name="line_color" value="{glow_color}"/>
            <Option type="QString" name="line_style" value="solid"/>
            <Option type="QString" name="line_width" value="{glow_width}"/>
            <Option type="QString" name="line_width_unit" value="MM"/>
            <Option type="QString" name="capstyle" value="round"/>
            <Option type="QString" name="joinstyle" value="round"/>
          </Option>
        </layer>
        <!-- Inner Core Neon Line -->
        <layer enabled="1" class="SimpleLine" locked="0" pass="1">
          <Option type="Map">
            <Option type="QString" name="line_color" value="{core_color}"/>
            <Option type="QString" name="line_style" value="solid"/>
            <Option type="QString" name="line_width" value="{core_width}"/>
            <Option type="QString" name="line_width_unit" value="MM"/>
            <Option type="QString" name="capstyle" value="round"/>
            <Option type="QString" name="joinstyle" value="round"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <blendMode>0</blendMode>
  <featureBlendMode>0</featureBlendMode>
</qgis>"""

    if target_file is not None:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(qml_content, encoding="utf-8")

    return qml_content


def apply_multiprofile_categorized_renderer(
    layer: Any, field_name: str = "mode_key", active_keys: Optional[List[str]] = None
) -> None:
    """Apply a publication-grade categorized glow+core renderer for calculated mobility modes in PyQGIS."""
    with contextlib.suppress(Exception):
        from qgis.core import (
            QgsCategorizedSymbolRenderer,
            QgsLineSymbol,
            QgsRendererCategory,
            QgsSimpleLineSymbolLayer,
        )
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QColor

        from .mobility_profiles import PROFILE_COLORS, PROFILES

        # If active_keys is explicitly given, only include those keys in the legend
        if active_keys is not None:
            keys_to_render = [k for k in active_keys if k in PROFILES]
        else:
            # Fallback: extract unique mode_key values from the layer's features
            idx = layer.fields().indexOf(field_name) if hasattr(layer, "fields") else -1
            if idx != -1:
                unique_vals = layer.uniqueValues(idx)
                keys_to_render = [str(v) for v in unique_vals if str(v) in PROFILES]
            else:
                keys_to_render = list(PROFILES.keys())

        if not keys_to_render:
            keys_to_render = list(PROFILES.keys())

        categories = []
        for key in keys_to_render:
            prof = PROFILES[key]
            color_hex = PROFILE_COLORS.get(key, "#0ea5e9")
            qcol = QColor(color_hex)
            glow_col = QColor(qcol.red(), qcol.green(), qcol.blue(), 85)

            # Determine line width and dash style
            line_width = (
                1.3
                if prof.category == "vehicle"
                else (1.1 if prof.category == "micromobility" else 0.9)
            )
            glow_width = line_width * 2.2

            sym = QgsLineSymbol()
            # Layer 0: Outer Glow
            sl_glow = QgsSimpleLineSymbolLayer(glow_col)
            sl_glow.setWidth(glow_width)
            sl_glow.setPenCapStyle(
                Qt.PenCapStyle.RoundCap if hasattr(Qt, "PenCapStyle") else Qt.RoundCap
            )
            sl_glow.setPenJoinStyle(
                Qt.PenJoinStyle.RoundJoin if hasattr(Qt, "PenJoinStyle") else Qt.RoundJoin
            )
            sym.changeSymbolLayer(0, sl_glow)

            # Layer 1: Core Line
            sl_core = QgsSimpleLineSymbolLayer(qcol)
            sl_core.setWidth(line_width)
            if key in ("wheelchair", "stroller"):
                sl_core.setPenStyle(
                    Qt.PenStyle.DashLine if hasattr(Qt, "PenStyle") else Qt.DashLine
                )
            elif key in ("jogger", "night_walk"):
                sl_core.setPenStyle(
                    Qt.PenStyle.DashDotLine if hasattr(Qt, "PenStyle") else Qt.DashDotLine
                )
            else:
                sl_core.setPenStyle(
                    Qt.PenStyle.SolidLine if hasattr(Qt, "PenStyle") else Qt.SolidLine
                )
            sl_core.setPenCapStyle(
                Qt.PenCapStyle.RoundCap if hasattr(Qt, "PenCapStyle") else Qt.RoundCap
            )
            sl_core.setPenJoinStyle(
                Qt.PenJoinStyle.RoundJoin if hasattr(Qt, "PenJoinStyle") else Qt.RoundJoin
            )
            sym.appendSymbolLayer(sl_core)

            label = f"{prof.name} ({prof.category.capitalize()})"
            categories.append(QgsRendererCategory(key, sym, label))

        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
