# ---- the battery (0.115.0; rebuilt from 0.116.0, 2026-11-12) ----
# Two agents lined up on one file, like rooks in chess: this brain's Claude sessions and a partner agent that runs on its
# own machine and reaches this computer through a shell its owner approved. They share a mailbox folder outside every
# repository (setting `battery_folder`): to-claude/, to-<partner>/, done/, handoff/ and, since 0.116.0, requests/; one note
# per file with a header (from, to, re, needs, by, and on a reply `request:` and `state:`). The partner's key in the
# mailbox and the name the page calls it by are settings (`battery_partner`, `battery_partner_name`), so nothing shipped
# names anyone's agent or folder. The design: brain-viewer-holon/design-directions/battery-2026-11-12.md.
#   - notes for Claude: while the viewer runs it looks in to-claude/ every `battery_seconds` (20), and each new note
#     becomes one batch in context/answers-inbox.md, which wakes the live session's batch watcher (0.115.0, unchanged).
#   - requests (0.116.0): a note that asks for something (needs answer, review, build or decision-for-<owner>) opens a
#     request with an id (R-0001) and a state, named as the A2A protocol names them: submitted, working, input-required
#     (it waits on the owner), completed, failed, canceled, rejected. Only a later note that carries `request: R-0001`
#     moves it, and a note from the side that holds it with no `state:` line answers it. Moving a note to done/ never
#     does: a request whose note was filed unanswered stays that side's turn and says so. The records are worked out from
#     the notes whenever someone reads the battery (the page, an adapter call, note.py), and since 0.120.0 by the timer
#     too, so a late mark is current with no press.
#   - whose turn: computed from the open requests, never written. A request past its limit is late.
#   - the partner's wait address answers the moment a note for it lands; every call it makes is its last-seen time, and
#     the page says from that whether it is listening, when it was last here and when its next check is due.
#   - what the battery made (0.117.0): one register, context/battery-register.jsonl, written only by note.py; the page
#     draws it newest first. A partner's file lands in the brain through a Claude session, under the partner's name.
#   - fewer hops (0.118.0): the partner makes one call per turn (POST /api/battery/exchange: its notes in, what it handled
#     filed, everything waiting for it out), since each of its shell calls costs its owner an approval; a Claude session
#     that holds a request waits on its own key (GET /api/battery/wait?for=claude&owner=<session>) and gets that request's
#     notes straight, the timer leaving them out of the answers inbox while the session listens.
#   - runs (0.119.0): a run of work opens with a brief (the goal in the owner's words, what done means, the parts, and
#     "reversible work: go") and ends with a closing note written from the records; the page shows the open run and
#     where its minutes went.

BATTERY_STATE_REL = USER_REL + "/battery-state.json"
BATTERY_OPENING = ("answer", "review", "build")         # plus decision-for-<owner>: battery_needs()
BATTERY_STATES = ("submitted", "working", "input-required", "completed", "failed", "canceled", "rejected")
BATTERY_CLOSED = ("completed", "failed", "canceled", "rejected")
BATTERY_MOVES = {"submitted": {"working", "input-required", "completed", "failed", "rejected", "canceled"},
                 "working": {"working", "input-required", "completed", "failed", "canceled"},
                 "input-required": {"working", "input-required", "completed", "failed", "canceled"}}
BATTERY_LIMITS = {"answer": 15, "review": 45, "build": 120, "decision": 30}     # minutes; setting battery_limits overrides
BATTERY_NOTE_MAX = 200 * 1024
BATTERY_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{4})-([a-z0-9]+)-[a-z0-9][a-z0-9-]*\.md$")
BATTERY_RID_RE = re.compile(r"^\s*R-?(\d{1,6})\s*$", re.I)
BATTERY_AWAKE_SECONDS = 180       # a partner call this recent, or a wait it holds open, means it is listening now
_battery_lock = threading.RLock()
_battery_listening = {"n": 0}


def battery_settings():
    return load_settings(os.path.join(BRAIN, SETTINGS_REL.replace("/", os.sep)))


def battery_partner():
    """The partner's key in the mailbox: its notes say `from: <key>` and its folder is to-<key>/ (setting battery_partner)."""
    k = re.sub(r"[^a-z0-9]", "", str(battery_settings().get("battery_partner") or "").lower())
    return k if k and k not in ("claude", battery_owner()) else "partner"


def battery_partner_name():
    return str(battery_settings().get("battery_partner_name") or "").strip()[:40] or "your partner agent"


def battery_owner():
    """The owner's key in the mailbox: the brain's owner setting without its @ (a note the page writes is from it)."""
    return re.sub(r"[^a-z0-9]", "", str(OWNER or "").lower()) or "owner"


def battery_sides():
    return ("claude", battery_partner())


def battery_needs():
    return ("answer", "review", "fyi", "build", "decision-for-" + battery_owner())


def battery_root():
    """The mailbox folder, or None when this computer has none (a mentee's brain, a team copy): then nothing runs."""
    p = str(battery_settings().get("battery_folder") or "").strip() or os.path.join(os.path.expanduser("~"), "battery-mailbox")
    p = os.path.expanduser(p)
    return p if os.path.isdir(os.path.join(p, "to-claude")) and os.path.isdir(os.path.join(p, "to-" + battery_partner())) else None


def battery_page_state():
    """What the header needs at first paint (window.BV_BATTERY): whether this computer has a battery, and its partner's name."""
    try:
        door = bool(battery_root())
    except Exception:                                           # noqa: BLE001 -- a bad setting never breaks a page
        door = False
    return {"door": door, "partner": battery_partner_name() if door else ""}


def battery_seconds():
    try:
        return max(5, int(battery_settings().get("battery_seconds") or 20))
    except (TypeError, ValueError):
        return 20


def _battery_head(text):
    """The note's header lines (from, to, re, needs, by, request, state, ...) as a dict, read from the top until the first
    blank line; a header inside a ``` fence (as the README shows it) is read too."""
    head, lines = {}, text.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("```")):
        i += 1
    while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith("```"):
        m = re.match(r"^\s*([a-z]+)\s*:\s*(.*?)\s*$", lines[i])
        if not m:
            break
        head[m.group(1).lower()] = m.group(2)
        i += 1
    return head


def battery_rid(s):
    """R-7, r-0007, R0007 -> R-0007; anything else -> ''."""
    m = BATTERY_RID_RE.match(str(s or ""))
    return ("R-%04d" % int(m.group(1))) if m else ""


