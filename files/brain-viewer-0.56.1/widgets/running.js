// What is live on this machine right now: the sessions with a turn in flight and the sub-agents under them.
BV.widgets.register({
  id: "running", contract: 1, title: "Running now", size: "4", defaultOn: false,
  source: "the sessions and sub-agents live on this machine (GET /api/agents)",
  mount: (el, api) => api.auto("/api/agents", j => {
    const live = (j.sessions || []).filter(s => s.active);
    const subs = live.reduce((a, s) => a + ((s.counts || {}).running || 0), 0);
    return {
      count: live.length ? api.plural(live.length, "session") + " \u00b7 " + api.plural(subs, "sub-agent") : "nothing running",
      lines: live.slice(0, 3).map(s => ({ text: api.clip(s.title || "untitled session", 64), href: "/agents",
                                          title: s.title || "", tail: api.when(s.lastActive) })),
      max: 3, link: { href: "/agents", text: "every session drawn" },
    };
  }),
});
