#!/usr/bin/env python3
"""skills/sharing/mailbox.py -- a mailbox per person, and one press that sends to many (2026-11-11).

A mailbox is one small shared space between the people who run a program (its admins) and ONE person in it. It is the
one channel between them: what an admin sends lands in that person's mailbox and nowhere else, and what the person
does with it comes back there. Nothing new is needed on the sharing service: a mailbox is a team space whose short
name starts `mailbox-`, so every rule that already holds for a space holds for it.

    make(brain, email, name)            an admin makes a mailbox for one person and invites them (and the other admins)
    boxes(brain)                        this brain's mailboxes: [{space, person, joined}]
    send(brain, kind, ref, to=None)     one thing into every mailbox, or only the ones named in `to`
    auto_join(brain)                    an admin's brain accepts a mailbox another admin made, with no press

Who is an admin is a setting of the brain, never the service's: in viewer/settings.json
    "sharing_admin": true                                  this brain makes mailboxes and sends to many
    "sharing_org": "the name the person reads on their side"
    "sharing_admins": [{"name": "...", "email": "..."}]    the other admins, invited into every mailbox

What a send is. A task or a question is COPIED into each chosen mailbox's own list, as that person's to do (or to
answer): each person sees only their own copy, and their tick, done mark or answer comes back on that copy alone. The
copy's words pass the gate first, exactly as a shared item's do. A file, a thread or a drawing is shared into each
chosen mailbox the usual way. Sending the same thing to the same mailbox twice puts nothing there a second time.

Standard library only; the engine binds itself as `E` when it loads this file. Spec: skills/sharing/readme.md.
"""
import datetime as dt
import os

E = None          # the engine, bound by engine.py: E.<name> reads the engine's own names at call time
PREFIX = "mailbox-"
NOT_ADMIN = "Mailboxes are made and sent to from the brain of someone who runs the program."
SENDS = {"task", "question", "file", "thread", "drawing"}


def _settings(brain):
    st, ok = E._settings_raw(brain)
    return st if ok and isinstance(st, dict) else {}


def is_admin(brain):
    return _settings(E.share.brain_root(brain)).get("sharing_admin") is True


def admins(brain):
    """The other admins this brain names: [{name, email}], addresses lower case, unreadable rows left out."""
    out = []
    for a in _settings(brain).get("sharing_admins") or []:
        mail = E.clean_email(a.get("email") if isinstance(a, dict) else a)
        if mail:
            out.append({"name": E.clean_name(a.get("name"), "") if isinstance(a, dict) else "", "email": mail})
    return out


def _org(brain, ctx):
    return E.clean_name(_settings(brain).get("sharing_org"), ctx["display"])


def _person_from(name):
    words = [w for w in str(name or "")[len(PREFIX):].split("-") if w]
    return " ".join(w[:1].upper() + w[1:] for w in words) or "Someone"


def _rename_row(brain, space, person):
    """The space's registry row says whose mailbox it is (it was written with the organisation's name)."""
    path = E.share._p(brain, E.share.REGISTRY_REL)
    reg = E.share._read_json(path)
    if not isinstance(reg, dict) or not isinstance(reg.get("holons"), list):
        return
    for h in reg["holons"]:
        if h.get("id") == "shared-" + space and h.get("name") != "Mailbox: %s" % person:
            h["name"] = "Mailbox: %s" % person
            h["description"] = "The mailbox this brain shares with %s; the stamp space.json says who is in it." % person
            E.share._write_json(path, reg)
            return


def _mark(brain, st):
    """A space named mailbox-... that this admin's brain holds with no mailbox stamp yet (it joined one another admin
    made): say whose it is, from the member who is not an admin, else from the space's own name."""
    mine = {a["email"] for a in admins(brain)}
    other = [m for m in st.get("members") or [] if m.get("user_id") and m.get("user_id") != st.get("me_user")
             and E.clean_email(m.get("email")) not in mine and m.get("role") != "maker"]
    person = (other[0].get("display") if other else "") or _person_from(st.get("name"))
    st["label"] = person
    st["mailbox"] = {"person": person, "email": E.clean_email(other[0].get("email")) if other else "",
                     "card": other[0].get("card") if other else None}
    E._save_stamp(brain, st)
    _rename_row(brain, st["name"], person)


