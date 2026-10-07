"""part_live.py -- a part of serve.py (0.68.0, the review's finding 8: the three biggest sections of the server in files of their own).

What it holds: the Forge's files and fields, the canvases, the live maps and part state (/api/forge*, /api/canvas*, /api/live*, /api/maps).

It is not imported as a module of its own. serve.py loads it with load_part() at the point where this code used to sit,
into serve.py's own namespace, so every name here is still serve.<name>: the tests that point serve.BRAIN at a scratch
folder reach it, derive_day.py's serve.live_binding() still answers, and nothing here imports anything serve.py has not.
Run serve.py, never this file.
"""

def forge_path(rel):
    """True when rel is a file the Forge may write: <FORGE_ROOT>/<family>[/...]/<name>.canvas or .forge.json."""
    rel = norm(rel)
    if rel and rel.startswith(SCRATCH_REL + "/") and rel.lower().endswith(FORGE_EXT):
        leaf = rel[len(SCRATCH_REL) + 1:]
        return "/" not in leaf and leaf not in (".canvas", ".forge.json")          # the scratch family: one level, no subfolders
    if not rel or not rel.startswith(FORGE_ROOT + "/") or not rel.lower().endswith(FORGE_EXT):
        return False
    inner = rel[len(FORGE_ROOT) + 1:]
    return "/" in inner and os.path.basename(inner) not in ("", ".canvas", ".forge.json")


def forge_sibling(canvas_rel):
    return canvas_rel[:-len(".canvas")] + ".forge.json"


def is_cell(n):
    """A cell is a group that is not one of the two nested layers a cell draws inside itself."""
    return n.get("type") == "group" and not str(n.get("label") or "").strip().lower().startswith(FORGE_INNER)


def forge_stages(nodes, meta):
    """Stage counts for a canvas: every cell, at the stage its .forge.json row names, else concept."""
    rows = (meta or {}).get("nodes") or {}
    out = {k: 0 for k in FORGE_STAGES}
    for n in nodes:
        if is_cell(n):
            st = str((rows.get(n.get("id")) or {}).get("stage") or "concept").lower()
            out[st if st in out else "concept"] += 1
    return out


def read_forge_meta(canvas_rel):
    """The sibling .forge.json as a dict, or None when there is none (every cell at concept)."""
    ap = os.path.join(BRAIN, forge_sibling(canvas_rel).replace("/", os.sep))
    if not os.path.isfile(ap):
        return None
    with open(ap, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def forge_api(rel):
    """GET /api/forge?path=: the drawing, its sibling, whether it may be written here, and the facts the client needs
    to write the file back the way it found it (a trailing newline or not; CRLF is handled by PUT /api/file itself)."""
    rel = norm(rel)
    ap = read_abs(rel) if rel else None
    if not ap or not rel.lower().endswith(".canvas") or not os.path.isfile(ap):
        return None, "canvas not found"
    with open(ap, "rb") as f:
        raw = f.read()
    d = json.loads(raw.decode("utf-8-sig"))
    meta = read_forge_meta(rel)
    return {"path": rel, "canvas": d, "forge": meta, "forgePath": forge_sibling(rel), "forgeExists": meta is not None,
            "editable": writable(rel), "propose": PROPOSE,
            "family": rel[len(FORGE_ROOT) + 1:].split("/")[0] if rel.startswith(FORGE_ROOT + "/") else "",
            "trailingNewline": raw.endswith(b"\n"), "crlf": b"\r\n" in raw[:4096],
            "stages": forge_stages(d.get("nodes", []), meta), "inForge": forge_path(rel),
            "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")}, None


def forge_new(family, name):
    """POST /api/forge/new: a fresh canvas with one empty cell under <FORGE_ROOT>/<family>/<name>.canvas (exclusive create).
    The family folder is made when it does not exist yet. Returns (rel, error).
    0.67.0: no family, or the family "scratch", puts it in the scratch family (SCRATCH_REL/<name>.canvas), the default."""
    fam = re.sub(r"[^a-z0-9-]+", "-", str(family or "").strip().lower()).strip("-")
    slug = re.sub(r"[^a-z0-9-]+", "-", str(name or "").strip().lower()).strip("-")
    if not slug:
        return None, "a name is required (letters, digits, dashes)"
    if not fam or fam == "scratch":
        rel = "%s/%s.canvas" % (SCRATCH_REL, slug)
    else:
        rel = "%s/%s/%s.canvas" % (FORGE_ROOT, fam, slug)
    label = re.sub(r"\s+", " ", str(name or "").strip()) or slug
    doc = {"nodes": [{"id": "cell_1", "type": "group", "x": 0, "y": 0, "width": 900, "height": 560, "color": "6", "label": "CELL 1 · " + label.upper()}],
           "edges": []}
    body = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if PROPOSE:
        return propose("file", rel, {"content": body}, note="Forge: new machine %s (1 cell)" % rel), None
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    try:
        with open(ap, "x", encoding="utf-8", newline="\n") as f:
            f.write(body)
    except FileExistsError:
        return None, "a canvas named %s already exists in %s" % (slug, fam)
    log_line("%s -- Forge: new machine, 1 cell, 0 edges; created from the picker" % rel, action="CREATED")
    return rel, None


def forge_untouched(rel):
    """True when a drawing is exactly what forge_new made and nothing since: one group cell (cell_1 at 0,0, 900 by 560),
    no lines, no sibling .forge.json. Only such a drawing may be deleted from the Forge (0.67.0)."""
    rel = norm(rel)
    if not rel or not rel.lower().endswith(".canvas") or not forge_path(rel):
        return False
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    if not os.path.isfile(ap) or os.path.isfile(os.path.join(BRAIN, forge_sibling(rel).replace("/", os.sep))):
        return False
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:                                             # noqa: BLE001
        return False
    nodes, edges = d.get("nodes") or [], d.get("edges") or []
    if edges or len(nodes) != 1:
        return False
    n = nodes[0]
    return (n.get("id") == "cell_1" and n.get("type") == "group"
            and (n.get("x"), n.get("y"), n.get("width"), n.get("height")) == (0, 0, 900, 560)
            and str(n.get("label") or "").startswith("CELL 1 ")
            and set(n) <= {"id", "type", "x", "y", "width", "height", "color", "label"})


