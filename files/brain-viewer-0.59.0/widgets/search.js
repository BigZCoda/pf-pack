// Find a file in the brain from the board: by its name or by what is written in it.
BV.widgets.register({
  id: "search", contract: 1, title: "Find a file", size: "4", defaultOn: false,
  source: "a search of the brain's files, by name and by text (GET /api/search)",
  refresh() {},   // it is holding a query and its hits
  mount(el, api) {
    api.count("");
    el.innerHTML = '<div class="wrow"><input type="search" placeholder="name or words in the file" aria-label="find a file">'
      + '<button class="btn" type="button">find</button></div><ul class="wlines" data-out></ul>';
    const box = el.querySelector("input"), btn = el.querySelector("button"), out = el.querySelector("[data-out]");
    async function go() {
      const q = box.value.trim(); if (!q) return;
      out.innerHTML = "<li><span class=\"wl\">looking</span></li>";
      try {
        const j = await api.get("/api/search?limit=3&q=" + encodeURIComponent(q));
        api.count(api.plural(j.count || 0, "hit"));
        out.innerHTML = (j.items || []).slice(0, 3).map(i =>
          '<li><a href="/reader?path=' + encodeURIComponent(i.path) + '" title="' + api.esc(i.snippet || "") + '">'
          + api.esc(api.clip(i.path, 60)) + '</a><span class="wt">' + api.esc(i.mtime || "") + "</span></li>").join("")
          || '<li><span class="wl">nothing found</span></li>';
      } catch (e) { out.innerHTML = '<li><span class="wl">' + api.esc(e.message) + "</span></li>"; }
    }
    btn.onclick = go;
    box.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); go(); } };
  },
});
