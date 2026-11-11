# Ferryman 1.4.0 — nothing goes to the PF App; your calls, transcripts and summaries stay on this computer (2026-11-02)

## What this means for you (read this first; your Claude applies the rest)

**Why it changed.** On 10/30 the ProspectForge team decided that PF does not collect your calls, transcripts or summaries: they stay on your own computer. The companies you work in are careful about where their information goes, and keeping your work on your machine means nothing from it reaches anyone unless you choose to send it. What PF receives is what you fill in and send yourself, such as your check-ins.

**How you work from now on, if you have been sending your calls to the PF App:**
- Keep recording and processing your calls the way you do now. The summary, the decisions and the action items are written into your brain, under `transcripts/import-reports/`, and you read them in your viewer. They no longer appear in the PF App.
- A call's action items stay in that call's report in your brain. Nothing waits for review in the app any more.
- The PF App still works for you: your check-in forms and the tasks PF gives you are there as before, and your app token keeps working for them.
- If you or your Claude try to send a call to the app, you see "Nothing sent: your transcripts and summaries stay on this computer." That is expected.
- Calls you already sent to the app before this update stay there, and you can open them in the app whenever you like. To bring copies back into your brain, ask your Claude to pull them (`python skills/ferryman/pull.py --pull`); each one lands in `pf-app-holon/transcripts/`.

**From 1.3.1.** Full replacement files at
`https://github.com/BigZCoda/pf-pack/tree/main/files/ferryman-1.4.0/`. `pull.py` and `ferryman-adapter-contract.md` are unchanged in this release.

**Apply to:** `skills/ferryman/push.py` (required, replace whole), `skills/ferryman/transcript-intake-runbook.md` (required), `skills/ferryman/ferryman-skill.md` (required), `skills/ferryman/pipeline-verify.py`, `pf-app-holon/ferryman-rules.md`. Replace `push.py` whole even if you adapted it. Merge the three docs, keeping your own LOCAL ADAPTATION blocks, except any block that sends something to the app: drop those.

## 1. REQUIRED — push.py sends nothing

ProspectForge no longer collects mentees' transcripts or summaries: what you record and process stays on your own computer. `push.py` 1.4.0 sends nothing. Run in any way, with any arguments, it prints one line and exits 0:

```
Nothing sent: your transcripts and summaries stay on this computer.
```

It opens no token file and makes no network call. Its old modes (`--push-summary`, `--push`, `--file`) are gone; a script or note that still calls them gets that line instead of an error.

Confirm after replacing it:
```
python skills/ferryman/push.py
```
It prints the line above and nothing else.

## 2. REQUIRED — the intake runbook has no push

`transcript-intake-runbook.md` is five steps now: file the raw transcript, extract it with the app's presets, fold the people, log it, verify. The push, the check that a push landed and the pull after it are removed, and so is the folder-ID table (it served pushes only). A new row in `transcripts/INDEX.md` has `| file | date | type |`; if your INDEX has a `pushed` column, keep it and leave it empty on new rows.

If you are asked to push or upload a processed call to the app, the answer is that calls, transcripts and summaries stay on this computer. Do not write a request to the app's API by hand instead.

## 3. pipeline-verify.py no longer expects a pushed record

Check 4 (every `SYNCED` push in `context/log.md` has a mirror record) is retired; the other checks keep their numbers and their meaning. `BRAIN_ROOT` in the environment overrides the brain root, as it does for the other two scripts. Run it once after the update:
```
python skills/ferryman/pipeline-verify.py
```

## 4. ferryman-skill.md and ferryman-rules.md

- `ferryman-skill.md`: two modes, STATUS and PULL, both read-only; the PUSH mode and the participants section are removed; frontmatter `version: 1.4.0`.
- `pf-app-holon/ferryman-rules.md`: the push/edit capability matrix and the push and correction sections are replaced by one table of what crosses the boundary: app to brain, read by `pull.py`; brain to app, nothing. The mirror sections (naming, the 2-file pattern, idempotency, the log format) are unchanged; keep your own filled-in values in them.

## 5. Your app token: nothing to do

If `PF App API.txt` at your brain root holds your personal token, leave it where it is: `pull.py` still uses it, read-only, to refresh the app's presets (the transcript processor extracts with them), your contacts and what is already in your account. `push.py` no longer opens it. With no token file, nothing changes either. Records already in your app account are not touched by this update.

## 6. Other lines in this brain that say transcripts go to the app

Search this brain's own text for lines saying a transcript, summary or action item is pushed or sent to the app (`WHAT-YOU-GET.md` at the brain root says so in several places; a procedure, readme or CLAUDE.md line you wrote may say it too) and change them to say these stay on this computer. Leave `pull.py` and anything that only reads from the app as they are.

Bump the skill frontmatter to `1.4.0` + the matching row in `skills/skill-registry.md`; log the update.
