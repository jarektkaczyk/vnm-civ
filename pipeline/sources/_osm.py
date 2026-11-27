"""Helpers shared by the OpenStreetMap sources (transport, power plants).

Not a source itself (no Source subclass), so the registry ignores it.

* Overpass (OpenStreetMap) queries: cached through Source.download(), several public endpoints,
  backoff on 429/502/504, and a check that the answer is a complete JSON result (Overpass answers a
  query that ran out of time with HTTP 200 and a "remark", which must never be cached as data).
* Eurostat dissemination API (JSON-stat 2.0): one cached request per filtered extract, decoded to
  {(dim value, ...): value}.
* Wikidata entity data (coordinates of curated sites by QID).
* Geometry: great-circle lengths, way chaining and Douglas-Peucker simplification in metres.
"""

from __future__ import annotations

import http.client
import json
import math
import re
import time
import urllib.error
import urllib.parse
from pathlib import Path

from ..core import fetch

# Public Overpass instances, tried in this order. Queries are tiled so that each one answers in well
# under a minute (some networks drop a request that sends no byte for 60 s).
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
OVERPASS_ROUNDS = 4  # passes over all endpoints before giving up
OVERPASS_WAIT = 20.0  # seconds after a busy answer (429/502/504); doubles each round
VN_AREA = 'area["ISO3166-1"="VN"][admin_level=2]->.vn;'
# Tiles (south, west, north, east) covering Vietnam's mainland and coastal islands (bands of 2 degrees of latitude,
# each as wide as the country is there).
VN_TILES = [(8.0, 102.0, 10.0, 107.5), (10.0, 102.0, 12.0, 109.5), (12.0, 105.0, 14.0, 109.5),
            (14.0, 106.5, 16.0, 109.5), (16.0, 104.5, 18.0, 108.5), (18.0, 103.5, 20.0, 107.0),
            (20.0, 102.0, 22.0, 108.2), (22.0, 102.0, 23.5, 106.9)]

EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

ODBL_NOTE = ("Map data (c) OpenStreetMap contributors, available under the Open Database Licence (ODbL 1.0), "
             "https://www.openstreetmap.org/copyright")


# --- Overpass -------------------------------------------------------------------------------------


class OverpassError(RuntimeError):
    """No endpoint returned a complete answer."""


def overpass_ok(path: Path) -> str | None:
    """None if the cached file is a complete Overpass JSON answer, else the reason it is not."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"not JSON ({exc})"
    if not isinstance(doc, dict) or "elements" not in doc:
        return "no 'elements' key"
    remark = str(doc.get("remark") or "")
    if re.search(r"runtime error|timed out|out of memory|Query run out", remark, re.I):
        return f"incomplete answer: {remark[:160]}"
    return None


def overpass(source, query: str, rel_path: str, *, force: bool = False, sleep=time.sleep) -> Path:
    """Run an Overpass QL `query` (JSON output) and cache the answer as data/raw/<id>/<rel_path>.

    Cached answers are reused (no request). A busy server (429, 502, 504 after core.fetch's own
    retries) or an incomplete answer moves on to the next endpoint, then waits and tries another round.
    """
    path = source.raw_dir / rel_path
    if path.exists() and not force:
        return path
    if source.offline:
        raise fetch.OfflineError(f"--offline: {source.id}/{rel_path} is not cached (Overpass query)")
    wait = OVERPASS_WAIT
    last = "no attempt"
    for rnd in range(OVERPASS_ROUNDS):
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
            bad = overpass_ok(got)
            if bad is None:
                return got
            last = f"{ep}: {bad}"
            source.discard(rel_path)
        print(f"      Overpass busy ({last}); waiting {wait:g}s")
        sleep(wait)
        wait *= 2
    raise OverpassError(f"Overpass query for {source.id}/{rel_path} failed: {last}")


def overpass_tiled(source, body: str, folder: str, *, force: bool = False, pause: float = 2.0,
                   out: str = "out tags geom qt;") -> list[Path]:
    """Run `body` (Overpass statements that use {bbox} and the Vietnam area set `.vn`) once per tile."""
    paths = []
    for i, (s, w, n, e) in enumerate(VN_TILES):
        q = f"[out:json][timeout:180];{VN_AREA}(" + body.format(bbox=f"{s},{w},{n},{e}") + f");{out}"
        rel = f"{folder}/tile_{s:g}_{w:g}.json"
        cached = (source.raw_dir / rel).exists() and not force
        paths.append(overpass(source, q, rel, force=force))
        if not cached and i < len(VN_TILES) - 1:
            time.sleep(pause)  # be polite between tiles
    return paths


def osm_timestamp(paths) -> str | None:
    """Newest `timestamp_osm_base` over the cached Overpass answers (the OSM data date)."""
    stamps = []
    for p in paths:
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        ts = (doc.get("osm3s") or {}).get("timestamp_osm_base")
        if ts:
            stamps.append(ts)
    return max(stamps) if stamps else None


def osm_elements(paths) -> list[dict]:
    """All elements of the cached answers, each OSM object once (tiles overlap at their edges)."""
    seen, out = set(), []
    for p in paths:
        for el in json.loads(Path(p).read_text(encoding="utf-8")).get("elements", []):
            key = (el.get("type"), el.get("id"))
            if key not in seen:
                seen.add(key)
                out.append(el)
    return out


def el_lonlat(el: dict) -> tuple[float, float] | None:
    """Position of an Overpass element: a node's own position or the `center` of a way/relation."""
    if "lat" in el and "lon" in el:
        return el["lon"], el["lat"]
    c = el.get("center")
    if c:
        return c["lon"], c["lat"]
    return None


