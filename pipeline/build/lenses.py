"""Lenses for Vietnam: one value per hex for each measure, grouped for the lens dock, and counties.json (the 63
former provinces with the measures that exist for them).

A province measure paints every hex of the province (world `owner`); a former-province measure (2019 census) every
hex of the former province (world `county`); a gridded measure is computed per hex by its own builder and read
from its interim (`_grid_lenses`). Land lenses read the hex's own WorldCover shares. Domains are the 2nd to 98th
percentile of hexes.
"""

from __future__ import annotations

from collections import Counter

from ..core.hexgrid import HexGrid
from ..core.store import load_interim, write_web
from .vnunits import optional

REQUIRES = ["_world", "vn_geo_admin", "vn_nso_yearbook", "vn_vcci_pci", "vn_census_2019", "vn_gfw", "_grid_lenses"]
PRODUCES = ["lenses.json", "counties.json"]

GROUPS = [
    {"id": "people", "name": "People"},
    {"id": "prosperity", "name": "Prosperity"},
    {"id": "enterprise", "name": "Enterprise", "icon": "i-manufacturing"},
    {"id": "governance", "name": "Governance", "icon": "i-public_admin"},
    {"id": "farm", "name": "Farm and sea", "icon": "i-agriculture"},
    {"id": "life", "name": "Daily life"},
    {"id": "climate", "name": "Climate and hazards", "icon": "g-hazards"},
    {"id": "land", "name": "Land"},
]

R = {  # ramps, dark to light
    "plum": ["#1b1035", "#4b2377", "#9a3b8a", "#e0645e", "#f9b24a", "#fff3a8"],
    "gold": ["#3a1c0b", "#7a4413", "#b8781f", "#e3b23c", "#f6e27f", "#fffbe0"],
    "teal": ["#0b2a2e", "#165a5c", "#2f8f83", "#7cc29a", "#d4ecb0", "#ffffe0"],
    "fire": ["#03051a", "#4c1d4b", "#a11a5b", "#e83f3f", "#f69c73", "#faebdd"],
    "cividis": ["#00224e", "#35456c", "#666970", "#948e77", "#c8b866", "#fee838"],
    "mako": ["#0b0405", "#382a54", "#395d9c", "#3497a9", "#60ceac", "#def5e5"],
    "blue": ["#08203e", "#0f4c81", "#2a7fc1", "#5fa8e0", "#a6d1f2", "#eaf5ff"],
    "violet": ["#1a0a2e", "#3f1d6b", "#6a3fa0", "#9a72c9", "#c9a9e6", "#f3e8ff"],
    "rose": ["#2b0b1e", "#5e1742", "#93275f", "#c84f7c", "#ea8fa8", "#fbd9e1"],
    "olive": ["#1c1a05", "#45410f", "#76701d", "#a8a033", "#d4ce62", "#f8f6c4"],
    "rust": ["#1a0505", "#4a0f0f", "#80201a", "#b8452b", "#e07b54", "#f9c9a8"],
    "dusk": ["#1a1033", "#3d2466", "#6b3d8f", "#a5649c", "#d99a8f", "#f7dca0"],
    "forest": ["#0b1f0f", "#14401c", "#1f6b2b", "#3a9443", "#7fc07a", "#d5efcd"],
    "farm": ["#141d05", "#2f4510", "#557019", "#84a02a", "#b8cf55", "#eef7b8"],
    "built": ["#121218", "#2c2c3c", "#4b4b66", "#727294", "#a3a3c2", "#e2e2f0"],
    "sea": ["#061a2b", "#0b3552", "#13607e", "#2a91a3", "#74c3bf", "#d8f1e6"],
    "rain": ["#1d1405", "#4a3a12", "#4f6b2a", "#2f8f6b", "#3aa6c4", "#cfeefa"],
    "heat": ["#0d1b3a", "#24508a", "#6d9ec0", "#efe0b0", "#e08a4a", "#a3261f"],
    # Diverging around zero: teal below, parchment at zero, amber above.
    "div": ["#0f5257", "#3c8c8a", "#9cc9bf", "#efe4c6", "#e8b86a", "#c9822a", "#8a4f12"],
}
# Icons (web/js/icons.js) of lenses that name none.
ICONS = {"fertility": "l-age", "migration": "l-commute", "migration_2019": "l-commute", "life": "l-uninsured",
         "doctors": "l-uninsured", "grdp_growth": "l-income", "hdi": "l-degrees", "unemployment": "l-poverty",
         "productivity": "i-manufacturing", "fdi": "i-finance", "aquaculture": "i-agriculture",
         "fishery": "i-agriculture", "water": "l-amenities", "nightlights": "l-developed",
         "nightlights_growth": "l-developed", "rain": "l-disasters", "typhoons": "l-disasters",
         "forest_loss": "l-forest"}
