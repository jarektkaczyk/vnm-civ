// Product and tech sites (ext/economy): a low round token with the thing itself standing on it, in the same painted
// style and size as the wonder tiles (render/art/sites.js), but on a white-and-crimson token ("Made in Poland") or a
// slate-and-teal token ("Tech and games") so the two layers and the wonders read apart. Painted once per (kind, size
// bucket) into sprites and stamped into the cached static map; nothing animates.
//
//   ECON_KINDS                                   kind id -> {layer, motif}
//   drawEconSite(ctx, kind, x, y, size)          size = glyph width in ctx user units (world km in the map)
//   drawCountBadge(ctx, n, x, y, size)           the number of game studios in a town, on the token's shoulder
import { bucketPx, deviceScale, getSprite, drawSprite } from "./sprites.js";

const TAU = Math.PI * 2;
const BOX = { x0: -1.25, y0: -1.62, x1: 1.25, y1: 1.1 };

export const ECON_KINDS = {
  cars: { layer: "made" }, transport: { layer: "made" }, boats: { layer: "made" }, home: { layer: "made" },
  food: { layer: "made" }, crafts: { layer: "made" }, cosmetics: { layer: "made" }, energy: { layer: "made" },
  studio: { layer: "tech" }, scaleup: { layer: "tech" }, hpc: { layer: "tech" }, space: { layer: "tech" },
  research: { layer: "tech" },
};

// A dark top with a light rim: the motif carries the colour, so small glyphs read as things, not as dots.
const TOKEN = {
  made: { side: "#3e1216", top: "#5e1c22", rim: "#f4ecdc", ring: "#c8323a" },
  tech: { side: "#14222e", top: "#22394c", rim: "#8fd6e0", ring: "#4a8aa8" },
};

export function drawEconSite(ctx, kind, x, y, size) {
  const layer = ECON_KINDS[kind]?.layer || "made";
  const k = size / 2;
  const upx = bucketPx(deviceScale(ctx) * k, { min: 3, max: 220 });
  const spr = getSprite(`econ:${kind}`, upx, BOX, (g, u) => paintSite(g, u, kind, layer));
  drawSprite(ctx, spr, x, y, k);
}

/** A small round number badge at the token's upper right (world units, like drawEconSite). */
export function drawCountBadge(ctx, n, x, y, size, font = "system-ui, sans-serif") {
  const r = size * 0.2;
  const bx = x + size * 0.38, by = y - size * 0.42;
  ctx.beginPath();
  ctx.arc(bx, by, r, 0, TAU);
  ctx.fillStyle = "#f4ecdc";
  ctx.fill();
  ctx.lineWidth = r * 0.16;
  ctx.strokeStyle = "#1c2f40";
  ctx.stroke();
  ctx.fillStyle = "#1c2f40";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const s = String(n);
  ctx.font = `700 ${(r * (s.length > 2 ? 0.95 : 1.2)).toFixed(3)}px ${font}`;
  ctx.fillText(s, bx, by + r * 0.06);
}

function ink(g, upx, wPx = 1.1, col = "rgba(28,20,10,.92)") {
  g.lineWidth = wPx / upx;
  g.strokeStyle = col;
  g.stroke();
}
function poly(g, pts) {
  g.beginPath();
  for (let k = 0; k < pts.length; k += 2) (k ? g.lineTo : g.moveTo).call(g, pts[k], pts[k + 1]);
  g.closePath();
}
function fillInk(g, upx, fill, w = 1) {
  g.fillStyle = fill;
  g.fill();
  ink(g, upx, w);
}
function rrect(g, x, y, w, h, r) {
  g.beginPath();
  g.moveTo(x + r, y); g.lineTo(x + w - r, y); g.quadraticCurveTo(x + w, y, x + w, y + r);
  g.lineTo(x + w, y + h - r); g.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  g.lineTo(x + r, y + h); g.quadraticCurveTo(x, y + h, x, y + h - r);
  g.lineTo(x, y + r); g.quadraticCurveTo(x, y, x + r, y);
  g.closePath();
}
function disc(g, x, y, r) {
  g.beginPath();
  g.arc(x, y, r, 0, TAU);
}

