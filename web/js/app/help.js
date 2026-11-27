// Keyboard and mouse cheat sheet.
import { icon } from "../ui/icon.js";
import { t } from "../i18n.js";
import { esc } from "../format.js";

const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
const MOD = isMac ? "Cmd" : "Ctrl";

const ROWS = [
  [t("Move"), [
    [[t("Drag"), t("Arrow keys"), "WASD"], t("Pan the map")],
    [[t("Scroll"), "+", "-"], t("Zoom in and out")],
    [[t("Double-click")], t("Zoom in on a spot")],
    [[t("Two fingers")], t("Pinch to zoom, drag to pan (touch)")],
    [[t("Minimap")], t("Click or drag to jump")],
  ]],
  [t("Explore"), [
    [[t("Click town")], t("Open the town screen")],
    [[t("Click land")], t("Open that province")],
    [["/", `${MOD} K`], t("Search towns and provinces")],
    [["L", "Shift L"], t("Next or previous lens")],
    [[t("Legend")], t("Hover or drag the scale to show only that range")],
    [["R"], t("Show or hide resources")],
  ]],
  [t("Panels"), [
    [["?"], t("This help")],
    [["Esc"], t("Close help, search, Almanac, then the panel")],
  ]],
];

export function initHelp() {
  const modal = document.getElementById("help");
  if (!modal) return { open() {}, close() {}, get isOpen() { return false; } };
  const card = modal.querySelector(".help-card");
  let restore = null;
  card.innerHTML = `
    <button class="icon-btn help-close" data-close aria-label="${esc(t("Close help"))}">${icon("close", "\u2715", { size: 13 })}</button>
    <h2 id="help-title">${icon("help", "?", { size: 22 })}<span>${esc(t("Controls"))}</span></h2>
    <div class="help-cols">${ROWS.map(([title, rows]) => `
      <section><h3>${esc(title)}</h3>${rows.map(([keys, what]) => `
        <div class="help-row"><span class="keys">${keys.map((k) => `<kbd>${esc(k)}</kbd>`).join("")}</span><span>${esc(what)}</span></div>`).join("")}
      </section>`).join("")}</div>
    <p class="help-foot">${esc(t("The link in the address bar always reopens this exact view."))}
      ${esc(t("Open the {almanac} for what every number means.")).replace("{almanac}", `<b>${esc(t("Almanac"))}</b>`)}</p>`;

  const close = () => {
    if (modal.hidden) return;
    modal.hidden = true;
    if (restore && document.contains(restore)) restore.focus();
    restore = null;
  };
  modal.addEventListener("click", (e) => {
    if (e.target === modal || e.target.closest("[data-close]")) close();
  });
  modal.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    // Keep Tab inside the dialog: the close button and the source link.
    const f = [...card.querySelectorAll("button, a[href]")];
    const i = f.indexOf(document.activeElement);
    e.preventDefault();
    f[(i + (e.shiftKey ? f.length - 1 : 1)) % f.length]?.focus();
  });

  return {
    open() {
      if (!modal.hidden) return;
      restore = document.activeElement;
      modal.hidden = false;
      card.querySelector("[data-close]").focus();
    },
    close,
    toggle() { modal.hidden ? this.open() : close(); },
    get isOpen() { return !modal.hidden; },
  };
}
