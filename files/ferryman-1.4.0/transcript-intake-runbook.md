# Transcript Intake Runbook — the ONE process for handling a transcript

> **1.4.0 (2026-11-02):** nothing goes to the PF App any more. Your calls, transcripts and summaries stay on this computer. The push step, the check that a push landed and the pull after it are gone, and `push.py` sends nothing: run in any way it prints one line, *Nothing sent: your transcripts and summaries stay on this computer.* The five steps below are the whole process.
>
> **1.3.0 (2026-09-03):** before reporting that any field is empty or a count is zero, print the response's keys — a field that is not on that endpoint looks exactly like real emptiness.

## THE SYSTEM (read this before anything else)
1. **Raw transcript** → filed in `transcripts/`, processed ONCE, here.
2. **The summary** (summary, key decisions, action items, relationship insights, topics) → the intake report in `transcripts/import-reports/` (pipeline ledger — NEVER `deliverables/`). The report is the record of the call.
3. **Action items** stay in the report with the rest. Nothing creates a task in the app from them.
4. **People understanding** → folds into your `people/` cards.
5. **Everything stays on this computer.** No transcript text, no summary and no action item is sent to the PF App, by `push.py` or by any other route.

> This is THE canonical procedure for what to do when you hand over a call transcript. If any other doc disagrees, this wins for the intake flow. The mirror of what is already in your app account (pulled read-only by `pull.py`) is described in [[pf-app-holon/ferryman-rules.md]].

## When this runs
You drop (or point at) a **call/meeting** transcript and want it processed. **Calls/meetings only — never texts or chats.**

## The 5 steps (do ALL of them, in order)

1. **File the raw transcript** into `transcripts/` with a globally-unique name: `<who>-<type>-<YYYY-MM-DD>.txt` (e.g. `mentor-checkin-2026-08-03.txt`). Add a row for it to `transcripts/INDEX.md` (create the file with a simple `| file | date | type |` table if it doesn't exist yet; an older INDEX with a `pushed` column keeps it, and new rows leave it empty).

2. **Extract it — using the app's presets (Preset Parity).** Do NOT improvise a format. Load `pf-app-holon/pf-app-presets.json` (a read-only copy of the app's presets, refreshed by `pull.py --pull`), pick the preset matching the transcript type, and run its prompt verbatim (see [[skills/transcript-processor/transcript-processor-skill.md]] "Preset Parity"). Write the result under the exact core headers: **`## Summary`**, **`## Key Decisions`**, **`## Action Items`** (one per line as **`- <item> | owner: <Name> | due: <YYYY-MM-DD>`** — owner and due optional; due is ISO only, and with no real deadline the `| due:` segment is left out), **`## Relationship Insights`**, **`## Topics`** (`- ` bullet lines, one per line). Save as `transcripts/import-reports/import-checkup-<slug>-<date>.md`. **NEVER save intake reports to `deliverables/`** — deliverables/ is for human-facing deliverables only; the intake report is pipeline ledger and lives with the raws + INDEX. pipeline-verify check 7 enforces this.

3. **Fold the substance** into the relevant `people/` cards and any open threads (dated fold at the bottom of each card — see the "People fold" section of the transcript-processor skill).

4. **Log it** in `context/log.md`: one `INGESTED` line for the transcript and its report.

5. **Verify.** Run `python skills/ferryman/pipeline-verify.py` — it checks the invariants (raw ↔ report ↔ INDEX, due format, no token strings, no report in `deliverables/`) and prints any discrepancy. A clean run is the definition of done; a dirty run gets fixed NOW, not flagged for later.

## Guardrails (do not skip)

- **Nothing goes to the app.** Do not send a transcript, a summary or an action item to the PF App: `push.py` sends nothing, and a request written by hand to the app's API is not a way around it. If you are asked to push or upload a processed call to the app, say that calls, transcripts and summaries stay on this computer.
- **Your app token, if you have one,** is used only by `pull.py`, which reads from the app and never writes to it.
- **The verbatim transcript, not the notes export.** Some recorders (Gemini among them) emit two files per meeting: the full transcript and a short auto-notes summary. Check the file's size against the call's length before processing; if it looks like notes, ask for the verbatim export.
- **One transcript, one report.** Process each transcript once; a second pass rewrites the same report rather than making a new one.