def forge_delete(rel):
    """POST /api/forge/delete {path}: remove a one-cell drawing that was never edited (forge_untouched), and nothing else.
    A family folder under the forge root left empty by it goes with it; the scratch folder stays."""
    rel = norm(rel)
    if PROPOSE:
        return None, "a team copy does not delete drawings"
    if not forge_untouched(rel):
        return None, "only a one-cell drawing that was never edited can be deleted here"
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    os.remove(ap)
    fam = os.path.dirname(ap)
    if rel.startswith(FORGE_ROOT + "/") and os.path.isdir(fam) and not os.listdir(fam):
        try:
            os.rmdir(fam)
        except OSError:
            pass
    log_line("%s -- Forge: deleted a one-cell drawing that was never edited" % rel, action="DELETED")
    return rel, None


def scratch_canvases():
    """GET /api/forge/scratch: the drawings in the scratch family, newest first, each marked whether it may be deleted."""
    d = os.path.join(BRAIN, SCRATCH_REL.replace("/", os.sep))
    out = []
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not fn.endswith(".canvas"):
            continue
        rel = "%s/%s" % (SCRATCH_REL, fn)
        ap = os.path.join(d, fn)
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                c = json.load(f)
            nodes = c.get("nodes", [])
            cells, nn, ne = sum(1 for n in nodes if is_cell(n)), len(nodes), len(c.get("edges", []))
        except Exception:                                         # noqa: BLE001
            cells = nn = ne = 0
        out.append({"path": rel, "name": fn[:-len(".canvas")], "cells": cells, "nodes": nn, "edges": ne,
                    "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="minutes"),
                    "deletable": forge_untouched(rel)})
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return {"root": SCRATCH_REL, "canvases": out}


# ---- the output shelf's loose fields (2026-09-10, the mouth, T-0091). "Derived, never drawn" applies to the OUTPUT of a
# cell as much as to a panel: where a cell is bound to something real, the fields it can ship are READ from that thing's
# own records at request time and never typed into the drawing. What the drawing carries is a pointer (the sibling's
# output.source, or the node's saved binding), so a schema that gains a key gains it here on the next reload.
_fields_cache = {}                # abs path -> (mtime, size, [rows])


