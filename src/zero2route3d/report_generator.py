"""Publication-grade HTML Analytical Scorecard and Route Report Generator."""

from __future__ import annotations

from pathlib import Path

from .routing_engine import RouteResult3D
from .solar_shadow import compute_shade_exposure_along_route


def generate_analytical_report_html(
    result: RouteResult3D,
    target_path: Path,
    report_title: str = "02Route 3D Analytical Scorecard",
) -> None:
    """Generate a self-contained, publication-grade HTML audit scorecard for a 3D route."""
    stats = result.statistics
    prof = result.profile
    coords = result.coordinates_3d
    shade_rep = compute_shade_exposure_along_route(coords)

    # Build Elevation SVG Chart
    width = 720
    height = 180
    elevations = [c[2] for c in coords] if coords else [0.0]
    min_ele = min(elevations)
    max_ele = max(elevations)
    ele_range = max(1.0, max_ele - min_ele)

    points_svg = []
    for i, c in enumerate(coords):
        x = (i / max(1, len(coords) - 1)) * (width - 60) + 40
        y = height - 30 - ((c[2] - min_ele) / ele_range) * (height - 60)
        points_svg.append(f"{x:.1f},{y:.1f}")

    path_d = "M " + " L ".join(points_svg) if points_svg else "M 0,0"
    fill_d = f"{path_d} L {width - 20},{height - 30} L 40,{height - 30} Z"

    # Slope distribution rows
    slope_rows = "".join(
        f"<tr><td><strong>{k.replace('_', ' ').capitalize()}</strong></td><td>{v:.1f}%</td>"
        f"<td><div style='background: #0284c7; height: 12px; width: {v * 2.5:.0f}px; border-radius: 3px;'></div></td></tr>"
        for k, v in stats.slope_distribution.items()
    )

    # Cue sheet rows
    cue_rows = "".join(
        f"<tr><td>{c.step_number}</td><td><strong>{c.direction.capitalize()}</strong></td>"
        f"<td>{c.distance_m:.0f} m</td><td>{c.elevation_delta_m:+.1f} m</td>"
        f"<td style='color: {'#ef4444' if abs(c.slope_pct) > 10 else '#38bdf8'};'>{c.slope_pct:.1f}%</td>"
        f"<td>{c.instruction}</td></tr>"
        for c in stats.cue_sheet
    )

    ada_badge = (
        '<span style="background: #10b981; color: white; padding: 4px 10px; border-radius: 4px; font-weight: 700;">PASSED (100% Barrier-Free)</span>'
        if stats.ada_compliant
        else f'<span style="background: #ef4444; color: white; padding: 4px 10px; border-radius: 4px; font-weight: 700;">VIOLATIONS ({stats.ada_violations_count} sections > 8.33%)</span>'
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{report_title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0b1120; color: #f8fafc; margin: 0; padding: 32px; line-height: 1.6; }}
    .container {{ max-width: 900px; margin: 0 auto; background: #1e293b; border-radius: 12px; border: 1px solid #334155; padding: 28px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
    h1, h2, h3 {{ color: #38bdf8; margin-top: 0; }}
    .header-bar {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #38bdf8; padding-bottom: 16px; margin-bottom: 24px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 28px; }}
    .kpi-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 14px; text-align: center; }}
    .kpi-label {{ font-size: 11px; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.5px; }}
    .kpi-value {{ font-size: 20px; font-weight: 800; color: #38bdf8; margin-top: 4px; }}
    .section-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 18px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ padding: 9px 12px; border: 1px solid #334155; text-align: left; font-size: 13px; }}
    th {{ background: #1e293b; color: #38bdf8; }}
    tr:nth-child(even) {{ background: #182234; }}
    svg {{ width: 100%; height: 180px; display: block; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header-bar">
      <div>
        <h1>{report_title}</h1>
        <div style="color: #94a3b8; font-size: 13px;">Profile: <strong>{prof.name}</strong> ({prof.category.capitalize()}) &bull; Cruising Speed: <strong>{prof.base_speed_kmh} km/h</strong></div>
      </div>
      <div>
        <span style="background: #0284c7; color: white; padding: 6px 12px; border-radius: 6px; font-weight: 700; font-size: 12px;">02ROUTE 3D</span>
      </div>
    </div>

    <!-- KPI Grid -->
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-label">Distance</div><div class="kpi-value">{stats.total_distance_km} km</div></div>
      <div class="kpi-card"><div class="kpi-label">Duration</div><div class="kpi-value">{stats.total_duration_min} min</div></div>
      <div class="kpi-card"><div class="kpi-label">Total Climb</div><div class="kpi-value">+{stats.elevation_gain_m:.1f} m</div></div>
      <div class="kpi-card"><div class="kpi-label">Calories</div><div class="kpi-value">{stats.total_calories_kcal:.0f} kcal</div></div>
    </div>

    <!-- Elevation Profile Section -->
    <div class="section-card">
      <h2>Longitudinal Elevation Profile</h2>
      <svg viewBox="0 0 {width} {height}">
        <defs>
          <linearGradient id="svgGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.5"/>
            <stop offset="100%" stop-color="#0284c7" stop-opacity="0.0"/>
          </linearGradient>
        </defs>
        <path d="{fill_d}" fill="url(#svgGrad)"/>
        <path d="{path_d}" fill="none" stroke="#38bdf8" stroke-width="3"/>
        <text x="40" y="20" fill="#94a3b8" font-size="11" font-weight="600">{max_ele:.1f} m</text>
        <text x="40" y="{height - 10}" fill="#94a3b8" font-size="11" font-weight="600">{min_ele:.1f} m</text>
      </svg>
    </div>

    <!-- Slope & Accessibility Section -->
    <div class="section-card">
      <h2>Slope Distribution & Accessibility Audit</h2>
      <div style="margin-bottom: 12px;">
        <strong>ADA 1:12 Barrier-Free Standard:</strong> {ada_badge}
      </div>
      <table>
        <thead><tr><th>Slope Category</th><th>Coverage (%)</th><th>Visual Bar</th></tr></thead>
        <tbody>{slope_rows}</tbody>
      </table>
    </div>

    <!-- Microclimate & Solar Shade Section -->
    <div class="section-card">
      <h2>Microclimate & Solar Shade Exposure</h2>
      <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 12px;">
        <div class="kpi-card"><div class="kpi-label">Direct Sun</div><div class="kpi-value">{shade_rep.direct_sun_pct:.1f}%</div></div>
        <div class="kpi-card"><div class="kpi-label">Shaded Area</div><div class="kpi-value">{shade_rep.shaded_pct:.1f}%</div></div>
        <div class="kpi-card"><div class="kpi-label">Thermal Rating</div><div class="kpi-value" style="font-size: 14px;">{shade_rep.comfort_category}</div></div>
      </div>
    </div>

    <!-- Turn-by-Turn Cue Sheet Section -->
    <div class="section-card">
      <h2>Turn-by-Turn Navigational Cue Sheet</h2>
      <table>
        <thead><tr><th>#</th><th>Direction</th><th>Distance</th><th>Elev Δ</th><th>Slope</th><th>Instruction</th></tr></thead>
        <tbody>{cue_rows}</tbody>
      </table>
    </div>
  </div>
</body>
</html>"""

    target_path.write_text(html_content, encoding="utf-8")
