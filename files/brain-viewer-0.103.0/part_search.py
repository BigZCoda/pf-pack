# ---- the search (0.100.0, 2026-10-30, brain-viewer T-0399; before it, the file search of 2026-09-17, T-0158) ----
# Run by serve.py's load_part() in serve.py's own namespace, where the file search used to sit.
#
# The owner asked on 10/30 that the search lead with what he acts on, take filter words, and be smart about it. So one
# box answers from five kinds of thing, drawn in this order: threads (the subject files), the tasks and questions on
# every registered ledger, people (the cards), the conversations of the Chat page, then files. Each kind is ranked on its
# own: the words in a name or a title over the words in a body, every word required, open over closed, the owner's own
# open items (the ones Today draws) and the newest higher. Filter words typed into the box narrow it (search_parse,
# SEARCH_KEYS); GET /api/search?hints=1 lists them with their values so the page can offer them as presses.
#
# The files are read once into memory, lowered, and re-read only when a file's time or size moves; the tree is walked at
# most every SEARCH_WALK_TTL seconds. On 10/30 the old walk-and-read took four seconds a query over 1,950 files; this
# answers in well under a second, so the box still answers as it is typed into. The semantic search (qmd) was tried for a
# second tier the same day and left out: seventeen seconds and off-target hits.
#
# Nothing here needs a skill only one brain has. The today pick is read when its file is there and adds a little weight;
# a brain with no ledgers, threads, cards or chats simply has no rows of that kind.
SEARCH_EXT = (".md", ".canvas", ".json", ".txt")
SEARCH_MAX = 50                      # the files in the answer's `items` (the Reader's own search and the board's widget read it)
SEARCH_BYTES = 2 * 1024 * 1024       # a file larger than this is found by its name only: context/log.md alone is megabytes
SEARCH_SNIPPET = 220
SEARCH_OPEN_WEIGHT = 6               # an open item over a closed one, unless the closed one matches much better by its words
SEARCH_COUNT_CAP = 16                # a word's hits in a file are counted to here (its rank stops growing at about 15)
SEARCH_WALK_TTL = 3.0                # seconds a walk of the tree is reused: the box asks again at every pause in the typing
SEARCH_ORDER = ("thread", "item", "person", "chat", "doc")
SEARCH_LABELS = {"thread": "Threads", "item": "Tasks and questions", "person": "People", "chat": "Chats", "doc": "Files"}
SEARCH_CAPS = {"thread": 4, "item": 7, "person": 3, "chat": 3, "doc": 8}   # rows per kind when the box names no kind
SEARCH_CAP_ONE = 40                  # rows when the box names one kind
SEARCH_CHATS = False                 # the Chat page's conversations as a kind: off until the owner says which chats he meant
SEARCH_MORE = {"thread": "thread:", "item": "item:", "person": "person:", "chat": "chat:", "doc": "file:"}

# (key, other spellings, the kinds it narrows to or applies to, what it does in words, an example)
# A kind key names the kinds to show. A value key keeps only the rows it can be read on, so a value key that cannot be
# read on a kind leaves that kind out (is:open has no meaning for a file, so is:open shows no files).
SEARCH_KEYS = (
    ("thread", ("threads",), ("thread",), "threads only", "thread:"),
    ("item", ("items",), ("task", "question"), "tasks and questions only", "item:"),
    ("task", ("tasks",), ("task",), "tasks only", "task:"),
    ("question", ("questions",), ("question",), "questions only", "question:"),
    ("person", ("people",), ("person",), "people only", "person:"),
    ("chat", ("chats",), ("chat",), "conversations from the Chat page only", "chat:"),
    ("file", ("files", "doc", "docs"), ("doc",), "files only", "file:"),
    ("is", (), ("thread", "item"), "open, closed, held, blocked, or mine (what Today shows you)", "is:open"),
    ("for", ("owner",), ("item",), "whose it is: me, claude, or anyone's handle", "for:me"),
    ("in", ("project",), ("thread", "item", "doc"), "a project's list, or a folder for files", "in:deliverables"),
    ("with", (), ("thread", "item", "person"), "naming a person", "with:name"),
    ("tag", (), ("item",), "a tag on a task or question", "tag:review"),
    ("due", (), ("item",), "today, overdue, week, or any", "due:today"),
    ("since", ("after",), ("thread", "item", "person", "chat", "doc"), "changed since: 7d, 2w, 3m, or a date", "since:7d"),
)
SEARCH_KEY_OF = {}
for _k in SEARCH_KEYS:
    for _name in (_k[0],) + _k[1]:
        SEARCH_KEY_OF[_name] = _k
