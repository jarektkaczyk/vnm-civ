// Energy extension (docs/ENERGY_PORT.md). Data: energy.json (pipeline/build/energy.py), loaded on first use.
//
// 1. Motion layer "Power plants by year" on the year axis of the shared clock (ext/motion): a plant shows from the
//    year it started until the year it retired, as a dot sized by its capacity and coloured by its technology. A
//    card above the clock bar shows the national installed capacity and the generation mix of the clock's year
//    (Ember); at the newest year the mix is the newest 12 months.
// 2. Map toggle "Power plants" (Map menu): the operating plants as medallions, drawn into the static map like the
//    other site layers, with a hover tooltip.
// The two lenses (Power capacity, Solar and wind capacity) are plain lenses in lenses.json.
import { esc } from "../../format.js";
import { num, int } from "../../i18n.js";
import { drawIcon, hasIcon } from "../../icons.js";
import { S, TECH_LABEL } from "./strings.js";

export const COLORS = {
  solar: "#f2c230", wind: "#8fd3e8", hydro: "#3b8fd9", coal: "#57514a", gas: "#e07b39", oil: "#9a6a3a",
  nuclear: "#b28be0", biomass: "#6aa84f", other: "#b9b4a8",
};
const ICONS = { solar: "r-solar", wind: "r-wind", hydro: "r-hydro", coal: "r-coal_plant", gas: "r-gas_plant", oil: "r-oil", nuclear: "r-nuclear" };
const CARD_TECHS = ["solar", "wind", "hydro", "coal", "gas"]; // the rest is summed as "other"
const SPEED = 2; // years per second at 1x
const MARKER_Z = 64; // under ports and airports (65)

// Columns of energy.json plants.rows.
const X = 0, Y = 1, TECH = 2, MW = 3, START = 4, END = 5, OP = 6, NAME = 8;

/** Dot radius in css px for a capacity in MW (unknown capacity: the smallest dot). */
export const dotPx = (mw) => (mw > 0 ? Math.min(16, 2 + 0.33 * Math.sqrt(mw)) : 1.8);
/** Whether a plant row stands in `year` (started in or before it, not retired by it). */
export const standsIn = (r, year) => r[START] != null && r[START] <= year && (r[END] == null || r[END] > year) && (r[OP] || r[END] != null);

/** The card's numbers for a year: capacity GW and generation share by card technology (null when unknown). */
export function cardFor(doc, year) {
  const nat = doc?.national;
  const out = { year, capYear: null, cap: null, mixLabel: null, share: null };
  if (!nat) return out;
  const yrs = nat.years;
  const atOrBefore = (field) => {
    for (let k = yrs.length - 1; k >= 0; k--) {
      if (yrs[k] > year) continue;
      if (CARD_TECHS.filter((tech) => nat[field][tech]?.[k] != null).length >= 3) return k;
    }
    return -1;
  };
  const sum = (field, k) => {
    const o = {};
    let other = null;
    for (const [tech, arr] of Object.entries(nat[field])) {
      const v = arr[k];
      if (CARD_TECHS.includes(tech)) o[tech] = v;
      else if (v != null) other = (other || 0) + v;
    }
    o.other = other;
    return o;
  };
  const kc = atOrBefore("capacity_gw");
  if (kc >= 0) { out.capYear = yrs[kc]; out.cap = sum("capacity_gw", kc); }
  const rec = doc.recent;
  const k = yrs.indexOf(year);
  // The newest 12 months stand for the year they end in and later; a year before or between Ember's years has no mix.
  if (rec && year >= +rec.to.slice(0, 4)) {
    const o = {};
    let other = null;
    for (const [tech, v] of Object.entries(rec.share_pct)) {
      if (CARD_TECHS.includes(tech)) o[tech] = v;
      else if (v != null) other = (other || 0) + v;
    }
    o.other = other;
    out.share = o;
    out.mixLabel = S.last12(rec.to);
  } else if (k >= 0 && Object.values(nat.share_pct).some((v) => v[k] != null)) {
    out.share = sum("share_pct", k);
    out.mixLabel = S.shareIn(year);
  }
  return out;
}

