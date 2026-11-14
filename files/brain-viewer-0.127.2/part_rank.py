"""part_rank.py -- the one order for the owner's open items (viewer 0.123.0, the Today focus direction).

The direction is brain-viewer-holon/design-directions/today-focus-2026-11-12.md, built on the owner's answer to
brain-viewer Q-0074 ("I guess just go for it and we can see"). Every open item of the owner's gets ONE reason, and the
reasons rank in this order:

  1 today    its moment is today: a pin a session wrote with its why; the one most pressing item of a call today;
             due today; back from a hold today; past its day by a week or less
  2 waiting  someone is waiting on it: another open task names it as what it waits on, or a person asked for it
  3 focus    it sits on one of this week's focus threads (context/today-focus.json)
  4 middle   its thread was touched today or yesterday (context/in-progress.json)
  5 press    a question one press settles (named choices, or a yes-or-no question)
  6 rest     everything else, by thread, the focus threads first

Urgency counts only where it is real, a set hour or a person waiting, never because an item is old or was touched
lately (the mere urgency effect, Zhu, Yang and Hsee 2018, in Grok Bot's research for the direction). Inside each reason
an item on a focus thread comes first.

Three things take an item out of the list:
  gathered   it names someone on a call in the next two days (today's call lifts its one most pressing item into
             reason 1; the rest wait on the call's tile and open in its prep)
  passed     it was among the top three on three days or more with no press since the first of them
  stale      it is two weeks past its day and nothing waits on it

This module is pure: serve.py reads the files and passes them in, and GET /api/today/rank answers what rank() returns.
The page, the thread page and skills/today-pick/pick.py suggest read that one answer, so one order holds everywhere.
Nothing here writes; the record of what was on top each day (viewer/today-top.json) is written by serve.py.
"""
import datetime as dt
import re

REASONS = ("today", "waiting", "focus", "middle", "press", "rest")
TOP_SIZE = 3
LATE_DAYS = 7          # past its day by this many days or fewer: still reason 1
STALE_DAYS = 14        # past its day by this many or more, nothing waiting on it: the Gone stale fold
PASSED_DAYS = 3        # among the top three on this many days with no press: the Passed over fold
CALL_DAYS = 2          # a call today, tomorrow or the day after gathers the items that name its people
INTAKE_DAYS = 14       # the page's rule: a call-intake item this old waits for the sweep before Today shows it

REF_RE = re.compile(r"\b[TQ]-\d{4}\b")
# a person asked for it: the words an item is filed with when someone is waiting on the owner
WAIT_RE = re.compile(r"(is waiting|are waiting|waiting (?:on|for) you|waits (?:on|for) you"
                     r"|(?:which|that|what) (?:he|she|they) asked (?:you )?for|(?:he|she|they) asked you (?:for|to)"
                     r"|wants (?:it|them|this|these) (?:ready|by|before|back|done|sent)|wants to know|you (?:promised|offered)"
                     r"|you (?:told|said to) \w+(?: \w+)? (?:you would|you'd))", re.I)
YESNO_RE = re.compile(r"^\s*(should|is|are|does|do|did|can|could|may|will|would|has|have|accept|confirm|approve)\b", re.I)
SEVEN_WORDS = re.compile(r"^(.{0,140}?[.?!])(\s|$)")


def _day(s):
    try:
        return dt.date.fromisoformat(str(s or "")[:10])
    except ValueError:
        return None


def _mdd(d):
    return "%d/%d" % (d.month, d.day) if d else ""


def _clock(hhmm):
    """'13:05' -> '1:05pm'."""
    try:
        h, m = int(hhmm[:2]), int(hhmm[3:5])
    except (ValueError, TypeError):
        return ""
    return "%d:%02d%s" % (12 if h % 12 == 0 else h % 12, m, "pm" if h >= 12 else "am")


def _first(slug):
    return str(slug or "").split("-")[0].title()


def _key(project, iid):
    return "%s/%s" % (project, iid)


def _link_path(l):
    s = str(l or "").strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    return s.split("|")[0].split("#")[0].strip().lstrip("./")


