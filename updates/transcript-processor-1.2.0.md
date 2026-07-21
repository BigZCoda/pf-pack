# Transcript-Processor 1.2.0-mentee — People fold + settled push facts (2026-07-20)

**From 1.0.1-mentee.** Full replacement file at
`https://github.com/BigZCoda/pf-pack/tree/main/files/transcript-processor-1.2.0/transcript-processor-skill.md` — or apply the two changes below to your copy, preserving any LOCAL ADAPTATION blocks.

## 1. NEW — People fold (mandatory after every SUMMARY)
Your brain's `people/` folder is where your understanding of the people in your world accumulates. After the preset extraction, ALWAYS:
1. List every named participant + recurring person in the transcript.
2. **Glob `people/*.md` and match against the actual file list** — never conclude "no card" from memory.
3. Card exists → append a dated fold at the bottom (`## YYYY-MM-DD — <call> fold`): only what's NEW versus the card; if the transcript CONTRADICTS the card, flag the conflict, never silently overwrite. Update the card's frontmatter facets per `people/facets.json`.
4. No card, and the person is part of your working world AND recurs (second appearance, or clearly ongoing) → CREATE `people/<first-last>.md` with frontmatter + Role & Relationship + Status + the fold, and add a log line for the creation. One-off mentions get no card. Never ask permission — creations are logged so you can prune.
5. Optional fold tags collect the fundamentals: `[skill]` `[wisdom]` `[status]` `[intro]` `[need]` `[private]`.
6. **People cards NEVER push to the app** — brain-side only.

## 2. CORRECTED — push facts
- Re-push WITH a record's `id` UPDATES it in place (upsert works). The old "re-push always duplicates" claim is wrong — only id-LESS re-pushes create duplicates.
- `## Action Items` lines push as-is and land "Pending Review" in the app — you approve → they become your tasks. This is the design; do not rename the header.

Bump to 1.2.0-mentee in the skill frontmatter + `skills/skill-registry.md`; log the update.
