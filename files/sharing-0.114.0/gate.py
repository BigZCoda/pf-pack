#!/usr/bin/env python3
"""skills/sharing/gate.py -- what never crosses into a shared space, and the cleaning of what does.

    render_task(brain, ledger_rel, item, raw_line, holds=None)  -> (body, "") or (None, why)
    refusal(brain, ledger_rel, item, raw_line)                  -> why it stays home, or ""
    words_refusal(brain, text)                                  -> why these words (a reply, an answer) stay home, or ""
    clean_words(brain, text)                                    -> the words as they may cross
    is_key_file(rel)                                            -> True for a key file (KEY_FILES)
    token_in(text)                                              -> True when a token or key shape is in it

`item` is one ledger item as skills/brain-tasks/tasks.py parses it (parse_item), `raw_line` its line as written.
`holds` says who is in the space, from this brain's side: {"me": <this brain's person, bare>, "me_user": <this
person's user id on the service>, "others": [{"name": <their short name>, "card": <their card's slug here, or None>,
"user_id": <their user id, or None while invited>}]}. `why` is one plain clause a press can say after "It stays home
because": "it is marked private".

Self-contained on purpose: every brain that shares carries this one gate. Standard library only. Spec:
skills/sharing/readme.md, Round two.
"""
import datetime as dt
import fnmatch
import json
import os
import posixpath
import re
import unicodedata

SETTINGS_REL = "viewer/settings.json"
REGISTRY_REL = "context/holon-registry.json"
HELD_BACK_REL = "skills/team-brain/people-held-back.json"
DEFAULT_PERSONAL = ["thoughts/", "questions/"]
PERSONAL_IF_THERE = ["astrology/", "characters/", "profiles/"]

# ---------------------------------------------------------------- key files: one list, here
# Every key file a brain keeps sits at its root. The patterns cover each name the viewer's own never-read list holds
# today (the test checks that against the viewer), so a new key file named the usual way is covered before anyone
# remembers to list it. The sign-in is covered under any letter case and with the temporary name it is written through.
KEY_FILES = [
    "*_key.txt",             # a provider's key, at the brain root
    "*token*.txt",           # a token, at the brain root
    "*Token*.txt",
    "* API.txt", "API*.txt",  # a key file named for the app or API it opens, at the brain root
    "* Key.txt", "* key.txt",  # a key file named in words ("Old Gemini Key.txt"), at the brain root
    "id_rsa*", "id_ed25519*", "*.pem", "*.p12",   # a private key, anywhere
    ".env", ".env.*",        # anywhere
    "viewer/sharing-signin.json*",
    "sharing-signin.json*",  # the sign-in by its name alone, wherever a copy of it might turn up
]
_ANY_CASE = ("viewer/sharing-signin.json*", "sharing-signin.json*")


def _clean_rel(rel):
    r = str(rel or "").replace("\\", "/").strip()
    r = posixpath.normpath("/" + r).lstrip("/") if r else ""
    return "" if r == "." else r


def is_key_file(rel):
    """True for a path KEY_FILES names. The .txt names count at the brain root; the sign-in anywhere, any case."""
    r = _clean_rel(rel)
    base = r.rsplit("/", 1)[-1]
    for pat in KEY_FILES:
        any_case = pat in _ANY_CASE
        subj_full, subj_base, p = (r.lower(), base.lower(), pat.lower()) if any_case else (r, base, pat)
        if "/" in pat:
            if fnmatch.fnmatchcase(subj_full, p):
                return True
        elif fnmatch.fnmatchcase(subj_base, p):
            if pat.endswith(".txt") and "/" in r:
                continue
            return True
    return False


