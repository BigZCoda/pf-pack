# Transcript Intake Runbook — the ONE process for handling a transcript

> **1.3.0 (2026-09-03):** the step-4 example no longer shows a `source` key (the API rejects it; every 1.2.0 push failed at validate because push.py sent it), and participants now ship via `--participants`. Before reporting that any field is empty or a count is zero, print the response's keys — a field that is not on that endpoint looks exactly like real emptiness.

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

2. **Extract it — using the app's presets (Preset Parity).** Do NOT improvise a format. Load `pf-app-holon/pf-app-presets.json`, pick the preset matching the transcript type, and run its prompt verbatim (see [[skills/transcript-processor/transcript-processor-skill.md]] "Preset Parity"). Write the result under the exact core headers: **`## Summary`**, **`## Key Decisions`**, **`## Action Items`** (one per line as **`- <item> | owner: <Name> | due: <YYYY-MM-DD>`** — owner/due optional, due ISO-only; see step 4), **`## Relationship Insights`**, **`## Topics`** (⚠️ Topics as `- ` bullet lines, one per line — a comma-separated Topics paragraph validates, pushes 201, and lands ZERO tags silently; fixable post-hoc via `PATCH /transcripts/:id {"tags":[...]}`). Save as `transcripts/import-reports/import-checkup-<slug>-<date>.md` — it is what gets pushed (no re-extraction). **NEVER save intake reports to `deliverables/`** — deliverables/ is for human-facing deliverables only; the intake report is pipeline ledger and lives with the raws + INDEX. pipeline-verify check 7 enforces this.

3. **Fold the substance** into the relevant `people/` cards and any open threads (dated fold at the bottom of each card — see the "People fold" section of the transcript-processor skill).

