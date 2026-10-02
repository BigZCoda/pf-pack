#!/usr/bin/env python3
"""status.py -- one read of a brain's state: pack versions, extras, local changes, features, activity.

  python skills/brain-status/status.py                    check this brain, write context/brain-status.json, log one line
  python skills/brain-status/status.py --json             also print the JSON
  python skills/brain-status/status.py --offline          skip the network (use the cached manifest if any)
  python skills/brain-status/status.py --manifest <path-or-url>   read this manifest instead of the update skill's MANIFEST_URL
  python skills/brain-status/status.py --brain <folder> [--out <file>]   check ANOTHER brain read-only: nothing is written
                                                                         into it (no JSON, no cache, no log line); the
                                                                         JSON goes to --out if given, else nowhere

On a Mac, python3. Standard library only, Python 3.10+. It never reads a token file's contents (presence only), never
sends a request to the viewer (a 1-second socket connect on 127.0.0.1:8765 only), and its only network call is one GET
of the pf-pack manifest. Exit 0 unless the brain folder does not exist (1).
"""
import argparse
import datetime as dt
import fnmatch
import glob
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BRAIN = os.path.dirname(os.path.dirname(HERE))
VERSION = "0.1.0"
GENERATOR = "skills/brain-status/status.py " + VERSION
CACHE_REL = "context/.pack-manifest-cache.json"
TOKEN_FILE = "PF App API.txt"                                   # the ferryman's TOKEN_PATH (pull.py, push.py)
KEY_PATTERNS = ["*API*.txt", "*token*.txt", "*_key.txt"]        # the shell .gitignore's patterns for key files
VIEWER_PORT = 8765
NOISE_DIRS = {"__pycache__", "node_modules", ".git"}
LOG_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] \[([^\]]+)\] ([A-Z]+)\b(.*)$")


def rd(path, limit=None):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read(limit) if limit else f.read()
    except Exception:
        return None


def rjson(path):
    t = rd(path)
    if t is None:
        return None
    try:
        return json.loads(t)
    except Exception:
        return None


def vkey(v):
    """Same comparison as skills/update/install-component.py: numeric parts, a -suffix (1.2.1-mentee) ignored."""
    out = []
    for part in str(v or "0").split("-")[0].split("."):
        out.append(int(part) if part.isdigit() else 0)
    return tuple(out)


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def frontmatter_version(path):
    t = rd(path, 4000)
    if not t or not t.startswith("---"):
        return None
    end = t.find("\n---", 3)
    head = t[3:end if end > 0 else len(t)]
    m = re.search(r"^version:\s*['\"]?([^'\"\s]+)", head, re.M)
    return m.group(1) if m else None


def registry_versions(brain):
    t = rd(os.path.join(brain, "skills", "skill-registry.md")) or ""
    out, cur = {}, None
    for line in t.splitlines():
        m = re.match(r"^###\s+(\S+)", line)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r"^- \*\*Version:\*\*\s*([^\s*]+)", line)
        if m and cur:
            out[cur] = m.group(1)
    return out


def skill_version(brain, name, spec_rel=None):
    """(version, where it came from). component.json wins for a folder component; then the spec file's frontmatter
    (the update skill's authority); then any .md in the folder with frontmatter; last, the registry line."""
    folder = os.path.join(brain, "skills", name)
    cj = rjson(os.path.join(folder, "component.json"))
    if isinstance(cj, dict) and cj.get("version"):
        return str(cj["version"]), "component.json"
    cands = []
    if spec_rel and spec_rel.endswith(".md"):
        cands.append(os.path.join(brain, spec_rel.replace("/", os.sep)))
    cands.append(os.path.join(folder, name + "-skill.md"))
    cands += sorted(glob.glob(os.path.join(folder, "*.md")))
    for c in cands:
        if os.path.isfile(c):
            v = frontmatter_version(c)
            if v:
                return v, "frontmatter:" + os.path.relpath(c, brain).replace(os.sep, "/")
    reg = registry_versions(brain).get(name)
    if reg:
        return reg, "skill-registry.md"
    return None, None


