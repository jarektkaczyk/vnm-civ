"""Power plants of Vietnam from OpenStreetMap (Overpass API): every `power=plant` with its source and electrical
output where the mappers recorded them, plus the start date for the solar and wind farms that have one."""

from __future__ import annotations

import re

from ..core.source import Source, SourceInfo
from ._osm import ODBL_NOTE, el_lonlat, osm_elements, osm_timestamp, overpass_tiled, parse_mw

BODY = 'nwr["power"="plant"](area.vn)({bbox});'
SOURCES = {"coal": "coal", "gas": "gas", "oil": "gas", "hydro": "hydro", "solar": "solar", "wind": "wind",
           "biomass": "biomass", "waste": "biomass", "biogas": "biomass", "nuclear": "nuclear"}


def year_of(tags: dict) -> int | None:
    m = re.search(r"(19|20)\d{2}", tags.get("start_date") or tags.get("opening_date") or "")
    return int(m.group(0)) if m else None


class VnOsmPower(Source):
    info = SourceInfo(
        id="vn_osm_power",
        title="Power plants of Vietnam (OpenStreetMap)",
        publisher="OpenStreetMap contributors (via the Overpass API)",
        homepage="https://www.openstreetmap.org/",
        license="ODbL 1.0. " + ODBL_NOTE,
        description="Every power plant mapped in OpenStreetMap in Vietnam, with its energy source (coal, gas, hydro, "
        "solar, wind, biomass) and its electrical output where it is recorded. Plants without a recorded output "
        "are kept without a value.",
        used_for=["Power plants on the map (resources)"],
    )

    def _paths(self, force=False):
        return overpass_tiled(self, BODY, "plants", force=force, out="out tags center qt;")

    def fetch(self, force=False):
        self._paths(force=force)

    def process(self):
        paths = self._paths()
        points = []
        for el in osm_elements(paths):
            tags = el.get("tags") or {}
            pos = el_lonlat(el)
            if pos is None:
                continue
            src = (tags.get("plant:source") or tags.get("generator:source") or "").split(";")[0].strip().lower()
            kind = SOURCES.get(src)
            if kind is None:
                continue
            mw = parse_mw(tags.get("plant:output:electricity"))
            points.append({"id": f"osm:{el['type']}/{el['id']}", "kind": kind,
                           "name": tags.get("name:vi") or tags.get("name") or None, "name_en": tags.get("name:en"),
                           "operator": tags.get("operator"), "mw": None if mw is None else round(mw, 1),
                           "year": year_of(tags), "lon": round(pos[0], 5), "lat": round(pos[1], 5)})
        stamp = osm_timestamp(paths)
        print(f"    {len(points)} plants with a known source; {sum(1 for p in points if p['mw'])} with an output")
        return {
            "vintage": f"OpenStreetMap extract {stamp[:10]}" if stamp else "OpenStreetMap",
            "points": points,
            "notes": [ODBL_NOTE],
            "_files": [str(p.relative_to(self.raw_dir)) for p in paths],
        }
