import { esc, int, popShort, compact } from "../format.js";
import { formatLensValue } from "./lenses.js";
import { glyph } from "./icon.js";
import { FOREIGN } from "../world.js";
import { t } from "../i18n.js";

const el = () => document.getElementById("tooltip");

// Terrain names come from world.json tables (Land, Lake, Hills, ...): shown in the page language.
const nameOf = (table, id) => { const n = table.find((r) => r.id === id)?.name; return n ? t(n) : n; };

export function showCellTooltip(mx, my, w, i, lens, showResources = true) {
  const raw = w.raw;
  const lines = [];
  const city = w.cityByCell.get(i);
  if (city) {
    const pop = popShort(city.population);
    const text = city.population_basis === "city" ? t("{pop} people in the city", { pop })
      : city.population_basis === "urban" ? t("{pop} people in the urban area", { pop }) : t("{pop} people", { pop });
    lines.push(`<b>${esc(city.name)}</b> <span class="muted">\u00b7 ${esc(text)}</span>`);
  }

  const wt = w.water[i];
  if (wt) {
    const depth = raw.elev[i] < 0 ? ` <span class="muted">\u00b7 ${esc(t("{depth} m deep", { depth: int(-raw.elev[i]) }))}</span>` : "";
    lines.push(`<b>${esc(nameOf(w.tables.water, wt) || t("Water"))}</b>${depth}`);
  } else {
    const cover = w.cover[i] > 0 ? nameOf(w.tables.cover, w.cover[i]) : null;
    const relief = w.relief[i] > 0 ? nameOf(w.tables.relief, w.relief[i]) : null;
    const terrain = [cover, relief].filter(Boolean).join(" \u00b7 ") || (relief ?? t("Land"));
    lines.push(`<b>${esc(terrain)}</b> <span class="muted">\u00b7 ${int(raw.elev[i])} m</span>`);
  }
  const o = raw.owner[i];
  if (o >= 0) {
    const g = raw.county[i] >= 0 ? raw.counties[raw.county[i]] : null;
    const county = g && g.name !== raw.states[o].name ? t("former {name}", { name: g.name }) + ", " : "";
    lines.push(`${esc(county)}${esc(raw.states[o].name)}`);
    if (lens) lines.push(`${glyph(lens, 13)} ${esc(t(lens.name))}: <b>${formatLensValue(lens, lens.values[i])}</b>`);
  } else if (o === FOREIGN) {
    lines.push(`<span class="muted">${esc(t("Beyond the borders (not mapped)"))}</span>`);
  }
  const res = showResources && w.resources?.byCell.get(i);
  if (res) {
    for (const it of res.slice(0, 4)) {
      const ty = w.resources.typeById.get(it.type);
      const num = it.value == null ? "" : Math.abs(it.value) < 1e6 ? int(it.value) : compact(it.value);
      const val = num ? ` \u00b7 ${num}${ty.unit ? " " + esc(t(ty.unit)) : ""}` : "";
      const kind = it.name && it.name !== ty.name ? ` <span class="muted">\u00b7 ${esc(t(ty.name))}${val}</span>` : `<span class="muted">${val}</span>`;
      lines.push(`<span style="color:${esc(ty.color || "#efe4c6")}">${glyph(ty, 13)}</span> ${esc(it.name || t(ty.name))}${kind}`);
    }
    if (res.length > 4) lines.push(`<span class="muted">${esc(t("+{n} more", { n: res.length - 4 }))}</span>`);
  }
  if (city) lines.push(`<span class="muted">${esc(t("Click to open the town"))}</span>`);
  else if (o >= 0) lines.push(`<span class="muted">${esc(t("Click to open {name}", { name: raw.states[o].name }))}</span>`);
  show(mx, my, lines.join("<br>"));
}

/**
 * A tooltip with ready-made content: a string is HTML (escape any data yourself with format.js esc), {text} is
 * plain text. Used for registered static layers' tooltip(item).
 */
export function showHtmlTooltip(mx, my, content) {
  if (content == null || content === "") return hideTooltip();
  const html = typeof content === "string" ? content : esc(content.text ?? "");
  show(mx, my, html);
}

export function showCityTooltip(mx, my, city) {
  show(mx, my, `<b>${esc(city.full)}</b><br><span class="muted">${esc(t("Click to open the town"))}</span>`);
}

function show(mx, my, html) {
  const tip = el();
  tip.innerHTML = html;
  tip.hidden = false;
  const r = tip.getBoundingClientRect();
  tip.style.left = Math.max(4, Math.min(window.innerWidth - r.width - 8, mx + 16)) + "px";
  tip.style.top = Math.max(4, Math.min(window.innerHeight - r.height - 8, my + 16)) + "px";
}

export function hideTooltip() {
  el().hidden = true;
}
