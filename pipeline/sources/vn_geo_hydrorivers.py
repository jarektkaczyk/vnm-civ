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


# The attribution the HydroSHEDS licence (Exhibit B) requires with any product that uses the data. THIRD_PARTY_NOTICES
# holds it with the full licence text that governs the river data.
EXHIBIT_B = (
    "This product vnm-civ incorporates data from the HydroSHEDS version 1 database which is \u00a9 World Wildlife "
    "Fund, Inc. (2006-2022) and has been used herein under license. WWF has not evaluated the data as altered and "
    "incorporated within vnm-civ, and therefore gives no warranty regarding its accuracy, completeness, currency or "
    "suitability for any particular purpose. Portions of the HydroSHEDS v1 database incorporate data which are the "
    "intellectual property rights of \u00a9 USGS (2006-2008), NASA (2000-2005), ESRI (1992-1998), CIAT (2004-2006), "
    "UNEP-WCMC (1993), WWF (2004), Commonwealth of Australia (2007), and Her Royal Majesty and the British Crown and "
    "are used under license. The HydroSHEDS v1 database and more information are available at "
    "https://www.hydrosheds.org."
)


class VnGeoHydroRivers(Source):
    info = SourceInfo(
        id="vn_geo_hydrorivers",
        title="HydroRIVERS v1.0, Asia",
        publisher="WWF HydroSHEDS (Lehner and Grill 2013)",
        homepage="https://www.hydrosheds.org/products/hydrorivers",
        license="HydroSHEDS Version 1 License Agreement. Use of the river data of this map is subject to the terms of "
        "that License, reproduced in full in the file THIRD_PARTY_NOTICES of the map's public repository; they bind "
        "every user of the river data. Required attribution (Exhibit B): " + EXHIBIT_B
        + " Lehner, B., Grill G. (2013), Global river hydrography and network routing, Hydrological Processes 27(15), "
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