/** The token: a shadow, a low drum and its coloured top with a light rim. */
function token(g, upx, pal) {
  g.fillStyle = "rgba(18,12,4,.33)";
  g.beginPath(); g.ellipse(0, 0.66, 1.02, 0.28, 0, 0, TAU); g.fill();
  g.fillStyle = pal.side;
  g.beginPath();
  g.ellipse(0, 0.5, 0.94, 0.32, 0, 0, Math.PI);
  g.lineTo(-0.94, 0.38);
  g.ellipse(0, 0.38, 0.94, 0.32, 0, Math.PI, 0, true);
  g.closePath();
  g.fill();
  ink(g, upx, 1);
  g.beginPath(); g.ellipse(0, 0.38, 0.94, 0.32, 0, 0, TAU);
  g.fillStyle = pal.top;
  g.fill();
  g.lineWidth = Math.max(2.2 / upx, 0.1);
  g.strokeStyle = pal.rim;
  g.stroke();
  g.beginPath(); g.ellipse(0, 0.38, 0.78, 0.25, 0, 0, TAU);
  g.lineWidth = Math.max(1.2 / upx, 0.05);
  g.strokeStyle = pal.ring;
  g.stroke();
  g.beginPath(); g.ellipse(0, 0.38, 0.94, 0.32, 0, 0, TAU);
  ink(g, upx, 0.7, "rgba(30,16,8,.8)");
}

function paintSite(g, upx, kind, layer) {
  token(g, upx, TOKEN[layer]);
  // the motif a little larger than the token, standing on it
  g.save();
  g.translate(0, 0.3);
  g.scale(1.14, 1.14);
  g.translate(0, -0.3);
  (PAINT[kind] || paintScaleup)(g, upx * 1.14);
  g.restore();
}

// --- Made in Poland ---------------------------------------------------------------------------------------------------

function paintCars(g, upx) {
  // a battery cell behind a small hatchback
  rrect(g, 0.1, -1.12, 0.5, 0.86, 0.08);
  fillInk(g, upx, "#3f8a5a", 1);
  g.fillStyle = "#cfd6cf";
  g.fillRect(0.26, -1.22, 0.18, 0.1);
  g.strokeStyle = "#f2f6e8"; g.lineWidth = 2 / upx;
  g.beginPath(); g.moveTo(0.4, -0.98); g.lineTo(0.28, -0.7); g.lineTo(0.42, -0.7); g.lineTo(0.3, -0.42); g.stroke();
  poly(g, [-0.88, 0.22, -0.88, -0.08, -0.62, -0.14, -0.42, -0.44, 0.08, -0.44, 0.3, -0.14, 0.58, -0.1, 0.62, 0.22]);
  fillInk(g, upx, "#dcd8cc", 1.1);
  poly(g, [-0.52, -0.16, -0.36, -0.38, -0.12, -0.38, -0.12, -0.16]);
  fillInk(g, upx, "#6f9cc0", 0.8);
  poly(g, [-0.04, -0.16, -0.04, -0.38, 0.06, -0.38, 0.22, -0.16]);
  fillInk(g, upx, "#6f9cc0", 0.8);
  for (const x of [-0.56, 0.32]) {
    disc(g, x, 0.22, 0.17); fillInk(g, upx, "#26282c", 1);
    disc(g, x, 0.22, 0.07); g.fillStyle = "#b8bcc4"; g.fill();
  }
}

function paintTransport(g, upx) {
  // a low-floor tram with its pantograph
  g.strokeStyle = "#2a2a30"; g.lineWidth = 1.4 / upx;
  g.beginPath(); g.moveTo(-0.2, -0.62); g.lineTo(0.02, -0.98); g.lineTo(0.24, -0.62); g.moveTo(-0.16, -0.98); g.lineTo(0.2, -0.98); g.stroke();
  rrect(g, -0.92, -0.62, 1.84, 0.82, 0.16);
  fillInk(g, upx, "#e8c23a", 1.1);
  g.fillStyle = "#c0392e";
  g.fillRect(-0.92, 0.02, 1.84, 0.16);
  g.fillStyle = "#3e5c78";
  for (const x of [-0.74, -0.34, 0.06, 0.46]) g.fillRect(x, -0.48, 0.3, 0.3);
  g.fillStyle = "rgba(255,255,255,.35)";
  for (const x of [-0.74, -0.34, 0.06, 0.46]) g.fillRect(x, -0.48, 0.08, 0.3);
  for (const x of [-0.6, 0.6]) { disc(g, x, 0.24, 0.1); fillInk(g, upx, "#2a2a30", 0.8); }
}

