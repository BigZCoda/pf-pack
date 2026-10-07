// People: who the brain is holding, in one of two forms you pick in its head and the board remembers.
// 2026-09-21: the owner rejected the ring this replaced because it did not say what it was showing. So the
// ring is gone and the people are drawn in relation to the brain instead of arranged around it decoratively.
//   graph -- the map page's own bubbles, in a widget. Everyone on the calendar this week and everyone the ledgers still
//            name on something open, tied to the mark in the middle by a line as heavy as what ties them to it, and to
//            each other where they share a call. Drag a bubble and the physics answers, drag the ground to pan, wheel
//            to zoom. The physics is /static/graph-physics.js, which IS the map's, lifted out so there is one engine.
//   list  -- the same people as a roll of names that drifts upward on its own and stops under the pointer.
// The mark in the middle is the sun. The graph settles and stops (correction #80, 9/09: "have physics" means a layout
// that comes to rest), fills the tile, and fits its camera so every bubble and name is inside it.
(function () {
const HOT_HOURS = 48;               // a call this close puts a person in the accent
const MAX = 24;                     // how many people either form will carry
const ROLL_PX = 17;                 // how fast the roll of names drifts, in pixels a second
// The names this board never draws, from any source, silently: a setting, viewer/settings.json `people_hidden`, a list
// of patterns matched on the start of a name, case-insensitive (read in refresh). Empty draws everyone.
let SKIP = /(?!)/;
const hiddenRe = list => {
  const src = (Array.isArray(list) ? list : []).map(x => String(x || "").trim()).filter(Boolean)
    .filter(x => { try { new RegExp(x); return true; } catch (e) { return false; } });
  return src.length ? new RegExp("^(?:" + src.join("|") + ")", "i") : /(?!)/;
};
const FORMS = [["graph", "the people in relation to the brain, with the physics"], ["list", "the same people as a roll of names"]];
const LABEL_PX = 10.5;              // a name's size on screen, whatever the zoom
const NARROW = 560;                 // under this width a name is drawn as first name and last initial
const FIT_MARGIN = 14;              // screen pixels kept clear round the drawing when the camera fits it
const C = {}, FONT = {};

BV.widgets.register({
  id: "people", contract: 1, title: "People", size: "4", defaultOn: true, expand: true,
  fillRows: 18,                             // free mode: the drawing fills the room it is given (360px unless the height is set)
  source: "everyone on your calendar this week and everyone the open items name, how many calls and items tie each of them to the brain, and the prep for their next call (GET /api/calendar/week, GET /api/calls, GET /api/projects, GET /api/people)",
  // T-0214: the rules a person can put on it in edit mode. max is how many people it carries; a project keeps only
  // the people that project's open items name, their calls still weighing them.
  filters: [
    { key: "max", label: "how many", kind: "range", min: 4, max: MAX, step: 1, default: MAX },
    { key: "project", label: "project", kind: "pick", options: "projects", any: "every project" },
  ],

  mount(el, api) {
    styleOnce();
    el.innerHTML = `<div class="pp" data-pp></div>`;
    api.card.addEventListener("click", e => {
      const f = e.target.closest("[data-form]");
      if (f) { api.setSettings({ form: f.dataset.form }); paintHead(api); el._built = false; draw(el, api); return; }
    });
    el.addEventListener("click", e => {
      const a = e.target.closest("[data-href]"); if (!a) return;
      window.location.href = a.dataset.href;
    });
    paintHead(api);
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const soft = p => api.get(p).then(j => j, () => null);
    const [week, calls, projects, cards, pr] = await Promise.all(
      [soft("/api/calendar/week"), soft("/api/calls"), soft("/api/projects"), soft("/api/people"), BV.prefs ? BV.prefs() : {}]);
    SKIP = hiddenRe((pr || {}).people_hidden);
    el._src = { week, calls, projects, cards };
    el._rows = roster(el._src, api.settings());
    draw(el, api);
  },
  // a new size, an opened-out tile, a freehand drag: the drawing takes the tile's height and the camera fits again
  resize(el, api) { el._userMoved = false; draw(el, api); },
});

// ---- the head: which form ----
const form = api => (FORMS.some(f => f[0] === api.settings().form) ? api.settings().form : "graph");
function paintHead(api) {
  const f = form(api);
  const tab = (k, t, on) => `<button class="wtab${on ? " on" : ""}" type="button" data-form="${k}" title="${BV.esc(t)}">${k}</button>`;
  api.head(FORMS.map(([k, t]) => tab(k, t, k === f)).join(""));
}

// ---- who is in it ----
// The calendar and the ledgers are two different claims on a person and both count. A person is keyed on their card
// when either side resolved one, so "Sam Rivera" on a call and `sam-rivera` on a task are one bubble, not two.
function events(src) {
  const week = src.week || {}, calls = src.calls || {};
  const today = dayKey(new Date());
  const now = (calls.exists && !calls.stale ? (calls.events || []) : []).map(e => Object.assign({ date: today }, e));
  const rest = (week.events || []).filter(e => e.date !== today || !now.length);
  return now.concat(rest).sort((a, b) => String(a.start).localeCompare(String(b.start)));
}
function roster(src, opt) {
  opt = opt || {};
  const only = String(opt.project || ""), cap = Math.max(1, Math.min(MAX, parseInt(opt.max, 10) || MAX));
  const nameBySlug = new Map();
  for (const c of ((src.cards || {}).people || [])) nameBySlug.set(c.slug, tidy(c.name));
  const by = new Map(), now = Date.now();
  const find = (slug, name) => {
    const k = slug ? "card:" + slug : "name:" + String(name).toLowerCase().replace(/\s+/g, " ");
    let r = by.get(k);
    if (!r) { r = { key: k, name: (slug && nameBySlug.get(slug)) || tidy(name), slug: slug || null, calls: 0, items: 0, next: null, last: null, with: new Set() }; by.set(k, r); }
    if (slug && !r.slug) r.slug = slug;
    return r;
  };
  for (const e of events(src)) {
    const at = new Date(e.start).getTime(), here = [];
    const people = (e.people && e.people.length ? e.people : (e.attendees || []).map(a => ({ name: a.name || a })));
    for (const p of people) {
      const name = String((p && p.name) || p || "").trim();
      if (!name || p.self || SKIP.test(name) || isMe(name)) continue;
      const r = find(p.slug || null, name);
      r.calls++;
      if (!isNaN(at)) {
        if (at >= now) { if (!r.next || at < new Date(r.next.start).getTime()) r.next = e; }
        else if (!r.last || at > new Date(r.last.start).getTime()) r.last = e;
      }
      here.push(r);
    }
    for (let i = 0; i < here.length; i++)
      for (let j = i + 1; j < here.length; j++) { here[i].with.add(here[j].key); here[j].with.add(here[i].key); }
  }
  const today = (src.projects || {}).today || dayKey(new Date());
  for (const p of ((src.projects || {}).projects || [])) {
    if (!p.exists || (only && p.id !== only)) continue;
    for (const g of p.groups || []) for (const it of g.items || []) {
      if (!isOpen(it, today)) continue;
      for (const slug of it.people || []) {
        const name = nameBySlug.get(slug) || words(slug);
        if (SKIP.test(name)) continue;
        find(slug, name).items++;
      }
    }
  }
  const out = Array.from(by.values()).filter(r => only ? r.items : (r.calls || r.items));
  for (const r of out) {
    r.weight = r.calls + r.items;
    r.hot = !!(r.next && new Date(r.next.start).getTime() - Date.now() <= HOT_HOURS * 3600000);
    r.href = hrefOf(r);
  }
  out.sort((a, b) => b.weight - a.weight || a.name.localeCompare(b.name));
  return out.slice(0, cap);
}
// an item still open: a task nobody has closed, a question nobody has answered, and not one parked until a later day
function isOpen(it, today) {
  if (it.until && it.until > today) return false;
  if (it.kind === "task") return it.mark === " " || it.mark === "-";
  if (it.kind === "question") return it.mark === "?";
  return false;
}
function hrefOf(r) {
  const prep = ((r.next || r.last || {}).preps || [])[0];
  if (prep) return "/reader?path=" + encodeURIComponent(prep.path);
  return r.slug ? "/people?open=" + encodeURIComponent(r.slug) : "/people";
}
function isMe(name) {
  const me = String(BV.owner || "@me").replace(/^@/, "").toLowerCase(), low = name.toLowerCase();
  return low === me || low.split(/\s+/)[0] === me;
}
const tidy = s => String(s || "").split("·")[0].replace(/["“”]/g, "").replace(/\s+/g, " ").trim();
const words = slug => String(slug || "").split("-").filter(Boolean).map(w => w[0].toUpperCase() + w.slice(1)).join(" ");
const dayKey = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
function when(e) {
  const d = new Date(e.start);
  if (isNaN(d)) return String(e.date || "");
  const t = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).toLowerCase().replace(" ", "");
  const day = e.date === dayKey(new Date()) ? "today" : d.toLocaleDateString(undefined, { weekday: "long" });
  return day + " " + t;
}
function sayWhen(r) {
  if (r.next) return "next " + when(r.next);
  if (r.last) return "last spoke " + when(r.last);
  return "no call on the week";
}
const sayOpen = r => (r.items ? (r.items === 1 ? "one open item" : r.items + " open items") : "nothing open");

// ---- drawing ----
function draw(el, api) {
  const rows = el._rows || [];
  const soon = rows.filter(r => r.hot).length;
  api.count(rows.length
    ? (rows.length === 1 ? "one person" : rows.length + " people") + (soon ? " · " + soon + " within two days" : "")
    : ((el._src || {}).week || {}).exists ? "nobody yet" : "no calendar");
  const box = el.querySelector("[data-pp]"); if (!box) return;
  if (!rows.length) {
    stopGraph(el); stopRoll(el);
    box.innerHTML = `<p class="pnone">${BV.esc(((el._src || {}).week || {}).exists
      ? "Nobody on the calendar this week, and nothing open naming anyone."
      : "No calendar has been written. The next session start writes it.")}</p>`;
    el._built = false;
    return;
  }
  if (form(api) === "list") { stopGraph(el); return roll(el, api, rows); }
  stopRoll(el);
  bubbles(el, api, rows).catch(e => { el._built = false; api.fail(e); });
}

// ---- (a) the bubbles ----
// The map's renderer, the map's forces, the map's gestures. What is this widget's own is the graph it hands them: the
// mark in the middle held still, a person tied to it by everything that ties them to it, and a thread between two
// people who sit on the same call.
let LOADING = null;
function physics() {
  if (window.BV && BV.graph) return BV.graph.ready().then(() => BV.graph);
  if (!LOADING) LOADING = new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = "/static/graph-physics.js";
    s.onload = () => (window.BV && BV.graph ? res() : rej(new Error("the bubbles did not load")));
    s.onerror = () => { LOADING = null; rej(new Error("the bubbles did not load")); };
    document.head.appendChild(s);
  });
  return LOADING.then(() => BV.graph.ready()).then(() => BV.graph);
}
function readTokens() {
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  for (const [k, v] of Object.entries({ bg: "--bg", surface: "--surface", ink: "--ink", inkSoft: "--ink-soft", muted: "--muted",
                                        rule: "--rule", ruleSoft: "--rule-soft", accent: "--accent", open: "--open" })) C[k] = css(v);
  FONT.display = css("--font-display") || "Georgia, serif";
  FONT.ui = css("--font-ui") || FONT.display;
  FONT.mono = css("--font-mono") || "monospace";
}
const radius = n => (n.hub ? 13 : 5.5 + Math.min(9, Math.sqrt(n.weight || 1) * 3.4));

async function bubbles(el, api, rows) {
  const box = el.querySelector("[data-pp]"); if (!box) return;
  const P = await physics();
  const FG = window.ForceGraph;
  if (!el._built || !el._host || !el._host.isConnected) {
    readTokens();
    box.innerHTML = `<div class="ppg" data-g></div>`;
    const host = box.querySelector("[data-g]");
    const height = tileHeight(el, api, host);
    host.style.height = height + "px";
    stopGraph(el);
    const held = n => n === el._held;
    el._rest = false; el._in = false; el._userMoved = false; el._hover = null; el._sig = "";
    const g = FG()(host)
      .width(host.clientWidth || 300).height(height)
      .backgroundColor(C.bg)
      .nodeId("id")
      .nodeCanvasObjectMode(() => "replace").nodeCanvasObject(paintNode).nodePointerAreaPaint(paintArea)
      .nodeLabel(hoverText)
      .linkColor(l => (l.kind === "shared" ? P.rgba(C.rule, 0.4) : P.rgba(C.accent, 0.22 + Math.min(0.45, l.w * 0.09))))
      .linkWidth(l => (l.kind === "shared" ? 0.7 : Math.min(2.6, 0.8 + l.w * 0.35)))
      .linkLineDash(l => (l.kind === "shared" ? [4, 4] : null))
      .minZoom(0.3).maxZoom(5)
      // it settles: alpha falls from 1 to a 0.002 floor in about 170 ticks, 150 of them run before the first frame,
      // so what is seen is a third of a second of easing and then a still drawing. force-graph's own floor is 0, which
      // never stops, so the floor is set here; four seconds is the hard stop whatever happens.
      .d3AlphaDecay(0.036).d3AlphaMin(0.002).d3VelocityDecay(0.62).cooldownTime(4000).warmupTicks(150)
      // the names are drawn after the bubbles, in one pass that can see them all and keep any two from overlapping
      .onRenderFramePost((ctx, scale) => paintLabels(el, ctx, scale))
      .onEngineTick(() => {
        // switched off the board, or re-drawn, the section is out of the page: a graph nobody can see stops itself
        if (!host.isConnected) { try { g._destructor(); } catch (e) {} return; }
        if (!el._ticked) { el._ticked = true; fitView(el, 0); }
      })
      .onEngineStop(() => {
        el._rest = true;
        if (!el._userMoved) fitView(el, 350); else sleepSoon(el, 60);
      })
      // only a pan or a wheel by the person counts as moving the view; the library's own zooms and the fit do not
      .onZoom(() => { if (el._down && !el._fitting && !el._held) el._userMoved = true; })
      .onNodeHover(n => { el._hover = n || null; host.style.cursor = n ? "pointer" : "grab"; })
      .onNodeClick(n => { if (n.href) window.location.href = n.href; })
      .onNodeDrag(n => { el._held = n; el._rest = false; })
      .onNodeDragEnd(n => {
        el._held = null;
        if (n.hub) { n.fx = 0; n.fy = 0; n.x = 0; n.y = 0; n.vx = n.vy = 0; }   // the middle is the middle
        else { n.fx = n.fy = undefined; }                                        // everything else goes back into the physics
      });
    g.d3Force("center", null);
    g.d3Force("charge").strength(n => (n.hub ? -240 : -110)).distanceMax(460);
    g.d3Force("link").distance(l => (l.kind === "shared" ? 74 : 104 - Math.min(34, l.w * 6))).strength(l => (l.kind === "shared" ? 0.07 : 0.22));
    g.d3Force("gravity", P.gravity(0.004, { skip: held }));
    // a bubble keeps clear the width of its own name, so the names have somewhere to go
    g.d3Force("collide", P.collide(0.35, { radius: n => Math.max(radius(n) + 8, (n.lh || 0) * 1.2), pad: () => 5, skip: held }));
    // no breathe force here: this instrument comes to rest (the map keeps its drift)
    // while the pointer is on the drawing it draws every frame, so a hovered name appears at once; off it, and at
    // rest, the frame loop is paused outright and the drawing costs nothing
    host.addEventListener("pointerenter", () => { el._in = true; wake(el); });
    host.addEventListener("pointerleave", () => { el._in = false; el._hover = null; sleepSoon(el, 80); });
    host.addEventListener("pointerdown", () => { el._down = true; });
    for (const ev of ["pointerup", "pointercancel", "pointerleave"]) host.addEventListener(ev, () => { el._down = false; });
    host.addEventListener("wheel", () => { el._userMoved = true; }, { passive: true });
    el._fg = g; el._host = host; el._built = true; el._nodes = new Map();
  }
  const g = el._fg, host = el._host;
  const height = tileHeight(el, api, host);
  host.style.height = height + "px";
  const width = host.clientWidth || 300;
  const resized = g.width() !== width || g.height() !== height;
  if (resized) g.width(width).height(height);
  const narrow = width < NARROW, data = model(el, rows), sig = signature(rows) + (narrow ? "|narrow" : "|wide");
  for (const n of data.nodes) n.lh = labelHalf(n, narrow);
  if (sig !== el._sig) {             // new people or new ties: run the physics again from where everyone stands
    el._sig = sig; el._rest = false; el._ticked = false;
    wake(el);
    g.graphData(data);
  } else if (resized || !el._userMoved) {
    fitView(el, 0);                  // the same people in a new box: no physics, just the camera
  }
}
// the drawing is as tall as the tile's body when the tile has a height of its own (free mode, a set row span), and a
// sensible fixed height when the body only grows to fit what is in it. Measured with the drawing out of the flow.
function tileHeight(el, api, host) {
  const fallback = api.expanded ? 460 : 268;
  const was = host.style.display;
  host.style.display = "none";
  const cs = getComputedStyle(el);
  const inner = el.clientHeight - (parseFloat(cs.paddingTop) || 0) - (parseFloat(cs.paddingBottom) || 0);
  host.style.display = was;
  if (!(inner > 24)) return fallback;
  return Math.max(120, Math.floor(inner) - 2);
}
const signature = rows => rows.map(r => `${r.key}:${r.weight}:${r.hot ? 1 : 0}:${Array.from(r.with).sort().join(",")}`).join("|");

// ---- the frame loop: running while the physics moves or the pointer is on it, paused otherwise ----
function wake(el) {
  const g = el._fg; if (!g) return;
  clearTimeout(el._sleep);
  try { g.autoPauseRedraw(false); g.resumeAnimation(); } catch (e) {}
}
function sleepSoon(el, ms) {
  const g = el._fg; if (!g) return;
  clearTimeout(el._sleep);
  el._sleep = setTimeout(() => {
    if (el._in || !el._rest || el._fg !== g) return;
    try { g.autoPauseRedraw(true); g.pauseAnimation(); } catch (e) {}
  }, ms);
}

// ---- the camera: every bubble and every name inside the canvas, with a margin ----
// The names are a fixed size on screen while the bubbles scale with the zoom, so the fit solves for the zoom where the
// widest reach (bubble or name, whichever is further out) of every node fits the box, by halving, then centres it.
function fitView(el, ms) {
  const g = el._fg; if (!g) return;
  const nodes = (g.graphData().nodes || []).filter(n => Number.isFinite(n.x) && Number.isFinite(n.y));
  if (!nodes.length) return;
  const w = g.width(), h = g.height(), m = FIT_MARGIN, narrow = w < NARROW;
  const ctx = measureCtx();
  ctx.font = `${LABEL_PX}px ${FONT.ui}`;
  const lw = new Map(nodes.map(n => [n, n.hub ? 0 : ctx.measureText(labelText(n, narrow)).width / 2]));
  const span = k => {
    let l = Infinity, r = -Infinity, t = Infinity, b = -Infinity;
    for (const n of nodes) {
      const rr = radius(n) * k, half = Math.max(rr, lw.get(n)), below = n.hub ? rr : rr + 4 + LABEL_PX + 3;
      l = Math.min(l, n.x * k - half); r = Math.max(r, n.x * k + half);
      t = Math.min(t, n.y * k - rr); b = Math.max(b, n.y * k + below);
    }
    return { l, r, t, b };
  };
  const fits = k => { const s = span(k); return s.r - s.l <= w - 2 * m && s.b - s.t <= h - 2 * m; };
  let lo = 0.3, hi = 2.2;
  if (fits(hi)) lo = hi;
  else for (let i = 0; i < 28; i++) { const mid = (lo + hi) / 2; if (fits(mid)) lo = mid; else hi = mid; }
  const k1 = lo, s = span(k1);
  const c1 = { x: (s.l + s.r) / 2 / k1, y: (s.t + s.b) / 2 / k1 };
  wake(el);
  clearTimeout(el._fitTimer);
  const k0 = g.zoom(), c0 = g.centerAt(), t0 = performance.now(), ease = t => 1 - Math.pow(1 - t, 3);
  const step = () => {               // timers, the way the map page fits: the first step lands at once, the last always lands
    const t = ms ? Math.min(1, (performance.now() - t0) / ms) : 1, e = ease(t);
    el._fitting = true;
    try { g.centerAt(c0.x + (c1.x - c0.x) * e, c0.y + (c1.y - c0.y) * e, 0); g.zoom(k0 + (k1 - k0) * e, 0); }
    finally { el._fitting = false; }
    if (t < 1) el._fitTimer = setTimeout(step, 16);
    else if (el._rest) sleepSoon(el, 120);
  };
  step();
}
let MEASURE = null;
const measureCtx = () => (MEASURE || (MEASURE = document.createElement("canvas").getContext("2d")));

// ---- the names ----
// Ported from the map page: a name is shortened, and one that would sit on a neighbour's name or bubble is not drawn.
// The hovered person is placed first and always in full, then the people with a call inside two days, then by weight.
function labelText(n, narrow) {
  // a card name can carry a bracket ("Sam Rivera (Samuel)", "Ana (the agency)"): the label drops it
  const name = String(n.name || "").replace(/\s*\([^)]*\)/g, " ").replace(/\s+/g, " ").trim() || String(n.name || "");
  const parts = name.split(" ").filter(Boolean);
  const initial = parts.length > 1 ? (parts[parts.length - 1].match(/[A-Za-z]/) || [""])[0].toUpperCase() : "";
  if (narrow && initial) return parts[0] + " " + initial + ".";
  return name.length > 22 ? name.slice(0, 21).trimEnd() + "…" : name;
}
// half a label's width in graph units at zoom 1, which the collide force keeps clear so the names have room
function labelHalf(n, narrow) {
  if (n.hub) return 0;
  const ctx = measureCtx();
  ctx.font = `${LABEL_PX}px ${FONT.ui}`;
  return ctx.measureText(labelText(n, narrow)).width / 2;
}
function paintLabels(el, ctx, scale) {
  const g = el._fg; if (!g) return;
  const px = 1 / scale, narrow = g.width() < NARROW, hover = el._hover;
  const nodes = (g.graphData().nodes || []).filter(n => Number.isFinite(n.x));
  const obstacles = nodes.map(n => { const r = radius(n); return { n, x0: n.x - r, x1: n.x + r, y0: n.y - r, y1: n.y + r }; });
  const order = nodes.filter(n => !n.hub).sort((a, b) =>
    (b === hover) - (a === hover) || (b.hot ? 1 : 0) - (a.hot ? 1 : 0) || (b.weight || 0) - (a.weight || 0)
    || String(a.name).localeCompare(String(b.name)));
  ctx.save();
  ctx.font = `${LABEL_PX * px}px ${FONT.ui}`;
  ctx.textAlign = "center"; ctx.textBaseline = "top";
  const placed = [], gap = 2 * px;
  const tl = g.screen2GraphCoords(0, 0), br = g.screen2GraphCoords(g.width(), g.height());
  const view = { x0: tl.x, y0: tl.y, x1: br.x, y1: br.y };      // a name is only placed where it can be seen whole
  const hit = (a, b) => a.x0 < b.x1 + gap && a.x1 + gap > b.x0 && a.y0 < b.y1 + gap && a.y1 + gap > b.y0;
  for (const n of order) {
    const text = n === hover ? String(n.name || "") : labelText(n, narrow);
    // below the bubble first, then above it, then to its right and its left; a name with no free place is not drawn
    const half = ctx.measureText(text).width / 2, r = radius(n), lh = (LABEL_PX + 1) * px, off = 4 * px;
    const spots = [[n.x, n.y + r + off], [n.x, n.y - r - off - lh], [n.x + r + off + half, n.y - lh / 2], [n.x - r - off - half, n.y - lh / 2]];
    let at = null;
    for (const [cx, top] of (n === hover ? spots.slice(0, 1) : spots)) {
      const box = { x0: cx - half, x1: cx + half, y0: top, y1: top + lh };
      const inside = box.x0 >= view.x0 && box.x1 <= view.x1 && box.y0 >= view.y0 && box.y1 <= view.y1;
      if (n === hover || inside && !(placed.some(p => hit(box, p)) || obstacles.some(o => o.n !== n && hit(box, o)))) { at = [cx, top, box]; break; }
    }
    if (!at) continue;
    placed.push(at[2]);
    ctx.lineWidth = 3 * px; ctx.strokeStyle = C.bg; ctx.lineJoin = "round";
    ctx.strokeText(text, at[0], at[1]);
    ctx.fillStyle = n.hot ? C.accent : n === hover ? C.ink : C.inkSoft || C.muted;
    ctx.fillText(text, at[0], at[1]);
  }
  ctx.restore();
}
// one node object per person, kept across refreshes so the physics does not start over every minute
function model(el, rows) {
  const keep = el._nodes instanceof Map ? el._nodes : (el._nodes = new Map());
  const seen = new Set(["the brain"]);
  let mark = keep.get("the brain");
  if (!mark) { mark = { id: "the brain", hub: true, x: 0, y: 0, vx: 0, vy: 0 }; keep.set("the brain", mark); }
  mark.fx = 0; mark.fy = 0;
  mark.href = "/people";
  const nodes = [mark], links = [];
  rows.forEach((r, i) => {
    let n = keep.get(r.key);
    if (!n) {
      const a = (i / Math.max(1, rows.length)) * Math.PI * 2 - Math.PI / 2, d = 70 + Math.random() * 40;
      n = { id: r.key, x: Math.cos(a) * d, y: Math.sin(a) * d, vx: 0, vy: 0 };
      keep.set(r.key, n);
    }
    Object.assign(n, { name: r.name, slug: r.slug, calls: r.calls, items: r.items, weight: r.weight, hot: r.hot,
                       href: r.href, said: sayWhen(r), open: sayOpen(r) });
    nodes.push(n); seen.add(r.key);
    links.push({ source: "the brain", target: r.key, kind: "ties", w: r.weight });
  });
  const done = new Set();
  for (const r of rows) for (const other of r.with) {
    if (!seen.has(other)) continue;
    const pair = [r.key, other].sort().join("|");
    if (done.has(pair)) continue;
    done.add(pair);
    links.push({ source: r.key, target: other, kind: "shared", w: 1 });
  }
  for (const id of Array.from(keep.keys())) if (!seen.has(id)) keep.delete(id);
  return { nodes, links };
}
function paintNode(n, ctx, scale) {
  const px = 1 / scale;
  ctx.save();
  if (n.hub) { paintHubMark(n, ctx, px); ctx.restore(); return; }
  const r = radius(n);
  ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
  ctx.fillStyle = n.hot ? C.accent : C.surface; ctx.fill();
  ctx.strokeStyle = n.hot ? C.accent : C.muted; ctx.lineWidth = 1.1 * px; ctx.stroke();
  ctx.restore();                    // the name is drawn by paintLabels, which sees every name at once
}
// the brain in the middle, as the sun: a line mark in the accent, a disc with a dot and twelve rays
function paintHubMark(n, ctx, px) {
  const r = 11;
  ctx.strokeStyle = C.accent; ctx.fillStyle = C.accent; ctx.lineWidth = 1.3 * px;
  ctx.beginPath(); ctx.arc(n.x, n.y, r * 0.62, 0, 2 * Math.PI); ctx.stroke();
  ctx.beginPath(); ctx.arc(n.x, n.y, r * 0.16, 0, 2 * Math.PI); ctx.fill();
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(n.x + Math.cos(a) * r * 0.82, n.y + Math.sin(a) * r * 0.82);
    ctx.lineTo(n.x + Math.cos(a) * r * 1.16, n.y + Math.sin(a) * r * 1.16);
    ctx.stroke();
  }
}
function paintArea(n, color, ctx, scale) {
  ctx.fillStyle = color; ctx.beginPath(); ctx.arc(n.x, n.y, radius(n) + 5 / scale, 0, 2 * Math.PI); ctx.fill();
}
function hoverText(n) {
  const esc = BV.esc;
  if (n.hub) return `<div class="pptl">the brain</div>`;
  return `<div class="pptl">${esc(n.name)}</div><div class="ppts">${esc(n.said)} · ${esc(n.open)}</div>`;
}
function stopGraph(el) {
  const g = el._fg;
  clearTimeout(el._sleep); clearTimeout(el._fitTimer);
  if (g && typeof g._destructor === "function") { try { g._destructor(); } catch (e) {} }
  el._fg = null; el._host = null;
}

