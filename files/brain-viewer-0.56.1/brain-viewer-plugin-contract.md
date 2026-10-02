# Brain Viewer plugin contract

**Written:** 2026-09-23 (viewer 0.48.0) | **Contract number:** 1 | **Ships:** into the component as `brain-viewer-plugin-contract.md`, beside `readme.md`

What the viewer promises to the things people build on it, and what it asks of them. One rule underneath all of it: the viewer is split into a bedrock folder that an update replaces whole, and a user layer that an update never writes.

## Bedrock

`skills/brain-viewer/` is the application: `serve.py`, the pages, `viewer-common.js`, `viewer-tokens.css`, the core widgets in `widgets/`, the two core looks (`looks/default.css`, `looks/paper.css`), the image providers, the chat prompts, the tests and the widget harness. It ships as the pf-pack component `brain-viewer`, and its installed version is `component.json`. An update (`python skills/update/install-component.py brain-viewer`, which `/update` runs on a yes) downloads the new folder, checks every file against its checksum, and swaps it in whole. Nothing is merged, so a change made inside this folder is lost at the next update. The maintainer copy is the one that carries `release.py`; the installer refuses to replace it.

Things that are not the application do not ship in it: the content manifests a brain declares (the mentee content manifest, the maps manifest), harness fixtures captured from one machine's live server, `node_modules`, caches.

## The user layer

`viewer/` at the brain root belongs to the person. The viewer creates it on first start and writes into it only when the person acts in the app:

| path | what |
| --- | --- |
| `viewer/settings.json` | the settings, each explained in the file's `_keys` |
| `viewer/layouts/<member>.json` | one home board per person: widgets, positions, sizes, their settings, named views, the chosen look |
| `viewer/looks/*.css` | looks the person wrote or imported |
| `viewer/widgets/*.js` | widgets the person wrote |

No update, export or pull writes here. A team copy grows its own; the team export does not ship it. A brain that still has the old files inside the code folder (`viewer-settings.json`, `home-layout-<member>.json`, a look other than the two core ones) has them copied into `viewer/` once, on first start and again by the installer before it replaces the folder; the copy never overwrites a file already in `viewer/`.

## The widget contract

A widget is one `.js` file whose name is its id. The core ones are in `skills/brain-viewer/widgets/`; a person's are in `viewer/widgets/` and load after the core ones.

The file makes one call, `BV.widgets.register({...})`, wrapping any helpers in a closure because every widget shares one global scope. The fields: `id` (the file name), `contract` (required, the number below), `title`, `size` (`"4"`, `"6"`, `"8"` or `"12"` of twelve columns), `defaultOn`, `rows` (1 or 2), `source` (one line naming what it reads, shown in the help panel), optional `card`, `head`, `expand`, `fillRows`, `filters`, and the functions `mount(el, api)`, optional `refresh(el, api)` and `resize(el, api)`. The full field list with examples is `widgets/readme.md`; the builder's brief is `widgets/curriculum.md`.

**The contract number.** The page sets `BV.contract = 1`. A widget declaring no number, or a higher one, is refused: its tile is drawn red with "written for a newer viewer" and nothing of it runs. A person's widget that asks for an id a core widget already holds is refused the same way, with "id taken by a core widget", and the core widget is untouched.

**The mount api.** `mount` receives the tile's body and an `api` object: `get(path)` (a shared, cached read that throws with `.status`), `auto(path, build)`, `set({count, lines, max, note, link})`, `html(markup)`, `head(markup)`, `count(text)`, `show(on)`, `settings()` and `setSettings(obj)`, `expanded` and `setExpanded(on)`, `emit(name, detail)` and `on(name, fn)`, `say(text)`, `fail(err)`, and the helpers `esc`, `clip`, `plural`, `when`, plus `el`, `card` and `row`. The function that builds it, `widgetApi()` in `home.html`, is the authority when a document disagrees.

