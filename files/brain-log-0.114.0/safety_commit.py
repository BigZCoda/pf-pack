#!/usr/bin/env python3
"""safety_commit.py -- the 21:45 safety commit (the owner asked for a nightly safety commit on 2026-09-24).

A day with no rounds used to leave the brain uncommitted (9/23 sat two days, and the Mac clone started behind).
This runs from a Windows scheduled task after the night agent and commits and pushes everything when no
rounds ran today, or when work was logged after today's rounds (2026-10-02). It never replaces rounds; it stops
an unrounded day, or an evening after rounds, from sitting uncommitted.

  python skills/brain-log/safety_commit.py            do it
  python skills/brain-log/safety_commit.py --dry-run  say what it would do, write nothing

What it refuses (playbook step 8, the deletion gate; step 11, the pre-checks):
  - a ROUNDS line dated today with nothing logged after -> rounds ran and nothing since, nothing to do
  - a clean working tree                                  -> nothing to commit
  - more than 20 deleted files in the tree                -> a shell-delete outside Claude (8/31); a human looks first
  - any of the seven key files not ignored by git         -> never commit a token
  - any file it would commit over 95 MB                   -> GitHub refuses a file over 100 MB on push; the 10/01 run
                                                             committed a 141 MB zip and every push failed until 10/02
                                                             (brain-central T-0097). Each such file is named, with its
                                                             size, on stdout and in a FLAGGED log line; a file over
                                                             50 MB (GitHub's warning size) is named and still committed.
Every outcome is one line on stdout (the task's history) and, when it commits, one SYNCED line through log.py.

The push is a person's choice (2026-11-11): the viewer's Settings page has a switch, Send this brain to my GitHub each
night, kept as `nightly_backup` in viewer/settings.json. With it off the commit is still made on this computer and
nothing is pushed. A settings file that is there and does not read counts as off: a person who turned the backup off
is never pushed against that choice by a broken file. With no settings file, or no such line, the push runs as before.
"""
import datetime as dt
import json
import os
import subprocess
import sys

BRAIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# 2026-10-14 (the 10/14 sweep, LS-001): Claude SetupToken.txt joined, the sixth key file (added 10/06).
KEY_FILES = ["APIZZLE.txt", "PF App API.txt", "Onboarding API.txt", "pfk_key.txt", "deepseek_key.txt", "Claude SetupToken.txt", "hf_key.txt", "typeform_key.txt", "tally_key.txt",
             "viewer/sharing-signin.json"]   # the sharing sign-in (2026-11-09): a key file that lives in the viewer's own folder
MAX_DELETIONS = 20
MB = 1024 * 1024
MAX_FILE_MB = 95    # GitHub refuses a file over 100 MB on push; the guard leaves a margin (T-0097)
WARN_FILE_MB = 50   # GitHub warns on a file over 50 MB; named, still committed


def run(args, check=True):
    return subprocess.run(args, cwd=BRAIN, capture_output=True, text=True, check=check)


def backup_setting():
    """(push, why not): whether tonight's commit is also sent to GitHub."""
    path = os.path.join(BRAIN, "viewer", "settings.json")
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
    except FileNotFoundError:
        return True, ""
    except Exception:  # noqa: BLE001 -- unreadable: keep it on this computer, and say so
        return False, "viewer/settings.json does not read, so the choice about the nightly backup is not known"
    if isinstance(d, dict) and d.get("nightly_backup") is False:
        return False, "the nightly backup to GitHub is off in the viewer's Settings"
    return True, ""


def files_to_commit():
    """(path, bytes) for every file `git add -A` would stage: tracked files changed against HEAD and untracked files
    git does not ignore, each listed singly (git status folds an untracked folder into one line). Deleted paths have
    no size and are skipped."""
    def names(args):
        r = subprocess.run(args, cwd=BRAIN, capture_output=True, encoding="utf-8", errors="replace", check=False)
        return [x for x in r.stdout.split("\0") if x] if r.returncode == 0 else []
    paths = set(names(["git", "diff", "--name-only", "-z", "--no-renames", "HEAD"]))
    paths |= set(names(["git", "ls-files", "-z", "--others", "--exclude-standard"]))
    out = []
    for rel in sorted(paths):
        full = os.path.join(BRAIN, rel)
        if os.path.isfile(full):
            out.append((rel, os.path.getsize(full)))
    return out


