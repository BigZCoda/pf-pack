# transcript-processor 1.0.1 — due-field rules (data-loss fix)

**What this fixes:** a formatting pattern in Action Items lines that makes the PF App silently drop EVERY action item in a pushed transcript. A push on 2026-07-17 lost all 15 of its items this way. The fix is three format rules; nothing else about the skill changes.

**Apply to:** the `transcript-processor` skill file in this brain's `skills/transcript-processor/` (whatever its exact filename is here). Merge — do not replace the file. Preserve any LOCAL ADAPTATION blocks.

## The change

Find the section that defines the Action Items line format (`- <item> | owner: <Name> | due: <YYYY-MM-DD>`). Immediately after the owner-format guidance, ADD this block if it is not already present:

> **Due-field rules (v1.0.1 — a violation makes the app drop EVERY item in the push, silently):**
> 1. Real deadline → `| due: YYYY-MM-DD`, ISO only, nothing else in the segment.
> 2. **No deadline → OMIT the `| due:` segment entirely.** Never write `due: none`, `due: TBD`, `due: ASAP`.
> 3. No emoji or markers inside the owner/due segments — priority flags (🔥 etc.) go on the item text, before the pipes.

Then update the skill's `version:` header line to `1.0.1` (keep any local suffix, e.g. `1.0.1-mentee`) and the matching row in `skills/skill-registry.md`.

## Why (one paragraph, for the curious)

The app maps each `| due:` value into a strict date column. A non-date string ("none") or a decorated date ("2026-07-17 🔥") fails that column, and the failure takes the whole batch of items down with it after the transcript itself has already saved — so the transcript looks fine but has zero tasks. Omitting the segment is safe: undated items import as undated.