def _subjects(it):
    return [p for p in (_link_path(l) for l in it.get("links") or []) if "/subjects/" in p and p.endswith(".md")]


def _is_test(it):
    return any(t == "test" or str(t).startswith("test-") for t in it.get("tags") or [])


def _source(it):
    if it.get("source"):
        return str(it["source"])
    for t in it.get("tags") or []:
        if str(t).startswith("source:"):
            return str(t)[7:]
    return ""


def owner_items(projects, owner, today, seen=None):
    """The owner's open items the page can act on, keyed holon/id, with what each holds up. The same cut Today's queue
    makes (today.html queueModel): a question put to the owner or a task of theirs; not a call's own item (its prep holds
    it), not in cold storage, not a test, not held past today, not a blocked task, and not a call-intake item older than
    two weeks that the sweep has not read yet."""
    seen = seen or {}
    all_items, mine = {}, {}
    for p in projects or []:
        for g in p.get("groups") or []:
            for it in g.get("items") or []:
                it = dict(it, project=p.get("id"), projectName=p.get("short") or p.get("name") or p.get("id"))
                all_items[_key(p.get("id"), it.get("id"))] = it
    holds = {}
    for k, it in all_items.items():
        if it.get("kind") != "task" or it.get("mark") == "x" or not it.get("blocked"):
            continue
        for ref in REF_RE.findall(str(it["blocked"])):
            holds.setdefault(_key(it["project"], ref), []).append(k)
    cut = today - dt.timedelta(days=INTAKE_DAYS)
    for k, it in all_items.items():
        q = it.get("kind") == "question" and it.get("mark") == "?" and (it.get("to") or owner) == owner
        t = it.get("kind") == "task" and it.get("mark") == " " and it.get("owner") == owner
        if not (q or t):
            continue
        if it.get("call") or _is_test(it) or re.search(r"cold storage", str(it.get("note") or ""), re.I):
            continue
        until = _day(it.get("until"))
        if t and until and until > today:
            continue
        due = _day(it.get("due"))
        made = _day(it.get("created"))
        if _source(it) == "import-checkup" and made and made < cut and not seen.get(k) and not (due and due <= today):
            continue
        open_holds = [h for h in holds.get(k, []) if all_items.get(h, {}).get("mark") not in ("x",)]
        mine[k] = dict(it, holdsUp=open_holds)
    return mine


def _waiting_person(it, owner):
    """(who, since) when a person is waiting on it: a team member's requests through her copy, a question another person asked,
    or the words it was filed with. who is a first name or None."""
    src = _source(it)
    frm = str(it.get("from") or "")
    who = None
    for s in it.get("people") or []:
        if s and "@" + s.split("-")[0] != owner:
            who = _first(s)
            break
    if src == "team-brain":
        return who or "someone", _day(it.get("created"))
    if frm and frm != owner and frm.startswith("@"):
        return _first(frm[1:]), _day(it.get("created"))
    if WAIT_RE.search(str(it.get("text") or "")):
        return who or "someone", _day(it.get("created"))
    return None, None


def _one_press(it):
    if it.get("kind") != "question":
        return False
    if it.get("options"):
        return True
    first = SEVEN_WORDS.match(str(it.get("text") or ""))
    s = first.group(1) if first else str(it.get("text") or "")[:160]
    return bool(YESNO_RE.match(s)) and " or " not in s.lower()


def _event_people(ev, owner):
    """[(slug or None, full name)] for everyone on a call but the owner."""
    out = []
    for w in ev.get("people") or []:
        if w.get("self"):
            continue
        nm = str(w.get("name") or "").strip()
        if not nm or "@" in nm or nm.lower().startswith(owner.lstrip("@").lower() + " "):
            continue
        out.append((w.get("slug"), re.sub(r"\s*\(.*?\)\s*", "", nm).strip()))
    return out


def _names_line(people, n=3):
    names = [p[1].split(" ")[0] for p in people if p[1]]
    if len(names) <= n:
        return " and ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else (names[0] if names else "")
    return ", ".join(names[:n]) + " and %d more" % (len(names) - n)


