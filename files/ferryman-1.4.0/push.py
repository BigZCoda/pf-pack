#!/usr/bin/env python
"""
Ferryman PUSH, 1.4.0 (2026-11-02): this brain sends NOTHING to the PF App.

Your calls, transcripts and summaries stay on this computer. Run in any way, with any
arguments, this script prints one line and exits 0:

  Nothing sent: your transcripts and summaries stay on this computer.

It opens no token file and makes no network call. pull.py is unchanged and read-only: it
still mirrors what is already in your app account (presets, contacts, records) into
pf-app-holon/.

1.4.0 (2026-11-02):
  - Nothing leaves this brain: no transcript text, no summary, no action items. Every send
    path is behind SEND_SUMMARIES below, which is False.
  - The raw modes (--push, --file and the brain-versus-app diff) are removed: they sent whole
    transcripts.
  - The intake runbook no longer has a push step, and pipeline-verify.py no longer expects a
    pushed record.

1.3.1 (2026-10-02):
  - Every request sends a User-Agent. The app sits behind Cloudflare, whose edge answers 403
    "error code: 1010" to a request with none, before it reaches the app; urllib sends none.
  - BRAIN_ROOT in the environment overrides the brain root (default: two folders up).

1.3.0 (2026-09-03):
  - "source" key removed from the payload builders (the import schema rejects it 422).
  - --participants writes a participants YAML list into the markdown frontmatter.
  - --base retargets the API base.
"""

import os
import sys
import json, re, argparse, urllib.request, urllib.error
from pathlib import Path

# ---- MAINTAINER SWITCH: OFF ---------------------------------------------------------------
# ProspectForge's decision of 2026-11-02: a mentee's brain sends nothing to the PF App. While
# this is False, main() prints NOTHING_SENT and returns before anything below is read or called.
# It is set by ProspectForge in a pack release, never by hand in a brain. If it is ever turned
# on, the only thing that can go is the summary sections of one intake report (--push-summary):
# never the transcript body and never the action items.
SEND_SUMMARIES = False

NOTHING_SENT = "Nothing sent: your transcripts and summaries stay on this computer."

BRAIN = Path(os.environ.get("BRAIN_ROOT") or Path(__file__).resolve().parents[2])   # two folders above this script, or BRAIN_ROOT
TOKEN_PATH = BRAIN / "PF App API.txt"
BASE = "https://app.prospectforge.us/api/v1"

# The sections a summary is made of. "## Action Items" and the transcript body are left out on purpose.
SUMMARY_HEADERS = ["## Summary", "## Key Decisions", "## Relationship Insights", "## Topics"]
CORE_HEADERS = ["## Summary", "## Key Decisions", "## Action Items",
                "## Relationship Insights", "## Topics"]


def _tok():
    return TOKEN_PATH.read_text(encoding="utf-8").strip().splitlines()[0]


def _post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"User-Agent": "prospectforge-brain-ferryman/1.0", "Authorization": f"Bearer {_tok()}", "Content-Type": "application/json"}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:600]


def _infer_type(low):
    if "interview" in low or "onboarding" in low:
        return "Interview"
    if "team-call" in low or "team call" in low:
        return "Team Meeting"
    if "call" in low or "meeting" in low:
        return "1:1"
    return "Other"


