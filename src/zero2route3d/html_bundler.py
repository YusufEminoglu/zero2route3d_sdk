"""Standalone single-file interactive HTML report generator.

The report is genuinely self-contained: all CSS and JavaScript are inlined and
no network request is made when it is opened, so it works from a file:// URL, an
email attachment or an air-gapped machine.

By default it renders a dependency-free viewer -- a plan-view route map, a
longitudinal elevation/speed profile, a slope-coloured track and a scrubber that
links all three. Pass ``web_dir`` pointing at the 02Route 3D QGIS plugin's
``web/`` folder to bundle the full Three.js WebGL studio instead; that folder
(Three.js alone is >1 MB) deliberately ships with the plugin rather than with
this SDK.
"""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .routing_engine import RouteResult3D

_WEBGL_ASSETS = (
    ("css", "studio3d.css"),
    ("js", "three.module.js"),
    ("js", "OrbitControls.js"),
    ("js", "KinematicAvatarRig.js"),
    ("js", "TerrainSlicerSystem.js"),
    ("js", "VoiceCueSystem.js"),
    ("js", "app3d.js"),
)


class StandaloneHtmlBundler:
    """Bundles a 3D route, its statistics and an interactive viewer into one HTML file."""

    def __init__(self, web_dir: Optional[Union[str, Path]] = None) -> None:
        self.web_dir: Optional[Path] = Path(web_dir) if web_dir else None

    # -- public API --------------------------------------------------------

    def bundle_to_file(
        self, data: Union[RouteResult3D, Dict[str, Any]], output_path: Union[str, Path]
    ) -> None:
        """Generate a standalone HTML document from a RouteResult3D or GeoJSON dict."""
        self.export_standalone_html(data, output_path)

    def export_standalone_html(
        self,
        result_or_geojson: Union[RouteResult3D, Dict[str, Any]],
        output_path: Union[str, Path],
    ) -> None:
        """Write the standalone HTML document atomically to ``output_path``."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        html_document = self.bundle(result_or_geojson)
        temp_path = out_p.with_suffix(out_p.suffix + ".tmp")
        temp_path.write_text(html_document, encoding="utf-8")
        temp_path.replace(out_p)

    @property
    def has_webgl_assets(self) -> bool:
        """True when ``web_dir`` holds the Three.js studio assets needed to bundle it."""
        if self.web_dir is None:
            return False
        return all((self.web_dir / folder / name).exists() for folder, name in _WEBGL_ASSETS)

    def bundle(self, result_or_geojson: Union[RouteResult3D, Dict[str, Any]]) -> str:
        """Return the complete standalone HTML document as a string."""
        payload = self._extract_payload(result_or_geojson)
        if self.has_webgl_assets:
            return self._render_webgl_studio(payload)
        return self._render_builtin_viewer(payload)

    # -- payload -----------------------------------------------------------

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

    def _extract_payload(
        self, result_or_geojson: Union[RouteResult3D, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Normalize a RouteResult3D or a GeoJSON Feature into one rendering payload."""
        if isinstance(result_or_geojson, RouteResult3D):
            geojson_data: Dict[str, Any] = result_or_geojson.to_geojson_feature()
        elif isinstance(result_or_geojson, dict):
            geojson_data = result_or_geojson
        else:
            geojson_data = {}

        props: Dict[str, Any] = {}
        if isinstance(geojson_data, dict):
            if geojson_data.get("type") == "FeatureCollection":
                features = geojson_data.get("features") or []
                if features and isinstance(features[0], dict):
                    props = features[0].get("properties") or {}
            else:
                props = geojson_data.get("properties") or {}

        coordinates = self._extract_coordinates(geojson_data)
        return {
            "geojson": geojson_data,
            "profile_name": str(props.get("profile_name", "3D Route")),
            "profile_color": str(props.get("profile_color", "#38bdf8")),
            "distance_km": self._finite_number(props.get("distance_km")),
            "duration_min": self._finite_number(props.get("duration_min")),
            "climb_m": self._finite_number(props.get("elevation_gain_m")),
            "descent_m": self._finite_number(props.get("elevation_loss_m")),
            "max_slope_pct": self._finite_number(props.get("max_slope_pct")),
            "calories_kcal": self._finite_number(props.get("calories_kcal")),
            "ada_compliant": bool(props.get("ada_compliant", False)),
            "elevation_profile": props.get("elevation_profile") or [],
            "cue_sheet": props.get("cue_sheet") or [],
            "coordinates": coordinates,
        }

    @staticmethod
    def _extract_coordinates(geojson_data: Any) -> List[Tuple[float, float, float]]:
        """Pull the 3D LineString vertices out of a Feature or FeatureCollection."""
        if not isinstance(geojson_data, dict):
            return []
        geometry = geojson_data.get("geometry")
        if geometry is None and geojson_data.get("type") == "FeatureCollection":
            features = geojson_data.get("features") or []
            if features and isinstance(features[0], dict):
                geometry = features[0].get("geometry")
        if not isinstance(geometry, dict):
            return []
        raw = geometry.get("coordinates") or []
        if geometry.get("type") == "MultiLineString":
            raw = [pt for line in raw for pt in line]

        coords: List[Tuple[float, float, float]] = []
        for pt in raw:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                continue
            try:
                lon, lat = float(pt[0]), float(pt[1])
                elevation = float(pt[2]) if len(pt) > 2 else 0.0
            except (TypeError, ValueError):
                continue
            if math.isfinite(lon) and math.isfinite(lat) and math.isfinite(elevation):
                coords.append((lon, lat, elevation))
        return coords

    def _embedded_json(self, payload: Dict[str, Any]) -> str:
        """Serialize a payload for safe inlining inside a <script> block."""
        text = json.dumps(self._json_safe(payload), allow_nan=False)
        return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    # -- renderers ---------------------------------------------------------

    def _render_webgl_studio(self, payload: Dict[str, Any]) -> str:
        """Inline the plugin's Three.js studio; only used when ``web_dir`` supplies it."""
        web_dir = self.web_dir
        if web_dir is None:  # pragma: no cover - guarded by has_webgl_assets
            raise RuntimeError("web_dir must be set to bundle the WebGL studio.")

        def read(folder: str, name: str) -> str:
            return (web_dir / folder / name).read_text(encoding="utf-8")

        css_content = read("css", "studio3d.css")
        three_js = read("js", "three.module.js")
        controls_js = read("js", "OrbitControls.js")
        rig_js = read("js", "KinematicAvatarRig.js")
        slicer_js = read("js", "TerrainSlicerSystem.js")
        voice_js = read("js", "VoiceCueSystem.js")
        app_js = read("js", "app3d.js")

        for module_import in (
            "import * as THREE from './three.module.js';",
            "import { OrbitControls } from './OrbitControls.js';",
            "import { KinematicAvatarRig } from './KinematicAvatarRig.js';",
            "import { TerrainSlicerSystem } from './TerrainSlicerSystem.js';",
            "import { VoiceCueSystem } from './VoiceCueSystem.js';",
        ):
            app_js = app_js.replace(module_import, "")
            rig_js = rig_js.replace(module_import, "")
            slicer_js = slicer_js.replace(module_import, "")
            voice_js = voice_js.replace(module_import, "")

        for export_class in (
            "KinematicAvatarRig",
            "TerrainSlicerSystem",
            "VoiceCueSystem",
        ):
            rig_js = rig_js.replace(f"export class {export_class}", f"class {export_class}")
            slicer_js = slicer_js.replace(f"export class {export_class}", f"class {export_class}")
            voice_js = voice_js.replace(f"export class {export_class}", f"class {export_class}")

        safe_profile_name = escape(payload["profile_name"], quote=True)
        json_str = self._embedded_json(payload["geojson"])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>02Route 3D Studio - {safe_profile_name}</title>
  <style>
{css_content}
  </style>
