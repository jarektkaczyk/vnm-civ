"""NSO Statistical Yearbook 2025: the appendix of indicators for the 34 provinces (2020-2025 on the borders of 2025).

The yearbook is one PDF with a text layer. Each appendix table is found by its number on the pages after the
appendix contents, its province rows are read with the small PDF reader in _pdf.py, and its numeric columns are
told apart by where the numbers end on the page (the tables right-align numbers). The 2020-2024 figures of merged
provinces are the NSO's own conversion to the 2025 borders.
"""

from __future__ import annotations

import re

from ..core.source import Source, SourceInfo
from . import vn_admin_units as U
from ._pdf import Pdf, merge_cells

URL = "https://www.nso.gov.vn/wp-content/uploads/2026/07/NG-TOAN-QUOC-2025-1.pdf"
FILE = "2025/NG-TOAN-QUOC-2025-1.pdf"
PAGE = "https://www.nso.gov.vn/default/2026/07/nien-giam-thong-ke-2025/"
APPENDIX_FROM = 1157  # page index of the first appendix table (after the appendix contents)
APPENDIX_TO = 1532
YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]

# table number -> (column names, unit, label, note). Series tables have one column per year 2020-2025 (2025 is
# preliminary or estimated); single-year tables name their own columns.
TABLES: dict[int, tuple[list[str], str, str, str]] = {
    5: (["area_km2", "population_k", "density"], "", "Area, population and density 2025", "Area at 31 Dec 2024"),
    6: (YEARS, "thousand persons", "Average population", ""),
    9: (YEARS, "thousand persons", "Average urban population", ""),
    16: (YEARS, "children per woman", "Total fertility rate", ""),
    22: (YEARS, "per 1,000", "Net migration rate", ""),
    24: (YEARS, "years", "Life expectancy at birth", ""),
    34: (YEARS, "%", "Share of the labour force aged 15+ with training", ""),
    35: (YEARS, "million VND per worker", "Labour productivity", ""),
    38: (YEARS, "%", "Unemployment rate of the labour force at working age", ""),
    42: (YEARS, "%", "GRDP index at constant 2010 prices (previous year = 100)", ""),
    43: (YEARS, "million VND", "GRDP per capita", ""),
    47: (["iip_2025"], "%", "Index of industrial production 2025 (2024 = 100)", ""),
    48: (["projects", "capital_musd"], "", "Foreign direct investment in effect at 31 Dec 2025", ""),
    54: (YEARS, "per 1,000 people", "Active enterprises per 1,000 people", ""),
    79: (YEARS, "thousand tonnes", "Rice production", ""),
    110: (["forest", "natural", "planted", "cover_pct"], "thousand ha", "Forest area at 31 Dec 2025", ""),
    117: (YEARS, "tonnes", "Fishery production", ""),
    120: (YEARS, "tonnes", "Aquaculture production", ""),
    123: (YEARS, "billion VND", "Retail sales of goods and services", ""),
    127: (YEARS, "billion VND", "Turnover of travel agencies", ""),
    149: (["doctors_2025"], "persons", "Doctors in the State sector", ""),
    158: (["total", "wage", "agri", "nonagri", "other"], "thousand VND per month",
          "Monthly income per capita 2025", ""),
    164: (YEARS, "index", "Human Development Index", ""),
    173: (YEARS, "%", "Poverty rate (multidimensional)", ""),
    175: (YEARS, "%", "Population using a hygienic water source", ""),
    186: (["2024", "2025"], "%", "Internet users", ""),
}

_NUM = re.compile(r"^-?\d+(,\d+)?$")


def parse_number(s: str) -> float | None:
    """A yearbook number ("3359,8"); "-" is the yearbook's mark for no occurrence, a real zero; ".." and the rest
    are no data (None)."""
    s = s.strip().replace(" ", "")
    if s == "-":
        return 0.0
    s = re.sub(r"\.(?=\d{3}(?:[.,]|$))", "", s)  # thousands dots ("1.898,5", "1.866.929")
    if not _NUM.match(s):
        return None
    return float(s.replace(",", "."))


def table_pages(index: dict[int, list[int]], num: int, start: int) -> list[int]:
    """The page indices of table `num` from page `start` to the page before a later table starts (at most 4). A
    continuation page prints the table number in pieces, so only larger numbers end the table."""
    later = sorted(p for n, ps in index.items() for p in ps if p > start and n > num)
    end = later[0] if later else start + 2
    return list(range(start, min(end, start + 4)))


