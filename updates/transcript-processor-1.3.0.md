# Transcript-Processor 1.3.0-mentee — summaries stay on this computer (2026-11-02)

## What this means for you

Your calls, transcripts and summaries now stay on your own computer, and the summaries and action items you make here are never sent to the PF App. The ferryman 1.4.0 note says why, and how you work from now on.

**From 1.2.1-mentee.** Full replacement file at
`https://github.com/BigZCoda/pf-pack/tree/main/files/transcript-processor-1.3.0/transcript-processor-skill.md` — or apply the changes below to your copy, preserving any LOCAL ADAPTATION blocks, except any block that sends something to the app: drop those.

**Apply to:** the `transcript-processor` skill file in this brain's `skills/transcript-processor/`. Merge — do not replace the file wholesale if you've adapted it. Apply it together with ferryman 1.4.0, which makes `push.py` send nothing.

## 1. REQUIRED — remove every push step

ProspectForge no longer collects mentees' transcripts or summaries: your transcripts, summaries and action items stay on this computer.

- Under "How This Skill Gets Used", REPLACE the "Pushing results to your PF App account?" block with: what you make here stays on this computer; transcripts, summaries and action items are kept in `transcripts/` and `transcripts/import-reports/` and are never sent to the PF App; if asked to push or upload one, say that it stays on this computer.
- SUMMARY: REPLACE "These headers are exact on purpose — they are what the app import maps ... this render IS the push payload ..." with: the headers are the layout of the app's own records, so a summary made here reads like one made there, and `pipeline-verify.py` checks every intake report for all five; the render goes into the intake report, which stays on this computer; Topics are `- ` bullet lines, one per line. Remove the `PATCH /transcripts/:id` fix.
- Action-item line format: REMOVE the "Pending Review" sentence and the re-push sentence; the items stay in the report, and nothing creates a task in the app from them.
- Prompts Discussed: the section sits below the five core sections; its heading becomes `## Prompts Discussed (brain-side)`.
- People fold, rule 6: people cards stay on this computer, never sent to the app. Remove the line about card-sharing arriving later.
- ACTIONS: REPLACE "If the items will be pushed to the app, use the SUMMARY task's line format" with "When the items go into an intake report, use the SUMMARY task's line format".
- General Principles: REPLACE "Push discipline (worth repeating)" with "It stays on this computer (worth repeating)": transcripts, summaries, action items and people cards are kept in your brain and never sent to the PF App, by `push.py` (which sends nothing) or any other route; check the render against the exact-header rules and save it as the intake report.

## 2. CHANGED — owner and due rules no longer depend on the app's import

- OWNER RULES: an owner is `me` (your own items) or one person's full name, the one on their `people/` card or in your contacts snapshot `pf-app-holon/pf-app-contacts.json`. Never a collective or placeholder (`both`, `us`, `team`, `TBD`, `Unassigned`, two names in one segment); when it is unclear, leave the owner segment out. REMOVE the paragraphs about the app's owner picker and about owner text not being validated at import.
- Due-field rules: unchanged (ISO `YYYY-MM-DD` only, left out when there is no real deadline, no emoji); the reason is now that `pipeline-verify.py` check 3 flags anything else.

## 3. UNCHANGED

Preset Parity (the presets still come from your app account, read-only, through the ferryman's `pull.py`), the five core headers, the People fold, the verbatim-versus-notes check, QUERY and ACTIONS.

Bump to `1.3.0-mentee` in the skill frontmatter + the matching row in `skills/skill-registry.md`; log the update.
