"""WRI Global Power Plant Database v1.3 (2021): plants of the ENERGY_COUNTRY with capacity, primary fuel and
commissioning year. Used only for plants that the other plant sources miss (pipeline/build/energy.py)."""

from __future__ import annotations

import csv
import io
import zipfile

from ..core.source import Source, SourceInfo
from .energy_common import tech_of, year_of
from .energy_config import ENERGY_COUNTRY

URL = "https://wri-dataportal-prod.s3.amazonaws.com/manual/global_power_plant_database_v_1_3.zip"
ZIP = "global_power_plant_database_v_1_3.zip"
CSV = "global_power_plant_database.csv"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class EnergyWri(Source):
    info = SourceInfo(
        id="energy_wri",
        title="Global Power Plant Database v1.3",
        publisher="World Resources Institute",
        homepage="https://datasets.wri.org/dataset/globalpowerplantdatabase",
        license="CC BY 4.0",
        description="Power plants of 1 MW or more worldwide with their capacity, main fuel and the year they started, "
        "as of 2021. Used only for plants missing from the other plant sources.",
        used_for=["Power plants by year", "Power capacity"],
    )

    def fetch(self, force=False):
        self.download(URL, ZIP, force=force, expect_binary=True)

    def process(self):
        path = self.download(URL, ZIP, expect_binary=True)
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith(CSV))
            text = z.read(name).decode("utf-8")
        points = []
        for r in csv.DictReader(io.StringIO(text)):
            if r["country"] != ENERGY_COUNTRY["iso3"]:
                continue
            lat, lon, mw = _f(r["latitude"]), _f(r["longitude"]), _f(r["capacity_mw"])
            tech = tech_of(r["primary_fuel"])
            if lat is None or lon is None or tech is None:
                continue
            points.append({"id": f"wri:{r['gppd_idnr']}", "tech": tech, "name": r["name"] or None,
                           "mw": None if not mw else round(mw, 2), "start": year_of(r["commissioning_year"]),
                           "end": None, "status": "operating", "lon": round(lon, 5), "lat": round(lat, 5)})
        print(f"    {len(points)} plants; {sum(1 for p in points if p['start'])} with a start year")
        return {"vintage": "Global Power Plant Database v1.3 (June 2021)", "points": points, "_files": [ZIP]}
