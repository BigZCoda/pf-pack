#!/usr/bin/env python
"""serve.py -- the Brain Viewer's local server.

  python skills/brain-viewer/serve.py            # http://127.0.0.1:8765
  python skills/brain-viewer/serve.py --port 8770
  python skills/brain-viewer/serve.py --brain "C:\\path\\to\\a\\brain"          # read ANOTHER folder as the brain
  python skills/brain-viewer/serve.py --brain "C:\\path\\to\\a\\brain" --init   # ...and create what it is missing first

WHICH FOLDER IS THE BRAIN (2026-09-16)
  The code does not have to live inside the folder it reads. `--brain <path>`, else the BRAIN_ROOT environment
  variable, else `brain_root` in skills/brain-viewer/viewer-settings.json, else the folder the code sits in (the
  original arrangement). Code assets -- the pages, the stylesheet, the vendored library, the chat prompts, tasks.py
  and log.py -- resolve against the code folder; everything else, including the registry, the manifests, the forge
  root, the ledgers, the log and the token files, resolves against the brain. `--init` creates, in the brain folder,
  the handful of files the viewer needs to boot, and never overwrites one that is already there.

Pages
  /            Home                      (home.html): a dashboard of widgets. Each widget is one file in skills/brain-viewer/widgets/ reading one endpoint;
               which ones are on, in what order and at what size is the layout file viewer/layouts/<member>.json, edited with the pencil.
               In a TEAM COPY the home stays the Mentee Content Dashboard (mentee-dashboard.html): every mentee-facing piece in program order, editable in place
  /chat        Chat                      (chat.html): the conversations with the brain's agents, unchanged -- it was the home page until 2026-09-21
  /call        The call               (call.html, 0.47.0): one call on one flat page for while you are on it -- the call, its join press, a card per person, what is due, the questions as boxes that tick into the prep file, the points per person, the notes box bound to the prep's ## Your notes. ?prep=<deliverables/call-prep/...md> or ?date=YYYY-MM-DD&start=<ISO>. Reads GET /api/call; writes POST /api/call/tick and POST /api/call/notes
  /today       Today                     (today.html): the day on one page -- every open question addressed to the owner across the ledgers with the BLOCKING ones first, everything due today or earlier plus the held items coming back today, EVERY open task of the owner's across the ledgers regardless of date grouped by project (T-0185), what the PF App is holding for review, today's calls with their preps, the transcripts that landed today with their intake state, and the day's closed items folded at the bottom. The ledger sections are composed in the browser from /api/projects (the page IS the ledgers read back); the open-tasks block comes from /api/today/tasks and writes through POST /api/today/tasks/action; the three outside halves come from /api/pending, /api/calls and /api/landed, each read at request time and stored nowhere; the app's review queue is approved and rejected in place through POST /api/pending/action
  /canvases    Canvas Viewer             (canvas-viewer.html): the architecture canvases drawn where they sit (pan, zoom, edges, colors, drill-through)
  /holons      Holons                    (holons.html): context/holon-registry.json as a tree; per holon its stamp vs frontmatter, rules, agent runbook, status file, children
  /status      Status                    (holons.html, status view): every machine-written status file the registry names, checks + age, read as-is
  /projects    Projects                  (projects.html): every project ledger the registry names (a holon's `tasks` field): progress per milestone and owner, questions answered and boxes checked here
  /requests    Requests                  (requests.html): the inbox -- what another person's viewer sent into a shared exchange repository, per exchange, newest first (2026-09-16) -- above every change request under requests/<member>/ (what a team copy proposed, or what came back after a pull), newest first
  /people      People                    (people.html): what is open for the owner about a person FIRST, then the card (collapsed section by section) and the dated call preps; the standing call threads (groups) above the individuals; New prep writes one from the cards
  /agents      Agents                    (agents.html): the orchestration view -- every recent Claude Code session on this machine, the sub-agents it spawned with their model, status, duration and the answer each returned; the last action per brain agent id; the open @claude tasks across the ledgers. Off the nav since 0.9.0 (folded into /chat as the "Running now" strip); the route still answers
  /chat        Chat                      (chat.html): talk to the brain's main agent, or to one project's agent, from the app -- every conversation is a real Claude Code session started here (`claude -p`, this machine, this account), streamed as it answers; the main agent routes questions onto the right ledgers and dispatches project work to sub-agents; past conversations per project; ?project=<id> opens a project chat
  /map         Map (the bubbles)         (map.html): RETIRED 2026-09-09 evening, off the nav, the route still answers -- the moving physics graph of that morning, replaced by the live maps below (the owner asked for several maps, each an existing canvas read against real state)
  /maps        Maps                      (maps.html): the picker -- the canvases that are maps, grouped by purpose as skills/brain-viewer/maps-manifest.json declares them (information flow, apps and services, the OS, machines, the daily workflow), each with how many nodes are bound, how many are concept, how many were active today, and an "open live" link; every other canvas folded by family; opens on the group whose map was active most recently
  /live        Live map                  (forge.html in live mode): one canvas drawn by the Forge's circular renderer, READ-ONLY, with three layers that can all be on at once -- intent (as drawn), build (every node tinted by what it is bound to: a file, a holon, a skill, an agent, a route, an outside service; unbound nodes dashed and marked concept; click opens the thing), runtime (nodes lit by the last 14 days of evidence, brighter for today, a count badge, "quiet 14d" on the rest; a line active today carries a gold bubble travelling along it, the one moving element on the screen). Hover a node for its binding and the last three log lines. ?path=<canvas>
  /findings    Findings                  (findings.html): every OPEN ledger item carrying a `#source:` tag, across every ledger the registry names, most-repeated then oldest first. Read-only; findings are triaged at rounds Step 0.5 on the ledger they already live on
  /review      Review                    (review.html): the rating surface -- Claude's proposals as cards the owner rates with one press (good / off / wrong, one optional line), without typing a reply, or leaves a line on with no answer at all (the `note only` press and Ctrl+Enter, on a fresh card and on a rated one). A card's face shows what the item says NOW; the rewrite and rating markers on its note sit behind a `history` press. Two card kinds: a CLOSURE (an open `#test` item the viewer proposes closing, with the evidence beside it) and a REVIEW (any open item carrying `#review`). A rating writes a `rated ... (viewer, <day>): ...` line onto the item through tasks.py, and a closure rated good is checked off as well; every rating is also appended to brain-viewer-holon/ratings/<day>.jsonl. A rated card no longer disappears: it sits in the `Rated` fold at the bottom with its verdict, its day and a `change` press, and a different answer writes a SECOND jsonl line (never a rewritten first), reopens a closure that was checked off, or closes one that is open. A closure rated OFF also files one @claude task to rewrite that test, idempotent by `#key:retest:<id>`. The auto-close bar the owner set (18 of the last 20 good) is counted and shown on the page and acted on by NOTHING in this build
  /reader      Reader                    (reader.html): one brain .md opened AS ONE PAGE (0.54.0) -- real headings at one measure, the outline rail with a scroll-spy, Edit and Ask in the margin, one agent-layer switch, and on every list item a strike and a move up/down that rewrite that one line in the file. ?path=<brain-relative .md>#<heading slug> opens at a section, which is what a ledger's "-> file.md#slug" link points at (a section ask); "Ask about this section" writes the question back onto a project ledger carrying that link
  /glossary    Glossary                  (glossary.html): the vocabulary, meant to sit in a narrow second window beside the work -- search, the groups from the seed with a glyph and a live example beside each term, a how-it-fits diagram whose labels are themselves hover targets, and the Keys section naming every hotkey. Opened by the "?" button in every page's top bar; ?from=<page> opens the group that page belongs to and leaves the rest folded
  /studio      Studio                    (studio.html, 2026-09-22, T-0235): the image studio -- prompts in, pictures out through the providers in skills/brain-viewer/providers/ (the folder is the registry); pictures land in deliverables/studio/<job>/. 403 on every studio route in a team copy
  /files       Files                     (files.html, 2026-09-28, T-0259): every file in the brain in one table, newest first, every column sorts; the folder tree and type chips filter, the box filters by path; a row opens in the Reader, the lightbox, the canvas viewer, or downloads

API (read)
  GET  /api/manifest                       skills/brain-viewer/mentee-content-manifest.json (+ mtimes, existence)
  GET  /api/file?path=<brain-relative>     text of a .md / .canvas / .json / .txt file under the brain (never the token files, never archive/)
  GET  /api/canvas?path=<brain-relative>   a .canvas file's JSON
  GET  /api/canvases                       every .canvas under the forge root (`forge_root` in viewer/settings.json) with family, counts, mtime, header text
  GET  /api/forge/fields?path=<canvas>&node=<cell id>  the loose fields one cell's output can ship, READ from the real thing behind it at request time (the record keys of the .json its sibling names as the output source, or of the .json it is bound to) -- never stored in the drawing. {source, kind, count, fields:[{key, type, sample, group}]}, or 404 saying what to declare when nothing real is behind the cell yet
  GET  /api/holons                         the registry; each holon enriched with exists / mtime / frontmatter + stamp verdict / rules + agent existence / readme / status file parsed + age
  GET  /api/status                         every status file the registry names, parsed as-is, with the age of _generatedAt (the viewer never recomputes status)
  GET  /api/projects                       every ledger the registry names, parsed by skills/brain-tasks/tasks.py, with counts derived at read time
  GET  /api/badges                         {people: {slug: n}, projects: {id: {questions, zak_tasks}}, total_questions, ...}: the open items waiting on the owner, counted per person and per project (the nav counts, and what the bubbles read)
  GET  /api/graph                          {nodes, edges, counts, generatedAt}: the bubbles. Nodes typed project | person | group | document | chat | copy | agent, each with label, badge, href, a two-line summary; children (dashboard pieces, canvases, preps) carry `parent`; people with nothing open carry `quiet`. Edges typed item | member | child | under | holds | chat | shared | session | running. Joined at read time from the registry, the ledgers, the cards, the groups file, the manifest, the canvases, the chat index, the team-brain status file and the session transcripts; stored nowhere. In a team copy: no people, groups, chats or agents
  GET  /api/review                         the rating surface: {cards[], rated[], presses, shown, waiting, sitting, counter, ratedTotal, autoClose: {bar, of, enforced}, rule} -- the cards waiting to be rated (kind, the proposal in one sentence, what changes, the evidence, who proposed it, age), `untested` (open stale tests with no rebuild behind them, which are NOT cards), the per-kind tally of the last 20 ratings, and the rule the cards were built by. A card's `note` is what the item says NOW; the rewrite and rating markers appended to it come back separately as `history`. A card already rated never comes back as a NEW card; it comes back in `rated[]`, the fold, with its latest verdict, its day and where the item stands now
  POST /api/review                         one rating: {card: "<project>:<id>", verdict: good|off|wrong, note?} -- or {card, undo: true}, which takes back the newest rating on that card if it was written in the last 90 seconds (a change is changed back; a first rating gets an `undone` line in the ratings file, a `rating undone` line on the item, the item reopened if the rating checked it off, and an off's rewrite task closed as withdrawn) -- or, with NO verdict, {card, note} alone, which writes `note (viewer, <day>): <text>` onto the item through tasks.py and does nothing else: no ratings line, no counter, no state move, the card keeps whatever answer it had (400 when the text is empty). The card is re-read on the server, the line is composed here (the day comes from this machine's clock), an existing keep-in-mind line is kept and the rating added after it; a CLOSURE rated good is then checked off through tasks.py, one rated off is left open and gets a rewrite task filed for it. The SAME route changes an answer: a card already rated is found among the ratings instead, the line says `changed from <old>`, the ratings file gets a second line, and the item is reopened or closed to match. The record is appended to brain-viewer-holon/ratings/<day>.jsonl and one DECISION line goes to the log. 403 in a team copy
  GET  /api/resolve?name=<leaf name>       brain-relative path for a unique leaf filename (how bare [[wikilinks]] resolve)
  GET  /api/image?path=<brain-relative>    bytes of a .png/.jpg/.jpeg/.gif/.webp/.svg under the brain with its content type (the in-app image viewer, T-0014); same exclusions and path rules as /api/file
  GET  /api/files?folder=&type=&q=&sort=&order=   the Files page (0.52.0, T-0259): every file under the brain except .git, node_modules, __pycache__ and the key files, each {path, name, folder, extension, type, size, modified, last: {at, agent, action} from the newest log line naming it}; newest first by default. /api/file and /api/image also read what it lists outside the live folders, read-only
  GET  /api/file-raw?path=<brain-relative>  a listed file's bytes as a download (xlsx, docx, pdf, psd and the rest); a path outside the brain, in a skipped folder, or a key file is refused 403
  GET  /api/app/<endpoint>?token=admin|personal   proxied GET to the PF App (checkin-templates, presets, contacts, tasks, action-items, users); tokens never leave the server; 403 in propose mode (no token file is read there)
  GET  /api/today/tasks                    every OPEN task of the owner's on every registered ledger regardless of date, grouped by project in the registry's order, newest first in a group; the ones the Today page's dated block already shows are left out (dedupe by ledger + id), the ones carrying `#call:<slug>` are left out and counted into `calls` / `callPeople` because they belong in that person's call prep (T-0192), and the ones on hold are held back by open_for_zak(). `?app=1` answers instead with the PF App's review-queue count alone (GET /api/v1/action-items?status=suggested on the personal token, cached 10 minutes), which is the one line at the block's foot
  POST /api/today/tasks/action             {"ledger": <holon id or its ledger path>, "id": "T-0123", "action": "done"|"hold"} -- one press on a row of that block. The ledger comes from the registry, the item is re-read off the file before the write, and tasks.py does the write plus its own one log line (agent brain-viewer); hold takes the tool's own three days
  GET  /api/pending                        the PF App's action items still waiting for review, FOLDED PER CONVERSATION (504 items over 61 conversations, so never a flat list): one group per conversation with its title, count and newest day, its items inside it. GET /api/v1/action-items?status=suggested on the personal token, cached 60 seconds
  POST /api/pending/action                 {"id": "<action item id>", "action": "approve"|"reject"} -- one press on one item, straight to the app: POST /api/v1/action-items/:id/status with ?dryRun=1 first (so 400/403/404/409 come back as a sentence with nothing written) and then for real. One SYNCED line in context/log.md per write. Approve-all is the page pressing this once an item at a time
  GET  /api/call?prep=|?date=&start=     the call screen's read (0.47.0): {event {date,start,end,title,join,calendarLink}, people [with role and where it stands], prep {due, questions [{subject, items [{line, checked, text}]}], points, notes, sections}, refs, aliases, defaultProject, canWrite}
  POST /api/call/tick                      {path, line, checked, text}: that question line becomes - [x] / - [ ]; 409 when the line changed since the page read it
  POST /api/call/notes                     {path, text}: the prep's ## Your notes section becomes the text (the skeleton's comment kept)
  GET  /api/calls                          today's calls: context/today-calendar.json as the /start-session recap wrote it (start, end, title, attendees), each attendee matched to a people/ card and each event to a dated prep in deliverables/call-prep/. Absent file, or one written for another day, is reported as such -- the server never reaches a calendar itself
  GET  /api/landed                         the transcripts whose filename carries today's date, in transcripts/ and pf-app-holon/transcripts/, with their intake state: the import-checkup report in transcripts/import-reports/ (exact stem match, or a same-day report sharing a name word, marked as the weaker match) or nothing yet
  GET  /api/mode                           {"mode": "normal"} or {"mode": "propose", member, tier, exported_at, source_commit, ...} from team-brain.json
  GET  /api/requests                       every request file under requests/<member>/ (member, at, kind, target, note), newest first, capped at 200; both modes
  GET  /api/exchange                       what the other side sent: every item addressed to `owner` in each exchange viewer-settings.json names in `exchanges`, newest first, composed from the manifests at request time (folders BESIDE the brain; 403 in a team copy)
  POST /api/exchange/pull                  fast-forward those exchanges and report what arrived (runs skills/exchange/pull.py; writes nothing into the brain but its log line; 403 in a team copy)
  GET  /api/people                         every people/*.md card: slug, name, role, the Where-it-stands line with its date and whether it is stale, last contact and call frequency, newest dated fold, flag count, prep count (403 in propose mode: people/ never travels with a team copy)
  GET  /api/person?slug=<slug>             one card in two sides (front: the standard sections in draw order; back: the history, an old Status section included), the Where-it-stands line, last contact and cadence, the next call, folds, owed lines, flags, that person's preps, and openItems: every open question and open @<owner> task across the ledgers that concerns them
  GET  /api/preps[?key=<group id or slug>] the dated preps in deliverables/call-prep/, newest call first
  GET  /api/groups                         the standing call threads in skills/call-prep/call-prep-groups.json, each with its members resolved to cards, the newest transcript whose participants include ALL members, and its preps
  GET  /api/chats                          every conversation in context/chats/ (index rows: project, title, session id, turns, cost, dispatched ledger items), newest first, + the routable projects, the models the installed CLI accepts (sonnet the default, probed at startup), what every turn carries as fixed context, which chats have a turn running; 403 in propose mode
  GET  /api/chat?id=<chat id>              one conversation: its index row + the history read from its Claude Code transcript (turns with tool calls, the sub-agents it spawned); 403 in propose mode
  GET  /api/agents                         {sessions, brain_agents, on_ledgers, chats, handoffs}: the newest 30 session transcripts within 14 days parsed for their Agent spawns and the answers those returned, the last log.md line per agent id, and every open @claude ledger task. Each session also carries the conversation it is (chat id, project, title) and whether it can be opened in the chat (adopt: {ok, reason}); handoffs are the send-to lines between conversations read off the index. Read-only, cached per file mtime, secrets masked; 403 in propose mode
  GET  /api/session?id=<session id>        ONE Claude Code session read back read-only: its header (title, model, turns, cwd, branch), its history as turns with the tool calls between, the sub-agents it spawned, the conversation row if the app already has one, and adopt: {ok, reason}. What a double-click on a bubble opens; 403 in propose mode
  GET  /api/docasks?path=<brain-relative>  every OPEN ledger item whose link points at this document, with the heading fragment it names: what the Reader badges in its outline (a section ask). Matched on path only; the slug half is matched in the page, where the headings are cut
  GET  /api/notes[?limit=8]                the notes the notepad has written, newest first (path, first words, when taken): what the panel lists so a note can be reached again
  GET  /api/note?path=<a note in thoughts/notepad/>  ONE note split the way the notepad edits it: {path, title, taken, body, pictures, mtime, editable} -- the header lines the file keeps, the body that can be changed, the pictures under it
  GET  /api/glossary                       {groups, terms, keys}: brain-viewer-holon/brain-viewer-glossary.md parsed at request time -- one source, no cache, no second copy. A term carries its aliases, definition, example, Septabee analog, group and anchor; a group carries the pages that open it. `available: false` where the seed is absent (a team copy)
  GET  /api/live?path=<canvas>             the live layers of one canvas: per node {binding: {kind: file|canvas|folder|holon|skill|agent|route|service|concept, target, label, href, via, exists, mtime, size}, activity: {count14, today, lastAt, lastAction, lastAgent, lines[3], todayScore, active14, + mtime | statusAt | sessionsToday | teamCopy | lastFerry by kind}}, per edge {today, active14}, counts, kinds, the binding order. Bindings cached in memory per canvas mtime; activity re-read from context/log.md (last 14 days) on every call; a binding saved in the sibling .forge.json wins
  GET  /api/adapter?name=ferryman[&twin=0]  the adapter level: one boundary's PORTS, generated -- the data behind all three views of it (one symbol on a canvas, the adapter sheet at /forge?adapter=<name>, the arcs when it sits in a cell). {name, label, app, base, catalog, noCatalog, twin, twinExists, fetchedAt, ageDays, stale, groups:[{resource, mirror, lastRan, tiers:{personal, admin, hollow}, ports:[{method, path, auth, scopes, purpose, callable, tier, source: catalog|manual, callers:[{skill, file, line}], lastRan, mirror:{path, exists, mtime}, health:{state, code, at, via, finding}}]}], drift:[{skill, file, line, path}], skills, counts}. Which adapters exist, their base URLs, their catalogs and their HAND-WRITTEN port groups come from the registry skills/brain-viewer/adapters.json (viewer Q-0024); catalog ports from that adapter's own inventory file (cached by mtime) and manual ports merged in marked source: manual; callers resolved over skills/**/*.py and *.md (literal paths + BASE-relative ones); a group's ports come back in tier order, personal token then admin key then hollow; lastRan from context/log.md, health from the component rounds' probes and the log. Writes the markdown twin (pf-app-holon/pf-app-adapter-<name>.md) from the same answer unless twin=0, and never for an adapter with no catalog
  GET  /api/adapters                       the registry: one row per boundary {name, label, app, base, catalog, catalogExists, twin, twinExists, manualGroups, manualPorts}, read from skills/brain-viewer/adapters.json. An `**Adapter . <name>**` head on any canvas binds to the row whose name matches, case-insensitive
  GET  /api/maps                           the picker: the groups from skills/brain-viewer/maps-manifest.json with each map's live counts and last activity, the other canvases by family, and which group was active most recently
  GET  /static/<file>                      files in this folder (.js .css .html as text; .png .ico as bytes: the sun mark + favicon); /static/vendor/<file>.js serves the one vendored library (force-graph, MIT) from vendor/
  GET  /api/widgets                        the home page's registry: every *.js in skills/brain-viewer/widgets/ (core), then viewer/widgets/ (the person's; a core id is never overridden, the file is listed as user-<id> with a conflict), with what its register() call declares (id = the filename stem, title, size, defaultOn, source). The FOLDER is the registry: drop a file in and it appears
  GET  /static/widgets/<file>.js           one widget file, for the home page to load
  GET  /api/looks                          the looks folders (T-0208): every *.css in skills/brain-viewer/looks/ (default, paper) and in viewer/looks/ (the person's), with {name, url, description, tokens, fonts, ok, error}, the member's `active` look, and the token names a look may set. The FOLDER is the registry: drop a look in and it is offered
  GET  /static/looks/<file>.css            one look file; every page is served with looks/default.css and the member's look linked in its head, ahead of viewer-tokens.css
  POST /api/looks                          {"name", "css", "replace"?, "activate"?} imports a look (one :root block of known tokens, Google Fonts @import allowed, size-capped, name sanitized; default.css never replaced); {"active": "<name>"} saves the member's look into the `look` field of their layout file
  GET  /api/home/layout                    which widgets are on, in what order, at what size, and where the add panel was left: the saved viewer/layouts/<member>.json, or the default built from the folder when there is none
  GET  /api/help                           skills/brain-viewer/help.json: what each page of this app is for, in plain words, with its parts named. The "?" panel on every page reads its own route out of this
  GET  /api/calendar/week                  context/week-calendar.json as the session start wrote it: the next seven days of calendar, each event with its start, end, title and attendees. With no week file, today-calendar.json is answered instead and `source` says so. Like the today file, this server never reaches a calendar itself
  GET  /api/people/week                   the face of /people (round 1b, 2026-10-02): every call in the two calendar files with a carded attendee and its preps, each prep's state in one word (ready, skeleton, held); per card, which of the last four weeks they were on a call (transcripts + the calendar's calls already over); who is weekly (two or more of the four weeks); and the fold each card sits in, from its own frontmatter and the people/readme.md directory. Read-only
  GET  /api/moved                          the tail of context/log.md parsed into rows (time, agent, action, text), newest first: what moved in the brain. `?since=<iso>` keeps only the rows at or after that moment, `?limit=` how many (40 by default, 200 at most), `?agent=<id[,id]>` only what one writer wrote, `?days=<n>` only the rows inside that many days back (reaching into the rotated months when the tail does not go that far)
  POST /api/widgets/broken                 a home tile broke (T-0217): {id, error, where, stack}, sent once per widget and error per page load. Kept in memory for the widgets lamp and filed as ONE finding on the brain-viewer ledger, key widget-broken:<id>:<hash of the error>, a repeat landing on the open item (and nothing written again inside an hour)
  GET  /api/system                         the home page's lamps: one row per part of this brain that runs on its own (the calendar read, the week file, the PF App sync, the night agent, the weekly librarian, git, this app, and since T-0217 the widgets lamp, red while any home tile broke in the last hour) with {id, name, lastRan, cadence, state: lit | dim | red, detail}, computed at request time from those parts' own files, the log and git
  GET  /api/events                         a text/event-stream of context/log.md as it is written: one data event per new line {ts, agent, action, text}, a comment every 15 seconds, ending after an hour so the page reconnects. What the home page's flow map pulses on
  GET  /api/mantras                        projects/pf-build/pf-mantras.md parsed: the pool the home page draws the day's line from, each entry {text, author, source}
  GET  /api/studio/providers              {providers: [{id, name, ready, reason, keyFile, models:[{id, name, sizes | aspects, edits, notes, ...}]}]}: every provider file in providers/, ready false with what to do when its key file (openai_key.txt, gemini_key.txt at the brain root) is absent, or for the local comfy provider when ComfyUI is not running or a model file is missing
  GET  /api/studio/jobs                   {jobs: [{slug, count, latest, candidates, history, images:[{path, url, provider, model, prompt, createdAt, sidecar, candidate, kind}]}]}: read from deliverables/studio/, newest job first
  GET  /api/studio/prompts?path=<.md>     {path, prompts: [{title, text, line, lang}]}: the fenced code blocks of one markdown file, each titled by the nearest heading above it

API (write)
  PUT  /api/manifest                       overwrite the manifest (the Mark-reviewed button)
  PUT  /api/home/layout                    {"widgets": [{id, on, size, collapsed, expanded, settings}, ...], "palette": {x, y, w, h}} saves the home layout for this copy's member (ids checked against the registry, sizes against the column spans, settings as a small object of that instrument's own choices, palette as where the add panel was left); {"reset": true} deletes the file so the default comes back
  POST /api/mantras                        {"text": "...", "author": "...", "source": "..."} appends one line to projects/pf-build/pf-mantras.md (logged MODIFIED); a team copy files it through the request path instead
  PUT  /api/file?path=<brain-relative>     overwrite a file NAMED IN THE MANIFEST, a dated prep in deliverables/call-prep/, or a Reader document (body = new text); appends a MODIFIED line to context/log.md via log.py. `&note=<one line>` names what changed and becomes that log line's text (the Reader sends "Reader: struck ..." / "Reader: moved ...")
  POST /api/prep                           {"slug": "<person>"} | {"group": "<group id>"} | {"participants": ["<slug>", ...]}  (+ "call_date"?, "purpose"?) | {"event_start": "<ISO>"} (0.47.0: the prep for that calendar event, keyed to its carded people)
                                           -> writes deliverables/call-prep/<slug | group id | slug1+slug2>-call-prep-<date>.md from the cards (never overwrites an existing one), logged CREATED
  PUT  /api/tasks?project=<holon id>       one structured ledger mutation {action: add|ask|done|reopen|block|answer, ...} through tasks.py (clock-stamped, logged as brain-viewer); never raw text
  POST /api/chat/send                      {"chat": <id or null>, "project": "main" | <ledger holon id>, "text": "...", "model": "sonnet" (the default) | "opus" | "fable", "from": {"chat": <source id>, "turn": N}?} -> text/event-stream of one turn:
                                           spawns `claude -p --output-format stream-json --include-partial-messages --verbose --model <m> --permission-mode auto --append-system-prompt-file <prompt> --session-id <new uuid> | --resume <id>`
                                           (cwd = the brain root, the message on stdin), relays its lines as SSE data events (start, init, seg, text, text_final, tool, tool_done, done, ledger, stopped | error, end),
                                           writes context/chats/<id>.json when the turn ends (one CREATED log line per conversation, not per turn); one running turn per chat; 10-minute cap; 403 in propose mode.
                                           `from` is a SEND-TO: this message carries another conversation's reply, so the line between the two is written onto both index rows (handoffs) and the agents page draws it
  POST /api/chat/stop                      {"chat": <id>} -> kills the running turn's process tree; 403 in propose mode
  POST /api/chat/adopt                     {"session": "<Claude Code session id>"} -> takes a session on this machine (CLI or app) into the chat rail: one index row
                                           pointing at the transcript it already has, under the project its cwd implies (or Main), logged CREATED; the next turn resumes it by session id.
                                           REFUSED (409) while the transcript has been written inside the last two minutes or a sub-agent of it is still working -- two programs writing one transcript at once corrupt it; 403 in propose mode
  POST /api/notepad                        {"text": "...", "pictures": ["thoughts/notepad/....png"], "page": "projects"} -> ONE NOTE: a dated markdown file in
                                           thoughts/notepad/ with the pictures it names beside it, logged CREATED (spec section 4 decision 14). A request file in a team copy
  PUT  /api/notepad                        {"path": "thoughts/notepad/....md", "text": "..."} -> ONE EXISTING NOTE rewritten in place: only the body changes, the title and
                                           **Taken:** lines and the pictures under them stay exactly as they were, logged MODIFIED (T-0146). It may only write a .md that
                                           ALREADY EXISTS directly inside thoughts/notepad/ -- anything else is refused, and it never creates, renames or deletes a file
  POST /api/paste                          {"name": "clip.png", "data": "<base64>", "kind": "chat"|"note"} -> one picture kept in thoughts/notepad/ under a dated
                                           name, answered with its brain-relative path (and /api/image URL) so the message or note refers to a real file. 12 MB cap, images only, 403 in a team copy
  POST /api/attach                         {"item": "Q-0026", "ledger": "<holon id or its registered ledger path>", "name": "x.png", "data": "<base64>"} -> one picture
                                           attached to a ledger item (T-0219): png/jpg/gif/webp by magic bytes, 12 MB cap, kept at <ledger folder>/attachments/<id>-<yyyymmdd-hhmmss>-<name>,
                                           added to the item's `→ links` through tasks.py (its own log line); answers {path, url, links}. 400 on an unknown ledger or item or a non-image, 403 in a team copy
  POST /api/reply                          {"project": "<holon id>" (or "ledger": "<its registered path>"), "id": "T-0078", "text": "..."} -> a NOTE on a ledger item: the item's `note:` line
                                           through tasks.py (the existing keep-in-mind line kept, the reply added after it, the date read from this machine's clock),
                                           and the item STAYS OPEN. What the reply box beside every task of the owner's writes (T-0078, T-0077). 202 + a request file in a team copy
  POST /api/note                           propose mode only (404 otherwise): {"target": "<path or empty>", "text": "..."} -> a `note` request file (a free-text change request about a file the member cannot edit)
  POST /api/live/bindings                  {"path": "<canvas>"} -> the live layer's ONE write: the bindings the server resolved, copied into the canvas's sibling .forge.json as binding: {kind, target} under each node id (a concept node's old binding cleared), one MODIFIED log line; the page sends only the path. 202 + a request file in a team copy
  POST /api/studio/generate               {provider, model, prompt, negative?, size?, n (1..4, default 2), references?: [brain-relative images], job, project?, quality?, imageSize?, seed?}
                                           -> {job, folder, images:[...]}: deliverables/studio/<job>/<yyyymmdd-hhmmss>-<provider>-<model>-<n>.<ext> + a sidecar .json each (candidate false)
                                           + one line in that folder's job.md, one CREATED log line per run. 400 on a bad request or a provider not ready, 502 with the provider's message in one line
  POST /api/studio/edit                   {provider, model, image: <path>, prompt, mask?: <path>, job, negative?, strength? (0 < s <= 1, image to image), seed?} -> the same shape as generate (one picture)
  POST /api/studio/candidate              {path, candidate: true|false} -> flips the flag in that picture's sidecar

PROPOSE MODE (2026-09-08): a team member runs this same viewer over a TEAM COPY of the brain (a git clone written by
skills/team-brain/export.py). There an in-place edit would be overwritten at the next export, so when a file `team-brain.json`
exists at the brain root, every write above writes ONE REQUEST FILE instead of its target and answers 202
{"proposed": true, "request": "requests/<member>/<YYYYMMDD-HHMMSS>Z-<kind>-<slug>.json", "kind", "target"}. The request JSON is
the contract shared with skills/team-brain/pull.py (schema team-brain-request/1: member, at, kind, target, before_sha256, payload,
note, source_export). No team-brain.json -> normal mode, zero behavior change.

USER LAYER (0.48.0): this folder is bedrock, replaced whole by an update. A person's settings, layouts, looks and widgets
live in viewer/ at the brain root (created on first start, seeded once from the legacy files in this folder when a brain
still has them), and no update writes there. Contract: brain-viewer-plugin-contract.md (in this folder as shipped; brain-viewer-holon/ in the maintainer brain).

Design: every page links /static/viewer-tokens.css, the one file that holds the viewer's fonts and colors.
Local only (127.0.0.1). Reads are broad but read-only; writes are manifest-scoped. Every write is logged. Git is the undo.
On startup writes brain-viewer-holon/brain-viewer-status.json (machine-written; trust = _generatedAt) when that folder exists (it is a private holon and may be absent from a team copy).
"""
import argparse
import atexit
import base64
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
# The folder the CODE sits in (this file is <code>/skills/brain-viewer/serve.py). Every page, script, stylesheet,
# vendored library, chat prompt and sibling tool (tasks.py, log.py) is found from HERE/CODE; the CONTENT is found from
# BRAIN below. Until 2026-09-16 the two were the same folder by definition, which meant the only way to read a brain
# was to copy the code into it.
CODE = os.path.dirname(os.path.dirname(HERE))
# ---- BEDROCK and the USER LAYER (0.48.0, 2026-09-23) ----
# This folder (skills/brain-viewer/) is BEDROCK: the viewer as it ships in the pf-pack component brain-viewer, replaced
# WHOLE by an update. Nothing a person makes lives in here any more. What a person makes -- their settings, their board
# layouts, the looks they imported or wrote, the widgets they wrote -- lives in the USER LAYER, `viewer/` at the root of
# the brain, which no update ever writes. serve.py creates that folder and a default settings file on first start.
# Contract doc: brain-viewer-plugin-contract.md (shipped in this folder; brain-viewer-holon/ in the maintainer brain). The legacy paths below are read ONCE, to seed the
# user layer on a brain that still has them, and never written again.
USER_REL = "viewer"
SETTINGS_REL = USER_REL + "/settings.json"
LEGACY_SETTINGS_REL = "skills/brain-viewer/viewer-settings.json"
USER_LAYOUTS_REL = USER_REL + "/layouts"
USER_LOOKS_REL = USER_REL + "/looks"
USER_WIDGETS_REL = USER_REL + "/widgets"
# The widget contract number this viewer implements. A widget declares `contract: N` in its register call; the page
# reddens one whose number is missing or higher ("written for a newer viewer"). Additions to the api stay within a
# number; a rename or a removal bumps it.
WIDGET_CONTRACT = 1



def load_settings(ap):
    """One viewer-settings.json read: the user-adjustable settings. A missing or unreadable file means defaults --
    the viewer never fails to start over a settings file."""
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


CODE_SETTINGS = load_settings(os.path.join(HERE, "viewer-settings.json"))


def resolve_brain():
    """WHICH FOLDER THE VIEWER READS AS THE BRAIN (2026-09-16). Four sources, first one wins:
        1. --brain <path>   on the command line
        2. BRAIN_ROOT       in the environment (the same variable tasks.py and log.py read, so a child process agrees)
        3. brain_root       in this code copy's skills/brain-viewer/viewer-settings.json
        4. the folder the code sits in -- the original arrangement, and what this brain keeps doing.
    The flag is read here by hand rather than by argparse because BRAIN is a module constant: every path in this file
    hangs off it, and `import tasks as ledger` below needs it, both long before main() runs."""
    raw = ""
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--brain" and i + 1 < len(argv):
            raw = argv[i + 1]
        elif a.startswith("--brain="):
            raw = a.split("=", 1)[1]
    raw = (raw or os.environ.get("BRAIN_ROOT") or str(CODE_SETTINGS.get("brain_root") or "")).strip().strip('"')
    return os.path.abspath(os.path.expanduser(raw)) if raw else CODE


BRAIN = resolve_brain()
# Every child process -- tasks.py, log.py, a chat's Claude Code -- reads this, so the folder a tool writes into can
# never disagree with the folder this server is reading.
os.environ["BRAIN_ROOT"] = BRAIN
# The settings a BRAIN carries for itself (owner, forge_root, the prep horizon) layered over the code copy's own file.
# `brain_root` is read from the code copy alone, since it is the thing that names the brain. When the code sits inside
# the brain -- the owner's arrangement -- these are one and the same file and nothing changes.
SETTINGS = dict(CODE_SETTINGS)
# 0.48.0: the brain's settings are viewer/settings.json. A brain that has not been started since the split still has
# them at the legacy path inside the code folder; they are read from there until the first start copies them across.
_user_settings = os.path.join(BRAIN, SETTINGS_REL.replace("/", os.sep))
_legacy_settings = os.path.join(BRAIN, LEGACY_SETTINGS_REL.replace("/", os.sep))
_settings_src = _user_settings if os.path.isfile(_user_settings) else _legacy_settings
if os.path.normcase(_settings_src) != os.path.normcase(os.path.join(HERE, "viewer-settings.json")):
    SETTINGS.update({k: v for k, v in load_settings(_settings_src).items() if k != "brain_root"})
else:
    SETTINGS = dict(CODE_SETTINGS)

# Where the Forge's drawings live, as a SETTING rather than a constant (2026-09-16): this brain keeps them in the
# ProspectForge architecture folder, another copy of the viewer can keep them somewhere plainer like `canvases/`.
# One value feeds the canvas list, the Forge's write scope and the maps picker, so a copy moves all three together.
# 0.48.0 (the layout check): with no setting, the first of these folders that exists, else `canvases`. The second is
# this brain's own place for its drawings, kept only so a copy with no settings file still finds them.
def _default_forge_root():
    for cand in ("canvases", "projects/pf-build/architecture"):
        if os.path.isdir(os.path.join(BRAIN, cand.replace("/", os.sep))):
            return cand
    return "canvases"


ARCH_REL = (str(SETTINGS.get("forge_root") or _default_forge_root()).replace("\\", "/").strip("/")
            or _default_forge_root())
# Who this brain treats as "me" (2026-09-16): the @name in the owner dropdowns, the Today count, the Waiting-on-you
# list and the home link. A SETTING rather than a literal, so a copy of the viewer answers to its own owner;
# skills/brain-tasks/tasks.py reads the same key, and an item's owner line still stores whatever @name it was given.
# ON A TEAM COPY BOTH OF THESE ARE SETTLED AGAIN once team-brain.json has been read (0.37.1, search for DEFAULT_OWNER
# below MEMBER): the member the copy was exported for is its owner, whatever @name the exported settings carry.
DEFAULT_OWNER = "@me"   # 0.48.0: a brain with no `owner` setting answers to @me, never to this brain's own owner
OWNER = ("@" + str(SETTINGS.get("owner")).strip().lstrip("@")) if str(SETTINGS.get("owner") or "").strip() else DEFAULT_OWNER
STATUS_REL = "brain-viewer-holon/brain-viewer-status.json"
REGISTRY_REL = "context/holon-registry.json"
# The content declarations the viewer renders (0.48.0, the layout check). They are the brain's, not the app's, so a
# brain may keep them in context/; the older place inside the code folder is still read when that is where they are.
# A missing file is an empty declaration, never an error.
def _declared(setting, leaf, legacy):
    v = str(SETTINGS.get(setting) or "").replace("\\", "/").strip("/")
    if v:
        return v
    for cand in ("context/" + leaf, legacy):
        if os.path.isfile(os.path.join(BRAIN, cand.replace("/", os.sep))):
            return cand
    return legacy


MANIFEST_REL = _declared("mentee_manifest", "mentee-content-manifest.json", "skills/brain-viewer/mentee-content-manifest.json")
PEOPLE_REL = "people"                 # the cards: one .md per person, the truth about that person (Correction #42)
CALLPREP_REL = "deliverables/call-prep"   # the dated preps derived from them (format: skills/call-prep/call-prep-format.md)
GROUPS_REL = "skills/call-prep/call-prep-groups.json"   # the standing call threads: the owner confirms them, the panel only renders them
TRANSCRIPT_DIRS = ("transcripts", "pf-app-holon/transcripts")   # the raws, and the app mirror whose JSON carries an explicit participants array
INTAKE_REL = "transcripts/import-reports"   # the import-checkup report per transcript: the runbook's retained artifact, and what "intaken" means
CALENDAR_REL = "context/today-calendar.json"   # MACHINE-WRITTEN by the /start-session recap (the calendar is reachable only through the Claude Code MCP tool, never from here)
CALENDAR_WEEK_REL = "context/week-calendar.json"   # the same hand, seven days wide (schema brain-calendar-week/1): what the home page's dial draws past today
TEAM_REL = "team-brain.json"          # present at the brain root only in a team copy (written by skills/team-brain/export.py) -> propose mode
REQUESTS_REL = "requests"             # requests/<member>/<stamp>-<kind>-<slug>.json
LOG_REL = "context/log.md"
# The log rotates monthly (structure-pass Batch 2, 2026-09-18, brain-central Q-0037): context/log.md
# holds the CURRENT month, everything older sits at archive/ledgers/YYYY-MM/log-YYYY-MM.md. Every
# reader in this file goes through log_lines() below so a 14-day window that crosses a month
# boundary reads the same lines it read before the rotation.
LEDGERS_REL = "archive/ledgers"
# ---- the Reader (2026-09-09, the straight line step 2b, ledger T-0046) ----
# The owner asked for a module in the app to view a properly organized .md, with the ability to strike and reorder
# lines, as an organized habit for moving projects forward.
# The write scope is NAMED here, not guessed: the folders whose .md files hold decisions for the owner. Two exclusions are
# load-bearing -- a project ledger (*-tasks.md) is written by skills/brain-tasks/tasks.py alone (rules 4), and
# context/log.md is append-only through skills/brain-log/log.py (the clock is read in the same call that writes).
# The write list as a TABLE (2026-09-22, ledger T-0220): the owner hit a note in thoughts/ that could not be fixed in
# place, so the list now names the folders the owner edits by hand and keeps the gate on the ones that must stay agent-written. One row per
# folder prefix: (prefix, editable, the one-line reason the Reader shows). The longest matching prefix decides; a prefix
# whose first segment is "*-holon" covers every ledger holon folder. The next widening is a row here, not a hunt.
# Rules that beat any row (in reader_write_rule below): a path with ".." or a drive or a leading slash; a .contract.json;
# any *-tasks.md ledger; context/log.md; a file at the brain root (the five key files, every *.txt, CLAUDE.md, index.md,
# zak-brain.md, zak-corrections-log.md, operational-playbook.md and the rest); anything that is not .md.
READER_WRITE = (
    ("thoughts/",                 True,  "the owner's own thinking, the notepad included"),
    ("questions/",                True,  "the owner's open questions"),
    ("deliverables/",             True,  "things made for a person to read, send or paste"),
    ("people/",                   True,  "the person cards the owner corrects by hand"),
    ("profiles/",                 True,  "the profiles the owner corrects by hand"),
    ("projects/",                 True,  "project notes and specs"),
    ("*-holon/",                  True,  "a holon's own notes (its ledger stays with tasks.py)"),
    ("pf-app-holon/transcripts/", False, "the app's transcript mirror, written by the Ferryman pull"),
    ("pf-app-holon/pf-app-adapter-", False, "the adapter sheet, rewritten by a script on every pull (T-0226)"),
    ("context/",                  False, "agent-written state file"),
    ("skills/",                   False, "code and skill specs, changed by an agent"),
    ("archive/",                  False, "archived dated record, never edited"),
    ("transcripts/",              False, "raw transcript, the record of a call"),
)
READER_DIRS = tuple(p.rstrip("/") for p, ok, _ in READER_WRITE if ok)   # what the status page names as the Reader's scope
# ---- the Forge (2026-09-09, the straight line step 3, ledger T-0041) ----
# The design surface: a canvas edited in the app and saved back to the same .canvas file Obsidian reads. The write scope
# is the architecture folder alone (any family folder under it, never a loose file at its root), two extensions only:
# the drawing (.canvas, JSON Canvas: nodes + edges) and its sibling .forge.json, which holds what JSON Canvas has no
# field for (a cell's stage, a part's doc, bindings later), keyed by node id and written by the Forge alone. A missing
# sibling means every cell is at stage concept. Types ride in the drawing itself the way the womb-phase canvases already
# do it: a text node's first line is **<Type> · <Name>** and the color preset per group (UI 3, running 5, minds 6,
# stores 4, hooks 1, assumed output 2), so nothing the Forge writes is invisible to Obsidian.
# ---- what the owner captures inside the viewer (2026-09-10, the notepad T-0074 + pictures in chat T-0079) ----
# A note taken in the app, and a picture pasted into a note or into a chat message, are the owner's own capture, so they live
# in the owner's own thinking folder rather than in a state folder or in deliverables: `thoughts/notepad/`, one dated file per
# note with its pictures beside it. The folder carries its own .contract.json and readme (spec section 4, decision 14),
# which is what a write-gate check reads. Nothing else in the brain is written by these two routes.
CAPTURE_REL = "thoughts/notepad"
CAPTURE_IMG = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
CAPTURE_MAX = 12 * 1024 * 1024        # one pasted picture; a screenshot is a few hundred KB and a phone photo a few MB
FORGE_ROOT = ARCH_REL
FORGE_EXT = (".canvas", ".forge.json")
FORGE_STAGES = ("concept", "prototype", "built", "stable")
FORGE_INNER = ("outer band", "inner layer")   # nested groups inside a cell: the band (what people see) and the core (what runs); not cells themselves
# The home page is a dashboard of widgets (2026-09-21, the home redesign). The owner asked for it to be more dynamic and
# less text-heavy, showing what is going on in the day and letting a user move every component around.
# The chat keeps its own full page at /chat, unchanged. The mentee content dashboard is at /mentee.
# In a team copy there is no chat at all (rules 4), so the copy's home stays the mentee dashboard.
PAGES = {"/": "home.html", "/index.html": "home.html", "/today": "today.html", "/mentee": "mentee-dashboard.html", "/canvases": "canvas-viewer.html",
         "/holons": "holons.html", "/status": "holons.html", "/projects": "projects.html", "/requests": "requests.html",
         "/agents": "agents.html", "/people": "people.html", "/chat": "chat.html", "/map": "map.html",
         "/glossary": "glossary.html", "/reader": "reader.html", "/forge": "forge.html",
         "/maps": "maps.html", "/live": "forge.html", "/findings": "findings.html",
         "/review": "review.html", "/studio": "studio.html", "/call": "call.html", "/files": "files.html"}   # /live = the Forge's renderer in its read-only live mode (step 4); /map = the retired moving graph, off the nav
HOME_ROUTES = ("/", "/index.html")
APP_BASE = "https://app.prospectforge.us/api/v1"
# 2026-09-24: the app's edge (Cloudflare) answers 403 error 1010 to any request with no User-Agent; app_get, app_post and the
# browser proxy all send "brain-viewer/<VERSION>". Found when /api/pending and the prep writer's contacts read went 403 today.
TOKENS = {"personal": os.path.join(BRAIN, "PF App API.txt"), "admin": os.path.join(BRAIN, "pfk_key.txt")}
# contacts + tasks joined the allow-list 2026-09-09 for the People panel: a prep names the app's Action Items for the person
# (the app calls them tasks on the personal token; /action-items is the admin route and is not used here).
APP_ALLOW = {"checkin-templates": "admin", "presets": "personal", "contacts": "personal", "tasks": "personal",
             "action-items": "personal", "users": "admin"}   # 2026-09-16, the Today page: the app's review queue, and the account the settings name (T-0150)
# The ONE write the viewer makes to the PF App (2026-09-18, T-0017): approve or reject one suggested action item, on the
# personal token, on the caller's own items. An id is all that varies -- the path is built here, never sent in from a page.
APP_POST_ALLOW = {"action-item-status": ("action-items/%s/status", "personal")}
READ_EXT = {".md", ".canvas", ".json", ".txt"}
IMAGE_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}
# GET /static/<file>: the viewer's own folder only (basename, no paths). Text files are decoded; the sun mark + favicon go out as bytes.
STATIC_TEXT = {".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8"}
STATIC_BYTES = {".png": "image/png", ".ico": "image/x-icon"}
# 2026-09-22 (image studio, T-0235): the image-provider keys, read only by skills/brain-viewer/providers/.
# 2026-09-22 (later): fal_key.txt joined, the fal.ai provider.
NEVER_READ = {"APIZZLE.txt", "PF App API.txt", "pfk_key.txt", "deepseek_key.txt", "Onboarding API.txt",
              "openai_key.txt", "gemini_key.txt", "fal_key.txt"}
SKIP_DIRS = {".git", "node_modules", "archive", ".obsidian", "__pycache__", ".claude"}
VERSION = "0.59.0"
# ---- the home page's widgets (2026-09-21, the home redesign) ----
# THE REGISTRY IS THE FOLDER. Every *.js in skills/brain-viewer/widgets/ is a widget, its id is the filename stem, and
# GET /api/widgets lists them. A file dropped in that folder appears in the app with no other change: nothing here names
# a widget, the head of each file is read for the four things it declares about itself (title, size, defaultOn, source).
WIDGETS_DIR = "widgets"
WIDGET_HEAD = 4000                # how much of a widget file is read for its declaration: the register() call is on top
# 0.37.0: the board is a TWELVE-column grid and a size IS its column span, so a widget says how much of the width it
# takes in the same word the grid uses. The four offered are a third, a half, two thirds and the whole width. The three
# letters the first board used are still accepted on the way in and turned into spans, so a layout saved under 0.36 is
# not thrown away for its sizes.
HOME_SIZES = ("4", "6", "8", "12")
HOME_SIZE_LEGACY = {"S": "4", "M": "6", "L": "12"}
# 0.39.0: a row may also say how many GRID ROWS it takes, which is how a tall instrument stands beside two short ones
# without leaving a hole under them. One or two, nothing else: three would be a layout engine, and the board is a board.
HOME_ROWS = (1, 2)
# The nine that are ON for a person who has never touched the page, in this order: the composition, top to bottom.
# Every other widget in the folder is off and addable in edit mode; a NEW file declaring defaultOn true joins after these.
# 0.38.0: the masthead carries the day itself (its middle slot draws the day, a project track or the week), so the
# sundial and the constellation come off the default board and wait in the add list; Next took the hero the sundial
# carried, System replaced the red strip with a row of lamps, and Flow took the column the constellation sat in.
# The spans pack the twelve columns with no holes. 0.39.0 packs them again around the chat, which took the empty room
# under Next that the tall Answer deck left beside it: 12 / (8 over 8) + 4 standing two rows / 4 + 4 + 4 / 6 + 6 / 12.
# The mantra is second in this order because it draws into the room the masthead keeps under the date, and a widget
# draws in the order the board mounts it; switched on with the masthead off, it takes a full-width line of its own and
# the row still packs. The plain command line came off the default board with the chat: it is still a file, in the add
# list, for whoever wants one line and no conversation.
# The deck is named before the chat because the grid fills forward and never goes back: placed after a full-width-of-
# eight chat it would start on the chat's own row and leave the room beside Next empty. Named here it takes columns
# nine to twelve across both rows and the chat drops in under Next, which is the composition the owner asked for.
HOME_ORDER = ("masthead", "mantra", "next", "deck", "chat", "decide", "people", "horizon", "moved", "flow", "system")
HOME_SCHEMA = "brain-viewer-home-layout/1"
# ---- a widget's own settings (0.38.0) ----
# A row in the layout may carry a small object of that instrument's own choices -- which drawing its slot shows, which
# project its track follows, which form its numbers wear. It rides with the layout, so a choice survives a reload and
# travels to another browser with the board. Small on purpose: this is a preference, never a place to keep data.
HOME_SETTINGS_KEYS = 24           # how many keys one widget's settings may hold
HOME_SETTINGS_CHARS = 2000        # ... and how long the whole object may be, written out
# ---- the add panel, where it was left (0.40.0) ----
# The same reasoning one level up: in edit mode the add list becomes a window that is dragged and pulled bigger, and
# where it was left is an arrangement of the board, so it is saved beside the widgets rather than in one browser.
HOME_PALETTE_KEYS = ("x", "y", "w", "h")
HOME_LAYOUT_FMT = USER_LAYOUTS_REL + "/%s.json"   # one file per member, in the user layer (0.48.0): the layout is per person, not per browser
LEGACY_LAYOUT_FMT = "skills/brain-viewer/home-layout-%s.json"   # where it was until 0.48.0; read once, to seed the user layer
HELP_REL = "skills/brain-viewer/help.json"                    # what each page is, in plain words: GET /api/help, the "?" panel
# ---- staying up, and saying why when it does not (2026-09-17, ledger T-0181) ----
# The viewer died twice without leaving a word: exit code 4 on 2026-09-11 at 20:27 after eight hours of ordinary 200s,
# and again some time after 2026-09-16 17:59, found down the next morning. Neither left a traceback, and neither COULD.
# The exit paths in this file are: main() returning 0 (Ctrl+C, or serve_forever coming back) or 2 (no such brain folder),
# argparse exiting 2 on a bad flag, and an uncaught exception exiting 1. NOTHING here can produce a 4 -- so the 4 came
# from OUTSIDE the process: whatever owned the console killed it (a background task torn down with its session, a sleep,
# a logoff). The night agent's own read of the 9/11 death says the same thing: ordinary 200s to the last second.
# Two halves, then:
#   1. EVERY way out leaves a record. sys.excepthook, a SIGTERM / SIGBREAK handler and an atexit hook each append one
#      dated line to the crash log -- code, reason, pid, uptime -- with the traceback indented under it when there is one.
#   2. --supervise runs serve.py as a CHILD and puts it back whenever it exits non-zero, waiting 2, 4, 8, 15, 30, 60
#      seconds and resetting that once a child has held for ten minutes. A clean 0 (Ctrl+C) stops the supervisor with it.
# The status file and GET /api/health both report the last record, so a morning session can see that it went and why.
CRASH_REL = "brain-viewer-holon/viewer-crash.log"
STARTED_AT = dt.datetime.now().astimezone()
SUPERVISE_BACKOFF = (2, 4, 8, 15, 30, 60)
SUPERVISE_STABLE = 600        # a child that held this long resets the wait: a restart loop and a long life are not the same fault
_exit_written = False
PREV_RUN = "unknown"
CRASH_HEAD_RE = re.compile(r"^\[([^\]]+)\] (EXIT|RESTART|START) code=(\S+) reason=(.*?) pid=(\d+) uptime=(\d+)s who=(\S+)")


def crash_abs():
    return os.path.join(BRAIN, CRASH_REL.replace("/", os.sep))


def crash_note(kind, code=None, reason="", tb="", who="server"):
    """One dated record in brain-viewer-holon/viewer-crash.log, appended. The first line is machine-readable
    (`[iso] KIND code=N reason=... pid=N uptime=Ns who=...`) and a traceback is indented four spaces under it."""
    global _exit_written
    try:
        if not os.path.isdir(os.path.dirname(crash_abs())):
            return ""      # a team copy has no brain-viewer-holon/: nowhere to write, and nothing worth saying about that
        up = int((dt.datetime.now().astimezone() - STARTED_AT).total_seconds())
        head = "[%s] %s code=%s reason=%s pid=%d uptime=%ds who=%s version=%s port=%s" % (
            dt.datetime.now().astimezone().isoformat(timespec="seconds"), kind,
            "-" if code is None else code, " ".join(str(reason or "-").split())[:300],
            os.getpid(), up, who, VERSION, getattr(ARGS, "port", "?") if "ARGS" in globals() else "?")
        with open(crash_abs(), "a", encoding="utf-8", newline="\n") as f:
            f.write(head + "\n")
            for line in (tb or "").rstrip().split("\n"):
                if line.strip():
                    f.write("    " + line + "\n")
        if kind == "EXIT":
            _exit_written = True
        return head
    except Exception:
        return ""


def _crashed(rec, prev):
    """Did this ending mean something was WRONG (0.37.1)? A child killed from outside -- which is how a reload happens,
    `taskkill` on the child under --supervise -- and a child that threw both leave the supervisor's
    `RESTART code=<non-zero>` line, and the codes overlap (1 and 4294967295 are both seen for a kill), so the code
    cannot tell them apart. The TRACEBACK can: a dying child writes its own EXIT record with the traceback indented
    under it, and Windows gives a terminated process no chance to write anything at all. So a RESTART with no such
    EXIT in front of it is a restart, not a fault, and the home page's lamp for this app stays green for it (0.38.0:
    the same flag, read now by GET /api/system where the red strip used to read it)."""
    def fault(r):
        if not r or not r["tb"] or r["m"].group(3) in ("0", "-"):
            return False
        reason = r["m"].group(4) or ""
        return not (reason.startswith("signal ") or "killed from outside" in reason)   # a signal is a kill, with a stack
    if rec["m"].group(2) == "EXIT":
        return fault(rec)
    return bool(prev and prev["m"].group(2) == "EXIT" and fault(prev))   # the supervisor's line: the fault is the child's


def last_exit():
    """The newest EXIT or RESTART record in the crash log, read back for the status file and GET /api/health. The log is
    the single source -- there is no second file to go stale -- and a log nobody has written reads as None, not as 'fine'.
    `traceback` says whether that record carried a stack under it and `crash` whether it was a fault at all (_crashed)."""
    try:
        ap = crash_abs()
        if not os.path.isfile(ap):
            return None
        with open(ap, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-500:]
        recs = []
        for l in lines:
            m = CRASH_HEAD_RE.match(l.rstrip("\n"))
            if m:
                recs.append({"m": m, "tb": False})
            elif recs and l.startswith("    ") and l.strip():
                recs[-1]["tb"] = True       # the traceback the dying process indented under its own record
        for i in range(len(recs) - 1, -1, -1):
            rec = recs[i]
            m = rec["m"]
            if m.group(2) == "START":
                continue
            return {"at": m.group(1), "kind": m.group(2), "code": m.group(3), "reason": m.group(4),
                    "pid": int(m.group(5)), "uptimeSeconds": int(m.group(6)), "who": m.group(7),
                    "traceback": rec["tb"], "crash": _crashed(rec, recs[i - 1] if i else None), "log": CRASH_REL}
        return None
    except Exception:
        return None


def prev_run():
    """How the LAST run ended, read off the crash log: "clean" (it wrote an exit line), "no-exit-line" (it did not, so it
    was killed from outside -- the shape of both silent deaths, 9/11 and 9/16), or "first-run". Windows gives a process no
    chance to write anything when it is terminated outright, so the absence of a line IS the evidence and is reported as such."""
    try:
        ap = crash_abs()
        if not os.path.isfile(ap):
            return "first-run"
        with open(ap, "r", encoding="utf-8", errors="replace") as f:
            kinds = [m.group(2) for m in (CRASH_HEAD_RE.match(l.rstrip("\n")) for l in f.readlines()[-500:]) if m]
        kinds = [k for k in kinds if k in ("START", "EXIT", "RESTART")]
        if not kinds:
            return "first-run"
        return "clean" if kinds[-1] in ("EXIT", "RESTART") else "no-exit-line"
    except Exception:
        return "unknown"


def install_exit_recorders():
    """Every way out of this process leaves a line. Called from main(), so importing serve.py (the tests do) changes nothing."""
    def hook(etype, val, tb):
        crash_note("EXIT", code=1, reason="%s: %s" % (etype.__name__, val),
                   tb="".join(traceback.format_exception(etype, val, tb)))
        sys.__excepthook__(etype, val, tb)
    sys.excepthook = hook

    def bye():
        if not _exit_written:
            crash_note("EXIT", code=0, reason="interpreter exit, no exception: a clean stop, or the console that owned this process went away")
    atexit.register(bye)

    def sig(signum, frame):
        crash_note("EXIT", code=128 + signum, reason="signal %d: killed from outside" % signum,
                   tb="".join(traceback.format_stack(frame)))
        os._exit(128 + signum)
    for name in ("SIGTERM", "SIGBREAK"):   # Ctrl+C stays with KeyboardInterrupt in main(); atexit records that one
        n = getattr(signal, name, None)
        if n is None:
            continue
        try:
            signal.signal(n, sig)
        except Exception:
            pass
    crash_note("START", code=0, reason="serving on port %s; the previous run: %s" % (
        getattr(ARGS, "port", "?") if "ARGS" in globals() else "?", PREV_RUN))


def port_answers(port, host="127.0.0.1"):
    """Is something already listening on this port? (0.47.0, T-0186). Windows lets a second server bind a port the first
    still holds (SO_REUSEADDR), and the stale one then answers old routes, so a viewer started at logon while one is
    already up must not start at all. A connect is the whole test: nothing is sent."""
    h = "127.0.0.1" if host in ("", "0.0.0.0") else host
    try:
        with socket.create_connection((h, int(port)), timeout=1.0):
            return True
    except OSError:
        return False


def supervise(argv):
    """--supervise: run serve.py as a child and put it back when it falls over. Nothing here answers a request -- the child
    is an ordinary `python serve.py <the same flags minus --supervise>` and everything it writes it writes itself."""
    wait_i, n = 0, 0
    port = getattr(ARGS, "port", 8765) if "ARGS" in globals() else 8765
    if port_answers(port, getattr(ARGS, "host", "127.0.0.1") if "ARGS" in globals() else "127.0.0.1"):
        # the logon task and a hand-started viewer both reach here; the second one leaves the first alone (T-0186).
        # No crash-log line: this is not the running viewer exiting, and /api/health reads that log's last EXIT.
        sys.stderr.write("supervisor: port %s already answers, so a viewer is running; nothing started\n" % port)
        return 0
    crash_note("START", code=0, reason="supervisor up, watching a child on port %s" % (getattr(ARGS, "port", "?") if "ARGS" in globals() else "?"), who="supervisor")
    sys.stderr.write("supervisor: restarting the viewer whenever it exits non-zero; every exit and restart lands in %s\n" % CRASH_REL)
    while True:
        started = time.time()
        try:
            r = subprocess.call([sys.executable, os.path.abspath(__file__)] + list(argv), cwd=os.getcwd(),
                                env=dict(os.environ, BV_SUPERVISED="1"))
        except KeyboardInterrupt:
            crash_note("EXIT", code=0, reason="supervisor stopped by Ctrl+C", who="supervisor")
            return 0
        held = int(time.time() - started)
        if r == 0:
            crash_note("EXIT", code=0, reason="child stopped cleanly after %ds; the supervisor stops with it" % held, who="supervisor")
            return 0
        if held >= SUPERVISE_STABLE:
            wait_i = 0
        wait = SUPERVISE_BACKOFF[min(wait_i, len(SUPERVISE_BACKOFF) - 1)]
        wait_i += 1
        n += 1
        line = crash_note("RESTART", code=r, reason="child exited after %ds; restart number %d in %ds" % (held, n, wait), who="supervisor")
        sys.stderr.write((line or "child exited %s, restarting in %ds" % (r, wait)) + "\n")
        try:
            time.sleep(wait)
        except KeyboardInterrupt:
            crash_note("EXIT", code=0, reason="supervisor stopped by Ctrl+C while waiting", who="supervisor")
            return 0


# ---- file search (2026-09-17, ledger T-0158) ----
# The owner asked for a file search like Obsidian's, shaped for this brain's purpose. Grep over the LIVE files --
# archive/ and the rest of SKIP_DIRS are out, the token files are out (NEVER_READ), and only the extensions the viewer can
# already open are read. A name match ranks above a text match, and a hit carries the line it was found on so the Reader
# can open there. Read at request time, cached nowhere: the brain is small enough that a walk is cheaper than a stale index.
SEARCH_EXT = (".md", ".canvas", ".json", ".txt")
SEARCH_MAX = 50
SEARCH_BYTES = 2 * 1024 * 1024       # a file larger than this is scanned for its name only: context/log.md alone is megabytes
SEARCH_SNIPPET = 220


def search_api(q, limit=SEARCH_MAX):
    q = (q or "").strip()
    if len(q) < 2:
        return {"q": q, "count": 0, "items": [], "capped": False, "error": "type at least two characters"}
    needle = q.lower()
    needle_b = needle.encode("utf-8")
    t0 = time.time()
    names, texts, scanned, skipped = [], [], 0, 0
    for dirpath, dirs, files in os.walk(BRAIN):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            if not fn.lower().endswith(SEARCH_EXT) or fn in NEVER_READ:
                continue
            ap = os.path.join(dirpath, fn)
            rel = os.path.relpath(ap, BRAIN).replace(os.sep, "/")
            if rel.split("/")[0] in SKIP_DIRS:
                continue
            hit_name = needle in rel.lower()
            if hit_name:
                names.append({"path": rel, "line": 1, "snippet": rel, "why": "name",
                              "mtime": _search_mtime(ap), "matches": 1})
            # the read is in BYTES and only a file that actually carries the words is decoded: over ~1000 files that
            # is the difference between a box that answers as you type and one that does not (measured 2026-09-17)
            try:
                if os.path.getsize(ap) > SEARCH_BYTES:
                    skipped += 1
                    continue
                with open(ap, "rb") as f:
                    blob = f.read()
            except Exception:
                continue
            scanned += 1
            if needle_b not in blob.lower():
                continue
            body = blob.decode("utf-8-sig", "replace")
            first, count = None, 0
            for i, line in enumerate(body.split("\n"), 1):
                if needle in line.lower():
                    count += 1
                    if first is None:
                        first = (i, line)
            if first and not hit_name:
                texts.append({"path": rel, "line": first[0], "snippet": _search_snip(first[1], q), "why": "text",
                              "mtime": _search_mtime(ap), "matches": count})
            elif first and hit_name:
                names[-1].update(line=first[0], snippet=_search_snip(first[1], q), matches=count, why="name+text")
    names.sort(key=lambda r: (len(r["path"]), r["path"].lower()))
    texts.sort(key=lambda r: (-r["matches"], r["mtime"] or "", r["path"].lower()))
    items = names + texts
    return {"q": q, "count": len(items), "items": items[:limit], "capped": len(items) > limit,
            "limit": limit, "files": scanned, "tooBig": skipped, "ms": int((time.time() - t0) * 1000),
            "note": "names first, then text; live files only (archive/ and the token files are never read)"}


# ---- the Files page (2026-09-28, ledger T-0259, viewer 0.52.0) ----
# The owner asked for a file viewer that shows every file inside the brain and sorts them properly, because a
# double click on a file on the computer opens it in a native application. GET /api/files lists EVERY file (archive/ and the dot folders included: this is the whole tree, not the
# live-files search) except .git, node_modules, __pycache__, the key files (NEVER_READ) and any *_key.txt. Each row
# carries the last log line that names its path. The walk is read at request time and cached nowhere (measured at the
# build: about 1,850 files in well under a second); the log index is cached on the log file's own mtime and size.
FILES_SKIP_DIRS = {".git", "node_modules", "__pycache__"}
FILES_TYPES = ("md", "txt", "json", "canvas", "png", "jpg", "xlsx", "docx", "py", "js", "html")
FILES_TYPE_ALIAS = {"jpeg": "jpg"}
# text the Reader shows READ-ONLY for the Files page, beside the four it already reads (READ_EXT)
FILES_VIEW_EXT = {".py", ".js", ".html", ".csv", ".css"}
FILES_LOG_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] \[([A-Za-z0-9_.-]+)\] ([A-Z]+) -- (.*)$")
FILES_PATH_RE = re.compile(r"[A-Za-z0-9_.\-/\\]+\.[A-Za-z0-9]{1,8}")
_FILES_LOG = {"key": None, "index": {}}


def files_hidden(name):
    """A key file never appears on the Files page and is never served from it: the five at the root, the provider keys,
    and anything named *_key.txt."""
    return name in NEVER_READ or name.lower().endswith("_key.txt")


def files_abs(rel):
    """Any file under the brain the Files page may serve: no traversal, no drive, not inside a skipped folder, not a key.
    The resolved path must still sit inside the brain (a link pointing out is refused)."""
    rel = norm(rel)
    if not rel:
        return None
    parts = rel.split("/")
    if any(p in FILES_SKIP_DIRS for p in parts) or files_hidden(parts[-1]):
        return None
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    root = os.path.normcase(os.path.realpath(BRAIN))
    real = os.path.normcase(os.path.realpath(ap))
    if real != root and not real.startswith(root.rstrip(os.sep) + os.sep):
        return None
    return ap


def files_view_abs(rel):
    """The Reader's wider read, for a file opened from the Files page: a text file anywhere files_abs admits (archive/
    included), in READ_EXT or FILES_VIEW_EXT. Never a write: the Reader's saves still go through writable()."""
    ap = files_abs(rel)
    if not ap or os.path.splitext(ap)[1].lower() not in (READ_EXT | FILES_VIEW_EXT):
        return None
    return ap


def files_type(ext):
    e = ext.lower().lstrip(".")
    e = FILES_TYPE_ALIAS.get(e, e)
    return e if e in FILES_TYPES else "other"


def files_log_index():
    """{path: {at, agent, action}} for the newest log line naming each path, rebuilt only when context/log.md changes."""
    ap = os.path.join(BRAIN, LOG_REL.replace("/", os.sep))
    try:
        st = os.stat(ap)
    except OSError:
        return {}
    key = (ap, st.st_mtime, st.st_size)
    if _FILES_LOG["key"] == key:
        return _FILES_LOG["index"]
    idx = {}
    with open(ap, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            m = FILES_LOG_RE.match(line.rstrip("\n"))
            if not m:
                continue
            row = {"at": m.group(1), "agent": m.group(2), "action": m.group(3)}
            for tok in FILES_PATH_RE.findall(m.group(4)):
                tok = tok.replace("\\", "/")
                while tok.startswith("./"):
                    tok = tok[2:]
                idx[tok] = row      # the file is read oldest first, so the last line naming a path wins
    _FILES_LOG["key"], _FILES_LOG["index"] = key, idx
    return idx


def files_walk():
    """Every file the Files page lists, as rows, unsorted."""
    rows, root_len = [], len(BRAIN.rstrip("\\/")) + 1
    log = files_log_index()
    for dirpath, dirs, files in os.walk(BRAIN):
        dirs[:] = [d for d in dirs if d not in FILES_SKIP_DIRS]
        for fn in files:
            if files_hidden(fn):
                continue
            ap = os.path.join(dirpath, fn)
            try:
                st = os.stat(ap)
            except OSError:
                continue
            rel = ap[root_len:].replace(os.sep, "/")
            folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
            ext = os.path.splitext(fn)[1].lower()
            rows.append({"path": rel, "name": fn, "folder": folder, "extension": ext.lstrip("."), "type": files_type(ext),
                         "size": st.st_size,
                         "modified": dt.datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
                         "last": log.get(rel)})
    return rows


def files_filter(rows, folder="", ftype="", q=""):
    """?folder= a folder and everything under it ("." the root's own files only); ?type= one chip, or several comma
    separated; ?q= a case-insensitive substring of the path."""
    folder = (folder or "").strip().strip("/")
    types = {t.strip().lower() for t in (ftype or "").split(",") if t.strip()}
    types = {FILES_TYPE_ALIAS.get(t, t) for t in types}
    needle = (q or "").strip().lower()
    out = []
    for r in rows:
        if folder == ".":
            if r["folder"]:
                continue
        elif folder and not (r["folder"] == folder or r["folder"].startswith(folder + "/")):
            continue
        if types and r["type"] not in types:
            continue
        if needle and needle not in r["path"].lower():
            continue
        out.append(r)
    return out


FILES_SORT_KEYS = {
    "name": lambda r: (r["name"].lower(), r["path"].lower()),
    "folder": lambda r: (r["folder"].lower(), r["name"].lower()),
    "type": lambda r: (r["type"], r["extension"], r["name"].lower()),
    "size": lambda r: (r["size"], r["name"].lower()),
    "modified": lambda r: (r["modified"], r["path"].lower()),
    "last": lambda r: (((r.get("last") or {}).get("agent") or "~"), ((r.get("last") or {}).get("at") or "")),
}


def files_sort(rows, key="modified", desc=None):
    """Newest modified first by default; size largest first; every other column A to Z. desc flips it. files.html sorts
    by the same keys in the browser, so the first paint and this order agree."""
    key = key if key in FILES_SORT_KEYS else "modified"
    if desc is None:
        desc = key in ("modified", "size")
    return sorted(rows, key=FILES_SORT_KEYS[key], reverse=bool(desc))


def files_api(folder="", ftype="", q="", sort="modified", order=""):
    t0 = time.time()
    rows = files_walk()
    walk_ms = int((time.time() - t0) * 1000)
    total = len(rows)
    rows = files_sort(files_filter(rows, folder, ftype, q), sort, None if order not in ("asc", "desc") else order == "desc")
    return {"count": len(rows), "total": total, "items": rows, "types": list(FILES_TYPES) + ["other"],
            "canvasRoot": ARCH_REL, "ms": int((time.time() - t0) * 1000), "walkMs": walk_ms,
            "now": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "skipped": sorted(FILES_SKIP_DIRS), "hidden": "the key files and any *_key.txt"}


FILES_RAW_TYPES = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                   ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                   ".psd": "image/vnd.adobe.photoshop", ".zip": "application/zip"}


def _search_mtime(ap):
    try:
        return dt.datetime.fromtimestamp(os.path.getmtime(ap)).strftime("%Y-%m-%d")
    except Exception:
        return None


def _search_snip(line, q):
    line = line.rstrip()
    i = line.lower().find(q.lower())
    if i < 0 or len(line) <= SEARCH_SNIPPET:
        return line[:SEARCH_SNIPPET]
    start = max(0, i - 60)
    return ("..." if start else "") + line[start:start + SEARCH_SNIPPET] + ("..." if start + SEARCH_SNIPPET < len(line) else "")
# ---- the glossary (2026-09-09, the straight line step 2, ledger T-0040) ----
# ONE source, and it is markdown the owner can edit in Obsidian or read in the drawer: the seed below is parsed at request
# time, so a save shows up on the next reload and there is no second copy to go stale. Bullet shape:
#   - **Term (alias).** definition. Example: ... Septabee: ...
# `## Heading` opens a group; the italic line under a heading that starts "Where these show up:" names the pages whose
# group the pop-out opens (the filtering rule); `## Keys` parses as `- **key** (pages) -- what it does.`
GLOSSARY_REL = "brain-viewer-holon/brain-viewer-glossary.md"
# Auto-underlining in running prose is a rendering decision, not vocabulary, and these words are too everyday for it
# ("build the map" would point at the Build layer). They keep their entry on /glossary and still hover wherever a page
# marks them deliberately -- the how-it-fits diagram's labels do. A whole group opts out by saying so in its own intro
# line (the picker group does: "not auto-underlined"), which keeps the decision in the owner's file rather than in this one.
HOVER_OFF = {"part", "line", "edge", "build", "intent", "runtime", "log"}
# The audit of 2026-09-24 (T-0196; on 9/18 the glossary test showed many highlighted words that were not the term
# they point at, the ordinary word back among them). A single ordinary
# English word is underlined in running prose far more often where it is NOT the term than where it is, so these come
# off the auto list too. Every one keeps its entry on /glossary, its hover wherever a page marks it on purpose, and
# the explicit marker below. What stays automatic: every multi-word term, and the single words that are the brain's
# own coinages or are almost never used in another sense here (holon, forge, ferryman, ledger, notepad, adapter,
# canvas, registry, blob).
HOVER_OFF |= {"node", "module", "component", "port", "cable", "bundle", "bubble", "cell", "output", "field", "package",
              "packet", "hook", "dispatch", "agent", "conversation", "reply", "panel", "history", "reader", "front",
              "back", "stale", "blocking", "stage", "binding", "symbols"}
# The explicit marker an agent writes when it MEANS the term: {{back}} or {{Where it stands}} renders as the plain word,
# underlined with its definition, whether or not the word is on the auto list. Handled in viewer-common.js glPass.
GL_MARKER = "{{term}}"


def gl_alias_needle(alias):
    """An alias is matched in running prose only when it is a real second name (`central line`, `mouth`), never when it
    is a qualifier on the head (`the box`, `of a card`, `a card`, `the back of a file`), and never when it is itself an
    everyday single word. (T-0196: `a card` and `history` were underlining whole pages.)"""
    a = str(alias or "").strip().lower()
    if not a or re.match(r"^(a|an|the|of)\b", a):
        return False
    return (" " in a or "-" in a) or a not in HOVER_OFF | {"history", "blocked", "adopt", "view", "script", "mouth"}
_resolve_cache = {"t": 0, "map": {}}
sys.path.insert(0, os.path.join(CODE, "skills", "brain-tasks"))   # the tool ships with the CODE; the ledgers it writes live in BRAIN (it reads BRAIN_ROOT, set above)
import tasks as ledger  # noqa: E402  -- the project ledger: parse + structured mutations, one parser for the tool and the viewer

# ---- the exchange (2026-09-16, T-0171): the convention lives in skills/exchange/, imported, never restated here.
# A code copy without that folder simply has no exchange: the page says so and the two routes answer 501.
# ---- the adapter level (2026-09-18, viewer Q-0022): the generator lives beside this file so the
# Ferryman pull can import it too and rewrite the markdown twin without dragging in a web server.
try:
    sys.path.insert(0, HERE)
    import adapter as adapters  # noqa: E402 -- ports, cables and drift, computed from the app's own catalog
except Exception as _ae:        # noqa: BLE001 -- the viewer never fails to start over one layer
    adapters, _ADAPTER_ERR = None, str(_ae)
else:
    _ADAPTER_ERR = None

EXCHANGE_DIR_PY = os.path.join(CODE, "skills", "exchange")
try:
    sys.path.insert(0, EXCHANGE_DIR_PY)
    import exchange_common as xchg  # noqa: E402
except Exception as _e:             # noqa: BLE001 -- the viewer never fails to start over an optional skill
    xchg, _XCHG_ERR = None, str(_e)
else:
    _XCHG_ERR = None


# ---- propose mode: a team copy proposes, it never edits in place ----

def load_team():
    """The team-brain.json at the brain root, or None. Its EXISTENCE switches propose mode on; an unreadable file still
    switches it on (the safe direction: never write in place inside a copy) with member 'unknown'."""
    ap = os.path.join(BRAIN, TEAM_REL)
    if not os.path.isfile(ap):
        return None
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {"member": "unknown", "_error": "team-brain.json is not an object"}
    except Exception as e:
        sys.stderr.write("team-brain.json unreadable (%s); propose mode stays ON with member 'unknown'\n" % e)
        return {"member": "unknown", "_error": str(e)}


TEAM = load_team()
PROPOSE = TEAM is not None
MEMBER = (re.sub(r"[^a-z0-9_-]+", "-", str((TEAM or {}).get("member") or "unknown").lower()).strip("-") or "unknown") if PROPOSE else None
# The owner of a TEAM COPY is the member it was exported for (0.37.1). viewer-settings.json is copied out of the owner's
# brain with the owner's @name in it, so a copy that took its owner from there showed the owner's tasks and questions on
# the member's machine: the member's Today count, Waiting-on-you list and home link were all the owner's. MEMBER is only known here, after
# team-brain.json has been read, which is why the two values are settled a second time instead of once up top.
if PROPOSE:
    DEFAULT_OWNER = "@" + MEMBER
    OWNER = DEFAULT_OWNER


def mode_info():
    if not PROPOSE:
        return {"mode": "normal"}
    return {"mode": "propose", "member": MEMBER, "tier": TEAM.get("tier"), "exported_at": TEAM.get("exported_at"),
            "source_commit": TEAM.get("source_commit"), "viewer_mode": TEAM.get("viewer_mode"), "files": TEAM.get("files"),
            "schema": TEAM.get("schema"), "requests": REQUESTS_REL + "/" + MEMBER + "/"}


def sha256_file(ap):
    try:
        with open(ap, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except (OSError, TypeError):
        return None


def propose(kind, target, payload, note=""):
    """Write one request file instead of the target. Returns its brain-relative path.
    Contract (shared with skills/team-brain/pull.py, schema team-brain-request/1): do not change the shape here alone."""
    now = dt.datetime.now(dt.timezone.utc)
    leaf = os.path.basename((target or "").rstrip("/")) or "general"
    slug = re.sub(r"[^a-z0-9]+", "-", leaf.lower()).strip("-")[:40].rstrip("-") or "general"
    folder = os.path.join(BRAIN, REQUESTS_REL, MEMBER)
    os.makedirs(folder, exist_ok=True)
    base = "%s-%s-%s" % (now.strftime("%Y%m%d-%H%M%SZ"), kind, slug)
    target_ap = os.path.join(BRAIN, target.replace("/", os.sep)) if target else None
    doc = {
        "schema": "team-brain-request/1",
        "member": MEMBER,
        "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": kind,
        "target": target or "",
        "before_sha256": sha256_file(target_ap) if (target_ap and os.path.isfile(target_ap)) else None,
        "payload": payload,
        "note": note or "",
        "source_export": {"exported_at": TEAM.get("exported_at"), "source_commit": TEAM.get("source_commit")},
    }
    body = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    n = 1
    while True:                                   # same second, same kind, same leaf -> -2, -3 ... ; exclusive create so two threads never share a name
        fn = base + (".json" if n == 1 else "-%d.json" % n)
        try:
            with open(os.path.join(folder, fn), "x", encoding="utf-8", newline="\n") as f:
                f.write(body)
            break
        except FileExistsError:
            n += 1
    rel = "%s/%s/%s" % (REQUESTS_REL, MEMBER, fn)
    log_line("%s -- PROPOSED %s %s -> %s (team copy, member %s; not applied here)" % (rel, kind, target or "(no file)", rel, MEMBER), action="CREATED")
    return rel


INBOX_REL = "context/team-requests-inbox.md"
INBOX_FILE_RE = re.compile(r"request file:\s*`([^`]+)`")
INBOX_CLOSE_RE = re.compile(r"^\s*-\s*(applied|rejected):\s*(\d{4}-\d{2}-\d{2})\s*(?:--\s*(.*))?$", re.I)


def request_closures():
    """Which request files are already dealt with -- read from the inbox the pull writes and the owner marks
    (context/team-requests-inbox.md: `- applied:<date>` / `- rejected:<date> -- why`, with the request file named in the
    same block). Declared, not guessed (rules 1): a request nobody has marked is open, and the page shows those first."""
    ap = os.path.join(BRAIN, INBOX_REL.replace("/", os.sep))
    out = {}
    if not os.path.isfile(ap):
        return out
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except OSError:
        return out
    block = []
    for line in lines + ["## "]:
        if line.startswith("## "):
            close, files = None, []
            for b in block:
                m = INBOX_CLOSE_RE.match(b)
                if m:
                    close = {"outcome": m.group(1).lower(), "on": m.group(2), "why": (m.group(3) or "").strip()}
                fm = INBOX_FILE_RE.search(b)
                if fm:
                    files.append(fm.group(1).strip())
            if close:
                for fn in files:
                    out[fn] = close
            block = []
        block.append(line)
    return out


def requests_api():
    """Every request file under requests/<member>/, newest first, capped at 200. Both modes: a team copy sees what it proposed; the owner's side sees what a pull brought back.
    Each row carries whether the inbox says it was applied or rejected, so the page can lead with the ones still open."""
    closures = request_closures()
    root = os.path.join(BRAIN, REQUESTS_REL)
    out = []
    if os.path.isdir(root):
        for member in sorted(os.listdir(root)):
            d = os.path.join(root, member)
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if not fn.endswith(".json"):
                    continue
                rel = "%s/%s/%s" % (REQUESTS_REL, member, fn)
                row = {"file": rel, "member": member, "at": None, "kind": None, "target": None, "note": ""}
                try:
                    with open(os.path.join(d, fn), "r", encoding="utf-8-sig") as f:
                        r = json.load(f)
                    row.update(member=r.get("member") or member, at=r.get("at"), kind=r.get("kind"), target=r.get("target"),
                               note=str(r.get("note") or "")[:120], schema=r.get("schema"), before_sha256=r.get("before_sha256"),
                               source_export=r.get("source_export"))
                except Exception as e:
                    row["error"] = "%s: %s" % (type(e).__name__, e)
                row["closed"] = closures.get(rel)
                out.append(row)
    out.sort(key=lambda r: ((r.get("at") or ""), r["file"]), reverse=True)
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "mode": mode_info()["mode"], "count": len(out),
            "open": sum(1 for r in out if not r.get("closed")), "inbox": INBOX_REL if os.path.isfile(os.path.join(BRAIN, INBOX_REL.replace("/", os.sep))) else None,
            "requests": out[:200]}


# ---- the exchange (2026-09-16, T-0171, first build) ----
# What another person's viewer sent here, read out of the exchange clones viewer-settings.json DECLARES in
# `exchanges` -- folders that sit BESIDE the brain, never inside it. The listing is a READ; the one action is a
# pull, which runs skills/exchange/pull.py and writes nothing into the brain but its own log line (rules 4).
def exchange_state():
    """The configured exchanges as the page needs them: per exchange, every item addressed to the owner, newest
    first, and whether it arrived after the last pull. Composed from the manifests at request time, stored nowhere."""
    me = OWNER.lstrip("@").lower()
    if xchg is None:
        return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "owner": me, "available": False,
                "note": "this copy has no skills/exchange/ folder, so it has no exchange (%s)" % (_XCHG_ERR or ""),
                "exchanges": [], "count": 0, "new": 0}
    rows = []
    for ex in xchg.exchanges_of(SETTINGS, BRAIN):
        row = {"name": ex["name"], "them": ex["them"], "repo": ex["repo"], "path": ex["path"],
               "exists": ex["exists"], "isRepo": ex["isRepo"], "cursor": "", "items": [], "error": None}
        if not ex["exists"]:
            row["error"] = "not cloned on this machine yet"
        else:
            try:
                row["cursor"] = xchg.load_cursor(ex)
                for it in xchg.inbox(ex, me):
                    it["new"] = it["name"] > row["cursor"]
                    row["items"].append(it)
            except OSError as e:
                row["error"] = "%s: %s" % (type(e).__name__, e)
        rows.append(row)
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "owner": me, "available": True,
            "settingsKey": "exchanges", "exchanges": rows,
            "count": sum(len(r["items"]) for r in rows), "new": sum(1 for r in rows for i in r["items"] if i["new"])}


def exchange_pull(name=None):
    """The pull button: skills/exchange/pull.py, in its own process, --json. The script owns the fast-forward and
    the cursor; the server only asks. Nothing in the brain is written here but pull.py's own log line."""
    if xchg is None:
        return 501, {"error": "this copy has no skills/exchange/ folder"}
    script = os.path.join(EXCHANGE_DIR_PY, "pull.py")
    if not os.path.isfile(script):
        return 501, {"error": "skills/exchange/pull.py is not here"}
    cmd = [sys.executable, script, "--json", "--brain", BRAIN]
    if name:
        cmd += ["--exchange", str(name)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=BRAIN,
                           env=dict(os.environ, BRAIN_ROOT=BRAIN))
    except Exception as e:
        return 500, {"error": "pull.py failed: %s" % e}
    try:
        out = json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return 500, {"error": "pull.py answered nothing readable", "stdout": (r.stdout or "")[-400:],
                     "stderr": (r.stderr or "")[-400:]}
    out["ok"] = r.returncode == 0 and "error" not in out
    return (200 if out["ok"] else 400), out


def read_token(kind):
    with open(TOKENS[kind], "r", encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                return line.strip()
    raise RuntimeError("empty token file for %s" % kind)


def app_get(ep, kind=None, timeout=20, query=None):
    """One GET to the PF App through the allow-list, parsed. The token is read here and never leaves the process (rules 3).
    Used by the browser proxy (/api/app/<ep>), by the prep writer, and by the Today page's review read, which is the one
    that needs a `query` (the admin routes take ?userId=). Raises on anything but a 200 with JSON."""
    if ep not in APP_ALLOW:
        raise RuntimeError("endpoint not allowed: %s" % ep)
    if PROPOSE:
        raise RuntimeError("the PF App proxy is off in a team copy")
    url = APP_BASE + "/" + ep + (("?" + urllib.parse.urlencode(query)) if query else "")
    req = urllib.request.Request(url, headers={"User-Agent": "brain-viewer/" + VERSION, "Authorization": "Bearer " + read_token(kind or APP_ALLOW[ep]), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def app_post(name, args=(), body=None, dry=False, timeout=20):
    """One POST to the PF App through the WRITE allow-list -> (status code, parsed body).

    The path is BUILT HERE from APP_POST_ALLOW; a caller passes values (an id), never a path, so nothing a browser sends
    can reach a route this file has not named. `dry=True` adds `?dryRun=1`, which the app validates and reports without
    writing -- the Ferryman's rule that a write is rehearsed first (pf-app-holon/pf-app-ferryman-rules.md, section 8).
    A 4xx comes back as (code, parsed error) rather than raising, because the page prints what it says. The same rules
    file's fake-success trap -- a route that does not exist answers 200 with the website's HTML -- is why a 200 whose
    body will not parse as JSON is turned into a 502 here instead of being read as a successful write."""
    if name not in APP_POST_ALLOW:
        raise RuntimeError("write not allowed: %s" % name)
    if PROPOSE:
        raise RuntimeError("the PF App proxy is off in a team copy")
    tmpl, kind = APP_POST_ALLOW[name]
    path = tmpl % tuple(urllib.parse.quote(str(a), safe="") for a in args)
    url = APP_BASE + "/" + path + ("?dryRun=1" if dry else "")
    req = urllib.request.Request(url, data=json.dumps(body or {}).encode("utf-8"), method="POST",
                                 headers={"User-Agent": "brain-viewer/" + VERSION, "Authorization": "Bearer " + read_token(kind), "Accept": "application/json",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code, raw = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        code, raw = e.code, e.read().decode("utf-8", "replace")
    try:
        return code, json.loads(raw)
    except ValueError:
        if code < 300:
            return 502, {"error": "the app answered %s with something that is not JSON, which is what a route that does "
                                  "not exist looks like here" % code, "body": raw[:200]}
        return code, {"error": raw[:300]}


def manifest():
    """The content manifest, or an empty one when this brain has none (0.48.0: a brain that never made a mentee content
    dashboard is not a broken brain; every page that reads this drew a 500 on a shell-shaped brain before)."""
    ap = os.path.join(BRAIN, MANIFEST_REL.replace("/", os.sep))
    if not os.path.isfile(ap):
        return {"stages": [], "_missing": MANIFEST_REL}
    with open(ap, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def registry():
    """The holon registry, or an empty one when this brain has none yet (0.48.0, same reason as manifest())."""
    ap = os.path.join(BRAIN, REGISTRY_REL.replace("/", os.sep))
    if not os.path.isfile(ap):
        return {"holons": [], "_missing": REGISTRY_REL}
    with open(ap, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_allowed():
    paths = {MANIFEST_REL}
    for st in manifest().get("stages", []):
        for p in st.get("pieces", []):
            if p.get("path"):
                paths.add(p["path"])
    return paths


def norm(rel):
    rel = (rel or "").replace("\\", "/").strip()
    if not rel or ".." in rel.split("/") or rel.startswith("/") or ":" in rel:
        return None
    return rel


def read_abs(rel):
    """Broad read: any .md/.canvas/.json/.txt under the brain except token files, archive/, .git/, .claude/."""
    rel = norm(rel)
    if not rel:
        return None
    parts = rel.split("/")
    if parts[0] in SKIP_DIRS or os.path.basename(rel) in NEVER_READ or os.path.splitext(rel)[1].lower() not in READ_EXT:
        return None
    return os.path.join(BRAIN, rel.replace("/", os.sep))


def image_abs(rel):
    """An image under the brain, served as bytes for the in-app image viewer: same path rules and skipped folders as read_abs; never a token file."""
    rel = norm(rel)
    if not rel:
        return None
    parts = rel.split("/")
    if parts[0] in SKIP_DIRS or os.path.basename(rel) in NEVER_READ or os.path.splitext(rel)[1].lower() not in IMAGE_EXT:
        return None
    return os.path.join(BRAIN, rel.replace("/", os.sep))


ROOT_REASONS = {n: "a local-only key file, never written from a page" for n in NEVER_READ}
ROOT_REASONS.update({"CLAUDE.md": "the safety net, changed by an agent on the owner's say",
                     "index.md": "the brain's index, kept by the agent that files a new entry point",
                     "zak-brain.md": "the source of truth, changed only by the rounds procedure",
                     "zak-corrections-log.md": "the corrections log, written by an agent when the owner corrects one",
                     "operational-playbook.md": "the procedures, changed by an agent on the owner's say"})


def reader_write_rule(rel):
    """(editable, reason) for a Reader save of this path, from READER_WRITE and the rules that beat any row. The reason is
    the one line the Reader shows beside a file it cannot edit (T-0220)."""
    rel = norm(rel)
    if not rel:
        return False, "not a path under the brain"
    leaf = rel.split("/")[-1]
    if leaf == ".contract.json" or leaf.endswith(".contract.json"):
        return False, "a folder contract, changed by an agent on the owner's say"
    if leaf.endswith("-tasks.md"):
        return False, "the ledger tool is the only writer (skills/brain-tasks/tasks.py)"
    if rel == LOG_REL:
        return False, "the log is append-only through skills/brain-log/log.py"
    if "/" not in rel:
        if leaf in ROOT_REASONS:
            return False, ROOT_REASONS[leaf]
        if leaf.lower().endswith(".txt"):
            return False, "a local-only file at the brain root"
        return False, "a brain-root file, kept by an agent"
    best, seg, tail = None, rel.split("/")[0], rel.split("/", 1)[1]
    for prefix, ok, why in READER_WRITE:
        head, _, rest = prefix.partition("/")
        if (seg.endswith(head[1:]) if head.startswith("*") else seg == head) and tail.startswith(rest):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, ok, why)
    if best is None:
        return False, "not in the Reader's write list (READER_WRITE in serve.py)"
    if best[1] and not rel.lower().endswith(".md"):
        return False, "the Reader edits markdown only"
    return best[1], best[2]


def writable(rel):
    """True when PUT /api/file may overwrite this path. Two scopes, both narrow (rules 4):
       - anything named in the mentee-content manifest (the dashboard's Save), and
       - a dated call prep directly inside deliverables/call-prep/ (the People panel, 2026-09-09), which the panel itself wrote, and
       - a Reader document: whatever reader_write_rule allows from the READER_WRITE table (2026-09-09, widened 2026-09-22 T-0220).
    In a team copy neither people/ nor the prep folder exists, so the call-prep scope is not granted there."""
    rel = norm(rel)
    if not rel:
        return False
    if rel in write_allowed():
        return True
    # the Reader's documents (2026-09-09, T-0046): granted in a team copy too, where the save becomes a request file
    # like every other write -- deliverables/ and context/ do travel with a copy, unlike people/ and the preps below.
    if reader_write_rule(rel)[0]:
        return True
    # the Forge's drawings (2026-09-09, T-0041): a .canvas or its .forge.json sibling inside a family folder under the
    # architecture root; granted in a team copy too, where the save becomes a request file like every other write.
    if forge_path(rel):
        return True
    if PROPOSE:
        return False
    leaf = rel[len(CALLPREP_REL) + 1:]
    return rel.startswith(CALLPREP_REL + "/") and leaf.endswith(".md") and "/" not in leaf


def write_abs(rel):
    rel = norm(rel)
    if not rel or not writable(rel):
        return None
    return os.path.join(BRAIN, rel.replace("/", os.sep))


def capture_slug(s, fallback):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return (s or fallback)[:48].strip("-") or fallback


def capture_name(kind, name, ext):
    """A unique, dated leaf name inside thoughts/notepad/ (leaf names stay globally unique across the brain)."""
    now = dt.datetime.now()
    parts = [now.strftime("%Y-%m-%d"), now.strftime("%H%M")]
    if (kind or "").strip():                     # "chat" / "note" on a picture; a note itself carries only its words
        parts.append(capture_slug(kind, "note"))
    parts.append(capture_slug(os.path.splitext(os.path.basename(name or ""))[0], "picture"))
    base = "-".join(parts)
    folder = os.path.join(BRAIN, CAPTURE_REL.replace("/", os.sep))
    leaf, n = base + ext, 2
    while os.path.exists(os.path.join(folder, leaf)):
        leaf, n = "%s-%d%s" % (base, n, ext), n + 1
    return leaf


def capture_write(leaf, data):
    """Write one captured file (bytes or text) into thoughts/notepad/ and return its brain-relative path."""
    folder = os.path.join(BRAIN, CAPTURE_REL.replace("/", os.sep))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    ap = os.path.join(folder, leaf)
    mode = "wb" if isinstance(data, (bytes, bytearray)) else "w"
    kw = {} if mode == "wb" else {"encoding": "utf-8", "newline": "\n"}
    with open(ap, mode, **kw) as f:
        f.write(data)
    return CAPTURE_REL + "/" + leaf


# ---- pictures attached to a question or an answer (2026-09-22, viewer T-0219) ----
# The owner asked on 2026-09-21 that pictures be attachable to the questions section. A picture belongs to the ledger item it
# was attached to, so it is kept in an attachments/ folder NEXT TO THAT LEDGER (brain-viewer-holon/attachments/,
# projects/pf-build/attachments/, context/attachments/ ...), created on the first upload, and the stored path goes on
# the item as one more `→ link` through tasks.py, which writes its own log line. GET /api/image already serves any
# image under the brain outside SKIP_DIRS, so those folders need no extra allow-list entry to be shown.
ATTACH_DIR = "attachments"
ATTACH_MAGIC = ((b"\x89PNG\r\n\x1a\n", ".png"), (b"\xff\xd8\xff", ".jpg"), (b"GIF87a", ".gif"), (b"GIF89a", ".gif"))


def attach_kind(blob):
    """The extension an image's own first bytes say it is (png / jpg / gif / webp), or None: the name is never trusted."""
    for magic, ext in ATTACH_MAGIC:
        if blob.startswith(magic):
            return ext
    if len(blob) >= 12 and blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return ".webp"
    return None


def attach_save(ledger_ref, iid, name, raw):
    """-> (http status, body). Validates the ledger against the registry, the item against that ledger and the bytes as
    an image, writes <ledger folder>/attachments/<id>-<yyyymmdd-hhmmss>-<name>.<ext>, then links it onto the item."""
    ref = str(ledger_ref or "").replace("\\", "/").strip()
    hit = next((h for h in registry().get("holons", []) if h.get("tasks") and ref and ref in (h["id"], h["tasks"])), None)
    if not hit:
        return 400, {"error": "no registered ledger answers to %r" % ref}
    iid = str(iid or "").strip()
    try:
        path, rel = ledger.resolve(hit["id"])
        it = ledger.find(ledger.parse(ledger.read(path)), iid)
    except ledger.LedgerError as e:
        return 400, {"error": str(e)}
    raw = str(raw or "")
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[-1]
    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception:
        return 400, {"error": "the picture did not arrive as base64"}
    if not blob:
        return 400, {"error": "the picture arrived empty"}
    if len(blob) > CAPTURE_MAX:
        return 413, {"error": "that picture is %.1f MB; the limit here is %d MB" % (len(blob) / 1048576.0, CAPTURE_MAX // 1048576)}
    ext = attach_kind(blob)
    if not ext:
        return 400, {"error": "only a png, jpg, gif or webp picture can be attached"}
    folder_rel = "/".join([p for p in [os.path.dirname(rel).replace("\\", "/"), ATTACH_DIR] if p])
    folder = os.path.join(BRAIN, folder_rel.replace("/", os.sep))
    base = "%s-%s-%s" % (iid, dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
                         capture_slug(os.path.splitext(os.path.basename(str(name or "")))[0], "picture"))
    os.makedirs(folder, exist_ok=True)
    leaf, n = base + ext, 2
    while os.path.exists(os.path.join(folder, leaf)):
        leaf, n = "%s-%d%s" % (base, n, ext), n + 1
    with open(os.path.join(folder, leaf), "wb") as f:
        f.write(blob)
    stored = folder_rel + "/" + leaf
    links = list(it.get("links") or []) + [stored]
    try:
        ledger.apply(path, rel, "link", agent="brain-viewer", id=iid, links=links)
    except ledger.LedgerError as e:
        os.remove(os.path.join(folder, leaf))
        return 400, {"error": str(e)}
    return 200, {"ok": True, "path": stored, "project": hit["id"], "ledger": rel, "id": iid, "bytes": len(blob),
                 "url": "/api/image?path=" + urllib.parse.quote(stored), "links": links}


def notes_api(limit=8):
    """The notes the notepad has written, newest first: what it lists under the box so a note can be reached again."""
    folder = os.path.join(BRAIN, CAPTURE_REL.replace("/", os.sep))
    out = []
    if os.path.isdir(folder):
        for fn in os.listdir(folder):
            if not fn.endswith(".md") or fn == "readme.md":
                continue
            ap = os.path.join(folder, fn)
            title, when = "", ""
            try:
                with open(ap, "r", encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("# "):
                            title = line[2:].strip()
                        elif line.startswith("**Taken:**"):
                            when = line[len("**Taken:**"):].strip()
                        elif title and when:
                            break
            except OSError:
                continue
            out.append({"path": CAPTURE_REL + "/" + fn, "title": title or fn[:-3], "taken": when,
                        "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")})
    out.sort(key=lambda r: r["path"], reverse=True)
    return {"folder": CAPTURE_REL, "count": len(out), "notes": out[:limit]}


def notepad_write(text, pictures, page=""):
    """One note: a dated markdown file in thoughts/notepad/, its pictures named beside it. Returns its relative path."""
    body = " ".join(str(text or "").split())
    first = " ".join(body.split()[:8]).rstrip(",;:-").strip()      # the note's first words are its title, without a hanging comma
    leaf = capture_name("", first or "note", ".md")
    now = dt.datetime.now()
    lines = ["# %s" % (first or "note"), "",
             "**Taken:** %s in the Brain Viewer%s" % (now.strftime("%Y-%m-%d %H:%M"), (" on %s" % page) if page else ""), "",
             str(text or "").replace("\r\n", "\n").rstrip(), ""]
    for p in pictures or []:
        leafp = os.path.basename(str(p))
        lines += ["![%s](%s)" % (leafp, leafp), ""]
    return capture_write(leaf, "\n".join(lines))


# ---- editing a note in place (2026-09-16, ledger T-0146) ----
# The owner asked on 9/15, in the notepad, for notes to be editable and clickable in recent notes. A note
# stays the owner's own words; what changes is that the owner can change them from the app instead of the file being write-once. The
# two lines the file was born with -- its title and when it was taken -- and the pictures under it are kept exactly as
# they are, so an edit can only ever move the body between them (rules 4, amended today).
NOTE_PIC = re.compile(r"^!\[[^\]]*\]\([^)]*\)\s*$")


def note_abs(rel):
    """The absolute path of a note the notepad may EDIT: a `.md` that ALREADY EXISTS directly inside thoughts/notepad/.
    A nested path, another extension, the folder's own readme or a name with no file behind it is refused here, before
    anything is opened -- this route edits and never creates."""
    rel = norm(rel or "")
    if not rel or not rel.startswith(CAPTURE_REL + "/"):
        return None
    leaf = rel[len(CAPTURE_REL) + 1:]
    if not leaf or "/" in leaf or not leaf.lower().endswith(".md") or leaf.lower() == "readme.md":
        return None
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    return ap if os.path.isfile(ap) else None


def note_parts(ap):
    """One note cut into the three things it is made of: the header lines it keeps (its title and its **Taken:** line),
    the body that can be edited, and the picture lines sitting under it, verbatim."""
    with open(ap, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    lines = raw.replace("\r\n", "\n").split("\n")
    head = 0
    if lines and lines[0].startswith("# "):
        head = 1
    for i, line in enumerate(lines[:6]):
        if line.startswith("**Taken:**"):
            head = i + 1
            break
    pics, end = [], len(lines)
    while end > head:
        line = lines[end - 1].strip()
        if not line:
            end -= 1
            continue
        if NOTE_PIC.match(line):
            pics.insert(0, lines[end - 1].rstrip())
            end -= 1
            continue
        break
    title = lines[0][2:].strip() if (lines and lines[0].startswith("# ")) else os.path.basename(ap)[:-3]
    taken = ""
    for line in lines[:head]:
        if line.startswith("**Taken:**"):
            taken = line[len("**Taken:**"):].strip()
    body = "\n".join(lines[head:end]).strip("\n")
    return {"header": lines[:head], "title": title, "taken": taken, "body": body, "pictures": pics,
            "crlf": "\r\n" in raw}


def note_read(rel):
    """What the notepad opens when a note is pressed in the recent list: the note as its three parts, plus when it was last touched."""
    ap = note_abs(rel)
    if not ap:
        return None
    p = note_parts(ap)
    return {"path": norm(rel), "title": p["title"], "taken": p["taken"], "body": p["body"],
            "pictures": [(lambda t: t if "/" in t else CAPTURE_REL + "/" + t)(
                re.sub(r"^!\[[^\]]*\]\(([^)]*)\)$", r"\1", x.strip())) for x in p["pictures"]],
            "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds"),
            "editable": True}


def notepad_edit(rel, text):
    """Rewrite ONE note's body in place. The header lines and the picture lines are written back exactly as they were
    read, so the only thing an edit can change is what sits between them. Returns (relative path, bytes written)."""
    ap = note_abs(rel)
    if not ap:
        return None, 0
    p = note_parts(ap)
    out = list(p["header"])
    while out and not out[-1].strip():
        out.pop()
    out += ["", str(text or "").replace("\r\n", "\n").rstrip(), ""]
    for pic in p["pictures"]:
        out += [pic, ""]
    body = "\n".join(out)
    if p["crlf"]:
        body = body.replace("\n", "\r\n")
    with open(ap, "w", encoding="utf-8", newline="") as f:
        f.write(body)
    return norm(rel), len(body.encode("utf-8"))


def forge_path(rel):
    """True when rel is a file the Forge may write: <FORGE_ROOT>/<family>[/...]/<name>.canvas or .forge.json."""
    rel = norm(rel)
    if not rel or not rel.startswith(FORGE_ROOT + "/") or not rel.lower().endswith(FORGE_EXT):
        return False
    inner = rel[len(FORGE_ROOT) + 1:]
    return "/" in inner and os.path.basename(inner) not in ("", ".canvas", ".forge.json")


def forge_sibling(canvas_rel):
    return canvas_rel[:-len(".canvas")] + ".forge.json"


def is_cell(n):
    """A cell is a group that is not one of the two nested layers a cell draws inside itself."""
    return n.get("type") == "group" and not str(n.get("label") or "").strip().lower().startswith(FORGE_INNER)


def forge_stages(nodes, meta):
    """Stage counts for a canvas: every cell, at the stage its .forge.json row names, else concept."""
    rows = (meta or {}).get("nodes") or {}
    out = {k: 0 for k in FORGE_STAGES}
    for n in nodes:
        if is_cell(n):
            st = str((rows.get(n.get("id")) or {}).get("stage") or "concept").lower()
            out[st if st in out else "concept"] += 1
    return out


def read_forge_meta(canvas_rel):
    """The sibling .forge.json as a dict, or None when there is none (every cell at concept)."""
    ap = os.path.join(BRAIN, forge_sibling(canvas_rel).replace("/", os.sep))
    if not os.path.isfile(ap):
        return None
    with open(ap, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def forge_api(rel):
    """GET /api/forge?path=: the drawing, its sibling, whether it may be written here, and the facts the client needs
    to write the file back the way it found it (a trailing newline or not; CRLF is handled by PUT /api/file itself)."""
    rel = norm(rel)
    ap = read_abs(rel) if rel else None
    if not ap or not rel.lower().endswith(".canvas") or not os.path.isfile(ap):
        return None, "canvas not found"
    with open(ap, "rb") as f:
        raw = f.read()
    d = json.loads(raw.decode("utf-8-sig"))
    meta = read_forge_meta(rel)
    return {"path": rel, "canvas": d, "forge": meta, "forgePath": forge_sibling(rel), "forgeExists": meta is not None,
            "editable": writable(rel), "propose": PROPOSE,
            "family": rel[len(FORGE_ROOT) + 1:].split("/")[0] if rel.startswith(FORGE_ROOT + "/") else "",
            "trailingNewline": raw.endswith(b"\n"), "crlf": b"\r\n" in raw[:4096],
            "stages": forge_stages(d.get("nodes", []), meta), "inForge": forge_path(rel),
            "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")}, None


def forge_new(family, name):
    """POST /api/forge/new: a fresh canvas with one empty cell under <FORGE_ROOT>/<family>/<name>.canvas (exclusive create).
    The family folder is made when it does not exist yet. Returns (rel, error)."""
    fam = re.sub(r"[^a-z0-9-]+", "-", str(family or "").strip().lower()).strip("-")
    slug = re.sub(r"[^a-z0-9-]+", "-", str(name or "").strip().lower()).strip("-")
    if not fam or not slug:
        return None, "a family folder and a name are both required (letters, digits, dashes)"
    rel = "%s/%s/%s.canvas" % (FORGE_ROOT, fam, slug)
    label = re.sub(r"\s+", " ", str(name or "").strip()) or slug
    doc = {"nodes": [{"id": "cell_1", "type": "group", "x": 0, "y": 0, "width": 900, "height": 560, "color": "6", "label": "CELL 1 · " + label.upper()}],
           "edges": []}
    body = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if PROPOSE:
        return propose("file", rel, {"content": body}, note="Forge: new machine %s (1 cell)" % rel), None
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    try:
        with open(ap, "x", encoding="utf-8", newline="\n") as f:
            f.write(body)
    except FileExistsError:
        return None, "a canvas named %s already exists in %s" % (slug, fam)
    log_line("%s -- Forge: new machine, 1 cell, 0 edges; created from the picker" % rel, action="CREATED")
    return rel, None


# ---- the output shelf's loose fields (2026-09-10, the mouth, T-0091). "Derived, never drawn" applies to the OUTPUT of a
# cell as much as to a panel: where a cell is bound to something real, the fields it can ship are READ from that thing's
# own records at request time and never typed into the drawing. What the drawing carries is a pointer (the sibling's
# output.source, or the node's saved binding), so a schema that gains a key gains it here on the next reload.
_fields_cache = {}                # abs path -> (mtime, size, [rows])


def forge_field_rows(rel):
    """The record keys of a .json full of records, as field rows. A file shaped {"<plural>": [ {...}, ... ]} is read as
    that list; a bare list is read as itself; a dict of dicts as its values. Sub-keys are one level deep, which is where
    the onboarding profile keeps profile / assessment / extendedQuestions."""
    ap = read_abs(rel)
    if not ap or not os.path.isfile(ap) or not rel.lower().endswith(".json"):
        return None, "not a readable .json under the brain: %s" % rel
    st = os.stat(ap)
    hit = _fields_cache.get(ap)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2], None
    with open(ap, "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    recs = None
    if isinstance(d, list):
        recs = [x for x in d if isinstance(x, dict)]
    elif isinstance(d, dict):
        best = None
        for k, v in d.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and (best is None or len(v) > len(best[1])):
                best = (k, v)
        if best:
            recs = best[1]
        elif d and all(isinstance(v, dict) for v in d.values()):
            recs = list(d.values())
        else:
            recs = [d]
    if not recs:
        return None, "no records in %s" % rel
    r0 = recs[0]

    def kind_of(v):
        if isinstance(v, bool):
            return "yes/no"
        if isinstance(v, (int, float)):
            return "number"
        if isinstance(v, list):
            return "list"
        if isinstance(v, dict):
            return "record"
        if v is None:
            return "empty"
        return "text"

    def sample_of(v):
        if isinstance(v, (dict, list)):
            return "%d %s" % (len(v), "keys" if isinstance(v, dict) else "items")
        t = str(v if v is not None else "")
        return (t[:70] + "…") if len(t) > 70 else t

    rows, seen = [], set()
    for k, v in r0.items():
        if k in seen:
            continue
        seen.add(k)
        rows.append({"key": k, "type": kind_of(v), "sample": sample_of(v), "group": "record"})
        if isinstance(v, dict):
            for k2, v2 in v.items():
                rows.append({"key": "%s.%s" % (k, k2), "type": kind_of(v2), "sample": sample_of(v2), "group": k})
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            for k2, v2 in v[0].items():
                rows.append({"key": "%s[].%s" % (k, k2), "type": kind_of(v2), "sample": sample_of(v2), "group": k})
    _fields_cache[ap] = (st.st_mtime, st.st_size, rows)
    if len(_fields_cache) > 24:
        _fields_cache.clear()
    return rows, None


def forge_fields_api(rel, node_id):
    """GET /api/forge/fields?path=&node=: what one cell's mouth can ship, read from the real thing behind the cell.
    The pointer comes from the drawing, never the field list: the sibling's `output.source` for that node first, then a
    binding saved on it, then the binding the live ladder resolves for it. Nothing is written."""
    rel = norm(rel)
    ap = read_abs(rel) if rel else None
    if not ap or not rel.lower().endswith(".canvas") or not os.path.isfile(ap):
        return None, "canvas not found"
    with open(ap, "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    n = next((x for x in d.get("nodes", []) if x.get("id") == node_id), None)
    if not n:
        return None, "no node %s in this drawing" % node_id
    meta = read_forge_meta(rel) or {}
    row = ((meta.get("nodes") or {}).get(node_id) or {})
    src, via = None, None
    out = row.get("output") if isinstance(row.get("output"), dict) else {}
    if out.get("source"):
        src, via = norm(out["source"]), "the source named beside the drawing"
    if not src:
        b = row.get("binding") if isinstance(row.get("binding"), dict) else None
        if b and str(b.get("target") or "").lower().endswith(".json"):
            src, via = norm(b["target"]), "the binding saved on this cell"
    if not src:
        try:
            b = live_bind(n, live_names(), (meta.get("nodes") or {}))
        except Exception:
            b = None
        if b and b.get("kind") in ("file", "canvas") and str(b.get("target") or "").lower().endswith(".json"):
            src, via = norm(b["target"]), "what this cell is bound to (%s)" % b.get("via")
    if not src:
        return None, ("nothing real is behind this cell yet, so there is no schema to read. Name the file its records "
                      "live in as `output.source` beside the drawing, or type the fields by hand in the shelf.")
    rows, err = forge_field_rows(src)
    if err:
        return None, err
    return {"path": rel, "node": node_id, "source": src, "via": via, "count": len(rows), "fields": rows,
            "readAt": dt.datetime.now().astimezone().isoformat(timespec="seconds")}, None


def resolve_map():
    if time.time() - _resolve_cache["t"] > 60:
        m = {}
        for root, dirs, files in os.walk(BRAIN):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in files:
                if (os.path.splitext(fn)[1].lower() in READ_EXT or os.path.splitext(fn)[1].lower() in IMAGE_EXT) and fn not in NEVER_READ:
                    rel = os.path.relpath(os.path.join(root, fn), BRAIN).replace(os.sep, "/")
                    m.setdefault(fn, []).append(rel)
        _resolve_cache.update(t=time.time(), map=m)
    return _resolve_cache["map"]


def canvases():
    out = []
    arch = os.path.join(BRAIN, ARCH_REL.replace("/", os.sep))
    for root, dirs, files in os.walk(arch):
        for fn in sorted(files):
            if not fn.endswith(".canvas"):
                continue
            ap = os.path.join(root, fn)
            rel = os.path.relpath(ap, BRAIN).replace(os.sep, "/")
            family = os.path.relpath(root, arch).replace(os.sep, "/")
            try:
                with open(ap, "r", encoding="utf-8-sig") as f:
                    d = json.load(f)
                nodes = d.get("nodes", []); edges = d.get("edges", [])
                header = next((n.get("text", "") for n in nodes if (n.get("text") or "").lstrip().startswith("🧭")), "")
                header = header.replace("\n", " ").replace("**", "").strip()
                try:
                    meta = read_forge_meta(rel)
                except Exception:
                    meta = None
                out.append({"path": rel, "name": fn[:-len(".canvas")], "family": family if family != "." else "(root)",
                            "nodes": len(nodes), "edges": len(edges),
                            "stages": forge_stages(nodes, meta), "cells": sum(1 for n in nodes if is_cell(n)), "forge": meta is not None,
                            "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).strftime("%Y-%m-%d"),
                            "header": header[:200], "home": fn == "zak-brain-map-radial.canvas"})
            except Exception as e:
                out.append({"path": rel, "name": fn, "family": family, "nodes": 0, "edges": 0, "mtime": None, "header": "unreadable: %s" % e, "home": False})
    return out


# ---- the live maps (2026-09-09, the straight line step 4, ledger T-0042) ----
# The owner's ask, on the 9/09 moving graph: not one map, several, each an existing canvas read against real state, with the gold
# bubbles along the lines kept for what is in flight. Two layers computed over a drawing nobody edits for it (build doc
# section 12):
#   BUILD    every node bound to the real thing it stands for -- a file (or a canvas, or a folder), a registry holon, a
#            skill folder under skills/, an agent id the log has seen, a route of this app, an outside service -- or marked
#            concept. The ladder, in order: the title line's own pointer ([[wikilink]], `backticked path`, a bare filename
#            unique in the brain), a holon id or name on the title line, a skill folder name there, an agent id there;
#            then the whole text: a pointer (a wikilink that only says "open →" or "⬆ Up" is navigation, not identity, and
#            is skipped), a route, a service name, a holon id or a skill name. A binding already SAVED in the sibling
#            .forge.json wins over all of it, so a drawing carries its bindings forward.
#   RUNTIME  each bound thing lit by evidence the brain already writes: the context/log.md lines of the last LIVE_DAYS that
#            name it (count, last time, last verb, the agent, the last three lines), a file's mtime, a holon's status-file
#            _generatedAt, whether a Claude Code session ran today (for agents), the team copy's status file, the last
#            Ferryman line (for the PF App and the onboarding app). An edge is active today when both its ends were.
# Nothing here is stored (rules 1 and 2): bindings are cached in memory per canvas mtime and the activity is re-read on
# every call. The ONE write is "save bindings" on the page, which copies the resolved bindings into the canvas's sibling
# .forge.json under each node id as binding: {kind, target} -- the Forge's file, the Forge's write scope, one log line --
# and only when that button is pressed. In a team copy that write is a request like every other.
LIVE_DAYS = 14
LIVE_LINES = 3                    # log lines carried per node, for the hover card
MAPS_REL = _declared("maps_manifest", "maps-manifest.json", "skills/brain-viewer/maps-manifest.json")   # which canvases are maps and by what purpose: a declaration, like the mentee manifest
LIVE_ROUTES = ("/projects", "/people", "/mentee", "/canvases", "/forge", "/live", "/maps", "/requests", "/map", "/status",
               "/holons", "/agents", "/chat", "/reader", "/glossary")
LIVE_EXT = (".md", ".py", ".json", ".canvas", ".txt", ".bat", ".js", ".css", ".html", ".csv", ".yaml", ".yml", ".ps1", ".sh")
# outside services: (name, what names it in a node's text, what names it in a log line, where a click goes)
LIVE_SERVICES = (
    ("team copy", r"team copy|zebrain-team|\bthe clone\b|team brain|team-brain", r"team-brain|team copy|zebrain-team|export\.py", None),
    ("GitHub", r"\bgithub\b|bigzcoda/|\bgit push\b|\bgit/", r"\bgithub\b|\bgit push\b|\bpushed to\b|bigzcoda|\bcommit(?:ted)?\b", "https://github.com/BigZCoda"),
    ("PF App", r"\bpf app\b|app\.prospectforge\.us", r"\bpf app\b|app\.prospectforge|push\.py|pull\.py|\bferryman\b", "https://app.prospectforge.us"),
    ("onboarding app", r"onboarding app|onboarding\.prospectforge\.us|onboarding api", r"onboarding-api-pull|onboarding app|onboarding-app-holon", "https://onboarding.prospectforge.us"),
    ("Google Calendar", r"google calendar|calendar mcp|\bcalendar\b", r"\bcalendar\b", None),
    ("Gmail", r"\bgmail\b", r"\bgmail\b", None),
    ("Notion", r"\bnotion\b", r"\bnotion\b", None),
    ("Replit", r"\breplit\b", r"\breplit\b", None),
    ("Obsidian Sync", r"obsidian sync|\bobsidian\b", r"\bobsidian\b", None),
    ("Google Drive", r"google doc|google drive|drive mcp", r"google doc|google drive", None),
    ("transcription", r"\botter\b|\bgranola\b|\bgemini\b", r"\bgemini\b|\botter\b|\bgranola\b", None),
)
LIVE_HOSTS = (("github.com", "GitHub"), ("app.prospectforge.us", "PF App"), ("onboarding.prospectforge.us", "onboarding app"),
              ("replit", "Replit"), ("notion.so", "Notion"), ("calendar.google", "Google Calendar"), ("docs.google", "Google Drive"))
WIKI_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
TICK_RE = re.compile(r"`([^`\n]+)`")
BARE_RE = re.compile(r"(?<![\w/.\-])([A-Za-z][\w.\-]*\.(?:md|py|json|canvas|txt|bat|js|css|html))(?![\w/])")
NAV_BEFORE_RE = re.compile(r"(?:open|up|twin|see also|drill[- ]?down|also|here)\s*[:→]?\s*$", re.I)
_live_cache = {}                  # canvas rel -> (key, bindings by node id)
_log_cache = {"key": None, "rows": [], "agents": set()}
_leaf_cache = {"t": 0, "map": {}}


def ledger_months():
    """[(month, path)] for every rotated log month on disk, oldest first."""
    base = os.path.join(BRAIN, LEDGERS_REL.replace("/", os.sep))
    if not os.path.isdir(base):
        return []
    out = []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    for name in names:
        if not re.fullmatch(r"\d{4}-\d{2}", name):
            continue
        path = os.path.join(base, name, "log-%s.md" % name)
        if os.path.isfile(path):
            out.append((name, path))
    return out


def log_lines(since=None):
    """THE reader of the operations log, for every caller in this file.

    Yields raw lines oldest-first: the rotated months `archive/ledgers/YYYY-MM/log-YYYY-MM.md` the
    window reaches into, then the live `context/log.md`. `since` is the oldest DAY the caller needs
    ('YYYY-MM-DD'); None means the whole rotation, which is what a "what has this brain ever done"
    reader (the agents page) wants. A 14-day window crossing a month boundary therefore reads the
    same lines it read when the live file still held every month (2026-09-18, Batch 2)."""
    for month, path in ledger_months():
        if since and month < since[:7]:
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    yield line.rstrip("\n")
        except OSError:
            continue
    ap = os.path.join(BRAIN, LOG_REL.replace("/", os.sep))
    if os.path.isfile(ap):
        with open(ap, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line.rstrip("\n")


def log_key():
    """The cache key for the log: the live file plus every rotated month, so a rotation invalidates."""
    parts = []
    for path in [os.path.join(BRAIN, LOG_REL.replace("/", os.sep))] + [pa for _m, pa in ledger_months()]:
        try:
            st = os.stat(path)
            parts.append((path, st.st_mtime, st.st_size))
        except OSError:
            continue
    return (tuple(parts), dt.date.today().isoformat())


def log_rows():
    """The log read once per change: the rows of the last LIVE_DAYS (append-only, so newest last) and
    every agent id the log has ever seen. One pass over log_lines(), live file and rotated months."""
    if not os.path.isfile(os.path.join(BRAIN, LOG_REL.replace("/", os.sep))):
        return [], set()
    key = log_key()
    if _log_cache["key"] == key:
        return _log_cache["rows"], _log_cache["agents"]
    since = (dt.date.today() - dt.timedelta(days=LIVE_DAYS)).isoformat()
    rows, agents = [], set()
    for line in log_lines():
        m = LOG_LINE_RE.match(line)
        if not m:
            continue
        agents.add(m.group(3))
        if m.group(1) < since:
            continue
        rows.append({"date": m.group(1), "at": m.group(1) + " " + m.group(2), "agent": m.group(3), "action": m.group(4),
                     "text": m.group(5), "low": (m.group(3) + " " + m.group(5)).lower()})
    _log_cache.update(key=key, rows=rows, agents=agents)
    return _log_cache["rows"], _log_cache["agents"]


def live_leaves():
    """Every file under the brain by leaf name (all extensions the ladder accepts, not only the readable ones), refreshed each minute."""
    if time.time() - _leaf_cache["t"] > 60:
        m = {}
        for root, dirs, files in os.walk(BRAIN):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in files:
                if fn.lower().endswith(LIVE_EXT) and fn not in NEVER_READ:
                    m.setdefault(fn, []).append(os.path.relpath(os.path.join(root, fn), BRAIN).replace(os.sep, "/"))
        _leaf_cache.update(t=time.time(), map=m)
    return _leaf_cache["map"]


def live_plain(s):
    """A node's text with the markdown, the wikilink brackets, the emoji and the symbols taken out; one space between words."""
    s = WIKI_RE.sub(lambda m: m.group(2) or m.group(1), str(s or ""))
    s = re.sub(r"[*`_#>|]+", " ", s)
    s = re.sub(r"[^\w\s/.:@+()'\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def live_resolve_path(tok):
    """A pointer's text -> (brain-relative path, is_dir) when it names something that exists under the brain, else None."""
    tok = str(tok or "").strip().strip("'\"").split(" ")[0].strip(",.;:)(")
    tok = re.sub(r"^\./", "", tok.replace("\\", "/"))
    if not tok or tok.lower().startswith(("http:", "https:")) or tok in NEVER_READ:
        return None
    rel = norm(tok)
    if not rel:
        return None
    if "/" in rel:
        if rel.split("/")[0] in SKIP_DIRS:
            return None
        ap = os.path.join(BRAIN, rel.rstrip("/").replace("/", os.sep))
        if os.path.isdir(ap):
            return rel.rstrip("/") + "/", True
        if os.path.isfile(ap) and os.path.basename(ap) not in NEVER_READ:
            return rel, False
        return None
    leaves = live_leaves()
    cands = leaves.get(rel) or leaves.get(rel + ".md") or leaves.get(rel + ".canvas") or []
    if len(cands) == 1:
        return cands[0], False
    if os.path.isdir(os.path.join(BRAIN, rel)) and rel not in SKIP_DIRS:
        return rel + "/", True
    return None


def live_pointers(text):
    """The pointers in a piece of text, in reading order: backticked paths, wikilinks (not the navigation ones), bare filenames."""
    out, spans = [], []
    for m in TICK_RE.finditer(text):
        out.append((m.start(), m.group(1))); spans.append((m.start(), m.end()))
    for m in WIKI_RE.finditer(text):
        spans.append((m.start(), m.end()))
        before = text[max(0, m.start() - 20):m.start()]
        alias = (m.group(2) or "").lower()
        if NAV_BEFORE_RE.search(before) or "open" in alias or "→" in alias:
            continue                                     # "🔍 Open: [[x]]", "⬆ Up: [[x]]", "[[x|open →]]": a drill-down, not what the node is
        out.append((m.start(), m.group(1)))
    for m in BARE_RE.finditer(text):
        if any(a <= m.start() < z for a, z in spans):
            continue                                     # already a wikilink or a backtick (a navigation wikilink stays skipped)
        out.append((m.start(), m.group(1)))
    out.sort(key=lambda t: t[0])
    return [t for _, t in out]


def live_names():
    """What the ladder can bind a name to: the registry's holons (by id, by name, by declared path), the skill folders, the agent ids the log has seen."""
    reg = registry()
    holons = [h for h in reg.get("holons", []) if h.get("id")]
    by_path = {}
    for h in holons:
        raw = str(h.get("path") or "").strip()
        if raw:
            by_path[raw] = h["id"]                # a folder path keeps its trailing slash in the registry, a file path has none
    sk = os.path.join(BRAIN, "skills")
    skills = sorted(d for d in (os.listdir(sk) if os.path.isdir(sk) else []) if os.path.isdir(os.path.join(sk, d)) and not d.startswith((".", "_")))
    rows, agents = log_rows()
    return {"holons": holons, "byId": {h["id"]: h for h in holons}, "byPath": by_path, "skills": skills, "agents": agents,
            "_key": (reg.get("_updated"), tuple(skills), len(agents))}


def word_in(word, text):
    return re.search(r"(?<![\w\-])" + re.escape(word.lower()) + r"(?![\w\-])", text) is not None


def live_skill_doc(name):
    """Where a skill binding opens: its skill doc, its readme, else the first .md in its folder."""
    d = os.path.join(BRAIN, "skills", name)
    for fn in (name + "-skill.md", "readme.md", "README.md"):
        if os.path.isfile(os.path.join(d, fn)):
            return "skills/%s/%s" % (name, fn)
    md = sorted(f for f in os.listdir(d) if f.lower().endswith(".md")) if os.path.isdir(d) else []
    return "skills/%s/%s" % (name, md[0]) if md else None


def live_binding(kind, target, names, via, label=None):
    """The full binding row for a kind + target: the short name, where a click goes, and for a file its facts."""
    b = {"kind": kind, "target": target, "label": label or target, "href": None, "via": via}
    if kind in ("file", "canvas", "folder"):
        ap = os.path.join(BRAIN, target.rstrip("/").replace("/", os.sep))
        b["label"] = target.rstrip("/").split("/")[-1] + ("/" if kind == "folder" else "")
        b["exists"] = os.path.isdir(ap) if kind == "folder" else os.path.isfile(ap)
        if b["exists"] and kind != "folder":
            st = os.stat(ap)
            b["mtime"] = dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
            b["size"] = st.st_size
        if kind == "canvas":
            b["href"] = "/live?path=" + urllib.parse.quote(target)
        elif kind == "file" and target.lower().endswith(".md"):
            b["href"] = "/reader?path=" + urllib.parse.quote(target)
        elif kind == "folder":
            hid = names["byPath"].get(target)
            if hid:
                return live_binding("holon", hid, names, via)
    elif kind == "holon":
        h = names["byId"].get(target)
        if not h:
            return None
        b["label"] = h.get("name") or target
        b["href"] = ("/projects?id=" + urllib.parse.quote(target)) if h.get("tasks") else "/holons"
        b["path"] = h.get("path")
    elif kind == "skill":
        if target not in names["skills"]:
            return None
        doc = live_skill_doc(target)
        b["href"] = ("/reader?path=" + urllib.parse.quote(doc)) if doc else None
        b["doc"] = doc
    elif kind == "agent":
        b["href"] = "/chat#running"
    elif kind == "route":
        b["href"] = target
    elif kind == "service":
        row = next((s for s in LIVE_SERVICES if s[0] == target), None)
        b["href"] = row[3] if row else (target if str(target).startswith("http") else None)
    elif kind == "concept":
        b["label"] = "concept"
    return b


def live_bind(n, names, saved):
    """One node -> its binding, by the ladder in the module note. A saved binding (the sibling .forge.json) wins."""
    row = (saved.get(n.get("id")) or {}).get("binding")
    if isinstance(row, dict) and row.get("kind") not in (None, "", "concept") and row.get("target"):
        b = live_binding(row["kind"], row["target"], names, "saved")
        if b:
            return b
    t = n.get("type")
    if t == "file":
        r = live_resolve_path(n.get("file"))
        if not r:
            return live_binding("file", str(n.get("file") or ""), names, "file node", label=str(n.get("file") or "").split("/")[-1])
        return live_binding("folder" if r[1] else ("canvas" if r[0].lower().endswith(".canvas") else "file"), r[0], names, "file node")
    if t == "link":
        url = str(n.get("url") or "")
        svc = next((name for host, name in LIVE_HOSTS if host in url.lower()), None)
        return live_binding("service", svc or url, names, "link node", label=svc or url.split("/")[2] if "//" in url else url)
    text = str(n.get("text") if t == "text" else n.get("label") or "")
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    title = lines[0] if lines else ""
    tplain, tlow = live_plain(title), live_plain(title).lower()
    if re.match(r"^\*\*(assumed[ ]+)?output\b", title.strip(), re.I):
        return live_binding("concept", None, names, "output")   # a cell's mouth: what it hands on. The fields behind it are read from the real thing (/api/forge/fields); the mouth itself is never a thing
    # 1. the title line's own pointer
    for tok in live_pointers(title):
        r = live_resolve_path(tok)
        if r:
            return live_binding("folder" if r[1] else ("canvas" if r[0].lower().endswith(".canvas") else "file"), r[0], names, "title pointer")
    # 2. a holon id or name on the title line (the longest name that fits wins)
    best = None
    for h in names["holons"]:
        for cand in (h["id"], str(h.get("name") or "")):
            if cand and len(cand) > 2 and word_in(cand, tlow) and (best is None or len(cand) > len(best[0])):
                best = (cand, h["id"])
    if best:
        return live_binding("holon", best[1], names, "title holon")
    # 3. a skill folder name on the title line
    for s in names["skills"]:
        if word_in(s, tlow) or (("-" in s) and word_in(s.replace("-", " "), tlow)):
            return live_binding("skill", s, names, "title skill")
    # 4. an agent id the log has seen, on the title line
    for a in sorted(names["agents"], key=len, reverse=True):
        if len(a) > 3 and (word_in(a, tlow) or (("-" in a) and word_in(a.replace("-", " "), tlow))):
            return live_binding("agent", a, names, "title agent")
    # 5. a pointer anywhere in the text
    for tok in live_pointers(text):
        r = live_resolve_path(tok)
        if r:
            return live_binding("folder" if r[1] else ("canvas" if r[0].lower().endswith(".canvas") else "file"), r[0], names, "text pointer")
    low = live_plain(text).lower()
    # 6. a route of this app, anywhere; "the home page" is /
    for route in sorted(LIVE_ROUTES, key=len, reverse=True):
        if re.search(r"(?<![\w/])" + re.escape(route) + r"(?![\w\-])", text):
            return live_binding("route", route, names, "route")
    if re.search(r"\bhome page\b|\bthe home\b", low):
        return live_binding("route", "/", names, "route", label="home")
    # 7. an outside service, the title first
    for scope, via in ((tlow, "title service"), (low, "text service")):
        for name, node_re, _, _ in LIVE_SERVICES:
            if re.search(node_re, scope, re.I):
                return live_binding("service", name, names, via)
    # 8. a holon id or a skill name anywhere in the text (ids are slugs, so this stays specific)
    for h in names["holons"]:
        if word_in(h["id"], low):
            return live_binding("holon", h["id"], names, "text holon")
    for s in names["skills"]:
        if word_in(s, low):
            return live_binding("skill", s, names, "text skill")
    return live_binding("concept", None, names, "unresolved")


def live_log_pattern(b, leaves):
    k, t = b["kind"], str(b.get("target") or "").lower()
    if not t:
        return None
    if k in ("file", "canvas", "folder"):
        pats = [re.escape(t.rstrip("/") if k != "folder" else t)]
        leaf = t.rstrip("/").split("/")[-1]
        if k != "folder" and len(leaves.get(b["label"], [])) == 1:
            pats.append(r"(?<![\w/.\-])" + re.escape(leaf) + r"(?![\w])")
        return re.compile("|".join(pats))
    if k == "holon":
        pats = [r"(?<![\w\-])" + re.escape(t) + r"(?![\w\-])"]
        if b.get("label") and b["label"].lower() != t:
            pats.append(r"\b" + re.escape(b["label"].lower()) + r"\b")
        if b.get("path"):
            pats.append(re.escape(str(b["path"]).lower()))
        return re.compile("|".join(pats))
    if k == "skill":
        return re.compile(r"skills/" + re.escape(t) + r"\b|(?<![\w\-])" + re.escape(t) + r"(?![\w\-])")
    if k == "agent":
        return re.compile(r"(?<![\w\-])" + re.escape(t) + r"(?![\w\-])")
    if k == "route":
        return re.compile(r"(?<![\w/])" + re.escape(t) + r"(?![\w\-])") if t != "/" else re.compile(r"\bhome page\b|\bthe home\b|chat\.html|/api/waiting")
    if k == "service":
        row = next((s for s in LIVE_SERVICES if s[0] == b["target"]), None)
        return re.compile(row[2], re.I) if row else None
    return None


def live_sessions_today(today):
    d = sessions_dir()
    if not d:
        return 0, None
    n, newest = 0, None
    for fn in os.listdir(d):
        if not fn.endswith(".jsonl"):
            continue
        mt = os.path.getmtime(os.path.join(d, fn))
        iso = dt.datetime.fromtimestamp(mt).isoformat(timespec="seconds")
        if iso[:10] == today:
            n += 1
        if newest is None or iso > newest:
            newest = iso
    return n, newest


def live_activity(b, rows, today, leaves, ctx):
    """The runtime layer for one binding: the log lines that name it, plus the evidence its kind carries."""
    pat = live_log_pattern(b, leaves)
    hits = [r for r in rows if pat.search(r["low"])] if pat else []
    if b["kind"] == "agent":
        hits = [r for r in rows if r["agent"] == b["target"] or (pat and pat.search(r["low"]))]
    since14 = (dt.date.today() - dt.timedelta(days=LIVE_DAYS)).isoformat()
    a = {"count14": len(hits), "today": sum(1 for r in hits if r["date"] == today),
         "lastAt": hits[-1]["at"] if hits else None, "lastAction": hits[-1]["action"] if hits else None,
         "lastAgent": hits[-1]["agent"] if hits else None,
         "lines": [{"at": r["at"], "agent": r["agent"], "action": r["action"], "text": clip(r["text"], 180)} for r in hits[-LIVE_LINES:][::-1]]}
    score_today, active14 = a["today"], a["count14"] > 0
    if b["kind"] in ("file", "canvas") and b.get("mtime"):
        a["mtime"] = b["mtime"]
        if b["mtime"][:10] == today:
            score_today += 1
        if b["mtime"][:10] >= since14:
            active14 = True
    if b["kind"] == "holon":
        h = ctx["names"]["byId"].get(b["target"]) or {}
        if h.get("status"):
            try:
                st = read_json_rel(h["status"])[0] or {}
                gen = str(st.get("_generatedAt") or "")
                a["statusAt"] = gen or None
                if gen[:10] == today:
                    score_today += 1
                if gen[:10] >= since14:
                    active14 = True
            except Exception:
                pass
    if b["kind"] == "agent":
        n, newest = ctx["sessions"]
        a["sessionsToday"], a["lastSession"] = n, newest
        if n:
            score_today += 1
            active14 = True
    if b["kind"] == "service" and b["target"] == "team copy":
        ts = ctx.get("team") or {}
        le = (ts.get("last_export") or {})
        at = str(le.get("at") or "")
        when = iso_utc(at)
        local = when.astimezone().isoformat(timespec="seconds") if when else None
        a["teamCopy"] = {"lastExport": local, "files": le.get("files"), "unpushed": (ts.get("remote") or {}).get("unpushed"),
                         "behind": (ts.get("remote") or {}).get("behind"), "inboxOpen": (ts.get("requests") or {}).get("inbox_open")}
        if local and local[:10] == today:
            score_today += 1
        if local and local[:10] >= since14:
            active14 = True
    if b["kind"] == "service" and b["target"] in ("PF App", "onboarding app"):
        fer = re.compile(r"push\.py|pull\.py|\bferryman\b" if b["target"] == "PF App" else r"onboarding-api-pull|onboarding-app-holon")
        last = next((r for r in reversed(rows) if (b["target"] == "PF App" and r["agent"] == "ferryman") or fer.search(r["low"])), None)
        if last:
            a["lastFerry"] = {"at": last["at"], "agent": last["agent"], "action": last["action"], "text": clip(last["text"], 160)}
    a["todayScore"] = score_today
    a["active14"] = active14 or score_today > 0
    return a


def live_api(rel):
    """GET /api/live?path=: every node of a canvas bound to the real thing it stands for, and lit by the last LIVE_DAYS of evidence."""
    rel = norm(rel)
    ap = read_abs(rel) if rel else None
    if not ap or not rel.lower().endswith(".canvas") or not os.path.isfile(ap):
        return None, "canvas not found"
    with open(ap, "r", encoding="utf-8-sig") as f:
        d = json.load(f)
    meta = read_forge_meta(rel) or {}
    saved = meta.get("nodes") or {}
    names = live_names()
    sib_ap = os.path.join(BRAIN, forge_sibling(rel).replace("/", os.sep))
    key = (os.path.getmtime(ap), os.path.getmtime(sib_ap) if os.path.isfile(sib_ap) else None, names["_key"])
    hit = _live_cache.get(rel)
    if hit and hit[0] == key:
        bindings = hit[1]
    else:
        bindings = {n["id"]: live_bind(n, names, saved) for n in d.get("nodes", []) if n.get("id")}
        _live_cache[rel] = (key, bindings)
        if len(_live_cache) > 80:
            _live_cache.clear()
    rows, _ = log_rows()
    today = dt.date.today().isoformat()
    leaves = live_leaves()
    team = None
    if os.path.isfile(os.path.join(BRAIN, TEAM_STATUS_REL.replace("/", os.sep))):
        team = read_json_rel(TEAM_STATUS_REL)[0]
    ctx = {"names": names, "sessions": live_sessions_today(today), "team": team}
    nodes = {}
    for nid, b in bindings.items():
        nodes[nid] = {"binding": b, "activity": live_activity(b, rows, today, leaves, ctx) if b["kind"] != "concept"
                      else {"count14": 0, "today": 0, "lastAt": None, "lastAction": None, "lastAgent": None, "lines": [], "todayScore": 0, "active14": False}}
    edges = {}
    for e in d.get("edges", []):
        a, z = nodes.get(e.get("fromNode")), nodes.get(e.get("toNode"))
        edges[e.get("id")] = {"today": bool(a and z and a["activity"]["todayScore"] and z["activity"]["todayScore"]),
                              "active14": bool(a and z and a["activity"]["active14"] and z["activity"]["active14"])}
    kinds = {}
    for r in nodes.values():
        kinds[r["binding"]["kind"]] = kinds.get(r["binding"]["kind"], 0) + 1
    last = max((r["activity"]["lastAt"] or "" for r in nodes.values()), default="") or None
    counts = {"nodes": len(nodes), "bound": sum(1 for r in nodes.values() if r["binding"]["kind"] != "concept"),
              "concept": kinds.get("concept", 0), "activeToday": sum(1 for r in nodes.values() if r["activity"]["todayScore"]),
              "active14": sum(1 for r in nodes.values() if r["activity"]["active14"]),
              "edges": len(edges), "edgesToday": sum(1 for x in edges.values() if x["today"]),
              "saved": sum(1 for r in nodes.values() if r["binding"].get("via") == "saved")}
    return {"path": rel, "generatedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "today": today, "days": LIVE_DAYS,
            "order": ["saved binding", "title pointer", "title holon", "title skill", "title agent", "text pointer", "route", "service", "text holon or skill", "concept"],
            "nodes": nodes, "edges": edges, "counts": counts, "kinds": kinds, "lastAt": last,
            "forgePath": forge_sibling(rel), "forgeExists": meta != {} or os.path.isfile(sib_ap),
            "editable": writable(forge_sibling(rel)), "propose": PROPOSE,
            "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")}, None


def live_save_bindings(rel):
    """POST /api/live/bindings {path}: the one write of the live layer -- the resolved bindings copied into the sibling .forge.json,
    binding: {kind, target} under each node id, a concept node's row cleared of any old binding. Nothing the page sends shapes the file."""
    live, err = live_api(rel)
    if err:
        return None, err
    sib = live["forgePath"]
    if not writable(sib):
        return None, "the sibling .forge.json is outside the Forge's write scope"
    meta = read_forge_meta(live["path"]) or {"_schema": "forge/1", "canvas": live["path"], "nodes": {}}
    meta["nodes"] = meta.get("nodes") or {}
    k, kinds = 0, {}
    for nid, row in live["nodes"].items():
        b, r = row["binding"], dict(meta["nodes"].get(nid) or {})
        if b["kind"] == "concept" or not b.get("target"):
            r.pop("binding", None)
        else:
            r["binding"] = {"kind": b["kind"], "target": b["target"]}
            k += 1
            kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
        if r:
            meta["nodes"][nid] = r
        else:
            meta["nodes"].pop(nid, None)
    meta["_updated"] = dt.datetime.now().isoformat(timespec="seconds")
    body = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    note = "Live map: bindings saved for %d of %d nodes (%s)" % (k, len(live["nodes"]), ", ".join("%d %s" % (v, kk) for kk, v in sorted(kinds.items(), key=lambda x: -x[1])) or "none")
    if PROPOSE:
        req = propose("file", sib, {"content": body}, note=note)
        return {"proposed": True, "request": req, "kind": "file", "target": sib, "saved": k}, None
    ap = os.path.join(BRAIN, sib.replace("/", os.sep))
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    _live_cache.pop(live["path"], None)
    return {"ok": True, "path": sib, "saved": k, "nodes": len(live["nodes"]), "log": log_line("%s -- %s" % (sib, note))}, None


def maps_manifest():
    ap = os.path.join(BRAIN, MAPS_REL.replace("/", os.sep))
    if not os.path.isfile(ap):
        return {"groups": []}
    with open(ap, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def maps_api():
    """GET /api/maps: the picker -- the maps by purpose as the manifest declares them, each with its live counts, and every other canvas folded by family."""
    cv = canvases()
    by_path = {c["path"]: c for c in cv}
    man = maps_manifest()
    used, groups = set(), []

    def row(path, purpose):
        c = by_path.get(path)
        r = {"path": path, "name": (c or {}).get("name") or path.split("/")[-1].replace(".canvas", ""), "purpose": purpose or "",
             "exists": bool(c), "mtime": (c or {}).get("mtime"), "family": (c or {}).get("family"),
             "cells": (c or {}).get("cells", 0), "nodes": (c or {}).get("nodes", 0), "edges": (c or {}).get("edges", 0), "counts": None, "lastAt": None}
        if c:
            try:
                live, err = live_api(path)
                if live:
                    r["counts"], r["lastAt"] = live["counts"], live["lastAt"]
            except Exception as e:
                r["error"] = "%s: %s" % (type(e).__name__, e)
        return r

    # every group's named maps first, then a family group takes what is left of its folder: a canvas named by a later
    # group (the daily workflow, drawn in womb-phase/) stays where it was named
    for g in man.get("groups", []):
        rows = []
        for m in g.get("maps", []):
            if m.get("path") and m["path"] not in used:
                rows.append(row(m["path"], m.get("purpose"))); used.add(m["path"])
        groups.append({"id": g.get("id"), "name": g.get("name"), "purpose": g.get("purpose") or "", "maps": rows, "_family": g.get("family"), "_fp": g.get("familyPurpose") or ""})
    for g in groups:
        if g["_family"]:
            for c in cv:
                if c["family"] == g["_family"] and c["path"] not in used:
                    g["maps"].append(row(c["path"], g["_fp"])); used.add(c["path"])
        g["lastAt"] = max((r["lastAt"] or "" for r in g["maps"]), default="") or None
        del g["_family"], g["_fp"]
    other = {}
    for c in cv:
        if c["path"] not in used:
            other.setdefault(c["family"], []).append({"path": c["path"], "name": c["name"], "mtime": c["mtime"], "nodes": c["nodes"], "edges": c["edges"], "header": c.get("header", "")})
    # the filtering rule: the picker opens on the map active most recently; a tie on the minute goes to the one with more moving today
    recent = max(((r["lastAt"] or "", (r["counts"] or {}).get("activeToday", 0), r["path"], g["id"]) for g in groups for r in g["maps"]), default=None)
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "manifest": MAPS_REL, "days": LIVE_DAYS, "groups": groups,
            "other": [{"family": f, "canvases": rows} for f, rows in sorted(other.items())],
            "mostRecent": {"path": recent[2], "group": recent[3], "at": recent[0] or None} if recent and recent[0] else None,
            "retired": {"route": "/map", "note": "the moving graph of 2026-09-09 retired with the live maps; the route still answers, off the nav"}}


# ---- holons + status (panels 3 and 4): the registry and the status files, read as declared, never recomputed ----

def gl_slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def gl_split(rest):
    """definition / example / Septabee analog out of one bullet's tail, in that order."""
    an = ""
    m = re.search(r"\bSeptabee:\s*", rest)
    if m:
        an, rest = rest[m.end():].strip(), rest[:m.start()].rstrip()
    ex = ""
    m = re.search(r"\bExample:\s*", rest)
    if m:
        ex, rest = rest[m.end():].strip(), rest[:m.start()].rstrip()
    return rest.strip(), ex, an


def glossary_api():
    """The seed parsed into groups + a flat term list + the keys. No cache: the file is small and the point is that a
    save is live on the next reload. In a team copy the holon is absent, so the answer is `available: false` and the
    page says so rather than pretending to a vocabulary it cannot see."""
    ap = os.path.join(BRAIN, GLOSSARY_REL.replace("/", os.sep))
    out = {"file": GLOSSARY_REL, "available": False, "groups": [], "terms": [], "keys": [], "marker": GL_MARKER,
           "note": "The glossary lives in the Brain Viewer's own holon, which does not travel with a team copy.",
           "_servedAt": dt.datetime.now().isoformat(timespec="seconds")}
    if PROPOSE or not os.path.isfile(ap):
        return out
    with open(ap, "r", encoding="utf-8-sig") as f:
        lines = f.read().replace("\r\n", "\n").split("\n")
    out["available"] = True
    out["note"] = ""
    out["mtime"] = dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")
    g = None
    for raw in lines:
        line = raw.rstrip()
        h = re.match(r"^##\s+(.*)$", line)
        if h:
            g = {"name": h.group(1).strip(), "anchor": gl_slug(h.group(1)), "pages": [], "note": "", "hover": True, "terms": []}
            out["groups"].append(g)
            continue
        if g is None or line.startswith(">") or not line.strip():
            continue
        if not line.lstrip().startswith("- "):
            t = line.strip().strip("*")
            w = re.match(r"^Where these show up:\s*(.*?)\.?$", t, re.I)
            if w:
                g["pages"] = [p.strip().lower() for p in re.split(r"[,/]", w.group(1)) if p.strip()]
            elif not t.lower().startswith("**last touched"):
                g["note"] = (g["note"] + " " + line.strip()).strip()
                if "not auto-underlined" in g["note"].lower():
                    g["hover"] = False
            continue
        m = re.match(r"^-\s+\*\*(.+?)\*\*\s*(.*)$", line.strip())
        if not m:
            continue
        head, rest = m.group(1).strip().rstrip(".").strip(), m.group(2).strip()
        aliases = []
        pm = re.search(r"\(([^)]*)\)\s*$", head)
        if pm:
            aliases = [a.strip() for a in re.split(r"[,/]", pm.group(1)) if a.strip()]
            head = head[:pm.start()].strip()
        if g["name"].lower() == "keys":
            # `- **Escape** (projects, people) -- what it does.`: here the parenthesis holds the pages the key applies
            # on, and it sits after the bold rather than inside it, so it is read off the tail instead of the head.
            km = re.match(r"^(?:\(([^)]*)\))?\s*(?:[—–-]{1,2}\s*)?(.*)$", rest)
            pages = [p.strip().lower() for p in re.split(r"[,/]", km.group(1) or "") if p.strip()]
            out["keys"].append({"key": head, "pages": pages, "what": km.group(2).strip()})
            continue
        d, ex, an = gl_split(rest)
        hover = g["hover"] and head.lower() not in HOVER_OFF
        term = {"term": head, "aliases": aliases, "definition": d, "example": ex, "analog": an,
                "group": g["name"], "anchor": gl_slug(head),
                "hover": hover,
                # the aliases that may be auto-underlined; every alias still resolves through the {{...}} marker
                "needles": ([a for a in aliases if gl_alias_needle(a)]) if hover else []}
        g["terms"].append(term)
        out["terms"].append(term)
    out["groups"] = [x for x in out["groups"] if x["terms"] or x["name"].lower() == "keys"]
    return out


def frontmatter(ap):
    """The frontmatter block of a file as a flat dict (top-level `key: value` lines only), or None when there is none."""
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            if f.readline().strip() != "---":
                return None
            out = {}
            for _ in range(80):
                line = f.readline()
                if not line or line.strip() == "---":
                    break
                if ":" in line and not line.startswith((" ", "\t", "-")):
                    k, v = line.split(":", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
            return out
    except Exception:
        return None


def age_hours(iso):
    try:
        t = dt.datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.astimezone()
        return round((dt.datetime.now().astimezone() - t).total_seconds() / 3600, 1)
    except Exception:
        return None


def read_json_rel(rel):
    ap = read_abs(rel)
    if not ap or not os.path.isfile(ap):
        return None, "file not found: %s" % rel
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            return json.load(f), None
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def holons_api():
    reg = registry()
    out = []
    for h in reg.get("holons", []):
        h = dict(h)
        rel = (h.get("path") or "").rstrip("/")
        ap = os.path.join(BRAIN, rel.replace("/", os.sep)) if rel else None
        h["isDir"] = bool(ap and os.path.isdir(ap))
        h["exists"] = bool(ap and (h["isDir"] or os.path.isfile(ap)))
        h["mtime"] = dt.datetime.fromtimestamp(os.path.getmtime(ap)).strftime("%Y-%m-%d") if h["exists"] else None
        h["frontmatter"] = frontmatter(ap) if (h["exists"] and not h["isDir"]) else None
        if h.get("stamped"):
            fm = h["frontmatter"] or {}
            h["stamp"] = "missing" if not fm.get("holon") else ("match" if fm.get("holon") == h["id"] and fm.get("type") == h.get("type") else "mismatch")
        else:
            h["stamp"] = None
        if h["isDir"]:
            n = 0
            for root, dirs, files in os.walk(ap):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                n += sum(1 for fn in files if os.path.splitext(fn)[1].lower() in READ_EXT)
            h["files"] = n
            h["readme"] = (rel + "/readme.md") if os.path.isfile(os.path.join(ap, "readme.md")) else None
        for k in ("rules", "agent"):
            if h.get(k):
                h[k + "Exists"] = os.path.isfile(os.path.join(BRAIN, h[k].replace("/", os.sep)))
        if h.get("status"):
            data, err = read_json_rel(h["status"])
            h["statusFile"] = data
            h["statusError"] = err
            h["statusAgeHours"] = age_hours(data.get("_generatedAt")) if isinstance(data, dict) else None
        out.append(h)
    return {"_updated": reg.get("_updated"), "_rules": reg.get("_rules", []), "sharing_tiers": reg.get("sharing_tiers", []),
            "types": reg.get("types", []), "_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "holons": out}


def status_api():
    reg = registry()
    out = []
    for h in reg.get("holons", []):
        if not h.get("status"):
            continue
        data, err = read_json_rel(h["status"])
        d = data if isinstance(data, dict) else {}
        out.append({"id": h["id"], "name": h.get("name"), "path": h["status"], "agent": h.get("agent"), "rules": h.get("rules"),
                    "generatedAt": d.get("_generatedAt"), "generatedBy": d.get("_generatedBy"),
                    "ageHours": age_hours(d.get("_generatedAt")), "data": data, "error": err})
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "holons": out}


def projects_api():
    """Every ledger the registry names, parsed by the tasks tool; counts are derived at read time, never stored."""
    out = []
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        rel = h["tasks"]; ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        e = {"id": h["id"], "name": h.get("name"), "description": h.get("description"), "path": rel, "holonPath": h.get("path"), "exists": os.path.isfile(ap)}
        if e["exists"]:
            p = ledger.parse(ledger.read(ap))
            e.update(mtime=dt.datetime.fromtimestamp(os.path.getmtime(ap)).strftime("%Y-%m-%d"),
                     groups=[{"name": g, "items": p["groups"][g]} for g in p["order"]], errors=p["errors"], summary=ledger.summary(p))
        out.append(e)
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": ledger.today(), "projects": out}


# ---- the Findings view (2026-09-17, the findings-routing design, piece 5) ----
# Every producer that finds something -- the night agent, brain-lint, the dispatcher, a holon handoff -- files it as an
# item on the ledger of the holon it belongs to, carrying a `#source:<producer>` tag; a finding raised AGAIN becomes
# `repeats:N` on the same item rather than a second one. This reads those items back across every registered ledger.
# Nothing here is computed that the ledgers do not already say: the age is today minus the item's own created date and
# the repeat count is the number written on the line. The owner's /today is untouched -- this is the queue the head agent
# drains at rounds, not a page that asks the owner for anything.
FINDING_SOURCE_TAG = "source:"
FINDING_KEY_TAG = "key:"
FINDING_OLD_DAYS = 14        # an open finding this old is marked on the page
FINDING_LOUD_REPEATS = 3     # ... and so is one raised this many times
FINDING_OPEN_MARKS = (" ", "?", "-")   # an open task, an open question, a blocked task


def _tag_value(it, prefix):
    for t in it.get("tags") or []:
        if t.startswith(prefix):
            v = t[len(prefix):].strip()
            if v:
                return v
    return None


def finding_fields(it):
    """(source, key, repeats, text) off one parsed item, whichever way its line carries them.

    The tags first (`#source:night-agent-86`, `#key:...`), then the item's own fields (`repeats:` once tasks.py knows
    the key), and last the TEXT: the shared parser keeps an unknown `key:value` segment with the text, so a line written
    before the tool learned `repeats:` still reads here instead of leaving `repeats:3` in the middle of a sentence.
    That fallback is why this page works whether or not the ledger tool has landed its half."""
    src = it.get("source") or _tag_value(it, FINDING_SOURCE_TAG)      # the tool's own field first (it parses the same tag), the tag itself second
    key = it.get("key") or _tag_value(it, FINDING_KEY_TAG)
    rep = it.get("repeats")
    text = it.get("text") or ""
    if src is None or key is None or rep is None:
        parts = text.split(ledger.SEP)
        keep = parts[:1]
        for seg in parts[1:]:
            k, colon, v = seg.partition(":")
            k, v = k.strip(), v.strip()
            if colon and k == "repeats" and rep is None:
                rep = v; continue
            if colon and k == "source" and src is None:
                src = v or None; continue
            if colon and k == "key" and key is None:
                key = v or None; continue
            keep.append(seg)
        text = ledger.SEP.join(keep)
    try:
        rep = int(str(rep).strip()) if str(rep or "").strip() else 0
    except ValueError:
        rep = 0
    return src, key, rep, text.strip()


def days_since(iso, ref=None):
    """Whole days from a YYYY-MM-DD to today (the server's clock, never the browser's). None on a date that will not parse."""
    try:
        d = dt.date.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None
    ref = ref or dt.date.today()
    return (ref - d).days


def findings_api(source=None, project=None, owner=None):
    """Every OPEN item carrying a source tag, across every ledger the registry names, newest pain first.

    Sorted by repeats then age, because a finding raised five nights running is the one the loop is failing on. The
    counts are taken over ALL of them before any filter is applied, so the page's chips keep saying how big each pile
    is while one of them is being read. Filters: `source` by prefix, `project` by holon id, `owner` by name."""
    try:
        refd = dt.date.fromisoformat(ledger.today())
    except ValueError:
        refd = dt.date.today()
    rows = []
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        rel = h["tasks"]; ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:
            continue
        for it in p["items"]:
            if it["mark"] not in FINDING_OPEN_MARKS:
                continue
            src, key, rep, text = finding_fields(it)
            if not src:
                continue
            age = days_since(it.get("created"), refd)
            rows.append({"id": it["id"], "project": h["id"], "projectName": h.get("name") or h["id"], "file": rel,
                         "owner": it.get("owner"), "to": it.get("to"), "kind": it["kind"], "mark": it["mark"],
                         "state": it["state"], "milestone": it.get("milestone"), "text": text,
                         "date": it.get("created"), "age_days": age, "repeats": rep, "source": src, "key": key,
                         "links": it.get("links") or [], "note": it.get("note"), "due": it.get("due"), "blocked": it.get("blocked"),
                         "people": it.get("people") or [],
                         "tags": [t for t in (it.get("tags") or []) if not t.startswith((FINDING_SOURCE_TAG, FINDING_KEY_TAG))],
                         "held": ledger.is_held(it)})
    by_source, by_project = {}, {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
        by_project[r["project"]] = by_project.get(r["project"], 0) + 1
    counts = {"total": len(rows), "repeated": sum(1 for r in rows if r["repeats"] >= 1),
              "loud": sum(1 for r in rows if r["repeats"] >= FINDING_LOUD_REPEATS),
              "old": sum(1 for r in rows if (r["age_days"] or 0) >= FINDING_OLD_DAYS),
              "questions": sum(1 for r in rows if r["kind"] == "question"),
              "bySource": by_source, "byProject": by_project}
    pre = (source or "").strip().lower()
    own = (owner or "").strip().lower()
    if own and not own.startswith("@"):
        own = "@" + own
    out = [r for r in rows
           if (not pre or r["source"].lower().startswith(pre))
           and (not project or r["project"] == project)
           and (not own or str(r["owner"] or "").lower() == own)]
    out.sort(key=lambda r: (-r["repeats"], -(r["age_days"] or 0), r["project"], r["id"]))
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": ledger.today(),
            "filter": {"source": source or None, "project": project or None, "owner": owner or None},
            "marks": {"oldDays": FINDING_OLD_DAYS, "loudRepeats": FINDING_LOUD_REPEATS},
            "ledgers": [h["id"] for h in registry().get("holons", []) if h.get("tasks")],
            "counts": counts, "shown": len(out), "items": out}


# ---- the Agents panel (2026-09-08; ledger T-0001 / T-0022, ideas E15): the orchestration view ----
# Read-only, and every number comes from something the machine already wrote. Three sources, none recomputed here:
#   1. the Claude Code session transcripts, ~/.claude/projects/<the brain path with every non-alphanumeric as ->/<session>.jsonl.
#      One JSON object per line. An `Agent` tool_use spawns a sub-agent (description, subagent_type, model, run_in_background);
#      a FOREGROUND one answers in the matching tool_result line, whose `toolUseResult` carries agentId / agentType /
#      resolvedModel / status / totalDurationMs / totalTokens / totalToolUseCount and the report in `content`; a BACKGROUND one
#      answers {"status": "async_launched"} at once and its report arrives later in a <task-notification> block (task-id =
#      the agentId, tool-use-id = the spawning tool_use, status, summary, result, usage). That block reaches the transcript in
#      THREE carriers, all three seen in one session on 2026-09-08: a plain `user` line whose content is the block; a
#      `queue-operation` line (enqueue, then remove) carrying it in top-level `content` when the answer lands while the main
#      thread is busy; and an `attachment` line of type queued_command carrying it in `prompt`. Reading only the first left
#      finished agents showing as running -- three of that session's answers never arrived as a user line at all.
#      The tasks/<agentId>.output files beside the session are empty on this machine, so they are not read. This format is Claude Code-internal and may shift: every
#      field is read defensively and a file that will not parse is reported as an error row, never guessed at.
#   2. context/log.md -- the last action per brain agent id.
#   3. the project ledgers the registry names -- the open @claude tasks: what agents are on.
# T-0004 (settled here): serve.py reads the transcript files directly. No session writes a sessions snapshot file, and this
# panel stores nothing about a session anywhere in the brain.
AGENT_SESSIONS_MAX = 30          # newest N session files
AGENT_DAYS = 14                  # ...or the last N days, whichever is smaller
AGENT_ACTIVE_MINUTES = 10        # a session whose last line is younger than this shows the running mark
AGENT_STALE_MINUTES = 90         # ...and a sub-agent whose session kept going this long past its launch without an answer
                                 # is unknown, not running: nothing that reports back stays silent through 90 minutes of
                                 # later turns. Below it, in a live session, running is still the honest reading.
AGENT_REPORT_CHARS = 600         # the report shown on the card; the rest sits behind the expand
AGENT_REPORT_MAX = 8000          # ...and even the expand is capped, so one huge report cannot swell the response
AGENT_PROMPT_CHARS = 420
# Tokens never reach a page (rules 3), and a prompt or a report can quote one. Masked on the way out, in both.
SECRET_RE = re.compile(r"\b(?:pf_tok_|pfk_|sk-ant-|sk-|ghp_|gho_|github_pat_|xox[baprs]-|AIza)[A-Za-z0-9_\-]{12,}")
HARNESS_RE = re.compile(r"^\[(harness:.*?)\]\s*", re.S)   # the harness note the runtime prefixes to some sub-agent output
LOG_LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})\]\s*\[([^\]]+)\]\s+([A-Z][A-Z_-]*)\s*--\s*(.*)$")
_sessions_cache = {}             # path -> (mtime, size, parsed session)


def mask_secrets(s):
    return SECRET_RE.sub(lambda m: m.group(0)[:7] + "…[redacted]", s) if s else s


def clip(s, n):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n].rstrip() + "…"


def sessions_dir():
    """~/.claude/projects/<cwd with every non-alphanumeric replaced by ->, which is how Claude Code names a project folder."""
    d = os.path.join(os.path.expanduser("~"), ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", BRAIN))
    return d if os.path.isdir(d) else None


def iso_utc(ts):
    try:
        return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")) if ts else None
    except Exception:
        return None


def minutes_since(ts):
    d = iso_utc(ts)
    if not d:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - d).total_seconds() / 60.0


def minutes_between(a, z):
    """Minutes from one transcript stamp to another, both read defensively; None if either will not parse."""
    a, z = iso_utc(a), iso_utc(z)
    if not a or not z:
        return None
    a = a.replace(tzinfo=dt.timezone.utc) if a.tzinfo is None else a
    z = z.replace(tzinfo=dt.timezone.utc) if z.tzinfo is None else z
    return (z - a).total_seconds() / 60.0


def blocks_text(content):
    """The text of a tool_result / toolUseResult content: a plain string, or the text blocks of a list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
    return ""


def session_title(raw):
    """A slash command, a scheduled task and a plain question all open a session; each says its name differently."""
    s = (raw or "").strip()
    if not s:
        return None
    m = re.search(r"<command-args>(.*?)</command-args>", s, re.S)
    if m and m.group(1).strip():
        s = m.group(1).strip()
    else:
        m = re.search(r"<command-name>\s*/?([\w-]+)", s)
        if m:
            s = "/" + m.group(1)
        else:
            m = re.search(r'<scheduled-task\s+name="([^"]+)"', s)
            if m:
                s = "scheduled: " + m.group(1)
    s = re.sub(r"<[^>]+>", " ", s)
    return clip(re.sub(r"\s+", " ", s), 80) or None


def tag_text(text, tag, greedy=False):
    pat = "<%s>(.*)</%s>" % (tag, tag) if greedy else "<%s>(.*?)</%s>" % (tag, tag)
    m = re.search(pat, text, re.S)
    return m.group(1) if m else None


def notification(text):
    """A <task-notification> block: a background agent's answer, arriving as a user line long after the launch.
    <result> is read greedily -- the harness neutralizes control tags inside it, so the LAST closing tag is the real one."""
    def num(t):
        v = (tag_text(text, t) or "").strip()
        return int(v) if v.isdigit() else None
    return {"taskId": tag_text(text, "task-id"), "toolUseId": tag_text(text, "tool-use-id"),
            "status": (tag_text(text, "status") or "").strip() or None, "summary": tag_text(text, "summary"),
            "result": tag_text(text, "result", greedy=True),
            "tokens": num("subagent_tokens"), "toolUses": num("tool_uses"), "durationMs": num("duration_ms")}


def notification_texts(o, msg_content):
    """Every <task-notification> block on one transcript line, whichever carrier it rode in on: a string message, the text
    blocks of a list message, a queue-operation's top-level `content`, or a queued_command attachment's `prompt`. The block
    is cut out of its surroundings first, so a <system-reminder> wrapper (or any other prose the harness puts around it)
    reads the same as a bare one."""
    raw = []
    if isinstance(msg_content, str):
        raw.append(msg_content)
    elif isinstance(msg_content, list):
        raw += [b["text"] for b in msg_content if isinstance(b, dict) and isinstance(b.get("text"), str)]
    if isinstance(o.get("content"), str):
        raw.append(o["content"])
    a = o.get("attachment")
    if isinstance(a, dict) and isinstance(a.get("prompt"), str):
        raw.append(a["prompt"])
    out = []
    for s in raw:
        i = s.find("<task-notification>")
        if i < 0:
            continue
        j = s.rfind("</task-notification>")
        out.append(s[i:j + len("</task-notification>")] if j > i else s[i:])
    return out


def answered(sa, n, ts):
    """Fold one notification into the sub-agent it belongs to. The same answer arrives up to three times (enqueued, attached,
    then delivered as a user line when the thread frees up), so the FIRST carrier fixes the end time -- that is the moment the
    agent actually stopped -- and later copies only refresh what they carry."""
    st = (n["status"] or "").strip()
    sa["status"] = st or "completed"
    sa["running"] = st.lower() in ("running", "in_progress")
    sa["_answeredAt"] = sa.get("_answeredAt") or ts
    sa["ended"] = sa["_answeredAt"]
    sa["summary"] = n["summary"] or sa["summary"]
    rep = mask_secrets((n["result"] or "").strip())
    if rep or not sa["_report"]:
        sa["_report"] = rep
    for k in ("tokens", "toolUses", "durationMs"):
        if n[k] is not None:
            sa[k] = n[k]


def parse_session(path):
    """One transcript file -> the session and its sub-agents. Streamed line by line; a file is never held in memory whole."""
    spawns, by_agent, order = {}, {}, []
    first_ts = last_ts = title = first_user = cwd = branch = version = None
    models, turns = {}, 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            ts = o.get("timestamp")
            if ts:
                first_ts = first_ts or ts
                last_ts = ts
            t = o.get("type")
            if t == "custom-title":
                title = o.get("customTitle") or title
                continue
            cwd = o.get("cwd") or cwd
            branch = o.get("gitBranch") or branch
            version = o.get("version") or version
            msg = o.get("message") or {}
            content = msg.get("content")
            if t == "assistant" and msg.get("model"):
                models[msg["model"]] = models.get(msg["model"], 0) + 1
            if not o.get("isSidechain"):
                notes = notification_texts(o, content)
                for txt in notes:
                    n = notification(txt)
                    # the tool_use that spawned it, or -- if the launch line is not in this file -- the agentId it was given
                    sa = spawns.get(n["toolUseId"]) or by_agent.get(n["taskId"])
                    if sa is not None:
                        answered(sa, n, ts)
                if notes:
                    continue                      # a notification is the runtime talking, never one of the owner's turns
            if t == "user" and not o.get("isSidechain"):
                if isinstance(content, str):
                    turns += 1
                    first_user = first_user or content
                elif isinstance(content, list) and o.get("toolUseResult") is None:
                    txt = next((b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text"), None)
                    if txt:
                        turns += 1
                        first_user = first_user or txt
            if not isinstance(content, list):
                continue
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and b.get("name") == "Agent":
                    inp = b.get("input") or {}
                    sa = {"toolUseId": b.get("id"), "agentId": None,
                          "description": inp.get("description") or "(no description)",
                          "type": inp.get("subagent_type") or "general-purpose", "model": inp.get("model"),
                          "background": bool(inp.get("run_in_background")), "isolation": inp.get("isolation"),
                          "ask": clip(mask_secrets(inp.get("prompt") or ""), AGENT_PROMPT_CHARS),
                          "started": ts, "ended": None, "running": True, "status": "running", "summary": None,
                          "durationMs": None, "tokens": None, "toolUses": None, "_report": None}
                    spawns[b["id"]] = sa
                    order.append(sa)
                    continue
                if b.get("type") != "tool_result":
                    continue
                sa = spawns.get(b.get("tool_use_id"))
                if sa is None:
                    continue
                tur = o.get("toolUseResult")
                if not isinstance(tur, dict) or not ("agentType" in tur or "agentId" in tur):
                    # a spawn that never became an agent (a permission denial, an input error): the result comes back as
                    # plain text with no agentId, so it is recorded as not started rather than left looking like a runner
                    txt = blocks_text(b.get("content")) or (tur if isinstance(tur, str) else "")
                    if txt or b.get("is_error"):
                        sa["status"] = "not started"
                        sa["running"] = False
                        sa["ended"] = ts
                        sa["_report"] = mask_secrets(clip(txt, 400))
                    continue
                sa["agentId"] = tur.get("agentId") or sa["agentId"]
                sa["type"] = tur.get("agentType") or sa["type"]
                sa["model"] = tur.get("resolvedModel") or sa["model"]
                if sa["agentId"]:
                    by_agent[sa["agentId"]] = sa
                if tur.get("status") == "async_launched":
                    sa["background"] = True          # launched; its answer arrives later as a <task-notification>
                    continue
                sa["status"] = tur.get("status") or "completed"
                sa["running"] = False
                sa["ended"] = ts
                sa["durationMs"] = tur.get("totalDurationMs")
                sa["tokens"] = tur.get("totalTokens")
                sa["toolUses"] = tur.get("totalToolUseCount")
                sa["_report"] = mask_secrets(blocks_text(tur.get("content") or b.get("content")))
    sid = os.path.splitext(os.path.basename(path))[0]
    mins = minutes_since(last_ts)
    active = mins is not None and mins < AGENT_ACTIVE_MINUTES
    for sa in order:
        rep = (sa.pop("_report", None) or "").strip()[:AGENT_REPORT_MAX]
        h = HARNESS_RE.match(rep)          # the harness's own note about the output rides in front of the answer: lifted out
        if h:
            sa["harnessNote"] = h.group(1).strip()
            rep = rep[h.end():].strip()
        sa["report"] = clip(rep, AGENT_REPORT_CHARS) or None
        sa["reportFull"] = rep if len(rep) > AGENT_REPORT_CHARS else None
        if sa["durationMs"] is None and sa["ended"]:
            a, z = iso_utc(sa["started"]), iso_utc(sa["ended"])
            if a and z:
                sa["durationMs"] = int((z - a).total_seconds() * 1000)
        sa.pop("_answeredAt", None)
        if sa["running"]:
            stale = minutes_between(sa["started"], last_ts)
            if stale is not None and stale > AGENT_STALE_MINUTES:
                sa["running"] = False                # the session kept working for 90+ minutes and it never reported back
                sa["status"] = "unknown (no report found)"
            elif not active:
                sa["running"] = False
                sa["status"] = "no answer recorded"  # the session stopped before this one reported back
    return {"id": sid[:8], "sessionId": sid, "file": os.path.basename(path), "title": title or session_title(first_user),
            "cwd": cwd, "branch": branch, "cliVersion": version, "started": first_ts, "lastActive": last_ts,
            "minutesIdle": round(mins, 1) if mins is not None else None, "active": active, "userTurns": turns,
            "model": max(models, key=models.get) if models else None,
            "models": sorted(models, key=models.get, reverse=True),
            "subagents": order,
            "counts": {"subagents": len(order), "running": sum(1 for s in order if s["running"]),
                       "background": sum(1 for s in order if s["background"])}}


def session(path):
    """Cached per file identity: the live session's file grows every turn, the other 29 are parsed once."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    hit = _sessions_cache.get(path)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2]
    try:
        s = parse_session(path)
    except Exception as e:
        s = {"id": os.path.basename(path)[:8], "sessionId": os.path.splitext(os.path.basename(path))[0],
             "file": os.path.basename(path), "title": None, "error": "%s: %s" % (type(e).__name__, e),
             "lastActive": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"), "active": False,
             "subagents": [], "counts": {"subagents": 0, "running": 0, "background": 0}}
    _sessions_cache[path] = (st.st_mtime, st.st_size, s)
    if len(_sessions_cache) > 120:
        _sessions_cache.clear()
    return s


def brain_agents():
    """The last action per agent id in the log -- who acted, what, when. Read as written; nothing
    recomputed. Spans the whole rotation (live file + archive months), so an agent whose last line
    fell into a rotated month still appears, exactly as before the 2026-09-18 rotation."""
    if not os.path.isfile(os.path.join(BRAIN, LOG_REL.replace("/", os.sep))):
        return []
    last = {}
    for line in log_lines():
        m = LOG_LINE_RE.match(line)
        if m:
            last[m.group(3)] = {"agent_id": m.group(3), "at": m.group(1) + " " + m.group(2),
                                "last_action": m.group(4), "last_text": clip(m.group(5), 120)}
    return sorted(last.values(), key=lambda r: r["at"], reverse=True)[:24]


def on_ledgers():
    """The open @claude tasks in every ledger the registry names: what agents are on. Same parser as /api/projects."""
    out = []
    for h in registry().get("holons", []):
        rel = h.get("tasks")
        ap = os.path.join(BRAIN, (rel or "").replace("/", os.sep))
        if not rel or not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:
            continue
        for group in p["order"]:
            for it in p["groups"][group]:
                if it["kind"] == "task" and it["state"] in ("open", "blocked") and it["owner"] == "@claude":
                    out.append({"project": h.get("name") or h["id"], "projectId": h["id"], "path": rel,
                                "id": it["id"], "text": clip(it["text"], 160), "owner": it["owner"],
                                "milestone": group, "state": it["state"], "blocked": it["blocked"],
                                "due": it["due"], "tags": it["tags"]})
    out.sort(key=lambda r: (r["state"] == "blocked", r["project"], r["id"]))
    return out[:80]


def agents_api():
    d = sessions_dir()
    files, note = [], None
    if d:
        cutoff = time.time() - AGENT_DAYS * 86400
        allf = sorted((os.path.join(d, n) for n in os.listdir(d) if n.endswith(".jsonl")),
                      key=os.path.getmtime, reverse=True)
        files = [p for p in allf[:AGENT_SESSIONS_MAX] if os.path.getmtime(p) >= cutoff]
        if not files and allf:
            note = "no session touched in the last %d days (%d transcripts on disk)" % (AGENT_DAYS, len(allf))
    else:
        note = "no Claude Code transcript folder for this brain path"
    sessions = [s for s in (session(p) for p in files) if s]
    sessions.sort(key=lambda s: s.get("lastActive") or "", reverse=True)
    # what the bubbles need on top of the transcript (2026-09-10, T-0117 + T-0101 + T-0102): which of these sessions are
    # this app's own conversations, whether each can be opened in the chat, and the send-to lines between conversations.
    # session() hands back a CACHED dict, so every session is copied before anything is added to it.
    rows = chat_index_rows()
    by_sid = {r.get("session_id"): r for r in rows if r.get("session_id")}
    out = []
    for s in sessions:
        s = dict(s)
        row = by_sid.get(s.get("sessionId"))
        ok, why = adopt_check(s, row)
        s["chat"] = row.get("id") if row else None
        s["chatProject"] = row.get("project") if row else None
        s["chatTitle"] = row.get("title") if row else None
        s["chatRunning"] = bool(row and row.get("running"))
        s["adopted"] = bool(row and row.get("adopted"))
        s["adopt"] = {"ok": ok, "reason": why}
        out.append(s)
    handoffs = [{"from": r["id"], "to": hx["chat"], "at": hx.get("at"), "turn": hx.get("turn")}
                for r in rows for hx in (r.get("handoffs") or [])
                if isinstance(hx, dict) and hx.get("direction") == "out" and hx.get("chat")]
    return {"generatedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": {"transcripts": d, "window": "newest %d sessions within %d days" % (AGENT_SESSIONS_MAX, AGENT_DAYS),
                       "log": LOG_REL, "note": note},
            "sessions": out, "chats": rows, "handoffs": handoffs, "projects": chat_projects(), "models": chat_models(),
            "brain_agents": brain_agents(), "on_ledgers": on_ledgers()}


# ---- the People panel + call preps (2026-09-09; ledger T-0026, the owner asked for a prep area in the app) ----
# Every people/ card as a row, the card rendered, and the dated preps derived from it. Format: skills/call-prep/call-prep-format.md.
# THE CARD IS THE TRUTH and this panel never writes one (Correction #42). The only thing it writes is a prep skeleton under
# deliverables/call-prep/, and only the parts that can be derived WITHOUT JUDGMENT: who they are, the last touchpoint, what is
# owed, the flags. Sections 3 (what the call decides), 4 (bring) and 6 (close) are left for /call-prep to fill after it has read
# the card, the transcripts and the governing documents (Correction #49). people/ never travels with a team copy, so every
# endpoint here answers 403 in propose mode.
# A prep is keyed to a CALL, not to a person (2026-09-09, T-0027): the key is a person slug, a group id, or slugs joined by +.
PREP_FILE_RE = re.compile(r"^(?P<slug>[a-z0-9][a-z0-9._+-]*)-call-prep-(?P<date>\d{4}-\d{2}-\d{2})\.md$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
HEAD_RE = re.compile(r"^(#{2,3})\s+(.*)$")
H2_RE = re.compile(r"^##\s+(.*)$")      # the card's own sections, the unit the People panel collapses (2026-09-09)
BULLET_RE = re.compile(r"^\s*[-*+]\s+\S")
# what one side owes the other, in the words the owner's own cards use for it
OWED_RE = re.compile(r"\b(owe|owes|owed|owing|waiting on|waiting for|send|sends|sending|ask|asks|asked|unasked)\b", re.I)
STRONG_OWED_RE = re.compile(r"\b(owe|owes|owed|owing|waiting on|waiting for|unasked|not sent|never sent|still open)\b", re.I)
SKIP_OWED_RE = re.compile(r"^\W*\*{0,2}(card (created|updated)|last updated|source|companion records)\b", re.I)
# the do-not-say / do-not-infer lines a prep has to carry into the room
DONOT_RE = re.compile(r"\b(do not|don't|do NOT|never|undisclosed|not raised|not been told|not disclosed|no authority)\b", re.I)
_people_cache = {}               # people/<file>.md -> ((mtime, size), parsed row)


def split_fm(text):
    """(frontmatter dict, body lines). Top-level `key: value` lines only, same shallow read the holons panel uses."""
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, min(len(lines), 200)):
            if lines[i].strip() == "---":
                fm = {}
                for l in lines[1:i]:
                    if ":" in l and not l.startswith((" ", "\t", "-")):
                        k, v = l.split(":", 1)
                        fm[k.strip()] = v.strip().strip('"').strip("'")
                return fm, lines[i + 1:]
    return {}, lines


def h2_section(body, title):
    """The lines under `## <title>`, to the next `## `. Prefix match, so `## Key Notes (interview signal)` answers to "Key Notes"."""
    pat = re.compile(r"^##\s+" + re.escape(title) + r"\b", re.I)
    out, on = [], False
    for l in body:
        if l.startswith("## "):
            if on:
                break
            on = bool(pat.match(l))
            continue
        if on:
            out.append(l)
    return out


def first_line(lines, n=200):
    for l in lines:
        s = re.sub(r"\s+", " ", re.sub(r"^\s*[-*+]\s+", "", l.strip().lstrip("> ")).strip())
        if s and not s.startswith(("---", "<!--", "|")):
            return clip(s, n)
    return ""


def first_para(lines, n=700):
    buf = []
    for l in lines:
        s = l.strip().lstrip("> ").strip()
        if not s or s.startswith(("---", "<!--")):
            if buf:
                break
            continue
        buf.append(s)
    return clip(re.sub(r"\s+", " ", " ".join(buf)), n)


def bullets(lines):
    return [re.sub(r"^\s*[-*+]\s+", "", l).strip() for l in lines if BULLET_RE.match(l)]


def card_folds(body):
    """The dated folds, newest first. Cards write them three ways (`## [2026-08-27] ...`, `## 2026-09-08 fold (...)`,
    `## ... established 2026-08-17`), so the date is matched anywhere in the heading and stripped when it leads."""
    out = []
    for l in body:
        m = HEAD_RE.match(l)
        if not m:
            continue
        d = DATE_RE.search(m.group(2))
        if not d:
            continue
        head = re.sub(r"^\[?" + d.group(1) + r"\]?\s*[-–—:]*\s*", "", m.group(2).strip()).strip()
        out.append({"date": d.group(1), "headline": clip(head or m.group(2).strip(), 180)})
    out.sort(key=lambda r: r["date"], reverse=True)
    return out


def card_sections(body):
    """The card cut at its `## ` headings: [{title, lines, bytes}], with anything above the first heading as the preamble.
    On 2026-09-09 the owner asked for every part of the card to collapse, since all of it was hard to follow. The page
    renders one collapsed block per section; the cut is here so the markdown is split the same way every time."""
    out, cur = [], {"title": "", "lines": []}
    for l in body:
        m = H2_RE.match(l)      # `## ` only: an h3 stays inside the section it belongs to
        if m:
            if cur["lines"] or cur["title"]:
                out.append(cur)
            cur = {"title": m.group(1).strip(), "lines": []}
            continue
        cur["lines"].append(l)
    if cur["lines"] or cur["title"]:
        out.append(cur)
    for s in out:
        while s["lines"] and not s["lines"][-1].strip():
            s["lines"].pop()
        s["text"] = "\n".join(s["lines"]).strip()
        s["chars"] = len(s["text"])
        s.pop("lines", None)
    return [s for s in out if s["title"] or s["text"]]


# ---- card format v2: one dated status line, a front and a history (2026-09-11, ledger T-0015) ----
# people/readme.md "Card format v2" is authoritative. A card carries ONE status -- `**Where it stands (YYYY-MM-DD):** ...`
# directly under the `# Name` title, rewritten in place on every change -- and everything below it is history. The page draws a
# front made only of the standard sections named here plus fields computed here, and folds the rest away. Nothing in this file
# writes a card (Correction #42): an unconverted card renders with its old Status inside the history and a stale mark on it,
# which is the point. The defect this replaces: Ria Raheja's Status section stopped on 2026-06-23 while three later folds moved
# her twice and then ended the placement, and on 2026-09-10 an agent read the top of the card and reported the June state.
STANDS_RE = re.compile(r"^\s*\*\*Where it stands\s*\((\d{4}-\d{2}-\d{2})\)\s*:\*\*\s*(.+?)\s*$", re.I)
STATUS_TAG_RE = re.compile(r"\[status\]", re.I)
STANDS_STALE_DAYS = 30
FRONT_TITLES = ("role & relationship", "what they are building", "contact")   # the front's own sections, in draw order


def norm_head(t):
    """A heading compared the way the format names it: collapsed, lowercased, "and" and "&" the same thing."""
    return re.sub(r"\s+", " ", str(t or "").strip().lower()).replace(" and ", " & ")


def days_between(a, b):
    try:
        return (dt.date.fromisoformat(str(b)[:10]) - dt.date.fromisoformat(str(a)[:10])).days
    except Exception:
        return None


def card_stands(body):
    """The card's one status line as {date, text, line}, or None. Read ONLY from the preamble above the first `## ` heading,
    so a sentence further down that happens to use the words can never be taken for the card's status."""
    for l in body:
        if l.startswith("## "):
            break
        m = STANDS_RE.match(l)
        if m:
            return {"date": m.group(1), "text": clip(m.group(2).strip(), 600), "line": l.strip()}
    return None


def status_folds(body):
    """Dates of the dated folds whose heading carries `[status]` -- a change in where the person stands -- newest first."""
    out = []
    for l in body:
        m = HEAD_RE.match(l)
        if m and STATUS_TAG_RE.search(m.group(2)):
            d = DATE_RE.search(m.group(2))
            if d:
                out.append(d.group(1))
    return sorted(out, reverse=True)


def stands_state(body, today=None):
    """(the line, {stale, why, kind, days}) per the staleness rule in people/readme.md: no line at all, a line more than
    30 days old, or a `[status]` fold dated after the line. Reported here, never repaired here."""
    today = today or dt.date.today().isoformat()
    st, sf = card_stands(body), status_folds(body)
    if not st:
        return None, {"stale": True, "kind": "missing", "days": None,
                      "why": "no Where it stands line (card format v2)"}
    days = days_between(st["date"], today)
    if sf and sf[0] > st["date"]:
        return st, {"stale": True, "kind": "behind", "days": days,
                    "why": "a [status] fold dated %s is newer than the line" % sf[0]}
    if days is not None and days > STANDS_STALE_DAYS:
        return st, {"stale": True, "kind": "old", "days": days,
                    "why": "the line is %d days old" % days}
    return st, {"stale": False, "kind": "", "days": days, "why": ""}


def card_two_sides(body):
    """(header, front, back). `front` is the standard sections in the order the format declares; `back` is everything else,
    which is where an old `## Status`, the dated folds, the flags and the pipeline detail all land. `header` is the preamble
    above the first heading minus the status line, and it rides on the BACK: a card's blockquote header often carries a second,
    older status, and the front holds exactly one."""
    header, front, back = [], [], []
    for s in card_sections(body):
        if not s["title"]:
            txt = "\n".join(l for l in s["text"].split("\n") if not STANDS_RE.match(l) and not l.startswith("# ")).strip()
            if txt:
                header.append({"title": "Card header", "text": txt, "chars": len(txt)})
        elif norm_head(s["title"]) in FRONT_TITLES:
            front.append(s)
        else:
            back.append(s)
    front.sort(key=lambda s: FRONT_TITLES.index(norm_head(s["title"])))
    return header, front, header + back


def contact_history(slug, fold_dates=(), today=None):
    """Last contact and how often the calls land -- computed, never typed on a card (people/readme.md, front item 3).
    Two sources the brain already holds: the dated folds on the card, and `transcript_index()`, every transcript in
    `transcripts/` and the app mirror with its participants mapped to card slugs (the same index the groups use). The folder
    is read rather than `transcripts/INDEX.md`, because that table is hand-maintained and is currently missing rows for calls
    that are on disk. Cadence is the median gap between the calls of the last year and stays None below three calls: two
    points are not a frequency."""
    today = today or dt.date.today().isoformat()
    dates = sorted({r["date"] for r in transcript_index()["rows"] if slug in (r.get("slugs") or [])}, reverse=True)
    year = [d for d in dates if (days_between(d, today) or 0) <= 365]
    gaps = sorted(g for g in (days_between(year[i + 1], year[i]) for i in range(len(year) - 1)) if g is not None)
    last_fold = max([d for d in fold_dates if d], default=None)
    last = max([d for d in (dates[0] if dates else None, last_fold) if d], default=None)
    return {"last": last, "kind": ("call" if dates and last == dates[0] else ("fold" if last else "")),
            "days": days_between(last, today) if last else None,
            "lastCall": dates[0] if dates else None,
            "calls90": len([d for d in dates if (days_between(d, today) or 999) <= 90]),
            "calls365": len(year), "cadenceDays": (gaps[len(gaps) // 2] if len(gaps) >= 2 else None)}


def owed_from(body):
    """What each side owes the other, off the card's Flags and Status bullets. A LEAD for the prep, never a claim of its own:
    a keyword match cannot tell an obligation from a sentence that happens to use the word, so the strong signals (owe, waiting
    on, unasked) sort above the weak ones (ask, send) and the card's own bookkeeping bullets are dropped."""
    out = []
    for t in ("Flags", "Status"):
        for b in bullets(h2_section(body, t)):
            if not OWED_RE.search(b) or SKIP_OWED_RE.search(b):
                continue
            out.append({"section": t, "text": clip(b, 300), "_rank": 0 if STRONG_OWED_RE.search(b) else 1})
    out.sort(key=lambda r: r["_rank"])
    for r in out:
        r.pop("_rank", None)
    return out[:8]


def donot_from(body):
    out = []
    for t in ("Flags", "Status", "Key Notes"):
        for b in bullets(h2_section(body, t)):
            if DONOT_RE.search(b):
                out.append(clip(b, 300))
    return out[:8]


def parse_card(rel, ap):
    with open(ap, "r", encoding="utf-8-sig") as f:
        text = f.read()
    fm, body = split_fm(text)
    name = next((l[2:].strip() for l in body if l.startswith("# ")), fm.get("name") or os.path.basename(rel)[:-3])
    folds = card_folds(body)
    last = max([f["date"] for f in folds] + ([fm["last-fold"]] if DATE_RE.fullmatch(str(fm.get("last-fold", "")).strip() or "x") else []), default=None)
    flags = bullets(h2_section(body, "Flags"))
    stands, state = stands_state(body)          # card format v2: the one dated status line, and whether it has gone stale
    return {"slug": os.path.basename(rel)[:-3], "name": name, "path": rel,
            "role": first_line(h2_section(body, "Role & Relationship"), 120),
            "status": first_line(h2_section(body, "Status"), 200),
            "stands": stands, "stale": state["stale"], "staleWhy": state["why"], "staleKind": state["kind"],
            "statusFold": (status_folds(body) or [None])[0],
            "category": fm.get("category", ""), "location": fm.get("location", ""),
            # which organization they belong to, and for a PF mentee placed inside one, where they were placed
            # (people/readme.md, 2026-09-16). The People page groups the list on these two.
            "org": fm.get("org", ""), "placedAt": fm.get("placed_at", ""),
            "lastFold": last, "folds": len(folds), "flags": len(flags),
            "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).strftime("%Y-%m-%d")}


def card_path(slug):
    slug = os.path.basename(str(slug or "").strip())
    if not SLUG_RE.match(slug or "") or slug == "readme":
        return None, None
    rel = "%s/%s.md" % (PEOPLE_REL, slug)
    ap = os.path.join(BRAIN, PEOPLE_REL, slug + ".md")
    return rel, (ap if os.path.isfile(ap) else None)


def preps(slug=None):
    """Every dated prep in deliverables/call-prep/, newest call first. `slug` filters on the FILE KEY, which is a person slug,
    a group id, or slugs joined by + (2026-09-09: a prep is keyed to a call, and a call can have several participants)."""
    root = os.path.join(BRAIN, CALLPREP_REL.replace("/", os.sep))
    out = []
    if os.path.isdir(root):
        for fn in sorted(os.listdir(root)):
            m = PREP_FILE_RE.match(fn)
            if not m:
                continue
            ap = os.path.join(root, fn)
            row = {"path": "%s/%s" % (CALLPREP_REL, fn), "slug": m.group("slug"), "key": m.group("slug"), "call": m.group("date"),
                   "purpose": "", "status": "", "group": "", "participants": [],
                   "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).strftime("%Y-%m-%d"), "bytes": os.path.getsize(ap)}
            try:
                with open(ap, "r", encoding="utf-8-sig") as f:
                    fm, _ = split_fm(f.read(4000))
                row.update(purpose=clip(fm.get("purpose", ""), 140), status=fm.get("status", ""), person=fm.get("person", m.group("slug")),
                           group=fm.get("group", ""),
                           participants=[p.strip() for p in re.sub(r"^\[|\]$", "", fm.get("participants", "")).split(",") if p.strip()])
                # 0.52.1 (2026-09-29): the frontmatter `call:` date wins over the filename's. The team call moved from
                # Monday to Tuesday, its prep kept Monday's filename, and the call page linked an empty skeleton instead.
                fc = str(fm.get("call", "")).strip()[:10]
                if re.match(r"^\d{4}-\d{2}-\d{2}$", fc):
                    row["call"] = fc
            except Exception as e:
                row["error"] = "%s: %s" % (type(e).__name__, e)
            # 2026-09-21: a prep belongs to EVERY participant, not only to its file key. The Mike four-way, keyed
            # dani-plumb+john-kissell+mike-bledsoe, was reachable from nobody's row (the owner could not find it from Mike's row).
            if slug and slug != row["key"] and slug not in row["participants"] and slug not in row["key"].split("+"):
                continue
            out.append(row)
    out.sort(key=lambda r: (r["call"], r["path"]), reverse=True)
    return out


def people_api():
    root = os.path.join(BRAIN, PEOPLE_REL)
    bySlug = {}
    for p in preps():
        # every participant's row carries the prep (2026-09-21), the file key included so a one-to-one prep still lands once
        for s in dict.fromkeys([p["slug"]] + p["slug"].split("+") + p["participants"]):
            bySlug.setdefault(s, []).append(p)
    rows, errors = [], []
    for fn in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if not fn.endswith(".md") or fn == "readme.md":
            continue
        ap = os.path.join(root, fn)
        rel = "%s/%s" % (PEOPLE_REL, fn)
        try:
            st = os.stat(ap)
            hit = _people_cache.get(rel)
            if hit and hit[0] == (st.st_mtime, st.st_size):
                row = dict(hit[1])
            else:
                row = parse_card(rel, ap)
                _people_cache[rel] = ((st.st_mtime, st.st_size), row)
                row = dict(row)
        except Exception as e:
            errors.append({"path": rel, "error": "%s: %s" % (type(e).__name__, e)})
            continue
        ps = bySlug.get(row["slug"]) or []
        row["preps"] = len(ps)
        row["lastPrep"] = ps[0]["call"] if ps else None
        rows.append(row)
    open_by_slug = badges_api()["people"]                       # how many open items are waiting on the owner about this person
    today = ledger.today()
    for row in rows:
        row["open"] = open_by_slug.get(row["slug"], 0)
        row["contact"] = contact_history(row["slug"], [row.get("lastFold")], today)   # computed, never typed on the card
    for row in rows:
        row["weekly"] = is_weekly(row.get("contact") or {})
        row["roleRank"], row["roleBucket"] = role_rank(row)
        row["top"] = bool(row["weekly"] or row["open"])                # the two things that put a card above the fold
    rows.sort(key=lambda r: r["name"].lower())
    rows.sort(key=lambda r: r.get("lastFold") or "", reverse=True)     # newest fold first; stable, so undated cards keep name order
    rows.sort(key=lambda r: r["open"], reverse=True)                   # ...and whoever the owner owes something about comes first
    rows.sort(key=lambda r: r["roleRank"])                             # then by role, in the order the page prints
    rows.sort(key=lambda r: 0 if r["top"] else 1)                      # and the weekly people + anything open sit on top of all of it
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": ledger.today(),
            "folder": PEOPLE_REL, "prepFolder": CALLPREP_REL, "format": "skills/call-prep/call-prep-format.md",
            "count": len(rows), "people": rows, "errors": errors, "prepCount": sum(len(v) for v in bySlug.values()),
            "openTotal": sum(r["open"] for r in rows), "staleCount": sum(1 for r in rows if r.get("stale")),
            "staleDays": STANDS_STALE_DAYS, "order": ORDER_RULE, "weeklyCount": sum(1 for r in rows if r["weekly"]),
            "topCount": sum(1 for r in rows if r["top"]), "roleBuckets": [b[0] for b in ROLE_ORDER] + [ROLE_OTHER]}


# ---- the order of the People list (2026-09-17, ledger T-0157) ----
# The owner asked for the people spoken to weekly and anyone with an open item on top, then by role, so the person talked
# to most is never behind a scroll, with the order rule written in the page rather than guessed per load. So the rule is WRITTEN DOWN here,
# shipped to the page as `order`, and printed under the heading -- one rule, visible, the same on every load.
# WEEKLY is computed, never typed on a card: contact_history() already gives the median gap between the calls of the last
# year and the number in the last ninety days, both read off the transcript folder. ROLE is the card's own
# "Role & Relationship" line, matched against the ladder below; a card whose role matches nothing falls to the bottom
# bucket rather than being guessed at.
WEEKLY_CADENCE_DAYS = 10          # a median gap of ten days or less is "weekly" (a week, plus the slip a real week has in it)
WEEKLY_CALLS_90 = 8               # ...or eight calls in ninety days, which is the same rhythm counted the other way
ROLE_OTHER = "everyone else"
ROLE_ORDER = [
    ("co-founder and partners", r"co-?founder|founder|partner|operations|ops\b|right hand"),
    ("the team", r"\bteam\b|employee|staff|engineer|developer|designer|assistant"),
    ("mentors", r"\bmentor\b(?!ee)|coach|advisor|advis"),
    ("mentees and placements", r"mentee|placed|placement|apprentice|intern"),
    ("candidates", r"candidate|applicant|prospect|interview|pipeline"),
    ("outside", r"client|customer|vendor|investor|contact|friend|family"),
]
ROLE_RE = [(name, re.compile(pat, re.I)) for name, pat in ROLE_ORDER]
ORDER_RULE = {
    "rule": "the people you speak to weekly and anyone with an open item first, then by role, then whoever you owe something about, then the newest fold",
    "weekly": "a median gap of %d days or less between calls in the last year, or %d calls in the last 90 -- computed from the transcripts, never typed on a card" % (WEEKLY_CADENCE_DAYS, WEEKLY_CALLS_90),
    "roles": [b[0] for b in ROLE_ORDER] + [ROLE_OTHER],
    "groups": "organizations keep their grouping; an organization holding someone from the top band is listed first, then by how many cards it holds",
}


def is_weekly(contact):
    cad = contact.get("cadenceDays")
    return bool((cad is not None and cad <= WEEKLY_CADENCE_DAYS) or (contact.get("calls90") or 0) >= WEEKLY_CALLS_90)


def role_rank(row):
    text = " ".join(str(row.get(k) or "") for k in ("role", "stands"))
    for i, (name, rx) in enumerate(ROLE_RE):
        if rx.search(text):
            return i, name
    return len(ROLE_RE), ROLE_OTHER


# ---- the People page's week (round 1b, 2026-10-02; ledger T-0265, T-0202, T-0161) ----
# The owner reported on 9/18 that the people spoken to weekly were not the ones on top (the Asprey group came first),
# on 9/24 that a prep could not be clicked, and on 9/25 that the page was still confusing. Direction:
# deliverables/viewer-direction-people-page-2026-10-02.md. One read-only answer for the face of /people:
#   events    every call in the two calendar files (calendar_events(), the same join the call page uses) with a carded
#             attendee, each prep carrying its state in one word (prep_state);
#   history   per card slug, which of the last four weeks they were on a call: the transcripts (transcript_index(), the
#             folder, not the hand-kept INDEX.md) plus the calendar's calls already over, one count per day;
#   weekly    the people on calls in two or more of those four weeks, the owner excluded (the owner has no card);
#   relation  per card slug, the fold it sits in, from the card's own frontmatter (category, placed_at, org, status) and
#             failing that the section of people/readme.md's directory that lists it. Never the role ladder.
PEOPLE_WEEK_WEEKS = 4
PEOPLE_WEEK_MIN = 2              # weeks out of four with a call: "weekly"
PEOPLE_RELATIONS = [
    ("mentees", "Mentees and placements", "who PF has placed or is placing"),
    ("mentors", "Mentors and their companies", "the mentors, and the people at their companies"),
    ("partners", "Partners and advisors", "the team, partners and advisors"),
    ("candidates", "Candidates", "interviewed, not placed"),
    ("family", "Family and personal", "family, and your own support"),
    ("else", "Everyone else", "outside contacts and old names"),
]
_DIR_SECTIONS = [("personal", r"personal"), ("candidates", r"candidate"), ("team", r"team|founder"),
                 ("mentors", r"mentor"), ("partners", r"partner|advis"), ("operational", r"operational|asprey-side"),
                 ("parked", r"parked|other")]
_fm_cache = {}
PREP_SKELETON_MARK = "Draft with `/call-prep"     # the line prep_v3_text writes under Decide before until /call-prep fills it


def prep_state(rel):
    """One word for a prep: held (its frontmatter says a transcript holds the call, `status: held`, or the older `used`),
    skeleton (the Decide before part still carries the skeleton's own "Draft with /call-prep" line, the test the session
    start uses to decide which preps /call-prep still has to fill), else ready."""
    ap = os.path.join(BRAIN, str(rel or "").replace("/", os.sep))
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except Exception:                                             # noqa: BLE001
        return "missing"
    fm, _ = split_fm(text[:4000])
    if str(fm.get("status") or "").strip().lower() in ("held", "used"):
        return "held"
    return "skeleton" if PREP_SKELETON_MARK in text else "ready"


def card_frontmatter(slug):
    rel, ap = card_path(slug)
    if not ap:
        return {}
    try:
        st = os.stat(ap)
        hit = _fm_cache.get(ap)
        if hit and hit[0] == (st.st_mtime, st.st_size):
            return hit[1]
        with open(ap, "r", encoding="utf-8-sig") as f:
            fm, _ = split_fm(f.read(6000))
        _fm_cache[ap] = ((st.st_mtime, st.st_size), fm)
        return fm
    except Exception:                                             # noqa: BLE001
        return {}


def people_directory():
    """{slug: section key} from the `## People Directory` part of people/readme.md, the hand-kept list a card with no
    category still sits in."""
    ap = os.path.join(BRAIN, PEOPLE_REL, "readme.md")
    out, sec, on = {}, None, False
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            lines = f.read().split("\n")
    except Exception:                                             # noqa: BLE001
        return out
    for l in lines:
        if l.startswith("## "):
            on = "directory" in l.lower()
            sec = None
            continue
        if not on:
            continue
        if l.startswith("### "):
            low = l[4:].lower()
            sec = next((k for k, rx in _DIR_SECTIONS if re.search(rx, low)), None)
            continue
        if sec:
            for s in re.findall(r"\[\[people/([a-z0-9-]+)\.md\]\]", l):
                out.setdefault(s, sec)
    return out


def card_relation(slug, fm, section, mentor_orgs):
    cat = str(fm.get("category") or "").strip().lower()
    status = str(fm.get("status") or "").strip().strip("\"'")
    placed = str(fm.get("placed_at") or "").strip()
    org = str(fm.get("org") or "").strip()
    if cat == "family" or section == "personal":
        return "family"
    if cat == "mentee" or placed or (cat == "mentee-prospect" and re.match(r"^\W*(accepted|onboarding)\b", status, re.I)):
        return "mentees"
    if cat == "mentee-prospect":
        return "candidates"
    if cat == "mentor":
        return "mentors"
    if cat in ("partner", "advisor", "team"):
        return "partners"
    if org and org in mentor_orgs:
        return "mentors"
    return {"candidates": "candidates", "team": "partners", "partners": "partners", "mentors": "mentors",
            "operational": "mentors"}.get(section or "", "else")


def people_week_api():
    today = ledger.today()
    now = dt.datetime.now().astimezone()
    d0 = dt.date.fromisoformat(today)
    span = PEOPLE_WEEK_WEEKS * 7
    weeks = [{"from": (d0 - dt.timedelta(days=7 * (PEOPLE_WEEK_WEEKS - i) - 1)).isoformat(),
              "to": (d0 - dt.timedelta(days=7 * (PEOPLE_WEEK_WEEKS - 1 - i))).isoformat()} for i in range(PEOPLE_WEEK_WEEKS)]

    def week_of(day):
        try:
            age = (d0 - dt.date.fromisoformat(str(day)[:10])).days
        except ValueError:
            return None
        return None if age < 0 or age >= span else PEOPLE_WEEK_WEEKS - 1 - age // 7

    days = {}                                                    # slug -> set of call days in the window
    for r in transcript_index()["rows"]:
        if week_of(r["date"]) is None:
            continue
        for s in r.get("slugs") or []:
            days.setdefault(s, set()).add(r["date"])
    events = []
    for e in calendar_events():
        who = e.get("people") or []
        if not any(w.get("slug") for w in who):
            continue                                             # a personal block with nobody carded on it does not show
        day = str(e.get("date") or "")[:10] or str(e.get("start") or "")[:10]
        st = _iso_ts(e.get("start"))
        if st is not None and st < now.timestamp() and week_of(day) is not None:
            for w in who:
                if w.get("slug"):
                    days.setdefault(w["slug"], set()).add(day)
        ps = [dict(p, state=prep_state(p.get("path"))) for p in e.get("preps") or []]
        events.append({"date": day, "start": e.get("start"), "end": e.get("end"), "title": e.get("title") or "(untitled)",
                       "people": [w for w in who if not w.get("self")], "preps": ps,
                       "join": e.get("join"), "calendarLink": e.get("calendarLink")})
    events.sort(key=lambda e: (str(e["start"] or ""), e["title"]))
    history = {}
    for s, ds in days.items():
        wk = [0] * PEOPLE_WEEK_WEEKS
        for d in ds:
            i = week_of(d)
            if i is not None:
                wk[i] = 1
        history[s] = {"weeks": wk, "calls": len(ds), "last": max(ds)}
    weekly = sorted((s for s, h in history.items() if sum(h["weeks"]) >= PEOPLE_WEEK_MIN and card_path(s)[1]),
                    key=lambda s: (-sum(history[s]["weeks"]), -history[s]["calls"], s))
    section = people_directory()
    root = os.path.join(BRAIN, PEOPLE_REL)
    slugs = [fn[:-3] for fn in sorted(os.listdir(root)) if fn.endswith(".md") and fn != "readme.md"] if os.path.isdir(root) else []
    fms = {s: card_frontmatter(s) for s in slugs}
    mentor_orgs = {str(fm.get("org") or "").strip() for fm in fms.values()
                   if str(fm.get("category") or "").strip().lower() == "mentor" and str(fm.get("org") or "").strip()}
    relation = {s: card_relation(s, fms[s], section.get(s), mentor_orgs) for s in slugs}
    return {"_servedAt": now.isoformat(timespec="seconds"), "today": today, "weeks": weeks, "events": events,
            "history": history, "weekly": weekly, "relation": relation,
            "relations": [{"id": a, "name": b, "why": c} for a, b, c in PEOPLE_RELATIONS],
            "rule": "on a call in %d or more of the last %d weeks, from the transcripts and the calendar's calls already over"
                    % (PEOPLE_WEEK_MIN, PEOPLE_WEEK_WEEKS)}


def person_api(slug):
    rel, ap = card_path(slug)
    if not rel:
        return None, "not a person slug"
    if not ap:
        return None, "no card at %s" % rel
    with open(ap, "r", encoding="utf-8-sig") as f:
        text = f.read()
    fm, body = split_fm(text)
    row = parse_card(rel, ap)
    ps = preps(row["slug"])
    today = ledger.today()
    upcoming = sorted([p for p in ps if p["call"] >= today], key=lambda p: p["call"])
    header, front, back = card_two_sides(body)          # card format v2: the front the page draws, the history it folds
    row.update(text=text, frontmatter=fm, foldList=card_folds(body)[:6], owed=owed_from(body),
               flagList=bullets(h2_section(body, "Flags"))[:12], preps=ps,
               front=front, back=back,
               contact=contact_history(row["slug"], [row.get("lastFold")], today),
               nextCall=(upcoming[0] if upcoming else None),
               sections=card_sections(body), openItems=[r for r in open_for_zak() if row["slug"] in r["people"]],
               heldItems=[r for r in held_for_zak() if row["slug"] in r["people"]])      # on hold, behind their own fold (T-0108)
    return row, None


# ---- routing: an item carries the people it concerns (2026-09-09, ideas E16) ----
# The owner's requirement, 9/09: questions must reach the specific areas they belong to.
# The ledger field `people:<slug>,<slug>` (skills/brain-tasks/tasks.py) is the routing, and it is DECLARED, not guessed:
# rules 1. The name matching below is only a fallback so an item nobody has tagged still reaches the person it names --
# conservative in the same way the group matcher is (Correction #73): a full name anywhere, or a first name that belongs
# to exactly one card and is not followed by a surname. An ambiguous first name ("Mike", "John") matches nothing; tagging
# it with `tasks.py people` is how that gets settled, and a declared field always wins outright.
PEOPLE_LINK_RE = re.compile(r"people/([a-z0-9][a-z0-9-]*)\.md")
COMMON_FIRST = {"grace", "faith", "hope", "may", "june", "will", "mark", "art", "amy"}   # words that are also first names
_name_index = {"t": 0, "rows": []}
_open_cache = {"sig": None, "rows": []}


def name_index():
    """[(slug, full-name regex or None, first-name regex or None)] from the cards themselves. Rebuilt at most once a minute."""
    if time.time() - _name_index["t"] < 60 and _name_index["rows"]:
        return _name_index["rows"]
    root = os.path.join(BRAIN, PEOPLE_REL)
    names = {}
    for fn in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if not fn.endswith(".md") or fn == "readme.md":
            continue
        slug = fn[:-3]
        titles = {slug.replace("-", " ")}
        try:
            with open(os.path.join(root, fn), "r", encoding="utf-8-sig") as f:
                fm, body = split_fm(f.read(2000))
            if fm.get("name"):
                titles.add(str(fm["name"]))
            titles |= {l[2:].strip() for l in body[:40] if l.startswith("# ")}
        except Exception:
            pass
        names[slug] = sorted({re.sub(r"\s*\([^)]*\)\s*$", "", re.sub(r"\s+", " ", t)).strip() for t in titles if str(t).strip()}, key=len, reverse=True)
    firsts = {}
    for slug, ns in names.items():
        for n in ns:
            w = n.split()[0].lower()
            if len(w) > 2:
                firsts.setdefault(w, set()).add(slug)
    rows = []
    for slug, ns in names.items():
        full = [re.escape(n).replace(r"\ ", r"\s+") for n in ns if " " in n]
        first = next((w for w in (n.split()[0].lower() for n in ns)
                      if len(w) > 2 and w not in COMMON_FIRST and len(firsts.get(w, ())) == 1), None)
        rows.append((slug,
                     re.compile(r"\b(?:%s)\b" % "|".join(full), re.I) if full else None,
                     re.compile(r"\b%s\b(?!\s+[A-Z][a-z])" % re.escape(first)) if first else None))
    _name_index.update(t=time.time(), rows=rows)
    return rows


def item_people(it):
    """(slugs, how) for one ledger item. `declared` = the item's own people: field; `named` = a people/ card it links or a
    name its text spells out. Nothing is written back here -- the fallback is a read-time convenience, not a tag."""
    if it.get("people"):
        return list(it["people"]), "declared"
    hits, text = [], it.get("text") or ""
    for l in it.get("links") or []:
        m = PEOPLE_LINK_RE.search(str(l))
        if m and m.group(1) not in hits:
            hits.append(m.group(1))
    for slug, full, first in name_index():
        if slug in hits:
            continue
        if (full and full.search(text)) or (first and first.search(text)):
            hits.append(slug)
    return hits, ("named" if hits else "")


def open_for_zak(include_held=False):
    """Every open item waiting on the owner across the registered ledgers -- an open question, or an open / blocked @<owner> task --
    each carrying the project it lives in and the people it concerns. Cached against the ledger files' own mtimes, so it
    costs one stat per ledger between writes. Derived at read time and stored nowhere (rules 2).

    A task ON HOLD (`until:` a day that has not arrived) is still open and still owed, and it is left OUT of what this
    returns (2026-09-10, T-0108): it is the one function every count and every list of the owner's reads, so holding it back
    here is what takes a held task off the home block, the nav counts, the people pages, the groups and the map at once.
    `held_for_zak()` is the same rows the other way round, for the folded "on hold" line that says how many there are."""
    hs = [h for h in registry().get("holons", []) if h.get("tasks")]
    sig = []
    for h in hs:
        ap = os.path.join(BRAIN, h["tasks"].replace("/", os.sep))
        try:
            st = os.stat(ap); sig.append((h["id"], st.st_mtime, st.st_size))
        except OSError:
            sig.append((h["id"], None, None))
    sig = tuple(sig) + (_name_index["t"] // 60, ledger.today())      # the day is part of it: a hold ends by the clock
    if _open_cache["sig"] == sig:
        rows = _open_cache["rows"]
        return rows if include_held else [r for r in rows if not r["held"]]
    rows = []
    for h in hs:
        ap = os.path.join(BRAIN, h["tasks"].replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:
            continue
        for it in p["items"]:
            waiting = (it["kind"] == "question" and it["mark"] == "?") or (it["kind"] == "task" and it["owner"] == OWNER and it["mark"] in " -")
            if not waiting:
                continue
            who, how = item_people(it)
            r = dict(it); r.pop("line", None)
            r["held"] = ledger.is_held(it)
            r.update(project=h["id"], projectName=h.get("name") or h["id"], projectPath=h["tasks"], people=who, peopleSource=how)
            rows.append(r)
    rows.sort(key=lambda r: (r["kind"] != "question", r["created"]))
    _open_cache.update(sig=sig, rows=rows)
    return rows if include_held else [r for r in rows if not r["held"]]


def held_for_zak():
    """The tasks of the owner's that are on hold: open, owed, and not asked for until the day written on them (T-0108)."""
    return [r for r in open_for_zak(True) if r["held"]]


def doc_asks(rel):
    """Every OPEN ledger item whose link points at this document -- the section asks (2026-09-09, T-0046).
    The owner's design: the agent links those documents and asks, through the projects viewer, for the portions of them
    that need attention. Matched on the PATH half only; the `#slug` half travels back untouched and is matched in the page,
    which is where the headings are cut into sections. Derived at read time from the same ledgers /projects renders."""
    rel = norm(rel) or ""
    out = []
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        ap = os.path.join(BRAIN, h["tasks"].replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:
            continue
        for it in p["items"]:
            if it["mark"] not in (" ", "?", "-"):        # an open task, an open question, a blocked task
                continue
            for raw in it["links"] or []:
                t = raw.strip()
                m = re.match(r"^\[\[(.+?)\]\]$", t)
                if m:
                    t = m.group(1).split("|")[0].strip()
                path, _, frag = t.partition("#")
                path = path.strip()
                if "/" not in path:                       # a bare leaf name, the way a [[wikilink]] usually reads
                    cands = resolve_map().get(path) or resolve_map().get(path + ".md") or []
                    path = cands[0] if len(cands) == 1 else path
                if norm(path) != rel:
                    continue
                r = dict(it); r.pop("line", None)
                r.update(project=h["id"], projectName=h.get("name") or h["id"], fragment=frag.strip(), link=t)
                out.append(r)
                break
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "path": rel, "items": out}


def badges_api():
    """The notification counts every panel reads: how many open items are waiting on the owner, per person and per project.
    This is what the nav counts show today and what the bubbles home (ideas E16) will read tomorrow."""
    rows = open_for_zak()
    projects = {}
    for h in registry().get("holons", []):
        if h.get("tasks"):
            projects[h["id"]] = {"name": h.get("name") or h["id"], "questions": 0, "zak_tasks": 0, "path": h["tasks"]}
    people = {}
    for r in rows:
        b = projects.setdefault(r["project"], {"name": r["projectName"], "questions": 0, "zak_tasks": 0, "path": r["projectPath"]})
        b["questions" if r["kind"] == "question" else "zak_tasks"] += 1
        for s in r["people"]:
            people[s] = people.get(s, 0) + 1
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"),
            "people": people, "projects": projects,
            "total_questions": sum(b["questions"] for b in projects.values()),
            "total_zak_tasks": sum(b["zak_tasks"] for b in projects.values()),
            "waiting": len(rows), "people_items": sum(1 for r in rows if r["people"]),
            "defaultProject": "pf-build" if "pf-build" in projects else (next(iter(projects), None))}


def waiting_api():
    """The same rows badges_api counts, grouped by project and sent whole: what the home page pins at the top.
    The filtering rule (2026-09-09): every page opens showing only what is live right now. Derived at read time
    from open_for_zak(), stored nowhere; a project with nothing open is present with an empty list so the home can say so."""
    rows = open_for_zak()
    order, groups = [], {}
    for h in registry().get("holons", []):
        if h.get("tasks"):
            order.append(h["id"])
            groups[h["id"]] = {"project": h["id"], "name": h.get("name") or h["id"], "path": h["tasks"],
                               "holonPath": h.get("path"), "questions": [], "tasks": [], "held": []}
    for r in rows + held_for_zak():
        g = groups.get(r["project"])
        if g is None:
            g = groups[r["project"]] = {"project": r["project"], "name": r["projectName"], "path": r["projectPath"],
                                        "holonPath": None, "questions": [], "tasks": [], "held": []}
            order.append(r["project"])
        g["held" if r.get("held") else "questions" if r["kind"] == "question" else "tasks"].append(r)
    out = [groups[i] for i in order]
    out.sort(key=lambda g: -(len(g["questions"]) * 2 + len(g["tasks"])))
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": ledger.today(),
            "total": len(rows), "questions": sum(1 for r in rows if r["kind"] == "question"),
            "tasks": sum(1 for r in rows if r["kind"] != "question"), "held": len(held_for_zak()), "groups": out}


# ---- the quest log and the timeline (2026-09-09, the straight line step 2c, ledger T-0058 + T-0059) ----
# The owner asked for a list of things to test and look through, kept in a panel at the top right of the screen like a
# game, and for recently completed things to be clickable like a vertical timeline task bar that expands at the bottom
# to show older completed tasks, so the progress of the whole app is visible. Both halves are the SAME ledgers /projects renders, read at request time and stored nowhere:
# the To-test tab is the open @<owner> tasks tagged #test, the Done tab is every closed item newest first, each carrying the
# `→ link` that says what it produced (set by `tasks.py done --link` / `tasks.py link`).
QUEST_TAG = "test"
QUEST_DONE_MAX = 200          # the newest N closed items; the panel pages through them ten at a time


def quests_api():
    tests, done, held = [], [], []
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        ap = os.path.join(BRAIN, h["tasks"].replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:
            continue
        for it in p["items"]:
            row = dict(it); row.pop("line", None)
            row.update(project=h["id"], projectName=h.get("name") or h["id"], projectPath=h["tasks"])
            if it["kind"] == "task" and it["mark"] == " " and it["owner"] == OWNER and QUEST_TAG in (it["tags"] or []):
                (held if ledger.is_held(it) else tests).append(row)      # on hold: out of the list until its day (T-0108)
            elif it["mark"] == "x":
                done.append(row)
    tests.sort(key=lambda r: (r["created"], r["id"]))
    held.sort(key=lambda r: (r.get("until") or "", r["id"]))
    done.sort(key=lambda r: (r.get("done") or "", r["id"]), reverse=True)
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": ledger.today(), "tag": QUEST_TAG,
            "tests": tests, "held": held, "done": done[:QUEST_DONE_MAX], "doneTotal": len(done)}


# ---- the rating surface (2026-09-17, ledger T-0166; the owner's yes on Q-0018) ----
# On 9/16 the owner asked for a way to look through many examples of proposals (connections that could be made, for
# instance) and rate their quality without typing a response. So: proposals arrive
# as CARDS and each one is rated with one press -- good, off, wrong -- with an optional line if the owner wants to say why.
# A rating is written back onto the item it is about, through the same tasks.py every other write in this file uses,
# and it is ALSO appended to brain-viewer-holon/ratings/<day>.jsonl so the pile becomes test data for the agent builder
# (T-0149) and the eleven-rules audit. Design: brain-viewer-holon/design-directions/rating-surface-2026-09-16.md.
#
# TWO card kinds in this first build, and the page says which is which:
#   closure -- an open `#test` item the viewer proposes closing, with the evidence beside it. THE EVIDENCE READ HERE IS
#              DELIBERATELY NARROW and is named on the page: a task on the SAME ledger, closed on or after the day the
#              test was written, pointing at the SAME route or file the test points at. That reads "what this test
#              covers was built again since it was written, and the test has sat unticked" -- it is NOT a claim that
#              anyone performed the test. The full pass (the log, the session transcripts) is T-0115 and is still open;
#              a test item with no such evidence is not a card at all. A test younger than REVIEW_STALE_DAYS is a live
#              test, not a stale one, and is left alone.
#   review  -- any OPEN item on any ledger carrying `#review`. `tasks.py add --tag review` makes one. The proposal is
#              the item's own words, and a rating writes a line onto it and nothing else: there is nothing to close.
#
# THE AUTO-CLOSE RULE IS COUNTED, NOT ENFORCED. The owner's answer to Q-0018 set the bar at eighteen of the last twenty
# ratings good, after which closures of that shape would apply on their own. This build COUNTS toward that bar, shows
# the counter on the page and writes it into the log line; nothing here closes anything without the owner's press. Turning it
# on is a later item, and the page says so in one line.
REVIEW_REL = "brain-viewer-holon/ratings"      # one <day>.jsonl, append-only, git-tracked, never edited by hand
REVIEW_TAG = "review"                          # #review on any open ledger item makes it a card
REVIEW_VERDICTS = ("good", "off", "wrong")
REVIEW_UNDONE = "undone"                        # the ratings-file verdict an undo press writes (T-0200); never a press of its own
REVIEW_UNDO_SECONDS = 90                        # the page offers undo for 60 s; the server allows a little slack for a slow press
REVIEW_SITTING = 20                            # a sitting is at most this many cards; the rest wait
REVIEW_BAR, REVIEW_WINDOW = 18, 20             # the auto-close bar the owner set: 18 of the last 20 good
REVIEW_STALE_DAYS = 7                          # a test item younger than this is still a live test, not a closure card
REVIEW_ENFORCED = False                        # ...and the bar does nothing yet. Shown and logged; never acted on
REVIEW_SOURCE = "viewer evidence read"         # who proposed it, where the item carries no #source: tag of its own
# WHAT EACH PRESS DOES, SAID ON THE CARD (2026-09-18, viewer Q-0018). The owner asked for one plain line under the three
# buttons, because "off" and "wrong" looked the same from the outside and neither said what it left behind.
REVIEW_PRESSES = {
    "closure": "good closes it, off keeps it open and files the rewrite, wrong keeps it as written and does not offer it again; note only writes your line and answers nothing.",
    "review": "good and wrong write your line and leave the item exactly as it is; off writes the line too, and nothing here closes anything; note only writes your line and answers nothing.",
}
# OFF FILES A REWRITE (2026-09-18, viewer Q-0018). A closure rated off means the test is not closable as written, which
# is a piece of work and not just a verdict: one @claude task on the SAME ledger, filed as a finding so it is
# idempotent -- a second `off` on the same card bumps the open item rather than filing another one.
REVIEW_RETEST_KEY = "retest:%s"
REVIEW_RETEST_TEXT = ("Rewrite test %s's steps against the current build (viewer %s) and the route as it stands; "
                      "the 9/09 wording is stale")
# A NOTE ON AN ITEM IS TWO DIFFERENT THINGS (2026-09-18: the owner found the cards still read as if they referenced old things).
# One `note:` field grows by appending, so it ends up holding both what somebody wrote on the item AND the markers the
# machinery leaves behind when it rewrites, rates, retires or moves that item -- including, on every 9/09 test, the
# whole 9/09 wording kept as "rewritten <day> ...; the 9/09 steps read: ...". Those markers are history: they go behind
# a press, and the face of a card shows only what the item says now.
NOTE_MARKERS = ("rewritten ", "rated ", "retired ", "moved to")
# the two shapes a PLAIN appended line takes -- what /api/reply writes ("note <day>: ...") and what the note-only press
# writes ("note (viewer, <day>): ..."). They are boundaries too, or a line written after a marker would be swallowed by
# it and vanish off the face; they are not markers, so they stay on the face.
_NOTE_PLAIN = (r"note \(viewer, ", r"note \d{4}-\d{2}-\d{2}")
_NOTE_SPLIT = re.compile(r";\s+(?=(?:%s))" % "|".join([re.escape(m) for m in NOTE_MARKERS] + list(_NOTE_PLAIN)), re.I)
# A REWRITE OF A TEST IS NOT A REBUILD OF WHAT THE TEST CHECKS (2026-09-18; ledger T-0189). Work filed BY this page
# (source `review`, key `retest:<id>`), work whose whole text is "Rewrite test ...", and the 2026-09-18 batch rewrite
# of the 9/09 steps all touch the TEST. None of it is evidence that the thing under test was built again.
REVIEW_RETEST_TEXT_PREFIX = "rewrite test"


def note_parts(note):
    """One ledger note -> (what it says now, [the history markers on it], in the order they were appended).

    The split is deliberately conservative: a note is cut only where a `; ` is followed by one of NOTE_MARKERS, so a
    semicolon inside somebody's sentence keeps that sentence whole."""
    s = " ".join(str(note or "").split())
    if not s:
        return "", []
    parts = [p.strip() for p in _NOTE_SPLIT.split(s) if p.strip()]
    face = [p for p in parts if not p.lower().startswith(NOTE_MARKERS)]
    hist = [p for p in parts if p.lower().startswith(NOTE_MARKERS)]
    return "; ".join(face), hist


def short_day(d):
    """2026-09-12 -> 9/12. The day said the way the page says it, for a sentence the server composes."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", str(d or "").strip())
    return "%d/%s" % (int(m.group(2)), m.group(3)) if m else str(d or "")


def review_is_maintenance(it):
    """True when a closed task is test maintenance rather than built work, and so can never stand as evidence."""
    src = str(it.get("source") or _tag_value(it, FINDING_SOURCE_TAG) or "").strip().lower()
    if src == REVIEW_TAG:
        return True
    if str(it.get("text") or "").strip().lower().startswith(REVIEW_RETEST_TEXT_PREFIX):
        return True
    if str(it.get("key") or _tag_value(it, FINDING_KEY_TAG) or "").strip().lower().startswith("retest:"):
        return True
    face, hist = note_parts(it.get("note"))
    return bool(hist) and not face and all(h.lower().startswith("rewritten ") for h in hist)


def review_dir():
    return os.path.join(BRAIN, REVIEW_REL.replace("/", os.sep))


def review_ratings():
    """Every rating written so far, oldest first. One .jsonl per day; a line that will not parse is skipped rather than
    guessed at, and a missing folder is simply no ratings yet."""
    out, d = [], review_dir()
    if not os.path.isdir(d):
        return out
    for leaf in sorted(os.listdir(d)):
        if not leaf.endswith(".jsonl"):
            continue
        try:
            with open(os.path.join(d, leaf), "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            continue
    return out


def review_counter(rows=None):
    """Per card kind, how the last REVIEW_WINDOW ratings went against the owner's bar. Reported on the page and written into
    the log line; `met` is a statement about the count, never a permission -- REVIEW_ENFORCED is what would act on it."""
    rows = review_ratings() if rows is None else rows
    per = {}
    for r in rows:
        k = str(r.get("kind") or "?")
        if r.get("verdict") == REVIEW_UNDONE:
            # an undo takes back the rating it reverses (the newest one for that card), so it never counts toward the bar
            cid = (r.get("project"), r.get("item"))
            lst = per.get(k, [])
            for i in range(len(lst) - 1, -1, -1):
                if (lst[i].get("project"), lst[i].get("item")) == cid:
                    del lst[i]
                    break
            continue
        per.setdefault(k, []).append(r)
    out = {}
    for kind, rs in per.items():
        win = rs[-REVIEW_WINDOW:]
        good = sum(1 for r in win if r.get("verdict") == "good")
        out[kind] = {"rated": len(rs), "window": len(win), "good": good, "bar": REVIEW_BAR, "of": REVIEW_WINDOW,
                     "met": len(win) >= REVIEW_WINDOW and good >= REVIEW_BAR, "enforced": REVIEW_ENFORCED}
    return out


def review_latest():
    """The LAST rating written for each card, by `<project>:<item>`. The ratings folder is append-only and stays that way
    (2026-09-18, viewer Q-0018): changing an answer writes a SECOND line rather than rewriting the first, so the history
    of a card reads in order in the file and the newest line is simply the one that wins here."""
    out = {}
    for r in review_ratings():
        cid = "%s:%s" % (r.get("project"), r.get("item"))
        out[cid] = r
    # an UNDO line (2026-09-24, T-0200) puts the card back where it was before the press: the card is unrated again,
    # so it leaves the fold and review_cards() may offer it as a card again. The undo line stays in the file.
    return {k: v for k, v in out.items() if v.get("verdict") != REVIEW_UNDONE}


def review_fold(latest=None):
    """The `Rated` fold at the bottom of /review: every card that has been rated, newest first, with the verdict, the day
    and where the item stands on its ledger NOW -- which is what makes changing an answer honest rather than cosmetic.

    Since 2026-09-18 a rated card no longer disappears. A wrong-rated card is still never offered again as a NEW card
    (review_cards() skips anything in the ratings folder); it sits here, and here is where the answer changes."""
    latest = review_latest() if latest is None else latest
    by_file = {}
    for r in latest.values():
        by_file.setdefault(r.get("file") or "", []).append(r)
    rows = []
    for rel, rs in by_file.items():
        items = {}
        ap = os.path.join(BRAIN, str(rel).replace("/", os.sep))
        if os.path.isfile(ap):
            try:
                items = {i["id"]: i for i in ledger.parse(ledger.read(ap))["items"]}
            except Exception:                    # noqa: BLE001 -- a ledger that will not parse simply has no live state
                items = {}
        for r in rs:
            it = items.get(r.get("item"))
            # the item's own note is split the same way a card's is: what it says now on the row, the rewrite and
            # rating markers behind a history press (2026-09-18)
            face, hist = note_parts((it or {}).get("note"))
            rows.append({"itemNote": face, "history": hist,
                         "cardId": "%s:%s" % (r.get("project"), r.get("item")), "project": r.get("project"),
                         "file": rel, "id": r.get("item"), "kind": r.get("kind"), "verdict": r.get("verdict"),
                         "day": r.get("day"), "at": r.get("at"), "note": r.get("note") or "",
                         "changedFrom": r.get("changedFrom"), "line": r.get("line"),
                         "text": (it or {}).get("text") or r.get("text") or "",
                         "proposal": r.get("proposal"),
                         "state": (it or {}).get("state"), "gone": it is None,
                         "links": (it or {}).get("links") or []})
    rows.sort(key=lambda r: (r.get("at") or "", r["cardId"]), reverse=True)
    return rows


def review_broad_links():
    """Links too broad to say two items are about the same thing (2026-09-24, T-0189): every holon's own spec, rules,
    status, readme and ledger file as the registry declares them, and any `*-spec.md` or `readme.md`. Nearly every
    viewer task links brain-viewer-spec.md, so a shared link to it matched the glossary test to 'connect bubbles on
    /map'. The bare home route `/` is broad for the same reason. Any other route and any other file stay narrow enough."""
    out = set()
    for h in registry().get("holons", []):
        for k in ("spec", "rules", "status", "tasks", "readme"):
            if h.get(k):
                out.add(str(h[k]).strip())
        if h.get("path"):
            out.add(str(h["path"]).rstrip("/") + "/readme.md")
    return out


def review_link_is_broad(link, broad):
    l = str(link or "").strip()
    leaf = l.rsplit("/", 1)[-1].lower()
    # the bare home route is linked by nearly every home-page task, so it is as broad as the spec
    return l in broad or l == "/" or leaf == "readme.md" or leaf.endswith("-spec.md")


def review_evidence(it, done, broad=None):
    """What the viewer can honestly point at for closing ONE test item: tasks on the same ledger, closed STRICTLY AFTER
    the day the test was written, pointing at the same route or file -- where the shared link is narrower than a
    project's own spec, readme or ledger (review_broad_links). Newest first, at most two. Empty means it is not a card.

    Tightened 2026-09-24 (T-0189, night-agent 86): 7 of the 20 cards served on 9/17 cited a task closed the SAME DAY the
    test was written, which is the work the test was written for rather than a rebuild after it, and the topical match
    was a shared link to brain-viewer-spec.md.

    `done` arrives already stripped of tests and of test maintenance (review_cards), so nothing here can cite the work
    that rewrote the test as the reason to close it; the item's own id is excluded below for the same reason."""
    broad = review_broad_links() if broad is None else broad
    mine = {l for l in (it.get("links") or []) if not review_link_is_broad(l, broad)}
    if not mine:
        return []
    hits = [d for d in done if d["id"] != it["id"] and (d.get("done") or "") > (it.get("created") or "")
            and (set(d.get("links") or []) & mine)]
    hits.sort(key=lambda d: (d.get("done") or "", d["id"]), reverse=True)
    return [{"id": d["id"], "done": d.get("done"), "text": d["text"][:180],
             "link": sorted(set(d.get("links") or []) & mine)[0],
             "links": sorted(set(d.get("links") or []) & mine)} for d in hits[:2]]


def review_cards(rated=None):
    """(the sitting, how many are waiting altogether, how many tests have no rebuild behind them). A card is rated ONCE:
    anything already in the ratings folder never comes back, whichever way it was rated.

    An open, stale test with no surviving evidence is NOT a card (2026-09-18): it is simply a test nobody has run, and
    it is counted into the third number so the page can say so and send him to Today rather than put a closure in front
    of him that nothing supports."""
    if rated is None:
        rated = set(review_latest())
    try:
        refd = dt.date.fromisoformat(ledger.today())
    except ValueError:
        refd = dt.date.today()
    cards, untested = [], 0
    broad = review_broad_links()
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        rel = h["tasks"]; ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:
            continue
        # a closed TEST is not evidence that another test passed -- only built work counts, so the test tag is out of
        # the pool, and so is every task that only rewrote a test (review_is_maintenance)
        done = [d for d in p["items"] if d["mark"] == "x" and d.get("done") and QUEST_TAG not in (d.get("tags") or [])
                and not review_is_maintenance(d)]
        for it in p["items"]:
            if it["mark"] not in FINDING_OPEN_MARKS:
                continue
            cid = "%s:%s" % (h["id"], it["id"])
            if cid in rated:
                continue
            tags = it.get("tags") or []
            age = days_since(it.get("created"), refd)
            row = None
            if REVIEW_TAG in tags:
                row = {"kind": "review", "proposal": it["text"],
                       "changes": "your rating is written onto %s; the item itself stays exactly as it is" % it["id"],
                       "evidence": []}
            elif (it["kind"] == "task" and it["mark"] == " " and QUEST_TAG in tags
                  and (age or 0) >= REVIEW_STALE_DAYS and not ledger.is_held(it)):
                ev = review_evidence(it, done, broad)
                if not ev:
                    untested += 1
                    continue
                row = {"kind": "closure",
                       "proposal": "Close this test: what it tests was rebuilt on %s, see %s, and it has sat unticked for %s."
                                   % (short_day(ev[0]["done"]), ev[0]["link"],
                                      ("%d days" % age) if age is not None else "a while"),
                       "changes": "%s is checked off on %s, with the rating written on its own line" % (it["id"], rel),
                       "evidence": ev}
            if not row:
                continue
            face, hist = note_parts(it.get("note"))
            row.update({"cardId": cid, "project": h["id"], "projectName": h.get("name") or h["id"], "file": rel,
                        "id": it["id"], "itemKind": it["kind"], "text": it["text"], "note": face, "history": hist,
                        "owner": it.get("owner"), "to": it.get("to"), "links": it.get("links") or [],
                        "tags": [t for t in tags if not t.startswith((FINDING_SOURCE_TAG, FINDING_KEY_TAG))],
                        "source": it.get("source") or _tag_value(it, FINDING_SOURCE_TAG) or REVIEW_SOURCE,
                        "date": it.get("created"), "age_days": age})
            cards.append(row)
    # a #review card was tagged on purpose, so it goes first; then the oldest proposal, which is the one rotting
    cards.sort(key=lambda c: (0 if c["kind"] == "review" else 1, -(c["age_days"] or 0), c["project"], c["id"]))
    return cards[:REVIEW_SITTING], len(cards), untested


def review_api():
    rows = review_ratings()
    latest = review_latest()
    cards, waiting, untested = review_cards(set(latest))
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": ledger.today(),
            "cards": cards, "shown": len(cards), "waiting": waiting, "sitting": REVIEW_SITTING,
            "untested": untested,
            "rated": review_fold(latest),
            "presses": REVIEW_PRESSES,
            "counter": review_counter(rows), "ratedTotal": len(rows), "ratingsFolder": REVIEW_REL,
            "autoClose": {"bar": REVIEW_BAR, "of": REVIEW_WINDOW, "enforced": REVIEW_ENFORCED,
                          "says": "Once %d of the last %d ratings of a kind are good, closures of that shape would apply on their own. "
                                  "This build counts toward that and does not act on it: every closure still waits for your press."
                                  % (REVIEW_BAR, REVIEW_WINDOW)},
            "rule": {"tag": REVIEW_TAG, "testTag": QUEST_TAG, "staleDays": REVIEW_STALE_DAYS,
                     "evidence": "a task on the same ledger, closed strictly after the day the test was written, pointing at the same route or file (a project's own spec, readme or ledger is too broad to count), and not itself test maintenance (nothing filed by this page, nothing whose job was to rewrite a test, never the item itself)",
                     "untested": "an open test with no such work behind it is not a card at all; it is counted and run from Today",
                     "notYet": "the full evidence pass over the log and the session transcripts is T-0115, still open"},
            "ledgers": [h["id"] for h in registry().get("holons", []) if h.get("tasks")]}


def review_retest(path, rel, it):
    """A closure rated OFF files the rewrite it implies: one @claude task on the same ledger saying the test's steps no
    longer describe the build (2026-09-18, viewer Q-0018). Filed as a FINDING -- source `review`, key `retest:<id>` --
    so a second off on the same card bumps the open item instead of filing a duplicate, which is the findings rule the
    rest of the brain already follows. -> (what happened, the item id)."""
    key = REVIEW_RETEST_KEY % it["id"]
    try:
        hits = ledger.open_by_key(key, file=rel)
        if hits:
            iid = hits[0][3]["id"]
            ledger.apply(path, rel, "repeat", agent="brain-viewer", id=iid, source="review",
                         text="rated off again in the viewer")
            return "repeated", iid
        iid = ledger.apply(path, rel, "add", agent="brain-viewer", owner="@claude",
                           text=REVIEW_RETEST_TEXT % (it["id"], VERSION),
                           source="review", key=key, links=list(it.get("links") or []))
        return "filed", iid
    except ledger.LedgerError as e:                # noqa: BLE001 -- the rating itself landed; say so, never undo it
        return "refused: %s" % e, None


def review_rate(card, verdict, note=None, previous=None):
    """ONE rating, written where it belongs. The line is composed HERE so the date is this machine's clock, and an
    existing keep-in-mind line is kept with the rating added after it rather than overwritten (the same rule /api/reply
    follows). A closure rated good is then checked off through tasks.py; nothing else closes anything.

    CHANGING AN ANSWER (2026-09-18, viewer Q-0018). `previous` is the verdict this card already carried. The note says
    so in its own words (rated off (viewer, <day>), changed from good: ...), the ratings file gets a SECOND line rather
    than a rewritten first one, and the item state follows the move: off good REOPENS a closure that was checked off,
    onto good CLOSES one that is open. A review card never had its state touched by a rating, so a change does not
    touch it either -- the line is the whole record there."""
    if verdict not in REVIEW_VERDICTS:
        raise ledger.LedgerError("a rating is one of: %s" % ", ".join(REVIEW_VERDICTS))
    path, rel = ledger.resolve(card["project"])
    it = ledger.find(ledger.parse(ledger.read(path)), card["id"])
    d = ledger.today()
    typed = " ".join(str(note or "").split())
    ev = card.get("evidence") or []
    said = typed or (("evidence %s, closed %s" % (ev[0]["id"], ev[0]["done"])) if ev else "no note")
    line = "rated %s (viewer, %s)%s: %s" % (verdict, d, (", changed from %s" % previous) if previous else "", said)
    was = (it.get("note") or "").strip()
    ledger.apply(path, rel, "note", agent="brain-viewer", id=card["id"], note=(("%s; " % was) if was else "") + line)
    # the state move. On a first rating this is the old rule unchanged (a closure rated good is checked off); on a
    # change it is that same rule read both ways, applied only when the item is not already in that state.
    it = ledger.find(ledger.parse(ledger.read(path)), card["id"])
    closed = reopened = False
    if card["kind"] == "closure":
        if verdict == "good" and it["mark"] != "x":
            ledger.apply(path, rel, "done", agent="brain-viewer", id=card["id"])
            closed = True
        elif verdict != "good" and previous == "good" and it["mark"] == "x":
            ledger.apply(path, rel, "reopen", agent="brain-viewer", id=card["id"])
            reopened = True
    retest = retest_id = None
    if card["kind"] == "closure" and verdict == "off":
        retest, retest_id = review_retest(path, rel, it)
    face, hist = note_parts(it.get("note"))
    rec = {"itemNote": face, "history": hist,
           "at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "day": d, "by": OWNER,
           "kind": card["kind"], "verdict": verdict, "project": card["project"], "file": rel, "item": card["id"],
           "proposal": card.get("proposal"), "text": it["text"], "note": typed, "line": line, "closed": closed,
           "reopened": reopened, "changedFrom": previous, "retest": retest, "retestId": retest_id,
           "evidence": [{"id": e.get("id"), "done": e.get("done"), "link": e.get("link")} for e in ev],
           "source": card.get("source"), "version": VERSION}
    os.makedirs(review_dir(), exist_ok=True)
    with open(os.path.join(review_dir(), d + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    c = review_counter().get(card["kind"], {})
    did = ", ".join(x for x in [("changed from %s" % previous) if previous else "", "closed" if closed else "",
                                "reopened" if reopened else "",
                                ("%s %s" % (retest, retest_id)) if retest_id else retest or ""] if x)
    rec["log"] = log_line("%s -- %s rated %s in the viewer (%s card%s); %s now %d of the last %d good, bar %d of %d, not enforced"
                          % (rel, card["id"], verdict, card["kind"], ("; " + did) if did else "", card["kind"],
                             c.get("good", 0), c.get("window", 0), REVIEW_BAR, REVIEW_WINDOW), action="DECISION")
    rec["counter"] = review_counter()
    return rec


def review_post(card_id, verdict, note=None):
    """The card is looked up on the SERVER, so the kind, the evidence and whether it is still on the board all come from
    the ledgers rather than from whatever a page sent.

    A card that has ALREADY been rated is not on the board any more -- review_cards() skips it -- so it is looked up a
    second way, among the ratings, and rated again as a CHANGE (2026-09-18, viewer Q-0018). The same verdict twice is
    refused: there is nothing to change, and a second identical line would only pad the file."""
    if verdict not in REVIEW_VERDICTS:   # checked before the lookup, so a bad verdict is always a 400 and never a 404
        raise ledger.LedgerError("a rating is one of: %s" % ", ".join(REVIEW_VERDICTS))
    cards, _n, _u = review_cards()
    card = next((c for c in cards if c["cardId"] == card_id), None)
    if card:
        return review_rate(card, verdict, note)
    was = review_latest().get(card_id)
    if not was:
        return None
    if was.get("verdict") == verdict:
        raise ledger.LedgerError("%s is already rated %s; pick a different answer to change it" % (was.get("item"), verdict))
    try:
        path, _rel = ledger.resolve(was.get("project"))
        ledger.find(ledger.parse(ledger.read(path)), was.get("item"))
    except ledger.LedgerError:
        raise ledger.LedgerError("%s is no longer on %s, so its answer cannot be changed" % (was.get("item"), was.get("file")))
    again = {"cardId": card_id, "project": was.get("project"), "id": was.get("item"), "kind": was.get("kind"),
             "proposal": was.get("proposal"), "evidence": was.get("evidence") or [], "source": was.get("source")}
    return review_rate(again, verdict, note, previous=was.get("verdict"))


def review_undo(card_id):
    """UNDO the rating just written on a card (2026-09-24, T-0200; on 9/18 the owner found changing many rated cards
    tedious). Only the newest rating, and only inside REVIEW_UNDO_SECONDS of it being
    written, so an undo can never reach back past a press the owner did not just make.

    A CHANGE is undone by changing back: the same review_rate() write with the old verdict, so the ledger and the file
    read in order. A FIRST rating is undone by one `undone` line in the ratings file (append-only, as ever), one
    `rating undone` line on the item, the item reopened if the rating checked it off, and the rewrite task that an
    `off` filed closed with a line saying why. The card is then unrated and back on the board. -> the row, or None."""
    rows = [r for r in review_ratings() if "%s:%s" % (r.get("project"), r.get("item")) == card_id]
    if not rows or rows[-1].get("verdict") == REVIEW_UNDONE:
        return None
    last = rows[-1]
    try:
        age = (dt.datetime.now().astimezone() - dt.datetime.fromisoformat(str(last.get("at")))).total_seconds()
    except (TypeError, ValueError):
        age = None
    if age is None or age > REVIEW_UNDO_SECONDS:
        raise ledger.LedgerError("%s was rated more than a minute ago; change it from the Rated fold instead" % last.get("item"))
    if last.get("changedFrom"):
        again = {"cardId": card_id, "project": last.get("project"), "id": last.get("item"), "kind": last.get("kind"),
                 "proposal": last.get("proposal"), "evidence": last.get("evidence") or [], "source": last.get("source")}
        rec = review_rate(again, last["changedFrom"], "undo", previous=last.get("verdict"))
        rec["undone"] = last.get("verdict")
        return rec
    path, rel = ledger.resolve(last.get("project"))
    it = ledger.find(ledger.parse(ledger.read(path)), last.get("item"))
    d = ledger.today()
    line = "rating undone (viewer, %s): was %s" % (d, last.get("verdict"))
    was = (it.get("note") or "").strip()
    ledger.apply(path, rel, "note", agent="brain-viewer", id=last["item"], note=(("%s; " % was) if was else "") + line)
    reopened = withdrawn = False
    if last.get("closed"):
        it = ledger.find(ledger.parse(ledger.read(path)), last["item"])
        if it["mark"] == "x":
            ledger.apply(path, rel, "reopen", agent="brain-viewer", id=last["item"])
            reopened = True
    if last.get("retest") == "filed" and last.get("retestId"):
        try:
            rt = ledger.find(ledger.parse(ledger.read(path)), last["retestId"])
            if rt["mark"] != "x":
                ledger.apply(path, rel, "note", agent="brain-viewer", id=rt["id"],
                             note="withdrawn (viewer, %s): the off rating on %s that filed this was undone" % (d, last["item"]))
                ledger.apply(path, rel, "done", agent="brain-viewer", id=rt["id"])
                withdrawn = True
        except ledger.LedgerError:
            pass
    rec = {"at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "day": d, "by": OWNER,
           "kind": last.get("kind"), "verdict": REVIEW_UNDONE, "undid": last.get("verdict"), "project": last.get("project"),
           "file": rel, "item": last.get("item"), "line": line, "reopened": reopened,
           "withdrew": last.get("retestId") if withdrawn else None, "version": VERSION}
    os.makedirs(review_dir(), exist_ok=True)
    with open(os.path.join(review_dir(), d + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    rec["log"] = log_line("%s -- %s: rating %s undone in the viewer%s%s" % (
        rel, last["item"], last.get("verdict"), "; reopened" if reopened else "",
        ("; rewrite task %s withdrawn" % last["retestId"]) if withdrawn else ""), action="DECISION")
    rec["counter"] = review_counter()
    rec["undone"] = last.get("verdict")
    return rec


def review_note(card_id, text):
    """A LINE WITHOUT AN ANSWER (2026-09-18: changing a card forced a new answer even when only a note was wanted).
    It writes `note (viewer, <day>): <text>` onto the item through the same tool a rating uses and stops
    there: no ratings line, no counter, no state move. A card that has not been rated stays on the board with the
    answer still open; one that has keeps the verdict it already carries. -> the row, or None if there is no such card."""
    typed = " ".join(str(text or "").split())
    if not typed:
        raise ledger.LedgerError("a note needs some words")
    cards, _n, _u = review_cards()
    card = next((c for c in cards if c["cardId"] == card_id), None)
    was = None if card else review_latest().get(card_id)
    if card:
        project, item = card["project"], card["id"]
    elif was:
        project, item = was.get("project"), was.get("item")
    elif card_id.count(":") == 1 and all(card_id.split(":")):
        project, item = card_id.split(":", 1)
    else:
        return None
    path, rel = ledger.resolve(project)
    it = ledger.find(ledger.parse(ledger.read(path)), item)
    d = ledger.today()
    line = "note (viewer, %s): %s" % (d, typed)
    prev = (it.get("note") or "").strip()
    whole = (("%s; " % prev) if prev else "") + line
    ledger.apply(path, rel, "note", agent="brain-viewer", id=item, note=whole)
    face, hist = note_parts(whole)
    return {"noteOnly": True, "cardId": card_id, "project": project, "file": rel, "id": item, "day": d,
            "note": typed, "line": line, "itemNote": face, "history": hist, "text": it["text"]}



# ---- the stage line (2026-09-09, ledger T-0064) ----
# The owner asked for a line on screen showing which stage the build is at out of how many, not another list. The build order
# is already declared and nothing here re-declares it: it is the `Straight-line` milestone on the ledgers the registry
# names, read with the same parser every other ledger view uses. A step's place in the order comes from the leading
# "Step N." / "Step 2b." token in the item's own text, so the order is the ledger's, never the file's line order and
# never a list typed into a page; step 6 sits on brain-central because it is not the viewer's work, and it belongs to
# the same line. A task filed under the milestone WITHOUT a step token is follow-up work, not a stage, and is skipped.
STAGE_MILESTONE = "straight-line"
STAGE_STEP_RE = re.compile(r"^\s*Step\s+(\d+)\s*([a-z]?)\s*[.:]\s*(.+)$", re.I | re.S)
STAGE_SHORT_MAX = 48          # past this the short name is cut again at its first comma ("Chat becomes the home page")


def stage_short(rest):
    """The step's short name: the text up to the first colon, period or semicolon after the token, and if that still
    runs long, up to its first comma. One step in nine reads as a sentence rather than a title; this is that step."""
    s = re.split(r"[.:;]", str(rest or "").strip(), maxsplit=1)[0].strip().rstrip("(,-— ")
    if len(s) > STAGE_SHORT_MAX and "," in s:
        s = s.split(",", 1)[0].strip()
    return s


def stages_api():
    steps = []
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        ap = os.path.join(BRAIN, h["tasks"].replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:
            continue
        for group in p["order"]:
            if group.strip().lower() != STAGE_MILESTONE:
                continue
            for it in p["groups"][group]:
                if it["kind"] != "task":
                    continue
                m = STAGE_STEP_RE.match(it["text"])
                if not m:
                    continue
                num, suffix, rest = int(m.group(1)), (m.group(2) or "").lower(), m.group(3)
                steps.append({"project": h["id"], "projectName": h.get("name") or h["id"], "projectPath": h["tasks"],
                              "id": it["id"], "step": "%d%s" % (num, suffix), "num": num, "suffix": suffix,
                              "short": stage_short(rest), "text": it["text"], "milestone": group,
                              # 0.39.0: the day the ledger puts on a step, so the home board can lay the build order
                              # out along a calendar rather than as evenly spaced dots. `due` is the day it is owed,
                              # `done` the day it was finished; a step carrying neither has no place on a dated track
                              # and is simply not drawn there.
                              "due": it.get("due"), "at": it.get("due") or it["done"],
                              "mark": it["mark"], "state": it["state"], "done": it["done"],
                              "blocked": it["blocked"], "links": it["links"], "note": it.get("note")})
    steps.sort(key=lambda s: (s["num"], s["suffix"]))
    current = None
    for s in steps:
        s["stage"] = "done" if s["mark"] == "x" else ("current" if current is None else "open")
        if s["stage"] == "current":
            current = s["id"]
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": ledger.today(),
            "milestone": "Straight-line", "steps": steps, "total": len(steps),
            "doneCount": sum(1 for s in steps if s["stage"] == "done"), "current": current}


# ---- groups + follow-ups (2026-09-09; ledger T-0027, the owner asked for follow-up calls by team, individual and group) ----
# A prep is keyed to a CALL, with one or many participants. The standing threads are DECLARED in skills/call-prep/call-prep-groups.json
# (rules 1: derived, never drawn -- the owner confirms that file, the panel only renders it). Everything else here is read from
# transcripts the brain already holds: the app mirror's JSON carries an explicit participants array, and a raw transcript is read
# for its `Attendees:` header or its speaker lines. Participant strings are TRANSCRIBER OUTPUT (Correction #73), so a name maps to
# a card only on an exact match against a card's own title or slug -- an unmapped name is reported, never invented into a member.
GROUP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
TX_SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){0,2}):\s")
TX_TIMED_RE = re.compile(r"^([A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){0,2})\s+\(\d+:\d\d(?::\d\d)?\)\s*$")
TX_ATTEND_RE = re.compile(r"^\s*(?:Attendees|Present)\s*:\s*(.+)$", re.I)
TX_PARTS_RE = re.compile(r"^\s*participants\s*:\s*(.+)$", re.I)     # the YAML frontmatter some raws carry: participants: [A, B]
TX_EXT = {".txt", ".md"}
# WHO THIS BRAIN READS AS ITSELF, and the transcriber spellings it has already reviewed: both are DECLARED in
# viewer-settings.json (`owner_names`, a list of the owner's own spellings; `name_fixes`, {spelling -> card slug})
# rather than written here, so this code names nobody and every copy of the viewer carries its own (2026-09-17).
# Empty is the default and a working state: a name that no card matches and no fix names stays unmapped and is
# reported as such, never invented. A bare first name belongs in `name_fixes` only when it is unambiguous across every
# card in that brain; a first name several cards share never does.
OWNER_NAMES = {re.sub(r"\s+", " ", str(n)).strip().lower() for n in (SETTINGS.get("owner_names") or []) if str(n).strip()}
NAME_FIXES = {re.sub(r"\s+", " ", str(k)).strip().lower(): str(v).strip()
              for k, v in (SETTINGS.get("name_fixes") or {}).items() if str(k).strip() and str(v).strip()}
_tx_cache = {}                   # transcript abs path -> ((mtime, size), row)
_tx_index = {"t": 0, "rows": [], "unmapped": {}}
_alias_cache = {"t": 0, "map": {}}
BRING_HEAD_RE = re.compile(r"^##\s*4\.\s", re.I)
NEXT_HEAD_RE = re.compile(r"^##\s")


def alias_map():
    """{lowered name -> slug} from the cards themselves, plus the handful of transcriber spellings the brain already knows about.
    Rebuilt at most once a minute; a name that is not in here stays unmapped and is reported as such."""
    if time.time() - _alias_cache["t"] < 60 and _alias_cache["map"]:
        return _alias_cache["map"]
    m = {}
    root = os.path.join(BRAIN, PEOPLE_REL)
    for fn in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if not fn.endswith(".md") or fn == "readme.md":
            continue
        slug = fn[:-3]
        titles = [slug.replace("-", " ")]
        try:
            with open(os.path.join(root, fn), "r", encoding="utf-8-sig") as f:
                fm, body = split_fm(f.read(2000))
            if fm.get("name"):
                titles.append(fm["name"])
            titles += [l[2:].strip() for l in body[:40] if l.startswith("# ")][:1]
        except Exception:
            pass
        for t in titles:
            t = re.sub(r"\s+", " ", str(t)).strip()
            if not t:
                continue
            m.setdefault(t.lower(), slug)
            bare = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip()          # "Full Name (Nickname)" -> also "Full Name"
            paren = (re.search(r"\(([^)]+)\)\s*$", t) or [None, ""])[1].strip()
            for extra in (bare, paren):
                if extra and re.fullmatch(r"[A-Za-z][A-Za-z' -]{2,}", extra):   # a name, not "(Esq.)" or "(mentor)"
                    m.setdefault(extra.lower(), slug)
    m.update(NAME_FIXES)
    _alias_cache.update(t=time.time(), map=m)
    return m


def tx_row(ap, rel):
    """One transcript as {date, path, source, title, names}. The app mirror's JSON declares its participants; a raw file is read
    for an `Attendees:` header, else for the speakers with three or more turns (one stray line is not a participant)."""
    fm = DATE_RE.search(os.path.basename(rel))
    date = fm.group(1) if fm else None
    ext = os.path.splitext(rel)[1].lower()
    if ext == ".json":
        with open(ap, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return None
        date = str(d.get("date") or date or "")[:10]
        items = [{"text": clip(i.get("description"), 200), "owner": i.get("owner"), "status": i.get("status") or i.get("approvalStatus")}
                 for i in (d.get("actionItems") or []) if isinstance(i, dict)][:10]
        return {"date": date, "path": rel, "source": "app", "title": clip(d.get("title"), 160),
                "names": [x for x in (d.get("participants") or []) if isinstance(x, str)],
                "summary": first_para(str(d.get("aiSummary") or "").split("\n"), 320), "items": items}
    turns, att = {}, []
    with open(ap, "r", encoding="utf-8-sig", errors="replace") as f:
        for i, l in enumerate(f):
            if i < 14 and not att:
                # three ways a transcript states who was there, most explicit first: frontmatter `participants: [..]`, an
                # `Attendees:` header, else the speakers themselves (below)
                a = TX_ATTEND_RE.match(l) or TX_PARTS_RE.match(l)
                if a:
                    att = [x.strip().strip("[]") for x in a.group(1).strip().strip("[]").split(",") if x.strip().strip("[]")]
            s = TX_SPEAKER_RE.match(l.strip()) or TX_TIMED_RE.match(l.rstrip())
            if s:
                turns[s.group(1)] = turns.get(s.group(1), 0) + 1
    names = att or [n for n, k in turns.items() if k >= 3]
    return {"date": date, "path": rel, "source": "raw", "title": os.path.basename(rel), "names": names, "summary": "", "items": []}


def transcript_index():
    """Every readable transcript with its participants mapped to card slugs, newest call first. Cached per file mtime/size and
    re-walked at most every two minutes, so the panel never waits on it twice (decision 10: no loading states)."""
    if time.time() - _tx_index["t"] < 120 and _tx_index["rows"]:
        return _tx_index
    rows, unmapped, al = [], {}, alias_map()
    for d in TRANSCRIPT_DIRS:
        root = os.path.join(BRAIN, d.replace("/", os.sep))
        if not os.path.isdir(root):
            continue
        mirror = d != TRANSCRIPT_DIRS[0]
        for fn in sorted(os.listdir(root)):
            ext = os.path.splitext(fn)[1].lower()
            # the mirror ships a .json and a .txt per call; the JSON declares its participants, so the 5 MB of .txt beside it is skipped
            if fn.lower() in ("readme.md", "index.md") or ext not in ((".json",) if mirror else TX_EXT):
                continue
            ap, rel = os.path.join(root, fn), "%s/%s" % (d, fn)
            try:
                st = os.stat(ap)
                hit = _tx_cache.get(ap)
                row = hit[1] if hit and hit[0] == (st.st_mtime, st.st_size) else tx_row(ap, rel)
                if row is None:
                    continue
                if not hit or hit[0] != (st.st_mtime, st.st_size):
                    _tx_cache[ap] = ((st.st_mtime, st.st_size), row)
            except Exception:
                continue
            if not DATE_RE.fullmatch(str(row.get("date") or "")):
                continue
            slugs, un = set(), []
            for n in row["names"]:
                disp = re.sub(r"\s+", " ", str(n or "")).strip(" .,[]\"'")
                key = disp.lower()
                if key in OWNER_NAMES:
                    continue
                s = al.get(key) or al.get(re.sub(r"\s*\([^)]*\)\s*$", "", key).strip())   # "Grace Schmidt (she/her)"
                if s:
                    slugs.add(s)
                elif key:
                    un.append(disp)
                    unmapped[disp] = unmapped.get(disp, 0) + 1
            r = dict(row)
            r["slugs"] = sorted(slugs)
            r["unmapped"] = un
            rows.append(r)
    rows.sort(key=lambda r: (r["date"], r["source"] != "app"), reverse=True)   # newest first; the mirror wins a tie, it carries the summary
    _tx_index.update(t=time.time(), rows=rows, unmapped=unmapped)
    return _tx_index


def newest_transcript(members):
    """The newest transcript whose participants include ALL members (the group's own matching rule). None is a normal answer."""
    want = set(members or [])
    if not want:
        return None
    for r in transcript_index()["rows"]:
        if want <= set(r["slugs"]):
            return r
    return None


def load_groups():
    """skills/call-prep/call-prep-groups.json as written. Never repaired here: a bad file is reported, not guessed at."""
    ap = os.path.join(BRAIN, GROUPS_REL.replace("/", os.sep))
    if not os.path.isfile(ap):
        return {"groups": [], "_error": "no %s yet" % GROUPS_REL}
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {"groups": [], "_error": "%s is not an object" % GROUPS_REL}
    except Exception as e:
        return {"groups": [], "_error": "%s: %s" % (type(e).__name__, e)}


def group_row(g, byKey=None):
    """One declared group, resolved: members to cards, the newest matching transcript, its preps."""
    gid = str(g.get("id") or "").strip()
    members = [str(m).strip() for m in (g.get("members") or []) if str(m).strip()]
    names, unknown = [], []
    for m in members:
        rel, ap = card_path(m)
        if ap:
            names.append({"slug": m, "name": parse_card(rel, ap)["name"], "path": rel})
        else:
            unknown.append(m)
            names.append({"slug": m, "name": m.replace("-", " "), "path": None})
    tx = newest_transcript([m for m in members if m not in unknown])
    ps = (byKey or {}).get(gid) or preps(gid)
    mset = set(members)
    open_items = [r for r in open_for_zak() if mset & set(r["people"])]     # counted once even when it names two of them
    return {"id": gid, "name": g.get("name") or gid, "cadence": g.get("cadence") or "", "notes": g.get("notes") or "",
            "open": len(open_items), "openItems": open_items[:20],
            "confirmed": bool(g.get("confirmed")), "evidence": g.get("evidence") or {},
            "members": names, "memberSlugs": members, "unknownMembers": unknown,
            "lastCall": {"date": tx["date"], "path": tx["path"], "title": tx["title"], "source": tx["source"]} if tx else None,
            "preps": len(ps), "lastPrep": ps[0]["call"] if ps else None, "prepList": ps[:6]}


def groups_api():
    d = load_groups()
    byKey = {}
    for p in preps():
        byKey.setdefault(p["key"], []).append(p)
    rows = [group_row(g, byKey) for g in (d.get("groups") or []) if isinstance(g, dict) and g.get("id")]
    idx = transcript_index()
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "file": GROUPS_REL, "today": ledger.today(),
            "updated": d.get("_updated", ""), "note": d.get("_note", ""), "notSeeded": d.get("_not_seeded") or {},
            "count": len(rows), "groups": rows, "error": d.get("_error"),
            "transcripts": len(idx["rows"]), "unmappedNames": sorted(idx["unmapped"].items(), key=lambda kv: -kv[1])[:12]}


def ledger_mentions(members, names):
    """The open ledger items that need these people: every @<owner> task and every open question, across the registered projects,
    whose text names a member by first or full name. This is how a team call's agenda assembles itself (T-0027)."""
    pats = []
    for slug, nm in zip(members, names):
        bare = re.sub(r"\s*\([^)]*\)\s*$", "", nm or "").strip() or slug.replace("-", " ")
        words = [w for w in re.split(r"[\s-]+", bare) if len(w) > 2]
        if not words:
            continue
        # the full name anywhere, or the first name when it is NOT followed by a surname -- so a member whose first name
        # several cards share does not collect every line about all of them
        alts = [re.escape(bare)] + ([re.escape(w) for w in words[1:]] if len(words) > 1 else [])
        rx = r"\b(?:%s)\b|\b%s\b(?!\s+[A-Z][a-z])" % ("|".join(sorted(set(alts), key=len, reverse=True)), re.escape(words[0]))
        pats.append((slug, bare, re.compile(rx)))
    out = []
    for h in registry().get("holons", []):
        rel = h.get("tasks")
        ap = os.path.join(BRAIN, (rel or "").replace("/", os.sep))
        if not rel or not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:
            continue
        for it in p["items"]:
            if it["kind"] == "question":
                if it["state"] != "open":
                    continue
            elif not (it["state"] in ("open", "blocked") and it["owner"] == OWNER):
                continue
            hits = [nm for _, nm, rx in pats if rx.search(it["text"] or "")]
            if not hits:
                continue
            out.append({"project": h.get("name") or h["id"], "path": rel, "id": it["id"], "kind": it["kind"],
                        "text": clip(it["text"], 200), "who": hits, "state": it["state"], "due": it["due"]})
    out.sort(key=lambda r: (r["kind"] != "question", r["project"], r["id"]))
    return out[:14]


def prev_bring(key, before):
    """The previous prep for the SAME call thread, and its unanswered `Bring` questions. A follow-up prep starts from the last
    one (T-0027): its open items are carried forward and marked, so nothing quietly falls off the agenda between calls."""
    earlier = [p for p in preps(key) if p["call"] < before]
    if not earlier:
        return None, []
    prev = earlier[0]
    carried = []
    try:
        with open(os.path.join(BRAIN, prev["path"].replace("/", os.sep)), "r", encoding="utf-8-sig") as f:
            lines = f.read().replace("\r\n", "\n").split("\n")
    except Exception:
        return prev, []
    on = False
    for l in lines:
        if BRING_HEAD_RE.match(l):
            on = True
            continue
        if on and NEXT_HEAD_RE.match(l):
            break
        if on and BULLET_RE.match(l) and "/call-prep" not in l:
            t = re.sub(r"^\s*[-*+]\s+", "", l).strip()
            if t.startswith("[x]") or t.lower().startswith("answered"):
                continue
            carried.append(clip(t, 220))
    return prev, carried[:10]


_app_cache = {}                  # endpoint -> (fetched_at, list)  -- a group prep asks for the same two lists once per member


def app_list(ep, ttl=60):
    """The app's `contacts` / `tasks` list, memoised for a minute so a three-person group prep makes two calls, not six."""
    hit = _app_cache.get(ep)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    rows = (app_get(ep) or {}).get(ep) or []
    _app_cache[ep] = (time.time(), rows)
    return rows


def app_action_items(name):
    """The PF App's Action Items for this person, when the app holds a contact by that exact name.
    Shapes printed from one real record before filtering (Correction #61, verified live 2026-09-09):
      GET /contacts -> {success, contacts: [{id, name, role, email, company, aiBio, lastContactDate, isMentor, ...}]}
      GET /tasks    -> {success, tasks:    [{id, title, dueDate, assignee, projectName, status, priority, overdue, ...}]}
    A task names its assignee by NAME, not by contact id, so the join is on the contact's own name. Never fatal: a miss,
    a 4xx or an unreachable app all come back as a note the prep prints and carries on."""
    out = {"contact": None, "items": [], "note": ""}
    if PROPOSE:
        out["note"] = "PF App: not read in a team copy"
        return out
    try:
        cs = app_list("contacts")
    except Exception as e:
        out["note"] = "PF App: contacts unreachable (%s)" % type(e).__name__
        return out
    # a card title can carry a short name where the app carries the full one (a card titled "Short (Formal)" against the
    # app's "Formal Surname"), so the parenthetical is tried as a first name too -- still an EXACT match, never a fuzzy one
    bare = re.sub(r"\s*\([^)]*\)\s*$", "", str(name)).strip()
    paren = (re.search(r"\(([^)]+)\)\s*$", str(name)) or [None, ""])[1].strip()
    cands = [str(name).strip(), bare]
    if paren and " " not in paren and " " in bare:
        cands.append("%s %s" % (paren, bare.split()[-1]))
    want = [c.lower() for c in cands if c]
    hit = next((c for c in cs if str(c.get("name") or "").strip().lower() in want), None)
    if not hit:
        out["note"] = "PF App: no contact record found for %s (%d contacts checked)" % (bare or name, len(cs))
        return out
    out["contact"] = {"id": hit.get("id"), "name": hit.get("name"), "role": hit.get("role"), "company": hit.get("company"),
                      "lastContactDate": hit.get("lastContactDate")}
    try:
        ts = app_list("tasks")
    except Exception as e:
        out["note"] = "PF App: contact found, action items unreachable (%s)" % type(e).__name__
        return out
    who = str(hit.get("name") or "").strip().lower()
    out["items"] = [{"title": clip(t.get("title"), 200), "status": t.get("status"), "due": t.get("dueDate"), "overdue": t.get("overdue")}
                    for t in ts if str(t.get("assignee") or "").strip().lower() == who and str(t.get("status") or "").lower() != "completed"][:12]
    out["note"] = "PF App: contact %s, %d open action item%s" % (hit.get("name"), len(out["items"]), "" if len(out["items"]) == 1 else "s")
    return out


# ---- the v3 prep skeleton: questions by subject, points per person, the rest closed (2026-09-21, ledger T-0203) ----
# Format: [[skills/call-prep/call-prep-format.md]], rewritten as v3 on 2026-09-21. That morning the owner found the
# 'bring to the meeting' section hard to turn into specific questions, with too much noise and too many closed tabs,
# and asked for sections of questions and points per person on the prep, with the why and the who still there but closed.
# So the durable unit is the SUBJECT FILE (`projects/<project>/subjects/<slug>.md`): it owns the open questions and who
# answers each. The skeleton no longer assembles an agenda out of ledger ids and card bullets -- it reads the subjects whose
# `threads:` name this call (or, for a one-to-one or an ad-hoc set, whose `people:` cover every participant), prints their
# open questions addressed to the person who can answer them, and moves everything section 4 used to print into Context,
# which renders closed. Sections, always in this order: Questions, Points per person, Decide before and the close, Your
# notes, Since last time, Context. The v2 writers (seven numbered sections) are gone from here; the v2 preps on disk stay
# valid as held records and nothing rewrites them.
SUBJECTS_GLOBS = ("projects/*/subjects/*.md", "projects/*/*/subjects/*.md")
SUBJECT_QUESTION_CAP = 5          # format rule 7: at most five per subject per call, the rest stay in the subject file
SUBJECT_ANSWERED_CAP = 8          # ...and what Since last time prints per subject before it becomes a wall
_subject_cache = {}               # projects/.../subjects/<slug>.md -> ((mtime, size), parsed subject)

SUBJ_NOT_THIS_CALL_RE = re.compile(r"_not this call", re.I)   # "...ends `_not this call_`" (format, Open questions)
SUBJ_WHO_RE = re.compile(r"^\*\*(.+?)\*\*\s*(?:·|:|—|–|-)?\s*(.*)$")
SUBJ_RAISED_RE = re.compile(r"\s*·\s*\([^()]*\)\s*$")         # the raised-note: " · (9/21; pf-build T-0007)"
SUBJ_ITALIC_TAIL_RE = re.compile(r"\s*_[^_]*_\s*$")
TOP_BULLET_RE = re.compile(r"^[-*+]\s+\S")                    # top-level only: an indented line is a continuation, not a question
# 0.50.1 (2026-09-25): a subject file's Answered line keeps `[[transcript]] L612` in its source column (a record field),
# but the prep this skeleton writes is read during the call, so a copied line carries the refs in a trailing comment.
# On 2026-09-25 the owner asked that these line refs stop showing up in anything read during a call.
_LREF_SEQ = r"L\d{1,4}(?:[ \t]*(?:to|-)[ \t]*L?\d{1,4}\b|[ \t]*(?:,|and)[ \t]*L\d{1,4}\b)*"
LREF_SEQ_RE = re.compile(r"[ \t]*\(%s\)|[ \t]*(?<!lint )\b%s" % (_LREF_SEQ, _LREF_SEQ))


def refs_to_comment(text):
    """'q · a · Mike, 2026-09-24 · [[t.txt]] L912 to L914' -> '... · [[t.txt]] <!-- L912 to L914 -->'."""
    refs = [m.group(0).strip(" \t()") for m in LREF_SEQ_RE.finditer(text or "")]
    if not refs:
        return text
    body = LREF_SEQ_RE.sub("", text)
    body = re.sub(r"[,;][ \t]*\)", ")", body)
    body = re.sub(r"[ \t]*\([ \t]*\)", "", body)
    body = re.sub(r"[ \t]+([,;:.)\]])", r"\1", body).rstrip(" \t·,;")
    return "%s <!-- %s -->" % (body, ", ".join(refs))


def fm_list(fm, key):
    """A one-line frontmatter list (`threads: [a, b]`) as a python list. split_fm reads a shallow `k: v`, so the brackets
    arrive as text. Nothing here repairs a malformed line -- it comes back empty and the prep says which subjects it found."""
    return [x.strip().strip('"').strip("'") for x in
            re.sub(r"^\[|\]$", "", str(fm.get(key) or "").strip()).split(",") if x.strip()]


def subject_question(line):
    """One `- **<who answers>** · <the question> · (<when raised>)` line as {who, text}, or None when the line is not a
    question this call can carry: a continuation line, or one the subject file marked `_not this call_`."""
    if not TOP_BULLET_RE.match(line or ""):
        return None
    t = re.sub(r"^\s*[-*+]\s+", "", line).strip()
    if SUBJ_NOT_THIS_CALL_RE.search(t):
        return None
    m = SUBJ_WHO_RE.match(t)
    who, text = (m.group(1).strip(), m.group(2)) if m else ("", t)
    text = SUBJ_ITALIC_TAIL_RE.sub("", text.strip())
    text = SUBJ_RAISED_RE.sub("", text).strip(" ·\t")
    return {"who": clip(who, 60), "text": clip(text, 400)} if text else None


def parse_subject(rel, ap):
    """One subject file as the prep needs it: its routing fields, its open questions in file order, its answers with dates."""
    with open(ap, "r", encoding="utf-8-sig") as f:
        fm, body = split_fm(f.read())
    qs = [q for q in (subject_question(l) for l in h2_section(body, "Open questions")) if q]
    ans = []
    for l in h2_section(body, "Answered"):
        if not TOP_BULLET_RE.match(l):
            continue
        t = re.sub(r"^\s*[-*+]\s+", "", l).strip()
        d = DATE_RE.search(t)
        ans.append({"date": d.group(1) if d else "", "text": clip(t, 400)})
    name = fm.get("subject") or next((l[2:].strip() for l in body if l.startswith("# ")), os.path.basename(rel)[:-3])
    return {"rel": rel, "slug": fm.get("slug") or os.path.basename(rel)[:-3], "name": name,
            "threads": fm_list(fm, "threads"), "people": fm_list(fm, "people"),
            "status": str(fm.get("status") or "").strip().lower(), "questions": qs, "answered": ans}


def load_subjects():
    """Every subject file under `projects/*/subjects/`, parsed once per change. A file that will not parse is skipped, never
    guessed at: a subject the prep could not read is better missing than half-read."""
    out, seen = [], set()
    for g in SUBJECTS_GLOBS:
        for ap in sorted(glob.glob(os.path.join(BRAIN, g.replace("/", os.sep)))):
            rel = os.path.relpath(ap, BRAIN).replace(os.sep, "/")
            if rel in seen or os.path.basename(rel) == "readme.md":
                continue
            seen.add(rel)
            try:
                st = os.stat(ap)
                hit = _subject_cache.get(rel)
                if hit and hit[0] == (st.st_mtime, st.st_size):
                    out.append(hit[1])
                    continue
                s = parse_subject(rel, ap)
                _subject_cache[rel] = ((st.st_mtime, st.st_size), s)
                out.append(s)
            except Exception:
                continue
    return out


def subjects_for(key, members, is_group):
    """The subjects this call carries: the ones whose `threads:` name the key, plus -- for anything that is not a declared
    thread (a one-to-one, an ad-hoc set) -- the ones whose `people:` cover every participant. A settled or dropped subject
    is not carried onto a prep. Routing is the subject file's own business: a subject with the wrong fields is invisible,
    which is why the prep prints the ones it found in Context."""
    subs = [s for s in load_subjects() if s["status"] not in ("settled", "dropped")]
    hits = [s for s in subs if key in s["threads"]]
    if not is_group:
        mset, seen = set(members or []), {s["rel"] for s in hits}
        hits += [s for s in subs if s["rel"] not in seen and mset and mset <= set(s["people"])]
    hits.sort(key=lambda s: s["rel"])
    return hits


def prep_v3_text(key, g, cards, call_date, purpose, tx, apps, subs, prev, mentions, nocard=None):
    """The skeleton in the v3 shape, from the subject files and the cards and nothing else. `Decide before, and the close`
    stays a pointer and the five-per-subject choice is the command's, so a half-written prep never reads as a finished one
    (Correction #71: one prep per call, and no unasked second version)."""
    names = [c["row"]["name"] for c in cards]
    who = (g or {}).get("name") or " + ".join(names)
    one = len(cards) == 1 and g is None
    todo = "Draft with `/call-prep %s` (Claude reads the subject files, the cards and the transcripts and fills this)." % key
    srcs = [s["rel"] for s in subs] + [c["rel"] for c in cards] + ([tx["path"]] if tx else []) + \
           (["PF App /api/v1/contacts + /api/v1/tasks"] if any(a.get("contact") for a in apps) else [])
    L = ["---", ("person: %s" % cards[0]["slug"]) if one else ("group: %s" % ((g or {}).get("id") or "")),
         "participants: [%s]" % ", ".join(c["slug"] for c in cards),
         "call: %s" % (call_date or "undated"),
         "purpose: %s" % (purpose or '""'),
         "format: v3",
         "subjects: [%s]" % ", ".join(s["slug"] for s in subs),
         "generated: %s" % dt.datetime.now().astimezone().isoformat(timespec="seconds"),
         "sources: [%s]" % ", ".join(srcs),
         "status: draft",
         "---", "",
         "# %s — call prep, %s" % (who, call_date or "undated"), "",
         "> Skeleton written by the Brain Viewer's People panel in the v3 shape ([[skills/call-prep/call-prep-format.md]]): the "
         "questions come from the subject files this thread carries, the points from the cards, which stay the truth about these "
         "people (Correction #42). `/call-prep %s` chooses which five per subject this call takes and writes *Decide before, and "
         "the close*." % key, ""]
    if nocard:
        # 0.47.0 (auto_prep.py, T-0130): attendee names on the calendar with no people/ card, listed as names and
        # nothing more -- a card is never invented from a calendar entry (Correction #42)
        L += ["> **On the calendar with no card:** %s." % ", ".join(nocard), ""]
    L += ["## Questions", ""]
    if subs:
        for s in subs:
            qs = s["questions"][:SUBJECT_QUESTION_CAP]
            left = len(s["questions"]) - len(qs)
            L += ["### %s" % s["name"], ""]
            if qs:
                L += ["- **%s:** %s" % (q["who"] or "who answers is not named in the subject file", refs_to_comment(q["text"])) for q in qs]
                L += ["", "<!-- %d of %d open questions in %s, in file order. Five per subject per call is format rule 7, so %s -->"
                      % (len(qs), len(s["questions"]),
                         s["rel"], ("%d stayed in the subject file" % left) if left else "none were left behind")]
            else:
                L += ["- _Nothing is open in [[%s]] for this call._" % s["rel"]]
            L += [""]
    else:
        L += ["### (no subject file yet)", "",
              "- _No subject file carries this call. A subject is one matter worked through with people over several calls; "
              "they live in `projects/<project>/subjects/` and route by `threads:` (the group id, here `%s`) or `people:` (the "
              "participants), in the shape [[skills/call-prep/call-prep-format.md]] describes. `/call-prep %s` proposes one and "
              "says so._" % (key, key), ""]
    L += ["## Points per person", ""]
    for c in cards:
        L += ["### %s" % c["row"]["name"], ""]
        lines = c["flags"][:3] or c["notes"][:3]
        shown = {x[:110] for x in lines}
        if lines:
            L += ["- %s" % x for x in lines]
        else:
            L += ["- _The card carries no Flags and no Key Notes line. Read [[%s]] before the call._" % c["rel"]]
        L += ["- **Do not say:** %s" % d for d in [d for d in c["donot"] if d[:110] not in shown][:2]]
        L += [""]
    L += ["## Decide before, and the close", "", todo, "",
          "## Your notes", "",
          "<!-- Owner: the notes for this call belong here, not in the notepad (format v3, section 4). A notes file dropped with "
          "the transcript is filed into this section verbatim at intake. -->", "", "",
          "## Since last time", ""]
    if tx:
        L += ["**Last call with all of them:** %s — [[%s]]%s" % (tx["date"], tx["path"], " · %s" % tx["title"] if tx["title"] else ""), ""]
        if tx.get("summary"):
            L += [tx["summary"], ""]
        if tx.get("items"):
            L += ["The action items that call produced, and where they stand:", ""] + [
                "- %s%s%s" % (i["text"], " · %s" % i["owner"] if i.get("owner") else "", " · %s" % i["status"] if i.get("status") else "")
                for i in tx["items"]] + [""]
    else:
        L += ["**No transcript in the brain has all of these people on it.** Either this set has not met, or the last call was "
              "not recorded — check before treating this as a first meeting.", ""]
    since = prev["call"] if prev else ""
    for s in subs:
        rows = [a for a in s["answered"] if not since or (a["date"] and a["date"] > since)]
        if not rows:
            continue
        L += ["**Answered in [[%s]] since %s:**" % (s["rel"], ("the prep of " + since) if since else "it was opened"), ""]
        L += ["- %s" % refs_to_comment(a["text"]) for a in rows[:SUBJECT_ANSWERED_CAP]] + [""]
    L += ["What each side owes, from the cards:", ""]
    any_owed = False
    for c in cards:
        if c["owed"]:
            any_owed = True
            L += ["- **%s**" % c["row"]["name"]] + ["    - %s" % x["text"] for x in c["owed"][:4]]
    if not any_owed:
        L += ["- Nothing on the cards reads as owed by any side. Check the transcripts before believing that."]
    L += [""]
    for c, a in zip(cards, apps):
        if a.get("items"):
            L += ["Open action items in the PF App for **%s**:" % c["row"]["name"], ""] + [
                "- %s%s%s" % (i["title"], " · due %s" % i["due"][:10] if i.get("due") else "", " · overdue" if i.get("overdue") else "")
                for i in a["items"]] + [""]
    L += ["_%s_" % " · ".join(a.get("note") or "PF App: not checked" for a in apps), "",
          "## Context", ""]
    for c in cards:
        r = c["row"]
        L.append("- **%s** ([[%s]]) — %s%s" % (r["name"], c["rel"], r["role"] or "no Role & Relationship line",
                                               " · %s" % clip(r["status"], 140) if r["status"] else ""))
    L += ["", "**This call is for:** %s" % (purpose or "_not stated yet — say what this call is for before it starts._"), ""]
    if (g or {}).get("cadence"):
        L += ["**Cadence:** %s" % g["cadence"], ""]
    if (g or {}).get("notes"):
        L += ["**On this thread:** %s" % g["notes"], ""]
    if g is not None and not g.get("confirmed"):
        L += ["> This thread is seeded, not confirmed by the owner yet — check the membership in [[%s]] before you trust the set." % GROUPS_REL, ""]
    if subs:
        L += ["**The subject files this prep was built from:**", ""] + [
            "- [[%s]] — %s (%d open question%s, `threads: %s`)" % (s["rel"], s["name"], len(s["questions"]),
                                                                   "" if len(s["questions"]) == 1 else "s",
                                                                   ", ".join(s["threads"]) or "none") for s in subs] + [""]
    else:
        L += ["**No subject file was found for `%s`.** Nothing routes to this call yet; the folder is "
              "`projects/<project>/subjects/` and the shape is in [[skills/call-prep/call-prep-format.md]]." % key, ""]
    if prev:
        L += ["**The previous prep for this call:** [[%s]] (%s)%s" % (prev["path"], prev["call"],
                                                                      " · %s" % prev["purpose"] if prev.get("purpose") else ""), "",
              "Open questions carry themselves in the subject files now; the previous prep is a record, not the agenda (format v3).", ""]
    else:
        L += ["**No earlier prep for `%s`.** This is the first one on file for this call." % key, ""]
    if mentions:
        L += ["**Open in the ledgers, naming %s** (answer them in the viewer at `/projects`):" %
              (" or ".join(n.split()[0] for n in names) if names else "them"), ""]
        L += ["- %s `%s` (%s) — %s%s" % ("Question" if m["kind"] == "question" else OWNER, m["id"], m["project"], refs_to_comment(m["text"]),
                                         " · due %s" % m["due"] if m["due"] else "") for m in mentions] + [""]
    L += ["_Claude's read:_ nothing here is weighted yet — the skeleton derives, `/call-prep %s` judges (Correction #59)." % key, ""]
    return "\n".join(L)


def resolve_call(slug=None, group=None, participants=None):
    """What call is this prep for? Returns (key, [slugs], group dict or None). A group id, an explicit participant list, or one
    person -- the same endpoint for all three, because a prep is keyed to a CALL (T-0027)."""
    gid = str(group or "").strip()
    if gid:
        if not GROUP_ID_RE.match(gid):
            raise ValueError("not a group id: %r" % gid)
        g = next((x for x in (load_groups().get("groups") or []) if isinstance(x, dict) and str(x.get("id") or "").strip() == gid), None)
        if not g:
            raise ValueError("no group %r in %s" % (gid, GROUPS_REL))
        members = [str(m).strip() for m in (g.get("members") or []) if str(m).strip()]
        if not members:
            raise ValueError("group %r has no members" % gid)
        return gid, members, g
    ps = [str(p).strip() for p in (participants or []) if str(p).strip()]
    if not ps and slug:
        ps = [str(slug).strip()]
    if not ps:
        raise ValueError("a prep needs a slug, a group, or participants")
    ps = sorted(set(ps))
    return ("+".join(ps) if len(ps) > 1 else ps[0]), ps, None


def make_prep(slug=None, call_date=None, purpose="", group=None, participants=None, dest=None, nocard=None):
    """Write one dated prep skeleton for a call, in the v3 shape. Returns (relative path, existed). Never overwrites a
    prep: one prep per call (format rule 4). `dest` writes the same text to a path OUTSIDE the brain instead -- the test
    runs the writer without putting a file into deliverables/call-prep/ and without a log line for a prep nobody asked for."""
    key, members, g = resolve_call(slug, group, participants)
    cards = []
    for m in members:
        rel, ap = card_path(m)
        if not rel:
            raise ValueError("not a person slug: %r" % m)
        if not ap:
            raise ValueError("no card at %s" % rel)
        with open(ap, "r", encoding="utf-8-sig") as f:
            _, body = split_fm(f.read())
        cards.append({"slug": m, "rel": rel, "ap": ap, "body": body, "row": parse_card(rel, ap),
                      "owed": owed_from(body), "flags": bullets(h2_section(body, "Flags")),
                      "notes": bullets(h2_section(body, "Key Notes")), "donot": donot_from(body)})
    call_date = (call_date or "").strip() or dt.date.today().isoformat()
    if not DATE_RE.fullmatch(call_date):
        raise ValueError("call date must be YYYY-MM-DD, got %r" % call_date)
    purpose = " ".join(str(purpose or "").split())[:200]
    out_rel = "%s/%s-call-prep-%s.md" % (CALLPREP_REL, key, call_date)
    out_ap = os.path.join(BRAIN, out_rel.replace("/", os.sep))
    if dest:
        out_rel, out_ap = dest, dest
    elif os.path.isfile(out_ap):
        return out_rel, True
    names = [c["row"]["name"] for c in cards]
    apps = [app_action_items(n) for n in names]
    subs = subjects_for(key, members, g is not None)
    prev = prev_bring(key, call_date)[0]      # the previous prep for this key; a v2 `Bring` carry is not read into a v3 prep
    text = prep_v3_text(key, g, cards, call_date, purpose, newest_transcript(members), apps, subs,
                        prev, ledger_mentions(members, names), nocard=[str(n) for n in (nocard or []) if str(n).strip()])
    who = (g or {}).get("name") or " + ".join(names)
    os.makedirs(os.path.dirname(out_ap), exist_ok=True)
    with open(out_ap, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if dest:
        return out_rel, False
    log_line("%s -- call prep skeleton for %s written in the v3 shape from %s in the People panel (Decide before, and "
             "the five-per-subject choice, await /call-prep)"
             % (out_rel, who, ", ".join([x["rel"] for x in subs] + [c["rel"] for c in cards])), action="CREATED")
    return out_rel, False


# ---- Chat (2026-09-09; ideas E16 step 2, ledger T-0031): every conversation is a real Claude Code session started by the viewer ----
# On 9/09 the owner asked for chat with the agents inside the app: one agent that tasks and dispatches to the other agents
# in the project, chat per project, and above all questions reaching the specific areas they belong to.
# So: POST /api/chat/send runs `claude -p` on THIS machine and THIS account (cwd = the brain root), relays its stream-json lines
# to the page as server-sent events while they arrive, and remembers only an INDEX of the conversation
# (context/chats/<id>.json: project, session id, title, turns, cost, the ledger items the turn created). The body of the
# conversation is Claude Code's own transcript under ~/.claude/projects/<brain>/<session id>.jsonl, read back for the history
# view with the same reader /api/agents uses (spec §2c) -- nothing of it is copied into the brain.
# Probed 2026-09-09 on claude 2.1.121, from the brain root:
#   - `claude -p` reads the message from STDIN when no positional prompt is given (no command-line length or quoting limits);
#   - `--output-format stream-json` needs `--verbose` in print mode, or it refuses; `--include-partial-messages` adds the deltas;
#   - `--session-id <uuid>` opens a conversation under that id (its transcript lands under that name), `--resume <uuid>` continues it;
#   - `--append-system-prompt-file <path>` carries the prompt (the inline flag works too; the file avoids the Windows 32K line);
#   - `--permission-mode auto` let Bash run `tasks.py check` with no prompt and no denial (permission_denials: []);
#   - `--model opus` resolves to claude-opus-4-7; `--model fable` / `claude-fable-5-1` are REFUSED by this CLI version
#     ("2.1.251 or newer is required"), so the fable toggle is offered only when the installed CLI is new enough.
# One running turn per conversation; a 10-minute cap; the child is killed when the page goes away or Stop is pressed. In a team
# copy every chat route answers 403: chat runs on the owner's machine, never through a copy.
CHATS_REL = "context/chats"
CHAT_PROMPTS = os.path.join(HERE, "chat-prompts")
# The models the picker offers, and which one a turn runs on when the page does not say (2026-09-17, T-0187). On 9/17 the
# owner saw about 1.60 spent on a really simple question -- measured on a four-turn ledger chat that afternoon:
# 2.61 USD, 12 model calls, 388K cache-write and 519K cache-read tokens on claude-opus-5. Sonnet is the default because the
# work in this window is mostly reading a ledger and writing a sentence; opus and fable stay one press away.
CHAT_MODELS = {"sonnet": "claude-sonnet-5", "opus": "opus", "fable": "claude-fable-5-1"}
CHAT_MODEL_ORDER = ["sonnet", "fable", "opus"]
CHAT_MODEL_DEFAULT = "sonnet"
CHAT_MODEL_FALLBACK = "opus"          # what a default that the installed CLI refuses falls back to
CHAT_MODEL_WHEN = {"sonnet": "the default: questions, ledger work, short edits",
                   "fable": "pick it for design and judgment",
                   "opus": "pick it for long builds"}
CHAT_TURN_SECONDS = 600
CHAT_ID_RE = re.compile(r"^c-\d{8}-\d{6}-[a-f0-9]{4}$")
_chat_running = {}       # chat id -> {"proc": Popen, "since": iso, "stop": reason or None}
_chat_lock = threading.Lock()


def cli_version_of(path):
    """One binary's version string, asked of the binary itself (a machine fact, not a guess)."""
    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30)
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", r.stdout or "")
        return m.group(0) if m else None
    except Exception:
        return None


def find_claude():
    """The NEWEST claude on this machine, asked once at startup: the one on PATH, or the desktop app's bundled build under
    %APPDATA%/Claude/claude-code/<version>/claude.exe. On 2026-09-09 PATH held 2.1.121 and the desktop app 2.1.258 + 2.1.260;
    only the newer one runs fable (2.1.121: "version 2.1.251 or newer is required"), and every flag this server uses exists in
    both. If the bundled build disappears with an app update, the next start falls back to PATH. -> (path, version) or (None, None)."""
    cands = []
    w = shutil.which("claude")
    if w:
        cands.append(w)
    appdata = os.environ.get("APPDATA")
    if appdata:
        cands += glob.glob(os.path.join(appdata, "Claude", "claude-code", "*", "claude.exe"))
    best = (None, None)
    for c in cands:
        v = cli_version_of(c)
        if v and (best[1] is None or tuple(int(x) for x in v.split(".")) > tuple(int(x) for x in best[1].split("."))):
            best = (c, v)
    return best


CLAUDE_BIN, CLI_VERSION = find_claude()


_model_probe = {}                     # model word -> {"ok", "note", "ms"}; filled once at startup, in the background
_probe_lock = threading.Lock()


def probe_model(key, timeout=25):
    """Does the installed claude accept this model id? Asked of the binary itself, with the API pointed at a dead port so the
    probe can never bill a real call: an id the CLI does not know is refused CLIENT-side ([claude-code:unrecognized_model],
    about five seconds, zero tokens), and an id it knows gets as far as trying to reach the API and is killed there.
    -> {"ok", "note", "ms"}. Probed this way on 2026-09-17: claude-sonnet-5 accepted, claude-bogus-9 refused."""
    mid = CHAT_MODELS.get(key, key)
    if not CLAUDE_BIN:
        return {"ok": False, "note": "no claude on this machine to ask", "ms": 0}
    env = dict(os.environ, ANTHROPIC_BASE_URL="http://127.0.0.1:1")
    t0 = time.time()
    try:
        proc = subprocess.Popen([CLAUDE_BIN, "-p", "--model", mid, "--output-format", "json",
                                 "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}'],
                                cwd=tempfile.gettempdir(), env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception as e:
        return {"ok": False, "note": "could not start claude to ask: %s" % e, "ms": 0}
    out = [b""]

    def read():
        try:
            out[0] = proc.stdout.read() or b""
        except Exception:
            pass
    th = threading.Thread(target=read, daemon=True); th.start()
    try:
        proc.stdin.write(b"probe"); proc.stdin.close()
    except Exception:
        pass
    try:
        proc.wait(timeout=timeout)
    except Exception:
        kill_tree(proc)                   # it got past the model check and is retrying an API that is not there: that is a yes
    th.join(2)
    txt = out[0].decode("utf-8", "replace")
    ms = int((time.time() - t0) * 1000)
    if "unrecognized_model" in txt:
        return {"ok": False, "note": "claude %s does not know the model id %s" % (CLI_VERSION or "?", mid), "ms": ms}
    return {"ok": True, "note": None, "ms": ms}


def probe_models_once():
    """Startup, once, off the serving thread: ask the installed CLI about the default model id (opus and fable are settled by
    the CLI version). Until it answers, the default stands; if it comes back no, chat_default_model() falls to opus."""
    for key in (CHAT_MODEL_DEFAULT,):
        r = probe_model(key)
        with _probe_lock:
            _model_probe[key] = r
        if not r["ok"]:
            log_line("skills/brain-viewer/serve.py -- the chat's default model %s (%s) is refused by the installed claude: %s. "
                     "Chat falls back to %s" % (key, CHAT_MODELS[key], r["note"], CHAT_MODEL_FALLBACK), action="MODIFIED")


def chat_default_model():
    """The model a turn runs on when the page does not name one: sonnet, unless the startup probe says this CLI refuses it."""
    r = _model_probe.get(CHAT_MODEL_DEFAULT)
    return CHAT_MODEL_FALLBACK if (r and not r["ok"]) else CHAT_MODEL_DEFAULT


def chat_models():
    v = tuple(int(x) for x in CLI_VERSION.split(".")) if CLI_VERSION else (0, 0, 0)
    fable_ok = v >= (2, 1, 251)
    dflt = chat_default_model()
    pr = _model_probe.get(CHAT_MODEL_DEFAULT)
    rows = {"sonnet": {"ok": pr["ok"] if pr else True, "resolves": CHAT_MODELS["sonnet"],
                       "note": (pr or {}).get("note") if pr else "asking the installed claude about this model id"},
            "opus": {"ok": True, "resolves": "opus (claude-opus-5 on this CLI)", "note": None},
            "fable": {"ok": fable_ok, "resolves": CHAT_MODELS["fable"],
                      "note": None if fable_ok else "claude %s refuses this model; 2.1.251 or newer is needed (claude update)" % (CLI_VERSION or "?")}}
    return [dict(rows[k], id=k, label=k, when=CHAT_MODEL_WHEN[k], default=(k == dflt)) for k in CHAT_MODEL_ORDER]


def chats_dir():
    d = os.path.join(BRAIN, CHATS_REL.replace("/", os.sep))
    os.makedirs(d, exist_ok=True)
    return d


def chat_path(cid):
    return os.path.join(chats_dir(), cid + ".json") if CHAT_ID_RE.match(cid or "") else None


def read_chat(cid):
    ap = chat_path(cid)
    if not ap or not os.path.isfile(ap):
        return None
    with open(ap, "r", encoding="utf-8-sig") as f:
        rec = json.load(f)
    return rec if isinstance(rec, dict) and rec.get("id") == cid else None


def write_chat(rec):
    ap = chat_path(rec["id"])
    tmp = ap + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1); f.write("\n")
    os.replace(tmp, ap)


def chat_projects():
    """The projects a chat can be fixed to: every registry row with a ledger, with what its agent boots from (readme, ledger,
    a *-spec.md in the folder root if there is one, the registry's rules file). Declared, not guessed."""
    out = []
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        path = (h.get("path") or "").strip("/")
        folder = os.path.join(BRAIN, path.replace("/", os.sep)) if path else BRAIN
        readme = spec = None
        if os.path.isdir(folder):
            if os.path.isfile(os.path.join(folder, "readme.md")):
                readme = (path + "/" if path else "") + "readme.md"
            for fn in sorted(os.listdir(folder)):
                if fn.endswith("-spec.md"):
                    spec = (path + "/" if path else "") + fn
                    break
        out.append({"id": h["id"], "name": h.get("name") or h["id"], "path": (path + "/") if path else "", "ledger": h["tasks"],
                    "readme": readme, "spec": spec, "rules": h.get("rules"), "description": h.get("description")})
    return out


def chat_prompt(project):
    """The system prompt appended to every turn: chat-prompts/main.md for the main agent (with the routable projects filled
    in), chat-prompts/project.md filled for one project. Read at spawn, so editing the file changes the next turn."""
    if project == "main":
        with open(os.path.join(CHAT_PROMPTS, "main.md"), "r", encoding="utf-8") as f:
            t = f.read()
        rows = ["- **%s** — id `%s`, folder `%s`, ledger `%s`%s" % (p["name"], p["id"], p["path"] or "(brain root)", p["ledger"],
                                                                (" — " + p["description"]) if p.get("description") else "")
                for p in chat_projects()]
        return t.replace("{projects}", "\n".join(rows) or "- (no project has a ledger yet)")
    p = next((x for x in chat_projects() if x["id"] == project), None)
    if not p:
        raise ValueError("no project %r with a ledger in the registry" % project)
    # The paths, with what each file weighs, and NOTHING of their contents (2026-09-17, T-0187). The prompt used to send the
    # agent to read the readme, the whole ledger, the spec and the rules before its first word: for this project that is about
    # 360 KB of markdown pulled into every turn. The ledger is read with tasks.py now, and the rest only when a message needs it.
    boot = []
    for label, rel in (("the readme, what this project is", p["readme"]),
                       ("the ledger, read with the tool below rather than opened", p["ledger"]),
                       ("the spec, how it is built", p["spec"]), ("the rules", p["rules"])):
        if not rel:
            continue
        ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        kb = (os.path.getsize(ap) / 1024.0) if os.path.isfile(ap) else 0
        boot.append("- `%s` -- %s%s" % (rel, label, (" (%d KB)" % round(kb)) if kb else ""))
    with open(os.path.join(CHAT_PROMPTS, "project.md"), "r", encoding="utf-8") as f:
        t = f.read()
    return (t.replace("{name}", p["name"]).replace("{project}", p["id"]).replace("{path}", p["path"] or "(brain root)")
             .replace("{ledger}", p["ledger"]).replace("{files}", "\n".join(boot) or "- `%s` -- the ledger" % p["ledger"]))


# ---- what every turn carries before a word of the conversation (2026-09-17, T-0187) ----
# The owner asked why a simple question cost what it cost. Part of the answer is fixed and the same every turn: Claude Code
# auto-loads the CLAUDE.md files, the SessionStart hooks print their block into the context, and this page appends a system
# prompt. Those are bytes on disk (and bytes a hook printed, read back from a transcript it was injected into -- no hook is
# ever re-run to measure it, because a hook that polls would poll), counted at four characters to the token. The CLI's own
# system prompt and tool definitions sit on top and are not counted here: about 55K tokens, measured 2026-09-17, and not
# something the viewer can change.
_hook_cache = {"at": 0, "chars": 0, "source": None}
HOOK_CACHE_SECONDS = 600


def hook_context_chars():
    """How much the SessionStart hooks put into a session, taken from the newest transcript that recorded one.
    -> (chars, where it was read)"""
    if time.time() - _hook_cache["at"] < HOOK_CACHE_SECONDS and _hook_cache["source"]:
        return _hook_cache["chars"], _hook_cache["source"]
    d = sessions_dir()
    files = []
    if d and os.path.isdir(d):
        files = sorted(glob.glob(os.path.join(d, "*.jsonl")), key=lambda f: os.path.getmtime(f), reverse=True)[:8]
    for fp in files:
        total, hits = 0, 0
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i > 60:
                        break
                    if "hook_success" not in line:
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    a = o.get("attachment") or {}
                    if str(a.get("hookEvent") or "").startswith("SessionStart"):
                        total += len(str(a.get("stdout") or a.get("content") or "")); hits += 1
        except Exception:
            continue
        if hits:
            _hook_cache.update({"at": time.time(), "chars": total, "source": "a session on this machine (%s)" % os.path.basename(fp)[:8]})
            return total, _hook_cache["source"]
    _hook_cache.update({"at": time.time(), "chars": 0, "source": "no session on this machine recorded one"})
    return 0, _hook_cache["source"]


def chat_context_weight():
    """The fixed part of every turn, in characters: the two CLAUDE.md files Claude Code auto-loads plus what the SessionStart
    hooks printed. The appended prompt is per project, so its size travels beside this, one number per project."""
    parts = []
    for label, ap in (("CLAUDE.md, this brain", os.path.join(BRAIN, "CLAUDE.md")),
                      ("CLAUDE.md, your user one", os.path.join(os.path.expanduser("~"), ".claude", "CLAUDE.md"))):
        parts.append({"what": label, "chars": os.path.getsize(ap) if os.path.isfile(ap) else 0})
    hc, src = hook_context_chars()
    parts.append({"what": "the session-start hook", "chars": hc, "from": src})
    prompts = {}
    for pid in ["main"] + [x["id"] for x in chat_projects()]:
        try:
            prompts[pid] = len(chat_prompt(pid))
        except Exception:
            pass
    return {"parts": parts, "chars": sum(x["chars"] for x in parts), "charsPerToken": 4, "prompts": prompts}


def cost_of_result(o):
    """What the CLI says a turn cost. total_cost_usd when it gives one, with the basis it reports per model: 'list' means the
    published prices, anything else (or no number at all, which a subscription login can do) is shown as a CLI estimate."""
    o = o or {}
    c = o.get("total_cost_usd")
    c = round(float(c), 6) if isinstance(c, (int, float)) else None
    bases = sorted({str((v or {}).get("costBasis")) for v in (o.get("modelUsage") or {}).values() if isinstance(v, dict)} - {"None"})
    basis = ", ".join(bases) if bases else None
    return {"cost_usd": c, "basis": basis, "estimate": c is None or basis not in ("list",),
            "models": sorted((o.get("modelUsage") or {}).keys())}


def ledger_snapshot():
    """{(project id, item id): item} across every registered ledger. Taken before and after a turn, so the items a chat
    created can be shown as chips and remembered in the index; the ledger itself stays the truth (rules 1)."""
    snap = {}
    for hid, name, rel in ledger.ledgers():
        ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:
            continue
        for it in p["items"]:
            snap[(hid, it["id"])] = {"project": hid, "projectName": name, "path": rel, "id": it["id"], "kind": it["kind"],
                                     "text": clip(it["text"], 140), "owner": it["owner"], "to": it.get("to"),
                                     "people": it.get("people") or [], "state": it["state"]}
    return snap


def ledger_new(before, after):
    return [after[k] for k in after if k not in before]


def tool_summary(name, inp):
    """One line per tool call for the 'working…' fold: the command, the file, the pattern, or the sub-agent's description."""
    inp = inp if isinstance(inp, dict) else {}
    base = BRAIN.replace("\\", "/").rstrip("/").lower() + "/"

    def rel(p):
        q = str(p or "").replace("\\", "/")
        return q[len(base):] if q.lower().startswith(base) else q
    if name == "Bash":
        s = inp.get("description") or inp.get("command") or ""
    elif name in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        s = rel(inp.get("file_path") or inp.get("notebook_path"))
    elif name in ("Grep", "Glob"):
        s = "%s%s" % (inp.get("pattern", ""), (" in " + rel(inp["path"])) if inp.get("path") else "")
    elif name == "Agent":
        s = "%s · %s%s" % (inp.get("description") or "(no description)", inp.get("subagent_type") or "general-purpose",
                           (" · " + str(inp["model"])) if inp.get("model") else "")
    elif name in ("WebFetch", "WebSearch"):
        s = inp.get("url") or inp.get("query") or ""
    elif name == "Skill":
        s = inp.get("skill", "")
    else:
        s = json.dumps(inp, ensure_ascii=False)
    return clip(mask_secrets(" ".join(str(s).split())), 160)


def parse_chat(path):
    """One Claude Code transcript -> the conversation as turns: what the owner typed, what came back, the tool calls between.
    The same file /api/agents reads (spec §2c), read the same way: streamed, every field defensive, nothing stored."""
    turns, cur = [], None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("isSidechain"):
                continue
            t = o.get("type"); msg = o.get("message") or {}; c = msg.get("content"); ts = o.get("timestamp")
            if t == "user":
                if o.get("isMeta"):
                    continue                          # "Continue from where you left off." -- what --resume injects
                if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_result" and cur:
                            for tl in cur["tools"]:
                                if tl["id"] == b.get("tool_use_id"):
                                    tl["done"] = True; tl["error"] = bool(b.get("is_error"))
                                    tl["preview"] = clip(mask_secrets(blocks_text(b.get("content"))), 200)
                    continue
                if notification_texts(o, c):
                    continue                          # a background agent's answer, not one of the owner's turns
                text = (c if isinstance(c, str) else blocks_text(c)).strip()
                if not text:
                    continue
                turns.append({"role": "user", "text": text, "ts": ts}); cur = None
            elif t == "assistant" and isinstance(c, list):
                blocks = [b for b in c if isinstance(b, dict)]
                if len(blocks) == 1 and blocks[0].get("type") == "text" and (blocks[0].get("text") or "").strip() == "No response requested.":
                    continue                          # the other half of the --resume artifact
                if cur is None:
                    cur = {"role": "assistant", "text": "", "tools": [], "ts": ts, "model": msg.get("model")}; turns.append(cur)
                for b in blocks:
                    if b.get("type") == "text" and (b.get("text") or "").strip():
                        cur["text"] = (cur["text"] + "\n\n" + b["text"].strip()).strip()
                    elif b.get("type") == "tool_use":
                        cur["tools"].append({"id": b.get("id"), "name": b.get("name"), "summary": tool_summary(b.get("name"), b.get("input")),
                                             "done": False, "error": False, "preview": None})
    for tr in turns:
        if tr["role"] == "assistant":
            tr["text"] = mask_secrets(tr["text"])
    return turns


def kill_tree(proc):
    """End the turn's process and whatever it started (a Bash tool's shell, for one). Windows needs taskkill /T for the tree."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=20)
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def chat_stop(cid, reason="stopped from the page"):
    with _chat_lock:
        run = _chat_running.get(cid)
    if not run or not run.get("proc"):
        return False
    run["stop"] = run.get("stop") or reason
    kill_tree(run["proc"])
    return True


def chat_index_rows():
    """Every conversation index row in context/chats/, newest first, each marked with whether a turn is running in it.
    One reader for all of it: the chat page's rail, the bubbles on /agents and the home strip, and the adoption check."""
    rows = []
    d = chats_dir()
    for fn in os.listdir(d):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, fn), "r", encoding="utf-8-sig") as f:
                rec = json.load(f)
        except Exception:
            continue
        if isinstance(rec, dict) and rec.get("id"):
            rec["running"] = rec["id"] in _chat_running
            rows.append(rec)
    rows.sort(key=lambda r: r.get("last") or r.get("created") or "", reverse=True)
    return rows


def chats_api():
    rows = chat_index_rows()
    return {"chats": rows, "projects": chat_projects(), "models": chat_models(), "running": sorted(_chat_running),
            "folder": CHATS_REL, "cli": CLAUDE_BIN, "cliVersion": CLI_VERSION, "capMinutes": CHAT_TURN_SECONDS // 60,
            "default_model": chat_default_model(), "context": chat_context_weight()}


def chat_api(cid):
    """One conversation: its index row + the history read from its Claude Code transcript (turns, and the sub-agents it spawned
    with their status and answers, via the same cached session() reader the Agents strip uses)."""
    rec = read_chat(cid)
    if not rec:
        return None, "no such conversation"
    d = sessions_dir()
    tp = os.path.join(d, rec["session_id"] + ".jsonl") if d else None
    turns, subs, note = [], [], None
    if tp and os.path.isfile(tp):
        try:
            turns = parse_chat(tp)
            subs = (session(tp) or {}).get("subagents") or []
        except Exception as e:
            note = "the transcript would not parse: %s: %s" % (type(e).__name__, e)
    else:
        note = "no transcript for this conversation on this machine (bodies live under ~/.claude/projects/; a chat started elsewhere has none here)"
    rec["running"] = cid in _chat_running
    return {"chat": rec, "turns": turns, "subagents": subs, "note": note, "transcript": tp if tp and os.path.isfile(tp) else None}, None


# ---- a session drawn, read back, and taken into the chat (2026-09-10; T-0117, T-0101, T-0102) ----
# The owner asked on 9/10 for in-progress chats shown as a bubble that opens their history on a double click and can be
# entered, and whether moving one conversation from the Claude CLI over to the app breaks anything. Sequential is safe:
# --resume opens the same session and appends to the same transcript. CONCURRENT IS NOT -- two processes appending to one
# .jsonl interleave their lines and the file stops parsing -- so adoption is refused while the transcript is still moving.
# The evidence used is the transcript's own mtime (the only thing on disk that says whether something is writing it) plus
# a sub-agent of that session still working. Nothing here copies a transcript into the brain: an adopted session gets an
# index row pointing at the file Claude Code already owns.
ADOPT_QUIET_SECONDS = 120
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,79}$")


def model_key_of(model):
    """The chat's own model word for a model id the transcript reports (claude-opus-4-7 -> opus). Defaults to opus."""
    m = str(model or "").lower()
    for k in CHAT_MODELS:
        if k in m:
            return k
    return "opus"


def project_for_cwd(cwd):
    """The project a session belongs to, read from the folder it ran in: the deepest registry path that contains its cwd,
    or "main" for the brain root. Declared, never guessed (rules 1)."""
    c = str(cwd or "").replace("\\", "/").rstrip("/").lower()
    b = BRAIN.replace("\\", "/").rstrip("/").lower()
    if not c or not c.startswith(b):
        return "main"
    rel = c[len(b):].strip("/")
    best, blen = "main", -1
    for pr in chat_projects():
        path = (pr["path"] or "").strip("/").lower()
        if path and (rel == path or rel.startswith(path + "/")) and len(path) > blen:
            best, blen = pr["id"], len(path)
    return best


def transcript_path(sid):
    d = sessions_dir()
    if not d or not SESSION_ID_RE.match(str(sid or "")):
        return None
    ap = os.path.join(d, sid + ".jsonl")
    return ap if os.path.isfile(ap) else None


def adopt_check(sess, row):
    """(ok, reason) -- may the chat take this session over? A plain sentence when not, because it is shown as written."""
    ap = transcript_path((sess or {}).get("sessionId"))
    if not ap:
        return False, "there is no transcript for that session on this machine"
    if row and row.get("id") in _chat_running:
        return False, "a turn is running in this conversation right now; wait for it to finish"
    if (sess.get("counts") or {}).get("running"):
        return False, "a sub-agent this session spawned is still working, so the session is still open somewhere else"
    quiet = time.time() - os.path.getmtime(ap)
    if quiet < ADOPT_QUIET_SECONDS:
        return False, ("something wrote to this session %d seconds ago, so it is still open somewhere else. Two programs "
                       "writing one transcript at once corrupt it, so wait for two quiet minutes and try again" % int(quiet))
    return True, None


def session_view(sid):
    """One session read back read-only: the header, the history as turns, the sub-agents, the conversation row if the app
    has one, and whether it can be opened in the chat. Same readers as /api/chat and /api/agents; nothing is stored."""
    ap = transcript_path(sid)
    if not ap:
        return None, "no transcript for that session on this machine (bodies live under ~/.claude/projects/)"
    sess = session(ap) or {}
    try:
        turns = parse_chat(ap)
    except Exception as e:
        return None, "the transcript would not parse: %s: %s" % (type(e).__name__, e)
    row = next((r for r in chat_index_rows() if r.get("session_id") == sid), None)
    ok, why = adopt_check(sess, row)
    head = {k: sess.get(k) for k in ("id", "sessionId", "title", "model", "models", "cwd", "branch", "cliVersion",
                                     "started", "lastActive", "minutesIdle", "active", "userTurns", "counts", "error")}
    return {"session": head, "turns": turns, "subagents": sess.get("subagents") or [], "chat": row,
            "adopt": {"ok": ok, "reason": why}}, None


def chat_adopt(sid):
    """POST /api/chat/adopt -- a Claude Code session becomes a conversation in the rail: an index row (project from its cwd,
    title from the session, turns as they already stand) pointing at the transcript it already has. The next turn resumes it
    by session id, so the app picks up the same agent where the CLI left it. -> (body, error, status)"""
    ap = transcript_path(sid)
    if not ap:
        return None, "no transcript for that session on this machine", 404
    sess = session(ap) or {}
    have = next((r for r in chat_index_rows() if r.get("session_id") == sid), None)
    if have:
        return {"ok": True, "chat": have, "existed": True,
                "note": "this session is already a conversation here"}, None, 200
    ok, why = adopt_check(sess, None)
    if not ok:
        return None, why, 409
    now = dt.datetime.now()
    cid = "c-%s-%s" % (now.strftime("%Y%m%d-%H%M%S"), uuid.uuid4().hex[:4])
    project = project_for_cwd(sess.get("cwd"))
    rec = {"id": cid, "project": project, "title": clip(sess.get("title") or "(untitled session)", 80), "session_id": sid,
           "model": model_key_of(sess.get("model")), "created": now.isoformat(timespec="seconds"),
           "last": sess.get("lastActive"), "turns": int(sess.get("userTurns") or 0), "cost_usd": 0.0, "dispatched": [],
           "adopted": {"at": now.isoformat(timespec="seconds"), "source": "a Claude Code session on this machine",
                       "cwd": sess.get("cwd"), "cli": sess.get("cliVersion"), "turnsThen": int(sess.get("userTurns") or 0)},
           "_note": "index only; the body is Claude Code's transcript ~/.claude/projects/<brain path>/%s.jsonl, which this "
                    "session already owns -- the app resumes it rather than starting anything new" % sid}
    write_chat(rec)
    log_line("%s/%s.json -- a Claude Code session opened in the chat (session %s, %d turns already, %s). Index only: the body "
             "stays that session's own transcript, and the next turn resumes it"
             % (CHATS_REL, cid, sid, int(sess.get("userTurns") or 0),
                "the main agent" if project == "main" else "project " + project), action="CREATED")
    return {"ok": True, "chat": rec, "existed": False}, None, 200


def handoff_write(target_cid, target_project, src, resume):
    """The send-to line, written onto BOTH index rows so the agents page can draw it (2026-09-10, T-0094): the owner asked
    to draw a line from a chat that feeds its answer into a higher-level agent. The quoted reply itself is
    just the next message in the target conversation -- this only records which conversation it came from.
    -> (the entry to put on a new target row, an error)"""
    sid = str((src or {}).get("chat") or "").strip()
    if not sid:
        return None, None
    srec = read_chat(sid)
    if not srec:
        return None, "the conversation this reply came from is not in the index"
    turn = src.get("turn") if isinstance(src.get("turn"), int) else None
    at = dt.datetime.now().isoformat(timespec="seconds")
    entry = {"direction": "in", "chat": sid, "title": srec.get("title"), "project": srec.get("project"), "turn": turn, "at": at}
    if resume:
        trec = read_chat(target_cid)
        if trec:
            trec["handoffs"] = (trec.get("handoffs") or []) + [entry]
            write_chat(trec)
    if srec["id"] != target_cid:
        srec["handoffs"] = (srec.get("handoffs") or []) + [{"direction": "out", "chat": target_cid, "project": target_project,
                                                            "turn": turn, "at": at}]
        write_chat(srec)
    return entry, None


def chat_send(h, data):
    """POST /api/chat/send {chat, project, text, model} -> a text/event-stream of the turn. Spawns `claude -p` (the message on
    stdin, the prompt in a file, --session-id on the first turn and --resume after), relays its stream-json as it arrives,
    diffs the ledgers to see what the turn put on them, and updates the index when it ends."""
    text = str(data.get("text") or "").strip()
    if not text:
        return h._send(400, {"error": "text is required"})
    model = str(data.get("model") or chat_default_model())
    if model not in CHAT_MODELS:
        return h._send(400, {"error": "model must be one of: %s" % ", ".join(CHAT_MODELS)})
    model_note = None
    probed = _model_probe.get(model)
    if probed and not probed["ok"]:                # the startup probe says this CLI will not run it: run the fallback, say so
        model_note = "%s: %s. This turn ran on %s" % (model, probed["note"], CHAT_MODEL_FALLBACK)
        model = CHAT_MODEL_FALLBACK
    if not CLAUDE_BIN:
        return h._send(500, {"error": "the claude CLI is not on PATH on this machine"})
    cid = str(data.get("chat") or "").strip() or None
    projects = {p["id"]: p for p in chat_projects()}
    if cid:
        rec = read_chat(cid)
        if not rec:
            return h._send(404, {"error": "no such conversation"})
        project, sid, resume = rec["project"], rec["session_id"], True
    else:
        project = str(data.get("project") or "main")
        if project != "main" and project not in projects:
            return h._send(400, {"error": "unknown project %r: main, or a registry id with a ledger" % project})
        now = dt.datetime.now()
        cid = "c-%s-%s" % (now.strftime("%Y%m%d-%H%M%S"), uuid.uuid4().hex[:4])
        sid, resume = str(uuid.uuid4()), False
        rec = {"id": cid, "project": project, "title": clip(" ".join(text.split()), 80), "session_id": sid, "model": model,
               "created": now.isoformat(timespec="seconds"), "last": None, "turns": 0, "cost_usd": 0.0, "dispatched": [],
               "_note": "index only; the body is Claude Code's transcript ~/.claude/projects/<brain path>/%s.jsonl" % sid}
    try:
        prompt = chat_prompt(project)
    except Exception as e:
        return h._send(500, {"error": "could not build the system prompt: %s" % e})
    with _chat_lock:
        if cid in _chat_running:
            return h._send(409, {"error": "a turn is already running in this conversation: stop it, or wait for it"})
        run = _chat_running[cid] = {"proc": None, "since": dt.datetime.now().isoformat(timespec="seconds"), "stop": None}
    # a send-to: this message carries another conversation's reply, so the line between the two is recorded before the
    # turn runs (T-0094). The quoted reply travels as the message itself; this is only the line the agents page draws.
    hand = None
    if isinstance(data.get("from"), dict):
        hand, herr = handoff_write(cid, project, data["from"], resume)
        if herr:
            with _chat_lock:
                _chat_running.pop(cid, None)
            return h._send(400, {"error": herr})
        if hand and not resume:
            rec["handoffs"] = [hand]
    pdir = os.path.join(tempfile.gettempdir(), "brain-viewer-chat")
    os.makedirs(pdir, exist_ok=True)
    pfile = os.path.join(pdir, "%s-%d.md" % (cid, int(time.time())))
    with open(pfile, "w", encoding="utf-8", newline="\n") as f:
        f.write(prompt)
    before = ledger_snapshot()
    args = [CLAUDE_BIN, "-p", "--output-format", "stream-json", "--include-partial-messages", "--verbose",
            "--model", CHAT_MODELS[model], "--permission-mode", "auto", "--append-system-prompt-file", pfile]
    args += ["--resume", sid] if resume else ["--session-id", sid]
    try:
        proc = subprocess.Popen(args, cwd=BRAIN, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        with _chat_lock:
            _chat_running.pop(cid, None)
        return h._send(500, {"error": "could not start claude: %s" % e})
    run["proc"] = proc
    if not resume:
        write_chat(rec)
        log_line("%s/%s.json -- conversation opened in the Brain Viewer chat (%s; Claude Code session %s, model %s). Index only: the body is that session's transcript"
                 % (CHATS_REL, cid, "the main agent" if project == "main" else "project " + project, sid, model), action="CREATED")
    if hand:
        log_line("%s/%s.json + %s/%s.json -- one agent's reply handed to another (send-to): the line is on both index rows"
                 % (CHATS_REL, hand["chat"], CHATS_REL, cid), action="LINKED")

    def feed():           # the message goes in on stdin, then stdin closes so -p starts at once (it waits 3 s for stdin otherwise)
        try:
            proc.stdin.write(text.encode("utf-8")); proc.stdin.close()
        except Exception:
            pass
    err_tail = []

    def drain():          # stderr is read on its own thread so a chatty child can never fill the pipe and stall
        try:
            for ln in proc.stderr:
                err_tail.append(ln.decode("utf-8", "replace")); del err_tail[:-40]
        except Exception:
            pass
    threading.Thread(target=feed, daemon=True).start()
    threading.Thread(target=drain, daemon=True).start()
    timer = threading.Timer(CHAT_TURN_SECONDS, lambda: chat_stop(cid, "the turn ran past %d minutes and was stopped" % (CHAT_TURN_SECONDS // 60)))
    timer.daemon = True; timer.start()

    h.send_response(200)
    h.send_header("Content-Type", "text/event-stream; charset=utf-8")
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Accel-Buffering", "no")
    h.end_headers()
    connected = [True]

    def sse(obj):
        if not connected[0]:
            return
        try:
            h.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8")); h.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            connected[0] = False                    # the page went away: the turn ends with it
            run["stop"] = run.get("stop") or "the page went away"
            kill_tree(proc)
    sse({"e": "start", "chat": cid, "project": project, "session": sid, "model": model, "modelId": CHAT_MODELS[model],
         "resumed": resume, "title": rec["title"], "note": model_note, "promptChars": len(prompt)})
    result = None
    try:
        for raw in proc.stdout:
            try:
                o = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            t = o.get("type")
            if t == "system" and o.get("subtype") == "init":
                sse({"e": "init", "model": o.get("model"), "tools": len(o.get("tools") or []), "cli": o.get("claude_code_version"),
                     "permissionMode": o.get("permissionMode")})
            elif t == "stream_event":
                if o.get("parent_tool_use_id"):
                    continue                        # a sub-agent's own stream: its answer arrives as the Agent tool's result
                ev = o.get("event") or {}
                et = ev.get("type")
                if et == "message_start":
                    sse({"e": "seg"})
                elif et == "content_block_delta" and (ev.get("delta") or {}).get("type") == "text_delta":
                    sse({"e": "text", "t": ev["delta"].get("text", "")})
            elif t == "assistant":
                if o.get("parent_tool_use_id"):
                    continue
                for b in ((o.get("message") or {}).get("content") or []):
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text":
                        sse({"e": "text_final", "t": mask_secrets(b.get("text") or "")})
                    elif b.get("type") == "tool_use":
                        inp = b.get("input") or {}
                        ev = {"e": "tool", "id": b.get("id"), "name": b.get("name"), "summary": tool_summary(b.get("name"), inp)}
                        if b.get("name") == "Agent":
                            ev["agent"] = {"description": inp.get("description"), "type": inp.get("subagent_type"),
                                           "model": inp.get("model"), "background": bool(inp.get("run_in_background"))}
                        sse(ev)
            elif t == "user":
                if o.get("parent_tool_use_id"):
                    continue
                for b in ((o.get("message") or {}).get("content") or []):
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        sse({"e": "tool_done", "id": b.get("tool_use_id"), "error": bool(b.get("is_error")),
                             "preview": clip(mask_secrets(blocks_text(b.get("content"))), 200)})
            elif t == "result":
                result = o
                u = o.get("usage") or {}
                ci = cost_of_result(o)
                sse({"e": "done", "ok": not o.get("is_error"), "text": mask_secrets(o.get("result") or ""), "cost": ci["cost_usd"],
                     "estimate": ci["estimate"], "basis": ci["basis"], "modelIds": ci["models"], "modelWord": model,
                     "turns": o.get("num_turns"), "duration_ms": o.get("duration_ms"), "session": o.get("session_id"), "subtype": o.get("subtype"),
                     "usage": {k: u.get(k) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")},
                     "denials": o.get("permission_denials") or []})
    finally:
        rc = proc.wait()
        timer.cancel()
        with _chat_lock:
            _chat_running.pop(cid, None)
        try:
            os.remove(pfile)
        except OSError:
            pass
    stopped = run.get("stop")
    if stopped:
        sse({"e": "stopped", "reason": stopped})
    elif result is None:
        sse({"e": "error", "message": clip("".join(err_tail).strip() or "claude exited with code %s and no result" % rc, 600)})
    new_items = ledger_new(before, ledger_snapshot())
    if new_items:
        sse({"e": "ledger", "items": new_items})
    rec = read_chat(cid) or rec
    rec["last"] = dt.datetime.now().isoformat(timespec="seconds")
    rec["turns"] = int(rec.get("turns") or 0) + 1
    rec["model"] = model
    # per turn, not only the running total (2026-09-17, T-0187): the page shows each turn's own cost under it, and the row
    # keeps the list so a conversation reopened tomorrow still shows where its money went.
    ci = cost_of_result(result)
    if ci["cost_usd"] is not None:
        rec["cost_usd"] = round(float(rec.get("cost_usd") or 0) + ci["cost_usd"], 4)
    rec["turns_cost"] = (rec.get("turns_cost") or []) + [
        {"turn": rec["turns"], "model": model, "modelIds": ci["models"], "cost_usd": ci["cost_usd"], "estimate": ci["estimate"],
         "basis": ci["basis"], "duration_ms": (result or {}).get("duration_ms"), "steps": (result or {}).get("num_turns"),
         "at": rec["last"], "stopped": bool(stopped),
         "usage": {k: ((result or {}).get("usage") or {}).get(k) for k in
                   ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}}]
    rec["last_result"] = ({"ok": False, "stopped": stopped} if stopped else
                          {"ok": bool(result) and not result.get("is_error"), "turns": (result or {}).get("num_turns"),
                           "duration_ms": (result or {}).get("duration_ms"), "cost_usd": (result or {}).get("total_cost_usd")})
    rec["dispatched"] = (rec.get("dispatched") or []) + [{"project": i["project"], "id": i["id"], "kind": i["kind"], "text": i["text"], "turn": rec["turns"]} for i in new_items]
    write_chat(rec)
    sse({"e": "end", "chat": rec})


# ---- the bubbles (/map, 2026-09-09; ideas E14 + E16, step 3 of the rebuild) ----
# The owner asked on 9/09 for bubbles that connect to everything and carry notification symbols, and on 9/08 for a look
# with physics rather than a static one. ONE graph, joined at read time from what the brain
# already declares and what the other endpoints already compute: nothing here is drawn by hand (rules 1) and nothing is stored
# (rules 2). A node is a thing that exists -- a project (a registry row with a ledger), a person (a card), a standing group (the
# groups file), a hub of documents (the dashboard manifest, the canvases), a conversation (the chat index), the team copy (its
# status file), a running session (the transcripts). An edge is a declared relation: an open ledger item tagged with a person on
# a project, a membership, a piece whose file sits under a project's path, a chat fixed to a project, a team-tier holon in the
# copy, a session that is a chat. The badge on a bubble is the same count /api/badges puts on the nav. Children (pieces,
# canvases, preps) carry `parent` and the page shows them only when their hub is unfolded; people with nothing open carry
# `quiet` and the page folds them into one bubble. In a team copy there are no people, groups, chats or agents (rules 3, 6).
TEAM_STATUS_REL = "skills/team-brain/status.json"
GRAPH_CHATS = 10                 # the newest conversations shown as bubbles
GRAPH_LABEL = 64                 # a bubble's label, at most


def graph_api():
    nodes, seen, edges = [], {}, {}

    def node(nid, **kw):
        if nid in seen:
            return seen[nid]
        d = {"id": nid, "badge": 0, "href": None, "summary": []}
        d.update(kw)
        d["label"] = clip(d.get("label") or nid, GRAPH_LABEL)
        d["summary"] = [x for x in (d.get("summary") or []) if x][:2]
        nodes.append(d); seen[nid] = d
        return d

    def edge(a, b, kind):
        if a and b and a != b:
            k = (a, b, kind) if a < b else (b, a, kind)
            edges[k] = edges.get(k, 0) + 1

    reg = registry()
    holons = [h for h in reg.get("holons", []) if h.get("tasks")]
    b = badges_api()
    rows = open_for_zak()
    notes = []

    # projects: every registry row with a ledger; the badge = what is waiting on the owner there
    paths = []
    for h in holons:
        pb = b["projects"].get(h["id"]) or {}
        q, t = pb.get("questions", 0), pb.get("zak_tasks", 0)
        node("project:" + h["id"], type="project", key=h["id"], label=h.get("name") or h["id"], badge=q + t,
             href="/projects?id=%s" % urllib.parse.quote(h["id"]), path=h.get("path"), sharing=h.get("sharing"),
             summary=[clip(h.get("description") or "", 110),
                      "%d question%s and %d task%s waiting on you" % (q, "" if q == 1 else "s", t, "" if t == 1 else "s") if q + t else "nothing waiting on you"])
        if h.get("path"):
            paths.append(((h["path"].strip("/") + "/"), h["id"]))
    paths.sort(key=lambda x: -len(x[0]))          # the deepest declared folder wins

    def project_for(rel):
        return next((pid for pre, pid in paths if rel.startswith(pre)), None)

    preps_by_key = {}
    if not PROPOSE:
        for pr in preps():
            preps_by_key.setdefault(pr["key"], []).append(pr)

        # people: every card; quiet when nothing is open about them (the page folds those)
        for pe in people_api()["people"]:
            kids = preps_by_key.get(pe["slug"]) or []
            node("person:" + pe["slug"], type="person", key=pe["slug"], label=pe["name"], badge=pe["open"], quiet=pe["open"] == 0,
                 hub=bool(kids), href="/people?open=%s" % urllib.parse.quote(pe["slug"]), path=pe["path"],
                 summary=[clip(pe.get("role") or pe.get("category") or "", 110),
                          ("last dated fold %s" % pe["lastFold"]) if pe.get("lastFold") else ("%d flag%s on the card" % (pe["flags"], "" if pe["flags"] == 1 else "s") if pe.get("flags") else "no dated fold on the card")])
        for r in rows:                                    # person -- project: an open item about them on that ledger
            for sl in r["people"]:
                edge("person:" + sl, "project:" + r["project"], "item")

        # groups: the standing threads, declared in the groups file
        for g in load_groups().get("groups") or []:
            if not isinstance(g, dict) or not g.get("id"):
                continue
            gid = str(g["id"]); members = [str(mm).strip() for mm in (g.get("members") or []) if str(mm).strip()]
            mset = set(members)
            items = [r for r in rows if mset & set(r["people"])]
            kids = preps_by_key.get(gid) or []
            node("group:" + gid, type="group", key=gid, label=g.get("name") or gid, badge=len(items), hub=bool(kids),
                 href="/people?group=%s" % urllib.parse.quote(gid), confirmed=bool(g.get("confirmed")),
                 summary=[", ".join(seen["person:" + mm]["label"] if ("person:" + mm) in seen else mm.replace("-", " ") for mm in members),
                          (g.get("cadence") or "no cadence on record") + ("" if g.get("confirmed") else " · not confirmed yet")])
            for mm in members:
                edge("person:" + mm, "group:" + gid, "member")
            for r in items:
                edge("group:" + gid, "project:" + r["project"], "item")

        # preps: children of the person or the group they were written for
        for key, ps in preps_by_key.items():
            parent = "group:" + key if ("group:" + key) in seen else "person:" + key if ("person:" + key) in seen else None
            if not parent:
                continue                                  # a slug1+slug2 call with no standing group: shown nowhere on the map yet
            for pr in ps:
                nid = "doc:prep:" + pr["path"]
                node(nid, type="document", parent=parent, label="prep · %s" % pr["call"], href=pr["path"], opens="drawer",
                     summary=[pr.get("purpose") or "call prep", pr["path"]])
                edge(parent, nid, "child")

    # documents, hub 1: the mentee content dashboard's manifest (the pieces with a file)
    man = manifest()
    pieces = [pc for st in man.get("stages", []) for pc in st.get("pieces", []) if pc.get("path")]
    node("doc:mentee", type="document", hub=True, label="Mentee content", href="/mentee", opens="page",
         summary=["%d pieces in program order" % len(pieces), "the dashboard's manifest; double-click to unfold them"])
    held = {}
    for pc in pieces:
        nid = "doc:piece:" + pc["id"]
        canvas = pc["path"].endswith(".canvas")
        node(nid, type="document", parent="doc:mentee", label=pc.get("title") or pc["id"], kind=pc.get("kind"),
             href=("/canvases?open=%s" % urllib.parse.quote(pc["path"])) if canvas else pc["path"], opens="page" if canvas else "drawer",
             summary=[pc["path"], pc.get("kind") or ""])
        edge("doc:mentee", nid, "child")
        pid = project_for(pc["path"])
        if pid:
            edge(nid, "project:" + pid, "under"); held[pid] = held.get(pid, 0) + 1
    for pid, n in held.items():
        for _ in range(n):
            edge("doc:mentee", "project:" + pid, "holds")

    # documents, hub 2: the architecture canvases
    cvs = canvases()
    node("doc:canvases", type="document", hub=True, label="Canvases", href="/canvases", opens="page",
         summary=["%d architecture canvases" % len(cvs), ARCH_REL + "/; double-click to unfold them"])
    held = {}
    for c in cvs:
        nid = "doc:canvas:" + c["path"]
        node(nid, type="document", parent="doc:canvases", label=c["name"], kind="canvas",
             href="/canvases?open=%s" % urllib.parse.quote(c["path"]), opens="page",
             summary=[c.get("header") or c["path"], "%d nodes · %d edges · %s" % (c["nodes"], c["edges"], c.get("mtime") or "")])
        edge("doc:canvases", nid, "child")
        pid = project_for(c["path"])
        if pid:
            held[pid] = held.get(pid, 0) + 1
    for pid, n in held.items():
        for _ in range(n):
            edge("doc:canvases", "project:" + pid, "holds")

    # the team copy: its status file, written by the exporter
    ts_ap = os.path.join(BRAIN, TEAM_STATUS_REL.replace("/", os.sep))
    if os.path.isfile(ts_ap):
        try:
            with open(ts_ap, "r", encoding="utf-8-sig") as f:
                ts = json.load(f)
            member = str(ts.get("member") or "team")
            le, rv, rq, rm = ts.get("last_export") or {}, ts.get("review") or {}, ts.get("requests") or {}, ts.get("remote") or {}
            waiting = int(rq.get("inbox_open") or 0) + int(rm.get("unpushed") or 0) + int(rm.get("behind") or 0)
            node("copy:" + member, type="copy", key=member, label="Team copy · %s" % member, badge=waiting, href="/requests", opens="page",
                 summary=["exported %s · %s files · commit %s" % (str(le.get("at") or "")[:10] or "?", le.get("files", "?"), le.get("brain_commit", "?")),
                          "unpushed %s · behind %s · review look %s / internal %s / fine %s · %s open request%s" % (
                              rm.get("unpushed", "?"), rm.get("behind", "?"), rv.get("look", "?"), rv.get("internal", "?"), rv.get("fine", "?"),
                              rq.get("inbox_open", 0), "" if rq.get("inbox_open") == 1 else "s")])
            for h in holons:
                if h.get("sharing") == "team":
                    edge("copy:" + member, "project:" + h["id"], "shared")
        except Exception as e:
            notes.append("team copy status unreadable: %s" % e)

    if not PROPOSE:
        # chats: the newest conversations; the badge is a running turn
        chats = chats_api()
        by_session = {}
        for c in chats["chats"][:GRAPH_CHATS]:
            nid = "chat:" + c["id"]
            proj = c.get("project") or "main"
            target = "project:brain-central" if proj == "main" and "project:brain-central" in seen else "project:" + proj
            turns = c.get("turns") or 0
            node(nid, type="chat", key=c["id"], label=c.get("title") or c["id"], badge=1 if c.get("running") else 0,
                 href="/chat?chat=%s" % urllib.parse.quote(c["id"]), opens="page", running=bool(c.get("running")),
                 summary=["with %s · %s" % ("the main agent" if proj == "main" else (seen.get("project:" + proj) or {}).get("label", proj),
                                            "a turn is running" if c.get("running") else "%d turn%s" % (turns, "" if turns == 1 else "s")),
                          "last %s · $%.2f so far" % (str(c.get("last") or c.get("created") or "")[:16].replace("T", " "), float(c.get("cost_usd") or 0))])
            edge(nid, target, "chat")
            if c.get("session_id"):
                by_session[c["session_id"]] = nid

        # agents: the sessions active right now (the same reading /agents and the chat strip use)
        for se in agents_api()["sessions"]:
            if not se.get("active"):
                continue
            nid = "agent:" + se["sessionId"]
            cnt = se.get("counts") or {}
            node(nid, type="agent", key=se["id"], label=se.get("title") or se["id"], badge=cnt.get("running", 0),
                 href="/agents?open=%s" % urllib.parse.quote(se["id"]), opens="page",
                 summary=["a Claude Code session in the brain · %s" % (se.get("model") or "model unknown"),
                          "%d sub-agent%s, %d running · idle %s min" % (cnt.get("subagents", 0), "" if cnt.get("subagents") == 1 else "s", cnt.get("running", 0), se.get("minutesIdle"))])
            if se["sessionId"] in by_session:
                edge(nid, by_session[se["sessionId"]], "running")
            elif "project:brain-central" in seen:
                edge(nid, "project:brain-central", "session")     # it runs in the brain root, which is the central agent's ground

    out_edges = [{"source": a, "target": z, "kind": k, "n": n} for (a, z, k), n in edges.items() if a in seen and z in seen]
    counts, ekinds = {}, {}
    for d in nodes:
        counts[d["type"]] = counts.get(d["type"], 0) + 1
    for e in out_edges:
        ekinds[e["kind"]] = ekinds.get(e["kind"], 0) + 1
    return {"generatedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "mode": mode_info()["mode"],
            "nodes": nodes, "edges": out_edges, "counts": counts, "edgeKinds": ekinds,
            "quietPeople": sum(1 for d in nodes if d.get("quiet")), "children": sum(1 for d in nodes if d.get("parent")),
            "propose": PROPOSE, "notes": notes,
            "absent": ["people", "groups", "chats", "agents"] if PROPOSE else []}


def review_counts():
    """How many cards are waiting, for the status file; a failure here must never cost the whole status write."""
    try:
        r = review_api()
        return {"waiting": r["waiting"], "shown": r["shown"], "rated": r["ratedTotal"], "untested": r["untested"]}
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}


def findings_counts():
    """The findings counts for the status file; a failure here must never cost the whole status write."""
    try:
        return findings_api()["counts"]
    except Exception as e:
        return {"_error": "%s: %s" % (type(e).__name__, e)}


def graph_counts():
    """Node counts by type for the status file; a failure here must never cost the whole status write."""
    try:
        return graph_api()["counts"]
    except Exception as e:
        return {"_error": "%s: %s" % (type(e).__name__, e)}


def _adapter_status():
    """The adapter registry as the status file records it: which boundaries exist and how big each
    one's inventory is. Read-only and forgiving -- a registry that will not parse must never stop
    the viewer writing its status file."""
    if adapters is None:
        return {"built": False, "note": "the adapter generator did not load: %s" % _ADAPTER_ERR}
    try:
        listing = adapters.list_adapters(BRAIN)
    except Exception as e:                       # noqa: BLE001
        return {"built": True, "error": "%s: %s" % (type(e).__name__, e)}
    rows = {}
    for r in listing.get("rows") or []:
        row = {"base": r["base"], "catalog": r["catalog"], "manualPorts": r["manualPorts"]}
        try:
            a, err = adapters.adapter_api(r["name"], BRAIN)
            row["ports"] = None if err else a["counts"]["ports"]
            row["groups"] = None if err else a["counts"]["groups"]
            row["hollow"] = None if err else a["counts"]["hollow"]
            row["drift"] = None if err else a["counts"]["drift"]
            row["fetchedAt"] = None if err else (a["fetchedAt"] or None)
            if err:
                row["error"] = err
        except Exception as e:                   # noqa: BLE001
            row["error"] = "%s: %s" % (type(e).__name__, e)
        rows[r["name"]] = row
    return {"built": True, "adapters": rows, "registryError": listing.get("error")}


def write_status():
    try:
        cv = canvases(); m = manifest(); reg = registry(); gl = glossary_api(); qs = quests_api(); st = stages_api()
        pieces = sum(len(st.get("pieces", [])) for st in m.get("stages", []))
        hol = reg.get("holons", [])
        status = {
            "_generatedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "_generatedBy": "skills/brain-viewer/serve.py v%s (on startup)" % VERSION,
            "_note": "machine-written; trust = _generatedAt freshness, never authorship",
            "panels": {
                "mentee-content-dashboard": {"built": True, "route": "/mentee", "pieces": pieces, "stages": len(m.get("stages", []))},
                "canvas-viewer": {"built": True, "route": "/canvases", "canvases": len(cv), "families": sorted({c["family"] for c in cv})},
                "holons": {"built": True, "route": "/holons", "holons": len(hol), "stamped": sum(1 for h in hol if h.get("stamped")), "registryUpdated": reg.get("_updated")},
                "status": {"built": True, "route": "/status", "statusFiles": sum(1 for h in hol if h.get("status"))},
                "today": {"built": True, "route": "/today",
                          "composed": "the ledger sections in the browser from GET /api/projects; the three outside sections from /api/pending, /api/calls and /api/landed, each read at request time and stored nowhere",
                          "sections": ["Waiting on you: every open question addressed to %s across the ledgers, the BLOCKING ones first," % OWNER +
                                      " then the rest newest first, the ones asked more than 7 days ago behind one fold",
                                       "Due today or earlier: open tasks of any owner past or on their due date, held tasks whose day has come, questions carrying a due date",
                                       "Pending in the app: the PF App's action items still awaiting review, folded per conversation (one row a conversation, opened on a press to its items), each item with an approve and a reject press, and an approve-all per conversation behind a confirm",
                                       "Today's calls: context/today-calendar.json as the /start-session recap wrote it, each attendee matched to a people/ card and each call to its dated prep",
                                       "Your open tasks: every open task owned by the owner on every ledger regardless of date, grouped by project, folded past ten per project, each with a done press and a hold; the dated ones above are not repeated. Its foot line counts what the PF App is holding for review",
                                       "Transcripts landed today: the files carrying today's date in transcripts/ and pf-app-holon/transcripts/, with the import-checkup report that means intaken, or nothing yet",
                                       "Closed today, folded: the tasks done today and the questions answered today"],
                          "writes": "the ledgers, through PUT /api/tasks and POST /api/today/tasks/action -> tasks.py (answer, done, reopen, hold); 'not today' is hold with tomorrow's date, the open-tasks block's hold is the tool's own three days. AND the PF App's review queue, through POST /api/pending/action -> POST /api/v1/action-items/:id/status. The calls and transcript sections stay read-only",
                          "canApprove": True,
                          "canApproveWhy": "PF-App commit e43ccbf (2026-09-17) added GET /action-items?status=suggested and POST /action-items/:id/status at the personal-token tier, so the queue can be read and moved from out here; every press is rehearsed with ?dryRun=1 before it is written and leaves one SYNCED line in context/log.md",
                          "deferred": ["server-side composition", "the next call's prep as a timed card on the home page (T-0168)"],
                          "nav": True, "note": "the home page's Waiting on you links here as 'today', carrying the count of the first two sections"},
                "findings": {"built": True, "route": "/findings", "api": "/api/findings",
                             "reads": "every OPEN item carrying a #source: tag on the ledgers the registry names; repeats:N on the item is the same finding raised again",
                             "open": findings_counts(), "sorted": "repeats, then age", "writes": "nothing (read-only queue; it is drained at rounds Step 0.5)",
                             "note": "the findings-routing design of 2026-09-17, piece 5: producers file, rounds and the owner decide. /today is unchanged"},
                "review": {"built": True, "route": "/review", "api": "/api/review (GET the cards, POST one rating -- or a note with no verdict at all)",
                           "kinds": ["closure -- an open #%s item with the evidence beside it" % QUEST_TAG,
                                     "review -- any open item carrying #%s" % REVIEW_TAG],
                           "evidence": "a task on the same ledger, closed on or after the day the test was written, pointing at the same route or file, and never test maintenance: nothing filed by this page (#source:review), nothing whose text starts 'Rewrite test', nothing carrying only a 2026-09-18 rewrite marker, never the item itself",
                           "untested": "an open stale test with no such work behind it is not a card; it is counted (waiting.untested) and run from Today",
                           "waiting": review_counts(), "sitting": REVIEW_SITTING, "staleDays": REVIEW_STALE_DAYS,
                           "ratings": REVIEW_REL + "/<day>.jsonl", "counter": review_counter(),
                           "writes": "tasks.py note on the item; tasks.py done as well when a CLOSURE card is rated good. A POST with no verdict writes the note ALONE -- no ratings line, no state move, the card keeps whatever answer it had",
                           "autoClose": {"bar": REVIEW_BAR, "of": REVIEW_WINDOW, "enforced": REVIEW_ENFORCED},
                           "note": "ledger T-0166, the owner's yes on Q-0018. The bar (18 of the last 20 good) is counted and shown, never acted on: every closure waits for the owner's press"},
                "projects": {"built": True, "route": "/projects", "ledgers": sum(1 for h in hol if h.get("tasks")), "tool": "skills/brain-tasks/tasks.py"},
                "requests": {"built": True, "route": "/requests", "folder": REQUESTS_REL + "/<member>/", "contract": "team-brain-request/1"},
                "agents": {"built": True, "route": "/agents", "api": "/api/agents + /api/session (+ POST /api/chat/adopt)",
                           "sources": ["~/.claude/projects/<brain>/*.jsonl", LOG_REL, "the ledgers the registry names", CHATS_REL],
                           "window": "newest %d sessions within %d days" % (AGENT_SESSIONS_MAX, AGENT_DAYS), "teamCopy": "403 (transcripts stay on this machine)",
                           "nav": True, "draws": "one bubble per conversation or session, its sub-agents as smaller bubbles on lines, the send-to lines between conversations; the list stays below as the detail",
                           "note": "back on the nav 2026-09-10 (T-0117); the home's Running strip is the summary and links here",
                           "adoptQuietSeconds": ADOPT_QUIET_SECONDS},
                "people": {"built": True, "route": "/people", "cards": sum(1 for f in (os.listdir(os.path.join(BRAIN, PEOPLE_REL)) if os.path.isdir(os.path.join(BRAIN, PEOPLE_REL)) else []) if f.endswith(".md") and f != "readme.md"),
                           "preps": len(preps()), "prepFolder": CALLPREP_REL, "format": "skills/call-prep/call-prep-format.md",
                           "questionsFirst": True, "teamCopy": "403 (people/ never travels with a copy)"},
                "badges": {"built": True, "route": "/api/badges", "note": "open items waiting on the owner, per person and per project; the nav counts read it, the bubbles home will too"},
                "chat": {"built": True, "route": "/ (home) + /chat", "index": CHATS_REL + "/<id>.json", "bodies": "~/.claude/projects/<brain path>/<session id>.jsonl (never copied into the brain)",
                         "cli": CLAUDE_BIN, "cliVersion": CLI_VERSION, "models": [m["id"] for m in chat_models() if m["ok"]],
                         "prompts": ["skills/brain-viewer/chat-prompts/main.md", "skills/brain-viewer/chat-prompts/project.md"],
                         "capMinutes": CHAT_TURN_SECONDS // 60, "teamCopy": "403 (chat runs on the owner's machine)"},
                "map": {"built": True, "retired": "2026-09-09", "route": "/map", "api": "/api/graph", "nav": False,
                        "note": "the moving physics graph of 2026-09-09 morning; retired the same evening by the live maps (the owner asked for several maps, each an existing canvas read against real state). The route and /api/graph still answer; the nav item is now maps",
                        "library": "force-graph 1.51.4 (skills/brain-viewer/vendor/force-graph.min.js, MIT, no network at runtime)",
                        "counts": graph_counts()},
                "maps": {"built": True, "route": "/maps (the picker) + /live?path=<canvas> (one map, live)", "api": "/api/maps + /api/live (+ POST /api/live/bindings)",
                         "manifest": MAPS_REL, "groups": [g.get("name") for g in maps_manifest().get("groups", [])],
                         "layers": ["intent (the drawing as drawn)", "build (every node bound to a file, holon, skill, agent, route or service; unbound = concept)", "runtime (lit by the last %d days of the log, mtimes, status files, sessions, the team copy; edges active today carry a gold bubble)" % LIVE_DAYS],
                         "writes": "nothing, except the sibling .forge.json when 'save bindings' is pressed (binding: {kind, target} per node), one log line",
                         "renderer": "forge.html in live mode: the Forge's circular render, read-only",
                         "sources": [LOG_REL, REGISTRY_REL, "skills/*/", "~/.claude/projects/<brain>/*.jsonl (mtimes only)", TEAM_STATUS_REL, "the registry's status files", "file mtimes"]},
                "glossary": {"built": True, "route": "/glossary", "api": "/api/glossary", "seed": GLOSSARY_REL,
                             "terms": len(gl.get("terms", [])), "groups": [x["name"] for x in gl.get("groups", [])],
                             "keys": len(gl.get("keys", [])), "hoverTerms": sum(1 for t in gl.get("terms", []) if t.get("hover")),
                             "nav": "a small link at the right of the bar, plus the ? button on every page",
                             "teamCopy": "available: false (the seed lives in this holon, which does not export)"},
                "questlog": {"built": True, "route": "every page (top right) + the home page's Recently done block", "api": "/api/quests",
                             "tag": "#test on an open %s task" % OWNER, "tests": len(qs["tests"]), "done": qs["doneTotal"],
                             "note": "the ledgers read back: what to test, and the timeline of what is done with a link to what each item produced",
                             "teamCopy": "hidden when the copy carries no #test items"},
                "stageline": {"built": True, "route": "the home page and a project page carrying the milestone", "api": "/api/stages",
                              "milestone": st["milestone"], "steps": st["total"], "done": st["doneCount"], "current": st["current"],
                              "note": "the build order drawn as one line of dots, read from the Straight-line milestone across the ledgers"},
                "reader": {"built": True, "route": "/reader", "api": "/api/docasks",
                           "writes": "a .md under %s, never a *-tasks.md ledger and never %s" % (", ".join(d + "/" for d in READER_DIRS), LOG_REL),
                           "note": "a document opened by its headings: strike and move on every list item, one line rewritten per action, each save logged",
                           "nav": "a small link at the right of the bar, beside glossary; every drawer offers 'open in Reader'"},
                "forge": {"built": True, "route": "/forge", "api": "/api/forge (+ /api/forge/fields, POST /api/forge/new)",
                          "writes": "a .canvas or its .forge.json sibling inside a family folder under %s/, through PUT /api/file, one log line each" % FORGE_ROOT,
                          "canvases": len(cv), "cells": sum(c.get("cells", 0) for c in cv), "withForgeFile": sum(1 for c in cv if c.get("forge")),
                          "note": "the design surface (step 3, part one): cells with a band and a core, typed parts, labelled lines, a palette, an inspector, undo, explicit save; the same renderer draws the live maps read-only at /live (step 4); part two (the agent that reads a drawing) is step 5"},
                "adapters": dict(_adapter_status(), route="/forge?adapter=<name>", api="/api/adapter (+ /api/adapters)",
                                 registry=adapters.REGISTRY_REL if adapters else None,
                                 note="a boundary the brain calls across, in three views of one generated answer (viewer Q-0024): one symbol with its counts wherever it sits on a canvas, its own read-only SHEET at /forge?adapter=<name> (the calling skills on the left, the ports down the middle grouped by resource and by tier, the app's stores on the right), and three counted arcs when it sits inside a cell. Which adapters exist, and any hand-written port groups, live in the registry file; nothing is ever written to a canvas"),
                "flow": {"built": False, "note": "the whole-wiring graph (T-0018) shares /map's renderer when it comes; /map is the first physics graph"},
                "files": {"built": True, "route": "/files", "api": "/api/files (+ /api/file-raw for downloads)",
                          "note": "every file in the brain in one sortable table, newest first, with the last log line naming each; the folder tree and type chips filter; a row opens beside the table (0.53.0), in the lightbox, in the canvas viewer, or downloads (0.52.0, T-0259)",
                          "excluded": sorted(FILES_SKIP_DIRS) + ["the key files", "*_key.txt"]},
            },
            "design": {"tokens": "skills/brain-viewer/looks/default.css", "looks": "skills/brain-viewer/looks/", "note": "the 33 tokens live in looks/default.css and a look file in that folder overrides them per member (0.41.0, T-0208); viewer-tokens.css is the stylesheet that reads them"},
            "process": {"startedAt": STARTED_AT.isoformat(timespec="seconds"), "pid": os.getpid(),
                        "supervised": bool(os.environ.get("BV_SUPERVISED")), "health": "/api/health",
                        "crashLog": CRASH_REL, "lastExit": last_exit(), "previousRun": PREV_RUN,
                        "note": "every exit appends one dated record to the crash log (T-0181); lastExit is the newest EXIT or RESTART in it, or null when nothing has ever been recorded, and its `crash` says whether that ending was a fault rather than a reload (a killed child leaves no traceback, a thrown one does). A viewer started with --supervise puts itself back when it exits non-zero"},
            "server": {"bind": getattr(ARGS, "host", "127.0.0.1") if "ARGS" in globals() else "127.0.0.1", "version": VERSION, "mode": mode_info()["mode"], "member": MEMBER,
                       "writes": "requests/<member>/ only (propose mode)" if PROPOSE else "manifest-scoped, logged via log.py as agent brain-viewer"},
        }
        ap = os.path.join(BRAIN, STATUS_REL.replace("/", os.sep))
        if not os.path.isdir(os.path.dirname(ap)):
            return  # brain-viewer-holon/ is a private holon and may be absent from a team copy: no status file there, silently
        with open(ap, "w", encoding="utf-8", newline="\n") as f:
            json.dump(status, f, ensure_ascii=False, indent=1); f.write("\n")
    except Exception as e:
        sys.stderr.write("status write failed: %s\n" % e)


def log_line(text, action="MODIFIED"):
    """One line in context/log.md through log.py (the clock is read at write time). BRAIN_ROOT is passed so a copy logs into
    its own context/log.md, never into the hard-coded canonical path; a copy without a log skips (the request file is the record)."""
    if not os.path.isfile(os.path.join(BRAIN, LOG_REL.replace("/", os.sep))):
        return "not logged: no %s in this copy" % LOG_REL
    try:
        r = subprocess.run([sys.executable, os.path.join(CODE, "skills", "brain-log", "log.py"), "--append",
                            "--agent", "brain-viewer", "--action", action, "--text", text],
                           cwd=BRAIN, capture_output=True, text=True, timeout=30, env=dict(os.environ, BRAIN_ROOT=BRAIN))
    except Exception as e:
        return "log.py failed: %s" % e
    if r.returncode != 0:
        return "log.py refused: %s" % (r.stderr or r.stdout).strip()[:200]
    return "logged"



# ---- the day's three outside halves (2026-09-16, ledger T-0150, second stretch) ----
# The Today page's first three sections are the ledgers read back in the browser and need no server. These three are the
# parts of a day that do NOT live in a ledger: what the PF App is holding for review, what is on the calendar, and what
# landed in the transcript folders. Each is READ at request time and stored nowhere (rules 1 and 2); the calendar is the
# one that needs a file, because the calendar itself is only reachable through the Claude Code MCP tool and the server
# has no path to it -- so the /start-session recap writes what it already read, and this reads that file.

# WHAT THE API OFFERS FOR ACTION ITEMS, re-checked 2026-09-18 against the catalog (`_fetchedAt` 2026-09-18) and
# exercised against the live app with `?dryRun=1` the same day, because this section now ACTS as well as lists:
#   GET  /api/v1/action-items?status=suggested   personal token -- THE REVIEW QUEUE ITSELF. Scope: the caller's own
#                                                items plus items on conversations the caller owns. Each one carries
#                                                conversationId, conversationTitle, status, approvalStatus, owner,
#                                                due and createdAt. 504 items over 61 conversations when this was built.
#   POST /api/v1/action-items/:id/status         personal token -- {"status": "approved" | "rejected"}, the same
#                                                storage call the in-app review panel makes (an approved item becomes a
#                                                real task, and an assigned one transfers to its assignee). 400 on a bad
#                                                body, 404 when the item is not visible, 403 when it is visible but
#                                                owned by someone else, 409 when it is already in that status, and
#                                                `?dryRun=1` rehearses any of it without writing.
# Both arrived with PF-App commit e43ccbf (2026-09-17) and its republish. What stood here until 2026-09-18 -- that the
# API has no approve or reject route and that GET /action-items answers with approved items alone -- was true of the app
# as it was and is false of the app as it is, so it is gone rather than softened.
#
# THE ADMIN KEY IS NOT USED HERE. The old read went out on `pfk_` with `?userId=`; the queue is the caller's own work, so
# it goes out on the personal token like every other Today read, and the write could not be admin even in principle --
# the viewer acts as the owner, never across users.
PENDING_NOTE = ("Approve and reject write to the app through its action-item status route, on your own token -- the same "
                "call the app's own review panel makes. Approving turns the item into a real task.")
PENDING_TTL = 60                 # the queue moves when a transcript is pushed or a press lands, not between two paints
_pending = {"at": 0.0, "row": None}


def pending_fold(items):
    """504 suggested items over 61 conversations -- so the page is given CONVERSATIONS, each with its items inside it,
    never a flat list. Newest conversation first (by its newest item), newest item first inside one."""
    by = {}
    for i in items:
        cid = str(i.get("conversationId") or i.get("documentId") or "") or "none"
        title = str(i.get("conversationTitle") or i.get("documentTitle") or "") or "no record named"
        g = by.get(cid)
        if g is None:
            g = by[cid] = {"id": cid, "title": clip(title, 160),
                           "kind": "meeting" if i.get("conversationId") else ("document" if i.get("documentId") else ""),
                           "items": []}
        g["items"].append({"id": str(i.get("id") or ""), "text": clip(str(i.get("description") or ""), 300),
                           "owner": str(i.get("owner") or "") or None, "due": str(i.get("due") or "")[:10] or None,
                           "at": str(i.get("createdAt") or "")[:10], "state": str(i.get("status") or ""),
                           "review": str(i.get("approvalStatus") or "")})
    out = []
    for g in by.values():
        g["items"].sort(key=lambda x: (x["at"], x["id"]), reverse=True)
        g["count"] = len(g["items"])
        g["newest"] = g["items"][0]["at"] if g["items"] else ""
        out.append(g)
    out.sort(key=lambda g: (g["newest"], g["count"]), reverse=True)
    return out


def pending_api(force=False):
    """The PF App's action items still waiting for review, folded per conversation. The transcript pushes are what create
    them (a pushed `## Action Items` line lands as approvalStatus `suggested`), which is why they belong on the day.

    Cached PENDING_TTL seconds, and what a press writes is taken out of the cache on the spot, so the list a page paints
    is never behind a write this server itself made. The token is read inside app_get and never leaves the process."""
    now = time.time()
    if not force and _pending["row"] and (now - _pending["at"]) < PENDING_TTL:
        row = dict(_pending["row"]); row["cached"] = True
        return row
    row = {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "source": APP_BASE + "/action-items?status=suggested",
           "app": APP_BASE.rsplit("/api/", 1)[0] + "/action-items", "canApprove": True, "note": PENDING_NOTE,
           "conversations": [], "count": 0, "groups": 0, "read": 0, "cached": False, "ttlSeconds": PENDING_TTL}
    try:
        j = app_get("action-items", "personal", query={"status": "suggested"}) or {}
        items = [i for i in (j.get("actionItems") or []) if isinstance(i, dict)]
        row["read"] = len(items)
        live = [i for i in items if not i.get("deletedAt") and not i.get("archivedAt")
                and str(i.get("approvalStatus") or "").strip().lower() in ("suggested", "pending", "pending_review")]
        row["conversations"] = pending_fold(live)
        row["count"] = len(live)
        row["groups"] = len(row["conversations"])
    except Exception as e:                       # noqa: BLE001 -- the page says the app did not answer; it never invents a queue
        row["error"] = "%s: %s" % (type(e).__name__, e)
    _pending.update(at=now, row=dict(row))
    return row


def pending_drop(iid):
    """A press landed: take that item out of what is cached rather than asking the app for 504 rows again, and move the
    foot count with it. The next read past the cache rebuilds both from the app anyway."""
    row = _pending["row"]
    if row and iid:
        gone, keep = 0, []
        for g in row.get("conversations") or []:
            before = len(g["items"])
            g["items"] = [i for i in g["items"] if i["id"] != iid]
            gone += before - len(g["items"])
            g["count"] = len(g["items"])
            if g["items"]:
                keep.append(g)
        row["conversations"] = keep
        row["count"] = max(0, row.get("count", 0) - gone)
        row["groups"] = len(keep)
    if _suggested["row"] and isinstance(_suggested["row"].get("count"), int):
        _suggested["row"]["count"] = max(0, _suggested["row"]["count"] - 1)


PENDING_WHY = {400: "the app refused the body",
               403: "that item is on a conversation you can see, but it belongs to someone else",
               404: "the app does not show you that item any more -- it may already be approved, rejected or gone",
               409: "it is already in that state; the page was out of date"}


def pending_act(iid, action):
    """One press on an item of the review queue: approve or reject, straight to the app. -> (status code, body).

    The Ferryman's law on an app write (pf-app-holon/pf-app-ferryman-rules.md): REHEARSE FIRST. Every press goes out
    twice -- `?dryRun=1`, which validates and reports without writing, and then for real only if the rehearsal came back
    2xx. So a 404, a 403 and a 409 each reach the page as a plain sentence with NOTHING written. Every real write leaves
    one SYNCED line in context/log.md through log.py (the clock is read in the same call that writes)."""
    want = {"approve": "approved", "approved": "approved",
            "reject": "rejected", "rejected": "rejected"}.get(str(action or "").strip().lower())
    if not want:
        return 400, {"error": "an item here is approved or rejected, nothing else"}
    iid = str(iid or "").strip()
    if not iid:
        return 400, {"error": "no action item named"}
    if PROPOSE:
        return 403, {"error": "a team copy does not write to the PF App: the proxy is off and no token file is read here"}
    try:
        code, dry = app_post("action-item-status", (iid,), {"status": want}, dry=True)
    except Exception as e:                       # noqa: BLE001
        return 502, {"error": "the app could not be reached: %s" % e}
    if code >= 300:
        return code, {"error": PENDING_WHY.get(code) or "the app answered %s" % code, "id": iid, "status": want,
                      "dryRun": True, "app": (dry.get("error") if isinstance(dry, dict) else None)}
    item = (dry.get("actionItem") if isinstance(dry, dict) else None) or {}
    title = str(item.get("conversationTitle") or item.get("documentTitle") or "none named")
    try:
        code, out = app_post("action-item-status", (iid,), {"status": want})
    except Exception as e:                       # noqa: BLE001
        return 502, {"error": "the rehearsal passed and the write itself could not be sent: %s" % e}
    if code >= 300:
        return code, {"error": "%s (the rehearsal had passed, so the item moved underneath the press)"
                               % (PENDING_WHY.get(code) or "the app answered %s" % code), "id": iid, "status": want}
    pending_drop(iid)
    logged = log_line("PF App: action item %s %s from /today (conversation %s)" % (iid, want, title), action="SYNCED")
    return 200, {"ok": True, "id": iid, "status": want, "conversation": title, "logged": logged,
                 "message": "%s in the app" % want, "app": out if isinstance(out, dict) else {"body": str(out)[:200]}}


# ---- the owner's open tasks, all of them, regardless of date (2026-09-18, ledger T-0185; layout A on Q-0023) ----
# On 9/17 the owner asked for those tasks to be clickable in the Today area, and for that working area to be more
# dynamic. The Today page only ever showed DATED work, so the open tasks of the owner's that carry no `due:` -- the
# Replit republish, the seven Asprey items, the forty-odd unticked tests -- never reached the page he actually opens.
# This is the third block: every open task of the owner's across every registered ledger, grouped by project in the registry's
# own order, newest first inside a group, with one press to close it and one to put it down for three days.
#
# Read at request time from open_for_zak() -- the SAME rows the home block, the nav counts and the people pages read, so
# there is no second definition of "open for the owner" anywhere (rules 1 and 2) and a hold made on any page takes it off this
# one too. Nothing is stored. The counts the page prints are derived here rather than in the browser, so the block's
# foot and its group headings cannot disagree with what was actually sent.
TODAY_TASKS_FOLD = 10          # per project; the rest sit behind a "N more" press


def today_dated(it, today):
    """True when the Today page's `Due today or earlier` block already shows this item, so this block must not repeat it.

    The same predicate dayModel() applies in viewer-common.js: a day that has arrived or gone by, or a hold whose day has
    come (it reads as `back today` up there). Dedupe is by ledger + id, and this is the rule that decides which of the
    two blocks owns a row."""
    due, until = it.get("due"), it.get("until")
    return bool((due and due <= today) or (until and until <= today))


def today_tasks_api():
    """Every OPEN task of the owner's, on every ledger the registry names, grouped by project in the registry's order.

    `total` is all of them; `shown` is what this block holds once the dated ones are left to the block above it and the
    CALL-SCOPED ones are left to their call preps (`calls`, and `callPeople` per person). A task on hold is not here at
    all -- open_for_zak() holds it back until its day, which is what the hold press is for."""
    today = ledger.today()
    try:
        refd = dt.date.fromisoformat(today)
    except ValueError:
        refd = dt.date.today()
    rows = [r for r in open_for_zak() if r["kind"] == "task" and r["mark"] == " " and r["owner"] == OWNER]
    order, groups = [], {}
    for h in registry().get("holons", []):
        if h.get("tasks"):
            order.append(h["id"])
            groups[h["id"]] = {"project": h["id"], "name": h.get("name") or h["id"], "path": h["tasks"], "items": []}
    dated = 0
    # A CALL-SCOPED ITEM IS NOT TODAY'S WORK (2026-09-18, T-0192). The owner asked that anything relevant to a call stay
    # out of the today tasks and sit inside that call's prep, unless it needs clarifying first, and the same for every
    # other call. An item carrying `#call:<slug>` is still open and
    # still owed -- it is simply owed on that person's next call, so it leaves this block and their call prep's Carried
    # section picks it up (skills/call-prep/call-prep-format.md). Counted here, per person, for the line at the foot.
    calls = {}
    for r in rows:
        if r.get("call"):
            calls[r["call"]] = calls.get(r["call"], 0) + 1
            continue
        if today_dated(r, today):
            dated += 1
            continue
        g = groups.get(r["project"])
        if g is None:
            g = groups[r["project"]] = {"project": r["project"], "name": r["projectName"], "path": r["projectPath"], "items": []}
            order.append(r["project"])
        g["items"].append({"id": r["id"], "text": r["text"], "created": r["created"], "due": r.get("due"),
                           "note": r.get("note"), "milestone": r.get("milestone"), "tags": r.get("tags") or [],
                           "links": r.get("links") or [], "people": r.get("people") or [],
                           "age_days": days_since(r.get("created"), refd),
                           "project": r["project"], "projectName": r["projectName"], "ledger": r["projectPath"]})
    out = []
    for pid in order:
        g = groups[pid]
        if not g["items"]:
            continue
        g["items"].sort(key=lambda i: (i["created"], i["id"]), reverse=True)     # newest first inside a group
        g["count"] = len(g["items"])
        out.append(g)
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": today, "owner": OWNER,
            "fold": TODAY_TASKS_FOLD, "groups": out, "total": len(rows), "shown": sum(g["count"] for g in out),
            "dated": dated, "calls": sum(calls.values()),
            "callPeople": [{"slug": s, "count": n} for s, n in sorted(calls.items(), key=lambda kv: (-kv[1], kv[0]))]}


# WHAT THE APP IS HOLDING FOR REVIEW, as one number at the foot of that block. On Q-0023 the owner raised the crossover
# between this and the PF App's tasks, which will eventually have to be merged. The count is that crossover made visible while the merge is still a design question: it
# says how big the other pile is and links to it. Nothing here approves or rejects anything -- that is T-0017, and the
# v1 API has no route for either (see PENDING_NOTE above).
# `?status=suggested` on the PERSONAL token answers with the review queue -- 504 items when this was written, 2026-09-18
# -- which is a DIFFERENT read from the one /api/pending makes (admin key, `?userId=`, and the app filters that one down
# to what is already approved). Cached ten minutes: the number moves when a transcript is pushed, not between two paints
# of a page. The token is read inside app_get and never leaves this process.
APP_SUGGESTED_TTL = 600
_suggested = {"at": 0.0, "row": None}


def app_suggested(force=False):
    now = time.time()
    if not force and _suggested["row"] and (now - _suggested["at"]) < APP_SUGGESTED_TTL:
        row = dict(_suggested["row"]); row["cached"] = True
        return row
    row = {"count": None, "app": APP_BASE.rsplit("/api/", 1)[0] + "/action-items", "cached": False,
           "readAt": dt.datetime.now().isoformat(timespec="seconds"), "ttlSeconds": APP_SUGGESTED_TTL}
    try:
        if PROPOSE:
            raise RuntimeError("the PF App proxy is off in a team copy")
        j = app_get("action-items", "personal", query={"status": "suggested"}) or {}
        items = [i for i in (j.get("actionItems") or []) if isinstance(i, dict)]
        row["read"] = len(items)
        row["count"] = len([i for i in items if not i.get("deletedAt") and not i.get("archivedAt")])
    except Exception as e:                       # noqa: BLE001 -- the line says the app did not answer; it never guesses a number
        row["error"] = "%s: %s" % (type(e).__name__, e)
    _suggested.update(at=now, row=dict(row))
    return row


def today_task_act(which, iid, action):
    """One press on a row of that block: `done` or `hold`. -> (status code, body).

    The ledger is named BY THE REGISTRY, never by the caller: `which` is matched against the registered holon ids and
    their ledger paths, so no path can be sent in here. The item is RE-READ off the file before anything is written --
    the page may have been open for an hour and the row may already be closed, held, or moved to another owner -- and
    only an open task of the owner's is acted on. tasks.py does the write, takes the day off the clock and appends the one
    context/log.md line itself (agent `brain-viewer`); nothing is logged a second time from here."""
    if action not in ("done", "hold"):
        return 400, {"error": "a row here is done or held, nothing else"}
    if PROPOSE:
        return 403, {"error": "a team copy does not close the owner's items: send a request instead"}
    want = str(which or "").replace("\\", "/").strip()
    hit = next((h for h in registry().get("holons", []) if h.get("tasks") and want in (h["id"], h["tasks"])), None)
    if not hit:
        return 400, {"error": "no registered ledger answers to %r" % want}
    rel = hit["tasks"]; path = os.path.join(BRAIN, rel.replace("/", os.sep))
    try:
        parsed = ledger.parse(ledger.read(path))
        it = next((x for x in parsed["items"] if x["id"] == str(iid or "").strip()), None)
    except Exception as e:                       # noqa: BLE001
        return 500, {"error": "could not read %s: %s" % (rel, e)}
    if it is None:
        return 404, {"error": "%s is not on %s" % (iid, rel)}
    if it["kind"] != "task":
        return 400, {"error": "%s is a question; a question is answered, not closed here" % it["id"]}
    if it["owner"] != OWNER:
        return 400, {"error": "%s belongs to %s, not to you" % (it["id"], it["owner"])}
    if it["mark"] != " ":
        return 409, {"error": "%s is %s already; the page was out of date" % (it["id"], it["state"])}
    if action == "hold" and ledger.is_held(it):
        return 409, {"error": "%s is already down until %s" % (it["id"], it["until"])}
    try:
        # `note` rides along exactly as the command line would carry it (`--note "done in the viewer, <day>"`).
        # tasks.py's `done` and `hold` do not write a note onto the item, so what records the press is the line
        # tasks.py logs itself: agent `brain-viewer`, the day off the clock, one line per write.
        ledger.apply(path, rel, action, agent="brain-viewer", id=it["id"],
                     note="%s in the viewer, %s" % (action, ledger.today()),
                     until=None)                 # no date: the tool's own three days (T-0108)
    except ledger.LedgerError as e:
        return 400, {"error": str(e)}
    return 200, {"ok": True, "id": it["id"], "ledger": rel, "project": hit["id"], "action": action,
                 "message": "%s %s" % (it["id"], "done" if action == "done" else "down for three days")}


_card_names = {"t": 0.0, "index": {}}    # the name index below, held for a few seconds (0.39.0)


def card_name_index():
    """{a spelling -> the card's slug} for every people/ card, held for ten seconds. A week of calls asks the same
    question once per event, and each miss costs the first line of fifty cards; the window is short enough that a card
    added mid-session is seen on the next minute's tick."""
    now = time.time()
    if _card_names["index"] and now - _card_names["t"] < 10:
        return _card_names["index"]
    cards = {}
    root = os.path.join(BRAIN, PEOPLE_REL)
    for fn in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if not fn.endswith(".md") or fn == "readme.md":
            continue
        slug = fn[:-3]
        cards[slug] = slug
        try:
            with open(os.path.join(root, fn), "r", encoding="utf-8-sig") as f:
                head = f.readline().strip()
            nm = re.sub(r"^#+\s*", "", head).split("—")[0].split("--")[0].strip().lower()
            if nm:
                cards.setdefault(nm, slug)
        except Exception:
            pass
    _card_names["t"], _card_names["index"] = now, cards
    return cards


def event_slugs(names):
    """Attendee names -> people/ card slugs. The card is the truth about who exists (Correction #42): a name with no card
    comes back as itself and marked, never invented into a slug that points at nothing."""
    cards = card_name_index()
    me = OWNER.lstrip("@").lower()
    out = []
    for n in names:
        n = str(n or "").strip()
        if not n:
            continue
        low = n.lower()
        slug = cards.get(low) or cards.get(re.sub(r"[^a-z0-9]+", "-", low).strip("-"))
        # the owner is on every call of his own and has no card in people/ (the cards are other people, Correction #42),
        # so he is marked rather than reported as a missing card. `me` comes from the `owner` setting, not from a name
        # typed in here.
        mine = not slug and (low == me or low.split(" ")[0] == me)
        out.append({"name": n, "slug": slug, "card": ("%s/%s.md" % (PEOPLE_REL, slug)) if slug else None, "self": mine})
    return out


def group_members():
    """{group id -> set of member slugs} from the declared call threads, which the prep matcher needs to know that a
    call whose attendees are exactly a thread's members is that thread's call."""
    return {str(g.get("id") or ""): set(str(m) for m in (g.get("members") or []))
            for g in (load_groups().get("groups") or []) if g.get("id")}


def name_slug(name):
    """An attendee's name as a prep file key: first-last, lowercase, hyphens ("Nathan Story" -> "nathan-story")."""
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").strip().lower()).strip("-")


def event_match_keys(who):
    """The keys a call's preps are matched on (0.49.0, T-0248): each carded attendee's slug, and each attendee with NO
    card by name slugified, so a prep written for someone before their card exists still attaches to the call (9/24:
    nathan-story-call-prep-2026-09-24.md sat unmatched until the card was written). The owner is never a key. Only the
    MATCH uses the name; the event's `people` rows still say plainly that the card is missing."""
    keys = set()
    for w in who or []:
        if w.get("slug"):
            keys.add(w["slug"])
        elif not w.get("self"):
            k = name_slug(w.get("name"))
            if k and "@" not in str(w.get("name") or ""):
                keys.add(k)
    return keys


def preps_for_event(slugs, day_preps, gmembers):
    """THE ONE PREP MATCHER (0.39.0). Which of that day's preps belong to a call whose attendees resolve to `slugs`.
    A prep's file key is a person slug, a declared group id, or slugs joined by +, so a prep matches when its key is
    one of the people on the call, when it is a thread every one of whose members is on the call, or when every slug in
    a joined key is on the call. The MOST SPECIFIC prep then wins: a prep whose people are a strict subset of another
    matched prep's people is dropped for that event (2026-09-21 -- the team thread, John + Dani, is a subset of the
    Mike four-way's attendees, so the four-way was matching the team prep as well as its own).

    It lived inside calls_api until the home board's Next asked the same question about a call LATER in the week, which
    is answered from the week file; one rule in one place, so today's answer and Thursday's answer cannot differ."""
    slugs = set(slugs or [])
    keys = set(slugs)
    for gid, mem in (gmembers or {}).items():
        if mem and mem <= slugs:
            keys.add(gid)
    hits = [p for p in day_preps
            if p["key"] in keys or ("+" in p["key"] and set(p["key"].split("+")) <= slugs)]

    def _members(p):
        k = p["key"]
        return set((gmembers or {}).get(k) or (k.split("+") if "+" in k else [k]))

    return [p for p in hits if not any(_members(p) < _members(q) for q in hits if q is not p)]


def event_day_preps(e, day, by_day):
    """The preps a calendar event can match: those dated its day, plus those dated its `originalDate` when the calendar
    writer recorded one (0.52.1, 2026-09-29). A moved occurrence of a recurring meeting keeps the prep written for the
    day it was first set on; the team call Dani moved from 9/28 to 9/29 is the case."""
    out = list(by_day.get(day) or [])
    orig = str((e or {}).get("originalDate") or "")[:10]
    if orig and orig != day:
        out += [p for p in (by_day.get(orig) or []) if p not in out]
    return out


def prep_rows(hits):
    """A matched prep as the pages read it: where it is, which call it is keyed to, and what it says it is for."""
    return [{"path": p["path"], "key": p["key"], "call": p["call"], "purpose": p["purpose"]} for p in hits]


def event_links(e):
    """The two optional links a calendar event carries (0.47.0, T-0168): `join`, the meeting's join URL (Google Calendar's
    conferenceData entry point, the MCP tool's `conferenceUrl`), and `calendarLink`, the event itself in Google Calendar
    (`htmlLink`). Only an http(s) URL is passed through; anything else is dropped rather than put into a link."""
    out = {}
    for k in ("join", "calendarLink"):
        v = str((e or {}).get(k) or "").strip()
        out[k] = v if re.match(r"^https?://", v, re.I) else None
    return out


def read_calendar_file(rel):
    """One calendar file read as JSON: (data, error). A missing file is (None, None)."""
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    if not os.path.isfile(ap):
        return None, None
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            return json.load(f), None
    except Exception as e:                                        # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)


def calls_api():
    """Today's calls, and whether each one has a prep. The calendar is reachable only through the Claude Code MCP tool,
    so the recap that already reads it at the start of a session writes what it saw into context/today-calendar.json and
    this renders THAT -- never a second calendar, never a guess. An absent or out-of-date file says so plainly.

    WHICH FILE ANSWERS (0.47.0, T-0224). The night agent writes context/week-calendar.json at 21:00 for the next seven
    days, so on a morning with no session yet the today file is yesterday's while the week file already holds today.
    The order: (1) the today file when it is dated today; (2) otherwise the week file, when its window (`from`..`to`, or
    failing that the days its events carry) includes today -- today's events are the ones whose date is today, and an
    empty list then means a quiet day, not missing data; (3) otherwise the today file as it stands. `answeredBy` names
    the file that answered; `file` stays the today file's path for the pages that already read it.

    THE STALE FLAG keeps its meaning: `stale` is true only when the file that answered was written for another day
    (case 3 with a today file dated elsewhere). The week file answering is not stale, because it was written for a
    window that contains today. `exists` is whether the answering file exists at all; `for` is the day it answered for."""
    today = ledger.today()
    rel = CALENDAR_REL
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    row = {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": today, "file": rel,
           "answeredBy": None, "exists": os.path.isfile(ap), "for": None, "stale": False, "events": [], "count": 0,
           "withPrep": 0, "prepFolder": CALLPREP_REL, "writtenBy": "the /start-session recap"}
    data, err = read_calendar_file(rel)
    if err:
        row["error"] = err
    raw = None
    if data is not None and str(data.get("date") or "") == today:
        raw, row["answeredBy"], row["for"] = data.get("events") or [], rel, today
        row["writtenAt"] = str(data.get("writtenAt") or "") or None
    else:
        wk, werr = read_calendar_file(CALENDAR_WEEK_REL)
        if wk is not None:
            evs = [e for e in (wk.get("events") or []) if isinstance(e, dict)]
            days = sorted(set((str(e.get("date") or "")[:10] or str(e.get("start") or "")[:10]) for e in evs))
            lo = str(wk.get("from") or "")[:10] or (days[0] if days else "")
            hi = str(wk.get("to") or "")[:10] or (days[-1] if days else "")
            if lo and hi and lo <= today <= hi:
                raw = [e for e in evs if (str(e.get("date") or "")[:10] or str(e.get("start") or "")[:10]) == today]
                row.update(answeredBy=CALENDAR_WEEK_REL, exists=True, **{"for": today},
                           writtenAt=str(wk.get("writtenAt") or "") or None, writtenBy="the night agent's week file")
                row.pop("error", None)
        if raw is None and data is not None:
            raw, row["answeredBy"] = data.get("events") or [], rel
            row["for"] = str(data.get("date") or "") or None
            row["stale"] = bool(row["for"] and row["for"] != today)
            row["writtenAt"] = str(data.get("writtenAt") or "") or None
    if raw is None:
        return row
    by_day = {}
    for p in preps():
        by_day.setdefault(p["call"], []).append(p)
    gmembers = group_members()
    for e in raw:
        if not isinstance(e, dict):
            continue
        who = event_slugs([a.get("name") if isinstance(a, dict) else a for a in (e.get("attendees") or [])])
        hits = preps_for_event(event_match_keys(who), event_day_preps(e, row["for"] or today, by_day), gmembers)
        ev = {"title": str(e.get("title") or "(untitled)"), "start": str(e.get("start") or ""),
              "end": str(e.get("end") or ""), "organizer": str(e.get("organizer") or "") or None,
              "people": who, "noCard": [w["name"] for w in who if not w["slug"] and not w["self"]],
              "preps": prep_rows(hits)}
        ev.update(event_links(e))
        row["events"].append(ev)
    row["events"].sort(key=lambda e: (e["start"], e["title"]))
    row["count"] = len(row["events"])
    row["withPrep"] = sum(1 for e in row["events"] if e["preps"])
    return row


# ---- the call screen (0.47.0, 2026-09-23; ledger T-0168, T-0202 part 4, T-0206) ----
# On 9/23, after the 09:00 team call was joined with no way to reach its prep from the home page, the owner asked for a
# place to click on the call, without drop-down menus for the questions and with fewer things to click on. So /call is ONE flat page over the same prep file the
# Reader opens: who is on the call as cards, what is due, the questions as boxes to tick, the points per person, the
# notes box. Nothing is folded. The page reads GET /api/call and writes only two things back into the prep file, through
# the two POSTs below: a tick (`- [x]` on that one line) and the notes section. Same file, so the Reader shows both.
CALL_REF_RE = re.compile(r"\b(?:(pf-build|asprey|brain-central|brain-viewer|viewer|pf-app|onboarding)\s+)?([TQ]-\d{4})\b")
CALL_ITEM_RE = re.compile(r"^(\s*)[-*]\s+(?:\[( |x|X)\]\s+)?(.*)$")
CALL_NOTES_RE = re.compile(r"^##\s+(?:\d+\.\s*)?Your notes\b", re.I)
CALL_LOG_EVERY = 600          # seconds: ticks and note saves on one prep log one line per ten minutes, not one per press
_call_logged = {}


def prep_rel_ok(rel):
    """A dated prep directly inside deliverables/call-prep/, the only files the call screen reads or writes."""
    rel = str(rel or "").replace("\\", "/").strip()
    if not rel.startswith(CALLPREP_REL + "/") or ".." in rel:
        return None
    if not PREP_FILE_RE.match(rel[len(CALLPREP_REL) + 1:]):
        return None
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    return ap if os.path.isfile(ap) else None


def call_aliases():
    """The words a prep writes in front of an id to say which ledger it is on ("asprey T-0008", "brain-central Q-0015"),
    mapped to the registry's project ids."""
    out = {}
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        pid = h["id"]
        out[pid] = pid
        if pid.endswith("-holon"):
            out[pid[:-6]] = pid
    out.setdefault("viewer", "brain-viewer-holon")
    out.setdefault("onboarding", "onboarding-mirror")
    return out


def call_ledger_index():
    """({project id: {item id: item}}, {ledger path: project id}) over every registered ledger, parsed by the tasks tool."""
    idx, paths = {}, {}
    for h in registry().get("holons", []):
        rel = h.get("tasks")
        if not rel:
            continue
        ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:                                         # noqa: BLE001
            continue
        idx[h["id"]] = {i["id"]: i for g in p["order"] for i in p["groups"][g]}
        paths[rel] = h["id"]
    return idx, paths


def call_refs(text, default_project, idx=None):
    """Every ledger id in the prep, resolved to the item it names: {"<project>/<id>": {id, project, kind, state, words,
    href}}. A prefixed id goes to that ledger; a bare one to the prep's own ledger (the first ledger in its sources), and
    failing that to the one ledger that carries it. An id that resolves nowhere is left out and the page says so."""
    if idx is None:
        idx, _ = call_ledger_index()
    al = call_aliases()
    out = {}
    for m in CALL_REF_RE.finditer(text or ""):
        pre, iid = m.group(1), m.group(2)
        pid = None
        if pre:
            want = al.get(pre)
            pid = want if want in idx and iid in idx[want] else None
        elif default_project in idx and iid in idx[default_project]:
            pid = default_project
        else:
            hits = [p for p in idx if iid in idx[p]]
            pid = hits[0] if len(hits) == 1 else None
        if not pid:
            continue
        it = idx[pid][iid]
        words = re.sub(r"\*\*|__|`|\[\[|\]\]", "", str(it.get("text") or "")).split()
        kind = "q" if it.get("kind") == "question" else "t"
        out["%s/%s" % (pid, iid)] = {"id": iid, "project": pid, "kind": it.get("kind"), "state": it.get("state"),
                                     "words": " ".join(words[:8]) + (" …" if len(words) > 8 else ""),
                                     "href": "/projects?id=%s#%s-%s-%s" % (urllib.parse.quote(pid), kind,
                                                                           urllib.parse.quote(pid), urllib.parse.quote(iid))}
    return out


def _notes_split(body):
    """The notes section's leading HTML comment (the skeleton's instruction) and the text under it."""
    comments, i, open_c = [], 0, False
    while i < len(body):
        l = body[i]
        if open_c:
            comments.append(l)
            open_c = "-->" not in l
        elif not l.strip():
            pass
        elif l.lstrip().startswith("<!--"):
            comments.append(l)
            open_c = "-->" not in l
        else:
            break
        i += 1
    return comments, body[i:]


def parse_prep(text):
    """A prep file as the call screen draws it. Every question keeps its line number in the file, so a tick can go back
    to it. kind per `##`: due | questions | points | notes | bring | other. v3 is `## Questions` (or `## Questions by
    subject`) with a `###` per subject; a v2 prep's questions are the `###` blocks under `## 4. Bring` whose title starts
    with Questions, and the rest of a v2 prep is kept as flat sections."""
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    fm, _ = split_fm(text)
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, min(len(lines), 200)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    title, intro, sections, cur = "", [], [], None
    for n in range(start, len(lines)):
        l = lines[n]
        if l.startswith("# ") and not title and cur is None:
            title = l[2:].strip()
            continue
        if l.startswith("## "):
            name = l[3:].strip()
            bare = re.sub(r"^\d+\.\s*", "", name).lower()
            kind = ("notes" if CALL_NOTES_RE.match(l) else "due" if bare.startswith("due") else
                    "questions" if bare.startswith("questions") else "points" if bare.startswith("points per person") else
                    "bring" if bare.startswith("bring") else "other")
            cur = {"title": name, "kind": kind, "start": n, "lines": []}
            sections.append(cur)
            continue
        if cur is None:
            intro.append(l)
        else:
            cur["lines"].append((n, l))

    def items_of(rows):
        """Top-level bullets with their indented continuation lines; the bullet's file line is the item's address."""
        out, it = [], None
        for n, l in rows:
            m = CALL_ITEM_RE.match(l)
            if m and not m.group(1):
                it = {"line": n, "checked": (m.group(2) or " ").lower() == "x", "text": m.group(3).rstrip(), "more": []}
                out.append(it)
            elif it is not None and l.strip():
                if l.startswith((" ", "\t")):
                    it["more"].append(l)
                else:
                    it = None
        return out

    def h3_groups(rows):
        groups, g, loose = [], None, []
        for n, l in rows:
            if l.startswith("### "):
                g = {"subject": l[4:].strip(), "rows": []}
                groups.append(g)
            elif g is None:
                loose.append((n, l))
            else:
                g["rows"].append((n, l))
        return groups, loose

    out = {"fm": fm, "title": title, "intro": "\n".join(intro).strip(), "sections": [], "due": None,
           "questions": [], "points": [], "notes": None,
           "format": fm.get("format") or ("v3" if any(s["kind"] == "questions" for s in sections) else "v2")}
    for s in sections:
        md_text = "\n".join(l for _, l in s["lines"]).strip()
        row = {"title": s["title"], "kind": s["kind"], "line": s["start"]}
        if s["kind"] == "due":
            out["due"] = {"title": s["title"], "md": md_text}
            continue
        if s["kind"] in ("questions", "bring"):
            groups, loose = h3_groups(s["lines"])
            keep = list(loose)
            for g in groups:
                if s["kind"] == "questions" or g["subject"].lower().startswith("questions"):
                    its = items_of(g["rows"])
                    if its:
                        out["questions"].append({"subject": g["subject"], "items": its})
                        continue
                keep += [(s["start"], "### " + g["subject"])] + g["rows"]
            if s["kind"] == "questions" and not groups:
                its = items_of(loose)
                if its:
                    out["questions"].append({"subject": "", "items": its})
                    keep = []
            rest = "\n".join(l for _, l in keep).strip()
            if rest:
                out["sections"].append(dict(row, md=rest))
            continue
        if s["kind"] == "points":
            groups, loose = h3_groups(s["lines"])
            if groups:
                for g in groups:
                    out["points"].append({"name": g["subject"],
                                          "items": [i["text"] + ("\n" + "\n".join(i["more"]) if i["more"] else "")
                                                    for i in items_of(g["rows"])]})
            else:
                byname = {}
                for i in items_of(loose):
                    m = re.match(r"^\*\*([^*]{1,60})\*\*\s*(?:·|:|-|—)?\s*(.*)$", i["text"])
                    name, body = (m.group(1).rstrip(":").strip(), m.group(2)) if m else ("", i["text"])
                    if name not in byname:
                        byname[name] = {"name": name, "items": []}
                        out["points"].append(byname[name])
                    byname[name]["items"].append(body + ("\n" + "\n".join(i["more"]) if i["more"] else ""))
            continue
        if s["kind"] == "notes":
            _, rest = _notes_split([l for _, l in s["lines"]])
            out["notes"] = {"title": s["title"], "line": s["start"], "text": "\n".join(rest).strip()}
            continue
        if md_text:
            out["sections"].append(dict(row, md=md_text))
    return out


def _iso_ts(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:                                             # noqa: BLE001
        return None


def calendar_events():
    """Every event the two calendar files carry, the week file's rows first, today's joined onto them (join, link, preps)."""
    evs = []
    try:
        evs += [dict(e) for e in calendar_week_api().get("events") or []]
    except Exception:                                             # noqa: BLE001
        pass
    try:
        cl = calls_api()
        for e in cl.get("events") or []:
            d = dict(e, date=cl.get("for") or ledger.today())
            same = next((x for x in evs if _iso_ts(x.get("start")) == _iso_ts(d["start"]) and x.get("title") == d["title"]), None)
            if same:
                for k in ("join", "calendarLink"):
                    same[k] = same.get(k) or d.get(k)
                same["preps"] = same.get("preps") or d.get("preps")
            else:
                evs.append(d)
    except Exception:                                             # noqa: BLE001
        pass
    return evs


def call_event_for(prep_rel=None, date=None, start=None):
    """The calendar event a call screen is for: by its start, or the event whose matched preps include this prep."""
    evs = calendar_events()
    if start:
        want = _iso_ts(start)
        for e in evs:
            if (want is not None and _iso_ts(e.get("start")) == want) or str(e.get("start")) == str(start):
                return e
        return None
    if prep_rel:
        hits = [e for e in evs if any(p.get("path") == prep_rel for p in e.get("preps") or [])]
        if date:
            hits = [e for e in hits if e.get("date") == date] or hits
        return hits[0] if hits else None
    return None


def event_prep_args(people):
    """What a prep for a calendar event is keyed to: the declared thread whose members are exactly the carded people on
    the call, else those people as a participant list. The owner and the names with no card are not participants."""
    slugs = sorted(set(w["slug"] for w in people or [] if w.get("slug")))
    if not slugs:
        return None
    for gid, mem in group_members().items():
        if mem and mem == set(slugs):
            return {"group": gid}
    return {"participants": slugs}


def prep_for_event(ev, purpose=""):
    """Write the skeleton for one calendar event through make_prep, the People panel's own writer. The attendee names with
    no card go into the skeleton's header as names. -> (path, existed) or raises ValueError."""
    args = event_prep_args(ev.get("people") or [])
    if not args:
        raise ValueError("nobody on this call has a people/ card")
    nocard = [w["name"] for w in ev.get("people") or [] if not w.get("slug") and not w.get("self")]
    day = str(ev.get("date") or "")[:10] or str(ev.get("start") or "")[:10]
    return make_prep(call_date=day, purpose=purpose or ev.get("title") or "", nocard=nocard, **args)


def call_api(prep=None, date=None, start=None):
    """GET /api/call?prep=<path> | ?date=YYYY-MM-DD&start=<ISO>: the call screen's one read. The event (title, time, join,
    people with their cards), the prep parsed into its parts, and every ledger id in it resolved to its words."""
    ev = None
    if start:
        ev = call_event_for(date=date, start=start)
        if ev is None:
            return 404, {"error": "no event starting %s on the calendar files" % start}
        if not prep:
            prep = ((ev.get("preps") or [{}])[0] or {}).get("path")
    rel = str(prep or "").replace("\\", "/").strip() or None
    ap = prep_rel_ok(rel) if rel else None
    if rel and not ap:
        return 404, {"error": "not a prep in %s: %s" % (CALLPREP_REL, rel)}
    parsed, text, mtime = None, "", None
    if ap:
        with open(ap, "r", encoding="utf-8-sig") as f:
            text = f.read()
        parsed = parse_prep(text)
        mtime = dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")
        if ev is None:
            ev = call_event_for(prep_rel=rel, date=parsed["fm"].get("call"))
    people = []
    if ev:
        people = [dict(w) for w in ev.get("people") or []]
    elif parsed:
        parts = [p.strip() for p in re.sub(r"^\[|\]$", "", parsed["fm"].get("participants", "")).split(",") if p.strip()]
        people = [{"name": s.replace("-", " ").title(), "slug": s, "card": "%s/%s.md" % (PEOPLE_REL, s), "self": False} for s in parts]
    try:
        rows = {r["slug"]: r for r in people_api().get("people") or []}
    except Exception:                                             # noqa: BLE001
        rows = {}
    for w in people:
        r = rows.get(w.get("slug") or "")
        if r:
            st = r.get("stands") or {}
            w.update(cardName=r.get("name"), role=clip(re.sub(r"\*\*", "", r.get("role") or ""), 160),
                     stands={"date": st.get("date"), "text": clip(st.get("text") or "", 260)} if st.get("text") else None,
                     status=clip(re.sub(r"\*\*", "", r.get("status") or ""), 200))
    idx, paths = call_ledger_index()
    # 0.48.0 (the layout check): this brain's main project when it has one, else the first registered ledger
    default_project = "pf-build" if "pf-build" in idx else next(iter(idx), None)
    if parsed:
        srcs = [s.strip() for s in re.sub(r"^\[|\]$", "", parsed["fm"].get("sources", "")).split(",")]
        default_project = next((paths[s] for s in srcs if s in paths), default_project)
    body = {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": ledger.today(),
            "prep": ({"path": rel, "mtime": mtime, "format": parsed["format"], "fm": parsed["fm"], "title": parsed["title"],
                      "intro": parsed["intro"], "due": parsed["due"], "questions": parsed["questions"],
                      "points": parsed["points"], "notes": parsed["notes"], "sections": parsed["sections"]} if parsed else None),
            "event": ({k: ev.get(k) for k in ("date", "start", "end", "title", "organizer", "join", "calendarLink")} if ev else None),
            "people": people, "canWrite": bool(ev and not parsed and event_prep_args(people)),
            "refs": call_refs(text, default_project, idx) if text else {}, "aliases": call_aliases(),
            "defaultProject": default_project, "reader": ("/reader?path=" + urllib.parse.quote(rel)) if rel else None}
    return 200, body


def call_log(rel, what):
    """One MODIFIED line per prep per ten minutes: a call with twenty ticks is one line in the log, not twenty."""
    now = time.time()
    if now - _call_logged.get(rel, 0) < CALL_LOG_EVERY:
        return "not logged: %s was logged under ten minutes ago" % rel
    _call_logged[rel] = now
    return log_line("%s -- %s on the call screen (/call)" % (rel, what))


def read_prep_lines(ap):
    with open(ap, "r", encoding="utf-8-sig", newline="") as f:
        raw = f.read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n").split("\n"), eol


def write_prep_lines(ap, lines, eol):
    with open(ap, "w", encoding="utf-8", newline="") as f:
        f.write(eol.join(lines))


def call_tick(data):
    """POST /api/call/tick {path, line, checked, text}: one question line becomes `- [x] ...` or `- [ ] ...`. `text` is the
    line as the page drew it; a line that no longer reads that way is refused (409), so a prep edited elsewhere since the
    page loaded is never ticked in the wrong place."""
    if PROPOSE:
        return 403, {"error": "call preps are not part of a team copy"}
    rel = str(data.get("path") or "").replace("\\", "/")
    ap = prep_rel_ok(rel)
    if not ap:
        return 404, {"error": "not a prep in %s: %s" % (CALLPREP_REL, rel)}
    try:
        n = int(data.get("line"))
    except (TypeError, ValueError):
        return 400, {"error": "line must be a number"}
    lines, eol = read_prep_lines(ap)
    if n < 0 or n >= len(lines):
        return 409, {"error": "line %d is not in the file any more" % n}
    m = CALL_ITEM_RE.match(lines[n])
    if not m or m.group(1) or m.group(3).rstrip() != str(data.get("text") or "").rstrip():
        return 409, {"error": "that line changed since the page loaded; reload the call screen"}
    on = bool(data.get("checked"))
    lines[n] = "- [%s] %s" % ("x" if on else " ", m.group(3))
    write_prep_lines(ap, lines, eol)
    return 200, {"ok": True, "path": rel, "line": n, "checked": on, "log": call_log(rel, "questions ticked")}


def call_notes(data):
    """POST /api/call/notes {path, text}: the prep's `## Your notes` section becomes this text. The HTML comment the
    skeleton puts at the top of the section stays; a prep without the section gets one at the end."""
    if PROPOSE:
        return 403, {"error": "call preps are not part of a team copy"}
    rel = str(data.get("path") or "").replace("\\", "/")
    ap = prep_rel_ok(rel)
    if not ap:
        return 404, {"error": "not a prep in %s: %s" % (CALLPREP_REL, rel)}
    text = str(data.get("text") or "").replace("\r\n", "\n").strip("\n")
    if len(text) > 200000:
        return 413, {"error": "the notes are over 200,000 characters"}
    lines, eol = read_prep_lines(ap)
    at = next((i for i, l in enumerate(lines) if CALL_NOTES_RE.match(l)), None)
    if at is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", "## Your notes", ""] + ([text, ""] if text else [])
    else:
        end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        comments, _ = _notes_split(lines[at + 1:end])
        new = [""] + (comments + [""] if comments else []) + ([text, ""] if text else [])
        lines = lines[:at + 1] + new + lines[end:]
    write_prep_lines(ap, lines, eol)
    return 200, {"ok": True, "path": rel, "chars": len(text), "log": call_log(rel, "notes saved")}


# A transcript is intaken when the import-checkup report for it exists (the runbook's retained artifact, and the reason
# the report folder sits next to the raws). The app mirror names the same call differently from the raw, so an exact
# stem match is tried first and a same-day report sharing a name word is accepted second, marked as the weaker match
# rather than quietly presented as the strong one.
TRANSCRIPT_EXT = {".txt", ".md", ".json", ".vtt", ".srt"}


def landed_api(day=None):
    today = day or ledger.today()
    reports = []
    rroot = os.path.join(BRAIN, INTAKE_REL.replace("/", os.sep))
    for fn in sorted(os.listdir(rroot)) if os.path.isdir(rroot) else []:
        if fn.startswith("import-checkup-") and fn.endswith(".md"):
            reports.append(fn)
    byStem, order = {}, []
    for d in TRANSCRIPT_DIRS:
        root = os.path.join(BRAIN, d.replace("/", os.sep))
        for fn in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            stem, ext = os.path.splitext(fn)
            if today not in fn or ext.lower() not in TRANSCRIPT_EXT or fn.startswith("."):
                continue
            k = (d, stem)
            if k not in byStem:
                byStem[k] = {"folder": d, "stem": stem, "mirror": d != TRANSCRIPT_DIRS[0], "files": [],
                             "report": None, "match": None, "mtime": ""}
                order.append(k)
            ap = os.path.join(root, fn)
            byStem[k]["files"].append({"path": "%s/%s" % (d, fn), "ext": ext.lower().lstrip("."), "bytes": os.path.getsize(ap)})
            byStem[k]["mtime"] = max(byStem[k]["mtime"], dt.datetime.fromtimestamp(os.path.getmtime(ap)).strftime("%Y-%m-%d %H:%M"))
    words_of = lambda s: set(w for w in re.split(r"[^a-z0-9]+", s.lower()) if len(w) >= 4 and not w.isdigit()) - {"import", "checkup"}
    for k in order:
        r = byStem[k]
        exact = "import-checkup-%s.md" % r["stem"]
        if exact in reports:
            r["report"], r["match"] = "%s/%s" % (INTAKE_REL, exact), "exact"
            continue
        want = words_of(r["stem"])
        for fn in reports:
            if today in fn and (want & words_of(fn)):
                r["report"], r["match"] = "%s/%s" % (INTAKE_REL, fn), "by name"
                break
    rows = [byStem[k] for k in order]
    rows.sort(key=lambda r: (r["mtime"], r["stem"]), reverse=True)
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": today, "folders": list(TRANSCRIPT_DIRS),
            "reportFolder": INTAKE_REL, "count": len(rows), "intaken": sum(1 for r in rows if r["report"]), "landed": rows}


# ---- the home page: the widget registry, the layout per member, and the help entries (2026-09-21) ----
# Three small readers and one writer. Nothing here derives anything about the brain: a widget reads its own endpoint in
# the browser, the layout file says which widgets are on and how big, and help.json says what each page is for.

def widget_registry():
    """Every *.js in skills/brain-viewer/widgets/, in the default order. The FOLDER is the registry: no list of widgets
    exists anywhere else, so dropping a file in there is the whole of adding a widget. The head of the file is read for
    what it declares about itself in its register() call -- title, size, defaultOn, source -- and a file that declares
    none of them still appears, small, off, under its own filename."""
    rows = []
    core_ids = set()
    user_folder = os.path.join(BRAIN, USER_WIDGETS_REL.replace("/", os.sep))
    # 0.48.0: the component's widgets/ first, then the user layer's viewer/widgets/. A user file whose stem is a core id
    # is listed under `user-<stem>` with a conflict and never loaded: a person's widget never overrides a core one.
    for origin, folder in (("core", os.path.join(HERE, WIDGETS_DIR)), ("user", user_folder)):
        try:
            names = sorted(n for n in os.listdir(folder) if n.endswith(".js"))
        except OSError:
            continue
        for name in names:
            row = _widget_row(origin, folder, name, core_ids)
            if row:
                rows.append(row)
            if origin == "core":
                core_ids.add(name[:-3])
    rows.sort(key=lambda w: (HOME_ORDER.index(w["id"]) if w["id"] in HOME_ORDER else len(HOME_ORDER), w["origin"] != "core", w["id"]))
    return rows


def _widget_row(origin, folder, name, core_ids):
    stem = name[:-3]
    if not WIDGET_ID_RE.match(stem):
        return None
    head = ""
    try:
        with open(os.path.join(folder, name), "r", encoding="utf-8", errors="replace") as f:
            head = f.read(WIDGET_HEAD)
    except OSError:
        pass
    title = re.search(r'title:\s*"([^"]{1,80})"', head)
    size = re.search(r'size:\s*"(\d{1,2}|[SML])"', head)
    tall = re.search(r"rows:\s*(\d)", head)
    on = re.search(r"defaultOn:\s*(true|false)", head)
    src = re.search(r'source:\s*"([^"]{1,240})"', head)
    con = re.search(r"contract:\s*(\d+)", head)
    span = size.group(1) if size else "4"
    taken = origin == "user" and stem in core_ids
    row = {"id": ("user-" + stem) if taken else stem, "file": name, "origin": origin,
           "path": ("skills/brain-viewer/%s/%s" % (WIDGETS_DIR, name)) if origin == "core" else "%s/%s" % (USER_WIDGETS_REL, name),
           "url": None if taken else ("/static/%s/%s" % (WIDGETS_DIR, name) if origin == "core" else "/static/user-widgets/%s" % name),
           "title": title.group(1) if title else stem,
           "size": HOME_SIZE_LEGACY.get(span, span) if HOME_SIZE_LEGACY.get(span, span) in HOME_SIZES else "4",
           "rows": int(tall.group(1)) if tall and int(tall.group(1)) in HOME_ROWS else 1,
           "defaultOn": bool(on and on.group(1) == "true") and not taken,
           "source": src.group(1) if src else "",
           "contract": int(con.group(1)) if con else None}
    if taken:
        row["conflict"] = "id taken by a core widget"
    return row


def home_member():
    """Whose layout this copy saves: the member a team copy was exported for, the owner otherwise (0.37.1: the owner,
    not a hard-coded name, so a copy answering to another @name keeps its own board)."""
    return MEMBER if PROPOSE else OWNER.lstrip("@")


def home_layout_rel(member=None):
    return HOME_LAYOUT_FMT % (member or home_member())


def home_default(reg=None):
    """The layout of a person who has never touched the page: the nine named above, on, in that order, then every other
    widget in the folder, off, so edit mode can add it."""
    reg = widget_registry() if reg is None else reg
    by = {w["id"]: w for w in reg}
    ids = [i for i in HOME_ORDER if i in by] + [w["id"] for w in reg if w["defaultOn"] and w["id"] not in HOME_ORDER]
    rows = [{"id": i, "on": True, "size": by[i]["size"], "rows": by[i].get("rows", 1),
             "collapsed": False, "expanded": False, "settings": {}} for i in ids]
    rows += [{"id": w["id"], "on": False, "size": w["size"], "rows": w.get("rows", 1),
              "collapsed": False, "expanded": False, "settings": {}}
             for w in reg if w["id"] not in ids]
    return rows


def home_settings(value, wid):
    """(settings, error) for one row's `settings`. A small JSON OBJECT and nothing else: a list, a string or a number is
    refused rather than quietly dropped, because a widget that saved its pick into something this cannot read would lose
    the pick on every save. Missing is an empty object, which is what a widget that has never been touched gets."""
    if value is None:
        return {}, None
    if not isinstance(value, dict):
        return None, "settings must be an object (%s)" % wid
    if len(value) > HOME_SETTINGS_KEYS:
        return None, "settings may hold at most %d keys (%s)" % (HOME_SETTINGS_KEYS, wid)
    for k in value:
        if not isinstance(k, str) or not k:
            return None, "every setting needs a name (%s)" % wid
    try:
        written = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return None, "settings must be something this can write out (%s)" % wid
    if len(written) > HOME_SETTINGS_CHARS:
        return None, "settings may be at most %d characters (%s)" % (HOME_SETTINGS_CHARS, wid)
    return value, None


def home_palette(value):
    """(palette, error) for where the add panel was left: {x, y, w, h}, four numbers, or nothing at all (0.40.0).
    The owner asked for the sidebar to be movable while scrolling, ideally in its own resizable window.
    It rides in the layout file beside the widgets because it is the same kind of thing -- an arrangement of the board
    that belongs to the person, not to one browser. Absent is absent: a panel that was never moved saves nothing."""
    if value is None:
        return None, None
    if not isinstance(value, dict):
        return None, "palette must be an object of x, y, w and h"
    out = {}
    for k in HOME_PALETTE_KEYS:
        v = value.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None, "palette %s must be a number, not %r" % (k, v)
        if v != v or v in (float("inf"), float("-inf")):        # NaN, and either infinity
            return None, "palette %s must be a real number" % k
        out[k] = round(float(v), 1)
    if out["w"] < 1 or out["h"] < 1:
        return None, "palette w and h must be sizes, not %r by %r" % (out["w"], out["h"])
    return out, None


# ---- looks: the design as a file that can be edited, swapped or imported (2026-09-22, ledger T-0208) ----
# THE REGISTRY IS THE FOLDER, as with widgets. Every *.css in skills/brain-viewer/looks/ is a look: one :root block of
# the design tokens, optionally led by one Google Fonts @import for its own faces. default.css holds all 33 and is always
# loaded; the person's chosen look is loaded after it, so a look that sets only some tokens falls back for the rest.
# The choice is the `look` field of that person's home-layout-<member>.json. Docs: looks/readme.md.
LOOKS_DIR = "looks"
LOOK_MAX_BYTES = 24000            # a look is a list of values; anything bigger is not one
LOOK_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
LOOK_IMPORT_RE = re.compile(r'@import\s+url\(\s*"(https://fonts\.googleapis\.com/[^"\s()]+)"\s*\)\s*;', re.I)
LOOK_TOKEN_RE = re.compile(r"^--[a-z][a-z0-9-]*$")
LOOK_BAD_VALUE_RE = re.compile(r"url\(|expression\(|@|<|>|\\|javascript:", re.I)
# the per-tile style a row of the layout may carry, key -> what it accepts
HOME_STYLE_SCALES = ("s", "m", "l")
HOME_STYLE_BOXES = ("hairline", "card", "none")
HOME_STYLE_FONTS = ("title", "display", "ui", "mono")
HOME_STYLE_ACCENT_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def look_parse(text):
    """(tokens, imports, error) for the text of one look. Only custom-property declarations inside one :root block, plus
    Google Fonts @import lines in front of it. A value may not load anything (no url(), no @, no angle brackets)."""
    if len(text.encode("utf-8")) > LOOK_MAX_BYTES:
        return None, None, "a look may be at most %d bytes" % LOOK_MAX_BYTES
    t = re.sub(r"/\*.*?\*/", " ", text, flags=re.S).strip()
    if "/*" in t:
        return None, None, "a comment is left open"
    imports = []
    while t.startswith("@"):
        m = LOOK_IMPORT_RE.match(t)
        if not m:
            return None, None, "the only @ rule a look may carry is @import url(\"https://fonts.googleapis.com/...\");"
        imports.append(m.group(1))
        t = t[m.end():].strip()
    m = re.fullmatch(r":root\s*\{(.*)\}", t, re.S)
    if not m:
        return None, None, "a look is one :root { ... } block and nothing else"
    body = m.group(1)
    if "{" in body or "}" in body:
        return None, None, "a look is one :root { ... } block and nothing else"
    tokens = {}
    for decl in body.split(";"):
        decl = decl.strip()
        if not decl:
            continue
        name, sep, val = decl.partition(":")
        name, val = name.strip(), val.strip()
        if not sep or not LOOK_TOKEN_RE.match(name):
            return None, None, "only custom properties (--name: value) belong in a look, not %r" % decl[:60]
        if not val:
            return None, None, "%s has no value" % name
        if LOOK_BAD_VALUE_RE.search(val):
            return None, None, "%s: a value may not load anything or carry markup" % name
        if name in tokens:
            return None, None, "%s is set twice" % name
        tokens[name] = val
    if not tokens:
        return None, None, "a look must set at least one token"
    return tokens, imports, None


CORE_LOOKS = ("default", "paper")     # the looks the component ships; every other look is the person's, in viewer/looks/


def user_looks_dir():
    return os.path.join(BRAIN, USER_LOOKS_REL.replace("/", os.sep))


def look_abs(name):
    """A core look from the component's looks/, anything else from the user layer's viewer/looks/ (0.48.0). A core
    name always resolves to the core file: a person's look never replaces one the viewer ships."""
    core = os.path.join(HERE, LOOKS_DIR, name + ".css")
    if name in CORE_LOOKS or os.path.isfile(core):
        return core
    return os.path.join(user_looks_dir(), name + ".css")


def look_known():
    """The token names the viewer knows: the ones default.css sets. A look may set only these."""
    try:
        with open(look_abs("default"), "r", encoding="utf-8") as f:
            tokens, _i, _e = look_parse(f.read())
        return list(tokens or {})
    except OSError:
        return []


def look_registry():
    """Every *.css in looks/, default first: its name, the one line its leading comment says, how many tokens it sets,
    and whether it parses. A file that does not parse is listed with its error and is never offered as usable."""
    folder = os.path.join(HERE, LOOKS_DIR)
    try:
        names = sorted(n[:-4] for n in os.listdir(folder) if n.endswith(".css"))
    except OSError:
        return []
    core = set(names)
    try:
        user = sorted(n[:-4] for n in os.listdir(user_looks_dir()) if n.endswith(".css"))
    except OSError:
        user = []
    known = set(look_known())
    rows = []
    for name in sorted(names, key=lambda n: (n != "default", n)) + [n for n in user if n not in core]:
        row = {"name": name, "url": "/static/%s/%s.css" % (LOOKS_DIR, name), "description": "", "tokens": 0, "ok": False, "error": None,
               "origin": "core" if name in core else "user"}
        try:
            with open(look_abs(name), "r", encoding="utf-8") as f:
                text = f.read()
            lead = re.match(r"\s*/\*(.*?)\*/", text, re.S)
            row["description"] = " ".join(lead.group(1).split())[:240] if lead else ""
            tokens, imports, err = look_parse(text)
            if not err and LOOK_NAME_RE.match(name) is None:
                err = "the file name must be lowercase letters, digits and hyphens"
            if not err:
                unknown = [k for k in tokens if k not in known]
                if unknown:
                    err = "sets tokens the viewer does not know: " + ", ".join(unknown[:6])
            row.update(tokens=len(tokens or {}), fonts=imports or [], ok=not err, error=err)
        except OSError as e:
            row["error"] = str(e)
        rows.append(row)
    for name in user:
        if name in core:     # a person's file under a name the viewer ships: listed, never used
            rows.append({"name": name + " (yours)", "url": None, "description": "", "tokens": 0, "ok": False, "origin": "user",
                         "error": "name taken by a core look: rename %s/%s.css" % (USER_LOOKS_REL, name)})
    return rows


def look_active():
    """The member's chosen look, from the `look` field of their layout file; default when there is none, or when the
    file it names is gone or no longer parses."""
    ap = os.path.join(BRAIN, home_layout_rel().replace("/", os.sep))
    name = "default"
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            name = str(json.load(f).get("look") or "default")
    except Exception:
        return "default"
    if name == "default" or not LOOK_NAME_RE.match(name) or not os.path.isfile(look_abs(name)):
        return "default"
    return name


def looks_api():
    """GET /api/looks: the folder, the member's active look, and the token names a look may set."""
    return {"looks": look_registry(), "active": look_active(), "tokens": look_known(),
            "folder": "skills/brain-viewer/%s/" % LOOKS_DIR, "userFolder": USER_LOOKS_REL + "/", "maxBytes": LOOK_MAX_BYTES,
            "styleKeys": {"accent": "#rgb or #rrggbb", "scale": list(HOME_STYLE_SCALES),
                          "box": list(HOME_STYLE_BOXES), "font": list(HOME_STYLE_FONTS)}}


def look_set_active(name):
    """Save the member's look into the `look` field of their layout file, leaving everything else in it as it was. With
    no layout file yet, the file is written with the look alone and the board stays the default."""
    name = str(name or "").strip().lower()
    if name != "default":
        if not LOOK_NAME_RE.match(name) or not os.path.isfile(look_abs(name)):
            return {"error": "no such look: %s" % (name or "(unnamed)")}
        row = next((r for r in look_registry() if r["name"] == name), None)
        if not row or not row["ok"]:
            return {"error": "that look does not parse: %s" % ((row or {}).get("error") or name)}
    rel = home_layout_rel()
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    doc = {"schema": HOME_SCHEMA, "member": home_member()}
    if os.path.isfile(ap):
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                doc = json.load(f)
        except Exception as e:
            return {"error": "the layout file could not be read, so the look was not saved: %s" % e}
    doc["look"] = name
    doc["updatedAt"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"ok": True, "active": name, "path": rel}


def look_import(data):
    """POST /api/looks {"name", "css", "replace"?, "activate"?}: a look written into looks/<name>.css after it parses and
    sets only known tokens. The name is sanitized to lowercase letters, digits and hyphens; default.css is never
    replaced, and an existing look only when `replace` is true. {"active": name} instead picks the member's look."""
    if "active" in data and "css" not in data:
        return look_set_active(data.get("active"))
    raw = re.sub(r"\.css$", "", str(data.get("name") or "").strip().lower())
    name = re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9-]+", "-", raw)).strip("-")[:40].strip("-")
    if not name or not LOOK_NAME_RE.match(name):
        return {"error": "a look needs a name made of letters, digits and hyphens"}
    if name in CORE_LOOKS or os.path.isfile(os.path.join(HERE, LOOKS_DIR, name + ".css")):
        return {"error": "%s.css ships with the viewer and is not replaced from here; give the look its own name" % name}
    css = data.get("css")
    if not isinstance(css, str) or not css.strip():
        return {"error": "no css was sent"}
    tokens, _imports, err = look_parse(css)
    if err:
        return {"error": err}
    known = set(look_known())
    unknown = [k for k in tokens if k not in known]
    if unknown:
        return {"error": "sets tokens the viewer does not know: %s (the names are in looks/readme.md)" % ", ".join(unknown[:6])}
    ap = look_abs(name)
    existed = os.path.isfile(ap)
    if existed and not data.get("replace"):
        return {"error": "a look named %s is already there; send replace: true to overwrite it" % name, "exists": True}
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        f.write(css if css.endswith("\n") else css + "\n")
    rel = "%s/%s.css" % (USER_LOOKS_REL, name)
    note = log_line("%s -- look %s from the home page (%d tokens)" % (rel, "replaced" if existed else "imported", len(tokens)),
                    action="MODIFIED" if existed else "CREATED")
    out = {"ok": True, "name": name, "path": rel, "tokens": len(tokens), "replaced": existed, "log": note}
    if data.get("activate"):
        out["activated"] = look_set_active(name)
    return out


def look_head(html):
    """Every page's look, in its head before first paint: default.css, then the member's look, both ahead of the shared
    stylesheet, plus window.BV_LOOK for viewer-common.js. Written into the page as it is served, so there is no flash."""
    active = look_active()
    tags = '<link rel="stylesheet" href="/static/%s/default.css" data-look-base>' % LOOKS_DIR
    if active != "default":
        tags += '\n<link rel="stylesheet" href="/static/%s/%s.css" id="bv-look" data-look="%s">' % (LOOKS_DIR, active, active)
    anchor = '<link rel="stylesheet" href="/static/viewer-tokens.css">'
    html = html.replace(anchor, tags + "\n" + anchor, 1) if anchor in html else html.replace("</head>", tags + "\n</head>", 1)
    return html.replace("</head>", "<script>window.BV_LOOK=%s;</script>\n</head>" % json.dumps(active), 1)


def home_style(value, wid):
    """(style, error) for one row's `style` (T-0208): the tile's own accent, text scale, box and face, each optional.
    Absent or empty is None, so a row that never had one is written exactly as before."""
    if value is None or value == {}:
        return None, None
    if not isinstance(value, dict):
        return None, "style must be an object (%s)" % wid
    out = {}
    for k, v in value.items():
        if k == "accent":
            if not isinstance(v, str) or not HOME_STYLE_ACCENT_RE.match(v):
                return None, "style accent must be a hex color like #b24a2c (%s)" % wid
        elif k == "scale":
            if v not in HOME_STYLE_SCALES:
                return None, "style scale must be one of %s (%s)" % (", ".join(HOME_STYLE_SCALES), wid)
        elif k == "box":
            if v not in HOME_STYLE_BOXES:
                return None, "style box must be one of %s (%s)" % (", ".join(HOME_STYLE_BOXES), wid)
        elif k == "font":
            if v not in HOME_STYLE_FONTS:
                return None, "style font must be one of %s (%s)" % (", ".join(HOME_STYLE_FONTS), wid)
        else:
            return None, "style has no key %r; it takes accent, scale, box and font (%s)" % (k, wid)
        out[k] = v
    return out or None, None


HOME_VIEWS_MAX = 40               # T-0214: how many named views one member's layout may carry
HOME_VIEW_NAME = 60               # ... and how long a view's name may be


def home_views(value, reg=None, drop_missing=False):
    """(views, error) for the layout's `views` (T-0214): a widget whose settings differ from its default, saved under a
    name so the add list offers it as its own entry. Each is {id, name, settings}: the id a widget file answers to, a
    name of one to sixty characters, unique ignoring case, and settings checked by home_settings. Absent is an empty
    list. Reading a saved file, a view whose widget file is gone is dropped, the way a row is."""
    if value is None:
        return [], None
    if not isinstance(value, list):
        return None, "views must be a list"
    if len(value) > HOME_VIEWS_MAX:
        return None, "a layout may carry at most %d views" % HOME_VIEWS_MAX
    reg = widget_registry() if reg is None else reg
    known = {w["id"] for w in reg}
    out, names = [], set()
    for v in value:
        if not isinstance(v, dict):
            return None, "each view must be an object"
        wid = str(v.get("id") or "")
        if wid not in known:
            if drop_missing:
                continue
            return None, "no such widget for a view: %s" % (wid or "(unnamed)")
        name = " ".join(str(v.get("name") or "").split()) if isinstance(v.get("name"), str) else ""
        if not name or len(name) > HOME_VIEW_NAME:
            return None, "a view needs a name of 1 to %d characters (%s)" % (HOME_VIEW_NAME, wid)
        if name.lower() in names:
            return None, "two views are named %s" % name
        conf, serr = home_settings(v.get("settings"), wid)
        if serr:
            return None, serr
        names.add(name.lower())
        out.append({"id": wid, "name": name, "settings": conf})
    return out, None


def home_validate(rows, reg=None, drop_missing=False, mode="grid", gravity=False, row_unit=None):
    """(rows, error). Every id must be one the folder holds, once; every size one of the column spans. A layout that does
    not name a widget the folder has grown since it was saved gets it appended, off, so a new file is never invisible.
    `expanded` rides along with `collapsed`: an instrument grows to the full width in place and that state is the
    person's, not the browser's. `settings` rides the same way (0.38.0): the small object an instrument keeps its own
    pick in, checked by home_settings.
    Free mode (T-0213): a row may carry its cell, x and y (column 0 to 11, row index) and w and h (columns 1 to 12,
    rows 1 to 24), whole numbers with x + w at most 12. In free mode a cell that is out of range is refused; reading a
    saved file it is treated as missing, and an on-board row with no cell is placed at the end, under the last tile.
    Grid mode ignores cells: a good one is kept, so switching back to free finds the tiles where they were, and a bad
    one is dropped without an error. Nothing that was valid before this is refused now.
    `gravity` is free mode's "keep closed" switch, beside the mode: true or false, nothing else.
    The fine row unit (2026-09-22): `row_unit` is the layout's rowUnit, the free row's height in px, a whole number 8 to
    200 (the page writes 20); None is a board saved before it, on the old 158px pitch, which the page converts once.
    The ranges are widened for the finer unit (y up to 4000, h up to 400). In free mode `h` may be missing, which means
    the tile fits its content, and `hFixed` (true or false) says the person set its height; only true is kept. A bad
    rowUnit or hFixed is refused from the page in free mode and dropped otherwise, as a bad cell is."""
    cols, max_y, max_h = 12, 4000, 400
    if not isinstance(gravity, bool):
        return None, "gravity must be true or false, not %r" % (gravity,)
    if row_unit is not None and not (isinstance(row_unit, int) and not isinstance(row_unit, bool) and 8 <= row_unit <= 200):
        if mode == "free" and not drop_missing:
            return None, "rowUnit must be a whole number of px from 8 to 200, not %r" % (row_unit,)
        row_unit = None
    reg = widget_registry() if reg is None else reg
    known = {w["id"]: w for w in reg}
    if not isinstance(rows, list):
        return None, "widgets must be a list"
    out, seen = [], set()
    # READING a saved board (drop_missing), a row that fails its own checks is dropped by itself and the rest is kept
    # (2026-09-24, T-0223, the saved-layout migration rule in widgets/readme.md): one bad row used to fail the whole
    # file, the page then drew the default, and the next save replaced the person's board with it. From the page every
    # check still refuses, so nothing malformed is ever written.
    for r in rows:
        if not isinstance(r, dict):
            if drop_missing:
                continue
            return None, "each widget must be an object"
        wid = str(r.get("id") or "")
        if wid not in known:
            # reading a SAVED board, a name the folder no longer answers to is simply dropped (0.38.0): deleting a
            # widget file must not throw away the arrangement around it, which is what happened to every saved board
            # the moment the red strip's file went. A board arriving from the page is still refused for the same name.
            if drop_missing:
                continue
            return None, "no such widget: %s" % (wid or "(unnamed)")
        if wid in seen:
            if drop_missing:
                continue                              # the first row for an id wins; a second is dropped
            return None, "widget named twice: %s" % wid
        size = str(r.get("size") or known[wid]["size"])
        size = HOME_SIZE_LEGACY.get(size, size)      # a layout saved under 0.36 named S, M or L
        if size not in HOME_SIZES:
            if drop_missing:
                size = known[wid]["size"] if known[wid]["size"] in HOME_SIZES else HOME_SIZES[0]   # keep the tile, at its default size
            else:
                return None, "size must be one of %s, not %r (%s)" % (", ".join(HOME_SIZES), r.get("size"), wid)
        tall = r.get("rows", known[wid].get("rows", 1))
        try:
            tall = int(tall)
        except (TypeError, ValueError):
            if not drop_missing:
                return None, "rows must be a whole number (%s)" % wid
            tall = 1
        if tall not in HOME_ROWS:
            if drop_missing:
                tall = 1                              # keep the tile, one row tall
            else:
                return None, "rows must be one of %s, not %r (%s)" % (", ".join(str(n) for n in HOME_ROWS), r.get("rows"), wid)
        conf, serr = home_settings(r.get("settings"), wid)
        if serr:
            if not drop_missing:
                return None, serr
            conf = {}                                 # a setting the widget no longer takes: the tile keeps its place
        look_style, sterr = home_style(r.get("style"), wid)
        if sterr:
            if not drop_missing:
                return None, sterr
            look_style = None
        seen.add(wid)
        out.append({"id": wid, "on": bool(r.get("on", True)), "size": size, "rows": tall,
                    "collapsed": bool(r.get("collapsed", False)), "expanded": bool(r.get("expanded", False)),
                    "settings": conf})
        if look_style:
            out[-1]["style"] = look_style     # the tile's own look (T-0208): absent when it has none, so old files read the same
        # T-0214: the name of the view this tile was placed from, shown as its title until a filter moves off it.
        # Absent when there is none; anything that is not a short string is simply not kept, never an error.
        vname = " ".join(str(r.get("view") or "").split())[:HOME_VIEW_NAME] if isinstance(r.get("view"), str) else ""
        if vname:
            out[-1]["view"] = vname
        # T-0213: the tile's cell on the twelve columns, for free mode
        if any(k in r for k in ("x", "y", "w", "h")):
            # h may be missing in free mode: the tile fits its content (the fine unit, 2026-09-22)
            auto = "h" not in r and mode == "free"
            vals = [r.get(k) for k in (("x", "y", "w") if auto else ("x", "y", "w", "h"))]
            good = all(isinstance(v, int) and not isinstance(v, bool) for v in vals)
            if good:
                cx, cy, cw = vals[:3]
                good = (0 <= cx < cols and 1 <= cw <= cols and cx + cw <= cols and 0 <= cy <= max_y
                        and (auto or 1 <= vals[3] <= max_h))
            if good:
                out[-1].update({"x": vals[0], "y": vals[1], "w": vals[2]})
                if not auto:
                    out[-1]["h"] = vals[3]
            elif mode == "free" and not drop_missing:
                return None, ("in free mode x, y, w and h are whole numbers on the twelve columns: x 0 to 11, w 1 to 12 "
                              "with x + w at most 12, y 0 to %d, h 1 to %d or missing (%s)" % (max_y, max_h, wid))
        if "hFixed" in r:
            if isinstance(r.get("hFixed"), bool):
                if r["hFixed"] and "x" in out[-1]:
                    out[-1]["hFixed"] = True   # the person set this tile's height; absent, it fits its content
            elif mode == "free" and not drop_missing:
                return None, "hFixed must be true or false, not %r (%s)" % (r.get("hFixed"), wid)
    if mode == "free":
        # a placed tile's height in the layout's unit: the old pitch's rows, or those rows (158px less the gap) in the
        # fine unit; a tile with no h (it fits its content) counts one unit here, and the page measures it
        def units(n):
            return max(1, int(round((n * 158 - 18) / float(row_unit)))) if row_unit else n
        bottom = max([o["y"] + o.get("h", 1) for o in out if o["on"] and "x" in o] or [0])
        for o in out:
            if o["on"] and "x" not in o:
                o.update({"x": 0, "y": bottom, "w": 12 if o["expanded"] else int(o["size"]), "h": units(o["rows"])})
                bottom += o["h"]
    out += [{"id": w["id"], "on": False, "size": w["size"], "rows": w.get("rows", 1),
             "collapsed": False, "expanded": False, "settings": {}}
            for w in reg if w["id"] not in seen]
    return out, None


# ---- what the home page's dial and its timeline read (2026-09-21, the home redesign 0.37.0) ----
# Both are one file read at request time and nothing else. The calendar is reachable only through the Claude Code MCP
# tool, so the session start writes what it saw and these render THAT -- never a second calendar, never a guess.

def calendar_week_api():
    """GET /api/calendar/week: the next seven days as the session start wrote them. With no week file the today file is
    answered instead, flattened into the same shape, and `source` says which one this is so the page can tell a person
    plainly how far its calendar reaches."""
    today = ledger.today()
    out = {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": today, "schema": "brain-calendar-week/1",
           "file": CALENDAR_WEEK_REL, "source": "week", "exists": False, "from": None, "to": None,
           "writtenAt": None, "timezone": None, "events": [], "count": 0, "days": [],
           "writtenBy": "the session start"}
    ap = os.path.join(BRAIN, CALENDAR_WEEK_REL.replace("/", os.sep))
    if not os.path.isfile(ap):
        out["source"], out["file"] = "today", CALENDAR_REL
        ap = os.path.join(BRAIN, CALENDAR_REL.replace("/", os.sep))
        if not os.path.isfile(ap):
            return out
    out["exists"] = True
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:                                        # noqa: BLE001
        out["error"] = "%s: %s" % (type(e).__name__, e)
        return out
    out["writtenAt"] = str(data.get("writtenAt") or "") or None
    out["timezone"] = str(data.get("timezone") or "") or None
    # every event carries its people resolved to cards and the prep written for that call, by the same rule the day's
    # calls are joined by (preps_for_event). 0.39.0: the home board's Next opens the prep for the call in front of you
    # whatever day it falls on, and the people ring reaches a person's card from an attendee name, so the join belongs
    # to the endpoint rather than to each instrument guessing at it. A copy with no people/ folder simply resolves
    # nobody and matches no prep, which is the shape a team copy already gets.
    by_day = {}
    gmembers = {}
    try:
        for p in preps():
            by_day.setdefault(p["call"], []).append(p)
        gmembers = group_members()
    except Exception:                                             # noqa: BLE001
        by_day, gmembers = {}, {}
    for e in (data.get("events") or []):
        if not isinstance(e, dict):
            continue
        start = str(e.get("start") or "")
        day = str(e.get("date") or "")[:10] or start[:10]
        names = [(a or {}).get("name") if isinstance(a, dict) else a for a in (e.get("attendees") or [])]
        try:
            who = event_slugs(names)
        except Exception:                                         # noqa: BLE001
            who = [{"name": str(n or ""), "slug": None, "card": None, "self": False} for n in names if str(n or "")]
        dp = event_day_preps(e, day, by_day)
        hits = preps_for_event(event_match_keys(who), dp, gmembers) if dp else []
        out["events"].append({"date": day, "start": start, "end": str(e.get("end") or ""),
                              "title": str(e.get("title") or "(untitled)"),
                              "organizer": str(e.get("organizer") or "") or None,
                              "attendees": [{"name": w["name"]} for w in who],
                              "people": who, "preps": prep_rows(hits), **event_links(e)})
    out["events"].sort(key=lambda e: (e["start"], e["title"]))
    out["count"] = len(out["events"])
    out["withPrep"] = sum(1 for e in out["events"] if e["preps"])
    days = sorted(set(e["date"] for e in out["events"] if e["date"]))
    out["days"] = days
    # the window the file itself claims wins; with none, the days it actually carries
    out["from"] = str(data.get("from") or "")[:10] or (days[0] if days else today)
    out["to"] = str(data.get("to") or "")[:10] or (days[-1] if days else today)
    return out


MOVED_MAX = 200                   # how many parsed log rows this will ever answer with
MOVED_DEFAULT = 40                # the window the home page's timeline asks for
MOVED_TAIL_BYTES = 400000         # how much of the tail of the log is read: ~3 weeks of lines at the current rate
MOVED_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})\]\s+\[([^\]]+)\]\s+([A-Z][A-Z_-]*)\s+--\s+(.*)$")


MOVED_DAYS_MAX = 60               # the furthest back a days= window will reach


def moved_api(since="", limit=MOVED_DEFAULT, agent="", days=""):
    """GET /api/moved: the tail of context/log.md parsed into rows, newest first. What moved in the brain, in the words
    whoever moved it wrote. The file is append-only and the newest lines are at the bottom, so only its tail is read.

    `agent=` keeps only the rows one writer wrote (`?agent=night-agent`, several separated by commas, case ignored) and
    `days=` keeps only the rows inside that many days back from today, both added 0.38.0 for the moon on the masthead,
    which asks "how many of the last seven nights did the night agent run" and needs the answer in one call. A days
    window reaches past the tail through the rotated months when it has to, so a seven-night question does not depend
    on how busy the log has been this week."""
    try:
        limit = max(1, min(MOVED_MAX, int(limit)))
    except (TypeError, ValueError):
        limit = MOVED_DEFAULT
    agents = {a.strip().lower() for a in str(agent or "").split(",") if a.strip()}
    window = None
    if str(days or "").strip():
        try:
            n = max(1, min(MOVED_DAYS_MAX, int(days)))
            window = (dt.date.today() - dt.timedelta(days=n - 1)).isoformat()
        except (TypeError, ValueError):
            window = None
    since = str(since or "").strip()
    if window and (not since or since[:10] > window):
        since = window + "T00:00"
    ap = os.path.join(BRAIN, LOG_REL.replace("/", os.sep))
    out = {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "file": LOG_REL, "since": since or None,
           "limit": limit, "items": [], "count": 0, "read": 0,
           "agent": sorted(agents) or None, "days": window}
    if not os.path.isfile(ap):
        out["error"] = "there is no %s to read" % LOG_REL
        return out
    try:
        size = os.path.getsize(ap)
        with open(ap, "rb") as f:
            reached_start = size <= MOVED_TAIL_BYTES
            if not reached_start:
                f.seek(size - MOVED_TAIL_BYTES)
                f.readline()                     # the first line of a seek is half a line
            text = f.read().decode("utf-8", errors="replace")
        lines = text.splitlines()
        # a window older than the tail reaches: read the whole rotation instead, which is the only way a seven-night
        # question is answered the same on a busy week and a quiet one
        if window and not reached_start:
            first = next((MOVED_RE.match(l.strip()) for l in lines if MOVED_RE.match(l.strip())), None)
            if not first or first.group(1) > window:
                lines = list(log_lines(since=window))
    except OSError as e:
        out["error"] = "%s: %s" % (type(e).__name__, e)
        return out
    rows = []
    for line in lines:
        m = MOVED_RE.match(line.strip())
        if not m:
            continue
        day, clock, who, action, what = m.groups()
        at = "%sT%s" % (day, clock)
        if since and at < since[:16]:
            continue
        if agents and who.strip().lower() not in agents:
            continue
        rows.append({"at": at, "day": day, "time": clock, "agent": who.strip(), "action": action,
                     "text": re.sub(r"\s+", " ", what).strip()})
    out["read"] = len(rows)
    rows.reverse()                               # newest first
    out["items"] = rows[:limit]
    out["count"] = len(out["items"])
    if out["items"]:
        out["newest"], out["oldest"] = out["items"][0]["at"], out["items"][-1]["at"]
    return out


# ---- the lamps (0.38.0): every part of this brain that runs on its own, and when it last ran ----
# On 2026-09-21 the owner found the red Wrong strip this replaces confusing. Blocked and overdue work is not a
# fault, it is work, and it already has two homes (Decide, and the day page). What belongs in a row of lamps is the
# machinery: the reads and the writes that happen without anybody pressing anything, each with the last time it ran.
# Everything here is computed at request time from what those parts themselves wrote: two calendar files, the brain's
# own log, git, and this process's uptime. Nothing is stored and nothing is guessed.
SYSTEM_WINDOW = {"session": 24 * 3600, "daily": 24 * 3600, "weekly": 7 * 24 * 3600}
SYSTEM_GIT_TIMEOUT = 3


def _system_state(ts, cadence, crashed=False):
    """lit inside one cadence window, dim inside two, red past that, and red for never and for a crash."""
    if crashed or not ts:
        return "red"
    age = (dt.datetime.now().astimezone() - ts).total_seconds()
    win = SYSTEM_WINDOW.get(cadence, 24 * 3600)
    return "lit" if age <= win else ("dim" if age <= 2 * win else "red")


def _system_when(value):
    """Whatever a file or a log line wrote, as an aware datetime, or None."""
    if not value:
        return None
    try:
        t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.astimezone()


def _calendar_lamp(rel, lid, name, cadence, detail_for):
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    if not os.path.isfile(ap):
        return {"id": lid, "name": name, "lastRan": None, "cadence": cadence, "state": "red",
                "detail": "no file has been written"}
    written = None
    count = 0
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            doc = json.load(f)
        written = _system_when(doc.get("writtenAt"))
        count = len(doc.get("events") or [])
    except Exception:                                             # noqa: BLE001
        pass
    if written is None:
        written = dt.datetime.fromtimestamp(os.path.getmtime(ap)).astimezone()
    return {"id": lid, "name": name, "lastRan": written.isoformat(timespec="seconds"), "cadence": cadence,
            "state": _system_state(written, cadence), "detail": detail_for(count)}


def _lamp_say(text, n=90):
    """A log line as a person reads it: no file path in front of it, no ledger ids, nothing to decode."""
    t = re.sub(r"^[a-z0-9._\-/]+\.(md|json|py|js|canvas|txt)\s+--\s+", "", str(text or ""), flags=re.I)
    t = re.sub(r"\b[QT]-\d{4}\b\s*", "", t)
    t = re.sub(r"\s+--\s+", ", ", t)
    return clip(re.sub(r"\s+", " ", t).strip(), n)


def _log_lamp(lid, name, cadence, match, detail, days=21):
    """One lamp off the newest log line a test matches. The window is days back, which is inside the tail read."""
    row = None
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    for line in log_lines(since=since):
        m = MOVED_RE.match(line.strip())
        if not m:
            continue
        r = {"at": "%sT%s" % (m.group(1), m.group(2)), "agent": m.group(3).strip(), "action": m.group(4),
             "text": re.sub(r"\s+", " ", m.group(5)).strip()}
        if match(r):
            row = r                                               # the file is oldest first: the last match is the newest
    when = _system_when(row["at"]) if row else None
    return {"id": lid, "name": name, "lastRan": when.isoformat(timespec="seconds") if when else None,
            "cadence": cadence, "state": _system_state(when, cadence),
            "detail": detail(row) if row else "nothing in the last %d days" % days}


def _git_lamp():
    when, detail = None, "git could not be read"
    try:
        p = subprocess.run(["git", "log", "-1", "--format=%cI"], cwd=BRAIN, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=SYSTEM_GIT_TIMEOUT)
        if p.returncode == 0:
            when = _system_when(p.stdout.decode("utf-8", "replace").strip())
            detail = "the newest commit in this folder" if when else "no commit could be read"
    except (OSError, subprocess.SubprocessError):
        pass
    return {"id": "git", "name": "Git", "lastRan": when.isoformat(timespec="seconds") if when else None,
            "cadence": "session", "state": _system_state(when, "session"), "detail": detail}


# ---- a broken widget, told to the server (T-0217) ----
# The home page guards every widget's mount and refresh. A throw, or an api.get that fails for any reason but a team
# copy's 403, turns that tile red-edged and POSTs {id, error, where, stack} here ONCE per widget and error per page
# load. This keeps the break in memory (the widgets lamp reads it) and files ONE finding on the brain-viewer ledger,
# keyed widget-broken:<id>:<hash of the error's first line>, so the same widget and error raised again lands on the open
# item as a repeat, never a second one. Inside WIDGET_BREAK_QUIET of the last write for that key nothing is written at
# all, because every reload of a broken board would otherwise add a repeat line.
WIDGET_BREAKS = {}                    # key -> {id, error, where, file, at, count, item, filed}
WIDGET_BREAK_LOCK = threading.Lock()
WIDGET_BREAK_WINDOW = 3600            # the lamp is red while any break is younger than this
WIDGET_BREAK_QUIET = 3600             # the ledger is not touched again for the same key inside this
WIDGET_BREAK_LEDGER = str(SETTINGS.get("findings_ledger") or "brain-viewer-holon")   # 0.48.0: a setting; unregistered = recorded, not filed
WIDGET_BREAK_SOURCE = "brain-viewer"
WIDGET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def widget_broken(data):
    """POST /api/widgets/broken -> (code, answer). Records the break and files or repeats its finding."""
    wid = str((data or {}).get("id") or "").strip()
    row = next((w for w in widget_registry() if w["id"] == wid), None) if WIDGET_ID_RE.match(wid) else None
    if not row:
        return 400, {"error": "no widget file answers to that id"}
    err = " ".join(str(data.get("error") or "it failed").split("\n")[0].split())[:240] or "it failed"
    where = " ".join(str(data.get("where") or "").split())[:120]
    key = "widget-broken:%s:%s" % (wid, hashlib.sha1(err.encode("utf-8")).hexdigest()[:8])
    now = dt.datetime.now().astimezone()
    rel_file = row["path"]
    with WIDGET_BREAK_LOCK:
        rec = WIDGET_BREAKS.get(key)
        quiet = bool(rec and rec.get("wrote") and (now - rec["wrote"]).total_seconds() < WIDGET_BREAK_QUIET)
        if not rec:
            rec = WIDGET_BREAKS[key] = {"id": wid, "error": err, "where": where, "file": rel_file, "count": 0,
                                        "item": None, "filed": None, "wrote": None}
        rec["count"] += 1
        rec["at"] = now
        rec["where"] = where or rec["where"]
        if quiet or PROPOSE:
            rec["filed"] = rec["filed"] or ("not filed: a team copy" if PROPOSE else None)
            return 200, _widget_break_out(key, rec, "held" if quiet else "recorded")
        try:
            path, rel = ledger.resolve(WIDGET_BREAK_LEDGER)
            hits = ledger.open_by_key(key, file=rel)
            if hits:
                iid = hits[0][3]["id"]
                ledger.apply(path, rel, "repeat", agent="brain-viewer", id=iid, source=WIDGET_BREAK_SOURCE,
                             text="broke again on the home board (%s)" % (where or "mount"))
                rec["filed"] = "repeated"
            else:
                iid = ledger.apply(path, rel, "add", agent="brain-viewer", owner="@claude",
                                   text="The home widget %s broke on the board: %s. Fix %s; it is done when node "
                                        "--check and skills/brain-viewer/widgets/harness.py pass on it"
                                        % (wid, err, rel_file),
                                   source=WIDGET_BREAK_SOURCE, key=key, links=[rel_file])
                rec["filed"] = "filed"
            rec["item"] = iid
            rec["wrote"] = now
        except (ledger.LedgerError, OSError) as e:  # noqa: BLE001 -- the break is still recorded and still lights the lamp
            rec["filed"] = "refused: %s" % e    # (OSError: a brain with no registry, or no such ledger, 0.48.0)
        return 200, _widget_break_out(key, rec, rec["filed"])


def _widget_break_out(key, rec, what):
    return {"ok": True, "key": key, "id": rec["id"], "error": rec["error"], "count": rec["count"], "item": rec["item"],
            "ledger": WIDGET_BREAK_LEDGER, "result": what, "at": rec["at"].isoformat(timespec="seconds")}


def _widgets_lamp():
    """Red while any widget has broken inside the last WIDGET_BREAK_WINDOW, lit otherwise. Watching since the app started."""
    now = dt.datetime.now().astimezone()
    with WIDGET_BREAK_LOCK:
        recent = [r for r in WIDGET_BREAKS.values() if (now - r["at"]).total_seconds() < WIDGET_BREAK_WINDOW]
    if recent:
        newest = max(r["at"] for r in recent)
        names = sorted({r["id"] for r in recent})
        return {"id": "widgets", "name": "Widgets", "lastRan": newest.isoformat(timespec="seconds"), "cadence": "session",
                "state": "red", "broken": names,
                "detail": "%d broken in the last hour: %s" % (len(names), ", ".join(names))}
    return {"id": "widgets", "name": "Widgets", "lastRan": STARTED_AT.isoformat(timespec="seconds"), "cadence": "session",
            "state": "lit", "broken": [], "detail": "no tile has broken in the last hour"}


def system_api():
    """GET /api/system: one row per part of this brain that runs on its own, newest run first in each case."""
    ferry_actions = {"PULL", "PUSH", "SYNCED", "INGESTED"}
    lamps = [
        _calendar_lamp(CALENDAR_REL, "calendar", "Calendar", "session",
                       lambda n: "%d today" % n if n else "the day was read and held nothing"),
        _calendar_lamp(CALENDAR_WEEK_REL, "week", "Week ahead", "weekly",
                       lambda n: "%d in the seven days" % n if n else "the week was read and held nothing"),
        _log_lamp("pfapp", "PF App", "daily",
                  lambda r: r["agent"].lower() == "ferryman" and (r["action"] in ferry_actions or "pull" in r["text"].lower()),
                  lambda r: "the last thing it did was a %s" % r["action"].lower()),
        _log_lamp("night", "Night agent", "daily", lambda r: r["agent"].lower() == "night-agent",
                  lambda r: _lamp_say(r["text"])),
        _log_lamp("librarian", "Librarian", "weekly", lambda r: r["agent"].lower() == "librarian-sweep",
                  lambda r: _lamp_say(r["text"]), days=45),
        _git_lamp(),
    ]
    exit_rec = last_exit()
    crashed = bool(exit_rec and exit_rec.get("crash"))
    up = int((dt.datetime.now().astimezone() - STARTED_AT).total_seconds())
    lamps.append({"id": "viewer", "name": "This app", "lastRan": STARTED_AT.isoformat(timespec="seconds"),
                  "cadence": "session", "state": "red" if crashed else _system_state(STARTED_AT, "session"),
                  "detail": ("it stopped on its own last time" if crashed
                             else "up for %s" % ("%d hours" % (up // 3600) if up >= 3600 else "%d minutes" % (up // 60)))})
    lamps.append(_widgets_lamp())         # T-0217: red while any home tile has broken in the last hour
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "lamps": lamps, "count": len(lamps),
            "red": sum(1 for l in lamps if l["state"] == "red")}


# ---- the live wire (0.38.0): the brain's log as it is written ----
# The owner asked the home page's flow map to show the data moving and how everything is hooked up to the brain, with
# pulses that are truly live. Every agent in this brain appends one line to context/log.md as it works, so the honest live feed is
# that file's tail. This remembers the size, sleeps a second, and sends whatever was appended, one event per parsed
# line, in the same shape GET /api/moved answers with. A comment every fifteen seconds keeps the connection honest and
# is how a page that went away is noticed. The stream ends itself after an hour; EventSource reconnects on its own.
EVENTS_POLL = 1.0
EVENTS_BEAT = 15
EVENTS_MAX_SECONDS = 3600


def events_stream(h):
    ap = os.path.join(BRAIN, LOG_REL.replace("/", os.sep))
    h.send_response(200)
    h.send_header("Content-Type", "text/event-stream; charset=utf-8")
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Accel-Buffering", "no")
    h.end_headers()

    def write(s):
        try:
            h.wfile.write(s.encode("utf-8"))
            h.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            return False                                  # the page went away: the stream ends with it

    try:
        pos = os.path.getsize(ap) if os.path.isfile(ap) else 0
    except OSError:
        pos = 0
    if not write(": the brain's log, as it is written\n\n"):
        return
    started, beat = time.time(), time.time()
    while time.time() - started < EVENTS_MAX_SECONDS:
        time.sleep(EVENTS_POLL)
        try:
            size = os.path.getsize(ap) if os.path.isfile(ap) else 0
        except OSError:
            size = 0
        if size < pos:                                    # the log rotated under us: start again from its end
            pos = size
        if size > pos:
            try:
                with open(ap, "rb") as f:
                    f.seek(pos)
                    chunk = f.read(size - pos)
            except OSError:
                chunk = b""
            cut = chunk.rfind(b"\n")                      # a half-written line waits for its newline
            if cut >= 0:
                pos += cut + 1
                for line in chunk[:cut].decode("utf-8", errors="replace").splitlines():
                    m = MOVED_RE.match(line.strip())
                    if not m:
                        continue
                    row = {"ts": "%sT%s" % (m.group(1), m.group(2)), "agent": m.group(3).strip(),
                           "action": m.group(4), "text": re.sub(r"\s+", " ", m.group(5)).strip()}
                    if not write("data: " + json.dumps(row, ensure_ascii=False) + "\n\n"):
                        return
                beat = time.time()
        if time.time() - beat >= EVENTS_BEAT:
            if not write(": still here\n\n"):
                return
            beat = time.time()


# ---- the mantras (0.38.0): one line a day under the date ----
# A file the owner builds over time, one line per entry, plain enough that anyone on the team can add to it by typing a line.
# The page picks the day's line from the date itself, so it is the same line all day on every machine and turns over at
# midnight. Nothing here judges or ranks a line: this reads the file and appends to it.
MANTRAS_REL = str(SETTINGS.get("mantras") or "projects/pf-build/pf-mantras.md").replace("\\", "/").strip("/")   # 0.48.0: a setting; absent file = an empty pool
MANTRA_LINE_RE = re.compile(r"^[-*]\s+(.+)$")
MANTRA_MAX = 400                  # the longest line this will store


def mantras_api():
    """GET /api/mantras: the pool, in file order. Each line is `- text | author | source`, the source optional."""
    ap = os.path.join(BRAIN, MANTRAS_REL.replace("/", os.sep))
    out = {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "file": MANTRAS_REL, "today": ledger.today(),
           "exists": os.path.isfile(ap), "items": [], "count": 0, "canAdd": not PROPOSE, "propose": PROPOSE}
    if not out["exists"]:
        return out
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except OSError as e:
        out["error"] = "%s: %s" % (type(e).__name__, e)
        return out
    for raw in lines:
        m = MANTRA_LINE_RE.match(raw.strip())
        if not m:
            continue
        parts = [p.strip() for p in m.group(1).split("|")]
        text = parts[0]
        if not text:
            continue
        out["items"].append({"text": text, "author": (parts[1] if len(parts) > 1 else "") or None,
                             "source": (parts[2] if len(parts) > 2 else "") or None})
    out["count"] = len(out["items"])
    return out


def mantra_add(data):
    """POST /api/mantras {text, author, source}: one line appended to the pool. A team copy proposes it instead."""
    text = " ".join(str(data.get("text") or "").split())[:MANTRA_MAX]
    author = " ".join(str(data.get("author") or "").split())[:120]
    source = " ".join(str(data.get("source") or "").split())[:160]
    if not text:
        return {"error": "a line needs words"}
    if "|" in text or "|" in author or "|" in source:
        return {"error": "the upright bar separates the parts of a line, so it cannot be inside one"}
    line = "- %s" % text + (" | %s" % author if author else "") + (" | %s" % source if source else "")
    if PROPOSE:
        rel = propose("mantra", MANTRAS_REL, {"line": line, "text": text, "author": author, "source": source},
                      note="a line for the mantra pool")
        return {"ok": True, "proposed": True, "request": rel, "line": line}
    ap = os.path.join(BRAIN, MANTRAS_REL.replace("/", os.sep))
    if not os.path.isfile(ap):
        return {"error": "there is no %s in this copy" % MANTRAS_REL}
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            body = f.read()
        with open(ap, "a", encoding="utf-8", newline="\n") as f:
            f.write(("" if body.endswith("\n") else "\n") + line + "\n")
    except OSError as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}
    log_line("%s -- one line added to the mantra pool from the home page" % MANTRAS_REL, action="MODIFIED")
    return {"ok": True, "line": line, "count": len(mantras_api()["items"])}


def home_layout_api():
    """GET /api/home/layout: the saved file when there is one, the default built from the folder when there is not."""
    reg = widget_registry()
    rel = home_layout_rel()
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    saved, err, palette, views, mode, gravity, row_unit = None, None, None, [], "grid", False, None
    if os.path.isfile(ap):
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                doc = json.load(f)
            # T-0213: the board's mode, grid (the default, and anything the file says that is not a mode) or free
            mode = doc.get("mode") if doc.get("mode") in ("grid", "free") else "grid"
            # a file holding only the look (T-0208: picked before the board was ever arranged) is not a broken board
            gravity = doc.get("gravity") is True     # free mode's "keep closed"; anything but true reads as off
            # the fine row unit (2026-09-22): None is a board on the old 158px pitch, converted once by the page
            ru = doc.get("rowUnit")
            row_unit = ru if isinstance(ru, int) and not isinstance(ru, bool) and 8 <= ru <= 200 else None
            saved, err = (home_validate(doc.get("widgets"), reg, drop_missing=True, mode=mode, row_unit=row_unit)
                          if "widgets" in doc else (None, None))
            palette, _perr = home_palette(doc.get("palette"))   # a palette written by hand and wrong is simply not there
            views, _verr = home_views(doc.get("views"), reg, drop_missing=True)   # T-0214: the same rule for views
            views = views or []
        except Exception as e:
            err = str(e)
    return {"schema": HOME_SCHEMA, "member": home_member(), "path": rel, "saved": bool(saved), "error": err,
            "updatedAt": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds") if os.path.isfile(ap) else None,
            "widgets": saved or home_default(reg), "registry": reg, "sizes": list(HOME_SIZES),
            "rows": list(HOME_ROWS), "palette": palette, "look": look_active(), "views": views,
            "mode": mode if saved else "grid", "gravity": bool(gravity and saved),
            "rowUnit": row_unit if saved else None,
            "_servedAt": dt.datetime.now().isoformat(timespec="seconds")}


def home_layout_write(data):
    """PUT /api/home/layout: {"widgets": [...], "palette": {...}} saves, {"reset": true} deletes the file so the
    default comes back. The palette is where the add panel was left and is optional in both directions (0.40.0)."""
    rel = home_layout_rel()
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    kept_look = look_active()             # T-0208: the look is the person's, not the board's; reset and save both keep it
    # T-0214: the named views are the person's too, a library beside the board, so a reset keeps them as it keeps the look
    kept_views, kept_mode, kept_gravity, kept_unit = [], "grid", False, None
    if os.path.isfile(ap):
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                was = json.load(f)
            kept_views, _verr = home_views(was.get("views"), drop_missing=True)
            kept_views = kept_views or []
            kept_mode = was.get("mode") if was.get("mode") in ("grid", "free") else "grid"
            kept_gravity = was.get("gravity") is True
            ku = was.get("rowUnit")
            kept_unit = ku if isinstance(ku, int) and not isinstance(ku, bool) and 8 <= ku <= 200 else None
        except Exception:
            kept_views = []
    if data.get("reset"):
        try:
            os.remove(ap)
        except OSError:
            pass
        if kept_views:
            os.makedirs(os.path.dirname(ap), exist_ok=True)
            with open(ap, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"schema": HOME_SCHEMA, "member": home_member(), "views": kept_views}, f, ensure_ascii=False, indent=2)
                f.write("\n")
        if kept_look != "default":
            look_set_active(kept_look)
        return {"ok": True, "reset": True, "path": rel, "widgets": home_default(), "views": kept_views, "mode": "grid", "gravity": False}
    if "look" in data:
        picked = look_set_active(data.get("look") or "default")
        if picked.get("error"):
            return picked
        kept_look = picked["active"]
    # T-0213: the board's mode, by the palette's rule: named, it must be grid or free; not named, the file's stays
    mode = data.get("mode", kept_mode)
    if mode not in ("grid", "free"):
        return {"error": "mode must be grid or free, not %r" % (mode,)}
    gravity = data.get("gravity", kept_gravity)   # not named, the file's stays, like the mode
    # the fine row unit (2026-09-22), by the mode's rule: named, it is checked; not named, the file's stays
    row_unit = data.get("rowUnit", kept_unit)
    rows, err = home_validate(data.get("widgets"), mode=mode, gravity=gravity, row_unit=row_unit)
    if err:
        return {"error": err}
    if not (isinstance(row_unit, int) and not isinstance(row_unit, bool) and 8 <= row_unit <= 200):
        row_unit = kept_unit                  # grid mode drops a bad one without an error, as it drops a bad cell
    # the add panel's place: named, it is checked and kept; not named at all, whatever the file already held stays,
    # so a page that knows nothing about it cannot wipe it; named as null, it is cleared (which is what reset means)
    if "palette" in data:
        palette, perr = home_palette(data.get("palette"))
        if perr:
            return {"error": perr}
    else:
        palette = None
        if os.path.isfile(ap):
            try:
                with open(ap, "r", encoding="utf-8-sig") as f:
                    palette, _perr = home_palette(json.load(f).get("palette"))
            except Exception:
                palette = None
    # the named views (T-0214), by the palette's rule: named, checked and kept; not named, the file's stay
    if "views" in data:
        views, verr = home_views(data.get("views"))
        if verr:
            return {"error": verr}
    else:
        views = kept_views
    doc = {"schema": HOME_SCHEMA, "member": home_member(),
           "updatedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "widgets": rows}
    if palette:
        doc["palette"] = palette
    if views:
        doc["views"] = views
    if kept_look != "default":
        doc["look"] = kept_look
    if mode == "free":
        doc["mode"] = "free"              # T-0213: written only when free, so a grid board's file reads exactly as before
    if gravity:
        doc["gravity"] = True             # "keep closed", written only when on, by the same rule
    if row_unit:
        doc["rowUnit"] = row_unit         # the free row unit in px; absent, the cells are on the old 158px pitch
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"ok": True, "path": rel, "widgets": rows, "palette": palette, "look": kept_look, "views": views,
            "mode": mode, "gravity": gravity, "rowUnit": row_unit, "updatedAt": doc["updatedAt"]}


def help_api():
    """GET /api/help: skills/brain-viewer/help.json, one entry per route of PAGES -- what the page is in plain words and
    what its parts are. The "?" panel on any page reads its own route out of this; the home page reads it whole."""
    ap = os.path.join(BRAIN, HELP_REL.replace("/", os.sep))
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            doc = json.load(f)
    except Exception as e:
        return {"error": str(e), "file": HELP_REL, "pages": {}}
    pages = doc.get("pages") if isinstance(doc.get("pages"), dict) else doc
    return {"file": HELP_REL, "pages": pages, "routes": sorted(PAGES),
            "_servedAt": dt.datetime.now().isoformat(timespec="seconds")}


# ---- the image studio (2026-09-22, brain-viewer T-0235) ----
# The owner chose GPT image 2 and Gemini as the first two services. THE FOLDER IS THE REGISTRY:
# every *.py in skills/brain-viewer/providers/ not starting with "_" is one image service (providers/readme.md has the
# contract). They are imported here at request time, so serve.py starts whatever a provider needs; a provider that fails
# to import is listed with ready false and the import error as its reason. Each reads its own key file at the brain
# root (openai_key.txt, gemini_key.txt: in NEVER_READ, git-ignored, never exported). Pictures land in
# deliverables/studio/<job>/ with a sidecar .json beside each and a job.md that keeps the history in one line per run.
# A team copy has no keys and no studio: every route answers 403 there.
# 0.51.0 (2026-09-25): providers/comfy_local.py joined, the first provider with no key: FLUX.1 Krea on the local GPU
# through ComfyUI. Its ready() asks ComfyUI itself (is it up, is every model file listed), so it costs one short local
# call per providers listing; its graph lives in providers/comfy_workflows/, a folder this loader never imports.
# 0.51.1 (2026-09-25): the local provider edits too, as image to image (comfy_workflows/flux-krea-gguf-img2img.json);
# an edit request may carry strength (the denoise) and seed, and its Leave out and source path reach an edit that
# names negative and source, so the local edit keeps its Avoid: clause and names its source in the sidecar meta.
PROVIDERS_DIR = "providers"
STUDIO_REL = "deliverables/studio"
STUDIO_MAX_N = 4
STUDIO_TEST_PROVIDERS = {}        # id -> module; studio.test.py puts a fake provider here so no test reaches a paid API
_STUDIO_MODS = {}                 # path -> (mtime, module | Exception)
_STUDIO_LOCK = threading.Lock()


def _studio_load(path):
    import importlib.util
    mt = os.path.getmtime(path)
    hit = _STUDIO_MODS.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        spec = importlib.util.spec_from_file_location("bv_provider_" + os.path.splitext(os.path.basename(path))[0], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:          # a missing package or a syntax error: listed, not fatal
        mod = e
    _STUDIO_MODS[path] = (mt, mod)
    return mod


def studio_providers():
    """{id: module | (stem, Exception)} for every provider file, plus any injected by a test."""
    out = {}
    folder = os.path.join(HERE, PROVIDERS_DIR)
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".py") or fn.startswith("_") or fn.endswith(".test.py"):
                continue
            mod = _studio_load(os.path.join(folder, fn))
            if isinstance(mod, Exception):
                out[fn[:-3]] = (fn[:-3], mod)
            else:
                out[str(getattr(mod, "ID", fn[:-3]))] = mod
    out.update(STUDIO_TEST_PROVIDERS)
    for mod in out.values():
        if not isinstance(mod, tuple):
            mod.BRAIN = BRAIN          # the key file is read at the root of the brain this server reads
    return out


def _studio_ready(mod):
    try:
        ok, reason = mod.ready()
        return bool(ok), str(reason or "")
    except Exception as e:
        return False, _studio_line(e)


def _studio_line(e):
    """A provider's message cut to one line, with anything shaped like a key taken out."""
    text = " ".join(str(e or e.__class__.__name__).split())
    text = re.sub(r"sk-[A-Za-z0-9_\-]{8,}|AIza[A-Za-z0-9_\-]{20,}", "[key]", text)
    return text[:300]


def studio_providers_api():
    rows = []
    for pid, mod in studio_providers().items():
        if isinstance(mod, tuple):
            err = mod[1]
            missing = getattr(err, "name", None) if isinstance(err, ImportError) else None
            rows.append({"id": pid, "name": pid, "ready": False, "keyFile": None, "models": [],
                         "reason": ("pip install %s" % missing) if missing else "the provider file did not load: " + _studio_line(err)})
            continue
        ok, reason = _studio_ready(mod)
        rows.append({"id": pid, "name": str(getattr(mod, "NAME", pid)), "ready": ok, "reason": reason,
                     "keyFile": getattr(mod, "KEY_FILE", None), "models": list(getattr(mod, "MODELS", []) or [])})
    return {"providers": rows, "folder": "skills/brain-viewer/%s/" % PROVIDERS_DIR, "root": STUDIO_REL + "/"}


def _studio_slug(s, cap=60):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")[:cap].strip("-")


class StudioBadInput(Exception):
    """A request the server refuses before any provider is called (400)."""


def _studio_image_bytes(rel, what):
    ap = image_abs(rel)
    if not ap or not os.path.isfile(ap):
        raise StudioBadInput("%s is not an image in the brain: %s" % (what, rel))
    with open(ap, "rb") as f:
        return f.read()


def _studio_row(rel, side):
    return {"path": rel, "url": "/api/image?path=" + urllib.parse.quote(rel), "provider": side.get("provider"),
            "model": side.get("model"), "prompt": side.get("prompt"), "createdAt": side.get("createdAt"),
            "sidecar": os.path.splitext(rel)[0] + ".json", "candidate": bool(side.get("candidate")),
            "kind": side.get("kind", "generate")}


def _studio_call(fn, *args, **kw):
    """Call a provider with the options it declares: quality or image_size go only to a function that names them."""
    import inspect
    try:
        params = inspect.signature(fn).parameters
        if not any(p.kind == p.VAR_KEYWORD for p in params.values()):
            kw = {k: v for k, v in kw.items() if k in params or k in ("mask", "negative", "references")}
    except (TypeError, ValueError):
        pass
    return fn(*args, **kw)


def _studio_names(fn, name):
    """True when a provider function declares the parameter by name (a **kwargs catch-all does not count)."""
    import inspect
    try:
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def studio_run(kind, data):
    """POST /api/studio/generate and /api/studio/edit -> (code, answer). Writes the pictures, their sidecars, the job.md
    line and one CREATED log line per run."""
    data = data if isinstance(data, dict) else {}
    provs = studio_providers()
    pid = str(data.get("provider") or "")
    mod = provs.get(pid)
    if mod is None:
        return 400, {"error": "no provider named %r; the ones there are: %s" % (pid, ", ".join(sorted(provs)) or "none")}
    if isinstance(mod, tuple):
        return 400, {"error": "the %s provider did not load: %s" % (pid, _studio_line(mod[1])), "ready": False}
    ok, reason = _studio_ready(mod)
    if not ok:
        return 400, {"error": reason, "ready": False}
    models = [m.get("id") for m in (getattr(mod, "MODELS", []) or [])]
    model = str(data.get("model") or (models[0] if models else ""))
    if models and model not in models:
        return 400, {"error": "%s has no model %r; it has %s" % (pid, model, ", ".join(models))}
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        return 400, {"error": "the prompt is empty"}
    job = _studio_slug(data.get("job")) or "untitled"
    negative = data.get("negative") or None
    size = data.get("size") or None
    extra = {}
    if data.get("quality"):
        extra["quality"] = str(data["quality"])
    if data.get("imageSize"):
        extra["image_size"] = str(data["imageSize"])
    # 0.51.1: an image-to-image edit's strength (0 < s <= 1) and a fixed seed, sent to a provider that names them
    if data.get("strength") not in (None, ""):
        try:
            extra["strength"] = float(data["strength"])
        except (TypeError, ValueError):
            extra["strength"] = -1.0
        if not 0 < extra["strength"] <= 1:
            return 400, {"error": "strength is a number above 0 and at most 1"}
    if data.get("seed") not in (None, ""):
        try:
            extra["seed"] = int(data["seed"])
        except (TypeError, ValueError):
            return 400, {"error": "seed is a whole number"}
    try:
        if kind == "edit":
            src = str(data.get("image") or "")
            img = _studio_image_bytes(src, "the image")
            mask_rel = str(data.get("mask") or "") or None
            mask = _studio_image_bytes(mask_rel, "the mask") if mask_rel else None
            refs, n = [], 1
            # the Leave out list and the source's path go only to an edit that names them (the local provider does)
            named = {k: v for k, v in (("negative", negative), ("source", src)) if v and _studio_names(mod.edit, k)}
            got = _studio_call(mod.edit, img, prompt, model, mask=mask, **dict(extra, **named))
        else:
            src = mask_rel = None
            try:
                n = 2 if data.get("n") in (None, "") else int(data.get("n"))
            except (TypeError, ValueError):
                return 400, {"error": "n is a number from 1 to %d" % STUDIO_MAX_N}
            if not 1 <= n <= STUDIO_MAX_N:
                return 400, {"error": "n is a number from 1 to %d" % STUDIO_MAX_N}
            refs = [str(r) for r in (data.get("references") or []) if str(r).strip()]
            ref_bytes = [_studio_image_bytes(r, "a reference") for r in refs]
            got = _studio_call(mod.generate, prompt, model, n, size, negative=negative, references=ref_bytes or None, **extra)
    except StudioBadInput as e:
        return 400, {"error": str(e)}
    except NotImplementedError as e:
        return 400, {"error": _studio_line(e) or "%s cannot do that" % model}
    except Exception as e:
        return 502, {"error": _studio_line(e), "provider": pid}
    if not got:
        return 502, {"error": "%s answered with no picture" % pid, "provider": pid}
    now = dt.datetime.now().astimezone()
    stamp, created = now.strftime("%Y%m%d-%H%M%S"), now.isoformat(timespec="seconds")
    folder_rel = "%s/%s" % (STUDIO_REL, job)
    folder = os.path.join(BRAIN, folder_rel.replace("/", os.sep))
    mshort = _studio_slug(model, 40) or "model"
    images = []
    with _STUDIO_LOCK:
        os.makedirs(folder, exist_ok=True)
        i = 0
        for item in got:
            blob, ext, meta = (list(item) + [None, None])[:3]
            ext = _studio_slug(ext or "png", 5) or "png"
            if ext == "jpeg":
                ext = "jpg"
            i += 1
            name = "%s-%s-%s-%d" % (stamp, _studio_slug(pid, 20), mshort, i)
            while os.path.exists(os.path.join(folder, name + "." + ext)):
                i += 1
                name = "%s-%s-%s-%d" % (stamp, _studio_slug(pid, 20), mshort, i)
            rel = "%s/%s.%s" % (folder_rel, name, ext)
            with open(os.path.join(folder, name + "." + ext), "wb") as f:
                f.write(blob)
            side = {"prompt": prompt, "negative": negative, "provider": pid, "model": model, "size": size,
                    "references": refs, "createdAt": created, "candidate": False, "kind": kind, "job": job,
                    "project": data.get("project") or None}
            if kind == "edit":
                side["source"] = src
                side["mask"] = mask_rel
            if extra:
                side["options"] = extra
            if isinstance(meta, dict) and meta:
                side["meta"] = meta
            with open(os.path.join(folder, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(side, f, ensure_ascii=False, indent=2)
            images.append(_studio_row(rel, side))
        jm = os.path.join(folder, "job.md")
        fresh = not os.path.isfile(jm)
        with open(jm, "a", encoding="utf-8", newline="\n") as f:
            if fresh:
                f.write("# Studio job: %s\n\nOne line per run: when, provider, model, how many pictures, the prompt's first 80 characters.\n\n" % job)
            f.write("- %s | %s | %s | %d %s | %s%s\n" % (created, pid, model, len(images), "edit" if kind == "edit" else "images",
                                                       " ".join(prompt.split())[:80], "" if len(prompt) <= 80 else "..."))
    log_line("%s/ -- image studio %s: %d picture%s from %s %s" % (folder_rel, kind, len(images), "" if len(images) == 1 else "s", pid, model),
             action="CREATED")
    return 200, {"job": job, "folder": folder_rel + "/", "images": images}


def _studio_sidecar(rel):
    rel = norm(rel)
    if not rel or not rel.startswith(STUDIO_REL + "/") or os.path.splitext(rel)[1].lower() not in IMAGE_EXT:
        return None, None
    ap = os.path.join(BRAIN, (os.path.splitext(rel)[0] + ".json").replace("/", os.sep))
    return rel, ap


def studio_candidate(data):
    data = data if isinstance(data, dict) else {}
    rel, ap = _studio_sidecar(str(data.get("path") or ""))
    if not rel:
        return 400, {"error": "not a studio picture: the path must be an image under %s/" % STUDIO_REL}
    if not os.path.isfile(ap):
        return 404, {"error": "no sidecar beside %s" % rel}
    if not isinstance(data.get("candidate"), bool):
        return 400, {"error": "candidate is true or false"}
    with _STUDIO_LOCK:
        with open(ap, "r", encoding="utf-8-sig") as f:
            side = json.load(f)
        side["candidate"] = data["candidate"]
        with open(ap, "w", encoding="utf-8") as f:
            json.dump(side, f, ensure_ascii=False, indent=2)
    return 200, {"path": rel, "candidate": side["candidate"], "image": _studio_row(rel, side)}


def studio_jobs():
    root = os.path.join(BRAIN, STUDIO_REL.replace("/", os.sep))
    jobs = []
    if os.path.isdir(root):
        for slug in sorted(os.listdir(root)):
            folder = os.path.join(root, slug)
            if not os.path.isdir(folder):
                continue
            imgs = []
            for fn in os.listdir(folder):
                if os.path.splitext(fn)[1].lower() not in IMAGE_EXT:
                    continue
                rel = "%s/%s/%s" % (STUDIO_REL, slug, fn)
                side = {}
                sp = os.path.join(folder, os.path.splitext(fn)[0] + ".json")
                try:
                    with open(sp, "r", encoding="utf-8-sig") as f:
                        side = json.load(f)
                except Exception:
                    side = {"createdAt": dt.datetime.fromtimestamp(os.path.getmtime(os.path.join(folder, fn))).astimezone().isoformat(timespec="seconds")}
                imgs.append(_studio_row(rel, side))
            imgs.sort(key=lambda r: (str(r.get("createdAt") or ""), r["path"]), reverse=True)
            jobs.append({"slug": slug, "count": len(imgs), "latest": imgs[0]["createdAt"] if imgs else None,
                         "candidates": sum(1 for r in imgs if r["candidate"]), "images": imgs,
                         "history": "%s/%s/job.md" % (STUDIO_REL, slug) if os.path.isfile(os.path.join(folder, "job.md")) else None})
    jobs.sort(key=lambda j: str(j["latest"] or ""), reverse=True)
    return {"jobs": jobs, "root": STUDIO_REL + "/"}


FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def studio_prompts(rel):
    """GET /api/studio/prompts?path=<.md>: every fenced code block of that file, titled by the nearest heading above it."""
    ap = read_abs(rel)
    if not ap or not ap.lower().endswith(".md"):
        return 400, {"error": "the path must be a markdown file in the brain"}
    if not os.path.isfile(ap):
        return 404, {"error": "no such file: %s" % rel}
    with open(ap, "r", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    out, title, fence, buf, start = [], "", None, [], 0
    for no, line in enumerate(lines, 1):
        if fence:
            if line.strip().startswith(fence) and not line.strip()[len(fence):].strip():
                out.append({"title": title, "text": "\n".join(buf).strip("\n"), "line": start, "lang": lang})
                fence, buf = None, []
            else:
                buf.append(line)
            continue
        m = FENCE_RE.match(line)
        if m:
            fence, buf, start, lang = m.group(1), [], no, line.strip()[len(m.group(1)):].strip()
            continue
        h = HEADING_RE.match(line)
        if h:
            title = h.group(2)
    return 200, {"path": norm(rel), "prompts": out}


def studio_api(method, path, q, body):
    """Every /api/studio/* route -> (code, answer), or None when the path is not one of them."""
    if not path.startswith("/api/studio/"):
        return None
    if PROPOSE:
        return 403, {"error": "the image studio runs on the owner's machine only; a team copy has no provider keys"}
    try:
        if method == "GET":
            if path == "/api/studio/providers":
                return 200, studio_providers_api()
            if path == "/api/studio/jobs":
                return 200, studio_jobs()
            if path == "/api/studio/prompts":
                return studio_prompts(q.get("path", [""])[0])
            return 404, {"error": "no studio route %s" % path}
        data = json.loads(body or "{}")
        if path == "/api/studio/generate":
            return studio_run("generate", data)
        if path == "/api/studio/edit":
            return studio_run("edit", data)
        if path == "/api/studio/candidate":
            return studio_candidate(data)
        return 404, {"error": "no studio route %s" % path}
    except json.JSONDecodeError:
        return 400, {"error": "the body is not JSON"}


class H(BaseHTTPRequestHandler):
    server_version = "brain-viewer/" + VERSION

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (dt.datetime.now().strftime("%H:%M:%S"), fmt % args))

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path in PAGES:
                page = PAGES[u.path]
                if u.path in HOME_ROUTES and PROPOSE:
                    page = "mentee-dashboard.html"      # a team copy has no chat: its home stays the dashboard
                with open(os.path.join(HERE, page), "r", encoding="utf-8") as f:
                    html = f.read()
                # the mode rides in with the page so the team strip renders synchronously (no fetch, no flash); viewer-common.js reads window.BV_MODE
                html = html.replace("</head>", "<script>window.BV_MODE=%s;window.BV_OWNER=%s;</script>\n</head>"
                                    % (json.dumps(mode_info(), ensure_ascii=False).replace("</", "<\\/"), json.dumps(OWNER)), 1)
                html = look_head(html)          # the member's look, in the head before first paint (T-0208)
                return self._send(200, html, "text/html; charset=utf-8")
            if u.path == "/api/health":
                # is it up, which build, since when, over which brain (2026-09-17, T-0181). Cheap on purpose: a morning
                # session asks this before it asks anything else, and a recap that cannot reach it reports the viewer down.
                now = dt.datetime.now().astimezone()
                return self._send(200, {"ok": True, "version": VERSION, "pid": os.getpid(),
                                        "startedAt": STARTED_AT.isoformat(timespec="seconds"),
                                        "uptimeSeconds": int((now - STARTED_AT).total_seconds()),
                                        "now": now.isoformat(timespec="seconds"),
                                        "brain": BRAIN, "code": CODE, "mode": mode_info()["mode"],
                                        "port": getattr(ARGS, "port", None) if "ARGS" in globals() else None,
                                        "supervised": bool(os.environ.get("BV_SUPERVISED")),
                                        "crashLog": CRASH_REL, "lastExit": last_exit(), "previousRun": PREV_RUN})
            if u.path == "/api/search":
                # file search (2026-09-17, T-0158): by name and by text over the live files, capped at 50
                try:
                    lim = max(1, min(SEARCH_MAX, int((q.get("limit") or [str(SEARCH_MAX)])[0])))
                except ValueError:
                    lim = SEARCH_MAX
                return self._send(200, search_api(q.get("q", [""])[0], lim))
            if u.path == "/api/files":
                # the Files page (0.52.0, T-0259): every file in the brain but .git, node_modules, __pycache__ and the keys
                g = lambda k: (q.get(k) or [""])[0]
                return self._send(200, files_api(g("folder"), g("type"), g("q"), g("sort") or "modified", g("order")))
            if u.path == "/api/file-raw":
                # a file's bytes as a download, for what the viewer cannot show (xlsx, docx, pdf, psd...). Brain tree only:
                # a path that climbs out, names a drive, sits in a skipped folder or is a key file is refused
                ap = files_abs(q.get("path", [""])[0])
                if not ap:
                    return self._send(403, {"error": "not a file this page serves"})
                if not os.path.isfile(ap):
                    return self._send(404, {"error": "file not found"})
                ext = os.path.splitext(ap)[1].lower()
                ctype = FILES_RAW_TYPES.get(ext) or IMAGE_EXT.get(ext) or "application/octet-stream"
                with open(ap, "rb") as f:
                    body = f.read()
                leaf = os.path.basename(ap)
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''%s" % urllib.parse.quote(leaf))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if u.path == "/api/mode":
                return self._send(200, mode_info())
            if u.path.startswith("/api/studio/"):
                # the image studio (T-0235): providers, jobs and the prompts of a markdown file; 403 in a team copy
                code, out = studio_api("GET", u.path, q, None)
                return self._send(code, out)
            if u.path == "/api/looks":
                # the looks folder, which IS the registry, and this member's active look (T-0208)
                return self._send(200, looks_api())
            if u.path == "/api/widgets":
                # the home page's registry: the *.js files in skills/brain-viewer/widgets/, which IS the registry
                reg = widget_registry()
                return self._send(200, {"folder": "skills/brain-viewer/" + WIDGETS_DIR, "userFolder": USER_WIDGETS_REL + "/",
                                        "contract": WIDGET_CONTRACT, "count": len(reg), "widgets": reg,
                                        "_servedAt": dt.datetime.now().isoformat(timespec="seconds")})
            if u.path == "/api/home/layout":
                # which widgets are on, in what order, at what size -- per member, in a file, so it survives the browser
                return self._send(200, home_layout_api())
            if u.path == "/api/help":
                # what each page of this app is for, in plain words: the "?" panel reads it
                return self._send(200, help_api())
            if u.path == "/api/calendar/week":
                # the next seven days as the session start wrote them: what the home page's dial draws past today
                return self._send(200, calendar_week_api())
            if u.path == "/api/call":
                # the call screen's one read (0.47.0): the event, its people with their cards, the prep in its parts
                if PROPOSE:
                    return self._send(403, {"error": "call preps and people cards are not part of a team copy"})
                code, out = call_api(q.get("prep", [""])[0] or None, q.get("date", [""])[0] or None, q.get("start", [""])[0] or None)
                return self._send(code, out)
            if u.path == "/api/moved":
                # the tail of the brain's log, parsed: what moved since a moment, newest first; one writer with agent=,
                # a window of days back with days= (0.38.0, the moon)
                return self._send(200, moved_api(q.get("since", [""])[0], (q.get("limit") or [MOVED_DEFAULT])[0],
                                                 q.get("agent", [""])[0], q.get("days", [""])[0]))
            if u.path == "/api/system":
                # the lamps (0.38.0): every part of this brain that runs on its own, and when it last ran
                return self._send(200, system_api())
            if u.path == "/api/events":
                # the live wire (0.38.0): context/log.md as it is written, one event per line, until the page goes away
                return events_stream(self)
            if u.path == "/api/mantras":
                # the line under the date (0.38.0): the pool the owner builds over time, in file order
                return self._send(200, mantras_api())
            if u.path == "/api/requests":
                return self._send(200, requests_api())
            if u.path == "/api/exchange":
                if PROPOSE:
                    return self._send(403, {"error": "an exchange is between two owners' own machines; a team copy has none"})
                return self._send(200, exchange_state())
            if u.path == "/favicon.ico":
                # every page declares /static/sun-favicon.png, and the browser asks for this anyway: answering it with the
                # same file is the difference between a console with one permanent error in it and a clean one (T-0065)
                u = u._replace(path="/static/sun-favicon.png")
            if u.path.startswith("/static/"):
                fn = os.path.basename(u.path)
                ext = os.path.splitext(fn)[1].lower()
                folder = HERE
                if u.path.startswith("/static/vendor/"):   # the vendored library (2026-09-09, /map): vendor/<file>.js only, nothing deeper, nothing else
                    if ext != ".js":
                        return self._send(404, {"error": "no such static file"})
                    folder = os.path.join(HERE, "vendor")
                if u.path.startswith("/static/%s/" % WIDGETS_DIR):   # the home page's widgets (2026-09-21): widgets/<file>.js only
                    if ext != ".js":
                        return self._send(404, {"error": "no such static file"})
                    folder = os.path.join(HERE, WIDGETS_DIR)
                if u.path.startswith("/static/%s/" % LOOKS_DIR):     # the looks (2026-09-22, T-0208): looks/<file>.css only
                    if ext != ".css":
                        return self._send(404, {"error": "no such static file"})
                    folder = os.path.dirname(look_abs(fn[:-4]))       # 0.48.0: a core look, else the user layer's
                if u.path.startswith("/static/user-widgets/"):        # 0.48.0: a widget a person wrote, from viewer/widgets/
                    if ext != ".js":
                        return self._send(404, {"error": "no such static file"})
                    folder = os.path.join(BRAIN, USER_WIDGETS_REL.replace("/", os.sep))
                if (ext not in STATIC_TEXT and ext not in STATIC_BYTES) or not os.path.isfile(os.path.join(folder, fn)):
                    return self._send(404, {"error": "no such static file"})
                if ext in STATIC_BYTES:   # the sun mark + the tab icon (2026-09-08): bytes, no decoding
                    with open(os.path.join(folder, fn), "rb") as f:
                        return self._send(200, f.read(), STATIC_BYTES[ext])
                with open(os.path.join(folder, fn), "r", encoding="utf-8") as f:
                    return self._send(200, f.read(), STATIC_TEXT[ext])
            if u.path == "/api/manifest":
                m = manifest()
                for st in m.get("stages", []):
                    for p in st.get("pieces", []):
                        if p.get("path"):
                            ap = os.path.join(BRAIN, p["path"].replace("/", os.sep))
                            p["exists"] = os.path.isfile(ap)
                            p["mtime"] = dt.datetime.fromtimestamp(os.path.getmtime(ap)).strftime("%Y-%m-%d") if p["exists"] else None
                            p["bytes"] = os.path.getsize(ap) if p["exists"] else None
                m["_brain"] = BRAIN; m["_servedAt"] = dt.datetime.now().isoformat(timespec="seconds")
                return self._send(200, m)
            if u.path == "/api/file":
                ap = read_abs(q.get("path", [""])[0]) or files_view_abs(q.get("path", [""])[0])   # 0.52.0: + code, csv, archive/, read-only
                if not ap:
                    return self._send(403, {"error": "path not readable here"})
                if not os.path.isfile(ap):
                    return self._send(404, {"error": "file not found"})
                with open(ap, "r", encoding="utf-8-sig") as f:
                    text = f.read()
                return self._send(200, {"path": q["path"][0], "text": text, "editable": writable(q["path"][0]),
                                        "editReason": reader_write_rule(q["path"][0])[1],   # the one line the Reader shows when it cannot edit (T-0220)
                                        "today": ledger.today(),   # the Reader stamps "struck <date>" from the server's clock, never the browser's
                                        "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")})
            if u.path == "/api/image":
                ap = image_abs(q.get("path", [""])[0])
                if not ap:   # 0.52.0: an image the Files page lists outside the live folders (archive/) opens too
                    fa = files_abs(q.get("path", [""])[0])
                    ap = fa if fa and os.path.splitext(fa)[1].lower() in IMAGE_EXT else None
                if not ap:
                    return self._send(403, {"error": "not an image path under the brain"})
                if not os.path.isfile(ap):
                    return self._send(404, {"error": "image not found"})
                with open(ap, "rb") as f:
                    return self._send(200, f.read(), IMAGE_EXT[os.path.splitext(ap)[1].lower()])
            if u.path == "/api/canvas":
                ap = read_abs(q.get("path", [""])[0])
                if not ap or not ap.endswith(".canvas") or not os.path.isfile(ap):
                    return self._send(404, {"error": "canvas not found"})
                with open(ap, "r", encoding="utf-8-sig") as f:
                    return self._send(200, json.load(f))
            if u.path == "/api/canvases":
                return self._send(200, {"canvases": canvases(), "root": ARCH_REL})
            if u.path == "/api/forge":
                # the Forge (2026-09-09, T-0041): one read for the design surface -- the drawing, its .forge.json sibling, the write scope
                row, err = forge_api(q.get("path", [""])[0])
                return self._send(404 if err else 200, {"error": err} if err else row)
            if u.path == "/api/forge/fields":
                # the mouth's shelf (2026-09-10, T-0091): the loose fields one cell can ship, read from the real records
                # behind it at request time. The drawing carries a pointer; the field list is never stored in it.
                row, err = forge_fields_api(q.get("path", [""])[0], q.get("node", [""])[0])
                return self._send(404 if err else 200, {"error": err} if err else row)
            if u.path == "/api/live":
                # the live maps (2026-09-09, T-0042): every node of a canvas bound to the real thing it stands for, lit by the last 14 days of evidence
                row, err = live_api(q.get("path", [""])[0])
                return self._send(404 if err else 200, {"error": err} if err else row)
            if u.path == "/api/adapter":
                # the adapter level (2026-09-18, viewer Q-0022): one boundary's ports, cables and drift,
                # generated from the app's own catalog plus who in the brain calls what. Nothing is stored
                # in the canvas; the markdown twin is rewritten from the same answer so the two cannot
                # disagree. ?twin=0 answers without touching the file (the page asks on every zoom).
                if adapters is None:
                    return self._send(501, {"error": "the adapter generator did not load: %s" % _ADAPTER_ERR})
                name = (q.get("name", ["ferryman"])[0] or "ferryman").strip()
                row, err = adapters.adapter_api(name, BRAIN)
                if err:
                    return self._send(404, {"error": err})
                if (q.get("twin", ["1"])[0] or "1") not in ("0", "no", "false") and not PROPOSE:
                    try:
                        row["twinWritten"] = adapters.write_twin(name, BRAIN)[2]
                    except Exception as e:                       # noqa: BLE001
                        row["twinError"] = "%s: %s" % (type(e).__name__, e)
                return self._send(200, row)
            if u.path == "/api/adapters":
                # the registry (2026-09-18, viewer Q-0024): WHICH boundaries exist is a file now,
                # skills/brain-viewer/adapters.json, so an `**Adapter · <name>**` head dropped on any
                # canvas binds by name without a code change
                if adapters is None:
                    return self._send(200, {"adapters": [], "rows": [], "error": _ADAPTER_ERR})
                return self._send(200, adapters.list_adapters(BRAIN))
            if u.path == "/api/maps":
                # the maps picker: the canvases that are maps, by purpose, from skills/brain-viewer/maps-manifest.json, each with its live counts
                return self._send(200, maps_api())
            if u.path == "/api/holons":
                return self._send(200, holons_api())
            if u.path == "/api/status":
                return self._send(200, status_api())
            if u.path == "/api/projects":
                return self._send(200, projects_api())
            if u.path == "/api/findings":
                # the findings queue (2026-09-17, piece 5): every open item carrying a #source: tag, across every ledger
                return self._send(200, findings_api(q.get("source", [""])[0], q.get("project", [""])[0], q.get("owner", [""])[0]))
            if u.path == "/api/review":
                # the rating surface (2026-09-17, T-0166): the cards waiting to be rated, the counter, and the rule the
                # cards were built by -- so the page never has to describe the rule in its own words
                return self._send(200, review_api())
            if u.path == "/api/today/tasks":
                # the Today page's third block (2026-09-18, T-0185, layout A): every open task of the owner's across the
                # ledgers regardless of date, grouped by project. `?app=1` answers with the review-queue count ALONE --
                # the foot line -- so a slow call to the PF App never holds up the list above it.
                if (q.get("app", [""])[0] or "") in ("1", "yes", "true"):
                    return self._send(200, {"app": app_suggested()})
                return self._send(200, today_tasks_api())
            if u.path in ("/api/pending", "/api/calls", "/api/landed"):
                # the Today page's three outside halves (2026-09-16, T-0150): what the app holds for review, today's
                # calls with their preps, and what landed in the transcript folders. Read at request time, stored nowhere.
                if u.path == "/api/landed":
                    return self._send(200, landed_api())
                if PROPOSE:
                    return self._send(403, {"error": "not part of a team copy: the app proxy is off here, and people/ and the preps do not travel"})
                return self._send(200, pending_api() if u.path == "/api/pending" else calls_api())
            if u.path == "/api/badges":
                # the notification counts: open items waiting on the owner, per person and per project. Read by every panel's nav
                # and, next, by the bubbles home (ideas E16). people/ is absent in a team copy, so `people` is simply empty there.
                return self._send(200, badges_api())
            if u.path == "/api/waiting":
                # what the home page pins on top: the same open-for-the-owner rows, grouped by project (2026-09-09, the filtering rule)
                return self._send(200, waiting_api())
            if u.path == "/api/quests":
                # the quest log (2026-09-09, step 2c): what is waiting to be tested, and the timeline of what is done
                return self._send(200, quests_api())
            if u.path == "/api/stages":
                # the stage line (2026-09-09, T-0064): the Straight-line milestone read back as an ordered build order
                return self._send(200, stages_api())
            if u.path == "/api/docasks":
                # the section asks on one document (2026-09-09, the Reader): open ledger items linking it, with their heading fragments
                return self._send(200, doc_asks(q.get("path", [""])[0]))
            if u.path == "/api/notes":
                # what the notepad has written, newest first: the panel lists them so a note can be reached again (T-0074)
                try:
                    n = max(1, min(50, int((q.get("limit") or ["8"])[0])))
                except ValueError:
                    n = 8
                return self._send(200, notes_api(n))
            if u.path == "/api/note":
                # ONE note, opened to be edited (2026-09-16, T-0146): the header lines, the body, the pictures under it
                row = note_read(q.get("path", [""])[0])
                if not row:
                    return self._send(404, {"error": "no such note in %s/" % CAPTURE_REL})
                return self._send(200, row)
            if u.path == "/api/glossary":
                # the vocabulary (2026-09-09, step 2): parsed from the markdown seed on every call, so the owner's edit is live
                # on the next reload. Every page reads it for the hover definitions; /glossary renders it whole.
                return self._send(200, glossary_api())
            if u.path == "/api/graph":
                # the bubbles (2026-09-09, ideas E14 + E16): one graph joined at read time; a team copy gets projects, documents and the copy itself
                return self._send(200, graph_api())
            if u.path in ("/api/chats", "/api/chat"):
                # chat runs on the owner's machine and account (rules §4, 2026-09-09): a team copy has no chat at all
                if PROPOSE:
                    return self._send(403, {"error": "Chat runs on the owner's machine; in a team copy, use your own Claude Code in this folder"})
                if u.path == "/api/chats":
                    return self._send(200, chats_api())
                row, err = chat_api((q.get("id") or [""])[0].strip())
                return self._send(404 if err else 200, {"error": err} if err else row)
            if u.path in ("/api/agents", "/api/session"):
                # Read-only, and this machine only: the transcripts are private to it and never travel with a team copy.
                if PROPOSE:
                    return self._send(403, {"error": "the Agents panel is not available in a team copy: session transcripts stay on the machine that ran them"})
                if u.path == "/api/agents":
                    return self._send(200, agents_api())
                # one session read back, read-only: what a double-click on a bubble opens (2026-09-10, T-0117)
                row, err = session_view((q.get("id") or [""])[0].strip())
                return self._send(404 if err else 200, {"error": err} if err else row)
            if u.path in ("/api/people", "/api/person", "/api/preps", "/api/groups", "/api/people/week"):
                # people/ never travels with a team copy (rules 6): the whole panel is off there, not merely read-only.
                if PROPOSE:
                    return self._send(403, {"error": "People cards are not part of a team copy"})
                if u.path == "/api/people":
                    return self._send(200, people_api())
                if u.path == "/api/people/week":
                    return self._send(200, people_week_api())
                if u.path == "/api/groups":
                    return self._send(200, groups_api())
                if u.path == "/api/preps":
                    s = ((q.get("key") or q.get("slug") or [""])[0] or "").strip() or None
                    return self._send(200, {"key": s, "slug": s, "folder": CALLPREP_REL, "preps": preps(s)})
                row, err = person_api(q.get("slug", [""])[0])
                return self._send(404 if err else 200, {"error": err} if err else row)
            if u.path == "/api/resolve":
                name = os.path.basename((q.get("name", [""])[0] or "").strip())
                if not name:
                    return self._send(400, {"error": "name required"})
                m = resolve_map()
                cands = m.get(name) or m.get(name + ".md") or m.get(name + ".canvas") or []
                if len(cands) == 1:
                    return self._send(200, {"path": cands[0]})
                if not cands:
                    return self._send(404, {"error": "no file named %s" % name})
                return self._send(300, {"error": "ambiguous", "candidates": cands})
            if u.path.startswith("/api/app/"):
                if PROPOSE:
                    return self._send(403, {"error": "the PF App proxy is off in a team copy (propose mode): no token file is read here"})
                ep = u.path[len("/api/app/"):].strip("/")
                if ep not in APP_ALLOW:
                    return self._send(403, {"error": "endpoint not allowed: %s" % ep})
                kind = q.get("token", [APP_ALLOW[ep]])[0]
                req = urllib.request.Request(APP_BASE + "/" + ep, headers={"User-Agent": "brain-viewer/" + VERSION, "Authorization": "Bearer " + read_token(kind), "Accept": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=30) as r:
                        return self._send(200, r.read(), r.headers.get("Content-Type", "application/json"))
                except urllib.error.HTTPError as e:
                    return self._send(e.code, {"error": "app returned %s" % e.code, "body": e.read().decode("utf-8", "replace")[:500]})
                except Exception as e:
                    return self._send(502, {"error": "app unreachable: %s" % e})
            return self._send(404, {"error": "no such route"})
        except Exception as e:
            return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

    def do_PUT(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8")
        try:
            if u.path == "/api/manifest":
                data = json.loads(body)
                if PROPOSE:
                    req = propose("manifest", MANIFEST_REL, {"manifest": data})
                    return self._send(202, {"proposed": True, "request": req, "kind": "manifest", "target": MANIFEST_REL})
                ap = os.path.join(BRAIN, MANIFEST_REL.replace("/", os.sep))
                with open(ap, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2); f.write("\n")
                return self._send(200, {"ok": True, "path": MANIFEST_REL})
            if u.path == "/api/file":
                rel = q.get("path", [""])[0]
                ap = write_abs(rel)
                if not ap:
                    return self._send(403, {"error": "not a writable path: %s" % reader_write_rule(rel)[1]})
                if norm(rel) == MANIFEST_REL:
                    json.loads(body)
                if forge_path(rel):
                    # the Forge's two files must stay readable by Obsidian and by the Forge itself: a .canvas is an object with
                    # nodes and edges lists, a .forge.json an object -- anything else is refused before it can reach the disk
                    doc = json.loads(body)
                    if not isinstance(doc, dict) or (rel.lower().endswith(".canvas") and not (isinstance(doc.get("nodes"), list) and isinstance(doc.get("edges"), list))):
                        return self._send(400, {"error": "not a canvas: expected an object with nodes and edges lists"})
                # `note=` says what the write was, in one line, and becomes the log line's text (the Reader sends
                # "Reader: struck <the item>"). Collapsed and clipped here so nothing a page sends can shape the log file.
                said = " ".join(((q.get("note") or [""])[0] or "").split())[:160]
                nl = "\n"
                if os.path.isfile(ap):
                    with open(ap, "rb") as f:
                        if b"\r\n" in f.read(4096):
                            nl = "\r\n"
                text = body.replace("\r\n", "\n")
                if nl == "\r\n":
                    text = text.replace("\n", "\r\n")
                if PROPOSE:
                    req = propose("file", norm(rel), {"content": text}, note=said)
                    return self._send(202, {"proposed": True, "request": req, "kind": "file", "target": norm(rel), "bytes": len(text.encode("utf-8"))})
                with open(ap, "w", encoding="utf-8", newline="") as f:
                    f.write(text)
                what = said or ("edited in %s (brain-viewer, %d bytes)"
                                % ("the People panel's prep editor" if norm(rel).startswith(CALLPREP_REL + "/") else "the Forge" if forge_path(rel) else "the Mentee Content Dashboard",
                                   len(text.encode("utf-8"))))
                note = log_line("%s -- %s" % (norm(rel), what))
                return self._send(200, {"ok": True, "path": norm(rel), "bytes": len(text.encode("utf-8")), "log": note})
            if u.path == "/api/notepad":
                # editing a note in place (2026-09-16, T-0146): the same folder the notepad writes into, one file that
                # already exists, and only its body. The title, the **Taken:** line and the pictures are written back
                # exactly as they were read, so nothing an edit sends can rewrite what the note says it is.
                data = json.loads(body or "{}")
                rel = str(data.get("path") or "")
                if not note_abs(rel):
                    return self._send(403, {"error": "a note is edited where it lives: an existing .md directly inside %s/" % CAPTURE_REL})
                text = str(data.get("text") or "").replace("\r\n", "\n").strip()
                if not text:
                    return self._send(400, {"error": "a note cannot be emptied here; delete the file yourself if that is what you mean"})
                if PROPOSE:
                    return self._send(403, {"error": "a team copy does not edit the owner's notes: write your own note instead"})
                rel, n = notepad_edit(rel, text)
                note = log_line("%s -- note edited in the viewer's notepad (brain-viewer, %d bytes)" % (rel, n))
                return self._send(200, {"ok": True, "path": rel, "bytes": n,
                                        "reader": "/reader?path=" + urllib.parse.quote(rel), "log": note})
            if u.path == "/api/home/layout":
                # the home page's own layout, saved for whoever this copy belongs to. It says nothing about the brain, so
                # it is written in place in a team copy too (each copy holds its own member's file, never the owner's).
                res = home_layout_write(json.loads(body or "{}"))
                return self._send(400 if res.get("error") else 200, res)
            if u.path == "/api/tasks":
                data = json.loads(body)
                proj = (q.get("project") or [data.get("project", "")])[0]
                args = dict(text=data.get("text"), owner=data.get("owner"), to=data.get("to"), frm=data.get("from"),
                            due=data.get("due") or None, milestone=data.get("milestone") or None,
                            links=[l for l in (data.get("links") or []) if l], tags=[x for x in (data.get("tags") or []) if x],
                            people=[p for p in (data.get("people") or []) if p],   # who the item concerns (validated against people/ by tasks.py)
                            id=data.get("id"), by=data.get("by"), reason=data.get("reason"),
                            until=data.get("until"),                                # hold: the day the task comes back (T-0108)
                            note=data.get("note"),                                  # the "keep in mind" line an item can carry (step 2c)
                            source=data.get("source"))                              # who filed it: the home prompt box files as home-prompt (0.42.0, T-0227)
                try:
                    path, rel = ledger.resolve(proj)
                    if PROPOSE:
                        # exactly what would have gone to ledger.apply(path, rel, action, **args); pull.py replays it on the canonical ledger
                        action = data.get("action", "")
                        if action not in ("add", "ask", "done", "reopen", "block", "answer", "people", "link", "hold"):
                            raise ledger.LedgerError("unknown action %r" % action)
                        req = propose("tasks", rel, {"action": action, "args": {k: v for k, v in args.items() if v not in (None, [], "")}})
                        return self._send(202, {"proposed": True, "request": req, "kind": "tasks", "target": rel, "project": proj})
                    iid = ledger.apply(path, rel, data.get("action", ""), agent="brain-viewer", **args)
                except ledger.LedgerError as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True, "id": iid, "project": proj, "path": rel})
            return self._send(404, {"error": "no such route"})
        except json.JSONDecodeError as e:
            return self._send(400, {"error": "not valid JSON: %s" % e})
        except Exception as e:
            return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8")
        try:
            if u.path.startswith("/api/studio/"):
                # the image studio (T-0235): generate, edit, candidate; 403 in a team copy, 502 with one line on a provider failure
                code, out = studio_api("POST", u.path, {}, body)
                return self._send(code, out)
            if u.path == "/api/looks":
                # T-0208: {"name", "css", "replace"?, "activate"?} imports a look into looks/; {"active": name} picks one
                if n > LOOK_MAX_BYTES * 2 + 2000:
                    return self._send(413, {"error": "a look may be at most %d bytes" % LOOK_MAX_BYTES})
                res = look_import(json.loads(body or "{}"))
                return self._send(400 if res.get("error") else 200, res)
            if u.path == "/api/pending/action":
                # one press on an item of the review queue (2026-09-18, T-0017): {id, action: approve|reject}. It goes
                # to the app twice -- ?dryRun=1 first, then for real -- and a real write leaves one SYNCED line.
                data = json.loads(body or "{}")
                code, out = pending_act(data.get("id"), str(data.get("action") or ""))
                return self._send(code, out)
            if u.path == "/api/today/tasks/action":
                # one press on a row of the Today page's open-tasks block: {ledger, id, action: done|hold}. The item is
                # read off the file again before anything is written, and tasks.py does the write and its own log line.
                data = json.loads(body or "{}")
                code, out = today_task_act(data.get("ledger") or data.get("project"), data.get("id"), str(data.get("action") or ""))
                return self._send(code, out)
            if u.path == "/api/widgets/broken":
                # a home tile broke (T-0217): {id, error, where, stack}. Kept in memory for the widgets lamp, and one
                # finding on the brain-viewer ledger, keyed by widget and error so a repeat lands on the open item.
                code, out = widget_broken(json.loads(body or "{}"))
                return self._send(code, out)
            if u.path == "/api/mantras":
                # one line added to the pool under the date (0.38.0): {text, author, source}. A team copy proposes it.
                data = json.loads(body or "{}")
                out = mantra_add(data)
                return self._send(400 if out.get("error") else 200, out)
            if u.path in ("/api/call/tick", "/api/call/notes"):
                # the call screen's two writes (0.47.0): a question ticked, the notes section saved, both into the prep
                data = json.loads(body or "{}")
                code, out = call_tick(data) if u.path.endswith("/tick") else call_notes(data)
                return self._send(code, out)
            if u.path == "/api/prep":
                if PROPOSE:
                    return self._send(403, {"error": "People cards are not part of a team copy"})
                data = json.loads(body)
                if data.get("event_start"):
                    # 0.47.0: a prep for one calendar event, by its start. The server finds the event, keys the prep to the
                    # thread its carded people make (or to them as a set) and names the attendees with no card.
                    ev = call_event_for(start=data.get("event_start"))
                    if ev is None:
                        return self._send(404, {"error": "no event starting %s on the calendar files" % data.get("event_start")})
                    try:
                        rel, existed = prep_for_event(ev, data.get("purpose") or "")
                    except ValueError as e:
                        return self._send(400, {"error": str(e)})
                    return self._send(200, {"ok": True, "path": rel, "existed": existed,
                                            "call": "/call?prep=" + urllib.parse.quote(rel),
                                            "note": "already written; opened as it stands (one prep per call)" if existed else "written from the cards"})
                try:
                    rel, existed = make_prep(data.get("slug"), data.get("call_date"), data.get("purpose"),
                                             group=data.get("group"), participants=data.get("participants"))
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True, "path": rel, "existed": existed,
                                        "note": "already written; opened as it stands (one prep per call)" if existed else "written from the card"})
            if u.path in ("/api/chat/send", "/api/chat/stop", "/api/chat/adopt"):
                if PROPOSE:
                    return self._send(403, {"error": "Chat runs on the owner's machine; in a team copy, use your own Claude Code in this folder"})
                data = json.loads(body or "{}")
                if u.path == "/api/chat/stop":
                    cid = str(data.get("chat") or "").strip()
                    return self._send(200, {"ok": True, "chat": cid, "stopped": chat_stop(cid)})
                if u.path == "/api/chat/adopt":
                    # a Claude Code session taken into the chat (2026-09-10, T-0102): refused while it is still being written
                    row, err, code = chat_adopt(str(data.get("session") or "").strip())
                    return self._send(code, {"error": err} if err else row)
                return chat_send(self, data)
            if u.path == "/api/exchange/pull":
                # the inbox's one action (2026-09-16, T-0171): fast-forward the configured exchanges and report what
                # arrived. skills/exchange/pull.py does the work; nothing is applied to the brain either way.
                if PROPOSE:
                    return self._send(403, {"error": "an exchange is between two owners' own machines; a team copy has none"})
                code, out = exchange_pull((json.loads(body or "{}") or {}).get("exchange"))
                return self._send(code, out)
            if u.path == "/api/forge/new":
                # the Forge's picker (2026-09-09, T-0041): a new machine = one canvas with one empty cell, in a family folder
                data = json.loads(body or "{}")
                rel, err = forge_new(data.get("family"), data.get("name"))
                if err:
                    return self._send(400, {"error": err})
                if PROPOSE:
                    return self._send(202, {"proposed": True, "request": rel, "kind": "file"})
                return self._send(200, {"ok": True, "path": rel})
            if u.path == "/api/live/bindings":
                # the live maps' one write (2026-09-09, T-0042): "save bindings" copies the resolved bindings into the sibling .forge.json.
                # The server resolves them itself; the page sends only the canvas path, so nothing a page sends shapes the file.
                data = json.loads(body or "{}")
                row, err = live_save_bindings(data.get("path"))
                if err:
                    return self._send(404 if err == "canvas not found" else 403, {"error": err})
                return self._send(202 if row.get("proposed") else 200, row)
            if u.path == "/api/notepad":
                # the notepad (2026-09-10, T-0074): one note, written as a dated markdown file in thoughts/notepad/ with
                # the pictures it names beside it (spec section 4, decision 14). A note is the owner's own words; nothing here
                # rewrites them, and the date comes from the clock in the same call that writes.
                data = json.loads(body or "{}")
                text = str(data.get("text") or "").replace("\r\n", "\n").strip()
                if not text and not (data.get("pictures") or []):
                    return self._send(400, {"error": "an empty note is not written"})
                pics = []
                for p in (data.get("pictures") or [])[:12]:
                    rel = norm(str(p))
                    if not rel or not rel.startswith(CAPTURE_REL + "/") or os.path.splitext(rel)[1].lower() not in CAPTURE_IMG:
                        return self._send(400, {"error": "a note may only name pictures already kept in %s/" % CAPTURE_REL})
                    pics.append(rel)
                page = " ".join(str(data.get("page") or "").split())[:60]
                if PROPOSE:
                    req = propose("note", "", {"text": text, "pictures": pics}, note=text[:200])
                    return self._send(202, {"proposed": True, "request": req, "kind": "note", "target": ""})
                rel = notepad_write(text, pics, page)
                note = log_line("%s -- note taken in the viewer's notepad%s (brain-viewer, %d chars%s)"
                                % (rel, (" on %s" % page) if page else "", len(text), (", %d picture(s)" % len(pics)) if pics else ""),
                                action="CREATED")
                return self._send(200, {"ok": True, "path": rel, "reader": "/reader?path=" + urllib.parse.quote(rel),
                                        "pictures": pics, "log": note})
            if u.path == "/api/paste":
                # a picture pasted or attached in the app (2026-09-10, T-0079 chat + T-0074 the notepad): the bytes are
                # kept in thoughts/notepad/ under a dated name and the page then refers to the file by its path, so a
                # message or a note carries a real brain file rather than an inline blob nothing else can read.
                if PROPOSE:
                    return self._send(403, {"error": "a team copy cannot add files to the brain: send the picture to the owner instead"})
                data = json.loads(body or "{}")
                raw = str(data.get("data") or "")
                if raw.startswith("data:"):
                    raw = raw.split(",", 1)[-1]
                try:
                    blob = base64.b64decode(raw, validate=True)
                except Exception:
                    return self._send(400, {"error": "the picture did not arrive as base64"})
                if not blob:
                    return self._send(400, {"error": "the picture arrived empty"})
                if len(blob) > CAPTURE_MAX:
                    return self._send(413, {"error": "that picture is %.1f MB; the limit here is %d MB" % (len(blob) / 1048576.0, CAPTURE_MAX // 1048576)})
                ext = os.path.splitext(str(data.get("name") or ""))[1].lower()
                if ext == ".jpe":
                    ext = ".jpg"
                if ext not in CAPTURE_IMG:
                    ext = {"image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}.get(str(data.get("type") or ""), ".png")
                leaf = capture_name(data.get("kind") or "note", data.get("name"), ext)
                rel = capture_write(leaf, blob)
                note = log_line("%s -- picture pasted in the %s (brain-viewer, %d bytes)"
                                % (rel, "chat" if (data.get("kind") == "chat") else "notepad", len(blob)), action="CREATED")
                return self._send(200, {"ok": True, "path": rel, "bytes": len(blob),
                                        "url": "/api/image?path=" + urllib.parse.quote(rel), "log": note})
            if u.path == "/api/attach":
                # a picture attached to a question or an answer (2026-09-22, T-0219): kept next to the item's ledger
                # and linked onto the item through tasks.py (attach_save), which writes the one log line itself.
                if PROPOSE:
                    return self._send(403, {"error": "a team copy cannot add files to the brain: send the picture to the owner instead"})
                data = json.loads(body or "{}")
                code, out = attach_save(data.get("ledger") or data.get("project"), data.get("item") or data.get("id"),
                                        data.get("name"), data.get("data"))
                return self._send(code, out)
            if u.path == "/api/reply":
                # a NOTE on a ledger item (2026-09-10, T-0078 + T-0077): the owner says something back and the item STAYS
                # OPEN. It is written as the item's `note:` line through the same tasks.py the checkboxes use, and the
                # server composes the line so the date comes from this machine's clock rather than a browser's: an
                # existing keep-in-mind line is kept and the reply is added after it, never overwritten.
                # 2026-09-18, T-0193: every task row has this box now, and a row may know only the LEDGER PATH it lives
                # on (the Today page's open-tasks block sends that). The path is matched against the registry rather
                # than trusted, exactly as POST /api/today/tasks/action does, so no path can be sent in here.
                data = json.loads(body or "{}")
                proj = str(data.get("project") or "").strip()
                led = str(data.get("ledger") or "").replace("\\", "/").strip()
                if not proj and led:
                    hit = next((h for h in registry().get("holons", []) if h.get("tasks") and led in (h["id"], h["tasks"])), None)
                    if not hit:
                        return self._send(400, {"error": "no registered ledger answers to %r" % led})
                    proj = hit["id"]
                iid = str(data.get("id") or "").strip()
                text = " ".join(str(data.get("text") or "").split())
                if not text:
                    return self._send(400, {"error": "a note needs some words"})
                try:
                    path, rel = ledger.resolve(proj)
                    it = ledger.find(ledger.parse(ledger.read(path)), iid)
                    was = (it.get("note") or "").strip()
                    line = ("%s; " % was if was else "") + "note %s: %s" % (ledger.today(), text)
                    if PROPOSE:
                        req = propose("tasks", rel, {"action": "note", "args": {"id": iid, "note": line}}, note=text[:200])
                        return self._send(202, {"proposed": True, "request": req, "kind": "tasks", "target": rel, "project": proj, "id": iid})
                    ledger.apply(path, rel, "note", agent="brain-viewer", id=iid, note=line)
                except ledger.LedgerError as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True, "id": iid, "project": proj, "path": rel, "note": line})
            if u.path == "/api/review":
                # ONE rating (2026-09-17, T-0166): {card, verdict, note?}. The card is looked up on the server, so what
                # it is, what its evidence is and whether it is still on the board come from the ledgers, not from the
                # page. good / off / wrong writes a line onto the item; a CLOSURE rated good is then checked off. The
                # auto-close bar is counted in the same call and acted on by nothing.
                if PROPOSE:
                    return self._send(403, {"error": "the rating surface is the owner's: a team copy proposes changes instead of rating his"})
                data = json.loads(body or "{}")
                cid = str(data.get("card") or data.get("cardId") or "").strip()
                verdict = str(data.get("verdict") or "").strip()
                if data.get("undo"):
                    # UNDO the press just made (2026-09-24, T-0200): only the newest rating, only inside a minute or so
                    try:
                        row = review_undo(cid)
                    except ledger.LedgerError as e:
                        return self._send(400, {"error": str(e)})
                    if row is None:
                        return self._send(404, {"error": "there is no rating on that card to undo"})
                    return self._send(200, dict(row, ok=True))
                if not verdict:
                    # A NOTE ON ITS OWN (2026-09-18). No verdict in the body means he wanted to say something, not
                    # answer: the line is written onto the item and nothing else moves -- no ratings line, no counter,
                    # and a card already rated keeps the answer it has.
                    try:
                        row = review_note(cid, data.get("note"))
                    except ledger.LedgerError as e:
                        return self._send(400, {"error": str(e)})
                    if row is None:
                        return self._send(404, {"error": "there is no such card to write a note on"})
                    return self._send(200, dict(row, ok=True))
                try:
                    row = review_post(cid, verdict, data.get("note"))
                except ledger.LedgerError as e:
                    return self._send(400, {"error": str(e)})
                if row is None:
                    return self._send(404, {"error": "that card is not on the board any more -- it may already have been rated, or the item may have changed"})
                return self._send(200, dict(row, ok=True))
            if u.path == "/api/note":
                if not PROPOSE:
                    return self._send(404, {"error": "no such route here: POST /api/note exists only in a team copy (propose mode)"})
                data = json.loads(body)
                text = " ".join(str(data.get("text") or "").split())
                if not text:
                    return self._send(400, {"error": "text is required"})
                raw_target = (data.get("target") or "").strip()
                target = norm(raw_target) if raw_target else ""
                if raw_target and not target:
                    return self._send(400, {"error": "target must be a brain-relative path (no .., no absolute paths)"})
                req = propose("note", target, {"text": text}, note=text[:200])
                return self._send(202, {"proposed": True, "request": req, "kind": "note", "target": target})
            return self._send(404, {"error": "no such route"})
        except json.JSONDecodeError as e:
            return self._send(400, {"error": "not valid JSON: %s" % e})
        except Exception as e:
            return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})


# ---- --init: make a folder bootable (2026-09-16) ----
# The viewer needs a registry to draw, a manifest to order, a place to draw into and a log to append to. A brain that
# has never met the viewer has none of them, and the answer is not "copy the code into your folder": it is this.
# EVERY step is create-if-missing. Nothing here opens an existing file for writing, so running it twice is a no-op.

INIT_EXAMPLE = {
    "nodes": [
        {"id": "title", "type": "text", "x": 0, "y": -300, "width": 900, "height": 160, "color": "6",
         "text": "# Example drawing\nA **cell** is a group node: one machine, with its parts laid out inside it. A **part** is a text node whose first line is `**<Type> · <Name>**`, and the colour says which type it is. Lines between parts are edges."},
        {"id": "cell", "type": "group", "x": 0, "y": -60, "width": 900, "height": 380, "color": "6", "label": "CELL · EXAMPLE — something arrives and is written down"},
        {"id": "ui", "type": "text", "x": 40, "y": 20, "width": 360, "height": 200, "color": "3",
         "text": "**UI · The box you type in**\nWhere the thing arrives. Replace this with your own first step."},
        {"id": "store", "type": "text", "x": 500, "y": 20, "width": 360, "height": 200, "color": "4",
         "text": "**Store · Where it lands**\nThe file or table the step writes. Replace this too."},
    ],
    "edges": [{"id": "e1", "fromNode": "ui", "fromSide": "right", "toNode": "store", "toSide": "left", "label": "writes"}],
}
INIT_LOG_HEADER = """# Brain Operations Log
> Append-only. Newest entries at the bottom. One line per action.
> This file is the ground truth for "what happened and when."

## Format
`[YYYY-MM-DD HH:MM] [AGENT-ID] ACTION -- description`

## How to write to this file
**Never type a timestamp by hand.** Append with:
```
python skills/brain-log/log.py --append --agent my-agent --action MODIFIED --text "what happened"
```
It reads the system clock in the same call that writes, so a stamp cannot come from an agent's own sense of time. There is deliberately no way to pass a timestamp. It also refuses an append that would create an out-of-order line, an unknown action verb, or a malformed agent id.

`python skills/brain-log/log.py --check` validates the file: exit 0 clean, exit 2 dirty.

## Actions vocabulary
- CREATED -- new file added
- MODIFIED -- existing file changed
- EXTRACTED -- section pulled from a source file into another file
- INGESTED -- raw material processed into pages
- LINKED -- links added to an existing file
- DELETED -- file removed
- SYNCED -- files pushed somewhere
- LINTED -- health check run, results noted
- DECISION -- a decision was made that affects this brain's state
- ROUNDS -- the end-of-session update procedure was run

## Log
"""


def default_settings():
    """The settings file a brain gets on its first start (0.48.0: written into the user layer, viewer/settings.json).
    Values come from whatever this run already resolved, so a brain seeded from a legacy file keeps its own."""
    return {
            "_schema": "brain-viewer-settings/1",
            "_note": "The settings the viewer reads at startup for THIS brain. Change a value and restart the server.",
            "_keys": {"prep_horizon_days": "how many days ahead the People page counts a call as coming up",
                      "forge_root": "the folder the Forge draws into, and the folder /canvases and /maps read from; a drawing sits one folder deep inside it",
                      "owner": "the @name the app treats as 'you': the owner dropdowns, the Today count, Waiting on you, the home link. skills/brain-tasks/tasks.py reads the same key",
                      "owner_names": "the spellings of your OWN name a transcript may carry: a participant matching one of these is you, and is skipped rather than matched to a card. Empty means no name is skipped",
                      "name_fixes": "the transcriber spellings this brain has reviewed, {the name as a transcript writes it -> the people/ card slug it means}. A bare first name belongs here only when it is unambiguous across every card. Empty means a name maps only by matching a card's own title",
                      "app_user": "which PF App account is yours: an email (resolved to its account id through the admin key) or the id itself. The Today page's review read asks the app about that account; with no value here, that section says so instead of guessing",
                      "mantras": "the markdown file the home page draws the day's line from (a bulleted list); absent means an empty pool",
                      "findings_ledger": "the registered holon id whose ledger a broken home widget files its finding on; unregistered means the break is recorded and lit, not filed",
                      "exchanges": "the shared repositories this viewer swaps drawings, notes and files through, one per person: [{name, repo, path, them}]. `path` is where that repo is cloned, BESIDE this folder and never inside it, and it is the only place the send step writes. /requests lists what arrived there for `owner`; skills/exchange/ is the convention. Empty means no exchange exists yet"},
            "prep_horizon_days": SETTINGS.get("prep_horizon_days", 4), "forge_root": ARCH_REL, "owner": OWNER,
            "owner_names": [], "name_fixes": {},
            "app_user": SETTINGS.get("app_user", ""), "exchanges": []}


USER_README = """# viewer/ -- your own layer of the Brain Viewer

What you make in the viewer lives here: `settings.json`, your home board layouts (`layouts/`), the looks you wrote or
imported (`looks/`) and the widgets you wrote (`widgets/`). An update of the viewer replaces `skills/brain-viewer/`
whole and never writes into this folder. The viewer created this readme on its first start; edit it freely.
"""
USER_WIDGETS_README = """# viewer/widgets/ -- widgets you wrote

One `*.js` file per widget, loaded after the viewer's own. The id is the filename. A file registers itself with
`BV.widgets.register({id, title, size, defaultOn, source, contract: 1, mount(el, api) {...}})`. The contract, the api,
the design tokens and the definition of done are in `skills/brain-viewer/widgets/readme.md` and
`skills/brain-viewer/widgets/curriculum.md`; prove a file with
`python skills/brain-viewer/widgets/harness.py viewer/widgets/<file>.js`. An id the viewer already ships is refused on
the board ("id taken by a core widget"); a missing or higher contract number is refused too ("written for a newer viewer").
"""


def ensure_user_layer(quiet=False):
    """The user layer on first start (0.48.0): viewer/ with layouts/, looks/ and widgets/, a settings file, and a short
    readme in viewer/ and viewer/widgets/. A brain that still has the legacy files inside the code folder has them COPIED
    across once (settings, every home-layout-<member>.json, every look that is not a core look); nothing is deleted and
    nothing that already exists in viewer/ is touched. Returns the brain-relative paths it created."""
    made = []

    def mk(rel):
        ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        if not os.path.isdir(ap):
            os.makedirs(ap, exist_ok=True)
            made.append(rel + "/")

    def put(rel, text=None, src=None):
        ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        if os.path.exists(ap):
            return
        os.makedirs(os.path.dirname(ap), exist_ok=True)
        if src:
            shutil.copyfile(src, ap)
        else:
            with open(ap, "w", encoding="utf-8", newline="\n") as f:
                f.write(text if text.endswith("\n") else text + "\n")
        made.append(rel)

    try:
        for rel in (USER_REL, USER_LAYOUTS_REL, USER_LOOKS_REL, USER_WIDGETS_REL):
            mk(rel)
        legacy = os.path.join(BRAIN, LEGACY_SETTINGS_REL.replace("/", os.sep))
        if os.path.isfile(legacy):
            put(SETTINGS_REL, src=legacy)
        else:
            put(SETTINGS_REL, json.dumps(default_settings(), ensure_ascii=False, indent=2))
        old_dir = os.path.join(BRAIN, "skills", "brain-viewer")
        for fn in (sorted(os.listdir(old_dir)) if os.path.isdir(old_dir) else []):
            m = re.match(r"^home-layout-([a-z0-9_-]+)\.json$", fn)
            if m:
                put(HOME_LAYOUT_FMT % m.group(1), src=os.path.join(old_dir, fn))
        old_looks = os.path.join(old_dir, LOOKS_DIR)
        for fn in (sorted(os.listdir(old_looks)) if os.path.isdir(old_looks) else []):
            if fn.endswith(".css") and fn[:-4] not in CORE_LOOKS:
                put("%s/%s" % (USER_LOOKS_REL, fn), src=os.path.join(old_looks, fn))
        put(USER_REL + "/readme.md", USER_README)
        put(USER_WIDGETS_REL + "/readme.md", USER_WIDGETS_README)
    except OSError as e:
        sys.stderr.write("the user layer %s/ could not be completed: %s\n" % (USER_REL, e))
    if made and not quiet:
        print("user layer: created %s" % ", ".join(made))
    return made


def init_brain():
    """`--init`: create, in BRAIN, the few files the viewer needs to boot. Prints what it created and what it left
    alone, and never touches a file that already exists."""
    made, kept = [], []

    def put(rel, text):
        ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        if os.path.exists(ap):
            kept.append(rel); return False
        os.makedirs(os.path.dirname(ap), exist_ok=True)
        with open(ap, "w", encoding="utf-8", newline="\n") as f:
            f.write(text if text.endswith("\n") else text + "\n")
        made.append(rel); return True

    def dump(rel, obj):
        return put(rel, json.dumps(obj, ensure_ascii=False, indent=2))

    print("--init on %s" % BRAIN)
    os.makedirs(BRAIN, exist_ok=True)
    pid = re.sub(r"[^a-z0-9]+", "-", os.path.basename(BRAIN.rstrip("\\/")).lower()).strip("-") or "my-project"
    name = os.path.basename(BRAIN.rstrip("\\/")) or "My project"
    tasks_rel = "projects/%s-tasks.md" % pid

    dump(REGISTRY_REL, {
        "_schema": "holon-registry v1", "_updated": ledger.today(),
        "_note": "The registry is the list of the folders and files this brain treats as units of work (holons). The viewer renders every row: /holons draws the tree, /status reads the status file a row names, and /projects renders the ledger a row names in its `tasks` field. Add a row to add a project.",
        "_rules": ["sharing defaults to private; sharing is opt-in per holon, never opt-out",
                   "a holon may name the per-holon rules that govern it (rules), the machine-written status file its agent regenerates (status), and its project ledger (tasks)",
                   "a ledger named in `tasks` is written only through skills/brain-tasks/tasks.py, or by hand in the same shape",
                   "machine-mirror trust = freshness, never authorship"],
        "sharing_tiers": ["private", "team", "external-partner", "public"],
        "types": ["canonical-domain", "people-card", "machine-mirror", "state-file", "synthetic", "dated-record", "index", "canvas", "family"],
        "holons": [
            {"id": "brain-viewer-holon", "name": "Brain Viewer (app holon)", "type": "family", "path": "brain-viewer-holon/",
             "description": "What this folder decides about the viewer, and the machine-written status file serve.py rewrites every time it starts.",
             "status": STATUS_REL, "sharing": "private", "stamped": False, "parent": None, "children": []},
            {"id": pid, "name": name, "type": "family", "path": "projects/",
             "description": "The first project in this brain, named after the folder. Rename it, or copy the row, to make this registry describe your own work. Its ledger is what /projects renders and writes to.",
             "tasks": tasks_rel, "sharing": "private", "stamped": False, "parent": None, "children": []},
        ]})
    dump(MANIFEST_REL, {
        "_about": "The ordered list of pieces the content dashboard renders, in program order, read by skills/brain-viewer/serve.py for /mentee. Paths are relative to this brain's root; kind = md | canvas | app | missing. Empty on purpose: add a stage with pieces and /mentee fills in.",
        "updated": ledger.today(), "stages": []})
    dump(MAPS_REL, {
        "_schema": "brain-viewer-maps/1",
        "_note": "Which drawings are MAPS, and grouped by what purpose. A declaration, like the content manifest: /maps renders these groups and never invents the grouping. Empty on purpose: every drawing you make shows up folded under 'other canvases' until you group it.",
        "groups": []})
    dump(SETTINGS_REL, default_settings())
    ensure_user_layer(quiet=True)

    ex_rel = "%s/example/example-machine.canvas" % ARCH_REL
    src = os.path.join(CODE, str(CODE_SETTINGS.get("forge_root") or "canvases").replace("/", os.sep), "example", "example-machine.canvas")
    if os.path.isfile(src) and os.path.normcase(src) != os.path.normcase(os.path.join(BRAIN, ex_rel.replace("/", os.sep))):
        with open(src, "r", encoding="utf-8-sig") as f:
            put(ex_rel, f.read())
    else:
        dump(ex_rel, INIT_EXAMPLE)

    # the holon folder the registry's first row names, so serve.py has somewhere to write its status file on startup
    if os.path.isdir(os.path.join(BRAIN, "brain-viewer-holon")):
        kept.append("brain-viewer-holon/")
    else:
        os.makedirs(os.path.join(BRAIN, "brain-viewer-holon"), exist_ok=True)
        made.append("brain-viewer-holon/")

    put(LOG_REL, INIT_LOG_HEADER)
    ap = os.path.join(BRAIN, tasks_rel.replace("/", os.sep))
    if os.path.exists(ap):
        kept.append(tasks_rel)
    else:
        try:
            ledger.init(ap, tasks_rel, pid, name, agent="brain-viewer")
            made.append(tasks_rel)
        except Exception as e:
            print("  could not create %s: %s" % (tasks_rel, e))

    for rel in made:
        print("  created     %s" % rel)
    for rel in kept:
        print("  left alone  %s (already there)" % rel)
    print("  %d created, %d left alone. Nothing existing was changed." % (len(made), len(kept)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="bind address; 127.0.0.1 (default) keeps the viewer local, 0.0.0.0 exposes it to a container's port forward (Replit preview)")
    ap.add_argument("--brain", help="the folder to read as the brain (default: the folder this code sits in). Also settable as BRAIN_ROOT, or as `brain_root` in viewer-settings.json. Read at import, before this parser runs")
    ap.add_argument("--init", action="store_true", help="create, in that brain folder, whatever the viewer needs to boot (registry, manifests, settings, forge root + example drawing, log, a first ledger). Never overwrites a file that is already there")
    ap.add_argument("--supervise", action="store_true", help="run the server as a child and restart it whenever it exits non-zero (2, 4, 8, 15, 30, 60 seconds, reset after ten minutes up). Every exit and restart is recorded in %s" % CRASH_REL)
    args = ap.parse_args()
    global ARGS
    ARGS = args
    if args.supervise:
        return supervise([a for a in sys.argv[1:] if a != "--supervise"])
    if port_answers(args.port, args.host):
        # never a second server on a port that answers (Windows would let it bind, and the stale one keeps answering)
        sys.stderr.write("port %s already answers: a viewer is running there, so this one did not start\n" % args.port)
        return 0
    if args.init:
        init_brain()
    elif not os.path.isdir(BRAIN):
        sys.stderr.write("no such brain folder: %s\nCreate it, or run again with --init to fill it in.\n" % BRAIN)
        return 2
    # the chat's default model is checked against the installed CLI once, in the background, so a refused id falls back to
    # opus with a note instead of failing a turn (2026-09-17, T-0187)
    threading.Thread(target=probe_models_once, daemon=True).start()
    global PREV_RUN
    PREV_RUN = prev_run()             # read BEFORE this run writes its own START line
    install_exit_recorders()          # T-0181: no exit without a line in the crash log
    ensure_user_layer()               # 0.48.0: viewer/ exists before the first request reads it
    write_status()
    srv = ThreadingHTTPServer((args.host, args.port), H)
    mode = ("PROPOSE MODE: team copy of member %s, every save becomes a request under %s/%s/" % (MEMBER, REQUESTS_REL, MEMBER)) if PROPOSE else "normal mode"
    print("Brain Viewer v%s -- home (the board) http://127.0.0.1:%d  chat /chat  today /today  projects /projects  people /people  mentee content /mentee  canvases /canvases  forge /forge  maps /maps  requests /requests  status /status  holons /holons  agents /agents  map (retired) /map  (brain: %s%s; %s; claude %s)  Ctrl+C to stop"
          % (VERSION, args.port, BRAIN, "" if os.path.normcase(BRAIN) == os.path.normcase(CODE) else "; code: " + CODE, mode, CLI_VERSION or "not found"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        crash_note("EXIT", code=0, reason="Ctrl+C")
    except Exception as e:
        crash_note("EXIT", code=1, reason="%s: %s" % (type(e).__name__, e), tb=traceback.format_exc())
        raise
    else:
        crash_note("EXIT", code=0, reason="serve_forever returned on its own")
    return 0


if __name__ == "__main__":
    sys.exit(main())