4. **Push to the app — validate, then push, via push.py ONLY.** Endpoint `POST /transcripts/import` (base `https://app.prospectforge.us/api/v1`, `Authorization: Bearer <PF App API.txt line 1>`). `push.py --push-summary` assembles the **markdown-with-sections** payload from the report core:
   ```json
   {"markdown": "---\ntitle: <Title>\ndate: <YYYY-MM-DD>\nconversationType: \"<type>\"\nparticipants:\n  - <Full Name>\n  - <Full Name>\n---\n## Summary\n<summary>\n\n## Key Decisions\n- <d>\n\n## Action Items\n- <item> | owner: <Name> | due: <YYYY-MM-DD>\n\n## Topics\n- <t>\n\n## Transcript\n<raw body>", "folders": ["<folderId>"]}
   ```
   The app maps `title` + `## Summary`→aiSummary + `## Key Decisions` (+ `## Relationship Insights`)→keyInsights + **`## Action Items` lines→Action Items on the record, landing "Pending Review" (you approve in the app → approved tasks)** + `## Topics`→tags, stores the body, and stores `date`, quoted `conversationType`, `participants`, and `folders`. **This is the design and it works.** ⚠️ **Do NOT send a `source` key** — the import schema rejects it `422 Unrecognized field(s): source` and the server sets it itself. push.py sent it until 1.3.0, so every 1.2.0 push failed at validate with nothing visible to you; if your pushes have been "not landing", this is why.

   **DUE rule (one bad due kills the ENTIRE item batch server-side):** `| due: YYYY-MM-DD` ISO only; **no real deadline → OMIT the `| due:` segment** — never `due: none`/`TBD`/`ASAP`; no emoji inside owner/due segments (🔥 goes on the item text). push.py strips violations with a warning.

   **OWNER rule — the owner pool is a CLOSED SET:** your app's network contacts (`GET /api/v1/contacts`) plus the self-references. Nothing else resolves to a person.
   - Your own items → `me` (also accepts `i`/`myself`/`self`, or blank). Correct as-is; do not "improve" it into a name.
   - Anyone else → an **exact name from your contacts pool**, fullest variant when duplicates exist (`owner: Sarah Chen`, not `owner: Sarah`).
   - **NEVER a collective or placeholder owner.** `both`, `us`, `team`, `the group`, `all`, `everyone`, `TBD`, **`Unassigned`**, or two names in one segment are invalid. **One item = one person.**
   - **Unclear, collective, or not in the pool → OMIT the `| owner:` segment** and flag the missing contact in the report. Do not invent a name. Only split an item per-owner when it genuinely divides *and* both people are real contacts.
   - **Omitting ≠ unassigned:** a blank owner resolves to the token user, so the item becomes yours. Accepted tradeoff — a recoverable item in your own queue beats silent junk that also pollutes the owner picker.
   - ✅ **The app's presets now state this rule themselves** (fixed app-side, verified live 2026-08-25): when ownership is unclear, leave `owner` EMPTY — never `Unassigned` or any placeholder. Preset and brain rule agree, so follow the preset — but the rules above are still yours to enforce, because of the next bullet.
   - ⚠️ **Owner text is never validated at import.** The segment is stored verbatim — no error, no write-time fuzzy match. And the owner picker is built from contacts **plus any owner string already on an item**, so one bad value joins the suggestion list permanently and invites reuse. Unlike the DUE rule, nothing downstream catches this for you.
   - ⚠️ **`conversationType` MUST be quoted** in the frontmatter (`"1:1"`) — an unquoted `1:1` breaks YAML and the type falls back to "Other".
   - ✅ Trust the response code: create returns `201 imported`, upsert returns `200 reimported`.
   - **`## Topics` populates the app's `tags` field** — tags = topics, so that's the intended home (not a gap). Keep the `## Topics` header (it's the verified parse key that fills `tags`).

5. **Confirm it landed (GET the record).** The push sets date/type/folder, so you usually do NOT need the app UI. GET `/transcripts/<id>` and check `date`, `conversationType`, `folders`, and that `aiSummary`/`keyInsights` populated. If metadata didn't land right, fix it with **`PATCH /transcripts/:id`** (date / conversationType / tags, without resending the body — THE correction path); folder membership moves via `POST /transcripts/:id/folders/move`. Your folder IDs go in the table at the bottom of this file.

6. **Log it** in `context/log.md` (`INGESTED` the file + `SYNCED` the push).

7. **Pull to mirror.** Run `python skills/ferryman/pull.py --pull` from the brain root so the new app record lands in `pf-app-holon/transcripts/` (2-file mirror). Every push ends with a pull.

8. **Verify.** Run `python skills/ferryman/pipeline-verify.py` — it checks the invariants (raw ↔ report ↔ push-format ↔ mirror ↔ INDEX) and prints any discrepancy. A clean run is the definition of done; a dirty run gets fixed NOW, not flagged for later.

## Guardrails (do not skip)

- **Validate first. To CREATE, push with NO `id`; to FIX a record's content, re-push WITH its `id`.** **Upsert-by-id works**: re-pushing with the record's `id` UPDATES it in place (no duplicate); an unknown `id` returns 404 (never creates). But a push with **no `id` still CREATES** — so never re-push a correction without the id, or you get a duplicate your personal token can't delete (there is no transcript-delete route for a personal token; cleanup needs the app). **Metadata mistakes don't need a re-push at all:** `PATCH /transcripts/:id` fixes date / conversationType / tags in place.
- **Participants (LIVE since 1.3.0):** `push.py --participants "Full Name,Full Name"` writes a `participants:` YAML **list** into the frontmatter — the only accepted form (a top-level `participants` JSON key is rejected 422 like `source` was). The app stores them and never overwrites a push-supplied list; once its contact-sync build is deployed it matches each one to your contacts and links the conversation. Rules: **participants only, never mentions** (people in the room, a small closed set you know before processing; people merely talked about get nothing); **canonical contact names, not transcriber labels** (speaker strings are speech-recognition output — resolve `Speaker 2` / a mangled surname to the exact contact name first); **read the import response's `contacts` block** when present (`matched / created / ambiguous / skipped / enrichmentQueued`): `ambiguous` means a participant matched two or more contacts and was linked to **none** — it drops silently unless you look.
- **No admin key is needed for this flow.** If you find yourself reaching for one, you're solving the wrong problem.
- **One side processes each transcript** (the brain OR the app, not both) — don't double-process.
- **push.py does the summary push — never assemble the payload by hand.** `python skills/ferryman/push.py --push-summary transcripts/import-reports/import-checkup-<slug>-<date>.md --raw transcripts/<file>.txt [--id <uuid>] [--folder <folderId>] [--type "<type>"] [--date YYYY-MM-DD] [--participants "A,B"] [--title "<title>"] [--base <url>] [--dry-run]` assembles the step-4 markdown-with-sections payload from the report's 5-header core + the raw body, enforces the DUE rule in code (non-ISO dues and emoji in owner/due segments are STRIPPED with a warning, never pushed), always validates first, and pushes once (no `--id` = create, `--id` = upsert). Use `--dry-run` to see the would-be payload. The old raw modes (`--push`, `--file`) still exist for body-only backfills, but a summarized transcript goes through `--push-summary` — hand-assembled payloads are the known cause of zero-item pushes.

## Folder IDs (yours — fill this in; ⚠️ treat it as a cache)

Discover your folders: `GET /api/v1/projects` then `GET /api/v1/projects/:id/folders` (personal token). Keep your own table here so pushes can be foldered — but the folder list grows in the app without this file knowing, so **fetch the live folder list at push time** and treat this table as a cache, not a fact:

| Folder name | UUID |
|---|---|
| *(discover and record yours)* | |
