"""The one country setting of the energy module (sources energy_*, builder build/energy.py, web/js/ext/energy).

Change ENERGY_COUNTRY to port the module to another country map. Nothing else in the module names a country.

  iso3        ISO 3166-1 alpha-3: the Ember "ISO 3 code" and the WRI "country" column
  iso2        ISO 3166-1 alpha-2: the OpenStreetMap country area (area["ISO3166-1"=iso2][admin_level=2])
  ember_name  the Ember "Area" name, used only when a row has no ISO 3 code
  gem_names   the GEM "Country/area" names of the country
  bbox        (south, west, north, east) in degrees: the Overpass query is cut into bands of `band_deg` latitude
"""

ENERGY_COUNTRY = {
    "iso3": "VNM",
    "iso2": "VN",
    "ember_name": "Viet Nam",
    "gem_names": ["Vietnam", "Viet Nam"],
    "bbox": (8.0, 102.0, 23.5, 109.6),
    "band_deg": 2.0,
}

# Words that name the kind of plant, not the plant, per language. The plant matcher (pipeline/build/energy.py
# name_key) drops them from every name; every language applies to every country, so a port only adds words.
# Words are folded the same way as names (lower case, Latin diacritics removed, l-with-stroke to l), so they may be
# written with or without diacritics. Non-Latin letters are written as \u escapes (the code is ASCII). An entry with
# a space is a phrase ("phong dien", wind power): its words go only together. "ur" is Urdu (Pakistan): bijli ghar,
# power plant, station, solar, wind, hydro (pan bijli), project, energy, farm, thermal, dam.
ENERGY_GENERIC_WORDS = {
    "en": ["power", "plant", "station", "solar", "wind", "farm", "park", "hydropower", "hydroelectric", "hydro", "thermal", "coal", "gas", "fired", "project", "pv", "energy", "the", "of", "and", "complex", "dam", "phase", "generation", "lng", "offshore", "onshore", "nearshore", "intertidal", "floating", "cluster", "center", "centre"],
    "vi": ["nha", "may", "nhiet", "thuy", "dien", "mat", "troi", "gio", "khi", "dap", "ho", "chua", "cong", "ty", "tnhh", "giai", "doan", "va", "so", "nmd", "nmdg", "nmtd", "nmnd", "dmt", "cum", "phong dien", "trang trai"],
    "pl": ["elektrownia", "elektrowni", "elektrociep\u0142ownia", "farma", "farmy", "wiatrowa", "wiatrowe", "wiatrowych", "fotowoltaiczna", "fotowoltaiczne", "s\u0142oneczna", "wodna", "w\u0119glowa", "gazowa", "j\u0105drowa", "zesp\u00f3\u0142", "blok"],
    "th": ["\u0e42\u0e23\u0e07\u0e44\u0e1f\u0e1f\u0e49\u0e32", "\u0e1e\u0e25\u0e31\u0e07\u0e07\u0e32\u0e19\u0e41\u0e2a\u0e07\u0e2d\u0e32\u0e17\u0e34\u0e15\u0e22\u0e4c", "\u0e1e\u0e25\u0e31\u0e07\u0e07\u0e32\u0e19\u0e25\u0e21", "\u0e40\u0e02\u0e37\u0e48\u0e2d\u0e19", "\u0e42\u0e0b\u0e25\u0e32\u0e23\u0e4c\u0e1f\u0e32\u0e23\u0e4c\u0e21", "\u0e1e\u0e25\u0e31\u0e07\u0e19\u0e49\u0e33", "\u0e1e\u0e25\u0e31\u0e07\u0e07\u0e32\u0e19"],
    "ar": ["\u0645\u062d\u0637\u0629", "\u0643\u0647\u0631\u0628\u0627\u0621", "\u0627\u0644\u0643\u0647\u0631\u0628\u0627\u0621", "\u0644\u0644\u0643\u0647\u0631\u0628\u0627\u0621", "\u062a\u0648\u0644\u064a\u062f", "\u0644\u062a\u0648\u0644\u064a\u062f", "\u0637\u0627\u0642\u0629", "\u0627\u0644\u0637\u0627\u0642\u0629", "\u0644\u0644\u0637\u0627\u0642\u0629", "\u0634\u0645\u0633\u064a\u0629", "\u0627\u0644\u0634\u0645\u0633\u064a\u0629", "\u0627\u0644\u0631\u064a\u0627\u062d", "\u0631\u064a\u0627\u062d", "\u0645\u0632\u0631\u0639\u0629", "\u0627\u0644\u0643\u0647\u0631\u0628\u0627\u0626\u064a\u0629", "\u0643\u0647\u0631\u0628\u0627\u0626\u064a\u0629", "\u0645\u0634\u0631\u0648\u0639"],
    "bn": ["\u09ac\u09bf\u09a6\u09cd\u09af\u09c1\u09ce", "\u09ac\u09bf\u09a6\u09cd\u09af\u09c1\u09ce\u0995\u09c7\u09a8\u09cd\u09a6\u09cd\u09b0", "\u0995\u09c7\u09a8\u09cd\u09a6\u09cd\u09b0", "\u09b8\u09cc\u09b0", "\u09aa\u09cd\u09b0\u0995\u09b2\u09cd\u09aa", "\u09aa\u09be\u0993\u09af\u09bc\u09be\u09b0", "\u09aa\u09cd\u09b2\u09cd\u09af\u09be\u09a8\u09cd\u099f"],
    "ur": ["\u0628\u062c\u0644\u06cc", "\u06af\u06be\u0631", "\u067e\u0627\u0648\u0631", "\u067e\u0644\u0627\u0646\u0679", "\u0627\u0633\u0679\u06cc\u0634\u0646", "\u0633\u0679\u06cc\u0634\u0646", "\u0634\u0645\u0633\u06cc", "\u0648\u0646\u0688", "\u067e\u0646", "\u0645\u0646\u0635\u0648\u0628\u06c1", "\u062a\u0648\u0627\u0646\u0627\u0626\u06cc", "\u0641\u0627\u0631\u0645", "\u06c1\u0627\u0626\u06cc\u0688\u0631\u0648", "\u062a\u06be\u0631\u0645\u0644", "\u0688\u06cc\u0645"],
}

# Languages written without spaces between words: their generic words are also cut out of longer words.
ENERGY_GENERIC_CUT = ["th"]
