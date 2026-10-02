---
name: brain-survey
version: 1.0.0
description: >-
  Seeds a new brain from a person's existing files in two stages: a survey that counts their files by type without opening any, with a question for everything the count raises, and then an ingest that takes one type at a time in the order the answers allow. Use when someone arrives with a year or more of their own material (documents, notes, transcripts, exports, code) and says "survey my files", "what do I have", or "start the ingest".
---

# brain-survey: survey first, then ingest by type

> **Version:** 1.0.0 (2026-09-28) | **Built for:** Owen Koenigs's brain, the first brain seeded from a person's own year of files; written to work for anyone after him.
> **Runs in:** the person's own brain, on their own machine, with their own Claude Code. Nothing in it calls an app or needs a key.

## Why two stages

Reading everything at once fills the brain with material nobody chose, and the person cannot see what was taken. The survey shows what exists from names, sizes and dates alone; the person decides what counts; the ingest does only what the answers allow. The survey is also the step every later brain reuses.

## Words used here

- **Brain:** this folder. Plain files, read and written by Claude Code, versioned in a private GitHub repository.
- **Project folder:** a folder under `projects/` for one area of work (a client, a role, a build). The brain's older name for it is *holon*; both mean the same thing.
- **Pointer:** one line in a project's readme saying where something lives outside the brain and what it is for. The thing itself is not copied.
- **Ingest:** copying a file into the brain and filing it where it belongs. The original is never moved, renamed or changed.
- **People card:** one file per person in `people/`, named `first-last.md`.

## Stage 1: the survey

```
python skills/brain-survey/survey.py <folder> [<folder> ...]
```

On a Mac, `python3`. Options: `--out DIR` (default: this brain's `inbox/`), `--top N` (how many of the biggest folders to ask about, default 15).

It walks each folder and records file types with counts, total size and date range; the folders holding the most files; code repositories (any folder with a `.git` inside, counted and not walked further); exports recognized by their layout (Slack: `channels.json` beside `users.json`; Notion: names ending in a 32-character id, or an `Export-` folder; Google Takeout: a `Takeout` folder or `archive_browser.html`; email: `.mbox`, `.pst` or twenty or more `.eml` files; an Obsidian vault: a `.obsidian` folder). It skips tooling folders (`node_modules`, caches, virtual environments, system folders) and hidden folders.

**It never opens a file.** It lists names and reads sizes and dates. The inventory records `filesOpened: 0`, and the last line printed says so.

It writes two files into `inbox/`:
- `survey-inventory-<date>.json`: the numbers.
- `survey-<date>.md`: a table of what is there, one numbered question per thing the inventory raises, each with the default that applies if it is left blank and an `Answer:` line, and a proposed ingest order by type.

The questions: which big folders are live and which are finished; what each repository is for (the brain points at repositories and never copies them); which exports to ingest, point at or skip, and which part; which transcripts, contacts and email are his to ingest; whether any skipped kind (images, video, audio, archives, installers) holds real work; and what the brain must never read.

**Prompt the person pastes:**

```
Run python skills/brain-survey/survey.py on my Documents, Desktop and Downloads folders, and on my Google Drive or OneDrive folder if this computer has one. Do not open any of my files. Tell me the line it prints and the name of the survey file it wrote.
```

**Worked when:** the printed line ends `0 files opened` and `inbox/survey-<date>.md` exists.

## Stage 2: answering

**Prompt:**

```
Take me through inbox/survey-<date>.md one question at a time. Read me the question and its default, write my answer on its Answer line, and move to the next. When we reach the end, read back every answer in one list.
```

**Worked when:** every `Answer:` line in the file has an answer or the word `default`.

## Stage 3: ingest, one type at a time

Rules for every type:
1. Do one type at a time, in the survey's proposed order, and report before starting the next.
2. Copy; never move, rename or edit the original.
3. Take only what the answers allow. A folder answered *finished* gets a pointer only. Anything under a folder answered *never read* is left alone.
4. Log each file created with `python skills/brain-log/log.py --append --agent claude-code --action INGESTED --text "<path> -- <what it is>"`.
5. Push nothing to any app. This brain has no app connection until its owner sets one up.
6. Commit and push the brain at the end of each type.

Before the first type, create the project folders: one per folder answered *live*, `projects/<name>/` with a `readme.md` saying what the area is, and a **Pointers** section listing the finished folders, repositories and exports that belong to it.

**Prompt to start any type** (replace `<type>`):

```
Using skills/brain-survey/brain-survey-skill.md, ingest the <type> the answers in inbox/survey-<date>.md allow. Tell me how many files that is and where they will go before copying anything, and wait for my yes.
```

What happens to each type:

| type | what the brain does with it |
|---|---|
| transcripts | Each call is copied into `transcripts/`, then the transcript processor (`skills/transcript-processor/`) writes its summary and action items beside it and adds what it learned about each person to their people card, asking before it creates a new card. Ask it: *Process the transcripts in transcripts/ with the transcript processor. Summaries and action items only, nothing pushed to any app.* |
| notes (`.md`, `.txt`) | Copied into the project folder of the area they belong to, found from the folder they came from; notes that fit no project go to `inbox/` and are listed for the person to place. |
| documents (`.docx` and similar) | Copied into the project folder, with a three-line summary at the top of a sibling `.md` so the brain can search it. |
| contacts (`.vcf`, contact lists) | Never bulk-created. Claude lists the names; the person picks the people they actually work with; each gets a card in `people/` in the shape `people/readme.md` describes. Check with `python skills/people-adapter/people.py --verify` (it reports every card that does not parse). |
| email | Only threads the person names, saved as notes in the project they concern. Whole mailboxes are never ingested. |
| spreadsheets, slides, data | A pointer and a one-line description in the project's readme; copied only when a project needs the numbers. |
| pdfs | Copied when they are the person's own work or a reference a project uses; otherwise a pointer. |
| repositories | A pointer in the project's readme: path, remote URL if it has one, one line on what it is for. The code is never copied; Claude Code opens the repository itself when work there is needed. |
| exports (Slack, Notion, Takeout) | Only the parts the answers name (a channel, a set of pages, a label), filed as notes in the project they concern; the rest of the export gets a pointer. |
| images, video, audio, archives, installers | Skipped. A folder of brand or design assets gets a pointer from the project that uses it. A call recording is transcribed first and then handled as a transcript. |

**Worked when**, for each type: the count Claude reported equals the files that landed, `context/log.md` has one INGESTED line per file, and the push succeeded.

## What this skill does not do

It does not read files during the survey, create people cards without the person's pick, import a repository, connect any app, or decide what is live. The person decides; the answers file is the record of it.
