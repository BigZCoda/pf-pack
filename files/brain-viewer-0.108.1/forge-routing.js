/*
 * DOM-free routing kernel for the Forge.  It accepts rendered circles, boxes
 * and annular sectors, so it is equally usable on the initial render and from
 * the lightweight drag repaint.
 */
(function(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ForgeRouting = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  const EPS = 0.75, MAX_OBSTACLES = 24, TAU = Math.PI * 2;
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const same = (a, b) => dist(a, b) < 0.01;
  const norm = a => ((a % TAU) + TAU) % TAU;
  const angleIn = (a, a0, a1) => norm(a - a0) <= norm(a1 - a0) + 1e-8;
  const polar = (cx, cy, r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const pointSegDistance = (p, a, b) => {
    const dx = b[0] - a[0], dy = b[1] - a[1], d2 = dx * dx + dy * dy;
    if (!d2) return dist(p, a);
    const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d2));
    return Math.hypot(p[0] - (a[0] + dx * t), p[1] - (a[1] + dy * t));
  };
  function boundsOf(o) {
    if (o.kind === "rect") return { x0: o.x, y0: o.y, x1: o.x + o.w, y1: o.y + o.h };
    if (o.kind === "circle") return { x0: o.cx - o.r, y0: o.cy - o.r, x1: o.cx + o.r, y1: o.cy + o.r };
    const angles = [o.a0, o.a1, 0, Math.PI / 2, Math.PI, Math.PI * 1.5].filter(a => angleIn(a, o.a0, o.a1));
    const ps = angles.flatMap(a => [polar(o.cx, o.cy, o.rIn, a), polar(o.cx, o.cy, o.rOut, a)]);
    return { x0: Math.min(...ps.map(p => p[0])), y0: Math.min(...ps.map(p => p[1])), x1: Math.max(...ps.map(p => p[0])), y1: Math.max(...ps.map(p => p[1])) };
  }
  function expanded(o, pad) {
    if (o._forgeRoutePrepared) return o;
    let q;
    if (o.kind === "circle") q = { kind: "circle", id: o.id || "", cx: o.cx, cy: o.cy, r: o.r + pad };
    else if (o.kind === "sector") {
      // Radial walls are closest at the inner rim, so padding by rOut leaves
      // a too-narrow angular gap there.  Forge bands always have an inner
      // radius; use it when present and retain a sane fallback for a sector
      // whose radial edge reaches the centre.
      const angularPad = pad / Math.max(1, o.rIn || o.rOut);
      q = { kind: "sector", id: o.id || "", cx: o.cx, cy: o.cy, rIn: Math.max(0, o.rIn - pad), rOut: o.rOut + pad, a0: o.a0 - angularPad, a1: o.a1 + angularPad };
    } else q = { kind: "rect", id: o.id || "", x: o.x - pad, y: o.y - pad, w: o.w + pad * 2, h: o.h + pad * 2 };
    return Object.assign(q, boundsOf(q), { _forgeRoutePrepared: true });
  }
  function prepare(obstacles, clearance) {
    const pad = clearance == null ? 12 : clearance;
    return (obstacles || []).filter(o => o && ["circle", "rect", "sector"].includes(o.kind)).map(o => expanded(o, pad));
  }
  const rectOf = o => ({ x0: o.x, y0: o.y, x1: o.x + o.w, y1: o.y + o.h });
  function segmentHitsRect(a, b, o) {
    const r = rectOf(o), dx = b[0] - a[0], dy = b[1] - a[1];
    let lo = 0, hi = 1;
    for (const [p, q] of [[-dx, a[0] - r.x0], [dx, r.x1 - a[0]], [-dy, a[1] - r.y0], [dy, r.y1 - a[1]]]) {
      if (Math.abs(p) < 1e-9) { if (q < 0) return false; continue; }
      const t = q / p;
      if (p < 0) { if (t > hi) return false; if (t > lo) lo = t; }
      else { if (t < lo) return false; if (t < hi) hi = t; }
    }
    return hi - lo > 1e-6; // a candidate may kiss a corner; it is placed EPS outside.
  }
  function pointInSector(p, o) {
    const dx = p[0] - o.cx, dy = p[1] - o.cy, r = Math.hypot(dx, dy);
    return r > o.rIn + 1e-7 && r < o.rOut - 1e-7 && angleIn(Math.atan2(dy, dx), o.a0, o.a1);
  }
  function circleCrossings(a, b, cx, cy, r) {
    const dx = b[0] - a[0], dy = b[1] - a[1], fx = a[0] - cx, fy = a[1] - cy;
    const A = dx * dx + dy * dy, B = 2 * (fx * dx + fy * dy), C = fx * fx + fy * fy - r * r, D = B * B - 4 * A * C;
    if (A < 1e-9 || D < -1e-8) return [];
    const s = Math.sqrt(Math.max(0, D));
    return [(-B - s) / (2 * A), (-B + s) / (2 * A)].filter(t => t >= -1e-8 && t <= 1 + 1e-8).map(t => [a[0] + dx * t, a[1] + dy * t]);
  }
  function orient(a, b, c) { return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]); }
  function segmentCrosses(a, b, c, d) {
    const o1 = orient(a, b, c), o2 = orient(a, b, d), o3 = orient(c, d, a), o4 = orient(c, d, b);
    return Math.min(o1, o2) <= 1e-8 && Math.max(o1, o2) >= -1e-8 && Math.min(o3, o4) <= 1e-8 && Math.max(o3, o4) >= -1e-8;
  }
  function segmentHitsSector(a, b, o) {
    if (pointInSector(a, o) || pointInSector(b, o)) return true;
    for (const r of [o.rIn, o.rOut]) for (const p of circleCrossings(a, b, o.cx, o.cy, r)) if (angleIn(Math.atan2(p[1] - o.cy, p[0] - o.cx), o.a0, o.a1)) return true;
    for (const angle of [o.a0, o.a1]) if (segmentCrosses(a, b, polar(o.cx, o.cy, o.rIn, angle), polar(o.cx, o.cy, o.rOut, angle))) return true;
    return false;
  }
  function segmentHits(a, b, o) {
    if (o.kind === "circle") return pointSegDistance([o.cx, o.cy], a, b) < o.r - 1e-6;
    if (o.kind === "sector") return segmentHitsSector(a, b, o);
    return segmentHitsRect(a, b, o);
  }
  function clearSegment(a, b, obstacles, clearance) {
    const prepared = (obstacles || []).some(o => o && o._forgeRoutePrepared) ? obstacles : prepare(obstacles, clearance);
    return !prepared.some(o => segmentHits(a, b, o));
  }
  function isClear(points, obstacles, clearance) {
    const prepared = prepare(obstacles, clearance);
    for (let i = 1; i < points.length; i++) if (!clearSegment(points[i - 1], points[i], prepared, 0)) return false;
    return true;
  }
  function candidatePoints(o) {
    if (o.kind === "rect") return [[o.x - EPS, o.y - EPS], [o.x + o.w + EPS, o.y - EPS], [o.x + o.w + EPS, o.y + o.h + EPS], [o.x - EPS, o.y + o.h + EPS]];
    if (o.kind === "circle") {
      const r = (o.r + EPS) / Math.cos(Math.PI / 8), out = [];
      for (let i = 0; i < 8; i++) { const a = i * TAU / 8; out.push([o.cx + r * Math.cos(a), o.cy + r * Math.sin(a)]); }
      return out;
    }
    const span = norm(o.a1 - o.a0), aPad = EPS / Math.max(1, o.rOut) + 0.01;
    const aa = [o.a0 - aPad, o.a0 + span / 2, o.a1 + aPad], out = [];
    // Three exterior points approximate the curved outer wall.  Increase their
    // radius enough that the two connecting chords remain outside that wall.
    const outer = (o.rOut + EPS) / Math.cos(Math.min(Math.PI / 4, (span + aPad * 2) / 4));
    for (const r of [Math.max(0, o.rIn - EPS), outer]) for (const a of aa) out.push(polar(o.cx, o.cy, r, a));
    return out;
  }
  function pointInside(p, o) {
    if (o.kind === "circle") return Math.hypot(p[0] - o.cx, p[1] - o.cy) < o.r - 1e-6;
    if (o.kind === "sector") return pointInSector(p, o);
    return p[0] > o.x && p[0] < o.x + o.w && p[1] > o.y && p[1] < o.y + o.h;
  }
  function distanceToObstacle(a, b, o) {
    if (segmentHits(a, b, o)) return 0;
    if (o.kind === "circle") return Math.max(0, pointSegDistance([o.cx, o.cy], a, b) - o.r);
    // Rect and sector use their extent rather than their centre.  This is what
    // keeps a 40×1000 barrier relevant when its centre is far from the line.
    const q = o.kind === "rect" ? rectOf(o) : o;
    const corners = [[q.x0 == null ? q.x : q.x0, q.y0 == null ? q.y : q.y0], [q.x1 == null ? q.x + q.w : q.x1, q.y0 == null ? q.y : q.y0], [q.x1 == null ? q.x + q.w : q.x1, q.y1 == null ? q.y + q.h : q.y1], [q.x0 == null ? q.x : q.x0, q.y1 == null ? q.y + q.h : q.y1]];
    const pointRect = p => Math.hypot(Math.max(q.x0 - p[0], 0, p[0] - q.x1), Math.max(q.y0 - p[1], 0, p[1] - q.y1));
    return Math.min(...corners.map(p => pointSegDistance(p, a, b)), pointRect(a), pointRect(b));
  }
  function relevant(start, end, obstacles, clearance) {
    const span = Math.max(1, dist(start, end)), corridor = Math.min(520, Math.max(180, span * 0.42));
    const rows = obstacles.map((o, index) => ({ o, index, d: distanceToObstacle(start, end, o) }))
      .filter(x => x.d <= corridor + clearance)
      .sort((a, b) => a.d - b.d || String(a.o.id || "").localeCompare(String(b.o.id || "")) || a.index - b.index);
    const kept = rows.slice(0, MAX_OBSTACLES).map(x => x.o);
    // When a dense corridor exceeds the cap, outside-corner guides still give
    // Dijkstra a bounded way to go around omitted blockers.  All blockers stay
    // in collision checks, so a guide can never authorize a crossing.
    const omitted = rows.slice(MAX_OBSTACLES);
    let guides = [];
    if (omitted.length) {
      const all = rows.map(x => x.o), b = { x0: Math.min(...all.map(o => o.x0)), y0: Math.min(...all.map(o => o.y0)), x1: Math.max(...all.map(o => o.x1)), y1: Math.max(...all.map(o => o.y1)) };
      const pad = Math.max(32, clearance * 2, span * 0.08);
      guides = [[b.x0 - pad, b.y0 - pad], [b.x1 + pad, b.y0 - pad], [b.x1 + pad, b.y1 + pad], [b.x0 - pad, b.y1 + pad]];
    }
    return { kept, guides };
  }
  function simplify(points, obstacles) {
    const out = [points[0]];
    for (let i = 1; i < points.length - 1; i++) if (!clearSegment(out[out.length - 1], points[i + 1], obstacles, 0)) out.push(points[i]);
    out.push(points[points.length - 1]);
    return out.filter((p, i, a) => !i || !same(p, a[i - 1]));
  }
  function signedFromBaseline(start, end, p) {
    const dx = end[0] - start[0], dy = end[1] - start[1], d = Math.hypot(dx, dy) || 1;
    return (dx * (p[1] - start[1]) - dy * (p[0] - start[0])) / d;
  }
  function route(start, end, obstacles, options) {
    options = options || {};
    const clearance = options.clearance == null ? 14 : options.clearance, all = prepare(obstacles, clearance);
    // A fallback lane can stay distinct in a narrow, otherwise clear corridor
    // without inflating its obstacles past feasibility.  It is only accepted
    // when both legs are clear, never as an authorization to cross anything.
    if (options.laneBend) {
      const dx = end[0] - start[0], dy = end[1] - start[1], d = Math.hypot(dx, dy) || 1;
      const sign = Math.sign(options.bias || 1), mid = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2];
      const via = [mid[0] - dy / d * sign * options.laneBend, mid[1] + dx / d * sign * options.laneBend];
      if (isClear([start, via, end], all, 0)) return { points: [start, via, end], clear: true, blocked: false, laneBend: true };
    }
    // `force` used to suppress this check.  That made a caller which was
    // already recovering from a colliding *curve* forbid an otherwise clear
    // chord, producing a gratuitous second detour (and, at a port, a visible
    // reversal).  Collision validation belongs to the actual candidate
    // geometry; a clear direct chord always wins, regardless of the legacy
    // option value.
    if (isClear([start, end], all, 0)) return { points: [start, end], clear: true, blocked: false };
    if (all.some(o => pointInside(start, o) || pointInside(end, o))) return { points: [start, end], clear: false, blocked: true };
    const near = relevant(start, end, all, 0), points = [start, end];
    for (const o of near.kept) for (const p of candidatePoints(o)) points.push(p);
    for (const p of near.guides) points.push(p);
    const n = points.length, costs = Array(n).fill(Infinity), prev = Array(n).fill(-1), done = Array(n).fill(false);
    costs[0] = 0;
    const side = Math.sign(options.bias || 0), biasWeight = side ? Math.min(0.16, Math.abs(options.bias) / 900) : 0;
    for (let pass = 0; pass < n; pass++) {
      let u = -1;
      for (let i = 0; i < n; i++) if (!done[i] && (u < 0 || costs[i] < costs[u] - 1e-7 || (Math.abs(costs[i] - costs[u]) < 1e-7 && i < u))) u = i;
      if (u < 0 || !Number.isFinite(costs[u])) break;
      if (u === 1) break;
      done[u] = true;
      for (let v = 0; v < n; v++) {
        if (v === u || done[v] || !clearSegment(points[u], points[v], all, 0)) continue;
        const mid = [(points[u][0] + points[v][0]) / 2, (points[u][1] + points[v][1]) / 2];
        const wrongSide = side ? Math.max(0, -side * signedFromBaseline(start, end, mid)) : 0;
        const next = costs[u] + dist(points[u], points[v]) + wrongSide * biasWeight;
        if (next < costs[v] - 1e-7 || (Math.abs(next - costs[v]) < 1e-7 && u < prev[v])) { costs[v] = next; prev[v] = u; }
      }
    }
    if (!Number.isFinite(costs[1])) {
      if (isClear([start, end], all, 0)) return { points: [start, end], clear: true, blocked: false, collapsed: true };
      return { points: [start, end], clear: false, blocked: true };
    }
    const out = [];
    for (let at = 1; at >= 0; at = prev[at]) { out.push(points[at]); if (at === 0) break; }
    out.reverse();
    const clean = simplify(out, all), clear = isClear(clean, all, 0);
    return { points: clean, clear, blocked: !clear };
  }
  function sample(points, t) {
    if (points.length === 1) return points[0].slice();
    const lengths = [], total = points.slice(1).reduce((s, p, i) => { const d = dist(points[i], p); lengths.push(d); return s + d; }, 0);
    let want = Math.max(0, Math.min(1, t)) * total;
    for (let i = 1; i < points.length; i++) {
      if (want <= lengths[i - 1] || i === points.length - 1) { const d = lengths[i - 1] || 1, q = want / d; return [points[i - 1][0] + (points[i][0] - points[i - 1][0]) * q, points[i - 1][1] + (points[i][1] - points[i - 1][1]) * q]; }
      want -= lengths[i - 1];
    }
    return points[points.length - 1].slice();
  }
  const pathD = points => "M" + points.map(p => `${p[0]},${p[1]}`).join(" L");
  function linePoint(a, b, t) {
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  }
  function quadPoint(a, c, b, t) {
    const u = 1 - t;
    return [u * u * a[0] + 2 * u * t * c[0] + t * t * b[0],
      u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]];
  }
  function cubicPoint(a, c1, c2, b, t) {
    const u = 1 - t, u2 = u * u, t2 = t * t;
    return [u2 * u * a[0] + 3 * u2 * t * c1[0] + 3 * u * t2 * c2[0] + t2 * t * b[0],
      u2 * u * a[1] + 3 * u2 * t * c1[1] + 3 * u * t2 * c2[1] + t2 * t * b[1]];
  }
  function roundedSegments(points, radius) {
    const clean = (points || []).filter((p, i, a) => p && (!i || !same(p, a[i - 1])));
    if (clean.length < 2) return [];
    if (!(radius > 0) || clean.length < 3) return clean.slice(1).map((p, i) => ({ kind: "line", a: clean[i], b: p }));
    const cuts = clean.map(p => ({ before: p, after: p }));
    for (let i = 1; i < clean.length - 1; i++) {
      const p = clean[i], prev = clean[i - 1], next = clean[i + 1];
      const beforeD = dist(p, prev), afterD = dist(p, next);
      const trim = Math.min(radius, beforeD * 0.35, afterD * 0.35);
      cuts[i].before = linePoint(p, prev, trim / Math.max(beforeD, 1e-9));
      cuts[i].after = linePoint(p, next, trim / Math.max(afterD, 1e-9));
    }
    const out = [], addLine = (a, b) => { if (!same(a, b)) out.push({ kind: "line", a, b }); };
    let at = clean[0];
    for (let i = 1; i < clean.length - 1; i++) {
      addLine(at, cuts[i].before);
      if (!same(cuts[i].before, cuts[i].after)) out.push({ kind: "quad", a: cuts[i].before, c: clean[i], b: cuts[i].after });
      at = cuts[i].after;
    }
    addLine(at, clean[clean.length - 1]);
    return out;
  }
  function flattenSegment(seg, maxStep, tolerance, out, depth) {
    if (seg.kind === "line") {
      out.push({ seg, u: 1, p: seg.b.slice() });
      return;
    }
    if (seg.kind === "cubic") {
      const mid = cubicPoint(seg.a, seg.c1, seg.c2, seg.b, 0.5);
      const flat = Math.max(pointSegDistance(seg.c1, seg.a, seg.b), pointSegDistance(seg.c2, seg.a, seg.b));
      if (depth >= 14 || (dist(seg.a, seg.b) <= maxStep && flat <= tolerance)) {
        out.push({ seg, u: 1, p: seg.b.slice() });
        return;
      }
      const c1m = linePoint(seg.a, seg.c1, 0.5), mc = linePoint(seg.c1, seg.c2, 0.5), c2m = linePoint(seg.c2, seg.b, 0.5);
      const left = { kind: "cubic", a: seg.a, c1: c1m, c2: linePoint(c1m, mc, 0.5), b: mid };
      const right = { kind: "cubic", a: mid, c1: linePoint(mc, c2m, 0.5), c2: c2m, b: seg.b };
      flattenSegment(left, maxStep, tolerance, out, depth + 1);
      flattenSegment(right, maxStep, tolerance, out, depth + 1);
      return;
    }
    const mid = quadPoint(seg.a, seg.c, seg.b, 0.5);
    const flat = pointSegDistance(seg.c, seg.a, seg.b);
    if (depth >= 14 || (dist(seg.a, seg.b) <= maxStep && flat <= tolerance)) {
      out.push({ seg, u: 1, p: seg.b.slice() });
      return;
    }
    const left = { kind: "quad", a: seg.a, c: linePoint(seg.a, seg.c, 0.5), b: mid };
    const right = { kind: "quad", a: mid, c: linePoint(seg.c, seg.b, 0.5), b: seg.b };
    flattenSegment(left, maxStep, tolerance, out, depth + 1);
    flattenSegment(right, maxStep, tolerance, out, depth + 1);
  }
  function flattened(segments, options) {
    const maxStep = options && options.maxStep || 3, tolerance = options && options.tolerance || 0.25, out = [];
    for (const seg of segments || []) {
      if (!out.length) out.push({ seg, u: 0, p: seg.a.slice() });
      flattenSegment(seg, maxStep, tolerance, out, 0);
    }
    return out;
  }
  function curveSamples(segments, options) {
    return flattened(segments, options).map(x => x.p);
  }
  function sampleSegments(segments, t, options) {
    const rows = flattened(segments, options), clean = [];
    for (const row of rows) {
      const last = clean[clean.length - 1];
      if (last && same(last.p, row.p)) continue;
      clean.push(row);
    }
    if (!clean.length) return [0, 0];
    if (clean.length === 1) return clean[0].p.slice();
    if (t >= 1) return clean[clean.length - 1].p.slice();
    if (t <= 0) return clean[0].p.slice();
    const lengths = [], total = clean.slice(1).reduce((sum, row, i) => {
      const d = dist(clean[i].p, row.p); lengths.push(d); return sum + d;
    }, 0);
    let want = Math.max(0, Math.min(1, t)) * total;
    for (let i = 1; i < clean.length; i++) {
      const d = lengths[i - 1] || 1;
      if (want <= d || i === clean.length - 1) {
        const f = Math.max(0, Math.min(1, want / d)), left = clean[i - 1], right = clean[i];
        // A flattened quadratic can split at a de Casteljau boundary.  Use
        // the segment on the right of that boundary; using the left segment
        // for the final line was the old source of labels/bubbles stopping at
        // the last waypoint instead of reaching the path's endpoint.
        const seg = left.seg === right.seg ? left.seg : right.seg;
        if (seg.kind === "quad") {
          const u = left.seg === right.seg ? left.u + (right.u - left.u) * f : f;
          return quadPoint(seg.a, seg.c, seg.b, u);
        }
        if (seg.kind === "cubic") {
          const u = left.seg === right.seg ? left.u + (right.u - left.u) * f : f;
          return cubicPoint(seg.a, seg.c1, seg.c2, seg.b, u);
        }
        const u = left.seg === right.seg ? left.u + (right.u - left.u) * f : f;
        return linePoint(seg.a, seg.b, u);
      }
      want -= d;
    }
    return clean[clean.length - 1].p.slice();
  }
  function curvePathD(segments) {
    if (!segments || !segments.length) return "";
    return "M" + segments[0].a.map(Number).join(",") + segments.map(seg => seg.kind === "quad"
      ? ` Q${seg.c[0]},${seg.c[1]} ${seg.b[0]},${seg.b[1]}`
      : seg.kind === "cubic" ? ` C${seg.c1[0]},${seg.c1[1]} ${seg.c2[0]},${seg.c2[1]} ${seg.b[0]},${seg.b[1]}`
      : ` L${seg.b[0]},${seg.b[1]}`).join("");
  }
  function isCurveClear(segments, obstacles, clearance, options) {
    const prepared = (obstacles || []).some(o => o && o._forgeRoutePrepared) ? obstacles : prepare(obstacles, clearance);
    const samples = curveSamples(segments, options);
    return !prepared.some(o => {
      for (let i = 1; i < samples.length; i++) if (segmentHits(samples[i - 1], samples[i], o)) return true;
      return false;
    });
  }
  // A manually placed bend is a desired point on a continuous cable, not a
  // sharp polyline corner. Solve the quadratic control point so t=.5 is the
  // requested waypoint, then let the same sampled collision checker decide
  // whether that smooth cable is safe.
  function quadraticWaypoint(start, end, waypoint, obstacles, options) {
    options = options || {};
    const control = [2 * waypoint[0] - (start[0] + end[0]) / 2, 2 * waypoint[1] - (start[1] + end[1]) / 2];
    const segment = { kind: "quad", a: start.slice(), c: control, b: end.slice() };
    const clear = isCurveClear([segment], obstacles, options.clearance, options);
    return {
      points: [start.slice(), waypoint.slice(), end.slice()],
      control,
      segments: [segment],
      d: curvePathD([segment]),
      sample: t => quadPoint(segment.a, segment.c, segment.b, Math.max(0, Math.min(1, t))),
      clear,
    };
  }
  function cubicPath(start, end, c1, c2, obstacles, options) {
    options = options || {};
    const segment = { kind: "cubic", a: start.slice(), c1: c1.slice(), c2: c2.slice(), b: end.slice() };
    const clear = isCurveClear([segment], obstacles, options.clearance, options);
    return {
      points: [start.slice(), end.slice()],
      controls: [segment.c1.slice(), segment.c2.slice()],
      segments: [segment],
      d: curvePathD([segment]),
      sample: t => cubicPoint(segment.a, segment.c1, segment.c2, segment.b, Math.max(0, Math.min(1, t))),
      clear,
    };
  }
  // Round only when the sampled curve itself is clear.  A quadratic's control
  // polygon is not enough here: cutting a waypoint can turn a clear polyline
  // into a collision, especially around circular and annular obstacles.
  function roundedPath(points, obstacles, options) {
    options = options || {};
    const clean = (points || []).filter((p, i, a) => p && (!i || !same(p, a[i - 1])));
    const requested = options.radius == null ? 10 : Math.max(0, options.radius);
    const radii = requested ? [requested, requested * 0.68, requested * 0.42, requested * 0.2, 0] : [0];
    for (const radius of radii) {
      const segments = roundedSegments(clean, radius);
      if (isCurveClear(segments, obstacles, options.clearance, options)) {
        return { points: clean, segments, d: curvePathD(segments), sample: t => sampleSegments(segments, t, options), clear: true, radius };
      }
    }
    const segments = roundedSegments(clean, 0);
    return { points: clean, segments, d: curvePathD(segments), sample: t => sampleSegments(segments, t, options), clear: false, radius: 0 };
  }
  // A cross-cell edge is drawn from the parent cell's rim, but a sibling band
  // can occupy that exact rim location.  Search nearest angular exits in a
  // stable order and prove the short radial escape is clear against the
  // already-expanded collision model before returning it.
  function clearCircleTerminal(g, toward, obstacles, guard) {
    const desired = Math.atan2(toward[1] - g.cy, toward[0] - g.cx);
    const step = Math.PI / 90, reach = guard == null ? 30 : guard, r = g.r == null ? g.R : g.r;
    for (let i = 0; i <= 90; i++) for (const sign of i ? [1, -1] : [1]) {
      const a = desired + sign * i * step, p = polar(g.cx, g.cy, r, a);
      const outside = polar(g.cx, g.cy, r + reach, a);
      if (clearSegment(p, outside, obstacles, 0)) return p;
    }
    return null;
  }
  // Saved top/bottom ports on a band lie on a circular rim.  A package can sit
  // immediately beside that point, so retain the requested rim while sliding
  // its angle to the nearest clearance-proven position. `direction` selects
  // the short ray that must also be open (+1 follows the boundary normal).
  function clearSectorTerminal(g, side, obstacles, direction, guard) {
    const reach = guard == null ? 24 : guard, dir = direction == null ? 1 : direction;
    const pointAt = (a, r) => [g.cx + r * Math.cos(a), g.cy + r * Math.sin(a)];
    const accepts = (p, normal) => clearSegment(p, [p[0] + normal[0] * reach * dir, p[1] + normal[1] * reach * dir], obstacles, 0);
    if (side === "top" || side === "bottom") {
      const span = norm(g.a1 - g.a0), mid = g.a0 + span / 2, r = side === "top" ? g.rOut : g.rIn;
      const step = Math.min(Math.PI / 180, 3 / Math.max(1, r)), count = Math.ceil(span / (2 * step));
      for (let i = 0; i <= count; i++) for (const sign of i ? [1, -1] : [1]) {
        const a = mid + sign * i * step;
        if (!angleIn(a, g.a0, g.a1)) continue;
        const p = pointAt(a, r), radial = [Math.cos(a), Math.sin(a)];
        if (accepts(p, side === "top" ? radial : [-radial[0], -radial[1]])) return p;
      }
      return null;
    }
    const a = side === "left" ? g.a0 : g.a1, r = (g.rIn + g.rOut) / 2;
    const p = pointAt(a, r);
    const normal = side === "left" ? [Math.sin(a), -Math.cos(a)] : [-Math.sin(a), Math.cos(a)];
    return accepts(p, normal) ? p : null;
  }
  function portNormal(g, p, side) {
    if (g.kind === "rect" || g.kind === "free" || g.kind === "tile") return ({ left: [-1, 0], right: [1, 0], top: [0, -1], bottom: [0, 1] })[side];
    if (g.kind === "seg" || g.kind === "sector") {
      // Forge's portPoint maps top to the segment's OUTER rim and bottom to
      // its INNER rim; the latter's safe exit is therefore radially inward.
      if (side === "left") return [Math.sin(g.a0), -Math.cos(g.a0)];
      if (side === "right") return [-Math.sin(g.a1), Math.cos(g.a1)];
      const a = Math.atan2(p[1] - g.cy, p[0] - g.cx);
      return side === "bottom" ? [-Math.cos(a), -Math.sin(a)] : [Math.cos(a), Math.sin(a)];
    }
    const cx = g.cx, cy = g.cy, d = Math.hypot(p[0] - cx, p[1] - cy) || 1;
    return [(p[0] - cx) / d, (p[1] - cy) / d];
  }
  return {
    route, prepare, isClear, clearSegment, sample, pathD, roundedPath, curveSamples,
    isCurveClear, quadraticWaypoint, cubicPath, clearCircleTerminal, clearSectorTerminal, portNormal
  };
});