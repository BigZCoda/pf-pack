// workspace.js -- one ledger item's workspace, drawn by the Thread page when it focuses an item and by the bare /work page
// for an item that belongs to no thread (0.64.0, 2026-10-05). The blocks read GET /api/work; the presses are the Today
// queue's (the pages wire the same data- attributes the Today page does); Brief me / Refresh start POST /api/brief/run and
// ask GET /api/brief/status every three seconds until the brief lands. Layout lives in viewer-tokens.css (.ws-*).
window.BVWork = (function () {
  const esc = BV.esc;
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
  const md = iso => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || "")); return m ? `${+m[2]}/${+m[3]}` : ""; };
  const clipWords = (s, n) => { s = String(s || ""); return s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, "") + "…" : s; };
  const whoWord = w => w === BV.owner ? "you" : w === "@claude" ? "Claude" : String(w || "").replace(/^@/, "");
  const localDay = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
  const ago = iso => { const t = new Date(iso); if (isNaN(t)) return ""; const m = Math.round((Date.now() - t) / 60000);
    return m < 60 ? `${Math.max(m, 0)}m ago` : m < 1440 ? `${Math.round(m / 60)}h ago` : t.toLocaleDateString(undefined, { month: "short", day: "numeric" }); };
  const dayWord = iso => { const t = new Date(iso); return isNaN(t) ? "" : t.toLocaleDateString(undefined, { weekday: "short", month: "numeric", day: "numeric" }); };
  const timeWord = iso => { const t = new Date(iso); return isNaN(t) ? "" : t.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).toLowerCase().replace(" ", ""); };

  // ---- a row with the Today queue's presses ----
  // opts.open: a link to the item's own workspace (or, with opts.focusHref, the same page focused on it)
  function row(i, opts = {}) {
    const p = i.project, isQ = i.kind === "question", who = i.who || (isQ ? (i.to || BV.owner) : i.owner);
    const meta = [`<span class="badge">${esc(i.label || p)}</span>`, `<span>${esc(isQ ? "asked of " + whoWord(who) : whoWord(who))}</span>`];
    const late = i.due && i.due < localDay();
    if (i.due) meta.push(`<span class="badge${late || i.due === localDay() ? " overdue" : ""}">${i.due === localDay() ? "due today" : "due " + esc(md(i.due))}</span>`);
    meta.push(`<span title="written ${esc(i.created)}">${esc(md(i.created))}</span>`);
    meta.push(BV.personChips(i));
    if (opts.open) meta.push(`<a class="worklink" href="${esc(opts.focusHref ? opts.focusHref(i) : BV.workHref(i, p))}"${opts.focusHref ? ` data-focus="${esc(p + "/" + i.id)}"` : ""}>workspace</a>`);
    const holds = i.holdsUp || [], waits = i.waitsOn || [];
    const rel = (cls, kick, list) => list.length ? `<div class="rel ${cls}"><span class="kicker">${kick}</span>${list.map(x => BV.ledgerText(x.text, x.project)).join("; ")}</div>` : "";
    let press = "", below = "";
    const open = isQ ? i.mark === "?" : i.mark !== "x";
    const survey = isQ && BV.survey.href(i, p);
    const pick = isQ && !survey && BV.pick.href(i, p);
    if (open && survey && who === BV.owner) {
      press = BV.survey.press(i, p);    // 0.78.0: a survey opens its own page, in place of the choices and the box
    } else if (open && pick && who === BV.owner) {
      // 0.79.0: a pick leads with Compare, which opens it on its options side by side; on the page that already shows
      // the comparison (opts.pickShown) the band above holds its presses and its box, so the row carries none
      press = opts.pickShown ? "" : BV.pick.press(i, p);
    } else if (open && isQ && who === BV.owner) {
      const ch = BV.choices(i);
      press = ch ? ch.map(c => `<button type="button" class="btn choice" data-qchoice="${esc(c)}" data-q="${esc(i.id)}" data-project="${esc(p)}">${esc(c)}</button>`).join("")
                   : "";
      below = `<form class="qbox" data-q="${esc(i.id)}" data-project="${esc(p)}"><textarea class="grow" rows="1" placeholder="${ch ? "or answer in your own words" : "answer"}" title="Enter for a new line, Ctrl+Enter sends" required></textarea><button class="btn primary" type="submit">Answer</button></form>`;
    } else if (open && !isQ) {
      const allTicked = BV.steps.complete(i);     // 0.86.0: once every step is ticked, done is the lead press
      press = `<button type="button" class="btn done${allTicked ? " primary" : ""}" data-qdone="${esc(i.id)}" data-project="${esc(p)}" title="${allTicked ? "every step is ticked: close it on its own ledger" : "close it on its own ledger"}">done</button>`
            + (i.mark === " " && !i.until ? `<button type="button" class="btn" data-hold="${esc(i.id)}" data-project="${esc(p)}" title="put it down for three days; it comes back on its own, still open">hold</button>` : "")
            + `<button type="button" class="btn" data-qnote="1" title="reply; the item stays open">reply</button>`   // 0.94.0: reply, not note
            + BV.shareItem.press(i, p);   // 0.98.0: share with the member, when her copy holds this task's list
      below = `<div class="qnote" hidden>${BV.replies.box(Object.assign({}, i, { ledger: i.ledger }), p)}</div>`;
    }
    const kind = isQ ? (survey ? "survey" : pick ? "pick" : BV.choices(i) && i.mark === "?" ? "decision" : "question") : "task";
    return `<li class="ws-row${holds.length ? " holding" : ""}${opts.focused ? " focused" : ""}" data-key="${esc(p + "/" + i.id)}">${BV.idTag(i.id, i.ledger)}
      <span class="qk">${kind}</span>
      <div class="body">
        <div class="t">${BV.ledgerText(i.text, p)}</div>
        ${BV.kind.line(i, p)}
        ${rel("frees", "frees:", holds)}${rel("", "waiting on:", waits)}
        ${BV.steps.html(i, p)}
        <div class="m">${meta.join("")}</div>
        ${!isQ || i.mark === "?" ? "" : `<div class="keep"><span class="kicker">answered ${esc(md(i.answered))}</span> ${BV.ledgerText(i.answer || "", p)}</div>`}
        ${opts.note !== false ? BV.noteBlock(i.note, p) + BV.exchange.html(i, p) : ""}
        ${press ? `<div class="press">${press}</div>` : ""}${below}
      </div></li>`;
  }

  // ---- the blocks, each a section ----
  function itemBlock(w, opts = {}) {
    const i = w.item, isQ = i.kind === "question";
    const lk = list => list.map(x => `<a href="${esc(opts.focusHref ? opts.focusHref(x) : x.href)}"${opts.focusHref ? ` data-focus="${esc(x.project + "/" + x.id)}"` : ""} title="${esc(x.text)}">${esc(clipWords(x.text, 90))}</a>`).join("; ");
    const f = [`<span><b>asked by</b> ${esc(whoWord(i.owner))}${isQ ? `, of ${esc(whoWord(i.who))}` : ""}</span>`, `<span><b>written</b> ${esc(md(i.created))}</span>`,
               `<span><b>due</b> ${i.due ? esc(md(i.due)) : "no day"}</span>`,
               `<span><b>holds up</b> ${(i.holdsUp || []).length ? lk(i.holdsUp) : "nothing"}</span>`,
               `<span><b>blocked by</b> ${(i.waitsOn || []).length ? lk(i.waitsOn) : "nothing"}</span>`];
    return `<section class="card ws-item"><h2>${esc(opts.title || "The item")}${opts.head ? ` <span class="meta">${opts.head}</span>` : ""}</h2>
      <ol class="ws-list">${row(i, { note: false, pickShown: !!w.pick })}</ol><p class="ws-fields">${f.join("")}</p></section>`;
  }

  // ---- the comparison (0.79.0): a pick item's options side by side, the answer press under each ----
  // GET /api/work carries `pick` for a question tagged pick with two or more linked options. One column per option: its
  // name on top, a live preview (a page or a markdown file in a frame, a picture as itself), a full-screen press, a
  // switch between the page's screens when it has sections to scroll to, and under it the press that answers with that
  // option. A plain option ("none of these") is a column with its name and its press. The answer box stays under the
  // columns for an answer in your own words. Once answered, the chosen column is marked and the presses go.
  const cap = s => { s = String(s || ""); return s.charAt(0).toUpperCase() + s.slice(1); };
  function pickBlock(w) {
    const pk = w && w.pick; if (!pk || !(pk.options || []).length) return "";
    const i = w.item, p = i.project, opts = pk.options;
    const live = i.mark === "?" && (i.who || BV.owner) === BV.owner;
    const chosen = String(pk.chosen || "").toLowerCase();
    const cols = opts.map(o => o.link ? "minmax(0, 1fr)" : "minmax(150px, .42fr)").join(" ");
    const col = (o, k) => {
      const nm = cap(o.name), isChosen = !!chosen && String(o.name).toLowerCase() === chosen;
      let view = "", tools = "";
      if (o.link) {
        if (o.exists === false) view = `<p class="none pk-none">The file it links is not in the brain.</p>`;
        else if (o.kind === "image") view = `<div class="pk-view pk-pic"><img src="${esc(o.preview)}" alt="${esc(nm)}" loading="lazy"></div>`;
        else if (o.kind === "html" || o.kind === "md") view = `<div class="pk-view"><iframe class="pk-frame" src="${esc(o.preview)}" title="${esc(nm)}" loading="lazy"></iframe></div>`;
        else view = `<p class="none pk-none">No preview for this kind of file; open it full screen to look.</p>`;
        const secs = o.kind === "html" && o.exists !== false ? (o.sections || []) : [];
        tools = `<div class="pk-tools">${o.exists === false ? "" : `<a class="btn pk-full" href="${esc(o.preview)}" target="_blank" rel="noopener" title="open it in its own tab, full window">Full screen</a>`}
          ${secs.length ? `<div class="pk-switch" role="group" aria-label="the screens of ${esc(nm)}">${secs.map(s => `<button type="button" class="btn pk-go" data-pk-go="${esc(s.id)}" data-pk-col="${k}" title="move the frame to this screen">${esc(s.name)}</button>`).join("")}</div>` : ""}</div>`;
      }
      const press = live ? `<button type="button" class="btn primary pk-answer" data-pick="${esc(nm)}" data-q="${esc(i.id)}" data-project="${esc(p)}" title="answer with this one, then go back to where you came from">Choose ${esc(o.name)}</button>` : "";
      return `<div class="pk-col${o.link ? "" : " plain"}${isChosen ? " chosen" : ""}" data-pk="${k}"${o.preview ? ` data-pk-src="${esc(String(o.preview).split("#")[0])}"` : ""}>
        <h3 class="pk-name">${esc(nm)}${isChosen ? ` <span class="kicker pk-mark">your answer</span>` : ""}</h3>
        ${view}${tools}${press ? `<div class="pk-press">${press}</div>` : ""}</div>`;
    };
    const answered = i.mark === "a";
    const said = answered && !chosen && i.answer ? `<p class="pk-said"><span class="kicker">answered</span> ${BV.ledgerText(i.answer, p)}</p>` : "";
    const box = live ? `<form class="qbox pk-box" data-q="${esc(i.id)}" data-project="${esc(p)}"><textarea class="grow" rows="1" placeholder="or answer in your own words" title="Enter for a new line, Ctrl+Enter sends" required></textarea><button class="btn primary" type="submit">Answer</button></form>` : "";
    const head = answered ? (chosen ? "answered; your answer is marked" : "answered") : live ? `${plural(opts.filter(o => o.link).length, "thing")} to look at; choose one under it` : "";
    return `<section class="card pk-band" id="pickband"><h2>Compare <span class="meta">${esc(head)}</span></h2>
      <p class="pk-q">${BV.ledgerText(i.text, p)}</p>${said}
      <div class="pk-cols" style="--pk-cols: ${cols}">${opts.map(col).join("")}</div>
      ${box}<p class="none pk-say" id="pickSay"></p></section>`;
  }
  // the switch under a frame: the frame moves to that screen of its page
  function pickGo(btn) {
    const c = btn.closest(".pk-col"), f = c && c.querySelector("iframe.pk-frame"); if (!f) return;
    f.src = (c.dataset.pkSrc || f.src.split("#")[0]) + "#" + btn.dataset.pkGo;
    for (const b of c.querySelectorAll("[data-pk-go]")) b.classList.toggle("on", b === btn);
  }
  // an answer press: the same answer write the item's presses make, then back to the page the user came from
  async function pickAnswer(btn) {
    const band = btn.closest(".pk-band");
    if (band) for (const b of band.querySelectorAll("[data-pick]")) b.disabled = true;
    const res = await BV.ledgerAct(btn.dataset.project, { action: "answer", id: btn.dataset.q, text: btn.dataset.pick, by: BV.owner });
    if (res.ok) { try { BV.refreshBadges(); } catch (e) {} BV.pick.back(); return res; }
    if (band) for (const b of band.querySelectorAll("[data-pick]")) b.disabled = false;
    const say = document.getElementById("pickSay"); if (say) say.textContent = res.message;
    return res;
  }

  function briefBlock(w, say) {
    const b = w.brief || {};
    const off = !w.briefInstalled;
    return `<section class="card ws-brief"><h2>Brief <span class="meta">${b.exists ? `written ${esc(b.writtenAt || "")}` : ""}</span></h2>
      <p class="bar2"><button type="button" class="btn" id="briefGo"${off ? " disabled" : ""} title="${off ? "the brief is not installed yet" : b.exists ? "write the brief again from the files as they stand now; this one stays until the new one lands" : "write a brief: a model reads the item, its files and its thread once and says what you need to know to answer it"}">${off ? "the brief is not installed yet" : b.exists ? "Refresh" : "Brief me"}</button>
        <span class="say" id="briefSay">${esc(say || "")}</span>${b.exists ? `<a href="${esc(b.reader)}">open the brief in the Reader</a>` : ""}</p>
      ${b.exists ? `<article class="md">${BV.md(b.text || "")}</article>` : `<p class="none">No brief yet.</p>`}</section>`;
  }

  function filesBlock(w, opts = {}) {
    const one = f => {
      if (f.kind === "route") return `<div class="ws-f"><span class="nm"><a href="${esc(f.href)}">${esc(f.title)}</a></span><span class="how">${esc(f.how)}</span></div>`;
      const sub = [f.folder ? `<span>${esc(f.folder)}</span>` : "", f.exists && f.at ? `<span>${esc(ago(f.at))}</span>` : "", !f.exists ? "<span>not found</span>" : "",
                   f.exists && /\.md$/i.test(f.path || "") ? BV.readerLink(f.path, "Reader") : ""].filter(Boolean).join("");
      const kids = f.kind === "folder" ? `<div class="kids">${(f.files || []).map(k => `<div><a href="${esc(k.href)}">${esc(k.name)}</a> <span class="meta">${esc(ago(k.at))}</span></div>`).join("") || `<span class="meta">empty</span>`}</div>` : "";
      const thumb = f.kind === "image" && f.exists ? `<img class="thumb" src="${esc(f.img)}" alt="${esc(f.name)}" data-img="${esc(f.path)}">` : "";
      return `<div class="ws-f${f.exists ? "" : " gone"}"><span class="nm"><a href="${esc(f.href)}" title="${esc(f.path)}">${esc(f.title || f.name)}</a>${thumb}</span><span class="how">${esc(opts.hideHow ? "" : f.how)}</span>
        <span class="sub">${sub}</span>${kids}</div>`;
    };
    const files = w.files || [];
    return `<section class="card"><h2>${esc(opts.title || "Files")} <span class="meta">${files.length ? plural(files.length, "file") : ""}</span></h2>${files.map(one).join("") || `<p class="none">${esc(opts.empty || "No files: the item links none and its thread names none.")}</p>`}</section>`;
  }

  function peopleBlock(people) {
    return `<section class="card"><h2>People</h2>${(people || []).map(p => `<div class="ws-pp"><a href="${esc(p.href)}">${esc(p.name)}</a>${p.role ? `<span class="role">${esc(clipWords(p.role, 120))}</span>` : ""}
        ${p.stands ? `<p class="st"><span class="d">${esc(md(p.standsDate))}</span>${BV.ledgerText(p.stands, "", { inline: true })}</p>` : `<p class="st meta">${p.exists ? "No Where it stands line on the card." : "No card."}</p>`}</div>`).join("") || `<p class="none">No one is named.</p>`}</section>`;
  }

  function siblingsBlock(w) {
    const s = w.siblings || [], h = w.siblingsHeld || [];
    return `<section class="card"><h2>Also open on this thread <span class="meta">${w.thread ? (s.length ? plural(s.length, "item") : "") : ""}</span></h2>
      ${!w.thread ? `<p class="none">This item belongs to no thread.</p>` : s.length ? `<ol class="ws-list">${s.map(i => row(i, { open: true })).join("")}</ol>` : `<p class="none">Nothing else is open on it.</p>`}
      ${h.length ? `<details class="fold"><summary>${plural(h.length, "item")} on hold</summary><ol class="ws-list">${h.map(i => row(i, { open: true })).join("")}</ol></details>` : ""}</section>`;
  }

  function callBlock(nc, names) {
    names = names || [];
    const list = !names.length ? "its people" : names.length === 1 ? names[0] : names.slice(0, -1).join(", ") + " or " + names[names.length - 1];
    return `<section class="card"><h2>Next call</h2>${nc
      ? `<p class="ws-call"><span class="when">${esc(dayWord(nc.start))} · ${esc(timeWord(nc.start))}</span> · ${esc(nc.title)} <span class="meta">with ${esc(nc.people.join(", "))}</span></p>
         <p class="ws-links">${nc.prep ? `<a href="${esc(nc.prep.href)}">open the prep</a><a href="${esc(nc.prep.reader)}">read it</a>` : `<span class="meta">no prep yet</span>`}${nc.join ? `<a href="${esc(nc.join)}" target="_blank" rel="noreferrer">join</a>` : ""}</p>`
      : `<p class="none">no call with ${esc(list)} on the calendar</p>`}</section>`;
  }

  function historyBlock(w) {
    const h = w.history || {};
    const rows = [];
    if (h.answer) rows.push(`<div class="ws-h"><span class="d">${esc(md(h.answered))}</span>answered: ${BV.ledgerText(h.answer, w.item.project)}</div>`);
    for (const n of h.notes || []) { const x = BV.noteHTML(n, w.item.project); rows.push(`<div class="ws-h"><span class="d">note</span>${x.text}${x.pics}</div>`); }   // 0.90.0: its pictures too (T-0354)
    const logs = (h.log || []).map(l => `<div class="ws-h"><span class="d">${esc(md(l.at))} ${esc(l.at.slice(11))}</span>${esc(l.agent)} · ${BV.ledgerText(l.text.replace(/^\S+\.md\s+--\s+/, ""), w.item.project)}</div>`);
    const first = logs.slice(0, h.fold || 5), more = logs.slice(h.fold || 5);
    return `<section class="card"><h2>History</h2>${rows.join("")}${first.join("")}${more.length ? `<details class="fold"><summary>${more.length} older</summary>${more.join("")}</details>` : ""}${!rows.length && !logs.length ? `<p class="none">Nothing on record yet.</p>` : ""}</section>`;
  }

  function notesBlock(w) {
    const i = w.item, n = i.note ? BV.noteHTML(i.note, i.project) : null;   // 0.90.0 (T-0354): a picture in the note is drawn under it
    return `<section class="card"><h2>Replies</h2>
      ${n ? `${n.text ? `<p class="ws-note">${n.text}</p>` : ""}${n.pics}` : `<p class="none">Nothing written on it yet.</p>`}
      ${BV.exchange.html(i, i.project)}
      <form class="ws-notebox" data-notebox="1"><textarea class="grow" rows="2" placeholder="reply, or paste a picture; the item stays as it is" title="Ctrl+Enter sends the reply"></textarea><button class="btn" type="submit">reply</button></form>
      <p class="none" id="noteSay"></p></section>`;
  }

  // ---- the brief run: start it, then ask every three seconds until it lands ----
  // brief({ ref: () => "<ledger>/<id>", item: () => the item, done: async () => reload }) -> {go(btn), status(), say}
  function brief(opts) {
    const st = { poll: 0, say: "" };
    const setSay = t => { st.say = t; const el = document.getElementById("briefSay"); if (el) el.textContent = t; };
    async function status() {
      const ref = opts.ref(); if (!ref) return;
      let s;
      try { const r = await fetch("/api/brief/status?item=" + encodeURIComponent(ref)); s = await r.json(); } catch (e) { s = { state: "unknown", error: e.message }; }
      const btn = document.getElementById("briefGo");
      if (s.state === "running") {
        setSay(s.step || (s.log || []).slice(-1)[0] || "writing the brief…");
        if (btn) { btn.disabled = true; btn.textContent = "writing…"; }
        if (!st.poll) st.poll = setInterval(status, 3000);
        return;
      }
      if (st.poll) {
        clearInterval(st.poll); st.poll = 0;
        st.say = s.state === "done" ? "written" : s.state === "failed" ? `not written: ${s.error || "no reason given"}` : s.state === "refused" ? `not started: ${s.error || "no reason given"}` : "";
        await opts.done();
        return;
      }
      if ((s.state === "failed" || s.state === "refused") && s.finishedAt && !st.say) setSay(`the last try did not write a brief: ${s.error || "no reason given"}`);
    }
    async function go(btn) {
      btn.disabled = true; btn.textContent = "starting…";
      const it = opts.item();
      const presses = it && it.kind === "question" ? (BV.choices(it) || []).concat(["write"]) : ["done", "hold", "note"];
      let j = {};
      try {
        const r = await fetch("/api/brief/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item: opts.ref(), presses }) });
        j = await r.json().catch(() => ({}));
      } catch (e) { j = { ok: false, error: e.message }; }
      if (!j.ok) { setSay(`not started: ${j.error || "no reason given"}`); btn.disabled = false; btn.textContent = "Brief me"; return; }
      setSay("writing the brief…");
      btn.textContent = "writing…";
      if (!st.poll) st.poll = setInterval(status, 3000);
    }
    function stop() { if (st.poll) { clearInterval(st.poll); st.poll = 0; } st.say = ""; }
    return { go, status, stop, get say() { return st.say; } };
  }

  // the note box at the foot: a line added to the item's note through POST /api/reply, the item left as it is
  async function saveNote(form, item, done) {
    const ta = form.querySelector("textarea"), text = ta.value.trim(); if (!text) return;
    const b = form.querySelector("button"); b.disabled = true;
    const res = await BV.replies.act(item.project, item.id, text, item.ledger);
    b.disabled = false;
    if (res.ok) { ta.value = ""; await done(); BV.refreshBadges(); }
    const say = document.getElementById("noteSay"); if (say) say.textContent = res.message;
  }

  return { row, itemBlock, pickBlock, pickGo, pickAnswer, briefBlock, filesBlock, peopleBlock, siblingsBlock, callBlock, historyBlock, notesBlock, brief, saveNote, clipWords };
})();
