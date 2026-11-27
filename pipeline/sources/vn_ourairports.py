"""OurAirports: the airports of Vietnam with scheduled passenger service."""

from __future__ import annotations

import csv
import io

from ..core.source import Source, SourceInfo

URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
FILE = "airports.csv"
KINDS = {"large_airport": "large", "medium_airport": "medium", "small_airport": "small"}


class VnOurAirports(Source):
    info = SourceInfo(
        id="vn_ourairports",
        title="OurAirports airport list",
        publisher="OurAirports (David Megginson and contributors)",
        homepage="https://ourairports.com/data/",
        license="Public domain",
        description="Every airport in Vietnam that the list marks as having scheduled passenger service, with its "
        "size class (large, medium), codes and position.",
        used_for=["Airports on the map"],
    )

    def fetch(self, force=False):
        self.download(URL, FILE, force=force)

    def process(self):
        text = (self.raw_dir / FILE).read_text(encoding="utf-8")
        points = []
        for r in csv.DictReader(io.StringIO(text)):
            if r["iso_country"] != "VN" or r["scheduled_service"] != "yes" or r["type"] not in KINDS:
                continue
            points.append({"id": f"airport:{r['ident']}", "name": r["name"], "kind": KINDS[r["type"]],
                           "icao": r["icao_code"] or r["ident"], "iata": r["iata_code"] or None,
                           "city": r["municipality"] or None, "lon": float(r["longitude_deg"]),
                           "lat": float(r["latitude_deg"])})
        print(f"    {len(points)} airports with scheduled service")
        return {"vintage": "OurAirports, data of the download day", "_files": [FILE], "points": points}