</head>
<body>
  <div id="canvasContainer"></div>

  <div class="hud-panel top-hud">
    <div class="brand-section">
      <span class="brand-badge">OFFLINE 3D</span>
      <span class="brand-title">02Route 3D - {safe_profile_name}</span>
    </div>
    <div class="stats-row">
      <div class="stat-item"><span class="stat-label">Distance</span><span class="stat-value">{payload["distance_km"]:.2f} km</span></div>
      <div class="stat-item"><span class="stat-label">Duration</span><span class="stat-value">{payload["duration_min"]:.1f} min</span></div>
      <div class="stat-item"><span class="stat-label">Climb</span><span class="stat-value">+{payload["climb_m"]:.1f} m</span></div>
      <div class="stat-item"><span class="stat-label">Max Slope</span><span class="stat-value">{payload["max_slope_pct"]:.1f}%</span></div>
    </div>
  </div>

  <div class="hud-panel bottom-controls">
    <div class="multi-metric-panel" id="multiMetricPanel">
      <div class="multi-metric-rows" id="multiMetricRows"></div>
    </div>
    <div class="player-scrubber-row">
      <button class="btn-play" id="btnPlay" title="Play/Pause 3D Centerline Simulation">
        <span id="playIcon">&#9654;</span>
      </button>
      <div class="scrubber-container">
        <input type="range" class="scrubber-slider" id="scrubber" min="0" max="1000" value="0">
      </div>
    </div>
  </div>

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
{app_js}

  window.addEventListener('DOMContentLoaded', () => {{
    const data = {json_str};
    if (window.setRouteData) {{
      window.setRouteData(data);
    }}
  }});
  </script>