def main():
    unknown = [a for a in sys.argv[1:] if a != "--dry-run"]
    if unknown:
        # An unrecognized flag must never fall through to a real commit and push (2026-09-28: a --help run committed
        # and pushed 145 paths mid-rounds).
        print("usage: python skills/brain-log/safety_commit.py [--dry-run]   (unknown argument: %s; nothing done)" % " ".join(unknown))
        return 2
    dry = "--dry-run" in sys.argv
    today = dt.date.today().isoformat()
    log_path = os.path.join(BRAIN, "context", "log.md")
    # Rounds ran today: the commit still runs when work was logged AFTER the rounds line (2026-10-02: an evening
    # session built two viewer releases and a correction after a 15:12 rounds, and the old rule would have left
    # all of it uncommitted). Only a day whose newest log line IS the rounds line has nothing to do.
    rounds_line, lines_after = None, 0
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.startswith("[" + today):
                continue
            if "] ROUNDS" in line[:60]:
                rounds_line, lines_after = line.strip(), 0
            elif rounds_line is not None:
                lines_after += 1
    after_rounds = rounds_line is not None
    if after_rounds and lines_after == 0:
        print(f"safety commit: rounds ran today ({rounds_line[:60]}...) and nothing was logged since, nothing to do")
        return 0
    status = run(["git", "status", "--porcelain"]).stdout.splitlines()
    if not status:
        print("safety commit: working tree clean, nothing to do")
        return 0
    deletions = sum(1 for l in status if l[:2].strip().startswith("D"))
    if deletions > MAX_DELETIONS:
        print(f"safety commit: REFUSED, {deletions} deleted files in the tree (gate {MAX_DELETIONS}); a human looks first")
        return 2
    for k in KEY_FILES:
        r = run(["git", "check-ignore", k], check=False)
        if r.returncode != 0:
            print(f"safety commit: REFUSED, key file not ignored by git: {k}")
            return 2
    logtool = os.path.join(BRAIN, "skills", "brain-log", "log.py")

    def log(action, text):
        subprocess.run([sys.executable, logtool, "--append", "--agent", "safety-commit", "--action", action,
                        "--text", text], cwd=BRAIN, check=False)

    # The size guard (T-0097): a file GitHub will refuse is caught here, by name, before anything is committed.
    sized = files_to_commit()
    big = [(p, b) for p, b in sized if b > MAX_FILE_MB * MB]
    large = [(p, b) for p, b in sized if WARN_FILE_MB * MB < b <= MAX_FILE_MB * MB]
    for p, b in large:
        print(f"safety commit: WARNING, {p} is {b / MB:.1f} MB (GitHub warns over {WARN_FILE_MB} MB); it is committed")
    if big:
        named = "; ".join(f"{p} ({b / MB:.1f} MB)" for p, b in big)
        if not dry:
            for p, b in big:
                log("FLAGGED", f"{p} -- safety commit REFUSED: {b / MB:.1f} MB, over the {MAX_FILE_MB} MB guard (GitHub refuses a file "
                               f"over 100 MB on push); nothing committed tonight; ignore it in .gitignore or move it out of the brain")
        print(f"safety commit: REFUSED, {len(big)} file(s) over {MAX_FILE_MB} MB, which GitHub refuses on push: {named}; "
              f"ignore or move {'it' if len(big) == 1 else 'them'} and the next run commits")
        return 2
    n = len(status)
    why = f"work logged after today's rounds ({lines_after} log lines since)" if after_rounds else "no rounds ran today"
    msg = f"Safety commit (after rounds) {today}" if after_rounds else f"Safety commit (no rounds ran) {today}"
    if large:
        why += "; over %d MB and committed: %s" % (WARN_FILE_MB, ", ".join(f"{p} ({b / MB:.1f} MB)" for p, b in large))
    push_on, why_off = backup_setting()
    if dry:
        tail = "and push origin main" if push_on else f"and keep it on this computer ({why_off})"
        print(f"safety commit: DRY RUN, would commit {n} changed paths ({deletions} deletions) as '{msg}' {tail}")
        return 0

    # This line is written before the commit so it travels in it. It claims the commit only; the push is
    # reported by its own line below once its result is known (2026-09-28: the old wording said "pushed"
    # before the push ran, and the 9/27 push failed while the log said it had landed).
    follows = "push to origin main follows" if push_on else f"kept on this computer, not pushed: {why_off}"
    log("SYNCED", f"git: safety commit of {n} changed paths, {why}, as '{msg}'; {follows}")
    run(["git", "add", "-A"])
    run(["git", "commit", "-q", "-m", msg, "-m",
         "Automatic 21:45 commit by skills/brain-log/safety_commit.py so an unrounded day never sits uncommitted. "
         "Rounds still owes the state files.\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"])
    if not push_on:
        print(f"safety commit: committed {n} changed paths as '{msg}' on this computer; not pushed: {why_off}")
        return 0
    push = run(["git", "push", "origin", "main"], check=False)
    if push.returncode != 0:
        reason = (push.stderr or push.stdout).strip().replace("\n", " ")[:200]
        log("FAILED", f"git: the safety commit '{msg}' is local only; git push origin main failed: {reason}")
        print(f"safety commit: committed {n} paths as '{msg}' but the push FAILED: {reason}")
        return 1
    print(f"safety commit: committed and pushed {n} changed paths as '{msg}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