GROUP_ICON = {"people": "l-people", "prosperity": "l-income", "enterprise": "i-manufacturing",
              "governance": "i-public_admin", "farm": "i-agriculture", "life": "l-amenities", "climate": "l-disasters",
              "land": "l-forest"}
PCI_COLORS = ["#2f8f83", "#7cc29a", "#d4ecb0", "#efe4c6", "#e8b86a", "#b8452b"]
DOMAIN_NOTE = "Colours span the 2nd to 98th percentile of hexes; values beyond are drawn at the end colours."
YB = "vn_nso_yearbook"
PCI = "vn_vcci_pci"


def nice(v: float, up: bool) -> float:
    import math

    if v == 0:
        return 0
    mag = 10 ** (math.floor(math.log10(abs(v))) - 1)
    return round((math.ceil if up else math.floor)(v / mag) * mag, 10)


def percentile_domain(values: list, log: bool) -> list[float] | None:
    vals = sorted(v for v in values if v is not None and (v > 0 or not log))
    if not vals:
        return None
    lo, hi = vals[int(0.02 * (len(vals) - 1))], vals[int(0.98 * (len(vals) - 1))]
    lo, hi = nice(lo, False), nice(hi, True)
    return [lo, hi] if hi > lo else [lo, nice(vals[-1], True)]


class Yearbook:
    def __init__(self, tables: dict):
        self.t = tables

    def get(self, num: str, code: str, col: str = "2025"):
        return ((self.t.get(num) or {}).get("rows", {}).get(code) or {}).get(col)

    def per_person(self, num: str, code: str, col: str = "2025", scale: float = 1.0):
        v, pop = self.get(num, code, col), self.get("6", code)
        return None if v is None or not pop else v * scale / (pop * 1000)


