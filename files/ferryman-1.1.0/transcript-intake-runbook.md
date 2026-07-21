# Transcript Intake Runbook — the ONE process for handling a transcript

## THE SYSTEM (read this before anything else — it is incredibly straightforward)
1. **Raw transcript** → filed locally in `transcripts/`, processed ONCE (preset parity).
2. **The record** (summary + key decisions + action items + insights + topics) → pushed to your PF App account. **The app is the home for transcripts and summaries; raw + summary live together on one record.**
3. **`## Action Items` lines are how tasks are generated from a transcript — that IS the design and it WORKS.** Pushed items land "Pending Review" in the record's Action Items panel; **you approve them in the app** → approved tasks, owner + date attached. The name is **Action Items** — the app's name. Do not rename it, fold it, gate it, or "fix" it. The one real failure mode is bad `due:` formatting, which push.py now strips automatically.
4. **The intake report** → `transcripts/import-reports/` (pipeline ledger — NEVER `deliverables/`).
5. **Pull mirrors it back** → `pf-app-holon/transcripts/` (machine mirror, .json + .txt side by side).
6. **People understanding** → folds into your `people/` cards, brain-side only (people cards never push to the app).

> This is THE canonical procedure for what to do when you hand over a call transcript. If any other doc disagrees, this wins for the intake flow. Deeper mechanics + API reference live in [[pf-app-holon/ferryman-rules.md]].

## When this runs
You drop (or point at) a **call/meeting** transcript and want it processed. **Calls/meetings only — never texts or chats.**

## The 8 steps (do ALL of them, in order)

