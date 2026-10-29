// Answer: the questions waiting on you, one card at a time, the blocking ones first. The owner asked on 2026-09-21
// for a place in the middle or top right to answer the top questions one by one, blocking questions first.
// A question is blocking when an OPEN TASK on its own ledger carries `blocked:` naming it, which is the same relation
// the Today page sorts by. Sending writes the answer through the same ledger call the chat page makes, and the deck
// advances by itself.
// T-0225: the deck declares its filters (project, what, about, found by, sort). /api/waiting takes no parameters, so
// every one of them is applied here, on the rows it already sends. With none set the deck is the one it always was.
(function () {
BV.widgets.register({
  id: "deck", contract: 1, title: "Answer", size: "4", defaultOn: false, card: true, rows: 2,
  source: "the open questions addressed to you on every project list, blocking ones first, or whatever its filters say (GET /api/waiting, GET /api/projects), answered back onto the ledger (PUT /api/tasks; a note on a task through POST /api/reply)",
  // the default sort is the order the deck always drew in: most held up first, then newest. "oldest", "newest" and
  // "due" are a person's choice and order by that alone, blocking kept only as the tie-break.
  filters: [
    { key: "project", label: "project", kind: "pick", options: "projects", any: "every project" },
    { key: "kind", label: "what", kind: "pick", default: "questions",
      options: [["questions", "questions"], ["tasks", "tasks"], ["both", "both"]] },
    { key: "people", label: "about", kind: "pick", options: "people", any: "anyone" },
    { key: "source", label: "found by", kind: "pick", options: "sources", any: "anyone" },
    { key: "sort", label: "sort", kind: "pick", default: "blocking",
      options: [["blocking", "blocking first"], ["oldest", "oldest first"], ["newest", "newest first"], ["due", "soonest due"]] },
  ],

  mount(el, api) {
    if (!document.getElementById("bv-deck-css")) {
      const s = document.createElement("style");
      s.id = "bv-deck-css";
      s.textContent = `
        .deck { min-height: 168px; }
        .deck .dk { transition: transform .22s ease, opacity .22s ease; }
        .deck .dk.out { transform: translateX(-18px); opacity: 0; }
        .deck .dpj { font-family: var(--font-ui); font-size: 10px; letter-spacing: .13em; text-transform: uppercase; color: var(--muted); }
        .deck .dblock { display: inline-block; margin-left: 7px; font-family: var(--font-ui); font-size: 9.5px; letter-spacing: .13em;
                        text-transform: uppercase; color: var(--blocked); border-bottom: 1px solid var(--blocked); }
        .deck .dq { font-family: var(--font-display); font-size: 16px; line-height: 1.52; margin: 9px 0 11px; }
        .deck textarea { width: 100%; padding: 8px 10px; border: 1px solid var(--rule-soft); border-radius: var(--radius);
                         background: var(--bg); resize: vertical; font-family: var(--font-ui); font-size: 14px; min-height: 62px; }
        .deck textarea:focus { outline: none; border-color: var(--accent); }
        .deck .drow { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
        .deck .dcount { margin-left: auto; font-family: var(--font-mono); font-size: 11px; color: var(--muted); }
        .deck .dmsg { font-size: 12px; color: var(--muted); margin: 7px 0 0; min-height: 1.2em; }
        .deck .dnone { font-family: var(--font-display); font-size: 15px; color: var(--muted); margin: 14px 0; }
        section.w[data-w="deck"] .whead select.wtab { border: 1px solid var(--rule-soft); border-radius: 2px;
                                                      background: var(--surface); padding: 1px 4px; max-width: 128px; }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="deck" data-deck></div>`;
    el._at = 0; el._filter = "blocking";
    api.card.addEventListener("click", e => {
      const f = e.target.closest("[data-filter]");
      if (f) { el._filter = f.dataset.filter; el._at = 0; paint(el, api); return; }
      if (e.target.closest("[data-next]")) { el._at++; slide(el, api); return; }
      if (e.target.closest("[data-send]")) { send(el, api); return; }
      if (e.target.closest("[data-done]")) { send(el, api, true); return; }
    });
    api.card.addEventListener("change", e => {
      const s = e.target.closest("[data-pjpick]"); if (!s) return;
      el._filter = s.value || "blocking"; el._at = 0; paint(el, api);
    });
    api.card.addEventListener("keydown", e => {
      const ta = e.target.closest("textarea"); if (!ta) return;
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(el, api); }
    });
    return loadAttach().then(() => this.refresh(el, api));
  },

  async refresh(el, api) {
    // a card being written in is never pulled out from under him: the read waits for the next quiet minute
    const ta = el.querySelector("textarea");
    if (ta && (ta.value.trim() || document.activeElement === ta)) return;
    let waiting, projects;
    try { waiting = await api.get("/api/waiting"); } catch (e) { return api.fail(e); }
    try { projects = await api.get("/api/projects"); } catch (e) { projects = null; }
    if (projects && BV.ledger) BV.ledger.learn(projects);   // so a T-#### in a question reads as the task it names (viewer Q-0028)
    el._s = rules(api.settings());
    el._q = questions(waiting, projects, el._s);
    // the head's "one project" pick offers the projects left after the filters, in the server's order
    const seen = new Set(el._q.map(q => q.project));
    el._projects = (waiting.groups || []).filter(g => seen.has(g.project)).map(g => ({ id: g.project, name: g.name }));
    paint(el, api);
  },
  _test: { rules: o => rules(o), questions: (w, p, o) => questions(w, p, rules(o)) },   // home.test.py reads the order here
});

// ---- the filters (T-0225) ----
// The settings a person set in edit mode, read into one object. `plain` is true when none differs from the default.
function rules(o) {
  o = o || {};
  const s = { project: o.project || "", kind: ["tasks", "both"].indexOf(o.kind) >= 0 ? o.kind : "questions",
              people: o.people || "", source: o.source || "",
              sort: ["oldest", "newest", "due"].indexOf(o.sort) >= 0 ? o.sort : "blocking" };
  s.plain = !s.project && s.kind === "questions" && !s.people && !s.source && s.sort === "blocking";
  return s;
}

// pictures on a question (T-0219): attach.js draws the thumbnails and owns the attach control and the paste, loaded once.
// If it cannot load, the deck still answers; it only loses the pictures.
function loadAttach() {
  if (window.BVAttach) return Promise.resolve();
  let tag = document.getElementById("bv-attach-js");
  if (!tag) { tag = document.createElement("script"); tag.id = "bv-attach-js"; tag.src = "/static/attach.js"; document.head.appendChild(tag); }
  return new Promise(res => { if (window.BVAttach) return res(); tag.addEventListener("load", res); tag.addEventListener("error", res); setTimeout(res, 4000); });
}

// the deck, in order: most held up first, then whatever order the server put the projects in, newest first inside one
// With filters: the tasks waiting on you come from the same /api/waiting rows (each group's `tasks`), and project,
// about and found by are tested on each row here. A task never blocks, so it sorts after the blocking questions.
function questions(waiting, projects, s) {
  s = s || rules({});
  const held = new Map();
  if (projects && typeof BV !== "undefined" && BV.day) {
    try { for (const q of BV.day.model(projects).blocking) held.set(q.project + "/" + q.id, q.holds.length); } catch (e) {}
  }
  const rows = [];
  for (const g of (waiting && waiting.groups) || []) {
    const items = (s.kind === "tasks" ? [] : g.questions || []).concat(s.kind === "questions" ? [] : g.tasks || []);
    for (const q of items) {
      const project = q.project || g.project;
      if (s.project && project !== s.project) continue;
      if (s.people && (q.people || []).indexOf(s.people) < 0) continue;
      if (s.source && q.source !== s.source) continue;
      rows.push(Object.assign({}, q, { project, projectName: g.name,
                                       blocks: q.kind === "task" ? 0 : held.get(g.project + "/" + q.id) || 0 }));
    }
  }
  const newest = (a, b) => String(b.created || "").localeCompare(String(a.created || "")) || String(b.id).localeCompare(String(a.id));
  const byDue = (a, b) => String(a.due || "9999").localeCompare(String(b.due || "9999"));
  if (s.sort === "oldest") rows.sort((a, b) => -newest(a, b) || b.blocks - a.blocks);
  else if (s.sort === "newest") rows.sort((a, b) => newest(a, b) || b.blocks - a.blocks);
  else if (s.sort === "due") rows.sort((a, b) => byDue(a, b) || b.blocks - a.blocks || newest(a, b));
  else rows.sort((a, b) => b.blocks - a.blocks || newest(a, b));
  return rows;
}

function shown(el) {
  const all = el._q || [];
  if (el._filter === "all") return all;
  if (el._filter === "blocking") { const b = all.filter(q => q.blocks); return b.length ? b : all; }
  return all.filter(q => q.project === el._filter);
}

function paint(el, api) {
  const box = el.querySelector("[data-deck]"); if (!box) return;
  const esc = api.esc, all = el._q || [], rows = shown(el);
  const blocking = all.filter(q => q.blocks).length;

  const plain = !el._s || el._s.plain;
  api.count(all.length ? all.length + " waiting" : (plain ? "clear" : "nothing matches"));
  api.head(`<button class="wtab${el._filter === "blocking" ? " on" : ""}" type="button" data-filter="blocking"${blocking ? "" : ' title="nothing is blocking work, so this shows them all"'}>blocking${blocking ? " " + blocking : ""}</button>`
    + `<button class="wtab${el._filter === "all" ? " on" : ""}" type="button" data-filter="all">all</button>`
    + (el._projects && el._projects.length > 1
      ? `<select class="wtab" data-pjpick aria-label="one project"><option value="">one project</option>`
        + el._projects.map(p => `<option value="${esc(p.id)}"${el._filter === p.id ? " selected" : ""}>${esc(p.short || p.name)}</option>`).join("")
        + `</select>` : ""));

  if (!all.length) { box.innerHTML = `<p class="dnone">${plain ? "Nothing is waiting on your answer." : "Nothing matches these filters."}</p>`; return; }
  if (!rows.length) { box.innerHTML = `<p class="dnone">Nothing waiting on that one.</p>`; return; }

  if (el._at >= rows.length) el._at = 0;
  const q = rows[el._at], task = q.kind === "task";
  const att = window.BVAttach;
  // a task is not answered: its box writes a note and leaves it open, and done closes it (the note first, if any)
  box.innerHTML = `<div class="dk" data-card data-attach-item="${esc(q.id)}" data-attach-ledger="${esc(q.project)}">
      <span class="dpj">${esc(q.projectName || q.project)}${task ? " · task" : ""}${task && q.due ? " · due " + esc(q.due) : ""}</span>${q.blocks ? `<span class="dblock" title="${esc(api.plural(q.blocks, "open task"))} on this ledger cannot move until this is answered">blocking</span>` : ""}
      <p class="dq">${BV.ledgerText(q.text, q.project)}</p>
      ${att ? att.thumbs(q.links) : ""}
      <textarea class="grow" rows="2" placeholder="${task ? "a note; the task stays open" : "answer"}" aria-label="${task ? "a note on this task" : "your answer"}"></textarea>
      <div class="drow">
        <button class="btn primary" type="button" data-send>${task ? "note" : "send"}</button>
        ${task ? `<button class="btn" type="button" data-done title="close the task, writing the note first if there is one">done</button>` : ""}
        <button class="btn" type="button" data-next title="leave it and show the next one">next</button>
        ${att ? att.control() : ""}
        <span class="dcount">${el._at + 1} of ${rows.length}</span>
      </div>
      <p class="dmsg" data-msg></p>
    </div>`;
  const ta = box.querySelector("textarea");
  if (ta) { BV.grow(ta); ta.title = "Enter for a new line, Ctrl+Enter sends"; }
}

function slide(el, api) {
  const card = el.querySelector("[data-card]");
  if (!card) return paint(el, api);
  card.classList.add("out");
  setTimeout(() => paint(el, api), 180);
}

async function send(el, api, close) {
  const box = el.querySelector("[data-deck]"), ta = box && box.querySelector("textarea");
  const msg = box && box.querySelector("[data-msg]");
  if (!ta) return;
  const text = ta.value.trim();
  const rows = shown(el), q = rows[el._at];
  if (!q) return;
  const task = q.kind === "task";
  if (!text && !(task && close)) { if (msg) msg.textContent = task ? "write the note first" : "write the answer first"; return; }
  ta.disabled = true;
  for (const b of box.querySelectorAll("button")) b.disabled = true;
  if (msg) msg.textContent = "writing it to the ledger";
  const undo = m => {
    ta.disabled = false;
    for (const b of box.querySelectorAll("button")) b.disabled = false;
    if (msg) msg.textContent = m;
  };
  if (task) {
    // a note, the same call every task row's note box makes; then, on done, the same close the checkboxes make
    if (text) { const r = await BV.replies.act(q.project, q.id, text); if (!r.ok) return undo(r.message); }
    if (!close) { ta.value = ""; el._at++; BV.refreshBadges(); return slide(el, api); }
    const r = await BV.ledgerAct(q.project, { action: "done", id: q.id });
    if (!r.ok) return undo(r.message);
  } else {
    // the same call the chat page's answer box makes
    const res = await BV.ledgerAct(q.project, { action: "answer", id: q.id, text, by: BV.owner });
    if (!res.ok) return undo(res.message);
  }
  el._q = (el._q || []).filter(r => !(r.project === q.project && r.id === q.id));
  BV.refreshBadges();
  slide(el, api);
}
})();
