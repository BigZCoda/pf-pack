# Step boards — the contract

A **step board** is a process drawn in the Forge as steps in order. Each step is a Forge cell: its modulators (location, style, purpose, attendees, prep) sit on the rim, its form on the rim too, and what the step is, its video and its documents inside; the line to the next step carries what happens on the way. The files are the record and the drawing is their view: the viewer redraws the drawing from the files every time it opens in the Forge, so attaching something is one line in a markdown file. A cell dragged in the Forge's edit mode keeps its place; its words always come from its file. Code: `part_board.py` (the server reads it), `board.py` (the terminal), `form.html` (the form page), `board.test.py`.

**Modulators** are facets drawn on a step's cell: every frontmatter line of the step file that is not the step's own (`step`, `status`, `master`) is one, read through a registry (the section below). A modulator written with no value is drawn "not set"; one not written is not drawn. The rim shows each as `<Label>: <value>`, cut at 26 characters, so keep values short. **What happens on the way** to the next step is a `## On the way to the next step` list in the step file; it becomes the label of the line leaving that step. A cell's stage on the rim (in the drawing's sibling `.forge.json`) comes from its status: live is built, planned and maybe are concept. **One master per step:** `master: file` (the default) or `master: live` says which copy of the step's form is the one to trust when the live thing and the file differ; a reader marks the drift, it never rewrites either side.

## Modulators: the registry, the families, the states, the two versions

A modulator exists when the registry names it: `modulators.json` in the board's folder, else in the folder above it (one registry for every board under `boards/`, shared with a team copy), else the default written in `part_board.py`. `board.py modulators <folder> --init` writes the default into a folder; `--add` puts one more in. A key the registry does not know is drawn grey as *new*, has nothing behind it, and is a problem for `board.py check`, so a session that wants a new one adds its row in the same change. The registry also carries the other spellings a key is read under (`who` is read as `attendees`, `venue` as `location`), so a step written in other words still lands on the right slot.

Six families, each with a colour (light and dark) and a fixed place round the rim, in this order:

| Family | Answers | Modulators (the defaults) |
|---|---|---|
| Where | where it lives, where it is reached | location, address, home |
| Who | who is on it, who it is for | attendees, owner, audience, handoff |
| Why | what it is for, what is true after | purpose, outcome, decides, measure |
| How it looks | its shape to the person | style, voice, length, template |
| In and out | what it needs, what it makes, where that goes | prep, needs, produces, delivers, endpoint, format |
| When | what starts it, how long, how often | when, duration, cadence, followup |

A modulator has its own state, never the Forge's live states (which are read from the ledgers and would paint it "not built"): **not set** (no value), **set** (a value), **made** (the thing behind it exists: for `location`, an `address` on the step, or a made record), **checked** (a reader confirmed the live thing still matches, after made). `board.py made <step> <modulator> [--address <link>] [--checked]` writes the made and checked records into the board's `.forge.json` (`board.made`, `board.checked`, keyed `<step>/<modulator>`); the next draw lifts the state. A press on a modulator opens its address when one is known, else the step file.

The drawing's sibling `.forge.json` carries, under `board`, the drawn version, the families with their colours and the registry's path, and under each modulator part's row `mod` (key, label, family, value, state, new, help, address) and `connector`; the Forge draws from those. **Two drawn versions, one switch:** `modulators: band` (the default) draws them as segments of the rim inside the cell; `modulators: outside` as small boxes against the outside of the rim, anchored to the cell, in family order from the top. The line on the board file sets the default; the switch on the board's page flips it for the reader and is remembered per drawing. Zoomed out, both versions show only a coloured dot per set modulator.

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
attendees: the owner and the client      # every other line is a modulator the registry knows
when: once the event form is in
location: a video call
address: https://meet.example.test/abc   # with an address, the location is made and its press opens the link
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
python skills/brain-viewer/board.py set <step.md> <modulator> <value>
python skills/brain-viewer/board.py made <step.md> <modulator> [--address <link>] [--checked]
python skills/brain-viewer/board.py modulators [<folder>] [--init] [--add <key> --family <family> --help-text "..." --also a,b]
```

`form --json` is what an agent reads to build a survey or a web page; `form --html` writes one plain, self-contained page with no script, whose `<form>` has no destination until whoever publishes it sets one. `set` writes a modulator on a step and redraws; a spelling the registry knows is written as the key it stands for, an unknown key is refused with the way to add it. `made` records that the thing behind a modulator exists (or was checked). `modulators` lists the registry a folder answers to.
