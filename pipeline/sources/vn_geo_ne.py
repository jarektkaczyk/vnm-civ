"""Natural Earth 1:10m around Vietnam: country outlines (Vietnam's point of view), lakes, rivers, minor islands and
reefs.

The countries come from the Vietnam point-of-view edition of the admin-0 file (ne_10m_admin_0_countries_vnm), in
which the islands of the Hoang Sa and Truong Sa archipelagos that Natural Earth maps belong to Vietnam.
"""

from ..core.geo import VN_LAT, VN_LON, bbox_intersects, geojson_lines, geojson_rings, load_geojson
from ..core.source import Source, SourceInfo

TAG = "v5.1.2"  # pinned release, so the content (and sha256) cannot change under the same URL
BASE = f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{TAG}/geojson"
PAD = 1.5  # degrees around the map window, so outlines that cross its edge are kept whole
BBOX = (VN_LON[0] - PAD, VN_LAT[0] - PAD, VN_LON[1] + PAD, VN_LAT[1] + PAD)
COUNTRIES = "ne_10m_admin_0_countries_vnm"
FILES = [COUNTRIES, "ne_10m_lakes", "ne_10m_rivers_lake_centerlines", "ne_10m_minor_islands", "ne_10m_reefs"]

# The two archipelagos (lon/lat boxes). Islands inside them are drawn as island marks with the archipelago label.
ARCHIPELAGOS = {
    "hoang_sa": (110.9, 15.5, 113.0, 17.3),
    "truong_sa": (111.5, 6.8, 116.2, 11.8),
}


def archipelago_of(lon: float, lat: float) -> str | None:
    for key, (x0, y0, x1, y1) in ARCHIPELAGOS.items():
        if x0 <= lon <= x1 and y0 <= lat <= y1:
            return key
    return None


class VnGeoNe(Source):
    info = SourceInfo(
        id="vn_geo_ne",
        title="Natural Earth 1:10m (countries from Vietnam's point of view, lakes, rivers, minor islands, reefs)",
        publisher="Natural Earth",
        homepage="https://www.naturalearthdata.com/",
        license="Public domain",
        description="Outlines of Vietnam and its neighbours (China, Laos, Cambodia, Thailand; shown under fog) from "
        "the Vietnam point-of-view edition, the larger lakes, river names outside Vietnam, and the minor islands and "
        f"reefs of the Ho\u00e0ng Sa and Tr\u01b0\u1eddng Sa archipelagos. Files are pinned to the natural-earth-vector release {TAG}.",
        used_for=["Neighbouring countries", "Islands of the Ho\u00e0ng Sa and Tr\u01b0\u1eddng Sa archipelagos", "Lake names"],
    )

    def _path(self, name):
        return f"{TAG}/{name}.geojson"

    def fetch(self, force=False):
        for name in FILES:
            self.download(f"{BASE}/{name}.geojson", self._path(name), force=force)

    def _features(self, name):
        return load_geojson(self.raw_dir / self._path(name))

    def process(self):
        countries = []
        islands = []
        for f in self._features(COUNTRIES):
            p = f["properties"]
            rings = [r for r in geojson_rings(f["geometry"]) if bbox_intersects(r, BBOX)]
            if not rings:
                continue
            iso = p.get("ADM0_A3")
            if iso == "VNM":
                keep = []
                for r in rings:
                    lon = sum(x for x, _ in r) / len(r)
                    lat = sum(y for _, y in r) / len(r)
                    arch = archipelago_of(lon, lat)
                    if arch:
                        islands.append({"archipelago": arch, "lon": round(lon, 4), "lat": round(lat, 4), "ring": r,
                                        "from": COUNTRIES})
                    else:
                        keep.append(r)
                rings = keep
            countries.append({"iso": iso, "name": p.get("ADMIN"), "rings": rings})
        for name in ("ne_10m_minor_islands", "ne_10m_reefs"):
            for f in self._features(name):
                if not f.get("geometry"):
                    continue
                for r in (geojson_rings(f["geometry"]) if "Polygon" in f["geometry"]["type"]
                          else geojson_lines(f["geometry"])):
                    lon = sum(x for x, _ in r) / len(r)
                    lat = sum(y for _, y in r) / len(r)
                    arch = archipelago_of(lon, lat)
                    if arch:
                        islands.append({"archipelago": arch, "lon": round(lon, 4), "lat": round(lat, 4), "ring": r,
                                        "from": name, "reef": name == "ne_10m_reefs"})
        lakes = []
        for f in self._features("ne_10m_lakes"):
            if not f.get("geometry"):
                continue
            rings = geojson_rings(f["geometry"])
            if rings and bbox_intersects(rings[0], BBOX):
                p = f["properties"]
                lakes.append({"name": p.get("name_vi") or p.get("name"), "name_en": p.get("name"),
                              "featurecla": p.get("featurecla"), "rings": rings})
        rivers = []
        for f in self._features("ne_10m_rivers_lake_centerlines"):
            if not f.get("geometry"):
                continue
            p = f["properties"]
            for line in geojson_lines(f["geometry"]):
                if bbox_intersects(line, BBOX):
                    rivers.append({"name": p.get("name_vi") or p.get("name"), "name_en": p.get("name"),
                                   "rank": p.get("scalerank"), "featurecla": p.get("featurecla"), "line": line})
        # The same island can sit in two files: keep one per 1 km.
        seen, uniq = set(), []
        for it in islands:
            key = (it["archipelago"], round(it["lon"] * 100), round(it["lat"] * 100))
            if key not in seen:
                seen.add(key)
                uniq.append(it)
        print(f"    {len(countries)} countries, {len(lakes)} lakes, {len(rivers)} river lines, "
              f"{len(uniq)} island and reef shapes in the archipelagos")
        return {
            "vintage": f"Natural Earth {TAG} (1:10m)",
            "_files": [self._path(n) for n in FILES],
            "countries": countries,
            "islands": uniq,
            "lakes": lakes,
            "rivers": rivers,
        }