</body>
</html>"""

    def _render_builtin_viewer(self, payload: Dict[str, Any]) -> str:
        """Render the dependency-free interactive report bundled with the SDK."""
        safe_profile_name = escape(payload["profile_name"], quote=True)
        accent = payload["profile_color"]
        if not (isinstance(accent, str) and accent.startswith("#") and len(accent) in (4, 7)):
            accent = "#38bdf8"

        view_payload = {
            "coordinates": payload["coordinates"],
            "elevationProfile": payload["elevation_profile"],
            "cueSheet": payload["cue_sheet"],
            "profileName": payload["profile_name"],
            "accent": accent,
            "stats": {
                "distance_km": payload["distance_km"],
                "duration_min": payload["duration_min"],
                "climb_m": payload["climb_m"],
                "descent_m": payload["descent_m"],
                "max_slope_pct": payload["max_slope_pct"],
                "calories_kcal": payload["calories_kcal"],
                "ada_compliant": payload["ada_compliant"],
            },
            "geojson": payload["geojson"],
        }
        json_str = self._embedded_json(view_payload)
        empty_state = "" if payload["coordinates"] else "is-empty"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>02Route 3D Report - {safe_profile_name}</title>
<style>
{_BUILTIN_CSS.replace("__ACCENT__", accent)}
</style>
</head>
<body class="{empty_state}">
<header class="topbar">
  <div class="brand">
    <span class="badge">OFFLINE REPORT</span>
    <h1>02Route 3D &mdash; {safe_profile_name}</h1>
  </div>
  <div class="stats" id="statsRow"></div>
</header>

<main class="grid">
  <section class="panel">
    <h2>Plan view</h2>
    <div class="plot-wrap"><svg id="planView" preserveAspectRatio="xMidYMid meet"></svg></div>
    <p class="hint">Slope-coloured centreline. Green = descent, grey = flat, red = climb.</p>
  </section>
  <section class="panel">
    <h2>Longitudinal profile</h2>
    <div class="plot-wrap"><svg id="profileView" preserveAspectRatio="none"></svg></div>
    <div class="scrub-row">
      <input type="range" id="scrubber" min="0" max="1000" value="0" aria-label="Position along route">
      <output id="readout"></output>
    </div>
  </section>
</main>

<section class="panel cues" id="cuePanel">
  <h2>Cue sheet</h2>
  <ol id="cueList"></ol>
</section>

<p class="empty-note">No route geometry was supplied, so there is nothing to draw.</p>

<script>
const ROUTE = {json_str};
{_BUILTIN_JS}
</script>
</body>
</html>"""


_BUILTIN_CSS = """
:root {
  color-scheme: dark;
  --accent: __ACCENT__;
  --bg: #0b1220;
  --panel: #131c2e;
  --line: #24314b;
  --text: #e6edf7;
  --muted: #94a3b8;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 0 24px 32px;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
}
.topbar {
  display: flex; flex-wrap: wrap; gap: 16px; align-items: center;
  justify-content: space-between; padding: 20px 0 16px;
  border-bottom: 1px solid var(--line);
}
.brand h1 { margin: 6px 0 0; font-size: 20px; font-weight: 700; }
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 999px;
  background: var(--accent); color: #05111f; font-size: 11px;
  font-weight: 700; letter-spacing: .06em;
}
.stats { display: flex; flex-wrap: wrap; gap: 10px; }
.stat {
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 12px; min-width: 96px;
}
.stat span { display: block; font-size: 11px; color: var(--muted); }
.stat strong { font-size: 15px; font-variant-numeric: tabular-nums; }
.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); margin-top: 20px; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
.panel h2 { margin: 0 0 12px; font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.plot-wrap { width: 100%; overflow-x: auto; }
svg { width: 100%; height: 280px; display: block; }
.hint { margin: 8px 0 0; font-size: 12px; color: var(--muted); }
.scrub-row { display: flex; gap: 12px; align-items: center; margin-top: 12px; }
.scrub-row input { flex: 1; accent-color: var(--accent); }
.scrub-row output { font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.cues { margin-top: 16px; }
.cues ol { margin: 0; padding-left: 20px; max-height: 260px; overflow-y: auto; }
.cues li { padding: 4px 0; border-bottom: 1px solid var(--line); }
.cues li:last-child { border-bottom: 0; }
.cue-dist { color: var(--muted); font-variant-numeric: tabular-nums; margin-right: 8px; }
.empty-note { display: none; margin-top: 24px; color: var(--muted); }
body.is-empty .grid, body.is-empty .cues { display: none; }
body.is-empty .empty-note { display: block; }
@media print {
  body { background: #fff; color: #111; }
  .panel { background: #fff; border-color: #ccc; }
}
"""

