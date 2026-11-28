"""The energy module (docs/ENERGY_PORT.md): web/data/energy.json and two lenses added to lenses.json.

energy.json holds every power plant from the plant sources (GEM when its file is cached, then OpenStreetMap, then
WRI for plants the others miss), placed on the map, and the national Ember series (installed capacity and the
electricity mix by year, plus the newest 12 months). The lenses "Power capacity" and "Solar and wind capacity" sum the
operating plants of each first-level unit (world `owner` -> world `states`).

Nothing here names a country: the sources read pipeline/sources/energy_config.py.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache

from ..core.geo import MapProjection
from ..core.hexgrid import HexGrid
from ..core.paths import INTERIM, WEB_DATA
from ..core.store import atomic_write_text, load_interim, load_interim_payload, write_web
from ..sources.energy_common import TECHS
from ..sources.energy_config import ENERGY_GENERIC_CUT, ENERGY_GENERIC_WORDS
from ..sources.energy_gem import gem_file

PLANT_SOURCES = ["energy_gem", "energy_osm", "energy_wri"]  # priority order
GEM = "energy_gem"
REQUIRES = ["_world", "energy_ember", "energy_osm", "energy_wri", "lenses.json", *(["energy_gem"] if gem_file() else [])]
PRODUCES = ["energy.json"]
MATCH_KM = 4.0  # an unnamed plant of the same technology this close to a kept one is the same plant
FAR_KM = 100.0  # the same name, numbers and capacity in two sources this far apart is one plant
NAME_KM = 15.0  # a plant with the same name and technology this close is the same plant (a dam and its power house)
RINGS = 40  # a plant off the coast (an island too small for its own hex) joins the nearest land hex this close (200 km)
LENS_IDS = ("energy_capacity", "energy_solar_wind")
# Almanac text of the moving layer ("Moving layers" page reads energy.json `rules`).
RULES = [
    "Power plants from the Global Integrated Power Tracker, then OpenStreetMap and the Global Power Plant Database "
    "for plants the tracker does not list. A plant shows from the year it started until the year it retired; plants "
    "without a start year are not drawn. The capacity of a plant is the sum of its operating units.",
    f"Two records of the same technology are one plant when their names and numbers agree and they lie within "
    f"{NAME_KM:g} km, or when one has no name and they lie within {MATCH_KM:g} km.",
    "Installed capacity and the electricity mix are national figures from Ember. In the newest year the mix covers "
    "the newest 12 months.",
    "The lenses Power capacity and Solar and wind capacity add up the operating plants with a known capacity.",
]
GROUP = {"id": "energy", "name": "Energy", "icon": "i-utilities"}
RAMP = ["#14110a", "#3d2f0c", "#7a5a12", "#c08a1c", "#eebd45", "#fff2b0"]
RAMP_SW = ["#0b1d24", "#173f4c", "#2b6f7a", "#56a3a0", "#a6d6b8", "#f4f9dc"]


def km(a: dict, b: dict) -> float:
    dlat = math.radians(b["lat"] - a["lat"])
    dlon = math.radians(b["lon"] - a["lon"]) * math.cos(math.radians((a["lat"] + b["lat"]) / 2))
    return 6371.0 * math.hypot(dlat, dlon)


# Latin letters that Unicode does not decompose into an ASCII base letter.
_FOLD = {"\u0142": "l", "\u0141": "l", "\u0111": "d", "\u0110": "d", "\u00f8": "o", "\u00d8": "o", "\u00df": "ss",
         "\u00e6": "ae", "\u00c6": "ae", "\u0131": "i"}
ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6"}
SIMILAR = 0.85  # two name keys this alike (1 - edit distance / longer length) are spelling variants of one name


def fold(text: str) -> str:
    """Lower case; Latin letters lose their diacritics (o-acute -> o, l-with-stroke -> l, d-with-stroke -> d);
    letters of other scripts (Thai, Bangla, Arabic) stay as they are."""
    out = []
    for ch in unicodedata.normalize("NFC", text):
        if ch in _FOLD:
            out.append(_FOLD[ch])
            continue
        d = unicodedata.normalize("NFKD", ch)
        out.append("".join(c for c in d if c.isascii()) if d[0].isascii() else unicodedata.normalize("NFKC", ch))
    return "".join(out).lower()


GENERIC = {fold(w) for words in ENERGY_GENERIC_WORDS.values() for w in words if " " not in w}
PHRASES = [re.compile(r"(?<!\w)" + re.escape(fold(w)) + r"(?!\w)")
           for words in ENERGY_GENERIC_WORDS.values() for w in words if " " in w]
CUT = sorted({fold(w) for lang in ENERGY_GENERIC_CUT for w in ENERGY_GENERIC_WORDS.get(lang, [])}, key=len, reverse=True)


def _runs(text: str) -> list[tuple[str, str]]:
    """(kind, text) runs of letters ("L", with their combining marks), digits ("D") and anything else ("S")."""
    runs: list[list[str]] = []
    for ch in text:
        cat = unicodedata.category(ch)
        kind = "L" if cat[0] in "LM" else "D" if cat == "Nd" else "S"
        if runs and runs[-1][0] == kind:
            runs[-1][1] += ch
        else:
            runs.append([kind, ch])
    return [(k, t) for k, t in runs]


def name_key(name: str | None) -> tuple[str, frozenset] | None:
    """(name words run together, numbers): see name_words()."""
    w = name_words(name)
    return w and ("".join(w[0]), w[1])


@lru_cache(maxsize=None)
def name_words(name: str | None) -> tuple[tuple[str, ...], frozenset] | None:
    """(name words run together, numbers) of a plant name without the generic words of energy_config
    ENERGY_GENERIC_WORDS: "Nha may Nhiet dien Vinh Tan 2" -> ("vinhtan", {"2"}); "Sre Pok 4A" -> ("srepok", {"4a"}).
    Latin letters are folded, so spellings with and without diacritics or spaces agree; Thai, Bangla and Arabic
    letters are kept. Roman numerals and a last word of one or two capital letters ("Nhan Hac B", "Cam An Bac VN")
    count as numbers. A name made only of generic words keys on those words. None only for an empty name."""
    if not name or not str(name).strip():
        return None
    name = _CAPACITY.sub(" ", str(name)).strip() or str(name).strip()
    letters = [t for k, t in _runs(name) if k == "L"]
    tail = letters[-1] if len(letters) > 1 and not name.isupper() else ""
    tail = tail.lower() if tail.isascii() and tail.isupper() and len(tail) <= 2 else None
    text = re.sub(r"(?<=\d)\.(?=\d)", "", fold(name))
    for ph in PHRASES:
        text = ph.sub(" ", text)
    runs = _runs(text)  # "Phu My 2.1" is "Phu My 21" in WRI
    last = max((i for i, (k, _) in enumerate(runs) if k == "L"), default=-1)
    words, nums, every = [], set(), []
    for i, (kind, tok) in enumerate(runs):
        if kind == "D":
            nxt = runs[i + 1][1] if i + 1 < len(runs) and runs[i + 1][0] == "L" else ""
            suffix = nxt if len(nxt) == 1 and nxt.isascii() else ""
            nums.add(str(int(tok)) + suffix)
        elif kind == "L":
            if len(tok) == 1 and tok.isascii() and i and runs[i - 1][0] == "D":
                continue  # the letter of "4A"
            if tok in ROMAN:
                nums.add(ROMAN[tok])
                continue
            if i == last and tok == tail:
                nums.add(tok)
                continue
            every.append(tok)
            if tok in GENERIC:
                continue
            for w in CUT:
                tok = tok.replace(w, "")
            if tok:
                words.append(tok)
    if not words and not nums:
        words = every or [fold(name)]
    return tuple(words), frozenset(nums)


def sound(word: str) -> str:
    """A name key with the usual romanisation variants made equal: kh/c/q -> k, y -> i, double letters single
    ("Dac Me" and "Dak Me", "Da Kai" and "Da Khai", "Tann" and "Tan"). Non-Latin letters are kept."""
    word = re.sub(r"c(?!h)", "k", word.replace("kh", "k")).replace("q", "k").replace("y", "i")
    return re.sub(r"(.)\1+", r"\1", word)


def similarity(a: str, b: str) -> float:
    """1 - Levenshtein distance / length of the longer string (1.0 for equal strings)."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return 1 - prev[-1] / max(len(a), len(b))


