#!/usr/bin/env python3
"""brain-log -- the ONLY correct way to write context/log.md, plus the integrity check.

WHY THIS EXISTS
---------------
`context/log.md` is append-only and its timestamps are load-bearing:
`context/dispatcher-cursor.md` bookmarks BY TIMESTAMP, so a line stamped behind the
cursor but written after it advances is skipped permanently -- that work never gets
routed. The night-agent ledger has carried this as a weighted observation since
2026-06-25 and its recommended fix has been proposed in runs #17, #18, #39, #40 and
#41 without being adopted:

    "read the clock in the same command that appends"

That is exactly what --append does. It takes NO timestamp argument -- there is no way
to pass one -- so a stamp cannot be typed from an agent's own sense of time. Every
observed instance of the defect came from an agent typing a clock by hand; every line
written by a script (ferryman, assemble-brain, scout, onboarding) has been exact.

Adopted 2026-08-10 on the owner's instruction, together with the hooks that run --check
automatically so nobody has to remember.

USAGE
-----
  python skills/brain-log/log.py --check              # validate the LIVE file; exit 0 clean, 2 dirty
  python skills/brain-log/log.py --check --all        # the live file AND every rotated month, in order
  python skills/brain-log/log.py --check --hook       # live file only, emits hook JSON
  python skills/brain-log/log.py --rotate             # move every month before this one to archive/ledgers/
  python skills/brain-log/log.py --rotate --dry-run   # say what it would move, write nothing
  python skills/brain-log/log.py --append \
        --agent claude-code --action MODIFIED \
        --text "people/john-kissell.md -- folded the 8/05 call"

MONTHLY ROTATION (structure-pass Batch 2, 2026-09-18 -- the owner's yes on brain-central Q-0037)
------------------------------------------------------------------------------------------
The live file crossed 1.1 MB, four times the ~262 KB read ceiling of the tool that reads it
(night-agent obs#47). --rotate moves every line stamped BEFORE the current month into
`archive/ledgers/YYYY-MM/log-YYYY-MM.md`, one file per month, lines verbatim; the live file
keeps its header, a pointer naming the months present, and the current month. The same call
rotates the second giant ledger's `## Run history` section into the same month folders (see
rotate_observations for why only that section moves).

Three properties make it safe to run at every rounds (step 10e):
  * it refuses unless --check is clean first, so it never rewrites a file whose ordering is
    already broken;
  * it is idempotent -- a second run finds nothing before the current month and says so;
  * it reconciles and PRINTS the counts (before = live after + archived), so a lost line is
    loud rather than silent.

The dispatcher cursor bookmarks BY TIMESTAMP and by the literal line, so dispatch.py reads
the live file plus the archive months a window needs, and lint L19 checks the split holds.

MONOTONICITY BASELINE
---------------------
The file carries ~25 historic inversions from June/July 2026 that predate this tool.
Re-reporting them forever would make the check permanently red and therefore ignored,
so --check FAILS only on inversions at or after BASELINE and reports older ones as
informational. Move BASELINE forward once a stretch is repaired; never move it
backward to hide a fresh break.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

# The brain this log belongs to: BRAIN_ROOT when a caller names one (tasks.py and the viewer both pass it), otherwise
# the folder this file sits in, two levels up (<brain>/skills/brain-log/log.py). Resolving from the file rather than
# from a hard-coded path means a COPY of these three tools logs into its own context/log.md when it is run directly,
# instead of appending to the tree the string happened to name. Independent of the working directory.
BRAIN = os.environ.get("BRAIN_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(BRAIN, "context", "log.md")
LOG_REL = "context/log.md"

# Rotated months (2026-09-18, Batch 2). One FOLDER per month so the second giant ledger sits
# beside its log: archive/ledgers/2026-08/{log,night-agent-observations}-2026-08.md
ARCHIVE_DIR = os.path.join(BRAIN, "archive", "ledgers")
ARCHIVE_REL = "archive/ledgers"
MONTH_FILE = "log-%s.md"

# The live file's managed pointer line: matched by this prefix and rewritten in place, so a
# second rotation never stacks a second pointer on top of the first.
POINTER_PREFIX = "> **Rotated months:**"

# Inversions on/after this date are FAILURES. Earlier ones are historic, reported only.
# 2026-08-10: verified strictly monotonic from 2026-07-29 onward.
BASELINE = "2026-07-29"

# An entry opens with [DATE TIME] where TIME is either a real clock or one of the
# historic "time unknown" markers the log has legitimately used: ~, --:--, am, pm,
# morning, etc. Those are honest imprecision, NOT corruption -- they sort by date.
ENTRY_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2})(?:[ T]([^\]]*))?\]\s*\[([a-z0-9-]+)\]\s*([A-Z][A-Z0-9]*)")
CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})")

# Vocabulary is enforced on WRITE only. --check never fails on a verb: the log has 30+
# real verbs across its history and policing them is not this tool's job.
ACTIONS = {
    "CREATED", "MODIFIED", "EXTRACTED", "INGESTED", "LINKED", "SYNCED", "LINTED",
    "DECISION", "ROUNDS", "DISPATCHED", "FLAGGED", "SKIPPED", "FAILED", "VERIFIED",
    "PULL", "PUSH", "ARCHIVED", "DELETED", "RENAMED", "STARTED", "AUDIT", "FOLDED",
    # CLOSED added 2026-09-01: the playbook's Step 0 tracking contract has prescribed
    # "CLOSED -- N items closed, M asked, K to cold storage" since 2026-08-28, and the
    # tool rejected it, so no closure pass could ever log itself as specified.
    "CLOSED",
    "REBUILT", "MOVED", "ROTATED", "DISCOVERED", "TESTED", "NOTE", "READ", "ADDED",
    "SEEDED", "FEEDBACK", "SUSPENDED", "RESTORED",
}


def parse(path):
    """Return (raw_lines, rows). Each row carries a sort key that degrades gracefully:
    a real clock sorts within its day; an imprecise marker sorts to the start of its day."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().split("\n")
    rows, unparseable = [], []
    for i, line in enumerate(raw, 1):
        if not line.startswith("["):
            continue
        m = ENTRY_RE.match(line)
        if not m:
            if re.match(r"^\[\d{4}-", line):
                unparseable.append((i, line[:110]))
            continue
        date, timepart, agent, action = m.groups()
        timepart = (timepart or "").strip()
        cm = CLOCK_RE.match(timepart)
        if cm:
            hhmm = "%02d:%s" % (int(cm.group(1)), cm.group(2))
            precise = True
        else:
            hhmm = "00:00"          # imprecise marker -> sorts to start of day
            precise = False
        rows.append({"n": i, "date": date, "ts": date + " " + hhmm, "precise": precise,
                     "marker": timepart, "agent": agent, "action": action})
    return raw, rows, unparseable


