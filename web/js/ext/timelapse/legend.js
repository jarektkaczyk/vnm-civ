// Shared by the time-lapse lenses (ext/timelapse): when a lens's values are
// swapped for another moment, recolour the map and redraw the legend histogram (ui/lenses.js caches one per lens).
import { lensScale } from "../../world.js";
import { rampColor, parseHex } from "../../color.js";

const BINS = 40; // as the legend histogram in ui/lenses.js

export function drawLegendHist(app, lens) {
  const cv = document.getElementById("legend")?.querySelector(".lg-hist");
  if (!cv || !lens?.ramp || app.state.lens !== lens) return;
  const dpr = window.devicePixelRatio || 1;
  const cssW = cv.clientWidth || 256, cssH = cv.clientHeight || 38;
  if (cv.width !== Math.round(cssW * dpr)) cv.width = Math.round(cssW * dpr);
  if (cv.height !== Math.round(cssH * dpr)) cv.height = Math.round(cssH * dpr);
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  const counts = new Array(BINS).fill(0);
  const scale = lensScale(lens);
  const owner = app.w.raw.owner;
  for (let i = 0; i < lens.values.length; i++) {
    const v = lens.values[i];
    if (v == null || owner[i] < 0) continue;
    const tv = scale(v);
    if (!Number.isFinite(tv)) continue;
    counts[Math.max(0, Math.min(BINS - 1, Math.floor(tv * BINS)))]++;
  }
  const max = Math.max(1, ...counts);
  const stops = lens.ramp.map(parseHex);
  const bw = cssW / BINS;
  for (let b = 0; b < BINS; b++) {
    if (!counts[b]) continue;
    const hh = Math.max(1.5, Math.sqrt(counts[b] / max) * (cssH - 2));
    const [r, g, bl] = rampColor(stops, (b + 0.5) / BINS);
    ctx.fillStyle = `rgb(${r | 0},${g | 0},${bl | 0})`;
    ctx.fillRect(b * bw + 0.5, cssH - hh, Math.max(1, bw - 1), hh);
  }
  ctx.fillStyle = "rgba(201,164,92,.45)";
  ctx.fillRect(0, cssH - 1, cssW, 1);
}

/** Recolour the map for `lens` after its values changed (only when it is the lens shown). `description` replaces the
 * legend text, so that it names the moment shown. */
export function recolour(app, lens, description) {
  if (app.state.lens !== lens) return;
  const desc = description && document.getElementById("legend")?.querySelector(".desc");
  if (desc) desc.textContent = description;
  app.setBand(app.state.band);
  app.invalidate();
  drawLegendHist(app, lens);
}

/** "Ben Tre (former), Vinh Long" for a land cell (as the map's own hex card). */
export function placeOf(app, cell, t) {
  const raw = app.w.raw;
  const o = raw.owner[cell];
  if (o < 0) return "";
  const g = raw.county[cell] >= 0 ? raw.counties[raw.county[cell]] : null;
  const st = raw.states[o];
  const county = g && st && g.name !== st.name ? t("former {name}", { name: g.name }) + ", " : "";
  return `${county}${raw.states[o].name}`;
}
