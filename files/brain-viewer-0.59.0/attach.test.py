#!/usr/bin/env python3
"""attach.test.py -- pictures attached to a question or an answer (viewer T-0219), checked end to end.

  python skills/brain-viewer/attach.test.py

A scratch brain is made in a temporary folder (`serve.py --init`), one question is asked on its ledger through tasks.py,
and a second copy of the server is started on a free port reading that folder. Nothing touches the real brain, its
ledgers or the viewer already running on 8765.

1. POST /api/attach refuses a ledger the registry does not name, an item the ledger does not hold, and bytes that are
   not a picture (a text file named .png), each with 400 and nothing written.
2. A real png lands in <ledger folder>/attachments/<id>-<yyyymmdd-hhmmss>-<name>.png, the item's `→ links` carries
   that path (a second upload is added after it, never in place of it), and GET /api/image serves the stored bytes.
3. attach.js, run in node, turns a linked image path into a thumbnail that opens in the lightbox (data-img plus an
   /api/image source), leaves a document link and a route alone, and reads the card ids the shared renderer writes.

Exit 0 when all three hold; 1 with the failure named otherwise.
"""

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(os.path.dirname(HERE))
SERVE = os.path.join(HERE, "serve.py")
TASKS = os.path.join(CODE, "skills", "brain-tasks", "tasks.py")
ATTACH_JS = os.path.join(HERE, "attach.js")
# the smallest valid png: one transparent pixel
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")

