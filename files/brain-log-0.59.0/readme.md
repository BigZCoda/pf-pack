# skills/brain-log/ — the only correct way to write context/log.md

**What's in here.** `log.py`, the tool CLAUDE.md Section 7 requires every agent to use, and nothing else. It appends entries, validates the file, and rotates old months out. `__pycache__/` is build noise and is ignored.

**What it does.** `--append --agent <id> --action <VERB> --text "<what happened>"` writes one line and reads the system clock in the same call. There is deliberately no argument that accepts a timestamp. `--check` validates ordering, verbs and agent ids and runs automatically from the PostToolUse, Stop and SessionEnd hooks in `~/.claude/settings.json`. `--rotate` moves months before the current one into `archive/ledgers/YYYY-MM/`.

**Why it matters.** `context/dispatcher-cursor.md` bookmarks by timestamp, so a line stamped behind an advanced cursor is skipped forever and that work is never routed. Every observed instance of the drift came from an agent typing a clock by hand.

**Authoritative vs derivative.** Authoritative for how the log is written. The log itself is `context/log.md`; this folder holds only the instrument.

**When to read.** Before writing to the log by any other means, or when `--check` reports a break. Run `python skills/brain-log/log.py --help`, which carries the full rationale, the rotation contract and the monotonicity baseline.

**When NOT to read.** To find out what happened. That is the log, the hot cache and `context/active-session.md`.

**What does NOT belong here.** Log content, other skills' tools, and any wrapper that writes `context/log.md` without going through `log.py`.

**Naming.** One tool, named for what it does. A future helper takes a plain lowercase name in this folder.

**Last touched.** Sept 18, 2026 (readme created, librarian sweep LS-006).

## Monthly rotation (added 2026-09-18, structure pass batch 2 — the owner's yes on brain-central Q-0037)

`python skills/brain-log/log.py --rotate` moves every log line stamped **before the current month**
into `archive/ledgers/YYYY-MM/log-YYYY-MM.md`, one file per month, lines verbatim, and leaves
`context/log.md` holding its header, a managed pointer naming the months present, and the current
month. The same call rotates the second giant ledger's `## Run history` section into the same month
folders as `night-agent-observations-YYYY-MM.md`.

- **Why:** the live log passed **1.1 MB**, four times the ~262 KB read ceiling of the tool that reads
  it (night-agent obs#47). After the first rotation it is 585 KB (1,855 September lines) with 1,160
  lines archived across 2026-06, 2026-07 and 2026-08.
- **It refuses on a dirty `--check`.** Rewriting a file whose ordering is already broken is how a
  rotation turns a reported problem into a lost line.
- **It is idempotent** and it **reconciles and prints** the counts (before = live after + archived),
  so a lost line is loud rather than silent.
- **Runs at rounds step 10e.** `lint.py`'s **L19** is the standing check that it ran.
- **`--check` still validates the live file only** — that is what the three hooks call.
  **`--check --all`** validates the live file and every rotated month in order, plus the joins
  between them (a month may not overlap the next).
- **Readers reach back on their own:** `dispatch.py` reads the live file plus the months its window
  or its cursor line needs, the Brain Viewer's `log_lines(since)` does the same for every one of its
  readers, and lint's L8 and `newest_rounds_day` fall back to the covering month.
- **What does NOT rotate:** the `## Active Observations` section of the night-agent ledger. 44 of its
  91 weighted entries carry dated evidence from more than one month (obs#43 spans 2026-04 to
  2026-09), so a month split would cut one observation's weight history across five files. Its size
  is obs#47's per-entry cap problem (brain-central T-0040), not a rotation problem.

**`--append` also warns (never refuses) on a bare basename.** A log line's first field is its path
field; `dispatch.py`'s `path_tokens()` accepts a bare token that carries a known extension, so
`push.py` counts as a file distinct from `skills/ferryman/push.py` and R3's touched-file counter
double-counts it — the 2026-09-18 scoped sweep (LS-008) found 8 such lines in one window, 116
counted for 102 real. A refusal here would lose the log line, which is worse than a miscounted one,
so it warns to stderr and writes the line as given. **Log full repo-relative paths.**