# ---------------------------------------------------------------- token and key shapes
TOKEN_PATTERNS = [re.compile(p) for p in (
    r"pf_tok_[A-Za-z0-9]{10,}", r"pfk_[A-Za-z0-9]{10,}", r"frt_[A-Za-z0-9]{10,}", r"pf_ext_[A-Za-z0-9]{10,}",
    r"AIza[0-9A-Za-z_-]{20,}",                       # a Google key
    r"ya29\.[0-9A-Za-z_-]{20,}",                     # a Google sign-in token
    r"\bsk-[A-Za-z0-9_-]{16,}",                       # OpenAI and Anthropic keys (sk-..., sk-ant-..., sk-proj-...)
    r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{10,}",    # Stripe keys
    r"sb_secret_[A-Za-z0-9_-]{8,}",                   # a Supabase secret key
    r"ghp_[A-Za-z0-9]{16,}", r"github_pat_[A-Za-z0-9_]{16,}",
    r"\bglpat-[A-Za-z0-9_-]{16,}",                    # a GitLab token
    r"\bhf_[A-Za-z0-9]{20,}",                         # a Hugging Face token
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}", r"\bxapp-[A-Za-z0-9-]{10,}",   # Slack tokens
    r"\bnpm_[A-Za-z0-9]{20,}", r"\bpypi-[A-Za-z0-9_-]{16,}",          # package registry tokens
    r"\bshpat_[A-Fa-f0-9]{16,}",                      # a Shopify token
    r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}",  # a SendGrid key
    r"\bAKIA[0-9A-Z]{16}\b",                          # an AWS access key
    r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}",             # a bearer token written out
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\b[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b",   # a JWT: three long dotted parts
    r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}",      # a JWT whose parts are short
)]
# where a key starts: the text after one, with its whitespace closed up, is checked again ("pf_tok_abc def...") when
# what follows looks like a key (four digits, or mixed case); a run of plain lower-case words never does
KEY_START = re.compile(r"pf_tok_|pfk_|frt_|pf_ext_|AIza|ya29\.|\bsk-|\b[sr]k_(?:live|test)_|sb_secret_|ghp_|github_pat_"
                       r"|\bglpat-|\bhf_|\bxox[abprs]-|\bxapp-|\bnpm_|\bpypi-|\bshpat_|\bAKIA|\beyJ")
LONG_RUN = re.compile(r"[A-Za-z0-9_+=]{32,}")          # unbroken: a hyphen, a slash or a dot ends a run
HTTP_LINK = re.compile(r"https?://\S+", re.I)
HOST_TOKEN = re.compile(r"(?<![\w.@/-])[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/\S*")   # example.com/... , a link without its scheme
HIDING = {0x034F, 0x115F, 0x1160, 0x3164, 0xFFA0}


def unseen_out(text):
    """The text without the characters that hide a key or a name from a pattern: every format character (zero-width
    spaces, joiners, bidi marks), the combining grapheme joiner, the Hangul fillers, and the variation selectors."""
    out = []
    for ch in str(text or ""):
        o = ord(ch)
        if unicodedata.category(ch) == "Cf" or o in HIDING or 0xFE00 <= o <= 0xFE0F or 0xE0100 <= o <= 0xE01EF:
            continue
        out.append(ch)
    return "".join(out)


def _looks_like_key(run):
    digits = sum(c.isdigit() for c in run)
    kinds = sum((any(c.islower() for c in run), any(c.isupper() for c in run), digits > 0))
    return kinds >= 2 and digits >= 4


def long_key_run(text):
    """The general rule: outside an http(s) link, a run of 32 or more of A-Za-z0-9_+/=- that mixes two of lower case,
    upper case and digits and has four or more digits is key-shaped."""
    t = HOST_TOKEN.sub(" ", HTTP_LINK.sub(" ", unseen_out(text)))
    return any(_looks_like_key(m.group(0)) for m in LONG_RUN.finditer(t))


def token_in(text):
    t = unseen_out(text)
    if any(p.search(t) for p in TOKEN_PATTERNS):
        return True
    for m in KEY_START.finditer(t):
        if len(re.match(r"\S*", t[m.end():]).group(0)) < 8:
            continue                                           # the piece right after the prefix is too short to be a key
        after = re.sub(r"\s+", "", t[m.end():m.end() + 160])
        if not (sum(c.isdigit() for c in after[:60]) >= 4 or (re.search(r"[a-z]", after[:60]) and re.search(r"[A-Z]", after[:60]))):
            continue
        window = t[m.start():m.end()] + after
        if any(p.match(window) or p.search(window[:120]) for p in TOKEN_PATTERNS):
            return True
    return False


# ---------------------------------------------------------------- reading the brain
def _p(brain, rel):
    return os.path.join(brain, *str(rel).split("/"))


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def settings(brain):
    d = _read_json(_p(brain, SETTINGS_REL))
    return d if isinstance(d, dict) else {}