def _battery_note(folder, name, ap, body=True):
    try:
        st = os.stat(ap)
        with open(ap, "r", encoding="utf-8-sig", errors="replace") as f:
            text = f.read(BATTERY_NOTE_MAX)
    except OSError:
        return None
    h = _battery_head(text)
    m = BATTERY_NAME_RE.match(name)
    at = ("%sT%s:%s" % (m.group(1), m.group(2)[:2], m.group(2)[2:])) if m else dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes")
    frm = (h.get("from") or (m.group(3) if m else "") or "").strip().lower()
    to = (h.get("to") or "").strip().lower().split()[0] if (h.get("to") or "").strip() else ""
    if not to and folder.startswith("to-"):
        to = folder[3:]
    row = {"file": name, "folder": folder, "path": ap, "at": at, "bytes": st.st_size,
           "modified": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
           "from": frm, "to": to, "re": h.get("re") or "", "needs": (h.get("needs") or "").strip().lower(),
           "by": h.get("by") or "", "request": battery_rid(h.get("request")), "state": (h.get("state") or "").strip().lower(),
           "question": (h.get("question") or "").strip()[:80], "owner": (h.get("owner") or "").strip()[:80],
           "made": (h.get("made") or "").strip()[:200], "title": (h.get("title") or "").strip()[:160]}
    if body:
        row["text"] = text
    return row


def battery_notes(folders=None, body=True):
    root = battery_root()
    if not root:
        return []
    folders = folders or ("to-claude", "to-" + battery_partner(), "done")
    out = []
    for folder in folders:
        d = os.path.join(root, folder)
        try:
            names = sorted(n for n in os.listdir(d) if n.lower().endswith(".md"))
        except OSError:
            continue
        for n in names:
            r = _battery_note(folder, n, os.path.join(d, n), body)
            if r:
                out.append(r)
    out.sort(key=lambda r: (r["at"], r["file"]))
    return out


def battery_state():
    try:
        with open(os.path.join(BRAIN, BATTERY_STATE_REL.replace("/", os.sep)), "r", encoding="utf-8-sig") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def _battery_state_put(**kv):
    with _battery_lock:
        st = battery_state()
        st.update(kv)
        _json_write(os.path.join(BRAIN, BATTERY_STATE_REL.replace("/", os.sep)), st)
        return st


BATTERY_OWNER_FRESH = 600         # seconds: a Claude session that waited on its own requests this recently gets its notes itself


def _battery_note_owner(root, r):
    """The Claude session that holds a note's request: the note's own owner line, else its request's record on disk (read
    only, so the timer never writes a record)."""
    if r.get("owner"):
        return r["owner"]
    rid = r.get("request")
    if not rid:
        return ""
    rec = _json_read(os.path.join(root, "requests", rid + ".json"))
    return str(rec.get("owner") or "") if isinstance(rec, dict) else ""


def _battery_owner_listening(st, owner, now=None):
    seen = st.get("ownerSeen") if isinstance(st.get("ownerSeen"), dict) else {}
    t = _battery_time(seen.get(owner))
    return bool(owner and t and ((now or dt.datetime.now()) - t).total_seconds() <= BATTERY_OWNER_FRESH)


def battery_owner_seen(owner):
    """A Claude session waited on its own requests: for ten minutes the timer leaves its notes to it (0.118.0)."""
    with _battery_lock:
        st = battery_state()
        seen = st.get("ownerSeen") if isinstance(st.get("ownerSeen"), dict) else {}
        seen[owner] = dt.datetime.now().isoformat(timespec="seconds")
        st["ownerSeen"] = dict(sorted(seen.items(), key=lambda kv: kv[1])[-50:])
        _json_write(os.path.join(BRAIN, BATTERY_STATE_REL.replace("/", os.sep)), st)


def _battery_mark_handed(files):
    with _battery_lock:
        st = battery_state()
        now = dt.datetime.now().isoformat(timespec="seconds")
        st["handed"] = sorted(set(st.get("handed") or []) | set(files))[-500:]
        handed_at = st.get("handedAt") if isinstance(st.get("handedAt"), dict) else {}
        handed_at.update({f: handed_at.get(f) or now for f in files})
        st["handedAt"] = dict(sorted(handed_at.items())[-500:])
        _json_write(os.path.join(BRAIN, BATTERY_STATE_REL.replace("/", os.sep)), st)


def battery_check(why="the timer"):
    """Every new note in to-claude/ handed to the main session as one batch in the answers inbox, except a note whose
    request a Claude session holds and is waiting on (0.118.0): that one goes straight to the session, and only if the
    session has not listened for ten minutes does it reach the inbox. -> the notes handed on."""
    root = battery_root()
    if not root:
        return []
    with _battery_lock:
        st = battery_state()
        seen = set(st.get("handed") or [])
        new = [r for r in battery_notes(("to-claude",), body=False) if r["file"] not in seen]
        owners = {r["file"]: _battery_note_owner(root, r) for r in new}
        new = [r for r in new if not _battery_owner_listening(st, owners[r["file"]])]
        if not new:
            return []
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = ["## Batch %s (%d battery note%s)" % (stamp, len(new), "" if len(new) == 1 else "s")]
        for r in new:
            lines.append('- battery · from %s · needs: %s · "%s" · %s%s' % (r["from"] or "?", r["needs"] or "?", (r["re"] or r["file"]).replace('"', "'")[:160], r["path"],
                                                                (" · held by %s, not listening" % owners[r["file"]]) if owners.get(r["file"]) else ""))
        with _answers_lock:
            _inbox_append(lines)
        now = dt.datetime.now().isoformat(timespec="seconds")
        st["handed"] = sorted(seen | {r["file"] for r in new})[-500:]
        handed_at = st.get("handedAt") if isinstance(st.get("handedAt"), dict) else {}
        handed_at.update({r["file"]: now for r in new})
        st["handedAt"] = dict(sorted(handed_at.items())[-500:])
        st["lastHanded"] = now
        _json_write(os.path.join(BRAIN, BATTERY_STATE_REL.replace("/", os.sep)), st)
    log_line("%s -- the battery: %d note%s from %s handed to the main session as one batch (%s)"
             % (ANSWERS_INBOX_REL, len(new), "" if len(new) == 1 else "s", ", ".join(sorted({r["from"] or "?" for r in new})), why))
    return new


def battery_loop():
    """While the viewer runs: a first look 15 seconds after start, then every battery_seconds. Since 0.120.0 each look also
    keeps the request records and their late marks current (decided 11/12 by the battery's agents, written into the
    viewer's rules on what runs by itself)."""
    time.sleep(15)
    while True:
        try:
            battery_check()
            battery_sync()
        except Exception as e:                                  # noqa: BLE001 -- the loop outlives one bad look
            sys.stderr.write("battery: the look stopped (%s: %s)\n" % (type(e).__name__, e))
        time.sleep(battery_seconds())


# ---- requests (0.116.0) ----

def _battery_time(s):
    try:
        return dt.datetime.fromisoformat(str(s or "").strip()[:19]) if s else None
    except ValueError:
        return None


def _battery_note_time(n):
    """A note's time to the second: its file's own time when it falls in the minute its name says, else the name's minute."""
    mod = str(n.get("modified") or "")
    return mod if mod[:16] == n["at"][:16] else n["at"] + ":00"


def _battery_records(root):
    d = os.path.join(root, "requests")
    out = {}
    try:
        names = os.listdir(d)
    except OSError:
        return out
    for x in names:
        if not x.endswith(".json") or not battery_rid(x[:-5]):
            continue
        rec = _json_read(os.path.join(d, x))
        if isinstance(rec, dict) and rec.get("id") == battery_rid(x[:-5]):
            out[rec["id"]] = rec
    return out


