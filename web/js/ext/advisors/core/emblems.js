// Original advisor emblems: a gilded medallion with a simple glyph for each office, drawn as
// inline SVG (no external art).
import { esc } from "./util.js";

const GLYPHS = {
  // Zupnik: crossed miner's hammer and iron (salt and coal) over a small lightning bolt (power)
  energy: `<path d="M19 47 43.5 22.5M45 47 20.5 22.5" stroke="#2a1d08" stroke-width="4.6" stroke-linecap="round"/>
    <path d="M19 47 43.5 22.5M45 47 20.5 22.5" stroke="#c99a5a" stroke-width="2.6" stroke-linecap="round"/>
    <path d="M49.7 24.2 46.2 27.7 36.3 17.8 39.8 14.3z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M14.3 24.2 17.8 27.7 27.7 17.8 24.2 14.3z" fill="#e9dcb7" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M24.2 14.3 20 13l1.2 4.2" fill="#e9dcb7" stroke="#2a1d08" stroke-width="1.2" stroke-linejoin="round"/>
    <path d="M34 33.5 28.5 43h4.2l-2.2 8.5 8.3-11.2h-4.4l3.1-6.8z" fill="#ffe08a" stroke="#2a1d08" stroke-width="1.3" stroke-linejoin="round"/>`,
  // Podskarbi: an iron-bound treasury chest with a gold lock
  economy: `<path d="M15 31c0-7.5 7-10.5 17-10.5S49 23.5 49 31z" fill="#e9dcb7" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M15 31h34v18H15z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M21.5 21.6V49M42.5 21.6V49" stroke="#2a1d08" stroke-width="4"/><path d="M21.5 21.8V48.6M42.5 21.8V48.6" stroke="#b4872f" stroke-width="2.4"/>
    <path d="M15 31h34" stroke="#2a1d08" stroke-width="1.4"/>
    <path d="M28.5 29h7v9.5l-3.5 2.5-3.5-2.5z" fill="#ffe08a" stroke="#2a1d08" stroke-width="1.2" stroke-linejoin="round"/>
    <circle cx="32" cy="33" r="1.5" fill="#2a1d08"/><path d="M32 33.5v3.4" stroke="#2a1d08" stroke-width="1.2"/>`,
  // two figures, one in front
  people: `<circle cx="24" cy="23" r="6.5" fill="#e9dcb7" stroke="#2a1d08" stroke-width="1.3"/>
    <path d="M12 47c0-8 5-13 12-13s12 5 12 13z" fill="#e9dcb7" stroke="#2a1d08" stroke-width="1.3"/>
    <circle cx="38" cy="26" r="7.5" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.4"/>
    <path d="M24 52c0-9 6-15 14-15s14 6 14 15z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.4"/>`,
  // Ochmistrz: a manor house (dwor) with a hipped roof and a columned porch
  prosperity: `<path d="M9.5 34 18 23h28l8.5 11z" fill="#b8644a" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M18 23h28" stroke="#e08a6a" stroke-width="1.2"/>
    <path d="M13 34h38v15H13z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.5"/>
    <path d="M23 34.5 32 26l9 8.5z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.4" stroke-linejoin="round"/>
    <path d="M25 35v14M29.7 35v14M34.3 35v14M39 35v14" stroke="#2a1d08" stroke-width="2.6"/><path d="M25 35.5v13M29.7 35.5v13M34.3 35.5v13M39 35.5v13" stroke="#fffaf0" stroke-width="1.3"/>
    <path d="M15.5 38h4.5v5h-4.5zM44 38h4.5v5H44z" fill="#5a6a7a" stroke="#2a1d08" stroke-width="1"/>
    <path d="M30.6 42.5h2.8V49h-2.8z" fill="#6a3a1c"/>`,
  // Rektor: an open book under a sun with an orbiting planet (Copernicus)
  knowledge: `<path d="M32 26c-5-4-12-5-19-4v24c7-1 14 0 19 4 5-4 12-5 19-4V22c-7-1-14 0-19 4z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M32 26v24" stroke="#2a1d08" stroke-width="1.3"/>
    <path d="M17 29c4-.4 8 .2 11 2M17 34c4-.4 8 .2 11 2M47 29c-4-.4-8 .2-11 2M47 34c-4-.4-8 .2-11 2" stroke="#8a6a2c" stroke-width="1" fill="none"/>
    <ellipse cx="32" cy="15.5" rx="10" ry="3.6" fill="none" stroke="#fff4d2" stroke-width="1.2" transform="rotate(-12 32 15.5)"/>
    <circle cx="32" cy="15.5" r="3.4" fill="#ffe08a" stroke="#2a1d08" stroke-width="1"/>
    <circle cx="41.6" cy="13.2" r="1.5" fill="#bfe0f2" stroke="#2a1d08" stroke-width=".8"/>`,
  // Geometra: mountains with snow, sun and furrowed fields
  land: `<circle cx="43" cy="20" r="5" fill="#ffe08a" stroke="#2a1d08" stroke-width="1.2"/>
    <path d="M10 40 24 20l8 11 5-6 15 15z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="m24 20-3.5 5 2.3-.6 1.4 1.8 1.6-2.2z" fill="#dfe8ef"/>
    <path d="M10 42h42c-2 6-8 10-21 10S12 48 10 42z" fill="#b9c96a" stroke="#2a1d08" stroke-width="1.4"/>
    <path d="M16 45c5 1.5 25 1.5 32 0M19 48.5c5 1 21 1 26 0" stroke="#5b6b22" stroke-width="1" fill="none"/>`,
  // compass rose
  explorer: `<circle cx="32" cy="32" r="16" fill="none" stroke="#fff4d2" stroke-width="1.6" stroke-dasharray="2 3"/>
    <path d="M32 11 36 28 53 32 36 36 32 53 28 36 11 32 28 28z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.4" stroke-linejoin="round"/>
    <path d="M32 11 36 28 32 32zM53 32 36 36 32 32zM32 53 28 36 32 32zM11 32 28 28 32 32z" fill="#c9a45c"/>
    <circle cx="32" cy="32" r="2.6" fill="#2a1d08"/>`,
  // Hetman: the bulawa, the hetman's mace of command, with a red-and-white plume
  military: `<path d="M27 27 46.5 46.5" stroke="#2a1d08" stroke-width="5" stroke-linecap="round"/>
    <path d="M27 27 46.5 46.5" stroke="#c99a5a" stroke-width="3" stroke-linecap="round"/>
    <path d="M36 36 40.5 40.5" stroke="#b4872f" stroke-width="3.4"/>
    <circle cx="47.5" cy="47.5" r="2.6" fill="#ffe08a" stroke="#2a1d08" stroke-width="1.1"/>
    <circle cx="26.8" cy="26.8" r="2.8" fill="#ffe08a" stroke="#2a1d08" stroke-width="1.1"/>
    <path d="M22.5 31.5c-6 .5-10-4-9.5-9.5s4-9.5 9.5-9.5 10 4 9.5 9.5-3.5 9-9.5 9.5z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.5"/>
    <path d="M22.7 12.4c-3.2 5.6-3.2 13.4 0 19M14 21.5c5.6-1.4 11.8-1.4 17.6 0M16 15.5c4.4 2.2 9.8 8 11.8 14" fill="none" stroke="#8a6a2c" stroke-width="1.2"/>
    <circle cx="18.4" cy="17.6" r="1.4" fill="#e0b54c"/><circle cx="26.8" cy="18" r="1.4" fill="#e0b54c"/><circle cx="18.6" cy="26.4" r="1.4" fill="#e0b54c"/>
    <path d="M16.6 13c-2-3 0-6.5 2.8-7.5-.4 2.4 1 3.6 2.4 4.4" fill="#f4ecd8" stroke="#2a1d08" stroke-width="1" stroke-linejoin="round"/>
    <path d="M19.4 11.2c1.6-2.6 4.6-3.2 6.8-2-1.8.8-2.4 2-2.6 3.4" fill="#c8323a" stroke="#2a1d08" stroke-width="1" stroke-linejoin="round"/>`,
  // Gdansk Merchant: a Hanseatic cog under a square sail with a red band and a pennant
  commerce: `<path d="M32 12v29" stroke="#2a1d08" stroke-width="2.4"/>
    <path d="M32 9.5 40 12l-8 2.4z" fill="#c8323a" stroke="#2a1d08" stroke-width=".9" stroke-linejoin="round"/>
    <path d="M20 16h24c1.4 6 1.4 12 0 18H20c-1.4-6-1.4-12 0-18z" fill="#fff4d2" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M19.2 22.5h25.6v4.6H19.2z" fill="#c8323a"/>
    <path d="M20 16h24c1.4 6 1.4 12 0 18H20c-1.4-6-1.4-12 0-18z" fill="none" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M10 38h44l-5.5 10.5h-33z" fill="#c08a4a" stroke="#2a1d08" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M44 38v-4.5h8.5V38M12 38v-3h6.5v3" fill="#d9a868" stroke="#2a1d08" stroke-width="1.3" stroke-linejoin="round"/>
    <path d="M13.5 42.5h37" stroke="#7a4a1c" stroke-width="1"/>
    <path d="M10 52c3 0 3-1.8 6-1.8s3 1.8 6 1.8 3-1.8 6-1.8 3 1.8 6 1.8 3-1.8 6-1.8 3 1.8 6 1.8 3-1.8 6-1.8" fill="none" stroke="#bfe0f2" stroke-width="1.4" stroke-linecap="round"/>`,
  // Kustosz: a laurel wreath around the key of the treasury
  culture: wreath(),
};