def check(path=None, label=None, month=None):
    """Validate ONE ledger file. path/label default to the live log, so every existing caller
    (the two hooks, plain --check, the viewer) behaves exactly as before. `month` is set when the
    file is a rotated month: every stamp in it must then belong to that month."""
    path = path or LOG
    label = label or LOG_REL
    problems, info = [], []
    if not os.path.exists(path):
        return ["%s IS MISSING -- Agent Tracking Contract breach, not a lint issue" % label], [], {}

    raw, rows, unparseable = parse(path)
    now = datetime.now()

    # --- FAILURES: only things that actually break something, and only from BASELINE on.
    # 1. Unparseable entry line written recently.
    hist_unparseable = 0
    for n, snippet in unparseable:
        d = snippet[1:11]
        if d >= BASELINE:
            problems.append("line %d: entry does not parse as [YYYY-MM-DD HH:MM] [agent-id] ACTION -- %s" % (n, snippet))
        else:
            hist_unparseable += 1

    # 2. Future stamps. 90 min absorbs a timezone/DST skew; a typo blows straight past it.
    for r in rows:
        if not r["precise"]:
            continue
        try:
            when = datetime.strptime(r["ts"], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if when > now + timedelta(minutes=90):
            problems.append("line %d: timestamp %s is IN THE FUTURE (clock says %s) -- a hand-typed stamp"
                            % (r["n"], r["ts"], now.strftime("%Y-%m-%d %H:%M")))

    # 3. Inversions. THIS is the one that silently loses work: dispatcher-cursor.md
    #    bookmarks by timestamp, so a line stamped behind an advanced cursor is skipped.
    hist_inv = 0
    for a, b in zip(rows, rows[1:]):
        if b["ts"] < a["ts"]:
            if b["date"] >= BASELINE:
                problems.append(
                    "line %d: OUT OF ORDER -- %s follows %s. log.md is append-only and the dispatcher "
                    "cursor bookmarks by timestamp, so this line can be skipped permanently."
                    % (b["n"], b["ts"], a["ts"]))
            else:
                hist_inv += 1

    # 4. Imprecise stamps are fine historically, discouraged going forward.
    recent_imprecise = [r["n"] for r in rows if not r["precise"] and r["date"] >= BASELINE]
    if recent_imprecise:
        info.append("%d entry/entries on or after %s use an imprecise time marker (%s...) -- allowed, but "
                    "--append always writes a real clock, so new lines should not need one"
                    % (len(recent_imprecise), BASELINE, recent_imprecise[:5]))

    # --- INFO: historic state, never a failure.
    if hist_inv:
        info.append("%d historic inversion(s) before the %s baseline -- pre-existing, not failing this check" % (hist_inv, BASELINE))
    if hist_unparseable:
        info.append("%d historic entry/entries before %s use the older '~' / '--:--' / 'am' time convention -- honest imprecision, not corruption" % (hist_unparseable, BASELINE))
    unknown = sorted({r["action"] for r in rows if r["action"] not in ACTIONS})
    if unknown:
        info.append("%d action verb(s) in the file are outside the write-time vocabulary (%s) -- read-only, not enforced"
                    % (len(unknown), ", ".join(unknown[:8])))

    # 5. A rotated month holds that month and nothing else. (The live half -- the live file holds
    #    ONLY the current month -- is lint L19, because lint is what sweeps the tree.)
    if month:
        strays = [r["n"] for r in rows if r["date"][:7] != month]
        if strays:
            problems.append("%d line(s) in the %s archive are not stamped %s (first at line %d) -- "
                            "the rotation put a month in the wrong file"
                            % (len(strays), month, month, strays[0]))

    stats = {"label": label, "entries": len(rows), "oldest": rows[0]["ts"] if rows else None,
             "newest": rows[-1]["ts"] if rows else None, "baseline": BASELINE}
    return problems, info, stats


# ---------------------------------------------------------------- rotation (Batch 2)

def archive_month_path(month):
    """<brain>/archive/ledgers/YYYY-MM/log-YYYY-MM.md"""
    return os.path.join(ARCHIVE_DIR, month, MONTH_FILE % month)


def archive_months():
    """Every rotated month on disk, oldest first."""
    if not os.path.isdir(ARCHIVE_DIR):
        return []
    out = []
    for name in sorted(os.listdir(ARCHIVE_DIR)):
        if re.fullmatch(r"\d{4}-\d{2}", name) and os.path.isfile(archive_month_path(name)):
            out.append(name)
    return out


def split_header(raw):
    """-> (header_lines, body_lines). The header is everything above the first entry line;
    it is kept verbatim apart from the one managed pointer line."""
    for i, line in enumerate(raw):
        if re.match(r"^\[\d{4}-\d{2}-\d{2}", line):
            return raw[:i], raw[i:]
    return raw, []


def bucket_by_month(body):
    """body lines -> {month: [lines]}, in file order. A blank line rides with the month of the
    entry above it, so nothing is dropped and each month's block reads the way it was written."""
    buckets, order, cur = {}, [], None
    for line in body:
        m = re.match(r"^\[(\d{4}-\d{2})", line)
        if m:
            cur = m.group(1)
        if cur is None:
            continue                      # blank lines above the first entry: header's business
        if cur not in buckets:
            buckets[cur] = []
            order.append(cur)
        buckets[cur].append(line)
    return buckets, order


def pointer_line(months):
    return ("%s the months before this one live in `%s/YYYY-MM/log-YYYY-MM.md` (%s). "
            "This file holds the CURRENT month only -- rotation runs at rounds step 10e "
            "(`python skills/brain-log/log.py --rotate`). Readers that need an older window "
            "(dispatch.py, the viewer, lint L19) read the live file plus the month they need."
            % (POINTER_PREFIX, ARCHIVE_REL, ", ".join(months) if months else "none yet"))


def set_pointer(header, months):
    """Rewrite the managed pointer in place, or insert it under the 2026-H1 rotation note."""
    line = pointer_line(months)
    out, done = [], False
    for ln in header:
        if ln.startswith(POINTER_PREFIX):
            if not done:
                out.append(line)
                done = True
            continue                      # a stacked duplicate from an older run is dropped
        out.append(ln)
    if done:
        return out
    anchor = None
    for i, ln in enumerate(out):
        if "archive/2026-H1-logs" in ln:
            anchor = i + 1
    if anchor is None:
        for i, ln in enumerate(out):
            if ln.startswith(">"):
                anchor = i + 1
    if anchor is None:
        anchor = 1
    return out[:anchor] + [line] + out[anchor:]


def write_month(month, lines, rotated_on):
    """Append `lines` to the month's archive file, verbatim, creating it with its two-line header.
    Lines already present verbatim are not written twice, so --rotate is idempotent."""
    path = archive_month_path(month)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    head = ["# Brain Operations Log -- %s" % month,
            "> Rotated verbatim out of `%s` on %s (`log.py --rotate`, structure-pass Batch 2). "
            "Read-only history: new lines are only ever appended to the live file."
            % (LOG_REL, rotated_on),
            ""]
    existing = []
    if os.path.exists(path):
        existing = open(path, encoding="utf-8").read().split("\n")
        body = split_header(existing)[1]
        head = [ln for ln in existing[:len(existing) - len(body)]]
        if head and head[-1] != "":
            head.append("")
    else:
        body = []
    have = set(ln for ln in body if ln.strip())
    added = [ln for ln in lines if ln.strip() and ln not in have]
    body = body + added
    text = "\n".join([ln for ln in head] + [ln for ln in body]).rstrip("\n") + "\n"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return len([ln for ln in added if ln.strip()]), len([ln for ln in body if ln.strip()])


# ---------------------------------------------------------------- the observations ledger
# The SECOND giant ledger of Batch 2. It lives here, in the log tool, for three reasons: one archive
# layout (archive/ledgers/YYYY-MM/), one clean-check gate, and one rounds step (10e) rather than two.
#
# What rotates is the `## Run history` section ONLY, and that is a finding, not a shortcut. The
# `## Active Observations` section is 700 KB of 91 weighted obs# entries, and 44 of them carry dated
# evidence bullets from more than one month -- obs#43 spans 2026-04 to 2026-09, obs#47 spans 2026-03
# to 2026-09. Splitting that section by month would cut a single observation's weight history across
# five files, which is the opposite of what the ledger is for ("never overwrite previous entries --
# add to them"). Its size is obs#47's own per-entry cap problem (brain-central T-0040), not a
# rotation problem. The run history is the per-run appended material: one dated, self-contained item
# per run, no weights, and it is what the night agent's "last 80 lines" read actually reaches.
OBS_REL = "context/night-agent-observations.md"
OBS_FILE = "night-agent-observations-%s.md"
OBS_HEADING = "## Run history"
OBS_ITEM_RE = re.compile(r"^(\*\*Run #\d+|- \*\*)")
OBS_DATE_RE = re.compile(r"\b(20\d\d-\d\d)-\d\d\b")
OBS_POINTER_PREFIX = "> **Rotated run history:**"
OBS_HEAD_PREFIX = "> **Rotated:**"


def obs_items(block):
    """The run-history block -> (preamble lines, [(month, [lines])]) in file order. An item starts at
    a `**Run #N ...**` paragraph or a `- **YYYY-MM-DD production run #N ...**` bullet and runs to the
    next one, so the blank line under an item travels with it."""
    pre, items, cur = [], [], None
    for line in block:
        if OBS_ITEM_RE.match(line):
            cur = [line]
            items.append(cur)
        elif cur is None:
            pre.append(line)
        else:
            cur.append(line)
    out = []
    for it in items:
        m = OBS_DATE_RE.search(it[0])
        out.append((m.group(1) if m else None, it))
    return pre, out


def obs_pointer(months):
    return ("%s the run-history entries from %s live in `%s/YYYY-MM/night-agent-observations-YYYY-MM.md`, "
            "verbatim. This section holds the CURRENT month; rotation runs at rounds step 10e. The weighted "
            "obs# entries under `## Active Observations` are NEVER rotated -- 44 of them carry evidence from "
            "more than one month, so a month split would cut one observation's history across files."
            % (OBS_POINTER_PREFIX, ", ".join(months) if months else "earlier months", ARCHIVE_REL))


def obs_set_head(above, months):
    """One managed line in the file's header, so a reader that only takes the header learns that the
    run history rotated and the weighted entries did not."""
    line = ("%s the `%s` section keeps the current month only; %s are at "
            "`%s/YYYY-MM/night-agent-observations-YYYY-MM.md`. `## Active Observations` is NOT rotated."
            % (OBS_HEAD_PREFIX, OBS_HEADING, ", ".join(months) if months else "earlier months", ARCHIVE_REL))
    out, done = [], False
    for ln in above:
        if ln.startswith(OBS_HEAD_PREFIX):
            if not done:
                out.append(line)
                done = True
            continue
        out.append(ln)
    if done:
        return out
    for i, ln in enumerate(out):
        if "THIS FILE IS" in ln or (i and ln.startswith("> Initialized:")):
            return out[:i + 1] + [line] + out[i + 1:]
    return out[:1] + [line] + out[1:]


def rotate_observations(dry_run=False):
    """Move `## Run history` items older than the current month into archive/ledgers/YYYY-MM/."""
    path = os.path.join(BRAIN, "context", "night-agent-observations.md")
    if not os.path.exists(path):
        print("rotate: %s is not here; nothing to do" % OBS_REL)
        return 0
    raw = open(path, encoding="utf-8").read().split("\n")
    if raw and raw[-1] == "":
        raw = raw[:-1]
    head_end = None
    for i, line in enumerate(raw):
        if line.strip() == OBS_HEADING:
            head_end = i
            break
    if head_end is None:
        print("rotate: %s has no '%s' section -- nothing rotates, and the weighted entries never do"
              % (OBS_REL, OBS_HEADING))
        return 0

    above, block = raw[:head_end + 1], raw[head_end + 1:]
    pre, items = obs_items(block)
    current = datetime.now().strftime("%Y-%m")
    old = sorted({mo for mo, _lines in items if mo and mo < current})
    if not old:
        print("rotate: no run-history item before %s in %s -- already rotated (%d item(s) live)"
              % (current, OBS_REL, len(items)))
        return 0
    if dry_run:
        for mo in old:
            n = sum(1 for m2, _l in items if m2 == mo)
            print("rotate (dry run): %s run history %s -> %s/%s/%s (%d item(s))"
                  % (OBS_REL, mo, ARCHIVE_REL, mo, OBS_FILE % mo, n))
        return 0

    stamp = datetime.now().strftime("%Y-%m-%d")
    moved = 0
    for mo in old:
        lines = []
        for m2, block_lines in items:
            if m2 == mo:
                lines.extend(block_lines)
                moved += 1
        target = os.path.join(ARCHIVE_DIR, mo, OBS_FILE % mo)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        body = ["# Night Agent Run History -- %s" % mo,
                "> Rotated verbatim out of the `%s` section of `%s` on %s (`log.py --rotate`, "
                "structure-pass Batch 2). The weighted obs# entries stay in the live file."
                % (OBS_HEADING, OBS_REL, stamp),
                "",
                "%s -- %s" % (OBS_HEADING, mo),
                ""] + lines
        existing = []
        if os.path.exists(target):
            existing = open(target, encoding="utf-8").read().split("\n")
            have = set(ln for ln in existing if ln.strip())
            body = existing + [ln for ln in lines if ln.strip() and ln not in have]
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(body).rstrip("\n") + "\n")
        print("rotate: %-7s -> %s/%s/%s  (%d run-history item(s))"
              % (mo, ARCHIVE_REL, mo, OBS_FILE % mo, sum(1 for m2, _l in items if m2 == mo)))

    kept = []
    for mo, block_lines in items:
        if mo is None or mo >= current:
            kept.extend(block_lines)
    pre = [ln for ln in pre if not ln.startswith(OBS_POINTER_PREFIX)]
    pre = [ln for ln in pre if ln.strip()] or []
    above = [ln for ln in above if not ln.startswith(OBS_POINTER_PREFIX)]
    above = obs_set_head(above, old)
    new = above + [""] + pre + ([""] if pre else []) + [obs_pointer(old), ""] + kept
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(new).rstrip("\n") + "\n")

    live_after = sum(1 for mo, _l in items if mo is None or mo >= current)
    ok = (live_after + moved) == len(items)
    print("rotate: %s run history -- %d item(s) before = %d live (%s) + %d archived  -- %s"
          % (OBS_REL, len(items), live_after, current, moved,
             "RECONCILED" if ok else "MISMATCH, INVESTIGATE BEFORE COMMITTING"))
    return 0 if ok else 2


