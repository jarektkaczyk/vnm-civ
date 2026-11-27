"""Gridded lenses (interim `_grid_lenses`): population density (WorldPop 2025), night lights 2024 and their growth
since 2014 (VIIRS), rainfall 2025 (CHIRPS v3) and typhoons since 1981 (IBTrACS), one value per land hex of Vietnam.

* Density: the WorldPop people of the 1 km cells whose centre lies in the hex, per km2 of the hex's land.
* Night lights: the mean radiance of the 1 arc-minute samples whose centre lies in the hex.
* Rainfall: the CHIRPS cell under the hex centre.
* Typhoons: storms of typhoon strength (sustained wind of 64 knots or more, USA agency or WMO agency) whose track
  passes within 50 km of the hex centre, 1981-2025.

Also writes the night lights of every year 2014-2024 per hex (`timelapse`) for the time-lapse lens.
"""

from __future__ import annotations

import math

from ..core.geo import MapProjection
from ..core.hexgrid import SQRT3, HexGrid
from ..core.store import load_interim, save_interim
from .vnunits import optional

REQUIRES = ["_world", "vn_worldpop", "vn_nightlights", "vn_chirps", "vn_ibtracs"]
PRODUCES = ["_grid_lenses"]
TYPHOON_KT = 64
TYPHOON_KM = 50.0
TYPHOON_FROM = 1981


def proj_of(world) -> MapProjection:
    p = world["projection"]
    return MapProjection(p["min_x"], p["max_y"], p.get("margin", 0))


def cell_map(win: dict, proj, grid: HexGrid) -> list[list[int]]:
    """The hex of each sample centre of a lon/lat window (-1 outside the map)."""
    out = []
    for r in range(len(win["rows"])):
        lat = win["lat_top"] - (r + 0.5) * win["step_y"]
        out.append([grid.cell_at(*proj(win["lon0"] + (c + 0.5) * win["step_x"], lat)) for c in range(win["cols"])])
    return out


def aggregate(win: dict, cells: list[list[int]], size: int, how: str) -> list:
    acc = [0.0] * size
    n = [0] * size
    for row, crow in zip(win["rows"], cells):
        for v, i in zip(row, crow):
            if i >= 0 and v is not None:
                acc[i] += v
                n[i] += 1
    if how == "sum":
        return [acc[i] if n[i] else None for i in range(size)]
    return [acc[i] / n[i] if n[i] else None for i in range(size)]


def lens(lid, name, unit, fmt, scale, ramp, higher, source, desc, values, **extra) -> dict:
    return {"id": lid, "group": extra.pop("group", "climate"), "name": name, "unit": unit, "format": fmt,
            "scale": scale, "ramp": ramp, "higher_is": higher, "source": source, "description": desc,
            "level": "hex", "values": values, **extra}


def typhoon_counts(storms: list[dict], grid: HexGrid, proj, land: list[bool]) -> list[int]:
    counts = [0] * grid.size
    R = TYPHOON_KM
    for st in storms:
        if st["season"] < TYPHOON_FROM:
            continue
        hit = set()
        pts = [(proj(p[2], p[1]), p[3]) for p in st["points"]]
        for (a, wa), (b, wb) in zip(pts, pts[1:]):
            if max(wa or 0, wb or 0) < TYPHOON_KT:
                continue
            (ax, ay), (bx, by) = a, b
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy or 1e-9
            x0, x1 = min(ax, bx) - R, max(ax, bx) + R
            y0, y1 = min(ay, by) - R, max(ay, by) + R
            r0, r1 = max(0, int(y0 / (1.5 * grid.radius))), min(grid.rows - 1, int(y1 / (1.5 * grid.radius)) + 1)
            c0 = max(0, int(x0 / (SQRT3 * grid.radius)) - 1)
            c1 = min(grid.cols - 1, int(x1 / (SQRT3 * grid.radius)) + 1)
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    i = grid.index(c, r)
                    if not land[i] or i in hit:
                        continue
                    px, py = grid.center(c, r)
                    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
                    if math.hypot(px - ax - t * dx, py - ay - t * dy) <= R:
                        hit.add(i)
        for i in hit:
            counts[i] += 1
    return counts


