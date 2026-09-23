const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

const forge = fs.readFileSync(__dirname + "/forge.html", "utf8");

function functions(...names) {
  return names.map(name => forge.match(new RegExp(`function ${name}\\([\\s\\S]*?\\n\\}`))?.[0]).join("\n");
}

test("Forge renders persistent terminals and middle tangent arrows", () => {
  assert.match(forge, /<div id="terminals" aria-hidden="true"><\/div>/);
  assert.match(forge, /#terminals[^}]*z-index:4/);
  assert.match(forge, /edge-terminal/);
  assert.match(forge, /function edgeArrowPath\(row, spec\)/);
  assert.match(forge, /syncEdgeTerminal\(row, "from", row\.pt\(0\)\)/);
  assert.match(forge, /syncEdgeTerminal\(row, "to", row\.pt\(1\)\)/);
  assert.doesNotMatch(forge, /marker-(?:start|end)/);
});

test("Forge arrow end values keep JSON Canvas direction semantics", () => {
  const source = functions("edgeEndHasArrow", "edgeArrowEnds", "edgeArrowTs");
  const context = vm.runInNewContext(`${source}\n({ edgeEndHasArrow, edgeArrowEnds, edgeArrowTs })`);
  assert.equal(context.edgeEndHasArrow(undefined, true), true);
  assert.equal(context.edgeEndHasArrow("none", true), false);
  assert.equal(JSON.stringify(context.edgeArrowEnds({})), JSON.stringify({ to: true, from: false }));
  assert.equal(JSON.stringify(context.edgeArrowEnds({ toEnd: "none", fromEnd: "arrow" })), JSON.stringify({ to: false, from: true }));
  assert.equal(JSON.stringify(context.edgeArrowTs({ e: { toEnd: "none", fromEnd: "none" }, t0: 0.5 })), "[]");
  const both = context.edgeArrowTs({ e: { toEnd: "arrow", fromEnd: "arrow" }, t0: 0.5 });
  assert.equal(both.length, 2);
  assert.ok(Math.abs(both[0].t - 0.41) < 1e-9 && both[0].forward === false);
  assert.ok(Math.abs(both[1].t - 0.59) < 1e-9 && both[1].forward === true);
});

test("Forge stores one draggable bend in sibling metadata and exposes reset controls", () => {
  assert.match(forge, /META\.edges\[e\.id\].*waypoints/);
  assert.match(forge, /function routeThroughWaypoint\(start, end, waypoint/);
  assert.match(forge, /ForgeRouting\.quadraticWaypoint\(start, end, waypoint/);
  assert.match(forge, /if \(smooth\.clear\) return \{ points: smooth\.points/);
  assert.match(forge, /ForgeRouting\.cubicPath\(pStart, pEnd, controls\.c1, controls\.c2/);
  assert.match(forge, /endpoint:\$\{n\.id\}/);
  assert.match(forge, /blocked: first\.blocked \|\| second\.blocked \|\| !clear/);
  assert.match(forge, /function drawEdgeHandles\(rows\)/);
  assert.match(forge, /startBendDrag\(edgeId, e\)/);
  assert.match(forge, /sideSelect\("iFromSide"/);
  assert.match(forge, /sideSelect\("iToSide"/);
  assert.match(forge, /id="iAutoRoute"/);
  assert.match(forge, /delete e\.fromSide; delete e\.toSide; setEdgeWaypoint\(e, null\)/);
  assert.match(forge, /META\.edges && Object\.keys\(META\.edges\)\.length/);
});