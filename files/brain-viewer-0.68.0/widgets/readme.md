# The home page's instruments

**Before you build.** Read [curriculum.md](curriculum.md) first. It is the builder's brief: the tokens a widget may use,
two widgets read line by line, every endpoint the widgets call with its real response shape, the harness
(`widgets/harness.py`) every file must pass before it goes live, the definition of done, and what the board shows when
a widget breaks.

**The folder is the registry.** Every `*.js` file in here is an instrument on the home board. `GET /api/widgets` lists
the files, `home.html` loads every one of them, and whatever registered gets drawn. Nothing anywhere names a widget:
drop a file in this folder, reload the home page, press edit, and it is in the "add" list. Delete the file and it is gone.

**The id is the filename.** `dial.js` must register `id: "dial"`. `home.test.py` checks that for every file here,
because a mismatch means the server lists a widget the page can never draw.

**The board is twelve columns and a size IS a column span** (0.37.0): `"4"` a third, `"6"` a half, `"8"` two thirds,
`"12"` the whole width. The three letters the first board used (`S`, `M`, `L`) are still read and turned into spans, so
an old file and an old saved layout keep working. **A height is a row span** (0.39.0): `rows: 2` makes an instrument
stand across two rows of the board so short ones can sit beside it, and one or two are the only values there are.

**Every file wraps its helpers in a closure.** All the files share one global scope, so anything outside the
`register()` call goes inside `(function () { ... })();` or it collides with another instrument's.

## The contract

```js
BV.widgets.register({
  id: "dial",               // the filename without .js
  contract: 1,              // REQUIRED (0.48.0): the widget contract this file was written against. The page implements
                            // BV.contract (1); a file with no number or a higher one is refused and its tile reddened
                            // "written for a newer viewer". Additions to `api` stay within a number; a rename bumps it
  title: "The day",         // what the head says, and what the add list and the "?" panel call it
  size: "8",                // its column span when nobody has set one: "4", "6", "8" or "12"
  defaultOn: true,          // whether it is on the board for someone who has never edited it
  rows: 1,                  // 1 or 2: how many rows of the board it stands across. The deck is the one that is 2
  fillRows: 22,             // OPTIONAL: for a widget that needs a working height rather than its content's (a message
                            // list, a drawing): its free-mode height in 20px units when nobody has fixed one. Without
                            // it the tile fits its content. chat 22, flow 26, moved 19, people 18
  card: false,              // true wears the notepad's look (surface, the rule frame, the gold left edge).
                            // Only the deck and the chat do; everything else is a hairline on the open ground.
  head: true,               // false draws no head at all, for an instrument that is its own title
  expand: false,            // true puts an open-out control in the head: the full width, in place, saved in the layout
  source: "one line naming what it reads",   // shown in the question mark panel, never on the page
  mount(el, api) { ... },   // draw it. `el` is the body; `api` is below
  refresh(el, api) { ... }, // OPTIONAL. The board refreshes every minute; without this it re-runs mount.
                            // An instrument holding something the person typed declares an empty refresh, or checks
                            // the box is empty before it reads anything.
  resize(el, api) { ... },  // OPTIONAL. Called when the width changes: a resize, a new size, an expand. For a drawing.
});
```

`size` and `defaultOn` are only the starting point: what a person sets in edit mode is saved in
`viewer/layouts/<member>.json` (the user layer, 0.48.0) and wins from then on.

**The saved-layout migration rule (2026-09-24).** A saved layout is the person's arrangement, and it outlives
every widget in it. When a widget is removed or renamed:

1. **Drop the unknown ids.** A row whose `id` no widget answers to any more is left out when the layout is read. A
   renamed widget is a removal plus a new widget: the old row is dropped and the new id arrives off, at its default
   size, for the person to place.
2. **Keep the rest.** Every other row keeps its place, size, height, cell, settings, look and view exactly as saved. A
   row that fails its own checks when read (a size or height the board no longer offers, a setting the widget no longer
   takes, a second row for the same id) keeps its place with that one value back at its default, or, for a second row,
   the first wins. One bad row never costs the board.
