#!/usr/bin/env python3
"""
pipeline-verify.py -- transcript-pipeline invariant checker (runbook step 5).

Verifies the raw -> report -> INDEX chain defined in skills/ferryman/transcript-intake-runbook.md.
Nothing in this brain is sent to the PF App (ferryman 1.4.0), so nothing here looks for a pushed
record. Fully offline: checks disk only, no API calls. Stdlib only.

1.4.0 (2026-11-02): check 4 (every SYNCED push in context/log.md has a mirror record) is retired,
since nothing is pushed; the other checks keep their numbers. BRAIN_ROOT in the environment
overrides the brain root (default: two folders above this script).

Checks:
  1. every raw in transcripts/*.txt has a transcripts/import-reports/import-checkup-* report
  2. every import-checkup report carries all five core headers
     (## Summary / ## Key Decisions / ## Action Items / ## Relationship Insights / ## Topics),
     the layout the PF App's own records use, so a summary made here reads like one made there.
  3. every `| due:` value in an Action Items section is bare ISO YYYY-MM-DD, no emoji
  4. (retired in 1.4.0: nothing is pushed, so there is no pushed record to look for)
  5. every raw from check 1 has a row in transcripts/INDEX.md
  6. no transcripts/ or deliverables/ file touched in the last 14 days contains a token string
  7. NO intake report lives in deliverables/ (deliverables/ is for human-facing
     deliverables only -- intake reports live in transcripts/import-reports/)

Exit 0 + "PIPELINE CLEAN" when clean (an empty transcripts/ is a clean pass);
exit 1 + "N DISCREPANCIES" otherwise.
Run: python skills/ferryman/pipeline-verify.py   (any cwd; paths resolve from the script)
"""

import os
import re
import sys
import time
from datetime import date
from pathlib import Path

BRAIN = Path(os.environ.get("BRAIN_ROOT") or Path(__file__).resolve().parents[2])
TRANSCRIPTS = BRAIN / "transcripts"
REPORTS = TRANSCRIPTS / "import-reports"
DELIVERABLES = BRAIN / "deliverables"
INDEX = TRANSCRIPTS / "INDEX.md"

# This brain's pipeline starts fresh at delivery -- every raw follows the rules.
RAW_CUTOFF = date(2026, 7, 20)      # checks 1/5 apply to files this date or later
HEADERS = ["## Summary", "## Key Decisions", "## Action Items",
           "## Relationship Insights", "## Topics"]
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
ISO_DUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# require real token-length values -- bare prefix mentions in prose are fine
TOKEN_RE = re.compile(rb"pf_tok_[A-Za-z0-9]{12,}|pfk_[A-Za-z0-9]{12,}")

violations = []


def flag(check, subject, what):
    violations.append(f"[CHECK-{check}] {subject}: {what}")


def file_date(name):
    m = DATE_RE.search(name)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def dateless_slug(stem):
    """strip the date (and anything after it) from a raw filename stem"""
    m = DATE_RE.search(stem)
    return stem[: m.start()].rstrip("-") if m else stem


# ---- gather ----
raws = sorted(p for p in TRANSCRIPTS.glob("*.txt")
              if (file_date(p.name) or date.min) >= RAW_CUTOFF)
reports = sorted(REPORTS.glob("import-checkup-*.md")) if REPORTS.exists() else []
report_names = [p.name for p in reports]

# ---- check 1: raw -> report ----
for raw in raws:
    slug = dateless_slug(raw.stem)
    if not (slug and any(slug in name for name in report_names)):
        flag(1, f"transcripts/{raw.name}",
             f"no transcripts/import-reports/import-checkup-*{slug}*.md report found")

# ---- check 2: report format (the 5 core headers) ----
for rep in reports:
    text = read(rep)
    missing = [h for h in HEADERS if h not in text]
    if missing:
        flag(2, f"transcripts/import-reports/{rep.name}",
             "missing core header(s): " + ", ".join(missing))

# ---- check 3: due-rule inside ## Action Items ----
for rep in reports:
    text = read(rep)
    in_items = False
    for line in text.splitlines():
        if line.strip().startswith("## "):
            in_items = line.strip() == "## Action Items"
            continue
        if not in_items or "| due:" not in line:
            continue
        seg = line.split("| due:", 1)[1]
        due = seg.split("|", 1)[0].strip()
        has_emoji = any(ord(ch) > 0x2000 for ch in due)
        if not ISO_DUE_RE.match(due) or has_emoji:
            why = "contains emoji" if has_emoji else "not bare ISO YYYY-MM-DD"
            if has_emoji and not ISO_DUE_RE.match(due.split()[0] if due.split() else ""):
                why = "not bare ISO YYYY-MM-DD + emoji"
            flag(3, f"transcripts/import-reports/{rep.name}",
                 f"bad due value '{due}' ({why}) -- write YYYY-MM-DD, or leave the due segment out")

# ---- check 4: retired in 1.4.0 (nothing is pushed, so there is no pushed record to look for) ----

# ---- check 5: INDEX rows for check-1 raws ----
index_text = read(INDEX) if INDEX.exists() else ""
for raw in raws:
    if raw.stem in index_text or raw.name in index_text:
        continue
    flag(5, f"transcripts/{raw.name}", "no row in transcripts/INDEX.md")

# ---- check 6: token hygiene, last 14 days ----
cutoff_mtime = time.time() - 14 * 86400
for folder in (TRANSCRIPTS, DELIVERABLES):
    if not folder.exists():
        continue
    for p in folder.rglob("*"):
        if not p.is_file() or p.stat().st_mtime < cutoff_mtime:
            continue
        m = TOKEN_RE.search(p.read_bytes())
        if m:
            tok = m.group(0).decode("ascii", "replace")
            flag(6, str(p.relative_to(BRAIN)),
                 f"contains token string '{tok[:12]}...' (modified within 14 days)")

# ---- check 7: intake reports must NEVER be in deliverables/ ----
if DELIVERABLES.exists():
    for stray in sorted(DELIVERABLES.glob("import-checkup-*.md")):
        flag(7, f"deliverables/{stray.name}",
             "intake reports do NOT live in deliverables/ -- "
             "move to transcripts/import-reports/")

# ---- report ----
for v in violations:
    print(v)
if violations:
    print(f"{len(violations)} DISCREPANCIES")
    sys.exit(1)
print("PIPELINE CLEAN")
sys.exit(0)
