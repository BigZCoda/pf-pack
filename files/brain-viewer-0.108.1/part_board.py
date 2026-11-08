"""part_board.py -- step boards: a process drawn in the Forge as steps, each step one markdown file (viewer 0.102.0).

Loaded into serve.py's namespace by load_part(), like the other part files; `skills/brain-viewer/board.py` is its terminal
side (draw, check, link, form). The contract is written for people in `step-boards-contract.md` beside this file.

A BOARD is one folder under the Forge's root holding
  <slug>-board.md      the order: `## Steps` (one line, in order) or `## Lanes` + `## Ends at` (several ways in, one end)
  <slug>.canvas        the drawing, DERIVED from the files here on every read in the Forge; never edited by hand
  <step files>.md      one per step: what happens, `## Files`, `## Video`, and at most one `## Form` of tagged questions
The drawing is the board's view, the files are the record: a document is attached to a step by a line under that step's
`## Files`, a video by a line under `## Video`, and the next read of the drawing shows it. Nothing here asks the drawing
for anything.

A FORM is the questions under a step's `## Form` heading, one numbered line each, tagged at the end of the line:
  1. Your name #short #required
  2. Which of these apply? #multi #optional
     - First choice
     - Second choice
     *An indented line that is not an option is the question's help text.*
The tags are FORM_TYPES (the input) plus #required or #optional; a question with neither is drawn with no mark, as a
paper form leaves it. GET /api/form reads one as data, /form draws it, and `board.py form --json | --html` hands the
same data to an agent or a web page, so the markdown is the only copy of the questions.
"""
import posixpath

BOARD_SUFFIX = "-board.md"
BOARD_STATUS_WORDS = {"live": "running today", "planned": "planned, not running yet", "maybe": "maybe, not decided"}
FORM_TYPES = ("short", "long", "email", "phone", "number", "date", "url", "choice", "multi", "yesno", "scale")
FORM_NEEDS_OPTIONS = ("choice", "multi")
BOARD_W = 420                                                   # the width a text tile's height is reckoned at
BOARD_VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")
# A step's modulators (0.106.0): every frontmatter key that is not the step's own is a facet drawn on its cell, each
# known to a registry (modulators.json in the board's folder or the folder above it, else the default below) that gives
# it a label, a family, a help line and the other spellings it is read under. A facet there with no value is drawn
# "not set"; one not written is not drawn; a key the registry does not know is drawn grey as new and is a problem for
# `board.py check`, so a session that wants a new one adds its row. Six families, each with a colour (light, dark), in
# the order they sit round the rim. `## On the way to the next step` is what the line to the next step carries.
BOARD_OWN_KEYS = ("step", "status", "master")                   # the step file's own lines, never modulators
BOARD_FAMILIES = (                                               # key, label, what it answers, colour, dark colour
    ("where", "Where", "where it lives, where it is reached", "#2a9d8f", "#5fd3c4"),
    ("who", "Who", "who is on it, who it is for", "#d99a2b", "#f1c566"),
    ("why", "Why", "what it is for, what is true after", "#7b5ea7", "#b39ddb"),
    ("looks", "How it looks", "its shape to the person", "#c9607a", "#f08ca4"),
    ("inout", "In and out", "what it needs, what it makes, where that goes", "#3b7dd8", "#7fb0f5"),
    ("when", "When", "what starts it, how long, how often", "#7a9a3b", "#b5d36a"),
)
BOARD_DEFAULT_MODULATORS = (                                     # key, label, family, help, also written as
    ("location", "Location", "where", "Where it lives: email, a form, a page of our own, in person.", ("venue", "place")),
    ("address", "Address", "where", "The link or path to the live thing.", ("link", "url")),
    ("home", "Home", "where", "Where its record sits in the brain.", ()),
    ("attendees", "Attendees", "who", "Who is on it.", ("who", "people")),
    ("owner", "Owner", "who", "Who runs the step.", ("runs",)),
    ("audience", "Audience", "who", "Who it is for.", ()),
    ("handoff", "Handoff", "who", "Who receives the result.", ("hand-off",)),
    ("purpose", "Purpose", "why", "What this step is for.", ("goal",)),
    ("outcome", "Outcome", "why", "What is true after it.", ()),
    ("decides", "Decides", "why", "What gets settled here.", ()),
    ("measure", "Measure", "why", "How you know it worked.", ()),
    ("style", "Style", "looks", "How it looks to the person.", ("look",)),
    ("voice", "Voice", "looks", "Whose words it is in.", ("tone",)),
    ("length", "Length", "looks", "How long it is.", ()),
    ("template", "Template", "looks", "The pattern it follows.", ()),
    ("prep", "Prep", "inout", "What is written before it.", ()),
    ("needs", "Needs", "inout", "What must exist before it.", ("input",)),
    ("produces", "Produces", "inout", "What it makes.", ("output",)),
    ("delivers", "Delivers to", "inout", "Where what it makes goes.", ("delivers to", "delivers-to")),
    ("endpoint", "Endpoint", "inout", "The API it talks to.", ("api",)),
    ("format", "Format", "inout", "The shape of what it makes.", ()),
    ("when", "When", "when", "What starts it.", ("trigger",)),
    ("duration", "Duration", "when", "How long it takes.", ("takes",)),
    ("cadence", "Cadence", "when", "How often.", ("every",)),
    ("followup", "Follow-up", "when", "What happens after, and by when.", ("follow-up", "follow up")),
)
BOARD_REGISTRY = "modulators.json"
BOARD_MOD_STATES = ("not set", "set", "made", "checked")        # a modulator's own state, never the Forge's live states
BOARD_MOD_MODES = ("band", "outside")                            # the two drawn versions: segments of the rim, or boxes against it
BOARD_STAGE = {"live": "built", "planned": "concept", "maybe": "concept"}   # a cell's stage on the Forge's rim badge
BOARD_CELL, BOARD_CELL_GAP = 760, 640                           # a step cell's box and the gap between two cells (room for the
                                                                 # boxes of the outside version on both sides of the line)
