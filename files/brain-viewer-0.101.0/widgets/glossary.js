// A door to the glossary: every word this app uses, with a definition and an example.
BV.widgets.register({
  id: "glossary", contract: 1, title: "Glossary", size: "4", defaultOn: false,
  source: "a link to the glossary, where every word this app uses is defined",
  mount: (el, api) => api.auto("/api/glossary", j => ({
    count: api.plural((j.terms || []).length, "word"),
    lines: [{ text: "open the glossary", href: "/glossary" }], max: 1,
  })),
});
