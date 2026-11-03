// The standing call threads: the groups of people who meet on a cadence, with how much is open for each.
BV.widgets.register({
  id: "threads", contract: 1, title: "Call threads", size: "4", defaultOn: false,
  source: "the standing call threads and what is open on each (GET /api/groups)",
  mount: (el, api) => api.auto("/api/groups", j => ({
    count: api.plural((j.groups || []).length, "thread"),
    lines: (j.groups || []).slice(0, 3).map(g => ({ text: g.name || g.id, href: "/people",
                                                    title: g.cadence || "", tail: g.open ? g.open + " open" : "" })),
    max: 3, link: { href: "/people", text: "the people page" },
  })),
});
