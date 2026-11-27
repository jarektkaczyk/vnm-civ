// Languages: English (the source language) and Vietnamese. web/i18n/vi.json maps each English string (exact) to
// Vietnamese; pipeline/core/i18n.py reads the same catalogue and lists the keys that have no Vietnamese entry.
//
//   t("Median age")                               -> its Vietnamese entry on the Vietnamese page, the key in English
//   t("{name} in {year}", {name, year})          -> {placeholders}; numbers are formatted for the language
//   t.plural(n, {one: "{n} town", other: "{n} towns"})  -> Vietnamese has one form: the catalogue entry of "other"
//
// t() returns plain text: escape it before putting it into HTML (vars that are already HTML stay as they are).
// ISO dates inside any text ("2026-06-30", "2026-10") come out in the reader's form.
// The language is the <html lang> of the page: web/index.html is English, web/vi/index.html is Vietnamese. The catalogue
// loads with a top-level await, so every module that imports this one can call t() at import time.

const doc = typeof document !== "undefined" ? document : null;
export let LANG = doc?.documentElement?.lang?.toLowerCase().startsWith("vi") ? "vi" : "en";
/** Path from the page to the site root (web/): "" for the English page, "../" for /vi/. */
export const ROOT = LANG === "vi" ? "../" : "";
let LOCALE = LANG === "vi" ? "vi-VN" : "en-GB";
let catalogue = {};

if (LANG === "vi") {
  try {
    const r = await fetch(`${ROOT}i18n/vi.json`);
    if (r.ok) catalogue = await r.json();
  } catch (err) {
    console.warn("i18n: the Vietnamese catalogue did not load", err);
  }
}

/** Switch language and catalogue (tests, tools). The page itself never switches: each language has its own URL. */
export function setLocale(lang, cat = {}) {
  LANG = lang === "vi" ? "vi" : "en";
  LOCALE = LANG === "vi" ? "vi-VN" : "en-GB";
  catalogue = cat || {};
  NF.clear();
}

const NF = new Map();
function nf(opts) {
  const key = JSON.stringify(opts);
  let f = NF.get(key);
  if (!f) NF.set(key, (f = new Intl.NumberFormat(LOCALE, opts)));
  return f;
}
const fin = (v) => typeof v === "number" && Number.isFinite(v);

function fill(text, vars) {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (m, name) => {
    if (!(name in vars)) return m;
    const v = vars[name];
    if (v == null) return "";
    // Integers of up to four digits stay ungrouped (a year passed as a number must not read "2,024").
    if (typeof v === "number") return Number.isInteger(v) ? (Math.abs(v) < 1e4 ? String(v) : num(v)) : num(v, 1, { trim: true });
    return String(v);
  });
}

// Dates and years inside a key: "GUS, 2026-10 and 2025-12" -> "GUS, {d1} and {d2}" (pipeline/core/i18n.py
// date_pattern). A key with no exact entry is looked up by this pattern, so a monthly date change keeps one entry.
const DATE_TOKEN = /(?<![\w/.:=-])(?:\d{4}-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?|(?:19|20)\d{2})(?![\w/-])/g;

function lookup(k) {
  const hit = catalogue[k];
  if (hit != null) return hit;
  const dates = [];
  const pattern = k.replace(DATE_TOKEN, (m) => `{d${dates.push(m)}}`);
  const tpl = dates.length ? catalogue[pattern] : null;
  return typeof tpl === "string" ? tpl.replace(/\{d(\d+)\}/g, (m, i) => dates[i - 1] ?? m) : null;
}

/** The text of `key` in the page language, with {placeholders} filled and ISO dates formatted. */
export function t(key, vars) {
  if (key == null) return "";
  const k = String(key);
  const hit = LANG === "vi" ? lookup(k) : null;
  return localizeDates(fill(typeof hit === "string" && hit ? hit : k, vars));
}

/** CLDR plural category: English one/other; Vietnamese has only other. */
export function pluralCategory(n, lang = LANG) {
  if (lang === "vi") return "other";
  return n === 1 ? "one" : "other";
}

/** forms: the English {one, other}. {n} is the formatted count; other vars as in t(). */
t.plural = function plural(n, forms, vars) {
  let text = n === 1 ? forms.one : forms.other;
  if (LANG === "vi") {
    const hit = lookup(forms.other);
    if (typeof hit === "string" && hit) text = hit;
    else if (hit && typeof hit === "object") text = hit.other || text;
  }
  return localizeDates(fill(text || "", { n, ...vars }));
};

/** Whether the catalogue has `key` (always true in English). */
t.has = (key) => LANG !== "vi" || lookup(String(key)) != null;

// ---------------------------------------------------------------- numbers

const DASH = "\u2013";

