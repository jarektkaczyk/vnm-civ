"""Small standard-library readers for the rasters the geography sources use.

* TIFF / BigTIFF: IFD parsing (little or big endian) and tiled 8-bit decoding with
  no compression, LZW (5) or Deflate (8, 32946), with or without horizontal
  differencing (predictor 2). Enough for Cloud-Optimised GeoTIFFs such as ESA
  WorldCover and the Copernicus Global Land Cover layers.
* ESRI ASCII grids (ERDDAP ``.esriAscii``).

Helpers only: no Source here (the registry ignores modules without one).
"""

from __future__ import annotations

import struct
import zlib

# TIFF field types -> (struct code, size in bytes)
_TYPES = {
    1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 6: ("b", 1), 7: ("B", 1),
    8: ("h", 2), 9: ("i", 4), 10: ("ii", 8), 11: ("f", 4), 12: ("d", 8), 16: ("Q", 8), 17: ("q", 8), 18: ("Q", 8),
}

TAG_WIDTH, TAG_HEIGHT, TAG_BPS, TAG_COMPRESSION = 256, 257, 258, 259
TAG_TILE_W, TAG_TILE_H, TAG_TILE_OFFSETS, TAG_TILE_COUNTS = 322, 323, 324, 325
TAG_PREDICTOR, TAG_PIXEL_SCALE, TAG_TIEPOINT = 317, 33550, 33922


class Pointer:
    """A tag value stored outside the bytes we have: read it later with read_values(buf, base, ptr)."""

    def __init__(self, offset: int, count: int, ftype: int, endian: str):
        self.offset, self.count, self.ftype, self.endian = offset, count, ftype, endian

    def __repr__(self) -> str:
        return f"Pointer(offset={self.offset}, count={self.count}, type={self.ftype})"


def _unpack(endian: str, ftype: int, count: int, data: bytes):
    code, size = _TYPES[ftype]
    if ftype == 2:
        return data[:count].split(b"\0", 1)[0].decode("latin-1")
    if ftype in (5, 10):
        vals = struct.unpack(endian + code[0] * (2 * count), data[: size * count])
        return tuple(vals[k] / vals[k + 1] if vals[k + 1] else 0.0 for k in range(0, len(vals), 2))
    return struct.unpack(endian + code * count, data[: size * count])


def read_values(buf: bytes, base: int, ptr: Pointer):
    """Values of a Pointer tag from `buf`, which holds the file's bytes starting at offset `base`."""
    start = ptr.offset - base
    size = _TYPES[ptr.ftype][1] * ptr.count
    if start < 0 or start + size > len(buf):
        raise ValueError(f"{ptr!r} is outside the {len(buf)} bytes at offset {base}")
    return _unpack(ptr.endian, ptr.ftype, ptr.count, buf[start:start + size])


def tiff_header(head: bytes) -> tuple[str, bool, int]:
    """(endian '<' or '>', bigtiff, offset of the first IFD) from the first 16 bytes of a TIFF."""
    if head[:2] == b"II":
        endian = "<"
    elif head[:2] == b"MM":
        endian = ">"
    else:
        raise ValueError("not a TIFF (no II/MM byte order mark)")
    magic = struct.unpack(endian + "H", head[2:4])[0]
    if magic == 42:
        return endian, False, struct.unpack(endian + "I", head[4:8])[0]
    if magic == 43:
        return endian, True, struct.unpack(endian + "Q", head[8:16])[0]
    raise ValueError(f"not a TIFF (magic {magic})")


