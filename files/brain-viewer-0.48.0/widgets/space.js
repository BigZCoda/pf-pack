// Space: nothing, on purpose. A gap the width and height you give it, so the board can be arranged with room in it
// rather than packed edge to edge. It draws no card, no head, no rule and no text; in edit mode the dashed outline
// every instrument wears is all there is of it, which is how it is found again to be moved, resized or taken off.
(function () {
BV.widgets.register({
  id: "space", contract: 1, title: "Space", size: "4", defaultOn: false, head: false,
  source: "nothing: a gap on the board, the size you give it",
  refresh() {},                     // there is nothing to read and nothing to redraw

  mount(el) {
    if (!document.getElementById("bv-space-css")) {
      const s = document.createElement("style");
      s.id = "bv-space-css";
      s.textContent = `
        section.w[data-w="space"] .wbody { min-height: 92px; }
        body:not(.editing) section.w[data-w="space"] .whead { display: none; }
      `;
      document.head.appendChild(s);
    }
    el.innerHTML = "";
  },
});
})();
