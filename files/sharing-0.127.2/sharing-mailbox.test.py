#!/usr/bin/env python3
"""sharing-mailbox.test.py -- a mailbox per person, and one send to everyone or to the ones picked (2026-11-11).

  python skills/sharing/sharing-mailbox.test.py

Four invented brains in a temp folder against the stand-in service on disk (SHARING_OFFLINE=1: no real service is
ever reached): two who run a program (Sam, who makes the mailboxes, and Dana) and two people in it (Riley and Jo).
What must hold:
  only an admin's brain makes a mailbox or sends to many; a mailbox reads as the person on the admins' side and as the
  program on the person's side; the second admin's brain joins every mailbox with no press; a task sent to all is one
  copy per mailbox, each the person's own to do, and one person's done mark touches no other copy and not the
  original; sending twice puts nothing there twice; a send to picked mailboxes reaches only those; a question comes
  back answered; a file goes the usual way; what the gate holds back is not sent to anyone; and a person on a
  computer their employer owns still gets what is sent and can answer it.
One ok / FAIL line per claim; exit 1 on any FAIL.
"""
import builtins
import importlib.util
import json
import os
import sys
import tempfile
import traceback

os.environ["SHARING_OFFLINE"] = "1"   # this run, and every process it starts, never reaches a real service
HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  -- " + str(detail)[:400]) if (detail and not ok) else ""))
    if not ok:
        FAILS.append(what)


TMP = tempfile.mkdtemp(prefix="sharing-mailbox-test-")
SVC = os.path.join(TMP, "service")
SAM, DANA, RILEY, JO = (os.path.join(TMP, n) for n in ("sam", "dana", "riley", "jo"))
WORK = "projects/work/work-tasks.md"
ORG = "The Program"


def put(root, rel, text):
    ap = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        f.write(text if isinstance(text, str) else json.dumps(text))


