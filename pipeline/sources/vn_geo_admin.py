"""Provincial boundaries of Vietnam.

* geoBoundaries gbOpen VNM ADM1 (public domain): the 63 former provinces. The 34 provinces of 1 July 2025 are made
  by dissolving them with the mapping of Resolution 202/2025/QH15 (vn_admin_units.PROVINCES). Its 64th feature,
  Con Dao, belongs to Ba Ria - Vung Tau.
* HDX COD-AB Viet Nam v02 (CC BY-IGO, from the General Statistics Office): the 34 provinces as published. It is the
  check of the dissolve (the world builder compares the two per hex), and its island parts in the Hoang Sa and
  Tr\u01b0\u1eddng Sa archipelagos are the island marks on the map.
"""

from __future__ import annotations

import json
import math
import zipfile

from ..core.source import Source, SourceInfo
from . import vn_admin_units as U
from .vn_geo_ne import archipelago_of

GB_URL = ("https://www.geoboundaries.org/data/snapshots/1c423398df24ddf6e730b116567d2181c9782778d0459c3f3b76ca2f9f12b6bc"
          "/gbOpen/VNM/ADM1/geoBoundaries-VNM-ADM1.geojson")
GB_FILE = "geoboundaries/geoBoundaries-VNM-ADM1.geojson"
COD_URL = ("https://data.humdata.org/dataset/3cb544a9-9d04-4f54-94e2-93230efd8ceb/resource/"
           "048a6012-a8c2-4fa9-be87-cb6c01e9afbf/download/vnm_admin_boundaries.geojson.zip")
COD_FILE = "hdx/vnm_admin_boundaries.geojson.zip"
COD_STEP_DEG = 0.01  # the check outlines keep a vertex every ~1 km
CON_DAO = "77"


def _polys(geom: dict) -> list[list[list[tuple[float, float]]]]:
    """Polygons (each a list of rings, outer first) of a Polygon or MultiPolygon."""
    if geom["type"] == "Polygon":
        return [[[tuple(p) for p in r] for r in geom["coordinates"]]]
    return [[[tuple(p) for p in r] for r in poly] for poly in geom["coordinates"]]


def _thin(ring, step):
    out = [ring[0]]
    for p in ring[1:]:
        if abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) >= step:
            out.append(p)
    return [(round(x, 5), round(y, 5)) for x, y in out] if len(out) >= 4 else []


def ring_area_km2(ring) -> float:
    """Planar area of a lon/lat ring in km2 (equirectangular at the ring's mean latitude)."""
    lat0 = math.radians(sum(y for _, y in ring) / len(ring))
    kx, ky = 111.32 * math.cos(lat0), 110.57
    a = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        a += (x0 * kx) * (y1 * ky) - (x1 * kx) * (y0 * ky)
    return abs(a) / 2


