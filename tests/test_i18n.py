"""English and Vietnamese: the catalogue lookup, plurals, number and date formats, ISO dates in data, the missing-key check.

The browser half (web/js/i18n.js) runs under node when it is installed.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pipeline.build import i18n as i18n_check
from pipeline.core import i18n

ROOT = Path(__file__).resolve().parent.parent
I18N_JS = ROOT / "web" / "js" / "i18n.js"
NBSP = "\u00a0"
CAT = {
    "Median age": "Tu\u1ed5i trung v\u1ecb",
    "{name} in {year}": "{name} n\u0103m {year}",
    "{n} towns": "{n} \u0111\u00f4 th\u1ecb",
    "Population on {date}": "D\u00e2n s\u1ed1 ng\u00e0y {date}",
}
VI_DAY = "30 th\u00e1ng 6, 2026"
VI_MONTH = "th\u00e1ng 10 n\u0103m 2026"


class IsoDatesTest(unittest.TestCase):
    def test_english_dates_become_iso(self):
        self.assertEqual(i18n.iso_dates("GUS population 30 June 2026; students 31 Dec 2025"),
                         "GUS population 2026-06-30; students 2025-12-31")
        self.assertEqual(i18n.iso_dates("GUS, October 2026, May 2026, and December 2025"),
                         "GUS, 2026-10, 2026-05, and 2025-12")
        self.assertEqual(i18n.iso_dates("June 30, 2026"), "2026-06-30")
        self.assertEqual(i18n.iso_dates("closed 31 Sept 2025"), "closed 31 Sept 2025")  # not a real date

    def test_other_text_is_left_alone(self):
        for s in ["Varso Tower", "Sejm 2023", "2015 to 2025", "Plac 3 Maja", "May I help", "2017-2021"]:
            self.assertEqual(i18n.iso_dates(s), s)

    def test_deep_skips_links_and_ids(self):
        doc = {"note": "as of 1 January 2026", "ref": "https://x/1 January 2026", "items": [{"vintage": "May 2026"}]}
        self.assertEqual(i18n.iso_dates_deep(doc),
                         {"note": "as of 2026-01-01", "ref": "https://x/1 January 2026", "items": [{"vintage": "2026-05"}]})


class FormatTest(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(i18n.fmt_date("2026-06-30", "en"), "30 June 2026")
        self.assertEqual(i18n.fmt_date("2026-06-30", "vi"), VI_DAY)
        self.assertEqual(i18n.fmt_date("2026-10", "vi"), VI_MONTH)
        self.assertEqual(i18n.fmt_date("2025", "vi"), "2025")

    def test_dates_inside_text(self):
        self.assertEqual(i18n.localize_dates("NSO, 2026-06-30 and 2026-10.", "vi"), f"NSO, {VI_DAY} and {VI_MONTH}.")
        for s in ["https://x.vn/2026-04/a", "regional/2026-01/x.xlsx", "2017-2021", "rounds 2015-2025", "?d=2026-10-01"]:
            self.assertEqual(i18n.localize_dates(s, "vi"), s)

    def test_numbers(self):
        self.assertEqual(i18n.fmt_num(1866929, 0, "en"), "1,866,929")
        self.assertEqual(i18n.fmt_num(1866929, 0, "vi"), "1.866.929")
        self.assertEqual(i18n.fmt_num(9178, 0, "vi"), "9.178")
        self.assertEqual(i18n.fmt_num(12.5, 1, "vi"), "12,5")
        self.assertEqual(i18n.fmt_pct(0.163, 1, "vi"), "16,3%")
        self.assertEqual(i18n.fmt_pct(0.163, 1, "en"), "16.3%")


class CatalogueTest(unittest.TestCase):
    def test_lookup_and_placeholders(self):
        self.assertEqual(i18n.t("Median age", "vi", CAT), CAT["Median age"])
        self.assertEqual(i18n.t("Median age", "en", CAT), "Median age")
        self.assertEqual(i18n.t("{name} in {year}", "vi", CAT, name="Hu\u1ebf", year="2025"), "Hu\u1ebf n\u0103m 2025")
        self.assertEqual(i18n.t("Not there", "vi", CAT), "Not there")  # falls back to English
        self.assertEqual(i18n.t("Population on {date}", "vi", CAT, date="2026-06-30"), f"D\u00e2n s\u1ed1 ng\u00e0y {VI_DAY}")
        self.assertEqual(i18n.t("{name} in {year}", "en", CAT, name="X", year=2024), "X in 2024")  # no "2,024"

    def test_vietnamese_plural_has_one_form(self):
        self.assertEqual({i18n.plural_category(n, "vi") for n in [0, 1, 2, 5, 1.5]}, {"other"})
        forms = {"one": "{n} town", "other": "{n} towns"}
        self.assertEqual([i18n.plural(n, forms, "vi", CAT) for n in (1, 5)], ["1 \u0111\u00f4 th\u1ecb", "5 \u0111\u00f4 th\u1ecb"])
        self.assertEqual([i18n.plural(n, forms, "en", CAT) for n in (1, 2)], ["1 town", "2 towns"])


class ExtractTest(unittest.TestCase):
    def make_site(self, cat):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "js" / "ui").mkdir(parents=True)
        (tmp / "data").mkdir()
        (tmp / "i18n").mkdir()
        (tmp / "js" / "ui" / "a.js").write_text(
            'const a = t("Open the map");\n'
            "const b = t('It\\'s here', {x: 1});\n"
            "// t(\"In a comment\")\n"
            "const c = t(`Plain template`);\n"
            "const d = t(`Has ${x}`);\n"
            'const e = t.plural(n, { one: "{n} town", other: "{n} towns" });\n'
            "const f = t(lens.name);\n"
            'const g = format("not a key");\n', encoding="utf-8")
        (tmp / "data" / "lenses.json").write_text(json.dumps(
            {"vintage": "NSO 2026-06-30", "groups": [{"name": "People"}],
             "lenses": [{"id": "age", "name": "Median age", "unit": "years", "description": None, "color": "#fff"}]}))
        (tmp / "index.html").write_text(
            '<html><head><title>Viet Nam</title><meta name="description" content="A map of Vietnam"></head>'
            '<body><button aria-label="Share this view"></button><p>Text version</p><script>var x="no";</script></body></html>')
        (tmp / "i18n" / "vi.json").write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
        return tmp

    def test_keys_from_js_data_and_html(self):
        web = self.make_site({})
        keys = i18n.all_keys(web)
        for k in ["Open the map", "It's here", "Plain template", "{n} towns", "People", "Median age", "years",
                  "NSO 2026-06-30", "A map of Vietnam", "Share this view", "Text version", "Viet Nam"]:
            self.assertIn(k, keys)
        for k in ["In a comment", "not a key", "#fff", "age", "no"]:
            self.assertNotIn(k, keys)
        self.assertTrue(keys["{n} towns"]["plural"])
        self.assertTrue(any(w.startswith("js/ui/a.js:1") for w in keys["Open the map"]["where"]))

    def test_missing_and_check(self):
        web = self.make_site({"Open the map": "M\u1edf b\u1ea3n \u0111\u1ed3", "{n} towns": ""})
        miss = i18n.missing(web, i18n.load_catalogue(web / "i18n" / "vi.json"))
        self.assertNotIn("Open the map", miss)
        self.assertIn("{n} towns", miss)  # an empty entry is missing
        self.assertIn("Median age", miss)
        lines = i18n_check.check(web / "data")
        self.assertEqual(lines[0][0], "FAIL")
        self.assertIn(f"{len(miss)} of", lines[0][1])

    def test_complete_catalogue_passes(self):
        web = self.make_site({})
        full = {k: "x " + k for k in i18n.all_keys(web)}
        (web / "i18n" / "vi.json").write_text(json.dumps(full), encoding="utf-8")
        i18n._CACHE.clear()
        self.assertEqual([lv for lv, _ in i18n_check.check(web / "data")], ["PASS"])

    def test_placeholder_problems(self):
        probs = i18n.placeholder_problems({"{a} and {b}": "{a} v\u00e0 {c}", "Bold": "<b>\u0110\u1eadm</b>", "Fine {n}": "T\u1ed1t {n}"})
        self.assertEqual(len(probs), 2)


JS = r"""
const m = await import(process.argv[1]);
const en = {
  t: m.t("Median age"), num: m.num(1866929), pct: m.pct(0.163), compact: m.compact(3.92e12), money: m.money(3.92e12),
  date: m.date("2026-06-30"), month: m.date("2026-10"), plural: [1, 2].map((n) => m.t.plural(n, {one: "{n} town", other: "{n} towns"})),
  href: m.langHref("vi", {pathname: "/vn-civ/", search: "", hash: "#city=uc1"}),
  bare: m.langHref("vi", {pathname: "/vn-civ", search: "", hash: ""}), year: m.t("{name} in {year}", {name: "X", year: 2024}),
};
m.setLocale("vi", JSON.parse(process.argv[2]));
const vi = {
  t: m.t("Median age"), vars: m.t("{name} in {year}", {name: "Hue", year: 2025}), missing: m.t("Not there"),
  num: m.num(1866929), dec: m.num(12.5, 1), pct: m.pct(0.163), mln: m.compact(18.6e6),
  plural: [1, 5].map((n) => m.t.plural(n, {one: "{n} town", other: "{n} towns"})),
  href: m.langHref("en", {pathname: "/vn-civ/vi/", search: "", hash: "#lens=hdi"}),
};
console.log(JSON.stringify({en, vi}));
"""


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class BrowserI18nTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = subprocess.run(["node", "--input-type=module", "-e", JS, I18N_JS.as_uri(), json.dumps(CAT)],
                             capture_output=True, text=True, timeout=30, check=True)
        cls.out = json.loads(run.stdout)

    def test_english(self):
        en = self.out["en"]
        self.assertEqual(en["t"], "Median age")
        self.assertEqual((en["num"], en["pct"], en["compact"], en["money"]), ("1,866,929", "16.3%", "3.92T", f"3.92T{NBSP}\u20ab"))
        self.assertEqual((en["date"], en["month"]), ("30 June 2026", "October 2026"))
        self.assertEqual(en["plural"], ["1 town", "2 towns"])
        self.assertEqual(en["href"], "/vn-civ/vi/#city=uc1")
        self.assertEqual((en["bare"], en["year"]), ("/vn-civ/vi/", "X in 2024"))

    def test_vietnamese(self):
        vi = self.out["vi"]
        self.assertEqual((vi["t"], vi["missing"]), (CAT["Median age"], "Not there"))
        self.assertEqual(vi["vars"], "Hue n\u0103m 2025")
        self.assertEqual((vi["num"], vi["dec"], vi["pct"]), ("1.866.929", "12,5", "16,3%"))
        self.assertEqual(vi["mln"], f"18,6{NBSP}tri\u1ec7u")
        self.assertEqual(vi["plural"], ["1 \u0111\u00f4 th\u1ecb", "5 \u0111\u00f4 th\u1ecb"])
        self.assertEqual(vi["href"], "/vn-civ/#lens=hdi")


class DatePatternTest(unittest.TestCase):
    """A source line whose dates move keeps one catalogue entry (pipeline/core/i18n.py date_pattern, lookup)."""

    CAT = {"GUS, {d1}, {d2}, and {d3}": "GUS, {d1}, {d2} i {d3}", "Change 2015-2025": "Zmiana 2015-2025",
           "Exact 2026-10": "Dokladnie 2026-10"}

    def test_pattern(self):
        self.assertEqual(i18n.date_pattern("GUS, 2026-10, 2026-05, and 2025-12"),
                         ("GUS, {d1}, {d2}, and {d3}", ["2026-10", "2026-05", "2025-12"]))
        self.assertEqual(i18n.date_pattern("Change 2015-2025")[1], [])  # a range stays literal
        self.assertEqual(i18n.date_pattern("Census 2021-03-31")[0], "Census {d1}")

    def test_lookup_by_pattern(self):
        self.assertEqual(i18n.lookup("GUS, 2026-11, 2026-05, and 2025-12", self.CAT), "GUS, 2026-11, 2026-05 i 2025-12")
        self.assertEqual(i18n.t("GUS, 2026-11, 2026-05, and 2025-12", "vi", self.CAT),
                         "GUS, th\u00e1ng 11 n\u0103m 2026, th\u00e1ng 5 n\u0103m 2026 i th\u00e1ng 12 n\u0103m 2025")

    def test_exact_entry_wins(self):
        self.assertEqual(i18n.lookup("Exact 2026-10", {**self.CAT, "Exact {d1}": "Wzor {d1}"}), "Dokladnie 2026-10")
        self.assertIsNone(i18n.lookup("Nothing 2026-10", self.CAT))


if __name__ == "__main__":
    unittest.main()
