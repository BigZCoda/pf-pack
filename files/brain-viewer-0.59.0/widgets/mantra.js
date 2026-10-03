// Mantra: one line a day, under the date. The line is picked from the date itself, so it is the same line all day on
// every machine and turns over at midnight. The pool is a plain file anyone on the team can add a line to
// (projects/pf-build/pf-mantras.md); add here writes into it, and next shows another of today's lines without moving
// the day's pick. When the masthead is on the board this draws into the room the masthead keeps under the date;
// switched off there, it takes a line of its own.
(function () {
BV.widgets.register({
  id: "mantra", contract: 1, title: "Mantra", size: "12", defaultOn: true, head: false,
  source: "one line a day from the pool anyone on the team can add to, picked from the date (GET /api/mantras, POST /api/mantras)",

  mount(el, api) {
    if (!document.getElementById("bv-mantra-css")) {
      const s = document.createElement("style");
      s.id = "bv-mantra-css";
      s.textContent = `
        .mn { margin: 9px 0 0; max-width: 62ch; }
        .mn .line { font-family: var(--font-display); font-style: italic; font-size: 16px; line-height: 1.45; color: var(--ink-soft); }
        .mn .who { font-family: var(--font-ui); font-size: 9.5px; letter-spacing: .13em; text-transform: uppercase;
                   color: var(--muted); margin-left: 9px; white-space: nowrap; font-style: normal; }
        .mn .ctl { display: inline-flex; gap: 4px; margin-left: 8px; vertical-align: 1px; opacity: 0; transition: opacity .2s ease; }
        .mn:hover .ctl, .mn .ctl:focus-within { opacity: 1; }
        .mn .ctl button { border: 0; background: none; cursor: pointer; padding: 0 3px; color: var(--muted);
                          font-family: var(--font-ui); font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase; }
        .mn .ctl button:hover { color: var(--accent); }
        .mn form { display: flex; gap: 6px; margin-top: 7px; flex-wrap: wrap; align-items: center; }
        .mn form[hidden] { display: none; }
        .mn form input { padding: 4px 8px; border: 1px solid var(--rule-soft); border-radius: var(--radius);
                         background: var(--bg); font: inherit; font-size: 13px; }
        .mn form input.text { flex: 1; min-width: 190px; }
        .mn form input.who { min-width: 110px; font-family: var(--font-ui); font-size: 13px; letter-spacing: 0;
                             text-transform: none; color: var(--ink); margin: 0; }
        .mn .said { font-size: 11.5px; color: var(--muted); margin-left: 6px; }
      `;
      document.head.appendChild(s);
    }
    // the masthead keeps a slot under the date; with the masthead off the board this draws in its own row instead
    const slot = document.querySelector("[data-mantra-slot]");
    el._box = document.createElement("div");
    el._box.className = "mn";
    if (slot) { slot.innerHTML = ""; slot.appendChild(el._box); api.show(false); }
    else { el.innerHTML = ""; el.appendChild(el._box); api.show(true); }
    // the controls are named data-mantra-*: the board itself claims [data-add] for "put this instrument back on the
    // board", so a bare data-add here re-rendered the whole page on every press
    el._box.addEventListener("click", e => {
      if (e.target.closest("[data-mantra-next]")) { el._turn = (el._turn || 0) + 1; return paint(el, api); }
      if (e.target.closest("[data-mantra-add]")) {
        const f = el._box.querySelector("form");
        if (f) { f.hidden = !f.hidden; if (!f.hidden) f.querySelector("input").focus(); }
      }
    });
    el._box.addEventListener("submit", async e => {
      e.preventDefault();
      const f = e.target, text = f.querySelector(".text").value.trim(), who = f.querySelector(".who").value.trim();
      if (!text) return;
      const note = f.querySelector("[data-said]");
      try {
        const r = await fetch("/api/mantras", { method: "POST", headers: { "Content-Type": "application/json" },
                                                body: JSON.stringify({ text, author: who }) });
        const j = await r.json();
        if (!r.ok || j.error) throw new Error(j.error || ("the server answered " + r.status));
        f.reset(); f.hidden = true;
        if (note) note.textContent = j.proposed ? "filed as a request" : "added";
        el._pool = null;
        await this.refresh(el, api);
      } catch (x) { if (note) note.textContent = "not added: " + x.message; }
    });
    if (!api.settings().source) api.setSettings({ source: "pool" });
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    if (!el._box) return;
    let j;
    try { j = await api.get("/api/mantras"); } catch (e) { j = null; }
    el._pool = j;
    paint(el, api);
  },
});

// the day's pick: the date's own number, so every machine shows the same line and it turns over at midnight
function pick(day, n) {
  if (!n) return 0;
  let h = 0;
  for (let i = 0; i < day.length; i++) h = (h * 31 + day.charCodeAt(i)) >>> 0;
  return h % n;
}
function paint(el, api) {
  const box = el._box; if (!box) return;
  const esc = api.esc, j = el._pool || {};
  const items = j.items || [];
  const day = j.today || new Date().toISOString().slice(0, 10);
  const add = j.canAdd !== false;
  if (!items.length) {
    box.innerHTML = `<p class="line">${esc(j.exists === false ? "The mantra pool is empty." : "")}</p>`;
    return;
  }
  const it = items[(pick(day, items.length) + (el._turn || 0)) % items.length];
  box.innerHTML = `<p class="line">${esc(it.text)}${it.author ? `<span class="who">${esc(it.author)}</span>` : ""}
      <span class="ctl">
        <button type="button" data-mantra-next title="another line for today, without changing the day's pick">next</button>
        ${add ? `<button type="button" data-mantra-add title="add a line to the pool everyone draws from">add</button>` : ""}
      </span><span class="said" data-said></span></p>
    ${add ? `<form hidden>
        <input class="text" type="text" maxlength="400" placeholder="the line" aria-label="the line">
        <input class="who" type="text" maxlength="120" placeholder="who said it" aria-label="who said it">
        <button class="btn" type="submit">add</button>
      </form>` : ""}`;
}
})();
