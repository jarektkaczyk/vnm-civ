"""Global Forest Watch country statistics for Vietnam: tree cover loss 2001-2025 by province of the time (63
provinces, GADM boundaries), from the Hansen / UMD Global Forest Change data, at the 30% canopy threshold."""

from __future__ import annotations

from ..core.source import Source, SourceInfo
from . import vn_admin_units as U
from ._xlsx import read_xlsx

URL = "https://gfw2-data.s3.amazonaws.com/country-pages/country_stats/download/2025/VNM.xlsx"
FILE = "2025/VNM.xlsx"
THRESHOLD = 30
SHEET = "Subnational 1 tree cover loss"


class VnGfw(Source):
    info = SourceInfo(
        id="vn_gfw",
        title="Global Forest Watch: tree cover loss in Vietnam by province, 2001-2025",
        publisher="World Resources Institute (Global Forest Watch), from Hansen et al. / University of Maryland "
        "Global Forest Change v1.13",
        homepage="https://www.globalforestwatch.org/dashboards/country/VNM/",
        license="CC BY 4.0. Hansen, M. C. et al. (2013), High-Resolution Global Maps of 21st-Century Forest Cover "
        "Change, Science 342: 850-853",
        description="Hectares of tree cover lost each year from 2001 to 2025 in each of the 63 provinces of the "
        "time (tree cover = canopy of 30% or more in 2000), and the tree cover of 2000. Loss counts any removal of "
        "tree canopy, including the harvest of plantations.",
        used_for=["Tree cover loss lens (63 former provinces)"],
    )

    def fetch(self, force=False):
        self.download(URL, FILE, force=force, expect_binary=True)

    def process(self):
        rows = read_xlsx(self.raw_dir / FILE, SHEET)
        head = rows[0]
        col = {k: j for j, k in enumerate(head)}
        years = [int(k.rsplit("_", 1)[1]) for k in head if str(k).startswith("tc_loss_ha_")]
        out = {}
        unmatched = []
        for r in rows[1:]:
            if len(r) < len(head) or r[col["threshold"]] != THRESHOLD:
                continue
            code = U.former_code(str(r[col["subnational1"]]))
            if code is None:
                unmatched.append(r[col["subnational1"]])
                continue
            loss = {y: r[col[f"tc_loss_ha_{y}"]] for y in years}
            out[code] = {"extent_2000_ha": r[col["extent_2000_ha"]], "area_ha": r[col["area_ha"]],
                         "loss_ha": {str(y): v for y, v in loss.items()}}
        if unmatched:
            print(f"    ! names not matched: {unmatched}")
        missing = sorted(set(U.FORMER_NAME) - set(out))
        if missing:
            raise ValueError(f"GFW: no row for {[U.FORMER_NAME[c] for c in missing]}")
        print(f"    {len(out)} provinces, loss {years[0]}-{years[-1]} at {THRESHOLD}% canopy")
        return {"vintage": f"GFW country statistics 2025 (Hansen GFC v1.13, {years[0]}-{years[-1]})", "_files": [FILE],
                "threshold": THRESHOLD, "years": [years[0], years[-1]], "rows": out}