def _matches(it, people):
    slugs = set(it.get("people") or [])
    text = str(it.get("text") or "")
    for slug, name in people:
        if slug and slug in slugs:
            return True
        if name and " " in name and re.search(r"\b%s\b" % re.escape(name), text, re.I):
            return True
    return False


def rank(projects, owner, now, events=None, progress=None, bound=None, pick=None, focus=None, history=None, seen=None):
    """The ranking. projects: GET /api/projects' projects; owner: '@zak'; now: a datetime; events: the week calendar's
    events with people resolved ({date, start, end, title, people:[{name, slug, self}], call}); progress: the work in
    progress file's projects; bound: {in-progress id -> {subject, name}}; pick: GET /api/today/pick; focus:
    context/today-focus.json; history: viewer/today-top.json's {days: {day: [keys]}, kept: {key: day}}; seen: the
    sweep's record. Returns the answer GET /api/today/rank serves."""
    today = now.date()
    mine = owner_items(projects, owner, today, seen)
    progress = progress or []
    bound = bound or {}
    focus = focus or {}
    history = history or {}
    focus_subjects = [str(t.get("subject") or "") for t in focus.get("threads") or [] if isinstance(t, dict) and t.get("subject")]
    focus_names = {str(t.get("subject")): str(t.get("name") or "") for t in focus.get("threads") or [] if isinstance(t, dict)}

    # the thread an item belongs to, and how lately it was touched
    in_proj = {}
    for p in progress:
        if not isinstance(p, dict):
            continue
        for x in p.get("items") or []:
            parts = str(x).split()
            if len(parts) == 2:
                in_proj.setdefault(_key(parts[0], parts[1]), []).append(p)
    subj_name = {b.get("subject"): b.get("name") for b in bound.values() if isinstance(b, dict) and b.get("subject")}
    subj_name.update({k: v for k, v in focus_names.items() if v})
    proj_by_subject = {}
    for pid, b in bound.items():
        if isinstance(b, dict) and b.get("subject"):
            proj_by_subject.setdefault(b["subject"], pid)
    prog_by_id = {p.get("id"): p for p in progress if isinstance(p, dict)}

    def thread_of(k, it):
        subs = _subjects(it)
        if subs:
            s = subs[0]
            return s, subj_name.get(s) or s.rsplit("/", 1)[-1][:-3].replace("-", " ").capitalize()
        for p in in_proj.get(k, []):
            b = bound.get(p.get("id"))
            if b and b.get("subject"):
                return b["subject"], b.get("name") or p.get("name")
            return "progress:" + str(p.get("id")), p.get("name") or p.get("id")
        return "ledger:" + str(it.get("project")), it.get("projectName") or it.get("project")

    def touched(k, it, subj):
        best = None
        cands = list(in_proj.get(k, []))
        pid = proj_by_subject.get(subj)
        if pid and pid in prog_by_id:
            cands.append(prog_by_id[pid])
        for p in cands:
            d = _day(p.get("lastActivity") or p.get("since"))
            if d and (best is None or d > best[0]):
                best = (d, p.get("name") or p.get("id"))
        return best

    def on_focus(k, it, subj):
        if subj in focus_subjects:
            return True
        for p in in_proj.get(k, []):
            b = bound.get(p.get("id"))
            if b and b.get("subject") in focus_subjects:
                return True
        return False

    rows = {}
    for k, it in mine.items():
        subj, tname = thread_of(k, it)
        foc = on_focus(k, it, subj)
        due, until, made = _day(it.get("due")), _day(it.get("until")), _day(it.get("created"))
        late = (today - due).days if due and due < today else 0
        who, since = _waiting_person(it, owner)
        r = {"key": k, "kind": it.get("kind"), "thread": subj, "threadName": tname, "focus": foc,
             "created": str(it.get("created") or ""), "due": str(it.get("due") or "") or None, "late": late,
             "holds": len(it.get("holdsUp") or []), "reason": "rest", "tag": "", "when": "", "sub": 9, "order": ""}
        if due == today:
            r.update(reason="today", tag="due today", when="By the end of today.", sub=2)
        elif until == today and it.get("kind") == "task":
            r.update(reason="today", tag="back today", when="Back today from its hold.", sub=3)
        elif due and 0 < late <= LATE_DAYS:
            r.update(reason="today", tag="due %s" % _mdd(due), when="It was due %s." % _mdd(due), sub=4, order="%03d" % late)
        elif r["holds"]:
            n = r["holds"]
            r.update(reason="waiting", tag="%d %s on it" % (n, "thing waits" if n == 1 else "things wait"),
                     when="When it is done, %s can move." % ("one other item" if n == 1 else "%d other items" % n),
                     sub=0, order="%03d" % (99 - min(n, 99)) + (r["created"] or ""))
        elif who:
            nm = who if who != "someone" else None
            r.update(reason="waiting", tag="%s is waiting" % nm if nm else "someone is waiting",
                     when="%s since %s." % (("%s has been waiting" % nm) if nm else "Waiting", _mdd(since)) if since else "",
                     sub=1, order=r["created"])
        elif foc:
            r.update(reason="focus", tag="your focus", when="On your focus this week: %s." % tname, order=r["created"])
        else:
            t = touched(k, it, subj)
            if t and (today - t[0]).days <= 1:
                r.update(reason="middle", tag="touched %s" % ("today" if t[0] == today else "yesterday"),
                         when="You were on %s %s." % (t[1], "today" if t[0] == today else "yesterday"),
                         order="%s" % (dt.date(2100, 1, 1) - t[0]).days)
            elif _one_press(it):
                r.update(reason="press", tag="one press", when="One press settles it.", order=r["created"])
            else:
                r.update(order=("0" if foc else "1") + (tname or "") + r["created"])
        rows[k] = r

    # pins: what a session wrote with its why, while the item is still the owner's and open
    pins = []
    if pick and pick.get("current"):
        for p in pick.get("items") or []:
            k = _key(p.get("holon"), p.get("id"))
            if k in rows and k not in pins:
                pins.append(k)
                rows[k]["pin"] = str(p.get("why") or "")

    # calls in the next two days gather the items that name their people; today's call lifts its most pressing one
    events_out = []
    gathered = {}
    for ev in sorted([e for e in events or [] if e.get("call")], key=lambda e: (str(e.get("start")), str(e.get("title")))):
        d = _day(ev.get("date") or ev.get("start"))
        if not d or d < today or (d - today).days > CALL_DAYS:
            continue
        end = str(ev.get("end") or ev.get("start") or "")
        if d == today and end[11:16] and end[11:16] < now.strftime("%H:%M"):
            continue                                      # today's call that has ended gathers nothing
        people = _event_people(ev, owner)
        if not people:
            continue
        eid = "%s %s" % (str(ev.get("start"))[:16], ev.get("title"))
        keys = [k for k in rows if k not in gathered and k not in pins and _matches(mine[k], people)]
        for k in keys:
            gathered[k] = eid
        events_out.append({"id": eid, "date": d.isoformat(), "start": str(ev.get("start") or ""), "end": end,
                           "title": str(ev.get("title") or ""), "names": [p[1] for p in people],
                           "namesLine": _names_line(people), "today": d == today, "keys": keys, "lifted": None,
                           "preps": ev.get("preps") or []})

    def sort_key(k):
        r = rows[k]
        return (REASONS.index(r["reason"]), r["sub"] if r["reason"] == "today" else (0 if r["focus"] else 1),
                r["sub"] if r["reason"] != "today" else 0, r["order"], k)

    for ev in events_out:
        if not ev["today"] or not ev["keys"]:
            continue
        best = sorted(ev["keys"], key=sort_key)[0]
        ev["keys"] = [k for k in ev["keys"] if k != best]
        ev["lifted"] = best
        del gathered[best]
        hhmm = ev["start"][11:16]
        rows[best].update(reason="today", sub=0, order=hhmm, tag="call %s" % _clock(hhmm) if hhmm else "call today",
                          when="Before %s, when you meet %s." % (_clock(hhmm), ev["namesLine"]) if hhmm
                          else "Before you meet %s today." % ev["namesLine"])
    for k, eid in gathered.items():
        rows[k]["gathered"] = eid

    # passed over: on top three or more days with no press since the first of them
    days = history.get("days") or {}
    kept = history.get("kept") or {}
    passed = []
    for k, r in rows.items():
        if k in pins or k in gathered:
            continue
        since = kept.get(k) or ""
        on = sorted(d for d, ks in days.items() if k in (ks or []) and d > since and d < today.isoformat())
        if len(on) < PASSED_DAYS:
            continue
        note = str(mine[k].get("note") or "")
        if any(d2 >= on[0] for d2 in re.findall(r"note(?: \(viewer,)? (\d{4}-\d{2}-\d{2})", note)):
            continue
        r["passed"] = {"days": len(on), "first": on[0]}
        passed.append(k)

    # gone stale: two weeks past its day and nothing waits on it
    stale = [k for k, r in rows.items() if k not in pins and k not in gathered and k not in passed
             and r["late"] >= STALE_DAYS and r["reason"] not in ("waiting",)]
    for k in stale:
        rows[k]["stale"] = True

    order = [k for k in sorted(rows, key=sort_key) if k not in pins and k not in gathered and k not in passed and k not in stale]
    top = (pins + order)[:TOP_SIZE]
    rest = [k for k in order if k not in top]
    counts = {"open": len(rows), "top": len(top), "list": len(rest), "gathered": len(gathered), "passed": len(passed),
              "stale": len(stale), "pins": len(pins)}
    passed = sorted(passed, key=sort_key)
    stale = sorted(stale, key=sort_key)
    for r in rows.values():
        r.pop("sub", None)
        r.pop("order", None)
    return {"today": today.isoformat(), "now": now.isoformat(timespec="seconds"), "owner": owner, "top": top, "list": rest,
            "pins": pins, "events": events_out, "passed": passed, "stale": stale,
            "rows": rows, "focus": {"threads": [{"subject": s, "name": focus_names.get(s) or subj_name.get(s) or s}
                                                for s in focus_subjects],
                                    "writtenAt": focus.get("writtenAt"), "by": focus.get("by")},
            "counts": counts, "reasons": list(REASONS)}