3. **Never replace or delete the file.** No worker, script or migration rewrites, regenerates, resets or deletes
   `viewer/layouts/<member>.json` (or the legacy `home-layout-<member>.json`). Removing or renaming a widget needs no
   change to any layout file: the read rule above does the migration every time the board loads, and the file is next
   written only when the person changes the board, carrying just the ids that still exist. The one thing that clears a
   layout is the person pressing **reset to default** on the board. If a saved file cannot be read at all, the page
   draws the default and saves nothing over the file until that press.

Where it lives: `home_validate(..., drop_missing=True)` in `serve.py` (the read) and `loadLayout` / `save` in
`home.html` (a partial layout is honoured, never swapped for the default).

**Two folders, one registry (0.48.0).** This folder holds the widgets the viewer ships (bedrock, replaced whole by an
update). A person's own widgets go in `viewer/widgets/` at the brain root, which no update writes; they load after
these, under the same contract, and an id this folder already uses is refused on the board ("id taken by a core
widget"). The rules for both: `brain-viewer-plugin-contract.md`, shipped in the viewer's folder.

## Filters: rules on a widget are settings, not code

A list instrument may declare the filters it understands, in order, as `filters` in its register call. In edit mode the
tile's strip gains a **filters** button beside **style**, which opens ONE row drawn from that declaration: a control
per filter, **save as view**, **reset**, and a box for what no filter can say. A pick writes into the widget's
`settings` in the layout and the tile re-mounts at once; the widget reads its choices with `api.settings()` as it
reads any other.

```js
filters: [
  { key: "project", label: "project", kind: "pick", options: "projects", any: "every project" },
  { key: "due", label: "due", kind: "pick", default: "today",
    options: [["today", "today or behind"], ["week", "this week"], ["all", "any day, or none"]] },
  { key: "days", label: "days back", kind: "range", min: 0, max: 14, step: 1, default: 0, zero: "today" },
],
```

| field | |
| --- | --- |
| `key` | the settings key it writes. A value equal to `default` (or empty) is removed, so an untouched widget saves `{}` |
| `label` | the word in front of the control |
| `kind` | `pick` (a list), `text` (a free box) or `range` (a slider, with `min`, `max`, `step`; `zero` names the 0 end) |
| `options` | for a pick: a static list of `[value, label]` pairs or plain strings; a source name, one read each: `projects` (`/api/projects`, the ledger registry), `owners`, `tags` and `sources` (read off the items in `/api/projects`), `people` (`/api/people`), `agents` (`/api/moved`); or an endpoint, `{from: "/api/x", list: "rows", value: "id", label: "name"}` |
| `default` / `any` | a pick with a `default` has no empty choice; one without offers an empty choice labelled `any` ("every project"), which means no filter |

The widget must draw exactly what it drew before when every filter is at its default: the filters narrow a board,
they never change the one nobody touched. Declared today: **decide** (project, owner, due, tag, people, source, sort),
**moved** (agent, days, project), **people** (max, project).

**Named views.** A tile whose filters differ from the default can be saved under a name. The layout file carries them
beside the widgets as `views: [{id, name, settings}]`; the add list shows each as its own entry, titled by the name
with the widget it is made of beside it, and has rename and remove on each. Adding one puts that widget on the board
with those settings and wears the name as its title until a filter moves off it. There is one tile per widget, so
adding a view of a widget already on the board changes that tile rather than placing a second. A reset of the board
keeps the views. No views ship in code. The worked case, Decide as this week's items for one person:

```json
"views": [{ "id": "decide", "name": "This week's Sam items",
            "settings": { "project": "pf-build", "people": "mike-bledsoe", "due": "week" } }]
```

**What a filter cannot say.** The box at the end of the row takes one line; enter files it on the Brain Viewer ledger
as an `@claude` task with `#source:home-prompt`, quoting the widget file, the request and the settings, and shows the
item it filed on the tile. A builder turns that into a new widget file.

## What `api` gives you

| | |
| --- | --- |
| `api.get(path)` | fetch that endpoint as JSON, throwing an error carrying `.status` when it fails. **The read is shared** for a few seconds, so four instruments asking for the same endpoint on the same tick cost one request |
| `api.set({count, lines, max, note, link})` | the small list shape in one call: a count, a few lines, an optional closing link |
| `api.auto(path, build)` | read one endpoint and hand its JSON to a function returning what `set` takes. Failures, including the 403 a team copy answers with, are handled for you |
| `api.count(text)` | the count beside the title, on its own |
| `api.html(markup)` | write the body yourself, which is what every instrument with a shape of its own does |
| `api.head(markup)` | the instrument's own control, in its head, left of the edit tools (a view toggle, a filter) |
| `api.show(on)` | `false` draws nothing at all, rather than an empty card. It comes back in edit mode so it can still be moved |
| `api.expanded` / `api.setExpanded(on)` | opened out to the full width, in place. Saved with the layout, like size |
| `api.settings()` / `api.setSettings(obj)` | this instrument's own small object of choices, saved with the layout. An id may be passed first to read another instrument's |
| `api.emit(name, detail)` / `api.on(name, fn)` | one instrument saying something the rest of the board can hear, and following it. The header's day replay emits `replay` and the log lights the lines it passes. One handler per instrument per name, cleared on every render |
| `api.say(text)`, `api.fail(err)` | one muted line; `fail` turns a 403 into "not on this copy" |
| `api.esc`, `api.clip(s, n)`, `api.plural(n, word)`, `api.when(iso)` | the small helpers every instrument wanted |
| `api.el`, `api.card`, `api.row` | the body element, the whole section, and its row in the layout |

A line is `{text, href?, title?, tail?, cls?}`. `title` is the hover, `tail` the small grey thing on the right, and
`cls` may be `live` (bold) or `past` (faded).

## The rules an instrument follows

1. **Each one has a shape of its own.** The owner said on 2026-09-21 that the old board looked uniform and static, with
   nothing for the eye to adjust to. An arc, a card deck, two numerals, a timeline, a constellation, a red-edged strip, a wide line.
   A new instrument that is another list of three lines is the thing this page was rebuilt to stop being.
2. **Nothing on the page explains the page.** No summary sentences, no captions about what a thing is. The explanation
   goes in `source`, which the question mark panel shows.
3. **No ids, no codes, no markdown, no em dashes** in anything a person sees.
4. **Colors and type come from `viewer-tokens.css`.** A widget may inject its own layout CSS, once, under an id of its
   own, but every color is a token and there are no gradients and no shadows the tokens do not already use.
5. **A team copy answers 403 on several endpoints** (`/api/pending`, `/api/calls`, `/api/chat*`, `/api/agents`,
   `/api/people*`, `/api/preps`, `/api/groups`, `/api/app/*`). `api.auto` and `api.fail` already render that as
   "not on this copy" in one line. Do not let it throw.

## The board, top to bottom

`masthead` the date, the slot you pick an instrument for (the day as a band with a replay in its corner, a project as a
track of its stages, or the week), the clock, the running sessions orbiting the sun and the moon for the night agent ·
`mantra` the day's line, drawn into the room the masthead keeps under the date · `next` the call in front of you (from
the morning of its day until 30 minutes after it ends), with a press to join it and one into its call screen, or to
write its prep when there is none · `deck` the questions, one card at a time, two rows tall · `chat` the conversation, under Next ·
`decide` what is due today · `people` the week's people and the ones the ledgers name, as bubbles on the map's own
physics or as a drifting roll of names · `horizon` the countdowns, as numerals or
as a road · `moved` what changed · `flow` the brain wired to everything it exchanges anything with, pulsing as the log
is written · `system` a lamp per part that runs on its own. The order in HOME_ORDER is the order the grid fills, not the
reading order: the deck is named before the chat so it takes the right hand column across both rows. Everything else in
this folder is off and waiting in the add list, `command` (the plain line to the main agent), `space` (a gap on
purpose), `dial` (the sundial) and `minimap` (the constellation) among them.