def build() -> None:
    world = load_interim("_world")
    grid = HexGrid(**world["grid"])
    proj = proj_of(world)
    owner = world["owner"]
    land = [o >= 0 for o in owner]
    hex_area = 1.5 * SQRT3 * grid.radius ** 2
    out = {"lenses": [], "timelapse": None}

    wp = (optional("vn_worldpop") or {}).get("data")
    if wp:
        pop = aggregate(wp, cell_map(wp, proj, grid), grid.size, "sum")
        smp = world["county_samples"]
        vals = []
        for i in range(grid.size):
            if not land[i]:
                vals.append(None)
                continue
            share = (sum(1 for k in smp[i] if k >= 0) / len(smp[i])) if smp[i] else 1.0
            vals.append(round((pop[i] or 0.0) / (hex_area * max(share, 0.3)), 1))
        out["lenses"].append(lens("density", "Population density", "people per km\u00b2", "int", "log",
                                  ["#1b1035", "#4b2377", "#9a3b8a", "#e0645e", "#f9b24a", "#fff3a8"], "neutral",
                                  "vn_worldpop", "Residents per km\u00b2 of land, 2025.", vals, group="people",
                                  icon="l-density", emoji="\U0001f465"))
        print(f"    density: {sum(v for v in pop if v):,.0f} people on the hexes")

    nl = (optional("vn_nightlights") or {}).get("data")
    if nl:
        cells = cell_map({**nl, "rows": nl["years"][str(min(map(int, nl["years"])))]}, proj, grid)
        years = sorted(nl["years"], key=int)
        per_year = {}
        for y in years:
            v = aggregate({**nl, "rows": nl["years"][y]}, cells, grid.size, "mean")
            per_year[y] = [round(x, 2) if land[i] and x is not None else None for i, x in enumerate(v)]
        last, first = years[-1], years[0]
        out["lenses"].append(lens("nightlights", "Night lights", "nW/cm\u00b2/sr", "float", "log",
                                  ["#03051a", "#1d1a4a", "#4c3a7a", "#a86a4a", "#f0b84a", "#fff6c8"], "neutral",
                                  "vn_nightlights", f"Average night-time light seen from space, {last}.", per_year[last], group="enterprise", emoji="\U0001f4a1"))
        growth = []
        for i in range(grid.size):
            a, b = per_year[first][i], per_year[last][i]
            growth.append(None if a is None or b is None or a < 0.5 else round(b / a - 1, 3))
        out["lenses"].append(lens("nightlights_growth", f"Night-light growth {first}-{last}", "", "pct", "linear",
                                  ["#0f5257", "#3c8c8a", "#9cc9bf", "#efe4c6", "#e8b86a", "#c9822a", "#8a4f12"],
                                  "neutral", "vn_nightlights", f"Change in the night-time light from {first} to {last}.", growth,
                                  group="enterprise", emoji="\U0001f4a1", short_name="Light growth"))
        out["timelapse"] = {"years": [int(y) for y in years], "values": [per_year[y] for y in years]}

    ch = (optional("vn_chirps") or {}).get("data")
    if ch:
        vals = []
        for i in range(grid.size):
            if not land[i]:
                vals.append(None)
                continue
            lon, lat = proj.inverse(*grid.center(*grid.col_row(i)))
            r, c = int((ch["lat_top"] - lat) / ch["step_y"]), int((lon - ch["lon0"]) / ch["step_x"])
            v = ch["rows"][r][c] if 0 <= r < len(ch["rows"]) and 0 <= c < ch["cols"] else None
            vals.append(None if v is None else round(v))
        out["lenses"].append(lens("rain", f"Rainfall {ch['year']}", "mm per year", "int", "linear",
                                  ["#1d1405", "#4a3a12", "#4f6b2a", "#2f8f6b", "#3aa6c4", "#cfeefa"], "neutral",
                                  "vn_chirps", f"Total rainfall of {ch['year']}.",
                                  vals, emoji="\U0001f327\ufe0f"))

    ib = (optional("vn_ibtracs") or {}).get("data")
    if ib:
        counts = typhoon_counts(ib["storms"], grid, proj, land)
        last = max(s["season"] for s in ib["storms"])
        vals = [counts[i] if land[i] else None for i in range(grid.size)]
        out["lenses"].append(lens("typhoons", f"Typhoons {TYPHOON_FROM}-{last}", "storms", "int", "linear",
                                  ["#0b2a2e", "#165a5c", "#2f8f83", "#e0b04a", "#e0645e", "#a3261f"], "bad",
                                  "vn_ibtracs", f"Typhoons that passed close to the hex, {TYPHOON_FROM}-{last}.", vals,
                                  emoji="\U0001f300"))
        print(f"    typhoons: max {max(c for c in counts)} storms on one hex")
    save_interim("_grid_lenses", out)
    print(f"    {len(out['lenses'])} gridded lenses: " + ", ".join(l["id"] for l in out["lenses"]))