def manifest_url(brain):
    t = rd(os.path.join(brain, "skills", "update", "update-skill.md")) or ""
    m = re.search(r"MANIFEST_URL:\s*(https?://[^\s`)]+)", t)
    return m.group(1) if m else None


def load_manifest(brain, override, offline, write_cache):
    """(manifest or None, source). Order: --manifest path or URL, else the update skill's MANIFEST_URL; on a network
    failure (or --offline) the last cached copy; else unavailable."""
    cache = os.path.join(brain, CACHE_REL.replace("/", os.sep))
    src = override or manifest_url(brain)
    if src and not re.match(r"https?://", src):
        m = rjson(os.path.abspath(src))
        if isinstance(m, dict):
            return m, "file:" + os.path.abspath(src).replace(os.sep, "/")
    elif src and not offline:
        try:
            req = urllib.request.Request(src, headers={"User-Agent": "pf-brain-status/" + VERSION})
            with urllib.request.urlopen(req, timeout=10) as r:
                m = json.loads(r.read().decode("utf-8"))
            if isinstance(m, dict):
                if write_cache:
                    try:
                        os.makedirs(os.path.dirname(cache), exist_ok=True)
                        with open(cache, "w", encoding="utf-8", newline="\n") as f:
                            json.dump({"_fetchedAt": now_iso(), "_url": src, "manifest": m}, f, indent=1)
                    except Exception:
                        pass
                return m, "network:" + src
        except Exception:
            pass
    c = rjson(cache)
    if isinstance(c, dict) and isinstance(c.get("manifest"), dict):
        return c["manifest"], "cache:%s (fetched %s)" % (CACHE_REL, c.get("_fetchedAt", "?"))
    return None, "unavailable"


def sha_matches(path, want):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return None
    if hashlib.sha256(data).hexdigest() == want:
        return True
    lf = data.replace(b"\r\n", b"\n")              # a Windows checkout may hold CRLF where the release has LF
    return b"\0" not in data and hashlib.sha256(lf).hexdigest() == want


def folder_files(root):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in NOISE_DIRS]
        for fn in fns:
            if not fn.endswith(".pyc"):
                out.append(os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, "/"))
    return sorted(out)


# ---------------------------------------------------------------- components, extras, customizations

def check_components(brain, manifest):
    components, extras, customizations = [], [], []
    entries = {s.get("skill"): s for s in (manifest or {}).get("skills", []) if isinstance(s, dict) and s.get("skill")}
    skills_dir = os.path.join(brain, "skills")
    local = sorted(d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d))
                   and d not in NOISE_DIRS and not d.startswith(".")) if os.path.isdir(skills_dir) else []

    if manifest is None:
        # no manifest: every versioned local skill is still listed, with nothing to compare against
        for name in local:
            have, how = skill_version(brain, name)
            if have:
                components.append({"name": name, "present": True, "installed": have, "installedFrom": how,
                                   "manifest": None, "updateAvailable": None,
                                   "kind": "folder" if how == "component.json" else "skill"})
        return components, extras, customizations

    for name, e in entries.items():
        root_rel = str(e.get("installRoot") or ("skills/" + name)).strip("/")
        root = os.path.join(brain, root_rel.replace("/", os.sep))
        present = os.path.isdir(root)
        have, how = skill_version(brain, name, e.get("specPath")) if present else (None, None)
        want = e.get("version")
        upd = (vkey(have) < vkey(want)) if (present and have and want) else None
        row = {"name": name, "present": present, "installed": have, "installedFrom": how, "manifest": want,
               "updateAvailable": upd, "kind": "folder" if e.get("update") == "replace-folder" else "skill"}
        if present and have and want and vkey(have) > vkey(want):
            row["note"] = "local newer than the manifest (a fork, or the maintainer copy)"
        if not present:
            row["note"] = "available, not installed"
        components.append(row)

        if present and e.get("update") == "replace-folder":
            listed = {}
            for f in e.get("files") or []:
                d = str(f.get("dest", "")).replace("\\", "/")
                if d.startswith(root_rel + "/"):
                    listed[d[len(root_rel) + 1:]] = f.get("sha256")
            added = [root_rel + "/" + p for p in folder_files(root) if p not in listed]
            changed, missing = [], []
            for p, want_sha in sorted(listed.items()):
                ap = os.path.join(root, p.replace("/", os.sep))
                if not os.path.isfile(ap):
                    missing.append(root_rel + "/" + p)
                elif want_sha and sha_matches(ap, want_sha) is False:
                    changed.append(root_rel + "/" + p)
            customizations.append({"component": name, "added": added, "changed": changed, "missing": missing})

    for name in local:
        if name not in entries:
            have, how = skill_version(brain, name)
            extras.append({"name": name, "version": have, "versionFrom": how})
    return components, extras, customizations


