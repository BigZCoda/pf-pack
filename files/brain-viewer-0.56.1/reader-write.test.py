"""reader-write.test.py -- the Reader's write gate (ledger T-0220), checked without starting a server and without
touching a brain file: every check calls serve.reader_write_rule / serve.writable on a path string.

Run from the brain root:  python skills/brain-viewer/reader-write.test.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import serve  # noqa: E402

FAILS = []


def check(rel, want):
    ok, why = serve.reader_write_rule(rel)
    got = ok and serve.writable(rel) if want else ok
    line = "%s  %-45s editable=%-5s %s" % ("ok  " if got == want else "FAIL", rel, ok, why)
    print(line)
    if got != want:
        FAILS.append(line)


for rel in ("thoughts/notepad/x.md", "thoughts/x.md", "people/x.md"):
    check(rel, True)
for rel in ("context/active-session.md", "context/brain-central-tasks.md", "brain-viewer-holon/brain-viewer-tasks.md",
            "zak-brain.md", "APIZZLE.txt", "skills/brain-viewer/serve.py"):
    check(rel, False)
for rel in ("thoughts/../zak-brain.md", "../outside.md", "people/../../x.md"):
    check(rel, False)
    if serve.writable(rel):
        FAILS.append("writable() let a '..' path through: " + rel)

# every refusal carries a reason the Reader can show
for rel in ("context/active-session.md", "context/brain-central-tasks.md", "APIZZLE.txt"):
    if not serve.reader_write_rule(rel)[1]:
        FAILS.append("no reason for " + rel)

if FAILS:
    print("\n%d FAILED" % len(FAILS))
    sys.exit(1)
print("\nall reader-write checks passed")