**Free mode.** The edit bar's board switch turns the grid into free placement: the same twelve columns, but
every tile sits at its own cell, saved in its row of the layout as `x` and `y` (column 0 to 11, row index) and `w` and
`h` (columns, and rows of the fine unit), with `"mode": "free"` on the file. In edit mode a tile moves by its head
and resizes by its corner and edge handles; both land on the cell edges when let go, and a tile put down on another
pushes that one down by rows. The first switch takes every cell from the grid order, grid mode keeps the cells for the
next switch, and under 760px both modes are one column (free mode in y, then x). A widget needs no code for any of it:
it draws into its body as it always has, and a tile whose box changes size gets its `resize` call. Snapping off, with
positions as fractions of the width, is not built yet; its toggle sits disabled in the edit bar.
**The row unit and the height (2026-09-22).** A free row is 20px (`"rowUnit": 20` on the file) with no row gap; the
tile's own 18px bottom margin is the gap. A tile's height follows its content by default: after every render and
refresh, and whenever anything in the tile changes size, it stands ceil(content / 20) units, and the board is refit
below it (grown, what it covers is pushed down; shrunk, what sat on it comes up). That is drawn, not saved; the heights
reach the file with the next change the person makes. A pull on the top or bottom edge or a corner fixes the height
(`"hFixed": true` on the row); a double-click on the bottom edge handle frees it again. A widget that needs a working
height rather than its content's declares `fillRows` (see the contract), used whenever no height is fixed. A file with
no `rowUnit` is on the old 158px pitch (a 140px row and an 18px gap) and is converted once in the page:
`y' = round(y * 158 / 20)`, every tile made to fit its content, and the board compacted once the tiles have measured.
`rowUnit` is written on the next save. On the server `h` may be missing in free mode (the tile fits its content),
`y` runs to 4000 and `h` to 400.

