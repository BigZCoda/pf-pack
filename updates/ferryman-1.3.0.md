# Ferryman 1.3.0 — push.py was failing at validate; participants now ship (2026-09-03)

**From 1.2.0.** Full replacement files at
`https://github.com/BigZCoda/pf-pack/tree/main/files/ferryman-1.3.0/` — or apply the changes below to your copies, preserving any LOCAL ADAPTATION blocks and your own filled-in folder table. `pull.py`, `pipeline-verify.py` and `ferryman-adapter-contract.md` are unchanged in this release.

**Apply to:** `skills/ferryman/push.py` (required), `skills/ferryman/transcript-intake-runbook.md`, `skills/ferryman/ferryman-skill.md`, and `pf-app-holon/ferryman-rules.md`. Merge — do not blind-replace anything you've adapted.

## 1. FIX (required) — push.py sent a field the API rejects, so every push has been failing

Your `push.py` sends `"source": "manual"` in both payload builders (the `--push-summary` path and the raw `--push`/`--file` path). The import schema rejects that field: `422 Unrecognized field(s): source`, on `/transcripts/import/validate` and on `/transcripts/import`. Because push.py validates first and stops on a validate failure, **every markdown push since the schema tightened has failed before writing anything**, and nothing surfaced it as an error you would notice. The server sets `source` itself.

Apply: delete the `"source": "manual"` key from both payload dicts in `push.py` (replace `push.py` with the 1.3.0 file if you have not adapted it). Then confirm with a dry run against a real report:
```
python skills/ferryman/push.py --push-summary transcripts/import-reports/<report>.md --raw transcripts/<raw>.txt --dry-run
```
A 1.3.0 dry run shows the would-be payload with no `source` key and reports validate OK.

Same fix in the runbook: step 4's example payload showed `"source": "manual"`. Remove it there too — a documented example that fails is followed.

## 2. NEW — participants ship in the frontmatter

The known gap from 1.2.0 is closed. `push.py --participants "Full Name,Full Name"` writes a YAML **list** into the markdown frontmatter:
```yaml
---
title: <Title>
date: <YYYY-MM-DD>
conversationType: "<type>"
participants:
  - Full Name
  - Full Name
---
```
The app stores them and (once its contact-sync build is deployed) matches each participant to your contacts and links the conversation to them. Rules that come with the flag:
- **Participants only — never mentions.** Participants are who was in the room: a small closed set you know before processing, safe to resolve. People merely talked about get no id and are never passed here.
- **Use canonical contact names, not transcriber labels.** A transcript's speaker strings are speech-recognition output (`Speaker 2`, mangled surnames). Resolve them to the exact contact name before passing them.
- A top-level `participants` JSON key is rejected the same way `source` was. Frontmatter list only. push.py does this for you.
- **Read the import response's `contacts` block** when the app returns one (`matched / created / ambiguous / skipped / enrichmentQueued`). `ambiguous` means a participant matched two or more contacts and was **linked to none** — it drops silently unless you look.

## 3. NEW — `--base` (and a reminder about `--title`, which already existed)

- `--base <url>` retargets the API base (default `https://app.prospectforge.us/api/v1`). Use only when you know why; a local dev build of the app shares its production database.
- `--title "<title>"` is not new, but use it: without it push.py takes the title from the report's H1, which for an intake report names the record after the report, not the call.

## 4. Smaller merges

- Runbook guardrail "Participants (known gap)" → replace with the participants rules above.
- Runbook step 4 push.py invocation → add `[--participants "A,B"] [--title "<title>"] [--base <url>]`.
- `ferryman-rules.md` capability matrix, participants row: status `LIVE (endpoint) / GAP (push.py)` → `LIVE`; header and "Last touched" updated.
- `ferryman-skill.md`: 1.3.0 note; push.py invocation updated.
- A habit worth adopting from the reference brain: **before reporting that a field is empty or a count is zero, print the response's keys.** A field that is not on that endpoint returns nothing and looks exactly like real emptiness.

Bump the skill frontmatter to `1.3.0` + the matching row in `skills/skill-registry.md`; log the update.
