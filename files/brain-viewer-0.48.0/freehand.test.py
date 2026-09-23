#!/usr/bin/env python3
"""freehand.test.py -- free mode on the home board (T-0213), checked without starting a server.

  python skills/brain-viewer/freehand.test.py

1. THE VALIDATOR. The layout carries a `mode`, grid or free. In free mode a row may carry its cell, x and y (column 0
   to 11, row index) and w and h (columns 1 to 12, rows 1 to 400), whole numbers with x + w at most 12; anything out of
   range is refused from the page. A row on the board with no cell is placed at the end, under the last tile. Grid
   mode ignores cells: a good one is kept for the next switch, a bad one is dropped with no error. Every layout that
   was valid before is still valid. The mode is written to the file only when it is free, a save that does not name
   it keeps the file's, and a reset takes the board back to grid.

2. THE PURE HALF OF THE PAGE. home.html keeps the placement rules between FREE-PURE-BEGIN and FREE-PURE-END, reading
   nothing from the page. This test lifts that block out of home.html as it is and runs it in node, so what is checked
   is the page's own code, not a Python copy of it: a grid layout switched to free derives x, y, w and h from the grid
   order with no overlap; the push moves a tile that is landed on down by rows so no two share a cell and leaves a tile
   nobody touched where it was; the snap rounds a drag to the cell edges and stays inside the twelve columns.
   Close gaps compacts a board with empty rows to none, keeps order and columns, and leaves a tight board unchanged;
   one empty row can be taken out. The layout's `gravity` (keep closed) is true or false, saved, kept when a save does
   not name it, and reset to off.

3. THE FINE ROW UNIT (2026-09-22). Rows are 20px (`rowUnit: 20`); a layout with no rowUnit is on the old 158px pitch
   and converts once (y' = round(y * 158 / 20), every tile made auto). A tile that fits its content stands
   ceil(content / 20) units; grown it pushes what it covers down, shrunk what sat on it comes up and nothing else moves.
   The empty space is selected as bands of consecutive empty rows and Delete takes a band out, pulling everything below
   up; Delete on a tile turns it off the board. The server accepts rowUnit (8 to 200), hFixed per row and a missing h
   in free mode, with y to 4000 and h to 400, and keeps a board's rowUnit across saves.

Exit 0 when all of them hold; 1 with the failure named otherwise.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import serve  # noqa: E402

FAILS = []


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(what)


def no_overlap(cells):
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            if a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]:
                return "%s and %s share a cell" % (a["id"], b["id"])
    return ""


def claim_validator(reg):
    ids = [w["id"] for w in reg]
    a, b, c = ids[0], ids[1], ids[2]
    cell = {"x": 4, "y": 2, "w": 8, "h": 3}
    rows, err = serve.home_validate([dict({"id": a, "on": True, "size": "8"}, **cell)], reg, mode="free")
    check(not err and all(rows[0].get(k) == v for k, v in cell.items()),
          "free mode keeps a row's x, y, w and h", err or json.dumps(rows[0]))
    for bad in [{"x": 12, "y": 0, "w": 1, "h": 1}, {"x": -1, "y": 0, "w": 4, "h": 1}, {"x": 6, "y": 0, "w": 7, "h": 1},
                {"x": 0, "y": 0, "w": 0, "h": 1}, {"x": 0, "y": 0, "w": 13, "h": 1}, {"x": 0, "y": -1, "w": 4, "h": 1},
                {"x": 0, "y": 0, "w": 4, "h": 0}, {"x": 0, "y": 0, "w": 4, "h": 401}, {"x": 0, "y": 4001, "w": 4, "h": 1},
                {"x": "0", "y": 0, "w": 4, "h": 1}, {"x": 1.5, "y": 0, "w": 4, "h": 1}, {"x": True, "y": 0, "w": 4, "h": 1},
                {"x": 0, "y": 0, "h": 4}, {"x": 0, "y": 0, "w": 4, "h": None}]:
        _r, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, **bad)], reg, mode="free")
        check(bool(err), "free mode refuses the cell %s" % json.dumps(bad), err or "accepted")
    # the fine unit: wider ranges, a missing h (the tile fits its content), hFixed, and rowUnit
    rows, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, x=0, y=3900, w=4, h=380, hFixed=True)],
                                    reg, mode="free", row_unit=20)
    check(not err and rows[0].get("y") == 3900 and rows[0].get("h") == 380 and rows[0].get("hFixed") is True,
          "the fine unit's ranges hold (y 3900, h 380) and hFixed: true is kept", err or json.dumps(rows[0]))
    rows, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, x=0, y=12, w=4, hFixed=False)],
                                    reg, mode="free", row_unit=20)
    check(not err and rows[0].get("y") == 12 and "h" not in rows[0] and "hFixed" not in rows[0],
          "free mode accepts a cell with no h, a tile that fits its content, and does not keep hFixed: false",
          err or json.dumps(rows[0]))
    _r, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, x=0, y=0, w=4, h=5, hFixed="yes")], reg, mode="free")
    check(bool(err), "free mode refuses an hFixed that is not true or false", err or "accepted")
    for bad_unit in (7, 201, "20", 20.0, True):
        _r, err = serve.home_validate([{"id": a, "on": True, "size": "4"}], reg, mode="free", row_unit=bad_unit)
        check(bool(err), "free mode refuses the rowUnit %r" % (bad_unit,), err or "accepted")
    rows, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, x=0, y=0, w=4, hFixed="yes")], reg,
                                    mode="grid", row_unit="x")
    check(not err, "grid mode ignores a bad rowUnit, a bad hFixed and a cell with no h", err or "")
    rows, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, x=0, y=0, w=4, h=10),
                                     {"id": b, "on": True, "size": "6", "rows": 2}], reg, mode="free", row_unit=20)
    by = {r["id"]: r for r in rows or []}
    check(not err and by[b].get("y") == 10 and by[b].get("h") == 15,
          "with rowUnit 20 a row with no cell is placed under the last at its grid height in fine units (2 rows = 15)",
          err or json.dumps(by.get(b)))
    rows, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, x=0, y=0, w=4, h=2),
                                     {"id": b, "on": True, "size": "6", "rows": 2},
                                     {"id": c, "on": False, "size": "4"}], reg, mode="free")
    by = {r["id"]: r for r in rows or []}
    check(not err and by[b].get("y") == 2 and by[b].get("x") == 0 and by[b].get("w") == 6 and by[b].get("h") == 2,
          "a row on the board with no cell is placed at the end, under the last tile", err or json.dumps(by.get(b)))
    check("x" not in by.get(c, {}), "a row off the board with no cell is not given one")
    rows, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, x=0, y=0, w=4, h=1)], reg, mode="grid")
    check(not err and rows[0].get("w") == 4, "grid mode keeps a good cell, so the next switch to free finds it", err or "")
    rows, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, x=40, y="a", w=0, h=1)], reg, mode="grid")
    check(not err and "x" not in rows[0], "grid mode ignores a bad cell: dropped, no error", err or "")
    rows, err = serve.home_validate([dict({"id": a, "on": True, "size": "4"}, x=40, y=0, w=4, h=1)], reg,
                                    drop_missing=True, mode="free")
    check(not err and rows[0].get("x") == 0 and rows[0].get("y") == 0,
          "reading a saved free file, a bad cell is treated as missing and placed again", err or json.dumps(rows[0]))
    _r, err = serve.home_validate([{"id": a, "on": True, "size": "4"}], reg, mode="free", gravity=1)
    check(bool(err), "home_validate refuses a gravity that is not true or false", err or "accepted")
    rows, err = serve.home_validate([{"id": a, "on": True, "size": "4"}, {"id": b, "on": True, "size": "12", "rows": 2}], reg)
    check(not err and all(k not in r for r in rows for k in ("x", "y", "w", "h")),
          "a layout with no cells and no mode reads exactly as before", err or "")
    # every board saved before this still validates, in both modes
    before = serve.home_default(reg)
    for m in ("grid", "free"):
        _r, err = serve.home_validate(before, reg, mode=m)
        check(not err, "the default board validates in %s mode" % m, err or "")

    keep = serve.BRAIN
    tmp = tempfile.mkdtemp(prefix="bv-free-test-")
    try:
        serve.BRAIN = tmp
        lay = serve.home_layout_api()
        check(lay.get("mode") == "grid", "with no layout file the mode is grid", str(lay.get("mode")))
        res = serve.home_layout_write({"widgets": [{"id": a, "on": True, "size": "4"}], "mode": "grid"})
        with open(os.path.join(tmp, serve.home_layout_rel().replace("/", os.sep)), encoding="utf-8") as f:
            doc = json.load(f)
        check(res.get("ok") and "mode" not in doc, "a grid board's file carries no mode key, so it reads as before")
        res = serve.home_layout_write({"widgets": [dict({"id": a, "on": True, "size": "4"}, x=2, y=1, w=5, h=2)], "mode": "free"})
        lay = serve.home_layout_api()
        row = [r for r in lay["widgets"] if r["id"] == a][0]
        check(res.get("ok") and lay.get("mode") == "free" and (row["x"], row["y"], row["w"], row["h"]) == (2, 1, 5, 2),
              "a free board saves its mode and cells and reads them back", str(res.get("error")))
        res = serve.home_layout_write({"widgets": [dict({"id": a, "on": True, "size": "4"}, x=2, y=1, w=5, h=2)]})
        check(res.get("mode") == "free", "a save that does not name the mode keeps the file's")
        res = serve.home_layout_write({"widgets": [{"id": a, "on": True, "size": "4"}], "mode": "tiles"})
        check(bool(res.get("error")), "a mode that is not grid or free is refused", res.get("error") or "accepted")
        res = serve.home_layout_write({"widgets": [dict({"id": a, "on": True, "size": "4"}, x=9, y=0, w=5, h=1)], "mode": "free"})
        check(bool(res.get("error")), "a free save with a cell off the twelve columns is refused", res.get("error") or "accepted")
        res = serve.home_layout_write({"widgets": [dict({"id": a, "on": True, "size": "4"}, x=0, y=0, w=4, h=1)], "mode": "free", "gravity": True})
        check(res.get("ok") and serve.home_layout_api().get("gravity") is True, "keep closed saves as gravity: true and reads back",
              str(res.get("error")))
        res = serve.home_layout_write({"widgets": [dict({"id": a, "on": True, "size": "4"}, x=0, y=0, w=4, h=1)]})
        check(res.get("gravity") is True, "a save that does not name gravity keeps the file's")
        res = serve.home_layout_write({"widgets": [{"id": a, "on": True, "size": "4"}], "gravity": "yes"})
        check(bool(res.get("error")), "a gravity that is not true or false is refused", res.get("error") or "accepted")
        lay = serve.home_layout_api()
        check(lay.get("rowUnit") is None, "a board saved with no rowUnit reads back with none, so the page converts it once")
        res = serve.home_layout_write({"widgets": [dict({"id": a, "on": True, "size": "4"}, x=0, y=40, w=4, h=9, hFixed=True)],
                                       "mode": "free", "rowUnit": 20})
        lay = serve.home_layout_api()
        row = [r for r in lay["widgets"] if r["id"] == a][0]
        check(res.get("ok") and lay.get("rowUnit") == 20 and row.get("hFixed") is True and row.get("y") == 40,
              "a free board saves rowUnit and hFixed and reads them back", str(res.get("error")))
        res = serve.home_layout_write({"widgets": [dict({"id": a, "on": True, "size": "4"}, x=0, y=40, w=4, h=9)]})
        check(res.get("rowUnit") == 20 and serve.home_layout_api().get("rowUnit") == 20,
              "a save that does not name rowUnit keeps the file's")
        res = serve.home_layout_write({"widgets": [dict({"id": a, "on": True, "size": "4"}, x=0, y=0, w=4, h=9)], "rowUnit": 3})
        check(bool(res.get("error")), "a free save with a rowUnit under 8 is refused", res.get("error") or "accepted")
        serve.home_layout_write({"reset": True})
        check(serve.home_layout_api().get("mode") == "grid", "a reset takes the board back to grid")
        check(serve.home_layout_api().get("gravity") is False, "and a reset turns keep closed off")
    finally:
        serve.BRAIN = keep
        shutil.rmtree(tmp, ignore_errors=True)


PURE_RE = re.compile(r"// FREE-PURE-BEGIN.*?\n(.*?)// FREE-PURE-END", re.S)

NODE_CASES = r"""
const out = {};
// a grid board as the default lays it out: full width, two thirds and a tall third, and so on
const board = [
  { id: "masthead", size: "12", rows: 1 }, { id: "mantra", size: "12", rows: 1 }, { id: "next", size: "8", rows: 1 },
  { id: "deck", size: "4", rows: 2 }, { id: "chat", size: "8", rows: 1 }, { id: "decide", size: "4", rows: 1 },
  { id: "people", size: "4", rows: 1 }, { id: "horizon", size: "4", rows: 1 }, { id: "moved", size: "6", rows: 1 },
  { id: "flow", size: "6", rows: 1, expanded: true }, { id: "system", size: "12", rows: 1 },
];
out.derived = freeCells(board);
// measured heights, with one tile that draws nothing right now (the mantra draws into the masthead)
out.measured = freeCells(board, r => r.id === "mantra" ? 0 : (r.id === "deck" ? 3 : (r.id === "people" ? 2 : 1)));
// the push: A dropped onto B's cell; B goes under A, and C (under B) goes under B; D, off to the side, stays
const cells = [
  { id: "A", x: 0, y: 0, w: 6, h: 2 }, { id: "B", x: 0, y: 0, w: 6, h: 1 }, { id: "C", x: 0, y: 1, w: 4, h: 1 },
  { id: "D", x: 8, y: 0, w: 4, h: 3 },
];
out.pushed = settle(cells, "A");
out.untouched = settle([{ id: "P", x: 0, y: 0, w: 4, h: 1 }, { id: "Q", x: 4, y: 0, w: 4, h: 1 }], "P");
out.settled = settle([{ id: "P", x: 0, y: 0, w: 6, h: 2 }, { id: "Q", x: 3, y: 1, w: 6, h: 1 }], null);
// a row with a cell and one without: kept, and the new one goes under the last
out.kept = freeCells([{ id: "k", size: "4", x: 3, y: 4, w: 5, h: 2 }, { id: "n", size: "6", rows: 2 }]);
// the snap
const s = { x: 2, y: 1, w: 4, h: 2 };
out.snap = {
  move: snapRect(s, "move", 1.4, 2.6), moveEdge: snapRect(s, "move", 30, -9), east: snapRect(s, "e", 1.6, 0),
  eastWall: snapRect(s, "e", 40, 0), west: snapRect(s, "w", -1.2, 0), westMin: snapRect(s, "w", 9, 0),
  north: snapRect(s, "n", 0, -0.7), se: snapRect(s, "se", 2.2, 3.4), southMin: snapRect(s, "s", 0, -5),
};
out.order = freeOrder([{ id: "b", x: 6, y: 0 }, { id: "c", x: 0, y: 2 }, { id: "a", x: 0, y: 0 }]).map(r => r.id);
out.hasCell = [hasCell({ x: 0, y: 0, w: 12, h: 1 }), hasCell({ x: 1, y: 0, w: 12, h: 1 }), hasCell({ x: 0, y: 0, w: 4 })];
// close gaps: a board with two empty rows (row 1 and row 4), and one with none
const gappy = [
  { id: "top", x: 0, y: 0, w: 12, h: 1 }, { id: "l", x: 0, y: 2, w: 8, h: 1 }, { id: "r", x: 8, y: 2, w: 4, h: 2 },
  { id: "low", x: 0, y: 5, w: 6, h: 2 }, { id: "side", x: 6, y: 6, w: 6, h: 1 },
];
out.gappyEmpty = emptyRows(gappy);
out.closed = closeGaps(gappy);
out.closedEmpty = emptyRows(out.closed);
const tight = [{ id: "a", x: 0, y: 0, w: 6, h: 2 }, { id: "b", x: 6, y: 0, w: 6, h: 1 }, { id: "c", x: 6, y: 1, w: 6, h: 1 },
               { id: "d", x: 0, y: 2, w: 12, h: 1 }];
