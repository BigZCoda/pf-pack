#!/usr/bin/env python3
"""hooks.py -- the hooks a brain runs on its own, so a session starts knowing where things stand.

  python skills/brain-hooks/hooks.py session-start   SessionStart: the brain's state as context before the first turn
  python skills/brain-hooks/hooks.py viewer          SessionStart: the viewer answering on 127.0.0.1:8765, started if not
  python skills/brain-hooks/hooks.py log-check       PostToolUse / Stop / SessionEnd: the log's timestamps still in order
  python skills/brain-hooks/hooks.py session-end     SessionEnd: a reminder when the last-session file has gone stale
  python skills/brain-hooks/hooks.py precompact      PreCompact: a breadcrumb in the log of what was in motion
  python skills/brain-hooks/hooks.py --check         says what each hook would do here, changes nothing

Registered in the brain's .claude/settings.json by install.py (the same folder). Every hook finds the brain from its own
place (two folders up), never from a fixed path, so a brain can live anywhere on any computer. Every hook exits 0 and
prints at most one JSON object: a hook never stops a session or a write. The brain's own CLAUDE.md is the rulebook; these
only put the right files in front of Claude at the right moment.
"""
import datetime as dt
import json
import os
import re
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.dirname(os.path.dirname(HERE))
PORT = int(os.environ.get("VIEWER_PORT") or 8765)
CAP = 6000            # characters of any one file put into the session's context


def rel(*parts):
    return os.path.join(BRAIN, *parts)


def read(path, cap=CAP):
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            t = f.read()
    except OSError:
        return None
    return t if len(t) <= cap else t[:cap] + "\n\n[... cut here; read the file for the rest]"


def emit_context(event, text):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def emit_message(text):
    print(json.dumps({"systemMessage": text}))


def py():
    return sys.executable or "python"


