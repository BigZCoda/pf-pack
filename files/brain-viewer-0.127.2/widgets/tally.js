// Tally: the three numbers the old sentence under the date carried, kept as an instrument for whoever wants them.
// Calls done of today's calls, decisions done of the ones on the clock, questions answered of the ones waiting.
// The head chooses the form: a sentence, three bars, or three numerals. The choice is saved with the board.
(function () {
const FORMS = [["sentence", "one line in words"], ["bars", "three bars, the numbers at their ends"],
               ["numerals", "three figures, big"]];
const WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"];
const word = n => (n >= 0 && n < WORDS.length ? WORDS[n] : String(n));

BV.widgets.register({
  id: "tally", contract: 1, title: "Tally", size: "4", defaultOn: false,
  source: "today's calls done, your dated work done of what is on the clock, and the questions answered of those waiting (GET /api/calls, GET /api/projects, GET /api/waiting)",

  mount(el, api) {
    if (!document.getElementById("bv-tally-css")) {
      const s = document.createElement("style");
      s.id = "bv-tally-css";
      s.textContent = `
        .ty .say { font-family: var(--font-display); font-size: 15px; line-height: 1.5; margin: 2px 0 0; color: var(--ink-soft); }
        .ty .bars { margin-top: 4px; }
        .ty .b { display: flex; gap: 10px; align-items: center; padding: 6px 0; }
        .ty .b .lb { font-family: var(--font-ui); font-size: 9.5px; letter-spacing: .13em; text-transform: uppercase;
                     color: var(--muted); width: 74px; flex: none; }
        .ty .b .track { flex: 1; min-width: 40px; height: 3px; background: var(--rule-soft); position: relative; }
        .ty .b .track i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--accent); display: block; }
        .ty .b .n { font-family: var(--font-mono); font-size: 11.5px; color: var(--muted); flex: none; }
        .ty .nums { display: flex; gap: 22px; flex-wrap: wrap; }
        .ty .nums .one { flex: 1; min-width: 78px; }
        .ty .nums .n { font-family: var(--font-title); font-weight: 500; color: var(--accent); font-size: 46px; line-height: .92; }
        .ty .nums .n .of { font-family: var(--font-mono); font-size: 13px; color: var(--muted); }
        .ty .nums .lb { font-family: var(--font-ui); font-size: 9.5px; letter-spacing: .13em; text-transform: uppercase;
                        color: var(--muted); margin-top: 6px; display: block; }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="ty" data-ty></div>`;
    api.card.addEventListener("click", e => {
      const b = e.target.closest("[data-form]"); if (!b) return;
      api.setSettings({ form: b.dataset.form });
      head(api);
      draw(el, api);
    });
    head(api);
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    const soft = p => api.get(p).then(j => j, () => null);
    const [calls, projects, waiting] = await Promise.all(
      ["/api/calls", "/api/projects", "/api/waiting"].map(soft));
    const now = Date.now();
    const evs = (calls && calls.exists && !calls.stale ? (calls.events || []) : []);
    const today = (projects && projects.today) || new Date().toISOString().slice(0, 10);
    let clock = { due: [] };
    try { clock = api.onTheClock(projects || {}); } catch (e) {}
    let taskDone = 0, asked = 0;
    for (const p of ((projects || {}).projects || [])) {
      if (!p.exists) continue;
      for (const g of p.groups || []) for (const i of g.items || []) {
        if (i.kind === "task" && i.owner === BV.owner && i.done === today) taskDone++;
        if (i.kind === "question" && i.answered === today) asked++;
      }
    }
    el._rows = [
      { label: "calls", done: evs.filter(e => new Date(e.end).getTime() < now).length, of: evs.length,
        one: "call done", many: "calls done" },
      { label: "decisions", done: taskDone, of: taskDone + clock.due.length, one: "decision done", many: "decisions done" },
      { label: "questions", done: asked, of: asked + (((waiting || {}).questions) || 0), one: "question answered", many: "questions answered" },
    ];
    draw(el, api);
  },
});

function form(api) {
  const f = (api.settings() || {}).form;
  return FORMS.some(r => r[0] === f) ? f : "sentence";
}
function head(api) {
  const on = form(api);
  api.head(FORMS.map(([id, why]) =>
    `<button class="wtab${id === on ? " on" : ""}" type="button" data-form="${id}" title="${api.esc(why)}">${id}</button>`).join(""));
}
function draw(el, api) {
  const box = el.querySelector("[data-ty]"); if (!box || !el._rows) return;
  const esc = api.esc, rows = el._rows;
  api.count(rows.map(r => r.done + " of " + r.of).join(" · "));
  if (form(api) === "bars") {
    box.innerHTML = `<div class="bars">${rows.map(r => `<div class="b">
        <span class="lb">${esc(r.label)}</span>
        <span class="track"><i style="width:${(r.of ? Math.round(100 * r.done / r.of) : 0)}%"></i></span>
        <span class="n">${r.done} of ${r.of}</span></div>`).join("")}</div>`;
    return;
  }
  if (form(api) === "numerals") {
    box.innerHTML = `<div class="nums">${rows.map(r => `<div class="one">
        <div class="n">${r.done}<span class="of"> of ${r.of}</span></div>
        <span class="lb">${esc(r.label)}</span></div>`).join("")}</div>`;
    return;
  }
  const bits = rows.map(r => `${word(r.done)} of ${r.of === 0 ? "none" : word(r.of).toLowerCase()} ${r.done === 1 ? r.one : r.many}.`);
  box.innerHTML = `<p class="say">${esc(bits.join(" "))}</p>`;
}
})();
