"""part_circle.py -- a part of serve.py (0.73.0, the extended circle's second round; 0.74.0, the third).

What it holds: the two circle files read for the People page, the person drawer and the Reader (GET /api/circle), and
the three things a press may change in them (POST /api/circle/edit): a circle row's one-line `what`, an opportunity's
`stage` and its `next`. Nothing else in either file is written from a page.

The files are machine-written by skills/circle/build.py (its readme says how each row is made): circle.json, one row per
person or company the brain can reach through someone who has a card, with the holders in `through`; opportunities.json,
one row per thing that could be done with a named person or company, with a stage. The builder keeps a stage and a next
move found in the file across a rebuild, which is what makes an edit from here safe.

0.74.0: GET /api/circle?view=opportunities is the opportunities page's one read (and the home instrument's): every
opportunity dressed with its holder's and its people's names and cards, the days since it was named and since its stage
last moved, and the counts by stage and by kind. A row's `what` set from a page carries `edited` (the day it was set),
which tells the builder to keep that line over the source's on the next rebuild.

A brain without the folder (every fresh mentee brain) answers present false with empty lists, and every page draws
nothing for it. A team copy answers 403, as the people routes do. Loaded by serve.py with load_part(); run serve.py.
"""

CIRCLE_REL = str(SETTINGS.get("circle_dir") or "projects/pf-build/circle").replace("\\", "/").strip("/")
CIRCLE_STAGES = ("heard-of", "in-conversation", "offered", "live", "dead")
CIRCLE_WHAT_MAX = 300
CIRCLE_LINEREF_RE = re.compile(r"\bL\d{2,}\b")          # a transcript line reference never reaches a prose field
_CIRCLE_LOCK = threading.Lock()
_circle_cache = {"sig": None, "data": None}


def circle_paths():
    root = os.path.join(BRAIN, CIRCLE_REL.replace("/", os.sep))
    return os.path.join(root, "circle.json"), os.path.join(root, "opportunities.json")


def _circle_sig():
    sig = [BRAIN]
    for p in circle_paths():
        try:
            st = os.stat(p)
            sig.append((st.st_mtime_ns, st.st_size))
        except OSError:
            sig.append(None)
    return tuple(sig)


def circle_load():
    """{present, circle: {built, rows}, opportunities: {built, opportunities}} read once per change of either file."""
    sig = _circle_sig()
    if _circle_cache["sig"] == sig and _circle_cache["data"] is not None:
        return _circle_cache["data"]
    cp, op = circle_paths()
    out = {"present": False, "circle": {"built": "", "rows": []}, "opportunities": {"built": "", "opportunities": []}, "errors": []}
    for path, key, field in ((cp, "circle", "rows"), (op, "opportunities", "opportunities")):
        if not os.path.isfile(path):
            continue
        out["present"] = True
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            rows = d.get(field) if isinstance(d, dict) else None
            out[key] = {"built": (d.get("built") or "") if isinstance(d, dict) else "", field: rows if isinstance(rows, list) else []}
        except (OSError, ValueError) as e:
            out["errors"].append("%s would not read: %s" % (os.path.basename(path), e))
    _circle_cache.update(sig=sig, data=out)
    return out


def _card_exists(slug):
    try:
        rel, ap = card_path(slug)
        return bool(rel and ap)
    except Exception:
        return False


