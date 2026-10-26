"""Tests for the QGIS-independent parts of the OSM styling module."""

from __future__ import annotations

import unittest

from zero2route3d import osm_styling


class TestOsmStylingHelpers(unittest.TestCase):
    def test_theme_catalog_and_fallback(self) -> None:
        themes = osm_styling.list_osm_themes()
        self.assertEqual(len(themes), len(osm_styling.OSM_THEMES))
        self.assertIn(osm_styling.DEFAULT_THEME, dict(themes))
        self.assertIs(osm_styling.get_theme_palette("missing"), osm_styling.OSM_THEMES["atlas"])
        for key, _label in themes:
            palette = osm_styling.get_theme_palette(key)
            self.assertIn("other", palette["buildings"])

    def test_shade_darkens_lightens_and_ignores_non_hex(self) -> None:
        self.assertEqual(osm_styling._shade("#808080", 0.5), "#404040")
        self.assertEqual(osm_styling._shade("#000000", 1.5), "#808080")
        self.assertEqual(osm_styling._shade("#123456", 1.0), "#123456")
        self.assertEqual(osm_styling._shade("#000000", 9.0), "#ffffff")
        self.assertEqual(osm_styling._shade("red", 0.5), "red")

    def test_apply_style_without_qgis_reports_failure(self) -> None:
        class FakeLayer:
            def geometryType(self) -> int:
                return 2

        self.assertFalse(osm_styling.apply_osm_atlas_style(FakeLayer()))


if __name__ == "__main__":
    unittest.main()
