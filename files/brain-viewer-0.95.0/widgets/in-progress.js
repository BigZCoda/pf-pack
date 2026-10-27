// In progress: the work being made right now, one row per project, the newest activity first, so its files are one press
// away instead of a hunt through the brain. A project and its files are registered by the session making them
// (skills/in-progress/progress.py writes context/in-progress.json); the server resolves it all and leaves the brain's own
// process files out, so this file draws and never parses. A row opens in place onto its files (newest first, each opening
// in the Reader, the preview page or the picture viewer), the ledger items it answers to in their own words, and its note.
// Under the projects, "Other recent work": the files the log says were made or changed in the last week that belong to
// no project.
(function () {
BV.widgets.register({
  id: "in-progress", contract: 1, title: "In progress", size: "6", defaultOn: true,
  source: "the projects being worked on and their files, as the sessions making them registered them (context/in-progress.json), and the other files changed this week, process files left out (GET /api/in-progress)",
  mount(el, api) {
    if (!document.getElementById("bv-in-progress-css")) {
      const s = document.createElement("style");
      s.id = "bv-in-progress-css";
      s.textContent = css();
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="ip" data-ip></div>`;
    el.addEventListener("click", e => {
      const b = e.target.closest("button[data-ipid]"); if (!b) return;
      const open = el._ipOpen || (el._ipOpen = new Set()), id = b.dataset.ipid;
      if (open.has(id)) open.delete(id); else open.add(id);
      const inside = b.parentElement.querySelector(".inside");
      if (inside) inside.hidden = !open.has(id);
      b.setAttribute("aria-expanded", String(open.has(id)));
      const car = b.querySelector(".car"); if (car) car.textContent = open.has(id) ? "▾" : "▸";
    });
    el.addEventListener("toggle", e => { if (e.target.matches && e.target.matches("details[data-ipother]")) el._ipOther = e.target.open; }, true);
    return this.refresh(el, api);
  },
  async refresh(el, api) {
    let d;
    try { d = await api.get("/api/in-progress"); } catch (e) { return api.fail(e); }
    draw(el, api, d || {});
  },
});


function stateWord(i) {
  return i.missing ? "not found" : i.kind === "question" ? (i.state === "answered" ? "answered" : "question")
    : (i.state === "done" ? "done" : i.state === "blocked" ? "blocked" : "task");
}

function fileLine(f, api) {
  const esc = api.esc;
  return `<div class="f${f.exists ? "" : " gone"}"><a href="${esc(f.href)}" title="${esc(f.path)}">${esc(f.name)}</a>`
    + `${f.folder ? `<span class="dir">${esc(f.folder)}</span>` : ""}<span class="t">${esc(f.exists ? api.when(f.at) : "missing")}</span></div>`;
}

function draw(el, api, d) {
  const esc = api.esc;
  const box = el.querySelector("[data-ip]"); if (!box) return;
  const open = el._ipOpen || (el._ipOpen = new Set());
  const projects = d.projects || [];
  api.count(projects.length ? api.plural(projects.length, "project") : "nothing registered");
  const rows = projects.map(p => {
    const last = (p.files || [])[0];
    const on = open.has(p.id);
    return `<div class="proj"><button type="button" class="row" data-ipid="${esc(p.id)}" aria-expanded="${on}">
        <span class="car">${on ? "▾" : "▸"}</span><span class="nm">${esc(p.name)}</span><span class="lt">${esc(api.plural(p.count || 0, "file"))}</span>
        <span class="sub">${last ? `${esc(last.name)} · ${esc(api.when(last.at || p.lastActivity))}` : `nothing yet · ${esc(api.when(p.lastActivity))}`}</span></button>
      <div class="inside"${on ? "" : " hidden"}>
        ${p.thread ? `<p class="thr">thread: <a href="${esc(p.thread.href)}">${esc(p.thread.name)}</a></p>` : ""}
        ${(p.files || []).map(f => fileLine(f, api)).join("") || `<p class="none">No files registered yet.</p>`}
        ${(p.items || []).length ? `<p class="lbl">On the ledgers</p>${p.items.map(i => `<div class="it"><span class="st">${esc(stateWord(i))}</span>${esc(api.clip(i.text, 170))}</div>`).join("")}` : ""}
        ${p.note ? `<p class="note">${esc(p.note)}</p>` : ""}
      </div></div>`;
  }).join("");
  const done = (d.done || []).length
    ? `<p class="finished">Finished this week: ${d.done.map(p => `${esc(p.name)} (${esc(api.when(p.doneAt))})`).join(", ")}</p>` : "";
  const recent = d.recent || [];
  const other = recent.length
    ? `<details class="other" data-ipother${el._ipOther ? " open" : ""}><summary>Other recent work · ${recent.length} file${recent.length === 1 ? "" : "s"} from the last ${d.recentDays || 7} days</summary>
        <div class="list">${recent.map(f => fileLine(f, api)).join("")}</div></details>` : "";
  box.innerHTML = (rows || `<p class="none">Nothing is registered as in progress. A session that starts work registers it with skills/in-progress/progress.py.</p>`)
    + done + other;
}

function css() {
  return `
  .ip { display: flex; flex-direction: column; gap: 2px; }
  .ip .row { display: grid; grid-template-columns: 14px 1fr auto; gap: 8px; align-items: baseline; width: 100%; padding: 6px 4px; text-align: left;
             background: none; border: 0; border-top: 1px solid var(--rule-soft); color: var(--ink); font: inherit; cursor: pointer; border-radius: 0; }
  .ip .proj:first-child .row { border-top: 0; }
  .ip .row:hover { background: var(--hover); }
  .ip .row .car { font-size: 10px; color: var(--muted); }
  .ip .row .nm { font-family: var(--font-display); font-size: 15px; min-width: 0; }
  .ip .row .lt { font-size: 12px; color: var(--muted); white-space: nowrap; }
  .ip .row .sub { grid-column: 2 / 4; font-size: 12px; color: var(--muted); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ip .inside { padding: 2px 4px 10px 26px; }
  .ip .inside[hidden] { display: none; }
  .ip .f { display: flex; gap: 8px; align-items: baseline; padding: 3px 0; min-width: 0; font-size: 13px; }
  .ip .f a { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ip .f .dir { font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; flex: 0 1 auto; }
  .ip .f .t { margin-left: auto; font-family: var(--font-mono); font-size: 10.5px; color: var(--muted); flex: none; }
  .ip .f.gone a { color: var(--muted); text-decoration: line-through; }
  .ip .lbl { margin: 9px 0 3px; font-family: var(--font-ui); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
  .ip .it { font-size: 13px; padding: 2px 0; color: var(--ink-soft); }
  .ip .it .st { font-size: 11px; color: var(--muted); margin-right: 6px; }
  .ip .note { margin: 8px 0 0; font-size: 12.5px; color: var(--ink-soft); }
  .ip .thr { margin: 0 0 6px; font-size: 12.5px; color: var(--muted); }
  .ip .finished { margin: 8px 0 0; font-size: 12px; color: var(--muted); }
  .ip details.other { margin-top: 8px; border-top: 1px solid var(--rule-soft); padding-top: 6px; }
  .ip details.other > summary { cursor: pointer; font-size: 12.5px; color: var(--muted); list-style: none; }
  .ip details.other > summary::-webkit-details-marker { display: none; }
  .ip details.other > summary::before { content: "\\25B8 "; font-size: 10px; }
  .ip details.other[open] > summary::before { content: "\\25BE "; }
  .ip details.other .list { padding: 4px 0 0 12px; }
  .ip .none { color: var(--muted); font-size: 13px; margin: 0; }
`;
}
})();
