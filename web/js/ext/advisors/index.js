// Advisors: Civ-style exploration dashboards docked beside the map, linked both ways with it.
//
//   app mode "advisor", params {id, ...}  (id = an advisor id, or none for the council picker)
//   URL hash: #advisor=<id> ("council" for the picker)
//   top-bar button "Advisors"
// Each advisor is a module in views/ exporting mount(ctx) -> {onMapHover?, onMapClick?, onEscape?, destroy?}.
// ctx = {app, data, el, link, params, on(name, fn), bubbles(id, opts), tip, setResourceFilter, setShowResources,
//        switchTo(id, params)} - everything registered through ctx is undone when the view goes away.
import { buildData } from "./core/data.js";
import { createLinker, createBubbles, createMapTip } from "./core/link.js";
import { emblem } from "./core/emblems.js";
import { frameNation } from "./core/frame.js";
import { esc, el } from "./core/util.js";
import { icon } from "../../ui/icon.js";
import { t } from "../../i18n.js";

// Ranking advisors share one view (views/ranking.js): measures are province fields (core/data.js), "lens_<id>" for a
// field that comes from a province lens.
import { fmtValue, signedPct, count3, pct, money } from "./core/fmt.js";
const rank = (spec) => () => import("./views/ranking.js").then((m) => m.makeRanking(spec));
const SPECS = {
  economy: {
    tiles: [
      { label: t("GRDP"), value: (n) => money(n.gdp), sub: t("2025 estimate") },
      { label: t("GRDP per person"), value: (n) => money(n.gdp_per_capita), sub: t("2025 estimate") },
      { label: t("GRDP growth"), value: (n) => signedPct(n.grdp_growth), sub: "2025" },
    ],
    measures: [
      { key: "gdp_pc", lens: "grdp_pc" }, { key: "lens_grdp_growth", lens: "grdp_growth" },
      { key: "lens_income", lens: "income" }, { key: "lens_poverty", lens: "poverty", asc: true, topLabel: t("Lowest"), bottomLabel: t("Highest") },
      { key: "lens_productivity", lens: "productivity" }, { key: "gdp" },
    ],
  },
  people: {
    tiles: [
      { label: t("Residents"), value: (n) => count3(n.population), sub: t("average of 2025") },
      { label: t("Change 2020-2025"), value: (n) => signedPct(n.growth, 1), sub: t("on the borders of 2025") },
      { label: t("Urban"), value: (n) => pct(n.urban, 0), sub: t("of residents") },
    ],
    measures: [
      { key: "growth", lens: "pop_growth", diverging: true }, { key: "density" }, { key: "lens_urban", lens: "urban" },
      { key: "lens_migration", lens: "migration", diverging: true }, { key: "lens_fertility", lens: "fertility" },
      { key: "lens_life", lens: "life" },
    ],
  },
  enterprise: {
    measures: [
      { key: "lens_fdi", lens: "fdi" }, { key: "lens_firms", lens: "firms" }, { key: "lens_industry", lens: "industry" },
      { key: "lens_retail", lens: "retail" }, { key: "lens_travel", lens: "travel" },
    ],
  },
  governance: {
    measures: [
      { key: "lens_pci_proactive", lens: "pci_proactive" }, { key: "lens_pci_transparency", lens: "pci_transparency" },
      { key: "lens_pci_informal", lens: "pci_informal" }, { key: "lens_pci_support", lens: "pci_support" },
      { key: "lens_pci_bpi", lens: "pci_bpi" },
    ],
  },
  farm: {
    measures: [
      { key: "rice" }, { key: "lens_rice", lens: "rice" }, { key: "lens_aquaculture", lens: "aquaculture" },
      { key: "lens_fishery", lens: "fishery" }, { key: "lens_forest_official", lens: "forest_official" },
    ],
  },
  life: {
    measures: [
      { key: "lens_hdi", lens: "hdi" }, { key: "lens_doctors", lens: "doctors" }, { key: "lens_water", lens: "water" },
      { key: "lens_internet", lens: "internet" }, { key: "lens_trained", lens: "trained" },
      { key: "unemployment", lens: "unemployment", asc: true, topLabel: t("Lowest"), bottomLabel: t("Highest") },
    ],
  },
};
export const ADVISORS = [
  { id: "economy", name: "Th\u01b0\u1ee3ng th\u01b0 B\u1ed9 H\u1ed9", role: t("Economy"), color: "#c9a43a", dark: "#3a2c08", blurb: t("What each province produces, earns and spends, and who is left behind."), load: rank(SPECS.economy) },
  { id: "people", name: "Quan H\u1ed9 t\u1ecbch", role: t("Population"), color: "#c46a4f", dark: "#3a140c", blurb: t("Where people live, where they move and how long they live."), load: rank(SPECS.people) },
  { id: "enterprise", glyph: "commerce", name: "Th\u01b0\u01a1ng nh\u00e2n H\u1ed9i An", role: t("Enterprise"), color: "#2fa4b8", dark: "#062630", blurb: t("Foreign investment, firms, factories, shops and travel."), load: rank(SPECS.enterprise) },
  { id: "governance", glyph: "knowledge", name: "Quan Ng\u1ef1 s\u1eed", role: t("Governance"), color: "#4a86d6", dark: "#0a1c3a", blurb: t("How firms rate their provincial government (PCI 2025)."), load: rank(SPECS.governance) },
  { id: "farm", glyph: "prosperity", name: "Quan Khuy\u1ebfn n\u00f4ng", role: t("Farm and sea"), color: "#7fae3a", dark: "#1c2a08", blurb: t("Rice, fish and shrimp, and the forests."), load: rank(SPECS.farm) },
  { id: "life", glyph: "culture", name: "Th\u00e1i y", role: t("Daily life"), color: "#c25b9a", dark: "#2e0c22", blurb: t("Health, schooling, clean water and the internet."), load: rank(SPECS.life) },
  { id: "land", name: "Quan \u0110\u1ecba b\u1ea1", role: t("Land"), color: "#6e9a3c", dark: "#18280a", blurb: t("Forest, farmland, wetland and towns: what covers the country."), load: () => import("./views/land.js") },
  { id: "explorer", name: "Ng\u01b0\u1eddi v\u1ebd b\u1ea3n \u0111\u1ed3", role: t("Data explorer"), color: "#9a7bc9", dark: "#1e1236", blurb: t("Slice and dice every number: any level, any columns, any chart."), load: () => import("./views/explorer.js") },
];
const byId = new Map(ADVISORS.map((a) => [a.id, a]));
// The council picker groups its advisors (any advisor not listed here is added to the last group).
const COUNCIL = (() => {
  const g = [
    { label: t("Wealth and work"), ids: ["economy", "enterprise", "governance"] },
    { label: t("People and land"), ids: ["people", "life", "farm", "land"] },
    { label: t("Your own questions"), ids: ["explorer"] },
  ];
  const listed = new Set(g.flatMap((x) => x.ids));
  g[g.length - 1].ids.push(...ADVISORS.filter((a) => !listed.has(a.id)).map((a) => a.id));
  return g;
})();
// 460 px, narrower below 1200 px wide so the whole country still fits beside the dock (matches advisors.css).
const dockW = () => (innerWidth >= 1200 ? 460 : Math.round(Math.min(460, Math.max(340, innerWidth * 0.38))));

