#!/usr/bin/env python3
"""tasks-lock.test.py -- one writer at a time per ledger, and a person's own question (2026-11-09).

Two additions made with the sharing sync, which writes ledgers from a second process beside the viewer and the
command line:

 1. LedgerLock: apply() holds a lock per ledger file from its read to its write, so writers that overlap lose nothing.
    Eight processes add five tasks each to one scratch ledger at the same moment: all forty are there, each id once,
    and the file still reads as a ledger. A lock left by a writer that died is taken over; a live one makes a second
    writer wait and then say so, changing nothing.
 2. The pose gate does not rewrite a person: a question another person asks the owner (--from a contact) is filed as
    written, and `check` does not fail on it; the same words from Claude are still refused.

Scratch brain in a temp folder, the real tasks.py as a subprocess with BRAIN_ROOT on it. One PASS / FAIL line per claim.

    python skills/brain-tasks/tasks-lock.test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PY = os.path.join(HERE, "tasks.py")
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


def env(brain):
    return dict(os.environ, BRAIN_ROOT=brain)


def run(brain, *args):
    return subprocess.run([sys.executable, TASKS_PY] + list(args), cwd=brain, capture_output=True, text=True,
                          encoding="utf-8", timeout=180, env=env(brain))


WRITER = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
import tasks
path, rel, who = sys.argv[2], sys.argv[3], sys.argv[4]
for n in range(5):
    tasks.apply(path, rel, "add", agent="lock-test", text="Writer %s adds scratch task number %d" % (who, n), owner="@claude")
"""

HOLDER = r"""
import os, sys, time
sys.path.insert(0, sys.argv[1])
import tasks
with tasks.LedgerLock(sys.argv[2]):
    print("held", flush=True)
    time.sleep(float(sys.argv[3]))
"""


def main():
    brain = tempfile.mkdtemp(prefix="tasks-lock-")
    try:
        put(brain, "context/holon-registry.json", json.dumps({"holons": [
            {"id": HOLON, "name": "Test holon", "path": "test-holon/", "tasks": LEDGER_REL}]}))
        put(brain, "context/log.md", "# Log\n")
        put(brain, "people/riley-stone.md", "# Riley Stone\n")
        r = run(brain, "init", "--project", HOLON, "--name", "Test holon")
        claim(r.returncode == 0, "init makes the scratch ledger (%s)" % (r.stderr.strip() or "ok"))
        path = os.path.join(brain, *LEDGER_REL.split("/"))

        # 1. eight writers at once
        procs = [subprocess.Popen([sys.executable, "-c", WRITER, HERE, path, LEDGER_REL, str(w)], cwd=brain, env=env(brain),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for w in range(8)]
        outs = [p.communicate(timeout=300) for p in procs]
        claim(all(p.returncode == 0 for p in procs), "eight writers at once all finish (%s)"
              % "; ".join(sorted({(o[1] or "").strip().splitlines()[-1] for o in outs if (o[1] or "").strip()}) or ["ok"])[:200])
        r = run(brain, "list", "--project", HOLON, "--json")
        items = [i for led in json.loads(r.stdout or "[]") for i in led.get("items") or []]
        ids = [i["id"] for i in items]
        claim(len(items) == 40, "all forty tasks are on the ledger (%d)" % len(items))
        claim(len(set(ids)) == len(ids), "each id is there once")
        claim(all(sum(1 for i in items if i["text"].startswith("Writer %d adds" % w)) == 5 for w in range(8)), "five from every writer")
        r = run(brain, "check")
        claim(r.returncode == 0, "the file still reads as a ledger (%s)" % ((r.stdout + r.stderr).strip().splitlines() or ["ok"])[-1][:120])

        # 1b. a live lock makes a second writer wait, then refuse, changing nothing
        sys.path.insert(0, HERE)
        os.environ["BRAIN_ROOT"] = brain
        import tasks                                           # noqa: E402
        tasks.LedgerLock.WAIT = 1.0
        holder = subprocess.Popen([sys.executable, "-c", HOLDER, HERE, path, "6"], cwd=brain, env=env(brain),
                                  stdout=subprocess.PIPE, text=True)
        holder.stdout.readline()
        before = open(path, "rb").read()
        t0 = time.time()
        try:
            tasks.apply(path, LEDGER_REL, "add", agent="lock-test", text="A task that must wait its turn", owner="@claude")
            refused = ""
        except tasks.LedgerError as e:
            refused = str(e)
        waited = time.time() - t0
        claim("still running" in refused and 0.8 <= waited < 5 and open(path, "rb").read() == before,
              "a second writer waits, then says another write is running and changes nothing (%.1fs)" % waited)
        holder.wait(timeout=60)
        # 1c. a lock left by a writer that died is taken over
        lock = tasks.LedgerLock(path).lock
        with open(lock, "w") as f:
            f.write("0")
        old = time.time() - 600
        os.utime(lock, (old, old))
        try:
            tasks.apply(path, LEDGER_REL, "add", agent="lock-test", text="A task written past a stale lock", owner="@claude")
            took = True
        except tasks.LedgerError:
            took = False
        claim(took and not os.path.exists(lock), "a lock left by a writer that died is taken over and cleared")

        # 2. the pose gate does not rewrite a person
        words = "status of the booth kit please"
        r = run(brain, "ask", "--project", HOLON, "--to", "@me", "--text", words)
        claim(r.returncode != 0 and "cannot be put to the owner" in (r.stdout + r.stderr), "Claude's question without a question in it is still refused")
        r = run(brain, "ask", "--project", HOLON, "--to", "@me", "--from", "@riley-stone", "--text", words)
        claim(r.returncode == 0, "the same words asked by a person are filed as written (%s)" % ((r.stdout + r.stderr).strip().splitlines() or ["ok"])[-1][:120])
        r = run(brain, "check", "--project", HOLON)
        claim(r.returncode == 0 and "POSED" not in "".join(l for l in (r.stdout + r.stderr).splitlines() if "FAIL" in l),
              "check does not fail on a person's own question")
    finally:
        shutil.rmtree(brain, ignore_errors=True)
    print("\n%d FAILED" % len(FAILS) if FAILS else "\nALL PASS")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
