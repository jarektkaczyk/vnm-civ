"""2019 Population and Housing Census: migration between provinces in the five years before 1 April 2019, for the
63 provinces of the time (the complete results book, table 26).

In-migrants are residents of a province aged 5 and over who lived in another province five years earlier;
out-migrants are the people who left it in that time for another province.
"""

from __future__ import annotations

import re

from ..core.source import Source, SourceInfo
from . import vn_admin_units as U
from ._pdf import Pdf, merge_cells

URL = "https://www.nso.gov.vn/wp-content/uploads/2019/12/Ket-qua-toan-bo-Tong-dieu-tra-dan-so-va-nha-o-2019.pdf"
FILE = "2019/Ket-qua-toan-bo-Tong-dieu-tra-dan-so-va-nha-o-2019.pdf"
TABLE = "26"


def count(s: str) -> int | None:
    s = s.strip()
    if not re.fullmatch(r"-?\d{1,3}(\.\d{3})*", s):
        return None
    return int(s.replace(".", ""))


class VnCensus2019(Source):
    info = SourceInfo(
        id="vn_census_2019",
        title="2019 Population and Housing Census, complete results (migration between provinces)",
        publisher="General Statistics Office of Viet Nam (now the National Statistics Office)",
        homepage="https://www.nso.gov.vn/",
        license="NSO terms: free to reuse with the source named; no open licence is named.",
        description="Table 26 of the complete census results: for each of the 63 provinces of 2019, its residents "
        "aged 5 and over, the people who moved in from another province in the five years before 1 April 2019 and "
        "the people who moved out to another province.",
        used_for=["Migration lens (2019, 63 provinces)"],
    )

    def fetch(self, force=False):
        self.download(URL, FILE, force=force, expect_binary=True)

    def process(self):
        pdf = Pdf((self.raw_dir / FILE).read_bytes())
        # The table starts on the page whose heading reads "Bieu - Table 26"; the both-sexes rows come before the
        # page headed "NAM - MALE".
        start = None
        for pg in range(700, len(pdf.pages)):
            head = " ".join(s for r in pdf.page_rows(pg)[:2] for _, s in merge_cells(r))
            if re.search(r"Table 2\s*6\b", head) and "Ti\u1ebfp theo" not in head:
                start = pg
                break
        if start is None:
            raise ValueError("census table 26 not found")
        rows: dict[str, dict] = {}
        for pg in range(start, start + 6):
            lines = [merge_cells(r) for r in pdf.page_rows(pg)]
            if any("MALE" in " ".join(s for _, s in c) for c in lines[:8]):
                break
            for cells in lines:
                if not cells or cells[0][0] > 100:
                    continue
                k = 0
                while k < len(cells) and cells[k][0] < 250 and count(cells[k][1]) is None:
                    k += 1
                code = U.former_code(" ".join(s for _, s in cells[:k]))
                nums = [count(s) for _, s in cells[k:k + 3]]
                if code and code not in rows and len(nums) == 3 and all(n is not None for n in nums):
                    pop5, inm, outm = nums
                    rows[code] = {"pop5": pop5, "in": inm, "out": outm,
                                  "net_rate": round((inm - outm) / pop5 * 1000, 1)}
        missing = sorted(set(U.FORMER_NAME) - set(rows))
        if missing:
            raise ValueError(f"census table 26: no row for {[U.FORMER_NAME[c] for c in missing]}")
        print(f"    {len(rows)} provinces of 2019 (pages {start}-{pg})")
        return {
            "vintage": "Census 2019 (1 April 2019), migration in the five years before",
            "_files": [FILE],
            "rows": rows,
        }