function wreath() {
  const leaves = [];
  for (let side = -1; side <= 1; side += 2) {
    for (let k = 0; k < 6; k++) {
      const th = ((28 + k * 23) * Math.PI) / 180; // angle from the bottom of the circle, up each side
      const r = 16;
      const x = 32 + side * r * Math.sin(th), y = 34 + r * Math.cos(th);
      // the leaf's long axis along the circle's tangent, tipped a little outward
      const rot = (Math.atan2(-side * Math.cos(th), -Math.sin(th)) * 180) / Math.PI + side * 22;
      leaves.push(`<ellipse cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" rx="2.4" ry="5.2" transform="rotate(${rot.toFixed(1)} ${x.toFixed(2)} ${y.toFixed(2)})" fill="#fff4d2" stroke="#2a1d08" stroke-width="1"/>`);
    }
  }
  return `<path d="M27.5 49.4A16 16 0 0 1 18.6 24.5M36.5 49.4A16 16 0 0 0 45.4 24.5" fill="none" stroke="#2a1d08" stroke-width="1.4"/>
    ${leaves.join("")}
    <path d="M27 48.5c2 1.6 8 1.6 10 0" fill="none" stroke="#b4872f" stroke-width="2" stroke-linecap="round"/>
    <circle cx="32" cy="23.5" r="5" fill="none" stroke="#2a1d08" stroke-width="3.6"/><circle cx="32" cy="23.5" r="5" fill="none" stroke="#ffe08a" stroke-width="2"/>
    <path d="M32 28.5v15.5" stroke="#2a1d08" stroke-width="3.8" stroke-linecap="round"/><path d="M32 28.8v15" stroke="#ffe08a" stroke-width="2" stroke-linecap="round"/>
    <path d="M32.6 38.6h4.4v2.4h-2v1.4h2v2.2h-4.4z" fill="#ffe08a" stroke="#2a1d08" stroke-width="1" stroke-linejoin="round"/>`;
}

