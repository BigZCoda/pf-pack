# pf-app-holon/ferryman-rules.md

**Holon:** PF App mirror
**Governs:** Ferryman behavior for this Holon only.
**Skill:** [[skills/ferryman/ferryman-skill.md]]
**Shipped:** 2026-07-20 rebuild. **Updated 2026-11-02 (ferryman 1.4.0):** nothing is sent from this brain to the app; the mirror is pulled read-only. Earlier updates (1.2.0, 1.3.0, 1.3.1) were about the push, which is gone.

## Current truth (read this first; 1.4.0)

- **Nothing goes from this brain to the PF App.** Your calls, transcripts and summaries stay on this computer: no transcript text, no summary, no action item, by any script or by hand. `push.py` sends nothing; run in any way it prints *Nothing sent: your transcripts and summaries stay on this computer.*
- **The one connection is a read.** `pull.py` makes GET calls only, with your personal token, and mirrors what is already in your account into this folder.
- **Print the response keys before reporting any negative.** A field that is not on that endpoint returns nothing and looks like real emptiness.
- Capability questions: live `GET /api/v1` → the `_fetchedAt`-stamped catalog (say its date) → this file, in that order. The catalog lists routes your token could write to; this brain calls none of them.

---

## Headline

**This folder is a read-only mirror of your PF App account.** The single canonical procedure for any transcript is [[skills/ferryman/transcript-intake-runbook.md]] — file, extract, fold, log, verify, all on this computer. This file is the reference for the mirror mechanics. The mirror itself is pull-populated only: mirror files are never edited in place.

**Capability questions get answered from the app, not from prose.** `GET /api/v1` is self-describing (it returns `callableByYou` for your token); every pull also snapshots it to `pf-app-holon/pf-app-api-catalog.json`, stamped `_fetchedAt`. Trust the live call first, the stamped snapshot second (say its date out loud when you cite it), this file third. A snapshot is not a fact — check the stamp.

## The transcript flow

> **The step-by-step runbook is [[skills/ferryman/transcript-intake-runbook.md]] — read that first for the actual do-this procedure.** This section is the reference model behind it.

1. **Your brain processes your transcripts.** You drop a call into Claude, the transcript-processor extracts it with the app's presets, and the report is kept in `transcripts/import-reports/`. Nothing of it goes to the app.
2. **The report is the record.** `transcripts/import-reports/import-checkup-<slug>-<date>.md` holds the 5-header core (runbook step 2). Do NOT only fan the substance into cards and discard the clean summary.
3. **Storage.** Raw transcripts live flat in `transcripts/`. `pf-app-holon/transcripts/` mirrors what is already in your app account, if anything; `transcripts/INDEX.md` is the log.
4. **PULL (app → brain, read-only):** run `python skills/ferryman/pull.py --pull`. Mirrors new/changed transcripts + snapshots + the API catalog. Idempotent (UUID + `updatedAt`).

## What crosses the boundary

| Direction | What | How | Status |
|---|---|---|---|
| **App → brain** | transcripts already in your account, tasks, contacts, projects, profile, presets, context documents, the API catalog | `pull.py` (GET only) | LIVE |
| **Brain → app** | nothing | — | OFF: no transcript, summary, action item, task, contact, project or profile item is sent |

**Mirror principles (non-negotiable):**
1. **Mirror files in `pf-app-holon/` are never edited in place.** An in-place mirror edit changes nothing in the app and is silently lost on the next pull.
2. **Identity = UUID; conflict = `updatedAt`.** The app's copy always wins inside this folder.
3. **Read-only means read-only.** No POST, PATCH, PUT or DELETE to the app from this brain.

## 1. Holon identity

- **Name:** PF App mirror (`pf-app-holon/`).
- **Purpose:** Faithful on-disk reflection of YOUR PF App data (transcripts, tasks, contacts, projects, profile, presets, context documents) so your agent can read app state without API round-trips.
- **Source-of-truth claim:** The PF App is canonical for everything in this folder. This Holon is **derivative**. Brain-side synthesis (people cards, profiles, transcript reports) lives in the main brain (`transcripts/`, `people/`, `profiles/`) — NEVER in this folder.

## 2. Token + API mapping

- **Token:** `PF App API.txt` line 1 (brain root, local-only, never sync, never commit, never print). You mint it yourself in the app (Settings → API); it can only see YOUR data.
- **Auth:** `Authorization: Bearer <token>`. **Base URL:** `https://app.prospectforge.us/api/v1`.
- **Scope tier:** personal (`pf_tok_*`). Discovery (`GET /api/v1`) returns the `callableByYou` list for this token — trust it over any cached inventory, including this file.

## 3. Endpoint inventory (endpoint → file it feeds)

