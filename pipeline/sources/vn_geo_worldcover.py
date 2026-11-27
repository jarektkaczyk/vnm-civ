"""ESA WorldCover 2021 (v200) land cover over the Vietnam map window, read from the public Cloud-Optimised GeoTIFFs.

Only one internal overview of each 3 x 3 degree tile is downloaded (HTTP range requests): the 1:32 overview,
1125 x 1125 pixels per tile, i.e. 1/375 degree (about 300 m by 290 m at 15 N). Tiles
that lie wholly in the sea do not exist on the server; they are skipped.
"""

from __future__ import annotations

import math
import urllib.error

from ..core.geo import VN_LAT, VN_LON
from ..core.source import Source, SourceInfo
from ._raster import (
    TAG_COMPRESSION, TAG_PREDICTOR, TAG_TILE_COUNTS, TAG_TILE_H, TAG_TILE_OFFSETS, TAG_TILE_W, TAG_WIDTH,
    decode_tile, ifd_int, read_ifds, tiff_header,
)

BUCKET = "https://esa-worldcover.s3.eu-central-1.amazonaws.com"
VERSION, YEAR = "v200", 2021
TILE_DEG = 3
OVR_PX = 1125  # overview width in pixels per tile
STEP = TILE_DEG / OVR_PX
HEAD_BYTES = 65536

# WorldCover class -> one character (the interim stores each raster row as a string).
LEGEND = {0: ".", 10: "t", 20: "s", 30: "g", 40: "c", 50: "u", 60: "b", 70: "i", 80: "w", 90: "h", 95: "m", 100: "l"}
CLASSES = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up", 60: "Bare / sparse vegetation",
    70: "Snow and ice", 80: "Permanent water bodies", 90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen",
}


def tile_name(lat0: int, lon0: int) -> str:
    """Tile name from its south-west corner, e.g. N51E018 (covers 51-54 N, 18-21 E)."""
    return f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}"


def tiles() -> list[tuple[int, int]]:
    lats = range(math.floor(VN_LAT[0] / TILE_DEG) * TILE_DEG, math.ceil(VN_LAT[1] / TILE_DEG) * TILE_DEG, TILE_DEG)
    lons = range(math.floor(VN_LON[0] / TILE_DEG) * TILE_DEG, math.ceil(VN_LON[1] / TILE_DEG) * TILE_DEG, TILE_DEG)
    return [(la, lo) for la in lats for lo in lons]


def tile_url(name: str) -> str:
    return f"{BUCKET}/{VERSION}/{YEAR}/map/ESA_WorldCover_10m_{YEAR}_{VERSION}_{name}_Map.tif"


def overview_ifd(head: bytes) -> dict:
    endian, big, first = tiff_header(head)
    ifds = read_ifds(head, 0, endian, big, first)
    for ifd in ifds:
        if ifd_int(ifd, TAG_WIDTH) == OVR_PX:
            return ifd
    raise ValueError(f"no {OVR_PX}-pixel overview in the COG header ({[ifd_int(i, TAG_WIDTH) for i in ifds]})")


def assemble(ifd: dict, blob: bytes, blob_start: int) -> list[bytes]:
    """Decode every internal tile of an overview into OVR_PX rows of OVR_PX bytes."""
    tw, th = ifd_int(ifd, TAG_TILE_W), ifd_int(ifd, TAG_TILE_H)
    comp, pred = ifd_int(ifd, TAG_COMPRESSION, 1), ifd_int(ifd, TAG_PREDICTOR, 1)
    across = math.ceil(OVR_PX / tw)
    offs, counts = ifd[TAG_TILE_OFFSETS], ifd[TAG_TILE_COUNTS]
    rows = [bytearray(across * tw) for _ in range(math.ceil(OVR_PX / th) * th)]
    for k, (o, n) in enumerate(zip(offs, counts)):
        tr, tc = divmod(k, across)
        px = decode_tile(blob[o - blob_start:o - blob_start + n], comp, pred, tw, th) if n else bytes(tw * th)
        for y in range(th):
            rows[tr * th + y][tc * tw:(tc + 1) * tw] = px[y * tw:(y + 1) * tw]
    return [bytes(r[:OVR_PX]) for r in rows[:OVR_PX]]


