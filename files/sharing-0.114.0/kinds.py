#!/usr/bin/env python3
"""skills/sharing/kinds.py -- round three: everything else that can be shared (files, threads, drawings, card sections,
messages). Bound to the engine (skills/sharing/engine.py), which re-exports the names below as its own; the viewer calls
them there:

    share_file(brain, space, rel)                      -> (ok, line)
    share_thread(brain, space, rel)                    -> (ok, line)   its open items that link it are shared with it
    share_drawing(brain, space, rel)                   -> (ok, line)   a .canvas and its .forge.json twin
    share_card_section(brain, space, card_rel, heading)-> (ok, line)
    take_back_thing(brain, space, kind, key)           -> (ok, line)   key: the path, or card_rel#heading
    proposals(brain)                                   -> [{id, space, from, person, heading, text, at}]
    take_section(brain, proposal_id) / leave_section(brain, proposal_id) -> (ok, line)
    send_message(brain, space, text)                   -> (ok, line)
    messages(brain, space, limit=50)                   -> [{id, from_user, from, at, text}]
    mark_read(brain, space)                            -> (ok, line)
    set_auto_take(brain, space, on)                    -> (ok, line)
    space_view(brain, space)                           -> everything the space's page draws, no network call

The sync uses the same patterns as tasks: rows in sent.json, a change the gate refuses held (the earlier version stays
shared), state rebuildable from the files and sent.json. Standard library only. Spec: skills/sharing/readme.md.
"""
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile

E = None          # the engine, bound by engine.py: E.<name> reads the engine's own names at call time

TEXT_KINDS = ("file", "thread", "drawing")
SENT_KEY = {"file": "files", "thread": "threads", "drawing": "drawings", "card-section": "sections"}
PLACE = {"file": "files", "thread": "threads", "drawing": "drawings"}
THREAD_DROP = ("people", "match", "canonical", "depends", "progress")


# ---------------------------------------------------------------- small helpers

def _p(brain, rel):
    return os.path.join(brain, *str(rel).split("/"))


def _read(brain, rel):
    """A text file, or None when it is not there or is not text."""
    try:
        with open(_p(brain, rel), "rb") as f:
            raw = f.read()
        return raw.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def _write(brain, rel, text):
    E.share._write_text(_p(brain, rel), text)


def _hash(text):
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


def _safe_name(name, fallback="file"):
    """A file name from outside: letters, digits, spaces, dots, hyphens and underscores, at most 80 characters."""
    n = re.sub(r"[^\w .-]", "", E.clean_name(name, "")).strip(" .")
    return n[:80] or fallback


def _key(kind, path, heading=None):
    return "%s:%s#%s" % (kind, path, heading) if kind == "card-section" else "%s:%s" % (kind, path)


def _sent_rows(brain, st):
    d = E.share._read_json(_p(brain, st["sent"]))
    d = d if isinstance(d, dict) else {}
    out = {k: [x for x in d.get(k) or [] if isinstance(x, dict)] for k in ("items", "threads", "files", "drawings", "sections")}
    return d, out


def _save_rows(brain, st, d, rows):
    d = dict(d or {})
    for k, v in rows.items():
        d[k] = v
    E.share._write_json(_p(brain, st["sent"]), d)


def _stamp_or(brain, space):
    st = E._find_stamp(brain, space)
    if not st or st.get("state") == "detached":
        return None, "You do not share with anyone named %s." % E.clean_name(space)
    return st, ""


def _ready(brain, space):
    """(ctx, stamp, "") or (None, None, the line that says why not)."""
    brain = E.share.brain_root(brain)
    try:
        ctx = E._ctx(brain)
    except E.Refused as e:
        return None, None, str(e)
    st, why = _stamp_or(brain, space)
    if not st:
        return None, None, why
    try:
        here, why = E._host_ok(brain, st, ctx)
    except E.service.ServiceError:
        return None, None, E.OFFLINE
    if not here:
        return None, None, why
    return ctx, st, ""


# ---------------------------------------------------------------- what a thing is, per kind

def split_frontmatter(text):
    """(frontmatter lines or None, body)."""
    t = str(text or "").replace("\r\n", "\n")
    if not t.startswith("---\n"):
        return None, t
    end = t.find("\n---", 4)
    if end == -1:
        return None, t
    return t[4:end].split("\n"), t[end + 4:].lstrip("\n")


def _drop_keys(lines, drop):
    """Frontmatter lines without the keys named (a list under a key goes with it)."""
    out, skipping = [], False
    for line in lines:
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:", line)
        if m:
            skipping = m.group(1).lower() in drop
            if skipping:
                continue
        elif skipping and (line.startswith(" ") or line.startswith("\t") or line.startswith("-")):
            continue
        else:
            skipping = False
        out.append(line)
    return out


def _with_frontmatter(lines, body):
    return ("---\n" + "\n".join(lines) + "\n---\n\n" + body) if lines is not None else body


def _title_of(text, fallback):
    fm, body = split_frontmatter(text)
    for line in fm or []:
        m = re.match(r"^title\s*:\s*(.+)$", line)
        if m:
            return m.group(1).strip().strip("\"'")
    for line in body.split("\n"):
        m = re.match(r"^#\s+(.+)$", line)
        if m:
            return m.group(1).strip()
    return fallback


def card_section(text, heading):
    """(level, the fold's text without its heading) for the ## or ### heading named, or (None, None)."""
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    want = " ".join(str(heading or "").split()).lower()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{2,3})\s+(.*?)\s*$", line)
        if m and " ".join(m.group(2).split()).lower() == want:
            level, body = len(m.group(1)), []
            for nxt in lines[i + 1:]:
                h = re.match(r"^(#{1,6})\s", nxt)
                if h and len(h.group(1)) <= level:
                    break
                body.append(nxt)
            return level, "\n".join(body).strip("\n")
    return None, None


