// One line: how many parts of the brain wrote a status about themselves, and how stale the stalest one is.
BV.widgets.register({
  id: "status", contract: 1, title: "Status files", size: "4", defaultOn: false,
  source: "the status file each part of the brain wrote about itself, and how old it is (GET /api/status)",
  mount: (el, api) => api.auto("/api/status", j => {
    const rows = j.holons || [];
    const oldest = rows.reduce((a, r) => (r.ageHours != null && (a == null || r.ageHours > a.ageHours) ? r : a), null);
    return { count: api.plural(rows.length, "status file"),
             lines: oldest ? [{ text: oldest.name + " is the stalest", href: "/home#lamps", title: oldest.path || "",
                                tail: Math.round(oldest.ageHours) + "h old" }] : [],
             max: 1, link: { href: "/home#lamps", text: "read them" } };
  }),
});