def registry_rows(brain):
    d = _read_json(_p(brain, REGISTRY_REL))
    return [h for h in (d or {}).get("holons", []) if isinstance(h, dict)] if isinstance(d, dict) else []


def _norm(rel):
    r = str(rel or "").replace("\\", "/").strip()
    while r.startswith("./"):
        r = r[2:]
    return r.lstrip("/")


def _covers(h, rel):
    hp = _norm(h.get("path")).rstrip("/")
    return bool(hp) and (rel == hp or rel.startswith(hp + "/"))


def row_of(brain, ledger_rel):
    """The registry row whose `tasks` is this ledger, else the most specific row whose path covers it; None."""
    rel = _norm(ledger_rel)
    rows = registry_rows(brain)
    own = next((h for h in rows if _norm(h.get("tasks")) == rel), None)
    if own:
        return own
    best, best_len = None, -1
    for h in rows:
        hp = _norm(h.get("path")).rstrip("/")
        if _covers(h, rel) and len(hp) > best_len:
            best, best_len = h, len(hp)
    return best


def _covering_says_employer(brain, ledger_rel):
    """True when the ledger's own row, ANY row whose path covers it, or any row on the parent chain of either (by
    `parent`, or by a row listing it among its `children`) says sharing: employer."""
    rel = _norm(ledger_rel)
    rows = registry_rows(brain)
    by_id = {h.get("id"): h for h in rows if h.get("id")}
    parent = {}
    for h in rows:
        if h.get("parent"):
            parent.setdefault(h.get("id"), set()).add(h["parent"])
        for c in h.get("children") or []:
            parent.setdefault(c, set()).add(h.get("id"))
    todo = [h for h in rows if _norm(h.get("tasks")) == rel or _covers(h, rel)]
    seen = set()
    while todo:
        h = todo.pop()
        hid = h.get("id")
        if hid in seen:
            continue
        seen.add(hid)
        if str(h.get("sharing") or "").lower() == "employer":
            return True
        todo += [by_id[p] for p in parent.get(hid, ()) if p in by_id]
    return False


def personal_folders(brain):
    st = settings(brain)
    got = st.get("sharing_personal")
    out = [str(x).strip().rstrip("/") + "/" for x in (got if isinstance(got, list) else DEFAULT_PERSONAL) if str(x).strip()]
    for f in PERSONAL_IF_THERE:
        if os.path.isdir(_p(brain, f.rstrip("/"))) and f not in out:
            out.append(f)
    return out


def held_back(brain):
    """(ok, pattern or None): the held-back list's drop_lines_naming. No file: (True, None). A file that does not read:
    (False, None), and the gate refuses everything (it fails closed)."""
    path = _p(brain, HELD_BACK_REL)
    if not os.path.isfile(path):
        return True, None
    d = _read_json(path)
    if not isinstance(d, dict):
        return False, None
    pats = [p for p in ((d.get("drop_lines_naming") or {}).get("patterns") or []) if isinstance(p, str) and p]
    try:
        return True, (re.compile("|".join("(?:%s)" % p for p in pats), re.I) if pats else None)
    except re.error:
        return False, None


def _names_one(named, text):
    """Whether a held-back name is in the text, with hidden characters out and every run of whitespace one space."""
    return bool(named) and bool(named.search(" ".join(unseen_out(text).split())))


def list_label(brain, ledger_rel):
    h = row_of(brain, ledger_rel)
    if not h:
        return ""
    labels = settings(brain).get("project_labels")
    lab = labels.get(h.get("id")) if isinstance(labels, dict) else None
    return str(lab or re.sub(r"\s*\(.*\)\s*$", "", str(h.get("name") or h.get("id") or "")))


# ---------------------------------------------------------------- refusal
PRIVATE_RE = re.compile(r"\\?\[\s*private\s*\\?\]", re.I)


def words_refusal(brain, text):
    """Why words someone writes on a shared copy (a reply, an answer) stay on this computer, or "". The home runs the
    same check, with its own held-back names, on what arrives."""
    t = unseen_out(text)
    if PRIVATE_RE.search(" ".join(t.split())):
        return "it is marked private"
    if token_in(t) or long_key_run(t):
        return "it holds something shaped like a password or a key"
    ok, named = held_back(brain)
    if not ok:
        return "the list of people who never cross cannot be read"
    if _names_one(named, t):
        return "it names someone who never crosses"
    return ""


