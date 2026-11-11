#!/usr/bin/env python3
"""skills/sharing/service.py -- the sharing service adapter: one interface, two carriers behind it.

    open_service(brain)          the carrier the config names, or raises NotSetUp
    LocalService(root)           a folder that stands in for the service (tests; two brains on one computer)
    SupabaseService(url, key)    the hosted service, over HTTPS with urllib

Every method but the two sign-in calls takes the session dict first. A failure raises ServiceError with words a person
can read; Conflict (a version clash on put_thing) and SignedOut (the sign-in ended; refresh once and retry) are its
subclasses. No method ever puts a token in a message, a log line or a file other than the caller's own.

The rules LocalService enforces in Python are the ones the service's SQL enforces in the database: only an allowed
email signs in (the first email ever seen is allowed, and an invitation allows its email); a person reads and writes
only spaces they are an active member of; only a thing's home rewrites it, others add acts; a thing made in the space
(home null) is rewritten by any member against its version; an act's space and home come from its thing; only the home
marks an act; a pair holds two people; a team's maker adds and removes people.

Standard library only. Spec: skills/sharing/readme.md, Round two.
"""
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE_JSON = "skills/sharing/service.json"
SETTINGS_REL = "viewer/settings.json"
USER_AGENT = "brain-viewer-sharing/2 (python urllib)"
TIMEOUT = 20
CODE_TTL = 600          # a sign-in code lasts ten minutes
SESSION_TTL = 3600      # a session lasts an hour, then refresh
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class NotSetUp(Exception):
    """The service is not set up on this computer (no address or key)."""


class ServiceError(Exception):
    """A call the service refused or could not answer, in words a person can read."""


class Conflict(ServiceError):
    """put_thing found the thing at another version than the one the caller last saw."""


class SignedOut(ServiceError):
    """The sign-in has ended (401). The caller refreshes once and tries again."""


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _iso(d=None):
    return (d or _now()).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def config(brain):
    """The service's address: the brain's own `sharing_service` setting, else skills/sharing/service.json (the brain's
    copy, else the one beside this file)."""
    st = _read_json(os.path.join(brain, *SETTINGS_REL.split("/")))
    if isinstance(st, dict) and isinstance(st.get("sharing_service"), dict):
        return dict(st["sharing_service"])
    for p in (os.path.join(brain, *SERVICE_JSON.split("/")), os.path.join(HERE, "service.json")):
        d = _read_json(p)
        if isinstance(d, dict):
            return {k: v for k, v in d.items() if not k.startswith("_")}
    return {}


def open_service(brain):
    cfg = config(brain)
    carrier = str(cfg.get("carrier") or "supabase")
    if carrier == "local":
        root = str(cfg.get("root") or "").strip()
        if not root:
            raise NotSetUp("Sharing is not set up on this computer yet.")
        return LocalService(root)
    url, key = str(cfg.get("url") or "").strip(), str(cfg.get("key") or "").strip()
    if not url or not key:
        raise NotSetUp("Sharing is not set up on this computer yet.")
    return SupabaseService(url, key)


def _norm_email(e):
    return str(e or "").strip().lower()


def _hash(s):
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()


# ================================================================== the stand-in

