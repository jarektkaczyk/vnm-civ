# Vietnamese catalogue

`vi.json` maps each English source string (exact, as the code or the data file writes it) to its Vietnamese text. The browser (`web/js/i18n.js`) reads it, and `pipeline/build/pages.py` uses it to make `web/vi/index.html` from `web/index.html`. `uv run python scripts/i18n-extract.py` lists the strings that have no Vietnamese entry; `uv run python -m pipeline check` fails while any is missing.

## Rules

1. Use the glossary words below every time. Write them in the case the sentence needs.
2. Write Vietnamese with full tone marks. Keep Vietnamese place names in their official spelling with tone marks.
3. Write numbers the Vietnamese way: a dot for thousands, a comma for decimals.
4. Use "tỉnh" and "thành phố trực thuộc trung ương" for the 34 provinces and cities, and "xã, phường, đặc khu" for the units below them. There are no districts (quận, huyện) since 1 July 2025.
5. A memorial site gets neutral words, never game language.
6. A string that a native speaker has not checked yet is listed in `docs/HANDOFF.md`.

## Glossary (binding)

| English | Vietnamese | Notes |
|---|---|---|
| Lenses | Lớp bản đồ | "Chọn một lớp" |
| Advisors | Cố vấn | The council |
| Almanac | Niên giám | Sources and method pages |
| Province | Tỉnh, thành phố | Both kinds, written together |
| Town | Đô thị | |
| Gold (GRDP) | Vàng | The GRDP figure in the top bar |
| Rice | Lúa | |
| Economy | Kinh tế | Advisor |
| Population | Dân số | Advisor |
| Enterprise | Doanh nghiệp | Advisor |
| Governance | Quản trị | Advisor (PCI) |
| Farm and sea | Nông nghiệp và biển | Advisor |
| Daily life | Đời sống | Advisor |
| Land | Đất đai | Advisor |
| Resources | Tài nguyên | Power plants, ports, airports |
| Animations | Hoạt ảnh | Moving layers: "Lớp chuyển động" |
| Share (button) | Chia sẻ | |
| Search | Tìm kiếm | |
| people | người | |

## Add a string

1. Add the English text as a key in `vi.json`, in alphabetical order.
2. Write the Vietnamese text as the value, with escapes or UTF-8.
3. Run `uv run python -m pipeline build --deps pages` when the string is in `web/index.html`.
4. Run `uv run python -m pipeline check`.