def refusal(brain, ledger_rel, item, raw_line):
    """Why this item stays home, one plain clause, or ""."""
    line = unseen_out(raw_line)
    rel = _norm(ledger_rel)
    if PRIVATE_RE.search(" ".join(line.split())):
        return "it is marked private"
    if token_in(line):
        return "it holds something shaped like a password or a key"
    if not item:
        return "its line does not read as a task or a question"
    words = [item.get("text") or "", item.get("note") or "", item.get("options") or "", item.get("answer") or ""] \
        + [s.get("text") or "" for s in _steps(item)]
    if any(long_key_run(w) for w in words):
        return "it holds something shaped like a password or a key"
    if "/" not in rel:
        return "its list sits at the top of the brain, which stays home"
    if any(rel.lower().startswith(f.lower()) for f in personal_folders(brain)):
        return "its list is in a personal folder"
    if is_key_file(rel):
        return "it is a key file"
    if _covering_says_employer(brain, rel):
        return "its list belongs to an employer"
    ok, named = held_back(brain)
    if not ok:
        return "the list of people who never cross cannot be read"
    if named and any(_names_one(named, w) for w in words):
        return "its words name someone who never crosses"
    return ""


# ---------------------------------------------------------------- cleaning
# A path is removed from where it starts (a drive letter, \\, ~/ or a leading /) through the LAST separator of that
# path, then its last part up to its first space, or through its extension when it has one within a few words.
# A path starts after anything but a letter, digit, dot, slash, tilde or hyphen: after a space, a bracket, a quote, =,
# : or a backtick (so "example.com/pricing", "and/or", "11/09" and "$19.99/29.99" never start one).
PATH_START = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\(?=[^\s\\])|(?<![A-Za-z0-9.~/\\-])~[\\/]"
                        r"|(?<![A-Za-z0-9./~\\-])/(?=[A-Za-z_.][^\s/]*/)")
LINK_START = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://")
PATH_END_CHARS = "`\"')(]<>,;|\n"                             # what closes a path written inside a sentence
TOP_FOLDER_PATH = re.compile(r"(?<![\w/.:@~\\-])([A-Za-z_][A-Za-z0-9_.-]*)/((?:[A-Za-z0-9_.-]+/)*)([A-Za-z0-9_.-]+)/?(?![\w/])")
LAST_PART_EXT = re.compile(r"[^\s\\/@]*(?: [^\s\\/@]+){0,3}?\.[A-Za-z][A-Za-z0-9]{0,7}\b")
OTHER_LINK_RE = re.compile(r"\b(?!https?://)[A-Za-z][A-Za-z0-9+.-]*://\S*", re.I)
LOCAL_URL_RE = re.compile(r"\bhttps?://(?:127\.0\.0\.1|localhost|\[::1\]|0\.0\.0\.0)(?::\d+)?[^\s`'\"<>)\]]*", re.I)
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|([^\]]+))?\]\]")
BACKSLASH_REL_RE = re.compile(r"(?<![\w\\:])((?:[A-Za-z_][A-Za-z0-9_.-]*\\)+[A-Za-z0-9_.-]+)(?![\w\\])")
REL_PATH_RE = re.compile(r"(?<![\w/.:-])((?:[A-Za-z_.][A-Za-z0-9_.-]*/)+([A-Za-z0-9_ .-]*?[A-Za-z0-9_-])\.[A-Za-z][A-Za-z0-9]{0,7})(?![\w/])")
FOLDER_RE = re.compile(r"(?<![\w/.:-])(?:[A-Za-z_.][A-Za-z0-9_.-]*/)+([A-Za-z0-9_.-]+)/(?![\w/])")
ID_RE = re.compile(r"(?<![A-Za-z0-9-])([TQ])-\d{4}(?![\w-])")


