"""Annual VIIRS night lights 2014-2024 at 500 m (OpenGeoHub, Zenodo record 17294744), over the Vietnam window.

Each year is a global Cloud-Optimised GeoTIFF (int16, DEFLATE). Only the header and the tiles of one internal
overview (1:4, 1 arc-minute, about 1.85 km) inside the map window are downloaded, with HTTP range requests, one
request per row of tiles.
"""

from __future__ import annotations

import math

from ..core.geo import VN_LAT, VN_LON
from ..core.source import Source, SourceInfo
from ._raster import (TAG_TILE_COUNTS, TAG_TILE_H, TAG_TILE_OFFSETS, TAG_TILE_W, TAG_WIDTH, geo_of, ifd_int,
                      read_ifds, read_window, tiff_header)

RECORD = "17294744"
YEARS = list(range(2014, 2025))
NAME = "nightlights.average_viirs.v21_m_500m_s_{y}0101_{y}1231_go_epsg4326_v20250904.tif"
HEAD_BYTES = 1 << 20
OVERVIEW = 4  # read the overview that is 1/4 of the full width
BBOX = (VN_LON[0], VN_LAT[0], VN_LON[1], VN_LAT[1])
# The record says values are radiance (nW/cm2/sr) moved from a 0-200 to a 0-2000 scale (x 10). The 2022-2024 layers
# hold values ten times smaller than that (their country total and every percentile drop tenfold from 2021 to 2022),
# so they are read as plain radiance. With that, the 2021 and 2022 totals over Vietnam differ by about 10%.
SCALE = {y: (1.0 if y >= 2022 else 0.1) for y in range(2000, 2025)}


def url(year: int) -> str:
    return f"https://zenodo.org/records/{RECORD}/files/{NAME.format(y=year)}"


class VnNightlights(Source):
    info = SourceInfo(
        id="vn_nightlights",
        title="Annual time series of global VIIRS night-time lights 2000-2024 at 500 m (v0.4)",
        publisher="OpenGeoHub Foundation, from the Earth Observation Group VIIRS nighttime lights (Colorado School "
        "of Mines), distributed on Zenodo",
        homepage=f"https://zenodo.org/records/{RECORD}",
        license="CC BY 4.0. Hengl, T. et al. (2025), Annual time series of global VIIRS nighttime lights for "
        "2000-2024 at 500-m, Zenodo, doi:10.5281/zenodo.17294744",
        description="The average night-time light of each year from the VIIRS instrument, 2014 to 2024 (the years "
        "measured by VIIRS; earlier years in the record are modelled and not used). Read at 1 arc-minute. The "
        "2022-2024 layers are stored at a tenth of the scale of the earlier years and are scaled to match them.",
        used_for=["Night lights lens", "Night-light growth lens", "Night lights by year (time-lapse)"],
    )

    def _layout(self, year, force=False):
        head = self.download(url(year), f"{year}/head", force=force, headers={"Range": f"bytes=0-{HEAD_BYTES - 1}"}).read_bytes()
        endian, big, first = tiff_header(head)
        ifds = read_ifds(head, 0, endian, big, first)
        full = ifds[0]
        want = ifd_int(full, TAG_WIDTH) // OVERVIEW
        ovr = next(i for i in ifds if abs(ifd_int(i, TAG_WIDTH) - want) <= 2)
        lon0, lat0, sx, sy = geo_of(full)
        scale = ifd_int(full, TAG_WIDTH) / ifd_int(ovr, TAG_WIDTH)
        return endian, ovr, (lon0, lat0, sx * scale, sy * scale)

    def _rows(self, ovr, geo):
        """Per row of tiles in the window: (first offset, end) of its tiles."""
        lon0, lat0, sx, sy = geo
        tw, th = ifd_int(ovr, TAG_TILE_W), ifd_int(ovr, TAG_TILE_H)
        across = math.ceil(ifd_int(ovr, TAG_WIDTH) / tw)
        c0, c1 = int((BBOX[0] - lon0) / sx), int((BBOX[2] - lon0) / sx) + 1
        r0, r1 = int((lat0 - BBOX[3]) / sy), int((lat0 - BBOX[1]) / sy) + 1
        offs, counts = ovr[TAG_TILE_OFFSETS], ovr[TAG_TILE_COUNTS]
        out = []
        for tr in range(r0 // th, (r1 - 1) // th + 1):
            ks = [tr * across + tc for tc in range(c0 // tw, (c1 - 1) // tw + 1) if counts[tr * across + tc]]
            if ks:
                out.append((min(offs[k] for k in ks), max(offs[k] + counts[k] for k in ks)))
        return out

    def fetch(self, force=False):
        for y in YEARS:
            endian, ovr, geo = self._layout(y, force)
            for a, b in self._rows(ovr, geo):
                self.download(url(y), f"{y}/tiles.{a}-{b - 1}", force=force, headers={"Range": f"bytes={a}-{b - 1}"})

    def process(self):
        years = {}
        files = []
        info = None
        for y in YEARS:
            endian, ovr, geo = self._layout(y)
            chunks = []
            for a, b in self._rows(ovr, geo):
                rel = f"{y}/tiles.{a}-{b - 1}"
                files.append(rel)
                chunks.append((a, (self.raw_dir / rel).read_bytes()))
            files.append(f"{y}/head")

            def read(off, cnt, chunks=chunks):
                for a, data in chunks:
                    if a <= off and off + cnt <= a + len(data):
                        return data[off - a:off - a + cnt]
                raise ValueError(f"night lights {y}: bytes {off}+{cnt} were not downloaded")

            win = read_window(read, ovr, endian, BBOX, geo=geo)
            years[str(y)] = [[None if v is None or v < 0 else round(v * SCALE[y], 2) for v in row] for row in win["rows"]]
            info = {k: win[k] for k in ("lon0", "lat_top", "step_x", "step_y", "cols")}
            print(f"    {y}: {win['cols']} x {len(win['rows'])} samples")
        return {
            "vintage": f"VIIRS night lights {YEARS[0]}-{YEARS[-1]} (OpenGeoHub v0.4)",
            "_files": files,
            **info,
            "unit": "nW/cm2/sr",
            "years": years,
        }
