#!/usr/bin/env python3
"""part_manual.py -- the manual of the brain and the viewer (0.94.0, 2026-10-26).

The owner asked on 2026-10-26 for "a full comprehensive manual of the brain/viewer that maybe organizes all of the
readmes of all of the different features + other info of it so that they can be seen and added to as it grows"; his
words and the shape are section M of brain-viewer-holon/brain-viewer-ideas.md. Nothing here keeps a copy of anything.
The book is put together at the moment it is asked for, from
  * the chapter order, brain-viewer-holon/brain-viewer-manual.md: the only hand-written part (the order, one "how it
    fits" paragraph per chapter, and which sources each chapter draws);
  * the help cards in skills/brain-viewer/help.json: a page's what, its three-step workflow and its parts, and the card
    of each instrument of the board (the `widgets` key);
  * the vocabulary, the `glossary` key of the same file (2026-10-28, the glossary page folded into the manual): a chapter
    line `- for you: glossary` draws every group with its note, every word as a section of its own whose id is
    term-<anchor> (the anchor serve.glossary_api computes, so /manual#term-<anchor> lands on it), then the keys as one
    table;
  * the folder readmes, the skill readmes and the skills' entries in skills/skill-registry.md;
  * the definition page and the rules, a whole document or one section of it;
and every section carries the file it came from and the day that file last changed, so a stale one shows its age.

The person's own layer is viewer/manual/: notes on a chapter or a section in notes/<section id>.md, the readmes of the
widgets they wrote in modules/<widget id>.md. user_layer() reads those beside their settings, their board, their looks
and their widgets as they stand, so What you changed lists everything of theirs against what the viewer ships. No
update, export or pull writes into viewer/ (brain-viewer-plugin-contract.md).

Three readers share this one file, so they never disagree about what the manual holds:
  serve.py            GET /api/manual, PUT /api/manual/note and PUT /api/manual/module (imported, like part_usage.py)
  brain-lint L21      placement(): a folder, a page or a module with no chapter fails rounds
  the librarian       keeper(): readmes and cards missing, readmes their folder has outgrown, filed as proposals by
                      skills/librarian-sweep/check-manual.py

The Verifier (in the brain's own word: the mechanical checker that prints CLEAN or named discrepancies) is verify():
every folder has a readme and a chapter, every page and module a card, no readme older than a newer file in its folder
it does not name, every link the manual draws resolves, and the person's own layer parses. brain-lint L21 runs it at
rounds; the librarian's weekly run prints it and reads the book cold on the live viewer (check-manual.py).

Run alone, from the brain folder:
  python skills/brain-viewer/part_manual.py              the book's outline, one line per chapter and section
  python skills/brain-viewer/part_manual.py --verify     the Verifier: CLEAN, or one line per discrepancy (exit 1)
  python skills/brain-viewer/part_manual.py --gaps       what has no place in the manual (placement alone)
  python skills/brain-viewer/part_manual.py --keeper     the librarian's checks, as JSON
"""
import ast
import datetime as dt
import fnmatch
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHAPTERS_REL = "brain-viewer-holon/brain-viewer-manual.md"   # the maintainer brain's chapter order
CHAPTERS_SHIPPED = "brain-viewer-manual.md"                   # beside this file, in a brain a release shipped one to
REGISTRY_REL = "skills/skill-registry.md"
USER_MANUAL_REL = "viewer/manual"
NOTES_REL = USER_MANUAL_REL + "/notes"
MODULES_REL = USER_MANUAL_REL + "/modules"
USER_WIDGETS_REL = "viewer/widgets"
USER_LOOKS_REL = "viewer/looks"
USER_SETTINGS_REL = "viewer/settings.json"
USER_LAYOUTS_REL = "viewer/layouts"
# Top-level folders that are not part of the brain the manual explains: build output, the archive on the external drive.
SKIP_TOP = {"archive", "node_modules", "graphify-out", "dist", "__pycache__", "venv", ".venv"}
ALIAS_ROUTES = ("/", "/index.html")       # Today's other two doors; the manual names it /today
DATED = re.compile(r"\d{4}-\d{2}-\d{2}")  # a dated name is one more record of a kind its readme already describes
SOURCE_RE = re.compile(r"^(page|widget|folder|skill|doc)\s+(.+)$")
GLOSSARY_SOURCE = "glossary"              # `- for you: glossary`: the vocabulary of help.json, drawn whole
GLOSSARY_CHAPTER = "the-words-the-viewer-uses"
LINE_RE = re.compile(r"^\s*-\s*(for you|under the hood|settings)\s*:\s*(.*)$", re.I)
SECTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,159}$")
NOTE_MAX = 8000                           # a note is a note: a few paragraphs at most
OUTGROWN_GRACE = 86400                    # a file made the same day the readme was last written does not count
FIRST_START = "written on first start"    # a shipped setting whose value is this brain's own from the start: shown, never counted


# ---- small readers ----

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")


def _abs(root, rel):
    return os.path.join(root, rel.replace("/", os.sep))


def _read(ap):
    try:
        with io.open(ap, "r", encoding="utf-8-sig") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _day(ap):
    try:
        return dt.date.fromtimestamp(os.path.getmtime(ap)).isoformat()
    except OSError:
        return None


def _brain_rel(brain, ap):
    """A path as the brain names it; a file outside the brain (the code of a viewer serving another brain) by its place
    in the code folder."""
    try:
        r = os.path.relpath(ap, brain)
    except ValueError:
        r = ap
    if r.startswith(".."):
        r = "skills/brain-viewer/" + os.path.basename(ap)
    return r.replace("\\", "/")


def doc_title(text):
    """A document's title: its frontmatter title, else its first # heading."""
    if not text:
        return None
    if text.startswith("---"):
        m = re.search(r"^title:\s*(.+)$", text[:800], re.M)
        if m:
            return m.group(1).strip().strip('"\'')
    m = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    return m.group(1).strip() if m else None


def doc_section(text, heading):
    """The body under the first heading that starts with `heading` (any level, case ignored), up to the next heading of
    the same level or higher. Fenced code is skipped. None when no heading matches."""
    if not text or not heading:
        return None
    want = heading.strip().lower()
    lines = text.replace("\r\n", "\n").split("\n")
    start = level = None
    fence = False
    for i, l in enumerate(lines):
        if l.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", l)
        if not m:
            continue
        if start is None:
            if m.group(2).lower().startswith(want):
                start, level = i, len(m.group(1))
        elif len(m.group(1)) <= level:
            return "\n".join(lines[start + 1:i]).strip()
    return "\n".join(lines[start + 1:]).strip() if start is not None else None


def pages_from_serve(code=HERE):
    """serve.py's PAGES, read from its source: the dict literal after `PAGES = `. Importing serve would build a whole
    server's state; the route table is the one fact the lint and the librarian need from it."""
    src = _read(os.path.join(code, "serve.py")) or ""
    m = re.search(r"^PAGES = \{", src, re.M)
    if not m:
        return {}
    i, depth = m.end() - 1, 0
    for j in range(i, len(src)):
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return ast.literal_eval(src[i:j + 1])
                except (ValueError, SyntaxError):
                    return {}
    return {}


