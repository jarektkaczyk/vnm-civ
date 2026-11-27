// Hover tooltips for Polish map layers. Values come from the layer files and every string is escaped.
import { esc, compact, int } from "../../format.js";
import { t, pct100 } from "../../i18n.js";
import { FORT_KINDS, fortKind, WONDER_KINDS } from "../../render/art/sites.js";

const muted = (s) => `<span class="muted">${s}</span>`;
const num = (n) => (n == null || !Number.isFinite(n) ? "-" : compact(n));
const join = (...xs) => xs.filter((x) => x != null && x !== "").map(esc).join(" &middot; ");
// Data prose (wonders.json, military.json ...) in the page language; empty values stay empty.
const tr = (s) => (s ? t(s) : s);
// A translated line with HTML pieces: pass {key: "{key}"} to t() for them, then the escaped text takes vars[key].
const html = (text, vars) => esc(text).replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
const bold = (s) => `<b>${esc(s)}</b>`;

const PORT_TYPE = { seaport: t("Seaport"), lng_terminal: t("LNG terminal"), coastal: t("Seaport"), small: t("Local port") };
const STATUS = {
  operating: t("Operating"), under_construction: t("Under construction"), planned: t("Planned"), forming: t("Forming"),
  active: t("Active"), act: t("Active"),
};

export const tips = {
  port(p) {
    const lines = [`<b>${esc(tr(p.name))}</b> ${muted(join(PORT_TYPE[p.type] || t("Port"), p.state))}`];
    if (p.cargo_kt != null) {
      const n = num(p.cargo_kt * 1000);
      lines.push(p.year
        ? html(t("{n} tonnes handled ({year})", { n: "{n}", year: String(p.year) }), { n: bold(n) })
        : html(t("{n} tonnes handled", { n: "{n}" }), { n: bold(n) }));
    }
    if (p.international_kt != null) lines.push(esc(t("International cargo {n} tonnes", { n: num(p.international_kt * 1000) })));
    if (p.teu != null) lines.push(`${esc(num(p.teu))} TEU`);
    if (p.status && p.status !== "operating") lines.push(muted(esc(STATUS[p.status] || p.status)));
    return lines.join("<br>");
  },
  airport(a) {
    const code = a.iata || a.icao;
    const title = code ? `${esc(code)} &middot; ${esc(t(a.name))}` : esc(t(a.name));
    const lines = [`<b>${title}</b> ${muted(join(a.state))}`];
    if (a.passengers != null) {
      const v = { n: "{n}", year: a.year ? String(a.year) : "" };
      let text;
      if (a.passengers_prev > 0) {
        v.change = pct100((a.passengers / a.passengers_prev - 1) * 100, 1);
        text = a.year ? t("{n} passengers ({year}), {change} from the prior year", v) : t("{n} passengers, {change} from the prior year", v);
      } else {
        text = a.year ? t("{n} passengers ({year})", v) : t("{n} passengers", v);
      }
      lines.push(html(text, { n: bold(num(a.passengers)) }));
    }
    if (a.freight_t != null) lines.push(esc(t("{n} tonnes of freight and mail", { n: num(a.freight_t) })));
    if (a.status && a.status !== "operating") {
      let status = STATUS[a.status] || a.status;
      if (a.status === "planned" && a.opening_planned) status = t("{status}, first stage by {year}", { status, year: String(a.opening_planned) });
      lines.push(muted(esc(status)));
    }
    return lines.join("<br>");
  },
  fort(f, m) {
    const comp = m.data.military?.components?.find((c) => c.id === f.component || c.id === f.branch);
    const branch = f.component || f.branch;
    const name = tr(comp?.name) || FORT_KINDS[fortKind(branch)]?.name || t("Military site");
    const lines = [
      `<b>${esc(f.name)}</b> ${muted(join(f.garrison, f.state))}`,
      join(name, tr(f.kind_label), STATUS[f.status] || f.status),
    ];
    if (f.note) lines.push(muted(esc(t(f.note))));
    return lines.filter(Boolean).join("<br>");
  },
  range(r, m) {
    const comp = m.data.military?.components?.find((c) => c.id === r.component || c.id === r.branch);
    const lines = [
      `<b>${esc(r.name)}</b> ${muted(join(r.garrison, r.state))}`,
      join(t("Restricted training ground"), tr(comp?.name) || r.component || r.branch),
    ];
    if (r.area_km2 != null) lines.push(`${esc(num(r.area_km2))} km\u00b2`);
    return lines.join("<br>");
  },
  wonder(x, m) {
    const rule = m.data.wonders?.rules?.find((r) => r.id === x.rule);
    const mt = x.metrics || {};
    const memorial = x.kind === "memorial";
    const kind = memorial ? t("Memorial site") : WONDER_KINDS[x.kind]?.name || tr(x.kind_label) || t("Landmark");
    const lines = [`<b>${esc(tr(x.name))}</b> ${muted(join(x.state))}`, esc(kind)];
    if (x.kind === "university" && mt.students != null) lines.push(esc(t.plural(mt.students, { one: "{n} student", other: "{n} students" }, { n: int(mt.students) })));
    const visitors = (n, year) => (year ? t("{n} visitors ({year})", { n: num(n), year: String(year) }) : t("{n} visitors", { n: num(n) }));
    if (mt.visits_latest != null) lines.push(esc(visitors(mt.visits_latest, mt.latest_year)));
    if (mt.visits != null) lines.push(esc(visitors(mt.visits, mt.year)));
    if (mt.record) lines.push(esc(t(mt.record)));
    if (mt.value != null) lines.push(`${esc(num(mt.value))} ${esc(tr(mt.unit) || "")}`.trim());
    if (rule?.text && !memorial) lines.push(muted(esc(t(rule.text))));
    return lines.join("<br>");
  },
  route(rt) {
    const r = rt.route;
    const a = rt.a?.short || rt.a?.name || r.a;
    const b = rt.b?.short || rt.b?.name || r.b;
    const lines = [
      `<b>${esc(t("{a} and {b}", { a, b }))}</b> ${muted(esc(t("route {rank}", { rank: r.rank })))}`,
      html(t("{n} tonnes by rail", { n: "{n}" }), { n: bold(num((r.value_kt ?? r.tons_k) * 1000)) }),
    ];
    if (r.dist_km != null) lines.push(esc(t("{n} km between the capital cities", { n: int(r.dist_km) })));
    return lines.join("<br>");
  },
};