def rotate(dry_run=False):
    """Move every line stamped before the current month into archive/ledgers/YYYY-MM/.

    Refuses on a dirty --check: rewriting a file whose ordering is already broken is how a
    rotation turns a reported problem into a lost line."""
    problems, _info, _stats = check()
    if problems:
        sys.stderr.write("refusing to rotate: --check is not clean (%d problem(s)). Fix the log first.\n"
                         % len(problems))
        for pb in problems[:5]:
            sys.stderr.write("  x %s\n" % pb)
        return 2

    now = datetime.now()
    current = now.strftime("%Y-%m")
    raw = open(LOG, encoding="utf-8").read().split("\n")
    if raw and raw[-1] == "":
        raw = raw[:-1]                      # the file's trailing newline, re-added on write
    header, body = split_header(raw)
    buckets, order = bucket_by_month(body)
    entries_before = sum(1 for ln in body if re.match(r"^\[\d{4}-\d{2}-\d{2}", ln))

    old = [m for m in order if m < current]
    if not old:
        print("rotate: nothing before %s in %s -- already rotated (%d entries live, months on disk: %s)"
              % (current, LOG_REL, entries_before, ", ".join(archive_months()) or "none"))
        return rotate_observations(dry_run=dry_run)

    if dry_run:
        for m in old:
            print("rotate (dry run): %s -> %s/%s/%s  (%d lines, %d entries)"
                  % (LOG_REL, ARCHIVE_REL, m, MONTH_FILE % m, len(buckets[m]),
                     sum(1 for ln in buckets[m] if ln.startswith("["))))
        print("rotate (dry run): %d entries before, %d would stay live, %d would be archived"
              % (entries_before,
                 sum(1 for m in order if m >= current for ln in buckets[m] if ln.startswith("[")),
                 sum(1 for m in old for ln in buckets[m] if ln.startswith("["))))
        return rotate_observations(dry_run=True)

    stamp = now.strftime("%Y-%m-%d")
    archived = 0
    for m in old:
        added, total = write_month(m, buckets[m], stamp)
        archived += added
        print("rotate: %-7s -> %s/%s/%s  (%d entries written, %d in the file)"
              % (m, ARCHIVE_REL, m, MONTH_FILE % m, added, total))

    kept = []
    for m in order:
        if m >= current:
            kept.extend(buckets[m])
    header = set_pointer(header, archive_months())
    with open(LOG, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(header + kept).rstrip("\n") + "\n")

    live_after = sum(1 for ln in kept if re.match(r"^\[\d{4}-\d{2}-\d{2}", ln))
    ok = (live_after + archived) == entries_before
    print("rotate: %d entries before = %d live (%s) + %d archived  -- %s"
          % (entries_before, live_after, current, archived,
             "RECONCILED" if ok else "MISMATCH, INVESTIGATE BEFORE COMMITTING"))
    if not ok:
        return 2
    problems, _info, _stats = check()
    if problems:
        sys.stderr.write("rotate wrote the files but --check is now dirty (%d problem(s)).\n" % len(problems))
        return 2
    print("rotate: --check clean after. Months on disk: %s" % ", ".join(archive_months()))
    return rotate_observations(dry_run=False)


