"""Helpers shared by the energy sources (energy_ember, energy_gem, energy_osm, energy_wri).

Kept inside the energy module on purpose: the module uses only pipeline/core (Source, fetch) so it can be copied into
another fork of the engine without the fork's own OSM or spreadsheet helpers.
"""

from __future__ import annotations

import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import zipfile
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

from ..core import fetch
from .energy_config import ENERGY_COUNTRY

# The technologies of the module, in display order. Every plant and every Ember series maps to one of them.
TECHS = ["solar", "wind", "hydro", "coal", "gas", "oil", "nuclear", "biomass", "other"]

_TECH_WORDS = {
    "solar": "solar", "photovoltaic": "solar", "pv": "solar", "utility-scale solar": "solar",
    "wind": "wind",
    "hydro": "hydro", "hydropower": "hydro", "hydroelectric": "hydro", "pumped storage": "hydro",
    "coal": "coal", "lignite": "coal",
    "gas": "gas", "natural gas": "gas", "lng": "gas", "fossil gas": "gas",
    "oil": "oil", "diesel": "oil", "petcoke": "oil", "fuel oil": "oil", "oil/gas": "gas",
    "nuclear": "nuclear",
    "biomass": "biomass", "bioenergy": "biomass", "biogas": "biomass", "biofuel": "biomass", "waste": "biomass",
    "geothermal": "other", "tidal": "other", "wave and tidal": "other", "battery": "other", "storage": "other",
    "cogeneration": "other", "other": "other",
}


def tech_of(*words) -> str | None:
    """The module technology of the first word that names one ("Hydro", "plant:source=hydro", "oil/gas")."""
    for w in words:
        k = str(w or "").split(";")[0].strip().lower()
        if k in _TECH_WORDS:
            return _TECH_WORDS[k]
    return None


_UNITS = {"w": 1e-6, "kw": 1e-3, "kwp": 1e-3, "mw": 1.0, "mwp": 1.0, "mwe": 1.0, "mwac": 1.0, "mwdc": 1.0,
          "gw": 1e3, "gwp": 1e3}


def parse_mw(text) -> float | None:
    """'1200 MW', '50.5', '1,2 GW', '30 MWp' -> MW; a bare number is MW; anything else None."""
    if text is None:
        return None
    s = str(text).strip().lower().replace(" ", "")
    m = re.fullmatch(r"([0-9]+(?:[.,][0-9]+)?)([a-z]*)", s)
    if not m:
        return None
    unit = m.group(2) or "mw"
    if unit not in _UNITS:
        return None
    v = float(m.group(1).replace(",", ".")) * _UNITS[unit]
    return v if v > 0 else None


def year_of(*texts) -> int | None:
    """The first four-digit year 1880-2099 in the texts ('2019-06-30', '2019.0', 'about 1994')."""
    for t in texts:
        m = re.search(r"(?<!\d)(18[89]\d|19\d\d|20\d\d)(?!\d)", str(t or ""))
        if m:
            return int(m.group(1))
    return None


# ---------------------------------------------------------------------------------------------- Overpass (OSM)
OVERPASS_ENDPOINTS = ("https://overpass-api.de/api/interpreter",
                      "https://maps.mail.ru/osm/tools/overpass/api/interpreter")


def country_area() -> str:
    return f'area["ISO3166-1"="{ENERGY_COUNTRY["iso2"]}"][admin_level=2]->.c;'


def bands() -> list[tuple[float, float, float, float]]:
    """The country bbox cut into latitude bands (south, west, north, east)."""
    s, w, n, e = ENERGY_COUNTRY["bbox"]
    step = float(ENERGY_COUNTRY.get("band_deg") or 2.0)
    out, lat = [], s
    while lat < n:
        out.append((round(lat, 4), w, round(min(n, lat + step), 4), e))
        lat += step
    return out


def overpass_ok(path: Path) -> bool:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    remark = str(doc.get("remark") or "")
    return isinstance(doc, dict) and "elements" in doc and not re.search(r"runtime error|timed out|out of memory", remark, re.I)


def overpass(source, query: str, rel_path: str, *, force: bool = False, rounds: int = 4, wait: float = 20.0) -> Path:
    """Run an Overpass QL query through Source.download (cached in data/raw/<id>/<rel_path>); retry busy servers."""
    path = source.raw_dir / rel_path
    if path.exists() and not force and overpass_ok(path):
        return path
    if source.offline:
        raise fetch.OfflineError(f"--offline: {source.id}/{rel_path} is not cached (Overpass query)")
    last = "no attempt"
    for _ in range(rounds):
        for ep in OVERPASS_ENDPOINTS:
            url = ep + "?" + urllib.parse.urlencode({"data": query})
            try:
                got = source.download(url, rel_path, force=True)
            except urllib.error.HTTPError as exc:
                exc.close()
                last = f"{ep}: HTTP {exc.code}"
                if exc.code not in (429, 502, 503, 504):
                    raise
                continue
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as exc:
                last = f"{ep}: {exc}"
                continue
            if overpass_ok(got):
                return got
            last = f"{ep}: incomplete answer"
            source.discard(rel_path)
        print(f"      Overpass busy ({last}); waiting {wait:g}s")
        time.sleep(wait)
        wait *= 2
    raise RuntimeError(f"Overpass query for {source.id}/{rel_path} failed: {last}")


# ---------------------------------------------------------------------------------------------- spreadsheets
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_rows(path: Path) -> Iterator[tuple[str, list]]:
    """(sheet name, row) for every row of an .xlsx file, sheet by sheet, standard library only. The sheets are
    streamed (a 200 MB sheet of every country reads in seconds with little memory); the shared strings are loaded."""
    m = f"{{{_NS['m']}}}"
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            with z.open("xl/sharedStrings.xml") as f:
                for _, el in ET.iterparse(f):
                    if el.tag == m + "si":
                        shared.append("".join(t.text or "" for t in el.iter(m + "t")))
                        el.clear()
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels}
        for sh in wb.find("m:sheets", _NS):
            t = target[sh.get(_REL)].lstrip("/")
            part = t if t.startswith("xl/") else "xl/" + t
            with z.open(part) as f:
                for _, row in ET.iterparse(f):
                    if row.tag != m + "row":
                        continue
                    cells = {}
                    for c in row.findall(m + "c"):
                        v = c.find(m + "v")
                        kind = c.get("t")
                        if kind == "inlineStr":
                            val = "".join(x.text or "" for x in c.iter(m + "t"))
                        elif v is None:
                            continue
                        elif kind == "s":
                            val = shared[int(v.text)]
                        elif kind in ("str", "b", "e"):
                            val = v.text
                        else:
                            try:
                                val = float(v.text)
                            except (TypeError, ValueError):
                                val = v.text
                        cells[_col(c.get("r"))] = val
                    row.clear()
                    if cells:
                        yield sh.get("name"), [cells.get(i) for i in range(max(cells) + 1)]


def xlsx_sheets(path: Path) -> dict[str, list[list]]:
    """{sheet name: rows (lists of str/float/None)} of a small .xlsx file."""
    out: dict[str, list[list]] = {}
    for sheet, row in xlsx_rows(path):
        out.setdefault(sheet, []).append(row)
    return out


def table_with(rows: list[list], *needles: str) -> tuple[list[str], list[list]] | None:
    """(header, data rows) of the first row whose cells contain every needle (case-insensitive), else None."""
    for k, row in enumerate(rows[:30]):
        head = [str(c or "").strip() for c in row]
        low = [h.lower() for h in head]
        if all(any(n.lower() in h for h in low) for n in needles):
            return head, rows[k + 1:]
    return None
