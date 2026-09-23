// The live maps, by purpose. Picking one opens it in its live view.
BV.widgets.register({
  id: "maps", contract: 1, title: "Maps", size: "4", defaultOn: false,
  source: "the live maps grouped by purpose (GET /api/maps)",
  mount: (el, api) => api.auto("/api/maps", j => ({
    count: api.plural((j.groups || []).length, "group"),
    lines: (j.groups || []).slice(0, 3).map(g => ({ text: g.name || g.id, href: "/maps", title: g.purpose || "",
                                                    tail: api.plural((g.maps || []).length, "map") })),
    max: 3, link: { href: "/maps", text: "the picker" },
  })),
});