def _strip_paths(s):
    out, i = [], 0
    while True:
        m = PATH_START.search(s, i)
        if not m:
            out.append(s[i:])
            return "".join(out)
        out.append(s[i:m.start()])
        start = m.end()
        lead = m.group(0)
        sep = "\\" if ("\\" in lead) else "/"
        end = len(s)                                           # up to the next path or link, or a closing mark
        for nxt in (PATH_START.search(s, start), LINK_START.search(s, start)):
            if nxt:
                end = min(end, nxt.start())
        for ch in PATH_END_CHARS:
            k = s.find(ch, start, end)
            if k != -1:
                end = k
        last = s.rfind(sep, start, end)
        rest_at = last + 1 if last >= start else start
        rest = s[rest_at:end]
        e = LAST_PART_EXT.match(rest)
        cut = rest_at + (e.end() if e else re.match(r"\S*", rest).end())
        out.append("[path removed]")
        i = cut


def _file_name(path):
    base = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"\.[A-Za-z][A-Za-z0-9]{0,7}$", "", base)


def _list_names(brain):
    names = set()
    for h in registry_rows(brain):
        for k in ("id", "name"):
            v = str(h.get(k) or "").strip()
            if v:
                names.add(v)
    labels = settings(brain).get("project_labels")
    if isinstance(labels, dict):
        names |= {str(v) for v in labels.values() if str(v).strip()}
    return sorted(names, key=len, reverse=True)


_IDS = {}
HOST_START = re.compile(r"^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/")


def known_ids(brain):
    """Every item id on this brain's registered lists (read again when a list changes)."""
    files = []
    for h in registry_rows(brain):
        if h.get("tasks"):
            p = _p(brain, _norm(h["tasks"]))
            try:
                files.append((p, os.path.getmtime(p)))
            except OSError:
                pass
    key = (os.path.abspath(brain), tuple(files))
    if key not in _IDS:
        ids = set()
        for p, _m in files:
            try:
                with open(p, "r", encoding="utf-8-sig") as f:
                    ids |= set(re.findall(r"(?m)^- \[.\] ([TQ]-\d{4}) ", f.read()))
            except OSError:
                pass
        _IDS.clear()
        _IDS[key] = ids
    return _IDS[key]


def _not_host(fn):
    """A relative-path cleaning that never touches a token beginning with a host name (example.com/...)."""
    def sub(m):
        return m.group(0) if HOST_START.match(m.group(1)) else fn(m)
    return sub


def clean_words(brain, text):
    return " ".join(clean_line(brain, text).split())


def clean_line(brain, text):
    """clean_words without folding the whitespace, so a line of a whole text keeps its indentation."""
    s = unseen_out(text)
    s = LOCAL_URL_RE.sub("[link removed]", s)
    s = OTHER_LINK_RE.sub("[link removed]", s)
    s = WIKILINK_RE.sub(lambda m: (m.group(2) or _file_name(m.group(1))).strip(), s)
    s = _strip_paths(s)
    s = BACKSLASH_REL_RE.sub(lambda m: _file_name(m.group(1)), s)
    s = REL_PATH_RE.sub(_not_host(lambda m: m.group(2)), s)
    s = FOLDER_RE.sub(lambda m: m.group(0) if HOST_START.match(m.group(0)) else m.group(1), s)
    # a relative path of two or more parts whose first part is a folder at the top of this brain reads as its last part
    s = TOP_FOLDER_PATH.sub(lambda m: m.group(3) if os.path.isdir(_p(brain, m.group(1))) and not HOST_START.match(m.group(0)) else m.group(0), s)
    ids = known_ids(brain)
    word = lambda m: ("a task" if m.group("k") == "T" else "a question") if m.group("id") in ids else m.group(0)
    names = _list_names(brain)
    if names:
        alt = "|".join(r"[-\s]+".join(re.escape(p) for p in re.split(r"[-\s]+", n)) for n in names if n.strip())
        s = re.sub(r"(?<![A-Za-z0-9-])(?:%s)[-\s]+(?P<id>(?P<k>[TQ])-\d{4})(?!\w)(?!-\d)" % alt, word, s, flags=re.I)
    s = re.sub(r"(?<![A-Za-z0-9-])(?P<id>(?P<k>[TQ])-\d{4})(?!\w)(?!-\d)", word, s)
    s = re.sub(r"\b(?:the|a|an|this|that)\s+(a (?:task|question))\b", r"\1", s, flags=re.I)
    s = re.sub(r"(^|[.!?]\s+)a (task|question)\b", lambda m: "%sA %s" % (m.group(1), m.group(2)), s)
    return s.rstrip()


