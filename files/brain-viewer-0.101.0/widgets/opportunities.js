// Opportunities (0.74.0, the extended circle's third round): two numerals, how many opportunities are in conversation
// and how many are live, each with its split by kind under it, the whole tile opening the opportunities page.
// Reads GET /api/circle?view=opportunities (the page's own read: the counts are computed there) and writes nothing.
// A brain with no circle files, or a team copy, draws no tile at all: absent, not broken.
(function () {
const STAGES = [["in-conversation", "in conversation"], ["live", "live"]];
const KIND = { client: ["client", "clients"], mentor: ["mentor", "mentors"], seat: ["seat", "seats"],
               partnership: ["partnership", "partnerships"], event: ["event", "events"] };
const kindWord = (k, n) => (KIND[k] || [k, k])[n === 1 ? 0 : 1];

BV.widgets.register({
  id: "opportunities", contract: 1, title: "Opportunities", size: "4", defaultOn: true,
  source: "the opportunities in conversation and live, with their kinds, from the circle's opportunities file (GET /api/circle?view=opportunities); writes nothing; no tile when the brain has no circle files",

  mount(el, api) {
    if (!document.getElementById("bv-opps-css")) {
      const s = document.createElement("style");
      s.id = "bv-opps-css";
      s.textContent = `
        .opw { display: flex; gap: 26px; flex-wrap: wrap; text-decoration: none; color: inherit; }
        .opw:hover .n { color: var(--accent-deep); }
        .opw .one { flex: 1; min-width: 110px; }
        .opw .n { font-family: var(--font-title); font-weight: 500; color: var(--accent); font-size: 52px; line-height: .9; }
        .opw .n.zero { color: var(--muted); }
        .opw .lb { font-family: var(--font-ui); font-size: 10px; letter-spacing: .14em; text-transform: uppercase;
                   color: var(--muted); margin-top: 5px; display: block; }
        .opw .kd { font-family: var(--font-mono); font-size: 10.5px; color: var(--muted); margin-top: 4px; display: block; }
      `;
      document.head.appendChild(s);
    }
    return this.refresh(el, api);
  },

  async refresh(el, api) {
    let j;
    try { j = await api.get("/api/circle?view=opportunities"); }
    catch (e) {
      if (e && (e.status === 403 || e.status === 404)) return api.show(false);
      return api.fail(e);
    }
    if (!j || !j.present) return api.show(false);
    api.show(true);
    const ops = j.opportunities || [];
    const cells = STAGES.map(([st, word]) => {
      const mine = ops.filter(o => o.stage === st);
      const by = {};
      mine.forEach(o => { by[o.kind] = (by[o.kind] || 0) + 1; });
      const split = Object.keys(by).sort((a, b) => by[b] - by[a]).map(k => `${by[k]} ${kindWord(k, by[k])}`).join(" · ");
      return `<div class="one"><div class="n${mine.length ? "" : " zero"}">${mine.length}</div>
        <span class="lb">${api.esc(word)}</span><span class="kd">${api.esc(split || "none")}</span></div>`;
    }).join("");
    api.count(ops.length + (ops.length === 1 ? " opportunity" : " opportunities"));
    api.html(`<a class="opw" href="/opportunities" title="every opportunity by stage, with who holds it">${cells}</a>`);
  },
});
})();
