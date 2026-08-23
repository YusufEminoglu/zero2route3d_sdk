"""OpenStreetMap XYZ tile basemap loader for 02Route 3D."""

from __future__ import annotations

from typing import Any, Tuple

OSM_BASEMAP_NAME = "OpenStreetMap Standard"
OSM_BASEMAP_PROPERTY = "zero2route3d/osm_basemap"
OSM_BASEMAP_URI = (
    "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmin=0&zmax=19&crs=EPSG3857"
)
OSM_ATTRIBUTION = "© OpenStreetMap contributors"


def add_osm_basemap(project: Any = None) -> Tuple[Any, bool]:
    """Add or reveal the standard OSM XYZ layer.

    Returns the layer and a boolean indicating whether a new layer was created.
    """
    from qgis.core import QgsProject, QgsRasterLayer

    target = project or QgsProject.instance()
    for layer in target.mapLayers().values():
        if layer.customProperty(OSM_BASEMAP_PROPERTY, False):
            layer_tree = target.layerTreeRoot().findLayer(layer.id())
            if layer_tree is not None:
                layer_tree.setItemVisibilityChecked(True)
            return layer, False

    layer = QgsRasterLayer(OSM_BASEMAP_URI, OSM_BASEMAP_NAME, "wms")
    if not layer.isValid():
        raise ValueError("QGIS could not create the OpenStreetMap basemap.")
    layer.setCustomProperty(OSM_BASEMAP_PROPERTY, True)
    layer.setCustomProperty("zero2route3d/attribution", OSM_ATTRIBUTION)
    if hasattr(layer, "serverProperties") and layer.serverProperties() is not None:
        layer.serverProperties().setAttribution(OSM_ATTRIBUTION)
        layer.serverProperties().setAttributionUrl("https://www.openstreetmap.org/copyright")
    else:
        layer.setAttribution(OSM_ATTRIBUTION)
        layer.setAttributionUrl("https://www.openstreetmap.org/copyright")
    target.addMapLayer(layer, False)
    # Insert at the bottom of the layer tree
    target.layerTreeRoot().insertLayer(len(target.layerTreeRoot().children()), layer)
    return layer, True