_POWER_UNITS = {"w": 1e-6, "kw": 1e-3, "kwp": 1e-3, "mw": 1.0, "mwp": 1.0, "mwe": 1.0, "gw": 1e3, "gwp": 1e3}


def parse_mw(text) -> float | None:
    """'5102 MW', '4,5 MW', '900 kW', '1.2 GW', 'yes' -> megawatts (None when there is no number).

    A bare number is taken as watts only when it is huge (OSM's documented default unit is W)."""
    if text is None:
        return None
    s = str(text).strip().lower().replace("\u00a0", " ")
    m = re.match(r"^([0-9]+(?:[.,][0-9]+)?)\s*([a-z]*)", s)
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    unit = m.group(2)
    if not unit:
        return value / 1e6 if value >= 1e5 else None  # ambiguous small bare numbers are dropped
    factor = _POWER_UNITS.get(unit)
    return value * factor if factor else None


# --- Eurostat -------------------------------------------------------------------------------------


def eurostat_url(dataset: str, **filters) -> str:
    """Dissemination API URL; a filter value may be a list (repeated parameter)."""
    params: list[tuple[str, str]] = [("format", "JSON"), ("lang", "EN")]
    for k, v in filters.items():
        for item in (v if isinstance(v, (list, tuple)) else [v]):
            params.append((k, str(item)))
    return EUROSTAT_API + dataset + "?" + urllib.parse.urlencode(params)


def eurostat_get(source, dataset: str, rel_path: str, *, force: bool = False, **filters) -> Path:
    """Download a filtered Eurostat extract; an error document (HTTP 200 with "error") is not cached."""
    path = source.download(eurostat_url(dataset, **filters), rel_path, force=force)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if "error" in doc or "value" not in doc:
        source.discard(rel_path)
        raise RuntimeError(f"Eurostat {dataset}: {str(doc.get('error'))[:300]}")
    return path


