# Ferryman 1.2.0 — PATCH correction path, API catalog, owner rules, Topics trap (2026-08-28)

**From 1.1.0.** Full replacement files at
`https://github.com/BigZCoda/pf-pack/tree/main/files/ferryman-1.2.0/` — or apply the changes below to your copies, preserving any LOCAL ADAPTATION blocks and your own filled-in folder table. `push.py` is unchanged in this release.

**Apply to:** `skills/ferryman/` (skill doc, `pull.py`, `transcript-intake-runbook.md`, `ferryman-adapter-contract.md`) and `pf-app-holon/ferryman-rules.md`. Merge — do not blind-replace anything you've adapted.

## 1. CORRECTED — your token CAN fix metadata (it still cannot delete)

Everywhere your copies say a personal token "cannot delete or patch" a transcript: still true for delete (a duplicate is permanent from your side), **no longer true for patch**. `PATCH /transcripts/:id` changes a record's `date`, `conversationType`, and `tags` WITHOUT resending the body — it is THE correction path for metadata mistakes; content corrections still re-push WITH the record's `id`. Folder membership also moves via `POST /transcripts/:id/folders/move` (and `DELETE /transcripts/:id/folders/:folderId` removes membership only — never the transcript).

## 2. NEW — pull.py refreshes the app's self-describing API catalog

Update `pull.py` from the 1.2.0 file (two changes: a `refresh_endpoint_catalog()` function hooked into `refresh_snapshots()`, and the API-root cache naming fix). Every pull now writes `pf-app-holon/pf-app-api-catalog.json` from `GET /api/v1`, stamped `_fetchedAt`. Rule that comes with it: **capability questions ("can my token do X?") get answered from the live API root or that stamped catalog — never from prose.** Check the stamp before trusting it.

## 3. TIGHTENED — the owner pool is a closed set

In the runbook's step 4, replace the old loose OWNER rule ("free text the app fuzzy-matches... blank defaults to you") with: the pool is **your app contacts (`GET /api/v1/contacts`) plus the self-references (`me`/`i`/`myself`/`self`/blank = you)**; anyone else gets their exact contact name (fullest variant); NEVER a collective or placeholder (`both`, `team`, `TBD`, `Unassigned`, two names in one segment); unclear or not-in-pool → OMIT the `| owner:` segment and flag the missing contact. Omitting resolves the item to you — the accepted tradeoff. The app's presets now state this rule themselves (fixed app-side, verified 2026-08-25), but owner text is never validated at import, so the enforcement is still yours.

## 4. NEW — the Topics silent-zero trap

In the runbook's step 2 (and anywhere the 5 headers are listed): `## Topics` must be `- ` bullet lines, one per line. A comma-separated Topics paragraph validates, pushes 201, and lands ZERO tags with no error. Fixable post-hoc via `PATCH /transcripts/:id {"tags":[...]}`.

## 5. DOCUMENTED — participants ship as a known gap

The import endpoint accepts `participants[]` and never overwrites a push-supplied list (the design: your brain resolves who's who, the app never guesses) — but `push.py` does not send participants yet. Note it as a known limitation; do NOT hand-assemble a payload to force it. Related caution: `POST /contacts` matching is exact-name only, not nickname-aware — resolve to the exact existing contact name before creating one, or you mint duplicates.

## 6. Smaller merges

- Capability matrix in `ferryman-rules.md`: tasks gained `DELETE /tasks/:id` (your own items); projects/folders/contacts gained CREATE routes (`POST /projects`, `POST /projects/:id/folders`, `POST /contacts`) — edit remains admin-only.
- Your folder-ID table is a **cache**: the folder list grows in the app without the file knowing, so fetch the live list at push time.
- Adapter contract: the filename-collision prefix belongs in the adapter, not the engine (wording refresh).

Bump the skill frontmatter to `1.2.0` + the matching row in `skills/skill-registry.md`; log the update.
