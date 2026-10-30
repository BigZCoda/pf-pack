// Search the brain from the board: threads, tasks and questions, people, then files, as the header's box finds them
// (0.100.0; a file finder before it). The four best rows across the kinds, each opening where its kind is read.
BV.widgets.register({
  id: "search", contract: 1, title: "Search the brain", size: "4", defaultOn: false,
  source: "the header's search (GET /api/search): threads, tasks and questions, people, then files; filter words work here too",
  refresh() {},   // it is holding a query and its hits
  mount(el, api) {
    api.count("");
    el.innerHTML = '<div class="wrow"><input type="search" placeholder="words, or is:open, thread:, for:me" aria-label="search the brain">'
      + '<button class="btn" type="button">find</button></div><ul class="wlines" data-out></ul>';
    const box = el.querySelector("input"), btn = el.querySelector("button"), out = el.querySelector("[data-out]");
    const KIND = { thread: "thread", task: "task", question: "question", person: "person", chat: "chat", doc: "file" };
    const href = r => r.href || ("/reader?path=" + encodeURIComponent(r.path) + (r.line > 1 ? "&line=" + r.line : ""));
    async function go() {
      const q = box.value.trim(); if (!q) return;
      out.innerHTML = "<li><span class=\"wl\">looking</span></li>";
      try {
        const j = await api.get("/api/search?limit=4&q=" + encodeURIComponent(q));
        const rows = (j.groups || []).flatMap(g => g.rows).slice(0, 4);
        api.count((j.total || 0) + " found");
        out.innerHTML = rows.map(r =>
          '<li><a href="' + api.esc(href(r)) + '" title="' + api.esc(r.snippet || r.stands || r.path || "") + '">'
          + api.esc(api.clip(r.title || r.path, 60)) + '</a><span class="wt">' + api.esc(KIND[r.kind] || r.kind) + "</span></li>").join("")
          || '<li><span class="wl">' + api.esc(j.error || "nothing found") + "</span></li>";
      } catch (e) { out.innerHTML = '<li><span class="wl">' + api.esc(e.message) + "</span></li>"; }
    }
    btn.onclick = go;
    box.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); go(); } };
  },
});
