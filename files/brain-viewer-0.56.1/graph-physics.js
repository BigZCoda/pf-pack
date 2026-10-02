// The physics the moving bubbles run on, in one place (2026-09-21, 0.40.0).
// It was written for /map -- Zak, 9/08: "I just want it to look good, have physics, not be super static" -- and lived
// inside that page until the home board wanted the same bubbles for its people. There is ONE engine, so this is the
// map's own three forces lifted out word for word and handed the two things they used to read off the page directly:
// how big a node is, and which node the pointer is holding. Nothing else changed, and nothing here fetches anything.
//
//   BV.graph.gravity(k, {skip})                     a weak spring to the middle: what keeps a bubble with no lines on screen
//   BV.graph.collide(strength, {radius, pad, skip}) bubbles (and their labels) do not sit on each other; the bundled d3
//                                                   exposes no collide, so this is the pairwise one
//   BV.graph.breathe(amp, {skip})                   the drift that stops a settled layout from looking like a picture
//   BV.graph.ready()                                a promise for the vendored force-graph, loaded once per page
//   BV.graph.token(name) / BV.graph.rgba(hex, a)    a css token as a value, and one as a translucent fill
//
// `skip(n)` is true for a node the forces must leave alone, which is the one being dragged. d3 calls `initialize` with
// the node list whenever the graph changes, so each force keeps its own reference and no caller has to re-install it.
(function () {
  const fn = (f, d) => (typeof f === "function" ? f : d);

  function gravity(k, o) {
    const skip = fn((o || {}).skip, () => false);
    let ns = [];
    const f = () => { for (const n of ns) { if (skip(n)) continue; n.vx -= n.x * k; n.vy -= n.y * k; } };
    f.initialize = nodes => { ns = nodes; };
    return f;
  }

  function collide(strength, o) {
    o = o || {};
    const skip = fn(o.skip, () => false);
    const radius = fn(o.radius, n => n.r || 6);
    const pad = fn(o.pad, () => 10);
    let ns = [];
    const f = () => {
      for (let i = 0; i < ns.length; i++) {
        const a = ns[i], ra = radius(a) + pad(a);
        for (let j = i + 1; j < ns.length; j++) {
          const b = ns[j], rb = radius(b) + pad(b), min = ra + rb;
          let dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy);
          if (d >= min) continue;
          if (d < 1e-6) { dx = (Math.random() - 0.5) * 1e-3; dy = (Math.random() - 0.5) * 1e-3; d = Math.hypot(dx, dy); }
          const push = (min - d) / d * strength, wa = rb / min, wb = ra / min;   // the bigger bubble gives way less
          if (!skip(a)) { a.vx -= dx * push * wa; a.vy -= dy * push * wa; }
          if (!skip(b)) { b.vx += dx * push * wb; b.vy += dy * push * wb; }
        }
      }
    };
    f.initialize = nodes => { ns = nodes; };
    return f;
  }

  function breathe(amp, o) {
    const skip = fn((o || {}).skip, () => false);
    let ns = [];
    const f = () => {
      const t = performance.now() / 1000;
      for (const n of ns) { if (skip(n)) continue; n.vx += Math.sin(t * 0.9 + n.ph) * amp; n.vy += Math.cos(t * 0.7 + n.ph * 1.3) * amp; }
    };
    f.initialize = nodes => { ns = nodes; for (const n of ns) if (n.ph == null) n.ph = Math.random() * Math.PI * 2; };
    return f;
  }

  // ---- the vendored library, loaded once ----
  // /map carries its own script tag because it is the whole page there. Anything that wants the bubbles inside
  // something else (the home board's People) asks for this instead, and several askers share the one load.
  const SRC = "/static/vendor/force-graph.min.js";
  let LOADING = null;
  function ready() {
    if (typeof window.ForceGraph === "function") return Promise.resolve(window.ForceGraph);
    if (LOADING) return LOADING;
    LOADING = new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = SRC;
      s.onload = () => (typeof window.ForceGraph === "function" ? res(window.ForceGraph) : rej(new Error("the bubbles did not load")));
      s.onerror = () => { LOADING = null; rej(new Error("the bubbles did not load")); };
      document.head.appendChild(s);
    });
    return LOADING;
  }

  const token = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const rgba = (hex, a) => {
    const h = String(hex || "#000").replace("#", "");
    const n = parseInt(h.length === 3 ? h.replace(/./g, c => c + c) : h, 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  };

  window.BV = window.BV || {};
  window.BV.graph = { gravity, collide, breathe, ready, token, rgba, VENDOR: SRC };
})();
