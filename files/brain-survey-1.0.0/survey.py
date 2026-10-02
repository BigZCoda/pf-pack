#!/usr/bin/env python3
"""
survey.py -- inventory a person's existing files before a brain ingests any of them.

  python skills/brain-survey/survey.py <folder> [<folder> ...] [--out DIR] [--top N]

Walks each folder and records, from file names, sizes and dates only:
  - every file type: count, total size, oldest and newest modified date
  - the folders holding the most files
  - code repositories (a folder with a .git inside), counted but never read
  - exports recognized by their layout: Slack, Notion, Google Takeout / Drive, email, Obsidian vaults
Then writes two files into --out (default: inbox/ of the brain this script sits in):
  survey-inventory-<date>.json   the numbers
  survey-<date>.md               one question per thing the inventory raises, and a proposed ingest order

The brain this script sits in is never surveyed, even when it sits inside a given folder.
It NEVER opens a file. It calls stat and lists directory names, nothing else, so it cannot
quote, copy or leak any file's contents. Stdlib only; runs on Windows and macOS.
"""
import argparse, json, os, re, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BRAIN = Path(__file__).resolve().parents[2]

# Folders never walked: tooling caches and system folders, not anyone's work.
SKIP_NAMES = {"node_modules", "__pycache__", ".venv", "venv", ".cache", ".npm", ".gradle",
              "$RECYCLE.BIN", "System Volume Information", ".Trash", ".Trashes", "AppData",
              "Library", ".idea", ".vscode", "dist", "build", ".next", "site-packages"}

