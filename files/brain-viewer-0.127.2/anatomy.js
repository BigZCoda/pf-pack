// anatomy.js -- a page's pieces drawn on the page itself, from the Anatomy (viewer 0.110.0, 2026-11-10, brain-central
// Q-0094: the Anatomy becomes the file the viewer reads). Opened from the "?" panel's "show its pieces on the page".
// It reads skills/brain-viewer/anatomy.json (through GET /api/file), finds this page by its address, and outlines its big
// pieces where they sit; a press on a piece scrolls to it and outlines what is inside it, down to numbered parts. The
// key on the right says what each piece is, and for a piece that is one of the brain's types (a task, a question, a
// thread, a project) it carries that type's facets too. Nothing on the page changes: the outlines float over it and go
// with Escape or the close press. The same file is meant to let the viewer draw pages from the Anatomy later, and to
// carry dashboards and customization, on the owner's word that day.
// 2026-11-10, the fixes from filming the example brain (brain-viewer T-0418 to T-0422, on the owner's yes that evening):
// the file comes from GET /api/anatomy, the brain's copy else the code's own (through /api/file it was the brain's alone,
// so every brain but the owner's said it could not be read); a piece is looked up inside the piece above it and a part
// inside its piece (looked up across the whole page, a part's pin sat on another card and a piece missing from its
// section outlined one in another); and on a phone the piece goes to the top of the window, above the key's sheet.
(function () {
  if (window.BVAnatomy) return;
  const FILE = "skills/brain-viewer/anatomy.json";
  const A = { doc: null, trail: [], layer: null, key: null, raf: 0, hot: null, on: false };
  const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const css = `
  #bv-anat-layer { position: fixed; inset: 0; z-index: 9000; pointer-events: none; }
  #bv-anat-layer .ov { position: fixed; pointer-events: auto; border: 2px solid var(--accent, #631111); border-radius: 5px;
    background: color-mix(in srgb, var(--accent, #631111) 5%, transparent); cursor: zoom-in; box-sizing: border-box; }
  #bv-anat-layer .ov:hover, #bv-anat-layer .ov.hot { background: color-mix(in srgb, var(--accent, #631111) 13%, transparent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent, #631111) 20%, transparent); }
  #bv-anat-layer .ov .tag { position: absolute; left: -2px; top: 0; transform: translateY(-100%); background: var(--accent, #631111);
    color: var(--surface, #fbf6e4); font: 700 12px/1 var(--font-ui, Georgia, serif); padding: 5px 8px 4px; border-radius: 4px 4px 4px 0; white-space: nowrap; }
  #bv-anat-layer .here { position: fixed; border: 2px dashed var(--accent, #631111); border-radius: 6px; box-sizing: border-box; }
  #bv-anat-layer .pin { position: fixed; pointer-events: auto; width: 22px; height: 22px; margin: -11px 0 0 -11px; border-radius: 50%;
    background: var(--accent, #631111); color: var(--surface, #fbf6e4); font: 700 11px/22px ui-monospace, Consolas, monospace;
    text-align: center; border: 0; padding: 0; cursor: pointer; box-shadow: 0 0 0 2px var(--surface, #fbf6e4), 0 1px 3px rgba(0,0,0,.35); }
  #bv-anat-layer .pin.hot { background: var(--ink, #2b2925); }
  #bv-anat-layer .hl { position: fixed; border: 2px dashed var(--accent, #631111); border-radius: 4px;
    background: color-mix(in srgb, var(--accent, #631111) 8%, transparent); }
  #bv-anat-key { position: fixed; right: 12px; top: 84px; width: 340px; max-height: calc(100vh - 100px); overflow-y: auto; z-index: 9001;
    background: var(--surface, #fbf6e4); color: var(--ink, #2b2925); border-radius: 6px; padding: 14px 16px 16px;
    box-shadow: inset 0 0 0 3px var(--surface, #fbf6e4), inset 0 0 0 4px var(--rule, #8e8c86), 0 8px 24px rgba(0,0,0,.18);
    font: 14px/1.5 var(--font-ui, Georgia, serif); }
  @media (max-width: 700px) { #bv-anat-key { left: 8px; right: 8px; top: auto; bottom: 8px; width: auto; max-height: 46vh; } }
  #bv-anat-key .kh { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; font-size: 12.5px; }
  #bv-anat-key .kh button { font: inherit; background: none; border: 0; padding: 0 2px; color: var(--accent, #631111); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
  #bv-anat-key .kh button[aria-current="true"] { color: var(--ink, #2b2925); text-decoration: none; font-weight: 700; cursor: default; }
  #bv-anat-key .kh .sep { color: var(--rule, #8e8c86); }
  #bv-anat-key .kh .x { margin-left: auto; text-decoration: none; font-size: 15px; }
  #bv-anat-key h2 { font: 700 18px/1.25 var(--font-display, Georgia, serif); margin: 2px 0 4px; }
  #bv-anat-key .means { color: var(--muted, #5a5957); margin: 0 0 10px; }
  #bv-anat-key h3 { font: 600 11px ui-monospace, Consolas, monospace; letter-spacing: .1em; text-transform: uppercase; color: var(--muted, #5a5957); margin: 12px 0 6px; }
  #bv-anat-key ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
  #bv-anat-key li { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 8px; padding: 5px 6px; border-radius: 3px; cursor: pointer; }
  #bv-anat-key li:hover, #bv-anat-key li.hot { background: color-mix(in srgb, var(--accent, #631111) 12%, transparent); }
  #bv-anat-key li.away { opacity: .55; cursor: default; }
  #bv-anat-key .num { width: 22px; height: 22px; border-radius: 50%; background: var(--accent, #631111); color: var(--surface, #fbf6e4); font: 700 11px/22px ui-monospace, Consolas, monospace; text-align: center; }
  #bv-anat-key .go { width: 22px; height: 22px; border-radius: 4px; border: 2px solid var(--accent, #631111); color: var(--accent, #631111); font: 700 12px/18px ui-monospace, monospace; text-align: center; box-sizing: border-box; }
  #bv-anat-key .term { font-weight: 700; }
  #bv-anat-key .what { display: block; }
  #bv-anat-key .note { color: var(--muted, #5a5957); font-style: italic; }
  #bv-anat-key details.type { margin-top: 10px; border-top: 1px solid var(--rule-soft, #d8d0b8); padding-top: 8px; }
  #bv-anat-key details.type summary { cursor: pointer; font-weight: 700; }
  #bv-anat-key dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 3px 10px; margin: 8px 0 0; font-size: 13px; }
  #bv-anat-key dt { font-family: ui-monospace, Consolas, monospace; color: var(--facet, #7a5a12); }
  #bv-anat-key dd { margin: 0; }
  `;
  async function load() {
    if (A.doc) return A.doc;
    // the viewer's own file, wherever the brain is (T-0418); a server older than /api/anatomy is asked through /api/file
    let r = await fetch("/api/anatomy");
    if (r.status === 404 && !(await r.clone().json().catch(() => ({}))).path) r = await fetch("/api/file?path=" + encodeURIComponent(FILE));
    const j = await r.json();
    if (!r.ok || !j.text) throw new Error(j.error || "the Anatomy file could not be read");
    A.doc = JSON.parse(j.text);
    return A.doc;
  }
  const node = () => A.trail[A.trail.length - 1];
  // the idx-th match of sel inside scope (T-0419, T-0420): a part is never looked for outside the piece it belongs to
  const within = (sel, idx, scope) => {
    if (sel === "body") return document.body;
    let list;
    try { list = [...document.querySelectorAll(sel)]; } catch (e) { return null; }
    if (scope && scope !== document.body) list = list.filter(x => scope.contains(x));
    return list[idx || 0] || null;
  };
  // the element of the trail's i-th piece, each looked up inside the one before it; the first is the page itself
  const elAt = i => { let el = document.body; for (let j = 1; j <= i; j++) { el = within(A.trail[j].sel, A.trail[j].idx, el); if (!el) return null; } return el; };
  const scopeEl = () => elAt(A.trail.length - 1);
  const find = n => within(n.sel, n.idx, scopeEl());        // a piece inside the one the key shows
  const findPart = p => within(p.sel, p.idx, scopeEl());    // a part of the piece the key shows
  // inside a closed fold (a <details> not open, outside its summary) a thing keeps a box but is not drawn, so it counts
  // as not showing: until 11/10 a holon row in the closed fold at the foot of /projects was outlined as an empty band
  const folded = el => {
    for (let d = el.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) {
      if (d.open || d === el) continue;
      const s = d.querySelector(":scope > summary");
      if (!(s && s.contains(el))) return true;
    }
    return false;
  };
  const boxOf = el => { if (!el || folded(el)) return null; const r = el.getBoundingClientRect(); return (r.width || r.height) ? r : null; };
  // on a phone the key is a sheet over the bottom of the window (T-0422): a piece goes to the top, under the bar, and the
  // page gets room at its foot, inside whatever scrolls it, so the last pieces can come up that far too
  const narrow = () => window.innerWidth <= 700;
  const scrollerOf = el => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/(auto|scroll)/.test(cs.overflowY) && p.scrollHeight > p.clientHeight + 1) return p;
    }
    return document.scrollingElement || document.documentElement;
  };
  function room(sc) {
    if (!narrow() || !A.key) return;
    let r = document.getElementById("bv-anat-room");
    if (!r) { r = document.createElement("div"); r.id = "bv-anat-room"; r.setAttribute("aria-hidden", "true"); }
    if (r.parentElement !== sc) (sc === document.documentElement || sc === document.scrollingElement ? document.body : sc).appendChild(r);
    // a whole window of room: the last piece on the page can then come up to the top like any other
    const doc = sc === document.documentElement || sc === document.scrollingElement;
    r.style.height = Math.ceil(doc ? window.innerHeight : sc.clientHeight) + "px";
  }
  // a piece fixed to the window (the send press, a corner) cannot be scrolled clear of the sheet: the sheet goes on top
  const pinned = el => { for (let p = el; p && p !== document.body; p = p.parentElement) if (getComputedStyle(p).position === "fixed") return true; return false; };
  function bring(el) {
    if (!el) return;
    if (!narrow()) { el.scrollIntoView({ block: "center", behavior: "smooth" }); return; }
    const sc = scrollerOf(el); room(sc);
    const bar = document.querySelector("header.bar"), top = Math.max(bar ? bar.getBoundingClientRect().bottom : 0,
      sc === document.scrollingElement || sc === document.documentElement ? 0 : sc.getBoundingClientRect().top);
    sc.scrollTo({ top: sc.scrollTop + el.getBoundingClientRect().top - top - 10, behavior: "smooth" });
  }
  function layer() {
    if (!document.getElementById("bv-anat-style")) { const s = document.createElement("style"); s.id = "bv-anat-style"; s.textContent = css; document.head.appendChild(s); }
    if (!A.layer) { A.layer = document.createElement("div"); A.layer.id = "bv-anat-layer"; document.body.appendChild(A.layer); }
    if (!A.key) { A.key = document.createElement("aside"); A.key.id = "bv-anat-key"; A.key.setAttribute("aria-live", "polite"); document.body.appendChild(A.key); }
  }
  function place(el, r, pad) { Object.assign(el.style, { left: (r.left - pad) + "px", top: (r.top - pad) + "px", width: (r.width + 2 * pad) + "px", height: (r.height + 2 * pad) + "px" }); }
  function draw() {
    A.raf = 0; if (!A.on) return;
    A.layer.replaceChildren();
    const n = node();
    const here = A.trail.length > 1 && boxOf(scopeEl());
    if (here) { const h = document.createElement("div"); h.className = "here"; place(h, here, 8); A.layer.appendChild(h); }
    (n.kids || []).forEach((k, i) => {
      const r = boxOf(find(k)); if (!r) return;
      const o = document.createElement("div"); o.className = "ov" + (A.hot === "k" + i ? " hot" : ""); o.dataset.k = i; place(o, r, 3);
      o.innerHTML = '<span class="tag">' + esc(k.name) + "</span>";
      if (r.top < 24) o.firstChild.style.transform = "none";   // a piece at the window's top edge carries its name inside

      o.addEventListener("click", ev => { ev.preventDefault(); ev.stopPropagation(); go(k); });
      o.addEventListener("mouseenter", () => hot("k" + i)); o.addEventListener("mouseleave", () => hot(null));
      A.layer.appendChild(o);
    });
    const taken = [];
    (n.parts || []).forEach((p, i) => {
      const r = boxOf(findPart(p)); if (!r) return;
      let x = r.left + 2, y = r.top + 2;
      while (taken.some(t => Math.abs(t[0] - x) < 24 && Math.abs(t[1] - y) < 24)) x += 25;
      taken.push([x, y]);
      const b = document.createElement("button"); b.type = "button"; b.className = "pin" + (A.hot === "p" + i ? " hot" : ""); b.textContent = i + 1;
      b.title = p.term + ": " + p.means; b.style.left = x + "px"; b.style.top = y + "px";
      b.addEventListener("click", ev => { ev.preventDefault(); ev.stopPropagation(); const li = A.key.querySelector('li[data-p="' + i + '"]'); if (li) li.scrollIntoView({ block: "nearest" }); hot("p" + i); });
      b.addEventListener("mouseenter", () => hot("p" + i)); b.addEventListener("mouseleave", () => hot(null));
      A.layer.appendChild(b);
      if (A.hot === "p" + i) { const h = document.createElement("div"); h.className = "hl"; place(h, r, 3); A.layer.appendChild(h); }
    });
  }
  const redraw = () => { if (A.on && !A.raf) A.raf = requestAnimationFrame(draw); };
  function hot(id) {
    A.hot = id;
    A.key.querySelectorAll("li").forEach(li => li.classList.toggle("hot", id != null && ("k" + li.dataset.k === id || "p" + li.dataset.p === id)));
    draw();
  }
  function paintKey() {
    const n = node(), doc = A.doc;
    const crumbs = A.trail.map((t, i) => (i ? '<span class="sep">›</span>' : "") + '<button type="button" data-i="' + i + '"' + (i === A.trail.length - 1 ? ' aria-current="true"' : "") + ">" + esc(t.name) + "</button>").join("");
    let h = '<div class="kh">' + crumbs + '<button type="button" class="x" title="close the pieces (Escape)">×</button></div>';
    h += "<h2>" + esc(n.name) + '</h2><p class="means">' + esc(n.means) + "</p>";
    if ((n.kids || []).length) h += "<h3>Its pieces · press one to go inside</h3><ol>" + n.kids.map((k, i) => {
      const away = !boxOf(find(k));
      return '<li data-k="' + i + '" class="' + (away ? "away" : "") + '"><span class="go">›</span><span><span class="term">' + esc(k.name) + '</span><span class="what">' + esc(k.means) + "</span>" + (away ? '<span class="note">not on the page right now</span>' : "") + "</span></li>";
    }).join("") + "</ol>";
    if ((n.parts || []).length) h += "<h3>Its parts</h3><ol>" + n.parts.map((p, i) => {
      const away = !boxOf(findPart(p));
      return '<li data-p="' + i + '" class="' + (away ? "away" : "") + '"><span class="num">' + (i + 1) + '</span><span><span class="term">' + esc(p.term) + '</span><span class="what">' + esc(p.means) + "</span>" + (away ? '<span class="note">not showing on this one; it shows when the item has it, or opens</span>' : "") + "</span></li>";
    }).join("") + "</ol>";
    const ty = n.type && doc.types && doc.types[n.type];
    if (ty) h += '<details class="type"><summary>It is a ' + esc(ty.name.toLowerCase()) + ": its " + (ty.facets || []).length + " facets</summary><p>" + esc(ty.means) + "</p><p><b>Fits into:</b> " + esc(ty.fits) + "</p><dl>"
      + (ty.facets || []).map(f => "<dt>" + esc(f.name) + "</dt><dd>" + esc(f.means) + "</dd>").join("") + "</dl></details>";
    A.key.innerHTML = h;
    A.key.querySelectorAll(".kh button[data-i]").forEach(b => b.addEventListener("click", () => { const i = +b.dataset.i; if (i < A.trail.length - 1) { A.trail = A.trail.slice(0, i + 1); show(); if (A.trail.length > 1) bring(scopeEl()); } }));
    A.key.querySelector(".kh .x").addEventListener("click", close);
    A.key.querySelectorAll("li[data-k]").forEach(li => {
      li.addEventListener("click", () => { if (!li.classList.contains("away")) go(n.kids[+li.dataset.k]); });
      li.addEventListener("mouseenter", () => hot("k" + li.dataset.k)); li.addEventListener("mouseleave", () => hot(null));
    });
    A.key.querySelectorAll("li[data-p]").forEach(li => { li.addEventListener("mouseenter", () => hot("p" + li.dataset.p)); li.addEventListener("mouseleave", () => hot(null)); });
  }
  function show() {
    A.hot = null; paintKey();
    // the key never sits on the piece it explains: a piece in the right-hand part of the window puts the key on the left
    const el = A.trail.length > 1 ? scopeEl() : null, r = boxOf(el), wide = !narrow();
    const left = wide && r && r.right > window.innerWidth - 370 && r.left > 360;
    A.key.style.left = left ? "12px" : ""; A.key.style.right = left ? "auto" : "";
    // on a phone the sheet sits at the foot, unless the piece is fixed down there itself (T-0422)
    const top = !wide && r && pinned(el) && r.top > window.innerHeight / 2;
    A.key.style.top = top ? "8px" : ""; A.key.style.bottom = top ? "auto" : "";
    draw();
  }
  function go(k) {
    A.trail.push(k);
    show();                                   // the key first, so on a phone its sheet's height is known
    const el = scopeEl();
    if (el && el !== document.body) bring(el);
  }
  function up() { if (A.trail.length > 1) { A.trail.pop(); show(); if (A.trail.length > 1) bring(scopeEl()); } else close(); }
  const onKey = e => { if (e.key === "Escape" && A.on) { e.preventDefault(); up(); } };
  async function open() {
    try { await load(); }
    catch (e) { (window.BV && BV.toast ? BV.toast : alertish)("The Anatomy could not be read: " + e.message); return; }
    const p = A.doc.pages && A.doc.pages[location.pathname];
    if (!p) { (window.BV && BV.toast ? BV.toast : alertish)("No pieces are written for this page in the Anatomy yet."); return; }
    layer();
    A.trail = [Object.assign({}, p, { kids: (p.kids || []).concat(A.doc.corners || []) })];
    A.on = true;
    document.addEventListener("scroll", redraw, true); window.addEventListener("resize", redraw); document.addEventListener("keydown", onKey, true);
    show();
  }
  function close() {
    A.on = false;
    document.removeEventListener("scroll", redraw, true); window.removeEventListener("resize", redraw); document.removeEventListener("keydown", onKey, true);
    if (A.layer) { A.layer.remove(); A.layer = null; }
    if (A.key) { A.key.remove(); A.key = null; }
    const room = document.getElementById("bv-anat-room"); if (room) room.remove();
  }
  // every piece and part of this page, looked up the way the key looks them up (each inside the piece above it), with
  // whether it is on the page: for the test runs on the example brain (pf-video), and for a session checking a page
  async function audit() {
    await load();
    const pg = A.doc.pages && A.doc.pages[location.pathname];
    if (!pg) return { page: location.pathname, error: "no pieces written for this page" };
    const rows = [];
    const look = (kind, trail, name, sel, idx, scope) => {
      const el = scope ? within(sel, idx, scope) : null;
      rows.push({ kind, trail, name, sel, idx: idx || 0, state: boxOf(el) ? "found" : el ? "in the page, no box" : "not on the page",
        text: el ? String(el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 70) : "" });
      return el;
    };
    const walk = (n, trail, scope) => {
      const el = trail.length ? look("piece", trail.join(" › "), n.name, n.sel, n.idx, scope) : document.body;
      const t = trail.concat(n.name);
      for (const p of n.parts || []) look("part", t.join(" › "), p.term, p.sel, p.idx, el);
      for (const k of n.kids || []) walk(k, t, el);
    };
    walk(Object.assign({}, pg, { kids: (pg.kids || []).concat(A.doc.corners || []) }), [], document.body);
    return { page: location.pathname, rows };
  }
  function alertish(msg) {
    const d = document.createElement("div"); d.textContent = msg;
    Object.assign(d.style, { position: "fixed", right: "16px", bottom: "16px", zIndex: 9002, background: "var(--ink, #2b2925)", color: "var(--surface, #fbf6e4)", padding: "10px 14px", borderRadius: "4px", font: "13px/1.4 var(--font-ui, Georgia, serif)", maxWidth: "320px" });
    document.body.appendChild(d); setTimeout(() => d.remove(), 5000);
  }
  window.BVAnatomy = { open, close, audit };
})();