function injectCss() {
  if (document.getElementById("advisors-css")) return;
  const l = document.createElement("link");
  l.id = "advisors-css";
  l.rel = "stylesheet";
  l.href = new URL("../../../css/advisors.css", import.meta.url).href;
  document.head.appendChild(l);
}

export function install(app) {
  injectCss();
  let data = null, dataP = null;
  let dock = null;
  let active = null; // {adv, api, cleanup: [fn], bubbles: [b], token}
  let current = null; // advisor id or "council"
  let pendingTeardown = false;
  let token = 0;
  let lastId = null;
  let framedFor = null; // the advisor the map was last framed for
  let prevCam = null; // the camera when the advisors opened
  const link = createLinker(app);
  const tip = createMapTip();
  const canvas = document.getElementById("map");

  const ensureData = () => (dataP ??= Promise.all([app.loadCounties().catch(() => null), app.loadData("sources").catch(() => null)])
    .then(() => (data = buildData(app))));

  // --- top-bar button ---------------------------------------------------------------------------------------------
  const btn = app.ui.addTopButton({
    id: "btn-advisors", icon: "g-people", label: t("Advisors"), title: t("Advisors: explore the data behind the map"),
    onClick: () => (app.mode === "advisor" ? app.setMode(null) : app.setMode("advisor", { id: lastId })),
  });
  if (btn) {
    btn.innerHTML = `<svg class="icon" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 2.5 3 7v2h18V7z" fill="currentColor"/><path d="M5 10.5h2.6v7H5zM10.7 10.5h2.6v7h-2.6zM16.4 10.5H19v7h-2.6zM3.5 19h17v2.5h-17z" fill="currentColor"/></svg><span class="lbl">${esc(t("Advisors"))}</span>`;
    btn.setAttribute("aria-pressed", "false");
  }
  app.on("mode", ({ name }) => btn?.setAttribute("aria-pressed", String(name === "advisor")));

  // --- dock shell -------------------------------------------------------------------------------------------------
  function shell() {
    dock = app.ui.dock("left", { width: dockW(), label: t("Advisors") });
    if (dock.querySelector(".adv-root")) return dock.querySelector(".adv-root");
    dock.innerHTML = "";
    dock.classList.add("adv-dock");
    const root = el("div", "adv-root");
    root.innerHTML = `
      <div class="adv-grip" aria-hidden="true"></div>
      <header class="adv-head">
        <button type="button" class="adv-council-btn" data-adv="council" title="${esc(t("All advisors"))}">${icon("g-people", "\u{1f465}", { size: 14 })}<span>${esc(t("Council"))}</span></button>
        <nav class="adv-tabs" role="tablist" aria-label="${esc(t("Advisors"))}">${ADVISORS.map((a) => `<button type="button" role="tab" data-adv="${a.id}" aria-selected="false" title="${esc(`${a.name}: ${a.role}`)}" style="--adv:${a.color}">${emblem(a, 30)}<span class="sr-only">${esc(a.name)}</span></button>`).join("")}</nav>
        <button type="button" class="icon-btn adv-close" aria-label="${esc(t("Close the advisors (Esc)"))}" title="${esc(t("Close (Esc)"))}">${icon("close", "\u2715", { size: 12 })}</button>
      </header>
      <div class="adv-main" tabindex="-1"></div>`;
    dock.appendChild(root);
    root.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.classList.contains("adv-close")) return app.setMode(null);
      if (b.dataset.adv) return switchTo(b.dataset.adv === "council" ? null : b.dataset.adv);
      if (b.dataset.pedia) return app.pedia?.open?.(b.dataset.pedia);
      if (b.hasAttribute("data-frame")) return link.frame() || frameNation(app);
    });
    root.querySelector(".adv-tabs").addEventListener("keydown", (e) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
      const tabs = [...root.querySelectorAll(".adv-tabs [role=tab]")];
      let i = tabs.indexOf(document.activeElement);
      i = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      e.preventDefault();
      tabs[i].focus();
      switchTo(tabs[i].dataset.adv);
    });
    return root;
  }

  function switchTo(id, params = {}) {
    if (app.mode === "advisor" && (id || "council") === current && !Object.keys(params).length) return;
    app.setMode("advisor", { ...params, id: id || null });
  }

  // --- views ------------------------------------------------------------------------------------------------------
  function teardownView() {
    if (!active) return;
    const a = active;
    active = null;
    try { a.api?.destroy?.(); } catch (err) { console.error("advisor destroy failed", err); }
    dispose(a);
    link.clear();
    tip.hide();
  }
  // Run (and forget) a view's cleanups and bubbles; safe to call again for anything registered later.
  function dispose(a) {
    const fns = a.cleanup.splice(0).reverse(), bs = a.bubbles.splice(0);
    for (const f of fns) { try { f(); } catch (err) { console.error(err); } }
    for (const b of bs) b.destroy();
  }

  async function show(id, params) {
    const my = ++token;
    const root = shell();
    const adv = id ? byId.get(id) : null;
    current = adv ? adv.id : "council";
    if (adv) lastId = adv.id;
    root.style.setProperty("--adv", adv?.color || "#c9a45c");
    root.querySelectorAll(".adv-tabs [role=tab]").forEach((b) => {
      const on = b.dataset.adv === current;
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on || (!adv && b === root.querySelector(".adv-tabs [role=tab]")) ? 0 : -1;
    });
    root.querySelector(".adv-council-btn").setAttribute("aria-pressed", String(!adv));
    teardownView();
    // Every advisor is national in scope: frame the whole country beside the dock when one opens (or the council
    // first appears), not when the same advisor is re-shown with new parameters.
    if (current !== framedFor) {
      framedFor = current;
      requestAnimationFrame(() => { if (my === token && app.mode === "advisor") frameNation(app); });
    }
    const main = root.querySelector(".adv-main");
    main.scrollTop = 0;
    dock.scrollTop = 0;
    if (!adv) {
      main.innerHTML = councilHtml();
      main.querySelectorAll(".adv-card").forEach((c) => c.addEventListener("click", () => switchTo(c.dataset.adv)));
      return;
    }
    main.innerHTML = `${titleHtml(adv)}<div class="adv-body"><div class="adv-loading">${esc(t("{name} is gathering the figures...", { name: adv.name }))}</div></div>`;
    let mod;
    try {
      [mod] = await Promise.all([adv.load(), ensureData()]);
    } catch (err) {
      console.error(err);
      if (my === token) main.querySelector(".adv-body").innerHTML = `<p class="adv-empty pad">${esc(t("This advisor could not load ({error}).", { error: String(err.message || err) }))}</p>`;
      return;
    }
    if (my !== token || app.mode !== "advisor") return;
    const body = main.querySelector(".adv-body");
    // The loading line stays while an advisor that awaits its own files mounts; it is removed once the view is up.
    const loading = body.querySelector(".adv-loading");
    body.replaceChildren(...(loading ? [loading] : []));
    const a = { adv, api: null, cleanup: [], bubbles: [], token: my };
    active = a;
    const ctx = {
      app, data, el: body, link, tip, params: params || {}, advisor: adv,
      on(name, fn) { const off = app.on(name, fn); a.cleanup.push(off); return off; },
      bubbles(id, opts = {}) {
        const b = createBubbles(app, `adv-${adv.id}-${id}`, opts);
        b.handlers = opts;
        a.bubbles.push(b);
        return b;
      },
      setResourceFilter(f) {
        if (!a.savedFilter) { a.savedFilter = { f: app.state.resourceFilter }; a.cleanup.push(() => app.setResourceFilter(a.savedFilter.f)); }
        app.setResourceFilter(f);
      },
      setShowResources(on) {
        if (!a.savedShow) { a.savedShow = { v: app.state.showResources }; a.cleanup.push(() => app.setShowResources(a.savedShow.v)); }
        app.setShowResources(on);
      },
      /** Colour the map with a lens (a lenses.json id, a lens object, or null) while this view is open. The lens the
       *  viewer had is restored on exit, unless they have picked another one themselves since. */
      setLens(ref) {
        if (!a.lensSaved) {
          a.lensSaved = { lens: app.state.lens, ours: new Set() };
          a.cleanup.push(() => {
            const cur = app.state.lens;
            if (cur === a.lensSaved.lens || (cur && !a.lensSaved.ours.has(cur))) return;
            app.setLens(a.lensSaved.lens || null);
          });
        }
        app.setLens(ref);
        if (app.state.lens) a.lensSaved.ours.add(app.state.lens);
      },
      switchTo,
      cleanup: (fn) => a.cleanup.push(fn),
    };
    try {
      a.api = (await mod.mount(ctx)) || {};
    } catch (err) {
      console.error(`advisor "${adv.id}" failed`, err);
      body.insertAdjacentHTML("beforeend", `<p class="adv-empty pad">${esc(t("Something went wrong drawing this advisor."))}</p>`);
      a.api = {};
    }
    loading?.remove();
    // The view may have been switched away while it awaited its files: undo what it registered.
    if (active !== a) {
      try { a.api?.destroy?.(); } catch (err) { console.error(err); }
      dispose(a);
      return;
    }
    // Map hover -> dashboard, only while a view that wants it is open (the app skips hover work without listeners).
    if (a.api.onMapHover && active === a) {
      a.cleanup.push(app.on("hover", (h) => {
        try { a.api.onMapHover(h); } catch (err) { console.error(err); }
      }));
    }
  }

  function titleHtml(adv) {
    return `<div class="adv-title" style="--adv:${adv.color}">
      ${emblem(adv, 64)}
      <div class="adv-titles"><h2>${esc(adv.name)}</h2><div class="adv-role">${esc(adv.role)}</div><p>${esc(adv.blurb)}</p></div>
    </div>`;
  }

  function councilHtml() {
    return `<div class="adv-title council"><div class="adv-titles"><h2>${esc(t("Advisors"))}</h2><div class="adv-role">${esc(t("Your council"))}</div>
      <p>${esc(t("Each advisor keeps one ledger of the country. Hover a figure to find it on the map, hover the map to find it in the charts, click to look closer."))}</p></div></div>
      ${COUNCIL.map((g) => `<h4 class="adv-council-h">${esc(g.label)}</h4><div class="adv-council">${g.ids.map((id) => byId.get(id)).filter(Boolean).map((a) => `<button type="button" class="adv-card" data-adv="${a.id}" style="--adv:${a.color}">
        ${emblem(a, 48)}<span class="t"><b>${esc(a.name)}</b><span class="r">${esc(a.role)}</span><span class="d">${esc(a.blurb)}</span></span></button>`).join("")}</div>`).join("")}`;
  }

  // --- map -> dashboard --------------------------------------------------------------------------------------------
  let lastBubble = null;
  canvas?.addEventListener("pointermove", (e) => {
    if (app.mode !== "advisor" || !active || e.pointerType !== "mouse" || e.buttons) return;
    let hit = null, owner = null;
    for (const b of active.bubbles) {
      hit = b.hit(e.clientX, e.clientY);
      if (hit) { owner = b; break; }
    }
    if (hit !== lastBubble) {
      for (const b of active.bubbles) b.setHot(b === owner ? hit.key : null);
      lastBubble = hit;
      link.fromMap(() => {
        owner?.handlers.onHover?.(hit);
        if (!hit) for (const b of active.bubbles) b.handlers.onHover?.(null);
      });
    }
    if (hit && owner.handlers.tip) tip.show(e.clientX, e.clientY, owner.handlers.tip(hit));
    else tip.hide();
  });
  canvas?.addEventListener("pointerleave", () => {
    if (!lastBubble || !active) return;
    link.fromMap(() => { for (const b of active.bubbles) { b.setHot(null); b.handlers.onHover?.(null); } });
    lastBubble = null;
    tip.hide();
  });
  app.on("mapclick", (ev) => {
    if (app.mode !== "advisor" || !active) return false;
    for (const b of active.bubbles) {
      const hit = b.hit(ev.x, ev.y);
      if (hit && b.handlers.onClick) { b.handlers.onClick(hit); return true; }
    }
    return active.api?.onMapClick?.(ev) === true;
  });

  // --- mode -------------------------------------------------------------------------------------------------------
  app.registerMode("advisor", {
    enter(params) {
      // Remember where the camera was when the advisors opened (not on a switch between advisors), to fly back on exit.
      if (!pendingTeardown && !current) prevCam = { x: app.cam.x, y: app.cam.y, scale: app.cam.scale };
      pendingTeardown = false;
      show(params?.id && byId.has(params.id) ? params.id : null, params);
    },
    exit() {
      // A switch between advisors is exit() + enter() in one go: keep the dock and only rebuild its content.
      pendingTeardown = true;
      token++;
      queueMicrotask(() => {
        if (!pendingTeardown) return;
        pendingTeardown = false;
        teardownView();
        current = null;
        framedFor = null;
        // Back to the view the advisors were opened from (unless another mode, e.g. the City view, took over).
        const p = prevCam;
        prevCam = null;
        if (p && app.mode == null) {
          const fs = app.cam.fitScale;
          if (fs > 0 && Math.abs(p.scale / fs - 1) < 0.03) app.home();
          else { app.cam.flyTo(p.x, p.y, p.scale, 650); app.requestDraw(); }
        }
        // Leave the left dock alone if another mode has already put its own content there.
        const d = dock, root = d?.querySelector(".adv-root");
        dock = null;
        if (!d || !root) return;
        root.remove();
        d.classList.remove("adv-dock");
        if (!d.children.length) app.ui.undock("left");
      });
    },
    onEscape() {
      if (active?.api?.onEscape?.() === true) return true;
      return false;
    },
  });

  app.hash.register("advisor", {
    get: () => (app.mode === "advisor" ? current || "council" : null),
    set(v) {
      if (v) {
        const id = byId.has(v) ? v : null;
        if (app.mode !== "advisor" || (id || "council") !== current) app.setMode("advisor", { id });
      } else if (app.mode === "advisor") app.setMode(null);
    },
  });

  app.advisors = { list: ADVISORS, open: (id, params) => switchTo(id, params), get current() { return current; }, data: () => data, ensureData };
}
