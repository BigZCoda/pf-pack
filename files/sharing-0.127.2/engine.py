#!/usr/bin/env python3
"""skills/sharing/engine.py -- the sync engine for spaces the sharing service carries.

    sync(brain, on_purpose=False, only=None)              send what this brain shares, take in what others share,
                                                          carry acts both ways; {ok, reason, spaces, line}
    share_item(brain, space_name, project, item_id)       the gate, the row in sent.json, a sync; (ok, line)
    take_back(brain, space_name, project, item_id)        the row out, the thing marked removed, a sync; (ok, line)
    sign_in_start / sign_in_finish / sign_out / whoami    the sign-in, kept in viewer/sharing-signin.json
    invite / invites / accept / detach / make_team        attaching and detaching
    set_client(brain, on, client=None, date=None)         the client-computer switch

Every ledger write goes through skills/brain-tasks/tasks.py apply (or init), loaded once per brain with that brain as
its BRAIN_ROOT, so one process can drive several brains. Nothing here sleeps or loops: the caller decides when to sync.
A sign-in token never reaches a message, a log line, a space or any file but the sign-in file. What comes from the
service (a name, a label, a body, what someone did) is cleaned where it arrives, and its words never reach a log line.
The sync state is written after every thing and every act, so a sync stopped half way is picked up where it stopped.

Standard library only. Spec: skills/sharing/readme.md, Round two.
"""
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import secrets
import sys
import threading
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))


_LOAD_LOCK = threading.RLock()


def _load(name, path):
    """A sibling file as a module, under a lock, published in sys.modules only once it has run."""
    with _LOAD_LOCK:
        if name in sys.modules:
            return sys.modules[name]
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        sys.modules[name] = m
        return m


service = _load("sharing_service_mod", os.path.join(HERE, "service.py"))
gate = _load("sharing_gate_mod", os.path.join(HERE, "gate.py"))
share = _load("sharing_share_mod", os.path.join(HERE, "share.py"))

SIGNIN_REL = "viewer/sharing-signin.json"
SETTINGS_REL = "viewer/settings.json"
# 2026-11-11: on a computer an employer owns, what is shared with this person arrives and can be answered; only what
# they share out of their own brain waits for the employer's written yes, and after the yes it goes on a press
OFF_LINE = "Sharing something of your own from this computer waits until your employer agrees in writing."
PRESS_LINE = "On this computer, what you shared goes when you press Check for what was shared."
IN_LINE = ("What is shared with you arrives here and you can answer it. Sharing something of your own waits until your "
           "employer agrees in writing.")