def circle_api(through=None):
    """GET /api/circle: both files as one answer. With through=<slug>: only the rows that slug holds, the opportunities
    those rows are attached to, and `cardOpps`, the opportunities the card itself is on (in `people`, or the holder)."""
    d = circle_load()
    rows = d["circle"]["rows"]
    opps = d["opportunities"]["opportunities"]
    by_id = {o.get("id"): o for o in opps if o.get("id")}
    holders = {}
    for r in rows:
        for h in r.get("through") or []:
            holders[h] = holders.get(h, 0) + 1
    base = {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "present": d["present"], "folder": CIRCLE_REL,
            "built": d["circle"]["built"] or d["opportunities"]["built"], "stages": list(CIRCLE_STAGES), "holders": holders,
            "errors": d["errors"]}
    cards = {}

    def card_of(slug):
        if slug and slug not in cards:
            cards[slug] = _card_exists(slug)
        return slug if slug and cards.get(slug) else ""

    def dressed(r):
        x = dict(r)
        x["card"] = card_of(r.get("card") or "")
        x["opps"] = [{"id": i, "title": by_id[i].get("title", ""), "stage": by_id[i].get("stage", ""), "next": by_id[i].get("next", "")}
                     for i in (r.get("opportunities") or []) if i in by_id]
        return x

    if not through:
        base.update(rows=[dressed(r) for r in rows], opportunities=opps)
        return base
    mine = [dressed(r) for r in rows if through in (r.get("through") or [])]
    ids = {o["id"] for r in mine for o in r["opps"]}
    own = {r.get("slug") for r in rows if r.get("card") == through}      # a carded person's own circle row, if any
    card_opps = [o for o in opps if through in (o.get("people") or []) or o.get("holder") == through
                 or own & set(o.get("people") or [])]
    base.update(through=through, rows=mine, opportunities=[o for o in opps if o.get("id") in ids], cardOpps=card_opps)
    return base


def _circle_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _one_line(v, limit):
    s = " ".join(str(v or "").split())
    if len(s) > limit:
        return None, "longer than %d characters" % limit
    if CIRCLE_LINEREF_RE.search(s):
        return None, "a transcript line reference does not belong in a line a person reads"
    return s, None


def circle_edit(data):
    """POST /api/circle/edit. {kind: "row", slug, what} or {kind: "opportunity", id, stage?, next?}. -> (code, body).
    One log line per write, through log.py. A stage that changes sets last_moved to today."""
    kind = (data.get("kind") or "").strip()
    cp, op = circle_paths()
    with _CIRCLE_LOCK:
        if kind == "row":
            slug = (data.get("slug") or "").strip()
            what, err = _one_line(data.get("what"), CIRCLE_WHAT_MAX)
            if err or not what:
                return 400, {"error": err or "the line is empty"}
            if not os.path.isfile(cp):
                return 404, {"error": "this brain has no circle file"}
            with open(cp, "r", encoding="utf-8-sig") as f:
                doc = json.load(f)
            row = next((r for r in doc.get("rows") or [] if r.get("slug") == slug), None)
            if not row:
                return 404, {"error": "no circle row named %s" % slug}
            if row.get("what") == what:
                return 200, {"ok": True, "unchanged": True, "row": row}
            row["what"] = what
            row["edited"] = ledger.today()      # 0.74.0: the builder keeps an edited line over its source's
            _circle_write(cp, doc)
            _circle_cache["sig"] = None
            logged = log_line("%s/circle.json -- the line for %s set from the viewer" % (CIRCLE_REL, row.get("name") or slug))
            return 200, {"ok": True, "row": row, "logged": logged}
        if kind == "opportunity":
            oid = (data.get("id") or "").strip()
            if not os.path.isfile(op):
                return 404, {"error": "this brain has no opportunities file"}
            with open(op, "r", encoding="utf-8-sig") as f:
                doc = json.load(f)
            o = next((x for x in doc.get("opportunities") or [] if x.get("id") == oid), None)
            if not o:
                return 404, {"error": "no opportunity %s" % oid}
            said = []
            if "stage" in data:
                st = (data.get("stage") or "").strip()
                if st not in CIRCLE_STAGES:
                    return 400, {"error": "the stage is one of %s" % ", ".join(CIRCLE_STAGES)}
                if st != o.get("stage"):
                    said.append("stage %s to %s" % (o.get("stage") or "none", st))
                    o["stage"] = st
                    o["last_moved"] = ledger.today()
            if "next" in data:
                nx, err = _one_line(data.get("next"), 200)
                if err:
                    return 400, {"error": err}
                if nx != (o.get("next") or ""):
                    said.append("next move set" if nx else "next move cleared")
                    o["next"] = nx
            if not said:
                return 200, {"ok": True, "unchanged": True, "opportunity": o}
            _circle_write(op, doc)
            _circle_cache["sig"] = None
            logged = log_line("%s/opportunities.json -- %s (%s): %s, from the viewer" % (CIRCLE_REL, oid, o.get("title", ""), "; ".join(said)))
            return 200, {"ok": True, "opportunity": o, "logged": logged}
    return 400, {"error": "kind is row or opportunity"}


