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
BOARD_STATUS = {"live": "4", "planned": "2", "maybe": "3"}      # the canvas colour per step status: green, orange, yellow
BOARD_STATUS_WORDS = {"live": "running today", "planned": "planned, not running yet", "maybe": "maybe, not decided"}
FORM_TYPES = ("short", "long", "email", "phone", "number", "date", "url", "choice", "multi", "yesno", "scale")
FORM_NEEDS_OPTIONS = ("choice", "multi")
BOARD_W, BOARD_GAP, BOARD_ATT_GAP = 420, 140, 26               # a step tile's width, the gap between steps, between attachments
BOARD_VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")
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


def board_step(rel, folder=None):
    """One step file -> {path, slug, title, status, who, when, summary, files, video, form, problems}."""
    folder = folder if folder is not None else posixpath.dirname(rel)
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
    problems = [] if status in BOARD_STATUS else ["status '%s' is not live, planned or maybe" % status]
    form = None
    fkey = next((k for k in secs if k.startswith("form")), None)
    if fkey:
        ftitle = re.sub(r"^form\s*[:·—-]?\s*", "", titles.get(fkey, ""), flags=re.I).strip() or title
        form = form_parse(secs[fkey], ftitle)
        problems += form["problems"]
    files = board_links(secs.get("files", []), folder)
    video = board_links(secs.get("video", []), folder)
    problems += ["%s is linked but not found" % r["target"] for r in files + video if r["target"] and not r["exists"]]
    return {"path": rel, "slug": os.path.splitext(posixpath.basename(rel))[0], "title": title, "status": status,
            "who": str(fm.get("who") or "").strip(), "when": str(fm.get("when") or "").strip(),
            "summary": " ".join(para), "files": files, "video": video, "form": form, "problems": problems}


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
    out = {"path": board_rel, "canvas": board_rel[:-len(BOARD_SUFFIX)] + ".canvas", "folder": folder,
           "title": str(fm.get("board") or h1 or posixpath.basename(folder)), "kind": str(fm.get("kind") or "steps").lower(),
           "intro": "\n".join(intro), "up": str(fm.get("up") or "").strip(), "steps": [], "lanes": [], "end": None,
           "then": [], "problems": []}

    def steps_of(lines):
        rows = []
        for r in board_links(lines, folder):
            if not r["exists"] or not r["path"].lower().endswith(".md"):
                out["problems"].append("%s is listed but not found" % (r["target"] or r["note"]))
                continue
            try:
                s = board_step(r["path"], folder)
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


def _board_step_text(step, n=None):
    head = "## %s%s" % ("%s. " % n if n is not None else "", step["title"])
    rows = [head]
    if step["summary"]:
        rows.append(step["summary"])
    meta = [x for x in (("**Who** " + step["who"]) if step["who"] else "", ("**When** " + step["when"]) if step["when"] else "") if x]
    if meta:
        rows.append(" · ".join(meta))
    rows.append("*%s*" % BOARD_STATUS_WORDS.get(step["status"], step["status"]))
    return "\n\n".join(rows)      # a paragraph each: a single line break runs the lines together when the tile is drawn


