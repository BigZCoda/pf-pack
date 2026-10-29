# looks/ -- the viewer's design as files

A **look** is the fonts, the colors and the box shapes of every page of the Brain Viewer, written as one file in this folder. The folder is the registry, the same way `widgets/` is: every `*.css` here is a look, and `GET /api/looks` lists them. Nothing else in the app names a look.

Built 2026-09-22 for a ledger item ("full customizability of the viewer, for a person or their agent").

## How it loads

- Every page is served with `looks/default.css` linked in its head, then the person's chosen look after it, both ahead of `viewer-tokens.css` (the shared stylesheet, which only *reads* the tokens). serve.py writes those links into the page as it serves it, so the first paint is already in the right look. There is no flash.
- A look that sets only some tokens falls back to `default.css` for the rest. `default.css` must always set all 33.
- **Two folders (0.48.0).** This folder holds the two looks the viewer ships, `default.css` and `paper.css`, and is replaced whole by an update. A look a person writes or imports lives in `viewer/looks/` at the brain root, which no update writes; both folders are listed together, and a person's file under a core name is listed as refused.
- The chosen look is per person: the `look` field of `viewer/layouts/<member>.json`. No field, or a look that is gone or no longer parses, means `default`. Resetting the home board keeps the look.
- In the page, `BV.look` (viewer-common.js) does the rest: `BV.look.use(name)` swaps the look in place without a reload, `BV.look.save(name)` makes it the person's look on every page, `BV.look.import(file)` adds a file, `BV.look.faces()` reads the faces the active look declares.

## The 33 tokens

These are the only names a look may set. The list is the one `default.css` holds, in its order; `home.test.py` asserts it.

**Type**

| token | what it controls |
|---|---|
| `--font-title` | the big titles only: a page's H1 in the header bar, a document's H1 in the reader, and the large numbers on home tiles (`.wbig`) |
| `--font-display` | names, headings (h1 to h3), node titles, anything with the `.display` class |
| `--font-ui` | all interface and body text: the default face of every page |
| `--font-mono` | code, ids, counts, times, the small mono numbers on tiles |
| `--size-ui` | the base text size of every page |
| `--lh-ui` | the base line height of every page |

**Ground and text**

| token | what it controls |
|---|---|
| `--bg` | the page ground, behind everything; canvases also soften their colors toward it |
| `--surface` | panels, cards, the header bar, drawers, popovers |
| `--ink` | the main text color |
| `--ink-soft` | slightly quieter text: secondary body copy |
| `--muted` | labels, counts, small-caps heads, the quiet grey of secondary information |
| `--rule` | frames, bars, the drawer edge, card borders |
| `--rule-soft` | dividers, table cells, hairlines between rows |
| `--code` | the background of inline code and code blocks |

**The one active thing**

| token | what it controls |
|---|---|
| `--accent` | titles, links, the one active thing on a page (a selected tab, the on button) |
| `--accent-deep` | the accent pressed or hovered: link hover, a darker accent edge |
| `--selected` | the background of a selected row |
| `--hover` | the background of a row or button under the pointer |

**Meaning** (status colors; each `-tint` is the pale background that goes with it)

| token | what it controls |
|---|---|
| `--done` | done, healthy, a lit lamp |
| `--done-tint` | the ground behind a done badge or row |
| `--open` | open, waiting, and the gold left edge of a card tile on the home page |
| `--open-tint` | the ground behind an open badge or row |
| `--blocked` | blocked, stuck |
| `--blocked-tint` | the ground behind a blocked badge or row |
| `--mouth` | a cell's output on the maps, and the packages waiting beyond it |
| `--mouth-tint` | the ground behind an output |
| `--mind` | minds (agents, skills, prompts) on the maps, and the agent glyph |
| `--danger` | errors, a broken tile, destructive buttons |
| `--danger-tint` | the ground behind an error message |

**Shape**

| token | what it controls |
|---|---|
| `--radius` | the corner of buttons, inputs, small cards, tiles |
| `--radius-lg` | the corner of large cards and panels |
| `--shadow` | the shadow of things that float: popovers, the search results, legends |
| `--frame` | the box-shadow every `.card` wears; in the default look it draws the second line of the double frame |

## Make a look

1. Copy `default.css` to a new name in `viewer/looks/`: lowercase letters, digits and hyphens, for example `night.css`.
2. Change the leading `/* ... */` comment to one line saying what the look is. The picker shows it.
3. Change the values you want. Delete the lines you do not change, if you like: they fall back to default.
4. Save. The look is in the picker on the home page's edit bar the next time it opens, and in `GET /api/looks`.

An agent does the same thing: write the file, then `POST /api/looks {"active": "<name>"}` to put it on.

What a look file may hold, and nothing else:

- One `:root { ... }` block of custom-property declarations, using only the 33 names above.
- In front of it, any number of `@import url("https://fonts.googleapis.com/...");` lines for the look's own faces. No other `@` rule.
- Comments.
- A value may not load anything or carry markup: no `url(`, no `@`, no angle brackets, no backslashes.
- At most 24,000 bytes.

The default look's faces (Grenze Gotisch, Libre Baskerville) are imported by `viewer-tokens.css`, so they are always there. Any other face a look uses must be imported by that look. `paper.css` shows how.

## Import a look

- On the home page: press **edit**, then **import a look** in the edit bar, and pick a `.css` file. It is checked, written into `viewer/looks/` under its file name, and put on straight away. A name already taken asks before it replaces; `default.css` and `paper.css` are never replaced from the page.
- From anywhere else: `POST /api/looks {"name": "<name>", "css": "<the file's text>", "activate": true}`. Add `"replace": true` to overwrite an existing look. A refused file comes back 400 with the reason.
- Or drop the file into `viewer/looks/` by hand. The same checks run when it is listed; a file that fails them is listed as not parsing and cannot be picked.

## The looks here

- `default.css`: Knight of the Sun. Cream ground, a blackletter title in burgundy, Libre Baskerville text, the grey double-line frame. The 33 tokens moved here unchanged from `viewer-tokens.css`.
- `paper.css`: Paper. A warm linen page set in Fraunces and Literata, a terracotta accent, rounded cards that lift off the page with a faint warm shadow instead of a drawn frame. It sets all 33, so nothing of the default shows through.

## A tile's own style (the home page)

In edit mode every tile on the home board has a **style** button. It opens a small panel whose choices are saved in that widget's row of `viewer/layouts/<member>.json`, as `"style": {...}` beside `settings`. Every key is optional, the row carries no `style` at all until one is set, and **reset** in the panel drops it.

| key | values | what it does on that tile |
|---|---|---|
| `accent` | `#rgb` or `#rrggbb` | sets `--accent`, `--accent-deep` (the accent mixed toward black) and `--w-edge`, the tile's own edge: the left edge of a card, the top hairline of a plain tile |
| `scale` | `s`, `m`, `l` | sets `--w-scale` (0.88, 1, 1.16), which sizes the tile's body text and its head |
| `box` | `hairline`, `card`, `none` | the tile's shape, overriding the one the widget declares: a hairline over open ground, the card (surface, frame, the gold edge), or nothing |
| `font` | `title`, `display`, `ui`, `mono` | which of the active look's faces the tile's text and headings wear. It points at the look's own token, so it follows the look when the look changes |

The overrides are written as custom properties inline on the tile element, so they beat the look for that tile only, and a widget that reads the tokens follows with no code of its own. A widget that hard-codes a color or a pixel size does not follow; that is the widget's to fix, under the contract in `widgets/readme.md`.