def read_ifds(buf: bytes, base: int, endian: str, bigtiff: bool, first: int, limit: int = 64) -> list[dict]:
    """Every IFD reachable from offset `first` whose entries lie in `buf` (file bytes from offset `base`).

    Each IFD is {tag: tuple | str | Pointer}; a value that lies outside `buf` is left as a Pointer.
    The chain stops at the first IFD outside `buf`.
    """
    ifds = []
    off = first
    cnt_fmt, cnt_size = ("Q", 8) if bigtiff else ("H", 2)
    ent_size, val_size = (20, 8) if bigtiff else (12, 4)
    while off and len(ifds) < limit:
        p = off - base
        if p < 0 or p + cnt_size > len(buf):
            break
        n = struct.unpack(endian + cnt_fmt, buf[p:p + cnt_size])[0]
        if p + cnt_size + n * ent_size + val_size > len(buf):
            break
        tags = {}
        for k in range(n):
            e = p + cnt_size + k * ent_size
            if bigtiff:
                tag, ftype, count = struct.unpack(endian + "HHQ", buf[e:e + 12])
                raw = buf[e + 12:e + 20]
            else:
                tag, ftype, count = struct.unpack(endian + "HHI", buf[e:e + 8])
                raw = buf[e + 8:e + 12]
            if ftype not in _TYPES:
                continue
            size = _TYPES[ftype][1] * count
            if size <= val_size:
                tags[tag] = _unpack(endian, ftype, count, raw)
            else:
                ptr = Pointer(struct.unpack(endian + ("Q" if bigtiff else "I"), raw)[0], count, ftype, endian)
                start = ptr.offset - base
                tags[tag] = read_values(buf, base, ptr) if 0 <= start and start + size <= len(buf) else ptr
        ifds.append(tags)
        q = p + cnt_size + n * ent_size
        off = struct.unpack(endian + ("Q" if bigtiff else "I"), buf[q:q + val_size])[0]
    return ifds


def lzw_decode(data: bytes) -> bytes:
    """TIFF LZW (MSB-first codes, 9 to 12 bits, early change, 256 = clear, 257 = end of information)."""
    out = bytearray()
    table: list[bytes] = []
    width = 9
    bitbuf = nbits = 0
    prev = None
    pos = 0
    n = len(data)
    while True:
        while nbits < width:
            if pos >= n:
                return bytes(out)
            bitbuf = (bitbuf << 8) | data[pos]
            pos += 1
            nbits += 8
        nbits -= width
        code = (bitbuf >> nbits) & ((1 << width) - 1)
        bitbuf &= (1 << nbits) - 1
        if code == 256:
            table = [bytes([k]) for k in range(256)] + [b"", b""]
            width = 9
            prev = None
            continue
        if code == 257:
            return bytes(out)
        if not table:
            table = [bytes([k]) for k in range(256)] + [b"", b""]
        if prev is None:
            entry = table[code]
            out += entry
            prev = entry
            continue
        if code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        elif code == len(table):
            entry = prev + prev[:1]
            table.append(entry)
        else:
            raise ValueError(f"bad LZW code {code} (table size {len(table)})")
        out += entry
        prev = entry
        # Early change: the code width grows one code before the table fills.
        if len(table) + 1 >= (1 << width) and width < 12:
            width += 1


def undo_horizontal_predictor(data: bytes, width: int) -> bytes:
    """Reverse TIFF predictor 2 for 8-bit, one sample per pixel."""
    out = bytearray(data)
    for r in range(0, len(out), width):
        acc = 0
        for k in range(r, min(r + width, len(out))):
            acc = (acc + out[k]) & 0xFF
            out[k] = acc
    return bytes(out)


def decode_tile(data: bytes, compression: int, predictor: int, tile_w: int, tile_h: int) -> bytes:
    """One 8-bit, single-band tile as tile_w * tile_h bytes (short tiles are zero-padded)."""
    if compression == 1:
        raw = data
    elif compression == 5:
        raw = lzw_decode(data)
    elif compression in (8, 32946):
        raw = zlib.decompress(data)
    else:
        raise ValueError(f"unsupported TIFF compression {compression}")
    if predictor == 2:
        raw = undo_horizontal_predictor(raw, tile_w)
    elif predictor not in (0, 1):
        raise ValueError(f"unsupported TIFF predictor {predictor}")
    need = tile_w * tile_h
    return raw[:need] if len(raw) >= need else raw + bytes(need - len(raw))


def ifd_int(ifd: dict, tag: int, default: int | None = None) -> int:
    v = ifd.get(tag)
    if v is None:
        if default is None:
            raise KeyError(f"TIFF tag {tag} missing")
        return default
    return int(v[0])


