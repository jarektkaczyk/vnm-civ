"""IBTrACS v04r01 (NOAA NCEI): tropical cyclone tracks of the western North Pacific that come near Vietnam.

Keeps every storm since 1950 whose track enters the box lon 100-121, lat 4-26, with its 3-hourly points: time,
position, the sustained wind (the USA agency's 1-minute wind, else the WMO agency's 10-minute wind), and the storm's
nature.
"""

from __future__ import annotations

import csv
import io

from ..core.source import Source, SourceInfo

URL = ("https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/"
       "access/csv/ibtracs.WP.list.v04r01.csv")
FILE = "v04r01/ibtracs.WP.list.v04r01.csv"
BOX = (100.0, 4.0, 121.0, 26.0)
FROM_YEAR = 1950


def _num(s: str) -> float | None:
    s = (s or "").strip()
    try:
        return float(s)
    except ValueError:
        return None


class VnIbtracs(Source):
    info = SourceInfo(
        id="vn_ibtracs",
        title="International Best Track Archive for Climate Stewardship (IBTrACS) v04r01, western North Pacific",
        publisher="NOAA National Centers for Environmental Information",
        homepage="https://www.ncei.noaa.gov/products/international-best-track-archive",
        license="Public domain (U.S. Government work). Knapp, K. R. et al. (2010), The International Best Track Archive "
        "for Climate Stewardship (IBTrACS), Bull. Amer. Meteor. Soc. 91, 363-376; Gahtan, J. et al. (2024), IBTrACS "
        "v04r01, NOAA NCEI, doi:10.25921/82ty-9e16",
        description="Positions and winds of tropical storms and typhoons every 3 hours, merged from the warning "
        "agencies of the region (Japan, China, Hong Kong, the United States and others). Storms whose track comes "
        "within the box around Vietnam and the East Sea are kept. The typhoon lens counts the storms with a sustained "
        "wind of 64 knots or more whose track passed within 50 km of the hex.",
        used_for=["Typhoon lens", "Typhoon tracks year by year (moving layer)"],
    )

    def fetch(self, force=False):
        self.download(URL, FILE, force=force)

    def process(self):
        text = (self.raw_dir / FILE).read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        # Line 2 holds the units; the data start on line 3.
        reader = csv.DictReader(io.StringIO("\n".join([lines[0]] + lines[2:])))
        storms: dict[str, dict] = {}
        for r in reader:
            season = int(r["SEASON"])
            if season < FROM_YEAR:
                continue
            lat, lon = _num(r["LAT"]), _num(r["LON"])
            if lat is None or lon is None:
                continue
            sid = r["SID"]
            st = storms.get(sid)
            if st is None:
                name = (r["NAME"] or "").strip()
                st = storms[sid] = {"sid": sid, "name": None if name in ("", "NOT_NAMED", "UNNAMED") else name.title(),
                                    "season": season, "inside": False, "points": []}
            wind = _num(r.get("USA_WIND")) or _num(r.get("WMO_WIND"))
            st["points"].append([r["ISO_TIME"][:16], round(lat, 2), round(lon, 2),
                                 None if wind is None else round(wind), (r.get("NATURE") or "").strip()])
            if BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]:
                st["inside"] = True
        kept = [s for s in storms.values() if s.pop("inside")]
        kept.sort(key=lambda s: (s["points"][0][0], s["sid"]))
        last = max(s["season"] for s in kept)
        print(f"    {len(kept)} storms near Vietnam, {FROM_YEAR}-{last}")
        return {
            "vintage": f"IBTrACS v04r01, tracks to {kept[-1]['points'][-1][0][:10]}",
            "_files": [FILE],
            "box": list(BOX),
            "storms": kept,
        }