SEARCH_KIND_KEYS = {"thread", "item", "task", "question", "person", "chat", "file"}
SEARCH_IS = ("open", "closed", "held", "blocked", "mine")
SEARCH_DUE = ("today", "overdue", "week", "any")
SEARCH_SINCE = ("today", "7d", "2w", "1m")
SEARCH_TOKEN = re.compile(r'(-?)(?:([A-Za-z]+):)?("([^"]*)"?|\S*)')
SEARCH_LINK = re.compile(r"!?\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]|!?\[([^\]]*)\]\([^)]*\)")
SEARCH_ID = re.compile(r"^[tq]-\d{4}$", re.I)

_SEARCH_IDX = {"at": 0.0, "brain": None, "files": {}}       # rel -> (mtime, size, lowered bytes or None, title)
_SEARCH_LOCK = threading.Lock()
_SEARCH_ITEMS = {"sig": None, "rows": []}
_SEARCH_SUBJ = {}                                            # subject rel -> ((mtime, size), row)


def search_parse(q):
    """The box's words as {words, phrases, minus, filters, kinds, unknown}. `key:value` is a filter when the key is one
    of SEARCH_KEYS, else the whole token is a word (a time like 10:30 stays a word); "quoted words" are one phrase; a
    leading minus leaves out what holds the word. A kind key with a value (person:sam) adds the value as a word."""
    q = str(q or "")
    out = {"words": [], "phrases": [], "minus": [], "filters": [], "kinds": set(), "unknown": []}
    pos = 0
    while pos < len(q):
        if q[pos].isspace():
            pos += 1
            continue
        m = SEARCH_TOKEN.match(q, pos)
        if not m or m.end() == pos:
            pos += 1
            continue
        pos = m.end()
        neg, key, raw, quoted = m.group(1), (m.group(2) or "").lower(), m.group(3) or "", m.group(4)
        val = (quoted if quoted is not None else raw).strip().lower()
        spec = SEARCH_KEY_OF.get(key) if key else None
        if key and not spec:
            val = (key + ":" + val).strip()
            quoted = None
        if spec:
            name = spec[0]
            if name in SEARCH_KIND_KEYS:
                out["kinds"].update(spec[2])
                out["filters"].append({"key": name, "value": "", "text": name + ":"})
                if val:
                    out["words" if quoted is None else "phrases"].append(val)
                continue
            if not val:
                out["unknown"].append(name + ":")
                continue
            out["filters"].append({"key": name, "value": val, "text": "%s:%s" % (name, val), "neg": bool(neg)})
            continue
        if not val:
            continue
        if neg:
            out["minus"].append(val)
        elif quoted is not None and " " in val:
            out["phrases"].append(val)
        else:
            out["words"].extend(w for w in val.split() if w)
    return out


def _search_since(v):
    """since:7d / 2w / 3m / today / week / month / a date -> the first day that counts, as YYYY-MM-DD, or None."""
    today = dt.date.fromisoformat(ledger.today())
    v = (v or "").strip().lower()
    m = re.fullmatch(r"(\d{1,4})\s*([dwmy]?)", v)
    days = None
    if v in ("today",):
        days = 0
    elif v in ("week",):
        days = 7
    elif v in ("month",):
        days = 30
    elif m:
        days = int(m.group(1)) * {"": 1, "d": 1, "w": 7, "m": 30, "y": 365}[m.group(2)]
    elif DATE_RE.fullmatch(v):
        return v
    return (today - dt.timedelta(days=days)).isoformat() if days is not None else None


def _search_hit(hay, w):
    """How a word sits in a lowered text: 0 not there, 1 inside a word, 2 at the start of a word, 3 the whole word."""
    best, at = 0, hay.find(w)
    while at >= 0 and best < 3:
        before = at == 0 or not hay[at - 1].isalnum()
        after = at + len(w) >= len(hay) or not hay[at + len(w)].isalnum()
        best = max(best, 3 if before and after else 2 if before else 1)
        at = hay.find(w, at + 1)
    return best


def _search_words_score(title, body, words, phrases):
    """Every word must be in the title or the body; a word in the title counts double its fit, one only in the body 1.
    None when a word is missing."""
    s = 0
    for w in words + phrases:
        t = _search_hit(title, w)
        if t:
            s += 2 * t
        elif w in body:
            s += 1
        else:
            return None
    if len(words) > 1:
        ph = " ".join(words)
        s += 4 if ph in title else 1 if ph in body else 0
    return s


def _search_recent(day, half=21.0):
    """A small weight for how new a day is: 2 for today, falling by half every `half` days."""
    try:
        age = (dt.date.fromisoformat(ledger.today()) - dt.date.fromisoformat(str(day)[:10])).days
    except Exception:                                              # noqa: BLE001
        return 0.0
    return 2.0 * (0.5 ** (max(0, age) / half))


