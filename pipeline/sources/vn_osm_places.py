"""Place names of Vietnam from OpenStreetMap (Overpass API): every named city, town, suburb and village node, with
its Vietnamese name. The town builder uses them to give an urban centre of the GHSL database the Vietnamese spelling
with tone marks where the database writes a plain name ("Trang Bang" becomes "Trảng Bàng")."""

from __future__ import annotations

from ..core.source import Source, SourceInfo
from ._osm import ODBL_NOTE, el_lonlat, osm_elements, osm_timestamp, overpass_tiled

BODY = 'node["place"~"^(city|town|suburb|village)$"]["name"](area.vn)({bbox});'


class VnOsmPlaces(Source):
    info = SourceInfo(
        id="vn_osm_places",
        title="Place names of Vietnam (OpenStreetMap)",
        publisher="OpenStreetMap contributors (via the Overpass API)",
        homepage="https://www.openstreetmap.org/",
        license="ODbL 1.0. " + ODBL_NOTE,
        description="Named cities, towns, suburbs and villages mapped in OpenStreetMap in Vietnam, with the "
        "Vietnamese spelling and its tone marks. They fix the spelling of the town names.",
        used_for=["Spelling of town names"],
    )

    def _paths(self, force=False):
        return overpass_tiled(self, BODY, "places", force=force, out="out body qt;")

    def fetch(self, force=False):
        self._paths(force=force)

    def process(self):
        paths = self._paths()
        places = []
        for el in osm_elements(paths):
            tags = el.get("tags") or {}
            pos = el_lonlat(el)
            name = tags.get("name:vi") or tags.get("name")
            if pos is None or not name:
                continue
            places.append({"name": name, "place": tags["place"], "lon": round(pos[0], 5), "lat": round(pos[1], 5)})
        stamp = osm_timestamp(paths)
        print(f"    {len(places)} named places")
        return {
            "vintage": f"OpenStreetMap extract {stamp[:10]}" if stamp else "OpenStreetMap",
            "places": places,
            "notes": [ODBL_NOTE],
            "_files": [str(p.relative_to(self.raw_dir)) for p in paths],
        }
