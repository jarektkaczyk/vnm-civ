"""A minimal XLSX value reader (standard library only), for the people and economy sources.

Reads cell values, not formatting: shared and inline strings, numbers, booleans and cached formula results.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def sheet_names(path: str | Path) -> list[str]:
    with zipfile.ZipFile(path) as book:
        root = ET.fromstring(book.read("xl/workbook.xml"))
    return [s.attrib["name"] for s in root.findall("x:sheets/x:sheet", _NS)]


def read_xlsx(path: str | Path, sheet: int | str = 0) -> list[list[object]]:
    """Rows of one worksheet (by name or index) as lists of values (None for empty cells)."""
    with zipfile.ZipFile(path) as book:
        wb = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        sheets = [(s.attrib["name"], target[s.attrib[_REL]]) for s in wb.findall("x:sheets/x:sheet", _NS)]
        if isinstance(sheet, str):
            match = [t for n, t in sheets if n == sheet]
            if not match:
                raise KeyError(f"worksheet {sheet!r} not found")
            t = match[0]
        else:
            t = sheets[sheet][1]
        t = t.lstrip("/")
        member = t if t.startswith("xl/") else "xl/" + t
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            ss = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(n.text or "" for n in si.iter("{%s}t" % _NS["x"])) for si in ss.findall("x:si", _NS)]
        root = ET.fromstring(book.read(member))
    rows = []
    for row in root.findall("x:sheetData/x:row", _NS):
        vals: list[object] = []
        for c in row.findall("x:c", _NS):
            i = _col(c.attrib["r"])
            while len(vals) <= i:
                vals.append(None)
            kind = c.attrib.get("t")
            v = c.find("x:v", _NS)
            raw = v.text if v is not None else None
            if kind == "inlineStr":
                val: object = "".join(n.text or "" for n in c.iter("{%s}t" % _NS["x"]))
            elif raw is None:
                val = None
            elif kind == "s":
                val = shared[int(raw)]
            elif kind in ("str", "e"):
                val = raw
            elif kind == "b":
                val = raw == "1"
            else:
                f = float(raw)
                val = int(f) if f.is_integer() else f
            vals[i] = val
        rows.append(vals)
    return rows
