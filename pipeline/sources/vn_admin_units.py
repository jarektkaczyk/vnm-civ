"""The provincial units of Vietnam: the 63 provinces in force until 30 June 2025 and the 34 in force since 1 July 2025.

Resolution 202/2025/QH15 of the National Assembly (12 June 2025) merges whole provinces: each of the 34 units is one
or more of the 63 former provinces. The 34 codes are those of Decision 19/2025/QD-TTg (the code of the province that
holds the new administrative centre, as the GSO codes of HDX COD-AB v02 confirm). This module is a helper (no Source): vn_geo_admin and the statistics sources
import the tables from it.
"""

from __future__ import annotations

import re
import unicodedata

RESOLUTION = "Resolution 202/2025/QH15"
RESOLUTION_URL = "https://daibieunhandan.vn/print/10375832.html"  # the text in the National Assembly newspaper
# Administrative centres: the annex of Resolution 60-NQ/TW (12 April 2025), as reported by SGGP / TTXVN.
CENTRES_URL = ("https://www.sggp.org.vn/danh-sach-du-kien-ten-goi-cac-tinh-thanh-pho-va-trung-tam-chinh-tri-hanh-"
               "chinh-tinh-ly-cua-34-don-vi-hanh-chinh-cap-tinh-post790508.html")

# The 63 former provinces: GSO code, name.
FORMER = [
    ("01", "H\u00e0 N\u1ed9i"), ("02", "H\u00e0 Giang"), ("04", "Cao B\u1eb1ng"), ("06", "B\u1eafc K\u1ea1n"), ("08", "Tuy\u00ean Quang"),
    ("10", "L\u00e0o Cai"), ("11", "\u0110i\u1ec7n Bi\u00ean"), ("12", "Lai Ch\u00e2u"), ("14", "S\u01a1n La"), ("15", "Y\u00ean B\u00e1i"),
    ("17", "H\u00f2a B\u00ecnh"), ("19", "Th\u00e1i Nguy\u00ean"), ("20", "L\u1ea1ng S\u01a1n"), ("22", "Qu\u1ea3ng Ninh"), ("24", "B\u1eafc Giang"),
    ("25", "Ph\u00fa Th\u1ecd"), ("26", "V\u0129nh Ph\u00fac"), ("27", "B\u1eafc Ninh"), ("30", "H\u1ea3i D\u01b0\u01a1ng"), ("31", "H\u1ea3i Ph\u00f2ng"),
    ("33", "H\u01b0ng Y\u00ean"), ("34", "Th\u00e1i B\u00ecnh"), ("35", "H\u00e0 Nam"), ("36", "Nam \u0110\u1ecbnh"), ("37", "Ninh B\u00ecnh"),
    ("38", "Thanh H\u00f3a"), ("40", "Ngh\u1ec7 An"), ("42", "H\u00e0 T\u0129nh"), ("44", "Qu\u1ea3ng B\u00ecnh"), ("45", "Qu\u1ea3ng Tr\u1ecb"),
    ("46", "Th\u1eeba Thi\u00ean Hu\u1ebf"), ("48", "\u0110\u00e0 N\u1eb5ng"), ("49", "Qu\u1ea3ng Nam"), ("51", "Qu\u1ea3ng Ng\u00e3i"), ("52", "B\u00ecnh \u0110\u1ecbnh"),
    ("54", "Ph\u00fa Y\u00ean"), ("56", "Kh\u00e1nh H\u00f2a"), ("58", "Ninh Thu\u1eadn"), ("60", "B\u00ecnh Thu\u1eadn"), ("62", "Kon Tum"),
    ("64", "Gia Lai"), ("66", "\u0110\u1eafk L\u1eafk"), ("67", "\u0110\u1eafk N\u00f4ng"), ("68", "L\u00e2m \u0110\u1ed3ng"), ("70", "B\u00ecnh Ph\u01b0\u1edbc"),
    ("72", "T\u00e2y Ninh"), ("74", "B\u00ecnh D\u01b0\u01a1ng"), ("75", "\u0110\u1ed3ng Nai"), ("77", "B\u00e0 R\u1ecba - V\u0169ng T\u00e0u"),
    ("79", "H\u1ed3 Ch\u00ed Minh"), ("80", "Long An"), ("82", "Ti\u1ec1n Giang"), ("83", "B\u1ebfn Tre"), ("84", "Tr\u00e0 Vinh"),
    ("86", "V\u0129nh Long"), ("87", "\u0110\u1ed3ng Th\u00e1p"), ("89", "An Giang"), ("91", "Ki\u00ean Giang"), ("92", "C\u1ea7n Th\u01a1"),
    ("93", "H\u1eadu Giang"), ("94", "S\u00f3c Tr\u0103ng"), ("95", "B\u1ea1c Li\u00eau"), ("96", "C\u00e0 Mau"),
]

