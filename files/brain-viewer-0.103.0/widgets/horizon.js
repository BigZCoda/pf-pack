// Horizon: how far away this brain's milestones are, in one of two forms you pick in its head and the board remembers.
//   numerals -- how many days are left to each milestone, as a number big enough to feel, with a bar for how far
//               through the run today is
//   road     -- the run drawn as one horizontal track from the day it started to the last milestone, each milestone
//               a stop on the way, the build order's steps set where their days fall, and a marker at today
// The milestones are DATA, not code (0.59.0): they are read from context/horizon.json through GET /api/file-raw,
//   {"startedAt": "YYYY-MM-DD", "milestones": [{"at": "YYYY-MM-DD", "label": "to the launch"}, ...]}
// so every brain carries its own dates and this file names none. With no file, or no milestone in it, the tile says
// so in one line and draws nothing made up. The steps come from the build order the ledgers already keep
// (GET /api/stages) and only the ones carrying a day are placed, because a step with no date has no honest place on
// a calendar.
(function () {
const FILE = "context/horizon.json";
const URL_ = "/api/file-raw?path=" + encodeURIComponent(FILE);
const NONE = "no horizon set; add milestones in context/horizon.json";
const FORMS = [["numerals", "the days left, one number per milestone"], ["road", "the run as one track, with the milestones on it"]];
const ISO = /^\d{4}-\d{2}-\d{2}/;

// the file, read raw: a missing file is null (the plain line), a broken one throws (the tile's own fail line)
async function readHorizon() {
  const ac = new AbortController(), t = setTimeout(() => ac.abort(), 20000);
  try {
    const r = await fetch(URL_, { signal: ac.signal, cache: "no-store" });
    if (r.status === 404) return null;
    if (!r.ok) { const e = new Error("the server answered " + r.status); e.status = r.status; throw e; }
    const j = await r.json();
    const marks = (Array.isArray(j && j.milestones) ? j.milestones : [])
      .filter(m => m && ISO.test(String(m.at || "")))
      .map(m => ({ at: String(m.at).slice(0, 10), label: String(m.label || "").trim() || "to " + String(m.at).slice(0, 10) }))
      .sort((a, b) => day(a.at) - day(b.at));
    if (!marks.length) return null;
    const from = ISO.test(String(j.startedAt || "")) ? String(j.startedAt).slice(0, 10) : null;
    return { from, marks, to: marks[marks.length - 1].at };
  } finally { clearTimeout(t); }
}

BV.widgets.register({
  id: "horizon", contract: 1, title: "Horizon", size: "4", defaultOn: true, expand: true,
  source: "the days left to this brain's milestones (context/horizon.json via GET /api/file-raw), and the build order laid along the run by the days the ledgers give its steps (GET /api/stages)",

  mount(el, api) {
    if (!document.getElementById("bv-horizon-css")) {
      const s = document.createElement("style");
      s.id = "bv-horizon-css";
      s.textContent = `
        .hz { display: flex; gap: 26px; flex-wrap: wrap; }
        .hz .one { flex: 1; min-width: 118px; }
        .hz .n { font-family: var(--font-title); font-weight: 500; color: var(--accent); font-size: 56px; line-height: .9; }
        .hz .n.past { color: var(--muted); }
        .hz .lb { font-family: var(--font-ui); font-size: 10px; letter-spacing: .14em; text-transform: uppercase;
                  color: var(--muted); margin-top: 5px; display: block; }
        .hz .bar { height: 2px; background: var(--rule-soft); margin-top: 9px; position: relative; }
        .hz .bar i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--accent); display: block; }
        .hz .on { font-family: var(--font-mono); font-size: 10.5px; color: var(--muted); margin-top: 5px; display: block; }
        .hzr svg { display: block; width: 100%; height: auto; overflow: visible; }
        .hzr .trk { stroke: var(--rule-soft); stroke-width: 1; }
        .hzr .trk.gone { stroke: var(--accent); stroke-width: 2.5; }
        .hzr .stop circle { fill: var(--surface); stroke: var(--rule); stroke-width: 1; }
        .hzr .stop.done circle { fill: var(--accent); stroke: var(--accent); }
        .hzr .stop.big circle { fill: var(--open); stroke: var(--open); }
        .hzr .cap { font-family: var(--font-ui); font-size: 9px; letter-spacing: .12em; text-transform: uppercase; fill: var(--muted); }
        .hzr .cap.on { fill: var(--accent); }
        .hzr .num { font-family: var(--font-mono); font-size: 10.5px; fill: var(--muted); }
        .hzr .today line { stroke: var(--open); stroke-width: 1.5; }
        .hzr .today circle { fill: var(--open); }
        .hzr .days { font-family: var(--font-title); font-weight: 500; font-size: 19px; fill: var(--accent); }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div data-hz></div>`;
    api.card.addEventListener("click", e => {
      const b = e.target.closest("[data-form]"); if (!b) return;
      api.setSettings({ form: b.dataset.form });
      paintHead(api);
      this.refresh(el, api);
    });
    paintHead(api);
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    try { el._hz = await readHorizon(); } catch (e) { el._hz = null; return api.fail(e); }
    if (!el._hz) { el._stages = null; api.count(""); return api.say(NONE); }
    let box = el.querySelector("[data-hz]");
    if (!box) { el.innerHTML = `<div data-hz></div>`; box = el.querySelector("[data-hz]"); }
    if (form(api) !== "road") { el._stages = null; return numerals(box, api, el._hz); }
    if (!el._stages) { try { el._stages = await api.get("/api/stages"); } catch (e) { el._stages = { steps: [] }; } }
    road(box, api, el._stages, el._hz);
  },
  resize(el, api) { if (el._hz && form(api) === "road") road(el.querySelector("[data-hz]"), api, el._stages || { steps: [] }, el._hz); },
});

function form(api) {
  const f = (api.settings() || {}).form;
  return FORMS.some(r => r[0] === f) ? f : "numerals";
}
function paintHead(api) {
  const f = form(api);
  api.head(FORMS.map(([id, why]) =>
    `<button class="wtab${id === f ? " on" : ""}" type="button" data-form="${id}" title="${api.esc(why)}">${id}</button>`).join(""));
}

// ---- the first form: one number per milestone ----
function numerals(box, api, hz) {
  const esc = api.esc, today = midnight(new Date());
  const FROM = hz.from, from = FROM ? day(FROM) : today;
  box.className = "hz";
  box.innerHTML = hz.marks.map(m => {
    const to = day(m.at);
    const left = Math.round((to - today) / 86400000);
    const span = Math.max(1, (to - from) / 86400000);
    const gone = Math.max(0, Math.min(1, (today - from) / 86400000 / span));
    return `<div class="one">
        <div class="n${left < 0 ? " past" : ""}">${esc(left < 0 ? "0" : String(left))}</div>
        <span class="lb">${esc(left === 1 ? "day " + m.label : "days " + m.label)}</span>
        <div class="bar" title="${FROM ? Math.round(gone * 100) + "% of the way there since " + esc(pretty(FROM)) : "no start day in " + FILE}"><i style="width:${(gone * 100).toFixed(1)}%"></i></div>
        <span class="on">${esc(pretty(m.at))}</span>
      </div>`;
  }).join("");
  api.count(soonest(hz.marks, today));
}

// ---- the second form: the road ----
function road(box, api, stages, hz) {
  if (!box || !hz) return;
  const esc = api.esc, today = midnight(new Date());
  const MARKS = hz.marks, FROM = hz.from || isoOf(Math.min(today, day(MARKS[0].at)));
  const from = day(FROM), to = day(hz.to);
  const span = Math.max(1, to - from);
  box.className = "hzr";
  const W = api.expanded ? 1100 : 430, H = 108;
  const X0 = 16, X1 = W - 16, TW = X1 - X0, Y = 66;
  const at = t => X0 + TW * Math.max(0, Math.min(1, (t - from) / span));
  const nowX = at(today);

  const bits = [`<line class="trk" x1="${X0}" y1="${Y}" x2="${X1}" y2="${Y}"></line>`,
                `<line class="trk gone" x1="${X0}" y1="${Y}" x2="${nowX.toFixed(1)}" y2="${Y}"></line>`];
  // the month it enters, under the track, so the run reads as a calendar and not as a bar
  for (let m = new Date(FROM + "T00:00:00"); m.getTime() <= to; m = new Date(m.getFullYear(), m.getMonth() + 1, 1)) {
    const x = at(m.getTime());
    if (x <= X0 + 1) continue;
    bits.push(`<line class="trk" x1="${x.toFixed(1)}" y1="${Y}" x2="${x.toFixed(1)}" y2="${Y + 5}"></line>`);
    bits.push(`<text class="cap" x="${x.toFixed(1)}" y="${Y + 17}" text-anchor="middle">${esc(m.toLocaleDateString(undefined, { month: "short" }).toLowerCase())}</text>`);
  }
  // the milestones the run is measured against: the stops
  for (const m of MARKS) {
    const x = at(day(m.at)), passed = day(m.at) <= today;
    bits.push(`<g class="stop big"><circle cx="${x.toFixed(1)}" cy="${Y}" r="5.5"></circle>
        <title>${esc(m.label.replace(/^to /, ""))} · ${esc(pretty(m.at))}</title></g>`);
    bits.push(`<text class="cap${passed ? "" : " on"}" x="${x.toFixed(1)}" y="${Y - 13}" text-anchor="${x > X1 - 60 ? "end" : "middle"}">${esc(m.label.replace(/^to /, ""))}</text>`);
  }
  // the build order, where the ledgers give a step a day. Several steps finished on one day are ONE mark on the road,
  // a little wider for each of them: six dots at the same x would simply sit on top of each other and say less.
  const steps = ((stages || {}).steps || []).filter(s => dated(s));
  const byDay = new Map();
  for (const s of steps) {
    const k = String(dated(s)).slice(0, 10);
    if (!byDay.has(k)) byDay.set(k, []);
    byDay.get(k).push(s);
  }
  for (const [k, group] of byDay) {
    const x = at(day(k));
    const done = group.every(s => s.stage === "done");
    const names = group.slice(0, 4).map(s => s.short || s.text || "a step");
    if (group.length > names.length) names.push("and " + (group.length - names.length) + " more");
    bits.push(`<g class="stop${done ? " done" : ""}">
        <circle cx="${x.toFixed(1)}" cy="${(Y - 22).toFixed(1)}" r="${(3.5 + Math.min(3, group.length - 1) * 0.9).toFixed(1)}"></circle>
        <title>${esc(names.join(", "))} · ${esc(pretty(k))}</title></g>`);
  }
  // today
  const next = MARKS.find(m => day(m.at) >= today) || MARKS[MARKS.length - 1];
  const left = Math.round((day(next.at) - today) / 86400000);
  bits.push(`<g class="today"><line x1="${nowX.toFixed(1)}" y1="${Y - 12}" x2="${nowX.toFixed(1)}" y2="${Y + 8}"></line>
      <circle cx="${nowX.toFixed(1)}" cy="${Y}" r="3.5"></circle></g>`);
  const anchor = nowX > X1 - 70 ? "end" : (nowX < X0 + 70 ? "start" : "middle");
  bits.push(`<text class="days" x="${nowX.toFixed(1)}" y="26" text-anchor="${anchor}">${esc(left < 0 ? "0" : String(left))}</text>`);
  bits.push(`<text class="num" x="${nowX.toFixed(1)}" y="40" text-anchor="${anchor}">${esc((left === 1 ? "day " : "days ") + next.label)}</text>`);

  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="the run as one track, with its milestones on it">${bits.join("")}</svg>`;
  api.count(soonest(MARKS, today) + (steps.length ? " · " + api.plural(steps.length, "milestone") : ""));
}

const dated = s => s && (s.at || s.due || s.done) || null;
function soonest(marks, today) {
  const n = marks.map(m => Math.round((day(m.at) - today) / 86400000)).filter(x => x >= 0).sort((a, b) => a - b)[0];
  return n == null ? "past" : n + " days";
}
const day = iso => new Date(String(iso).slice(0, 10) + "T00:00:00").getTime();
const isoOf = t => { const d = new Date(t); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const midnight = d => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
const pretty = iso => new Date(String(iso).slice(0, 10) + "T12:00:00").toLocaleDateString(undefined, { month: "long", day: "numeric" });
})();
