// The notes you have taken in this app, newest first. Each one opens in the reader.
BV.widgets.register({
  id: "notepad", contract: 1, title: "Your notes", size: "4", defaultOn: false,
  source: "the notes you have taken in this app, newest first (GET /api/notes)",
  mount: (el, api) => api.auto("/api/notes?limit=3", j => ({
    count: api.plural(j.count || 0, "note"),
    lines: (j.notes || []).slice(0, 3).map(n => ({ text: api.clip(n.title, 62), href: "/reader?path=" + encodeURIComponent(n.path),
                                                   title: n.taken || "", tail: api.when(n.mtime) })),
    max: 3, link: { href: "/reader", text: "open the reader" },
  })),
});
