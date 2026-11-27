"""A small PDF text reader (standard library only), enough for statistical tables printed from a word processor.

It finds every object (plain and inside object streams) by scanning the file, walks the page tree from the catalogue,
decodes Flate content streams, maps glyph codes to text through each font's ToUnicode CMap, and returns the text
pieces of a page with their positions. `page_rows()` groups the pieces into lines (same baseline), left to right.

Not supported: encrypted files, LZW or other filters on content streams, vertical writing.
"""

from __future__ import annotations

import re
import zlib
from functools import lru_cache

_OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b")
_REF = re.compile(rb"(\d+)\s+(\d+)\s+R")


class Pdf:
    def __init__(self, data: bytes):
        self.data = data
        self.offsets: dict[int, int] = {}
        for m in _OBJ.finditer(data):
            self.offsets[int(m.group(1))] = m.end()  # the last definition wins (incremental updates)
        self.packed: dict[int, tuple[int, int]] = {}  # object number -> (object stream number, index)
        self._streams: dict[int, list[bytes]] = {}
        for num in list(self.offsets):
            head = self._raw_head(num)
            if b"/ObjStm" in head:
                for k, n in enumerate(self._objstm_numbers(num)):
                    self.packed.setdefault(n, (num, k))
        self.pages = self._page_list()

    # --- objects ---------------------------------------------------------------------------------------------------
    def _raw_head(self, num: int) -> bytes:
        start = self.offsets[num]
        end = self.data.find(b"stream", start, start + 4000)
        endobj = self.data.find(b"endobj", start)
        if end < 0 or (0 <= endobj < end):
            end = endobj
        return self.data[start:end]

    def _stream_of(self, num: int) -> bytes:
        start = self.offsets[num]
        head_end = self.data.find(b"stream", start)
        dict_text = self.data[start:head_end]
        p = head_end + len(b"stream")
        if self.data[p:p + 2] == b"\r\n":
            p += 2
        elif self.data[p:p + 1] in (b"\n", b"\r"):
            p += 1
        length = self._length(dict_text)
        raw = self.data[p:p + length] if length else self.data[p:self.data.find(b"endstream", p)]
        if b"/FlateDecode" in dict_text:
            return zlib.decompressobj().decompress(raw)
        return raw

    def _length(self, dict_text: bytes) -> int | None:
        m = re.search(rb"/Length\s+(\d+)\s+(\d+)\s+R", dict_text)
        if m:
            v = self.obj(int(m.group(1)))
            return int(v.strip()) if v.strip().isdigit() else None
        m = re.search(rb"/Length\s+(\d+)", dict_text)
        return int(m.group(1)) if m else None

    def _objstm_numbers(self, num: int) -> list[int]:
        body = self._objstm(num)
        return [n for n, _ in body]

    def _objstm(self, num: int) -> list[tuple[int, bytes]]:
        if num in self._streams:
            return self._streams[num]
        head = self._raw_head(num)
        n = int(re.search(rb"/N\s+(\d+)", head).group(1))
        first = int(re.search(rb"/First\s+(\d+)", head).group(1))
        data = self._stream_of(num)
        nums = list(map(int, data[:first].split()))
        pairs = [(nums[2 * k], nums[2 * k + 1]) for k in range(n)]
        out = []
        for k, (onum, off) in enumerate(pairs):
            end = pairs[k + 1][1] if k + 1 < n else len(data) - first
            out.append((onum, data[first + off:first + end]))
        self._streams[num] = out
        return out

    def obj(self, num: int) -> bytes:
        """The object's text (its dictionary or value; a stream's dictionary only)."""
        if num in self.offsets:
            return self._raw_head(num)
        if num in self.packed:
            sn, k = self.packed[num]
            return self._objstm(sn)[k][1]
        return b""

    def resolve(self, text: bytes) -> bytes:
        m = re.fullmatch(rb"\s*(\d+)\s+(\d+)\s+R\s*", text)
        return self.obj(int(m.group(1))) if m else text

    def value(self, dict_text: bytes, key: bytes) -> bytes | None:
        """The raw value of /key in a dictionary text (a reference, a name, a number, an array or a dictionary)."""
        m = re.search(rb"/" + key + rb"(?![A-Za-z])\s*", dict_text)
        if not m:
            return None
        p = m.end()
        c = dict_text[p:p + 1]
        if c == b"<" and dict_text[p:p + 2] == b"<<":
            depth, q = 0, p
            while q < len(dict_text):
                if dict_text[q:q + 2] == b"<<":
                    depth += 1
                    q += 2
                elif dict_text[q:q + 2] == b">>":
                    depth -= 1
                    q += 2
                    if depth == 0:
                        return dict_text[p:q]
                else:
                    q += 1
            return dict_text[p:]
        if c == b"[":
            q = dict_text.find(b"]", p)
            return dict_text[p:q + 1]
        m2 = re.match(rb"(\d+\s+\d+\s+R|/[^\s/<>\[\]()]+|[-\d.]+)", dict_text[p:])
        return m2.group(1) if m2 else None

    # --- pages -----------------------------------------------------------------------------------------------------
    def _page_list(self) -> list[bytes]:
        root = None
        for num in list(self.offsets) + list(self.packed):
            o = self.obj(num)
            if re.search(rb"/Type\s*/Catalog", o):
                root = o
                break
        pages_ref = self.value(root, b"Pages")
        out: list[bytes] = []

        def walk(text: bytes, seen: set):
            kids = self.value(text, b"Kids")
            if kids is None:
                out.append(text)
                return
            for m in _REF.finditer(kids):
                n = int(m.group(1))
                if n in seen:
                    continue
                seen.add(n)
                walk(self.obj(n), seen)

        walk(self.resolve(pages_ref), set())
        return out

    def _inherited(self, page: bytes, key: bytes) -> bytes | None:
        v = self.value(page, key)
        while v is None:
            parent = self.value(page, b"Parent")
            if parent is None:
                return None
            page = self.resolve(parent)
            v = self.value(page, key)
        return v

    @lru_cache(maxsize=4096)
    def _cmap(self, font_ref: bytes) -> tuple[dict[int, str], int]:
        """(code -> text, code bytes) of a font."""
        font = self.resolve(font_ref)
        two = b"/Type0" in font or b"Identity-H" in font
        cmap: dict[int, str] = {}
        tu = self.value(font, b"ToUnicode")
        if tu is not None and _REF.match(tu):
            text = self._stream_of(int(_REF.match(tu).group(1))).decode("latin-1")
            for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
                for a, b in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
                    cmap[int(a, 16)] = _utf16(b)
            for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
                for m in re.finditer(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]+>)", block):
                    lo, hi, dst = int(m.group(1), 16), int(m.group(2), 16), m.group(3)
                    if dst.startswith("["):
                        for k, h in enumerate(re.findall(r"<([0-9A-Fa-f]+)>", dst)):
                            cmap[lo + k] = _utf16(h)
                    else:
                        base = int(dst[1:-1], 16)
                        for k in range(hi - lo + 1):
                            cmap[lo + k] = chr(base + k) if base + k < 0x110000 else ""
            m = re.search(r"begincodespacerange\s*<([0-9A-Fa-f]+)>", text)
            if m:
                two = len(m.group(1)) >= 4
        return cmap, 2 if two else 1

    def page_text(self, index: int) -> list[tuple[float, float, str]]:
        """Text pieces (x, y, text) of page `index` (0-based), y up as in PDF space."""
        page = self.pages[index]
        res = self.resolve(self._inherited(page, b"Resources") or b"<<>>")
        fonts = self.resolve(self.value(res, b"Font") or b"<<>>")
        font_refs = {m.group(1): m.group(2) for m in re.finditer(rb"/([^\s/<>\[\]]+)\s+(\d+\s+\d+\s+R)", fonts)}
        contents = self.value(page, b"Contents") or b""
        streams = b"".join(self._stream_of(int(m.group(1))) + b"\n" for m in _REF.finditer(contents))
        return _run(streams, lambda name: self._cmap(font_refs[name]) if name in font_refs else ({}, 1))

    def page_rows(self, index: int, tol: float = 2.0) -> list[list[tuple[float, str]]]:
        """Lines of page `index`, top to bottom; each a list of (x, text) left to right."""
        pieces = sorted(self.page_text(index), key=lambda p: (-p[1], p[0]))
        rows: list[list[tuple[float, float, str]]] = []
        for x, y, s in pieces:
            if not s.strip():
                continue
            if rows and abs(rows[-1][0][1] - y) <= tol:
                rows[-1].append((x, y, s))
            else:
                rows.append([(x, y, s)])
        return [[(x, s) for x, _, s in sorted(r)] for r in rows]


