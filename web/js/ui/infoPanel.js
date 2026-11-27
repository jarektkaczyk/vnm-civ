// Shared building blocks for the city and state panels (both render into #city-panel).
import { compact, dollars, esc, int, money, pct, yieldValue } from "../format.js";
import { icon, glyph } from "./icon.js";
import { t, num } from "../i18n.js";

// Industry -> a "district" glyph: SVG icons i-<key> from icons.js; these emoji are only the fallback.
// Keys are the PKD sections of nation.json industries (pipeline/build/yields.py SECTIONS).
export const DISTRICT_ICON = {
  agriculture: "\u{1f33e}", mining: "\u26cf\ufe0f", manufacturing: "\u{1f3ed}", energy: "\u26a1", water: "\u{1f4a7}", construction: "\u{1f3d7}\ufe0f", trade: "\u{1f6cd}\ufe0f",
  transport: "\u{1f69a}", accommodation: "\u{1f37d}\ufe0f", information: "\u{1f4e1}", finance: "\u{1f3e6}", real_estate: "\u{1f3d8}\ufe0f", professional: "\u{1f52c}",
  admin: "\u{1f5c2}\ufe0f", public_admin: "\u{1f3db}\ufe0f", education: "\u{1f393}", health: "\u{1f3e5}", arts: "\u{1f3ad}", other: "\u{1f527}",
};

const panelEl = () => document.getElementById("city-panel");

// Yield tiles; `ranks` (optional) adds "#3 of 49" under each.
export function yieldGrid(nation, yields, ranks = null, rankOf = 0) {
  return nation.yields
    .map((y) => {
      const v = yields?.[y.key];
      const r = ranks?.[y.key];
      const label = y.key === "gold" ? t("GDP") : t(y.label);
      const name = y.key === "gold" ? t("{yield} (GDP)", { yield: t(y.label) }) : t(y.label);
      return `<div class="yield-tile" title="${esc(name)}: ${esc(t(y.description || ""))}">
        <div class="ico" style="color:${esc(y.color)}">${glyph(y, 20)}</div>
        <div class="val" style="color:${esc(y.color)}">${yieldValue(y, v)}</div>
        <div class="lbl">${esc(label)}</div>
        ${r ? `<div class="rank" title="${esc(t("Rank among the {n} provinces (1 = largest)", { n: rankOf }))}">${esc(t("#{rank} of {total}", { rank: r, total: rankOf }))}</div>` : ""}</div>`;
    })
    .join("");
}

// One "value ^ Vietnam value" row. higherIsGood: true / false / null (neutral).
export function statRow(ic, fallback, label, v, nv, fmt, higherIsGood) {
  let cmp = "";
  if (v != null && nv != null && nv !== 0) {
    const ratio = v / nv;
    const cls = Math.abs(ratio - 1) < 0.03 || higherIsGood == null ? "" : (higherIsGood ? ratio >= 1 : ratio <= 1) ? "good" : "bad";
    // Within 3% of the national value reads as level: no arrow, no colour (the colour uses the same band).
    const arrow = Math.abs(ratio - 1) < 0.03 ? "\u2248" : ratio > 1 ? "\u25b2" : "\u25bc";
    cmp = `<span class="cmp ${cls}">${arrow} VN ${fmt(nv)}</span>`;
  }
  return `<div class="stat-row"><span class="sl">${icon(ic, fallback, { size: 14 })}${esc(label)}</span><span><b>${fmt(v)}</b>${cmp}</span></div>`;
}

// Prosperity rows of a province (NSO yearbook 2025); a row whose value is missing is left out.
export function amenities(o, n) {
  const row = (ic, fb, label, v, nv, fmt, good) => (v == null ? "" : statRow(ic, fb, label, v, nv, fmt, good));
  return `
    ${row("l-income", "\u{1f4b0}", t("GRDP per person"), o.gdp_per_capita, n.gdp_per_capita, money, true)}
    ${row("l-income", "\u{1f4b5}", t("Monthly income per person"), o.income, n.income, (x) => (x == null ? "\u2013" : t("{value}/mo", { value: money(x) })), true)}
    ${row("unemployment", "\u{1f610}", t("Unemployment"), o.unemployment, n.unemployment, (x) => pct(x), false)}
    ${row("l-poverty", "\u{1f4c9}", t("Poverty rate"), o.poverty, n.poverty, (x) => pct(x), false)}
    ${row("l-degrees", "\u{1f393}", t("Human Development Index"), o.hdi, n.hdi, (x) => (x == null ? "\u2013" : num(x, 3)), true)}
    ${row("l-people", "\u2764\ufe0f", t("Life expectancy"), o.life_expectancy, n.life_expectancy, (x) => (x == null ? "\u2013" : t("{n} years", { n: num(x, 1) })), true)}`;
}