_CAPACITY = re.compile(r"\d+(?:[.,]\d+)?\s*(?:k|m|g)wp?(?:ac|dc)?\b", re.I)  # "100MWp", "50 MW" in a name


def alias_ok(text: str) -> bool:
    """Whether the text in brackets is itself a plant name: not a capacity ("100MWp"), not a phase ("Phase 1"), not
    a fragment ("ho", "gan bo"). Latin text needs a word with a capital letter and a key of at least 4 letters."""
    key = name_key(_CAPACITY.sub(" ", text))
    if not key or len(key[0]) < 4:
        return False
    latin = [w for w in re.findall(r"[^\W\d_]+", text) if w[0].isascii()]
    return not latin or any(w[0].isupper() for w in latin)


def names_of(p: dict) -> list[tuple[str, frozenset]]:
    """The name keys of a plant: its name, English name, local name and other names (GEM `aliases`). For
    "Suoi Vang (Ankroet)" also the part outside the brackets, and the part inside when alias_ok()."""
    out = []
    texts = [p.get("name"), p.get("name_en"), p.get("name_local"), *(p.get("aliases") or ())]
    for text in (str(t) for t in texts if t):
        parts = [text]
        if "(" in text:
            parts.append(re.sub(r"\([^()]*\)", " ", text))
            parts += [b for b in re.findall(r"\(([^()]*)\)", text) if alias_ok(b)]
        out += [k for k in map(name_key, parts) if k and k not in out]
    return out


