#!/usr/bin/env python
"""
Ferryman PULL — canonical, runnable implementation of the app->brain transcript pull.

This is the executable behind skills/ferryman/ferryman-skill.md + pf-app-holon/ferryman-rules.md.
An uninitiated agent should NOT hand-roll a pull — just run this.

Usage:
  python pull.py                 STATUS (default): diff app vs mirror, report, write NOTHING.
  python pull.py --pull          PULL: mirror new/changed transcripts (2-file pattern) +
                                 refresh snapshots (profile/tasks/contacts/projects/presets/
                                 context-documents) + append log lines.
  python pull.py --id <uuid>     Mirror ONE transcript by UUID (+ refresh snapshots).

Correctness guarantees (see ferryman-rules.md):
  - Identity = UUID (never filename). Diff by id; CHANGED iff mirrored updatedAt < app updatedAt.
  - Idempotent: run twice = identical end state.
  - 2-file pattern: <slug>.txt (raw body only) + <slug>.json (everything else, incl. folders[]).
  - App always wins; mirror files are read-only reflections (never hand-edit).
  - UTF-8 forced (cp1252 chokes on transcript bodies).
  - Volume guard: max 12 NEW transcripts per PULL; overflow -> pull-backlog.md. CHANGED unlimited.
  - PULL is read-only against the app: NO POST/PATCH/DELETE ever (push lives in push.py, not here).
"""

import json
import re
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

# Brain root = this brain (two levels above this script), machine-independent
BRAIN = Path(__file__).resolve().parents[2]
TOKEN_PATH = BRAIN / "PF App API.txt"
BASE = "https://app.prospectforge.us/api/v1"
HOLON = BRAIN / "pf-app-holon"
TX_OUT = HOLON / "transcripts"
CACHE = HOLON / ".cache"
MAIN_TX = BRAIN / "transcripts"
LOG = BRAIN / "context" / "log.md"
VOLUME_GUARD = 12

# Add lowercase fragments of YOUR OWN name (e.g. {"fred", "geiser"}) so mirror
# files get named after the OTHER participant, not you. Empty set = first
# participant is used as-is.
SELF_NAMES = set()


def _token():
    return TOKEN_PATH.read_text(encoding="utf-8").strip().splitlines()[0]


def _slug(n):
    return re.sub(r"[^a-zA-Z0-9]+", "-", str(n)).strip("-").lower()


def _get(path, timeout=120):
    """GET an /api/v1 path (leading slash optional). Returns parsed JSON + raw bytes."""
    url = path if path.startswith("http") else f"{BASE}{path if path.startswith('/') else '/'+path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_token()}"})
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    return json.loads(raw.decode("utf-8")), raw


def _cache(path, raw):
    CACHE.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-zA-Z0-9]+", "_", path.strip("/")) + ".json"
    (CACHE / name).write_bytes(raw)


def mirrored_index():
    """{id: updatedAt} for every .json already in the mirror (id read from file, not filename)."""
    idx = {}
    if TX_OUT.exists():
        for jf in TX_OUT.glob("*.json"):
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
                if d.get("id"):
                    idx[d["id"]] = d.get("updatedAt") or ""
            except Exception:
                pass
    return idx


def slug_for(rec):
    parts = rec.get("participants") or []
    others = [p for p in parts if not any(s in p.lower() for s in SELF_NAMES)] if SELF_NAMES else parts
    who = others[0] if others else (parts[0] if parts else (rec.get("title") or "meeting"))
    ctype = rec.get("conversationType") or "meeting"
    if str(ctype).lower() == "other":
        ctype = (rec.get("title") or "meeting")[:40]
    date = (rec.get("date") or "")[:10]
    slug = _slug(f"{who}-{ctype}-{date}")
    # Collision guard: if the leaf already exists in main transcripts/, prefix.
    if (MAIN_TX / f"{slug}.txt").exists() or (MAIN_TX / f"{slug}.md").exists():
        slug = "pf-app-" + slug
    return slug


