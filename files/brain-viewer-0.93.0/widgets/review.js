// The proposals waiting for a verdict, and the first three of them.
BV.widgets.register({
  id: "review", contract: 1, title: "To rate", size: "4", defaultOn: false,
  source: "Claude's proposals waiting for your verdict (GET /api/review)",
  mount: (el, api) => api.auto("/api/review", j => ({
    count: api.plural(j.waiting || (j.cards || []).length, "card"),
    lines: (j.cards || []).slice(0, 3).map(c => ({ text: api.clip(c.proposal, 78), href: "/from-claude",
                                                   title: c.proposal || "", tail: c.kind || "" })),
    max: 3, note: (j.cards || []).length ? "" : "nothing waiting",
    link: { href: "/from-claude", text: "rate them" },
  })),
});