// ---- (b) the roll of names ----
// Sorted by the next call and then by what ties them to the brain, drifting upward on its own so the page has one
// thing moving on it, and standing still the moment the pointer is on it so a name can be read or pressed.
function roll(el, api, rows) {
  const box = el.querySelector("[data-pp]"); if (!box) return;
  const esc = BV.esc;
  const sorted = rows.slice().sort((a, b) => {
    const an = a.next ? new Date(a.next.start).getTime() : Infinity, bn = b.next ? new Date(b.next.start).getTime() : Infinity;
    return an - bn || b.weight - a.weight || a.name.localeCompare(b.name);
  });
  const line = r => `<button class="pl" type="button" data-href="${esc(r.href)}" title="${esc(r.name + " · " + sayWhen(r) + " · " + sayOpen(r))}">
      <span class="pn${r.hot ? " hot" : ""}">${esc(r.name)}</span><span class="pw">${esc(r.next ? when(r.next) : r.last ? when(r.last) : "")}</span></button>`;
  const once = sorted.map(line).join("");
  box.innerHTML = `<div class="ppl" data-roll><div data-half>${once}</div><div data-half>${once}</div></div>`;
  const view = box.querySelector("[data-roll]");
  view.style.height = (api.expanded ? 420 : 240) + "px";
  stopRoll(el);
  let over = false;
  view.addEventListener("pointerenter", () => { over = true; });
  view.addEventListener("pointerleave", () => { over = false; });
  const halves = view.querySelectorAll("[data-half]");
  // the drift is kept as a number of its own and the box is told where to be, because scrollTop is rounded to whole
  // pixels: a third of a pixel a frame added to scrollTop itself rounds straight back and the roll never moves at all.
  // The list is written twice, so at the end of the first copy it steps back a copy and the seam never shows.
  let at = 0, last = 0;
  const step = ts => {
    el._roll = requestAnimationFrame(step);
    const dt = Math.min(100, last ? ts - last : 16); last = ts;   // by the clock, not by the frame: a 165Hz screen drifted three times as fast
    if (over || document.hidden || !view.isConnected) return;
    const half = halves[0] ? halves[0].offsetHeight : 0;
    if (half < 2 || view.scrollHeight <= view.clientHeight + 2) return;
    if (Math.abs(view.scrollTop - at) > 1.5) at = view.scrollTop;    // the wheel moved it: the drift carries on from there
    at += ROLL_PX * dt / 1000;
    if (at >= half) at -= half;
    view.scrollTop = at;
  };
  el._roll = requestAnimationFrame(step);
}
function stopRoll(el) { if (el._roll) cancelAnimationFrame(el._roll); el._roll = 0; }