def check_all():
    """--check --all: the live file, then every rotated month oldest-first, then the joins
    between them (an archive month must end before the next month's file begins)."""
    rc = 0
    months = archive_months()
    edges = []
    for m in months:
        problems, info, stats = check(archive_month_path(m), "%s/%s/%s" % (ARCHIVE_REL, m, MONTH_FILE % m), month=m)
        rc = report(problems, info, stats) or rc
        if stats.get("oldest"):
            edges.append((m, stats["oldest"], stats["newest"]))
    problems, info, stats = check()
    rc = report(problems, info, stats) or rc
    if stats.get("oldest"):
        edges.append(("live", stats["oldest"], stats["newest"]))
    for (ma, _oa, na), (mb, ob, _nb) in zip(edges, edges[1:]):
        if ob < na:
            print("  x %s ends %s but %s starts %s -- the months overlap" % (ma, na, mb, ob))
            rc = 2
    if rc == 0 and edges:
        print("LEDGER SPAN CLEAN -- %s, %s ... %s" % (" + ".join(m for m, _, _ in edges),
                                                      edges[0][1], edges[-1][2]))
    return rc


def report(problems, info, stats):
    """One file's check, printed the way plain --check prints the live one."""
    label = stats.get("label") or LOG_REL
    if problems:
        print("LOG INTEGRITY: %d PROBLEM(S) in %s" % (len(problems), label))
        for pb in problems:
            print("  x " + pb)
    else:
        print("LOG INTEGRITY CLEAN -- %s: %d entries, %s .. %s"
              % (label, stats.get("entries", 0), stats.get("oldest"), stats.get("newest")))
    for i in info:
        print("  . " + i)
    return 2 if problems else 0


