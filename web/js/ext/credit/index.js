// The OpenStreetMap credit on the map surface. Roads, rail, coast and many sites come from OpenStreetMap (ODbL),
// whose attribution guidelines ask for a credit visible on the map without any interaction; it may fade out
// automatically. This one shows in a corner on arrival and fades after FADE_MS or at the first pan, zoom or click
// on the map, whichever comes first. The full licence text stays in the Almanac (Sources).
// Owner's choice (2026-11-27): 3 seconds. OSM's safe-harbour wording names 5 seconds; change FADE_MS to 5000 to match.
import { t } from "../../i18n.js";

const FADE_MS = 3000;
const CSS = `
.osm-credit { position: fixed; z-index: 12; left: calc(12px + var(--dock-left, 0px)); bottom: 0; padding: 1px 6px 2px;
  font-size: 11px; line-height: 1.3; color: #e8dcc0; background: rgba(12,18,28,.72); border-radius: 4px 4px 0 0;
  text-decoration: none; transition: opacity .6s ease; }
.osm-credit:hover, .osm-credit:focus-visible { color: #ecd08e; text-decoration: underline; }
.osm-credit.gone { opacity: 0; pointer-events: none; }
@media (max-width: 700px) { .osm-credit { left: 8px; bottom: auto; top: calc(var(--topbar-h, 40px) + 6px); border-radius: 4px; } }
`;

export function install(app) {
  const st = document.createElement("style");
  st.textContent = CSS;
  document.head.appendChild(st);
  const a = document.createElement("a");
  a.className = "osm-credit";
  a.href = "https://www.openstreetmap.org/copyright";
  a.target = "_blank";
  a.rel = "noopener";
  a.textContent = t("Map data (c) OpenStreetMap");
  document.body.appendChild(a);
  let done = false;
  const fade = () => {
    if (done) return;
    done = true;
    a.classList.add("gone");
    setTimeout(() => a.remove(), 800);
  };
  setTimeout(fade, FADE_MS);
  const map = document.getElementById("map");
  for (const ev of ["pointerdown", "wheel"]) map?.addEventListener(ev, fade, { once: true, passive: true });
  app.credit = { fade };
}