FAILS = []


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(what)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def post(port, path, body):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=json.dumps(body).encode("utf-8"),
                                 method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def get(port, path):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def server_part(tmp):
    brain = os.path.join(tmp, "attachtest")
    env = dict(os.environ, BRAIN_ROOT=brain, PYTHONIOENCODING="utf-8")
    port = free_port()
    log = open(os.path.join(tmp, "serve.out"), "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, SERVE, "--brain", brain, "--init", "--port", str(port)],
                            cwd=tmp, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        up = False
        for _ in range(150):
            if proc.poll() is not None:
                break
            try:
                if get(port, "/api/projects")[0] == 200:
                    up = True
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not up:
            log.close()
            with open(os.path.join(tmp, "serve.out"), encoding="utf-8", errors="replace") as f:
                check(False, "the scratch server starts", f.read()[-600:])
            return
        with open(os.path.join(brain, "context", "holon-registry.json"), encoding="utf-8-sig") as f:
            row = next(h for h in json.load(f)["holons"] if h.get("tasks"))
        pid, led = row["id"], row["tasks"]
        r = subprocess.run([sys.executable, TASKS, "ask", "--project", pid, "--to", "@zak", "--text", "Which of these two covers?"],
                           cwd=brain, env=env, capture_output=True, text=True, timeout=60)
        m = re.search(r"Q-\d{4}", r.stdout + r.stderr)
        check(r.returncode == 0 and bool(m), "a question is asked on the scratch ledger", (r.stdout + r.stderr).strip()[:200])
        if not m:
            return
        qid = m.group(0)
        folder = os.path.join(brain, os.path.dirname(led), "attachments")
        b64 = base64.b64encode(PNG).decode("ascii")

        # --- 1. the refusals ---------------------------------------------------------
        code, j = post(port, "/api/attach", {"ledger": "no-such-project", "item": qid, "name": "x.png", "data": b64})
        check(code == 400 and "registered ledger" in j.get("error", ""), "an unknown ledger is refused", "%s %s" % (code, j.get("error")))
        code, j = post(port, "/api/attach", {"ledger": led, "item": "Q-9999", "name": "x.png", "data": b64})
        check(code == 400 and "Q-9999" in j.get("error", ""), "an unknown item is refused", "%s %s" % (code, j.get("error")))
        text = base64.b64encode(b"just some words, not a picture").decode("ascii")
        code, j = post(port, "/api/attach", {"ledger": led, "item": qid, "name": "fake.png", "data": text})
        check(code == 400 and "picture" in j.get("error", ""), "a non-image named .png is refused", "%s %s" % (code, j.get("error")))
        check(not os.path.isdir(folder) or not os.listdir(folder), "nothing was written by a refusal")

        # --- 2. a valid upload -------------------------------------------------------
        code, j = post(port, "/api/attach", {"ledger": led, "item": qid, "name": "Cover Option A.png", "data": b64})
        stored = j.get("path", "")
        want = re.compile(r"^%s/attachments/%s-\d{8}-\d{6}-cover-option-a\.png$" % (re.escape(os.path.dirname(led)), qid))
        check(code == 200 and bool(want.match(stored)), "a valid upload lands next to its ledger", "%s %s" % (code, stored or j))
        ap = os.path.join(brain, stored.replace("/", os.sep))
        check(os.path.isfile(ap) and open(ap, "rb").read() == PNG, "the stored bytes are the picture sent", stored)
        with open(os.path.join(brain, led.replace("/", os.sep)), encoding="utf-8") as f:
            line = next((l for l in f.read().splitlines() if (" %s " % qid) in l), "")
        check(("→ %s" % stored) in line, "the item's link carries the stored path", line.strip()[:200])
        code2, j2 = post(port, "/api/attach", {"ledger": pid, "item": qid, "name": "b.gif",
                                               "data": base64.b64encode(b"GIF89a" + b"\x00" * 20).decode("ascii")})
        check(code2 == 200 and j2.get("links") == [stored, j2.get("path")] and j2.get("path", "").endswith(".gif"),
              "a second picture is added after the first, by holon id, typed by its bytes", "%s %s" % (code2, j2.get("links")))
        code3, blob = get(port, "/api/image?path=" + urllib.request.quote(stored))
        check(code3 == 200 and blob == PNG, "GET /api/image serves the attachment", str(code3))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        log.close()


def render_part():
    node = shutil.which("node")
    if not node:
        check(False, "node is on the path (needed for the render check)")
        return
    script = r"""
const A = require(process.argv[1]);
const links = ["brain-viewer-holon/attachments/Q-0026-20260922-101500-clip.png", "deliverables/x.md", "/glossary",
               "[[references/cover.JPG]]", "https://example.com/a.png"];
const html = A.thumbs(links);
const imgs = html.match(/<img [^>]*>/g) || [];
const out = {
  paths: A.imageLinks(links),
  count: imgs.length,
  first: imgs[0] || "",
  empty: A.thumbs(["deliverables/x.md"]),
  card: A.parseCardId("q-pf-build-Q-0026"),
  row: A.parseCardId("t-brain-viewer-holon-T-0219"),
  none: A.parseCardId("drawer"),
  due: A.parseCardId("due-q-brain-central-Q-0041"),
  control: A.control(),
};
process.stdout.write(JSON.stringify(out));
"""
    r = subprocess.run([node, "-e", script, ATTACH_JS], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout)
    except Exception:
        check(False, "attach.js runs in node", (r.stdout + r.stderr).strip()[:300])
        return
    check(o["paths"] == ["brain-viewer-holon/attachments/Q-0026-20260922-101500-clip.png", "references/cover.JPG"],
          "only brain image paths are thumbnails (a doc, a route and a web address are not)", str(o["paths"]))
    first = o["first"]
    check(o["count"] == 2 and 'data-img="brain-viewer-holon/attachments/Q-0026-20260922-101500-clip.png"' in first
          and 'src="/api/image?path=brain-viewer-holon%2Fattachments%2FQ-0026-20260922-101500-clip.png"' in first,
          "a linked image renders as a thumbnail that opens in the lightbox", first[:160])
    check(o["empty"] == '<div class="att-thumbs"></div>', "an item with no picture draws an empty strip", o["empty"])
    check(o["card"] == {"kind": "question", "ledger": "pf-build", "item": "Q-0026"}
          and o["row"] == {"kind": "task", "ledger": "brain-viewer-holon", "item": "T-0219"} and o["none"] is None
          and o["due"] == {"kind": "question", "ledger": "brain-central", "item": "Q-0041"},
          "the card ids the shared renderer writes are read back", "%s %s" % (o["card"], o["row"]))
    check("data-attach" in o["control"], "the attach control carries its hook", o["control"][:80])


def main():
    tmp = tempfile.mkdtemp(prefix="bv-attach-")
    try:
        server_part(tmp)
        render_part()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%d failure(s)" % len(FAILS) if FAILS else "all hold")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