function paintBoats(g, upx) {
  // a yacht under sail on blue water
  g.beginPath(); g.ellipse(0, 0.36, 0.9, 0.29, 0, 0, TAU);
  g.save(); g.clip();
  g.fillStyle = "#4f9ccc"; g.fillRect(-1, 0.1, 2, 0.6);
  g.strokeStyle = "rgba(230,245,255,.8)"; g.lineWidth = 0.9 / upx;
  g.beginPath();
  for (const [x, y] of [[-0.55, 0.42], [0.2, 0.52], [0.6, 0.38]]) { g.moveTo(x - 0.14, y); g.quadraticCurveTo(x, y - 0.06, x + 0.14, y); }
  g.stroke();
  g.restore();
  poly(g, [-0.78, 0.12, 0.78, 0.12, 0.56, 0.36, -0.6, 0.36]);
  fillInk(g, upx, "#f6f2ea", 1.1);
  g.fillStyle = "#1f3e66"; g.fillRect(-0.62, 0.2, 1.26, 0.05);
  g.strokeStyle = "#3a2c1c"; g.lineWidth = 1.2 / upx;
  g.beginPath(); g.moveTo(-0.04, 0.12); g.lineTo(-0.04, -1.25); g.stroke();
  poly(g, [0.0, -1.2, 0.0, 0.04, 0.62, 0.04]);
  fillInk(g, upx, "#fbf7ec", 0.9);
  poly(g, [-0.08, -1.0, -0.08, 0.04, -0.56, 0.04]);
  fillInk(g, upx, "#efe4cc", 0.9);
}

function paintHome(g, upx) {
  // a white window with a cross frame and an armchair in front
  rrect(g, -0.66, -1.18, 0.98, 1.08, 0.05);
  fillInk(g, upx, "#f4f2ec", 1.1);
  g.fillStyle = "#8ec3e6";
  g.fillRect(-0.56, -1.08, 0.36, 0.42);
  g.fillRect(-0.12, -1.08, 0.34, 0.42);
  g.fillRect(-0.56, -0.58, 0.36, 0.38);
  g.fillRect(-0.12, -0.58, 0.34, 0.38);
  g.fillStyle = "rgba(255,255,255,.55)";
  g.fillRect(-0.52, -1.04, 0.06, 0.34);
  // armchair
  rrect(g, 0.06, -0.52, 0.72, 0.6, 0.14);
  fillInk(g, upx, "#9a4a32", 1);
  rrect(g, -0.04, -0.12, 0.92, 0.36, 0.12);
  fillInk(g, upx, "#b85a3c", 1);
  for (const x of [0.06, 0.74]) { g.fillStyle = "#3a2618"; g.fillRect(x, 0.22, 0.06, 0.12); }
}

function paintFood(g, upx) {
  // a sheaf of wheat behind a red apple
  g.strokeStyle = "#c9a040"; g.lineWidth = 1.6 / upx;
  g.beginPath();
  for (const a of [-0.32, -0.12, 0.1, 0.3]) { g.moveTo(0.38, 0.2); g.lineTo(0.38 + a * 1.4, -1.0); }
  g.stroke();
  g.fillStyle = "#e0b84c";
  for (const a of [-0.32, -0.12, 0.1, 0.3]) {
    const tx = 0.38 + a * 1.4;
    g.beginPath(); g.ellipse(tx, -1.06, 0.07, 0.2, a * 0.8, 0, TAU); g.fill(); ink(g, upx, 0.7, "rgba(90,60,10,.9)");
  }
  g.fillStyle = "#8a5a20"; g.fillRect(0.28, -0.3, 0.2, 0.08);
  g.beginPath();
  g.moveTo(-0.32, -0.56);
  g.bezierCurveTo(-0.62, -0.78, -0.98, -0.5, -0.9, -0.12);
  g.bezierCurveTo(-0.84, 0.22, -0.56, 0.36, -0.32, 0.22);
  g.bezierCurveTo(-0.08, 0.36, 0.2, 0.22, 0.24, -0.12);
  g.bezierCurveTo(0.3, -0.5, -0.04, -0.78, -0.32, -0.56);
  g.closePath();
  fillInk(g, upx, "#c8302e", 1.1);
  g.fillStyle = "rgba(255,230,220,.45)";
  g.beginPath(); g.ellipse(-0.6, -0.3, 0.08, 0.16, 0.4, 0, TAU); g.fill();
  g.strokeStyle = "#4a3018"; g.lineWidth = 1.4 / upx;
  g.beginPath(); g.moveTo(-0.32, -0.56); g.lineTo(-0.28, -0.8); g.stroke();
  g.beginPath(); g.ellipse(-0.14, -0.8, 0.16, 0.07, -0.4, 0, TAU);
  fillInk(g, upx, "#5a9a3a", 0.8);
}

