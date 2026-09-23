// Flow: the brain in the middle and everything it is wired to around it, with the data moving on the wires.
// Zak, 2026-09-21: "for the brain I want to see the data moving, how everything is hooked up to the brain and the flow
// chart for it", the pulses "truly live". So the ring is fixed -- these are the eight things this brain exchanges
// anything with -- and the wires are read twice: how much each one carried in the last day, which is its brightness,
// and what is crossing it RIGHT NOW, which is a dot travelling the wire. The live half is an event stream of the
// brain's own log (GET /api/events): every agent writes one line as it works, so a line arriving IS the data moving.
// With no stream, it falls back to asking every five seconds and says nothing about it on the face.
(function () {
const RING = [
  { key: "pfapp", name: "The ProspectForge app", href: "/forge?adapter=ferryman", dir: "both",
    agents: ["ferryman"], words: ["ferryman", "pf-app", "pf app", "prospectforge app", "action item", "/api/v1"] },
  { key: "onboarding", name: "The onboarding API", href: "/status", dir: "in",
    agents: ["onboarding-api-pull"], words: ["onboarding"] },
  { key: "calendar", name: "Google Calendar", href: "/status", dir: "in",
    agents: [], words: ["calendar", "call-prep", "the recap"] },
  { key: "team", name: "Dani's copy of the brain", href: "/people", dir: "out",
    agents: ["team-brain"], words: ["team-brain", "team copy", "zebrain-team", "export"] },
  { key: "agents", name: "The scheduled agents", href: "/agents", dir: "in",
    agents: ["night-agent", "librarian-sweep", "dispatcher", "rounds-bot", "scout-script"],
    words: ["night agent", "librarian", "dispatcher", "scheduled"] },
  { key: "obsidian", name: "Obsidian Sync", href: "/status", dir: "both", agents: [], words: ["obsidian"] },
  { key: "github", name: "GitHub", href: "/status", dir: "both",
    agents: [], words: ["git ", "commit", "rounds", "pushed", "zebrain"] },
  { key: "sessions", name: "Claude Code sessions", href: "/agents", dir: "both",
    agents: ["claude-code", "builder", "opus-worker", "brain-viewer", "brain-tasks", "import-checkup", "call-prep"],
    words: ["session", "sub-agent"] },
];
const OUTWARD = /\b(push|pushed|export|exported|synced|sent|published|upload|uploaded|proposed)\b/i;
const HOT_MS = 60000;                 // how long a wire holds the accent after something crossed it
const PULSE_MS = 1200;

BV.widgets.register({
  id: "flow", contract: 1, title: "Flow", size: "6", defaultOn: true, expand: true,
  fillRows: 26,                             // free mode: the map is drawn to the room it has (520px unless the height is set)
  source: "the eight systems this brain exchanges anything with, how much each wire carried in the last day, and every line the brain writes as it is written (GET /api/moved, GET /api/events)",

  mount(el, api) {
    if (!document.getElementById("bv-flow-css")) {
      const s = document.createElement("style");
      s.id = "bv-flow-css";
      s.textContent = `
        .fl svg { display: block; width: 100%; height: auto; }
        .fl .wire { fill: none; stroke: var(--rule-soft); stroke-width: 1; transition: stroke .4s ease, stroke-width .4s ease; }
        .fl .wire.carried { stroke: var(--accent); stroke-width: 1.4; opacity: .55; }
        .fl .wire.hot { stroke: var(--accent); stroke-width: 2.2; opacity: 1; }
        .fl .halo { fill: none; stroke: var(--rule-soft); stroke-width: 1; }
        .fl .port { fill: var(--rule); transition: fill .4s ease; }
        .fl .port.carried { fill: var(--accent); }
        .fl .port.hot { fill: var(--open); }
        .fl .arrow { fill: var(--rule); }
        .fl .nd { cursor: pointer; }
        .fl .nd circle { fill: var(--surface); stroke: var(--rule); stroke-width: 1; }
        .fl .nd.carried circle { fill: var(--accent); stroke: var(--accent); }
        .fl .nd.hot circle { fill: var(--open); stroke: var(--open); }
        .fl .nd text { font-family: var(--font-ui); font-size: 8.5px; letter-spacing: .08em; text-transform: uppercase;
                       fill: var(--muted); pointer-events: none; }
        .fl .nd.carried text { fill: var(--ink-soft); }
        .fl .nd:hover text { fill: var(--accent); }
        .fl .pulse { fill: var(--open); }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="fl" data-fl></div>`;
    el._hot = el._hot || new Map();          // node id -> when something last crossed its wire
    el._last = el._last || new Map();        // node id -> the last line that crossed it, for the hover
    el.addEventListener("click", e => {
      const g = e.target.closest("[data-href]"); if (!g) return;
      window.location.href = g.dataset.href;
    });
    wire(el, api);
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const since = new Date(Date.now() - 86400000);
    const iso = `${since.getFullYear()}-${String(since.getMonth() + 1).padStart(2, "0")}-${String(since.getDate()).padStart(2, "0")}T${String(since.getHours()).padStart(2, "0")}:${String(since.getMinutes()).padStart(2, "0")}`;
    let j;
    try { j = await api.get("/api/moved?limit=200&since=" + encodeURIComponent(iso)); } catch (e) { return api.fail(e); }
    const carried = new Map();
    for (const r of (j.items || [])) {
      const id = route(r); if (!id) continue;
      carried.set(id, (carried.get(id) || 0) + 1);
      if (!el._last.has(id)) el._last.set(id, r);        // newest first, so the first one seen is the newest
    }
    el._carried = carried;
    el._newest = (j.items || [])[0] ? (j.items || [])[0].at : el._newest;
    draw(el, api);
  },
  resize(el, api) { draw(el, api); },
});

// ---- which wire a line belongs to ----
function route(ev) {
  const agent = String(ev.agent || "").toLowerCase();
  for (const n of RING) if ((n.agents || []).indexOf(agent) >= 0) return n.key;
  const hay = (String(ev.agent || "") + " " + String(ev.action || "") + " " + String(ev.text || "")).toLowerCase();
  for (const n of RING) if ((n.words || []).some(w => hay.indexOf(w) >= 0)) return n.key;
  return null;
}
const outward = ev => OUTWARD.test(String(ev.action || "") + " " + String(ev.text || ""));

// ---- the drawing ----
function draw(el, api) {
  const box = el.querySelector("[data-fl]"); if (!box) return;
  const esc = api.esc, wide = api.expanded;
  const W = wide ? 1240 : 430, H = wide ? 470 : 320;
  const cx = W / 2, cy = H / 2;
  const CHAR = 5.9, PAD = 8;
  // 2026-09-21, Zak on the sun: "this guy looks weird since all of the lines are intersecting with it." So the wires
  // stop on a halo around it and meet that ring like spokes meeting a hub; nothing crosses the mark itself.
  const HALO = wide ? 40 : 26;
  const labelRoom = wide ? 170 : 104;
  const rx = Math.max(HALO + 40, cx - PAD - labelRoom - 14);
  const ry = Math.max(HALO + 30, cy - PAD - 30);
  const carried = el._carried || new Map();
  const wires = [], ports = [], marks = [];
  el._at = new Map();
  RING.forEach((n, i) => {
    const th = (i / RING.length) * Math.PI * 2 - Math.PI / 2;
    const x = cx + rx * Math.cos(th), y = cy + ry * Math.sin(th);
    const a = Math.atan2(y - cy, x - cx);                  // the node's own angle, which the ellipse bends off th
    const hx = cx + HALO * Math.cos(a), hy = cy + HALO * Math.sin(a);
    const d = path(x, y, hx, hy, cx, cy);
    el._at.set(n.key, { x, y, d });
    const got = carried.get(n.key) || 0;
    wires.push(`<path class="wire${got ? " carried" : ""}" data-wire="${esc(n.key)}" d="${d}"></path>`);
    ports.push(`<circle class="port${got ? " carried" : ""}" data-port="${esc(n.key)}" cx="${hx.toFixed(1)}" cy="${hy.toFixed(1)}" r="${wide ? 3 : 2.4}"></circle>`);
    // the arrow sits where the data arrives: on the ring for what comes in, at the node for what goes out
    if (n.dir !== "both") wires.push(arrow(a, cx, cy, x, y, HALO, n.dir === "out", wide ? 8 : 6));
    const right = x >= cx;
    const room = right ? (W - PAD) - (x + 12) : (x - 12) - PAD;
    const per = Math.max(6, Math.floor(room / CHAR));
    const lines = wrapName(n.name, per, 2);
    const tx = x + (right ? 12 : -12), ty = y + 3 - (lines.length - 1) * 5;
    const last = el._last.get(n.key);
    marks.push(`<g class="nd${got ? " carried" : ""}" data-node="${esc(n.key)}" data-href="${esc(n.href)}" tabindex="0">
        <title>${esc(n.name)}${last ? " · " + esc(api.clip(say(last), 90)) : " · nothing lately"}</title>
        <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${wide ? 8 : 6}"></circle>
        <text x="${tx.toFixed(1)}" y="${ty.toFixed(1)}" text-anchor="${right ? "start" : "end"}">${lines.map((l, k) =>
          `<tspan x="${tx.toFixed(1)}"${k ? ` dy="10"` : ""}>${esc(l)}</tspan>`).join("")}</text>
      </g>`);
  });
  const sun = wide ? 64 : 42;
  api.count(carried.size ? api.plural(carried.size, "wire") + " carried something" : "quiet");
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="the brain and what it is wired to" data-svg>
      <g data-wires>${wires.join("")}</g>
      <circle class="halo" cx="${cx}" cy="${cy}" r="${HALO}"></circle>
      <image href="/static/sun-mark.png" x="${(cx - sun / 2).toFixed(1)}" y="${(cy - sun * 0.39).toFixed(1)}" width="${sun}" preserveAspectRatio="xMidYMid meet"><title>the brain</title></image>
      <g data-ports>${ports.join("")}</g>
      <g data-marks>${marks.join("")}</g>
      <g data-pulses></g>
    </svg>`;
  for (const [id, at] of el._hot) if (Date.now() - at < HOT_MS) hot(el, id, false);
}
// the node to its port on the ring, bowed a little so eight wires do not read as a star
function path(x, y, hx, hy, cx, cy) {
  const mx = (x + hx) / 2, my = (y + hy) / 2;
  const bx = mx + (cy - y) * 0.08, by = my + (x - cx) * 0.08;
  return `M ${x.toFixed(1)} ${y.toFixed(1)} Q ${bx.toFixed(1)} ${by.toFixed(1)} ${hx.toFixed(1)} ${hy.toFixed(1)}`;
}
function arrow(a, cx, cy, x, y, halo, out, nodeR) {
  const ux = Math.cos(a), uy = Math.sin(a);
  const px = out ? x - ux * (nodeR + 9) : cx + ux * (halo + 9);
  const py = out ? y - uy * (nodeR + 9) : cy + uy * (halo + 9);
  const ang = (out ? a : a + Math.PI) * 180 / Math.PI;
  return `<path class="arrow" d="M 0 -3 L 6 0 L 0 3 Z" transform="translate(${px.toFixed(1)} ${py.toFixed(1)}) rotate(${ang.toFixed(1)})"></path>`;
}
// a name reads in full: it breaks over two short lines rather than losing its end, and only a name too long for both
// is cut, with the whole of it on hover
function wrapName(name, per, maxLines) {
  const words = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [""];
  const lines = [];
  for (const w of words) {
    const last = lines.length ? lines[lines.length - 1] : null;
    if (last && (last + " " + w).length <= per) lines[lines.length - 1] = last + " " + w;
    else lines.push(w);
  }
  if (lines.length <= maxLines) return lines;
  const head = lines.slice(0, maxLines - 1);
  head.push(clip(lines.slice(maxLines - 1).join(" "), Math.floor(per * 1.4)));
  return head;
}
const clip = (s, n) => { s = String(s || "").trim(); return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s; };
function say(r) {
  let t = String(r.text || "");
  t = t.replace(/^[a-z0-9._\-/]+\.(md|json|py|js|canvas|txt)\s+--\s+/i, "");
  t = t.replace(/\b[QT]-\d{4}\b\s*/g, "");
  return t.replace(/\s+/g, " ").trim() || String(r.action || "").toLowerCase();
}

// ---- something crossed a wire ----
function hot(el, id, pulseIt, out) {
  const box = el.querySelector("[data-fl]"); if (!box) return;
  const w = box.querySelector(`[data-wire="${id}"]`), n = box.querySelector(`[data-node="${id}"]`);
  const p = box.querySelector(`[data-port="${id}"]`);
  if (w) w.classList.add("hot");
  if (n) n.classList.add("hot");
  if (p) p.classList.add("hot");
  clearTimeout((el._cool = el._cool || {})[id]);
  el._cool[id] = setTimeout(() => {
    if (w) w.classList.remove("hot");
    if (n) n.classList.remove("hot");
    if (p) p.classList.remove("hot");
  }, HOT_MS);
  if (!pulseIt) return;
  const at = (el._at || new Map()).get(id); if (!at) return;
  const holder = box.querySelector("[data-pulses]"); if (!holder) return;
  const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  dot.setAttribute("class", "pulse");
  dot.setAttribute("r", "4");
  const move = document.createElementNS("http://www.w3.org/2000/svg", "animateMotion");
  move.setAttribute("dur", (PULSE_MS / 1000) + "s");
  move.setAttribute("path", at.d);
  move.setAttribute("fill", "freeze");
  if (out) { move.setAttribute("keyPoints", "1;0"); move.setAttribute("keyTimes", "0;1"); move.setAttribute("calcMode", "linear"); }
  dot.appendChild(move);
  holder.appendChild(dot);
  if (move.beginElement) { try { move.beginElement(); } catch (e) {} }
  setTimeout(() => dot.remove(), PULSE_MS + 120);
}
function arrived(el, api, ev) {
  const id = route(ev); if (!id) return;
  el._hot.set(id, Date.now());
  el._last.set(id, { at: ev.ts || ev.at, agent: ev.agent, action: ev.action, text: ev.text });
  if (!(el._carried instanceof Map)) el._carried = new Map();
  if (!el._carried.get(id)) { el._carried.set(id, 1); draw(el, api); }
  hot(el, id, true, outward(ev));
}

// ---- the live wire, with a plain fallback ----
function wire(el, api) {
  try { if (el._es) el._es.close(); } catch (e) {}
  clearInterval(el._poll);
  if (typeof EventSource !== "function") return poll(el, api);
  let es;
  try { es = new EventSource("/api/events"); } catch (e) { return poll(el, api); }
  el._es = es;
  es.onmessage = m => {
    // switched off the board, the section is out of the page: close the stream rather than pulse into nothing
    if (!el.isConnected) { try { es.close(); } catch (e) {} clearInterval(el._poll); return; }
    let ev = null;
    try { ev = JSON.parse(m.data); } catch (e) { return; }
    if (ev) arrived(el, api, ev);
  };
  es.onerror = () => {
    // the stream ends itself every hour and the browser reconnects on its own; only a stream that is CLOSED is gone
    if (es.readyState === 2) { try { es.close(); } catch (e) {} if (el._es === es) poll(el, api); }
  };
}
function poll(el, api) {
  clearInterval(el._poll);
  el._poll = setInterval(async () => {
    if (document.hidden) return;
    let j;
    // its own read, not the board's shared one: that one is held for a few seconds and this asks more often than that
    try { j = await (await fetch("/api/moved?limit=20")).json(); } catch (e) { return; }
    const rows = (j.items || []).filter(r => !el._newest || r.at > el._newest).reverse();
    if (rows.length) el._newest = (j.items || [])[0].at;
    for (const r of rows) arrived(el, api, r);
  }, 5000);
}
})();
