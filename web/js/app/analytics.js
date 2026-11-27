// Anonymous, cookieless usage counts (PostHog EU) and the Cloudflare Web Analytics beacon. Loaded by index.html.
//
//   track(name, props)   queue an event; a no-op when analytics is off. Props are small enums and numbers only:
//                        never names of people, free text the user typed, or anything that identifies a visitor.
//
// Nothing loads on localhost, 127.0.0.1 or file:, or under automation (navigator.webdriver); PostHog also needs
// POSTHOG_KEY and the beacon CF_BEACON_TOKEN in config.js. Both scripts are fetched after the first map frame (app)
// or after the load event (atlas pages). PostHog keeps state in memory only (no cookies, no localStorage), never
// records sessions, never autocaptures clicks and never calls identify. Its automatic $pageview and $pageleave stay
// on (they count visitors), but before_send rewrites every URL property to origin + path + hash, keeping only utm_*
// query parameters, so a query such as ?email=... never leaves the page. When another site frames the page (for
// example a gallery of country maps), before_send also adds embedded_in: the framing site's host name, or "unknown"
// where the browser hides it (Firefox; a parent that strips the referrer). Add ?analytics=debug to a URL to print
// each event to the console.
//
// In the app, most events come from the extension API (window.__app events) and a few delegated DOM listeners, so
// the modules that own those actions stay untouched. Search and the Explorer call track() directly.
import { POSTHOG_KEY, POSTHOG_HOST, POSTHOG_ASSETS, CF_BEACON_TOKEN, CF_BEACON_SRC } from "./config.js";

