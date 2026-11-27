"""Copernicus Global Land Service Land Cover 100 m (collection 3, epoch 2019): the forest type layer over the
Vietnam map window. It tells needle-leaved, broad-leaved and mixed forest apart, which WorldCover does not.

The global GeoTIFF (BigTIFF, 256 x 256 deflate tiles, no overviews) is read with HTTP range requests: the tag
block at the end of the file, then one byte range per row of internal tiles inside the window.
"""

from __future__ import annotations

import math

from ..core.geo import VN_LAT, VN_LON
from ..core.source import Source, SourceInfo
from ._raster import (
    TAG_COMPRESSION, TAG_PIXEL_SCALE, TAG_PREDICTOR, TAG_TIEPOINT, TAG_TILE_COUNTS, TAG_TILE_H, TAG_TILE_OFFSETS,
    TAG_TILE_W, TAG_WIDTH, decode_tile, ifd_int, read_ifds, tiff_header,
)

RECORD = "3939050"
FILE_NAME = "PROBAV_LC100_global_v3.0.1_2019-nrt_Forest-Type-layer_EPSG-4326.tif"
URL = f"https://zenodo.org/api/records/{RECORD}/files/{FILE_NAME}/content"
DOWNSAMPLE = 4  # keep every 4th pixel (1/252 degree, about 440 m by 270 m): plenty for per-hex majorities
# Forest type codes (product user manual): 0 unknown / no forest, 1 evergreen needle leaf, 2 evergreen broad leaf,
# 3 deciduous needle leaf, 4 deciduous broad leaf, 5 mixed.
LEGEND = {0: ".", 1: "n", 2: "b", 3: "l", 4: "d", 5: "m"}
CLASSES = {1: "Evergreen needle leaf", 2: "Evergreen broad leaf", 3: "Deciduous needle leaf",
           4: "Deciduous broad leaf", 5: "Mixed"}


