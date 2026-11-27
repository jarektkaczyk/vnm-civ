// The coast as it is today, at close zoom: OpenStreetMap land (coast.json) filled over the sea hexes, so reclaimed
// land, port terminals and small islands keep their real shape, and the coastline stroked over everything. Airports
// and seaports as areas (hubs.json): the aerodrome outline with its runways, and the port areas.
const COAST_MIN_RPX = 16; // a hex at least this many css px across its radius: the coastline is worth drawing
const HUBS_MIN_RPX = 12;
const LAND = "#7f9a58";
const SHORE = "rgba(240,228,190,.85)";
const SEA = "#2b6790"; // the coastal-water blue of the hexes

function hexPath(w, cells, pred) {
  const P = new Path2D();
  const R = w.grid.R * 1.01;
  for (const i of cells) {
    if (!pred(i)) continue;
    const x = w.grid.cx(i), y = w.grid.cy(i);
    for (let k = 0; k < 6; k++) {
      const a = (Math.PI / 180) * (60 * k - 30);
      const px = x + R * Math.cos(a), py = y + R * Math.sin(a);
      if (k) P.lineTo(px, py); else P.moveTo(px, py);
    }
    P.closePath();
  }
  return P;
}

function prepRings(list) {
  return (list || []).map((r) => {
    const P = new Path2D();
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    P.moveTo(r[0], r[1]);
    for (let k = 0; k < r.length; k += 2) {
      if (k) P.lineTo(r[k], r[k + 1]);
      x0 = Math.min(x0, r[k]); x1 = Math.max(x1, r[k]); y0 = Math.min(y0, r[k + 1]); y1 = Math.max(y1, r[k + 1]);
    }
    return { P, box: [x0, y0, x1, y1] };
  });
}

const seen = (it, vp) => !(it.box[2] < vp.x0 || it.box[0] > vp.x1 || it.box[3] < vp.y0 || it.box[1] > vp.y1);

// The Hoang Sa and Truong Sa archipelagos (world.json archipelagos): the Vietnamese name in italic over the sea, with
// the province it belongs to on a second line. Drawn per frame in screen space, so a label that would run past the
// edge of the screen slides inside it, and one that cannot fit is not drawn.
function archipelagoLabels(app) {
  const list = app.w.raw.archipelagos || [];
  const font = '"Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif';
  return {
    id: "archipelago-labels", z: 95, space: "screen",
    draw(ctx, cam) {
      const W = cam.w, H = cam.h;
      for (const a of list) {
        const [sx, sy] = cam.toScreen(a.x, a.y);
        const px = Math.max(11, Math.min(22, 34 * cam.scale));
        const prov = app.w.raw.states[a.state]?.name || "";
        ctx.font = `italic ${px.toFixed(1)}px ${font}`;
        const w1 = ctx.measureText(a.name).width;
        ctx.font = `italic ${(px * 0.72).toFixed(1)}px ${font}`;
        const w2 = prov ? ctx.measureText(`(${prov})`).width : 0;
        const half = Math.max(w1, w2) / 2 + 4;
        if (2 * half > W - 16) continue; // too wide for this screen: not drawn
        if (sy < -px * 2 || sy > H + px * 2 || sx + half < 0 || sx - half > W) continue;
        const x = Math.max(half + 8, Math.min(W - half - 8, sx));
        const y = Math.max(px + 44, Math.min(H - px * 2.2, sy));
        if (Math.abs(x - sx) > half * 1.2 || Math.abs(y - sy) > px * 3) continue; // the islands are off screen
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.lineJoin = "round";
        ctx.strokeStyle = "rgba(10,24,38,.7)";
        ctx.fillStyle = "rgba(244,232,200,.92)";
        ctx.font = `italic ${px.toFixed(1)}px ${font}`;
        ctx.lineWidth = Math.max(2, px * 0.14);
        ctx.strokeText(a.name, x, y);
        ctx.fillText(a.name, x, y);
        if (prov) {
          const p2 = px * 0.72;
          ctx.font = `italic ${p2.toFixed(1)}px ${font}`;
          ctx.lineWidth = Math.max(2, p2 * 0.14);
          ctx.strokeText(`(${prov})`, x, y + px * 1.05);
          ctx.fillText(`(${prov})`, x, y + px * 1.05);
        }
      }
    },
  };
}

