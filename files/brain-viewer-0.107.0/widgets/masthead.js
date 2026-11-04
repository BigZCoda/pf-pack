// The masthead: the date on the left, an instrument you choose in the middle, and the sky on the right.
// 2026-09-21: the italic sentence under the date was removed at the owner's request, and the timeline was moved to the
// top, between the day name and the sun, which is the middle slot. The slot draws one of three things and the pick is saved with the board: the DAY as a flat band from seven in
// the morning to seven at night, a PROJECT as the track of its stages, or the WEEK as seven narrow columns.
// On the right the sun carries the sessions running on this machine as dots in orbit, and beside it the moon says
// whether the night agent ran, with a phase drawn from how many of the last seven nights it did.
(function () {
const FROM = 7, TO = 19;                    // the band and the week columns both run seven to seven
const W = 640, H = 96;                      // the slot's drawing, which scales to whatever width it is given
const REPLAY_MS = 6000;                     // how long the day takes to run past when you press replay
const VIEWS = [["day", "the day as a band, with today's calls on it"],
               ["project", "one project as the track of its stages"],
               ["week", "the seven days ahead, one column each"]];

BV.widgets.register({
  id: "masthead", contract: 1, title: "The header", size: "12", defaultOn: true, head: false,
  source: "the date, the instrument you picked for the middle (GET /api/calls, GET /api/calendar/week, GET /api/projects, GET /api/stages), the sessions around the sun (GET /api/agents) and the nights the night agent ran (GET /api/moved)",

  mount(el, api) {
    if (!document.getElementById("bv-masthead-css")) {
      const s = document.createElement("style");
      s.id = "bv-masthead-css";
      s.textContent = `
        .mh { display: flex; align-items: flex-start; gap: 26px; flex-wrap: wrap; padding: 2px 0 14px; border-bottom: 1px solid var(--rule); }
        .mh .mhl { flex: none; min-width: 230px; max-width: 380px; }
        .mh .mhdate { font-family: var(--font-title); font-weight: 500; color: var(--accent); font-size: 44px; line-height: 1; margin: 0; letter-spacing: .004em; }
        .mh .mhm { flex: 1; min-width: 300px; position: relative; padding-top: 3px; }
        .mh .mhpick { position: absolute; right: 0; top: -2px; display: flex; gap: 2px; align-items: center; z-index: 1; }
        .mh .mhpick select { font-family: var(--font-ui); font-size: 11px; color: var(--muted); background: var(--surface);
                             border: 1px solid var(--rule-soft); border-radius: var(--radius); padding: 1px 4px; max-width: 170px; }
        .mh .mhpick select:focus { outline: none; border-color: var(--accent); }
        .mh svg { display: block; width: 100%; height: auto; overflow: visible; }
        .mh .cap { font-family: var(--font-ui); font-size: 9px; letter-spacing: .13em; text-transform: uppercase; fill: var(--muted); }
        .mh .cap.on { fill: var(--accent); }
        .mh .hr { font-family: var(--font-mono); font-size: 9px; fill: var(--muted); }
        .mh .hr.on { fill: var(--accent); }
        .mh .nm { font-family: var(--font-display); font-size: 12px; fill: var(--ink-soft); }
        .mh .none { color: var(--muted); font-size: 13px; margin: 18px 0 0; }
        .mh .mhr { display: flex; align-items: center; gap: 12px; flex: none; margin-left: auto; }
        .mh .mhclock { font-family: var(--font-mono); font-size: 15px; color: var(--muted); letter-spacing: .02em; white-space: nowrap; }
        .mh .sun { position: relative; width: 92px; height: 92px; flex: none; }
        .mh .sun img { position: absolute; left: 50%; top: 50%; width: 44px; height: auto; transform: translate(-50%, -50%); }
        .mh .orb { position: absolute; left: 50%; top: 50%; width: 0; height: 0; animation: bvorbit linear infinite; }
        .mh .orb a { position: absolute; display: block; width: 7px; height: 7px; margin: -3.5px 0 0 -3.5px; border-radius: 50%;
                     background: var(--accent); box-shadow: 0 0 0 3px var(--blocked-tint); }
        .mh .orb a:hover { background: var(--accent-deep); }
        .mh .moon { width: 34px; height: 34px; flex: none; }
        @keyframes bvorbit { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @media (prefers-reduced-motion: reduce) { .mh .orb { animation: none; } }
        @media (max-width: 760px) { .mh .mhdate { font-size: 32px; } .mh .sun { width: 68px; height: 68px; } .mh .mhm { min-width: 220px; } }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="mh">
        <div class="mhl"><p class="mhdate" data-date></p><div data-mantra-slot></div></div>
        <div class="mhm"><div class="mhpick" data-pick></div><div data-draw></div></div>
        <div class="mhr"><span class="mhclock" data-clock></span>
          <span class="sun" data-sun><img src="/static/sun-mark.png" alt=""></span>
          <span class="moon" data-moon></span></div>
      </div>`;
    const date = el.querySelector("[data-date]"), clock = el.querySelector("[data-clock]");
    date.textContent = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });

    clearInterval(el._clock);
    const tick = () => {
      const now = new Date();
      clock.textContent = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" }).toLowerCase();
      const d = now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
      if (d !== date.textContent) date.textContent = d;
    };
    tick();
    el._clock = setInterval(tick, 1000);
    // the now line walks the band without asking the server anything
    clearInterval(el._line);
    el._line = setInterval(() => { if (!document.hidden) moveNow(el); }, 60000);

    api.card.addEventListener("click", e => {
      if (e.target.closest("[data-replay]")) { toggleReplay(el, api); return; }
      const b = e.target.closest("[data-view]"); if (!b) return;
      stopReplay(el, api);
      api.setSettings({ view: b.dataset.view });
      el._pickKey = "";
      paint(el, api);
    });
    api.card.addEventListener("change", e => {
      const s = e.target.closest("[data-project]"); if (!s) return;
      api.setSettings({ project: s.value });
      paint(el, api);
    });
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const soft = p => api.get(p).then(j => j, () => null);
    const [calls, week, projects, stages, agents, nights] = await Promise.all(
      ["/api/calls", "/api/calendar/week", "/api/projects", "/api/stages", "/api/agents",
       "/api/moved?agent=night-agent&days=7&limit=60"].map(soft));
    el._calls = calls; el._week = week; el._projects = projects; el._stages = stages;
    paint(el, api);
    sky(el, api, agents, nights);
  },
  resize(el, api) { paint(el, api); },
});

// ---- the middle slot ----
function view(api) {
  const v = (api.settings() || {}).view;
  return VIEWS.some(r => r[0] === v) ? v : "day";
}
function paint(el, api) {
  const box = el.querySelector("[data-draw]"), pick = el.querySelector("[data-pick]");
  if (!box) return;
  const v = view(api), esc = api.esc;
  const projects = ((el._projects || {}).projects || []).filter(p => p.exists);
  const key = v + "|" + projects.map(p => p.id).join(",");
  if (pick && el._pickKey !== key) {                 // the picker is only rebuilt when it would say something new
    el._pickKey = key;
    const chosen = project(el, api);
    pick.innerHTML = VIEWS.map(([id, why]) =>
        `<button class="wtab${id === v ? " on" : ""}" type="button" data-view="${id}" title="${esc(why)}">${id}</button>`).join("")
      + (v === "day"
        ? `<button class="wtab" type="button" data-replay title="run the day past from seven in the morning to now">replay</button>`
        : "")
      + (v === "project" && projects.length
        ? `<select data-project title="which project the track follows">${projects.map(p =>
            `<option value="${esc(p.id)}"${p.id === (chosen && chosen.id) ? " selected" : ""}>${esc(p.name || p.id)}</option>`).join("")}</select>`
        : "");
  }
  if (v === "week") box.innerHTML = drawWeek(el, api);
  else if (v === "project") box.innerHTML = drawProject(el, api);
  else box.innerHTML = drawDay(el, api);
  if (v !== "day" && el._replay) stopReplay(el, api);
  markReplay(el, !!el._replay);
}

const dayKey = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const clockOf = iso => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).toLowerCase().replace(" ", ""); };
function frac(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return 0;
  return Math.max(0, Math.min(1, (d.getHours() + d.getMinutes() / 60 - FROM) / (TO - FROM)));
}
function nowFrac() {
  const d = new Date();
  return Math.max(0, Math.min(1, (d.getHours() + d.getMinutes() / 60 - FROM) / (TO - FROM)));
}
const cut = (s, n) => { s = String(s || "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s; };

// ---- the day: a flat band, the calls as blocks on it, the hours under it, a line where the hour is ----
function drawDay(el, api) {
  const esc = api.esc, calls = el._calls || {}, week = el._week || {};
  const todayKey = dayKey(new Date());
  let evs = (calls.exists && !calls.stale ? (calls.events || []) : []);
  if (!evs.length) evs = (week.events || []).filter(e => e.date === todayKey);
  const now = Date.now(), nf = nowFrac();
  const Y = 42, BH = 9, BX = 26, BW = W - 44;        // the band itself
  const px = f => BX + BW * f;
  const bits = [];
  bits.push(`<rect x="${BX}" y="${Y}" width="${(BW * nf).toFixed(1)}" height="${BH}" fill="var(--rule-soft)"></rect>`);
  bits.push(`<rect x="${px(nf).toFixed(1)}" y="${Y}" width="${(BW * (1 - nf)).toFixed(1)}" height="${BH}" fill="var(--accent)" opacity=".25"></rect>`);
  for (let h = FROM; h <= TO; h += 2) {
    const x = px((h - FROM) / (TO - FROM));
    const on = Math.abs(nf - (h - FROM) / (TO - FROM)) < 0.04;
    bits.push(`<line x1="${x.toFixed(1)}" y1="${Y + BH}" x2="${x.toFixed(1)}" y2="${Y + BH + 4}" stroke="var(--rule)" stroke-width="1"></line>`);
    bits.push(`<text class="hr${on ? " on" : ""}" x="${x.toFixed(1)}" y="${Y + BH + 15}" text-anchor="middle">${h > 12 ? h - 12 : h}${h < 12 ? "a" : "p"}</text>`);
  }
  let taken = [];
  for (const e of evs.slice().sort((a, b) => String(a.start).localeCompare(String(b.start)))) {
    const f0 = frac(e.start), f1 = Math.max(f0 + 0.015, frac(e.end));
    const x0 = px(f0), w = Math.max(6, px(f1) - x0);
    const past = new Date(e.end).getTime() < now;
    const live = new Date(e.start).getTime() <= now && new Date(e.end).getTime() >= now;
    bits.push(`<rect x="${x0.toFixed(1)}" y="${Y - 9}" width="${w.toFixed(1)}" height="${BH + 18}" rx="2"
        fill="${past ? "var(--rule-soft)" : "var(--selected)"}" stroke="${past ? "var(--muted)" : "var(--accent)"}"
        stroke-width="${live ? 2 : 1}" opacity="${past ? .7 : 1}"><title>${esc(e.title || "a call")} · ${esc(clockOf(e.start))}</title></rect>`);
    // the name over the block, lifted a row when it would land on one already written
    const text = cut(e.title || "a call", Math.max(6, Math.floor((w + 46) / 6.6)));
    let row = 0, lx = x0 + w / 2, half = text.length * 3.3;
    while (row < 3 && taken.some(t => t.row === row && lx - half < t.x1 + 5 && t.x0 < lx + half + 5)) row++;
    taken.push({ row, x0: lx - half, x1: lx + half });
    bits.push(`<text class="cap${past ? "" : " on"}" x="${lx.toFixed(1)}" y="${(Y - 15 - row * 11).toFixed(1)}" text-anchor="middle">${esc(text)}</text>`);
  }
  bits.push(`<g data-now><line x1="${px(nf).toFixed(1)}" y1="${Y - 13}" x2="${px(nf).toFixed(1)}" y2="${Y + BH + 7}" stroke="var(--open)" stroke-width="1.5"></line>
      <circle cx="${px(nf).toFixed(1)}" cy="${Y + BH / 2}" r="3.5" fill="var(--open)"></circle></g>`);
  const head = evs.length ? "" : `<text class="cap" x="${BX}" y="${Y - 16}">nothing on the calendar today</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="the day as a band" data-band data-x0="${BX}" data-w="${BW}" data-y="${Y}" data-h="${BH}">${head}${bits.join("")}</svg>`;
}
function putNow(el, f) {
  const svg = el.querySelector("svg[data-band]"); if (!svg) return;
  const g = svg.querySelector("[data-now]"); if (!g) return;
  const x0 = +svg.dataset.x0, w = +svg.dataset.w, x = x0 + w * Math.max(0, Math.min(1, f));
  const line = g.querySelector("line"), dot = g.querySelector("circle");
  if (line) { line.setAttribute("x1", x.toFixed(1)); line.setAttribute("x2", x.toFixed(1)); }
  if (dot) dot.setAttribute("cx", x.toFixed(1));
}
function moveNow(el) { if (el._replay) return; putNow(el, nowFrac()); }

// ---- the replay (0.39.0) ----
// Press it and the line walks the day again, seven in the morning to this minute, in about six seconds. Every frame
// says what time the line is standing on, and any instrument that asked for it hears that: the log lights the lines it
// passes as it passes them. Press it again and the line goes back to now. With the day strip off the slot there is
// nothing to replay, so the control is only there when the slot is drawing the day.
function toggleReplay(el, api) {
  if (el._replay) return stopReplay(el, api);
  if (!el.querySelector("svg[data-band]")) return;
  const end = nowFrac();
  const dayStart = new Date(); dayStart.setHours(FROM, 0, 0, 0);
  const spanMs = (TO - FROM) * 3600000;
  const t0 = (window.performance || Date).now();
  el._replay = true;
  markReplay(el, true);
  const step = at => {
    if (!el._replay) return;
    const k = Math.min(1, (at - t0) / REPLAY_MS);
    const f = end * k;
    putNow(el, f);
    if (api.emit) api.emit("replay", { running: true, at: f, time: dayStart.getTime() + spanMs * f });
    if (k < 1) el._raf = requestAnimationFrame(step);
    else stopReplay(el, api);
  };
  el._raf = requestAnimationFrame(step);
}
function stopReplay(el, api) {
  if (!el._replay) return;
  el._replay = false;
  cancelAnimationFrame(el._raf);
  markReplay(el, false);
  putNow(el, nowFrac());
  if (api.emit) api.emit("replay", { running: false, at: null, time: null });
}
function markReplay(el, on) {
  const b = el.querySelector("[data-replay]");
  if (!b) return;
  b.classList.toggle("on", on);
  b.textContent = on ? "stop" : "replay";
}

// ---- a project as a track of its stages ----
// GET /api/stages answers ONE ordered build order across the brain, each step carrying the project it belongs to, so a
// project with steps there is drawn from them. A project with none is drawn from its own milestones (the groups on its
// ledger, each done when everything in it is done), and one with no groups at all as a single filled bar.
function project(el, api) {
  const rows = ((el._projects || {}).projects || []).filter(p => p.exists);
  if (!rows.length) return null;
  const want = (api.settings() || {}).project;
  return rows.find(p => p.id === want) || rows.find(p => stepsOf(el, p.id).length) || rows[0];
}
function stepsOf(el, id) {
  return (((el._stages || {}).steps) || []).filter(s => s.project === id);
}
function drawProject(el, api) {
  const esc = api.esc, p = project(el, api);
  if (!p) return `<p class="none">No project has a ledger yet.</p>`;
  const steps = stepsOf(el, p.id);
  let track;
  if (steps.length) {
    track = steps.map(s => ({ name: s.short || s.text, state: s.stage, href: "/projects?id=" + encodeURIComponent(s.project) }));
  } else {
    const groups = (p.groups || []).filter(g => (g.items || []).some(i => i.kind === "task"));
    if (groups.length) {
      let current = false;
      track = groups.map(g => {
        const items = (g.items || []).filter(i => i.kind === "task");
        const done = items.every(i => i.mark === "x");
        const state = done ? "done" : (current ? "open" : (current = true, "current"));
        return { name: g.name, state, href: "/projects?id=" + encodeURIComponent(p.id) };
      });
    } else {
      const s = p.summary || {};
      track = [{ name: api.plural(s.done || 0, "thing") + " done", state: "done", href: "/projects?id=" + encodeURIComponent(p.id) },
               { name: api.plural(s.open || 0, "open"), state: "current", href: "/projects?id=" + encodeURIComponent(p.id) }];
    }
  }
  const n = track.length, BX = 26, BW = W - 52, Y = 44;
  const at = i => BX + (n === 1 ? BW / 2 : BW * i / (n - 1));
  const doneCount = track.filter(t => t.state === "done").length;
  const cur = track.find(t => t.state === "current");
  const next = track[track.indexOf(cur) + 1];
  const bits = [`<line x1="${BX}" y1="${Y}" x2="${BX + BW}" y2="${Y}" stroke="var(--rule-soft)" stroke-width="2"></line>`];
  if (doneCount) bits.push(`<line x1="${BX}" y1="${Y}" x2="${at(Math.max(0, Math.min(n - 1, doneCount - 1))).toFixed(1)}" y2="${Y}" stroke="var(--accent)" stroke-width="2"></line>`);
  track.forEach((t, i) => {
    const x = at(i), r = t.state === "current" ? 7 : 4.5;
    const fill = t.state === "done" ? "var(--accent)" : t.state === "current" ? "var(--open)" : "var(--surface)";
    bits.push(`<circle cx="${x.toFixed(1)}" cy="${Y}" r="${r}" fill="${fill}" stroke="${t.state === "open" ? "var(--rule)" : "none"}" stroke-width="1"><title>${esc(t.name)}</title></circle>`);
  });
  const say = cur ? cut(cur.name, 52) : "every step is done";
  const after = next ? "next, " + cut(next.name, 40) : "";
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(p.name || p.id)} as a track of its stages">
      <text class="cap" x="${BX}" y="20">${esc(cut(p.name || p.id, 34))}</text>
      <text class="hr" x="${BX + BW}" y="20" text-anchor="end">${doneCount} of ${n}</text>
      ${bits.join("")}
      <text class="nm" x="${BX}" y="${Y + 26}">${esc(say)}</text>
      <text class="hr" x="${BX + BW}" y="${Y + 26}" text-anchor="end">${esc(after)}</text>
    </svg>`;
}

// ---- the week: seven narrow columns ----
function drawWeek(el, api) {
  const esc = api.esc, week = el._week || {};
  const todayKey = dayKey(new Date());
  const evs = (week.events || []);
  if (!evs.length && !week.exists) return `<p class="none">No week has been written. The next session start writes it.</p>`;
  const start = new Date(); start.setHours(0, 0, 0, 0);
  const BX = 22, BW = W - 40, colW = BW / 7, Y0 = 30, Y1 = H - 14;
  const cols = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(start.getTime() + i * 86400000), k = dayKey(d);
    const x = BX + colW * i, inner = colW - 8;
    const mine = evs.filter(e => e.date === k);
    const today = k === todayKey;
    cols.push(`<line x1="${x.toFixed(1)}" y1="${Y0 - 8}" x2="${(x + inner).toFixed(1)}" y2="${Y0 - 8}" stroke="${today ? "var(--accent)" : "var(--rule-soft)"}" stroke-width="${today ? 2 : 1}"></line>`);
    cols.push(`<text class="cap${today ? " on" : ""}" x="${x.toFixed(1)}" y="${Y0 - 14}">${esc(d.toLocaleDateString(undefined, { weekday: "short" }).toLowerCase())} ${d.getDate()}</text>`);
    for (const e of mine) {
      const f0 = frac(e.start), f1 = Math.max(f0 + 0.03, frac(e.end));
      const y = Y0 + (Y1 - Y0) * f0, h = Math.max(5, (Y1 - Y0) * (f1 - f0));
      cols.push(`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${inner.toFixed(1)}" height="${h.toFixed(1)}" rx="2"
          fill="${today ? "var(--selected)" : "var(--surface)"}" stroke="var(--accent)" stroke-width="1"><title>${esc(e.title || "a call")} · ${esc(clockOf(e.start))}</title></rect>`);
    }
    if (!mine.length) cols.push(`<line x1="${x.toFixed(1)}" y1="${((Y0 + Y1) / 2).toFixed(1)}" x2="${(x + inner).toFixed(1)}" y2="${((Y0 + Y1) / 2).toFixed(1)}" stroke="var(--rule-soft)" stroke-width="1" stroke-dasharray="2 4"></line>`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="the seven days ahead">${cols.join("")}</svg>`;
}

// ---- the sky: the sessions in orbit, and the moon ----
function sky(el, api, agents, nights) {
  const sun = el.querySelector("[data-sun]"), moon = el.querySelector("[data-moon]");
  if (sun) {
    for (const o of Array.from(sun.querySelectorAll(".orb"))) o.remove();
    const live = ((agents && agents.sessions) || []).filter(s => s.active);
    const R = sun.clientWidth >= 80 ? 36 : 27;
    live.slice(0, 10).forEach((s, i) => {
      const o = document.createElement("span");
      o.className = "orb";
      o.style.animationDuration = (22 + i * 5) + "s";
      o.style.animationDelay = "-" + (i * 2.4) + "s";
      const a = document.createElement("a");
      a.href = "/chat#running";   // 0.66.0: the agents page folded into the chat
      a.style.left = R + "px";
      a.style.top = "0";
      a.title = (s.title || "a session") + ((s.counts && s.counts.running) ? " · " + api.plural(s.counts.running, "sub-agent") + " running" : "");
      o.appendChild(a);
      sun.appendChild(o);
    });
    sun.title = live.length ? api.plural(live.length, "session") + " running on this machine" : "nothing running on this machine";
  }
  if (!moon) return;
  const rows = (nights && nights.items) || [];
  const seen = new Set(rows.map(r => r.day));
  const n = Math.min(7, seen.size);
  const yesterday6 = new Date(); yesterday6.setDate(yesterday6.getDate() - 1); yesterday6.setHours(18, 0, 0, 0);
  const ranLastNight = rows.some(r => new Date(r.at).getTime() >= yesterday6.getTime());
  const f = ranLastNight ? Math.max(0.08, n / 7) : 0;
  const R = 12;
  moon.innerHTML = `<svg viewBox="-16 -16 32 32" role="img" aria-label="the nights the night agent ran">
      <circle cx="0" cy="0" r="${R}" fill="var(--rule-soft)" stroke="var(--rule)" stroke-width="1" opacity="${ranLastNight ? .55 : .35}"></circle>
      ${f > 0 ? `<path d="${moonPath(R, f)}" fill="var(--open)"></path>` : ""}
    </svg>`;
  moon.title = (ranLastNight ? "the night agent ran last night" : "the night agent did not run last night")
    + " · " + api.plural(n, "night") + " of the last seven";
}
// the lit part of a disc: the right half of the circle, closed by an ellipse whose width is how far from half full it is
function moonPath(r, f) {
  const rx = (r * Math.abs(1 - 2 * f)).toFixed(2);
  return `M 0 ${-r} A ${r} ${r} 0 0 1 0 ${r} A ${rx} ${r} 0 0 ${f > 0.5 ? 1 : 0} 0 ${-r} Z`;
}
})();
