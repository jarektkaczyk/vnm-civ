"""NOAA ETOPO 2022 (15 arc-second) relief over the Vietnam map window, through an ERDDAP server.

The window is fetched in latitude bands (the server drops very large responses), selected by grid index so the
bands meet without overlap.
"""

from ..core.geo import VN_LAT, VN_LON
from ..core.source import Source, SourceInfo
from ._raster import parse_esri_ascii

DATASET = "ETOPO_2022_v1_15s"
ERDDAP = "https://oceanwatch.pifsc.noaa.gov/erddap/griddap"
STEP = 1 / 240  # 15 arc-seconds
LAT_FIRST, LON_FIRST = -89.99791666666667, 0.0020833333333333333  # centre of grid index 0 (dataset info)
BAND_ROWS = 240  # one degree of latitude per request


def lat_index(lat: float) -> int:
    return round((lat - LAT_FIRST) / STEP)


def lon_index(lon: float) -> int:
    return round((lon % 360 - LON_FIRST) / STEP)


I0, I1 = lat_index(VN_LAT[0]), lat_index(VN_LAT[1])
J0, J1 = lon_index(VN_LON[0]), lon_index(VN_LON[1])
BANDS = [(a, min(a + BAND_ROWS - 1, I1)) for a in range(I0, I1 + 1, BAND_ROWS)]


def band_url(a: int, b: int) -> str:
    return f"{ERDDAP}/{DATASET}.esriAscii?z%5B{a}:1:{b}%5D%5B{J0}:1:{J1}%5D"


def band_file(a: int, b: int) -> str:
    return f"etopo2022_15s_lat{a}-{b}_lon{J0}-{J1}.asc"


class VnGeoEtopo(Source):
    info = SourceInfo(
        id="vn_geo_etopo",
        title="ETOPO 2022 global relief model (15 arc-second)",
        publisher="NOAA National Centers for Environmental Information (served by the NOAA PIFSC ERDDAP)",
        homepage="https://www.ncei.noaa.gov/products/etopo-global-relief-model",
        license="Public domain (U.S. Government work). NOAA NCEI 2022, ETOPO 2022 15 Arc-Second Global Relief Model, "
        "doi:10.25921/fd45-gt74",
        description="Land elevation and sea depth on a 15 arc-second grid (about 460 m by 460 m) over Vietnam, "
        "its neighbours and the East Sea. Each hex's elevation, highest point and relief class (flat, hills, mountains, peaks) "
        "come from the samples inside it.",
        used_for=["Relief (hills, mountains, peaks)", "Hill-shading", "Sea depth"],
    )

    def fetch(self, force=False):
        for a, b in BANDS:
            self.download(band_url(a, b), band_file(a, b), force=force)

    def process(self):
        rows, head = [], None
        for a, b in reversed(BANDS):  # north first
            g = parse_esri_ascii((self.raw_dir / band_file(a, b)).read_text())
            if g["nrows"] != b - a + 1:
                raise ValueError(f"ETOPO band {a}-{b}: {g['nrows']} rows")
            head = head or g
            rows += [[None if v is None else round(v) for v in row] for row in g["rows"]]
        return {
            "vintage": "ETOPO 2022 v1, 15 arc-second (ice surface)",
            "_files": [band_file(a, b) for a, b in BANDS],
            # Cell centres: lon = lon0 + c * step, lat = lat_top - r * step (row 0 is the northern edge).
            "lon0": round(LON_FIRST + J0 * STEP, 8),
            "lat_top": round(LAT_FIRST + I1 * STEP, 8),
            "step": STEP,
            "cols": J1 - J0 + 1,
            "rows_n": len(rows),
            "rows": rows,
        }