def _board_column(step, x, y):
    """The step's attachments stacked under its tile: the form, the video or its slot, each document, the step's own file.
    Returns (nodes, bottom)."""
    nodes, sid = [], step["slug"]
    if step["form"]:
        fq = step["form"]["questions"]
        req = sum(1 for q in fq if q["required"])
        opt = sum(1 for q in fq if q["required"] is False)
        words = "%d question%s" % (len(fq), "" if len(fq) == 1 else "s")
        if opt:
            words += ", %d optional" % opt
        elif req and req < len(fq):
            words += ", %d required" % req
        t = "📝 **Form:** %s\n\n%s · [Open the form](%s)" % (step["form"]["title"], words, _board_form_href(step))
        h = _board_h(t)
        nodes.append({"id": "%s-form" % sid, "type": "text", "x": x, "y": y, "width": BOARD_W, "height": h, "color": "5", "text": t})
        y += h + BOARD_ATT_GAP
    for i, v in enumerate(step["video"]):
        if v["exists"]:
            nodes.append({"id": "%s-video-%d" % (sid, i), "type": "file", "file": v["path"], "x": x, "y": y, "width": BOARD_W, "height": 240})
            y += 240 + 8
            if v["note"]:
                t = "🎬 %s" % v["note"]
                h = _board_h(t)
                nodes.append({"id": "%s-video-%d-note" % (sid, i), "type": "text", "x": x, "y": y, "width": BOARD_W, "height": h, "text": t})
                y += h
            y += BOARD_ATT_GAP - 8
        else:
            t = "🎬 **Video slot**, not made yet\n\n%s" % (v["note"] or v["target"] or "")
            h = _board_h(t)
            nodes.append({"id": "%s-video-%d" % (sid, i), "type": "text", "x": x, "y": y, "width": BOARD_W, "height": h, "color": "6", "text": t.strip()})
            y += h + BOARD_ATT_GAP
    for i, r in enumerate(step["files"]):
        if r["exists"]:
            h = 240 if r["kind"] == "video" else 90
            nodes.append({"id": "%s-file-%d" % (sid, i), "type": "file", "file": r["path"], "x": x, "y": y, "width": BOARD_W, "height": h})
        else:
            t = "📄 **Not found:** %s%s" % (r["target"] or "", ("\n\n" + r["note"]) if r["note"] else "")
            h = _board_h(t)
            nodes.append({"id": "%s-file-%d" % (sid, i), "type": "text", "x": x, "y": y, "width": BOARD_W, "height": h, "color": "1", "text": t})
        y += h + BOARD_ATT_GAP
    nodes.append({"id": "%s-source" % sid, "type": "file", "file": step["path"], "x": x, "y": y, "width": BOARD_W, "height": 70})
    return nodes, y + 70


def _board_edge(a, b, label=None):
    e = {"id": "e-%s--%s" % (a, b), "fromNode": a, "fromSide": "right", "toNode": b, "toSide": "left"}
    if label:
        e["label"] = label
    return e


