#!/usr/bin/env python3
"""sharing-kinds.test.py -- sharing round three, the engine: files, threads, drawings, card sections and messages.

Two scratch brains (Sam and Riley) and one LocalService folder standing in for the service, made with tempfile; the real
brain is never written. One process drives both brains (the engine loads the ledger tool once per brain). Key-shaped
fixtures are built from pieces at run time, so no line of this file (which ships) holds one. One ok / FAIL line per
claim; exit 1 on any failure.
"""
import builtins
import io
import json
import os
import re
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
KEY = "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz0123"


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  -- " + str(detail)[:300]) if detail else ""))
    if not ok:
        FAILS.append(what)


TMP = tempfile.mkdtemp(prefix="sharing-kinds-test-")
SVC = os.path.join(TMP, "service")
SAM, RILEY = os.path.join(TMP, "sam"), os.path.join(TMP, "riley")
WORK = "projects/work/work-tasks.md"
BS = chr(92)


def put(root, rel, text):
    ap = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with RAW_OPEN(ap, "w", encoding="utf-8", newline="\n") as f:
        f.write(text if isinstance(text, str) else json.dumps(text))


def get(root, rel):
    with RAW_OPEN(os.path.join(root, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


def has(root, rel):
    return os.path.isfile(os.path.join(root, *rel.split("/")))


def build(root, person, display, ledger):
    put(root, "context/log.md", "# Brain Operations Log\n\n## Log\n\n")
    put(root, "context/holon-registry.json", {"holons": [
        {"id": "work", "name": "Work", "path": "projects/work/", "sharing": "private", "tasks": WORK},
        {"id": "client", "name": "Client work", "path": "projects/client/", "sharing": "employer"}]})
    put(root, "viewer/settings.json", {"owner": person, "display_name": display, "project_labels": {"work": "Work"},
                                       "sharing_service": {"carrier": "local", "root": SVC}})
    put(root, "people/readme.md", "# people/\n")
    put(root, WORK, "# Work -- tasks\n\n## Inbox\n\n" + ledger)


build(SAM, "sam", "Sam",
      "- [ ] T-0001 2026-11-01 @sam · Book the venue for the meetup · → projects/work/meetup.md\n"
      "- [?] Q-0001 2026-11-01 @sam → @riley · Which day works for the meetup? · options:Friday | Saturday · → projects/work/meetup.md\n"
      "- [ ] T-0002 2026-11-01 @sam · Order the banner\n")
build(RILEY, "riley", "Riley", "- [ ] T-0001 2026-11-01 @riley · Water the plants\n")
put(SAM, "skills/team-brain/people-held-back.json", {"drop_lines_naming": {"patterns": ["Morgan Hidden"]}})
NOTES = ("# Notes for the meetup\n\nThe room holds forty.\n[private] the secret plan\nAsk Morgan Hidden about chairs.\n"
         "The draft is at C:" + BS + "Users" + BS + "sam" + BS + "draft.txt and see T-0002.\n\n## Budget [private]\n\nForty dollars a head.\n"
         "\n## Food\n\nPizza for everyone.\n")
put(SAM, "projects/work/notes.md", NOTES)
put(SAM, "projects/work/todo.md", "Bring the cables.\n")
put(SAM, "projects/work/meetup.md", "---\ntitle: The spring meetup\nproject: work\npeople:\n  - riley\nmatch: meetup\n"
                                     "canonical: true\ndepends: notes\nprogress: half\nstatus: open\n---\n\n# The spring meetup\n\nPlanning notes.\n")
put(SAM, "projects/work/plan.canvas", json.dumps({"nodes": [{"id": "a", "type": "text", "text": "Stage", "x": 0, "y": 0}], "edges": []}, indent=1))
put(SAM, "projects/work/plan.forge.json", json.dumps({"pins": [1, 2]}))
put(SAM, "projects/work/bad.canvas", json.dumps({"nodes": [{"id": "a", "type": "file", "file": "C:" + BS + "Users" + BS + "sam" + BS + "x.png"}]}, indent=1))
put(SAM, "hf_key.txt", "x\n")
put(SAM, "projects/work/keyed.md", "Use " + KEY + " here\n")
put(SAM, "thoughts/me.md", "Some thoughts\n")
put(SAM, "projects/client/plan.md", "The client plan\n")
put(SAM, "transcripts/call.md", "A call\n")
put(SAM, "people/jordan-lee.md", "# Jordan Lee\n\n## Background\n\nWorks on stage design.\n\n## Notes [private]\n\nPrivate notes.\n\n"
                                 "## Family\n\nMarried to Morgan Hidden.\n\n## Skills\n\nLighting.\n")
put(SAM, "projects/work/big.md", "x" * (401 * 1024))
with RAW_OPEN(os.path.join(SAM, "projects", "work", "pic.png"), "wb") as f:
    f.write(bytes(range(256)))


def load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


share = load("sharing_share_kinds_test", os.path.join(HERE, "share.py"))
eng = share.engine()


def T(brain):
    return eng.tasks_for(brain)


def items(brain, rel):
    t = T(brain)
    p = os.path.join(brain, *rel.split("/"))
    return t.parse(t.read(p))["items"] if os.path.isfile(p) else []


def apply(brain, rel, action, **a):
    return T(brain).apply(os.path.join(brain, *rel.split("/")), rel, action, agent="sharing-test", **a)


def db():
    with RAW_OPEN(os.path.join(SVC, "service-data.json"), encoding="utf-8") as f:
        return json.load(f)


def sign(brain, email):
    eng.sign_in_start(brain, email)
    code = get(SVC, "outbox/%s.txt" % email).strip()
    ok, line = eng.sign_in_finish(brain, email, code)
    assert ok, line


def probs(r):
    return [p for s in r.get("spaces") or [] for p in s["problems"]]


# the ledger-write guard, as in sharing-service.test.py
VIOLATIONS = []
_open, _replace = builtins.open, os.replace


def _from_tool():
    f, names = sys._getframe(2), set()
    while f is not None:
        if f.f_code.co_filename.replace("\\", "/").endswith("brain-tasks/tasks.py"):
            names.add(f.f_code.co_name)
        f = f.f_back
    return "write" in names and bool(names & {"apply", "init"})


def g_open(file, mode="r", *a, **k):
    if isinstance(file, (str, os.PathLike)) and str(file).endswith("-tasks.md") and any(c in str(mode) for c in "wax+") and not _from_tool():
        VIOLATIONS.append(str(file))
    return _open(file, mode, *a, **k)


def g_replace(src, dst, *a, **k):
    if isinstance(dst, (str, os.PathLike)) and str(dst).endswith("-tasks.md") and not _from_tool():
        VIOLATIONS.append(str(dst))
    return _replace(src, dst, *a, **k)


builtins.open, io.open, os.replace = g_open, g_open, g_replace
try:
    sign(SAM, "sam@example.com")
    inv = eng.invite(SAM, "riley@example.com", "Riley")
    sign(RILEY, "riley@example.com")
    acc = eng.accept(RILEY, invite_id=eng.invites(RILEY)["invites"][0]["id"])
    eng.sync(SAM)
    SP, RP = inv["space"], acc["space"]                    # riley at Sam's, sam at Riley's
    RF = "shared/%s/" % RP

    # ---------------------------------------------------------------- the gate for whole texts: every refusal
    for rel, why in (("hf_key.txt", "it is a key file"),
                     ("projects/work/keyed.md", "it holds something shaped like a password or a key"),
                     ("thoughts/me.md", "it is in a personal folder"),
                     ("projects/client/plan.md", "it belongs to an employer's project"),
                     ("transcripts/call.md", "it is a transcript"),
                     ("people/jordan-lee.md", "a card goes section by section, not as a whole file"),
                     ("projects/work/big.md", "it is over the 400 KB a shared file may be"),
                     ("projects/work/pic.png", "only text files can be shared so far")):
        ok, line = eng.share_file(SAM, SP, rel)
        check(not ok and line == "Not shared with Riley: %s." % why, "refused: %s" % why, line)
    ok, line = eng.share_drawing(SAM, SP, "projects/work/bad.canvas")
    check(not ok and "holds a path on this computer, on line" in line, "a drawing with a path on this computer is refused, and says where", line)
    for heading, why in (("Notes [private]", "it is marked private"), ("Family", "it names someone who never crosses")):
        ok, line = eng.share_card_section(SAM, SP, "people/jordan-lee.md", heading)
        check(not ok and line.endswith(why + "."), "a card section %s is refused" % ("marked private" if "private" in heading else "naming a held-back person"), line)
    check(not [t for t in db()["things"].values() if t["kind"] != "task"], "nothing refused reached the service")

    # ---------------------------------------------------------------- what a thing is, per kind
    ok, line = eng.share_file(SAM, SP, "projects/work/notes.md")
    check(ok and line.startswith("Shared with Riley:"), "a text file is shared", line)
    ok_t, line_t = eng.share_thread(SAM, SP, "projects/work/meetup.md")
    check(ok_t and "2 open items" in line_t, "a thread is shared, with the open items that link it", line_t)
    ok_d, line_d = eng.share_drawing(SAM, SP, "projects/work/plan.canvas")
    ok_s, line_s = eng.share_card_section(SAM, SP, "people/jordan-lee.md", "Background")
    check(ok_d and ok_s, "a drawing and a card section are shared", (line_d, line_s))
    sent = json.loads(get(SAM, "shared/%s/sent.json" % SP))
    check(all(sent[k] and all(r.get("thing") for r in sent[k]) for k in ("files", "threads", "drawings", "sections"))
          and {r["path"] for r in sent["files"]} == {"projects/work/notes.md"} and sent["sections"][0]["heading"] == "Background",
          "sent.json gains files, threads, drawings and sections, each with its thing", sent.get("sections"))
    srow = next(x for x in share.status(SAM)["spaces"] if x["name"] == SP)
    check({k: srow["counts"].get(k) for k in ("files", "threads", "drawings", "sections")} == {"files": 1, "threads": 1, "drawings": 1, "sections": 1}
          and "1 file" in share.status(SAM)["line"] and "1 drawing" in share.status(SAM)["line"],
          "status counts what this brain shared by kind", share.status(SAM)["line"])
    r = eng.sync(RILEY)
    f = get(RILEY, RF + "files/notes.md") if has(RILEY, RF + "files/notes.md") else ""
    check(f and "secret plan" not in f and "Forty dollars" not in f and "Budget" not in f and "Morgan" not in f
          and "C:" not in f and "[path removed]" in f and "see a task" in f and "Pizza for everyone." in f,
          "the file arrives where the table says, with private lines, a private fold, a held-back name and a path taken out", f)
    th = get(RILEY, RF + "threads/meetup.md") if has(RILEY, RF + "threads/meetup.md") else ""
    check(th and "project: shared-%s" % RP in th and not re.search(r"(?m)^(people|match|canonical|depends|progress)\s*:", th)
          and "title: The spring meetup" in th and "status: open" in th,
          "the thread arrives with its frontmatter kept less people, match, canonical, depends and progress, in the space's project", th[:200])
    rl = "shared/%s/%s-tasks.md" % (RP, RP)
    linked = [i for i in items(RILEY, rl) if any("threads/meetup.md" in l for l in i["links"])]
    check(len(linked) == 2 and {i["kind"] for i in linked} == {"task", "question"},
          "the thread's open items arrive as items that link the thread's file", [(i["text"], i["links"]) for i in items(RILEY, rl)])
    cv = get(RILEY, RF + "drawings/plan.canvas") if has(RILEY, RF + "drawings/plan.canvas") else ""
    v0 = eng.space_view(RILEY, RP)
    fr = next((x for x in v0["from_them"] if x["kind"] == "file"), {})
    ok_o, line_o = eng.mark_opened(RILEY, RP, fr.get("id"))
    fr2 = next((x for x in eng.space_view(RILEY, RP)["from_them"] if x.get("id") == fr.get("id")), {})
    check(fr and fr.get("opened") is False and ok_o and fr2.get("opened") is True and not eng.mark_opened(RILEY, RP, "no-such-thing")[0],
          "mark_opened records that a received file was opened, with no call to the service", line_o)
    check(cv == get(SAM, "projects/work/plan.canvas") and has(RILEY, RF + "drawings/plan.forge.json"),
          "the drawing arrives unrewritten, with its forge twin", cv[:60])
    pr = eng.proposals(RILEY)
    check(len(pr) == 1 and pr[0]["person"] == "Jordan Lee" and pr[0]["heading"] == "Background" and "stage design" in pr[0]["text"]
          and not os.path.isfile(os.path.join(RILEY, "people", "jordan-lee.md")),
          "a card section waits as a proposal, written into no card", pr)
    ok, line = eng.take_section(RILEY, pr[0]["id"])
    card = get(RILEY, "people/jordan-lee.md") if has(RILEY, "people/jordan-lee.md") else ""
    check(ok and re.search(r"## Background \(from Sam, \d+/\d+\)", card) and "stage design" in card,
          "take_section adds it to the card as a fold that says who it came from", card)
    check(card.startswith("# Jordan Lee\n") and "share partner" not in card,
          "a card made for the person a section is about never calls them a share partner", card[:160])
    eng.sync(SAM)
    eng.sync(RILEY)
    check(not eng.proposals(RILEY) and card.count("## Background") == get(RILEY, "people/jordan-lee.md").count("## Background"),
          "the same version never lands twice")
    ok_s2, _l = eng.share_card_section(SAM, SP, "people/jordan-lee.md", "Skills")
    eng.sync(RILEY)
    pr2 = eng.proposals(RILEY)
    ok, line = eng.leave_section(RILEY, pr2[0]["id"]) if pr2 else (False, "")
    check(ok and not eng.proposals(RILEY) and "Lighting" not in get(RILEY, "people/jordan-lee.md"),
          "leave_section leaves the card as it was", line)

    # ---------------------------------------------------------------- a file there already is never overwritten
    put(RILEY, RF + "files/todo.md", "Riley's own list\n")
    eng.share_file(SAM, SP, "projects/work/todo.md")
    r = eng.sync(RILEY)
    check(get(RILEY, RF + "files/todo.md") == "Riley's own list\n" and has(RILEY, RF + "files/todo (from Sam).md")
          and any("beside your own file" in p for p in probs(r)),
          "a file already there with other content is never overwritten: the new one is written beside it, and said", probs(r))

    # ---------------------------------------------------------------- a change the gate refuses is held
    put(SAM, "projects/work/notes.md", NOTES + "Key: " + KEY + "\n")
    r = eng.sync(SAM)
    thing = next(t for t in db()["things"].values() if t["kind"] == "file" and "notes" in t["body"].get("name", ""))
    check(any("stays here" in p and "earlier version" in p for p in probs(r)) and not thing["removed_at"] and KEY not in json.dumps(db()),
          "a change the gate refuses is held: the earlier version stays shared, nothing new goes, and it is said", probs(r))
    put(SAM, "projects/work/notes.md", NOTES)
    eng.sync(SAM)

    # ---------------------------------------------------------------- the other person's edit
    put(RILEY, RF + "files/notes.md", get(RILEY, RF + "files/notes.md") + "Riley adds: bring name tags.\n")
    r = eng.sync(RILEY)
    check(any(a["act"] == "edit" for a in db()["acts"].values()), "a change to someone else's file goes out as one edit act", r["line"])
    r = eng.sync(SAM)
    sl = "shared/%s/%s-tasks.md" % (SP, SP)
    q = next((i for i in items(SAM, sl) if i["kind"] == "question" and "Take the change?" in i["text"]), None)
    prop = "shared/%s/proposed/notes (from Riley).md" % SP
    check(q is not None and q["text"] == "Riley changed “notes.md”. Take the change?" and q["options"] == "Take it | Keep mine"
          and has(SAM, prop) and "bring name tags" not in get(SAM, "projects/work/notes.md"),
          "at the home the change is saved as proposed and one question is asked; the original is untouched", q and q["text"])
    apply(SAM, sl, "answer", id=q["id"], text="Take it")
    r = eng.sync(SAM)
    now = get(SAM, "projects/work/notes.md")
    check("bring name tags" in now and "secret plan" in now and "Forty dollars" in now,
          "Take it lays the change onto the original, which keeps its own private lines", now[-120:])
    r = eng.sync(RILEY)
    check("bring name tags" in get(RILEY, RF + "files/notes.md"), "and the other side sees the result")
    # a clash
    put(SAM, "projects/work/notes.md", get(SAM, "projects/work/notes.md").replace("The room holds forty.", "The room holds fifty."))
    eng.sync(SAM)
    eng.sync(RILEY)
    put(RILEY, RF + "files/notes.md", get(RILEY, RF + "files/notes.md").replace("The room holds fifty.", "The room holds sixty."))
    eng.sync(RILEY)
    put(SAM, "projects/work/notes.md", get(SAM, "projects/work/notes.md").replace("The room holds fifty.", "The room holds seventy."))
    eng.sync(SAM)
    q2 = next((i for i in items(SAM, sl) if i["kind"] == "question" and i["mark"] == "?"), None)
    if q2:
        apply(SAM, sl, "answer", id=q2["id"], text="Take it")
    r = eng.sync(SAM)
    check(q2 is not None and "seventy" in get(SAM, "projects/work/notes.md") and "sixty" not in get(SAM, "projects/work/notes.md")
          and any("touches the same lines as yours" in p for p in probs(r)) and has(SAM, prop),
          "a change that clashes leaves the original, the proposed file stays beside it, and it is said", probs(r))
    # taken without asking
    ok, line = eng.set_auto_take(SAM, SP, True)
    check(ok and any(m.get("auto_take") for m in eng._stamp(SAM, SP)["members"]), "set_auto_take writes it on the stamp", line)
    eng.sync(RILEY)
    n_q = len([i for i in items(SAM, sl) if i["kind"] == "question"])
    put(RILEY, RF + "files/notes.md", get(RILEY, RF + "files/notes.md") + "Riley adds: and a banner stand.\n")
    eng.sync(RILEY)
    eng.sync(SAM)
    check("banner stand" in get(SAM, "projects/work/notes.md") and len([i for i in items(SAM, sl) if i["kind"] == "question"]) == n_q,
          "with auto_take, a clean merge is applied without the question")

    # ---------------------------------------------------------------- take back
    ok, line = eng.take_back_thing(SAM, SP, "drawing", "projects/work/plan.canvas")
    eng.sync(RILEY)
    view = eng.space_view(RILEY, RP)
    dr = next((x for x in view["from_them"] if x["kind"] == "drawing"), {})
    check(ok and dr.get("taken_back") and has(RILEY, RF + "drawings/plan.canvas")
          and not json.loads(get(SAM, "shared/%s/sent.json" % SP))["drawings"],
          "take_back_thing takes a drawing back; the copy stays and reads as taken back", line)

    # ---------------------------------------------------------------- messages
    ok, line = eng.send_message(SAM, SP, "Hello Riley, the room is booked")
    ok2, line2 = eng.send_message(SAM, SP, "the key is " + KEY)
    check(ok and line == "Sent to Riley." and not ok2 and "Not sent to Riley" in line2, "a message is sent, and one holding a key is not", (line, line2))
    eng.sync(RILEY)
    ms = eng.messages(RILEY, RP)
    check(len(ms) == 1 and ms[0]["from"] == "Sam" and ms[0]["text"] == "Hello Riley, the room is booked", "a sync appends a message to messages.jsonl", ms)
    eng.send_message(RILEY, RP, "Great, thanks")
    eng.sync(SAM)
    row = next(x for x in share.status(SAM)["spaces"] if x["name"] == SP)
    check(row["unread"] == 1 and [m["text"] for m in eng.messages(SAM, SP)] == ["Hello Riley, the room is booked", "Great, thanks"],
          "messages go both ways, and status counts what is unread", row["unread"])
    eng.mark_read(SAM, SP)
    row = next(x for x in share.status(SAM)["spaces"] if x["name"] == SP)
    check(row["unread"] == 0, "mark_read clears the count")

    # ---------------------------------------------------------------- the space's page
    v = eng.space_view(SAM, SP)
    want = {"label", "kind", "people", "here", "host_name", "shared", "from_them", "made_here", "proposals", "messages", "unread"}
    kinds_shared = {x["kind"] for x in v["shared"]}
    check(set(v) == want and {"file", "thread", "card-section", "task", "question"} <= kinds_shared and v["here"] is True
          and v["people"][0]["display"] == "Riley" and len(v["messages"]) == 2,
          "space_view gives everything the page draws", sorted(kinds_shared))

    # ---------------------------------------------------------------- the command line
    out = subprocess.run([sys.executable, os.path.join(HERE, "share.py"), "space", "--space", SP, "--json", "--brain", SAM],
                         capture_output=True, text=True, encoding="utf-8")
    try:
        jv = json.loads(out.stdout)
    except ValueError:
        jv = {}
    out2 = subprocess.run([sys.executable, os.path.join(HERE, "share.py"), "messages", "--space", SP, "--brain", SAM],
                          capture_output=True, text=True, encoding="utf-8")
    check(jv.get("label") == "Riley" and "Great, thanks" in out2.stdout, "the space and messages verbs work from the command line", out2.stdout[:120])
except Exception:
    check(False, "the run reached its end", traceback.format_exc()[-1500:])
    print(traceback.format_exc())
finally:
    builtins.open, io.open, os.replace = _open, _open, _replace

check(not VIOLATIONS, "every ledger file was changed only through the list tool", VIOLATIONS[:3])
print("")
print("%d claim(s) failed" % len(FAILS) if FAILS else "all claims hold")
print("scratch: %s" % TMP)
sys.exit(1 if FAILS else 0)