/** The medallion SVG for an advisor ({id, color}). */
export function emblem(adv, size = 48, title = "") {
  const g = GLYPHS[adv.glyph || adv.id] || GLYPHS.explorer;
  const gid = `advg-${adv.id}-${size}`;
  const a11y = title ? `role="img" aria-label="${esc(title)}"` : `aria-hidden="true" focusable="false"`;
  return `<svg class="adv-emblem" ${a11y} width="${size}" height="${size}" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="${gid}-d" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="${esc(adv.color)}" stop-opacity="1"/><stop offset="1" stop-color="${esc(adv.dark || "#12202c")}"/></radialGradient>
      <linearGradient id="${gid}-r" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6dc8a"/><stop offset=".5" stop-color="#b4872f"/><stop offset="1" stop-color="#6e5020"/></linearGradient>
    </defs>
    <circle cx="32" cy="32" r="31" fill="#120d06"/>
    <circle cx="32" cy="32" r="29.5" fill="url(#${gid}-r)"/>
    <circle cx="32" cy="32" r="25.5" fill="url(#${gid}-d)" stroke="#2a1d08" stroke-width="1.2"/>
    <path d="M14 22a22 22 0 0 1 36 0" fill="none" stroke="rgba(255,240,200,.18)" stroke-width="3" stroke-linecap="round"/>
    ${g}
  </svg>`;
}
