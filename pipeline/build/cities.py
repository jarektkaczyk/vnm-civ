"""Towns (cities.json): the urban centres of the GHSL Urban Centre Database with their 2025 population, and the
administrative centre of every province (Resolution 60-NQ/TW annex) whether or not it is an urban centre.

A centre is matched to the urban centre of the same name in its province; a centre without one is placed at its
known position and has no population (null). Each town takes the hex under it; when two towns share a hex the
smaller moves to the nearest free land hex of the same province.
"""

from __future__ import annotations

import json
import math
import re

from ..core.geo import MapProjection
from ..core.hexgrid import HexGrid
from ..core.paths import WEB_DATA
from ..core.store import load_interim, write_web
from ..sources import vn_admin_units as U

REQUIRES = ["_world", "vn_geo_admin", "vn_ghsl_ucdb", "vn_osm_places", "states.json"]
PRODUCES = ["cities.json"]
RULE = ("Every urban centre of the GHSL Urban Centre Database R2024A in Vietnam (a dense cluster of 50,000 people or "
        "more; population estimate for 2025), and the administrative centre of every province.")


def projection(world: dict) -> MapProjection:
    """lon/lat -> map km of the world grid (the Albers parameters are core.geo's defaults)."""
    p = world["projection"]
    return MapProjection(p["min_x"], p["max_y"], p.get("margin", 0))


SUFFIX = re.compile(r"\s+(town|city)$", re.I)
PREFIX = re.compile(r"^(th\u1ecb tr\u1ea5n|th\u1ecb x\u00e3|th\u00e0nh ph\u1ed1|ph\u01b0\u1eddng|x\u00e3)\s+", re.I)
SPELL_KM = 25.0  # an OSM place spells a town's name when it lies this close to the urban centre


def has_marks(name: str) -> bool:
    return any(ord(ch) > 127 for ch in name)


def plain(name: str) -> str:
    """The name without an English suffix ("Van Gia Town" -> "Van Gia")."""
    return SUFFIX.sub("", name.strip())


# Spellings that neither OpenStreetMap nor the province list give: a district town of Ha Noi.
SPELLINGS = {"phuxuyen": "Ph\u00fa Xuy\u00ean"}


def spell(name: str, lon: float, lat: float, places: list[dict], known: dict[str, str] | None = None) -> str:
    """The Vietnamese spelling (with tone marks) of a plain name, from the nearest OpenStreetMap place of the same
    name; else the official spelling of a province or provincial centre of that name; else the name itself. A name
    that already has tone marks is kept."""
    name = plain(name)
    if has_marks(name):
        return name
    key = U.fold(name)
    best, best_d = None, SPELL_KM
    for pl in places:
        pname = PREFIX.sub("", pl["name"].strip())
        if not has_marks(pname) or U.fold(pname) != key:
            continue
        d = math.hypot((pl["lon"] - lon) * 111.0 * math.cos(math.radians(lat)), (pl["lat"] - lat) * 111.0)
        if d < best_d:
            best, best_d = pname, d
    if best:
        return best
    return (known or {}).get(key) or SPELLINGS.get(key) or name


def build() -> None:
    world = load_interim("_world")
    admin = load_interim("vn_geo_admin")
    ucdb = load_interim("vn_ghsl_ucdb")["centres"]
    places = load_interim("vn_osm_places")["places"]
    pop_of = {st["fips"]: st["population"] for st in json.loads((WEB_DATA / "states.json").read_text(encoding="utf-8"))}
    known = {}
    for p in admin["provinces"]:
        for nm in (p["name"], p["centre"]):
            known[U.fold(nm)] = nm
    city_codes = {p["code"] for p in admin["provinces"] if p["type"] == "city"}
    grid = HexGrid(**world["grid"])
    proj = projection(world)
    owner = world["owner"]
    codes = world["states"]
    abbr = {p["code"]: p["abbr"] for p in admin["provinces"]}
    name_of = {p["code"]: p["name"] for p in admin["provinces"]}

    towns = []
    for c in ucdb:
        x, y = proj(c["lon"], c["lat"])
        towns.append({"id": c["id"], "name": spell(c["name"], c["lon"], c["lat"], places, known), "population": c["population"],
                      "x": x, "y": y, "capital": c["capital"], "centre": None, "names": c.get("names") or ""})
    # Provincial centres.
    for p in admin["provinces"]:
        key = U.fold(p["centre"])
        match = next((t for t in towns if U.fold(t["name"]) == key), None)
        if match is not None and match["centre"] is None:
            match["centre"] = p["code"]
            match["name"] = p["centre"]  # the official spelling of the centre (the GHSL file drops some tone marks)
            continue
        lon, lat, _ref = U.CENTRE_POSITIONS[p["centre"]]
        x, y = proj(lon, lat)
        towns.append({"id": f"centre{p['code']}", "name": p["centre"], "population": None, "x": x, "y": y,
                      "capital": False, "centre": p["code"]})

    # The population of a town is its urban area (GHSL), except for the centre of a centrally run city: that
    # town stands for the whole city, so it carries the official city population (NSO 2025). "population_basis"
    # tells the page which one it shows.
    for t in towns:
        t["basis"] = "urban" if t["population"] is not None else None
        if t["centre"] in city_codes and pop_of.get(t["centre"]):
            t["urban_population"] = t["population"]
            t["population"] = pop_of[t["centre"]]
            t["basis"] = "city"

    # Banner cells: the hex under the town (land of Vietnam), unique where possible.
    taken = set()
    towns.sort(key=lambda t: (t["population"] is None, -(t["population"] or 0)))
    out = []
    for t in towns:
        cell = grid.cell_at(t["x"], t["y"])
        if cell < 0 or owner[cell] < 0 or cell in taken:
            ring = sorted((i for i in range(max(0, cell - 3 * grid.cols - 3), min(grid.size, cell + 3 * grid.cols + 4))
                           if owner[i] >= 0 and i not in taken),
                          key=lambda i: math.dist(grid.center(*grid.col_row(i)), (t["x"], t["y"])))
            if not ring:
                print(f"    ! {t['name']}: no land hex near it; left out")
                continue
            cell = ring[0]
        taken.add(cell)
        st = codes[owner[cell]]
        if t["centre"] and t["centre"] != st:
            print(f"    note: centre {t['name']} falls in {name_of[st]}, not {name_of[t['centre']]}")
        out.append({
            "id": t["id"], "name": t["name"],
            "full": f"{t['name']}, {name_of[st]}",
            "states": [abbr[st]], "province": st, "kind": "town",
            "centre": t["centre"] is not None, "capital": t["name"] == "H\u00e0 N\u1ed9i",
            "city_view": False, "metro": False,
            "x": round(t["x"], 1), "y": round(t["y"], 1), "cell": cell,
            "population": t["population"], "population_basis": t["basis"],
            "urban_population": t.get("urban_population"), "yields": {}, "jobs": {},
        })
    write_web("cities.json", out)
    print(f"    {len(out)} towns ({sum(1 for c in out if c['centre'])} provincial centres, "
          f"{sum(1 for c in out if c['population'] is None)} without a population)")
