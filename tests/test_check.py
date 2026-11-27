"""pipeline.check on a tiny synthetic v2 dataset (a 3x2 grid)."""

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from pipeline import check

YIELDS = {"gold": 3.5e12, "food": 1.2e6}
ECON = {"population": 1000, "yields": YIELDS, "jobs": {}, "unemployment": 0.02, "gdp": 3.5e12, "gdp_year": 2025,
        "growth": 0.031, "growth_years": [2020, 2025]}


def dataset():
    """Grid 3x2: cells 0, 1, 3, 4 are province 0 (former provinces 0/1), cell 2 is sea, cell 5 foreign land."""
    owner = [0, 0, -1, 0, 0, -2]
    world = {
        "version": 2, "grid": {"radius": 25.0, "cols": 3, "rows": 2}, "width": 120.0, "height": 60.0, "margin": 0,
        "owner": owner, "county": [0, 0, -1, 1, 1, -1], "elev": [10, 20, -50, 30, 40, 100],
        "water": [0, 0, 1, 0, 0, 0], "relief": [0, 1, 0, 0, 2, 1], "cover": [1, 7, 0, 9, 5, 0],
        "pct": {k: [50 if k == "forest" and o >= 0 else 0 for o in owner] for k in check.PCT_KEYS},
        "tables": {
            "water": [{"id": i, "name": n} for i, n in enumerate(["Land", "Ocean", "Coast", "Lake"])],
            "relief": [{"id": i, "name": n} for i, n in enumerate(["Flat", "Hills", "Mountains", "Peaks"])],
            "cover": [{"id": 0, "key": "none", "name": "None"}]
            + [{"id": i, "key": k, "name": k, "color": "#123456"} for i, k in enumerate(check.COVER_KEYS) if i],
        },
        "states": [{"fips": "01", "abbr": "HN", "name": "Ha Noi"}, {"fips": "04", "abbr": "CB", "name": "Cao Bang"}],
        "counties": [{"geoid": "01", "name": "Ha Noi"}, {"geoid": "04", "name": "Cao Bang"}],
        "rivers": [{"name": "Big", "rank": 1, "pts": [1.0, 1.0, 50.0, 30.0]}],
    }
    cities = [
        {"id": "uc1", "name": "Big", "full": "Big, Ha Noi", "states": ["HN"], "x": 1.0, "y": 1.0, "cell": 0,
         "population": 1000, "capital": True, "centre": True},
        {"id": "centre04", "name": "Small", "full": "Small, Ha Noi", "states": ["HN"], "x": 40.0, "y": 40.0, "cell": 4,
         "population": None, "capital": False, "centre": True},
    ]
    land = {k: (0.5 if k == "forest" else 0.0) for k in check.PCT_KEYS}
    states = [{"fips": "01", "abbr": "HN", "name": "Ha Noi", **ECON, "label": {"x": 10, "y": 10, "angle": 0, "size": 12},
               "land": land},
              {"fips": "04", "abbr": "CB", "name": "Cao Bang", **ECON, "yields": {"gold": 1e12, "food": None},
               "label": None, "land": None}]
    nation = {"vintage": "NSO 2025", "year": 2025, "gdp_vintage": None, "nation": {**ECON, "population": 2000, "gdp": 7e12}, "industries": {},
              "yields": [{"key": "gold", "label": "Gold", "color": "#e8c34a", "unit": "vnd"},
                         {"key": "food", "label": "Rice", "color": "#7fbf3f", "unit": "t"}]}
    lenses = {"vintage": "NSO 2025", "groups": [{"id": "people", "name": "People"}],
              "lenses": [{"id": "density", "group": "people", "name": "Population", "icon": "l-people", "emoji": "*",
                          "unit": "people / km2", "format": "float", "scale": "log", "domain": [1, 2000],
                          "ramp": ["#000000", "#ffffff"], "higher_is": "neutral", "source": "src", "description": "d",
                          "values": [5, 5, None, 0, 7, None]}]}
    sources = [{"id": "src", "title": "NSO", "publisher": "NSO", "homepage": "h", "license": "pd", "description": "d",
                "used_for": ["lenses"], "vintage": "2025", "files": [{"file": "a", "url": "u", "retrieved": "t", "sha256": "s", "bytes": 1}]}]
    resources = {"types": [{"id": "hydro", "name": "Hydro", "category": "energy", "emoji": "*", "icon": "r-hydro", "color": "#2f7fc1",
                            "unit": "MW", "description": "30 MW or more", "source": "src"}],
                 "items": [{"type": "hydro", "name": "P", "x": 5.0, "y": 5.0, "cell": 0, "value": 100, "detail": "",
                            "state": "HN", "cbsa": None}],
                 "summary": {"note": "mapped sites only", "national": {"hydro": {"count": 1, "value": 100, "unit": "MW"}},
                             "states": {"HN": {"hydro": {"count": 1, "value": 100, "unit": "MW"}}}}}
    county_fields = [{"key": "migration_2019", "label": "m", "format": "float", "unit": None, "higher_is": "neutral",
                      "source": "src", "description": "d"}]
    counties = {"vintage": "Census 2019", "fields": county_fields,
                "columns": ["geoid", "name", "type", "province", "state", "migration_2019"],
                "rows": [["01", "Ha Noi", "former", "01", "HN", 12.5], ["04", "Cao Bang", "former", "01", "HN", None]]}
    interim = {"_world": {"data": {"counties": ["01", "04"], "county_samples": [[0] * 7, [0] * 7, [], [1] * 7, [1] * 7, []]}}}
    return {"world.json": world, "cities.json": cities, "states.json": states, "nation.json": nation,
            "lenses.json": lenses, "sources.json": sources, "resources.json": resources, "counties.json": counties}, interim


