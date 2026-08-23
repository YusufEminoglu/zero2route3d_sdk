"""Native QGIS cartographic styling inspired by the 02Agent OSM Downloader palette suite."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

OSM_THEMES: Dict[str, dict] = {
    "atlas": {
        "label": "Civic Atlas",
        "description": "Clean, legible civic cartography for general urban mobility planning.",
        "bg": "#f7f8f2",
        "base": "#566b6f",
        "roads_major": "#2f4858",
        "roads_minor": "#d8d7ce",
        "greens": "#7fb069",
        "water": "#3a86b5",
        "trees": "#3f7d4e",
        "buildings": {
            "residential": "#d9c8b4",
            "commercial": "#a9bdd0",
            "industrial": "#c4b79a",
            "civic": "#b8d5ce",
            "worship": "#d9c7df",
            "other": "#cfd0c8",
        },
    },
    "cyber": {
        "label": "Tokyo Cyber",
        "description": "High-contrast dark neon tones for striking network and mobility maps.",
        "bg": "#0a0b10",
        "base": "#121420",
        "roads_major": "#ff0055",
        "roads_minor": "#1a1d36",
        "greens": "#082c2b",
        "water": "#00ffcc",
        "trees": "#00ff66",
        "buildings": {
            "residential": "#bc39fa",
            "commercial": "#ff8800",
            "industrial": "#ffdd00",
            "civic": "#00aaff",
            "worship": "#00ff66",
            "other": "#ff007f",
        },
    },
    "paper": {
        "label": "Editorial Paper",
        "description": "Warm ink-and-parchment tones for high-end master plan publications.",
        "bg": "#fdfbf7",
        "base": "#e6dfd3",
        "roads_major": "#7c5c43",
        "roads_minor": "#eadecc",
        "greens": "#c2c5aa",
        "water": "#9ab8c2",
        "trees": "#6b705c",
        "buildings": {
            "residential": "#ebd4c0",
            "commercial": "#c4d1db",
            "industrial": "#dbcfb8",
            "civic": "#cfdcd5",
            "worship": "#e8dfeb",
            "other": "#dcd8d3",
        },
    },
    "frost": {
        "label": "Nordic Frost",
        "description": "Cool minimal scandinavian tones with crisp glacier blue accents.",
        "bg": "#f5f7fa",
        "base": "#d8dee9",
        "roads_major": "#4c566a",
        "roads_minor": "#e5e9f0",
        "greens": "#a3be8c",
        "water": "#88c0d0",
        "trees": "#4c566a",
        "buildings": {
            "residential": "#d8dee9",
            "commercial": "#81a1c1",
            "industrial": "#4c566a",
            "civic": "#88c0d0",
            "worship": "#b48ead",
            "other": "#e5e9f0",
        },
    },
    "noir": {
        "label": "Monochrome Noir",
        "description": "Architectural high-contrast grayscale scheme for structural massing.",
        "bg": "#1e1e1e",
        "base": "#121212",
        "roads_major": "#ffffff",
        "roads_minor": "#2e2e2e",
        "greens": "#262626",
        "water": "#3a3a3a",
        "trees": "#5c5c5c",
        "buildings": {
            "residential": "#404040",
            "commercial": "#808080",
            "industrial": "#2a2a2a",
            "civic": "#a0a0a0",
            "worship": "#c0c0c0",
            "other": "#606060",
        },
    },
    "mediterranean": {
        "label": "Mediterranean Survey",
        "description": "Sun, terracotta and deep azure tones for coastal urban morphology.",
        "bg": "#fbf4e6",
        "base": "#8a7a5a",
        "roads_major": "#c65f46",
        "roads_minor": "#eadfc9",
        "greens": "#86a873",
        "water": "#4fa6c6",
        "trees": "#4e7f55",
        "buildings": {
            "residential": "#e7c7aa",
            "commercial": "#b8cad8",
            "industrial": "#d4b98d",
            "civic": "#c8d9c9",
            "worship": "#ddc2d9",
            "other": "#d8cfc1",
        },
    },
    "nightprint": {
        "label": "Night Print",
        "description": "Deep obsidian backdrop with warm amber arterial transit highlights.",
        "bg": "#11161a",
        "base": "#1b2628",
        "roads_major": "#ffd166",
        "roads_minor": "#2d3a3f",
        "greens": "#2a6f58",
        "water": "#118ab2",
        "trees": "#5fbf7a",
        "buildings": {
            "residential": "#7d8da1",
            "commercial": "#f4a261",
            "industrial": "#a7a16d",
            "civic": "#74c0c2",
            "worship": "#b28fd8",
            "other": "#98a0a6",
        },
    },
    "default": {
        "label": "Muted Planning",
        "description": "Quiet everyday planning tones for comprehensive urban analytics.",
        "bg": "#ffffff",
        "base": "#5e7274",
        "roads_major": "#e1846f",
        "roads_minor": "#eae5da",
        "greens": "#a9c08a",
        "water": "#a5c9eb",
        "trees": "#6f9e5c",
        "buildings": {
            "residential": "#d8c3b1",
            "commercial": "#b7c2d0",
            "industrial": "#c6b9a4",
            "civic": "#cdd6d2",
            "worship": "#d8cfe2",
            "other": "#cac5bf",
        },
    },
}

DEFAULT_THEME = "atlas"


def list_osm_themes() -> List[Tuple[str, str]]:
    """Return list of (theme_key, display_label) tuples for all 8 cartographic styles."""
    return [(k, v["label"]) for k, v in OSM_THEMES.items()]


def get_theme_palette(theme_key: str = "atlas") -> dict:
    """Retrieve theme dictionary by key with fallback to atlas."""
    return OSM_THEMES.get(theme_key, OSM_THEMES["atlas"])


def _shade(color: str, factor: float) -> str:
    if not (color.startswith("#") and len(color) == 7):
        return color
    rgb = [int(color[index : index + 2], 16) for index in (1, 3, 5)]
    if factor <= 1.0:
        values = [round(value * factor) for value in rgb]
    else:
        amount = min(1.0, factor - 1.0)
        values = [round(value + (255 - value) * amount) for value in rgb]
    return "#%02x%02x%02x" % tuple(values)


def _fill(color: str, opacity: float = 0.82) -> Any:
    from qgis.core import QgsFillSymbol

    symbol = QgsFillSymbol.createSimple(
        {
            "color": color,
            "outline_color": _shade(color, 0.72),
            "outline_width": "0.18",
            "style": "solid",
        }
    )
    symbol.setOpacity(opacity)
    return symbol


def _line(color: str, width: float, dashed: bool = False) -> Any:
    from qgis.core import QgsLineSymbol

    properties = {
        "color": color,
        "width": str(width),
        "capstyle": "round",
        "joinstyle": "round",
    }
    if dashed:
        properties["line_style"] = "dash"
    return QgsLineSymbol.createSimple(properties)


def _renderer(expression: str, entries: Any) -> Any:
    from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory

    return QgsCategorizedSymbolRenderer(
        expression,
        [QgsRendererCategory(value, symbol, label) for value, label, symbol in entries],
    )


def _building_renderer(theme: dict) -> Any:
    colors = theme["buildings"]
    expression = (
        "CASE"
        " WHEN lower(coalesce(\"building\",'')) IN ('apartments','residential','house','detached','terrace','dormitory','bungalow','semidetached_house','hut') THEN 'building_residential'"
        " WHEN lower(coalesce(\"building\",'')) IN ('commercial','retail','office','supermarket','kiosk','hotel') THEN 'building_commercial'"
        " WHEN lower(coalesce(\"building\",'')) IN ('industrial','warehouse','manufacture','hangar','factory') THEN 'building_industrial'"
        " WHEN lower(coalesce(\"building\",'')) IN ('church','mosque','temple','synagogue','cathedral','chapel') THEN 'building_worship'"
        " WHEN coalesce(\"building\",'') <> '' THEN 'building_civic'"
        " WHEN lower(coalesce(\"type\",'')) IN ('commercial','retail','office') THEN 'building_commercial'"
        " WHEN lower(coalesce(\"type\",'')) IN ('industrial','warehouse') THEN 'building_industrial'"
        " ELSE 'building_other' END"
    )
    labels = {
        "residential": "Residential buildings",
        "commercial": "Commercial buildings",
        "industrial": "Industrial buildings",
        "civic": "Civic buildings",
        "worship": "Worship buildings",
    }
    entries = [
        (f"building_{key}", labels[key], _fill(color))
        for key, color in colors.items()
        if key != "other"
    ]
    entries.append(("building_other", "Other buildings", _fill(colors["other"], 0.66)))
    return _renderer(expression, entries)


def _road_renderer(theme: dict) -> Any:
    major = theme["roads_major"]
    minor = theme["roads_minor"]
    greens = theme["greens"]
    base = theme["base"]
    expression = (
        "CASE"
        " WHEN lower(coalesce(\"highway\",'')) IN ('motorway','trunk','motorway_link','trunk_link') THEN 'major'"
        " WHEN lower(coalesce(\"highway\",'')) IN ('primary','primary_link') THEN 'primary'"
        " WHEN lower(coalesce(\"highway\",'')) IN ('secondary','secondary_link') THEN 'secondary'"
        " WHEN lower(coalesce(\"highway\",'')) IN ('tertiary','tertiary_link') THEN 'tertiary'"
        " WHEN lower(coalesce(\"highway\",'')) IN ('residential','unclassified','living_street','road') THEN 'residential'"
        " WHEN lower(coalesce(\"highway\",'')) IN ('service','track') THEN 'service'"
        " WHEN lower(coalesce(\"highway\",'')) IN ('footway','path','pedestrian','steps','corridor','bridleway','cycleway') THEN 'active'"
        " WHEN lower(coalesce(\"type\",'')) IN ('primary','secondary','tertiary') THEN lower(\"type\")"
        " ELSE 'other' END"
    )
    widths = {
        "major": 1.55,
        "primary": 1.28,
        "secondary": 1.05,
        "tertiary": 0.82,
        "residential": 0.66,
        "service": 0.48,
        "active": 0.55,
        "other": 0.58,
    }
    entries = [
        ("major", "Motorway and trunk", _line(major, widths["major"])),
        ("primary", "Primary roads", _line(major, widths["primary"])),
        ("secondary", "Secondary roads", _line(major, widths["secondary"])),
        ("tertiary", "Tertiary roads", _line(major, widths["tertiary"])),
        ("residential", "Residential roads", _line(minor, widths["residential"])),
        ("service", "Service roads", _line(minor, widths["service"])),
        ("active", "Walking and cycling", _line(greens, widths["active"], True)),
        ("other", "Other lines", _line(base, widths["other"])),
    ]
    return _renderer(expression, entries)


def _point_renderer(theme: dict) -> Any:
    from qgis.core import QgsMarkerSymbol, QgsSingleSymbolRenderer

    tree_color = theme.get("trees", "#16a34a")
    sym = QgsMarkerSymbol.createSimple(
        {
            "name": "circle",
            "color": tree_color,
            "outline_color": "#ffffff",
            "outline_width": "0.4",
            "size": "3.5",
        }
    )
    return QgsSingleSymbolRenderer(sym)


def apply_osm_theme_style(layer: Any, theme_key: str = "atlas") -> bool:
    """Apply any of the 8 02Agent OSM Downloader visual themes to a vector layer."""
    try:
        geometry_type = int(layer.geometryType())
        from qgis.core import QgsWkbTypes

        theme = get_theme_palette(theme_key)

        if geometry_type == int(QgsWkbTypes.PolygonGeometry):
            renderer = _building_renderer(theme)
        elif geometry_type == int(QgsWkbTypes.LineGeometry):
            renderer = _road_renderer(theme)
        elif geometry_type == int(QgsWkbTypes.PointGeometry):
            renderer = _point_renderer(theme)
        else:
            return False

        layer.setRenderer(renderer)
        layer.setCustomProperty("zero2route3d/style", f"02Agent OSM Downloader — {theme['label']}")
        layer.setCustomProperty("zero2route3d/theme_key", theme_key)
        layer.triggerRepaint()
        return True
    except Exception:
        return False


def apply_osm_atlas_style(layer: Any) -> bool:
    """Backwards-compatible convenience helper applying Civic Atlas style."""
    return apply_osm_theme_style(layer, "atlas")


__all__ = [
    "OSM_THEMES",
    "DEFAULT_THEME",
    "list_osm_themes",
    "get_theme_palette",
    "apply_osm_theme_style",
    "apply_osm_atlas_style",
]
