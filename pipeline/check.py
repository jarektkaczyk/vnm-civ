"""Validate web/data/*.json against docs/DATA_CONTRACTS.md (v2) and report data quality.

    uv run python -m pipeline check

Part 1 checks each file's shape: required keys, types, per-cell array lengths
and value ranges, cross references (lens sources, resource types, state order).
Part 2 is a data-quality report: population conservation of the density lens,
cities on water or sharing a cell, null yields, rivers outside the map, counties
missing from the hex sampling and per-lens null shares.

Every line is PASS, WARN or FAIL (NOTE for information). The exit code is 1 if
anything FAILed. WARN thresholds are the constants below.

Part 3 runs builder-level checks: any module in pipeline/build/ may define

    def check(web_dir: Path) -> list[tuple[str, str]]   # [(level, message)], level in PASS/NOTE/WARN/FAIL

to validate the files it PRODUCES, so a new builder never has to edit this file. It is discovered
automatically (see run_builder_checks); a missing output should be reported as a NOTE (or WARN), not a FAIL,
unless the file is required. A check that raises is reported as a FAIL with the error.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from .core.paths import INTERIM, WEB_DATA

# Density lens total vs the NSO province total. Tight because lenses.py uses the same
# land-share formula, so this mainly catches dropped or double-counted people.
LENS_NULL_WARN = 0.05  # share of land cells of Vietnam with a null lens value

REQUIRED = ["world.json", "cities.json", "states.json", "nation.json", "lenses.json", "sources.json"]
OPTIONAL = ["resources.json", "counties.json"]

WATER_IDS = range(0, 4)
RELIEF_IDS = range(0, 4)
COVER_KEYS = [
    "none", "forest_deciduous", "forest_evergreen", "forest_mixed", "scrub", "grassland",
    "pasture", "cropland", "wetland", "urban", "barren", "ice",
]
PCT_KEYS = ["forest", "crop", "pasture", "grass", "shrub", "wetland", "developed"]
YIELD_KEYS = ["gold", "food"]
YIELD_UNITS = {"vnd", "usd", "t", "workers"}
# Lenses whose data exists only for some provinces (university towns, stations within 25 km, the 2021 census map).
SPARSE_LENSES = {"nightlights_growth"}  # null by design where a hex was dark at the start
LENS_FORMATS = {"int", "vnd", "usd", "pct", "float", "minutes", "years", "category"}
LENS_SCALES = {"log", "linear"}
HIGHER_IS = {"good", "bad", "neutral"}
RESOURCE_CATEGORIES = {"energy", "mineral", "agri"}
COLOR = re.compile(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?([0-9a-fA-F]{2})?$")
# The economic shape shared by a town, a province and nation.json "nation" (see pipeline/build/yields.py).
NOT_ADDITIVE = {"oil", "gas"}  # resource types whose item values are play areas (summary value is null)


# ---------------------------------------------------------------- reporting


class Report:
    """Collects PASS/WARN/FAIL/NOTE lines and prints them as they come."""

    def __init__(self, quiet: bool = False):
        self.lines: list[tuple[str, str]] = []
        self.quiet = quiet

    def _add(self, level: str, msg: str) -> None:
        self.lines.append((level, msg))
        if not self.quiet:
            print(f"  {level:4}  {msg}")

    def ok(self, msg):
        self._add("PASS", msg)

    def warn(self, msg):
        self._add("WARN", msg)

    def fail(self, msg):
        self._add("FAIL", msg)

    def note(self, msg):
        self._add("NOTE", msg)

    def section(self, title):
        if not self.quiet:
            print(f"\n[{title}]")

    def count(self, level: str) -> int:
        return sum(1 for lv, _ in self.lines if lv == level)

    @property
    def failed(self) -> bool:
        return self.count("FAIL") > 0


def is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _sample(items, n=5) -> str:
    items = list(items)
    more = f" \u2026 (+{len(items) - n})" if len(items) > n else ""
    return ", ".join(str(x) for x in items[:n]) + more


def need_keys(r: Report, what: str, obj, keys) -> bool:
    """FAIL (once per object kind) if `obj` is not a dict or lacks keys. Returns True if all present."""
    if not isinstance(obj, dict):
        r.fail(f"{what}: expected an object, got {type(obj).__name__}")
        return False
    missing = [k for k in keys if k not in obj]
    if missing:
        r.fail(f"{what}: missing {', '.join(missing)}")
        return False
    return True


def check_cells(r: Report, name: str, arr, n: int, lo=None, hi=None, *, kind="int") -> bool:
    """A per-cell array: length n, every value an int (or number) within [lo, hi]."""
    if not isinstance(arr, list) or len(arr) != n:
        got = len(arr) if isinstance(arr, list) else type(arr).__name__
        r.fail(f"{name}: expected {n} values, got {got}")
        return False
    test = is_int if kind == "int" else is_num
    bad = [i for i, v in enumerate(arr) if not test(v) or (lo is not None and v < lo) or (hi is not None and v > hi)]
    if bad:
        r.fail(f"{name}: {len(bad)} values not {kind} in [{lo}, {hi}] (cells {_sample(bad)}; e.g. {arr[bad[0]]!r})")
        return False
    return True


# ---------------------------------------------------------------- validators


def check_world(r: Report, w) -> dict | None:
    """Validate world.json. Returns a small context (n, owner, states, ...) for the other checks, or None."""
    if not isinstance(w, dict):
        r.fail("world.json: not an object")
        return None
    fails_before = r.count("FAIL")
    if w.get("version") != 2:
        r.fail(f"world.json: version is {w.get('version')!r}, expected 2 (still v1?)")
    if not need_keys(r, "world.json grid", w.get("grid"), ["radius", "cols", "rows"]):
        return None
    g = w["grid"]
    if not (is_num(g["radius"]) and g["radius"] > 0 and is_int(g["cols"]) and is_int(g["rows"]) and g["cols"] > 0 and g["rows"] > 0):
        r.fail(f"world.json grid: bad values {g}")
        return None
    n = g["cols"] * g["rows"]
    need_keys(r, "world.json", w, ["width", "height", "margin", "owner", "county", "elev", "water", "relief", "cover", "pct", "tables", "states", "counties", "rivers"])
    for k in ("width", "height", "margin"):
        if k in w and not is_num(w[k]):
            r.fail(f"world.json {k}: not a number ({w[k]!r})")

    states, counties = w.get("states") or [], w.get("counties") or []
    if not all(isinstance(s, dict) and {"fips", "abbr", "name"} <= s.keys() for s in states):
        r.fail("world.json states: every entry needs fips, abbr, name")
    if not all(isinstance(c, dict) and {"geoid", "name"} <= c.keys() for c in counties):
        r.fail("world.json counties: every entry needs geoid, name")

    ok = True
    owner = w.get("owner")
    ok &= check_cells(r, "world.json owner", owner, n, -2, len(states) - 1)
    ok &= check_cells(r, "world.json county", w.get("county"), n, -1, len(counties) - 1)
    ok &= check_cells(r, "world.json elev", w.get("elev"), n)
    if "elev_max" in w:
        ok &= check_cells(r, "world.json elev_max", w["elev_max"], n, 0, 9000)
    water = w.get("water")
    if "water" in w:
        ok &= check_cells(r, "world.json water", water, n, 0, 3)
    if "relief" in w:
        ok &= check_cells(r, "world.json relief", w["relief"], n, 0, 3)
    if "cover" in w:
        ok &= check_cells(r, "world.json cover", w["cover"], n, 0, len(COVER_KEYS) - 1)
    owner_ok = isinstance(owner, list) and len(owner) == n and all(is_int(v) for v in owner)

    if owner_ok and isinstance(water, list) and len(water) == n:
        wet_land = sum(1 for o, wt in zip(owner, water) if o != -1 and wt != 0)
        dry_water = sum(1 for o, wt in zip(owner, water) if o == -1 and wt == 0)
        if wet_land or dry_water:
            r.warn(f"world.json: owner/water disagree on {wet_land} land cells with water>0 and {dry_water} water cells with water=0")
        if isinstance(w.get("relief"), list) and len(w["relief"]) == n:
            bad = sum(1 for wt, rl in zip(water, w["relief"]) if is_int(wt) and wt != 0 and rl != 0)
            if bad:
                r.fail(f"world.json relief: {bad} water cells have relief != 0")
        elev = w.get("elev")
        if isinstance(elev, list) and len(elev) == n:
            high = [i for i, (wt, e) in enumerate(zip(water, elev)) if is_int(wt) and wt != 0 and is_num(e) and e > 0]
            if high:
                r.fail(f"world.json elev: {len(high)} water cells have elev > 0 (water elev is mean depth, <= 0; cells {_sample(high)})")

    pct = w.get("pct")
    if "pct" in w:
        if need_keys(r, "world.json pct", pct, PCT_KEYS):
            for k in PCT_KEYS:
                ok &= check_cells(r, f"world.json pct.{k}", pct[k], n, 0, 100)
            if owner_ok and all(isinstance(pct[k], list) and len(pct[k]) == n for k in PCT_KEYS):
                over = [i for i in range(n) if sum(pct[k][i] or 0 for k in PCT_KEYS if is_num(pct[k][i])) > 100 + len(PCT_KEYS)]
                outside = [i for i in range(n) if owner[i] < 0 and any(pct[k][i] for k in PCT_KEYS)]
                if over:
                    r.fail(f"world.json pct: {len(over)} cells sum above 100% (cells {_sample(over)})")
                if outside:
                    r.fail(f"world.json pct: {len(outside)} cells off Vietnamese land have non-zero land-cover shares (must be 0)")

    tables = w.get("tables")
    if "tables" in w and need_keys(r, "world.json tables", tables, ["water", "relief", "cover"]):
        for t, ids in (("water", WATER_IDS), ("relief", RELIEF_IDS)):
            got = sorted(e.get("id") for e in tables[t] if isinstance(e, dict))
            if got != list(ids) or not all("name" in e for e in tables[t]):
                r.fail(f"world.json tables.{t}: expected ids {list(ids)} with names, got {got}")
        bad = [e for e in tables["cover"] if not isinstance(e, dict) or not is_int(e.get("id")) or not 0 <= e["id"] < len(COVER_KEYS)
               or e.get("key") != COVER_KEYS[e["id"]] or "name" not in e or (e["id"] and not COLOR.match(str(e.get("color", ""))))]
        if bad:
            r.fail(f"world.json tables.cover: {len(bad)} entries don't match the fixed cover ids/keys or lack name/color: {_sample(bad, 2)}")

    rivers = w.get("rivers") or []
    bad = [i for i, rv in enumerate(rivers) if not isinstance(rv, dict) or not {"name", "rank", "pts"} <= rv.keys()
           or not is_int(rv["rank"]) or not isinstance(rv["pts"], list) or len(rv["pts"]) < 4 or len(rv["pts"]) % 2 or not all(is_num(v) for v in rv["pts"])]
    if bad:
        r.fail(f"world.json rivers: {len(bad)} malformed (need name, int rank, pts=[x0,y0,x1,y1,\u2026])")

    if ok and r.count("FAIL") == fails_before:
        r.ok(f"world.json: {g['cols']}\u00d7{g['rows']} grid, {len(states)} states, {len(counties)} counties, {len(rivers)} rivers")
    return {
        "n": n, "grid": g, "owner": owner if owner_ok else None, "states": states, "counties": counties,
        "width": w.get("width"), "height": w.get("height"), "rivers": rivers,
    }


def check_nation(r: Report, nat) -> list[str]:
    """nation.json: the national figures and the yield definitions. Returns the yield keys."""
    if not need_keys(r, "nation.json", nat, ["vintage", "year", "nation", "yields"]):
        return []
    keys = []
    for y in nat["yields"]:
        if not need_keys(r, "nation.json yield", y, ["key", "label", "color", "unit"]):
            continue
        if y["unit"] not in YIELD_UNITS or not COLOR.match(str(y["color"])):
            r.fail(f"nation.json yield {y['key']}: unit must be one of {sorted(YIELD_UNITS)} and color #hex")
        keys.append(y["key"])
    n = nat["nation"]
    if need_keys(r, "nation.json nation", n, ["population", "yields", "gdp"]):
        if not (is_num(n["population"]) and n["population"] > 0):
            r.fail("nation.json nation: population must be a positive number")
        else:
            r.ok(f"nation.json: {n['population']:,.0f} people, yields {keys}")
    return keys


def check_nation_sums(r: Report, nat, states) -> None:
    """The national population and GRDP equal the sum of the provinces; national rice is within 0.1% of it."""
    if not isinstance(nat, dict) or not isinstance(states, list) or not isinstance(nat.get("nation"), dict):
        return
    n = nat["nation"]
    for key, get in (("population", lambda st: st.get("population")), ("gdp", lambda st: st.get("gdp"))):
        vals = [get(st) for st in states if isinstance(st, dict)]
        if any(not is_num(v) for v in vals) or not is_num(n.get(key)):
            r.note(f"national {key}: a province or the nation has no value, sum check skipped")
        elif sum(vals) != n[key]:
            r.fail(f"national {key} {n[key]:,.0f} differs from the sum of the provinces {sum(vals):,.0f}")
        else:
            r.ok(f"national {key} equals the sum of the {len(vals)} provinces")
    rice = [st.get("yields", {}).get("food") for st in states if isinstance(st, dict)]
    nrice = (n.get("yields") or {}).get("food")
    if all(is_num(v) for v in rice) and is_num(nrice) and nrice:
        diff = abs(sum(rice) - nrice) / nrice
        if diff > 0.001:
            r.fail(f"national rice differs from the sum of the provinces by {diff:.2%}")
        else:
            r.ok(f"national rice is within 0.1% of the province sum ({diff:.3%})")


def check_states(r: Report, states, ctx: dict | None, yield_keys) -> None:
    """states.json: one province per world.json state, same order, with the economic fields (numbers or null)."""
    if not isinstance(states, list):
        r.fail("states.json: expected a list")
        return
    fails = r.count("FAIL")
    if ctx is not None and len(states) != len(ctx["states"]):
        r.fail(f"states.json: {len(states)} entries, world.json has {len(ctx['states'])} states")
    for k, st in enumerate(states):
        what = f"states.json {st.get('fips') if isinstance(st, dict) else st!r}"
        if not need_keys(r, what, st, ["fips", "abbr", "name", "population", "yields", "label"]):
            continue
        if ctx is not None and k < len(ctx["states"]) and ctx["states"][k].get("fips") != st["fips"]:
            r.fail(f"{what}: order differs from world.json states")
        for key in ("population", "gdp", "unemployment", "growth"):
            v = st.get(key)
            if v is not None and not is_num(v):
                r.fail(f"{what}: {key} must be a number or null")
        if st.get("population") == 0:
            r.fail(f"{what}: population 0 (missing data must be null)")
        if st.get("population") is None:
            r.fail(f"{what}: no population (every province has a published population)")
        bad = [y for y in yield_keys if y in st["yields"] and st["yields"][y] is not None and not is_num(st["yields"][y])]
        if bad:
            r.fail(f"{what}: yields {bad} must be numbers or null")
    if r.count("FAIL") == fails:
        tot = sum(st["population"] for st in states if isinstance(st, dict) and is_num(st.get("population")))
        r.ok(f"states.json: {len(states)} provinces, {tot:,.0f} people")


def check_cities(r: Report, cities, ctx: dict | None) -> None:
    """cities.json: towns with a land cell, a position and a population (a number, or null when unknown)."""
    if not isinstance(cities, list):
        r.fail("cities.json: expected a list")
        return
    fails = r.count("FAIL")
    ids = Counter(c.get("id") for c in cities if isinstance(c, dict))
    if any(k > 1 for k in ids.values()):
        r.fail(f"cities.json: duplicate ids {[i for i, k in ids.items() if k > 1]}")
    cells = Counter()
    for c in cities:
        what = f"cities.json {c.get('id') if isinstance(c, dict) else c!r}"
        if not need_keys(r, what, c, ["id", "name", "full", "states", "x", "y", "cell", "population"]):
            continue
        if c["population"] is not None and not (is_num(c["population"]) and c["population"] > 0):
            r.fail(f"{what}: population must be positive or null")
        if ctx is not None and ctx["owner"] and not (is_int(c["cell"]) and 0 <= c["cell"] < ctx["n"] and ctx["owner"][c["cell"]] >= 0):
            r.fail(f"{what}: cell must be a land cell of Vietnam")
        cells[c["cell"]] += 1
    shared = [k for k, n in cells.items() if n > 1]
    if shared:
        r.warn(f"cities.json: {len(shared)} cells hold more than one town")
    if r.count("FAIL") == fails:
        r.ok(f"cities.json: {len(cities)} towns, {sum(1 for c in cities if c.get('population') is None)} without a population")


def check_counties(r: Report, doc, ctx: dict | None) -> None:
    """counties.json: the former provinces, one row per world.json county, column-oriented."""
    if not need_keys(r, "counties.json", doc, ["fields", "columns", "rows"]):
        return
    cols = doc["columns"]
    bad = [row for row in doc["rows"] if not isinstance(row, list) or len(row) != len(cols)]
    if bad:
        r.fail(f"counties.json: {len(bad)} rows do not have {len(cols)} columns")
    if ctx is not None and len(doc["rows"]) != len(ctx["counties"]):
        r.fail(f"counties.json: {len(doc['rows'])} rows, world.json has {len(ctx['counties'])} counties")
    for f in doc["fields"]:
        if not need_keys(r, "counties.json field", f, ["key", "label", "format", "source"]):
            continue
        if f["key"] not in cols:
            r.fail(f"counties.json field {f['key']}: not a column")
    if not bad:
        r.ok(f"counties.json: {len(doc['rows'])} former provinces, {len(doc['fields'])} fields")



def check_lenses(r: Report, doc, ctx: dict | None, source_ids: set | None) -> None:
    if not need_keys(r, "lenses.json", doc, ["vintage", "groups", "lenses"]):
        return
    fails_before = r.count("FAIL")
    groups = {g.get("id") for g in doc["groups"] if isinstance(g, dict) and "name" in g}
    if len(groups) != len(doc["groups"]):
        r.fail("lenses.json groups: every group needs id and name")
    ids = Counter(l.get("id") for l in doc["lenses"] if isinstance(l, dict))
    if any(k > 1 for k in ids.values()):
        r.fail(f"lenses.json: duplicate lens ids {[i for i, k in ids.items() if k > 1]}")
    keys = ["id", "group", "name", "icon", "emoji", "unit", "format", "scale", "domain", "ramp", "higher_is", "source", "description", "values"]
    for lens in doc["lenses"]:
        what = f"lenses.json {lens.get('id') if isinstance(lens, dict) else lens!r}"
        if not need_keys(r, what, lens, keys):
            continue
        if lens["group"] not in groups:
            r.fail(f"{what}: unknown group {lens['group']!r}")
        if lens["format"] not in LENS_FORMATS or lens["scale"] not in LENS_SCALES or lens["higher_is"] not in HIGHER_IS:
            r.fail(f"{what}: format/scale/higher_is must be one of {sorted(LENS_FORMATS)}/{sorted(LENS_SCALES)}/{sorted(HIGHER_IS)}")
        d = lens["domain"]
        if not (isinstance(d, list) and len(d) == 2 and all(is_num(v) for v in d) and d[0] < d[1]) or (lens["scale"] == "log" and d[0] <= 0):
            r.fail(f"{what}: domain must be [lo, hi] with lo < hi (lo > 0 for log): {d!r}")
        if not (isinstance(lens["ramp"], list) and len(lens["ramp"]) >= 2 and all(COLOR.match(str(c)) for c in lens["ramp"])):
            r.fail(f"{what}: ramp must be \u22652 #hex colours")
        if source_ids is not None and lens["source"] not in source_ids:
            r.warn(f"{what}: source {lens['source']!r} is not in sources.json")
        if "note" in lens and not (lens["note"] is None or isinstance(lens["note"], str)):
            r.fail(f"{what}: note must be a string or null")
        if lens["format"] == "category":
            _check_categories(r, what, lens)
        elif "categories" in lens:
            r.fail(f"{what}: categories is only for format 'category'")
        vals = lens["values"]
        if ctx is None:
            continue
        cells = doc.get("cells")
        if isinstance(cells, list) and isinstance(vals, list) and len(vals) == len(cells):
            full = [None] * ctx["n"]
            for c, v in zip(cells, vals):
                if is_int(c) and 0 <= c < ctx["n"]:
                    full[c] = v
            vals = full
        if not isinstance(vals, list) or len(vals) != ctx["n"]:
            r.fail(f"{what}: values must have {ctx['n']} entries, got {len(vals) if isinstance(vals, list) else type(vals).__name__}")
            continue
        bad = [i for i, v in enumerate(vals) if v is not None and not is_num(v)]
        if bad:
            r.fail(f"{what}: {len(bad)} values are neither number nor null (cells {_sample(bad)})")
        if ctx["owner"]:
            off = [i for i, v in enumerate(vals) if v is not None and ctx["owner"][i] < 0]
            if off:
                r.fail(f"{what}: {len(off)} values off Vietnamese land (must be null)")
        lo, hi = (-1, 100) if "growth" in str(lens.get("id")) else (0, 1)  # growth is a signed change
        if lens["format"] == "pct" and any(is_num(v) and not lo - 1e-9 <= v <= hi + 1e-9 for v in vals):
            r.fail(f"{what}: format pct but some values are outside {lo}..{hi} (pct lenses are fractions)")
        if lens["format"] == "category":
            n = len(lens["categories"]) if isinstance(lens.get("categories"), list) else 0
            if any(is_num(v) and not (is_int(v) and 0 <= v < n) for v in vals):
                r.fail(f"{what}: category values must be integer indices into categories (0..{n - 1}) or null")
    if r.count("FAIL") == fails_before:
        r.ok(f"lenses.json: {len(doc['lenses'])} lenses in {len(groups)} groups ({doc['vintage']})")


def _check_categories(r: Report, what: str, lens: dict) -> None:
    """A categorical lens: categories [{id, name, color}], ramp = their colours, linear domain [0, n-1]."""
    cats = lens.get("categories")
    if not (isinstance(cats, list) and len(cats) >= 2
            and all(isinstance(c, dict) and {"id", "name", "color"} <= c.keys() and COLOR.match(str(c["color"])) for c in cats)):
        r.fail(f"{what}: format category needs categories: [{{id, name, color}}] (\u22652, #hex colours)")
        return
    n = len(cats)
    if [str(c).lower() for c in lens["ramp"]] != [str(c["color"]).lower() for c in cats]:
        r.fail(f"{what}: ramp must list the categories' colours in order")
    if lens["scale"] != "linear" or lens["domain"] != [0, n - 1]:
        r.fail(f"{what}: a categorical lens needs scale 'linear' and domain [0, {n - 1}]")
    if len({c["id"] for c in cats}) != n:
        r.fail(f"{what}: duplicate category ids")


def check_resources(r: Report, doc, ctx: dict | None, source_ids: set | None, city_ids: set | None = None) -> None:
    if not need_keys(r, "resources.json", doc, ["types", "items"]):
        return
    fails_before = r.count("FAIL")
    types = {}
    for t in doc["types"]:
        what = f"resources.json type {t.get('id') if isinstance(t, dict) else t!r}"
        if not need_keys(r, what, t, ["id", "name", "category", "emoji", "icon", "color", "unit", "description", "source"]):
            continue
        types[t["id"]] = t
        if t["category"] not in RESOURCE_CATEGORIES or not COLOR.match(str(t["color"])):
            r.fail(f"{what}: category must be {sorted(RESOURCE_CATEGORIES)} and color #hex")
        if source_ids is not None and t["source"] not in source_ids:
            r.warn(f"{what}: source {t['source']!r} is not in sources.json")
    abbrs = {s.get("abbr") for s in ctx["states"] if isinstance(s, dict)} if ctx and ctx["states"] else None
    bad_type, bad_shape, outside, bad_place = Counter(), 0, 0, 0
    for it in doc["items"]:
        if not isinstance(it, dict) or not {"type", "name", "x", "y", "cell", "value", "detail", "state", "cbsa"} <= it.keys():
            bad_shape += 1
            continue
        if it["type"] not in types:
            bad_type[it["type"]] += 1
        if (it["state"] is not None and abbrs is not None and it["state"] not in abbrs) or not (
                it["cbsa"] is None or (city_ids is None and isinstance(it["cbsa"], str)) or (city_ids and it["cbsa"] in city_ids)):
            bad_place += 1
        if not (is_num(it["x"]) and is_num(it["y"]) and is_int(it["cell"])) or (it["value"] is not None and not is_num(it["value"])):
            bad_shape += 1
        elif ctx and (not 0 <= it["cell"] < ctx["n"] or not (0 <= it["x"] <= (ctx["width"] or math.inf) and 0 <= it["y"] <= (ctx["height"] or math.inf))):
            outside += 1
    if bad_shape:
        r.fail(f"resources.json: {bad_shape} items malformed (need type, name, x, y, cell, value number|null, detail, state, cbsa)")
    if bad_place:
        r.fail(f"resources.json: {bad_place} items with a state that is not a world.json abbr or a cbsa that is not a cities.json id")
    _check_resource_summary(r, doc.get("summary"), types, [it for it in doc["items"] if isinstance(it, dict)])
    if bad_type:
        r.fail(f"resources.json: items with unknown types {dict(bad_type)}")
    if outside:
        r.warn(f"resources.json: {outside} items outside the map")
    if r.count("FAIL") == fails_before:
        per = Counter(it.get("type") for it in doc["items"] if isinstance(it, dict))
        r.ok(f"resources.json: {len(types)} types, {len(doc['items'])} items ({_sample(f'{k} {v}' for k, v in per.most_common())})")


def _check_resource_summary(r: Report, summary, types: dict, items: list) -> None:
    """summary.national/states recomputed from the items: counts and value sums must match."""
    if not need_keys(r, "resources.json summary", summary, ["note", "national", "states"]):
        return
    expect_n: dict = defaultdict(lambda: [0, 0])
    expect_s: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for it in items:
        v = it.get("value") if is_num(it.get("value")) else 0
        for row in [expect_n[it.get("type")]] + ([expect_s[it["state"]][it.get("type")]] if it.get("state") else []):
            row[0] += 1
            row[1] += v

    def same(what, got, want, t):
        if not (isinstance(got, dict) and {"count", "value", "unit"} <= got.keys()):
            return f"{what}: needs count, value, unit"
        if got["count"] != want[0] or (types.get(t) and got["unit"] != types[t]["unit"]):
            return f"{what}: count/unit {got['count']}/{got['unit']!r} do not match the items ({want[0]})"
        if t in NOT_ADDITIVE:
            return None if got["value"] is None else f"{what}: value must be null (play areas are not additive)"
        if not is_num(got["value"]) or abs(got["value"] - want[1]) > 1:
            return f"{what}: value {got['value']!r} != sum of item values {round(want[1])}"
        return None

    errs = []
    nat = summary["national"]
    if not isinstance(nat, dict) or set(nat) != set(types):
        errs.append(f"national must have exactly the types {sorted(types)}")
    else:
        errs += [e for t in types if (e := same(f"national.{t}", nat[t], expect_n[t], t))]
    st = summary["states"]
    if not isinstance(st, dict) or set(st) != set(expect_s):
        errs.append(f"states must have exactly the states with items {sorted(expect_s)}")
    else:
        for a, rows in expect_s.items():
            if not isinstance(st[a], dict) or set(st[a]) != set(rows):
                errs.append(f"states.{a}: types {sorted(st[a]) if isinstance(st[a], dict) else st[a]!r} != {sorted(rows)}")
                continue
            errs += [e for t in rows if (e := same(f"states.{a}.{t}", st[a][t], rows[t], t))]
    for e in errs[:5]:
        r.fail(f"resources.json summary {e}")


def check_sources(r: Report, doc) -> set | None:
    if not isinstance(doc, list):
        r.fail("sources.json: expected a list")
        return None
    fails_before = r.count("FAIL")
    keys = ["id", "title", "publisher", "homepage", "license", "description", "used_for", "vintage", "files"]
    ids = set()
    for s in doc:
        what = f"sources.json {s.get('id') if isinstance(s, dict) else s!r}"
        if not need_keys(r, what, s, keys):
            continue
        if s["id"] in ids:
            r.fail(f"{what}: duplicate id")
        ids.add(s["id"])
        bad = [f for f in s["files"] if not isinstance(f, dict) or not {"file", "url", "retrieved", "sha256", "bytes"} <= f.keys()]
        if bad:
            r.fail(f"{what}: {len(bad)} file entries lack file/url/retrieved/sha256/bytes")
        if not s["files"]:
            r.warn(f"{what}: no files cited (not fetched yet?)")
    if r.count("FAIL") == fails_before:
        r.ok(f"sources.json: {len(doc)} sources, {sum(len(s['files']) for s in doc if isinstance(s, dict))} files")
    return ids


# ---------------------------------------------------------------- data quality


def _interim(interim_dir: Path, name: str):
    p = interim_dir / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def quality_rivers(r: Report, ctx: dict) -> None:
    W, H = ctx["width"], ctx["height"]
    if not (is_num(W) and is_num(H)):
        return
    outside_all, stray = [], 0
    for rv in ctx["rivers"]:
        pts = rv.get("pts") if isinstance(rv, dict) else None
        if not isinstance(pts, list):
            continue
        inside = [0 <= pts[j] <= W and 0 <= pts[j + 1] <= H for j in range(0, len(pts) - 1, 2)]
        if not any(inside):
            outside_all.append(rv.get("name"))
        stray += inside.count(False)
    if outside_all:
        r.warn(f"rivers entirely outside the map: {len(outside_all)} ({_sample(outside_all)})")
    elif stray:
        r.warn(f"rivers: {stray} vertices outside the map (contract says clipped)")
    else:
        r.ok(f"rivers: all {len(ctx['rivers'])} inside the map")


def quality_lens_nulls(r: Report, ctx: dict, lenses: dict) -> None:
    if not ctx["owner"]:
        return
    us = [i for i, o in enumerate(ctx["owner"]) if o >= 0]
    for lens in lenses.get("lenses", []):
        vals = lens.get("values") if isinstance(lens, dict) else None
        if not isinstance(vals, list) or len(vals) != ctx["n"] or not us:
            continue
        share = sum(1 for i in us if vals[i] is None) / len(us)
        coarse = share > LENS_NULL_WARN and lens.get("id") in SPARSE_LENSES
        (r.note if coarse else r.warn if share > LENS_NULL_WARN else r.ok)(
            f"lens {lens.get('id')}: {share:.1%} of {len(us)} land cells are null"
            + (" (expected: data exists only where noted)" if coarse else f" (warn above {LENS_NULL_WARN:.0%})"))


# ---------------------------------------------------------------- entry point


def _load(r: Report, web_dir: Path, name: str, required: bool):
    p = web_dir / name
    if not p.exists():
        (r.fail if required else r.note)(f"{name}: missing" + ("" if required else " (optional, skipped)"))
        return None
    try:
        return json.loads(p.read_text())
    except ValueError as exc:
        r.fail(f"{name}: invalid JSON ({exc})")
        return None


LEVELS = ("PASS", "NOTE", "WARN", "FAIL")


def builder_checks() -> list[tuple[str, object]]:
    """(builder module name, check function) for every pipeline/build module that defines check(web_dir).

    Helpers without build() count too, so a module can check a file another builder writes.
    """
    import importlib
    import pkgutil

    from . import build as build_pkg

    out = []
    for m in sorted(pkgutil.iter_modules(build_pkg.__path__), key=lambda m: m.name):
        mod = importlib.import_module(f"{build_pkg.__name__}.{m.name}")
        fn = getattr(mod, "check", None)
        if callable(fn):
            out.append((m.name, fn))
    return out


def run_builder_checks(r: Report, web_dir: Path, checks=None) -> None:
    """Run each builder's check(web_dir) and add its lines to the report (prefixed with the builder name)."""
    checks = builder_checks() if checks is None else checks
    if not checks:
        return
    r.section("builder checks")
    for name, fn in checks:
        try:
            lines = fn(web_dir) or []
        except Exception as exc:  # a broken check must not hide the rest of the report
            r.fail(f"{name}: check() raised {type(exc).__name__}: {exc}")
            continue
        for item in lines:
            try:
                level, msg = item
            except (TypeError, ValueError):
                r.fail(f"{name}: check() returned {item!r}, expected (level, message)")
                continue
            level = str(level).upper()
            if level not in LEVELS:
                r.fail(f"{name}: unknown level {level!r} for: {msg}")
                continue
            r._add(level, f"{name}: {msg}")