def parse_esri_ascii(text: str) -> dict:
    """ESRI ASCII grid -> {ncols, nrows, xll, yll (lower-left cell centre), cellsize, nodata, rows (north first)}.

    Accepts both corner (xllcorner) and centre (xllcenter) headers; values become floats, nodata None.
    """
    lines = text.splitlines()
    head: dict[str, float] = {}
    k = 0
    while k < len(lines):
        parts = lines[k].split()
        if len(parts) == 2 and parts[0].replace("_", "").isalpha():
            head[parts[0].lower()] = float(parts[1])
            k += 1
        else:
            break
    ncols, nrows, cs = int(head["ncols"]), int(head["nrows"]), head["cellsize"]
    xll = head["xllcenter"] if "xllcenter" in head else head["xllcorner"] + cs / 2
    yll = head["yllcenter"] if "yllcenter" in head else head["yllcorner"] + cs / 2
    nodata = head.get("nodata_value")
    rows = []
    for line in lines[k:]:
        vals = line.split()
        if not vals:
            continue
        rows.append([None if (nodata is not None and float(v) == nodata) else float(v) for v in vals])
    if len(rows) != nrows or any(len(r) != ncols for r in rows):
        raise ValueError(f"ESRI ASCII grid: expected {nrows}x{ncols}, got {len(rows)} rows")
    return {"ncols": ncols, "nrows": nrows, "xll": xll, "yll": yll, "cellsize": cs, "nodata": nodata, "rows": rows}


# --- general windows (8/16/32-bit integers and 32/64-bit floats, tiles or strips) --------------------------------

TAG_STRIP_OFFSETS, TAG_ROWS_PER_STRIP, TAG_STRIP_COUNTS, TAG_SAMPLE_FORMAT = 273, 278, 279, 339
TAG_NODATA = 42113  # GDAL_NODATA (ASCII)


def _struct_code(bps: int, fmt: int) -> str:
    """struct code for one sample: SampleFormat 1 unsigned, 2 signed, 3 float."""
    return {(8, 1): "B", (8, 2): "b", (16, 1): "H", (16, 2): "h", (32, 1): "I", (32, 2): "i", (32, 3): "f",
            (64, 3): "d"}[(bps, fmt)]


def decode_block(data: bytes, ifd: dict, endian: str, w: int, h: int) -> tuple:
    """The samples of one tile or strip (w x h, one band) as a tuple of numbers."""
    comp, pred = ifd_int(ifd, TAG_COMPRESSION, 1), ifd_int(ifd, TAG_PREDICTOR, 1)
    bps, fmt = ifd_int(ifd, TAG_BPS, 8), ifd_int(ifd, TAG_SAMPLE_FORMAT, 1)
    if comp == 1:
        raw = data
    elif comp == 5:
        raw = lzw_decode(data)
    elif comp in (8, 32946):
        raw = zlib.decompress(data)
    else:
        raise ValueError(f"unsupported TIFF compression {comp}")
    size = bps // 8
    need = w * h * size
    raw = raw[:need] if len(raw) >= need else raw + bytes(need - len(raw))
    code = _struct_code(bps, fmt)
    if pred == 3:  # floating-point predictor: byte planes, differenced per row
        out = bytearray(need)
        row = w * size
        for r in range(h):
            b = bytearray(raw[r * row:(r + 1) * row])
            for k in range(1, row):
                b[k] = (b[k] + b[k - 1]) & 0xFF
            for x in range(w):
                for j in range(size):
                    # planes are stored most significant byte first
                    out[r * row + x * size + (size - 1 - j if endian == "<" else j)] = b[j * w + x]
        raw = bytes(out)
    vals = struct.unpack(f"{endian}{w * h}{code}", raw)
    if pred == 2:
        mask = (1 << bps) - 1
        signed = fmt == 2
        lst = list(vals)
        for r in range(h):
            acc = 0
            for k in range(r * w, (r + 1) * w):
                acc = (acc + lst[k]) & mask
                lst[k] = acc - (1 << bps) if signed and acc >= 1 << (bps - 1) else acc
        vals = tuple(lst)
    return vals