// ---- the look ----
function styleOnce() {
  if (document.getElementById("bv-people-css")) return;
  const s = document.createElement("style");
  s.id = "bv-people-css";
  s.textContent = `
    .pp .ppg { width: 100%; position: relative; overflow: hidden; border-radius: var(--radius); cursor: grab; }
    .pp .ppg canvas { display: block; }
    .pp .ppg .graph-tooltip { font: 12.5px/1.4 var(--font-ui); color: var(--ink); background: var(--surface);
                              border: 1px solid var(--rule); border-radius: var(--radius); padding: 6px 9px; max-width: 260px; }
    .pp .ppg .graph-tooltip .pptl { font-family: var(--font-display); font-size: 13.5px; }
    .pp .ppg .graph-tooltip .ppts { color: var(--muted); font-size: 12px; }
    .pp .ppl { overflow: auto; scrollbar-width: none; }
    .pp .ppl::-webkit-scrollbar { display: none; }
    .pp .ppl .pl { display: flex; gap: 10px; align-items: baseline; width: 100%; text-align: left; cursor: pointer;
                   border: 0; background: none; padding: 4px 2px; border-top: 1px solid var(--rule-soft); }
    .pp .ppl .pl:first-child { border-top: 0; }
    .pp .ppl .pl:hover { background: var(--hover); }
    .pp .ppl .pn { font-family: var(--font-display); font-size: 14.5px; color: var(--ink); flex: 1; min-width: 0;
                   overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .pp .ppl .pn.hot { color: var(--accent); }
    .pp .ppl .pw { font-family: var(--font-mono); font-size: 11px; color: var(--muted); white-space: nowrap; }
    .pp .pnone { color: var(--muted); font-size: 13px; margin: 6px 0; }
  `;
  document.head.appendChild(s);
}
})();