def log_line(action, text):
    """One line in context/log.md through the brain's own log tool, which reads the clock itself."""
    tool = rel("skills", "brain-log", "log.py")
    if not os.path.isfile(tool):
        return
    try:
        subprocess.run([py(), tool, "--append", "--agent", "brain-hooks", "--action", action, "--text", text],
                       cwd=BRAIN, capture_output=True, timeout=15,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        pass


# ---- session start: the state of the brain, before the first turn ----

def section(text, heading_re):
    """The lines of one ## section, heading included, up to the next ## heading."""
    out, on = [], False
    for line in (text or "").splitlines():
        if re.match(r"^## ", line):
            if on:
                break
            on = bool(re.match(heading_re, line))
        if on:
            out.append(line)
    return "\n".join(out).strip()


def first_block(text, lines=40):
    """The top of the last-session file: its first session block, or its first lines."""
    t = (text or "").splitlines()
    starts = [i for i, l in enumerate(t) if re.match(r"^## ", l)]
    if starts:
        end = starts[1] if len(starts) > 1 else min(len(t), starts[0] + lines)
        return "\n".join(t[starts[0]:min(end, starts[0] + lines)]).strip()
    return "\n".join(t[:lines]).strip()


def open_work():
    tool = rel("skills", "brain-tasks", "tasks.py")
    if not os.path.isfile(tool):
        return None
    try:
        r = subprocess.run([py(), tool, "list", "--open"], cwd=BRAIN, capture_output=True, text=True, timeout=20,
                           encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if len(lines) > 60:
        lines = lines[:60] + ["[... %d more lines; run `python skills/brain-tasks/tasks.py list --open`]" % (len(lines) - 60)]
    return "\n".join(lines)


def unread_presses():
    """Batches the viewer wrote to context/answers-inbox.md that no session has marked processed."""
    t = read(rel("context", "answers-inbox.md"), cap=10 ** 7)
    if not t:
        return 0
    n = 0
    for block in re.split(r"(?m)^(?=## Batch)", t):
        if block.startswith("## Batch") and "processed:" not in block:
            n += 1
    return n


def session_start():
    today = dt.date.today()
    parts = ["# Session start: this brain, read before your first reply", "",
             "**Today:** %s (%s)" % (today.isoformat(), today.strftime("%A"))]
    claude_md = read(rel("CLAUDE.md"), cap=4000) or ""
    if "{{INHABITANT}}" in claude_md:
        parts += ["", "## Not set up yet",
                  "CLAUDE.md still says {{INHABITANT}}. Whatever the first message says, start by running SETUP.md with "
                  "the person (about five minutes, once)."]
    last = read(rel("context", "active-session.md"))
    parts += ["", "## Last session (the top of context/active-session.md)",
              first_block(last) if last else "context/active-session.md is missing: say so in the recap."]
    focus = read(rel("context", "current-focus.md"), cap=20000)
    reminders = section(focus, r"^## .*Standing reminders") if focus else ""
    if reminders:
        parts += ["", reminders]
    work = open_work()
    if work:
        parts += ["", "## Open work (tasks.py list --open)", work]
    n = unread_presses()
    if n:
        parts += ["", "## %d batch%s from the viewer not read yet" % (n, "" if n == 1 else "es"),
                  "Notes, answers and Send presses from the viewer wait in context/answers-inbox.md. Read each batch "
                  "with no `processed:` line, act on it, then add `processed: <date time> · <one plain sentence to the "
                  "person on what changed>` under it. The viewer shows that sentence on the card they pressed."]
    parts += ["", "## Your first reply",
              "Open with the short recap from CLAUDE.md's boot sequence (step 5): where the brain stands, what is "
              "open and due, the standing reminders, the viewer's address, and one line asking what to work on. If "
              "the first message asks for something specific, answer that, then give the recap in a few lines."]
    emit_context("SessionStart", "\n".join(parts))


# ---- the viewer: answering before the first turn ----

def answering(timeout=2.0):
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=timeout) as s:
            s.sendall(b"GET / HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
            return s.recv(12).startswith(b"HTTP/1.")
    except OSError:
        return False


def start_viewer():
    """serve.py --supervise, detached, so it outlives the session that started it."""
    serve = rel("skills", "brain-viewer", "serve.py")
    if not os.path.isfile(serve):
        return "no viewer in this brain (skills/brain-viewer/serve.py missing)"
    if os.name == "nt":
        # Start-Process leaves the viewer outside the session's process tree; a child started from here would die with it
        cmd = ("Start-Process -FilePath '%s' -ArgumentList 'skills\\brain-viewer\\serve.py','--supervise','--port','%d' "
               "-WorkingDirectory '%s' -WindowStyle Hidden" % (py().replace("'", "''"), PORT, BRAIN.replace("'", "''")))
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], capture_output=True, timeout=20,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        logf = open(rel("viewer", "viewer-start.log"), "ab") if os.path.isdir(rel("viewer")) else subprocess.DEVNULL
        subprocess.Popen([py(), serve, "--supervise", "--port", str(PORT)], cwd=BRAIN, stdin=subprocess.DEVNULL,
                         stdout=logf, stderr=logf, start_new_session=True, close_fds=True)
    return None


def served_brain():
    """The folder the viewer on the port says it serves (GET /api/health), or None when it does not say."""
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/health" % PORT, timeout=3) as r:
            b = json.loads(r.read().decode("utf-8", "replace")).get("brain")
        return os.path.normcase(os.path.abspath(b)) if b else None
    except Exception:  # noqa: BLE001
        return None


def viewer():
    if os.environ.get("BRAIN_HEADLESS_CHILD"):
        return                                     # the viewer's own background helpers never start a second viewer
    url = "http://127.0.0.1:%d/" % PORT
    if answering():
        other = served_brain()
        if other and other != os.path.normcase(BRAIN):
            line = ("The viewer on %s belongs to another brain on this computer (%s), so this brain's viewer was not "
                    "started. To open this one, start it on another port: python skills/brain-viewer/serve.py --port %d"
                    % (url, other, PORT + 10))
            emit_context("SessionStart", "## The viewer\n" + line)
            return
        line = "Answering on %s (already up)." % url
    else:
        why = start_viewer()
        if why:
            line = "Not started: %s." % why
        else:
            up = False
            for _ in range(10):
                time.sleep(1)
                if answering():
                    up = True
                    break
            line = ("Started; answering on %s." % url) if up else (
                "Started but not answering on %s yet. If it stays silent, ask Claude to start the viewer." % url)
    emit_context("SessionStart", "## The viewer\n" + line + " Give this address in the recap.")


# ---- the log check, the stale-session reminder, the compaction breadcrumb ----

def log_check(event):
    tool = rel("skills", "brain-log", "log.py")
    if not os.path.isfile(tool):
        return
    args = [py(), tool, "--check", "--hook", "--event", event]
    if event == "PostToolUse":
        args.append("--gate-on-log-path")          # after a write, check only when the write touched the log
    try:
        r = subprocess.run(args, cwd=BRAIN, capture_output=True, input=sys.stdin.read() if event == "PostToolUse" and not sys.stdin.isatty() else None,
                           text=True, timeout=15, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.stdout.strip():
            print(r.stdout.strip())                # log.py speaks the hook protocol itself; clean is silent
    except (OSError, subprocess.SubprocessError):
        pass


def session_end():
    p = rel("context", "active-session.md")
    try:
        age_h = (time.time() - os.path.getmtime(p)) / 3600
    except OSError:
        return
    if age_h >= 4:
        emit_message("context/active-session.md was last updated about %d hours ago. Next time, say \"I'm done for "
                     "today\" before you close, so the next session picks up where this one left off." % int(age_h))


def precompact():
    cutoff = time.time() - 2 * 3600
    skip = {".git", ".obsidian", ".claude", "archive", "thoughts", "node_modules", "__pycache__"}
    recent = []
    for root, dirs, files in os.walk(BRAIN):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(".md"):
                fp = os.path.join(root, f)
                try:
                    if os.path.getmtime(fp) >= cutoff:
                        recent.append(os.path.relpath(fp, BRAIN).replace("\\", "/"))
                except OSError:
                    pass
    recent.sort()
    shown = ", ".join(recent[:25]) + (" and %d more" % (len(recent) - 25) if len(recent) > 25 else "")
    log_line("MODIFIED", "context compaction: %d brain file(s) changed in the last 2h%s" % (len(recent), (": " + shown) if recent else ""))
    emit_message("The conversation is being compacted. What changed in the last two hours is noted in context/log.md, "
                 "so the work in motion can be picked up again.")


def check():
    print("brain-hooks --check, brain at %s" % BRAIN)
    for name, path in (("CLAUDE.md", rel("CLAUDE.md")), ("last-session file", rel("context", "active-session.md")),
                       ("current focus", rel("context", "current-focus.md")), ("task lists", rel("skills", "brain-tasks", "tasks.py")),
                       ("log tool", rel("skills", "brain-log", "log.py")), ("viewer", rel("skills", "brain-viewer", "serve.py"))):
        print("  %-18s %s" % (name, "found" if os.path.exists(path) else "MISSING (that hook stays quiet)"))
    print("  viewer port %d    %s" % (PORT, "answering" if answering() else "silent (session start would start it)"))
    print("  viewer batches     %d not read yet" % unread_presses())


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    try:
        if cmd == "session-start":
            session_start()
        elif cmd == "viewer":
            viewer()
        elif cmd == "log-check":
            log_check(argv[2] if len(argv) > 2 else "Stop")
        elif cmd == "session-end":
            session_end()
        elif cmd == "precompact":
            precompact()
        elif cmd == "--check":
            check()
        else:
            print(__doc__)
    except Exception:  # noqa: BLE001 -- a hook never stops a session
        pass
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
