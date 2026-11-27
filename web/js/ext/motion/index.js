// The motion engine: animated map layers that share one clock (app.motion). See docs/DATA_CONTRACTS.md "Motion
// layers" for the contract other extensions build on.
//
//   app.motion.register({id, name?, data?, axis, range, step?, speed, start?, loop?, background?(), label(t), status?(t),
//                        active(), load(), draw(ctx, vp, t, o), hit?(mx, my), filter?(sel)}) -> unregister
//   app.motion.clock     {t, axis, playing, speed, play(), pause(), toggle(), seek(t), setSpeed(k), axisOf(id)}
//   app.motion.particles(path, opts)   the shared moving-dots helper (particles.js)
//   app.motion.month(iso) / monthIso(index)   the month axis unit: year * 12 + (month - 1)
//   app.motion.hour(iso) / hourIso(index)     the hour axis unit: whole hours since 1970-01-01T00:00 (wall clock)
//
// How it runs: one overlay (under the city banners) draws every active motion layer each frame. While a layer is on
// and the clock plays, the overlay asks main for the next frame; it stops when the clock pauses, when no motion layer
// is on, and while the tab is hidden. Clock time comes from performance.now(), so a fake clock (Playwright
// page.clock) drives it frame by frame. With prefers-reduced-motion nothing plays by itself: the layer draws one
// still frame and the play button works on demand.
//
// The clock follows the axis of the most recently enabled layer; layers on another axis hold their last frame. The
// clock bar (play/pause, speed, scrubber, time label, the layer's counter) sits above the lens dock while any motion
// layer is on. The URL keeps the clock value as #t= (08:15, 2026-01-20T23:00, 2018-06, 2019) once it was paused or
// moved by hand. panel.js adds the Animations button and panel to the lens dock.
import { particles } from "./particles.js";
import { installPanel } from "./panel.js";
import { t, ROOT } from "../../i18n.js";
import { esc } from "../../format.js";

const AXES = ["day", "hour", "month", "year", "live"];
const SPEEDS = [1, 4, 16];
// The bar's words (getters, so they read the catalogue when used; `t` is a clock value inside the functions below).
const TXT = {
  get clock() { return t("Clock"); },
  get speed() { return t("Speed"); },
  get play() { return t("Play"); },
  get pause() { return t("Pause"); },
  get time() { return t("Time"); },
};
const MAX_DT = 0.25; // s: a long frame gap (a stalled tab) advances the clock by at most this much

export const month = (iso) => {
  const m = /^(\d{4})-(\d{2})$/.exec(String(iso || ""));
  return m ? +m[1] * 12 + (+m[2] - 1) : null;
};
export const monthIso = (k) => {
  const i = Math.floor(k);
  return `${String(Math.floor(i / 12)).padStart(4, "0")}-${String((i % 12) + 1).padStart(2, "0")}`;
};
// The hour axis unit: whole hours since 1970-01-01 00:00 of the data's own wall clock (no time zone, no DST).
export const hour = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2})(?::(\d{2}))?/.exec(String(iso || ""));
  return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4]) / 3600000 : null;
};
export const hourIso = (k) => new Date(Math.floor(k) * 3600000).toISOString().slice(0, 16);
export const hhmm = (sec) => {
  const m = Math.floor(((sec % 86400) + 86400) % 86400 / 60);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};

// The clock value as it goes into the URL, and back.
function formatT(axis, t) {
  if (axis === "day") return hhmm(t);
  if (axis === "month") return monthIso(t);
  if (axis === "hour") return hourIso(t);
  if (axis === "year") return String(Math.floor(t));
  return null;
}
function parseT(v) {
  const s = String(v || "").trim();
  let m = /^(\d{1,2}):(\d{2})$/.exec(s);
  if (m && +m[1] < 24 && +m[2] < 60) return { axis: "day", t: +m[1] * 3600 + +m[2] * 60 };
  m = /^(\d{4})-(\d{2})$/.exec(s);
  if (m && +m[2] >= 1 && +m[2] <= 12) return { axis: "month", t: month(s) };
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s)) return { axis: "hour", t: hour(s) };
  m = /^(\d{4})$/.exec(s);
  if (m) return { axis: "year", t: +m[1] };
  return null;
}