// Workforce by industry with location quotients vs. the nation ("specialisation"). limit = max rows (0 = all).
export function industries(o, nation, limit = 0) {
  const n = nation.nation;
  const total = o.employed || 1;
  const nTotal = n.employed || 1;
  let rows = Object.entries(o.jobs || {})
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);
  if (limit) rows = rows.slice(0, limit);
  if (!rows.length) return "";
  const maxShare = rows[0][1] / total;
  return rows
    .map(([k, v]) => {
      const share = v / total;
      const nShare = (n.jobs?.[k] || 0) / nTotal;
      const lq = nShare > 0 ? share / nShare : 1;
      const tip = esc(t("Share of workers is {lq}\u00d7 the share in Vietnam", { lq: num(lq, 1) }));
      const badge = lq >= 1.3 ? `<span class="lq hi" title="${tip}">\u00d7${num(lq, 1)}</span>`
        : lq <= 0.6 ? `<span class="lq lo" title="${tip}">\u00d7${num(lq, 1)}</span>` : "";
      return `<div class="ind"><span aria-hidden="true">${icon(`i-${k}`, DISTRICT_ICON[k] || "\u2022")}</span>
        <span>${esc(nation.industries?.[k] ? t(nation.industries[k]) : k)}${badge}</span><span class="n">${compact(v)} \u00b7 ${pct(share, 0)}</span>
        <div class="bar"><i style="width:${(share / maxShare) * 100}%;background:${lq >= 1.3 ? "#9fd76a" : "#c9a45c"}"></i></div></div>`;
    })
    .join("");
}

export const gdpRow = (o) =>
  o.gdp != null
    ? `<div class="stat-row"><span class="sl">${icon("y-gold", "\u{1f4b0}", { size: 14 })}${esc(t("GRDP"))}${o.gdp_year ? ` (${esc(o.gdp_year)})` : ""}</span><span><b>${money(o.gdp)}</b>${
        o.population ? `<span class="cmp">${esc(t("{value} per person", { value: money(o.gdp / o.population) }))}</span>` : ""}</span></div>`
    : "";

// " - ^ 3.4% since 2020" from growth / growth_years (provinces), compared with Vietnam in the tooltip.
// Empty when growth is missing (null means "not measured", never zero).
export function growthSpan(o, n = null) {
  if (!Number.isFinite(o?.growth)) return "";
  const yrs = Array.isArray(o.growth_years) && o.growth_years.length === 2 ? o.growth_years : null;
  const p = (g) => `${g >= 0 ? "+" : "\u2212"}${num(Math.abs(g * 100), 1)}%`;
  const period = yrs ? `${yrs[0]}\u2013${yrs[1]}` : t("the last few years");
  const tip = Number.isFinite(n?.growth)
    ? t("Population change {period}: {change} (Vietnam {national})", { period, change: p(o.growth), national: p(n.growth) })
    : t("Population change {period}: {change}", { period, change: p(o.growth) });
  const cls = o.growth >= 0 ? "good" : "bad";
  return ` \u00b7 <span class="growth ${cls}" title="${esc(tip)}">${o.growth >= 0 ? "\u25b2" : "\u25bc"} ${num(Math.abs(o.growth * 100), 1)}%${
    yrs ? ` <span class="since">${esc(t("since {year}", { year: String(yrs[0]) }))}</span>` : ""}</span>`;
}