export function install(app) {
  const w = app.w;
  // Land hexes within three steps of the sea: where estuaries and port basins can cut into a land hex.
  let near = null;
  const nearSea = () => {
    if (near) return near;
    near = new Uint8Array(w.grid.size);
    let front = [];
    for (let i = 0; i < w.grid.size; i++) if (w.water[i] === 1 || w.water[i] === 2) front.push(i);
    for (let step = 0; step < 3; step++) {
      const next = [];
      for (const i of front) {
        for (let d = 0; d < 6; d++) {
          const j = w.grid.neighbour(i, d);
          if (j >= 0 && w.water[j] === 0 && !near[j]) { near[j] = 1; next.push(j); }
        }
      }
      front = next;
    }
    return near;
  };
  app.registerOverlay(archipelagoLabels(app));
  let coast = null, hubs = null;
  app.loadData("coast").then((d) => {
    if (!d?.rings) return;
    coast = { rings: prepRings(d.rings), lines: prepRings(d.lines) };
    app.requestDraw();
  }, () => {});
  app.loadData("hubs").then((d) => {
    if (!d) return;
    const runways = (d.runways || []).map((r) => ({ ...prepRings([r.line])[0], width: r.width_m || 45 }));
    hubs = { aerodromes: prepRings((d.aerodromes || []).flatMap((a) => a.rings)), ports: prepRings((d.ports || []).flatMap((a) => a.rings)), runways };
    app.requestDraw();
  }, () => {});

  app.registerStaticLayer({
    id: "coast", z: 45, minRpx: COAST_MIN_RPX,
    visible: () => !!coast,
    sig: () => (coast ? 1 : 0),
    draw(ctx, vp, _w, o) {
      const px = 1 / vp.s;
      ctx.save();
      ctx.clip(hexPath(w, o.cells, (i) => w.water[i] !== 0));
      ctx.fillStyle = o.lens ? "rgba(140,140,125,.85)" : LAND;
      for (const r of coast.rings) if (seen(r, vp)) ctx.fill(r.P, "evenodd");
      ctx.restore();
      // The sea inside land hexes (estuaries, bays, the water around a port): water on an offscreen canvas, the
      // land polygons cut out of it (nonzero, so the overlapping pieces of the source do not leave seams), laid over
      // the land hexes next to the sea.
      const cv = ctx.canvas;
      const off = (this._off ??= document.createElement("canvas"));
      if (off.width !== cv.width || off.height !== cv.height) { off.width = cv.width; off.height = cv.height; }
      const g = off.getContext("2d");
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, off.width, off.height);
      g.setTransform(ctx.getTransform());
      const shore = (i) => w.water[i] === 0 && nearSea()[i] === 1;
      g.fillStyle = o.lens ? "rgba(120,170,210,.75)" : SEA;
      g.fill(hexPath(w, o.cells, shore));
      g.globalCompositeOperation = "destination-out";
      g.fillStyle = "#000";
      for (const r of coast.rings) if (seen(r, vp)) g.fill(r.P, "nonzero");
      g.globalCompositeOperation = "source-over";
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.drawImage(off, 0, 0);
      ctx.restore();
      ctx.strokeStyle = SHORE;
      ctx.lineWidth = Math.max(0.8, Math.min(2, o.Rpx * 0.04)) * px;
      ctx.lineJoin = "round";
      for (const r of coast.lines) if (seen(r, vp)) ctx.stroke(r.P);
    },
  });
  app.registerStaticLayer({
    id: "hub-areas", z: 62, minRpx: HUBS_MIN_RPX, // above the town tiles: an airport sits beside its city
    visible: () => !!hubs,
    sig: () => (hubs ? 1 : 0),
    draw(ctx, vp, _w, o) {
      const px = 1 / vp.s;
      ctx.lineJoin = "round";
      ctx.fillStyle = "rgba(188,186,168,.95)";
      ctx.strokeStyle = "rgba(40,38,32,.85)";
      ctx.lineWidth = 1.4 * px;
      for (const r of hubs.aerodromes) if (seen(r, vp)) { ctx.fill(r.P, "evenodd"); ctx.stroke(r.P); }
      ctx.fillStyle = "rgba(128,122,116,.95)";
      for (const r of hubs.ports) if (seen(r, vp)) { ctx.fill(r.P, "evenodd"); ctx.stroke(r.P); }
      ctx.lineCap = "butt";
      for (const r of hubs.runways) {
        if (!seen(r, vp)) continue;
        ctx.strokeStyle = "rgba(34,34,34,1)";
        ctx.lineWidth = Math.max(3 * px, r.width / 1000);
        ctx.stroke(r.P);
        ctx.strokeStyle = "rgba(245,240,220,.85)"; // the centre line
        ctx.setLineDash([4 * px, 4 * px]);
        ctx.lineWidth = Math.max(0.6 * px, r.width / 12000);
        ctx.stroke(r.P);
        ctx.setLineDash([]);
      }
    },
  });
}
