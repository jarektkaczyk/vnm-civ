"""Small, dependency-free geometry helpers.

Everything on the map lives in "map km": an Albers equal-area projection of
Vietnam (standard parallels 10 and 20 N, centre 15 N 106 E), shifted so the
top-left of the map is (0, 0) and y points *down* (like screen coordinates).
Both the hex grid and the browser use this space (web/js/render/art/terrain.js
keeps a copy of the projection constants).
"""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from typing import IO, Iterable, Iterator

R_EARTH_KM = 6371.0088

# Map window (lon/lat): Vietnam with the Hoang Sa and Truong Sa archipelagos, a margin of its neighbours and the
# East Sea (docs/BLUEPRINT.md section 4).
VN_LON = (101.9, 116.2)
VN_LAT = (6.8, 23.6)
VN_ALBERS = {"lat1": 10.0, "lat2": 20.0, "lat0": 15.0, "lon0": 106.0}


class Albers:
    """Albers equal-area conic (spherical). Defaults are the vn-civ parameters for Vietnam."""

    def __init__(self, lat1=10.0, lat2=20.0, lat0=15.0, lon0=106.0):
        p1, p2, p0 = map(math.radians, (lat1, lat2, lat0))
        self.lon0 = math.radians(lon0)
        self.n = (math.sin(p1) + math.sin(p2)) / 2
        self.c = math.cos(p1) ** 2 + 2 * self.n * math.sin(p1)
        self.rho0 = R_EARTH_KM * math.sqrt(self.c - 2 * self.n * math.sin(p0)) / self.n

    def __call__(self, lon: float, lat: float) -> tuple[float, float]:
        rho = R_EARTH_KM * math.sqrt(self.c - 2 * self.n * math.sin(math.radians(lat))) / self.n
        theta = self.n * (math.radians(lon) - self.lon0)
        return rho * math.sin(theta), self.rho0 - rho * math.cos(theta)

    def inverse(self, x: float, y: float) -> tuple[float, float]:
        """Albers km -> (lon, lat)."""
        dy = self.rho0 - y
        rho = math.hypot(x, dy)
        theta = math.atan2(x, dy)
        s = (self.c - (rho * self.n / R_EARTH_KM) ** 2) / (2 * self.n)
        return math.degrees(self.lon0 + theta / self.n), math.degrees(math.asin(max(-1.0, min(1.0, s))))


class AlbersEllipsoid:
    """Ellipsoidal Albers equal-area (Snyder 1987, eqs. 14-3..14-6), output in metres.

    Defaults are EPSG:5070 (NAD83 / Conus Albers): GRS80, lat0 23, lon0 -96,
    standard parallels 29.5 and 45.5. Used to look up rasters such as NLCD.
    """

    def __init__(self, lat1=29.5, lat2=45.5, lat0=23.0, lon0=-96.0, a=6378137.0, inv_f=298.257222101):
        f = 1 / inv_f
        self.a = a
        self.e2 = f * (2 - f)
        self.e = math.sqrt(self.e2)
        self.lon0 = math.radians(lon0)
        p1, p2, p0 = map(math.radians, (lat1, lat2, lat0))
        m1, m2 = self._m(p1), self._m(p2)
        q1, q2, q0 = self._q(p1), self._q(p2), self._q(p0)
        self.n = (m1 * m1 - m2 * m2) / (q2 - q1)
        self.c = m1 * m1 + self.n * q1
        self.rho0 = a * math.sqrt(self.c - self.n * q0) / self.n

    def _m(self, phi: float) -> float:
        s = math.sin(phi)
        return math.cos(phi) / math.sqrt(1 - self.e2 * s * s)

    def _q(self, phi: float) -> float:
        s, e = math.sin(phi), self.e
        return (1 - self.e2) * (s / (1 - self.e2 * s * s) - math.log((1 - e * s) / (1 + e * s)) / (2 * e))

    def __call__(self, lon: float, lat: float) -> tuple[float, float]:
        rho = self.a * math.sqrt(self.c - self.n * self._q(math.radians(lat))) / self.n
        theta = self.n * (math.radians(lon) - self.lon0)
        return rho * math.sin(theta), self.rho0 - rho * math.cos(theta)


