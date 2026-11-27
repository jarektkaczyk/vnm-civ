"""The 34 provinces (the `states` slot of the contracts) and the national figures (nation.json).

Each province: code, name, kind, administrative centre, a label anchor, land-cover shares and the economic shape
from the NSO Statistical Yearbook 2025 appendix (2025 figures, preliminary; GRDP estimated). Gold is GRDP, derived
as GRDP per capita x average population (the appendix publishes the two, not the total). Food is rice production.
"""

from __future__ import annotations

from ..core.hexgrid import HexGrid
from ..core.store import load_interim, write_web
from .vnunits import label_anchor, land_shares, optional

REQUIRES = ["_world", "vn_geo_admin", "vn_nso_yearbook"]
PRODUCES = ["states.json", "nation.json"]
YEAR = "2025"
YIELDS = [
    {"key": "gold", "icon": "y-gold", "emoji": "\U0001f4b0", "label": "Gold", "color": "#e8c34a", "unit": "vnd", "banner": False,
     "description": "GRDP: the value of everything produced in the year, 2025 estimate, current prices."},
    {"key": "food", "icon": "y-food", "emoji": "\U0001f33e", "label": "Rice", "color": "#7fbf3f", "unit": "t", "banner": False,
     "description": "Rice harvested in the year, tonnes of paddy (2025, preliminary)."},
]


def series(tab: dict, code: str) -> dict | None:
    row = (tab or {}).get("rows", {}).get(code)
    return row


def shape(yb: dict, code: str) -> dict:
    """The economic shape of a province (or "VN" for the country) from the yearbook tables."""
    def get(num, col=YEAR):
        row = (yb.get(num) or {}).get("rows", {}).get(code) or {}
        return row.get(col)

    pop_k = get("6")
    pop = round(pop_k * 1000) if pop_k is not None else None
    gdp_pc_m = get("43")
    gdp = round(gdp_pc_m * 1e6 * pop) if gdp_pc_m is not None and pop else None
    rice_kt = get("79")
    pop20 = get("6", "2020")
    urban_k = get("9")
    unemp = get("38")
    income_k = get("158", "total")
    poverty = get("173")
    return {
        "population": pop,
        "pop_series": {y: round(v * 1000) if v is not None else None
                       for y, v in ((yb.get("6") or {}).get("rows", {}).get(code) or {}).items()},
        "growth": round(pop_k / pop20 - 1, 4) if pop_k and pop20 else None,
        "growth_years": [2020, 2025],
        "area_km2": get("5", "area_km2"),
        "density": get("5", "density"),
        "urban": round(urban_k / pop_k, 4) if urban_k is not None and pop_k else None,
        "gdp": gdp, "gdp_year": 2025, "gdp_estimated": True,
        "gdp_per_capita": round(gdp_pc_m * 1e6) if gdp_pc_m is not None else None,
        "grdp_growth": round(get("42") / 100 - 1, 4) if get("42") is not None else None,
        "yields": {"gold": gdp, "food": round(rice_kt * 1000) if rice_kt is not None else None},
        "jobs": {},
        "unemployment": round(unemp / 100, 4) if unemp is not None else None,
        "income": round(income_k * 1000) if income_k is not None else None,
        "poverty": round(poverty / 100, 4) if poverty is not None else None,
        "hdi": get("164"),
        "life_expectancy": get("24"),
        "fdi_musd": get("48", "capital_musd"),
        "enterprises_per_1000": get("54"),
    }


def add_ranks(states: list[dict]) -> None:
    for key in ("population", "gdp", "gdp_per_capita", "growth", "food"):
        val = (lambda s, k=key: s["yields"].get("food") if k == "food" else s.get(k))
        ranked = sorted((s for s in states if val(s) is not None), key=lambda s: -val(s))
        for r, s in enumerate(ranked, 1):
            s.setdefault("ranks", {})["gold" if key == "gdp" else key] = r


def build() -> None:
    world = load_interim("_world")
    admin = load_interim("vn_geo_admin")
    yb_pay = optional("vn_nso_yearbook")
    yb = (yb_pay or {}).get("data", {}).get("tables", {})
    grid = HexGrid(**world["grid"])
    owner = world["owner"]
    by_code = {p["code"]: p for p in admin["provinces"]}
    states = []
    for i, code in enumerate(world["states"]):
        p = by_code[code]
        cells = sum(1 for o in owner if o == i)
        st = {"fips": code, "abbr": p["abbr"], "name": p["name"], "type": p["type"],
              "capitals": [{"name": p["centre"], "role": "centre"}],
              "capitals_ref": admin["resolution"]["centres_url"],
              "former": p["former"], "cells": cells, "land": land_shares(world, i),
              "label": label_anchor(grid, owner, i, p["name"]), "energy": None}
        st.update(shape(yb, code))
        states.append(st)
    add_ranks(states)
    write_web("states.json", states)
    nat = shape(yb, "VN")
    nat["growth_years"] = [2020, 2025]
    # The yearbook publishes no provincial GRDP totals, only per-person values, so the provinces are rounded
    # products. The national figure is the sum of the 34 provinces: the parts then add up to the whole.
    gdps = [st["gdp"] for st in states]
    if all(g is not None for g in gdps):
        nat["gdp"] = sum(gdps)
        nat["yields"]["gold"] = nat["gdp"]
        nat["gdp_per_capita"] = round(nat["gdp"] / nat["population"]) if nat["population"] else None
    vint = (yb_pay or {}).get("vintage") or ""
    write_web("nation.json", {
        "vintage": vint,
        "year": 2025,
        "population_date": "2025",
        "gdp_vintage": "NSO Statistical Yearbook 2025: GRDP per capita (2025 estimate) x average population, summed over the 34 provinces",
        "years": {"population": 2025, "gdp": 2025, "unemployment": 2025, "rice": 2025},
        "nation": nat,
        "yields": YIELDS,
        "industries": {},
    })
    print(f"    {len(states)} provinces; Viet Nam {nat['population']:,} people, GRDP "
          f"{(nat['gdp'] or 0) / 1e15:.1f} quadrillion VND")