UNREAD_LINE = "Sharing is off: this computer's settings file does not read."
REAL_BRAIN_LINE = "This is a real brain. Sharing tests run on stand-in brains, never on this one."
NOT_SIGNED_IN = "Nobody is signed in to sharing on this computer."
OTHER_SERVICE = "This sign-in belongs to another sharing address; sign in again."
OFFLINE = "Sharing could not be reached, so nothing changed. Try again when this computer is online."
AGENT = "sharing"
FIELDS = ("text", "steps", "note", "due", "state", "answer", "options")
STEP_CHARS, STEPS_MAX = 200, 12
EMAIL_RE = re.compile(r"^[a-z0-9._%+-]{1,64}@[a-z0-9.-]{1,100}\.[a-z]{2,24}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# the results an act is marked with: a fixed set of phrases, so no exception text ever leaves this computer
R_APPLIED = "applied"
R_GONE = "refused: it is no longer shared"
R_OFF_LIST = "refused: it is no longer on its list"
R_STRANGER = "refused: the person is not in this space"
R_NO_STEP = "refused: that step is not on it"
R_NOT_THEIRS = "refused: it is not theirs to close"
R_NOT_ASKED = "refused: it was not asked of them"
R_ANSWERED = "refused: it was already answered"
R_EMPTY = "refused: it is empty"
R_NEVER = "refused: it holds something that never crosses"
R_NOT_Q = "refused: it is not a question"
R_Q_DONE = "refused: a question is answered, not closed"
R_UNKNOWN = "refused: it cannot be done from a shared copy"


class Refused(Exception):
    """A verb that cannot go ahead, in one plain line."""


class _Unplaced(Exception):
    """An act on a thing this brain cannot place yet (its state was lost and not rebuilt); tried again next time."""


class _WriteFailed(Exception):
    """A ledger write here did not happen (the list does not read, a lock, the disk); tried again next sync."""


# ---------------------------------------------------------------- small helpers

def _p(brain, rel):
    return os.path.join(brain, *str(rel).split("/"))


def _today():
    return dt.date.today().isoformat()


def _md(day=None):
    d = dt.date.fromisoformat(day) if day else dt.date.today()
    return "%d/%d" % (d.month, d.day)


def _slug(s):
    """A slug for a card or a folder: accents dropped ("Renée" gives renee), anything not a-z0-9 becomes a hyphen."""
    s = "".join(ch for ch in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.category(ch).startswith("M"))
    s = re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")
    return s[:40].strip("-")


def _name_slug(name, email=None):
    """The slug of a person's name; a name with no Latin letters takes the part of the address before the @, else
    `partner`."""
    return _slug(name) or _slug(str(email or "").split("@")[0]) or "partner"


def _bare(o):
    return str(o or "").strip().lstrip("@").lower()


def clean_name(s, fallback=""):
    """A name or label from outside, as it may be written anywhere here: no control or format characters, no line
    breaks, only letters (any language), digits, spaces and . ' -; whitespace collapsed; at most 60 characters; never
    empty (the fallback, cleaned the same way, else "Someone")."""
    def one(x):
        x = unicodedata.normalize("NFC", str(x or ""))
        x = "".join(ch for ch in x if not unicodedata.category(ch).startswith("C"))
        keep = lambda ch: unicodedata.category(ch)[0] in "LM" or unicodedata.category(ch) == "Nd" or ch in " .'’-"
        x = " ".join("".join(ch if keep(ch) else " " for ch in x).split())
        if len(x) > 60:                                       # never cut a letter from its accent
            x = x[:60]
            while x and unicodedata.category(x[-1]).startswith("M"):
                x = x[:-1]
        return x.strip()
    return one(s) or one(fallback) or "Someone"


def clean_email(e):
    e = str(e or "").strip().lower()
    return e if EMAIL_RE.match(e) else ""


def _settings_raw(brain):
    """(settings dict, readable): a settings file that exists and does not read is (None, False)."""
    path = _p(brain, SETTINGS_REL)
    if not os.path.exists(path):
        return {}, True
    d = share._read_json(path)
    return (d, True) if isinstance(d, dict) else (None, False)


def settings(brain):
    d, _ok = _settings_raw(brain)
    return d or {}


def _write_settings(brain, updates):
    d = settings(brain)
    for k, v in updates.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    share._write_json(_p(brain, SETTINGS_REL), d)


# ---------------------------------------------------------------- the ledger tool, once per brain

_TASKS = {}
_QUIET = threading.RLock()


def tasks_for(brain):
    """skills/brain-tasks/tasks.py bound to this brain (its BRAIN_ROOT), loaded once per brain."""
    brain = os.path.abspath(brain)
    if brain in _TASKS:
        return _TASKS[brain]
    path = _p(brain, "skills/brain-tasks/tasks.py")
    if not os.path.isfile(path):
        path = os.path.join(os.path.dirname(HERE), "brain-tasks", "tasks.py")
    old = os.environ.get("BRAIN_ROOT")
    os.environ["BRAIN_ROOT"] = brain
    try:
        spec = importlib.util.spec_from_file_location("sharing_tasks_%d" % len(_TASKS), path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    finally:
        if old is None:
            os.environ.pop("BRAIN_ROOT", None)
        else:
            os.environ["BRAIN_ROOT"] = old
    _TASKS[brain] = m
    return m


def _apply(ctx, rel, action, **a):
    """tasks.apply, with its log line saying only which list and what kind of change: words that came through the
    sharing service never reach the brain's log."""
    t = ctx["tasks"]
    with _QUIET:
        real = t.log_line
        t.log_line = lambda agent, text: real(agent, "%s -- %s through the sharing service" % (rel, action))
        try:
            return t.apply(_p(ctx["brain"], rel), rel, action, agent=AGENT, **a)
        finally:
            t.log_line = real


def _write(ctx, rel, action, **a):
    """_apply, with any failure turned into _WriteFailed (never its text)."""
    try:
        return _apply(ctx, rel, action, **a)
    except Exception as e:                                     # noqa: BLE001
        raise _WriteFailed(action) from e


def _ledger_rel(brain, project, fallback=None):
    for h in gate.registry_rows(brain):
        if h.get("id") == project and h.get("tasks"):
            return gate._norm(h["tasks"])
    return gate._norm(fallback) if fallback else None


def _read_item(ctx, rel, iid):
    """(item, raw line) or (None, None). A list that exists and cannot be read raises _WriteFailed."""
    if not rel or not iid:
        return None, None
    t = ctx["tasks"]
    path = _p(ctx["brain"], rel)
    if not os.path.isfile(path):
        return None, None
    try:
        parsed = t.parse(t.read(path))
    except Exception as e:                                     # noqa: BLE001
        raise _WriteFailed("read") from e
    it = next((i for i in parsed["items"] if i["id"] == iid), None)
    if not it:
        return None, None
    return it, parsed["lines"][it["line"] - 1]


def _items(ctx, rel):
    t = ctx["tasks"]
    path = _p(ctx["brain"], rel)
    if not os.path.isfile(path):
        return []
    return t.parse(t.read(path))["items"]


# ---------------------------------------------------------------- the client-computer switch

def _real_date(v):
    try:
        return bool(DATE_RE.match(str(v))) and bool(dt.date.fromisoformat(str(v)))
    except ValueError:
        return False


def client_block(brain, on_purpose=False):
    """"" when this computer may share OUT of its brain now; else the line that says why not (2026-11-11: taking in what
    others share, and answering it, is never held by the switch). A settings file that does not read holds everything."""
    st, ok = _settings_raw(brain)
    if not ok:
        return UNREAD_LINE
    if not st.get("client_computer"):
        return ""
    agreed = st.get("client_agreed")
    if not (isinstance(agreed, dict) and str(agreed.get("client") or "").strip() and _real_date(agreed.get("date"))):
        return OFF_LINE
    return "" if on_purpose else PRESS_LINE


def client_line(brain):
    """The sentence Settings shows under the switch while it is on."""
    st, ok = _settings_raw(brain)
    if not ok:
        return UNREAD_LINE
    if not st.get("client_computer"):
        return ""
    agreed = st.get("client_agreed")
    if isinstance(agreed, dict) and str(agreed.get("client") or "").strip() and _real_date(agreed.get("date")):
        return ("%s agreed in writing on %s. What is shared with you arrives on its own; what you share goes when you press."
                % (clean_name(agreed.get("client")), _md(agreed.get("date"))))
    return IN_LINE


def set_client(brain, on, client=None, date=None):
    brain = share.brain_root(brain)
    if on:
        agreed = None
        if client or date:
            if not (client and date):
                return False, "Say both your employer's name and the date they agreed in writing."
            if not _real_date(date):
                return False, "The date reads as YYYY-MM-DD, like 2026-11-09."
            client = clean_name(client)
            agreed = {"client": client, "date": str(date)}
        _write_settings(brain, {"client_computer": True, "client_agreed": agreed})
        line = ("Your employer owns this computer; %s agreed in writing on %s, so what you share goes when you press." % (client, _md(date))
                if agreed else "Your employer owns this computer: what is shared with you still arrives, and sharing something of your own waits until they agree in writing.")
    else:
        _write_settings(brain, {"client_computer": False, "client_agreed": None})
        line = "This computer is no longer marked as your employer's."
    share._log(brain, "MODIFIED", "viewer/settings.json -- the client-computer switch: %s" % line)
    return True, line


# ---------------------------------------------------------------- the sign-in

def _signin_path(brain):
    return _p(brain, SIGNIN_REL)


def signed_in(brain):
    d = share._read_json(_signin_path(brain))
    return d if isinstance(d, dict) and d.get("access_token") else None


def _keep_out_of_git(brain):
    """The sign-in is a key file: when the brain is a git repository, its .gitignore names it (and the temporary name
    it is written through) before it is written."""
    if not os.path.exists(_p(brain, ".git")):
        return
    path = _p(brain, ".gitignore")
    want = SIGNIN_REL + "*"
    try:
        have = open(path, "r", encoding="utf-8").read() if os.path.isfile(path) else ""
        if want not in have.splitlines():
            lead = "" if (not have or have.endswith("\n")) else "\n"
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                f.write(lead + "# this computer's sign-in to the sharing service: a key file, never committed\n" + want + "\n")
    except OSError:
        pass


def _save_signin(brain, s):
    path = _signin_path(brain)
    _keep_out_of_git(brain)
    share._write_json(path, s)                                 # through sharing-signin.json.tmp, which KEY_FILES covers
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _my_display(brain):
    st = settings(brain)
    s = signed_in(brain) or {}
    return clean_name(st.get("display_name") or s.get("display"), share.label_for(_my_name(brain)))


def _my_name(brain, email=None):
    """This brain's person, bare: share.me, else (for the default `me`) the display name's slug, else the address's
    part before the @."""
    n = share.me(brain)
    if n != "me":
        return n
    st = settings(brain)
    s = signed_in(brain) or {}
    return (_slug(clean_name(st.get("display_name") or s.get("display"), "")) if (st.get("display_name") or s.get("display")) else "") \
        or _slug(str(email or s.get("email") or "").split("@")[0]) or "me"


def _service(brain):
    try:
        return service.open_service(brain), ""
    except service.NotSetUp as e:
        return None, str(e)


def sign_in_start(brain, email, invitation=None):
    """Send the sign-in code. `invitation` is an invitation's code, for a person who signs in with another address
    than the one they were invited at: it lets this address in first."""
    brain = share.brain_root(brain)
    if client_block(brain, on_purpose=True) == UNREAD_LINE:    # signing in is not sharing out; only an unreadable file holds it
        return False, UNREAD_LINE
    svc, why = _service(brain)
    if not svc:
        return False, why
    try:
        if str(invitation or "").strip() and not svc.claim_code(email, invitation):
            return False, "That invitation code does not match an invitation that is still open."
        svc.start_sign_in(email)
    except service.ServiceError as e:
        return False, str(e)
    return True, "A code was sent to %s. Enter it to finish signing in." % str(email).strip().lower()


def sign_in_finish(brain, email, code):
    brain = share.brain_root(brain)
    if client_block(brain, on_purpose=True) == UNREAD_LINE:    # signing in is not sharing out; only an unreadable file holds it
        return False, UNREAD_LINE
    svc, why = _service(brain)
    if not svc:
        return False, why
    try:
        s = svc.finish_sign_in(email, code)
    except service.ServiceError as e:
        return False, str(e)
    doc = {"carrier": svc.carrier, "url": svc.url, "email": s["email"], "user_id": s["user_id"],
           "display": _my_display(brain), "access_token": s["access_token"], "refresh_token": s["refresh_token"],
           "expires_at": s["expires_at"]}
    _save_signin(brain, doc)
    share._log(brain, "MODIFIED", "%s -- signed in to sharing as %s" % (SIGNIN_REL, s["email"]))
    return True, "Signed in to sharing as %s." % s["email"]


def sign_out(brain):
    brain = share.brain_root(brain)
    path = _signin_path(brain)
    if not os.path.isfile(path):
        return True, NOT_SIGNED_IN
    os.remove(path)
    share._log(brain, "DELETED", "%s -- signed out of sharing" % SIGNIN_REL)
    return True, "Signed out of sharing on this computer."


def whoami(brain):
    brain = share.brain_root(brain)
    s = signed_in(brain)
    if not s:
        return {"signed_in": False, "email": None, "display": None, "line": NOT_SIGNED_IN}
    return {"signed_in": True, "email": s.get("email"), "display": s.get("display"),
            "line": "Signed in to sharing as %s (%s)." % (s.get("email"), s.get("display"))}


def _norm_url(u):
    """An address as compared: scheme and host in lower case, the default port dropped, no trailing slash, localhost
    the same as 127.0.0.1. A stand-in folder's address is compared as written."""
    u = str(u or "").strip()
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", u):
        return u.rstrip("/")
    import urllib.parse as up
    p = up.urlsplit(u)
    host = (p.hostname or "").lower()
    host = "127.0.0.1" if host == "localhost" else host
    port = p.port
    scheme = p.scheme.lower()
    if (scheme, port) in (("https", 443), ("http", 80)):
        port = None
    return "%s://%s%s%s" % (scheme, host, (":%d" % port) if port else "", p.path.rstrip("/"))


def _same_service(sess, svc):
    return str(sess.get("carrier") or "") == str(svc.carrier) and _norm_url(sess.get("url")) == _norm_url(svc.url)


def _ctx(brain, on_purpose=True):
    """The context every service verb runs in, or raises Refused with the plain line."""
    out = client_block(brain, on_purpose)                     # "" when this computer may share out now (ctx["out"])
    if out == UNREAD_LINE:
        raise Refused(out)
    # a test run (SHARING_OFFLINE=1) never works on a brain that says it is a real one (real_brain in its settings):
    # on 2026-11-10 a check ran with a real brain as one side, and its test person and presses went where real ones go
    if os.environ.get("SHARING_OFFLINE") == "1" and (_settings_raw(brain)[0] or {}).get("real_brain") is True:
        raise Refused(REAL_BRAIN_LINE)
    svc, why = _service(brain)
    if not svc:
        raise Refused(why)
    s = signed_in(brain)
    if not s:
        raise Refused(NOT_SIGNED_IN)
    if not _same_service(s, svc):
        raise Refused(OTHER_SERVICE)
    return {"brain": brain, "svc": svc, "sess": s, "tasks": tasks_for(brain), "me": _my_name(brain, s.get("email")),
            "uid": s.get("user_id"), "display": _my_display(brain), "out": out}


def _refresh(ctx):
    # another process of this brain (the viewer, a command) may have refreshed already: a refresh token is used once,
    # so a newer sign-in on disk is taken up rather than refreshed again
    disk = signed_in(ctx["brain"]) or {}
    if disk.get("access_token") and disk["access_token"] != ctx["sess"].get("access_token") \
            and float(disk.get("expires_at") or 0) - time.time() >= 60 and _same_service(disk, ctx["svc"]):
        ctx["sess"] = disk
        return
    s = ctx["svc"].refresh(ctx["sess"])
    doc = dict(ctx["sess"])
    doc.update(access_token=s["access_token"], refresh_token=s["refresh_token"], expires_at=s["expires_at"])
    ctx["sess"] = doc
    _save_signin(ctx["brain"], doc)


def call(ctx, method, *args, **kw):
    """One service call: a refresh first when the session ends within a minute, and once more after a SignedOut. A
    sign-in made at another service address is never sent anywhere."""
    if not _same_service(ctx["sess"], ctx["svc"]):
        raise service.ServiceError(OTHER_SERVICE)
    try:
        if float(ctx["sess"].get("expires_at") or 0) - time.time() < 60:
            _refresh(ctx)
    except service.ServiceError:
        pass
    fn = getattr(ctx["svc"], method)
    try:
        return fn(ctx["sess"], *args, **kw)
    except service.SignedOut:
        try:
            _refresh(ctx)
        except service.ServiceError:
            raise service.SignedOut("This sign-in has ended; sign in again.") from None
        return fn(ctx["sess"], *args, **kw)


# ---------------------------------------------------------------- cards and stamps

def _card_text(brain, slug):
    try:
        with open(_p(brain, "people/%s.md" % slug), "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _card_holding(brain, mail):
    """The one people/ card whose text holds this address as a whole word, else None (none, or more than one)."""
    if not mail:
        return None
    pat = re.compile(r"(?<![A-Za-z0-9._%+-])" + re.escape(mail) + r"(?![A-Za-z0-9._%+-])", re.I)
    try:
        names = sorted(f for f in os.listdir(_p(brain, "people")) if f.endswith(".md") and f != "readme.md")
    except OSError:
        return None
    hits = [f[:-3] for f in names if pat.search(_card_text(brain, f[:-3]) or "")]
    return hits[0] if len(hits) == 1 else None


def ensure_card(brain, display, name=None, email=None, picked=None, said=None):
    """The people/ card for a share partner. An existing card is used ONLY when this side picked it when inviting
    (`picked`), or when its text holds the member's address (whatever the card's file is called: 2026-11-11);
    otherwise a new minimal card is written, named the name's slug plus the address's local part, so nobody is ever
    filed as an existing person by typing their name. A new card is said in `said` (a list) when one is given.
    Returns the slug."""
    shown = clean_name(display, name)
    mail = clean_email(email)
    if picked and _card_text(brain, _slug(picked)) is not None:
        return _slug(picked)
    held = _card_holding(brain, mail)
    if held:
        return held
    slug = _name_slug(shown, mail)
    have = _card_text(brain, slug)
    if have is not None and mail and mail in have.lower():
        return slug
    if have is None:                                           # no clash: nobody is being impersonated, the plain slug
        today = _today()
        share._write_text(_p(brain, "people/%s.md" % slug),
                          "# %s\n\n**Where it stands (%s):** A share partner since %s.\n\n## Role & Relationship\n"
                          "A share partner since %s, through sharing.\n%s"
                          % (shown, today, today, today, ("\n## Contact\nEmail: %s\n" % mail) if mail else ""))
        share._log(brain, "CREATED", "people/%s.md -- a minimal card for a share partner" % slug)
        return slug
    local = _slug(mail.split("@")[0]) if mail else ""
    base = ("%s-%s" % (slug, local or "partner"))[:60].strip("-")
    cand, n = base, 1
    while True:
        have = _card_text(brain, cand)
        if have is None:
            break
        if (mail and mail in have.lower()) or (not mail and "A share partner since" in have):
            return cand
        n += 1
        cand = "%s-%d" % (base[:56], n)
    today = _today()
    share._write_text(_p(brain, "people/%s.md" % cand),
                      "# %s\n\n**Where it stands (%s):** A share partner since %s.\n\n## Role & Relationship\n"
                      "A share partner since %s, through sharing.\n%s"
                      % (shown, today, today, today, ("\n## Contact\nEmail: %s\n" % mail) if mail else ""))
    share._log(brain, "CREATED", "people/%s.md -- a minimal card for a share partner" % cand)
    if said is not None:
        said.append("A separate card was made for %s%s, because a card with that name already belongs to someone else."
                    % (shown, (" (%s)" % mail) if mail else ""))
    return cand


def _stamp_path(brain, name):
    return _p(brain, "%s/%s/%s" % (share.SHARED_DIR, name, share.STAMP))


def _stamp(brain, name):
    d = share._read_json(_stamp_path(brain, name))
    return d if isinstance(d, dict) else None


def _save_stamp(brain, stamp):
    share._write_json(_stamp_path(brain, stamp["name"]), stamp)


def list_rel(name):
    return "%s/%s/%s-tasks.md" % (share.SHARED_DIR, name, name)


def _free_name(brain, want, space_id):
    base = _slug(want) or "space"
    n, name = 1, base
    while True:
        st = _stamp(brain, name)
        if (st is None and not os.path.isdir(_p(brain, "%s/%s" % (share.SHARED_DIR, name)))) or (st and st.get("space_id") == space_id):
            return name
        n += 1
        name = "%s-%d" % (base[:36], n)


def _write_space(ctx, name, label, kind, space_id, members):
    """The folder, the stamp, the readme, the space's own list (tasks.py init) and the registry row with its tasks. The
    service is asked first which of this person's computers keeps the space: the stamp records its answer either way,
    and only the keeper makes the list."""
    brain = ctx["brain"]
    ans = _claim(ctx, space_id)
    today = _today()
    label = clean_name(label, name)
    root = _p(brain, share.SHARED_DIR)
    if not os.path.isfile(os.path.join(root, "readme.md")):
        share._write_text(os.path.join(root, "readme.md"), share.SHARED_README.format(today=today))
    if not os.path.isfile(os.path.join(root, ".contract.json")):
        share._write_json(os.path.join(root, ".contract.json"), share.SHARED_CONTRACT)
    if not os.path.isfile(os.path.join(root, ".gitignore")):
        share._write_text(os.path.join(root, ".gitignore"), "# a space's sync state and this computer's id stay on this computer\n.sync/\n.sync-host\n")
    stamp = {"contract": share.CONTRACT, "name": name, "label": label, "kind": kind, "me": ctx["me"],
             "members": members, "carrier": "service", "space_id": space_id,
             "sent": "%s/%s/sent.json" % (share.SHARED_DIR, name), "list": list_rel(name),
             "page": "/share?space=%s" % name, "joined": today, "state": "attached", "salt": secrets.token_hex(16),
             "me_user": ctx["uid"], "host": ans.get("host"), "host_name": ans.get("host_name"),
             "_about": "The stamp of one shared space (skills/sharing/readme.md). carrier service: the sharing service "
                       "carries it; `sent` lists what this brain put in front of it, `list` holds what the others shared.",
             "_written": today}
    _save_stamp(brain, stamp)
    sent = _p(brain, stamp["sent"])
    if not os.path.isfile(sent):
        share._write_json(sent, {"items": [], "threads": []})
    people = ", ".join(clean_name(m.get("display"), share.label_for(m["name"])) for m in members)
    share._write_text(_p(brain, "%s/%s/readme.md" % (share.SHARED_DIR, name)), share.SPACE_README.format(
        name=name, label=label, today=today, people=people, carrier_words=share.CARRIER_WORDS["service"], sent=stamp["sent"]))
    share._registry_rows(brain, [(name, label, [m["name"] for m in members], "service")])
    _registry_tasks(brain, "shared-" + name, list_rel(name))
    lp = _p(brain, list_rel(name))
    if not os.path.isfile(lp) and ans.get("mine"):
        ctx["tasks"].init(lp, list_rel(name), "shared-" + name, "Shared with %s" % label, agent=AGENT)
    share._log(brain, "CREATED", "%s/%s/ -- a space the sharing service carries" % (share.SHARED_DIR, name))
    return stamp


def _kept_line(name):
    return "This is kept in step from %s. Move it here to share from this computer." % clean_name(name, "another computer")


def _claim(ctx, space_id, force=False):
    """Ask the service which of this person's computers keeps the space: {host, host_name, mine}."""
    hid, hname = share.this_host(ctx["brain"])
    return call(ctx, "claim_host", space_id, hid, hname, force=force)


def _host_ok(brain, st, ctx=None, force=False):
    """(True, "") when this computer keeps the space in step; else (False, the line that says which computer does).
    With a context the SERVICE decides (claim_host): the stamp only records its answer. Without one, the stamp says."""
    if ctx is not None and st.get("space_id"):
        ans = _claim(ctx, st["space_id"], force=force)
        if (st.get("host"), st.get("host_name")) != (ans.get("host"), ans.get("host_name")):
            st["host"], st["host_name"] = ans.get("host"), ans.get("host_name")
            _save_stamp(brain, st)
        return (True, "") if ans.get("mine") else (False, _kept_line(ans.get("host_name")))
    hid, hname = share.this_host(brain)
    if not st.get("host"):
        st["host"], st["host_name"] = hid, hname
        _save_stamp(brain, st)
        return True, ""
    if st["host"] == hid:
        return True, ""
    return False, _kept_line(st.get("host_name"))


def move_here(brain, space_name):
    """Make this computer the one that keeps a space in step: its state is rebuilt from the service and the list as
    they stand (nothing kept from before), then a check runs. {ok, line}."""
    brain = share.brain_root(brain)
    try:
        ctx = _ctx(brain)
    except Refused as e:
        return {"ok": False, "line": str(e)}
    st = _find_stamp(brain, space_name)
    if not st or st.get("state") == "detached":
        return {"ok": False, "line": "You do not share with anyone named %s." % clean_name(space_name)}
    with _SpaceLock(brain, st["name"]) as ok:
        if not ok:
            return {"ok": False, "line": "This space is already being checked; try again in a moment."}
        try:
            os.remove(_state_path(brain, st["name"]))
        except OSError:
            pass
        try:
            _host_ok(brain, st, ctx, force=True)
        except service.ServiceError:
            return {"ok": False, "line": OFFLINE}
        lp = _p(brain, st.get("list") or list_rel(st["name"]))
        if not os.path.isfile(lp):
            ctx["tasks"].init(lp, st.get("list") or list_rel(st["name"]), "shared-" + st["name"], "Shared with %s" % st["label"], agent=AGENT)
    share._log(brain, "MODIFIED", "%s/%s/ -- this computer now keeps the space in step" % (share.SHARED_DIR, st["name"]))
    r = sync(brain, on_purpose=True, only=st["name"])
    return {"ok": True, "line": "This computer now keeps what you share with %s in step. %s" % (st["label"], r.get("line") or "")}


def _salt(brain, st):
    if not st.get("salt"):
        st["salt"] = secrets.token_hex(16)
        _save_stamp(brain, st)
    return st["salt"]


def _registry_tasks(brain, hid, rel):
    path = _p(brain, share.REGISTRY_REL)
    reg = share._read_json(path)
    if not isinstance(reg, dict):
        return
    row = next((h for h in reg.get("holons", []) if h.get("id") == hid), None)
    if row is not None and row.get("tasks") != rel:
        row["tasks"] = rel
        share._write_json(path, reg)


def _service_stamps(brain, attached_only=True):
    out = []
    root = _p(brain, share.SHARED_DIR)
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return out
    for n in names:
        st = _stamp(brain, n)
        if st and st.get("carrier") == "service" and (not attached_only or st.get("state", "attached") == "attached"):
            out.append(st)
    return out


def _find_stamp(brain, name):
    want = _slug(name)
    for st in _service_stamps(brain, attached_only=False):
        if st["name"] == want or _slug(st.get("label")) == want:
            return st
    return None


def _members_from(ctx, svc_space, old):
    """The stamp's members from the service's list, every name cleaned where it arrives: each {name, display, email,
    card, role, user_id, left}; an invited person not yet in the space stays as invited until someone who matches
    them joins."""
    out = []
    before = {o.get("user_id"): o for o in old or [] if o.get("user_id")}
    pending = [o for o in old or [] if o.get("invited") and not o.get("user_id")]
    said = ctx.setdefault("notices", [])
    for m in svc_space.get("members") or []:
        if not isinstance(m, dict):
            continue
        mine = m.get("user_id") == ctx["uid"]
        left = str(m.get("left_at") or "")[:10] or None
        name = _slug(m.get("name")) or "member"
        display = clean_name(m.get("display"), share.label_for(name))
        email = clean_email(m.get("email"))
        picked = (before.get(m.get("user_id")) or {}).get("card")
        if not picked and svc_space.get("kind") == "pair" and len(pending) == 1:
            picked = pending[0].get("card")                    # the card this side picked when inviting
        card = None if mine else ensure_card(ctx["brain"], display, name, email, picked=picked, said=said)
        out.append({"name": name, "display": display, "email": email, "card": card, "role": "maker" if m.get("role") == "maker" else "member",
                    "user_id": m.get("user_id"), "left": left if left and _real_date(left) else None})
        if (before.get(m.get("user_id")) or {}).get("auto_take"):
            out[-1]["auto_take"] = True                        # this side's own choice, kept across checks
    joined = [x for x in out if x["user_id"] != ctx["uid"]]
    for o in old or []:
        if not o.get("invited") or o.get("user_id"):
            continue
        hit = any(x["name"] == o["name"] or _slug(x["display"]) == _slug(o.get("display")) for x in joined)
        if not hit and not (svc_space.get("kind") == "pair" and joined):
            out.append(o)
    return out


def _holds(stamp, ctx):
    """Who is in the space from this side, by user id (two people may share a short name)."""
    return {"me": ctx["me"], "me_user": ctx["uid"],
            "others": [{"name": m["name"], "card": m.get("card"), "user_id": m.get("user_id")}
                       for m in stamp.get("members") or []
                       if (m.get("user_id") != ctx["uid"] if m.get("user_id") else m.get("name") != ctx["me"])
                       and not m.get("left")]}


# ---------------------------------------------------------------- attaching and detaching

def _guard(brain, fn):
    brain = share.brain_root(brain)
    try:
        ctx = _ctx(brain)
        return fn(ctx)
    except Refused as e:
        return {"ok": False, "line": str(e)}
    except service.ServiceError as e:
        return {"ok": False, "line": str(e)}


def invite(brain, email, name, card=None, team=None):
    """With no team: a pair space on the service for this partner, and the invitation. With team: an invitation into
    that team. {ok, line, code, text, space}; the code is shown here once and kept nowhere."""
    def go(ctx):
        b = ctx["brain"]
        if team:
            st = _find_stamp(b, team)
            if not st or st.get("kind") != "team" or st.get("state") == "detached":
                return {"ok": False, "line": "There is no team brain called %s here." % clean_name(team)}
            label = clean_name(name, card or "")
            got = call(ctx, "invite", st["space_id"], email, label)
            st["members"].append({"name": _slug(label) or "member", "display": label, "card": card,
                                  "role": "member", "user_id": None, "left": None, "invited": _today()})
            _save_stamp(b, st)
            sp_name = st["name"]
        else:
            label = clean_name(name, share.label_for(card) if card else "") if (name or card) else ""
            if not label:
                return {"ok": False, "line": "Say the name of the person to share with."}
            short = _slug(label)
            have = _find_stamp(b, short)
            if have and have.get("state") != "detached":
                return {"ok": False, "line": "You already share with %s." % have["label"]}
            made = call(ctx, "make_space", short, label, "pair", ctx["me"], ctx["display"])
            got = call(ctx, "invite", made["id"], email, label)
            sp_name = _free_name(b, short, made["id"])
            members = [{"name": ctx["me"], "display": ctx["display"], "email": clean_email(ctx["sess"].get("email")), "card": None,
                        "role": "maker", "user_id": ctx["uid"], "left": None},
                       {"name": short, "display": label, "card": card, "role": "member", "user_id": None, "left": None,
                        "invited": _today()}]
            _write_space(ctx, sp_name, label, "pair", made["id"], members)
        share._log(b, "MODIFIED", "%s/%s/ -- an invitation to share was made" % (share.SHARED_DIR, sp_name))
        into = (" into %s" % st["label"]) if team else ""
        text = ("%s invited you to share tasks and questions through the Brain Viewer.\n"
                "Open the viewer, go to Settings, then Sharing, and sign in with this email address.\n"
                "If the invitation is not listed there, choose Join with a code and enter %s"
                % (ctx["display"], got["code"]))
        return {"ok": True, "line": "Invited %s%s. Send %s the text below; the code is shown only now." % (label, into, label),
                "code": got["code"], "text": text, "space": sp_name}
    return _guard(brain, go)


def _join_space(ctx, svc_space):
    """Write the stamp, list, readme and registry row for a space the service lists this person in. (name, label)."""
    b = ctx["brain"]
    members = _members_from(ctx, svc_space, [])
    others = [m for m in members if m["user_id"] != ctx["uid"]]
    if svc_space.get("kind") == "pair" and others:
        want, label = others[0]["name"], others[0]["display"]
    else:
        want, label = _slug(svc_space.get("name")) or "team", clean_name(svc_space.get("label"), "Team")
    name = _free_name(b, want, svc_space["id"])
    _write_space(ctx, name, label, "team" if svc_space.get("kind") == "team" else "pair", svc_space["id"], members)
    return name, label


def _finish_joins(ctx, svc_spaces=None):
    """Any space the service lists this person as an active member of that has no stamp here (an accept that died
    after the join) gets its stamp, list, readme and registry row now. Returns [(name, label)] written."""
    if svc_spaces is None:
        svc_spaces = [s for s in call(ctx, "spaces") if isinstance(s, dict) and s.get("id")]
    have = {st.get("space_id") for st in _service_stamps(ctx["brain"], attached_only=False)}
    done = []
    for sp in svc_spaces:
        me = next((m for m in sp.get("members") or [] if isinstance(m, dict) and m.get("user_id") == ctx["uid"]), None)
        if sp.get("id") in have or not me or me.get("left_at"):
            continue
        done.append(_join_space(ctx, sp))
    return done


def invites(brain):
    def go(ctx):
        try:
            _finish_joins(ctx)
        except service.ServiceError:
            pass
        rows = []
        for r in call(ctx, "invites") or []:
            if not isinstance(r, dict):
                continue
            rows.append(dict(r, from_display=clean_name(r.get("from_display"), "Someone"),
                             space_label=clean_name(r.get("space_label"), "a shared space"),
                             from_email=clean_email(r.get("from_email")),
                             space_kind="team" if r.get("space_kind") == "team" else "pair"))

        def one(r):
            who = r["from_display"] + ((" (%s)" % r["from_email"]) if r["from_email"] else "")
            return "%s invited you to %s" % (who, "share" if r["space_kind"] == "pair" else "the team brain %s" % r["space_label"])
        line = "No invitations are waiting." if not rows else "; ".join(one(r) for r in rows)
        return {"ok": True, "line": line, "invites": rows}
    return _guard(brain, go)


def accept(brain, invite_id=None, code=None):
    def go(ctx):
        if not invite_id and not code:
            return {"ok": False, "line": "Pick an invitation, or enter the code you were sent."}
        ctx["notices"] = []
        try:
            sp = call(ctx, "accept", invite_id, code, ctx["me"], ctx["display"])
        except service.ServiceError as e:
            try:                                               # the join may have landed before the answer was lost
                done = _finish_joins(ctx)
            except service.ServiceError:
                done = []
            if done:
                return {"ok": True, "line": " ".join(["You now share with %s." % done[0][1]] + ctx["notices"]), "space": done[0][0]}
            raise e
        svc_space = next((s for s in call(ctx, "spaces") if s["id"] == sp["id"]), None) or dict(sp, members=[])
        name, label = _join_space(ctx, svc_space)
        return {"ok": True, "line": " ".join(["You now share with %s." % label] + ctx["notices"]), "space": name}
    return _guard(brain, go)


def make_team(brain, name, label):
    def go(ctx):
        short = _slug(name)
        if not short:
            return {"ok": False, "line": "A team brain needs a short name."}
        if _find_stamp(ctx["brain"], short):
            return {"ok": False, "line": "There is already a space called %s here." % short}
        lab = clean_name(label, share.label_for(short))
        made = call(ctx, "make_space", short, lab, "team", ctx["me"], ctx["display"])
        members = [{"name": ctx["me"], "display": ctx["display"], "email": clean_email(ctx["sess"].get("email")), "card": None,
                    "role": "maker", "user_id": ctx["uid"], "left": None}]
        _write_space(ctx, _free_name(ctx["brain"], short, made["id"]), lab, "team", made["id"], members)
        return {"ok": True, "line": "Made the team brain %s. Invite people into it from here." % lab, "space": short}
    return _guard(brain, go)


def _detach_local(brain, st, why):
    st["state"] = "detached"
    st["left"] = _today()
    _save_stamp(brain, st)
    share._log(brain, "MODIFIED", "%s/%s/ -- detached: %s; what it holds stays here as it is" % (share.SHARED_DIR, st["name"], why))


def _not_in_space(err):
    w = str(err).lower()
    return "not in this space" in w or "not in this shared space" in w


def detach(brain, space_name):
    def go(ctx):
        st = _find_stamp(ctx["brain"], space_name)
        if not st:
            return {"ok": False, "line": "You do not share with anyone named %s." % clean_name(space_name)}
        if st.get("state") == "detached":
            return {"ok": True, "line": "You already stopped sharing with %s." % st["label"]}
        try:
            call(ctx, "leave", st["space_id"])
        except service.ServiceError as e:
            if not _not_in_space(e):
                return {"ok": False, "line": OFFLINE}
        _detach_local(ctx["brain"], st, "this brain left")
        if st.get("kind") == "team":
            return {"ok": True, "line": "You left %s. What was shared there stays here as it stands today, and nothing more is sent."
                    % st["label"]}
        return {"ok": True, "line": "You and %s each keep what the other shared, as it stands today. Nothing more is sent."
                % st["label"]}
    return _guard(brain, go)


# ---------------------------------------------------------------- sharing one item

def _sent(brain, st):
    d = share._read_json(_p(brain, st["sent"]))
    d = d if isinstance(d, dict) else {}
    return {"items": [x for x in d.get("items") or [] if isinstance(x, dict)], "threads": list(d.get("threads") or [])}


def _save_sent(brain, st, d):
    """sent.json's items and threads, every other key it holds (files, drawings, sections) kept as it is."""
    whole = share._read_json(_p(brain, st["sent"]))
    whole = whole if isinstance(whole, dict) else {}
    whole.update(items=d["items"], threads=d["threads"])
    share._write_json(_p(brain, st["sent"]), whole)


def _thing_key(salt, ledger, iid):
    return hashlib.sha256(("%s/%s/%s" % (salt, ledger, iid)).encode("utf-8")).hexdigest()[:16]


def share_item(brain, space_name, project, item_id):
    brain = share.brain_root(brain)
    try:
        ctx = _ctx(brain)
    except Refused as e:
        return False, str(e)
    if ctx.get("out"):                                         # an employer's computer: sharing out waits for the yes
        return False, ctx["out"]
    st = _find_stamp(brain, space_name)
    if not st or st.get("state") == "detached":
        return False, "You do not share with anyone named %s." % clean_name(space_name)
    try:
        here, why = _host_ok(brain, st, ctx)
    except service.ServiceError:
        return False, OFFLINE
    if not here:
        return False, why
    rel = _ledger_rel(brain, project)
    try:
        it, raw = _read_item(ctx, rel, item_id)
    except _WriteFailed:
        return False, "Its list cannot be read right now."
    if not it:
        return False, "That item is not on its list."
    who = st["label"]
    body, why = gate.render_task(brain, rel, it, raw, _holds(st, ctx))
    if not body:
        return False, "Not shared with %s: %s." % (who, why)
    d = _sent(brain, st)
    if not any(x.get("project") == project and x.get("id") == item_id for x in d["items"]):
        d["items"].append({"project": project, "ledger": rel, "id": item_id,
                           "at": dt.datetime.now().isoformat(timespec="seconds"), "thing": None})
        _save_sent(brain, st, d)
        share._log(brain, "MODIFIED", "%s -- %s %s shared" % (st["sent"], project, item_id))
    res = sync(brain, on_purpose=True, only=st["name"])
    words = body["text"] if len(body["text"]) <= 60 else body["text"][:57].rstrip() + "..."
    tail = "" if res.get("ok") else " (%s)" % res.get("line")
    return True, "Shared with %s: “%s” is on %s's Today once %s checks for what was shared%s." % (who, words, who, who, tail)


def take_back(brain, space_name, project, item_id):
    brain = share.brain_root(brain)
    try:
        ctx = _ctx(brain)
    except Refused as e:
        return False, str(e)
    st = _find_stamp(brain, space_name)
    if not st:
        return False, "You do not share with anyone named %s." % clean_name(space_name)
    try:
        here, why = _host_ok(brain, st, ctx)
    except service.ServiceError:
        return False, OFFLINE
    if not here:
        return False, why
    d = _sent(brain, st)
    row = next((x for x in d["items"] if x.get("project") == project and x.get("id") == item_id), None)
    if not row:
        return False, "That item is not shared with %s." % st["label"]
    with _SpaceLock(brain, st["name"]) as ok:
        if not ok:
            return False, "What you share with %s is being checked right now; try again in a moment." % st["label"]
        state = _load_state(brain, st["name"])
        try:
            _remove_own(ctx, st, state, row)
        except service.ServiceError:
            return False, OFFLINE
        finally:
            _save_state(brain, st["name"], state)
        d["items"] = [x for x in d["items"] if x is not row]
        _save_sent(brain, st, d)
    share._log(brain, "MODIFIED", "%s -- %s %s taken back" % (st["sent"], project, item_id))
    sync(brain, on_purpose=True, only=st["name"])
    return True, "Taken back: it leaves %s's Today once %s checks for what was shared." % (st["label"], st["label"])


# ---------------------------------------------------------------- sync state and lock

class _SpaceLock:
    def __init__(self, brain, name):
        self.path = _p(brain, "%s/%s/.sync/lock" % (share.SHARED_DIR, name))
        self.ok = False

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self.ok = True
                return True
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > 120:
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                return False
        return False

    def __exit__(self, *exc):
        if self.ok:
            try:
                os.remove(self.path)
            except OSError:
                pass
        return False


def _state_path(brain, name):
    return _p(brain, "%s/%s/.sync/state.json" % (share.SHARED_DIR, name))


def _load_state(brain, name):
    d = share._read_json(_state_path(brain, name))
    d = d if isinstance(d, dict) else {}
    d.setdefault("out", {})         # "<project>/<id>" -> {thing, version, body, key}: what this brain is home of
    d.setdefault("in", {})          # thing id -> {local, version, body, sent, home, removed, refused}
    d.setdefault("local_only", [])  # ids on the space's list that the gate keeps here
    d.setdefault("acts", {})        # act id -> the result this brain gave it (saved before the mark)
    return d


def _save_state(brain, name, d):
    share._write_json(_state_path(brain, name), d)        # a temp file and a replace: never half written


# ---------------------------------------------------------------- bodies, views, merging

def _str(v, cap=4000):
    return str(v)[:cap] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def _norm_body(raw):
    """A body from the service, defensively: every key the right type, missing keys filled, nothing else kept."""
    b = raw if isinstance(raw, dict) else {}
    kind = "question" if b.get("kind") == "question" else "task"
    steps = []
    for s in b.get("steps") if isinstance(b.get("steps"), list) else []:
        if isinstance(s, dict):
            steps.append({"text": _str(s.get("text"), 1000), "done": s.get("done") is True})
        elif isinstance(s, str):
            steps.append({"text": s[:1000], "done": False})
    opts = [o.split("=", 1)[0].strip()[:48] for o in (b.get("options") if isinstance(b.get("options"), list) else []) if isinstance(o, str)]
    state = b.get("state") if b.get("state") in ("open", "done", "blocked", "held", "asked", "answered") else ("asked" if kind == "question" else "open")
    out = {"kind": kind, "text": _str(b.get("text")), "steps": [s for s in steps if s["text"].strip()], "note": _str(b.get("note")),
           "created": "", "due": "", "done": "", "until": "", "state": state, "mine": b.get("mine") is True,
           "to_you": b.get("to_you") is True, "options": [o for o in opts if o], "answer": _str(b.get("answer")),
           "list": clean_name(b.get("list"), "") if b.get("list") else ""}
    for k in ("created", "due", "done", "until"):
        if _real_date(b.get(k)):
            out[k] = b[k]
    if isinstance(b.get("for"), str) and _slug(b["for"]):
        out["for"] = _slug(b["for"])
    for k in ("for_user", "home_user"):
        if isinstance(b.get(k), str) and re.fullmatch(r"[A-Za-z0-9-]{1,64}", b[k]):
            out[k] = b[k]
    if isinstance(b.get("thread"), str) and re.fullmatch(r"[A-Za-z0-9-]{1,64}", b["thread"]):
        out["thread"] = b["thread"]
    if isinstance(b.get("group"), str) and clean_name(b["group"], ""):
        out["group"] = clean_name(b["group"], "")
    o = b.get("origin")
    if isinstance(o, dict) and isinstance(o.get("user"), str) and isinstance(o.get("local"), str) \
            and re.fullmatch(r"[A-Za-z0-9-]{1,64}", o["user"]) and re.fullmatch(r"[TQ]-\d{4}", o["local"]):
        out["origin"] = {"user": o["user"], "local": o["local"]}
    if b.get("removed") is True:
        out["removed"] = True
    return out


def _canon(ctx, body):
    """A body as the ledger tool would write it back, so a comparison never loops on spacing or a separator; steps are
    cut to the tool's limits."""
    t = ctx["tasks"]
    b = _norm_body(body)
    b["text"] = t.clean(b.get("text"))
    b["note"] = t.clean(b.get("note"))
    b["answer"] = t.clean(b.get("answer"))
    steps = []
    for s in b["steps"][:STEPS_MAX]:
        txt = t.clean(s["text"].replace("|", "/"))
        if len(txt) > STEP_CHARS:
            txt = txt[:STEP_CHARS - 3].rstrip() + "..."
        if txt:
            steps.append({"text": txt, "done": bool(s["done"])})
    b["steps"] = steps
    b["options"] = [t.clean(o.replace("|", "/").replace("=", " ")) for o in b["options"] if o.strip()][:6]
    return b


def _view(ctx, body):
    b = _canon(ctx, body)
    st = b.get("state")
    if b.get("kind") == "question":
        st = "answered" if st == "answered" else "asked"
    else:
        st = "done" if st == "done" else "open"
    return {"text": b["text"], "steps": [[s["text"], s["done"]] for s in b["steps"]], "note": b["note"], "due": b["due"],
            "state": st, "answer": b["answer"] if st == "answered" else "", "options": b["options"]}


def _local_view(ctx, it):
    """The shared fields of a local item, read the way _view reads a body."""
    t = ctx["tasks"]
    q = it["kind"] == "question"
    st = ("answered" if it["mark"] == "a" else "asked") if q else ("done" if it["mark"] == "x" else "open")
    opts = [t.option_parts(o)[0] for o in str(it.get("options") or "").split("|") if o.strip()]
    return {"text": t.clean(it["text"]), "steps": [[t.clean(s["text"]), bool(s["done"])] for s in t.steps_list(it.get("steps"))],
            "note": t.clean(it.get("note")), "due": it.get("due") or "", "state": st,
            "answer": t.clean(it.get("answer")) if st == "answered" else "", "options": opts}


def _extension(base, cur):
    """What was added to a note: the part after the old note, or the whole note when it was rewritten."""
    base, cur = base or "", cur or ""
    if cur == base:
        return ""
    if base and cur.startswith(base):
        return cur[len(base):].strip(" |,;-")
    return cur.strip()


NOTE_STAMP_RE = re.compile(r"^(?:\s*[|,;:.\-]\s*)*(?:note\s+\d{4}-\d{2}-\d{2}\s*:\s*)?", re.I)


def _reply_words(text):
    """What a person added to a note, without the viewer's own `; note YYYY-MM-DD:` lead (the home writes its own
    name and date in front) and without a leading separator."""
    return NOTE_STAMP_RE.sub("", str(text or ""), count=1).strip()


def _merge(base, local, remote):
    """A three-way merge of two views against the one both started from. (merged, clashes): a field only one side
    changed takes that side's value; steps and notes combine; any other field both changed keeps the local value and
    is named in clashes, with the other side's value, so nothing is lost silently."""
    out, clashes = dict(remote), []
    for f in FIELDS:
        lv, rv, bv = local.get(f), remote.get(f), base.get(f)
        if lv == bv or lv == rv:
            continue
        if rv == bv:
            out[f] = lv
            continue
        if f == "steps" and [s[0] for s in lv] == [s[0] for s in rv] == [s[0] for s in bv]:
            out[f] = [[lv[i][0], lv[i][1] if lv[i][1] != bv[i][1] else rv[i][1]] for i in range(len(lv))]
            continue
        if f == "note" and lv.startswith(bv or "") and rv.startswith(bv or ""):
            add = _extension(bv, lv)
            out[f] = (rv + " | " + add) if (rv and add) else (rv or add)
            continue
        out[f] = lv
        clashes.append((f, rv))
    return out, clashes


# ---------------------------------------------------------------- writing a body onto the local list

def _owner_for(ctx, sp_stamp, body, writer):
    """(owner, to) on this brain's list for a body written by `writer` (a stamp member)."""
    t = ctx["tasks"]
    me_name = next((m["name"] for m in sp_stamp.get("members") or [] if m.get("user_id") == ctx["uid"]), ctx["me"])
    if body.get("for_user"):                                  # the service's user id decides, never a name
        for_me = body["for_user"] == ctx["uid"]
    else:
        for_me = bool(body.get("to_you")) and body.get("for") in (None, me_name, ctx["me"]) and writer.get("user_id") != ctx["uid"]
    them = "@" + (writer.get("card") or writer.get("name") or "claude")
    if writer.get("user_id") == ctx["uid"]:
        them = t.OWNER
    if body.get("kind") == "question":
        return them, (t.OWNER if for_me else them)
    return (t.OWNER if for_me else them), None


def _pose_refusal(err):
    return "cannot be put to the owner" in str(err.__cause__ or err)


def _by_key(ctx, rel, key):
    return next((i for i in _items(ctx, rel) if i.get("key") == key), None)


def _create_local(ctx, sp, rel, body, writer, tid):
    """A new item on the space's list from a body, keyed `space:<thing id>` so a second try adopts the first instead of
    making another. Returns (local id or None, problem, permanent): a half-made item returns its id with a problem."""
    b = _canon(ctx, body)
    key = "space:%s" % tid
    who = writer.get("display") or "Someone"
    have = _by_key(ctx, rel, key)
    if have:
        return have["id"], "", False
    owner, to = _owner_for(ctx, sp, b, writer)
    src = _slug(writer.get("card") or writer.get("name")) or None
    if not b["text"]:
        return None, "Something %s shared has no words, so it was not put on your list." % who, True
    try:
        if b.get("kind") == "question":
            opts = " | ".join(b["options"]) if 2 <= len(b["options"]) <= 6 else None
            tlink = (ctx.get("thread_paths") or {}).get(b.get("thread")) if b.get("thread") else None
            iid = _write(ctx, rel, "ask", text=b["text"], frm=owner, to=to, note=b["note"] or None, options=opts,
                         source=src, key=key, due=b["due"] or None, links=[tlink] if tlink else None,
                         milestone=b.get("group") or None, new_milestone=bool(b.get("group")))
        else:
            tlink = (ctx.get("thread_paths") or {}).get(b.get("thread")) if b.get("thread") else None
            iid = _write(ctx, rel, "add", text=b["text"], owner=owner, note=b["note"] or None, source=src, key=key,
                         due=b["due"] or None, links=[tlink] if tlink else None,
                         milestone=b.get("group") or None, new_milestone=bool(b.get("group")))
    except _WriteFailed as e:
        if _pose_refusal(e):
            return None, "A question from %s could not go on your list as it is written." % who, True
        return None, "Something %s shared could not be written to your list yet; it will be tried again." % who, False
    try:
        if b.get("kind") == "question" and b.get("state") == "answered" and b.get("answer"):
            _write(ctx, rel, "answer", id=iid, text=b["answer"], by=to)
        if b.get("kind") != "question":
            if b["steps"]:
                _write(ctx, rel, "steps", id=iid, steps=b["steps"])
            if b.get("state") == "done":
                _write(ctx, rel, "done", id=iid)
    except _WriteFailed:
        return iid, "Part of what %s shared could not be written yet; it will be tried again." % who, False
    return iid, "", False


def _match_local(ctx, rel, iid, view, writer, owner=None):
    """Make the local item read as `view`, field by field, each through the ledger tool. Returns (problems, failed).
    `owner`, when given, is whose task it is on this list (_owner_for): a task handed over or taken back after it
    first arrived changes hands here too (found on the real service, 2026-11-10)."""
    it, _raw = _read_item(ctx, rel, iid)
    if not it:
        return [], False
    cur = _local_view(ctx, it)
    who = writer.get("display") or "them"
    try:
        if owner and it["kind"] == "task" and it.get("owner") and it["owner"] != owner:
            _write(ctx, rel, "reassign", id=iid, owner=owner,
                   reason=("handed to you by %s" if owner == ctx["tasks"].OWNER else "taken back by %s") % who)
        if cur["text"] != view["text"] and view["text"]:
            _write(ctx, rel, "retext", id=iid, text=view["text"])
        if it["kind"] == "task" and cur["steps"] != view["steps"]:
            _write(ctx, rel, "steps", id=iid, steps=[{"text": s[0], "done": s[1]} for s in view["steps"]] or "")
        if cur["note"] != view["note"]:
            _write(ctx, rel, "note", id=iid, note=view["note"])
        if cur["due"] != view["due"]:
            _write(ctx, rel, "today", id=iid, due=view["due"] or "none")
        if it["kind"] == "question" and cur["options"] != view["options"] and (len(view["options"]) >= 2 or not view["options"]):
            _write(ctx, rel, "options", id=iid, options=" | ".join(view["options"]))
        if it["kind"] == "task":
            if view["state"] == "done" and cur["state"] != "done":
                _write(ctx, rel, "done", id=iid)
            elif view["state"] != "done" and cur["state"] == "done":
                _write(ctx, rel, "reopen", id=iid)
        else:
            if view["state"] == "answered" and (cur["state"] != "answered" or cur["answer"] != view["answer"]) and view["answer"]:
                _write(ctx, rel, "answer", id=iid, text=view["answer"], by="@" + (writer.get("card") or writer.get("name") or "claude"))
            elif view["state"] != "answered" and cur["state"] == "answered":
                _write(ctx, rel, "reopen", id=iid)
    except _WriteFailed:
        return ["A change from %s could not be written to your list yet; it will be tried again." % who], True
    return [], False


def _close_local(ctx, rel, iid, who):
    """Close an item whose thing was taken back. Raises _WriteFailed when the list cannot be written."""
    t = ctx["tasks"]
    it, _raw = _read_item(ctx, rel, iid)
    if not it:
        return
    words = "taken back by %s on %s" % (who, _md())
    if it["kind"] == "task":
        if it["mark"] != "x":
            _write(ctx, rel, "done", id=iid, note=words)
    elif it["mark"] != "a":
        _write(ctx, rel, "note", id=iid, note=((it.get("note") + " | ") if it.get("note") else "") + words)
        _write(ctx, rel, "answer", id=iid, text=words, by=t.OWNER)


# ---------------------------------------------------------------- the home side: what this brain shares

def _put_own(ctx, st, state, key, body, removed=False, thing_key=None):
    e = state["out"].setdefault(key, {})
    if thing_key:
        e["key"] = thing_key
    row = {"id": e.get("thing"), "space_id": st["space_id"], "kind": body.get("kind") or "task", "home": ctx["uid"],
           "key": e.get("key") or "", "title": (body.get("text") or "")[:80],
           "body": body, "version": e.get("version"), "removed_at": service._iso() if removed else None}
    for attempt in range(3):
        try:
            got = call(ctx, "put_thing", row)
            break
        except service.Conflict:
            cur = call(ctx, "get_things", [row["id"]])[0]
            row["version"] = cur["version"]
        except service.ServiceError:
            if row["id"] or attempt:
                raise
            hit = next((h for h in call(ctx, "heads", st["space_id"]) if h.get("home") == ctx["uid"] and h.get("key") == row["key"]), None)
            if not hit:
                raise
            row["id"], row["version"] = hit["id"], hit["version"]
    else:
        raise service.ServiceError("This kept changing; try again.")
    e.update(thing=got["id"], version=got["version"], body=body)
    return got


def _remove_own(ctx, st, state, row):
    key = "%s/%s" % (row["project"], row["id"])
    e = state["out"].get(key)
    if not e or not e.get("thing"):
        state["out"].pop(key, None)
        return
    kind = (e.get("body") or {}).get("kind") or "task"
    _put_own(ctx, st, state, key, {"kind": kind, "removed": True}, removed=True)   # the words leave the service
    state["out"].pop(key, None)


def _payload_never_crosses(ctx, text):
    """The home's own gate on what arrives: hidden characters out, a private mark in any spacing, key shapes, and
    the home's held-back names."""
    return bool(gate.words_refusal(ctx["brain"], str(text or "")))


def _apply_one_act(ctx, st, state, a, rows, by_thing, members, pair):
    """(result, scrub, problem) for one act; raises _WriteFailed when this brain's list could not be written."""
    t = ctx["tasks"]
    hit = by_thing.get(a.get("thing_id"))
    actor = members.get(a.get("by"))
    if not hit:
        h = (ctx.get("heads") or {}).get(a.get("thing_id"))
        if h and h.get("removed_at"):
            return R_GONE, False, ""                           # taken back: proof, so it is refused
        raise _Unplaced()
    if not actor:
        return R_STRANGER, False, ""
    key, e = hit
    row = rows.get(key)
    rel = _ledger_rel(ctx["brain"], row["project"], row.get("ledger")) if row else None
    it, _raw = _read_item(ctx, rel, row["id"]) if row else (None, None)
    if not it:
        return R_OFF_LIST, False, ""
    body = e.get("body") or {}
    name = actor.get("display") or share.label_for(actor.get("name"))
    if body.get("for_user"):                                  # the service's user id decides, never a name
        for_actor = body["for_user"] == actor.get("user_id")
    else:
        for_actor = bool(body.get("to_you")) and (body.get("for") == actor.get("name") or (pair and not body.get("for")))
    p = a.get("payload") if isinstance(a.get("payload"), dict) else {}
    kind = a.get("act")
    words_of = "“%s”" % (it["text"][:50])
    if kind == "tick":
        steps = t.steps_list(it.get("steps"))
        idx = next((i for i, s in enumerate(steps) if t.clean(s["text"]) == t.clean(_str(p.get("text")))), None)
        if idx is None:
            try:
                n = int(p.get("step") or 0) - 1
            except (TypeError, ValueError):
                n = -1
            idx = n if 0 <= n < len(steps) else None
        if it["kind"] != "task" or idx is None:
            return R_NO_STEP, False, "%s's tick on %s was not applied: that step is not on it." % (name, words_of)
        if steps[idx]["done"] != (p.get("done") is True):
            _write(ctx, rel, "steps", id=it["id"], **({"tick": idx + 1} if p.get("done") is True else {"untick": idx + 1}))
        return R_APPLIED, False, ""
    if kind in ("reply", "answer"):
        words = _reply_words(t.clean(_str(p.get("text"))))[:500]
        if _payload_never_crosses(ctx, _str(p.get("text"))):
            return R_NEVER, True, "%s's %s on %s was not taken in: it holds something that never crosses." % (name, kind, words_of)
        if not words:
            return R_EMPTY, False, ""
        if kind == "reply":
            line = "%s, %s: %s" % (name, _md(), words)
            note = it.get("note") or ""
            if not note.endswith(line):
                _write(ctx, rel, "note", id=it["id"], note=((note + " | ") if note else "") + line)
            return R_APPLIED, False, ""
        if it["kind"] != "question":
            return R_NOT_Q, False, ""
        if not for_actor:
            return R_NOT_ASKED, False, "%s's answer to %s was not applied: it was not asked of %s." % (name, words_of, name)
        if it["mark"] == "a":
            return R_ANSWERED, False, "%s's answer to %s was not applied: it was already answered." % (name, words_of)
        _write(ctx, rel, "answer", id=it["id"], text=words, by="@" + (actor.get("card") or actor.get("name")))
        return R_APPLIED, False, ""
    if kind in ("done", "reopen"):
        if it["kind"] != "task":
            return R_Q_DONE, False, ""
        if not for_actor:
            return R_NOT_THEIRS, False, "%s's %s was not applied: it is not %s's to do." % (name, kind, name)
        if kind == "done" and it["mark"] != "x":
            _write(ctx, rel, "done", id=it["id"])
        elif kind == "reopen" and it["mark"] == "x":
            _write(ctx, rel, "reopen", id=it["id"])
        return R_APPLIED, False, ""
    return R_UNKNOWN, False, "Something %s did on %s cannot be done from a shared copy." % (name, words_of)


def _apply_acts(ctx, st, state, acts, force, report):
    members = {m.get("user_id"): m for m in st.get("members") or []}
    by_thing = {e.get("thing"): (k, e) for k, e in state["out"].items() if e.get("thing")}
    rows = {"%s/%s" % (x["project"], x["id"]): x for x in _sent(ctx["brain"], st)["items"]}
    pair = st.get("kind") == "pair"
    for a in acts:
        if not isinstance(a, dict) or a.get("space_id") != st["space_id"] or not a.get("id"):
            continue
        aid = a["id"]
        scrub = False
        if aid in state["acts"]:
            result = state["acts"][aid]                       # applied here already; only the mark is missing
            scrub = result == R_NEVER
        else:
            try:
                hit_ = by_thing.get(a.get("thing_id"))
                if a.get("act") == "edit" and hit_ and hit_[0].split(":", 1)[0] in kinds.TEXT_KINDS and members.get(a.get("by")):
                    result, scrub, prob = kinds.apply_edit(ctx, st, state, a, hit_[0], hit_[1], members[a["by"]])
                else:
                    result, scrub, prob = _apply_one_act(ctx, st, state, a, rows, by_thing, members, pair)
            except _WriteFailed:
                who = (members.get(a.get("by")) or {}).get("display") or "Someone"
                report["problems"].append("What %s did could not be written to your list yet; it will be tried again." % who)
                continue
            except _Unplaced:
                who = (members.get(a.get("by")) or {}).get("display") or "Someone"
                report["problems"].append("Something %s did could not be placed yet; it will be tried again." % who)
                continue
            if prob:
                report["problems"].append(prob)
            if result != R_APPLIED and by_thing.get(a.get("thing_id")):
                force.add(by_thing[a["thing_id"]][0])
            state["acts"][aid] = result
            ctx["save"]()
            report["acts_in"] += 1
        try:
            call(ctx, "mark_act", aid, result, scrub=scrub)
        except service.ServiceError:
            report["problems"].append("A change was applied here and sharing has not heard yet; it will be told next time.")


def _send_own(ctx, st, state, force, report, active):
    d = _sent(ctx["brain"], st)
    keep, changed = [], False
    holds = _holds(st, ctx)
    salt = _salt(ctx["brain"], st)
    for row in d["items"]:
        key = "%s/%s" % (row.get("project"), row.get("id"))
        rel = _ledger_rel(ctx["brain"], row.get("project"), row.get("ledger"))
        try:
            it, raw = _read_item(ctx, rel, row.get("id"))
        except _WriteFailed:
            keep.append(row)
            report["problems"].append("A list you share from cannot be read right now; it will be tried again.")
            continue
        if not it:                                             # gone from its list: that, or the press, takes it back
            if active:
                _remove_own(ctx, st, state, row)
            else:
                state["out"].pop(key, None)
            ctx["save"]()
            report["problems"].append("Taken back from %s because it is no longer on its list." % st["label"])
            changed = True
            continue
        body, why = gate.render_task(ctx["brain"], rel, it, raw, holds)
        if body and kinds.thread_of(ctx, st, row):
            body["thread"] = kinds.thread_of(ctx, st, row)
        if body and kinds.group_of(st, row):
            body["group"] = kinds.group_of(st, row)
        keep.append(row)
        if not body:                                           # the earlier words stay on the service; nothing new goes
            e = state["out"].setdefault(key, {})
            seen = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            if e.get("held_at") != seen:
                report["problems"].append("Your change to \u201c%s\u201d stays here: %s. %s still sees the earlier words."
                                          % (" ".join(it["text"].split()[:6]), why, st["label"]))
            e["held"], e["held_at"] = why, seen
            ctx["save"]()
            continue
        e0 = state["out"].get(key)
        if e0 and e0.get("held"):
            e0.pop("held", None)
            e0.pop("held_at", None)
        if not active:
            continue                                           # nobody else in the space: nothing goes to nobody
        e = state["out"].get(key) or {}
        if (e.get("body") != body or key in force or not e.get("thing")) and not (not e.get("thing") and e.get("held")):
            _put_own(ctx, st, state, key, body, thing_key=_thing_key(salt, rel, row.get("id")))
            ctx["save"]()
            report["sent"] += 1
            if row.get("thing") != state["out"][key]["thing"]:
                row["thing"] = state["out"][key]["thing"]
                changed = True
    if changed:
        d["items"] = keep
        _save_sent(ctx["brain"], st, d)


# ---------------------------------------------------------------- the receiving side

def _writer(st, uid):
    m = next((m for m in st.get("members") or [] if m.get("user_id") == uid), None)
    return m or {"name": "someone", "display": "Someone", "card": None, "user_id": uid}


def _take_in(ctx, st, state, heads, report):
    rel = st.get("list") or list_rel(st["name"])
    need = [h for h in heads if isinstance(h, dict) and h.get("home") and h.get("home") != ctx["uid"]
            and (h.get("id") not in state["in"] or int(h.get("version") or 0) > int(state["in"][h["id"]].get("version") or 0))]
    if not need:
        return
    rows_ = call(ctx, "get_things", [h["id"] for h in need])
    rows_.sort(key=lambda r: 0 if r.get("kind") in kinds.TEXT_KINDS else 1)   # a thread before the items that ride with it
    for row in rows_:
        writer = _writer(st, row.get("home"))
        try:
            if row.get("kind") in kinds.TEXT_KINDS + ("card-section", "message"):
                kinds.take_text(ctx, st, state, row, writer, report)
                if row.get("kind") == "thread" and state["in"].get(row["id"], {}).get("path"):
                    ctx.setdefault("thread_paths", {})[row["id"]] = state["in"][row["id"]]["path"]
                ctx["save"]()
                continue
            _take_one(ctx, st, state, rel, row, writer, report)
        except Exception:                                      # noqa: BLE001 -- one bad thing never stops a space
            report["problems"].append("Something %s shared could not be read here; it was skipped." % writer.get("display"))
        ctx["save"]()


def _take_one(ctx, st, state, rel, row, writer, report):
    tid, version = row["id"], int(row.get("version") or 0)
    e = state["in"].get(tid)
    local = e.get("local") if e else None
    it = _read_item(ctx, rel, local)[0] if local else None
    if row.get("removed_at"):
        try:
            if it:
                _close_local(ctx, rel, local, writer.get("display") or "them")
        except _WriteFailed:
            report["problems"].append("Something %s took back could not be closed on your list yet; it will be tried again."
                                      % writer.get("display"))
            return
        state["in"][tid] = dict(e or {}, version=version, removed=True, home=row.get("home"))
        report["received"] += 1
        return
    body = _norm_body(row.get("body"))
    if not it and not (e and e.get("refused")):
        have = _by_key(ctx, rel, "space:%s" % tid)            # a copy made before, and its state lost: adopt it
        if have:
            it, local = have, have["id"]
    if it and not (e or {}).get("body"):
        if _reconcile(ctx, st, state, rel, tid, it, body, version, writer, report):
            report["received"] += 1
        return
    if not it:
        if e and e.get("refused") and version <= int(e.get("version") or 0):
            return
        iid, prob, permanent = _create_local(ctx, st, rel, body, writer, tid)
        if iid is not None:                                    # made or adopted: finish it before it is trusted
            probs, failed = _match_local(ctx, rel, iid, _view(ctx, body), writer)
            prob = prob if failed else ""
            if failed and not prob:
                prob = probs[0] if probs else "Part of what was shared could not be written yet; it will be tried again."
        if prob:
            report["problems"].append(prob)
        if iid is None and not permanent:
            return                                             # not taken in: the version stays where it was
        done = not prob
        state["in"][tid] = {"local": iid, "version": version if (done or permanent) else 0,
                            "body": body if done else None, "sent": None, "home": row.get("home"),
                            "refused": bool(permanent)}
    else:
        owner, _to = _owner_for(ctx, st, _canon(ctx, body), writer)
        probs, failed = _match_local(ctx, rel, local, _view(ctx, body), writer, owner=owner)
        report["problems"] += probs
        if failed:
            return
        state["in"][tid] = {"local": local, "version": version, "body": body, "sent": None, "home": row.get("home")}
    report["received"] += 1


def _first_words(text, n=6):
    return " ".join(str(text or "").split()[:n])


def _send_one_act(ctx, tid, act, payload, words, report):
    """One act out, through this side's gate for words. True when it went (or was rightly kept here)."""
    if act in ("reply", "answer"):
        why = gate.words_refusal(ctx["brain"], payload.get("text"))
        if why:
            report["problems"].append("Your %s on \u201c%s\u201d stays here: %s." % (act, words, why))
            return False
        payload = {"text": gate.clean_words(ctx["brain"], payload["text"])}
    call(ctx, "add_act", tid, act, payload)
    report["acts_out"] += 1
    return True


def _extras(lv, rv, may_close, may_answer):
    """With no baseline: what the local copy has MORE of than the service's is this person's own (a step ticked here,
    words added to the end of the note, done or an answer where it is theirs). (target view, acts, replaced) where
    target is the service's view plus those, acts the ones to send, and replaced [(field, local value)] each local value
    that differs otherwise and gives way to the service's."""
    target = json.loads(json.dumps(rv))
    acts, replaced = [], []
    if [x[0] for x in lv["steps"]] == [x[0] for x in rv["steps"]]:
        for i, (a, b) in enumerate(zip(lv["steps"], rv["steps"])):
            if a[1] and not b[1]:
                target["steps"][i][1] = True
                acts.append(("tick", {"step": i + 1, "done": True, "text": a[0]}))
    elif lv["steps"] and lv["steps"] != rv["steps"]:
        replaced.append(("steps", " | ".join(x[0] for x in lv["steps"])))
    if lv["note"] != rv["note"]:
        if lv["note"].startswith(rv["note"]) and len(lv["note"]) > len(rv["note"]):
            add = _reply_words(_extension(rv["note"], lv["note"]))
            target["note"] = lv["note"]
            if add:
                acts.append(("reply", {"text": add}))
        elif lv["note"] and not rv["note"].startswith(lv["note"]):
            replaced.append(("note", lv["note"]))
    if lv["state"] == "done" and rv["state"] == "open":
        if may_close:
            target["state"] = "done"
            acts.append(("done", {}))
        else:
            replaced.append(("state", "done"))
    if lv["state"] == "answered" and rv["state"] == "asked":
        if may_answer:
            target["state"], target["answer"] = "answered", lv["answer"]
            acts.append(("answer", {"text": lv["answer"]}))
        else:
            replaced.append(("answer", lv["answer"]))
    if lv["text"] != rv["text"] and lv["text"]:
        replaced.append(("text", lv["text"]))
    return target, acts, replaced


def _say_replaced(report, replaced, words, who):
    for field, value in replaced:
        if field in ("text", "note"):
            report["problems"].append("Your words on \u201c%s\u201d were replaced by the newer ones from %s: %s" % (words, who, value))
        else:
            report["problems"].append("Your %s on \u201c%s\u201d was replaced by %s's: %s" % (
                {"steps": "steps", "state": "done mark", "answer": "answer"}.get(field, field), words, who, value))


def _reconcile(ctx, st, state, rel, tid, it, body, version, writer, report):
    """A local item mapped to someone else's thing with no recorded baseline: this person's own extras are sent as
    acts, everything else takes the service's value with a line for each local value replaced, then the baseline is
    recorded. False when the list could not be written (tried again next time)."""
    t = ctx["tasks"]
    lv, rv = _local_view(ctx, it), _view(ctx, body)
    owner, to = _owner_for(ctx, st, _canon(ctx, body), writer)
    target, acts, replaced = _extras(lv, rv, may_close=(owner == t.OWNER), may_answer=(to == t.OWNER))
    words = _first_words(it["text"])
    probs, failed = _match_local(ctx, rel, it["id"], target, writer, owner=owner)
    if failed:
        report["problems"] += probs
        return False
    _say_replaced(report, replaced, words, writer.get("display") or "them")
    state["in"][tid] = {"local": it["id"], "version": version, "body": body, "sent": target, "home": writer.get("user_id")}
    ctx["save"]()
    for act, payload in acts:
        _send_one_act(ctx, tid, act, payload, words, report)
    return True


def _send_acts(ctx, st, state, report):
    rel = st.get("list") or list_rel(st["name"])
    for tid, e in list(state["in"].items()):
        if not e.get("home") or e.get("removed") or not e.get("local") or not e.get("body"):
            continue
        try:
            it = _read_item(ctx, rel, e["local"])[0]
        except _WriteFailed:
            continue
        if not it:
            continue
        cur = _local_view(ctx, it)
        base = json.loads(json.dumps(e.get("sent") or _view(ctx, e.get("body"))))
        todo = []
        if it["kind"] == "task" and [s[0] for s in cur["steps"]] == [s[0] for s in base["steps"]]:
            for i, (s, b) in enumerate(zip(cur["steps"], base["steps"])):
                if s[1] != b[1]:
                    todo.append(("tick", {"step": i + 1, "done": s[1], "text": s[0]}, ("step", i)))
        if cur["note"] != base["note"]:
            add = _reply_words(_extension(base["note"], cur["note"]))
            todo.append(("reply", {"text": add}, ("note", None)) if add else (None, None, ("note", None)))
        if it["kind"] == "task" and cur["state"] != base["state"]:
            todo.append(("done" if cur["state"] == "done" else "reopen", {}, ("state", None)))
        if it["kind"] == "question" and cur["state"] == "answered" and base["state"] != "answered":
            todo.append(("answer", {"text": cur["answer"]}, ("answer", None)))
        for act, payload, (field, i) in todo:
            if act in ("reply", "answer"):
                why = gate.words_refusal(ctx["brain"], payload["text"])
                if why:
                    report["problems"].append("Your %s on “%s” stays here: %s." % (act, it["text"][:50], why))
                    act = None
                else:
                    payload = {"text": gate.clean_words(ctx["brain"], payload["text"])}
            if act:
                call(ctx, "add_act", tid, act, payload)
                report["acts_out"] += 1
            if field == "step":
                base["steps"][i] = list(cur["steps"][i])
            elif field == "note":
                base["note"] = cur["note"]
            elif field == "state":
                base["state"] = cur["state"]
            elif field == "answer":
                base["state"], base["answer"] = cur["state"], cur["answer"]
            e["sent"] = base
            ctx["save"]()                                       # recorded after each act: a later failure resends nothing
        e["sent"] = base


def _space_made(ctx, st, state, heads, report):
    """Things made in the space (home null): any member rewrites them against the version they last saw."""
    rel = st.get("list") or list_rel(st["name"])
    holds = _holds(st, ctx)
    by_id = {h["id"]: h for h in heads if isinstance(h, dict) and not h.get("home") and h.get("id")}
    mapped = {e.get("local") for e in state["in"].values() if e.get("local")}
    salt = _salt(ctx["brain"], st)

    def local_body(it):
        _ap, raw = _read_item(ctx, rel, it["id"])
        return gate.render_task(ctx["brain"], rel, it, raw, holds)

    def put(tid, version, body):
        row = {"id": tid, "space_id": st["space_id"], "kind": body["kind"],          # the key it was made with stays
               "title": body["text"][:80], "body": body, "version": version}
        return call(ctx, "put_thing", row)

    # changes on the service, and changes here, to the things already mapped
    for tid, h in by_id.items():
        e = state["in"].get(tid)
        if e is None or not e.get("local"):
            continue
        try:
            _space_one(ctx, st, state, rel, tid, h, e, local_body, put, report)
        except _WriteFailed:
            report["problems"].append("A change to something made in the space could not be written yet; it will be tried again.")
        except service.ServiceError:
            raise
        except Exception:                                      # noqa: BLE001
            report["problems"].append("Something made in the space could not be read here; it was skipped.")
        ctx["save"]()

    # made elsewhere in the space and new here
    new = [tid for tid in by_id if tid not in state["in"]
           or (not state["in"][tid].get("local") and not state["in"][tid].get("refused"))]
    if new:
        # what this brain made itself and lost track of (a state that did not survive) is found by its salted key
        mine_by_key = {_thing_key(salt, ctx["uid"], it["id"]): it["id"] for it in _items(ctx, rel)
                       if it["id"] not in mapped and not str(it.get("key") or "").startswith("space:")}
        for row in call(ctx, "get_things", new):
            writer = _writer(st, row.get("updated_by"))
            if row.get("key") in mine_by_key:
                state["in"][row["id"]] = {"local": mine_by_key[row["key"]], "version": 0, "body": None, "sent": None, "home": None}
                mapped.add(mine_by_key[row["key"]])
                ctx["save"]()
                continue
            try:
                body = _norm_body(row.get("body"))
                iid, prob, permanent = _create_local(ctx, st, rel, body, writer, row["id"])
                if iid is not None:                            # made or adopted: finish it before it is trusted
                    probs_, failed_ = _match_local(ctx, rel, iid, _view(ctx, body), writer)
                    prob = prob if failed_ else ""
                    if failed_ and not prob:
                        prob = probs_[0] if probs_ else "Part of what was shared could not be written yet; it will be tried again."
                if prob:
                    report["problems"].append(prob)
                if iid is None and not permanent:
                    continue
                state["in"][row["id"]] = {"local": iid, "version": int(row.get("version") or 0) if not prob or permanent else 0,
                                          "body": body if not prob else None, "sent": None, "home": None,
                                          "refused": bool(permanent)}
                mapped.add(iid)
                report["received"] += 1
            except Exception:                                  # noqa: BLE001
                report["problems"].append("Something made in the space could not be read here; it was skipped.")
            ctx["save"]()

    # made here and new to the space: keyed by this brain's salt and the item, so a second try finds the first
    have_keys = {h.get("key"): h for h in heads if isinstance(h, dict) and not h.get("home") and h.get("key")}
    for it in _items(ctx, rel):
        if it["id"] in mapped or it["id"] in state["local_only"] or it.get("key", "") and str(it.get("key")).startswith("space:"):
            continue
        if it["mark"] in ("x", "a"):
            continue                                           # an item closed before it was ever shared stays here
        body, why = local_body(it)
        if not body:
            state["local_only"].append(it["id"])
            report["problems"].append("“%s” stays on your list only: %s." % (it["text"][:50], why))
            ctx["save"]()
            continue
        key = _thing_key(salt, ctx["uid"], it["id"])
        if key in have_keys:
            h = have_keys[key]
            state["in"][h["id"]] = {"local": it["id"], "version": 0, "body": None, "sent": None, "home": None}
        else:
            origin = {"user": ctx["uid"], "local": it["id"]}
            body = dict(body, origin=origin)
            got = call(ctx, "put_thing", {"id": None, "space_id": st["space_id"], "kind": body["kind"], "home": None,
                                          "key": key, "title": body["text"][:80], "body": body, "removed_at": None})
            state["in"][got["id"]] = {"local": it["id"], "version": got["version"], "body": body, "sent": None, "home": None,
                                      "origin": origin}
            report["sent"] += 1
        ctx["save"]()


def _space_one(ctx, st, state, rel, tid, h, e, local_body, put, report):
    it = _read_item(ctx, rel, e.get("local"))[0]
    if not it:
        return
    base = _view(ctx, e.get("body")) if e.get("body") else None
    mine, _why = local_body(it)
    if not mine:
        return
    lv = _view(ctx, mine)
    if base is None:                                           # no baseline: own extras are kept, the rest is the service's
        remote_row = call(ctx, "get_things", [tid])[0]
        rv = _view(ctx, remote_row.get("body"))
        writer = _writer(st, remote_row.get("updated_by"))
        target, _acts, replaced = _extras(lv, rv, may_close=True, may_answer=True)
        probs, failed = _match_local(ctx, rel, it["id"], target, writer)
        if failed:
            report["problems"] += probs
            return
        if remote_row.get("updated_by") != ctx["uid"]:
            _say_replaced(report, replaced, _first_words(it["text"]), writer.get("display") or "them")
        e.update(version=int(remote_row.get("version") or 0), body=_norm_body(remote_row.get("body")), sent=None)
        if target != rv:
            it = _read_item(ctx, rel, it["id"])[0]
            body, _w = local_body(it)
            try:
                got = put(tid, e["version"], dict(body, origin=e["origin"]) if e.get("origin") else body)
                e.update(version=got["version"], body=got["body"])
                report["sent"] += 1
            except service.Conflict:
                report["problems"].append("\u201c%s\u201d changed on both sides; it will be tried again next time" % it["text"][:50])
        report["received"] += 1
        return
    newer = int(h.get("version") or 0) > int(e.get("version") or 0)
    if base is None:
        newer, base = True, lv                                 # never applied yet: take the service's copy first
    changed_here = lv != base
    if not newer and not changed_here:
        return
    remote_row = call(ctx, "get_things", [tid])[0] if newer else None
    version = int(remote_row.get("version") or 0) if newer else e.get("version")
    rv = _view(ctx, remote_row.get("body")) if newer else base
    for _ in range(4):
        merged, clashes = _merge(base, lv, rv) if changed_here else (rv, [])
        writer = _writer(st, (remote_row or {}).get("updated_by"))
        probs, failed = _match_local(ctx, rel, it["id"], merged, writer)
        if failed:
            report["problems"] += probs                        # never send this brain's stale copy over a newer one
            return
        for f, other in clashes:
            report["problems"].append("%s and you both changed the %s of “%s”; yours was kept, theirs read: %s"
                                      % (writer.get("display") or "Someone", "words" if f == "text" else f,
                                         merged["text"][:50], other if isinstance(other, str) else json.dumps(other)))
        if newer:
            report["received"] += 1
        if merged == rv:
            e.update(version=version, body=_norm_body(remote_row.get("body")) if remote_row else e.get("body"), sent=None)
            return
        it = _read_item(ctx, rel, it["id"])[0]
        body, _w = local_body(it)
        try:
            got = put(tid, version, dict(body, origin=e["origin"]) if e.get("origin") else body)
            report["sent"] += 1
            e.update(version=got["version"], body=got["body"], sent=None)
            return
        except service.Conflict:
            remote_row = call(ctx, "get_things", [tid])[0]
            version, base, lv, rv = int(remote_row.get("version") or 0), rv, _view(ctx, body), _view(ctx, remote_row.get("body"))
            newer, changed_here = True, True
    report["problems"].append("“%s” kept changing on both sides; it will be tried again next time" % it["text"][:50])


# ---------------------------------------------------------------- sync

def _count_words(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def _unsent(ctx, st, state):
    """How many changes of this person's had not gone yet: copies changed here since the last baseline sent, and
    their own changes held back by the gate."""
    rel = st.get("list") or list_rel(st["name"])
    n = sum(1 for e in state["out"].values() if isinstance(e, dict) and e.get("held"))
    for e in state["in"].values():
        if not e.get("home") or e.get("removed") or not e.get("local") or not e.get("body"):
            continue
        try:
            it = _read_item(ctx, rel, e["local"])[0]
        except _WriteFailed:
            continue
        if it and _local_view(ctx, it) != (e.get("sent") or _view(ctx, e.get("body"))):
            n += 1
    return n


def _tell_refused(ctx, st, state, report):
    """Each act of this person's that the home refused is said once, and the local copy is put back at this check."""
    told = state.setdefault("told", [])
    rel = st.get("list") or list_rel(st["name"])
    names = {"tick": "tick", "reply": "reply", "done": "done mark", "reopen": "reopening", "answer": "answer"}
    for a in ctx.get("my_acts") or []:
        if a.get("space_id") != st["space_id"] or a.get("id") in told or not str(a.get("result") or "").startswith("refused"):
            continue
        e = state["in"].get(a.get("thing_id")) or {}
        it = _read_item(ctx, rel, e.get("local"))[0] if e.get("local") else None
        home = _writer(st, e.get("home"))
        report["problems"].append("%s's brain did not take your %s on \u201c%s\u201d: %s." % (
            home.get("display") or "The other", names.get(a.get("act"), "change"), _first_words((it or {}).get("text") or "it"),
            str(a["result"])[len("refused: "):]))
        told.append(a["id"])
        if e:
            e["version"] = 0                                   # the home's copy comes back in at this check
        ctx["save"]()


def _rebuild(ctx, st, state, heads, report):
    """What the state should know and does not (it was deleted, or this is the same brain on another computer):
    this brain's own shared items from sent.json's thing ids (else the salted key), items made from someone else's
    thing from their `space:<thing id>` key, and things made in the space from their body's `origin`."""
    brain, uid = ctx["brain"], ctx["uid"]
    rel = st.get("list") or list_rel(st["name"])
    by_id = {h["id"]: h for h in heads if isinstance(h, dict) and h.get("id")}
    salt = _salt(brain, st)
    d = _sent(brain, st)
    rows_changed, want = False, {}
    for row in d["items"]:
        key = "%s/%s" % (row.get("project"), row.get("id"))
        if (state["out"].get(key) or {}).get("thing"):
            continue
        tid = row.get("thing")
        if not tid or tid not in by_id:
            k = _thing_key(salt, _ledger_rel(brain, row.get("project"), row.get("ledger")), row.get("id"))
            tid = next((h["id"] for h in heads if h.get("home") == uid and h.get("key") == k), None)
        if tid and tid in by_id and not by_id[tid].get("removed_at"):
            want[tid] = (key, row)
    if want:
        for got in call(ctx, "get_things", list(want)):
            key, row = want[got["id"]]
            state["out"][key] = dict(state["out"].get(key) or {}, thing=got["id"], version=got["version"],
                                     body=got.get("body"), key=got.get("key") or "")
            if row.get("thing") != got["id"]:
                row["thing"], rows_changed = got["id"], True
    if rows_changed:
        _save_sent(brain, st, d)
    local = _items(ctx, rel)
    by_key = {str(i.get("key")): i["id"] for i in local if str(i.get("key") or "").startswith("space:")}
    mapped = {e.get("local") for e in state["in"].values() if e.get("local")}
    for h in heads:
        if not isinstance(h, dict) or h.get("id") in state["in"] or h.get("home") == uid:
            continue
        lid = by_key.get("space:%s" % h["id"])
        if lid:
            state["in"][h["id"]] = {"local": lid, "version": 0, "body": None, "sent": None, "home": h.get("home")}
            mapped.add(lid)
    unknown = [h["id"] for h in heads if isinstance(h, dict) and not h.get("home") and h.get("id") not in state["in"]]
    if unknown:
        have = {i["id"] for i in local}
        for got in call(ctx, "get_things", unknown):
            o = _norm_body(got.get("body")).get("origin")
            if o and o["user"] == uid and o["local"] in have and o["local"] not in mapped:
                state["in"][got["id"]] = {"local": o["local"], "version": 0, "body": None, "sent": None, "home": None,
                                          "origin": o}
                mapped.add(o["local"])
    ctx["save"]()


def _sync_space(ctx, st, svc_space, acts, memberships=None):
    report = {"name": st["name"], "label": st["label"], "sent": 0, "received": 0, "acts_in": 0, "acts_out": 0, "problems": []}
    brain = ctx["brain"]
    if svc_space is None:
        left = (memberships or {}).get(st["space_id"])
        if left:                                               # proof: this person's own row says they left
            n = _unsent(ctx, st, _load_state(brain, st["name"]))
            _detach_local(brain, st, "this person left it on the service")
            report["problems"].append("You are no longer in the space with %s; what it holds stays here as it is.%s"
                                      % (st["label"], (" %s of yours had not gone yet." % _count_words(n, "change")) if n else ""))
        else:
            report["problems"].append("The space with %s could not be seen just now; nothing changed." % st["label"])
        return report
    members = _members_from(ctx, svc_space, st.get("members"))
    gone = [m for m in members if m.get("left") and m.get("user_id") != ctx["uid"]
            and not any(o.get("user_id") == m.get("user_id") and o.get("left") for o in st.get("members") or [])]
    if members != st.get("members"):
        st["members"] = members
        _save_stamp(brain, st)
    if gone:
        n = _unsent(ctx, st, _load_state(brain, st["name"]))
        unsent = (" %s of yours had not been sent yet." % _count_words(n, "change")) if n else ""
        for m in gone:
            who = m.get("display") or "Your partner"
            if st.get("kind") == "team":
                report["problems"].append("%s left %s." % (who, st["label"]))
            else:
                report["problems"].append("%s stopped sharing with you; what each of you shared stays here as it was.%s" % (who, unsent))
    active = [m for m in members if m.get("user_id") and m["user_id"] != ctx["uid"] and not m.get("left")]
    # a pair whose other person left is over on this side too (each keeps what the other shared, as it stood): this
    # check still runs to the end, so the last of what they shared is here, and the caller then ends it (2026-11-10)
    if st.get("kind") != "team" and not active and any(m.get("left") and m.get("user_id") != ctx["uid"] for m in members):
        report["ended"] = True
    state = _load_state(brain, st["name"])
    ctx["save"] = lambda: _save_state(brain, st["name"], state)
    force = set()
    try:
        first = call(ctx, "heads", st["space_id"])
        ctx["heads"] = {h["id"]: h for h in first if isinstance(h, dict) and h.get("id")}
        _rebuild(ctx, st, state, first, report)
        kinds.rebuild(ctx, st, state, first)
        ctx["thread_paths"] = {tid: e.get("path") for tid, e in state["in"].items() if e.get("kind") == "thread" and e.get("path")}
        _tell_refused(ctx, st, state, report)
        _apply_acts(ctx, st, state, acts, force, report)
        kinds.settle_proposals(ctx, st, state, report)
        if not ctx.get("out"):
            for proj in list((st.get("projects") or {})):       # a project shared whole: what is new on it goes too
                kinds.sweep_project(ctx, st, proj)
            kinds.send_texts(ctx, st, state, report, bool(active))
            _send_own(ctx, st, state, force, report, bool(active))
        elif state.get("out") or (st.get("projects") or {}):
            # an employer's computer: what this brain shared stays where it is until the yes (or, with it, a press);
            # what others shared still comes in below, and answers to it still go
            report["problems"].append("What you shared with %s is not being sent from this computer. %s" % (st["label"], ctx["out"]))
        _send_acts(ctx, st, state, report)                    # before taking in: a newer copy never eats an unsent change
        kinds.send_edits(ctx, st, state, report)
        heads = call(ctx, "heads", st["space_id"])
        _take_in(ctx, st, state, heads, report)
        _space_made(ctx, st, state, heads, report)
    finally:
        _save_state(brain, st["name"], state)
    return report


def _line(reports, reason=""):
    if reason:
        return reason
    if not reports:
        return "Nothing is shared from this brain yet."
    parts = []
    for r in reports:
        bits = []
        if r["sent"]:
            bits.append("%d sent" % r["sent"])
        if r["received"]:
            bits.append("%d received" % r["received"])
        if r["acts_in"]:
            bits.append("%d change%s from %s applied here" % (r["acts_in"], "" if r["acts_in"] == 1 else "s", r["label"]))
        if r["acts_out"]:
            bits.append("%d of yours sent back" % r["acts_out"])
        if bits:
            parts.append("with %s: %s" % (r["label"], ", ".join(bits)))
    probs = sum(len(r["problems"]) for r in reports)
    head = ("Shared " + "; ".join(parts) + ".") if parts else "Nothing new was shared."
    return head + (" %d thing%s to look at." % (probs, "" if probs == 1 else "s") if probs else "")


def sync(brain, on_purpose=False, only=None):
    """Every attached service space (or the one named `only`), under its lock. Returns {ok, reason, spaces, line}."""
    brain = share.brain_root(brain)
    try:
        ctx = _ctx(brain, on_purpose)
    except Refused as e:
        return {"ok": False, "reason": str(e), "spaces": [], "line": str(e)}
    try:
        listed = [s for s in call(ctx, "spaces") if isinstance(s, dict) and s.get("id")]
        ctx["notices"] = []
        _finish_joins(ctx, listed)
        svc_spaces = {s["id"]: s for s in listed}
        memberships = {m.get("space_id"): m.get("left_at") for m in call(ctx, "my_memberships") if isinstance(m, dict)}
        ctx["my_acts"] = [a for a in call(ctx, "my_acts") if isinstance(a, dict)]
        acts = call(ctx, "acts_for")
    except service.ServiceError as e:
        return {"ok": False, "reason": str(e), "spaces": [], "line": str(e)}
    stamps, elsewhere, kept_elsewhere = [], 0, []
    for s in _service_stamps(brain):
        if only and s["name"] != _slug(only):
            continue
        owner = s.get("me_user") or next((m.get("user_id") for m in s.get("members") or []
                                          if m.get("name") == s.get("me") and m.get("user_id")), None)
        if owner != ctx["uid"]:
            elsewhere += 1                                     # joined under another sign-in: left exactly as it is
            continue
        if not s.get("me_user"):
            s["me_user"] = owner
            _save_stamp(brain, s)
        if s.get("space_id") in svc_spaces:                    # a space no longer listed goes on to the proof of leaving
            try:
                here, why = _host_ok(brain, s, ctx)
            except service.ServiceError as e:
                here, why = False, str(e)
            if not here:
                kept_elsewhere.append(why)
                continue
        stamps.append(s)
    note = ("%d space%s belong%s to another sign-in and %s left alone." % (
        elsewhere, "" if elsewhere == 1 else "s", "s" if elsewhere == 1 else "", "was" if elsewhere == 1 else "were")) if elsewhere else ""
    note = " ".join(x for x in [note] + sorted(set(kept_elsewhere)) if x)
    if not stamps:
        return {"ok": True, "reason": "", "spaces": [], "line": " ".join(x for x in (_line([]), note) if x)}
    reports = []
    for st in stamps:
        with _SpaceLock(brain, st["name"]) as ok:
            if not ok:
                reports.append({"name": st["name"], "label": st["label"], "sent": 0, "received": 0, "acts_in": 0,
                                "acts_out": 0, "problems": ["This space is already being checked; try again in a moment."]})
                continue
            try:
                r_ = _sync_space(ctx, st, svc_spaces.get(st["space_id"]), acts, memberships)
                if r_.pop("ended", None) and (st.get("state") or "attached") == "attached":
                    _detach_local(brain, st, "the other person stopped sharing")
                reports.append(r_)
            except service.ServiceError as e:
                reports.append({"name": st["name"], "label": st["label"], "sent": 0, "received": 0, "acts_in": 0,
                                "acts_out": 0, "problems": [str(e)]})
            except _WriteFailed:
                reports.append({"name": st["name"], "label": st["label"], "sent": 0, "received": 0, "acts_in": 0,
                                "acts_out": 0, "problems": ["A list here could not be read or written; it will be tried again."]})
    crossed = sum(r["sent"] + r["received"] + r["acts_in"] + r["acts_out"] for r in reports)
    if ctx.get("notices") and reports:
        reports[0]["problems"] += ctx["notices"]
    line = " ".join(x for x in (_line(reports), note) if x)
    if crossed:
        share._log(brain, "SYNCED", "shared/ -- the sharing service: %s" % re.sub(r"\s+\d+ things? to look at\.$", "", line))
    return {"ok": True, "reason": "", "spaces": reports, "line": line}


# ---------------------------------------------------------------- round three: the other kinds (skills/sharing/kinds.py)

class _Self:
    """The engine's own names, read at call time, for kinds.py."""

    def __getattr__(self, k):
        return globals()[k]


kinds = _load("sharing_kinds_mod_%x" % id(globals()), os.path.join(HERE, "kinds.py"))
kinds.E = _Self()
share_file = kinds.share_file
share_thread = kinds.share_thread
share_drawing = kinds.share_drawing
share_card_section = kinds.share_card_section
take_back_thing = kinds.take_back_thing
proposals = kinds.proposals
take_section = kinds.take_section
leave_section = kinds.leave_section
send_message = kinds.send_message
messages = kinds.messages
mark_read = kinds.mark_read
set_auto_take = kinds.set_auto_take
space_view = kinds.space_view
mark_opened = kinds.mark_opened
share_project = kinds.share_project
unshare_project = kinds.unshare_project

# ---------------------------------------------------------------- a mailbox per person (skills/sharing/mailbox.py)

mailbox = _load("sharing_mailbox_mod_%x" % id(globals()), os.path.join(HERE, "mailbox.py"))
mailbox.E = _Self()
make_mailbox = mailbox.make
mailboxes = mailbox.boxes
send_to = mailbox.send
