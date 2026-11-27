// Number formatting for the banners: format.js's compact helpers with a roll-over fix, so a value that rounds up to
// the next unit reads "1.0M" rather than "1000K" (e.g. a town of 999,600 people).
import { compact as baseCompact, popShort as basePopShort } from "../format.js";
import { LANG } from "../i18n.js";

const UNITS = LANG === "vi"
  ? [[1e12, "\u00a0ngh\u00ecn t\u1ef7"], [1e9, "\u00a0t\u1ef7"], [1e6, "\u00a0tri\u1ec7u"], [1e3, "\u00a0ngh\u00ecn"]]
  : [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]];
const ROLL = new RegExp(`^-?1(?:\\u00a0| |[.,])?000(?:[.,]0+)?(${UNITS.map(([, u]) => u).join("|")})$`);

/** Rounds n up to the next unit when its compact form would print 1000 of the current one. */
function rollover(n, fmt) {
  if (n == null || Number.isNaN(n)) return fmt(n);
  const s = fmt(n);
  const m = ROLL.exec(s);
  if (!m) return s;
  const i = UNITS.findIndex(([, u]) => u === m[1]);
  return i > 0 ? fmt(Math.sign(n) * UNITS[i - 1][0]) : s;
}

export const compact = (n) => rollover(n, baseCompact);
export const popShort = (n) => rollover(n, basePopShort);
