"""Airports and seaports of Vietnam as areas, from OpenStreetMap (Overpass API): the aerodrome outlines, their
runways, and the port areas (`landuse=port`, `industrial=port`)."""

from __future__ import annotations

from ..core.source import Source, SourceInfo
from ._osm import ODBL_NOTE, chain_ways, osm_elements, osm_timestamp, overpass_tiled, round_coords, simplify

BODY = ('way["aeroway"="aerodrome"](area.vn)({bbox});'
        'way["aeroway"="runway"](area.vn)({bbox});'
        'way["landuse"="port"](area.vn)({bbox});'
        'way["industrial"="port"](area.vn)({bbox});')
# Multipolygon relations (Noi Bai, Long Thanh) need their members, which "out tags geom" leaves out.
REL_BODY = 'rel["aeroway"="aerodrome"](area.vn)({bbox});rel["landuse"="port"](area.vn)({bbox});'
TOLERANCE_M = 15.0


def _rings(el: dict) -> list[list[tuple[float, float]]]:
    if el["type"] == "way":
        g = [(p["lon"], p["lat"]) for p in el.get("geometry") or [] if p]
        return [g] if len(g) >= 3 else []
    parts = []
    for m in el.get("members") or []:
        if m.get("type") == "way" and m.get("role") in ("outer", "") and m.get("geometry"):
            g = [(p["lon"], p["lat"]) for p in m["geometry"] if p]
            if len(g) >= 2:
                parts.append(g)
    # Outer rings are often split over several ways: join them end to end.
    return [r for r in chain_ways(parts) if len(r) >= 3]


class VnOsmHubs(Source):
    info = SourceInfo(
        id="vn_osm_hubs",
        title="Airport and port areas of Vietnam (OpenStreetMap)",
        publisher="OpenStreetMap contributors (via the Overpass API)",
        homepage="https://www.openstreetmap.org/",
        license="ODbL 1.0. " + ODBL_NOTE,
        description="The outline of every aerodrome with its runways, and the port areas, as mapped in OpenStreetMap "
        "on the extract date. They are drawn as areas when the map is zoomed in.",
        used_for=["Airports and seaports drawn as areas"],
    )

    def _paths(self, force=False):
        # The relations come first: an element seen twice keeps its first copy, the one with members.
        return (overpass_tiled(self, REL_BODY, "hub_relations", force=force, out="out body geom qt;")
                + overpass_tiled(self, BODY, "hubs", force=force))

    def fetch(self, force=False):
        self._paths(force=force)

    def process(self):
        paths = self._paths()
        aerodromes, runways, ports = [], [], []
        for el in osm_elements(paths):
            tags = el.get("tags") or {}
            name = tags.get("name:vi") or tags.get("name") or None
            if tags.get("aeroway") == "runway" and el["type"] == "way":
                line = [(p["lon"], p["lat"]) for p in el.get("geometry") or [] if p]
                if len(line) >= 2:
                    runways.append({"id": f"osm:way/{el['id']}", "ref": tags.get("ref"),
                                    "width_m": float(tags["width"]) if (tags.get("width") or "").replace(".", "").isdigit() else None,
                                    "line": round_coords(line)})
                continue
            rings = [round_coords(simplify(r, TOLERANCE_M)) for r in _rings(el)]
            rings = [r for r in rings if len(r) >= 3]
            if not rings:
                continue
            item = {"id": f"osm:{el['type']}/{el['id']}", "name": name, "iata": tags.get("iata"),
                    "icao": tags.get("icao"), "rings": rings}
            if tags.get("aeroway") == "aerodrome":
                aerodromes.append(item)
            else:
                ports.append(item)
        stamp = osm_timestamp(paths)
        print(f"    {len(aerodromes)} aerodromes, {len(runways)} runways, {len(ports)} port areas")
        return {"vintage": f"OpenStreetMap extract {stamp[:10]}" if stamp else "OpenStreetMap",
                "aerodromes": aerodromes, "runways": runways, "ports": ports, "notes": [ODBL_NOTE],
                "_files": [str(p.relative_to(self.raw_dir)) for p in paths]}
