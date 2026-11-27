"""Check of the Vietnamese catalogue (web/i18n/vi.json): every English string the page shows must have a Vietnamese entry.

Not a builder (no build()): pipeline check discovers check() and runs it after the contract checks. The keys come
from pipeline/core/i18n.py: t("...") and t.plural() calls in web/js, the DATA_TEXT fields of web/data and the visible
text of web/index.html. scripts/i18n-extract.py prints the same list with where each key is used.
"""

from __future__ import annotations

from pathlib import Path

from ..core import i18n


def check(web_dir: Path) -> list[tuple[str, str]]:
    web = Path(web_dir).parent  # web_dir is web/data
    path = web / "i18n" / "vi.json"
    if not path.exists():
        # A synthetic dataset (tests) has no site around it; the real site always ships the catalogue.
        return [("NOTE", "no web/i18n/vi.json next to this data folder; translation check skipped")]
    cat = i18n.load_catalogue(path)
    out: list[tuple[str, str]] = []
    keys = i18n.all_keys(web)
    miss = i18n.missing(web, cat)
    if miss:
        sample = "; ".join(f"{k!r} ({v['where'][0]})" for k, v in sorted(miss.items())[:8])
        out.append(("FAIL", f"{len(miss)} of {len(keys)} English strings have no Vietnamese entry "
                            f"(scripts/i18n-extract.py lists them): {sample}"))
    else:
        out.append(("PASS", f"all {len(keys)} English strings have a Vietnamese entry"))
    probs = i18n.placeholder_problems(cat)
    if probs:
        out.append(("FAIL", f"{len(probs)} entries break placeholders or add HTML: {'; '.join(probs[:5])}"))
    unused = [k for k in cat if not k.startswith("_") and k not in keys]
    if unused:
        out.append(("NOTE", f"{len(unused)} catalogue entries are not used any more (e.g. {unused[0]!r})"))
    return out