def parse_report(text):
    """Return (h1_title, {header: body}) from the report's core (above the first --- divider that
    follows the five H2 sections). Loud error if any header is missing."""
    lines = text.splitlines()
    h1 = next((l[2:].strip() for l in lines if l.startswith("# ")), None)
    positions = {}
    for i, l in enumerate(lines):
        s = l.rstrip()
        if s in CORE_HEADERS and s not in positions:
            positions[s] = i
    missing = [h for h in CORE_HEADERS if h not in positions]
    if missing:
        raise SystemExit(f"ERROR: report is missing required header(s): {', '.join(missing)}. Aborting.")
    last_hdr = max(positions.values())
    end = len(lines)
    for i in range(last_hdr + 1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    core = lines[:end]
    sections = {}
    for h in CORE_HEADERS:
        start = positions[h] + 1
        stop = min([p for p in positions.values() if p > positions[h]] + [end])
        sections[h] = "\n".join(core[start:stop]).strip()
    return h1, sections


def build_summary_payload(args):
    """The summary sections of one intake report as a markdown-with-sections payload. No transcript
    body, no action items."""
    rp = Path(args.push_summary)
    if not rp.is_absolute():
        rp = BRAIN / rp
    if not rp.exists():
        raise SystemExit(f"ERROR: report not found: {rp}")
    h1, sections = parse_report(rp.read_text(encoding="utf-8"))
    title = args.title or h1 or rp.stem
    date = args.date
    if not date:
        ds = re.findall(r"(20\d{2}-\d{2}-\d{2})", rp.stem)
        date = ds[-1] if ds else None
    ctype = args.type or _infer_type(rp.stem.lower())
    fm = ["---", f"title: {title}"]
    if date:
        fm.append(f"date: {date}")
    fm.append(f'conversationType: "{ctype}"')  # must stay quoted (an unquoted 1:1 breaks YAML)
    parts = [p.strip() for p in (args.participants or "").split(",") if p.strip()]
    if parts:
        fm.append("participants: [" + ", ".join(json.dumps(p) for p in parts) + "]")
    fm.append("---")
    md = "\n".join(fm) + "\n" + "\n\n".join(f"{h}\n{sections[h]}" for h in SUMMARY_HEADERS)
    payload = {"markdown": md}
    if args.folder:
        payload["folders"] = [args.folder]
    if args.id:
        payload["id"] = args.id
    meta = {"title": title, "date": date, "type": ctype, "folder": args.folder, "id": args.id,
            "participants": parts}
    return payload, meta


def push_summary(args):
    payload, meta = build_summary_payload(args)
    st, resp = _post("/transcripts/import/validate", payload)
    if not isinstance(resp, dict):
        raise SystemExit(f"ERROR: validate failed: HTTP {st} {resp}")
    if not resp.get("valid"):
        print(f"VALIDATE: HTTP {st} valid=false -- STOPPING. Errors:")
        print(json.dumps(resp, indent=2, default=str)[:1200])
        raise SystemExit(1)
    print(f"VALIDATE: HTTP {st} valid=true")
    if args.dry_run:
        print(f"DRY-RUN -- would send the summary of: {meta['title']} ({meta['date']}, {meta['type']}). Nothing sent.")
        return
    st, resp = _post("/transcripts/import", payload)
    if not isinstance(resp, dict):
        raise SystemExit(f"ERROR: send failed: HTTP {st} {resp}")
    print(f"SENT: HTTP {st} {resp.get('status', '')}".rstrip())
    print(f"  conversation id: {resp.get('id')}")


def main(argv=None):
    if not SEND_SUMMARIES:
        print(NOTHING_SENT)
        return 0
    global BASE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--push-summary", dest="push_summary", metavar="REPORT", required=True,
                    help="intake report .md whose summary sections are sent (never the transcript, never the action items)")
    ap.add_argument("--id", help="existing conversation id -> update in place (omit to create)")
    ap.add_argument("--folder", help="folderId to assign")
    ap.add_argument("--type", help="conversationType; default inferred from the report's filename")
    ap.add_argument("--date", help="YYYY-MM-DD; default derived from the report's filename")
    ap.add_argument("--title", help="app title; default is the report H1")
    ap.add_argument("--participants", metavar="NAMES", help="comma-separated full names of the people in the room")
    ap.add_argument("--base", metavar="URL", help=f"override the API base URL (default {BASE})")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true", help="validate only, send nothing")
    args = ap.parse_args(argv)
    if args.base:
        BASE = args.base.rstrip("/")
    push_summary(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
