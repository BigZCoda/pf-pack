#!/usr/bin/env python
"""
Ferryman PUSH — send brain-origin transcripts the app is MISSING into your PF App account.

Goal: "everything in the same place." The app is canonical for transcripts; this pushes
raw brain transcripts (main transcripts/) that aren't in the app yet, so app + mirror are complete.

Usage:
  python push.py                 DRY (default): diff brain transcripts/ vs app, VALIDATE each
                                 missing candidate via /import/validate, report. Writes NOTHING.
  python push.py --push          PUSH: create the missing ones (no id -> app runs dedup).
  python push.py --file <path>   Push ONE specific transcript file.

  python push.py --push-summary <intake-report.md> --raw <raw.txt>
                 [--id <uuid>] [--folder <folderId>] [--type "<conversationType>"]
                 [--date YYYY-MM-DD] [--title "<title>"] [--dry-run]
      SUMMARY PUSH (runbook step 4): assemble the markdown-with-sections payload from the
      retained intake report (the 5-header core above the first --- divider) plus
      the raw transcript body. Enforces the DUE rule (ISO date or the segment is stripped
      with a warning; emoji in owner/due segments stripped the same way). ALWAYS validates
      first; --dry-run stops after validate. No --id -> create; --id -> upsert in place.

Safety:
  - id-less creates => the app's dedup runs: a likely match is FLAGGED
    (reviewStatus=possible_duplicate) for you to resolve in the app's review view, never
    silently merged/dropped. So an imperfect "missing" guess can't silently dupe.
  - source is forced to 'manual' (app enum: otter|zoom|manual).
  - Folder assignment is additive + ownership-checked; unfoldered pushes get their folder
    assigned in the app afterward.
  - Bodies never enter the agent's context — this script reads files and posts directly.
"""

import json, re, argparse, urllib.request, urllib.error
from pathlib import Path

# Brain root = this brain (two levels above this script), machine-independent
BRAIN = Path(__file__).resolve().parents[2]
TOKEN_PATH = BRAIN / "PF App API.txt"
BASE = "https://app.prospectforge.us/api/v1"
TX = BRAIN / "transcripts"

# ---- YOUR FOLDER IDS (discover, then record here) ---------------------------
# Discover your own folders:  GET /api/v1/projects  then  GET /api/v1/projects/:id/folders
# Keep your own name -> UUID table here, and wire the ones you use into build()
# below — or just pass --folder <uuid> on the command line. None = push
# unfoldered and assign the folder in the app afterward.
INTERVIEWS_FOLDER = None  # e.g. "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# Add lowercase fragments of YOUR OWN name (e.g. {"fred", "geiser"}) so files
# named after you can still be matched to app records by date in the diff heuristic.
SELF_NAMES = set()

STOP = set("team call meeting transcript notes interview synthesis analysis with and the mentee mentor program update check checkin chat texts post group full onboarding".split())
SKIP_RE = re.compile(r"(INDEX|readme|-notes|-synthesis|-analysis|-nuggets)", re.I)


def _tok():
    return TOKEN_PATH.read_text(encoding="utf-8").strip().splitlines()[0]


def _toks(s):
    return set(t for t in re.findall(r"[a-z]{3,}", (s or "").lower()))


def _pmatch(a, B):
    return any(a == b or (len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a))) for b in B)


def _post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"Authorization": f"Bearer {_tok()}", "Content-Type": "application/json"}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:600]


def app_list():
    req = urllib.request.Request(f"{BASE}/transcripts/tags", headers={"Authorization": f"Bearer {_tok()}"})
    d = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    return d.get("transcripts") or []


def candidates():
    out = []
    for f in sorted(list(TX.glob("*.txt")) + list(TX.glob("*.md"))):
        if SKIP_RE.search(f.name):
            continue
        out.append(f)
    return out


def build(path):
    base = path.stem
    ds = re.findall(r"(20\d{2}-\d{2}-\d{2})", base)
    date = ds[-1] if ds else None
    name = re.sub(r"20\d{2}-\d{2}-\d{2}", "", base).replace("-", " ").strip(" -")
    title = name.title() or base
    low = base.lower()
    folders = []
    if "interview" in low or "onboarding" in low:
        ctype = "Interview"
        if INTERVIEWS_FOLDER:
            folders = [INTERVIEWS_FOLDER]
    elif "team-call" in low or "team call" in low:
        ctype = "Team Meeting"
    elif "call" in low or "meeting" in low:
        ctype = "1:1"
    else:
        ctype = "Other"
    p = {"title": title, "conversationType": ctype, "transcript": path.read_text(encoding="utf-8"),
         "source": "manual"}
    if date:
        p["conversationDate"] = date
    if folders:
        p["folders"] = folders
    return p, date


# ---------- summary push (runbook step 4: markdown-with-sections) ----------

CORE_HEADERS = ["## Summary", "## Key Decisions", "## Action Items",
                "## Relationship Insights", "## Topics"]
DUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# emoji + symbol/arrow/dingbat blocks (U+2190-U+2BFF covers arrows/misc symbols/dingbats) + VS16
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF←-⯿️]")