def run(web_dir: Path = WEB_DATA, interim_dir: Path = INTERIM, quiet: bool = False, builder_checks_=None) -> Report:
    """Run every check and return the report.

    builder_checks_: None = discover the builder check() functions (part 3); a list of (name, fn) to run those
    instead; [] to skip part 3.
    """
    r = Report(quiet)
    r.section("contracts (docs/DATA_CONTRACTS.md v2)")
    docs = {name: _load(r, web_dir, name, True) for name in REQUIRED}
    docs.update({name: _load(r, web_dir, name, False) for name in OPTIONAL})
    ctx = check_world(r, docs["world.json"]) if docs["world.json"] is not None else None
    source_ids = check_sources(r, docs["sources.json"]) if docs["sources.json"] is not None else None
    yield_keys = check_nation(r, docs["nation.json"]) if docs["nation.json"] is not None else YIELD_KEYS
    city_ids = None
    if docs["cities.json"] is not None:
        check_cities(r, docs["cities.json"], ctx)
        if isinstance(docs["cities.json"], list):
            city_ids = {c.get("id") for c in docs["cities.json"] if isinstance(c, dict)}
    if docs["states.json"] is not None:
        check_states(r, docs["states.json"], ctx, yield_keys)
        if docs["nation.json"] is not None:
            check_nation_sums(r, docs["nation.json"], docs["states.json"])
    if docs["lenses.json"] is not None:
        check_lenses(r, docs["lenses.json"], ctx, source_ids)
    if docs["resources.json"] is not None:
        check_resources(r, docs["resources.json"], ctx, source_ids, city_ids)
    if docs["counties.json"] is not None:
        check_counties(r, docs["counties.json"], ctx)

    r.section("data quality")
    if ctx is None:
        r.note("world.json unusable; skipping the data-quality report")
        run_builder_checks(r, web_dir, builder_checks_)
        return r
    if isinstance(docs["lenses.json"], dict):
        lenses = docs["lenses.json"]
        cells = lenses.get("cells")
        if isinstance(cells, list):
            lenses = {**lenses, "lenses": [{**l, "values": _spread(l.get("values"), cells, ctx["n"])}
                                           for l in lenses.get("lenses", []) if isinstance(l, dict)]}
        quality_lens_nulls(r, ctx, lenses)
    quality_rivers(r, ctx)
    run_builder_checks(r, web_dir, builder_checks_)
    return r


def _spread(vals, cells, n):
    if not isinstance(vals, list) or len(vals) != len(cells):
        return vals
    full = [None] * n
    for c, v in zip(cells, vals):
        if is_int(c) and 0 <= c < n:
            full[c] = v
    return full


def main(web_dir: Path = WEB_DATA, interim_dir: Path = INTERIM) -> int:
    r = run(web_dir, interim_dir)
    print(f"\ncheck: {r.count('PASS')} pass, {r.count('WARN')} warn, {r.count('FAIL')} fail")
    return 1 if r.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
