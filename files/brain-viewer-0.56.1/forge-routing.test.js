const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const R = require("./forge-routing.js");

const clear = (route, obstacles) => assert.equal(R.isClear(route.points, obstacles, 12), true);
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} was not ${expected}`);

test("keeps a clear connection straight", () => {
  const got = R.route([0, 0], [200, 0], [{ id: "away", kind: "rect", x: 70, y: 80, w: 30, h: 30 }], { clearance: 12 });
  assert.deepEqual(got.points, [[0, 0], [200, 0]]);
  assert.equal(got.blocked, false);
});

test("legacy force flag cannot turn a clear chord into a detour", () => {
  const got = R.route([0, 0], [200, 0], [{ id: "away", kind: "rect", x: 70, y: 80, w: 30, h: 30 }], { clearance: 12, force: true });
  assert.deepEqual(got.points, [[0, 0], [200, 0]]);
  assert.equal(got.clear, true);
});

test("adaptive curve validation catches a narrow collision away from the midpoint", () => {
  const curve = { kind: "quad", a: [0, 0], c: [100, 300], b: [100, 0] };
  const obstacle = [{ id: "narrow", kind: "rect", x: 22, y: 62, w: 4, h: 8 }];
  assert.equal(R.isCurveClear([curve], obstacle, 0), false);
  const samples = R.curveSamples([curve], { maxStep: 3, tolerance: 0.25 });
  assert.ok(samples.some(p => p[0] > 22 && p[0] < 26 && p[1] > 62 && p[1] < 70), "the actual curve was sampled near the obstacle");
});

test("rounded waypoint paths keep their label sampler on the emitted curve", () => {
  const got = R.roundedPath([[0, 0], [40, -30], [90, 0]], [], { radius: 10, clearance: 0 });
  assert.equal(got.clear, true);
  assert.match(got.d, /Q/);
  assert.deepEqual(got.sample(0), [0, 0]);
  assert.deepEqual(got.sample(1), [90, 0]);
  assert.ok(got.sample(0.5)[1] < 0, "the label point follows the rounded path rather than a straight chord");
});

test("manual waypoint cables are smooth and pass exactly through the bend", () => {
  const got = R.quadraticWaypoint([0, 0], [100, 0], [50, -40], [], { clearance: 0, maxStep: 3, tolerance: 0.25 });
  assert.equal(got.clear, true);
  assert.match(got.d, /Q/);
  assert.deepEqual(got.sample(0), [0, 0]);
  assert.deepEqual(got.sample(0.5), [50, -40]);
  assert.deepEqual(got.sample(1), [100, 0]);
  assert.deepEqual(got.control, [50, -80]);
});

test("manual waypoint cables report an invalid bend instead of crossing an obstacle", () => {
  const obstacle = [{ id: "tile", kind: "rect", x: 45, y: -10, w: 10, h: 20 }];
  const got = R.quadraticWaypoint([0, 0], [100, 0], [50, 0], obstacle, { clearance: 0, maxStep: 3, tolerance: 0.25 });
  assert.equal(got.clear, false);
  assert.equal(R.isCurveClear(got.segments, obstacle, 0, { maxStep: 3, tolerance: 0.25 }), false);
});

test("cubic socket paths flatten and sample with exact endpoint tangents", () => {
  const source = { kind: "rect", x: 0, y: 0, w: 20, h: 40 };
  const target = { kind: "rect", x: 80, y: 0, w: 20, h: 40 };
  const start = [20, 20], end = [80, 20], sourceNormal = [1, 0], targetNormal = [-1, 0], handle = 16;
  const got = R.cubicPath(start, end, [start[0] + sourceNormal[0] * handle, start[1]], [end[0] + targetNormal[0] * handle, end[1]], [source, target], { clearance: 0, maxStep: 3, tolerance: 0.25 });
  assert.equal(got.clear, true);
  assert.match(got.d, /C/);
  assert.deepEqual(got.sample(0), start);
  assert.deepEqual(got.sample(1), end);
  assert.ok(got.segments[0].c1[0] > start[0], "source control is outside its rectangle");
  assert.ok(got.segments[0].c2[0] < end[0], "target control is outside its rectangle");
  assert.ok((got.segments[0].c1[0] - start[0]) * sourceNormal[0] > 0, "source tangent leaves outward");
  assert.ok((end[0] - got.segments[0].c2[0]) * targetNormal[0] < 0, "target tangent arrives inward");
  assert.equal(R.isCurveClear(got.segments, [source, target], 0, { maxStep: 3, tolerance: 0.25 }), true);
});

test("routes deterministically around multiple obstacles", () => {
  const obstacles = [
    { id: "one", kind: "rect", x: 70, y: -35, w: 45, h: 70 },
    { id: "two", kind: "circle", cx: 165, cy: 5, r: 36 },
    { id: "three", kind: "rect", x: 235, y: -45, w: 40, h: 90 }
  ];
  const a = R.route([0, 0], [340, 0], obstacles, { clearance: 12, bias: 28 });
  const b = R.route([0, 0], [340, 0], obstacles, { clearance: 12, bias: 28 });
  assert.deepEqual(a.points, b.points);
  assert.ok(a.points.length > 2);
  clear(a, obstacles);
});

test("keeps a long barrier relevant by its extent, not its distant centre", () => {
  const barrier = [{ id: "long", kind: "rect", x: 80, y: -10, w: 40, h: 1000 }];
  const got = R.route([0, 0], [200, 0], barrier, { clearance: 14 });
  assert.equal(got.blocked, false);
  assert.ok(got.points.length > 2);
  assert.ok(Math.min(...got.points.map(p => p[1])) < -20, "route takes the available top detour");
  assert.equal(R.isClear(got.points, barrier, 14), true);
});

test("routes can leave an endpoint container when it is omitted from obstacles", () => {
  const endpointContainer = { id: "source-cell", kind: "circle", cx: 35, cy: 0, r: 62 };
  const child = { id: "unrelated-child", kind: "rect", x: 90, y: -28, w: 44, h: 56 };
  const got = R.route([75, 0], [250, 0], [child], { clearance: 12 });
  assert.ok(got.points.length > 2);
  clear(got, [child]);
  assert.equal(R.isClear(got.points, [endpointContainer, child], 12), false);
});

test("a sampled obstructed arc is detected and rerouted", () => {
  const obstacle = [{ id: "tile", kind: "rect", x: 82, y: -72, w: 36, h: 36 }];
  const arcSamples = [[0, 0], [40, -44], [100, -68], [160, -44], [200, 0]];
  assert.equal(R.isClear(arcSamples, obstacle, 10), false);
  const got = R.route([0, 0], [200, 0], obstacle, { clearance: 10, bias: -25 });
  clear(got, obstacle);
});

test("real annular sectors do not turn their empty middle into an obstacle", () => {
  const sector = [{ id: "upper-band", kind: "sector", cx: 0, cy: 0, rIn: 55, rOut: 100, a0: -2.5, a1: -0.65 }];
  assert.equal(R.isClear([[-150, 0], [150, 0]], sector, 12), true);
  const crossing = R.route([-150, -90], [150, -90], sector, { clearance: 12 });
  assert.equal(crossing.blocked, false);
  clear(crossing, sector);
});

test("sector radial walls use inner-rim clearance", () => {
  const sector = [{ id: "band", kind: "sector", cx: 0, cy: 0, rIn: 60, rOut: 100, a0: 0, a1: Math.PI / 2 }];
  const a = -0.20, radial = [60 * Math.cos(a), 60 * Math.sin(a)], tangent = [-Math.sin(a), Math.cos(a)];
  const short = [[radial[0] - tangent[0] * 3, radial[1] - tangent[1] * 3], [radial[0] + tangent[0] * 3, radial[1] + tangent[1] * 3]];
  assert.equal(R.isClear(short, sector, 14), false, "a 12px radial-wall gap is not 14px clearance");
});

test("a parent rim terminal moves to a clear sibling-band gap", () => {
  const siblingBand = [{ id: "sibling", kind: "sector", cx: 0, cy: 0, rIn: 70, rOut: 100, a0: -0.5, a1: 0.5 }];
  const prepared = R.prepare(siblingBand, 14);
  const terminal = R.clearCircleTerminal({ kind: "cell", cx: 0, cy: 0, R: 100 }, [300, 0], prepared);
  assert.ok(terminal, "a band gap should provide a parent rim exit");
  const angle = Math.atan2(terminal[1], terminal[0]);
  assert.ok(Math.abs(angle) > 0.5 + 14 / 70, "terminal was still within the padded sibling sector");
  const radialExit = [terminal[0] * 1.3, terminal[1] * 1.3];
  assert.equal(R.clearSegment(terminal, radialExit, prepared, 0), true);
  const got = R.route(terminal, [300, 0], prepared, { clearance: 0, force: true });
  assert.equal(got.blocked, false);
  assert.equal(R.isClear(got.points, prepared, 0), true);
});

test("a rendered package rectangle forces a detour", () => {
  const packageChip = [{ id: "pkg:cell-a:other", kind: "rect", x: 85, y: -16, w: 50, h: 32 }];
  const got = R.route([0, 0], [220, 0], packageChip, { clearance: 12, force: true });
  assert.equal(got.blocked, false);
  assert.ok(got.points.length > 2);
  assert.equal(R.isClear(got.points, packageChip, 12), true);
});

test("a mouth top port slides along its rim away from an unrelated package", () => {
  const mouth = { kind: "seg", cx: 0, cy: 0, rIn: 96, rOut: 120, a0: -0.5, a1: 0.5, mid: 0 };
  const chip = [{ id: "pkg:other", kind: "rect", x: 121, y: -22, w: 80, h: 44 }];
  const prepared = R.prepare(chip, 14);
  const fixed = [120, 0];
  assert.equal(R.clearSegment([-80, 0], fixed, prepared, 0), false, "the fixed top-rim port is package-crowded");
  const terminal = R.clearSectorTerminal(mouth, "top", prepared, -1);
  assert.ok(terminal, "a mouth rim with spare angular extent should have a safe terminal");
  assert.ok(Math.abs(Math.atan2(terminal[1], terminal[0])) > 0.2, "terminal did not leave the package's padded angular footprint");
  assert.equal(R.clearSegment([-80, 0], terminal, prepared, 0), true);
  assert.equal(R.clearSegment(terminal, [terminal[0] * .8, terminal[1] * .8], prepared, 0), true);
});

test("band port normals follow Forge's radial and angular port boundaries", () => {
  const g = { kind: "seg", cx: 0, cy: 0, a0: 0, a1: Math.PI / 2 };
  const diagonal = Math.SQRT1_2;
  const top = R.portNormal(g, [100 * diagonal, 100 * diagonal], "top");
  const bottom = R.portNormal(g, [60 * diagonal, 60 * diagonal], "bottom");
  const left = R.portNormal(g, [60, 0], "left");
  const right = R.portNormal(g, [0, 60], "right");
  close(top[0], diagonal); close(top[1], diagonal);
  close(bottom[0], -diagonal); close(bottom[1], -diagonal);
  close(left[0], 0); close(left[1], -1);
  close(right[0], -1); close(right[1], 0);
});

test("the actual Forge band port helper and routing normals agree", () => {
  const forge = fs.readFileSync(__dirname + "/forge.html", "utf8");
  const center = forge.match(/function centerOf\(g\) \{[\s\S]*?\n\}/)?.[0];
  const port = forge.match(/function portPoint\(g, side\) \{[\s\S]*?\n\}/)?.[0];
  assert.ok(center && port, "could not isolate Forge's geometry helpers");
  const g = { kind: "seg", cx: 0, cy: 0, rIn: 60, rOut: 100, a0: 0, a1: Math.PI / 2, mid: Math.PI / 4 };
  const actual = vm.runInNewContext(`${center}\n${port}\n["top", "bottom", "left", "right"].map(side => portPoint(${JSON.stringify(g)}, side))`, { DEG: Math.PI / 180 });
  close(Math.hypot(...actual[0]), 100); // Forge top = outer rim
  close(Math.hypot(...actual[1]), 60);  // Forge bottom = inner rim
  close(actual[2][0], 80); close(actual[2][1], 0);
  close(actual[3][0], 0); close(actual[3][1], 80);
  for (const [side, point] of [["top", actual[0]], ["bottom", actual[1]], ["left", actual[2]], ["right", actual[3]]]) {
    const n = R.portNormal(g, point, side);
    if (side === "left") { close(n[0], 0); close(n[1], -1); }
    else if (side === "right") { close(n[0], -1); close(n[1], 0); }
    else if (side === "top") { close(n[0], Math.SQRT1_2); close(n[1], Math.SQRT1_2); }
    else { close(n[0], -Math.SQRT1_2); close(n[1], -Math.SQRT1_2); }
  }
  assert.match(forge, /savedBandPorts[\s\S]*?!savedBandPorts/, "saved band ports must take the explicit-port route");
});

test("Forge uses socket-tangent curves and rounded recovery without fixed endpoint guards", () => {
  const forge = fs.readFileSync(__dirname + "/forge.html", "utf8");
  assert.doesNotMatch(forge, /force:\s*!baseClear/, "curve recovery must not force a second detour");
  assert.doesNotMatch(forge, /fromGuard|toGuard|leavesInside|entersInside/, "endpoint guard loops must not be synthesized");
  assert.match(forge, /ForgeRouting\.roundedPath/, "obstacle recovery must emit small smooth bends");
  assert.match(forge, /laneOffset/, "parallel lanes should use local offsets");
  assert.match(forge, /ForgeRouting\.cubicPath\(pStart, pEnd, controls\.c1, controls\.c2/, "automatic routes should validate a socket-tangent cubic before fallback routing");
  assert.match(forge, /const own = \[\], seen = new Set/, "endpoint tile interiors must be collision obstacles");
});

test("Forge retains unrelated package chips while exempting only a shipping edge's own chip", () => {
  const forge = fs.readFileSync(__dirname + "/forge.html", "utf8");
  const ancestor = forge.match(/function ancestorIds\(n, into\) \{[\s\S]*?\n\}/)?.[0];
  const edge = forge.match(/function edgeObstacles\(p, model\) \{[\s\S]*?\n\}/)?.[0];
  assert.ok(ancestor && edge, "could not isolate Forge package obstacle filtering");
  const kept = vm.runInNewContext(`${ancestor}\n${edge}\n(() => {
    const parent = { id: "cell-a", parent: null }, source = { id: "out", parent };
    const p = { a: source, b: { id: "target", parent: null }, oa: parent, ob: { id: "target-parent", parent: null }, e: { carried: { id: "own" } } };
    const model = new Map([
      ["pkg:cell-a:own", { id: "pkg:cell-a:own", packageId: "own", cellId: "cell-a" }],
      ["pkg:cell-a:other", { id: "pkg:cell-a:other", packageId: "other", cellId: "cell-a" }],
      ["pkg:cell-b:own", { id: "pkg:cell-b:own", packageId: "own", cellId: "cell-b" }]
    ]);
    return edgeObstacles(p, model).map(x => x.id).sort();
  })()`, {
    pkgOnLine: e => e.carried,
    parentCell: n => n.parent || null
  });
  assert.deepEqual([...kept], ["pkg:cell-a:other", "pkg:cell-b:own"]);
  assert.match(forge, /querySelectorAll\("\.pkg:not\(\.hide\)"\)/, "package obstacles must come from rendered chip geometry");
});

test("overlapping endpoint and obstacle reports a visible blocked fallback", () => {
  const got = R.route([0, 0], [100, 0], [{ id: "overlap", kind: "circle", cx: 0, cy: 0, r: 25 }], { clearance: 12 });
  assert.equal(got.blocked, true);
  assert.equal(got.clear, false);
  assert.deepEqual(got.points, [[0, 0], [100, 0]]);
});

test("parallel lanes remain distinct when a wall forces both below", () => {
  const obstacles = [
    { id: "middle", kind: "rect", x: 85, y: -38, w: 50, h: 76 },
    { id: "top-wall", kind: "rect", x: -20, y: -260, w: 260, h: 225 }
  ];
  const first = R.route([0, 0], [220, 0], obstacles, { clearance: 14, bias: 45, lane: 0 });
  const second = R.route([0, 0], [220, 0], obstacles, { clearance: 22, bias: 45, lane: 1 });
  clear(first, obstacles); clear(second, obstacles);
  assert.ok(Math.min(...first.points.map(p => p[1])) >= -35);
  assert.ok(Math.min(...second.points.map(p => p[1])) >= -35);
  assert.notDeepEqual(first.points, second.points);
  assert.ok(Math.max(...second.points.map(p => p[1])) > Math.max(...first.points.map(p => p[1])));
});

test("tight parallel spacing falls back to usable base clearance", () => {
  const walls = [
    { id: "ceiling", kind: "rect", x: -30, y: -40, w: 280, h: 22 },
    { id: "floor", kind: "rect", x: -30, y: 18, w: 280, h: 22 }
  ];
  const base = R.route([0, 0], [220, 0], walls, { clearance: 14 });
  const strictLane = R.route([0, 0], [220, 0], walls, { clearance: 22 });
  const fallback = R.route([0, 0], [220, 0], walls, { clearance: 14, laneBend: 6, bias: 1 });
  assert.equal(base.blocked, false);
  assert.equal(strictLane.blocked, true, "the cosmetic lane envelope cannot fit");
  assert.equal(fallback.blocked, false, "base clearance remains usable");
  assert.equal(R.isClear(fallback.points, walls, 14), true);
});

test("parallel bias chooses distinguishable sides when both are available", () => {
  const obstacles = [{ id: "middle", kind: "rect", x: 85, y: -38, w: 50, h: 76 }];
  const up = R.route([0, 0], [220, 0], obstacles, { clearance: 12, bias: -45 });
  const down = R.route([0, 0], [220, 0], obstacles, { clearance: 12, bias: 45 });
  clear(up, obstacles); clear(down, obstacles);
  assert.notDeepEqual(up.points, down.points);
  assert.ok(Math.min(...up.points.map(p => p[1])) < 0);
  assert.ok(Math.max(...down.points.map(p => p[1])) > 0);
});

test("dense obstacle sets stay bounded and route multiple edges", () => {
  const obstacles = Array.from({ length: 200 }, (_, i) => ({
    id: "dense-" + i, kind: "rect", x: 35 + (i % 25) * 42, y: -100 + Math.floor(i / 25) * 28, w: 20, h: 16
  }));
  const started = performance.now();
  for (let i = 0; i < 8; i++) R.route([0, i * 3], [1120, i * 3], obstacles, { clearance: 12, bias: i % 2 ? 20 : -20, lane: i });
  assert.ok(performance.now() - started < 2500, "bounded dense routing exceeded 2.5 seconds");
});