def _search_daykey(day):
    """A sort key that puts the newer day first, an undated row last."""
    d = str(day or "")[:10]
    return -int(d.replace("-", "")) if DATE_RE.fullmatch(d) else 0


def _search_plain(t):
    """An item's words as they read: a link by its words, no markup."""
    t = SEARCH_LINK.sub(lambda m: m.group(2) or m.group(3) or os.path.basename(m.group(1) or "").rsplit(".", 1)[0], str(t or ""))
    return re.sub(r"\s+", " ", re.sub(r"[*_`]+", "", t)).strip()


# ---- the rows of each kind, cached on what they are read from ----

def search_items():
    """Every item on every registered ledger with its words lowered for the match, cached on the ledgers' times and sizes
    and the day (a hold ends by the clock)."""
    hs = [h for h in registry().get("holons", []) if h.get("tasks")]
    sig = []
    for h in hs:
        try:
            st = os.stat(os.path.join(BRAIN, h["tasks"].replace("/", os.sep)))
            sig.append((h["id"], st.st_mtime, st.st_size))
        except OSError:
            sig.append((h["id"], None, None))
    sig = (BRAIN, tuple(sig), ledger.today())
    if _SEARCH_ITEMS["sig"] == sig:
        return _SEARCH_ITEMS["rows"]
    rows = []
    for r in thread_ledgers():
        text = _search_plain(r.get("text"))
        body = " ".join(_search_plain(x) for x in [r.get("note"), r.get("answer"), " ".join(r.get("options") or [])]
                        + [s.get("text") for s in (r.get("steps") or []) if isinstance(s, dict)] if x)
        closed = r["mark"] in ("x", "a")
        rows.append({"r": r, "text": text, "title": (text + " " + r["id"]).lower(), "body": body.lower(),
                     "closed": closed, "held": (not closed) and ledger.is_held(r),
                     "mine": not closed and ((r["kind"] == "question" and r["mark"] == "?" and (not COPY or r.get("to") == OWNER))
                                             or (r["kind"] == "task" and r.get("owner") == OWNER)) and not is_try_item(r),
                     "day": max([str(d)[:10] for d in (r.get("created"), r.get("answered"), r.get("done")) if d] or [""]),
                     "links": {norm(str(l).split("#")[0]) for l in (r.get("links") or []) if l}})
    _SEARCH_ITEMS.update(sig=sig, rows=rows)
    return rows


def search_subject(rel):
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    st = os.stat(ap)
    hit = _SEARCH_SUBJ.get(rel)
    if hit and hit[0] == (st.st_mtime, st.st_size):
        return hit[1]
    s = thread_subject(rel)
    row = {"rel": rel, "name": s["name"], "slug": s["slug"], "status": s["status"] or "", "people": s["people"],
           "project": s["project"], "stands": _search_plain(first_line(s["stands"].split("\n"), 300))[:220] if s["stands"] else "",
           "last": s["timeline"][0]["date"] if s["timeline"] else (s["updatedField"] or "")[:10],
           "title": " ".join([s["name"], s["slug"].replace("-", " ")] + s["match"]).lower(),
           "body": " ".join([s["stands"]] + [t["text"] for t in s["timeline"]] + [p.replace("-", " ") for p in s["people"]]).lower()}
    _SEARCH_SUBJ[rel] = ((st.st_mtime, st.st_size), row)
    return row


def search_people():
    root = os.path.join(BRAIN, PEOPLE_REL)
    out = []
    for fn in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if not fn.endswith(".md") or fn == "readme.md":
            continue
        ap, rel = os.path.join(root, fn), "%s/%s" % (PEOPLE_REL, fn)
        try:
            st = os.stat(ap)
            hit = _people_cache.get(rel)
            if hit and hit[0] == (st.st_mtime, st.st_size):
                row = hit[1]
            else:
                row = parse_card(rel, ap)
                _people_cache[rel] = ((st.st_mtime, st.st_size), row)
        except Exception:                                          # noqa: BLE001
            continue
        out.append(row)
    return out


def _search_walk():
    """(rel, mtime, size) for every live file the search reads: the skipped folders, dot folders and key files never."""
    stack = [BRAIN]
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name not in SKIP_DIRS and not e.name.startswith("."):
                            stack.append(e.path)
                        continue
                    if not e.name.lower().endswith(SEARCH_EXT) or e.name in NEVER_READ or e.name.lower().endswith("_key.txt"):
                        continue
                    st = e.stat()
                except OSError:
                    continue
                yield os.path.relpath(e.path, BRAIN).replace(os.sep, "/"), st.st_mtime, st.st_size


