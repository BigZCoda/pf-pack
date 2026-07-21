---
version: 1.1.0
name: ferryman
description: >-
  Sync agent between your PF App account (app.prospectforge.us/api/v1, your own personal token)
  and the brain-side mirror at pf-app-holon/. Three modes: STATUS (diff app vs mirror, report only,
  write nothing), PULL (mirror new/changed transcripts via the 2-file pattern + refresh resource
  snapshots), and PUSH (send processed transcripts to the app via push.py — validate-first,
  upsert-by-id). Use when the user says "run the ferryman", "pull from the PF App", "push this
  transcript", "what's new in the app", or "ferryman status".
---

> **2026-07-20 rebuild: settled pipeline + people component.**

# Ferryman
> The carrier between the PF App and `pf-app-holon/`. Registry entry: [[skills/skill-registry.md]]. Per-Holon law: [[pf-app-holon/ferryman-rules.md]] — read it before operating; if an action isn't covered by it, STOP and ask.
>
> **Handling an incoming transcript? Follow [[skills/ferryman/transcript-intake-runbook.md]] — the single canonical file→extract→fold→push procedure. Validate first, push via push.py only; to CREATE push with no `id`, to FIX a record re-push WITH its `id` (upsert-by-id updates in place, no duplicate).**

## Run it (do NOT hand-roll a pull or a push)

There are canonical executables. An uninitiated agent must NOT reconstruct these from prose — just run them:

```
python skills/ferryman/pull.py               # STATUS: diff app vs mirror, report only (safe — writes nothing)
python skills/ferryman/pull.py --pull        # PULL: mirror new/changed (2-file) + refresh snapshots + log
python skills/ferryman/pull.py --id <uuid>   # mirror ONE transcript by UUID

python skills/ferryman/push.py --push-summary <report.md> --raw <raw.txt> [--id <uuid>] [--dry-run]
                                             # PUSH a processed transcript (validate-first; see runbook step 4)
python skills/ferryman/pipeline-verify.py    # verify the pipeline invariants (runbook step 8)
```

`pull.py` implements everything in this doc + `ferryman-rules.md`: UUID diff (CHANGED iff mirror `updatedAt` < app), the 2-file pattern, `folders[]` capture, resource snapshots (profile/tasks/contacts/projects/presets/context-documents), volume guard (12 NEW/run → `pull-backlog.md`), UTF-8, and `INGESTED`/`PULL` logging. It never writes to the app (pull is read-only; writes live in push.py).

## What this is

One agent, two directions, one Holon. Reads your PF App API with your personal token, writes faithful mirror files into `pf-app-holon/`, and pushes processed transcripts up via `push.py`. The Ferryman does NOT summarize, does NOT interpret, does NOT update people cards — its job ends when the mirror file is written (pull) or the record is upserted (push) and the log line lands. Interpretation (summaries, people folds) is the transcript-processor's job, per the intake runbook.

**Push is LIVE — via push.py only.** `push.py --push-summary` assembles the markdown-with-sections payload from an intake report's 5-header core + the raw body, enforces the due/emoji hygiene rules in code, ALWAYS validates first (`/import/validate`), and pushes once. No `--id` = create (app-side dedup flags likely duplicates for your review); `--id` = upsert in place (no duplicate; unknown id → 404, never creates). Never assemble a push payload by hand. Full rules: runbook step 4 + guardrails.

## Auth + transport

- Token: `PF App API.txt` line 1 (brain root). Yours, minted by you in the app (Settings → API); sees only your data. NEVER print, log, or echo the token anywhere.
- `Authorization: Bearer <token>`, base `https://app.prospectforge.us/api/v1`.
- Use Python with UTF-8 forced (`encoding="utf-8"` on every open) — transcript bodies contain characters cp1252 chokes on.
- If auth fails or the API is unreachable: STOP, report the exact error. Never fake a pull, never fall back to stale prose about sync state.

## Mode: STATUS (report only — writes nothing, logs nothing)

1. Read `pf-app-holon/ferryman-rules.md` (the law) and list currently-mirrored transcript UUIDs (read `id` from every `.json` in `pf-app-holon/transcripts/`, plus `pull-backlog.md` if present).
2. `GET /api/v1` (discovery) — confirm token works + endpoint list matches the rules-file inventory. Flag drift.
3. `GET /transcripts/tags` — full transcript list. Diff by UUID against the mirror: NEW (in app, not mirrored), CHANGED (mirrored but app `updatedAt` is newer), BACKLOGGED (in pull-backlog).
4. `GET /profile/me`, `/tasks`, `/contacts`, `/projects` — record counts; diff against `pf-app-holon/pf-app-*.json` snapshots for a coarse changed/unchanged signal.
5. Report in chat: counts per resource, new/changed transcript titles+dates, backlog size. No file writes, no log lines (unless an error worth flagging — then one `[ferryman]` line).

## Mode: PULL (mirror new/changed)

1. Everything STATUS does (steps 1-4), then:
2. **Mirror transcripts.** For each NEW or CHANGED transcript (most recent first by `date` then `createdAt`):
   - `GET /transcripts/:id`
   - Write the **2-file pattern** (ferryman-rules Section 3): `<slug>.txt` = body only; `<slug>.json` = everything else.
   - Slug per rules Section 3 (`<first-last>-<conversation-type>-<YYYY-MM-DD>`); on a leaf-name collision with main `transcripts/`, prefix `pf-app-`.
   - **Volume guard:** max 12 new transcripts per PULL. Overflow goes to `pf-app-holon/transcripts/pull-backlog.md`. CHANGED re-pulls don't count against the guard.
3. **Refresh snapshots.** Overwrite `pf-app-holon/pf-app-*.json`. Raw responses for every call land in `pf-app-holon/.cache/`.
4. **Log (Agent Tracking Contract).** Append to `context/log.md`, agent-id `[ferryman]`:
   - One `INGESTED pf-app-holon/transcripts/<slug>.txt -- <title> (<date>, ...)` line per mirrored transcript.
   - **Batch rule:** more than 5 mirrored in one run → ONE INGESTED line listing all slugs.
   - One `PULL` summary line: transcripts mirrored / backlogged, snapshots refreshed, errors.
5. **Report in chat:** what landed, what's backlogged, anything that surprised (shape drift vs ferryman-rules → flag it AND trust reality over the docs).

## Mode: PUSH (processed transcript → app)

Follow [[skills/ferryman/transcript-intake-runbook.md]] steps 4-8. The short version: `push.py --push-summary <intake-report> --raw <raw>` (validate → push → GET-confirm → log `SYNCED` → `pull.py --pull` → `pipeline-verify.py`). Corrections re-push WITH the record's `id`.

## Hard rules (non-negotiable)

- Mirror is read-only from the brain side; never edit mirror files in place.
- Idempotent: pull twice = same end state; diff by UUID, not filename.
- `.cache/` and `PF App API.txt` never sync anywhere.
- Admin endpoints out of scope; 401/403 from them is expected, not an error.
- If the per-Holon rules file is missing, the Ferryman cannot operate in that Holon. Full stop.

## Registry wiring

- **Listens for:** nothing — invoked manually ("pull from the app", "push this transcript") or as runbook steps 4/7/8.
- **Emits:** `INGESTED` / `PULL` / `SYNCED` log lines in `context/log.md`.

**Last touched:** 2026-07-20 rebuild: settled pipeline + people component — push-is-live via push.py (validate-first, upsert-by-id), pipeline-verify added, genericized from the reference implementation.
