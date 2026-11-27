"""The provincial units: the 63 -> 34 mapping of Resolution 202/2025/QH15, name matching, and the PDF table helpers."""

import unittest

from pipeline.sources import vn_admin_units as U
from pipeline.sources._pdf import _run, merge_cells
from pipeline.sources.vn_nso_yearbook import parse_number


class UnitsTest(unittest.TestCase):
    def test_34_units_partition_the_63(self):
        self.assertEqual(len(U.FORMER), 63)
        self.assertEqual(len(U.PROVINCES), 34)
        olds = [o for *_, olds, _ in U.PROVINCES for o in olds]
        self.assertEqual(len(olds), 63)
        self.assertEqual(set(olds), {c for c, _ in U.FORMER})

    def test_kinds_and_codes(self):
        kinds = [k for _, _, k, *_ in U.PROVINCES]
        self.assertEqual(kinds.count("city"), 6)
        self.assertEqual(kinds.count("province"), 28)
        # Each new code is the code of one of its own former provinces (Decision 19/2025/QD-TTg).
        for code, _, _, _, olds, _ in U.PROVINCES:
            self.assertIn(code, olds)
        self.assertEqual(len({a for _, _, _, a, _, _ in U.PROVINCES}), 34)
        self.assertTrue(all(a.isascii() for _, _, _, a, _, _ in U.PROVINCES))

    def test_known_merges(self):
        self.assertEqual(U.NEW_OF["74"], "79")  # Binh Duong -> Ho Chi Minh City
        self.assertEqual(U.NEW_OF["77"], "79")  # Ba Ria - Vung Tau -> Ho Chi Minh City
        self.assertEqual(U.NEW_OF["49"], "48")  # Quang Nam -> Da Nang
        self.assertEqual(U.NEW_OF["64"], "52")  # Gia Lai -> new Gia Lai (centre in Quy Nhon)
        self.assertEqual(U.NEW_OF["01"], "01")  # Ha Noi unchanged

    def test_names_in_any_spelling(self):
        # geoBoundaries spellings (a trailing tab, no diacritics, an en dash), the yearbook's "TP." prefix.
        self.assertEqual(U.former_code("H\u00e0 N\u1ed9i\t"), "01")
        self.assertEqual(U.former_code("Ho Chi Minh"), "79")
        self.assertEqual(U.former_code("B\u00e0 R\u1ecba\u2013V\u0169ng T\u00e0u"), "77")
        self.assertEqual(U.former_code("Th\u1eeba Thi\u00ean Hu\u1ebf"), "46")
        self.assertEqual(U.province_code("TP. H\u1ed3 Ch\u00ed Minh"), "79")
        self.assertEqual(U.province_code("Hu\u1ebf"), "46")
        self.assertEqual(U.province_code("\u0110\u1eafk L\u1eafk"), "66")
        self.assertIsNone(U.province_code("\u0110\u1ed3ng b\u1eb1ng s\u00f4ng H\u1ed3ng"))
        for code, name in U.FORMER:
            self.assertEqual(U.former_code(name), code)
        for code, name, *_ in U.PROVINCES:
            self.assertEqual(U.province_code(name), code)

    def test_archipelagos_belong_to_da_nang_and_khanh_hoa(self):
        by = {a["id"]: a["province"] for a in U.ARCHIPELAGOS}
        self.assertEqual(by, {"hoang_sa": "48", "truong_sa": "56"})


class PdfTablesTest(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(parse_number("3359,8"), 3359.8)
        self.assertEqual(parse_number("-1,0"), -1.0)
        self.assertEqual(parse_number("2636"), 2636.0)
        self.assertEqual(parse_number("-"), 0.0)  # the yearbook mark for no occurrence
        self.assertIsNone(parse_number(".."))
        self.assertEqual(parse_number("1.898,5"), 1898.5)  # a thousands dot
        self.assertEqual(parse_number("1.866.929"), 1866929.0)
        self.assertIsNone(parse_number("H\u00e0 N\u1ed9i"))

    def test_merge_cells_joins_touching_pieces(self):
        row = [(62.4, "B\u1eafc Ninh"), (317.5, "3"), (321.7, "57"), (330.22, "2"), (334.42, ",4"), (398.4, "758")]
        self.assertEqual([s for _, s in merge_cells(row)], ["B\u1eafc Ninh", "3572,4", "758"])

    def test_text_operators(self):
        content = b"BT /F1 8 Tf 1 0 0 1 100 700 Tm (12,5) Tj 40 0 Td [(3)-20(4)] TJ ET"
        out = _run(content, lambda name: ({}, 1))
        self.assertEqual(out, [(100, 700, "12,5"), (140, 700, "34")])


if __name__ == "__main__":
    unittest.main()