**Taking things out.** In edit mode each run of fully empty rows is drawn as one faint band. Click a band and press
Delete (or Backspace) and it goes, everything below it coming up. Click a tile's head (anywhere that is not a control,
for a tile with no head) and press Delete and the tile goes off the board; the add list puts it back. Escape lets go,
and a key typed into a box is never taken. **keep closed** (`"gravity": true` on the file) moves every tile up as far
as it goes after every drop and resize, and when it is switched on.

**The cap and undo.** No height a person did not pull stands taller than 40 units (800px): measured content and
`fillRows` both stop there, a measurement reads the content at its natural height (never the tile's span), and any
saved height above 40 comes back fitting when the board is read. In edit mode Ctrl+Z (Cmd+Z) or **undo** takes back
the last change and Ctrl+Shift+Z, Ctrl+Y or **redo** puts it back, 50 steps kept until the page reloads, each one saved
like any edit and named on the status line.

## Reaching for the moving bubbles

There is ONE physics, at `/static/graph-physics.js`, which is the map page's own three forces lifted out (0.40.0):
`BV.graph.gravity(k, {skip})`, `BV.graph.collide(strength, {radius, pad, skip})`, `BV.graph.breathe(amp, {skip})`, and
`BV.graph.ready()` for the vendored renderer, loaded once however many instruments ask. `people` draws with it. An
instrument that wants bubbles loads that file and uses those forces; it does not write a second engine, because two of
them drift apart and only one of them gets the next fix.

## An instrument's own settings

A row in the layout carries a small `settings` object for that widget, so a pick survives a reload and travels with the
board rather than living in one browser. `api.settings()` reads it, `api.setSettings({...})` merges and saves. It is
for a preference (which drawing, which project, which form), never for data.

## A worked example

`skills/brain-viewer/widgets/landed.js`, whole:

```js
BV.widgets.register({
  id: "landed", title: "Landed today", size: "4", defaultOn: false,
  source: "the transcripts whose name carries today's date, and their intake state (GET /api/landed)",
  mount: (el, api) => api.auto("/api/landed", j => ({
    count: (j.count || 0) + " landed · " + (j.intaken || 0) + " taken in",
    lines: (j.landed || []).slice(0, 3).map(r => ({ text: api.clip(r.stem, 62), href: "/today", title: r.stem,
                                                    tail: r.report ? "taken in" : "not yet" })),
    max: 3, note: (j.count || 0) ? "" : "nothing landed today",
    link: { href: "/today", text: "the day page" },
  })),
});
```

Nine lines, one endpoint, and it is on the board.
