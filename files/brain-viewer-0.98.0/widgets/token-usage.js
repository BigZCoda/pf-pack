// Usage: the tokens each agent used, week by week, as stacked bars. The owner asked on 2026-10-02 for a weekly
// graph of each agent's tokens, so anyone can see whether something needs adjusting.
// It reads context/token-usage.json, which skills/token-usage/usage.py writes from Claude Code's own transcripts and
// the close of the day refreshes every night. The file is read raw through /api/file-raw, so a missing file is a plain
// line on the tile, never a broken one.
(function () {
BV.widgets.register({
  id: "token-usage", contract: 1, title: "Token usage", size: "8", defaultOn: false,
  source: "tokens per agent per week, last eight weeks, from Claude Code transcripts (context/token-usage.json via GET /api/file-raw; skills/token-usage/usage.py, nightly at the close). A subagent's output count is understated.",
  async mount(el, api) {
    css();
    return refresh(el, api);
  },
  refresh: (el, api) => refresh(el, api),
  resize(el, api) { if (el._data) draw(el, api); },
});

async function refresh(el, api) {
  let j;
  try { j = await read(); }
  catch (e) { api.fail(e); return; }
  if (!j) { el._data = null; api.count(""); api.say("no usage file yet; run python skills/token-usage/usage.py"); return; }
  el._data = j;
  draw(el, api);
}
const FILE = "context/token-usage.json";
const URL_ = "/api/file-raw?path=" + encodeURIComponent(FILE);
// series colors, all tokens, the six hues the look tells apart; the rest share --rule as "everything else"
const COLORS = ["--accent", "--mind", "--done", "--open", "--mouth", "--ink-soft"];
const REST = "everything else";

function fmt(n) {
  n = Number(n) || 0;
  if (n >= 1e9) return (n / 1e9).toFixed(n >= 1e10 ? 0 : 1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e8 ? 0 : 1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e5 ? 0 : 1) + "K";
  return String(n);
}
function shortDay(iso) {
  const d = new Date(iso + "T12:00:00");
  return isNaN(d) ? iso : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

async function read() {
  const ac = new AbortController(), t = setTimeout(() => ac.abort(), 20000);
  try {
    const r = await fetch(URL_, { signal: ac.signal, cache: "no-store" });
    if (r.status === 404) return null;
    if (!r.ok) { const e = new Error("the server answered " + r.status); e.status = r.status; throw e; }
    return await r.json();
  } finally { clearTimeout(t); }
}

// the agents in order of their eight-week total; the first five (six when there are only six) keep their own color
function series(weeks) {
  const tot = {};
  for (const w of weeks) for (const [a, b] of Object.entries(w.byAgent || {})) tot[a] = (tot[a] || 0) + (b.total || 0);
  const names = Object.keys(tot).sort((x, y) => tot[y] - tot[x]);
  const keep = names.length > COLORS.length ? names.slice(0, COLORS.length - 1) : names;
  const out = keep.map((n, i) => ({ name: n, color: "var(" + COLORS[i] + ")", members: [n], total: tot[n] }));
  const rest = names.slice(keep.length);
  if (rest.length) out.push({ name: REST, color: "var(--rule)", members: rest, total: rest.reduce((s, n) => s + tot[n], 0) });
  return out;
}
function cell(w, s) {
  const b = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0, messages: 0 };
  for (const m of s.members) {
    const x = (w.byAgent || {})[m]; if (!x) continue;
    for (const k in b) b[k] += x[k] || 0;
  }
  return b;
}

function css() {
  if (document.getElementById("bv-usage-css")) return;
  const s = document.createElement("style");
  s.id = "bv-usage-css";
  s.textContent = `
    .tu .read { font-family: var(--font-display); font-size: 15px; line-height: 1.45; color: var(--ink-soft); margin: 2px 0 8px; }
    .tu .read b { font-family: var(--font-title); font-weight: 500; color: var(--accent); font-size: 22px; }
    .tu .read .d { font-family: var(--font-mono); font-size: 12px; color: var(--muted); }
    .tu svg { display: block; width: 100%; overflow: visible; }
    .tu svg .ax { font-family: var(--font-mono); font-size: 10.5px; fill: var(--muted); }
    .tu svg .gl { stroke: var(--rule-soft); stroke-width: 1; }
    .tu svg rect.seg { cursor: default; transition: opacity .12s; }
    .tu svg.hov rect.seg { opacity: .35; }
    .tu svg.hov rect.seg.on { opacity: 1; }
    .tu .hover { font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-soft); min-height: 1.5em; margin: 6px 0 4px; }
    .tu .lg { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 4px; }
    .tu .lg span { font-family: var(--font-ui); font-size: 11.5px; color: var(--ink-soft); display: inline-flex; align-items: center; gap: 6px; cursor: default; }
    .tu .lg i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; flex: none; }
    .tu .lg em { font-style: normal; font-family: var(--font-mono); font-size: 10.5px; color: var(--muted); }
  `;
  document.head.appendChild(s);
}

function draw(el, api) {
  const j = el._data;
  const weeks = (j && Array.isArray(j.weeks)) ? j.weeks.slice(-8) : [];
  if (!weeks.length) { api.count(""); api.say("the usage file has no weeks in it; run python skills/token-usage/usage.py"); return; }
  const S = series(weeks);
  const cur = weeks[weeks.length - 1], prev = weeks[weeks.length - 2];
  const now = new Date();
  const dayIn = Math.min(7, Math.max(1, Math.floor((now - new Date(cur.start + "T00:00:00")) / 864e5) + 1));
  let delta = "";
  if (prev && prev.total) {
    const pct = Math.round((cur.total - prev.total) / prev.total * 100);
    delta = (pct >= 0 ? "+" : "") + pct + "%";
  }
  const pace = prev && prev.total && dayIn < 7 ? ", on pace for " + fmt(cur.total / dayIn * 7) : "";
  const readout = `<p class="read">this week <b>${fmt(cur.total)}</b> <span class="d">(${dayIn} of 7 days${pace})</span>
    &nbsp;last week <b>${fmt(prev ? prev.total : 0)}</b>${delta ? ` <span class="d">${delta} so far</span>` : ""}</p>`;

  const W = Math.max(280, Math.round(el.clientWidth || 640)), H = 210;
  const L = 46, R = 6, T = 8, B = 22, ph = H - T - B, pw = W - L - R;
  const max = Math.max(1, ...weeks.map(w => w.total || 0));
  const step = Math.pow(10, Math.floor(Math.log10(max)));
  const tick = [1, 2, 2.5, 5, 10].map(m => m * step).find(t => max / t <= 4) || step * 10;
  const top = Math.ceil(max / tick) * tick, y = v => T + ph - v / top * ph;
  let g = "";
  for (let v = 0; v <= top + 1; v += tick) {
    g += `<line class="gl" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>`;
    g += `<text class="ax" x="${L - 6}" y="${(y(v) + 3.5).toFixed(1)}" text-anchor="end">${fmt(v)}</text>`;
  }
  const slot = pw / weeks.length, bw = Math.min(54, slot * 0.62);
  weeks.forEach((w, i) => {
    const x = L + slot * i + (slot - bw) / 2;
    let base = 0;
    S.forEach((s, si) => {
      const c = cell(w, s); if (!c.total) return;
      const y1 = y(base + c.total), h = Math.max(0.5, y(base) - y1);
      g += `<rect class="seg" data-w="${i}" data-s="${si}" x="${x.toFixed(1)}" y="${y1.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" fill="${s.color}"/>`;
      base += c.total;
    });
    g += `<text class="ax" x="${(x + bw / 2).toFixed(1)}" y="${H - 6}" text-anchor="middle">${api.esc(shortDay(w.start))}</text>`;
  });
  const legend = S.map((s, si) => `<span data-s="${si}"><i style="background:${s.color}"></i>${api.esc(s.name)} <em>${fmt(s.total)}</em></span>`).join("");
  api.count(fmt(cur.total) + " this week");
  api.html(`<div class="tu">${readout}<svg viewBox="0 0 ${W} ${H}" height="${H}" data-tu>${g}</svg>
    <div class="hover" data-hover>${api.esc("updated " + api.when(j.generatedAt))}</div><div class="lg">${legend}</div></div>`);

  const svg = el.querySelector("svg[data-tu]"), hv = el.querySelector("[data-hover]");
  const rest = hv.textContent;
  const show = (wi, si) => {
    svg.classList.add("hov");
    svg.querySelectorAll("rect.seg").forEach(r => r.classList.toggle("on",
      (wi == null || r.dataset.w === String(wi)) && r.dataset.s === String(si)));
    const s = S[si], who = s.members.length > 1 ? s.name + " (" + s.members.join(", ") + ")" : s.name;
    if (wi == null) { hv.textContent = who + ": " + fmt(s.total) + " over " + weeks.length + " weeks"; return; }
    const w = weeks[wi], c = cell(w, s);
    hv.textContent = who + ", week of " + shortDay(w.start) + ": " + fmt(c.total) + " (input " + fmt(c.input) +
      ", output " + fmt(c.output) + ", cache read " + fmt(c.cacheRead) + ", cache write " + fmt(c.cacheWrite) + "; " +
      api.plural(c.messages, "message") + ")";
  };
  const clear = () => { svg.classList.remove("hov"); hv.textContent = rest; };
  svg.addEventListener("mouseover", e => { const r = e.target.closest("rect.seg"); if (r) show(+r.dataset.w, +r.dataset.s); });
  svg.addEventListener("mouseleave", clear);
  const lg = el.querySelector(".lg");
  lg.addEventListener("mouseover", e => { const sp = e.target.closest("[data-s]"); if (sp) show(null, +sp.dataset.s); });
  lg.addEventListener("mouseleave", clear);
}

})();