# Extension -> kind. The kind decides the ingest route.
KINDS = {
    "notes": {".md", ".txt", ".rtf", ".org"},
    "documents": {".docx", ".doc", ".odt", ".pages", ".gdoc"},
    "pdfs": {".pdf"},
    "spreadsheets": {".xlsx", ".xls", ".csv", ".tsv", ".numbers", ".ods", ".gsheet"},
    "slides": {".pptx", ".ppt", ".key", ".odp", ".gslides"},
    "transcripts": {".vtt", ".srt", ".sbv"},
    "contacts": {".vcf"},
    "email": {".eml", ".mbox", ".pst", ".msg", ".ost"},
    "data": {".json", ".xml", ".yaml", ".yml", ".sqlite", ".db"},
    "code": {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".java", ".go", ".rb", ".php",
             ".c", ".cpp", ".cs", ".sh", ".ps1", ".sql", ".ipynb", ".swift", ".kt", ".rs"},
    "images": {".png", ".jpg", ".jpeg", ".gif", ".heic", ".webp", ".svg", ".psd", ".ai", ".tif", ".tiff", ".bmp", ".raw"},
    "video": {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"},
    "audio": {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz"},
    "installers": {".exe", ".msi", ".dmg", ".pkg", ".iso", ".app", ".apk"},
}
EXT_KIND = {e: k for k, exts in KINDS.items() for e in exts}
# A file NAME (never its contents) can move a note or document into a better kind.
NAME_HINTS = [(re.compile(r"transcript|meeting notes|notes by gemini|otter|fireflies", re.I), "transcripts"),
              (re.compile(r"contacts?\b", re.I), "contacts")]
HINTABLE = {"notes", "documents", "pdfs", "data", "spreadsheets"}

# What the brain does with each kind, in the order it happens. Skipped kinds come last.
ROUTE = {
    "transcripts": "the transcript processor writes a summary, the action items and the people named, one file per call",
    "notes": "copied into the project folder of the area they belong to",
    "documents": "copied into the project folder they belong to, with a short summary",
    "contacts": "people cards for the people you actually work with, chosen by you, never bulk-created",
    "email": "only the threads you name, filed as notes of the project they concern",
    "spreadsheets": "a pointer and a one-line description; copied only when a project needs the numbers",
    "slides": "a pointer and a one-line description in the project folder",
    "pdfs": "copied when it is your own work or a reference a project uses; otherwise a pointer",
    "data": "a pointer only, unless a project names the file",
    "code": "loose code files outside a repository: a pointer from the project they belong to",
    "images": "skipped; brand or design assets get a pointer from the project that uses them",
    "video": "skipped; call recordings are transcribed first, then handled as transcripts",
    "audio": "skipped; call recordings are transcribed first, then handled as transcripts",
    "archives": "skipped until unzipped; an export inside one is surveyed again after unzipping",
    "installers": "skipped",
    "other": "skipped unless you name a use",
}
ORDER = ["transcripts", "notes", "documents", "contacts", "email", "spreadsheets", "slides", "pdfs",
         "data", "code", "images", "video", "audio", "archives", "installers", "other"]
SKIP_KINDS = {"images", "video", "audio", "archives", "installers", "other"}

NOTION_RE = re.compile(r" [0-9a-f]{32}(\.(md|html|csv))?$")


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def day(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else None


def detect_export(path, names, dirs):
    """Recognize an export from the names in one folder. Returns a label or None. Reads nothing."""
    low = {n.lower() for n in names}
    if {"channels.json", "users.json"} <= low:
        return "Slack export"
    if path.name.lower() == "takeout" or "archive_browser.html" in low:
        return "Google Takeout export"
    if ".obsidian" in dirs:
        return "Obsidian vault"
    if sum(1 for n in names if NOTION_RE.search(n)) >= 3 or re.match(r"^Export-[0-9a-f-]{8,}", path.name):
        return "Notion export"
    if any(n.endswith((".mbox", ".pst", ".ost")) for n in low) or sum(1 for n in low if n.endswith(".eml")) >= 20:
        return "email export"
    return None


def walk_count(root):
    """Files under a repository or export, .git and tooling folders excluded. Counted, never opened."""
    n, newest = 0, 0.0
    for dp, dn, fn in os.walk(root, onerror=lambda e: None):
        dn[:] = [d for d in dn if d != ".git" and d not in SKIP_NAMES]
        for f in fn:
            try:
                st = os.stat(os.path.join(dp, f))
            except OSError:
                continue
            n += 1
            newest = max(newest, st.st_mtime)
    return n, newest


def survey(roots, top):
    ext = defaultdict(lambda: {"count": 0, "bytes": 0, "oldest": None, "newest": None, "kind": "other"})
    folder_count = defaultdict(int)      # recursive file count per folder, up to 3 levels under a root
    folder_newest = defaultdict(float)
    repos, exports, skipped, unreadable, total = [], [], defaultdict(int), 0, 0
    resolved = []
    for root in roots:
        root = Path(root).expanduser().resolve()
        if not root.is_dir():
            print(f"[skip] not a folder: {root}", file=sys.stderr)
            continue
        resolved.append(str(root))
        for dp, dn, fn in os.walk(root, onerror=lambda e: None):
            p = Path(dp)
            if p == BRAIN or BRAIN in p.parents:
                dn[:] = []          # the brain itself is never surveyed
                continue
            if ".git" in dn:
                n, newest = walk_count(p)
                repos.append({"path": str(p), "files": n, "newest": day(newest)})
                dn[:] = []
                continue
            label = detect_export(p, fn + dn, set(dn))
            if label:
                n, newest = walk_count(p)
                exports.append({"path": str(p), "kind": label, "files": n, "newest": day(newest)})
                dn[:] = []
                continue
            kept = []
            for d in dn:
                if d in SKIP_NAMES or d.startswith("."):
                    skipped[d] += 1
                else:
                    kept.append(d)
            dn[:] = kept
            parts = p.relative_to(root).parts
            chain = [root.joinpath(*parts[:i]) for i in range(1, min(len(parts), 3) + 1)]
            for f in fn:
                try:
                    st = os.stat(os.path.join(dp, f))
                except OSError:
                    unreadable += 1
                    continue
                total += 1
                e = Path(f).suffix.lower() or "(none)"
                kind = EXT_KIND.get(e, "other")
                for rx, k in NAME_HINTS:
                    if kind in HINTABLE and rx.search(f):
                        kind, e = k, f"{e} ({k} by name)"
                        break
                r = ext[e]
                r["kind"] = kind
                r["count"] += 1
                r["bytes"] += st.st_size
                r["oldest"] = st.st_mtime if r["oldest"] is None else min(r["oldest"], st.st_mtime)
                r["newest"] = st.st_mtime if r["newest"] is None else max(r["newest"], st.st_mtime)
                for c in chain:
                    folder_count[str(c)] += 1
                    folder_newest[str(c)] = max(folder_newest[str(c)], st.st_mtime)

    types = sorted(({"ext": k, **v, "oldest": day(v["oldest"]), "newest": day(v["newest"])} for k, v in ext.items()),
                   key=lambda r: -r["count"])
    kinds = {}
    for t in types:
        k = kinds.setdefault(t["kind"], {"count": 0, "bytes": 0, "oldest": None, "newest": None, "exts": []})
        k["count"] += t["count"]
        k["bytes"] += t["bytes"]
        k["exts"].append(t["ext"])
        k["oldest"] = t["oldest"] if k["oldest"] is None else min(k["oldest"], t["oldest"])
        k["newest"] = t["newest"] if k["newest"] is None else max(k["newest"], t["newest"])
    folders = sorted(({"path": p, "files": n, "newest": day(folder_newest[p])} for p, n in folder_count.items()),
                     key=lambda r: -r["files"])
    picked = []
    for f in folders:
        if len(picked) >= top:
            break
        # a folder whose only content is one subfolder adds nothing: keep the deeper one
        if any(Path(f["path"]) in Path(q["path"]).parents and q["files"] == f["files"] for q in folders[:top * 2]):
            continue
        picked.append(f)
    return {
        "surveyedAt": datetime.now().isoformat(timespec="seconds"),
        "roots": resolved,
        "totalFiles": total,
        "unreadable": unreadable,
        "kinds": {k: kinds[k] for k in ORDER if k in kinds},
        "types": types,
        "topFolders": picked,
        "repositories": repos,
        "exports": exports,
        "skippedFolders": dict(skipped),
        "filesOpened": 0,
    }


def files(n):
    return f"{n} file" if n == 1 else f"{n} files"


def short(path, roots):
    """A path shown from the surveyed folder's name down, so questions stay readable."""
    for r in roots:
        rp = Path(r)
        try:
            rel = Path(path).relative_to(rp)
        except ValueError:
            continue
        return str(Path(rp.name) / rel) if str(rel) != "." else rp.name
    return path


TYPE_DEFAULT = {"transcripts": "all of them",
                "contacts": "none until you name the people",
                "email": "none until you name the threads"}


def survey_md(inv, today):
    R = inv["roots"]
    L = [f"# Survey of existing files ({today})", "",
         f"Folders surveyed: {', '.join(R)}. {files(inv['totalFiles'])} counted"
         + (f", {inv['unreadable']} could not be listed" if inv["unreadable"] else "")
         + ". No file was opened; everything below comes from names, sizes and dates.", "",
         "Answer each question on its Answer line, or tell Claude the answers and it writes them in. "
         "The ingest step reads this file and does nothing the answers do not allow.", "",
         "## What is there", "",
         "| kind | files | size | oldest | newest | extensions |", "|---|---|---|---|---|---|"]
    for k, v in inv["kinds"].items():
        L.append(f"| {k} | {v['count']} | {human(v['bytes'])} | {v['oldest']} | {v['newest']} | {', '.join(v['exts'][:8])} |")
    L += ["", "## Questions", ""]
    q = 0

    def ask(text, default):
        nonlocal q
        q += 1
        L.extend([f"{q}. {text}", f"   - Default if left blank: {default}", "   - Answer:", ""])

    if inv["topFolders"]:
        L += ["### Folders: live or finished", "",
              "A live folder is work still going on and gets a project folder in the brain. A finished one gets a pointer only.", ""]
        for f in inv["topFolders"]:
            ask(f"{short(f['path'], R)} ({files(f['files'])}, newest {f['newest']}): live, finished, or not yours?",
                "live if the newest file is under 90 days old, finished otherwise")
    if inv["repositories"]:
        L += ["### Code repositories: point or copy", "",
              "A pointer is one line in the brain saying where the repository is and what it is for; the code stays where it is.", ""]
        for r in inv["repositories"]:
            ask(f"Repository {short(r['path'], R)} ({files(r['files'])}, newest {r['newest']}): what is it for, and is it still in use?",
                "a pointer, with the one-line description you give")
    if inv["exports"]:
        L += ["### Exports: which first", ""]
        for x in inv["exports"]:
            ask(f"{x['kind']} at {short(x['path'], R)} ({files(x['files'])}, newest {x['newest']}): ingest, point at, or skip? "
                "If ingest, which part (channels, pages, labels)?",
                "a pointer only; nothing from it is ingested until you name a part")
    L += ["### Types", ""]
    for k in ("transcripts", "contacts", "email"):
        if k in inv["kinds"]:
            ask(f"{k.capitalize()}: {files(inv['kinds'][k]['count'])}. For these, {ROUTE[k]}. Which of them are yours to ingest?",
                TYPE_DEFAULT[k])
    skip = [k for k in inv["kinds"] if k in SKIP_KINDS]
    if skip:
        ask("These kinds are skipped: " + ", ".join(f"{k} ({inv['kinds'][k]['count']})" for k in skip)
            + ". Is any of them work the brain should know about (a folder of brand assets, call recordings)?",
            "all skipped")
    ask("Is there anything the brain must never read, whatever folder it sits in?",
        "nothing excluded beyond the skipped kinds")
    L += ["## Proposed ingest order", "", "One kind at a time, in this order, each checked before the next starts.", ""]
    n = 0
    for k in ORDER:
        if k in inv["kinds"] and k not in SKIP_KINDS:
            n += 1
            L.append(f"{n}. **{k}** ({files(inv['kinds'][k]['count'])}): {ROUTE[k]}.")
    if inv["repositories"]:
        n += 1
        L.append(f"{n}. **repositories** ({len(inv['repositories'])}): one pointer each, in the project it belongs to.")
    if inv["exports"]:
        n += 1
        L.append(f"{n}. **exports** ({len(inv['exports'])}): only the parts named in the answers above.")
    L += ["", f"Skipped: {', '.join(skip) if skip else 'nothing'}.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Inventory existing files by type and count; opens nothing.")
    ap.add_argument("roots", nargs="+", help="folders to survey")
    ap.add_argument("--out", default=str(BRAIN / "inbox"), help="where the two survey files go (default: this brain's inbox/)")
    ap.add_argument("--top", type=int, default=15, help="how many of the biggest folders to ask about")
    a = ap.parse_args()
    inv = survey(a.roots, a.top)
    if not inv["roots"]:
        print("[fail] none of the given paths is a folder", file=sys.stderr)
        sys.exit(1)
    today = datetime.now().strftime("%Y-%m-%d")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"survey-inventory-{today}.json"
    mp = out / f"survey-{today}.md"
    jp.write_text(json.dumps(inv, indent=2), encoding="utf-8")
    mp.write_text(survey_md(inv, today), encoding="utf-8")
    q = mp.read_text(encoding="utf-8").count("   - Answer:")
    print(f"[ok] {inv['totalFiles']} files in {len(inv['kinds'])} kinds, {len(inv['repositories'])} repositories, "
          f"{len(inv['exports'])} exports, {q} questions; 0 files opened")
    print(f"     {mp}")
    print(f"     {jp}")


if __name__ == "__main__":
    main()
