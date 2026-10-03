// The day dial: the day drawn as a sundial, sunrise on the left, sunset on the right, with the sun sitting where the
// hour is. Under it the next call is the hero, with its people and a way into its prep. The head switches the drawing
// between today, three days, the week and the month.
// The calendar is reachable only through the Claude Code tool, so the session start writes what it saw and this draws
// THAT: context/today-calendar.json for today and context/week-calendar.json for the seven days after it. Past the last
// day the file knows, the dial says so rather than drawing an empty week.
(function () {
BV.widgets.register({
  id: "dial", contract: 1, title: "The day", size: "8", defaultOn: false,
  source: "the calendar the session start wrote, today and the seven days after it, each call joined to its prep (GET /api/calls, GET /api/calendar/week)",

  mount(el, api) {
    if (!document.getElementById("bv-dial-css")) {
      const s = document.createElement("style");
      s.id = "bv-dial-css";
      s.textContent = `
        .dial svg { display: block; width: 100%; height: auto; overflow: visible; }
        .dial .lbl { font-family: var(--font-ui); font-size: 9.5px; letter-spacing: .12em; text-transform: uppercase; fill: var(--muted); }
        .dial .hr { font-family: var(--font-mono); font-size: 9px; fill: var(--muted); }
        .dial .lbl.on { fill: var(--accent); }
        .dial .hero { display: flex; gap: 18px; align-items: flex-end; flex-wrap: wrap; margin-top: 4px; }
        .dial .hero .ht { font-family: var(--font-title); font-weight: 500; color: var(--accent); font-size: 36px; line-height: 1.02; margin: 0; }
        .dial .hero .hw { font-family: var(--font-mono); font-size: 13px; color: var(--muted); margin: 5px 0 0; }
        .dial .hero .hr2 { margin-left: auto; display: flex; gap: 10px; align-items: center; }
        .dial .faces { display: inline-flex; }
        .dial .face { width: 27px; height: 27px; border-radius: 50%; border: 1px solid var(--rule); background: var(--surface);
                      color: var(--ink-soft); font-family: var(--font-ui); font-size: 10.5px; letter-spacing: .04em;
                      display: inline-flex; align-items: center; justify-content: center; margin-right: -6px; }
        .dial .face.me { background: var(--selected); }
        .dial .days { display: grid; gap: 10px; margin-top: 2px; }
        .dial .dcol { border-top: 1px solid var(--rule-soft); padding-top: 5px; min-width: 0; }
        .dial .dcol.today { border-top-color: var(--accent); }
        .dial .dcol h4 { margin: 0 0 4px; font-family: var(--font-ui); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); font-weight: 400; }
        .dial .dcol.today h4 { color: var(--accent); }
        .dial .dev { font-size: 12.5px; padding: 2px 0; display: flex; gap: 7px; min-width: 0; }
        .dial .dev .t { font-family: var(--font-mono); font-size: 11px; color: var(--muted); flex: none; }
        .dial .dev .n { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .dial .dnone { font-size: 12px; color: var(--muted); opacity: .6; }
        .dial .month { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 3px; margin-top: 2px; }
        .dial .mcell { border-top: 1px solid var(--rule-soft); padding: 3px 4px 8px; min-height: 40px; }
        .dial .mcell .d { font-family: var(--font-mono); font-size: 11px; color: var(--muted); }
        .dial .mcell.now { border-top-color: var(--accent); }
        .dial .mcell.now .d { color: var(--accent); font-weight: 700; }
        .dial .mcell .pip { display: block; height: 3px; border-radius: 2px; background: var(--accent); margin-top: 3px; }
        .dial .mcell.out { opacity: .35; }
        .dial .mcap { font-family: var(--font-ui); font-size: 9.5px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); text-align: center; padding-bottom: 2px; }
        .dial .edge { font-size: 12px; color: var(--muted); margin: 9px 0 0; }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="dial" data-dial></div>`;
    try { el._view = localStorage.getItem("bv.home.dial.view") || "today"; } catch (e) { el._view = "today"; }
    api.head(["today", "3 days", "week", "month"].map(v =>
      `<button class="wtab${v === el._view ? " on" : ""}" type="button" data-view="${v}">${v}</button>`).join(""));
    api.card.addEventListener("click", e => {
      const b = e.target.closest("[data-view]"); if (!b) return;
      el._view = b.dataset.view;
      try { localStorage.setItem("bv.home.dial.view", el._view); } catch (x) {}
      for (const o of api.card.querySelectorAll("[data-view]")) o.classList.toggle("on", o.dataset.view === el._view);
      paint(el, api);
    });
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const soft = p => api.get(p).then(j => j, e => ({ _error: e && e.message, _status: e && e.status }));
    const [calls, week] = await Promise.all([soft("/api/calls"), soft("/api/calendar/week")]);
    el._calls = calls; el._week = week;
    paint(el, api);
  },
  resize(el, api) { paint(el, api); },
});

// ---- the drawing ----
const DIAL_FROM = 7, DIAL_TO = 19;            // the arc runs 7 in the morning to 7 at night
const DAY_MS = 86400000;

function dayKey(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
function dayName(iso) {
  const d = new Date(iso + "T12:00:00");
  return isNaN(d) ? iso : d.toLocaleDateString(undefined, { weekday: "long" }) + " " + (d.getMonth() + 1) + "/" + d.getDate();
}
function clockOf(iso) {
  const d = new Date(iso);
  return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).toLowerCase().replace(" ", "");
}
function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}
function countdown(ms) {
  if (ms <= 0) return "now";
  const m = Math.round(ms / 60000);
  if (m < 60) return "in " + m + (m === 1 ? " minute" : " minutes");
  const h = Math.floor(m / 60), rm = m % 60;
  if (h < 24) return "in " + h + (h === 1 ? " hour" : " hours") + (rm ? " " + rm + (rm === 1 ? " minute" : " minutes") : "");
  const d = Math.floor(h / 24), rh = h % 24;
  return "in " + d + (d === 1 ? " day" : " days") + (rh ? " " + rh + (rh === 1 ? " hour" : " hours") : "");
}

function paint(el, api) {
  const box = el.querySelector("[data-dial]"); if (!box) return;
  const calls = el._calls || {}, week = el._week || {};
  const esc = api.esc;
  const todayKey = dayKey(new Date());

  // today's events carry their preps and their matched people; the week file carries the days after it
  const todayEvents = (calls && calls.exists && !calls.stale ? (calls.events || []) : [])
    .map(e => Object.assign({}, e, { date: todayKey }));
  const weekEvents = (week.events || []).filter(e => e.date !== todayKey || !todayEvents.length);
  const all = todayEvents.concat(weekEvents).sort((a, b) => String(a.start).localeCompare(String(b.start)));
  const lastDay = week.to || (all.length ? all[all.length - 1].date : null);

  api.count(all.length ? api.plural(todayEvents.length || all.filter(e => e.date === todayKey).length, "call") + " today"
                       : "no calendar");
  if (!all.length && !(calls && calls.exists) && !week.exists) {
    box.innerHTML = `<p class="wsay">No calendar has been written. The next session start writes it.</p>`;
    return;
  }

  const view = el._view || "today";
  let body = "";
  if (view === "today") body = drawToday(todayEvents.length ? todayEvents : all.filter(e => e.date === todayKey), esc);
  else if (view === "month") body = drawMonth(all, esc);
  else body = drawDays(all, view === "3 days" ? 3 : 7, esc);

  const hero = drawHero(all, calls, esc);
  const edge = lastDay && lastDay < dayKey(new Date())
    ? `<p class="edge">No calendar past ${esc(dayName(lastDay))}; the next session start writes the week.</p>` : "";
  box.innerHTML = body + hero + edge;

  // the sun walks the arc, and the countdown counts, without asking the server anything
  clearInterval(el._sun);
  if (view === "today") el._sun = setInterval(() => { if (!document.hidden) placeSun(box, el); }, 30000);
  clearInterval(el._count);
  el._count = setInterval(() => { if (!document.hidden) tickCount(box); }, 30000);
}

// ---- the arc ----
function arcPt(f) {
  const th = Math.PI * (1 - Math.max(0, Math.min(1, f)));
  return [380 + 330 * Math.cos(th), 205 - 105 * Math.sin(th)];
}
function arcPath(f0, f1) {
  const [x0, y0] = arcPt(f0), [x1, y1] = arcPt(f1);
  return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A 330 105 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
}
function frac(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return 0;
  return (d.getHours() + d.getMinutes() / 60 - DIAL_FROM) / (DIAL_TO - DIAL_FROM);
}
function nowFrac() {
  const d = new Date();
  return Math.max(0, Math.min(1, (d.getHours() + d.getMinutes() / 60 - DIAL_FROM) / (DIAL_TO - DIAL_FROM)));
}

// ---- where a label goes (0.37.1) ----
// The hours read INSIDE the arc, under it, and the calls OUTSIDE it, above. 0.37.0 wrote both on the outside, so
// "MIKE MEETING" landed on top of "12p" and two calls an hour apart wrote over each other. A call label that would
// touch one already placed -- another call, or an hour -- is lifted a row, one label height at a time, until it is
// clear, and a name is cut with an ellipsis to the room its own side of the arc has, so nothing is drawn past the
// edge of the box.
const LBL_H = 12;                       // one label height, which is also the stagger step
const LBL_OUT = 22;                     // how far off the arc the first row of call labels sits
const HOUR_CH = 5.6;                    // one 9px mono character, for the room "12p" takes up
const LBL_CH = 7.4;                     // one uppercase 9.5px Baskerville character plus its .12em of letter-spacing
const LBL_LEFT = 6, LBL_RIGHT = 754;    // the box, less a hair
const HOUR_IN = 17;                     // how far under the arc an hour reads
const LBL_ROWS = 4;                     // how many rows up a crowded hour may stagger to

function cut(s, n) {
  s = String(s || "").replace(/\s+/g, " ").trim();
  if (n < 2) return "";
  return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
}
function hits(box, placed) {
  return placed.some(q => box.x0 < q.x1 + 4 && q.x0 < box.x1 + 4 && box.y0 < q.y1 + 2 && q.y0 < box.y1 + 2);
}

function drawToday(events, esc) {
  const nf = nowFrac(), now = Date.now();
  const ticks = [], placed = [];
  for (let h = DIAL_FROM; h <= DIAL_TO; h++) {
    const f = (h - DIAL_FROM) / (DIAL_TO - DIAL_FROM);
    const [x, y] = arcPt(f);
    const th = Math.PI * (1 - f), nx = Math.cos(th) * 0.9, ny = -Math.sin(th) * 0.9;   // away from the centre
    const big = h % 3 === 0;
    ticks.push(`<line x1="${x.toFixed(1)}" y1="${y.toFixed(1)}" x2="${(x + nx * (big ? 9 : 5)).toFixed(1)}" y2="${(y + ny * (big ? 9 : 5)).toFixed(1)}" stroke="var(--rule)" stroke-width="1"></line>`);
    if (!big) continue;
    const hour = `${h > 12 ? h - 12 : h}${h < 12 ? "a" : "p"}`;
    const tx = x - nx * HOUR_IN, ty = y - ny * HOUR_IN + 3, tw = hour.length * HOUR_CH;
    ticks.push(`<text class="hr" x="${tx.toFixed(1)}" y="${ty.toFixed(1)}" text-anchor="middle">${hour}</text>`);
    placed.push({ x0: tx - tw / 2, x1: tx + tw / 2, y0: ty - 9, y1: ty + 3 });   // a call label is kept off these
  }
  const segs = [], labels = [];
  const order = events.slice().sort((a, b) => String(a.start).localeCompare(String(b.start)));
  for (const e of order) {
    const f0 = Math.max(0, Math.min(1, frac(e.start))), f1 = Math.max(f0 + 0.012, Math.min(1, frac(e.end)));
    const past = new Date(e.end).getTime() < now;
    const live = new Date(e.start).getTime() <= now && new Date(e.end).getTime() >= now;
    segs.push(`<path d="${arcPath(f0, f1)}" fill="none" stroke="${past ? "var(--muted)" : "var(--accent)"}" stroke-width="${live ? 13 : 10}" stroke-linecap="butt" opacity="${past ? .45 : 1}"><title>${esc(e.title || "a call")}</title></path>`);
    const fm = (f0 + f1) / 2, th = Math.PI * (1 - fm);
    const [ax, ay] = arcPt(fm);
    const anchor = fm < 0.2 ? "start" : fm > 0.8 ? "end" : "middle";
    const lx = Math.max(LBL_LEFT, Math.min(LBL_RIGHT, ax + Math.cos(th) * LBL_OUT));
    const room = anchor === "start" ? LBL_RIGHT - lx
               : anchor === "end" ? lx - LBL_LEFT
               : 2 * Math.min(lx - LBL_LEFT, LBL_RIGHT - lx);
    const text = cut(e.title || "a call", Math.min(28, Math.floor(room / LBL_CH)));
    if (!text) continue;                           // no room for a word: the band and its tooltip still say it is there
    const w = text.length * LBL_CH;
    const x0 = anchor === "start" ? lx : anchor === "end" ? lx - w : lx - w / 2;
    let put = null;
    for (let row = 0; row < LBL_ROWS; row++) {
      // the stagger is a row UP, not further along the normal: at the ends of the arc the normal is sideways, so
      // pushing out there would slide a long name along under the hours instead of lifting it off them
      const ly = ay - Math.sin(th) * LBL_OUT - row * LBL_H;
      const box = { x0, x1: x0 + w, y0: ly - LBL_H + 3, y1: ly + 3, lx, ly, text };
      put = box;                                   // the top row is taken whether or not it came out clear
      if (!hits(box, placed)) break;
    }
    placed.push(put);
    labels.push(`<text class="lbl${past ? "" : " on"}" x="${put.lx.toFixed(1)}" y="${put.ly.toFixed(1)}" text-anchor="${anchor}">${esc(put.text)}</text>`);
  }
  const [sx, sy] = arcPt(nf);
  return `<svg viewBox="0 0 760 232" role="img" aria-label="today drawn as a sundial">
      <path data-past d="${arcPath(0, nf)}" fill="none" stroke="var(--muted)" stroke-width="1.5" opacity=".6"></path>
      <path data-future d="${arcPath(nf, 1)}" fill="none" stroke="var(--accent)" stroke-width="1.5"></path>
      ${ticks.join("")}
      ${segs.join("")}
      ${labels.join("")}
      <circle data-sun cx="${sx.toFixed(1)}" cy="${sy.toFixed(1)}" r="8" fill="var(--open)" stroke="var(--open-tint)" stroke-width="5"></circle>
    </svg>`;
}

function placeSun(box, el) {
  const svg = box.querySelector("svg"); if (!svg) return;
  const nf = nowFrac();
  const [x, y] = arcPt(nf);
  const sun = svg.querySelector("[data-sun]");
  if (sun) { sun.setAttribute("cx", x.toFixed(1)); sun.setAttribute("cy", y.toFixed(1)); }
  const past = svg.querySelector("[data-past]"), fut = svg.querySelector("[data-future]");
  if (past) past.setAttribute("d", arcPath(0, nf));
  if (fut) fut.setAttribute("d", arcPath(nf, 1));
}
function tickCount(box) {
  const w = box.querySelector("[data-when]");
  if (w && w.dataset.start) w.textContent = countdown(new Date(w.dataset.start).getTime() - Date.now());
}

// ---- the hero: the next call, or the one happening now ----
function drawHero(all, calls, esc) {
  const now = Date.now();
  const todayKey = dayKey(new Date());
  const live = all.find(e => new Date(e.start).getTime() <= now && new Date(e.end).getTime() >= now);
  const next = live || all.find(e => new Date(e.start).getTime() > now);
  if (!next) return `<p class="wsay">Nothing more on the calendar.</p>`;
  const people = (next.people || next.attendees || []).map(p => p.name || p).filter(Boolean);
  // the face that is this brain's owner: the @name in the viewer's `owner` setting (BV.owner), matched on the name's
  // start, so "@sam" marks "Sam" and "Samantha Lee" and the code names nobody
  const me = String(BV.owner || "").replace(/^@/, "").toLowerCase();
  const faces = people.slice(0, 6).map(n =>
    `<span class="face${me && me !== "me" && String(n).toLowerCase().startsWith(me) ? " me" : ""}" title="${esc(n)}">${esc(initials(n))}</span>`).join("");
  // the prep the /api/calls row carries; a call on a later day has none written yet, so its people are the way in
  const prep = ((calls.events || []).find(e => e.start === next.start) || {}).preps;
  const href = (prep && prep[0]) ? "/reader?path=" + encodeURIComponent(prep[0].path) : "/people";
  const label = (prep && prep[0]) ? "open the prep" : next.date === todayKey ? "no prep yet, open the people" : "open the people";
  const at = next.date === todayKey ? clockOf(next.start) : dayName(next.date) + " " + clockOf(next.start);
  return `<div class="hero">
      <div><p class="ht">${esc(next.title || "a call")}</p>
        <p class="hw" data-when data-start="${esc(next.start)}">${esc(live ? "now" : countdown(new Date(next.start).getTime() - now))} · ${esc(at)}</p></div>
      <div class="hr2"><span class="faces">${faces}</span><a class="btn" href="${esc(href)}" style="text-decoration:none">${esc(label)}</a></div>
    </div>`;
}

// ---- three days, and the week ----
function drawDays(all, n, esc) {
  const start = new Date(); start.setHours(0, 0, 0, 0);
  const todayKey = dayKey(new Date());
  const cols = [];
  for (let i = 0; i < n; i++) {
    const d = new Date(start.getTime() + i * DAY_MS), k = dayKey(d);
    const evs = all.filter(e => e.date === k);
    cols.push(`<div class="dcol${k === todayKey ? " today" : ""}">
        <h4>${esc(d.toLocaleDateString(undefined, { weekday: "short" }))} ${d.getMonth() + 1}/${d.getDate()}</h4>
        ${evs.length ? evs.map(e => `<div class="dev"><span class="t">${esc(clockOf(e.start))}</span><span class="n" title="${esc(e.title || "")}">${esc(e.title || "a call")}</span></div>`).join("")
                     : `<p class="dnone">nothing</p>`}
      </div>`);
  }
  return `<div class="days" style="grid-template-columns: repeat(${n}, minmax(0, 1fr))">${cols.join("")}</div>`;
}

// ---- the month, with the days the calendar knows about marked ----
function drawMonth(all, esc) {
  const now = new Date(), todayKey = dayKey(now);
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  const lead = first.getDay();
  const days = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const caps = ["s", "m", "t", "w", "t", "f", "s"].map(c => `<div class="mcap">${c}</div>`).join("");
  const cells = [];
  for (let i = 0; i < lead; i++) cells.push(`<div class="mcell out"></div>`);
  for (let d = 1; d <= days; d++) {
    const k = dayKey(new Date(now.getFullYear(), now.getMonth(), d));
    const evs = all.filter(e => e.date === k);
    cells.push(`<div class="mcell${k === todayKey ? " now" : ""}"${evs.length ? ` title="${esc(evs.map(e => e.title).join(", "))}"` : ""}>
        <span class="d">${d}</span>${evs.slice(0, 3).map(() => `<span class="pip"></span>`).join("")}</div>`);
  }
  return `<div class="month">${caps}${cells.join("")}</div>`;
}
})();
