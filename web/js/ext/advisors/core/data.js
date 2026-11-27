// The advisors' data model: "levels" (provinces, former provinces, towns) of rows with typed fields, plus the links
// between rows and the hex map (row -> highlight, cell -> row). Built once from app.data.
//
//   level = {id, label, noun, rows: [row], fields: [field], field(key), value(row, key),
//            highlight(rows, opts) -> app.state.highlight, rowAtCell(cell) -> row | null, focus(row), byKey: Map}
//   row   = {key, name, sub, full?, level, ref, v: {fieldKey: value}}
//   field = {key, label, format, unit, higher_is, source, description, lens?, group, derived?}
//
// Province fields come from states.json and from every lens whose level is "province" (lenses.json); former-province
// fields from counties.json; towns carry their population.
import { frameBox } from "./frame.js";
import { t } from "../../../i18n.js";

const LAND_KEYS = ["forest", "crop", "pasture", "grass", "shrub", "wetland", "developed"];
export const LAND_LABEL = {
  forest: t("Forest"), crop: t("Cropland"), pasture: t("Grassland"), grass: t("Mountain grassland"), shrub: t("Scrub"), wetland: t("Wetland and mangroves"), developed: t("Built-up"),
};
export const LAND_COLOR = {
  forest: "#3f7a3a", crop: "#d2c457", pasture: "#93b852", grass: "#b9b06a", shrub: "#c9a874", wetland: "#4f9a86", developed: "#9a8f9e",
};
export { LAND_KEYS };

export const GROUP_NAME = {
  people: t("People"), prosperity: t("Prosperity"), enterprise: t("Enterprise"), governance: t("Governance"),
  farm: t("Farm and sea"), life: t("Daily life"), climate: t("Climate and hazards"), land: t("Land"),
};

const F = (key, label, format, o = {}) => ({ key, label, format, unit: o.unit || null, higher_is: o.higher_is || "neutral", source: o.source || "", description: o.description || "", lens: o.lens || null, group: o.group || t("Economy"), derived: !!o.derived });

/** Column-oriented file ({columns, rows}) -> [{r, i, get(key)}]. */
function columnRows(file) {
  if (!file || !Array.isArray(file.columns) || !Array.isArray(file.rows)) return [];
  const col = Object.fromEntries(file.columns.map((k, j) => [k, j]));
  return file.rows.map((r, i) => ({ r, i, get: (k) => (col[k] == null ? null : r[col[k]] ?? null) }));
}

const LENS_FORMAT = { vnd: "vnd", usd: "usd", pct: "pct", float: "float", years: "years", int: "int" };
// Lenses that repeat a states.json field are not added twice.
const DUP = new Set(["grdp_pc", "unemployment", "pop_growth"]);