def render(brain, kind, row, holds):
    """(body, why) for one row of sent.json, through the gate."""
    gate = E.gate
    if kind == "file":
        rel = row["path"]
        text = _read(brain, rel)
        clean, why = gate.render_text(brain, rel, text, holds)
        if clean is None:
            return None, why
        base = rel.rsplit("/", 1)[-1]
        name, ext = os.path.splitext(base)
        return {"kind": "file", "title": base, "name": name, "ext": ext.lower(), "text": clean}, ""
    if kind == "thread":
        rel = row["path"]
        text = _read(brain, rel)
        if text is None:
            return None, "only text files can be shared so far"
        fm, body = split_frontmatter(text)
        stripped = _with_frontmatter(_drop_keys(fm, THREAD_DROP) if fm is not None else None, body)
        clean, why = gate.render_text(brain, rel, stripped, holds)
        if clean is None:
            return None, why
        slug = os.path.splitext(rel.rsplit("/", 1)[-1])[0]
        return {"kind": "thread", "title": gate.clean_words(brain, _title_of(text, slug)), "slug": slug, "text": clean}, ""
    if kind == "drawing":
        rel = row["path"]
        canvas = _read(brain, rel)
        if canvas is None:
            return None, "only text files can be shared so far"
        twin = rel[: -len(".canvas")] + ".forge.json" if rel.endswith(".canvas") else None
        forge = _read(brain, twin) if twin else None
        got, why = gate.render_drawing(brain, rel, canvas, forge)
        if got is None:
            return None, why
        name = os.path.splitext(rel.rsplit("/", 1)[-1])[0]
        return {"kind": "drawing", "title": name, "name": name, "canvas": got["canvas"], "forge": got["forge"]}, ""
    if kind == "card-section":
        text = _read(brain, row["card"])
        if text is None:
            return None, "the card cannot be read"
        _lvl, sec = card_section(text, row["heading"])
        if sec is None:
            return None, "that section is no longer on the card"
        clean, why = gate.render_section(brain, row["card"], row["heading"], sec)
        if clean is None:
            return None, why
        m = re.match(r"^#\s+(.+)$", text.lstrip("﻿").split("\n", 1)[0])
        person = E.clean_name(m.group(1) if m else row["card"].rsplit("/", 1)[-1][:-3])
        return {"kind": "card-section", "person": person, "heading": gate.clean_words(brain, row["heading"]), "text": clean}, ""
    return None, "that cannot be shared"


def _norm(kind, raw):
    """A body from the service, defensively."""
    b = raw if isinstance(raw, dict) else {}
    s = lambda k, cap=TEXTCAP: str(b.get(k))[:cap] if isinstance(b.get(k), str) else ""
    if kind == "file":
        ext = s("ext", 8).lower()
        return {"title": E.clean_name(s("title"), "a file"), "name": _safe_name(s("name")), "ext": ext if ext in E.gate.TEXT_EXTS else "",
                "text": s("text")}
    if kind == "thread":
        return {"title": E.clean_name(s("title"), "a thread"), "slug": E._slug(s("slug")) or "thread", "text": s("text")}
    if kind == "drawing":
        return {"title": E.clean_name(s("title"), "a drawing"), "name": _safe_name(s("name"), "drawing"), "canvas": s("canvas"),
                "forge": s("forge") or None}
    if kind == "card-section":
        return {"person": E.clean_name(s("person"), "Someone"), "heading": E.clean_name(s("heading"), "Notes"), "text": s("text")}
    if kind == "message":
        return {"text": s("text", 4000), "at": s("at", 40)}
    return {}


TEXTCAP = 400 * 1024


# ---------------------------------------------------------------- sharing and taking back

def _share(brain, space, kind, row_new, same):
    ctx, st, why = _ready(brain, space)
    if not ctx:
        return False, why
    if ctx.get("out"):                                         # an employer's computer: sharing out waits for the yes
        return False, ctx["out"]
    brain = ctx["brain"]
    body, why = render(brain, kind, row_new, E._holds(st, ctx))
    if not body:
        return False, "Not shared with %s: %s." % (st["label"], why)
    d, rows = _sent_rows(brain, st)
    lst = rows[SENT_KEY[kind]]
    if not any(same(x) for x in lst):
        lst.append(dict(row_new, at=_now(), thing=None))
    extra = []
    if kind == "thread":                                   # its open items that link it go with it
        for proj, rel_l, it in _items_linking(ctx, row_new["path"]):
            raw = _raw_line(brain, rel_l, it)
            b2, _w = E.gate.render_task(brain, rel_l, it, raw, E._holds(st, ctx))
            if b2 and not any(x.get("project") == proj and x.get("id") == it["id"] for x in rows["items"]):
                rows["items"].append({"project": proj, "ledger": rel_l, "id": it["id"], "at": _now(), "thing": None,
                                      "thread": row_new["path"]})
                extra.append(it["id"])
    _save_rows(brain, st, d, rows)
    E.share._log(brain, "MODIFIED", "%s -- a %s shared" % (st["sent"], kind.replace("-", " ")))
    res = E.sync(brain, on_purpose=True, only=st["name"])
    title = body.get("title") or body.get("heading") or "it"
    tail = "" if res.get("ok") else " (%s)" % res.get("line")
    more = (" with %s on it" % E._count_words(len(extra), "open item")) if extra else ""
    return True, "Shared with %s: “%s”%s is in the space once %s checks for what was shared%s." % (
        st["label"], title, more, st["label"], tail)


def share_file(brain, space, rel):
    rel = E.gate._norm(rel)
    return _share(brain, space, "file", {"path": rel}, lambda x: x.get("path") == rel)


def share_thread(brain, space, rel):
    rel = E.gate._norm(rel)
    return _share(brain, space, "thread", {"path": rel}, lambda x: x.get("path") == rel)


def share_drawing(brain, space, rel):
    rel = E.gate._norm(rel)
    return _share(brain, space, "drawing", {"path": rel}, lambda x: x.get("path") == rel)


def share_card_section(brain, space, card_rel, heading):
    card_rel = E.gate._norm(card_rel)
    return _share(brain, space, "card-section", {"card": card_rel, "heading": heading},
                  lambda x: x.get("card") == card_rel and x.get("heading") == heading)