def name_match(a: dict, b: dict) -> float | None:
    """How well the names of two plants agree: 1.0 for the same words, the similarity of the closest spelling
    variant (at least SIMILAR, compared by sound(); below 1.0 even when the sounds agree), 0.0 when both are named
    and no names agree, None when either has no name. Names agree only when their numbers are equal: "Vinh Son" and
    "Vinh Son 5", "Srepok 4" and "Srepok 4A" differ. One exception: a plant of several phases (GEM `parts`, its name
    without a number) agrees with a numbered name of one of its phases ("Vinh Tan power station" with parts 1-4 and
    "Vinh Tan 2")."""
    ka, kb = names_of(a), names_of(b)
    if not ka or not kb:
        return None
    pa, pb = set(a.get("parts") or ()), set(b.get("parts") or ())
    best = 0.0
    for wa, na in ka:
        for wb, nb in kb:
            if not wa or not wb:
                continue
            if na != nb and not (not na and nb and nb <= pa) and not (not nb and na and na <= pb):
                continue
            if wa == wb:
                return 1.0
            s = similarity(sound(wa), sound(wb))
            if s >= SIMILAR and min(len(wa), len(wb)) >= 4:
                best = max(best, min(s, 0.99))
    return best


def words_of(p: dict) -> list[tuple[tuple[str, ...], frozenset]]:
    texts = [p.get("name"), p.get("name_en"), p.get("name_local"), *(p.get("aliases") or ())]
    return [w for w in (name_words(re.sub(r"\([^()]*\)", " ", str(t))) for t in texts if t) if w]


def subset_match(a: dict, b: dict) -> bool:
    """The words of one name (two words or more, 5 letters or more) are all words of the other, with equal numbers:
    OSM "Ea Sup" (600 MW) and GEM "Ea Sup Xuan Thien" (500 MW). same_plant() adds the distance and capacity checks
    ("Hoa Binh mo rong", the extension, is not "Hoa Binh")."""
    for wa, na in words_of(a):
        for wb, nb in words_of(b):
            short, long_ = sorted((wa, wb), key=len)
            if na == nb and len(short) >= 2 and len("".join(short)) >= 5 and set(short) <= set(long_):
                return True
    return False


def same_name(a: dict, b: dict) -> bool | None:
    """True when a name of one plant agrees with a name of the other (name_match), False when both are named and
    no names agree, None when either has no name."""
    m = name_match(a, b)
    return None if m is None else m > 0


def same_mw(a: dict, b: dict, tol: float = 0.05) -> bool:
    """Two records with the same capacity (within `tol`, 5%)."""
    return bool(a.get("mw") and b.get("mw")) and abs(a["mw"] - b["mw"]) <= tol * max(a["mw"], b["mw"])


