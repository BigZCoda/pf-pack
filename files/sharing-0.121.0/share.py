#!/usr/bin/env python3
"""skills/sharing/share.py -- the sharing module's register: who this brain shares with, and what.

Design: the maintainer brain's design direction of 2026-11-09 (sharing between any two brains), built in five rounds.
Spec: skills/sharing/readme.md.

A SHARED SPACE is a place two or more people hold together: two is a pair, three or more is a team brain. Every space
this brain is attached to is one folder, shared/<name>/, holding its stamp (space.json, contract shared-space/1) and a
readme that says who sees what is in it. This file reads that register, for the viewer, the ledger tool, the session
recap and any agent:

    python skills/sharing/share.py list                  # every space this brain is attached to, one line each
    python skills/sharing/share.py status                # what is shared with each; its LAST line is the recap's line
    python skills/sharing/share.py shared                # every task and thread shared, and with whom
    python skills/sharing/share.py verify                # CLEAN, or each discrepancy named (exit 1)
    python skills/sharing/share.py init                  # write the folder, stamp and registry row for a space found unregistered
    ... --json on list / status / shared for a machine; --brain <folder> or BRAIN_ROOT for another brain

    python skills/sharing/share.py signin --email E [--code C]    # round two: the sharing service (engine.py)
    ... signout, whoami, invite, invites, accept, detach, team, share, takeback, sync, client: see main() and the readme

Round one (viewer 0.109.0): the register, read-only but for `init`. One carrier exists, "team-copy": the space rides the
team copy on GitHub (skills/team-brain, skills/team-sync), and what was put on the member's Today is the file the
export already reads, skills/team-brain/shared-with-<member>.json, named by the stamp's `sent`. So nothing is kept
twice. A brain that has a team copy and no shared/ folder yet still answers: the space is derived from
skills/team-brain/status.json, marked registered: false, and `init` writes it down. The second carrier, "service",
arrives with round two: skills/sharing/service.py (the service), gate.py (what never crosses), engine.py (the sync).

`shared` on a ledger item is a COMPUTED facet: never written on the item's line (the line itself crosses, so writing
there would tell one partner who else an item is shared with). It is read from the register by shared_index().

Standard library only. Imported by path by skills/brain-viewer/serve.py and skills/brain-tasks/tasks.py.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import threading

CONTRACT = "shared-space/1"
SHARED_DIR = "shared"
STAMP = "space.json"
TEAM_STATUS_REL = "skills/team-brain/status.json"
TEAM_SENT_REL = "skills/team-brain/shared-with-{member}.json"
TEAM_STAMP_REL = "team-brain.json"
REGISTRY_REL = "context/holon-registry.json"
SETTINGS_REL = "viewer/settings.json"
LOG_REL = "skills/brain-log/log.py"
CARRIERS = ("team-copy", "service")
KINDS = ("pair", "team")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
ITEM_ID_RE = re.compile(r"^[TQ]-\d{4}$")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BRAIN = os.path.abspath(os.path.join(HERE, "..", ".."))


def brain_root(arg=None):
    return os.path.abspath(arg or os.environ.get("BRAIN_ROOT") or DEFAULT_BRAIN)


def _p(brain, rel):
    return os.path.join(brain, *str(rel).split("/"))


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def _slug(s):
    return re.sub(r"[^a-z0-9-]", "", str(s or "").lower())


# ---------------------------------------------------------------- who is who

def me(brain):
    """This brain's person, bare: the member a team copy was made for, else the viewer's `owner` setting, else me."""
    team = _read_json(_p(brain, TEAM_STAMP_REL))
    if isinstance(team, dict) and team.get("member"):
        return _slug(team["member"]) or "me"
    st = _read_json(_p(brain, SETTINGS_REL))
    if isinstance(st, dict) and st.get("owner"):
        return _slug(str(st["owner"]).lstrip("@")) or "me"
    return "me"


def card_for(brain, name):
    """The people card for a short name: people/<name>.md, else the one card whose file starts with <name>-. None when
    there is no card or more than one could be meant (the caller never guesses)."""
    name = _slug(name)
    if not name:
        return None
    folder = _p(brain, "people")
    if os.path.isfile(os.path.join(folder, name + ".md")):
        return name
    try:
        hits = sorted(f[:-3] for f in os.listdir(folder) if f.endswith(".md") and f.startswith(name + "-"))
    except OSError:
        return None
    return hits[0] if len(hits) == 1 else None


def label_for(name):
    return " ".join(w.capitalize() for w in str(name or "").split("-")) or "?"


# ---------------------------------------------------------------- the register

def _normal(brain, raw, folder, registered):
    """A stamp as every caller reads it. Missing pieces are filled from what the brain itself says, never guessed."""
    name = _slug(raw.get("name") or folder)
    carrier = raw.get("carrier") if raw.get("carrier") in CARRIERS else "team-copy"
    member = _slug(raw.get("carrier_member") or name)
    mine = _slug(raw.get("me")) or me(brain)
    members = []
    for m in raw.get("members") or []:
        if isinstance(m, dict) and m.get("name"):
            n = _slug(m["name"])
            row = {"name": n, "card": m.get("card") or (None if n == mine else card_for(brain, n)),
                   "role": m.get("role") or "member"}
            for k in ("display", "user_id", "left", "invited"):
                if m.get(k) is not None:
                    row[k] = m[k]
            members.append(row)
    if not members:
        members = [{"name": mine, "card": None, "role": "maker"},
                   {"name": name, "card": card_for(brain, name), "role": "member"}]
    kind = raw.get("kind") if raw.get("kind") in KINDS else ("team" if len(members) > 2 else "pair")
    sent_rel = raw.get("sent") or (TEAM_SENT_REL.format(member=member) if carrier == "team-copy"
                                   else "%s/%s/sent.json" % (SHARED_DIR, name))
    out = {"name": name, "label": raw.get("label") or label_for(name), "kind": kind, "me": mine, "members": members,
           "carrier": carrier, "carrier_member": member if carrier == "team-copy" else None, "sent": sent_rel,
           "page": raw.get("page") or ("/share?member=%s" % member if carrier == "team-copy" else "/share?space=%s" % name),
           "joined": raw.get("joined") or None, "state": raw.get("state") or "attached",
           "registered": registered, "dir": "%s/%s/" % (SHARED_DIR, name) if registered else None}
    if carrier == "service":
        out.update(space_id=raw.get("space_id"), list=raw.get("list") or "%s/%s/%s-tasks.md" % (SHARED_DIR, name, name),
                   left=raw.get("left") or None, host=raw.get("host") or None, host_name=raw.get("host_name") or None,
                   me_user=raw.get("me_user") or None)
    return out


HOST_REL = "shared/.sync-host"


def this_host(brain=None):
    """(id, name) of this computer, made once and kept in shared/.sync-host, which shared/.gitignore keeps out of any
    mirror. A copy that arrived from another computer anyway (its fingerprint is not this computer's and this folder's)
    is replaced, so two computers never share an id."""
    import hashlib
    import secrets
    import socket
    brain = brain_root(brain)
    name = (socket.gethostname() or "this computer").strip()
    fp = hashlib.sha256(("%s|%s" % (name.lower(), os.path.abspath(brain).lower())).encode("utf-8")).hexdigest()[:16]
    path = _p(brain, HOST_REL)
    d = _read_json(path)
    if not (isinstance(d, dict) and d.get("id") and d.get("fp") == fp):
        d = {"id": secrets.token_hex(8), "name": name, "fp": fp,
             "_about": "This computer's own id for sharing: the computer that keeps a space in step. Never mirrored."}
        _write_json(path, d)
    gi = _p(brain, "%s/.gitignore" % SHARED_DIR)
    try:
        have = open(gi, "r", encoding="utf-8").read() if os.path.isfile(gi) else ""
    except OSError:
        have = ""
    if ".sync-host" not in have.splitlines():
        _write_text(gi, (have + ("" if not have or have.endswith("\n") else "\n")) + (".sync/\n" if ".sync/" not in have.splitlines() else "") + ".sync-host\n")
    return d["id"], str(d.get("name") or name)


def _here(brain, sp):
    """(here, host name) for a service space: whether this computer keeps it in step (a space with no host yet is
    whoever checks it first, so this one)."""
    if sp["carrier"] != "service":
        return None, None
    if not sp.get("host"):
        return True, None
    return sp["host"] == this_host(brain)[0], sp.get("host_name")


def registered(brain):
    """(spaces, problems): every shared/<name>/space.json that reads as a stamp, and why each other folder does not."""
    out, bad = [], []
    root = _p(brain, SHARED_DIR)
    try:
        names = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)) and not d.startswith("."))
    except OSError:
        return out, bad
    for d in names:
        raw = _read_json(os.path.join(root, d, STAMP))
        if not isinstance(raw, dict):
            bad.append("%s/%s/: no %s that reads as JSON" % (SHARED_DIR, d, STAMP))
            continue
        if raw.get("contract") != CONTRACT:
            bad.append("%s/%s/%s: contract is %r, not %s" % (SHARED_DIR, d, STAMP, raw.get("contract"), CONTRACT))
            continue
        if _slug(raw.get("name")) != d or not NAME_RE.match(d):
            bad.append("%s/%s/%s: its name %r is not its folder's" % (SHARED_DIR, d, STAMP, raw.get("name")))
            continue
        out.append(_normal(brain, raw, d, True))
    return out, bad


def derived(brain, have):
    """The space a team copy implies when no stamp names it: the member in skills/team-brain/status.json (the owner's
    side). In a team copy itself the other side is whoever the copy came from; that side is registered by round four."""
    if os.path.isfile(_p(brain, TEAM_STAMP_REL)):
        return []
    st = _read_json(_p(brain, TEAM_STATUS_REL))
    member = _slug((st or {}).get("member")) if isinstance(st, dict) else ""
    if not member or any(s["carrier"] == "team-copy" and s["carrier_member"] == member for s in have):
        return []
    return [_normal(brain, {"name": member, "carrier": "team-copy", "carrier_member": member}, member, False)]


def spaces(brain=None):
    """Every space this brain is attached to: the registered ones, then any a team copy implies."""
    brain = brain_root(brain)
    have, _bad = registered(brain)
    out = sorted(have + derived(brain, have), key=lambda s: s["label"].lower())
    # the same person reached two ways (a team copy, and the sharing service) reads as one name twice: in a list the
    # team copy's entry says so, so a pick is never a guess (2026-11-11). `label` stays the name for sentences.
    live = [s for s in out if (s.get("state") or "attached") == "attached"]
    for s in out:
        twin = s in live and any(o is not s and o["label"].lower() == s["label"].lower() for o in live)
        s["shown"] = ("%s (team copy)" % s["label"]) if twin and s.get("carrier") == "team-copy" else s["label"]
    return out


def space(brain, name):
    name = _slug(name)
    return next((s for s in spaces(brain) if s["name"] == name), None)


# ---------------------------------------------------------------- what is shared

def sent(brain, sp):
    """What this brain put in front of a space with the Share press: {items: [{project, ledger, id, at}], threads:
    [{path, at}]}. Rows that do not read are left out, never repaired here."""
    brain = brain_root(brain)
    d = _read_json(_p(brain, sp["sent"]))
    d = d if isinstance(d, dict) else {}
    items = [x for x in d.get("items") or [] if isinstance(x, dict) and x.get("project") and ITEM_ID_RE.match(str(x.get("id") or ""))]
    threads = [x for x in d.get("threads") or [] if isinstance(x, dict) and x.get("path")]
    return {"items": items, "threads": threads}


def shared_index(brain=None):
    """The computed `shared` facet: {"items": {"<project>/<id>": [space names]}, "threads": {<path>: [space names]},
    "labels": {<space name>: <label>}}. Read fresh; nothing here is stored on an item."""
    brain = brain_root(brain)
    out = {"items": {}, "threads": {}, "labels": {}}
    for sp in spaces(brain):
        if sp.get("state") == "detached":
            continue                                           # a space this brain left shares nothing any more
        out["labels"][sp["name"]] = sp["label"]
        s = sent(brain, sp)
        for x in s["items"]:
            out["items"].setdefault("%s/%s" % (x["project"], x["id"]), []).append(sp["name"])
        for x in s["threads"]:
            out["threads"].setdefault(str(x["path"]), []).append(sp["name"])
    return out


def _kind_counts(brain, sp):
    """What this brain shared into a space beyond its items and threads: {files, drawings, sections}."""
    d = _read_json(_p(brain, sp["sent"]))
    d = d if isinstance(d, dict) else {}
    return {k: len([x for x in d.get(k) or [] if isinstance(x, dict)]) for k in ("files", "drawings", "sections")}


def _unread(brain, sp):
    """For a service space: the messages from others after the last one this computer showed."""
    state = _read_json(_p(brain, "%s/%s/.sync/state.json" % (SHARED_DIR, sp["name"]))) or {}
    me = sp.get("me_user") or next((m.get("user_id") for m in sp["members"] if m["name"] == sp["me"]), None)
    ms = []
    try:
        with open(_p(brain, "%s/%s/messages.jsonl" % (SHARED_DIR, sp["name"])), "r", encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if isinstance(m, dict) and m.get("id"):
                    ms.append(m)
    except OSError:
        return 0
    idx = next((i for i, m in enumerate(ms) if m["id"] == state.get("read_upto")), -1)
    return sum(1 for m in ms[idx + 1:] if m.get("from_user") != me)


def _held_back(brain, sp):
    """For a service space: how many shared items have a change the gate keeps here (the earlier words stay shared)."""
    state = _read_json(_p(brain, "%s/%s/.sync/state.json" % (SHARED_DIR, sp["name"]))) or {}
    return sum(1 for e in (state.get("out") or {}).values() if isinstance(e, dict) and e.get("held"))


def _waiting_from(brain, sp):
    """For a service space: the open items on the space's own list that came from someone else, by that person's name."""
    state = _read_json(_p(brain, "%s/%s/.sync/state.json" % (SHARED_DIR, sp["name"]))) or {}
    me_uid = next((m.get("user_id") for m in sp["members"] if m["name"] == sp["me"]), None)
    names = {m.get("user_id"): m["name"] for m in sp["members"]}
    try:
        with open(_p(brain, sp["list"]), "r", encoding="utf-8") as f:
            text = f.read()
    except (OSError, KeyError):
        return {}
    open_ids = set(re.findall(r"(?m)^- \[[ ?-]\] ([TQ]-\d{4}) ", text))
    out = {}
    for e in (state.get("in") or {}).values():
        if not isinstance(e, dict) or e.get("removed") or e.get("local") not in open_ids:
            continue
        if e.get("home") and e.get("home") != me_uid:
            who = names.get(e["home"]) or "someone"
            out[who] = out.get(who, 0) + 1
    return out


def _last_sent(brain, sp):
    if sp["carrier"] == "team-copy":
        st = _read_json(_p(brain, TEAM_STATUS_REL))
        if not isinstance(st, dict) or _slug(st.get("member")) != sp["carrier_member"]:
            return None                                        # the status file speaks for the one member it names
        return (st.get("last_export") or {}).get("at") or None
    return None


def _when(iso):
    """A stamp as a person reads it, in this computer's own time: 11/8 20:06. A stamp with a zone (the export writes
    UTC) is moved to local time first; one without is taken as it stands."""
    s = str(iso or "").strip()
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":     # a day with no time reads as the day alone, never "11/10 00:00"
            return "%d/%d" % (int(s[5:7]), int(s[8:10]))
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is not None:
            d = d.astimezone()
        return "%d/%d %02d:%02d" % (d.month, d.day, d.hour, d.minute)
    except ValueError:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
        return "%d/%d" % (int(m.group(2)), int(m.group(3))) if m else ""


def _count(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def status(brain=None):
    """{"spaces": [...], "line": <the recap's one line>}. Each space: name, label, kind, carrier, registered, the counts
    of what this brain shared with it, and when it last went."""
    brain = brain_root(brain)
    rows = []
    for sp in spaces(brain):
        s = sent(brain, sp)
        last = _last_sent(brain, sp)
        rows.append({"name": sp["name"], "label": sp["label"], "shown": sp.get("shown") or sp["label"], "kind": sp["kind"], "carrier": sp["carrier"],
                     "registered": sp["registered"], "page": sp["page"], "members": sp["members"],
                     "to": {"tasks": len(s["items"]), "threads": len(s["threads"])}, "last_sent": last,
                     "counts": dict({"tasks": sum(1 for x in s["items"] if str(x["id"]).startswith("T-")),
                                     "questions": sum(1 for x in s["items"] if str(x["id"]).startswith("Q-")),
                                     "threads": len(s["threads"])}, **_kind_counts(brain, sp)),
                     "state": sp.get("state") or "attached", "left": sp.get("left"),
                     "from": _waiting_from(brain, sp) if sp["carrier"] == "service" else {},
                     "held": _held_back(brain, sp) if sp["carrier"] == "service" else 0,
                     "here": _here(brain, sp)[0], "host_name": _here(brain, sp)[1],
                     "unread": _unread(brain, sp) if sp["carrier"] == "service" else 0})
    if not rows:
        line = "Sharing: nobody attached"
    else:
        parts = []
        for r in rows:
            if r["state"] == "detached":
                parts.append("%s (stopped sharing%s)" % (r["label"], (" on " + _when(r["left"])) if r.get("left") else ""))
                continue
            bits = [_count(n, w) for n, w in ((r["counts"]["tasks"], "task"), (r["counts"]["questions"], "question"),
                                              (r["counts"]["threads"], "thread"), (r["counts"]["files"], "file"),
                                              (r["counts"]["drawings"], "drawing"), (r["counts"]["sections"], "card section")) if n]
            what = (", ".join(bits[:-1]) + " and " + bits[-1]) if len(bits) > 1 else (bits[0] if bits else "")
            if r["kind"] == "team":
                what = ("%s shared with %s" % (what, r["label"])) if what else "nothing shared with %s" % r["label"]
            else:
                what = ("%s on %s's Today" % (what, r["label"])) if what else "nothing on %s's Today" % r["label"]
            waits = sum((r.get("from") or {}).values())
            parts.append("%s (%s%s%s%s%s)" % (r.get("shown") or r["label"], what,
                                            ("; %d waiting from %s" % (waits, r["label"])) if waits else "",
                                            ("; %s held back" % _count(r["held"], "change")) if r.get("held") else "",
                                            ("; last sent %s" % _when(r["last_sent"])) if r["last_sent"] else "",
                                            "" if r["registered"] else "; not registered yet, run init"))
        line = "Sharing: " + "; ".join(parts)
    return {"spaces": rows, "line": line}


# ---------------------------------------------------------------- verify

def verify(brain=None):
    """A list of discrepancies, empty when the register is clean."""
    brain = brain_root(brain)
    have, bad = registered(brain)
    out = list(bad)
    reg = _read_json(_p(brain, REGISTRY_REL))
    reg_ids = {h.get("id") for h in (reg or {}).get("holons", [])} if isinstance(reg, dict) else None
    ledgers = {h.get("id"): h.get("tasks") for h in (reg or {}).get("holons", []) if h.get("tasks")} if isinstance(reg, dict) else {}
    for sp in derived(brain, have):
        out.append("%s: this brain shares with %s through its team copy and no %s/%s/%s says so (run init)"
                   % (sp["name"], sp["label"], SHARED_DIR, sp["name"], STAMP))
    for sp in have:
        tag = "%s/%s/" % (SHARED_DIR, sp["name"])
        if len(sp["members"]) < (1 if sp["carrier"] == "service" and sp["kind"] == "team" else 2):
            out.append("%s: fewer than two members" % tag)
        if sp["me"] not in [m["name"] for m in sp["members"]]:
            out.append("%s: this brain's own person (%s) is not among its members" % (tag, sp["me"]))
        if not os.path.isfile(_p(brain, tag + "readme.md")):
            out.append("%s: no readme.md saying who sees this folder" % tag)
        if reg_ids is not None and ("shared-" + sp["name"]) not in reg_ids:
            out.append("%s: no registry row shared-%s in %s" % (tag, sp["name"], REGISTRY_REL))
        if sp["carrier"] == "service":
            if not sp.get("space_id"):
                out.append("%s: shared through sharing, and its record names no space there" % tag)
            if sp.get("state") not in ("attached", "detached"):
                out.append("%s: its state is %r, not attached or detached" % (tag, sp.get("state")))
            if sp.get("state") == "detached" and not sp.get("left"):
                out.append("%s: detached with no date it was left" % tag)
            if not os.path.isfile(_p(brain, sp["list"])):
                if _here(brain, sp)[0] is not False:          # only the computer that keeps it makes its list
                    out.append("%s: its own list %s is missing" % (tag, sp["list"]))
            elif reg_ids is not None and ledgers.get("shared-" + sp["name"]) != sp["list"]:
                out.append("%s: the registry row shared-%s does not name %s as its tasks" % (tag, sp["name"], sp["list"]))
            if not os.path.isfile(_p(brain, sp["sent"])):
                out.append("%s: %s is missing" % (tag, sp["sent"]))
            stp = _p(brain, "%s/%s/.sync/state.json" % (SHARED_DIR, sp["name"]))
            if os.path.isfile(stp) and _read_json(stp) is None:
                out.append("%s: its record of what was shared does not read as JSON" % tag)
        if sp["carrier"] == "team-copy":
            st = _read_json(_p(brain, TEAM_STATUS_REL))
            if not isinstance(st, dict):
                out.append("%s: its carrier is the team copy and %s is missing" % (tag, TEAM_STATUS_REL))
            elif _slug(st.get("member")) != sp["carrier_member"]:
                out.append("%s: its carrier member is %s and %s names %s" % (tag, sp["carrier_member"], TEAM_STATUS_REL, st.get("member")))
        raw = _read_json(_p(brain, sp["sent"]))
        if raw is None and os.path.isfile(_p(brain, sp["sent"])):
            out.append("%s: %s does not read as JSON" % (tag, sp["sent"]))
        s = sent(brain, sp)
        for x in s["items"]:
            led = ledgers.get(x["project"]) or x.get("ledger")
            path = _p(brain, led) if led else None
            if not path or not os.path.isfile(path):
                out.append("%s: shared item %s/%s is on a list this brain does not have" % (tag, x["project"], x["id"]))
                continue
            try:
                text = open(path, "r", encoding="utf-8").read()
            except OSError:
                text = ""
            if not re.search(r"(?m)^- \[.\] %s " % re.escape(x["id"]), text):
                out.append("%s: shared item %s/%s is no longer on its list" % (tag, x["project"], x["id"]))
        for x in s["threads"]:
            if not os.path.isfile(_p(brain, x["path"])):
                out.append("%s: shared thread %s is no longer a file" % (tag, x["path"]))
    return out


# ---------------------------------------------------------------- init (the one write)

SHARED_README = """# shared/ : the spaces this brain shares

**Created:** {today} by `skills/sharing/share.py init` (viewer 0.109.0). Spec: [[skills/sharing/readme.md]].

**What's in here.** One folder per shared space this brain is attached to. A shared space is a place two or more people hold together: two people are a pair, three or more are a team brain. Each folder holds the space's stamp (`space.json`, contract `shared-space/1`: who is in it, what carries it, where the list of what was shared lives) and a readme that says who sees what is in that folder.

**Authoritative for:** who this brain shares with. The viewer's Share press, its Settings page, the ledger tool's `shared` facet and the session recap all read it through `skills/sharing/share.py`.
**NOT authoritative for:** what a team copy receives by tier (that is the registry's `sharing` entry and `skills/team-brain/`), or anything about a person (their card).

**When to read.** Before writing into a space's folder: its readme names everyone who will see what you write. When asked who something is shared with: `python skills/sharing/share.py shared`.
**When NOT to read.** For the content of a team copy; it lives outside the brain.

**What does NOT belong here.** Anything private to this brain. A key file, a token, a line marked `[private]`, the personal folders. A space's folder is read by everyone in the space.

**Naming.** `shared/<name>/`, the partner's short name for a pair, the team's for a team brain; lowercase letters, digits and hyphens.

**Last touched:** {today}, created.
"""

SHARED_CONTRACT = {
    "authority": "canonical",
    "description": "The spaces this brain shares, one folder each, written by skills/sharing/share.py. A space's folder is read by every member of the space, so nothing private to this brain is ever written into one: no key file, no token, no line marked [private], none of the personal folders.",
    "belongs": [],
    "never": [
        {"glob": "*_key.txt", "reason": "A key file never crosses and never sits in a shared space", "home": "brain root"},
        {"glob": "*token*.txt", "reason": "A token never crosses and never sits in a shared space", "home": "brain root"},
        {"glob": "*-profile.md", "reason": "A profile of a person is this brain's own read and never sits in a shared space", "home": "profiles/"}
    ],
    "applies_to_subfolders": True
}

SPACE_README = """# shared/{name}/ : shared with {label}

**Written by** `skills/sharing/share.py` on {today}. Do not edit by hand; the stamp beside it (`space.json`) is the record.

**Who sees what is in this folder:** {people}. Anything written here is written for them.

**What carries it:** {carrier_words}

**What is shared with {label} today:** `python skills/sharing/share.py shared` lists every task and thread, read from `{sent}`.

**What does NOT belong here.** Anything private to this brain: a key file, a token, a line marked `[private]`, the personal folders, an employer's own work.
"""

CARRIER_WORDS = {
    "team-copy": "the team copy on GitHub (`skills/team-brain/` on this side, `skills/team-sync/` on theirs). What goes is decided by the sharing tiers in the registry, the held-back list and the Share press, and every file passes the export's gate.",
    "service": "the sharing service. What goes is decided by the Share press, and everything passes the gate on this computer first.",
}


def _log(brain, action, text):
    tool = _p(brain, LOG_REL)
    if not os.path.isfile(tool):
        tool = os.path.join(DEFAULT_BRAIN, *LOG_REL.split("/"))
    try:
        subprocess.run([sys.executable, tool, "--append", "--agent", "sharing", "--action", action, "--text", text],
                       cwd=brain, capture_output=True, text=True, timeout=30, env=dict(os.environ, BRAIN_ROOT=brain))
    except Exception as e:                                     # noqa: BLE001 -- a log that fails never stops the write
        sys.stderr.write("log.py failed: %s\n" % e)


def _registry_rows(brain, names_labels):
    """Add the `shared` family row and one `space` row per name when missing. The file keeps its own formatting
    (two-space JSON). Returns the ids added."""
    path = _p(brain, REGISTRY_REL)
    reg = _read_json(path)
    if not isinstance(reg, dict) or not isinstance(reg.get("holons"), list):
        return []
    ids = {h.get("id") for h in reg["holons"]}
    added = []
    if "space" not in (reg.get("types") or []):
        reg.setdefault("types", []).append("space")
    rule = ("space (added 2026-11-09): a holon of type space is a shared space this brain is attached to; "
            "skills/sharing/share.py writes its row and its folder under shared/. Its own sharing stays private: what "
            "crosses into a space is decided by the Share press and the gate, never by a tier")
    if isinstance(reg.get("_rules"), list) and not any(str(r).startswith("space (added") for r in reg["_rules"]):
        reg["_rules"].append(rule)
    if "shared" not in ids:
        reg["holons"].append({"id": "shared", "name": "Shared spaces", "type": "family", "path": SHARED_DIR + "/",
                              "description": "The spaces this brain shares, one folder each (skills/sharing/share.py). "
                                             "A pair is two people, a team brain three or more.",
                              "sharing": "private", "stamped": False, "parent": None, "children": []})
        added.append("shared")
    fam = next(h for h in reg["holons"] if h.get("id") == "shared")
    for name, label, members, carrier in names_labels:
        hid = "shared-" + name
        if hid in ids:
            continue
        reg["holons"].append({"id": hid, "name": "Shared with %s" % label, "type": "space",
                              "path": "%s/%s/" % (SHARED_DIR, name),
                              "description": "The space this brain shares with %s; the stamp space.json says who is in "
                                             "it and what carries it." % label,
                              "members": members, "carrier": carrier, "sharing": "private", "stamped": False,
                              "parent": "shared"})
        fam.setdefault("children", [])
        if hid not in fam["children"]:
            fam["children"].append(hid)
        added.append(hid)
    if added:
        reg["_updated"] = dt.date.today().isoformat()
        _write_json(path, reg)
    return added


def init(brain=None):
    """Write down every space found unregistered: its folder, stamp, readme and registry row; and the shared/ folder's
    own readme and contract when missing. Returns the lines that say what was written."""
    brain = brain_root(brain)
    today = dt.date.today().isoformat()
    said = []
    root = _p(brain, SHARED_DIR)
    have, _bad = registered(brain)
    todo = derived(brain, have)
    if not have and not todo:
        return ["nothing to register: this brain shares with nobody"]
    if not os.path.isfile(os.path.join(root, "readme.md")):
        _write_text(os.path.join(root, "readme.md"), SHARED_README.format(today=today))
        said.append("wrote %s/readme.md" % SHARED_DIR)
    if not os.path.isfile(os.path.join(root, ".contract.json")):
        _write_json(os.path.join(root, ".contract.json"), SHARED_CONTRACT)
        said.append("wrote %s/.contract.json" % SHARED_DIR)
    for sp in todo:
        folder = os.path.join(root, sp["name"])
        stamp = {"contract": CONTRACT, "name": sp["name"], "label": sp["label"], "kind": sp["kind"], "me": sp["me"],
                 "members": sp["members"], "carrier": sp["carrier"], "carrier_member": sp["carrier_member"],
                 "sent": sp["sent"], "page": sp["page"], "joined": sp["joined"] or today, "state": "attached",
                 "_about": "The stamp of one shared space (skills/sharing/readme.md). carrier team-copy: it rides the "
                           "team copy on GitHub, and `sent` is the file the export reads for what was put on the "
                           "member's Today.",
                 "_written": today}
        _write_json(os.path.join(folder, STAMP), stamp)
        people = ", ".join(label_for(m["name"]) for m in sp["members"])
        _write_text(os.path.join(folder, "readme.md"), SPACE_README.format(
            name=sp["name"], label=sp["label"], today=today, people=people,
            carrier_words=CARRIER_WORDS[sp["carrier"]], sent=sp["sent"]))
        said.append("registered %s/%s/ (%s, carried by the %s)" % (SHARED_DIR, sp["name"], sp["label"],
                                                                   "team copy" if sp["carrier"] == "team-copy" else "service"))
    now, _ = registered(brain)
    added = _registry_rows(brain, [(s["name"], s["label"], [m["name"] for m in s["members"]], s["carrier"]) for s in now])
    if added:
        said.append("registry rows added: %s" % ", ".join(added))
    if said:
        _log(brain, "CREATED", "%s/ -- the sharing register written by skills/sharing/share.py init: %s" % (SHARED_DIR, "; ".join(said)))
    return said or ["nothing to write: every space is registered"]


# ---------------------------------------------------------------- command line

# ---------------------------------------------------------------- round two: the service verbs

SERVICE_VERBS = ["signin", "signout", "whoami", "invite", "invites", "accept", "detach", "team", "share", "takeback",
                 "sync", "client", "move", "move-here", "share-file", "share-thread", "share-drawing", "share-section",
                 "takeback-thing", "proposals", "take-section", "leave-section", "message", "messages", "space", "auto-take"]


_ENGINE = {"mod": None}
_ENGINE_LOCK = threading.Lock()


def engine():
    """skills/sharing/engine.py, loaded by path on first use (the register itself never needs it). Loaded under a lock
    and published only once it has run, so a second thread never gets a half-loaded engine."""
    if _ENGINE["mod"] is not None:
        return _ENGINE["mod"]
    with _ENGINE_LOCK:
        if _ENGINE["mod"] is None:
            import importlib.util
            name = "sharing_engine_mod"
            spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "engine.py"))
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            sys.modules[name] = m
            _ENGINE["mod"] = m
    return _ENGINE["mod"]


def _say(a, ok, line, extra=None):
    if a.json:
        print(json.dumps(dict(extra or {}, ok=bool(ok), line=line), indent=1, ensure_ascii=False))
    else:
        print(line)
    return 0 if ok else 1


def service_main(a, brain):
    """The round-two verbs. Each prints one or a few plain lines (or JSON with --json); none prints a token."""
    eng = engine()
    v = a.action
    if v == "signin":
        if not a.email:
            return _say(a, False, "Say the email address to sign in with.")
        ok, line = eng.sign_in_finish(brain, a.email, a.code) if a.code else eng.sign_in_start(brain, a.email)
        return _say(a, ok, line)
    if v == "signout":
        ok, line = eng.sign_out(brain)
        return _say(a, ok, line)
    if v == "whoami":
        w = eng.whoami(brain)
        return _say(a, True, w["line"], {k: w[k] for k in ("signed_in", "email", "display")})
    if v == "invite":
        if not a.email or not a.name:
            return _say(a, False, "Say the person's name and email address.")
        r = eng.invite(brain, a.email, a.name, card=a.card, team=a.team)
        if r.get("ok") and not a.json:
            print(r["line"])
            print("")
            print(r["text"])
            return 0
        return _say(a, r.get("ok"), r["line"], {k: r.get(k) for k in ("code", "text", "space")})
    if v == "invites":
        r = eng.invites(brain)
        if r.get("ok") and not a.json and r.get("invites"):
            for i in r["invites"]:
                print("%s invited you to %s  (accept --invite %s)" % (
                    i.get("from_display") or "Someone",
                    "share" if i.get("space_kind") == "pair" else "the team brain %s" % i.get("space_label"), i["id"]))
            return 0
        return _say(a, r.get("ok"), r["line"], {"invites": r.get("invites") or []})
    if v == "accept":
        r = eng.accept(brain, invite_id=a.invite, code=a.code)
        return _say(a, r.get("ok"), r["line"], {"space": r.get("space")})
    if v == "detach":
        r = eng.detach(brain, a.space or "")
        return _say(a, r.get("ok"), r["line"])
    if v in ("move", "move-here"):
        r = eng.move_here(brain, a.space or "")
        return _say(a, r.get("ok"), r["line"])
    if v in ("share-file", "share-thread", "share-drawing"):
        if not (a.space and a.path):
            return _say(a, False, "Say the space and the file: --space, --path.")
        fn = {"share-file": eng.share_file, "share-thread": eng.share_thread, "share-drawing": eng.share_drawing}[v]
        ok, line = fn(brain, a.space, a.path)
        return _say(a, ok, line)
    if v == "share-section":
        if not (a.space and a.card and a.heading):
            return _say(a, False, "Say the space, the card and the heading: --space, --card, --heading.")
        ok, line = eng.share_card_section(brain, a.space, a.card, a.heading)
        return _say(a, ok, line)
    if v == "takeback-thing":
        if not (a.space and a.kind and a.key):
            return _say(a, False, "Say the space, the kind and what to take back: --space, --kind, --key.")
        ok, line = eng.take_back_thing(brain, a.space, a.kind, a.key)
        return _say(a, ok, line)
    if v == "proposals":
        rows = eng.proposals(brain)
        if a.json:
            print(json.dumps(rows, indent=1, ensure_ascii=False))
            return 0
        if not rows:
            print("No sections are waiting.")
        for r in rows:
            print("%s sent \u201c%s\u201d for %s's card  (take-section --id %s)" % (r["from"], r["heading"], r["person"], r["id"]))
        return 0
    if v in ("take-section", "leave-section"):
        if not a.id:
            return _say(a, False, "Say which proposal: --id.")
        ok, line = (eng.take_section if v == "take-section" else eng.leave_section)(brain, a.id)
        return _say(a, ok, line)
    if v == "message":
        if not (a.space and a.text):
            return _say(a, False, "Say the space and the words: --space, --text.")
        ok, line = eng.send_message(brain, a.space, a.text)
        return _say(a, ok, line)
    if v == "messages":
        rows = eng.messages(brain, a.space or "")
        if a.json:
            print(json.dumps(rows, indent=1, ensure_ascii=False))
            return 0
        if not rows:
            print("No messages yet.")
        for m in rows:
            print("%s, %s: %s" % (m.get("from") or "Someone", _when(m.get("at")), m.get("text")))
        return 0
    if v == "space":
        view = eng.space_view(brain, a.space or "")
        if view is None:
            return _say(a, False, "You do not share with anyone named %s." % (a.space or ""))
        if a.json:
            print(json.dumps(view, indent=1, ensure_ascii=False))
            return 0
        print("%s: %d shared from here, %d from them, %d made here, %d waiting for you, %d unread" % (
            view["label"], len(view["shared"]), len(view["from_them"]), len(view["made_here"]), len(view["proposals"]), view["unread"]))
        return 0
    if v == "auto-take":
        if a.on == a.off or not a.space:
            return _say(a, False, "Say the space and --on or --off.")
        ok, line = eng.set_auto_take(brain, a.space, bool(a.on))
        return _say(a, ok, line)
    if v == "team":
        r = eng.make_team(brain, a.name or "", a.label or a.name or "")
        return _say(a, r.get("ok"), r["line"], {"space": r.get("space")})
    if v in ("share", "takeback"):
        if not (a.space and a.project and a.id):
            return _say(a, False, "Say the space, the list and the item: --space, --project, --id.")
        fn = eng.share_item if v == "share" else eng.take_back
        ok, line = fn(brain, a.space, a.project, a.id)
        return _say(a, ok, line)
    if v == "sync":
        r = eng.sync(brain, on_purpose=a.on_purpose)
        if a.json:
            print(json.dumps(r, indent=1, ensure_ascii=False))
            return 0 if r.get("ok") else 1
        print(r["line"])
        for sp in r.get("spaces") or []:
            for prob in sp.get("problems") or []:
                print("  " + prob)
        return 0 if r.get("ok") else 1
    if v == "client":
        if a.on == a.off:
            return _say(a, False, "Say --on or --off.")
        ok, line = eng.set_client(brain, bool(a.on), client=a.client, date=a.date)
        return _say(a, ok, line)
    return _say(a, False, "Unknown verb.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="the sharing register: who this brain shares with, and what (skills/sharing/readme.md)")
    ap.add_argument("action", choices=["list", "status", "shared", "verify", "init"] + SERVICE_VERBS)
    ap.add_argument("--brain", help="the brain folder (default BRAIN_ROOT, else the brain this file sits in)")
    ap.add_argument("--json", action="store_true", help="print JSON (list, status, shared and every service verb)")
    ap.add_argument("--email"); ap.add_argument("--code"); ap.add_argument("--name"); ap.add_argument("--label")
    ap.add_argument("--card", help="on invite: the partner's people/ card, when they have one")
    ap.add_argument("--team", help="on invite: the team brain to invite into")
    ap.add_argument("--invite", help="on accept: the invitation's id, from invites")
    ap.add_argument("--space"); ap.add_argument("--project"); ap.add_argument("--id")
    ap.add_argument("--path", help="on share-file / share-thread / share-drawing: the brain-relative file")
    ap.add_argument("--heading", help="on share-section: the card's ## or ### heading"); ap.add_argument("--kind")
    ap.add_argument("--key", help="on takeback-thing: the path, or card#heading"); ap.add_argument("--text")
    ap.add_argument("--on-purpose", dest="on_purpose", action="store_true", help="on sync: a press, not the background")
    ap.add_argument("--on", action="store_true"); ap.add_argument("--off", action="store_true")
    ap.add_argument("--client", help="on client --on: the client who agreed in writing"); ap.add_argument("--date")
    a = ap.parse_args(argv)
    brain = brain_root(a.brain)
    if a.action in SERVICE_VERBS:
        return service_main(a, brain)
    if a.action == "list":
        sps = spaces(brain)
        if a.json:
            print(json.dumps(sps, indent=1, ensure_ascii=False))
        elif not sps:
            print("nobody attached")
        else:
            for s in sps:
                print("%-14s %s · %s · through %s%s" % (
                    s["name"], s["label"], "a pair" if s["kind"] == "pair" else "a team brain",
                    "the team copy" if s["carrier"] == "team-copy" else "sharing",
                    "" if s["registered"] else " · not registered yet (run init)"))
        return 0
    if a.action == "status":
        st = status(brain)
        if a.json:
            print(json.dumps(st, indent=1, ensure_ascii=False))
        else:
            print(st["line"])
        return 0
    if a.action == "shared":
        idx = shared_index(brain)
        if a.json:
            print(json.dumps(idx, indent=1, ensure_ascii=False))
        else:
            lab = idx["labels"]
            rows = [("task  " + k, v) for k, v in sorted(idx["items"].items())] + [("thread " + k, v) for k, v in sorted(idx["threads"].items())]
            if not rows:
                print("nothing shared")
            for what, names in rows:
                print("%s  ->  %s" % (what, ", ".join(lab.get(n, n) for n in names)))
        return 0
    if a.action == "verify":
        found = verify(brain)
        if not found:
            print("CLEAN")
            return 0
        for line in found:
            print(line)
        return 1
    for line in init(brain):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