def province_lenses(yb: Yearbook, pci: dict) -> list[dict]:
    """(spec, {province code: value}) for every province measure."""
    def per_area(num, scale=1.0):
        return lambda c: (None if yb.get(num, c) is None or not yb.get("5", c, "area_km2")
                          else yb.get(num, c) * scale / yb.get("5", c, "area_km2"))

    L = []

    def add(lid, group, name, unit, fmt, ramp, higher, fn, src=YB, desc="", note=None, scale="linear", short=None,
            icon=None, emoji=None, digits=2):
        L.append(({"id": lid, "group": group, "name": name, "short_name": short, "unit": unit, "format": fmt,
                   "scale": scale, "ramp": R[ramp], "higher_is": higher, "source": src, "description": desc,
                   "note": note, "icon": icon, "emoji": emoji}, fn, digits))

    add("pop_growth", "people", "Population growth 2020-2025", "", "pct", "teal", "neutral",
        lambda c: None if not yb.get("6", c, "2020") else yb.get("6", c) / yb.get("6", c, "2020") - 1,
        desc="Change in the average population from 2020 to 2025 (2025 preliminary).", short="Growth 2020-2025",
        icon="l-people", emoji="\U0001f4c8", digits=4)
    add("urban", "people", "Urban population", "share of residents", "pct", "built", "neutral",
        lambda c: None if not yb.get("6", c) else yb.get("9", c) / yb.get("6", c),
        desc="Share of the average population of 2025 that lives in urban areas.", icon="l-developed", emoji="\U0001f3d9\ufe0f",
        digits=4)
    add("fertility", "people", "Total fertility rate", "children per woman", "float", "rose", "neutral",
        lambda c: yb.get("16", c), desc="Children a woman would have at the birth rates of 2025.", emoji="\U0001f476")
    add("migration", "people", "Net migration 2025", "per 1,000 residents", "float", "div", "neutral",
        lambda c: yb.get("22", c), desc="People who moved in minus people who moved out, per 1,000 residents, 2025.",
        short="Net migration", emoji="\U0001f9f3")
    add("life", "people", "Life expectancy at birth", "years", "years", "mako", "good", lambda c: yb.get("24", c),
        desc="Years a newborn would live at the death rates of 2025.", emoji="\u2764\ufe0f")
    add("grdp_pc", "prosperity", "GRDP per person", "VND per resident", "vnd", "gold", "good",
        lambda c: None if yb.get("43", c) is None else yb.get("43", c) * 1e6,
        desc="Gross regional domestic product per resident, 2025 estimate, current prices.", scale="log",
        icon="l-income", emoji="\U0001f4b0", digits=0)
    add("grdp_growth", "prosperity", "GRDP growth 2025", "", "pct", "teal", "good",
        lambda c: None if yb.get("42", c) is None else yb.get("42", c) / 100 - 1,
        desc="Real growth of GRDP in 2025 over 2024, at constant 2010 prices (estimate).", emoji="\U0001f4c8", digits=4)
    add("income", "prosperity", "Monthly income per person", "VND per month", "vnd", "gold", "good",
        lambda c: None if yb.get("158", c, "total") is None else yb.get("158", c, "total") * 1000,
        desc="Average monthly income per household member, 2025, current prices.", short="Income per person", icon="l-income", emoji="\U0001f4b5", digits=0)
    add("poverty", "prosperity", "Poverty rate", "share of households", "pct", "rust", "bad",
        lambda c: None if yb.get("173", c) is None else yb.get("173", c) / 100,
        desc="Share of households below the multidimensional poverty line, 2025.", icon="l-poverty", emoji="\U0001f4c9",
        digits=4)
    add("hdi", "prosperity", "Human Development Index", "index", "float", "mako", "good", lambda c: yb.get("164", c),
        desc="Human Development Index of the province (health, education, income), 2025 preliminary.", short="HDI",
        emoji="\U0001f393", digits=3)
    add("unemployment", "prosperity", "Unemployment rate", "share of the labour force", "pct", "rust", "bad",
        lambda c: None if yb.get("38", c) is None else yb.get("38", c) / 100,
        desc="Unemployed people as a share of the labour force at working age, 2025.", emoji="\U0001f610", digits=4)
    add("productivity", "prosperity", "Labour productivity", "VND per worker", "vnd", "gold", "good",
        lambda c: None if yb.get("35", c) is None else yb.get("35", c) * 1e6,
        desc="GRDP per employed person, 2025, current prices.", scale="log", emoji="\u2699\ufe0f", digits=0)
    add("trained", "prosperity", "Trained labour force", "share of the labour force", "pct", "violet", "good",
        lambda c: None if yb.get("34", c) is None else yb.get("34", c) / 100,
        desc="Share of the labour force aged 15 and over with a degree or certificate, 2025.",
        icon="l-degrees", emoji="\U0001f393", digits=4)
    add("fdi", "enterprise", "Foreign investment per person", "USD per resident", "usd", "gold", "neutral",
        lambda c: yb.per_person("48", c, "capital_musd", 1e6),
        desc="Registered capital of the foreign direct investment projects in effect on 31 December 2025, per "
             "resident.", scale="log", short="FDI per person", emoji="\U0001f3d7\ufe0f", digits=0)
    add("firms", "enterprise", "Active enterprises", "per 1,000 residents", "float", "violet", "good",
        lambda c: yb.get("54", c), desc="Enterprises in operation per 1,000 residents.", scale="log",
        icon="i-manufacturing", emoji="\U0001f3e2")
    add("industry", "enterprise", "Industrial production 2025", "index, 2024 = 100", "float", "teal", "good",
        lambda c: yb.get("47", c, "iip_2025"), desc="Index of industrial production in 2025 (2024 = 100).",
        short="Industry growth", icon="i-manufacturing", emoji="\U0001f3ed")
    add("retail", "enterprise", "Retail sales per person", "VND per resident", "vnd", "gold", "good",
        lambda c: yb.per_person("123", c, "2025", 1e9),
        desc="Retail sales of goods and consumer services in 2025 per resident, current prices.", scale="log",
        icon="i-retail", emoji="\U0001f6cd\ufe0f", digits=0)
    add("travel", "enterprise", "Travel agency turnover", "VND per resident", "vnd", "olive", "neutral",
        lambda c: yb.per_person("127", c, "2025", 1e9),
        desc="Turnover of travel agencies and tour operators in 2025 per resident, current prices.", scale="log",
        short="Travel turnover", icon="i-accommodation", emoji="\U0001f9f3", digits=0)
    groups = pci.get("groups") or []
    pos = {g["id"]: k for k, g in enumerate(groups)}
    rows = pci.get("rows") or {}
    if rows:
        L.append(({"id": "pci_group", "group": "governance", "name": "PCI 2025 ranking group", "short_name": "PCI group",
                   "format": "category", "scale": "linear", "unit": None, "higher_is": "good", "source": PCI,
                   "description": "The ranking group of the province in the Provincial Competitiveness Index 2025, "
                                  "from a survey of private firms on economic governance.",
                   "categories": [{"id": g["id"], "name": g["name"], "color": PCI_COLORS[k]} for k, g in enumerate(groups)],
                   "ramp": PCI_COLORS[:len(groups)], "icon": "i-public_admin", "emoji": "\U0001f3db\ufe0f", "note": None},
                  lambda c: pos.get((rows.get(c) or {}).get("group")), 0))
        for key, name, desc in [
            ("transparency", "PCI transparency", "Access to plans, laws and documents, and how openly the province "
             "governs (PCI 2025 sub-index, 1 to 10)."),
            ("informal", "PCI informal charges", "How rarely firms pay informal charges (PCI 2025 sub-index, 1 to 10; "
             "higher means fewer charges)."),
            ("support", "PCI business support", "Business support services and labour training (PCI 2025 "
             "sub-index, 1 to 10)."),
            ("proactive", "PCI proactive government", "How active and creative the provincial government is in "
             "solving problems for firms (PCI 2025 sub-index, 1 to 10)."),
            ("bpi", "Business Performance Index", "Results of private business in the province: new and active "
             "firms, turnover, growth and plans (PCI 2025, experimental index)."),
        ]:
            add(f"pci_{key}", "governance", name, "score", "float", "teal", "good",
                lambda c, k=key: (rows.get(c) or {}).get(k), src=PCI, desc=desc, icon="i-public_admin", emoji="\U0001f3db\ufe0f")
    add("rice", "farm", "Rice per km\u00b2", "tonnes per km\u00b2", "float", "farm", "neutral", per_area("79", 1000),
        desc="Rice production of 2025 (tonnes of paddy) per km\u00b2 of the province.", scale="log",
        icon="i-agriculture", emoji="\U0001f33e")
    add("aquaculture", "farm", "Aquaculture per km\u00b2", "tonnes per km\u00b2", "float", "sea", "neutral",
        per_area("120"), desc="Fish, shrimp and other farmed seafood of 2025 per km\u00b2 of the province.", scale="log",
        emoji="\U0001f990")
    add("fishery", "farm", "Fishery per person", "kg per resident", "float", "sea", "neutral",
        lambda c: yb.per_person("117", c, "2025", 1000),
        desc="Fishery production of 2025 (caught and farmed) per resident.", scale="log", emoji="\U0001f41f")
    add("forest_official", "farm", "Forest area", "share of the province", "pct", "forest", "neutral",
        lambda c: None if not yb.get("5", c, "area_km2") or yb.get("110", c, "forest") is None
        else yb.get("110", c, "forest") * 10 / yb.get("5", c, "area_km2"),
        desc="Forest area on 31 December 2025 (natural and planted) as a share of the province's area.",
        icon="l-forest", emoji="\U0001f333", digits=4)
    add("doctors", "life", "Doctors per 10,000", "per 10,000 residents", "float", "teal", "good",
        lambda c: yb.per_person("149", c, "doctors_2025", 1e4),
        desc="Doctors in the public sector in 2025 per 10,000 residents.", emoji="\U0001fa7a")
    add("water", "life", "Clean water", "share of residents", "pct", "blue", "good",
        lambda c: None if yb.get("175", c) is None else yb.get("175", c) / 100,
        desc="Share of residents who use a hygienic water source, 2025.", emoji="\U0001f6b0", digits=4)
    add("internet", "life", "Internet users", "share of people", "pct", "violet", "neutral",
        lambda c: None if yb.get("186", c) is None else yb.get("186", c) / 100,
        desc="Share of people aged 6 and over who used the internet in the last 3 months, 2025.",
        icon="l-broadband", emoji="\U0001f4f6", digits=4)
    return L


