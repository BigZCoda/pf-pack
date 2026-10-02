#!/usr/bin/env python
"""md.test.py -- the shared markdown renderer BV.md() in viewer-common.js (ledger T-0247), run in jsdom.

  python skills/brain-viewer/md.test.py

Claims:
  1. a numbered list with a blank line between items renders ONE <ol> with three <li> (it used to be three <ol>, all "1.").
  2. a tight list renders exactly as before (one <ul>, three <li>, no stray tags).
  3. a list followed by a paragraph after a blank line closes before the paragraph.
  4. an ordered list that starts at 4 carries start="4"; one that starts at 1 carries no start.
  5. a <ul> nested inside an <ol> opens and closes inside it, and the outer list keeps going after it.
  6. checkbox items still read as the box glyphs.
  7. two blank lines end a list; a bullet after a numbered list (blank line between) is its own list.
  8. an indented line under an item is part of that item, so the numbering does not restart after it.
  9. the Owen questions file renders one <ol> with six items; the 9/21 team prep (tight bullets) renders byte for byte
     as the renderer at git HEAD rendered it, when HEAD's copy can be read.

Exit 0 when every claim holds, 1 when one fails, 2 when node or jsdom is missing.
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.abspath(os.path.join(HERE, "..", ".."))
OWEN = "deliverables/owen-starter-brain-questions-2026-09-23.md"
TEAM = "deliverables/call-prep/team-call-prep-2026-09-21.md"

CASES = {
    "loose": "1. one\n\n2. two\n\n3. three\n",
    "tight": "- a\n- b\n- c\n",
    "then_para": "1. one\n2. two\n\nA paragraph after.\n",
    "start4": "4. four\n\n5. five\n",
    "start1": "1. one\n2. two\n",
    "nested": "1. one\n   - sub a\n   - sub b\n2. two\n",
    "boxes": "- [ ] open\n- [x] done\n",
    "two_blanks": "1. one\n\n\n2. two\n",
    "kind_change": "1. one\n\n- bullet\n",
    "continued": "1. one\n   more about one\n\n2. two\n",
    # transcript line references (T-0284): the five 0.50.1 shapes, then a reference before a " ·" and before a cell's "|"
    "lref_old": "at L726, he said it (L612) and the rest (see 7/24, L257) and L798 to L819 here <!-- agent -->\n- [ ] keep\n",
    "lref_dot": "Mike, 7/24 L524 · superseded 2026-09-21\n",
    "lref_mid": "Mike, 7/24 · L524 · superseded\n",
    "lref_bar": "| a | b |\n|---|---|\n| x | 7/24 verbatim L524 |\n| y | L524 · superseded |\n",
}

NODE_SCRIPT = r"""
const fs = require("fs"), path = require("path");
const [viewer, commonPath, casesPath, headPath] = process.argv.slice(2);
const { JSDOM } = require(path.join(viewer, "node_modules", "jsdom"));
function load(src) {
  const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://127.0.0.1/", runScripts: "outside-only", pretendToBeVisual: true });
  dom.window.fetch = () => Promise.reject(new Error("no network in the test"));
  dom.window.eval(src);
  return dom.window.BV;
}
const cases = JSON.parse(fs.readFileSync(casesPath, "utf8"));
const now = load(fs.readFileSync(commonPath, "utf8"));
const out = { now: {}, head: {} };
for (const [k, v] of Object.entries(cases)) out.now[k] = now.md(v);
if (headPath) { try { const head = load(fs.readFileSync(headPath, "utf8")); for (const k of ["team"]) out.head[k] = head.md(cases[k]); } catch (e) { out.headError = String(e); } }
process.stdout.write(JSON.stringify(out));
"""

FAILS = []


def claim(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        FAILS.append(what)


def main():
    node = shutil.which("node")
    if not node or not os.path.isdir(os.path.join(HERE, "node_modules", "jsdom")):
        print("md.test: node or jsdom is missing (npm install under skills/brain-viewer)")
        return 2
    scratch = os.path.join(HERE, "__pycache__", "md-test")
    os.makedirs(scratch, exist_ok=True)
    cases = dict(CASES)
    for key, rel in (("owen", OWEN), ("team", TEAM)):
        p = os.path.join(BRAIN, rel.replace("/", os.sep))
        if os.path.isfile(p):
            cases[key] = open(p, encoding="utf-8").read()
    cp, sp, hp = (os.path.join(scratch, n) for n in ("cases.json", "run.js", "head-viewer-common.js"))
    json.dump(cases, open(cp, "w", encoding="utf-8"))
    open(sp, "w", encoding="utf-8").write(NODE_SCRIPT)
    head = subprocess.run(["git", "show", "HEAD:skills/brain-viewer/viewer-common.js"], cwd=BRAIN,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    have_head = head.returncode == 0
    if have_head:
        open(hp, "wb").write(head.stdout)
    r = subprocess.run([node, sp, HERE, os.path.join(HERE, "viewer-common.js"), cp] + ([hp] if have_head else []),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if r.returncode != 0:
        print(r.stderr.decode("utf-8", "replace"))
        return 2
    res = json.loads(r.stdout.decode("utf-8"))
    now = res["now"]
    c = lambda k, tag: now[k].count(tag)

    claim(c("loose", "<ol") == 1 and c("loose", "<li>") == 3, "a loose numbered list is one <ol> with three <li>")
    claim(now["tight"] == "<ul>\n<li>a</li>\n<li>b</li>\n<li>c</li>\n</ul>", "a tight list renders as before: " + now["tight"].replace("\n", ""))
    t = now["then_para"]
    claim(c("then_para", "<ol") == 1 and t.index("</ol>") < t.index("<p>"), "a list followed by a paragraph closes before it")
    claim('<ol start="4">' in now["start4"] and c("start4", "<li>") == 2, 'a list starting at 4 carries start="4"')
    claim("start=" not in now["start1"], "a list starting at 1 carries no start")
    n = now["nested"]
    claim(c("nested", "<ol") == 1 and c("nested", "<ul>") == 1 and n.index("<ol") < n.index("<ul>") < n.index("</ul>") < n.index("</ol>")
          and n.index("</ul>") < n.index("two"), "a <ul> nests inside the <ol> and the <ol> continues after it")
    claim("☐ open" in now["boxes"] and "☑ done" in now["boxes"], "checkbox items keep their glyphs")
    claim(c("two_blanks", "<ol") == 2, "two blank lines end a list")
    claim(c("kind_change", "<ol") == 1 and c("kind_change", "<ul>") == 1, "a bullet after a numbered list is its own list")
    claim(c("continued", "<ol") == 1 and "one<br>more about one" in now["continued"], "an indented line under an item stays in that item")
    lo = now["lref_old"]
    claim(not re.search(r"L\d", lo) and "agent" not in lo and "at," not in lo and "☐ keep" in lo and "he said it and the rest (see 7/24) and here" in lo,
          "the five 0.50.1 line-reference shapes still go and leave the line whole: " + lo.replace("\n", ""))
    claim("L524" not in now["lref_dot"] and "Mike, 7/24 · superseded 2026-09-21" in now["lref_dot"],
          'a reference before a " ·" goes: ' + now["lref_dot"].strip())
    claim("L524" not in now["lref_mid"] and "Mike, 7/24 · superseded" in now["lref_mid"],
          'a " ·" in front of a reference goes with it: ' + now["lref_mid"].strip())
    lb = now["lref_bar"]
    claim("L524" not in lb and "7/24 verbatim</td>" in lb and "<td>superseded</td>" in lb,
          'a reference before a cell\'s bar, or opening a cell before a " ·", goes: ' + lb.replace("\n", ""))
    if "owen" in now:
        o = now["owen"]
        claim(c("owen", "<ol") == 1 and o.count("<li>") == 6, "the Owen questions file is one <ol> with six items (%d <ol>, %d <li>)" % (c("owen", "<ol"), o.count("<li>")))
    if "team" in res.get("head", {}):
        claim(now["team"] == res["head"]["team"], "the 9/21 team prep renders exactly as the renderer at HEAD rendered it")
    elif have_head:
        claim(False, "HEAD's renderer could not be run: " + res.get("headError", "?"))
    print("-" * 72)
    print("md.test: all checks pass" if not FAILS else "md.test: %d FAILED" % len(FAILS))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