def _search_title(data, rel):
    """A file's own title: frontmatter title or subject, else its first heading, else nothing (the page shows the path)."""
    if not rel.lower().endswith(".md"):
        return ""
    head = data[:4000].decode("utf-8-sig", "replace").replace("\r\n", "\n")
    m = re.search(r"^(?:title|subject):\s*[\"']?(.+?)[\"']?\s*$", head.split("\n---", 1)[0], re.M) if head.startswith("---") else None
    if m:
        return m.group(1).strip()[:160]
    m = re.search(r"^#\s+(.+)$", head, re.M)
    return _search_plain(m.group(1))[:160] if m else ""


def search_index():
    """{rel: (mtime, size, lowered bytes or None, title)} for every live file. The first call reads them all (a few
    seconds on a big brain); after that a file is read again only when its time or size moved."""
    with _SEARCH_LOCK:
        now = time.time()
        if _SEARCH_IDX["brain"] == BRAIN and now - _SEARCH_IDX["at"] < SEARCH_WALK_TTL:
            return _SEARCH_IDX["files"]
        old = _SEARCH_IDX["files"] if _SEARCH_IDX["brain"] == BRAIN else {}
        new = {}
        for rel, mtime, size in _search_walk():
            o = old.get(rel)
            if o and o[0] == mtime and o[1] == size:
                new[rel] = o
                continue
            blob, title = None, ""
            if size <= SEARCH_BYTES:
                try:
                    with open(os.path.join(BRAIN, rel.replace("/", os.sep)), "rb") as f:
                        data = f.read()
                    blob, title = data.lower(), _search_title(data, rel)
                except OSError:
                    pass
            new[rel] = (mtime, size, blob, title)
        _SEARCH_IDX.update(at=time.time(), brain=BRAIN, files=new)
        return new


def search_warm():
    """Read the files in on a thread of its own, so the first search after a start does not wait for it."""
    if _SEARCH_IDX["brain"] != BRAIN and not _SEARCH_LOCK.locked():
        threading.Thread(target=search_index, name="search-warm", daemon=True).start()


def _search_count(blob, b, cap=SEARCH_COUNT_CAP):
    """How often a word is in a file, counted to `cap`: the rank stops growing well before it, and a long transcript
    holding a name hundreds of times need not be read to its end for it."""
    n, at = 0, blob.find(b)
    while at >= 0 and n < cap:
        n += 1
        at = blob.find(b, at + len(b))
    return n


def _search_snippet(rel, blob, words, phrases):
    """The line the best word sits on, from the file as written, and its number. The lowered copy keeps every byte where
    it was (only ASCII letters change), so an offset found in it is the same offset in the file."""
    keys = [p.encode("utf-8") for p in phrases] + sorted((w.encode("utf-8") for w in words), key=lambda b: _search_count(blob, b) or 10 ** 9)
    at = next((blob.find(k) for k in keys if blob.find(k) >= 0), -1)
    if at < 0:
        return "", 1
    try:
        with open(os.path.join(BRAIN, rel.replace("/", os.sep)), "rb") as f:
            data = f.read()
    except OSError:
        return "", 1
    a = data.rfind(b"\n", 0, at) + 1
    b = data.find(b"\n", at)
    line = data[a:b if b >= 0 else len(data)].decode("utf-8-sig", "replace").strip()
    need = (phrases or sorted(words, key=len, reverse=True) or [""])[0]
    return _search_snip(line, need), data.count(b"\n", 0, at) + 1


def _search_mtime_day(mtime):
    try:
        return dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except Exception:                                              # noqa: BLE001
        return None


# ---- the answer ----

def _search_filter_val(p, key):
    return [f for f in p["filters"] if f["key"] == key]


def _search_kinds(p):
    """The kinds this box asks for: the kind keys it names, else all; less any kind a value key cannot be read on."""
    kinds = set(p["kinds"]) or {"thread", "task", "question", "person", "chat", "doc"}
    for f in p["filters"]:
        if f["key"] in SEARCH_KIND_KEYS:
            continue
        reads = set(SEARCH_KEY_OF[f["key"]][2])
        if "item" in reads:
            reads |= {"task", "question"}
        kinds &= reads
    return kinds


def _search_in(v, *names):
    v = v.strip("/").replace(" ", "-")
    return any(v and v in str(n or "").lower().replace(" ", "-") for n in names)


def _search_pick():
    """{(holon, id)} on today's pick, when this brain keeps one."""
    try:
        j = today_pick_api()
    except Exception:                                              # noqa: BLE001
        return set()
    return {(i["holon"], i["id"]) for i in j.get("items") or []} if j.get("current") else set()