# ---------------------------------------------------------------- whole texts (round three)
TEXT_EXTS = (".md", ".txt", ".json", ".csv", ".html", ".css", ".js", ".py")
TEXT_LIMIT = 400 * 1024
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
ABS_ANYWHERE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\[^\s\\]+\\|(?<![\w.~/-])~[\\/]|file://"
                          r"|(?<![\w.:/-])/(?:Users|home|mnt|var|tmp|opt|private|Volumes|etc|root|srv|c)/", re.I)


def _rel_refusal(brain, rel):
    """Why a file at `rel` never crosses whatever it holds, or ""."""
    r = _norm(rel)
    if not r or ".." in r.split("/"):
        return "it is not a file in this brain"
    if is_key_file(r):
        return "it is a key file"
    if r.lower().startswith("transcripts/"):
        return "it is a transcript"
    if r.lower().startswith("people/") and r.lower().endswith(".md"):
        return "a card goes section by section, not as a whole file"
    if "/" not in r:
        return "it sits at the top of the brain, which stays home"
    if any(r.lower().startswith(f.lower()) for f in personal_folders(brain)):
        return "it is in a personal folder"
    if _covering_says_employer(brain, r):
        return "it belongs to an employer's project"
    return ""


def _text_refusal(text):
    if text is None:
        return "only text files can be shared so far"
    if len(text.encode("utf-8", "replace")) > TEXT_LIMIT:
        return "it is over the 400 KB a shared file may be"
    if "\x00" in text:
        return "only text files can be shared so far"
    if token_in(text) or any(long_key_run(line) for line in text.split("\n")):
        return "it holds something shaped like a password or a key"
    return ""


def render_text(brain, rel, text, holds=None):
    """A whole text as it may cross: (text, "") or (None, why). Refused: a key file, a key shape anywhere, a personal
    folder or an employer's project, a transcript, a people card as a whole file, over 400 KB, not text. Cleaned line by
    line: a line marked [private] is dropped, a [private] heading drops its whole fold, a line naming a held-back person
    is dropped, and paths, other link schemes, item ids and wikilinks read as in clean_words."""
    why = _rel_refusal(brain, rel)
    if why:
        return None, why
    if not str(rel).lower().endswith(TEXT_EXTS):
        return None, "only text files can be shared so far"
    why = _text_refusal(text)
    if why:
        return None, why
    ok, named = held_back(brain)
    if not ok:
        return None, "the list of people who never cross cannot be read"
    out, drop_level = [], None
    for line in str(text).replace("\r\n", "\n").split("\n"):
        seen = unseen_out(line)
        h = HEADING_RE.match(seen)
        if h:
            level = len(h.group(1))
            if drop_level is not None and level <= drop_level:
                drop_level = None
            if drop_level is None and PRIVATE_RE.search(" ".join(seen.split())):
                drop_level = level
                continue
        if drop_level is not None:
            continue
        if PRIVATE_RE.search(" ".join(seen.split())) or _names_one(named, seen):
            continue
        out.append(clean_line(brain, line))
    return "\n".join(out), ""


def render_drawing(brain, rel, canvas, forge=None):
    """A drawing as it may cross: ({canvas, forge}, "") or (None, why). Its JSON is never rewritten: a path on this
    computer anywhere in it refuses the share and says where."""
    why = _rel_refusal(brain, rel)
    if why:
        return None, why
    for name, text in (("the drawing", canvas), ("its forge file", forge)):
        if text is None:
            continue
        why = _text_refusal(text)
        if why:
            return None, why
        for n, line in enumerate(str(text).split("\n"), 1):
            seen = unseen_out(line)
            if ABS_ANYWHERE.search(seen):
                return None, "%s holds a path on this computer, on line %d" % (name, n)
            if PRIVATE_RE.search(" ".join(seen.split())):
                return None, "%s has a part marked private, on line %d" % (name, n)
    ok, named = held_back(brain)
    if not ok:
        return None, "the list of people who never cross cannot be read"
    if _names_one(named, canvas) or _names_one(named, forge or ""):
        return None, "it names someone who never crosses"
    try:
        json.loads(canvas)
    except ValueError:
        return None, "the drawing does not read"
    return {"canvas": canvas, "forge": forge}, ""


