// attach.js -- pictures attached to a question or an answer (2026-09-22, viewer T-0219).
// The owner asked on 2026-09-21 that pictures be attachable to the questions section. A picture goes up through POST /api/attach,
// lands in an attachments/ folder next to the ledger the item lives on, and its path becomes one more `→ link` on the item.
// A linked image renders as a thumbnail; a thumbnail carries data-img, so viewer-common.js's one delegated click opens it
// in the lightbox the viewer already has.
//
// A HOST is any element carrying data-attach-item (the Q-/T- id) and data-attach-ledger (the holon id or its ledger path).
// Inside a host: a [data-attach] control opens a file picker, a picture pasted into a textarea uploads the same way, and
// the new thumbnail is added to the host's .att-thumbs strip before the answer is sent. The Answer deck renders its own
// host; on today and projects, watch() turns every question card and ledger row the shared renderer draws into one.
(function (root) {
  "use strict";
  const IMG_RE = /\.(png|jpe?g|gif|webp|svg)$/i;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // "→ links" on an item, reduced to the brain-relative image paths among them: a [[wikilink]] is unwrapped, a query or
  // a fragment is ignored for the extension test, a route (/glossary) or a web address is never a picture of the brain's
  function imageLinks(links) {
    const out = [];
    for (const raw of links || []) {
      let l = String(raw == null ? "" : raw).trim();
      const wl = /^\[\[(.+)\]\]$/.exec(l);
      if (wl) l = wl[1].split("|")[0].trim();
      if (!l || l.startsWith("/") || /^[a-z]+:/i.test(l)) continue;
      if (!IMG_RE.test(l.split(/[?#]/)[0])) continue;
      if (!out.includes(l)) out.push(l);
    }
    return out;
  }

  function thumb(path) {
    return `<img class="att-thumb" src="/api/image?path=${encodeURIComponent(path)}" data-img="${esc(path)}" alt="" title="${esc(path)}" loading="lazy">`;
  }

  // the strip of thumbnails for an item's links; always drawn, empty when there are none, so an upload has somewhere to land
  function thumbs(links) {
    return `<div class="att-thumbs">${imageLinks(links).map(thumb).join("")}</div>`;
  }

  function control() {
    return `<button type="button" class="att-clip" data-attach title="attach a picture to this item (or paste one into the answer box)">attach</button>`;
  }

  // the ids the shared renderer puts on a card: q-<project>-<Q-0001> on a question, t-<project>-<T-0001> on a task row,
  // and the same with a block's own prefix in front of it (the Today page's due block writes due-q-<project>-<Q-0001>)
  function parseCardId(id) {
    const m = /^(?:[a-z]+-)?([qt])-(.+)-([QT]-\d{4})$/.exec(String(id || ""));
    return m ? { kind: m[1] === "q" ? "question" : "task", ledger: m[2], item: m[3] } : null;
  }

  function css() {
    if (typeof document === "undefined" || document.getElementById("bv-attach-css")) return;
    const s = document.createElement("style");
    s.id = "bv-attach-css";
    s.textContent = `
      .att-thumbs { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 4px; }
      .att-thumbs:empty { display: none; }
      .att-thumb { width: 64px; height: 48px; object-fit: cover; border: 1px solid var(--rule-soft); border-radius: var(--radius);
                   background: var(--bg); cursor: zoom-in; }
      .att-thumb:hover { border-color: var(--accent); }
      button.att-clip { font-family: var(--font-ui); font-size: 12px; color: var(--muted); background: none; border: 0;
                        border-bottom: 1px dotted var(--muted); padding: 0 1px; cursor: pointer; align-self: center; }
      button.att-clip:hover { color: var(--accent); border-bottom-color: var(--accent); }
      .att-msg { font-size: 12px; color: var(--muted); }
    `;
    document.head.appendChild(s);
  }

  function readB64(file) {
    return new Promise((res, rej) => {
      const fr = new FileReader();
      fr.onload = () => res(String(fr.result).split(",")[1] || "");
      fr.onerror = () => rej(new Error("could not read the file"));
      fr.readAsDataURL(file);
    });
  }

  async function upload(ledger, item, file) {
    const data = await readB64(file);
    const r = await fetch("/api/attach", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ledger, item, name: file.name || "pasted.png", data }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || ("the server answered " + r.status));
    return j;
  }

  function say(host, text) {
    const m = host.querySelector("[data-msg]") || host.querySelector(".att-msg");
    if (m) m.textContent = text;
  }

  function addThumb(host, path) {
    let strip = host.querySelector(".att-thumbs");
    if (!strip) {
      strip = document.createElement("div"); strip.className = "att-thumbs";
      host.appendChild(strip);
    }
    if (!Array.from(strip.querySelectorAll("[data-img]")).some(i => i.dataset.img === path)) strip.insertAdjacentHTML("beforeend", thumb(path));
  }

  async function send(host, files) {
    const pics = Array.from(files || []).filter(f => /^image\//.test(f.type || ""));
    if (!pics.length) { say(host, "only a picture can be attached"); return; }
    for (const f of pics) {
      say(host, `attaching ${f.name || "the picture"}`);
      try {
        const j = await upload(host.dataset.attachLedger, host.dataset.attachItem, f);
        addThumb(host, j.path);
        say(host, "attached");
      } catch (err) { say(host, "the picture was not attached: " + err.message); return; }
    }
  }

  // the two gestures, delegated once for the whole page, so a re-render never unbinds them
  let bound = false;
  function bind() {
    if (bound || typeof document === "undefined") return;
    bound = true;
    css();
    document.addEventListener("click", e => {
      const b = e.target.closest && e.target.closest("[data-attach]"); if (!b) return;
      const host = b.closest("[data-attach-item]"); if (!host) return;
      e.preventDefault(); e.stopPropagation();
      const input = document.createElement("input");
      input.type = "file"; input.accept = "image/png,image/jpeg,image/gif,image/webp"; input.multiple = true;
      input.addEventListener("change", () => send(host, input.files));
      input.click();
    }, true);
    document.addEventListener("paste", e => {
      const ta = e.target.closest && e.target.closest("textarea"); if (!ta) return;
      const host = ta.closest("[data-attach-item]"); if (!host) return;
      const files = Array.from((e.clipboardData && e.clipboardData.items) || [])
        .filter(i => i.kind === "file" && /^image\//.test(i.type)).map(i => i.getAsFile()).filter(Boolean);
      if (!files.length) return;          // words paste as words
      e.preventDefault();
      send(host, files);
    });
  }

  // a card the shared renderer drew (viewer-common.js questionCard / itemRow), made into a host: its image links become
  // thumbnails, and a question gets the attach control beside its Answer button (or its reopen button once answered)
  function decorate(scope) {
    const base = scope || document;
    for (const card of base.querySelectorAll(".q[id], li.item[id]")) {
      if (card.hasAttribute("data-att-done")) continue;
      card.setAttribute("data-att-done", "");
      const ref = parseCardId(card.id); if (!ref) continue;
      card.dataset.attachItem = ref.item; card.dataset.attachLedger = ref.ledger;
      const links = Array.from(card.querySelectorAll(".filelink[data-open]"))
        .filter(a => !a.closest(".att-thumbs")).map(a => a.getAttribute("data-open") || "");
      const strip = document.createElement("div"); strip.className = "att-thumbs";
      strip.innerHTML = imageLinks(links).map(thumb).join("");
      if (ref.kind === "question") {
        const qt = card.querySelector(".qt");
        if (qt) qt.insertAdjacentElement("afterend", strip); else card.appendChild(strip);
        const spot = card.querySelector("form button[type=submit]") || card.querySelector(".ans button");
        if (spot) {
          spot.insertAdjacentHTML("beforebegin", control());
          spot.insertAdjacentHTML("afterend", `<span class="att-msg"></span>`);
        }
      } else {
        const t = card.querySelector(".t");
        if (t) t.insertAdjacentElement("afterend", strip); else card.appendChild(strip);
      }
    }
  }

  // decorate now and after every re-render of the given element (the pages redraw with innerHTML)
  function watch(el) {
    bind();
    const target = el || document.body;
    decorate(target);
    let queued = false;
    new MutationObserver(() => {
      if (queued) return; queued = true;
      Promise.resolve().then(() => { queued = false; decorate(target); });
    }).observe(target, { childList: true, subtree: true });
  }

  const api = { imageLinks, thumbs, thumb, control, parseCardId, upload, addThumb, decorate, watch, bind };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else { root.BVAttach = api; bind(); }
})(typeof window !== "undefined" ? window : globalThis);