export function buildData(app) {
  const { cities = [], states = [], nation = {}, counties, resources, sources = [], lenses } = app.data;
  const w = app.w;
  const grid = w.grid;
  const owner = w.raw.owner;
  const countyOf = w.raw.county || [];
  const worldCounties = w.raw.counties || [];

  // --- cell indexes ---------------------------------------------------------------------------------------------
  const stateCells = new Map();
  const countyCells = new Map();
  for (let i = 0; i < grid.size; i++) {
    const o = owner[i];
    if (!(o >= 0)) continue;
    if (!stateCells.has(o)) stateCells.set(o, []);
    stateCells.get(o).push(i);
    const c = countyOf[i];
    if (c >= 0) {
      if (!countyCells.has(c)) countyCells.set(c, []);
      countyCells.get(c).push(i);
    }
  }
  const cellTown = new Map();
  for (const c of cities) if (c.cell != null) cellTown.set(c.cell, c);
  const srcTitle = new Map((sources || []).map((s) => [s.id, s]));
  const nat = nation.nation || {};
  const vintage = nation.vintage || "";
  const countyVintage = counties?.vintage || vintage;
  const frameCells = (cells) => {
    if (!cells || !cells.length) return false;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const c of cells) {
      const x = grid.cx(c), y = grid.cy(c);
      x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
    }
    const R = grid.R * 6;
    frameBox(app, { x0: x0 - R, y0: y0 - R, x1: x1 + R, y1: y1 + R }, { pad: 24, maxScale: 2.4 });
    return true;
  };

  // --- provinces ------------------------------------------------------------------------------------------------
  const provLenses = (lenses?.lenses || []).filter((l) => l.level === "province" && l.format !== "category" && !DUP.has(l.id));
  const stList = Array.isArray(states) ? states : [];
  const stateRows = stList.map((s, i) => {
    const cell = stateCells.get(i)?.[0];
    const v = {
      name: s.name, kind: s.type === "city" ? t("Centrally run city") : t("Province"),
      population: s.population ?? null, growth: s.growth ?? null, area_km2: s.area_km2 ?? null, density: s.density ?? null,
      gdp: s.gdp ?? null, gdp_pc: s.gdp_per_capita ?? null, unemployment: s.unemployment ?? null,
      rice: s.yields?.food ?? null, energy_mw: s.energy?.total ?? null,
    };
    for (const l of provLenses) v[`lens_${l.id}`] = cell != null ? l.values[cell] ?? null : null;
    for (const k of LAND_KEYS) v[`land_${k}`] = s.land?.[k] ?? null;
    return { key: i, name: s.name, sub: s.abbr, level: "states", ref: i, v };
  });
  const stateFields = [
    F("name", t("Province"), "text", { group: t("Name") }),
    F("kind", t("Type"), "text", { group: t("Name") }),
    F("population", t("Population"), "int", { unit: t("people"), source: "vn_nso_yearbook", group: t("People"), description: t("Average population of 2025 (preliminary).") }),
    F("growth", t("Change 2020-2025"), "signed", { unit: t("population change"), source: "vn_nso_yearbook", group: t("People"), lens: "pop_growth", description: t("Change in the average population from 2020 to 2025.") }),
    F("area_km2", t("Area"), "km2", { unit: "km\u00b2", source: "vn_nso_yearbook", group: t("Land"), description: t("Area on 31 December 2024.") }),
    F("density", t("Density"), "float", { unit: t("people / km\u00b2"), source: "vn_nso_yearbook", group: t("People"), description: t("Residents per km\u00b2, 2025.") }),
    F("gdp", t("GRDP"), "money", { unit: t("VND per year"), source: "vn_nso_yearbook", description: t("GRDP per person times the average population, 2025 estimate, current prices."), derived: true }),
    F("gdp_pc", t("GRDP per person"), "vnd", { unit: t("VND per resident"), higher_is: "good", source: "vn_nso_yearbook", lens: "grdp_pc", description: t("Gross regional domestic product per resident, 2025 estimate.") }),
    F("unemployment", t("Unemployment"), "pct", { unit: t("share of the labour force"), higher_is: "bad", source: "vn_nso_yearbook", group: t("Prosperity"), lens: "unemployment", description: t("Unemployed people as a share of the labour force at working age, 2025.") }),
    F("rice", t("Rice"), "int", { unit: t("tonnes"), source: "vn_nso_yearbook", group: t("Farm and sea"), description: t("Rice production of 2025, tonnes of paddy.") }),
    ...(resources ? [F("energy_mw", t("Mapped power"), "mw", { unit: "MW", source: "vn_osm_power", group: t("Energy"), description: t("Capacity of the power plants on the map (not every plant in the province).") })] : []),
    ...provLenses.map((l) => F(`lens_${l.id}`, t(l.name), LENS_FORMAT[l.format] || "float", { unit: l.unit ? t(l.unit) : null, higher_is: l.higher_is, source: l.source, group: GROUP_NAME[l.group] || t("Other"), lens: l.id, description: t(l.description || "") })),
    ...LAND_KEYS.map((k) => F(`land_${k}`, LAND_LABEL[k], "pct", { unit: t("share of land"), source: "vn_geo_worldcover", group: t("Land"), description: t("Share of the province's land in this cover.") })),
  ];
  const states_ = makeLevel({
    id: "states", label: t("Provinces"), noun: t("province"),
    rows: stateRows, fields: stateFields,
    highlight: (rows) => ({ states: new Set(rows.map((r) => r.ref)) }),
    rowAtCell: (cell) => (owner[cell] >= 0 ? stateRows[owner[cell]] || null : null),
    focus: (row) => app.selectState(row.ref, { fly: true }),
    cellsOf: (row) => stateCells.get(row.ref) || [],
  });

  // --- former provinces (before 1 July 2025) ----------------------------------------------------------------------
  let counties_ = null;
  const cRows = columnRows(counties);
  if (cRows.length) {
    const idxOf = new Map(worldCounties.map((c, k) => [c.geoid, k]));
    const stateByCode = new Map(stList.map((s, i) => [s.fips, i]));
    const rows = cRows.map((g) => {
      const k = idxOf.get(g.get("geoid"));
      const si = stateByCode.get(g.get("province"));
      return {
        key: g.get("geoid"), name: g.get("name"), sub: stList[si]?.name || "", level: "counties", ref: k,
        v: Object.fromEntries([["name", g.get("name")], ["state", stList[si]?.name || null], ["area_km2", g.get("area_km2")],
          ...(counties.fields || []).map((f) => [f.key, g.get(f.key)])]),
      };
    });
    const rowByWorld = new Map(rows.map((r) => [r.ref, r]));
    const cellsOf = (row) => countyCells.get(row.ref) || [];
    counties_ = makeLevel({
      id: "counties", label: t("Former provinces"), noun: t("former province"),
      rows,
      fields: [
        F("name", t("Former province"), "text", { group: t("Name") }),
        F("state", t("Province since 2025"), "text", { group: t("Name") }),
        F("area_km2", t("Area"), "km2", { unit: "km\u00b2", source: "vn_geo_admin", group: t("Land"), description: t("Area of the outline drawn on the map.") }),
        ...(counties.fields || []).map((f) => F(f.key, t(f.label), f.format, { unit: f.unit ? t(f.unit) : null, higher_is: f.higher_is, source: f.source, group: GROUP_NAME[f.group] || t("Other"), lens: f.lens || null, description: t(f.description || "") })),
      ],
      highlight: (rs) => {
        const cells = new Set();
        for (const r of rs) for (const c of cellsOf(r)) cells.add(c);
        return { cells };
      },
      rowAtCell: (cell) => (countyOf[cell] >= 0 ? rowByWorld.get(countyOf[cell]) || null : null),
      focus: (row) => {
        const cells = cellsOf(row);
        if (!frameCells(cells)) app.selectState(owner[cells[0]], { fly: true });
      },
      cellsOf,
    });
  }

  // --- towns ----------------------------------------------------------------------------------------------------
  const townRows = cities.map((c) => ({
    key: c.id, name: c.name, full: c.full || c.name, sub: (c.states || []).join("-"), level: "towns", ref: c,
    v: { name: c.name, state: stList[c.cell != null ? owner[c.cell] : -1]?.name ?? null, population: c.population ?? null,
         kind: c.centre ? t("Provincial centre") : t("Town") },
  }));
  const townByRef = new Map(townRows.map((r) => [r.ref, r]));
  const towns = makeLevel({
    id: "towns", label: t("Towns"), noun: t("town"),
    rows: townRows,
    fields: [
      F("name", t("Town"), "text", { group: t("Name") }), F("state", t("Province"), "text", { group: t("Name") }),
      F("kind", t("Type"), "text", { group: t("Name") }),
      F("population", t("Population"), "int", { unit: t("people"), source: "vn_ghsl_ucdb", group: t("People"), description: t("People living in the urban centre, 2025 estimate.") }),
    ],
    highlight: (rows, o = {}) => {
      const cells = new Set(rows.map((r) => r.ref.cell).filter((c) => c != null));
      return { cells, cities: rows.length <= (o.ringMax ?? 30) ? new Set(rows.map((r) => r.key)) : undefined };
    },
    rowAtCell: (cell) => { const c = cellTown.get(cell); return c ? townByRef.get(c) : null; },
    focus: (row) => app.selectCity(row.ref, { fly: true }),
    cellsOf: (row) => (row.ref.cell != null ? [row.ref.cell] : []),
  });

  const items = resources?.items || [];
  const typeById = new Map((resources?.types || []).map((x) => [x.id, x]));
  return {
    app, nation, nat, vintage, countyVintage, countiesOffMap: 0,
    levels: { states: states_, counties: counties_, towns },
    stateCells, countyCells, cellTown, items, typeById,
    source: (id) => srcTitle.get(id) || null,
  };
}

