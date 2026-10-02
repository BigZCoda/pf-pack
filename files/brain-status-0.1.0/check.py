#!/usr/bin/env python3
"""check.py -- brain-status's self-check. Exit 0 clean, 2 on any finding. Writes nothing into any brain.

1. status.py compiles (in memory, no __pycache__).
2. It runs read-only against a mentee brain with --brain and --offline and prints the summary. The brain is the
   folder given with --brain, else ~/Documents/kyle-brain when that clone exists.
3. It runs against an empty temporary folder (no manifest, no viewer, no token, no ledger, no log) without crashing.
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(HERE, "status.py")


def run(args):
    r = subprocess.run([sys.executable, STATUS] + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    ap = argparse.ArgumentParser(description="brain-status self-check")
    ap.add_argument("--brain", default=os.path.expanduser(os.path.join("~", "Documents", "kyle-brain")))
    a = ap.parse_args()
    bad = 0
    try:
        with open(STATUS, encoding="utf-8") as f:
            compile(f.read(), STATUS, "exec")
        print("compile  status.py ok")
    except SyntaxError as e:
        print("COMPILE  status.py:%s %s" % (e.lineno, e.msg))
        return 2

    if os.path.isdir(a.brain):
        code, out = run(["--brain", a.brain, "--offline"])
        print(out.rstrip())
        if code != 0 or "Traceback" in out:
            print("FAIL     run against %s exited %d" % (a.brain, code)); bad += 1
    else:
        print("skip     no brain at %s (pass --brain <folder>)" % a.brain)

    with tempfile.TemporaryDirectory(prefix="brain-status-empty-") as empty:
        code, out = run(["--brain", empty, "--offline"])
        if code != 0 or "Traceback" in out:
            print(out.rstrip())
            print("FAIL     run against an empty folder exited %d" % code); bad += 1
        else:
            print("ok       empty folder (no manifest, viewer, token, ledger or log): no crash")
    print("brain-status check: %s" % ("clean" if not bad else "%d finding(s)" % bad))
    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(main())