# A log line's first field is its path field: dispatch.py's path_tokens() reads it, and R3 counts
# distinct paths from it. A bare basename with a known extension PASSES that filter, so `push.py`
# counts as a file distinct from `skills/ferryman/push.py` and R3 double-counts the same file --
# the 2026-09-18 scoped sweep (LS-008) found 8 such lines in one window, 116 counted for 102 real.
# This WARNS rather than refuses: a refusal here would lose the log line, which is worse than a
# miscounted one, and some legitimate descriptions open with a bare word that happens to look filey.
LS008_EXTS = {
    "md", "py", "js", "json", "txt", "html", "css", "canvas", "png", "jpg", "jpeg",
    "gif", "svg", "xlsx", "docx", "pdf", "csv", "tsv", "command", "yaml", "yml",
    "sh", "ts", "tsx", "ipynb", "skill", "toml", "ini", "log", "bat", "ps1",
}


def warn_bare_path(text):
    """Warn (never refuse) when the path field names a file by basename with no folder."""
    field = text.split(" -- ", 1)[0].strip()
    tok = field.split()[0].rstrip(".,;:") if field.split() else ""
    if "/" in tok or "." not in tok:
        return
    ext = tok.rsplit(".", 1)[-1].lower()
    if ext not in LS008_EXTS:
        return
    sys.stderr.write(
        "warning: %r is a bare basename with no folder. Log full repo-relative paths -- the\n"
        "dispatcher's R3 counts it as a file distinct from the real one and double-counts the\n"
        "change (LS-008, 2026-09-18). Writing the line as given.\n" % tok)


