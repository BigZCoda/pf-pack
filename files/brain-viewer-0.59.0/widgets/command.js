// Command: one line to the main agent, in the notepad's look. What comes back sits under it in the same shape the chat
// page gives a reply; the whole conversation, with its tool calls and its sub-agents, is the chat page. The notes
// button opens the notepad this app carries on every page.
// Off the default board since 0.39.0: the chat instrument took this room and does the same send with the conversation
// around it. The file stays, in the add list, for whoever wants one line and nothing else.
(function () {
BV.widgets.register({
  id: "command", contract: 1, title: "Command", size: "12", defaultOn: false, card: true,
  source: "one message to the main agent, the same call the chat page makes (POST /api/chat/send)",
  refresh() {},        // it holds what you typed and what came back: the minute tick must not wipe either

  mount(el, api) {
    if (!document.getElementById("bv-command-css")) {
      const s = document.createElement("style");
      s.id = "bv-command-css";
      s.textContent = `
        .cmd .line { display: flex; gap: 9px; align-items: flex-end; }
        .cmd textarea { flex: 1; min-width: 0; padding: 8px 11px; border: 1px solid var(--rule-soft); border-radius: var(--radius);
                        background: var(--bg); resize: none; font-family: var(--font-ui); font-size: 15px; line-height: 1.45;
                        min-height: 40px; max-height: 190px; overflow-y: auto; }
        .cmd textarea:focus { outline: none; border-color: var(--accent); }
        .cmd .btns { display: flex; gap: 7px; align-items: center; }
        .cmd .out { margin: 11px 0 0; border-left: 2px solid var(--rule-soft); padding-left: 12px; font-size: 14px;
                    line-height: 1.55; max-height: 240px; overflow: auto; white-space: pre-wrap; }
        .cmd .out[hidden] { display: none; }
        .cmd .m { color: var(--muted); font-size: 11.5px; margin-top: 5px; display: flex; gap: 12px; align-items: baseline; }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = `<div class="cmd">
        <div class="line">
          <textarea rows="1" placeholder="tell the brain what to do" aria-label="tell the brain what to do"
                    title="Enter sends it; Shift+Enter makes a new line"></textarea>
          <span class="btns">
            <button class="btn primary" type="button" data-send>send</button>
            <button class="btn" type="button" data-notes title="open the notepad">notes</button>
          </span>
        </div>
        <div class="out" data-out hidden></div>
        <p class="m"><span data-say></span><a href="/chat">the whole conversation</a></p>
      </div>`;
    const box = el.querySelector("textarea"), out = el.querySelector("[data-out]"), say = el.querySelector("[data-say]");
    const btn = el.querySelector("[data-send]");
    api.count("main agent");

    const fit = () => { box.style.height = "auto"; box.style.height = Math.min(190, box.scrollHeight + 2) + "px"; };
    box.addEventListener("input", fit);

    el.querySelector("[data-notes]").onclick = () => {
      BV.notepad.mount();
      const tab = document.querySelector("#notepad [data-note-toggle]");
      if (tab) tab.click();
    };

    async function go() {
      const text = box.value.trim(); if (!text) return;
      box.disabled = btn.disabled = true;
      say.textContent = "opening a session";
      out.hidden = false; out.textContent = "";
      let got = "";
      try {
        const r = await fetch("/api/chat/send", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat: null, project: "main", text: text }),
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
              if (ev.e === "text") { got += ev.t || ""; out.textContent = got; out.scrollTop = out.scrollHeight; }
              else if (ev.e === "text_final") { got = ev.t || got; out.textContent = got; }
              else if (ev.e === "error") say.textContent = ev.message || "the turn failed";
            }
          }
        }
        if (!got.trim()) out.textContent = "It came back with nothing. The turn is on the chat page.";
        else say.textContent = "";
        box.value = ""; fit();
      } catch (e) {
        out.hidden = true;
        say.textContent = e.status === 403 ? "not on this copy" : e.message;
      }
      box.disabled = btn.disabled = false; box.focus();
    }
    btn.onclick = go;
    box.onkeydown = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go(); } };
  },
});
})();
