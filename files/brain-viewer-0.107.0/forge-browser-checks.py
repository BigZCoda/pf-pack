#!/usr/bin/env python3
"""Focused browser regressions for the Forge's obstacle-aware edge renderer.

This is intentionally a browser check rather than a unit test for the routing
kernel.  The fixture is served by Playwright route handlers, so saving it can
never write a canvas or a log line to the real brain.  The existing Brain
Viewer workflow must already be running.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from playwright.async_api import (
    Browser,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)


TEST_PATH = "projects/pf-build/architecture/browser-checks/forge-obstacles.canvas"
DENSE_PATH = "projects/pf-build/architecture/womb-phase/onboarding-app-cells.canvas"
CHAT_MACHINE_PATH = "projects/pf-build/architecture/womb-phase/chat-machine-cells.canvas"
CHROMIUM = "/repl/tools/bin/chromium"


def fixture_canvas() -> dict[str, Any]:
    """A small drawing with free endpoint and obstacle rectangles.

    The three barriers deliberately span the two endpoint centres.  The two
    parallel edges make the side-bias and marker checks exercise the same
    route geometry rather than a separate synthetic JavaScript call.
    """

    def text_node(node_id: str, x: int, y: int, width: int, height: int, text: str) -> dict[str, Any]:
        return {
            "id": node_id,
            "type": "text",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "text": text,
        }

    nodes = [
        text_node("source", 0, 120, 110, 70, "**Step · Source**\nstart"),
        text_node("target", 1100, 120, 110, 70, "**Step · Target**\nfinish"),
        text_node("barrier-a", 230, 40, 120, 260, "first unrelated rectangle"),
        text_node("barrier-b", 510, 40, 120, 260, "second unrelated rectangle"),
        text_node("barrier-c", 790, 40, 120, 260, "third unrelated rectangle"),
        text_node("blocked-source", 255, 100, 60, 60, "**Step · Blocked source**\ninside a barrier"),
    ]
    edges = [
        {
            "id": "edge-primary",
            "fromNode": "source",
            "fromSide": "right",
            "toNode": "target",
            "toSide": "left",
            "label": "primary route",
        },
        {
            "id": "edge-parallel",
            "fromNode": "source",
            "fromSide": "right",
            "toNode": "target",
            "toSide": "left",
            "label": "parallel route",
        },
        {
            "id": "edge-blocked",
            "fromNode": "blocked-source",
            "fromSide": "right",
            "toNode": "target",
            "toSide": "left",
            "label": "blocked route",
        },
    ]
    return {"nodes": nodes, "edges": edges}


def fixture_info(canvas: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": TEST_PATH,
        "canvas": copy.deepcopy(canvas),
        "forge": {"_schema": "forge/1", "canvas": TEST_PATH, "nodes": {}},
        "forgePath": TEST_PATH.removesuffix(".canvas") + ".forge.json",
        "forgeExists": True,
        "editable": True,
        "propose": False,
        "family": "browser-checks",
        "trailingNewline": True,
        "crlf": False,
        "stages": {"concept": 0, "prototype": 0, "built": 0, "stable": 0},
        "inForge": True,
        "mtime": "browser-check-fixture",
    }


@dataclass
class CheckResult:
    name: str
    elapsed_ms: float
    ok: bool
    detail: str = ""


class BrowserFixture:
    """In-memory API transport for the fixture page."""

    def __init__(self) -> None:
        self.canvas = fixture_canvas()
        self.meta: dict[str, Any] = {
            "_schema": "forge/1",
            "canvas": TEST_PATH,
            "nodes": {},
        }
        self.puts: list[dict[str, Any]] = []

    def forge_answer(self) -> dict[str, Any]:
        answer = fixture_info(self.canvas)
        answer["forge"] = copy.deepcopy(self.meta)
        answer["canvas"] = copy.deepcopy(self.canvas)
        return answer

    async def forge(self, route) -> None:
        request = route.request
        query = parse_qs(urlparse(request.url).query)
        requested = query.get("path", [""])[0].lstrip("/")
        if requested == TEST_PATH:
            await route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(self.forge_answer()),
            )
            return
        await route.continue_()

    async def file(self, route) -> None:
        request = route.request
        parsed = urlparse(request.url)
        query = parse_qs(parsed.query)
        requested = query.get("path", [""])[0].lstrip("/")
        if request.method != "PUT":
            await route.continue_()
            return

        body = request.post_data or ""
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            await route.fulfill(
                status=400,
                content_type="application/json",
                body=json.dumps({"error": f"fixture received invalid JSON: {exc}"}),
            )
            return
        self.puts.append(
            {
                "path": requested,
                "note": query.get("note", [""])[0],
                "body": body,
                "json": decoded,
            }
        )
        if requested == TEST_PATH:
            self.canvas = decoded
        elif requested == TEST_PATH.removesuffix(".canvas") + ".forge.json":
            self.meta = decoded
        else:
            await route.fulfill(
                status=403,
                content_type="application/json",
                body=json.dumps({"error": "fixture refuses writes outside its canvas"}),
            )
            return
        await route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"saved": True, "log": "fixture save; no brain write"}),
        )


def require(value: Any, message: str) -> None:
    if not value:
        raise AssertionError(message)


async def wait_for_forge(page: Page, timeout: float = 15_000) -> None:
    await page.wait_for_selector("#stage", state="visible", timeout=timeout)
    await page.wait_for_function(
        "() => typeof DOC !== 'undefined' && DOC && typeof L !== 'undefined' && L.size > 0",
        timeout=timeout,
    )


async def eval_state(page: Page, expression: str, arg: Any = None) -> Any:
    """Evaluate in the page's script world, where Forge's globals are lexical."""

    if arg is None:
        return await page.evaluate(expression)
    return await page.evaluate(expression, arg)


async def edge_snapshot(page: Page, edge_id: str) -> dict[str, Any]:
    return await eval_state(
        page,
        """edgeId => {
          const row = edgeGeoms().find(x => x.e.id === edgeId);
          const hit = row && svg.querySelector(`path.hit[data-edge="${CSS.escape(edgeId)}"]`);
          const line = row && svg.querySelector(`path.line[data-edge="${CSS.escape(edgeId)}"]`);
          const label = svg.querySelector(`text.elabel[data-edge="${CSS.escape(edgeId)}"]`);
          const length = hit && hit.getTotalLength ? hit.getTotalLength() : 0;
          const pointAt = t => {
            if (!hit || !length) return null;
            const p = hit.getPointAtLength(length * t);
            return [p.x, p.y];
          };
          return {
            row: !!row,
            d: row && row.d,
            blocked: row && !!row.blocked,
            hitD: hit && hit.getAttribute("d"),
            lineD: line && line.getAttribute("d"),
            hasLabel: !!label,
            labelXY: label && [parseFloat(label.getAttribute("x")), parseFloat(label.getAttribute("y"))],
            labelT: label && parseFloat(label.dataset.t),
            length,
            mid: pointAt(0.5),
          };
        }""",
        edge_id,
    )


async def drag_free_node(
    page: Page,
    node_id: str,
    destination: tuple[float, float],
    *,
    pause_after_move_ms: int = 80,
) -> None:
    start = await eval_state(
        page,
        """id => {
          const g = L.get(id);
          if (!g) throw new Error("no drawn geometry for " + id);
          const p = g.kind === "free" ? [g.x + g.w / 2, g.y + g.h / 2] : centerOf(g);
          return toScreen(p[0], p[1]);
        }""",
        node_id,
    )
    finish = await eval_state(
        page,
        "p => toScreen(p[0], p[1])",
        list(destination),
    )
    await page.mouse.move(start[0], start[1])
    await page.mouse.down()
    await page.mouse.move(finish[0], finish[1], steps=10)
    await page.wait_for_timeout(pause_after_move_ms)


async def check_fixture_loaded(page: Page) -> str:
    state = await eval_state(
        page,
        """() => ({
          nodes: DOC.nodes.length,
          edges: DOC.edges.length,
          free: [...L.values()].filter(g => g.kind === "free").length,
          editable: !!INFO.editable,
          hasRouter: typeof ForgeRouting !== "undefined",
          hasEdgeGeoms: typeof edgeGeoms === "function",
        })""",
    )
    require(state["nodes"] == 6, f"fixture node count was {state['nodes']}")
    require(state["edges"] == 3, f"fixture edge count was {state['edges']}")
    require(state["free"] == 6, f"expected six free rectangles, got {state['free']}")
    require(state["editable"], "fixture did not open editable")
    require(state["hasRouter"], "ForgeRouting was not loaded")
    require(state["hasEdgeGeoms"], "edgeGeoms global is not available")
    return f"{state['nodes']} nodes, {state['edges']} edges, {state['free']} free rectangles"


async def check_multiple_obstacles(page: Page) -> str:
    result = await eval_state(
        page,
        """() => {
          const ids = ["barrier-a", "barrier-b", "barrier-c"];
          const rects = ids.map(id => {
            // Use the rendered boxes, not fixture coordinates.  This keeps
            // the check honest after fit/zoom and catches a route that misses
            // the actual free-node rectangle only by a CSS border's width.
            const el = world.querySelector(`[data-id="${CSS.escape(id)}"]`);
            const r = el && el.getBoundingClientRect();
            const [x, y] = toWorld(r.left, r.top), [x1, y1] = toWorld(r.right, r.bottom);
            return { id, kind: "rect", x, y, w: x1 - x, h: y1 - y };
          });
          const rows = edgeGeoms();
          const row = rows.find(x => x.e.id === "edge-primary");
          if (!row) throw new Error("primary edge geometry is missing");
          const hit = svg.querySelector('path.hit[data-edge="edge-primary"]');
          const d = hit && hit.getAttribute("d");
          // The native SVG path is the rendered truth.  In particular, a Q/C
          // route's row.points (when present) is only the router's input and
          // can silently miss the curve between its control points.
          const length = hit && hit.getTotalLength ? hit.getTotalLength() : 0;
          const count = length ? Math.max(1, Math.ceil(length / 1)) : 0;
          const points = length ? Array.from({ length: count + 1 }, (_, i) => {
            const p = hit.getPointAtLength(length * i / count);
            return [p.x, p.y];
          }) : [];
          const violations = [];
          for (let i = 1; i < points.length; i++) {
            for (const obstacle of rects) {
              if (!ForgeRouting.clearSegment(points[i - 1], points[i], [obstacle], 14)) {
                violations.push(obstacle.id + ":" + (i - 1));
              }
            }
          }
          const direct = ForgeRouting.isClear([points[0], points[points.length - 1]], rects, 14);
          return {
            obstacleCount: rects.length,
            direct,
            nativePath: !!hit && !!length,
            sampleStep: count ? length / count : 0,
            pathLength: length,
            routedClear: points.length > 1 && !violations.length,
            segmentCount: points.length - 1,
            points,
            blocked: !!row.blocked,
            violations,
          };
        }""",
    )
    require(result["nativePath"], "rendered route has no native SVG path geometry")
    require(result["sampleStep"] <= 1.01, f"route samples were too coarse ({result['sampleStep']:.2f} world units)")
    require(result["obstacleCount"] == 3, "fixture obstacles were not all visible")
    require(not result["direct"], "fixture direct endpoint path was unexpectedly clear")
    require(
        result["routedClear"],
        "rendered routed segment intersects a free rectangle "
        f"(violations={','.join(result['violations'][:6]) or 'unknown'})",
    )
    require(result["segmentCount"] > 1, f"route did not add turns: {result['segmentCount']} segments")
    require(not result["blocked"], "route returned a blocked fallback for clearable obstacles")
    return (
        f"three obstacles; native SVG path sampled at {result['sampleStep']:.2f} world units "
        f"({result['segmentCount']} clearance segments) clear"
    )


async def check_endpoint_side_attachment(page: Page) -> str:
    result = await eval_state(
        page,
        """() => {
          const row = edgeGeoms().find(x => x.e.id === "edge-primary");
          if (!row) throw new Error("primary edge geometry is missing");
          const edge = row.e;
          const box = id => {
            const el = world.querySelector(`[data-id="${CSS.escape(id)}"]`);
            const r = el && el.getBoundingClientRect();
            const [x, y] = toWorld(r.left, r.top), [x1, y1] = toWorld(r.right, r.bottom);
            return { x, y, w: x1 - x, h: y1 - y };
          };
           const a = box(edge.fromNode), b = box(edge.toNode);
           const hit = svg.querySelector('path.hit[data-edge="edge-primary"]');
           const length = hit && hit.getTotalLength ? hit.getTotalLength() : 0;
           const pointAt = t => {
             if (!hit || !length) return null;
             const p = hit.getPointAtLength(length * t);
             return [p.x, p.y];
           };
           const start = pointAt(0), end = pointAt(1), tolerance = 4;
          const attached = {
            fromSide: edge.fromSide,
            toSide: edge.toSide,
             from: !!start && Math.abs(start[0] - (a.x + a.w)) <= tolerance &&
              start[1] >= a.y - tolerance && start[1] <= a.y + a.h + tolerance,
             to: !!end && Math.abs(end[0] - b.x) <= tolerance &&
              end[1] >= b.y - tolerance && end[1] <= b.y + b.h + tolerance,
          };
           return { ...attached, start, end, nativePath: !!hit && !!length };
        }""",
    )
    require(result["fromSide"] == "right", f"saved source side changed to {result['fromSide']}")
    require(result["toSide"] == "left", f"saved target side changed to {result['toSide']}")
    require(result["nativePath"], "endpoint attachment could not inspect native SVG geometry")
    require(result["from"], f"route start is not attached to saved right side: {result['start']}")
    require(result["to"], f"route end is not attached to saved left side: {result['end']}")
    return "primary route remains attached to saved right/left endpoint sides"


async def check_blocked_hit_tooltip(page: Page) -> str:
    result = await eval_state(
        page,
        """() => {
          const row = edgeGeoms().find(x => x.e.id === "edge-blocked");
          const hit = svg.querySelector('path.hit[data-edge="edge-blocked"]');
          const line = row && svg.querySelector(`path.line[data-edge="${CSS.escape(row.e.id)}"]`);
          return {
            blocked: !!(row && row.blocked),
            hitTip: hit && (hit.querySelector("title") || {}).textContent || "",
            lineTip: line && (line.querySelector("title") || {}).textContent || "",
          };
        }""",
    )
    require(result["blocked"], "blocked fixture edge did not report blocked")
    require(
        "route blocked" in result["hitTip"].lower(),
        f"blocked hit tooltip lacks warning: {result['hitTip']!r}",
    )
    require(
        "route blocked" in result["lineTip"].lower(),
        f"blocked visible-line tooltip lacks warning: {result['lineTip']!r}",
    )
    return "blocked edge exposes route-blocked warning on hit and visible-line tooltips"


async def check_parallel_distinct(page: Page) -> str:
    result = await eval_state(
        page,
        """() => {
          const rows = edgeGeoms().filter(x => ["edge-primary", "edge-parallel"].includes(x.e.id));
           const mids = rows.map(row => {
             const hit = svg.querySelector(`path.hit[data-edge="${CSS.escape(row.e.id)}"]`);
             const length = hit && hit.getTotalLength ? hit.getTotalLength() : 0;
             if (!length) return null;
             const p = hit.getPointAtLength(length / 2);
             return [p.x, p.y];
           });
          return {
            count: rows.length,
            paths: rows.map(x => x.d),
            mids,
             midDistance: mids.length === 2 && mids.every(Boolean) ? Math.hypot(mids[0][0] - mids[1][0], mids[0][1] - mids[1][1]) : 0,
          };
        }""",
    )
    require(result["count"] == 2, f"expected two parallel edge geometries, got {result['count']}")
    require(result["paths"][0] != result["paths"][1], "parallel paths share one geometry")
    require(result["midDistance"] > 2, f"parallel midpoint separation was only {result['midDistance']:.2f}")
    return f"two distinct paths; midpoint separation {result['midDistance']:.1f} world px"


async def check_terminals_arrows_and_hits(page: Page) -> str:
    result = await eval_state(
        page,
        """() => {
          const rows = edgeGeoms();
          const distance = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
          const arrowInfo = (arrow, hit, length, target) => {
            const arrowLength = arrow && arrow.getTotalLength ? arrow.getTotalLength() : 0;
            if (!arrowLength || !hit || !length) return null;
            const points = Array.from({ length: 20 }, (_, i) => {
              const p = arrow.getPointAtLength(arrowLength * i / 19);
              return [p.x, p.y];
            });
            const centre = points.reduce(
              (sum, p) => [sum[0] + p[0] / points.length, sum[1] + p[1] / points.length],
              [0, 0],
            );
            let xx = 0, yy = 0, xy = 0;
            for (const p of points) {
              const dx = p[0] - centre[0], dy = p[1] - centre[1];
              xx += dx * dx; yy += dy * dy; xy += dx * dy;
            }
            const angle = Math.atan2(2 * xy, xx - yy) / 2;
            const axis = [Math.cos(angle), Math.sin(angle)];
            const wanted = target || (() => {
              const p = hit.getPointAtLength(length / 2);
              return [p.x, p.y];
            })();
            let nearestLength = 0, nearest = Infinity;
            for (let i = 0; i <= 100; i++) {
              const at = length * i / 100, p = hit.getPointAtLength(at);
              const d = distance([p.x, p.y], wanted);
              if (d < nearest) { nearest = d; nearestLength = at; }
            }
            const before = hit.getPointAtLength(Math.max(0, nearestLength - length * 0.03));
            const after = hit.getPointAtLength(Math.min(length, nearestLength + length * 0.03));
            const tangentLength = Math.hypot(after.x - before.x, after.y - before.y) || 1;
            const tangent = [(after.x - before.x) / tangentLength, (after.y - before.y) / tangentLength];
            return {
              centre,
              target: wanted,
              midpointDistance: distance(centre, wanted),
              nearestDistance: Math.min(...points.map(p => distance(p, wanted))),
              tangentAlignment: Math.abs(axis[0] * tangent[0] + axis[1] * tangent[1]),
            };
          };
          const checked = rows.map(row => {
            const id = row.e.id;
            const hit = svg.querySelector(`path.hit[data-edge="${CSS.escape(id)}"]`);
            const line = svg.querySelector(`path.line[data-edge="${CSS.escape(id)}"]`);
            const arrows = [...svg.querySelectorAll(`path.edge-arrow[data-edge="${CSS.escape(id)}"]`)];
            const terminals = [...terminalsEl.querySelectorAll(`.edge-terminal[data-edge="${CSS.escape(id)}"]`)];
            const length = hit && hit.getTotalLength ? hit.getTotalLength() : 0;
            const endpoint = end => {
              if (!hit || !length) return null;
              const p = hit.getPointAtLength(end ? length : 0);
              return [p.x, p.y];
            };
            const socket = end => {
              const el = terminals.find(x => x.dataset.end === end);
              if (!el) return null;
              const r = el.getBoundingClientRect();
              const p = toWorld(r.left + r.width / 2, r.top + r.height / 2);
              return {
                present: true,
                visible: r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden",
                point: p,
              };
            };
            const from = endpoint(false), to = endpoint(true);
            const fromSocket = socket("from"), toSocket = socket("to");
            const arrowTargets = edgeArrowTs(row).map(spec => row.pt(spec.t));
            const arrowGeometry = arrows.map((arrow, i) => arrowInfo(arrow, hit, length, arrowTargets[i]));
            const label = svg.querySelector(`text.elabel[data-edge="${CSS.escape(id)}"]`);
            const labelPoint = label ? [
              parseFloat(label.getAttribute("x")),
              parseFloat(label.getAttribute("y")),
            ] : null;
            const labelArrowGap = labelPoint && arrowGeometry.length
              ? Math.min(...arrowGeometry.map(arrow => distance(labelPoint, arrow.centre)))
              : Infinity;
            return {
              id,
              hit: !!hit,
              line: !!line && line.classList.contains("line"),
              sameD: !!line && !!hit && line.getAttribute("d") === hit.getAttribute("d"),
              markerEnd: line && line.getAttribute("marker-end"),
              markerStart: line && line.getAttribute("marker-start"),
              arrowCount: arrows.length,
              arrowTs: edgeArrowTs(row).map(spec => spec.t),
              arrowGeometry,
              terminals: terminals.map(el => el.dataset.end).sort(),
              fromSocket,
              toSocket,
              from,
              to,
              fromDistance: from && fromSocket ? distance(from, fromSocket.point) : Infinity,
              toDistance: to && toSocket ? distance(to, toSocket.point) : Infinity,
              labelArrowGap,
            };
          });
          return { count: checked.length, checked };
        }""",
    )
    require(result["count"] == 3, f"expected three rendered edges, got {result['count']}")
    for row in result["checked"]:
        require(row["hit"], f"missing hit path for {row['id']}")
        require(row["line"], f"missing visible line for {row['id']}")
        require(row["sameD"], f"hit path diverges from visible line for {row['id']}")
        require(not row["markerEnd"] and not row["markerStart"], f"endpoint marker remained on {row['id']}")
        require(row["arrowCount"] > 0, f"missing middle directional arrow for {row['id']}")
        require(
            row["arrowTs"] and all(0.25 <= t <= 0.75 for t in row["arrowTs"]),
            f"directional arrows for {row['id']} were not placed in the middle: {row['arrowTs']}",
        )
        for arrow in row["arrowGeometry"]:
            require(
                arrow and arrow["nearestDistance"] < 18,
                f"directional arrow for {row['id']} is not near the path midpoint "
                f"({arrow and arrow['nearestDistance']:.2f}px)",
            )
            require(
                arrow["tangentAlignment"] > 0.55,
                f"directional arrow for {row['id']} is not tangent to its cable "
                f"({arrow['tangentAlignment']:.2f})",
            )
        require(row["terminals"] == ["from", "to"], f"missing terminal sockets for {row['id']}: {row['terminals']}")
        require(row["fromSocket"] and row["fromSocket"]["visible"], f"source terminal is not visible for {row['id']}")
        require(row["toSocket"] and row["toSocket"]["visible"], f"target terminal is not visible for {row['id']}")
        require(row["fromDistance"] < 2.5, f"source terminal misses native path end for {row['id']} ({row['fromDistance']:.2f})")
        require(row["toDistance"] < 2.5, f"target terminal misses native path end for {row['id']} ({row['toDistance']:.2f})")
        require(row["labelArrowGap"] > 8, f"label is too close to directional arrow for {row['id']} ({row['labelArrowGap']:.2f})")
    return "all lines have matching hit paths, permanent endpoint sockets, and tangent midpoint arrows"


async def check_labels_sample_the_path(page: Page) -> str:
    result = await eval_state(
        page,
        """() => {
          const rows = edgeGeoms().filter(x => x.e.label);
          return rows.map(row => {
            const text = svg.querySelector(`text.elabel[data-edge="${CSS.escape(row.e.id)}"]`);
            const x = text && parseFloat(text.getAttribute("x"));
            const y = text && parseFloat(text.getAttribute("y"));
             const hit = svg.querySelector(`path.hit[data-edge="${CSS.escape(row.e.id)}"]`);
             const length = hit && hit.getTotalLength ? hit.getTotalLength() : 0;
             const count = length ? Math.max(1, Math.ceil(length / 1)) : 0;
            let nearest = Infinity;
             if (Number.isFinite(x) && Number.isFinite(y) && hit && count) {
               for (let i = 0; i <= count; i++) {
                 const p = hit.getPointAtLength(length * i / count);
                 nearest = Math.min(nearest, Math.hypot(p.x - x, p.y - y));
              }
            }
             return { id: row.e.id, present: !!text, nativePath: !!hit && !!length, nearest };
          });
        }""",
    )
    require(result, "no labelled edge geometries found")
    for row in result:
        require(row["present"], f"missing DOM label for {row['id']}")
        require(row["nativePath"], f"label for {row['id']} has no native SVG path to sample")
        require(row["nearest"] < 4, f"label for {row['id']} is {row['nearest']:.2f}px from sampled path")
    return f"{len(result)} labels sit on their sampled edge paths"


async def check_unrelated_drag_updates_hit_identity(page: Page) -> str:
    before = await edge_snapshot(page, "edge-primary")
    await eval_state(
        page,
        """edgeId => {
          window.__forgeCheckHit = svg.querySelector(`path.hit[data-edge="${CSS.escape(edgeId)}"]`);
          if (!window.__forgeCheckHit) throw new Error("primary hit path missing before drag");
        }""",
        "edge-primary",
    )
    # Put the middle rectangle directly under the route's current midpoint.
    # That makes the obstacle relevant regardless of whether the router chose
    # its upper or lower side.  The selected edge must be recomputed while the
    # drag is still in flight, before mouseup's full render replaces DOM nodes.
    destination = await eval_state(
        page,
        """() => {
          const hit = svg.querySelector('path.hit[data-edge="edge-primary"]');
          const length = hit && hit.getTotalLength ? hit.getTotalLength() : 0;
          if (!hit || !length) throw new Error("primary native SVG path is missing before drag");
          const p = hit.getPointAtLength(length / 2);
          return [p.x, p.y];
        }""",
    )
    await drag_free_node(page, "barrier-b", (destination[0], destination[1]))
    mid = await edge_snapshot(page, "edge-primary")
    identity = await eval_state(
        page,
        """edgeId => {
          const hit = svg.querySelector(`path.hit[data-edge="${CSS.escape(edgeId)}"]`);
          return { same: window.__forgeCheckHit === hit, d: hit && hit.getAttribute("d") };
        }""",
        "edge-primary",
    )
    await page.mouse.up()
    require(identity["same"], "unrelated obstacle drag replaced the hit path mid-frame")
    require(mid["d"] != before["d"], "edge path did not update while unrelated obstacle moved")
    require(mid["hitD"] == mid["lineD"], "mid-frame hit and visible paths diverged")
    return "unrelated obstacle changed route in-flight while retaining hit DOM identity"


async def check_endpoint_drag(page: Page) -> str:
    before = await edge_snapshot(page, "edge-primary")
    node_before = await eval_state(
        page, "id => { const n = byId(id); return [n.x, n.y]; }", "source"
    )
    await drag_free_node(page, "source", (55, 20))
    await page.mouse.up()
    await page.wait_for_timeout(60)
    after = await edge_snapshot(page, "edge-primary")
    node_after = await eval_state(
        page, "id => { const n = byId(id); return [n.x, n.y]; }", "source"
    )
    require(node_after != node_before, "endpoint drag did not move the source rectangle")
    require(after["d"] != before["d"], "endpoint drag did not update the edge path")
    require(after["hitD"] == after["lineD"], "endpoint drag left hit and visible paths out of sync")
    return f"source moved from {node_before} to {node_after}; edge repainted"


async def check_zoom_and_pan(page: Page) -> str:
    before = await eval_state(page, "() => ({s: view.s, tx: view.tx, ty: view.ty})")
    await page.locator("#zoomIn").click()
    await page.wait_for_timeout(40)
    zoomed = await eval_state(page, "() => ({s: view.s, tx: view.tx, ty: view.ty})")
    require(zoomed["s"] > before["s"], "zoom-in control did not change view scale")
    await check_terminals_arrows_and_hits(page)
    await page.locator("#zoomOut").click()
    await page.wait_for_timeout(40)

    box = await page.locator("#stage").bounding_box()
    require(box is not None, "stage has no browser bounding box")
    # The lower-right stage corner is outside this fixture's world objects;
    # starting there exercises the stage pan handler rather than a node drag.
    x = box["x"] + box["width"] - 8
    y = box["y"] + box["height"] - 8
    panned_before = await eval_state(page, "() => ({tx: view.tx, ty: view.ty})")
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.move(x + 26, y + 13, steps=4)
    await page.mouse.up()
    await page.wait_for_timeout(40)
    panned_after = await eval_state(page, "() => ({tx: view.tx, ty: view.ty})")
    require(
        panned_after != panned_before,
        f"stage pan did not change translation ({panned_before} -> {panned_after})",
    )
    return f"zoom {before['s']:.3f} -> {zoomed['s']:.3f}; pan translated stage"


async def check_bend_route_controls(page: Page, fixture: BrowserFixture) -> str:
    selected = await eval_state(
        page,
        """() => {
          SEL = new Set();
          SEL_EDGE = "edge-primary";
          paintSel();
          inspect();
          const handle = document.querySelector('#edge-handles .edge-bend-handle[data-edge="edge-primary"]');
          const waypoint = META && META.edges && META.edges["edge-primary"] &&
            META.edges["edge-primary"].route && META.edges["edge-primary"].route.waypoints;
          return {
            handle: !!handle,
            manual: !!(handle && handle.classList.contains("manual")),
            point: handle && [parseFloat(handle.style.left), parseFloat(handle.style.top)],
            waypoint: waypoint || null,
            fromSide: document.querySelector("#iFromSide") && document.querySelector("#iFromSide").value,
            toSide: document.querySelector("#iToSide") && document.querySelector("#iToSide").value,
            autoButton: !!document.querySelector("#iAutoRoute"),
          };
        }""",
    )
    require(selected["handle"], "selected primary edge did not expose a bend handle")
    require(not selected["manual"], "fixture primary edge unexpectedly started with a manual bend")
    require(not selected["waypoint"], "fixture primary edge unexpectedly started with saved waypoints")
    require(selected["fromSide"] == "right", f"source side selector started at {selected['fromSide']!r}")
    require(selected["toSide"] == "left", f"target side selector started at {selected['toSide']!r}")
    require(selected["autoButton"], "selected line inspector did not expose reset automatic")
    require(
        all(isinstance(value, (int, float)) for value in selected["point"]),
        f"bend handle has no world position: {selected['point']}",
    )

    start = await eval_state(page, "p => toScreen(p[0], p[1])", selected["point"])
    destination_world = [selected["point"][0] + 96, selected["point"][1] + 42]
    finish = await eval_state(page, "p => toScreen(p[0], p[1])", destination_world)
    await page.mouse.move(start[0], start[1])
    await page.mouse.down()
    await page.mouse.move(finish[0], finish[1], steps=12)
    await page.wait_for_timeout(90)
    await page.mouse.up()
    await page.wait_for_timeout(100)

    manual = await eval_state(
        page,
        """() => {
          const handle = document.querySelector('#edge-handles .edge-bend-handle[data-edge="edge-primary"]');
          const waypoint = META && META.edges && META.edges["edge-primary"] &&
            META.edges["edge-primary"].route && META.edges["edge-primary"].route.waypoints;
          return {
            handle: !!handle,
            manual: !!(handle && handle.classList.contains("manual")),
            waypoint: waypoint || null,
            dirty: !!DIRTY,
          };
        }""",
    )
    require(manual["handle"] and manual["manual"], "dragging the selected bend did not leave a manual bend handle")
    require(
        manual["waypoint"] and len(manual["waypoint"]) == 1 and len(manual["waypoint"][0]) == 2,
        f"bend drag did not write META.edges.edge-primary.route.waypoints: {manual['waypoint']}",
    )
    require(manual["dirty"], "bend drag did not mark the fixture dirty")

    puts_before = len(fixture.puts)
    await page.locator("#save").click()
    await page.wait_for_function(
        "() => typeof DIRTY !== 'undefined' && DIRTY === false",
        timeout=8_000,
    )
    await page.wait_for_timeout(100)
    puts = fixture.puts[puts_before:]
    meta_path = TEST_PATH.removesuffix(".canvas") + ".forge.json"
    meta_puts = [put for put in puts if put["path"] == meta_path]
    require(meta_puts, "manual bend save did not issue the mocked forge sibling PUT")
    saved_waypoint = (
        fixture.meta.get("edges", {})
        .get("edge-primary", {})
        .get("route", {})
        .get("waypoints")
    )
    require(saved_waypoint == manual["waypoint"], f"saved bend metadata changed: {saved_waypoint} != {manual['waypoint']}")

    await page.reload(wait_until="domcontentloaded")
    await wait_for_forge(page)
    reloaded = await eval_state(
        page,
        """() => {
          SEL = new Set();
          SEL_EDGE = "edge-primary";
          paintSel();
          inspect();
          const handle = document.querySelector('#edge-handles .edge-bend-handle[data-edge="edge-primary"]');
          const waypoint = META && META.edges && META.edges["edge-primary"] &&
            META.edges["edge-primary"].route && META.edges["edge-primary"].route.waypoints;
          return {
            handle: !!handle,
            manual: !!(handle && handle.classList.contains("manual")),
            waypoint: waypoint || null,
            fromSide: document.querySelector("#iFromSide") && document.querySelector("#iFromSide").value,
            toSide: document.querySelector("#iToSide") && document.querySelector("#iToSide").value,
            autoButton: !!document.querySelector("#iAutoRoute"),
          };
        }""",
    )
    require(reloaded["handle"] and reloaded["manual"], "reload did not restore the manual bend handle")
    require(reloaded["waypoint"] == saved_waypoint, "reload did not restore META.edges route waypoints")
    require(reloaded["fromSide"] == "right", f"reload changed source side selector: {reloaded['fromSide']!r}")
    require(reloaded["toSide"] == "left", f"reload changed target side selector: {reloaded['toSide']!r}")
    require(reloaded["autoButton"], "reload lost the selected line's reset automatic control")

    await page.locator("#iFromSide").select_option("top")
    await page.wait_for_timeout(80)
    await page.locator("#iToSide").select_option("bottom")
    await page.wait_for_timeout(100)
    sides = await eval_state(
        page,
        """() => {
          const e = DOC.edges.find(x => x.id === "edge-primary");
          const hit = svg.querySelector('path.hit[data-edge="edge-primary"]');
          const length = hit && hit.getTotalLength ? hit.getTotalLength() : 0;
          const start = hit && length ? hit.getPointAtLength(0) : null;
          const end = hit && length ? hit.getPointAtLength(length) : null;
          const source = byId("source"), target = byId("target");
          return {
            fromSide: e && e.fromSide || null,
            toSide: e && e.toSide || null,
            fromTop: !!start && !!source &&
              Math.abs(start.y - source.y) <= 5 &&
              start.x >= source.x - 5 && start.x <= source.x + source.width + 5,
            toBottom: !!end && !!target &&
              Math.abs(end.y - (target.y + target.height)) <= 5 &&
              end.x >= target.x - 5 && end.x <= target.x + target.width + 5,
          };
        }""",
    )
    require(sides["fromSide"] == "top", f"source side selector did not save top: {sides['fromSide']!r}")
    require(sides["toSide"] == "bottom", f"target side selector did not save bottom: {sides['toSide']!r}")
    require(sides["fromTop"], "source side selector top did not move the native terminal to the source top")
    require(sides["toBottom"], "target side selector bottom did not move the native terminal to the target bottom")

    await page.locator("#iAutoRoute").click()
    await page.wait_for_timeout(100)
    reset = await eval_state(
        page,
        """() => {
          const e = DOC.edges.find(x => x.id === "edge-primary");
          const handle = document.querySelector('#edge-handles .edge-bend-handle[data-edge="edge-primary"]');
          const route = META && META.edges && META.edges["edge-primary"] &&
            META.edges["edge-primary"].route;
          return {
            fromSide: e && e.fromSide || null,
            toSide: e && e.toSide || null,
            waypoint: route && route.waypoints || null,
            manual: !!(handle && handle.classList.contains("manual")),
            fromSelect: document.querySelector("#iFromSide") && document.querySelector("#iFromSide").value,
            toSelect: document.querySelector("#iToSide") && document.querySelector("#iToSide").value,
            undoEnabled: !document.querySelector("#undo").disabled,
          };
        }""",
    )
    require(reset["fromSide"] is None and reset["toSide"] is None, "reset automatic retained explicit endpoint sides")
    require(not reset["waypoint"], "reset automatic retained META route waypoints")
    require(not reset["manual"], "reset automatic retained the manual bend handle")
    require(reset["fromSelect"] == "" and reset["toSelect"] == "", "reset automatic did not return side selectors to auto")
    require(reset["undoEnabled"], "reset automatic was not added to undo history")

    await page.locator("#undo").click()
    await page.wait_for_timeout(120)
    undone = await eval_state(
        page,
        """() => {
          const e = DOC.edges.find(x => x.id === "edge-primary");
          const handle = document.querySelector('#edge-handles .edge-bend-handle[data-edge="edge-primary"]');
          const waypoint = META && META.edges && META.edges["edge-primary"] &&
            META.edges["edge-primary"].route && META.edges["edge-primary"].route.waypoints;
          return {
            fromSide: e && e.fromSide || null,
            toSide: e && e.toSide || null,
            waypoint: waypoint || null,
            manual: !!(handle && handle.classList.contains("manual")),
            fromSelect: document.querySelector("#iFromSide") && document.querySelector("#iFromSide").value,
            toSelect: document.querySelector("#iToSide") && document.querySelector("#iToSide").value,
          };
        }""",
    )
    require(undone["fromSide"] == "top" and undone["toSide"] == "bottom", "undo did not restore endpoint side selectors")
    require(undone["waypoint"] == saved_waypoint, "undo did not restore the saved manual bend metadata")
    require(undone["manual"], "undo did not restore the manual bend handle")
    require(undone["fromSelect"] == "top" and undone["toSelect"] == "bottom", "undo did not restore inspector side values")

    await page.locator("#iAutoRoute").click()
    await page.wait_for_timeout(100)
    return (
        f"manual bend persisted through save/reload at {saved_waypoint}; "
        "source/target selectors honored explicit ports, reset automatic, and undo restored the bend"
    )


async def check_save_reload(page: Page, fixture: BrowserFixture, base_url: str) -> str:
    puts_before = len(fixture.puts)
    await page.locator("#save").click()
    await page.wait_for_function(
        "() => typeof DIRTY !== 'undefined' && DIRTY === false",
        timeout=8_000,
    )
    await page.wait_for_timeout(100)
    puts = fixture.puts[puts_before:]
    canvas_puts = [put for put in puts if put["path"] == TEST_PATH]
    meta_path = TEST_PATH.removesuffix(".canvas") + ".forge.json"
    meta_puts = [put for put in puts if put["path"] == meta_path]
    require(canvas_puts, "Save did not issue the mocked canvas PUT")
    require(meta_puts, "Save did not issue the mocked forge sibling PUT")
    saved_source = next(n for n in fixture.canvas["nodes"] if n["id"] == "source")
    await page.reload(wait_until="domcontentloaded")
    await wait_for_forge(page)
    reloaded = await eval_state(
        page,
        """() => {
          const n = byId("source");
          return {source: [n.x, n.y], edges: DOC.edges.length, routed: edgeGeoms().map(x => x.e.id)};
        }"""
    )
    require(reloaded["source"] == [saved_source["x"], saved_source["y"]], "reload did not read mocked saved coordinates")
    require(reloaded["edges"] == 3, "reload lost fixture edges")
    require(
        set(reloaded["routed"]) == {"edge-primary", "edge-parallel", "edge-blocked"},
        "reload did not rebuild edge geometry",
    )
    saved_edge = next(edge for edge in fixture.canvas["edges"] if edge["id"] == "edge-primary")
    reloaded_edge = await eval_state(
        page,
        """() => {
          const e = DOC.edges.find(x => x.id === "edge-primary");
          return {fromSide: e.fromSide ?? null, toSide: e.toSide ?? null};
        }""",
    )
    saved_sides = {
        "fromSide": saved_edge.get("fromSide"),
        "toSide": saved_edge.get("toSide"),
    }
    require(
        reloaded_edge == saved_sides,
        f"reload changed saved endpoint sides: {reloaded_edge}",
    )
    require(all(put["path"] in {TEST_PATH, meta_path} for put in puts), "mock observed an unexpected save path")
    return f"mocked save/reload restored source {reloaded['source']} with {len(puts)} PUTs"


async def check_dense_read_only_smoke(page: Page, base_url: str) -> str:
    url = f"{base_url}/forge?path={quote(DENSE_PATH, safe='')}"
    await page.goto(url, wait_until="domcontentloaded")
    await wait_for_forge(page, timeout=20_000)
    state = await eval_state(
        page,
        """() => ({
          nodes: DOC.nodes.length,
          edges: DOC.edges.length,
          drawn: L.size,
          lineHits: svg.querySelectorAll("path.hit").length,
          editable: !!INFO.editable,
          title: document.title,
        })""",
    )
    collision_expression = """() => {
          const expected = DOC.edges.map(e => e.id);
          const rows = edgeGeoms();
          const byId = new Map(rows.map(row => [row.e.id, row]));
          const norm = a => ((a % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
          const inside = (p, o) => {
            if (o.kind === "circle") return Math.hypot(p[0] - o.cx, p[1] - o.cy) < o.r - 1e-6;
            if (o.kind === "rect") return p[0] > o.x && p[0] < o.x + o.w && p[1] > o.y && p[1] < o.y + o.h;
            const radius = Math.hypot(p[0] - o.cx, p[1] - o.cy);
            const angle = norm(Math.atan2(p[1] - o.cy, p[0] - o.cx));
            return radius > o.rIn + 1e-7 && radius < o.rOut - 1e-7 &&
              norm(angle - o.a0) <= norm(o.a1 - o.a0) + 1e-8;
          };
          const obstacleOf = g => {
            if (g.kind === "cell" || g.kind === "blob") {
              return { id: g.id, kind: "circle", cx: g.cx, cy: g.cy, r: g.kind === "cell" ? g.R : g.r };
            }
            if (g.kind === "seg") {
              return { id: g.id, kind: "sector", cx: g.cx, cy: g.cy, rIn: g.rIn, rOut: g.rOut, a0: g.a0, a1: g.a1 };
            }
            return null;
          };
          const worldBox = (el, extra = {}) => {
            const r = el.getBoundingClientRect();
            const corners = [[r.left, r.top], [r.right, r.bottom]].map(p => toWorld(p[0], p[1]));
            const x = Math.min(corners[0][0], corners[1][0]), y = Math.min(corners[0][1], corners[1][1]);
            return {
              id: extra.id || `dom:${el.className}:${el.dataset.id || ""}`,
              sourceId: extra.sourceId || null,
              kind: "rect",
              x, y,
              w: Math.abs(corners[1][0] - corners[0][0]),
              h: Math.abs(corners[1][1] - corners[0][1]),
              pkgId: extra.pkgId || null,
              cellId: extra.cellId || null,
            };
          };
          const lObstacles = [...L.values()].map(obstacleOf).filter(Boolean);
          const domObstacles = [...world.querySelectorAll(".node, .ctile")].map(el =>
            worldBox(el, { sourceId: el.dataset.id })
          );
          const packageElements = [...world.querySelectorAll(".pkg")];
          const packageObstacles = packageElements.map(el => worldBox(el, {
            id: `pkg:${el.dataset.cell}:${el.dataset.pkg}`,
            pkgId: el.dataset.pkg || null,
            cellId: el.dataset.cell || null,
          }));
          const obstacles = lObstacles.concat(domObstacles, packageObstacles);
          const ancestorIds = nodes => {
            const ignored = new Set();
            for (const node of nodes) {
              let current = node;
              while (current) {
                ignored.add(current.id);
                current = parentCell(current);
              }
            }
            return ignored;
          };
          const actualPath = (row, hit) => {
            const length = hit && hit.getTotalLength ? hit.getTotalLength() : 0;
            // Always sample the DOM path itself.  row.points is an
            // implementation detail and is not the rendered geometry once a
            // route is a quadratic/cubic/arc.  One world unit keeps the
            // clearance sweep fine enough to see narrow crossings without
            // making a polyline claim about a curve.
            const count = length ? Math.max(1, Math.ceil(length / 1)) : 0;
            return {
              points: length ? Array.from({ length: count + 1 }, (_, i) => {
                const p = hit.getPointAtLength(length * i / count);
                return [p.x, p.y];
              }) : [],
              nativePath: !!hit && !!length,
              pathLength: length,
              sampleStep: count ? length / count : 0,
            };
          };
          const violations = [];
          const missingHit = [];
          const invalidPath = [];
          const visibleSvgIds = new Set([...cellsSvg.querySelectorAll("path.seg, path.mouth, circle.blob")]
            .map(el => el.dataset.id).filter(Boolean));
          for (const id of expected) {
            const row = byId.get(id);
            if (!row) continue;
            const ignored = ancestorIds([row.a, row.b, row.oa, row.ob]);
            const ownPackage = row.ship ? pkgOnLine(row.e) : null;
            const ownCell = row.ship ? parentCell(row.a) : null;
            const relevant = obstacles.filter(o =>
              !ignored.has(o.sourceId || o.id) &&
              !(o.pkgId && ownPackage && o.pkgId === ownPackage.id &&
                o.cellId === (ownCell && ownCell.id))
            );
            const hit = svg.querySelector(`path.hit[data-edge="${CSS.escape(id)}"]`);
            if (!hit) {
              missingHit.push(id);
              continue;
            }
            const path = actualPath(row, hit);
            if (!path.nativePath) {
              invalidPath.push(id);
              continue;
            }
            const points = path.points;
            for (const point of points) {
              for (const obstacle of relevant) {
                if (inside(point, obstacle)) {
                  violations.push({ id, label: row.e.label || id, obstacle: obstacle.id, kind: "point" });
                }
              }
            }
            for (let i = 1; i < points.length; i++) {
              for (const obstacle of relevant) {
                // Adjacent one-unit native samples are the local curve
                // approximation.  Check their clearance too, rather than
                // merely asking whether a sparse point happened to land
                // outside an obstacle.
                if (!ForgeRouting.clearSegment(points[i - 1], points[i], [obstacle], 14)) {
                  violations.push({ id, label: row.e.label || id, obstacle: obstacle.id, kind: "clearance" });
                }
              }
            }
          }
          return {
            expected,
            rowCount: rows.length,
            missing: expected.filter(id => !byId.has(id)),
            missingHit,
            invalidPath,
            blocked: rows.filter(row => expected.includes(row.e.id) && row.blocked)
              .map(row => ({ id: row.e.id, label: row.e.label || row.e.id })),
            obstacleCount: obstacles.length,
            domObstacleCount: domObstacles.length,
            packageCount: packageElements.length,
            renderedSvgObstacleCount: visibleSvgIds.size,
            violations,
          };
        }"""
    await page.locator("#fit").click()
    await page.wait_for_timeout(180)
    fit_view = await eval_state(page, "() => view.s")
    fit_collision = await eval_state(page, collision_expression)
    await eval_state(
        page,
        "() => { while (view.s < 0.6) zoomAt(1.25, stage.clientWidth / 2, stage.clientHeight / 2); zoomAt(1.25, stage.clientWidth / 2, stage.clientHeight / 2); return view.s; }",
    )
    await page.wait_for_timeout(220)
    detail_view = await eval_state(page, "() => view.s")
    detail_collision = await eval_state(page, collision_expression)
    timing = await eval_state(
        page,
        """() => {
          const samples = [];
          let count = 0;
          for (let i = 0; i < 10; i++) {
            const started = performance.now();
            count = edgeGeoms().length;
            samples.push(performance.now() - started);
          }
          return {
            iterations: samples.length,
            edgeCount: count,
            totalMs: samples.reduce((a, b) => a + b, 0),
            maxMs: Math.max(...samples),
          };
        }""",
    )

    def require_collision(snapshot: dict[str, Any], phase: str) -> None:
        require(
            not snapshot["missing"],
            f"dense canvas edges missing geometry at {phase}: {', '.join(snapshot['missing'])}",
        )
        require(
            not snapshot["missingHit"],
            f"dense canvas edges missing hit paths at {phase}: {', '.join(snapshot['missingHit'])}",
        )
        require(
            not snapshot["invalidPath"],
            f"dense canvas edges have no native SVG geometry at {phase}: "
            f"{', '.join(snapshot['invalidPath'])}",
        )
        require(
            not snapshot["blocked"],
            f"dense canvas has blocked routes at {phase}: "
            + ", ".join(f"{row['label']} ({row['id']})" for row in snapshot["blocked"]),
        )
        require(
            not snapshot["violations"],
            f"dense canvas route collisions at {phase}: "
            + ", ".join(
                f"{row['label']} ({row['id']})/{row['obstacle']} [{row['kind']}]"
                for row in snapshot["violations"][:12]
            ),
        )
        require(snapshot["domObstacleCount"] > 0, f"dense canvas has no DOM obstacles at {phase}")
        require(
            snapshot["renderedSvgObstacleCount"] > 0,
            f"dense canvas has no rendered SVG band/blob obstacles at {phase}",
        )
        require(snapshot["packageCount"] > 0, f"dense canvas rendered no package chips at {phase}")

    require(state["nodes"] >= 20, f"dense sample unexpectedly has only {state['nodes']} nodes")
    require(state["drawn"] > 0, "dense sample produced no drawn geometry")
    require(state["lineHits"] > 0, "dense sample produced no edge hit paths")
    require(fit_view > 0, f"dense fit produced invalid view scale {fit_view}")
    require(detail_view > fit_view, f"dense detail zoom did not increase scale ({fit_view} -> {detail_view})")
    require_collision(fit_collision, "fit")
    require_collision(detail_collision, "detail zoom")
    require(timing["iterations"] == 10, "dense reroute timing did not run ten iterations")
    require(timing["edgeCount"] > 0, "dense edgeGeoms produced no route geometries")
    # This smoke check intentionally performs no pointer or save operation on
    # the real canvas.  INFO.editable is reported, not used to mutate it.
    return (
        f"dense read-only smoke rendered {state['nodes']} nodes, "
        f"{state['edges']} edges, {state['lineHits']} hit paths "
        f"(editable={state['editable']}); {detail_collision['rowCount']} edges clear "
        f"of {detail_collision['obstacleCount']} rendered obstacles "
        f"({detail_collision['packageCount']} package chips; fit/detail collision checks); edgeGeoms x10 "
        f"{timing['totalMs']:.1f} ms total / {timing['maxMs']:.1f} ms max"
    )


async def check_chat_machine_scout_read_only(page: Page, base_url: str) -> str:
    """Check the short, visible links in the Scout Researcher cell.

    The drawing intentionally contains a few cross-cell links whose endpoints
    can overlap the deliberately dense layout.  They are reported below but
    are not blanket-rejected.  The three neighbouring Scout links are the
    stable acceptance target: their saved ports are adjacent in the source
    drawing, so a long detour or an added endpoint guard is gratuitous unless
    the actual endpoint rectangles force a corner detour.
    """

    url = f"{base_url}/forge?path={quote(CHAT_MACHINE_PATH, safe='')}"
    await page.goto(url, wait_until="domcontentloaded")
    await wait_for_forge(page, timeout=20_000)
    state = await eval_state(
        page,
        """() => {
          const cell = re => DOC.nodes.find(n => n.type === "group" && re.test(String(n.label || "")));
          const scout = cell(/HOLON\\s*·\\s*SCOUT RESEARCHER/i);
          const current = cell(/PRIMARY CURRENT/i);
          if (!scout) throw new Error("Scout Researcher cell was not found in the drawing");
          if (!current) throw new Error("primary current cell was not found in the drawing");
          const childIds = parent => new Set(DOC.nodes.filter(n =>
            n.id !== parent.id && n.type !== "group" && contains(parent, n)
          ).map(n => n.id));
          const scoutChildren = childIds(scout);
          const directLabels = new Set(["queries", "new finds", "shaped"]);
          const directEdges = DOC.edges.filter(e =>
            scoutChildren.has(e.fromNode) && scoutChildren.has(e.toNode) && directLabels.has(e.label)
          );
          const scoutEdges = DOC.edges.filter(e =>
            scoutChildren.has(e.fromNode) || scoutChildren.has(e.toNode)
          );
          const rows = edgeGeoms();
          const rowIds = new Set(rows.map(row => row.e.id));
          const allBlocked = rows.filter(row => row.blocked).map(row => ({
            id: row.e.id,
            label: row.e.label || row.e.id,
          }));
          return {
            nodes: DOC.nodes.length,
            edges: DOC.edges.length,
            scoutId: scout.id,
            scoutLabel: scout.label,
            currentId: current.id,
            scoutChildren: [...scoutChildren],
            directEdges: directEdges.map(e => ({
              id: e.id,
              label: e.label,
              fromNode: e.fromNode,
              toNode: e.toNode,
              fromSide: e.fromSide,
              toSide: e.toSide,
              hasGeometry: rowIds.has(e.id),
            })),
            scoutEdges: scoutEdges.map(e => ({
              id: e.id,
              label: e.label,
              hasGeometry: rowIds.has(e.id),
              hasHit: !!svg.querySelector(`path.hit[data-edge="${CSS.escape(e.id)}"]`),
            })),
            allBlocked,
            dirty: !!DIRTY,
            scoutSvg: !!cellsSvg.querySelector(`g.cellg[data-id="${CSS.escape(scout.id)}"]`),
          };
        }""",
    )
    require(state["nodes"] >= 14, f"chat-machine drawing unexpectedly has only {state['nodes']} nodes")
    require(state["edges"] >= 9, f"chat-machine drawing unexpectedly has only {state['edges']} edges")
    require(state["scoutSvg"], f"Scout Researcher cell {state['scoutId']} has no rendered SVG cell")
    require(not state["dirty"], "chat-machine read-only check unexpectedly dirtied the drawing")
    require(
        len(state["directEdges"]) == 3,
        "could not locate all three adjacent Scout connections "
        f"(found {[row['label'] for row in state['directEdges']]})",
    )
    require(
        all(row["hasGeometry"] for row in state["directEdges"]),
        "an adjacent Scout connection has no edge geometry",
    )
    require(
        all(row["hasGeometry"] and row["hasHit"] for row in state["scoutEdges"]),
        "a Scout Researcher connection has no rendered geometry/hit path",
    )

    direct = await eval_state(
        page,
        """() => {
          const cell = re => DOC.nodes.find(n => n.type === "group" && re.test(String(n.label || "")));
          const scout = cell(/HOLON\\s*·\\s*SCOUT RESEARCHER/i);
          const scoutChildren = new Set(DOC.nodes.filter(n =>
            n.id !== scout.id && n.type !== "group" && contains(scout, n)
          ).map(n => n.id));
          const labels = new Set(["queries", "new finds", "shaped"]);
          const domBoxes = [...world.querySelectorAll(".node, .ctile")].map(el => {
            const r = el.getBoundingClientRect();
            const [x, y] = toWorld(r.left, r.top), [x1, y1] = toWorld(r.right, r.bottom);
            return {
              id: el.dataset.id || "",
              x: Math.min(x, x1),
              y: Math.min(y, y1),
              w: Math.abs(x1 - x),
              h: Math.abs(y1 - y),
            };
          });
          const boxById = new Map();
          for (const box of domBoxes) if (box.id && !boxById.has(box.id)) boxById.set(box.id, box);
          const socketPoint = (box, side) => {
            if (!box) return null;
            if (side === "left") return [box.x, box.y + box.h / 2];
            if (side === "right") return [box.x + box.w, box.y + box.h / 2];
            if (side === "top") return [box.x + box.w / 2, box.y];
            if (side === "bottom") return [box.x + box.w / 2, box.y + box.h];
            return null;
          };
          const socketNormal = side => ({
            left: [-1, 0],
            right: [1, 0],
            top: [0, -1],
            bottom: [0, 1],
          }[side] || null);
          const unit = p => {
            const length = Math.hypot(p[0], p[1]) || 1;
            return [p[0] / length, p[1] / length];
          };
          // Test open rectangle interiors, not padded rectangles.  A cable may
          // touch a DOM corner or run on a DOM boundary, but cannot enter the
          // interior.  This is deliberately independent of ForgeRouting's
          // clearance preparation and uses only the rendered DOM boxes.
          const openRange = (a, b, lo, hi) => {
            if (Math.abs(b - a) < 1e-9) return a > lo && a < hi ? [-Infinity, Infinity] : null;
            const p = (lo - a) / (b - a), q = (hi - a) / (b - a);
            return [Math.min(p, q), Math.max(p, q)];
          };
          const crossesInterior = (a, b, box, tolerance = 0) => {
            const inset = Math.min(tolerance, Math.max(0, Math.min(box.w, box.h) / 2 - 1e-7));
            const xr = openRange(a[0], b[0], box.x + inset, box.x + box.w - inset);
            const yr = openRange(a[1], b[1], box.y + inset, box.y + box.h - inset);
            if (!xr || !yr) return false;
            const lo = Math.max(0, xr[0], yr[0]), hi = Math.min(1, xr[1], yr[1]);
            return hi - lo > 1e-8;
          };
          const shortestCornerRoute = (start, end, obstacles) => {
            if (!start || !end) return { length: Infinity, corners: 0 };
            const points = [start, end];
            for (const box of obstacles) {
              points.push(
                [box.x, box.y],
                [box.x + box.w, box.y],
                [box.x + box.w, box.y + box.h],
                [box.x, box.y + box.h],
              );
            }
            const best = Array(points.length).fill(Infinity), used = new Set();
            best[0] = 0;
            for (let step = 0; step < points.length; step++) {
              let at = -1;
              for (let i = 0; i < points.length; i++) {
                if (!used.has(i) && (at < 0 || best[i] < best[at])) at = i;
              }
              if (at < 0 || !Number.isFinite(best[at])) break;
              used.add(at);
              for (let next = 0; next < points.length; next++) {
                if (used.has(next) || next === at) continue;
                if (obstacles.some(box => crossesInterior(points[at], points[next], box))) continue;
                const length = Math.hypot(
                  points[at][0] - points[next][0],
                  points[at][1] - points[next][1],
                );
                best[next] = Math.min(best[next], best[at] + length);
              }
            }
            return { length: best[1], corners: points.length - 2 };
          };
          const rows = edgeGeoms();
          const byId = new Map(rows.map(row => [row.e.id, row]));
          const pointAt = (hit, length, t) => {
            const p = hit.getPointAtLength(length * t);
            return [p.x, p.y];
          };
          const samplePath = hit => {
            const length = hit.getTotalLength();
            const count = length ? Math.max(1, Math.ceil(length / 1)) : 0;
            const points = length ? Array.from({ length: count + 1 }, (_, i) =>
              pointAt(hit, length, i / count)
            ) : [];
            return { length, count, points };
          };
          const endpointBoundaryTolerance = 0.1;
          const inBox = (p, b, tolerance = 0) => {
            const inset = Math.min(tolerance, Math.max(0, Math.min(b.w, b.h) / 2 - 1e-7));
            return p[0] > b.x + inset && p[0] < b.x + b.w - inset &&
              p[1] > b.y + inset && p[1] < b.y + b.h - inset;
          };
          const directEdges = DOC.edges.filter(e =>
            scoutChildren.has(e.fromNode) && scoutChildren.has(e.toNode) && labels.has(e.label)
          );
          const checked = directEdges.map(e => {
            const row = byId.get(e.id);
            const hit = svg.querySelector(`path.hit[data-edge="${CSS.escape(e.id)}"]`);
            const line = svg.querySelector(`path.line[data-edge="${CSS.escape(e.id)}"]`);
            const from = L.get(e.fromNode), to = L.get(e.toNode);
            const fromBox = boxById.get(e.fromNode), toBox = boxById.get(e.toNode);
            const expectedStart = socketPoint(fromBox, e.fromSide) || (from && portPoint(from, e.fromSide));
            const expectedEnd = socketPoint(toBox, e.toSide) || (to && portPoint(to, e.toSide));
            if (!row || !hit || !from || !to || !expectedStart || !expectedEnd || !hit.getTotalLength()) {
              return { id: e.id, label: e.label, valid: false };
            }
            const path = samplePath(hit);
            const start = path.points[0], end = path.points[path.points.length - 1];
            const directGap = Math.hypot(
              expectedStart[0] - expectedEnd[0], expectedStart[1] - expectedEnd[1]
            );
            // Include both endpoint boxes: the saved socket is on a boundary,
            // but a cubic that turns into its own tile is still a collision.
            const pathBoxes = domBoxes.filter(b => b.id);
            const endpointBoxes = [fromBox, toBox].filter(Boolean);
            const endpointTolerance = box => endpointBoxes.includes(box) ? endpointBoundaryTolerance : 0;
            const domCollisions = path.points.filter(p => pathBoxes.some(b =>
              inBox(p, b, endpointTolerance(b))
            ))
              .map(p => p);
            const segmentCollisions = [];
            for (let i = 1; i < path.points.length; i++) {
              for (const box of pathBoxes) {
                if (crossesInterior(
                  path.points[i - 1], path.points[i], box, endpointTolerance(box)
                )) {
                  segmentCollisions.push({ box: box.id, segment: i - 1 });
                }
              }
            }
            const endpointCollisions = path.points.filter(p =>
              endpointBoxes.some(box => inBox(p, box, endpointBoundaryTolerance))
            ).length;
            const reference = shortestCornerRoute(expectedStart, expectedEnd, pathBoxes);
            const startNormal = fromBox
              ? socketNormal(e.fromSide)
              : (ForgeRouting.portNormal(from, expectedStart, e.fromSide) || null);
            const endNormal = toBox
              ? socketNormal(e.toSide)
              : (ForgeRouting.portNormal(to, expectedEnd, e.toSide) || null);
            const startTangent = unit([
              path.points[Math.min(path.points.length - 1, 8)][0] - start[0],
              path.points[Math.min(path.points.length - 1, 8)][1] - start[1],
            ]);
            const endTangent = unit([
              end[0] - path.points[Math.max(0, path.points.length - 1 - 8)][0],
              end[1] - path.points[Math.max(0, path.points.length - 1 - 8)][1],
            ]);
            const d = hit.getAttribute("d") || "";
            return {
              id: e.id,
              label: e.label,
              valid: true,
              blocked: !!row.blocked,
              line: !!line && line.classList.contains("line"),
              sameD: !!line && line.getAttribute("d") === d,
              start,
              end,
              expectedStart,
              expectedEnd,
              startError: Math.hypot(start[0] - expectedStart[0], start[1] - expectedStart[1]),
              endError: Math.hypot(end[0] - expectedEnd[0], end[1] - expectedEnd[1]),
               startNormalDot: startNormal ? startTangent[0] * startNormal[0] + startTangent[1] * startNormal[1] : null,
               endNormalDot: endNormal ? endTangent[0] * endNormal[0] + endTangent[1] * endNormal[1] : null,
              directGap,
              length: path.length,
               referenceLength: reference.length,
               referenceCorners: reference.corners,
               referenceRatio: reference.length ? path.length / reference.length : Infinity,
              sampleStep: path.count ? path.length / path.count : Infinity,
              domCollisions: domCollisions.length,
               segmentCollisions,
               endpointCollisions,
               endpointRectCount: endpointBoxes.length,
              commands: [...d.matchAll(/[A-Za-z]/g)].map(m => m[0]),
            };
          });
          return {
            checked,
            domObstacleCount: domBoxes.length,
            renderedSvgObstacleCount: cellsSvg.querySelectorAll("path.seg, path.mouth, circle.blob").length,
          };
        }""",
    )
    for row in direct["checked"]:
        require(row["valid"], f"Scout direct edge {row['id']} has no native SVG geometry")
        require(not row["blocked"], f"Scout direct edge {row['id']} is blocked")
        require(row["line"] and row["sameD"], f"Scout direct edge {row['id']} hit/visible paths diverge")
        require(
            row["startError"] <= 2.5 and row["endError"] <= 2.5,
            f"Scout direct edge {row['id']} has an endpoint hook "
            f"(errors {row['startError']:.1f}/{row['endError']:.1f})",
        )
        # In the saved drawing each of these three neighbouring ports has a
        # native outward socket tangent.  Endpoint rectangles are intentionally
        # unpadded: boundary contact is legal, but an initial cubic turn into
        # either endpoint tile is not.
        require(
            row["endpointRectCount"] >= 1 and not row["endpointCollisions"],
            f"Scout direct edge {row['id']} enters an endpoint tile "
            f"({row['endpointCollisions']} interior samples)",
        )
        require(
            row["startNormalDot"] is not None and row["endNormalDot"] is not None and
            row["startNormalDot"] >= 0.55 and row["endNormalDot"] <= -0.55,
            f"Scout direct edge {row['id']} leaves/arrives with the wrong socket tangent "
            f"({row['startNormalDot']!s}/{row['endNormalDot']!s})",
        )
        require(
            not row["domCollisions"] and not row["segmentCollisions"],
            f"Scout direct edge {row['id']} crosses a DOM tile interior "
            f"(points={row['domCollisions']}, segments={len(row['segmentCollisions'])})",
        )
        # Compare with the shortest visibility-graph route through the actual
        # DOM rectangle corners.  This permits the saved backside ports to
        # loop around an endpoint tile, while rejecting an excursion that is
        # gratuitously longer than the necessary corner detour.  The modest
        # 1.35 slack covers smooth cubic curvature and the renderer's actual
        # obstacle clearance; it is never measured against the forbidden chord.
        require(
            row["directGap"] >= 20 and row["referenceLength"] < float("inf"),
            f"Scout direct edge {row['id']} has no valid DOM-corner reference route "
            f"(direct gap {row['directGap']:.1f})",
        )
        require(
            row["referenceRatio"] <= 1.35,
            f"Scout direct edge {row['id']} is gratuitously long relative to its "
            f"DOM-corner route (path {row['length']:.1f}, reference "
            f"{row['referenceLength']:.1f}, ratio {row['referenceRatio']:.2f})",
        )
        require(
            row["sampleStep"] <= 1.01,
            f"Scout direct edge {row['id']} used coarse native-path samples "
            f"({row['sampleStep']:.2f} world units)",
        )
    return (
        f"Scout Researcher cell {state['scoutId']} direct links "
        f"{', '.join(row['id'] for row in direct['checked'])} stay attached and short "
        f"(DOM-corner route ratios {', '.join(f'{row['referenceRatio']:.2f}' for row in direct['checked'])}); "
        f"{len(state['allBlocked'])} other dense-layout routes reported without blanket rejection "
        f"(DOM obstacles={direct['domObstacleCount']}, "
        f"SVG obstacles={direct['renderedSvgObstacleCount']})"
    )


async def run(base_url: str) -> list[CheckResult]:
    fixture = BrowserFixture()
    results: list[CheckResult] = []
    async with async_playwright() as playwright:
        if not os.path.exists(CHROMIUM):
            raise RuntimeError(f"required Chromium executable is missing: {CHROMIUM}")
        browser: Browser = await playwright.chromium.launch(
            executable_path=CHROMIUM,
            headless=True,
            args=["--no-sandbox"],
        )
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.route("**/api/forge**", fixture.forge)
            await page.route("**/api/file**", fixture.file)
            await page.goto(
                f"{base_url}/forge?path={quote(TEST_PATH, safe='')}",
                wait_until="domcontentloaded",
            )
            await wait_for_forge(page)

            checks = [
                ("fixture loaded", lambda: check_fixture_loaded(page)),
                ("multiple obstacles", lambda: check_multiple_obstacles(page)),
                ("saved endpoint-side attachment", lambda: check_endpoint_side_attachment(page)),
                ("blocked hit tooltip", lambda: check_blocked_hit_tooltip(page)),
                ("parallel edges distinct", lambda: check_parallel_distinct(page)),
                ("terminals, arrows and hit paths", lambda: check_terminals_arrows_and_hits(page)),
                ("labels sample routed path", lambda: check_labels_sample_the_path(page)),
                ("unrelated drag is lightweight", lambda: check_unrelated_drag_updates_hit_identity(page)),
                ("endpoint drag", lambda: check_endpoint_drag(page)),
                ("bend route controls", lambda: check_bend_route_controls(page, fixture)),
                ("zoom and pan", lambda: check_zoom_and_pan(page)),
                ("mocked save and reload", lambda: check_save_reload(page, fixture, base_url)),
                ("dense real-canvas smoke", lambda: check_dense_read_only_smoke(page, base_url)),
                ("chat-machine Scout Researcher", lambda: check_chat_machine_scout_read_only(page, base_url)),
            ]
            for name, check in checks:
                started = time.perf_counter()
                try:
                    detail = await check()
                except Exception as exc:  # keep later focused checks running
                    results.append(
                        CheckResult(
                            name=name,
                            elapsed_ms=(time.perf_counter() - started) * 1000,
                            ok=False,
                            detail=f"{type(exc).__name__}: {exc}",
                        )
                    )
                else:
                    results.append(
                        CheckResult(
                            name=name,
                            elapsed_ms=(time.perf_counter() - started) * 1000,
                            ok=True,
                            detail=detail,
                        )
                    )
        finally:
            await browser.close()
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=None,
        help="Brain Viewer origin (default: https://$REPLIT_DEV_DOMAIN)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    domain = os.environ.get("REPLIT_DEV_DOMAIN", "").strip()
    base_url = (args.base_url or (f"https://{domain}" if domain else "")).rstrip("/")
    if not base_url:
        print("ERROR: REPLIT_DEV_DOMAIN is not set; pass --base-url", file=sys.stderr)
        return 2
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url

    started = time.perf_counter()
    try:
        results = asyncio.run(run(base_url))
    except (RuntimeError, PlaywrightTimeoutError) as exc:
        print(f"ERROR: browser checks could not start: {exc}", file=sys.stderr)
        return 2
    print(f"Forge browser checks against {base_url}")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {result.name} ({result.elapsed_ms:.1f} ms) — {result.detail}")
    passed = sum(result.ok for result in results)
    failed = len(results) - passed
    print(
        f"Summary: {passed} passed, {failed} failed, "
        f"{(time.perf_counter() - started) * 1000:.1f} ms total"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())