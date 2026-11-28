"""Ember electricity data for the country of ENERGY_COUNTRY: generation by source per month (monthly release) and per
year with the installed capacity (yearly release). A country outside the monthly set keeps the yearly series only."""

from __future__ import annotations

import csv
import io

from ..core.source import Source, SourceInfo
from .energy_common import TECHS
from .energy_config import ENERGY_COUNTRY

BASE = "https://files.ember-energy.org/public-downloads/generation/outputs/"
FILES = {"monthly": "release_generation_monthly_global.csv", "yearly": "release_generation_yearly_global.csv"}
# Ember "Electricity source" -> module technology. "Other fossil" is oil and other fossil fuels.
SERIES = {"Solar": "solar", "Wind": "wind", "Hydro": "hydro", "Coal": "coal", "Gas": "gas", "Other fossil": "oil",
          "Nuclear": "nuclear", "Bioenergy": "biomass", "Other renewables": "other"}
TOTALS = {"Total generation": "total", "Net imports": "net_imports", "Demand": "demand"}


def _num(v):
    try:
        return None if v in (None, "") else float(v)
    except ValueError:
        return None


def country_rows(text: str) -> list[dict]:
    """The rows of the configured country (by ISO 3 code, else by area name)."""
    iso3, name = ENERGY_COUNTRY["iso3"], ENERGY_COUNTRY.get("ember_name")
    return [r for r in csv.DictReader(io.StringIO(text))
            if (r.get("ISO 3 code") or "") == iso3 or (not r.get("ISO 3 code") and r.get("Area") == name)]


def series(rows: list[dict], key: str) -> dict:
    """{periods, gen_twh: {tech|total: [...]}, share_pct: {tech: [...]}, capacity_gw: {tech: [...]}} sorted by period."""
    periods = sorted({r[key][:7] if key == "Date" else r[key] for r in rows})
    at = {p: i for i, p in enumerate(periods)}
    n = len(periods)
    gen = {k: [None] * n for k in [*TECHS, "total", "net_imports", "demand"]}
    share = {k: [None] * n for k in TECHS}
    cap = {k: [None] * n for k in TECHS}
    for r in rows:
        if str(r.get("Is aggregated source")).lower() == "true" and r["Electricity source"] not in TOTALS:
            continue
        i = at[r[key][:7] if key == "Date" else r[key]]
        src = r["Electricity source"]
        tech = SERIES.get(src) or TOTALS.get(src)
        if tech is None:
            continue
        g = _num(r.get("Generation (TWh)"))
        if g is not None:
            gen[tech][i] = round((gen[tech][i] or 0) + g, 4)
        if tech in share:
            s = _num(r.get("Share of generation (%)"))
            if s is not None:
                share[tech][i] = round((share[tech][i] or 0) + s, 3)
            c = _num(r.get("Capacity (GW)"))
            if c is not None:
                cap[tech][i] = round((cap[tech][i] or 0) + c, 3)
    out = {"periods": periods, "gen_twh": gen, "share_pct": share}
    if key == "Year":
        out["periods"] = [int(p) for p in periods]
        out["capacity_gw"] = cap
    return out


class EnergyEmber(Source):
    info = SourceInfo(
        id="energy_ember",
        title="Monthly and yearly electricity data",
        publisher="Ember",
        homepage="https://ember-energy.org/data/monthly-electricity-data/",
        license="CC BY 4.0",
        description="Electricity generation by source for each month and each year, the share of each source and the "
        "installed capacity by source at the end of each year.",
        used_for=["Power plants by year (installed capacity, electricity mix)", "Electricity mix"],
    )

    def fetch(self, force=False):
        for name in FILES.values():
            self.download(BASE + name, name, force=force)

    def process(self):
        out = {"iso3": ENERGY_COUNTRY["iso3"]}
        used, vint = [], []
        for kind, name in FILES.items():
            path = self.download(BASE + name, name)
            rows = country_rows(path.read_text(encoding="utf-8"))
            if not rows:
                out[kind] = None
                print(f"    {kind}: no rows for {ENERGY_COUNTRY['iso3']}")
                continue
            used.append(name)
            s = series(rows, "Date" if kind == "monthly" else "Year")
            out[kind] = s
            vint.append(f"{kind} to {s['periods'][-1]}")
            print(f"    {kind}: {len(s['periods'])} periods {s['periods'][0]}-{s['periods'][-1]}")
        out["coverage"] = "monthly" if out.get("monthly") else "yearly" if out.get("yearly") else "none"
        return {**out, "vintage": "Ember, " + ", ".join(vint) if vint else "Ember", "_files": used}
