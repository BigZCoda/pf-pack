#!/usr/bin/env python3
"""sharing-project.test.py -- sharing round four, the engine: a whole project into a team brain, and the plan for moving
a team copy (move_copy.py plan), on scratch brains and a scratch copy only. `apply` is never run here. One ok / FAIL
line per claim; exit 1 on any failure.
"""
import builtins
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

os.environ["SHARING_OFFLINE"] = "1"   # this run, and every process it starts, never reaches a real service
HERE = os.path.dirname(os.path.abspath(__file__))
RAW_OPEN = builtins.open
FAILS = []


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  -- " + str(detail)[:300]) if detail else ""))
    if not ok:
        FAILS.append(what)


TMP = tempfile.mkdtemp(prefix="sharing-project-test-")
SVC = os.path.join(TMP, "service")
SAM, RILEY, COPY = os.path.join(TMP, "sam"), os.path.join(TMP, "riley"), os.path.join(TMP, "team-copy")
TEAM = "projects/meetup/meetup-tasks.md"


def put(root, rel, text):
    ap = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with RAW_OPEN(ap, "w", encoding="utf-8", newline="\n") as f:
        f.write(text if isinstance(text, str) else json.dumps(text, indent=1))


def get(root, rel):
    with RAW_OPEN(os.path.join(root, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


def build(root, person, display, holons):
    put(root, "context/log.md", "# Brain Operations Log\n\n## Log\n\n")
    put(root, "context/holon-registry.json", {"holons": holons})
    put(root, "viewer/settings.json", {"owner": person, "display_name": display, "sharing_service": {"carrier": "local", "root": SVC}})
    put(root, "people/readme.md", "# people/\n")


build(SAM, "sam", "Sam", [
    {"id": "meetup", "name": "Spring meetup", "path": "projects/meetup/", "sharing": "team", "tasks": TEAM},
    {"id": "home", "name": "Home", "path": "projects/home/", "sharing": "private", "tasks": "projects/home/home-tasks.md"},
    {"id": "client", "name": "Client", "path": "projects/client/", "sharing": "employer", "tasks": "projects/client/client-tasks.md"}])
put(SAM, TEAM, "# Meetup -- tasks\n\n## Inbox\n\n- [ ] T-0001 2026-11-01 @sam · Book the venue\n"
               "- [?] Q-0001 2026-11-01 @sam → @riley · Which day works, Friday or Saturday? · options:Friday | Saturday\n"
               "- [x] T-0002 2026-11-01 @sam · Make the list · done:2026-11-02\n"
               "- [ ] T-0003 2026-11-01 @sam · Print the badges [private]\n")
put(SAM, "projects/home/home-tasks.md", "# Home\n\n## Inbox\n\n- [ ] T-0001 2026-11-01 @sam · Water the plants\n")
put(SAM, "projects/client/client-tasks.md", "# Client\n\n## Inbox\n\n- [ ] T-0001 2026-11-01 @sam · Draft the plan\n")
put(SAM, "projects/meetup/venue.md", "# The venue\n\nThe hall holds sixty.\n[private] the owner's number\n")
put(SAM, "projects/meetup/budget.md", "# Budget\n\nForty a head.\n")
put(SAM, "threads/meetup-thread.md", "---\ntitle: The meetup\nproject: meetup\npeople:\n  - riley\n---\n\n# The meetup\n\nWhere it stands.\n")
build(RILEY, "riley", "Riley", [{"id": "work", "name": "Work", "path": "projects/work/", "sharing": "private",
                                 "tasks": "projects/work/work-tasks.md"}])
put(RILEY, "projects/work/work-tasks.md", "# Work\n\n## Inbox\n\n- [ ] T-0001 2026-11-01 @riley · Water the plants\n")


def load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


share = load("sharing_share_project_test", os.path.join(HERE, "share.py"))
eng = share.engine()


def items(brain, rel):
    t = eng.tasks_for(brain)
    p = os.path.join(brain, *rel.split("/"))
    return t.parse(t.read(p))["items"] if os.path.isfile(p) else []


def apply(brain, rel, action, **a):
    t = eng.tasks_for(brain)
    return t.apply(os.path.join(brain, *rel.split("/")), rel, action, agent="sharing-test", **a)


def sign(brain, email):
    eng.sign_in_start(brain, email)
    ok, line = eng.sign_in_finish(brain, email, get(SVC, "outbox/%s.txt" % email).strip())
    assert ok, line


def registry_row(brain, hid):
    return next(h for h in json.loads(get(brain, "context/holon-registry.json"))["holons"] if h["id"] == hid)


try:
    sign(SAM, "sam@example.com")
    t = eng.make_team(SAM, "crew", "The crew")
    inv = eng.invite(SAM, "riley@example.com", "Riley", team="crew")
    sign(RILEY, "riley@example.com")
    acc = eng.accept(RILEY, invite_id=eng.invites(RILEY)["invites"][0]["id"])
    eng.sync(SAM)
    RL = "shared/%s/%s-tasks.md" % (acc["space"], acc["space"])

    r = eng.share_project(SAM, "crew", "meetup")
    check(r["ok"] and r["counts"] == {"tasks": 1, "questions": 1, "threads": 1, "files": 2}
          and r["line"] == "Shared the Spring meetup project with The crew: 1 task, 1 question, 1 thread and 2 files.",
          "share_project shares the open items, the subject files and the text files of a project, through the gate", r)
    check(registry_row(SAM, "meetup")["sharing"] == "space:crew", "the project's registry row says which space it is shared into")
    eng.sync(RILEY)
    lst = get(RILEY, RL)
    got = items(RILEY, RL)
    check("## Milestone — Spring meetup" in lst and {i["text"] for i in got} == {"Book the venue", "Which day works, Friday or Saturday?"}
          and all(i["milestone"] == "Spring meetup" for i in got),
          "on the other side the project is the space's own list, under a heading of its own", [(i["text"], i["milestone"]) for i in got])
    check(os.path.isfile(os.path.join(RILEY, "shared", acc["space"], "files", "venue.md"))
          and "owner's number" not in get(RILEY, "shared/%s/files/venue.md" % acc["space"])
          and os.path.isfile(os.path.join(RILEY, "shared", acc["space"], "threads", "meetup-thread.md")),
          "its files and its thread arrive, cleaned")
    apply(SAM, TEAM, "add", text="Order the chairs", owner="@sam")
    eng.sync(SAM)
    eng.sync(RILEY)
    check(any(i["text"] == "Order the chairs" and i["milestone"] == "Spring meetup" for i in items(RILEY, RL)),
          "from then on a check shares what is new on it")
    r2 = eng.share_project(SAM, "crew", "client")
    check(not r2["ok"] and "belongs to an employer" in r2["line"] and registry_row(SAM, "client")["sharing"] == "employer",
          "an employer's project is refused and its row is left as it was", r2["line"])
    r3 = eng.unshare_project(SAM, "crew", "meetup")
    eng.sync(RILEY)
    sent = json.loads(get(SAM, "shared/crew/sent.json"))
    open_left = [i for i in items(RILEY, RL) if i["mark"] in " ?"]
    check(r3["ok"] and registry_row(SAM, "meetup")["sharing"] == "team" and not sent["items"] and not sent.get("files")
          and not open_left and "Stopped sharing the Spring meetup project with The crew" in r3["line"],
          "unshare_project stops, takes all of it back, and puts the row back as it was", (r3["line"], open_left))

    # ---------------------------------------------------------------- the plan for moving a team copy (scratch only)
    for rel in ("projects/meetup/meetup-tasks.md", "projects/meetup/budget.md"):
        put(COPY, rel, get(SAM, rel))
    put(COPY, "projects/meetup/venue.md", "# The venue\n\nThe hall holds sixty.\n")
    put(COPY, "team-brain.json", {"member": "riley"})
    before = {os.path.relpath(os.path.join(d, f), COPY): os.path.getmtime(os.path.join(d, f)) for d, _s, fs in os.walk(COPY) for f in fs}
    out = subprocess.run([sys.executable, os.path.join(HERE, "move_copy.py"), "plan", "--member", "riley", "--copy", COPY, "--brain", SAM],
                         capture_output=True, text=True, encoding="utf-8")
    lines = out.stdout.strip().split("\n")
    check(out.returncode == 0 and lines[-1] == "CLEAN" and any("same                projects/meetup/venue.md" in l for l in lines)
          and any("made for the copy   team-brain.json" in l for l in lines),
          "a copy that matches what the space would hold plans CLEAN, file by file", out.stdout[-400:])
    put(COPY, "projects/meetup/budget.md", "# Budget\n\nFifty a head.\n")
    put(COPY, "projects/meetup/old-notes.md", "Old notes\n")
    os.remove(os.path.join(COPY, "projects", "meetup", "venue.md"))
    out = subprocess.run([sys.executable, os.path.join(HERE, "move_copy.py"), "plan", "--member", "riley", "--copy", COPY, "--brain", SAM],
                         capture_output=True, text=True, encoding="utf-8")
    lines = out.stdout.strip().split("\n")
    check(out.returncode == 1 and lines[-1] == "3 differences" and any(l.strip().startswith("differs") and "budget.md" in l for l in lines)
          and any(l.strip().startswith("copy only") and "old-notes.md" in l for l in lines)
          and any(l.strip().startswith("space only") and "venue.md" in l for l in lines),
          "every difference is named, and the last line counts them", out.stdout[-400:])
    after = {os.path.relpath(os.path.join(d, f), COPY) for d, _s, fs in os.walk(COPY) for f in fs}
    check(after == {"projects/meetup/meetup-tasks.md".replace("/", os.sep), "projects/meetup/budget.md".replace("/", os.sep),
                    "projects/meetup/old-notes.md".replace("/", os.sep), "team-brain.json"},
          "plan writes nothing in the copy", sorted(after))
    out = subprocess.run([sys.executable, os.path.join(HERE, "move_copy.py"), "apply", "--member", "riley", "--copy", COPY, "--brain", SAM],
                         capture_output=True, text=True, encoding="utf-8")
    check(out.returncode == 2 and "only with the owner and the member present" in out.stdout,
          "apply refuses unless the owner and the member are both present", out.stdout)
except Exception:
    check(False, "the run reached its end", traceback.format_exc()[-1500:])
    print(traceback.format_exc())

print("")
print("%d claim(s) failed" % len(FAILS) if FAILS else "all claims hold")
print("scratch: %s" % TMP)
sys.exit(1 if FAILS else 0)