def get(root, rel):
    with open(os.path.join(root, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


def build(root, person, display, ledger, **settings):
    put(root, "context/log.md", "# Brain Operations Log\n\n## Log\n\n")
    put(root, "context/holon-registry.json", {"holons": [
        {"id": "work", "name": "Work", "path": "projects/work/", "sharing": "private", "tasks": WORK}]})
    put(root, "viewer/settings.json", dict({"owner": person, "display_name": display, "project_labels": {"work": "Work"},
                                            "sharing_service": {"carrier": "local", "root": SVC}}, **settings))
    put(root, "people/readme.md", "# people/\n")
    put(root, WORK, "# Work -- tasks\n\n## Inbox\n\n" + ledger)


build(SAM, "sam", "Sam",
      "- [ ] T-0001 2026-11-11 @sam · Fill in the November survey · note:It takes five minutes · steps:[ ] Open the form | [ ] Send it\n"
      "- [?] Q-0001 2026-11-11 @sam → @sam · Which day works for the group call? · options:Thursday | Friday\n"
      "- [ ] T-0002 2026-11-11 @sam · [private] Think about the budget\n"
      "- [ ] T-0003 2026-11-11 @sam · Read the welcome note\n",
      sharing_admin=True, sharing_org=ORG, sharing_admins=[{"name": "Dana", "email": "dana@example.com"}])
build(DANA, "dana", "Dana", "- [ ] T-0001 2026-11-11 @dana · Order lunch\n",
      sharing_admin=True, sharing_org=ORG, sharing_admins=[{"name": "Sam", "email": "sam@example.com"}])
build(RILEY, "riley", "Riley", "- [ ] T-0001 2026-11-11 @riley · Water the plants\n")
build(JO, "jo", "Jo", "- [ ] T-0001 2026-11-11 @jo · Return the library books\n")
put(SAM, "projects/work/welcome.md", "# Welcome\n\nStart here.\n")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


share = load("sharing_share_mailbox_test", os.path.join(HERE, "share.py"))
eng = share.engine()
mb = eng.mailbox


def T(brain):
    return eng.tasks_for(brain)


def items(brain, rel):
    t = T(brain)
    p = os.path.join(brain, *rel.split("/"))
    return t.parse(t.read(p))["items"] if os.path.isfile(p) else []


def apply(brain, rel, action, **a):
    return T(brain).apply(os.path.join(brain, *rel.split("/")), rel, action, agent="sharing-test", **a)


def sign(brain, email):
    eng.sign_in_start(brain, email)
    code = get(SVC, "outbox/%s.txt" % email).strip()
    ok, line = eng.sign_in_finish(brain, email, code)
    assert ok, line


def lst(name):
    return "shared/%s/%s-tasks.md" % (name, name)


def find(brain, rel, words):
    return next((i for i in items(brain, rel) if words in i["text"]), None)


def both(*brains):
    for _ in range(2):
        for b in brains:
            eng.sync(b)


try:
    # ---- 1. only an admin's brain makes a mailbox
    sign(SAM, "sam@example.com")
    r0 = mb.make(RILEY, "x@example.com", "X")
    check(not r0["ok"] and r0["line"] == mb.NOT_ADMIN and mb.boxes(RILEY) == [], "a brain that does not run the program makes no mailbox and lists none", r0)
    r1 = mb.make(SAM, "riley@example.com", "Riley")
    r2 = mb.make(SAM, "jo@example.com", "Jo")
    check(r1["ok"] and r2["ok"] and r1.get("code") and "Riley" in r1["line"] and "Dana can see it too" in r1["line"],
          "an admin makes a mailbox for each person; the line says who else can see it", (r1.get("line"), r2.get("line")))
    r3 = mb.make(SAM, "riley@example.com", "Riley")
    check(not r3["ok"] and "already has a mailbox" in r3["line"], "a second mailbox for the same person is refused in one line", r3.get("line"))
    bx = mb.boxes(SAM)
    check([b["person"] for b in bx] == ["Jo", "Riley"] and not any(b["joined"] for b in bx), "the admin's list names each person, none joined yet", bx)
    reg = json.loads(get(SAM, "context/holon-registry.json"))
    check(any(h.get("name") == "Mailbox: Riley" for h in reg["holons"]), "the registry row says whose mailbox it is")

    # ---- 2. the people join; the second admin's brain joins with no press
    sign(RILEY, "riley@example.com")
    sign(JO, "jo@example.com")
    sign(DANA, "dana@example.com")
    ar = eng.accept(RILEY, invite_id=eng.invites(RILEY)["invites"][0]["id"])
    aj = eng.accept(JO, invite_id=eng.invites(JO)["invites"][0]["id"])
    joined = mb.auto_join(DANA)
    both(SAM, DANA, RILEY, JO)
    rs = [s for s in share.spaces(RILEY) if s.get("carrier") == "service"]
    check(ar["ok"] and aj["ok"] and len(rs) == 1 and rs[0]["label"] == ORG, "on the person's side the mailbox reads as the program", [(s["name"], s["label"]) for s in rs])
    check(len(joined) == 2 and [b["person"] for b in mb.boxes(DANA)] == ["Jo", "Riley"],
          "the second admin's brain joined both mailboxes with no press, and names them by the person", (joined, mb.boxes(DANA)))
    check(all(b["joined"] for b in mb.boxes(SAM)), "the maker's list says both have joined", mb.boxes(SAM))

    # ---- 3. one task to everyone: a copy each, each the person's own
    s1 = mb.send(SAM, "task", {"project": "work", "id": "T-0001"})
    both(SAM, DANA, RILEY, JO)
    rl, jl = lst(rs[0]["name"]), lst([s for s in share.spaces(JO) if s.get("carrier") == "service"][0]["name"])
    ri, ji = find(RILEY, rl, "November survey"), find(JO, jl, "November survey")
    check(s1["ok"] and s1["sent"] == ["Jo", "Riley"] and "Sent “Fill in the November survey” to Jo and Riley." in s1["line"],
          "sending to everyone says who it went to", s1.get("line"))
    check(ri is not None and ji is not None and ri["owner"] == "@riley" and ji["owner"] == "@jo"
          and [s["text"] for s in ri["steps"]] == ["Open the form", "Send it"] and "five minutes" in (ri.get("note") or ""),
          "each person has their own copy, theirs to do, with its steps and note", (ri and ri["owner"], ji and ji["owner"]))
    s1b = mb.send(SAM, "task", {"project": "work", "id": "T-0001"})
    both(SAM, RILEY)
    check(s1b["ok"] and not s1b["sent"] and s1b["there"] == ["Jo", "Riley"]
          and sum(1 for i in items(RILEY, rl) if "November survey" in i["text"]) == 1,
          "sending the same thing again puts nothing there a second time", s1b.get("line"))

    # ---- 4. one person's done mark is theirs alone
    apply(RILEY, rl, "done", id=ri["id"])
    both(RILEY, SAM, DANA, JO)
    sam_r = find(SAM, lst("mailbox-riley"), "November survey")
    sam_j = find(SAM, lst("mailbox-jo"), "November survey")
    dana_r = find(DANA, lst("mailbox-riley"), "November survey")
    orig = next(i for i in items(SAM, WORK) if i["id"] == "T-0001")
    check(sam_r["mark"] == "x" and sam_j["mark"] == " " and orig["mark"] == " " and find(JO, jl, "November survey")["mark"] == " ",
          "Riley's done mark closes Riley's copy only: Jo's copy and the original stay open", (sam_r["mark"], sam_j["mark"], orig["mark"]))
    check(dana_r is not None and dana_r["mark"] == "x", "the second admin sees it done in Riley's mailbox", dana_r and dana_r["mark"])

    # ---- 5. a question to picked mailboxes only, answered
    s2 = mb.send(SAM, "question", {"project": "work", "id": "Q-0001"}, to=["mailbox-riley"])
    both(SAM, RILEY, JO)
    rq = find(RILEY, rl, "group call")
    check(s2["ok"] and s2["sent"] == ["Riley"] and rq is not None and rq["to"] == "@riley" and rq.get("options") == "Thursday | Friday"
          and find(JO, jl, "group call") is None, "a question sent to one picked mailbox reaches that person only, theirs to answer", (s2.get("line"), rq and rq["to"]))
    apply(RILEY, rl, "answer", id=rq["id"], text="Friday", by="@riley")
    both(RILEY, SAM)
    sq = find(SAM, lst("mailbox-riley"), "group call")
    check(sq is not None and sq["mark"] == "a" and "Friday" in (sq.get("answer") or ""), "their answer comes back on that copy", sq and (sq["mark"], sq.get("answer")))
    s2b = mb.send(SAM, "task", {"project": "work", "id": "T-0003"}, to=[])
    check(not s2b["ok"] and s2b["line"] == "Pick at least one mailbox.", "a send with nobody picked says so and sends nothing", s2b.get("line"))

    # ---- 6. a file, to one; what the gate holds back, to nobody
    s3 = mb.send(SAM, "file", {"path": "projects/work/welcome.md"}, to=["mailbox-jo"])
    both(SAM, JO, RILEY)
    check(s3["ok"] and s3["sent"] == ["Jo"] and os.path.isfile(os.path.join(JO, "shared", os.path.dirname(jl).split("/")[-1], "files", "welcome.md"))
          and not os.path.isdir(os.path.join(RILEY, "shared", os.path.dirname(rl).split("/")[-1], "files")),
          "a file sent to one mailbox arrives there and nowhere else", s3.get("line"))
    s4 = mb.send(SAM, "task", {"project": "work", "id": "T-0002"})
    both(SAM, RILEY)
    check(not s4["ok"] and "private" in s4["line"] and find(RILEY, rl, "budget") is None, "a task marked private is sent to nobody", s4.get("line"))

    # ---- 7. the other admin sends too
    put(DANA, "people/readme.md", "# people/\n")
    s5 = mb.send(DANA, "task", {"project": "work", "id": "T-0001"}, to=["mailbox-jo"])
    both(DANA, JO, SAM)
    jd = find(JO, jl, "Order lunch")
    check(s5["ok"] and s5["sent"] == ["Jo"] and jd is not None and jd["owner"] == "@jo" and find(SAM, lst("mailbox-jo"), "Order lunch") is not None,
          "the second admin sends into a mailbox, and the first admin sees it there", (s5.get("line"), jd and jd["owner"]))

    # ---- 8. a person on a computer their employer owns still gets what is sent, and can answer it
    eng.set_client(RILEY, True)
    s6 = mb.send(SAM, "task", {"project": "work", "id": "T-0003"}, to=["mailbox-riley"])
    both(SAM, RILEY)
    rw = find(RILEY, rl, "welcome note")
    check(s6["ok"] and rw is not None and rw["owner"] == "@riley", "on an employer's computer what is sent still arrives", s6.get("line"))
    apply(RILEY, rl, "done", id=rw["id"])
    both(RILEY, SAM)
    check(find(SAM, lst("mailbox-riley"), "welcome note")["mark"] == "x", "and their done mark still comes back")
    held = eng.share_item(RILEY, rs[0]["name"], "work", "T-0001")
    check(not held[0] and held[1] == eng.OFF_LINE, "while sharing something of their own from that computer waits", held)
    eng.set_client(RILEY, False)
except Exception:
    check(False, "the run reached its end", traceback.format_exc()[-1800:])

print("")
print("%d claim(s) failed" % len(FAILS) if FAILS else "all claims hold")
print("scratch: %s" % TMP)
sys.exit(1 if FAILS else 0)