function paintCrafts(g, upx) {
  // a stoneware jug with blue peacock-eye dots (Boleslawiec) and a glass goblet
  g.beginPath();
  g.moveTo(-0.62, 0.24);
  g.bezierCurveTo(-0.98, 0.0, -0.94, -0.56, -0.62, -0.68);
  g.lineTo(-0.66, -0.96); g.lineTo(-0.2, -0.96); g.lineTo(-0.24, -0.68);
  g.bezierCurveTo(0.08, -0.56, 0.12, 0.0, -0.24, 0.24);
  g.closePath();
  fillInk(g, upx, "#f2eee4", 1.1);
  g.strokeStyle = "rgba(28,20,10,.92)"; g.lineWidth = 1.1 / upx;
  g.beginPath(); g.moveTo(-0.12, -0.6); g.bezierCurveTo(0.16, -0.6, 0.16, -0.2, -0.04, -0.14); g.stroke();
  for (const [x, y] of [[-0.62, -0.36], [-0.34, -0.36], [-0.48, -0.08], [-0.76, -0.08], [-0.2, -0.08]]) {
    disc(g, x, y, 0.09); g.fillStyle = "#2a52a0"; g.fill();
    disc(g, x, y, 0.04); g.fillStyle = "#c8a030"; g.fill();
  }
  g.fillStyle = "#2a52a0"; g.fillRect(-0.66, -0.94, 0.42, 0.06);
  // goblet
  g.beginPath();
  g.moveTo(0.3, -0.98); g.lineTo(0.86, -0.98); g.quadraticCurveTo(0.86, -0.4, 0.6, -0.36);
  g.lineTo(0.6, 0.06); g.lineTo(0.8, 0.18); g.lineTo(0.36, 0.18); g.lineTo(0.56, 0.06); g.lineTo(0.56, -0.36);
  g.quadraticCurveTo(0.3, -0.4, 0.3, -0.98);
  g.closePath();
  fillInk(g, upx, "rgba(196,228,240,.85)", 1);
  g.fillStyle = "rgba(170,40,60,.75)";
  g.beginPath(); g.moveTo(0.33, -0.76); g.lineTo(0.83, -0.76); g.quadraticCurveTo(0.82, -0.44, 0.58, -0.42); g.quadraticCurveTo(0.34, -0.44, 0.33, -0.76); g.fill();
}

function paintCosmetics(g, upx) {
  // a scent bottle with a round stopper and a lipstick
  rrect(g, -0.76, -0.66, 0.8, 0.86, 0.16);
  fillInk(g, upx, "rgba(240,200,214,.92)", 1.1);
  g.fillStyle = "rgba(255,255,255,.5)"; g.fillRect(-0.66, -0.54, 0.1, 0.6);
  g.fillStyle = "#c9a45c"; g.fillRect(-0.48, -0.8, 0.24, 0.14);
  disc(g, -0.36, -0.94, 0.16); fillInk(g, upx, "#d8b860", 0.9);
  rrect(g, 0.26, -0.3, 0.38, 0.5, 0.04); fillInk(g, upx, "#2a2a30", 1);
  rrect(g, 0.3, -0.56, 0.3, 0.28, 0.03); fillInk(g, upx, "#c9a45c", 0.9);
  poly(g, [0.34, -0.56, 0.34, -0.9, 0.56, -1.02, 0.56, -0.56]);
  fillInk(g, upx, "#c42a44", 0.9);
}

