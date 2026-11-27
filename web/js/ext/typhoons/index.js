// Typhoon tracks, year by year (a motion layer on the year axis): every tropical storm of the year on the clock
// (typhoons.json, IBTrACS since 1981), its track drawn up to where the storm is at that moment of the year and
// coloured by its wind, with the eye as a dot. The tracks of the year stay on the map until the year ends.
import { esc } from "../../format.js";
import { t, int } from "../../i18n.js";

const SPEED = 0.5; // years per second at 1x (one season in 2 s)
const COLORS = { td: "rgba(150,200,220,.75)", ts: "rgba(240,200,90,.9)", ty: "rgba(235,90,60,.95)" };

export function install(app) {
  const motion = app.motion;
  if (!motion) return;
  let on = false, doc = null, loading = null, byYear = new Map(), years = [1981, 2025];
  const load = () => (loading ??= app.loadData("typhoons").then((d) => {
    if (!d?.storms?.length) return;
    doc = d;
    years = d.years;
    byYear = new Map();
    for (const s of d.storms) {
      if (!byYear.has(s.year)) byYear.set(s.year, []);
      byYear.get(s.year).push(s);
    }
  }));
  const tyKt = () => doc?.typhoon_kt || 64;
  const color = (kt) => (kt == null || kt < 0 ? COLORS.td : kt >= tyKt() ? COLORS.ty : kt >= 34 ? COLORS.ts : COLORS.td);
  let lastDrawn = [];

  motion.register({
    id: "typhoons",
    name: t("Typhoons"),
    data: "typhoons",
    axis: "year",
    get range() { return [years[0], years[1] + 0.999]; },
    get start() { return motion.reducedMotion ? years[1] : years[0]; },
    speed: SPEED,
    loop: false,
    label: (tt) => String(Math.min(Math.floor(tt), years[1])),
    status(tt) {
      const list = byYear.get(Math.floor(tt)) || [];
      const f = tt - Math.floor(tt);
      const seen = list.filter((s) => s.pts[3] <= f);
      const ty = seen.filter((s) => (s.peak_kt ?? 0) >= tyKt()).length;
      return seen.length ? t("{n} storms, {ty} typhoons", { n: seen.length, ty }) : "";
    },
    active: () => on,
    load,
    draw(ctx, vp, tt, o) {
      if (!doc) return 0;
      const y = Math.floor(tt), f = tt - y;
      const list = byYear.get(y) || [];
      const px = 1 / vp.s;
      let dots = 0;
      lastDrawn = [];
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, app.w.raw.width, app.w.raw.height); // tracks stop at the edge of the map
      ctx.clip();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      // The season before fades out over the first months of the year.
      const fade = 0.4 * Math.max(0, 1 - f * 3);
      if (fade > 0.02) {
        ctx.globalAlpha = fade;
        ctx.lineWidth = Math.max(1.2, Math.min(3, 1.6 * vp.s)) * px;
        for (const s of byYear.get(y - 1) || []) {
          const P = s.pts;
          for (let k = 0; k + 4 < P.length; k += 4) {
            ctx.strokeStyle = color(Math.max(P[k + 2], P[k + 6]));
            ctx.beginPath();
            ctx.moveTo(P[k], P[k + 1]);
            ctx.lineTo(P[k + 4], P[k + 5]);
            ctx.stroke();
          }
        }
        ctx.globalAlpha = 1;
      }
      for (const s of list) {
        const P = s.pts;
        if (P[3] > f) continue;
        let k = 0;
        ctx.lineWidth = Math.max(1.6, Math.min(4, 2.2 * vp.s)) * px;
        for (; k + 4 < P.length && P[k + 7] <= f; k += 4) {
          ctx.strokeStyle = color(Math.max(P[k + 2], P[k + 6]));
          ctx.beginPath();
          ctx.moveTo(P[k], P[k + 1]);
          ctx.lineTo(P[k + 4], P[k + 5]);
          ctx.stroke();
        }
        // The eye: between point k and the next, at the time of year on the clock.
        let ex = P[k], ey = P[k + 1], kt = P[k + 2];
        const done = k + 4 >= P.length;
        if (!done) {
          const a = P[k + 3], b = P[k + 7];
          const u = b > a ? Math.max(0, Math.min(1, (f - a) / (b - a))) : 0;
          ex = P[k] + (P[k + 4] - P[k]) * u;
          ey = P[k + 1] + (P[k + 5] - P[k + 1]) * u;
          ctx.strokeStyle = color(Math.max(P[k + 2], P[k + 6]));
          ctx.beginPath();
          ctx.moveTo(P[k], P[k + 1]);
          ctx.lineTo(ex, ey);
          ctx.stroke();
        }
        lastDrawn.push({ s, x: ex, y: ey });
        if (done) continue;
        const r = (kt >= tyKt() ? 6 : 4) * px;
        ctx.fillStyle = color(kt);
        ctx.beginPath();
        ctx.arc(ex, ey, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(255,250,235,.9)";
        ctx.lineWidth = 1.2 * px;
        ctx.stroke();
        dots++;
      }
      ctx.restore();
      return dots;
    },
    hit(mx, my) {
      if (!lastDrawn.length) return null;
      const cam = app.cam;
      let best = null, bd = 14;
      for (const d of lastDrawn) {
        const [sx, sy] = cam.toScreen(d.x, d.y);
        const dd = Math.hypot(sx - mx, sy - my);
        if (dd < bd) { bd = dd; best = d; }
      }
      if (!best) return null;
      const s = best.s;
      const name = s.name || t("Unnamed storm");
      return { html: `<b>${esc(name)}</b> \u00b7 ${esc(String(s.season))}<br>${s.peak_kt == null ? "" : esc(t("Peak wind {kt} knots", { kt: int(s.peak_kt) }))}` };
    },
  });

  app.ui.addMapToggle({
    id: "typhoons", label: t("Typhoons"), icon: "l-disasters", default: false, menu: false,
    title: t("Storm tracks year by year since 1981"),
    get: () => on,
    set: (v) => {
      on = !!v;
      if (on) load().then(() => app.requestDraw());
      app.requestDraw();
    },
  });
}
