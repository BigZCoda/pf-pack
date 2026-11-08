#!/usr/bin/env python
"""check.py -- the mentee-project folder's self-check. Exit 0 clean, 2 on any finding.

1. Every .py in this folder compiles.
2. No file in this folder carries a token value (PF App personal or admin tokens, API keys, bearer strings).
3. No file names the program's founder (the prompts must read as plain instructions, never in someone's voice).
4. No file carries a transcript line reference (an L-number, or the word line or lines followed by a number).
The patterns are assembled from pieces so this file does not match itself.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TOKEN = re.compile("|".join([
    "pf" + "_tok_[A-Za-z0-9]{8,}",
    "pf" + "k_[A-Za-z0-9]{8,}",
    "s" + "k-[A-Za-z0-9_-]{16,}",
    "Bear" + r"er\s+[A-Za-z0-9._-]{16,}",
]))
VOICE = re.compile(r"\b(" + "Za" + "k|Za" + "kary|Koe" + r"nigs)\b", re.I)
LINEREF = re.compile(r"\bL\d{2,5}\b|\blines?\s+\d+(?:\s*[-–]\s*\d+)?\b", re.I)


def main():
    bad = 0
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, HERE).replace(os.sep, "/")
            if fn.endswith(".py"):
                try:
                    with open(p, encoding="utf-8") as f:
                        compile(f.read(), p, "exec")   # in memory: writes no __pycache__
                except SyntaxError as e:
                    print("COMPILE  %s:%s %s" % (rel, e.lineno, e.msg)); bad += 1
            try:
                with open(p, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                for label, rx in (("TOKEN", TOKEN), ("VOICE", VOICE), ("LINEREF", LINEREF)):
                    m = rx.search(line)
                    if m:
                        shown = "(value withheld)" if label == "TOKEN" else repr(m.group(0))
                        print("%-8s %s:%d %s" % (label, rel, n, shown)); bad += 1
    print("check: %s" % ("clean" if not bad else "%d finding(s)" % bad))
    sys.exit(2 if bad else 0)


if __name__ == "__main__":
    main()
