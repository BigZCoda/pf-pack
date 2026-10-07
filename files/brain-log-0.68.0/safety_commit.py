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
  - any of the five key files not ignored by git          -> never commit a token
Every outcome is one line on stdout (the task's history) and, when it commits, one SYNCED line through log.py.
"""
import datetime as dt
import os
import subprocess
import sys

BRAIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KEY_FILES = ["APIZZLE.txt", "PF App API.txt", "Onboarding API.txt", "pfk_key.txt", "deepseek_key.txt"]
MAX_DELETIONS = 20


def run(args, check=True):
    return subprocess.run(args, cwd=BRAIN, capture_output=True, text=True, check=check)


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
    n = len(status)
    why = f"work logged after today's rounds ({lines_after} log lines since)" if after_rounds else "no rounds ran today"
    msg = f"Safety commit (after rounds) {today}" if after_rounds else f"Safety commit (no rounds ran) {today}"
    if dry:
        print(f"safety commit: DRY RUN, would commit {n} changed paths ({deletions} deletions) as '{msg}' and push origin main")
        return 0
    logtool = os.path.join(BRAIN, "skills", "brain-log", "log.py")

    def log(action, text):
        subprocess.run([sys.executable, logtool, "--append", "--agent", "safety-commit", "--action", action,
                        "--text", text], cwd=BRAIN, check=False)

    # This line is written before the commit so it travels in it. It claims the commit only; the push is
    # reported by its own line below once its result is known (2026-09-28: the old wording said "pushed"
    # before the push ran, and the 9/27 push failed while the log said it had landed).
    log("SYNCED", f"git: safety commit of {n} changed paths, {why}, as '{msg}'; push to origin main follows")
    run(["git", "add", "-A"])
    run(["git", "commit", "-q", "-m", msg, "-m",
         "Automatic 21:45 commit by skills/brain-log/safety_commit.py so an unrounded day never sits uncommitted. "
         "Rounds still owes the state files.\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"])
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