1. **File the raw transcript** into `transcripts/` with a globally-unique name: `<who>-<type>-<YYYY-MM-DD>.txt` (e.g. `mentor-checkin-2026-08-03.txt`). Add a row for it to `transcripts/INDEX.md` (create the file with a simple `| file | date | type | pushed |` table if it doesn't exist yet). This is local filing only — **it does NOT reach the app by itself. There is no auto-sync/watcher.** The push in step 4 is what puts it in the app.

2. **Extract it — using the app's presets (Preset Parity).** Do NOT improvise a format. Load `pf-app-holon/pf-app-presets.json`, pick the preset matching the transcript type, and run its prompt verbatim (see [[skills/transcript-processor/transcript-processor-skill.md]] "Preset Parity"). Write the result under the exact core headers: **`## Summary`**, **`## Key Decisions`**, **`## Action Items`** (one per line as **`- <item> | owner: <Name> | due: <YYYY-MM-DD>`** — owner/due optional, due ISO-only; see step 4), **`## Relationship Insights`**, **`## Topics`**. Save as `transcripts/import-reports/import-checkup-<slug>-<date>.md` — it is what gets pushed (no re-extraction). **NEVER save intake reports to `deliverables/`** — deliverables/ is for human-facing deliverables only; the intake report is pipeline ledger and lives with the raws + INDEX. pipeline-verify check 7 enforces this.

3. **Fold the substance** into the relevant `people/` cards and any open threads (dated fold at the bottom of each card — see the "People fold" section of the transcript-processor skill).

4. **Push to the app — validate, then push, via push.py ONLY.** Endpoint `POST /transcripts/import` (base `https://app.prospectforge.us/api/v1`, `Authorization: Bearer <PF App API.txt line 1>`). `push.py --push-summary` assembles the **markdown-with-sections** payload from the report core:
   ```json
   {"markdown": "---\ntitle: <Title>\ndate: <YYYY-MM-DD>\nconversationType: \"<type>\"\n---\n## Summary\n<summary>\n\n## Key Decisions\n- <d>\n\n## Action Items\n- <item> | owner: <Name> | due: <YYYY-MM-DD>\n\n## Topics\n- <t>\n\n## Transcript\n<raw body>", "source": "manual", "folders": ["<folderId>"]}
   ```
   The app maps `title` + `## Summary`→aiSummary + `## Key Decisions` (+ `## Relationship Insights`)→keyInsights + **`## Action Items` lines→Action Items on the record, landing "Pending Review" (you approve in the app → approved tasks)** + `## Topics`→tags, stores the body, and stores `date`, quoted `conversationType`, and `folders`. **This is the design and it works.**

   **DUE rule (one bad due kills the ENTIRE item batch server-side):** `| due: YYYY-MM-DD` ISO only; **no real deadline → OMIT the `| due:` segment** — never `due: none`/`TBD`/`ASAP`; no emoji inside owner/due segments (🔥 goes on the item text). push.py strips violations with a warning.

   **OWNER rule:** `owner` is free text the app fuzzy-matches to people — use `me` for your own items, a person's full canonical name otherwise (`owner: Sarah Chen`, not `owner: Sarah`); blank defaults to you (the token user).
   - ⚠️ **`conversationType` MUST be quoted** in the frontmatter (`"1:1"`) — an unquoted `1:1` breaks YAML and the type falls back to "Other".
   - ✅ Trust the response code: create returns `201 imported`, upsert returns `200 reimported`.
   - **`## Topics` populates the app's `tags` field** — tags = topics, so that's the intended home (not a gap). Keep the `## Topics` header (it's the verified parse key that fills `tags`).

5. **Confirm it landed (GET the record).** The push sets date/type/folder, so you usually do NOT need the app UI. GET `/transcripts/<id>` and check `date`, `conversationType`, `folders`, and that `aiSummary`/`keyInsights` populated. Only if something didn't land, fix it in the app UI. Your folder IDs go in the table at the bottom of this file.

6. **Log it** in `context/log.md` (`INGESTED` the file + `SYNCED` the push).

7. **Pull to mirror.** Run `python skills/ferryman/pull.py --pull` from the brain root so the new app record lands in `pf-app-holon/transcripts/` (2-file mirror). Every push ends with a pull.

8. **Verify.** Run `python skills/ferryman/pipeline-verify.py` — it checks the invariants (raw ↔ report ↔ push-format ↔ mirror ↔ INDEX) and prints any discrepancy. A clean run is the definition of done; a dirty run gets fixed NOW, not flagged for later.

## Guardrails (do not skip)

- **Validate first. To CREATE, push with NO `id`; to FIX a record, re-push WITH its `id`.** **Upsert-by-id works**: re-pushing with the record's `id` UPDATES it in place (no duplicate); an unknown `id` returns 404 (never creates). But a push with **no `id` still CREATES** — so never re-push a correction without the id, or you get a duplicate your personal token can't delete (delete/patch need the app UI).
- **No admin key is needed for this flow.** If you find yourself reaching for one, you're solving the wrong problem.
- **One side processes each transcript** (the brain OR the app, not both) — don't double-process.
- **push.py does the summary push — never assemble the payload by hand.** `python skills/ferryman/push.py --push-summary transcripts/import-reports/import-checkup-<slug>-<date>.md --raw transcripts/<file>.txt [--id <uuid>] [--folder <folderId>] [--type "<type>"] [--date YYYY-MM-DD] [--dry-run]` assembles the step-4 markdown-with-sections payload from the report's 5-header core + the raw body, enforces the DUE rule in code (non-ISO dues and emoji in owner/due segments are STRIPPED with a warning, never pushed), always validates first, and pushes once (no `--id` = create, `--id` = upsert). Use `--dry-run` to see the would-be payload. The old raw modes (`--push`, `--file`) still exist for body-only backfills, but a summarized transcript goes through `--push-summary` — hand-assembled payloads are the known cause of zero-item pushes.

## Folder IDs (yours — fill this in)

Discover your folders: `GET /api/v1/projects` then `GET /api/v1/projects/:id/folders` (personal token). Keep your own table here so pushes can be foldered:

| Folder name | UUID |
|---|---|
| *(discover and record yours)* | |
