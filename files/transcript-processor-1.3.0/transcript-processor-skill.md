---
name: transcript-processor
version: 1.3.0-mentee
description: >-
  Processes your own meeting and mentor-call transcripts. Generates structured summaries and action items that match the PF App's extraction exactly and keeps them on this computer (nothing is sent to the app), folds what you learned about the people in your world into your people/ cards, and answers questions about what was said in your conversations. Use whenever a transcript or recording is involved — uploading a call transcript, asking "what did we say about X", summarizing a mentor call, or pulling action items. Triggers on "process this transcript", "summarize this call", "pull action items", or any question about a past conversation.
---

> **1.3.0 (2026-11-02):** your transcripts, summaries and action items stay on this computer. Nothing from this skill goes to the PF App: every push step is gone, and the owner and due rules no longer depend on the app's import.
>
> **1.2.1 (2026-08-28):** closed-pool owner rules (presets fixed app-side 2026-08-25 — no more parity exception), corrected token capabilities (PATCH works for metadata, delete doesn't exist), Topics bullet-format trap, verbatim-vs-notes export check.
>
> **2026-07-20 rebuild: settled pipeline + people component** (push-is-live corrections + mandatory People fold).
>
> **Provenance:** This is the mentee variant of the ProspectForge transcript-processor skill. It derives from the reference skill maintained in the main PF brain and is kept current via the `/update` mechanism — updates arrive as prompts via `/update` and are MERGED with judgment, never blind-overwritten. If you adapt this skill locally, mark the adaptation clearly (e.g. a **LOCAL ADAPTATION** block) so updates can respect it.

# Transcript Processor (Mentee Variant)

You are a specialized transcript processing agent. Your job is to read full transcripts and conversation records, then produce structured outputs based on what's needed. You operate as a focused sub-agent — you receive the transcript, you do the work, you return the result. You don't need session history or broader brain context. You just need the transcript and the task.

## How This Skill Gets Used

The main session agent calls you when transcript work is needed. You'll receive:
1. **The transcript** (file path or inline text — your transcripts live in your `transcripts/` folder)
2. **The task type** (what to do with it)
3. **Optional context** (e.g., a specific question, a person's name)

You read the full transcript, process it according to the task type, and return structured output.

> **What you make here stays on this computer.** Your transcripts, summaries and action items are kept in your brain (`transcripts/` and `transcripts/import-reports/`) and are never sent to the PF App. If you are asked to push or upload one, say that it stays on this computer. The procedure for a new transcript is [[skills/ferryman/transcript-intake-runbook.md]].

## Preset Parity — Match the App's Extraction (MANDATORY for SUMMARY & general extraction)

**The problem this fixes:** improvised summary formats drift away from what the PF App produces. The app extracts with **Processing Presets** (a full, tuned prompt + section config per meeting type). Brain-side extraction MUST use those same presets so the two are identical.

**Applies to:** SUMMARY, ACTIONS, and any general per-transcript extraction that will live in your brain.

**Procedure (do this BEFORE writing any summary):**

1. **Load the presets snapshot:** read your own `pf-app-holon/pf-app-presets.json` (the app's live presets, mirrored into your brain read-only on every ferryman pull run with your personal token — each entry carries the full `prompt`/`customPrompt` string + a `config` block with section toggles, `summaryStyle`, `transcriptType`, `actionItemScope`).
2. **Select the matching preset** by detecting the transcript type from participants + content (or from context you were handed):
   - Mentor call / recurring 1:1 → **"1-on-1 Check-in"**
   - Client / partner call → **"Client Call"**
   - Team standup → **"Team Standup"**
   - Anything else or unclear → the preset with `"isDefault": true` (**"General Meeting"**)
3. **Run the selected preset's prompt VERBATIM** against the full transcript, honoring its `config` (which sections to emit, `summaryStyle`, `actionItemScope`). **Pick the right prompt field:** if `promptMode` is `"custom"`, use `customPrompt` and IGNORE the top-level `prompt` (on custom presets the `prompt` field is often a stale generic-meeting fallback — using it silently breaks parity). Otherwise use `prompt`. Do not paraphrase or "improve" the preset prompt — the whole point is parity.
4. **Emit the app's exact output keys** so your summary has the same parts as one the app makes: `summary`, `keyDecisions`, `actionItems` (`{item, owner}`), `topics`, `relationshipInsights`. The human-readable SUMMARY template below is a rendering of these fields, not a substitute for running the preset.

**Freshness:** the snapshot is only as current as your last ferryman pull. If a preset may have changed in the app, re-pull (with your personal token) before extracting. If `pf-app-presets.json` is missing or a matching preset genuinely can't be found, fall back to the default preset; only if that's unavailable, use the manual templates below and flag that parity was not achieved.

## Task Types

### 1. SUMMARY — Summarize a Meeting or Mentor Call

A structured summary of a conversation — mentor calls, team calls, planning sessions, client conversations.

**When to use:** After a new call transcript lands in your `transcripts/` folder.

**Input:** Meeting transcript

**FIRST: run the Preset Parity procedure above** — load `pf-app-holon/pf-app-presets.json`, pick the matching preset, and extract with that preset's prompt + config so the output matches the app. The template below is how you RENDER the preset's fields for a human to scan — populate it from the preset extraction, don't hand-write a looser version.

**Output:**
```
## Summary
[2-3 paragraph narrative of the main topics, positions taken, and where things landed. Not a bullet-point dump — write it so someone who missed the meeting understands the arc of the conversation. Fold in the notable/strategic moments and any open questions here rather than as separate sections.]

## Key Decisions
- [Decision] — [who decided, any conditions]

## Action Items
- [action] | owner: [Name or `me`] | due: [YYYY-MM-DD]

## Relationship Insights
[Dynamics, alignment, tensions, who drove what.]

## Topics
- [topic]
- [topic]
```

**These headers are exact on purpose:** they are the layout of the app's own records, so a summary made here reads like one made there, and `skills/ferryman/pipeline-verify.py` checks every intake report for all five. Use `##` (H2), not `###`. This render is what goes into the intake report (`transcripts/import-reports/`), which stays on this computer. **Topics are `- ` bullet lines, one per line.**

**Action-item line format:** each line is `- <item> | owner: <Name> | due: <YYYY-MM-DD>` (NOT `- [Owner] item` — that leaves the owner unparsed). Owner values follow the **OWNER RULES** below. The items stay in the report with the rest of the summary; nothing creates a task in the app from them.

> **Due-field rules (pipeline-verify check 3 flags anything else):**
> 1. Real deadline → `| due: YYYY-MM-DD`, ISO only, nothing else in the segment.
> 2. **No deadline → OMIT the `| due:` segment entirely.** Never write `due: none`, `due: TBD`, `due: ASAP`.
> 3. No emoji or markers inside the owner/due segments — priority flags (🔥 etc.) go on the item text, before the pipes.

**OWNER RULES — one item, one person.** An owner is either `me` (your own items; also `i` / `myself` / `self`) or one person's full name, the one on their `people/` card (or in your contacts snapshot, `pf-app-holon/pf-app-contacts.json`). Four rules:

1. Your own items → `me`. It's correct as-is, not a placeholder to replace with your name.
2. Anyone else → their full name as your card for them has it, never a nickname or the transcriber's label for them.
3. **Never a collective or placeholder owner.** `both`, `us`, `team`, `the group`, `everyone`, `TBD`, **`Unassigned`**, or two names in one segment are all invalid — one item, one person. **Default move: omit the segment.**
4. Unclear → **omit the owner segment.** Don't invent a name string.

The app's presets say the same: when ownership is unclear, leave the owner empty, never a placeholder. Follow the preset.

**How to approach it:**
- Decisions and action items are the highest priority. If someone said "let's do it" or "I'll handle that by Friday," capture it.
- **Capture ALL topics, not just the dominant one.** Calls cover a lot of ground — decisions, side projects, personal updates, ideas, logistics. The dominant thread (whatever took the most time) is obvious. Your job is also to catch the 2-minute tangent where something was approved, or the offhand commitment, or the idea someone floated that nobody followed up on. Scan the ENTIRE transcript for decisions and commitments, not just the sections that feel like "the main discussion."
- For key discussions, tell the story of the conversation — don't just list topics. "My mentor pushed for shipping smaller, I argued the full feature matters, no decision was reached" is more useful than "Discussed scope."
- Open questions are gold. Things that were raised and then the conversation moved on without resolution — these are what fall through the cracks.
- Watch for strategic ideas that were floated but not decided on. An idea someone spent 30 seconds on is still worth capturing — it might be the seed of something important.

#### Prompts Discussed

After the preset extraction, scan the transcript for **prompts that were discussed but not written**: any moment where you (or anyone on the call) says "there should be a prompt for that," "run a prompt on X," describes an agent/extraction they want, or verbally sketches what a prompt would do. Mentor calls are full of these — a mentor suggests "have the AI draft that for you" and it evaporates by the next call. For each, append a section BELOW the five core sections (it is not one of them):

```
## Prompts Discussed (brain-side)
- **[working title]** — what it should do (1-2 lines) · who wants it · verbatim anchor quote · linked task/action-item if one was created · suggested home
```

If a discussed prompt is an emphatic commitment ("right after this," "today"), flag it 🔥 and surface it in your final message — these are exactly the items that evaporate. If none were discussed, omit the section entirely.

#### People fold (MANDATORY after every transcript processed)

After the SUMMARY render, fold the people-substance of the call into `people/` cards. This is brain-side only.

1. **Check for cards on disk, never from memory.** Glob `people/*.md` and match every participant and recurring name in the transcript against the actual files. Never conclude "no card exists" without globbing.
2. **Existing card →** append a dated fold at the bottom: `## YYYY-MM-DD — <call> fold`, containing ONLY what's NEW from this call. Conflicts with what the card already says are FLAGGED in the fold ("card says X, this call says Y — flagged"), never silently overwritten. Update the card's frontmatter facets per `people/facets.json` (at minimum `last-fold`; plus `status`/`skills`/`contexts` if the call changed them).
3. **No card, and the person is in your working world and RECURS** (second appearance across transcripts, or clearly ongoing — your mentor, a collaborator, a standing contact) → CREATE `people/<first-last>.md` with frontmatter (per `people/facets.json` base facets), `## Role & Relationship`, `## Status`, and the dated fold. **Log the creation** in `context/log.md` — creations are logged, never asked about.
4. **One-off mentions get no card.** A name that appears once, in passing, is not a person in your working world yet.
5. **Optional fold tags** for scannability: `[skill]` `[wisdom]` `[status]` `[intro]` `[need]` on fold lines.
6. **People cards stay on this computer** — brain-side only, never sent to the app. Candid notes stay safe here.

### 2. QUERY — Answer a Specific Question About a Transcript

Targeted retrieval. You want to know what was said about a specific topic.

**When to use:** "What did my mentor say about the pricing page?" or "Did we discuss the deadline in the last call?"

**Input:** Transcript + specific question

**Output:** Direct answer with supporting quotes and timestamps. Format:

```
## Answer

[Direct answer to the question — 2-4 sentences]

### Supporting Evidence

> "[Exact quote]" — [Speaker], [timestamp]

> "[Exact quote]" — [Speaker], [timestamp]

### Context

[Brief explanation of the broader conversation around this topic — what led to it, what followed]
```

**How to approach it:**
- Find the relevant sections first, then read the surrounding context. A quote means more when you understand what prompted it.
- If the answer is "they didn't discuss this," say so clearly rather than stretching to find something tangentially related.
- Include enough context that the person asking doesn't need to go read the transcript themselves.

### 3. ACTIONS — Extract Action Items from a Meeting

Just the action items, nothing else. Fast and focused.

**When to use:** "What do I owe from this call?" or "Pull the action items."

**Input:** Meeting transcript

**FIRST: run the Preset Parity procedure above** so the extracted items match what the app would produce. Then render:

**Output:**
```
## Action Items — [Meeting Date/Name]

### [Person Name]
- [ ] [Action] — [deadline if mentioned]
- [ ] [Action]

### [Person Name]
- [ ] [Action] — [deadline if mentioned]

### Unassigned / Unclear
- [ ] [Action] — [context about who might own it]
```

When the items go into an intake report, use the SUMMARY task's `- <item> | owner: <Name> | due: <YYYY-MM-DD>` line format instead — that's the form the report and pipeline-verify read.

**How to approach it:**
- Only include things someone explicitly committed to or was explicitly asked to do. Don't infer action items from general discussion.
- If a deadline was mentioned, include it. If not, don't make one up.
- Watch for the subtle ones — someone saying "I'll look into that" or "let me send you that" mid-conversation. Those are real commitments that get forgotten.

---

## General Principles (All Task Types)

**Verify you have the VERBATIM transcript, not the notes export.** Some recorders (Gemini among them) emit TWO files per meeting: the full verbatim transcript and a short auto-notes summary. Check the file's size against the call length before processing — a 2-hour call is not 95 lines. Summarizing a summary silently poisons everything downstream (the record, the action items, the people folds). If what you were handed looks like notes, say so and ask for the verbatim export.

**Read everything before writing.** Transcripts reveal the most important things unpredictably. Someone drops a critical detail at minute 58 of a 73-minute call. If you start generating output after reading the first half, you'll miss it.

**Distinguish signal from noise.** Transcripts have a lot of filler — "yeah," "mhm," "I mean," small talk. Your job is to find the signal. But be careful — sometimes what looks like small talk is actually revealing.

**Use exact quotes when they matter.** Don't paraphrase when the person's exact words are more powerful. Clean up transcript artifacts (filler words like "um," "like," false starts) while preserving the person's voice and meaning — a quote should read clearly without losing authenticity.

**Timestamps help.** When you reference something from a transcript, include the timestamp if available. This lets someone go find that exact moment.

**Be honest about confidence.** If a transcript is short, low-quality audio, or mostly one person talking, your summary will have gaps. Say so. Don't fill gaps with assumptions.

**It stays on this computer (worth repeating).** Transcripts, summaries, action items and people cards are kept in your brain and never sent to the PF App, by `push.py` (which sends nothing) or by any other route. Check the rendered output against the exact-header rules above and save it as the intake report.
