#!/usr/bin/env python3
"""tasks-shared.test.py -- the computed facet `shared`: who a ledger item is shared with (2026-11-09, Brain Viewer 0.109.0).

Builds a scratch brain in a temp folder: a holon registry naming one ledger, that ledger with three items made through
the tool, a copy of skills/sharing/share.py, skills/team-brain/status.json = {"member": "riley"} and
skills/team-brain/shared-with-riley.json naming ONE of the three items. The real tasks.py runs as a subprocess with
BRAIN_ROOT pointing at the scratch brain, so no brain file is touched. One PASS / FAIL line per claim; exit 1 on any FAIL.

    python skills/brain-tasks/tasks-shared.test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PY = os.path.join(HERE, "tasks.py")
SHARE_PY = os.path.join(os.path.dirname(HERE), "sharing", "share.py")
HOLON = "test-holon"
LEDGER_REL = "test-holon/test-holon-tasks.md"

FAILS = []


def claim(ok, what):
    print("%s  %s" % ("PASS" if ok else "FAIL", what))
    if not ok:
        FAILS.append(what)


def put(brain, rel, text):
    path = os.path.join(brain, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def raw(brain, rel):
    with open(os.path.join(brain, *rel.split("/")), "rb") as f:
        return f.read()


def run(brain, *args):
    return subprocess.run([sys.executable, TASKS_PY] + list(args), cwd=brain, capture_output=True, text=True,
                          encoding="utf-8", timeout=120, env=dict(os.environ, BRAIN_ROOT=brain))


def items_of(out):
    return {i["id"]: i for led in json.loads(out) for i in led.get("items") or []}


def item_lines(out):
    return [l for l in out.splitlines() if l.startswith("  [")]


def main():
    brain = tempfile.mkdtemp(prefix="tasks-shared-")
    try:
        put(brain, "context/holon-registry.json", json.dumps({"holons": [
            {"id": HOLON, "name": "Test holon", "path": "test-holon/", "tasks": LEDGER_REL}]}))
        put(brain, "context/log.md", "# Log\n")
        r = run(brain, "init", "--project", HOLON, "--name", "Test holon")
        claim(r.returncode == 0, "init makes the scratch ledger (%s)" % (r.stderr.strip() or "ok"))
        for text in ("Write the first scratch note for the test", "Write the second scratch note for the test",
                     "Write the third scratch note for the test"):
            r = run(brain, "add", "--project", HOLON, "--owner", "@claude", "--text", text)
            claim(r.returncode == 0, "add makes an item (%s)" % (r.stdout.strip().splitlines() or [r.stderr.strip()])[0])
        os.makedirs(os.path.join(brain, "skills", "sharing"), exist_ok=True)
        shutil.copy(SHARE_PY, os.path.join(brain, "skills", "sharing", "share.py"))
        put(brain, "skills/team-brain/status.json", json.dumps({"member": "riley"}))
        put(brain, "skills/team-brain/shared-with-riley.json", json.dumps({"items": [
            {"project": HOLON, "ledger": LEDGER_REL, "id": "T-0002", "at": "2026-11-09T10:00:00"}], "threads": []}))
        before = raw(brain, LEDGER_REL)

        def same(what):
            claim(raw(brain, LEDGER_REL) == before, "the ledger's bytes are unchanged after %s" % what)

        r = run(brain, "list", "--project", HOLON, "--json")
        same("list --json")
        its = items_of(r.stdout) if r.returncode == 0 else {}
        claim(sorted(its) == ["T-0001", "T-0002", "T-0003"], "list --json carries the three items")
        claim(its.get("T-0002", {}).get("shared") == ["riley"], "T-0002 carries shared == [\"riley\"]")
        claim(its.get("T-0002", {}).get("shared_with") == ["Riley"], "T-0002 carries shared_with == [\"Riley\"]")
        claim(all(its.get(k, {}).get("shared") == [] and its.get(k, {}).get("shared_with") == [] for k in ("T-0001", "T-0003")),
              "T-0001 and T-0003 carry shared == [] and shared_with == []")

        r = run(brain, "list", "--project", HOLON)
        same("list")
        lines = item_lines(r.stdout)
        hit = [l for l in lines if "shared:riley" in l]
        claim(len(lines) == 3 and len(hit) == 1 and "T-0002" in hit[0], "the text list shows shared:riley on T-0002's line only")

        for want in ("riley", "Riley", "any"):
            r = run(brain, "list", "--project", HOLON, "--shared-with", want)
            same("list --shared-with %s" % want)
            lines = item_lines(r.stdout)
            claim(r.returncode == 0 and len(lines) == 1 and "T-0002" in lines[0], "--shared-with %s lists only T-0002 (text)" % want)
            r = run(brain, "list", "--project", HOLON, "--shared-with", want, "--json")
            same("list --shared-with %s --json" % want)
            led = json.loads(r.stdout)[0] if r.returncode == 0 else {}
            in_groups = [i["id"] for rows in (led.get("groups") or {}).values() for i in rows]
            claim([i["id"] for i in led.get("items") or []] == ["T-0002"] and in_groups == ["T-0002"],
                  "--shared-with %s returns only T-0002 (json items and groups)" % want)

        r = run(brain, "list", "--project", HOLON, "--shared-with", "nobody-here")
        same("list --shared-with nobody-here")
        claim(r.returncode == 2 and r.stdout == "" and "riley" in r.stderr and len(r.stderr.strip().splitlines()) == 1,
              "--shared-with nobody-here exits 2, stdout empty, one stderr line naming the spaces (%s)" % r.stderr.strip())

        os.remove(os.path.join(brain, "skills", "sharing", "share.py"))
        r = run(brain, "list", "--project", HOLON, "--json")
        same("list --json without share.py")
        its = items_of(r.stdout) if r.returncode == 0 else {}
        claim(r.returncode == 0 and r.stderr == "" and sorted(its) == ["T-0001", "T-0002", "T-0003"]
              and all(i.get("shared") == [] and i.get("shared_with") == [] for i in its.values()),
              "without share.py: three items, no error, shared == [] on each")
        r = run(brain, "list", "--project", HOLON)
        same("list without share.py")
        claim(r.returncode == 0 and r.stderr == "" and len(item_lines(r.stdout)) == 3 and "shared:" not in r.stdout,
              "without share.py: the text list shows all three and no shared: segment")
        r = run(brain, "list", "--project", HOLON, "--shared-with", "riley")
        claim(r.returncode == 2 and r.stdout == "" and "shares with nobody" in r.stderr,
              "without share.py: --shared-with riley exits 2 saying this brain shares with nobody")
    finally:
        shutil.rmtree(brain, ignore_errors=True)
    print("%d FAIL" % len(FAILS) if FAILS else "ALL PASS")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
