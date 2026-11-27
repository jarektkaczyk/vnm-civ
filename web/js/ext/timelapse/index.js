// Lenses that play on the shared motion clock (app.motion):
//
// * Night lights by year (lens nightlights, year axis): the average night-time light of every year 2014-2024 per
//   hex (timelapse.json), on the scale of the newest year, so the deltas, the coast and the towns brighten year by
//   year.
//
// The lens is the motion layer's switch: the layer is on while its lens is shown. It swaps the lens's `values` for
// the year on the clock and recolours the map only when the year changes.
import { esc } from "../../format.js";
import { t, num } from "../../i18n.js";
import { recolour, placeOf } from "./legend.js";

const SPEED = 1.5; // years per second at 1x (the eleven years in about 7 s)

export function install(app) {
  const motion = app.motion;
  if (!motion) return;
  const lens = app.lensById.get("nightlights");
  if (!lens) return;
  const size = app.w.grid.size;
  const own = lens.values;
  const arr = new Array(size).fill(null);
  let doc = null, shown = -1, loading = null, wanted = null;
  const years = () => doc?.years || [2014, 2024];
  const first = () => years()[0], last = () => years()[years().length - 1];
  const load = () => (loading ??= app.loadData("timelapse").then((d) => {
    const nl = d?.nightlights;
    if (nl?.years?.length) doc = nl;
  }));
  const idx = (tt) => (doc ? Math.max(0, Math.min(doc.years.length - 1, Math.floor(tt) - doc.years[0])) : -1);
  motion.register({
    id: "nightlights-years",
    name: t("Night lights by year"),
    data: "timelapse",
    axis: "year",
    get range() { return [first(), last()]; },
    get start() { return motion.reducedMotion ? last() : first(); },
    step: 1,
    speed: SPEED,
    loop: false,
    label: (tt) => String(Math.min(Math.floor(tt), last())),
    active: () => app.state.lens === lens,
    load,
    draw(ctx, vp, tt) {
      if (wanted != null && motion.clock.layer === "nightlights-years") {
        motion.clock.seek(wanted);
        wanted = null;
      }
      const k = idx(tt);
      if (k < 0 || (k === shown && lens.values === arr)) return 0;
      shown = k;
      arr.fill(null);
      const row = doc.values[k];
      doc.cells.forEach((c, j) => { arr[c] = row[j]; });
      lens.values = arr;
      recolour(app, lens, t("Average night-time light seen from space, {year}.", { year: String(doc.years[k]) }));
      return 0;
    },
    hit(mx, my) {
      if (!doc || shown < 0) return null;
      const cell = app.cellAt(mx, my);
      if (cell < 0 || app.w.raw.owner[cell] < 0) return null;
      const v = arr[cell];
      return {
        html: `<b>${esc(placeOf(app, cell, t))}</b><br>${esc(String(doc.years[shown]))}: ${v == null ? esc(t("no data")) : `<b>${esc(num(v, 1))}</b> ${esc(t("nW/cm\u00b2/sr"))}`}`,
      };
    },
  });
  app.on("lens", (l) => {
    if (l === lens) wanted = motion.reducedMotion ? last() : first();
    else if (lens.values !== own) { lens.values = own; shown = -1; }
  });
}