def _battery_record_write(root, rec):
    d = os.path.join(root, "requests")
    os.makedirs(d, exist_ok=True)
    _json_write(os.path.join(d, rec["id"] + ".json"), rec)


def _battery_kind(needs):
    return "decision" if str(needs or "").startswith("decision-for-") else str(needs or "")


def _battery_open(rid, n, parent=""):
    at = _battery_note_time(n)
    to = n["to"] or ("claude" if n["from"] != "claude" else battery_partner())
    return {"id": rid, "re": (n["re"] or n["file"])[:160], "from": n["from"] or "?", "to": to, "needs": n["needs"],
            "by": n["by"] if n["by"] and n["by"].lower() != "whenever" else "", "owner": n.get("owner") or "",
            "state": "submitted", "createdAt": at, "deliveredAt": "", "notes": [n["file"]], "parent": parent,
            "question": n.get("question") or "", "history": [{"state": "submitted", "at": at, "by": n["from"] or "?", "note": n["file"]}]}


def _battery_apply(rec, n):
    """One note that names a request: the side holding it moves it (a note with no state line answers it), the side that
    asked may cancel it, and anyone may add to it. A move the states do not allow is kept in the history as refused."""
    who, st, at = n["from"], n.get("state") or "", _battery_note_time(n)
    cur = rec.get("state") or "submitted"
    if who == "claude" and n.get("owner"):
        rec["owner"] = n["owner"]                    # 0.118.0: the Claude session that holds it from now on
    if who == rec.get("to"):
        new = st or "completed"
    elif st == "canceled" and who in (rec.get("from"), battery_owner()):
        new = "canceled"
    else:
        rec["history"].append({"state": cur, "at": at, "by": who, "note": n["file"], "added": True})
        return
    if new not in BATTERY_STATES or new not in BATTERY_MOVES.get(cur, set()):
        rec["history"].append({"state": cur, "at": at, "by": who, "note": n["file"],
                               "refused": "%s cannot become %s" % (cur, new) if new in BATTERY_STATES else "%s is not a state" % new})
        return
    rec["state"] = new
    if new == "input-required" and n.get("question"):
        rec["question"] = n["question"]
    if new in BATTERY_CLOSED:
        rec["closedAt"] = at
    rec["history"].append({"state": new, "at": at, "by": who, "note": n["file"]})


def battery_sync(partner_call=False):
    """Bring the request records up to date with the notes; -> {id: record}. Run on every read, never by a timer.
    The first run starts the records: notes already in done/ then are history and open nothing."""
    root = battery_root()
    if not root:
        return {}
    with _battery_lock:
        st = battery_state()
        since = st.get("requestsSince")
        if not since:
            since = dt.datetime.now().isoformat(timespec="minutes")
            st = _battery_state_put(requestsSince=since)
        recs = _battery_records(root)
        claimed = {f for r in recs.values() for f in r.get("notes") or []}
        handed_at = st.get("handedAt") if isinstance(st.get("handedAt"), dict) else {}
        changed = set()
        nxt = max([int(i[2:]) for i in recs] or [0]) + 1
        opening = BATTERY_OPENING + ("decision-for-" + battery_owner(),)
        for n in battery_notes(body=False):
            if n["file"] in claimed:
                continue
            claimed.add(n["file"])
            rec = recs.get(n["request"]) if n["request"] else None
            if rec:
                _battery_apply(rec, n)
                rec.setdefault("notes", []).append(n["file"])
                changed.add(rec["id"])
                # an answer that asks something back opens a new request the other way
                if n["from"] == rec.get("to") and n["needs"] in opening and (n.get("state") or "completed") in BATTERY_CLOSED:
                    rid = "R-%04d" % nxt
                    nxt += 1
                    recs[rid] = _battery_open(rid, n, parent=rec["id"])
                    changed.add(rid)
                continue
            if n["needs"] not in opening:
                continue
            if n["folder"] == "done" and n["at"] < since:
                continue                                       # filed before the records began
            rid = "R-%04d" % nxt
            nxt += 1
            recs[rid] = _battery_open(rid, n)
            changed.add(rid)
        partner, now = battery_partner(), dt.datetime.now().isoformat(timespec="seconds")
        for rec in recs.values():
            if rec.get("deliveredAt") or rec.get("state") in BATTERY_CLOSED:
                continue
            first = (rec.get("notes") or [""])[0]
            if rec.get("to") == "claude" and handed_at.get(first):
                rec["deliveredAt"] = handed_at[first]
                changed.add(rec["id"])
            elif rec.get("to") == partner and partner_call and (rec.get("createdAt") or "") <= now:
                rec["deliveredAt"] = now
                changed.add(rec["id"])
        for rid in changed:
            _battery_record_write(root, recs[rid])
        return recs


def battery_partner_call():
    """The partner called the viewer: that time is when it was last here, and what waited for it is delivered."""
    _battery_state_put(partnerLastCall=dt.datetime.now().isoformat(timespec="seconds"))


def _battery_hours():
    """The partner's waking hours (setting battery_partner_hours, "08:00-23:50"), or None for always."""
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", str(battery_settings().get("battery_partner_hours") or ""))
    return (dt.time(int(m.group(1)), int(m.group(2))), dt.time(int(m.group(3)), int(m.group(4)))) if m else None


def _battery_in_hours(t, hours):
    if not hours:
        return True
    a, b = hours
    return a <= t.time() <= b if a <= b else (t.time() >= a or t.time() <= b)


def _battery_next_open(t, hours):
    """The first moment at or after t inside the waking hours."""
    if _battery_in_hours(t, hours):
        return t
    a = hours[0]
    day = dt.datetime.combine(t.date(), a)
    return day if day > t else day + dt.timedelta(days=1)


def battery_partner_status(now=None):
    now = now or dt.datetime.now()
    st, hours = battery_state(), _battery_hours()
    try:
        every = max(0, int(battery_settings().get("battery_partner_every") or 0))
    except (TypeError, ValueError):
        every = 0
    seen = [t for t in [_battery_time(st.get("partnerLastCall"))] if t]
    partner = battery_partner()
    for n in battery_notes(("to-claude", "done"), body=False)[-60:]:
        if n["from"] == partner:
            t = _battery_time(_battery_note_time(n))
            if t:
                seen.append(t)
    last = max(seen) if seen else None
    listening = _battery_listening["n"] > 0
    awake = listening or bool(last and (now - last).total_seconds() <= BATTERY_AWAKE_SECONDS)
    nxt = None
    if every and last:
        nxt = last + dt.timedelta(minutes=every)
        while nxt <= now:
            nxt += dt.timedelta(minutes=every)
        if hours:
            nxt = _battery_next_open(nxt, hours)
    return {"key": partner, "name": battery_partner_name(), "listening": listening, "awake": awake,
            "lastSeen": last.isoformat(timespec="seconds") if last else None,
            "nextCheck": nxt.isoformat(timespec="minutes") if nxt else None, "every": every,
            "hours": "%s-%s" % (hours[0].strftime("%H:%M"), hours[1].strftime("%H:%M")) if hours else ""}