# ---- 0.74.0: the opportunities page's read ----------------------------------------------------------------------------
CIRCLE_KINDS = ("client", "mentor", "seat", "partnership", "event")


def _card_display(slug):
    """A card's display name: its frontmatter `name:` or its first heading; "" when the slug names no card."""
    rel, ap = card_path(slug)
    if not ap:
        return ""
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            head = [next(f, "") for _ in range(30)]
    except OSError:
        return ""
    for ln in head:
        m = re.match(r"^name:\s*(.+?)\s*$", ln)
        if m:
            return m.group(1).strip().strip("\"'")
    for ln in head:
        if ln.startswith("# "):
            return re.sub(r"^#+\s*", "", ln).split("—")[0].split("--")[0].strip()
    return slug.replace("-", " ").title()


def _days_since(day, today):
    try:
        return (dt.date.fromisoformat(today) - dt.date.fromisoformat(str(day)[:10])).days
    except (TypeError, ValueError):
        return None


def circle_opps_api():
    """GET /api/circle?view=opportunities. {present, built, today, stages, kinds, counts: {stage: {..}, kind: {..}},
    opportunities: [{id, title, kind, stage, holder: {slug, name, card}, people: [{slug, name, card, via}],
    what_pf_could_do, since, last_moved, sinceDays, movedDays, next}]}. A person who is a circle row with no card
    carries `via`, the first holder whose card shows them under their circle."""
    d = circle_load()
    today = ledger.today()
    rows = {r.get("slug"): r for r in d["circle"]["rows"] if r.get("slug")}
    names = {}

    def person(slug):
        if slug not in names:
            r = rows.get(slug)
            card_slug = (r.get("card") if r else "") or slug
            nm = _card_display(card_slug)
            if nm:
                names[slug] = {"slug": slug, "name": nm, "card": card_slug, "via": ""}
            elif r:
                via = next((h for h in (r.get("through") or []) if _card_display(h)), "")
                names[slug] = {"slug": slug, "name": r.get("name") or slug, "card": "", "via": via}
            else:
                names[slug] = {"slug": slug, "name": slug.replace("-", " ").title(), "card": "", "via": ""}
        return names[slug]

    out = []
    by_stage = {s: 0 for s in CIRCLE_STAGES}
    by_kind = {}
    for o in d["opportunities"]["opportunities"]:
        st = o.get("stage") if o.get("stage") in CIRCLE_STAGES else "heard-of"
        kd = o.get("kind") or "other"
        by_stage[st] += 1
        by_kind[kd] = by_kind.get(kd, 0) + 1
        h = o.get("holder") or ""
        holder = {"slug": h, "name": "came directly", "card": ""} if h in ("", "direct") else dict(person(h))
        out.append({"id": o.get("id", ""), "title": o.get("title", ""), "kind": kd, "stage": st, "holder": holder,
                    "people": [person(p) for p in (o.get("people") or []) if p],
                    "what_pf_could_do": o.get("what_pf_could_do", ""), "since": o.get("since", ""),
                    "last_moved": o.get("last_moved", ""), "sinceDays": _days_since(o.get("since"), today),
                    "movedDays": _days_since(o.get("last_moved") or o.get("since"), today), "next": o.get("next", "")})
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "present": d["present"], "folder": CIRCLE_REL,
            "built": d["opportunities"]["built"] or d["circle"]["built"], "today": today, "stages": list(CIRCLE_STAGES),
            "kinds": list(CIRCLE_KINDS), "counts": {"stage": by_stage, "kind": by_kind, "all": len(out)},
            "opportunities": out, "errors": d["errors"]}
