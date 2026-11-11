---
version: 1.4.0
name: ferryman
description: >-
  Read-only connection between your PF App account (app.prospectforge.us/api/v1, your own personal token)
  and the brain-side mirror at pf-app-holon/. Two modes: STATUS (diff app vs mirror, report only, write
  nothing) and PULL (mirror what is already in your account via the 2-file pattern + refresh resource
  snapshots + the app's self-describing API catalog). Nothing goes from this brain to the app: your calls,
  transcripts and summaries stay on this computer, and push.py sends nothing. Use when the user says "run
  the ferryman", "pull from the PF App", "what's new in the app", or "ferryman status"; and when asked to
  "push this transcript", to say that it stays on this computer.
---

> **1.4.0 (2026-11-02):** nothing is sent to the PF App any more. Your calls, transcripts and summaries stay on this computer. `push.py` sends nothing: run in any way it prints *Nothing sent: your transcripts and summaries stay on this computer.* and exits 0, without opening your token file. The intake runbook has no push step, and `pipeline-verify.py` no longer looks for a pushed record. `pull.py` is unchanged and still read-only.
> **1.3.1 (2026-10-02):** `pull.py` sends a `User-Agent` header on every call; without it the app's edge answers `403` (`error code: 1010`) before the request reaches the app, which reads like a bad token. `BRAIN_ROOT` in the environment overrides the brain root.

# Ferryman
> The reader between the PF App and `pf-app-holon/`. Registry entry: [[skills/skill-registry.md]]. Per-Holon law: [[pf-app-holon/ferryman-rules.md]] — read it before operating; if an action isn't covered by it, STOP and ask.
>
> **Handling an incoming transcript? Follow [[skills/ferryman/transcript-intake-runbook.md]] — file, extract, fold, log, verify. It all stays on this computer.**

## Run it (do NOT hand-roll a pull)

There are canonical executables. An uninitiated agent must NOT reconstruct these from prose — just run them:

```
python skills/ferryman/pull.py               # STATUS: diff app vs mirror, report only (safe — writes nothing)
python skills/ferryman/pull.py --pull        # PULL: mirror new/changed (2-file) + refresh snapshots + catalog + log
python skills/ferryman/pull.py --id <uuid>   # mirror ONE transcript by UUID
python skills/ferryman/pipeline-verify.py    # verify the transcript pipeline (runbook step 5)
```

`pull.py` implements everything in this doc + `ferryman-rules.md`: UUID diff (CHANGED iff mirror `updatedAt` < app), the 2-file pattern, `folders[]` capture, resource snapshots (profile/tasks/contacts/projects/presets/context-documents), volume guard (12 NEW/run → `pull-backlog.md`), UTF-8, and `INGESTED`/`PULL` logging. It also refreshes **`pf-app-holon/pf-app-api-catalog.json`** from `GET /api/v1` — the app's own self-describing answer to "what can this token call", stamped `_fetchedAt` so staleness is visible. **pull.py never writes to the app.**

`push.py` is still installed so that anything which calls it gets a plain answer instead of an error: it prints one line, *Nothing sent: your transcripts and summaries stay on this computer.*, and exits 0. It opens no token file and makes no network call.

## What this is

One agent, one direction, one Holon. Reads your PF App account with your personal token and writes faithful mirror files into `pf-app-holon/`. The Ferryman does NOT summarize, does NOT interpret, does NOT update people cards — its job ends when the mirror file is written and the log line lands. Interpretation (summaries, people folds) is the transcript-processor's job, per the intake runbook, and what it makes stays on this computer.

**Nothing goes to the app.** No transcript text, no summary, no action item. If you are asked to push or upload a processed call, say that calls, transcripts and summaries stay on this computer; do not write a request to the app's API by hand instead.

## Auth + transport

- Token: `PF App API.txt` line 1 (brain root). Yours, minted by you in the app (Settings → API); sees only your data. Used by `pull.py` alone, read-only. NEVER print, log, or echo the token anywhere.
- `Authorization: Bearer <token>`, base `https://app.prospectforge.us/api/v1`.
- Use Python with UTF-8 forced (`encoding="utf-8"` on every open) — transcript bodies contain characters cp1252 chokes on.
- If auth fails or the API is unreachable: STOP, report the exact error. Never fake a pull, never fall back to stale prose about sync state.
- No token file: the pull has nothing to read, and nothing else in this brain needs one.

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
3. **Refresh snapshots.** Overwrite `pf-app-holon/pf-app-*.json` + the API catalog (`pf-app-api-catalog.json`, `_fetchedAt`-stamped). Raw responses for every call land in `pf-app-holon/.cache/`.
4. **Log (Agent Tracking Contract).** Append to `context/log.md`, agent-id `[ferryman]`:
   - One `INGESTED pf-app-holon/transcripts/<slug>.txt -- <title> (<date>, ...)` line per mirrored transcript.
   - **Batch rule:** more than 5 mirrored in one run → ONE INGESTED line listing all slugs.
   - One `PULL` summary line: transcripts mirrored / backlogged, snapshots refreshed, errors.
5. **Report in chat:** what landed, what's backlogged, anything that surprised (shape drift vs ferryman-rules → flag it AND trust reality over the docs).

## Hard rules (non-negotiable)

- Nothing goes from this brain to the app: no POST, PATCH, PUT or DELETE, by any script or by hand.
- Mirror is read-only from the brain side; never edit mirror files in place.
- Idempotent: pull twice = same end state; diff by UUID, not filename.
- `.cache/` and `PF App API.txt` never sync anywhere.
- Admin endpoints out of scope; 401/403 from them is expected, not an error.
- If the per-Holon rules file is missing, the Ferryman cannot operate in that Holon. Full stop.

## Registry wiring

- **Listens for:** nothing — invoked manually ("pull from the app", "ferryman status").
- **Emits:** `INGESTED` / `PULL` log lines in `context/log.md`.

**Last touched:** 2026-11-02 (1.4.0): nothing is sent to the app; push.py sends nothing, the runbook's push steps and pipeline-verify's pushed-record check removed. Previous: 2026-10-02 (1.3.1): User-Agent on every call, `BRAIN_ROOT`. Previous: 2026-09-03 (1.3.0), 2026-08-28 (1.2.0), 2026-07-20 rebuild.