def take_back_thing(brain, space, kind, key):
    """Take back a file, thread, drawing (key: its path) or card section (key: card_rel#heading)."""
    if kind not in SENT_KEY:
        return False, "That cannot be taken back here."
    ctx, st, why = _ready(brain, space)
    if not ctx:
        return False, why
    brain = ctx["brain"]
    d, rows = _sent_rows(brain, st)
    if kind == "card-section":
        card, _h, heading = str(key).partition("#")
        same = lambda x: x.get("card") == E.gate._norm(card) and x.get("heading") == heading
        skey = _key(kind, E.gate._norm(card), heading)
    else:
        same = lambda x: x.get("path") == E.gate._norm(key)
        skey = _key(kind, E.gate._norm(key))
    lst = rows[SENT_KEY[kind]]
    row = next((x for x in lst if same(x)), None)
    if not row:
        return False, "That is not shared with %s." % st["label"]
    with E._SpaceLock(brain, st["name"]) as ok:
        if not ok:
            return False, "What you share with %s is being checked right now; try again in a moment." % st["label"]
        state = E._load_state(brain, st["name"])
        e = state["out"].get(skey)
        try:
            if e and e.get("thing"):
                E._put_own(ctx, st, state, skey, {"kind": kind, "removed": True}, removed=True)
            state["out"].pop(skey, None)
        except E.service.ServiceError:
            return False, E.OFFLINE
        finally:
            E._save_state(brain, st["name"], state)
        rows[SENT_KEY[kind]] = [x for x in lst if x is not row]
        if kind == "thread":                               # its items go with it
            rows["items"] = [x for x in rows["items"] if x.get("thread") != row.get("path")]
        _save_rows(brain, st, d, rows)
    E.share._log(brain, "MODIFIED", "%s -- a %s taken back" % (st["sent"], kind.replace("-", " ")))
    E.sync(brain, on_purpose=True, only=st["name"])
    return True, "Taken back: it leaves %s's side once %s checks for what was shared." % (st["label"], st["label"])


def _items_linking(ctx, rel):
    """[(project, ledger rel, item)] for every open task and question that links the subject file."""
    out = []
    t = ctx["tasks"]
    for h in E.gate.registry_rows(ctx["brain"]):
        if not h.get("tasks"):
            continue
        lrel = E.gate._norm(h["tasks"])
        for it in E._items(ctx, lrel):
            if it["mark"] not in " -?":
                continue
            links = [str(l) for l in it.get("links") or []]
            if any(l == rel or l.endswith("/" + rel) or l.strip("[]") in (rel, rel[:-3]) or rel in l for l in links):
                out.append((h["id"], lrel, it))
    return out


def _raw_line(brain, rel, it):
    try:
        return _read(brain, rel).replace("\r\n", "\n").split("\n")[it["line"] - 1]
    except (AttributeError, IndexError):
        return ""


# ---------------------------------------------------------------- the sync: the home side

def send_texts(ctx, st, state, report, active):
    """Each shared file, thread, drawing and section: re-rendered, sent when it changed, held when it stops passing."""
    brain = ctx["brain"]
    d, rows = _sent_rows(brain, st)
    holds = E._holds(st, ctx)
    changed = False
    for kind in ("thread", "file", "drawing", "card-section"):
        keep = []
        for row in rows[SENT_KEY[kind]]:
            key = _key(kind, row.get("card") or row.get("path"), row.get("heading")) if kind == "card-section" else _key(kind, row.get("path"))
            gone = (_read(brain, row.get("card") or row.get("path")) is None) and not os.path.exists(_p(brain, row.get("card") or row.get("path") or "x"))
            if gone:                                       # gone from the brain: that, or the press, takes it back
                e = state["out"].get(key)
                if active and e and e.get("thing"):
                    E._put_own(ctx, st, state, key, {"kind": kind, "removed": True}, removed=True)
                state["out"].pop(key, None)
                report["problems"].append("Taken back from %s because it is no longer in this brain." % st["label"])
                changed = True
                ctx["save"]()
                continue
            keep.append(row)
            body, why = render(brain, kind, row, holds)
            e = state["out"].setdefault(key, {})
            if not body:
                seen = _hash(why + (_read(brain, row.get("card") or row.get("path")) or ""))
                if e.get("held_at") != seen:
                    report["problems"].append("Your change to “%s” stays here: %s. %s still sees the earlier version."
                                              % (row.get("heading") or (row.get("path") or "").rsplit("/", 1)[-1], why, st["label"]))
                e["held"], e["held_at"] = why, seen
                ctx["save"]()
                continue
            e.pop("held", None)
            e.pop("held_at", None)
            if not active:
                continue
            if e.get("body") != body or not e.get("thing"):
                salt = E._salt(brain, st)
                E._put_own(ctx, st, state, key, body, thing_key=E._thing_key(salt, kind, row.get("card") or row.get("path"))
                           if kind != "card-section" else E._thing_key(salt, row["card"], row["heading"]))
                ctx["save"]()
                report["sent"] += 1
                if row.get("thing") != state["out"][key]["thing"]:
                    row["thing"] = state["out"][key]["thing"]
                    changed = True
        rows[SENT_KEY[kind]] = keep
    if changed:
        _save_rows(brain, st, d, rows)
    ctx["thread_things"] = {row["path"]: (state["out"].get(_key("thread", row["path"])) or {}).get("thing")
                            for row in rows["threads"]}


def thread_of(ctx, st, row):
    """The thread thing id a task row rides with, or None."""
    return (ctx.get("thread_things") or {}).get(row.get("thread")) if row.get("thread") else None


def rebuild(ctx, st, state, heads):
    """The rows of sent.json whose thing the state does not know, mapped back by the thing ids sent.json keeps."""
    brain = ctx["brain"]
    by_id = {h["id"]: h for h in heads if isinstance(h, dict) and h.get("id")}
    _d, rows = _sent_rows(brain, st)
    want = {}
    for kind in ("thread", "file", "drawing", "card-section"):
        for row in rows[SENT_KEY[kind]]:
            key = _key(kind, row.get("card") if kind == "card-section" else row.get("path"), row.get("heading"))
            if (state["out"].get(key) or {}).get("thing"):
                continue
            tid = row.get("thing")
            if tid and tid in by_id and not by_id[tid].get("removed_at"):
                want[tid] = key
    if want:
        for got in E.call(ctx, "get_things", list(want)):
            state["out"][want[got["id"]]] = dict(state["out"].get(want[got["id"]]) or {}, thing=got["id"],
                                                 version=got["version"], body=got.get("body"), key=got.get("key") or "")


