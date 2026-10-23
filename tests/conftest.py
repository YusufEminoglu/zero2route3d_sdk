"""Pytest configuration for the zero2route3d-sdk test-suite.

Some Windows machines expose a process-wide ``PROJ_LIB`` (or ``PROJ_DATA``)
pointing at a PostGIS ``proj`` directory that does not contain a usable
``proj.db``. GDAL, and therefore rasterio/pyproj, then cannot resolve any EPSG
code, which makes the GeoTIFF sampling tests fail for reasons that have nothing
to do with the SDK.

When the configured PROJ directory is missing its database, this module points
PROJ at the database bundled with the installed rasterio wheel before any test
module imports rasterio. When rasterio is not installed, or its bundled data is
also missing, nothing is changed and the rasterio tests skip as usual.
"""

from __future__ import annotations

import os
from pathlib import Path


def _has_proj_database(directory: str | None) -> bool:
    """Return True when ``directory`` contains a usable ``proj.db``."""
    return bool(directory) and (Path(directory) / "proj.db").is_file()


def _repair_proj_data() -> None:
    """Point PROJ at rasterio's bundled database when the configured one is broken."""
    if _has_proj_database(os.environ.get("PROJ_LIB")) or _has_proj_database(
        os.environ.get("PROJ_DATA")
    ):
        return

    try:
        import rasterio
    except ImportError:
        return

    bundled = Path(rasterio.__file__).resolve().parent / "proj_data"
    if _has_proj_database(str(bundled)):
        os.environ["PROJ_LIB"] = str(bundled)
        os.environ["PROJ_DATA"] = str(bundled)


_repair_proj_data()
