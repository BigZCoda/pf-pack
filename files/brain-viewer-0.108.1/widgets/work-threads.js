// Threads (work-threads.js; the id `threads` is the older Call threads widget): every piece of work that runs across the ledgers (one per subject file), the ones with the most waiting on the
// owner first, then the most recently active. A row says how much is open for the owner and in all, and when the next
// call with one of its people is; it opens the thread page. Read from GET /api/threads, which does all the counting.
(function () {
BV.widgets.register({
  id: "work-threads", contract: 1, title: "Threads", size: "6", defaultOn: true,
  source: "every subject file as a thread: what is open for you and in all, and the next call with its people (GET /api/threads)",
  mount(el, api) {
    if (!document.getElementById("bv-threads-css")) {
      const s = document.createElement("style");
      s.id = "bv-threads-css";
      s.textContent = css();
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="thw" data-thw></div>`;
    return this.refresh(el, api);
  },
  async refresh(el, api) {
    const box = el.querySelector("[data-thw]"); if (!box) return;
    let d;
    try { d = await api.get("/api/threads"); } catch (e) { return api.fail(e); }
    const esc = api.esc;
    const rows = (d.threads || []).slice().sort((a, b) => (b.forOwner || 0) - (a.forOwner || 0) || String(b.last || "").localeCompare(String(a.last || "")));
    const mine = rows.reduce((n, r) => n + (r.forOwner || 0), 0);
    api.count(rows.length ? `${api.plural(rows.length, "thread")} · ${mine} for you` : "none yet");
    box.innerHTML = (rows.map(r => `<a class="row" href="${esc(r.href)}" title="${esc(r.subject)}">
        <span class="nm">${esc(r.name)}</span><span class="lt">${r.forOwner || 0} for you · ${r.open || 0} in all</span>
        <span class="sub">${r.nextCall ? esc(callWords(r.nextCall.start)) + (r.nextCall.title ? ` · ${esc(api.clip(r.nextCall.title, 48))}` : "") : "no call set"}</span></a>`).join("")
      || `<p class="none">No subject files yet. The transcript intake writes them under projects/*/subjects/.</p>`)
      + `<a class="all" href="/threads">all threads</a>`;
  },
});

// "Tue 10/06 09:00": the weekday computed from the date, never written from memory
function callWords(iso) {
  const t = new Date(iso);
  if (isNaN(t)) return String(iso || "");
  const p = n => String(n).padStart(2, "0");
  return `${t.toLocaleDateString("en-US", { weekday: "short" })} ${p(t.getMonth() + 1)}/${p(t.getDate())} ${p(t.getHours())}:${p(t.getMinutes())}`;
}

// the In progress widget's row, so the two halves of the board read alike
function css() {
  return `
  .thw { display: flex; flex-direction: column; gap: 2px; }
  .thw .row { display: grid; grid-template-columns: 1fr auto; gap: 2px 8px; align-items: baseline; padding: 6px 4px; border-top: 1px solid var(--rule-soft);
              color: var(--ink); text-decoration: none; }
  .thw .row:first-child { border-top: 0; }
  .thw .row:hover { background: var(--hover); }
  .thw .row .nm { font-family: var(--font-display); font-size: 15px; min-width: 0; }
  .thw .row .lt { font-size: 12px; color: var(--muted); white-space: nowrap; }
  .thw .row .sub { grid-column: 1 / 3; font-size: 12px; color: var(--muted); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .thw .all { margin-top: 6px; font-size: 12px; color: var(--muted); }
  .thw .none { color: var(--muted); font-size: 13px; margin: 0; }
`;
}
})();