function paintEnergy(g, upx) {
  // a works with a chimney beside a wind turbine
  poly(g, [-0.9, 0.24, -0.9, -0.36, -0.62, -0.56, -0.62, -0.36, -0.34, -0.56, -0.34, -0.36, -0.06, -0.56, -0.06, 0.24]);
  fillInk(g, upx, "#a84a32", 1);
  g.fillStyle = "rgba(255,240,210,.5)";
  for (const x of [-0.78, -0.5, -0.24]) g.fillRect(x, -0.22, 0.12, 0.18);
  poly(g, [-0.24, -0.5, -0.2, -1.14, -0.08, -1.14, -0.04, -0.5]);
  fillInk(g, upx, "#8a3a28", 0.9);
  g.fillStyle = "rgba(236,236,232,.8)";
  for (const [x, y, r] of [[-0.12, -1.24, 0.08], [-0.02, -1.34, 0.1]]) { disc(g, x, y, r); g.fill(); }
  // turbine
  g.strokeStyle = "#f2f2ee"; g.lineWidth = 2.2 / upx;
  g.beginPath(); g.moveTo(0.52, 0.24); g.lineTo(0.52, -0.86); g.stroke();
  g.strokeStyle = "rgba(28,20,10,.8)"; g.lineWidth = 0.7 / upx;
  g.beginPath(); g.moveTo(0.49, 0.24); g.lineTo(0.49, -0.86); g.stroke();
  g.fillStyle = "#f6f6f2";
  for (let k = 0; k < 3; k++) {
    const a = -Math.PI / 2 + (k * TAU) / 3 + 0.25;
    g.save(); g.translate(0.52, -0.88); g.rotate(a);
    g.beginPath(); g.moveTo(0, -0.04); g.quadraticCurveTo(0.3, -0.06, 0.6, 0); g.quadraticCurveTo(0.3, 0.05, 0, 0.04); g.closePath();
    g.fill(); ink(g, upx, 0.7);
    g.restore();
  }
  disc(g, 0.52, -0.88, 0.05); fillInk(g, upx, "#d0d0cc", 0.7);
}

// --- Tech and games ---------------------------------------------------------------------------------------------------

function paintStudio(g, upx) {
  // a game controller
  g.beginPath();
  g.moveTo(-0.5, -0.66);
  g.lineTo(0.5, -0.66);
  g.bezierCurveTo(0.86, -0.66, 1.0, -0.2, 0.92, 0.02);
  g.bezierCurveTo(0.86, 0.22, 0.62, 0.24, 0.5, 0.06);
  g.lineTo(0.34, -0.12); g.lineTo(-0.34, -0.12); g.lineTo(-0.5, 0.06);
  g.bezierCurveTo(-0.62, 0.24, -0.86, 0.22, -0.92, 0.02);
  g.bezierCurveTo(-1.0, -0.2, -0.86, -0.66, -0.5, -0.66);
  g.closePath();
  fillInk(g, upx, "#e8e4da", 1.2);
  g.fillStyle = "#2a2e36";
  g.fillRect(-0.62, -0.46, 0.3, 0.09);
  g.fillRect(-0.515, -0.56, 0.09, 0.3);
  for (const [x, y, c] of [[0.5, -0.54, "#3fa05a"], [0.62, -0.42, "#c0392e"], [0.38, -0.42, "#2f6ab8"], [0.5, -0.3, "#e0b03a"]]) {
    disc(g, x, y, 0.065); fillInk(g, upx, c, 0.7);
  }
}

function paintScaleup(g, upx) {
  // a glass office tower with a lower wing
  poly(g, [-0.34, 0.3, -0.34, -1.12, 0.16, -1.28, 0.16, 0.3]);
  fillInk(g, upx, "#6fa6c8", 1.1);
  poly(g, [0.16, 0.3, 0.16, -1.28, 0.36, -1.12, 0.36, 0.3]);
  fillInk(g, upx, "#4a7c9c", 1);
  g.strokeStyle = "rgba(230,245,255,.55)"; g.lineWidth = 0.8 / upx;
  g.beginPath();
  for (let y = -1.0; y < 0.3; y += 0.16) { g.moveTo(-0.34, y); g.lineTo(0.16, y - 0.02); }
  g.stroke();
  poly(g, [-0.9, 0.3, -0.9, -0.32, -0.34, -0.32, -0.34, 0.3]);
  fillInk(g, upx, "#a9c6d8", 1);
  poly(g, [0.36, 0.3, 0.36, -0.5, 0.86, -0.5, 0.86, 0.3]);
  fillInk(g, upx, "#8fb4ca", 1);
  g.fillStyle = "rgba(40,60,80,.55)";
  for (const y of [-0.2, 0.0]) { g.fillRect(-0.8, y, 0.36, 0.08); }
  for (const y of [-0.38, -0.18, 0.02]) { g.fillRect(0.44, y, 0.34, 0.08); }
}

