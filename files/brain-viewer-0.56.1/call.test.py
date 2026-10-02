#!/usr/bin/env python
"""call.test.py -- the call screen's server half (0.47.0) and the calendar fallback (T-0224), checked on a scratch brain.

  python skills/brain-viewer/call.test.py

Claims:
  1. today's team prep parses into its parts: due, four question groups with their lines, points per person, notes.
  2. a v2 prep (seven sections) parses without losing a section, its Bring questions as a group.
  3. a tick writes `- [x]` on that one line and nothing else; an untick writes `- [ ]`; a stale line is refused.
  4. the notes save replaces the notes section only, keeps the skeleton's comment, and round-trips.
  5. calls_api answers from the week file when the today file is another day's, and says so in answeredBy; the stale
     flag is set only when the answering file is another day's; join and calendarLink pass through.
  6. an attendee with no people/ card still gets the prep keyed to their name slugified (T-0248): a synthetic event
     with "Zed Nocard" matches a synthetic nocard prep on /api/calls and on the week file, the person row keeps
     slug None, and a prep keyed to somebody else stays off the event.
Nothing is written into the real brain: every write goes to a temporary folder that is removed at the end.
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.argv = [sys.argv[0]]
import serve  # noqa: E402

FAILS = []


def check(ok, what, detail=""):
    print(("ok   " if ok else "FAIL ") + what + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILS.append(what)


def main():
    real = os.path.join(BRAIN, "deliverables", "call-prep")
    team = os.path.join(real, "team-call-prep-2026-09-23.md")
    v2 = os.path.join(real, "team-call-prep-2026-09-14.md")
    with io.open(team, encoding="utf-8-sig") as f:
        p = serve.parse_prep(f.read())
    check(p["format"] in ("v3", "v2") and p["due"] and "Reply to Mike" in p["due"]["md"], "the Due section is read", p["due"])
    check(len(p["questions"]) == 4, "four question groups, as the file groups them", [g["subject"] for g in p["questions"]])
    check(all(i["text"].startswith("**") for g in p["questions"] for i in g["items"]), "every question keeps its bold who-answers at the front")
    check([x["name"] for x in p["points"]] == ["John", "Dani", "Owen", "Vivian"], "points per person, one list per name", [x["name"] for x in p["points"]])
    check(p["notes"] is not None, "the notes section is found")
    if os.path.isfile(v2):
        with io.open(v2, encoding="utf-8-sig") as f:
            q = serve.parse_prep(f.read())
        titles = [s["title"] for s in q["sections"]]
        check(q["format"] == "v2" and len(titles) >= 5, "a v2 prep keeps its sections flat", titles)
        check(any(g["subject"].lower().startswith("questions") for g in q["questions"]), "a v2 prep's Bring questions become a group",
              [g["subject"] for g in q["questions"]])

    tmp = tempfile.mkdtemp(prefix="call-test-")
    old = serve.BRAIN
    try:
        serve.BRAIN = tmp
        os.makedirs(os.path.join(tmp, "deliverables", "call-prep"))
        os.makedirs(os.path.join(tmp, "context"))
        dst = os.path.join(tmp, "deliverables", "call-prep", "team-call-prep-2026-09-23.md")
        shutil.copyfile(team, dst)
        rel = "deliverables/call-prep/team-call-prep-2026-09-23.md"
        with io.open(dst, encoding="utf-8") as f:
            before = f.read().split("\n")
        it = p["questions"][0]["items"][0]
        code, out = serve.call_tick({"path": rel, "line": it["line"], "checked": True, "text": it["text"]})
        with io.open(dst, encoding="utf-8") as f:
            after = f.read().split("\n")
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        check(code == 200 and changed == [it["line"]] and after[it["line"]].startswith("- [x] **"), "a tick writes - [x] on that line alone", (code, out, changed))
        code, out = serve.call_tick({"path": rel, "line": it["line"], "checked": False, "text": it["text"]})
        with io.open(dst, encoding="utf-8") as f:
            again = f.read().split("\n")
        check(code == 200 and again[it["line"]].startswith("- [ ] **"), "an untick writes - [ ]", again[it["line"]])
        code, out = serve.call_tick({"path": rel, "line": it["line"], "checked": True, "text": "something else"})
        check(code == 409, "a line that changed since the page loaded is refused", (code, out))
        code, out = serve.call_tick({"path": "people/john-kissell.md", "line": 1, "checked": True, "text": "x"})
        check(code == 404, "a file that is not a prep is refused", code)

        code, out = serve.call_notes({"path": rel, "text": "John: yes to the split.\nDani drafts it."})
        with io.open(dst, encoding="utf-8") as f:
            t = f.read()
        pn = serve.parse_prep(t)
        check(code == 200 and pn["notes"]["text"] == "John: yes to the split.\nDani drafts it.", "the notes round-trip", (code, pn["notes"]))
        check(t.split("## Your notes")[0] == "\n".join(again).split("## Your notes")[0], "nothing above the notes section moved")
        skel = os.path.join(tmp, "deliverables", "call-prep", "x-call-prep-2026-09-24.md")
        with io.open(skel, "w", encoding="utf-8") as f:
            f.write("# x\n\n## Your notes\n\n<!-- Zak: the notes go here -->\n\n\n## Since last time\n\nold\n")
        serve.call_notes({"path": "deliverables/call-prep/x-call-prep-2026-09-24.md", "text": "one line"})
        with io.open(skel, encoding="utf-8") as f:
            s = f.read()
        check("<!-- Zak: the notes go here -->" in s and "one line" in s and "## Since last time\n\nold" in s,
              "the skeleton's comment and the next section are kept", s)

        today = serve.ledger.today()
        ev = {"date": today, "start": today + "T09:00:00-07:00", "end": today + "T09:30:00-07:00", "title": "Team",
              "attendees": [{"name": "Somebody"}], "join": "https://meet.example/abc", "calendarLink": "https://calendar.example/e"}
        with io.open(os.path.join(tmp, "context", "week-calendar.json"), "w", encoding="utf-8") as f:
            json.dump({"from": "2000-01-01", "to": "2999-12-31", "events": [ev]}, f)
        with io.open(os.path.join(tmp, "context", "today-calendar.json"), "w", encoding="utf-8") as f:
            json.dump({"date": "2000-01-01", "events": []}, f)
        c = serve.calls_api()
        check(c["answeredBy"] == serve.CALENDAR_WEEK_REL and not c["stale"] and c["count"] == 1,
              "a today file dated another day falls back to the week file", {k: c[k] for k in ("answeredBy", "stale", "count", "for")})
        check(c["events"] and c["events"][0]["join"] == "https://meet.example/abc", "join passes through /api/calls")
        w = serve.calendar_week_api()
        check(w["events"] and w["events"][0].get("calendarLink") == "https://calendar.example/e", "calendarLink passes through /api/calendar/week")
        with io.open(os.path.join(tmp, "context", "week-calendar.json"), "w", encoding="utf-8") as f:
            json.dump({"from": "2000-01-01", "to": "2000-01-07", "events": []}, f)
        c = serve.calls_api()
        check(c["answeredBy"] == serve.CALENDAR_REL and c["stale"], "with no week covering today the old file answers, marked stale",
              {k: c[k] for k in ("answeredBy", "stale")})
        os.remove(os.path.join(tmp, "context", "today-calendar.json"))
        os.remove(os.path.join(tmp, "context", "week-calendar.json"))
        c = serve.calls_api()
        check(not c["exists"] and c["answeredBy"] is None, "with neither file, the answer says so")

        # 6. the prep for a person with no card (T-0248) -- synthetic event, synthetic prep, scratch brain only
        cp = os.path.join(tmp, "deliverables", "call-prep")
        with io.open(os.path.join(cp, "zed-nocard-call-prep-%s.md" % today), "w", encoding="utf-8") as f:
            f.write("---\nperson: zed-nocard\ncall: %s\npurpose: intro\n---\n# Zed\n" % today)
        with io.open(os.path.join(cp, "yara-other-call-prep-%s.md" % today), "w", encoding="utf-8") as f:
            f.write("---\nperson: yara-other\ncall: %s\n---\n# Yara\n" % today)
        nev = {"date": today, "start": today + "T10:00:00-07:00", "end": today + "T10:30:00-07:00", "title": "Zed Meeting",
               "attendees": [{"name": "Zed Nocard"}]}
        with io.open(os.path.join(tmp, "context", "today-calendar.json"), "w", encoding="utf-8") as f:
            json.dump({"date": today, "events": [nev]}, f)
        with io.open(os.path.join(tmp, "context", "week-calendar.json"), "w", encoding="utf-8") as f:
            json.dump({"from": "2000-01-01", "to": "2999-12-31", "events": [nev]}, f)
        c = serve.calls_api()
        e0 = (c.get("events") or [{}])[0]
        paths = [x["path"] for x in e0.get("preps") or []]
        check(paths == ["deliverables/call-prep/zed-nocard-call-prep-%s.md" % today],
              "a prep keyed to a no-card attendee's name attaches on /api/calls, and only that one", paths)
        zed = [w for w in e0.get("people") or [] if w["name"] == "Zed Nocard"]
        check(zed and zed[0]["slug"] is None and zed[0]["card"] is None and "Zed Nocard" in e0.get("noCard", []),
              "the attendee still reads as having no card", zed)
        w = serve.calendar_week_api()
        wp = [x["path"] for e in w.get("events") or [] for x in e.get("preps") or []]
        check(wp == paths, "the week file's event gets the same prep", wp)
        check(serve.event_match_keys([{"name": "Zak", "slug": None, "self": True}, {"name": "a@b.com", "slug": None, "self": False},
                                      {"name": "John Kissell", "slug": "john-kissell", "self": False}]) == {"john-kissell"},
              "the owner and an email address are never match keys; a carded slug is")
    finally:
        serve.BRAIN = old
        shutil.rmtree(tmp, ignore_errors=True)
    print("-" * 72)
    print("call.test: " + ("all checks pass" if not FAILS else "%d FAILED: %s" % (len(FAILS), "; ".join(FAILS))))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