_BOARD_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]|\[([^\]]+)\]\(([^)\s]+)\)|`([^`]+\.[A-Za-z0-9]{1,6})`")
_BOARD_Q_RE = re.compile(r"^\s{0,3}(\d+)[.)]\s+(.*\S)\s*$")
_BOARD_TAGS_RE = re.compile(r"((?:\s+#[A-Za-z][A-Za-z0-9-]*)+)\s*$")


def board_split(text):
    """(frontmatter dict, body) of a markdown file; a `key: [a, b]` value comes back as a list."""
    fm, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].splitlines():
                if ":" in line and not line.startswith((" ", "\t", "-", "#")):
                    k, v = line.split(":", 1)
                    v = v.split(" #", 1)[0].strip().strip('"').strip("'")
                    fm[k.strip()] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()] \
                        if v.startswith("[") and v.endswith("]") else v
            body = text[end + 4:].lstrip("\r\n")
    return fm, body


def board_sections(body):
    """{lower-cased level-2 heading: [lines]} plus '' for the lines before the first one, and the H1 when there is one.
    The heading's own words are kept under (heading, 'title') for a `## Form: <title>`."""
    out, titles, cur, h1 = {"": []}, {}, "", ""
    for line in body.splitlines():
        m = re.match(r"^(#{1,2})\s+(.*\S)\s*$", line)
        if m and len(m.group(1)) == 1 and not h1 and cur == "":
            h1 = m.group(2).strip()
            continue
        if m and len(m.group(1)) == 2:
            words = m.group(2).strip()
            key = re.split(r"[\s:·—-]", words.lower(), 1)[0]
            cur = key if key not in out else key + "+"
            out[cur], titles[cur] = [], words
            continue
        out[cur].append(line)
    return out, titles, h1


def board_resolve(target, folder):
    """A link as written ([[leaf]], [[path]], a relative path) -> a brain-relative path, or None when nothing matches.
    The board's own folder is tried first, then the brain root, then the leaf name anywhere (leaf names are unique)."""
    t = str(target or "").strip().replace("\\", "/")
    if not t or re.match(r"^[a-z]+://", t, re.I) or t.startswith("/"):
        return None
    cands = []
    for base in (folder, ""):
        p = posixpath.normpath(posixpath.join(base, t)) if base else posixpath.normpath(t)
        cands += [p, p + ".md"]
    for p in cands:
        if norm(p) and os.path.exists(os.path.join(BRAIN, p.replace("/", os.sep))):
            return p
    leaf = t.split("/")[-1]
    leaves = live_leaves()
    for name in (leaf, leaf + ".md"):
        hits = leaves.get(name) or []
        if len(hits) == 1:
            return hits[0]
    if os.path.splitext(leaf)[1].lower() in BOARD_VIDEO_EXT:   # a video is not in the leaf index (it lists text files)
        for root, dirs, files in os.walk(BRAIN):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if leaf in files:
                return os.path.relpath(os.path.join(root, leaf), BRAIN).replace(os.sep, "/")
    return None