const CSS = `
.energy-card { padding: 7px 10px 8px; width: 270px; max-width: calc(100vw - 16px); font-size: 12px; line-height: 1.35; }
.energy-card[hidden] { display: none; }
.energy-card .ec-title { font-size: 14px; color: var(--gold-bright, #f0d58c); margin-bottom: 4px; }
.energy-card .ec-sub { font-size: 11px; color: var(--ink-dim, #b9ae96); margin: -3px 0 4px; }
.energy-card .ec-bar { display: flex; height: 8px; border-radius: 3px; overflow: hidden; margin: 2px 0 6px; background: rgba(255,255,255,.08); }
.energy-card table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
.energy-card th { font-weight: normal; color: var(--ink-dim, #b9ae96); text-align: right; padding: 0 0 2px 6px; font-size: 11px; }
.energy-card th:first-child { text-align: left; padding-left: 0; }
.energy-card td { text-align: right; padding: 1px 0 1px 6px; }
.energy-card td:first-child { text-align: left; padding-left: 0; white-space: nowrap; }
.energy-card .ec-sw { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; vertical-align: -1px; }
@media (max-width: 700px) {
  .energy-card { width: auto; margin: 0 8px; padding: 5px 8px 6px; font-size: 11px; }
  .energy-card .ec-title { font-size: 13px; margin-bottom: 2px; }
  .energy-card td, .energy-card th { padding-top: 0; padding-bottom: 0; }
}`;

function addCss() {
  if (document.getElementById("energy-css")) return;
  const s = document.createElement("style");
  s.id = "energy-css";
  s.textContent = CSS;
  document.head.appendChild(s);
}

const gwText = (v) => (v == null ? "-" : v > 0 && v < 0.05 ? `<${num(0.1, 1)}` : v < 10 ? num(v, 1) : int(v));
const pctText = (v) => (v == null ? "-" : `${num(v, v < 10 ? 1 : 0)}%`);

