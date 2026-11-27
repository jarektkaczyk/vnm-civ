// Land advisor: national land cover, where each cover dominates and the provinces' make-up.
import { esc, fin, ratio } from "../core/util.js";
import { pct, int, count3 } from "../core/fmt.js";
import { shareBar, barList, donut, smallMultiples } from "../core/charts.js";
import { createTable } from "../core/table.js";
import { section, tiles, segmented, lensButton, sourcesHtml, topBy, frameBtn } from "../core/view.js";
import { LAND_KEYS, LAND_LABEL, LAND_COLOR, rowsHighlight } from "../core/data.js";
import { t } from "../../../i18n.js";

const LENS_OF = { forest: "forest", crop: "farmland", pasture: "farmland", developed: "developed" };
const SHORT_LABEL = { pasture: t("Grassland"), grass: t("Mountain grassland") };
// Cover names come from core/data.js; t() returns them in the page language (a no-op when already translated).
const landLabel = (k) => t(LAND_LABEL[k]);
// Escape a translated template and fill its {placeholders} with HTML.
const tHtml = (text, vars) => esc(text).replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));

export function mount(ctx) {
  const { app, data, el, link } = ctx;
  const w = app.w;
  const P = w.raw.pct;
  const owner = w.raw.owner;
  const { states } = data.levels;
  if (!P) {
    el.innerHTML = `<p class="adv-empty pad">${esc(t("No land-cover data is available."))}</p>`;
    return {};
  }

  // --- national shares and dominant cover per hex ---------------------------------------------------------------
  const sums = Object.fromEntries(LAND_KEYS.map((k) => [k, 0]));
  const dominant = new Map(LAND_KEYS.map((k) => [k, []]));
  let cells = 0;
  for (let i = 0; i < w.grid.size; i++) {
    if (!(owner[i] >= 0)) continue;
    let tot = 0, best = null, bv = 0;
    for (const k of LAND_KEYS) {
      const v = P[k]?.[i] || 0;
      tot += v;
      if (v > bv) { bv = v; best = k; }
    }
    if (tot <= 0) continue; // no land-cover samples
    cells++;
    for (const k of LAND_KEYS) sums[k] += P[k]?.[i] || 0;
    dominant.get(best).push(i);
  }
  const share = Object.fromEntries(LAND_KEYS.map((k) => [k, cells ? sums[k] / (cells * 100) : 0]));
  const other = Math.max(0, 1 - LAND_KEYS.reduce((a, k) => a + share[k], 0));

  el.insertAdjacentHTML("beforeend", tiles([
    { label: t("Forest"), value: pct(share.forest, 0), sub: t("of the land"), color: LAND_COLOR.forest },
    { label: t("Farmland"), value: pct(share.crop, 0), sub: t("crops and rice paddies"), color: LAND_COLOR.crop },
    { label: t("Built-up"), value: pct(share.developed, 1), sub: t("of the land"), color: LAND_COLOR.developed },
  ]));

  // --- composition ----------------------------------------------------------------------------------------------
  const cBody = section(el, { title: t("What covers the country"), kicker: t("Vietnam"), note: esc(t("Share of the land in each cover type, averaged over every hex. Hover a type to light up the hexes where it is the largest cover; click to keep them lit.")) });
  let pinned = null;
  const parts = [...LAND_KEYS.filter((k) => share[k] >= 0.0005).map((k) => ({ key: k, label: landLabel(k), value: share[k], color: LAND_COLOR[k], text: pct(share[k]) })), { key: "other", label: t("Other (water, bare ground)"), value: other, color: "#6c6358", text: pct(other) }].sort((a, b) => (a.key === "other") - (b.key === "other") || b.value - a.value);
  const domHighlight = (k, dim = true) => (dominant.has(k) ? { cells: new Set(dominant.get(k)), dimOthers: dim, color: LAND_COLOR[k] } : null);
  const sb = shareBar(cBody, {
    parts,
    onHover: (p) => link.hover(p && p.key !== "other" ? { ...domHighlight(p.key), color: "#fff3c4" } : null),
    onClick: (p) => pin(p.key === "other" || pinned === p.key ? null : p.key),
  });
  const pinInfo = document.createElement("div");
  pinInfo.className = "adv-brushinfo";
  cBody.appendChild(pinInfo);
  const lensRow = document.createElement("div");
  lensRow.className = "adv-row";
  for (const [id, label] of [["forest", t("Forest lens")], ["farmland", t("Farmland lens")], ["developed", t("Built-up lens")]]) {
    const b = lensButton(app, id, label);
    if (b) lensRow.appendChild(b);
  }
  cBody.appendChild(lensRow);
  function pin(k) {
    pinned = k;
    sb.setSelected(k);
    link.base(k ? domHighlight(k) : null, { frame: true });
    if (!k) { pinInfo.innerHTML = ""; return; }
    const n = dominant.get(k).length;
    const lens = LENS_OF[k] && app.lensById.get(LENS_OF[k]);
    pinInfo.innerHTML = `${tHtml(t.plural(n, { one: "{cover} is the largest cover on {count} hex ({hexShare} of the land hexes) and covers {landShare} of all land.", other: "{cover} is the largest cover on {count} hexes ({hexShare} of the land hexes) and covers {landShare} of all land." }), { cover: `<b>${esc(landLabel(k))}</b>`, count: `<b>${esc(int(n))}</b>`, hexShare: esc(pct(n / cells, 0)), landShare: esc(pct(share[k])) })}
      ${lens ? `<button type="button" class="adv-mini" data-lens="${lens.id}">${esc(t("Show the {lens} lens", { lens: t(lens.name) }))}</button>` : ""}${frameBtn()}<button type="button" class="adv-mini" data-clear>${esc(t("Clear"))}</button>`;
  }
  pinInfo.addEventListener("click", (e) => {
    if (e.target.closest("[data-clear]")) pin(null);
    const l = e.target.closest("[data-lens]")?.dataset.lens;
    if (l) app.setLens(l);
  });

  // --- per voivodeship ------------------------------------------------------------------------------------------
  const sBody = section(el, { title: t("The provinces' make-up"), note: esc(t("Each province's land by cover type. Sort by any cover; hover a province to outline it, click to open it.")) });
  const stRows = states.rows.filter((r) => LAND_KEYS.some((k) => fin(r.v[`land_${k}`])));
  const comp = (r) => `<span class="adv-minibar">${LAND_KEYS.map((k) => {
    const v = r.v[`land_${k}`];
    return fin(v) && v > 0 ? `<i style="width:${(v * 100).toFixed(2)}%;background:${LAND_COLOR[k]}" title="${esc(`${landLabel(k)} ${pct(v)}`)}"></i>` : "";
  }).join("")}</span>`;
  const domOf = (r) => LAND_KEYS.reduce((b, k) => ((r.v[`land_${k}`] ?? -1) > (r.v[`land_${b}`] ?? -1) ? k : b), LAND_KEYS[0]);
  let sortKey = "forest";
  const colsFor = (k) => [
    { key: "name", label: t("Province"), align: "l", width: "minmax(0,1.1fr)", value: (r) => r.name, text: (r) => r.name },
    { key: "comp", label: t("Land"), align: "l", width: "minmax(0,1.6fr)", value: (r) => r.v[`land_${k}`], html: comp, title: t("Sort by {cover}", { cover: landLabel(k).toLowerCase() }) },
    { key: "share", label: landLabel(k), value: (r) => r.v[`land_${k}`], html: (r) => `<span class="dot" style="background:${LAND_COLOR[k]}"></span>${pct(r.v[`land_${k}`], 0)}` },
    { key: "dom", label: t("Largest"), align: "l", width: "minmax(0,.9fr)", value: (r) => landLabel(domOf(r)), text: (r) => landLabel(domOf(r)) },
  ];
  const sortSeg = document.createElement("div");
  sortSeg.className = "adv-row";
  sBody.appendChild(sortSeg);
  segmented(sortSeg, {
    label: t("Sort by"), value: sortKey,
    options: LAND_KEYS.filter((k) => stRows.some((r) => r.v[`land_${k}`] >= 0.005)).map((k) => ({ value: k, label: SHORT_LABEL[k] || landLabel(k) })),
    onChange: (k) => { sortKey = k; table.setColumns(colsFor(k), { key: "share", dir: "desc" }); drawShape(); },
  });
  let shape = "table";
  segmented(sortSeg, { label: t("Show as"), value: shape, options: [{ value: "table", label: t("Table") }, { value: "grid", label: t("Grid") }], onChange: (v) => { shape = v; drawShape(); } });
  const tableHost = document.createElement("div");
  const gridHost = document.createElement("div");
  sBody.append(tableHost, gridHost);
  const table = createTable(tableHost, {
    caption: t("Land cover by province"), rank: true, maxHeight: 320, rows: stRows, columns: colsFor(sortKey), sort: { key: "share", dir: "desc" },
    onHover: (r) => link.hover(r ? rowsHighlight(states, [r]) : null),
    onClick: (r) => states.focus(r),
  });
  // Small multiples: one donut per voivodeship, sorted by the chosen cover.
  let grid = null;
  function drawShape() {
    tableHost.hidden = shape !== "table";
    gridHost.hidden = shape !== "grid";
    if (shape !== "grid") return;
    gridHost.innerHTML = "";
    const sorted = [...stRows].sort((a, b) => (b.v[`land_${sortKey}`] ?? -1) - (a.v[`land_${sortKey}`] ?? -1));
    grid = smallMultiples(gridHost, {
      min: 92,
      items: sorted.map((r) => ({ key: r.key, label: r.sub || r.name, sub: pct(r.v[`land_${sortKey}`], 0), row: r })),
      render: (cell, it) => donut(cell, {
        interactive: false, size: 62, thickness: 12,
        parts: LAND_KEYS.map((k) => ({ key: k, label: landLabel(k), value: it.row.v[`land_${k}`], color: LAND_COLOR[k] })),
        center: { big: pct(it.row.v[`land_${sortKey}`], 0), small: "" },
        ariaLabel: `${it.row.name}: ${LAND_KEYS.map((k) => `${landLabel(k)} ${pct(it.row.v[`land_${k}`], 0)}`).join(", ")}`,
      }),
      onHover: (it) => link.hover(it ? rowsHighlight(states, [it.row]) : null),
      onClick: (it) => states.focus(it.row),
    });
  }
  drawShape();

  el.insertAdjacentHTML("beforeend", sourcesHtml(data, ["vn_geo_worldcover"], [
    esc(t("WorldCover counts every patch with tree canopy as tree cover, so tree cover here ({share} of the land) differs from the official forest area of the Statistical Yearbook.", { share: pct(share.forest, 0) })),
    esc(t("Land cover is sampled a few times per hex, so small features (a valley's farms, a small town) blur into their surroundings.")),
  ]));

  return {
    onMapHover(h) {
      const r = h.cell >= 0 ? states.rowAtCell(h.cell) : null;
      table.setHot(r ? r.key : null);
      if (shape === "grid") grid?.setHot(r ? r.key : null);
      if (h.cell >= 0 && owner[h.cell] >= 0) {
        let best = null, bv = 0;
        for (const k of LAND_KEYS) { const v = P[k]?.[h.cell] || 0; if (v > bv) { bv = v; best = k; } }
        sb.setHot(best);
      } else sb.setHot(null);
    },
    onEscape() {
      if (pinned) { pin(null); return true; }
      return false;
    },
  };
}