// The count stays bold: the plural text keeps its {n} and the number goes in after escaping.
const boldCount = (text, v) => esc(text).replace("{n}", `<b>${int(v)}</b>`);
// A town says which population it shows: the urban area, or the whole city for a centrally run city.
const popText = (o) => (o.population_basis === "city" ? t.plural(o.population, { one: "{n} person in the city", other: "{n} people in the city" }, { n: "{n}" })
  : o.population_basis === "urban" ? t.plural(o.population, { one: "{n} person in the urban area", other: "{n} people in the urban area" }, { n: "{n}" })
  : t.plural(o.population, { one: "{n} person", other: "{n} people" }, { n: "{n}" }));
export const popLine = (o, extra = "") => (o.population == null ? (extra ? `<div class="cp-pop">${extra.replace(/^ \u00b7 /, "")}</div>` : "") :
  `<div class="cp-pop">${icon("pop", "\u{1f465}", { size: 16 })} ${boldCount(popText(o), o.population)}${
    o.employed != null ? ` \u00b7 ${esc(t.plural(o.employed, { one: "{n} worker", other: "{n} workers" }))}` : ""}${extra}</div>`);

/**
 * Fill and show the panel.
 * spec: {kind: "city"|"state", stripe, title, sub, headExtra, sections: [{title, html}], foot, onClose, onPedia, wire(panel)}
 */
export function showPanel(spec) {
  const panel = panelEl();
  panel.dataset.kind = spec.kind;
  const kindLabel = spec.kindLabel || (spec.kind === "state" ? t("Province") : t("Town"));
  panel.setAttribute("aria-label", `${kindLabel}: ${spec.title}`);
  panel.innerHTML = `
    <div class="sheet-grip" aria-hidden="true"></div>
    <div class="cp-head">
      <div class="stripe" style="background:${spec.stripe}"></div>
      <button class="icon-btn cp-close" aria-label="${esc(t("Close panel (Esc)"))}" title="${esc(t("Close (Esc)"))}">${icon("close", "\u2715", { size: 13 })}</button>
      <div class="cp-kind">${esc(kindLabel)}</div>
      <h2 class="cp-name">${spec.titleHtml ?? esc(spec.title)}</h2>
      ${spec.sub ? `<div class="cp-full">${spec.sub}</div>` : ""}
      ${spec.headExtra || ""}
    </div>
    ${spec.sections.filter(Boolean).map((s) => `<section class="cp-section"><h3>${esc(s.title)}</h3>${s.html}</section>`).join("")}
    <div class="cp-foot">${spec.foot || ""} <a href="#" data-pedia>${esc(t("Almanac"))}</a></div>`;
  panel.hidden = false;
  panel.scrollTop = 0;
  panel.classList.remove("dragging-sheet");
  panel.style.transform = "";
  document.body.classList.add("panel-open");
  panel.querySelector(".cp-close").onclick = spec.onClose;
  panel.querySelector("[data-pedia]").onclick = (e) => {
    e.preventDefault();
    spec.onPedia?.();
  };
  spec.wire?.(panel);
}

export function hidePanel() {
  const panel = panelEl();
  panel.hidden = true;
  panel.innerHTML = "";
  delete panel.dataset.kind;
  document.body.classList.remove("panel-open");
}

// Bottom-sheet swipe-down to close (mobile). Installed once.
export function installSheetSwipe(onClose) {
  const panel = panelEl();
  let start = null;
  panel.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" || !matchMedia("(max-width: 700px)").matches) return;
    // Only from the grip/head, or anywhere while the sheet is scrolled to the top.
    const fromHead = e.target.closest(".sheet-grip, .cp-head");
    if (!fromHead && panel.scrollTop > 0) return;
    if (e.target.closest("button, a, input")) return;
    start = { y: e.clientY, id: e.pointerId, dy: 0, head: !!fromHead };
  });
  panel.addEventListener("pointermove", (e) => {
    if (!start || e.pointerId !== start.id) return;
    start.dy = Math.max(0, e.clientY - start.y);
    if (start.dy > 6 && (start.head || panel.scrollTop <= 0)) {
      panel.classList.add("dragging-sheet");
      panel.style.transform = `translateY(${start.dy}px)`;
    }
  });
  const end = (e) => {
    if (!start || e.pointerId !== start.id) return;
    const dy = start.dy;
    start = null;
    panel.classList.remove("dragging-sheet");
    panel.style.transform = "";
    if (dy > 80) onClose();
  };
  panel.addEventListener("pointerup", end);
  panel.addEventListener("pointercancel", end);
}
