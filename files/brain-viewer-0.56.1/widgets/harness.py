#!/usr/bin/env python3
"""harness.py -- mount ONE home widget in a real DOM against canned responses, and say whether it holds (T-0217).

  python skills/brain-viewer/widgets/harness.py skills/brain-viewer/widgets/dial.js   one widget, the full report
  python skills/brain-viewer/widgets/harness.py --all                                every widget, one line each
  python skills/brain-viewer/widgets/harness.py --capture                            refresh fixtures/ from the live server
  add --json for the report as JSON, --verbose to print the warnings on a passing run

WHAT IT DOES. `node --check` on the file first. Then it loads the REAL home.html into jsdom (installed under
skills/brain-viewer/node_modules by `npm install`), with the real viewer-common.js and the real guard, and hands the
page a board holding only the widget under test. Every `/api/...` read the page makes is answered from
widgets/fixtures/<endpoint>.json, captured from the live server, so the widget draws against real response shapes
with no server running. The page boots (mount), the harness runs the board's own refreshAll() (refresh), then calls
the widget's resize() if it declares one.

WHAT FAILS A RUN (exit 1):
  * the file fails `node --check`, or does not register the id its filename names
  * an error is thrown anywhere, in mount, refresh, resize, a timer or a handler (reported with its stack)
  * the page's own guard turned the tile red-edged (that is the same break Zak would see on the board)
  * an endpoint was requested that has no fixture file (add one with --capture, or by hand from the live server)
  * an UNBOUND PART: the body stayed empty without the widget hiding itself, or text or an attribute in the body
    still holds a placeholder the widget never filled: undefined, NaN, null, [object Object], a template mark, or
    a "loading" line left standing after everything settled
WHAT ONLY WARNS: an empty element carrying a data-* hook (often a slot a widget fills later on purpose), a write the
widget made (a POST or PUT, answered with an empty ok), and jsdom's "not implemented" notices.

Exit 0 when the widget holds, 1 when it does not, 2 when the harness itself cannot run (no node, no jsdom).
"""

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import urllib.request

WIDGETS = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.dirname(WIDGETS)
FIXTURES = os.path.join(WIDGETS, "fixtures")
NODE_TIMEOUT = 90
# What home.html and viewer-common.js read on their own, whatever is on the board: the nav badges, the glossary strip and
# the quest log. They are answered like any other read but are not counted as the widget's, so "N endpoints" in a
# report is what the widget itself asked for, and a widget that asks for nothing may draw nothing (the Space gap).
PAGE_READS = ("/api/badges", "/api/glossary", "/api/quests", "/api/help")

# What --capture reads off the live server: the endpoint as a widget asks for it (the query it sends), and how much of
# a big answer to keep. The fixture file is named by the PATH alone, so every query a widget sends to one endpoint is
# answered by one file, which is how the page's own reads are shaped too.
CAPTURE = [
    ("/api/agents", {"sessions": 6}),
    ("/api/badges", None),
    ("/api/calendar/week", None),
    ("/api/calls", None),
    ("/api/chats", None),
    ("/api/chat?id={chat}", {"turns": 6}),       # after /api/chats: it opens the newest conversation that one lists
    ("/api/glossary", None),
    ("/api/graph", None),
    ("/api/groups", None),
    ("/api/help", None),
    ("/api/holons", None),
    ("/api/landed", None),
    ("/api/manifest", None),
    ("/api/mantras", None),
    ("/api/maps", None),
    ("/api/moved?limit=200", None),
    ("/api/notes?limit=3", None),
    ("/api/people", None),
    ("/api/projects", None),
    ("/api/quests", None),
    ("/api/review", None),
    ("/api/search?limit=3&q=brain", None),
    ("/api/stages", None),
    ("/api/status", None),
    ("/api/system", None),
    ("/api/today/tasks?app=1", None),
    ("/api/waiting", None),
]


def fixture_name(path):
    """/api/today/tasks?app=1 -> today-tasks.json"""
    p = path.split("?")[0]
    p = p[len("/api/"):] if p.startswith("/api/") else p.lstrip("/")
    return p.replace("/", "-") + ".json"


