// Share popover: copy a link to the current view, or download a 1600x900 PNG of it with a caption strip.
import { drawIcon, hasIcon } from "../icons.js";
import { icon } from "../ui/icon.js";
import { t, LANG } from "../i18n.js";
import { esc } from "../format.js";

// The published site: the one place it is set. index.html's canonical and social-card tags repeat it as literals
// (crawlers read no JS); keep them equal. Shared images print it without the scheme. When left empty, the page's own
// host and path are used, except on a local dev server, where SITE_FALLBACK is printed.
// A placeholder: this map has no public address. Set it only if the map is ever published.
export const SITE_URL = "https://softonsofa.com/vnm-civ/";
const SITE_FALLBACK = "vn-civ";

export function siteLabel() {
  // The Vietnamese page prints its own address (the site address plus /vi).
  if (SITE_URL) return SITE_URL.replace(/^https?:\/\//, "").replace(/\/$/, "") + (LANG === "vi" ? "/vi" : "");
  try {
    const { hostname, host, pathname } = location;
    const local = !hostname || /^(localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0)$/.test(hostname) || /\.(localhost|test|local)$/.test(hostname);
    if (local || !/^https?:$/.test(location.protocol)) return SITE_FALLBACK;
    const path = pathname.replace(/\/index\.html?$/, "/").replace(/\/$/, "");
    return (host.replace(/^www\./, "") + path).slice(0, 60);
  } catch {
    return SITE_FALLBACK;
  }
}

export const IMG_W = 1600;
export const IMG_H = 900;
export const CAPTION_H = 118;
const SERIF = '"Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif';
const SANS = '-apple-system, "Segoe UI", system-ui, sans-serif';
const CREDIT = t("Map data \u00a9 OpenStreetMap contributors");

async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch { /* fall through to the legacy path */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  } catch {
    return false;
  }
}

function spaced(ctx, px) {
  if ("letterSpacing" in ctx) ctx.letterSpacing = px + "px";
}

/**
 * Compose the share image.
 * info: {renderMap(canvas, w, h) -> bool, lens (lens object or null), formatValue(lens, t) -> string,
 *        selection: {kind, name, sub} | null}
 */
