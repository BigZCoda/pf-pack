# Your brain, part by part

Each part in a few paragraphs: what it is, where you see it, and what to say to Claude about it.

[Back to the start](/reader?path=skills%2Fbrain-viewer%2Fguide%2Fbrain-guide-start-here.md)

## Today

Today is the page the viewer opens on, and the one place where you answer, finish or put off what is yours. It reads your task lists, so nothing on it is typed twice.

From the top: **Up first** holds the one to three items to do or answer now, each with a line on why it is up there. **Due today** and **New since you last looked** sit side by side. Everything else of yours is folded under **Backlog** with its count, and what you put off is under **On hold**, with the day each item comes back. **Closed today**, near the bottom, lists what you finished or answered, each with an undo for the rest of the day.

A task has three buttons: **done**, **hold** and **note**. A question has a button for each answer, or a box to write your own. Every button you press is written into your brain right away, and Claude sees it the next time it reads your lists.

## People

Your brain keeps a card for each person you work with, in the `people` folder: who they are, what they care about, what you have talked about, and what is open between you.

Claude makes and updates the cards from your calls. After a call it folds in what changed, and it makes a new card the second time someone shows up. You can also tell it what you learned: **add to her card that she prefers email**.

The **People** page shows every card, what is open that concerns each person, and the calls you have had with them. Before a call, ask Claude what you should know about the person. It answers from the card and your past calls.

## Projects and tasks

Your work is kept as task lists, one per project. A list holds tasks (things to do, each with who it is for and, if it has one, a due date) and questions (things someone needs to answer). Claude writes to the lists with a small tool, so every change is dated and logged. You work them from Today and from the **Projects** page, which shows one project at a time.

Your brain starts with one project, **Getting started**, which holds your first-week list once setup has run. Ask for a task in plain words: **add a task to call the caterer Thursday**.

When you are given an assignment, say **start a project** followed by its name. Claude walks you through four steps, each ending in a file: what the project is for, who you need to talk to, the limits you work within, and the tools to build it with. Each conversation you plan becomes a task, and questions for the people involved go on the project's list.

A piece of work that runs across projects can have its own page on **Threads**: where it stands, its files and its open questions.

## Calls and transcripts

Most of what your brain knows comes from your calls. Save a call's transcript as a text file in the `transcripts` folder and say **process the newest transcript**. You get a summary, the key decisions, the action items with owners and dates, the topics, and what the call says about the people on it. The report is saved beside the transcript, and the people's cards are updated.

Use the full transcript, not the short notes some tools make beside it. A summary of a summary loses most of what was said.

After that you can ask about any call: **what did we decide about the venue?** Claude answers from the transcript itself, not from memory. The action items stay in the call's report until you say **put my action items on my task list**.

## Asking Claude

Claude is the assistant that works inside your brain. Open a terminal in the brain folder, type `claude`, and talk to it in plain words. It follows the rules in `CLAUDE.md` at the top of the folder, reads a folder's readme before working in it, and writes one line to the brain's log for every change it makes, so you can always see what it did.

It learns how you work. When you correct it, say **remember that**: it writes the correction into `CLAUDE.md` with the date, and every later session follows it.

Things worth knowing how to say:

- **survey my files**: counts what you have elsewhere on your computer by type, size and date, without opening anything, then asks you about it one question at a time.
- **ingest the next type**: brings one kind of material into your brain, after telling you how much and where it goes and waiting for your yes. The originals stay where they are.
- **process the newest transcript**, **start a project**, **start the viewer**.
- **commit and push**: saves your brain to its backup. End every session with it.
- **check for updates**: once a week.

## What stays on your computer

Everything in your brain stays on your computer: your transcripts and notes, the people cards, your projects and task lists, what you build, and the log. Your brain sends nothing to ProspectForge, and ProspectForge has no access to your brain or to its backup.

Four things cross the edge of your computer, each on purpose:

- **Claude.** To answer you, Claude sends what it reads to Anthropic, the company that runs it, under the account you sign in with.
- **The backup.** **Commit and push** saves your brain to its own private repository. Where that repository lives is agreed with your company.
- **Updates.** New versions of the viewer and the tools come from ProspectForge's public kit, and only after your yes. Checking for one sends nothing about you.
- **Your check-ins.** The forms ProspectForge sends you as links, which you fill in yourself.

The `thoughts` and `questions` folders are for your own thinking.

An update replaces the viewer's own folder, `skills/brain-viewer`, whole, so don't keep changes of yours there. What you set up yourself (your settings and your own pages) lives in the `viewer` folder, which no update touches.
