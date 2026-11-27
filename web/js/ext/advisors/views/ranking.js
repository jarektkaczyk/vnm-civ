// A ranking advisor: national tiles, a map picker over its lenses, and for each measure the leading and trailing
// provinces as linked bar lists. Each advisor that uses it passes a spec (index.js ADVISORS[].spec):
//   {tiles: [{label, value(nat, data), sub}], measures: [{key, lens, title, note, fmt, asc?, diverging?}], sources}
import { esc, fin } from "../core/util.js";
import { fmtValue } from "../core/fmt.js";
import { barList } from "../core/charts.js";
import { section, tiles, segmented, mapPicker, sourcesHtml, topBy } from "../core/view.js";
import { rowsHighlight } from "../core/data.js";
import { t } from "../../../i18n.js";

export function makeRanking(spec) {
  return {
    mount(ctx) {
      const { app, data, el, link } = ctx;
      const lv = data.levels[spec.level || "states"];
      const nat = data.nat;
      const measures = spec.measures.filter((m) => lv.field(m.key) && lv.rows.some((r) => fin(r.v[m.key])));
      if (spec.tiles?.length) {
        el.insertAdjacentHTML("beforeend", tiles(spec.tiles.map((x) => ({ label: x.label, value: x.value(nat, data), sub: x.sub || "", color: x.color }))));
      }
      const hasLens = (id) => !!app.lensById?.get(id);
      const lensMeasures = measures.filter((m) => m.lens && hasLens(m.lens));
      if (lensMeasures.length) {
        const mapRow = document.createElement("div");
        mapRow.className = "adv-sec adv-mapsec";
        el.appendChild(mapRow);
        mapPicker(ctx, mapRow, {
          value: lensMeasures[0].lens,
          options: [
            ...lensMeasures.map((m) => ({ value: m.lens, label: m.short || lv.field(m.key).label, lens: () => m.lens })),
            { value: "terrain", label: t("Terrain"), lens: () => null },
          ],
        });
      }
      for (const m of measures) {
        const f = lv.field(m.key);
        const fmt = (v) => (m.fmt ? m.fmt(v) : fmtValue(f.format, v, f.unit));
        const body = section(el, { title: m.title || f.label, note: esc(m.note || f.description || "") });
        const host = document.createElement("div");
        let dir = "top";
        const draw = () => {
          host.innerHTML = "";
          const asc = dir === "bottom" ? !m.asc : !!m.asc;
          const list = topBy(lv.rows, (r) => r.v[m.key], { n: m.n || 8, asc });
          const max = Math.max(...lv.rows.map((r) => Math.abs(r.v[m.key] ?? 0)));
          barList(host, {
            rows: list.map((x) => ({ key: x.r.key, label: x.r.name, sub: "", value: x.v, text: fmt(x.v), row: x.r,
              tone: m.diverging ? (x.v >= 0 ? "good" : "bad") : undefined })),
            max, diverging: !!m.diverging,
            onHover: (r) => link.hover(r ? rowsHighlight(lv, [r.row]) : null),
            onClick: (r) => r && lv.focus(r.row),
          });
        };
        segmented(body, {
          label: t("Show"), value: dir,
          options: [{ value: "top", label: m.topLabel || t("Highest") }, { value: "bottom", label: m.bottomLabel || t("Lowest") }],
          onChange: (v) => { dir = v; draw(); },
        });
        body.appendChild(host);
        draw();
      }
      const srcs = [...new Set(measures.map((m) => lv.field(m.key).source).filter(Boolean))];
      el.insertAdjacentHTML("beforeend", sourcesHtml(data, srcs, spec.caveats || []));
      return {};
    },
  };
}