def _battery_limit(kind):
    lim = dict(BATTERY_LIMITS)
    over = battery_settings().get("battery_limits")
    if isinstance(over, dict):
        for k, v in over.items():
            try:
                lim[str(k)] = max(1, int(v))
            except (TypeError, ValueError):
                pass
    return lim.get(kind, 30)


def _battery_due(rec, status):
    """When a request is late: its `by:` when that is a time, else its start plus the limit for its kind. A request for the
    partner that it has not yet picked up starts at its next check, as that is when it can. A pick-up earlier than that
    check starts the clock at delivery (sooner). A late first call must not push the due time past that unpicked-up start,
    or lateness already accrued while the partner was away would be hidden."""
    created = _battery_time(rec.get("createdAt")) or dt.datetime.now()
    by = str(rec.get("by") or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}$", by):
        t = _battery_time(by.replace(" ", "T") if len(by.split(" ")[-1]) == 5 else by.replace(" ", "T0"))
        if t:
            return t
    start = _battery_time(rec.get("deliveredAt")) or created
    if rec.get("to") == status["key"]:
        earliest = created + dt.timedelta(minutes=status["every"]) if status["every"] else created
        hours = _battery_hours()
        if hours:
            earliest = _battery_next_open(earliest, hours)
        start = earliest if not rec.get("deliveredAt") else min(start, earliest)
    return start + dt.timedelta(minutes=_battery_limit(_battery_kind(rec.get("needs"))))


