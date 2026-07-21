# pf-app-holon/ferryman-rules.md

**Holon:** PF App mirror
**Governs:** Ferryman behavior for this Holon only.
**Skill:** [[skills/ferryman/ferryman-skill.md]]
**Shipped:** 2026-07-20 rebuild — settled pipeline (push live via push.py, mirror pull, verify).

---

## Headline

**Transcript push is LIVE and routine** (markdown-with-sections via `POST /transcripts/import`). **The single canonical procedure for any transcript is [[skills/ferryman/transcript-intake-runbook.md]] — if this file and the runbook disagree, the runbook wins.** This file is the reference for the mirror mechanics, capability matrix, and corruption rules. The mirror itself is pull-populated only: mirror files are never a push source and never edited in place.

## The end-to-end transcript flow

> **The step-by-step runbook is [[skills/ferryman/transcript-intake-runbook.md]] — read that first for the actual do-this procedure.** This section is the reference model behind it.

1. **A transcript is processed by exactly ONE side** (peer-processor): either the PF App (you upload it there → the app extracts summary/decisions/action-items) OR your brain (you drop it into Claude → the transcript-processor extracts). Don't double-process.
2. **The processor RETAINS the per-transcript summary as an artifact.** App-side: it's on the conversation record. Brain-side: the retained artifact is `transcripts/import-reports/import-checkup-<slug>-<date>.md`, whose TOP is the push-mappable 5-header core (runbook step 2). Do NOT only fan the substance into cards and discard the clean summary — the report is what makes the transcript pushable later without re-extracting.
3. **Storage.** Raw transcripts live flat in `transcripts/` (brain origin) + are mirrored in `pf-app-holon/transcripts/` (app reflection). The APP is canonical for the transcript record; the brain mirror reflects it; `transcripts/INDEX.md` is the log.
4. **PULL (app → brain):** run `python skills/ferryman/pull.py --pull`. Mirrors new/changed transcripts + snapshots. Idempotent (UUID + `updatedAt`).
5. **PUSH (brain → app):** via `python skills/ferryman/push.py`. **If a per-transcript summary exists, push MARKDOWN-with-sections via `push.py --push-summary`** → the app FORMS the fields, no re-extraction; Action Items land "Pending Review" on the record's panel (**you approve in the app** → tasks). **Only push raw when there's no summary** (the app must then extract). id-less pushes get dedup-flagged, never silently duped.

**The one rule that prevents the classic mess:** whoever processes a transcript KEEPS its summary, and push sends that summary (markdown-sections) — so a transcript's derived fields are never empty and never re-extracted.

## Push/edit capability matrix — what can cross the boundary

The canonical list of what your brain may push/edit vs. what is read-only. Your personal token (`pf_tok_*`) only.

| Holon entity | Read | Create | Update | Endpoint | Corruption controls | Status |
|---|---|---|---|---|---|---|
| **Transcript / meeting** | ✅ | ✅ | ✅ (upsert by `id`) | `POST /transcripts/import` (+ `/import/validate`) | **validate before commit**; Action Items → "Pending Review" (first-create only; re-push does not re-materialize items); **nothing auto-commits** | LIVE |
| — folder membership on push | ✅ read | ✅ | ✅ | `POST /transcripts/import` | assign on import, multi-folder OK | LIVE |
| — id-less dedup | | ✅ | | `POST /transcripts/import` | id-less creates matched ±2-day + participant/title → `possibleDuplicate:true`; NEVER auto-merges; resolve in the app's review view. Upserts-by-id are NOT dup-checked. | LIVE |
| **Task** | ✅ | ✅ | ✅ (status/date) | `POST /tasks`, `PATCH /tasks/:id` | — | LIVE |
| **Profile observation/item** | ✅ | ✅ | — | `POST /profile/items` | lands "pending" for your approval | LIVE |
| **Meeting context (context document)** | ✅ (list + `/:id` body) | ❌ | ❌ | — | **READ-ONLY. The app is the sole writer.** | READ-ONLY |
| **Folders / projects** | ✅ | ❌ | ❌ | — | read structure only | READ-ONLY |
| **Contacts** | ✅ | ❌ | ❌ | — | — | READ-ONLY |
| **Presets** | ✅ | ❌ | ❌ | `GET /presets` | needed for Preset Parity | READ-ONLY |
| **Other users' data** | ❌ (personal token) | ❌ | ❌ | — | your token sees only YOUR data — by design | OUT OF SCOPE |