def forge_field_rows(rel):
    """The record keys of a .json full of records, as field rows. A file shaped {"<plural>": [ {...}, ... ]} is read as
    that list; a bare list is read as itself; a dict of dicts as its values. Sub-keys are one level deep, which is where
    the onboarding profile keeps profile / assessment / extendedQuestions."""
    ap = read_abs(rel)
    if not ap or not os.path.isfile(ap) or not rel.lower().endswith(".json"):
        return None, "not a readable .json under the brain: %s" % rel
    st = os.stat(ap)
    hit = _fields_cache.get(ap)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2], None
    with open(ap, "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    recs = None
    if isinstance(d, list):
        recs = [x for x in d if isinstance(x, dict)]
    elif isinstance(d, dict):
        best = None
        for k, v in d.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and (best is None or len(v) > len(best[1])):
                best = (k, v)
        if best:
            recs = best[1]
        elif d and all(isinstance(v, dict) for v in d.values()):
            recs = list(d.values())
        else:
            recs = [d]
    if not recs:
        return None, "no records in %s" % rel
    r0 = recs[0]

    def kind_of(v):
        if isinstance(v, bool):
            return "yes/no"
        if isinstance(v, (int, float)):
            return "number"
        if isinstance(v, list):
            return "list"
        if isinstance(v, dict):
            return "record"
        if v is None:
            return "empty"
        return "text"

    def sample_of(v):
        if isinstance(v, (dict, list)):
            return "%d %s" % (len(v), "keys" if isinstance(v, dict) else "items")
        t = str(v if v is not None else "")
        return (t[:70] + "…") if len(t) > 70 else t

    rows, seen = [], set()
    for k, v in r0.items():
        if k in seen:
            continue
        seen.add(k)
        rows.append({"key": k, "type": kind_of(v), "sample": sample_of(v), "group": "record"})
        if isinstance(v, dict):
            for k2, v2 in v.items():
                rows.append({"key": "%s.%s" % (k, k2), "type": kind_of(v2), "sample": sample_of(v2), "group": k})
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            for k2, v2 in v[0].items():
                rows.append({"key": "%s[].%s" % (k, k2), "type": kind_of(v2), "sample": sample_of(v2), "group": k})
    _fields_cache[ap] = (st.st_mtime, st.st_size, rows)
    if len(_fields_cache) > 24:
        _fields_cache.clear()
    return rows, None


def forge_fields_api(rel, node_id):
    """GET /api/forge/fields?path=&node=: what one cell's mouth can ship, read from the real thing behind the cell.
    The pointer comes from the drawing, never the field list: the sibling's `output.source` for that node first, then a
    binding saved on it, then the binding the live ladder resolves for it. Nothing is written."""
    rel = norm(rel)
    ap = read_abs(rel) if rel else None
    if not ap or not rel.lower().endswith(".canvas") or not os.path.isfile(ap):
        return None, "canvas not found"
    with open(ap, "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    n = next((x for x in d.get("nodes", []) if x.get("id") == node_id), None)
    if not n:
        return None, "no node %s in this drawing" % node_id
    meta = read_forge_meta(rel) or {}
    row = ((meta.get("nodes") or {}).get(node_id) or {})
    src, via = None, None
    out = row.get("output") if isinstance(row.get("output"), dict) else {}
    if out.get("source"):
        src, via = norm(out["source"]), "the source named beside the drawing"
    if not src:
        b = row.get("binding") if isinstance(row.get("binding"), dict) else None
        if b and str(b.get("target") or "").lower().endswith(".json"):
            src, via = norm(b["target"]), "the binding saved on this cell"
    if not src:
        try:
            b = live_bind(n, live_names(), (meta.get("nodes") or {}))
        except Exception:
            b = None
        if b and b.get("kind") in ("file", "canvas") and str(b.get("target") or "").lower().endswith(".json"):
            src, via = norm(b["target"]), "what this cell is bound to (%s)" % b.get("via")
    if not src:
        return None, ("nothing real is behind this cell yet, so there is no schema to read. Name the file its records "
                      "live in as `output.source` beside the drawing, or type the fields by hand in the shelf.")
    rows, err = forge_field_rows(src)
    if err:
        return None, err
    return {"path": rel, "node": node_id, "source": src, "via": via, "count": len(rows), "fields": rows,
            "readAt": dt.datetime.now().astimezone().isoformat(timespec="seconds")}, None


def resolve_map():
    if time.time() - _resolve_cache["t"] > 60:
        m = {}
        for root, dirs, files in os.walk(BRAIN):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in files:
                if (os.path.splitext(fn)[1].lower() in READ_EXT or os.path.splitext(fn)[1].lower() in IMAGE_EXT) and fn not in NEVER_READ:
                    rel = os.path.relpath(os.path.join(root, fn), BRAIN).replace(os.sep, "/")
                    m.setdefault(fn, []).append(rel)
        _resolve_cache.update(t=time.time(), map=m)
    return _resolve_cache["map"]


def canvases():
    out = []
    arch = os.path.join(BRAIN, ARCH_REL.replace("/", os.sep))
    scratch = os.path.normcase(os.path.join(BRAIN, SCRATCH_REL.replace("/", os.sep)))
    for root, dirs, files in os.walk(arch):
        if os.path.normcase(root).startswith(scratch):            # 0.67.0: the scratch family is never listed as a drawing
            dirs[:] = []
            continue
        for fn in sorted(files):
            if not fn.endswith(".canvas"):
                continue
            ap = os.path.join(root, fn)
            rel = os.path.relpath(ap, BRAIN).replace(os.sep, "/")
            family = os.path.relpath(root, arch).replace(os.sep, "/")
            try:
                with open(ap, "r", encoding="utf-8-sig") as f:
                    d = json.load(f)
                nodes = d.get("nodes", []); edges = d.get("edges", [])
                header = next((n.get("text", "") for n in nodes if (n.get("text") or "").lstrip().startswith("🧭")), "")
                header = header.replace("\n", " ").replace("**", "").strip()
                try:
                    meta = read_forge_meta(rel)
                except Exception:
                    meta = None
                out.append({"path": rel, "name": fn[:-len(".canvas")], "family": family if family != "." else "(root)",
                            "nodes": len(nodes), "edges": len(edges),
                            "stages": forge_stages(nodes, meta), "cells": sum(1 for n in nodes if is_cell(n)), "forge": meta is not None,
                            "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).strftime("%Y-%m-%d"),
                            "header": header[:200], "home": fn == "zak-brain-map-radial.canvas",
                            "deletable": len(nodes) == 1 and not edges and forge_untouched(rel)})
            except Exception as e:
                out.append({"path": rel, "name": fn, "family": family, "nodes": 0, "edges": 0, "mtime": None, "header": "unreadable: %s" % e, "home": False})
    return out


# ---- the live maps (2026-09-09, the straight line step 4, ledger T-0042) ----
# The owner's ask, on the 9/09 moving graph: not one map, several, each an existing canvas read against real state, with the gold
# bubbles along the lines kept for what is in flight. Two layers computed over a drawing nobody edits for it (build doc
# section 12):
#   BUILD    every node bound to the real thing it stands for -- a file (or a canvas, or a folder), a registry holon, a
#            skill folder under skills/, an agent id the log has seen, a route of this app, an outside service -- or marked
#            concept. The ladder, in order: the title line's own pointer ([[wikilink]], `backticked path`, a bare filename
#            unique in the brain), a holon id or name on the title line, a skill folder name there, an agent id there;
#            then the whole text: a pointer (a wikilink that only says "open →" or "⬆ Up" is navigation, not identity, and
#            is skipped), a route, a service name, a holon id or a skill name. A binding already SAVED in the sibling
#            .forge.json wins over all of it, so a drawing carries its bindings forward.
#   RUNTIME  each bound thing lit by evidence the brain already writes: the context/log.md lines of the last LIVE_DAYS that
#            name it (count, last time, last verb, the agent, the last three lines), a file's mtime, a holon's status-file
#            _generatedAt, whether a Claude Code session ran today (for agents), the team copy's status file, the last
#            Ferryman line (for the PF App and the onboarding app). An edge is active today when both its ends were.
# Nothing here is stored (rules 1 and 2): bindings are cached in memory per canvas mtime and the activity is re-read on
# every call. The ONE write is "save bindings" on the page, which copies the resolved bindings into the canvas's sibling
# .forge.json under each node id as binding: {kind, target} -- the Forge's file, the Forge's write scope, one log line --
# and only when that button is pressed. In a team copy that write is a request like every other.
LIVE_DAYS = 14
LIVE_LINES = 3                    # log lines carried per node, for the hover card
MAPS_REL = _declared("maps_manifest", "maps-manifest.json", "skills/brain-viewer/maps-manifest.json")   # which canvases are maps and by what purpose: a declaration, like the mentee manifest
LIVE_ROUTES = ("/projects", "/people", "/mentee", "/canvases", "/forge", "/live", "/maps", "/requests", "/map", "/status",
               "/holons", "/agents", "/chat", "/reader", "/glossary", "/from-claude", "/threads", "/thread", "/today", "/files",
               "/review", "/findings", "/work")   # the folded routes stay: a drawing that names one still binds, and it redirects
LIVE_EXT = (".md", ".py", ".json", ".canvas", ".txt", ".bat", ".js", ".css", ".html", ".csv", ".yaml", ".yml", ".ps1", ".sh")
# outside services: (name, what names it in a node's text, what names it in a log line, where a click goes)
LIVE_SERVICES = (
    ("team copy", r"team copy|zebrain-team|\bthe clone\b|team brain|team-brain", r"team-brain|team copy|zebrain-team|export\.py", None),
    ("GitHub", r"\bgithub\b|bigzcoda/|\bgit push\b|\bgit/", r"\bgithub\b|\bgit push\b|\bpushed to\b|bigzcoda|\bcommit(?:ted)?\b", "https://github.com/BigZCoda"),
    ("PF App", r"\bpf app\b|app\.prospectforge\.us", r"\bpf app\b|app\.prospectforge|push\.py|pull\.py|\bferryman\b", "https://app.prospectforge.us"),
    ("onboarding app", r"onboarding app|onboarding\.prospectforge\.us|onboarding api", r"onboarding-api-pull|onboarding app|onboarding-app-holon", "https://onboarding.prospectforge.us"),
    ("Google Calendar", r"google calendar|calendar mcp|\bcalendar\b", r"\bcalendar\b", None),
    ("Gmail", r"\bgmail\b", r"\bgmail\b", None),
    ("Notion", r"\bnotion\b", r"\bnotion\b", None),
    ("Replit", r"\breplit\b", r"\breplit\b", None),
    ("Obsidian Sync", r"obsidian sync|\bobsidian\b", r"\bobsidian\b", None),
    ("Google Drive", r"google doc|google drive|drive mcp", r"google doc|google drive", None),
    ("transcription", r"\botter\b|\bgranola\b|\bgemini\b", r"\bgemini\b|\botter\b|\bgranola\b", None),
)
LIVE_HOSTS = (("github.com", "GitHub"), ("app.prospectforge.us", "PF App"), ("onboarding.prospectforge.us", "onboarding app"),
              ("replit", "Replit"), ("notion.so", "Notion"), ("calendar.google", "Google Calendar"), ("docs.google", "Google Drive"))
WIKI_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
TICK_RE = re.compile(r"`([^`\n]+)`")
BARE_RE = re.compile(r"(?<![\w/.\-])([A-Za-z][\w.\-]*\.(?:md|py|json|canvas|txt|bat|js|css|html))(?![\w/])")
NAV_BEFORE_RE = re.compile(r"(?:open|up|twin|see also|drill[- ]?down|also|here)\s*[:→]?\s*$", re.I)
_live_cache = {}                  # canvas rel -> (key, bindings by node id)
_log_cache = {"key": None, "rows": [], "agents": set()}
_leaf_cache = {"t": 0, "map": {}}


def ledger_months():
    """[(month, path)] for every rotated log month on disk, oldest first."""
    base = os.path.join(BRAIN, LEDGERS_REL.replace("/", os.sep))
    if not os.path.isdir(base):
        return []
    out = []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    for name in names:
        if not re.fullmatch(r"\d{4}-\d{2}", name):
            continue
        path = os.path.join(base, name, "log-%s.md" % name)
        if os.path.isfile(path):
            out.append((name, path))
    return out


def log_lines(since=None):
    """THE reader of the operations log, for every caller in this file.

    Yields raw lines oldest-first: the rotated months `archive/ledgers/YYYY-MM/log-YYYY-MM.md` the
    window reaches into, then the live `context/log.md`. `since` is the oldest DAY the caller needs
    ('YYYY-MM-DD'); None means the whole rotation, which is what a "what has this brain ever done"
    reader (the agents page) wants. A 14-day window crossing a month boundary therefore reads the
    same lines it read when the live file still held every month (2026-09-18, Batch 2)."""
    for month, path in ledger_months():
        if since and month < since[:7]:
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    yield line.rstrip("\n")
        except OSError:
            continue
    ap = os.path.join(BRAIN, LOG_REL.replace("/", os.sep))
    if os.path.isfile(ap):
        with open(ap, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line.rstrip("\n")


def log_key():
    """The cache key for the log: the live file plus every rotated month, so a rotation invalidates."""
    parts = []
    for path in [os.path.join(BRAIN, LOG_REL.replace("/", os.sep))] + [pa for _m, pa in ledger_months()]:
        try:
            st = os.stat(path)
            parts.append((path, st.st_mtime, st.st_size))
        except OSError:
            continue
    return (tuple(parts), dt.date.today().isoformat())


def log_rows():
    """The log read once per change: the rows of the last LIVE_DAYS (append-only, so newest last) and
    every agent id the log has ever seen. One pass over log_lines(), live file and rotated months."""
    if not os.path.isfile(os.path.join(BRAIN, LOG_REL.replace("/", os.sep))):
        return [], set()
    key = log_key()
    if _log_cache["key"] == key:
        return _log_cache["rows"], _log_cache["agents"]
    since = (dt.date.today() - dt.timedelta(days=LIVE_DAYS)).isoformat()
    rows, agents = [], set()
    for line in log_lines():
        m = LOG_LINE_RE.match(line)
        if not m:
            continue
        agents.add(m.group(3))
        if m.group(1) < since:
            continue
        rows.append({"date": m.group(1), "at": m.group(1) + " " + m.group(2), "agent": m.group(3), "action": m.group(4),
                     "text": m.group(5), "low": (m.group(3) + " " + m.group(5)).lower()})
    _log_cache.update(key=key, rows=rows, agents=agents)
    return _log_cache["rows"], _log_cache["agents"]


def live_leaves():
    """Every file under the brain by leaf name (all extensions the ladder accepts, not only the readable ones), refreshed each minute."""
    if time.time() - _leaf_cache["t"] > 60:
        m = {}
        for root, dirs, files in os.walk(BRAIN):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in files:
                if fn.lower().endswith(LIVE_EXT) and fn not in NEVER_READ:
                    m.setdefault(fn, []).append(os.path.relpath(os.path.join(root, fn), BRAIN).replace(os.sep, "/"))
        _leaf_cache.update(t=time.time(), map=m)
    return _leaf_cache["map"]


def live_plain(s):
    """A node's text with the markdown, the wikilink brackets, the emoji and the symbols taken out; one space between words."""
    s = WIKI_RE.sub(lambda m: m.group(2) or m.group(1), str(s or ""))
    s = re.sub(r"[*`_#>|]+", " ", s)
    s = re.sub(r"[^\w\s/.:@+()'\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def live_resolve_path(tok):
    """A pointer's text -> (brain-relative path, is_dir) when it names something that exists under the brain, else None."""
    tok = str(tok or "").strip().strip("'\"").split(" ")[0].strip(",.;:)(")
    tok = re.sub(r"^\./", "", tok.replace("\\", "/"))
    if not tok or tok.lower().startswith(("http:", "https:")) or tok in NEVER_READ:
        return None
    rel = norm(tok)
    if not rel:
        return None
    if "/" in rel:
        if rel.split("/")[0] in SKIP_DIRS:
            return None
        ap = os.path.join(BRAIN, rel.rstrip("/").replace("/", os.sep))
        if os.path.isdir(ap):
            return rel.rstrip("/") + "/", True
        if os.path.isfile(ap) and os.path.basename(ap) not in NEVER_READ:
            return rel, False
        return None
    leaves = live_leaves()
    cands = leaves.get(rel) or leaves.get(rel + ".md") or leaves.get(rel + ".canvas") or []
    if len(cands) == 1:
        return cands[0], False
    if os.path.isdir(os.path.join(BRAIN, rel)) and rel not in SKIP_DIRS:
        return rel + "/", True
    return None


def live_pointers(text):
    """The pointers in a piece of text, in reading order: backticked paths, wikilinks (not the navigation ones), bare filenames."""
    out, spans = [], []
    for m in TICK_RE.finditer(text):
        out.append((m.start(), m.group(1))); spans.append((m.start(), m.end()))
    for m in WIKI_RE.finditer(text):
        spans.append((m.start(), m.end()))
        before = text[max(0, m.start() - 20):m.start()]
        alias = (m.group(2) or "").lower()
        if NAV_BEFORE_RE.search(before) or "open" in alias or "→" in alias:
            continue                                     # "🔍 Open: [[x]]", "⬆ Up: [[x]]", "[[x|open →]]": a drill-down, not what the node is
        out.append((m.start(), m.group(1)))
    for m in BARE_RE.finditer(text):
        if any(a <= m.start() < z for a, z in spans):
            continue                                     # already a wikilink or a backtick (a navigation wikilink stays skipped)
        out.append((m.start(), m.group(1)))
    out.sort(key=lambda t: t[0])
    return [t for _, t in out]


def live_names():
    """What the ladder can bind a name to: the registry's holons (by id, by name, by declared path), the skill folders, the agent ids the log has seen."""
    reg = registry()
    holons = [h for h in reg.get("holons", []) if h.get("id")]
    by_path = {}
    for h in holons:
        raw = str(h.get("path") or "").strip()
        if raw:
            by_path[raw] = h["id"]                # a folder path keeps its trailing slash in the registry, a file path has none
    sk = os.path.join(BRAIN, "skills")
    skills = sorted(d for d in (os.listdir(sk) if os.path.isdir(sk) else []) if os.path.isdir(os.path.join(sk, d)) and not d.startswith((".", "_")))
    rows, agents = log_rows()
    return {"holons": holons, "byId": {h["id"]: h for h in holons}, "byPath": by_path, "skills": skills, "agents": agents,
            "_key": (reg.get("_updated"), tuple(skills), len(agents))}


def word_in(word, text):
    return re.search(r"(?<![\w\-])" + re.escape(word.lower()) + r"(?![\w\-])", text) is not None


def live_skill_doc(name):
    """Where a skill binding opens: its skill doc, its readme, else the first .md in its folder."""
    d = os.path.join(BRAIN, "skills", name)
    for fn in (name + "-skill.md", "readme.md", "README.md"):
        if os.path.isfile(os.path.join(d, fn)):
            return "skills/%s/%s" % (name, fn)
    md = sorted(f for f in os.listdir(d) if f.lower().endswith(".md")) if os.path.isdir(d) else []
    return "skills/%s/%s" % (name, md[0]) if md else None


def live_binding(kind, target, names, via, label=None):
    """The full binding row for a kind + target: the short name, where a click goes, and for a file its facts."""
    b = {"kind": kind, "target": target, "label": label or target, "href": None, "via": via}
    if kind in ("file", "canvas", "folder"):
        ap = os.path.join(BRAIN, target.rstrip("/").replace("/", os.sep))
        b["label"] = target.rstrip("/").split("/")[-1] + ("/" if kind == "folder" else "")
        b["exists"] = os.path.isdir(ap) if kind == "folder" else os.path.isfile(ap)
        if b["exists"] and kind != "folder":
            st = os.stat(ap)
            b["mtime"] = dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
            b["size"] = st.st_size
        if kind == "canvas":
            b["href"] = "/forge?mode=live&path=" + urllib.parse.quote(target)
        elif kind == "file" and target.lower().endswith(".md"):
            b["href"] = "/reader?path=" + urllib.parse.quote(target)
        elif kind == "folder":
            hid = names["byPath"].get(target)
            if hid:
                return live_binding("holon", hid, names, via)
    elif kind == "holon":
        h = names["byId"].get(target)
        if not h:
            return None
        b["label"] = h.get("name") or target
        b["href"] = ("/projects?id=" + urllib.parse.quote(target)) if h.get("tasks") else "/projects?holon=%s#holons" % urllib.parse.quote(target)
        b["path"] = h.get("path")
    elif kind == "skill":
        if target not in names["skills"]:
            return None
        doc = live_skill_doc(target)
        b["href"] = ("/reader?path=" + urllib.parse.quote(doc)) if doc else None
        b["doc"] = doc
    elif kind == "agent":
        b["href"] = "/chat#running"
    elif kind == "route":
        b["href"] = target
    elif kind == "service":
        row = next((s for s in LIVE_SERVICES if s[0] == target), None)
        b["href"] = row[3] if row else (target if str(target).startswith("http") else None)
    elif kind == "concept":
        b["label"] = "concept"
    return b


def live_bind(n, names, saved):
    """One node -> its binding, by the ladder in the module note. A saved binding (the sibling .forge.json) wins."""
    row = (saved.get(n.get("id")) or {}).get("binding")
    if isinstance(row, dict) and row.get("kind") not in (None, "", "concept") and row.get("target"):
        b = live_binding(row["kind"], row["target"], names, "saved")
        if b:
            return b
    t = n.get("type")
    if t == "file":
        r = live_resolve_path(n.get("file"))
        if not r:
            return live_binding("file", str(n.get("file") or ""), names, "file node", label=str(n.get("file") or "").split("/")[-1])
        return live_binding("folder" if r[1] else ("canvas" if r[0].lower().endswith(".canvas") else "file"), r[0], names, "file node")
    if t == "link":
        url = str(n.get("url") or "")
        svc = next((name for host, name in LIVE_HOSTS if host in url.lower()), None)
        return live_binding("service", svc or url, names, "link node", label=svc or url.split("/")[2] if "//" in url else url)
    text = str(n.get("text") if t == "text" else n.get("label") or "")
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    title = lines[0] if lines else ""
    tplain, tlow = live_plain(title), live_plain(title).lower()
    if re.match(r"^\*\*(assumed[ ]+)?output\b", title.strip(), re.I):
        return live_binding("concept", None, names, "output")   # a cell's mouth: what it hands on. The fields behind it are read from the real thing (/api/forge/fields); the mouth itself is never a thing
    # 1. the title line's own pointer
    for tok in live_pointers(title):
        r = live_resolve_path(tok)
        if r:
            return live_binding("folder" if r[1] else ("canvas" if r[0].lower().endswith(".canvas") else "file"), r[0], names, "title pointer")
    # 2. a holon id or name on the title line (the longest name that fits wins)
    best = None
    for h in names["holons"]:
        for cand in (h["id"], str(h.get("name") or "")):
            if cand and len(cand) > 2 and word_in(cand, tlow) and (best is None or len(cand) > len(best[0])):
                best = (cand, h["id"])
    if best:
        return live_binding("holon", best[1], names, "title holon")
    # 3. a skill folder name on the title line
    for s in names["skills"]:
        if word_in(s, tlow) or (("-" in s) and word_in(s.replace("-", " "), tlow)):
            return live_binding("skill", s, names, "title skill")
    # 4. an agent id the log has seen, on the title line
    for a in sorted(names["agents"], key=len, reverse=True):
        if len(a) > 3 and (word_in(a, tlow) or (("-" in a) and word_in(a.replace("-", " "), tlow))):
            return live_binding("agent", a, names, "title agent")
    # 5. a pointer anywhere in the text
    for tok in live_pointers(text):
        r = live_resolve_path(tok)
        if r:
            return live_binding("folder" if r[1] else ("canvas" if r[0].lower().endswith(".canvas") else "file"), r[0], names, "text pointer")
    low = live_plain(text).lower()
    # 6. a route of this app, anywhere; "the home page" is /
    for route in sorted(LIVE_ROUTES, key=len, reverse=True):
        if re.search(r"(?<![\w/])" + re.escape(route) + r"(?![\w\-])", text):
            return live_binding("route", route, names, "route")
    if re.search(r"\bhome page\b|\bthe home\b", low):
        return live_binding("route", "/", names, "route", label="home")
    # 7. an outside service, the title first
    for scope, via in ((tlow, "title service"), (low, "text service")):
        for name, node_re, _, _ in LIVE_SERVICES:
            if re.search(node_re, scope, re.I):
                return live_binding("service", name, names, via)
    # 8. a holon id or a skill name anywhere in the text (ids are slugs, so this stays specific)
    for h in names["holons"]:
        if word_in(h["id"], low):
            return live_binding("holon", h["id"], names, "text holon")
    for s in names["skills"]:
        if word_in(s, low):
            return live_binding("skill", s, names, "text skill")
    return live_binding("concept", None, names, "unresolved")


def live_log_pattern(b, leaves):
    k, t = b["kind"], str(b.get("target") or "").lower()
    if not t:
        return None
    if k in ("file", "canvas", "folder"):
        pats = [re.escape(t.rstrip("/") if k != "folder" else t)]
        leaf = t.rstrip("/").split("/")[-1]
        if k != "folder" and len(leaves.get(b["label"], [])) == 1:
            pats.append(r"(?<![\w/.\-])" + re.escape(leaf) + r"(?![\w])")
        return re.compile("|".join(pats))
    if k == "holon":
        pats = [r"(?<![\w\-])" + re.escape(t) + r"(?![\w\-])"]
        if b.get("label") and b["label"].lower() != t:
            pats.append(r"\b" + re.escape(b["label"].lower()) + r"\b")
        if b.get("path"):
            pats.append(re.escape(str(b["path"]).lower()))
        return re.compile("|".join(pats))
    if k == "skill":
        return re.compile(r"skills/" + re.escape(t) + r"\b|(?<![\w\-])" + re.escape(t) + r"(?![\w\-])")
    if k == "agent":
        return re.compile(r"(?<![\w\-])" + re.escape(t) + r"(?![\w\-])")
    if k == "route":
        return re.compile(r"(?<![\w/])" + re.escape(t) + r"(?![\w\-])") if t != "/" else re.compile(r"\bhome page\b|\bthe home\b|chat\.html|/api/waiting")
    if k == "service":
        row = next((s for s in LIVE_SERVICES if s[0] == b["target"]), None)
        return re.compile(row[2], re.I) if row else None
    return None


def live_sessions_today(today):
    d = sessions_dir()
    if not d:
        return 0, None
    n, newest = 0, None
    for fn in os.listdir(d):
        if not fn.endswith(".jsonl"):
            continue
        mt = os.path.getmtime(os.path.join(d, fn))
        iso = dt.datetime.fromtimestamp(mt).isoformat(timespec="seconds")
        if iso[:10] == today:
            n += 1
        if newest is None or iso > newest:
            newest = iso
    return n, newest


def live_activity(b, rows, today, leaves, ctx):
    """The runtime layer for one binding: the log lines that name it, plus the evidence its kind carries."""
    pat = live_log_pattern(b, leaves)
    hits = [r for r in rows if pat.search(r["low"])] if pat else []
    if b["kind"] == "agent":
        hits = [r for r in rows if r["agent"] == b["target"] or (pat and pat.search(r["low"]))]
    since14 = (dt.date.today() - dt.timedelta(days=LIVE_DAYS)).isoformat()
    a = {"count14": len(hits), "today": sum(1 for r in hits if r["date"] == today),
         "lastAt": hits[-1]["at"] if hits else None, "lastAction": hits[-1]["action"] if hits else None,
         "lastAgent": hits[-1]["agent"] if hits else None,
         "lines": [{"at": r["at"], "agent": r["agent"], "action": r["action"], "text": clip(r["text"], 180)} for r in hits[-LIVE_LINES:][::-1]]}
    score_today, active14 = a["today"], a["count14"] > 0
    if b["kind"] in ("file", "canvas") and b.get("mtime"):
        a["mtime"] = b["mtime"]
        if b["mtime"][:10] == today:
            score_today += 1
        if b["mtime"][:10] >= since14:
            active14 = True
    if b["kind"] == "holon":
        h = ctx["names"]["byId"].get(b["target"]) or {}
        if h.get("status"):
            try:
                st = read_json_rel(h["status"])[0] or {}
                gen = str(st.get("_generatedAt") or "")
                a["statusAt"] = gen or None
                if gen[:10] == today:
                    score_today += 1
                if gen[:10] >= since14:
                    active14 = True
            except Exception:
                pass
    if b["kind"] == "agent":
        n, newest = ctx["sessions"]
        a["sessionsToday"], a["lastSession"] = n, newest
        if n:
            score_today += 1
            active14 = True
    if b["kind"] == "service" and b["target"] == "team copy":
        ts = ctx.get("team") or {}
        le = (ts.get("last_export") or {})
        at = str(le.get("at") or "")
        when = iso_utc(at)
        local = when.astimezone().isoformat(timespec="seconds") if when else None
        a["teamCopy"] = {"lastExport": local, "files": le.get("files"), "unpushed": (ts.get("remote") or {}).get("unpushed"),
                         "behind": (ts.get("remote") or {}).get("behind"), "inboxOpen": (ts.get("requests") or {}).get("inbox_open")}
        if local and local[:10] == today:
            score_today += 1
        if local and local[:10] >= since14:
            active14 = True
    if b["kind"] == "service" and b["target"] in ("PF App", "onboarding app"):
        fer = re.compile(r"push\.py|pull\.py|\bferryman\b" if b["target"] == "PF App" else r"onboarding-api-pull|onboarding-app-holon")
        last = next((r for r in reversed(rows) if (b["target"] == "PF App" and r["agent"] == "ferryman") or fer.search(r["low"])), None)
        if last:
            a["lastFerry"] = {"at": last["at"], "agent": last["agent"], "action": last["action"], "text": clip(last["text"], 160)}
    a["todayScore"] = score_today
    a["active14"] = active14 or score_today > 0
    return a


# ---- part state, display only (0.67.0, viewer Q-0025, the owner's 9/21 question: "if the brain is able to keep track of
# the actual progression"). Each bound part of a drawing reads as one of three, from records the brain already keeps and
# never from the drawing: NOT BUILT when the thing it points at does not exist (or it points at nothing), BUILDING when an
# open ledger item links its path or route, WORKING when the live layer saw it in the last LIVE_DAYS. A part that exists,
# has no open item and was quiet is "quiet". A cell's mouth (an output) and a cell itself carry no state. Nothing is stored.
def open_link_targets():
    """{normalized target: [(project, id)]} for every link on every open task, question or blocked task: a brain path (a
    [[wikilink]]'s leaf resolved when it is unique), or a route of this app (the part before any query)."""
    out = {}
    for it in thread_ledgers():
        if not thread_open(it) and it.get("mark") != "-":
            continue
        for raw in it.get("links") or []:
            t = str(raw).strip()
            m = re.match(r"^\[\[(.+?)\]\]$", t)
            if m:
                t = m.group(1).split("|")[0].strip()
            t = t.partition("#")[0].strip()
            if t.startswith("/"):
                key = t.split("?")[0].rstrip("/") or "/"
            else:
                if "/" not in t:
                    cands = resolve_map().get(t) or resolve_map().get(t + ".md") or []
                    t = cands[0] if len(cands) == 1 else t
                key = norm(t) or t
            if key:
                out.setdefault(key, []).append((it.get("project"), it.get("id")))
    return out


def part_state(b, a, links):
    """not built | building | working | quiet for one binding and its activity; None for a mouth."""
    if not b or b.get("via") == "output":
        return None, []
    k, t = b.get("kind"), str(b.get("target") or "")
    keys = []
    if k in ("file", "canvas", "folder"):
        keys = [t.rstrip("/"), t]
    elif k == "route":
        keys = [t.split("?")[0].rstrip("/") or "/"]
    elif k == "skill":
        doc = b.get("doc") or ""
        keys = ["skills/" + t, "skills/" + t + "/", doc] + [x for x in links if x.startswith("skills/%s/" % t)]
    elif k == "holon":
        keys = [str(b.get("path") or "").rstrip("/"), str(b.get("path") or "")] + [x for x in links if b.get("path") and x.startswith(str(b["path"]))]
    by = [ref for key in keys if key for ref in links.get(key, [])]
    if by:
        return "building", by[:5]
    if k == "concept" or (k in ("file", "canvas", "folder") and not b.get("exists")):
        return "not built", []
    if (a or {}).get("active14"):
        return "working", []
    return "quiet", []


def live_api(rel):
    """GET /api/live?path=: every node of a canvas bound to the real thing it stands for, and lit by the last LIVE_DAYS of evidence."""
    rel = norm(rel)
    ap = read_abs(rel) if rel else None
    if not ap or not rel.lower().endswith(".canvas") or not os.path.isfile(ap):
        return None, "canvas not found"
    with open(ap, "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    meta = read_forge_meta(rel) or {}
    saved = meta.get("nodes") or {}
    names = live_names()
    sib_ap = os.path.join(BRAIN, forge_sibling(rel).replace("/", os.sep))
    key = (os.path.getmtime(ap), os.path.getmtime(sib_ap) if os.path.isfile(sib_ap) else None, names["_key"])
    hit = _live_cache.get(rel)
    if hit and hit[0] == key:
        bindings = hit[1]
    else:
        bindings = {n["id"]: live_bind(n, names, saved) for n in d.get("nodes", []) if n.get("id")}
        _live_cache[rel] = (key, bindings)
        if len(_live_cache) > 80:
            _live_cache.clear()
    rows, _ = log_rows()
    today = dt.date.today().isoformat()
    leaves = live_leaves()
    team = None
    if os.path.isfile(os.path.join(BRAIN, TEAM_STATUS_REL.replace("/", os.sep))):
        team = read_json_rel(TEAM_STATUS_REL)[0]
    ctx = {"names": names, "sessions": live_sessions_today(today), "team": team}
    nodes = {}
    try:
        links = open_link_targets()
    except Exception:                                             # noqa: BLE001
        links = {}
    cell_ids = {n.get("id") for n in d.get("nodes", []) if is_cell(n) or n.get("type") == "group"}
    # a text note that is not a typed part ("**Type · Name**" on its first line) is a caption, not a part: no state
    cell_ids |= {n.get("id") for n in d.get("nodes", []) if n.get("type") == "text"
                 and " · " not in (str(n.get("text") or "").strip().split("\n") or [""])[0]}
    for nid, b in bindings.items():
        nodes[nid] = {"binding": b, "activity": live_activity(b, rows, today, leaves, ctx) if b["kind"] != "concept"
                      else {"count14": 0, "today": 0, "lastAt": None, "lastAction": None, "lastAgent": None, "lines": [], "todayScore": 0, "active14": False}}
        st, by = (None, []) if nid in cell_ids else part_state(b, nodes[nid]["activity"], links)
        nodes[nid]["state"] = st
        if by:
            nodes[nid]["stateBy"] = ["%s/%s" % x for x in by]
    edges = {}
    for e in d.get("edges", []):
        a, z = nodes.get(e.get("fromNode")), nodes.get(e.get("toNode"))
        edges[e.get("id")] = {"today": bool(a and z and a["activity"]["todayScore"] and z["activity"]["todayScore"]),
                              "active14": bool(a and z and a["activity"]["active14"] and z["activity"]["active14"])}
    kinds = {}
    for r in nodes.values():
        kinds[r["binding"]["kind"]] = kinds.get(r["binding"]["kind"], 0) + 1
    last = max((r["activity"]["lastAt"] or "" for r in nodes.values()), default="") or None
    counts = {"nodes": len(nodes), "bound": sum(1 for r in nodes.values() if r["binding"]["kind"] != "concept"),
              "concept": kinds.get("concept", 0), "activeToday": sum(1 for r in nodes.values() if r["activity"]["todayScore"]),
              "active14": sum(1 for r in nodes.values() if r["activity"]["active14"]),
              "edges": len(edges), "edgesToday": sum(1 for x in edges.values() if x["today"]),
              "saved": sum(1 for r in nodes.values() if r["binding"].get("via") == "saved"),
              "states": {k: sum(1 for r in nodes.values() if r.get("state") == k) for k in ("not built", "building", "working", "quiet")}}
    return {"path": rel, "generatedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "today": today, "days": LIVE_DAYS,
            "order": ["saved binding", "title pointer", "title holon", "title skill", "title agent", "text pointer", "route", "service", "text holon or skill", "concept"],
            "nodes": nodes, "edges": edges, "counts": counts, "kinds": kinds, "lastAt": last,
            "forgePath": forge_sibling(rel), "forgeExists": meta != {} or os.path.isfile(sib_ap),
            "editable": writable(forge_sibling(rel)), "propose": PROPOSE,
            "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")}, None


def live_save_bindings(rel):
    """POST /api/live/bindings {path}: the one write of the live layer -- the resolved bindings copied into the sibling .forge.json,
    binding: {kind, target} under each node id, a concept node's row cleared of any old binding. Nothing the page sends shapes the file."""
    live, err = live_api(rel)
    if err:
        return None, err
    sib = live["forgePath"]
    if not writable(sib):
        return None, "the sibling .forge.json is outside the Forge's write scope"
    meta = read_forge_meta(live["path"]) or {"_schema": "forge/1", "canvas": live["path"], "nodes": {}}
    meta["nodes"] = meta.get("nodes") or {}
    k, kinds = 0, {}
    for nid, row in live["nodes"].items():
        b, r = row["binding"], dict(meta["nodes"].get(nid) or {})
        if b["kind"] == "concept" or not b.get("target"):
            r.pop("binding", None)
        else:
            r["binding"] = {"kind": b["kind"], "target": b["target"]}
            k += 1
            kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
        if r:
            meta["nodes"][nid] = r
        else:
            meta["nodes"].pop(nid, None)
    meta["_updated"] = dt.datetime.now().isoformat(timespec="seconds")
    body = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    note = "Live map: bindings saved for %d of %d nodes (%s)" % (k, len(live["nodes"]), ", ".join("%d %s" % (v, kk) for kk, v in sorted(kinds.items(), key=lambda x: -x[1])) or "none")
    if PROPOSE:
        req = propose("file", sib, {"content": body}, note=note)
        return {"proposed": True, "request": req, "kind": "file", "target": sib, "saved": k}, None
    ap = os.path.join(BRAIN, sib.replace("/", os.sep))
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    _live_cache.pop(live["path"], None)
    return {"ok": True, "path": sib, "saved": k, "nodes": len(live["nodes"]), "log": log_line("%s -- %s" % (sib, note))}, None


def maps_manifest():
    ap = os.path.join(BRAIN, MAPS_REL.replace("/", os.sep))
    if not os.path.isfile(ap):
        return {"groups": []}
    with open(ap, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def maps_api():
    """GET /api/maps: the picker -- the maps by purpose as the manifest declares them, each with its live counts, and every other canvas folded by family."""
    cv = canvases()
    by_path = {c["path"]: c for c in cv}
    man = maps_manifest()
    used, groups = set(), []

    def row(path, purpose):
        c = by_path.get(path)
        r = {"path": path, "name": (c or {}).get("name") or path.split("/")[-1].replace(".canvas", ""), "purpose": purpose or "",
             "exists": bool(c), "mtime": (c or {}).get("mtime"), "family": (c or {}).get("family"),
             "cells": (c or {}).get("cells", 0), "nodes": (c or {}).get("nodes", 0), "edges": (c or {}).get("edges", 0), "counts": None, "lastAt": None}
        if c:
            try:
                live, err = live_api(path)
                if live:
                    r["counts"], r["lastAt"] = live["counts"], live["lastAt"]
            except Exception as e:
                r["error"] = "%s: %s" % (type(e).__name__, e)
        return r

    # every group's named maps first, then a family group takes what is left of its folder: a canvas named by a later
    # group (the daily workflow, drawn in womb-phase/) stays where it was named
    for g in man.get("groups", []):
        rows = []
        for m in g.get("maps", []):
            if m.get("path") and m["path"] not in used:
                rows.append(row(m["path"], m.get("purpose"))); used.add(m["path"])
        groups.append({"id": g.get("id"), "name": g.get("name"), "purpose": g.get("purpose") or "", "maps": rows, "_family": g.get("family"), "_fp": g.get("familyPurpose") or ""})
    for g in groups:
        if g["_family"]:
            for c in cv:
                if c["family"] == g["_family"] and c["path"] not in used:
                    g["maps"].append(row(c["path"], g["_fp"])); used.add(c["path"])
        g["lastAt"] = max((r["lastAt"] or "" for r in g["maps"]), default="") or None
        del g["_family"], g["_fp"]
    other = {}
    for c in cv:
        if c["path"] not in used:
            other.setdefault(c["family"], []).append({"path": c["path"], "name": c["name"], "mtime": c["mtime"], "nodes": c["nodes"], "edges": c["edges"], "header": c.get("header", "")})
    # the filtering rule: the picker opens on the map active most recently; a tie on the minute goes to the one with more moving today
    recent = max(((r["lastAt"] or "", (r["counts"] or {}).get("activeToday", 0), r["path"], g["id"]) for g in groups for r in g["maps"]), default=None)
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "manifest": MAPS_REL, "days": LIVE_DAYS, "groups": groups,
            "other": [{"family": f, "canvases": rows} for f, rows in sorted(other.items())],
            "mostRecent": {"path": recent[2], "group": recent[3], "at": recent[0] or None} if recent and recent[0] else None,
            "retired": {"route": "/map", "note": "the moving graph of 2026-09-09 retired with the live maps; the route still answers, off the nav"}}