def jsonstat_cells(doc: dict) -> tuple[list[str], dict[tuple, float | None]]:
    """Decode a JSON-stat 2.0 dataset to (dimension ids, {tuple of category codes: value}).

    Only cells present in `value` are returned (Eurostat leaves out empty cells). Status flags
    (`status`) are not applied: ':' cells are simply absent."""
    ids = doc["id"]
    sizes = doc["size"]
    cats = []
    for d in ids:
        index = doc["dimension"][d]["category"]["index"]
        order = sorted(index, key=index.get) if isinstance(index, dict) else list(index)
        cats.append(order)
    strides = [1] * len(ids)
    for i in range(len(ids) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    values = doc.get("value") or {}
    items = values.items() if isinstance(values, dict) else enumerate(values)
    out: dict[tuple, float | None] = {}
    for flat, v in items:
        flat = int(flat)
        key = []
        for i in range(len(ids)):
            key.append(cats[i][(flat // strides[i]) % sizes[i]])
        out[tuple(key)] = v
    return ids, out


def jsonstat_labels(doc: dict, dim: str) -> dict[str, str]:
    return dict(doc["dimension"][dim]["category"].get("label") or {})


# --- Wikidata -------------------------------------------------------------------------------------


def wikidata_entities(source, qids: list[str], rel_path: str, *, force: bool = False) -> dict:
    """Labels (pl, en) and coordinates (P625) for up to 50 QIDs per request, cached."""
    out: dict[str, dict] = {}
    qids = sorted(set(qids))
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        url = WIKIDATA_API + "?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(chunk), "props": "labels|claims",
            "languages": "pl|en", "format": "json"})
        rel = rel_path if len(qids) <= 50 else rel_path.replace(".json", f"_{i // 50}.json")
        for attempt in range(4):  # Wikidata answers 429 when busy; core.fetch does not retry 4xx
            try:
                got = source.download(url, rel, force=force)
                break
            except urllib.error.HTTPError as exc:
                exc.close()
                if exc.code != 429 or attempt == 3:
                    raise
                time.sleep(30 * (attempt + 1))
        doc = json.loads(got.read_text(encoding="utf-8"))
        for qid, ent in (doc.get("entities") or {}).items():
            labels = {k: v.get("value") for k, v in (ent.get("labels") or {}).items()}
            coords = None
            for claim in (ent.get("claims") or {}).get("P625", []):
                dv = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                if dv and claim.get("rank") != "deprecated":
                    coords = (dv["longitude"], dv["latitude"])
                    if claim.get("rank") == "preferred":
                        break
            out[qid] = {"labels": labels, "lonlat": coords}
    return out


def curated_points(items: list[dict], wd: dict, *, check_label: bool = True) -> tuple[list[dict], list[str]]:
    """Turn curated items into interim points, placed by their Wikidata QID (or a given `lonlat`).

    Each item: id, name, kind, qid or lonlat, `expect` (a word that must occur in the Wikidata label, to
    catch a wrong QID), and any other keys, which become props. Returns (points, problems)."""
    points, problems = [], []
    for it in items:
        ent = wd.get(it.get("qid") or "", {}) if it.get("qid") else {}
        ll = it.get("lonlat") or ent.get("lonlat")
        if it.get("qid") and check_label and it.get("expect"):
            labels = " ".join(str(v) for v in (ent.get("labels") or {}).values()).lower()
            if it["expect"].lower() not in labels:
                problems.append(f"{it['id']}: Wikidata {it['qid']} label {labels!r} lacks {it['expect']!r}")
                ll = it.get("lonlat")
        if ll is None:
            problems.append(f"{it['id']}: no coordinates")
        props = {k: v for k, v in it.items() if k not in ("id", "name", "kind", "lonlat", "expect")}
        points.append({"id": it["id"], "name": it["name"], "kind": it["kind"],
                       "lon": round(ll[0], 5) if ll else None, "lat": round(ll[1], 5) if ll else None,
                       "props": props})
    return points, problems


# --- geometry -------------------------------------------------------------------------------------

EARTH_R = 6371008.8  # metres (mean radius)


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(h)))


def line_length_km(coords) -> float:
    return sum(haversine_m(p, q) for p, q in zip(coords, coords[1:])) / 1000.0


def simplify(coords: list[tuple[float, float]], tol_m: float = 200.0) -> list[tuple[float, float]]:
    """Douglas-Peucker in a local equirectangular plane (metres); the ends are always kept."""
    if len(coords) <= 2:
        return list(coords)
    lat0 = math.radians(sum(c[1] for c in coords) / len(coords))
    kx, ky = math.cos(lat0) * math.pi / 180 * EARTH_R, math.pi / 180 * EARTH_R
    pts = [(c[0] * kx, c[1] * ky) for c in coords]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = pts[i], pts[j]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, idx = -1.0, -1
        for k in range(i + 1, j):
            x, y = pts[k]
            d = math.hypot(x - x1, y - y1) if norm == 0 else abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm
            if d > best:
                best, idx = d, k
        if idx >= 0 and best > tol_m:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [c for c, k in zip(coords, keep) if k]


def chain_ways(ways: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Join polylines that share end points (either direction) into as few lines as possible."""
    lines = [list(w) for w in ways if len(w) >= 2]
    ends: dict[tuple, list[int]] = {}

    def key(p):
        return (round(p[0], 7), round(p[1], 7))

    for i, ln in enumerate(lines):
        ends.setdefault(key(ln[0]), []).append(i)
        ends.setdefault(key(ln[-1]), []).append(i)
    used = [False] * len(lines)
    out = []
    for start in range(len(lines)):
        if used[start]:
            continue
        used[start] = True
        cur = list(lines[start])
        for forward in (True, False):  # grow at the tail, then at the head
            while True:
                tip = key(cur[-1] if forward else cur[0])
                nxt = next((j for j in ends.get(tip, []) if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True
                seg = lines[nxt]
                if key(seg[0]) != tip:
                    seg = seg[::-1]
                # seg now starts at the tip: append it at the tail, or prepend it reversed at the head
                cur = cur + seg[1:] if forward else seg[::-1][:-1] + cur
        out.append(cur)
    return out


def round_coords(coords, nd: int = 5) -> list[list[float]]:
    return [[round(x, nd), round(y, nd)] for x, y in coords]