export function composeImage(info, { height = IMG_H } = {}) {
  const imgH = Math.max(CAPTION_H + 100, Math.round(height)); // a shorter frame serves 1.91:1 social cards
  const cv = document.createElement("canvas");
  cv.width = IMG_W;
  cv.height = imgH;
  const ctx = cv.getContext("2d");
  const mapH = imgH - CAPTION_H;

  // --- map ---
  ctx.fillStyle = "#0f2233";
  ctx.fillRect(0, 0, IMG_W, mapH);
  const map = document.createElement("canvas");
  map.width = IMG_W;
  map.height = mapH;
  let ok = false;
  try {
    ok = info.renderMap(map, IMG_W, mapH);
  } catch (err) {
    console.warn("share: map render failed", err);
  }
  if (ok) ctx.drawImage(map, 0, 0);

  // --- caption strip ---
  const y0 = mapH;
  const g = ctx.createLinearGradient(0, y0, 0, imgH);
  g.addColorStop(0, "#1f3447");
  g.addColorStop(1, "#0d1924");
  ctx.fillStyle = g;
  ctx.fillRect(0, y0, IMG_W, CAPTION_H);
  ctx.fillStyle = "#c9a45c";
  ctx.fillRect(0, y0, IMG_W, 3);
  ctx.fillStyle = "rgba(0,0,0,.6)";
  ctx.fillRect(0, y0 + 3, IMG_W, 1);
  ctx.fillStyle = "rgba(236,208,142,.25)";
  ctx.fillRect(0, y0 + 7, IMG_W, 1);
  const cy = y0 + CAPTION_H / 2 + 3;

  // Emblem + title
  drawEmblem(ctx, 64, cy, 62);
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = "#ecd08e";
  ctx.font = `bold 40px ${SERIF}`;
  spaced(ctx, 9);
  ctx.fillText(t("Vietnam").toUpperCase(), 108, cy + 2);
  spaced(ctx, 0);
  ctx.fillStyle = "#b9ab88";
  ctx.font = `italic 17px ${SERIF}`;
  ctx.fillText(t("Vietnam, the Civ way"), 110, cy + 28);

  // Lens + legend ramp
  const mx = 640;
  const lens = info.lens;
  const iconOk = (id) => id && hasIcon(id);
  const lensIcon = lens ? (iconOk(lens.icon) ? lens.icon : null) : "terrain";
  if (lensIcon) drawIcon(ctx, lensIcon, mx + 20, cy - 16, 40, { shadow: true });
  ctx.fillStyle = "#ecd08e";
  ctx.font = `24px ${SERIF}`;
  spaced(ctx, 1.5);
  ctx.fillText(lens ? t("{name} lens", { name: t(lens.name) }) : t("Terrain"), mx + 50, cy - 8);
  spaced(ctx, 0);
  if (lens?.ramp?.length) {
    const rx = mx + 50, ry = cy + 4, rw = 330, rh = 12;
    const rg = ctx.createLinearGradient(rx, 0, rx + rw, 0);
    lens.ramp.forEach((c, i) => rg.addColorStop(i / (lens.ramp.length - 1), c));
    ctx.fillStyle = "rgba(0,0,0,.6)";
    ctx.fillRect(rx - 1, ry - 1, rw + 2, rh + 2);
    ctx.fillStyle = rg;
    ctx.fillRect(rx, ry, rw, rh);
    ctx.font = `14px ${SANS}`;
    ctx.fillStyle = "#d8cba8";
    ctx.textAlign = "left";
    ctx.fillText(t("{value} or less", { value: info.formatValue(lens, 0) }), rx, ry + rh + 18);
    ctx.textAlign = "right";
    ctx.fillText(t("{value} or more", { value: info.formatValue(lens, 1) }), rx + rw, ry + rh + 18);
    ctx.textAlign = "left";
  } else {
    ctx.font = `15px ${SANS}`;
    ctx.fillStyle = "#b9ab88";
    ctx.fillText(t("Land cover, relief, rivers and resources"), mx + 50, cy + 16);
  }

  // Selection, credits, site
  const rx = IMG_W - 44;
  ctx.textAlign = "right";
  const sel = info.selection;
  if (sel?.name) {
    ctx.font = `italic 15px ${SERIF}`;
    ctx.fillStyle = "#b9ab88";
    ctx.fillText(sel.kind === "state" ? t("Province") : t("Town"), rx, cy - 30);
    ctx.font = `bold 24px ${SERIF}`;
    ctx.fillStyle = "#f3e6c4";
    ctx.fillText(fit(ctx, sel.name, 460), rx, cy - 6);
  }
  ctx.font = `14px ${SANS}`;
  ctx.fillStyle = "#b9ab88";
  ctx.fillText(CREDIT, rx, cy + 20);
  ctx.font = `bold 17px ${SERIF}`;
  ctx.fillStyle = "#c9a45c";
  spaced(ctx, 1);
  ctx.fillText(siteLabel(), rx, cy + 42);
  spaced(ctx, 0);
  ctx.textAlign = "left";

  // Thin gold frame around the whole picture
  ctx.strokeStyle = "rgba(201,164,92,.85)";
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, IMG_W - 2, imgH - 2);
  return cv;
}

function fit(ctx, text, maxW) {
  if (ctx.measureText(text).width <= maxW) return text;
  let s = text;
  while (s.length > 3 && ctx.measureText(s + "...").width > maxW) s = s.slice(0, -1);
  return s + "...";
}

/**
 * The studio emblem: a heater shield with a gold border, parchment-white over crimson, split by a gold wave (a river).
 * Original art; no state symbol. (x, y) is the centre, h the height in px. Same shape as the favicon in index.html.
 */