def build() -> None:
    world = load_interim("_world")
    admin = load_interim("vn_geo_admin")
    grid = HexGrid(**world["grid"])
    owner, county = world["owner"], world["county"]
    states, formers = world["states"], world["counties"]
    yb = Yearbook(((optional(YB) or {}).get("data") or {}).get("tables", {}))
    pci = (optional(PCI) or {}).get("data") or {}
    census = ((optional("vn_census_2019") or {}).get("data") or {}).get("rows", {})

    lenses = []
    for spec, fn, digits in province_lenses(yb, pci):
        per = {}
        for c in states:
            try:
                v = fn(c)
            except (TypeError, ZeroDivisionError):
                v = None
            per[c] = None if v is None else (v if spec["format"] == "category" else round(v, digits))
        if not any(v is not None for v in per.values()):
            print(f"    lens {spec['id']}: no data")
            continue
        vals = [per[states[o]] if o >= 0 else None for o in owner]
        lenses.append({**{k: v for k, v in spec.items() if v is not None}, "level": "province", "values": vals})

    if census:
        per = {c: (census.get(c) or {}).get("net_rate") for c in formers}
        vals = [per[formers[k]] if o >= 0 and k >= 0 else None for o, k in zip(owner, county)]
        lenses.append({"id": "migration_2019", "group": "people", "name": "Net migration 2014-2019",
                       "short_name": "Migration 2019", "unit": "per 1,000 residents aged 5+", "format": "float",
                       "scale": "linear", "ramp": R["div"], "higher_is": "neutral", "source": "vn_census_2019",
                       "description": "People who moved in from another province minus people who moved out, in the "
                                      "five years before the census of 1 April 2019, per 1,000 residents aged 5 and "
                                      "over.", "note": "2019, 63 provinces.", "level": "former", "emoji": "\U0001f9f3",
                       "values": vals})

    gfw = ((optional("vn_gfw") or {}).get("data") or {})
    if gfw.get("rows"):
        y0, y1 = gfw["years"]
        per = {}
        for c in formers:
            row = gfw["rows"].get(c)
            ext = (row or {}).get("extent_2000_ha")
            per[c] = None if not ext else round(sum(v or 0 for v in row["loss_ha"].values()) / ext, 4)
        vals = [per[formers[k]] if o >= 0 and k >= 0 else None for o, k in zip(owner, county)]
        lenses.append({"id": "forest_loss", "group": "climate", "name": f"Tree cover loss {y0}-{y1}",
                       "short_name": "Tree cover loss", "unit": "share of the tree cover of 2000", "format": "pct",
                       "scale": "linear", "ramp": R["rust"], "higher_is": "bad", "source": "vn_gfw",
                       "description": f"Tree cover lost from {y0} to {y1} as a share of the tree cover of 2000.",
                       "note": "63 provinces of the time.", "level": "former", "icon": "l-forest", "emoji": "\U0001fa93",
                       "values": vals})

    grid_lenses = (optional("_grid_lenses") or {}).get("data") or {}
    for lens in grid_lenses.get("lenses", []):
        lenses.append(lens)

    pct = world.get("pct")
    cover = world.get("cover")
    for lid, keys, name, icon, emoji, ramp, desc in [
        ("forest", ["forest"], "Tree cover", "l-forest", "\U0001f332", "forest",
         "Share of the land with tree cover, 2021."),
        ("farmland", ["crop"], "Farmland", "l-farmland", "\U0001f69c", "farm",
         "Share of the land in cropland and rice paddies, 2021."),
        ("developed", ["developed"], "Built-up", "l-developed", "\U0001f3d9\ufe0f", "built",
         "Share of the land that is built up, 2021."),
    ]:
        vals = [round(sum(pct[k][i] for k in keys) / 100, 2) if owner[i] >= 0 and cover[i] else None
                for i in range(grid.size)]
        lenses.append({"id": lid, "group": "land", "name": name, "icon": icon, "emoji": emoji, "unit": "share of land",
                       "format": "pct", "scale": "linear", "ramp": R[ramp], "higher_is": "neutral",
                       "source": "vn_geo_worldcover", "description": desc, "level": "hex", "values": vals})

    for lens in lenses:
        lens.setdefault("icon", ICONS.get(lens["id"]) or GROUP_ICON.get(lens["group"], "l-people"))
        lens.setdefault("emoji", "")
        if lens.get("unit") is None:
            lens["unit"] = ""
        if "domain" not in lens:
            if lens["format"] == "category":
                lens["domain"] = [0, len(lens["categories"]) - 1]
            else:
                lens["domain"] = percentile_domain(lens["values"], lens["scale"] == "log")
                lens["scale_note"] = DOMAIN_NOTE
        if (lens["ramp"] == R["div"] or lens.get("diverging")) and lens["domain"]:
            m = max(abs(lens["domain"][0]), abs(lens["domain"][1]))
            lens["domain"] = [-m, m]
    groups = [g for g in GROUPS if any(l["group"] == g["id"] for l in lenses)]
    # Values are stored for the land hexes of Vietnam only (`cells`, in order); the browser spreads them back over
    # the whole grid (null elsewhere). Every lens is null off Vietnamese land.
    land = [i for i, o in enumerate(owner) if o >= 0]
    for lens in lenses:
        stray = sum(1 for i, o in enumerate(owner) if o < 0 and lens["values"][i] is not None)
        if stray:
            raise ValueError(f"lens {lens['id']}: {stray} values off Vietnamese land")
        lens["values"] = [lens["values"][i] for i in land]
    write_web("lenses.json", {"vintage": (optional(YB) or {}).get("vintage") or "", "groups": groups,
                              "cells": land, "lenses": lenses})
    print(f"    {len(lenses)} lenses: " + ", ".join(l["id"] for l in lenses))

    # counties.json: the 63 former provinces.
    name_of = {f["code"]: f for f in admin["former"]}
    fields = [
        {"key": "migration_2019", "label": "Net migration 2014-2019", "format": "float",
         "unit": "per 1,000 residents aged 5+", "higher_is": "neutral", "source": "vn_census_2019",
         "description": "In-migrants minus out-migrants over the five years before 1 April 2019, per 1,000 residents "
                        "aged 5 and over (2019 census).", "level": "former", "group": "people"},
        {"key": "in_migrants_2019", "label": "In-migrants 2014-2019", "format": "int", "unit": "people",
         "higher_is": "neutral", "source": "vn_census_2019", "description": "People aged 5 and over who lived in "
         "another province five years before the 2019 census.", "level": "former", "group": "people"},
        {"key": "out_migrants_2019", "label": "Out-migrants 2014-2019", "format": "int", "unit": "people",
         "higher_is": "neutral", "source": "vn_census_2019", "description": "People who left for another province "
         "in the five years before the 2019 census.", "level": "former", "group": "people"},
    ]
    abbr = {p["code"]: p["abbr"] for p in admin["provinces"]}
    cells = Counter(k for k in county if k >= 0)
    rows = []
    for k, code in enumerate(formers):
        f = name_of[code]
        c = census.get(code) or {}
        rows.append([code, f["name"], "former", f["province"], abbr[f["province"]], c.get("pop5"), f["area_km2"],
                     c.get("net_rate"), c.get("in"), c.get("out"), cells.get(k, 0)])
    write_web("counties.json", {"vintage": (optional("vn_census_2019") or {}).get("vintage") or "", "fields": fields,
                                "columns": ["geoid", "name", "type", "province", "state", "population_5plus_2019",
                                            "area_km2", "migration_2019", "in_migrants_2019", "out_migrants_2019",
                                            "cells"],
                                "rows": rows})
