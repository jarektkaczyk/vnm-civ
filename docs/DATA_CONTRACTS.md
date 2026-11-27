# Data contracts (v2, Vietnam)

The pipeline (Python) and the browser (web/js) agree on these files in `web/data/`. Change a contract here first, then
on both sides. All coordinates are **map km**: Albers equal-area (`lat1=10, lat2=20, lat0=15, lon0=106`), origin
top-left, y **down** (see `pipeline/core/geo.py`). Per-cell arrays have length `grid.cols * grid.rows`, with index
`row * cols + col` (pointy-top, odd-r layout, `pipeline/core/hexgrid.py` and `web/js/hex.js`). `null` means "no data";
a real zero is `0`.

## Pipeline conventions

* **Sources** (`pipeline/sources/*.py`) are discovered automatically: any `Source` subclass with `info = SourceInfo(...)`.
  `process()` returns a dict; it may include `"vintage"` and `"_files"` (the raw files it used; the Almanac cites only
  those). Helpers without a Source (`vn_admin_units`, `_pdf`, `_raster`, `_xlsx`, `_osm`) are ignored by the registry.
* **Builders** (`pipeline/build/*.py`) are discovered automatically: a module with `REQUIRES`, `PRODUCES` and `build()`.
  They run in dependency order. Interims made by builders start with `_`.
* **Units.** world `states` are the 34 provinces and centrally run cities of 1 July 2025 (`fips` = the unit's GSO code,
  `abbr` an ASCII short code, `name`, `type` "province" or "city"). world `counties` are the 63 former provinces
  (`geoid` = GSO code, `province` = the code of the province it belongs to, `type` "former"). The `_world` interim holds
  `grid`, `projection`, `owner`, `county`, `county_samples`, `states`, `counties`, `water`, `cover`, `pct`, `notes`,
  `gminy_without_samples` and `dissolve_check` (`{hexes, agree, by_province}`: hexes whose province in the dissolve
  matches the published 34-province outlines).
* **Land.** A hex sample is land when it lies in the OpenStreetMap land polygons (`vn_osm_land`); its owner is the
  former province (or foreign country) whose outline covers it; land in no outline takes its neighbours' owner.
* **Builder checks.** Any module in `pipeline/build/` may define `check(web_dir) -> [(level, message)]`; `pipeline
  check` runs them after its own checks. A missing output is a NOTE.
* **Languages.** English is the source language; `web/i18n/vi.json` maps each English string to Vietnamese. The data
  fields that are translated are listed in `pipeline/core/i18n.py` `DATA_TEXT`. `pipeline check` fails while a key has
  no Vietnamese entry; `scripts/i18n-extract.py` lists them. `pipeline/build/pages.py` writes `web/vi/index.html`.
* **Dates are ISO** in every data file; the browser formats them per language.

## world.json

As the engine's v2 world (owner, county, elev, elev_max, water, relief, cover, pct, tables, states, counties, rivers,
lakes, spits), plus:

```jsonc
"archipelagos": [{"id": "hoang_sa", "name": "Qu\u1ea7n \u0111\u1ea3o Ho\u00e0ng Sa", "name_en": "Hoang Sa archipelago",
                  "state": 20,                  // index of the province it belongs to (Da Nang; Truong Sa: Khanh Hoa)
                  "x": 1059.0, "y": 791.0,      // label anchor, map km
                  "marks": [{"x": 1060.1, "y": 788.2, "size_km": 1.9, "reef": false, "name": "Ph\u00fa L\u00e2m"}]}]
```

* `owner`: -1 water, -2 foreign land (China, Laos, Cambodia, Thailand), >= 0 index into `states`.
* Cover ids are fixed (0 none ... 11 ice); the names are Vietnam's: 1 Broadleaf forest, 2 Pine forest, 3 Mixed forest,
  5 Mountain grassland, 6 Grassland, 7 Farmland, 8 Wetland and mangroves.
* `rivers[].name`: Vietnamese inside Vietnam (curated points on the main stems), Natural Earth names outside.

## coast.json (lazy, close zoom)

`{version, vintage (OSM land polygon file date), sources, rules, rings: [[x0, y0, ...]], lines: [[x0, y0, ...]]}`: the
OSM land polygons near Vietnam and in the archipelagos, simplified to 30 m. `rings` are filled (even-odd) over the sea
hexes; `lines` are the same outlines without the seams where the source splits polygons on whole degrees.

