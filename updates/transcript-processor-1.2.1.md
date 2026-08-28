# Transcript-Processor 1.2.1-mentee — owner rules, corrected push facts, Topics trap, verbatim check (2026-08-28)

**From 1.2.0-mentee.** Full replacement file at
`https://github.com/BigZCoda/pf-pack/tree/main/files/transcript-processor-1.2.1/transcript-processor-skill.md` — or apply the changes below to your copy, preserving any LOCAL ADAPTATION blocks.

**Apply to:** the `transcript-processor` skill file in this brain's `skills/transcript-processor/`. Merge — do not replace the file wholesale if you've adapted it.

## 1. NEW — OWNER RULES (the name pool is a closed set)

After the Due-field rules block, ADD the owner rules if not already present: the only values that resolve to a person are the self-references (`me`/`i`/`myself`/`self`/blank — all mean you) and an exact name from **your app's network contacts** (`GET /api/v1/contacts`). Your own items → `me`. Anyone else → their exact contact name, fullest variant. **Never a collective or placeholder** (`both`, `us`, `team`, `everyone`, `TBD`, `Unassigned`, or two names in one segment) — one item, one person; default move is to omit the segment. Not in your contacts → omit and note that a contact needs creating. The app's presets now state this rule themselves (fixed app-side, verified live 2026-08-25 — if your copy carries an "ignore the preset's Unassigned line" exception, retire it: follow the preset). Owner text is never validated at import and bad values permanently join the owner picker, so the enforcement is yours. Omitting isn't truly unassigned — a blank owner resolves to you.

## 2. CORRECTED — push facts

- Replace "personal tokens cannot delete or patch records" with: they **cannot delete** a transcript (a duplicate is permanent from your side), but they **CAN `PATCH /transcripts/:id`** — date, conversationType, and tags, without resending the body. Metadata mistakes don't need a re-push.
- Replace any "imported items land as `suggested` in `/tasks/import-review`" wording with the settled fact: **`## Action Items` lines land "Pending Review" on the record's Action Items panel** — you approve them in the app and they become your tasks.

## 3. NEW — the Topics silent-zero trap

Where the exact headers are described: `## Topics` must be `- ` bullet lines, one per line. A comma-separated Topics paragraph validates, pushes fine, and lands ZERO tags silently (fixable afterward via `PATCH /transcripts/:id {"tags":[...]}`).

## 4. NEW — verify verbatim, not notes (General Principles)

ADD as the first general principle: some recorders (Gemini among them) emit TWO files per meeting — the full verbatim transcript and a short auto-notes summary. Check file size against call length before processing (a 2-hour call is not 95 lines). Summarizing a summary silently poisons the record, the action items, and the people folds — if it looks like notes, ask for the verbatim export.

Bump to `1.2.1-mentee` in the skill frontmatter + the matching row in `skills/skill-registry.md`; log the update.