**Corruption-prevention principles (non-negotiable):**
1. **Mirror files in `pf-app-holon/` are never a push source and are never edited in place.** Pushes originate from brain synthesis → the app via the import endpoint. An in-place mirror edit changes nothing in the app and is silently lost on the next pull.
2. **Identity = UUID; conflict = `updatedAt` (last-write-wins).** Never push a stale record.
3. **Nothing auto-commits into app data** — action items land "Pending Review," observations "pending"; you approve.
4. **Read-only means read-only.** Do not attempt to push context documents / folders / contacts / presets — the write path does not exist.
5. **Validate before commit** (`/import/validate`) on every transcript push.
6. **Re-push a correction only WITH the record's `id`** — a push with no `id` creates, and your personal token cannot delete the resulting duplicate (app UI only).

### Two ways a push populates the derived fields (pick the right one)

1. **Markdown WITH sections** (`{"markdown": "---\nfrontmatter\n---\n## Summary\n…"}`) → the app **MAPS** those sections into fields: `## Summary → aiSummary`, `## Key Decisions` + `## Relationship Insights → keyInsights`, `## Action Items` lines → Action Items (Pending Review), `## Topics → tags`. **No extraction — it forms what's already there.** USE THIS when your brain already has a summary.
2. **Raw body, no sections** (JSON `transcript` = verbatim dialogue) → no `##` sections to map, so the derived fields land **EMPTY** and the app must extract them. Fallback for transcripts the brain never summarized.

**Verified API behavior:**
- Markdown-mode push honors frontmatter `date:`, quoted `conversationType:`, and `folders`.
- `POST /transcripts/import` **upserts by `id`**: an owned `id` UPDATES that record in place (no duplicate, `200 reimported`); an unknown `id` returns 404 (never creates); no `id` creates (`201 imported`) with id-less dedup flagging.
- **Your personal token cannot DELETE or PATCH a transcript** — a bad push is cleaned up in the app UI only. So: validate first, push once, upsert-with-id for corrections.
- A `## Topics` section populates the record's **`tags`** field — tags = topics; that's the intended home.

## 1. Holon identity

- **Name:** PF App mirror (`pf-app-holon/`).
- **Purpose:** Faithful on-disk reflection of YOUR PF App data (transcripts, tasks, contacts, projects, profile, presets, context documents) so your agent can read app state without API round-trips.
- **Source-of-truth claim:** The PF App is canonical for everything in this folder. This Holon is **derivative**. Brain-side synthesis (people cards, profiles, transcript reports) lives in the main brain (`transcripts/`, `people/`, `profiles/`) — NEVER in this folder.

## 2. Token + API mapping

- **Token:** `PF App API.txt` line 1 (brain root, local-only, never sync, never commit, never print). You mint it yourself in the app (Settings → API); it can only see YOUR data.
- **Auth:** `Authorization: Bearer <token>`. **Base URL:** `https://app.prospectforge.us/api/v1`.
- **Scope tier:** personal (`pf_tok_*`). Discovery (`GET /api/v1`) returns the `callableByYou` list for this token — trust it over any cached inventory.

## 3. Endpoint inventory (endpoint → file it feeds)

| Endpoint | Output file(s) | Pull behavior |
|---|---|---|
| `GET /api/v1` (discovery) | `.cache/api_v1.json` only | Validation step — confirms token + endpoint list |
| `GET /transcripts/tags` | `.cache/…` | The transcript LIST (misnamed path — returns transcripts, not tags). Diff source |
| `GET /transcripts/:id` | `transcripts/<slug>.txt` + `<slug>.json` | 2-FILE PATTERN, pulled per-UUID for new/changed; returns `folders[]` inline |
| `GET /profile/me` | `pf-app-profile-me.json` | Full snapshot overwrite |
| `GET /tasks` | `pf-app-tasks.json` | Full snapshot overwrite |
| `GET /contacts` | `pf-app-contacts.json` | Full snapshot overwrite |
| `GET /projects` | `pf-app-projects.json` | Full snapshot overwrite |
| `GET /presets` | `pf-app-presets.json` | The app's processing presets — needed for Preset Parity |
| `GET /context-documents` (+`/:id`) | `pf-app-context-documents.json` + `pf-app-context-<slug>.md` | One .md per context doc body |
| `GET /projects/:id/folders` | (your folder table in the runbook) | Discover your folder UUIDs |

**Raw responses** for every call land in `.cache/` (filename = endpoint path, `/` → `_`). `.cache/` never syncs anywhere.

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
- **People cards (`people/`) never push to the app** — brain-side only.

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

**Last touched:** 2026-07-20 rebuild: settled pipeline + people component; genericized from the reference implementation.