# ---------------------------------------------------------------- features

def find_ledgers(brain):
    """Ledgers the holon registry names, plus any *-tasks.md in the shape skills/brain-tasks writes."""
    found = set()
    reg = rjson(os.path.join(brain, "context", "holon-registry.json"))
    if isinstance(reg, dict):
        hs = reg.get("holons")
        items = hs if isinstance(hs, list) else (list(hs.values()) if isinstance(hs, dict) else [])
        for h in items:
            t = h.get("tasks") if isinstance(h, dict) else None
            if isinstance(t, str) and os.path.isfile(os.path.join(brain, t.replace("/", os.sep))):
                found.add(t.replace("\\", "/"))
    skip = {"archive", "skills", "node_modules", "transcripts", "deliverables"}
    for dp, dns, fns in os.walk(brain):
        dns[:] = [d for d in dns if d not in skip and not d.startswith(".")]
        for fn in fns:
            if fn.endswith("-tasks.md"):
                ap = os.path.join(dp, fn)
                head = rd(ap, 1500) or ""
                if "project ledger" in head.lower() or re.search(r"^- \[.\] [TQ]-\d{4}", head, re.M):
                    found.add(os.path.relpath(ap, brain).replace(os.sep, "/"))
    return sorted(found)


def viewer_answers():
    try:
        with socket.create_connection(("127.0.0.1", VIEWER_PORT), timeout=1):
            return True
    except Exception:
        return False


def read_log_rows(brain, since):
    """The live context/log.md plus any rotated months (archive/ledgers/YYYY-MM/) the window reaches, oldest first."""
    paths, d, today = [], since.replace(day=1), dt.date.today()
    while d <= today:
        p = os.path.join(brain, "archive", "ledgers", d.strftime("%Y-%m"), "log-%s.md" % d.strftime("%Y-%m"))
        if os.path.isfile(p):
            paths.append(p)
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    paths.append(os.path.join(brain, "context", "log.md"))
    rows, seen = [], set()
    for p in paths:
        for line in (rd(p) or "").splitlines():
            m = LOG_RE.match(line)
            if m and line not in seen:
                seen.add(line)
                rows.append({"date": m.group(1), "time": m.group(2), "agent": m.group(3),
                             "action": m.group(4), "text": m.group(5).lstrip(" -").strip(), "line": line})
    return rows


def last_match(rows, pred):
    for r in reversed(rows):
        if pred(r):
            return {"at": "%s %s" % (r["date"], r["time"]), "line": r["line"][:300]}
    return None


