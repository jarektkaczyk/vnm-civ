"""HydroRIVERS v1.0 (Asia): the river network around Vietnam, reach by reach, with upstream area and discharge."""

from __future__ import annotations

import zipfile

from ..core.geo import VN_LAT, VN_LON, read_dbf, read_shp
from ..core.source import Source, SourceInfo

URL = "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_as_shp.zip"
FILE = "HydroRIVERS_v10_as_shp.zip"
MIN_UPLAND_KM2 = 800  # reaches draining less than this are left out (the map shows rivers, not brooks)
PAD = 0.5
BBOX = (VN_LON[0] - PAD, VN_LAT[0] - PAD, VN_LON[1] + PAD, VN_LAT[1] + PAD)


class VnGeoHydroRivers(Source):
    info = SourceInfo(
        id="vn_geo_hydrorivers",
        title="HydroRIVERS v1.0, Asia",
        publisher="WWF HydroSHEDS (Lehner and Grill 2013)",
        homepage="https://www.hydrosheds.org/products/hydrorivers",
        license="HydroSHEDS licence agreement: free for scientific, educational and commercial use with attribution. "
        "Lehner, B., Grill G. (2013), Global river hydrography and network routing, Hydrological Processes 27(15), "
        "doi:10.1002/hyp.9740",
        description="Vector river network derived from 15 arc-second hydrography, every reach with its downstream "
        f"link, upstream catchment area and long-term mean discharge. Reaches that drain {MIN_UPLAND_KM2:,} km2 or "
        "more are drawn; a river's line width follows its discharge. Names come from Natural Earth.",
        used_for=["Rivers on the map"],
    )

    def fetch(self, force=False):
        self.download(URL, FILE, force=force, expect_binary=True)

    def process(self):
        with zipfile.ZipFile(self.raw_dir / FILE) as z:
            names = z.namelist()
            shp = z.read(next(n for n in names if n.lower().endswith(".shp")))
            dbf = z.read(next(n for n in names if n.lower().endswith(".dbf")))
        recs = read_dbf(dbf)
        x0, y0, x1, y1 = BBOX
        reaches = []
        for rec, (_, parts) in zip(recs, read_shp(shp)):
            if (rec.get("UPLAND_SKM") or 0) < MIN_UPLAND_KM2 or not parts:
                continue
            line = [(round(x, 5), round(y, 5)) for part in parts for x, y in part]
            if not any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in line):
                continue
            reaches.append({
                "id": rec["HYRIV_ID"], "next": rec["NEXT_DOWN"], "main": rec["MAIN_RIV"],
                "upland_km2": rec["UPLAND_SKM"], "dis_m3s": rec["DIS_AV_CMS"], "order": rec["ORD_CLAS"],
                "line": line,
            })
        print(f"    {len(reaches)} reaches (upstream area >= {MIN_UPLAND_KM2} km2) in the window")
        return {
            "vintage": "HydroRIVERS v1.0 (2019 release of the 2013 network)",
            "_files": [FILE],
            "min_upland_km2": MIN_UPLAND_KM2,
            "reaches": reaches,
        }
