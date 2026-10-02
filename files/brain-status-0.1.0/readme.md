# skills/brain-status/ -- one read of what a brain has, what version it runs, and what is switched on

**What's in here.** `brain-status-skill.md` (the spec: triggers, what each field of the JSON means, how rounds and a mentee's session start call it), `status.py` (the check itself; writes `context/brain-status.json` and one log line), `check.py` (compiles the script, runs it read-only against a mentee brain and against an empty folder) and `component.json` (version 0.1.0, the pack shape).

**Authoritative or derivative.** The script is authoritative for how a brain's state is read. Its output, `context/brain-status.json`, is a dated snapshot: true as of its `_generatedAt`, never a current-state source after that.

**When to read.** When asked "check my brain" or "what version am I on", at Zak's rounds, at a mentee's session start, or when changing what the check reports.

**When NOT to read.** To apply an update (that is `skills/update/`), or to find out what happened in a session (that is the log and `context/active-session.md`).

**What does NOT belong here.** Any brain's `brain-status.json` (it lives in that brain's `context/`), the manifest cache (`context/.pack-manifest-cache.json`), and token or key files, which the check notes by presence only and never opens.

**Naming.** The spec is `brain-status-skill.md`; the script is `status.py`; the self-check is `check.py`.

**Last touched.** 2026-10-01 (created; tested on Zak's brain, on the kyle-brain clone read-only, and on an empty folder).
