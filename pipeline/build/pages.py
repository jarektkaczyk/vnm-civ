"""web/vi/index.html: the Vietnamese app page, made from web/index.html.

Every visible text and readable attribute (title, aria-label, placeholder, alt, the meta description) goes through
the catalogue (web/i18n/vi.json); `lang` becomes "vi"; relative links get a "../" so they work from /vi/; the
language switch marks VI as the current page. The page loads the same scripts: web/js/i18n.js reads <html lang>.
"""

from __future__ import annotations

import html
import re

from ..core import i18n
from ..core.paths import WEB
from ..core.store import atomic_write_text

REQUIRES: list[str] = []
PRODUCES = ["_pages"]
RUN_LAST = True

SITE_URL = "https://softonsofa.com/vnm-civ/"  # repeats web/js/app/share.js

_SKIP = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_ATTR = re.compile(r'\s(title|aria-label|placeholder|alt)="([^"]*)"')


def _plain(text: str, cat: dict) -> str | None:
    """The Vietnamese text of an HTML text or attribute value (unescaped), or None."""
    key = " ".join(html.unescape(text).split())
    if not i18n.is_text(key):
        return None
    hit = i18n.lookup(key, cat)
    return hit if isinstance(hit, str) and hit else None


def _tr(text: str, cat: dict) -> str:
    hit = _plain(text, cat)
    return text if hit is None else html.escape(hit, quote=False)


def _attr(value: str, cat: dict) -> str:
    hit = _plain(value, cat)
    return value if hit is None else html.escape(hit, quote=True)


def _tag(tag: str, cat: dict) -> str:
    tag = _ATTR.sub(lambda m: f' {m.group(1)}="{_attr(m.group(2), cat)}"', tag)
    if tag.startswith("<meta") and re.search(
            r'(name|property)="(description|og:title|og:description|og:image:alt|og:site_name|twitter:title|'
            r'twitter:description|twitter:image:alt)"', tag):
        tag = re.sub(r'content="([^"]*)"', lambda m: f'content="{_attr(m.group(1), cat)}"', tag)
    tag = re.sub(r'\s(href|src)="(?!https?:|data:|#|/|\.\./)([^"]*)"', lambda m: f' {m.group(1)}="../{m.group(2)}"', tag)
    tag = tag.replace('href="../vi/"', 'href="./"').replace('href=".././"', 'href="../"')
    if tag.startswith("<link") and 'rel="canonical"' in tag:
        tag = tag.replace(f'"{SITE_URL}"', f'"{SITE_URL}vi/"')
    if tag.startswith("<meta") and 'property="og:url"' in tag:
        tag = tag.replace(f'"{SITE_URL}"', f'"{SITE_URL}vi/"')
    if tag.startswith("<meta") and 'property="og:locale:alternate"' in tag:
        tag = tag.replace('vi_VN', 'en_GB')
    elif tag.startswith("<meta") and 'property="og:locale"' in tag:
        tag = tag.replace('en_GB', 'vi_VN')
    if tag.startswith("<html"):
        tag = tag.replace('lang="en"', 'lang="vi"')
    if 'data-lang="en"' in tag:
        tag = tag.replace(' aria-current="page"', "")
    if 'data-lang="vi"' in tag and "aria-current" not in tag:
        tag = tag[:-1] + ' aria-current="page">'
    return tag


def vietnamese_index(en_html: str, cat: dict) -> str:
    out = []
    pos = 0
    for m in _SKIP.finditer(en_html):
        out.append(_markup(en_html[pos:m.start()], cat))
        block = re.sub(r'(\ssrc=")(?!https?:)([^"]*)(")', lambda x: x.group(1) + "../" + x.group(2) + x.group(3),
                       m.group(0), count=1)
        out.append(block)
        pos = m.end()
    out.append(_markup(en_html[pos:], cat))
    return "".join(out)


def _markup(part: str, cat: dict) -> str:
    out = []
    pos = 0
    for m in _TAG.finditer(part):
        text = part[pos:m.start()]
        if text.strip():
            lead = text[:len(text) - len(text.lstrip())]
            tail = text[len(text.rstrip()):]
            text = lead + _tr(text.strip(), cat) + tail
        out.append(text)
        out.append(_tag(m.group(0), cat))
        pos = m.end()
    out.append(part[pos:])
    return "".join(out)


def build() -> None:
    cat = i18n.load_catalogue()
    en = (WEB / "index.html").read_text(encoding="utf-8")
    atomic_write_text(WEB / "vi" / "index.html", vietnamese_index(en, cat))
    print("    \u2192 web/vi/index.html")