_BUILTIN_JS = """
(function () {
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const coords = Array.isArray(ROUTE.coordinates) ? ROUTE.coordinates : [];
  const accent = ROUTE.accent || '#38bdf8';

  function el(name, attrs) {
    const node = document.createElementNS(SVG_NS, name);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    return node;
  }

  function fmt(value, digits) {
    return Number.isFinite(value) ? value.toFixed(digits) : '-';
  }

  const s = ROUTE.stats || {};
  const statsRow = document.getElementById('statsRow');
  [
    ['Distance', fmt(s.distance_km, 2) + ' km'],
    ['Duration', fmt(s.duration_min, 1) + ' min'],
    ['Climb', '+' + fmt(s.climb_m, 1) + ' m'],
    ['Descent', '-' + fmt(s.descent_m, 1) + ' m'],
    ['Max slope', fmt(s.max_slope_pct, 1) + '%'],
    ['Energy', s.calories_kcal ? fmt(s.calories_kcal, 0) + ' kcal' : 'n/a'],
    ['ADA', s.ada_compliant ? 'Compliant' : 'Not compliant']
  ].forEach(function (pair) {
    const box = document.createElement('div');
    box.className = 'stat';
    const label = document.createElement('span');
    label.textContent = pair[0];
    const value = document.createElement('strong');
    value.textContent = pair[1];
    box.appendChild(label);
    box.appendChild(value);
    statsRow.appendChild(box);
  });

  const cueList = document.getElementById('cueList');
  const cues = Array.isArray(ROUTE.cueSheet) ? ROUTE.cueSheet : [];
  if (!cues.length) {
    document.getElementById('cuePanel').style.display = 'none';
  } else {
    cues.forEach(function (cue) {
      const li = document.createElement('li');
      const dist = document.createElement('span');
      dist.className = 'cue-dist';
      const metres = Number(cue.distance_m || cue.cumulative_distance_m || 0);
      dist.textContent = Number.isFinite(metres) ? metres.toFixed(0) + ' m' : '';
      li.appendChild(dist);
      li.appendChild(document.createTextNode(
        cue.instruction || cue.text || cue.street_name || 'Continue'
      ));
      cueList.appendChild(li);
    });
  }

  if (coords.length < 2) return;

  // Cumulative distance and per-vertex slope, from the geometry itself.
  const R = 6371000;
  const rad = Math.PI / 180;
  const cum = [0];
  const slopes = [0];
  for (let i = 1; i < coords.length; i++) {
    const a = coords[i - 1];
    const b = coords[i];
    const meanLat = (a[1] + b[1]) * 0.5 * rad;
    const dx = (b[0] - a[0]) * rad * Math.cos(meanLat) * R;
    const dy = (b[1] - a[1]) * rad * R;
    const step = Math.sqrt(dx * dx + dy * dy);
    cum.push(cum[i - 1] + step);
    slopes.push(step > 0.01 ? ((b[2] - a[2]) / step) * 100 : 0);
  }
  const total = cum[cum.length - 1] || 1;

  function slopeColor(pct) {
    if (pct > 2) return '#ef4444';
    if (pct < -2) return '#22c55e';
    return '#94a3b8';
  }

  // -- plan view --------------------------------------------------------
  const plan = document.getElementById('planView');
  const W = 600, H = 280, PAD = 24;
  plan.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

  let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
  coords.forEach(function (c) {
    minLon = Math.min(minLon, c[0]); maxLon = Math.max(maxLon, c[0]);
    minLat = Math.min(minLat, c[1]); maxLat = Math.max(maxLat, c[1]);
  });
  const latScale = Math.cos(((minLat + maxLat) / 2) * rad) || 1;
  const spanX = Math.max((maxLon - minLon) * latScale, 1e-9);
  const spanY = Math.max(maxLat - minLat, 1e-9);
  const scale = Math.min((W - 2 * PAD) / spanX, (H - 2 * PAD) / spanY);
  const offX = (W - spanX * scale) / 2;
  const offY = (H - spanY * scale) / 2;

  function planX(lon) { return offX + (lon - minLon) * latScale * scale; }
  function planY(lat) { return H - offY - (lat - minLat) * scale; }

  for (let i = 1; i < coords.length; i++) {
    plan.appendChild(el('line', {
      x1: planX(coords[i - 1][0]), y1: planY(coords[i - 1][1]),
      x2: planX(coords[i][0]), y2: planY(coords[i][1]),
      stroke: slopeColor(slopes[i]), 'stroke-width': 3, 'stroke-linecap': 'round'
    }));
  }
  [[coords[0], '#22c55e', 'A'], [coords[coords.length - 1], '#ef4444', 'B']]
    .forEach(function (marker) {
      plan.appendChild(el('circle', {
        cx: planX(marker[0][0]), cy: planY(marker[0][1]), r: 6,
        fill: marker[1], stroke: '#0b1220', 'stroke-width': 2
      }));
      const label = el('text', {
        x: planX(marker[0][0]), y: planY(marker[0][1]) - 11,
        fill: '#e6edf7', 'font-size': 12, 'text-anchor': 'middle'
      });
      label.textContent = marker[2];
      plan.appendChild(label);
    });
  const planMarker = el('circle', { cx: planX(coords[0][0]), cy: planY(coords[0][1]), r: 5,
    fill: accent, stroke: '#0b1220', 'stroke-width': 2 });
  plan.appendChild(planMarker);

  // -- longitudinal profile --------------------------------------------
  const prof = document.getElementById('profileView');
  prof.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  let minZ = Infinity, maxZ = -Infinity;
  coords.forEach(function (c) { minZ = Math.min(minZ, c[2]); maxZ = Math.max(maxZ, c[2]); });
  if (!(maxZ > minZ)) { maxZ = minZ + 1; }

  function profX(d) { return PAD + (d / total) * (W - 2 * PAD); }
  function profY(z) { return H - PAD - ((z - minZ) / (maxZ - minZ)) * (H - 2 * PAD); }

  let area = 'M ' + profX(0) + ' ' + (H - PAD);
  coords.forEach(function (c, i) { area += ' L ' + profX(cum[i]) + ' ' + profY(c[2]); });
  area += ' L ' + profX(total) + ' ' + (H - PAD) + ' Z';
  prof.appendChild(el('path', { d: area, fill: accent, 'fill-opacity': 0.18 }));

  for (let i = 1; i < coords.length; i++) {
    prof.appendChild(el('line', {
      x1: profX(cum[i - 1]), y1: profY(coords[i - 1][2]),
      x2: profX(cum[i]), y2: profY(coords[i][2]),
      stroke: slopeColor(slopes[i]), 'stroke-width': 2.5
    }));
  }
  [minZ, maxZ].forEach(function (z) {
    prof.appendChild(el('line', {
      x1: PAD, y1: profY(z), x2: W - PAD, y2: profY(z),
      stroke: '#24314b', 'stroke-width': 1, 'stroke-dasharray': '4 4'
    }));
    const t = el('text', { x: 4, y: profY(z) + 4, fill: '#94a3b8', 'font-size': 11 });
    t.textContent = z.toFixed(0) + ' m';
    prof.appendChild(t);
  });
  const needle = el('line', { x1: profX(0), y1: PAD, x2: profX(0), y2: H - PAD,
    stroke: accent, 'stroke-width': 1.5 });
  prof.appendChild(needle);

  // -- scrubber ---------------------------------------------------------
  const scrubber = document.getElementById('scrubber');
  const readout = document.getElementById('readout');

  function update(fraction) {
    const target = fraction * total;
    let i = 1;
    while (i < cum.length - 1 && cum[i] < target) i++;
    const span = cum[i] - cum[i - 1] || 1;
    const t = Math.max(0, Math.min(1, (target - cum[i - 1]) / span));
    const lon = coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * t;
    const lat = coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * t;
    const z = coords[i - 1][2] + (coords[i][2] - coords[i - 1][2]) * t;

    planMarker.setAttribute('cx', planX(lon));
    planMarker.setAttribute('cy', planY(lat));
    needle.setAttribute('x1', profX(target));
    needle.setAttribute('x2', profX(target));
    readout.textContent =
      (target / 1000).toFixed(2) + ' km / ' + z.toFixed(1) + ' m / ' +
      slopes[i].toFixed(1) + '%';
  }

  scrubber.addEventListener('input', function () { update(this.value / 1000); });
  update(0);
})();
"""