## hubs.json (lazy, close zoom)

`{version, vintage, sources, rules, aerodromes: [{name, iata, rings}], runways: [{ref, width_m, line}], ports: [{name,
rings}]}` in map km, from OSM (`vn_osm_hubs`).

## cities.json

Towns: every GHSL urban centre (R2024A, population 2025) and the administrative centre of every province.

```jsonc
{"id": "uc5239", "name": "H\u1ed3 Ch\u00ed Minh", "full": "H\u1ed3 Ch\u00ed Minh, H\u1ed3 Ch\u00ed Minh", "states": ["HCM"], "province": "79",
 "kind": "town", "centre": true, "capital": false, "city_view": false, "metro": false,
 "x": 497.4, "y": 1426.8, "cell": 32547, "population": 14557830, "yields": {}, "jobs": {}}
```

`population` is `null` for a provincial centre that is not an urban centre of its own. `cell` is a land cell of Vietnam,
unique where possible.

## states.json

One entry per world `states` entry, same order: `fips`, `abbr`, `name`, `type`, `capitals: [{name, role: "centre"}]`,
`capitals_ref`, `former` (GSO codes of its former provinces), `cells`, `land` (mean `pct` as 0..1 fractions), `label`,
`energy` (`{unit: "MW", total, by_type, sites, note}` from resources.json, mapped sites only), and the economic shape:
`population` (average 2025), `pop_series` (2020-2025), `growth` (2020 to 2025), `area_km2`, `density`, `urban`, `gdp`
(GRDP per capita x average population, VND), `gdp_year`, `gdp_per_capita`, `grdp_growth`, `yields: {gold, food}`,
`unemployment`, `income` (VND per month), `poverty`, `hdi`, `life_expectancy`, `fdi_musd`, `enterprises_per_1000`,
`ranks`. Shares are 0..1 fractions; money is in VND unless the key ends in `_usd` or `_musd`.

## nation.json

`{vintage, year, population_date, gdp_vintage, years, nation: {economic shape of the country}, yields: [{key, icon,
emoji, label, color, unit ("vnd" | "usd" | "t" | "workers"), banner (false: not drawn on town banners),
description}], industries: {}}`. Yields: Gold = GRDP, Rice = rice production in tonnes.

## lenses.json

```jsonc
{"vintage": "...", "groups": [{"id": "people", "name": "People", "icon": "..."}],
 "cells": [int],                // the land cells of Vietnam; every lens's values follow this order
 "lenses": [{"id": "grdp_pc", "group": "prosperity", "name": "GRDP per person", "short_name": "...",
             "icon": "l-income", "emoji": "", "unit": "VND per resident",
             "format": "int|vnd|usd|pct|float|years|category", "scale": "log|linear", "domain": [lo, hi],
             "ramp": ["#..."], "higher_is": "good|bad|neutral", "source": "vn_nso_yearbook",
             "description": "...", "note": "optional legend caveat", "level": "province|former|hex",
             "values": [number|null]}]}   // one per entry of `cells`; the browser spreads them over the grid
```

`level` says where a value comes from: a province figure on every hex of the province, a former-province figure
(2019 census, Global Forest Watch) on every hex of the former province, or a per-hex figure (land cover, WorldPop,
night lights, rainfall, typhoons). Domains are the 2nd-98th percentile of hexes; diverging ramps are centred on 0.

## counties.json

The 63 former provinces, column-oriented: `{vintage, fields: [{key, label, format, unit, higher_is, source,
description, level, group}], columns: ["geoid", "name", "type", "province", "state", "population_5plus_2019",
"area_km2", "migration_2019", "in_migrants_2019", "out_migrants_2019", "cells"], rows: [[...]]}`.

## resources.json

The engine's shape (`version`, `vintage`, `sources`, `types`, `items`, `summary`, `rules`): every OSM power plant with a
recorded output of 30 MW or more, by source (coal, gas, hydro, solar, wind, biomass). Item `value` is MW.

## infrastructure.json (eager)