def search_item_rows(p, kinds, words, phrases):
    want = {k for k in ("task", "question") if k in kinds}
    if not want:
        return []
    today = ledger.today()
    week = (dt.date.fromisoformat(today) + dt.timedelta(days=7)).isoformat()
    pick = _search_pick()
    owner = OWNER.lower()
    out = []
    for x in search_items():
        r = x["r"]
        if r["kind"] not in want:
            continue
        if any(m in x["title"] or m in x["body"] for m in p["minus"]):
            continue
        ok = True
        for f in p["filters"]:
            k, v = f["key"], f["value"]
            if k == "is":
                hit = {"open": not x["closed"], "closed": x["closed"], "done": x["closed"], "answered": r["mark"] == "a",
                       "held": x["held"], "blocked": r["mark"] == "-", "mine": x["mine"], "me": x["mine"]}.get(v)
                ok = bool(hit) if hit is not None else True
            elif k == "for":                                   # whose move it is: a task's owner, a question's answerer
                h = owner if v in ("me", "mine", "you") else "@" + v.lstrip("@")
                ok = str((r.get("to") if r["kind"] == "question" else r.get("owner")) or "").lower() == h
            elif k == "in":
                ok = _search_in(v, r["project"], r.get("label"))
            elif k == "with":
                ok = any(v in s for s in r.get("people") or []) or v in x["title"]
            elif k == "tag":
                ok = v.lstrip("#") in [str(t).lower() for t in r.get("tags") or []]
            elif k == "due":
                d = r.get("due") or ""
                ok = bool(d) and not x["closed"] and ({"today": d <= today, "overdue": d < today, "week": d <= week}.get(v, True))
            elif k == "since":
                cut = _search_since(v)
                ok = not cut or (x["day"] or "") >= cut
            if f.get("neg"):
                ok = not ok
            if not ok:
                break
        if not ok:
            continue
        ws = _search_words_score(x["title"], x["body"], words, phrases) if (words or phrases) else 0
        if ws is None:
            continue
        exact = any(SEARCH_ID.match(w) and w.upper() == r["id"] for w in words)
        score = ws + (20 if exact else 0) + (0 if x["closed"] else SEARCH_OPEN_WEIGHT) + (3 if x["mine"] and not x["held"] else 0) \
            + (4 if (r["project"], r["id"]) in pick and not x["closed"] else 0) + (2 if (r.get("due") or "9") <= today and not x["closed"] else 0) \
            + (1 if r["mark"] == "-" else 0) - (1 if x["held"] else 0) + _search_recent(x["day"])
        out.append((score, x))
    out.sort(key=lambda t: (-t[0], _search_daykey(t[1]["day"]), t[1]["r"]["id"]))
    rows = []
    for score, x in out:
        r = x["r"]
        state = ("answered" if r["mark"] == "a" else "done") if x["closed"] else "held" if x["held"] \
            else "blocked" if r["mark"] == "-" else "open"
        who = r.get("to") if r["kind"] == "question" else r.get("owner")
        rows.append({"kind": r["kind"], "title": clip(x["text"], 200), "id": r["id"], "project": r["project"],
                     "projectName": r.get("label") or r["project"], "state": state, "mine": x["mine"], "who": who or "",
                     "due": r.get("due") or "", "day": x["day"], "onPick": (r["project"], r["id"]) in pick and not x["closed"],
                     "href": "/work?item=%s/%s" % (urllib.parse.quote(r["project"]), urllib.parse.quote(r["id"])),
                     "today": ("/?item=%s/%s" % (urllib.parse.quote(r["project"]), urllib.parse.quote(r["id"]))) if x["mine"] else "",
                     "score": round(score, 2)})
    return rows