out.tight = closeGaps(tight);
out.removed = removeRow(gappy, 1);
out.removeCovered = removeRow(gappy, 2);
// a pull on a height handle cannot go under its minimum (the page passes 2 units)
out.floorS = snapRect({ x: 0, y: 0, w: 12, h: 2 }, "s", 0, -3, 2);
out.floorN = snapRect({ x: 0, y: 0, w: 12, h: 2 }, "n", 0, 4, 2);
// a height the page wants (a filling widget's fillRows) replaces a row's h, and what it now covers settles down
out.wanted = freeCells([{ id: "chat", size: "8", x: 0, y: 0, w: 8, h: 7 }, { id: "nx", size: "8", x: 0, y: 7, w: 8, h: 7 }],
                       null, r => (r.id === "chat" ? 22 : 0));
// ---- the fine row unit ----
out.unit = ROW_UNIT;
// Zak's board as it was saved on the old pitch (no rowUnit): masthead two rows, next under it, chat four rows
const oldBoard = [
  { id: "masthead", on: true, size: "12", x: 0, y: 0, w: 11, h: 2 }, { id: "next", on: true, size: "8", x: 0, y: 2, w: 8, h: 1 },
  { id: "deck", on: true, size: "4", x: 8, y: 2, w: 4, h: 3, hFixed: true }, { id: "chat", on: true, size: "8", x: 0, y: 3, w: 8, h: 4 },
  { id: "space", on: false, size: "4" },
];
out.conv = convertLayout(oldBoard, null);
out.convSame = convertLayout(out.conv.rows, 20);
out.convOther = convertLayout([{ id: "a", x: 0, y: 10, w: 4, h: 10, hFixed: true }], 40);
out.oldUntouched = oldBoard[0].y === 0 && oldBoard[1].y === 2 && oldBoard[2].hFixed === true;
// the converted board once its tiles have measured (masthead 190px of content, next 140, chat stays at its guess),
// then the one compaction: it comes up tight
let cc = out.conv.rows.filter(r => r.on).map(r => ({ id: r.id, x: r.x, y: r.y, w: r.w, h: r.h }));
cc = refit(cc, "masthead", autoUnits(190));
cc = refit(cc, "next", autoUnits(140));
out.convFit = cc;
out.convTight = closeGaps(cc);
out.convTightEmpty = emptyRows(out.convTight);
// auto height rounding: ceil(content / 20), and half a pixel of noise does not add a unit
out.auto = [autoUnits(190), autoUnits(200), autoUnits(200.4), autoUnits(201), autoUnits(0), autoUnits(99999)];
// refit: A shrinks from 10 to 6; B and C sat on it and come up 4, D sat on B and comes up 4, E sat on nothing it rose
// from (a gap under C's column) and stays; then A grows to 12 and pushes
const stack = [
  { id: "A", x: 0, y: 0, w: 12, h: 10 }, { id: "B", x: 0, y: 10, w: 8, h: 5 }, { id: "C", x: 8, y: 10, w: 4, h: 5 },
  { id: "D", x: 0, y: 15, w: 8, h: 5 }, { id: "E", x: 8, y: 20, w: 4, h: 3 },
];
out.shrunk = refit(stack, "A", 6);
out.grown = refit(stack, "A", 12);
out.same = refit(stack, "A", 10);
// bands: a fine-unit board with a two-row and a three-row run of empty space
const fine = [
  { id: "top", x: 0, y: 0, w: 12, h: 3 }, { id: "l", x: 0, y: 5, w: 8, h: 4 }, { id: "r", x: 8, y: 5, w: 4, h: 2 },
  { id: "low", x: 0, y: 12, w: 12, h: 2 },
];
out.bands = bandsOf(fine);
out.bandAt4 = bandAt(fine, 4);
out.bandAt5 = bandAt(fine, 5);
out.bandRemoved = removeBand(fine, { y: 3, h: 2 });
out.bandCovered = removeBand(fine, { y: 4, h: 2 });
out.fineClosed = closeGaps(fine);
out.fineClosedEmpty = emptyRows(out.fineClosed);
// settle with the finer unit: a 15-unit tile dropped over two stacked 7-unit ones
out.fineSettle = settle([{ id: "P", x: 0, y: 0, w: 8, h: 15 }, { id: "Q", x: 0, y: 3, w: 8, h: 7 }, { id: "S", x: 0, y: 10, w: 8, h: 7 }], "P");
// a tile off the board by the key: its row switched off, nothing else touched, the input left as it was
const lay = [{ id: "a", on: true, x: 0, y: 0, w: 4, h: 7 }, { id: "b", on: true, x: 4, y: 0, w: 4, h: 9 }];
out.off = turnOff(lay, "b");
out.offInput = lay[1].on;
// ---- the height rule (the runaway fix) ----
out.hRule = {
  fillBeatsPx: tileHeight({ h: 60, fill: 22, px: 1180 }),        // chat: fillRows, never the measurement
  fixedBeatsFill: tileHeight({ h: 30, hFixed: true, fill: 22, px: 900 }),
  fixedOverCap: tileHeight({ h: 60, hFixed: true, fill: 22 }),     // not set by a handle this session: the fill wins
  fixedOverCapHandle: tileHeight({ h: 60, hFixed: true, fill: 22, byHandle: true }),
  fixedNoFill: tileHeight({ h: 55, hFixed: true, px: 300 }),       // over the cap, untrusted: the content wins
  pxCapped: tileHeight({ px: 5000 }), px: tileHeight({ px: 361 }), nothing: tileHeight({ h: 12 }),
  fillCapped: tileHeight({ fill: 90 }),
};
const saved = [
  { id: "chat", size: "8", rows: 1, x: 0, y: 22, w: 8, h: 60, hFixed: true },   // Zak's board, 2026-09-22
  { id: "people", size: "4", rows: 1, x: 10, y: 44, w: 2, h: 37, hFixed: true },
  { id: "flow", size: "6", rows: 1, x: 6, y: 82, w: 6, h: 90 },                  // a runaway saved with no hFixed
  { id: "deck", size: "4", rows: 2, x: 8, y: 11, w: 4, h: 23 },
  { id: "grid", size: "4", rows: 1 },
];
out.read = readHeights(saved);
out.readInput = saved[0].hFixed === true && saved[0].h === 60 && saved[2].h === 90;
// ---- the undo stack ----
let u = undoEmpty();
for (const s of ["s0", "s1", "s2"]) u = undoPush(u, s, "change " + s);
out.u3 = u.past.length;
const b1 = undoBack(u, "s3");                          // at s3, undo: back to s2, s3 on the redo side
const b2 = undoBack(b1.st, b1.state);                  // and again: back to s1
const f1 = undoForward(b2.st, b2.state);               // redo: forward to s2
out.undo = { b1: [b1.state, b1.said], b2: [b2.state, b2.said], f1: [f1.state, f1.said, f1.st.past.length, f1.st.future.length] };
const fresh = undoPush(f1.st, f1.state, "a new change");   // a new change clears the redo side
out.freshFuture = fresh.future.length;
out.emptyBack = undoBack(undoEmpty(), "x");
out.emptyFwd = undoForward(undoEmpty(), "x");
let big = undoEmpty();
for (let i = 0; i < 70; i++) big = undoPush(big, "s" + i, "c" + i, UNDO_CAP);
out.capped = [big.past.length, big.past[0].state, big.past[big.past.length - 1].state, UNDO_CAP];
out.pushInput = u.past.length === 3 && u.future.length === 0 && b1.st.future.length === 1;
// what the undo line says
const bA = { rows: [{ id: "next", on: true, x: 0, y: 10, w: 4, h: 11 }, { id: "deck", on: true, x: 8, y: 10, w: 4, h: 24 }], mode: "free", gravity: false, views: [] };
const moved = JSON.parse(JSON.stringify(bA)); moved.rows[0].x = 4;
const fitted = JSON.parse(JSON.stringify(bA)); fitted.rows[1].h = 26;
const off = JSON.parse(JSON.stringify(bA)); off.rows[1].on = false;
const mode = JSON.parse(JSON.stringify(bA)); mode.mode = "grid";
out.said = [describeChange(bA, moved, { next: "Next" }), describeChange(bA, fitted, {}), describeChange(bA, off, { deck: "Deck" }),
            describeChange(bA, mode, {})];