# The 34 units since 1 July 2025: code, name, kind ("city" = centrally run city), short code, former provinces,
# administrative centre (the town that holds the provincial authorities).
PROVINCES = [
    ("01", "H\u00e0 N\u1ed9i", "city", "HN", ["01"], "H\u00e0 N\u1ed9i"),
    ("04", "Cao B\u1eb1ng", "province", "CB", ["04"], "Cao B\u1eb1ng"),
    ("08", "Tuy\u00ean Quang", "province", "TQ", ["08", "02"], "Tuy\u00ean Quang"),
    ("11", "\u0110i\u1ec7n Bi\u00ean", "province", "DB", ["11"], "\u0110i\u1ec7n Bi\u00ean Ph\u1ee7"),
    ("12", "Lai Ch\u00e2u", "province", "LCH", ["12"], "Lai Ch\u00e2u"),
    ("14", "S\u01a1n La", "province", "SL", ["14"], "S\u01a1n La"),
    ("15", "L\u00e0o Cai", "province", "LCA", ["15", "10"], "Y\u00ean B\u00e1i"),
    ("19", "Th\u00e1i Nguy\u00ean", "province", "TN", ["19", "06"], "Th\u00e1i Nguy\u00ean"),
    ("20", "L\u1ea1ng S\u01a1n", "province", "LS", ["20"], "L\u1ea1ng S\u01a1n"),
    ("22", "Qu\u1ea3ng Ninh", "province", "QN", ["22"], "H\u1ea1 Long"),
    ("24", "B\u1eafc Ninh", "province", "BN", ["24", "27"], "B\u1eafc Giang"),
    ("25", "Ph\u00fa Th\u1ecd", "province", "PT", ["25", "26", "17"], "Vi\u1ec7t Tr\u00ec"),
    ("31", "H\u1ea3i Ph\u00f2ng", "city", "HP", ["31", "30"], "H\u1ea3i Ph\u00f2ng"),
    ("33", "H\u01b0ng Y\u00ean", "province", "HY", ["33", "34"], "H\u01b0ng Y\u00ean"),
    ("37", "Ninh B\u00ecnh", "province", "NB", ["37", "35", "36"], "Ninh B\u00ecnh"),
    ("38", "Thanh H\u00f3a", "province", "TH", ["38"], "Thanh H\u00f3a"),
    ("40", "Ngh\u1ec7 An", "province", "NA", ["40"], "Vinh"),
    ("42", "H\u00e0 T\u0129nh", "province", "HT", ["42"], "H\u00e0 T\u0129nh"),
    ("44", "Qu\u1ea3ng Tr\u1ecb", "province", "QT", ["44", "45"], "\u0110\u1ed3ng H\u1edbi"),
    ("46", "Hu\u1ebf", "city", "HUE", ["46"], "Hu\u1ebf"),
    ("48", "\u0110\u00e0 N\u1eb5ng", "city", "DNG", ["48", "49"], "\u0110\u00e0 N\u1eb5ng"),
    ("51", "Qu\u1ea3ng Ng\u00e3i", "province", "QNG", ["51", "62"], "Qu\u1ea3ng Ng\u00e3i"),
    ("52", "Gia Lai", "province", "GL", ["52", "64"], "Quy Nh\u01a1n"),
    ("56", "Kh\u00e1nh H\u00f2a", "province", "KH", ["56", "58"], "Nha Trang"),
    ("66", "\u0110\u1eafk L\u1eafk", "province", "DLK", ["66", "54"], "Bu\u00f4n Ma Thu\u1ed9t"),
    ("68", "L\u00e2m \u0110\u1ed3ng", "province", "LDG", ["68", "67", "60"], "\u0110\u00e0 L\u1ea1t"),
    ("75", "\u0110\u1ed3ng Nai", "province", "DNA", ["75", "70"], "Bi\u00ean H\u00f2a"),
    ("79", "H\u1ed3 Ch\u00ed Minh", "city", "HCM", ["79", "74", "77"], "H\u1ed3 Ch\u00ed Minh"),
    ("80", "T\u00e2y Ninh", "province", "TNI", ["80", "72"], "T\u00e2n An"),
    ("82", "\u0110\u1ed3ng Th\u00e1p", "province", "DTH", ["82", "87"], "M\u1ef9 Tho"),
    ("86", "V\u0129nh Long", "province", "VL", ["86", "83", "84"], "V\u0129nh Long"),
    ("91", "An Giang", "province", "AG", ["91", "89"], "R\u1ea1ch Gi\u00e1"),
    ("92", "C\u1ea7n Th\u01a1", "city", "CT", ["92", "93", "94"], "C\u1ea7n Th\u01a1"),
    ("96", "C\u00e0 Mau", "province", "CM", ["96", "95"], "C\u00e0 Mau"),
]

