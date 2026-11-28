"""The energy module: source parsers, the plant merge, the national series and the lenses (no network)."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from pipeline.build import energy
from pipeline.sources import energy_common as ec
from pipeline.sources import energy_ember, energy_gem, energy_osm
from pipeline.sources.energy_config import ENERGY_COUNTRY


class Words(unittest.TestCase):
    def test_tech_of(self):
        self.assertEqual(ec.tech_of("Hydro"), "hydro")
        self.assertEqual(ec.tech_of(None, "solar;battery"), "solar")
        self.assertEqual(ec.tech_of("bioenergy"), "biomass")
        self.assertEqual(ec.tech_of("oil/gas"), "gas")
        self.assertIsNone(ec.tech_of("", "unknown"))
        self.assertTrue(set(ec._TECH_WORDS.values()) <= set(ec.TECHS))

    def test_parse_mw(self):
        self.assertEqual(ec.parse_mw("1200 MW"), 1200)
        self.assertEqual(ec.parse_mw("1,2 GW"), 1200)
        self.assertEqual(ec.parse_mw("50"), 50)
        self.assertAlmostEqual(ec.parse_mw("500 kWp"), 0.5)
        self.assertIsNone(ec.parse_mw("yes"))
        self.assertIsNone(ec.parse_mw("0"))

    def test_year_of(self):
        self.assertEqual(ec.year_of("2019-06-30"), 2019)
        self.assertEqual(ec.year_of("2004.0"), 2004)
        self.assertEqual(ec.year_of(None, "about 1994"), 1994)
        self.assertIsNone(ec.year_of("12345"))

    def test_bands_cover_bbox(self):
        b = ec.bands()
        s, w, n, e = ENERGY_COUNTRY["bbox"]
        self.assertEqual(b[0][0], s)
        self.assertEqual(b[-1][2], n)
        self.assertTrue(all(x[1] == w and x[3] == e for x in b))


EMBER = """Area,ISO 3 code,Year,Area type,Electricity source,Is aggregated source,Generation (TWh),Share of generation (%),Capacity (GW)
{name},{iso},2019,Country or economy,Solar,False,5.0,2.0,5.0
{name},{iso},2019,Country or economy,Coal,False,120.0,50.0,18.8
{name},{iso},2019,Country or economy,Fossil,True,130.0,54.0,26.0
{name},{iso},2019,Country or economy,Total generation,True,240.0,100.0,55.0
{name},{iso},2020,Country or economy,Solar,False,10.9,4.3,16.7
Other,XXX,2020,Country or economy,Solar,False,1.0,1.0,1.0
"""


class Ember(unittest.TestCase):
    def test_yearly_series_of_the_country(self):
        text = EMBER.format(name=ENERGY_COUNTRY["ember_name"], iso=ENERGY_COUNTRY["iso3"])
        s = energy_ember.series(energy_ember.country_rows(text), "Year")
        self.assertEqual(s["periods"], [2019, 2020])
        self.assertEqual(s["capacity_gw"]["solar"], [5.0, 16.7])
        self.assertEqual(s["gen_twh"]["coal"], [120.0, None])  # missing stays null
        self.assertEqual(s["gen_twh"]["total"], [240.0, None])
        self.assertIsNone(s["share_pct"]["gas"][0])  # aggregated "Fossil" is not counted as a technology

    def test_recent_mix(self):
        months = [f"2025-{m:02d}" for m in range(1, 13)] + ["2026-01"]
        gen = {t: [None] * 13 for t in [*ec.TECHS, "total", "net_imports", "demand"]}
        gen["solar"] = [1.0] * 13
        gen["coal"] = [3.0] * 13
        gen["total"] = [4.0] * 13
        r = energy.recent_mix({"periods": months, "gen_twh": gen})
        self.assertEqual((r["from"], r["to"]), ("2025-02", "2026-01"))
        self.assertEqual(r["total_twh"], 48.0)
        self.assertEqual(r["share_pct"]["solar"], 25.0)
        self.assertIsNone(r["share_pct"]["wind"])
        self.assertIsNone(energy.recent_mix({"periods": months[:5], "gen_twh": gen}))


class Plants(unittest.TestCase):
    def test_osm_plant_point(self):
        el = {"type": "way", "id": 7, "center": {"lat": 11.5, "lon": 108.9},
              "tags": {"plant:source": "solar", "plant:output:electricity": "450 MW", "start_date": "2019-04"}}
        p = energy_osm.plant_point(el)
        self.assertEqual((p["tech"], p["mw"], p["start"], p["status"]), ("solar", 450, 2019, "operating"))
        el["tags"]["end_date"] = "2023"
        self.assertEqual(energy_osm.plant_point(el)["status"], "retired")
        self.assertIsNone(energy_osm.plant_point({"type": "node", "id": 1, "lat": 1, "lon": 1, "tags": {}}))

    def test_merge_fills_and_dedupes(self):
        a = {"id": "osm:1", "tech": "hydro", "mw": 1920.0, "start": None, "status": "operating", "lat": 20.81, "lon": 105.32}
        b = {"id": "wri:1", "tech": "hydro", "mw": 1900.0, "start": 1994, "status": "operating", "lat": 20.82, "lon": 105.33}
        c = {"id": "wri:2", "tech": "coal", "mw": 600.0, "start": 2015, "status": "operating", "lat": 20.82, "lon": 105.33}
        far = {"id": "wri:3", "tech": "hydro", "mw": 50.0, "start": 2001, "status": "operating", "lat": 21.5, "lon": 104.0}
        out = energy.merge([("energy_osm", [a]), ("energy_wri", [b, c, far])])
        self.assertEqual(len(out), 3)
        hydro = next(p for p in out if p["id"] == "osm:1")
        self.assertEqual((hydro["mw"], hydro["start"], hydro["fill"]), (1920.0, 1994, {"start": "energy_wri"}))
        self.assertEqual({p["src"] for p in out}, {"energy_osm", "energy_wri"})

    def test_merge_same_source_twins(self):
        dam = {"id": "osm:1", "tech": "hydro", "mw": 2400.0, "start": 2012, "status": "operating", "lat": 21.43, "lon": 103.98}
        plant = {"id": "osm:2", "tech": "hydro", "mw": 2400.0, "start": None, "status": "operating", "lat": 21.44, "lon": 103.99}
        small = {"id": "osm:3", "tech": "hydro", "mw": 30.0, "start": None, "status": "operating", "lat": 21.44, "lon": 103.99}
        out = energy.merge([("energy_osm", [dam, plant, small])])
        self.assertEqual([p["id"] for p in out], ["osm:1", "osm:3"])

    # Real records (OSM 2026-11-27, WRI v1.3): neighbours with distinct names stay apart; one plant in two sources
    # or mapped twice in one source joins.
    VT1 = {"id": "osm:way/1317922272", "tech": "coal", "name": "Nh\u00e0 m\u00e1y Nhi\u1ec7t \u0111i\u1ec7n V\u0129nh T\u00e2n 1", "mw": 1200.0, "start": None, "status": "operating", "lat": 11.31638, "lon": 108.80744}
    VT2 = {"id": "osm:way/1317922271", "tech": "coal", "name": "Nh\u00e0 m\u00e1y Nhi\u1ec7t \u0111i\u1ec7n V\u0129nh T\u00e2n 2", "mw": 1244.0, "start": None, "status": "operating", "lat": 11.31433, "lon": 108.80368}
    DH1 = {"id": "osm:way/827889601", "tech": "coal", "name": "Nh\u00e0 m\u00e1y Nhi\u1ec7t \u0111i\u1ec7n Duy\u00ean H\u1ea3i 1", "mw": 1245.0, "start": None, "status": "operating", "lat": 9.58184, "lon": 106.52492}
    DH2 = {"id": "osm:way/968243276", "tech": "coal", "name": "Nh\u00e0 m\u00e1y Nhi\u1ec7t \u0111i\u1ec7n Duy\u00ean H\u1ea3i 2", "mw": 1200.0, "start": None, "status": "operating", "lat": 9.58923, "lon": 106.53232}
    IALY = {"id": "osm:way/1385239540", "tech": "hydro", "name": "Nh\u00e0 m\u00e1y Th\u1ee7y \u0111i\u1ec7n Ialy", "mw": 720.0, "start": None, "status": "operating", "lat": 14.22212, "lon": 107.79563}
    W_IALY = {"id": "wri:WRI1030835", "tech": "hydro", "name": "Ialy", "mw": 720.0, "start": 2002, "status": "operating", "lat": 14.2274, "lon": 107.8294}
    W_RYNINH = {"id": "wri:WRI1030833", "tech": "hydro", "name": "Ry Ninh", "mw": 3.6, "start": None, "status": "operating", "lat": 14.209, "lon": 107.8141}
    W_VT2 = {"id": "wri:WRI1030751", "tech": "coal", "name": "Vinh Tan 2", "mw": 1244.0, "start": None, "status": "operating", "lat": 11.317, "lon": 108.81}
    W_DH3 = {"id": "wri:WRI1030732", "tech": "coal", "name": "Duyen Hai 3", "mw": 622.0, "start": None, "status": "operating", "lat": 9.5867, "lon": 106.53}

    def test_merge_keeps_named_neighbours_apart(self):
        out = energy.merge([("energy_osm", [self.VT1, self.VT2, self.DH1, self.DH2])])
        self.assertEqual(len(out), 4)
        self.assertEqual(sum(p["mw"] for p in out), 1200 + 1244 + 1245 + 1200)

    def test_merge_matches_across_sources_by_name(self):
        out = energy.merge([("energy_osm", [self.VT1, self.VT2, self.IALY, self.DH1]),
                            ("energy_wri", [self.W_IALY, self.W_RYNINH, self.W_VT2, self.W_DH3])])
        ids = {p["id"] for p in out}
        self.assertEqual(ids, {self.VT1["id"], self.VT2["id"], self.IALY["id"], self.DH1["id"], self.W_RYNINH["id"],
                               self.W_DH3["id"]})
        ialy = next(p for p in out if p["id"] == self.IALY["id"])
        self.assertEqual((ialy["start"], ialy["fill"]), (2002, {"start": "energy_wri"}))

    def test_name_key(self):
        self.assertEqual(energy.name_key("Nh\u00e0 m\u00e1y Nhi\u1ec7t \u0111i\u1ec7n Qu\u1ea3ng Tr\u1ea1ch I"),
                         ("quangtrach", frozenset({"1"})))
        self.assertTrue(energy.same_name({"name": "SrePok 3"}, {"name": "Th\u1ee7y \u0111i\u1ec7n Sr\u00ea P\u1ed1k 3"}))
        self.assertFalse(energy.same_name({"name": "SrePok 4"}, {"name": "Sre Pok 4A"}))
        self.assertFalse(energy.same_name({"name": "Ph\u1ea3 L\u1ea1i"}, {"name": "Pha Lai 1"}))  # numbers differ
        self.assertTrue(energy.same_name({"name": "Ph\u1ea3 L\u1ea1i 1"}, {"name": "Pha Lai I"}))
        self.assertFalse(energy.same_name({"name": "Nh\u1ea1n H\u1ea1c A"}, {"name": "Nh\u1ea1n H\u1ea1c B"}))
        self.assertFalse(energy.same_name({"name": "Cam An Bac VN"}, {"name": "Cam An Bac KN"}))
        self.assertFalse(energy.same_name({"name": "V\u0129nh T\u00e2n 4"}, {"name": "V\u0129nh T\u00e2n 4 m\u1edf r\u1ed9ng"}))
        self.assertIsNone(energy.same_name({"name": None}, {"name": "Ialy"}))
        self.assertIsNone(energy.same_name({"name": "  "}, {"name": "Ialy"}))
        # A name of generic words only is still a name: it keys on those words.
        self.assertEqual(energy.name_key("Solar Power Plant"), ("solarpowerplant", frozenset()))
        self.assertTrue(energy.same_name({"name": "Suoi Vang (AnKroet)"}, {"name": "Nh\u00e0 m\u00e1y th\u1ee7y \u0111i\u1ec7n Ankroet"}))

    def test_name_key_other_scripts(self):
        # Polish: l-with-stroke folds to l, "Elektrownia" and "Farma wiatrowa" are generic.
        self.assertEqual(energy.name_key("Elektrownia Be\u0142chat\u00f3w"), ("belchatow", frozenset()))
        self.assertEqual(energy.name_key("Farma Wiatrowa Pot\u0119gowo 2"),
                         ("potegowo", frozenset({"2"})))
        self.assertTrue(energy.same_name({"name": "Elektrownia Be\u0142chat\u00f3w"}, {"name": "Belchatow Power Station"}))
        # Thai: letters and vowel marks are kept; "power plant" is cut out of the word.
        mae_moh = "\u0e42\u0e23\u0e07\u0e44\u0e1f\u0e1f\u0e49\u0e32\u0e41\u0e21\u0e48\u0e40\u0e21\u0e32\u0e30"
        self.assertEqual(energy.name_key(mae_moh), ("\u0e41\u0e21\u0e48\u0e40\u0e21\u0e32\u0e30", frozenset()))
        self.assertTrue(energy.same_name({"name": mae_moh}, {"name": "\u0e41\u0e21\u0e48\u0e40\u0e21\u0e32\u0e30"}))
        self.assertFalse(energy.same_name({"name": mae_moh}, {"name": "\u0e42\u0e23\u0e07\u0e44\u0e1f\u0e1f\u0e49\u0e32\u0e1a\u0e32\u0e07\u0e1b\u0e30\u0e01\u0e07"}))
        # Bangla: vowel signs are kept, "power plant" is generic, Bangla digits are numbers.
        payra = "\u09aa\u09be\u09af\u09bc\u09b0\u09be \u09ac\u09bf\u09a6\u09cd\u09af\u09c1\u09ce\u0995\u09c7\u09a8\u09cd\u09a6\u09cd\u09b0 \u09e8"
        self.assertEqual(energy.name_key(payra), ("\u09aa\u09be\u09af\u09bc\u09b0\u09be", frozenset({"2"})))
        self.assertFalse(energy.same_name({"name": payra}, {"name": payra[:-2]}))
        # Arabic: "station" and "for electricity" are generic.
        qurayyah = "\u0645\u062d\u0637\u0629 \u0627\u0644\u0642\u0631\u064a\u0629 \u0644\u0644\u0643\u0647\u0631\u0628\u0627\u0621"
        self.assertEqual(energy.name_key(qurayyah), ("\u0627\u0644\u0642\u0631\u064a\u0629", frozenset()))
        self.assertTrue(energy.same_name({"name": qurayyah}, {"name": "\u0627\u0644\u0642\u0631\u064a\u0629"}))
        # A non-Latin name is a name: a nameless neighbour of another source within 4 km still joins, a named one not.
        a = {"id": "osm:1", "tech": "gas", "name": qurayyah, "mw": 3900.0, "start": None, "status": "operating", "lat": 25.84, "lon": 50.12}
        b = {"id": "wri:1", "tech": "gas", "name": "Rabigh", "mw": 3900.0, "start": 2011, "status": "operating", "lat": 25.85, "lon": 50.12}
        self.assertEqual(len(energy.merge([("energy_osm", [a]), ("energy_wri", [b])])), 2)

    # Real records (OSM 2026-11-27, WRI v1.3).
    O_VS = {"id": "osm:way/320351744", "tech": "hydro", "name": "Nh\xe0 m\xe1y th\u1ee7y \u0111i\u1ec7n V\u0129nh S\u01a1n", "mw": 66.0, "start": None, "status": "operating", "lat": 14.37085, "lon": 108.71521}
    O_VS5 = {"id": "osm:way/827889634", "tech": "hydro", "name": "Nh\xe0 m\xe1y th\u1ee7y \u0111i\u1ec7n V\u0129nh S\u01a1n 5", "mw": 28.0, "start": None, "status": "operating", "lat": 14.31864, "lon": 108.75364}
    W_VS = {"id": "wri:WRI1030837", "tech": "hydro", "name": "Vinh Son", "mw": 66.0, "start": 2001, "status": "operating", "lat": 14.3656, "lon": 108.6943}
    W_VS5 = {"id": "wri:WRI1030836", "tech": "hydro", "name": "Vinh Son 5", "mw": 28.0, "start": 2014, "status": "operating", "lat": 14.3611, "lon": 108.7203}
    O_SP3 = {"id": "osm:way/827889683", "tech": "hydro", "name": "Th\u1ee7y \u0111i\u1ec7n S\xear\xeap\xf4k 3", "mw": 220.0, "start": None, "status": "operating", "lat": 12.76674, "lon": 107.85916}
    O_SP4 = {"id": "osm:way/827889687", "tech": "hydro", "name": "Th\u1ee7y \u0111i\u1ec7n S\xear\xeap\xf4k 4", "mw": 80.0, "start": None, "status": "operating", "lat": 12.80825, "lon": 107.85576}
    O_SP4A = {"id": "osm:way/827889639", "tech": "hydro", "name": "Th\u1ee7y \u0111i\u1ec7n S\xear\xeap\xf4k 4A", "mw": 64.0, "start": None, "status": "operating", "lat": 12.89357, "lon": 107.81202}
    W_SP3 = {"id": "wri:WRI1030814", "tech": "hydro", "name": "SrePok 3", "mw": 220.0, "start": 2009, "status": "operating", "lat": 12.7524, "lon": 107.8768}
    W_SP4 = {"id": "wri:WRI1030816", "tech": "hydro", "name": "SrePok 4", "mw": 80.0, "start": 2010, "status": "operating", "lat": 12.8072, "lon": 107.8551}
    W_SP4A = {"id": "wri:WRI1030817", "tech": "hydro", "name": "Sre Pok 4a", "mw": 64.0, "start": 2014, "status": "operating", "lat": 12.8935, "lon": 107.8123}

    def test_merge_vinh_son_and_vinh_son_5_stay_apart(self):
        out = energy.merge([("energy_osm", [self.O_VS, self.O_VS5]), ("energy_wri", [self.W_VS, self.W_VS5])])
        self.assertEqual(sorted((p["name"][-1], p["mw"], p["start"]) for p in out), [("5", 28.0, 2014), ("n", 66.0, 2001)])

    def test_merge_srepok_spelling_variants(self):
        log = []
        out = energy.merge([("energy_osm", [self.O_SP3, self.O_SP4, self.O_SP4A]),
                            ("energy_wri", [self.W_SP3, self.W_SP4, self.W_SP4A])], log)
        self.assertEqual(sorted((p["mw"], p["start"]) for p in out), [(64.0, 2014), (80.0, 2010), (220.0, 2009)])
        self.assertTrue(all(0.85 <= m[4] < 1 for m in log))
        # One source spells one plant one way: the same names in one source as variants stay apart.
        twin = {**self.O_SP3, "id": "osm:2", "name": "Srepok 3"}
        self.assertEqual(len(energy.merge([("energy_osm", [self.O_SP3, twin])])), 2)

    def test_nearest_land_is_nearest_not_lowest(self):
        from pipeline.core.hexgrid import HexGrid
        grid = HexGrid(radius=5.0, cols=10, rows=10)
        owner = [-1] * grid.size
        sea = grid.index(5, 5)
        x, y = grid.center(5, 5)
        left, right = grid.index(4, 5), grid.index(6, 5)
        owner[left] = 0
        owner[right] = 1
        self.assertLess(left, right)
        self.assertEqual(energy.nearest_land(grid, owner, x + 3.0, y), right)  # nearer the right-hand hex
        self.assertEqual(energy.nearest_land(grid, owner, x - 3.0, y), left)
        island = grid.index(0, 0)
        owner2 = [-1] * grid.size
        owner2[grid.index(9, 9)] = 0
        self.assertEqual(energy.nearest_land(grid, owner2, *grid.center(0, 0)), grid.index(9, 9))  # beyond 2 rings
        self.assertEqual(energy.nearest_land(grid, owner2, *grid.center(0, 0), rings=2), -1)
        self.assertEqual(island, 0)

    def test_gem_units_become_plants(self):
        units = [{"loc": "L1", "unit": "U1", "tech": "coal", "name": "Vinh Tan 4", "mw": 600.0, "start": 2017, "end": None,
                  "status": "operating", "lon": 108.8, "lat": 11.3},
                 {"loc": "L1", "unit": "U2", "tech": "coal", "name": "Vinh Tan 4", "mw": 600.0, "start": 2018, "end": None,
                  "status": "operating", "lon": 108.8, "lat": 11.3},
                 {"loc": "L2", "unit": "U3", "tech": "coal", "name": "Old", "mw": 100.0, "start": 1974, "end": 2015,
                  "status": "retired", "lon": 106.7, "lat": 21.0}]
        out = {p["id"]: p for p in energy_gem.plants(units)}
        self.assertEqual((out["gem:L1"]["mw"], out["gem:L1"]["start"], out["gem:L1"]["units"]), (1200.0, 2017, 2))
        self.assertEqual((out["gem:L2"]["status"], out["gem:L2"]["end"]), ("retired", 2015))

    def test_gem_rows(self):
        head = ["Type", "Country/area", "Plant / Project name", "Unit / Phase name", "Capacity (MW)", "Status",
                "Start year", "Retired year", "Latitude", "Longitude", "GEM unit/phase ID", "Other IDs (unit/phase)",
                "Fuel (combustion only)"]
        name = ENERGY_COUNTRY["gem_names"][0]
        rows = [["utility-scale solar", name, "Trung Nam", "", 450.0, "operating", 2020.0, None, 11.6, 108.9, "G1",
                 "TZ: 1315667", None],
                ["coal", name, "Old", "1", 100.0, "retired", 1974.0, 2015.0, 21.0, 106.7, "G2", None, None],
                ["wind", name, "Plan", "", 300.0, "announced", None, None, 9.0, 105.0, "G3", None, None],
                ["wind", name, "Gone", "", 30.0, "cancelled - inferred 4 y", None, None, 9.1, 105.0, "G5", None, None],
                ["oil/gas", name, "O Mon", "1-1", 330.0, "operating", 2009.0, None, 10.1, 105.6, "G6", None,
                 "fossil liquids: fuel oil"],
                ["utility-scale solar", "Elsewhere", "X", "", 5.0, "operating", 2020.0, None, 1.0, 1.0, "G4", None, None]]
        pts = energy_gem.gem_points(head, rows)
        self.assertEqual([(p["id"], p["status"], p["tech"]) for p in pts],
                         [("gem:G1", "operating", "solar"), ("gem:G2", "retired", "coal"), ("gem:G3", "planned", "wind"),
                          ("gem:G6", "operating", "oil")])
        self.assertEqual((pts[1]["status"], pts[1]["start"], pts[1]["end"]), ("retired", 1974, 2015))
        self.assertEqual([p["tz"] for p in pts], [True, False, False, False])

    def test_gem_phases(self):
        self.assertEqual([energy_gem.phase(n) for n in ("Phase 2 Unit 1", "Phase II", "Unit 3-1", "Unit 3 Extension",
                                                         "4", "1-2, timepoint 1", "Unit 2", "--", None)],
                         ["2", "2", "3", "3", "4", "1", None, None, None])
        units = [{"loc": "L1", "unit": f"G{k}", "tech": "coal", "name": "Vinh Tan power station", "unit_name": u,
                  "mw": mw, "start": y, "end": None, "status": st, "lon": 108.808, "lat": 11.317}
                 for k, (u, mw, y, st) in enumerate([("Phase 1 Unit 1", 600, 2018, "operating"),
                                                     ("Phase 2 Unit 1", 622, 2014, "operating"),
                                                     ("Phase 3 Unit 1", 660, 2025, "planned"),
                                                     ("Phase 4 Unit 1", 600, 2017, "operating")])]
        (vt,) = energy_gem.plants(units)
        self.assertEqual((vt["mw"], vt["start"], vt["status"], vt["parts"]), (1822, 2014, "operating", ["1", "2", "3", "4"]))
        # Numbered records of other sources are phases of the GEM plant; a planned GEM plant takes and hides its namesakes.
        o_vt2 = {**self.VT2, "tech": "coal"}
        plan = {"id": "gem:L2", "tech": "coal", "name": "Long Phu Power Centre", "parts": ["1", "2"], "mw": 1200.0,
                "start": 2027, "status": "planned", "lat": 9.7089, "lon": 106.081}
        o_lp = {"id": "osm:9", "tech": "coal", "name": "Long Ph\u00fa 1 Power Plant", "mw": 1200.0, "start": None,
                "status": "operating", "lat": 9.71003, "lon": 106.08502}
        o_free = {"id": "osm:10", "tech": "coal", "name": None, "mw": 50.0, "start": None, "status": "operating",
                  "lat": 9.71, "lon": 106.09}
        log = []
        out = energy.merge([("energy_gem", [vt, plan]), ("energy_osm", [o_vt2, o_lp, o_free])], log)
        self.assertEqual([p["id"] for p in out], ["gem:L1", "osm:10"])
        self.assertEqual([m[6] for m in log], ["phase", "phase"])

    def test_merge_parts_and_far(self):
        gem = [{"id": f"gem:{n}", "tech": "gas", "name": f"Phu My {n} Thermal power station", "mw": mw, "start": 2000,
                "status": "operating", "lat": 10.60, "lon": 107.04} for n, mw in (("1", 1118.0), ("2.1", 946.0),
                                                                                   ("2.2", 733.0), ("3", 733.0), ("4", 477.0))]
        osm = {"id": "osm:1", "tech": "gas", "name": "Nh\u00e0 m\u00e1y Nhi\u1ec7t \u0111i\u1ec7n Ph\u00fa M\u1ef9",
               "mw": 3975.0, "start": None, "status": "operating", "lat": 10.60222, "lon": 107.03549}
        wri = {"id": "wri:1", "tech": "gas", "name": "Phu My 21", "mw": 896.0, "start": None, "status": "operating",
               "lat": 10.6041, "lon": 107.04}
        mao = {"id": "gem:M", "tech": "coal", "name": "Mao Khe power station", "mw": 440.0, "start": 2013,
               "status": "operating", "lat": 21.09069, "lon": 106.57731}
        w_mao = {"id": "wri:2", "tech": "coal", "name": "Mao Khe", "mw": 440.0, "start": None, "status": "operating",
                 "lat": 21.0907, "lon": 105.77}
        log = []
        out = energy.merge([("energy_gem", [*gem, mao]), ("energy_osm", [osm]), ("energy_wri", [wri, w_mao])], log)
        self.assertEqual(len(out), 6)
        self.assertEqual(sorted({m[6] for m in log}), ["far", "name", "parts"])

    def test_gem_aliases_join_other_names(self):
        # GEM "Plant / Project name (other)": OSM "Formosa Dong Nai" is GEM "Nhon Trach Formosa power station".
        gem = {"id": "gem:L1", "tech": "coal", "name": "Nhon Trach Formosa power station", "aliases": ["Formosa Dong Nai"],
               "mw": 450.0, "start": 2002, "status": "operating", "lat": 10.73264, "lon": 106.9354}
        osm = {"id": "osm:1", "tech": "coal", "name": "Nh\u00e0 m\u00e1y Nhi\u1ec7t \u0111i\u1ec7n Formosa \u0110\u1ed3ng Nai",
               "mw": 450.0, "start": None, "status": "operating", "lat": 10.73271, "lon": 106.93437}
        self.assertEqual([p["id"] for p in energy.merge([("energy_gem", [gem]), ("energy_osm", [osm])])], ["gem:L1"])
        # GEM lists a few plants twice (same name through an alias, same capacity): one plant.
        tn1 = {"id": "gem:A", "tech": "wind", "name": "Trung Nam wind farm", "aliases": ["Trung Nam Iii (Phase 3)"],
               "mw": 152.0, "start": 2019, "status": "operating", "lat": 11.683, "lon": 109.030}
        tn2 = {"id": "gem:B", "tech": "wind", "name": "Thu\u1eadn B\u1eafc Trungnam wind farm", "aliases": ["Trungnam wind farm"],
               "mw": 152.0, "start": 2019, "status": "operating", "lat": 11.715, "lon": 109.059}
        other = {**tn2, "id": "gem:C", "mw": 50.0}
        self.assertEqual(len(energy.merge([("energy_gem", [tn1, tn2])])), 1)
        self.assertEqual(len(energy.merge([("energy_gem", [tn1, other])])), 2)
        # An owner in common at the same capacity joins two names (OSM operator, GEM owner).
        g = {"id": "gem:S", "tech": "wind", "name": "C\u00f4ng L\u00fd S\u00f3c Tr\u0103ng wind farm", "aliases": [],
             "owner": "Super Energy Corporation PCL [51%]; Cong Ly Construction", "mw": 30.0, "start": 2021,
             "status": "operating", "lat": 9.2367, "lon": 105.911}
        o = {"id": "osm:S", "tech": "wind", "name": "Nh\u00e0 m\u00e1y \u0111i\u1ec7n gi\u00f3 S\u00f3c Tr\u0103ng",
             "owner": "Super Energy Corp", "mw": 30.0, "start": None, "status": "operating", "lat": 9.28, "lon": 105.95}
        self.assertEqual(len(energy.merge([("energy_gem", [g]), ("energy_osm", [o])])), 1)
        self.assertEqual(len(energy.merge([("energy_gem", [g]), ("energy_osm", [{**o, "mw": 100.0}])])), 2)

    def test_brackets_alias_only_plant_names(self):
        self.assertTrue(energy.alias_ok("AnKroet"))
        for frag in ("100MWp", "Phase 1", "g\u1ea7n b\u1edd", "h\u1ed3", "AC Energy"):
            self.assertFalse(energy.alias_ok(frag), frag)
        # Two projects whose names share only "(100MWp)" stay apart; the capacity is not a number of the name.
        a = {"id": "gem:1", "tech": "solar", "name": "Thac Mo solar farm", "name_local": "Nh\u00e0 m\u00e1y \u0111i\u1ec7n m\u1eb7t tr\u1eddi Th\u00e1c M\u01a1 (100MWp)",
             "mw": 50.0, "start": 2020, "status": "operating", "lat": 11.8, "lon": 106.915}
        b = {"id": "gem:2", "tech": "solar", "name": "An Khang Binh Phuoc solar farm", "name_local": "Nh\u00e0 m\u00e1y \u0111i\u1ec7n m\u1eb7t tr\u1eddi An Khang (100MWp)",
             "mw": 80.0, "start": None, "status": "planned", "lat": 11.8, "lon": 106.915}
        self.assertEqual(energy.name_key("Th\u00e1c M\u01a1 (100MWp)"), ("thacmo", frozenset()))
        self.assertEqual([p["id"] for p in energy.merge([("energy_gem", [b, a])])], ["gem:1"])

    def test_planned_never_absorbs_operating_of_another_size(self):
        plan = {"id": "gem:P", "tech": "solar", "name": "Easup solar farm", "mw": 130.0, "start": None, "status": "planned",
                "lat": 13.231, "lon": 107.691}
        osm = {"id": "osm:E", "tech": "solar", "name": "Nh\u00e0 m\u00e1y \u0110i\u1ec7n m\u1eb7t tr\u1eddi Ea S\u00fap", "mw": 600.0,
               "start": 2020, "status": "operating", "lat": 13.233, "lon": 107.69}
        self.assertEqual([p["id"] for p in energy.merge([("energy_gem", [plan]), ("energy_osm", [osm])])], ["osm:E"])
        self.assertEqual(energy.merge([("energy_gem", [plan]), ("energy_osm", [{**osm, "mw": 130.0}])]), [])
        # OSM construction and planned tags never make an operating plant.
        el = {"type": "way", "id": 7, "center": {"lat": 17.9, "lon": 106.5},
              "tags": {"power": "plant", "plant:source": "gas", "construction:power": "plant", "plant:output:electricity": "2700 MW"}}
        self.assertEqual(energy_osm.plant_point(el)["status"], "planned")
        self.assertEqual(energy.merge([("energy_osm", [energy_osm.plant_point(el)])]), [])

    def test_oil_and_gas_units_of_one_location_add_up(self):
        units = [{"loc": "L9", "unit": f"G{k}", "tech": t, "name": "Ca Mau power station", "unit_name": str(k),
                  "mw": mw, "start": 2008, "end": None, "status": "operating", "lon": 105.06, "lat": 9.242}
                 for k, (t, mw) in enumerate([("gas", 750.0), ("oil", 750.0), ("oil", 100.0)], 1)]
        (cm,) = energy_gem.plants(units)
        self.assertEqual((cm["tech"], cm["mw"]), ("oil", 1600.0))
        wri = {"id": "wri:1", "tech": "gas", "name": "Ca Mau 1", "mw": 1542.0, "start": None, "status": "operating",
               "lat": 9.242, "lon": 105.06}
        out = energy.merge([("energy_gem", [cm]), ("energy_osm", [wri])])
        self.assertEqual([(p["id"], p["mw"]) for p in out], [("gem:L9", 1600.0)])

    def test_numbered_plants_that_share_an_alias_stay_apart(self):
        # An alias of several plants is the identity of none, so numbered neighbours do not merge through it.
        def rec(i, name, alias, mw, lat):
            return {"id": f"gem:{i}", "tech": "biomass", "name": name, "aliases": [alias], "mw": mw, "start": None, "status": "operating", "lat": lat, "lon": 101.5}
        a = rec(1, "National Power Plant 5 power station", "304-Ip", 37.0, 13.90)
        b = rec(2, "National Power Plant 6 power station", "304-Ip", 37.0, 13.91)
        self.assertEqual(len(energy.merge([("energy_gem", [a, b])])), 2)
        e = rec(3, "Kampaengsaen East power station", "Thailand MWE", 8.0, 14.0)
        w = rec(4, "Kamphaengsaen West power station", "Thailand MWE", 8.0, 14.003)
        self.assertEqual(len(energy.merge([("energy_gem", [e, w])])), 2)
        # The same alias on records of one source does not join their numbered plants either.
        o1 = {"id": "osm:1", "tech": "gas", "name": "Amata B.Grimm Power Plant 1 & 2", "aliases": ["amata bgrimm power limited"], "mw": 337.0, "status": "operating", "start": None, "lat": 13.5, "lon": 101.0}
        o2 = {"id": "osm:2", "tech": "gas", "name": "Amata B.Grimm Power Plant 3", "aliases": ["amata bgrimm power limited"], "mw": 133.0, "status": "operating", "start": None, "lat": 13.51, "lon": 101.0}
        self.assertEqual(len(energy.merge([("energy_osm", [o1, o2])])), 2)
        # A plant keeps its own alias as a name when no other record has it.
        g = {"id": "gem:5", "tech": "gas", "name": "Chiang Rak Noi power station", "aliases": ["Gulf CRN power station"], "mw": 126.0, "start": 2013, "status": "operating", "lat": 14.1, "lon": 100.7}
        o = {"id": "osm:5", "tech": "gas", "name": "Gulf CRN power station", "mw": None, "start": None, "status": "operating", "lat": 14.1, "lon": 100.7}
        self.assertEqual(len(energy.merge([("energy_gem", [g]), ("energy_osm", [o])])), 1)

    def test_alias_that_is_also_a_name_still_joins(self):
        # Both records carry "Ras Laffan C" as an alias and a third record has it as its name: it is one plant.
        g = {"id": "gem:1", "tech": "gas", "name": "Ras Laffan C power plant", "aliases": ["Ras Laffan C power and desalination plant"], "mw": 2732.0, "start": 2011, "status": "operating", "lat": 25.93, "lon": 51.52}
        o = {"id": "osm:1", "tech": "gas", "name": "Ras Girtas Power Station", "aliases": ["Ras Laffan 'C' Power Plant"], "mw": 2730.0, "start": None, "status": "operating", "lat": 25.937, "lon": 51.522}
        self.assertEqual(len(energy.merge([("energy_gem", [g]), ("energy_osm", [o])])), 1)

    def test_alias_without_numbers_takes_the_numbers_of_the_name(self):
        p = {"name": "Amata B.Grimm Power Plant 4 & 5", "aliases": ["amata bgrimm power limited"]}
        q = {"name": "Amata B.Grimm Power Plant 1 & 2", "aliases": ["amata bgrimm power limited"]}
        self.assertEqual(energy.name_match(p, q), 0.0)
        # An alias that is a plant's real name still joins it.
        self.assertEqual(energy.name_match({"name": "Foo 2", "aliases": ["Bar"]}, {"name": "Bar 2"}), 1.0)

    def test_urdu_generic_words(self):
        tarbela = "\u062a\u0631\u0628\u06cc\u0644\u0627 \u067e\u0646 \u0628\u062c\u0644\u06cc \u06af\u06be\u0631"
        self.assertEqual(energy.name_key(tarbela), ("\u062a\u0631\u0628\u06cc\u0644\u0627", frozenset()))
        self.assertTrue(energy.same_name({"name": tarbela}, {"name": "\u062a\u0631\u0628\u06cc\u0644\u0627 \u067e\u0627\u0648\u0631 \u067e\u0644\u0627\u0646\u0679"}))

    def test_gem_file_streamed_and_recorded(self):
        def cell(ref, v):
            return f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>' if isinstance(v, str) else f'<c r="{ref}"><v>{v}</v></c>'
        table = [["Type", "Country/area", "Plant / Project name", "Capacity (MW)", "Status", "Latitude", "Longitude",
                  "GEM location ID"],
                 ["coal", "Elsewhere", "X", 5, "operating", 1, 1, "L0"],
                 ["coal", ENERGY_COUNTRY["gem_names"][0], "Y", 600, "operating", 21, 106.7, "L1"]]
        sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' +
                 "".join(f'<row r="{i + 1}">' + "".join(cell(f"{chr(65 + j)}{i + 1}", v) for j, v in enumerate(r)) + "</row>"
                         for i, r in enumerate(table)) + "</sheetData></worksheet>")
        about = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                 '<row r="1"><c r="A1" t="inlineStr"><is><t>About</t></is></c></row></sheetData></worksheet>')
        files = {
            "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                               '<sheet name="About" sheetId="1" r:id="rId1"/><sheet name="Power facilities" sheetId="2" r:id="rId2"/>'
                               '</sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                          '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                                          '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>',
            "xl/worksheets/sheet1.xml": about, "xl/worksheets/sheet2.xml": sheet,
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "Global-Integrated-Power-September-2026-V2.xlsx"
            with zipfile.ZipFile(path, "w") as z:
                for k, v in files.items():
                    z.writestr(k, v)
            head, rows = energy_gem._rows(path)
            self.assertEqual((head[2], [r[2] for r in rows]), ("Plant / Project name", ["Y"]))
            self.assertEqual(energy_gem.release(path), "September 2026")
            with mock.patch.object(energy_gem, "manifest_path", lambda sid: Path(d) / "manifest.json"), \
                    mock.patch.object(energy_gem, "read_manifest", lambda sid: {}):
                entry = energy_gem.record(path)
            self.assertEqual((entry["url"], entry["bytes"], len(entry["sha256"])), (energy_gem.DOWNLOAD, path.stat().st_size, 64))

    def test_xlsx_reader(self):
        sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                 '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="inlineStr"><is><t>Latitude</t></is></c></row>'
                 '<row r="2"><c r="A2"><v>12.5</v></c><c r="C2"><v>10</v></c></row></sheetData></worksheet>')
        files = {
            "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                               '<sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                          '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
            "xl/sharedStrings.xml": '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Capacity (MW)</t></si></sst>',
            "xl/worksheets/sheet1.xml": sheet,
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.xlsx"
            with zipfile.ZipFile(path, "w") as z:
                for k, v in files.items():
                    z.writestr(k, v)
            rows = ec.xlsx_sheets(path)["Data"]
        self.assertEqual(rows, [["Capacity (MW)", None, "Latitude"], [12.5, None, 10.0]])
        head, data = ec.table_with(rows, "capacity", "latitude")
        self.assertEqual(data, [[12.5, None, 10.0]])

    def test_gem_source_only_with_a_file(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(energy_gem, "FOLDER", Path(d)):
            self.assertIsNone(energy_gem.gem_file())
            (Path(d) / "Global-Integrated-Power-test.xlsx").write_bytes(b"")
            self.assertEqual(energy_gem.gem_file().name, "Global-Integrated-Power-test.xlsx")


class Lenses(unittest.TestCase):
    def test_add_lenses_is_idempotent(self):
        world = {"owner": [0, 0, 1, -1], "states": ["A", "B"]}
        doc = {"groups": [{"id": "people", "name": "People"}], "cells": [0, 1, 2],
               "lenses": [{"id": "pop", "level": "province", "values": [1, 1, 2]}]}
        units = {"A": {"mw": 1200, "solar_wind_mw": 200}}
        energy.add_lenses(doc, world, units, "energy_osm")
        energy.add_lenses(doc, world, units, "energy_osm")
        ids = [l["id"] for l in doc["lenses"]]
        self.assertEqual(ids, ["pop", "energy_capacity", "energy_solar_wind"])
        cap = doc["lenses"][1]
        self.assertEqual(cap["values"], [1200, 1200, 0])
        self.assertEqual(cap["level"], "province")
        self.assertEqual(sum(1 for g in doc["groups"] if g["id"] == "energy"), 1)
        self.assertLess(cap["domain"][0], cap["domain"][1])


if __name__ == "__main__":
    unittest.main()