class LocalService:
    """The service's data in one JSON file under `root`, behind a lock file. Sign-in codes are written to
    <root>/outbox/<email>.txt, where a test reads them. Tokens are kept only as hashes."""

    carrier = "local"

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.url = "local:" + self.root
        self.db_path = os.path.join(self.root, "service-data.json")
        self.lock_path = os.path.join(self.root, "service-data.lock")

    # ---------------------------------------------------------- storage
    def _lock(self):
        os.makedirs(self.root, exist_ok=True)
        t0 = time.time()
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.lock_path) > 30:
                        os.remove(self.lock_path)
                        continue
                except OSError:
                    pass
                if time.time() - t0 > 15:
                    raise ServiceError("Sharing is busy; try again in a moment.")
                time.sleep(0.02)

    def _unlock(self):
        try:
            os.remove(self.lock_path)
        except OSError:
            pass

    def _load(self):
        d = _read_json(self.db_path)
        if not isinstance(d, dict):
            d = {}
        for k, v in (("allowed", {}), ("users", {}), ("codes", {}), ("sessions", {}), ("refresh", {}), ("spaces", {}),
                     ("members", []), ("invites", {}), ("invite_codes", {}), ("things", {}), ("acts", {}), ("seq", 0)):
            d.setdefault(k, v)
        return d

    def _save(self, d):
        tmp = self.db_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.db_path)

    def _tx(self, fn, write=True):
        self._lock()
        try:
            d = self._load()
            out = fn(d)
            if write:
                self._save(d)
            return out
        finally:
            self._unlock()

    # ---------------------------------------------------------- who is asking
    def _who(self, d, session):
        tok = (session or {}).get("access_token")
        if not tok:
            raise SignedOut("Sign in to sharing first.")
        s = d["sessions"].get(_hash(tok))
        if not s or s["expires_at"] < time.time():
            raise SignedOut("This sign-in has ended; sign in again.")
        return s["user_id"], s["email"]

    @staticmethod
    def _member(d, space_id, uid):
        return next((m for m in d["members"] if m["space_id"] == space_id and m["user_id"] == uid and not m["left_at"]), None)

    def _need_member(self, d, space_id, uid):
        m = self._member(d, space_id, uid)
        if not m:
            raise ServiceError("You are not in this shared space.")
        return m

    def _session(self, d, uid, email):
        tok, ref = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        exp = int(time.time()) + SESSION_TTL
        d["sessions"][_hash(tok)] = {"user_id": uid, "email": email, "expires_at": exp}
        d["refresh"][_hash(ref)] = {"user_id": uid, "email": email}
        return {"user_id": uid, "email": email, "access_token": tok, "refresh_token": ref, "expires_at": exp}

    # ---------------------------------------------------------- sign-in
    def start_sign_in(self, email):
        email = _norm_email(email)
        if not EMAIL_RE.match(email):
            raise ServiceError("That does not read as an email address.")

        def go(d):
            if not d["allowed"]:
                d["allowed"][email] = {"added_by": None, "added_at": _iso()}      # the first address, as the owner's is
            if email not in d["allowed"]:
                raise ServiceError("This email has not been invited to share yet. Ask the person you want to share with to add you.")
            code = "%06d" % secrets.randbelow(1000000)
            d["codes"][email] = {"hash": _hash(code), "at": time.time()}
            out = os.path.join(self.root, "outbox")
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, email + ".txt"), "w", encoding="utf-8") as f:
                f.write(code + "\n")
        self._tx(go)

    def finish_sign_in(self, email, code):
        email = _norm_email(email)
        code = re.sub(r"\s", "", str(code or ""))

        def go(d):
            c = d["codes"].get(email)
            if not c or time.time() - c["at"] > CODE_TTL:
                raise ServiceError("That code has ended; ask for a new one.")
            if not re.fullmatch(r"\d{6}", code) or _hash(code) != c["hash"]:
                raise ServiceError("That code is not the one that was sent.")
            del d["codes"][email]
            u = d["users"].get(email)
            if not u:
                u = d["users"][email] = {"id": str(uuid.uuid4()), "email": email}
            return self._session(d, u["id"], email)
        return self._tx(go)

    def refresh(self, session):
        ref = (session or {}).get("refresh_token")

        def go(d):
            r = d["refresh"].pop(_hash(ref), None) if ref else None
            if not r:
                raise SignedOut("This sign-in has ended; sign in again.")
            return self._session(d, r["user_id"], r["email"])
        return self._tx(go)

    # ---------------------------------------------------------- spaces and people
    def _space_out(self, d, sp):
        return {"id": sp["id"], "name": sp["name"], "label": sp["label"], "kind": sp["kind"], "made_by": sp["made_by"],
                "members": [{"user_id": m["user_id"], "name": m["name"], "display": m["display"],
                             "email": m.get("email") or "", "role": m["role"],
                             "left_at": m["left_at"]} for m in d["members"] if m["space_id"] == sp["id"]]}

    def spaces(self, session):
        def go(d):
            uid, _e = self._who(d, session)
            return [self._space_out(d, sp) for sp in d["spaces"].values() if self._member(d, sp["id"], uid)]
        return self._tx(go, write=False)

    def my_acts(self, session):
        """The acts this person made that the home has marked: [{id, space_id, thing_id, act, result, applied_at}]."""
        def go(d):
            uid, _e = self._who(d, session)
            return [{k: a[k] for k in ("id", "space_id", "thing_id", "act", "result", "applied_at")}
                    for a in d["acts"].values() if a["by"] == uid and a["applied_at"]]
        return self._tx(go, write=False)

    def my_memberships(self, session):
        """Every row of this person's own membership, left or not: [{space_id, left_at}] (the proof a space was left)."""
        def go(d):
            uid, _e = self._who(d, session)
            return [{"space_id": m["space_id"], "left_at": m["left_at"], "host": m.get("host"), "host_name": m.get("host_name") or ""}
                    for m in d["members"] if m["user_id"] == uid]
        return self._tx(go, write=False)

    def claim_host(self, session, space_id, host, name, force=False):
        """Which computer of this person's keeps the space in step, decided here and nowhere else: the first to claim it,
        the same one again, or one that claims with force. {host, host_name, mine}."""
        def go(d):
            uid, _e = self._who(d, session)
            m = self._need_member(d, space_id, uid)
            if not str(host or "").strip():
                raise ServiceError("A computer needs an id.")
            if not m.get("host") or m["host"] == host or force:
                m["host"], m["host_name"] = host, name or ""
                return {"host": host, "host_name": name or "", "mine": True}
            return {"host": m["host"], "host_name": m.get("host_name") or "", "mine": False}
        return self._tx(go)

    def make_space(self, session, name, label, kind, my_name, my_display):
        def go(d):
            uid, email = self._who(d, session)
            if email not in d["allowed"]:
                raise ServiceError("This email has not been invited to share.")
            if kind not in ("pair", "team"):
                raise ServiceError("A space is a pair or a team.")
            sid = str(uuid.uuid4())
            sp = {"id": sid, "name": str(name or "").strip() or "space", "label": str(label or "").strip() or "Shared space",
                  "kind": kind, "made_by": uid, "made_at": _iso()}
            d["spaces"][sid] = sp
            d["members"].append({"space_id": sid, "user_id": uid, "name": str(my_name or "").strip() or "me",
                                 "display": my_display or "", "email": email, "role": "maker", "joined_at": _iso(),
                                 "left_at": None})
            return {k: sp[k] for k in ("id", "name", "label", "kind", "made_by")}
        return self._tx(go)

    def invite(self, session, space_id, email, name):
        email = _norm_email(email)

        def go(d):
            uid, my_email = self._who(d, session)
            me = self._need_member(d, space_id, uid)
            if not EMAIL_RE.match(email):
                raise ServiceError("An invitation needs an email address.")
            sp = d["spaces"][space_id]
            ever = [m for m in d["members"] if m["space_id"] == space_id]
            if sp["kind"] == "pair" and len(ever) >= 2:
                raise ServiceError("A pair is two people and this one has had both; start a new one to share with someone else.")
            if sp["kind"] == "team" and me["role"] != "maker":
                raise ServiceError("The team's maker adds people.")
            if sp["kind"] == "pair" and any(i["space_id"] == space_id and not i["accepted_at"] and not i["revoked_at"]
                                            for i in d["invites"].values()):
                raise ServiceError("An invitation to this pair is already waiting; take it back first to invite someone else.")
            code = secrets.token_hex(6).upper()
            iid = str(uuid.uuid4())
            d["invites"][iid] = {"id": iid, "space_id": space_id, "email": email, "name": name or "", "made_by": uid,
                                 "made_at": _iso(), "space_label": sp["label"], "space_kind": sp["kind"],
                                 "from_display": me["display"], "from_email": my_email,
                                 "accepted_at": None, "accepted_by": None, "revoked_at": None}
            d["invite_codes"][iid] = _hash(code)
            d["allowed"].setdefault(email, {"added_by": uid, "added_at": _iso()})
            return {"id": iid, "code": code}
        return self._tx(go)

    def claim_code(self, email, code):
        """An invitation's code, given before signing in, lets the address it is given with sign up: how a person
        invited at one address joins with another. True when the code matched an open invitation."""
        email = _norm_email(email)
        want = _hash(re.sub(r"[\s-]", "", str(code or "")).upper())

        def go(d):
            if not EMAIL_RE.match(email):
                return False
            for iid, h in d["invite_codes"].items():
                i = d["invites"].get(iid)
                if h == want and i and not i["accepted_at"] and not i["revoked_at"]:
                    d["allowed"].setdefault(email, {"added_by": i["made_by"], "added_at": _iso()})
                    return True
            return False
        return self._tx(go)

    def invites(self, session):
        def go(d):
            _uid, email = self._who(d, session)
            rows = [i for i in d["invites"].values() if i["email"] == email and not i["accepted_at"] and not i["revoked_at"]]
            rows.sort(key=lambda i: i["made_at"])
            return [dict({k: i[k] for k in ("id", "space_id", "space_label", "space_kind", "from_display", "made_at")},
                         from_email=i.get("from_email") or "") for i in rows]
        return self._tx(go, write=False)

    def revoke_invite(self, session, invite_id):
        def go(d):
            uid, _e = self._who(d, session)
            i = d["invites"].get(invite_id)
            if not i or i["made_by"] != uid or i["accepted_at"] or i["revoked_at"]:
                raise ServiceError("There is no open invitation of yours to take back.")
            i["revoked_at"] = _iso()
        self._tx(go)

    def accept(self, session, invite_id, code, my_name, my_display):
        def go(d):
            uid, email = self._who(d, session)
            i = d["invites"].get(invite_id) if invite_id else None
            ok = bool(i) and i["email"] == email
            if not ok and str(code or "").strip():
                h = _hash(str(code).strip().replace("-", "").upper())
                cands = [d["invites"][k] for k, v in d["invite_codes"].items() if v == h and k in d["invites"]
                         and not d["invites"][k]["accepted_at"] and not d["invites"][k]["revoked_at"]]
                cands.sort(key=lambda x: x["made_at"], reverse=True)
                i = cands[0] if cands else None
                ok = i is not None
            if not ok:
                raise ServiceError("No invitation matches.")
            if i["accepted_at"] or i["revoked_at"]:
                raise ServiceError("This invitation was already used or taken back.")
            sp = d["spaces"][i["space_id"]]
            others = [m for m in d["members"] if m["space_id"] == sp["id"] and m["user_id"] != uid]
            if sp["kind"] == "pair" and len(others) >= 2:
                raise ServiceError("This pair already has its two people.")
            m = next((m for m in d["members"] if m["space_id"] == sp["id"] and m["user_id"] == uid), None)
            if m and m["left_at"]:
                raise ServiceError("You left this space; ask for a new one to share again.")
            if m:
                m.update(name=str(my_name or "").strip() or "me", display=my_display or "", email=email)
            else:
                d["members"].append({"space_id": sp["id"], "user_id": uid, "name": str(my_name or "").strip() or "me",
                                     "display": my_display or "", "email": email, "role": "member", "joined_at": _iso(),
                                     "left_at": None})
            i["accepted_at"], i["accepted_by"] = _iso(), uid
            d["allowed"].setdefault(email, {"added_by": i["made_by"], "added_at": _iso()})
            return {k: sp[k] for k in ("id", "name", "label", "kind", "made_by")}
        return self._tx(go)

    def leave(self, session, space_id):
        def go(d):
            uid, _e = self._who(d, session)
            m = self._need_member(d, space_id, uid)
            m["left_at"] = _iso()
        self._tx(go)

    def remove_member(self, session, space_id, user_id):
        def go(d):
            uid, _e = self._who(d, session)
            me = self._need_member(d, space_id, uid)
            if me["role"] != "maker":
                raise ServiceError("The space's maker removes people.")
            m = self._member(d, space_id, user_id)
            if not m:
                raise ServiceError("That person is not in this space.")
            m["left_at"] = _iso()
        self._tx(go)

    # ---------------------------------------------------------- things and acts
    def heads(self, session, space_id):
        def go(d):
            uid, _e = self._who(d, session)
            self._need_member(d, space_id, uid)
            return [{k: t[k] for k in ("id", "kind", "home", "key", "version", "removed_at")}
                    for t in d["things"].values() if t["space_id"] == space_id]
        return self._tx(go, write=False)

    def get_things(self, session, ids):
        def go(d):
            uid, _e = self._who(d, session)
            out = []
            for i in ids or []:
                t = d["things"].get(i)
                if not t or not self._member(d, t["space_id"], uid):
                    raise ServiceError("A shared thing could not be read.")
                out.append(json.loads(json.dumps(t)))
            return out
        return self._tx(go, write=False)

    def put_thing(self, session, row):
        def go(d):
            uid, _e = self._who(d, session)
            if not row.get("id"):
                self._need_member(d, row.get("space_id"), uid)
                if row.get("home") not in (None, uid):
                    raise ServiceError("A thing can only be shared from its own brain.")
                tid = str(uuid.uuid4())
                t = {"id": tid, "space_id": row["space_id"], "kind": row.get("kind") or "task", "home": row.get("home"),
                     "key": row.get("key") or "", "title": row.get("title") or "", "body": row.get("body") or {},
                     "version": 1, "updated_by": uid, "updated_at": _iso(), "removed_at": row.get("removed_at")}
                if t["home"] is not None and t["key"] and any(
                        x["space_id"] == t["space_id"] and x["home"] == t["home"] and x["key"] == t["key"] for x in d["things"].values()):
                    raise ServiceError("This thing is already shared into this space.")
                d["things"][tid] = t
                return json.loads(json.dumps(t))
            t = d["things"].get(row["id"])
            if not t or not self._member(d, t["space_id"], uid):
                raise ServiceError("You are not in this shared space.")
            if t["home"] not in (None, uid):
                raise ServiceError("Only the person who shared it can change it; others add what they did.")
            if row.get("space_id") not in (None, t["space_id"]) or ("home" in row and row["home"] != t["home"]):
                raise ServiceError("A shared thing keeps its space and its home.")
            if int(row.get("version") or 0) != t["version"]:
                raise Conflict("Someone changed this in the meantime.")
            for k in ("kind", "key", "title", "body", "removed_at"):
                if k in row:
                    t[k] = row[k]
            t["version"] += 1
            t["updated_by"], t["updated_at"] = uid, _iso()
            return json.loads(json.dumps(t))
        return self._tx(go)

    def acts_for(self, session):
        def go(d):
            uid, _e = self._who(d, session)
            rows = [a for a in d["acts"].values() if a["home"] == uid and not a["applied_at"] and self._member(d, a["space_id"], uid)]
            rows.sort(key=lambda a: a["seq"])
            return [{k: a[k] for k in ("id", "space_id", "thing_id", "home", "by", "at", "act", "payload")} for a in rows]
        return self._tx(go, write=False)

    def add_act(self, session, thing_id, act, payload):
        def go(d):
            uid, _e = self._who(d, session)
            t = d["things"].get(thing_id)
            if not t:
                raise ServiceError("No such shared thing.")
            self._need_member(d, t["space_id"], uid)
            d["seq"] += 1
            aid = str(uuid.uuid4())
            d["acts"][aid] = {"id": aid, "space_id": t["space_id"], "thing_id": thing_id, "home": t["home"], "by": uid,
                              "at": _iso(), "seq": d["seq"], "act": str(act), "payload": payload or {},
                              "applied_at": None, "result": None}
            return {"id": aid}
        return self._tx(go)

    def mark_act(self, session, act_id, result, scrub=False):
        """The home marks an act applied or refused; with scrub its payload becomes {} (what it said never crosses)."""
        def go(d):
            uid, _e = self._who(d, session)
            a = d["acts"].get(act_id)
            if not a or a["home"] != uid or not self._member(d, a["space_id"], uid):
                raise ServiceError("Only the person who shared it marks what was done to it.")
            a["applied_at"], a["result"] = _iso(), str(result)
            if scrub:
                a["payload"] = {}
        self._tx(go)

    def read_act(self, session, act_id):
        """One act as its reader sees it: only the person who did it and the thing's home read it (the SQL's acts_read)."""
        def go(d):
            uid, _e = self._who(d, session)
            a = d["acts"].get(act_id)
            if not a or not self._member(d, a["space_id"], uid) or uid not in (a["by"], a["home"]):
                raise ServiceError("That act cannot be read.")
            return {k: a[k] for k in ("id", "space_id", "thing_id", "home", "by", "at", "act", "payload", "result")}
        return self._tx(go, write=False)