FAMILY = {"oil": "gas"}  # oil and gas units of one plant often switch fuel: they match as one technology


def family(p: dict) -> str:
    return FAMILY.get(p["tech"], p["tech"])


def same_plant(p: dict, q: dict, src: str) -> bool:
    """Whether p (of source src) is the kept plant q, of the same technology (oil and gas count as one). Two named
    plants match only by name, within NAME_KM. Without a name on either side, within MATCH_KM, plants of two sources
    match, and two objects of one source match when they have the same capacity (a node and an area of one plant).
    Spelling variants (name_match below 1) join only records of two sources, so do names of which one holds all the
    words of the other (subset_match, within MATCH_KM, capacity within 25%) and names with an owner in common at the same capacity
    (same_owner). A planned plant (GEM) takes only
    records with its name, and an operating record only when it has the same capacity. Two GEM plants are one only
    with the same name and capacity (2%): GEM rows are plants by GEM location already."""
    if family(q) != family(p):
        return False
    d = km(p, q)
    if d > NAME_KM:
        return False
    if src == q["src"] == GEM:
        return name_match(p, q) == 1.0 and same_mw(p, q, 0.02)  # GEM lists a few plants twice
    if q["status"] == "planned" and p["status"] == "operating" and p.get("mw") and q.get("mw") and not same_mw(p, q):
        return False  # a project of another size at the place of an operating plant
    m = name_match(p, q)
    if m == 0 and q["src"] != src and (same_owner(p, q) or d <= MATCH_KM and same_mw(p, q, 0.25) and subset_match(p, q)):
        return True
    if m is not None:
        return m == 1.0 if q["src"] == src else m > 0  # one source spells one plant one way
    return d <= MATCH_KM and q["status"] != "planned" and (q["src"] != src or same_mw(p, q))


_FIRM = {"corp", "corporation", "co", "company", "ltd", "limited", "jsc", "pcl", "plc", "group", "inc", "llc", "the",
         "joint", "stock", "investment", "cong", "ty", "tnhh", "cp", "tap", "doan"}


def owners_of(p: dict) -> set[str]:
    """The owner keys of a plant (GEM `owner`, OSM `operator`): "Super Energy Corporation PCL [51%]; Cong Ly" ->
    {"superenergy", "congly"}. Company-form words are dropped; keys shorter than 5 letters are dropped."""
    out = set()
    for part in re.split(r"[;,]", str(p.get("owner") or "")):
        part = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", part)
        words = [w for w in re.findall(r"[^\W\d_]+", fold(part)) if w not in _FIRM]
        if len("".join(words)) >= 5:
            out.add("".join(words))
    return out


def same_owner(p: dict, q: dict) -> bool:
    """Two records of two sources with an owner in common, the same capacity (5%) and the same technology: one plant
    under two names (OSM "Soc Trang" of operator Super Energy Corp, GEM "Cong Ly Soc Trang" of Super Energy)."""
    return bool(owners_of(p) & owners_of(q)) and same_mw(p, q)


def kind_of(p: dict, q: dict) -> str:
    """How p matched q, for the merge log: name, variant, phase (a numbered phase of a GEM plant) or unnamed."""
    m = name_match(p, q)
    if m is None:
        return "unnamed"
    if m == 0:
        return "owner" if same_owner(p, q) else "subset"
    if m < 1:
        return "variant"
    return "name" if any(k in names_of(q) for k in names_of(p)) else "phase"