def _single(c: int) -> str:
    """A one-byte code with no ToUnicode entry: Windows-1252 (the encoding word processors write)."""
    if c < 32:
        return ""
    try:
        return bytes([c]).decode("cp1252")
    except UnicodeDecodeError:
        return chr(c)


def merge_cells(row: list[tuple[float, str]], char_w: float = 4.3, gap: float = 2.5) -> list[tuple[float, str]]:
    """Join the pieces of a line that touch (a number printed in several pieces) into cells. A piece's width is
    estimated as len(text) * char_w (table digits are about 4.2 points wide at 8 points)."""
    out: list[list] = []
    for x, s in row:
        if out:
            px, ps, pend = out[-1]
            if x - pend <= gap:
                out[-1] = [px, ps + s, x + len(s) * char_w]
                continue
        out.append([x, s, x + len(s) * char_w])
    return [(x, s) for x, s, _ in out]


def _utf16(h: str) -> str:
    try:
        return bytes.fromhex(h).decode("utf-16-be")
    except (ValueError, UnicodeDecodeError):
        return ""


_TOKEN = re.compile(rb"\s*(\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/<>\[\]()]+|[-+]?(?:\d+\.?\d*|\.\d+)|[A-Za-z'\"*]+\d*)", re.S)


def _string_bytes(tok: bytes) -> bytes:
    if tok.startswith(b"<"):
        return bytes.fromhex(re.sub(rb"\s", b"", tok[1:-1]).decode() + ("0" if len(re.sub(rb"\s", b"", tok[1:-1])) % 2 else ""))
    s = tok[1:-1]
    out = bytearray()
    k = 0
    while k < len(s):
        c = s[k]
        if c == 0x5C and k + 1 < len(s):
            n = s[k + 1]
            esc = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}
            if n in esc:
                out.append(esc[n])
                k += 2
            elif 0x30 <= n <= 0x37:
                m = re.match(rb"[0-7]{1,3}", s[k + 1:k + 4])
                out.append(int(m.group(0), 8) & 0xFF)
                k += 1 + len(m.group(0))
            elif n in (10, 13):
                k += 2
            else:
                out.append(n)
                k += 2
        else:
            out.append(c)
            k += 1
    return bytes(out)


