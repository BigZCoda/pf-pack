// Moved: what changed in the brain, newest first, in the words of whoever changed it. The brain's log is append-only
// and every agent writes one line per action into it, so this is the honest record of the last few hours rather than
// a summary of one. Grouped by the hour it happened in.
// 0.39.0: it listens for the header's day replay. While the now line walks the day again, every line the line passes
// lights as it is passed and the list follows it, so the two instruments read as one day being played back.
(function () {
BV.widgets.register({
  id: "moved", contract: 1, title: "Moved", size: "6", defaultOn: true,
  fillRows: 19,                             // free mode: the log scrolls in a working height (380px unless the height is set)
  source: "the tail of the brain's own log, newest first, grouped by the hour, narrowed by its filters (GET /api/moved)",
  // T-0214: the rules a person can put on it in edit mode. Days 0 is the board it always was: today, or the last of
  // what there was when today is still empty. A project keeps the lines that name its id or its folder.
  filters: [
    { key: "agent", label: "who", kind: "pick", options: "agents", any: "every agent" },
    { key: "days", label: "days back", kind: "range", min: 0, max: 14, step: 1, default: 0, zero: "today" },
    { key: "project", label: "project", kind: "pick", options: "projects", any: "every project" },
  ],

  mount(el, api) {
    if (!document.getElementById("bv-moved-css")) {
      const s = document.createElement("style");
      s.id = "bv-moved-css";
      s.textContent = `
        .mv { max-height: 330px; overflow: auto; padding-right: 4px; position: relative; }
        .mv .hour { font-family: var(--font-ui); font-size: 9.5px; letter-spacing: .13em; text-transform: uppercase;
                    color: var(--muted); margin: 11px 0 4px; }
        .mv .hour:first-child { margin-top: 0; }
        .mv .ln { position: relative; padding: 3px 0 3px 19px; display: flex; gap: 9px; align-items: baseline; min-width: 0; }
        .mv .ln::before { content: ""; position: absolute; left: 4px; top: 0; bottom: 0; width: 1px; background: var(--rule-soft); }
        .mv .ln:first-of-type::before { top: 9px; }
        .mv .ln.last::before { bottom: auto; height: 9px; }
        .mv .ln .dot { position: absolute; left: 1px; top: 8px; width: 7px; height: 7px; border-radius: 50%;
                       background: var(--surface); border: 1px solid var(--rule); }
        .mv .ln.fresh .dot { background: var(--accent); border-color: var(--accent); }
        .mv .ln.lit { background: var(--selected); }
        .mv .ln.lit .dot { background: var(--open); border-color: var(--open); }
        .mv .ln.lit .x { color: var(--accent); }
        .mv .ln .t { font-family: var(--font-mono); font-size: 10.5px; color: var(--muted); flex: none; }
        .mv .ln .x { flex: 1; min-width: 0; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .mv .none { color: var(--muted); font-size: 13px; }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="mv" data-mv></div>`;
    if (api.on) api.on("replay", d => replay(el, d));
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const box = el.querySelector("[data-mv]"); if (!box) return;
    const esc = api.esc;
    const d = new Date(); d.setHours(0, 0, 0, 0);
    const since = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T00:00`;
    const o = api.settings() || {};
    const agent = String(o.agent || ""), back = Math.max(0, Math.min(14, parseInt(o.days, 10) || 0)), proj = String(o.project || "");
    // a project filter is applied here, so it reads the widest window and keeps forty of what matches
    const lim = proj ? 200 : 40;
    const who = agent ? "&agent=" + encodeURIComponent(agent) : "";
    let j;
    try {
      j = await api.get(back ? `/api/moved?limit=${lim}&days=${back}${who}` : `/api/moved?limit=${lim}&since=${encodeURIComponent(since)}${who}`);
    } catch (e) { return api.fail(e); }
    // nothing today means the day has not started yet, not that nothing ever happened: show the last of what there was
    if (!back && !(j.items || []).length) { try { j = await api.get(`/api/moved?limit=${lim}${who}`); } catch (e) {} }
    let items = j.items || [];
    if (proj) {
      let path = "";
      try { const pj = await api.get("/api/projects"); path = ((pj.projects || []).find(p => p.id === proj) || {}).path || ""; } catch (e) {}
      const dir = path.replace(/[^/]+$/, "").toLowerCase(), id = proj.toLowerCase();
      items = items.filter(r => { const x = String(r.text || "").toLowerCase(); return x.indexOf(id) >= 0 || (dir && x.indexOf(dir) >= 0); }).slice(0, 40);
    }
    api.count(items.length ? api.plural(items.length, "thing") : "nothing yet");
    if (!items.length) { box.innerHTML = `<p class="none">Nothing has moved.</p>`; return; }

    const fresh = Date.now() - 45 * 60000;
    let hour = "", out = [];
    items.forEach((r, i) => {
      const h = r.at.slice(0, 13);
      if (h !== hour) {
        hour = h;
        out.push(`<p class="hour">${esc(hourLabel(r))}</p>`);
      }
      const at = new Date(r.at).getTime();
      out.push(`<div class="ln${at >= fresh ? " fresh" : ""}${i === items.length - 1 ? " last" : ""}"${isNaN(at) ? "" : ` data-at="${at}"`}>
          <span class="dot"></span><span class="t">${esc(r.time)}</span>
          <span class="x" title="${esc(r.agent + " " + r.action.toLowerCase())}: ${esc(r.text)}">${esc(api.clip(say(r), 200))}</span></div>`);
    });
    box.innerHTML = out.join("");
  },
});

// ---- the header's replay, heard here ----
// One frame says what time the line is standing on. Everything between the last frame's time and this one has just
// been passed, so it lights for a moment and the list scrolls to it; the end of the run puts every line back.
function replay(el, d) {
  const box = el.querySelector("[data-mv]"); if (!box) return;
  if (!d || !d.running || d.time == null) {
    el._replayAt = null;
    for (const n of box.querySelectorAll(".ln.lit")) n.classList.remove("lit");
    return;
  }
  const prev = el._replayAt == null ? d.time - 1 : el._replayAt;
  el._replayAt = d.time;
  for (const n of box.querySelectorAll(".ln[data-at]")) {
    const t = +n.dataset.at;
    if (!(t > prev && t <= d.time)) continue;
    n.classList.add("lit");
    clearTimeout(n._off);
    n._off = setTimeout(() => n.classList.remove("lit"), 1500);
    box.scrollTop = Math.max(0, n.offsetTop - box.clientHeight / 2);
  }
}

function hourLabel(r) {
  const d = new Date(r.at);
  if (isNaN(d)) return r.at;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const h = d.toLocaleTimeString([], { hour: "numeric" }).toLowerCase().replace(" ", "");
  return d < today ? d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }).toLowerCase() + " " + h : h;
}
// the log line as a person reads it: no file path in front, no ledger id, just what happened
function say(r) {
  let t = String(r.text || "");
  t = t.replace(/^[a-z0-9._\-/]+\.(md|json|py|js|canvas|txt)\s+--\s+/i, "");
  t = t.replace(/\b[QT]-\d{4}\b\s*/g, "");
  t = t.replace(/\s*\[found by [^\]]+\]\s*$/i, "");
  return t.replace(/\s+/g, " ").trim() || String(r.action || "").toLowerCase();
}
})();
