// transcript.js -- the transcript of a call, brought in from the call page and from Today (0.97.0, 2026-10-29).
// The owner asked that day for an upload control on the call prep page, and for the verbatim transcript Gemini makes to
// reach the viewer from the email Google sends. Both end in the same record (context/transcript-intake.json, written by
// skills/import-checkup/intake.py): the upload press here, and the Gemini pull a session makes. This file draws it.
//
//   BV.transcript.section(ctx)  -> HTML for "The transcript" on the call page; ctx {prep, date, meeting}
//   BV.transcript.mount(el, ctx) fills it from GET /api/call/transcript and wires the presses
//   BV.transcript.pick(ctx)      opens the file picker, uploads, resolves with the intake record (Today's press uses it)
//
// After an upload the page shows what the drop step printed (drop.py's screen) and, when a transcript was filed, the press
// that asks the session to run the import chain (POST /api/call/transcript/chain, one batch in the answers inbox).
(function (root) {
  "use strict";
  const BV = root.BV = root.BV || {};
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const clock = iso => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).toLowerCase().replace(" ", ""); };
  const dayClock = iso => { const d = new Date(iso); if (isNaN(d)) return "";
    const today = new Date().toDateString() === d.toDateString();
    return (today ? "today" : d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })) + " at " + clock(iso); };

  const CSS = `
  #transcript { scroll-margin-top: 96px; }
  .tx { background: var(--surface); border: 1px solid var(--rule-soft); border-radius: var(--radius-lg); padding: 14px 18px 16px; }
  .tx.drag { border-color: var(--accent); border-style: dashed; }
  .tx .txl { font-size: 15px; line-height: 1.5; margin: 0 0 10px; color: var(--ink); }
  .tx .txl .src { font-family: var(--font-mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--accent);
                  border: 1px solid var(--accent); border-radius: 3px; padding: 0 6px; margin-right: 8px; vertical-align: 1px; }
  .tx .txl.bad { color: var(--danger); }
  .tx .txl a { color: var(--accent-deep); }
  .tx .how { font-size: 13px; color: var(--muted); margin: 10px 0 0; line-height: 1.45; }
  .tx .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .tx .asked { font-size: 13px; color: var(--ink-soft); }
  .tx details { margin: 0 0 12px; }
  .tx details > summary { cursor: pointer; font-size: 13px; color: var(--ink-soft); }
  .tx pre.screen { font-family: var(--font-mono); font-size: 12px; line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere;
                   background: var(--bg); border: 1px solid var(--rule-soft); border-radius: var(--radius); padding: 10px 12px; margin: 8px 0 0;
                   max-height: 360px; overflow: auto; color: var(--ink); }
  .tx .msg { font-size: 13px; color: var(--muted); min-height: 1.2em; margin: 8px 0 0; }
  .tx .msg.err { color: var(--danger); }`;
  let styled = false;
  function style() {
    if (styled) return; styled = true;
    const s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s);
  }

  function readFile(file) {
    return new Promise((ok, no) => {
      const fr = new FileReader();
      fr.onload = () => ok(String(fr.result || ""));
      fr.onerror = () => no(new Error("the file could not be read"));
      fr.readAsDataURL(file);
    });
  }

  async function upload(file, ctx) {
    if (!file) throw new Error("no file chosen");
    const data = await readFile(file);
    const r = await fetch("/api/call/transcript", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prep: ctx.prep || null, date: ctx.date || null, meeting: ctx.meeting || null, name: file.name, data }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || ("the upload answered " + r.status));
    return j.intake;
  }

  // onChosen runs once a file is picked, before the upload (a cancelled picker never resolves, so the press stays as it was)
  function pick(ctx, onChosen) {
    return new Promise((ok, no) => {
      const inp = document.createElement("input");
      inp.type = "file"; inp.accept = ".txt,.md,text/plain,text/markdown"; inp.style.display = "none";
      inp.addEventListener("change", () => {
        const f = inp.files && inp.files[0]; inp.remove();
        if (!f) return no(new Error("no file chosen"));
        if (onChosen) onChosen(f);
        upload(f, ctx).then(ok, no);
      });
      document.body.appendChild(inp); inp.click();
    });
  }

  // one record as words: where it came from, and what the drop step did with it
  function verdict(r) {
    const src = r.source === "gemini" ? "pulled from Gemini" : "uploaded";
    const at = dayClock(r.at);
    if (r.code === 0 && r.filed)
      return { ok: true, html: `<span class="src">${esc(src)}</span>Filed ${esc(at)} as <a href="/reader?path=${encodeURIComponent(r.filed)}" data-open="${esc(r.filed)}">${esc(r.filed.split("/").pop())}</a>.` };
    if (r.code === 2)
      return { ok: false, html: `<span class="src">${esc(src)}</span>Not filed (${esc(at)}): that file is Gemini's notes, not the transcript. In the meeting's Google Doc, open the Transcript tab and download it as plain text.` };
    if (r.code === 3)
      return { ok: false, html: `<span class="src">${esc(src)}</span>Not filed (${esc(at)}): this call's transcript is already in the brain under the same name.` };
    return { ok: false, html: `<span class="src">${esc(src)}</span>Not filed (${esc(at)}): the drop step stopped. What it printed is below.` };
  }

  // what follows a filed transcript: the report once the chain has run, else when it was asked, else the press
  function chainHTML(path, report, asked) {
    if (report) return `<p class="asked">Read in: <a href="/reader?path=${encodeURIComponent(report)}" data-open="${esc(report)}">what came out of the call</a>.</p>`;
    if (asked) return `<p class="asked">The import chain was asked of the session ${esc(dayClock(asked))}; what came out of the call shows here once it has run.</p>`;
    return `<div class="row"><button class="press go" data-tx-chain="${esc(path)}">run the import chain</button>
             <span class="asked">The session reads the call in: summary, people, threads, and the action items to the app.</span></div>`;
  }

  function recordHTML(r, fresh) {
    const v = verdict(r);
    let h = `<p class="txl${v.ok ? "" : " bad"}">${v.html}</p>`;
    h += `<details${fresh ? " open" : ""}><summary>what the drop step printed</summary><pre class="screen">${esc(r.screen || "")}</pre></details>`;
    if (v.ok) h += chainHTML(r.filed, r.report, r.chainAsked);
    return h;
  }

  function heldHTML(t) {
    return `<p class="txl">In the brain as <a href="/reader?path=${encodeURIComponent(t.path)}" data-open="${esc(t.path)}">${esc(t.path.split("/").pop())}</a>.</p>`
      + chainHTML(t.path, t.report, null);
  }

  function section(ctx) {
    style();
    return `<h3 class="sec" id="transcript">The transcript</h3><div class="tx" data-tx><p class="msg">Reading…</p></div>`;
  }

  async function mount(el, ctx, fresh) {
    if (!el) return;
    style();
    let j = { intakes: [], enabled: true };
    try {
      const qs = new URLSearchParams({ prep: ctx.prep || "", date: ctx.date || "", meeting: ctx.meeting || "" });
      const r = await fetch("/api/call/transcript?" + qs);
      j = await r.json();
    } catch (e) { /* drawn as no record */ }
    if (!j.enabled) { el.innerHTML = `<p class="txl">This brain has no drop step beside its viewer, so a transcript is brought in by a session.</p>`; return; }
    const last = (j.intakes || [])[0];
    const filed = (j.intakes || []).some(r => r.code === 0) || !!j.held;
    el.innerHTML = (last ? recordHTML(last, fresh) : j.held ? heldHTML(j.held) : `<p class="txl">No transcript for this call yet.</p>`)
      + `<div class="row" style="margin-top:12px"><button class="press${last || j.held ? " quiet" : " go"}" data-tx-pick>${filed ? "add another file" : "add the transcript"}</button></div>`
      + `<p class="how">The plain-text transcript Gemini makes (in the meeting's Google Doc: File, Download, Plain text), or drop the file on this box. The drop step reads who spoke, files it in transcripts/ under this call's date, and turns away a notes export.</p>`
      + `<p class="msg" data-tx-msg></p>`;
    const msg = el.querySelector("[data-tx-msg]");
    const filing = f => { msg.className = "msg"; msg.textContent = "Filing " + f.name + "…"; };
    const go = async (p) => {
      try { await p; mount(el, ctx, true); }
      catch (e) { if (e.message !== "no file chosen") { msg.className = "msg err"; msg.textContent = e.message; } else msg.textContent = ""; }
    };
    el.querySelector("[data-tx-pick]").onclick = () => go(pick(ctx, filing));
    el.ondragover = e => { e.preventDefault(); el.classList.add("drag"); };
    el.ondragleave = () => el.classList.remove("drag");
    el.ondrop = e => { e.preventDefault(); el.classList.remove("drag");
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]; if (f) { filing(f); go(upload(f, ctx)); } };
    const ch = el.querySelector("[data-tx-chain]");
    if (ch) ch.onclick = async () => {
      ch.disabled = true; ch.textContent = "asking the session";
      try {
        const r = await fetch("/api/call/transcript/chain", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: ch.dataset.txChain }) });
        const k = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(k.error || ("answered " + r.status));
        mount(el, ctx, false);
      } catch (e) { ch.disabled = false; ch.textContent = "run the import chain"; msg.className = "msg err"; msg.textContent = e.message; }
    };
  }

  BV.transcript = { section, mount, pick, upload };
})(window);
