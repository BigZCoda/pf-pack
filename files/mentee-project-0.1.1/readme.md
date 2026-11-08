# skills/mentee-project/ -- start a project and walk it through four steps on its ledger

**What's in here.**
- `mentee-project-skill.md`: the driver Claude follows. Trigger "start a project <name>" / "new project"; step 0 and the four steps (purpose, interviews, confines, outfitter), each with its prompt, result file and ledger task.
- `project.py`: the mechanical half. `start`, `finish`, `conversation`, `landed`, `ask`, `log`, `status`. Writes the ledger only through `skills/brain-tasks/tasks.py` and the log only through `skills/brain-log/log.py`; it takes no date argument anywhere.
- `prompts/`: the four step prompts (`mentee-project-purpose-prompt.md`, `mentee-project-interviews-prompt.md`, `mentee-project-confines-prompt.md`, `mentee-project-outfitter-prompt.md`).
- `check.py`: the folder's self-check. Compiles every `.py` here and scans every file for token values, a named program voice, and transcript line references. Run it before shipping a change: `python skills/mentee-project/check.py`.
- `component.json`: the pf-pack component record.

**Authoritative or derivative.** Authoritative for how a project is started and stepped through in this brain. The prompts are a cleaned-up copy of the program's step prompts (purpose feedback, interview planner, confines extractor, outfitter), with everything program-internal removed; a change to their substance comes from upstream, a change to how they run here is made here.

**When to read.** When the owner starts a project, asks where a project stands, or a transcript lands for a project. When changing what a step writes.

**When NOT to read.** For a single task or note that belongs to no project (use `tasks.py` directly), or for transcript processing itself (that is the transcript processor).

**What does NOT belong here.** Any project's own files (they live in `projects/<slug>/`), transcripts, keys or tokens, and anyone's answers.

**What it writes, per project.** `projects/<slug>/readme.md`, `<slug>-tasks.md` (the ledger), `<slug>-interviews.md` (the conversation list, links only), one result file per step (`<slug>-purpose.md`, `<slug>-interview-plan.md`, `<slug>-constraint-register.md`, `<slug>-stack.md`, written by Claude), and one row in `context/holon-registry.json` (created if the brain has none) so the Brain Viewer's `/projects` renders the ledger.

**The reporter.** Every `project.py` verb that writes appends one line to `context/log.md` through `log.py`, agent `mentee-project`, action CREATED (a project started, a step finished for the first time) or MODIFIED (a re-run, a partial result, a conversation, a question, a gate refusal), text `<file> -- <slug>: <what happened>`. The ledger writes that `tasks.py` makes log their own MODIFIED lines under the same agent.

**The PF App is not written, and why.** The plan was for each finished step to also create one task in the PF App ("<project>: purpose written") through the ferryman's `push.py` when the brain has a token. `push.py` (ferryman 1.3.0, the version in mentee brains) sends transcripts only: its verbs are a dry diff, `--push`, `--file` and `--push-summary`, all on the transcript import route, and it has no task route. The ferryman rules list a task create route in the app's capability matrix, but `push.py` does not call it and the rules do not describe its fields (including how a task is placed under a project), so this skill does not call it either. The log line is the only record. `project.py` checks whether the token file (`PF App API.txt` at the brain root, the path `push.py` uses) exists, never opens it, and prints which of the two reasons applies. To turn the app half on: a ferryman release that gives `push.py` a task verb, then one call to it inside `report()` in `project.py`.

**Fixed 2026-11-07: the tags and roles the ledger tool refused.** From 2026-10-16 `skills/brain-tasks/tasks.py` checks every tag and every owner against the two tables in `skills/brain-tasks/readme.md`, and neither table carried what this skill writes, so `start` stopped at its first step (the folder, its registry row and an empty ledger made, no step filed) and `ask` was refused for every role. The tables now carry `step` (and `step-*`) and `conversation`, and the four roles `@principal`, `@daily-user`, `@it` and `@tester`; the purpose step's words were changed so the ledger tool's text-to-judge warning no longer fires on it. Every verb (start, finish, conversation, landed, ask to a role, log, status) was run in a scratch brain built from the brain's own brain-tasks, brain-log and this folder on 2026-11-07. A named person in a project (`@jane-doe`) still needs a people card before a question can be addressed to them. A mentee brain gets the fix with the next pack release of brain-tasks and mentee-project 0.1.1.

**Naming.** The spec is `mentee-project-skill.md`; prompts are `mentee-project-<step>-prompt.md`; a project's files are `<slug>-<what>.md`.

**Last touched.** 2026-11-07 (0.1.1: the step, conversation and role labels the ledger tool refused; the purpose step reworded). Earlier: 2026-10-22 (the known gap found). Earlier: 2026-10-01 (created, 0.1.0; every verb tested in a scratch brain built from the brain-tasks and brain-log 0.48.0 that mentee brains carry: ledger `check` OK, log `--check` clean). First user: Kyle Collins's brain, first project a CPG reporting dashboard.
