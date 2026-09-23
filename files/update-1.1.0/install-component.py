#!/usr/bin/env python3
"""install-component.py -- install or update ONE folder component from the pf-pack manifest, replacing it whole.

  python skills/update/install-component.py brain-viewer            install, or update to the manifest's version
  python skills/update/install-component.py brain-viewer --check    say what is installed and what is published, change nothing
  python skills/update/install-component.py brain-viewer --dry-run  list what would be written, change nothing
  add --pack <folder> to read a local pf-pack checkout instead of GitHub, --brain <folder> to act on another brain

WHICH COMPONENTS. Only a manifest entry carrying `"update": "replace-folder"` and an `installRoot` (the Brain Viewer is
the first). Every other pack skill is still updated the way skills/update/update-skill.md says: by a prompt the agent
applies with judgment. A folder component is different on purpose: it is an application, the same for everyone, and
what a person makes lives OUTSIDE it (the viewer's user layer is viewer/), so replacing the folder loses nothing.

WHAT ONE RUN DOES
  1. Reads the manifest and the installed version (<installRoot>/component.json; none means not installed).
  2. Downloads every file the entry lists into a staging folder beside the install, checking each sha256 the entry gives.
  3. Copies the entry's `keepBeforeReplace` files out of the OLD folder into the user layer, only where the destination
     does not exist yet (a person's settings, layouts and looks from before the user layer existed).
  4. Swaps: the old folder is moved aside, the staged one takes its place, the old one is deleted. On any failure the
     old folder is put back and nothing else has changed.
  5. Appends one line to context/log.md (through skills/brain-log/log.py when this brain has it).

It never writes outside <installRoot>, the user layer named by the entry, and that one log line. It refuses to replace
a maintainer copy (a folder carrying release.py) unless --force is given. Exit 0 done or current, 1 failed, 2 refused.
"""
import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

PACK_RAW = "https://raw.githubusercontent.com/BigZCoda/pf-pack/main/"
HERE = os.path.dirname(os.path.abspath(__file__))


def brain_root(explicit):
    raw = (explicit or os.environ.get("BRAIN_ROOT") or "").strip().strip('"')
    return os.path.abspath(raw) if raw else os.path.dirname(os.path.dirname(HERE))


def fetch(src, pack):
    if pack:
        with open(os.path.join(pack, src.replace("/", os.sep)), "rb") as f:
            return f.read()
    with urllib.request.urlopen(PACK_RAW + src, timeout=60) as r:
        return r.read()


def vkey(v):
    out = []
    for part in str(v or "0").split("-")[0].split("."):
        out.append(int(part) if part.isdigit() else 0)
    return tuple(out)


def installed_version(root):
    try:
        with open(os.path.join(root, "component.json"), "r", encoding="utf-8-sig") as f:
            return str(json.load(f).get("version") or "") or None
    except Exception:
        return None


