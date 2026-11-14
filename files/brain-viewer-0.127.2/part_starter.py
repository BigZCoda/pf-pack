"""part_starter.py -- the Starter brain page (viewer 0.122.0): what a brain assembled for a new person contains, read
live from the files each time the page asks, and how its pieces work together.

  python skills/brain-viewer/part_starter.py --json      what GET /api/starter answers, as JSON
  python skills/brain-viewer/part_starter.py             the same, as a short summary for the terminal

Why (the owner, 2026-11-12): "I want to know why she doesn't have the start session ... I just want to know what the
starting brains have, I would like there to be a constantly updated (as in proper files are linked so it is living)
viewer page for me to look at what a starter brain contains so I just know. I would love to know how it all operates
together as well."

Nothing here is a copy. Each read goes to the source:
  - where the shell and the kit live, and which folders the assembler skips: read from the assembler itself
    (skills/assemble-brain/assemble-brain.py), so a moved shell moves the page
  - the shell: its folders, each folder's readme line, its version (SHELL.md)
  - the kit: pf-pack-manifest.json, every component with its version, what it does and the files it installs; how far
    the kit on this PC is ahead of GitHub, from git's own refs (no network call)
  - what stays out: the owner's slash commands (~/.claude/commands), the brain's hooks (.claude/settings.local.json),
    and every skill folder in this brain that the kit does not ship, found by comparing folders
  - how it works together: skills/assemble-brain/starter-brain-flow.json, written by hand, and every file a step names
    is checked against the shell and the kit on each read, so a step whose file is gone is marked, never silently wrong
The page shows a file's words through GET /api/starter/file, which reads only paths this scan listed, under the
shell, the kit, the commands and hooks folders or the brain, and never a key file. It writes nothing.
On a computer with no kit (a mentee's, a team copy) the answer is {"available": false} and the menu draws no entry.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAIN = HERE.parent.parent
ASSEMBLER = BRAIN / "skills" / "assemble-brain" / "assemble-brain.py"
FLOW = BRAIN / "skills" / "assemble-brain" / "starter-brain-flow.json"
HOME = Path.home()
COMMANDS = HOME / ".claude" / "commands"
HOOKS = HOME / ".claude" / "hooks"
SETTINGS = BRAIN / ".claude" / "settings.local.json"
TEXT_EXT = {".md", ".py", ".json", ".txt", ".js", ".html", ".css", ".sh", ".command", ".canvas", ".yml", ".yaml", ".toml", ""}
FILE_CAP = 400_000
# key files never read, whatever folder they sit in (the same names the viewer's never-read list and the assembler guard)
NEVER = {"apizzle.txt", "pf app api.txt", "onboarding api.txt", "pfk_key.txt", "deepseek_key.txt", "claude setuptoken.txt",
         "hf_key.txt", "tally_key.txt", "typeform_key.txt", "openai_key.txt", "gemini_key.txt", "fal_key.txt", ".env"}


def _assembler_paths():
    """SHELL, PACK_LOCAL and SKIP_DIRS as the assembler itself declares them."""
    shell, pack, skip = None, None, {".git", ".obsidian", ".claude", "__pycache__"}
    try:
        src = ASSEMBLER.read_text(encoding="utf-8")
    except OSError:
        return shell, pack, skip
    m = re.search(r'^SHELL\s*=\s*Path\(r?"([^"]+)"\)', src, re.M)
    if m:
        shell = Path(m.group(1))
    m = re.search(r'^PACK_LOCAL\s*=\s*Path\(r?"([^"]+)"\)', src, re.M)
    if m:
        pack = Path(m.group(1))
    m = re.search(r"^SKIP_DIRS\s*=\s*\{([^}]*)\}", src, re.M)
    if m:
        skip = set(re.findall(r'"([^"]+)"', m.group(1)))
    return shell, pack, skip


def _assembler_steps():
    """The numbered steps in the assembler's own docstring ('  1. Preflight: ...'), joined across wrapped lines."""
    try:
        src = ASSEMBLER.read_text(encoding="utf-8")
    except OSError:
        return []
    doc = src.split('"""')[1] if src.count('"""') >= 2 else ""
    steps, cur = [], None
    for line in doc.splitlines():
        m = re.match(r"\s{2}(\d+)\.\s+(.*)", line)
        if m:
            cur = m.group(2).strip()
            steps.append(cur)
        elif cur is not None and line.startswith("     ") and line.strip():
            steps[-1] = steps[-1] + " " + line.strip()
        elif not line.strip():
            cur = None
    return steps