@dataclass
class MapProjection:
    """lon/lat -> map km (origin top-left, y down)."""

    min_x: float
    max_y: float
    margin: float

    def __post_init__(self):
        self._albers = Albers()

    def __call__(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = self._albers(lon, lat)
        return x - self.min_x + self.margin, self.max_y - y + self.margin

    def inverse(self, x: float, y: float) -> tuple[float, float]:
        """map km -> (lon, lat)."""
        return self._albers.inverse(x + self.min_x - self.margin, self.max_y + self.margin - y)

    def to_dict(self) -> dict:
        return {"min_x": self.min_x, "max_y": self.max_y, "margin": self.margin}


def ring_contains(ring: list[tuple[float, float]], x: float, y: float) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


class Shape:
    """A (multi)polygon as a bag of rings; even-odd rule handles holes."""

    def __init__(self, rings: Iterable[list[tuple[float, float]]]):
        self.rings = [r for r in rings if len(r) >= 3]
        xs = [p[0] for r in self.rings for p in r] or [0]
        ys = [p[1] for r in self.rings for p in r] or [0]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))

    def contains(self, x: float, y: float) -> bool:
        x0, y0, x1, y1 = self.bbox
        if x < x0 or x > x1 or y < y0 or y > y1:
            return False
        inside = False
        for r in self.rings:
            if ring_contains(r, x, y):
                inside = not inside
        return inside