function addCss() {
  if (document.getElementById("motion-css")) return;
  const l = document.createElement("link");
  l.id = "motion-css";
  l.rel = "stylesheet";
  l.href = `${ROOT}css/motion.css`;
  document.head.appendChild(l);
}

const PLAY_SVG = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 2.5v11l9.5-5.5z" fill="currentColor"/></svg>';
const PAUSE_SVG = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><rect x="3.5" y="2.5" width="3.2" height="11" rx=".8" fill="currentColor"/><rect x="9.3" y="2.5" width="3.2" height="11" rx=".8" fill="currentColor"/></svg>';

export function createEngine(app, { reducedMotion = null } = {}) {
  const layers = new Map(); // id -> {def, on, order, loaded, loading, lastT}
  const axes = Object.fromEntries(AXES.map((a) => [a, { t: null, committed: null }]));
  let order = 0;
  let current = null; // the layer entry the clock follows
  let playing = false;
  let speedK = 1;
  let lastNow = null;
  let pendingUrl = null; // {axis, t} from the URL before a layer on that axis is on
  let filterSel = null;
  let bar = null;
  const stats = { frames: 0, dots: 0, drawMs: 0 };
  const reduce = () => (reducedMotion != null ? reducedMotion : matchMedia("(prefers-reduced-motion: reduce)").matches);

  const isOn = (e) => {
    try { return !!e.def.active(); } catch (err) { warn(e, "active", err); return false; }
  };
  function warn(e, what, err) {
    if (e[`_w${what}`]) return;
    e[`_w${what}`] = true;
    console.error(`motion layer "${e.def.id}" ${what}() failed`, err);
  }

  const rangeOf = (e) => (Array.isArray(e?.def.range) ? e.def.range : null);
  function clampT(e, t) {
    const r = rangeOf(e);
    if (!r) return t;
    if (e.def.loop ?? e.def.axis === "day") {
      const span = r[1] - r[0];
      return span > 0 ? r[0] + ((((t - r[0]) % span) + span) % span) : r[0];
    }
    return Math.min(r[1], Math.max(r[0], t));
  }
  const snap = (e, t) => {
    const st = e?.def.step;
    return st ? Math.round(t / st) * st : t;
  };
  function startOf(e) {
    const r = rangeOf(e);
    return e.def.start ?? (r ? r[0] : 0);
  }

  // Load a layer's data once; redraw when it arrives.
  function ensureLoaded(e) {
    if (e.loaded || e.loading || typeof e.def.load !== "function") {
      if (typeof e.def.load !== "function") e.loaded = true;
      return;
    }
    e.loading = Promise.resolve().then(() => e.def.load()).then(() => {
      e.loaded = true;
      e.loading = null;
      if (current === e) clampAxis();
      syncBar();
      app.requestDraw();
    }, (err) => {
      e.loading = null;
      warn(e, "load", err);
    });
  }

  function clampAxis() {
    if (!current || !current.loaded) return; // a layer's range may depend on its data
    const ax = axes[current.def.axis];
    ax.t = clampT(current, ax.t ?? startOf(current));
  }

  // Which layers are on: called each frame and after toggles. Newly enabled layers take the clock.
  function poll() {
    let changed = false;
    for (const e of layers.values()) {
      const on = isOn(e);
      if (on === e.on) continue;
      changed = true;
      e.on = on;
      if (on) {
        // A layer that is on only by default (trains) takes the clock only when no other layer is on.
        let bg = false;
        try { bg = !!e.def.background?.(); } catch (err) { warn(e, "background", err); }
        e.order = bg ? -(++order) : ++order;
        ensureLoaded(e);
        applyFilter(e);
      }
    }
    if (!changed) return;
    const prev = current;
    current = [...layers.values()].filter((e) => e.on).sort((a, b) => b.order - a.order)[0] || null;
    if (current && current !== prev) {
      const ax = axes[current.def.axis];
      if (pendingUrl && pendingUrl.axis === current.def.axis) {
        ax.t = pendingUrl.t;
        ax.committed = pendingUrl.t;
        pendingUrl = null;
        playing = false;
      } else {
        if (ax.t == null) ax.t = startOf(current);
        playing = !reduce();
      }
      clampAxis();
      lastNow = null;
    }
    if (!current) playing = false;
    syncBar();
    app.hash?.update?.();
  }

  function applyFilter(e) {
    if (typeof e.def.filter !== "function") return;
    try { e.def.filter(filterSel); } catch (err) { warn(e, "filter", err); }
  }

  function advance(now) {
    if (!current || !playing || !current.loaded) { lastNow = now; return; } // the clock waits for the data
    const dt = lastNow == null ? 0 : Math.min(MAX_DT, Math.max(0, (now - lastNow) / 1000));
    lastNow = now;
    if (!dt) return;
    const ax = axes[current.def.axis];
    const r = rangeOf(current);
    let t = (ax.t ?? startOf(current)) + dt * (current.def.speed || 1) * speedK;
    if (r && !(current.def.loop ?? current.def.axis === "day") && t >= r[1]) {
      t = r[1];
      playing = false; // a time-lapse stops on its last month and holds it
      commit();
      syncBar();
    }
    ax.t = clampT(current, t);
  }

  // The overlay: every active motion layer, each at its own axis's clock value.
  const overlay = {
    id: "motion", z: 92, space: "world",
    draw(ctx, cam) {
      const t0 = performance.now();
      poll();
      advance(t0);
      const v = cam.view();
      const dpr = ctx.getTransform().a / cam.scale || 1;
      const vp = { ...v, s: cam.scale, cam, dpr };
      const o = { Rpx: app.w.grid.R * cam.scale, lens: app.state.lens, dpr, s: cam.scale, cam };
      const on = [...layers.values()].filter((e) => e.on && e.loaded).sort((a, b) => (a.def.z ?? 0) - (b.def.z ?? 0) || a.order - b.order);
      let dots = 0;
      for (const e of on) {
        const ax = axes[e.def.axis];
        const t = e.def.axis === "live" ? t0 / 1000 : (ax.t ?? startOf(e));
        e.lastT = t;
        ctx.save();
        try {
          dots += e.def.draw(ctx, vp, t, o) || 0;
        } catch (err) {
          warn(e, "draw", err);
        }
        ctx.restore();
      }
      stats.frames++;
      stats.dots = dots;
      stats.drawMs = performance.now() - t0;
      if (bar && current) updateBarTime();
      // While the data loads the clock waits; ensureLoaded() asks for a frame when it arrives.
      if (playing && current && current.loaded && !document.hidden) app.requestDraw();
    },
  };

  // --- clock ---------------------------------------------------------------------------------------------------
  function commit() {
    if (!current) return;
    const ax = axes[current.def.axis];
    ax.committed = ax.t;
    app.hash?.update?.();
  }
  const clock = {
    get t() { return current ? axes[current.def.axis].t : null; },
    get axis() { return current ? current.def.axis : null; },
    get layer() { return current ? current.def.id : null; },
    get playing() { return playing; },
    get speed() { return speedK; },
    play() {
      if (!current) return;
      const r = rangeOf(current), ax = axes[current.def.axis];
      if (r && !(current.def.loop ?? current.def.axis === "day") && ax.t >= r[1]) ax.t = r[0]; // replay from the start
      playing = true;
      lastNow = null;
      syncBar();
      app.requestDraw();
    },
    pause() {
      playing = false;
      commit();
      syncBar();
      app.requestDraw();
    },
    toggle() { return playing ? clock.pause() : clock.play(); },
    seek(t) {
      if (!current || !Number.isFinite(+t)) return;
      axes[current.def.axis].t = clampT(current, snap(current, +t));
      lastNow = null;
      commit();
      updateBarTime();
      app.requestDraw();
    },
    setSpeed(k) {
      if (!SPEEDS.includes(+k)) return;
      speedK = +k;
      syncBar();
    },
    axisOf: (id) => layers.get(id)?.def.axis ?? null,
  };

  // --- clock bar -----------------------------------------------------------------------------------------------
  function buildBar() {
    const area = document.getElementById("lens-area");
    const dock = document.getElementById("lens-dock");
    if (!area) return null;
    const el = document.createElement("div");
    el.id = "motion-bar";
    el.className = "panel motion-bar";
    el.setAttribute("role", "group");
    el.setAttribute("aria-label", TXT.clock);
    el.hidden = true;
    el.innerHTML = `
      <button type="button" class="mb-play"></button>
      <span class="mb-time" aria-live="off"></span>
      <input class="mb-scrub" type="range" min="0" max="1" step="any">
      <span class="mb-status"></span>
      <span class="mb-speed" role="group" aria-label="${esc(TXT.speed)}">${SPEEDS.map((k) =>
        `<button type="button" data-k="${k}" aria-pressed="false">${k}x</button>`).join("")}</span>`;
    area.insertBefore(el, dock || null);
    const play = el.querySelector(".mb-play");
    play.onclick = () => clock.toggle();
    const scrub = el.querySelector(".mb-scrub");
    let wasPlaying = false;
    scrub.addEventListener("pointerdown", () => { wasPlaying = playing; playing = false; });
    scrub.addEventListener("input", () => {
      if (!current) return;
      axes[current.def.axis].t = clampT(current, snap(current, +scrub.value));
      updateBarTime(true);
      app.requestDraw();
    });
    scrub.addEventListener("change", () => {
      clock.seek(+scrub.value);
      if (wasPlaying) { wasPlaying = false; clock.play(); } else syncBar();
    });
    el.querySelector(".mb-speed").onclick = (ev) => {
      const b = ev.target.closest("button[data-k]");
      if (b) clock.setSpeed(+b.dataset.k);
    };
    // Space toggles play while the bar has focus (the map keeps its own keys).
    el.addEventListener("keydown", (ev) => {
      if (ev.key === " " && ev.target.tagName !== "BUTTON") { ev.preventDefault(); clock.toggle(); }
    });
    return el;
  }

  function syncBar() {
    if (!bar) bar = buildBar();
    if (!bar) return;
    const show = !!current;
    if (bar.hidden === show) {
      bar.hidden = !show;
      document.body.classList.toggle("motion-on", show);
    }
    if (!show) return;
    const play = bar.querySelector(".mb-play");
    play.innerHTML = playing ? PAUSE_SVG : PLAY_SVG;
    play.setAttribute("aria-label", playing ? TXT.pause : TXT.play);
    play.classList.toggle("on", playing);
    for (const b of bar.querySelectorAll(".mb-speed button")) {
      const on = +b.dataset.k === speedK;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", String(on));
    }
    const scrub = bar.querySelector(".mb-scrub");
    const r = rangeOf(current);
    scrub.disabled = !r;
    if (r) {
      scrub.min = String(r[0]);
      scrub.max = String(r[1]);
      scrub.step = current.def.step ? String(current.def.step) : "any";
    }
    scrub.setAttribute("aria-label", TXT.time);
    bar.dataset.axis = current.def.axis;
    updateBarTime(true);
  }

  let lastLabel = "", lastStatus = "", lastScrub = -1;
  function updateBarTime(force = false) {
    if (!bar || !current) return;
    const t = axes[current.def.axis].t ?? startOf(current);
    let label = "", status = "";
    try { label = current.def.label ? String(current.def.label(t) ?? "") : ""; } catch (err) { warn(current, "label", err); }
    try { status = current.def.status ? String(current.def.status(t) ?? "") : ""; } catch (err) { warn(current, "status", err); }
    if (force || label !== lastLabel) bar.querySelector(".mb-time").textContent = lastLabel = label;
    if (force || status !== lastStatus) {
      const st = bar.querySelector(".mb-status");
      st.textContent = lastStatus = status;
      st.hidden = !status;
    }
    const scrub = bar.querySelector(".mb-scrub");
    // The scrubber follows the clock unless the pointer holds it.
    if (document.activeElement !== scrub || force) {
      const r = rangeOf(current);
      if (r && (force || Math.abs(t - lastScrub) > (r[1] - r[0]) / 2000)) {
        scrub.value = String(t);
        lastScrub = t;
      }
    }
    scrub.setAttribute("aria-valuetext", label);
  }

  // --- URL -----------------------------------------------------------------------------------------------------
  app.hash?.register?.("t", {
    get() {
      if (!current) return pendingUrl ? formatT(pendingUrl.axis, pendingUrl.t) : null;
      const ax = axes[current.def.axis];
      return ax.committed == null ? null : formatT(current.def.axis, ax.committed);
    },
    set(v) {
      const p = v == null ? null : parseT(v);
      if (!p) return;
      if (current && current.def.axis === p.axis) {
        axes[p.axis].t = clampT(current, p.t);
        axes[p.axis].committed = axes[p.axis].t;
        playing = false;
        syncBar();
        app.requestDraw();
      } else {
        pendingUrl = p;
      }
    },
  });

  // --- selection, visibility -----------------------------------------------------------------------------------
  app.on?.("select", (sel) => {
    filterSel = sel || null;
    for (const e of layers.values()) if (e.on) applyFilter(e);
    app.requestDraw();
  });
  document.addEventListener("visibilitychange", () => {
    lastNow = null;
    if (!document.hidden && playing) app.requestDraw();
  });

  // A hover card for motion layers that give one (hit in screen css px), through a static layer that draws nothing.
  app.registerStaticLayer?.({
    id: "motion-hit", z: 86, snapshot: false,
    visible: () => [...layers.values()].some((e) => e.on && e.loaded && typeof e.def.hit === "function"),
    draw() {},
    hit(x, y) {
      const [mx, my] = app.cam.toScreen(x, y);
      const list = [...layers.values()].filter((e) => e.on && e.loaded && typeof e.def.hit === "function").sort((a, b) => b.order - a.order);
      for (const e of list) {
        let h = null;
        try { h = e.def.hit(mx, my); } catch (err) { warn(e, "hit", err); }
        if (h && h.html) return h;
      }
      return null;
    },
    tooltip: (item) => item.html,
  });
  app.registerOverlay(overlay);

  function register(def) {
    if (!def || !def.id || typeof def.draw !== "function" || typeof def.active !== "function") {
      throw new Error("app.motion.register({id, axis, range, speed, label, active, load, draw})");
    }
    if (!AXES.includes(def.axis)) throw new Error(`motion layer "${def.id}": axis must be one of ${AXES.join(", ")}`);
    const e = { def, on: false, order: 0, loaded: false, loading: null, lastT: null };
    layers.set(def.id, e);
    app.requestDraw();
    return () => {
      layers.delete(def.id);
      if (current === e) { current = null; poll(); }
      app.requestDraw();
    };
  }

  return {
    register,
    clock,
    particles,
    month,
    monthIso,
    hour,
    hourIso,
    hhmm,
    /** Re-read the layers' active() now (toggles call it through main's redraw anyway). */
    refresh() { poll(); app.requestDraw(); },
    // name: the toggle label; data: the web/data file (without .json) whose rules, sources and attribution the Almanac shows.
    layers: () => [...layers.values()].map((e) => ({ id: e.def.id, name: e.def.name ?? e.def.id, data: e.def.data ?? null, axis: e.def.axis, on: e.on, loaded: e.loaded, t: e.lastT })),
    stats: () => ({ ...stats }),
    get reducedMotion() { return reduce(); },
  };
}

export function install(app) {
  addCss();
  app.motion = createEngine(app);
  app.motion.panel = installPanel(app);
}
