"""Global Energy Monitor, Global Integrated Power Tracker: power units of the ENERGY_COUNTRY with position, capacity,
technology, status, start year and retirement year. The main plant source of the module when its file is cached.

GEM hands the file out only through a request form (name, email, organisation), so the pipeline never downloads it.
The owner downloads the tracker spreadsheet (for example Global-Integrated-Power-<Month>-<Year>.xlsx) by hand into
data/raw/energy_gem/. fetch and process record that file in the folder's manifest.json (sha256, bytes, file date).
The source exists only while such a file is there; without it the module runs on OpenStreetMap and WRI
(pipeline/build/energy.py). The file holds every country; the reader streams it and keeps the rows of the country.

Rows with a TransitionZero ID ("TZ: ...") in "Other IDs (unit/phase)" come partly or fully from the TransitionZero
Solar Asset Mapper (CC BY-NC 4.0). Their plants carry `tz`, and the source energy_gem_tz credits TransitionZero.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..core.fetch import manifest_path, read_manifest
from ..core.paths import RAW
from ..core.source import Source, SourceInfo
from ..core.store import atomic_write_text
from .energy_common import table_with, tech_of, xlsx_rows, year_of
from .energy_config import ENERGY_COUNTRY

FOLDER = RAW / "energy_gem"
DOWNLOAD = "https://globalenergymonitor.org/projects/global-integrated-power-tracker/download-data/"
# Statuses kept: the plant exists or existed. Planned units (announced, pre-construction, construction) are kept as
# "planned": the builder never draws them, but they absorb the records of other sources with the same name (an OSM
# object of a plant still in construction). Cancelled and shelved units are left out.
KEEP = {"operating": "operating", "retired": "retired", "mothballed": "retired", "announced": "planned",
        "pre-construction": "planned", "construction": "planned"}


def gem_file() -> Path | None:
    files = sorted([*FOLDER.glob("*.xlsx"), *FOLDER.glob("*.csv")], key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _pick(head: list[str], *names: str) -> int | None:
    low = [h.lower() for h in head]
    for n in names:
        for i, h in enumerate(low):
            if h == n.lower():
                return i
    for n in names:
        for i, h in enumerate(low):
            if n.lower() in h:
                return i
    return None


def record(path: Path, source_id: str = "energy_gem") -> dict:
    """The manifest entry of the hand-downloaded file in the manifest of `source_id`: sha256, bytes and the file date.
    Recomputed only when the file changed (size or date)."""
    manifest = read_manifest(source_id)
    st = path.stat()
    when = datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")
    entry = manifest.get(path.name)
    if entry and entry.get("bytes") == st.st_size and entry.get("retrieved") == when:
        return entry
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    manifest[path.name] = {"url": DOWNLOAD, "sha256": digest.hexdigest(), "bytes": st.st_size, "retrieved": when,
                           "manual": "downloaded by hand through the GEM form; the pipeline never fetches it"}
    manifest_path(source_id).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path(source_id), json.dumps(manifest, indent=2, sort_keys=True))
    return manifest[path.name]


def release(path: Path) -> str:
    """'September 2026' from Global-Integrated-Power-September-2026-V2.xlsx, else the file name."""
    m = re.search(r"([A-Z][a-z]+)-(20\d\d)", path.stem)
    return f"{m.group(1)} {m.group(2)}" if m else path.stem


def _rows(path: Path) -> tuple[list[str], list[list]]:
    """(header, rows of the ENERGY_COUNTRY) of the first table with Capacity (MW), Latitude and Status. The .xlsx
    sheet is streamed and filtered row by row, so the rows of other countries are never kept."""
    names = {n.lower() for n in ENERGY_COUNTRY.get("gem_names", [])}
    if path.suffix.lower() == ".csv":
        got = table_with(list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines())), "capacity", "latitude")
        if got:
            return got
    else:
        head, sheet, seen, out, ci = None, None, 0, [], None
        for name, row in xlsx_rows(path):
            if head is not None and name != sheet:
                break
            if head is None:
                seen = seen + 1 if name == sheet else 1
                sheet = name
                got = table_with([row], "capacity (mw)", "latitude", "status") if seen <= 30 else None
                if got:
                    head = got[0]
                    ci = _pick(head, "Country/area", "Country/Area", "Country")
                continue
            if ci is not None and ci < len(row) and str(row[ci] or "").strip().lower() in names:
                out.append(row)
        if head is not None:
            return head, out
    raise ValueError(f"{path.name}: no sheet with Capacity (MW), Latitude and Status columns")


def gem_points(head: list[str], rows: list[list]) -> list[dict]:
    col = {k: _pick(head, *names) for k, names in {
        "country": ("Country/area", "Country/Area", "Country"), "type": ("Type",), "fuel": ("Fuel",),
        "tech": ("Technology",), "mw": ("Capacity (MW)",), "status": ("Status",), "start": ("Start year",),
        "end": ("Retired year",), "lat": ("Latitude",), "lon": ("Longitude",),
        "name": ("Plant / Project name", "Project Name", "Plant name"), "unit": ("Unit / Phase name", "Unit name"),
        "local": ("Plant / Project name (local)",), "other": ("Other IDs (unit/phase)",),
        "alias": ("Plant / Project name (other)",), "owner": ("Owner(s)",),
        "id": ("GEM unit/phase ID", "GEM unit ID", "GEM phase ID"), "loc": ("GEM location ID",)}.items()}
    names = {n.lower() for n in ENERGY_COUNTRY.get("gem_names", [])}
    get = lambda r, k: r[col[k]] if col[k] is not None and col[k] < len(r) else None  # noqa: E731
    out = []
    for r in rows:
        if str(get(r, "country") or "").strip().lower() not in names:
            continue
        status = KEEP.get(str(get(r, "status") or "").strip().lower().split(" - ")[0])
        tech = tech_of(get(r, "type"), get(r, "fuel"), get(r, "tech"))
        try:
            lat, lon = float(get(r, "lat")), float(get(r, "lon"))
        except (TypeError, ValueError):
            continue
        if status is None or tech is None:
            continue
        fuel = str(get(r, "fuel") or "").lower()
        if tech == "gas" and "fossil liquids" in fuel and "fossil gas" not in fuel:
            tech = "oil"  # "oil/gas" units that burn only oil
        try:
            mw = float(get(r, "mw"))
        except (TypeError, ValueError):
            mw = None
        out.append({"loc": get(r, "loc"), "unit": get(r, "id"), "tech": tech, "name": get(r, "name") or None,
                    "unit_name": get(r, "unit") or None,
                    "name_local": get(r, "local") or None, "tz": "TZ" in str(get(r, "other") or ""),
                    "aliases": [a.strip() for a in str(get(r, "alias") or "").split(",") if a.strip()],
                    "owner": str(get(r, "owner") or "").strip() or None,
                    "mw": mw if mw else None, "start": year_of(get(r, "start")), "end": year_of(get(r, "end")),
                    "status": status, "lon": round(lon, 5), "lat": round(lat, 5)})
    return plants(out)


FAMILY = {"oil": "gas"}  # oil and gas units of one location are one plant
_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6"}


def phase(unit_name) -> str | None:
    """The phase number of a GEM unit name: "Phase 2 Unit 1", "Phase II", "Unit 2-1", "Unit 2 Extension", "2" and
    "2-1" -> "2". A plain "Unit 2" has none (a unit, not a phase)."""
    text = str(unit_name or "").lower()
    m = (re.search(r"\bphase\s+([0-9]+|[ivx]+)\b", text) or re.search(r"\bunit\s+([0-9]+)\s*[-:.]\s*[0-9]+", text)
         or re.search(r"\bunit\s+([0-9]+)\s+extension", text) or re.match(r"\s*([0-9]+)\b", text))
    if not m:
        return None
    return _ROMAN.get(m.group(1), m.group(1) if m.group(1).isdigit() else None)


def plants(units: list[dict]) -> list[dict]:
    """GEM rows are units: the units of one plant (GEM location ID, else the same name, technology and position)
    become one plant; oil and gas units of one location are one plant of the larger technology, with the sum of
    both (FAMILY). Its capacity is the sum of its operating units (else of its retired units, else of its planned
    units), its start the first start year of those units, its end the last retirement year once no unit operates.
    Its status is operating, retired (no unit operates, one retired) or planned.
    `aliases` are the other names of its units ("Plant / Project name (other)"), `owner` the owners of the first unit
    that names them. `tz` is true when any unit has a TransitionZero ID; `parts` lists the phase numbers of the units (phase()), so the
    builder can tell that "Vinh Tan 2" of another source is a part of "Vinh Tan power station"."""
    groups: dict = {}
    for u in units:
        key = u["loc"] or (u["name"], u["tech"], u["lon"], u["lat"])
        groups.setdefault((key, FAMILY.get(u["tech"], u["tech"])), []).append(u)
    out = []
    for (key, _), us in groups.items():
        live = [u for u in us if u["status"] == "operating"]
        gone = [u for u in us if u["status"] == "retired"]
        use = live or gone or us
        mws = [u["mw"] for u in use if u["mw"]]
        starts = [u["start"] for u in use if u["start"]]
        ends = [u["end"] for u in us if u["end"]]
        first = us[0]
        by_tech: dict = {}
        for u in use:
            by_tech[u["tech"]] = by_tech.get(u["tech"], 0) + (u["mw"] or 0)
        tech = max(by_tech, key=lambda t: (by_tech[t], t))  # oil and gas units of one location: the larger one
        out.append({"id": f"gem:{first['loc'] or first['unit'] or len(out)}", "tech": tech, "name": first["name"],
                    "name_local": next((u["name_local"] for u in us if u.get("name_local")), None),
                    "tz": any(u.get("tz") for u in us),
                    "aliases": sorted({a for u in us for a in u.get("aliases") or ()}),
                    "owner": next((u["owner"] for u in us if u.get("owner")), None),
                    "parts": sorted({n for u in us if (n := phase(u.get("unit_name")))}),
                    "mw": round(sum(mws), 2) if mws else None, "start": min(starts) if starts else None,
                    "end": None if live else (max(ends) if ends else None),
                    "status": "operating" if live else "retired" if gone else "planned", "units": len(us),
                    "lon": first["lon"], "lat": first["lat"]})
    return out


class EnergyGem(Source):
    info = SourceInfo(
        id="energy_gem",
        title="Global Integrated Power Tracker",
        publisher="Global Energy Monitor",
        homepage="https://globalenergymonitor.org/projects/global-integrated-power-tracker/",
        license="CC BY 4.0",
        description="Power plants and their units with position, capacity, technology, status, start year and "
        "retirement year.",
        used_for=["Power plants by year", "Power capacity", "Power plants on the map"],
    ) if gem_file() else None

    def fetch(self, force=False):
        path = gem_file()
        if not path:
            print("    GEM needs a form: download the tracker spreadsheet by hand into data/raw/energy_gem/")
            return
        print(f"    {path.name}: hand-downloaded, sha256 {record(path)['sha256'][:12]}")

    def process(self):
        path = gem_file()
        if path is None:
            raise FileNotFoundError("data/raw/energy_gem/ has no tracker file (GEM needs a form)")
        record(path)
        points = gem_points(*_rows(path))
        print(f"    {path.name}: {len(points)} plants, {sum(1 for p in points if p['tz'])} with a TransitionZero ID")
        # The citation GEM asks for (About sheet of the file).
        return {"vintage": f"Global Energy Monitor, Global Integrated Power Tracker, {release(path)} release.",
                "points": points,
                "_files": [path.name]}


class EnergyGemTz(Source):
    """TransitionZero, Solar Asset Mapper: the source of the GEM solar rows with a TZ ID. Nothing to fetch; listed in
    the Almanac next to GEM for its licence, citing the GEM file that carries those rows."""

    info = SourceInfo(
        id="energy_gem_tz",
        title="Solar Asset Mapper",
        publisher="TransitionZero",
        homepage="https://www.transitionzero.org/",
        license="CC BY-NC 4.0",
        description="Solar farms found in satellite images. Part of the solar farms of the Global Integrated Power "
        "Tracker come from it.",
        used_for=["Power plants by year", "Power capacity", "Power plants on the map"],
    ) if gem_file() else None

    def fetch(self, force=False):
        record(gem_file(), self.id)

    def process(self):
        path = gem_file()
        record(path, self.id)
        return {"vintage": "Solar Asset Mapper, August 2025", "_files": [path.name]}
