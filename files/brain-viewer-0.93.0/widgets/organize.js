// Still to organize: what is sitting in a project's Inbox, which is to say open and not yet sorted into a milestone.
BV.widgets.register({
  id: "organize", contract: 1, title: "Still to organize", size: "4", defaultOn: false,
  source: "the open items sitting unsorted in a project's Inbox (GET /api/projects)",
  mount: (el, api) => api.auto("/api/projects", j => {
    const groups = [];
    for (const p of j.projects || []) {
      if (!p.exists) continue;
      let n = 0;
      for (const g of p.groups || []) {
        if (String(g.name || "").trim().toLowerCase() !== "inbox") continue;
        for (const i of g.items || []) if (i.mark === "?" || i.mark === " " || i.mark === "-") n++;
      }
      if (n) groups.push({ id: p.id, name: p.name || p.id, n: n });
    }
    groups.sort((a, b) => b.n - a.n);
    return { count: api.plural(groups.reduce((a, g) => a + g.n, 0), "item"),
             lines: groups.slice(0, 3).map(g => ({ text: g.name, href: "/projects?id=" + encodeURIComponent(g.id), tail: String(g.n) })),
             max: 3, note: groups.length ? "" : "everything is sorted",
             link: { href: "/projects", text: "sort them" } };
  }),
});