function paintHpc(g, upx) {
  // two server racks with lit status lights
  for (const [x, w] of [[-0.82, 0.74], [0.04, 0.74]]) {
    rrect(g, x, -1.12, w, 1.4, 0.06);
    fillInk(g, upx, "#2a3038", 1.1);
    for (let k = 0; k < 6; k++) {
      const y = -1.02 + k * 0.21;
      g.fillStyle = "#3e4652"; g.fillRect(x + 0.08, y, w - 0.16, 0.15);
      g.fillStyle = k % 2 ? "#7fe08a" : "#8fd6e0"; g.fillRect(x + 0.14, y + 0.05, 0.07, 0.05);
      g.fillStyle = "#e0b03a"; g.fillRect(x + 0.26, y + 0.05, 0.05, 0.05);
    }
  }
}

function paintSpace(g, upx) {
  // a small satellite with two solar wings and a dish
  g.save(); g.translate(0, -0.46); g.rotate(-0.35);
  for (const s of [-1, 1]) {
    const x0 = s < 0 ? -1.02 : 0.3;
    g.beginPath(); g.rect(x0, -0.2, 0.72, 0.4);
    fillInk(g, upx, "#2f4f8a", 1);
    g.strokeStyle = "rgba(200,220,255,.6)"; g.lineWidth = 0.7 / upx;
    g.beginPath();
    for (let k = 1; k < 4; k++) { g.moveTo(x0 + k * 0.18, -0.2); g.lineTo(x0 + k * 0.18, 0.2); }
    g.moveTo(x0, 0); g.lineTo(x0 + 0.72, 0);
    g.stroke();
  }
  g.beginPath(); g.rect(-0.3, -0.3, 0.6, 0.6);
  fillInk(g, upx, "#d8b860", 1.1);
  g.strokeStyle = "rgba(120,90,20,.7)"; g.lineWidth = 0.8 / upx;
  g.beginPath(); g.moveTo(-0.3, 0); g.lineTo(0.3, 0); g.moveTo(0, -0.3); g.lineTo(0, 0.3); g.stroke();
  g.beginPath(); g.ellipse(0, -0.46, 0.2, 0.1, 0, 0, TAU);
  fillInk(g, upx, "#e8e8e4", 0.9);
  g.strokeStyle = "#2a2a30"; g.lineWidth = 1 / upx;
  g.beginPath(); g.moveTo(0, -0.3); g.lineTo(0, -0.42); g.stroke();
  g.restore();
}

function paintResearch(g, upx) {
  // a lit bulb
  g.fillStyle = "rgba(255,220,120,.35)";
  disc(g, 0, -0.62, 0.66); g.fill();
  g.beginPath();
  g.moveTo(-0.2, -0.04);
  g.bezierCurveTo(-0.24, -0.3, -0.5, -0.42, -0.5, -0.72);
  g.bezierCurveTo(-0.5, -1.04, -0.26, -1.22, 0, -1.22);
  g.bezierCurveTo(0.26, -1.22, 0.5, -1.04, 0.5, -0.72);
  g.bezierCurveTo(0.5, -0.42, 0.24, -0.3, 0.2, -0.04);
  g.closePath();
  fillInk(g, upx, "#ffe08a", 1.1);
  g.strokeStyle = "#b87a20"; g.lineWidth = 1.1 / upx;
  g.beginPath(); g.moveTo(-0.12, -0.08); g.lineTo(-0.08, -0.6); g.lineTo(0, -0.5); g.lineTo(0.08, -0.6); g.lineTo(0.12, -0.08); g.stroke();
  rrect(g, -0.22, -0.06, 0.44, 0.32, 0.05);
  fillInk(g, upx, "#9aa0a8", 1);
  g.strokeStyle = "rgba(40,40,48,.7)"; g.lineWidth = 0.8 / upx;
  g.beginPath(); g.moveTo(-0.22, 0.04); g.lineTo(0.22, 0.04); g.moveTo(-0.22, 0.14); g.lineTo(0.22, 0.14); g.stroke();
}

const PAINT = {
  cars: paintCars, transport: paintTransport, boats: paintBoats, home: paintHome, food: paintFood, crafts: paintCrafts,
  cosmetics: paintCosmetics, energy: paintEnergy,
  studio: paintStudio, scaleup: paintScaleup, hpc: paintHpc, space: paintSpace, research: paintResearch,
};