def search_thread_rows(p, kinds, words, phrases):
    if "thread" not in kinds:
        return []
    items = search_items()
    labels = {h["id"]: ledger_label(h) for h in registry().get("holons", []) if h.get("id")}   # in: names a list by its label
    out = []
    for rel in thread_files():
        try:
            s = search_subject(rel)
        except Exception:                                          # noqa: BLE001
            continue
        if any(m in s["title"] or m in s["body"] for m in p["minus"]):
            continue
        mine = sum(1 for x in items if rel in x["links"] and x["mine"] and not x["held"])
        live = s["status"] not in ("settled", "dropped", "closed", "done")
        ok = True
        for f in p["filters"]:
            k, v = f["key"], f["value"]
            if k == "is":
                ok = {"open": live, "closed": not live, "mine": mine > 0, "me": mine > 0}.get(v, False)
            elif k == "in":
                ok = _search_in(v, s["project"], labels.get(s["project"]), rel)
            elif k == "with":
                ok = any(v in x for x in s["people"])
            elif k == "since":
                cut = _search_since(v)
                ok = not cut or (s["last"] or "") >= cut
            if f.get("neg"):
                ok = not ok
            if not ok:
                break
        if not ok:
            continue
        ws = _search_words_score(s["title"], s["body"], words, phrases) if (words or phrases) else 0
        if ws is None:
            continue
        score = ws + (2 if live else -3) + min(3, mine) + _search_recent(s["last"])
        out.append((score, s, mine, live))
    out.sort(key=lambda t: (-t[0], _search_daykey(t[1]["last"]), t[1]["name"].lower()))
    return [{"kind": "thread", "title": subject_short(s["name"]), "name": s["name"], "path": s["rel"],
             "status": s["status"], "live": live, "mine": mine, "day": s["last"], "stands": s["stands"],
             "peopleSlugs": s["people"],
             "href": "/thread?subject=" + urllib.parse.quote(s["rel"]), "score": round(score, 2)}
            for score, s, mine, live in out]


def search_person_rows(p, kinds, words, phrases):
    if "person" not in kinds:
        return []
    items = search_items()
    out = []
    for c in search_people():
        st = c.get("stands")
        stands = (st.get("text") or "") if isinstance(st, dict) else str(st or "")      # the card's dated Where it stands line
        title = " ".join([c["name"], c["slug"].replace("-", " "), c.get("org") or ""]).lower()
        body = " ".join([c.get("role") or "", stands, c.get("status") or "", c.get("category") or "",
                         c.get("location") or "", c.get("placedAt") or ""]).lower()
        if any(m in title or m in body for m in p["minus"]):
            continue
        day = c.get("lastFold") or c.get("mtime") or ""
        ok = True
        for f in p["filters"]:
            k, v = f["key"], f["value"]
            if k == "with":
                ok = v in c["slug"] or v in title
            elif k == "since":
                cut = _search_since(v)
                ok = not cut or day >= cut
            if f.get("neg"):
                ok = not ok
            if not ok:
                break
        if not ok:
            continue
        ws = _search_words_score(title, body, words, phrases) if (words or phrases) else 0
        if ws is None:
            continue
        mine = sum(1 for x in items if x["mine"] and not x["held"] and c["slug"] in (x["r"].get("people") or []))
        out.append((ws + min(3, mine) + _search_recent(day, 45), c, mine, day, stands))
    out.sort(key=lambda t: (-t[0], t[1]["name"].lower()))
    return [{"kind": "person", "title": re.sub(r"\s*\([^)]*\)\s*$", "", c["name"]).strip() or c["name"], "name": c["name"],
             "slug": c["slug"], "path": c["path"], "role": clip(c.get("role") or "", 120), "org": c.get("org") or "",
             "stands": clip(stands, 200), "mine": mine, "day": day,
             "href": "/people?open=" + urllib.parse.quote(c["slug"]), "score": round(score, 2)}
            for score, c, mine, day, stands in out]


def search_chat_rows(p, kinds, words, phrases):
    """The Chat page's conversations, by their title (the first thing asked) and the project they were fixed to. None in
    a team copy: the chat is the owner's own."""
    if "chat" not in kinds or COPY or not SEARCH_CHATS or not os.path.isdir(os.path.join(BRAIN, CHATS_REL.replace("/", os.sep))):
        return []
    try:
        rows = chat_index_rows()
    except Exception:                                              # noqa: BLE001
        return []
    out = []
    for c in rows:
        title = str(c.get("title") or "").lower()
        body = str(c.get("project") or "").lower()
        if any(m in title for m in p["minus"]):
            continue
        day = str(c.get("last") or c.get("created") or "")[:10]
        ok = True
        for f in p["filters"]:
            if f["key"] == "since":
                cut = _search_since(f["value"])
                ok = not cut or day >= cut
                if f.get("neg"):
                    ok = not ok
            if not ok:
                break
        if not ok:
            continue
        ws = _search_words_score(title, body, words, phrases) if (words or phrases) else 0
        if ws is None:
            continue
        out.append((ws + _search_recent(day), c, day))
    out.sort(key=lambda t: -t[0])
    return [{"kind": "chat", "title": clip(str(c.get("title") or "a conversation"), 160), "id": c.get("id"),
             "project": c.get("project") or "main", "day": day, "turns": c.get("turns") or 0,
             "href": "/chat?id=" + urllib.parse.quote(str(c.get("id") or "")), "score": round(score, 2)}
            for score, c, day in out]


