#!/usr/bin/env python3
"""derive_day.py -- the day drawing, derived from a declared manifest, never drawn by hand (viewer 0.67.0).

  python skills/brain-viewer/derive_day.py            write the drawing and print the check
  python skills/brain-viewer/derive_day.py --check    print the check only, write nothing
  python skills/brain-viewer/derive_day.py --json     the check as JSON (for a caller such as brain-lint)

WHY. The hand-drawn day drawing of 2026-09-09 went stale inside eight days: it said the chat was the home page, pointed at
a dropped recap step, showed the night agent filing to deliverables, and lacked Today, the viewer hook, the answers inbox,
the safety commit, threads and the call screen (the 10/06 viewer review, finding 6). The viewer's first rule is "derived,
never drawn" (brain-viewer-holon/brain-viewer-rules.md rule 1), and the review's addendum says the fix is to derive this
drawing, not to redraw it. So the parts of the day are DECLARED once, in skills/brain-viewer/day-manifest.json (each part
with its name, its kind, what it points at and which cell it belongs to), and this script draws from that.

WHAT IT WRITES (and nothing else):
  * projects/pf-build/architecture/womb-phase/daily-workflow-cells.canvas, overwritten whole: four cells (start, work,
    inbound, close), each with an outer band (what the owner sees) and an inner layer (what runs), one tile per part, the
    declared flows as labelled lines, and each part's outline coloured by its state today (green working, ochre
    building, dashed grey not built or quiet). Obsidian reads it as an ordinary canvas.
  * its sibling .forge.json, MERGED: each part's binding (kind, target) so the Forge's live mode binds exactly what the
    manifest declares; any other row the Forge wrote (an output's angle, a placed part) is kept.
  * one log line through skills/brain-log/log.py, only when the canvas changed.

HOW IT LIGHTS A PART. The same way the live layer does (serve.py live_binding + live_activity over the last
serve.LIVE_DAYS days of context/log.md): a part with `light` uses that binding; otherwise its `points` becomes the
binding (route -> route, skill -> skill, file -> file or folder, task -> the agent heartbeat.py names for it); a part
with only a `match` pattern is lit by the log lines that pattern finds.

THE ROT CHECK. Printed every run, one line per finding:
    GONE   <part> -> <type> <target>: <why>     the thing it points at no longer exists (a route not served or folded
                                                into another, a skill folder gone, a file gone, a scheduled task not in
                                                heartbeat.py, a hook file missing or no longer registered in
                                                ~/.claude/settings.json, a slash command gone)
    QUIET  <part> -> <type> <target>: nothing in <N> days
and a last line `day-drawing check: <parts> parts, <gone> gone, <quiet> quiet`. Exit 0 always (it reports, it does not
gate) unless the manifest cannot be read (2).

HOW BRAIN-LINT CAN CALL IT. A lint check (say L19) runs `python skills/brain-viewer/derive_day.py --check --json` from
the brain root and reads {"parts", "gone": [{part, type, target, why}], "quiet": [{part, type, target, days}]}:
each `gone` row is a finding to file (key `L19:<part>`), and `quiet` rows are reported, not filed, since a part can be
quiet for a fortnight and still be right. --check writes nothing, so it is safe at rounds step 7b.
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("BRAIN_HEADLESS_CHILD", "1")
import serve  # noqa: E402

BRAIN = serve.BRAIN
MANIFEST_REL = "skills/brain-viewer/day-manifest.json"
CANVAS_REL = "projects/pf-build/architecture/womb-phase/daily-workflow-cells.canvas"
HOME = os.path.expanduser("~")
HOOKS_DIR = os.path.join(HOME, ".claude", "hooks")
COMMANDS_DIR = os.path.join(HOME, ".claude", "commands")
SETTINGS_JSON = os.path.join(HOME, ".claude", "settings.json")

# the canvas palette: 3 band, 5 inner, 6 cell, 4 working (green), 2 building (orange), none for the rest
COLOR = {"working": "4", "building": "2"}
TILE_W, TILE_H, GAP, COLS = 360, 230, 30, 3


def heartbeat_tasks():
    try:
        sys.path.insert(0, os.path.join(BRAIN, "skills", "dispatcher"))
        import heartbeat  # noqa: E402
        return {t["id"]: t for t in heartbeat.TASKS}
    except Exception:                                             # noqa: BLE001
        return {}


def registered_hooks():
    """Every command string the settings register under any hook event."""
    try:
        with open(SETTINGS_JSON, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for rows in (d.get("hooks") or {}).values():
        for r in rows or []:
            out += [str(h.get("command") or "") for h in r.get("hooks") or []]
    return out


def exists(points, tasks, hooks):
    """(True, "") when what a part points at exists, else (False, why)."""
    t, at = points.get("type"), str(points.get("at") or "")
    if t == "route":
        if at in serve.PAGES:
            return True, ""
        if at in getattr(serve, "REDIRECT_ROUTES", ()):
            return False, "folded: the route now redirects"
        return False, "not a page the viewer serves"
    if t == "skill":
        return (True, "") if os.path.isdir(os.path.join(BRAIN, "skills", at)) else (False, "no folder skills/%s/" % at)
    if t == "file":
        ap = os.path.join(BRAIN, at.rstrip("/").replace("/", os.sep))
        ok = os.path.isdir(ap) if at.endswith("/") else os.path.isfile(ap)
        return (True, "") if ok else (False, "no such %s" % ("folder" if at.endswith("/") else "file"))
    if t == "task":
        return (True, "") if at in tasks else (False, "not a scheduled task in skills/dispatcher/heartbeat.py")
    if t == "hook":
        if not os.path.isfile(os.path.join(HOOKS_DIR, at)):
            return False, "no file ~/.claude/hooks/%s" % at
        if not any(at in c for c in hooks):
            return False, "not registered in ~/.claude/settings.json"
        return True, ""
    if t == "command":
        return (True, "") if os.path.isfile(os.path.join(COMMANDS_DIR, at + ".md")) else (False, "no ~/.claude/commands/%s.md" % at)
    return False, "unknown points.type %r" % t


def binding_for(part, names, tasks):
    """The live-layer binding for a part: its light, else its points, else None (lit by `match` alone)."""
    lt = part.get("light")
    if lt:
        return serve.live_binding(lt["kind"], lt["target"], names, "day manifest")
    p = part.get("points") or {}
    t, at = p.get("type"), str(p.get("at") or "")
    if t == "route":
        return serve.live_binding("route", at, names, "day manifest")
    if t == "skill":
        return serve.live_binding("skill", at, names, "day manifest")
    if t == "file":
        kind = "folder" if at.endswith("/") else ("canvas" if at.endswith(".canvas") else "file")
        return serve.live_binding(kind, at if kind != "folder" else at, names, "day manifest")
    if t == "task" and at in tasks:
        return serve.live_binding("agent", tasks[at]["agents"][0], names, "day manifest")
    return None


def activity(part, b, rows, today, leaves, ctx):
    """The live layer's activity for the binding, joined with the part's own log pattern when it has one."""
    a = serve.live_activity(b, rows, today, leaves, ctx) if b and b.get("kind") != "concept" else \
        {"count14": 0, "today": 0, "lastAt": None, "todayScore": 0, "active14": False}
    if part.get("match"):
        rx = re.compile(part["match"], re.I)
        since = (dt.date.today() - dt.timedelta(days=serve.LIVE_DAYS)).isoformat()
        hits = [r for r in rows if r["date"] >= since and rx.search(r.get("raw") or r["text"])]
        if hits:
            a = dict(a)
            a["count14"] = max(a["count14"], len(hits))
            a["today"] = max(a.get("today", 0), sum(1 for r in hits if r["date"] == today))
            a["todayScore"] = max(a["todayScore"], a["today"])
            a["active14"] = True
            a["lastAt"] = max(a.get("lastAt") or "", hits[-1]["at"]) or None
    return a


def tile_text(part, a, state):
    p = part["points"]
    where = {"route": "page", "skill": "skill", "file": "file", "task": "scheduled task", "hook": "hook",
             "command": "command"}.get(p["type"], p["type"])
    at = p["at"] if p["type"] != "command" else "/" + p["at"]
    if p["type"] == "skill":
        at = "skills/%s/" % p["at"]
    line = {"working": "working: %d in the log in %d days" % (a.get("count14", 0), serve.LIVE_DAYS),
            "building": "building: an open item links it",
            "not built": "not built: what it points at is gone",
            "quiet": "quiet: nothing in %d days" % serve.LIVE_DAYS}.get(state, "")
    return "**%s · %s**\n%s\n%s `%s`\n_%s_" % (part["kind"], part["name"], part["what"], where, at, line)


def layout(man, results):
    nodes, edges = [], []
    nodes.append({"id": "title", "type": "text", "x": 0, "y": -620, "width": 1700, "height": 260, "color": "6",
                  "text": "# The owner's day, as the brain runs it\nDerived, never drawn: `skills/brain-viewer/derive_day.py` draws this from "
                          "`skills/brain-viewer/day-manifest.json` (written from CLAUDE.md Section 5 and 5B, the dispatcher's rules, the "
                          "scheduled tasks, the registered hooks and the live pages). To change it, change the manifest and run the script. "
                          "Drawn %s." % dt.datetime.now().strftime("%Y-%m-%d %H:%M")})
    nodes.append({"id": "legend", "type": "text", "x": 1800, "y": -620, "width": 1000, "height": 260,
                  "text": "**How to read it**\nFour cells: the day starts with the recap, the work happens in the viewer, things arrive and are "
                          "sorted before the owner sees them, and the day closes overnight. Outer band: what the owner sees. Inner layer: what runs.\n\n"
                          "Outline: green working (the log named it in %d days), orange building (an open item links it), none quiet or not built. "
                          "Open it live in the Forge for today's activity." % serve.LIVE_DAYS})
    for ci, cell in enumerate(man["cells"]):
        x0 = cell["x"]
        outer = [r for r in results if r["part"]["cell"] == cell["id"] and r["part"]["band"] == "outer"]
        inner = [r for r in results if r["part"]["cell"] == cell["id"] and r["part"]["band"] != "outer"]
        rows_o = max(1, -(-len(outer) // COLS))
        rows_i = max(1, -(-len(inner) // COLS))
        band_h = 70 + rows_o * (TILE_H + GAP)
        inner_h = 70 + rows_i * (TILE_H + GAP)
        cell_h = 80 + band_h + 40 + inner_h + 40
        nodes.append({"id": "g_" + cell["id"], "type": "group", "x": x0, "y": -200, "width": 1300, "height": cell_h, "color": "6",
                      "label": "CELL %d · %s · %s" % (ci + 1, cell["name"].upper(), cell["what"])})
        nodes.append({"id": "g_%s_outer" % cell["id"], "type": "group", "x": x0 + 40, "y": -120, "width": 1220, "height": band_h,
                      "color": "3", "label": "outer band · what the owner sees"})
        y_in = -120 + band_h + 40
        nodes.append({"id": "g_%s_inner" % cell["id"], "type": "group", "x": x0 + 40, "y": y_in, "width": 1220, "height": inner_h,
                      "color": "5", "label": "inner layer · what runs"})
        for band_rows, top in ((outer, -120), (inner, y_in)):
            for i, r in enumerate(band_rows):
                col, row = i % COLS, i // COLS
                n = {"id": r["part"]["id"], "type": "text", "x": x0 + 80 + col * (TILE_W + 25), "y": top + 60 + row * (TILE_H + GAP),
                     "width": TILE_W, "height": TILE_H, "text": tile_text(r["part"], r["activity"], r["state"])}
                if r["state"] in COLOR:
                    n["color"] = COLOR[r["state"]]
                nodes.append(n)
    ids = {n["id"] for n in nodes}
    for i, (a, z, label) in enumerate(man.get("flows") or []):
        if a in ids and z in ids:
            edges.append({"id": "f%d" % (i + 1), "fromNode": a, "fromSide": "bottom", "toNode": z, "toSide": "top", "label": label})
    return {"nodes": nodes, "edges": edges}


def state_of(b, a, ok, links):
    if b:
        st, _ = serve.part_state(b, a, links)
    else:
        st = "working" if a.get("active14") else "quiet"
    if not ok:
        return "not built"
    return st if st != "not built" else ("working" if a.get("active14") else "quiet")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="print the check only; write nothing")
    ap.add_argument("--json", action="store_true", help="the check as JSON")
    args = ap.parse_args()
    try:
        with open(os.path.join(BRAIN, MANIFEST_REL.replace("/", os.sep)), "r", encoding="utf-8-sig") as f:
            man = json.load(f)
    except (OSError, ValueError) as e:
        print("derive_day: cannot read %s: %s" % (MANIFEST_REL, e))
        return 2
    tasks, hooks = heartbeat_tasks(), registered_hooks()
    names = serve.live_names()
    rows, _ = serve.log_rows()
    for r in rows:
        r.setdefault("raw", "[%s] [%s] %s %s" % (r.get("at"), r.get("agent"), r.get("action"), r.get("text")))
    today = dt.date.today().isoformat()
    leaves = serve.live_leaves()
    ctx = {"names": names, "sessions": serve.live_sessions_today(today), "team": None}
    try:
        links = serve.open_link_targets()
    except Exception:                                             # noqa: BLE001
        links = {}
    results, gone, quiet = [], [], []
    for part in man["parts"]:
        p = part["points"]
        ok, why = exists(p, tasks, hooks)
        b = binding_for(part, names, tasks)
        a = activity(part, b, rows, today, leaves, ctx)
        st = state_of(b, a, ok, links)
        results.append({"part": part, "ok": ok, "binding": b, "activity": a, "state": st})
        if not ok:
            gone.append({"part": part["id"], "type": p["type"], "target": p["at"], "why": why})
        elif not a.get("active14"):
            quiet.append({"part": part["id"], "type": p["type"], "target": p["at"], "days": serve.LIVE_DAYS})

    wrote = None
    if not args.check:
        doc = layout(man, results)
        body = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        cap = os.path.join(BRAIN, CANVAS_REL.replace("/", os.sep))
        old = open(cap, "r", encoding="utf-8").read() if os.path.isfile(cap) else ""
        strip = lambda t: re.sub(r"Drawn \d{4}-\d{2}-\d{2} \d{2}:\d{2}\.", "", t)
        if strip(old) != strip(body):
            with open(cap, "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
            wrote = CANVAS_REL
        sib_rel = serve.forge_sibling(CANVAS_REL)
        sap = os.path.join(BRAIN, sib_rel.replace("/", os.sep))
        meta = {"_schema": "forge/1", "canvas": CANVAS_REL, "nodes": {}}
        if os.path.isfile(sap):
            try:
                with open(sap, "r", encoding="utf-8-sig") as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                pass
        meta.setdefault("nodes", {})
        meta["_note"] = ("forge/1. The bindings below are written by skills/brain-viewer/derive_day.py from "
                         "skills/brain-viewer/day-manifest.json; any other row is the Forge's own and is kept.")
        ids = {r["part"]["id"] for r in results}
        for nid in list(meta["nodes"]):
            if nid not in ids and not str(nid).startswith("g_"):
                meta["nodes"].pop(nid)                        # a part the manifest no longer declares
        for r in results:
            row = dict(meta["nodes"].get(r["part"]["id"]) or {})
            b = r["binding"]
            if b and b.get("kind") != "concept" and b.get("target"):
                row["binding"] = {"kind": b["kind"], "target": b["target"]}
            else:
                row.pop("binding", None)
            if row:
                meta["nodes"][r["part"]["id"]] = row
            else:
                meta["nodes"].pop(r["part"]["id"], None)
        sbody = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
        sold = open(sap, "r", encoding="utf-8").read() if os.path.isfile(sap) else ""
        if json.loads(sold or "{}").get("nodes") != meta["nodes"] or not sold:
            meta["_updated"] = dt.datetime.now().isoformat(timespec="seconds")
            with open(sap, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        if wrote:
            counts = {}
            for r in results:
                counts[r["state"]] = counts.get(r["state"], 0) + 1
            subprocess.run([sys.executable, os.path.join(BRAIN, "skills", "brain-log", "log.py"), "--append", "--agent", "derive-day",
                            "--action", "MODIFIED", "--text", "%s -- derived from %s: %d parts in %d cells (%s), %d lines"
                            % (CANVAS_REL, MANIFEST_REL, len(results), len(man["cells"]),
                               ", ".join("%d %s" % (v, k) for k, v in sorted(counts.items())), len(man.get("flows") or []))],
                           cwd=BRAIN, capture_output=True, text=True, timeout=30)

    if args.json:
        print(json.dumps({"parts": len(results), "gone": gone, "quiet": quiet, "wrote": wrote}, indent=2))
        return 0
    for g in gone:
        print("GONE   %s -> %s %s: %s" % (g["part"], g["type"], g["target"], g["why"]))
    for q in quiet:
        print("QUIET  %s -> %s %s: nothing in %d days" % (q["part"], q["type"], q["target"], q["days"]))
    if wrote:
        print("wrote  %s" % wrote)
    print("day-drawing check: %d parts, %d gone, %d quiet" % (len(results), len(gone), len(quiet)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