def geo_of(ifd: dict) -> tuple[float, float, float, float]:
    """(lon of the left edge, lat of the top edge, pixel width, pixel height) of a north-up GeoTIFF."""
    sx, sy = ifd[TAG_PIXEL_SCALE][:2]
    _, _, _, lon_ul, lat_ul, _ = ifd[TAG_TIEPOINT][:6]
    return lon_ul, lat_ul, sx, sy


def read_window(read, ifd: dict, endian: str, bbox: tuple[float, float, float, float], geo=None,
                stride: int = 1) -> dict:
    """The pixels of `ifd` inside bbox (west, south, east, north), every `stride`-th row and column.

    `read(offset, count)` returns file bytes. `geo` = (lon0, lat_top, sx, sy) for an overview IFD that carries no
    georeferencing of its own. Returns {lon0, lat_top, step_x, step_y, cols, rows: [[value]]}: sample (r, c) is
    the pixel whose north-west corner is (lon0 + c * step_x, lat_top - r * step_y).
    """
    lon_ul, lat_ul, sx, sy = geo or geo_of(ifd)
    width, height = ifd_int(ifd, TAG_WIDTH), ifd_int(ifd, TAG_HEIGHT)
    w, s, e, n = bbox
    c0, c1 = max(0, int((w - lon_ul) / sx)), min(width, int((e - lon_ul) / sx) + 1)
    r0, r1 = max(0, int((lat_ul - n) / sy)), min(height, int((lat_ul - s) / sy) + 1)
    keep_c = list(range(c0, c1, stride))
    keep_r = list(range(r0, r1, stride))
    out = {r: [None] * len(keep_c) for r in keep_r}
    if TAG_TILE_W in ifd:
        tw, th = ifd_int(ifd, TAG_TILE_W), ifd_int(ifd, TAG_TILE_H)
        across = -(-width // tw)
        offs, counts = ifd[TAG_TILE_OFFSETS], ifd[TAG_TILE_COUNTS]
        for tr in range(r0 // th, (r1 - 1) // th + 1):
            rows_here = [r for r in keep_r if tr * th <= r < (tr + 1) * th]
            if not rows_here:
                continue
            for tc in range(c0 // tw, (c1 - 1) // tw + 1):
                cols_here = [(j, c) for j, c in enumerate(keep_c) if tc * tw <= c < (tc + 1) * tw]
                if not cols_here:
                    continue
                k = tr * across + tc
                if not counts[k]:
                    continue
                px = decode_block(read(offs[k], counts[k]), ifd, endian, tw, th)
                for r in rows_here:
                    base = (r - tr * th) * tw - tc * tw
                    row = out[r]
                    for j, c in cols_here:
                        row[j] = px[base + c]
    else:
        rps = ifd_int(ifd, TAG_ROWS_PER_STRIP, height)
        offs, counts = ifd[TAG_STRIP_OFFSETS], ifd[TAG_STRIP_COUNTS]
        for sidx in range(r0 // rps, (r1 - 1) // rps + 1):
            rows_here = [r for r in keep_r if sidx * rps <= r < (sidx + 1) * rps]
            if not rows_here:
                continue
            h = min(rps, height - sidx * rps)
            px = decode_block(read(offs[sidx], counts[sidx]), ifd, endian, width, h)
            for r in rows_here:
                base = (r - sidx * rps) * width
                out[r] = [px[base + c] for c in keep_c]
    return {"lon0": lon_ul + c0 * sx, "lat_top": lat_ul - r0 * sy, "step_x": sx * stride, "step_y": sy * stride,
            "cols": len(keep_c), "rows": [out[r] for r in keep_r]}


def local_reader(data: bytes):
    """read(offset, count) over the bytes of a whole file."""
    return lambda off, cnt: data[off:off + cnt]


def open_tiff(data: bytes) -> tuple[str, list[dict]]:
    """(endian, IFDs) of a TIFF held in memory."""
    endian, big, first = tiff_header(data[:16])
    return endian, read_ifds(data, 0, endian, big, first)
