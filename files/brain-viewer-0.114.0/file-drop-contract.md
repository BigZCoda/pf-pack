# A file dropped on a page: the contract, and what the session does with it

**What this file is (2026-11-03, viewer 0.103.0).** The one place the rules for a file dropped on a page of the viewer live: where the viewer keeps it, what it writes beside it, the lines the session reads, and what the session does with each kind of file. The viewer's side is `part_drop.py`; the session's side is everything under "What the session does". It answers the owner's notepad note of 11/03, written after an onboarding application reached the session only because its path was dragged into a chat: a file dropped on the page it belongs to should land as part of what that page is about, and the system should work out what it is for.

**The split.** The viewer saves and labels a file, nothing more. It never reads a file to decide what it is, never files it, never runs a chain. The main session does that when the batch it rides in lands, using the label the page gave it.

## What the viewer writes

A file dragged onto any page (or picked with the **file** press in the notepad or in the Send press's note box) opens a small panel naming what the page is about, with a note box. **Add** writes:

- **The file:** `inbox/uploads/<yyyy-mm-dd-hhmm>-<its own name>`, the name kept readable (`application_182.txt` lands as `2026-11-03-1520-application_182.txt`; spaces and other signs become dashes). `inbox/` is the brain's in-flight drop zone: nothing in it is knowledge, and it is emptied as it is processed.
- **The sidecar:** the same path plus `.json`:

  ```
  {"file": "inbox/uploads/...", "name": "<the name as dropped>", "bytes": N, "droppedAt": "<ISO time>",
   "note": "<the person's words, or empty>", "batch": null | "<the batch it went in, YYYY-MM-DD HH:MM>",
   "page": {"route": "/call?prep=...", "kind": "...", "label": "<the page's subject in words>", "ref": "<what it points at>", ...}}
  ```

  The page's context is read from the page's own address on the server, never taken from what a page claims. `page.kind`, and what comes with it:

  | kind | the page | `ref` | also |
  |---|---|---|---|
  | `call` | a call page | the prep's path | `prep`, `date`, `meeting` (the calendar title), `people` [{name, slug, card}] |
  | `thread` | a thread page | the subject file | `subject`, `thread` (its short name) |
  | `item` | a thread or Today page opened on one item | `<holon> <id>` | `item` {project, id, ledger, text}; `subject` when it sits on a thread |
  | `project` | Projects, one project | the holon id | `project` |
  | `person` | People, one card open | the card's path | `people` |
  | `file` / `drawing` | the Reader / the Forge on one file | the file's path | `file` |
  | `today` | Today | empty | |
  | `page` | any other page | empty | only the route |

- **One log line** per file, `CREATED -- inbox/uploads/<leaf> -- file dropped on a page in the viewer: ...`. The log is the viewer's outbox, so the file joins the next answers batch the way a notepad note does.

**When it goes.** With *Hold a file I drop on a page until I send it* on (the Settings page; the default), a drop is one more press: it waits with the held answers and goes with the next Send, on leaving the viewer, or after the quiet minutes. Off, it goes at once in a batch of its own that holds the dropped files only, so answers being held stay held. With answers not held at all, a drop always goes at once. Until it has gone, **take it back** on the panel removes the file and its sidecar, and the session hears nothing of it.

## The lines in the batch (`context/answers-inbox.md`)

```
## Batch 2026-11-03 15:24 (2 answers)
- note for this batch · "<the person's words for the whole batch>"
- upload · 15:20 · on the call with Robin Ash on Tuesday 11/03 (deliverables/call-prep/robin-ash-call-prep-2026-11-03.md) · application_182.txt · note: "the application" · inbox/uploads/2026-11-03-1520-application_182.txt
- <an answer, done, hold or note line, as before>
```

- `- upload · <when> · on <label> (<ref>) · <file name>[ · note: "<the note>"] · <path>`: the `(<ref>)` is left out when the page points at nothing (Today), the note when none was written. The sidecar beside `<path>` has the rest.
- A batch that went at once for drops alone is headed `## Batch <stamp> (N file[s])`.
- `- note for this batch · "<words>"` is the first line under the header when the batch was sent with a note (a right-click on Send, a long press on a phone, or every press with *Ask for a note every time I press Send* on). It is about the whole batch, the drops and the answers both: read it before any other line and let it decide what the rest is for.

## What the session does

Read the batch note first, then each upload line with its sidecar. The page it was dropped on is the strongest clue to what it is for; the file's content decides what kind it is. Then, by kind:

1. **A call's transcript** (a `.txt`, `.md` or `.json` of speaker turns: a Gemini export, a Circleback file converted by its own rule, a plain transcript): through the brain's drop step, `/drop`, with the page's context. On a call page the call is the one it was dropped on: `python skills/import-checkup/intake.py "<path>" --source upload --prep <page.prep> --date <page.date> --meeting "<page.meeting>" --json` is the call page's own door and files it against that prep; then the import chain as the drop step says, from its first stage on. Anywhere else, `/drop "<path>"` reads the date from the file. A notes export is turned away by the drop step as always: say so in one line.
2. **An onboarding application export** (`application_<n>.txt`, the onboarding app's export of a website application, which the app's API does not serve): onto the person's people card as a dated section, `## [<day>] The application, #<n> [status]`, with its source line and what it says (education, work, now, wants, contact); and onto the call's prep, one line in its header that the application is on the card, and the points it changes under *Decide before* and *Updates to share*. The person is the page's: the call's one other participant, or the card that is open. Anywhere else, the name in the file against the people cards; a person being interviewed who has no card gets one before the interview; anyone else, ask once. The export itself is kept in the holon that mirrors the onboarding app, as `onboarding-app-holon/applications/<person-slug>-application-<n>.txt` (the folder made with its readme the first time).
3. **A picture**: into the `attachments/` folder beside the ledger of the item or the thread it was dropped on, and linked there as in 4.
4. **Any other document** (a PDF, a Word file, a spreadsheet, a page): moved to the folder whose contract takes it (`deliverables/` for something made for a person to read, the holon's `attachments/` for a reference) and linked where it was dropped: on an item with `python skills/brain-tasks/tasks.py link <id> <path>` (it adds); on a thread by adding the path to the subject file's `depends:` list, which the thread page draws under Documents; on a call as a line in the prep's header, and under *Updates to share* when it changes what is said; on a project, on the item the note names, else ask once; on Today, by what it is and the note, and ask once when neither says.

**After each one:**

- Move the file out of `inbox/uploads/` to its home and delete its sidecar; the folder is empty again when the batch is processed. A sidecar left behind means the file still waits.
- Under the batch, one processed line per upload: `processed: <date time> · upload · <one or two plain sentences to the owner on where it went>`. The `upload` in front keeps the clause off the cards of the other items in the batch. Example: `processed: 2026-11-03 15:30 · upload · The application is on Robin's card, and today's prep has its two changes under Decide before.` What the session did, step by step, goes in the log line, not here.
- Log what moved (`MODIFIED`, or `INGESTED` for a transcript) through `skills/brain-log/log.py`.

## What this is not

- Not the call page's transcript box: that box files a transcript at once through `intake.py`, before any batch. A transcript dropped anywhere else on the call page comes here, and the session files it with the same call's context.
- Not the notepad's pictures: a picture dropped in the open notepad still goes with the note. A file that is not a picture, dropped there, comes here.
- Not a team copy in propose mode: it sends nothing to a session, so the panel is not drawn and `POST /api/upload` answers 403.