def render_section(brain, card_rel, heading, text):
    """One ## or ### fold of a people card as it may cross: (text, "") or (None, why)."""
    if is_key_file(card_rel):
        return None, "it is a key file"
    ok, named = held_back(brain)
    if not ok:
        return None, "the list of people who never cross cannot be read"
    whole = unseen_out(str(heading or "") + "\n" + str(text or ""))
    if any(PRIVATE_RE.search(" ".join(line.split())) for line in whole.split("\n")):
        return None, "it is marked private"
    if any(_names_one(named, line) for line in whole.split("\n")):
        return None, "it names someone who never crosses"
    if token_in(whole) or any(long_key_run(line) for line in whole.split("\n")):
        return None, "it holds something shaped like a password or a key"
    return "\n".join(clean_line(brain, line) for line in str(text or "").split("\n")).strip("\n"), ""


# ---------------------------------------------------------------- the body
def _steps(item):
    st = item.get("steps")
    if isinstance(st, list):
        return [{"text": str(x.get("text") or ""), "done": bool(x.get("done"))} for x in st if isinstance(x, dict)]
    out = []
    for part in str(st or "").split(" | "):
        p = " ".join(part.split())
        if not p:
            continue
        m = re.match(r"^\[( |x|X)\]\s*(.*)$", p)
        out.append({"text": (m.group(2) if m else p).strip(), "done": bool(m and m.group(1).lower() == "x")})
    return [x for x in out if x["text"]]


def _bare(o):
    return str(o or "").strip().lstrip("@").lower()


def _who_is(holds, owner):
    """The other member an @owner names, by card slug or short name; None."""
    o = _bare(owner)
    for m in (holds or {}).get("others") or []:
        if o and o in {_bare(m.get("name")), _bare(m.get("card"))}:
            return m
    return None


def _date(v):
    s = str(v or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return ""
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        return ""


def state_of(item, today=None):
    mark = item.get("mark")
    if item.get("kind") == "question":
        return "answered" if mark == "a" else "asked"
    if mark == "x":
        return "done"
    if mark == "-":
        return "blocked"
    if _date(item.get("until")) and _date(item.get("until")) > (today or dt.date.today().isoformat()):
        return "held"
    return "open"


def render_task(brain, ledger_rel, item, raw_line, holds=None):
    """(body, "") for a task or a question that may cross, or (None, why) when it stays home. `for` and `to_you` are
    kept for display and older readers; `for_user` and `home_user` (user ids) are what decides whose it is."""
    why = refusal(brain, ledger_rel, item, raw_line)
    if why:
        return None, why
    holds = holds or {}
    me = _bare(holds.get("me"))
    is_q = item.get("kind") == "question"
    whose = item.get("to") if is_q else item.get("owner")
    target = None if (me and _bare(whose) == me) else _who_is(holds, whose)   # this brain's own person is never "them"
    text = clean_words(brain, item.get("text"))
    if not text:
        return None, "its words are empty once the private parts are taken out"
    note = clean_words(brain, item.get("note")) if item.get("note") else ""
    steps = [{"text": clean_words(brain, s["text"]), "done": s["done"]} for s in _steps(item)]
    steps = [s for s in steps if s["text"]]
    opts = []
    for o in str(item.get("options") or "").split("|"):
        name = o.strip().split("=", 1)[0].strip()
        if name:
            opts.append(clean_words(brain, name))
    label = list_label(brain, ledger_rel)
    _ok, named = held_back(brain)
    if _names_one(named, label):
        label = ""
    body = {"kind": "question" if is_q else "task", "text": text, "steps": steps, "note": note,
            "created": _date(item.get("created")), "due": _date(item.get("due")), "done": _date(item.get("done")),
            "until": _date(item.get("until")), "state": state_of(item),
            "mine": _bare(item.get("owner")) in {me, "me"} if me else _bare(item.get("owner")) == "me",
            "to_you": target is not None, "options": opts,
            "answer": clean_words(brain, item.get("answer")) if item.get("answer") else "",
            "list": label}
    if target is not None:
        body["for"] = _bare(target.get("name"))
        if target.get("user_id"):
            body["for_user"] = str(target["user_id"])
    if holds.get("me_user"):
        body["home_user"] = str(holds["me_user"])
    if token_in(json.dumps(body, ensure_ascii=False)):
        return None, "it holds something shaped like a password or a key"
    return body, ""
