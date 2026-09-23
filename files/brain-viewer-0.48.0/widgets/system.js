// System: a lamp for every part of this brain that runs on its own, and when it last ran. The calendar read, the week
// file, the sync with the ProspectForge app, the night agent, the weekly librarian, git, and this app itself.
// Lit means it ran inside its own rhythm, dim means it has missed one turn, red means it is overdue or has never run.
// Blocked and overdue work is NOT here: that is work, not a fault, and it lives in Decide and on the day page.
(function () {
BV.widgets.register({
  id: "system", contract: 1, title: "System", size: "12", defaultOn: true,
  source: "every part of this brain that runs on its own, with the last time each one ran (GET /api/system)",

  mount(el, api) {
    if (!document.getElementById("bv-system-css")) {
      const s = document.createElement("style");
      s.id = "bv-system-css";
      s.textContent = `
        .sy { display: flex; gap: 8px 26px; flex-wrap: wrap; align-items: flex-start; }
        .sy .lamp { display: flex; gap: 8px; align-items: baseline; min-width: 118px; }
        .sy .lamp .dot { width: 9px; height: 9px; border-radius: 50%; flex: none; position: relative; top: 1px; }
        .sy .lamp.lit .dot { background: var(--done); }
        .sy .lamp.dim .dot { background: var(--open); }
        .sy .lamp.red .dot { background: var(--danger); }
        .sy .lamp .nm { font-family: var(--font-ui); font-size: 9.5px; letter-spacing: .13em; text-transform: uppercase;
                        color: var(--muted); display: block; }
        .sy .lamp.red .nm { color: var(--danger); }
        .sy .lamp .ago { font-family: var(--font-mono); font-size: 11px; color: var(--ink-soft); display: block; margin-top: 2px; }
        .sy .lamp.red .ago { color: var(--danger); }
        .sy .none { color: var(--muted); font-size: 13px; }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="sy" data-sy></div>`;
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const box = el.querySelector("[data-sy]"); if (!box) return;
    const esc = api.esc;
    let j;
    try { j = await api.get("/api/system"); } catch (e) { return api.fail(e); }
    const lamps = j.lamps || [];
    // the widgets lamp (T-0217) is a break, not a missed run, so the count names it apart from the overdue ones
    const wl = lamps.find(l => l.id === "widgets"), wred = wl && wl.state === "red";
    const late = (j.red || 0) - (wred ? 1 : 0);
    api.count(lamps.length ? ([late ? late + " overdue" : "", wred ? "a widget broken" : ""].filter(Boolean).join(" · ") || "all running") : "");
    if (!lamps.length) { box.innerHTML = `<p class="none">Nothing runs on its own in this copy.</p>`; return; }
    box.innerHTML = lamps.map(l => `<span class="lamp ${esc(l.state)}" title="${esc(title(l))}">
        <span class="dot"></span>
        <span><span class="nm">${esc(l.name)}</span><span class="ago">${esc(l.id === "widgets" ? (l.state === "red" ? (l.broken || []).length + " broken" : "all whole") : ago(l.lastRan))}</span></span>
      </span>`).join("");
  },
});

function title(l) {
  if (l.id === "widgets") return [l.name, "every tile on the home board, watched while this app runs", l.detail].filter(Boolean).join(" · ");
  const rhythm = l.cadence === "weekly" ? "every week" : l.cadence === "daily" ? "every day" : "every session";
  return [l.name, rhythm, l.detail].filter(Boolean).join(" · ");
}
function ago(iso) {
  if (!iso) return "never";
  const t = new Date(iso);
  if (isNaN(t)) return "never";
  const mins = Math.round((Date.now() - t.getTime()) / 60000);
  if (mins < 2) return "just now";
  if (mins < 60) return mins + " m ago";
  if (mins < 60 * 20) return Math.round(mins / 60) + " h ago";
  const days = Math.round(mins / 60 / 24);
  if (days <= 6) return t.toLocaleDateString(undefined, { weekday: "short" });
  return t.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
})();