def boxes(brain):
    """This brain's mailboxes, by the person's name: [{space, person, joined}]. Empty in a brain that is not an admin's."""
    brain = E.share.brain_root(brain)
    if not is_admin(brain):
        return []
    out = []
    for st in E._service_stamps(brain, attached_only=True):
        if not str(st.get("name") or "").startswith(PREFIX):
            continue
        mb = st.get("mailbox")
        if not isinstance(mb, dict) or (not mb.get("email") and any(m.get("user_id") and m.get("user_id") != st.get("me_user")
                                                                     and m.get("role") != "maker" for m in st.get("members") or [])):
            _mark(brain, st)
            mb = st["mailbox"]
        mail = E.clean_email(mb.get("email"))
        joined = any(m.get("user_id") and not m.get("left") and (E.clean_email(m.get("email")) == mail if mail else m.get("role") != "maker")
                     and m.get("user_id") != st.get("me_user") for m in st.get("members") or [])
        out.append({"space": st["name"], "person": mb.get("person") or st.get("label") or _person_from(st["name"]), "joined": joined,
                    "open": _open_count(brain, st)})
    return sorted(out, key=lambda b: b["person"].lower())


def _open_count(brain, st):
    """How many things in this mailbox are still open (not done, not answered), whoever they wait on."""
    try:
        t = E.tasks_for(brain)
        p = E.share._p(brain, st.get("list") or E.list_rel(st["name"]))
        return sum(1 for i in (t.parse(t.read(p))["items"] if os.path.isfile(p) else []) if i.get("mark") in (" ", "?"))
    except Exception:                                          # noqa: BLE001 -- a count that cannot be read is no count
        return 0


def make(brain, email, name):
    """A mailbox for one person: the space, their invitation, and an invitation for each other admin.
    {ok, line, code, text, space}: the code is shown here once and kept nowhere."""
    brain = E.share.brain_root(brain)
    if not is_admin(brain):
        return {"ok": False, "line": NOT_ADMIN}
    mail, person = E.clean_email(email), E.clean_name(name, "")
    if not mail or not person:
        return {"ok": False, "line": "Enter the person's name and their email address."}
    short = PREFIX + (E._slug(person) or "person")
    if E._find_stamp(brain, short):
        return {"ok": False, "line": "%s already has a mailbox here." % person}
    try:
        ctx = E._ctx(brain)
    except E.Refused as e:
        return {"ok": False, "line": str(e)}
    made = E.make_team(brain, short, _org(brain, ctx))
    if not made.get("ok"):
        return made
    space = made["space"]
    card = E.ensure_card(brain, person, E._slug(person), mail)
    inv = E.invite(brain, mail, person, card=card, team=space)
    st = E._find_stamp(brain, space)
    st["label"] = person
    st["mailbox"] = {"person": person, "email": mail, "card": card}
    E._save_stamp(brain, st)
    _rename_row(brain, space, person)
    if not inv.get("ok"):
        return {"ok": False, "line": "The mailbox for %s is made, and the invitation did not go: %s" % (person, inv.get("line")), "space": space}
    me = E.clean_email(ctx["sess"].get("email"))
    also = []
    for a in admins(brain):
        if a["email"] == me:
            continue
        ra = E.invite(brain, a["email"], a["name"] or a["email"].split("@")[0], team=space)
        if ra.get("ok"):
            also.append(a["name"] or a["email"])
    E.share._log(brain, "CREATED", "%s/%s/ -- a mailbox for one person was made" % (E.share.SHARED_DIR, space))
    tail = (" %s can see it too." % " and ".join(also)) if also else ""
    return {"ok": True, "line": "Made a mailbox for %s. Send %s the text below; the code is shown only now.%s" % (person, person, tail),
            "code": inv.get("code"), "text": inv.get("text"), "space": space}


def auto_join(brain):
    """An admin's brain accepts, with no press, an invitation from another admin into a space that reads as this
    program's (its label is this brain's sharing_org): the mailboxes the other admin makes. Returns the spaces joined."""
    brain = E.share.brain_root(brain)
    if not is_admin(brain):
        return []
    mine = {a["email"] for a in admins(brain)}
    want = E.clean_name(_settings(brain).get("sharing_org"), "")
    if not mine or not want:
        return []
    r = E.invites(brain)
    done = []
    for inv in (r.get("invites") or []) if isinstance(r, dict) else []:
        if inv.get("space_kind") == "team" and E.clean_email(inv.get("from_email")) in mine \
                and E.clean_name(inv.get("space_label"), "") == want:
            a = E.accept(brain, invite_id=inv.get("id"))
            if a.get("ok") and a.get("space"):
                done.append(a["space"])
    if done:
        boxes(brain)                                           # says whose each one is
    return done


def _names(rows):
    names = [r for r in rows if r]
    return names[0] if len(names) == 1 else (", ".join(names[:-1]) + " and " + names[-1]) if names else ""