export function install(app) {
  const motion = app.motion;
  let doc = null, loading = null, motionOn = false, markersOn = false, years = [2000, 2025];
  let dated = [], markers = [], lastDrawn = [], card = null, cardYear = null;

  const startYear = () => (motion?.reducedMotion ? years[1] : Math.max(years[0], years[1] - 15));
  let preStart = null;
  const load = () => (loading ??= (preStart = startYear(), app.loadData("energy")).then((d) => {
    if (!d?.plants?.rows?.length) return;
    doc = d;
    years = d.years;
    const techs = d.techs;
    const rows = d.plants.rows.map((r) => { const c = r.slice(); c.tech = techs[r[TECH]]; return c; });
    dated = rows.filter((r) => r[START] != null);
    markers = rows.filter((r) => r[OP] && r[MW] > 0);
    // The clock took this layer's start before the data gave the year range: move it to the real start, unless
    // the link or the visitor set a time.
    if (motionOn && motion?.clock?.axis === "year" && !/[#&]t=/.test(location.hash) && Math.floor(motion.clock.t) === preStart) {
      motion.clock.seek(startYear());
    }
    app.requestDraw();
  }, (err) => console.warn("energy: energy.json failed to load", err)));

  // --- the card ------------------------------------------------------------------------------------------------
  function ensureCard() {
    if (card) return card;
    const area = document.getElementById("lens-area");
    if (!area) return null;
    addCss();
    card = document.createElement("div");
    card.className = "panel energy-card";
    card.hidden = true;
    area.insertBefore(card, document.getElementById("motion-bar") || document.getElementById("lens-dock") || null);
    return card;
  }
  function renderCard(year) {
    const el = ensureCard();
    if (!el) return;
    const show = motionOn && !!doc;
    el.hidden = !show;
    if (!show || year === cardYear) return;
    cardYear = year;
    const c = cardFor(doc, year);
    const keys = [...CARD_TECHS, "other"];
    const bar = c.share ? keys.filter((k) => c.share[k] > 0).map((k) =>
      `<span style="width:${c.share[k]}%;background:${COLORS[k]}" title="${esc(TECH_LABEL[k])}"></span>`).join("") : "";
    // A line under the title names the periods when they are not the clock's year.
    const capOff = c.capYear != null && c.capYear !== year;
    const mixOff = c.mixLabel && c.mixLabel !== S.shareIn(year);
    const sub = [capOff ? S.capIn(c.capYear) : null, mixOff ? c.mixLabel : null].filter(Boolean).join(" \u00b7 ");
    el.innerHTML = `<div class="ec-title">${esc(S.title(year))}</div>${sub ? `<div class="ec-sub">${esc(sub)}</div>` : ""}
      ${bar ? `<div class="ec-bar">${bar}</div>` : ""}
      ${!c.cap && !c.share ? "" : `<table><thead><tr><th></th><th>${esc(`${S.capacity}, ${S.gw}`)}</th><th>${esc(S.share)}</th></tr></thead>
      <tbody>${keys.map((k) => `<tr><td><span class="ec-sw" style="background:${COLORS[k]}"></span>${esc(TECH_LABEL[k])}</td>
        <td>${esc(gwText(c.cap?.[k]))}</td><td>${esc(pctText(c.share?.[k]))}</td></tr>`).join("")}</tbody></table>`}`;
  }

  // --- motion layer ------------------------------------------------------------------------------------------
  if (motion) {
    motion.register({
      id: "energy_plants",
      name: S.layer,
      data: "energy",
      axis: "year",
      get range() { return [years[0], years[1] + 0.999]; },
      get start() { return startYear(); },
      speed: SPEED,
      loop: false,
      label: (tt) => String(Math.min(Math.floor(tt), years[1])),
      status(tt) {
        const y = Math.min(Math.floor(tt), years[1]);
        return doc ? S.plants(dated.filter((r) => standsIn(r, y)).length) : "";
      },
      active: () => motionOn,
      load,
      draw(ctx, vp, tt, o) {
        if (!doc) return 0;
        const y = Math.min(Math.floor(tt), years[1]), f = Math.min(1, tt - Math.floor(tt));
        renderCard(y);
        const px = 1 / vp.s;
        const pad = 20 * px;
        let n = 0;
        lastDrawn = [];
        ctx.save();
        ctx.lineWidth = 1 * px;
        ctx.strokeStyle = "rgba(20,16,10,.75)";
        for (const r of dated) {
          if (!standsIn(r, y)) continue;
          if (r[X] < vp.x0 - pad || r[X] > vp.x1 + pad || r[Y] < vp.y0 - pad || r[Y] > vp.y1 + pad) continue;
          // A plant that starts in this year grows in over the first part of the year.
          const grow = r[START] === y && tt < years[1] + 0.001 ? Math.min(1, 0.25 + f * 2) : 1;
          const rad = dotPx(r[MW]) * grow * px;
          ctx.globalAlpha = r[START] === y ? 1 : 0.85;
          ctx.fillStyle = COLORS[r.tech];
          ctx.beginPath();
          ctx.arc(r[X], r[Y], rad, 0, Math.PI * 2);
          ctx.fill();
          if (rad > 2.5 * px) ctx.stroke();
          lastDrawn.push(r);
          n++;
        }
        ctx.restore();
        return n;
      },
      hit(mx, my) {
        let best = null, bd = Infinity;
        for (const r of lastDrawn) {
          const [sx, sy] = app.cam.toScreen(r[X], r[Y]);
          const d = Math.hypot(sx - mx, sy - my);
          if (d <= Math.max(6, dotPx(r[MW]) + 2) && d < bd) { bd = d; best = r; }
        }
        return best ? { html: tip(best) } : null;
      },
    });
    (motion.panelRows ||= []).push({ id: "energy_plants", get label() { return S.layer; }, get hint() { return S.layerHint; } });
    app.ui.addMapToggle({
      id: "energy_plants", label: S.layer, icon: "r-solar", default: false, menu: !Array.isArray(motion.panelRows),
      title: S.layerHint,
      get: () => motionOn,
      set: (v) => {
        motionOn = !!v;
        if (motionOn) load().then(() => app.requestDraw());
        else if (card) card.hidden = true;
        cardYear = null;
        app.requestDraw();
      },
    });
  }

  function tip(r) {
    const name = r[NAME] || S.unnamed;
    const bits = [TECH_LABEL[r.tech], r[MW] > 0 ? S.mw(int(r[MW])) : null,
      r[START] != null ? (r[END] != null ? S.until(String(r[START]), String(r[END])) : S.since(String(r[START]))) : null];
    return `<b>${esc(name)}</b><br>${bits.filter(Boolean).map(esc).join(" &middot; ")}`;
  }

  // --- operating plants as markers (static layer + Map menu toggle) ------------------------------------------
  const minMw = (Rpx) => (Rpx < 5 ? 400 : Rpx < 9 ? 100 : Rpx < 16 ? 30 : Rpx < 30 ? 5 : 0);
  const sizePx = (mw, Rpx) => Math.min(26, Math.max(10, 9 + 2.6 * Math.log10(Math.max(1, mw)) + Math.min(6, Rpx / 8)));
  let shown = [];
  function visibleMarkers(vp, Rpx) {
    const lim = minMw(Rpx), s = vp.s, placed = [], out = [];
    for (const r of markers) { // largest first
      if (r[MW] < lim) continue;
      if (r[X] < vp.x0 - 30 / s || r[X] > vp.x1 + 30 / s || r[Y] < vp.y0 - 30 / s || r[Y] > vp.y1 + 30 / s) continue;
      const size = sizePx(r[MW], Rpx);
      const sx = (r[X] - vp.x0) * s, sy = (r[Y] - vp.y0) * s;
      if (placed.some(([px, py, pr]) => (px - sx) ** 2 + (py - sy) ** 2 < ((pr + size / 2) * 0.8) ** 2)) continue;
      placed.push([sx, sy, size / 2]);
      out.push({ r, x: r[X], y: r[Y], size });
    }
    return out;
  }
  app.registerStaticLayer({
    id: "energy_markers", z: MARKER_Z,
    visible: () => markersOn && markers.length > 0,
    sig: () => `${markersOn}|${markers.length}`,
    draw(ctx, vp, w, o) {
      const Rpx = o.Rpx ?? vp.s * w.grid.R;
      shown = visibleMarkers(vp, Rpx);
      for (let k = shown.length - 1; k >= 0; k--) { // small on top of big
        const { r, size } = shown[k];
        ctx.save();
        ctx.translate(r[X], r[Y]);
        ctx.scale(1 / vp.s, 1 / vp.s);
        const id = ICONS[r.tech];
        if (!(id && hasIcon(id) && drawIcon(ctx, id, 0, 0, size, { bg: COLORS[r.tech] }))) {
          ctx.beginPath();
          ctx.arc(0, 0, size / 2.6, 0, Math.PI * 2);
          ctx.fillStyle = COLORS[r.tech];
          ctx.fill();
          ctx.lineWidth = 1.5;
          ctx.strokeStyle = "#c9a45c";
          ctx.stroke();
        }
        ctx.restore();
      }
    },
    hit(x, y, Rpx) {
      const s = Rpx / app.w.grid.R;
      for (const it of shown) {
        const rad = (it.size / 2) * 0.85 / s;
        if ((it.x - x) ** 2 + (it.y - y) ** 2 <= rad * rad) return it;
      }
      return null;
    },
    tooltip: (it) => tip(it.r),
  });
  app.ui.addMapToggle({
    id: "energy_markers", label: S.markers, icon: "r-solar", default: false, title: S.markersHint,
    get: () => markersOn,
    set: (v) => {
      markersOn = !!v;
      if (markersOn) load().then(() => app.requestDraw());
      app.requestDraw();
    },
  });

  app.energy = { load, cardFor: (y) => cardFor(doc, y), get doc() { return doc; } };
}