def mirror_one(tid):
    """Fetch /transcripts/:id, write the 2-file pattern. Returns (slug, title, date, n_actions)."""
    data, raw = _get(f"/transcripts/{tid}")
    _cache(f"transcripts_{tid}", raw)
    rec = data.get("transcript") or data
    body = rec.pop("body", "") or ""
    slug = slug_for(rec)
    TX_OUT.mkdir(parents=True, exist_ok=True)
    (TX_OUT / f"{slug}.txt").write_text(body, encoding="utf-8")
    (TX_OUT / f"{slug}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    n_actions = len(rec.get("actionItems") or [])
    return slug, rec.get("title") or "(untitled)", (rec.get("date") or "")[:10], n_actions


def refresh_snapshots():
    """Overwrite the resource snapshots. Read-only GETs; safe to run any time."""
    done = []
    simple = {
        "/profile/me": "pf-app-profile-me.json",
        "/tasks": "pf-app-tasks.json",
        "/contacts": "pf-app-contacts.json",
        "/projects": "pf-app-projects.json",
        "/presets": "pf-app-presets.json",
        "/context-documents": "pf-app-context-documents.json",
    }
    for path, fname in simple.items():
        try:
            data, raw = _get(path)
            (HOLON / fname).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            _cache(path, raw)
            done.append(fname)
        except urllib.error.HTTPError as e:
            done.append(f"{fname}:HTTP{e.code}")
        except Exception as e:
            done.append(f"{fname}:{type(e).__name__}")
    # context-document bodies (one .md each; there are few)
    try:
        cds = json.loads((HOLON / "pf-app-context-documents.json").read_text(encoding="utf-8"))
        for cd in (cds.get("contextDocuments") or []):
            try:
                d, raw = _get(f"/context-documents/{cd['id']}")
                doc = d.get("contextDocument") or d
                sl = _slug(doc.get("name") or cd.get("name") or cd["id"])
                (HOLON / f"pf-app-context-{sl}.md").write_text(doc.get("content") or "", encoding="utf-8")
            except Exception:
                pass
    except Exception:
        pass
    return done


def _log(lines):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with LOG.open("a", encoding="utf-8") as f:
        for ln in lines:
            f.write(f"[{stamp}] [ferryman] {ln}\n")


def diff():
    """Return (new_list, changed_list) of transcript stubs from /transcripts/tags vs the mirror."""
    data, raw = _get("/transcripts/tags")
    _cache("transcripts_tags", raw)
    tags = data.get("transcripts") or []
    idx = mirrored_index()
    new, changed = [], []
    for t in tags:
        tid = t.get("id")
        if not tid:
            continue
        if tid not in idx:
            new.append(t)
        elif (idx[tid] or "") < (t.get("updatedAt") or ""):
            changed.append(t)
    # most recent first
    key = lambda t: (t.get("date") or "", t.get("createdAt") or "")
    new.sort(key=key, reverse=True)
    changed.sort(key=key, reverse=True)
    return tags, new, changed


def do_status():
    tags, new, changed = diff()
    print(f"STATUS — app has {len(tags)} transcripts; mirror has {len(mirrored_index())}.")
    print(f"  NEW (in app, not mirrored): {len(new)}")
    for t in new[:20]:
        print(f"    + {(t.get('date') or '')[:10]}  {(t.get('title') or '')[:60]}")
    if len(new) > 20:
        print(f"    ... +{len(new)-20} more")
    print(f"  CHANGED (mirror stale): {len(changed)}")
    for t in changed[:20]:
        print(f"    ~ {(t.get('date') or '')[:10]}  {(t.get('title') or '')[:60]}")
    print("Run  python pull.py --pull  to mirror them.")


def do_pull():
    tags, new, changed = diff()
    to_pull = changed + new[:VOLUME_GUARD]
    backlog = new[VOLUME_GUARD:]
    mirrored = []
    for t in to_pull:
        try:
            slug, title, date, na = mirror_one(t["id"])
            mirrored.append((slug, title, date, na))
        except Exception as e:
            print(f"  ! failed {t.get('id')}: {type(e).__name__} {e}")
    if backlog:
        with (TX_OUT / "pull-backlog.md").open("w", encoding="utf-8") as f:
            f.write("# Ferryman pull backlog (volume guard overflow)\n")
            f.write("> Next PULL continues from here.\n\n")
            for t in backlog:
                f.write(f"- {t['id']}  {(t.get('date') or '')[:10]}  {t.get('title')}\n")
    snaps = refresh_snapshots()
    # logging (Agent Tracking Contract)
    loglines = []
    if len(mirrored) > 5:
        slugs = ", ".join(m[0] for m in mirrored)
        loglines.append(f"INGESTED {len(mirrored)} transcripts -> pf-app-holon/transcripts/ [{slugs}]")
    else:
        for slug, title, date, na in mirrored:
            loglines.append(f"INGESTED pf-app-holon/transcripts/{slug}.txt -- {title} ({date}, {na} action items)")
    loglines.append(f"PULL -- {len(mirrored)} transcripts mirrored, {len(backlog)} backlogged, snapshots refreshed ({', '.join(snaps)})")
    if mirrored or backlog:
        _log(loglines)
    print(f"PULL — mirrored {len(mirrored)}, backlogged {len(backlog)}, snapshots: {', '.join(snaps)}")
    for slug, title, date, na in mirrored:
        print(f"  + {slug}  ({date}, {na} action items)")
    if mirrored:
        print("Next: process any new transcripts per skills/ferryman/transcript-intake-runbook.md.")


def do_single(tid):
    slug, title, date, na = mirror_one(tid)
    refresh_snapshots()
    _log([f"INGESTED pf-app-holon/transcripts/{slug}.txt -- {title} ({date}, {na} action items) [single --id]"])
    print(f"Mirrored {slug} ({date}, {na} action items).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pull", action="store_true", help="mirror new/changed (default is STATUS)")
    ap.add_argument("--id", help="mirror ONE transcript by UUID")
    args = ap.parse_args()
    try:
        if args.id:
            do_single(args.id)
        elif args.pull:
            do_pull()
        else:
            do_status()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"API error HTTP {e.code}: {e.reason}. Check PF App API.txt token + endpoint.")
    except urllib.error.URLError as e:
        raise SystemExit(f"Network error: {e.reason}. App unreachable — did NOT fake a pull.")


if __name__ == "__main__":
    main()
