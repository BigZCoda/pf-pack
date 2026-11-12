#!/usr/bin/env python3
"""install.py -- register this brain's hooks and commands in .claude/, so they run on their own.

  python skills/brain-hooks/install.py              write .claude/settings.json's hooks and .claude/commands/
  python skills/brain-hooks/install.py --check      say what is registered and what would change, change nothing
  python skills/brain-hooks/install.py --brain <folder>   act on another brain (the assembler passes the new one)

Run once when a brain is built (the assembler does it) and again after this component updates. It is safe to run any
number of times:
  - .claude/settings.json keeps everything already in it. For each hook event, the entries whose command runs
    skills/brain-hooks/ are replaced by this folder's settings.json; every other hook the person added stays.
  - each command in commands/ is copied to .claude/commands/, replacing a file only when the old one is this
    component's (it carries the brain-hooks marker line) or does not exist. A command the person wrote is never touched.
  - .claude/settings.local.json, the person's own, is never read or written.
One line goes to context/log.md through the brain's log tool when anything changed. Exit 0 done or nothing to do, 1 failed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "skills/brain-hooks/"
CMD_MARK = "<!-- brain-hooks:"


def merged(current, ours):
    """current hooks block plus ours: per event, our old entries out, our new ones in, the person's kept."""
    out = dict(current or {})
    for event, groups in (ours or {}).items():
        kept = []
        for g in out.get(event) or []:
            hooks = [h for h in (g.get("hooks") or []) if MARK not in str(h.get("command", "")).replace("\\", "/")]
            if hooks:
                kept.append(dict(g, hooks=hooks))
        out[event] = kept + list(groups)
    return out


def main():
    ap = argparse.ArgumentParser(description="register the brain's hooks and commands in .claude/")
    ap.add_argument("--brain", default=os.path.dirname(os.path.dirname(HERE)))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    brain = os.path.abspath(a.brain)
    # the maintainer's brain runs its own hooks from .claude/settings.local.json; registering these beside them would
    # run every session-start twice. It is known by the tools only it has: the assembler and the viewer's release script.
    if (os.path.isfile(os.path.join(brain, "skills", "assemble-brain", "assemble-brain.py"))
            or os.path.isfile(os.path.join(brain, "skills", "brain-viewer", "release.py"))):
        print("install: refused, %s is the maintainer's brain (it has the assembler or the release script); "
              "these hooks are for the brains built from the kit" % brain)
        return 0
    claude = os.path.join(brain, ".claude")
    sp = os.path.join(claude, "settings.json")
    try:
        ours = json.load(open(os.path.join(HERE, "settings.json"), encoding="utf-8"))["hooks"]
    except (OSError, ValueError, KeyError) as e:
        print("install: this folder's settings.json cannot be read (%s)" % e)
        return 1
    try:
        cur = json.load(open(sp, encoding="utf-8-sig")) if os.path.isfile(sp) else {}
    except ValueError as e:
        print("install: %s is not valid JSON (%s); fix it or move it aside, then run this again" % (sp, e))
        return 1
    new = dict(cur, hooks=merged(cur.get("hooks"), ours))
    changes = []
    if new != cur:
        changes.append(".claude/settings.json hooks (%s)" % ", ".join(sorted(ours)))
    cmd_src = os.path.join(HERE, "commands")
    cmd_dst = os.path.join(claude, "commands")
    copies, kept = [], []
    for f in sorted(os.listdir(cmd_src)) if os.path.isdir(cmd_src) else []:
        if not f.endswith(".md"):
            continue
        src, dst = os.path.join(cmd_src, f), os.path.join(cmd_dst, f)
        body = open(src, encoding="utf-8").read()
        if os.path.isfile(dst):
            old = open(dst, encoding="utf-8", errors="replace").read()
            if CMD_MARK not in old:
                kept.append(f)            # the person's own command of that name
                continue
            if old == body:
                continue
        copies.append(f)
    if copies:
        changes.append(".claude/commands: " + ", ".join("/" + c[:-3] for c in copies))
    if a.check:
        print("install --check, brain at %s" % brain)
        print("  would change: %s" % ("; ".join(changes) if changes else "nothing, all registered"))
        if kept:
            print("  left alone (the person's own): %s" % ", ".join(kept))
        return 0
    if not changes:
        print("install: nothing to do, the hooks and commands are registered")
        return 0
    os.makedirs(cmd_dst, exist_ok=True)
    if new != cur:
        tmp = sp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(new, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, sp)
    for f in copies:
        shutil.copyfile(os.path.join(cmd_src, f), os.path.join(cmd_dst, f))
    print("install: " + "; ".join(changes))
    if kept:
        print("install: left alone (the person's own): %s" % ", ".join(kept))
    tool = os.path.join(brain, "skills", "brain-log", "log.py")
    if os.path.isfile(tool):
        try:
            subprocess.run([sys.executable, tool, "--append", "--agent", "brain-hooks", "--action", "MODIFIED",
                            "--text", "registered the brain's hooks and commands: " + "; ".join(changes)],
                           cwd=brain, capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError):
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
