// Number formats for the page language (web/js/i18n.js holds the language and the Intl formatters).
import { compact, money, dong, usd, int, pct, popShort } from "./i18n.js";

export { compact, money, dong, usd, int, pct, popShort };
// Money is Vietnamese dong (VND), written after the number, or US dollars where a source publishes dollars.
export const dollars = usd;

export function yieldValue(y, v) {
  return y.unit === "vnd" ? money(v) : y.unit === "usd" ? usd(v) : compact(v);
}

export const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