NEW_OF = {old: code for code, _, _, _, olds, _ in PROVINCES for old in olds}
FORMER_NAME = dict(FORMER)
PROVINCE_NAME = {code: name for code, name, *_ in PROVINCES}

# The two archipelagos and the unit each belongs to: the Hoang Sa special zone of Da Nang and the Truong Sa special
# zone of Khanh Hoa (Resolution 1659/NQ-UBTVQH15, 2025). Label anchors and named islands are lon/lat.
ARCHIPELAGOS = [
    {"id": "hoang_sa", "name": "Qu\u1ea7n \u0111\u1ea3o Ho\u00e0ng Sa", "name_en": "Ho\u00e0ng Sa archipelago", "province": "48",
     "label": (112.0, 16.15), "islands": [{"name": "Ph\u00fa L\u00e2m", "lon": 112.335, "lat": 16.835}]},
    {"id": "truong_sa", "name": "Qu\u1ea7n \u0111\u1ea3o Tr\u01b0\u1eddng Sa", "name_en": "Tr\u01b0\u1eddng Sa archipelago", "province": "56",
     "label": (113.9, 9.4), "islands": [{"name": "Tr\u01b0\u1eddng Sa", "lon": 111.919, "lat": 8.645},
                                         {"name": "Song T\u1eed T\u00e2y", "lon": 114.333, "lat": 11.429},
                                         {"name": "Sinh T\u1ed3n", "lon": 114.329, "lat": 9.884},
                                         {"name": "Nam Y\u1ebft", "lon": 114.366, "lat": 10.181}]},
]


def fold(name: str) -> str:
    """Lower-case ASCII key of a Vietnamese name: 'Thua Thien - Hue' -> 'thuathienhue', 'Dak Lak' -> 'daklak'."""
    s = name.replace("\u0110", "D").replace("\u0111", "d")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"^(tinh|thanh pho|tp\.?)\s+", "", s)
    return re.sub(r"[^a-z]", "", s)


# Spelling variants seen in boundary files and statistical tables (folded) -> former province code.
ALIASES = {
    "hochiminhcity": "79", "tphochiminh": "79", "hochiminh": "79", "thanhphohochiminh": "79", "saigon": "79",
    "baria": "77", "bariavungtau": "77", "thuathien": "46", "thuathienhue": "46", "hue": "46",
    "daknong": "67", "daklak": "66", "daclac": "66", "daclak": "66", "haiphong": "31", "hanoi": "01",
    "danang": "48", "cantho": "92", "hoabinh": "17", "thanhhoa": "38", "khanhhoa": "56", "quangngai": "51",
    "langson": "20", "backan": "06", "baccan": "06",
}


def former_code(name: str) -> str | None:
    """The former-province code of a name in any common spelling, or None."""
    key = fold(name)
    if key in ALIASES:
        return ALIASES[key]
    for code, nm in FORMER:
        if fold(nm) == key:
            return code
    return None


def province_code(name: str) -> str | None:
    """The code of one of the 34 units from its name in any common spelling, or None."""
    key = fold(name)
    for code, nm, *_ in PROVINCES:
        if fold(nm) == key:
            return code
    if key in ("hochiminhcity", "tphochiminh", "thanhphohochiminh"):
        return "79"
    if key in ("thuathienhue",):
        return "46"
    return None

# Positions (lon, lat) of the provincial centres that are not urban centres of their own in the GHSL Urban Centre
# Database (too small, or inside the Ho Chi Minh City urban centre). From Natural Earth populated places
# (public domain); Lai Chau, which Natural Earth lacks, from its Wikipedia article.
CENTRE_POSITIONS = {
    "Cao B\u1eb1ng": (106.268, 22.664, "Natural Earth"), "Tuy\u00ean Quang": (105.211, 21.818, "Natural Earth"),
    "Bi\u00ean H\u00f2a": (106.830, 10.970, "Natural Earth"), "T\u00e2n An": (106.417, 10.534, "Natural Earth"),
    "Lai Ch\u00e2u": (103.458, 22.396, "https://en.wikipedia.org/wiki/Lai_Ch%C3%A2u"),
}
