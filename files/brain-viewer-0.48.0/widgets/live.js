// A door, nothing more: the live map view, one press away.
BV.widgets.register({
  id: "live", contract: 1, title: "Live map", size: "4", defaultOn: false,
  source: "a link to the live map view, which reads a drawing against what is actually happening",
  mount: (el, api) => api.set({ count: "", lines: [{ text: "open the live map", href: "/live" }], max: 1 }),
});
