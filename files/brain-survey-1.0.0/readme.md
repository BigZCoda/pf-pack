# skills/brain-survey/ -- survey a person's existing files, then ingest them by type

**What's in here.** `brain-survey-skill.md` (the spec: survey, answers, ingest by type, with the prompt for each stage) and `survey.py`, which walks one or more folders and writes `survey-inventory-<date>.json` and `survey-<date>.md` into the brain's `inbox/`. It opens no file; it reads names, sizes and dates only.

**Authoritative or derivative.** Authoritative for how a brain is seeded from someone's own files. Built 2026-09-28 for Owen Koenigs's brain (the first case); copied into a brain before its first push, since it is not yet a pf-pack component.

**When to read.** When a new brain's owner arrives with existing material to bring in, or when changing what the survey counts or asks.

**When NOT to read.** For transcripts arriving one at a time after setup (that is the transcript processor), or for a brain with nothing to bring in.

**What does NOT belong here.** Anyone's survey output (it lives in that brain's `inbox/`), ingested files, keys or tokens, and per-person answers.

**Naming.** The spec is `brain-survey-skill.md`; the script is `survey.py`; its outputs are dated `survey-<date>.md` and `survey-inventory-<date>.json`.

**Last touched.** 2026-09-28 (created; tested on a scratch tree of 17 files with one fake repository and one fake Slack export).