def log(brain, text):
    tool = os.path.join(brain, "skills", "brain-log", "log.py")
    if os.path.isfile(tool):
        env = dict(os.environ, BRAIN_ROOT=brain)
        r = subprocess.run([sys.executable, tool, "--append", "--agent", "update-skill", "--action", "MODIFIED", "--text", text],
                           capture_output=True, text=True, env=env)
        if r.returncode == 0:
            return
    ap = os.path.join(brain, "context", "log.md")
    if os.path.isdir(os.path.dirname(ap)):
        with open(ap, "a", encoding="utf-8", newline="\n") as f:     # the clock is read in the same call that writes
            f.write("[%s] [update-skill] MODIFIED -- %s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), text))


def keep_before_replace(brain, old_root, rules):
    """Copy a person's files out of the old folder into the user layer. `to` may carry one `*`, filled with what the
    glob's `*` matched. Never overwrites; returns the brain-relative paths it wrote."""
    wrote = []
    if not os.path.isdir(old_root):
        return wrote
    for rule in rules or []:
        pat, dest, skip = rule.get("glob", ""), rule.get("to", ""), set(rule.get("except") or [])
        sub, leaf = os.path.split(pat.replace("/", os.sep))
        folder = os.path.join(old_root, sub)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name in skip or not fnmatch.fnmatch(name, leaf) or not os.path.isfile(os.path.join(folder, name)):
                continue
            star = name
            if "*" in leaf:
                pre, post = leaf.split("*", 1)
                star = name[len(pre):len(name) - len(post) if post else None]
            rel = dest.replace("*", star)
            ap = os.path.join(brain, rel.replace("/", os.sep))
            if os.path.exists(ap):
                continue
            os.makedirs(os.path.dirname(ap), exist_ok=True)
            shutil.copyfile(os.path.join(folder, name), ap)
            wrote.append(rel)
    return wrote


def main(argv=None):
    ap = argparse.ArgumentParser(description="install or update one replace-folder component from the pf-pack manifest")
    ap.add_argument("component")
    ap.add_argument("--pack", help="a local pf-pack checkout to read instead of GitHub")
    ap.add_argument("--brain", help="the brain to install into (default: the brain this script sits in)")
    ap.add_argument("--check", action="store_true", help="report installed and published versions, change nothing")
    ap.add_argument("--dry-run", action="store_true", help="list what would be written, change nothing")
    ap.add_argument("--force", action="store_true", help="replace even a maintainer copy, or reinstall the same version")
    a = ap.parse_args(argv)
    brain = brain_root(a.brain)

    try:
        manifest = json.loads(fetch("pf-pack-manifest.json", a.pack).decode("utf-8"))
    except Exception as e:
        print("could not read the pf-pack manifest (%s). Nothing was changed." % e)
        return 1
    entry = next((s for s in manifest.get("skills", []) if s.get("skill") == a.component), None)
    if not entry:
        print("the manifest has no component named %s" % a.component)
        return 1
    if entry.get("update") != "replace-folder" or not entry.get("installRoot"):
        print("%s is not a folder component; update it with /update (skills/update/update-skill.md)" % a.component)
        return 2
    root_rel = entry["installRoot"].strip("/")
    root = os.path.join(brain, root_rel.replace("/", os.sep))
    have, want = installed_version(root), entry.get("version")
    if a.check:
        state = "not installed" if not have else ("current" if vkey(have) >= vkey(want) else "update available")
        print("%s: installed %s, published %s (%s)" % (a.component, have or "none", want, state))
        return 0
    if os.path.isfile(os.path.join(root, "release.py")) and not a.force:
        print("%s holds release.py: this is the maintainer copy the component is released FROM, so it is never replaced "
              "here (--force overrides)" % root_rel)
        return 2
    if have and vkey(have) >= vkey(want) and not a.force:
        print("%s %s is installed and current." % (a.component, have))
        return 0
    files = entry.get("files") or []
    bad = [f["dest"] for f in files if not str(f.get("dest", "")).replace("\\", "/").startswith(root_rel + "/")]
    if bad or not files:
        print("refused: the entry lists files outside %s/ (%s)" % (root_rel, ", ".join(bad[:3]) or "no files at all"))
        return 2
    if a.dry_run:
        for f in files:
            print("  would write %s" % f["dest"])
        print("%d files, %s -> %s. Nothing was changed." % (len(files), have or "none", want))
        return 0

    parent = os.path.dirname(root)
    os.makedirs(parent, exist_ok=True)
    stage = tempfile.mkdtemp(prefix=".install-%s-" % a.component, dir=parent)
    aside = None
    try:
        for f in files:
            data = fetch(f["src"], a.pack)
            if f.get("sha256") and hashlib.sha256(data).hexdigest() != f["sha256"]:
                raise RuntimeError("checksum mismatch on %s" % f["src"])
            dest = os.path.join(stage, f["dest"][len(root_rel) + 1:].replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as out:
                out.write(data)
        kept = keep_before_replace(brain, root, entry.get("keepBeforeReplace"))
        if os.path.isdir(root):
            aside = root + ".previous-" + dt.datetime.now().strftime("%Y%m%d%H%M%S")
            os.rename(root, aside)
        os.rename(stage, root)
        stage = None
    except Exception as e:
        if aside and not os.path.isdir(root):
            os.rename(aside, root)
            aside = None
        print("install failed, the old folder is as it was: %s" % e)
        if isinstance(e, PermissionError):
            print("(on Windows a running viewer holds its folder open: stop it, then run this again)")
        return 1
    finally:
        if stage and os.path.isdir(stage):
            shutil.rmtree(stage, ignore_errors=True)
    if aside:
        shutil.rmtree(aside, ignore_errors=True)
    log(brain, "%s %s -> %s: %s/ replaced whole from the pf-pack manifest (%d files)%s" % (
        a.component, have or "none", want, root_rel, len(files),
        ("; kept into the user layer: " + ", ".join(kept)) if kept else ""))
    print("installed %s %s into %s/ (%d files)%s" % (a.component, want, root_rel, len(files),
                                                   ("; kept " + ", ".join(kept)) if kept else ""))
    if entry.get("start"):
        print("start it: %s" % entry["start"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