def capture(base):
    os.makedirs(FIXTURES, exist_ok=True)
    got, chat = {}, ""
    for path, trim in CAPTURE:
        if "{chat}" in path:
            if not chat:
                print("skip %s (no conversation in /api/chats)" % path)
                continue
            path = path.replace("{chat}", chat)
        try:
            with urllib.request.urlopen(base.rstrip("/") + path, timeout=60) as r:
                j = json.loads(r.read().decode("utf-8"))
        except Exception as e:                    # noqa: BLE001 -- one endpoint down must not cost the rest
            print("FAIL %s  -- %s" % (path, e))
            continue
        if path.startswith("/api/chats"):
            chat = ((j.get("chats") or [{}])[0] or {}).get("id") or ""
        for key, n in (trim or {}).items():
            if isinstance(j.get(key), list):
                j[key] = j[key][:n]
        name = fixture_name(path)
        with open(os.path.join(FIXTURES, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(j, f, ensure_ascii=False, indent=1)
            f.write("\n")
        got[name] = path
        print("ok   %-22s %s" % (name, path))
    with open(os.path.join(FIXTURES, "_captured.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"capturedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "base": base,
                   "files": got}, f, indent=1)
        f.write("\n")
    print("%d fixtures written to %s" % (len(got), os.path.relpath(FIXTURES)))
    return 0


def node_bin():
    return shutil.which("node")


def node_check(node, path):
    p = subprocess.run([node, "--check", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    return p.returncode == 0, p.stderr.decode("utf-8", "replace").strip()


def run_one(path):
    """-> report dict. `ok` is the verdict; `fatal` means the harness itself could not run."""
    path = os.path.abspath(path)
    wid = os.path.splitext(os.path.basename(path))[0]
    rep = {"id": wid, "file": os.path.relpath(path, VIEWER).replace("\\", "/"), "ok": False, "fatal": False,
           "errors": [], "broken": [], "missing": [], "unbound": [], "warnings": [], "requested": []}
    node = node_bin()
    if not node:
        rep.update(fatal=True, errors=[{"phase": "setup", "message": "node is not on PATH"}])
        return rep
    if not os.path.isfile(path):
        rep["errors"].append({"phase": "setup", "message": "no such file: %s" % path})
        return rep
    ok, err = node_check(node, path)
    if not ok:
        said = [l.strip() for l in err.splitlines() if "Error" in l and not l.strip().startswith("at ")]
        rep["errors"].append({"phase": "node --check", "message": said[0] if said else "syntax error",
                              "stack": err})
        return rep
    if not os.path.isdir(os.path.join(VIEWER, "node_modules", "jsdom")):
        rep.update(fatal=True, errors=[{"phase": "setup", "message": "jsdom is not installed: run `npm install` in skills/brain-viewer"}])
        return rep
    cfg = {"viewer": VIEWER, "file": path, "id": wid, "fixtures": FIXTURES, "settleMs": 250, "maxMs": 6000}
    env = dict(os.environ, BV_HARNESS=json.dumps(cfg))
    try:
        p = subprocess.run([node, "-"], input=NODE_JS.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           cwd=VIEWER, env=env, timeout=NODE_TIMEOUT)
    except subprocess.TimeoutExpired:
        rep["errors"].append({"phase": "harness", "message": "the page did not settle in %d seconds" % NODE_TIMEOUT})
        return rep
    out = p.stdout.decode("utf-8", "replace")
    line = next((l for l in reversed(out.splitlines()) if l.startswith("BVH ")), None)
    if not line:
        rep.update(fatal=True)
        rep["errors"].append({"phase": "harness", "message": "the node side gave no report",
                              "stack": (p.stderr.decode("utf-8", "replace") or out)[-3000:]})
        return rep
    rep.update(json.loads(line[4:]))
    rep["page"] = [r for r in rep["requested"] if r in PAGE_READS]
    rep["requested"] = [r for r in rep["requested"] if r not in PAGE_READS]
    if not rep["requested"]:
        # it read nothing, so an empty body is the widget's design (a gap), not a part it failed to fill
        rep["unbound"] = [u for u in rep["unbound"] if not u.startswith("the body stayed empty")]
    rep["ok"] = not (rep["errors"] or rep["broken"] or rep["missing"] or rep["unbound"])
    return rep


def one_line(rep):
    if rep["ok"]:
        extra = (" · %d warning%s" % (len(rep["warnings"]), "" if len(rep["warnings"]) == 1 else "s")) if rep["warnings"] else ""
        return "ok   %-10s %d endpoint%s%s" % (rep["id"], len(rep["requested"]), "" if len(rep["requested"]) == 1 else "s", extra)
    first = (rep["errors"] or rep["broken"] or [{}])[0]
    why = (first.get("message") if first else "") or ""
    if not why and rep["missing"]:
        why = "no fixture for " + ", ".join(rep["missing"])
    if not why and rep["unbound"]:
        why = "unbound: " + rep["unbound"][0]
    return "FAIL %-10s %s" % (rep["id"], why[:160])


def full(rep, verbose):
    print(one_line(rep))
    for e in rep["errors"]:
        print("  error (%s): %s" % (e.get("phase"), e.get("message")))
        if e.get("stack"):
            for s in str(e["stack"]).splitlines()[:8]:
                print("      " + s)
    for b in rep["broken"]:
        print("  the tile went red (%s): %s" % (b.get("where") or "?", b.get("error")))
    for m in rep["missing"]:
        print("  no fixture: %s (would be fixtures/%s)" % (m, fixture_name(m)))
    for u in rep["unbound"]:
        print("  unbound: %s" % u)
    if verbose or not rep["ok"]:
        for w in rep["warnings"]:
            print("  warning: %s" % w)
    print("  read: %s" % (", ".join(rep["requested"]) or "nothing"))
    if rep.get("page"):
        print("  the page itself read: %s" % ", ".join(rep["page"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="mount one home widget in jsdom against canned responses")
    ap.add_argument("file", nargs="?", help="the widget file, e.g. skills/brain-viewer/widgets/dial.js")
    ap.add_argument("--all", action="store_true", help="every widget in the folder, one line each")
    ap.add_argument("--capture", action="store_true", help="refresh fixtures/ from the live server")
    ap.add_argument("--base", default="http://127.0.0.1:8765", help="the live server --capture reads (default %(default)s)")
    ap.add_argument("--json", action="store_true", help="print the report(s) as JSON")
    ap.add_argument("--verbose", action="store_true", help="print warnings on a passing run too")
    a = ap.parse_args(argv)
    if a.capture:
        return capture(a.base)
    if a.all:
        files = sorted(os.path.join(WIDGETS, n) for n in os.listdir(WIDGETS) if n.endswith(".js"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            reps = list(pool.map(run_one, files))
        if a.json:
            print(json.dumps(reps, indent=1))
        else:
            for r in reps:
                print(one_line(r))
                if a.verbose and r["ok"]:
                    for w in r["warnings"]:
                        print("       warning: %s" % w)
        bad = [r for r in reps if not r["ok"]]
        if not a.json:
            print("harness: %d of %d widgets hold%s" % (len(reps) - len(bad), len(reps),
                                                   (" -- failing: " + ", ".join(r["id"] for r in bad)) if bad else ""))
        if any(r["fatal"] for r in reps):
            return 2
        return 1 if bad else 0
    if not a.file:
        ap.error("name a widget file, or pass --all or --capture")
    rep = run_one(a.file)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        full(rep, a.verbose)
    return 2 if rep["fatal"] else (0 if rep["ok"] else 1)


# ---- the Node side: the real page in jsdom, the network answered from fixtures ----
NODE_JS = r"""
const fs = require("fs"), path = require("path");
const C = JSON.parse(process.env.BV_HARNESS);
const { JSDOM, VirtualConsole, requestInterceptor } = require(path.join(C.viewer, "node_modules", "jsdom"));
const R = { errors: [], broken: [], missing: [], unbound: [], warnings: [], requested: [] };
let PHASE = "mount", PENDING = 0, LAST = Date.now();
const ORIGIN = "http://127.0.0.1:8765";
const TYPES = { ".js": "application/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png",
                ".svg": "image/svg+xml", ".html": "text/html" };
const note = (list, v) => { if (list.indexOf(v) < 0) list.push(v); };
const err = (phase, e) => {
  const message = String((e && e.message) || e || "error").split("\n")[0];
  if (!R.errors.some(x => x.message === message)) R.errors.push({ phase, message, stack: String((e && e.stack) || "").split("\n").slice(0, 10).join("\n") });
};
const fixtureFile = p => path.join(C.fixtures, p.replace(/^\/api\//, "").replace(/\//g, "-") + ".json");

// the page's own markup, scripts and all
const html = fs.readFileSync(path.join(C.viewer, "home.html"), "utf8");

const vc = new VirtualConsole();
vc.on("jsdomError", e => {
  if (e.type === "not-implemented") { note(R.warnings, "jsdom does not implement: " + String(e.message).slice(0, 120)); return; }
  if (e.type === "css-parsing") return;
  if (e.type === "resource-loading") { note(R.warnings, "a resource did not load: " + (e.url || e.message)); return; }
  err(PHASE, e.cause || e);
});
vc.on("error", (...a) => note(R.warnings, "console.error: " + a.map(String).join(" ").slice(0, 200)));
process.on("unhandledRejection", e => err(PHASE + " (unhandled promise)", e));
process.on("uncaughtException", e => err(PHASE + " (uncaught)", e));

function staticResponse(u) {
  const rel = decodeURIComponent(u.pathname.slice("/static/".length));
  // the widget under test is served from wherever it is, so a draft outside the folder can be checked before it goes live
  const file = rel === "widgets/" + path.basename(C.file) ? C.file : path.join(C.viewer, rel);
  if ((file !== C.file && !file.startsWith(C.viewer)) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    note(R.warnings, "no static file " + u.pathname);
    return new Response("", { status: 404 });
  }
  return new Response(fs.readFileSync(file), { status: 200, headers: { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" } });
}

function install(w) {
  // ---- the network: every /api/ read from a fixture, the board itself made up to hold the one widget ----
  w.fetch = async (input, init) => {
    const u = new URL(typeof input === "string" ? input : input.url, ORIGIN);
    const method = String((init && init.method) || "GET").toUpperCase();
    PENDING++; LAST = Date.now();
    try {
      await new Promise(r => setTimeout(r, 5));
      const json = (body, status) => new Response(JSON.stringify(body), { status: status || 200, headers: { "Content-Type": "application/json" } });
      if (u.pathname.startsWith("/static/")) return staticResponse(u);
      if (u.pathname === "/api/widgets") {
        const file = path.basename(C.file);
        return json({ folder: "skills/brain-viewer/widgets", count: 1, widgets: [{ id: C.id, file, url: "/static/widgets/" + file }] });
      }
      if (u.pathname === "/api/home/layout") {
        if (method !== "GET") return json({ ok: true, saved: true });
        let d = {};
        try { d = w.eval("(REG.get(" + JSON.stringify(C.id) + ") || {})") || {}; } catch (e) {}
        return json({ schema: "brain-viewer-home-layout/1", member: "zak", saved: true, error: null, sizes: ["4", "6", "8", "12"], rows: [1, 2],
                      widgets: [{ id: C.id, on: true, size: d.size || "12", rows: d.rows === 2 ? 2 : 1, collapsed: false, expanded: false, settings: {} }], palette: null });
      }
      if (u.pathname === "/api/widgets/broken") {
        let b = {}; try { b = JSON.parse((init && init.body) || "{}"); } catch (e) {}
        R.broken.push({ where: b.where, error: b.error, phase: PHASE });
        return json({ ok: true });
      }
      if (method !== "GET") {
        note(R.warnings, "the widget wrote: " + method + " " + u.pathname);
        return json({ ok: true });
      }
      if (!u.pathname.startsWith("/api/")) return new Response("", { status: 200 });
      note(R.requested, u.pathname);
      const f = fixtureFile(u.pathname);
      if (!fs.existsSync(f)) { note(R.missing, u.pathname); return json({ error: "no fixture for " + u.pathname }, 404); }
      return new Response(fs.readFileSync(f), { status: 200, headers: { "Content-Type": "application/json" } });
    } finally { PENDING--; LAST = Date.now(); }
  };
  // ---- what a browser has and jsdom does not ----
  w.EventSource = class { constructor(url) { this.url = url; this.readyState = 1; note(R.requested, String(url).split("?")[0] + " (stream)"); }
                          addEventListener() {} removeEventListener() {} close() { this.readyState = 2; } };
  w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  w.IntersectionObserver = class { constructor(cb) { this.cb = cb; } observe(el) { const cb = this.cb; setTimeout(() => { try { cb([{ target: el, isIntersecting: true, intersectionRatio: 1 }], this); } catch (e) { err(PHASE, e); } }, 0); } unobserve() {} disconnect() {} };
  w.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} });
  w.scrollTo = () => {}; w.scrollBy = () => {};
  w.Element.prototype.scrollIntoView = function () {};
  w.Element.prototype.setPointerCapture = function () {};
  // a room to draw into: jsdom lays nothing out, so every width would be 0 and every drawing NaN
  const W = 960, H = 320;
  for (const [k, v] of [["clientWidth", W], ["offsetWidth", W], ["clientHeight", H], ["offsetHeight", H], ["scrollHeight", H]])
    Object.defineProperty(w.HTMLElement.prototype, k, { configurable: true, get() { return v; } });
  w.Element.prototype.getBoundingClientRect = function () { return { x: 0, y: 0, left: 0, top: 0, width: W, height: H, right: W, bottom: H, toJSON() {} }; };
  if (w.SVGElement) w.SVGElement.prototype.getBBox = function () { return { x: 0, y: 0, width: 100, height: 20 }; };
  if (w.SVGElement) w.SVGElement.prototype.getTotalLength = function () { return 100; };
  if (w.SVGElement) w.SVGElement.prototype.getPointAtLength = function () { return { x: 0, y: 0 }; };
  // a canvas that takes every call and draws nothing
  const ctx = new Proxy({}, { get(t, k) { if (k in t) return t[k]; if (k === "measureText") return () => ({ width: 10 }); if (k === "canvas") return undefined;
                                          if (k === "getImageData" || k === "createImageData") return () => ({ data: new Uint8ClampedArray(4) });
                                          if (/^create/.test(String(k))) return () => ({ addColorStop() {} });
                                          return function () {}; },
                              set(t, k, v) { t[k] = v; return true; } });
  w.HTMLCanvasElement.prototype.getContext = function () { return ctx; };
  w.HTMLCanvasElement.prototype.toDataURL = function () { return ""; };
  w.onerror = null;
  w.addEventListener("error", e => { err(PHASE, e.error || e.message); });
  w.addEventListener("unhandledrejection", e => { err(PHASE + " (unhandled promise)", e.reason); });
}

async function settle() {
  const t0 = Date.now();
  for (;;) {
    await new Promise(r => setTimeout(r, 40));
    if (!PENDING && Date.now() - LAST > C.settleMs) return;
    if (Date.now() - t0 > C.maxMs) { note(R.warnings, "the page was still reading after " + C.maxMs + " ms in " + PHASE); return; }
  }
}

const PLACEHOLDER = /\bundefined\b|\bNaN\b|\[object Object\]|\{\{|\$\{|^\s*null\s*$/;
const LOADING = /^\s*(loading|reading)\b[^]{0,30}$/i;
function inspect(w) {
  const d = w.document;
  let registered = false;
  try { registered = !!w.eval("REG.has(" + JSON.stringify(C.id) + ")"); } catch (e) {}
  if (!registered) {
    const ids = (() => { try { return w.eval("Array.from(REG.keys())"); } catch (e) { return []; } })();
    err("register", new Error("the file did not register id \"" + C.id + "\"" + (ids.length ? " (it registered " + ids.join(", ") + ")" : "")));
    return;
  }
  const tile = d.querySelector('section.w[data-w="' + C.id + '"]');
  if (!tile) { err("render", new Error("the board drew no tile for " + C.id)); return; }
  const status = (d.querySelector("#status") || {}).textContent || "";
  if (/did not load|could not/.test(status)) err("boot", new Error(status));
  if (tile.classList.contains("wbroken") && !R.broken.length) {
    const say = tile.querySelector(".wbroke-say");
    R.broken.push({ where: "tile", error: say ? say.textContent : "red-edged", phase: PHASE });
  }
  if (tile.classList.contains("whidden")) { note(R.warnings, "it hid itself (api.show(false)) against these fixtures"); return; }
  const body = tile.querySelector(".wbody");
  if (!body) return;
  if (!body.children.length && !body.textContent.trim()) R.unbound.push("the body stayed empty and the widget did not hide itself");
  const walker = d.createTreeWalker(body, w.NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = n.nodeValue;
    if (!t.trim()) continue;
    const host = n.parentElement;
    if (host && /^(SCRIPT|STYLE|TEXTAREA)$/.test(host.tagName)) continue;
    if (PLACEHOLDER.test(t)) note(R.unbound, "text still holds a placeholder: \"" + t.trim().slice(0, 80) + "\" in <" + host.tagName.toLowerCase() + ">");
    else if (LOADING.test(t)) note(R.unbound, "a loading line was left standing: \"" + t.trim().slice(0, 60) + "\"");
  }
  for (const el of body.querySelectorAll("*")) {
    for (const a of Array.from(el.attributes)) {
      if (a.name === "style" || a.name === "class") continue;
      if (/\bNaN\b|\bundefined\b|\[object Object\]/.test(a.value)) note(R.unbound, "attribute " + a.name + " on <" + el.tagName.toLowerCase() + "> holds \"" + a.value.slice(0, 60) + "\"");
    }
    const hook = Array.from(el.attributes).find(a => a.name.startsWith("data-"));
    if (hook && !el.children.length && !el.textContent.trim() && !el.hidden
        && !/^(INPUT|TEXTAREA|CANVAS|IMG|BUTTON|BR|HR|SELECT|IFRAME|svg|SVG|path|circle|line|rect|g)$/.test(el.tagName))
      note(R.warnings, "an empty " + hook.name + " hook on <" + el.tagName.toLowerCase() + ">");
  }
}

(async () => {
  let dom;
  try {
    dom = new JSDOM(html, {
      url: ORIGIN + "/", runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc,
      resources: { interceptors: [requestInterceptor(req => {
        const u = new URL(req.url);
        if (u.origin === ORIGIN && u.pathname.startsWith("/static/")) return staticResponse(u);
        return new Response("", { status: 200 });   // fonts, favicons, anything off this machine: nothing, quietly
      })] },
      beforeParse: install,
    });
  } catch (e) { err("setup", e); }
  if (dom) {
    const w = dom.window;
    await new Promise(r => { if (w.document.readyState === "complete") r(); else w.addEventListener("load", r); });
    PHASE = "mount"; await settle();
    PHASE = "refresh";
    try { w.eval("refreshAll()"); } catch (e) { err("refresh", e); }
    await settle();
    PHASE = "resize";
    try {
      const has = w.eval("(() => { const m = MOUNTED.get(" + JSON.stringify(C.id) + "); return !!(m && typeof m.w.resize === 'function'); })()");
      if (has) w.eval("(() => { const m = MOUNTED.get(" + JSON.stringify(C.id) + "); return m.w.resize.call(m.w, m.api.el, m.api); })()");
    } catch (e) { err("resize", e); }
    await settle();
    PHASE = "inspect";
    try { inspect(w); } catch (e) { err("inspect", e); }
    try { w.close(); } catch (e) {}
  }
  process.stdout.write("BVH " + JSON.stringify(R) + "\n", () => process.exit(0));
})();
"""


if __name__ == "__main__":
    sys.exit(main())