def search_doc_rows(p, kinds, words, phrases, skip=()):
    """Files: every word in the file's name, its title or its text. A name or a title that holds the words over a text
    that holds them; the more often, the newer, the higher. With no words, a folder or a day lists what changed newest."""
    if "doc" not in kinds:
        return [], 0
    ins = [f["value"].strip("/") for f in p["filters"] if f["key"] == "in" and not f.get("neg")]
    outs = [f["value"].strip("/") for f in p["filters"] if f["key"] == "in" and f.get("neg")]
    cut = max([_search_since(f["value"]) or "" for f in p["filters"] if f["key"] == "since"] or [""])
    if not (words or phrases) and not (ins or cut):
        return [], 0
    ledgers = {norm(h["tasks"]) for h in registry().get("holons", []) if h.get("tasks")}
    only_docs = p["kinds"] == {"doc"}
    wb = [w.encode("utf-8") for w in words]
    pb = [x.encode("utf-8") for x in phrases]
    mb = [m.encode("utf-8") for m in p["minus"]]
    idx = search_index()
    out, read = [], 0
    for rel, (mtime, size, blob, title) in idx.items():
        if not only_docs and (rel in skip or rel in ledgers):
            continue                                           # its rows are drawn above, as an item, a thread or a person
        lrel = rel.lower()
        if ins and not any(lrel.startswith(v + "/") or ("/" + v + "/") in ("/" + lrel) or v in lrel.split("/")[0] for v in ins):
            continue
        if outs and any(lrel.startswith(v + "/") or ("/" + v + "/") in ("/" + lrel) for v in outs):
            continue
        day = _search_mtime_day(mtime) or "" if cut else None
        if cut and day < cut:
            continue
        read += 1 if blob is not None else 0
        if mb and any(m in (blob or b"") or m.decode() in lrel for m in mb):
            continue
        leaf, ltitle = lrel.rsplit("/", 1)[-1], title.lower()
        score, count, why_name, why_text = 0.0, None, False, False
        ok = True
        for w, b in zip(words + phrases, wb + pb):
            n = _search_hit(leaf, w) or _search_hit(ltitle, w)
            c = _search_count(blob, b) if blob is not None else 0
            if n:
                score += 2 * n
                why_name = True
            elif w in lrel:
                score += 1.5
                why_name = True
            elif c:
                why_text = True
            else:
                ok = False
                break
            if c:
                score += min(3.0, (c + 1) ** 0.5 - 1)
                count = c if count is None else min(count, c)
        if not ok:
            continue
        if len(words) > 1:
            ph = " ".join(words)
            score += 4 if (ph in ltitle or ph in leaf) else 2 if blob is not None and ph.encode("utf-8") in blob else 0
        day = day if day is not None else (_search_mtime_day(mtime) or "")
        score += _search_recent(day, 30) - (1.5 if lrel.endswith(".json") else 0)
        out.append((score, rel, blob, title, day, count or 0, why_name, why_text))
    out.sort(key=lambda t: (-t[0], t[1]))
    return out, read


