// What landed today: the transcripts carrying today's date, and whether each has been taken in yet.
BV.widgets.register({
  id: "landed", contract: 1, title: "Landed today", size: "4", defaultOn: false,
  source: "the transcripts whose name carries today's date, and their intake state (GET /api/landed)",
  mount: (el, api) => api.auto("/api/landed", j => ({
    count: (j.count || 0) + " landed \u00b7 " + (j.intaken || 0) + " taken in",
    lines: (j.landed || []).slice(0, 3).map(r => ({ text: api.clip(r.stem, 62), href: "/today", title: r.stem,
                                                    tail: r.report ? "taken in" : "not yet" })),
    max: 3, note: (j.count || 0) ? "" : "nothing landed today",
    link: { href: "/today", text: "the day page" },
  })),
});
