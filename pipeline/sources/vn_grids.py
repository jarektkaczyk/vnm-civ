"""Gridded data over Vietnam: WorldPop population 2025 (1 km) and CHIRPS v3 rainfall 2025 (0.05 degree).

Both are GeoTIFFs read whole and cut to the map window; the window rows go into the interim.
"""

from __future__ import annotations

from ..core.geo import VN_LAT, VN_LON
from ..core.source import Source, SourceInfo
from ._raster import local_reader, open_tiff, read_window

BBOX = (VN_LON[0], VN_LAT[0], VN_LON[1], VN_LAT[1])

WORLDPOP_URL = ("https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/VNM/v1/1km_ua/constrained/"
                "vnm_pop_2025_CN_1km_R2025A_UA_v1.tif")
WORLDPOP_FILE = "R2025A/vnm_pop_2025_CN_1km_R2025A_UA_v1.tif"
CHIRPS_YEAR = 2025
CHIRPS_URL = f"https://data.chc.ucsb.edu/products/CHIRPS/v3.0/annual/global/tifs/chirps-v3.0.{CHIRPS_YEAR}.tif"
CHIRPS_FILE = f"v3.0/chirps-v3.0.{CHIRPS_YEAR}.tif"


def window(path, nodata_below: float = -1e30) -> dict:
    data = path.read_bytes()
    endian, ifds = open_tiff(data)
    win = read_window(local_reader(data), ifds[0], endian, BBOX)
    win["rows"] = [[None if v is None or v != v or v <= nodata_below else round(v, 3) for v in row] for row in win["rows"]]
    return win


class VnWorldPop(Source):
    info = SourceInfo(
        id="vn_worldpop",
        title="WorldPop Global2 population 2025, Viet Nam, 1 km, constrained, UN-adjusted (R2025A)",
        publisher="WorldPop, University of Southampton",
        homepage="https://www.worldpop.org/",
        license="CC BY 4.0. Bondarenko, M. et al. (2025), Global2 R2025A, WorldPop, University of Southampton",
        description="Estimated residents of 2025 on a 1 km grid, placed only where buildings are mapped and "
        "adjusted to the United Nations national total. Each hex sums the cells inside it.",
        used_for=["Population density lens (per hex)"],
    )

    def fetch(self, force=False):
        self.download(WORLDPOP_URL, WORLDPOP_FILE, force=force, expect_binary=True)

    def process(self):
        win = window(self.raw_dir / WORLDPOP_FILE, nodata_below=-1)
        total = sum(v for row in win["rows"] for v in row if v)
        print(f"    {win['cols']} x {len(win['rows'])} cells, {total:,.0f} people")
        return {"vintage": "WorldPop Global2 R2025A, 2025", "_files": [WORLDPOP_FILE], **win}


class VnChirps(Source):
    info = SourceInfo(
        id="vn_chirps",
        title=f"CHIRPS v3.0 annual rainfall {CHIRPS_YEAR}",
        publisher="Climate Hazards Center, University of California, Santa Barbara",
        homepage="https://www.chc.ucsb.edu/data/chirps3",
        license="Public domain (CC0) / CC BY 4.0 as the Climate Hazards Center states. Funk, C. et al., CHIRPS v3.0, "
        "Climate Hazards Center, UC Santa Barbara",
        description=f"Total rainfall of {CHIRPS_YEAR} on a 0.05 degree grid (about 5.5 km), from satellite "
        "observations blended with rain-gauge records.",
        used_for=["Rainfall lens"],
    )

    def fetch(self, force=False):
        self.download(CHIRPS_URL, CHIRPS_FILE, force=force, expect_binary=True)

    def process(self):
        win = window(self.raw_dir / CHIRPS_FILE, nodata_below=-1)
        vals = sorted(v for row in win["rows"] for v in row if v is not None)
        print(f"    {win['cols']} x {len(win['rows'])} cells, median {vals[len(vals) // 2]:.0f} mm")
        return {"vintage": f"CHIRPS v3.0, {CHIRPS_YEAR}", "_files": [CHIRPS_FILE], "year": CHIRPS_YEAR, **win}
