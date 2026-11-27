"""Shared helpers for the Vietnam builders (not a builder: no build()).

Units: the 34 provinces (world `states`) and the 63 former provinces (world `counties`). Every former province lies
whole inside one province, so a hex's province is `owner[cell]` and its former province `county[cell]`.

A province metric reaches a hex through `owner`; a former-province metric through `county`. Gridded metrics are
computed per hex by their builder.
"""

from __future__ import annotations

import math
from collections import deque

from ..core.hexgrid import HexGrid
from ..core.store import load_interim_payload

MIN_LABEL_KM, MAX_LABEL_KM = 8.0, 40.0  # suggested font height range, map km
PCT_KEYS = ["forest", "crop", "pasture", "grass", "shrub", "wetland", "developed"]


def optional(name: str) -> dict | None:
    """An interim payload ({vintage, data, files}) or None when the source has not been processed."""
    try:
        return load_interim_payload(name)
    except FileNotFoundError:
        return None


def land_shares(world: dict, s: int) -> dict | None:
    """Mean world `pct` (0..100) over the province's cells with land-cover samples, as 0..1 fractions."""
    pct, cover, owner = world.get("pct"), world.get("cover"), world["owner"]
    if not pct or not cover:
        return None
    cells = [i for i, o in enumerate(owner) if o == s and cover[i]]
    if not cells:
        return None
    return {k: round(sum(pct[k][i] for i in cells) / len(cells) / 100, 3) for k in PCT_KEYS}


def label_anchor(grid: HexGrid, owner: list[int], s: int, name: str) -> dict | None:
    """{x, y, angle, size} for state index `s`, or None if it owns no hex.

    angle: degrees, clockwise on screen (y down), in (-90, 90]. size: suggested font height in map km.
    """
    cells = [i for i, o in enumerate(owner) if o == s]
    if not cells:
        return None
    # Multi-source BFS from the border hexes inward.
    dist = {}
    queue = deque()
    for c in cells:
        nb = grid.neighbours(c)
        if len(nb) < 6 or any(owner[n] != s for n in nb):
            dist[c] = 0
            queue.append(c)
    while queue:
        c = queue.popleft()
        for n in grid.neighbours(c):
            if owner[n] == s and n not in dist:
                dist[n] = dist[c] + 1
                queue.append(n)
    pts = {c: grid.center(*grid.col_row(c)) for c in cells}
    mx = sum(p[0] for p in pts.values()) / len(cells)
    my = sum(p[1] for p in pts.values()) / len(cells)

    # Principal axis of the hex centres. Labels stay horizontal unless tilting them
    # along a clearly elongated state (at most 45 degrees) allows a much bigger name.
    sxx = sum((p[0] - mx) ** 2 for p in pts.values())
    syy = sum((p[1] - my) ** 2 for p in pts.values())
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts.values())
    theta = 0.5 * math.atan2(2 * sxy, sxx - syy)  # (-90, 90] degrees, clockwise on screen
    angles = [0.0] + ([theta] if 1 <= abs(math.degrees(theta)) <= 45 else [])
    step = grid.radius / 4

    def reach(x: float, y: float, ux: float, uy: float) -> float:
        """Distance (km) from (x, y) along (ux, uy) before leaving the state's hexes."""
        t = 0.0
        while True:
            c = grid.cell_at(x + (t + step) * ux, y + (t + step) * uy)
            if c < 0 or owner[c] != s:
                return t + step / 2
            t += step

    def fit(c: int, t: float) -> float:
        """Font height (km) for a label centred on hex c at angle t: ~0.6 em per character
        over 90% of the local run through c, and no taller than 80% of the local breadth.
        The run is then re-measured along the label's top and bottom edges (twice), so the
        whole box, not just its centre line, stays inside the state."""
        (x, y), ux, uy = pts[c], math.cos(t), math.sin(t)
        across = 2 * min(reach(x, y, -uy, ux), reach(x, y, uy, -ux))
        h, offsets = 0.8 * across, [0.0]
        for _ in range(3):
            along = min(
                2 * min(reach(x - o * uy, y + o * ux, ux, uy), reach(x - o * uy, y + o * ux, -ux, -uy))
                for o in offsets
            )
            h = min(h, 0.9 * along / (0.6 * max(len(name), 4)))
            offsets = [0.0, h / 2, -h / 2]
        return h

    # Candidates: the pole of inaccessibility and hexes nearly as deep; pick the one (and angle)
    # that fits the biggest label, a tilted label only if it is 25% bigger than a flat one.
    far = max(dist.values())
    best = None
    for c in cells:
        if dist[c] < far - 1:
            continue
        for t in angles:
            size = fit(c, t) / (1.25 if t else 1.0)
            score = (round(size), -math.hypot(pts[c][0] - mx, pts[c][1] - my))
            if best is None or score > best[0]:
                best = (score, c, t, size * (1.25 if t else 1.0))
    _, pole, angle, size = best
    px, py = pts[pole]
    return {
        "x": round(px, 1),
        "y": round(py, 1),
        "angle": round(math.degrees(angle), 1),
        "size": round(max(MIN_LABEL_KM, min(MAX_LABEL_KM, size)), 1),
    }

