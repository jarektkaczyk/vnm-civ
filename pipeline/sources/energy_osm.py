"""Power plants of the ENERGY_COUNTRY from OpenStreetMap (Overpass API): every power=plant with its energy source,
electrical output, start date and end date where the mappers recorded them."""

from __future__ import annotations

import re

import json

from ..core.source import Source, SourceInfo
from .energy_common import bands, country_area, overpass, overpass_ok, parse_mw, tech_of, year_of
from .energy_config import ENERGY_COUNTRY

ODBL = ("Map data (c) OpenStreetMap contributors, available under the Open Database Licence (ODbL 1.0), "
        "https://www.openstreetmap.org/copyright.")


def aliases(tags: dict) -> list[str]:
    """Other names of an OSM plant: alt_name, old_name, official_name, short_name, name:vi (";" lists), and the last
    part of a source or website link when it is a slug of three words or more
    (".../nha-may-dien-gio-hung-hai-gia-lai/" -> "nha may dien gio hung hai gia lai")."""
    out = []
    for k in ("alt_name", "old_name", "official_name", "short_name", "name:vi"):
        out += [v.strip() for v in str(tags.get(k) or "").split(";") if v.strip()]
    for k in ("source", "website"):
        v = str(tags.get(k) or "")
        if v.startswith("http"):
            slug = v.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
            words = [w for w in re.split(r"[-_]", slug.split(".")[0]) if w.isalpha()]
            if len(words) >= 3:
                out.append(" ".join(words))
    return [v for v in dict.fromkeys(out) if v != tags.get("name")]


def plant_point(el: dict) -> dict | None:
    """One Overpass element -> a plant dict, or None without a position or a known energy source."""
    tags = el.get("tags") or {}
    if "lat" in el and "lon" in el:
        lon, lat = el["lon"], el["lat"]
    elif el.get("center"):
        lon, lat = el["center"]["lon"], el["center"]["lat"]
    else:
        return None
    tech = tech_of(tags.get("plant:source"), tags.get("generator:source"))
    if tech is None:
        return None
    mw = parse_mw(tags.get("plant:output:electricity"))
    end = year_of(tags.get("end_date"), tags.get("disused:start_date"))
    building = (any(k in tags for k in ("construction:power", "planned:power", "proposed:power"))
                or tags.get("construction") == "power" or tags.get("landuse") == "construction")
    status = ("retired" if end or any(k.startswith(("disused:", "abandoned:")) for k in tags)
              else "planned" if building else "operating")  # planned: in construction or proposed, never drawn
    return {"id": f"osm:{el['type']}/{el['id']}", "tech": tech, "name": tags.get("name") or None,
            "name_en": tags.get("name:en") or None, "aliases": aliases(tags), "owner": tags.get("operator") or None, "mw": None if mw is None else round(mw, 2),
            "start": year_of(tags.get("start_date"), tags.get("opening_date")), "end": end, "status": status,
            "lon": round(lon, 5), "lat": round(lat, 5)}


class EnergyOsm(Source):
    info = SourceInfo(
        id="energy_osm",
        title="Power plants (OpenStreetMap)",
        publisher="OpenStreetMap contributors (via the Overpass API)",
        homepage="https://www.openstreetmap.org/",
        license="ODbL 1.0. " + ODBL,
        description="Every power plant mapped in OpenStreetMap, with its energy source, its electrical output and its "
        "start year where they are recorded.",
        used_for=["Power plants by year", "Power capacity", "Power plants on the map"],
    )

    def _paths(self, force=False):
        paths = []
        for s, w, n, e in bands():
            q = (f"[out:json][timeout:180];{country_area()}"
                 f'(nwr["power"="plant"](area.c)({s},{w},{n},{e}););out tags center qt;')
            paths.append(overpass(self, q, f"plants/{ENERGY_COUNTRY['iso2']}_{s:g}_{w:g}.json", force=force))
        return paths

    def fetch(self, force=False):
        self._paths(force=force)

    def _cached(self) -> list:
        """The band answers when all are cached; else every complete cached Overpass answer in plants/ (for example
        answers of an earlier band layout), so a run without Overpass access still processes."""
        want = [self.raw_dir / f"plants/{ENERGY_COUNTRY['iso2']}_{s:g}_{w:g}.json" for s, w, _n, _e in bands()]
        if all(p.exists() and overpass_ok(p) for p in want):
            return want
        got = sorted(p for p in (self.raw_dir / "plants").glob("*.json") if overpass_ok(p))
        if not got:
            return self._paths()
        print(f"    using {len(got)} cached Overpass answers (run fetch energy_osm --force for the newest data)")
        return got

    def process(self):
        paths = self._cached()
        seen, points, stamps = set(), [], []
        for p in paths:
            doc = json.loads(p.read_text(encoding="utf-8"))
            ts = (doc.get("osm3s") or {}).get("timestamp_osm_base")
            if ts:
                stamps.append(ts)
            for el in doc.get("elements", []):
                key = (el.get("type"), el.get("id"))
                if key in seen:
                    continue
                seen.add(key)
                pt = plant_point(el)
                if pt:
                    points.append(pt)
        stamp = max(stamps) if stamps else ""
        print(f"    {len(points)} plants; {sum(1 for p in points if p['mw'])} with an output, "
              f"{sum(1 for p in points if p['start'])} with a start year")
        return {"vintage": f"OpenStreetMap extract {stamp[:10]}" if stamp else "OpenStreetMap", "points": points,
                "notes": [ODBL], "_files": [str(p.relative_to(self.raw_dir)) for p in paths]}
