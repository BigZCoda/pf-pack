// The build order: how far through the current milestone the work is, and what is next.
BV.widgets.register({
  id: "stages", contract: 1, title: "Build order", size: "4", defaultOn: false,
  source: "the milestone being worked through, read back as an ordered build order (GET /api/stages)",
  mount: (el, api) => api.auto("/api/stages", j => {
    const rest = (j.steps || []).filter(s => s.state !== "done");
    return { count: (j.doneCount || 0) + " of " + (j.total || 0) + " done",
             lines: rest.slice(0, 3).map(s => ({ text: api.clip(s.short || s.text, 66),
                                                 href: "/projects?id=" + encodeURIComponent(s.project),
                                                 title: s.text || "", tail: s.state || "" })),
             max: 3, note: rest.length ? "" : "every step is done",
             link: { href: "/projects", text: "the project holding it" } };
  }),
});
