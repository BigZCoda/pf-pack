// viewer-common.js -- shared by the Brain Viewer pages: escaping, a small markdown renderer, Obsidian canvas colors.
window.BV = (function () {
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

  // ---- One guard for every key handler in the app (2026-09-10, ledger T-0112) ----
  // No page hotkey fires while the focus is in something you type into. A slash typed in the notepad was jumping to
  // the people filter, so every page's own keydown listener asks this first (`if (BV.typing(e)) return;`) and there is
  // one rule instead of nine. Escape is the way out of a box: pressed inside one it blurs the field and stops there,
  // so the second Escape is the page's own (fold the quest log, close a drawer) with nothing typed in between.
  const TYPED_INPUT = /^(text|search|url|tel|email|password|number|date|datetime-local|month|week|time)$/;
  function typing(e) {
    const t = e && e.target && e.target.nodeType === 1 && e.target.closest ? e.target : null;
    const el = t || document.activeElement;
    if (!el || !el.closest) return false;
    const f = el.closest("input, textarea, select, [contenteditable]");
    if (!f) return false;
    if (f.tagName === "INPUT" && !TYPED_INPUT.test((f.getAttribute("type") || "text").toLowerCase())) return false;   // a checkbox or a button is not a box you type in
    if (f.hasAttribute("contenteditable") && f.getAttribute("contenteditable") === "false") return false;
    if (e && e.type === "keydown" && e.key === "Escape") { try { f.blur(); } catch (_) {} }
    return true;
  }

  // Where a rendered document sits, so its own relative links resolve: md(text, { base: "folder/of/that/file" }).
  // Set for the length of one md() call, so every inline() inside it inherits it (2026-09-10, T-0021 + T-0079).
  let mdBase = "";
  const isURL = h => /^(https?:|mailto:|data:|tel:|#)/i.test(String(h || "").trim());
  function mdPath(p) {
    p = String(p || "").trim().replace(/^<|>$/g, "");
    if (!p) return "";
    if (/^\/api\/image\?path=/.test(p)) return decodeURIComponent(p.split("path=")[1] || "");
    p = p.replace(/^\.\//, "");
    if (!mdBase || p.startsWith("/") || (p.includes("/") && !p.startsWith("../"))) return p;   // already brain-relative
    const out = [];
    for (const x of (mdBase + "/" + p).split("/")) { if (!x || x === ".") continue; if (x === "..") out.pop(); else out.push(x); }
    return out.join("/");
  }
  function inline(s, base) {
    const prev = mdBase; if (base !== undefined) mdBase = base || "";
    s = esc(hideLineRefs(s));
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (m, a, b) => `<a class="wikilink" href="#" data-wikilink="${a}">${b || a}</a>`);
    // A picture written into a document or a message is SHOWN: a thumbnail that opens in the image viewer (T-0021,
    // T-0079). The bytes come from GET /api/image, which serves images under the brain and refuses everything else, so
    // nothing here reaches the network -- an outside URL stays a link rather than becoming a fetch.
    s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (m, alt, src) => {
      if (isURL(src)) return `<a href="${src}" target="_blank" rel="noopener">${alt || src}</a>`;
      const path = mdPath(src);
      // only a real picture is fetched: an image tag whose target is not an image file is text the writer meant as
      // something else, and asking the server for it earns a 403 in the console for nothing
      if (!path || !isImage(path)) return `<em>[image: ${alt}]</em>`;
      return `<img class="mdimg" src="/api/image?path=${encodeURIComponent(path)}" data-img="${path}" alt="${alt}" title="${path}">`;
    });
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (m, label, href) => {
      if (isURL(href)) return `<a href="${href}" target="_blank" rel="noopener">${label}</a>`;
      if (href.startsWith("/")) return `<a href="${href}">${label}</a>`;                       // a route in this app
      const path = mdPath(href); if (!path) return m;
      if (isImage(path)) return `<span class="filelink" data-img="${path}" title="${path}">${label}</span>`;
      return `<span class="filelink" data-open="${path}" title="${path}">${label}</span>`;     // a file in the brain: the drawer opens it
    });
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/__([^_]+)__/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>").replace(/~~([^~]+)~~/g, "<del>$1</del>");
    mdBase = prev;
    return s;
  }

  // md(text) as before; md(text, {base}) resolves the document's own relative image and file links against that folder
  function md(src, opts) {
    const prev = mdBase; mdBase = (opts && opts.base) || "";
    try { return mdBody(hideLineRefs(src)); } finally { mdBase = prev; }
  }
  function mdBody(src) {
    const lines = String(src ?? "").replace(/\r\n/g, "\n").split("\n"); let out = [], i = 0;
    if (lines[0] === "---") { let j = lines.indexOf("---", 1); if (j > 0) { out.push(`<details class="fm"><summary>frontmatter</summary><pre>${esc(lines.slice(1, j).join("\n"))}</pre></details>`); i = j + 1; } }
    const listStack = [];
    const LI = /^(\s*)([-*+]|\d+\.)\s+(.*)$/, liLevel = ws => Math.floor(ws.replace(/\t/g, "  ").length / 2);
    const listContinues = k => {
      const nx = lines[k + 1]; if (nx == null || /^\s*$/.test(nx)) return false;
      const m = nx.match(LI); if (!m) return false;
      const lv = liLevel(m[1]), ty = /\d/.test(m[2]) ? "ol" : "ul";
      return lv >= listStack.length || listStack[lv] === ty;
    };
    const closeLists = (toLevel = -1) => { while (listStack.length && listStack.length - 1 > toLevel) { out.push(listStack.pop() === "ol" ? "</ol>" : "</ul>"); } };
    while (i < lines.length) {
      let l = lines[i];
      if (/^```/.test(l)) { closeLists(); let buf = []; i++; while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]); i++; out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`); continue; }
      // A list survives ONE blank line between its items (2026-09-23, T-0247): the brain writes numbered lists loose,
      // a blank line between items, and closing on every blank made one <ol> per item, so every item read "1.". The
      // list stays open when the next line is an item at a deeper level or one of the same kind at an open level; two
      // blank lines, or anything that is not an item, closes it as before.
      if (/^\s*$/.test(l)) { if (listStack.length && listContinues(i)) { i++; continue; } closeLists(); i++; continue; }
      let h = l.match(/^(#{1,6})\s+(.*)$/); if (h) { closeLists(); out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i++; continue; }
      if (/^(-{3,}|\*{3,})\s*$/.test(l)) { closeLists(); out.push("<hr>"); i++; continue; }
      if (/^\|/.test(l)) { closeLists(); let rows = []; while (i < lines.length && /^\|/.test(lines[i])) rows.push(lines[i++]);
        rows = rows.filter(r => !/^\|\s*:?-{2,}/.test(r)); const cells = r => r.replace(/^\||\|$/g, "").split("|").map(c => inline(c.trim()));
        out.push("<table>" + rows.map((r, k) => `<tr>${cells(r).map(c => k === 0 ? `<th>${c}</th>` : `<td>${c}</td>`).join("")}</tr>`).join("") + "</table>"); continue; }
      if (/^>/.test(l)) { closeLists(); let buf = []; while (i < lines.length && /^>/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, "")); out.push(`<blockquote>${md(buf.join("\n"))}</blockquote>`); continue; }
      let li = l.match(LI);
      if (li) {
        const level = liLevel(li[1]); const type = /\d/.test(li[2]) ? "ol" : "ul";
        while (listStack.length - 1 > level) out.push(listStack.pop() === "ol" ? "</ol>" : "</ul>");
        // an ordered list opened at a number other than 1 keeps that number (T-0247)
        while (listStack.length - 1 < level) {
          listStack.push(type); const n = type === "ol" && listStack.length - 1 === level ? parseInt(li[2], 10) : 1;
          out.push(type === "ol" ? (n !== 1 ? `<ol start="${n}">` : "<ol>") : "<ul>");
        }
        let text = inline(li[3].replace(/^\[( |x)\]\s*/i, (m, c) => c.toLowerCase() === "x" ? "☑ " : "☐ "));
        i++;
        // an indented line under an item that is not itself an item belongs to that item (T-0247): it used to close
        // the list and stand as a paragraph, which restarted the numbering after it. One blank line before it is allowed.
        const cont = k => lines[k] != null && /^(\s{2,}|\t)\S/.test(lines[k]) && !LI.test(lines[k]);
        while (i < lines.length) {
          if (cont(i)) { text += "<br>" + inline(lines[i].trim()); i++; }
          else if (/^\s*$/.test(lines[i]) && cont(i + 1)) { text += "<br><br>" + inline(lines[i + 1].trim()); i += 2; }
          else break;
        }
        out.push(`<li>${text}</li>`); continue;
      }
      closeLists(); let buf = [l]; i++; while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|\||>|\s*([-*+]|\d+\.)\s)/.test(lines[i])) buf.push(lines[i++]);
      out.push(`<p>${inline(buf.join(" "))}</p>`);
    }
    closeLists(); return out.join("\n");
  }

  // Obsidian canvas preset colors 1-6; hex passes through; none = neutral.
  const PALETTE = { "1": "#e93147", "2": "#ec7500", "3": "#e0ac00", "4": "#08b94e", "5": "#00bfbc", "6": "#7852ee" };
  function color(c) { if (!c) return null; if (PALETTE[c]) return PALETTE[c]; if (/^#?[0-9a-f]{6}$/i.test(c)) return c.startsWith("#") ? c : "#" + c; return null; }
  function tint(hex, alpha) { if (!hex) return `rgba(0,0,0,${alpha})`; const n = parseInt(hex.slice(1), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`; }
  // Mix a hex toward the page ground (--bg from viewer-tokens.css) so canvas colors sit on it instead of shouting
  // (chosen direction 2026-09-04, principle 3: "canvas nodes keep the brain's six colors, desaturated to sit on sand").
  function soften(hex, k = 0.3) {
    if (!hex) return null;
    const g = (getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() || "#efe9dc").replace("#", "");
    const a = parseInt(hex.slice(1), 16), b = parseInt(g.length === 3 ? g.replace(/./g, c => c + c) : g, 16);
    const ch = s => Math.round(((a >> s) & 255) * (1 - k) + ((b >> s) & 255) * k);
    return "#" + [16, 8, 0].map(s => ch(s).toString(16).padStart(2, "0")).join("");
  }

  // The image viewer (ledger T-0014): a reference image opened inside the app instead of a note to look on disk.
  // One overlay per page, built on first use; bytes come from GET /api/image (brain-relative paths only, the server rejects the rest).
  // Closes from its button, the Escape key, or a click on the scrim; the close control is delegated, so re-rendering never unbinds it.
  const isImage = p => /\.(png|jpe?g|gif|webp|svg)$/i.test(String(p ?? "").split(/[?#]/)[0]);
  function lightbox(path) {
    let box = document.getElementById("lightbox");
    if (!box) {
      box = document.createElement("div"); box.className = "lightbox"; box.id = "lightbox"; box.hidden = true;
      box.innerHTML = `<figure class="card"><figcaption><button class="btn" type="button" data-close>close</button><code></code><span class="meta"></span></figcaption><img alt=""></figure>`;
      document.body.appendChild(box);
      const close = () => { box.hidden = true; };
      box.addEventListener("click", e => { if (e.target === box || e.target.closest("[data-close]")) close(); });
      document.addEventListener("keydown", e => { if (typing(e)) return; if (e.key === "Escape" && !box.hidden) close(); });
      const img = box.querySelector("img");
      img.onload = () => { box.querySelector(".meta").textContent = `${img.naturalWidth} \u00d7 ${img.naturalHeight}`; };
      img.onerror = () => { box.querySelector(".meta").textContent = "the server would not serve this file (not an image under the brain, or missing)"; };
    }
    box.querySelector("code").textContent = path; box.querySelector(".meta").textContent = "";
    box.querySelector("img").src = `/api/image?path=${encodeURIComponent(path)}`;
    box.hidden = false; box.querySelector("[data-close]").focus();
    return box;
  }

  // a picture inside rendered markdown, and a link to one, open in the image viewer wherever they appear (T-0021)
  document.addEventListener("click", e => {
    const im = e.target.closest("[data-img]"); if (!im) return;
    e.preventDefault(); lightbox(im.dataset.img);
  });

  // ---- propose mode (2026-09-08): a team copy of the brain proposes changes, it never edits in place ----
  // serve.py injects window.BV_MODE into every page ({mode:"normal"} or {mode:"propose", member, exported_at, ...}); /api/mode says the same.
  function mode() {
    const m = window.BV_MODE || { mode: "normal" };
    return Object.assign({ propose: m.mode === "propose" }, m);
  }
  // The feedback text every panel shows after a write that came back 202 {proposed:true, request:"requests/..."}.
  const proposedText = j => `Proposed, not applied · sent to ${j.request || "requests/"}`;

  // The strip under the header on every panel while in propose mode. Existing tokens only (.team-strip lives in viewer-tokens.css).
  function teamStrip() {
    const m = mode(); if (!m.propose || document.querySelector(".team-strip")) return null;
    const strip = document.createElement("div"); strip.className = "team-strip"; strip.setAttribute("role", "status");
    const exported = (m.exported_at || "").slice(0, 10) || "unknown date";
    strip.innerHTML = `<span>Team copy · proposing as ${esc(m.member || "unknown")} · exported ${esc(exported)}${m.source_commit ? ` (${esc(String(m.source_commit).slice(0, 7))})` : ""} · every save here becomes a request, nothing is edited in place</span><a href="/requests">requests</a>`;
    const bar = document.querySelector("header.bar");
    if (bar && bar.parentNode) bar.parentNode.insertBefore(strip, bar.nextSibling); else document.body.prepend(strip);
    return strip;
  }

  // "Propose a change": one component, reused by the dashboard and the Projects panel. A text box + Send -> POST /api/note
  // -> a `note` request about `target` (a brain-relative path, or "" for a general note). Returns the element, or null outside propose mode.
  function proposeBox(target, opts = {}) {
    if (!mode().propose) return null;
    const leaf = (target || "").split("/").filter(Boolean).pop();
    const box = document.createElement("details"); box.className = "propose-box";
    box.innerHTML = `<summary>${esc(opts.label || "propose a change")}${leaf ? ` <code>${esc(leaf)}</code>` : ""}</summary>
      <form><textarea rows="3" required placeholder="${esc(opts.placeholder || (leaf ? `what should change in ${leaf}, and why` : "what should change, and why"))}"></textarea>
      <div class="row"><button class="btn primary" type="submit">Send</button><span class="status-line"></span></div></form>`;
    const form = box.querySelector("form"), ta = box.querySelector("textarea"), status = box.querySelector(".status-line"), btn = box.querySelector("button");
    form.addEventListener("submit", async e => {
      e.preventDefault(); btn.disabled = true; status.textContent = "sending…";
      try {
        const r = await fetch("/api/note", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target: target || "", text: ta.value }) });
        const j = await r.json();
        if (!r.ok) { status.textContent = "refused: " + (j.error || r.status); }
        else { status.textContent = proposedText(j); ta.value = ""; if (opts.onSent) opts.onSent(j); }
      } catch (err) { status.textContent = "could not send: " + err.message; }
      btn.disabled = false;
    });
    return box;
  }
  document.addEventListener("DOMContentLoaded", teamStrip);

  // ---- ledger items: ONE set of components, used by /projects and by /people (2026-09-09, ideas E16) ----
  // Zak, 9/09: "the biggest thing is just making sure that questions go to the specific areas that they need to." A
  // question is answered wherever it is shown, so the row, the question card and the write all live here rather than
  // being drawn twice. Every control carries its project, because the People panel shows items from several ledgers at once.
  // ---- the Reader (2026-09-09, ledger T-0046) ----
  // ONE slugger, so a ledger's "-> file.md#7-undecided-the-conversation" and the Reader's own outline agree on what a
  // heading is called: lowercase, every run of non-alphanumerics becomes one dash, ends trimmed. The "-2" suffix for a
  // repeated heading is added by the page, which is the only place that sees the whole document at once.
  const slug = s => String(s ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  const readerHref = (path, frag) => `/reader?path=${encodeURIComponent(path)}` + (frag ? "#" + frag : "");
  // the Forge (2026-09-09, T-0041): every .canvas link in the app opens the design surface; the read-only viewer stays at /canvases
  const forgeHref = path => `/forge?path=${encodeURIComponent(path)}`;

  // ---- the glyphs: one drawing per kind of thing, shared by the glossary page and the Forge's tiles (2026-09-09) ----
  // Presentation only, and deliberately crude: these stand in until real screenshots exist beside each part (build doc
  // section 14). Drawn with the tokens; the one literal is the canvas palette's purple lightened to sit on cream, because
  // minds are purple everywhere in the app.
  const GLYPH_PURPLE = "#8a72d6";
  const glyphSvg = (inner, vb) => `<svg viewBox="${vb || "0 0 26 26"}" width="26" height="26" aria-hidden="true">${inner}</svg>`;
  const GLYPH = {
    dot: () => glyphSvg(`<circle cx="13" cy="13" r="5" fill="var(--ink-soft)"/>`),
    ring: () => glyphSvg(`<circle cx="13" cy="13" r="9" fill="none" stroke="var(--rule)" stroke-width="1.6"/><circle cx="13" cy="13" r="3" fill="var(--ink-soft)"/>`),
    module: () => glyphSvg(`<circle cx="13" cy="13" r="9" fill="none" stroke="var(--rule)" stroke-width="1.6"/><circle cx="13" cy="13" r="3.4" fill="var(--ink-soft)"/><circle cx="20" cy="6" r="3.4" fill="var(--open)"/>`),
    cell: () => glyphSvg(`<circle cx="13" cy="13" r="9" fill="none" stroke="var(--rule)" stroke-width="1.4"/><path d="M5 9 A9 9 0 0 1 13 4" fill="none" stroke="var(--open)" stroke-width="3" stroke-linecap="round"/><path d="M15 4 A9 9 0 0 1 21 9" fill="none" stroke="var(--open)" stroke-width="3" stroke-linecap="round"/><circle cx="13" cy="14" r="3" fill="var(--ink-soft)"/>`),
    holon: () => glyphSvg(`<circle cx="13" cy="13" r="10" fill="none" stroke="var(--rule)" stroke-width="1.4"/><circle cx="13" cy="13" r="6" fill="none" stroke="var(--rule-soft)" stroke-width="1.2"/><circle cx="13" cy="13" r="2.4" fill="var(--ink-soft)"/>`),
    part: () => glyphSvg(`<circle cx="13" cy="13" r="9.5" fill="none" stroke="var(--rule-soft)" stroke-width="1.2"/><rect x="9" y="9" width="8" height="8" rx="1.5" fill="none" stroke="var(--ink-soft)" stroke-width="1.6"/>`),
    port: () => glyphSvg(`<circle cx="11" cy="13" r="8.5" fill="none" stroke="var(--rule)" stroke-width="1.4"/><circle cx="19.5" cy="13" r="3.4" fill="var(--surface)" stroke="var(--rule)" stroke-width="1.4"/>`),
    // ⇄ in two arrows: a boundary information crosses in both directions, with a port on either wall
    adapter: () => glyphSvg(`<rect x="7.5" y="4.5" width="11" height="17" rx="2" fill="none" stroke="var(--ink-soft)" stroke-width="1.5"/><path d="M2 9.5 h5.5 M2 16.5 h5.5 M18.5 9.5 h5.5 M18.5 16.5 h5.5" stroke="var(--rule)" stroke-width="1.3" stroke-linecap="round"/><path d="M13.5 8 L16 10.6 L13.5 13.2" fill="none" stroke="var(--open)" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M12.5 13 L10 15.6 L12.5 18.2" fill="none" stroke="var(--open)" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>`),
    cable: () => glyphSvg(`<path d="M3 19 C9 19 9 7 15 7 L21 7" fill="none" stroke="var(--rule)" stroke-width="1.6"/><circle cx="3" cy="19" r="2.4" fill="var(--ink-soft)"/><path d="M18 4.6 L23 7 L18 9.4 z" fill="var(--rule)"/>`),
    bundle: () => glyphSvg(`<path d="M3 17 C9 17 9 6 16 6 L23 6" fill="none" stroke="var(--rule-soft)" stroke-width="1.2"/><path d="M3 20 C9 20 9 9 16 9 L23 9" fill="none" stroke="var(--rule-soft)" stroke-width="1.2"/><path d="M3 23 C9 23 9 12 16 12 L23 12" fill="none" stroke="var(--rule)" stroke-width="1.5"/><circle cx="11" cy="14" r="4.6" fill="var(--surface)" stroke="var(--rule)" stroke-width="1.3"/><text x="11" y="17" font-size="7" text-anchor="middle" fill="var(--ink-soft)">3</text>`),
    line: () => glyphSvg(`<path d="M3 17 L20 9" stroke="var(--rule)" stroke-width="1.6" fill="none"/><path d="M17 6.6 L22.5 8.4 L18.8 12.4 z" fill="var(--rule)"/>`),
    bubble: () => glyphSvg(`<path d="M3 17 L23 9" stroke="var(--rule-soft)" stroke-width="1.4" fill="none"/><circle cx="13" cy="13" r="4.6" fill="var(--open)"/>`),
    hook: () => glyphSvg(`<path d="M16 4 L16 14 A5 5 0 1 1 8 17.5" fill="none" stroke="var(--blocked)" stroke-width="2" stroke-linecap="round"/>`),
    agent: () => glyphSvg(`<circle cx="13" cy="13" r="7.5" fill="${GLYPH_PURPLE}" stroke="var(--rule)" stroke-width="1"/>`),
    store: () => glyphSvg(`<rect x="4" y="7" width="18" height="13" rx="2" fill="var(--done-tint)" stroke="var(--done)" stroke-width="1.5"/><path d="M7 12 h12 M7 15.5 h8" stroke="var(--done)" stroke-width="1.1"/>`),
    outside: () => glyphSvg(`<path d="M13 3.5 L21.4 8.2 L21.4 17.8 L13 22.5 L4.6 17.8 L4.6 8.2 z" fill="none" stroke="var(--ink-soft)" stroke-width="1.5"/>`),
    arc: () => glyphSvg(`<circle cx="13" cy="13" r="9" fill="none" stroke="var(--rule-soft)" stroke-width="1.1"/><path d="M4.6 10 A9 9 0 0 1 21.4 10" fill="none" stroke="var(--open)" stroke-width="3.4" stroke-linecap="round"/>`),
    core: () => glyphSvg(`<circle cx="13" cy="13" r="9" fill="none" stroke="var(--rule-soft)" stroke-width="1.1"/><rect x="9" y="9.5" width="8" height="7" rx="1.5" fill="var(--surface)" stroke="var(--ink-soft)" stroke-width="1.5"/>`),
    layers: () => glyphSvg(`<path d="M13 4 L22 9 L13 14 L4 9 z" fill="none" stroke="var(--ink-soft)" stroke-width="1.4"/><path d="M4 14 L13 19 L22 14" fill="none" stroke="var(--rule)" stroke-width="1.3"/>`),
    panel: () => glyphSvg(`<rect x="4" y="5.5" width="18" height="15" rx="2" fill="none" stroke="var(--rule)" stroke-width="1.5"/><path d="M4 10 h18" stroke="var(--rule)" stroke-width="1.2"/>`),
    canvas: () => glyphSvg(`<rect x="4" y="5.5" width="18" height="15" rx="2" fill="none" stroke="var(--rule-soft)" stroke-width="1.2"/><circle cx="10" cy="11" r="2.4" fill="none" stroke="var(--ink-soft)" stroke-width="1.3"/><circle cx="17" cy="15.5" r="2.4" fill="none" stroke="var(--ink-soft)" stroke-width="1.3"/><path d="M12 12 L15 14.6" stroke="var(--rule)" stroke-width="1.2"/>`),
    gate: () => glyphSvg(`<path d="M6 20 L6 9 A7 7 0 0 1 20 9 L20 20" fill="none" stroke="var(--ink-soft)" stroke-width="1.5"/><path d="M13 20 L13 11" stroke="var(--blocked)" stroke-width="1.6"/>`),
    ferry: () => glyphSvg(`<rect x="6" y="8.5" width="14" height="9" rx="2" fill="none" stroke="var(--ink-soft)" stroke-width="1.5"/><circle cx="4" cy="13" r="2.4" fill="var(--surface)" stroke="var(--rule)" stroke-width="1.3"/><circle cx="22" cy="13" r="2.4" fill="var(--surface)" stroke="var(--rule)" stroke-width="1.3"/>`),
    clock: () => glyphSvg(`<circle cx="13" cy="13" r="9" fill="none" stroke="var(--ink-soft)" stroke-width="1.5"/><path d="M13 7.5 L13 13 L17 15.5" fill="none" stroke="var(--ink-soft)" stroke-width="1.5" stroke-linecap="round"/>`),
    message: () => glyphSvg(`<path d="M4 7 h18 v11 h-11 l-4 3.5 v-3.5 h-3 z" fill="none" stroke="var(--open)" stroke-width="1.5" stroke-linejoin="round"/>`),
    output: () => glyphSvg(`<circle cx="13" cy="13" r="9" fill="none" stroke="var(--rule-soft)" stroke-width="1.1"/><circle cx="21" cy="13" r="4" fill="#ec7500" fill-opacity=".85" stroke="var(--surface)" stroke-width="1.2"/>`),
    blob: () => glyphSvg(`<path d="M3 13 A10 10 0 0 1 9 4.2" fill="none" stroke="var(--rule)" stroke-width="1.5"/><circle cx="17.5" cy="13" r="6.2" fill="var(--done-tint)" stroke="var(--done)" stroke-width="1.6"/><path d="M14.6 11.4 h5.8 M14.6 14.4 h4" stroke="var(--done)" stroke-width="1.1"/>`),
    packet: () => glyphSvg(`<rect x="5" y="8" width="16" height="10" rx="2" fill="var(--mouth-tint)" stroke="var(--mouth)" stroke-width="1.5"/><path d="M5 8 L13 14 L21 8" fill="none" stroke="var(--mouth)" stroke-width="1.2"/>`),
    package: () => glyphSvg(`<path d="M4 9.5 L13 5 L22 9.5 L22 18 L13 22.5 L4 18 z" fill="var(--mouth-tint)" stroke="var(--mouth)" stroke-width="1.5" stroke-linejoin="round"/><path d="M4 9.5 L13 14 L22 9.5 M13 14 L13 22.5" fill="none" stroke="var(--mouth)" stroke-width="1.2"/>`),
  };
  // glossary term anchor -> glyph. Anything unlisted falls back to its group's glyph.
  const GLYPH_BY_TERM = { node: "dot", module: "module", component: "ring", part: "part", port: "port", line: "line", bubble: "bubble",
    adapter: "adapter", cable: "cable", bundle: "bundle",
    cell: "cell", holon: "holon", hook: "hook", "primary-current": "bubble", dispatch: "line", ferryman: "ferry", agent: "agent",
    "assumed-output": "output", output: "output", field: "dot", package: "package", blob: "blob", packet: "packet", ledger: "store", panel: "panel", canvas: "canvas", registry: "store", log: "store",
    intent: "canvas", build: "layers", runtime: "bubble", "womb-phase": "layers", forge: "cell", stage: "layers",
    screen: "arc", form: "arc", dashboard: "arc", message: "message", step: "core", schedule: "clock", gate: "gate",
    skill: "agent", prompt: "agent", store: "store", catalogue: "store", app: "outside", service: "outside",
    person: "outside", "in-flight-bubble": "bubble" };
  const GLYPH_BY_GROUP = { "the things on a canvas": "ring", "the things that move and decide": "line",
    "the things that record and organize": "store", "the layers of a drawing": "layers", "the parts you can drop in": "part" };
  const glyph = name => (GLYPH[name] || GLYPH.dot)();
  const isDoc = p => /\.md$/i.test(String(p ?? "").split(/[?#]/)[0]);
  // the button every drawer carries: the same file, opened by its headings, where its list items can be struck and moved
  const readerLink = (path, label) => isDoc(path)
    ? `<a class="btn" href="${readerHref(path)}" title="open this document in the Reader: an outline, folding sections, strike and reorder on every list item">${esc(label || "open in Reader")}</a>` : "";

  // Who the pages treat as "me". serve.py injects it into every page from viewer-settings.json's `owner` key
  // (the same key skills/brain-tasks/tasks.py reads), so nothing here is bound to one person's name.
  const OWNER = String(window.BV_OWNER || "@me");
  const ownerBadge = o => `<span class="badge ${o === OWNER ? "owner-zak" : ""}">${esc(String(o || "").replace(/^@/, ""))}</span>`;
  function fileLink(l) {
    const wl = /^\[\[(.+)\]\]$/.exec(l), target = wl ? wl[1].split("|")[0] : l;
    const label = wl ? wl[1].split("|").pop() : (String(l).split("/").filter(Boolean).pop() || l);
    // A link with a "#" on a .md is a SECTION ASK (2026-09-09): it names the portion of the document that needs Zak.
    // Until 0.53.0 it was a real <a> to the Reader, so the same-looking link left the page on one item and opened
    // beside it on the next (Zak, 2026-09-29: "why don't things show up in the side viewer when I click on them in the
    // projects area and instead take me to the md page?"). Now every document link opens in the drawer, and the
    // drawer scrolls to the section (data-frag, read by the shared jump in drawerOpen / the pending-frag hook).
    const hash = target.indexOf("#");
    if (hash > 0 && isDoc(target.slice(0, hash))) {
      const path = target.slice(0, hash), frag = target.slice(hash + 1);
      const leaf = wl ? label : (path.split("/").filter(Boolean).pop() || path);   // the name, then the heading, never both spelled out twice
      return `<span class="filelink" data-open="${esc(path)}" data-frag="${esc(frag)}" title="${esc(target)} — opens beside the page, at that section">${esc(leaf)} <span class="frag">#${esc(frag)}</span></span>`;
    }
    return `<span class="filelink" data-open="${esc(target)}" title="${esc(target)}">${esc(label)}</span>`;
  }

  // ---- the shared read drawer (0.53.0, 2026-09-29) ----
  // One rule: a document link opens in the drawer on every page, scrolled to its section when the link names one;
  // "open in Reader" is the button inside the drawer for the full page. Since 0.54.1 (T-0152) the pages that keep a
  // global openFile (projects, people, today and the rest) only delegate to drawerOpen below, passing the section, and
  // their own click handlers still own their close button; this file records the section and jumps once the drawer
  // has painted. A page with no openFile of its own (the Reader, the Files page, home, the call screen) gets this
  // drawer straight from the capture handler, created on first use.
  let PENDING_FRAG = "";
  const fragKey = s => String(s ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
  function drawerJump(frag, tries) {
    const d = document.getElementById("drawer"); if (!frag) return;
    const want = fragKey(frag);
    const h = d && !d.hidden ? [...d.querySelectorAll("h1,h2,h3,h4,h5,h6")].find(x => x.id === frag || fragKey(x.textContent) === want) : null;
    if (h) { h.scrollIntoView({ block: "start" }); h.classList.add("jumped"); setTimeout(() => h.classList.remove("jumped"), 2500); PENDING_FRAG = ""; return; }
    if ((tries || 0) < 30) setTimeout(() => drawerJump(frag, (tries || 0) + 1), 100);
  }
  function drawerEl() {
    let d = document.getElementById("drawer");
    if (!d) { d = document.createElement("aside"); d.className = "drawer auto"; d.id = "drawer"; d.hidden = true; document.body.appendChild(d); }
    const hd = document.querySelector("body > header, header.top, header");   // below the page header, not over it
    if (d.classList.contains("auto") && hd) d.style.top = Math.max(0, Math.round(hd.getBoundingClientRect().bottom)) + "px";
    return d;
  }
  // 0.54.1 (T-0152): this is the ONLY drawer body. The twelve pages that carried their own openFile (projects, people,
  // today, chat, the canvases and the rest) hand it here in one line, so a document reads the same beside every page:
  // "reading…" while it loads, a JSON file pretty-printed, the error when there is one, the touched date, "open in
  // Reader" carrying the section, and `edit` where GET /api/file says the file is editable (PUT /api/file with the
  // status line, then the page's own load() when it defines one, then the file reopened). The prep/card folds people.html
  // used to apply in here are gone: the drawer shows a document the way the Reader does, a flowing page.
  const pageId = () => (document.querySelector("nav.panels") || { dataset: {} }).dataset.page || "";
  const drawerHead = (path, extra) => `<div class="dh"><button class="btn" id="closeDrawer" type="button">close</button><code>${esc(path)}</code>${extra || ""}</div>`;
  let DRAWER_SEQ = 0;   // a newer open (or the edit box) wins over a read still in flight
  async function drawerOpen(path, frag) {
    const d = drawerEl(), seq = ++DRAWER_SEQ; d.hidden = false;
    path = String(path ?? "").trim(); frag = frag || "";
    const paint = html => { if (seq === DRAWER_SEQ) d.innerHTML = html; return seq === DRAWER_SEQ; };
    const fail = html => paint(drawerHead(path) + `<div class="empty">${html}</div>`);
    paint(drawerHead(path) + `<div class="empty">reading…</div>`);
    if (!path) { fail("no file named"); return; }
    if (!path.includes("/")) {
      let j; try { j = await (await fetch(`/api/resolve?name=${encodeURIComponent(path)}`)).json(); } catch (e) { j = { error: `could not resolve ${path}: ${e.message}` }; }
      if (seq !== DRAWER_SEQ) return;
      if (j.path) path = j.path;
      else { fail(esc(j.error || "could not resolve " + path) + (j.candidates ? "<br>" + j.candidates.map(esc).join("<br>") : "")); return; }
    }
    if (path.endsWith("/")) { fail(`a folder: <code>${esc(path)}</code>${/references\/$/.test(path) ? " · the source images live here" : ""}`); return; }
    if (/\.canvas$/i.test(path)) { d.hidden = true; location.href = `/canvases?open=${encodeURIComponent(path)}`; return; }   // the canvas viewer, as every page drawer did before 0.54.1; it hands an outside canvas to the Forge itself
    if (isImage(path)) { d.hidden = true; lightbox(path); return; }
    let r, j;
    try { r = await fetch(`/api/file?path=${encodeURIComponent(path)}`); j = await r.json(); }
    catch (e) { fail(`could not read ${esc(path)}: ${esc(e.message)}`); return; }
    if (seq !== DRAWER_SEQ) return;
    if (j.error || !r.ok) {
      // a team copy, or a request naming a file it would create: the target is simply not on this machine
      const away = r.status === 404 && (mode().propose || pageId() === "requests") ? `<br><span class="meta">the target is not in this copy (a private file, or one the request would create)</span>` : "";
      fail(esc(j.error || `the server answered ${r.status}`) + away); return;
    }
    let body;
    if (/\.json$/i.test(path)) { let t = j.text; try { t = JSON.stringify(JSON.parse(j.text), null, 1); } catch (e) {} body = `<pre>${esc(t)}</pre>`; }
    else if (isDoc(path)) body = `<article class="md">${md(j.text, { base: path.split("/").slice(0, -1).join("/") })}</article>`;
    else body = `<pre>${esc(j.text)}</pre>`;
    const full = isDoc(path) ? `<a class="btn" href="${readerHref(path, frag)}" title="the full page in the Reader${frag ? ", at this section" : ""}">open in Reader</a>` : "";
    const edit = j.editable ? `<button class="btn" id="editBtn" type="button" title="change this file here; the save is written and logged">edit</button>` : "";
    const touched = j.mtime ? `<span class="meta">touched ${esc(String(j.mtime).slice(0, 10))}</span>` : "";
    paint(drawerHead(path, full + edit + touched + `<span class="status-line" id="saveStatus" style="margin:0"></span>`) + body);
    d.scrollTop = 0;
    const eb = d.querySelector("#editBtn"); if (eb) eb.addEventListener("click", () => drawerEdit(path, frag, j.text));
    if (pageId() !== "glossary") glScan(d);   // the glossary page marks its own terms and never its drawer
    if (frag) drawerJump(frag);
  }
  // the edit box: the file's text, save and cancel; the PUT is the one people.html used (GET /api/file's `editable` decides)
  function drawerEdit(path, frag, text) {
    const d = drawerEl(); DRAWER_SEQ++; d.hidden = false;
    d.innerHTML = drawerHead(path, `<button class="btn primary" id="saveBtn" type="button">save</button><button class="btn" id="cancelBtn" type="button">cancel</button><span class="status-line" id="saveStatus" style="margin:0"></span>`)
      + `<textarea class="edit" id="editor" spellcheck="false"></textarea>`;
    const ta = d.querySelector("#editor"); ta.value = text ?? ""; d.scrollTop = 0;
    d.querySelector("#cancelBtn").addEventListener("click", () => drawerOpen(path, frag));
    d.querySelector("#saveBtn").addEventListener("click", async ev => {
      const btn = ev.currentTarget, out = d.querySelector("#saveStatus"); btn.disabled = true; out.textContent = "saving…";
      try {
        const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`, { method: "PUT", headers: { "Content-Type": "text/plain; charset=utf-8" }, body: ta.value });
        const jj = await res.json().catch(() => ({}));
        if (!res.ok) out.textContent = "refused: " + (jj.error || res.status);
        else if (jj.proposed) out.textContent = proposedText(jj);
        else {
          out.textContent = `saved · ${jj.bytes} bytes · ${jj.log}`;
          // the page re-reads what the file feeds (people: its cards and preps), then the file reopens as saved
          if (typeof window.load === "function") { try { await window.load(); } catch (e) {} }
          setTimeout(() => drawerOpen(path, frag), 700);
        }
      } catch (err) { out.textContent = "could not save: " + err.message; }
      btn.disabled = false;
    });
  }
  document.addEventListener("click", e => {
    const own = typeof window.openFile === "function";
    const close = e.target.closest("#closeDrawer");
    if (close && !own) { const d = document.getElementById("drawer"); if (d) d.hidden = true; return; }
    const o = e.target.closest(".filelink[data-open]");
    const w = !o && e.target.closest("a.wikilink");
    if (!o && !w) return;
    const frag = o ? (o.dataset.frag || "") : ((w.dataset.wikilink || "").split("#")[1] || "");
    if (own) { PENDING_FRAG = frag; if (frag) drawerJump(frag, 1); return; }   // the page's own openFile paints the drawer; this only jumps
    // no openFile on this page: the drawer takes the link, and the page's own bubble handler (the Reader's wikilink
    // navigation) does not run on top of it
    if (w) { const t = (w.dataset.wikilink || "").split("#")[0].trim(); if (!t) return; if (/\.canvas$/i.test(t)) return; e.preventDefault(); e.stopPropagation(); drawerOpen(t.endsWith(".md") || /\.[a-z0-9]+$/i.test(t) ? t : t + ".md", frag); return; }
    e.preventDefault(); e.stopPropagation(); drawerOpen(o.dataset.open, frag);
  }, true);
  // ---- the ledger id, one gesture off the reading line (2026-09-18, Zak) ----
  // Zak, 9/18: "I don't love the T-0087, for my ADHD it makes me space out and get distracted, far better for you to
  // have it on the backend." So a row reads its words, its project, its age and its links, and the id sits in the
  // corner behind three faint dots: hover it, or press it on a touch screen, and the id and the ledger it lives on
  // open beside it. The id is still IN the DOM -- `data-id` on that corner, the ledger as `data-path` -- so anything
  // that reads the page still has it, and no API payload changed.
  const idTag = (id, path) => !id ? "" : `<span class="idtag" data-id="${esc(id)}"${path ? ` data-path="${esc(path)}"` : ""} tabindex="0" role="button" aria-label="the ledger id for this item" title="its ledger id"><span class="dots" aria-hidden="true">⋮</span><span class="idpop"><code>${esc(id)}</code>${path ? `<span class="p filelink" data-open="${esc(path)}" title="${esc(path)} — open it">${esc(path)}</span>` : ""}</span></span>`;
  const idTagOf = e => (e && e.target && e.target.closest) ? e.target.closest(".idtag") : null;
  document.addEventListener("click", e => {
    const t = idTagOf(e);
    for (const el of document.querySelectorAll(".idtag.on")) if (el !== t) el.classList.remove("on");
    if (t && !e.target.closest(".idpop")) t.classList.toggle("on");   // a press inside the popover is a link, not a toggle
  });
  document.addEventListener("keydown", e => {
    const t = idTagOf(e);
    if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); t.classList.toggle("on"); return; }
    if (e.key === "Escape") for (const el of document.querySelectorAll(".idtag.on")) el.classList.remove("on");
  });

  // ---- a ledger code inside ledger text reads as the thing it names (2026-09-21, viewer Q-0028) ----
  // Zak: "If something is called T-0202 or anything with a T in front, can we please have a link to the task itself?
  // Like at least something, or even a name... I am a human, I do not recognize the numbers, in fact, I am a
  // neurodivergent one and it pisses me off and makes me tired when I see it, so lets make a decision around this."
  // The decision: every T-#### / Q-#### written into an item's own words renders as a LINK to that item on Projects,
  // and its face is the item's first six words. The code itself lives in the title attribute, where it is there when he
  // wants it and out of the reading line when he does not -- the same rule the corner id tag follows. Nothing is
  // written back to any ledger file; this is a reading rule and it lives here so the four pages cannot disagree.
  const REF_RE = /\b([TQ]-\d{4})\b/g;
  const LEDGER = new Map();          // "<project>/<id>" -> { id, project, kind, text }
  function learnLedger(data) {
    let n = 0;
    for (const p of (data && data.projects) || []) {
      if (!p.exists) continue;
      for (const g of p.groups || []) for (const i of g.items || []) {
        LEDGER.set(p.id + "/" + i.id, { id: i.id, project: p.id, projectName: p.name || p.id, kind: i.kind, text: i.text || "",
          state: i.state || "", note: i.note || "", due: i.due || "", done: i.done || "", answer: i.answer || "" }); n++;
      }
    }
    if (n) repaintRefs();
    return n;
  }
  // ids run from 0001 on EVERY ledger (T-0107), so the item's OWN project is asked first; a code from another ledger
  // resolves only when exactly one loaded ledger carries it, because guessing here links him to the wrong item.
  function findRef(id, project) {
    if (project && LEDGER.has(project + "/" + id)) return LEDGER.get(project + "/" + id);
    const hits = [];
    for (const v of LEDGER.values()) if (v.id === id) hits.push(v);
    return hits.length === 1 ? hits[0] : null;
  }
  // 0.55.0 (asked 2026-09-21, again 2026-10-02): a reference is a CHIP, visibly not prose -- the kind word, then the
  // item's first words trimmed to about 40 characters, the full text in the tooltip -- and a press opens a PREVIEW card
  // beside it instead of navigating. Zak, 9/21: "When clicking on the linked things here, it doesn't look good." Zak,
  // 10/02: "it takes me to another question page, I don't really know what that means or why its doing that." The
  // preview names the kind, its ledger, the id, the state, the full text, the note and the due date, with one small
  // "open in its ledger" link that goes where the old link went. One preview at a time; Escape, a press outside, or a
  // second press on the chip closes it. An unresolved code stays a plain span with the code.
  function refFace(text) {
    const t = String(text || "").replace(/\s+/g, " ").trim();
    if (t.length <= 40) return t;
    const cut = t.slice(0, 40), sp = cut.lastIndexOf(" ");
    return (sp > 24 ? cut.slice(0, sp) : cut).replace(/[\s,;:.(-]+$/, "") + "…";
  }
  const refHref = it => `/projects?id=${encodeURIComponent(it.project)}#${it.kind === "question" ? "q" : "t"}-${encodeURIComponent(it.project)}-${encodeURIComponent(it.id)}`;
  const refKind = it => it.kind === "question" ? "question" : "task";
  function refHTML(id, project) {
    const it = findRef(id, project);
    const d = ` data-ref="${esc(id)}" data-refpj="${esc(project || "")}"`;
    if (!it) return `<span class="idref"${d} title="not on a loaded ledger">${esc(id)}</span>`;
    const full = hideLineRefs(it.text);
    const closed = it.state === "done" || it.state === "answered" ? " closed" : "";
    return `<span class="idref on ${it.kind === "question" ? "k-q" : "k-t"}${closed}"${d} role="button" tabindex="0" aria-haspopup="dialog" title="${esc(full)}"><span class="idref-k">${refKind(it)}</span><span class="idref-t">${esc(refFace(full))}</span></span>`;
  }
  // the preview card: one element, made on open, appended to the body so no card's overflow clips it, fixed to the viewport
  let REFPOP = null, REFPOP_FOR = null;
  function refPopClose() {
    if (REFPOP) REFPOP.remove();
    if (REFPOP_FOR) REFPOP_FOR.classList.remove("open");
    REFPOP = null; REFPOP_FOR = null;
  }
  function refPopOpen(chip) {
    const it = findRef(chip.dataset.ref, chip.dataset.refpj || "");
    refPopClose();
    if (!it) return;
    const meta = [`<code>${esc(it.id)}</code>`];
    if (it.state) meta.push(`<span class="badge ${esc(it.state)}">${esc(it.state)}${it.done ? " " + esc(it.done) : ""}</span>`);
    if (it.due) meta.push(`<span class="badge">due ${esc(it.due)}</span>`);
    const pop = document.createElement("div");
    pop.className = "refpop"; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", refKind(it) + " " + it.id);
    pop.innerHTML = `<div class="rp-h"><span class="rp-k">${refKind(it)}</span> on <span class="rp-l">${esc(it.projectName || it.project)}</span></div>
      <div class="rp-m">${meta.join("")}</div>
      <div class="rp-t">${esc(hideLineRefs(it.text))}</div>
      ${it.answer ? `<div class="rp-n"><span class="kicker">answer</span> ${esc(hideLineRefs(it.answer))}</div>` : ""}
      ${it.note ? `<div class="rp-n"><span class="kicker">note</span> ${esc(hideLineRefs(it.note))}</div>` : ""}
      <div class="rp-f"><a href="${refHref(it)}">open in its ledger</a></div>`;
    document.body.appendChild(pop);
    REFPOP = pop; REFPOP_FOR = chip; chip.classList.add("open");
    const r = chip.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    const left = Math.min(Math.max(8, r.left), vw - w - 8);
    let top = r.bottom + 6;
    if (top + h > vh - 8 && r.top - h - 6 > 8) top = r.top - h - 6;    // no room below: open above the chip
    pop.style.left = left + "px"; pop.style.top = top + "px";   // fixed to the viewport: every page scrolls its own panel
  }
  if (typeof document !== "undefined") {
    // capture phase, so a row's or a card's own click handler never sees a press that was meant for a chip
    document.addEventListener("click", e => {
      const chip = e.target.closest && e.target.closest(".idref.on[data-ref]");
      if (chip) {
        e.preventDefault(); e.stopPropagation();
        if (REFPOP_FOR === chip) refPopClose(); else refPopOpen(chip);
        return;
      }
      if (REFPOP && (!(e.target.closest && e.target.closest(".refpop")) || e.target.closest(".refpop a"))) setTimeout(refPopClose, 0);
    }, true);
    document.addEventListener("keydown", e => {
      if (e.key === "Escape" && REFPOP) { e.stopPropagation(); refPopClose(); return; }
      const chip = e.target.closest && e.target.closest(".idref.on[data-ref]");
      if (chip && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); if (REFPOP_FOR === chip) refPopClose(); else refPopOpen(chip); }
    }, true);
    window.addEventListener("resize", () => refPopClose());
    // the panel under it scrolled, so the card would float away from its chip: close it (a scroll inside the card is its own)
    document.addEventListener("scroll", e => { if (REFPOP && !(e.target && e.target.closest && e.target.closest(".refpop"))) refPopClose(); }, true);
  }
  // Transcript line references (L612, L591 to L603, L726, L738) are an agent's evidence trail, never his reading line.
  // Zak, 2026-09-25: "why the fuck are the L612 and all of those fucking words still showing up when I have written
  // about 1000000000000 times TO STOP DOING THAT figure out a better way to display it". The way: the reference stays
  // in the file, where an agent can follow it, and no page shows it. Lint rule ids (lint L15) are not line refs.
  // 0.50.1: every pattern stays on its own line ([ \t], never \s), each removal takes the space before it (so nothing is
  // left to collapse), and "[ ]" is never touched. md() runs this over a whole document: \s let "L612\n- 2026-09-24" eat
  // the next bullet, the space collapse took a nested list's indent and a code block's alignment, and "- [ ]" became
  // "- []" (md.test claims 5, 6 and 8). "at L726," goes before the tail rule so it does not leave "at,".
  const LREF = String.raw`L\d{1,4}(?:[ \t]*(?:to|,|and|-)[ \t]*L?\d{1,4})*`;
  const LREF_AT    = new RegExp(String.raw`\b[Aa]t[ \t]+${LREF}\b,?[ \t]*`, "g");                  // at L726, he said
  const LREF_PAREN = new RegExp(String.raw`[ \t]*\((?:${LREF})\)`, "g");                       // (L612) / (L591 to L603)
  // 0.55.1 (T-0284): a Source column separates with " · " and a table cell ends on "|", so a reference before either is a
  // tail too ("Mike, 7/24 L524 · superseded", "verbatim L524 |"), and a " ·" in front of one goes with it ("a · L524 · b"
  // reads "a · b"). A reference that OPENS a cell or a line before a " ·" takes the separator after it instead (LEAD).
  const LREF_LEAD  = new RegExp(String.raw`(?<=^|\|)([ \t]*)${LREF}[ \t]*·[ \t]*`, "gm");          // | L524 · superseded
  const LREF_TAIL  = new RegExp(String.raw`(?:,|[ \t]+·)?[ \t]*(?<!lint\s)\b${LREF}(?=[ \t]*[)\];:.,·|]|[ \t]*$)`, "gm"); // ..., L257) / ... L41) / 7/24 L524 ·
  const LREF_RANGE = new RegExp(String.raw`[ \t]*\bL\d{1,4}[ \t]*(?:to|-)[ \t]*L?\d{1,4}\b`, "g");  // L798 to L819 anywhere
  function hideLineRefs(text) {
    return String(text == null ? "" : text)
      .replace(/[ \t]*<!--[\s\S]*?-->/g, "")
      .replace(LREF_AT, "").replace(LREF_PAREN, "").replace(LREF_LEAD, "$1").replace(LREF_TAIL, "").replace(LREF_RANGE, "")
      .replace(/\([ \t]*[,;][ \t]*/g, "(").replace(/[ \t]*\([ \t]*\)/g, "").replace(/(?<!\[)[ \t]+([,;:.)\]])/g, "$1");
  }
  // THE one door every ledger body goes through: the line refs hidden, escaped, then the codes become links.
  // 0.55.1 (T-0284): {inline: true, base} keeps the line's own markdown (bold, code, links) and turns the codes into
  // chips in its text only, never inside a tag, a code span or a link label. A code written right after a project in a
  // code span ("`pf-build` T-0048", the way a card names another ledger's item) is looked up on THAT ledger. A card's
  // Where it stands line goes through this door on the Reader and on People, where it used to show the code raw.
  function ledgerText(text, project, opts) {
    if (!(opts && opts.inline)) return esc(hideLineRefs(text)).replace(REF_RE, m => refHTML(m, project));
    let lastCode = null, inA = 0;
    return inline(text, opts.base).split(/(<code>[\s\S]*?<\/code>|<[^>]*>)/).map(seg => {
      if (!seg) return seg;
      const c = seg.match(/^<code>([\s\S]*?)<\/code>$/);
      if (c) { lastCode = c[1]; return seg; }
      if (seg[0] === "<") { if (/^<a[\s>]/i.test(seg)) inA++; else if (/^<\/a>/i.test(seg)) inA = Math.max(0, inA - 1); lastCode = null; return seg; }
      if (inA) { lastCode = null; return seg; }
      const pj = lastCode && /^[a-z0-9][a-z0-9-]*$/.test(lastCode) ? lastCode : "";
      lastCode = null;
      return seg.replace(REF_RE, (m, id, off) => refHTML(m, pj && !seg.slice(0, off).trim() ? pj : project));
    }).join("");
  }
  // A page can paint before its ledgers are read (the review cards do), so a code left unresolved is upgraded in place
  // the moment a read lands rather than sitting there as a dead token.
  function repaintRefs(root) {
    for (const el of (root || document).querySelectorAll("span.idref[data-ref]:not(.on)")) {
      if (!findRef(el.dataset.ref, el.dataset.refpj || "")) continue;
      el.outerHTML = refHTML(el.dataset.ref, el.dataset.refpj || "");
    }
  }
  // one read, shared, for a page that renders ledger text without loading the ledgers itself
  let LEDGER_PRIMED = null;
  function primeLedgers() {
    return LEDGER_PRIMED || (LEDGER_PRIMED = dayLoad().then(j => { learnLedger(j); return j; }).catch(() => null));
  }


  // ---- a box that grows with what is written in it (2026-09-18, Zak) ----
  // Zak, 9/18: "Answered another review thing with an extended answer, can we please allow for more room for
  // responses?" Every box a sentence goes into carries `class="grow"`: two lines to start where it is a reply, taller
  // as the text is, up to half the window and then it scrolls, and no cap on the words. Enter makes a newline;
  // Ctrl+Enter (Cmd+Enter) sends, wherever sending is one thing -- a box inside a form submits it, and a page whose
  // send is a choice (the review cards' three presses) wires its own.
  function growBox(ta) {
    if (!ta) return;
    const cap = Math.max(120, Math.round(window.innerHeight * 0.5));
    ta.style.height = "auto";
    const want = ta.scrollHeight + 2;
    ta.style.height = Math.min(want, cap) + "px";
    ta.style.overflowY = want > cap ? "auto" : "hidden";
  }
  const growOf = e => (e && e.target && e.target.closest) ? e.target.closest("textarea.grow") : null;
  document.addEventListener("input", e => growBox(growOf(e)));
  document.addEventListener("focusin", e => growBox(growOf(e)));
  document.addEventListener("keydown", e => {
    const ta = growOf(e);
    if (!ta || e.key !== "Enter" || !(e.ctrlKey || e.metaKey)) return;
    const f = ta.closest("form"); if (!f) return;
    e.preventDefault();
    if (f.requestSubmit) f.requestSubmit(); else f.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
  });

  const personChips = i => (i.people || []).map(s => `<span class="badge person" data-person="${esc(s)}" title="this item is about ${esc(s)}">${esc(s.replace(/-/g, " "))}</span>`).join("");

  // one ledger mutation -> PUT /api/tasks?project=… (the server calls tasks.py: clock-stamped, validated, logged)
  async function ledgerAct(project, payload) {
    const r = await fetch(`/api/tasks?project=${encodeURIComponent(project)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const j = await r.json().catch(() => ({}));
    return { ok: r.ok, status: r.status, json: j,
             message: !r.ok ? "refused: " + (j.error || r.status) : j.proposed ? proposedText(j) : `${j.id} ${payload.action} · written to the ledger and logged` };
  }

  // ---- the note box (2026-09-10, ledger T-0078 + T-0077; on every task row 2026-09-18, T-0193) ----
  // Zak, 9/10: a task waiting on him is not always a box to tick -- sometimes the answer is a sentence, and ticking it
  // would close work that is not done. A note writes the item's `note:` line through the same tasks.py the checkboxes
  // use (POST /api/reply composes it and stamps the date) and LEAVES THE ITEM OPEN. A checkbox may carry one along:
  // whatever is sitting in the box is written first, then the item closes.
  // 2026-09-18, T-0193 -- Zak: "it also seems like I can't leave notes on some of these tasks so I don't really know
  // what to do about them." The box used to appear only on an OPEN task of HIS, so a task on Claude, or one already
  // closed, had nowhere to say anything. Every task row has it now; only a question is left out, because a question is
  // answered in its own box and the answer is a different field.
  const replyBox = (i, p) => `<form class="replyrow" data-reply="${esc(i.id)}" data-project="${esc(p)}"${i.ledger ? ` data-ledger="${esc(i.ledger)}"` : ""}>
      <textarea class="grow" rows="1" placeholder="leave a note; the item stays as it is" title="Enter makes a new line; Ctrl+Enter (Cmd+Enter) writes the note"></textarea><button class="btn" type="submit">note</button></form>`;
  const canReply = (i, opts) => opts.reply !== false && i.kind === "task";
  // the note under the row, without a reload (T-0193): the line the server composed is put straight into the row's own
  // `keep` block, which is the same element a repaint would draw. An empty answer changes nothing.
  function showNote(form, note) {
    const li = form && form.closest("li"); if (!li || !note) return;
    let keep = li.querySelector(".keep");
    if (!keep) {
      keep = document.createElement("div");
      keep.className = "keep";
      form.parentNode.insertBefore(keep, form.previousElementSibling && form.previousElementSibling.classList.contains("holdrow") ? form.previousElementSibling : form);
    }
    keep.innerHTML = `<span class="kicker">note</span> ${esc(note)}`;
  }
  async function replyAct(project, id, text, ledger) {
    const r = await fetch("/api/reply", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project, id, text, ledger: ledger || undefined }) });
    const j = await r.json().catch(() => ({}));
    return { ok: r.ok, status: r.status, json: j,
             message: !r.ok ? "refused: " + (j.error || r.status) : j.proposed ? proposedText(j)
                      : `${id} · your note is on the ledger and the item stays as it is` };
  }
  // the words sitting in the reply box of whatever item this element belongs to (a checkbox carries them along)
  function pendingReply(el) {
    const li = el && el.closest("li"); const f = li && li.querySelector("form[data-reply]");
    const text = f ? f.querySelector("textarea").value.trim() : "";
    return text ? { form: f, id: f.dataset.reply, project: f.dataset.project, ledger: f.dataset.ledger, text } : null;
  }
  // one wiring for every page that renders ledger items: the reply box submits here, and a checkbox hands its pending
  // words over before it closes anything. `onDone` is the page's own refresh.
  function wireReplies(root, opts = {}) {
    (root || document).addEventListener("submit", async e => {
      const f = e.target.closest("form[data-reply]"); if (!f) return;
      if (f.closest("aside.quest")) return;   // the quest log floats over every page and wires its own boxes
      e.preventDefault();
      const ta = f.querySelector("textarea"), text = ta.value.trim(); if (!text) return;
      const btn = f.querySelector("button"); btn.disabled = true; ta.disabled = true;
      if (opts.status) opts.status("writing to the ledger…");
      const res = await replyAct(f.dataset.project, f.dataset.reply, text, f.dataset.ledger);
      ta.disabled = false; btn.disabled = false;
      if (res.ok) { ta.value = ""; showNote(f, res.json && res.json.note); if (opts.onDone) await opts.onDone(res); }
      // after the page has re-rendered, not before: a panel that redraws its status line would wipe the message
      if (opts.status) opts.status(res.message);
    });
    return { pending: pendingReply, reply: replyAct };
  }

  // ---- on hold (2026-09-10, ledger T-0108) ----
  // Zak: deprioritizing a task, putting it down for a few days, instead of checking off something that is not done. A
  // held task carries `until:` a day that has not arrived: it is still open and still owed, it just leaves the lists
  // that ask for it now and comes back on its own. The server holds them back (open_for_zak); these are the controls.
  const HOLD_DAYS = 3;
  const heldNow = (i, today) => !!(i && i.mark === " " && i.until && i.until > (today || isoToday()));
  // the LOCAL day, not the UTC one: toISOString() after 5pm Pacific reads tomorrow, which offered "hold until" a day
  // past what the server would write and a minimum of the day after next
  const isoDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const isoToday = () => isoDay(new Date());
  const plusDays = n => { const d = new Date(); d.setDate(d.getDate() + n); return isoDay(d); };
  // beside the checkbox on every open task of Zak's: one press puts it down for three days, and the date box beside it
  // picks another day. On a held task the same place says when it comes back and hands it back early.
  function holdControl(i, p, opts = {}) {
    if (!i || i.kind === "question" || i.mark !== " " || i.owner !== OWNER) return "";
    if (heldNow(i, opts.today)) return "";
    return `<span class="holdrow"><button type="button" class="btn hold" data-hold="${esc(i.id)}" data-project="${esc(p)}"
        title="put this down for ${HOLD_DAYS} days; it comes back on its own, still open">hold</button>
      <input type="date" class="holdpick" data-hold-until="${esc(i.id)}" data-project="${esc(p)}" min="${esc(plusDays(1))}" value="${esc(plusDays(HOLD_DAYS))}"
        title="the day it comes back"></span>`;
  }
  const holdBadge = (i, p, opts = {}) => heldNow(i, opts.today)
    ? `<span class="badge held">on hold until ${esc(i.until)}</span><button type="button" class="btn" data-resume="${esc(i.id)}" data-project="${esc(p)}" title="bring this back now">bring back</button>`
    : "";
  async function holdAct(project, id, until) {
    return ledgerAct(project, until === null ? { action: "reopen", id } : { action: "hold", id, until: until || null });
  }
  // one delegated wiring per page, the way the reply boxes are wired: the pages differ only in what they reload after
  function wireHolds(root, opts = {}) {
    const run = async (project, id, until) => {
      const res = await holdAct(project, id, until);
      if (res.ok && opts.onDone) await opts.onDone(res);      // the reload first: a page that repaints its status line would wipe the message
      if (opts.status) opts.status(res.message);
      if (res.ok) refreshBadges();
      return res;
    };
    root.addEventListener("click", async e => {
      const h = e.target.closest("[data-hold]");
      if (h) { e.preventDefault(); await run(h.dataset.project, h.dataset.hold, undefined); return; }   // no date: the tool's own few days
      const r = e.target.closest("[data-resume]");
      if (r) { e.preventDefault(); await run(r.dataset.project, r.dataset.resume, null); return; }
    });
    root.addEventListener("change", async e => {
      const d = e.target.closest("[data-hold-until]");
      if (!d || !d.value) return;
      await run(d.dataset.project, d.dataset.holdUntil, d.value);
    });
  }

  // ---- the day (2026-09-15, ledger T-0150) ----
  // Zak: "I need a place to be able to see the questions that are prohibiting us from moving forwards." The Today page
  // is composed IN THE BROWSER out of one read every page already makes -- GET /api/projects, which carries every
  // ledger the registry names and the server's own `today` -- so nothing is computed on the server and nothing is
  // stored anywhere (rules 1 and 2). It lives here rather than in the page because the home's "today" link paints its
  // count from the same function: the number on the link and the page it opens cannot disagree.
  const DAY_RECENT_DAYS = 7;
  const dayBack = (iso, n) => { const p = String(iso || "").split("-").map(Number); return p[0] ? isoDay(new Date(p[0], p[1] - 1, p[2] - n)) : ""; };
  // newest first, everywhere on this page: asked (or created) descending, then id descending
  const byNewestDay = (a, b) => String(b.created || "").localeCompare(String(a.created || "")) || String(b.id || "").localeCompare(String(a.id || ""));
  function dayModel(data) {
    const today = (data && data.today) || isoToday();
    const items = [];
    for (const p of (data && data.projects) || []) {
      if (!p.exists) continue;
      for (const g of p.groups || []) for (const i of g.items || [])
        items.push(Object.assign({}, i, { project: p.id, projectName: p.name, milestone: g.name, ledger: p.path }));
    }
    // what a question blocks: an open task writes `blocked:` in its own words, which may be the question's id alone
    // ("blocked:Q-0002") or a sentence naming it, so the id is looked for INSIDE that text -- and only on the same
    // ledger, because ids run from Q-0001 on every file.
    const holdsUp = q => items.filter(i => i.kind === "task" && i.mark !== "x" && i.blocked
                                        && i.project === q.project && String(i.blocked).includes(q.id));
    const questions = items.filter(i => i.kind === "question" && i.mark === "?" && (i.to || OWNER) === OWNER)
      .sort(byNewestDay).map(q => Object.assign({}, q, { holds: holdsUp(q).map(i => i.text) }));
    const cut = dayBack(today, DAY_RECENT_DAYS);
    const recent = questions.filter(q => String(q.created || "") >= cut), older = questions.filter(q => String(q.created || "") < cut);
    // ---- the blocking ones first (2026-09-16, ledger T-0163) ----
    // Zak: "I want to be able to see the most important questions up in an easy place to access first... those are the
    // primary ones blocking." Important is not a judgement made here: a question is blocking when an OPEN TASK on its own
    // ledger carries `blocked:` naming it, which is exactly the relation `tasks.py block` writes and `answer` releases.
    // Most held up first, then newest, so the one question that frees three pieces of work sits above the one that frees
    // one. The rest keep the order they had, newest first, split at the seven-day line the page already folds on.
    const blocking = questions.filter(q => q.holds.length)
      .sort((a, b) => b.holds.length - a.holds.length || byNewestDay(a, b));
    const rest = questions.filter(q => !q.holds.length);
    const restRecent = rest.filter(q => String(q.created || "") >= cut), restOlder = rest.filter(q => String(q.created || "") < cut);
    // due today or earlier: an open task past its day or on it, a held task whose day has come (it is back), and a
    // question carrying a due date. Each item once, whichever reason came first, with the reason kept for the row.
    const due = [], seen = new Set();
    const add = (i, why, sort) => { const k = i.project + "/" + i.id; if (seen.has(k)) return; seen.add(k); due.push(Object.assign({}, i, { why, daysort: sort })); };
    for (const i of items) {
      const open = i.mark === " ";
      if (i.kind === "task" && open && i.due && i.due < today) add(i, "overdue", "0" + i.due);
      else if (i.kind === "task" && open && i.due === today) add(i, "due today", "1");
      else if (i.kind === "task" && open && i.until && i.until <= today) add(i, "back today", "2");
      else if (i.kind === "question" && i.mark === "?" && i.due && i.due <= today) add(i, i.due < today ? "overdue" : "due today", i.due < today ? "0" + i.due : "1");
    }
    due.sort((a, b) => String(a.daysort).localeCompare(String(b.daysort)) || byNewestDay(a, b));
    const closed = items.filter(i => (i.kind === "task" && i.done === today) || (i.kind === "question" && i.answered === today)).sort(byNewestDay);
    return { today, cut, recentDays: DAY_RECENT_DAYS, items, questions, recent, older, blocking, rest, restRecent, restOlder, due, closed,
             counts: { waiting: questions.length, older: older.length, due: due.length, closed: closed.length,
                       blocking: blocking.length, rest: rest.length, restOlder: restOlder.length,
                       total: questions.length + due.length } };
  }
  // the one read the page and the home's link both make
  async function dayLoad() {
    const r = await fetch("/api/projects");
    const j = await r.json();
    if (!r.ok || j.error) throw new Error(j.error || ("the server answered " + r.status));
    learnLedger(j);                                   // every code in every body can now read as the item it names
    return j;
  }

  // a task row: the checkbox writes done / reopen. `opts.project` is the ledger it belongs to; `opts.today` marks overdue.
  function itemRow(i, opts = {}) {
    const p = opts.project || i.project || "";
    const overdue = i.mark === " " && i.due && opts.today && i.due < opts.today;
    const meta = [ownerBadge(i.owner), `<span>${esc(i.created)}</span>`];   // the id is the corner tag now (2026-09-18), never the reading line
    if (opts.showProject && (i.projectName || i.project)) meta.push(`<span class="badge">${esc(i.projectName || i.project)}</span>`);
    if (i.due) meta.push(`<span class="badge ${overdue ? "overdue" : ""}">due ${esc(i.due)}</span>`);
    if (i.done) meta.push(`<span class="badge done">done ${esc(i.done)}</span>`);
    if (i.blocked) meta.push(`<span class="badge blocked">blocked · ${esc(i.blocked)}</span>`);
    if (heldNow(i, opts.today)) meta.push(holdBadge(i, p, opts));
    if (i.unblocked) meta.push(`<span class="badge">freed by ${esc(i.unblocked)}</span>`);
    for (const t of i.tags || []) meta.push(`<span class="tag">#${esc(t)}</span>`);
    if (!opts.hidePeople) meta.push(personChips(i));
    for (const l of i.links || []) meta.push(fileLink(l));
    return `<li class="item ${i.state}${heldNow(i, opts.today) ? " held" : ""}" id="t-${esc(p)}-${esc(i.id)}">${idTag(i.id, i.ledger || opts.ledger || "")}<input type="checkbox" ${i.mark === "x" ? "checked" : ""} data-id="${esc(i.id)}" data-project="${esc(p)}" title="${i.mark === "x" ? "reopen" : "mark done"}"><div><div class="t">${ledgerText(i.text, p)}</div><div class="m">${meta.join("")}</div>${i.note ? `<div class="keep"><span class="kicker">note</span> ${ledgerText(i.note, p)}</div>` : ""}${holdControl(i, p, opts)}${canReply(i, opts) ? replyBox(i, p) : ""}</div></li>`;
  }

  // ---- the document a question points at, one press away (2026-09-23, T-0247) ----
  // Zak, answering Q-0043 (the six Owen questions, linked to their file): "This wasn't showing up in the chat." The
  // link was there, but only as a small grey filename in the card's header line among the badges, and the six questions
  // themselves lived in the file. So a question that links a document now carries a press under its words that opens
  // that document in the Reader, named by the document's own first heading (read once per file, filled in after the
  // card is drawn; the filename shows until it arrives). Links that are not documents stay in the header as before.
  const docTarget = l => {
    const wl = /^\[\[(.+)\]\]$/.exec(l), t = wl ? wl[1].split("|")[0] : String(l || "");
    const h = t.indexOf("#"), path = h > 0 ? t.slice(0, h) : t;
    return isDoc(path) ? { path, frag: h > 0 ? t.slice(h + 1) : "" } : null;
  };
  function askDocs(links) {
    const ds = (links || []).map(docTarget).filter(Boolean);
    if (!ds.length) return "";
    // 0.53.0: a span the drawer opens, not a link to the Reader (the one rule for document links; see drawerOpen)
    return `<div class="qdoc">${ds.map(d => `<span class="btn askdoc filelink" data-open="${esc(d.path)}"${d.frag ? ` data-frag="${esc(d.frag)}"` : ""} data-askdoc="${esc(d.path)}" title="${esc(d.path)}${d.frag ? " #" + esc(d.frag) : ""} · opens beside the page${d.frag ? ", at that section" : ""}"><span class="askdoc-k">open</span> <span class="askdoc-t">${esc(d.path.split("/").filter(Boolean).pop() || d.path)}</span>${d.frag ? ` <span class="frag">#${esc(d.frag)}</span>` : ""}</span>`).join("")}</div>`;
  }
  const DOC_HEADS = new Map();
  const docHead = path => {
    if (!DOC_HEADS.has(path)) DOC_HEADS.set(path, fetch(`/api/file?path=${encodeURIComponent(path)}`).then(r => r.ok ? r.json() : {}).then(j => {
      const m = /^#{1,6}\s+(.+)$/m.exec(String((j && j.text) || ""));
      return m ? m[1].replace(/\[\[([^\]|]+\|)?([^\]]+)\]\]/g, "$2").replace(/[*_`]/g, "").trim() : "";
    }).catch(() => ""));
    return DOC_HEADS.get(path);
  };
  function askDocFill(root) {
    for (const a of (root || document).querySelectorAll(".askdoc[data-askdoc]:not([data-headed])")) {
      a.dataset.headed = "1";
      if (/^archive\//.test(a.dataset.askdoc)) continue;   // /api/file refuses archive/; the filename stays the label
      docHead(a.dataset.askdoc).then(t => { const el = a.querySelector(".askdoc-t"); if (t && el) el.textContent = t; });
    }
  }
  let askDocTimer = null;
  function askDocWatch() {
    if (!window.MutationObserver || !document.body) return;
    new MutationObserver(() => { clearTimeout(askDocTimer); askDocTimer = setTimeout(() => askDocFill(document), 60); })
      .observe(document.body, { childList: true, subtree: true });
  }
  if (typeof document !== "undefined") {
    if (document.body) askDocWatch(); else document.addEventListener("DOMContentLoaded", askDocWatch);
  }

  // a question: answered in place, which frees every task blocked by it (tasks.py does that half)
  function questionCard(q, opts = {}) {
    const p = opts.project || q.project || "", open = q.mark === "?";
    const head = [ownerBadge(q.owner), "<span>asks</span>", ownerBadge(q.to || OWNER), `<span>${esc(q.created)}</span>`];
    if (opts.showProject && (q.projectName || q.project)) head.push(`<span class="badge">${esc(q.projectName || q.project)}</span>`);
    if (!opts.hidePeople) head.push(personChips(q));
    // the id carries the ledger as well as the item, because two ledgers can now be read stacked and their ids run
    // from Q-0001 on each file (T-0107)
    return `<div class="q ${open ? "" : "answered"}" id="q-${esc(p)}-${esc(q.id)}">${idTag(q.id, q.ledger || opts.ledger || "")}
      <div class="qh">${head.join("")}${(q.links || []).filter(l => !docTarget(l)).map(fileLink).join("")}${(q.tags || []).map(t => `<span class="tag">#${esc(t)}</span>`).join("")}</div>
      <div class="qt">${ledgerText(q.text, p)}</div>
      ${askDocs(q.links)}
      ${open ? `<form data-q="${esc(q.id)}" data-project="${esc(p)}"><textarea class="grow" rows="2" placeholder="answer" title="Enter for a new line, Ctrl+Enter sends" required></textarea><button class="btn primary" type="submit">Answer</button></form>`
             : `<div class="ans"><strong>${esc(String(q.to || OWNER).replace(/^@/, ""))}, ${esc(q.answered || "")}:</strong> ${esc(q.answer || "")} <button class="btn" data-reopen="${esc(q.id)}" data-project="${esc(p)}" style="margin-left:8px">reopen</button></div>`}
    </div>`;
  }

  // ---- the notification counts in the top bar (2026-09-09): open items waiting on Zak, from GET /api/badges ----
  // Zak, 9/09: "the bubbles can have notifications symbols on them." The nav is where they live until the bubbles home exists.
  let BADGES = null;
  async function badges(force) {
    if (BADGES && !force) return BADGES;
    try {
      const r = await fetch("/api/badges");
      BADGES = r.ok ? await r.json() : null;
    } catch (e) { BADGES = null; }
    return BADGES;
  }
  function paintNavCounts(b) {
    if (!b) return;
    const put = (href, n, title) => {
      const a = document.querySelector(`nav.panels a[href="${href}"]`); if (!a) return;
      const old = a.querySelector(".navcount"); if (old) old.remove();
      if (!n) return;
      const s = document.createElement("span"); s.className = "navcount"; s.textContent = n; s.title = title; a.appendChild(s);
    };
    put("/", b.waiting, `${b.total_questions} questions and ${b.total_zak_tasks} tasks are waiting on you`);
    put("/people", b.people_items, `${b.people_items} open items are about someone with a card`);
    put("/projects", b.waiting, `${b.total_questions} questions and ${b.total_zak_tasks} tasks are waiting on you`);
  }
  const refreshBadges = async () => paintNavCounts(await badges(true));
  document.addEventListener("DOMContentLoaded", () => badges().then(paintNavCounts));

  // ---- drag an edge to make a panel wider (2026-09-09, ledger T-0060) ----
  // Zak: "Side panel should be resizable". The handle is a FIXED strip laid over the panel's edge rather than a child of
  // it, because every panel that needs this scrolls its own content and a child handle would scroll away with it. The
  // width is remembered per browser under bv.w.<key>; every localStorage touch is wrapped, so a private window or blocked
  // site data costs the remembered width and nothing else. Double-click the handle to put it back where it started.
  const WKEY = k => "bv.w." + k;
  const lsGet = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  const lsDel = k => { try { localStorage.removeItem(k); } catch (e) {} };
  function resizable(el, key, opts) {
    if (!el || el.dataset.bvResize) return null;
    const o = Object.assign({ edge: "right", min: 180, max: 900, apply: null, title: "" }, opts || {});
    el.dataset.bvResize = "1";
    const bar = document.createElement("div");
    bar.className = "resizer " + (o.edge === "left" ? "on-left" : "on-right");
    bar.title = o.title || "drag to resize · double-click to put it back";
    document.body.appendChild(bar);
    const clamp = w => Math.max(o.min, Math.min(o.max, Math.round(w)));
    const width = () => el.getBoundingClientRect().width;
    const setW = w => { w = clamp(w); if (o.apply) o.apply(w); else el.style.width = w + "px"; lsSet(WKEY(key), String(w)); place(); };
    function place() {
      const r = el.getBoundingClientRect();
      if (!r.width && !r.height) { bar.hidden = true; return; }
      bar.hidden = false;
      bar.style.top = r.top + "px"; bar.style.height = r.height + "px";
      bar.style.left = ((o.edge === "left" ? r.left : r.right) - 3) + "px";
    }
    const saved = parseInt(lsGet(WKEY(key)) || "", 10);
    const start = width();
    if (saved && Math.abs(saved - start) > 1) { if (o.apply) o.apply(clamp(saved)); else el.style.width = clamp(saved) + "px"; }
    let from = null;
    bar.addEventListener("mousedown", e => {
      e.preventDefault(); from = { x: e.clientX, w: width() };
      document.body.classList.add("resizing"); bar.classList.add("on");
    });
    window.addEventListener("mousemove", e => {
      if (!from) return;
      setW(from.w + (o.edge === "left" ? from.x - e.clientX : e.clientX - from.x));
    });
    window.addEventListener("mouseup", () => { if (!from) return; from = null; document.body.classList.remove("resizing"); bar.classList.remove("on"); });
    bar.addEventListener("dblclick", () => { lsDel(WKEY(key)); if (o.apply) o.apply(null); else el.style.width = ""; place(); });
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    try { new ResizeObserver(place).observe(el); } catch (e) {}
    try { new MutationObserver(place).observe(el, { attributes: true, attributeFilter: ["hidden", "style", "class"] }); } catch (e) {}
    place(); setTimeout(place, 120); setTimeout(place, 600);
    return { place, set: setW };
  }

  // ---- file search, on every page (2026-09-17, ledger T-0158) ----
  // Zak: "a file search system that could work kind of like Obsidian but more for our purpose". One box in the top bar,
  // one route behind it (GET /api/search: names first, then text, live files only, capped at 50), and a hit opens the
  // Reader at the line it was found on. "/" or Ctrl+K puts the cursor in it; Escape closes the list; the arrows walk it.
  let fsBox = null, fsList = null, fsRows = [], fsAt = -1, fsTimer = 0, fsSeq = 0;
  function fsPlace() {
    if (!fsBox || !fsList || fsList.hidden) return;
    const r = fsBox.getBoundingClientRect();
    fsList.style.top = (r.bottom + 4) + "px";
    fsList.style.left = Math.max(8, Math.min(r.left, window.innerWidth - 480)) + "px";
  }
  function fsClose() { if (fsList) { fsList.hidden = true; fsAt = -1; } }
  // a hit opens where that kind of file is read: a drawing in the Forge, everything else in the Reader at its line
  const fsHref = r => /\.canvas$/i.test(r.path) ? forgeHref(r.path)
                    : readerHref(r.path) + (r.line > 1 ? "&line=" + r.line : "");
  function fsPaint(j) {
    if (!fsList) return;
    fsRows = (j && j.items) || [];
    fsAt = -1;
    if (!fsRows.length) {
      fsList.innerHTML = `<div class="fsnone">${esc(j && j.error ? j.error : `nothing in the live files matches “${(j && j.q) || ""}”`)}</div>`;
    } else {
      fsList.innerHTML = `<div class="fshead">${fsRows.length}${j.capped ? ` of ${j.count}` : ""} hit${fsRows.length === 1 ? "" : "s"} · ${j.files} files read · ${j.ms} ms · names first, then text</div>`
        + fsRows.map((r, i) => `<a class="fsrow" href="${fsHref(r)}" data-i="${i}">
             <span class="p">${esc(r.path)}</span><span class="w">${esc(r.why)}${r.line > 1 ? ` · line ${r.line}` : ""}${r.matches > 1 ? ` · ${r.matches}` : ""}</span>
             <span class="s">${esc(r.snippet || "")}</span></a>`).join("");
    }
    fsList.hidden = false; fsPlace();
  }
  async function fsRun(q) {
    const mine = ++fsSeq;
    try {
      const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const j = await r.json();
      if (mine === fsSeq) fsPaint(j);
    } catch (e) { if (mine === fsSeq) fsPaint({ q, items: [], error: "search failed: " + e.message }); }
  }
  function fsWalk(d) {
    if (fsList.hidden || !fsRows.length) return;
    fsAt += d;
    if (fsAt < 0) fsAt = fsRows.length - 1;
    if (fsAt >= fsRows.length) fsAt = 0;
    [...fsList.querySelectorAll(".fsrow")].forEach((a, i) => a.classList.toggle("on", i === fsAt));
    const on = fsList.querySelector(".fsrow.on"); if (on) on.scrollIntoView({ block: "nearest" });
  }
  function mountSearch() {
    const bar = document.querySelector("header.bar");
    if (!bar || bar.querySelector("form.filesearch")) return null;
    const f = document.createElement("form");
    f.className = "filesearch";
    f.innerHTML = `<input type="search" name="q" placeholder="find a file or a line…" autocomplete="off" spellcheck="false"
        title="search every live brain file by name and by text (archive/ and the token files are never read). / or Ctrl+K puts the cursor here; a hit opens in the Reader at its line">`;
    const spacer = bar.querySelector(".spacer");
    if (spacer) bar.insertBefore(f, spacer.nextSibling); else bar.appendChild(f);
    fsBox = f.querySelector("input");
    fsList = document.createElement("div");
    fsList.className = "fsres"; fsList.hidden = true;
    document.body.appendChild(fsList);
    f.addEventListener("submit", e => { e.preventDefault(); const on = fsList.querySelector(".fsrow.on"); if (on) location.href = on.href; else if (fsBox.value.trim().length > 1) fsRun(fsBox.value.trim()); });
    fsBox.addEventListener("input", () => {
      clearTimeout(fsTimer);
      const q = fsBox.value.trim();
      if (q.length < 2) return fsClose();
      fsTimer = setTimeout(() => fsRun(q), 240);
    });
    fsBox.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { e.preventDefault(); fsWalk(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); fsWalk(-1); }
      else if (e.key === "Escape") { fsClose(); fsBox.blur(); }
    });
    fsBox.addEventListener("focus", () => { if (fsRows.length && fsBox.value.trim().length > 1) { fsList.hidden = false; fsPlace(); } });
    document.addEventListener("click", e => { if (!e.target.closest(".fsres") && !e.target.closest("form.filesearch")) fsClose(); });
    window.addEventListener("resize", fsPlace);
    document.addEventListener("keydown", e => {
      if (typing(e)) return;
      if (e.key === "/" || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k")) { e.preventDefault(); fsBox.focus(); fsBox.select(); }
    });
    return f;
  }

  // ---- the back button (2026-09-10, ledger T-0061) ----
  // The app moves without reloading -- a project picked in the rail, a file in the drawer, a section in the Reader --
  // and every page does that with history.replaceState, so the browser's own back button leaves the app instead of
  // stepping back inside it. This keeps the app's own trail of places, in this tab only (sessionStorage, nothing in the
  // brain): a page load records where you are, the button walks back down that trail, and whatever is open ON TOP of
  // the page (a picture, a read drawer) closes first so one press never skips a step.
  const TRAIL = "bv.trail", TRAIL_POP = "bv.trail.pop", TRAIL_MAX = 40;
  const ssGet = k => { try { return sessionStorage.getItem(k); } catch (e) { return null; } };
  const ssSet = (k, v) => { try { sessionStorage.setItem(k, v); } catch (e) {} };
  const ssDel = k => { try { sessionStorage.removeItem(k); } catch (e) {} };
  const herePath = () => location.pathname + location.search + location.hash;
  const trailRead = () => { try { return JSON.parse(ssGet(TRAIL) || "[]"); } catch (e) { return []; } };
  const trailWrite = a => ssSet(TRAIL, JSON.stringify(a.slice(-TRAIL_MAX)));
  const placeLabel = () => {
    const t = (document.title || "").trim() || (document.querySelector("nav.panels") || { dataset: {} }).dataset.page || "the app";
    const frag = decodeURIComponent(location.hash.replace(/^#/, "")).replace(/-/g, " ").trim();
    return frag ? `${t} · ${frag}` : t;
  };
  const backHooks = [];
  // a page with its own idea of "one step back" registers it here; the newest hook is asked first and a hook that
  // returns true has handled the press (nothing navigates)
  const onBack = fn => { backHooks.push(fn); return fn; };
  function trailPush(label) {
    // a hash-only move (the Reader's sections) changes the URL without reloading, so a press of Back lands here rather
    // than in trailLand: the flag decides which of the two this is, and the trail never ping-pongs between two sections
    if (ssGet(TRAIL_POP)) return trailLand();
    const a = trailRead(), u = herePath(), last = a[a.length - 1];
    if (last && last.u === u) last.t = label || last.t || placeLabel();
    else a.push({ u, t: label || placeLabel() });
    trailWrite(a); paintBack(); return a;
  }
  function trailLand() {      // one call per page load: a press of Back pops the trail, anything else pushes onto it
    if (ssGet(TRAIL_POP)) {
      ssDel(TRAIL_POP);
      const a = trailRead(), u = herePath();
      while (a.length && a[a.length - 1].u !== u) a.pop();
      if (!a.length) a.push({ u, t: placeLabel() });
      trailWrite(a); paintBack(); return a;
    }
    return trailPush();
  }
  const backTarget = () => { const a = trailRead(); return a.length > 1 ? a[a.length - 2] : null; };
  function goBack() {
    const lb = document.getElementById("lightbox");
    if (lb && !lb.hidden) { lb.hidden = true; paintBack(); return true; }
    for (let i = backHooks.length - 1; i >= 0; i--) { try { if (backHooks[i]()) { paintBack(); return true; } } catch (e) {} }
    const dr = document.querySelector("aside.drawer");
    if (dr && !dr.hidden) { dr.hidden = true; paintBack(); return true; }
    const t = backTarget();
    if (t) { ssSet(TRAIL_POP, "1"); location.href = t.u; return true; }
    if (history.length > 1) { history.back(); return true; }
    return false;
  }
  function paintBack() {
    const b = document.querySelector("header.bar button.back"); if (!b) return;
    const t = backTarget(), lb = document.getElementById("lightbox"), dr = document.querySelector("aside.drawer");
    const onTop = (lb && !lb.hidden) ? "the picture" : (dr && !dr.hidden) ? "the open file" : null;
    b.disabled = !(onTop || t || history.length > 1);
    b.title = onTop ? `close ${onTop} and stay here` : t ? `back to ${t.t}` : b.disabled ? "nothing to go back to yet" : "back";
  }
  function mountBack() {
    const bar = document.querySelector("header.bar"); if (!bar || bar.querySelector("button.back")) return null;
    const b = document.createElement("button");
    b.type = "button"; b.className = "btn back"; b.innerHTML = `<span aria-hidden="true">‹</span> back`;
    b.onclick = () => { if (!goBack()) paintBack(); };
    const first = bar.querySelector("img.mark") || bar.querySelector("h1");
    if (first) bar.insertBefore(b, first); else bar.prepend(b);
    paintBack(); return b;
  }
  document.addEventListener("DOMContentLoaded", trailLand);

  // ---- the top nav, ONE definition for every page (2026-09-09, the straight line step 1) ----
  // Home is the chat (Zak: "we can make chat the home"); the mentee content dashboard moved to /mentee. A page declares
  // itself with <nav class="panels" data-page="projects"></nav> and this paints it, so the order changes in one place.
  // In a team copy chat does not exist (rules 4): the copy's home stays the dashboard at "/" and no chat link is drawn.
  // GROUPED 2026-09-17 (ledger T-0160). Zak, 9/16 and again 9/17: the nav is "too all over the place" and "things can
  // be consolidated a little bit better." The routes are unchanged and every one of them is still one press away; what
  // changed is that they are now in the three piles the ledger item named. WORK is the day's queues, BRAIN is the
  // material, MORE is the rest. `reader` moved out of the faint aside links, which disappeared below 1560px, into
  // BRAIN where the item puts it -- so the team folder (requests) and the Reader are both reachable from every page at
  // any width. The group labels are the only new chrome and they go at phone width.
  const NAV = [
    { group: "", items: [
      { key: "home", href: "/", label: "home", title: "the board: today's calls, what is waiting on you, what is running, what closed. Each tile opens the page behind it, and the edit button rearranges the board" },
    ] },
    { group: "work", items: [
      { key: "today", href: "/today", label: "today", title: "the day on one page: the questions blocking work, what is due today or was due earlier, what comes back today, and what closed today" },
      { key: "projects", href: "/projects", label: "projects" },
      { key: "findings", href: "/findings", label: "findings", title: "Findings: what the night agent, brain-lint, the dispatcher and the handoffs have filed on the ledgers — open items carrying a source tag, the most-repeated and the oldest first" },
      { key: "review", href: "/review", label: "review", title: "Review: Claude's proposals as cards you rate with one press — good, off or wrong, a line only if you want one" },
      { key: "people", href: "/people", label: "people" },
    ] },
    { group: "brain", items: [
      { key: "reader", href: "/reader", label: "reader", title: "read a document by its headings: strike and reorder its list items, ask about one section. Opens the build doc when no file is named" },
      { key: "files", href: "/files", label: "files", title: "every file in the brain in one table, newest first: sort by any column, filter by folder, type or path, and open a file here instead of in a desktop program" },
      { key: "maps", href: "/maps", label: "maps", title: "the live maps: existing canvases read against real state (what each node is bound to, what moved in the last 14 days). Replaced the moving graph at /map on 2026-09-09" },
      { key: "canvases", href: "/canvases", label: "canvases" },
      { key: "forge", href: "/forge", label: "forge", title: "design a system before it exists: cells, typed parts and labelled lines, saved back to the canvas file" },
      { key: "agents", href: "/agents", label: "agents", title: "every conversation and session on this machine drawn as a bubble, its sub-agents attached: what is running, what it answered, and the handoffs between them" },
      { key: "chat", href: "/chat", label: "chat", title: "talk to the brain's agents: the main agent, or one fixed to a project. It was the home page until 2026-09-21, when home became the board" },
    ] },
    { group: "more", items: [
      { key: "mentee", href: "/mentee", label: "mentee content" },
      { key: "requests", href: "/requests", label: "requests", title: "the shared folder: what another person's viewer sent you, and every change a team copy has proposed" },
      { key: "studio", href: "/studio", label: "studio", title: "the image studio: write a brief, pick a provider and model, make pictures, star the candidates, edit one, attach it to a ledger item (T-0235)" },
      { key: "status", href: "/status", label: "status" },
    ] },
  ];
  function nav(page) {
    const el = document.querySelector("nav.panels"); if (!el) return null;
    page = page || el.dataset.page || "";
    let groups = NAV;
    if (mode().propose) {   // a team copy has no chat: its home stays the dashboard, and no chat link is drawn
      groups = [{ group: "", items: [{ key: "mentee", href: "/", label: "mentee content" }] }]
        .concat(NAV.map(g => ({ group: g.group, items: g.items.filter(i => i.key !== "home" && i.key !== "mentee" && i.key !== "chat") })));
    }
    el.innerHTML = groups.filter(g => g.items.length).map(g =>
        `<span class="navgroup">${g.group ? `<span class="navlbl">${esc(g.group)}</span>` : ""}`
        + g.items.map(i => `<a href="${i.href}"${i.key === page ? ' class="on"' : ""}${i.title ? ` title="${esc(i.title)}"` : ""}>${esc(i.label)}</a>`).join("")
        + `</span>`).join("")
      + (page === "glossary" ? "" : `<a class="aside" href="/glossary?from=${encodeURIComponent(page)}" title="every word this app uses, with a definition, an example and a picture">glossary</a>`);
    el.dataset.page = page;
    mountBack();   // one step back inside the app, left of the title (T-0061)
    mountSearch(); // find any brain file by name or by text, from any page (T-0158)
    // the read drawer takes a drag on its left edge, like the Reader's rail (T-0060); one width for every page
    const dr = document.querySelector("aside.drawer");
    if (dr) resizable(dr, "drawer", { edge: "left", min: 320, max: Math.max(520, Math.round(window.innerWidth * 0.9)), title: "drag to make the drawer wider or narrower · double-click to put it back" });
    // the "?" button (2026-09-21, the home redesign). Zak: "make the help page like a thing that you can just click so
    // you can get an idea of what is going on on the page." It opens a panel that says, in plain words, what THIS page
    // is and what its parts are, read from help.json; the glossary is one press further in, from inside the panel.
    // Before this it opened the glossary straight away, which answered a word and never the page.
    const bar = document.querySelector("header.bar");
    if (bar && page !== "glossary" && !bar.querySelector("button.help")) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "btn help"; b.textContent = "?";
      b.title = "what this page is, and what each part of it does";
      b.onclick = () => helpOpen();
      bar.appendChild(b);
    }
    return el;
  }

  // ---- the "?" panel: what this page is, in plain words (2026-09-21) ----
  // One entry per route in skills/brain-viewer/help.json, served at GET /api/help. A page adds nothing and declares
  // nothing: the panel finds its own route. A page that wants to add to it sets BV.help.extra to a function returning
  // {title, rows:[{name, line}]} -- which is how the home board names the tiles it is carrying.
  const HELP = { data: null, el: null, extra: null };
  async function helpLoad() {
    if (HELP.data) return HELP.data;
    try { HELP.data = await (await fetch("/api/help")).json(); }
    catch (e) { HELP.data = { pages: {}, error: e.message }; }
    return HELP.data;
  }
  const helpEntry = (route) => ((HELP.data || {}).pages || {})[route || location.pathname] || null;
  function helpClose() { if (HELP.el) { HELP.el.remove(); HELP.el = null; } }
  async function helpOpen() {
    if (HELP.el) return helpClose();
    const d = await helpLoad(), e = helpEntry(), page = (document.querySelector("nav.panels") || { dataset: {} }).dataset.page || "";
    const extra = typeof HELP.extra === "function" ? HELP.extra() : null;
    const rows = list => `<ul class="hp">${list.map(r => `<li><b>${esc(r.name)}</b> ${esc(r.line)}</li>`).join("")}</ul>`;
    const el = document.createElement("aside");
    el.className = "card helppanel";
    el.innerHTML = `<div class="hh"><b>${esc(document.title || "this page")}</b><button class="btn" type="button" data-hx>close</button></div>`
      + (e ? `<p class="hw">${esc(e.what)}</p>` + ((e.parts || []).length ? rows(e.parts) : "")
           : `<p class="hw">${esc(d.error ? "the help file could not be read: " + d.error : "No entry written for this page yet.")}</p>`)
      + (extra && extra.rows && extra.rows.length ? `<p class="kicker">${esc(extra.title || "on this page")}</p>` + rows(extra.rows) : "")
      + `<a class="hg" href="#">every word this app uses, with a definition</a>`;
    el.querySelector("[data-hx]").onclick = helpClose;
    el.querySelector(".hg").onclick = ev => { ev.preventDefault(); helpClose(); openGlossary(null, page); };
    document.body.appendChild(el); HELP.el = el;
    return el;
  }
  document.addEventListener("keydown", e => { if (e.key === "Escape" && HELP.el && !typing(e)) helpClose(); });

  // ---- the glossary (2026-09-09, the straight line step 2, ledger T-0040) ----
  // Zak: "we should have words be highlightable with their definitions behind it... my working memory can be really
  // slow sometimes... having vocabulary essentially hyperlinked via a hover would be tremendously useful." One source
  // (brain-viewer-holon/brain-viewer-glossary.md, parsed by serve.py), read once per page here, and every page asks for
  // a scan after it renders. A term is wrapped ONCE PER BLOCK so a page does not turn into underline soup, and never
  // inside code, a link, an input, a badge or a summary, so nothing that was clickable stops being clickable.
  const GL = { ready: null, terms: [], keys: [], groups: [], byNeedle: new Map(), byAnchor: new Map(), byName: new Map(), re: null, available: false };
  // The explicit marker (2026-09-24, T-0196): {{back}} or {{Where it stands}} written by an agent that MEANS the term.
  // It renders as the plain words, underlined, for ANY term or alias -- including the everyday words that are off the
  // auto list, which is the point: a word like back is underlined only where someone said it is the term.
  const GL_MARK = /\{\{([^{}\n]{2,48})\}\}/g;
  const GL_SKIP = "code,pre,kbd,a,button,input,textarea,select,option,summary,label,svg,script,style,.gl,.badge,.tag,.id,.filelink,.navcount,[data-open],[data-person],[data-wikilink],[contenteditable],.no-gloss";
  const GL_BLOCK = "p,li,td,th,h2,h3,h4,h5,h6,blockquote,figcaption,dd,dt,.t,.qt,.desc,.m,.msg,.note,.empty,div,section,article";
  const reEsc = s => String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  function glLoad() {
    if (GL.ready) return GL.ready;
    GL.ready = (async () => {
      try {
        const r = await fetch("/api/glossary"); const j = r.ok ? await r.json() : null;
        if (!j) return GL;
        GL.available = !!j.available; GL.note = j.note || ""; GL.file = j.file;
        GL.terms = j.terms || []; GL.keys = j.keys || []; GL.groups = j.groups || [];
        const needles = [];
        for (const t of GL.terms) {
          GL.byAnchor.set(t.anchor, t);
          for (const n of [t.term].concat(t.aliases || [])) { const k = String(n).toLowerCase().trim(); if (k && !GL.byName.has(k)) GL.byName.set(k, t); }
          if (!t.hover) continue;
          // only the aliases the server calls real second names are matched in prose (`needles`); `a card` is not one
          for (const n of [t.term].concat(t.needles || t.aliases || [])) {
            const k = String(n).toLowerCase().trim();
            if (k.length < 3) continue;
            if (!GL.byNeedle.has(k)) { GL.byNeedle.set(k, t); needles.push(k); }
          }
        }
        needles.sort((a, b) => b.length - a.length);   // longest first: "primary current" wins over "current"
        if (needles.length) GL.re = new RegExp("\\b(" + needles.map(reEsc).join("|") + ")\\b", "gi");
      } catch (e) { /* no glossary, no underlines: every page still works */ }
      return GL;
    })();
    return GL.ready;
  }

  let glCardEl = null, glHideTimer = null;
  function glCard() {
    if (glCardEl) return glCardEl;
    glCardEl = document.createElement("div"); glCardEl.className = "gl-card"; glCardEl.hidden = true;
    document.body.appendChild(glCardEl);
    glCardEl.addEventListener("mouseenter", () => clearTimeout(glHideTimer));
    glCardEl.addEventListener("mouseleave", glHideSoon);
    return glCardEl;
  }
  const glHideSoon = () => { clearTimeout(glHideTimer); glHideTimer = setTimeout(() => { if (glCardEl) glCardEl.hidden = true; }, 160); };
  function glShow(el) {
    const t = GL.byAnchor.get(el.dataset.gl); if (!t) return;
    clearTimeout(glHideTimer);
    const navEl = document.querySelector("nav.panels"), page = navEl ? (navEl.dataset.page || "") : "";
    const c = glCard();
    c.innerHTML = `<div class="gh"><b>${esc(t.term)}</b>${(t.aliases || []).length ? `<span class="meta">also: ${esc(t.aliases.join(", "))}</span>` : ""}<span class="meta grp">${esc(t.group)}</span></div>
      <p class="gd">${inline(t.definition)}</p>${t.example ? `<p class="gx"><span class="kicker">example</span> ${inline(t.example)}</p>` : ""}
      <a class="gmore" href="/glossary?from=${encodeURIComponent(page || "")}#term-${esc(t.anchor)}">more</a>`;
    c.querySelector(".gmore").onclick = e => { e.preventDefault(); openGlossary(t.anchor, page); };
    c.hidden = false;
    const r = el.getBoundingClientRect(), w = c.offsetWidth, h = c.offsetHeight;
    let x = Math.min(Math.max(8, r.left), window.innerWidth - w - 8);
    let y = r.bottom + 8; if (y + h > window.innerHeight - 8) y = Math.max(8, r.top - h - 8);
    c.style.left = x + "px"; c.style.top = y + "px";
  }
  function openGlossary(anchor, page) {
    const url = `/glossary?from=${encodeURIComponent(page || (document.querySelector("nav.panels") || { dataset: {} }).dataset.page || "")}` + (anchor ? "#term-" + anchor : "");
    const w = window.open(url, "bv-glossary", "width=520,height=820,menubar=no,toolbar=no,location=no");
    if (w) w.focus(); else location.href = url;   // a blocked pop-up must not swallow the click
    return w;
  }
  document.addEventListener("mouseover", e => { const g = e.target.closest && e.target.closest(".gl[data-gl]"); if (g) glShow(g); });
  document.addEventListener("mouseout", e => { if (e.target.closest && e.target.closest(".gl[data-gl]")) glHideSoon(); });
  document.addEventListener("click", e => { const g = e.target.closest && e.target.closest(".gl[data-gl]"); if (g) glShow(g); else if (glCardEl && !e.target.closest(".gl-card")) glCardEl.hidden = true; });
  document.addEventListener("keydown", e => { if (typing(e)) return; if (e.key === "Escape" && glCardEl) glCardEl.hidden = true; });

  let glQueue = new Set(), glFrame = 0;
  function glSpan(t, shown) {
    const s = document.createElement("span");
    s.className = "gl"; s.dataset.gl = t.anchor; s.textContent = shown;
    s.title = t.term + " — " + String(t.definition || "").split(". ")[0];
    return s;
  }
  function glPass(root) {
    if ((!GL.re && !GL.byName.size) || !root || !root.nodeType) return 0;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (!n.nodeValue || n.nodeValue.length < 3 || !/[A-Za-z]{2}/.test(n.nodeValue)) return NodeFilter.FILTER_REJECT;
        const p = n.parentElement;
        if (!p || p.closest(GL_SKIP)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = []; let n;
    while ((n = walker.nextNode())) nodes.push(n);
    const used = new Map(); let wraps = 0;
    for (const node of nodes) {
      if (wraps > 200) break;                       // a cap, so a very long page cannot cost a visible pause
      const block = (node.parentElement.closest(GL_BLOCK) || node.parentElement);
      let seen = used.get(block); if (!seen) used.set(block, seen = new Set());
      const text = node.nodeValue; let frag = null;
      // the auto pass over one run of plain text: first occurrence of a term per block, as it always was
      const auto = (str, into) => {
        let last = 0, m, hit = false;
        if (GL.re) {
          GL.re.lastIndex = 0;
          while ((m = GL.re.exec(str))) {
            const t = GL.byNeedle.get(m[0].toLowerCase());
            if (!t || seen.has(t.anchor)) continue;     // first occurrence per block only
            seen.add(t.anchor); hit = true;
            into.appendChild(document.createTextNode(str.slice(last, m.index)));
            into.appendChild(glSpan(t, m[0])); last = m.index + m[0].length; wraps++;
          }
        }
        into.appendChild(document.createTextNode(str.slice(last)));
        return hit;
      };
      if (text.includes("{{")) {
        // marked terms first: each {{...}} becomes its words, underlined when they name a term (the braces never show)
        const f = document.createDocumentFragment(); let pos = 0, mm, changed = false;
        GL_MARK.lastIndex = 0;
        while ((mm = GL_MARK.exec(text))) {
          auto(text.slice(pos, mm.index), f);
          const words = mm[1].trim(), t = GL.byName.get(words.toLowerCase());
          if (t) { seen.add(t.anchor); f.appendChild(glSpan(t, words)); wraps++; }
          else f.appendChild(document.createTextNode(words));
          pos = mm.index + mm[0].length; changed = true;
        }
        if (changed) { auto(text.slice(pos), f); frag = f; }
      }
      if (!frag) { const f = document.createDocumentFragment(); if (auto(text, f)) frag = f; }
      if (frag) node.parentNode.replaceChild(frag, node);
    }
    return wraps;
  }
  // Pages call this after they render. Several calls in one frame do one pass (a chat streaming its answer would
  // otherwise scan on every token).
  let glBusy = false;
  async function glFlush(roots) {
    await glLoad();
    if (!GL.re && !GL.byName.size) return;
    glBusy = true;                                  // our own wrapping is a DOM change: the watcher below must ignore it
    try { for (const r of roots) { try { if (r === document.body || (r && r.isConnected && !r.closest(".gl-card,.keyshint"))) glPass(r); } catch (e) {} } }
    finally { setTimeout(() => { glBusy = false; }, 0); }
  }
  function glScan(root) {
    glQueue.add(root || document.body);
    if (glFrame) return;
    glFrame = requestAnimationFrame(() => { glFrame = 0; const roots = glQueue; glQueue = new Set(); glFlush(roots); });
  }
  // Every panel paints itself from JS, several of them repeatedly (a chat streams, a ledger re-renders on every write),
  // so instead of a scan call at each of ~30 render sites the definitions follow the DOM: what gets added gets scanned
  // once the page goes quiet for a moment. The quiet window is what keeps a streaming answer from being scanned per
  // token, and glBusy keeps our own spans from starting the cycle again.
  let glWatchRoots = new Set(), glWatchTimer = null;
  function glWatch() {
    if (!window.MutationObserver || document.querySelector("nav.panels")?.dataset.page === "glossary") return;
    new MutationObserver(muts => {
      if (glBusy) return;
      for (const m of muts) {
        for (const n of m.addedNodes || []) {
          if (n.nodeType === 1 && !(n.classList && n.classList.contains("gl"))) glWatchRoots.add(n);
          else if (n.nodeType === 3 && n.parentElement) glWatchRoots.add(n.parentElement);
        }
      }
      if (!glWatchRoots.size) return;
      clearTimeout(glWatchTimer);
      glWatchTimer = setTimeout(() => { const r = glWatchRoots; glWatchRoots = new Set(); glFlush(r); }, 260);
    }).observe(document.body, { childList: true, subtree: true });
  }

  // The keys that apply on this page, named in the corner (Zak, 9/09: "make sure that we have good explanations for
  // things if we do make hotkeys"). Declared in the glossary seed's Keys section; nothing here binds a key.
  // CLOSABLE since 2026-09-17 (ledger T-0138; Zak 9/11 and again 9/17: "Hintbox in the bottom needs to have a close
  // button too"). Closed, it becomes a small "keys" tab in the same corner that puts it back. The choice is remembered
  // per browser under bv.keyshint, and every localStorage touch is wrapped -- a private window costs the memory of the
  // choice and nothing else, and the strip simply starts open there.
  const KEYSHINT_KEY = "bv.keyshint";
  async function keysHint(page) {
    await glLoad();
    page = page || (document.querySelector("nav.panels") || { dataset: {} }).dataset.page || "";
    const mine = GL.keys.filter(k => (k.pages || []).some(p => p === page || p === "every page"));
    if (!mine.length || document.querySelector(".keyshint")) return null;
    const d = document.createElement("div"); d.className = "keyshint";
    const gist = w => { const s = String(w).split(/[:;,.]/)[0].trim(); return s.length > 34 ? s.slice(0, 33).trimEnd() + "…" : s; };
    // One spot for open and close (2026-09-24, T-0197; Zak 9/18: the x "should just stay in the same area as the key
    // button itself so its easier to open and close"): the strip ends in a "keys ×" press pinned to its own bottom-right
    // corner, which is the exact box the folded "keys" tab occupies, so the pointer never moves between the two.
    d.innerHTML = `<span class="kitems">` + mine.map(k => `<span title="${esc(k.what)}"><kbd>${esc(k.key)}</kbd> ${esc(gist(k.what))}</span>`).join("")
      + `</span><button type="button" class="keysx" title="hide the keys — the same spot puts them back" aria-label="hide the keys">keys ×</button>`;
    const tab = document.createElement("button");
    tab.type = "button"; tab.className = "keystab"; tab.textContent = "keys";
    tab.title = "show the keys that work on this page";
    const show = on => { d.hidden = !on; tab.hidden = on; lsSet(KEYSHINT_KEY, on ? "on" : "off"); };
    d.querySelector(".keysx").onclick = () => show(false);
    tab.onclick = () => show(true);
    document.body.appendChild(d); document.body.appendChild(tab);
    tab.hidden = true;
    if (lsGet(KEYSHINT_KEY) === "off") { d.hidden = true; tab.hidden = false; }
    return d;
  }

  // one call for a page that just wants the lot: definitions under its text now and as it re-renders, and its keys named
  // in the corner. Every panel calls this once, at the bottom of its script.
  function glMount(page) { glScan(document.body); glWatch(); keysHint(page); return glLoad(); }
  document.addEventListener("DOMContentLoaded", () => {
    const el = document.querySelector("nav.panels");
    if (el && el.dataset.page !== "glossary") glMount(el.dataset.page || "");
  });

  // ---- the filtering rule (2026-09-09, Zak: "smart filtering") ----
  // Every page opens showing only what is live right now -- waiting on him, changed since he last looked, running -- and
  // everything else is one click away behind a fold. This is the click: one toggle per page, remembered in that browser.
  const showAllKey = page => "bv.showall." + page;
  function showAll(page) { try { return localStorage.getItem(showAllKey(page)) === "1"; } catch (e) { return false; } }
  function mountShowAll(page, onChange, opts = {}) {
    const bar = document.querySelector("header.bar"); if (!bar) return null;
    let b = bar.querySelector("button.showall");
    if (!b) { b = document.createElement("button"); b.type = "button"; b.className = "btn showall"; bar.insertBefore(b, bar.querySelector("nav.panels")); }
    const paint = () => {
      const on = showAll(page);
      b.classList.toggle("on", on);
      b.textContent = on ? (opts.allLabel || "showing everything") : (opts.liveLabel || "showing what's live");
      b.title = on ? "click to show only what is live: waiting on you, changed, running" : "click to show everything, including what is folded away";
    };
    b.onclick = () => { try { localStorage.setItem(showAllKey(page), showAll(page) ? "0" : "1"); } catch (e) {} paint(); if (onChange) onChange(showAll(page)); };
    paint(); return b;
  }

  // ---- the quest log and the timeline (2026-09-09, the straight line step 2c, ledger T-0058 + T-0059) ----
  // Zak: "giving me a list of things that I should test and look through would be optimal... Hyperlinking/giving those
  // links to just help me navigate towards the sections and keeping the what needs to be tested panel in the top right
  // of the screen like its a game", and "click on recently completed things like its a timeline task bar (probably
  // vertical), and expandable on the bottom to show older completed tasks so you can see the process of the whole
  // app... very similar to acquiring tasks in an RPG."
  // ONE read (GET /api/quests) behind two tabs: the open #test items owned by Zak across every ledger, and the
  // timeline of everything done. Both are the ledgers read back -- nothing here is stored in the brain, and the fold,
  // the tab and how far the timeline is unrolled live in this browser only.
  const Q = { data: null, ready: null, el: null, older: 0 };
  const qGet = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } };
  const qSet = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  const QUEST_PAGE = 10;                    // entries visible before "show older", and how many each press adds

  // Where an item points. A TEST item names the page it tests in its own words ("Test projects (/projects)", "press ?
  // on /projects"), so the first /route in the text wins and its → link is the fallback. A DONE item is the other way
  // round: its → link is what it PRODUCED, which is the whole point of the timeline.
  const ROUTE_RE = /(?:^|[\s(\[])(\/[A-Za-z0-9\-_/]*(?:\?[^\s)\]]+)?)/;
  function routeIn(s) {
    const m = ROUTE_RE.exec(String(s || ""));
    if (!m) return null;
    const r = m[1].replace(/[).,;:]+$/, "");
    return r || "/";
  }
  // a route reads as the page it opens, not as a path with a query string trailing off the panel ("/" is home)
  const routeLabel = r => { const p = String(r).split("?")[0].replace(/\/$/, ""); return p === "" ? "home" : p.replace(/^\//, ""); };
  // one raw `→ link` -> something clickable, or null when nothing on this page could open it
  function questTarget(raw) {
    let t = String(raw || "").trim();
    const wl = /^\[\[(.+)\]\]$/.exec(t);
    if (wl) t = wl[1].split("|")[0].trim();
    if (!t) return null;
    if (t.startsWith("/")) return { kind: "route", href: t, label: routeLabel(t) };
    const hash = t.indexOf("#"), path = hash > 0 ? t.slice(0, hash) : t, frag = hash > 0 ? t.slice(hash + 1) : "";
    const leaf = path.split("/").filter(Boolean).pop() || path;
    if (isDoc(path)) return { kind: "doc", href: readerHref(path, frag), label: leaf, path, frag };
    if (isImage(path)) return { kind: "image", path: path, label: leaf };
    if (/\.canvas$/i.test(path)) return { kind: "route", href: forgeHref(path), label: leaf };   // a drawing opens in the Forge (2026-09-09, T-0041)
    return null;
  }
  // Where a TEST item points: its own → link when that link is a route, then the first /route in its words, then
  // whatever else it links. The link leads (2026-09-09, T-0070) because the route left the words when the panel began
  // rendering it as a link -- and a sentence can name another page in passing ("on /people open Kyle") without that
  // being the page the item tests.
  const questTest = i => (i.links || []).map(questTarget).find(t => t && t.kind === "route")
                      || (routeIn(i.text) ? { kind: "route", href: routeIn(i.text), label: routeLabel(routeIn(i.text)) } : null)
                      || (i.links || []).map(questTarget).find(Boolean) || null;
  const questResult = i => (i.links || []).map(questTarget).find(Boolean) || null;
  // The route an item names is shown as a link beside it, so the "(/projects)" it was parsed out of is noise in the
  // sentence (2026-09-09, T-0070). Dropped from what is DRAWN wherever the quest log renders an item; the ledger line
  // itself is the ledger's business (`tasks.py retext` is how those were rewritten).
  const questText = (text, linked) => linked ? String(text || "").replace(/\s*\(\/[^)]*\)/, "") : String(text || "");
  // A test item that names several moves in one sentence reads as a wall (Zak, 9/10: the instructions are overwhelming).
  // Its semicolons already mark the moves, so the panel renders them as numbered steps -- the words on the ledger are
  // untouched, this is only how they are drawn (2026-09-10, T-0077).
  function stepsHTML(text) {
    const parts = String(text || "").split(";").map(x => x.trim()).filter(Boolean);
    if (parts.length < 2) return `<div class="qt">${esc(text || "")}</div>`;
    return `<ol class="qsteps">${parts.map(x => `<li>${esc(x)}</li>`).join("")}</ol>`;
  }
  function questAnchor(t, extra) {
    if (!t) return "";
    if (t.kind === "image") return `<button class="btn go" type="button" data-quest-img="${esc(t.path)}" title="${esc(t.path)}">${esc(t.label)}</button>`;
    // a document result opens beside the page like every other document link (0.53.0); a route is still followed
    if (t.kind === "doc" && t.path) return `<span class="go filelink" data-open="${esc(t.path)}"${t.frag ? ` data-frag="${esc(t.frag)}"` : ""} title="${esc(t.path)} — opens beside the page">${esc(extra || t.label)}</span>`;
    return `<a class="go" href="${esc(t.href)}" title="${esc(t.href)}">${esc(extra || t.label)}</a>`;
  }

  async function questLoad(force) {
    if (Q.ready && !force) return Q.ready;
    Q.ready = (async () => {
      try {
        const r = await fetch("/api/quests"); const j = await r.json();
        Q.data = r.ok ? j : { error: j.error || String(r.status), tests: [], done: [] };
      } catch (e) { Q.data = { error: e.message, tests: [], done: [] }; }
      return Q.data;
    })();
    return Q.ready;
  }

  // ---- the timeline: vertical, newest at the top, grouped by the day the item was closed ----
  // Every entry links to what it produced. `shown` is how far it is unrolled; the rest is one press away, which is the
  // "expandable on the bottom to show older completed tasks" half.
  function timelineHTML(rows, shown, opts = {}) {
    rows = rows || [];
    if (!rows.length) return `<p class="empty" style="padding:14px">Nothing is closed on the ledgers yet.</p>`;
    const take = rows.slice(0, shown), days = [];
    for (const r of take) {
      const d = r.done || "undated";
      if (!days.length || days[days.length - 1].day !== d) days.push({ day: d, rows: [] });
      days[days.length - 1].rows.push(r);
    }
    const trim = (s, n) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);
    const body = days.map(g => `<div class="tl-day"><b>${esc(g.day)}</b><span class="meta">${g.rows.length}</span></div>` + g.rows.map(r => {
      const t = questResult(r);
      const txt = questText(r.text, !!t);
      return `<div class="tl-item"><div class="tl-h"><span class="badge">${esc(r.projectName || r.project)}</span>${t ? questAnchor(t, t.kind === "route" ? t.label : "what it built") : `<span class="meta">no result link</span>`}</div>
        <div class="tl-t" title="${esc(txt)}">${esc(trim(txt, 90))}</div></div>`;
    }).join("")).join("");
    const more = rows.length - take.length;
    return body + (more > 0
      ? `<button class="btn older" type="button" data-quest-older>show older · ${more} more</button>`
      : (rows.length > QUEST_PAGE ? `<button class="btn older" type="button" data-quest-older="reset">that is all ${rows.length} · fold back</button>` : ""));
  }

  // A timeline anywhere on a page (the home's "Recently done" block uses this). It owns its own unrolling.
  function mountTimeline(el, opts = {}) {
    if (!el) return null;
    let shown = opts.shown || QUEST_PAGE;
    const paint = () => {
      const rows = (Q.data && Q.data.done) || [];
      el.innerHTML = (Q.data && Q.data.error) ? `<p class="note">could not read the ledgers: ${esc(Q.data.error)}</p>`
                                              : `<div class="timeline">${timelineHTML(rows, shown, opts)}</div>`;
      if (opts.onPaint) opts.onPaint(Q.data);
    };
    el.addEventListener("click", e => {
      const b = e.target.closest("[data-quest-older]"); if (!b) return;
      shown = b.dataset.questOlder === "reset" ? (opts.shown || QUEST_PAGE) : shown + QUEST_PAGE;
      paint();
    });
    questLoad().then(paint);
    return { paint, refresh: () => questLoad(true).then(paint) };
  }

  // ---- the panel gets out of the drawer's way (2026-09-09, T-0065) ----
  // The panel is fixed to the right edge; so is every panel's read drawer, which used to open underneath it. While a
  // drawer is open the panel DOCKS to that drawer's left edge instead; when what is left over is narrower than the
  // panel needs, it folds to its one-line tab there and unfolds again when the drawer closes. No page has to call
  // this: the panel watches the page's `aside.drawer` and reacts to it being shown or hidden.
  const QUEST_MIN_ROOM = 380;                      // the open panel is 340px + its margins
  function questDock(drawer) {
    const el = Q.el; if (!el) return;
    const r = drawer ? drawer.getBoundingClientRect() : null;
    const open = !!(drawer && !drawer.hidden && r.width > 0);
    Q.drawer = open ? drawer : null;
    if (!open) {
      el.style.right = ""; el.classList.remove("docked");
      if (Q.folded) { Q.folded = false; if (Q.setOpen) Q.setOpen(qGet("bv.quest.open", "0") === "1", false); }
      return;
    }
    const right = Math.round(Math.max(12, window.innerWidth - r.left + 12));
    el.style.right = right + "px"; el.classList.add("docked");
    const need = (parseFloat(el.style.width) || 340) + 40;   // the panel is resizable (T-0077), so the room it needs is its own width
    if (window.innerWidth - right < Math.max(QUEST_MIN_ROOM, need) && el.dataset.questOpen === "1" && Q.setOpen) { Q.folded = true; Q.setOpen(false, false); }
  }
  function questWatchDrawer() {
    const d = document.querySelector("aside.drawer"); if (!d) return;
    new MutationObserver(() => { questDock(d); paintBack(); }).observe(d, { attributes: true, attributeFilter: ["hidden", "style", "class"] });
    questDock(d);
  }

  // ---- the panel itself: folded to a one-line tab, top right, on every page ----
  function questMount() {
    if (Q.el || !document.querySelector("nav.panels")) return Q.el;
    // a page for use during a call carries no quest log (0.47.1): its boxes and its fold are nothing to act on mid-call
    if (document.body && document.body.hasAttribute("data-noquest")) return Q.el;
    const page = (document.querySelector("nav.panels") || { dataset: {} }).dataset.page || "";
    const el = document.createElement("aside");
    el.className = "quest no-gloss"; el.id = "questlog"; el.hidden = true;
    el.innerHTML = `<button class="qtab" type="button" data-quest-toggle><span class="sun"></span><span class="n">·</span><span class="w">to test</span></button>
      <div class="qbody" hidden>
        <div class="qtabs"><button type="button" data-quest-tab="test">To test <span class="c"></span></button><button type="button" data-quest-tab="done">Done <span class="c"></span></button></div>
        <div class="qpane" data-pane="test"></div>
        <div class="qpane" data-pane="done" hidden></div>
        <p class="status-line qmsg"></p>
        <details class="qtips"><summary>what this is</summary>
          <p><b>To test</b> is every open task of yours tagged <code>#test</code>, on any project ledger: what to look at now. The link takes you to the page it names; the checkbox closes it on the ledger (dated by the clock, logged), and <i>keep in mind</i> is the one thing to watch while you are there.</p>
          <p><b>Done</b> is the timeline: everything closed across the projects, newest first, each entry linking to what it produced. <i>Show older</i> unrolls the rest, so the whole build reads back in order.</p>
          <p>The <b>stage line</b> on the home page and on a project page is the same ledgers seen the other way round: one dot per step of the build order, filled once a step is closed, with the current one marked. Hover a dot for its name, click it to keep the card open and follow the link to what that step built.</p>
          <p>The tab remembers whether it is open, per browser. <kbd>Esc</kbd> folds it, and it steps aside to the left of a drawer whenever one is open. Drag the corner at its bottom left to resize it; that size is remembered too.</p></details>
      </div>
      <div class="qgrip" data-quest-grip title="drag to resize this panel: left and right for width, up and down for height. The size is remembered in this browser"></div>`;
    document.body.appendChild(el);
    Q.el = el;
    // the panel's size, dragged from the grip at its bottom-left corner and remembered in this browser (T-0077)
    const QW = [260, 760], QH = [180, 900];
    const clamp = (v, [lo, hi]) => Math.max(lo, Math.min(hi, v));
    let qw = clamp(parseInt(qGet("bv.quest.w", "340"), 10) || 340, QW);
    let qh = clamp(parseInt(qGet("bv.quest.h", "0"), 10) || 0, QH);
    function applySize() {
      // the viewport is only a ceiling when the browser actually reports one: a window that has not been laid out yet
      // answers 0 for innerWidth, and clamping to that wrote a negative length the browser threw away
      const vw = window.innerWidth || 0, vh = window.innerHeight || 0;
      const w = vw > 320 ? Math.min(qw, vw - 24) : qw;
      const h = qh ? (vh > 300 ? Math.min(qh, vh - 90) : qh) : 0;
      el.style.width = el.dataset.questOpen === "1" ? Math.round(w) + "px" : "";
      el.querySelector(".qbody").style.maxHeight = h ? Math.round(h) + "px" : "";
    }
    // the drag listens on the window rather than on the grip: the pointer leaves a 16px corner immediately, and a
    // capture that is lost mid-drag would strand the panel at whatever size the last event set
    el.addEventListener("pointerdown", e => {
      if (!e.target.closest("[data-quest-grip]")) return;
      e.preventDefault();
      const x0 = e.clientX, y0 = e.clientY, w0 = qw, h0 = qh || el.querySelector(".qbody").getBoundingClientRect().height;
      const move = ev => { qw = clamp(w0 + (x0 - ev.clientX), QW); qh = clamp(h0 + (ev.clientY - y0), QH); applySize(); };
      const up = () => {
        window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", up);
        qSet("bv.quest.w", String(Math.round(qw))); qSet("bv.quest.h", String(Math.round(qh))); questDock(Q.drawer);
      };
      window.addEventListener("pointermove", move); window.addEventListener("pointerup", up); window.addEventListener("pointercancel", up);
    });
    // the bar can wrap to two rows on a narrow window, so the panel is placed under whatever height it actually has
    const place = () => { const bar = document.querySelector("header.bar"); el.style.top = ((bar ? bar.getBoundingClientRect().bottom : 56) + 8) + "px"; applySize(); questDock(Q.drawer); };
    place(); window.addEventListener("resize", place);
    Q.setOpen = setOpen;      // questDock folds the panel when a drawer leaves it no room
    questWatchDrawer();

    // the Reader has its own outline on the right of the text and the glossary pop-out is a narrow window: the tab is
    // there, folded, and one press opens it like anywhere else
    const startOpen = (page === "reader" || page === "glossary") ? false : qGet("bv.quest.open", "0") === "1";
    setOpen(startOpen, false);
    setTab(qGet("bv.quest.tab", "test"), false);

    el.addEventListener("click", async e => {
      if (e.target.closest("[data-quest-toggle]")) { setOpen(el.dataset.questOpen !== "1"); return; }
      const tb = e.target.closest("[data-quest-tab]"); if (tb) { setTab(tb.dataset.questTab); return; }
      const ol = e.target.closest("[data-quest-older]"); if (ol) { Q.older = ol.dataset.questOlder === "reset" ? 0 : Q.older + QUEST_PAGE; paintDone(); return; }
      const im = e.target.closest("[data-quest-img]"); if (im) { lightbox(im.dataset.questImg); return; }
      const cb = e.target.closest("input[type=checkbox][data-quest-id]");
      if (cb) {
        e.preventDefault(); cb.disabled = true;
        const msg = el.querySelector(".qmsg"); msg.textContent = "writing to the ledger…";
        const pend = pendingReply(cb);      // words still in the reply box are written before the item closes (T-0077)
        if (pend) { const r = await replyAct(pend.project, pend.id, pend.text, pend.ledger); if (r.ok) pend.form.querySelector("textarea").value = ""; }
        const res = await ledgerAct(cb.dataset.questProject, { action: "done", id: cb.dataset.questId });
        msg.textContent = res.message;
        if (res.ok) { await questLoad(true); paint(); refreshBadges(); }
        else cb.disabled = false;
      }
    });
    el.addEventListener("submit", async e => {
      const f = e.target.closest("form[data-reply]"); if (!f) return;
      e.preventDefault();
      const ta = f.querySelector("textarea"), text = ta.value.trim(); if (!text) return;
      const btn = f.querySelector("button"), msg = el.querySelector(".qmsg");
      btn.disabled = true; ta.disabled = true; msg.textContent = "writing to the ledger…";
      const res = await replyAct(f.dataset.project, f.dataset.reply, text, f.dataset.ledger);
      ta.disabled = false; btn.disabled = false;
      if (res.ok) { ta.value = ""; showNote(f, res.json && res.json.note); await questLoad(true); paint(); }
      msg.textContent = res.message;
    });
    document.addEventListener("keydown", e => { if (typing(e)) return; if (e.key === "Escape" && el.dataset.questOpen === "1") setOpen(false); });
    // hold and bring-back inside the panel, on the panel (T-0108): the page's own wiring never sees these rows
    wireHolds(el, { status: m => { const x = el.querySelector(".qmsg"); if (x) x.textContent = m; },
                    onDone: async () => { await questLoad(true); paint(); } });

    function setOpen(on, remember = true) {
      // NOT `data-open`: every panel opens a file with a delegated `[data-open]` handler, so a state attribute by that
      // name on a panel that sits over the page made every click inside the quest log open a drawer on the path "1"
      // (2026-09-09, T-0065). The handlers were narrowed to `.filelink[data-open]` as well; this is the other half.
      el.dataset.questOpen = on ? "1" : "0";
      el.classList.toggle("open", !!on);
      el.querySelector(".qbody").hidden = !on;
      applySize();
      if (remember) qSet("bv.quest.open", on ? "1" : "0");
    }
    function setTab(name, remember = true) {
      name = name === "done" ? "done" : "test";
      el.querySelectorAll("[data-quest-tab]").forEach(b => b.classList.toggle("on", b.dataset.questTab === name));
      el.querySelectorAll(".qpane").forEach(p => { p.hidden = p.dataset.pane !== name; });
      if (remember) qSet("bv.quest.tab", name);
      if (name === "done") paintDone();
    }
    function paintDone() {
      const rows = (Q.data && Q.data.done) || [];
      // the plain-words page above the timeline (2026-09-10, T-0093): the timeline is one line per thing closed, which is
      // the record; What's new is the same days written to be picked up later.
      el.querySelector('[data-pane="done"]').innerHTML =
        `<p class="qwn"><span class="filelink" data-open="brain-viewer-holon/brain-viewer-whats-new.md" title="what was added, day by day, in plain words: what it is, where it is, what to press · opens beside the page">what's new, in plain words →</span></p>`
        + `<div class="timeline">${timelineHTML(rows, QUEST_PAGE + Q.older)}</div>`;
    }
    function paint() {
      const d = Q.data || { tests: [], done: [] };
      const tests = d.tests || [], done = d.done || [], held = d.held || [];
      // a team copy that carries no test items has no quest to log: the panel stays away entirely (rules 4b, the fold is the rule everywhere else)
      if (mode().propose && !tests.length) { el.hidden = true; return; }
      el.hidden = false;
      el.querySelector(".qtab .n").textContent = d.error ? "!" : tests.length;
      el.querySelector(".qtab .w").textContent = d.error ? "quest log" : "to test";
      el.querySelector(".qtab").title = d.error ? "the ledgers could not be read: " + d.error
        : `${tests.length} thing${tests.length === 1 ? "" : "s"} to test · ${done.length} done on the timeline · click to open`;
      el.querySelector('[data-quest-tab="test"] .c').textContent = tests.length;
      el.querySelector('[data-quest-tab="done"] .c').textContent = done.length;
      el.querySelector('[data-pane="test"]').innerHTML = d.error
        ? `<p class="note">could not read the ledgers: ${esc(d.error)}</p>`
        : (tests.length ? `<ul class="qlist">${tests.map(i => {
            const t = questTest(i);
            return `<li><input type="checkbox" data-quest-id="${esc(i.id)}" data-quest-project="${esc(i.project)}" title="mark this done on ${esc(i.projectName || i.project)}">
              <div>${stepsHTML(questText(i.text, !!t))}
              <div class="qm"><span class="id">${esc(i.id)}</span><span class="badge">${esc(i.projectName || i.project)}</span>${questAnchor(t, t && t.kind === "route" ? "go to " + t.label : null)}</div>
              ${i.note ? `<div class="keep"><span class="kicker">keep in mind</span> ${esc(hideLineRefs(i.note))}</div>` : ""}
              ${holdControl(i, i.project, { today: d.today })}${replyBox(i, i.project)}</div></li>`;
          }).join("")}</ul>`
        : `<p class="empty" style="padding:16px 8px">Nothing is waiting to be tested. New test items arrive when a step closes.</p>`)
        + (held.length && !d.error ? `<details class="qheld"><summary>${held.length} on hold</summary><ul class="qlist">${held.map(i =>
            `<li><span class="holdmark"></span><div>${stepsHTML(questText(i.text, !!questTest(i)))}
              <div class="qm"><span class="id">${esc(i.id)}</span><span class="badge">${esc(i.projectName || i.project)}</span><span class="badge held">back ${esc(i.until)}</span>
                <button type="button" class="btn" data-resume="${esc(i.id)}" data-project="${esc(i.project)}" title="bring this back now">bring back</button></div></div></li>`).join("")}</ul></details>` : "");
      paintDone();
    }
    Q.paint = paint;
    questLoad().then(paint);
    return el;
  }
  const questRefresh = () => questLoad(true).then(() => { if (Q.paint) Q.paint(); });
  document.addEventListener("DOMContentLoaded", questMount);

  // ---- the notepad (2026-09-10, ideas B15, ledger T-0074) ----
  // Zak: "We should make a notepad in the bottom left corner that has extended capabilities... something that just can
  // be brought up and gives the ability to take notes with. Ability to add pictures/notes would be nice."
  // Folded it is one line at the bottom left of every page, the same shape as the quest log at the top right. Open, it
  // is a box to type in, a picture can be pasted or attached, and Save writes ONE dated markdown file into
  // thoughts/notepad/ with the picture beside it (POST /api/notepad; spec section 4, decision 14). The last few notes
  // are listed under the box, each openable in the Reader and each with its path ready to paste into a chat or onto a
  // ledger, which is what "linkable" means here: the note is a real brain file with a real path.
  //
  // 2026-09-16 (ledger T-0146). Zak, 9/15 in this same notepad: "We need to make notebooks editable, and they should be
  // clickable in recent notes." So a note in the recent list is a BUTTON that opens it right here -- its words in the
  // box, its pictures under them, save writing the same file back (PUT /api/notepad; only the body moves, the title,
  // the **Taken:** line and the pictures stay). The note being written is kept aside while a saved one is open, so
  // opening an old note never costs the new one.
  const N = { el: null, pics: [], notes: null, editing: null, note: null, draft: "" };
  function notepadMount() {
    if (N.el || !document.querySelector("nav.panels")) return N.el;
    const page = (document.querySelector("nav.panels") || { dataset: {} }).dataset.page || "";
    const el = document.createElement("aside");
    el.className = "notepad no-gloss"; el.id = "notepad";
    el.innerHTML = `<button class="ntab" type="button" data-note-toggle><span class="pen"></span><span class="w">notepad</span></button>
      <div class="nbody" hidden>
        <button class="nx" type="button" data-note-close title="close the notepad" aria-label="close the notepad">×</button>
        <div class="nhead" hidden></div>
        <textarea class="ntext" rows="5" placeholder="a note, as you thought of it · paste a picture straight in"></textarea>
        <div class="npics"></div>
        <div class="nrow"><button class="btn" type="button" data-note-pick>picture</button>
          <input type="file" accept="image/*" multiple hidden data-note-file>
          <span class="spacer"></span><button class="btn primary" type="button" data-note-save>save</button></div>
        <p class="status-line nmsg"></p>
        <div class="nrecent"></div>
      </div>`;
    document.body.appendChild(el);
    N.el = el;
    const ta = el.querySelector(".ntext"), msg = el.querySelector(".nmsg");
    const setOpen = (on, remember = true) => {
      el.dataset.noteOpen = on ? "1" : "0";
      el.classList.toggle("open", !!on);
      el.querySelector(".nbody").hidden = !on;
      if (remember) qSet("bv.note.open", on ? "1" : "0");
      if (on) { ta.focus(); loadNotes(); }
    };
    // a draft survives a page move: it lives in this browser until it is saved (nothing half-typed reaches the brain)
    try { ta.value = qGet("bv.note.draft", "") || ""; } catch (e) {}
    ta.addEventListener("input", () => { if (!N.editing) qSet("bv.note.draft", ta.value); });
    setOpen(qGet("bv.note.open", "0") === "1", false);

    function paintPics() {
      // an open note shows the pictures it already carries, with no × on them: an edit moves the words and nothing else
      const own = (N.editing && N.note && N.note.pictures) || null;
      el.querySelector(".npics").innerHTML = (own || N.pics).map(p => own
        ? `<span class="npic"><img src="/api/image?path=${encodeURIComponent(p)}" alt="" title="${esc(p)} — it stays with this note"></span>`
        : `<span class="npic"><img src="/api/image?path=${encodeURIComponent(p)}" alt=""><button class="btn" type="button" data-note-drop="${esc(p)}" title="leave this picture out of the note (the file stays in the brain)">×</button></span>`).join("");
    }
    // the box says which note it is holding: a new one, or one already written that save will rewrite
    function paintMode() {
      const head = el.querySelector(".nhead"), pick = el.querySelector("[data-note-pick]"), save = el.querySelector("[data-note-save]");
      if (N.editing && N.note) {
        head.hidden = false;
        head.innerHTML = `<span class="w">editing</span> <strong title="${esc(N.editing)}">${esc(N.note.title)}</strong>`
          + `<span class="meta">${esc((N.note.taken || "").slice(0, 16))}</span>`
          + `<button class="btn" type="button" data-note-new title="leave this note as it is and go back to writing a new one">new note</button>`;
        save.textContent = "save changes";
        pick.hidden = true;
        ta.placeholder = "this note, as you want it to read now";
      } else {
        head.hidden = true; head.innerHTML = "";
        save.textContent = "save";
        pick.hidden = false;
        ta.placeholder = "a note, as you thought of it · paste a picture straight in";
      }
    }
    // pressing a note in the recent list opens it HERE, in the box, with its words in it (T-0146)
    async function openNote(path) {
      if (!path) return;
      msg.textContent = "opening the note…";
      try {
        const r = await fetch("/api/note?path=" + encodeURIComponent(path));
        const j = await r.json().catch(() => ({}));
        if (!r.ok) { msg.textContent = "could not open it: " + (j.error || r.status); return; }
        if (!N.editing) N.draft = ta.value;      // the half-written new note is kept until this one is closed
        N.editing = j.path; N.note = j; N.pics = [];
        ta.value = j.body || "";
        paintPics(); paintMode(); loadNotes();
        setOpen(true);
        ta.focus();
        msg.innerHTML = `editing <a href="${readerHref(j.path)}">${esc(j.path)}</a> · save writes this same file`;
      } catch (err) { msg.textContent = "could not open it: " + err.message; }
    }
    // back to a blank note, with whatever was half-written before the old one was opened
    function newNote() {
      N.editing = null; N.note = null; N.pics = [];
      ta.value = N.draft || ""; N.draft = "";
      qSet("bv.note.draft", ta.value);
      paintPics(); paintMode(); loadNotes();
      msg.textContent = "";
      ta.focus();
    }
    async function loadNotes() {
      try { const r = await fetch("/api/notes?limit=5"); N.notes = r.ok ? await r.json() : null; } catch (e) { N.notes = null; }
      const rows = (N.notes && N.notes.notes) || [];
      el.querySelector(".nrecent").innerHTML = !rows.length
        ? `<p class="empty" style="padding:8px 2px;text-align:left">No notes yet. What you write here is kept in <code>${esc((N.notes && N.notes.folder) || "thoughts/notepad")}</code>, one file per note.</p>`
        : `<div class="nlist"><span class="kicker">recent notes</span>${rows.map(n => `<div class="nitem"${n.path === N.editing ? ' data-note-current="1"' : ""}>
            <button class="nopen" type="button" data-note-load="${esc(n.path)}" title="${esc(n.path)} — open it here to read it and change it">${esc(n.title)}</button>
            <span class="meta">${esc((n.taken || n.mtime || "").slice(0, 16).replace("T", " "))}</span>
            <button class="btn" type="button" data-note-cite="${esc(n.path)}" title="put this note's path where you are typing, so a message or a ledger item can point at it">cite</button>
          </div>`).join("")}</div>`;
    }
    async function attach(file) {
      if (!file) return;
      if (!/^image\//.test(file.type || "")) { msg.textContent = "only a picture can be added to a note"; return; }
      msg.textContent = `keeping ${file.name || "the picture"}…`;
      try {
        const data = await new Promise((res, rej) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(",")[1]); fr.onerror = () => rej(new Error("could not read the file")); fr.readAsDataURL(file); });
        const r = await fetch("/api/paste", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: file.name || "pasted.png", type: file.type, data, kind: "note" }) });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) { msg.textContent = "the picture was not kept: " + (j.error || r.status); return; }
        N.pics.push(j.path); paintPics();
        msg.textContent = `${j.path} · it goes with this note`;
      } catch (err) { msg.textContent = "could not add the picture: " + err.message; }
    }
    async function save() {
      const text = ta.value.trim();
      if (!text && !N.pics.length) { msg.textContent = "nothing to save yet"; return; }
      const btn = el.querySelector("[data-note-save]"); btn.disabled = true;
      if (N.editing) {
        // the same file, rewritten: the server keeps the title line, the **Taken:** line and the pictures (T-0146)
        msg.textContent = "saving the note…";
        try {
          const r = await fetch("/api/notepad", { method: "PUT", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: N.editing, text }) });
          const j = await r.json().catch(() => ({}));
          if (!r.ok) { msg.textContent = "refused: " + (j.error || r.status); }
          else {
            msg.innerHTML = `saved · <a href="${readerHref(j.path)}">${esc(j.path)}</a> · ${j.bytes} bytes`;
            loadNotes();
          }
        } catch (err) { msg.textContent = "could not save the note: " + err.message; }
        btn.disabled = false;
        return;
      }
      msg.textContent = "writing the note…";
      try {
        const r = await fetch("/api/notepad", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, pictures: N.pics, page }) });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) { msg.textContent = "refused: " + (j.error || r.status); }
        else if (j.proposed) { msg.textContent = proposedText(j); ta.value = ""; qSet("bv.note.draft", ""); N.pics = []; paintPics(); }
        else {
          ta.value = ""; qSet("bv.note.draft", ""); N.pics = []; paintPics();
          msg.innerHTML = `saved as <a href="${readerHref(j.path)}">${esc(j.path)}</a>`;
          loadNotes();
        }
      } catch (err) { msg.textContent = "could not write the note: " + err.message; }
      btn.disabled = false;
    }
    // "cite": the note's path goes wherever Zak is typing (a chat message, a reply box, a ledger form), so the thing he
    // is writing can point at the note. Nothing is auto-inserted anywhere.
    function cite(path) {
      const box = document.querySelector("#box") || document.querySelector("form.add input[name=text]") || ta;
      if (box === ta) { navigator.clipboard && navigator.clipboard.writeText(path); msg.textContent = `${path} · copied`; return; }
      box.value = (box.value ? box.value.replace(/\s*$/, "") + " " : "") + path;
      box.focus(); msg.textContent = `${path} · put where you are typing`;
    }

    el.addEventListener("click", e => {
      if (e.target.closest("[data-note-toggle]")) { setOpen(el.dataset.noteOpen !== "1"); return; }
      if (e.target.closest("[data-note-close]")) { setOpen(false); return; }   // the x in the corner, the same close as the tab
      if (e.target.closest("[data-note-pick]")) { el.querySelector("[data-note-file]").click(); return; }
      if (e.target.closest("[data-note-save]")) { save(); return; }
      const d = e.target.closest("[data-note-drop]"); if (d) { N.pics = N.pics.filter(p => p !== d.dataset.noteDrop); paintPics(); return; }
      // data-note-LOAD, never data-note-open: the strip's own fold state is data-note-open on the root, so that name
      // in a button would make every click in the notepad resolve to the root and ask for the note at path "1"
      const o = e.target.closest("[data-note-load]"); if (o) { openNote(o.dataset.noteLoad); return; }
      if (e.target.closest("[data-note-new]")) { newNote(); return; }
      const c = e.target.closest("[data-note-cite]"); if (c) { cite(c.dataset.noteCite); return; }
    });
    el.querySelector("[data-note-file]").addEventListener("change", e => { for (const f of e.target.files || []) attach(f); e.target.value = ""; });
    ta.addEventListener("paste", e => {
      const items = [...((e.clipboardData && e.clipboardData.items) || [])].filter(i => i.kind === "file" && /^image\//.test(i.type || ""));
      if (!items.length) return;
      e.preventDefault();
      for (const i of items) attach(i.getAsFile());
    });
    // a file dropped onto the notepad (the box or anywhere in the open panel) lands exactly as a paste does: POST
    // /api/paste with kind "note", the same dated name in thoughts/notepad/, the same picture going with the note
    // (2026-09-24, T-0249). Only the picture kinds the folder's .contract.json allows are sent; anything else gets one
    // plain line and nothing is written. Several files dropped at once go up one after another, in the order dropped.
    const body = el.querySelector(".nbody");
    const DROP_OK = /\.(png|jpe?g|gif|webp)$/i, DROP_TYPES = /^image\/(png|jpeg|gif|webp)$/i;
    const hasFiles = e => [...((e.dataTransfer && e.dataTransfer.types) || [])].includes("Files");
    let depth = 0;
    const dropOff = () => { depth = 0; body.classList.remove("dropping"); };
    body.addEventListener("dragenter", e => { if (!hasFiles(e)) return; e.preventDefault(); depth++; body.classList.add("dropping"); });
    body.addEventListener("dragover", e => { if (!hasFiles(e)) return; e.preventDefault(); e.dataTransfer.dropEffect = "copy"; });
    body.addEventListener("dragleave", e => { if (!hasFiles(e)) return; if (--depth <= 0) dropOff(); });
    body.addEventListener("drop", async e => {
      if (!hasFiles(e)) return;
      e.preventDefault(); dropOff();
      const files = [...((e.dataTransfer && e.dataTransfer.files) || [])];
      if (N.editing) { msg.textContent = "a picture goes with a new note; press new note first, then drop it"; return; }
      const refused = [];
      for (const f of files) {
        if (!(DROP_OK.test(f.name || "") || DROP_TYPES.test(f.type || ""))) { refused.push(f.name || "that file"); continue; }
        await attach(f);
      }
      if (refused.length) msg.textContent = `not added: ${refused.join(", ")} · the notepad keeps pictures only (png, jpg, gif, webp)`;
    });
    ta.addEventListener("keydown", e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); } });
    N.open = openNote;
    paintMode();
    document.addEventListener("keydown", e => { if (typing(e)) return; if (e.key === "Escape" && el.dataset.noteOpen === "1" && document.activeElement !== ta) setOpen(false); });
    return el;
  }
  document.addEventListener("DOMContentLoaded", notepadMount);
  // BV.notepad.open(path): open a note in the box from anywhere on the page (the Reader's "edit it in the notepad")
  function notepadOpen(path) { notepadMount(); return N.open ? N.open(path) : null; }

  // ---- the stage line (2026-09-09, ledger T-0064) ----
  // Zak meant an actual line on screen showing what stage the build is at out of how many, not another list. One
  // horizontal line, one dot per step, read from GET /api/stages -- which is the `Straight-line` milestone on the
  // ledgers ordered by the "Step N." token in each task's own words, so the picture cannot drift from the ledger
  // (rules 1: derived, never drawn). A done dot is filled, the first open dot is the current one and wears its name in
  // the caption, and hovering, focusing or clicking a dot names the step; a done dot also carries the link its close
  // pointed at, which is the same `→ link` the timeline reads. One component, two mounts (the home, a project page).
  const S = { data: null, ready: null };
  async function stageLoad(force) {
    if (S.ready && !force) return S.ready;
    S.ready = (async () => {
      try { const r = await fetch("/api/stages"); const j = await r.json(); S.data = r.ok ? j : { error: j.error || String(r.status), steps: [] }; }
      catch (e) { S.data = { error: e.message, steps: [] }; }
      return S.data;
    })();
    return S.ready;
  }
  function stageHTML(d, opts = {}) {
    if (!d) return "";
    if (d.error) return `<p class="note">could not read the build order: ${esc(d.error)}</p>`;
    const steps = d.steps || []; if (!steps.length) return "";
    const cur = steps.find(s => s.stage === "current") || null;
    const dots = steps.map(s => {
      const t = s.stage === "done" ? questResult(s) : null;
      const when = s.stage === "done" ? "done " + esc(s.done || "") : s.stage === "current" ? "this is where the build is now" : "not started";
      return `<li class="sdot ${s.stage}"><button type="button" data-stage="${esc(s.id)}" title="step ${esc(s.step)} · ${esc(s.short)}"><i></i></button><span class="sn">${esc(s.step)}</span>
        <div class="spop"><b>Step ${esc(s.step)}</b> ${esc(s.short)}<span class="sm">${when} · ${esc(s.projectName || s.project)}</span>${t ? questAnchor(t, "→ " + t.label) : ""}</div></li>`;
    }).join("");
    const cap = cur ? `Step ${esc(cur.step)} of ${steps.length} · ${esc(cur.short)}` : `All ${steps.length} steps done`;
    return `<div class="stageline"><ol class="sdots">${dots}</ol>
      <p class="scap">${cap}<span class="meta">· ${d.doneCount} done · ${esc(opts.label || d.milestone || "the build order")}</span></p></div>`;
  }
  // A stage line anywhere on a page. It owns its own pinned dot: hover shows a step, a click keeps it open so the
  // result link can be reached with the mouse (touch has no hover, which is the other reason the click exists).
  function mountStageLine(el, opts = {}) {
    if (!el) return null;
    const paint = () => { el.innerHTML = stageHTML(S.data, opts); if (opts.onPaint) opts.onPaint(S.data); };
    const unpin = () => el.querySelectorAll("li.sdot.pinned").forEach(x => x.classList.remove("pinned"));
    const unshy = () => el.querySelectorAll("li.sdot.shy").forEach(x => x.classList.remove("shy"));
    el.addEventListener("click", e => {
      const b = e.target.closest("[data-stage]"); if (!b) return;
      const li = b.closest("li.sdot"), was = li.classList.contains("pinned");
      unpin(); unshy();
      // a second press closes the card (2026-09-10, T-0081). Hover alone opens it, so the dot under the pointer would
      // reopen it at once: `shy` holds the card shut until the pointer leaves the line.
      if (was) li.classList.add("shy"); else li.classList.add("pinned");
    });
    el.addEventListener("mouseleave", unshy);
    document.addEventListener("click", e => { if (!e.target.closest(".stageline")) unpin(); });   // a click anywhere else closes it
    document.addEventListener("keydown", e => { if (typing(e)) return; if (e.key === "Escape") { unpin(); unshy(); } });
    stageLoad().then(paint);
    return { paint, refresh: () => stageLoad(true).then(paint) };
  }

  // ---- the bubbles: a conversation or a session drawn as a circle, its sub-agents attached (2026-09-10, T-0117 + T-0101) ----
  // Zak, 9/10: "I would like to have the in progress chats in a special bubble that can be double clicked on and then chat
  // history will be shown... also the ability to enter a chat", and on the agents page: "I wanted to have the visuals of it
  // built out a little more." Same circle language as the Forge -- a ring band, the glossary's glyph in the core, the name
  // under it -- and deliberately NOT a physics graph: these are laid out newest first and hold still so a name can be read.
  // One renderer, two sizes: the field on /agents and the small row in the home's Running strip.
  // Lines are drawn in one overlay for the whole field, measured off the real boxes after layout, so a wrap never breaks them.
  const BUB_KIND = { conversation: "message", session: "agent", agent: "agent" };
  const bubShort = m => String(m || "").replace(/^claude-/, "");
  const bubPlural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
  function bubWhen(iso) {
    if (!iso) return "";
    const d = new Date(iso); if (isNaN(d)) return String(iso).slice(0, 16).replace("T", " ");
    const t = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    return d.toDateString() === new Date().toDateString() ? t : `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${t}`;
  }
  // one session (or one of this app's conversations) -> the group the field draws: the bubble, and its sub-agents as kids
  function bubGroup(s, opts = {}) {
    const kind = s.chat ? "conversation" : "session";
    const kids = (s.subagents || []).slice(-(opts.maxKids || 12)).map(a => ({
      id: a.toolUseId || a.agentId || a.description, kind: "agent", live: !!a.running, title: a.description || "(no description)",
      glyph: "agent", meta: [bubShort(a.model), a.type, a.running ? "running" : a.status].filter(Boolean).join(" · "),
      badge: null, sub: a,
    }));
    return {
      id: s.sessionId, kind, session: s.sessionId, chat: s.chat || null, live: !!s.active, title: s.chatTitle || s.title || "(untitled session)",
      glyph: BUB_KIND[kind], badge: s.userTurns || null, project: s.chatProject || null, adopt: s.adopt || null,
      meta: [bubShort(s.model), s.userTurns ? bubPlural(s.userTurns, "turn") : "", kids.length ? bubPlural(kids.length, "sub-agent") : "",
             s.active ? "running" : `last ${bubWhen(s.lastActive)}`].filter(Boolean).join(" · "),
      kids,
    };
  }
  // a conversation the index knows about but this machine has no transcript for (or a turn running with no session row yet)
  function bubChatGroup(c) {
    return { id: c.session_id || c.id, kind: "conversation", session: c.session_id || null, chat: c.id, live: !!c.running,
             title: c.title || "(untitled)", glyph: "message", badge: c.turns || null, project: c.project, adopt: null,
             meta: [bubShort(c.model), c.turns ? bubPlural(c.turns, "turn") : "", c.running ? "a turn is running" : `last ${bubWhen(c.last || c.created)}`].filter(Boolean).join(" · "),
             kids: [] };
  }
  function bubDisc(b, cls) {
    return `<button class="disc ${cls}" type="button" title="${esc(b.title)} — double-click for its history; drag onto another bubble to hand this reply over">
      <span class="gl">${glyph(b.glyph || "dot")}</span>${b.badge ? `<span class="n">${esc(String(b.badge))}</span>` : ""}</button>`;
  }
  function bubHTML(b, opts) {
    const acts = [];
    if (b.chat && !opts.hideEnter) acts.push(`<button class="btn tiny" type="button" data-enter="${esc(b.chat)}" title="open this conversation in the chat and keep talking to it">enter</button>`);
    if (!b.chat && b.session && opts.adopt) acts.push(b.adopt && b.adopt.ok
      ? `<button class="btn tiny" type="button" data-adopt="${esc(b.session)}" title="take this Claude Code session into the chat: the next turn resumes the same session">open in chat</button>`
      : `<button class="btn tiny" type="button" data-why="${esc((b.adopt && b.adopt.reason) || "")}" title="why this cannot be opened yet">why not</button>`);
    return `<div class="bub ${b.kind}${b.live ? " live" : ""}" data-bub="${esc(b.id)}"${b.session ? ` data-session="${esc(b.session)}"` : ""}${b.chat ? ` data-chat="${esc(b.chat)}"` : ""} tabindex="0">
      ${bubDisc(b, b.kids ? "big" : "kid")}
      <div class="cap"><b>${esc(b.title)}</b><span class="m">${esc(b.meta || "")}</span></div>
      ${acts.length ? `<div class="acts">${acts.join("")}</div>` : ""}</div>`;
  }
  function bubKidHTML(k) {
    return `<div class="bub agent${k.live ? " live" : ""}" data-bub="${esc(k.id)}" data-sub="${esc(k.id)}" tabindex="0">
      ${bubDisc(k, "kid")}<div class="cap"><b>${esc(k.title)}</b><span class="m">${esc(k.meta || "")}</span></div></div>`;
  }
  // the lines: spawns (parent -> each sub-agent) and handoffs (one conversation's reply fed to another), measured after layout
  function bubWires(el, groups, handoffs) {
    const svg = el.querySelector("svg.wires"); if (!svg) return;
    const box = el.getBoundingClientRect();
    const W = Math.max(el.scrollWidth, box.width), Hh = Math.max(el.scrollHeight, box.height);
    const at = sel => { const n = el.querySelector(sel); if (!n) return null; const r = n.getBoundingClientRect();
      return { x: r.left - box.left + el.scrollLeft + r.width / 2, y: r.top - box.top + el.scrollTop + r.height / 2, r: r.width / 2 }; };
    const parts = [];
    for (const g of groups) {
      const a = at(`[data-bub="${cssEsc(g.id)}"] > .disc`); if (!a) continue;
      for (const k of g.kids || []) {
        const b = at(`[data-bub="${cssEsc(k.id)}"] > .disc`); if (!b) continue;
        parts.push(`<path class="w spawn" d="M${a.x} ${a.y} C ${(a.x + b.x) / 2} ${a.y}, ${(a.x + b.x) / 2} ${b.y}, ${b.x} ${b.y}"/>`);
      }
    }
    for (const h of handoffs || []) {
      const a = at(`[data-chat="${cssEsc(h.from)}"] > .disc`), b = at(`[data-chat="${cssEsc(h.to)}"] > .disc`);
      if (!a || !b) continue;
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2 - Math.max(26, Math.abs(b.y - a.y) / 3);
      parts.push(`<path class="w hand" d="M${a.x} ${a.y} Q ${mx} ${my}, ${b.x} ${b.y}" marker-end="url(#bubarrow)"/>`);
      parts.push(`<text class="wl" x="${mx}" y="${my - 4}" text-anchor="middle">sent to</text>`);
    }
    svg.setAttribute("viewBox", `0 0 ${Math.round(W)} ${Math.round(Hh)}`);
    svg.setAttribute("width", Math.round(W)); svg.setAttribute("height", Math.round(Hh));
    svg.innerHTML = `<defs><marker id="bubarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 1 L9 5 L0 9 z" fill="var(--accent)"/></marker></defs>${parts.join("")}`;
  }
  const cssEsc = s => String(s ?? "").replace(/["\\]/g, "\\$&");
  // the field itself. opts: {small, adopt, hideEnter, onHistory(b), onEnter(chatId), onAdopt(sessionId), onHandoff(from, to), onWhy(text)}
  function bubPaint(el, groups, handoffs, opts = {}) {
    if (!el) return;
    el.classList.add("bubs"); el.classList.toggle("small", !!opts.small);
    el.innerHTML = `<svg class="wires" aria-hidden="true"></svg>` + (groups.length ? groups.map(g =>
      `<section class="bgrp"${g.chat ? ` data-grpchat="${esc(g.chat)}"` : ""}>${bubHTML(g, opts)}
        ${(g.kids || []).length ? `<div class="kids">${g.kids.map(bubKidHTML).join("")}</div>` : ""}</section>`).join("")
      : `<div class="empty">${esc(opts.emptyText || "nothing to draw here yet")}</div>`);
    if (!el.dataset.wired) { bubWire(el, opts); el.dataset.wired = "1"; }
    el._bubs = { groups, handoffs, opts };
    // measured off the real boxes: once now, and once on the next frame in case a fold or a font has still to settle.
    // A hidden tab never runs a frame callback, so the first call is the one that makes a background tab correct.
    bubWires(el, groups, handoffs || []);
    requestAnimationFrame(() => bubWires(el, groups, handoffs || []));
  }
  function bubFind(el, id) { const st = el._bubs || { groups: [] };
    for (const g of st.groups) { if (String(g.id) === String(id)) return g; for (const k of g.kids || []) if (String(k.id) === String(id)) return k; }
    return null; }
  function bubWire(el, opts) {
    const O = () => (el._bubs || {}).opts || opts || {};
    el.addEventListener("click", e => {
      const en = e.target.closest("[data-enter]"); if (en) { e.stopPropagation(); const f = O().onEnter; if (f) f(en.dataset.enter); return; }
      const ad = e.target.closest("[data-adopt]"); if (ad) { e.stopPropagation(); const f = O().onAdopt; if (f) f(ad.dataset.adopt); return; }
      const wy = e.target.closest("[data-why]"); if (wy) { e.stopPropagation(); const f = O().onWhy; if (f) f(wy.dataset.why); return; }
    });
    el.addEventListener("dblclick", e => {
      const b = e.target.closest(".bub"); if (!b) return;
      const f = O().onHistory; if (f) f(bubFind(el, b.dataset.bub) || { id: b.dataset.bub, session: b.dataset.session, chat: b.dataset.chat });
    });
    el.addEventListener("keydown", e => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const b = e.target.closest(".bub"); if (!b) return;
      e.preventDefault(); const f = O().onHistory; if (f) f(bubFind(el, b.dataset.bub) || { id: b.dataset.bub, session: b.dataset.session, chat: b.dataset.chat });
    });
    // the drawn form of send-to (T-0094): drag from one conversation's bubble onto another agent's bubble
    el.addEventListener("pointerdown", e => {
      const disc = e.target.closest(".disc"); if (!disc || e.button !== 0) return;
      const from = disc.closest(".bub"); if (!from || !O().onHandoff) return;
      const box = el.getBoundingClientRect(); const r = disc.getBoundingClientRect();
      const a = { x: r.left - box.left + el.scrollLeft + r.width / 2, y: r.top - box.top + el.scrollTop + r.height / 2 };
      let dragging = false, over = null;
      const svg = el.querySelector("svg.wires");
      const move = ev => {
        const d = Math.hypot(ev.clientX - (r.left + r.width / 2), ev.clientY - (r.top + r.height / 2));
        if (!dragging && d < 8) return;
        dragging = true; el.classList.add("dragging");
        const x = ev.clientX - box.left + el.scrollLeft, y = ev.clientY - box.top + el.scrollTop;
        const hit = document.elementFromPoint(ev.clientX, ev.clientY);
        const tgt = hit && hit.closest && hit.closest(".bub");
        if (over && over !== tgt) over.classList.remove("target");
        over = tgt && tgt !== from ? tgt : null;
        if (over) over.classList.add("target");
        let g = svg.querySelector("#bubdrag");
        if (!g) { svg.insertAdjacentHTML("beforeend", `<path id="bubdrag" class="w drag"/>`); g = svg.querySelector("#bubdrag"); }
        g.setAttribute("d", `M${a.x} ${a.y} L${x} ${y}`);
      };
      const up = () => {
        window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
        el.classList.remove("dragging");
        const g = svg.querySelector("#bubdrag"); if (g) g.remove();
        if (over) over.classList.remove("target");
        if (dragging && over) O().onHandoff(bubFind(el, from.dataset.bub) || { id: from.dataset.bub, session: from.dataset.session, chat: from.dataset.chat },
                                           bubFind(el, over.dataset.bub) || { id: over.dataset.bub, session: over.dataset.session, chat: over.dataset.chat });
      };
      window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
    });
    window.addEventListener("resize", () => { const st = el._bubs; if (st) bubWires(el, st.groups, st.handoffs || []); });
  }

  // ---- a conversation read back, read-only (2026-09-10, T-0117): the turns, the tool work folded ----
  // The same turns the chat page renders, without a composer: what a double-click on a bubble opens in the drawer.
  function histHTML(d) {
    const turns = (d && d.turns) || [], subs = (d && d.subagents) || [], head = (d && (d.session || d.chat)) || {};
    const tool = t => {
      const sa = t.name === "Agent" && subs.length ? subs.find(x => x.toolUseId === t.id) : null;
      const state = sa ? (sa.running ? "running" : sa.status) : t.done ? (t.error ? "failed" : "done") : "running";
      const cls = /^(done|completed)$/.test(state) ? "done" : /fail|error|not started/.test(state) ? "missing" : "open";
      return `<li><span class="name">${esc(t.name)}</span><span class="sum">${esc(t.summary || "")}</span><span class="badge ${cls}">${esc(state)}</span>
        ${sa && (sa.reportFull || sa.report) ? `<details class="rep"><summary>what it came back with</summary><article class="md">${md(sa.reportFull || sa.report)}</article></details>` : ""}</li>`;
    };
    const body = turns.map(t => t.role === "user"
      ? `<div class="msg user"><div class="bubble"><article class="md">${md(t.text)}</article></div><div class="m">${esc(bubWhen(t.ts))}</div></div>`
      : `<div class="msg bot"><article class="md">${md(t.text || "")}</article>
         ${(t.tools || []).length ? `<details class="work"><summary>worked · ${bubPlural((t.tools || []).length, "tool call")}</summary><ul>${t.tools.map(tool).join("")}</ul></details>` : ""}
         <div class="m">${esc(bubWhen(t.ts))}${t.model ? " · " + esc(bubShort(t.model)) : ""}</div></div>`).join("");
    const bits = [bubShort(head.model), head.userTurns || head.turns ? bubPlural(head.userTurns || head.turns, "turn") : "",
                  head.cwd ? "ran in " + esc(String(head.cwd).split(/[\\/]/).pop()) : "", head.branch ? "branch " + esc(head.branch) : ""].filter(Boolean);
    return `<div class="hist"><div class="m">${bits.join(" · ")}${d && d.note ? " · " + esc(d.note) : ""}</div>
      ${body || `<div class="empty">nothing was said in this one yet</div>`}</div>`;
  }
  async function histLoad(b) {
    const url = b.session ? `/api/session?id=${encodeURIComponent(b.session)}` : `/api/chat?id=${encodeURIComponent(b.chat)}`;
    const r = await fetch(url); const j = await r.json();
    if (!r.ok) throw new Error(j.error || ("the server answered " + r.status));
    return j;
  }

  // ---- send-to: one agent's reply handed to another (2026-09-10, T-0094) ----
  // Zak, 9/10: "the ability to draw a line from a chat to feed the answer into a higher leveled agent." The quoted reply
  // plus a note become the next message in the target conversation -- a new one with that agent, or one already going --
  // and the line between the two is recorded on both index rows (POST /api/chat/send carries `from`).
  const ST = { el: null, state: null };
  function sendToText(src, note) {
    const who = src.projectName || (src.project === "main" ? "the main agent" : src.project) || "another agent";
    const quote = String(src.text || "").trim().split("\n").map(l => "> " + l).join("\n");
    return [`This came from another conversation in the app: ${src.title || "an answer"} (${who})${src.turn ? `, answer ${src.turn}` : ""}.`,
            note ? note.trim() : "", "The reply, as it was written:", quote].filter(Boolean).join("\n\n");
  }
  function sendToClose() { if (ST.el) { ST.el.remove(); ST.el = null; ST.state = null; } }
  function sendToOpen(cfg) {
    sendToClose();
    const src = cfg.source || {}, projects = cfg.projects || [], chats = cfg.chats || [], models = cfg.models || [{ id: "opus", label: "opus", ok: true }];
    const st = ST.state = { target: cfg.target || { project: "main" }, model: cfg.model || "opus" };
    const el = ST.el = document.createElement("div");
    el.className = "sendto";
    const targetOptions = [`<option value="main">Main — the central agent</option>`]
      .concat(projects.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`)).join("");
    el.innerHTML = `<div class="scrim"></div><div class="sheet card">
      <div class="sh"><b>Hand this answer to another agent</b><button class="btn" type="button" data-cancel>close</button></div>
      <div class="quote"><article class="md">${md(String(src.text || "").slice(0, 900) + (String(src.text || "").length > 900 ? "\n\n…" : ""))}</article></div>
      <label class="fl"><span class="kicker">to</span><select data-target>${targetOptions}</select></label>
      <label class="fl"><span class="kicker">conversation</span><select data-conv></select></label>
      <label class="fl"><span class="kicker">model</span><span class="models" data-models></span></label>
      <label class="fl col"><span class="kicker">note (optional)</span><textarea rows="2" data-note placeholder="what you want checked or extended"></textarea></label>
      <div class="sh end"><span class="m" data-say></span><button class="btn primary" type="button" data-go>send</button></div></div>`;
    document.body.appendChild(el);
    const sel = el.querySelector("[data-target]"), conv = el.querySelector("[data-conv]");
    const paintModels = () => { el.querySelector("[data-models]").innerHTML = models.map(m =>
      `<button class="btn tiny ${st.model === m.id ? "on" : ""}" type="button" data-m="${esc(m.id)}"${m.ok ? "" : " disabled"} title="${esc(m.ok ? (m.resolves || m.id) : (m.note || "not available"))}">${esc(m.label)}</button>`).join(""); };
    const paintConv = () => {
      const pid = sel.value;
      const rows = chats.filter(c => c.project === pid && c.id !== src.chat);
      conv.innerHTML = `<option value="">a new conversation</option>` + rows.map(c =>
        `<option value="${esc(c.id)}">${esc(c.title || c.id)} — ${esc(bubPlural(c.turns || 0, "turn"))}</option>`).join("");
      if (st.target.chat && rows.some(c => c.id === st.target.chat)) conv.value = st.target.chat;
    };
    if (st.target.chat) { const row = chats.find(c => c.id === st.target.chat); if (row) sel.value = row.project; }
    else if (st.target.project) sel.value = st.target.project;
    paintModels(); paintConv();
    el.addEventListener("click", async e => {
      if (e.target.closest("[data-cancel]") || e.target.closest(".scrim")) return sendToClose();
      const m = e.target.closest("[data-m]"); if (m && !m.disabled) { st.model = m.dataset.m; paintModels(); return; }
      if (!e.target.closest("[data-go]")) return;
      const note = el.querySelector("[data-note]").value;
      const payload = { project: sel.value, chat: conv.value || null, model: st.model,
                        text: sendToText(src, note), from: { chat: src.chat, turn: src.turn || null } };
      el.querySelector("[data-say]").textContent = "handing it over…";
      try { await cfg.onSend(payload); sendToClose(); }
      catch (err) { el.querySelector("[data-say]").textContent = err.message; }
    });
    sel.addEventListener("change", paintConv);
    el.querySelector("[data-note]").focus();
    return el;
  }
  document.addEventListener("keydown", e => { if (e.key === "Escape" && ST.el && !typing(e)) sendToClose(); });

  // ---- the look (2026-09-22, ledger T-0208): the design tokens as a file that can be edited, swapped or imported ----
  // serve.py writes looks/default.css and the member's own look into every page's head as it serves it, ahead of the
  // shared stylesheet, and window.BV_LOOK names which one that was, so the first paint is already in the right look.
  // This is the swap after that: use(name) changes the link in place, with no reload, and keeps the old one until the
  // new one has loaded so nothing flashes unstyled in between. save(name) makes it this member's look on every page.
  const LOOK = { active: window.BV_LOOK || "default" };
  (function lookBase() {
    // a page reached some other way than the server's page route still gets the base tokens, or it has no design at all
    if (document.querySelector("link[data-look-base]")) return;
    const l = document.createElement("link");
    l.rel = "stylesheet"; l.href = "/static/looks/default.css"; l.setAttribute("data-look-base", "");
    const first = document.querySelector('link[rel="stylesheet"]');
    if (first && first.parentNode) first.parentNode.insertBefore(l, first); else document.head.appendChild(l);
  })();
  function lookUse(name) {
    name = String(name || "default");
    const old = document.getElementById("bv-look");
    LOOK.active = name;
    const done = () => { try { document.dispatchEvent(new CustomEvent("bv:look", { detail: { name } })); } catch (e) {} };
    if (name === "default") { if (old) old.remove(); done(); return Promise.resolve(name); }
    return new Promise(res => {
      const l = document.createElement("link");
      l.rel = "stylesheet"; l.href = `/static/looks/${encodeURIComponent(name)}.css?t=${Date.now()}`; l.dataset.look = name;
      const fin = () => { if (old && old !== l) old.remove(); l.id = "bv-look"; done(); res(name); };
      l.onload = fin; l.onerror = fin;
      const base = document.querySelector("link[data-look-base]");
      if (old && old.parentNode) old.parentNode.insertBefore(l, old.nextSibling);
      else if (base && base.parentNode) base.parentNode.insertBefore(l, base.nextSibling);
      else document.head.appendChild(l);
    });
  }
  async function lookPost(body) {
    const r = await fetch("/api/looks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    let j = null; try { j = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error((j && j.error) || ("the server answered " + r.status));
    return j;
  }
  async function lookSave(name) { const j = await lookPost({ active: name }); await lookUse(j.active); return j; }
  async function lookList() { const r = await fetch("/api/looks"); return r.json(); }
  // a .css file picked from disk becomes a look in the folder; activate makes it this member's look straight away
  async function lookImport(file, opts = {}) {
    const css = await file.text();
    const j = await lookPost({ name: opts.name || file.name, css, replace: !!opts.replace, activate: opts.activate !== false });
    if (j.activated && j.activated.ok) await lookUse(j.name);
    return j;
  }
  // the faces the active look declares, read off the page as it stands: {title, display, ui, mono} -> font stacks
  function lookFaces() {
    const cs = getComputedStyle(document.documentElement), out = {};
    for (const k of ["title", "display", "ui", "mono"]) out[k] = cs.getPropertyValue("--font-" + k).trim();
    return out;
  }

  nav();   // the header sits above this script on every page, so the nav is painted before anything else runs

  return { esc, owner: OWNER,
           look: { get active() { return LOOK.active; }, use: lookUse, save: lookSave, list: lookList, import: lookImport, faces: lookFaces }, inline, md, color, tint, soften, isImage, lightbox, mode, proposedText, teamStrip, proposeBox, typing,
           slug, isDoc, readerHref, readerLink, forgeHref, openFile: drawerOpen, drawer: { open: drawerOpen, jump: drawerJump },
           glyph: Object.assign(glyph, { GLYPH, BY_TERM: GLYPH_BY_TERM, BY_GROUP: GLYPH_BY_GROUP, svg: glyphSvg, PURPLE: GLYPH_PURPLE }),
           ownerBadge, fileLink, personChips, idTag, grow: growBox, ledgerAct, itemRow, questionCard, badges, paintNavCounts, refreshBadges,
           ledgerText, ledger: { text: ledgerText, learn: learnLedger, prime: primeLedgers, repaint: repaintRefs, find: findRef, face: refFace },
           replies: { act: replyAct, pending: pendingReply, wire: wireReplies, box: replyBox, show: showNote },
           holds: { act: holdAct, wire: wireHolds, is: heldNow, control: holdControl, days: HOLD_DAYS },
           day: { model: dayModel, load: dayLoad, recentDays: DAY_RECENT_DAYS, tomorrow: () => plusDays(1), newest: byNewestDay },
           nav, showAll, mountShowAll, resizable,
           search: { mount: mountSearch, run: fsRun, close: fsClose },
           back: { go: goBack, on: onBack, push: trailPush, paint: paintBack, target: backTarget },
           glossary: { load: glLoad, scan: glScan, mount: glMount, keysHint, open: openGlossary, data: GL },
           help: { load: helpLoad, open: helpOpen, close: helpClose, entry: helpEntry,
                   get extra() { return HELP.extra; }, set extra(fn) { HELP.extra = fn; } },
           quests: { load: questLoad, mount: questMount, refresh: questRefresh, timeline: mountTimeline, timelineHTML, route: routeIn, target: questTarget, result: questResult, text: questText, dock: questDock, data: Q },
           notepad: { mount: notepadMount, open: notepadOpen, data: N, isNote: p => /^thoughts\/notepad\/[^/]+\.md$/.test(p || "") },
           bubbles: { paint: bubPaint, group: bubGroup, chatGroup: bubChatGroup, wires: bubWires, when: bubWhen, shortModel: bubShort },
           history: { html: histHTML, load: histLoad },
           sendTo: { open: sendToOpen, close: sendToClose, text: sendToText },
           stages: { load: stageLoad, mount: mountStageLine, html: stageHTML, data: S } };
})();