class VnGeoForestType(Source):
    info = SourceInfo(
        id="vn_geo_forest_type",
        title="Copernicus Global Land Cover 100 m, forest type layer (epoch 2019)",
        publisher="Copernicus Global Land Service (VITO), distributed on Zenodo",
        homepage=f"https://zenodo.org/records/{RECORD}",
        license="CC BY 4.0. Buchhorn, M. et al. (2020), Copernicus Global Land Service: Land Cover 100m: "
        "collection 3: epoch 2019: Globe, doi:10.5281/zenodo.3939050",
        description="Forest type (needle-leaved, broad-leaved or mixed) at 100 m for 2019, the newest epoch of the "
        "product. It decides whether a forest hex is drawn as evergreen broadleaf, deciduous, pine or mixed forest.",
        used_for=["Forest type of forest hexes (evergreen, deciduous, pine, mixed)"],
    )

    def _tail(self, off):
        return f"2019/forest_type.tail{off}"

    def _row(self, r, a, b):
        return f"2019/forest_type.tilerow{r}.{a}-{b}"

    def _layout(self, force=False):
        head = self.download(URL, "2019/forest_type.head16", force=force, headers={"Range": "bytes=0-15"}).read_bytes()
        endian, big, first = tiff_header(head)
        tail = self.download(URL, self._tail(first), force=force, headers={"Range": f"bytes={first}-"}).read_bytes()
        ifd = read_ifds(tail, first, endian, big, first, limit=1)[0]
        tw, th = ifd_int(ifd, TAG_TILE_W), ifd_int(ifd, TAG_TILE_H)
        width = ifd_int(ifd, TAG_WIDTH)
        sx, sy = ifd[TAG_PIXEL_SCALE][:2]
        _, _, _, lon_ul, lat_ul, _ = ifd[TAG_TIEPOINT][:6]
        across = math.ceil(width / tw)
        c0, c1 = math.floor((VN_LON[0] - lon_ul) / sx), math.ceil((VN_LON[1] - lon_ul) / sx)
        r0, r1 = math.floor((lat_ul - VN_LAT[1]) / sy), math.ceil((lat_ul - VN_LAT[0]) / sy)
        return {"ifd": ifd, "tw": tw, "th": th, "across": across, "sx": sx, "sy": sy, "lon_ul": lon_ul,
                "lat_ul": lat_ul, "c0": c0, "c1": c1, "r0": r0, "r1": r1, "first": first}

    def _tile_rows(self, L):
        ifd, tw, th, across = L["ifd"], L["tw"], L["th"], L["across"]
        offs, counts = ifd[TAG_TILE_OFFSETS], ifd[TAG_TILE_COUNTS]
        for tr in range(L["r0"] // th, (L["r1"] - 1) // th + 1):
            ks = [tr * across + tc for tc in range(L["c0"] // tw, (L["c1"] - 1) // tw + 1)]
            live = [k for k in ks if counts[k]]
            if not live:
                yield tr, ks, None, None
                continue
            a = min(offs[k] for k in live)
            b = max(offs[k] + counts[k] for k in live)
            if b - a > 4 * sum(counts[k] for k in live) + (1 << 20):
                raise ValueError(f"tile row {tr}: tiles are not stored together ({b - a} bytes span)")
            yield tr, ks, a, b

    def fetch(self, force=False):
        L = self._layout(force)
        for tr, _, a, b in self._tile_rows(L):
            if a is not None:
                self.download(URL, self._row(tr, a, b - 1), force=force, headers={"Range": f"bytes={a}-{b - 1}"})

    def process(self):
        L = self._layout()
        ifd, tw, th = L["ifd"], L["tw"], L["th"]
        comp, pred = ifd_int(ifd, TAG_COMPRESSION, 1), ifd_int(ifd, TAG_PREDICTOR, 1)
        offs, counts = ifd[TAG_TILE_OFFSETS], ifd[TAG_TILE_COUNTS]
        c0, c1, r0, r1 = L["c0"], L["c1"], L["r0"], L["r1"]
        keep_c = range(c0, c1, DOWNSAMPLE)
        table = bytes(ord(LEGEND.get(v, ".")) for v in range(256))
        out_rows = []
        files = ["2019/forest_type.head16", self._tail(L["first"])]
        for tr, ks, a, b in self._tile_rows(L):
            band = [bytearray(len(keep_c)) for _ in range(th)]
            if a is not None:
                rel = self._row(tr, a, b - 1)
                files.append(rel)
                blob = (self.raw_dir / rel).read_bytes()
                for k in ks:
                    if not counts[k]:
                        continue
                    px = decode_tile(blob[offs[k] - a:offs[k] - a + counts[k]], comp, pred, tw, th)
                    tc = k % L["across"]
                    for j, gc in enumerate(keep_c):
                        if tc * tw <= gc < (tc + 1) * tw:
                            x = gc - tc * tw
                            for y in range(th):
                                band[y][j] = px[y * tw + x]
            for y in range(th):
                gr = tr * th + y
                if r0 <= gr < r1 and (gr - r0) % DOWNSAMPLE == 0:
                    out_rows.append(bytes(band[y]).translate(table).decode("ascii"))
        step_x, step_y = L["sx"] * DOWNSAMPLE, L["sy"] * DOWNSAMPLE
        return {
            "vintage": "CGLS-LC100 collection 3, epoch 2019 (v3.0.1)",
            "_files": files,
            # Sample (r, c) is the original pixel whose north-west corner is (lon0 + c * step_x, lat_top - r * step_y).
            "lon0": L["lon_ul"] + c0 * L["sx"],
            "lat_top": L["lat_ul"] - r0 * L["sy"],
            "step_x": step_x,
            "step_y": step_y,
            "pixel": [L["sx"], L["sy"]],
            "cols": len(keep_c),
            "rows_n": len(out_rows),
            "legend": {ch: code for code, ch in LEGEND.items()},
            "classes": CLASSES,
            "rows": out_rows,
        }
