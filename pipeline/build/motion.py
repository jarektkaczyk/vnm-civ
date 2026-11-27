"""Data of the moving layers: typhoons.json (storm tracks year by year, IBTrACS) and timelapse.json (night lights of
every year 2014-2024 per land hex, for the time-lapse lens)."""

from __future__ import annotations

import datetime as dt

from ..core.geo import MapProjection
from ..core.hexgrid import HexGrid
from ..core.store import load_interim, write_web
from .vnunits import optional

REQUIRES = ["_world", "vn_ibtracs", "_grid_lenses"]
PRODUCES = ["typhoons.json", "timelapse.json"]
FROM_YEAR = 1981
PAD_KM = 150  # track points this far outside the map are kept, so tracks enter and leave at the edge
TYPHOON_KT = 64
RULES = [
    f"Every tropical storm of {FROM_YEAR} or later in IBTrACS whose track crosses the map, drawn year by year.",
    "A track is coloured by the storm's sustained wind at each point (the US agency's 1-minute wind, else the wind of "
    "the WMO agency, a 10-minute wind): tropical depression below 34 knots, tropical storm 34-63 knots, "
    f"typhoon {TYPHOON_KT} knots or more.",
]


def year_fraction(iso: str, year: int) -> float:
    """Time since 1 January of `year` in years: a storm that runs into January of the next year goes above 1."""
    d = dt.datetime.fromisoformat(iso)
    return round((d - dt.datetime(year, 1, 1)).total_seconds() / (365.25 * 86400), 4)


def build() -> None:
    world = load_interim("_world")
    grid = HexGrid(**world["grid"])
    p = world["projection"]
    proj = MapProjection(p["min_x"], p["max_y"], p.get("margin", 0))
    W, H = grid.cols * grid.radius * 3 ** 0.5, grid.rows * grid.radius * 1.5

    ib = optional("vn_ibtracs")
    if ib:
        storms = []
        for st in ib["data"]["storms"]:
            if st["season"] < FROM_YEAR:
                continue
            pts, inside = [], False
            year0 = int(st["points"][0][0][:4])
            for k, (iso, lat, lon, wind, _nature) in enumerate(st["points"]):
                x, y = proj(lon, lat)
                if not (-PAD_KM <= x <= W + PAD_KM and -PAD_KM <= y <= H + PAD_KM):
                    continue
                inside = inside or (0 <= x <= W and 0 <= y <= H)
                if k % 2 and k != len(st["points"]) - 1:
                    continue  # 6-hourly is enough for the art
                pts += [round(x, 1), round(y, 1), -1 if wind is None else wind, year_fraction(iso, year0)]
            if not inside or len(pts) < 8:
                continue
            winds = [w for w in pts[2::4] if w >= 0]
            storms.append({"id": st["sid"], "name": st["name"], "season": st["season"],
                           "year": int(st["points"][0][0][:4]), "peak_kt": max(winds) if winds else None, "pts": pts})
        last = max(s["season"] for s in storms)
        write_web("typhoons.json", {"version": 1, "vintage": ib["vintage"], "sources": ["vn_ibtracs"],
                                    "rules": RULES, "years": [FROM_YEAR, last], "typhoon_kt": TYPHOON_KT,
                                    "storms": storms})
        print(f"    {len(storms)} storms {FROM_YEAR}-{last}")

    gl = (optional("_grid_lenses") or {}).get("data") or {}
    tl = gl.get("timelapse")
    if tl:
        land = [i for i, o in enumerate(world["owner"]) if o >= 0]
        write_web("timelapse.json", {
            "version": 1, "vintage": (optional("vn_nightlights") or {}).get("vintage") or "",
            "sources": ["vn_nightlights"],
            "rules": ["The average night-time light of each year, the mean of the 1 arc-minute samples in the hex."],
            "nightlights": {"years": tl["years"], "cells": land,
                            "values": [[row[i] for i in land] for row in tl["values"]]},
        })
        print(f"    night lights {tl['years'][0]}-{tl['years'][-1]} on {len(land)} hexes")
