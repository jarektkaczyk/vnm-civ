"""Vietnam's expressways, national highways, railways and airports on the hex map (infrastructure.json).

Lines are sampled every 2.5 km and snapped to links between neighbouring hex centres; each link keeps its best
class. Airports take the land hex under them (or the nearest within three rings).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from ..core.geo import MapProjection
from ..core.hexgrid import HexGrid
from ..core.store import load_interim, load_interim_payload, write_web

REQUIRES = ["_world", "vn_osm_transport", "vn_ourairports", "vn_geo_admin", "vn_osm_hubs"]
PRODUCES = ["infrastructure.json", "hubs.json"]

SAMPLE_KM = 2.5
SITE_RINGS = 3
# Airport names as they are written locally (tone marks), on the English page too; OurAirports writes most plain.
AIRPORT_NAMES = {
    "VVCR": "Cam Ranh International Airport / Cam Ranh Air Base",
    "VVCT": "C\u1ea7n Th\u01a1 International Airport",
    "VVCI": "C\xe1t Bi International Airport",
    "VVDN": "\u0110\xe0 N\u1eb5ng International Airport",
    "VVNB": "N\u1ed9i B\xe0i International Airport",
    "VVPB": "Ph\xfa B\xe0i International Airport",
    "VVPQ": "Ph\xfa Qu\u1ed1c International Airport",
    "VVTS": "T\xe2n S\u01a1n Nh\u1ea5t International Airport",
    "VVBM": "Bu\xf4n Ma Thu\u1ed9t Airport",
    "VVCS": "C\xf4n \u0110\u1ea3o Airport",
    "VVCM": "C\xe0 Mau Airport",
    "VVDB": "\u0110i\u1ec7n Bi\xean Ph\u1ee7 Airport",
    "VVDH": "\u0110\u1ed3ng H\u1edbi Airport",
    "VVTH": "\u0110\u1ed3ng T\xe1c Airport",
    "VVDL": "Li\xean Kh\u01b0\u01a1ng Airport",
    "VVPC": "Ph\xf9 C\xe1t Airport",
    "VVPK": "Pleiku Airport",
    "VVRG": "R\u1ea1ch Gi\xe1 Airport",
    "VVVD": "V\xe2n \u0110\u1ed3n International Airport",
    "VVVH": "Vinh Airport",
    "VVCA": "Chu Lai Airport",
    "VVTX": "Th\u1ecd Xu\xe2n Airport",
}


ROAD_CLASSES = [{"id": "motorway", "name": "Expressway"}, {"id": "trunk", "name": "National highway"}]
RAIL_TIERS = [{"id": "main", "name": "Railway line"}, {"id": "secondary", "name": "Other mapped line"}]
RULES = {
    "roads": "Every expressway (highway=motorway) and national highway (highway=trunk) open to traffic in the "
             "OpenStreetMap extract, sampled every 2.5 km and snapped to links between neighbouring hexes.",
    "rail": "Every railway line (railway=rail without a service tag) in the OpenStreetMap extract.",
    "airports": "Every airport in Vietnam with scheduled passenger service in the OurAirports list.",
}

def _axial(grid: HexGrid, cell: int) -> tuple[int, int]:
    col, row = grid.col_row(cell)
    return col - (row - (row & 1)) // 2, row


def _from_axial(grid: HexGrid, q: int, r: int) -> int:
    col = q + (r - (r & 1)) // 2
    if 0 <= col < grid.cols and 0 <= r < grid.rows:
        return grid.index(col, r)
    return -1


def hex_distance(grid: HexGrid, a: int, b: int) -> int:
    (q1, r1), (q2, r2) = _axial(grid, a), _axial(grid, b)
    return (abs(q1 - q2) + abs(r1 - r2) + abs((q1 + r1) - (q2 + r2))) // 2


def hex_walk(grid: HexGrid, a: int, b: int) -> list[int]:
    """Return the cells on the straight hex line from a to b, including both ends."""
    n = hex_distance(grid, a, b)
    if n <= 1:
        return [a, b] if a != b else [a]
    (q1, r1), (q2, r2) = _axial(grid, a), _axial(grid, b)
    out = []
    for i in range(n + 1):
        t = i / n
        x = q1 + (q2 - q1) * t + 1e-6
        z = r1 + (r2 - r1) * t + 1e-6
        y = -x - z
        rx, ry, rz = round(x), round(y), round(z)
        dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
        if dx > dy and dx > dz:
            rx = -ry - rz
        elif dy <= dz:
            rz = -rx - ry
        cell = _from_axial(grid, rx, rz)
        if cell >= 0 and (not out or out[-1] != cell):
            out.append(cell)
    return out


def sample_cells(grid: HexGrid, pts: list[tuple[float, float]]) -> list[list[int]]:
    """Sample a projected line and return runs of distinct cells."""
    runs, run = [], []

    def add(x: float, y: float) -> None:
        cell = grid.cell_at(x, y)
        if cell >= 0 and (not run or run[-1] != cell):
            run.append(cell)

    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        steps = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / SAMPLE_KM))
        for i in range(steps):
            t = i / steps
            add(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
    if pts:
        add(*pts[-1])
    if len(run) > 1:
        runs.append(run)
    return runs


def straighten(grid: HexGrid, run: list[int]) -> list[int]:
    """Remove corner-clipping detours that make a line zigzag between two rows."""
    out = []
    for cell in run:
        while len(out) >= 2 and cell in grid.neighbours(out[-2]):
            out.pop()
        if not out or out[-1] != cell:
            out.append(cell)
    return out


def links_of(grid: HexGrid, run: list[int]) -> list[tuple[int, int]]:
    if len(run) < 2:
        return []
    filled = [run[0]]
    for a, b in zip(run, run[1:]):
        filled.extend(hex_walk(grid, a, b)[1:])
    filled = straighten(grid, filled)
    out = []
    for a, b in zip(filled, filled[1:]):
        path = hex_walk(grid, a, b)
        for u, v in zip(path, path[1:]):
            if u != v:
                out.append((u, v) if u < v else (v, u))
    return out


def _route_key(name: str) -> tuple:
    digits = "".join(ch for ch in name if ch.isdigit())
    return (int(digits) if digits else 99999, name)


def build_lines(grid: HexGrid, proj: MapProjection, owner: list[int], lines: list[dict], kinds: dict) -> list[list]:
    """[[cell a, cell b, class, name]] for the lines whose kind is in `kinds` (kind -> class, 0 best)."""
    class_of: dict[tuple[int, int], int] = {}
    names: dict[tuple[int, int], Counter] = defaultdict(Counter)
    for feature in lines:
        cls = kinds.get(feature.get("kind"))
        if cls is None:
            continue
        name = feature.get("ref") or feature.get("name")
        pts = [proj(lon, lat) for lon, lat in feature.get("coords") or []]
        for run in sample_cells(grid, pts):
            for pair in links_of(grid, run):
                a, b = pair
                if owner[a] < 0 and owner[b] < 0:
                    continue
                if cls < class_of.get(pair, 9):
                    class_of[pair] = cls
                    names[pair].clear()
                if cls == class_of.get(pair) and name:
                    names[pair][name] += 1
    return [[a, b, cls, min(names[(a, b)], key=_route_key) if names[(a, b)] else None]
            for (a, b), cls in sorted(class_of.items())]


def nearest_land(grid: HexGrid, owner: list[int], cell: int, rings: int = SITE_RINGS) -> int:
    if cell < 0:
        return -1
    if owner[cell] >= 0:
        return cell
    seen, frontier = {cell}, [cell]
    x, y = grid.center(*grid.col_row(cell))
    for _ in range(rings):
        nxt = []
        for current in frontier:
            for near in grid.neighbours(current):
                if near not in seen:
                    seen.add(near)
                    nxt.append(near)
        land = [n for n in nxt if owner[n] >= 0]
        if land:
            return min(land, key=lambda n: math.dist(grid.center(*grid.col_row(n)), (x, y)))
        frontier = nxt
    return -1


def build() -> None:
    world = load_interim("_world")
    admin = load_interim("vn_geo_admin")
    osm_p = load_interim_payload("vn_osm_transport")
    air_p = load_interim_payload("vn_ourairports")
    grid = HexGrid(**world["grid"])
    p = world["projection"]
    proj = MapProjection(p["min_x"], p["max_y"], p.get("margin", 0))
    owner = world["owner"]
    abbr = {u["code"]: u["abbr"] for u in admin["provinces"]}
    lines = osm_p["data"]["lines"]
    roads = build_lines(grid, proj, owner, lines, {"motorway": 0, "trunk": 1})
    rail = [[a, b, cls] for a, b, cls, _ in build_lines(grid, proj, owner, lines, {"rail": 0})]
    airports = []
    order = {"large": 0, "medium": 1, "small": 2}
    for pt in sorted(air_p["data"]["points"], key=lambda q: (order[q["kind"]], q["name"])):
        x, y = proj(pt["lon"], pt["lat"])
        cell = nearest_land(grid, owner, grid.cell_at(x, y))
        if cell < 0:
            continue
        airports.append({"id": pt["id"], "name": AIRPORT_NAMES.get(pt["icao"], pt["name"]), "icao": pt["icao"], "iata": pt["iata"],
                         "rank": len(airports) + 1, "size": pt["kind"], "passengers": None, "year": None,
                         "status": "operating", "x": round(x, 1), "y": round(y, 1), "cell": cell,
                         "county": None, "cbsa": None, "state": abbr[world["states"][owner[cell]]]})
    write_web("infrastructure.json", {
        "version": 1,
        "vintage": {"roads": osm_p["vintage"], "rail": osm_p["vintage"], "airports": air_p["vintage"]},
        "sources": ["vn_osm_transport", "vn_ourairports"],
        "rules": RULES,
        "road_classes": ROAD_CLASSES, "rail_tiers": RAIL_TIERS,
        "roads": roads, "rail": rail, "ports": [], "airports": airports,
        "totals": {"network": osm_p["data"].get("km") or {}},
    })
    print(f"    {len(roads)} road links, {len(rail)} rail links, {len(airports)} airports")
    try:
        hubs = load_interim_payload("vn_osm_hubs")
    except FileNotFoundError:
        hubs = None
    if hubs:
        def km(rings):
            return [[round(v, 3) for lon, lat in r for v in proj(lon, lat)] for r in rings]
        d = hubs["data"]
        write_web("hubs.json", {
            "version": 1, "vintage": hubs["vintage"], "sources": ["vn_osm_hubs"],
            "rules": ["Every aerodrome outline with its runways and every port area (landuse=port or industrial=port) "
                      "in the OpenStreetMap extract, drawn when the map is zoomed in."],
            "aerodromes": [{"name": a["name"], "iata": a["iata"], "rings": km(a["rings"])} for a in d["aerodromes"]],
            "runways": [{"ref": r["ref"], "width_m": r["width_m"], "line": km([r["line"]])[0]} for r in d["runways"]],
            "ports": [{"name": a["name"], "rings": km(a["rings"])} for a in d["ports"]],
        })