def _battery_age(seconds):
    m = max(0, int(seconds // 60))
    if m < 60:
        return "%d min" % m
    if m < 48 * 60:
        return "%d h %d min" % (m // 60, m % 60) if m % 60 else "%d h" % (m // 60)
    return "%d days" % (m // (24 * 60))


def battery_turn_data(recs=None, now=None):
    """Whose turn it is, from the open requests: the lead request (the latest-overdue, else the oldest), a line for it, the
    count each side holds, every open request with its holder, age and late mark, and the partner's state."""
    root = battery_root()
    if not root:
        return {"enabled": False}
    now = now or dt.datetime.now()
    recs = recs if recs is not None else battery_sync()
    status = battery_partner_status(now)
    owner, partner, pname = battery_owner(), status["key"], status["name"]
    names = {"claude": "Claude", partner: pname, owner: "you"}
    in_done = set()
    try:
        in_done = {x for x in os.listdir(os.path.join(root, "done"))}
    except OSError:
        pass
    open_, closed = [], []
    for rec in recs.values():
        if rec.get("state") in BATTERY_CLOSED:
            closed.append(rec)
            continue
        holder = owner if rec.get("state") == "input-required" else rec.get("to") or "claude"
        created = _battery_time(rec.get("createdAt")) or now
        due = _battery_due(rec, status)
        late = holder != owner and now > due
        filed = rec.get("state") == "submitted" and (rec.get("notes") or [""])[0] in in_done
        open_.append(dict(rec, holder=holder, holderName=names.get(holder, holder), age=_battery_age((now - created).total_seconds()),
                          ageSeconds=int((now - created).total_seconds()), due=due.isoformat(timespec="minutes"), late=late, filed=filed))
    open_.sort(key=lambda r: (not r["late"], r["createdAt"]))
    counts = {k: sum(1 for r in open_ if r["holder"] == k) for k in ("claude", partner, owner)}
    lead = open_[0] if open_ else None
    if not lead:
        line, turn = "Nothing is waiting on either side.", None
    else:
        turn = lead["holder"]
        who = "Your turn" if turn == owner else "%s's turn" % names.get(turn, turn)
        re_ = lead["re"] if len(lead["re"]) <= 80 else lead["re"][:78].rstrip() + "…"
        line = "%s: %s, waiting %s%s%s." % (who, re_, lead["age"], ", late" if lead["late"] else "",
                                             ", filed but not answered" if lead["filed"] else "")
        rest = []
        for k in ("claude", partner, owner):
            c = counts[k] - (1 if k == turn else 0)
            if c:
                rest.append(("%d more with %s" if k == turn else "%d with %s") % (c, names.get(k, k)))
        if rest:
            line += " Also waiting: %s." % ", ".join(rest)
    if status["listening"]:
        pline = "%s is listening now." % pname
    elif status["awake"]:
        pline = "%s was here a moment ago." % pname
    elif status["lastSeen"]:
        t = _battery_time(status["lastSeen"])
        pline = "%s was last here %s%s." % (pname, _battery_clock(t, now),
                                             (", next check about %s" % _battery_clock(_battery_time(status["nextCheck"]), now)) if status["nextCheck"] else "")
    else:
        pline = "%s has not called this viewer yet." % pname
    closed.sort(key=lambda r: r.get("closedAt") or r.get("createdAt") or "", reverse=True)
    return {"enabled": True, "turn": turn, "turnName": names.get(turn, turn) if turn else None, "line": line,
            "late": any(r["late"] for r in open_), "counts": {"claude": counts["claude"], "partner": counts[partner], "you": counts[owner]},
            "open": open_, "closed": closed[:12], "partner": status, "partnerLine": pline, "owner": owner,
            "at": now.isoformat(timespec="seconds")}


def _battery_clock(t, now):
    if not t:
        return ""
    c = t.strftime("%I:%M%p").lstrip("0").lower()
    return c if t.date() == now.date() else "%s %s" % (t.strftime("%b %d").replace(" 0", " "), c)


def battery_turn(q):
    """GET /api/battery/turn?as=claude|<partner>: whose turn it is. A call as the partner is its last-seen time."""
    if not battery_root():
        return 404, {"error": "no battery folder on this computer"}
    as_ = (q.get("as", [""])[0] or "").strip().lower()
    if as_ and as_ not in battery_sides():
        return 400, {"error": "as= takes claude or %s" % battery_partner()}
    if as_ == battery_partner():
        battery_partner_call()
    return 200, battery_turn_data(battery_sync(partner_call=as_ == battery_partner()))


def battery_request(q):
    """GET /api/battery/request?id=R-0007: one request's record and the notes on it, oldest first."""
    root = battery_root()
    if not root:
        return 404, {"error": "no battery folder on this computer"}
    rid = battery_rid(q.get("id", [""])[0])
    recs = battery_sync()
    if not rid or rid not in recs:
        return 404, {"error": "no request %s" % (q.get("id", [""])[0] or "named")}
    names = set(recs[rid].get("notes") or [])
    return 200, {"request": recs[rid], "notes": [n for n in battery_notes() if n["file"] in names]}


def battery_progress_live(p):
    """Today's In progress instrument for the battery (setting battery_progress, default the-battery) shows whose turn it
    is, live, in place of its note, and the line opens the Battery page."""
    if not battery_root():
        return None
    if str(p.get("id") or "") != (str(battery_settings().get("battery_progress") or "").strip() or "the-battery"):
        return None
    t = battery_turn_data()
    today = dt.date.today().isoformat()
    made = sum(1 for r in battery_register() if str(r.get("at") or "").startswith(today))
    sub = t.get("partnerLine", "") + ((" %d made today." % made) if made else "")
    return {"line": t.get("line", ""), "partner": sub.strip(), "late": bool(t.get("late")), "href": "/battery"}


PROGRESS_LIVE.append(battery_progress_live)


BATTERY_DESK_FRESH = 180          # seconds: the desk session rewrites desk.json every 30 while its watcher runs


def battery_mailbox_dirs():
    return ("handoff", "done", "to-claude", "to-" + battery_partner(), "requests")


# ---- what the battery made: the register (0.117.0, round two of the design) ----
# One line per made thing in context/battery-register.jsonl (setting battery_register), written only by
# skills/battery/note.py (`made` for a thing already in the brain, `land` for a file the partner left in the mailbox,
# copied into deliverables/battery/<day>/ under its maker's name). The page draws it newest first; nothing is read off the
# notes any more. A partner's file it proposes for the list (a note with a `made:` header naming a mailbox file) shows as
# waiting to be landed until a Claude session lands it.

BATTERY_REGISTER_DEFAULT = "context/battery-register.jsonl"


def battery_register_rel():
    return (str(battery_settings().get("battery_register") or "").strip() or BATTERY_REGISTER_DEFAULT).replace("\\", "/")


def battery_register():
    """The register's rows, newest first, each with whether its file is there and the address that opens it."""
    ap = os.path.join(BRAIN, battery_register_rel().replace("/", os.sep))
    rows = []
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("id"):
                    rows.append(r)
    except OSError:
        return []
    out = []
    for r in rows:
        rel = str(r.get("path") or "").replace("\\", "/").strip("/")
        if rel and (".." in rel.split("/") or os.path.basename(rel) in NEVER_READ_NAMES_BATTERY):
            continue
        ap2 = os.path.join(BRAIN, rel.replace("/", os.sep)) if rel else ""
        out.append(dict(r, path=rel, exists=bool(ap2 and os.path.exists(ap2)), where="brain" if rel else "release"))
    out.sort(key=lambda r: (str(r.get("at") or ""), str(r.get("id") or "")), reverse=True)
    return out


def battery_proposed(notes=None, rows=None):
    """Files the partner offered for the list (a note's `made:` header) that no row has landed yet."""
    notes = notes if notes is not None else battery_notes(body=False)
    landed = {str(r.get("from") or "") for r in (rows if rows is not None else battery_register())}
    out, seen = [], set()
    for n in notes:
        src = str(n.get("made") or "").replace("\\", "/").strip("/")
        if not src or src in landed or src in seen or src.split("/")[0] not in ("handoff", "done") or ".." in src.split("/"):
            continue                                   # only a file in the mailbox can be landed
        seen.add(src)
        out.append({"from": src, "title": (n.get("title") or os.path.basename(src))[:160], "maker": n.get("from") or "",
                    "at": _battery_note_time(n), "request": n.get("request") or "", "note": n["file"], "proposed": True})
    out.sort(key=lambda r: r["at"], reverse=True)
    return out


def battery_made_api(q):
    """GET /api/battery/made?since=&limit=: the register newest first, then what waits to be landed."""
    if not battery_root():
        return 404, {"error": "no battery folder on this computer"}
    since = (q.get("since", [""])[0] or "").strip()
    try:
        limit = max(1, min(500, int(q.get("limit", ["100"])[0])))
    except ValueError:
        limit = 100
    rows = battery_register()
    if since:
        rows = [r for r in rows if str(r.get("at") or "") > since]
    return 200, {"rows": rows[:limit], "count": len(rows), "proposed": battery_proposed(rows=battery_register()),
                 "register": battery_register_rel()}


# the brain's key files never appear on the list, even if a note names one (the viewer's own NEVER_READ guard covers reads)
NEVER_READ_NAMES_BATTERY = {"APIZZLE.txt", "PF App API.txt", "Onboarding API.txt", "pfk_key.txt", "deepseek_key.txt", "Claude SetupToken.txt",
                            "hf_key.txt", "tally_key.txt", "typeform_key.txt", "openai_key.txt", "gemini_key.txt", "fal_key.txt", "sharing-signin.json"}


def battery_file(q):
    """GET /api/battery/file?path=handoff/<name> (or done/, to-claude/, to-<partner>/): one mailbox file's text, for the
    Battery page's drawer. Only inside the mailbox, only text."""
    root = battery_root()
    if not root:
        return 404, {"error": "no battery folder on this computer"}
    rel = (q.get("path", [""])[0] or "").replace("\\", "/").strip("/")
    parts = rel.split("/")
    dirs = [d for d in battery_mailbox_dirs() if d != "requests"]
    if len(parts) != 2 or parts[0] not in dirs or not parts[1] or parts[1].startswith(".") or ".." in rel:
        return 400, {"error": "a mailbox file is one of %s and a name" % ", ".join(d + "/" for d in dirs)}
    ap = os.path.join(root, parts[0], parts[1])
    if not os.path.isfile(ap):
        return 404, {"error": "no such file in the mailbox: %s" % rel}
    try:
        with open(ap, "r", encoding="utf-8-sig", errors="replace") as f:
            text = f.read(BATTERY_NOTE_MAX * 4)
    except OSError as e:
        return 500, {"error": str(e)}
    return 200, {"path": rel, "text": text, "kind": "patch" if rel.endswith(".patch") else "text"}


def battery_desk():
    """The battery desk: the standing Claude session that takes every note (skills/battery/readme.md). It rewrites
    desk.json in the mailbox every 30 seconds while it watches; fresher than three minutes means it is on, and the main
    session leaves battery notes to it."""
    root = battery_root()
    ap = root and os.path.join(root, "desk.json")
    if not ap or not os.path.isfile(ap):
        return {"on": False, "at": None, "name": None}
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    age = time.time() - os.path.getmtime(ap)
    return {"on": age <= BATTERY_DESK_FRESH, "at": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds"),
            "name": d.get("name") if isinstance(d, dict) else None, "ageSeconds": int(age)}


def _battery_tag(notes, recs):
    """Each note's request id: the one its header names, else the one it opened."""
    opened = {f: rid for rid, r in recs.items() for f in (r.get("notes") or [])[:1]}
    for n in notes:
        n["request"] = n.get("request") or opened.get(n["file"], "")
    return notes


def battery_api(q):
    """GET /api/battery: the whole exchange, whose turn it is, the board, and what waits on each side."""
    root = battery_root()
    if not root:
        return 200, {"enabled": False, "why": "no battery folder on this computer (setting battery_folder)"}
    partner = battery_partner()
    as_ = (q.get("as", [""])[0] or "").strip().lower()
    if as_ == partner:
        battery_partner_call()
    recs = battery_sync(partner_call=as_ == partner)
    notes = _battery_tag(battery_notes(), recs)
    board = ""
    try:
        with open(os.path.join(root, "board.md"), "r", encoding="utf-8-sig") as f:
            board = f.read(64 * 1024)
    except OSError:
        pass
    try:
        handoff = sorted(n for n in os.listdir(os.path.join(root, "handoff")) if not n.startswith("."))
    except OSError:
        handoff = []
    st = battery_state()
    rows = battery_register()
    waiting = {"claude": [r["file"] for r in notes if r["folder"] == "to-claude"],
               "partner": [r["file"] for r in notes if r["folder"] == "to-" + partner]}
    waiting[partner] = waiting["partner"]           # the partner's own key too, as 0.115.0 answered
    try:
        thread = threads_for_progress().get(str(battery_settings().get("battery_progress") or "").strip() or "the-battery")
    except Exception:                               # noqa: BLE001 -- the thread link is a convenience
        thread = None
    return 200, {"enabled": True, "folder": root, "partner": partner, "partnerName": battery_partner_name(), "owner": battery_owner(),
                 "notes": notes, "board": board, "handoff": handoff, "thread": thread, "waiting": waiting,
                 "lastHanded": st.get("lastHanded"), "seconds": battery_seconds(), "desk": battery_desk(),
                 "turn": battery_turn_data(recs), "made": rows, "proposed": battery_proposed(notes, rows),
                 "register": battery_register_rel(), "runs": battery_runs(recs)}


def battery_wait(q):
    """GET /api/battery/wait?for=claude|<partner>&after=<file name>&seconds=N: answers as soon as a note for that side
    lands whose file name sorts after `after` (every note is named by its time), or with an empty list after N seconds
    (at most 900). One address an agent can block on instead of watching a folder. While the partner holds it open, the
    page says it is listening; each note comes with its request id."""
    side = (q.get("for", [""])[0] or "").strip().lower()
    if side not in battery_sides():
        return 400, {"error": "for= takes claude or %s" % battery_partner()}
    if not battery_root():
        return 404, {"error": "no battery folder on this computer"}
    after = (q.get("after", [""])[0] or "").strip()
    try:
        secs = min(900, max(1, int(q.get("seconds", ["300"])[0])))
    except ValueError:
        secs = 300
    owner = (q.get("owner", [""])[0] or "").strip()[:80]
    if owner and side != "claude":
        return 400, {"error": "owner= is for a Claude session waiting on its own requests"}
    root = battery_root()
    is_partner = side == battery_partner()
    if is_partner:
        battery_partner_call()
        with _battery_lock:
            _battery_listening["n"] += 1
    if owner:
        battery_owner_seen(owner)
    try:
        end = time.time() + secs
        while True:
            rows = [r for r in battery_notes(("to-" + side,)) if r["file"] > after]
            if owner:
                rows = [r for r in rows if _battery_note_owner(root, r) == owner]
            if rows or time.time() >= end:
                break
            time.sleep(2)
    finally:
        if is_partner:
            with _battery_lock:
                _battery_listening["n"] = max(0, _battery_listening["n"] - 1)
            battery_partner_call()
        if owner:
            battery_owner_seen(owner)
    if owner and rows:
        _battery_mark_handed([r["file"] for r in rows])     # delivered to its session: the timer never batches it
    recs = battery_sync(partner_call=is_partner)
    return 200, {"for": side, "owner": owner, "notes": _battery_tag(rows, recs), "timedOut": not rows}


def _battery_slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")
    return (s[:48].rstrip("-") or "note")


def _battery_note_error(data):
    """Why a note cannot be written, or None. Shared by the page's write and the partner's exchange, so every note in an
    exchange is checked before any is written."""
    sides, owner = battery_sides(), battery_owner()
    to = str(data.get("to") or "").strip().lower()
    frm = str(data.get("from") or owner).strip().lower()
    if to not in sides:
        return "to takes %s" % " or ".join(sides)
    if frm not in sides + (owner,) or frm == to:
        return "from takes %s, and is not the side it goes to" % ", ".join(sides + (owner,))
    if str(data.get("needs") or "fyi").strip().lower() not in battery_needs():
        return "needs takes one of: " + ", ".join(battery_needs())
    if data.get("request") and not battery_rid(data.get("request")):
        return "request takes an id like R-0007"
    state = str(data.get("state") or "").strip().lower()
    if state and (state not in BATTERY_STATES or not data.get("request")):
        return "state takes one of %s, on a note that names its request" % ", ".join(BATTERY_STATES[1:])
    made = str(data.get("made") or "").replace("\\", "/").strip("/")
    if made and (made.split("/")[0] not in ("handoff", "done") or ".." in made.split("/")):
        return "made names a file in the mailbox's handoff/ or done/"
    text = str(data.get("text") or "").strip()
    if not text:
        return "the note is empty"
    if len(text.encode("utf-8")) > BATTERY_NOTE_MAX:
        return "a note is at most 200 KB; put a long piece in handoff/ and point at it"
    if re.search(r"\b(pf_tok_|pfk_|sk-ant-|ghp_|xai-|sk-proj-)[A-Za-z0-9_-]{8,}", text):
        return "the note carries something shaped like a key or token; a note never holds one"
    return None


def battery_write(data):
    """POST /api/battery/note {to, re, needs, text, from?, request?, state?, question?, made?, title?, owner?}: one note
    written with the README's header. The page writes them as the owner; a note to Claude is handed to the main session
    at the next look."""
    root = battery_root()
    if not root:
        return 404, {"error": "no battery folder on this computer"}
    err = _battery_note_error(data)
    if err:
        return (413 if "200 KB" in err else 400), {"error": err}
    sides, owner = battery_sides(), battery_owner()
    to = str(data.get("to") or "").strip().lower()
    frm = str(data.get("from") or owner).strip().lower()
    if to not in sides:
        return 400, {"error": "to takes %s" % " or ".join(sides)}
    if frm not in sides + (owner,) or frm == to:
        return 400, {"error": "from takes %s, and is not the side it goes to" % ", ".join(sides + (owner,))}
    needs = str(data.get("needs") or "fyi").strip().lower()
    if needs not in battery_needs():
        return 400, {"error": "needs takes one of: " + ", ".join(battery_needs())}
    rid = battery_rid(data.get("request")) if data.get("request") else ""
    if data.get("request") and not rid:
        return 400, {"error": "request takes an id like R-0007"}
    state = str(data.get("state") or "").strip().lower()
    if state and (state not in BATTERY_STATES or not rid):
        return 400, {"error": "state takes one of %s, on a note that names its request" % ", ".join(BATTERY_STATES[1:])}
    text, re_ = str(data.get("text") or "").strip(), str(data.get("re") or "").strip()[:160]
    if not text:
        return 400, {"error": "the note is empty"}
    if len(text.encode("utf-8")) > BATTERY_NOTE_MAX:
        return 413, {"error": "a note is at most 200 KB; put a long piece in handoff/ and point at it"}
    now = dt.datetime.now()
    d = os.path.join(root, "to-" + to)
    name = "%s-%s-%s.md" % (now.strftime("%Y-%m-%d-%H%M"), frm, _battery_slug(re_ or text[:40]))
    n = 2
    while os.path.exists(os.path.join(d, name)):
        name = "%s-%s-%s-%d.md" % (now.strftime("%Y-%m-%d-%H%M"), frm, _battery_slug(re_ or text[:40]), n)
        n += 1
    extra = "".join("%s: %s\n" % (k, v) for k, v in (
        ("request", rid), ("state", state), ("question", str(data.get("question") or "").strip()[:80]),
        ("made", str(data.get("made") or "").replace("\\", "/").strip("/")[:200]), ("title", str(data.get("title") or "").strip()[:160]),
        ("owner", str(data.get("owner") or "").strip()[:80])) if v)
    body = "from: %s\nto: %s\nre: %s\nneeds: %s\nby: %s\n%s\n%s\n" % (
        frm, to, re_ or "(no topic)", needs, str(data.get("by") or "whenever").strip()[:40], extra, text)
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    if to == "claude":
        threading.Thread(target=battery_check, args=("a note was written on the Battery page",), daemon=True).start()
    return 200, {"ok": True, "file": name, "folder": "to-" + to}


# ---- the partner's one call per turn (0.118.0, round three) ----
# Every shell call the partner makes to this computer waits for its owner's approval (its note of 11/11, 21:21), so a turn
# is one call: its notes in, the notes it handled filed, and everything waiting for it out, whole, with whose turn it is.

BATTERY_EXCHANGE_KEYS = 200


def _battery_exchange_out(after, wait, seen=None):
    """What waits for the partner: the notes after `after`, or, with `seen` (the notes already handed to it, which the
    viewer keeps), every note it has not been given yet; file names in one minute do not sort by time, a kept set does."""
    partner = battery_partner()
    new = (lambda r: r["file"] not in seen) if seen is not None else (lambda r: r["file"] > after)
    if wait:
        battery_partner_call()
        with _battery_lock:
            _battery_listening["n"] += 1
        try:
            end = time.time() + wait
            while not [r for r in battery_notes(("to-" + partner,), body=False) if new(r)] and time.time() < end:
                time.sleep(2)
        finally:
            with _battery_lock:
                _battery_listening["n"] = max(0, _battery_listening["n"] - 1)
    battery_partner_call()
    recs = battery_sync(partner_call=True)
    waiting = _battery_tag([r for r in battery_notes(("to-" + partner,)) if new(r)], recs)
    t = battery_turn_data(recs)
    yours = [{"id": r["id"], "re": r["re"], "needs": r["needs"], "state": r["state"], "age": r["age"], "late": r["late"],
              "filed": r["filed"], "notes": r.get("notes") or []} for r in t.get("open") or [] if r.get("holder") == partner]
    return {"waiting": waiting, "newest": max([after] + [r["file"] for r in waiting]),
            "turn": {"line": t.get("line"), "partnerLine": t.get("partnerLine"), "yours": yours}}


def battery_exchange(data):
    """POST /api/battery/exchange {key, as, notes?: [{to?, re, needs?, by?, request?, state?, question?, made?, title?,
    text}], done?: [file names in to-<partner>/], after?: <the newest file name it has read>, wait?: seconds, 0 to 600}
    -> {wrote, filed, repeat, waiting, newest, turn}. GET /api/battery/exchange?as=&after=&wait= is the same call with
    nothing to write. Every note is checked before any is written; a repeated key writes nothing again and answers with
    what the first call wrote."""
    root = battery_root()
    if not root:
        return 404, {"error": "no battery folder on this computer"}
    partner = battery_partner()
    if str(data.get("as") or "").strip().lower() != partner:
        return 400, {"error": "as names the partner, %s" % partner}
    notes, done = data.get("notes") or [], data.get("done") or []
    if not isinstance(notes, list) or len(notes) > 20 or not all(isinstance(n, dict) for n in notes):
        return 400, {"error": "notes is a list of at most 20 notes"}
    if isinstance(done, str):
        done = [x.strip() for x in done.split(",") if x.strip()]
    if not isinstance(done, list) or len(done) > 50:
        return 400, {"error": "done is a list of at most 50 file names"}
    after = data.get("after")
    kept = after is None or not str(after).strip()                  # no after=: the viewer keeps what it has handed over
    after = "" if kept else str(after).strip()
    try:
        wait = max(0, min(600, int(data.get("wait") or 0)))
    except (TypeError, ValueError):
        wait = 0
    key = str(data.get("key") or "").strip()[:80]
    if (notes or done) and not key:
        return 400, {"error": "a call that writes carries a key, so a retry never writes twice"}
    battery_partner_call()
    wrote, filed, repeat = [], [], False
    if notes or done:
        with _battery_lock:
            st = battery_state()
            keys = st.get("exchangeKeys") if isinstance(st.get("exchangeKeys"), dict) else {}
            prior = keys.get(key)
            if prior:
                wrote, filed, repeat = prior.get("wrote") or [], prior.get("filed") or [], True
            else:
                notes = [dict(n, **{"from": partner, "to": str(n.get("to") or "claude").strip().lower()}) for n in notes]
                held = [r for r in battery_sync().values() if r.get("to") == partner and r.get("state") not in BATTERY_CLOSED]
                for i, n in enumerate(notes):
                    err = _battery_note_error(n)
                    if not err and not n.get("request"):
                        same = [r["id"] for r in held if str(r.get("re") or "").strip().lower() == str(n.get("re") or "").strip().lower()]
                        if same:
                            err = ("it answers %s (the same topic) but names no request; add \"request\": \"%s\", or the request "
                                   "stays yours and goes late" % (same[0], same[0]))
                    if err:
                        return 400, {"error": "note %d: %s; nothing was written" % (i + 1, err)}
                pd = os.path.join(root, "to-" + partner)
                for name in done:
                    if not BATTERY_NAME_RE.match(str(name)) or not os.path.isfile(os.path.join(pd, str(name))):
                        return 400, {"error": "done names a note in to-%s/: %s is not one; nothing was written" % (partner, name)}
                for n in notes:
                    code, out = battery_write(n)
                    if code != 200:
                        return code, dict(out, wrote=wrote)
                    wrote.append(out["file"])
                os.makedirs(os.path.join(root, "done"), exist_ok=True)
                for name in done:
                    os.replace(os.path.join(pd, name), os.path.join(root, "done", name))
                    filed.append(name)
                keys[key] = {"wrote": wrote, "filed": filed, "at": dt.datetime.now().isoformat(timespec="seconds")}
                st = battery_state()
                st["exchangeKeys"] = dict(sorted(keys.items(), key=lambda kv: kv[1].get("at") or "")[-BATTERY_EXCHANGE_KEYS:])
                _json_write(os.path.join(BRAIN, BATTERY_STATE_REL.replace("/", os.sep)), st)
    seen = set(battery_state().get("partnerSeen") or []) if kept else None
    out = _battery_exchange_out(after, wait if not wrote else 0, seen)
    with _battery_lock:
        st = battery_state()
        st["partnerSeen"] = sorted(set(st.get("partnerSeen") or []) | {r["file"] for r in out["waiting"]})[-500:]
        _json_write(os.path.join(BRAIN, BATTERY_STATE_REL.replace("/", os.sep)), st)
    return 200, dict(out, wrote=wrote, filed=filed, repeat=repeat)


def battery_exchange_get(q):
    """GET /api/battery/exchange?as=<partner>&wait=<seconds>: the exchange with nothing to write, one call the partner
    can make the same way every time: with no after= it picks up from its last read, which the viewer keeps."""
    data = {"as": q.get("as", [""])[0], "wait": q.get("wait", ["0"])[0]}
    if q.get("after"):
        data["after"] = q["after"][0]
    return battery_exchange(data)


# ---- runs (0.119.0, round four): a brief when a run of work opens, a closing note when it ends ----
# A run is one file in deliverables/battery/runs/ (setting battery_runs), written only by note.py run open and run close:
# the goal in the owner's words, what done means, the parts and who has each, "reversible work: go", and at the close
# every thing made in the run, what waits on the owner and what carries over, written from the records. The page draws
# the open run, where its minutes went (from the request records), and the earlier runs folded.

BATTERY_RUNS_DEFAULT = "deliverables/battery/runs"


def battery_runs_rel():
    return (str(battery_settings().get("battery_runs") or "").strip() or BATTERY_RUNS_DEFAULT).replace("\\", "/").strip("/")


def _battery_run_front(text):
    out, lines = {}, text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return out
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([a-z]+):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def _battery_minutes(recs, start, end):
    """Where a run's minutes went: for each request made in it, the time each side held it (the side asked while it
    waited or was worked on, the owner while it waited on them), and how much of it was past the request's limit."""
    status = battery_partner_status()
    owner, partner = battery_owner(), status["key"]
    held = {"claude": 0.0, partner: 0.0, owner: 0.0}
    late = 0.0
    for rec in recs.values():
        created = _battery_time(rec.get("createdAt"))
        if not created or created < start or (end and created > end):
            continue
        hist = rec.get("history") or []
        marks = [(created, rec.get("to"))]
        for h in hist[1:]:
            t = _battery_time(h.get("at"))
            if t and not h.get("refused") and not h.get("added"):
                marks.append((t, owner if h.get("state") == "input-required" else None if h.get("state") in BATTERY_CLOSED else rec.get("to")))
        stop = _battery_time(rec.get("closedAt")) or end or dt.datetime.now()
        for (t0, who), (t1, _) in zip(marks, marks[1:] + [(stop, None)]):
            if who in held and t1 > t0:
                held[who] += (t1 - t0).total_seconds()
        due = _battery_due(rec, status)
        if rec.get("state") != "input-required" and stop > due:
            late += (stop - max(due, created)).total_seconds()
    names = {"claude": "Claude", partner: status["name"], owner: "you"}
    return {"held": [{"who": names[k], "minutes": int(v // 60)} for k, v in held.items()], "lateMinutes": int(late // 60)}


def battery_runs(recs=None):
    """The open run (its brief, its parts, what was made in it, where its minutes went) and the earlier ones."""
    d = os.path.join(BRAIN, battery_runs_rel().replace("/", os.sep))
    rows = []
    try:
        names = sorted(x for x in os.listdir(d) if x.endswith(".md") and x != "readme.md")
    except OSError:
        names = []
    for x in names:
        try:
            with open(os.path.join(d, x), "r", encoding="utf-8-sig") as f:
                fm = _battery_run_front(f.read(64 * 1024))
        except OSError:
            continue
        if fm.get("id"):
            rows.append(dict(fm, path=battery_runs_rel() + "/" + x))
    rows.sort(key=lambda r: r.get("opened") or "")
    reg = battery_register()
    for r in rows:
        r["made"] = sum(1 for m in reg if m.get("run") == r["id"])
    cur = next((r for r in reversed(rows) if not r.get("closed")), None)
    if cur:
        recs = recs if recs is not None else battery_sync()
        start = _battery_time(cur.get("opened")) or dt.datetime.now()
        cur = dict(cur, minutes=_battery_minutes(recs, start, None),
                   madeRows=[{"id": m["id"], "title": m.get("title"), "maker": m.get("maker")} for m in reg if m.get("run") == cur["id"]][:12])
    earlier = [r for r in reversed(rows) if r.get("closed")][:8]
    return {"current": cur, "earlier": earlier}


# ---- what got done, for the owner (0.120.0): the battery's inbox on Today and at the top of the Battery page ----
# The owner's ask, 11/12: one place that shows what got done, in plain words, with every part of a piece one press away
# and the rare thing that waits on them apart. Built on the register: each row is one finished piece, with who made it,
# whether the other checked it, and its parts (the file, the notes on its request, its run's write-up, its release note).

def _battery_reader(rel):
    import urllib.parse
    return "/reader?path=" + urllib.parse.quote(rel, safe="/")


def battery_done(limit=20):
    """What got done, newest first, each piece with its parts as addresses, and what waits on the owner."""
    if not battery_root():
        return {"enabled": False}
    owner, partner, pname = battery_owner(), battery_partner(), battery_partner_name()
    names = {"claude": "Claude", partner: pname, owner: "you"}
    other = {"claude": pname, partner: "Claude"}
    runs = {}
    d = os.path.join(BRAIN, battery_runs_rel().replace("/", os.sep))
    try:
        for x in os.listdir(d):
            if x.endswith(".md") and x != "readme.md":
                with open(os.path.join(d, x), "r", encoding="utf-8-sig") as f:
                    fm = _battery_run_front(f.read(8192))
                if fm.get("id"):
                    runs[fm["id"]] = {"title": fm.get("title") or fm["id"], "path": battery_runs_rel() + "/" + x}
    except OSError:
        pass
    rows = []
    for r in battery_register()[:limit]:
        parts = []
        if r.get("path") and r.get("exists"):
            parts.append({"label": "open it", "href": _battery_reader(r["path"])})
        if r.get("request"):
            parts.append({"label": "its notes", "href": "/battery?request=" + r["request"]})
        if r.get("run") and r["run"] in runs:
            parts.append({"label": "the run", "href": _battery_reader(runs[r["run"]]["path"])})
        if r.get("kind") == "release":
            parts.append({"label": "the release note", "href": _battery_reader(VIEWER_WHATS_NEW_REL)})
        checked = other.get(r.get("maker")) if r.get("review") == "passed" else ""
        rows.append({"id": r.get("id"), "at": r.get("at"), "title": r.get("title"), "line": r.get("line"), "kind": r.get("kind"),
                     "version": r.get("version") or "", "by": names.get(r.get("maker"), r.get("maker") or ""),
                     "checkedBy": checked or "", "changes": r.get("review") == "changes", "tested": r.get("tested") or "",
                     "evidence": r.get("evidence") or "", "parts": parts})
    t = battery_turn_data()
    waits = [{"id": o["id"], "re": o["re"], "question": o.get("question") or "", "age": o["age"],
              "href": "/battery?request=" + o["id"]} for o in t.get("open") or [] if o.get("holder") == owner]
    return {"enabled": True, "rows": rows, "waits": waits, "turn": t.get("line", ""), "late": bool(t.get("late")),
            "partnerName": pname, "count": len(battery_register())}


def battery_done_api(q):
    """GET /api/battery/done?limit=N: what got done, newest first, with each piece's parts and what waits on the owner."""
    try:
        limit = max(1, min(100, int(q.get("limit", ["20"])[0])))
    except ValueError:
        limit = 20
    return 200, battery_done(limit)
