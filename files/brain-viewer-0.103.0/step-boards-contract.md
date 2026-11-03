# Step boards — the contract

A **step board** is a process drawn in the Forge as steps in order, with each step's documents, video and form hanging under it. The files are the record and the drawing is their view: the viewer redraws the drawing from the files every time it opens in the Forge, so attaching something is one line in a markdown file. Code: `part_board.py` (the server reads it), `board.py` (the terminal), `form.html` (the form page), `board.test.py`.

## The folder

One folder under the Forge's root (`forge_root` in the settings), holding:

| File | What it is |
|---|---|
| `<slug>-board.md` | The order of the steps, and the board's name and intro. |
| `<slug>.canvas` | The drawing, written by the viewer from the files. Never edit it by hand: the next read redraws it. |
| one `.md` per step | What happens at that step, its files, its video, its form. |

Leaf names stay unique across the brain, so name step files `<slug>-<step>.md`, numbered when the order matters to a reader (`client-onboarding-3-the-call.md`).

## The board file

```markdown
---
board: The client onboarding
kind: steps            # steps: one line, in order · funnels: several ways in, one end
up: client-path.canvas        # optional: the drawing this one sits under
---

# The client onboarding

One or two lines on what the board shows. They head the drawing.

## Steps
1. [[client-onboarding-1-event-form]]
2. [[client-onboarding-3-the-call]]
```

A **funnels** board names lanes instead, each a `###` heading with its steps listed under it, then the one step every lane ends at, and optionally what comes after it:

```markdown
## Lanes
### The card handed out
- [[event-booth-card]]
- [[event-booth-score]]
### At the booth
- [[event-booth-screen]]

## Ends at
- [[client-onboarding-1-event-form]]

## Then
- [[client-onboarding.canvas]] · the call, and what follows it
```

A step can sit on more than one board: here the event booth ends at the client onboarding's first step.

## A step file

```markdown
---
step: The call          # the tile's name (else the H1, else the file name)
status: live            # live (green) · planned (orange) · maybe (yellow)
who: the owner and the client
when: once the event form is in
---

# The call

The first paragraph is the tile's summary.

## Files
- [[docs/call-script.md]] · the questions for the call

## Video
- Answers the questions every client asks; sent ahead of the call     ← a line with no link is a slot, drawn "not made yet"

## Form: Tell us about your company
1. Name #short #required
```

A link can be a `[[wikilink]]` (a brain path, or a leaf name), a `[words](path)` or a path in backticks; anything after ` · ` is its note. When the video is made, the link replaces the slot line (`board.py link <step> <video> --video` does it).

## A form

The questions under the step's `## Form` heading (one per step; `## Form: <title>` names it). Each is a numbered line with its tags at the end:

| Tag | Drawn as |
|---|---|
| `#short` | one line (the default when a question has no type tag; the check names it) |
| `#long` | a paragraph box |
| `#email` `#phone` `#number` `#date` `#url` | that kind of field |
| `#choice` | pick one of the options listed under it |
| `#multi` | pick any of the options listed under it |
| `#yesno` | Yes or No (or the options listed under it) |
| `#scale` | 1 to 5; `#scale-1-10` sets the range |
| `#required` / `#optional` | a mark on the question; with neither, it carries no mark, as a paper form leaves it |

Under a question, an indented `- line` is an option and any other indented line is its help text, one paragraph each. A `###` heading or a line that is all bold is a section; a paragraph before the first question is the intro and one after the last is the closing line.

```markdown
## Form: Problems list

Thank you for the time on Monday.

1. What takes up your team's time or keeps getting stuck? #long #required
   One line each, as many as come to mind.
5. Does it touch member or patient data? #choice #required
   - Yes
   - No
   - Parts of it

### For your top problem:

6. How is it done today, step by step? #long #optional
```

## Where it shows

- **The Forge**, in read mode: `/forge?path=<the .canvas>&mode=read`. A press on a file card opens it in the side drawer (a video plays there), a drawing's card opens that drawing, and a form tile's *Open the form* goes to the form page. Board drawings are not editable in the Forge's edit mode, since the files are the record.
- **The form page**, `/form?path=<the step file>`: the form drawn the way the person filling it in sees it. Nothing typed there is sent or saved. *Copy as data* puts the questions on the clipboard as JSON.

## From the terminal

```
python skills/brain-viewer/board.py list
python skills/brain-viewer/board.py draw [<board>]
python skills/brain-viewer/board.py check [<board>]
python skills/brain-viewer/board.py link <step.md> <file> [--video] [--note "what it is for"]
python skills/brain-viewer/board.py form <step.md> --json
python skills/brain-viewer/board.py form <step.md> --html <out.html>
```

`form --json` is what an agent reads to build a survey or a web page; `form --html` writes one plain, self-contained page with no script, whose `<form>` has no destination until whoever publishes it sets one.