/** origin + path + hash of an absolute URL, with only its utm_* query parameters. Other strings pass unchanged. */
export function sanitizeUrl(value) {
  if (typeof value !== "string" || !/^https?:\/\//i.test(value)) return value;
  try {
    const u = new URL(value);
    const keep = new URLSearchParams();
    for (const [k, v] of u.searchParams) if (/^utm_/i.test(k)) keep.append(k, v);
    const q = keep.toString();
    return `${u.origin}${u.pathname}${q ? `?${q}` : ""}${u.hash}`;
  } catch {
    return value.replace(/[?#].*$/, "");
  }
}

function sanitizeProps(props) {
  if (!props || typeof props !== "object") return props;
  for (const [k, v] of Object.entries(props)) if (typeof v === "string") props[k] = sanitizeUrl(v);
  return props;
}

/** The host name of the site that frames this page, "unknown" when framed by a hidden site, or null when not framed. */
export function embedHost(win = globalThis) {
  try {
    if (!win || win.top === win.self) return null;
  } catch {
    /* a cross-origin top that throws on access: still framed */
  }
  const host = (url) => { try { return new URL(url).hostname || null; } catch { return null; } };
  return host(win.location?.ancestorOrigins?.[0]) || host(win.document?.referrer) || "unknown";
}

const EMBED = embedHost();

/** PostHog before_send: strip query text from $current_url, $referrer and every other URL-valued property. */
export function sanitizeEvent(event) {
  if (!event || typeof event !== "object") return event;
  if (EMBED && event.properties && typeof event.properties === "object") event.properties.embedded_in = EMBED;
  sanitizeProps(event.properties);
  sanitizeProps(event.$set);
  sanitizeProps(event.$set_once);
  return event;
}

const CONFIG = {
  api_host: POSTHOG_HOST,
  persistence: "memory",
  cookieless_mode: "always",
  disable_session_recording: true,
  autocapture: false,
  capture_pageview: true,
  capture_pageleave: true,
  disable_surveys: true,
  person_profiles: "identified_only",
  before_send: sanitizeEvent,
};

const loc = globalThis.location || { protocol: "file:", hostname: "", search: "", hash: "" };
const debug = /[?&]analytics=debug\b/.test(loc.search || "");
const LOCAL = /^(localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0)$/;
const blocked = () => loc.protocol === "file:" || LOCAL.test(loc.hostname || "") || !!globalThis.navigator?.webdriver;
const enabled = !!POSTHOG_KEY && !blocked();
const beaconEnabled = !!CF_BEACON_TOKEN && !blocked();
const entryHash = String(loc.hash || "");
let ph = null; // the PostHog stub (queues calls until the script arrives), then the real client
let loading = false;
const last = new Map(); // event name -> {sig, t}: drops exact repeats within a short window

const slug = (s) => String(s || "").replace(/ł/g, "l").replace(/Ł/g, "L").normalize("NFD").replace(/[̀-ͯ]/g, "")
  .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

function clean(props) {
  const out = {};
  for (const [k, v] of Object.entries(props || {})) {
    if (typeof v === "number" && Number.isFinite(v)) out[k] = v;
    else if (typeof v === "boolean") out[k] = v;
    else if (typeof v === "string" && v) out[k] = v.slice(0, 64);
  }
  return out;
}

/** Record one event. Safe to call anywhere, any time; never throws. */
export function track(name, props = {}, { dedupeMs = 1500 } = {}) {
  try {
    const p = clean(props);
    const sig = JSON.stringify(p);
    const now = Date.now();
    const prev = last.get(name);
    if (prev && prev.sig === sig && now - prev.t < dedupeMs) return;
    last.set(name, { sig, t: now });
    if (debug) console.info("[analytics]", name, p);
    if (!enabled) return;
    stub().capture(name, p);
  } catch {
    /* analytics must never break the page */
  }
}

// The documented PostHog snippet, minus its inline script: a queue that array.js replays on load.
function stub() {
  if (ph) return ph;
  const q = [];
  q.__SV = 1;
  q._i = [[POSTHOG_KEY, CONFIG, "posthog"]];
  q.people = [];
  for (const m of ["capture", "register", "register_once", "unregister", "opt_out_capturing", "opt_in_capturing"]) {
    q[m] = (...args) => { q.push([m, ...args]); };
  }
  globalThis.posthog = q;
  ph = q;
  return q;
}

// Cloudflare Web Analytics, under the same guard as PostHog. Its token lives in config.js only.
let beaconLoaded = false;
function loadBeacon() {
  if (!beaconEnabled || beaconLoaded || typeof document === "undefined") return;
  beaconLoaded = true;
  const s = document.createElement("script");
  s.src = CF_BEACON_SRC;
  s.defer = true;
  s.setAttribute("data-cf-beacon", JSON.stringify({ token: CF_BEACON_TOKEN }));
  document.body.appendChild(s);
}

function load() {
  loadBeacon();
  if (!enabled || loading) return;
  loading = true;
  stub();
  const s = document.createElement("script");
  s.src = `${POSTHOG_ASSETS}/static/array.js`;
  s.async = true;
  s.crossOrigin = "anonymous";
  s.onload = () => { if (globalThis.posthog && !Array.isArray(globalThis.posthog)) ph = globalThis.posthog; };
  document.head.appendChild(s);
}

const idle = (fn) => (globalThis.requestIdleCallback ? requestIdleCallback(fn, { timeout: 3000 }) : setTimeout(fn, 1200));

function viewportClass() {
  const w = globalThis.innerWidth || 0;
  return w <= 700 ? "phone" : w <= 1100 ? "tablet" : "desktop";
}

/** What a landing URL's hash asks for: the most specific key wins. */
export function entryKind(hash) {
  const p = new URLSearchParams(String(hash || "").replace(/^#/, ""));
  if (p.get("advisor")) return "advisor";
  if (p.get("city")) return "city";
  if (p.get("state")) return "state";
  if (p.get("lens")) return "lens";
  if (p.get("layers")) return "layers";
  if (p.get("at")) return "camera";
  return "none";
}

function watchApp() {
  const ready = () => globalThis.__app && !document.getElementById("loading");
  const go = () => {
    const app = globalThis.__app;
    requestAnimationFrame(() => {
      const kind = entryKind(entryHash);
      track("app_loaded", { ms: Math.round(performance.now()), viewport: viewportClass(), entry: kind });
      if (kind !== "none") track("deep_link_landing", { kind });
      idle(load);
    });
    app.on("lens", (lens) => { if (lens?.id) track("lens_opened", { lens: lens.id }); });
    app.on("mode", (e) => {
      if (e?.name === "advisor") {
        track("advisor_opened", { advisor: e.params?.id || "council" });
      }
    });
    // The Almanac opens from several places; every path goes through pedia.open.
    const pedia = app.pedia;
    if (pedia && typeof pedia.open === "function") {
      const open = pedia.open.bind(pedia);
      pedia.open = (page, ...rest) => {
        track("almanac_opened", { page: page || "About this map" });
        return open(page, ...rest);
      };
    }
    document.addEventListener("click", (e) => {
      const t = e.target instanceof Element ? e.target : null;
      if (!t) return;
      const nav = t.closest("#pedia-nav button[data-page]");
      if (nav) track("almanac_opened", { page: nav.dataset.page });
      if (t.closest("#btn-share")) track("share_clicked", {});
      const res = t.closest("#btn-res");
      const row = t.closest("#map-layers-pop [data-toggle]");
      if (res || row) {
        // after the app's own handler has flipped the switch
        setTimeout(() => {
          if (res) track("map_layer_toggled", { layer: "resources", on: !!app.state?.showResources }, { dedupeMs: 0 });
          else {
            const id = row.dataset.toggle;
            const on = app.ui?.mapToggles?.().find((x) => x.id === id)?.on;
            track("map_layer_toggled", { layer: id, on: !!on }, { dedupeMs: 0 });
          }
        }, 0);
      }
    }, true);
  };
  if (ready()) return go();
  const mo = new MutationObserver(() => {
    if (ready()) {
      mo.disconnect();
      go();
    }
  });
  mo.observe(document.body, { childList: true });
}

function start() {
  if (typeof document === "undefined") return;
  if (document.getElementById("map")) watchApp();
}

start();
