// The Animations button in the lens dock (right after the Map button) and its panel: the motion layers ("On the
// map", switches kept in layers= through app.ui.setMapToggle) and the time-lapse lenses ("Over time", a pick shows
// that lens and its clock). The motion layers register their toggles with menu: false, so the Map menu leaves them
// out. The badge counts the animations that are on (the motion layers plus a time-lapse lens shown).
import { t } from "../../i18n.js";
import { esc } from "../../format.js";
import { icon, glyph as lensGlyph } from "../../ui/icon.js";
import { hasIcon } from "../../icons.js";

// Order, names and hint lines of the panel (the toggles keep their own ids in layers=). Other extensions add their
// rows to app.motion.panelRows ({id, label, hint}, id = their map toggle id), shown after these.
const layerRows = (app) => [
  { id: "typhoons", label: t("Typhoons"), hint: t("Storm tracks year by year since 1981") },
  ...(app?.motion?.panelRows || []),
];
// lens: the lens a pick shows (its icon too); lenses: every lens that plays this time-lapse (ext/timelapse).
const lensRows = () => [
  { lens: "nightlights", lenses: ["nightlights"], label: t("Night lights by year"), hint: t("2014 to 2024") },
];

const glyph = (ic, size) => (ic && hasIcon(ic) ? icon(ic, "", { size }) : "");

export function installPanel(app) {
  const area = document.getElementById("lens-area");
  const dock = document.getElementById("lens-dock");
  if (!area || !dock || !app.ui?.mapToggles) return null;

  const btn = document.createElement("button");
  btn.id = "btn-animations";
  btn.type = "button";
  btn.className = "lens-btn res-toggle map-layers-btn anim-btn";
  btn.setAttribute("aria-haspopup", "true");
  btn.setAttribute("aria-expanded", "false");
  btn.setAttribute("aria-controls", "anim-pop");
  const pop = document.createElement("div");
  pop.id = "anim-pop";
  pop.className = "panel map-layers-pop anim-pop";
  pop.hidden = true;
  pop.setAttribute("role", "menu");
  pop.setAttribute("aria-label", t("Animations"));
  area.insertBefore(pop, area.firstChild);

  // Right after the Map button (it appears when the first map toggle registers), else after Resources.
  function place() {
    const after = document.getElementById("btn-maplayers") || document.getElementById("btn-res");
    if (after && after.parentNode === dock) {
      if (after.nextSibling !== btn) dock.insertBefore(btn, after.nextSibling);
    } else if (btn.parentNode !== dock) dock.insertBefore(btn, dock.firstChild);
  }

  const toggles = () => new Map(app.ui.mapToggles().map((tg) => [tg.id, tg]));
  const lensById = new Map((app.data?.lenses?.lenses || []).map((l) => [l.id, l]));
  const lensOk = (r) => !lensById.size || lensById.has(r.lens);
  const lensOn = (r) => r.lenses.includes(app.state?.lens?.id);

  function count() {
    const tg = toggles();
    return layerRows(app).filter((r) => tg.get(r.id)?.on).length + (lensRows().some(lensOn) ? 1 : 0);
  }

  const row = (key, on, ig, label, hint) => `<button type="button" class="ml-row anim-row${on ? " on" : ""}" role="menuitemcheckbox"
    aria-checked="${on}" data-anim="${esc(key)}"><span class="ml-ic">${ig}</span><span class="ml-txt"><span class="ml-lbl">${esc(label)}</span><span class="ml-hint">${esc(hint)}</span></span>
    <span class="ml-switch" aria-hidden="true"></span></button>`;

  function render() {
    place();
    const n = count();
    btn.classList.toggle("active", n > 0);
    btn.setAttribute("aria-label", n ? `${t("Animations")} (${n})` : t("Animations"));
    btn.innerHTML = `${glyph("animations", 15)}<span>${esc(t("Animations"))}</span>${n ? `<b class="ml-count">${n}</b>` : ""}`;
    if (pop.hidden) return;
    const focused = document.activeElement?.closest?.("[data-anim]")?.dataset.anim;
    const tg = toggles();
    const layers = layerRows(app).filter((r) => tg.has(r.id));
    const lenses = lensRows().filter(lensOk);
    pop.innerHTML =
      (layers.length ? `<div class="ml-head">${esc(t("On the map"))}</div>` +
        layers.map((r) => row(`layer:${r.id}`, !!tg.get(r.id).on, glyph(tg.get(r.id).icon, 18), r.label, r.hint)).join("") : "") +
      (lenses.length ? `<div class="ml-head">${esc(t("Over time"))}</div>` +
        lenses.map((r) => row(`lens:${r.lens}`, lensOn(r), lensById.has(r.lens) ? lensGlyph(lensById.get(r.lens), 18) : "", r.label, r.hint)).join("") : "");
    if (focused) pop.querySelector(`[data-anim="${CSS.escape(focused)}"]`)?.focus();
  }

  let restoreFocus = null;
  function open() {
    restoreFocus = document.activeElement;
    pop.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    render();
    pop.querySelector("[data-anim]")?.focus();
  }
  function close(restore = true) {
    if (pop.hidden) return false;
    pop.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    if (restore) (restoreFocus && document.contains(restoreFocus) && restoreFocus !== document.body ? restoreFocus : btn).focus();
    return true;
  }

  btn.onclick = () => (pop.hidden ? open() : close());
  pop.onclick = (e) => {
    const el = e.target.closest("[data-anim]");
    if (!el) return;
    const [kind, id] = el.dataset.anim.split(":");
    if (kind === "layer") {
      const tg = toggles().get(id);
      if (tg) app.ui.setMapToggle(id, !tg.on);
    } else {
      const r = lensRows().find((x) => x.lens === id);
      if (r) app.setLens(lensOn(r) ? null : r.lens);
    }
    render();
  };
  // Esc closes the panel first, wherever the focus is (capture phase: before main's keys and the active mode).
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || pop.hidden || e.defaultPrevented) return;
    e.preventDefault();
    close(pop.contains(document.activeElement) || document.activeElement === btn || document.activeElement === document.body);
  }, true);
  pop.addEventListener("keydown", (e) => {
    const rows = [...pop.querySelectorAll("[data-anim]")];
    const k = rows.indexOf(document.activeElement);
    const step = { ArrowDown: 1, ArrowUp: -1 }[e.key];
    if (step && k >= 0) {
      e.preventDefault();
      rows[(k + step + rows.length) % rows.length].focus();
    }
  });
  document.addEventListener("pointerdown", (e) => {
    if (!pop.hidden && !pop.contains(e.target) && !btn.contains(e.target)) close(false);
  });
  app.on("maptoggle", render);
  app.on("lens", () => setTimeout(render, 0));
  app.on("extensions", render);
  render();
  return { open, close, render, get isOpen() { return !pop.hidden; } };
}