/** Kept for older views: names need no shortening. */
export function shortCounty(name) {
  return String(name || "");
}

function makeLevel(def) {
  const fieldByKey = new Map(def.fields.map((f) => [f.key, f]));
  const byKey = new Map(def.rows.map((r) => [r.key, r]));
  return {
    ...def,
    byKey,
    field: (k) => fieldByKey.get(k) || null,
    value: (row, k) => row.v[k] ?? null,
    numericFields: () => def.fields.filter((f) => f.format !== "text"),
    addFields(list) {
      for (const f of list) {
        if (fieldByKey.has(f.key)) continue;
        def.fields.push(f);
        fieldByKey.set(f.key, f);
      }
    },
  };
}

/** No optional files add columns in this build. */
export async function extendData(data) {
  data.extended ??= new Set();
  return {};
}

/** The highlight for a set of rows of one level, with defaults (gold outline, other land dimmed when asked). */
export function rowsHighlight(level, rows, opts = {}) {
  if (!level || !rows || !rows.length) return null;
  const one = rows.length === 1 ? rows[0] : null;
  const label = opts.label ?? (one ? (one.level === "states" ? one.name : `${one.full || one.name}${one.sub && !one.full ? `, ${one.sub}` : ""}`) : "");
  return { ...level.highlight(rows, opts), dimOthers: !!opts.dim, color: opts.color, label };
}
