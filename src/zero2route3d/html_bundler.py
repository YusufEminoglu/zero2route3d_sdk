"""Standalone single-file 3D WebGL HTML report generator."""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .routing_engine import RouteResult3D


class StandaloneHtmlBundler:
    """Bundles 3D WebGL engine, Three.js, CSS, and 3D route into a single self-contained HTML file."""

    def __init__(self, web_dir: Optional[Path] = None) -> None:
        self.web_dir = Path(web_dir) if web_dir else Path(__file__).resolve().parent.parent / "web"

    def bundle_to_file(self, data: Union[RouteResult3D, Dict[str, Any]], output_path: Path) -> None:
        """Generate standalone HTML document from RouteResult3D or GeoJSON dict."""
        self.export_standalone_html(data, output_path)

    @staticmethod
    def _finite_number(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        """Convert route payload values into strict JSON-safe primitives."""
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_safe(item) for item in value]
        return value

    def export_standalone_html(
        self, result_or_geojson: Union[RouteResult3D, Dict[str, Any]], output_path: Path
    ) -> None:
        """Generate standalone HTML document with embedded data and JavaScript."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(result_or_geojson, RouteResult3D):
            geojson_data = result_or_geojson.to_geojson_feature()
            profile_name = str(result_or_geojson.profile.name)
            dist_km = result_or_geojson.statistics.total_distance_km
            dur_min = result_or_geojson.statistics.total_duration_min
            climb_m = result_or_geojson.statistics.elevation_gain_m
            slope_pct = result_or_geojson.statistics.max_slope_pct
        else:
            geojson_data = result_or_geojson if isinstance(result_or_geojson, dict) else {}
            props = geojson_data.get("properties", {})
            if geojson_data.get("type") == "FeatureCollection":
                features = geojson_data.get("features", [])
                if features and isinstance(features[0], dict):
                    props = features[0].get("properties", {})
            profile_name = str(props.get("profile_name", "3D Route"))
            dist_km = props.get("distance_km", 0.0)
            dur_min = props.get("duration_min", 0.0)
            climb_m = props.get("elevation_gain_m", 0.0)
            slope_pct = props.get("max_slope_pct", 0.0)

        dist_val = self._finite_number(dist_km)
        dur_val = self._finite_number(dur_min)
        climb_val = self._finite_number(climb_m)
        slope_val = self._finite_number(slope_pct)

        json_str = json.dumps(self._json_safe(geojson_data), allow_nan=False)
        json_str = json_str.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        safe_profile_name = escape(profile_name, quote=True)

        # Read local CSS & JS
        css_content = ""
        css_file = self.web_dir / "css" / "studio3d.css"
        if css_file.exists():
            css_content = css_file.read_text(encoding="utf-8")

        three_js = ""
        three_file = self.web_dir / "js" / "three.module.js"
        if three_file.exists():
            three_js = three_file.read_text(encoding="utf-8")

        controls_js = ""
        controls_file = self.web_dir / "js" / "OrbitControls.js"
        if controls_file.exists():
            controls_js = controls_file.read_text(encoding="utf-8")

        rig_js = ""
        rig_file = self.web_dir / "js" / "KinematicAvatarRig.js"
        if rig_file.exists():
            rig_js = (
                rig_file.read_text(encoding="utf-8")
                .replace("import * as THREE from './three.module.js';", "")
                .replace("export class KinematicAvatarRig", "class KinematicAvatarRig")
            )

        slicer_js = ""
        slicer_file = self.web_dir / "js" / "TerrainSlicerSystem.js"
        if slicer_file.exists():
            slicer_js = (
                slicer_file.read_text(encoding="utf-8")
                .replace("import * as THREE from './three.module.js';", "")
                .replace("export class TerrainSlicerSystem", "class TerrainSlicerSystem")
            )

        voice_js = ""
        voice_file = self.web_dir / "js" / "VoiceCueSystem.js"
        if voice_file.exists():
            voice_js = voice_file.read_text(encoding="utf-8").replace(
                "export class VoiceCueSystem", "class VoiceCueSystem"
            )

        app_js = ""
        app_file = self.web_dir / "js" / "app3d.js"
        if app_file.exists():
            app_js = app_file.read_text(encoding="utf-8")

        # Strip module imports from app_js for standalone script
        app_js_clean = app_js.replace("import * as THREE from './three.module.js';", "")
        app_js_clean = app_js_clean.replace(
            "import { OrbitControls } from './OrbitControls.js';", ""
        )
        app_js_clean = app_js_clean.replace(
            "import { KinematicAvatarRig } from './KinematicAvatarRig.js';", ""
        )
        app_js_clean = app_js_clean.replace(
            "import { TerrainSlicerSystem } from './TerrainSlicerSystem.js';", ""
        )
        app_js_clean = app_js_clean.replace(
            "import { VoiceCueSystem } from './VoiceCueSystem.js';", ""
        )

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>02Route 3D Studio — Standalone 3D Route Report ({safe_profile_name})</title>
  <style>
{css_content}
  </style>
</head>
<body>
  <div id="canvasContainer"></div>

  <div class="hud-panel top-hud">
    <div class="brand-section">
      <span class="brand-badge">OFFLINE 3D</span>
      <span class="brand-title">02Route 3D — {safe_profile_name}</span>
    </div>
    <div class="stats-row">
      <div class="stat-item"><span class="stat-label">Distance</span><span class="stat-value">{dist_val:.2f} km</span></div>
      <div class="stat-item"><span class="stat-label">Duration</span><span class="stat-value">{dur_val:.1f} min</span></div>
      <div class="stat-item"><span class="stat-label">Climb</span><span class="stat-value">+{climb_val:.1f} m</span></div>
      <div class="stat-item"><span class="stat-label">Max Slope</span><span class="stat-value">{slope_val:.1f}%</span></div>
    </div>
  </div>

  <div class="hud-panel bottom-player">
    <div class="player-controls">
      <div class="play-btn-group">
        <button id="btnPlay" class="btn-icon"><span id="playIcon">▶</span></button>
      </div>
      <div class="timeline-scrubber">
        <input type="range" id="scrubber" class="scrubber-slider" min="0" max="1000" value="0">
      </div>
    </div>
    <div class="chart-drawer" id="chartDrawer">
      <svg id="profileSvg" preserveAspectRatio="none"></svg>
      <div class="profile-needle" id="profileNeedle"></div>
    </div>
  </div>

  <!-- Embedded Three.js & Controls -->
  <script type="text/javascript">
{three_js}
  </script>
  <script type="text/javascript">
{controls_js}
  </script>
  <script type="text/javascript">
{rig_js}
  </script>
  <script type="text/javascript">
{slicer_js}
  </script>
  <script type="text/javascript">
{voice_js}
  </script>
  <script type="text/javascript">
{app_js_clean}

  // Auto-load route data on startup
  window.addEventListener('DOMContentLoaded', () => {{
    const data = {json_str};
    if (window.setRouteData) {{
      window.setRouteData(data);
    }}
  }});
  </script>
</body>
</html>"""

        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        temp_path.write_text(html_template, encoding="utf-8")
        temp_path.replace(output_path)
