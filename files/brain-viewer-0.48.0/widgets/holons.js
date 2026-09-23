// The registry: how many parts the brain declares, and how many of their folders are really there.
BV.widgets.register({
  id: "holons", contract: 1, title: "The registry", size: "4", defaultOn: false,
  source: "every part the brain declares, and whether its folder is really there (GET /api/holons)",
  mount: (el, api) => api.auto("/api/holons", j => {
    const rows = j.holons || [];
    const gone = rows.filter(h => h.exists === false).length;
    return { count: api.plural(rows.length, "part"),
             lines: [{ text: gone ? api.plural(gone, "folder") + " named but not there" : "every folder is there",
                       href: "/holons" }], max: 1,
             link: { href: "/holons", text: "read the registry" } };
  }),
});