def merge(lists: list[tuple[str, list[dict]]], log: list | None = None) -> list[dict]:
    """One list of plants from sources in priority order. A plant that is a kept plant adds only the values the kept
    one lacks (mw, start, name), recorded in `fill`; every other plant is kept with `src` = its source. A plant is a
    kept plant when:
    - same_plant() holds within NAME_KM (the nearest best-named one wins);
    - it has the same name, numbers, technology and capacity (5%) as a plant of another source within FAR_KM (one
      of the two positions is wrong: WRI "Mao Khe" lies 84 km from the plant), or as another GEM plant (2%);
    - its capacity (10%) is the sum of two or more kept plants of another source within NAME_KM with the same words
      and numbers that are its numbers, or any numbers when it has none (OSM "Phu My" is GEM "Phu My 1" to
      "Phu My 4"; OSM "Loc Ninh 1-2-3" is GEM "Loc Ninh 1", "Loc Ninh 2" and "Loc Ninh 3"). Planned plants count:
      an OSM wind farm of 241 MW is a GEM farm of 99 MW and its 141 MW extension in construction.
    Planned plants (GEM) are dropped at the end, with the records they took.
    `log`, when given, gets one (source, name, kept source, kept name, name similarity or None, km, kind) per merge."""
    kept: list[dict] = []
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    by_name: dict[tuple, list[dict]] = defaultdict(list)
    cell = lambda p: (round(p["lat"] * 6), round(p["lon"] * 6))  # noqa: E731  (about 18 km, more than NAME_KM)

    def note(p, q, src, kind):
        if log is not None:
            log.append((src, p.get("name"), q["src"], q.get("name"), name_match(p, q), round(km(p, q), 1), kind))

    for src, points in lists:
        for p in points:
            ci, cj = cell(p)
            around = [q for di in (-1, 0, 1) for dj in (-1, 0, 1) for q in buckets.get((ci + di, cj + dj), [])]
            near = [q for q in around if same_plant(p, q, src)]
            keys = names_of(p)
            if near:
                q = min(near, key=lambda q: (-(name_match(p, q) or 0), km(p, q)))
                note(p, q, src, kind_of(p, q))
            else:
                far = [q for k in keys if k[0] for q in by_name.get((family(p), k), [])
                       if name_match(p, q) == 1.0 and (q["src"] != src or src == GEM) and same_mw(p, q, 0.02 if src == GEM else 0.05)
                       and km(p, q) <= FAR_KM]
                if far:
                    q = min(far, key=lambda q: km(p, q))
                    note(p, q, src, "far")
                    near = [q]
            if not near and p.get("mw") and keys:
                parts = [q for q in around if q["src"] != src and family(q) == family(p) and km(p, q) <= NAME_KM
                         and any(wq == w and nq and (not n or nq <= n)
                                                              for w, n in keys for wq, nq in names_of(q))]
                total = sum(q["mw"] or 0 for q in parts)
                if len(parts) >= 2 and abs(total - p["mw"]) <= 0.1 * p["mw"]:
                    for q in parts:
                        note(p, q, src, "parts")
                    continue
            if near:
                q = min(near, key=lambda q: (-(name_match(p, q) or 0), km(p, q)))
                for k in ("mw", "start", "name"):
                    if q.get(k) is None and p.get(k) is not None:
                        q[k] = p[k]
                        q.setdefault("fill", {})[k] = src
                continue
            kept.append({**p, "src": src})
            buckets[(ci, cj)].append(kept[-1])
            for k in keys:
                by_name[(family(p), k)].append(kept[-1])
    return [q for q in kept if q["status"] != "planned"]


def nearest_land(grid: HexGrid, owner: list[int], x: float, y: float, rings: int = RINGS) -> int:
    """The land hex under (x, y), else the land hex whose centre is nearest, searched ring by ring up to `rings`
    (one ring more after the first hit, since a hex of the next ring can be nearer). -1 when there is none."""
    cell = grid.cell_at(x, y)
    if cell < 0:
        return -1
    if owner[cell] >= 0:
        return cell
    seen, frontier, found, extra = {cell}, [cell], [], None
    for k in range(rings):
        nxt = [n for c in frontier for n in grid.neighbours(c) if n not in seen]
        seen.update(nxt)
        found += [n for n in nxt if owner[n] >= 0]
        if found and extra is None:
            extra = k + 1
        if extra is not None and k >= extra:
            break
        frontier = nxt
    if not found:
        return -1
    return min(found, key=lambda n: (grid.center(*grid.col_row(n))[0] - x) ** 2 + (grid.center(*grid.col_row(n))[1] - y) ** 2)