def warn_unparsed_path(action, text):
    """Warn (never refuse, for the reason above) when a CREATED/MODIFIED line's path field is
    one the dispatcher cannot read, so R3 would not count the file (librarian-sweep 2026-09-28,
    scoped LS-006 / verification item 17). Uses dispatch.py's own parser so the two never drift."""
    if action not in ("CREATED", "MODIFIED"):
        return
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "dispatch_for_log", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dispatcher", "dispatch.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rest = text[2:].strip() if text.startswith("--") else text
        if mod.path_tokens(rest.split(" -- ", 1)[0].strip()):
            return
    except Exception:
        return
    sys.stderr.write(
        "warning: the dispatcher cannot read a path from this %s line, so R3 will not count the\n"
        "file. Open the text with the repo-relative path, then ' -- ' or ': ' and the description.\n"
        "Writing the line as given.\n" % action)


def append(agent, action, text):
    action = action.upper().strip()
    if action not in ACTIONS:
        sys.stderr.write("refusing: %r is not a known action verb. Known: %s\n"
                         % (action, ", ".join(sorted(ACTIONS))))
        return 1
    if not re.fullmatch(r"[a-z0-9-]+", agent):
        sys.stderr.write("refusing: agent id %r must be lowercase kebab (e.g. claude-code)\n" % agent)
        return 1
    text = " ".join(text.split())
    if not text:
        sys.stderr.write("refusing: empty description\n")
        return 1
    warn_bare_path(text)
    warn_unparsed_path(action, text)

    # THE POINT OF THIS TOOL: the clock is read here, in the same call that writes.
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    _raw, rows, _mal = parse(LOG)
    if rows and stamp < rows[-1]["ts"]:
        sys.stderr.write(
            "refusing: this append would create an inversion. Clock says %s but the last\n"
            "entry is %s. Something wrote ahead of the clock (a script's own self-log, or a\n"
            "machine time change). Resolve the ordering before appending.\n" % (stamp, rows[-1]["ts"]))
        return 2

    line = "[%s] [%s] %s -- %s" % (stamp, agent, action, text)

    # read-modify-write so the result is exactly one entry, one trailing newline,
    # regardless of whether the file previously ended with a blank line.
    with open(LOG, encoding="utf-8") as fh:
        body = fh.read().rstrip("\n")
    with open(LOG, "w", encoding="utf-8", newline="") as fh:
        fh.write(body + "\n" + line + "\n")

    print(line)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate context/log.md (default)")
    ap.add_argument("--all", action="store_true",
                    help="with --check: also validate every rotated month in archive/ledgers/, in order")
    ap.add_argument("--rotate", action="store_true",
                    help="move every month before this one into archive/ledgers/YYYY-MM/ (rounds step 10e)")
    ap.add_argument("--dry-run", action="store_true", help="with --rotate: report, write nothing")
    ap.add_argument("--hook", action="store_true", help="emit hook JSON instead of plain text")
    ap.add_argument("--event", default="Stop", help="hookEventName to echo back (Stop, PostToolUse, ...)")
    ap.add_argument("--gate-on-log-path", action="store_true",
                    help="read hook JSON from stdin and exit 0 silently unless it touched context/log.md. "
                         "Keeps the PostToolUse hook free of any jq dependency (jq is not installed here).")
    ap.add_argument("--append", action="store_true", help="append one entry, stamped from the system clock")
    ap.add_argument("--agent", help="agent id, lowercase kebab (claude-code, night-agent, ...)")
    ap.add_argument("--action", help="action verb (CREATED, MODIFIED, SYNCED, ...)")
    ap.add_argument("--text", help="the description after the -- separator")
    args = ap.parse_args()

    if args.append:
        if not (args.agent and args.action and args.text):
            ap.error("--append needs --agent, --action and --text")
        return append(args.agent, args.action, args.text)

    if args.rotate:
        return rotate(dry_run=args.dry_run)

    if args.gate_on_log_path:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except (ValueError, OSError):
            return 0  # unreadable payload is not an integrity problem
        blob = json.dumps(payload).replace("\\\\", "/").replace("\\", "/").lower()
        if "context/log.md" not in blob:
            return 0  # this edit had nothing to do with the log

    if args.all and not args.hook:
        return check_all()

    problems, info, stats = check()

    if args.hook:
        if problems:
            msg = "brain log.md INTEGRITY FAILURE (%d):\n" % len(problems) + "\n".join("  - " + p for p in problems[:8])
            print(json.dumps({
                "systemMessage": msg,
                "hookSpecificOutput": {
                    "hookEventName": args.event,
                    "additionalContext": msg + "\n\nFix context/log.md before continuing. Classify each stamp "
                                               "against append order (append-only = ground truth) per Correction #50 -- "
                                               "do NOT blanket-restamp. Append with "
                                               "`python skills/brain-log/log.py --append` so the clock is read at write time.",
                },
            }))
        else:
            print(json.dumps({"suppressOutput": True}))
        return 2 if problems else 0

    if problems:
        print("LOG INTEGRITY: %d PROBLEM(S)" % len(problems))
        for p in problems:
            print("  ✗ " + p)
    else:
        print("LOG INTEGRITY CLEAN -- %d entries, newest %s, monotonic since %s"
              % (stats.get("entries", 0), stats.get("newest"), stats.get("baseline")))
    for i in info:
        print("  · " + i)
    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