def check_features(brain, rows):
    f = {}
    keys = []
    try:
        for fn in os.listdir(brain):
            if os.path.isfile(os.path.join(brain, fn)) and (fn == TOKEN_FILE or any(fnmatch.fnmatch(fn, p) for p in KEY_PATTERNS)):
                keys.append(fn)
    except Exception:
        pass
    # presence only: the files are never opened
    f["tokenFile"] = {"present": TOKEN_FILE in keys, "name": TOKEN_FILE, "otherKeyFiles": len([k for k in keys if k != TOKEN_FILE])}
    lg = find_ledgers(brain)
    f["ledgers"] = {"count": len(lg), "paths": lg}
    f["registry"] = os.path.isfile(os.path.join(brain, "context", "holon-registry.json"))
    surveys = sorted(os.path.basename(p) for p in glob.glob(os.path.join(brain, "inbox", "survey-*.md")))
    f["survey"] = {"done": bool(surveys), "files": surveys}
    f["hooks"] = os.path.isfile(os.path.join(brain, ".claude", "settings.json"))
    vc = rjson(os.path.join(brain, "skills", "brain-viewer", "component.json"))
    f["viewer"] = {"installed": os.path.isdir(os.path.join(brain, "skills", "brain-viewer")),
                   "version": vc.get("version") if isinstance(vc, dict) else None,
                   "answersOn8765": viewer_answers()}
    setup = rd(os.path.join(brain, "SETUP.md"), 3000)
    f["setupComplete"] = None if setup is None else ("SETUP COMPLETE" in setup)
    f["lastPull"] = last_match(rows, lambda r: r["agent"] == "ferryman" and r["action"] == "PULL")
    f["lastPush"] = last_match(rows, lambda r: r["agent"] == "ferryman" and r["action"] == "SYNCED"
                               and ("-> pf app" in r["text"].lower() or "push" in r["text"].lower()))
    f["lastGitPush"] = last_match(rows, lambda r: r["action"] == "SYNCED" and "push" in r["text"].lower()
                                  and ("git" in r["text"].lower()))
    inbox = os.path.join(brain, "inbox")
    names = sorted(n for n in os.listdir(inbox) if n.lower() != "readme.md" and not n.startswith(".")) \
        if os.path.isdir(inbox) else []
    f["inbox"] = {"count": len(names), "files": names}
    return f


def check_activity(rows):
    today = dt.date.today()

    def within(n):
        lim = (today - dt.timedelta(days=n)).isoformat()
        return sum(1 for r in rows if r["date"] > lim)
    agents = []
    for r in reversed(rows):
        if r["agent"] not in agents:
            agents.append(r["agent"])
        if len(agents) == 3:
            break
    return {"linesLast7Days": within(7), "linesLast30Days": within(30),
            "lastLogDate": rows[-1]["date"] if rows else None, "lastAgents": agents}


def owner_of(brain):
    """The shell CLAUDE.md's Inhabitant line; a brain without that line (Zak's) falls back to viewer/settings.json."""
    t = rd(os.path.join(brain, "CLAUDE.md"), 3000) or ""
    m = re.search(r"\*\*Inhabitant:\*\*\s*([^|\n]+)", t)
    if m:
        v = m.group(1).strip()
        return v if v and "{{" not in v else "uninhabited"
    s = rjson(os.path.join(brain, "viewer", "settings.json"))
    if isinstance(s, dict) and s.get("owner") and s.get("owner") != "@me":
        return str(s["owner"])
    return "uninhabited"


# ---------------------------------------------------------------- run

def build(brain, manifest_arg, offline, write_cache):
    manifest, msrc = load_manifest(brain, manifest_arg, offline, write_cache)
    comps, extras, custom = check_components(brain, manifest)
    rows = read_log_rows(brain, dt.date.today() - dt.timedelta(days=31))
    return {
        "_generatedAt": now_iso(),
        "_generatedBy": GENERATOR,
        "brain": os.path.basename(os.path.normpath(brain)),
        "owner": owner_of(brain),
        "maintainerCopy": os.path.isfile(os.path.join(brain, "skills", "brain-viewer", "release.py")),
        "manifestSource": msrc,
        "manifestUpdatedAt": (manifest or {}).get("updatedAt"),
        "components": comps,
        "extras": extras,
        "customizations": custom,
        "features": check_features(brain, rows),
        "activity": check_activity(rows),
    }