# ---------------------------------------------------------------- an edit from the other person, at the home

def _merge3(base, mine, theirs):
    """(merged text, clean). git merge-file when git is here; without it only a side the other did not change merges."""
    if mine == base:
        return theirs, True
    if theirs == base or theirs == mine:
        return mine, True
    git = shutil.which("git")
    if not git:
        return mine, False
    with tempfile.TemporaryDirectory(prefix="sharing-merge-") as tmp:
        paths = []
        for name, text in (("mine", mine), ("base", base), ("theirs", theirs)):
            p = os.path.join(tmp, name)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            paths.append(p)
        r = subprocess.run([git, "merge-file", "-p", paths[0], paths[1], paths[2]], capture_output=True)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", "replace"), True
        return mine, False


def _proposed_name(kind, body, who):
    who = E.clean_name(who, "them")
    if kind == "file":
        return "%s (from %s)%s" % (body.get("name") or "file", who, body.get("ext") or ".txt")
    if kind == "thread":
        return "%s (from %s).md" % (body.get("slug") or "thread", who)
    return "%s (from %s).canvas" % (body.get("name") or "drawing", who)


def apply_edit(ctx, st, state, a, key, e, actor):
    """An `edit` act on a file, thread or drawing this brain shared. Its text is never laid onto the original blindly:
    it is saved under proposed/ and a question is asked of the owner, unless this person's changes are taken without
    asking and the merge is clean. Returns (result, scrub, problem)."""
    brain = ctx["brain"]
    kind = key.split(":", 1)[0]
    rel = key.split(":", 1)[1]
    body = e.get("body") or {}
    p = a.get("payload") if isinstance(a.get("payload"), dict) else {}
    name = actor.get("display") or "Someone"
    title = body.get("title") or rel.rsplit("/", 1)[-1]
    if kind == "drawing":
        canvas, forge = p.get("canvas"), p.get("forge")
        got, why = E.gate.render_drawing(brain, rel, canvas if isinstance(canvas, str) else "", forge if isinstance(forge, str) else None)
        if got is None:
            return E.R_NEVER, True, "%s's change to “%s” was not taken in: %s." % (name, title, why)
        incoming, base = got["canvas"], body.get("canvas") or ""
    else:
        text = p.get("text") if isinstance(p.get("text"), str) else ""
        clean, why = E.gate.render_text(brain, rel, text, None)
        if clean is None:
            return E.R_NEVER, True, "%s's change to “%s” was not taken in: %s." % (name, title, why)
        incoming, base = clean, body.get("text") or ""
        if kind == "thread":                               # the home's own frontmatter stays its own
            incoming = _restore_frontmatter(_read(brain, rel) or "", incoming)
    member = next((m for m in st.get("members") or [] if m.get("user_id") == actor.get("user_id")), {})
    mine = _read(brain, rel) or ""
    if member.get("auto_take"):
        merged, clean_ = _merge3(base if kind != "thread" else mine if base == "" else _restore_frontmatter(mine, base), mine, incoming)
        if clean_:
            _write(brain, rel, merged)
            return E.R_APPLIED, False, ""
    prop = "%s/%s/proposed/%s" % (E.share.SHARED_DIR, st["name"], _proposed_name(kind, body, name))
    _write(brain, prop, incoming)
    t = ctx["tasks"]
    lrel = st.get("list") or E.list_rel(st["name"])
    frm = "@" + (actor.get("card") or actor.get("name") or "claude")
    try:
        qid = E._write(ctx, lrel, "ask", text="%s changed “%s”. Take the change?" % (name, title), frm=frm, to=t.OWNER,
                       options="Take it | Keep mine")
    except E._WriteFailed:
        raise
    state.setdefault("edits", {})[qid] = {"key": key, "kind": kind, "path": rel, "proposed": prop, "base": base,
                                         "from": name, "title": title, "settled": False, "at": _now()}
    return E.R_APPLIED, False, ""


def _restore_frontmatter(original, text):
    """`text` with the frontmatter of `original` (the home's own keys never change through someone else's edit)."""
    fm_o, _b = split_frontmatter(original)
    _fm, body = split_frontmatter(text)
    return _with_frontmatter(fm_o, body) if fm_o is not None else body


def settle_proposals(ctx, st, state, report):
    """Each edit question the owner has answered: Take it lays the change on the original (a clean merge), Keep mine
    leaves it. A clash leaves the original and the proposed file beside it, with a line saying so."""
    brain = ctx["brain"]
    lrel = st.get("list") or E.list_rel(st["name"])
    for qid, ed in (state.get("edits") or {}).items():
        if ed.get("settled"):
            continue
        it = E._read_item(ctx, lrel, qid)[0]
        if not it or it["mark"] != "a":
            continue
        ans = (it.get("answer") or "").strip().lower()
        if ans.startswith("take"):
            mine = _read(brain, ed["path"]) or ""
            theirs = _read(brain, ed["proposed"]) or ""
            base = ed.get("base") or ""
            if ed["kind"] == "thread":
                base = _restore_frontmatter(mine, base)
            merged, clean = _merge3(base, mine, theirs)
            if clean:
                _write(brain, ed["path"], merged)
                report["problems"].append("%s's change to “%s” was taken in." % (ed["from"], ed["title"]))
            else:
                report["problems"].append("%s's change to “%s” touches the same lines as yours; your version was left "
                                          "and theirs is beside it." % (ed["from"], ed["title"]))
        ed["settled"] = True
        ctx["save"]()


# ---------------------------------------------------------------- the receiving side

def _place(st, kind, body, who=None):
    base = "%s/%s/%s" % (E.share.SHARED_DIR, st["name"], PLACE[kind])
    if kind == "file":
        name = body["name"] + (" (from %s)" % who if who else "")
        return "%s/%s%s" % (base, name, body["ext"])
    if kind == "thread":
        return "%s/%s%s.md" % (base, body["slug"], (" (from %s)" % who) if who else "")
    return "%s/%s%s.canvas" % (base, body["name"], (" (from %s)" % who) if who else "")