class VnGeoAdmin(Source):
    info = SourceInfo(
        id="vn_geo_admin",
        title="Provincial boundaries of Vietnam: the 63 former provinces and the 34 provinces of 2025",
        publisher="geoBoundaries (William & Mary geoLab); OCHA and the General Statistics Office of Viet Nam (HDX "
        "COD-AB); National Assembly of Viet Nam (Resolution 202/2025/QH15)",
        homepage="https://www.geoboundaries.org/",
        license="geoBoundaries gbOpen VNM ADM1: public domain. HDX COD-AB Viet Nam v02: CC BY-IGO. Runfola, D. et al. "
        "(2020) geoBoundaries: A global database of political administrative boundaries. PLoS ONE 15(4): e0231866",
        description="Outlines of the 63 provinces in force until 30 June 2025 (geoBoundaries, digitised at a small "
        "scale). The 34 provinces and centrally run cities in force since 1 July 2025 are drawn by joining whole "
        "former provinces as Resolution 202/2025/QH15 sets out; the published 34-province outlines of the "
        "General Statistics Office (HDX COD-AB, valid 2025-09-25) check the result and give the islands of the "
        "Ho\u00e0ng Sa and Tr\u01b0\u1eddng Sa archipelagos.",
        used_for=["The 34 provinces and the 63 former provinces on the map", "Islands of the Ho\u00e0ng Sa and Tr\u01b0\u1eddng Sa "
                  "archipelagos"],
    )

    def fetch(self, force=False):
        self.download(GB_URL, GB_FILE, force=force)
        self.download(COD_URL, COD_FILE, force=force, expect_binary=True)

    def process(self):
        gb = json.loads((self.raw_dir / GB_FILE).read_text())
        rings_of: dict[str, list] = {c: [] for c, _ in U.FORMER}
        notes = []
        for f in gb["features"]:
            name = f["properties"]["shapeName"].strip()
            code = CON_DAO if U.fold(name) == "condao" else U.former_code(name)
            if code is None:
                raise ValueError(f"geoBoundaries feature {name!r} matches no former province")
            if U.fold(name) == "condao":
                notes.append("geoBoundaries draws Con Dao as its own feature; it is part of Ba Ria - Vung Tau")
            for poly in _polys(f["geometry"]):
                rings_of[code] += [[(round(x, 5), round(y, 5)) for x, y in r] for r in poly]
        missing = [c for c, r in rings_of.items() if not r]
        if missing:
            raise ValueError(f"no outline for former provinces {missing}")
        former = []
        for code, name in U.FORMER:
            outer = sum(ring_area_km2(r) for r in rings_of[code])
            former.append({"code": code, "name": name, "province": U.NEW_OF[code], "rings": rings_of[code],
                           "area_km2": round(outer, 1)})
        provinces = [{"code": c, "name": n, "type": k, "abbr": a, "former": olds, "centre": centre}
                     for c, n, k, a, olds, centre in U.PROVINCES]

        # HDX COD-AB: the published 34 outlines (thinned) and the archipelago islands.
        with zipfile.ZipFile(self.raw_dir / COD_FILE) as z:
            name = next(n for n in z.namelist() if n.endswith("admin1.geojson"))
            cod = json.loads(z.read(name))
        check, islands = [], []
        for f in cod["features"]:
            p = f["properties"]
            pcode = (p.get("adm1_pcode") or "")[-2:]
            if pcode not in U.PROVINCE_NAME:
                raise ValueError(f"COD-AB unit {p.get('adm1_pcode')} {p.get('adm1_name1')} is not one of the 34")
            rings = []
            for poly in _polys(f["geometry"]):
                outer = poly[0]
                lon = sum(x for x, _ in outer) / len(outer)
                lat = sum(y for _, y in outer) / len(outer)
                arch = archipelago_of(lon, lat)
                if arch and lon > 109.8:
                    xs, ys = [x for x, _ in outer], [y for _, y in outer]
                    islands.append({"archipelago": arch, "province": pcode, "lon": round(lon, 4),
                                    "lat": round(lat, 4), "w_deg": round(max(xs) - min(xs), 4),
                                    "h_deg": round(max(ys) - min(ys), 4),
                                    "area_km2": round(ring_area_km2(outer), 3)})
                    continue
                for r in poly:
                    t = _thin(r, COD_STEP_DEG)
                    if t:
                        rings.append(t)
            check.append({"code": pcode, "name": p.get("adm1_name1"), "name_en": p.get("adm1_name"),
                          "type_vi": p.get("adm1_type_vi"), "area_km2": p.get("area_sqkm"),
                          "valid_on": p.get("valid_on"), "rings": rings})
        print(f"    63 former provinces ({len(gb['features'])} geoBoundaries features), 34 provinces; COD-AB check "
              f"outlines for {len(check)} units, {len(islands)} archipelago island parts")
        return {
            "vintage": "geoBoundaries gbOpen VNM ADM1 (2008 outlines); HDX COD-AB Viet Nam v02 (valid 2025-09-25); "
                       "Resolution 202/2025/QH15",
            "_files": [GB_FILE, COD_FILE],
            "resolution": {"id": U.RESOLUTION, "url": U.RESOLUTION_URL, "centres_url": U.CENTRES_URL},
            "provinces": provinces,
            "former": former,
            "check34": check,
            "archipelagos": [{**a, "label": list(a["label"])} for a in U.ARCHIPELAGOS],
            "islands": islands,
            "notes": notes,
        }