def seed_history_from_log(lines):
    """{day: [keys]} from the log's pick lines ("[today-pick] MODIFIED -- context/today-pick.json -- the pick for D set by
    X: holon id, holon id"), so the Passed over fold knows the days before viewer/today-top.json existed."""
    out = {}
    rx = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) [\d:]+\] \[today-pick\] MODIFIED -- \S+ -- the pick for (\d{4}-\d{2}-\d{2}) set by [^:]+: (.+)$")
    for line in lines:
        m = rx.match(line.strip())
        if not m:
            continue
        day = m.group(2)
        for part in m.group(3).split(","):
            bits = part.strip().split()
            if len(bits) == 2:
                k = _key(bits[0], bits[1])
                lst = out.setdefault(day, [])
                if k not in lst:
                    lst.append(k)
    return out


# ---- what got done today (0.124.0, the Today focus direction: what "worked on" shows) ----
CLOSE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] \[([^\]]+)\] \w+ -- (\S+) -- ([TQ]-\d{4}) (done|answered by ([^:]+))")


def _short(text, n=96):
    t = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", str(text or ""))
    t = re.sub(r"\[\[([^\]]+)\]\]", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    m = SEVEN_WORDS.match(t)
    t = m.group(1) if m else t
    return t if len(t) <= n else t[:n - 2].rsplit(" ", 1)[0] + "…"


def thread_label(it, key, progress, bound):
    """(thread id, name) for any item, open or closed: the subject file it links, else the work-in-progress project
    that holds it, else its ledger."""
    subs = _subjects(it)
    names = {b.get("subject"): b.get("name") for b in (bound or {}).values() if isinstance(b, dict) and b.get("subject")}
    if subs:
        s0 = subs[0]
        return s0, names.get(s0) or s0.rsplit("/", 1)[-1][:-3].replace("-", " ").capitalize()
    for p in progress or []:
        if not isinstance(p, dict):
            continue
        if any(" ".join(str(x).split()) == key.replace("/", " ") for x in p.get("items") or []):
            b = (bound or {}).get(p.get("id"))
            if b and b.get("subject"):
                return b["subject"], b.get("name") or p.get("name")
            return "progress:" + str(p.get("id")), p.get("name") or p.get("id")
    return "ledger:" + str(it.get("project")), it.get("projectName") or it.get("project")


def sofar(projects, owner, today, log_lines, presses, register, progress=None, bound=None, ledger_paths=None, days_back=6):
    """What got done today, with when and who: the marks the day strip draws above its line and the lines Today so far
    reads, one per thread. log_lines: today's log; presses: the day's undo journal (the owner's own presses in the viewer);
    register: the battery's register rows; ledger_paths: {ledger file -> holon id}. Plus `week`, the owner's items closed
    each day for the last days_back days and today."""
    items = {}
    for p in projects or []:
        for g in p.get("groups") or []:
            for it in g.get("items") or []:
                items[_key(p.get("id"), it.get("id"))] = dict(it, project=p.get("id"), projectName=p.get("short") or p.get("name") or p.get("id"))
    lp = ledger_paths or {}
    mine_by = {}
    for pr in presses or []:
        k = _key(pr.get("project") or "", pr.get("id") or "")
        mine_by.setdefault(k, []).append(str(pr.get("at") or "")[11:16])
    marks = []
    for line in log_lines or []:
        m = CLOSE_RE.match(line.strip())
        if not m or m.group(1) != today.isoformat():
            continue
        hhmm, ledger_file, iid = m.group(2), m.group(4), m.group(5)
        holon = lp.get(ledger_file)
        if not holon:
            continue
        k = _key(holon, iid)
        it = items.get(k)
        if not it:
            continue
        by = m.group(7) or ""
        if any(abs(_mins(hhmm) - _mins(t)) <= 2 for t in mine_by.get(k, [])):
            who = "you"
        elif "@grokbot" in by and "@claude" in by:
            who = "claude-grokbot"
        elif by and owner in by:
            who = "you"
        elif "@grokbot" in by:
            who = "grokbot"
        else:
            who = "claude"
        tid, tname = thread_label(it, k, progress, bound)
        marks.append({"at": hhmm, "who": who, "kind": "answered" if m.group(6) != "done" else "done", "key": k,
                      "title": _short(it.get("text")), "answer": _short(it.get("answer"), 80) if m.group(6) != "done" else "",
                      "mine": it.get("owner") == owner or it.get("to") == owner, "thread": tid, "threadName": tname,
                      "href": "/thread?item=" + k.replace("/", "%2F")})
    for r in register or []:
        at = str(r.get("at") or "")
        if at[:10] != today.isoformat():
            continue
        path = str(r.get("path") or "")
        marks.append({"at": at[11:16], "who": str(r.get("maker") or "claude"), "kind": r.get("kind") or "made",
                      "key": r.get("id"), "title": str(r.get("title") or ""), "answer": str(r.get("line") or "")[:120],
                      "mine": False, "thread": "battery", "threadName": "The battery",
                      "href": ("/reader?path=" + path) if path else "/battery"})
    marks.sort(key=lambda x: x["at"])
    threads = {}
    for mk in marks:
        t = threads.setdefault(mk["thread"], {"thread": mk["thread"], "name": mk["threadName"], "from": mk["at"], "to": mk["at"],
                                              "marks": [], "who": []})
        t["to"] = mk["at"]
        t["marks"].append(mk)
        if mk["who"] not in t["who"]:
            t["who"].append(mk["who"])
    ordered = sorted(threads.values(), key=lambda t: t["to"], reverse=True)
    week = []
    for n in range(days_back, -1, -1):
        d = (today - dt.timedelta(days=n)).isoformat()
        c = sum(1 for it in items.values() if (it.get("owner") == owner or it.get("to") == owner)
                and str(it.get("done") or it.get("answered") or "")[:10] == d and it.get("mark") in ("x", "a"))
        week.append({"day": d, "closed": c})
    return {"today": today.isoformat(), "marks": marks, "threads": ordered, "count": len(marks), "week": week}


def _mins(hhmm):
    try:
        return int(hhmm[:2]) * 60 + int(hhmm[3:5])
    except (ValueError, TypeError):
        return -999