`{version, vintage, sources, rules, road_classes: [motorway (expressway), trunk (national highway)], rail_tiers,
roads: [[cell a, cell b, class, ref]], rail: [[cell a, cell b, tier]], ports: [], airports: [{id, name, icao, iata,
rank, size, passengers: null, x, y, cell, state}], totals}`. Lines are sampled every 2.5 km and snapped to links between
neighbouring hexes.

## typhoons.json (lazy, motion layer)

`{version, vintage, sources, rules, years: [1981, last], typhoon_kt: 64, storms: [{id, name, season, year, peak_kt,
pts: [x, y, wind_kt or -1, year fraction, ...]}]}`: every storm since 1981 whose track crosses the map, 6-hourly.

## timelapse.json (lazy)

`{version, vintage, sources, rules, nightlights: {years: [2014 ... 2024], cells: [int], values: [[per cell] per year]}}`.

## sources.json

The bibliography, one entry per source: `id, title, publisher, homepage, license, description, used_for, vintage,
files: [{file, url, retrieved, sha256, bytes}]`.

## Motion layers (browser)

Animated map layers share one clock (`web/js/ext/motion/`, installed first and exposed as `app.motion`). A layer's
static art (arcs, routes) stays a static layer in the cached map; the moving part is a motion layer drawn every frame in
one overlay (z 92, under the city banners).

```js
app.motion.register({
  id: "typhoons",               // also the toggle id (the layer registers its own toggle with app.ui.addMapToggle, menu: false)
  name: t("Trains"),            // optional: the name the Almanac shows (the toggle label)
  data: "typhoons",             // optional: the web/data file whose rules, sources, vintage and attribution the Almanac shows
  axis: "day",                  // "day" | "hour" | "month" | "year" | "live": what the clock counts for this layer
  range: [0, 86400],            // day: seconds; hour: hour index (app.motion.hour("2026-01-18T00:00"));
                                // month: month index (app.motion.month("2016-01")); year: 1995..2025; live: null.
                                // May be a getter (a range that depends on the data, read every frame).
  step: 60,                     // optional: the scrubber snaps to it
  speed: 1440,                  // axis units per real second at 1x (day: 1440 = 24 h in 60 s)
  start: 23400,                 // optional: the clock value when the layer first takes the clock (default range[0])
  loop: true,                   // optional: wrap at the end (default true on "day"); else play stops on the last value
  background() { return true; },// optional: while true, the layer takes the clock only when no other motion layer is on
                                // (a layer on only by default, so a lens link keeps its own clock)
  z: 10,                        // optional: draw order among motion layers
  label(t) { return "08:15"; },             // the clock text, localized
  status(t) { return "8,492 permits"; },    // optional: a running count beside the scrubber, localized
  active() { return on; },                  // is the layer on (read every frame)
  load() { return Promise; },               // lazy data load, called once on first activation
  draw(ctx, vp, t, o) { return dotsDrawn; },// per frame; ctx in world km; vp = {x0, y0, x1, y1, s, cam, dpr};
                                            // o = {Rpx, lens, dpr, s, cam}; return the number of dots drawn
  hit(mx, my) { return {html} | null; },    // optional hover card; screen css px; html is escaped by the layer
  filter(sel) {},                           // optional: the "select" payload ({kind: "city", city} | {kind: "state", ...}
                                            // | null) when the selection changes or the layer turns on
});
app.motion.clock    // {t, axis, layer, playing, speed (1 | 4 | 16), play(), pause(), toggle(), seek(t), setSpeed(k), axisOf(id)}
app.motion.particles(path, {slots, speed, shape: "dot" | "wagon", seed, dir, offset, size, color, cars})
  // -> {len, slots, travel, bbox, at(d), draw(ctx, vp, t, {density, alpha, dir, size, color, cars, gap, offset}) -> dots}
app.motion.month("2018-06") -> 24221;  app.motion.monthIso(24221) -> "2018-06";  app.motion.hhmm(29700) -> "08:15"
app.motion.hour("2026-01-20T23:00") -> 491375;  app.motion.hourIso(491375) -> "2026-01-20T23:00"
  // hour axis: whole hours since 1970-01-01T00:00 on the data's own wall clock (no time zone, no DST)
app.motion.layers() -> [{id, name, data, axis, on, loaded, t}];  app.motion.stats() -> {frames, dots, drawMs}
```