def _copy_item(ctx, brain, st, box, kind, body, key):
    """One copy of a task or a question on a mailbox's own list. ("sent" | "there" | a line that says why not)."""
    rel = st.get("list") or E.list_rel(st["name"])
    if E._by_key(ctx, rel, key):
        return "there"
    mb = st.get("mailbox") or {}
    card = mb.get("card") or next((m.get("card") for m in st.get("members") or []
                                   if m.get("card") and m.get("user_id") != st.get("me_user") and m.get("role") != "maker"), None)
    if not card:
        return "%s has not joined yet, so nothing can be put down as theirs" % box["person"]
    try:
        if kind == "question":
            opts = " | ".join(body["options"]) if 2 <= len(body.get("options") or []) <= 6 else None
            iid = E._write(ctx, rel, "ask", text=body["text"], frm=ctx["tasks"].OWNER, to="@" + card, note=body.get("note") or None,
                           options=opts, key=key, due=body.get("due") or None)
        else:
            iid = E._write(ctx, rel, "add", text=body["text"], owner="@" + card, note=body.get("note") or None, key=key,
                           due=body.get("due") or None)
            if body.get("steps"):
                E._write(ctx, rel, "steps", id=iid, steps=[{"text": s["text"], "done": False} for s in body["steps"]])
    except E._WriteFailed:
        return "it could not be written to %s's mailbox" % box["person"]
    return "sent"


def send(brain, kind, ref, to=None):
    """One thing into every mailbox (`to` None or "all") or only the ones named (a list of space names).
    ref: {"project", "id"} for a task or a question; {"path"} for a file, a thread or a drawing.
    {ok, line, sent: [person], there: [person], not_sent: [{person, why}]}."""
    brain = E.share.brain_root(brain)
    ref = ref if isinstance(ref, dict) else {}
    if not is_admin(brain):
        return {"ok": False, "line": NOT_ADMIN}
    if kind not in SENDS:
        return {"ok": False, "line": "That kind of thing is not sent to mailboxes."}
    every = boxes(brain)
    if not every:
        return {"ok": False, "line": "There are no mailboxes yet. Make one in Settings, under Sharing."}
    if to in (None, "all"):
        chosen = every
    else:
        names = {str(x) for x in (to if isinstance(to, (list, tuple, set)) else [to])}
        chosen = [b for b in every if b["space"] in names]
    if not chosen:
        return {"ok": False, "line": "Pick at least one mailbox."}
    try:
        ctx = E._ctx(brain)
    except E.Refused as e:
        return {"ok": False, "line": str(e)}
    if ctx.get("out"):
        return {"ok": False, "line": ctx["out"]}
    sent, there, not_sent = [], [], []
    if kind in ("task", "question"):
        rel = E._ledger_rel(brain, ref.get("project"))
        try:
            it, raw = E._read_item(ctx, rel, ref.get("id")) if rel else (None, None)
        except E._WriteFailed:
            return {"ok": False, "line": "Its list cannot be read right now."}
        if not it:
            return {"ok": False, "line": "That item is not on its list."}
        if (it.get("kind") == "question") != (kind == "question"):
            kind = "question" if it.get("kind") == "question" else "task"
        for box in chosen:
            st = E._find_stamp(brain, box["space"])
            body, why = E.gate.render_task(brain, rel, it, raw, E._holds(st, ctx))
            if not body:
                return {"ok": False, "line": "Not sent: %s." % why}       # the gate's answer is the same for every mailbox
            key = "send:%s" % E._thing_key(E._salt(brain, st), rel, it["id"])
            got = _copy_item(ctx, brain, st, box, kind, body, key)
            (sent if got == "sent" else there if got == "there" else not_sent).append(box["person"] if got in ("sent", "there") else {"person": box["person"], "why": got})
        what = "“%s”" % (it["text"] if len(it["text"]) <= 60 else it["text"][:57].rstrip() + "...")
    else:
        path = E.gate._norm(ref.get("path") or "")
        fn = {"file": E.share_file, "thread": E.share_thread, "drawing": E.share_drawing}[kind]
        for box in chosen:
            ok, line = fn(brain, box["space"], path)
            if ok:
                sent.append(box["person"])
            elif "already" in str(line).lower():
                there.append(box["person"])
            else:
                not_sent.append({"person": box["person"], "why": str(line)})
        what = "“%s”" % os.path.basename(path)
    if sent:
        E.share._log(brain, "MODIFIED", "%s/ -- one %s was sent to %d mailbox%s" % (E.share.SHARED_DIR, kind, len(sent), "" if len(sent) == 1 else "es"))
        if kind in ("task", "question"):
            E.sync(brain, on_purpose=True)
    bits = []
    if sent:
        bits.append("Sent %s to %s." % (what, _names(sent)))
    if there:
        bits.append("Already in the mailbox of %s." % _names(there))
    for n in not_sent:
        bits.append("Not sent to %s: %s." % (n["person"], str(n["why"]).rstrip(".")))
    return {"ok": bool(sent or there), "line": " ".join(bits) or "Nothing was sent.", "sent": sent, "there": there, "not_sent": not_sent,
            "at": dt.datetime.now().isoformat(timespec="seconds")}