def _thread_text(st, text):
    fm, body = split_frontmatter(text)
    fm = [l for l in (fm or []) if not re.match(r"^project\s*:", l)]
    return _with_frontmatter(fm + ["project: shared-%s" % st["name"]], body)


def take_text(ctx, st, state, row, writer, report):
    """A file, thread, drawing, card section or message from someone else, written where the table says (a file there
    with other content than this thing's last version is never overwritten: the new one goes beside it)."""
    brain = ctx["brain"]
    kind = row.get("kind")
    tid, version = row["id"], int(row.get("version") or 0)
    e = state["in"].get(tid) or {}
    who = writer.get("display") or "Someone"
    if kind == "message":
        if not e:
            b = _norm("message", row.get("body"))
            if b["text"]:
                _append_message(brain, st, {"id": tid, "from_user": row.get("home"), "from": who, "at": b["at"] or _now(),
                                            "text": b["text"]})
        state["in"][tid] = {"kind": "message", "version": version, "home": row.get("home")}
        report["received"] += 1
        return
    if row.get("removed_at"):
        if kind == "card-section":
            for pr in (state.get("proposals") or {}).values():
                if pr.get("thing") == tid and not pr.get("status"):
                    pr["status"] = "taken back"
        state["in"][tid] = dict(e, kind=kind, version=version, removed=True, home=row.get("home"))
        report["received"] += 1
        return
    body = _norm(kind, row.get("body"))
    if kind == "card-section":
        props = state.setdefault("proposals", {})
        absorbed = (state.setdefault("absorbed", {})).get(tid, 0)
        if version > absorbed:
            pid = "%s:%s" % (st["name"], tid)
            props[pid] = {"id": pid, "thing": tid, "version": version, "space": st["name"], "from": who,
                          "from_user": row.get("home"), "person": body["person"], "heading": body["heading"],
                          "text": body["text"], "at": _now(), "status": None}
        state["in"][tid] = {"kind": kind, "version": version, "home": row.get("home")}
        report["received"] += 1
        return
    if kind == "file" and not body["ext"]:
        report["problems"].append("A file from %s is not a kind of text file this brain takes in." % who)
        state["in"][tid] = {"kind": kind, "version": version, "home": row.get("home"), "refused": True}
        return
    if kind == "thread":
        fm, _b = split_frontmatter(body["text"])
        proj = next((l for l in fm or [] if re.match(r"^project\s*:", l)), None)
        text = _thread_text(st, body["text"])
    elif kind == "drawing":
        text = body["canvas"]
    else:
        text = body["text"]
    path = e.get("path") or _place(st, kind, body)
    have = _read(brain, path)
    if have is not None and have != e.get("written") and have != text:
        path = _place(st, kind, body, who)
        report["problems"].append("“%s” from %s was written beside your own file of that name, not over it." % (body["title"], who))
    _write(brain, path, text)
    if kind == "drawing" and body.get("forge"):
        _write(brain, path[: -len(".canvas")] + ".forge.json", body["forge"])
    state["in"][tid] = {"kind": kind, "version": version, "home": row.get("home"), "path": path, "written": text,
                        "forge_written": body.get("forge") if kind == "drawing" else None, "title": body["title"],
                        "project_line": proj if kind == "thread" else None, "at": _now(), "opened": e.get("opened", False)}
    report["received"] += 1


def send_edits(ctx, st, state, report):
    """A file, thread or drawing of someone else's changed here: one `edit` act, through this side's gate."""
    brain = ctx["brain"]
    for tid, e in list(state["in"].items()):
        if e.get("kind") not in TEXT_KINDS or e.get("removed") or e.get("refused") or e.get("written") is None:
            continue
        cur = _read(brain, e["path"])
        if cur is None or cur == e["written"]:
            continue
        title = e.get("title") or e["path"].rsplit("/", 1)[-1]
        if e["kind"] == "drawing":
            forge = _read(brain, e["path"][: -len(".canvas")] + ".forge.json")
            got, why = E.gate.render_drawing(brain, e["path"], cur, forge)
            payload = {"canvas": got["canvas"], "forge": got["forge"]} if got else None
        else:
            text = cur
            if e["kind"] == "thread":                      # the space's own project line goes back to what came
                fm, body = split_frontmatter(cur)
                fm = [l for l in (fm or []) if not re.match(r"^project\s*:", l)] + ([e["project_line"]] if e.get("project_line") else [])
                text = _with_frontmatter(fm, body)
            got, why = E.gate.render_text(brain, e["path"], text, None)
            payload = {"text": got} if got is not None else None
        if payload is None:
            report["problems"].append("Your change to “%s” stays here: %s." % (title, why))
        else:
            E.call(ctx, "add_act", tid, "edit", payload)
            report["acts_out"] += 1
        e["written"] = cur
        ctx["save"]()


# ---------------------------------------------------------------- card sections, at the receiver

def _all_states(brain):
    for st in E._service_stamps(brain, attached_only=False):
        yield st, E._load_state(brain, st["name"])


def proposals(brain):
    brain = E.share.brain_root(brain)
    out = []
    for st, state in _all_states(brain):
        for pr in (state.get("proposals") or {}).values():
            if not pr.get("status"):
                out.append({k: pr[k] for k in ("id", "space", "from", "person", "heading", "text", "at")})
    return out


def _find_proposal(brain, proposal_id):
    for st, state in _all_states(brain):
        pr = (state.get("proposals") or {}).get(proposal_id)
        if pr:
            return st, state, pr
    return None, None, None


