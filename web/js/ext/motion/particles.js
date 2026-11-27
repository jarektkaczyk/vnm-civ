// Moving dots along a polyline, for the motion layers (app.motion.particles).
//
//   const flow = particles(path, {slots, speed, color, size, shape, seed, offset, density})
//   flow.draw(ctx, view, t, {density?, alpha?, dir?, size?})
//
// path: flat [x0, y0, x1, y1, ...] in map km (an Array or Float64Array). The flow has `slots` dots, evenly spread
// along the path, that travel at `speed` km per clock unit (dir -1 runs from the end to the start). A dot's place is
// a pure function of the clock value t, so pausing holds the picture and scrubbing jumps straight to it.
// density(tDepart) -> 0..1 says how many of the slots are filled for dots that left the start at clock value
// tDepart. Each slot draws its own random number per trip, so a dot appears or vanishes only at the path ends,
// never in the middle.
//
// view: {cam, dpr, x0, y0, x1, y1} (the vp a motion layer gets); dots are drawn in screen pixels from cached sprites,
// and ctx is left in the transform it came in.
// shape: "dot" (a soft glowing disc) or "wagon" (a small oriented box, `cars` boxes in a row).

const sprites = new Map();

/** A cached sprite canvas for a shape, colour and css px size at a device scale. */
export function sprite(shape, color, sizePx, dpr) {
  const px = Math.max(1, Math.round(sizePx * 2) / 2);
  const key = `${shape}|${color}|${px}|${dpr}`;
  let c = sprites.get(key);
  if (c) return c;
  c = document.createElement("canvas");
  if (shape === "wagon") {
    const w = px * 1.9, h = px;
    c.width = Math.ceil((w + 2) * dpr);
    c.height = Math.ceil((h + 2) * dpr);
    const g = c.getContext("2d");
    g.scale(dpr, dpr);
    g.fillStyle = "rgba(250,240,214,.95)"; // a parchment rim reads on the route's halo and on dark ground
    g.fillRect(0, 0, w + 2, h + 2);
    g.fillStyle = color;
    g.fillRect(1, 1, w, h);
    g.fillStyle = "rgba(255,255,255,.22)";
    g.fillRect(1, 1, w, Math.max(0.6, h * 0.3));
    c.cssW = w + 2;
    c.cssH = h + 2;
  } else {
    // A bright core with a thin dark rim and a soft glow, so a dot reads on light fields and on its own arc.
    const core = px / 2;
    const r = core + 2.5;
    c.width = c.height = Math.ceil(2 * r * dpr);
    const g = c.getContext("2d");
    g.scale(dpr, dpr);
    const grad = g.createRadialGradient(r, r, core, r, r, r);
    grad.addColorStop(0, withAlpha(color, 0.5));
    grad.addColorStop(1, withAlpha(color, 0));
    g.fillStyle = grad;
    g.beginPath();
    g.arc(r, r, r, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = "rgba(30,14,2,.75)";
    g.beginPath();
    g.arc(r, r, core + 0.7, 0, Math.PI * 2);
    g.fill();
    const body = g.createRadialGradient(r - core * 0.3, r - core * 0.3, 0, r, r, core);
    body.addColorStop(0, "#fffbe8");
    body.addColorStop(1, color);
    g.fillStyle = body;
    g.beginPath();
    g.arc(r, r, core, 0, Math.PI * 2);
    g.fill();
    c.cssW = c.cssH = 2 * r;
  }
  if (sprites.size > 400) sprites.clear();
  sprites.set(key, c);
  return c;
}

function withAlpha(hex, a) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
  if (!m) return hex;
  return `rgba(${parseInt(m[1], 16)},${parseInt(m[2], 16)},${parseInt(m[3], 16)},${a})`;
}