* **Clock.** One clock bar (play/pause, time label, scrubber, the layer's `status`, speed 1x/4x/16x) sits above the lens
  dock while any motion layer is on. It follows the axis of the most recently enabled layer; layers on another axis hold
  their last frame. Each axis keeps its own value, so switching back resumes where it was. `clock.speed` is the multiplier
  of each layer's `speed`. A day layer loops; a time-lapse stops on its last value and the play button replays it.
* **Frames.** Clock time comes from `performance.now()` (frame gaps are capped at 0.25 s). While a motion layer is on
  and the clock plays, the overlay asks main for the next frame; it stops when the clock pauses, when no motion layer is
  on and while the tab is hidden. A fake clock (Playwright `page.clock`) drives it frame by frame.
* **Reduced motion.** With `prefers-reduced-motion: reduce` nothing plays by itself: the layer draws one still frame at
  its `start` and the play button works on demand.
* **URL.** `#t=` keeps the clock value in the axis's own form: `08:15` (day), `2026-01-20T23:00` (hour), `2018-06`
  (month), `2019` (year). It is
  written when the clock is paused, sought or stops, never while it plays (so a playing clock adds no history entries).
  The layers that are on stay in `layers=`. A link with `t=` opens paused at that value.
* **particles.** A dot's place is a pure function of `t`, so pause and scrub are exact. `slots` dots are spread along the
  path; `density(tDepart)` (0..1, or a number) says how many slots carry a dot for trips that left at `tDepart`, so a dot
  appears or vanishes only at the path ends. Sprites are cached per shape, colour, size and device scale; dots are drawn
  in screen pixels and the path is culled by its bounding box.
* **Budget.** At most about 3,000 moving dots and 60 fps on a mid-range phone (390x844, 4x CPU throttling in headless
  Chromium). Use level of detail by zoom (fewer cars per train, fewer routes at the country view) and cull to `vp`.
* **Animations panel.** An "Animations" button in the lens dock, right after the Map button, with the count of animations
  that are on. Its panel (`ext/motion/panel.js`) lists the motion layers under "On the map" (`typhoons`) and the
  time-lapse lenses under "Over time" (`nightlights`). Esc closes it and returns the focus to the button.
* **Hover.** A static layer `motion-hit` (z 86, draws nothing) asks the active motion layers' `hit()`, newest first.
* **Layers now.** `typhoons` (year, 1981 to the newest season; `ext/typhoons`, data `typhoons.json`) and the lens layer
  `nightlights-years` (year, 2014 to 2024; lens `nightlights`, data `timelapse.json`), which swaps the lens's `values`
  for the year on the clock and recolours the map only when the year changes.
* **Almanac.** The "Moving layers" page lists every registered layer by `name`, with the `rules`, `sources` and
  `vintage` of its `data` file (loaded on demand).


## Browser module boundaries (web/js)

* `world.js`: `prepareWorld(world, cities, extras) -> w` with `w.grid`, `w.raw`, `w.stateColor[]`, `w.cityByCell: Map<cell, city>`;
  `applyLens(w, lens, band = null)` sets `w.colors`/`w.rgb`; exports `WATER = -1`, `FOREIGN = -2`.
* `camera.js`: `Camera` with `fit()`, `toScreen()`, `toWorld()`, `zoomAt()`, `panBy()`, `centerOn()`, `flyTo(x, y, scale, ms)`,
  `step(dt) -> bool stillMoving`, `view()`.
* `render/*`: map drawing and banners. `main.js` owns input, state and wiring. `ui/*` owns DOM panels.
* The `state` object (owned by `main.js`, read by `render/*`): `cities`, `lens` (a lenses.json lens or null = terrain),
  `band` (`[t0, t1]` in normalised lens units 0..1, or null: cells outside are dimmed, see `applyLens`), `hoverCell`,
  `selectedCity` (a city object or null), `selectedState` (a state index, abbr, fips or `{index|abbr|fips}`, or null;
  resolved with `world.js` `stateIndex(w, ref)`), `showResources`.
* `render/snapshot.js`: `renderToCanvas(target, cam, w, state, nation, opts) -> {cam, hits}` draws a full frame off-screen
  (share images, OG cards) without touching the on-screen cache. `target` is a canvas, OffscreenCanvas or 2D context;
  `opts`: `banners = true`, `overlay = true`, `dpr = 1`, `fit = "contain"|"cover"|"same"`, or an explicit `scale`, `x`, `y`.

## Browser extension API (window.__app; main.js "extension API", app/api.js)

Extensions live in `web/js/ext/<name>/index.js` and export `install(app)`; `ext/index.js` loads `motion` (the shared
clock of the animated layers, installed first; see "Motion layers"), `advisors`, `layers` (roads, rail, ports and
airports), `coast` (the OSM coastline and the airport and port areas at close zoom, and the archipelago labels),
`timelapse` (night lights by year) and `typhoons` (storm tracks year by year). The API:

**Data.**
* `app.data.<name>`: the core files (`world`, `cities`, `states`, `nation`, `lenses`, `resources`, `sources`) are loaded
  before anything runs. Optional files: `undefined` until loaded, `null` when missing (404) or invalid.
* `app.loadData(name) -> Promise<data | null>`: loads `data/<name>.json` once (cached promise; later calls return the same
  promise) and sets `app.data[name]`. Emits `"data"` `{name, data}` when it arrives. `infrastructure`, `military`,
  `wonders`, `trade` are requested automatically right after the first frame; `citizens`, `districts`, `disasters` (and
  `counties`) only when something calls `loadData`. `app.loadCounties()` = `app.loadData("counties")`.

**Static map layers** (art that belongs in the cached map, drawn once per cache render):

```js
const off = app.registerStaticLayer({
  id: "roads",                 // unique; registering the same id again replaces the layer
  z: 55,                       // where it draws among the built-in steps (app.layerZ / render/map.js Z)
  draw(ctx, vp, w, o) {},      // required. ctx starts in world km (saved/restored around the call)
  visible() { return on; },    // optional; false = not drawn, not hit-tested (part of the cache key)
  sig() { return "v1"; },      // optional; any string that changes when the art must re-render (cache key)
  minRpx: 6, maxRpx: Infinity, // optional zoom range in hex radius css px (drawn when minRpx <= Rpx < maxRpx)
  hit(xKm, yKm, Rpx) { return item | null; },   // optional hover / click test, pointer in world km
  tooltip(item) { return "<b>html</b>" | {text: "plain"} | null; },  // optional; a string is HTML: escape data yourself
  click(item, ev) { return true; },             // optional; true consumes the click (see below)
  warm(ctx, vp, w, o) {},      // optional; paint sprites for vp's zoom in idle time (stamps may land anywhere)
  snapshot: true,              // default true: drawn into share images too
});
off();   // or app.unregisterStaticLayer("roads" | layer)
```

* `o` = `{Rpx, s, dpr, lod, lens, selectedCity, showResources, snapshot, app, cells, range: {r0, r1, c0, c1},
  world(), screen(), toScreen(x, y) -> [css px]}`. `cells` are the visible cell indices; `o.screen()` switches ctx to
  screen css px of the cache canvas (use `o.toScreen`), `o.world()` back. Use sprites (`render/art/sprites.js`
  getSprite/drawSprite) for anything richer than a few paths.
* Built-in z steps: `WATER 10`, `LAND 20` (land tiles), `GRID 30`, `GLYPHS 40` (terrain), `RIVERS_BORDERS 50`, `CITIES 60`
  (city tiles), `FOG 70` (edge mist), `RESOURCES 80` (screen-space icons), `LABELS 90` (state names). A layer with z
  between two steps draws after the lower one; equal to a step = right after it. Suggested slots: 45 terrain
  improvements, **55 roads and rail**, 58 restricted ground / protected land hatching, **65 sites** (ports, airports,
  forts, wonders, plaques), **85 trade routes** (above resources, under state names).
* The cache key includes every layer's id, `visible()` and `sig()`, so toggling or restyling re-renders the cache and
  nothing else does. Errors in `draw`/`hit`/`sig`/... are logged once per layer and the layer is skipped.
* **Performance**: nothing may animate continuously (an idle map draws no frames); keep each layer under ~3 ms per cache
  render at typical zooms (time it with `drawStatic(..., {layers: app.staticLayers(), timings: T})`: it reports
  `layer:<id>`); precompute geometry once (not per draw); cull to `vp`.
* `app.staticLayers()` lists the registered layers; `app.hitLayer(mx, my)` (screen css px) -> `{layer: id, item} | null`.

**Hover and click.** The hover tooltip asks the layers (highest z first, only those drawn at the current zoom) after the
city banners: the first non-null `hit()` wins and its `tooltip(item)` is shown (the cell tooltip otherwise). The
`"hover"` event payload is `{cell, city, resource, x, y, layer, item}` (`layer` = id or null). A click builds
`ev = {cell, city, resource, state, x, y, pointerType, layer, item}`; outside a mode the layer's `click(item, ev)` goes
first (true consumes it), then the `"mapclick"` handlers, then the default (select city/state). While a mode is active
(City View, advisors) the `"mapclick"` handlers go first and the layer's `click` only after them.

**Map toggles.** `app.ui.addMapToggle({id, label, icon, get() -> bool, set(on), title?, default?, menu?}) -> remove()`: a switch
in the "Map" menu next to the Resources toggle in the lens dock (one button + a small menu, so it fits phones). `set` is
yours (flip the state your layer's `visible()` reads); main redraws. The hash key `layers` lists the switches that are on
(`#layers=roads,rail,military`, `layers=none`) and is written only while some switch differs from its default; switches
added after load are set from it, and ids whose extension has not loaded yet stay in the URL. `menu: false` keeps the
switch and its `layers=` entry but leaves it out of the Map menu and its count (the motion layers: the Animations panel
lists them). Main emits `"maptoggle"` after any switch changes. `app.ui.mapToggles()` -> `[{id, label, icon, menu, on}]`. `app.ui.setMapToggle(id, on) -> bool` switches one from code exactly as the menu would (redraw,
hash), e.g. an advisor's "show roads, rail and forts" button; false if no toggle has that id (yet).

**URL.** Core keys: `lens`, `city` (cities.json `id`), `state`, `at`, plus extension
keys (`advisor`, `layers`, ...).
* `#state=` accepts the province code (`48`), its abbr (`DNG`) or its name; a link keeps the form it was opened
  with.
* `at=x,y,z`: `x`, `y` = the map-km point at the centre of the screen (rounded), and `z` = **log2(camera scale /
  home-fit scale)**, the zoom relative to the "whole country fits" view: `0` = home framing, `1` = twice as close,
  negative = zoomed out past it. It is relative so a link frames the same area on any screen size; it is *not* the
  absolute scale (css px per km) that `app.flyTo(x, y, scale)` and `camera.scale` use. Convert with
  `scale = fitScale x 2^z`. `at` is written only once the user (or an extension) has moved the camera.
* When the hash is written: during a fly-to the link names the **destination** right away (within one 350 ms debounce
  of the flight starting); after a pan or wheel zoom it catches up 350 ms after the camera settles; `app.setMode`
  writes it on the next task. Lens, selection and mode changes push a history entry (Back undoes them); camera moves
  replace the current one. `app.hash.flush()` writes immediately (Share calls it before copying).

**Optional state and debug handles** (not data contracts; don't rely on them from other extensions without asking):
* `state.cityBadges`: an optional `Map<city id, {label, color: "#rrggbb"}>` that `render/banners.js` reads to draw a
  city-type tab on banners that show their yield row. Filled by `ext/cityView` from districts.json; absent = no tabs.
* `app.cityView.model`: read-only getter on the City View's current model (debugging).
* `app.mapArt = {model, on, layers}`: added by `ext/layers` for debugging. `model` holds `installations`, `ports`,
  `airports`, `wonders`, each item `{data (the json row), cell, x, y}`. The layers' hit items have the shape
  `{kind: "fort"|"range"|"port"|"airport"|"wonder"|"route", data}` (route items: `data.route` with `a`/`b`); the
  advisors rely on that shape for map-to-dashboard links, so keep it.

**Who reads which fields.** The advisors read every counties.json column after `cell`, military.json `states`, districts.json
`cities` and `counties`, and citizens.json `cities`; the City View reads citizens.json, districts.json, military.json
`cities`, trade.json zones and infrastructure.json `cbsa`. Update `web/js/ext/advisors` and `web/js/ext/cityView`
when renaming a field in those files.

**Lenses.** Legend ticks print numbers only (plus short units: %, the dong sign, min, /km2); a longer `unit` is printed once under
the ticks, so keep `unit` a plain phrase ("adherents per 100 residents"), not part of the number. `lens.note` is shown in the legend; `format: "category"` lenses get a swatch legend (see lenses.json).
