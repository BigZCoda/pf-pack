// Chat: the conversation, on the board. Zak, 2026-09-21, looking at the room under Next: "the chat could be right
// there, the most recent chat and the chat box to communicate with it could show up in that empty space... It should
// have the ability to create a new chat, etc, and then if there are multiple chats running, maybe those show up as a
// visual somewhere." So this is the last exchange of whichever conversation you are in, the box to answer it, a
// chooser for which one, a new one on a press, and a lit bubble per conversation with a turn running. The whole
// thread, with its tool calls and its sub-agents, is still the chat page, one link away.
// It replaced two files' jobs: the plain command line (still in the add list for whoever wants one line and nothing
// else) and the framed copy of the chat page that used to live under this name.
(function () {
BV.widgets.register({
  id: "chat", contract: 1, title: "Chat", size: "8", defaultOn: true, card: true,
  fillRows: 22,                             // free mode: the message list wants a working height (440px), not its content's
  source: "your conversations with the main agent, the newest one's last exchange, and the box that sends the next message (GET /api/chats, GET /api/chat, POST /api/chat/send)",

  mount(el, api) {
    if (!document.getElementById("bv-chat-css")) {
      const s = document.createElement("style");
      s.id = "bv-chat-css";
      s.textContent = `
        /* it fills the room it is given rather than sitting short in it: standing under Next beside a deck two rows
           tall, the leftover height goes to the conversation instead of to a gap */
        section.w[data-w="chat"] { align-self: stretch; display: flex; flex-direction: column; }
        section.w[data-w="chat"] > .wbody { flex: 1; min-height: 0; display: flex; }
        .cw { display: flex; flex-direction: column; gap: 9px; min-height: 0; flex: 1; }
        .cw .ex { flex: 1; min-height: 64px; max-height: 340px; overflow: auto; padding-right: 3px; }
        .cw .ex .ask { font-family: var(--font-ui); font-size: 13px; color: var(--ink-soft); background: var(--selected);
                       border: 1px solid var(--rule-soft); border-radius: var(--radius-lg); padding: 6px 11px;
                       margin: 0 0 9px; align-self: flex-end; max-width: 78ch; }
        .cw .ex article.md { border: 0; box-shadow: none; background: transparent; padding: 0; font-size: 14px; line-height: 1.55; }
        .cw .ex article.md h1, .cw .ex article.md h2 { font-size: 16px; margin: .6em 0 .3em; border: 0; padding: 0; }
        .cw .ex article.md h3, .cw .ex article.md h4 { font-size: 14.5px; margin: .5em 0 .25em; }
        .cw .ex .quiet { color: var(--muted); font-size: 13px; margin: 2px 0; }
        .cw .ex .caret { display: inline-block; width: 7px; height: 14px; background: var(--accent); vertical-align: -2px;
                         animation: bvcaret 1s steps(2) infinite; }
        @keyframes bvcaret { 50% { opacity: 0; } }
        .cw .live { display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }
        .cw .live[hidden] { display: none; }
        .cw .live button { width: 11px; height: 11px; padding: 0; border-radius: 50%; border: 1px solid var(--open);
                           background: var(--open); cursor: pointer; box-shadow: 0 0 0 3px var(--open-tint);
                           animation: bvlive 1.8s ease-in-out infinite; }
        .cw .live button.on { background: var(--accent); border-color: var(--accent); box-shadow: 0 0 0 3px var(--blocked-tint); }
        @keyframes bvlive { 50% { opacity: .45; } }
        @media (prefers-reduced-motion: reduce) { .cw .live button, .cw .ex .caret { animation: none; } }
        .cw .line { display: flex; gap: 9px; align-items: flex-end; }
        .cw textarea { flex: 1; min-width: 0; padding: 8px 11px; border: 1px solid var(--rule-soft); border-radius: var(--radius);
                       background: var(--bg); resize: none; font-family: var(--font-ui); font-size: 15px; line-height: 1.45;
                       min-height: 40px; max-height: 190px; overflow-y: auto; }
        .cw textarea:focus { outline: none; border-color: var(--accent); }
        .cw .btns { display: flex; gap: 7px; align-items: center; }
        .cw .m { color: var(--muted); font-size: 11.5px; margin: 0; display: flex; gap: 12px; align-items: baseline; }
        .whead select[data-pick] { font-family: var(--font-ui); font-size: 11px; color: var(--muted); background: var(--surface);
                                   border: 1px solid var(--rule-soft); border-radius: var(--radius); padding: 1px 4px; max-width: 220px; }
        .whead select[data-pick]:focus { outline: none; border-color: var(--accent); }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="cw">
        <div class="ex" data-ex></div>
        <div class="live" data-live hidden></div>
        <div class="line">
          <textarea rows="1" placeholder="tell the brain what to do" aria-label="tell the brain what to do"
                    title="Enter sends it; Shift+Enter makes a new line"></textarea>
          <span class="btns">
            <button class="btn primary" type="button" data-send>send</button>
            <button class="btn" type="button" data-new title="start a conversation of its own">new</button>
          </span>
        </div>
        <p class="m"><span data-say></span><a href="/chat">the whole conversation</a></p>
      </div>`;

    const box = el.querySelector("textarea");
    box.addEventListener("input", () => { box.style.height = "auto"; box.style.height = Math.min(190, box.scrollHeight + 2) + "px"; });
    box.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(el, api); } });
    el.addEventListener("click", e => {
      if (e.target.closest("[data-send]")) return send(el, api);
      if (e.target.closest("[data-new]")) return fresh(el, api);
      const b = e.target.closest("[data-live] button");
      if (b) return open(el, api, b.dataset.id);
    });
    api.card.addEventListener("change", e => {
      const s = e.target.closest("[data-pick]"); if (!s) return;
      if (!s.value) return fresh(el, api);
      open(el, api, s.value);
    });
    return this.refresh(el, api);
  },

  // the minute tick must not throw away a turn in flight, and must not wipe what is half typed
  async refresh(el, api) {
    if (el._busy) return;
    let j;
    try { j = await api.get("/api/chats"); } catch (e) { return api.fail(e); }
    el._chats = j.chats || [];
    if (!el._chat && el._chats.length) el._chat = el._chats[0].id;
    head(el, api);
    bubbles(el, api);
    api.count(el._chats.length ? api.plural(el._chats.length, "conversation") : "new");
    if (el.querySelector("textarea").value.trim()) return;      // he is writing: leave the room alone
    await exchange(el, api);
  },
});

