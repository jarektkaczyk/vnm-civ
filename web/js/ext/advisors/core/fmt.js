// Number formatting for the advisor kit, built on web/js/format.js.
// Formats follow lenses.json / counties.json: int | pln | pct (0..1 fraction) | float | minutes | years | km2 | text,
// plus a few of our own: money (compact dong), signed (signed %), lq (x1.23), mw, count, ratio (x4.2).
// "vnd" is Vietnamese dong, "usd" US dollars.
import { compact, dollars, int, money, pct } from "../../../format.js";
import { t, num, sig, LANG } from "../../../i18n.js";
import { fin } from "./util.js";

export { compact, dollars, int, money, pct };

const DASH = "\u2013";
const MINUS = "\u2212";
const TIMES = "\u00d7";
const ZL = "\u00a0\u20ab";
const KM2 = "\u00a0km\u00b2";

export const signedPct = (g, d = 1) => (fin(g) ? `${g >= 0 ? "+" : MINUS}${num(Math.abs(g * 100), d)}%` : DASH);
const UNIT3 = LANG === "vi" ? ["\u00a0ngh\u00ecn t\u1ef7", "\u00a0t\u1ef7", "\u00a0tri\u1ec7u", "\u00a0ngh\u00ecn"] : ["T", "B", "M", "K"];

// Counts to three significant figures (1.12M vs 1.11M rather than 1.1M twice).
export function count3(n) {
  if (!fin(n)) return DASH;
  const a = Math.abs(n);
  const sig = (d, unit) => num(n / d, a / d >= 100 ? 0 : a / d >= 10 ? 1 : 2) + unit;
  if (a >= 1e12) return sig(1e12, UNIT3[0]);
  if (a >= 1e9) return sig(1e9, UNIT3[1]);
  if (a >= 1e6) return sig(1e6, UNIT3[2]);
  if (a >= 1e4) return sig(1e3, UNIT3[3]);
  return int(n);
}

export const mw = (v) => (fin(v) ? (Math.abs(v) >= 10000 ? `${num(v / 1000, v >= 1e5 ? 0 : 1)}\u00a0GW` : `${int(v)}\u00a0MW`) : DASH);

const isPln = (f) => f === "vnd";

/** Full-ish text for a value in a given format (tables, tooltips). */
export function fmtValue(format, v, unit) {
  if (format === "text") return v == null || v === "" ? DASH : String(v);
  if (!fin(v)) return DASH;
  if (format === "usd") return dollars(v);
  if (isPln(format)) return money(v);
  switch (format) {
    case "int": case "count": return Math.abs(v) >= 1e6 ? count3(v) : int(v);
    case "money": return money(v);
    case "pct": return pct(v);
    case "signed": return signedPct(v);
    case "lq": return `${TIMES}${num(v, 2)}`;
    case "ratio": return `${TIMES}${num(v, 1)}`;
    case "minutes": return t("{v} min", { v: num(v, 1) });
    case "years": return t("{v} yrs", { v: num(v, 1) });
    case "km2": return `${int(v)}${KM2}`;
    case "mw": return mw(v);
    case "float": return Math.abs(v) >= 100 ? int(v) : Math.abs(v) >= 10 ? num(v, 1) : num(v, 2);
    default:
      if (unit === "MW") return mw(v);
      return Math.abs(v) >= 1e4 ? count3(v) : Math.abs(v) >= 100 ? int(v) : num(v, 2);
  }
}

/** Compact text for a table cell, so numbers fit narrow columns: 121K zl, 9.4M, +2.1%, 12.3%, 4,210 km2. */
export function fmtCell(format, v, unit) {
  if (format === "text") return v == null || v === "" ? DASH : String(v);
  if (!fin(v)) return DASH;
  const a = Math.abs(v);
  if (format === "usd") return dollars(v);
  if (isPln(format)) return `${count3(v)}${ZL}`;
  switch (format) {
    case "int": case "count": return a >= 1e4 ? count3(v) : int(v);
    case "money": return money(v);
    case "km2": return a >= 1e5 ? `${count3(v)}${KM2}` : `${int(v)}${KM2}`;
    case "float": return a >= 1e4 ? count3(v) : fmtValue(format, v, unit);
    default: return fmtValue(format, v, unit);
  }
}

/** Short text for axis ticks and chips. */
export function fmtShort(format, v) {
  if (!fin(v)) return DASH;
  if (isPln(format)) return money(v);
  switch (format) {
    case "money": return money(v);
    case "pct": return `${num(v * 100, Math.abs(v) < 0.1 && v !== 0 ? 1 : 0, { trim: true })}%`;
    case "signed": return `${v > 0 ? "+" : v < 0 ? MINUS : ""}${num(Math.abs(v * 100), 1, { trim: true })}%`;
    case "lq": case "ratio": return `${TIMES}${num(v, 1, { trim: true })}`;
    case "mw": return mw(v);
    case "minutes": case "years": return num(v, 0);
    default: return Math.abs(v) >= 1000 ? compact(v) : sig(v, 3);
  }
}

/** Parse "1.5M", "250k", "12%", "-3%" (Vietnamese: "1,5M", "1.500", "12,5%") into a number in the
 * field's units (pct -> fraction). */
const MULT = { "": 1, k: 1e3, m: 1e6, b: 1e9, t: 1e12 };
export function parseNum(text, format) {
  if (text == null) return null;
  let s = String(text).trim().replace(/\u20ab|vnd/gi, "").replace(/^\u2212/, "-");
  // Vietnamese groups with dots and writes a decimal comma; English groups with commas.
  s = LANG === "vi" ? s.replace(/[\s\u00a0]/g, "").replace(/\.(?=\d{3}(?!\d))/g, "").replace(",", ".") : s.replace(/[,\s\u00a0]/g, "");
  if (!s) return null;
  let isPct = false;
  if (s.endsWith("%")) { isPct = true; s = s.slice(0, -1); }
  const m = /^(-?\d*\.?\d+)(k|m|b|t)?$/i.exec(s);
  if (!m) return null;
  let v = parseFloat(m[1]) * MULT[(m[2] || "").toLowerCase()];
  if ((format === "pct" || format === "signed") && (isPct || Math.abs(v) > 1)) v /= 100;
  return v;
}