def _card_for_person(brain, person):
    """The card that holds the person's name (its title), else a minimal card made now."""
    folder = _p(brain, "people")
    want = " ".join(str(person).split()).lower()
    try:
        names = sorted(f for f in os.listdir(folder) if f.endswith(".md") and f != "readme.md")
    except OSError:
        names = []
    for f in names:
        text = _read(brain, "people/" + f) or ""
        m = re.match(r"^#\s+(.+)$", text.split("\n", 1)[0])
        if m and " ".join(m.group(1).split()).lower() == want:
            return f[:-3]
    # nobody by that name has a card: a plain one, never the share partner's card (the person a section is about is
    # not the person who shared it; found on the real service, 2026-11-10)
    shown = E.clean_name(person, "")
    base = E._slug(shown) or "person"
    slug, n = base, 1
    while E._card_text(brain, slug) is not None:
        n += 1
        slug = "%s-%d" % (base, n)
    E.share._write_text(_p(brain, "people/%s.md" % slug),
                        "# %s\n\n**Where it stands (%s):** A card made to hold a section someone shared with you.\n" % (shown, E._today()))
    E.share._log(brain, "CREATED", "people/%s.md -- a card for the person a shared section is about" % slug)
    return slug


def take_section(brain, proposal_id):
    brain = E.share.brain_root(brain)
    st, state, pr = _find_proposal(brain, proposal_id)
    if not pr or pr.get("status"):
        return False, "That proposal is not waiting any more."
    slug = _card_for_person(brain, pr["person"])
    rel = "people/%s.md" % slug
    text = (_read(brain, rel) or "# %s\n" % pr["person"]).rstrip("\n")
    fold = "\n\n## %s (from %s, %s)\n\n%s\n" % (pr["heading"], pr["from"], E._md(), pr["text"].strip("\n"))
    _write(brain, rel, text + fold)
    pr["status"] = "taken"
    state.setdefault("absorbed", {})[pr["thing"]] = pr["version"]
    E._save_state(brain, st["name"], state)
    E.share._log(brain, "MODIFIED", "%s -- a section a share partner sent was taken into the card" % rel)
    return True, "Taken into %s's card." % pr["person"]


def leave_section(brain, proposal_id):
    brain = E.share.brain_root(brain)
    st, state, pr = _find_proposal(brain, proposal_id)
    if not pr or pr.get("status"):
        return False, "That proposal is not waiting any more."
    pr["status"] = "left"
    state.setdefault("absorbed", {})[pr["thing"]] = pr["version"]
    E._save_state(brain, st["name"], state)
    return True, "Left it; %s's card is as it was." % pr["person"]


# ---------------------------------------------------------------- messages

def _messages_rel(st):
    return "%s/%s/messages.jsonl" % (E.share.SHARED_DIR, st["name"])


def _read_messages(brain, st):
    out = []
    try:
        with open(_p(brain, _messages_rel(st)), "r", encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if isinstance(m, dict) and m.get("id"):
                    out.append(m)
    except OSError:
        pass
    return out


def _append_message(brain, st, m):
    have = {x["id"] for x in _read_messages(brain, st)}
    if m["id"] in have:
        return
    path = _p(brain, _messages_rel(st))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(m, ensure_ascii=False) + "\n")


def send_message(brain, space, text):
    ctx, st, why = _ready(brain, space)
    if not ctx:
        return False, why
    brain = ctx["brain"]
    words = " ".join(str(text or "").split())
    if not words:
        return False, "Write something to send."
    why = E.gate.words_refusal(brain, words)
    if why:
        return False, "Not sent to %s: %s." % (st["label"], why)
    words = E.gate.clean_words(brain, words)[:4000]
    at = _now()
    try:
        got = E.call(ctx, "put_thing", {"id": None, "space_id": st["space_id"], "kind": "message", "home": ctx["uid"],
                                        "key": secrets.token_hex(8), "title": "", "body": {"text": words, "at": at},
                                        "removed_at": None})
    except E.service.ServiceError:
        return False, E.OFFLINE
    _append_message(brain, st, {"id": got["id"], "from_user": ctx["uid"], "from": ctx["display"], "at": at, "text": words})
    with E._SpaceLock(brain, st["name"]) as ok:
        state = E._load_state(brain, st["name"])
        state["in"][got["id"]] = {"kind": "message", "version": got["version"], "home": ctx["uid"]}
        if ok:
            E._save_state(brain, st["name"], state)
    return True, "Sent to %s." % st["label"]


def messages(brain, space, limit=50):
    brain = E.share.brain_root(brain)
    st = E._find_stamp(brain, space)
    if not st:
        return []
    return _read_messages(brain, st)[-int(limit or 50):]


def unread(brain, st):
    state = E.share._read_json(_p(brain, "%s/%s/.sync/state.json" % (E.share.SHARED_DIR, st["name"]))) or {}
    upto = state.get("read_upto")
    ms = _read_messages(brain, st)
    me = st.get("me_user")
    idx = next((i for i, m in enumerate(ms) if m["id"] == upto), -1)
    return sum(1 for m in ms[idx + 1:] if m.get("from_user") != me)


def mark_read(brain, space):
    brain = E.share.brain_root(brain)
    st = E._find_stamp(brain, space)
    if not st:
        return False, "You do not share with anyone named %s." % E.clean_name(space)
    ms = _read_messages(brain, st)
    state = E._load_state(brain, st["name"])
    state["read_upto"] = ms[-1]["id"] if ms else None
    E._save_state(brain, st["name"], state)
    return True, "Marked as read."


def mark_opened(brain, space, thing_id):
    """This computer's person opened a file, drawing or thread they were sent: from_them says opened from now on. No
    network call. -> (ok, line)."""
    brain = E.share.brain_root(brain)
    st = E._find_stamp(brain, space)
    if not st:
        return False, "You do not share with anyone named %s." % E.clean_name(space)
    state = E._load_state(brain, st["name"])
    e = state["in"].get(str(thing_id or ""))
    if not e or e.get("kind") not in TEXT_KINDS:
        return False, "That was not shared with you."
    if not e.get("opened"):
        e["opened"] = True
        E._save_state(brain, st["name"], state)
    return True, "Marked as opened."


def set_auto_take(brain, space, on):
    brain = E.share.brain_root(brain)
    st = E._find_stamp(brain, space)
    if not st:
        return False, "You do not share with anyone named %s." % E.clean_name(space)
    for m in st.get("members") or []:
        if m.get("user_id") != st.get("me_user"):
            m["auto_take"] = bool(on)
    E._save_stamp(brain, st)
    return True, ("Changes from %s to what you share are taken in without asking when they merge cleanly." if on
                  else "You are asked before a change from %s is taken in.") % st["label"]


