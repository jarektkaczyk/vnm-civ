#!/usr/bin/env python3
"""List every English string the page shows that has no Vietnamese entry in web/i18n/vi.json.

    uv run python scripts/i18n-extract.py                  # one line per missing key, with where it is used
    uv run python scripts/i18n-extract.py --json out.json  # {key: ""} (plural keys: {"one","few","many"}) to fill in
    uv run python scripts/i18n-extract.py --all            # every key, translated or not

Keys come from t("...") and t.plural(n, {...}) calls in web/js, the text fields of web/data listed in
pipeline/core/i18n.py DATA_TEXT, and the visible text of web/index.html. Exit code 1 when a key is missing.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.core import i18n  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", metavar="PATH", help="write the missing keys as a JSON template")
    ap.add_argument("--all", action="store_true", help="list every key, not only the missing ones")
    ap.add_argument("--web", default=str(ROOT / "web"), help="the site folder (default: web/)")
    args = ap.parse_args(argv)
    web = Path(args.web)
    cat = i18n.load_catalogue(web / "i18n" / "vi.json")
    keys = i18n.all_keys(web) if args.all else i18n.missing(web, cat)
    if args.json:
        out = {k: ({"one": "", "few": "", "many": ""} if v["plural"] else "") for k, v in sorted(keys.items())}
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in sorted(keys.items()):
        where = ", ".join(v["where"][:3]) + (f" (+{len(v['where']) - 3})" if len(v["where"]) > 3 else "")
        print(f"{json.dumps(k, ensure_ascii=False)}\t{where}")
    label = "keys" if args.all else "missing Vietnamese keys"
    print(f"{len(keys)} {label}", file=sys.stderr)
    return 1 if keys and not args.all else 0


if __name__ == "__main__":
    sys.exit(main())
