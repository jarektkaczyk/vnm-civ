"""OpenStreetMap land polygons (osmdata.openstreetmap.de, split, WGS 84): the land mask and the coastline as they are
today, reclaimed land, ports and new islands included.

The world file is a zipped shapefile of small polygons (large ones are split on a grid). The .shp member is read as
a stream; only the polygons whose bounding box meets the map window are kept.
"""

from __future__ import annotations

import struct
import zipfile

from ..core.geo import VN_LAT, VN_LON
from ..core.source import Source, SourceInfo

URL = "https://osmdata.openstreetmap.de/download/land-polygons-split-4326.zip"
FILE = "land-polygons-split-4326.zip"
PAD = 0.3
BBOX = (VN_LON[0] - PAD, VN_LAT[0] - PAD, VN_LON[1] + PAD, VN_LAT[1] + PAD)


def read_polygons(stream, bbox) -> list[list[list[tuple[float, float]]]]:
    """Polygons (lists of rings) of a .shp stream whose record bounding box meets `bbox`."""
    head = stream.read(100)
    if struct.unpack(">i", head[:4])[0] != 9994:
        raise ValueError("not a shapefile")
    x0, y0, x1, y1 = bbox
    out = []
    while True:
        rh = stream.read(8)
        if len(rh) < 8:
            break
        _, length = struct.unpack(">ii", rh)
        body = stream.read(length * 2)
        if len(body) < 36 or struct.unpack("<i", body[:4])[0] != 5:
            continue
        bx0, by0, bx1, by1 = struct.unpack("<4d", body[4:36])
        if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
            continue
        nparts, npts = struct.unpack("<2i", body[36:44])
        parts = list(struct.unpack(f"<{nparts}i", body[44:44 + 4 * nparts])) + [npts]
        base = 44 + 4 * nparts
        coords = struct.unpack(f"<{2 * npts}d", body[base:base + 16 * npts])
        rings = []
        for a, b in zip(parts, parts[1:]):
            rings.append([(round(coords[2 * k], 6), round(coords[2 * k + 1], 6)) for k in range(a, b)])
        out.append(rings)
    return out


class VnOsmLand(Source):
    info = SourceInfo(
        id="vn_osm_land",
        title="OpenStreetMap land polygons (split, WGS 84)",
        publisher="OpenStreetMap contributors, processed by osmdata.openstreetmap.de (FOSSGIS)",
        homepage="https://osmdata.openstreetmap.de/data/land-polygons.html",
        license="ODbL 1.0. Map data (c) OpenStreetMap contributors",
        description="The land of the world as OpenStreetMap maps its coastline today, reclaimed land and new "
        "islands included. It decides which hexes are land and gives the coastline drawn over the hexes when the "
        "map is zoomed in.",
        used_for=["Land and sea of every hex", "The coastline at close zoom"],
    )

    def fetch(self, force=False):
        self.download(URL, FILE, force=force, expect_binary=True)

    def process(self):
        with zipfile.ZipFile(self.raw_dir / FILE) as z:
            name = next(n for n in z.namelist() if n.endswith(".shp"))
            info = z.getinfo(name)
            with z.open(name) as stream:
                polys = read_polygons(stream, BBOX)
        stamp = "%04d-%02d-%02d" % info.date_time[:3]
        print(f"    {len(polys)} land polygons in the window (file of {stamp})")
        return {"vintage": f"OSM land polygons of {stamp}", "_files": [FILE], "date": stamp, "polygons": polys}
