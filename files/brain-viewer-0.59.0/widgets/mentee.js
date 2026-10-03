// The mentee content: how many stages the programme has and how many pieces sit under them.
BV.widgets.register({
  id: "mentee", contract: 1, title: "Mentee content", size: "4", defaultOn: false,
  source: "the mentee-facing pieces in programme order (GET /api/manifest)",
  mount: (el, api) => api.auto("/api/manifest", j => {
    const stages = j.stages || [];
    const pieces = stages.reduce((a, s) => a + (s.pieces || []).length, 0);
    const missing = stages.reduce((a, s) => a + (s.pieces || []).filter(p => p.exists === false).length, 0);
    return { count: api.plural(stages.length, "stage") + " \u00b7 " + api.plural(pieces, "piece"),
             lines: [{ text: missing ? api.plural(missing, "piece") + " not written yet" : "every piece exists",
                       href: "/mentee" }], max: 1,
             link: { href: "/mentee", text: "the dashboard" } };
  }),
});