# ---------------------------------------------------------------- the space's page

def space_view(brain, space):
    brain = E.share.brain_root(brain)
    st = E._find_stamp(brain, space)
    if not st:
        return None
    state = E._load_state(brain, st["name"])
    sp = E.share._normal(brain, st, st["name"], True)
    here, host_name = E.share._here(brain, sp)
    me = st.get("me_user")
    people = [{"name": m.get("name"), "display": m.get("display"), "card": m.get("card"), "left": m.get("left")}
              for m in st.get("members") or [] if m.get("user_id") != me]
    _d, rows = _sent_rows(brain, st)
    shared = []
    for row in rows["items"]:
        e = state["out"].get("%s/%s" % (row.get("project"), row.get("id"))) or {}
        rel = E._ledger_rel(brain, row.get("project"), row.get("ledger"))
        title = next((i["text"] for i in E.tasks_for(brain).parse(_read(brain, rel) or "")["items"] if i["id"] == row.get("id")), row.get("id")) if rel else row.get("id")
        shared.append({"kind": "question" if str(row.get("id")).startswith("Q-") else "task", "title": title,
                       "path": "%s#%s" % (rel, row.get("id")), "at": row.get("at"), "held": bool(e.get("held")), "why": e.get("held") or ""})
    for kind in ("file", "thread", "drawing", "card-section"):
        for row in rows[SENT_KEY[kind]]:
            path = row.get("card") + "#" + row.get("heading") if kind == "card-section" else row.get("path")
            key = _key(kind, row.get("card") if kind == "card-section" else row.get("path"), row.get("heading"))
            e = state["out"].get(key) or {}
            shared.append({"kind": kind, "title": row.get("heading") if kind == "card-section" else path.rsplit("/", 1)[-1],
                           "path": path, "at": row.get("at"), "held": bool(e.get("held")), "why": e.get("held") or ""})
    names = {m.get("user_id"): m.get("display") for m in st.get("members") or []}
    lrel = st.get("list") or E.list_rel(st["name"])
    local = {i["id"]: i for i in E.tasks_for(brain).parse(_read(brain, lrel) or "")["items"]}
    from_them, made_here = [], []
    for tid, e in state["in"].items():
        if e.get("kind") == "message" or e.get("refused"):
            continue
        if e.get("home") and e.get("home") != me:
            if e.get("kind") in TEXT_KINDS:
                from_them.append({"id": tid, "kind": e["kind"], "title": e.get("title"), "path": e.get("path"), "from": names.get(e["home"]),
                                  "at": e.get("at"), "opened": bool(e.get("opened")), "taken_back": bool(e.get("removed"))})
            elif e.get("local") in local:
                it = local[e["local"]]
                from_them.append({"kind": it["kind"], "title": it["text"], "path": "%s#%s" % (lrel, it["id"]),
                                  "from": names.get(e["home"]), "at": it.get("created"), "opened": True, "taken_back": bool(e.get("removed"))})
        elif not e.get("home") and e.get("local") in local:
            it = local[e["local"]]
            made_here.append({"kind": it["kind"], "title": it["text"], "path": "%s#%s" % (lrel, it["id"]), "at": it.get("created")})
    props = [dict({k: pr[k] for k in ("id", "space", "from", "person", "heading", "text", "at")}, kind="card-section")
             for pr in (state.get("proposals") or {}).values() if not pr.get("status")]
    for qid, ed in (state.get("edits") or {}).items():
        if not ed.get("settled"):
            props.append({"id": qid, "space": st["name"], "from": ed["from"], "kind": "edit", "title": ed["title"],
                          "path": ed["path"], "proposed": ed["proposed"], "at": ed.get("at")})
    return {"label": st["label"], "kind": st.get("kind"), "people": people, "here": here, "host_name": host_name,
            "shared": shared, "from_them": from_them, "made_here": made_here, "proposals": props,
            "messages": _read_messages(brain, st)[-50:], "unread": unread(brain, st)}


# ---------------------------------------------------------------- round four: a whole project into a space

SKIP_DIRS = {".git", "node_modules", ".obsidian", "archive", "shared", "__pycache__", ".claude", "viewer"}


def _registry(brain):
    path = _p(brain, E.share.REGISTRY_REL)
    reg = E.share._read_json(path)
    return path, reg if isinstance(reg, dict) else None


def _subject_files(brain, project):
    """Every subject file (a markdown file whose frontmatter names project: <id>) of a project."""
    out = []
    for root, dirs, files in os.walk(brain):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            if not fn.endswith(".md") or fn.endswith("-tasks.md"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), brain).replace(os.sep, "/")
            fm, _b = split_frontmatter(_read(brain, rel) or "")
            if any(re.match(r"^project\s*:\s*%s\s*$" % re.escape(project), l) for l in fm or []):
                out.append(rel)
    return sorted(out)