def board_kind(rel):
    ext = os.path.splitext(rel or "")[1].lower()
    return ("video" if ext in BOARD_VIDEO_EXT else "drawing" if ext == ".canvas" else
            "image" if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp") else "document")


def board_links(lines, folder):
    """The list lines of a `## Files` or `## Video` section, one row each: {target, path, words, note, exists, kind}.
    A line with no link is a slot: {path: None, note: the line}. A note follows the link after a ` · ` or an em-free dash."""
    rows = []
    for line in lines:
        m = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$", line)
        if not m:
            continue
        item = m.group(1)
        lm = _BOARD_LINK_RE.search(item)
        if not lm:
            rows.append({"target": None, "path": None, "words": "", "note": item, "exists": False, "kind": "slot"})
            continue
        target = lm.group(1) or lm.group(4) or lm.group(5)
        words = (lm.group(2) or lm.group(3) or "").strip()
        rest = (item[:lm.start()] + item[lm.end():]).strip()
        note = re.sub(r"^[·:|-]+\s*", "", rest).strip()
        path = board_resolve(target, folder)
        rows.append({"target": target.strip(), "path": path, "words": words or posixpath.basename(path or target.strip()),
                     "note": note, "exists": bool(path), "kind": board_kind(path or target)})
    return rows


def form_slug(text, seen):
    s = re.sub(r"[^a-z0-9]+", "-", re.sub(r"\*+|_+", "", text.lower())).strip("-")
    s = "-".join(s.split("-")[:5]) or "question"
    base, i = s, 2
    while s in seen:
        s, i = "%s-%d" % (base, i), i + 1
    seen.add(s)
    return s


def form_parse(lines, title=""):
    """The lines under a `## Form` heading -> {title, blocks, questions, problems}. Blocks keep the written order:
    {kind: text, md} for a paragraph, {kind: section, text} for a `###` heading or a line that is all bold, and
    {kind: question, ...} for a numbered line. A problem is something the page can still draw but the writer should fix."""
    blocks, problems, seen, para, q = [], [], set(), [], None

    def flush():
        if para:
            blocks.append({"kind": "text", "md": "\n".join(para).strip()})
            para.clear()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            flush()
            if not line.strip():
                continue
            q = None
            continue
        if q is not None and re.match(r"^(\s{2,}|\t)", line):          # indented under a question: an option or help
            om = re.match(r"^\s+[-*+]\s+(.*\S)\s*$", line)
            if om:
                q["options"].append(om.group(1).strip())
            else:
                q["help"] = ((q["help"] + "\n\n") if q["help"] else "") + line.strip()   # each line its own paragraph
            continue
        hm = re.match(r"^#{3,6}\s+(.*\S)\s*$", line) or re.match(r"^\s*\*\*([^*].*?)\*\*\s*$", line)
        if hm:
            flush()
            q = None
            blocks.append({"kind": "section", "text": hm.group(1).strip()})
            continue
        qm = _BOARD_Q_RE.match(line)
        if qm:
            flush()
            words, tags = qm.group(2), []
            tm = _BOARD_TAGS_RE.search(words)
            if tm:
                tags = [t[1:].lower() for t in tm.group(1).split()]
                words = words[:tm.start()].rstrip()
            words = re.sub(r"^\*\*(.*)\*\*$", r"\1", words.strip()).strip()
            types = [t for t in tags if t in FORM_TYPES or re.match(r"^scale-\d+-\d+$", t)]
            unknown = [t for t in tags if t not in types and t not in ("required", "optional")]
            q = {"kind": "question", "n": qm.group(1), "id": form_slug(words, seen), "text": words,
                 "type": "short", "required": None, "options": [], "help": "", "min": None, "max": None, "tags": tags}
            if types:
                t = types[0]
                if t.startswith("scale"):
                    q["type"], q["min"], q["max"] = "scale", 1, 5
                    sm = re.match(r"^scale-(\d+)-(\d+)$", t)
                    if sm:
                        q["min"], q["max"] = int(sm.group(1)), int(sm.group(2))
                else:
                    q["type"] = t
            else:
                problems.append("question %s has no type tag, so it is drawn as one line" % q["n"])
            if len(types) > 1:
                problems.append("question %s has two type tags; the first, #%s, is used" % (q["n"], types[0]))
            if "required" in tags and "optional" in tags:
                problems.append("question %s is tagged both #required and #optional" % q["n"])
            q["required"] = True if "required" in tags else False if "optional" in tags else None
            for t in unknown:
                problems.append("question %s carries #%s, which is not a form tag" % (q["n"], t))
            blocks.append(q)
            continue
        q = None
        para.append(line.strip())
    flush()
    questions = [b for b in blocks if b["kind"] == "question"]
    for q in questions:
        if q["type"] == "yesno" and not q["options"]:
            q["options"] = ["Yes", "No"]
        if q["type"] in FORM_NEEDS_OPTIONS and not q["options"]:
            problems.append("question %s is #%s but lists no options under it" % (q["n"], q["type"]))
        if q["options"] and q["type"] not in FORM_NEEDS_OPTIONS + ("yesno",):
            problems.append("question %s lists options but is #%s, so they are not drawn" % (q["n"], q["type"]))
    if not questions:
        problems.append("the form has no numbered questions")
    return {"title": title, "blocks": blocks, "questions": questions, "problems": problems}


def _mod_key(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").strip().lower()).strip("-")


def board_registry(folder):
    """The modulator registry a board's folder answers to: modulators.json there, else in the folder above it, else the
    default written in this file. -> {path, families, mods (by key), alias (other spelling -> key), order}."""
    families = [{"key": k, "label": lb, "answers": a, "color": c, "colorDark": cd} for k, lb, a, c, cd in BOARD_FAMILIES]
    mods = [{"key": k, "label": lb, "family": fam, "help": h, "alsoWrittenAs": list(also), "mode": "manual", "values": {}}
            for k, lb, fam, h, also in BOARD_DEFAULT_MODULATORS]
    path, folder = None, (folder or "").strip("/")
    for cand in (folder, posixpath.dirname(folder)):
        rel = (cand + "/" if cand else "") + BOARD_REGISTRY
        ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        if os.path.isfile(ap):
            try:
                with open(ap, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                if isinstance(data.get("families"), list) and data["families"]:
                    families = [dict(x) for x in data["families"] if isinstance(x, dict) and x.get("key")]
                if isinstance(data.get("modulators"), list):
                    mods = [dict(x) for x in data["modulators"] if isinstance(x, dict) and x.get("key")]
                path = rel
            except (OSError, ValueError):
                pass
            break
    fkeys = [f["key"] for f in families]
    by, alias, order = {}, {}, []
    for m in mods:
        k = _mod_key(m.get("key"))
        if not k or k in by:
            continue
        m = dict(m, key=k)
        m.setdefault("label", k.replace("-", " ").capitalize())
        m["family"] = m.get("family") if m.get("family") in fkeys else None
        m.setdefault("help", "")
        m["alsoWrittenAs"] = [_mod_key(a) for a in (m.get("alsoWrittenAs") or []) if _mod_key(a)]
        m.setdefault("mode", "manual")
        m["values"] = m.get("values") if isinstance(m.get("values"), dict) else {}
        by[k] = m
        order.append(k)
    for k in order:
        for a in by[k]["alsoWrittenAs"]:
            if a not in by:
                alias.setdefault(a, k)
    return {"path": path, "families": families, "mods": by, "alias": alias, "order": order}


def board_mods(fm, reg):
    """A step's frontmatter -> its modulators in family order: every key that is not the step's own, read through the
    registry (a key written under another spelling is read as the one it stands for; one the registry does not know is
    new), each with its value, help, family and state."""
    famorder = {f["key"]: i for i, f in enumerate(reg["families"])}
    seen, out = set(), []
    for raw, val in fm.items():
        k = _mod_key(raw)
        if not k or k in BOARD_OWN_KEYS:
            continue
        key = k if k in reg["mods"] else reg["alias"].get(k, k)
        if key in seen or (key != k and _mod_key(key) in {_mod_key(x) for x in fm}):
            continue                                                  # the spelling it stands for is written too
        seen.add(key)
        row = reg["mods"].get(key)
        value = str(val or "").strip()
        out.append({"key": key, "written": k, "label": row["label"] if row else k.replace("-", " ").capitalize(),
                    "family": row["family"] if row else None, "help": row["help"] if row else "",
                    "value": value, "state": "set" if value else "not set", "new": row is None, "address": None})
    addr = next((m["value"] for m in out if m["key"] == "address" and m["value"]), None)
    for m in out:
        if m["key"] == "location" and m["value"] and addr:
            m["state"], m["address"] = "made", addr                   # the thing behind it exists: its link is on the step
            out = [x for x in out if x["key"] != "address"]           # the address is the location's link, not a box of its own
            break
    out.sort(key=lambda m: (famorder.get(m["family"], len(famorder)), reg["order"].index(m["key"]) if m["key"] in reg["order"] else 999))
    return out


def board_step(rel, folder=None, reg=None):
    """One step file -> {path, slug, title, status, master, summary, files, video, form, mods, way, problems}."""
    folder = folder if folder is not None else posixpath.dirname(rel)
    reg = reg or board_registry(folder)
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    with open(ap, "r", encoding="utf-8-sig") as f:
        text = f.read()
    fm, body = board_split(text)
    secs, titles, h1 = board_sections(body)
    title = str(fm.get("step") or h1 or os.path.splitext(posixpath.basename(rel))[0]).strip()
    para = []
    for line in secs.get("", []):
        if line.strip() and not line.lstrip().startswith((">", "#", "<!--")):
            para.append(line.strip())
        elif para:
            break
    status = str(fm.get("status") or "planned").strip().lower()
    problems = [] if status in BOARD_STAGE else ["status '%s' is not live, planned or maybe" % status]
    form = None
    fkey = next((k for k in secs if k.startswith("form")), None)
    if fkey:
        ftitle = re.sub(r"^form\s*[:·—-]?\s*", "", titles.get(fkey, ""), flags=re.I).strip() or title
        form = form_parse(secs[fkey], ftitle)
        problems += form["problems"]
    files = board_links(secs.get("files", []), folder)
    video = board_links(secs.get("video", []), folder)
    problems += ["%s is linked but not found" % r["target"] for r in files + video if r["target"] and not r["exists"]]
    mods = board_mods(fm, reg)
    slug = os.path.splitext(posixpath.basename(rel))[0]
    for m in mods:
        if m["new"]:
            problems.append("unknown modulator '%s': add it to %s, or write it as one the registry knows" % (
                m["written"], reg["path"] or BOARD_REGISTRY))
    master = str(fm.get("master") or "file").strip().lower()
    if master not in ("file", "live"):
        problems.append("master '%s' is not file or live" % master)
        master = "file"
    way = [re.sub(r"^\s*[-*+]\s+", "", l).strip() for l in secs.get("on", []) if re.match(r"^\s*[-*+]\s+\S", l)]
    return {"path": rel, "slug": slug, "title": title, "status": status, "master": master,
            "summary": " ".join(para), "files": files, "video": video, "form": form, "mods": mods, "way": way,
            "problems": problems}


def board_of(canvas_rel):
    """The board file beside a drawing (<dir>/<stem>-board.md), or None when the drawing is not a board's."""
    rel = norm(canvas_rel or "")
    if not rel or not rel.lower().endswith(".canvas"):
        return None
    b = rel[:-len(".canvas")] + BOARD_SUFFIX
    return b if os.path.isfile(os.path.join(BRAIN, b.replace("/", os.sep))) else None


def board_read(board_rel):
    """A board file -> {path, canvas, title, kind, intro, up, steps | lanes + end + then, problems}."""
    folder = posixpath.dirname(board_rel)
    with open(os.path.join(BRAIN, board_rel.replace("/", os.sep)), "r", encoding="utf-8-sig") as f:
        fm, body = board_split(f.read())
    secs, titles, h1 = board_sections(body)
    intro = [l.strip() for l in secs.get("", []) if l.strip() and not l.lstrip().startswith(("#", "<!--"))]
    reg = board_registry(folder)
    mode = str(fm.get("modulators") or "band").strip().lower()
    out = {"path": board_rel, "canvas": board_rel[:-len(BOARD_SUFFIX)] + ".canvas", "folder": folder,
           "title": str(fm.get("board") or h1 or posixpath.basename(folder)), "kind": str(fm.get("kind") or "steps").lower(),
           "intro": "\n".join(intro), "up": str(fm.get("up") or "").strip(), "steps": [], "lanes": [], "end": None,
           "then": [], "problems": [], "registry": reg, "modulators": mode if mode in BOARD_MOD_MODES else "band"}
    if mode not in BOARD_MOD_MODES:
        out["problems"].append("modulators '%s' is not band or outside" % mode)

    def steps_of(lines):
        rows = []
        for r in board_links(lines, folder):
            if not r["exists"] or not r["path"].lower().endswith(".md"):
                out["problems"].append("%s is listed but not found" % (r["target"] or r["note"]))
                continue
            try:
                s = board_step(r["path"], folder, reg)
            except Exception as e:
                out["problems"].append("%s could not be read: %s" % (r["path"], e))
                continue
            out["problems"] += ["%s: %s" % (s["slug"], p) for p in s["problems"]]
            rows.append(s)
        return rows

    if out["kind"] == "funnels":
        lane, lines = None, []
        for line in secs.get("lanes", []):
            m = re.match(r"^###\s+(.*\S)\s*$", line)
            if m:
                if lane is not None:
                    out["lanes"].append({"name": lane, "steps": steps_of(lines)})
                lane, lines = m.group(1), []
            else:
                lines.append(line)
        if lane is not None:
            out["lanes"].append({"name": lane, "steps": steps_of(lines)})
        ends = steps_of(secs.get("ends", []))
        out["end"] = ends[0] if ends else None
        if not out["end"]:
            out["problems"].append("a funnels board names the step every lane ends at under ## Ends at")
    else:
        out["steps"] = steps_of(secs.get("steps", []))
        if not out["steps"]:
            out["problems"].append("the board lists no steps under ## Steps")
    out["then"] = [r for r in board_links(secs.get("then", []), folder) if r["exists"]]
    return out


def _board_h(text, w=BOARD_W):
    """A text tile's height for its words: the Forge and Obsidian both cut what does not fit, so this errs tall."""
    per = max(20, int((w - 30) / 7.6))
    lines = 0
    for line in text.splitlines():
        s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", re.sub(r"\[\[[^\]|]*\|?([^\]]*)\]\]", r"\1", line))
        s = re.sub(r"[*#`]", "", s)
        lines += max(1, -(-len(s) // per)) if s.strip() else 0.5      # a blank line is a paragraph's margin, not a line
    return max(80, int(34 + 23 * lines))


def _board_form_href(step):
    return "/form?path=" + urllib.parse.quote(step["path"], safe="/")


def _board_text(nid, x, y, w, h, color, text):
    n = {"id": nid, "type": "text", "x": x, "y": y, "width": w, "height": h, "text": text}
    if color:
        n["color"] = color
    return n


def _board_cell(step, n, x, y, families=None):
    """One step as a Forge cell: the group the Forge draws as a circle, its outer band (the modulators, drawn as segments on
    the rim or as boxes against it, each in its family's colour) and its inner layer (what the step is, its form, its
    video, its documents and its own file, drawn inside). The first line of a part is **<Type> · <Name>**, the Forge's
    typed part. Returns (nodes, size)."""
    sid, cid = step["slug"], "cell-" + step["slug"]
    pw, ph, gx, gy, pad = 300, 92, 20, 20, 40
    colour = {f["key"]: f.get("color") for f in (families or [])}
    band = [("%s-mod-%s" % (sid, m["key"]), colour.get(m["family"]) if m["value"] and not m["new"] else None,
             "**Modulator · %s: %s**\n%s" % (m["label"], m["value"] or "not set", m["help"])) for m in step["mods"]]
    core = []
    core.append(("text", "%s-about" % sid, "6", "**Step · %s**\n%s\n\n*%s*" % (
        step["title"], step["summary"], BOARD_STATUS_WORDS.get(step["status"], step["status"]))))
    if step["form"]:
        fq = step["form"]["questions"]
        opt = sum(1 for q in fq if q["required"] is False)
        words = "%d question%s%s" % (len(fq), "" if len(fq) == 1 else "s", (", %d optional" % opt) if opt else "")
        core.append(("text", "%s-form" % sid, "3", "**Form · %s**\n%s\n\n[Open the form](%s)" % (
            step["form"]["title"], words, _board_form_href(step))))
    for i, v in enumerate(step["video"]):
        if v["exists"]:
            core.append(("file", "%s-video-%d" % (sid, i), v["path"], None))
        else:
            core.append(("text", "%s-video-%d" % (sid, i), "2", "**Video · not made yet**\n%s" % (v["note"] or v["target"] or "")))
    for i, r in enumerate(step["files"]):
        if r["exists"]:
            core.append(("file", "%s-file-%d" % (sid, i), r["path"], None))
        else:
            core.append(("text", "%s-file-%d" % (sid, i), "1", "**Missing · %s**\n%s" % (r["target"] or "a file", r["note"])))
    core.append(("file", "%s-source" % sid, step["path"], None))
    band_rows = -(-len(band) // 2)
    core_rows = -(-len(core) // 2)
    band_h = (pad + band_rows * (ph + gy) + gy) if band else 0
    core_h = pad + core_rows * (ph + gy) + gy
    size = max(BOARD_CELL, 2 * pad + band_h + (gy if band else 0) + core_h + 2 * pad)
    inner_w = size - 2 * pad
    pw = min(pw, (inner_w - 3 * gx) // 2)
    nodes = [{"id": cid, "type": "group", "x": x, "y": y, "width": size, "height": size, "color": "6",
              "label": ("%d · %s" % (n, step["title"])) if n else step["title"]}]
    cy = y + 2 * pad
    if band:
        nodes.append({"id": cid + "-band", "type": "group", "x": x + pad, "y": cy, "width": inner_w, "height": band_h,
                      "color": "3", "label": "outer band · modulators"})
        for k, (nid, color, text) in enumerate(band):
            nodes.append(_board_text(nid, x + pad + gx + (k % 2) * (pw + gx), cy + pad + (k // 2) * (ph + gy), pw, ph, color, text))
        cy += band_h + gy
    nodes.append({"id": cid + "-core", "type": "group", "x": x + pad, "y": cy, "width": inner_w, "height": core_h,
                  "color": "5", "label": "inner layer · the step"})
    for k, item in enumerate(core):
        px, py = x + pad + gx + (k % 2) * (pw + gx), cy + pad + (k // 2) * (ph + gy)
        if item[0] == "file":
            nodes.append({"id": item[1], "type": "file", "file": item[2], "x": px, "y": py, "width": pw, "height": ph})
        else:
            nodes.append(_board_text(item[1], px, py, pw, ph, item[2], item[3]))
    return nodes, size


def _board_edge(a, b, label=None):
    e = {"id": "e-%s--%s" % (a, b), "fromNode": a, "fromSide": "right", "toNode": b, "toSide": "left"}
    if label:
        e["label"] = label
    return e


def _board_way(step):
    return " · ".join(step.get("way") or []) or None


def board_canvas(b, keep=None):
    """A board -> the JSON Canvas the Forge and Obsidian draw: the header, one cell per step (its modulators on the rim, its
    form, video and documents inside), a line from each step to the next carrying what happens on the way. keep is the
    drawing as it stands: a cell or the header found there by its id keeps its place, so a step moved in the Forge stays
    where it was put; everything else comes from the files. Ids are the step files' names."""
    keep = {n.get("id"): n for n in ((keep or {}).get("nodes") or [])}
    nodes, edges = [], []

    families = (b.get("registry") or {}).get("families") or []

    def place(step, n, x, y):
        old = keep.get("cell-" + step["slug"])
        ox, oy = (old["x"], old["y"]) if old else (x, y)
        cell, size = _board_cell(step, n, ox, oy, families)
        nodes.extend(cell)
        return size

    how = ("Each step is a cell: its modulators sit on the rim or against it, one colour per family, its form, video and "
           "documents inside, and the line to the next step says what happens on the way. Drawn from the files in this "
           "folder each time it opens: change a step's file for its words, drag a step in edit to move it.")
    head = ["🧭 **%s**, a step board" % b["title"]]
    if b["intro"]:
        head.append(b["intro"])
    head.append(how)
    if b["up"]:
        head.append("⬆ Up: [[%s]]" % (board_resolve(b["up"], b["folder"]) or b["up"]))
    head.append("Board file: [[%s]]" % b["path"])
    step_w = BOARD_CELL + BOARD_CELL_GAP
    if b["kind"] == "funnels":
        lanes, x0, lane_w, y = b["lanes"], 0, 360, 0
        longest = max([len(l["steps"]) for l in lanes] or [1])
        lasts = []
        for li, lane in enumerate(lanes):
            lid = "lane-%d" % (li + 1)
            nodes.append(_board_text(lid, x0, y + BOARD_CELL // 2 - 60, lane_w, 120, None,
                                     "### %s\n%d step%s" % (lane["name"], len(lane["steps"]), "" if len(lane["steps"]) == 1 else "s")))
            prev, prev_step, row_h = lid, None, BOARD_CELL
            for si, s in enumerate(lane["steps"]):
                row_h = max(row_h, place(s, None, x0 + lane_w + BOARD_CELL_GAP + si * step_w, y))
                edges.append(_board_edge(prev, "cell-" + s["slug"], _board_way(prev_step) if prev_step else None))
                prev, prev_step = "cell-" + s["slug"], s
            if lane["steps"]:
                lasts.append(lane["steps"][-1])
            y += row_h + BOARD_CELL_GAP
        end = b["end"]
        ex = x0 + lane_w + BOARD_CELL_GAP + longest * step_w + 200
        top_w = ex + BOARD_CELL
        if end:
            ey = max(0, int((y - BOARD_CELL_GAP) / 2 - BOARD_CELL / 2))
            size = place(end, None, ex, ey)
            for s in lasts:
                if s["slug"] != end["slug"]:
                    edges.append(_board_edge("cell-" + s["slug"], "cell-" + end["slug"], _board_way(s)))
            tx, prev = ex + size + BOARD_CELL_GAP, "cell-" + end["slug"]
            for i, r in enumerate(b["then"]):
                nid = "then-%d" % (i + 1)
                nodes.append({"id": nid, "type": "file", "file": r["path"], "x": tx, "y": ey + size // 2 - 60, "width": 420, "height": 120})
                edges.append(_board_edge(prev, nid, r["note"] or None))
                prev, tx = nid, tx + 420 + BOARD_CELL_GAP
            top_w = tx
    else:
        prev, x = None, 0
        for i, s in enumerate(b["steps"]):
            size = place(s, i + 1, x, 0)
            if prev:
                edges.append(_board_edge("cell-" + prev["slug"], "cell-" + s["slug"], _board_way(prev)))
            prev, x = s, x + size + BOARD_CELL_GAP
        for i, r in enumerate(b["then"]):
            nid = "then-%d" % (i + 1)
            nodes.append({"id": nid, "type": "file", "file": r["path"], "x": x, "y": BOARD_CELL // 2 - 60, "width": 420, "height": 120})
            if prev:
                edges.append(_board_edge("cell-" + prev["slug"], nid, r["note"] or None))
            prev, x = None, x + 420 + BOARD_CELL_GAP
        top_w = max(BOARD_CELL, x - BOARD_CELL_GAP)
    ht = "\n\n".join(head)
    hw = min(max(1200, int(top_w * 0.5)), 1800)
    hh = _board_h(ht, hw)
    old = keep.get("board-header")
    hx, hy = (old["x"], old["y"]) if old else (0, -hh - 200)
    nodes.insert(0, _board_text("board-header", hx, hy, hw, hh, None, ht))
    return {"nodes": nodes, "edges": edges}


def board_steps(b):
    return ([s for l in b["lanes"] for s in l["steps"]] + ([b["end"]] if b["end"] else [])) if b["kind"] == "funnels" else b["steps"]


def board_meta(b, rel):
    """The drawing's sibling .forge.json: each step cell's stage from its status (live: built; planned, maybe: concept) and
    its master; under `board`, the drawn version (band or outside), the families with their colours, the registry's path,
    and the made and checked records (`<step>/<key>`: when, and the address) that lift a modulator's state; each
    modulator part's row carries `mod` (key, label, family, value, state, new, help, address) and its connector (the
    address when one is known, else the step file). Every other row the Forge wrote is kept."""
    try:
        meta = read_forge_meta(rel) or {}
    except Exception:
        meta = {}
    meta = dict(meta)
    meta.setdefault("_schema", "forge/1")
    meta["canvas"] = rel
    rows = dict(meta.get("nodes") or {})
    reg = b.get("registry") or board_registry(b["folder"])
    old = meta.get("board") if isinstance(meta.get("board"), dict) else {}
    made = {k: v for k, v in (old.get("made") or {}).items() if isinstance(v, dict)}
    checked = {k: v for k, v in (old.get("checked") or {}).items() if isinstance(v, dict)}
    meta["board"] = {"modulators": b.get("modulators") or "band", "families": reg["families"], "registry": reg["path"],
                     "made": made, "checked": checked}
    for s in board_steps(b):
        row = dict(rows.get("cell-" + s["slug"]) or {})
        row["stage"] = BOARD_STAGE.get(s["status"], "concept")
        row["master"] = s["master"]
        rows["cell-" + s["slug"]] = row
        now = {"%s-mod-%s" % (s["slug"], m["key"]) for m in s["mods"]}
        for nid in [k for k in rows if k.startswith(s["slug"] + "-mod-") and k not in now]:
            del rows[nid]                                             # a modulator taken off the step leaves no row behind
        for m in s["mods"]:
            key = s["slug"] + "/" + m["key"]
            state, address = m["state"], m["address"]
            if m["value"] and key in made:
                state, address = "made", address or made[key].get("address")
            if state == "made" and key in checked:
                state = "checked"
            nid = "%s-mod-%s" % (s["slug"], m["key"])
            mrow = dict(rows.get(nid) or {})
            mrow["mod"] = {"key": m["key"], "label": m["label"], "family": m["family"], "value": m["value"], "state": state,
                           "new": m["new"], "help": m["help"], "address": address}
            mrow["connector"] = address or s["path"]
            rows[nid] = mrow
    meta["nodes"] = rows
    return meta


def board_draw(board_rel, log=True):
    """Write the drawing a board file describes, and its sibling's stages, when they differ from what is on disk; a cell
    keeps the place it has in the drawing on disk. Returns (changed, canvas_rel, board)."""
    b = board_read(board_rel)
    ap = os.path.join(BRAIN, b["canvas"].replace("/", os.sep))
    try:
        with open(ap, "r", encoding="utf-8") as f:
            old_text = f.read()
        old = json.loads(old_text)
    except (OSError, ValueError):
        old_text, old = None, None
    body = json.dumps(board_canvas(b, old), ensure_ascii=False, indent=2) + "\n"
    changed = body != old_text
    if changed:
        with open(ap, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
    mrel = forge_sibling(b["canvas"])
    mp = os.path.join(BRAIN, mrel.replace("/", os.sep))
    mbody = json.dumps(board_meta(b, b["canvas"]), ensure_ascii=False, indent=2) + "\n"
    try:
        with open(mp, "r", encoding="utf-8") as f:
            mold = f.read()
    except OSError:
        mold = None
    if mbody != mold:
        with open(mp, "w", encoding="utf-8", newline="\n") as f:
            f.write(mbody)
        changed = True
    if changed and log:
        n_steps = (sum(len(l["steps"]) for l in b["lanes"]) + (1 if b["end"] else 0)) if b["kind"] == "funnels" else len(b["steps"])
        log_line("step board %s redrawn from its files (%d steps)" % (b["canvas"], n_steps))
    return changed, b["canvas"], b


def board_redraw_if_board(canvas_rel):
    """Called by the Forge's read (forge_api): a board's drawing is redrawn from its files first, so a document linked in
    a step file shows the next time the drawing opens. Never raises: a broken board leaves the last drawing as it was.
    In a team copy (TEAM_REL at its root) nothing is written: the drawing arrives from the owner's side with the export,
    a step file the member changes goes back through her sync and is drawn there, and a drawing redrawn on both sides
    would come back to the owner as a clash, since her copy lacks some of the files the steps link."""
    br = board_of(canvas_rel)
    if not br:
        return None
    try:
        if os.path.isfile(os.path.join(BRAIN, TEAM_REL)):
            b = board_read(br)
            return {"board": br, "redrawn": False, "problems": b["problems"][:20], "kind": b["kind"], "drawnBy": "owner"}
        changed, _, b = board_draw(br)
        return {"board": br, "redrawn": changed, "problems": b["problems"][:20], "kind": b["kind"]}
    except Exception as e:
        return {"board": br, "redrawn": False, "problems": ["the board could not be read: %s" % e]}


def form_api(rel):
    """GET /api/form?path=<a step file or any .md with a ## Form>: the form as data, the step's title and its board."""
    rel = norm(rel or "")
    ap = read_abs(rel) if rel else None
    if not ap or not rel.lower().endswith(".md") or not os.path.isfile(ap):
        return 404, {"error": "no such markdown file"}
    s = board_step(rel)
    if not s["form"]:
        return 404, {"error": "this file has no ## Form section", "path": rel}
    folder = posixpath.dirname(rel)
    board = None
    for fn in sorted(os.listdir(os.path.join(BRAIN, folder.replace("/", os.sep)))):
        if fn.endswith(BOARD_SUFFIX):
            board = {"path": posixpath.join(folder, fn), "canvas": posixpath.join(folder, fn[:-len(BOARD_SUFFIX)] + ".canvas")}
            break
    return 200, {"path": rel, "step": s["title"], "status": s["status"], "form": s["form"], "board": board}