/** A number with the language's grouping and decimal sign: 1,866,929 / 1 866 929; 12.5 / 12,5. */
export function num(v, digits = 0, { trim = false, signed = false } = {}) {
  if (!fin(v)) return DASH;
  return nf({ minimumFractionDigits: trim ? 0 : digits, maximumFractionDigits: digits, signDisplay: signed ? "exceptZero" : "auto" }).format(v);
}
/** A number to `n` significant digits (0.000456, 0.34, 12.3), with the language's decimal sign. */
export const sig = (v, n = 3) => (fin(v) ? nf({ maximumSignificantDigits: n }).format(v) : DASH);
export const int = (v) => (fin(v) ? num(Math.round(v)) : DASH);
/** A 0..1 share as a percentage: 16.3% / 16,3%. */
export const pct = (frac, digits = 1, opts = {}) => (fin(frac) ? num(frac * 100, digits, opts) + "%" : DASH);
/** A value already in percent (0..100). */
export const pct100 = (v, digits = 1, opts = {}) => (fin(v) ? num(v, digits, opts) + "%" : DASH);

// Short scales: English K, M, B, T; Vietnamese nghin, trieu, ty, nghin ty (after a no-break space).
const VI_K = "\u00a0ngh\u00ecn", VI_M = "\u00a0tri\u1ec7u", VI_B = "\u00a0t\u1ef7";
const SCALES = {
  en: [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]],
  vi: [[1e15, VI_M + VI_B], [1e12, VI_K + VI_B], [1e9, VI_B], [1e6, VI_M], [1e3, VI_K]],
};

/** 3.92T / 3,92 nghin ty; 12,8 trieu ty (1e15); 18.6M / 18,6 trieu; 12K / 12 nghin. Below 1,000 a plain integer. */
export function compact(n) {
  if (!fin(n)) return DASH;
  const a = Math.abs(n);
  for (const [base, suffix] of SCALES[LANG]) {
    if (a < base) continue;
    const v = n / base;
    const digits = base === 1e3 ? (a >= 1e5 ? 0 : 1) : base === 1e12 ? (a >= 1e13 ? 1 : 2) : a >= base * 100 ? 0 : 1;
    return num(v, digits, { trim: base === 1e3 }) + suffix;
  }
  return num(Math.round(n));
}

const DONG = "\u00a0\u20ab";
/** Money in Vietnamese dong, short: 120M dong / 120 trieu dong. */
export const money = (n) => (fin(n) ? compact(n) + DONG : DASH);
/** Money in dong, in full. */
export const dong = (n) => (fin(n) ? int(n) + DONG : DASH);
/** Money in US dollars, short: $4.7K. */
export const usd = (n) => (fin(n) ? "$" + compact(n) : DASH);

/** Population, short: 1.9M / 1,9 trieu; 28K / 28 nghin. */
export function popShort(n) {
  if (!fin(n)) return DASH;
  if (n >= 1e7) return num(Math.round(n / 1e6)) + (LANG === "vi" ? VI_M : "M");
  if (n >= 1e6) return num(n / 1e6, 1) + (LANG === "vi" ? VI_M : "M");
  return num(Math.round(n / 1e3)) + (LANG === "vi" ? VI_K : "K");
}

// ---------------------------------------------------------------- dates

const DF = {};
function df(kind) {
  const k = LOCALE + kind;
  if (!DF[k]) {
    const opts = kind === "day" ? { day: "numeric", month: "long", year: "numeric" } : { month: "long", year: "numeric" };
    DF[k] = new Intl.DateTimeFormat(LOCALE, { ...opts, timeZone: "UTC" });
  }
  return DF[k];
}

/** "2026-06-30" -> 30 June 2026 / 30 czerwca 2026; "2026-10" -> October 2026 / pazdziernik 2026; "2025" -> 2025. */
export function date(iso) {
  if (iso == null) return "";
  const s = String(iso);
  let m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (m) return df("day").format(new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])));
  m = /^(\d{4})-(\d{2})$/.exec(s);
  if (m) return df("month").format(new Date(Date.UTC(+m[1], +m[2] - 1, 1)));
  return s;
}

const ISO_DAY = /(?<![\w/.:=-])(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?![\w/-])/g;
const ISO_MONTH = /(?<![\w/.:=-])(\d{4})-(0[1-9]|1[0-2])(?![\w/-])/g;

/** Every ISO date inside a text, formatted for the reader. Links and file names are left alone. */
export function localizeDates(text) {
  if (typeof text !== "string" || text.indexOf("-") < 0) return text;
  return text.replace(ISO_DAY, (m) => date(m)).replace(ISO_MONTH, (m) => date(m));
}

// ---------------------------------------------------------------- the other language

/** The URL of the current view in `lang`: same page, same hash. */
export function langHref(lang, loc = typeof location !== "undefined" ? location : null) {
  if (!loc) return lang === "vi" ? "vi/" : "./";
  const path = loc.pathname;
  const isVi = /\/vi(\/|$)/.test(path);
  let target = path;
  if (lang === "vi" && !isVi) target = path.replace(/\/?(index\.html)?$/, "/") + "vi/";
  if (lang === "en" && isVi) target = path.replace(/\/vi(\/(index\.html)?)?$/, "/");
  return target + (loc.search || "") + (loc.hash || "");
}

export { LOCALE };