// ---- which conversation you are in ----
function head(el, api) {
  const esc = api.esc, rows = el._chats || [];
  const sig = rows.map(c => c.id + (c.running ? "!" : "")).join(",") + "|" + (el._chat || "");
  if (el._headSig === sig) return;
  el._headSig = sig;
  api.head(`<select data-pick title="which conversation this is">
      ${rows.map(c => `<option value="${esc(c.id)}"${c.id === el._chat ? " selected" : ""}>${esc(api.clip(c.title || "a conversation", 44))}</option>`).join("")}
      <option value=""${el._chat ? "" : " selected"}>a new conversation</option>
    </select>`);
}

// ---- a lit bubble per conversation with a turn running, when there is more than one ----
function bubbles(el, api) {
  const live = el.querySelector("[data-live]"); if (!live) return;
  const running = (el._chats || []).filter(c => c.running);
  live.hidden = running.length < 2;
  if (live.hidden) { live.innerHTML = ""; return; }
  live.innerHTML = running.map(c =>
    `<button type="button" class="${c.id === el._chat ? "on" : ""}" data-id="${api.esc(c.id)}"
       title="${api.esc(c.title || "a conversation")}" aria-label="${api.esc(c.title || "a conversation")}"></button>`).join("");
}

// ---- the last exchange of the conversation you are in ----
async function exchange(el, api) {
  const box = el.querySelector("[data-ex]"); if (!box) return;
  if (!el._chat) { box.innerHTML = `<p class="quiet">Nothing said yet.</p>`; return; }
  let j;
  try { j = await api.get("/api/chat?id=" + encodeURIComponent(el._chat)); }
  catch (e) { box.innerHTML = `<p class="quiet">${api.esc(e.status === 403 ? "not on this copy" : e.message)}</p>`; return; }
  const turns = j.turns || [];
  let reply = null, ask = null;
  for (let i = turns.length - 1; i >= 0; i--) {
    if (!reply && turns[i].role === "assistant" && (turns[i].text || "").trim()) { reply = turns[i]; continue; }
    if (reply && turns[i].role === "user") { ask = turns[i]; break; }
  }
  if (!reply && !ask) { box.innerHTML = `<p class="quiet">Nothing said yet.</p>`; return; }
  box.innerHTML = (ask ? `<p class="ask">${api.esc(api.clip(ask.text, 300))}</p>` : "")
    + (reply ? `<article class="md">${BV.md(reply.text || "")}</article>` : "");
  box.scrollTop = 0;
}