def _infer_type(low):
    if "interview" in low or "onboarding" in low:
        return "Interview"
    if "team-call" in low or "team call" in low:
        return "Team Meeting"
    if "call" in low or "meeting" in low:
        return "1:1"
    return "Other"


def parse_report(text):
    """Return (h1_title, {header: body}) from the push-mappable core (above the first
    --- divider that follows the five H2 sections). Loud error if any header is missing."""
    lines = text.splitlines()
    h1 = next((l[2:].strip() for l in lines if l.startswith("# ")), None)
    positions = {}
    for i, l in enumerate(lines):
        s = l.rstrip()
        if s in CORE_HEADERS and s not in positions:
            positions[s] = i
    missing = [h for h in CORE_HEADERS if h not in positions]
    if missing:
        raise SystemExit(f"ERROR: report is missing required header(s): {', '.join(missing)} "
                         f"-- not a push-mappable intake-report core. Aborting.")
    last_hdr = max(positions.values())
    end = len(lines)
    for i in range(last_hdr + 1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    else:
        print("WARNING: no --- divider found after the five core sections; using the whole file as core.")
    core = lines[:end]
    sections = {}
    for h in CORE_HEADERS:
        start = positions[h] + 1
        stop = min([p for p in positions.values() if p > positions[h]] + [end])
        sections[h] = "\n".join(core[start:stop]).strip()
    return h1, sections


def clean_action_items(body):
    """Enforce the DUE rule (one bad due value kills the WHOLE item batch server-side).
    Strip non-ISO due segments and emoji-bearing owner/due segments; warn, never abort."""
    out, warnings = [], []
    for ln in body.splitlines():
        if not ln.lstrip().startswith("- "):
            out.append(ln)
            continue
        parts = ln.split(" | ")
        kept = [parts[0]]
        for seg in parts[1:]:
            m = re.match(r"\s*(owner|due)\s*:\s*(.*?)\s*$", seg, re.I)
            if not m:
                kept.append(seg)
                continue
            key, val = m.group(1).lower(), m.group(2)
            if EMOJI_RE.search(val):
                warnings.append(f"stripped {key} '{val}' (emoji not allowed in {key} segment) from: {parts[0].strip()}")
                continue
            if key == "due" and not DUE_RE.match(val):
                warnings.append(f"stripped due '{val}' (must be YYYY-MM-DD; omit when no real deadline) from: {parts[0].strip()}")
                continue
            kept.append(seg)
        out.append(" | ".join(kept))
    return "\n".join(out), warnings


def build_summary_payload(args):
    rp = Path(args.push_summary)
    if not rp.is_absolute():
        rp = BRAIN / rp
    raw = Path(args.raw)
    if not raw.is_absolute():
        raw = BRAIN / raw
    if not rp.exists():
        raise SystemExit(f"ERROR: report not found: {rp}")
    if not raw.exists():
        raise SystemExit(f"ERROR: raw transcript not found: {raw}")

    # SETTLED design (do not rename, refold, or gate): "Action Items" is the app's
    # name and the wire header. ## Action Items lines push as-is -> land "Pending
    # Review" in the record's Action Items panel -> YOU approve in the app ->
    # approved tasks with owner + date attached. This is the design and it works.
    h1, sections = parse_report(rp.read_text(encoding="utf-8"))
    items_body, warnings = clean_action_items(sections["## Action Items"])
    item_count = sum(1 for l in items_body.splitlines() if l.lstrip().startswith("- "))
    sections["## Action Items"] = items_body

    title = args.title or h1 or rp.stem
    if not args.title and h1 and h1.lower().startswith("import-checkup"):
        print(f"WARNING: title comes from the report H1 and looks like a report header ('{h1}') "
              f"-- pass --title for a cleaner app title.")
    date = args.date
    if not date:
        ds = re.findall(r"(20\d{2}-\d{2}-\d{2})", raw.stem) or re.findall(r"(20\d{2}-\d{2}-\d{2})", rp.stem)
        date = ds[-1] if ds else None
        if not date:
            print("WARNING: no --date and none derivable from filenames; frontmatter date omitted.")
    ctype = args.type or _infer_type(raw.stem.lower())

    fm = ["---", f"title: {title}"]
    if date:
        fm.append(f"date: {date}")
    fm.append(f'conversationType: "{ctype}"')  # MUST stay quoted (unquoted 1:1 breaks YAML)
    fm.append("---")
    md = "\n".join(fm) + "\n"
    md += "\n\n".join(f"{h}\n{sections[h]}" for h in CORE_HEADERS)
    md += "\n\n## Transcript\n" + raw.read_text(encoding="utf-8")

    payload = {"markdown": md, "source": "manual"}
    if args.folder:
        payload["folders"] = [args.folder]
    if args.id:
        payload["id"] = args.id
    meta = {"title": title, "date": date, "type": ctype, "folder": args.folder,
            "id": args.id, "item_count": item_count, "warnings": warnings}
    return payload, meta


def push_summary(args):
    payload, meta = build_summary_payload(args)
    for w in meta["warnings"]:
        print(f"WARNING: {w}")

    st, resp = _post("/transcripts/import/validate", payload)
    if not isinstance(resp, dict):
        raise SystemExit(f"ERROR: validate failed: HTTP {st} {resp}")
    if not resp.get("valid"):
        print(f"VALIDATE: HTTP {st} valid=false -- STOPPING. Errors:")
        print(json.dumps(resp, indent=2, default=str)[:1200])
        raise SystemExit(1)
    print(f"VALIDATE: HTTP {st} valid=true")

    if args.dry_run:
        print("\nDRY-RUN -- would push:")
        print(f"  title:  {meta['title']}")
        print(f"  date:   {meta['date']}")
        print(f"  type:   {meta['type']}")
        print(f"  folder: {meta['folder'] or '(none)'}")
        print(f"  mode:   {'UPSERT id ' + meta['id'] if meta['id'] else 'CREATE (no id)'}")
        print(f"  action items: {meta['item_count']}")
        print(f"  stripped-due/owner warnings: {len(meta['warnings'])}")
        print("Re-run without --dry-run to push.")
        return

    st, resp = _post("/transcripts/import", payload)
    if not isinstance(resp, dict):
        raise SystemExit(f"ERROR: push failed: HTTP {st} {resp}")
    print(f"PUSH: HTTP {st} {resp.get('status', '')}".rstrip())
    print(f"  conversation id: {resp.get('id')}")
    print(f"  actionItemCount: {resp.get('actionItemCount')}")
    print("Now run pull.py --pull to mirror (runbook step 7).")


def is_present(path, app):
    base = path.stem
    ds = re.findall(r"(20\d{2}-\d{2}-\d{2})", base)
    d = ds[-1] if ds else None
    bt = _toks(base) - STOP
    distinct = bt - SELF_NAMES
    for a in app:
        at = _toks(a.get("title")) - STOP
        if any(_pmatch(x, at) for x in distinct):
            return True
    if bt & SELF_NAMES and d:
        for a in app:
            if (a.get("date") or "")[:10] == d:
                return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--push", action="store_true", help="actually create (default is dry validate)")
    ap.add_argument("--file", help="push ONE file (absolute or transcripts/-relative)")
    ap.add_argument("--push-summary", dest="push_summary", metavar="REPORT",
                    help="intake report .md (5-header core) to assemble a markdown-with-sections push from")
    ap.add_argument("--raw", help="raw transcript file whose body goes under ## Transcript (required with --push-summary)")
    ap.add_argument("--id", help="existing conversation id -> UPSERT in place (omit to CREATE)")
    ap.add_argument("--folder", help="folderId to assign (see runbook Folder IDs)")
    ap.add_argument("--type", help='conversationType (quoted in frontmatter); default inferred from raw filename')
    ap.add_argument("--date", help="YYYY-MM-DD; default derived from raw/report filename")
    ap.add_argument("--title", help="app title; default is the report H1")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="with --push-summary: validate + print payload summary, write nothing")
    args = ap.parse_args()

    if args.push_summary:
        if not args.raw:
            raise SystemExit("ERROR: --push-summary requires --raw <raw transcript file>.")
        push_summary(args)
        return

    if args.file:
        fp = Path(args.file)
        if not fp.is_absolute():
            fp = TX / fp.name
        payload, _ = build(fp)
        st, resp = _post("/transcripts/import" if args.push else "/transcripts/import/validate", payload)
        print(f"{'PUSH' if args.push else 'VALIDATE'} {fp.name}: HTTP {st}")
        print(json.dumps(resp, indent=2, default=str)[:800] if isinstance(resp, dict) else resp)
        return

    app = app_list()
    cands = candidates()
    missing = [c for c in cands if not is_present(c, app)]
    print(f"brain raw transcripts: {len(cands)} | app: {len(app)} | MISSING from app: {len(missing)}\n")
    pushed = flagged = errs = 0
    for c in missing:
        payload, date = build(c)
        path = "/transcripts/import" if args.push else "/transcripts/import/validate"
        st, resp = _post(path, payload)
        if not isinstance(resp, dict):
            print(f"  ! {c.name}: HTTP {st} {resp[:120]}"); errs += 1; continue
        if args.push:
            dup = resp.get("possibleDuplicate")
            tag = " ⚠ possible_duplicate" if dup else ""
            print(f"  + {c.name} -> id {resp.get('id')}{tag} | folders {(resp.get('folders') or {}).get('assigned')}")
            pushed += 1; flagged += 1 if dup else 0
        else:
            print(f"  · {c.name}: valid={resp.get('valid')} type={build(c)[0]['conversationType']} date={date}")
    print()
    if args.push:
        print(f"PUSHED {pushed} ({flagged} flagged possible_duplicate -> resolve in the app's review view), {errs} errors.")
    else:
        print(f"DRY: {len(missing)} would be pushed. Re-run with --push to create them.")


if __name__ == "__main__":
    main()
