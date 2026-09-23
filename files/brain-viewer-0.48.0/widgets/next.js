// Next: the call in front of you. What it is, when it is in plain words, who is on it, and two presses: join the call,
// and open the prep on the call screen (/call). Under it, one quiet line for the call after that.
// 0.39.0, Zak: "when the call prep gets generated that becomes clickable." Both calendar endpoints carry the preps
// written for each event, joined by the one matcher on the server (preps_for_event).
// 0.47.0, Zak, 9/23, after the 09:00 team call with no way into it from here: "if im supposed to be on the call at a
// certain period of time, it should show up on the home page meeting widget and allow me to click on it to get to the
// call prep." and "Where is the call? Give me a place to click on it." So a call is the hero from the morning of its day
// until 30 minutes after it ends, then the next one takes over; the join URL is the event's own (`join` in the calendar
// files), and a call with no prep offers to write one (POST /api/prep for that event) and opens it.
(function () {
const AFTER_MS = 30 * 60000;      // a call stays in front of you this long after it ends

BV.widgets.register({
  id: "next", contract: 1, title: "Next", size: "8", defaultOn: true,
  source: "the call in front of you from the calendar files the night agent and the session start write, with its people, its join link and the prep written for it (GET /api/calendar/week, GET /api/calls)",

  mount(el, api) {
    if (!document.getElementById("bv-next-css")) {
      const s = document.createElement("style");
      s.id = "bv-next-css";
      s.textContent = `
        .nx { display: flex; gap: 14px 22px; align-items: flex-end; flex-wrap: wrap; }
        .nx .nl { min-width: 0; flex: 1 1 280px; }
        .nx .nt { font-family: var(--font-title); font-weight: 500; color: var(--accent); font-size: 32px; line-height: 1.04; margin: 0; }
        .nx .nw { font-family: var(--font-mono); font-size: 13px; color: var(--muted); margin: 6px 0 0; }
        .nx .nw .d { color: var(--ink); }
        .nx .nw .d.live { color: var(--accent); font-weight: 600; }
        .nx .who { display: flex; align-items: center; gap: 12px; margin: 10px 0 0; flex-wrap: wrap; }
        .nx .faces { display: inline-flex; }
        .nx .face { width: 27px; height: 27px; border-radius: 50%; border: 1px solid var(--rule); background: var(--surface);
                    color: var(--ink-soft); font-family: var(--font-ui); font-size: 10.5px; letter-spacing: .04em;
                    display: inline-flex; align-items: center; justify-content: center; margin-right: -6px; }
        .nx .names { color: var(--ink-soft); font-size: 13px; }
        .nx .nr { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .nx .press { display: inline-block; text-decoration: none; font-family: var(--font-ui); font-size: 12px;
                     letter-spacing: .12em; text-transform: uppercase; padding: 10px 16px; border-radius: var(--radius);
                     border: 1px solid var(--accent); color: var(--accent); background: transparent; cursor: pointer; }
        .nx .press.go { background: var(--accent); color: var(--bg); }
        .nx .press:hover { background: var(--hover); color: var(--accent-deep); }
        .nx .press.go:hover { background: var(--accent-deep); color: var(--bg); }
        .nx .press[disabled] { opacity: .6; cursor: default; }
        .nx .after { flex-basis: 100%; margin: 10px 0 0; padding-top: 7px; border-top: 1px solid var(--rule-soft);
                     color: var(--muted); font-size: 12.5px; display: flex; gap: 10px; align-items: baseline; }
        .nx .after .t { font-family: var(--font-mono); font-size: 11px; flex: none; }
        .nx .after a { color: inherit; }
        .nx .none { font-family: var(--font-display); color: var(--muted); font-size: 14px; margin: 4px 0; }
        .nx .err { color: var(--danger); font-size: 12.5px; flex-basis: 100%; margin: 4px 0 0; }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="nx" data-nx></div>`;
    clearInterval(el._tick);
    el._tick = setInterval(() => { if (!document.hidden) count(el); }, 30000);
    el.onclick = e => {
      const b = e.target.closest("[data-write]");
      if (!b) return;
      e.preventDefault();
      writePrep(el, b);
    };
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const box = el.querySelector("[data-nx]"); if (!box) return;
    const esc = api.esc;
    const soft = p => api.get(p).then(j => j, () => null);
    const [week, calls] = await Promise.all([soft("/api/calendar/week"), soft("/api/calls")]);
    const todayKey = key(new Date());
    const today = (calls && calls.exists && !calls.stale ? (calls.events || []) : []).map(e => Object.assign({ date: calls.for || todayKey }, e));
    // the day's own file wins for today's events (it carries the join link the session start read); the week file for the rest
    const rest = ((week || {}).events || []).filter(e => e.date !== todayKey || !today.length);
    const all = today.concat(rest).sort((a, b) => String(a.start).localeCompare(String(b.start)));
    const now = Date.now();
    const next = all.find(e => endOf(e) + AFTER_MS >= now);
    if (!next) {
      api.count(week && week.exists ? "nothing ahead" : "no calendar");
      box.innerHTML = `<p class="none">${esc(week && week.exists ? "Nothing more on the calendar." : "No calendar has been written. The next session start writes it.")}</p>`;
      return;
    }
    const after = all.filter(e => e !== next && new Date(e.start).getTime() > new Date(next.start).getTime())[0];
    const nToday = all.filter(e => e.date === todayKey).length;
    api.count(nToday ? api.plural(nToday, "call") + " today" : "none today");

    // the join link and the prep: the event's own first, the day file's row for the same start as the fallback
    const twin = (((calls || {}).events) || []).find(e => e.start === next.start) || {};
    const join = next.join || twin.join || "";
    const prep = (next.preps && next.preps.length ? next.preps : twin.preps) || [];
    const people = (next.people || next.attendees || []).filter(p => !(p && p.self)).map(p => p.name || p).filter(Boolean);
    const carded = (next.people || twin.people || []).some(p => p && p.slug);
    const faces = people.slice(0, 6).map(n => `<span class="face" title="${esc(n)}">${esc(initials(n))}</span>`).join("");
    const names = people.slice(0, 4).join(", ") + (people.length > 4 ? " and " + (people.length - 4) + " more" : "");
    const at = next.date === todayKey ? clockOf(next.start) : dayName(next.date) + " " + clockOf(next.start);
    const prepPress = prep[0]
      ? `<a class="press" href="/call?prep=${encodeURIComponent(prep[0].path)}">open the prep</a>`
      : carded ? `<button class="press" data-write="${esc(next.start)}" data-title="${esc(next.title || "")}">no prep yet, write one</button>` : "";
    box.innerHTML = `<div class="nl"><p class="nt">${esc(next.title || "a call")}</p>
        <p class="nw" data-when data-start="${esc(next.start)}" data-end="${esc(next.end || "")}" data-at="${esc(at)}">${whenHTML(next, at, esc)}</p>
        ${people.length ? `<div class="who"><span class="faces">${faces}</span><span class="names">${esc(names)}</span></div>` : ""}</div>
      <div class="nr">${join ? `<a class="press go" href="${esc(join)}" target="_blank" rel="noopener">join the call</a>` : ""}${prepPress}</div>
      ${after ? `<p class="after"><span class="t">${esc(after.date === todayKey ? clockOf(after.start) : dayName(after.date) + " " + clockOf(after.start))}</span>
        <span>${esc(api.clip(after.title || "a call", 70))}</span></p>` : ""}`;
  },
});

async function writePrep(el, b) {
  b.disabled = true;
  const was = b.textContent;
  b.textContent = "writing the prep";
  try {
    const r = await fetch("/api/prep", { method: "POST", headers: { "Content-Type": "application/json" },
                                         body: JSON.stringify({ event_start: b.dataset.write, purpose: b.dataset.title || "" }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || !j.path) throw new Error(j.error || ("the prep writer answered " + r.status));
    location.href = j.call || ("/call?prep=" + encodeURIComponent(j.path));
  } catch (e) {
    b.disabled = false;
    b.textContent = was;
    const box = el.querySelector("[data-nx]");
    if (box) { const p = document.createElement("p"); p.className = "err"; p.textContent = String(e.message || e); box.appendChild(p); }
  }
}

const endOf = e => { const t = new Date(e.end || e.start).getTime(); return isNaN(t) ? new Date(e.start).getTime() : t; };
const key = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const clockOf = iso => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).toLowerCase().replace(" ", ""); };
function dayName(iso) {
  const d = new Date(iso + "T12:00:00");
  return isNaN(d) ? String(iso) : d.toLocaleDateString(undefined, { weekday: "long" }) + " " + (d.getMonth() + 1) + "/" + d.getDate();
}
function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}
// the distance in plain words: "in 40 min", "now", "ended 20 min ago"
function span(m) {
  if (m < 60) return m + " min";
  const h = Math.floor(m / 60), rm = m % 60;
  if (h < 24) return h + (h === 1 ? " hour" : " hours") + (rm ? " " + rm + " min" : "");
  const d = Math.floor(h / 24), rh = h % 24;
  return d + (d === 1 ? " day" : " days") + (rh ? " " + rh + (rh === 1 ? " hour" : " hours") : "");
}
function distance(startIso, endIso) {
  const now = Date.now(), s = new Date(startIso).getTime();
  const e = new Date(endIso || startIso).getTime();
  if (!isNaN(s) && now < s) return { text: "in " + span(Math.max(1, Math.round((s - now) / 60000))), live: false };
  if (!isNaN(e) && now <= e) return { text: "now", live: true };
  return { text: "ended " + span(Math.max(1, Math.round((now - (isNaN(e) ? s : e)) / 60000))) + " ago", live: false };
}
function whenHTML(ev, at, esc) {
  const d = distance(ev.start, ev.end);
  return `<span class="d${d.live ? " live" : ""}">${esc(d.text)}</span> · ${esc(at)}`;
}
function count(el) {
  const w = el.querySelector("[data-when]");
  if (!w || !w.dataset.start) return;
  const d = distance(w.dataset.start, w.dataset.end);
  const s = w.querySelector(".d");
  if (s) { s.textContent = d.text; s.classList.toggle("live", d.live); }
}
})();