def province_rows(pdf: Pdf, pages: list[int], ncols: int) -> dict[str, list[float | None]]:
    """{province code: [values]} from the pages of one table. Columns are clustered by the right edge of the numbers
    on each page; a page whose rows have fewer numbers than `ncols` leaves the missing columns null."""
    out: dict[str, list[float | None]] = {}
    for pg in pages:
        rows = []
        for raw in pdf.page_rows(pg):
            cells = merge_cells(raw)
            if not cells or cells[0][0] > 80:
                continue
            k = 0
            while k < len(cells) and cells[k][0] < 200 and parse_number(cells[k][1]) is None:
                k += 1  # the name may be printed in pieces ("Hung", "Yen")
            name = " ".join(s for _, s in cells[:k])
            code = "VN" if U.fold(name).startswith("canuoc") else U.province_code(name)
            if code is None:
                continue
            nums = []
            for x, s in cells[k:]:
                s = s.strip()
                if s and parse_number(s) is None and len(re.findall(r"-?\d+,\d", s)) > 1:
                    # two numbers printed so close that they merged ("1120929,11313219,3"): split them
                    for part in re.findall(r"-?\d+,\d", s):
                        nums.append((x + len(part) * 4.3, part))
                        x += len(part) * 4.3 + 4
                    continue
                nums.append((x + len(s) * 4.3, s))
            nums = [(r, s) for r, s in nums if s]
            rows.append((code, nums))
        if not rows:
            continue
        # Column anchors: the right edges of the rows that have every column.
        full = [n for _, n in rows if len(n) == ncols]
        if not full:
            raise ValueError(f"pages {pages}: no province row has {ncols} numbers")
        anchors = [sum(n[k][0] for n in full) / len(full) for k in range(ncols)]
        for code, nums in rows:
            if code in out:
                continue  # the first row of a code wins (a following table may share the last page)
            vals: list[float | None] = [None] * ncols
            for r, s in nums:
                k = min(range(ncols), key=lambda j: abs(anchors[j] - r))
                if abs(anchors[k] - r) < 18:
                    vals[k] = parse_number(s)
            out[code] = vals
    return out


class VnNsoYearbook(Source):
    info = SourceInfo(
        id="vn_nso_yearbook",
        title="Statistical Yearbook of Viet Nam 2025, appendix of the 34 provinces",
        publisher="National Statistics Office of Viet Nam (NSO, C\u1ee5c Th\u1ed1ng k\u00ea), Ministry of Finance",
        homepage=PAGE,
        license="NSO terms: free to reuse with the source named (\"Ngu\u1ed3n: C\u1ee5c Th\u1ed1ng k\u00ea\"); no open licence is named.",
        description="The appendix of the Statistical Yearbook 2025 gives the main indicators of the 34 provinces "
        "and centrally run cities, 2020-2025, on the borders of 1 July 2025 (2025 figures are preliminary, GRDP "
        "estimated): area, population, urban population, fertility, migration, life expectancy, labour, GRDP, "
        "industrial production, foreign investment, enterprises, rice, fishery, forest, retail, travel, doctors, "
        "the Human Development Index, poverty, clean water and internet use.",
        used_for=["Province lenses", "Province figures in the panels and the advisors"],
    )

    def fetch(self, force=False):
        self.download(URL, FILE, force=force, expect_binary=True)

    def process(self):
        pdf = Pdf((self.raw_dir / FILE).read_bytes())
        index: dict[int, list[int]] = {}
        for pg in range(APPENDIX_FROM, min(APPENDIX_TO, len(pdf.pages))):
            for raw in pdf.page_rows(pg)[:6]:
                cells = merge_cells(raw)
                if cells and cells[0][0] < 50 and re.fullmatch(r"\d{1,3}", cells[0][1].strip()):
                    index.setdefault(int(cells[0][1]), []).append(pg)
                    break
        # Tables follow each other in number order. Walking the pages, a number starts a table only when it is a little
        # above the current one: a contents page that lists table 117 among the farm tables, or a continuation page
        # whose number is printed in pieces ("1" for 13), is not a start.
        starts, cur = {}, min(TABLES) - 1
        for pg in range(APPENDIX_FROM, min(APPENDIX_TO, len(pdf.pages))):
            for n, pages in index.items():
                if pg in pages and cur < n <= cur + 4:
                    starts[n] = pg
                    cur = n
        tables = {}
        problems = []
        for num, (cols, unit, label, note) in TABLES.items():
            if num not in index:
                problems.append(f"table {num} not found")
                continue
            rows, pages, errs = {}, [], []
            for start in ([starts[num]] if num in starts else []) + [pg for pg in index[num] if pg != starts.get(num)]:
                pages = table_pages(index, num, start)
                try:
                    rows = province_rows(pdf, pages, len(cols))
                except ValueError as exc:
                    errs.append(f"table {num}: {exc}")
                    rows = {}
                if rows:
                    break
            if not rows:
                problems += errs or [f"table {num}: no province rows"]
                continue
            if "VN" not in rows:
                problems.append(f"table {num}: no national row")
            missing = sorted(set(U.PROVINCE_NAME) - set(rows))
            if missing:
                problems.append(f"table {num}: no row for {', '.join(U.PROVINCE_NAME[c] for c in missing)}")
            tables[str(num)] = {"label": label, "unit": unit, "note": note, "columns": cols,
                                "pages": [p for p in pages],
                                "rows": {c: dict(zip(cols, v)) for c, v in sorted(rows.items())}}
            print(f"    table {num:>3} ({label}): {len(rows)} provinces, pages {pages[0]}-{pages[-1]}")
        for p in problems:
            print(f"    ! {p}")
        return {
            "vintage": "NSO Statistical Yearbook 2025 (published 2026-07; 2025 preliminary)",
            "_files": [FILE],
            "tables": tables,
            "notes": problems,
        }