def recent_mix(monthly: dict | None) -> dict | None:
    """The newest 12 months of the monthly series: TWh by technology and the share of the total."""
    if not monthly or len(monthly["periods"]) < 12:
        return None
    sl = slice(len(monthly["periods"]) - 12, None)
    gen = monthly["gen_twh"]
    twh = {t: (None if any(v is None for v in gen[t][sl]) else round(sum(gen[t][sl]), 3)) for t in TECHS}
    if all(v is None for v in twh.values()):
        return None
    total = gen["total"][sl]
    tot = round(sum(total), 3) if all(v is not None for v in total) else round(sum(v or 0 for v in twh.values()), 3)
    share = {t: (None if v is None or not tot else round(100 * v / tot, 2)) for t, v in twh.items()}
    return {"from": monthly["periods"][sl][0], "to": monthly["periods"][-1], "twh": twh, "total_twh": tot,
            "share_pct": share}


def domain(values: list) -> list[float]:
    vals = sorted(v for v in values if v)
    hi = vals[min(len(vals) - 1, int(0.98 * len(vals)))] if vals else 1.0
    mag = 10 ** math.floor(math.log10(max(hi, 1)))
    return [0, math.ceil(hi / mag) * mag]


def add_lenses(doc: dict, world: dict, per_unit: dict, source: str) -> None:
    """Replace the energy lenses in lenses.json with fresh ones (idempotent)."""
    owner, states = world["owner"], world["states"]
    doc["lenses"] = [l for l in doc["lenses"] if l.get("id") not in LENS_IDS]
    if not any(g.get("id") == GROUP["id"] for g in doc["groups"]):
        doc["groups"].append(dict(GROUP))
    level = next((l["level"] for l in doc["lenses"]
                  if l.get("level") and l["level"] not in ("hex", "former", "county")), "province")
    cells = doc["cells"]
    for lid, key, name, short, desc, ramp, icon in [
        ("energy_capacity", "mw", "Power capacity", "Power capacity",
         "Installed electrical capacity of the operating power plants.", RAMP, "i-utilities"),
        ("energy_solar_wind", "solar_wind_mw", "Solar and wind capacity", "Solar and wind",
         "Installed electrical capacity of the operating solar and wind farms.", RAMP_SW, "r-solar"),
    ]:
        per = {code: per_unit.get(code, {}).get(key, 0) for code in states}
        vals = [per[states[owner[c]]] for c in cells]
        doc["lenses"].append({
            "id": lid, "group": GROUP["id"], "name": name, "short_name": short, "unit": "MW", "format": "int",
            "scale": "linear", "ramp": ramp, "higher_is": "neutral", "source": source, "description": desc,
            "level": level, "icon": icon, "emoji": "\u26a1", "domain": domain(list(per.values())), "values": vals})


