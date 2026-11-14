"""part_drop.py -- a file dropped on any page, kept with what that page is about (viewer 0.103.0, brain-viewer T-0403).

Loaded into serve.py's namespace by load_part(), like the other part files. The contract (the folder, the sidecar, the
batch line, and what the session does with each kind of file) is written for people and sessions in
`file-drop-contract.md` beside this file; that file is the one place the session's rules live.

The owner, 11/03, in the notepad on Today, after an application export reached the session only because he dragged its
path into chat: a file dragged onto a page should land with what the page is about ("Okay this document is important to
this conversation"), and something should work out what it is for and put it through the system. So the viewer does the
first half and only that: it SAVES the file and LABELS it. Working out what it is happens in the main session, when the
batch it rides in lands.

  POST /api/upload {route, note?, files: [{name, data}]}   each file into inbox/uploads/<yyyy-mm-dd-hhmm>-<name>, with a
                                                           sidecar <leaf>.json holding the page's context and the note;
                                                           one CREATED log line per file (the log is the outbox, so the
                                                           file joins the next answers batch the way a notepad note does)
  GET  /api/upload/context?route=                          what a drop on that page is kept with, before anything is sent
  POST /api/upload/takeback {path}                         a dropped file taken back before it was sent: file and sidecar gone

Whether a drop waits for Send or goes at once is the `drop_hold` setting (the Settings page). Waiting, it is one more
press: the quiet timer starts over and it goes with the next batch. At once, it goes in a batch of its own that holds the
dropped files only, so answers that are being held stay held.
"""

DROP_REL = "inbox/uploads"
DROP_MAX = 25 * 1024 * 1024           # one file; an application export is a few KB, a PDF a few MB
DROP_FILES_MAX = 12                   # files in one drop
DROP_NOTE_MAX = 600
_DROP_LEAF_BAD = re.compile(r"[^A-Za-z0-9._-]+")
# what the log line is, so answers_read() can carry it in the batch (serve.py, beside the notepad's own line)
_UPLOAD_LINE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] \[brain-viewer\] CREATED -- (" + re.escape(DROP_REL)
                          + r"/\S+) -- (file dropped on a page in the viewer.*)$")
# a page's name by its menu label, for a page that is about nothing more than itself
DROP_PAGE_WORDS = {"/": "Today", "/today": "Today", "/call": "the call page", "/from-claude": "From Claude",
                   "/threads": "Threads", "/thread": "Threads", "/artifacts": "Artifacts", "/projects": "Projects",
                   "/people": "People", "/chat": "Chat", "/reader": "the Reader", "/files": "Files", "/forge": "the Forge",
                   "/maps": "the Forge", "/mentee": "Programme content", "/studio": "the Studio", "/preview": "Preview",
                   "/home": "System", "/usage": "Usage", "/share": "Sharing", "/settings": "Settings", "/manual": "the Manual"}


def drop_hold_setting():
    """True when a dropped file waits for the next send (the default), False when it goes at once. With answers not held
    at all there is no Send press to wait for, so a drop goes at once whatever this says."""
    d = load_settings(os.path.join(BRAIN, SETTINGS_REL.replace("/", os.sep)))
    v = d.get("drop_hold")
    return (True if v is None else bool(v)) and answers_hold_setting()["on"]


def send_note_box_setting():
    """True when the Send press opens a note box on every press; False (the default) when it sends at once and a
    right-click (or a long press on a phone) opens the box."""
    d = load_settings(os.path.join(BRAIN, SETTINGS_REL.replace("/", os.sep)))
    return bool(d.get("send_note_box"))


def _drop_day(iso):
    """2026-11-03 -> 'Tuesday 11/03'."""
    try:
        d = dt.date.fromisoformat(str(iso or "")[:10])
    except ValueError:
        return ""
    return "%s %d/%02d" % (d.strftime("%A"), d.month, d.day)


def _drop_names(names):
    names = [n for n in names if n]
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def drop_person_name(slug):
    """A people card's name (its `name:` line, else its first heading), else the slug made readable."""
    ap = os.path.join(BRAIN, PEOPLE_REL, "%s.md" % slug)
    fm = frontmatter(ap) if os.path.isfile(ap) else None
    if fm and fm.get("name"):
        return fm["name"]
    if os.path.isfile(ap):
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                for line in f:
                    if line.startswith("# "):
                        return line[2:].split("—")[0].split(",")[0].strip()
        except OSError:
            pass
    return slug.replace("-", " ").title()