def sweep_project(ctx, st, project):
    """Put on sent.json, through the gate, what of a project is not on it yet: every open task and question on its list,
    every subject file whose project it is, and every text file under its folder. Returns the counts added."""
    brain = ctx["brain"]
    _path, reg = _registry(brain)
    row = next((h for h in (reg or {}).get("holons", []) if h.get("id") == project), None)
    counts = {"tasks": 0, "questions": 0, "threads": 0, "files": 0}
    if not row:
        return counts
    holds = E._holds(st, ctx)
    d, rows = _sent_rows(brain, st)
    lrel = E.gate._norm(row.get("tasks")) if row.get("tasks") else None
    if lrel:
        for it in E._items(ctx, lrel):
            if it["mark"] not in " -?" or any(x.get("project") == project and x.get("id") == it["id"] for x in rows["items"]):
                continue
            body, _w = E.gate.render_task(brain, lrel, it, _raw_line(brain, lrel, it), holds)
            if body:
                rows["items"].append({"project": project, "ledger": lrel, "id": it["id"], "at": _now(), "thing": None, "via": project})
                counts["questions" if it["kind"] == "question" else "tasks"] += 1
    threads = _subject_files(brain, project)
    for rel in threads:
        if not any(x.get("path") == rel for x in rows["threads"]) and render(brain, "thread", {"path": rel}, holds)[0]:
            rows["threads"].append({"path": rel, "at": _now(), "thing": None, "via": project})
            counts["threads"] += 1
    folder = E.gate._norm(row.get("path")).rstrip("/")
    if folder:
        for root, dirs, files in os.walk(_p(brain, folder)):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
            for fn in sorted(files):
                rel = os.path.relpath(os.path.join(root, fn), brain).replace(os.sep, "/")
                if rel == lrel or rel in threads or not rel.lower().endswith(E.gate.TEXT_EXTS) or fn.endswith("-tasks.md"):
                    continue
                if any(x.get("path") == rel for x in rows["files"]):
                    continue
                if render(brain, "file", {"path": rel}, holds)[0]:
                    rows["files"].append({"path": rel, "at": _now(), "thing": None, "via": project})
                    counts["files"] += 1
    if any(counts.values()):
        _save_rows(brain, st, d, rows)
    return counts


def _counts_words(c):
    bits = [E._count_words(c[k], w) for k, w in (("tasks", "task"), ("questions", "question"), ("threads", "thread"), ("files", "file")) if c.get(k)]
    return (", ".join(bits[:-1]) + " and " + bits[-1]) if len(bits) > 1 else (bits[0] if bits else "nothing new")


def share_project(brain, space, project):
    """A whole project into a space: its registry row says sharing: space:<name>, and everything of it that passes the
    gate is shared now and at every check after. {ok, line, counts}."""
    ctx, st, why = _ready(brain, space)
    if not ctx:
        return {"ok": False, "line": why, "counts": {}}
    if ctx.get("out"):                                         # an employer's computer: sharing out waits for the yes
        return {"ok": False, "line": ctx["out"], "counts": {}}
    brain = ctx["brain"]
    path, reg = _registry(brain)
    row = next((h for h in (reg or {}).get("holons", []) if h.get("id") == project), None)
    if not row:
        return {"ok": False, "line": "There is no project called %s here." % E.clean_name(project), "counts": {}}
    label = E.gate.list_label(brain, row.get("tasks") or row.get("path") or "") or E.clean_name(row.get("name"), project)
    if E.gate._covering_says_employer(brain, E.gate._norm(row.get("tasks") or row.get("path") or "")) \
            or str(row.get("sharing") or "").lower() == "employer":
        return {"ok": False, "line": "Not shared with %s: the %s project belongs to an employer." % (st["label"], label), "counts": {}}
    projects = st.setdefault("projects", {})
    if project not in projects:
        projects[project] = {"was": row.get("sharing"), "label": label, "at": _now()}
    row["sharing"] = "space:%s" % st["name"]
    E.share._write_json(path, reg)
    E._save_stamp(brain, st)
    counts = sweep_project(ctx, st, project)
    E.share._log(brain, "MODIFIED", "%s -- the %s project is shared into a space" % (st["sent"], project))
    res = E.sync(brain, on_purpose=True, only=st["name"])
    tail = "" if res.get("ok") else " (%s)" % res.get("line")
    return {"ok": True, "line": "Shared the %s project with %s: %s.%s" % (label, st["label"], _counts_words(counts), tail), "counts": counts}


def unshare_project(brain, space, project):
    """Stop sharing a project into a space and take all of it back. {ok, line, counts}."""
    ctx, st, why = _ready(brain, space)
    if not ctx:
        return {"ok": False, "line": why, "counts": {}}
    brain = ctx["brain"]
    info = (st.get("projects") or {}).get(project)
    if not info:
        return {"ok": False, "line": "That project is not shared with %s." % st["label"], "counts": {}}
    d, rows = _sent_rows(brain, st)
    counts = {"tasks": 0, "questions": 0, "threads": 0, "files": 0}
    with E._SpaceLock(brain, st["name"]) as ok:
        if not ok:
            return {"ok": False, "line": "This space is already being checked; try again in a moment.", "counts": {}}
        state = E._load_state(brain, st["name"])
        try:
            for row in [x for x in rows["items"] if x.get("via") == project]:
                E._remove_own(ctx, st, state, row)
                counts["questions" if str(row.get("id")).startswith("Q-") else "tasks"] += 1
            for kind in ("thread", "file"):
                for row in [x for x in rows[SENT_KEY[kind]] if x.get("via") == project]:
                    key = _key(kind, row["path"])
                    e = state["out"].get(key)
                    if e and e.get("thing"):
                        E._put_own(ctx, st, state, key, {"kind": kind, "removed": True}, removed=True)
                    state["out"].pop(key, None)
                    counts[SENT_KEY[kind]] += 1
        except E.service.ServiceError:
            E._save_state(brain, st["name"], state)
            return {"ok": False, "line": E.OFFLINE, "counts": {}}
        E._save_state(brain, st["name"], state)
        for k in ("items", "threads", "files"):
            rows[k] = [x for x in rows[k] if x.get("via") != project]
        _save_rows(brain, st, d, rows)
    path, reg = _registry(brain)
    row = next((h for h in (reg or {}).get("holons", []) if h.get("id") == project), None)
    if row is not None:
        if info.get("was") is None:
            row.pop("sharing", None)
        else:
            row["sharing"] = info["was"]
        E.share._write_json(path, reg)
    st["projects"].pop(project, None)
    E._save_stamp(brain, st)
    E.share._log(brain, "MODIFIED", "%s -- the %s project is no longer shared into a space" % (st["sent"], project))
    E.sync(brain, on_purpose=True, only=st["name"])
    return {"ok": True, "line": "Stopped sharing the %s project with %s and took back %s." % (
        info.get("label") or project, st["label"], _counts_words(counts)), "counts": counts}


def group_of(st, row):
    """The heading a shared item sits under on the other side: its project's label, when the project is shared whole."""
    return ((st.get("projects") or {}).get(row.get("via")) or {}).get("label") if row.get("via") else None