function open(el, api, id) {
  el._chat = id || null;
  el._headSig = "";
  head(el, api);
  bubbles(el, api);
  exchange(el, api);
}
function fresh(el, api) {
  el._chat = null;
  el._headSig = "";
  head(el, api);
  bubbles(el, api);
  el.querySelector("[data-ex]").innerHTML = `<p class="quiet">Nothing said yet.</p>`;
  const t = el.querySelector("textarea"); t.value = ""; t.focus();
}

// ---- sending, which is the same call the chat page makes ----
async function send(el, api) {
  const t = el.querySelector("textarea"), btn = el.querySelector("[data-send]");
  const say = el.querySelector("[data-say]"), box = el.querySelector("[data-ex]");
  const text = t.value.trim(); if (!text || el._busy) return;
  el._busy = true;
  t.disabled = btn.disabled = true;
  say.textContent = "opening a session";
  box.innerHTML = `<p class="ask">${api.esc(api.clip(text, 300))}</p><article class="md"></article>`;
  const art = box.querySelector("article.md");
  art.innerHTML = `<span class="caret"></span>`;
  let got = "";
  try {
    const r = await fetch("/api/chat/send", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat: el._chat, project: "main", text: text }),
    });
    if (!r.ok || !r.body) {
      const j = await r.json().catch(() => ({}));
      const err = new Error(j.error || ("the server answered " + r.status)); err.status = r.status; throw err;
    }
    say.textContent = "thinking";
    const rd = r.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const step = await rd.read(); if (step.done) break;
      buf += dec.decode(step.value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
        for (const ln of chunk.split("\n")) {
          if (ln.indexOf("data: ") !== 0) continue;
          let ev; try { ev = JSON.parse(ln.slice(6)); } catch (x) { continue; }
          if (ev.e === "start" && ev.chat) el._chat = ev.chat;
          else if (ev.e === "text") { got += ev.t || ""; art.innerHTML = BV.md(got) + `<span class="caret"></span>`; box.scrollTop = box.scrollHeight; }
          else if (ev.e === "text_final") { got = ev.t || got; art.innerHTML = BV.md(got); }
          else if (ev.e === "error") say.textContent = ev.message || "the turn failed";
        }
      }
    }
    art.innerHTML = got.trim() ? BV.md(got) : `<p class="quiet">It came back with nothing. The turn is on the chat page.</p>`;
    if (got.trim()) say.textContent = "";
    t.value = ""; t.style.height = "auto";
  } catch (e) {
    say.textContent = e.status === 403 ? "not on this copy" : e.message;
    art.innerHTML = "";
  }
  el._busy = false;
  t.disabled = btn.disabled = false; t.focus();
  el._headSig = "";
  try { head(el, api); } catch (x) {}
}
})();
