"""Power plants on the tiles (resources.json): every OpenStreetMap power plant in Vietnam with a recorded electrical
output of 30 MW or more, by energy source. Also fills each province's mapped capacity (states.json `energy`)."""

from __future__ import annotations

import json
from collections import defaultdict

from ..core.geo import MapProjection
from ..core.hexgrid import HexGrid
from ..core.paths import WEB_DATA
from ..core.store import load_interim, load_interim_payload, write_web
from .infrastructure import nearest_land

REQUIRES = ["_world", "vn_osm_power", "vn_geo_admin", "states.json"]
PRODUCES = ["resources.json"]
MIN_MW = 30.0
RULE = (f"Every power plant in the OpenStreetMap extract with a recorded electrical output of {MIN_MW:g} MW or more. "
        "Plants without a recorded output are left out, so the totals count the mapped sites only.")
TYPES = [
    ("coal_plant", "coal", "Coal power plant", "r-coal_plant", "#434343"),
    ("gas_plant", "gas", "Gas power plant", "r-gas_plant", "#5c7fa3"),
    ("hydro", "hydro", "Hydropower plant", "r-hydro", "#2f7fc1"),
    ("solar", "solar", "Solar farm", "r-solar", "#e8b63a"),
    ("wind", "wind", "Wind farm", "r-wind", "#9fd0e0"),
    ("biomass", "biomass", "Biomass power plant", "r-coal_plant", "#7a9a3a"),
    ("nuclear", "nuclear", "Nuclear power plant", "r-nuclear", "#e3d03a"),
]


def build() -> None:
    world = load_interim("_world")
    admin = load_interim("vn_geo_admin")
    pay = load_interim_payload("vn_osm_power")
    grid = HexGrid(**world["grid"])
    p = world["projection"]
    proj = MapProjection(p["min_x"], p["max_y"], p.get("margin", 0))
    owner = world["owner"]
    abbr = {u["code"]: u["abbr"] for u in admin["provinces"]}
    type_of = {kind: tid for tid, kind, *_ in TYPES}
    items = []
    for pt in pay["data"]["points"]:
        if (pt["mw"] or 0) < MIN_MW:
            continue
        x, y = proj(pt["lon"], pt["lat"])
        cell = nearest_land(grid, owner, grid.cell_at(x, y), rings=2)
        if cell < 0:
            continue
        items.append({"id": f"plant:{pt['id']}", "type": type_of[pt["kind"]], "name": pt["name"],
                      "value": pt["mw"], "status": "operating", "status_label": None, "status_note": None,
                      "operator": pt["operator"], "detail": pt["operator"], "year": pt["year"],
                      "x": round(x, 1), "y": round(y, 1), "cell": cell, "county": None, "cbsa": None,
                      "state": abbr[world["states"][owner[cell]]]})
    items.sort(key=lambda it: -it["value"])
    used = {it["type"] for it in items}
    types = [{"id": tid, "name": name, "category": "energy", "emoji": "\u26a1", "icon": icon, "color": color, "unit": "MW",
              "description": f"{name}s with a recorded output of {MIN_MW:g} MW or more.", "source": "vn_osm_power"}
             for tid, _, name, icon, color in TYPES if tid in used]
    national = defaultdict(lambda: {"count": 0, "value": 0.0, "unit": "MW"})
    per_state: dict[str, dict] = defaultdict(lambda: defaultdict(lambda: {"count": 0, "value": 0.0, "unit": "MW"}))
    for it in items:
        for acc in (national[it["type"]], per_state[it["state"]][it["type"]]):
            acc["count"] += 1
            acc["value"] = round(acc["value"] + it["value"], 1)
    write_web("resources.json", {
        "version": 1, "vintage": {"plants": pay["vintage"]}, "sources": ["vn_osm_power"], "types": types,
        "items": items,
        "summary": {"note": "Totals cover the mapped sites only, not all generating capacity.",
                    "national": {k: dict(v) for k, v in national.items()},
                    "states": {s: {k: dict(v) for k, v in d.items()} for s, d in per_state.items()}},
        "rules": {"plants": RULE},
    })
    # Each province's mapped capacity, into states.json.
    path = WEB_DATA / "states.json"
    states = json.loads(path.read_text())
    for st in states:
        d = per_state.get(st["abbr"]) or {}
        st["energy"] = {"unit": "MW", "total": round(sum(v["value"] for v in d.values()), 1),
                        "by_type": {k: v["value"] for k, v in d.items()}, "sites": sum(v["count"] for v in d.values()),
                        "note": "Mapped sites only."}
    write_web("states.json", states)
    print(f"    {len(items)} plants of {MIN_MW:g} MW or more: " + ", ".join(
        f"{k} {v['count']} ({v['value']:,.0f} MW)" for k, v in national.items()))