def board_canvas(b):
    """A board -> the JSON Canvas the Forge and Obsidian draw: the header, a tile per step with its attachments stacked
    under it, a line from each step to the next. Ids are the step files' names, so a redraw changes only what changed."""
    nodes, edges = [], []
    legend = "**Colours** green running today · orange planned · yellow maybe · blue a form · purple a video not made yet"
    how = ("Drawn from the files in this folder each time it opens; change a step's file, not this drawing. "
           "A document joins a step as a line under `## Files` in the step's file, a video under `## Video`, "
           "questions under `## Form`.")
    head = ["🧭 **%s**, a step board" % b["title"]]
    if b["intro"]:
        head.append(b["intro"])
    head.append(how)
    if b["up"]:
        head.append("⬆ Up: [[%s]]" % (board_resolve(b["up"], b["folder"]) or b["up"]))
    head.append("Board file: [[%s]]" % b["path"])
    head.append(legend)
    if b["kind"] == "funnels":
        lanes = b["lanes"]
        longest = max([len(l["steps"]) for l in lanes] or [1])
        x0, lane_w = 0, 300
        y = 0
        lane_mid = []
        for li, lane in enumerate(lanes):
            tiles = [(_board_step_text(s), s) for s in lane["steps"]]
            th = max([_board_h(t) for t, _ in tiles] or [80])
            bottom = y + th
            lid = "lane-%d" % (li + 1)
            nodes.append({"id": lid, "type": "text", "x": x0, "y": y, "width": lane_w, "height": th,
                          "text": "### %s\n%d step%s" % (lane["name"], len(tiles), "" if len(tiles) == 1 else "s")})
            prev = lid
            for si, (t, s) in enumerate(tiles):
                x = x0 + lane_w + BOARD_GAP + si * (BOARD_W + BOARD_GAP)
                nodes.append({"id": s["slug"], "type": "text", "x": x, "y": y, "width": BOARD_W, "height": th,
                              "color": BOARD_STATUS.get(s["status"], "2"), "text": t})
                col, bot = _board_column(s, x, y + th + BOARD_ATT_GAP)
                nodes += col
                bottom = max(bottom, bot)
                edges.append(_board_edge(prev, s["slug"]))
                prev = s["slug"]
            lane_mid.append((prev, y + th / 2))
            y = bottom + 120
        end = b["end"]
        ex = x0 + lane_w + BOARD_GAP + longest * (BOARD_W + BOARD_GAP) + 60
        if end:
            t = _board_step_text(end)
            eh = _board_h(t)
            ey = max(0, int((y - 120) / 2 - eh / 2))
            nodes.append({"id": end["slug"], "type": "text", "x": ex, "y": ey, "width": BOARD_W, "height": eh,
                          "color": BOARD_STATUS.get(end["status"], "2"), "text": t})
            col, _ = _board_column(end, ex, ey + eh + BOARD_ATT_GAP)
            nodes += col
            for last, _mid in lane_mid:
                if last != end["slug"]:
                    edges.append(_board_edge(last, end["slug"]))
            tx, prev = ex + BOARD_W + BOARD_GAP, end["slug"]
            for i, r in enumerate(b["then"]):
                nid = "then-%d" % (i + 1)
                nodes.append({"id": nid, "type": "file", "file": r["path"], "x": tx, "y": ey, "width": BOARD_W, "height": 120})
                edges.append(_board_edge(prev, nid, r["note"] or None))
                prev, tx = nid, tx + BOARD_W + BOARD_GAP
        top_w = ex + BOARD_W
    else:
        steps = b["steps"]
        tiles = [(_board_step_text(s, i + 1), s) for i, s in enumerate(steps)]
        th = max([_board_h(t) for t, _ in tiles] or [80])
        prev = None
        for i, (t, s) in enumerate(tiles):
            x = i * (BOARD_W + BOARD_GAP)
            nodes.append({"id": s["slug"], "type": "text", "x": x, "y": 0, "width": BOARD_W, "height": th,
                          "color": BOARD_STATUS.get(s["status"], "2"), "text": t})
            col, _ = _board_column(s, x, th + BOARD_ATT_GAP)
            nodes += col
            if prev:
                edges.append(_board_edge(prev, s["slug"]))
            prev = s["slug"]
        tx = len(tiles) * (BOARD_W + BOARD_GAP)
        for i, r in enumerate(b["then"]):
            nid = "then-%d" % (i + 1)
            nodes.append({"id": nid, "type": "file", "file": r["path"], "x": tx, "y": 0, "width": BOARD_W, "height": 120})
            if prev:
                edges.append(_board_edge(prev, nid, r["note"] or None))
            prev, tx = nid, tx + BOARD_W + BOARD_GAP
        top_w = max(BOARD_W, tx - BOARD_GAP)
    ht = "\n\n".join(head)
    hw = min(max(BOARD_W * 2 + BOARD_GAP, int(top_w * 0.6)), 1600)
    hh = _board_h(ht, hw)
    nodes.insert(0, {"id": "board-header", "type": "text", "x": 0, "y": -hh - 90, "width": hw, "height": hh, "text": ht})
    return {"nodes": nodes, "edges": edges}


def board_draw(board_rel, log=True):
    """Write the drawing a board file describes when it differs from the one on disk. Returns (changed, canvas_rel, board)."""
    b = board_read(board_rel)
    body = json.dumps(board_canvas(b), ensure_ascii=False, indent=2) + "\n"
    ap = os.path.join(BRAIN, b["canvas"].replace("/", os.sep))
    try:
        with open(ap, "r", encoding="utf-8") as f:
            if f.read() == body:
                return False, b["canvas"], b
    except FileNotFoundError:
        pass
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    if log:
        log_line("step board %s redrawn from its files (%d steps)" % (b["canvas"], sum(len(l["steps"]) for l in b["lanes"])
                 + (1 if b["end"] else 0) if b["kind"] == "funnels" else len(b["steps"])))
    return True, b["canvas"], b


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