def _mul(a, b):
    return (a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2],
            a[2] * b[1] + a[3] * b[3], a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5])


def _run(content: bytes, font_of) -> list[tuple[float, float, str]]:
    out = []
    ctm = (1, 0, 0, 1, 0, 0)
    stack = []
    tm = tlm = (1, 0, 0, 1, 0, 0)
    leading = 0.0
    cmap, width = {}, 1
    ops: list = []

    def decode(bs: bytes) -> str:
        if width == 2:
            codes = [int.from_bytes(bs[k:k + 2], "big") for k in range(0, len(bs) - 1, 2)]
        else:
            codes = list(bs)
        return "".join(cmap.get(c, _single(c) if width == 1 else "") for c in codes)

    def emit(text: str):
        if not text:
            return
        m = _mul(tm, ctm)
        out.append((round(m[4], 2), round(m[5], 2), text))

    for m in _TOKEN.finditer(content):
        tok = m.group(1)
        c = tok[:1]
        if c in b"(<" or c == b"[" or c == b"]" or c == b"/" or re.fullmatch(rb"[-+]?(?:\d+\.?\d*|\.\d+)", tok):
            ops.append(tok)
            continue
        op = tok
        nums = [float(x) for x in ops if re.fullmatch(rb"[-+]?(?:\d+\.?\d*|\.\d+)", x)]
        if op == b"q":
            stack.append(ctm)
        elif op == b"Q":
            ctm = stack.pop() if stack else ctm
        elif op == b"cm" and len(nums) >= 6:
            ctm = _mul(tuple(nums[-6:]), ctm)
        elif op == b"BT":
            tm = tlm = (1, 0, 0, 1, 0, 0)
        elif op == b"Tf":
            names = [x for x in ops if x.startswith(b"/")]
            if names:
                cmap, width = font_of(names[-1][1:])
        elif op == b"Tm" and len(nums) >= 6:
            tm = tlm = tuple(nums[-6:])
        elif op in (b"Td", b"TD") and len(nums) >= 2:
            tx, ty = nums[-2:]
            if op == b"TD":
                leading = -ty
            tlm = _mul((1, 0, 0, 1, tx, ty), tlm)
            tm = tlm
        elif op == b"TL" and nums:
            leading = nums[-1]
        elif op == b"T*":
            tlm = _mul((1, 0, 0, 1, 0, -leading), tlm)
            tm = tlm
        elif op in (b"Tj", b"'", b'"'):
            if op != b"Tj":
                tlm = _mul((1, 0, 0, 1, 0, -leading), tlm)
                tm = tlm
            strs = [x for x in ops if x[:1] in b"(<"]
            if strs:
                emit(decode(_string_bytes(strs[-1])))
        elif op == b"TJ":
            parts, buf = [], ""
            for x in ops:
                if x[:1] in b"(<" and x != b"[":
                    buf += decode(_string_bytes(x))
                elif re.fullmatch(rb"[-+]?(?:\d+\.?\d*|\.\d+)", x) and float(x) < -180:
                    buf += " "
            emit(buf)
        ops = []
    return out
