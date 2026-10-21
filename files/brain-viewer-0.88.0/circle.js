// circle.js (0.73.0, the extended circle's second round): "their circle" under a holder's card, and the opportunities a
// card is on, drawn on the People page, in the person drawer and on a card's front in the Reader.
// The data is GET /api/circle (the two machine-written circle files, served as one answer). It is read after the page's
// first paint, never before it; a brain with no circle files answers present false and every piece here draws nothing.
// The three edits a press may make (a row's one line, an opportunity's stage, its next move) go through
// POST /api/circle/edit, which writes the file and one log line; they are offered only where the caller asks (the drawer).
window.BVC = (function () {
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const STAGE_WORD = { "heard-of": "heard of", "in-conversation": "in conversation", offered: "offered", live: "live", dead: "dead" };
  const STAGE_BADGE = { "heard-of": "open", "in-conversation": "draft", offered: "draft", live: "ok", dead: "held" };
  const stageBadge = st => `<span class="badge ${STAGE_BADGE[st] || "open"}" title="the stage">${esc(STAGE_WORD[st] || st || "no stage")}</span>`;
  const shortDate = d => d ? `${+String(d).slice(5, 7)}/${String(d).slice(8, 10)}` : "";
  const SRC_WORD = { report: "intake report", contact: "app contact", onboarding: "onboarding record", ledger: "ledger item", subject: "thread" };
  let ALL = null, ALL_AT = 0;
  // the section's own look, once per page; every color and font comes from the tokens
  (function style() {
    if (document.getElementById("bv-circle-css")) return;
    const st = document.createElement("style"); st.id = "bv-circle-css";
    st.textContent = `
      details.circle { margin: 4px 0 8px 22px; border-left: 2px solid var(--rule-soft); padding: 2px 0 2px 10px; }
      details.circle > summary { cursor: pointer; list-style: none; font-family: var(--font-ui); font-size: 13px; color: var(--ink-soft); }
      details.circle > summary::-webkit-details-marker { display: none; }
      details.circle > summary::before { content: "▸ "; color: var(--muted); font-size: 11px; }
      details.circle[open] > summary::before { content: "▾ "; }
      details.circle > summary .meta { margin-left: 6px; font-size: 12px; }
      details.circle.indrawer { margin: 0 0 14px; border-left-color: var(--accent); }
      details.circle.indrawer > summary { font-family: var(--font-display); font-size: 16px; color: var(--ink); }
      ul.circle { list-style: none; padding: 0; margin: 6px 0 0; }
      ul.circle li.crow { padding: 6px 0; border-top: 1px dotted var(--rule-soft); }
      ul.circle li.crow:first-child { border-top: 0; }
      .crow .chead { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
      .crow .cn { font-weight: 600; }
      .crow .ckind { font-size: 11.5px; }
      .crow .csrc { margin-left: auto; font-size: 12px; }
      .crow .cwhat { color: var(--ink-soft); font-size: 13.5px; margin: 2px 0 0; display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
      .crow .copps, ul.opplines li { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; margin: 3px 0 0; font-size: 13px; }
      .crow .copp { display: inline-flex; gap: 6px; align-items: baseline; flex-wrap: wrap; margin-right: 12px; }
      ul.opplines { list-style: none; padding: 0; margin: 0 0 10px; }
      ul.opplines li { padding: 4px 0; border-top: 1px dotted var(--rule-soft); }
      .cnext { font-size: 12px; }
      form.cedit { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; width: 100%; margin: 4px 0; }
      form.cedit input { flex: 1; min-width: 200px; padding: 4px 8px; border: 1px solid var(--rule-soft); border-radius: var(--radius); background: var(--surface); }
      form.cedit select { padding: 4px 6px; border: 1px solid var(--rule-soft); border-radius: var(--radius); background: var(--surface); }
`;
    document.head.appendChild(st);
  })();

  async function load(through) {
    const r = await fetch("/api/circle" + (through ? `?through=${encodeURIComponent(through)}` : ""));
    if (!r.ok) return { present: false, rows: [], opportunities: [], cardOpps: [], holders: {} };
    return r.json();
  }
  // the whole circle, once per page view (the People page groups it by holder itself)
  async function all(force) {
    if (!ALL || force || Date.now() - ALL_AT > 60000) { ALL = await load(); ALL_AT = Date.now(); }
    return ALL;
  }
  const rowsFor = (data, slug) => ((data && data.rows) || []).filter(r => (r.through || []).includes(slug));
  const isHolder = (data, slug) => !!(data && data.holders && data.holders[slug]);

  function sourceLink(r) {
    const s = (r.sources || [])[0];
    if (!s || !s.path) return "";
    const word = SRC_WORD[s.kind] || s.kind || "source";
    return `<a class="csrc" href="/reader?path=${encodeURIComponent(s.path)}" title="${esc(s.path)}">${esc(word)}${s.date ? ` · ${esc(shortDate(s.date))}` : ""}</a>`;
  }
  function oppChip(o, edit) {
    return `<span class="copp" data-opp="${esc(o.id)}"><a href="/opportunities" title="the opportunities page">${esc(o.title)}</a>${stageBadge(o.stage)}`
      + (edit ? `<button type="button" class="btn tiny" data-circle-edit="opp" data-id="${esc(o.id)}" title="move the stage or set the next move">edit</button>` : "")
      + (o.next ? `<span class="meta cnext">next: ${esc(o.next)}</span>` : "") + `</span>`;
  }
  function rowHTML(r, edit) {
    const name = r.card ? `<a class="n" href="/people?open=${encodeURIComponent(r.card)}" data-slug="${esc(r.card)}">${esc(r.name)}</a>` : `<span class="cn">${esc(r.name)}</span>`;
    const opps = (r.opps || []).map(o => oppChip(o, edit)).join("");
    return `<li class="crow" data-row="${esc(r.slug)}">
      <div class="chead">${name}<span class="meta ckind">${esc(r.kind || "")}</span>${sourceLink(r)}</div>
      <div class="cwhat"><span class="cw">${esc(r.what || "")}</span>${edit ? `<button type="button" class="btn tiny" data-circle-edit="row" data-slug="${esc(r.slug)}" title="change this one line">edit</button>` : ""}</div>
      ${opps ? `<div class="copps">${opps}</div>` : ""}</li>`;
  }
  // the folded section: "Their circle", one row per circle row this card holds. Empty string when there is none.
  function section(rows, opts = {}) {
    if (!rows || !rows.length) return "";
    const n = rows.length;
    return `<details class="circle${opts.cls ? " " + opts.cls : ""}"${opts.open ? " open" : ""}><summary>Their circle <span class="meta">${n} ${n === 1 ? "person or company" : "people and companies"} reachable through ${esc(opts.name || "them")}</span></summary>
      <ul class="circle">${rows.map(r => rowHTML(r, !!opts.edit)).join("")}</ul><p class="status-line" data-circle-status></p></details>`;
  }
  const loading = (cls) => `<details class="circle${cls ? " " + cls : ""}" data-circle-loading><summary>Their circle <span class="meta">loading…</span></summary></details>`;
  // the opportunities a card is on: one line each, linking to the opportunities page
  function oppLines(opps, opts = {}) {
    if (!opps || !opps.length) return "";
    return `<ul class="opplines">${opps.map(o => `<li data-opp="${esc(o.id)}"><a href="/opportunities" title="the opportunities page">${esc(o.title)}</a>${stageBadge(o.stage)}`
      + (opts.edit ? `<button type="button" class="btn tiny" data-circle-edit="opp" data-id="${esc(o.id)}" title="move the stage or set the next move">edit</button>` : "")
      + (o.next ? `<span class="meta cnext">next: ${esc(o.next)}</span>` : "") + `</li>`).join("")}</ul><p class="status-line" data-circle-status></p>`;
  }

  // ---- the edit press: the press opens a small form in place; save writes through the server, cancel puts it back ----
  function form(kind, el, data) {
    if (kind === "row") {
      const cur = el.querySelector(".cw") ? el.querySelector(".cw").textContent : "";
      return `<form class="cedit" data-kind="row" data-slug="${esc(data.slug)}"><input name="what" value="${esc(cur)}" maxlength="300" required>
        <button class="btn primary" type="submit">save</button><button class="btn" type="button" data-circle-cancel>cancel</button></form>`;
    }
    const o = data.opp || {};
    return `<form class="cedit" data-kind="opportunity" data-id="${esc(o.id)}"><select name="stage">${Object.keys(STAGE_WORD).map(s => `<option value="${s}"${s === o.stage ? " selected" : ""}>${STAGE_WORD[s]}</option>`).join("")}</select>
      <input name="next" value="${esc(o.next || "")}" maxlength="200" placeholder="the next move, and whose">
      <button class="btn primary" type="submit">save</button><button class="btn" type="button" data-circle-cancel>cancel</button></form>`;
  }
  // wire(root, {find: id -> opportunity, onDone}) once per page; the presses carry what they edit
  function wire(root, cfg) {
    root.addEventListener("click", e => {
      const b = e.target.closest("[data-circle-edit]");
      if (b) {
        e.preventDefault(); e.stopPropagation();
        const host = b.closest(b.dataset.circleEdit === "row" ? ".cwhat" : "[data-opp]");
        if (!host || host.querySelector("form.cedit")) return;
        const opp = b.dataset.id ? (cfg.find(b.dataset.id) || { id: b.dataset.id }) : null;
        host.insertAdjacentHTML("beforeend", form(b.dataset.circleEdit, host, { slug: b.dataset.slug, opp }));
        const f = host.querySelector("form.cedit"); const i = f.querySelector("input,select"); if (i) i.focus();
        return;
      }
      const c = e.target.closest("[data-circle-cancel]");
      if (c) { e.preventDefault(); e.stopPropagation(); c.closest("form.cedit").remove(); }
    }, true);
    root.addEventListener("submit", async e => {
      const f = e.target.closest("form.cedit"); if (!f) return;
      e.preventDefault(); e.stopPropagation();
      const body = f.dataset.kind === "row" ? { kind: "row", slug: f.dataset.slug, what: f.what.value }
                                            : { kind: "opportunity", id: f.dataset.id, stage: f.stage.value, next: f.next.value };
      const st = f.closest(".circle, .openblock, .circlebox") && f.closest(".circle, .openblock, .circlebox").querySelector("[data-circle-status]");
      const btn = f.querySelector("button[type=submit]"); btn.disabled = true;
      try {
        const r = await fetch("/api/circle/edit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const j = await r.json();
        if (!r.ok) { if (st) st.textContent = "refused: " + (j.error || r.status); btn.disabled = false; return; }
        if (st) st.textContent = j.unchanged ? "nothing changed" : "saved";
        ALL = null;
        if (cfg.onDone) await cfg.onDone(j);
      } catch (err) { if (st) st.textContent = "could not save: " + err.message; btn.disabled = false; }
    }, true);
  }

  return { load, all, rowsFor, isHolder, section, loading, oppLines, wire, stageBadge, STAGE_WORD };
})();