def search_api(q, limit=SEARCH_MAX, caps=None):
    """GET /api/search?q=: {q, filters, unknown, groups:[{kind, label, total, rows, more}], counts, items, count, capped, ms}.
    `items` keeps the 9/17 answer's shape (the files, path line snippet why mtime matches) for the Reader's own search and
    the board's widget."""
    t0 = time.time()
    raw = (q or "").strip()
    p = search_parse(raw)
    words = [w for w in p["words"] if w]
    phrases = [x for x in p["phrases"] if x]
    named = [f for f in p["filters"] if f["key"] not in SEARCH_KIND_KEYS]
    if sum(len(w) for w in words + phrases) < 2 and not named and not p["kinds"]:
        return {"q": raw, "count": 0, "items": [], "groups": [], "capped": False, "filters": p["filters"],
                "unknown": p["unknown"], "error": "type at least two characters"}
    if not (words or phrases or named) and p["kinds"] and p["kinds"] <= {"thread", "task", "question"}:
        # a kind word alone lists the open ones of that kind (person: or chat: alone lists them newest first)
        p["filters"] = p["filters"] + [{"key": "is", "value": "open", "text": "is:open", "implied": True}]
    kinds = _search_kinds(p)
    one = len({("item" if k in ("task", "question") else k) for k in kinds}) == 1
    caps = dict(SEARCH_CAPS, **(caps or {}))
    groups, counts, shown = [], {}, set()
    for kind in SEARCH_ORDER:
        if kind == "doc":
            continue
        rows = {"thread": search_thread_rows, "item": search_item_rows, "person": search_person_rows,
                "chat": search_chat_rows}[kind](p, kinds, words, phrases)
        counts[kind] = len(rows)
        cap = SEARCH_CAP_ONE if one else caps[kind]
        for r in rows[:cap]:
            if r.get("path"):
                shown.add(r["path"])
            if "peopleSlugs" in r:                             # a thread's people by name, read for the rows shown only
                sl = r.pop("peopleSlugs")
                r["people"] = [card_display_name(x) for x in sl[:3]] + (["+%d" % (len(sl) - 3)] if len(sl) > 3 else [])
        if rows:
            groups.append({"kind": kind, "label": SEARCH_LABELS[kind], "total": len(rows), "rows": rows[:cap],
                           "more": SEARCH_MORE[kind] if len(rows) > cap and not one else ""})
    docs, read = search_doc_rows(p, kinds, words, phrases, skip=shown)
    counts["doc"] = len(docs)
    cap = SEARCH_CAP_ONE if one else caps["doc"]
    items = []
    for score, rel, blob, title, day, count, why_name, why_text in docs[:max(cap, limit)]:
        snip, line = _search_snippet(rel, blob, words, phrases) if blob is not None and (words or phrases) else ("", 1)
        items.append({"path": rel, "line": line, "snippet": snip or rel, "title": title,
                      "why": "name+text" if why_name and why_text else "name" if why_name else "text",
                      "mtime": day, "matches": count, "score": round(score, 2)})
    if docs:
        groups.append({"kind": "doc", "label": SEARCH_LABELS["doc"], "total": len(docs),
                       "rows": [dict(r, kind="doc") for r in items[:cap]],
                       "more": SEARCH_MORE["doc"] if len(docs) > cap and not one else ""})
    return {"q": raw, "filters": p["filters"], "unknown": p["unknown"], "words": words + phrases, "minus": p["minus"],
            "kinds": sorted(kinds), "groups": groups, "counts": counts, "total": sum(counts.values()),
            "count": len(docs), "items": items[:limit], "capped": len(docs) > limit, "limit": limit,
            "files": read, "ms": int((time.time() - t0) * 1000),
            "note": "threads, tasks and questions, people and chats first, then files; live files only (archive/ and the token files are never read)"}


def search_hints():
    """GET /api/search?hints=1: the filter words with what each does and the values worth offering, plus the threads
    worked on most lately for an empty box. Also starts reading the files in, so the first search does not wait."""
    search_warm()
    items = search_items()
    ledgers, seen = [], set()
    for h in registry().get("holons", []):
        if h.get("tasks") and h["id"] not in seen:
            seen.add(h["id"])
            lab = ledger_label(h)
            ledgers.append({"value": re.sub(r"[^a-z0-9]+", "-", lab.lower()).strip("-") or h["id"], "says": lab})
    folders = sorted({rel.split("/", 1)[0] for rel in (_SEARCH_IDX["files"] or {}) if "/" in rel})
    if not folders:
        try:
            folders = sorted(d for d in os.listdir(BRAIN) if os.path.isdir(os.path.join(BRAIN, d))
                             and d not in SKIP_DIRS and not d.startswith("."))
        except OSError:
            folders = []
    who = collections.Counter()
    tags = collections.Counter()
    for x in items:
        if x["closed"]:
            continue
        r = x["r"]
        for h in (r.get("owner"), r.get("to")):
            if h and h != OWNER:
                who[h] += 1
        for t in r.get("tags") or []:
            if not str(t).startswith(("source:", "key:")):
                tags[str(t)] += 1
    people = []
    try:
        people = sorted(c["slug"] for c in search_people())
    except Exception:                                              # noqa: BLE001
        pass
    recent = []
    try:
        threads = search_thread_rows(search_parse("is:open"), {"thread"}, [], [])
        threads.sort(key=lambda r: (r["day"] or "", r["title"]), reverse=True)
        recent = [{"title": r["title"], "href": r["href"], "day": r["day"], "mine": r["mine"]} for r in threads[:4]]
    except Exception:                                              # noqa: BLE001
        pass
    return {"keys": [{"key": k[0] + ":", "also": [a + ":" for a in k[1]], "says": k[3], "example": k[4],
                      "kind": k[0] in SEARCH_KIND_KEYS} for k in SEARCH_KEYS
                     if k[0] != "chat" or (SEARCH_CHATS and not COPY)],
            "values": {"is": list(SEARCH_IS), "for": ["me"] + [h.lstrip("@") for h, _ in who.most_common(8)],
                       "in": ledgers + [{"value": f, "says": "the %s folder" % f} for f in folders],
                       "with": people, "tag": [t for t, _ in tags.most_common(12)],
                       "due": list(SEARCH_DUE), "since": list(SEARCH_SINCE)},
            "recent": recent, "owner": OWNER, "chats": SEARCH_CHATS and not COPY, "warm": _SEARCH_IDX["brain"] == BRAIN}