def build() -> None:
    world = load_interim("_world")
    grid = HexGrid(**world["grid"])
    p = world["projection"]
    proj = MapProjection(p["min_x"], p["max_y"], p.get("margin", 0))
    owner, states = world["owner"], world["states"]

    lists, vint, used = [], [], []
    for sid in PLANT_SOURCES:
        try:
            pay = load_interim_payload(sid)
        except FileNotFoundError:
            continue
        lists.append((sid, pay["data"]["points"]))
        vint.append(pay.get("vintage") or sid)
        used.append(sid)
    log: list = []
    plants = merge(lists, log)
    kinds = defaultdict(int)
    for m in log:
        kinds[m[6]] += 1
    print(f"    {len(log)} records merged into kept plants: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))
    for m in log:
        if m[6] not in ("name", "unnamed"):
            print(f"      {m[6]}: {m[0]} {m[1]!a} -> {m[2]} {m[3]!a} ({m[5]} km)")
    atomic_write_text(INTERIM / "energy_merges.tsv", "".join("\t".join(map(str, m)) + "\n" for m in log))

    rows, per_unit = [], defaultdict(lambda: {"mw": 0.0, "solar_wind_mw": 0.0, "by_tech": defaultdict(float)})
    for pl in plants:
        x, y = proj(pl["lon"], pl["lat"])
        c = nearest_land(grid, owner, x, y)
        if c < 0:
            continue
        operating = pl["status"] == "operating" and pl.get("end") is None
        rows.append([round(x, 1), round(y, 1), TECHS.index(pl["tech"]), pl["mw"], pl["start"], pl.get("end"),
                     1 if operating else 0, used.index(pl["src"]), pl.get("name"), c, 1 if pl.get("tz") else 0])
        if operating and pl["mw"]:
            u = per_unit[states[owner[c]]]
            u["mw"] += pl["mw"]
            u["by_tech"][pl["tech"]] += pl["mw"]
            if pl["tech"] in ("solar", "wind"):
                u["solar_wind_mw"] += pl["mw"]
    rows.sort(key=lambda r: -(r[3] or 0))  # big plants first: drawn under the small ones
    units = {code: {"mw": round(u["mw"]), "solar_wind_mw": round(u["solar_wind_mw"]),
                    "by_tech": {t: round(v) for t, v in u["by_tech"].items()}} for code, u in per_unit.items()}

    ember = load_interim_payload("energy_ember")
    ed = ember["data"]
    yearly, monthly = ed.get("yearly"), ed.get("monthly")
    starts = [r[4] for r in rows if r[4]]
    last = max([*starts, *(yearly["periods"][-1:] if yearly else []),
                *([int(monthly["periods"][-1][:4])] if monthly else [])])
    first = min(starts) if starts else (yearly["periods"][0] if yearly else last)
    national = None
    if yearly:
        national = {"years": yearly["periods"], "capacity_gw": yearly["capacity_gw"],
                    "share_pct": yearly["share_pct"], "gen_twh": {t: yearly["gen_twh"][t] for t in [*TECHS, "total"]}}

    doc = {"version": 1, "iso3": ed.get("iso3"), "techs": TECHS, "years": [first, last], "srcs": used,
           "sources": ["energy_ember", *used, *(["energy_gem_tz"] if any(r[10] for r in rows) else [])], "rules": RULES, "vintage": {"ember": ember.get("vintage"), "plants": "; ".join(vint)},
           "plants": {"columns": ["x", "y", "tech", "mw", "start", "end", "operating", "src", "name", "cell", "tz"],
                      "rows": rows},
           "national": national, "recent": recent_mix(monthly), "coverage": ed.get("coverage"),
           "units": units}

    path = WEB_DATA / "lenses.json"
    lenses = json.loads(path.read_text(encoding="utf-8"))
    add_lenses(lenses, world, units, used[0] if used else "energy_osm")
    atomic_write_text(path, json.dumps(lenses, separators=(",", ":"), allow_nan=False))
    write_web("energy.json", doc)  # after lenses.json, so energy.json stays newer than its inputs
    by = defaultdict(int)
    for r in rows:
        by[TECHS[r[2]]] += 1
    print(f"    {len(rows)} plants ({sum(r[10] for r in rows)} tz) {first}-{last} ({', '.join(f'{t} {n}' for t, n in by.items())}); "
          f"{sum(1 for r in rows if r[4])} with a start year; lenses {', '.join(LENS_IDS)}")


def check(web_dir) -> list[tuple[str, str]]:
    """energy.json: plants inside the map with known technologies, the year range, and the two lenses."""
    from pathlib import Path

    f = Path(web_dir) / "energy.json"
    if not f.exists():
        return [("NOTE", "energy.json missing (build energy)")]
    doc = json.loads(f.read_text(encoding="utf-8"))
    out = []
    rows = doc["plants"]["rows"]
    bad = [r for r in rows if not (0 <= r[2] < len(doc["techs"])) or (r[3] is not None and r[3] <= 0)
           or (r[4] is not None and not doc["years"][0] <= r[4] <= doc["years"][1])]
    out.append(("FAIL" if bad else "PASS", f"energy.json: {len(rows)} plants, {len(bad)} with a bad tech, MW or year"))
    lens = json.loads((Path(web_dir) / "lenses.json").read_text(encoding="utf-8"))
    have = {l["id"] for l in lens["lenses"]}
    miss = [i for i in LENS_IDS if i not in have]
    out.append(("FAIL" if miss else "PASS", f"lenses.json energy lenses: {'missing ' + ', '.join(miss) if miss else 'present'}"))
    total = sum(u["mw"] for u in doc["units"].values())
    plant_mw = sum(r[3] or 0 for r in rows if r[6])
    out.append(("PASS" if abs(total - plant_mw) <= 1 + 0.001 * plant_mw else "FAIL",
                f"energy.json: unit capacity sums to the operating plants ({total:,.0f} MW)"))
    return out
