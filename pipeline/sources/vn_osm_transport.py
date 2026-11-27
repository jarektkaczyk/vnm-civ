"""Vietnam's expressways, national highways and railways from OpenStreetMap (Overpass API).

* roads: `highway=motorway` (the expressways, cao toc) and `highway=trunk` (the national highways, quoc lo). Ways
  under construction carry `highway=construction` and are left out.
* rail: `railway=rail` without sidings and yards (`service=*`): the North-South Railway and the lines of the north.

Output is `lines` (chains of ways with the same class and ref, simplified to about 300 m) and a country table of
lengths measured on the unsimplified geometry.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from ..core.source import Source, SourceInfo
from ._osm import ODBL_NOTE, chain_ways, line_length_km, osm_elements, osm_timestamp, overpass_tiled, round_coords, simplify

ROADS_BODY = 'way["highway"~"^(motorway|trunk)$"](area.vn)({bbox});'
RAIL_BODY = 'way["railway"="rail"][!"service"](area.vn)({bbox});'
TOLERANCE_M = 300.0


def road_ref(tags: dict) -> str | None:
    """The first route number in `ref` ('QL.1A;AH1' -> 'QL1A', 'CT.01' -> 'CT01'), else None."""
    for part in re.split(r"[;,]", tags.get("ref") or ""):
        m = re.fullmatch(r"\s*(CT|QL|AH)\s*\.?\s*(\d+[A-Z]?)\s*", part.strip(), re.I)
        if m:
            return m.group(1).upper() + m.group(2).upper()
    return None


def summarize(elements: list[dict], kind_of) -> tuple[dict, list[dict]]:
    km: dict[str, float] = defaultdict(float)
    groups: dict[tuple, list] = defaultdict(list)
    names: dict[tuple, Counter] = defaultdict(Counter)
    for el in elements:
        tags = el.get("tags") or {}
        coords = [(g["lon"], g["lat"]) for g in el.get("geometry") or [] if g]
        if len(coords) < 2:
            continue
        kind = kind_of(tags)
        oneway = (tags.get("oneway") or "").lower() in ("yes", "1", "true") or tags.get("highway") == "motorway"
        length = line_length_km(coords)
        km[kind] += length / 2 if oneway and kind != "rail" else length
        key = (kind, road_ref(tags) if kind != "rail" else None)
        groups[key].append(coords)
        if tags.get("name"):
            names[key][tags["name"]] += 1
    lines = []
    for (kind, ref), ways in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        for i, chain in enumerate(chain_ways(ways)):
            lines.append({"id": f"{kind}:{ref or '-'}:{i}", "kind": kind, "ref": ref,
                          "name": names[(kind, ref)].most_common(1)[0][0] if names[(kind, ref)] else None,
                          "coords": round_coords(simplify(chain, TOLERANCE_M))})
    return dict(km), lines


class VnOsmTransport(Source):
    info = SourceInfo(
        id="vn_osm_transport",
        title="Expressways, national highways and railways of Vietnam (OpenStreetMap)",
        publisher="OpenStreetMap contributors (via the Overpass API)",
        homepage="https://www.openstreetmap.org/",
        license="ODbL 1.0. " + ODBL_NOTE,
        description="The expressways and national highways open to traffic and the railway lines, as mapped in "
        "OpenStreetMap on the extract date. Geometry is simplified to about 300 m.",
        used_for=["Roads and railways on the map"],
    )

    def _paths(self, force=False):
        return overpass_tiled(self, ROADS_BODY, "roads", force=force), overpass_tiled(self, RAIL_BODY, "rail", force=force)

    def fetch(self, force=False):
        self._paths(force=force)

    def process(self):
        roads_p, rail_p = self._paths()
        road_km, road_lines = summarize(osm_elements(roads_p), lambda t: t.get("highway"))
        rail_km, rail_lines = summarize(osm_elements(rail_p), lambda t: "rail")
        stamp = osm_timestamp(list(roads_p) + list(rail_p))
        date = stamp[:10] if stamp else None
        print(f"    {len(road_lines)} road lines, {len(rail_lines)} rail lines; km: "
              + ", ".join(f"{k} {v:,.0f}" for k, v in {**road_km, **rail_km}.items()))
        return {
            "vintage": f"OpenStreetMap extract {date}" if date else "OpenStreetMap",
            "osm_timestamp": stamp,
            "km": {k: round(v, 1) for k, v in {**road_km, **rail_km}.items()},
            "lines": road_lines + rail_lines,
            "notes": [ODBL_NOTE, "Rule (roads): highway=motorway (expressways) and highway=trunk (national highways). "
                      "Rule (rail): railway=rail without a service tag."],
            "_files": [str(p.relative_to(self.raw_dir)) for p in list(roads_p) + list(rail_p)],
        }