def _first_line(p, skip_title=True):
    """The first line of a readme or skill file that says something: past frontmatter, titles, status and blank lines."""
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            lines = f.read(6000).splitlines()
    except OSError:
        return ""
    i = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    for line in lines[i:]:
        s = line.strip()
        if not s or (skip_title and s.startswith("#")) or s.startswith("<!--") or s.startswith("---"):
            continue
        s = re.sub(r"^[>*\-\s]+", "", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        if s.lower().startswith(("status:", "last updated", "**status")):
            continue
        return s[:260]
    return ""


def _frontmatter(p):
    try:
        txt = Path(p).read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return {}
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    out = {}
    for line in txt[3:end].splitlines():
        m = re.match(r"([A-Za-z_-]+):\s*(.*)", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def _git(pack, *args):
    try:
        r = subprocess.run(["git", "-C", str(pack)] + list(args), capture_output=True, text=True, timeout=8,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _shell(shell, skip):
    if not shell or not shell.is_dir():
        return {"found": False, "path": str(shell) if shell else None}
    version = ""
    m = re.search(r"\*\*Version:\*\*\s*([^\s|]+(?:\s*\([^)]*\))?)", (shell / "SHELL.md").read_text(encoding="utf-8", errors="replace")[:3000]) if (shell / "SHELL.md").is_file() else None
    if m:
        version = m.group(1)
    files, folders = [], []
    for e in sorted(shell.iterdir(), key=lambda x: (x.is_dir(), x.name.lower())):
        if e.name in skip or e.name.startswith("."):
            continue
        if e.is_file():
            files.append({"name": e.name, "path": e.name, "line": _first_line(e) if e.suffix.lower() == ".md" else ""})
        elif e.is_dir():
            readme = next((e / n for n in ("readme.md", "README.md") if (e / n).is_file()), None)
            count, inner = 0, []
            for root, dirs, fs in os.walk(e):
                dirs[:] = [d for d in dirs if d not in skip]
                count += len(fs)
                rel = Path(root).relative_to(shell).as_posix()
                for f in sorted(fs):
                    if len(inner) < 40:
                        inner.append(rel + "/" + f)
            folders.append({"name": e.name, "path": (readme.relative_to(shell).as_posix() if readme else None),
                            "line": _first_line(readme) if readme else "", "files": count, "inner": inner})
    return {"found": True, "path": str(shell), "version": version, "files": files, "folders": folders}


def _kit(pack, brain_skills):
    mf = (pack / "pf-pack-manifest.json") if pack else None
    if not mf or not mf.is_file():
        return {"found": False, "path": str(pack) if pack else None}
    m = json.loads(mf.read_text(encoding="utf-8"))
    comps = []
    for s in m.get("skills") or []:
        name = s.get("skill")
        pc = None
        cj = BRAIN / "skills" / name / "component.json"
        if cj.is_file():
            try:
                pc = json.loads(cj.read_text(encoding="utf-8")).get("version")
            except (OSError, ValueError):
                pc = None
        files = [{"src": f.get("src"), "dest": f.get("dest")} for f in s.get("files") or []]
        comps.append({"name": name, "version": s.get("version"), "pcVersion": pc, "blurb": s.get("blurb") or "",
                      "spec": s.get("specPath"), "start": s.get("start"), "requires": s.get("requires"),
                      "fileCount": len(files), "files": files})
    sh = m.get("shell") or {}
    ahead = _git(pack, "rev-list", "--count", "origin/main..HEAD")
    pending = _git(pack, "log", "--format=%h %s", "origin/main..HEAD")
    pushed_at = _git(pack, "log", "-1", "--format=%cI", "origin/main")
    return {"found": True, "path": str(pack), "updatedAt": m.get("updatedAt"),
            "shellVersion": sh.get("version"), "components": comps,
            "github": {"ahead": int(ahead) if ahead and ahead.isdigit() else None,
                       "pending": [ln for ln in (pending or "").splitlines() if ln],
                       "lastPushedCommitAt": pushed_at, "repo": "BigZCoda/pf-pack"}}


def _commands():
    out = []
    if COMMANDS.is_dir():
        for p in sorted(COMMANDS.glob("*.md")):
            fm = _frontmatter(p)
            out.append({"name": "/" + p.stem, "path": p.name, "line": fm.get("description") or _first_line(p)})
    return out


def _hooks():
    out = []
    try:
        cfg = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    for event, groups in (cfg.get("hooks") or {}).items():
        for g in groups or []:
            for h in g.get("hooks") or []:
                cmd = h.get("command") or ""
                m = re.search(r"\.claude/hooks/([\w.\-]+)", cmd.replace("\\", "/"))
                out.append({"event": event, "matcher": g.get("matcher") or "", "command": cmd[:240],
                            "script": m.group(1) if m and (HOOKS / m.group(1)).is_file() else None})
    return out


def _skills_not_shipped(kit_names):
    out = []
    root = BRAIN / "skills"
    for d in sorted(root.iterdir(), key=lambda x: x.name.lower()):
        if not d.is_dir() or d.name.startswith((".", "_")) or d.name in kit_names:
            continue
        doc = next((d / n for n in ("readme.md", "README.md", d.name + "-skill.md", "SKILL.md") if (d / n).is_file()), None)
        if doc is None:
            doc = next(iter(sorted(d.glob("*-skill.md"))), None)
        out.append({"name": d.name, "path": ("skills/%s/%s" % (d.name, doc.name)) if doc else None,
                    "line": _first_line(doc) if doc else ""})
    return out


def _locate(p, shell, skip, dests):
    """Where one path of the flow file lives: in the kit (by its installed place), in the shell (unless under a folder
    the assembler skips, which never reaches a new brain), or, with 'brain:', in the owner's own brain."""
    p = p.strip().replace("\\", "/")
    if p.startswith("brain:"):
        rel = p[len("brain:"):]
        return {"path": rel, "where": "brain", "src": rel, "ok": (BRAIN / rel).exists()}
    if p in dests:
        return {"path": p, "where": "kit", "src": dests[p], "ok": True}
    first = p.split("/", 1)[0]
    if shell and first not in skip and (shell / p).exists():
        return {"path": p, "where": "shell", "src": p, "ok": True}
    return {"path": p, "where": None, "src": None, "ok": False}


def _flow(shell, skip, kit):
    try:
        f = json.loads(FLOW.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"found": False, "error": str(e), "path": "skills/assemble-brain/starter-brain-flow.json"}
    dests = {}
    if kit.get("found"):
        for c in kit["components"]:
            for fl in c["files"]:
                if fl.get("dest"):
                    dests[fl["dest"]] = fl.get("src")
    steps = []
    for st in f.get("steps") or []:
        files = [_locate(p, shell, skip, dests) for p in st.get("files") or []]
        steps.append({"title": st.get("title", ""), "when": st.get("when", ""), "what": st.get("what", ""),
                      "owner": st.get("owner", ""), "files": files, "missing": sum(1 for x in files if not x["ok"])})
    gaps = []
    ahead = ((kit.get("github") or {}).get("ahead")) if kit.get("found") else None
    for g in f.get("gaps") or []:
        if g.get("kitAhead"):
            closed = ahead == 0
            detail = ("the kit on this PC is %s release commit%s ahead of GitHub" % (ahead, "" if ahead == 1 else "s")
                      if ahead else "the kit on this PC matches GitHub" if ahead == 0 else "git could not say")
            gaps.append({"title": g.get("title", ""), "what": g.get("what", ""), "closed": closed, "detail": detail, "needs": []})
            continue
        needs = [_locate(p, shell, skip, dests) for p in g.get("needs") or []]
        closed = bool(needs) and all(n["ok"] for n in needs)
        gaps.append({"title": g.get("title", ""), "what": g.get("what", ""), "closed": closed,
                     "checked": bool(needs), "needs": needs})
    return {"found": True, "path": "skills/assemble-brain/starter-brain-flow.json", "intro": f.get("intro", ""),
            "updated": f.get("updated", ""), "steps": steps, "missing": sum(s["missing"] for s in steps),
            "gaps": gaps, "open": sum(1 for g in gaps if not g["closed"])}


def available():
    _, pack, _ = _assembler_paths()
    return bool(pack and (pack / "pf-pack-manifest.json").is_file())


def starter():
    """What GET /api/starter answers."""
    shell, pack, skip = _assembler_paths()
    if not (pack and (pack / "pf-pack-manifest.json").is_file()):
        return {"available": False, "why": "This computer has no kit to build brains from, so there is no starter brain to show."}
    kit = _kit(pack, None)
    kit_names = {c["name"] for c in kit.get("components", [])}
    sh = _shell(shell, skip)
    cmds = _commands()
    why = ("A starter brain is the shell folder plus the kit's components, put together by the assembler. Your slash "
           "commands live in your own user folder (%s), outside both, and the assembler skips every .claude folder, "
           "so no starter brain has ever had /start-session or any of the other %d." % (COMMANDS, max(len(cmds) - 1, 0)))
    return {"available": True, "why": why,
            "assembler": {"path": "skills/assemble-brain/assemble-brain.py", "steps": _assembler_steps(),
                          "skips": sorted(skip), "command": "python skills/assemble-brain/assemble-brain.py --name <first-name>"},
            "shell": sh, "kit": kit,
            "notShipped": {"commands": cmds, "commandsPath": str(COMMANDS), "hooks": _hooks(),
                           "skills": _skills_not_shipped(kit_names)},
            "flow": _flow(shell, skip, kit)}


def read_file(root, rel):
    """GET /api/starter/file?root=&path=: (code, body). Only a text file under one of the scan's roots, never a key file."""
    shell, pack, skip = _assembler_paths()
    roots = {"shell": shell, "kit": pack, "commands": COMMANDS, "hooks": HOOKS, "brain": BRAIN}
    base = roots.get(root or "")
    if base is None or not rel:
        return 400, {"error": "root must be one of shell, kit, commands, hooks, brain, with a path"}
    rel = rel.replace("\\", "/").lstrip("/")
    try:
        p = (base / rel).resolve()
        p.relative_to(base.resolve())
    except (ValueError, OSError):
        return 403, {"error": "that path is outside its folder"}
    parts = set(Path(rel).parts)
    low = p.name.lower()
    if low in NEVER or low.endswith(("_key.txt", "token.txt")) or parts & {".git"} or (root == "brain" and parts & {".obsidian"}):
        return 403, {"error": "that file is never shown"}
    if not p.is_file():
        return 404, {"error": "no such file", "path": rel}
    if p.suffix.lower() not in TEXT_EXT:
        return 415, {"error": "not a text file", "path": rel}
    data = p.read_bytes()[:FILE_CAP]
    return 200, {"root": root, "path": rel, "text": data.decode("utf-8", errors="replace"),
                 "truncated": p.stat().st_size > FILE_CAP, "bytes": p.stat().st_size}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    d = starter()
    if "--json" in sys.argv:
        print(json.dumps(d, indent=1, ensure_ascii=False))
    elif not d.get("available"):
        print(d.get("why"))
    else:
        k = d["kit"]
        print(d["why"])
        print("shell %s: %d files, %d folders" % (d["shell"].get("version"), len(d["shell"].get("files", [])), len(d["shell"].get("folders", []))))
        print("kit %s: %s" % (k.get("updatedAt"), ", ".join("%s %s" % (c["name"], c["version"]) for c in k.get("components", []))))
        print("kit ahead of GitHub: %s" % (k.get("github") or {}).get("ahead"))
        ns = d["notShipped"]
        print("not shipped: %d commands, %d hooks, %d skills" % (len(ns["commands"]), len(ns["hooks"]), len(ns["skills"])))
        fl = d["flow"]
        print("flow: %s" % ("%d steps, %d files missing" % (len(fl["steps"]), fl["missing"]) if fl.get("found") else "no flow file (%s)" % fl.get("error")))