def _drop_item(ref):
    """'<holon id>/<id>' or '<holon id> <id>' -> {project, id, text, ledger} for an item that is on its ledger, else None."""
    m = re.match(r"^\s*([A-Za-z0-9_.-]+)[/ ]+([TQ]-\d{4})\s*$", str(ref or ""))
    if not m:
        return None
    hid, iid = m.groups()
    hit = next((h for h in registry().get("holons", []) if h.get("tasks") and hid in (h.get("id"), h.get("tasks"))), None)
    if not hit:
        return None
    rel = norm(hit["tasks"])
    try:
        it = ledger.find(ledger.parse(ledger.read(os.path.join(BRAIN, rel.replace("/", os.sep)))), iid)
    except Exception:                                              # noqa: BLE001
        return None
    return {"project": hit["id"], "id": iid, "ledger": rel, "text": _first_sentence(it.get("text") or "", 90)}


def drop_context(route):
    """What a drop on this page is kept with: {route, kind, label, ref, ...}. `label` is the page's subject in words, for
    the face and the batch; `ref` is what the session acts on (a prep, a subject file, '<holon> <id>', a card, a file).
    Read from the page's own address, server side, so the context is the brain's, never what a page claims."""
    raw = str(route or "/").strip() or "/"
    u = urllib.parse.urlparse(raw if raw.startswith("/") else "/" + raw)
    path = (u.path.rstrip("/") or "/")
    q = urllib.parse.parse_qs(u.query)
    g = lambda k: (q.get(k) or [""])[0].strip()
    ctx = {"route": path + (("?" + u.query) if u.query else ""), "kind": "page",
           "label": DROP_PAGE_WORDS.get(path, path.strip("/") or "Today"), "ref": ""}
    if path in ("/", "/today") and not g("item"):
        ctx.update(kind="today", label="Today")
        return ctx
    if path == "/call":
        prep, start, date = g("prep"), g("start"), g("date")
        ev = None
        if start:
            ev = call_event_for(date=date or None, start=start)
            if ev and not prep:
                prep = ((ev.get("preps") or [{}])[0] or {}).get("path") or ""
        ap = prep_rel_ok(prep) if prep else None
        fm = (frontmatter(ap) or {}) if ap else {}
        if ap and ev is None:
            ev = call_event_for(prep_rel=prep, date=fm.get("call"))
        people = []
        if ev:
            people = [{"name": w.get("cardName") or w.get("name") or "", "slug": w.get("slug") or "",
                       "card": ("%s/%s.md" % (PEOPLE_REL, w["slug"])) if w.get("slug") else ""}
                      for w in ev.get("people") or [] if not w.get("self")]
            for w in people:
                if w["slug"]:
                    w["name"] = drop_person_name(w["slug"])
        elif fm:
            parts = [p.strip() for p in re.sub(r"^\[|\]$", "", fm.get("participants", "") or fm.get("person", "")).split(",") if p.strip()]
            people = [{"name": drop_person_name(s), "slug": s, "card": "%s/%s.md" % (PEOPLE_REL, s)} for s in parts]
        day = str(fm.get("call") or (ev or {}).get("date") or str((ev or {}).get("start") or "")[:10])[:10]
        who = _drop_names([w["name"] for w in people])
        label = "the call with %s" % who if who else ("the call %s" % ((ev or {}).get("title") or "")).strip()
        if day:
            label += " on %s" % _drop_day(day)
        ctx.update(kind="call", label=label, ref=prep if ap else "", prep=prep if ap else "", date=day,
                   meeting=(ev or {}).get("title") or "", people=people)
        return ctx
    if path in ("/thread", "/threads") and (g("subject") or g("item")):
        sub = subject_by_ref(g("subject"), subject_index()) if g("subject") else None
        it = _drop_item(g("item")) if g("item") else None
        if it:
            ctx.update(kind="item", label="the item “%s”" % it["text"], ref="%s %s" % (it["project"], it["id"]), item=it)
            if sub:
                ctx.update(subject=sub["rel"], thread=sub["short"])
                ctx["label"] += " on the thread %s" % sub["short"]
            return ctx
        if sub:
            ctx.update(kind="thread", label="the thread %s" % sub["short"], ref=sub["rel"], subject=sub["rel"], thread=sub["short"])
        return ctx
    if path in ("/", "/today") and g("item"):
        it = _drop_item(g("item"))
        if it:
            ctx.update(kind="item", label="the item “%s”" % it["text"], ref="%s %s" % (it["project"], it["id"]), item=it)
        else:
            ctx.update(kind="today", label="Today")
        return ctx
    if path == "/projects" and g("holon"):
        hit = next((h for h in registry().get("holons", []) if h.get("id") == g("holon")), None)
        if hit:
            ctx.update(kind="project", label="the project %s" % (hit.get("short") or hit.get("name") or hit["id"]),
                       ref=hit["id"], project=hit["id"])
        return ctx
    if path == "/people" and g("open"):
        slug = re.sub(r"[^a-z0-9-]", "", g("open").lower())
        if slug and os.path.isfile(os.path.join(BRAIN, PEOPLE_REL, slug + ".md")):
            nm = drop_person_name(slug)
            ctx.update(kind="person", label="%s's card" % nm, ref="%s/%s.md" % (PEOPLE_REL, slug),
                       people=[{"name": nm, "slug": slug, "card": "%s/%s.md" % (PEOPLE_REL, slug)}])
        return ctx
    if path in ("/reader", "/forge") and g("path"):
        rel = norm(g("path"))
        if rel and os.path.isfile(os.path.join(BRAIN, rel.replace("/", os.sep))):
            ctx.update(kind="file" if path == "/reader" else "drawing",
                       label=("the file %s" if path == "/reader" else "the drawing %s") % doc_name(rel), ref=rel, file=rel)
        return ctx
    return ctx


