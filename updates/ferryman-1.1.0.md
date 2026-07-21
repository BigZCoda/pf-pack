# Ferryman 1.1.0 — settled pipeline (2026-07-20)

**From 1.0.0.** Apply by replacing files, then verifying. Preserve any LOCAL ADAPTATION blocks you have added.

## What changed and why
1. **push.py now does summary pushes** (`--push-summary <report> --raw <transcript>`): assembles the markdown-with-sections payload from your intake report's 5-header core, enforces due-date hygiene in code (bad `due:` values are stripped with a warning — one bad due kills the app's whole item batch server-side), validates first, pushes once. Hand-assembled payloads are retired.
2. **Action Items are SETTLED:** your report's `## Action Items` lines push as-is and land "Pending Review" on the record's Action Items panel in the app — you approve them there and they become your tasks. Do not rename, fold, or gate this.
3. **Intake reports live in `transcripts/import-reports/`** — never `deliverables/` (that folder is for things made FOR a human). `pipeline-verify.py` check 7 enforces this.
4. **pipeline-verify.py added** (runbook step 8): checks raw → report → push-format → mirror → INDEX after every intake. A clean run is the definition of done.
5. **ferryman-rules.md now ships** at `pf-app-holon/ferryman-rules.md` (the ferryman skill requires reading it; it was previously referenced but missing).
6. **Upsert works:** re-push WITH the record's `id` updates in place; a push with no `id` creates. Never re-push a correction without the id.

## Apply
Replace these files in your brain with the 1.1.0 versions from
`https://github.com/BigZCoda/pf-pack/tree/main/files/ferryman-1.1.0/`:
- `skills/ferryman/push.py`, `pull.py`, `pipeline-verify.py`, `transcript-intake-runbook.md`, `ferryman-skill.md`
- `pf-app-holon/ferryman-rules.md`

Then: create `transcripts/import-reports/` if absent (move any `import-checkup-*.md` you have in `deliverables/` into it), fill in YOUR folder table in the runbook (discover via `GET /api/v1/projects/:id/folders` with your token), and run `python skills/ferryman/pipeline-verify.py` — it must print PIPELINE CLEAN. Log the update in `context/log.md` and bump ferryman to 1.1.0 in `skills/skill-registry.md`.