class VnGeoWorldCover(Source):
    info = SourceInfo(
        id="vn_geo_worldcover",
        title=f"ESA WorldCover {YEAR} ({VERSION}), 10 m land cover",
        publisher="European Space Agency (ESA WorldCover consortium)",
        homepage="https://esa-worldcover.org/",
        license="CC BY 4.0. (c) ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) "
        "processed by ESA WorldCover consortium",
        description=f"Land cover for {YEAR} from Sentinel-1 and Sentinel-2 (11 classes: tree cover, shrubland, "
        "grassland, cropland, built-up, bare, snow and ice, water, wetland...). Read from the public Cloud-Optimised "
        "GeoTIFF tiles at their 1:32 internal overview (1/375 degree, about 300 m by 180 m). Each hex's land cover "
        "and its forest, farmland, grassland, wetland and built-up shares come from the pixels sampled inside it; "
        "the lakes on the map are the outlines of its water pixels.",
        used_for=["Hex land cover", "Forest, cropland, grassland, wetland and built-up shares", "Lake outlines"],
    )

    def _head(self, name):
        return f"{VERSION}/{YEAR}/{name}.head{HEAD_BYTES}"

    def _ovr(self, name):
        return f"{VERSION}/{YEAR}/{name}.ovr{OVR_PX}"

    def fetch(self, force=False):
        for la, lo in tiles():
            name = tile_name(la, lo)
            url = tile_url(name)
            try:
                head = self.download(url, self._head(name), force=force,
                                     headers={"Range": f"bytes=0-{HEAD_BYTES - 1}"}).read_bytes()
            except urllib.error.HTTPError as exc:
                if exc.code not in (403, 404):
                    raise
                print(f"    {name}: no tile (open sea)")
                continue
            ifd = overview_ifd(head)
            offs, counts = ifd[TAG_TILE_OFFSETS], ifd[TAG_TILE_COUNTS]
            a = min(o for o, n in zip(offs, counts) if n)
            b = max(o + n for o, n in zip(offs, counts))
            self.download(url, self._ovr(name) + f".{a}-{b - 1}", force=force, headers={"Range": f"bytes={a}-{b - 1}"})

    def process(self):
        # Window in the global 1/375-degree pixel grid (column 0 at 180 W, row 0 at 90 N).
        c0, c1 = math.floor((VN_LON[0] + 180) / STEP), math.ceil((VN_LON[1] + 180) / STEP)
        r0, r1 = math.floor((90 - VN_LAT[1]) / STEP), math.ceil((90 - VN_LAT[0]) / STEP)
        table = bytes(ord(LEGEND.get(v, ".")) for v in range(256))
        unknown = set()
        out = [bytearray(b"." * (c1 - c0)) for _ in range(r1 - r0)]
        files = []
        for la, lo in tiles():
            name = tile_name(la, lo)
            head_rel = self._head(name)
            if not (self.raw_dir / head_rel).exists():
                continue  # open sea: WorldCover has no tile here
            head = (self.raw_dir / head_rel).read_bytes()
            ifd = overview_ifd(head)
            ovr = next((self.raw_dir / f"{VERSION}/{YEAR}").glob(f"{name}.ovr{OVR_PX}.*"))
            start = int(ovr.name.rsplit(".", 1)[1].split("-")[0])
            files += [head_rel, f"{VERSION}/{YEAR}/{ovr.name}"]
            rows = assemble(ifd, ovr.read_bytes(), start)
            tc0 = round((lo + 180) / STEP)  # global column of the tile's first pixel
            tr0 = round((90 - (la + TILE_DEG)) / STEP)  # global row of its first (northern) pixel
            for y, row in enumerate(rows):
                gr = tr0 + y
                if not r0 <= gr < r1:
                    continue
                a, b = max(c0, tc0), min(c1, tc0 + OVR_PX)
                if a >= b:
                    continue
                seg = row[a - tc0:b - tc0]
                unknown |= set(seg) - set(LEGEND)
                out[gr - r0][a - c0:b - c0] = seg.translate(table)
        if unknown:
            print(f"    warning: unknown WorldCover codes treated as no data: {sorted(unknown)}")
        return {
            "vintage": f"ESA WorldCover {YEAR} {VERSION}, 1:32 overview (1/375 degree)",
            "_files": files,
            # Pixel (r, c) covers lon [lon0 + c * step, + step), lat [lat_top - (r + 1) * step, lat_top - r * step).
            "lon0": c0 * STEP - 180,
            "lat_top": 90 - r0 * STEP,
            "step": STEP,
            "cols": c1 - c0,
            "rows_n": r1 - r0,
            "legend": {ch: code for code, ch in LEGEND.items()},
            "classes": CLASSES,
            "rows": [r.decode("ascii") for r in out],
        }
