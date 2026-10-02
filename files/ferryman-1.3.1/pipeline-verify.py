#!/usr/bin/env python3
"""
pipeline-verify.py -- transcript-pipeline invariant checker (runbook step 8).

Verifies the raw -> report -> push-format -> mirror -> INDEX chain defined in
skills/ferryman/transcript-intake-runbook.md + pf-app-holon/ferryman-rules.md.
Fully offline: checks disk + context/log.md only, no API calls. Stdlib only.

Checks:
  1. every raw in transcripts/*.txt has a transcripts/import-reports/import-checkup-* report
  2. every import-checkup report carries all five core headers
     (## Summary / ## Key Decisions / ## Action Items / ## Relationship Insights / ## Topics).
     SETTLED design: the name is ACTION ITEMS (the app's name). Lines push as-is and
     land Pending Review in the app's Action Items panel; your approval makes them tasks.
  3. every `| due:` value in an Action Items section is bare ISO YYYY-MM-DD, no emoji
     (one bad due kills the whole item batch server-side)
  4. every conversation id in SYNCED log lines has a mirror .json (by "id" field)
  5. every raw from check 1 has a row in transcripts/INDEX.md
  6. no transcripts/ or deliverables/ file touched in the last 14 days contains a token string
  7. NO intake report lives in deliverables/ (deliverables/ is for human-facing
     deliverables only -- intake reports live in transcripts/import-reports/)

Exit 0 + "PIPELINE CLEAN" when clean (an empty transcripts/ is a clean pass);
exit 1 + "N DISCREPANCIES" otherwise.
Run: python skills/ferryman/pipeline-verify.py   (any cwd; paths resolve from the script)
"""

import json
import re
import sys
import time
from datetime import date
from pathlib import Path

BRAIN = Path(__file__).resolve().parents[2]
TRANSCRIPTS = BRAIN / "transcripts"
REPORTS = TRANSCRIPTS / "import-reports"
DELIVERABLES = BRAIN / "deliverables"
MIRROR = BRAIN / "pf-app-holon" / "transcripts"
LOG = BRAIN / "context" / "log.md"
INDEX = TRANSCRIPTS / "INDEX.md"

# This brain's pipeline starts fresh at delivery -- every raw follows the rules.
RAW_CUTOFF = date(2026, 7, 20)      # checks 1/4/5 apply to files/log lines this date or later
HEADERS = ["## Summary", "## Key Decisions", "## Action Items",
           "## Relationship Insights", "## Topics"]
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
ISO_DUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# conversation ids in SYNCED lines: "id <hex8[-uuid]>" or "record <hex8[-uuid]>"
LOG_ID_RE = re.compile(
    r"\b(?:id|record)\s+([0-9a-f]{8}(?:-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})?)\b",
    re.I)
# only SYNCED lines that are transcript pushes (not repo/etc. syncs)
TRANSCRIPT_LINE_RE = re.compile(r"transcript|markdown|import|upsert|call", re.I)
# require real token-length values -- bare prefix mentions in prose are fine
TOKEN_RE = re.compile(rb"pf_tok_[A-Za-z0-9]{12,}|pfk_[A-Za-z0-9]{12,}")

# documented historical warts check 4 must not re-flag forever (id-prefix -> why)
KNOWN_ORPHANS = {}

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

# ---- check 2: report format (5 push headers) ----
for rep in reports:
    text = read(rep)
    missing = [h for h in HEADERS if h not in text]
    if missing:
        flag(2, f"transcripts/import-reports/{rep.name}",
             "missing push header(s): " + ", ".join(missing))

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
                 f"bad due value '{due}' ({why}) -- kills the item batch server-side")

# ---- check 4: mirror coverage of SYNCED conversation ids ----
mirror_ids = []
if MIRROR.exists():
    for j in MIRROR.glob("*.json"):
        try:
            rec = json.loads(read(j))
            rid = str(rec.get("id", "")).lower()
            if rid:
                mirror_ids.append((rid, j.name))
        except (json.JSONDecodeError, OSError):
            flag(4, f"pf-app-holon/transcripts/{j.name}", "unreadable mirror .json")

seen = set()
log_text = read(LOG) if LOG.exists() else ""
for line in log_text.splitlines():
    if "SYNCED" not in line:
        continue
    d = file_date(line[:12] if line.startswith("[") else line)
    if not d or d < RAW_CUTOFF:
        continue
    if not TRANSCRIPT_LINE_RE.search(line):
        continue
    for cid in LOG_ID_RE.findall(line):
        cid = cid.lower()
        if cid in seen:
            continue
        seen.add(cid)
        if any(cid.startswith(k) for k in KNOWN_ORPHANS):
            continue
        if not any(mid.startswith(cid) for mid, _ in mirror_ids):
            flag(4, cid,
                 f"SYNCED {d.isoformat()} in context/log.md but no mirror .json "
                 "in pf-app-holon/transcripts/ carries this id (pull.py not run?)")

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