def _drop_leaf(name, now):
    """A dated leaf in inbox/uploads/ that keeps the file's own name readable (application_182.txt stays itself)."""
    leaf = os.path.basename(str(name or "").replace("\\", "/")).strip() or "file"
    stem, ext = os.path.splitext(leaf)
    stem = _DROP_LEAF_BAD.sub("-", stem).strip("-.")[:80] or "file"
    ext = _DROP_LEAF_BAD.sub("", ext)[:12].lower()
    base = "%s-%s" % (now.strftime("%Y-%m-%d-%H%M"), stem)
    folder = os.path.join(BRAIN, DROP_REL.replace("/", os.sep))
    out, n = base + ext, 2
    while os.path.exists(os.path.join(folder, out)) or os.path.exists(os.path.join(folder, out + ".json")):
        out, n = "%s-%d%s" % (base, n, ext), n + 1
    return out


def _drop_sidecar_path(rel):
    return os.path.join(BRAIN, (rel + ".json").replace("/", os.sep))


def drop_sidecar(rel):
    """The sidecar of a dropped file, or None when the file was taken back or the session has taken it in."""
    rel = norm(rel or "")
    if not rel or not rel.startswith(DROP_REL + "/") or rel.endswith(".json"):
        return None
    if not os.path.isfile(os.path.join(BRAIN, rel.replace("/", os.sep))):
        return None
    return _json_read(_drop_sidecar_path(rel))