class ShapeIndex:
    """Bucket shapes by coarse grid square so point lookups only test a few shapes."""

    def __init__(self, shapes: list[Shape], cell_km: float = 100.0):
        self.shapes = shapes
        self.cell = cell_km
        self.buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
        for k, s in enumerate(shapes):
            x0, y0, x1, y1 = s.bbox
            for gx in range(int(x0 // cell_km), int(x1 // cell_km) + 1):
                for gy in range(int(y0 // cell_km), int(y1 // cell_km) + 1):
                    self.buckets[(gx, gy)].append(k)

    def locate(self, x: float, y: float) -> int:
        for k in self.buckets.get((int(x // self.cell), int(y // self.cell)), ()):
            if self.shapes[k].contains(x, y):
                return k
        return -1


# --- file formats -----------------------------------------------------------

KML_NS = "{http://www.opengis.net/kml/2.2}"


def read_kml_placemarks(fileobj: IO[bytes]) -> Iterator[tuple[dict, list[list[tuple[float, float]]]]]:
    """Yield (properties, rings) for each Placemark in a Census cartographic KML."""
    for _, el in ET.iterparse(fileobj):
        if el.tag != KML_NS + "Placemark":
            continue
        props = {sd.get("name"): (sd.text or "") for sd in el.iter(KML_NS + "SimpleData")}
        rings = []
        for coords in el.iter(KML_NS + "coordinates"):
            pts = []
            for tok in (coords.text or "").split():
                lon, lat = tok.split(",")[:2]
                pts.append((round(float(lon), 5), round(float(lat), 5)))
            rings.append(pts)
        yield props, rings
        el.clear()


def geojson_rings(geom: dict) -> list[list[tuple[float, float]]]:
    t, c = geom["type"], geom["coordinates"]
    polys = [c] if t == "Polygon" else c if t == "MultiPolygon" else []
    return [[(round(x, 5), round(y, 5)) for x, y, *_ in ring] for poly in polys for ring in poly]


def geojson_lines(geom: dict) -> list[list[tuple[float, float]]]:
    t, c = geom["type"], geom["coordinates"]
    lines = [c] if t == "LineString" else c if t == "MultiLineString" else []
    return [[(round(x, 5), round(y, 5)) for x, y, *_ in line] for line in lines]


def load_geojson(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


def bbox_intersects(points: Iterable[tuple[float, float]], bbox: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = bbox
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in points)


def topojson_arcs(topo: dict) -> list[list[tuple[float, float]]]:
    """Decoded arcs of a TopoJSON topology (quantised delta-encoded or plain), in its coordinate units."""
    tr = topo.get("transform")
    out = []
    for arc in topo["arcs"]:
        if tr:
            (sx, sy), (tx, ty) = tr["scale"], tr["translate"]
            x = y = 0
            pts = []
            for p in arc:
                x += p[0]
                y += p[1]
                pts.append((x * sx + tx, y * sy + ty))
        else:
            pts = [(p[0], p[1]) for p in arc]
        out.append(pts)
    return out


def topojson_ring(arcs: list[list[tuple[float, float]]], refs: list[int]) -> list[tuple[float, float]]:
    """One ring from arc indices (a negative index ~k is arc k reversed); shared end points appear once."""
    ring: list[tuple[float, float]] = []
    for k in refs:
        pts = arcs[k] if k >= 0 else arcs[~k][::-1]
        ring.extend(pts if not ring else pts[1:])
    return ring


def topojson_rings(arcs, geom: dict) -> list[list[tuple[float, float]]]:
    """All rings (outer and holes) of a TopoJSON Polygon / MultiPolygon geometry."""
    t, a = geom.get("type"), geom.get("arcs") or []
    polys = [a] if t == "Polygon" else a if t == "MultiPolygon" else []
    return [topojson_ring(arcs, ring) for poly in polys for ring in poly]


def read_dbf(data: bytes) -> list[dict]:
    """Records of a dBASE III table (shapefile .dbf). Text is decoded as UTF-8 (latin-1 fallback); numbers
    become int/float, empty numbers None."""
    import struct

    n, hlen, rlen = struct.unpack("<IHH", data[4:12])
    fields = []
    pos = 32
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\0", 1)[0].decode("ascii")
        ftype = chr(data[pos + 11])
        flen, fdec = data[pos + 16], data[pos + 17]
        fields.append((name, ftype, flen, fdec))
        pos += 32
    out = []
    for r in range(n):
        start = hlen + r * rlen
        rec = data[start:start + rlen]
        if rec[:1] == b"*":
            continue  # deleted
        row, off = {}, 1
        for name, ftype, flen, fdec in fields:
            raw = rec[off:off + flen]
            off += flen
            if ftype in "NF":
                txt = raw.strip().decode("ascii", "replace")
                if not txt or set(txt) <= {"*"}:
                    row[name] = None
                else:
                    try:
                        row[name] = float(txt) if (fdec or "." in txt or "e" in txt.lower()) else int(txt)
                    except ValueError:
                        row[name] = None
            else:
                try:
                    row[name] = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    row[name] = raw.decode("latin-1").strip()
        out.append(row)
    return out


def read_shp(data: bytes) -> Iterator[tuple[int, list[list[tuple[float, float]]]]]:
    """(shape type, parts) for each record of an ESRI shapefile (.shp): polylines and polygons give their parts
    as point lists, points a single one-point part, null shapes no parts."""
    import struct

    pos = 100
    n = len(data)
    while pos + 8 <= n:
        _, clen = struct.unpack(">ii", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + 2 * clen]
        pos += 8 + 2 * clen
        st = struct.unpack("<i", body[:4])[0]
        if st == 0:
            yield 0, []
        elif st in (1, 11, 21):
            x, y = struct.unpack("<dd", body[4:20])
            yield st, [[(x, y)]]
        elif st in (3, 5, 13, 15, 23, 25):
            nparts, npts = struct.unpack("<ii", body[36:44])
            starts = list(struct.unpack(f"<{nparts}i", body[44:44 + 4 * nparts]))
            p0 = 44 + 4 * nparts
            coords = struct.unpack(f"<{2 * npts}d", body[p0:p0 + 16 * npts])
            starts.append(npts)
            parts = [[(coords[2 * k], coords[2 * k + 1]) for k in range(starts[j], starts[j + 1])] for j in range(nparts)]
            yield st, parts
        else:
            yield st, []
