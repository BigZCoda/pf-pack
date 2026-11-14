#!/usr/bin/env python3
"""skills/sharing/move_copy.py -- the move of a member's team copy onto the sharing service (round four).

    python skills/sharing/move_copy.py plan --member <name> --copy <the copy's folder> [--brain <folder>]
    python skills/sharing/move_copy.py apply --member <name> --copy <folder> --space <name> --both-present

`plan` reads, and writes nothing: file by file, what the copy holds, what the space would hold, and every difference.
Its last line is CLEAN or the count of differences. `apply` is run only with the owner and the member present (the flag
says so): it shares each team-tier project of the brain into the member's space and leaves the copy exactly as it is.
Nothing in the copy is moved or deleted by either. Standard library only. Spec: skills/sharing/readme.md, Round four.
"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# what the copy holds that the export makes for the copy itself, never a file of the brain's
COPY_OWN = {"team-brain.json", "CLAUDE.md", "WHATS-NEW.md", "context/log.md", "context/holon-registry.json",
            "context/mentee-content-manifest.json", "context/maps-manifest.json", "requests/readme.md"}
SKIP_DIRS = {".git", "requests", "node_modules", "__pycache__", ".obsidian"}


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.modules[name] = m
    return m


def _files(root):
    out = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            out.append(os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/"))
    return sorted(out)


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def team_rows(gate, brain):
    """(path prefix, id, tasks) of every registry row whose sharing is team."""
    return [(gate._norm(h.get("path")).rstrip("/") + "/", h.get("id"), gate._norm(h.get("tasks")) if h.get("tasks") else None)
            for h in gate.registry_rows(brain) if str(h.get("sharing") or "").lower() == "team" and h.get("path")]


def _tier(gate, brain, rel):
    """The sharing of the most specific registry row covering rel (the export's own rule)."""
    best, best_len = None, -1
    for h in gate.registry_rows(brain):
        hp = gate._norm(h.get("path")).rstrip("/")
        if hp and (rel == hp or rel.startswith(hp + "/")) and len(hp) > best_len:
            best, best_len = h, len(hp)
    return str((best or {}).get("sharing") or "").lower()


def space_would_hold(gate, brain):
    """{rel: (what, text or None)} for what the space would hold of the brain's team-tier projects: each text file
    through the whole-text gate (a list as its open items), and why each other file would not go."""
    out = {}
    for prefix, hid, tasks in team_rows(gate, brain):
        root = os.path.join(brain, *prefix.rstrip("/").split("/"))
        for rel_in in _files(root) if os.path.isdir(root) else []:
            rel = prefix + rel_in
            if _tier(gate, brain, rel) != "team":
                continue
            if tasks and rel == tasks:
                out[rel] = ("a list, shared as its open items", None)
                continue
            text = _read(os.path.join(brain, *rel.split("/")))
            clean, why = gate.render_text(brain, rel, text, None)
            out[rel] = ("a file", clean) if clean is not None else ("stays home: " + why, None)
    return out


def plan(brain, copy, member):
    """The lines of the plan; the last is CLEAN or the count of differences. Reads only."""
    eng = _load("sharing_engine_for_move_copy", os.path.join(HERE, "engine.py"))
    gate = eng.gate
    lines = ["The team copy for %s, against what a shared space would hold." % eng.clean_name(member, "the member")]
    if not os.path.isdir(copy):
        return lines + ["There is no copy at the folder given.", "1 difference"]
    held = {rel: rel for rel in _files(copy)}
    space = space_would_hold(gate, brain)
    diffs = 0
    for rel in sorted(set(held) | set(space)):
        if rel in COPY_OWN:
            lines.append("  made for the copy   %s" % rel)
            continue
        if rel not in space:
            if rel.startswith("people/"):
                lines.append("  copy only           %s (a card goes section by section)" % rel)
            else:
                lines.append("  copy only           %s" % rel)
            diffs += 1
            continue
        what, text = space[rel]
        if rel not in held:
            if text is None and not what.startswith("a list"):
                lines.append("  stays home          %s (%s)" % (rel, what[len("stays home: "):]))
                continue
            lines.append("  space only          %s" % rel)
            diffs += 1
            continue
        if what.startswith("a list"):
            lines.append("  same list           %s (%s)" % (rel, what))
            continue
        if text is None:
            lines.append("  in the copy only    %s (the space would not take it: %s)" % (rel, what[len("stays home: "):]))
            diffs += 1
            continue
        mine = (_read(os.path.join(copy, *rel.split("/"))) or "").replace("\r\n", "\n").rstrip("\n")
        if mine == text.replace("\r\n", "\n").rstrip("\n"):
            lines.append("  same                %s" % rel)
        else:
            a, b = mine.split("\n"), text.split("\n")
            n = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
            lines.append("  differs             %s (%d line%s)" % (rel, n, "" if n == 1 else "s"))
            diffs += 1
    lines.append("CLEAN" if not diffs else "%d difference%s" % (diffs, "" if diffs == 1 else "s"))
    return lines


def apply(brain, copy, member, space):
    """Share each team-tier project into the member's space. The copy is not touched."""
    eng = _load("sharing_engine_for_move_copy", os.path.join(HERE, "engine.py"))
    out = []
    for _prefix, hid, _tasks in team_rows(eng.gate, brain):
        r = eng.share_project(brain, space, hid)
        out.append(r["line"])
    out.append("The copy at the folder given was left exactly as it is.")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="the move of a member's team copy onto the sharing service")
    ap.add_argument("action", choices=["plan", "apply"])
    ap.add_argument("--member", required=True)
    ap.add_argument("--copy", help="the team copy's folder (required: nothing is guessed)")
    ap.add_argument("--brain", help="the owner's brain (default BRAIN_ROOT, else the brain this file sits in)")
    ap.add_argument("--space", help="on apply: the member's space")
    ap.add_argument("--both-present", action="store_true", help="on apply: the owner and the member are both here")
    a = ap.parse_args(argv)
    brain = os.path.abspath(a.brain or os.environ.get("BRAIN_ROOT") or os.path.join(HERE, "..", ".."))
    if not a.copy:
        print("Say where the team copy is: --copy <folder>.")
        return 2
    if a.action == "plan":
        lines = plan(brain, os.path.abspath(a.copy), a.member)
        for line in lines:
            print(line)
        return 0 if lines[-1] == "CLEAN" else 1
    if not (a.both_present and a.space):
        print("The move runs only with the owner and the member present: pass --space and --both-present.")
        return 2
    for line in apply(brain, os.path.abspath(a.copy), a.member, a.space):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