def summary(s):
    out = ["brain-status: %s (owner %s), manifest %s" % (s["brain"], s["owner"], s["manifestSource"])]
    if s["maintainerCopy"]:
        out.append("  maintainer copy: components here are released FROM this brain, so local-newer is expected")
    behind = [c for c in s["components"] if c["updateAvailable"]]
    if s["manifestUpdatedAt"] is None:
        out.append("  behind: unknown (no manifest); %d versioned skills listed" % len(s["components"]))
    else:
        out.append("  behind: " + (", ".join("%s %s -> %s" % (c["name"], c["installed"], c["manifest"]) for c in behind) or "none"))
        absent = [c["name"] for c in s["components"] if not c["present"]]
        if absent:
            out.append("  available, not installed: " + ", ".join(absent))
    ex = s["extras"]
    names = ["%s %s" % (e["name"], e["version"]) if e["version"] else e["name"] for e in ex]
    out.append("  extras (%d): %s" % (len(ex), (", ".join(names[:10]) + (" ..." if len(names) > 10 else "")) or "none"))
    add = sum(len(c["added"]) for c in s["customizations"])
    chg = sum(len(c["changed"]) for c in s["customizations"])
    out.append("  customizations: %d added, %d changed across %d folder components" % (add, chg, len(s["customizations"])))
    f = s["features"]
    flags = [("token", f["tokenFile"]["present"]), ("ledgers (%d)" % f["ledgers"]["count"], f["ledgers"]["count"] > 0),
             ("registry", f["registry"]), ("survey", f["survey"]["done"]), ("hooks", f["hooks"]),
             ("viewer %s" % (f["viewer"]["version"] or ""), f["viewer"]["installed"]),
             ("viewer running", f["viewer"]["answersOn8765"]), ("setup", f["setupComplete"])]
    out.append("  on: " + (", ".join(n.strip() for n, v in flags if v) or "nothing"))
    out.append("  off: " + (", ".join(n.strip() for n, v in flags if v is False) or "nothing")
               + (" (setup: no SETUP.md)" if f["setupComplete"] is None else ""))
    out.append("  last pull %s, last push %s" % ((f["lastPull"] or {}).get("at", "never"), (f["lastPush"] or {}).get("at", "never")))
    a = s["activity"]
    out.append("  inbox %d; log lines 7d %d / 30d %d, last %s by %s" % (
        f["inbox"]["count"], a["linesLast7Days"], a["linesLast30Days"], a["lastLogDate"] or "never",
        ", ".join(a["lastAgents"]) or "nobody"))
    return "\n".join(out)


def log_line(brain, s):
    tool = os.path.join(brain, "skills", "brain-log", "log.py")
    if not os.path.isfile(tool):
        return "no skills/brain-log/log.py in this brain; no log line written"
    behind = sum(1 for c in s["components"] if c["updateAvailable"])
    cust = sum(len(c["changed"]) + len(c["added"]) for c in s["customizations"])
    text = ("context/brain-status.json -- %d components (%d behind), %d extras, %d customized files, manifest %s"
            % (len(s["components"]), behind, len(s["extras"]), cust, s["manifestSource"].split(":")[0]))
    r = subprocess.run([sys.executable, tool, "--append", "--agent", "brain-status", "--action", "LINTED", "--text", text],
                       capture_output=True, text=True, env=dict(os.environ, BRAIN_ROOT=brain), cwd=brain)
    return None if r.returncode == 0 else "log line refused: " + (r.stderr or r.stdout).strip()[:200]


def main(argv=None):
    ap = argparse.ArgumentParser(description="check a brain's pack versions, extras, local changes, features and activity")
    ap.add_argument("--json", action="store_true", help="print the JSON too")
    ap.add_argument("--brain", help="check another brain read-only (nothing is written into it)")
    ap.add_argument("--manifest", help="a manifest path or URL instead of the update skill's MANIFEST_URL")
    ap.add_argument("--offline", action="store_true", help="no network; use the cached manifest if any")
    ap.add_argument("--out", help="where to write the JSON (default: this brain's context/brain-status.json; "
                                   "with --brain, nowhere unless given)")
    a = ap.parse_args(argv)
    other = bool(a.brain)
    brain = os.path.abspath(a.brain.strip().strip('"')) if other else DEFAULT_BRAIN
    if not os.path.isdir(brain):
        print("no brain folder at %s" % brain)
        return 1
    s = build(brain, a.manifest, a.offline, write_cache=not other)
    out = a.out or (None if other else os.path.join(brain, "context", "brain-status.json"))
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(s, f, indent=1, ensure_ascii=False)
            f.write("\n")
    if a.json:
        print(json.dumps(s, indent=1, ensure_ascii=False))
    print(summary(s))
    if not other:
        err = log_line(brain, s)
        if err:
            print("  " + err)
    print("  wrote %s" % out if out else "  read-only run: nothing written")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