// A stable random number in 0..1 for (seed, slot, trip).
function rand(seed, i, k) {
  let h = Math.imul(seed ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul(i + 1, 0xc2b2ae35) ^ Math.imul(k + 7, 0x27d4eb2f);
  h ^= h >>> 15;
  h = Math.imul(h, 0x2c1b3c6d);
  h ^= h >>> 12;
  h = Math.imul(h, 0x297a2d39);
  h ^= h >>> 15;
  return (h >>> 0) / 4294967296;
}

export function particles(path, opts = {}) {
  const pts = Float64Array.from(path || []);
  const n = pts.length >> 1;
  const cum = new Float64Array(Math.max(1, n));
  for (let k = 1; k < n; k++) cum[k] = cum[k - 1] + Math.hypot(pts[2 * k] - pts[2 * k - 2], pts[2 * k + 1] - pts[2 * k - 1]);
  const len = n > 1 ? cum[n - 1] : 0;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let k = 0; k < n; k++) {
    x0 = Math.min(x0, pts[2 * k]); x1 = Math.max(x1, pts[2 * k]);
    y0 = Math.min(y0, pts[2 * k + 1]); y1 = Math.max(y1, pts[2 * k + 1]);
  }
  const slots = Math.max(1, Math.round(opts.slots ?? 8));
  const speed = opts.speed ?? 1; // km per clock unit
  const seed = (opts.seed ?? 1) | 0;
  const jitter = new Float64Array(slots).map((_, i) => rand(seed, i, -1) * 0.6);
  const out = new Float64Array(4); // x, y, dx, dy of the last lookup

  // Point and direction at distance d along the path (binary search on the cumulative lengths).
  function at(d) {
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (cum[mid] <= d) lo = mid; else hi = mid;
    }
    const seg = cum[hi] - cum[lo] || 1;
    const f = Math.min(1, Math.max(0, (d - cum[lo]) / seg));
    const ax = pts[2 * lo], ay = pts[2 * lo + 1], bx = pts[2 * hi], by = pts[2 * hi + 1];
    out[0] = ax + (bx - ax) * f;
    out[1] = ay + (by - ay) * f;
    out[2] = (bx - ax) / seg;
    out[3] = (by - ay) / seg;
    return out;
  }

  const travel = len > 0 && speed > 0 ? len / speed : 1; // clock units for one trip

  /**
   * Draw the dots at clock value t. view = engine view {cam, dpr, x0..y1}; returns the number of dots drawn.
   * o: {density(tDepart) | number, alpha, dir, size (css px), color, cars, gap (css px between cars), offset (css px sideways)}
   */
  function draw(ctx, view, t, o = {}) {
    if (n < 2 || len <= 0) return 0;
    const { cam, dpr } = view;
    const s = cam.scale;
    const pad = 12 / s;
    if (x1 < view.x0 - pad || x0 > view.x1 + pad || y1 < view.y0 - pad || y0 > view.y1 + pad) return 0;
    const dens = o.density ?? opts.density ?? 1;
    const densAt = typeof dens === "function" ? dens : () => dens;
    const dir = (o.dir ?? opts.dir ?? 1) < 0 ? -1 : 1;
    const shape = opts.shape || "dot";
    const size = o.size ?? opts.size ?? 3;
    const color = o.color ?? opts.color ?? "#ffd27a";
    const cars = shape === "wagon" ? Math.max(1, o.cars ?? opts.cars ?? 1) : 1;
    const gapKm = ((o.gap ?? size * 2.2) / s);
    const offKm = (o.offset ?? opts.offset ?? 0) / s;
    const img = sprite(shape, color, size, dpr);
    const hw = img.cssW / 2, hh = img.cssH / 2;
    const cx = cam.w / 2 - cam.x * s, cy = cam.h / 2 - cam.y * s;
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalAlpha = o.alpha ?? 1;
    let drawn = 0;
    const phase = t / travel;
    for (let i = 0; i < slots; i++) {
      const p = phase + i / slots + jitter[i] / slots;
      const trip = Math.floor(p);
      const u = p - trip;
      const tDepart = t - u * travel;
      const want = densAt(tDepart);
      if (!(want > 0) || rand(seed, i, trip) >= want) continue;
      for (let c = 0; c < cars; c++) {
        const d = u * len - c * gapKm;
        if (d < 0) break;
        const q = at(dir > 0 ? d : len - d);
        let x = q[0], y = q[1];
        const dx = q[2] * dir, dy = q[3] * dir;
        if (offKm) { x += -dy * offKm; y += dx * offKm; }
        if (x < view.x0 - pad || x > view.x1 + pad || y < view.y0 - pad || y > view.y1 + pad) continue;
        const sx = x * s + cx, sy = y * s + cy;
        if (shape === "wagon") {
          ctx.setTransform(dpr * dx, dpr * dy, -dpr * dy, dpr * dx, dpr * sx, dpr * sy);
          ctx.drawImage(img, -hw, -hh, img.cssW, img.cssH);
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        } else {
          ctx.drawImage(img, sx - hw, sy - hh, img.cssW, img.cssH);
        }
        drawn++;
      }
    }
    ctx.restore();
    return drawn;
  }

  return { len, slots, travel, bbox: [x0, y0, x1, y1], at: (d) => Array.from(at(d)), draw };
}