| Endpoint | Output file(s) | Pull behavior |
|---|---|---|
| `GET /api/v1` (discovery) | `pf-app-api-catalog.json` + `.cache/root.json` | The app's self-describing catalog, `_fetchedAt`-stamped — refreshed on every pull; THE capability source |
| `GET /transcripts/tags` | `.cache/…` | The transcript LIST (misnamed path — returns transcripts, not tags). Diff source |
| `GET /transcripts/:id` | `transcripts/<slug>.txt` + `<slug>.json` | 2-FILE PATTERN, pulled per-UUID for new/changed; returns `folders[]` inline |
| `GET /profile/me` | `pf-app-profile-me.json` | Full snapshot overwrite |
| `GET /tasks` | `pf-app-tasks.json` | Full snapshot overwrite |
| `GET /contacts` | `pf-app-contacts.json` | Full snapshot overwrite |
| `GET /projects` | `pf-app-projects.json` | Full snapshot overwrite |
| `GET /presets` | `pf-app-presets.json` | The app's processing presets — needed for Preset Parity |
| `GET /context-documents` (+`/:id`) | `pf-app-context-documents.json` + `pf-app-context-<slug>.md` | One .md per context doc body |

**Raw responses** for every call land in `.cache/` (filename = endpoint path, `/` → `_`; the API root caches as `root.json`). `.cache/` never syncs anywhere.

### The 2-file transcript pattern

For each mirrored transcript, exactly two files sharing one slug:

- **`<slug>.txt`** — the raw transcript body, nothing else.
- **`<slug>.json`** — everything else the API returned: id (UUID), title, date, status, source, conversationType, tags, participants, `aiSummary`, `keyInsights`, `actionItems`, `folders[]`, timestamps.

**No third file. No `-summary.md` in the mirror.** The app's `aiSummary` already lives in the `.json`; brain-side synthesis lives elsewhere.

### Naming convention (globally unique leaf filenames)

- **Slug:** `<first-last>-<conversation-type>-<YYYY-MM-DD>`. first-last = first non-self participant (set your name in pull.py's `SELF_NAMES`); type falls back to a title fragment when the API says `Other`.
- **Collision guard:** if the leaf name already exists in main `transcripts/`, prefix with `pf-app-`. Snapshot files are always prefixed.
- **Identity is the UUID, not the filename.** The slug is presentation; diff/idempotency runs on the `id` field inside each `.json`. Files may be renamed without breaking sync.

## 4. Scope + limits

- Your token sees: your own data + transcripts shared with you (`accessVia: "uploader" | "shared"`). Mirror both, preserve `accessVia` in the `.json`.
- Admin-only endpoints are out of scope; a 401/403 from them is EXPECTED, not an error.
- **Volume guard:** a single PULL mirrors at most 12 new transcripts (most recent first). The remainder goes to `pf-app-holon/transcripts/pull-backlog.md`; the next PULL continues from there.

## 5. Conflict resolution

App always wins inside this folder. Mirror files are never edited in place — local edits are silently lost on the next pull and the app never learns of them. If app data is wrong, fix it in the app and re-pull. (Brain wins on brain-side synthesis — but that lives outside this folder by definition.)

## 6. Privacy

- Transcripts contain real people and full conversation bodies. Never quote them into anything shared without your explicit choice.
- `PF App API.txt` never syncs, never gets committed, never gets quoted in any document.
- `.cache/` never syncs anywhere.
- **Nothing from this brain goes to the app** — transcripts, summaries, action items and `people/` cards stay on this computer.

## 7. Idempotency contract

- Pull twice → identical end state. Transcript diff is UUID-based: "new" iff its `id` appears in `/transcripts/tags` but in no mirror `.json`; "changed" iff mirrored `updatedAt` < API `updatedAt`. Re-pulling an unchanged transcript overwrites with identical content.
- Snapshot files (`pf-app-*.json`) are deterministic full overwrites.
- Renamed mirror files do NOT cause re-pulls (UUID is read from every `.json`).

## 8. Audit log format

Every Ferryman run appends to `context/log.md` per the Agent Tracking Contract (CLAUDE.md), agent-id `[ferryman]`:

- Per new mirrored transcript: `[YYYY-MM-DD HH:MM] [ferryman] INGESTED pf-app-holon/transcripts/<slug>.txt -- <title> (<date>, <n> action items)`.
- **Batching rule:** if a single PULL mirrors more than 5 transcripts, write ONE INGESTED line listing all slugs.
- Run summary: `[YYYY-MM-DD HH:MM] [ferryman] PULL -- N transcripts mirrored, M backlogged, snapshots refreshed`.
- STATUS mode (report-only) logs nothing unless it finds an error worth flagging.

---

**Last touched:** 2026-11-02 (ferryman 1.4.0): nothing is sent from this brain to the app; the push sections, the push/edit capability matrix and the correction paths removed; the mirror is read-only. Previous: 2026-09-03 (ferryman 1.3.0), 2026-08-28 (ferryman 1.2.0), 2026-07-20 rebuild, genericized from the reference implementation.
