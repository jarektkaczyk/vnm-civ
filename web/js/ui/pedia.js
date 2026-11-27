// The Almanac: what every number means and exactly where it comes from.
import { resolveTables } from "../terrain.js";
import { esc, int } from "../format.js";
import { t, num, date } from "../i18n.js";
import { parseHex, luminance } from "../color.js";
import { icon, glyph } from "./icon.js";

const COVER_ICON = { forest_deciduous: "l-forest", forest_evergreen: "l-forest", forest_mixed: "l-forest", cropland: "l-farmland", pasture: "l-farmland", urban: "l-developed" };
// Glyph colour that reads on a resource medallion (dark on light faces such as nuclear yellow or silver).
const inkOn = (hex) => {
  try { return /^#[0-9a-f]{6}$/i.test(hex || "") && luminance(parseHex(hex)) > 0.4 ? "#1c1710" : "#f8f0d8"; } catch { return "#f8f0d8"; }
};
const CATEGORY = { energy: t("Energy"), mineral: t("Minerals"), agri: t("Agriculture") };
const SCALE = { log: t("log"), linear: t("linear") };

export function initPedia(data) {
  const modal = document.getElementById("pedia");
  const card = modal.querySelector(".modal-card");
  const nav = document.getElementById("pedia-nav");
  const body = document.getElementById("pedia-body");
  const srcName = (id) => {
    const title = data.sources?.find((s) => s.id === id)?.title;
    return title ? t(title) : id || "";
  };
  let restoreFocus = null;

  const h2 = (ic, fb, text) => `<h2>${icon(ic, fb, { size: 24 })}<span>${esc(text)}</span></h2>`;

  // A translated text with HTML pieces: the text is escaped, then each {name} of `html` is replaced by its markup.
  const th = (text, html = {}) => esc(text).replace(/\{(\w+)\}/g, (m, k) => (k in html ? html[k] : m));
  const ext = (href, text) => `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(text)}</a>`;

  const pages = {
    "About this map": () => `
      ${h2("pedia", "\u{1f4d6}", t("About this map"))}
      <p>${th(t("This is real Vietnam, the Civ way. Every tile, town and number comes from public data, listed under {sources}."), { sources: `<i>${esc(t("Sources"))}</i>` })}</p>
      <h4>${esc(t("How it is built"))}</h4>
      <p>${esc(t("The country is projected (Albers equal-area) and cut into {cols} by {rows} hexes, each {size} km corner to corner. Each hex belongs to the province under most of its sample points. Terrain comes from the elevation and land-cover samples inside each hex.", { cols: data.world.grid.cols, rows: data.world.grid.rows, size: data.world.grid.radius * 2 }))}</p>
      <p>${esc(t("The map shows the 34 provinces and centrally run cities in force since 1 July 2025. Each of them joins one or more of the 63 provinces of before, whole; their old borders show as thin lines inside the new ones."))}</p>
      <p>${esc(t("The Ho\xe0ng Sa and Tr\u01b0\u1eddng Sa archipelagos are part of \u0110\xe0 N\u1eb5ng and Kh\xe1nh H\xf2a. Their islands are smaller than a hex, so each one is drawn as a mark."))}</p>
      <h4>${esc(t("How to read it"))}</h4>
      <p><b>${esc(t("Positions are schematic."))}</b> ${esc(t("A hex is a few kilometres wide, so a town or a power station sits on the hex that holds it, not at its exact address. Rivers, coasts and borders follow the hexes."))}</p>
      <p><b>${esc(t("Missing data stays missing."))}</b> ${esc(t("When a figure is not published for a place, the map shows a dash or leaves the place uncoloured. It never shows a zero or a guess."))}</p>
      <p><b>${esc(t("Selections are rules."))}</b> ${esc(t("Towns, resources and other sites are picked by a published rule (for example every power station above a size), never by taste. Each rule is in this Almanac."))}</p>
      <h4>${esc(t("Controls"))}</h4>
      <p>${esc(t("Drag, the arrow keys or WASD pan the map. Scroll, + and - or a double-click zoom. Click a town or a province to open it. Press / to search, L to change the lens, R to show or hide resources, ? for every shortcut and Esc to close."))}</p>
      <p>${th(t("The address bar always holds a link to what you are looking at. Use {share} to copy it or to download a picture."), { share: `<i>${esc(t("Share"))}</i>` })}</p>
      <h4>${esc(t("Credits"))}</h4>
      <p>${th(t("This map uses code from {link} under the MIT licence."), { link: ext("https://karpathy.ai/usaciv/", "usaciv") })}</p>
      <p>${esc(t("Map data from OpenStreetMap contributors (ODbL)."))}</p>`,
    Yields: () => `
      ${h2("y-gold", "\u{1f4b0}", t("Output"))}
      <p>${esc(t("The figures in the top bar and the province panels are real national and provincial statistics. Nothing is scored or simulated."))}</p>
      <table>${data.nation.yields.map((y) => `<tr><td class="ic" style="color:${esc(y.color)}">${glyph(y, 26)}</td><td><b style="color:${esc(y.color)}">${esc(y.key === "gold" ? t("{yield} (GDP)", { yield: t(y.label) }) : t(y.label))}</b><br>${esc(y.description ? t(y.description) : "")}</td></tr>`).join("")}</table>
      <h4>${esc(t("Work"))}</h4>
      <p>${esc(t("Unemployment is the share of the labour force at working age that has no work and is looking for it (Labour Force Survey)."))}</p>`,
    Provinces: () => `
      ${h2("terrain", "\u{1f5fa}\ufe0f", t("Provinces"))}
      <p>${esc(t("Click any land hex without a town to open its province. A province's figures are those the National Statistics Office publishes for it on the borders of 2025 ({vintage}).", { vintage: t(data.nation.vintage) }))}</p>
      <p>${esc(t("Six of the 34 units are centrally run cities: H\xe0 N\u1ed9i, H\u1ea3i Ph\xf2ng, Hu\u1ebf, \u0110\xe0 N\u1eb5ng, H\u1ed3 Ch\xed Minh and C\u1ea7n Th\u01a1. A city takes in its countryside, so its figures cover far more than the built-up town."))}</p>
      <p>${th(t("{ranks} (\"#3 of 34\") compare the 34 provinces; 1 is the largest."), { ranks: `<b>${esc(t("Ranks"))}</b>` })}</p>
      <h4>${esc(t("Towns"))}</h4>
      <p>${esc(t("Towns are the urban centres of the Global Human Settlement Layer: places where at least 50,000 people live close together. Their population is the estimate for 2025. The administrative centre of every province is shown too."))}</p>
      ${data.states ? "" : `<p class="muted">${esc(t("This data build has no province statistics."))}</p>`}`,
    Terrain: () => {
      const tb = data.w?.tables || resolveTables(data.world.tables);
      const hasCover = Array.isArray(data.world.cover);
      // Table names and rules come from world.json (or the defaults in terrain.js).
      const row = (x) => `<tr><td class="nm">${x.color ? `<span class="swatch" style="background:${esc(x.color)}"></span>` : ""}${
        COVER_ICON[x.key] ? icon(COVER_ICON[x.key], "", { size: 15 }) + " " : ""}<b>${esc(t(x.name))}</b></td><td>${esc(x.rule ? t(x.rule) : "")}</td></tr>`;
      return `
      ${h2("terrain", "\u{1f5fa}\ufe0f", t("Terrain"))}
      <p>${esc(t("Each hex averages the elevation samples inside it. Relief comes from the mean elevation and the roughness of those samples: the Red River and Mekong deltas stay flat, the Central Highlands rise into hills, and the north-west becomes mountains, highest in the Hoang Lien Son range. Shading comes from the height of each hex against its neighbours, lit from the north-west."))}</p>
      <h4>${icon("l-forest", "\u{1f332}", { size: 16 })} ${esc(t("Land cover"))}</h4>
      ${hasCover
        ? `<p>${esc(t("The base colour of each hex is its main land cover: the largest group among the land samples inside it. Small symbols show the mix: trees grow with the forest share, and fields, reeds, shrubs and grass mark farmland, wetland, scrub and meadow."))}</p>
           <table>${tb.cover.filter((x) => x.id > 0).map(row).join("")}</table>`
        : `<p class="muted">${esc(t("This data build has no land-cover layer yet; land is coloured by elevation."))}</p>`}
      <h4>${esc(t("Relief"))}</h4>
      <table>${tb.relief.map(row).join("")}</table>
      <h4>${icon("r-hydro", "\u{1f4a7}", { size: 16 })} ${esc(t("Water"))}</h4>
      <table>${tb.water.filter((x) => x.id > 0).map(row).join("")}</table>
      <h4>${esc(t("Beyond the borders"))}</h4>
      <p class="muted">${esc(t("The neighbouring countries (China, Laos, Cambodia and Thailand) are drawn under a light fog: they are shown for context and not mapped in detail."))}</p>`;
    },
    Lenses: () => `
      ${h2("layers", "\u25a4", t("Lenses"))}
      <p>${esc(t("Lenses recolour the map by one measure. Most measures are published per province: every hex of the province shows its value. Measures of the 2019 census exist only for the 63 provinces of that time, and the legend says so. Land, climate and night-light measures are computed for each hex from gridded data."))}</p>
      <p>${esc(t("The legend shows how many hexes fall at each value. Hover or drag on it to show only that range on the map."))}</p>
      ${(data.lenses.groups || [{ id: null, name: "" }]).map((g) => {
        const ls = data.lenses.lenses.filter((l) => !g.id || l.group === g.id);
        if (!ls.length) return "";
        return `${g.name ? `<h3 class="grp">${icon(`g-${g.id}`, "", { size: 16 })} ${esc(t(g.name))}</h3>` : ""}${ls.map((l) => {
          const meta = [
            t("Scale: {scale}, {min}\u2013{max} {unit}", { scale: SCALE[l.scale] || l.scale, min: num(l.domain[0], 3, { trim: true }), max: num(l.domain[1], 3, { trim: true }), unit: t(l.unit) }).trim(),
            l.higher_is === "good" ? t("higher is better") : l.higher_is === "bad" ? t("higher is worse") : "",
            l.source ? srcName(l.source) : "",
          ].filter(Boolean);
          return `
          <div class="lens-entry"><div class="le-ic">${glyph(l, 26)}</div><div>
          <h4>${esc(t(l.name))}</h4><p>${esc(t(l.description))}${l.scale_note ? ` ${esc(t(l.scale_note))}` : ""}<br>
          <i class="le-ramp" style="background:linear-gradient(90deg, ${(l.ramp || []).map(esc).join(",")})"></i>
          <span class="muted">${meta.map(esc).join(" \u00b7 ")}</span></p></div></div>`;
        }).join("")}`;
      }).join("")}`,
    Resources: () => {
      const r = data.resources;
      if (!r?.types?.length) return `${h2("resources", "\u26cf\ufe0f", t("Resources"))}<p class="muted">${esc(t("This data build has no resources layer."))}</p>`;
      const count = new Map();
      for (const it of r.items || []) count.set(it.type, (count.get(it.type) || 0) + 1);
      const cats = [...new Set(r.types.map((x) => x.category || "other"))];
      return `
      ${h2("resources", "\u26cf\ufe0f", t("Resources"))}
      <p>${esc(t("Resources mark the country's biggest power plants, mines and oil & gas fields on the tiles where they are. Only meaningful sites are shown: each type's threshold is in its description. When zoomed out, a hex shows its highest-ranked resource; zoom in to see more."))}
      ${th(t("Press {key} to show or hide them."), { key: "<b>R</b>" })}</p>
      ${cats.map((c) => `<h4>${esc(CATEGORY[c] || c)}</h4><table class="res-table">
        <tr><th></th><th>${esc(t("Type"))}</th><th>${esc(t("What counts"))}</th><th>${esc(t("Sites"))}</th></tr>
        ${r.types.filter((x) => (x.category || "other") === c).map((x) => `<tr>
          <td class="ic"><span class="res-ic" style="background:${esc(x.color || "#24384f")};color:${inkOn(x.color)}">${glyph(x, 20)}</span></td>
          <td class="nm"><b>${esc(t(x.name))}</b>${x.unit ? `<br><span class="muted">${esc(t("value in {unit}", { unit: t(x.unit) }))}</span>` : ""}</td>
          <td>${esc(x.description ? t(x.description) : "")}<br><span class="muted">${esc(t("Source: {source}", { source: srcName(x.source) }))}</span></td>
          <td class="num">${esc(int(count.get(x.id) || 0))}</td></tr>`).join("")}</table>`).join("")}`;
    },
    // Every registered motion layer (app.motion), with the rules, sources and attribution of its data file.
    "Moving layers": () => {
      const app = data.app;
      const list = app?.motion?.layers?.() || [];
      if (!list.length) return `${h2("layers", "\u25a4", t("Moving layers"))}<p class="muted">${esc(t("This data build has no moving layers."))}</p>`;
      const stamp = (iso) => (iso ? `${date(String(iso).slice(0, 10))} ${String(iso).slice(11, 16)} UTC` : "");
      const waiting = [];
      const entries = list.map((l) => {
        const d = l.data ? app.data?.[l.data] : null;
        if (l.data && d === undefined) waiting.push(l.data);
        const rules = Array.isArray(d?.rules) ? d.rules : d?.rules && typeof d.rules === "object" ? Object.values(d.rules) : d?.rule ? [d.rule] : [];
        const srcs = (d?.sources || []).map(srcName).filter(Boolean);
        const vintage = typeof d?.vintage === "string" ? t(d.vintage) : "";
        const a = d?.attribution && !Array.isArray(d.attribution) ? d.attribution : null;
        return `<h4>${esc(l.name || l.id)}</h4>
          ${rules.length ? `<ul>${rules.map((r) => `<li>${esc(t(r))}</li>`).join("")}</ul>` : d === undefined ? `<p class="muted">${esc(t("Loading..."))}</p>` : ""}
          ${a ? `<p>${a.created
            ? `${esc(t("Source: {source}", { source: (a.credit || []).join("; ") }))}<br>
            ${esc(t("Data created {created}; retrieved {retrieved}.", { created: stamp(a.created), retrieved: stamp(a.retrieved) }))}`
            : esc(a.retrieved ? t("Source: {source}, retrieved {retrieved}", { source: (a.credit || []).join("; "), retrieved: date(String(a.retrieved).slice(0, 10)) })
              : t("Source: {source}", { source: (a.credit || []).join("; ") }))}
            ${a.processed ? `<br>${esc(t(a.processed))}` : ""}${a.disclaimer ? `<br>${esc(t(a.disclaimer))}` : ""}
            ${a.original?.url ? `<br>${t("Original data: {link} ({size}, SHA-256 {hash})", { link: `<a href="${esc(a.original.url)}" rel="noopener">${esc(a.original.url.replace(/^https?:\/\//, ""))}</a>`, size: `${num((a.original.bytes || 0) / 1e6, 1)} MB`, hash: `<code style="word-break:break-all">${esc(String(a.original.sha256 || ""))}</code>` })}` : ""}</p>` : ""}
          ${srcs.length || vintage ? `<p class="muted">${esc([srcs.join(", "), vintage].filter(Boolean).join(" \u00b7 "))}</p>` : ""}`;
      });
      // Data files not loaded yet: load them, then redraw this page if it is still open.
      if (waiting.length) {
        Promise.all(waiting.map((n) => app.loadData(n))).then(() => {
          if (!modal.hidden && current === "Moving layers") show("Moving layers");
        });
      }
      return `${h2("layers", "\u25a4", t("Moving layers"))}
      <p>${esc(t("These layers play on one clock. Press play under the map, drag the slider or change the speed."))}</p>
      ${entries.join("")}`;
    },
    Sources: () => `
      ${h2("pedia", "\u{1f4d6}", t("Sources"))}
      ${data.sources == null ? `<p class="muted">${esc(t("Loading..."))}</p>` : ""}${(data.sources || []).map((s) => `
        <h4>${esc(t(s.title))}</h4>
        <p>${esc(t(s.description))}<br>
        <span class="muted">${esc(t(s.publisher))} \u00b7 ${esc(t(s.license))}${s.vintage ? " \u00b7 " + esc(t(s.vintage)) : ""} \u00b7
        <a href="${esc(s.homepage)}" target="_blank" rel="noopener">${esc(t("homepage"))}</a></span></p>
        <table>${(s.files || []).map((f) => `<tr><td><code>${esc(f.url)}</code></td><td class="muted" style="white-space:nowrap">${esc(date((f.retrieved || "").slice(0, 10)))}<br>${esc(num((f.bytes || 0) / 1e6, 1))} MB</td></tr>`).join("")}</table>`).join("")}`,
  };
  // Page ids stay English (other modules open pages by id); the nav shows the translated title.
  const TITLE = {
    "About this map": t("About this map"), Yields: t("Output"), Provinces: t("Provinces"), Terrain: t("Terrain"),
    Lenses: t("Lenses"), Resources: t("Resources"), "Moving layers": t("Moving layers"), Sources: t("Sources"),
  };

  let current = null;
  const show = (name) => {
    if (!pages[name]) name = "About this map";
    current = name;
    body.innerHTML = pages[name]();
    body.scrollTop = 0;
    nav.querySelectorAll("button").forEach((b) => {
      const on = b.dataset.page === name;
      b.classList.toggle("active", on);
      b.setAttribute("aria-current", on ? "page" : "false");
    });
  };
  nav.innerHTML = `<div class="hd">${esc(t("Almanac"))}</div>` + Object.keys(pages).map((p) => `<button data-page="${esc(p)}">${esc(TITLE[p] || p)}</button>`).join("");
  nav.onclick = (e) => {
    const b = e.target.closest("button[data-page]");
    if (b) show(b.dataset.page);
  };
  const close = () => {
    if (modal.hidden) return;
    modal.hidden = true;
    if (restoreFocus && document.contains(restoreFocus)) restoreFocus.focus();
    restoreFocus = null;
  };
  modal.onclick = (e) => {
    if (e.target === modal || e.target.closest("[data-close]")) close();
  };
  // Keep Tab inside the dialog.
  modal.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    const f = [...card.querySelectorAll("button, a[href], [tabindex]:not([tabindex='-1'])")].filter((x) => x.offsetParent);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  return {
    open(page = "About this map") {
      if (modal.hidden) restoreFocus = document.activeElement;
      // The source list loads with the Almanac, not with the map.
      if (data.sources == null && data.app?.loadData) {
        data.app.loadData("sources").then((d) => {
          data.sources = Array.isArray(d) ? d : [];
          if (!modal.hidden && current) show(current);
        }, () => {
          data.sources = [];
          if (!modal.hidden && current) show(current);
        });
      }
      show(page);
      modal.hidden = false;
      (nav.querySelector("button.active") || card.querySelector("[data-close]"))?.focus();
    },
    close,
    get isOpen() {
      return !modal.hidden;
    },
  };
}