console.log(JSON.stringify(out));
"""


def claim_pure():
    with open(os.path.join(HERE, "home.html"), encoding="utf-8") as f:
        page = f.read()
    m = PURE_RE.search(page)
    check(bool(m), "home.html marks its free-mode rules between FREE-PURE-BEGIN and FREE-PURE-END")
    if not m:
        return
    node = shutil.which("node")
    check(bool(node), "node is on the path, to run the page's own code")
    if not node:
        return
    fd, path = tempfile.mkstemp(suffix=".js", prefix="bv-freehand-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(m.group(1) + NODE_CASES)
    try:
        p = subprocess.run([node, path], capture_output=True, text=True, timeout=60)
    finally:
        os.remove(path)
    check(p.returncode == 0, "the lifted block runs in node on its own, touching no page", (p.stderr or "").strip()[:300])
    if p.returncode != 0:
        return
    out = json.loads(p.stdout)

    d = {c["id"]: c for c in out["derived"]}
    check(len(d) == 11 and not no_overlap(out["derived"]), "a grid board switched to free gets a cell for every tile, none overlapping",
          no_overlap(out["derived"]))
    check(all(0 <= c["x"] and c["x"] + c["w"] <= 12 for c in out["derived"]), "every derived cell is inside the twelve columns")
    check((d["masthead"]["x"], d["masthead"]["y"], d["masthead"]["w"]) == (0, 0, 12), "the first full-width tile takes row 0",
          json.dumps(d["masthead"]))
    check((d["next"]["x"], d["next"]["y"], d["next"]["w"]) == (0, 14, 8) and (d["deck"]["x"], d["deck"]["y"], d["deck"]["h"]) == (8, 14, 15),
          "the grid order is kept: two thirds, then the tall third beside it", json.dumps([d["next"], d["deck"]]))
    check((d["chat"]["x"], d["chat"]["y"]) == (0, 21), "the next two-thirds tile flows under Next, beside the deck's second row",
          json.dumps(d["chat"]))
    check(d["flow"]["w"] == 12, "an expanded tile takes the full width", json.dumps(d["flow"]))
    mm = {c["id"]: c for c in out["measured"]}
    check(not no_overlap(out["measured"]) and mm["deck"]["h"] == 3 and mm["people"]["h"] == 2,
          "measured heights set h, still with no overlap", no_overlap(out["measured"]))
    check(mm["mantra"]["y"] == max(c["y"] + c["h"] for c in out["measured"] if c["id"] != "mantra"),
          "a tile that draws nothing right now goes after the rest, holding no hole", json.dumps(mm["mantra"]))

    p_ = {c["id"]: c for c in out["pushed"]}
    check(not no_overlap(out["pushed"]), "after the push no two tiles share a cell", no_overlap(out["pushed"]))
    check((p_["A"]["x"], p_["A"]["y"]) == (0, 0), "the tile put down stays where it was put", json.dumps(p_["A"]))
    check(p_["B"]["y"] == 2 and p_["B"]["x"] == 0, "the tile it landed on goes down by rows, to just under it", json.dumps(p_["B"]))
    check(p_["C"]["y"] == 3, "and a tile under that one is pushed on in turn", json.dumps(p_["C"]))
    check((p_["D"]["x"], p_["D"]["y"]) == (8, 0), "a tile nothing landed on does not move", json.dumps(p_["D"]))
    check([c["y"] for c in out["untouched"]] == [0, 0], "side by side tiles that do not overlap both stay")
    st = {c["id"]: c for c in out["settled"]}
    check(st["P"]["y"] == 0 and st["Q"]["y"] == 2, "with no tile named, an overlap is settled in reading order", json.dumps(out["settled"]))
    kk = {c["id"]: c for c in out["kept"]}
    check((kk["k"]["x"], kk["k"]["y"], kk["k"]["w"]) == (3, 4, 5) and (kk["n"]["x"], kk["n"]["y"], kk["n"]["w"], kk["n"]["h"]) == (0, 6, 6, 15),
          "a board that has cells keeps them, and a tile without one goes under the last", json.dumps(out["kept"]))

    sn = out["snap"]
    exp = {"move": (3, 4, 4, 2), "moveEdge": (8, 0, 4, 2), "east": (2, 1, 6, 2), "eastWall": (2, 1, 10, 2),
           "west": (1, 1, 5, 2), "westMin": (5, 1, 1, 2), "north": (2, 0, 4, 3), "se": (2, 1, 6, 5), "southMin": (2, 1, 4, 1)}
    bad = ["%s %s" % (k, json.dumps(sn[k])) for k, v in exp.items() if (sn[k]["x"], sn[k]["y"], sn[k]["w"], sn[k]["h"]) != v]
    check(not bad, "the snap rounds a move or a pull to the nearest cell edge and stays inside the columns", "; ".join(bad))
    check(out["order"] == ["a", "b", "c"], "one column reads top to bottom, then left to right", " ".join(out["order"]))
    check(out["hasCell"] == [True, False, False], "a cell must fit the twelve columns and carry all four numbers")

    check(out["gappyEmpty"] == [1, 4], "empty rows are the rows no tile covers, above the last tile", json.dumps(out["gappyEmpty"]))
    cl = {c["id"]: c for c in out["closed"]}
    check(out["closedEmpty"] == [] and not no_overlap(out["closed"]), "close gaps: a board with two empty rows compacts to none, no overlap",
          json.dumps(out["closed"]))
    check((cl["top"]["y"], cl["l"]["y"], cl["r"]["y"], cl["low"]["y"], cl["side"]["y"]) == (0, 1, 1, 2, 3)
          and all(cl[k]["x"] == g for k, g in (("top", 0), ("l", 0), ("r", 8), ("low", 0), ("side", 6))),
          "close gaps keeps the order and the columns: every tile only goes up", json.dumps(out["closed"]))
    check([(c["id"], c["x"], c["y"]) for c in out["tight"]] == [("a", 0, 0), ("b", 6, 0), ("c", 6, 1), ("d", 0, 2)],
          "a board with no gaps is unchanged by close gaps", json.dumps(out["tight"]))
    rm = {c["id"]: c["y"] for c in out["removed"]}
    check(rm == {"top": 0, "l": 1, "r": 1, "low": 4, "side": 5}, "removing one empty row pulls everything below it up by one",
          json.dumps(rm))
    check([c["y"] for c in out["removeCovered"]] == [0, 2, 2, 5, 6], "a row a tile covers is not removed",
          json.dumps(out["removeCovered"]))
    check((out["floorS"]["h"], out["floorN"]["y"], out["floorN"]["h"]) == (2, 0, 2),
          "a pull on a height handle by either edge stops at its minimum", json.dumps([out["floorS"], out["floorN"]]))
    wa = {c["id"]: c for c in out["wanted"]}
    check(wa["chat"]["h"] == 22 and wa["nx"]["y"] == 22 and not no_overlap(out["wanted"]),
          "a filling widget's fillRows replaces its h and the tile below is pushed down", json.dumps(out["wanted"]))

    print("\nthe fine row unit")
    check(out["unit"] == 20, "the free row unit is 20px", str(out["unit"]))
    cv = {r["id"]: r for r in out["conv"]["rows"]}
    check(out["conv"]["converted"] is True, "a layout with no rowUnit is converted")
    check((cv["masthead"]["y"], cv["next"]["y"], cv["deck"]["y"], cv["chat"]["y"]) == (0, 16, 16, 24),
          "the conversion: y' = round(y * 158 / 20)", json.dumps([cv[k].get("y") for k in ("masthead", "next", "deck", "chat")]))
    check((cv["masthead"]["h"], cv["next"]["h"], cv["deck"]["h"], cv["chat"]["h"]) == (15, 7, 23, 31),
          "and the first guess at h: round((h * 158 - 18) / 20)", json.dumps([cv[k].get("h") for k in ("masthead", "next", "deck", "chat")]))
    check(all("hFixed" not in r for r in out["conv"]["rows"]), "every tile comes out of the conversion fitting its content (hFixed dropped)")
    check("y" not in cv["space"] and cv["space"]["on"] is False, "a row with no cell is left as it is")
    check(out["oldUntouched"] is True, "the conversion does not change the rows it was handed")
    check(out["convSame"]["converted"] is False and out["convSame"]["rows"] == out["conv"]["rows"],
          "a layout already on the 20px unit is not converted again")
    co = out["convOther"]
    check(co["converted"] is False and (co["rows"][0]["y"], co["rows"][0]["h"], co["rows"][0].get("hFixed")) == (20, 20, True),
          "a layout on another fine unit is rescaled and keeps its fixed heights", json.dumps(co))
    ct = {c["id"]: c for c in out["convTight"]}
    check({c["id"]: c["h"] for c in out["convFit"]}["masthead"] == 10,
          "the masthead fits its content: 190px of it is 10 units (200px), not the old 298px", json.dumps(out["convFit"]))
    check((ct["masthead"]["y"], ct["next"]["y"], ct["deck"]["y"], ct["chat"]["y"]) == (0, 10, 10, 17)
          and out["convTightEmpty"] == [] and not no_overlap(out["convTight"]),
          "the converted board, measured and compacted once, comes up tight", json.dumps(out["convTight"]))
    check(out["auto"] == [10, 10, 10, 11, 1, 40], "auto height is ceil(content / 20), half a pixel of noise ignored, 1 to the 40-unit cap",
          json.dumps(out["auto"]))
    sh = {c["id"]: c for c in out["shrunk"]}
    check(sh["A"]["h"] == 6 and (sh["B"]["y"], sh["C"]["y"], sh["D"]["y"]) == (6, 6, 11) and not no_overlap(out["shrunk"]),
          "a tile that shrinks brings up what sat on it, and what sat on those", json.dumps(out["shrunk"]))
    check(sh["E"]["y"] == 20, "a tile that did not sit on anything that rose keeps its place", json.dumps(sh["E"]))
    gr = {c["id"]: c for c in out["grown"]}
    check(gr["A"]["h"] == 12 and (gr["B"]["y"], gr["C"]["y"], gr["D"]["y"], gr["E"]["y"]) == (12, 12, 17, 20)
          and not no_overlap(out["grown"]), "a tile that grows pushes what it covers down, and nothing else",
          json.dumps(out["grown"]))
    check(out["same"] == [dict(c) for c in out["same"]] and [c["y"] for c in out["same"]] == [0, 10, 10, 15, 20],
          "a tile whose height did not change moves nothing")
    check(out["bands"] == [{"y": 3, "h": 2}, {"y": 9, "h": 3}], "the empty space is the runs of empty rows, one band each",
          json.dumps(out["bands"]))
    check(out["bandAt4"] == {"y": 3, "h": 2} and out["bandAt5"] is None,
          "a click on an empty row selects its whole band; a row a tile covers selects nothing", json.dumps([out["bandAt4"], out["bandAt5"]]))
    br = {c["id"]: c["y"] for c in out["bandRemoved"]}
    check(br == {"top": 0, "l": 3, "r": 3, "low": 10}, "Delete on a band takes it out and pulls everything below up by its height",
          json.dumps(br))
    check([c["y"] for c in out["bandCovered"]] == [0, 5, 5, 12], "a band that is not fully empty is not taken out",
          json.dumps(out["bandCovered"]))
    fc = {c["id"]: c["y"] for c in out["fineClosed"]}
    check(fc == {"top": 0, "l": 3, "r": 3, "low": 7} and out["fineClosedEmpty"] == [],
          "keep closed (gravity) still compacts on the finer unit, order and columns kept", json.dumps(fc))
    fs = {c["id"]: c["y"] for c in out["fineSettle"]}
    check(fs == {"P": 0, "Q": 15, "S": 22} and not no_overlap(out["fineSettle"]),
          "settle still pushes in reading order on the finer unit", json.dumps(fs))
    check([r["on"] for r in out["off"]] == [True, False] and out["offInput"] is True
          and out["off"][1].get("x") == 4, "Delete on a tile turns only that tile off, keeping its cell, and changes nothing it was handed",
          json.dumps(out["off"]))

    print("\nthe height rule and the cap")
    hr = out["hRule"]
    check(hr["fillBeatsPx"] == 22, "a widget with fillRows stands its fillRows, never what was measured", json.dumps(hr))
    check(hr["fixedBeatsFill"] == 30, "a height a person fixed beats fillRows and the measurement", json.dumps(hr))
    check(hr["fixedOverCap"] == 22 and hr["fixedNoFill"] == 15,
          "a fixed height over the 40-unit cap not set by a handle this session gives way to fillRows or the content", json.dumps(hr))
    check(hr["fixedOverCapHandle"] == 60, "a fixed height over the cap set by a handle this session is kept", json.dumps(hr))
    check(hr["pxCapped"] == 40 and hr["px"] == 19 and hr["fillCapped"] == 40 and hr["nothing"] == 0,
          "measured content and fillRows stop at 40 units; with nothing to go on the rule keeps the tile's own h", json.dumps(hr))
    rd = {r["id"]: r for r in out["read"]}
    check(rd["chat"]["h"] == 7 and "hFixed" not in rd["chat"],
          "read: a saved fixed height over the cap (chat 60) comes back fitting, its hFixed dropped", json.dumps(rd["chat"]))
    check(rd["people"]["h"] == 37 and rd["people"].get("hFixed") is True, "read: a fixed height at or under the cap is kept",
          json.dumps(rd["people"]))
    check(rd["flow"]["h"] == 7 and "hFixed" not in rd["flow"], "read: a runaway height saved with no hFixed is treated as auto",
          json.dumps(rd["flow"]))
    check(rd["deck"]["h"] == 23 and "h" not in rd["grid"] and out["readInput"] is True,
          "read: a height under the cap and a row with no cell are left alone, and nothing handed in is changed", json.dumps(out["read"]))

    print("\nundo")
    un = out["undo"]
    check(out["u3"] == 3 and out["pushInput"] is True, "a change pushes the board from before it; the stacks handed in are not changed")
    check(un["b1"] == ["s2", "change s2"] and un["b2"] == ["s1", "change s1"], "undo walks back one change at a time, saying what it undid",
          json.dumps(un))
    check(un["f1"] == ["s2", "change s1", 2, 1], "redo walks forward again", json.dumps(un["f1"]))
    check(out["freshFuture"] == 0, "a new change clears the redo side")
    check(out["emptyBack"] is None and out["emptyFwd"] is None, "an empty side undoes and redoes nothing")
    check(out["capped"] == [50, "s20", "s69", 50], "the stack holds 50, the oldest dropped first", json.dumps(out["capped"]))
    check(out["said"] == ["Next moved", "", "Deck taken off", "the board switched to grid"],
          "the undo line names the change; a tile fitting its content is not one", json.dumps(out["said"]))


def main():
    reg = serve.widget_registry()
    print("\nthe validator, free mode")
    claim_validator(reg)
    print("\nthe page's own placement rules, run in node")
    claim_pure()
    print("-" * 72)
    if FAILS:
        print("%d failed: %s" % (len(FAILS), "; ".join(FAILS[:6])))
        return 1
    print("all hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