export function drawEmblem(ctx, x, y, h) {
  const k = h / 56; // the SVG emblem spans y 4..60 of a 64 box
  ctx.save();
  ctx.translate(x - 32 * k, y - 32 * k);
  ctx.scale(k, k);
  const shield = (inset) => {
    const p = new Path2D();
    const l = 8 + inset, r = 56 - inset, t = 6 + inset, b = 60 - inset * 1.15;
    p.moveTo(l, t);
    p.lineTo(r, t);
    p.lineTo(r, 30);
    p.bezierCurveTo(r, 30 + 15 * ((r - l) / 48), 32 + 10, b - 4, 32, b);
    p.bezierCurveTo(32 - 10, b - 4, l, 30 + 15 * ((r - l) / 48), l, 30);
    p.closePath();
    return p;
  };
  ctx.shadowColor = "rgba(0,0,0,.55)";
  ctx.shadowBlur = 4;
  ctx.shadowOffsetY = 1.5;
  ctx.fillStyle = "#120d06";
  ctx.fill(shield(0));
  ctx.shadowColor = "transparent";
  const gold = ctx.createLinearGradient(0, 6, 0, 60);
  gold.addColorStop(0, "#f6dc8a");
  gold.addColorStop(0.5, "#c9a45c");
  gold.addColorStop(1, "#8a6a2c");
  ctx.fillStyle = gold;
  ctx.fill(shield(3));
  const inner = shield(6.5);
  ctx.fillStyle = "#b3262e";
  ctx.fill(inner);
  ctx.save();
  ctx.clip(inner);
  const wave = new Path2D();
  wave.moveTo(8, 28);
  wave.bezierCurveTo(14, 31, 20, 31, 32, 28);
  wave.bezierCurveTo(44, 25, 50, 25, 56, 28);
  const white = new Path2D(wave);
  white.lineTo(56, 0);
  white.lineTo(8, 0);
  white.closePath();
  ctx.fillStyle = "#f4ecd8";
  ctx.fill(white);
  ctx.strokeStyle = "#e2bf6e";
  ctx.lineWidth = 2.6;
  ctx.stroke(wave);
  ctx.restore();
  ctx.restore();
}

/**
 * opts: {button, getInfo() -> composeImage info, fileName() -> string, onToast(msg)}
 */
export function initShare(opts) {
  const btn = opts.button;
  const pop = document.getElementById("share-pop");
  if (!btn || !pop) return { close() {}, get isOpen() { return false; } };
  let restore = null;

  pop.innerHTML = `
    <div class="sp-title">${esc(t("Share this view"))}</div>
    <button class="sp-item" data-act="copy">${icon("share", "\u{1f517}", { size: 16 })}<span>${esc(t("Copy link"))}</span></button>
    <button class="sp-item" data-act="image">${icon("terrain", "\u{1f5bc}\ufe0f", { size: 16 })}<span>${esc(t("Download image"))}</span></button>
    <div class="sp-status" role="status" aria-live="polite"></div>
    <input class="sp-url" type="text" readonly hidden aria-label="${esc(t("Link to this view"))}">`;
  const status = pop.querySelector(".sp-status");
  const urlBox = pop.querySelector(".sp-url");

  function position() {
    const r = btn.getBoundingClientRect();
    const w = pop.offsetWidth || 250;
    pop.style.top = r.bottom + 8 + "px";
    pop.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.right - w)) + "px";
  }
  function open() {
    restore = document.activeElement;
    status.textContent = "";
    urlBox.hidden = true;
    pop.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    position();
    pop.querySelector(".sp-item")?.focus();
  }
  function close(restoreFocus = true) {
    if (pop.hidden) return;
    pop.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    if (restoreFocus && restore && document.contains(restore)) restore.focus();
  }
  btn.addEventListener("click", () => (pop.hidden ? open() : close()));
  document.addEventListener("pointerdown", (e) => {
    if (!pop.hidden && !pop.contains(e.target) && !btn.contains(e.target)) close(false);
  });
  window.addEventListener("resize", () => !pop.hidden && position());

  pop.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-act]");
    if (!b) return;
    if (b.dataset.act === "copy") {
      opts.beforeCopy?.();
      const link = location.href;
      if (await copyText(link)) {
        status.textContent = t("Link copied to the clipboard");
        opts.onToast?.(t("Link copied"));
      } else {
        status.textContent = t("Copy this link:");
        urlBox.hidden = false;
        urlBox.value = link;
        urlBox.focus();
        urlBox.select();
      }
    } else if (b.dataset.act === "image") {
      status.textContent = t("Drawing the map...");
      await new Promise((r) => setTimeout(r, 30)); // let the status paint
      try {
        const cv = composeImage(opts.getInfo());
        const blob = await new Promise((r) => cv.toBlob(r, "image/png"));
        if (!blob) throw new Error("toBlob failed");
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = opts.fileName();
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 4000);
        status.textContent = t("Saved {file}", { file: a.download });
      } catch (err) {
        console.warn(err);
        status.textContent = t("Could not create the image in this browser.");
      }
    }
  });

  return {
    open,
    close,
    get isOpen() { return !pop.hidden; },
  };
}
