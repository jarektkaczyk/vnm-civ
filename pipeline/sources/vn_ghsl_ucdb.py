"""GHSL Urban Centre Database R2024A (V1.2): the urban centres of Vietnam with their 2025 population.

An urban centre is a cluster of contiguous 1 km cells with at least 1,500 residents per km2 and 50,000 residents
in all (the Degree of Urbanisation method). The region file is a GeoPackage (SQLite); the general-characteristics
table holds the names and the population, the centroid table the position.
"""

from __future__ import annotations

import math
import sqlite3
import zipfile

from ..core.source import Source, SourceInfo

URL = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_UCDB_GLOBE_R2024A/GHS_UCDB_REGION_R2024A/"
       "GHS_UCDB_REGION_EASTERN_AND_SOUTH_EASTERN_ASIA_R2024A/V1-2/"
       "GHS_UCDB_REGION_EASTERN_AND_SOUTH_EASTERN_ASIA_R2024A_V1_2.zip")
FILE = "R2024A/GHS_UCDB_REGION_EASTERN_AND_SOUTH_EASTERN_ASIA_R2024A_V1_2.zip"
GENERAL = "GHSL_UCDB_THEME_GENERAL_CHARACTERISTICS_GLOBE_R2024A"
# The database names a few centres in English; the map uses the Vietnamese name.
NAMES = {"Ho Chi Minh City": "H\u1ed3 Ch\u00ed Minh", "Hanoi": "H\u00e0 N\u1ed9i"}


def mollweide_inverse(x: float, y: float, r: float = 6378137.0) -> tuple[float, float]:
    """World Mollweide (ESRI:54009, sphere of the WGS 84 major axis) metres -> (lon, lat) degrees. The centroid
    table stores its GC_UCC_LON / GC_UCC_LAT in this projection."""
    theta = math.asin(max(-1.0, min(1.0, y / (r * math.sqrt(2)))))
    lat = math.asin((2 * theta + math.sin(2 * theta)) / math.pi)
    lon = math.pi * x / (2 * r * math.sqrt(2) * math.cos(theta))
    return math.degrees(lon), math.degrees(lat)


def fix_text(s: str | None) -> str | None:
    """Some names are UTF-8 read as Latin-1 ("Cao?n Th??"): undo that when it is the case."""
    if not s:
        return s
    try:
        fixed = s.encode("latin-1").decode("utf-8")
        return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


class VnGhslUcdb(Source):
    info = SourceInfo(
        id="vn_ghsl_ucdb",
        title="GHSL Urban Centre Database R2024A (V1.2), Eastern and South-Eastern Asia",
        publisher="European Commission, Joint Research Centre (GHSL)",
        homepage="https://human-settlement.emergency.copernicus.eu/ghs_ucdb_2024.php",
        license="CC BY 4.0. Mari Rivero, I. et al. (2024), GHS-UCDB R2024A - GHS Urban Centre Database 2025, "
        "European Commission, Joint Research Centre",
        description="Every urban centre in Vietnam (a dense cluster of at least 50,000 people), with its name, "
        "position and its population estimate for 2025. These are the towns on the map.",
        used_for=["Towns and their population"],
    )

    def fetch(self, force=False):
        self.download(URL, FILE, force=force, expect_binary=True)

    def _gpkg(self):
        out = self.raw_dir / "extract" / "ucdb.gpkg"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(self.raw_dir / FILE) as z:
                name = next(n for n in z.namelist() if n.endswith(".gpkg"))
                tmp = out.with_suffix(".part")
                tmp.write_bytes(z.read(name))
                tmp.replace(out)
        return out

    def process(self):
        db = sqlite3.connect(self._gpkg())
        pos = {r[0]: (r[1], r[2]) for r in db.execute(
            "SELECT ID_UC_G0, GC_UCC_LON_2025, GC_UCC_LAT_2025 FROM UC_centroids")}
        rows = db.execute(
            f'SELECT ID_UC_G0, GC_UCN_MAI_2025, GC_UCN_LIS_2025, GC_POP_TOT_2025, GC_UCA_KM2_2025, GC_UCM_CAP '
            f'FROM "{GENERAL}" WHERE GC_CNT_GAD_2025 = ? ORDER BY GC_POP_TOT_2025 DESC', ("Vietnam",)).fetchall()
        centres = []
        for uid, name, names, pop, area, cap in rows:
            name = fix_text(name)
            lon, lat = mollweide_inverse(*pos[uid])
            centres.append({"id": f"uc{uid}", "name": NAMES.get(name, name), "names": fix_text(names),
                            "population": round(pop) if pop is not None else None, "area_km2": area,
                            "capital": bool(cap), "lon": round(lon, 5), "lat": round(lat, 5)})
        db.close()
        print(f"    {len(centres)} urban centres; largest: " + ", ".join(
            f"{c['name']} {c['population']:,}" for c in centres[:5]))
        return {
            "vintage": "GHS-UCDB R2024A V1.2 (population 2025)",
            "_files": [FILE],
            "centres": centres,
        }