# ================================================================== the hosted service

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would carry the sign-in to another address: every one is refused, and nothing is sent there."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ServiceError("Sharing tried to send this somewhere else, so it was stopped.")


class SupabaseService:
    """The project in service.json: the auth API for sign-in, PostgREST for the tables and functions. The table, column
    and argument names are the ones in the service's SQL (brain-viewer-holon/sharing-service/supabase-setup.sql in the
    maintainer brain)."""

    carrier = "supabase"

    def __init__(self, url, key):
        self.url = str(url).strip().rstrip("/")
        self.key = str(key)
        u = urllib.parse.urlsplit(self.url)
        local = u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost")
        if not ((u.scheme == "https" and u.hostname) or local) or u.username or u.password:
            raise NotSetUp("The sharing address must start with https://, so nothing was sent to it.")
        self._opener = urllib.request.build_opener(_NoRedirect)

    def _req(self, method, path, session=None, body=None, query=None, prefer=None):
        if os.environ.get("SHARING_OFFLINE") == "1" and urllib.parse.urlsplit(self.url).hostname not in ("127.0.0.1", "localhost"):
            raise ServiceError("Sharing is switched off for this run.")   # a test run never reaches a real service
        q = ("?" + urllib.parse.urlencode(query, safe="(),.*:")) if query else ""
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.url + path + q, data=data, method=method)
        req.add_header("apikey", self.key)
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if session is not None:
            tok = session.get("access_token")
            if not tok:
                raise SignedOut("Sign in to sharing first.")
            req.add_header("Authorization", "Bearer " + tok)
        if prefer:
            req.add_header("Prefer", prefer)
        try:
            with self._opener.open(req, timeout=TIMEOUT) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read() or b"{}")
            except ValueError:
                err = {}
            msg = ""
            if isinstance(err, dict):
                msg = str(err.get("message") or err.get("msg") or err.get("error_description") or "")
            if e.code == 401:
                raise SignedOut(msg or "This sign-in has ended; sign in again.") from None
            if isinstance(err, dict) and str(err.get("code") or "") == "40001":
                raise Conflict(msg or "Someone changed this in the meantime.") from None
            raise ServiceError(msg or "Sharing answered with an error (%d)." % e.code) from None
        except (urllib.error.URLError, OSError):
            raise ServiceError("Sharing could not be reached.") from None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            raise ServiceError("Sharing answered something that does not read.") from None

    def _rpc(self, session, name, args):
        return self._req("POST", "/rest/v1/rpc/" + name, session, args)

    @staticmethod
    def _session_of(r):
        if not isinstance(r, dict) or not r.get("access_token"):
            raise ServiceError("Sharing did not sign you in.")
        u = r.get("user") or {}
        exp = r.get("expires_at") or (int(time.time()) + int(r.get("expires_in") or SESSION_TTL))
        return {"user_id": u.get("id"), "email": _norm_email(u.get("email")), "access_token": r["access_token"],
                "refresh_token": r.get("refresh_token"), "expires_at": int(exp)}

    def start_sign_in(self, email):
        self._req("POST", "/auth/v1/otp", body={"email": _norm_email(email), "create_user": True})

    def claim_code(self, email, code):
        r = self._req("POST", "/rest/v1/rpc/claim_code", body={"p_code": str(code or ""), "p_email": _norm_email(email)})
        return r is True

    def finish_sign_in(self, email, code):
        r = self._req("POST", "/auth/v1/verify", body={"type": "email", "email": _norm_email(email),
                                                         "token": re.sub(r"\s", "", str(code or ""))})
        return self._session_of(r)

    def refresh(self, session):
        r = self._req("POST", "/auth/v1/token", body={"refresh_token": (session or {}).get("refresh_token")},
                      query={"grant_type": "refresh_token"})
        return self._session_of(r)

    def spaces(self, session):
        rows = self._req("GET", "/rest/v1/spaces", session, query={
            "select": "id,name,label,kind,made_by,members(user_id,name,display,email,role,left_at)"}) or []
        return [{"id": r.get("id"), "name": r.get("name"), "label": r.get("label"), "kind": r.get("kind"),
                 "made_by": r.get("made_by"), "members": list(r.get("members") or [])} for r in rows]

    def my_acts(self, session):
        return self._req("GET", "/rest/v1/acts", session, query={
            "select": "id,space_id,thing_id,act,result,applied_at", "by": "eq." + str(session.get("user_id")),
            "applied_at": "not.is.null"}) or []

    def my_memberships(self, session):
        rows = self._req("GET", "/rest/v1/members", session, query={
            "user_id": "eq." + str(session.get("user_id")), "select": "space_id,left_at,host,host_name"}) or []
        return [{"space_id": r.get("space_id"), "left_at": r.get("left_at"), "host": r.get("host"),
                 "host_name": r.get("host_name") or ""} for r in rows if isinstance(r, dict)]

    def claim_host(self, session, space_id, host, name, force=False):
        r = self._rpc(session, "claim_host", {"p_space": space_id, "p_host": host, "p_name": name, "p_force": bool(force)})
        r = r[0] if isinstance(r, list) and r else (r or {})
        return {"host": r.get("host"), "host_name": r.get("host_name") or "", "mine": r.get("mine") is True}

    def make_space(self, session, name, label, kind, my_name, my_display):
        r = self._rpc(session, "make_space", {"p_name": name, "p_label": label, "p_kind": kind, "p_my_name": my_name,
                                              "p_my_display": my_display})
        return r[0] if isinstance(r, list) and r else r

    def invite(self, session, space_id, email, name):
        r = self._rpc(session, "invite", {"p_space": space_id, "p_email": _norm_email(email), "p_name": name})
        row = r[0] if isinstance(r, list) and r else (r or {})
        return {"id": row.get("invite_id"), "code": row.get("code")}

    def invites(self, session):
        return self._req("GET", "/rest/v1/invites", session, query={
            "select": "id,space_id,space_label,space_kind,from_display,from_email,made_at",
            "email": "eq." + _norm_email(session.get("email")), "accepted_at": "is.null", "revoked_at": "is.null",
            "order": "made_at.asc"}) or []

    def revoke_invite(self, session, invite_id):
        self._rpc(session, "revoke_invite", {"p_invite": invite_id})

    def accept(self, session, invite_id, code, my_name, my_display):
        r = self._rpc(session, "accept_invite", {"p_invite": invite_id, "p_code": code, "p_my_name": my_name,
                                                 "p_my_display": my_display})
        return r[0] if isinstance(r, list) and r else r

    def leave(self, session, space_id):
        self._rpc(session, "leave_space", {"p_space": space_id})

    def remove_member(self, session, space_id, user_id):
        self._rpc(session, "remove_member", {"p_space": space_id, "p_user": user_id})

    def heads(self, session, space_id):
        if not self._req("GET", "/rest/v1/spaces", session, query={"select": "id", "id": "eq." + str(space_id)}):
            raise ServiceError("You are not in this shared space.")
        return self._req("GET", "/rest/v1/things", session, query={
            "select": "id,kind,home,key,version,removed_at", "space_id": "eq." + str(space_id)}) or []

    def get_things(self, session, ids):
        ids = [str(i) for i in ids or []]
        if not ids:
            return []
        rows = self._req("GET", "/rest/v1/things", session, query={"select": "*", "id": "in.(%s)" % ",".join(ids)}) or []
        if len(rows) != len(set(ids)):
            raise ServiceError("A shared thing could not be read.")
        by = {r["id"]: r for r in rows}
        return [by[i] for i in ids]

    def put_thing(self, session, row):
        if not row.get("id"):
            body = {k: row.get(k) for k in ("space_id", "kind", "home", "key", "title", "body", "removed_at")}
            r = self._req("POST", "/rest/v1/things", session, body, prefer="return=representation")
            return r[0] if isinstance(r, list) and r else r
        v = int(row.get("version") or 0)
        body = {k: row[k] for k in ("kind", "key", "title", "body", "removed_at") if k in row}
        body["version"] = v + 1
        r = self._req("PATCH", "/rest/v1/things", session, body, prefer="return=representation",
                      query={"id": "eq." + str(row["id"]), "version": "eq.%d" % v})
        if not r:
            raise Conflict("Someone changed this in the meantime.")
        return r[0]

    def acts_for(self, session):
        return self._req("GET", "/rest/v1/acts", session, query={
            "select": "id,space_id,thing_id,home,by,at,act,payload", "home": "eq." + str(session.get("user_id")),
            "applied_at": "is.null", "order": "at.asc"}) or []

    def add_act(self, session, thing_id, act, payload):
        r = self._req("POST", "/rest/v1/acts", session, {"thing_id": thing_id, "act": act, "payload": payload or {},
                                                          "by": session.get("user_id")}, prefer="return=representation")
        row = r[0] if isinstance(r, list) and r else (r or {})
        return {"id": row.get("id")}

    def mark_act(self, session, act_id, result, scrub=False):
        body = {"applied_at": _iso(), "result": str(result)}
        if scrub:
            body["payload"] = {}
        r = self._req("PATCH", "/rest/v1/acts", session, body,
                      prefer="return=representation", query={"id": "eq." + str(act_id)})
        if not r:
            raise ServiceError("Only the person who shared it marks what was done to it.")