class CheckTest(unittest.TestCase):
    def run_check(self, web, interim):
        with tempfile.TemporaryDirectory() as tmp:
            wd, idir = Path(tmp) / "web", Path(tmp) / "interim"
            wd.mkdir()
            idir.mkdir()
            for name, doc in web.items():
                if doc is not None:
                    (wd / name).write_text(json.dumps(doc))
            for name, doc in interim.items():
                (idir / f"{name}.json").write_text(json.dumps(doc))
            return check.run(wd, idir, quiet=True)

    def levels(self, rep, level):
        return [m for lv, m in rep.lines if lv == level]

    def test_clean_dataset_passes(self):
        web, interim = dataset()
        rep = self.run_check(web, interim)
        self.assertEqual(self.levels(rep, "FAIL"), [])

    def test_national_figures_equal_the_province_sums(self):
        for key in ("population", "gdp"):
            web, interim = dataset()
            web["nation.json"]["nation"][key] *= 1.01
            fails = self.levels(self.run_check(web, interim), "FAIL")
            self.assertTrue(any(f"national {key}" in m for m in fails), key)

    def test_missing_optional_is_a_note(self):
        web, interim = dataset()
        web["resources.json"] = None
        rep = self.run_check(web, interim)
        self.assertEqual(self.levels(rep, "FAIL"), [])
        self.assertTrue(any("resources.json" in m for m in self.levels(rep, "NOTE")))

    def test_missing_required_fails(self):
        web, interim = dataset()
        web["cities.json"] = None
        self.assertTrue(any("cities.json" in m for m in self.levels(self.run_check(web, interim), "FAIL")))

    def test_v1_world_fails(self):
        web, interim = dataset()
        web["world.json"]["version"] = 1
        self.assertTrue(self.levels(self.run_check(web, interim), "FAIL"))

    def test_contract_violations(self):
        cases = {
            "lens value off land": lambda w: w["lenses.json"]["lenses"][0]["values"].__setitem__(2, 3),
            "zero population": lambda w: w["states.json"][0].__setitem__("population", 0),
            "town on the sea": lambda w: w["cities.json"][0].__setitem__("cell", 2),
            "unknown yield unit": lambda w: w["nation.json"]["yields"][0].__setitem__("unit", "pln"),
            "county row width": lambda w: w["counties.json"]["rows"][0].pop(),
            "states order": lambda w: w["states.json"].reverse(),
        }
        for what, change in cases.items():
            web, interim = dataset()
            change(web)
            with self.subTest(what=what):
                self.assertTrue(self.levels(self.run_check(web, interim), "FAIL"), what)

    def test_lens_values_for_land_cells_only(self):
        web, interim = dataset()
        lens = web["lenses.json"]["lenses"][0]
        web["lenses.json"]["cells"] = [0, 1, 3, 4]
        lens["values"] = [5, 5, 0, 7]
        rep = self.run_check(web, interim)
        self.assertEqual(self.levels(rep, "FAIL"), [])

    def test_real_zero_is_not_null(self):
        web, interim = dataset()
        rep = self.run_check(web, interim)
        # Cell 3 holds a real zero: it counts as a value, not as a gap.
        self.assertFalse(any("density" in m and "null" in m for m in self.levels(rep, "WARN")))


if __name__ == "__main__":
    unittest.main()
