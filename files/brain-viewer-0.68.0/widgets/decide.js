// Decide: what is on the clock today, and the way to answer the rest.
// The owner said on 2026-09-21 that the old rows could not be read or answered here, and asked for today's decisions
// plus a link to the place where the next questions are answered. So it no longer shows the three soonest, which put
// Wednesday's work in front of the owner on a Monday and cut every line to a stub: it shows only what is due today or already behind, in full
// readable text, each line a way into that item on the day page. The app's review queue stays as the foot.
(function () {
const LINES = 3;                 // how many lines of text a row may wrap to before it is cut at a word

BV.widgets.register({
  id: "decide", contract: 1, title: "Decide", size: "4", defaultOn: false,
  source: "your open tasks due today or already behind, or whatever its filters say (GET /api/projects), and what the app is holding for review (GET /api/today/tasks)",
  // T-0214: the rules a person can put on it in edit mode, saved in its settings. The defaults are the board it always was.
  filters: [
    { key: "project", label: "project", kind: "pick", options: "projects", any: "every project" },
    { key: "owner", label: "owner", kind: "pick", options: "owners", any: "yours" },
    { key: "due", label: "due", kind: "pick", default: "today",
      options: [["today", "today or behind"], ["week", "this week"], ["all", "any day, or none"]] },
    { key: "tag", label: "tag", kind: "pick", options: "tags", any: "any tag" },
    { key: "people", label: "about", kind: "pick", options: "people", any: "anyone" },
    { key: "source", label: "found by", kind: "pick", options: "sources", any: "anyone" },
    { key: "sort", label: "sort", kind: "pick", default: "due",
      options: [["due", "soonest first"], ["project", "by project"], ["newest", "newest first"]] },
  ],

  mount(el, api) {
    if (!document.getElementById("bv-decide-css")) {
      const s = document.createElement("style");
      s.id = "bv-decide-css";
      s.textContent = `
        .dec .row { display: flex; gap: 10px; align-items: baseline; padding: 9px 0; border-top: 1px solid var(--rule-soft); }
        .dec .row:first-child { border-top: 0; padding-top: 2px; }
        .dec .row .txt { flex: 1; min-width: 0; font-family: var(--font-display); font-size: 14px; line-height: 1.45;
                         display: -webkit-box; -webkit-line-clamp: ${LINES}; -webkit-box-orient: vertical; overflow: hidden;
                         overflow-wrap: break-word; }
        .dec .row a.txt { color: var(--ink); text-decoration: none; }
        .dec .row a.txt:hover { color: var(--accent); }
        .dec .pill { flex: none; font-family: var(--font-mono); font-size: 10.5px; letter-spacing: .04em; padding: 1px 7px;
                     border-radius: 2px; border: 1px solid var(--rule-soft); color: var(--muted); background: var(--surface); white-space: nowrap; }
        .dec .pill.late { color: var(--danger); border-color: var(--danger); background: var(--danger-tint); }
        .dec .pill.soon { color: var(--accent); border-color: var(--accent); }
        .dec .next { margin: 10px 0 0; padding-top: 7px; border-top: 1px solid var(--rule-soft); font-size: 13px; }
        .dec .foot { margin: 7px 0 0; font-size: 12.5px; }
        .dec .none { font-family: var(--font-display); color: var(--muted); font-size: 14px; margin: 6px 0; }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="dec" data-dec></div>`;
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const box = el.querySelector("[data-dec]"); if (!box) return;
    const esc = api.esc;
    let j;
    try { j = await api.get("/api/projects"); } catch (e) { return api.fail(e); }
    // the board's one count of what carries a day (api.onTheClock, 0.37.1): open tasks of the owner with a due day, a
    // held one left out until it comes back. `due` is the part of that on the clock today or already behind it, which
    // is now the whole of what this draws.
    const clock = api.onTheClock(j);
    const today = clock.today, s = rules(api.settings());
    // with no filter set this is exactly the board's one count (api.onTheClock); a filter reads the ledgers itself
    const due = s.plain ? clock.due : pick(j, s, today);
    api.count(due.length ? api.plural(due.length, s.plain ? "on the clock" : "item") : (s.plain ? "nothing today" : "nothing matches"));

    box.innerHTML = (due.length
      ? due.map(r => `<div class="row">
          <a class="txt" href="/today" title="${esc(r.projectName)} · due ${esc(r.due || "no day")}">${esc(r.text)}</a>
          <span class="pill ${r.due ? cls(r.due, today) : ""}">${esc(r.due ? dayWord(r.due, today) : "no day")}</span>
        </div>`).join("")
      : `<p class="none">${s.plain ? "Nothing due today." : "Nothing matches these filters."}</p>`)
      + `<p class="next"><a href="/today">the next things to answer</a></p>`;

    // the app's review queue is a different pile on a different machine, so it is counted on its own line
    try {
      const a = (await api.get("/api/today/tasks?app=1")).app || {};
      if (a.count != null) box.insertAdjacentHTML("beforeend",
        `<p class="foot"><a href="/today" title="the queue the app is holding">the app is holding ${esc(api.plural(a.count, "item"))} for review</a></p>`);
    } catch (e) {}
  },
});

// ---- the filters (T-0214) ----
// The settings a person set in edit mode, read into one object. `plain` is true when none differs from the default,
// which is the case the board's shared count answers.
function rules(o) {
  o = o || {};
  const s = { project: o.project || "", owner: o.owner || "", due: ["week", "all"].indexOf(o.due) >= 0 ? o.due : "today",
              tag: o.tag || "", people: o.people || "", source: o.source || "",
              sort: ["project", "newest"].indexOf(o.sort) >= 0 ? o.sort : "due" };
  s.plain = !s.project && !s.owner && s.due === "today" && !s.tag && !s.people && !s.source && s.sort === "due";
  return s;
}
// the open tasks the rules let through, by the same test api.onTheClock uses for "open": a blank mark, and a held one
// left out until its day comes back
function pick(j, s, today) {
  const owner = s.owner || BV.owner, week = isoAdd(today, 6), out = [];
  for (const p of (j && j.projects) || []) {
    if (!p.exists || (s.project && p.id !== s.project)) continue;
    for (const g of p.groups || []) for (const i of g.items || []) {
      if (i.kind !== "task" || i.mark !== " ") continue;
      if (i.until && i.until > today) continue;
      if (owner !== "*" && i.owner !== owner) continue;
      if (s.due === "today" && !(i.due && i.due <= today)) continue;
      if (s.due === "week" && !(i.due && i.due <= week)) continue;
      if (s.tag && (i.tags || []).indexOf(s.tag) < 0) continue;
      if (s.people && (i.people || []).indexOf(s.people) < 0) continue;
      if (s.source && i.source !== s.source) continue;
      out.push(Object.assign({}, i, { projectName: p.name || p.id, project: p.id }));
    }
  }
  const byDue = (a, b) => String(a.due || "9999").localeCompare(String(b.due || "9999")) || String(a.id).localeCompare(String(b.id));
  if (s.sort === "project") out.sort((a, b) => String(a.projectName).localeCompare(String(b.projectName)) || byDue(a, b));
  else if (s.sort === "newest") out.sort((a, b) => String(b.created || "").localeCompare(String(a.created || "")) || byDue(a, b));
  else out.sort(byDue);
  return out.slice(0, MAX_ROWS);
}
const MAX_ROWS = 12;             // a wide filter (any day, anyone) could name hundreds; the tile carries this many
function isoAdd(day, n) {
  const d = new Date(day + "T12:00:00"); d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const days = (a, b) => Math.round((new Date(b + "T12:00:00") - new Date(a + "T12:00:00")) / 86400000);

function cls(due, today) {
  if (due < today) return "late";
  return due === today ? "soon" : "";
}
function dayWord(due, today) {
  const n = days(today, due);
  if (n === 0) return "today";
  if (n < 0) return -n === 1 ? "a day late" : (-n) + " days late";
  return new Date(due + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }).toLowerCase();
}
})();
