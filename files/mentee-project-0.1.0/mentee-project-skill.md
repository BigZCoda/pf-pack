---
name: mentee-project
version: 0.1.0
description: >-
  Starts a project in this brain and walks it through four steps (purpose, interviews, confines, outfitter), each with its own prompt, a result file in the project's folder and a task on the project's ledger, so the ledger always shows where the project stands. Use when the brain's owner says "start a project <name>", "new project", or asks what the next step on a project is.
---

# mentee-project: start a project, then four steps on its ledger

> **Version:** 0.1.0 (2026-10-01) | **Runs in:** the owner's own brain with Claude Code. Needs `skills/brain-tasks/tasks.py` and `skills/brain-log/log.py`; nothing else.
> **The mechanical parts** (folders, ledger items, which step is open, the log line) are done by `skills/mentee-project/project.py`. **The thinking** is done by Claude running the step's prompt from `skills/mentee-project/prompts/`. Never hand-edit the ledger or `context/log.md`; never type a date.

## It is a guiderail, not a gate

The steps have an order because each one's output is the next one's input. The owner can still work on anything, in any order, inside or outside the steps: build a prototype, take a call, write code. Do not refuse work because a step is not finished. When the owner asks for a step out of order, run it, stamp its result **DRAFT** at the top with the reason (for example "purpose still ITERATE" or "2 of 4 conversations landed"), finish it with `--partial`, and say which earlier step will make it re-run.

## Words used here

- **Project folder:** `projects/<slug>/`, one per project. Holds `readme.md`, the ledger, the conversation list and one result file per step.
- **Ledger:** `projects/<slug>/<slug>-tasks.md`, written only through `tasks.py`. Rendered by the Brain Viewer at `/projects`.
- **Stakeholder roles:** principal (the person the product is for), daily user, IT, tester. A question goes to the role or the named person who can answer it, as `@principal`, `@daily-user`, `@it`, `@tester`, or their own `@first-last`. Questions only the owner can answer go to `@me`.

## Step 0: start the project

Trigger: "start a project <name>", "new project".

1. Ask for the project's name if it was not given, and for the assignment if there is one (a transcript in `transcripts/`, an email, notes). Do not ask for anything else yet.
2. Run from the brain root (on a Mac, `python3`):
   ```
   python skills/mentee-project/project.py start --name "<name>"
   ```
   It creates `projects/<slug>/` with `readme.md` and `<slug>-interviews.md`, adds the project to `context/holon-registry.json` so the viewer shows it, creates the ledger, and files the four step tasks: purpose open, the other three blocked "after <previous step>". It prints the slug; use it in every later command.
3. If there is an assignment transcript, add a link to it under **Pointers** in the project's readme. Link it; never copy it.
4. Tell the owner, in three lines: the folder, that the purpose step is open, and what you need from them for it (a draft purpose, any maturity).

**Worked when:** `python skills/mentee-project/project.py status <slug>` shows purpose open and the other three blocked.

## The four steps

Every step runs the same way:
1. Read the step's prompt in full and follow it exactly. Inputs are the files the prompt names; the earlier steps' result files are in the project folder.
2. Write the result to the step's file in the project folder (table below), in the prompt's output shape.
3. File every question the step could not answer alone with `project.py ask` (below), addressed to the stakeholder who holds the answer. One question per line, the sharpest one per gap.
4. Run `project.py finish <slug> <step>`. It checks the file exists, marks the step done with the file as its result, opens the next step, and writes the report line. Add `--status PASS` / `ITERATE` / `DRAFT` when the prompt produces one.
5. Tell the owner what was written, what is open now, and what the next step needs from them.

| Step | Prompt | Result file | Finished when |
|---|---|---|---|
| purpose | `prompts/mentee-project-purpose-prompt.md` | `<slug>-purpose.md` | the feedback is written. PASS or ITERATE both finish the step: ITERATE gaps become interview questions. Re-run it when the owner revises the purpose (`finish` again logs it as a re-run). |
| interviews | `prompts/mentee-project-interviews-prompt.md` | `<slug>-interview-plan.md` | the plan is written AND each planned conversation is on the ledger: `project.py conversation <slug> --who "<Name> (<role>)"` per conversation. A role with no named person becomes a task: `tasks.py add --file projects/<slug>/<slug>-tasks.md --owner @me --text "Find out who owns <role>" --agent mentee-project`. |
| confines | `prompts/mentee-project-confines-prompt.md` | `<slug>-constraint-register.md` | the register is written with every planned conversation landed. Until then, write it with what has landed and finish with `--partial`; re-run it each time a transcript lands. Its follow-ups go out as `ask` questions to the holders. |
| outfitter | `prompts/mentee-project-outfitter-prompt.md` | `<slug>-stack.md` | the recommendation is written past the prompt's gate. If the gate refuses, write nothing to the result file, report the refusal with `project.py log <slug> outfitter --text "refused at the gate, <n> of <m> conversations landed"`, and tell the owner which conversations are missing. A forced early run is written stamped DRAFT and finished with `--partial`. |

When a conversation's transcript lands in `transcripts/`, mark it:
```
python skills/mentee-project/project.py landed <slug> --who "<Name> (<role>)" --transcript transcripts/<file>
```
That closes the conversation task with the transcript as its result and adds the link to `<slug>-interviews.md`. Then offer to re-run the confines step.

## Questions

```
python skills/mentee-project/project.py ask <slug> --to @it --text "<the question>" --step confines
```
The question lands on the project's ledger, addressed to the stakeholder, and shows in the viewer at `/projects`. Never address a question to anyone outside the project's own stakeholders and the owner. When the owner brings back an answer, record it with `python skills/brain-tasks/tasks.py answer --file projects/<slug>/<slug>-tasks.md Q-000N --text "<answer>" --by @<who> --agent mentee-project`.

## Where the project stands

`python skills/mentee-project/project.py status <slug>` prints each step's state and result file, the conversations landed out of planned, and the open questions. It writes nothing. Run it whenever the owner asks "where am I on <project>" or comes back to a project after a break.

## What the project grows into

The four steps are the start. As the project grows, its folder is where everything it needs gets wired: new conversations go through `conversation` and `landed`, new questions through `ask`, new work as ordinary ledger tasks (`tasks.py add --file projects/<slug>/<slug>-tasks.md ... --agent mentee-project`), and anything that lives outside the brain (a repository, a shared drive, a dashboard) as one line under **Pointers** in the project's readme. This skill edits nothing outside the brain folder and nothing under `~/.claude`.

## The report line

Every `project.py` verb that writes appends one line to `context/log.md` as agent `mentee-project`, naming the project and the step (`<slug>: purpose written (ITERATE)`). That line is how the program sees whether the framework is being used; see `readme.md` for why it does not also write to the PF App yet. For a run that changed nothing on the ledger, write the line with `project.py log`.