def redirects_from_serve(code=HERE):
    """serve.py's REDIRECT_ROUTES: the old routes that answer with a redirect, so a link to one still resolves."""
    m = re.search(r"^REDIRECT_ROUTES = (\([^)]*\))", _read(os.path.join(code, "serve.py")) or "", re.M)
    try:
        return set(ast.literal_eval(m.group(1))) if m else set()
    except (ValueError, SyntaxError):
        return set()


def page_files(pages):
    """{page file: [its routes]}: one page per file, so Today's three doors are one page."""
    out = {}
    for route, html in sorted(pages.items()):
        out.setdefault(html, []).append(route)
    return out


def canonical_route(routes, cards=None):
    """The route the manual names a page by: not one of Today's aliases, one with a card when there is one, the shortest."""
    pick = [r for r in routes if r not in ALIAS_ROUTES] or list(routes)
    if cards:
        carded = [r for r in pick if r in cards]
        pick = carded or pick
    return sorted(pick, key=lambda r: (len(r), r))[0]


def page_title(code, html):
    src = _read(os.path.join(code, html)) or ""
    m = re.search(r"<title>([^<]*)</title>", src[:4000], re.I)
    return (m.group(1).strip() if m else "") or html.rsplit(".", 1)[0]


def load_help(code=HERE):
    try:
        d = json.loads(_read(os.path.join(code, "help.json")) or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def widget_ids(folder):
    try:
        return sorted(f[:-3] for f in os.listdir(folder)
                      if f.endswith(".js") and not f.endswith(".test.js") and not f.startswith("."))
    except OSError:
        return []


def widget_title(path):
    m = re.search(r'title:\s*"([^"]*)"', (_read(path) or "")[:4000])
    return m.group(1) if m else os.path.basename(path)[:-3]


def top_folders(brain):
    out = []
    for name in sorted(os.listdir(brain)):
        ap = os.path.join(brain, name)
        if name.startswith((".", "_")) or name in SKIP_TOP or not os.path.isdir(ap):
            continue
        try:
            if os.listdir(ap):
                out.append(name)
        except OSError:
            continue
    return out


def skill_folders(brain):
    root = os.path.join(brain, "skills")
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    return [n for n in names if not n.startswith((".", "_")) and os.path.isdir(os.path.join(root, n))]


def registry_entries(brain, skills):
    """{skill: its entry in skills/skill-registry.md}: the lines under a ## or ### heading whose first word is the
    skill's folder name. A skill with no such heading has no entry."""
    text = _read(_abs(brain, REGISTRY_REL)) or ""
    out, cur, buf = {}, None, []
    for line in text.split("\n"):
        if line.startswith("#"):
            if cur and cur not in out:
                out[cur] = "\n".join(buf).strip()
            m = re.match(r"^#{2,3}\s+`?([a-z0-9][a-z0-9-]*)`?", line)
            cur, buf = (m.group(1) if m and m.group(1) in skills else None), []
            continue
        if cur is not None:
            buf.append(line)
    if cur and cur not in out:
        out[cur] = "\n".join(buf).strip()
    return out


def _born(st):
    """When a file was made: its birth time where the system keeps one (Windows, macOS), else its last change."""
    b = getattr(st, "st_birthtime", None)
    if b:
        return b
    return st.st_ctime if os.name == "nt" else st.st_mtime


_GIT_ROOTS, _FIRST_ADDED = {}, {}


def _git_root(ap):
    d = ap if os.path.isdir(ap) else os.path.dirname(ap)
    seen = []
    while d and d not in _GIT_ROOTS:
        seen.append(d)
        if os.path.exists(os.path.join(d, ".git")):
            _GIT_ROOTS[d] = d
            break
        up = os.path.dirname(d)
        if up == d:
            d = None
            break
        d = up
    root = _GIT_ROOTS.get(d) if d else None
    for x in seen:
        _GIT_ROOTS[x] = root
    return root


def _git_adds(root):
    """{repo-relative path: when git first saw it} from one `git log` over the whole history (a third of a second on
    this brain), cached until the repository's index changes."""
    gi = os.path.join(root, ".git")
    gi = os.path.join(gi, "index") if os.path.isdir(gi) else gi
    try:
        stamp = os.path.getmtime(gi)
    except OSError:
        stamp = None
    hit = _FIRST_ADDED.get(root)
    if hit and hit[0] == stamp:
        return hit[1]
    adds = {}
    try:
        import subprocess
        r = subprocess.run(["git", "-c", "core.quotepath=off", "-C", root, "log", "--diff-filter=A", "--format=%ct", "--name-only"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        when = None
        for line in (r.stdout or "").splitlines() if r.returncode == 0 else []:
            line = line.strip()
            if not line:
                continue
            if line.isdigit():
                when = float(line)
            elif when is not None:
                adds[line] = min(adds.get(line, when), when)   # newest first in the log: keep the earliest
    except Exception:          # noqa: BLE001 -- no git, no answer: birth times stand
        adds = {}
    _FIRST_ADDED[root] = (stamp, adds)
    return adds


def first_added(ap):
    """When git first saw this path (a folder: its earliest file), as a timestamp, or None when git does not know it. A
    file rewritten by an atomic replace (a ledger, the work in progress) gets a new birth time at every write, so its
    birth time says nothing about when it first appeared; git's first commit of it does."""
    root = _git_root(ap)
    if not root:
        return None
    rel = os.path.relpath(ap, root).replace("\\", "/")
    adds = _git_adds(root)
    if rel in adds:
        return adds[rel]
    if os.path.isdir(ap):
        pre = rel.rstrip("/") + "/"
        hits = [t for p, t in adds.items() if p.startswith(pre)]
        return min(hits) if hits else None
    return None


def contract_kinds(folder_ap):
    """The kinds of file a folder's .contract.json declares by pattern (`*.md`, `obs-*-....md`): a new file of a declared
    kind is one more of something the folder already holds. An exact name in `belongs` declares that one file only."""
    try:
        with io.open(os.path.join(folder_ap, ".contract.json"), "r", encoding="utf-8-sig") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return []
    return [g for g in (d.get("belongs") or []) if isinstance(g, str) and any(c in g for c in "*?[")]


def outgrown(folder_ap, readme_ap, readme_text=None):
    """The newest thing in the folder that was made after its readme last changed and that the readme does not name,
    or None. Counted: the folder's own files and subfolders. Not counted: the readme, hidden and build files, a dated
    name (a transcript, a report, a prep), which is one more record of a kind the readme already describes, and a file
    of a kind the folder's contract declares by pattern; so a folder that grows every day by its convention does not
    flag its readme, and a new kind of thing does."""
    try:
        rt = os.path.getmtime(readme_ap)
        names = os.listdir(folder_ap)
    except OSError:
        return None
    low = (readme_text if readme_text is not None else (_read(readme_ap) or "")).lower()
    kinds = contract_kinds(folder_ap)
    best = None
    for name in names:
        if (name.lower() == "readme.md" or name.startswith((".", "_")) or name in SKIP_TOP or DATED.search(name)
                or name.endswith((".pyc", ".tmp", ".log")) or any(fnmatch.fnmatch(name, g) for g in kinds)):
            continue
        try:
            born = _born(os.stat(os.path.join(folder_ap, name)))
        except OSError:
            continue
        if born <= rt + OUTGROWN_GRACE:
            continue
        stem = os.path.splitext(name)[0].lower()
        if name.lower() in low or (len(stem) > 2 and stem in low):
            continue
        first = first_added(os.path.join(folder_ap, name))
        if first is not None:
            if first <= rt + OUTGROWN_GRACE:
                continue                  # it was there before the readme last changed; only rewritten since
            born = first
        if best is None or born > best[1]:
            best = (name, born)
    if not best:
        return None
    return {"name": best[0], "added": dt.date.fromtimestamp(best[1]).isoformat()}


# ---- the chapter order ----

def read_chapter_file(brain, code=HERE):
    """(text, brain-relative path) of the chapter order: the maintainer brain's, else one shipped beside this file,
    else (None, None) and the book falls back to its default chapters."""
    for ap in (_abs(brain, CHAPTERS_REL), os.path.join(code, CHAPTERS_SHIPPED)):
        t = _read(ap)
        if t is not None:
            return t, _brain_rel(brain, ap)
    return None, None


def parse_source(s):
    if s.strip().strip("`").lower() == GLOSSARY_SOURCE:    # the vocabulary: one word, no target
        return {"kind": GLOSSARY_SOURCE, "target": GLOSSARY_SOURCE, "heading": None}
    m = SOURCE_RE.match(s.strip())
    if not m:
        return {"kind": "bad", "target": s.strip(), "heading": None}
    target, _, heading = m.group(2).strip().partition(" > ")
    return {"kind": m.group(1), "target": target.strip().strip("`"), "heading": heading.strip() or None}


def parse_chapters(text):
    """Every ### heading under '## The chapters' is a chapter: its paragraph is how it fits, then the three lines."""
    chapters, cur, in_book = [], None, False
    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if line.startswith("## "):
            in_book = line[3:].strip().lower().startswith("the chapters")
            cur = None
            continue
        if not in_book:
            continue
        if line.startswith("### "):
            title = line[4:].strip()
            cur = {"id": slug(title), "title": title, "fits": [], "forYou": [], "underHood": [], "settings": []}
            chapters.append(cur)
            continue
        if cur is None:
            continue
        m = LINE_RE.match(line)
        if m:
            key = {"for you": "forYou", "under the hood": "underHood", "settings": "settings"}[m.group(1).lower()]
            parts = [p.strip() for p in re.split(r"\s+·\s+", m.group(2)) if p.strip()]
            if key == "settings":
                cur["settings"] += [p.strip("`") for p in parts]
            else:
                cur[key] += [parse_source(p) for p in parts]
            continue
        if line.strip():
            cur["fits"].append(line.strip())
    for c in chapters:
        c["fits"] = " ".join(c["fits"])
    return chapters


def default_chapters(inv, cards, words=False):
    """The book with no chapter file (a brain the order was not shipped to): every page, every instrument, every folder,
    every module, each in a chapter of its own kind, and the vocabulary when the help file carries one. Complete, only
    not ordered by the day."""
    pages = [{"kind": "page", "target": canonical_route(r, cards), "heading": None} for _, r in sorted(inv["pages"].items())]
    vocab = [{"id": GLOSSARY_CHAPTER, "title": "The words the viewer uses", "fits": "Every word the viewer uses, by group.",
              "forYou": [{"kind": GLOSSARY_SOURCE, "target": GLOSSARY_SOURCE, "heading": None}], "underHood": [],
              "settings": []}] if words else []
    return [
        {"id": "the-pages", "title": "The pages", "fits": "Every page of the viewer, by its card.",
         "forYou": pages, "underHood": [], "settings": []},
        {"id": "the-instruments", "title": "The instruments", "fits": "Every instrument the board can carry.",
         "forYou": [{"kind": "widget", "target": w, "heading": None} for w in inv["widgets"]], "underHood": [], "settings": []},
        {"id": "the-folders", "title": "The folders", "fits": "Every folder of this brain, by its readme.",
         "forYou": [], "underHood": [{"kind": "folder", "target": f, "heading": None} for f in inv["folders"]], "settings": []},
        {"id": "the-modules", "title": "The modules", "fits": "Every skill of this brain, by its readme.",
         "forYou": [], "underHood": [{"kind": "skill", "target": s, "heading": None} for s in inv["skills"]], "settings": []},
    ] + vocab


def inventory(brain, code=HERE, pages=None):
    pages = pages if pages is not None else pages_from_serve(code)
    return {"folders": top_folders(brain), "pages": page_files(pages), "widgets": widget_ids(os.path.join(code, "widgets")),
            "skills": skill_folders(brain), "userWidgets": widget_ids(_abs(brain, USER_WIDGETS_REL))}


# ---- the sections ----

def section_id(src):
    k, t, h = src["kind"], src["target"], src.get("heading")
    if k == "page":
        base = "page-" + (slug(t) or "today")
        return base + ("-" + slug(h) if h else "")
    if k == "doc":
        return ("doc-" + slug(t) + ("-" + slug(h) if h else ""))[:160].strip("-")
    return "%s-%s" % (k, slug(t))


def _readme_label(kind, name, title):
    """What a readme is called on the page: its own title, unless that title is a path or the bare folder name, then
    the folder in words (rule 12 of the easy-to-use rules: a path is a title, a slug is a name)."""
    if title and "/" not in title and slug(title) not in ("readme", "", slug(name)):
        return title
    words = name.replace("-", " ")
    return ("The %s folder" % words) if kind == "folder" else ("The %s skill" % words)


def _doc_label(path, title):
    """A document's title as the page shows it; a title that is a path becomes the folder or the file in words, and a
    title that opens with the file's own name ("x.md -- what it is") keeps only what it is."""
    leaf0 = os.path.basename(path)
    if title and title.lower().startswith(leaf0.lower()):
        rest = re.sub(r"^[\s—–:-]+", "", title[len(leaf0):])
        if rest:
            title = rest[:1].upper() + rest[1:]
    if title and "/" not in title:
        return title
    folder, leaf = os.path.split(path.replace("\\", "/"))
    if leaf.lower() == "readme.md":
        last = folder.rstrip("/").split("/")[-1] if folder else ""
        return ("The %s folder" % last.replace("-", " ")) if last else "The brain folder"
    stem = os.path.splitext(leaf)[0].replace("-", " ")
    return stem[:1].upper() + stem[1:]


class Book:
    """One reading of the brain: the help file, the registry and the inventory read once, then each source drawn."""

    def __init__(self, brain, code=HERE, pages=None):
        self.brain, self.code = brain, code
        self.pages = pages if pages is not None else pages_from_serve(code)
        self.inv = inventory(brain, code, self.pages)
        help_doc = load_help(code)
        self.cards = help_doc.get("pages") if isinstance(help_doc.get("pages"), dict) else {}
        self.wcards = help_doc.get("widgets") if isinstance(help_doc.get("widgets"), dict) else {}
        self.glossary = help_doc.get("glossary") if isinstance(help_doc.get("glossary"), dict) else {}
        hap = os.path.join(code, "help.json")
        self.help_rel, self.help_day = _brain_rel(brain, hap), _day(hap)
        self.route_file = dict(self.pages)
        self.files = page_files(self.pages)
        self.registry = registry_entries(brain, set(self.inv["skills"]))
        reg_ap = _abs(brain, REGISTRY_REL)
        self.registry_day = _day(reg_ap)
        self._docs = {}

    def _doc(self, rel):
        if rel not in self._docs:
            ap = _abs(self.brain, rel)
            self._docs[rel] = (_read(ap), _day(ap)) if os.path.isfile(ap) else (None, None)
        return self._docs[rel]

    def sections(self, src, register):
        """Every section one source draws: the vocabulary is many (a group, its words, the keys), any other source one
        or none."""
        if src["kind"] == GLOSSARY_SOURCE:
            return self.glossary_sections()
        s = self.section(src, register)
        return [s] if s else []

    def glossary_groups(self):
        """The groups of help.json's `glossary` key that hold a word, each word with its anchor: the same groups and
        anchors serve.glossary_api() serves, read from the same file."""
        out = []
        for g in self.glossary.get("groups") or []:
            name = str((g or {}).get("name") or "").strip()
            if not name:
                continue
            terms = []
            for t in g.get("terms") or []:
                head = str((t or {}).get("term") or "").strip()
                if not head:
                    continue
                terms.append({"term": head, "anchor": slug(head),       # serve.gl_slug: the same anchor, character for character
                              "aliases": [str(a).strip() for a in t.get("aliases") or [] if str(a).strip()],
                              "definition": str(t.get("definition") or "").strip(),
                              "example": str(t.get("example") or "").strip(),
                              "analog": str(t.get("analog") or "").strip()})
            if terms:
                out.append({"name": name, "anchor": slug(name), "note": str(g.get("note") or "").strip(),
                            "pages": [str(p).strip().lower() for p in g.get("pages") or [] if str(p).strip()],
                            "terms": terms})
        return out

    def glossary_sections(self):
        """The vocabulary as the manual draws it: per group a section with its name, its note and its words as links,
        then each word as a section of its own whose id is term-<anchor>, so /manual#term-<anchor> lands on it; then the
        keys as one table. They are drawn as cards of text (kind doc with text), the style every other card of the book
        has, and carry `glossary` (group, term or keys) and their fields for a page that draws them closer. A word's
        stamp is its group's: the help file and its day, once per group rather than once per word."""
        groups = self.glossary_groups()
        anchors = {t["anchor"] for g in groups for t in g["terms"]}

        def here(text):
            # a word's own link to another word ("[manual port](#manual-port)") lands on that word's place in the book
            return re.sub(r"\]\(#([a-z0-9-]+)\)",
                          lambda m: "](/manual#term-%s)" % m.group(1) if m.group(1) in anchors else m.group(0), text or "")

        base = {"kind": "doc", "path": self.help_rel, "heading": None}
        out, seen = [], set()
        for g in groups:
            words = " · ".join("[%s](/manual#term-%s)" % (t["term"].replace("]", ""), t["anchor"]) for t in g["terms"])
            gs = dict(base, id="glossary-" + g["anchor"], glossary="group", title=g["name"], name=g["name"],
                      anchor=g["anchor"], pages=g["pages"], note=g["note"], what=g["note"] or None,
                      terms=[t["anchor"] for t in g["terms"]],
                      text="\n\n".join(x for x in (here(g["note"]), words) if x),
                      source=self.help_rel, sourceTitle="the help cards", changed=self.help_day)
            out.append(gs)
            for t in g["terms"]:
                sid = "term-" + t["anchor"]
                if sid in seen:              # two words with one anchor: the first keeps it, as the hover card finds it
                    continue
                seen.add(sid)
                body = []
                if t["aliases"]:
                    body.append("*also:* " + ", ".join(t["aliases"]))
                body.append(here(t["definition"]))
                if t["example"]:
                    body.append("*example:* " + here(t["example"]))
                if t["analog"]:
                    body.append("*septabee:* " + here(t["analog"]))
                out.append(dict(base, id=sid, glossary="term", title=t["term"], term=t["term"], anchor=t["anchor"],
                                group=g["name"], groupId=gs["id"], aliases=t["aliases"], definition=t["definition"],
                                example=t["example"] or None, analog=t["analog"] or None, what=t["definition"],
                                text="\n\n".join(b for b in body if b), source=None, changed=None))
        keys = [k for k in self.glossary.get("keys") or [] if str((k or {}).get("key") or "").strip()]
        if keys:
            cell = lambda v: re.sub(r"\s+", " ", str(v or "")).replace("|", "/").strip()
            rows = ["| Key | Pages | What it does |", "|---|---|---|"]
            for k in keys:
                rows.append("| `%s` | %s | %s |" % (cell(k.get("key")).replace("`", "'"),
                                                   cell(", ".join(str(p).strip() for p in k.get("pages") or [] if str(p).strip())),
                                                   cell(k.get("what"))))
            note = str(self.glossary.get("keys_note") or "").strip()
            out.append(dict(base, id="glossary-keys", glossary="keys", title="Keys", what=note or None,
                            keys=[{"key": str(k.get("key") or "").strip(), "what": str(k.get("what") or "").strip(),
                                   "pages": [str(p).strip() for p in k.get("pages") or [] if str(p).strip()]} for k in keys],
                            text="\n\n".join(x for x in (note, "\n".join(rows)) if x),
                            source=self.help_rel, sourceTitle="the help cards", changed=self.help_day))
        return out

    def section(self, src, register):
        """One source as the page draws it, or None when this brain does not have it (left out without a gap)."""
        k, t, h = src["kind"], src["target"], src.get("heading")
        sid = section_id(src)
        if k == "page":
            html = self.route_file.get(t)
            if not html:
                return None
            card = self.cards.get(t) or {}
            # a file that answers to more than one route (the thread page is /thread and /threads) is named by the route
            doors = [r for r in self.files.get(html, []) if r not in ALIAS_ROUTES]
            title = t.strip("/").replace("-", " ").capitalize() if len(doors) > 1 else page_title(self.code, html)
            base = {"id": sid, "kind": "page", "route": t, "href": t, "file": html, "title": title,
                    "source": self.help_rel, "sourceTitle": "the help cards", "changed": self.help_day}
            if h:
                part = next((p for p in card.get("parts") or [] if str(p.get("name", "")).lower().startswith(h.lower())), None)
                if not part:
                    return None
                base.update({"kind": "part", "name": part.get("name"), "line": part.get("line")})
                return base
            base.update({"what": card.get("what"), "workflow": card.get("workflow") or [], "parts": card.get("parts") or [],
                         "missing": not card.get("what")})
            return base
        if k == "widget":
            wap = os.path.join(self.code, "widgets", t + ".js")
            if not os.path.isfile(wap):
                return None
            card = self.wcards.get(t) or {}
            return {"id": sid, "kind": "widget", "wid": t, "title": widget_title(wap), "what": card.get("what"),
                    "missing": not card.get("what"), "source": self.help_rel, "sourceTitle": "the help cards",
                    "changed": self.help_day}
        if k in ("folder", "skill"):
            folder_rel = t if k == "folder" else "skills/" + t
            fap = _abs(self.brain, folder_rel)
            if not os.path.isdir(fap):
                return None
            rrel = folder_rel + "/readme.md"
            text, day = self._doc(rrel)
            out = {"id": sid, "kind": k, "name": t, "folder": folder_rel + "/", "path": rrel, "changed": day,
                   "missing": text is None, "title": _readme_label(k, t, doc_title(text)),
                   "sourceTitle": "its readme", "source": rrel,
                   "outgrown": outgrown(fap, _abs(self.brain, rrel), text) if text is not None else None}
            if k == "skill":
                entry = self.registry.get(t)
                out["registry"] = entry
                out["registryDay"] = self.registry_day if entry is not None else None
            return out
        if k == "doc":
            text, day = self._doc(t)
            if text is None:
                return None
            title = _doc_label(t, doc_title(text))
            out = {"id": sid, "kind": "doc", "path": t, "heading": h, "changed": day, "source": t, "sourceTitle": title,
                   "title": title}
            if h:
                body = doc_section(text, h)
                if body is None:
                    return None
                out["title"] = re.sub(r"^\d+[a-z]?\.\s+", "", h)   # "4. The vocabulary" is The vocabulary
                out["text"] = body
            else:
                out["sourceTitle"] = "its file"      # the fold is the document: its line names the file, not the title again
            return out
        return None


def build(brain, code=HERE, pages=None):
    """The whole book: the chapters with their sections, what has no chapter yet, and where the order came from."""
    b = Book(brain, code, pages)
    text, chap_rel = read_chapter_file(brain, code)
    chapters_src = parse_chapters(text) if text else default_chapters(b.inv, b.cards, bool(b.glossary_groups()))
    chapters, index, placed = [], {}, {"folder": set(), "page": set(), "widget": set(), "skill": set()}
    settings_chapter = {}
    for n, c in enumerate(chapters_src, 1):
        ch = {"id": c["id"], "n": n, "title": c["title"], "fits": c["fits"], "settings": c["settings"],
              "forYou": [], "underHood": []}
        index["chapter-" + c["id"]] = c["id"]
        for key in ("forYou", "underHood"):
            for src in c[key]:
                if src["kind"] in ("folder", "widget", "skill"):
                    placed[src["kind"]].add(src["target"])
                elif src["kind"] == "page" and src["target"] in b.route_file:
                    placed["page"].add(b.route_file[src["target"]])
                for s in b.sections(src, key):
                    if s["id"] not in index:
                        ch[key].append(s)
                        index[s["id"]] = c["id"]
        for k in c["settings"]:
            settings_chapter.setdefault(k, c["id"])
        chapters.append(ch)
    unplaced = []
    if text:
        for f in b.inv["folders"]:
            if f not in placed["folder"]:
                unplaced.append(b.section({"kind": "folder", "target": f, "heading": None}, "underHood"))
        for html, routes in sorted(b.inv["pages"].items()):
            if html not in placed["page"]:
                unplaced.append(b.section({"kind": "page", "target": canonical_route(routes, b.cards), "heading": None}, "forYou"))
        for w in b.inv["widgets"]:
            if w not in placed["widget"]:
                unplaced.append(b.section({"kind": "widget", "target": w, "heading": None}, "forYou"))
        for s in b.inv["skills"]:
            if s not in placed["skill"]:
                unplaced.append(b.section({"kind": "skill", "target": s, "heading": None}, "underHood"))
        unplaced = [u for u in unplaced if u]
        if unplaced:
            ch = {"id": "not-in-a-chapter-yet", "n": len(chapters) + 1, "title": "Not in a chapter yet",
                  "fits": "", "settings": [], "unplaced": True,
                  "forYou": [u for u in unplaced if u["kind"] in ("page", "widget")],
                  "underHood": [u for u in unplaced if u["kind"] in ("folder", "skill")]}
            for u in unplaced:
                index.setdefault(u["id"], ch["id"])
            chapters.append(ch)
    cap = _abs(brain, chap_rel) if chap_rel and not chap_rel.startswith("skills/brain-viewer/") else (
        os.path.join(code, CHAPTERS_SHIPPED) if chap_rel else None)
    return {"chapterFile": {"path": chap_rel, "changed": _day(cap) if cap else None,
                            "title": doc_title(text) if text else None, "found": bool(text)},
            "chapters": chapters, "index": index, "settingsChapter": settings_chapter,
            "counts": {"chapters": len(chapters), "sections": len(index) - len(chapters), "unplaced": len(unplaced)},
            "today": dt.date.today().isoformat()}


# ---- L21: a folder, page or module with no place in the manual ----

def placement(brain, code=HERE, pages=None):
    """([(path, why)], [(path, why)]): the findings fail rounds, the warnings do not. Nothing when the brain has no
    chapter file (the page then draws its default chapters, which hold everything)."""
    text, chap_rel = read_chapter_file(brain, code)
    if not text:
        return [], []
    b = Book(brain, code, pages)
    chapters = parse_chapters(text)
    placed = {"folder": set(), "page": set(), "widget": set(), "skill": set()}
    findings, warnings = [], []
    for c in chapters:
        for src in c["forYou"] + c["underHood"]:
            k, t = src["kind"], src["target"]
            if k == "bad":
                warnings.append((chap_rel, "the chapter '%s' names '%s', which is not a source the manual reads "
                                           "(page, widget, folder, skill, doc or glossary)" % (c["title"], t)))
            elif k == GLOSSARY_SOURCE:
                if not b.glossary_groups():
                    warnings.append((chap_rel, "the chapter '%s' draws the glossary, which skills/brain-viewer/help.json "
                                               "does not carry here" % c["title"]))
            elif k == "page":
                if t in b.route_file:
                    placed["page"].add(b.route_file[t])
                else:
                    warnings.append((chap_rel, "the chapter '%s' names the page %s, which the viewer does not serve" % (c["title"], t)))
            elif k in placed:
                placed[k].add(t)
                gone = ((k == "folder" and not os.path.isdir(_abs(brain, t)))
                        or (k == "skill" and not os.path.isdir(_abs(brain, "skills/" + t)))
                        or (k == "widget" and not os.path.isfile(os.path.join(code, "widgets", t + ".js"))))
                if gone:
                    warnings.append((chap_rel, "the chapter '%s' names the %s %s, which this brain does not have" % (c["title"], k, t)))
            elif k == "doc" and not os.path.isfile(_abs(brain, t)):
                warnings.append((chap_rel, "the chapter '%s' names the document %s, which this brain does not have" % (c["title"], t)))
    where = "name it under the chapter it belongs to in %s" % chap_rel
    for f in b.inv["folders"]:
        if f not in placed["folder"]:
            findings.append((f + "/", "the folder has no chapter in the manual; " + where))
        elif not os.path.isfile(_abs(brain, f + "/readme.md")):
            findings.append((f + "/readme.md", "the folder has no readme, so its chapter in the manual draws nothing for it"))
    for html, routes in sorted(b.inv["pages"].items()):
        label = " ".join(r for r in routes if r not in ALIAS_ROUTES) or routes[0]
        if html not in placed["page"]:
            findings.append(("skills/brain-viewer/" + html, "the page %s has no chapter in the manual; %s" % (label, where)))
        if not any((b.cards.get(r) or {}).get("what") for r in routes):
            findings.append(("skills/brain-viewer/" + html, "the page %s has no help card in skills/brain-viewer/help.json "
                                                           "(the \"?\" and the manual draw nothing for it)" % label))
    for w in b.inv["widgets"]:
        rel = "skills/brain-viewer/widgets/%s.js" % w
        if w not in placed["widget"]:
            findings.append((rel, "the widget has no chapter in the manual; " + where))
        if not (b.wcards.get(w) or {}).get("what"):
            findings.append((rel, "the widget has no card under `widgets` in skills/brain-viewer/help.json"))
    for s in b.inv["skills"]:
        if s not in placed["skill"]:
            findings.append(("skills/%s/" % s, "the skill has no chapter in the manual; " + where))
        elif not os.path.isfile(_abs(brain, "skills/%s/readme.md" % s)):
            findings.append(("skills/%s/readme.md" % s, "the skill has no readme, so the manual draws nothing for it"))
    for w in b.inv["userWidgets"]:
        if not os.path.isfile(_abs(brain, "%s/%s.md" % (MODULES_REL, w))):
            warnings.append(("%s/%s.js" % (USER_WIDGETS_REL, w),
                             "a widget of your own with no readme in %s/%s.md; the manual shows it without one" % (MODULES_REL, w)))
    return findings, warnings


# ---- the keeper: the librarian's second job ----

def keeper(brain, code=HERE, pages=None):
    """The librarian's manual check: every folder the manual draws has a readme, every page and widget a help card and
    every page a workflow, every skill an entry in the skill registry, and no readme is outgrown by its folder. Each
    finding is a fact with the file it is about; check-manual.py files them as proposals."""
    b = Book(brain, code, pages)
    readmes, page_cards, widget_cards, skill_cards, grown = [], [], [], [], []
    for kind, names, prefix in (("folder", b.inv["folders"], ""), ("skill", b.inv["skills"], "skills/")):
        for n in names:
            rel = prefix + n + "/readme.md"
            ap = _abs(brain, rel)
            if not os.path.isfile(ap):
                readmes.append({"kind": kind, "name": n, "path": rel})
                continue
            g = outgrown(_abs(brain, prefix + n), ap)
            if g:
                grown.append({"kind": kind, "name": n, "path": rel, "changed": _day(ap), "newer": g["name"], "added": g["added"]})
    for html, routes in sorted(b.inv["pages"].items()):
        r = canonical_route(routes, b.cards)
        card = next((b.cards[x] for x in [r] + routes if (b.cards.get(x) or {}).get("what")), None)
        if not card:
            page_cards.append({"route": r, "file": "skills/brain-viewer/" + html, "missing": "card"})
        elif len(card.get("workflow") or []) != 3:
            page_cards.append({"route": r, "file": "skills/brain-viewer/" + html, "missing": "workflow"})
    for w in b.inv["widgets"]:
        if not (b.wcards.get(w) or {}).get("what"):
            widget_cards.append({"id": w, "file": "skills/brain-viewer/widgets/%s.js" % w, "user": False})
    for w in b.inv["userWidgets"]:
        if not os.path.isfile(_abs(brain, "%s/%s.md" % (MODULES_REL, w))):
            widget_cards.append({"id": w, "file": "%s/%s.js" % (USER_WIDGETS_REL, w), "user": True})
    for s in b.inv["skills"]:
        if s not in b.registry:
            skill_cards.append({"name": s, "path": "skills/%s/" % s})
    findings, _ = placement(brain, code, b.pages)
    return {"generatedAt": dt.datetime.now().isoformat(timespec="seconds"),
            "chapterFile": read_chapter_file(brain, code)[1],
            "checks": {"readmes": readmes, "pageCards": page_cards, "widgetCards": widget_cards,
                       "skillCards": skill_cards, "outgrown": grown,
                       "unplaced": [{"path": p, "why": w} for p, w in findings]}}


# ---- the Verifier: CLEAN or named discrepancies ----

LINK_MD_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LINK_WIKI_RE = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
LINK_SKIP_DIRS = {".git", "node_modules", "archive", ".obsidian", "__pycache__", ".claude", ".cache", "graphify-out"}
PLACEHOLDERS = ("{", "}", "<", ">", "*", "...", "\u2026", "|")
FENCE = "`" * 3


def _leaf_index(brain):
    """Every file of the brain by its leaf name, lowercased, for a bare wikilink: {leaf: [path]}."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(brain):
        dirnames[:] = [d for d in dirnames if d not in LINK_SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            out.setdefault(fn.lower(), []).append(os.path.join(dirpath, fn))
    return out


def _strip_code(text):
    """The text without its fenced and inline code: a path written as code is an example, not a link."""
    text = re.sub(re.escape(FENCE) + r"[\s\S]*?" + re.escape(FENCE), "", text or "")
    return re.sub(r"`[^`\n]*`", "", text)


def broken_links(text, base_rel, brain, routes, index):
    """The links in a text (markdown links, pictures and wikilinks) that open nothing: a route this viewer does not
    answer, or a file the brain does not have. Not counted: a web address, an anchor, a template placeholder, and a
    pointer into archive/, which lives on the external drive since 2026-08-31 and is a true statement of where a file
    went (the same exemptions as the librarian's link check, sweep-scan.py)."""
    bad = []
    body = _strip_code(text)
    for kind, rx in (("md", LINK_MD_RE), ("wiki", LINK_WIKI_RE)):
        for m in rx.finditer(body):
            raw = m.group(1).strip().strip("<>")
            t = raw.split("#")[0].split("?")[0].strip()
            if (not t or re.match(r"^[a-z][a-z0-9+.-]*:", t, re.I) or any(c in raw for c in PLACEHOLDERS)
                    or t.replace("\\", "/").lstrip("./").lower().startswith("archive/")):
                continue
            if t.startswith("/"):
                if t.rstrip("/") in routes or t in routes or t.startswith(("/api/", "/static/", "/raw/")):
                    continue
                bad.append(raw)
                continue
            t = t.replace("\\", "/")
            tries = [os.path.normpath(os.path.join(brain, base_rel, t)), os.path.normpath(os.path.join(brain, t))]
            tries += [x + ".md" for x in tries if not x.lower().endswith(".md")]
            if any(os.path.exists(x) for x in tries):
                continue
            if kind == "wiki" and "/" not in t:
                leaf = t.lower() if t.lower().endswith(".md") else t.lower() + ".md"
                if index.get(leaf) or index.get(t.lower()):
                    continue
            bad.append(raw)
    return sorted(set(bad))


def _user_layer_discrepancies(brain, known):
    out = []
    add = lambda path, what: out.append({"check": "your layer", "path": path, "what": what})
    sap = _abs(brain, USER_SETTINGS_REL)
    if os.path.isfile(sap):
        try:
            d = json.loads(_read(sap) or "")
            if not isinstance(d, dict):
                add(USER_SETTINGS_REL, "the settings file is not a JSON object")
        except ValueError as e:
            add(USER_SETTINGS_REL, "the settings file does not read as JSON (%s)" % str(e)[:80])
    for sub, ext, check in ((USER_LAYOUTS_REL, ".json", "layout"), (USER_LOOKS_REL, ".css", "look"),
                            (USER_WIDGETS_REL, ".js", "widget"), (NOTES_REL, ".md", "note"), (MODULES_REL, ".md", "module")):
        d = _abs(brain, sub)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not f.endswith(ext) or (check == "widget" and f.endswith(".test.js")) or f == "readme.md":
                continue
            rel, ap = sub + "/" + f, os.path.join(d, f)
            text = _read(ap)
            if text is None:
                add(rel, "the file does not read as text")
                continue
            if check == "layout":
                try:
                    if not isinstance(json.loads(text), dict):
                        add(rel, "the board layout is not a JSON object")
                except ValueError as e:
                    add(rel, "the board layout does not read as JSON (%s)" % str(e)[:80])
            elif check == "look" and (len(text.encode("utf-8")) > 24000 or ":root" not in text):
                add(rel, "a look is one :root block of at most 24,000 bytes (the plugin contract)")
            elif check == "widget" and ("BV.widgets.register(" not in text or "contract:" not in text):
                add(rel, "a widget makes one BV.widgets.register({...}) call that declares its contract number")
            elif check == "note" and f[:-3] not in known:
                add(rel, "a note on a section the manual no longer has; move it to the section it is about")
            elif check == "module" and not os.path.isfile(_abs(brain, "%s/%s.js" % (USER_WIDGETS_REL, f[:-3]))):
                add(rel, "the readme of a widget that is not in your widgets folder")
    return out


def verify(brain, code=HERE, pages=None):
    """The Verifier. -> (discrepancies, warnings): each {check, path, what}, named and placed so a person or brain-lint
    can act on it; a warning names what is worth a look and fails nothing. The checks, in order:
      chapter     every top-level folder, page, widget and skill has a chapter in the chapter order
      readme      every folder and skill the manual draws has its readme
      card        every page has its help card with a three-step workflow; every widget its card; every skill its entry
                  in the skill registry; every widget the person wrote its readme in viewer/manual/modules/
      outgrown    no readme is older than a newer file in its folder that it does not name (dated records and the
                  kinds a folder's contract declares by pattern do not count; git's first commit dates a rewritten file)
      links       every link the manual draws resolves: in a chapter's paragraph, a card, the vocabulary, a section of a
                  document, a registry entry and a readme under the hood
      your layer  the person's settings, board, looks, widgets, notes and readmes read as what they claim to be"""
    pages = pages if pages is not None else pages_from_serve(code)
    out = []
    add = lambda check, path, what: out.append({"check": check, "path": path, "what": what})
    found, warnings = placement(brain, code, pages)
    for path, why in found:
        check = "readme" if path.endswith("readme.md") else ("card" if ("help card" in why or "card under" in why) else "chapter")
        add(check, path, why)
    k = keeper(brain, code, pages)["checks"]
    have = {d["path"] for d in out}
    for r in k["readmes"]:
        if r["path"] not in have:
            add("readme", r["path"], "the %s has no readme, so the manual draws nothing for it"
                % ("skill" if r["kind"] == "skill" else "folder"))
    for pc in k["pageCards"]:
        if pc["missing"] == "workflow":
            add("card", pc["file"], "the page %s has its card but not its typical workflow in three steps" % pc["route"])
    for w in k["widgetCards"]:
        if w["user"]:
            add("card", w["file"], "a widget of your own with no readme in %s/%s.md" % (MODULES_REL, w["id"]))
    sc = k["skillCards"]
    if sc:
        add("card", REGISTRY_REL, "%d skill%s with no entry in the skill registry, so the manual has no card for %s: %s"
            % (len(sc), "" if len(sc) == 1 else "s", "it" if len(sc) == 1 else "them", ", ".join(x["name"] for x in sc)))
    for g in k["outgrown"]:
        add("outgrown", g["path"], "last changed %s, before %s was added to its folder (%s), and it does not name it"
            % (g["changed"], g["newer"], g["added"]))
    # links: what the manual draws, file by file
    book = build(brain, code, pages)
    b = Book(brain, code, pages)
    routes = set(pages) | redirects_from_serve(code)
    index = _leaf_index(brain)
    texts = {}
    cf_text, cf_rel = read_chapter_file(brain, code)
    if cf_text:
        texts[(cf_rel, "")] = "\n".join(c["fits"] for c in book["chapters"])
    for ch in book["chapters"]:
        for sec in ch["forYou"] + ch["underHood"]:
            if sec.get("glossary"):           # the vocabulary is help.json's text: checked with the cards' text
                key = (b.help_rel, "")
                texts[key] = texts.get(key, "") + "\n" + (sec.get("text") or "")
            elif sec["kind"] in ("page", "part", "widget"):
                bits = [sec.get("what") or "", sec.get("line") or ""] + list(sec.get("workflow") or [])
                bits += [pt.get("line", "") for pt in sec.get("parts") or []]
                key = (b.help_rel, "")
                texts[key] = texts.get(key, "") + "\n" + "\n".join(bits)
            elif sec["kind"] == "doc" and sec.get("text") is not None:
                texts[(sec["path"], os.path.dirname(sec["path"]))] = sec["text"]
            elif sec.get("path") and not sec.get("missing"):
                body = _read(_abs(brain, sec["path"]))
                if body is not None:
                    texts[(sec["path"], os.path.dirname(sec["path"]))] = body
            if sec["kind"] == "skill" and sec.get("registry"):
                key = (REGISTRY_REL, "skills")
                texts[key] = texts.get(key, "") + "\n" + sec["registry"]
    for (rel, base), text in sorted(texts.items()):
        bad = broken_links(text, base, brain, routes, index)
        if bad:
            add("links", rel, "%d link%s that open%s nothing: %s" % (
                len(bad), "" if len(bad) == 1 else "s", "s" if len(bad) == 1 else "",
                ", ".join(bad[:8]) + (" ..." if len(bad) > 8 else "")))
    out += _user_layer_discrepancies(brain, set(book["index"]))
    return out, [{"check": "chapter", "path": pth, "what": w} for pth, w in warnings if not pth.startswith(USER_WIDGETS_REL)]


# ---- the person's own layer ----

def _json(ap):
    try:
        d = json.loads(_read(ap) or "")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def _empty(v):
    return v is None or v == "" or v == [] or v == {}


def user_layer(brain, book, shipped=None, home_default=(), member="me"):
    """What is the person's own, read as it stands and set beside what the viewer ships, chapter by chapter:
    notes on a section (viewer/manual/notes/), the settings that differ from the shipped ones (viewer/settings.json),
    their board (viewer/layouts/<member>.json) against the board a new brain gets, the looks and widgets they wrote,
    and the readmes of their modules (viewer/manual/modules/). Read only."""
    shipped = shipped or {}
    index, by_setting = book.get("index") or {}, book.get("settingsChapter") or {}
    titles = {}
    for ch in book.get("chapters") or []:
        titles["chapter-" + ch["id"]] = ch["title"]
        for s in ch["forYou"] + ch["underHood"]:
            titles[s["id"]] = s.get("title") or s.get("name")
    own = "your-own-layer" if any(c["id"] == "your-own-layer" for c in book.get("chapters") or []) else None
    notes = []
    nd = _abs(brain, NOTES_REL)
    for f in sorted(os.listdir(nd)) if os.path.isdir(nd) else []:
        if not f.endswith(".md"):
            continue
        sid, ap = f[:-3], os.path.join(nd, f)
        notes.append({"section": sid, "chapter": index.get(sid), "title": titles.get(sid), "path": NOTES_REL + "/" + f,
                      "changed": _day(ap), "text": (_read(ap) or "").strip()})
    settings = []
    cur = _json(_abs(brain, USER_SETTINGS_REL))
    explain = cur.get("_keys") if isinstance(cur.get("_keys"), dict) else {}
    for k, v in cur.items():
        if k.startswith("_"):
            continue
        base = shipped.get(k, None)
        if base == FIRST_START:
            continue
        changed = (not _empty(v)) if k not in shipped else (v != base)
        if changed:
            settings.append({"key": k, "value": v, "shipped": base if k in shipped else None, "explain": explain.get(k),
                             "chapter": by_setting.get(k, own)})
    board = None
    lap = _abs(brain, "%s/%s.json" % (USER_LAYOUTS_REL, member))
    if os.path.isfile(lap):
        lay = _json(lap)
        on = [w.get("id") for w in lay.get("widgets") or [] if isinstance(w, dict) and w.get("on")]
        board = {"path": "%s/%s.json" % (USER_LAYOUTS_REL, member), "changed": _day(lap),
                 "added": [w for w in on if w not in home_default], "removed": [w for w in home_default if w not in on],
                 "look": lay.get("look"), "chapter": "the-board"}
    looks = [{"name": f[:-4], "path": "%s/%s" % (USER_LOOKS_REL, f), "changed": _day(_abs(brain, USER_LOOKS_REL + "/" + f)),
              "chapter": "the-board"}
             for f in (sorted(os.listdir(_abs(brain, USER_LOOKS_REL))) if os.path.isdir(_abs(brain, USER_LOOKS_REL)) else [])
             if f.endswith(".css")]
    widgets = []
    for w in widget_ids(_abs(brain, USER_WIDGETS_REL)):
        wap = _abs(brain, "%s/%s.js" % (USER_WIDGETS_REL, w))
        rap = _abs(brain, "%s/%s.md" % (MODULES_REL, w))
        widgets.append({"id": w, "title": widget_title(wap), "path": "%s/%s.js" % (USER_WIDGETS_REL, w), "changed": _day(wap),
                        "readme": ("%s/%s.md" % (MODULES_REL, w)) if os.path.isfile(rap) else None,
                        "readmeText": (_read(rap) or "").strip() if os.path.isfile(rap) else None, "chapter": own})
    modules = []
    md = _abs(brain, MODULES_REL)
    for f in sorted(os.listdir(md)) if os.path.isdir(md) else []:
        if f.endswith(".md") and f[:-3] not in {w["id"] for w in widgets}:
            modules.append({"name": f[:-3], "path": MODULES_REL + "/" + f, "changed": _day(os.path.join(md, f)),
                            "text": (_read(os.path.join(md, f)) or "").strip(), "chapter": own})
    count = len(notes) + len(settings) + len(looks) + len(widgets) + len(modules) + (
        1 if board and (board["added"] or board["removed"] or board["look"]) else 0)
    return {"notes": notes, "settings": settings, "board": board, "looks": looks, "widgets": widgets, "modules": modules,
            "count": count, "folder": USER_MANUAL_REL + "/"}


def write_note(brain, section, text, known):
    """viewer/manual/notes/<section>.md: kept, replaced or (empty text) taken away. -> (code, body). Only a section the
    book has right now, so nothing a page sends can name another file."""
    section = str(section or "").strip()
    if not SECTION_ID_RE.match(section) or section not in known:
        return 400, {"error": "not a section of the manual: %r" % section[:80]}
    if not isinstance(text, str):
        return 400, {"error": "send the note as text"}
    text = text.replace("\r\n", "\n").strip()
    if len(text) > NOTE_MAX:
        return 400, {"error": "a note holds at most %d characters" % NOTE_MAX}
    return _write_user(brain, "%s/%s.md" % (NOTES_REL, section), text)


def write_module_readme(brain, wid, text):
    """viewer/manual/modules/<id>.md: the readme of a widget the person wrote, which must exist in viewer/widgets/."""
    wid = str(wid or "").strip()
    if not re.match(r"^[a-z0-9][a-z0-9-]{0,63}$", wid) or not os.path.isfile(_abs(brain, "%s/%s.js" % (USER_WIDGETS_REL, wid))):
        return 400, {"error": "not a widget of your own: %r" % wid[:64]}
    if not isinstance(text, str):
        return 400, {"error": "send the readme as text"}
    text = text.replace("\r\n", "\n").strip()
    if len(text) > NOTE_MAX * 2:
        return 400, {"error": "a readme here holds at most %d characters" % (NOTE_MAX * 2)}
    return _write_user(brain, "%s/%s.md" % (MODULES_REL, wid), text)


def _write_user(brain, rel, text):
    ap = _abs(brain, rel)
    if not text:
        if os.path.isfile(ap):
            os.remove(ap)
            return 200, {"ok": True, "path": rel, "state": "removed"}
        return 200, {"ok": True, "path": rel, "state": "none"}
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    existed = os.path.isfile(ap)
    tmp = ap + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    os.replace(tmp, ap)
    return 200, {"ok": True, "path": rel, "state": "replaced" if existed else "kept", "changed": _day(ap)}


# ---- run alone ----

def _brain_root():
    env = os.environ.get("BRAIN_ROOT")
    return os.path.abspath(env) if env else os.path.dirname(os.path.dirname(HERE))


def main(argv):
    brain = _brain_root()
    if "--gaps" in argv:
        findings, warnings = placement(brain)
        for p, w in findings:
            print("%s -- %s" % (p, w))
        for p, w in warnings:
            print("WARN %s -- %s" % (p, w))
        print("manual: %d with no place, %d warning(s)" % (len(findings), len(warnings)))
        return 1 if findings else 0
    if "--verify" in argv:
        found, warnings = verify(brain)
        for d in found:
            print("%-10s %s -- %s" % (d["check"], d["path"], d["what"]))
        for w in warnings:
            print("WARN %-5s %s -- %s" % (w["check"], w["path"], w["what"]))
        print("CLEAN" if not found else "%d discrepanc%s" % (len(found), "y" if len(found) == 1 else "ies"))
        return 1 if found else 0
    if "--keeper" in argv:
        print(json.dumps(keeper(brain), ensure_ascii=False, indent=2))
        return 0
    book = build(brain)
    print("chapter order: %s" % (book["chapterFile"]["path"] or "none (the default chapters)"))
    for ch in book["chapters"]:
        print("%2d %s" % (ch["n"], ch["title"]))
        for s in ch["forYou"]:
            print("     for you: %s%s" % (s.get("title"), "  (no card)" if s.get("missing") else ""))
        for s in ch["underHood"]:
            print("     under the hood: %s%s%s" % (s.get("title"), "  (no readme)" if s.get("missing") else "",
                                                   "  (outgrown by %s)" % s["outgrown"]["name"] if s.get("outgrown") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
