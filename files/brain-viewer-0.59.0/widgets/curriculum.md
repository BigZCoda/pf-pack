# How to build a home widget, and how to prove it works

Read this whole file before you write a widget. It is the builder's brief for ledger item brain-viewer T-0217. The
owner set the priority on 2026-09-21: an agent must know exactly how to create a widget and verify it, and a break must
be caught.

The order: what a widget is, the tokens it may use, two widgets read line by line, every endpoint the widgets call with
its real response shape, the harness, the definition of done, and what the board shows when a widget breaks.

## 1. What a widget is, and the contract

A widget is one `*.js` file in `skills/brain-viewer/widgets/`. The folder is the registry: `GET /api/widgets` lists the
files, `home.html` loads every one, and whatever calls `BV.widgets.register({...})` is drawn. The id is the filename.

The contract itself (every field of `register`, every method on `api`, the shape of a line, the five rules an
instrument follows, the board's order) is in [readme.md](readme.md). Read it next; it is not repeated here. The parts
you will use on every widget:

- `mount(el, api)` draws it. `refresh(el, api)` is optional and runs every minute (without it, mount runs again).
  `resize(el, api)` is optional and runs when the width changes.
- In free mode a tile fits its content on its own. `fillRows: N` in the register call is only for a widget that needs a
  working height rather than its content's (a message list, a drawing): its tile then stands N units of 20px.
- `api.get(path)` reads an endpoint as JSON, shared across widgets for eight seconds, and throws an error carrying
  `.status` on a non-2xx answer.
- `api.auto(path, build)` reads one endpoint and hands the JSON to `build`, which returns what `api.set` takes.
- `api.set({count, lines, max, note, link})` draws the small list shape; `api.html(markup)` draws anything else.
- `api.settings()` and `api.setSettings(obj)` keep a preference with the board; `api.head(markup)` puts a control in
  the head.

**Declaring filters.** A list instrument that someone might want narrowed (by project, owner, day, person) does not
grow a head control per rule: it declares `filters: [{key, label, kind, options?, default?, any?}]` in its register
call (the fields are in the readme's Filters section) and the board draws one shared row for them in edit mode,
writing the picks into its `settings`. In the widget, read the keys from `api.settings()` in `refresh`, treat a missing
key as the default, and keep the untouched case drawing exactly what it drew before. `decide.js` is the worked case:
`rules()` reads the settings into one object whose `plain` flag keeps the board's shared count when nothing is set,
and `pick()` applies the rest. The harness mounts with empty settings; to prove a filtered path, run it on a draft
copy whose `api.settings()` returns the settings you want to check.

The real `api` object is built by `widgetApi()` in `skills/brain-viewer/home.html`. When the readme and that function
disagree, the function is right and the readme is the thing to fix.

## 2. The design tokens a widget may use

Every color, face and box shape comes from a token. The tokens are set by a **look** file in
`skills/brain-viewer/looks/` (`default.css` holds all of them); what each one controls is in
[looks/readme.md](../looks/readme.md). `viewer-tokens.css` only reads them. A widget's own CSS names tokens with
`var(--name)` and never carries a hex, a font name, a gradient or a shadow the tokens do not already have.

The 33 names, as `looks/default.css` sets them on 2026-09-22:

| group | tokens |
| --- | --- |
| type | `--font-title` `--font-display` `--font-ui` `--font-mono` `--size-ui` `--lh-ui` |
| ground and text | `--bg` `--surface` `--ink` `--ink-soft` `--muted` `--rule` `--rule-soft` `--code` |
| the one active thing | `--accent` `--accent-deep` `--selected` `--hover` |
| status meanings | `--done` `--done-tint` `--open` `--open-tint` `--blocked` `--blocked-tint` `--danger` `--danger-tint` |
| kinds of thing | `--mouth` `--mouth-tint` `--mind` |
| boxes | `--radius` `--radius-lg` `--shadow` `--frame` |

Status colors carry meaning: `--done` is finished or healthy, `--open` is waiting, `--blocked` is stuck, `--danger` is
a fault. A widget does not use `--danger` for decoration, because a red edge on the board means a broken tile
(section 7).

The page also gives every widget a few shared classes (defined in `home.html`): `ul.wlines` (what `api.set` draws),
`p.wsay` (one muted line), `a.wmore` (a closing link), `.wbig` (a big numeral in the title face), `.wcaps` (a small caps
label), `.wnum` (a mono number), `.wtab` (a quiet toggle for `api.head`).

## 3. Two widgets, read line by line

### A small list instrument: `organize.js`

```js
 1 // Still to organize: what is sitting in a project's Inbox, which is to say open and not yet sorted into a milestone.
 2 BV.widgets.register({
 3   id: "organize", contract: 1, title: "Still to organize", size: "4", defaultOn: false,
 4   source: "the open items sitting unsorted in a project's Inbox (GET /api/projects)",
 5   mount: (el, api) => api.auto("/api/projects", j => {
 6     const groups = [];
 7     for (const p of j.projects || []) {
 8       if (!p.exists) continue;
 9       let n = 0;
10       for (const g of p.groups || []) {
11         if (String(g.name || "").trim().toLowerCase() !== "inbox") continue;
12         for (const i of g.items || []) if (i.mark === "?" || i.mark === " " || i.mark === "-") n++;
13       }
14       if (n) groups.push({ id: p.id, name: p.name || p.id, n: n });
15     }
16     groups.sort((a, b) => b.n - a.n);
17     return { count: api.plural(groups.reduce((a, g) => a + g.n, 0), "item"),
18              lines: groups.slice(0, 3).map(g => ({ text: g.name, href: "/projects?id=" + encodeURIComponent(g.id), tail: String(g.n) })),
19              max: 3, note: groups.length ? "" : "everything is sorted",
20              link: { href: "/projects", text: "sort them" } };
21   }),
22 });
```

- **1** One comment line saying what the instrument shows, for whoever opens the file. Nothing on the page says it.
- **2** The one register call. This file has no helpers outside it, so it needs no closure; the moment it has one, the
  whole file goes inside `(function () { ... })();`.
- **3** `id` equals the filename stem, or the board never draws it. `contract: 1` is the widget contract the file was
  written against (0.48.0): without it, or with a higher number, the board refuses the file and reddens its tile. `title` is the head label and the name in the add
  list. `size: "4"` is a third of the twelve columns. `defaultOn: false` keeps it off a board nobody has edited.
- **4** `source` is what the question mark panel shows. The endpoint in parentheses is for readers of the file; the
  panel strips it.
- **5** `api.auto` does the read and the failure handling: a 403 on a team copy becomes "not on this copy", any other
  failure breaks the tile (section 7). Because this widget has no `refresh`, the board re-runs this mount each minute.
- **6 to 15** The work: for each ledger that exists (line 8), count the items in its Inbox group (line 11) whose mark
  is open, a question, or held (line 12). The mark letters and field names are the ones in the `/api/projects` shape
  below; guessing a field name is the most common way a widget draws nothing.
- **16** Most first, so the three lines shown are the three that matter.
- **17** The count beside the title, in words, through `api.plural`.
- **18** At most three lines, each a link into that project, with the number as the grey tail.
- **19** `note` is the line shown when there are no lines, so an empty result says something instead of nothing.
- **20** The closing link.

### A drawing instrument: `tally.js`

`tally.js` draws three numbers in one of three forms (a sentence, three bars, or three numerals) and keeps the chosen
form with the board. Open the file beside this section.

- **1 to 3** What it shows and that the head chooses the form.
- **4 and 103** The closure. `FORMS`, `WORDS`, `word`, `form`, `head` and `draw` live outside the register call, so
  without it they would collide with another widget's names in the one global scope.
- **5 to 8** Constants and a helper, private to this file.
- **10 to 12** The declaration. `source` names all three endpoints it reads.
- **14 to 35** Its own layout CSS, injected ONCE under the id `bv-tally-css`, and every value in it a token
  (`--font-display`, `--ink-soft`, `--rule-soft`, `--accent`, `--muted`, `--font-mono`, `--font-title`). The class
  prefix `.ty` keeps the rules from reaching any other tile.
- **36** One container with a `data-ty` hook, which `draw` finds again later.
- **37 to 42** A click on a form button in the head saves the pick with `api.setSettings` (so it survives a reload and
  travels with the board), repaints the head and redraws. The listener is on `api.card`, the tile, because the head
  is outside `el`.
- **43 and 44** Paint the head, then hand over to `refresh`, so the first draw and the minute tick are the same code.
- **47 to 50** Three reads at once. `soft` turns a failed read into `null` so one missing endpoint does not stop the
  other two numbers; the failure still turns the tile red-edged, because every failed `api.get` does.
- **51 to 63** The numbers: calls finished today, the owner's tasks done today, questions answered today.
  `api.onTheClock(projects)` (line 55) is the page's one rule for "on the clock", shared so two widgets never disagree.
- **64 to 70** Keep the rows on the element and draw.
- **74 to 77** Read the saved form, falling back to `sentence` for anything unknown.
- **78 to 82** The head control: three `.wtab` buttons, the saved one marked `on`.
- **83 to 102** One drawing per form. Bars are a track of `--rule-soft` with an `--accent` fill whose width is the
  percentage; numerals are `.n` in the title face; the sentence spells small numbers out. Every value put into markup
  goes through `esc` (line 85) unless it is a number the widget computed.

## 4. The endpoint catalogue

Every `/api/...` path a widget in the folder calls, which widgets call it, the fixture file that holds its real
answer, and that answer trimmed to its shape: lists cut to one entry, strings clipped, deep objects shown as `{...}`.
Captured from the live server on 2026-09-22 with `harness.py --capture`; the full answers are in
`widgets/fixtures/`. Read the fixture for any field this summary folds away before you rely on it.

A fixture is named by the path alone (`/api/today/tasks?app=1` is `today-tasks.json`), so every query a widget sends to
one endpoint is answered by the same file.

| endpoint | read by | fixture |
| --- | --- | --- |
| `/api/agents` | masthead, running | `agents.json` (trimmed to 6 sessions) |
| `/api/calendar/week` | dial, masthead, next, people | `calendar-week.json` |
| `/api/calls` | dial, masthead, next, people, tally | `calls.json` |
| `/api/chat?id=<chat>` | chat | `chat.json` (trimmed to 6 turns) |
| `/api/chats` | chat | `chats.json` |
| `/api/events` | flow (a server-sent stream, stubbed, no fixture) | none |
| `/api/glossary` | glossary, and the page itself | `glossary.json` |
| `/api/graph` | minimap | `graph.json` |
| `/api/groups` | threads | `groups.json` |
| `/api/holons` | holons | `holons.json` |
| `/api/landed` | landed | `landed.json` |
| `/api/manifest` | mentee | `manifest.json` |
| `/api/mantras` | mantra (GET, and POST to add a line) | `mantras.json` |
| `/api/maps` | maps | `maps.json` |
| `/api/moved?limit=&since=` | flow, masthead, minimap, moved | `moved.json` |
| `/api/notes?limit=3` | notepad | `notes.json` |
| `/api/people` | people | `people.json` |
| `/api/projects` | decide, deck, masthead, organize, people, tally | `projects.json` |
| `/api/review` | review | `review.json` |
| `/api/search?limit=3&q=` | search (only once something is typed) | `search.json` |
| `/api/stages` | masthead, stages, horizon (the road form) | `stages.json` |
| `/api/status` | status | `status.json` |
| `/api/system` | system | `system.json` |
| `/api/today/tasks?app=1` | decide | `today-tasks.json` |
| `/api/waiting` | deck, tally | `waiting.json` |
| `POST /api/chat/send` | chat, command (a server-sent stream, on send only) | none |
| `POST /api/prep {event_start}` | next (only when "no prep yet, write one" is pressed; then it navigates to `/call`) | none |

The page itself also reads `/api/badges`, `/api/glossary`, `/api/quests` and `/api/help` whatever is on the board; the
harness answers them from fixtures and does not count them as the widget's.

A team copy answers 403 on `/api/calls`, `/api/chat*`, `/api/agents`, `/api/people*`, `/api/groups` and `/api/waiting`
among others (readme rule 5). A 403 is never a break.

The shapes:

```text
/api/agents
{generatedAt, source: {transcripts, window, log, note},
 sessions: [{id, sessionId, file, title, cwd, branch, cliVersion, started, lastActive, minutesIdle, active, userTurns,
             model, models: [...], counts, ...}],
 chats: [{id, project, title, session_id, model, created, last, turns, cost_usd, dispatched, last_result, running}],
 handoffs: [], projects: [{id, name, path, ledger, readme, spec, rules, description}],
 models: [{ok, resolves, note, id, label, when, default}],
 brain_agents: [{agent_id, at: "2026-09-22 11:27", last_action: "DECISION", last_text}],
 on_ledgers: [{project, projectId, path, id: "T-0005", text, owner: "@claude", milestone, state: "open", blocked, due, tags}]}

/api/calendar/week
{_servedAt, today: "2026-09-22", schema: "brain-calendar-week/1", file, source: "week", exists: true,
 from: "2026-09-21", to: "2026-09-28", writtenAt, timezone: "America/Los_Angeles",
 events: [{date, start: "2026-09-21T09:00:00-07:00", end, title, organizer, attendees: [{name}], people: [{...}],
           preps: [{...}], join: "https://meet.google.com/..." | null, calendarLink: "https://www.google.com/calendar/event?eid=..." | null}],
 count: 6, days: ["2026-09-21", ...], writtenBy}

/api/calls
{_servedAt, today, file: "context/today-calendar.json", answeredBy: "context/today-calendar.json" | "context/week-calendar.json" | null,
 exists: true, for: "2026-09-22", stale: false,
 events: [ same event shape as the week, plus noCard ], count: 0, withPrep: 0, prepFolder, writtenBy, writtenAt}
 (0.47.0: when the today file is another day's, today is read from the week file and answeredBy says so; stale is true
  only when the file that answered was written for another day)

/api/chat?id=<chat id>
{chat: { one row of /api/chats }, turns: [{role: "user", text, ts} | {role: "assistant", model, text, tools, ts}], subagents: [], note, transcript}

/api/chats
{chats: [{id, project, title, session_id, model, created, last, turns, cost_usd, dispatched, last_result, running}],
 projects: [{id, name, path, ledger, readme, spec, rules, description}], models: [...], running: [],
 folder: "context/chats", cli, cliVersion, capMinutes: 10, default_model: "sonnet", context: {parts, chars, prompts}}

/api/glossary
{file, available: true, groups: [{name, anchor, pages: [...], note, hover, terms: [...]}],
 terms: [{term: "Node", aliases: [], definition, example, analog, group, anchor, hover}],
 keys: [{key: "Escape", pages: [...], what}], note, _servedAt, mtime}

/api/graph
{generatedAt, mode: "normal",
 nodes: [{id: "project:pf-build", badge: 45, href, summary: [...], type: "project", key, label, path, sharing}],
 edges: [{source: "person:...", target: "project:pf-build", kind: "item", n: 4}],
 counts: {project: 6, person: 51, group: 4, document: 69, copy: 1, chat: 8, agent: 1}, edgeKinds: {...},
 quietPeople, children, propose: false, notes: [], absent: []}

/api/groups
{_servedAt, file, today, updated, note, notSeeded: {...}, count: 4,
 groups: [{id: "team", name: "PF team", cadence, notes, open: 13, openItems: [...], confirmed, evidence, members: [...],
           memberSlugs: [...], unknownMembers: [], lastCall: {...}, preps: 3, lastPrep: "2026-09-21"}],
 error: null, transcripts: 208, unmappedNames: [[...]]}

/api/holons
{_updated, _rules: [...], sharing_tiers: [...], types: [...], _servedAt,
 holons: [{id, name, type: "family", path, description, tasks, sharing: "team", stamped, parent, children: [...],
           isDir, exists, mtime, frontmatter, ...}]}

/api/landed
{_servedAt, today, folders: ["transcripts", ...], reportFolder: "transcripts/import-reports", count: 0, intaken: 0,
 landed: [{folder, stem, mirror, files: [{path, ext, bytes}], report, ...}]}  (empty in the fixture: nothing had landed that day)

/api/manifest
{_about, updated: "2026-09-04", stages: [{stage: "Before day one", why, pieces: [{...}]}], _brain, _servedAt}

/api/mantras
{_servedAt, file: "projects/pf-build/pf-mantras.md", today, exists: true,
 items: [{text, author: "Marcus Aurelius", source: "Meditations"}], count: 23, canAdd: true, propose: false}

/api/maps
{_servedAt, manifest, days: 14, groups: [{id: "flow", name, purpose, maps: [{...}], lastAt}],
 other: [{family, canvases: [...]}], mostRecent: {path, group, at}, retired: {route, note}}

/api/moved?limit=200
{_servedAt, file: "context/log.md", since: null, limit: 200,
 items: [{at: "2026-09-22T11:27", day, time: "11:27", agent: "claude-code", action: "DECISION", text}],
 count: 200, read: 1492, agent: null, days: null, newest, oldest}

/api/notes?limit=3
{folder: "thoughts/notepad", count: 35, notes: [{path, title, taken, mtime}]}

/api/people
{_servedAt, today, folder: "people", prepFolder, format, count: 51,
 people: [{slug, name, path, role, status, stands: {...}, stale, staleWhy, staleKind, statusFold, category,
           location, org, placedAt, ...}],
 errors: [], prepCount, openTotal, staleCount, staleDays: 30, order: {...}, weeklyCount, ...}

/api/projects
{_servedAt, today: "2026-09-22",
 projects: [{id: "pf-build", name, description, path: "projects/pf-build/pf-build-tasks.md", holonPath, exists: true,
             mtime, errors: [],
             summary: {tasks, open, done, blocked, held, overdue, questions_open, questions_answered, ...},
             groups: [{name: "Inbox", items: [
               {state: "open" | "done" | "answered" | ..., mark: " " | "x" | "?" | "-" | "a", id: "T-0001",
                kind: "task" | "question", created, owner: "@zak", to, text, due, done, blocked, unblocked, until,
                answer, answered, app, note, people: [...], links: [...], tags: [...], repeats: 0, source, key,
                call, milestone, line}]}]}]}

/api/review
{_servedAt, today,
 cards: [{kind: "closure" | "review", proposal, changes, evidence: [...], cardId: "brain-viewer-holon:T-0057",
          project, projectName, file, id, itemKind, text, note, history: [...], owner, ...}],
 shown: 20, waiting: 29, sitting: 20, untested: 6, rated: [{... verdict: "off", day, at, ...}],
 presses: {...}, counter: {...}, ratedTotal, ratingsFolder, autoClose: {...}, rule: {...}}

/api/search?limit=3&q=brain
{q, count: 755, items: [{path, line, snippet, why: "name+text", mtime, matches}], capped: true, limit: 3,
 files, tooBig, ms, note}

/api/stages
{_servedAt, today, milestone: "Straight-line",
 steps: [{project, projectName, projectPath, id: "T-0039", step: "1", num: 1, suffix, short, text, milestone, due,
          at, mark: "x", state: "done", ...}],
 total: 9, doneCount: 6, current: "T-0043"}

/api/status
{_servedAt, holons: [{id, name, path, agent, rules, generatedAt, generatedBy, ageHours, data: {...}, error}]}

/api/system
{_servedAt, lamps: [{id: "calendar", name: "Calendar", lastRan: "2026-09-22T10:36:47-07:00", cadence: "session",
                     state: "lit" | "dim" | "red", detail}],
 count, red}
 (since T-0217 the last lamp is {id: "widgets", name: "Widgets", ..., broken: ["<widget id>", ...]}; the fixture was
  captured before the server restart that brings it, so re-run --capture after that restart)

/api/today/tasks?app=1
{app: {count: 552, app, cached: true, readAt, ttlSeconds: 600, read: 552}}

/api/waiting
{_servedAt, today, total: 110, questions: 15, tasks: 95, held: 0,
 groups: [{project: "pf-build", name, path, holonPath, questions: [ item ], tasks: [ item ], held: []}]}
 (an item here is a /api/projects item plus project, projectName, projectPath, held and peopleSource)
```

## 5. The harness: how to run it and read it

`skills/brain-viewer/widgets/harness.py` mounts ONE widget file in jsdom and says whether it holds. It loads the REAL
`home.html` with the real `viewer-common.js`, the real `api` object and the real break guard, on a board holding only
that widget, and answers every `/api/...` read from `widgets/fixtures/`. No server is needed.

```text
python skills/brain-viewer/widgets/harness.py skills/brain-viewer/widgets/mywidget.js    one widget, full report
python skills/brain-viewer/widgets/harness.py path/to/a/draft/mywidget.js                a draft, before it goes live
python skills/brain-viewer/widgets/harness.py --all                                      every widget, one line each
python skills/brain-viewer/widgets/harness.py --capture                                  refresh the fixtures from the live server
```

`--json` prints the report as JSON; `--verbose` prints warnings on a passing run too. It needs `node` and jsdom
(`npm install` in `skills/brain-viewer/`, which reads `package.json`; `node_modules/` is git-ignored).

What a run does, in order: `node --check` on the file; boot the page (this is **mount**); run the board's own
`refreshAll()` (**refresh**); call the widget's `resize()` if it has one (**resize**); then look at the tile.

A run FAILS (exit 1) on any of:

| line in the report | what it means | what to do |
| --- | --- | --- |
| `error (node --check): SyntaxError: ...` | the file does not parse | fix the syntax at the line shown |
| `error (register): the file did not register id "x"` | no register call ran, or it used another id | make `id` equal the filename |
| `error (mount / refresh / resize): ...` with a stack | something threw, including later from a timer or a handler | the stack's first `static/widgets/<file>.js:line:col` is your line |
| `the tile went red (where): ...` | the page's own guard caught a throw or a failed read, the same red tile the owner would see | as above; `where` says `mount`, `refresh`, `later`, `fail` or `GET <path>` |
| `no fixture: /api/x (would be fixtures/x.json)` | the widget reads an endpoint with no canned answer | add it to `CAPTURE` in harness.py and run `--capture`, or save the live answer by hand |
| `unbound: text still holds a placeholder: "undefined"` | a value the widget never filled reached the page | you read a field that is not in the shape; check section 4 or the fixture |
| `unbound: attribute d on <path> holds "NaN"` | a drawing computed with a missing number | guard the input, or give the drawing a width (the harness gives every element 960 by 320) |
| `unbound: a loading line was left standing` | a "loading" text was never replaced | replace it on every path, including the empty one |
| `unbound: the body stayed empty and the widget did not hide itself` | it read something and drew nothing | draw a `note` for the empty case, or call `api.show(false)` |

It only WARNS on: an empty element carrying a `data-*` hook (often a slot filled later on purpose), a write the widget
made (a POST or PUT is answered with an empty ok and never reaches a server), a resource that did not load, and
jsdom's "not implemented" notices. Read the warnings anyway.

A passing run ends with the widget's own reads, then the reads the page made on its own:

```text
ok   tally      3 endpoints
  read: /api/calls, /api/projects, /api/waiting
  the page itself read: /api/badges, /api/glossary, /api/quests
```

`--all` prints one line per widget and a closing line, `harness: 30 of 30 widgets hold`, or the failing ids. Exit 0
when everything holds, 1 when something does not, 2 when the harness itself cannot run (no node, no jsdom).

What the harness does not prove: how it looks. jsdom lays nothing out and paints nothing, so a widget that passes can
still be ugly or overflow its tile. After the harness passes, open the home page, press edit, add it, and look.

## 6. The definition of done

A widget file goes live only when all of these hold:

1. `node --check skills/brain-viewer/widgets/<id>.js` passes.
2. `python skills/brain-viewer/widgets/harness.py skills/brain-viewer/widgets/<id>.js` passes, with no unbound parts.
3. `python skills/brain-viewer/home.test.py` passes. It runs `harness.py --all` as its ninth claim, so a new widget
   that breaks, or one that breaks an old one, fails the suite.
4. The `id` it registers equals its filename stem, and it registers exactly once.
5. Anything outside the `register()` call is inside `(function () { ... })();`. Wrapping the whole file is the safe
   default.
6. The readme's rules hold: a shape of its own, nothing on the page explaining the page (that goes in `source`), no
   ids, codes, markdown or em dashes in anything a person sees, every color a token, and no throw on a 403.
7. Every endpoint it reads has a fixture, and any new endpoint is added to the catalogue in section 4.

Build a draft outside the folder first and point the harness at it: the harness serves the file under test from
wherever it is. Copy it into `widgets/` only once it passes, because the moment it is in the folder it is on every
board's add list.

## 7. What the board shows when a widget breaks

`home.html` guards every widget (T-0217). A break is any of:

- `mount` or `refresh` throws, or the promise it returns rejects;
- `api.get` fails for any reason but a 403: a non-2xx answer or no answer at all. A widget that catches the failure
  itself (as tally's `soft` does) still breaks the tile, because a read that fails is a fault worth seeing;
- `api.fail(e)` is called with anything but a 403;
- a throw later, from a widget's timer, event handler or unawaited promise, traced to its file by the stack.

What happens then:

1. **The tile goes red-edged.** A 3px `--danger` left edge; the body is hidden and in its place a `--danger-tint` box
   shows the error's first line, then two links: **open the file** (the widget's source, as the server serves it at
   `/static/widgets/<id>.js`, in a new tab) and **ask the builder to fix** (it opens the chat on the Brain Viewer project
   and sends a builder the file path, the error, and the instruction to read this curriculum and pass the harness).
2. **The server is told once.** The page POSTs `{id, file, error, where, stack}` to `/api/widgets/broken`, once per
   widget and error per page load.
3. **A finding lands on the brain-viewer ledger.** The server files one `@claude` task, source `brain-viewer`, key
   `widget-broken:<id>:<8-character hash of the error's first line>`. The same widget and error reported again lands
   on that open item as a repeat (`repeats:N` and a dated line), never a second item, and inside an hour of the last
   write nothing is written at all, so a reload of a broken board does not pile up lines. A different error on the same
   widget is a different finding.
4. **The System panel's widgets lamp goes red** while any break is younger than an hour, and names the broken widgets
   in its hover. Otherwise it is lit and reads "all whole".
5. **The tile mends itself** on the next minute tick whose refresh runs clean. The finding stays open until someone
   fixes the file and closes it.

To see it on purpose: add `throw new Error("test")` to a draft's mount and run the harness on the draft. The report
shows `the tile went red (mount): test`. Do not do this to a file in the folder while the server is running, because the
live board would file a real finding.