**The guarded mount.** Every run of `mount`, `refresh` and `resize` is watched. A throw, a rejected promise, or a later error traced to the widget's file turns that one tile red with the error's first line and a press that hands the fix to a builder; the rest of the board keeps drawing. A 403 (an endpoint a team copy does not serve) is not a break: `auto` and `fail` say "not on this copy".

**The harness.** `python skills/brain-viewer/widgets/harness.py <file>` loads the real home page in jsdom with only that widget on the board and answers every read from `widgets/fixtures/`. A widget is done when `node --check` passes, the harness says it holds, and it draws nothing unbound (no `undefined`, `NaN`, empty body or leftover "loading"). Fixtures are captured from the person's own running viewer with `--capture`; they are never shipped, because they hold that machine's real data.

## The look contract

A look is one file: at most 24,000 bytes, Google Fonts `@import` lines, comments, and one `:root { ... }` block setting only the tokens `looks/default.css` sets. A value may not load anything (`url(`, `@`, angle brackets, backslashes are refused). A look that sets only some tokens falls back to `default.css` for the rest.

The tokens a look may redefine, 33 of them:

- type: `--font-title` `--font-display` `--font-ui` `--font-mono` `--size-ui` `--lh-ui`
- ground and text: `--bg` `--surface` `--ink` `--ink-soft` `--muted` `--rule` `--rule-soft` `--code`
- the one active thing: `--accent` `--accent-deep` `--selected` `--hover`
- status meanings: `--done` `--done-tint` `--open` `--open-tint` `--blocked` `--blocked-tint` `--danger` `--danger-tint`
- kinds of thing: `--mouth` `--mouth-tint` `--mind`
- boxes: `--radius` `--radius-lg` `--shadow` `--frame`

Widgets read these tokens and nothing else for color, type and box shape. `--danger` means a fault, never decoration, because a red edge on the board means a broken tile.

## The endpoint promise

Within one contract number the `/api/*` endpoints a widget reads only grow: a new endpoint, a new field in an answer, a new optional parameter. Renaming or removing an endpoint or a field, or changing what a field means, bumps the contract number, and every widget has to say it was written for the new one before it runs again. The same holds for the `api` object handed to `mount`.

## How a person's widget becomes shared

A widget someone wrote in their `viewer/widgets/` becomes everyone's by being copied into the pf-pack repository's contrib folder at a release: the maintainer reviews the file, runs it through the harness, and the release script carries it into the component's `widgets/`, where it becomes a core widget that ships with the next version. Until then it lives only in the brain that wrote it. This path is described, not built.

## A brain's layout, and what the viewer discovers

The viewer reads any brain laid out on the PF convention: `people/` (one card per person), `context/` (the log, the calendar files, the chats index, the holon registry), `deliverables/` (call preps, studio output), `transcripts/` (raws and `import-reports/`), `thoughts/notepad/`, `requests/`, and the project ledgers named by the holon registry, the same registry `skills/brain-tasks/tasks.py check` reads. A brain built from the mentee shell has these folders, but not yet a registry or a ledger; with none, every page draws empty rather than failing, and `serve.py --init` creates a registry and a first ledger without overwriting anything.

What is not a convention comes from `viewer/settings.json`, and the viewer falls back to a plain default when a setting is absent: the owner (`owner`, default `@me`), where the drawings live (`forge_root`, default the first of `canvases/` or the PF architecture folder that exists), the mantra pool (`mantras`), the ledger a broken widget files its finding on (`findings_ledger`), and where the content manifests are (`mentee_manifest`, `maps_manifest`; otherwise `context/` first, then the older place inside the code folder). The PF App endpoints and token files are the same for every PF brain; with no token the pages that need them say so. The remaining places where the viewer still names this maintainer brain's own folders are listed with their fixes in the maintainer brain's layout check of 2026-09-23 and filed on its Brain Viewer ledger.