def drop_save(data):
    """POST /api/upload -> (code, body). Every file is checked before any is written, so a refused drop writes nothing."""
    if PROPOSE:
        return 403, {"error": "a team copy sends nothing to a session, so a dropped file has nowhere to go"}
    if not isinstance(data, dict):
        return 400, {"error": "send {route, note, files: [{name, data}]}"}
    files = data.get("files")
    if files is None and data.get("data") is not None:
        files = [{"name": data.get("name"), "data": data.get("data")}]
    if not isinstance(files, list) or not files:
        return 400, {"error": "no file came with the drop"}
    if len(files) > DROP_FILES_MAX:
        return 400, {"error": "%d files at once is more than this takes (%d); drop them in smaller groups" % (len(files), DROP_FILES_MAX)}
    note = " ".join(str(data.get("note") or "").split())[:DROP_NOTE_MAX]
    ctx = drop_context(data.get("route"))
    blobs = []
    for f in files:
        f = f if isinstance(f, dict) else {}
        name = os.path.basename(str(f.get("name") or "").replace("\\", "/")).strip() or "file"
        raw = str(f.get("data") or "")
        if raw.startswith("data:"):
            raw = raw.split(",", 1)[-1]
        try:
            blob = base64.b64decode(raw, validate=True)
        except Exception:                                          # noqa: BLE001
            return 400, {"error": "%s did not arrive whole; drop it again" % name}
        if not blob:
            return 400, {"error": "%s is empty" % name}
        if len(blob) > DROP_MAX:
            return 413, {"error": "%s is %.1f MB; one file here can be up to %d MB" % (name, len(blob) / 1048576.0, DROP_MAX // 1048576)}
        blobs.append((name, blob))
    now = dt.datetime.now()
    folder = os.path.join(BRAIN, DROP_REL.replace("/", os.sep))
    os.makedirs(folder, exist_ok=True)
    saved = []
    for name, blob in blobs:
        leaf = _drop_leaf(name, now)
        rel = DROP_REL + "/" + leaf
        with open(os.path.join(folder, leaf), "wb") as fh:
            fh.write(blob)
        side = {"file": rel, "name": name, "bytes": len(blob), "droppedAt": now.isoformat(timespec="seconds"),
                "note": note, "page": ctx, "batch": None}
        _json_write(_drop_sidecar_path(rel), side)
        log_line("%s -- file dropped on a page in the viewer: %s, kept with %s (%d bytes)"
                 % (rel, name.replace("\n", " ")[:120], ctx["label"][:160], len(blob)), action="CREATED")
        saved.append({"path": rel, "name": name, "bytes": len(blob)})
    waits = drop_hold_setting()
    sent = None
    if waits:
        answers_hold_arm()               # a drop is a press: the quiet minutes start over, and it goes with the next batch
    else:
        sent = drop_send_now([s["path"] for s in saved])
    return 200, {"ok": True, "files": saved, "context": ctx, "note": note, "waits": waits, "batch": sent}


def drop_batch_row(rel, when, n):
    """A dropped file as answers_read() carries it, or None when there is nothing to send: taken back, already sent in a
    batch of its own, or already taken in by the session."""
    side = drop_sidecar(rel)
    if not side or side.get("batch"):
        return None
    page = side.get("page") or {}
    return {"project": "upload", "id": "", "kind": "upload", "when": when, "action": "upload",
            "text": side.get("name") or rel.rsplit("/", 1)[-1], "note": side.get("note") or "",
            "page": page.get("label") or "", "ref": page.get("ref") or "", "ledger": rel, "presses": 1, "_n": n}


def drop_batch_line(r, when):
    """`- upload · HH:MM · on <the page's subject> (<what it points at>) · <file name> · note: "<his note>" · <path>`"""
    on = r.get("page") or "a page"
    if r.get("ref"):
        on += " (%s)" % r["ref"]
    tail = (' · note: "%s"' % r["note"].replace('"', "'")) if r.get("note") else ""
    return "- upload · %s · on %s · %s%s · %s" % (when, on, r["text"], tail, r["ledger"])


def drop_mark_sent(rels, stamp):
    """Each sidecar records the batch it went in, so the face can say when it went and nothing goes twice."""
    for rel in rels:
        ap = _drop_sidecar_path(rel)
        side = _json_read(ap)
        if side is not None and not side.get("batch"):
            side["batch"] = stamp
            _json_write(ap, side)


def drop_send_now(rels):
    """A drop that goes at once: one batch holding these files only (answers being held stay held). -> the batch stamp."""
    now = dt.datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M")
    rows = [r for r in (drop_batch_row(rel, stamp, i) for i, rel in enumerate(rels)) if r]
    if not rows:
        return None
    lines = ["## Batch %s (%d file%s)" % (stamp, len(rows), "" if len(rows) == 1 else "s")] \
        + [drop_batch_line(r, stamp[11:]) for r in rows]
    with _answers_lock:
        _inbox_append(lines)
        drop_mark_sent([r["ledger"] for r in rows], stamp)
    log_line("%s -- %d file%s dropped on a page sent to the main session as one batch (%s), at once (the drop setting)"
             % (ANSWERS_INBOX_REL, len(rows), "" if len(rows) == 1 else "s", stamp))
    return stamp


def drop_takeback(data):
    """POST /api/upload/takeback {path}: a dropped file that has not gone yet is removed with its sidecar, and logged.
    Once sent it stays: the session has been told of it."""
    rel = norm(str((data or {}).get("path") or ""))
    side = drop_sidecar(rel) if rel else None
    if not side:
        return 404, {"error": "no dropped file waits at %s" % (rel or "that path")}
    if side.get("batch"):
        return 409, {"error": "it went to the main agent at %s, so it stays; say in a note what to do with it instead" % side["batch"][11:]}
    os.remove(os.path.join(BRAIN, rel.replace("/", os.sep)))
    try:
        os.remove(_drop_sidecar_path(rel))
    except OSError:
        pass
    log_line("%s -- a dropped file taken back before it was sent (%s)" % (rel, side.get("name") or ""), action="DELETED")
    return 200, {"ok": True, "path": rel}
