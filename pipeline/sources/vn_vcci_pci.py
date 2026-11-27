"""VCCI Provincial Competitiveness Index (PCI) 2025: nine sub-indices, the ranking group and the Business
Performance Index (BPI) of the 34 provinces, from the data workbook of the PCI 2025 report (May 2026)."""

from __future__ import annotations

from ..core.source import Source, SourceInfo
from . import vn_admin_units as U
from ._xlsx import read_xlsx

URL = "https://pcivietnam.vn/data_pci_file/general_file/1778745497-06.%20Du%20lieu%20PCI%202025.xlsx"
FILE = "2025/Du-lieu-PCI-2025.xlsx"

SUBINDICES = [
    ("entry", "Market entry"), ("land", "Access to land"), ("transparency", "Transparency"),
    ("compliance", "Cost of administrative compliance"), ("informal", "Informal charges"),
    ("competition", "Equal competition"), ("support", "Business support services"), ("legal", "Legal institutions"),
    ("proactive", "Proactive government"),
]
# Ranking groups of PCI 2.0, best first (the workbook's Vietnamese labels).
GROUPS = [("rat_tot", "R\u1ea5t t\u1ed1t", "Excellent"), ("tot", "T\u1ed1t", "Very good"), ("kha", "Kh\u00e1", "Good"),
          ("trung_binh", "Trung b\u00ecnh", "Average"), ("tuong_doi_thap", "T\u01b0\u01a1ng \u0111\u1ed1i th\u1ea5p", "Fairly low"),
          ("thap", "Th\u1ea5p", "Low")]


class VnVcciPci(Source):
    info = SourceInfo(
        id="vn_vcci_pci",
        title="Provincial Competitiveness Index (PCI) 2025",
        publisher="Vietnam Chamber of Commerce and Industry (VCCI), PCI project",
        homepage="https://pcivietnam.vn/",
        license="(c) 2026 PCI project, VCCI. No open licence is named; reused with the source named (\"Ngu\u1ed3n: VCCI, "
        "PCI 2025\").",
        description="The PCI 2025 survey of private firms scores each of the 34 provinces on nine sub-indices of "
        "economic governance (1 to 10, higher is better) and places it in a ranking group. The experimental "
        "Business Performance Index (BPI) scores the results of private business in each province.",
        used_for=["Governance lenses (PCI sub-indices, ranking group, BPI)"],
    )

    def fetch(self, force=False):
        self.download(URL, FILE, force=force, expect_binary=True)

    def process(self):
        path = self.raw_dir / FILE
        rows: dict[str, dict] = {}
        for r in read_xlsx(path, "PCI")[1:]:
            if not r or not isinstance(r[0], str):
                continue
            code = U.province_code(r[0])
            if code is None:
                continue
            vals = {key: round(float(v), 3) if isinstance(v, (int, float)) else None
                    for (key, _), v in zip(SUBINDICES, r[1:10])}
            group = next((g for g, vi, _ in GROUPS if U.fold(vi) == U.fold(str(r[10] or ""))), None)
            rows[code] = {**vals, "group": group}
        for r in read_xlsx(path, "BPI")[1:]:
            if r and isinstance(r[0], str):
                code = U.province_code(r[0])
                if code in rows and isinstance(r[1], (int, float)):
                    rows[code]["bpi"] = round(float(r[1]), 3)
        missing = sorted(set(U.PROVINCE_NAME) - set(rows))
        if missing:
            raise ValueError(f"PCI 2025: no row for {missing}")
        print(f"    {len(rows)} provinces; groups: " + ", ".join(
            f"{g} {sum(1 for x in rows.values() if x['group'] == g)}" for g, _, _ in GROUPS))
        return {
            "vintage": "PCI 2025 (VCCI, published 2026-05)",
            "_files": [FILE],
            "subindices": [{"key": k, "label": lab} for k, lab in SUBINDICES],
            "groups": [{"id": g, "name_vi": vi, "name": en} for g, vi, en in GROUPS],
            "rows": rows,
        }
