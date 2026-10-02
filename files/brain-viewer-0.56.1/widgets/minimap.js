// Minimap: the brain drawn small, as a constellation around the sun. The projects sit on the inner ring, the people
// and the standing threads on the ring beyond it, and a hairline joins two of them when the ledgers or the cards say
// they touch. A node is as big as the work open on it and as bright as how recently something moved there.
// Hover names it, a press opens it, and the control in the head opens the whole drawing out to the full width.
(function () {
const KINDS = { project: 1, group: 2, person: 3 };     // the rings, inside out
const MAX_SMALL = 26, MAX_WIDE = 54;

BV.widgets.register({
  id: "minimap", contract: 1, title: "The brain", size: "4", defaultOn: false, expand: true,
  source: "the projects, threads and people the brain holds, with the work open on each and what moved there lately (GET /api/graph, GET /api/moved)",

  mount(el, api) {
    if (!document.getElementById("bv-minimap-css")) {
      const s = document.createElement("style");
      s.id = "bv-minimap-css";
      s.textContent = `
        .mm svg { display: block; width: 100%; height: auto; }
        .mm .nd { cursor: pointer; }
        .mm .nd circle { fill: var(--muted); opacity: .38; transition: opacity .2s ease; }
        .mm .nd.lit circle { fill: var(--accent); opacity: .95; }
        .mm .nd.today circle { animation: bvpulse 3.6s ease-in-out infinite; }
        .mm .nd:hover circle { opacity: 1; }
        .mm .nd text { font-family: var(--font-ui); font-size: 8.5px; letter-spacing: .1em; text-transform: uppercase;
                       fill: var(--muted); pointer-events: none; }
        .mm .nd.lit text { fill: var(--ink-soft); }
        .mm .nd:hover text { fill: var(--accent); }
        .mm .wire { stroke: var(--rule-soft); fill: none; }
        .mm .none { color: var(--muted); font-size: 13px; }
        @keyframes bvpulse { 0%, 100% { opacity: .55; } 50% { opacity: 1; } }
        @media (prefers-reduced-motion: reduce) { .mm .nd.today circle { animation: none; } }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="mm" data-mm></div>`;
    el.addEventListener("click", e => {
      const g = e.target.closest("[data-href]"); if (!g) return;
      window.location.href = g.dataset.href;
    });
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const soft = p => api.get(p).then(j => j, () => null);
    const [graph, moved] = await Promise.all([soft("/api/graph"), soft("/api/moved?limit=120")]);
    if (!graph) return api.fail(new Error("the graph could not be read"));
    el._graph = graph; el._moved = moved;
    draw(el, api);
  },
  resize(el, api) { draw(el, api); },
});

function draw(el, api) {
  const box = el.querySelector("[data-mm]"); if (!box || !el._graph) return;
  const esc = api.esc, wide = api.expanded;
  const g = el._graph, moved = el._moved || { items: [] };

  // ---- who is on the map ----
  const cap = wide ? MAX_WIDE : MAX_SMALL;
  let nodes = (g.nodes || []).filter(n => KINDS[n.type]);
  nodes.sort((a, b) => (KINDS[a.type] - KINDS[b.type]) || ((b.badge || 0) - (a.badge || 0)));
  const keep = nodes.filter(n => n.type !== "person" || (n.badge || 0) > 0);
  nodes = (keep.length >= 8 ? keep : nodes).slice(0, cap);
  if (!nodes.length) { box.innerHTML = `<p class="none">Nothing to draw yet.</p>`; return; }

  // ---- how lately something moved there ----
  const today = new Date().toISOString().slice(0, 10);
  const lines = (moved.items || []);
  const hay = lines.map(r => ({ day: r.day, text: (r.text || "").toLowerCase() }));
  const heat = n => {
    const words = terms(n);
    let seen = 0, fresh = false;
    for (const h of hay) if (words.some(w => h.text.indexOf(w) >= 0)) { seen++; if (h.day === today) fresh = true; }
    return { seen, fresh };
  };

  // ---- the rings, with the room a name needs taken out first (0.37.1) ----
  // Every node writes its label beside it, so the rings cannot be as wide as the box: 0.37.0 sized them to the box
  // and the names on the left ran off the edge ("ELO LI…", "AVER"). The half width left after the widest label, the
  // biggest node and the hairline gap is what the outer ring gets, and everything inside it scales with it. Each
  // label is then cut to the room its own node actually has, so nothing is ever drawn outside the viewBox.
  const W = wide ? 1240 : 430, H = wide ? 470 : 320;
  const cx = W / 2, cy = H / 2;
  const PAD = 6, GAP = 5;
  const maxR = wide ? 17 : 12;                 // the cap the node radius below is computed against
  const CHAR_W = 6.9;                          // one uppercase 8.5px Baskerville character plus its .1em of letter-spacing
  const LABEL_ROOM = wide ? 150 : 80;          // what the outermost node on the horizon keeps for its name
  const rings = [[], [], [], []];
  for (const n of nodes) rings[KINDS[n.type]].push(n);
  const rxWant = [0, wide ? 150 : 88, wide ? 300 : 132, wide ? 520 : 178];
  const ryWant = [0, wide ? 74 : 62, wide ? 148 : 94, wide ? 200 : 128];
  const kx = Math.min(1, Math.max(60, cx - PAD - LABEL_ROOM - maxR - GAP) / rxWant[3]);
  const ky = Math.min(1, Math.max(40, cy - PAD - maxR - 8) / ryWant[3]);
  const rx = rxWant.map(v => v * kx);
  const ry = ryWant.map(v => v * ky);
  const at = new Map();
  rings.forEach((ring, i) => {
    ring.forEach((n, k) => {
      const th = (k / Math.max(1, ring.length)) * Math.PI * 2 - Math.PI / 2 + (i * 0.4);
      at.set(n.id, [cx + rx[i] * Math.cos(th), cy + ry[i] * Math.sin(th), th]);
    });
  });

  // ---- the hairlines the data already knows about ----
  const wires = [];
  for (const e of g.edges || []) {
    const a = at.get(e.source), b = at.get(e.target);
    if (!a || !b) continue;
    wires.push(`<path class="wire" d="M ${a[0].toFixed(1)} ${a[1].toFixed(1)} Q ${((a[0] + b[0]) / 2 + (cx - (a[0] + b[0]) / 2) * .35).toFixed(1)} ${((a[1] + b[1]) / 2 + (cy - (a[1] + b[1]) / 2) * .35).toFixed(1)} ${b[0].toFixed(1)} ${b[1].toFixed(1)}" stroke-width="${Math.min(1.6, .5 + (e.n || 1) * .18).toFixed(2)}" opacity="${Math.min(.8, .22 + (e.n || 1) * .07).toFixed(2)}"></path>`);
  }

  let lit = 0;
  const marks = nodes.map(n => {
    const p = at.get(n.id); if (!p) return "";
    const h = heat(n);
    if (h.seen) lit++;
    const r = Math.max(3, Math.min(maxR, 3 + Math.sqrt(n.badge || 0) * (wide ? 2.6 : 1.9)));
    const right = p[0] >= cx;
    const label = String(n.label || "").replace(/\s*\([^)]*\)\s*$/, "");
    // a node on the right half writes to its right, one on the left to its left, and the name is cut to whatever room
    // is left between it and the edge of the box
    const room = right ? (W - PAD) - (p[0] + r + GAP) : (p[0] - r - GAP) - PAD;
    const fits = Math.min(wide ? 26 : 15, Math.floor(room / CHAR_W));
    const show = (wide || r >= 5 || h.seen) && fits >= 4;
    return `<g class="nd${h.seen ? " lit" : ""}${h.fresh ? " today" : ""}" data-href="${esc(href(n))}" tabindex="0">
        <title>${esc(label)}${n.badge ? " · " + esc(api.plural(n.badge, "thing")) + " open" : ""}${h.fresh ? " · moved today" : ""}</title>
        <circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${r.toFixed(1)}"></circle>
        ${show ? `<text x="${(p[0] + (right ? r + GAP : -r - GAP)).toFixed(1)}" y="${(p[1] + 3).toFixed(1)}" text-anchor="${right ? "start" : "end"}">${esc(clipLabel(label, fits))}</text>` : ""}
      </g>`;
  }).join("");

  api.count(api.plural(nodes.length, "place") + (lit ? " · " + lit + " lit" : ""));
  const sun = wide ? 52 : 34;
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="the brain drawn as a constellation">
      <g>${wires.join("")}</g>
      <image href="/static/sun-mark.png" x="${(cx - sun / 2).toFixed(1)}" y="${(cy - sun * 0.39).toFixed(1)}" width="${sun}" preserveAspectRatio="xMidYMid meet"></image>
      ${marks}
    </svg>`;
}

// the words that mean this node, for matching against what the log says moved
function terms(n) {
  const out = new Set();
  const key = String(n.id || "").split(":").slice(1).join(":");
  if (key) out.add(key.toLowerCase());
  const label = String(n.label || "").replace(/\s*\([^)]*\)\s*$/, "").trim().toLowerCase();
  if (label.length >= 4) out.add(label);
  if (n.path) out.add(String(n.path).toLowerCase().replace(/\/$/, ""));
  return Array.from(out).filter(w => w.length >= 4);
}
function href(n) {
  const h = String(n.href || "");
  if (!h) return "/holons";
  return h.charAt(0) === "/" ? h : "/reader?path=" + encodeURIComponent(h);
}
function clipLabel(s, n) {
  s = String(s || "").trim();
  return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
}
})();
