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
  the handful of files the viewer needs to boot, and never overwrites one that is already there; then it starts the
  viewer on --port, or, when that port already answers (your own viewer on 8765), stops there with the folder filled in
  (0.90.0: it used to stop at the port and create nothing).

Pages
  /            Today                     (today.html, the landing page since 0.65.0): see /today below
  /home        Home                      (home.html, at "/" until 0.65.0): a dashboard of widgets, instruments only since 0.65.0 (Answer and Decide off a new board, Next one line into Today). Each widget is one file in skills/brain-viewer/widgets/ reading one endpoint;
               which ones are on, in what order and at what size is the layout file viewer/layouts/<member>.json, edited with the pencil.
               In a TEAM COPY the home stays the Mentee Content Dashboard (mentee-dashboard.html): every mentee-facing piece in program order, editable in place
  /chat        Chat                      (chat.html): the conversations with the brain's agents, unchanged -- it was the home page until 2026-09-21
  /call        The call               (call.html, 0.47.0): one call on one flat page for while you are on it -- the call, its join press, a card per person, what is due, the questions as boxes that tick into the prep file, the points per person, the notes box bound to the prep's ## Your notes. ?prep=<deliverables/call-prep/...md> or ?date=YYYY-MM-DD&start=<ISO>. Reads GET /api/call; writes POST /api/call/tick and POST /api/call/notes
  /survey      Survey                    (survey.html, 0.78.0): one survey file as a page to press through -- its title and intro, then each item as a card: the statement, one press per option (the chosen one marked), a one-line note box; a press saves at once, a note when its box is left; "N of M answered"; Finish answers the ledger question named in q through PUT /api/tasks and returns to Today. ?path=<brain .md>&q=<ledger>:<id>. Reads GET /api/survey; writes POST /api/survey/answer. Opened by the one press a question tagged `survey` draws on Today, the thread page and the workspace (BV.survey)
  /today       Today                    (today.html; also "/" since 0.65.0, the one place an item is acted on): ONE run-through of the owner's open items, blocking first, then due, then the rest (blocking first since 0.65.1), then one row per call whose PF App action items wait for approval (approve all through POST /api/pending/approve-all, skip until tomorrow); click-through #test items are off it (the rating page's To try) and transcript-intake items older than 14 days wait for the sweep (viewer/sweep/seen.json); `?item=<ledger>/<id>` opens that item at the top; then what others owe today, today's calls with their preps, the transcripts that landed today with their intake state, and the day's closed items folded at the bottom. The ledger sections are composed in the browser from /api/projects (the page IS the ledgers read back); the open-tasks block comes from /api/today/tasks and writes through POST /api/today/tasks/action; the three outside halves come from /api/pending, /api/calls and /api/landed, each read at request time and stored nowhere; the app's review queue is approved and rejected in place through POST /api/pending/action. 0.80.0: Might annoy you, the friction cards from the person's record (GET /api/friction, at most three), each answered annoying, not annoying or with a comment through POST /api/friction/answer; drawn only when one is open. 0.81.0 (the Today direction, amendment 2): Yours to do opens with what is NEW since the owner's previous visit (GET /api/today/visit, POST on the page's load), each row marked new with why; then what is due today; then the backlog, overdue, later-dated and undated alike, folded under one line with its count, blocking first in each group as before; the owner's held items in an On hold fold of their own with their return dates, never under Others owe today; every band header counts what the band draws
  /projects    Projects                  (projects.html): every project ledger the registry names (a holon's `tasks` field): progress per milestone and owner, questions answered and boxes checked here
  /people      People                    (people.html): what is open for the owner about a person FIRST, then the card (collapsed section by section) and the dated call preps; the standing call threads (groups) above the individuals; New prep writes one from the cards
  /chat        Chat                      (chat.html): talk to the brain's main agent, or to one project's agent, from the app -- every conversation is a real Claude Code session started here (`claude -p`, this machine, this account), streamed as it answers; the main agent routes questions onto the right ledgers and dispatches project work to sub-agents; past conversations per project; ?project=<id> opens a project chat
  /maps        0.69.0: a redirect to /forge, where the picker now lives (below). Until 0.69.0, Maps (maps.html): the picker (0.66.0: read, live and edit per drawing, all in the Forge) -- the canvases that are maps, grouped by purpose as skills/brain-viewer/maps-manifest.json declares them (information flow, apps and services, the OS, machines, the daily workflow), each with how many nodes are bound, how many are concept, how many were active today, and an "open live" link; every other canvas folded by family; opens on the group whose map was active most recently
  /from-claude From Claude               (review.html, 0.66.0): one page of what Claude filed for the owner's say -- the rating cards (good / off /
               wrong, one optional line; the closure and review kinds as before), the To try batch, the findings (every open
               ledger item with a `#source:` tag, the source chips in words as the filter, ten to a page) and, only when it holds
               something, the team requests and the exchange inbox; then the Rated fold. /review, /findings and /requests redirect here
  folded       0.66.0 (Round 2 of the 10/06 review): every old route answers with a 302 (fold_redirect) -- /work to the item's
               thread or /thread?item= (the "no thread yet" case), /canvases?open= and /live?path= to /forge?path=&mode=read|live,
               /map to /maps, /agents to /chat, /holons to /projects#holons, /status to /home#lamps
               0.70.0: every redirect also sets the cookie bv_moved=<old route>, and viewer-common.js (MOVED) draws one line on
               the landing page saying where the old address went and why, once per browser session (the navigation direction rule 6)
  forge        0.69.0 (the navigation direction, Round A): /forge with no drawing IS the picker, painted at once from GET /api/maps?counts=0
               (the maps by purpose, then the other drawings by family, the scratch fold and New machine); the live counts arrive
               after from GET /api/maps. /maps, /map and a bare /canvases or /live now redirect to /forge (/maps with ?moved=maps,
               which draws one line saying the picker moved, for one release); the header entry named forge opens /forge
  first paint  0.72.0 (the navigation direction, Round C, rule 3): every page's HTML plus the calls its script waits on before its
               first content paints stays under 500 ms; paint.test.py measures every page above (the calls each waits on are listed
               there, per page) and gates a release on a scratch brain, and with --real reports the same over this brain's data.
               A slow call goes after the paint into its own place, which says it is loading (the Forge picker's counts, the chat's
               running strip, the studio's provider probe)
  /reader      Reader                    (reader.html): one brain .md opened AS ONE PAGE (0.54.0) -- real headings at one measure, the outline rail with a scroll-spy, Edit and Ask in the margin, one agent-layer switch, and on every list item a strike and a move up/down that rewrite that one line in the file. ?path=<brain-relative .md>#<heading slug> opens at a section, which is what a ledger's "-> file.md#slug" link points at (a section ask); "Ask about this section" writes the question back onto a project ledger carrying that link
  /glossary    Glossary                  (glossary.html): the vocabulary, meant to sit in a narrow second window beside the work -- search, the groups from help.json's `glossary` key with a glyph and a live example beside each term, a how-it-fits diagram whose labels are themselves hover targets, and the Keys section naming every hotkey. The "?" button in every page's top bar opens that page's help panel (its help.json entry), and the glossary is one press further in, from the link inside the panel (0.85.0, 2026-10-16: this line said the button opened the glossary, which was true until 2026-09-21); ?from=<page> opens the group that page belongs to and leaves the rest folded
  /studio      Studio                    (studio.html, 2026-09-22, T-0235): the image studio -- prompts in, pictures out through the providers in skills/brain-viewer/providers/ (the folder is the registry); pictures land in deliverables/studio/<job>/. 403 on every studio route in a team copy
  /files       Files                     (files.html, 2026-09-28, T-0259): every file in the brain in one table, newest first, every column sorts; the folder tree and type chips filter, the box filters by path; a row opens in the Reader, the lightbox, the canvas viewer, or downloads
  /threads     Threads                   (thread.html, 0.62.0): every subject file under projects/*/subjects/, one row each: name, people, open items for the owner and in all, the newest dated line; a row opens its thread
  /thread      Thread                    (thread.html, 0.62.0; 0.66.0: ?item=<ledger>/<id> with no subject is the "no thread yet" case, the bare Workspace folded in): ?subject=<subject file>: one piece of work across the ledgers -- where it stands (the file's own summary), what needs to get done (every open item naming its people or words, and what those wait on), what it depends on, its files, its next call, its dated lines
  /preview     Preview                   (preview.html, 0.61.0): a web page shown inside the viewer -- a .html in the brain (picked by folder, newest first) or a URL (a local dev server, a live site) -- at full, 1280, 768 or 375 wide, a brain file reloaded when it changes. ?path=<brain .html> or ?url=<http(s)>
  /settings    Settings                  (settings.html, 0.92.0): what a person changes in the viewer; first, sending answers: held until the Send
                                         press, leaving the viewer or the quiet minutes (on), or each press at once (off), and the minutes. GET/PUT /api/settings
  /usage       Usage                     (usage.html, 0.84.0): what used the plan, today and over the week, from this computer's Claude Code transcripts -- the seven days as bars (press one to pick it), the top ten turns of the picked day and of the week (the $, the time, who started it, its first words, the session, the model, the workers' share and why it cost that), the sessions of the week ranked, each opening onto its turns on the picked day with the calls, the context size and the idle time before each. ?day=YYYY-MM-DD&session=<id>. Reads GET /api/usage only; writes nothing

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
                                           0.71.0: `?thread=<subject file>` or `?project=<holon id>` (the page the person last opened) adds `now` {kind, name, href, keys}: the items of that thread or project, which the page draws first as the Now band
  GET  /api/today/undo                     0.71.0: the day's presses (answer, done, hold, note, reopen, from any page) newest first, each {n, at, action, project, ledger, id, said, undone, kind, text, mark, answer, options, links}, read from viewer/undo/<day>.json
  POST /api/today/undo                     0.71.0: {n} takes that press back, and every later press on the same item today; {ledger, id} takes back every press on that item today. The item is put back through tasks.py (reopen, answer, block, hold, note), the tasks an answer freed are blocked on it again, and the undo goes to context/answers-inbox.md as its own batch, `- <project> · undo · <id> · <what was reverted> · "<sentence>"`. A press from another day is final (404)
  GET  /api/today/waiting                  0.71.0: what another person moves next (the Today direction rule 2): a task blocked by someone else's question or task or with a person named in its block, a held task with a person named in its note, a question put to someone else; each {who, since, why}, never the owner's own to do and never Claude's
  GET  /api/today/visit                    0.81.0: {since, sinceKind: visit|today, current, previous, recorded, gapMinutes, marks: {"<holon>/<id>": {why: filed|reassigned|returned|answered|noted|changed, at, by?}}, count}: what changed for the owner after the previous Today visit, read from the log's tasks.py lines to the minute (a line the viewer wrote, the owner's own press, and an answer he gave mark nothing; a hand-written item falls back to its own dates by the day; a hold that ended since is back). Records nothing
  GET  /api/whats-new                      0.91.0: {version, seen, seenAt, seenToday, path, entries: [{date, title, version, lines, leads, more, where}], overnight: [{title, path, when, kind}], overnightMore, since}: Today's Changed since you last looked band. entries are the newest two of brain-viewer-holon/brain-viewer-whats-new.md read from its markdown (lines: the top-level bullets as plain words, at most six, more the rest; where: the "Where to see it" line); seen is the version kept in viewer/whats-new-seen.json; overnight the notes in deliverables/brain-dev/, night-agent/ and brain-engineer/ dated since the previous Today visit (today_visit's since), a delivery note first, then newest, at most five (empty in a team copy)
  POST /api/whats-new/seen                 0.91.0: keeps VERSION as seen, with the time, in viewer/whats-new-seen.json; answers as the GET does. Every page also carries {version, seen, path} as window.BV_WHATSNEW for the header's what's new link and its dot
  POST /api/today/visit                    0.81.0: the Today page opened: kept in viewer/today-visits.json {current: {start, last, openings}, previous}; an opening more than ten minutes after the last one starts a new visit and the old one becomes previous, one inside ten minutes only moves `last`, so a reload keeps the marks. With no previous visit, since is the start of today. Answers as the GET does
  GET  /api/today/pick                     0.85.0: the agent's pick, the first band on Today: context/today-pick.json as skills/today-pick/pick.py wrote it, {file, exists, writtenAt, by, for, today, current (for today, with an item in it), items:[{holon, id, why}]}; the page falls back to its own ranking when current is false. Records nothing
  POST /api/today/waiting/action           0.71.0: {ledger, id, action: nudge|drop, text?}: a nudge is a note on the item; a drop closes it with the reason (a task noted and done, a question answered `dropped: <reason>`). Journaled for undo and sent like any press
  POST /api/today/tasks/action             {"ledger": <holon id or its ledger path>, "id": "T-0123", "action": "done"|"hold"} -- one press on a row of that block. The ledger comes from the registry, the item is re-read off the file before the write, and tasks.py does the write plus its own one log line (agent brain-viewer); hold takes the tool's own three days
  GET  /api/pending                        the PF App's action items still waiting for review, FOLDED PER CONVERSATION (504 items over 61 conversations, so never a flat list): one group per conversation with its title, count and newest day, its items inside it. GET /api/v1/action-items?status=suggested on the personal token, cached 60 seconds
  POST /api/pending/action                 {"id": "<action item id>", "action": "approve"|"reject"} -- one press on one item, straight to the app: POST /api/v1/action-items/:id/status with ?dryRun=1 first (so 400/403/404/409 come back as a sentence with nothing written) and then for real. One SYNCED line in context/log.md per write. Approve-all is the page pressing this once an item at a time
  GET  /api/call?prep=|?date=&start=     the call screen's read (0.47.0): {event {date,start,end,title,join,calendarLink}, people [with role and where it stands], prep {due, questions [{subject, items [{line, checked, text}]}], points, notes, sections}, refs, aliases, defaultProject, canWrite}
  POST /api/call/tick                      {path, line, checked, text}: that question line becomes - [x] / - [ ]; 409 when the line changed since the page read it
  POST /api/call/notes                     {path, text}: the prep's ## Your notes section becomes the text (the skeleton's comment kept)
  GET  /api/survey?path=<brain .md>        (0.78.0) {path, title, intro, default, items:[{n, title, section, statement, options, choice, note, answer, answered, line}], total, answered,
                                           canWrite, writeReason, reader}: a survey file read generically (### N. Title, its statement, Options: a · b · c, Answer:); 403 for a path
                                           outside the brain or not .md, 404 for no such file
  POST /api/survey/answer                  (0.78.0) {path, n, choice, note} -> that item's Answer line, and nothing else, becomes `Answer: <choice>`, `Answer: <choice>. <note>`
                                           or `Answer: <note>` (a note alone is allowed); 400 for a choice that is not one of the item's options, 403 for a path the Reader
                                           may not write (writable()), 404 for no such item; the Reader's steps: line endings kept, a team copy proposes, one log line
                                           per survey per ten minutes
  GET  /api/friction                       (0.80.0) {cards:[{record, title, instance, rule, opened, days, path, reader}], max, holon}: the friction cards open in the
                                           person's record (how-<first>-works/), at most three, read through skills/patterns/patterns.py (cards_json); none in a team copy
  POST /api/friction/answer                (0.80.0) {record, press: annoying|not-annoying|comment, note} -> his press written into that record through
                                           skills/patterns/patterns.py (card_press: annoying an evidence line, not annoying counter-evidence and the record at
                                           0.2, a comment his words), then sent to context/answers-inbox.md as its own batch; 400 for a press it does not know or
                                           a comment with no words, 404 for no such record, 409 for a record with no card open, 403 in a team copy
  GET  /api/calls                         today's calls: context/today-calendar.json as the /start-session recap wrote it (start, end, title, attendees), each attendee matched to a people/ card and each event to a dated prep in deliverables/call-prep/. Absent file, or one written for another day, is reported as such -- the server never reaches a calendar itself. 0.70.0: `prepCalls`, the calls only a prep knows about -- a draft prep whose `call:` is today that no event carries and whose people are not all on one of today's calendar calls -- with no time, `notOnCalendar` true, and the prep's call page (derived; nothing written)
  GET  /api/landed                         the transcripts whose filename carries today's date, in transcripts/ and pf-app-holon/transcripts/, with their intake state: the import-checkup report in transcripts/import-reports/ (exact stem match, or a same-day report sharing a name word, marked as the weaker match) or nothing yet
  GET  /api/mode                           {"mode": "normal"} or {"mode": "propose", member, tier, exported_at, source_commit, ..., whats_new} from team-brain.json (0.82.0: re-read on every call; whats_new is "WHATS-NEW.md" when the copy has that page, else null)
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
  GET  /api/glossary                       {groups, terms, keys}: the `glossary` key of skills/brain-viewer/help.json read at request time (0.85.0; until then the markdown seed in the viewer's holon, now a tombstone) -- one source, no cache, no second copy. A term carries its aliases, definition, example, Septabee analog, group and anchor; a group carries the pages that open it. `available: false` only where the help file or its key is absent
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
                                          0.72.0: `?probe=0` answers at once: a provider with no key file (its ready() asks a service, the local
                                          ComfyUI up to its ping timeout) comes back `checking: true`, not asked; the studio paints from it, then
                                          asks again without the flag and fills each provider in (the navigation direction rule 3, first paint)
  GET  /api/studio/jobs                   {jobs: [{slug, count, latest, candidates, history, images:[{path, url, provider, model, prompt, createdAt, sidecar, candidate, kind}]}]}: read from deliverables/studio/, newest job first
  GET  /api/studio/prompts?path=<.md>     {path, prompts: [{title, text, line, lang}]}: the fenced code blocks of one markdown file, each titled by the nearest heading above it

API (write)
  PUT  /api/manifest                       overwrite the manifest (the Mark-reviewed button)
  PUT  /api/home/layout                    {"widgets": [{id, on, size, collapsed, expanded, settings}, ...], "palette": {x, y, w, h}} saves the home layout for this copy's member (ids checked against the registry, sizes against the column spans, settings as a small object of that instrument's own choices, palette as where the add panel was left); {"reset": true} deletes the file so the default comes back
  POST /api/mantras                        {"text": "...", "author": "...", "source": "..."} appends one line to projects/pf-build/pf-mantras.md (logged MODIFIED); a team copy files it through the request path instead
  PUT  /api/file?path=<brain-relative>     overwrite a file NAMED IN THE MANIFEST, a dated prep in deliverables/call-prep/, or a Reader document (body = new text); appends a MODIFIED line to context/log.md via log.py. `&note=<one line>` names what changed and becomes that log line's text (the Reader sends "Reader: struck ..." / "Reader: moved ...")
  GET  /api/circle                         0.73.0: the extended circle's two files (circle.json, opportunities.json under the circle folder) as one answer, each row with its opportunities' titles and stages; `?through=<slug>` only the rows that card holds, their opportunities, and `cardOpps`, the opportunities the card itself is on; `?view=opportunities` (0.74.0) every opportunity with its holder's and people's names and cards, `sinceDays` and `movedDays`, and `counts` by stage and by kind. No folder: present false and empty lists. 403 in a team copy
  POST /api/circle/edit                    0.73.0: {"kind": "row", "slug", "what"} sets a circle row's one line (0.74.0: and marks it `edited` with the day, so a rebuild keeps it); {"kind": "opportunity", "id", "stage"?, "next"?} moves a stage (last_moved becomes today) or sets the next move. Nothing else in the files is written from a page; one log line per write
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
  POST /api/paste                          {"name": "clip.png", "data": "<base64>", "kind": "chat"|"note"|"item-note"} -> one picture kept in thoughts/notepad/ under a dated
                                           name, answered with its brain-relative path (and /api/image URL) so the message or note refers to a real file. 12 MB cap, images only, 403 in a team copy.
                                           0.90.0 (T-0354): "item-note" is a picture pasted into an item's note box; the box then carries ![picture](<path>) and the note draws it
  POST /api/attach                         {"item": "Q-0026", "ledger": "<holon id or its registered ledger path>", "name": "x.png", "data": "<base64>"} -> one picture
                                           attached to a ledger item (T-0219): png/jpg/gif/webp by magic bytes, 12 MB cap, kept at <ledger folder>/attachments/<id>-<yyyymmdd-hhmmss>-<name>,
                                           added to the item's `→ links` through tasks.py (its own log line); answers {path, url, links}. 400 on an unknown ledger or item or a non-image, 403 in a team copy
  POST /api/reply                          {"project": "<holon id>" (or "ledger": "<its registered path>"), "id": "T-0078", "text": "..."} -> a NOTE on a ledger item: the item's `note:` line
                                           through tasks.py (the existing keep-in-mind line kept, the reply added after it, the date read from this machine's clock),
                                           and the item STAYS OPEN. What the reply box beside every task of the owner's writes (T-0078, T-0077). 202 + a request file in a team copy
  GET  /api/replies                        0.93.0: {"replies": {"<project>/<id>": [{at, press, yours, replyAt, reply}, newest first]}}: what the session wrote when it took in a
                                           press on an item, read off context/answers-inbox.md (the batch's `processed:` line) for the note, answered and done presses of the last
                                           thirty days; a card draws it under the note as Claude's reply, apart from the owner's words. Nothing is written; {} in a team copy
  POST /api/note                           propose mode only (404 otherwise): {"target": "<path or empty>", "text": "..."} -> a `note` request file (a free-text change request about a file the member cannot edit)
  POST /api/live/bindings                  {"path": "<canvas>"} -> the live layer's ONE write: the bindings the server resolved, copied into the canvas's sibling .forge.json as binding: {kind, target} under each node id (a concept node's old binding cleared), one MODIFIED log line; the page sends only the path. 202 + a request file in a team copy
  POST /api/studio/generate               {provider, model, prompt, negative?, size?, n (1..4, default 2), references?: [brain-relative images], job, project?, quality?, imageSize?, seed?}
                                           -> {job, folder, images:[...]}: deliverables/studio/<job>/<yyyymmdd-hhmmss>-<provider>-<model>-<n>.<ext> + a sidecar .json each (candidate false)
                                           + one line in that folder's job.md, one CREATED log line per run. 400 on a bad request or a provider not ready, 502 with the provider's message in one line
  POST /api/studio/edit                   {provider, model, image: <path>, prompt, mask?: <path>, job, negative?, strength? (0 < s <= 1, image to image), seed?} -> the same shape as generate (one picture)
  POST /api/studio/candidate              {path, candidate: true|false} -> flips the flag in that picture's sidecar
  GET  /raw/<brain path>                   (0.61.0) a brain file's bytes for the preview frame: .html .htm .css .js .mjs .json .png .jpg .jpeg .gif .svg .webp .ico .woff .woff2 .ttf .mp4
                                           only, with their content types; 403 for any other type, a dot segment, a root-level .txt, a path out of the brain, or what the Files page hides
  GET  /api/mtime?path=<brain path>        (0.61.0) {path, mtime, size, at}: when a file last changed (the preview page polls it every 2 seconds); 404 when there is no such file
  GET  /api/preview/pages                  (0.61.0) {count, groups:[{folder, newest, files:[{path, name, mtime, at}]}]}: every .html the preview picker offers (no node_modules, dot folders,
                                           archive/, or viewer pages but its mockups/), by folder, newest first
  GET  /api/artifacts[?limit=N]            (0.76.0) {count, artifacts:[{name, path, folder, site, line, about, mtime, at, pages:[{name, path}]}], ms}: every built page by its
                                           name (title, h1, readme heading, file name), newest first; a folder under deliverables/ is one site with its entry page
                                           (the later of index.html and flow.html, else the newest); no skills/ or viewer/; heads cached per (mtime, size)
  GET  /api/usage?days=7[&day=YYYY-MM-DD][&session=<id or its start>]   (0.84.0) what used the plan, read from this machine's ~/.claude/projects
                                           transcripts by part_usage.py and priced at the API's list price per model ("API $ equivalent, a proxy for plan
                                           usage"): {unit, prices, today, day, days:[{day, label, today, total, sub, turns}], total, turns, dayTotal,
                                           top:{day, week}:[turn], sessions:[{id, title, project, total, sub, subShare, turns, dayTotal, dayTurns}], byWho,
                                           timeline (with &session: that session's turns on the day, in order, and the days it ran), scan}; a turn is
                                           {session, title, project, start, day, time, total, main, sub, subShare, calls, ctx, who, words, models,
                                           subModels, subagents, why, idleMin, parts, tokens}; 400 for a day outside the days or a session prefix
                                           that names two; the first read of a cold cache takes a second or two, a reload reads only what was appended
  GET  /api/thread?subject=<subject file>  (0.62.0) {subject, name, people, ledgers, updated, stands {head, text, reader}, items [ordered: what others wait on, the owner's, Claude's,
                                           anyone's; each {project, label, id, kind, text, who, due, waitsOn, holdsUp, options, note, why}], held, counts, depends [{path, title, kind, href, open?}],
                                           files, filesFrom, nextCall {title, start, people, prep?} or null, timeline [{date, text, section}]}; 404 for a path that is not a subject file
                                           0.77.0 adds: rollup {open, forOwner, inPieces} (its pieces counted in), done [closed items it takes in, newest first, with
                                           their files by name], parent / ancestors [{name, title, href, subject}], children [{subject, name, short, href, open, forOwner,
                                           stands}], now {name, path, line, next, page, exists, open, preview} or null, connects [{kind, name, title, href, line, thread,
                                           open?, missing?}], built [{name, path, line, open, preview, about, pages, at}], documents [{name, path, href, exists, at}],
                                           refs {"<ledger> <id>" | "<id>": {project, id, kind, words, closed, href} | {missing}}, subjectLinks {slug or path: {name, href}}
  GET  /api/work?item=<ledger>/<id>[&scope=item]  (0.63.0; scope=item 0.64.0 leaves out what the thread page already has) {ref, item (+ who, holdsUp, waitsOn), thread, brief {path, exists, text, writtenAt}, files (each with how: on the item | the thread
                                           depends on it | in progress), people, siblings, siblingsHeld, nextCall, history {notes, answer, log}, counts}; 404 for an unknown item
                                           0.79.0 adds: pick {options:[{name, link, kind (html | image | md | other), preview (/raw/ for a page or a picture, the
                                           Reader for markdown), exists, sections [{id, name}]}], chosen} for a question tagged pick with two or more linked options, else null
  GET  /api/brief/status?item=             (0.63.0) that item's entry in viewer/brief/status.json {state, startedAt, finishedAt, report, error, costUsd, step} + log; state missing with no brief.py
  POST /api/brief/run                      (0.63.0) {item, presses?} -> skills/item-brief/brief.py started detached for the item; 409 while one runs for it
  GET  /api/threads[?person=<slug>]       (0.62.0) {count, threads:[{subject, name, people, forOwner, open, held, last, href, nextCall (0.62.1)}]}, newest dated line first; 0.77.0: open / forOwner roll a thread's pieces in, own is its own count, parent the subject it is a piece of
  GET  /api/in-progress                    (0.61.0) context/in-progress.json resolved for the home widget and Today's In progress band (0.83.0): {projects:[{id, name, since, lastActivity, note, count, files:[{path, name, folder,
                                           exists, mtime, at, href, added, by}], items:[{ref, project, id, text, kind, state, href}]}], done (finished in the last 7 days), recent (the last
                                           15 files the log says were created or changed in 7 days that belong to no project)}; process files (context/, ledgers, the log, reports, skills/,
                                           viewer/, archive/, people/, *.json) are left out everywhere
  GET  /api/answers/pending                {count, since, items:[{project, id, kind, when, action, text, answer?, note?, ledger, presses}], lastSubmitAt, lastBatch, batches}
                                           (0.60.0): every answer, done, hold, reopen, block and note the viewer wrote onto a ledger since the last send, read off
                                           context/log.md (agent brain-viewer, after the cursor in viewer/answers-state.json; with no file, since the start of
                                           today), one row per item, resolved to its ledger row for the first sentence, the answer and the newest note. Newest first
  POST /api/answers/away                   (0.92.0) a viewer page went out of sight: with answers held and something waiting, it is sent after
                                           ANSWERS_AWAY_GRACE seconds unless a viewer page says it is here first -> {ok, held, toSend, awaySendsAt}
  POST /api/answers/here                   (0.92.0) a viewer page is in sight (every page load, and coming back to the front): the away timer stops
  GET  /api/settings                       (0.92.0) {answers: {hold, quietMinutes, default, teamCopy}, path}: what the Settings page changes
  PUT  /api/settings                       (0.92.0) {answers_hold?: bool, answers_quiet_minutes?: 1..60} written into viewer/settings.json, every other
                                           key kept; 400 for another key or a bad value, 403 in a team copy; the hold turned off sends what waits
  POST /api/answers/submit                 -> {ok, batch, count, path}: those rows appended as ONE batch to context/answers-inbox.md under the fixed header
                                           `## Batch <YYYY-MM-DD HH:MM> (<n> answers)` (the clock read here), the cursor moved past every line read, one log line.
                                           {ok: false, count: 0} and nothing written when nothing is pending; 403 in a team copy
  POST /api/sweep/run                      {project?} -> {ok, startedAt, pid, scope}: skills/question-sweep/sweep.py started detached in the brain root
                                           (BRAIN_ROOT set, output to viewer/sweep/last-run.log); {ok: false, error: "a check is already running since HH:MM"}
                                           while one runs; 501 when the runner is not in this copy, 403 in a team copy
  GET  /api/sweep/status                   viewer/sweep/status.json as the runner wrote it (state idle|running|done|failed|refused, counts, report, error, pid)
                                           + `log`: the last 5 lines of last-run.log + `reportHref`; {state: idle} with no file; {state: missing} with no runner

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
import collections
import datetime as dt
import fnmatch
import glob
import hashlib
import html
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

def load_part(name):
    """Run one part file of the server (0.68.0) in this module's namespace, where its code used to sit: the same names,
    the same globals, a traceback that names the part file and its line."""
    ap = os.path.join(HERE, name)
    with open(ap, "r", encoding="utf-8") as f:
        exec(compile(f.read(), ap, "exec"), globals())


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
# any *-tasks.md ledger; context/log.md; a file at the brain root (the seven key files, every *.txt, CLAUDE.md, index.md,
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
    ("pf-app-holon/pf-app-adapter-", False, "the adapter sheet, rewritten by a script on every pull"),
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
# 0.67.0 (the 10/06 review, finding 6): the scratch family. Test drawings go to one folder at the brain root, outside the
# architecture folder, git-ignored, and left out of /api/canvases, /maps and the architecture readme's count. The
# new-drawing picker defaults to it; a drawing there is <SCRATCH_REL>/<name>.canvas, one level deep.
SCRATCH_REL = str(SETTINGS.get("forge_scratch") or "canvases/scratch").replace("\\", "/").strip("/") or "canvases/scratch"
FORGE_EXT = (".canvas", ".forge.json")
FORGE_STAGES = ("concept", "prototype", "built", "stable")
FORGE_INNER = ("outer band", "inner layer")   # nested groups inside a cell: the band (what people see) and the core (what runs); not cells themselves
# The home page is a dashboard of widgets (2026-09-21, the home redesign). The owner asked for it to be more dynamic and
# less text-heavy, showing what is going on in the day and letting a user move every component around.
# The chat keeps its own full page at /chat, unchanged. The mentee content dashboard is at /mentee.
# In a team copy there is no chat at all (rules 4), so the copy's home stays the mentee dashboard.
# 0.65.0 (2026-10-06, Round 1 of the viewer review, the owner's yes): Today is the landing page at "/", the board moved to /home.
# /today still answers, so every old link lands on the same page. A team copy keeps the mentee dashboard at "/".
# 0.66.0 (2026-10-06, Round 2 of the viewer review, the menu folds, the owner's yes): seven pages folded into
# the ones that hold their work, and every old route answers with a 302 to the new place (REDIRECTS below), never a dead
# route. work.html, findings.html, requests.html, canvas-viewer.html, map.html, agents.html and holons.html are gone.
PAGES = {"/": "today.html", "/index.html": "today.html", "/home": "home.html", "/today": "today.html", "/mentee": "mentee-dashboard.html",
         "/projects": "projects.html", "/people": "people.html", "/chat": "chat.html",
         "/glossary": "glossary.html", "/reader": "reader.html", "/forge": "forge.html",
         "/from-claude": "review.html", "/studio": "studio.html", "/call": "call.html", "/files": "files.html",
         "/preview": "preview.html", "/thread": "thread.html", "/threads": "thread.html",
         "/opportunities": "opportunities.html",   # 0.74.0: every opportunity by stage (a placeholder in 0.73.0)
         "/artifacts": "artifacts.html",           # 0.76.0: every built thing by its name, one press to open it
         "/survey": "survey.html",                 # 0.78.0: one survey file as a page to press through (?path=&q=)
         "/usage": "usage.html",                   # 0.84.0: what used the plan, today and over the week (part_usage.py)
         "/share": "share.html",                   # 0.87.0: one person's copy of the brain as ticks (the sharing checklist)
         "/settings": "settings.html"}   # 0.92.0: the settings a person changes (sending answers, first)


def fold_redirect(path, q):
    """0.66.0: where a folded page's route now lives, as the Location of a 302, or None when the route is not a folded one.
    The query an old link carried goes with it where the new page reads the same thing; a browser keeps an old link's
    #fragment across the redirect when the Location carries none."""
    one = lambda k: (q.get(k) or [""])[0]
    enc = lambda v: urllib.parse.quote(v, safe="/")
    if path == "/work":                     # Work into Thread: the item's thread, or the thread page's "no thread yet" case
        item = one("item")
        if not item:
            return "/threads"
        return work_redirect(item) or "/thread?item=" + enc(item)
    if path in ("/review", "/findings", "/requests"):   # one page of what Claude filed for the owner's say
        keep = {k: v[0] for k, v in q.items() if k in ("source", "project", "owner") and v and v[0]}
        tail = ("?" + urllib.parse.urlencode(keep)) if keep else ""
        return "/from-claude" + tail + {"/review": "", "/findings": "#findings", "/requests": "#requests"}[path]
    if path in ("/canvases", "/live"):      # the canvas viewer and the live map are the Forge's read and live modes
        target = one("open") or one("path")
        if not target:
            return "/forge"
        extra = "&select=" + enc(one("select")) if one("select") else ""
        return "/forge?path=%s&mode=%s%s" % (enc(target), "read" if path == "/canvases" else "live", extra)
    if path == "/map":                      # retired 2026-09-09; the picker of drawings
        return "/forge"
    if path == "/maps":                     # 0.69.0 (the navigation direction, rule 2): the picker lives inside the Forge now;
        return "/forge?moved=maps"          # the Forge says so in one line for one release (rule 6)
    if path == "/agents":                   # one room: the chat's Running now strip and its sessions fold
        return "/chat#running"
    if path == "/holons":                   # the registry rows sit on Projects
        hid = one("id")
        return "/projects" + ("?holon=" + enc(hid) if hid else "") + "#holons"
    if path == "/status":                   # the status lamps sit at the foot of the home board
        return "/home#lamps"
    return None


REDIRECT_ROUTES = ("/work", "/review", "/findings", "/requests", "/canvases", "/live", "/map", "/maps", "/agents", "/holons", "/status")
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
# 2026-10-14 (0.78.1, the 10/14 librarian sweep LS-001): Claude SetupToken.txt joined, the sixth key file (added 10/06).
NEVER_READ = {"APIZZLE.txt", "PF App API.txt", "pfk_key.txt", "deepseek_key.txt", "Onboarding API.txt",
              "Claude SetupToken.txt", "openai_key.txt", "gemini_key.txt", "fal_key.txt", "hf_key.txt"}
SKIP_DIRS = {".git", "node_modules", "archive", ".obsidian", "__pycache__", ".claude"}
VERSION = "0.93.0"   # 0.93.0 (2026-10-26, the first build against the easy-to-use rules (brain-viewer-holon/brain-viewer-easy-to-use.md, written the same day on the owner's note on a card: "Where are the instructions for making an easy user experience? Why have you not started on that?"): on a task's steps the box is the only tick, the words never tick (twice he pressed a step's words to go where they said and the step ticked instead), and a step whose words name a place (a markdown link, a wikilink or a route) carries an open press at its right that opens the same place (BV.steps, stepPlace, stepGoHTML); Claude's reply drawn on the card: GET /api/replies reads context/answers-inbox.md once per change, the note, answered and done lines of the last thirty days keyed by project and id with each batch's processed clause beside them, and every card (Today, the thread page, the workspace, the projects and people rows) draws the clause under the note as Claude's reply with its time, apart from his words (10/21: "How am I supposed to read this response? This looks bad. This just looks like the same thread"), filled once per page the way the titles are (BV.exchange); {} in a team copy; help.json; exchange.test.py; layout.test.py keeps the press inside the row); 0.92.0 (2026-10-26, answers held until sent, from the owner after two presses woke the session while he was still working down the page ("why does this whole answers batch process run before I have moved off of the page to go through what has been answered?"; brain-viewer T-0359): a press still writes its ledger at once, but the batch to context/answers-inbox.md waits for the Send press at the bottom right of every page (BV.outbox, "Send N", POST /api/answers/submit {press: true}), the viewer going out of sight (POST /api/answers/away, sent after ANSWERS_AWAY_GRACE unless a viewer page posts /api/answers/here first, which every page does on load and on coming back to the front), or the quiet minutes with no new press (a server timer, re-armed at start when something waits); an undo while held is kept aside in viewer/answers-state.json and leads the next batch, and a press taken back before it was sent tells the session nothing; the hold and the minutes are settings (answers_hold, answers_quiet_minutes in viewer/settings.json) on the new Settings page (/settings, GET and PUT /api/settings, which writes those two keys only and keeps the rest), under more; off, each press goes at once as in 0.65.0; never on in a team copy; help.json, answers-hold.test.py, today.test.py runs with the hold off); 0.91.0 (2026-10-22, Changed since you last looked, from the owner on the night's 0.90.0 that nothing on Today pointed at ("why is there no easy way to get to this from the today page?"): a band under Up first, drawn while the running VERSION is not the one last marked seen or while a run wrote a note since the previous Today visit: the version and its what's-new entry's title, the entry's lines by their opening sentences (at most six, the rest counted), its where-to-see-it line, an older entry not yet seen as one line, Read what's new (the Reader on the viewer's what's-new page) and Seen (POST /api/whats-new/seen, kept in viewer/whats-new-seen.json), after which the band is one line, "Viewer <version>, seen", for the rest of the day; under it Overnight, the notes in deliverables/brain-dev/, night-agent/ and brain-engineer/ dated since that visit (today_visit's since, as the From band reads it), each a press to the Reader by its title, a delivery note first, at most five (GET /api/whats-new; empty in a team copy); every page carries {version, seen, path} as window.BV_WHATSNEW and the header's more fold opens on what's new, a dot on more and beside the link while unseen, the phone's menu press carrying the dot while folded, the row unchanged (BV.whatsNew); help.json's Today entries and every phone line name the band and the link; whats-new-band.test.py); 0.90.0 (2026-10-21, the night viewer track: pictures in a note, from the owner's 10/21 "images should be linkable in the note section as well" (T-0354): a note on an item draws every picture it names, an embed (![words](path), ![[path]]) or a link ([words](path), [[path]], a bare path) to a picture in the brain, as a row of thumbnails under its words on Today, the thread page and the workspace (BV.noteBlock, BV.noteHTML), each opening the image viewer, the row kept when the words fold; a picture pasted into a note box goes up through POST /api/paste (kind item-note, thoughts/notepad/) and the box carries ![picture](<path>) (BV.notePaste); a web address stays a link; the header at phone width (T-0340): below 600 px one line, back, the sun, the page name and a menu press that unfolds the rest under it (mountFold); a thread header may say gather: own (T-0343): it takes in only its own ledger's items (the holon project: names, else the one whose folder holds it) and the items that link it, its people still drawn; progress: names an in-progress project by its id or its name, any case (T-0342, inprog_ids); paint.test.py names its scratch brain as BRAIN_ROOT before serve.py loads, so no line reaches the real log (T-0350); for a team copy (2026-10-22): the From band reads the export's newer what's-new page, a file as [[path|title]], the lead sentences and the Your requests receipts (from_whats_new, from-band.test.py), and the send press brings in GitHub before it pushes (git pull --rebase --autostash, a rebase that stops undone and answered Not sent; brain-central T-0212's viewer half)); 0.89.1 (2026-10-21, the owner on the review item's bottom row, empty since 0.89.0: the row under a card draws every link of the item again, each by the title of what it opens (a document by its own title, a route by its page's), whether or not the words in the text link it too; an id chip's hover reads the item's words, not its link markup); 0.89.0 (2026-10-21, links drawn as links, from the owner on a review item whose link was a chip named after its file and whose route opened in the side drawer: every page carries the app's routes with their pages' titles (window.BV_ROUTES); in an item's text a bare route, a wikilink to a route and a markdown link to a route navigate, a markdown or labelled wikilink to a document opens it in the drawer under its words; the row under a card draws a route by its page's title, an outside page as a tab, a document by its own title (GET /api/titles), and leaves out what the text already links (BV.linksBelow); the glossary leaves an item's words and the pick's why line alone; links.test.py); 0.88.0 (2026-10-21, the From band on a member's Today, from the owner's ask for a section on her Today that holds what comes from his side so she can answer it there: in a team copy Today opens on it, her own rows (questions addressed to her, tasks she owns) with the queue's presses and a line on where her last press stands (saved, waiting, sent, landed), the files new since her last look and the notes written for her from the copy's what's-new, and one press that sends what she saved (GET /api/from-owner, POST /api/requests/send); in a copy the Calls band is not drawn, her rows leave the columns for the band, Today is back in her menu at /today, and the save line says the request is on this computer until it is sent; skills/team-brain/pull.py lands her answer, done or note on her own item; from-band.test.py); 0.87.1 (2026-10-21, the People page in a team copy: since the export's people tier the copy holds the cards, so GET /api/people and /api/person answer there with what the copy holds instead of a 403, and people.html lists and opens them read only, with no call-prep fold or form and a note that a change goes through the Reader as a request); 0.87.0 (2026-10-21, the sharing checklist, from the owner's ask for a checklist to tick off when he shares the brain with one person and for ticking a people card's parts in or out: /share draws one person's copy as ticks from the team-copy export's own selection (GET /api/share loads skills/team-brain/export.py by path); a folder, file or dashboard piece unticked goes into the export's share file for that person, a whole card into the held-back list every copy reads, a card section becomes [private] on its heading (POST /api/share, POST /api/share/section); owner only, 403 in a team copy; the menu's more fold carries it; help.json; share.test.py); 0.86.0 (2026-10-16, the steps on a task, from the owner's 10/16 note on a card whose instructions sat in its note as one block: a task's `steps:` segment (skills/brain-tasks/tasks.py `steps <id> --set | --tick N | --untick N`, twelve at most, 200 characters each) is drawn under the item's words on Today, the thread page and the workspace as a numbered list with a tick box each, before the chips and the note; a tick goes through PUT /api/tasks like every press, is journaled for the day's undo, logged as `step N of M ticked` and reaches the session as its own batch line (`· step: ...`); when every step is ticked, done is the card's lead press; the note sits under the steps, folded to its first line past about 200 characters with a more press (BV.noteBlock); the projects and people rows draw the steps read-only; the brief names the steps; help.json's Today entry and glossary say so; today.test.py 14f and layout.test.py's twelve-step card at both widths); 0.85.1 (2026-10-16, Today drawn right: the rows of Due today and New since you last looked keep their words the card's width with the kind label beside them, not over them (a hidden number left a three-track grid with two items); the next call is laid out like the one held, one line of state and its press at the right, never the prep's paragraph, and its weekday and time fit their column; the strip's cells have their own ground, so no grey block is painted behind an empty track; a queue card's parts stand apart; at phone width the kind label sits over the words; the call cards no longer take the page lead's width cap; an empty foot line or status line takes no room; a done row's long words wrap inside a phone's width; layout.test.py measures Today in a headless browser at 1200 and 375 px, every fold opened alone, in the release gate); 0.85.0 (2026-10-16, Today as chosen: the Today direction, amendment 3; brain-viewer T-0344): the agent's pick leads the page, one to three items as full cards with their presses and one line saying why each is up there, from context/today-pick.json (skills/today-pick/pick.py, GET /api/today/pick), the viewer's own ranking when nothing is picked today (a question with named choices new since the last visit, then due today, then what holds other work); then the calls as on the day, the call held carrying what came out of it and the now or next call its prep (GET /api/calls adds outcome and nextLater); then the work in progress as one strip of instruments, each its name, how fresh, one line of state, the count of the owner's open items and his next move as the one press; then Due today and New since you last looked side by side; then the backlog, on hold and the bands below, each folded with its count; the In progress band of 0.83.0 is gone; also 0.85.0 (2026-10-16, the ledger labelling consolidation): the glossary is the `glossary` key of help.json, one help file for the words and the pages, read by GET /api/glossary the way the markdown seed was (the seed in the viewer's holon is a tombstone); it gained a group, The things on a ledger, with one entry per kind and tag skills/brain-tasks/readme.md defines (task, question, decision, picture question, survey, pick, test, proposal, raised on a call, future, later, from, Might annoy you, To approve in the app, hold), and the entries on where an item is acted on (Today and its thread page, 0.65.0) and what the "?" button opens (the page's help panel, the glossary one press in) were corrected; the Today help entry says a test is not listed and shows only when opened by its link; the /glossary route line says what the "?" button opens; 0.84.0: the Usage page (/usage, GET /api/usage, part_usage.py): what used the plan today and over the week, read from this computer's Claude Code transcripts and priced at the API's list price per model as a proxy for plan usage: the days as bars, the top ten turns of the picked day and of the week with who started each, its first words, the workers' share and why it cost that, the sessions ranked, each opening onto its turns of the day with the context size and the idle time before each; a reply counted once across files (forks copy their parent's lines), a subagent counted in the turn that launched it; 0.83.0: In progress leads Today (the Today direction, amendment 2 rule 5; brain-viewer T-0338): the first band on Today draws context/in-progress.json through GET /api/in-progress, one block a project newest first, its name (its thread when a subject binds it), its note, its files as chips and the owner's open items on it as queue rows with their presses, each drawn once (the queue leaves them to the band), the header counting the projects and the rows; nothing registered, no band; 0.82.0: a team copy says its date at the top of every page: the team strip leads with "Your copy: exported <date and time>" from team-brain.json's exported_at (re-read on every page, so a pull while the viewer runs shows the new date), with a what's new link to the copy's WHATS-NEW.md when the export wrote one (mode_info's whats_new); 0.81.0: Today opens on the day (the Today direction, amendment 2): Yours to do leads with what is new since the previous visit (GET/POST /api/today/visit, the visit kept in viewer/today-visits.json, ten minutes one visit), each row marked new with why, then due today, then the backlog folded under one line with its count; the owner's held items in an On hold fold, never under Others owe today; every band header counts what it draws; a survey, a pick, a test and a friction card each say in one small line what kind of card it is and what its press does (BV.kind); 0.80.0: the friction cards on Today (GET /api/friction, POST /api/friction/answer): at most three open cards from the person's record, each quoting the instance and naming the pattern it resembles with its rule, answered annoying, not annoying or with a comment written into the record through skills/patterns/patterns.py and sent to the session like any press; 0.79.0: the pick question type: a question tagged pick carries a link per option, its workspace opens on the options side by side with the answer press under each, and Today and the thread page draw one Compare press; 0.78.1: Claude SetupToken.txt, the sixth key file, joins NEVER_READ so no page lists, searches or serves it; 0.78.0: the survey page (/survey, GET /api/survey, POST /api/survey/answer) and the survey type: a question tagged survey draws one press, Take the survey, on Today, the thread page and the workspace; 0.77.2: Today's "Built, to look at" draws only what is new (7 days) and still in play (an item linking it is open), and a choice question shows its answer box with no write press; 0.77.1: Today draws what its headings say: Today's calls holds calls only (a block such as therapy or an all-day marker is not drawn there); Others owe today holds other people's items, Claude's own overdue items are one line; the queue draws the app's calls from the last 30 days and counts the older ones in one line; 0.77.0: the thread page as a workspace (nesting, in progress first, the id rule, Progress on the side, the drawn map, Built here and Documents); 0.76.0: the artifacts page, its header entry and the Built band on Today; 0.75.0: the header in one row from the left with the full day; a call row on Today is one press
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
# 0.61.0: In progress joins at the foot, so the twelve columns still pack with no holes.
# 0.62.1: Threads beside it, the two halves of the last row.
# 0.65.0 (2026-10-06, Round 1 of the viewer review): the board is instruments only. Answer (deck) and Decide are off a new
# board -- an item is acted on on Today -- and stay in the folder, off, for anyone who adds them back in edit mode.
# 0.74.0: Opportunities beside the horizon, the circle's counts (in conversation, live) as one more instrument.
HOME_ORDER = ("masthead", "mantra", "next", "chat", "people", "horizon", "opportunities", "moved", "flow", "system", "in-progress", "work-threads")
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


class ExclusiveServer(ThreadingHTTPServer):
    """The listener, bound exclusively (0.68.0, review finding 8). http.server sets SO_REUSEADDR, and on Windows that lets a
    second process bind a port the first still holds, so two viewers split the requests between them. Here the reuse is
    off and, on Windows, SO_EXCLUSIVEADDRUSE is set before the bind: a second server on the same port fails to bind
    instead. port_answers() before the bind stays the friendly path; this is the floor under it when two starts race."""
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


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
    """A key file never appears on the Files page and is never served from it: the six at the root, the provider keys,
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


_FILES_WALK = {"key": None, "rows": None}


def files_stat_walk():
    """[(rel, name, mtime, size)] for every file the Files page may list. scandir's entries carry their stat on Windows,
    so this costs one directory listing per folder and no call per file (0.68.0)."""
    out, root_len = [], len(BRAIN.rstrip("\\/")) + 1
    stack = [BRAIN]
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name not in FILES_SKIP_DIRS:
                            stack.append(e.path)
                        continue
                    if files_hidden(e.name):
                        continue
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                out.append((e.path[root_len:].replace(os.sep, "/"), e.name, st.st_mtime, st.st_size))
    return out


def files_walk():
    """Every file the Files page lists, as rows, unsorted. Cached by what the rows are made of (0.68.0, the review's
    finding 8): every file's path, modification time and size, and the log index's own key. A walk that finds the same
    files at the same times reuses the rows built last time instead of building them again."""
    stats = files_stat_walk()
    log = files_log_index()
    key = (BRAIN, _FILES_LOG.get("key"), hash(tuple(stats)))
    if _FILES_WALK["key"] == key and _FILES_WALK["rows"] is not None:
        return [dict(r) for r in _FILES_WALK["rows"]]
    rows = []
    for rel, fn, mtime, size in stats:
        folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
        ext = os.path.splitext(fn)[1].lower()
        rows.append({"path": rel, "name": fn, "folder": folder, "extension": ext.lstrip("."), "type": files_type(ext),
                     "size": size,
                     "modified": dt.datetime.fromtimestamp(mtime).astimezone().isoformat(timespec="seconds"),
                     "last": log.get(rel)})
    _FILES_WALK["key"], _FILES_WALK["rows"] = key, rows
    return [dict(r) for r in rows]


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


# ---- the preview page (0.61.0, 2026-10-05): a web page shown inside the viewer, next to the brain ----
# A site mockup, a page design or a local dev server, looked at at phone and desktop widths and reloaded when its file
# changes. The frame reads a brain file through GET /raw/<path>: bytes as they sit, STATIC TYPES ONLY, so a page's own
# relative stylesheets, scripts and pictures load beside it. Refused: any other extension (a .py, a .md, a .txt), any
# dot segment, a path that climbs out of the brain, and everything the Files page hides (its skip rules, reused).
# Read-only, like every read here; the page polls GET /api/mtime to reload, and the picker is GET /api/preview/pages.
RAW_TYPES = {".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
             ".js": "application/javascript; charset=utf-8", ".mjs": "application/javascript; charset=utf-8",
             ".json": "application/json; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp", ".ico": "image/x-icon",
             ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf", ".mp4": "video/mp4"}
PREVIEW_SKIP_TOP = {"archive"}                       # top-level folders the picker never lists (plus every dot folder)
PREVIEW_VIEWER_REL = "skills/brain-viewer/"          # the viewer's own pages are not previews ...
PREVIEW_KEEP_REL = "skills/brain-viewer/mockups/"    # ... except its design directions, which are


def raw_abs(rel):
    """The brain file GET /raw/ may serve, or None: a static type, no dot segment, no root-level .txt, inside the brain,
    and nothing the Files page hides."""
    rel = norm(rel)
    if not rel:
        return None
    parts = rel.split("/")
    if any(p.startswith(".") for p in parts):
        return None
    ext = os.path.splitext(parts[-1])[1].lower()
    if ext not in RAW_TYPES or (len(parts) == 1 and ext == ".txt"):
        return None
    ap = files_abs(rel)
    return ap if ap and os.path.isfile(ap) else None


def mtime_api(rel):
    """GET /api/mtime?path=: when a brain file last changed -> (code, body). Any file the Files page may show."""
    ap = files_abs(rel)
    if not ap or not os.path.isfile(ap):
        return 404, {"error": "no such file in the brain", "path": rel}
    st = os.stat(ap)
    return 200, {"path": norm(rel), "mtime": st.st_mtime, "size": st.st_size,
                 "at": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}


def preview_pages():
    """GET /api/preview/pages: every .html under the brain the picker offers, grouped by folder, newest first (and the
    groups ordered by their newest page). Left out: node_modules and the other skipped folders, every dot folder,
    archive/, and the viewer's own pages except its mockups."""
    groups = {}
    root_len = len(BRAIN.rstrip("\\/")) + 1
    for dirpath, dirs, files in os.walk(BRAIN):
        rel_dir = dirpath[root_len:].replace("\\", "/") if len(dirpath) >= root_len else ""
        dirs[:] = sorted(d for d in dirs if d not in FILES_SKIP_DIRS and not d.startswith(".")
                         and not (not rel_dir and d in PREVIEW_SKIP_TOP))
        for fn in files:
            if not fn.lower().endswith((".html", ".htm")) or fn.startswith("."):
                continue
            rel = (rel_dir + "/" + fn) if rel_dir else fn
            if rel.startswith(PREVIEW_VIEWER_REL) and not rel.startswith(PREVIEW_KEEP_REL):
                continue
            try:
                mt = os.path.getmtime(os.path.join(dirpath, fn))
            except OSError:
                continue
            groups.setdefault(rel_dir or ".", []).append({"path": rel, "name": fn, "mtime": mt,
                                                         "at": dt.datetime.fromtimestamp(mt).isoformat(timespec="minutes")})
    out = []
    for folder, rows in groups.items():
        rows.sort(key=lambda r: r["mtime"], reverse=True)
        out.append({"folder": "" if folder == "." else folder, "newest": rows[0]["mtime"], "files": rows})
    out.sort(key=lambda g: g["newest"], reverse=True)
    return {"count": sum(len(g["files"]) for g in out), "groups": out}



# ---- artifacts (0.76.0, 2026-10-09): every built thing, by its name, one press to open it ----
# A built site or page had no place to be pressed: every link led to a document about it. GET /api/artifacts answers one row per built thing, newest first, NAMED:
# the page's <title> (a trailing "| ProspectForge" cut), else its first <h1>, else the folder readme's first heading, else
# the file name made readable. Pages that share a folder under deliverables/ are ONE artifact (a site): its entry page is
# whichever of index.html and flow.html changed last, else the newest page; a subfolder of a folder that has an
# index.html or flow.html belongs to that site (deliverables/<site>/problems/1.html). Everything else is one row a page.
# The set is the preview picker's, less skills/ (code pages) and viewer/ (the owner's own layer). Each page's head and
# each readme is read once per (mtime, size), so a repeat call costs the walk alone.
ARTIFACT_SKIP_TOP = {"skills", "viewer"}
ARTIFACT_ENTRY = ("index.html", "flow.html")
ARTIFACT_HEAD = 24000
_artifact_head_cache = {}        # abs path -> ((mtime, size), parsed head)
_ART_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_ART_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
_ART_DESC = re.compile(r"""<meta\s+[^>]*name=["']description["'][^>]*>""", re.I)
_ART_CONTENT = re.compile(r"""content=["']([^"']*)["']""", re.I)
_ART_SUFFIX = re.compile(r"\s+(?:\||\u00b7|\u2014|\u2013)\s+[^|\u00b7\u2014\u2013]+$")
_ART_FENCE = chr(96) * 3


def _art_text(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = html.unescape(s) if "&" in s else s
    return re.sub(r"\s+", " ", s).strip()


def artifact_name_clean(t):
    t = _art_text(t)
    cut = _ART_SUFFIX.sub("", t).strip()
    return cut or t


def _art_cached(ap):
    try:
        st = os.stat(ap)
    except OSError:
        return None, None
    sig = (st.st_mtime, st.st_size)
    hit = _artifact_head_cache.get(ap)
    return sig, (hit[1] if hit and hit[0] == sig else None)


def artifact_head(ap):
    """The page's <title>, first <h1> and meta description, read from its head once per (mtime, size)."""
    sig, row = _art_cached(ap)
    if sig is None:
        return {}
    if row is not None:
        return row
    try:
        with open(ap, encoding="utf-8", errors="replace") as f:
            src = f.read(ARTIFACT_HEAD)
    except OSError:
        src = ""
    m, h, d = _ART_TITLE.search(src), _ART_H1.search(src), _ART_DESC.search(src)
    c = _ART_CONTENT.search(d.group(0)) if d else None
    row = {"title": artifact_name_clean(m.group(1)) if m else "", "h1": artifact_name_clean(h.group(1)) if h else "",
           "desc": _art_text(c.group(1)) if c else ""}
    _artifact_head_cache[ap] = (sig, row)
    return row


def artifact_readme(folder_ap):
    """(the folder's readme file name or None, its first heading, its first paragraph in plain words)."""
    try:
        fn = next((n for n in os.listdir(folder_ap) if n.lower() == "readme.md"), None)
    except OSError:
        fn = None
    if not fn:
        return None, "", ""
    ap = os.path.join(folder_ap, fn)
    sig, row = _art_cached(ap)
    if sig is None:
        return None, "", ""
    if row is None:
        try:
            with open(ap, encoding="utf-8", errors="replace") as f:
                lines = f.read(ARTIFACT_HEAD).splitlines()
        except OSError:
            lines = []
        head, cur = "", []
        for ln in lines:
            s = ln.strip()
            if not head and not cur and s.startswith("#"):
                head = s.lstrip("#").strip()
                continue
            if not s:
                if cur:
                    break
                continue
            if not cur and (s.startswith(("#", "|", ">", "- ", "* ", "<")) or s.startswith(_ART_FENCE)):
                continue
            cur.append(s)
        para = " ".join(cur)
        para = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), para)
        para = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", para)
        para = re.sub(r"[*_" + chr(96) + r"]+", "", para).replace(" \u2014 ", ", ").replace("\u2014", ", ").strip()
        if len(para) > 240:
            para = para[:237].rsplit(" ", 1)[0] + "..."
        row = {"head": re.sub(r"[*_" + chr(96) + r"]+", "", head).replace("\u2014", ","), "para": para}
        _artifact_head_cache[ap] = (sig, row)
    return fn, row["head"], row["para"]


def artifact_readable(stem):
    """A file or folder name made readable: no extension, no date, dashes to spaces, a capital first."""
    s = re.sub(r"[-_]+", " ", os.path.splitext(stem)[0]).strip()
    s = re.sub(r"\s*\b\d{4} \d{2} \d{2}\b\s*", " ", s).strip() or s
    return (s[:1].upper() + s[1:]) if s else stem


def artifacts_list(limit=None):
    """GET /api/artifacts: {count, artifacts:[{name, path, folder, site, line, about, mtime, at, pages:[{name, path}]}], ms}."""
    t0 = time.time()
    root_len = len(BRAIN.rstrip("\\/")) + 1
    folders = {}                                                   # rel folder -> [(file name, mtime)]
    for dirpath, dirs, files in os.walk(BRAIN):
        rel_dir = dirpath[root_len:].replace("\\", "/") if len(dirpath) >= root_len else ""
        dirs[:] = sorted(d for d in dirs if d not in FILES_SKIP_DIRS and not d.startswith(".")
                         and not (not rel_dir and (d in PREVIEW_SKIP_TOP or d in ARTIFACT_SKIP_TOP)))
        for fn in files:
            if not fn.lower().endswith((".html", ".htm")) or fn.startswith("."):
                continue
            try:
                mt = os.path.getmtime(os.path.join(dirpath, fn))
            except OSError:
                continue
            folders.setdefault(rel_dir, []).append((fn, mt))
    # the sites: each folder under deliverables/ (never deliverables/ itself); a folder below one that holds an
    # index.html or flow.html joins that site
    entry_dirs = {d for d, fs in folders.items() if d.startswith("deliverables/") and any(f.lower() in ARTIFACT_ENTRY for f, _ in fs)}
    site_of = {}
    for d in folders:
        if not d.startswith("deliverables/"):
            continue
        parts, home = d.split("/"), d
        for i in range(2, len(parts)):
            if "/".join(parts[:i]) in entry_dirs:
                home = "/".join(parts[:i])
                break
        site_of[d] = home
    sites, rows = {}, []
    for d, fs in folders.items():
        if d in site_of:
            sites.setdefault(site_of[d], []).extend((d + "/" + f, mt) for f, mt in fs)
        else:
            rows.extend({"kind": "page", "folder": d, "pages": [((d + "/" + f) if d else f, mt)]} for f, mt in fs)
    rows.extend({"kind": "site", "folder": home, "pages": pages} for home, pages in sites.items())
    out = []
    for r in rows:
        folder, kind = r["folder"], r["kind"]
        pages = sorted(r["pages"], key=lambda p: p[1], reverse=True)
        top = [p for p in pages if p[0].rsplit("/", 1)[0] == folder]
        cands = [p for p in top if p[0].rsplit("/", 1)[-1].lower() in ARTIFACT_ENTRY]
        entry = (cands or top or pages)[0][0]
        folder_ap = os.path.join(BRAIN, folder.replace("/", os.sep)) if folder else BRAIN
        # a loose page's folder readme is about the folder, so it lends ABOUT, never the page's line or name;
        # deliverables/ itself and the brain's root lend nothing
        rd, rhead, rpara = artifact_readme(folder_ap) if folder and folder != "deliverables" else (None, "", "")
        head = artifact_head(os.path.join(BRAIN, entry.replace("/", os.sep)))
        name = head.get("title") or head.get("h1") or (rhead if kind == "site" else "") \
            or artifact_readable(folder.rsplit("/", 1)[-1] if kind == "site" or (folder and entry.rsplit("/", 1)[-1].lower() in ARTIFACT_ENTRY)
                                 else entry.rsplit("/", 1)[-1])
        line = (rpara if kind == "site" else "") or head.get("desc") or ""
        mt = max(p[1] for p in pages)
        if rd and kind == "site":
            try:
                mt = max(mt, os.path.getmtime(os.path.join(folder_ap, rd)))
            except OSError:
                pass
        others = []
        for p, _ in sorted(pages, key=lambda p: p[0]):
            if p == entry:
                continue
            h = artifact_head(os.path.join(BRAIN, p.replace("/", os.sep)))
            nm = next((x for x in (h.get("title"), h.get("h1")) if x and x != name), "")
            others.append({"name": nm or artifact_readable(p[len(folder) + 1:].replace("/", " ")), "path": p})
        out.append({"name": name, "path": entry, "folder": folder, "site": kind == "site" and len(pages) > 1, "line": line,
                    "about": (folder + "/" + rd) if rd else None, "mtime": mt,
                    "at": dt.datetime.fromtimestamp(mt).isoformat(timespec="minutes"), "pages": others})
    out.sort(key=lambda a: a["mtime"], reverse=True)
    total = len(out)
    if limit:
        out = out[:limit]
    return {"count": total, "artifacts": out, "ms": int((time.time() - t0) * 1000)}


# ---- Today's "Built, to look at": only what is new and still in play (0.77.2, 2026-10-13) ----
# The owner, 10/13, on the band showing the September booth backdrop and banner: "this built to look at thing is displaying
# some irrelevant stuff ... Why is this showing up on the built to look at thing? And how does it know when to close those
# things?" It knew nothing: it drew the three newest pages by file date, so finished work stayed until three newer pages
# pushed it off. A built thing is to look at while it is new and in play: built in the last BUILT_DAYS days, and not
# finished, where finished means at least one ledger item links it (or a file inside its site) and every such item is
# closed. GET /api/artifacts?fresh=1 applies this; the artifacts page, which lists everything, does not ask for it.
BUILT_DAYS = 7


def artifact_link_states():
    """{linked path -> set of "open" / "closed"} over every registered ledger's items, read with the ledger's own parser."""
    out = {}
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
                st = "closed" if it["state"] in ("done", "answered") else "open"
                for link in it.get("links") or []:
                    out.setdefault(str(link).strip().replace("\\", "/").lstrip("./"), set()).add(st)
    return out


def built_to_look_at(rows, days=BUILT_DAYS):
    """The rows of artifacts_list() that are new (built within `days`) and not finished (see the banner above)."""
    cut, states, keep = time.time() - days * 86400, artifact_link_states(), []
    for a in rows:
        if (a.get("mtime") or 0) < cut:
            continue
        paths = {a.get("path")} | {pg.get("path") for pg in (a.get("pages") or [])}
        folder, seen = a.get("folder") or "", set()
        for linked, sts in states.items():
            if linked in paths or (a.get("site") and folder and linked.startswith(folder + "/")):
                seen |= sts
        if seen and "open" not in seen:
            continue
        keep.append(a)
    return keep


# ---- usage (0.84.0, 2026-10-15): which prompts and actions used the most of the plan, today and over the week ----
# The owner asked for the actions and prompts that pulled the most usage on the day and over the week, in the viewer. The
# scan is skills/brain-viewer/part_usage.py, imported here and runnable alone, so the terminal and the page print the same
# numbers: this machine's Claude Code transcripts (~/.claude/projects, every project folder), a reply counted once across
# files, a subagent counted in the turn that launched it, each reply priced at the API's list price for its model. It reads
# no brain file and writes nothing; a team copy or a mentee's brain shows its own computer's usage. The first read of a
# cold cache takes a second or two, so the page paints first and asks after (paint.test.py lists the call after paint).
if HERE not in sys.path:
    sys.path.insert(0, HERE)
try:
    import part_usage as usage_part  # noqa: E402
except Exception as _ue:              # noqa: BLE001 -- a code copy without the module answers 501 on /api/usage
    usage_part, _USAGE_ERR = None, str(_ue)
else:
    _USAGE_ERR = None


def usage_api(q):
    """GET /api/usage: (code, body). ?days=7, ?day=YYYY-MM-DD (one of those days), ?session=<id or its start>."""
    if usage_part is None:
        return 501, {"error": "the usage scan is not in this code copy (%s)" % _USAGE_ERR}
    one = lambda k: (q.get(k) or [""])[0].strip()
    try:
        days = int(one("days") or 7)
    except ValueError:
        return 400, {"error": "days must be a whole number"}
    try:
        out = usage_part.report(days=days, day=one("day") or None, session=one("session") or None)
    except ValueError as e:
        return 400, {"error": str(e)}
    out["_servedAt"] = dt.datetime.now().isoformat(timespec="seconds")
    return 200, out




# ---- in progress (0.61.0, 2026-10-05): the work being made right now, for the home widget of that name ----
# context/in-progress.json is agent-written by skills/in-progress/progress.py: projects, the files each is made of, the
# ledger items it answers to. GET /api/in-progress answers it resolved -- every file with its folder, its time and the
# link that opens it, every item in its own words off its ledger -- plus "other recent work": the files the log says
# were created or changed in the last seven days that belong to no project. The brain's own process files are left out
# everywhere (inprog_is_process below), so the widget shows the work and not the machinery, and does no parsing itself.
INPROG_REL = "context/in-progress.json"
INPROG_RECENT_DAYS = 7
INPROG_RECENT_MAX = 15
INPROG_SKIP_PREFIX = ("context/", "skills/", "viewer/", "archive/", "people/", "transcripts/import-reports/",
                      "deliverables/night-agent/", "deliverables/question-sweep-", "deliverables/task-review-")
INPROG_TEXT_EXT = {".md", ".txt", ".json", ".py", ".js", ".css", ".csv", ".canvas"}
_INPROG_LOG_PATH = re.compile(r"^([A-Za-z0-9_.\-/]+\.[A-Za-z0-9]{1,8})(?=\s+--|:|\s|$)")


def inprog_is_process(rel):
    """A file of the brain's own machinery, never shown as work: state, ledgers, logs, contracts, reports, code, records."""
    r = str(rel or "").replace("\\", "/").lower()
    leaf = r.rsplit("/", 1)[-1]
    # a file at the brain's root is one of its anchors (CLAUDE.md, index.md, the zak-*.md extracts, the playbook), never work
    return (r.startswith(INPROG_SKIP_PREFIX) or "/" not in r or leaf.endswith("-tasks.md") or leaf.endswith(".contract.json")
            or "hot-cache" in r or leaf == "log.md" or leaf.endswith(".json") or leaf.startswith("."))


def inprog_href(rel):
    ext = os.path.splitext(rel)[1].lower()
    q = urllib.parse.quote(rel)
    if ext in (".html", ".htm"):
        return "/preview?path=" + q
    if ext in IMAGE_EXT:
        return "/api/image?path=" + q
    if ext in INPROG_TEXT_EXT:
        return "/reader?path=" + q
    return "/api/file-raw?path=" + q


def inprog_file(rel, extra=None):
    ap = files_abs(rel)
    mt = None
    if ap and os.path.isfile(ap):
        try:
            mt = os.path.getmtime(ap)
        except OSError:
            mt = None
    row = {"path": rel, "name": rel.rsplit("/", 1)[-1], "folder": rel.rsplit("/", 1)[0] if "/" in rel else "",
           "exists": mt is not None, "mtime": mt,
           "at": dt.datetime.fromtimestamp(mt).isoformat(timespec="minutes") if mt else None, "href": inprog_href(rel)}
    row.update(extra or {})
    return row


def inprog_item(ref, cache, holons):
    """'pf-build T-0115' -> the item in its own words off its ledger (or the ref itself, marked missing)."""
    hid, _, iid = str(ref or "").strip().partition(" ")
    out = {"ref": ref, "project": hid, "id": iid, "text": ref, "kind": "question" if iid.startswith("Q") else "task",
           "state": None, "missing": True}
    rel = holons.get(hid)
    if rel:
        it = _ledger_row(rel, iid, cache)
        if it:
            out.update(text=it["text"], kind=it["kind"], state=it["state"], mark=it["mark"], missing=False,
                       href="/projects?id=%s#%s-%s-%s" % (urllib.parse.quote(hid), "q" if it["kind"] == "question" else "t", hid, iid))
            # 0.93.0: the subject file the item links, so an instrument's name press can open the item on its thread
            subj = next((l for l in (it.get("links") or []) if "/subjects/" in str(l) and str(l).endswith(".md")), None)
            if subj:
                out["subject"] = subj
    return out


def in_progress_api():
    ap = os.path.join(BRAIN, INPROG_REL.replace("/", os.sep))
    data, err = {}, None
    if os.path.isfile(ap):
        data = _json_read(ap)
        if data is None:
            data, err = {}, "%s could not be read" % INPROG_REL
    holons = {h.get("id"): h.get("tasks") for h in registry().get("holons", []) if h.get("tasks")}
    cache, owned, projects = {}, set(), []
    for p in data.get("projects") or []:
        if not isinstance(p, dict):
            continue
        files = []
        for f in p.get("files") or []:
            rel = norm(str((f or {}).get("path") or ""))
            if not rel:
                continue
            owned.add(rel)
            if inprog_is_process(rel):
                continue
            files.append(inprog_file(rel, {"added": f.get("added"), "by": f.get("by"), "touched": f.get("touched")}))
        files.sort(key=lambda r: (r["mtime"] or 0, r.get("touched") or r.get("added") or ""), reverse=True)
        newest = max([r["mtime"] for r in files if r["mtime"]] or [0])
        last = str(p.get("lastActivity") or p.get("since") or "")
        if newest:
            fl = dt.datetime.fromtimestamp(newest).isoformat(timespec="seconds")
            last = max(last, fl)
        projects.append({"id": p.get("id"), "name": p.get("name") or p.get("id"), "since": p.get("since"), "lastActivity": last,
                         "note": p.get("note") or "", "count": len(files), "files": files,
                         "items": [inprog_item(x, cache, holons) for x in p.get("items") or []]})
    projects.sort(key=lambda p: p["lastActivity"] or "", reverse=True)
    try:
        bound = threads_for_progress()                 # 0.62.0: a subject file that binds the project gets a thread link
    except Exception:                                  # noqa: BLE001
        bound = {}
    for p in projects:
        p["thread"] = bound.get(p["id"])
    cut = (dt.datetime.now() - dt.timedelta(days=INPROG_RECENT_DAYS))
    done = []
    for p in data.get("done") or []:
        for f in (p or {}).get("files") or []:
            if norm(str((f or {}).get("path") or "")):
                owned.add(norm(f["path"]))
        if str((p or {}).get("doneAt") or "") >= cut.isoformat(timespec="seconds"):
            done.append({"id": p.get("id"), "name": p.get("name"), "doneAt": p.get("doneAt"), "count": len(p.get("files") or [])})
    done.sort(key=lambda p: p["doneAt"] or "", reverse=True)
    # other recent work: the log's own CREATED / MODIFIED lines, newest first, the path each opens with (RULE 27)
    recent, seen = [], set()
    lines = [l for l in log_lines(since=cut.date().isoformat())]
    stamp_cut = cut.strftime("%Y-%m-%d %H:%M")
    for line in reversed(lines):
        m = FILES_LOG_RE.match(line)
        if not m or m.group(3) not in ("CREATED", "MODIFIED") or m.group(1) < stamp_cut:
            continue
        pm = _INPROG_LOG_PATH.match(m.group(4).strip())
        if not pm:
            continue
        tok = pm.group(1).replace("\\", "/")
        while tok.startswith("./"):
            tok = tok[2:]
        rel = norm(tok)
        if not rel or rel in seen or rel in owned or inprog_is_process(rel):
            continue
        seen.add(rel)
        row = inprog_file(rel, {"loggedAt": m.group(1), "agent": m.group(2), "action": m.group(3)})
        if not row["exists"]:
            continue
        recent.append(row)
        if len(recent) >= INPROG_RECENT_MAX:
            break
    out = {"file": INPROG_REL, "exists": os.path.isfile(ap), "projects": projects, "done": done, "recent": recent,
           "recentDays": INPROG_RECENT_DAYS, "writtenBy": "skills/in-progress/progress.py"}
    if err:
        out["error"] = err
    return out


# ---- threads (0.62.0, 2026-10-05): one page per subject file, cutting across the ledgers ----
# A piece of work (a placement, a partnership) has its to-dos on several ledgers and leans on files outside them. Its
# subject file (projects/*/subjects/<slug>.md, written by import-checkup's subject pass) already declares who it is about
# (`people:`) and the words that name it (`match:`), so the thread is DERIVED, never drawn (rules 1): GET /api/thread
# gathers every open item on every registered ledger that names one of its people or carries one of its words, plus the
# items those wait on and the items waiting on them, and joins the file's own sections, its `depends:` files, the
# in-progress project bound by `progress:`, the next call with its people and its dated lines. Stored nowhere.
THREAD_REFS = re.compile(r"\b[TQ]-\d{4}\b")
THREAD_DATED = re.compile(r"^[-*+]\s+(\d{4}-\d{2}-\d{2})\s*·\s*(.+)$")
THREAD_TIMELINE_SECTIONS = ("decisions", "learned", "timeline")


def ledger_label(h):
    """A ledger's short name: the owner's own label in viewer/settings.json `project_labels`, else the registry name
    without its bracket (the Projects page's rule)."""
    labels = SETTINGS.get("project_labels") if isinstance(SETTINGS.get("project_labels"), dict) else {}
    return labels.get(h.get("id")) or re.sub(r"\s*\(.*\)\s*$", "", str(h.get("name") or h.get("id") or ""))


def thread_ledgers():
    """Every item on every registered ledger, each carrying its ledger id, path and short label. Read once per request."""
    rows = []
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        ap = os.path.join(BRAIN, h["tasks"].replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            p = ledger.parse(ledger.read(ap))
        except Exception:                                          # noqa: BLE001
            continue
        for it in p["items"]:
            r = dict(it)
            r.pop("line", None)
            r.update(project=h["id"], ledger=h["tasks"], label=ledger_label(h))
            rows.append(r)
    return rows


def thread_open(r):
    return (r["kind"] == "task" and r["mark"] in " -") or (r["kind"] == "question" and r["mark"] == "?")


def is_subject_rel(rel):
    rel = norm(rel)
    return bool(rel and rel.endswith(".md") and os.path.basename(rel) != "readme.md"
                and any(fnmatch.fnmatch(rel, g) for g in SUBJECTS_GLOBS)
                and os.path.isfile(os.path.join(BRAIN, rel.replace("/", os.sep))))


def card_display_name(slug):
    rel, ap = card_path(slug)
    if not ap:
        return slug.replace("-", " ").title()
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            fm, body = split_fm(f.read(3000))
        name = next((l[2:].strip() for l in body if l.startswith("# ")), fm.get("name") or slug)
        return re.sub(r"\s*\([^)]*\)\s*$", "", re.split(r"\s+(?:·|—|--|\|)\s+", name)[0]).strip() or slug      # the name alone, not its alias or role
    except Exception:                                              # noqa: BLE001
        return slug


def thread_subject(rel):
    """One subject file read for its thread: the routing fields, the summary section, the dated lines."""
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    with open(ap, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    fm, body = split_fm(raw)
    extra = subject_fm_extra(raw)
    name = fm.get("subject") or next((l[2:].strip() for l in body if l.startswith("# ")), os.path.basename(rel)[:-3])
    # the summary: the section Stage 5b names "Where it stands (<date>)"; with none, the first paragraph under the title
    stands_head, stands = None, []
    for i, l in enumerate(body):
        if re.match(r"^##\s+where it stands\b", l, re.I):
            stands_head = l[3:].strip()
            stands = h2_section(body, "Where it stands")
            break
    if stands_head is None:
        para, on = [], False
        for l in body:
            if l.startswith("#"):
                if on:
                    break
                continue
            if l.strip():
                para.append(l)
                on = True
            elif on:
                break
        stands = para
    timeline, sect = [], ""
    for l in body:
        if l.startswith("## "):
            sect = l[3:].strip()
            continue
        m = THREAD_DATED.match(l)
        if m and sect.lower().startswith(THREAD_TIMELINE_SECTIONS):
            timeline.append({"date": m.group(1), "text": m.group(2).strip(), "section": sect})
    timeline.sort(key=lambda t: t["date"], reverse=True)          # stable: same-day lines keep the file's order
    return {"rel": rel, "name": name, "slug": fm.get("slug") or os.path.basename(rel)[:-3], "status": str(fm.get("status") or "").lower(),
            "people": fm_list(fm, "people"), "match": fm_list(fm, "match"), "canonical": fm_list(fm, "canonical"),
            "depends": fm_list(fm, "depends"), "progress": str(fm.get("progress") or "").strip(),
            "project": str(fm.get("project") or "").strip(), "updatedField": str(fm.get("updated") or "").strip(),
            "standsHead": stands_head, "stands": "\n".join(stands).strip(), "timeline": timeline,
            # 0.77.0, the workspaces direction: nesting (`parent:`), who routes alone (`routes:`), the thing in progress
            # (`now:`) and the drawn connections (`connects:`)
            "parent": str(fm.get("parent") or "").strip().strip('"').strip("'"), "routes": fm_list(fm, "routes"),
            "now": extra.get("now"), "connects": extra.get("connects") or [],
            # 0.90.0 (brain-viewer T-0343): `gather: own` -- the thread takes in only its own ledger's items and the items
            # that link it; its people and words no longer pull in other work (thread_gather)
            "gather": str(fm.get("gather") or "").strip().strip('"').strip("'").lower()}


def thread_own_ledgers(subj):
    """The ledger(s) a thread calls its own, for `gather: own` (0.90.0, T-0343): the registered holon its `project:`
    names, else the holon whose folder holds the subject file (the deepest one). An empty set means only the items
    that link the subject file are its own."""
    hs = [h for h in registry().get("holons", []) if h.get("tasks")]
    pid = str(subj.get("project") or "").strip()
    if any(h.get("id") == pid for h in hs):
        return {pid}
    rel = str(subj.get("rel") or "")
    best, depth = None, -1
    for h in hs:
        p = str(h.get("path") or "").replace("\\", "/").strip("/")
        if p and rel.startswith(p + "/") and len(p) > depth:
            best, depth = h["id"], len(p)
    return {best} if best else set()


# ---- the workspace fields (0.77.0, 2026-10-09, the workspaces direction W1) ----
# split_fm reads a shallow `k: v`, so the two structured fields are read here from the raw frontmatter:
#   now: {name: "...", path: <brain file>, line: "...", next: "..."}          (inline, or an indented block of k: v)
#   connects:
#     - {kind: part-of, to: <subject slug or brain file>, line: "..."}         (or "- kind: ..." with indented k: v lines)
# Every other reader of a subject file (subject_pass.py, call-prep) reads top-level lines only and passes these by.
CONNECT_KINDS = ("part-of", "piece", "feeds", "fed-by", "beside", "builds-on")
_FLOW_PAIR = re.compile(r"""\s*([A-Za-z_][\w-]*)\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^,}]*)\s*,?""")


def _fm_scalar(v):
    v = str(v or "").strip()
    if len(v) >= 2 and v[0] == v[-1] == '"':
        return v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def _fm_flow_map(s):
    s = str(s or "").strip()
    if s.startswith("{"):
        s = s[1:]
    if s.endswith("}"):
        s = s[:-1]
    return {m.group(1): _fm_scalar(m.group(2)) for m in _FLOW_PAIR.finditer(s) if m.group(1)}


def subject_fm_extra(text):
    """{now: {name, path, line, next} or None, connects: [{kind, to, line}]} from a subject file's raw frontmatter."""
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    out = {"now": None, "connects": []}
    if not lines or lines[0].strip() != "---":
        return out
    end = next((i for i in range(1, min(len(lines), 200)) if lines[i].strip() == "---"), None)
    if end is None:
        return out
    fm = lines[1:end]
    i = 0
    while i < len(fm):
        m = re.match(r"^(now|connects):\s*(.*)$", fm[i])
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        j, block = i + 1, []
        while j < len(fm) and fm[j].strip() and (fm[j][0] in " \t" or fm[j].startswith("- ")):
            block.append(fm[j])
            j += 1
        i = j
        if key == "now":
            d = _fm_flow_map(rest) if rest.startswith("{") else {}
            if not d:
                for b in block:
                    mm = re.match(r"^\s+([A-Za-z_][\w-]*)\s*:\s*(.*)$", b)
                    if mm:
                        d[mm.group(1)] = _fm_scalar(mm.group(2))
            if d.get("name") or d.get("path"):
                out["now"] = {k: str(d.get(k) or "").strip() for k in ("name", "path", "line", "next")}
            continue
        entries = []
        if rest.startswith("["):
            entries = [_fm_flow_map(g) for g in re.findall(r"\{[^{}]*\}", rest)]
        for b in block:
            s = b.strip()
            if s.startswith("- "):
                s = s[2:].strip()
                entries.append(_fm_flow_map(s) if s.startswith("{") else {})
                if not s.startswith("{"):
                    mm = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", s)
                    if mm:
                        entries[-1][mm.group(1)] = _fm_scalar(mm.group(2))
            elif entries:
                mm = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", s)
                if mm:
                    entries[-1][mm.group(1)] = _fm_scalar(mm.group(2))
        for e in entries:
            kind = str(e.get("kind") or "").strip().lower()
            to = str(e.get("to") or "").strip()
            if kind in CONNECT_KINDS and to:
                out["connects"].append({"kind": kind, "to": to, "line": str(e.get("line") or "").strip()})
    return out


def thread_team():
    """The owner's standing team: the members of the declared `team` call thread (skills/call-prep/call-prep-groups.json)."""
    try:
        return set(group_members().get("team") or ())
    except Exception:                                              # noqa: BLE001
        return set()


def thread_route_people(slugs):
    """The people whose name on an item routes it to the thread by itself. The standing team is on most items in the brain,
    so a teammate in a subject's `people:` routes nothing alone (the item still comes in when it carries one of the
    subject's words); a subject made only of teammates routes on all of them."""
    s = set(slugs or [])
    rest = s - thread_team()
    return rest or s


def subj_route_people(sub):
    """0.77.0: a subject's `routes:` (when it has one) names the people whose name routes an item, a call or a transcript
    to it by themselves; its `people:` stay the people drawn. A piece of a larger thread names the parent's people too
    (the mentor on a candidate's screening), and without `routes:` it would take every one of the parent's items."""
    return set(sub.get("routes") or []) or thread_route_people(sub["people"])


def _link_path(l):
    return norm(str(l or "").strip().strip("[]").split("|")[0].split("#")[0].strip())


def thread_gather(subj, items, exclude=None, done=None):
    """The open items of a thread, ordered, and its held ones. Who is in: an open item naming one of the thread's people
    in its `people:` field, or carrying one of its `match:` words in its text; plus, one step out, the open items such an
    item waits on (its `blocked:` names them) and the open items waiting on it. Order: what other items wait on, then the
    owner's, then Claude's, then anyone else's; inside each, the due day (none last), then the oldest first.
    0.77.0: an item whose link names this subject file is in too ("linked"); `exclude` holds the (project, id) keys a
    piece of this thread claims (the most specific thread wins); `done`, when a list is given, receives the closed items
    the same rule takes in (done tasks and answered questions, newest first), for the Progress fold.
    0.90.0 (T-0343): a subject whose header says `gather: own` takes in only the items on its own ledger
    (thread_own_ledgers) and the items whose link names it; its people and words route nothing. Its people are still
    drawn as cards and still find its next call; the one step out over `blocked:` is unchanged."""
    own = subj.get("gather") == "own"
    own_ids = thread_own_ledgers(subj) if own else set()
    people = set() if own else subj_route_people(subj)
    me = subj.get("rel") or ""
    terms = [] if own else [t for t in subj["match"] if t.strip()]
    rx = re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(re.escape(t.strip()).replace(r"\ ", r"\s+") for t in terms), re.I) if terms else None
    key = lambda r: (r["project"], r["id"])
    byk = {key(r): r for r in items}
    opens = [r for r in items if thread_open(r)]
    waits_on, held_up = {}, {}
    for r in opens:
        if r["kind"] == "task" and r.get("blocked"):
            for bid in THREAD_REFS.findall(str(r["blocked"])):
                b = byk.get((r["project"], bid))
                if b is not None and thread_open(b) and b is not r:
                    waits_on.setdefault(key(r), []).append(key(b))
                    held_up.setdefault(key(b), []).append(key(r))
    def reasons(r):
        w = []
        if own and r["project"] in own_ids:
            w.append("own ledger")
        if people & set(r.get("people") or []):
            w.append("person")
        if rx and rx.search(r.get("text") or ""):
            w.append("words")
        if me and any(_link_path(l) == me for l in r.get("links") or []):
            w.append("linked")
        return w
    ex = exclude or set()
    why = {}
    for r in opens:
        w = reasons(r)
        if w and key(r) not in ex:
            why[key(r)] = w
    if done is not None:
        for r in items:
            closed = (r["kind"] == "task" and r["mark"] == "x") or (r["kind"] == "question" and r["mark"] == "a")
            if closed and key(r) not in ex and reasons(r):
                done.append({"project": r["project"], "id": r["id"], "kind": r["kind"], "text": r.get("text") or "",
                             "answer": r.get("answer") or "", "date": r.get("done") or r.get("answered") or r.get("created") or "",
                             "who": (r.get("to") or OWNER) if r["kind"] == "question" else r.get("owner"),
                             "links": r.get("links") or []})
        done.sort(key=lambda x: (x["date"] or "", x["id"]), reverse=True)
    for k in list(why):
        for b in waits_on.get(k, []):
            why.setdefault(b, ["holds a thread item"])
        for w in held_up.get(k, []):
            why.setdefault(w, ["waits on a thread item"])
    def words(k):
        r = byk[k]
        return {"id": r["id"], "project": r["project"], "text": clip(r.get("text") or "", 140)}
    rows, held = [], []
    for k, w in why.items():
        if k in ex:
            continue
        r = byk[k]
        who = (r.get("to") or OWNER) if r["kind"] == "question" else r.get("owner")
        hu = held_up.get(k, [])
        group = 0 if hu else 1 if who == OWNER else 2 if who == "@claude" else 3
        row = {"project": r["project"], "ledger": r["ledger"], "label": r["label"], "id": r["id"], "kind": r["kind"],
               "mark": r["mark"], "state": r.get("state"), "text": r.get("text") or "", "note": r.get("note"),
               "options": r.get("options"), "owner": r.get("owner"), "to": r.get("to"), "who": who,
               "due": r.get("due"), "created": r.get("created"), "until": r.get("until"), "blocked": r.get("blocked"),
               "waitsOn": [words(x) for x in waits_on.get(k, [])], "holdsUp": [words(x) for x in hu],
               "people": r.get("people") or [], "links": r.get("links") or [], "tags": r.get("tags") or [],
               "steps": r.get("steps") or [],                      # 0.86.0
               "why": w, "group": group}
        (held if ledger.is_held(r) else rows).append(row)
    order = lambda x: (x["group"], x["due"] or "9999-99-99", x["created"] or "", x["project"], x["id"])
    rows.sort(key=order)
    held.sort(key=lambda x: (x["until"] or "", order(x)))
    return rows, held


def thread_counts(rows, held):
    return {"open": len(rows), "forOwner": sum(1 for r in rows if r["who"] == OWNER), "holding": sum(1 for r in rows if r["group"] == 0),
            "claude": sum(1 for r in rows if r["who"] == "@claude"), "held": len(held)}


def thread_doc(rel, items):
    """One `depends:` entry as a link: its title, whether it is there, and for another thread its open-item count."""
    rel = norm(str(rel or "").strip())
    if not rel:
        return None
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    row = {"path": rel, "exists": os.path.isfile(ap), "title": os.path.basename(rel), "kind": "file", "href": inprog_href(rel)}
    if row["exists"] and rel.endswith(".md"):
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                fm, body = split_fm(f.read(6000))
            row["title"] = fm.get("subject") or fm.get("title") or next((l[2:].strip() for l in body if l.startswith("# ")), row["title"])
        except Exception:                                          # noqa: BLE001
            pass
    if row["exists"] and is_subject_rel(rel):
        sub = thread_subject(rel)
        o, h = thread_gather(sub, items)
        row.update(kind="thread", title=sub["name"], href="/thread?subject=" + urllib.parse.quote(rel), open=len(o))
    return row


def progress_key(s):
    """An in-progress project's id or name as a subject header may write it: case and runs of spaces do not count."""
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def inprog_ids():
    """{progress_key(id or name) -> id} for the projects in context/in-progress.json, read raw (no file is stat'ed).
    0.90.0 (brain-viewer T-0342): a subject's `progress:` may name its project by name as well as by id; the WFS
    onboarding thread wrote `progress: WFS onboarding problem` and drew two files instead of its twelve. An id wins over
    another project's name when the two read the same."""
    ap = os.path.join(BRAIN, INPROG_REL.replace("/", os.sep))
    data = _json_read(ap) if os.path.isfile(ap) else None
    projects = [p for p in (data or {}).get("projects") or [] if isinstance(p, dict) and p.get("id")]
    out = {}
    for p in projects:
        if p.get("name"):
            out.setdefault(progress_key(p["name"]), str(p["id"]))
    for p in projects:
        out[progress_key(p["id"])] = str(p["id"])
    return out


def thread_progress_id(sub, ids=None):
    """The in-progress project a subject binds: `progress:`, or a `project:` that names an in-progress project, each by
    its id or its name (0.90.0, T-0342), answered as the project's id. A value that names no in-progress project is
    answered as written, as before."""
    ids = inprog_ids() if ids is None else ids
    raws = [str(sub.get(k) or "").strip() for k in ("progress", "project")]
    for r in raws:
        if r and progress_key(r) in ids:
            return ids[progress_key(r)]
    return next((r for r in raws if r), "")


def _when(s):
    s = str(s or "").strip()
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.astimezone()


def thread_events():
    """The calendar's events as the threads read them: the week file's and today's, each with its people and preps."""
    evs = []
    try:
        evs += calendar_week_api().get("events") or []
    except Exception:                                              # noqa: BLE001
        pass
    try:
        evs += calls_api().get("events") or []
    except Exception:                                              # noqa: BLE001
        pass
    return evs


def thread_next_call(slugs, evs=None):
    """The next calendar event (the week file and today's) with any of these people on it, with its prep when one exists."""
    evs = thread_events() if evs is None else evs
    now = dt.datetime.now().astimezone()
    best, seen = None, set()
    for e in evs:
        k = (str(e.get("start") or ""), str(e.get("title") or ""))
        if k in seen:
            continue
        seen.add(k)
        on = [w for w in e.get("people") or [] if w.get("slug") in slugs]
        if not on:
            continue
        end, start = _when(e.get("end")), _when(e.get("start"))
        if (end or start) and (end or start) < now:
            continue
        if start is None:
            continue
        if best is None or start < best[0]:
            best = (start, e, on)
    if not best:
        return None
    start, e, on = best
    prep = (e.get("preps") or [None])[0]
    return {"title": e.get("title"), "start": e.get("start"), "end": e.get("end"), "date": str(e.get("start") or "")[:10],
            "people": [w.get("name") for w in on], "join": e.get("join"),
            "prep": ({"path": prep["path"], "href": "/call?prep=" + urllib.parse.quote(prep["path"]),
                      "reader": "/reader?path=" + urllib.parse.quote(prep["path"])} if prep else None)}


# ---- nesting, the workspace bands and the id rule (0.77.0, 2026-10-09, the workspaces direction W1) ----
# A subject file may carry `parent: <slug>`: the thread is then a piece of that thread. The page draws a breadcrumb up
# the chain and, on a parent, its pieces with their open counts; counts roll up (a parent's open count includes its
# pieces'), and an item both a piece and its parent take in belongs to the piece alone (the most specific thread wins,
# as subject_pass.py find does for transcripts). The bands the page draws from this one read: the thing in progress
# (`now:`), the drawn connections (`connects:` plus the parent and the pieces), what was built here and the documents by
# name, the done items for the Progress fold, and every ledger id the subject's prose names resolved to the item's
# words, so the page never shows a code (rule 1 of the owner's reading of the workspace proposal, 2026-10-09).
THREAD_ID_MENTION = re.compile(r"(?:`?\b([a-z][a-z0-9-]*)`?\s+)?\b([TQ]-\d{4})\b")    # a ledger word may sit in a code span
THREAD_DOC_EXT = (".md", ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".pdf", ".csv", ".json", ".txt", ".canvas")
THREAD_DONE_MAX = 80


def subject_short(name):
    """A subject's name without its trailing parenthesis: "The operations seat (the mentor's first hire)" reads "The
    operations seat" in a breadcrumb or a box; the page title keeps the whole name."""
    s = re.sub(r"\s*\([^()]*\)\s*$", "", str(name or "")).strip()
    return s or str(name or "")


def subject_index():
    """{slug: {rel, slug, name, short, parent, href}} for every subject file, read from each file's head."""
    out = {}
    for rel in thread_files():
        try:
            with open(os.path.join(BRAIN, rel.replace("/", os.sep)), "r", encoding="utf-8-sig") as f:
                fm, body = split_fm(f.read(6000))
        except Exception:                                          # noqa: BLE001
            continue
        slug = fm.get("slug") or os.path.basename(rel)[:-3]
        name = fm.get("subject") or next((l[2:].strip() for l in body if l.startswith("# ")), slug)
        out[slug] = {"rel": rel, "slug": slug, "name": name, "short": subject_short(name),
                     "parent": str(fm.get("parent") or "").strip().strip('"').strip("'"),
                     "href": "/thread?subject=" + urllib.parse.quote(rel)}
    return out


def subject_by_ref(ref, idx):
    """A `to:` / `parent:` / [[link]] target as a subject row: a slug, a subject file's path, or its leaf."""
    r = str(ref or "").strip().strip("[]").split("|")[0].split("#")[0].strip()
    if not r:
        return None
    if r in idx:
        return idx[r]
    p = norm(r if r.endswith(".md") else r + ".md") if "/" in r else ""
    for row in idx.values():
        if row["rel"] == p or (not p and os.path.basename(row["rel"])[:-3] == r.replace(".md", "")):
            return row
    return None


def doc_name(rel):
    """A file by what it is, never its leaf: a page's <title> or first <h1>; a document's title or first heading; else
    the leaf made readable with its date taken out."""
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    leaf = rel.rsplit("/", 1)[-1]
    name = ""
    if leaf.lower().endswith((".html", ".htm")) and os.path.isfile(ap):
        h = artifact_head(ap)
        name = h.get("title") or h.get("h1") or ""
        if not name and leaf.lower() in ARTIFACT_ENTRY and "/" in rel:
            name = artifact_readable(rel.rsplit("/", 2)[-2])
    elif leaf.lower().endswith(".md") and os.path.isfile(ap):
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                fm, body = split_fm(f.read(6000))
            name = fm.get("title") or fm.get("subject") or next((l[2:].strip() for l in body if l.startswith("# ")), "")
        except Exception:                                          # noqa: BLE001
            name = ""
        name = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), name)
        name = re.sub(r"[*_" + chr(96) + r"]+", "", name).strip()
        if leaf.lower() == "readme.md" and "/" in rel and (not name or name.lower() == "readme"):
            name = artifact_readable(rel.rsplit("/", 2)[-2])
    name = (name or artifact_readable(leaf)).replace(" — ", ", ").replace("—", ", ").strip()
    return name


def _thread_paths(raw):
    """A list of registered paths, a folder (one ending in "/", or one that is a folder) opened to its files."""
    out = []
    for x in raw:
        p = _link_path(x)
        if not p or p.startswith("/") or "://" in p:
            continue
        ap = os.path.join(BRAIN, p.rstrip("/").replace("/", os.sep))
        if os.path.isdir(ap):
            try:
                fs = sorted(n for n in os.listdir(ap) if n.lower().endswith(THREAD_DOC_EXT) and not n.startswith("."))
            except OSError:
                fs = []
            out.extend(p.rstrip("/") + "/" + n for n in fs)
        else:
            out.append(p)
    return out


def thread_file_href(p):
    """A page opens itself (a new tab, /raw/); anything else opens the way the Files page opens it (a document in the Reader)."""
    return ("/raw/" + p) if p.lower().endswith((".html", ".htm")) else inprog_href(p)


def thread_built_and_docs(sub, rows, held, done, bound_files):
    """Built here (the pages and sites, named and opened the way the Artifacts page does) and Documents (the rest, by a
    readable name, newest first), from the subject's depends and canonical lists, the bound in-progress files and every
    link on its open and held items (a done item's files are named on its row in Progress). A subject file, a people
    card, a ledger, a route, a transcript, an item's brief and the brain's own machinery are not files of the work."""
    raw = list(sub["depends"]) + list(sub["canonical"]) + [f.get("path") for f in bound_files or []]
    for r in rows + held:
        raw.extend(r.get("links") or [])
    seen, paths = set(), []
    for p in _thread_paths(raw):
        if (p in seen or p == sub["rel"] or is_subject_rel(p) or p.endswith("-tasks.md") or inprog_is_process(p)
                or p.startswith(("transcripts/", "deliverables/briefs/")) or "-holon/" in p and p.endswith("whats-new.md")):
            continue
        seen.add(p)
        paths.append(p)
    sites, docs = {}, []
    for p in paths:
        ap = os.path.join(BRAIN, p.replace("/", os.sep))
        exists = os.path.isfile(ap)
        try:
            mt = os.path.getmtime(ap) if exists else None
        except OSError:
            mt, exists = None, False
        if p.lower().endswith((".html", ".htm")) and exists:
            parts = p.split("/")
            home = "/".join(parts[:2]) if parts[0] == "deliverables" and len(parts) > 2 else p
            sites.setdefault(home, []).append((p, mt))
            continue
        docs.append({"name": doc_name(p), "path": p, "href": inprog_href(p), "exists": exists, "mtime": mt,
                     "at": dt.datetime.fromtimestamp(mt).isoformat(timespec="minutes") if mt else None})
    built = []
    for home, pages in sites.items():
        pages.sort(key=lambda x: x[1] or 0, reverse=True)
        entry = next((p for p, _ in pages if p.rsplit("/", 1)[-1].lower() in ARTIFACT_ENTRY), pages[0][0])
        folder = entry.rsplit("/", 1)[0] if "/" in entry else ""
        folder_ap = os.path.join(BRAIN, folder.replace("/", os.sep)) if folder else BRAIN
        rd, rhead, rpara = artifact_readme(folder_ap) if folder and folder != "deliverables" else (None, "", "")
        head = artifact_head(os.path.join(BRAIN, entry.replace("/", os.sep)))
        mt = max(m or 0 for _, m in pages)
        built.append({"name": doc_name(entry) or rhead, "path": entry, "line": rpara or head.get("desc") or "",
                      "open": "/raw/" + entry, "preview": "/preview?path=" + urllib.parse.quote(entry),
                      "about": ("/reader?path=" + urllib.parse.quote(folder + "/" + rd)) if rd else None,
                      "pages": len(pages), "mtime": mt, "at": dt.datetime.fromtimestamp(mt).isoformat(timespec="minutes") if mt else None})
    built.sort(key=lambda b: b["mtime"] or 0, reverse=True)
    docs.sort(key=lambda d: (d["exists"], d["mtime"] or 0), reverse=True)
    return built, docs


def thread_refs(texts, items, project):
    """Every ledger id the subject's prose names, resolved: {mention: {project, id, kind, words, closed, href} | {missing}}.
    A mention is "<ledger word> <id>" when the word names a registered ledger (pf-build, viewer, brain-central, in the
    registry's usual shapes), else the bare id, looked up on the subject's own project, else on the one ledger that has
    it. The page swaps each for a press carrying the item's first six words, or drops a missing one from the sentence."""
    holons = {h["id"] for h in registry().get("holons", []) if h.get("tasks")}
    byk = {(r["project"], r["id"]): r for r in items}

    def ledger_of(w):
        w = (w or "").lower()
        return next((p for p in (w, w + "-holon", "brain-" + w, "brain-" + w + "-holon", w + "-mirror") if p in holons), "")

    def resolve(pj, iid):
        r = byk.get((pj, iid)) if pj else None
        if r is None and not pj:
            r = byk.get((project, iid)) if project else None
            if r is None:
                hits = [x for (p, i), x in byk.items() if i == iid]
                r = hits[0] if len(hits) == 1 else None
        if r is None:
            return {"missing": True}
        words = re.sub(r"<!--.*?-->", "", r.get("text") or "")
        words = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or os.path.basename(m.group(1)), words)
        words = re.sub(r"[*_" + chr(96) + r"]+", "", words).split()
        face = " ".join(words[:6]).rstrip(",.;:")
        return {"project": r["project"], "id": r["id"], "kind": r["kind"], "words": face,
                "closed": r["mark"] in ("x", "a"), "href": "/thread?item=%s/%s" % (r["project"], r["id"])}
    out = {}
    for t in texts:
        for m in THREAD_ID_MENTION.finditer(str(t or "")):
            w, iid = m.group(1), m.group(2)
            pj = ledger_of(w) if w else ""
            k = ("%s %s" % (w, iid)) if pj else iid
            if k not in out:
                out[k] = resolve(pj, iid)
    return out


def thread_tree(rel, items, idx, cache, trail=()):
    """One subject gathered with its pieces: {sub, rows, held, done, kids, keys, open, forOwner}; the pieces' items are
    claimed from it (child wins), and open / forOwner roll the pieces up. A cycle in `parent:` stops at the first repeat."""
    if rel in cache:
        return cache[rel]
    sub = thread_subject(rel)
    kids, claimed = [], set()
    for row in idx.values():
        if row["parent"] and row["parent"] == sub["slug"] and row["rel"] != rel and row["rel"] not in trail:
            try:
                k = thread_tree(row["rel"], items, idx, cache, trail + (rel,))
            except Exception:                                      # noqa: BLE001
                continue
            kids.append(k)
            claimed |= k["keys"]
    done = []
    rows, held = thread_gather(sub, items, exclude=claimed, done=done)
    own = {(r["project"], r["id"]) for r in rows + held} | {(d["project"], d["id"]) for d in done}
    out = {"sub": sub, "rows": rows, "held": held, "done": done, "kids": kids, "keys": own | claimed,
           "open": len(rows) + sum(k["open"] for k in kids),
           "forOwner": sum(1 for r in rows if r["who"] == OWNER) + sum(k["forOwner"] for k in kids)}
    cache[rel] = out
    return out


def thread_connects(sub, idx, kids):
    """The drawn map: [{kind, name, title, href, line, thread, open?, missing?}]. The parent comes first as part-of and the
    pieces as piece, then the file's own `connects:` (naming the parent or a piece again adds its line to that box)."""
    out = []

    def put(kind, target, line):
        row = subject_by_ref(target, idx)
        if row:
            if row["rel"] == sub["rel"]:
                return
            hit = next((x for x in out if x.get("rel") == row["rel"]), None)
            if hit:
                hit["line"] = hit["line"] or line
                return
            out.append({"kind": kind, "name": row["short"], "title": row["name"], "href": row["href"], "rel": row["rel"],
                        "line": line, "thread": True})
            return
        p = _link_path(target)
        ap = os.path.join(BRAIN, p.replace("/", os.sep)) if p else ""
        if p and os.path.isfile(ap):
            out.append({"kind": kind, "name": doc_name(p), "title": doc_name(p), "href": thread_file_href(p), "rel": p, "line": line,
                        "thread": False, "page": p.lower().endswith((".html", ".htm"))})
        else:
            out.append({"kind": kind, "name": artifact_readable(os.path.basename(str(target))), "title": "", "href": None, "rel": "",
                        "line": line, "thread": False, "missing": True})
    if sub["parent"]:
        put("part-of", sub["parent"], "")
    for k in kids:
        put("piece", k["sub"]["rel"], "")
    for c in sub["connects"]:
        put(c["kind"], c["to"], c["line"])
    for k in kids:                                                 # a piece's open count, for its box
        hit = next((x for x in out if x.get("rel") == k["sub"]["rel"]), None)
        if hit:
            hit["open"] = k["open"]
    return out


def thread_ancestors(sub, idx):
    """The chain above a piece, outermost first: [{name, title, href, subject}]."""
    chain, seen, cur = [], {sub["slug"]}, sub["parent"]
    while cur and cur not in seen:
        seen.add(cur)
        row = subject_by_ref(cur, idx)
        if not row:
            break
        chain.insert(0, {"name": row["short"], "title": row["name"], "href": row["href"], "subject": row["rel"]})
        cur = row["parent"]
    return chain


def thread_api(rel):
    rel = norm(rel)
    if not rel or not is_subject_rel(rel):
        return 404, {"error": "no subject file at %r (a .md under projects/*/subjects/)" % rel}
    items = thread_ledgers()
    idx = subject_index()
    tree = thread_tree(rel, items, idx, {})
    sub, rows, held, done = tree["sub"], tree["rows"], tree["held"], tree["done"]
    people = [work_card(s) for s in sub["people"]]                  # 0.64.0: with role and Where it stands, for the People block
    files, bound = [], None
    pid = thread_progress_id(sub)
    if pid:
        ip = in_progress_api()
        hit = next((p for p in ip.get("projects") or [] if p.get("id") == pid), None)
        if hit:
            bound, files = {"id": hit["id"], "name": hit["name"], "note": hit.get("note") or ""}, hit.get("files") or []
    if not bound:
        files = [inprog_file(c) for c in sub["canonical"] if norm(c)]
    depends = [d for d in (thread_doc(x, items) for x in sub["depends"]) if d]
    route = subj_route_people(sub)
    nxt = thread_next_call(route)
    ledgers = sorted({r["label"] for r in rows + held})
    updated = sub["timeline"][0]["date"] if sub["timeline"] else (sub["updatedField"] or None)
    built, docs = thread_built_and_docs(sub, rows, held, done, files)
    now = None
    if sub["now"]:
        n = sub["now"]
        p = _link_path(n.get("path"))
        page = p.lower().endswith((".html", ".htm"))
        now = {"name": n.get("name") or (doc_name(p) if p else ""), "path": p, "line": n.get("line") or "", "next": n.get("next") or "",
               "page": page, "exists": bool(p) and os.path.isfile(os.path.join(BRAIN, p.replace("/", os.sep))),
               "open": thread_file_href(p) if p else None, "preview": ("/preview?path=" + urllib.parse.quote(p)) if page else None}
    connects = thread_connects(sub, idx, tree["kids"])
    ancestors = thread_ancestors(sub, idx)
    texts = [sub["stands"]] + [t["text"] for t in sub["timeline"]] + [c["line"] for c in connects]
    if now:
        texts += [now["line"], now["next"]]
    done = done[:THREAD_DONE_MAX]
    for d in done:
        d["files"] = [{"name": doc_name(p), "path": p, "href": thread_file_href(p), "page": p.lower().endswith((".html", ".htm"))}
                      for p in _thread_paths(d.get("links") or [])
                      if p != rel and not is_subject_rel(p) and os.path.isfile(os.path.join(BRAIN, p.replace("/", os.sep)))]
    texts += [d["text"] for d in done]
    kids = [{"subject": k["sub"]["rel"], "name": k["sub"]["name"], "short": subject_short(k["sub"]["name"]),
             "href": "/thread?subject=" + urllib.parse.quote(k["sub"]["rel"]), "open": k["open"], "forOwner": k["forOwner"],
             "stands": first_line(k["sub"]["stands"].split("\n"), 220), "status": k["sub"]["status"]} for k in tree["kids"]]
    texts += [k["stands"] for k in kids] + [p.get("stands") or "" for p in people] + [b["line"] for b in built]
    refs = thread_refs(texts, items, sub["project"])
    # an item's own words name ids on ITS ledger: those resolve there, keyed "<its ledger> <id>" (ids repeat across ledgers)
    for r in rows + held + done:
        for k, v in thread_refs([r.get("text") or "", r.get("note") or ""], items, r["project"]).items():
            refs.setdefault(k if " " in k else "%s %s" % (r["project"], k), v)
    links = {}
    for row in idx.values():
        links[row["slug"]] = links[row["rel"]] = {"name": row["short"], "href": row["href"]}
    counts = thread_counts(rows, held)
    rollup = {"open": tree["open"], "forOwner": tree["forOwner"], "inPieces": tree["open"] - len(rows)}
    return 200, {"subject": rel, "name": sub["name"], "short": subject_short(sub["name"]), "slug": sub["slug"], "status": sub["status"],
                 "people": people, "match": sub["match"], "ledgers": ledgers, "updated": updated,
                 "gather": sub["gather"] or "people and words",          # 0.90.0 (T-0343): "own" when the header limits it
                 "stands": {"head": sub["standsHead"], "text": sub["stands"], "reader": "/reader?path=" + urllib.parse.quote(rel)},
                 "items": rows, "held": held, "done": done, "counts": counts, "rollup": rollup, "depends": depends,
                 "files": files, "filesFrom": ("in progress: %s" % bound["name"]) if bound else "the subject file's canonical list",
                 "progress": bound, "nextCall": nxt, "nextCallPeople": [p["name"] for p in people if p["slug"] in route],
                 "team": sorted(set(sub["people"]) & thread_team()),
                 "timeline": sub["timeline"], "owner": OWNER,
                 "parent": ancestors[-1] if ancestors else None, "ancestors": ancestors, "children": kids,
                 "now": now, "connects": connects, "built": built, "documents": docs,
                 "refs": refs, "subjectLinks": links}


def thread_files():
    out, seen = [], set()
    for g in SUBJECTS_GLOBS:
        for ap in sorted(glob.glob(os.path.join(BRAIN, g.replace("/", os.sep)))):
            rel = os.path.relpath(ap, BRAIN).replace(os.sep, "/")
            if rel in seen or os.path.basename(rel) == "readme.md":
                continue
            seen.add(rel)
            out.append(rel)
    return out


def threads_api(person=None):
    """GET /api/threads: every subject file, one row each, newest dated line first. 0.77.0: each row names its parent
    (`parent`, the subject path), and `open` / `forOwner` roll its pieces up (`own` is the thread's own open count)."""
    items = thread_ledgers()
    evs = thread_events()                              # read once for every row's next call (0.62.1, the home widget)
    idx = subject_index()
    by_slug = {r["slug"]: r["rel"] for r in idx.values()}
    ids = inprog_ids()                                 # 0.90.0: read once for every row's progress (T-0342)
    cache, rows = {}, []
    for rel in thread_files():
        try:
            tree = thread_tree(rel, items, idx, cache)
        except Exception:                                          # noqa: BLE001
            continue
        sub = tree["sub"]
        if person and person not in sub["people"]:
            continue
        c = thread_counts(tree["rows"], tree["held"])
        rows.append({"subject": rel, "name": sub["name"], "status": sub["status"], "href": "/thread?subject=" + urllib.parse.quote(rel),
                     "people": [{"slug": s, "name": card_display_name(s)} for s in sub["people"]],
                     "forOwner": tree["forOwner"], "open": tree["open"], "own": c["open"], "held": c["held"],
                     "parent": by_slug.get(sub["parent"]) if sub["parent"] else None,
                     "last": sub["timeline"][0]["date"] if sub["timeline"] else (sub["updatedField"] or None),
                     "progress": thread_progress_id(sub, ids) or None,
                     "nextCall": thread_next_call(subj_route_people(sub), evs)})
    rows.sort(key=lambda r: (r["last"] or "", r["name"]), reverse=True)
    out = {"count": len(rows), "threads": rows}
    if not rows and not person:
        out["first"] = first_thread_suggestion()          # 0.69.0: what a fresh brain's first thread would be about
    return out


# ---- the first thread (0.69.0, the navigation direction rule 5) ----
# A brain set up from the pack has no subject files until the transcript intake writes one, so its threads page was empty
# with nothing to press. The page now offers the first thread, named from what the setup wrote into context/current-focus.md
# (its Priorities, else its Active threads), and POST /api/threads/new writes it: one subject file, exclusive create, logged.
FOCUS_REL = "context/current-focus.md"
NEW_THREAD_DIR = "projects/%s/subjects/%s.md"


def first_thread_suggestion():
    """{name, about, from} read from the first real bullet under ## Priorities (else ## Active threads) in the focus file,
    or {} when the file has none yet (a fresh shell writes `*(none yet)*` there)."""
    ap = os.path.join(BRAIN, FOCUS_REL.replace("/", os.sep))
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            body = f.read().replace("\r\n", "\n").split("\n")
    except OSError:
        return {}
    for head in ("Priorities", "Active threads"):
        for l in h2_section(body, head):
            t = l.strip()
            if not re.match(r"^([-*]|\d+[.)])\s+", t):
                continue
            t = re.sub(r"^([-*]|\d+[.)])\s+", "", t).strip()
            t = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", lambda m: (m.group(2) or "|" + m.group(1))[1:], t)
            plain = re.sub(r"[*_`]", "", t).strip()
            if not plain or plain.lower().startswith("(none"):
                continue
            name = re.split(r"\s+[-:\u2014\u2013]\s+|[.:;](\s|$)", plain, maxsplit=1)[0].strip()[:80] or plain[:80]
            return {"name": name, "about": plain[:400], "from": FOCUS_REL + " (" + head + ")"}
    return {}


def new_thread(name, about=""):
    """POST /api/threads/new {name, about?}: one subject file at projects/<slug>/subjects/<slug>.md, created exclusively, with
    the routing fields the thread page reads and a first Where it stands line. Returns (rel, error)."""
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:120]
    about = re.sub(r"\s+", " ", str(about or "")).strip()[:600]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60].strip("-")
    if not slug:
        return None, "a name is required: what the work is, in a few words"
    rel = NEW_THREAD_DIR % (slug, slug)
    day = ledger.today()
    text = ("---\nsubject: %s\nslug: %s\nthreads: []\npeople: []\nmatch: [%s]\ncanonical: []\nstatus: live\nopened: %s\nupdated: %s\n---\n\n"
            "# %s\n\n## Where it stands (%s)\n\n- %s\n\n## Open questions\n\n## Timeline\n\n- %s · thread started from the viewer\n"
            % (name.replace("\n", " "), slug, name.replace(",", " ").replace("]", " "), day, day, name, day,
               about or "Started today. Say what it is for, who it is with, and what comes next.", day))
    if PROPOSE:
        return propose("file", rel, {"content": text}, note="Threads: a new thread, %s" % name), None
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    try:
        with open(ap, "x", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except FileExistsError:
        return None, "a thread named %s already exists" % slug
    _subject_cache.pop(rel, None)
    log_line("%s -- Threads: new thread %s, started from the viewer" % (rel, name), action="CREATED")
    return rel, None


def threads_for_progress():
    """{in-progress id -> {subject, name, href}} for the subject files that bind one (the In progress widget's link)."""
    out = {}
    ids = inprog_ids()                                 # 0.90.0 (T-0342): a header naming the project by name binds it too
    for rel in thread_files():
        try:
            ap = os.path.join(BRAIN, rel.replace("/", os.sep))
            with open(ap, "r", encoding="utf-8-sig") as f:
                fm, body = split_fm(f.read(4000))
        except Exception:                                          # noqa: BLE001
            continue
        name = fm.get("subject") or os.path.basename(rel)[:-3]
        for raw in (str(fm.get("progress") or "").strip(), str(fm.get("project") or "").strip()):
            pid = ids.get(progress_key(raw), raw) if raw else ""
            if pid and pid not in out:
                out[pid] = {"subject": rel, "name": name, "href": "/thread?subject=" + urllib.parse.quote(rel)}
    return out


# ---- the Workspace (0.63.0, 2026-10-05): one page per ledger item, everything needed to answer or do it ----
# GET /api/work?item=<holon id>/<item id> joins, at read time, the item as its ledger holds it, what it holds up and
# waits on, the thread it belongs to (a subject file it links, else the first thread that gathers it), its files, its
# people, the thread's other open items, the next call, its history and its brief. skills/item-brief/brief.py imports
# work_bundle() so the brief is built from exactly what the page shows. Stored nowhere; the only writes on the page are
# the ledger presses (tasks.py) and the brief run (POST /api/brief/run starts brief.py, which writes its own files).
BRIEF_REL = "deliverables/briefs"
BRIEF_STATE_REL = USER_REL + "/brief"
BRIEF_SCRIPT = os.path.join(CODE, "skills", "item-brief", "brief.py")
WORK_LOG_FOLD = 5


def brief_rel(hid, iid):
    return "%s/%s-%s-brief.md" % (BRIEF_REL, hid, iid)


def work_ref(ref):
    """'pf-build/Q-0041' (or 'pf-build Q-0041') -> (holon, item id) when the holon has a registered ledger, else (None, None)."""
    m = re.match(r"^\s*([a-z0-9][a-z0-9-]*)[/\s]+([TQ]-\d{4})\s*$", str(ref or ""))
    if not m:
        return None, None
    h = next((x for x in registry().get("holons", []) if x.get("id") == m.group(1) and x.get("tasks")), None)
    return (h, m.group(2)) if h else (None, None)


def work_link_row(link, how):
    """One link of an item as a file row: a brain file (its title, its folder, the link that opens it; a picture flagged
    for the lightbox; a folder listed), or a route / address kept as it is."""
    raw = str(link or "").strip()
    wl = re.match(r"^\[\[(.+?)\]\]$", raw)
    target = (wl.group(1).split("|")[0] if wl else raw).strip()
    path, _, frag = target.partition("#")
    if not path or path.startswith(("/", "http://", "https://")):
        return {"kind": "route", "path": target, "title": target, "href": target, "how": how, "exists": True}
    rel = norm(path)
    if not rel:
        return None
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    if os.path.isdir(ap):
        kids = []
        try:
            for fn in sorted(os.listdir(ap)):
                if fn.startswith(".") or files_hidden(fn):
                    continue
                if os.path.isfile(os.path.join(ap, fn)):
                    kids.append(inprog_file(rel.rstrip("/") + "/" + fn))
        except OSError:
            pass
        kids.sort(key=lambda r: r["mtime"] or 0, reverse=True)
        return {"kind": "folder", "path": rel, "title": rel.rstrip("/").rsplit("/", 1)[-1] + "/", "folder": rel.rsplit("/", 1)[0] if "/" in rel else "",
                "exists": True, "files": kids[:40], "how": how, "href": "/files?q=" + urllib.parse.quote(rel)}
    row = inprog_file(rel, {"how": how})
    row["kind"] = "image" if os.path.splitext(rel)[1].lower() in IMAGE_EXT else "file"
    row["title"] = row["name"]
    if frag:
        row["href"] += "#" + frag
    if row["exists"] and rel.endswith(".md"):
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                fm, body = split_fm(f.read(6000))
            row["title"] = fm.get("subject") or fm.get("title") or next((l[2:].strip() for l in body if l.startswith("# ")), row["name"])
        except Exception:                                          # noqa: BLE001
            pass
    if row["kind"] == "image":
        row["img"] = "/api/image?path=" + urllib.parse.quote(rel)
    return row


# ---- the pick question type (0.79.0, 2026-10-14) ----
# The owner, on the workspace of a question that asked which of three design directions to follow: the page showed the
# presses and a link to the directions' index, never the three beside each other, so there was nothing to decide from.
# So a question tagged `pick` carries a link per option (`options:Folio=deliverables/x/direction-1.html | ... | none of
# these`, parsed by the ledger tool's option_parts, one parser for both) and GET /api/work carries
# pick {options: [{name, link, kind, preview, exists, sections}], chosen}: kind from the extension (html, image,
# md, other), preview the same-origin URL this server already serves the file at (/raw/ for a page or a picture, the
# Reader for markdown, the Files page's route for anything else), and for a page its top-level <section>s that carry an
# id, or name one through aria-labelledby, so the column can move its frame to each screen. A plain option has no link
# and no preview. The workspace (workspace.js pickBlock) draws it as the item's first band; Today, the thread page and
# the workspace list draw one lead press, Compare (BV.pick in viewer-common.js). A pick needs two linked options; with
# fewer the item is an ordinary question and no block is sent.
PICK_SECTIONS_MAX = 12
PICK_READ_MAX = 2_000_000          # bytes of a page read for its sections


from html.parser import HTMLParser as _HTMLParser   # noqa: E402  -- the pick's section reader, nothing else


class _PickSections(_HTMLParser):
    """The top-level <section>s of a page that can be scrolled to, in page order: each one's anchor (its own id, else
    the id its aria-labelledby names, else the id of its first heading) and its name (its aria-label, else the text of
    the heading it is labelled by, else its first heading's text). A section with no id to scroll to is left out."""
    HEAD = re.compile(r"^h[1-6]$")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth, self.cur, self.found, self.texts, self.grab = 0, None, [], {}, None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "").strip() for k, v in attrs}
        if tag == "section":
            if self.depth == 0:
                self.cur = {"id": a.get("id", ""), "by": (a.get("aria-labelledby", "").split() or [""])[0],
                            "label": a.get("aria-label", ""), "head": None, "headText": ""}
            self.depth += 1
        elif self.cur is not None and self.grab is None and self.HEAD.match(tag):
            self.grab = [tag, a.get("id", ""), [], self.cur["head"] is None]
            if self.cur["head"] is None:
                self.cur["head"] = a.get("id", "")

    def handle_data(self, data):
        if self.grab is not None:
            self.grab[2].append(data)

    def handle_endtag(self, tag):
        if self.grab is not None and self.grab[0] == tag:
            _t, gid, words, first = self.grab
            text = " ".join("".join(words).split())
            if gid:
                self.texts.setdefault(gid, text)
            if first and self.cur is not None:
                self.cur["headText"] = text
            self.grab = None
        if tag == "section" and self.depth:
            self.depth -= 1
            if self.depth == 0 and self.cur is not None:
                self.found.append(self.cur)
                self.cur = None

    def sections(self):
        out = []
        for s in self.found:
            anchor = s["id"] or s["by"] or s["head"] or ""
            if not anchor:
                continue
            name = s["label"] or self.texts.get(s["by"]) or s["headText"] or anchor
            out.append({"id": anchor, "name": name[:80]})
        return out[:PICK_SECTIONS_MAX]


def pick_sections(ap):
    """The screens of a linked page: its top-level sections with an id to scroll to, or [] (no switch is drawn)."""
    try:
        with open(ap, "r", encoding="utf-8-sig", errors="replace") as f:
            text = f.read(PICK_READ_MAX)
        p = _PickSections()
        p.feed(text)
        p.close()
        return p.sections()
    except Exception:                                              # noqa: BLE001
        return []


def pick_kind(rel):
    ext = os.path.splitext(rel)[1].lower()
    return "html" if ext in (".html", ".htm") else "image" if ext in IMAGE_EXT else "md" if ext == ".md" else "other"


def pick_block(it):
    """The pick block of GET /api/work for an item tagged pick with two or more linked options, else None."""
    if it.get("kind") != "question" or not ledger.is_pick(it.get("tags")):
        return None
    opts = []
    for raw in str(it.get("options") or "").split("|"):
        if not raw.strip():
            continue
        name, link = ledger.option_parts(raw)
        row = {"name": name, "link": None, "kind": None, "preview": None}
        if link:
            path_, _, frag = link.partition("#")
            rel = norm(path_) or ""
            if not rel:
                opts.append(row)       # a link that does not stay inside the brain is shown as a plain option
                continue
            kind = pick_kind(rel)
            q = urllib.parse.quote(rel)
            preview = ("/raw/" + q) if kind in ("html", "image") else ("/reader?path=" + q) if kind == "md" else inprog_href(rel)
            ap = files_abs(rel)
            exists = bool(ap and os.path.isfile(ap))
            row.update(link=rel, kind=kind, preview=preview + (("#" + frag) if frag and kind != "image" else ""), exists=exists,
                       sections=pick_sections(ap) if exists and kind == "html" else [])
        opts.append(row)
    if sum(1 for o in opts if o["link"]) < 2:
        return None
    ans = str(it.get("answer") or "").strip().lower()
    chosen = next((o["name"] for o in opts if ans and o["name"].lower() == ans), None) if it.get("mark") == "a" else None
    return {"options": opts, "chosen": chosen}


def work_thread(it, items):
    """The thread an item belongs to: a subject file it links, else the first live thread whose gathering takes it in."""
    linked = []
    for l in it.get("links") or []:
        p = norm(str(l).strip().strip("[]").split("|")[0].split("#")[0])
        if p and is_subject_rel(p):
            linked.append(p)
    # 0.77.0: a piece of a thread is tried before the threads above it, so the most specific thread takes the item
    depth = {}
    try:
        idx = subject_index()
        for row in idx.values():
            n, cur, seen = 0, row["parent"], set()
            while cur and cur not in seen and cur in idx:
                seen.add(cur)
                n, cur = n + 1, idx[cur]["parent"]
            depth[row["rel"]] = n
    except Exception:                                              # noqa: BLE001
        pass
    rest = sorted((r for r in thread_files() if r not in linked), key=lambda r: -depth.get(r, 0))
    cands = linked + rest
    key = (it["project"], it["id"])
    for rel in cands:
        try:
            sub = thread_subject(rel)
        except Exception:                                          # noqa: BLE001
            continue
        rows, held = thread_gather(sub, items)
        if rel in linked or any((r["project"], r["id"]) == key for r in rows + held):
            return sub, rows, held
    return None, [], []


def work_card(slug):
    rel, ap = card_path(slug)
    if not ap:
        return {"slug": slug, "name": slug.replace("-", " ").title(), "exists": False, "href": "/people?open=" + urllib.parse.quote(slug)}
    c = parse_card(rel, ap)
    st = c.get("stands") or {}
    return {"slug": slug, "name": card_display_name(slug), "exists": True, "path": rel, "role": c.get("role") or "",
            "stands": st.get("text") or "", "standsDate": st.get("date"), "stale": c.get("stale"),
            "href": "/people?open=" + urllib.parse.quote(slug)}


def work_redirect(ref):
    """GET /work's decision (0.64.0): the thread page focused on the item when the item belongs to a thread (the same
    resolution the Workspace uses), else None and the bare page is served."""
    h, iid = work_ref(ref)
    if not h:
        return None
    items = thread_ledgers()
    it = next((r for r in items if r["project"] == h["id"] and r["id"] == iid), None)
    if it is None:
        return None
    sub, rows, held = work_thread(it, items)
    if not sub:
        return None
    return "/thread?subject=%s&item=%s" % (urllib.parse.quote(sub["rel"]), urllib.parse.quote("%s/%s" % (h["id"], iid), safe="/"))


def work_bundle(ref, scope="all"):
    """Everything the Workspace shows for one item -> (code, body). scope "item" (0.64.0, the Thread page's focused
    item) leaves out what the thread page already draws: the thread's people, its other items, its depends and its
    in-progress files, and the next call."""
    h, iid = work_ref(ref)
    if not h:
        return 404, {"error": "no item %r: give it as <ledger id>/<item id>, like <project>/Q- and four digits" % ref}
    items = thread_ledgers()
    it = next((r for r in items if r["project"] == h["id"] and r["id"] == iid), None)
    if it is None:
        return 404, {"error": "%s is not on the %s ledger" % (iid, h["id"])}
    key = lambda r: "%s/%s" % (r["project"], r["id"])
    byid = {(r["project"], r["id"]): r for r in items}
    words = lambda r: {"id": r["id"], "project": r["project"], "text": r.get("text") or "", "state": r.get("state"),
                       "who": (r.get("to") or OWNER) if r["kind"] == "question" else r.get("owner"), "href": "/work?item=" + key(r)}
    holds_up = [words(r) for r in items if r["project"] == it["project"] and r["kind"] == "task" and r["mark"] in " -"
                and it["id"] in THREAD_REFS.findall(str(r.get("blocked") or ""))]
    waits_on = [words(byid[(it["project"], b)]) for b in THREAD_REFS.findall(str(it.get("blocked") or "")) if (it["project"], b) in byid]
    sub, rows, held = work_thread(it, items) if scope != "item" else (None, [], [])
    thread = None
    if sub:
        thread = {"subject": sub["rel"], "name": sub["name"], "href": "/thread?subject=" + urllib.parse.quote(sub["rel"]),
                  "standsHead": sub["standsHead"], "stands": sub["stands"], "timeline": sub["timeline"],
                  "match": sub["match"], "people": sub["people"]}
    # the files: the item's own links, then what the thread depends on, then the in-progress project's, newest first
    files, seen = [], set()
    def add(row):
        if row and row.get("path") not in seen:
            seen.add(row.get("path"))
            files.append(row)
    for l in it.get("links") or []:
        add(work_link_row(l, "on the item"))
    if sub:
        for d in sub["depends"]:
            r = thread_doc(d, items)
            if r:
                r.update(how="the thread depends on it", name=os.path.basename(r["path"]), folder=r["path"].rsplit("/", 1)[0] if "/" in r["path"] else "")
                if r["exists"]:
                    try:
                        mt = os.path.getmtime(os.path.join(BRAIN, r["path"].replace("/", os.sep)))
                        r.update(mtime=mt, at=dt.datetime.fromtimestamp(mt).isoformat(timespec="minutes"))
                    except OSError:
                        pass
                add(r)
        pid = thread_progress_id(sub)
        if pid:
            hit = next((p for p in (in_progress_api().get("projects") or []) if p.get("id") == pid), None)
            for f in (hit or {}).get("files") or []:
                add(dict(f, how="in progress", kind="file", title=f["name"]))
    # the people: the item's, then the thread's
    slugs = []
    for s in list(it.get("people") or []) + list((sub or {}).get("people") or []):
        if s not in slugs:
            slugs.append(s)
    people = [work_card(s) for s in slugs]
    siblings = [r for r in rows if (r["project"], r["id"]) != (it["project"], it["id"])]
    nxt = thread_next_call(thread_route_people(slugs)) if slugs and scope != "item" else None
    # history: the note's lines split where the tools join them, newest first; the answer; the log lines naming it
    notes = [x.strip() for x in str(it.get("note") or "").split(" | ") if x.strip()]
    rx = re.compile(r"(?<![\w-])%s(?!\d)" % re.escape(iid))
    logs = []
    for line in log_lines(since=it.get("created") or None):
        m = FILES_LOG_RE.match(line)
        if m and rx.search(m.group(4)) and (h["tasks"] in m.group(4) or re.search(r"\b%s\b" % re.escape(h["id"]), m.group(4))):
            logs.append({"at": m.group(1), "agent": m.group(2), "action": m.group(3), "text": m.group(4)})
    logs.reverse()
    brel = brief_rel(h["id"], iid)
    bap = os.path.join(BRAIN, brel.replace("/", os.sep))
    brief = {"path": brel, "exists": os.path.isfile(bap), "reader": "/reader?path=" + urllib.parse.quote(brel)}
    if brief["exists"]:
        with open(bap, "r", encoding="utf-8-sig") as f:
            text = f.read()
        lines = text.replace("\r\n", "\n").split("\n")
        head = [l for l in lines[:4] if l.startswith(">")]
        body = "\n".join(l for l in lines if not (l.startswith(">") and lines.index(l) < 4)).strip()
        m = re.search(r"written (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", " ".join(head))
        brief.update(text=body, header=head, writtenAt=m.group(1) if m else dt.datetime.fromtimestamp(os.path.getmtime(bap)).strftime("%Y-%m-%d %H:%M"))
    item = dict(it)
    item.update(who=(it.get("to") or OWNER) if it["kind"] == "question" else it.get("owner"), holdsUp=holds_up, waitsOn=waits_on,
                href="/work?item=" + key(it), projectHref="/projects?id=%s#%s-%s-%s" % (urllib.parse.quote(h["id"]), "q" if it["kind"] == "question" else "t", h["id"], iid))
    return 200, {"ref": key(it), "item": item, "pick": pick_block(it), "thread": thread, "brief": brief, "files": files, "people": people,
                 "siblings": siblings, "siblingsHeld": [r for r in held if (r["project"], r["id"]) != (it["project"], it["id"])],
                 "nextCall": nxt, "nextCallPeople": [p["name"] for p in people if p["slug"] in thread_route_people(slugs)],
                 "history": {"notes": list(reversed(notes)), "answer": it.get("answer"), "answered": it.get("answered"),
                             "log": logs, "fold": WORK_LOG_FOLD},
                 "counts": {"files": len(files), "people": len(people), "siblings": len(siblings),
                            "history": len(notes) + (1 if it.get("answer") else 0) + len(logs)},
                 "owner": OWNER, "briefInstalled": os.path.isfile(BRIEF_SCRIPT), "scope": scope}


# ---- the brief run, started from the Workspace (0.63.0) ----
_brief_procs = {}
_brief_lock = threading.Lock()


def brief_status_path():
    return os.path.join(BRAIN, BRIEF_STATE_REL.replace("/", os.sep), "status.json")


def brief_status(ref):
    """GET /api/brief/status?item=: that item's entry in viewer/brief/status.json, laid over with what this server
    started, plus the last lines of its run log."""
    h, iid = work_ref(ref)
    if not h:
        return 404, {"error": "no item %r" % ref}
    k = "%s/%s" % (h["id"], iid)
    if not os.path.isfile(BRIEF_SCRIPT):
        return 200, {"item": k, "state": "missing", "error": "the brief is not installed yet: skills/item-brief/brief.py is not in this copy"}
    st = dict((_json_read(brief_status_path()) or {}).get(k) or {"state": "idle"})
    proc = _brief_procs.get(k)
    if proc is not None:
        rc = proc.poll()
        ours = str(st.get("pid") or "") == str(proc.pid)
        if rc is None and st.get("state") != "running":
            st.update(state="running", pid=proc.pid)
        elif rc is not None and (st.get("state") in ("running", "idle") and (ours or not st.get("pid"))):
            st.update(state="refused" if rc == 2 else "failed", error=st.get("error") or "the brief stopped before it said how it ended (exit %d)" % rc)
    elif st.get("state") == "running" and st.get("pid") and not _pid_alive(st.get("pid")):
        st.update(state="failed", error="the last brief stopped without finishing: its process is gone")
    st["item"] = k
    st["log"] = _tail(os.path.join(BRAIN, BRIEF_STATE_REL.replace("/", os.sep), "%s-%s-run.log" % (h["id"], iid)))
    return 200, st


def brief_run(ref, presses=None):
    """POST /api/brief/run {item, presses?}: brief.py started detached for that item, one run per item at a time."""
    if PROPOSE:
        return 403, {"ok": False, "error": "a team copy does not run the owner's briefs"}
    h, iid = work_ref(ref)
    if not h:
        return 404, {"ok": False, "error": "no item %r" % ref}
    if not os.path.isfile(BRIEF_SCRIPT):
        return 501, {"ok": False, "state": "missing", "error": "the brief is not installed yet: skills/item-brief/brief.py is not in this copy"}
    k = "%s/%s" % (h["id"], iid)
    with _brief_lock:
        code, st = brief_status(k)
        if st.get("state") == "running":
            return 409, {"ok": False, "error": "a brief for this item is already being written"}
        d = os.path.join(BRAIN, BRIEF_STATE_REL.replace("/", os.sep))
        os.makedirs(d, exist_ok=True)
        args = [sys.executable, "-u", BRIEF_SCRIPT, h["id"], iid]
        ps = [" ".join(str(p).split())[:60] for p in (presses or []) if str(p).strip()][:8]
        if ps:
            args += ["--presses", " | ".join(ps)]
        kw = {"creationflags": 0x00000200 | 0x08000000} if os.name == "nt" else {"start_new_session": True}
        try:
            with open(os.path.join(d, "%s-%s-run.log" % (h["id"], iid)), "w", encoding="utf-8") as logf:
                proc = subprocess.Popen(args, cwd=BRAIN, stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.STDOUT,
                                        env=dict(os.environ, BRAIN_ROOT=BRAIN, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8"),
                                        close_fds=True, **kw)
        except Exception as e:                                     # noqa: BLE001
            return 500, {"ok": False, "error": "the brief could not start: %s" % e}
        _brief_procs[k] = proc
    return 200, {"ok": True, "item": k, "pid": proc.pid, "startedAt": dt.datetime.now().isoformat(timespec="seconds")}


def threads_for_person(slug):
    """The subject files whose `people:` name this person, for the People page's threads line (names only, no counting)."""
    out = []
    for rel in thread_files():
        try:
            with open(os.path.join(BRAIN, rel.replace("/", os.sep)), "r", encoding="utf-8-sig") as f:
                fm, body = split_fm(f.read(4000))
        except Exception:                                          # noqa: BLE001
            continue
        if slug in fm_list(fm, "people"):
            out.append({"subject": rel, "name": fm.get("subject") or os.path.basename(rel)[:-3],
                        "status": str(fm.get("status") or "").lower(), "href": "/thread?subject=" + urllib.parse.quote(rel)})
    return out


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
# ---- the glossary (2026-09-09, the straight line step 2, ledger T-0040; 0.85.0, 2026-10-16: read from help.json) ----
# ONE source, read at request time so a save shows up on the next reload and there is no second copy to go stale. Until
# 0.85.0 it was a markdown seed in the viewer's holon (brain-viewer-holon/brain-viewer-glossary.md, now a tombstone),
# which did not travel with the code and had drifted from the viewer on where an item is acted on and what the "?"
# button opens. It is now the `glossary` key of help.json, beside the entry each page shows behind its "?" button:
#   {"groups": [{"name", "pages" (the pages whose "?" panel opens this group), "note", "hover" (false for a group of
#    reference entries, never auto-underlined), "terms": [{"term", "aliases", "definition", "example", "analog"}]}],
#    "keys": [{"key", "pages", "what"}], "keys_note"}
# The anchor, the hover decision (HOVER_OFF below) and the prose needles are computed here, as before.
GLOSSARY_REL = "skills/brain-viewer/help.json"
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
              "back", "stale", "blocking", "stage", "binding", "symbols",
              # 0.67.0: the six words added for the rooms; everyday words except budding, which is the owner's own coinage
              "thread", "workspace", "brief", "studio", "preview"}
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


WHATS_NEW_REL = "WHATS-NEW.md"     # 0.82.0: at a team copy's root, written by skills/team-brain/export.py, newest export first


def mode_info():
    """0.82.0: exported_at is re-read from team-brain.json on every call, so the copy's date at the top of each page is the
    export the copy holds now (a pull while the viewer runs brings a new stamp), and whats_new says whether the copy has
    its what's-new page for the strip to link."""
    if not PROPOSE:
        return {"mode": "normal"}
    team = load_team() or TEAM
    return {"mode": "propose", "member": MEMBER, "tier": team.get("tier"), "exported_at": team.get("exported_at"),
            "source_commit": team.get("source_commit"), "viewer_mode": team.get("viewer_mode"), "files": team.get("files"),
            "schema": team.get("schema"), "requests": REQUESTS_REL + "/" + MEMBER + "/",
            "from": team.get("from") or None,     # 0.88.0: whose brain the copy is from, the From band's name (team-brain.json)
            "whats_new": WHATS_NEW_REL if os.path.isfile(os.path.join(BRAIN, WHATS_NEW_REL)) else None}


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


load_part('part_live.py')   # 0.68.0: the Forge's files, the canvases, the live maps and part state, in its own file


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
    """The `glossary` key of help.json as groups + a flat term list + the keys, with the anchor, the hover decision and
    the prose needles computed here (0.85.0; until then the markdown seed parsed the same way). No cache: the file is
    small and the point is that a save is live on the next reload. The help file ships with the code, so a team copy
    has the words too; the brain's own copy is read first, the code's when the brain has none."""
    out = {"file": GLOSSARY_REL, "available": False, "groups": [], "terms": [], "keys": [], "marker": GL_MARKER,
           "note": "The glossary lives in the viewer's help file (skills/brain-viewer/help.json), which this copy does not carry.",
           "_servedAt": dt.datetime.now().isoformat(timespec="seconds")}
    ap = next((p for p in (os.path.join(root, GLOSSARY_REL.replace("/", os.sep)) for root in (BRAIN, CODE)) if os.path.isfile(p)), None)
    if not ap:
        return out
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            gl = (json.load(f) or {}).get("glossary") or {}
    except Exception as e:                       # noqa: BLE001 -- a broken help file is reported, never a 500 on every page
        out["note"] = "The help file could not be read: %s" % e
        return out
    if not gl.get("groups"):
        return out
    out["available"] = True
    out["note"] = ""
    out["mtime"] = dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")
    out["keysNote"] = str(gl.get("keys_note") or "")
    for g0 in gl.get("groups") or []:
        name = str(g0.get("name") or "").strip()
        if not name:
            continue
        g = {"name": name, "anchor": gl_slug(name), "pages": [str(p).strip().lower() for p in g0.get("pages") or [] if str(p).strip()],
             "note": str(g0.get("note") or "").strip(), "hover": bool(g0.get("hover", True)), "terms": []}
        for t0 in g0.get("terms") or []:
            head = str(t0.get("term") or "").strip()
            if not head:
                continue
            aliases = [str(a).strip() for a in t0.get("aliases") or [] if str(a).strip()]
            hover = g["hover"] and head.lower() not in HOVER_OFF
            term = {"term": head, "aliases": aliases, "definition": str(t0.get("definition") or "").strip(),
                    "example": str(t0.get("example") or "").strip(), "analog": str(t0.get("analog") or "").strip(),
                    "group": name, "anchor": gl_slug(head),
                    "hover": hover,
                    # the aliases that may be auto-underlined; every alias still resolves through the {{...}} marker
                    "needles": ([a for a in aliases if gl_alias_needle(a)]) if hover else []}
            g["terms"].append(term)
            out["terms"].append(term)
        if g["terms"]:
            out["groups"].append(g)
    out["keys"] = [{"key": str(k.get("key") or "").strip(), "pages": [str(p).strip().lower() for p in k.get("pages") or [] if str(p).strip()],
                    "what": str(k.get("what") or "").strip()} for k in gl.get("keys") or [] if str(k.get("key") or "").strip()]
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


_PROJECTS_CACHE = {"key": None, "body": None}


def projects_api():
    """Every ledger the registry names, parsed by the tasks tool; counts are derived at read time, never stored.
    0.68.0 (the review's finding 8): five pages and seven widgets read this, so the answer is cached by what it is made
    of, the registry's and every ledger's modification time and size, the day, and the brain; a change to any of them
    parses again. Only _servedAt is new on a cached answer."""
    reg = registry()
    sig = [BRAIN, ledger.today()]
    for p in [REGISTRY_REL] + [h["tasks"] for h in reg.get("holons", []) if h.get("tasks")]:
        try:
            st = os.stat(os.path.join(BRAIN, p.replace("/", os.sep)))
            sig.append((p, st.st_mtime_ns, st.st_size))
        except OSError:
            sig.append((p, None, None))
    sig = tuple(sig)
    if _PROJECTS_CACHE["key"] == sig and _PROJECTS_CACHE["body"] is not None:
        return dict(_PROJECTS_CACHE["body"], _servedAt=dt.datetime.now().isoformat(timespec="seconds"))
    body = projects_build(reg)
    _PROJECTS_CACHE["key"], _PROJECTS_CACHE["body"] = sig, body
    return dict(body)


def projects_build(reg):
    out = []
    for h in reg.get("holons", []):
        if not h.get("tasks"):
            continue
        rel = h["tasks"]; ap = os.path.join(BRAIN, rel.replace("/", os.sep))
        e = {"id": h["id"], "name": h.get("name"), "short": ledger_label(h), "description": h.get("description"), "path": rel, "holonPath": h.get("path"), "exists": os.path.isfile(ap)}
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
            rows.append({"id": it["id"], "project": h["id"], "projectName": ledger_label(h), "file": rel,
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
# which is the point. The defect this replaces: one card's Status section stopped on 2026-06-23 while three later folds moved
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
                row.update(purpose=clip(fm.get("purpose", ""), 1000),   # 0.75.0 (T-0325): Today draws the purpose in full, wrapped; 140 cut it mid-sentence
                           status=fm.get("status", ""), person=fm.get("person", m.group("slug")),
                           group=fm.get("group", ""),
                           participants=[p.strip() for p in re.sub(r"^\[|\]$", "", fm.get("participants", "")).split(",") if p.strip()])
                # 0.52.1 (2026-09-29): the frontmatter `call:` date wins over the filename's. The team call moved from
                # Monday to Tuesday, its prep kept Monday's filename, and the call page linked an empty skeleton instead.
                fc = str(fm.get("call", "")).strip()[:10]
                if re.match(r"^\d{4}-\d{2}-\d{2}$", fc):
                    row["call"] = fc
            except Exception as e:
                row["error"] = "%s: %s" % (type(e).__name__, e)
            # 2026-09-21: a prep belongs to EVERY participant, not only to its file key. A four-way call, keyed
            # by its three other participants' slugs joined, was reachable from nobody's row (the owner could not find it from the guest's row).
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
               heldItems=[r for r in held_for_zak() if row["slug"] in r["people"]],      # on hold, behind their own fold (T-0108)
               threads=threads_for_person(row["slug"]))                                     # 0.62.0: the subject files naming them
    return row, None


load_part('part_circle.py')   # 0.73.0: the extended circle under each holder's card, and its three edits


# ---- routing: an item carries the people it concerns (2026-09-09, ideas E16) ----
# The owner's requirement, 9/09: questions must reach the specific areas they belong to.
# The ledger field `people:<slug>,<slug>` (skills/brain-tasks/tasks.py) is the routing, and it is DECLARED, not guessed:
# rules 1. The name matching below is only a fallback so an item nobody has tagged still reaches the person it names --
# conservative in the same way the group matcher is (Correction #73): a full name anywhere, or a first name that belongs
# to exactly one card and is not followed by a surname. An ambiguous first name ("Sam" with two Sams) matches nothing; tagging
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
            # 0.87.1: in a team copy a question waits on the member only when it is addressed to her; a question to the
            # brain's owner travels in the copy but is not hers, so it is not counted or listed as waiting on her
            waiting = (it["kind"] == "question" and it["mark"] == "?" and (not PROPOSE or it.get("to") == OWNER)) or \
                      (it["kind"] == "task" and it["owner"] == OWNER and it["mark"] in " -")
            if not waiting or is_try_item(it):
                continue
            who, how = item_people(it)
            r = dict(it); r.pop("line", None)
            r["held"] = ledger.is_held(it)
            r.update(project=h["id"], projectName=ledger_label(h), projectPath=h["tasks"], people=who, peopleSource=how)
            rows.append(r)
    rows.sort(key=lambda r: (r["kind"] != "question", r["created"]))
    _open_cache.update(sig=sig, rows=rows)
    return rows if include_held else [r for r in rows if not r["held"]]


def is_try_item(it):
    """A click-through test in the owner's name (`#test`, or `#test-<version>`): the "to try" batch (0.65.0, 2026-10-06,
    Round 1 of the viewer review). The rule that filed one for every closed build step is retired (skills/brain-tasks/
    readme.md: a closed step records how to try it on the what's-new page instead), and the ones it left open are neither
    closed nor deleted: they are held out of everything that counts or lists the owner's open work -- this function's
    callers, so Today's queue, the nav counts, the home widgets and the people pages at once -- and shown under one
    "To try" heading on the rating page (review_api's `toTry`)."""
    if it.get("kind") != "task" or it.get("owner") != OWNER:
        return False
    return any(t == QUEST_TAG or str(t).startswith(QUEST_TAG + "-") for t in (it.get("tags") or []))


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
                r.update(project=h["id"], projectName=ledger_label(h), fragment=frag.strip(), link=t)
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
            groups[h["id"]] = {"project": h["id"], "name": ledger_label(h), "path": h["tasks"],
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
            row.update(project=h["id"], projectName=ledger_label(h), projectPath=h["tasks"])
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
            row.update({"cardId": cid, "project": h["id"], "projectName": ledger_label(h), "file": rel,
                        "id": it["id"], "itemKind": it["kind"], "text": it["text"], "note": face, "history": hist,
                        "owner": it.get("owner"), "to": it.get("to"), "links": it.get("links") or [],
                        "tags": [t for t in tags if not t.startswith((FINDING_SOURCE_TAG, FINDING_KEY_TAG))],
                        "source": it.get("source") or _tag_value(it, FINDING_SOURCE_TAG) or REVIEW_SOURCE,
                        "date": it.get("created"), "age_days": age})
            cards.append(row)
    # a #review card was tagged on purpose, so it goes first; then the oldest proposal, which is the one rotting
    cards.sort(key=lambda c: (0 if c["kind"] == "review" else 1, -(c["age_days"] or 0), c["project"], c["id"]))
    return cards[:REVIEW_SITTING], len(cards), untested


def review_to_try(cards=()):
    """The "To try" batch (0.65.0): every open click-through test in the owner's name (is_try_item), oldest first, that
    is not already a closure card in this sitting. Read from the same quests_api rows the quest log reads; held ones
    included, marked, because the batch is the whole pile and nothing else lists them any more."""
    on_card = {(c.get("project"), c.get("id")) for c in cards or ()}
    q = quests_api()
    out = []
    for r in list(q.get("tests") or []) + list(q.get("held") or []):
        if (r["project"], r["id"]) in on_card:
            continue
        face, _hist = note_parts(r.get("note"))
        routes = [l for l in (r.get("links") or []) if str(l).startswith("/")]
        out.append({"project": r["project"], "projectName": r.get("projectName") or r["project"], "file": r["projectPath"],
                    "id": r["id"], "text": r["text"], "note": face, "links": r.get("links") or [],
                    "route": routes[0] if routes else None, "created": r.get("created"),
                    "held": bool(ledger.is_held(r)), "until": r.get("until")})
    out.sort(key=lambda x: (x["created"] or "", x["id"]))
    return out


def review_api():
    rows = review_ratings()
    latest = review_latest()
    cards, waiting, untested = review_cards(set(latest))
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": ledger.today(),
            "cards": cards, "shown": len(cards), "waiting": waiting, "sitting": REVIEW_SITTING,
            "untested": untested, "toTry": review_to_try(cards),
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
                     "notYet": "the full evidence pass over the log and the session transcripts is a ledger item, still open"},
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
                steps.append({"project": h["id"], "projectName": ledger_label(h), "projectPath": h["tasks"],
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
                s = al.get(key) or al.get(re.sub(r"\s*\([^)]*\)\s*$", "", key).strip())   # "Sam Rivera (they/them)"
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
    """The open ledger items raised for these people's call: every open question and every open or blocked @<owner> task,
    across the registered projects, carrying `#call:<slug>` for one of the members (tasks.py `tag <id> --call <slug>`, the
    item's `call` field). This is how a call's agenda assembles itself (T-0027).
    0.81.0 (the ledger-rules pass, 2026-10-14): matched by the call tag the item carries, no longer by a name in its text
    (a first name several cards share collected lines about all of them, and an item about a person is not always for
    their call); and an open question counts again: its state is "question", never "open", so the old test dropped every
    one of them."""
    who = {}
    for slug, nm in zip(members, names):
        s = str(slug or "").strip().lower()
        if s:
            who[s] = re.sub(r"\s*\([^)]*\)\s*$", "", nm or "").strip() or s.replace("-", " ")
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
                if it["mark"] != "?":
                    continue
            elif not (it["mark"] in (" ", "-") and it["owner"] == OWNER):
                continue
            slug = str(it.get("call") or "").strip().lower()
            if slug not in who:
                continue
            out.append({"project": h.get("name") or h["id"], "path": rel, "id": it["id"], "kind": it["kind"],
                        "text": clip(it["text"], 200), "who": [who[slug]], "state": it["state"], "due": it["due"]})
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
    """'q · a · Sam, 2026-09-24 · [[t.txt]] L912 to L914' -> '... · [[t.txt]] <!-- L912 to L914 -->'."""
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


def carried_threads():
    """{series id: [thread ids it carries]} from the groups file's `carries:` field (2026-10-06, the Friday series)."""
    groups = load_groups().get("groups") or []
    return {str(g.get("id")): [str(c) for c in (g.get("carries") or [])] for g in groups
            if isinstance(g, dict) and g.get("carries")}


def subjects_for(key, members, is_group):
    """The subjects this call carries: the ones whose `threads:` name the key, plus -- for anything that is not a declared
    thread (a one-to-one, an ad-hoc set) -- the ones whose `people:` cover every participant. A settled or dropped subject
    is not carried onto a prep. Routing is the subject file's own business: a subject with the wrong fields is invisible,
    which is why the prep prints the ones it found in Context."""
    subs = [s for s in load_subjects() if s["status"] not in ("settled", "dropped")]
    # 0.67.0: a call series' `carries:` (call-prep-groups.json) names other threads whose subjects its preps carry too
    # (the Friday set carries the team's); one step only, a carried thread's own carries are not followed
    carried = carried_threads().get(key, [])
    hits = [s for s in subs if key in s["threads"] or any(t in s["threads"] for t in carried)]
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
    # 0.67.0 (the v3 order since 2026-10-06): Decide before, and the close leads the file, before the questions
    # 2026-10-23 (format section 1c): every prep carries Updates to share, between Decide before and the questions
    L += ["## Decide before, and the close", "", todo, "",
          "## Updates to share", "", "- _`/call-prep %s` writes what you tell this call that they do not know yet._" % key, "",
          "## Questions", ""]
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
    L += ["## Your notes", "",
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
        L += ["**Open in the ledgers, raised for %s's call** (answer them in the viewer at `/projects`):" %
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


load_part('part_chat.py')   # 0.68.0: the chat, in its own file


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
    """brain-viewer-holon/brain-viewer-status.json, on every start (0.68.0, the review's finding 8: it was a prose document
    rewritten per start and committed 68 times). Now counts and the keys something reads: `_generatedAt` and
    `_generatedBy` (the home board's status lamp and /api/status), one row per page with its route and its counts, the
    process (pid, supervised, the crash log's last exit) and the server (version, bind, mode). Prose about what a page is
    lives in brain-viewer-skill.md and the spec, never here."""
    try:
        cv = canvases(); m = manifest(); reg = registry(); gl = glossary_api(); qs = quests_api(); st = stages_api()
        hol = reg.get("holons", [])
        people_dir = os.path.join(BRAIN, PEOPLE_REL)
        status = {
            "_generatedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "_generatedBy": "skills/brain-viewer/serve.py v%s (on startup)" % VERSION,
            "_note": "machine-written on every start; counts only; trust = _generatedAt",
            "panels": {
                "today": {"route": "/"},
                "home": {"route": "/home", "statusFiles": sum(1 for h in hol if h.get("status"))},
                "mentee": {"route": "/mentee", "stages": len(m.get("stages", [])),
                           "pieces": sum(len(x.get("pieces", [])) for x in m.get("stages", []))},
                "projects": {"route": "/projects", "ledgers": sum(1 for h in hol if h.get("tasks")), "holons": len(hol),
                             "stamped": sum(1 for h in hol if h.get("stamped"))},
                "people": {"route": "/people", "preps": len(preps()),
                           "cards": sum(1 for f in (os.listdir(people_dir) if os.path.isdir(people_dir) else [])
                                        if f.endswith(".md") and f != "readme.md")},
                "from-claude": {"route": "/from-claude", "findings": findings_counts(), "review": review_counts()},
                "chat": {"route": "/chat", "cliVersion": CLI_VERSION, "models": [x["id"] for x in chat_models() if x["ok"]]},
                "maps": {"route": "/forge", "groups": len(maps_manifest().get("groups", []))},
                "forge": {"route": "/forge", "canvases": len(cv), "cells": sum(c.get("cells", 0) for c in cv),
                          "withForgeFile": sum(1 for c in cv if c.get("forge"))},
                "glossary": {"route": "/glossary", "terms": len(gl.get("terms", [])), "groups": len(gl.get("groups", []))},
                "questlog": {"tests": len(qs["tests"]), "done": qs["doneTotal"]},
                "stageline": {"steps": st["total"], "done": st["doneCount"]},
                "adapters": _adapter_status(),
            },
            "process": {"startedAt": STARTED_AT.isoformat(timespec="seconds"), "pid": os.getpid(),
                        "supervised": bool(os.environ.get("BV_SUPERVISED")), "health": "/api/health",
                        "crashLog": CRASH_REL, "lastExit": last_exit(), "previousRun": PREV_RUN},
            "server": {"bind": getattr(ARGS, "host", "127.0.0.1") if "ARGS" in globals() else "127.0.0.1",
                       "port": getattr(ARGS, "port", 8765) if "ARGS" in globals() else 8765,
                       "version": VERSION, "mode": mode_info()["mode"], "member": MEMBER},
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


# ---- the outbox: what the owner pressed in the viewer, handed to the main session as ONE batch (0.60.0, 2026-10-05) ----
# An answer pressed in the viewer is written onto its ledger and logged at once, and nothing told the running session
# that it happened. Every ledger write this server makes is already one context/log.md line as agent `brain-viewer`
# (tasks.py writes it), so THE LOG IS THE OUTBOX: GET /api/answers/pending reads the viewer's own ledger lines since the
# last send and resolves each one to its ledger row; POST /api/answers/submit appends them as one batch to
# context/answers-inbox.md, which a watcher and the session-start hook parse -- the batch header's shape is fixed.
# Where the last send stopped lives in the user layer, viewer/answers-state.json; with no file, the outbox starts at the
# beginning of today. Nothing here is counted in the browser and no line is typed with a clock: the log's own stamps
# are the times, and the batch header is this machine's clock read in the call that writes it.
ANSWERS_INBOX_REL = "context/answers-inbox.md"
ANSWERS_STATE_REL = USER_REL + "/answers-state.json"
ANSWERS_CUT = 140                     # an item's first sentence is cut here in the batch line
ANSWERS_INBOX_HEAD = ("# Answers inbox\n"
                      "> What the owner answered, closed, held or noted in the Brain Viewer, sent to the main session with its "
                      "every press in the viewer (since 0.92.0 held until the Send press, leaving the viewer or the quiet minutes; 0.65.0 to 0.91.0 a batch a press): appended at the bottom by skills/brain-viewer/serve.py. "
                      "The main session marks a batch done by adding a line `processed: <date time> · <one clause>` under it.\n")
_ANY_STAMP = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] ")
_ANSWER_LINE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] \[brain-viewer\] [A-Z]+ -- (\S+?) -- ([TQ]-\d{4}) (.*)$")
# what tasks.py writes after the id, for each press the owner can make in the viewer -> the word the batch uses. A line
# the viewer writes for anything else (a finding it filed, a link, a picture, a note in the notepad) is not an answer.
_ANSWER_VERBS = (("answered by ", "answered"), ("done: ", "done"), ("on hold until ", "held"),
                 ("keep in mind: ", "note"), ("reopened", "reopened"), ("back from hold", "reopened"),
                 ("blocked: ", "blocked"), ("step ", "step"))      # 0.86.0: a tick on a step (`step 3 of 11 ticked: ...`)
# 0.93.0 (brain-viewer T-0360): a note taken or edited in the notepad rides the send too. Until now the notepad's
# CREATED and MODIFIED lines were left out on purpose and a note never reached the session (10/26: four notes written in
# the viewer that morning reached nobody; the owner: notepad notes should be included in that send). One notepad, no
# second kind: each note is one batch line, `- notepad · HH:MM · on <page> · "<first sentence>" · <its path>`.
_NOTEPAD_LINE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] \[brain-viewer\] (?:CREATED|MODIFIED) -- (thoughts/notepad/\S+\.md) -- (note (?:taken|edited) in the viewer's notepad.*)$")


def notepad_batch_row(rel, when, n):
    """A note the notepad wrote, as the batch carries it: the page it was taken on and its first sentence (0.93.0)."""
    page, first = "", ""
    try:
        with open(os.path.join(BRAIN, rel.replace("/", os.sep)), "r", encoding="utf-8-sig") as f:
            text = f.read().replace("\r\n", "\n")
        m = re.search(r"^\*\*Taken:\*\* .*? in the Brain Viewer on (\S+)\s*$", text, re.M)
        page = m.group(1) if m else ""
        body = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("#") and not l.startswith("**Taken:**")]
        first = _first_sentence(" ".join(body)) if body else ""
    except OSError:
        pass
    return {"project": "notepad", "id": "", "kind": "notepad", "when": when, "action": "notepad",
            "text": first or rel.split("/")[-1], "page": page, "ledger": rel, "presses": 1, "_n": n}
_answers_lock = threading.Lock()


def _json_read(ap):
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def _json_write(ap, data):
    """Written whole and swapped in, so a reader never sees half a file."""
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    tmp = ap + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, ap)


def answers_state():
    return _json_read(os.path.join(BRAIN, ANSWERS_STATE_REL.replace("/", os.sep))) or {}


def _first_sentence(text, cut=ANSWERS_CUT):
    """An item's first sentence, on one line, cut at `cut` characters at a word with ' ...' (a question keeps its '?').
    Double quotes become single ones, because the batch line quotes the sentence."""
    t = " ".join(str(text or "").split()).replace('"', "'")
    m = re.match(r"(.+?[.?!])(?=\s+[A-Z0-9'(\[*]|$)", t)
    s = m.group(1) if m else t
    if len(s) > cut:
        tail = " ...?" if s.endswith("?") else " ..."
        s = s[:cut - len(tail)].rsplit(" ", 1)[0].rstrip(" ,;:") + tail
    return s


def _latest_note(note):
    """The newest line on an item's note: the part after the last `; note <day>:` / `; rated ...` boundary, with the
    plain note stamp taken off (the batch line says when)."""
    s = " ".join(str(note or "").split())
    if not s:
        return ""
    parts = [p.strip() for p in _NOTE_SPLIT.split(s) if p.strip()]
    last = parts[-1] if parts else s
    return re.sub(r"^note (?:\(viewer, \d{4}-\d{2}-\d{2}\)|\d{4}-\d{2}-\d{2}):\s*", "", last, flags=re.I)


def _answers_cursor(state):
    """-> (minute, seen): the next read takes log lines stamped after `minute`, and lines stamped IN that minute that are
    not among `seen` (the lines that minute already held when the last batch was sent). The log is minute-stamped and
    append-only in order (log.py refuses an inversion), so this loses nothing and sends nothing twice. (None, []) when
    nothing has been sent: the outbox then starts at the beginning of today."""
    cur = state.get("cursor") if isinstance(state.get("cursor"), dict) else {}
    minute = str(cur.get("minute") or "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", minute):
        return minute, [str(x) for x in (cur.get("seen") or [])]
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})", str(state.get("lastSubmitAt") or ""))
    if m:
        return "%s %s" % m.groups(), []
    return None, []


def _ledger_row(rel, iid, cache):
    """The item as its ledger holds it now, or None (a ledger moved, an id gone). Each ledger parsed once per call."""
    rel = norm(rel)
    if not rel or not rel.endswith(".md"):
        return None
    if rel not in cache:
        try:
            cache[rel] = ledger.parse(ledger.read(os.path.join(BRAIN, rel.replace("/", os.sep))))
        except Exception:                                          # noqa: BLE001
            cache[rel] = None
    p = cache[rel]
    return next((x for x in p["items"] if x["id"] == iid), None) if p else None


def answers_read():
    """-> (body for GET /api/answers/pending, (minute, lines) the cursor a send made now would leave).

    One line per ITEM, however many presses it had: its action is the last thing done to it other than a note (an answer,
    a done, a hold, a reopen), or `note` when a note is all it got; `when` is that press's time. The words come from the
    ledger as it stands -- the item's first sentence, its answer, the newest line of its note -- and fall back to the
    log line when the item is gone. Newest first."""
    state = answers_state()
    minute, seen = _answers_cursor(state)
    today = dt.date.today().isoformat()
    since_day = minute[:10] if minute else today
    left = {}
    for s in seen:
        left[s] = left.get(s, 0) + 1
    events, last_minute, last_lines = [], None, []
    for line in log_lines(since=since_day):
        ms = _ANY_STAMP.match(line)
        if not ms:
            continue
        st = ms.group(1)
        if st[:10] < since_day:
            continue
        if st != last_minute:
            last_minute, last_lines = st, []
        last_lines.append(line)
        if minute:
            if st < minute:
                continue
            if st == minute and left.get(line):
                left[line] -= 1
                continue
        mn = _NOTEPAD_LINE.match(line)
        if mn:                                                     # 0.93.0 (T-0360): a notepad note rides the send
            events.append({"when": st, "rel": mn.group(2), "id": "", "action": "notepad", "said": mn.group(3)})
            continue
        m = _ANSWER_LINE.match(line)
        if not m:
            continue
        rest = m.group(4)
        act = next((w for pre, w in _ANSWER_VERBS if rest.startswith(pre)), None)
        if act:
            events.append({"when": st, "rel": m.group(2), "id": m.group(3), "action": act, "said": rest})
    holons = {h.get("tasks"): h.get("id") for h in registry().get("holons", []) if h.get("tasks")}
    groups, order = {}, []
    for ev in events:
        k = (ev["rel"], ev["id"])
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(ev)
    cache, items = {}, []
    for n, k in enumerate(order):
        rel, iid = k
        evs = groups[k]
        if not iid and evs[-1]["action"] == "notepad":              # 0.93.0 (T-0360): the note's own row
            items.append(notepad_batch_row(rel, evs[-1]["when"], n))
            continue
        it = _ledger_row(rel, iid, cache)
        acts = [e for e in evs if e["action"] != "note"]
        main = acts[-1] if acts else evs[-1]
        notes = [e for e in evs if e["action"] == "note"]
        kind = it["kind"] if it else ("question" if iid.startswith("Q") else "task")
        text = it["text"] if it else main["said"].split(": ", 1)[-1]
        row = {"project": holons.get(rel) or rel.split("/")[0], "id": iid, "kind": kind, "when": main["when"],
               "action": main["action"], "text": _first_sentence(text), "ledger": rel, "presses": len(evs), "_n": n}
        if main["action"] == "answered":
            # the words pressed are the log's (tasks.py keeps the first 80 characters); the ledger's answer is used when it
            # is still those words in full, and not when someone answered the item again afterwards in other words
            said = " ".join(re.sub(r" \(unblocked [^)]*\)$", "", re.sub(r"^answered by \S+: ", "", main["said"])).split())
            full = " ".join(str(it.get("answer") or "").split()) if it and it.get("mark") == "a" else ""
            row["answer"] = full if full and full.startswith(said[:79]) else (said + (" ..." if len(said) >= 80 else ""))
        if notes:
            said = _latest_note(it.get("note")) if it else ""
            row["note"] = said or notes[-1]["said"][len("keep in mind: "):]
        if main["action"] == "step":
            # 0.86.0: which step was ticked (the log's own words, `3 of 11 ticked: <the step>`)
            row["step"] = main["said"][len("step "):]
        items.append(row)
    items.sort(key=lambda r: (r["when"], r["_n"]), reverse=True)
    for r in items:
        r.pop("_n", None)
    body = {"count": len(items), "since": minute or (today + " 00:00"), "items": items,
            "lastSubmitAt": state.get("lastSubmitAt"), "lastBatch": state.get("lastBatch"),
            "batches": int(state.get("batches") or 0), "inbox": ANSWERS_INBOX_REL}
    return body, (last_minute, last_lines)


def answers_pending():
    """GET /api/answers/pending: answers_read's body, plus (0.92.0) what an undo set aside while answers are held
    (`held`), the whole count the Send press would send (`toSend`), and the hold as it stands (`hold`)."""
    body = answers_read()[0]
    held = _answers_held(answers_state())
    body["held"] = held["undos"] + held["answers"]
    body["toSend"] = body["count"] + body["held"]
    s = answers_hold_setting()
    body["hold"] = {"on": s["on"], "quietMinutes": s["quietMinutes"], "sendsAt": _hold["sendsAt"], "awaySendsAt": _hold["awayAt"]}
    return body


def _answers_held(state):
    """The lines an undo set aside while answers are held (0.92.0): {lines, undos, answers}, empty when there are none."""
    h = state.get("held") if isinstance(state.get("held"), dict) else {}
    return {"lines": [str(x) for x in (h.get("lines") or [])], "undos": int(h.get("undos") or 0), "answers": int(h.get("answers") or 0)}


def answers_batch_lines(items, stamp):
    """The batch as it is written: the fixed header, then one line per item. A press made on the batch's own day is
    timed HH:MM, an older one carries its day as well."""
    n = len(items)
    out = ["## Batch %s (%d answer%s)" % (stamp, n, "" if n == 1 else "s")]
    for r in items:
        when = r["when"][11:] if r["when"][:10] == stamp[:10] else r["when"]
        if r.get("kind") == "notepad":                               # 0.93.0 (T-0360): a note taken in the notepad
            out.append('- notepad · %s · on %s · "%s" · %s' % (when, r.get("page") or "a page", r["text"], r["ledger"]))
            continue
        tail = (" · answer: %s" % r["answer"]) if r.get("answer") else ""
        tail += (" · note: %s" % r["note"]) if r.get("note") else ""
        tail += (" · step: %s" % r["step"]) if r.get("step") else ""        # 0.86.0
        out.append('- %s %s · %s · %s %s · "%s"%s' % (r["project"], r["id"], r["kind"], r["action"], when, r["text"], tail))
    return out


def answers_submit(why=None):
    """POST /api/answers/submit -> (code, body). Reads what is pending HERE (never from the page), appends one batch to
    context/answers-inbox.md (created with its two-line header on first use), moves the cursor past every line it read,
    and logs one line. With nothing pending it writes nothing at all. `why` (0.92.0) ends the log line: the Send press,
    leaving the viewer, the quiet minutes. Whatever sends, the hold's timers stop."""
    if PROPOSE:
        return 403, {"ok": False, "count": 0, "error": "a team copy does not send answers to the owner's session"}
    _hold_stop()
    with _answers_lock:
        return _answers_submit_locked(why)


def _inbox_append(lines):
    """One batch appended to context/answers-inbox.md (created with its two-line header on first use)."""
    ap = os.path.join(BRAIN, ANSWERS_INBOX_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    lead = ""
    if not os.path.isfile(ap):
        lead = ANSWERS_INBOX_HEAD
    else:
        with open(ap, "rb") as f:
            f.seek(0, 2)
            if f.tell():
                f.seek(-1, 2)
                if f.read(1) != b"\n":
                    lead = "\n"
    with open(ap, "a", encoding="utf-8", newline="\n") as f:
        f.write(lead + "\n" + "\n".join(lines) + "\n")


def _answers_cursor_move(now, stamp, n, cur_min, cur_lines):
    """The state file after a batch: the cursor past every log line the batch read, and nothing left held."""
    st = answers_state()
    st.update({"lastSubmitAt": now.isoformat(timespec="seconds"), "lastBatch": stamp, "lastCount": n,
               "batches": int(st.get("batches") or 0) + 1,
               "cursor": {"minute": cur_min or stamp, "seen": cur_lines if cur_min else []}})
    st.pop("held", None)
    _json_write(os.path.join(BRAIN, ANSWERS_STATE_REL.replace("/", os.sep)), st)


def _answers_hold_keep(lines, undos, answers, stamp, cur_min, cur_lines):
    """0.92.0: an undo made while answers are held is set aside with what was pending beside it, in the state file, and the
    cursor moves past what it read; the next send puts these lines first in its batch. Nothing reaches the inbox now."""
    st = answers_state()
    held = _answers_held(st)
    if held["lines"] or lines:
        st["held"] = {"lines": held["lines"] + list(lines), "undos": held["undos"] + undos, "answers": held["answers"] + answers}
    st["cursor"] = {"minute": cur_min or stamp, "seen": cur_lines if cur_min else []}
    _json_write(os.path.join(BRAIN, ANSWERS_STATE_REL.replace("/", os.sep)), st)


def _batch_head(stamp, undos, answers):
    """`## Batch <stamp> (N answers)`, or with an undo in it `(1 undo, N answers)` / `(1 undo)`, the shape since 0.71.0."""
    parts = (["%d undo%s" % (undos, "" if undos == 1 else "s")] if undos else []) \
        + (["%d answer%s" % (answers, "" if answers == 1 else "s")] if answers or not undos else [])
    return "## Batch %s (%s)" % (stamp, ", ".join(parts))


def _answers_submit_locked(why=None):
    """answers_submit's body, for a caller that already holds _answers_lock (the undo route sends what is pending first
    when answers are not held). What an undo set aside while they were held goes first, under one header."""
    body, (cur_min, cur_lines) = answers_read()
    held = _answers_held(answers_state())
    n = body["count"]
    if not n and not held["lines"]:
        return 200, {"ok": False, "count": 0}
    now = dt.datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M")
    lines = answers_batch_lines(body["items"], stamp)
    if held["lines"]:
        lines = [_batch_head(stamp, held["undos"], held["answers"] + n)] + held["lines"] + lines[1:]
    total = n + held["answers"] + held["undos"]
    _inbox_append(lines)
    _answers_cursor_move(now, stamp, total, cur_min, cur_lines)
    note = log_line("%s -- %d %s sent to the main session as one batch (%s)%s"
                    % (ANSWERS_INBOX_REL, total, "answer" if total == 1 else "answers", stamp, (", " + why) if why else ""))
    return 200, {"ok": True, "batch": stamp, "count": total, "path": ANSWERS_INBOX_REL, "log": note}


# ---- every press reaches the session at once (0.65.0, 2026-10-06, Round 1 of the viewer review) ----
# The round send press existed only to wake the session: the ledger write had already happened when he pressed. Now a
# successful write on any of these routes is followed, on its own thread, by answers_submit() -- so every answer, done,
# hold or note lands in context/answers-inbox.md as its own batch within a second, and the session's batch watcher wakes
# on it. One answer per batch is fine. answers_submit holds the lock and writes nothing when nothing is pending, so two
# presses close together make one batch or two, never a duplicate. The floating send press is gone from every page;
# POST /api/answers/submit stays for a hand-run and for the tests. 0.92.0: this is now the hold OFF case; with the hold on
# (the default) a press only starts the quiet timer over, and the send press is back (the section after this one).
ANSWERS_AUTOSEND_ROUTES = {"/api/tasks", "/api/reply", "/api/today/tasks/action", "/api/review", "/api/today/waiting/action"}


def answers_autosend(why=None):
    try:
        answers_submit(why)
    except Exception as e:                                         # noqa: BLE001 -- a failed send must never fail the press
        sys.stderr.write("answers autosend failed: %s: %s\n" % (type(e).__name__, e))


def answers_autosend_soon():
    """After a press that wrote: with answers held (0.92.0, the default), the quiet timer starts over; with the hold off,
    the press goes to the session at once, as 0.65.0 had it."""
    if PROPOSE:
        return
    if answers_hold_setting()["on"]:
        answers_hold_arm()
        return
    threading.Thread(target=answers_autosend, name="answers-autosend", daemon=True).start()


# ---- answers held until he sends them (0.92.0, 2026-10-26, brain-viewer T-0359) ----
# The owner, 10/26, after two presses woke the session while he was still working down the page: "why does this whole
# answers batch process run before I have moved off of the page to go through what has been answered?" So a press still
# writes its ledger at once (nothing is lost if the page closes), but the batch that wakes the session waits for the
# first of three things: the Send answers press at the bottom right of every page, the viewer going out of sight (no
# viewer page visible for ANSWERS_AWAY_GRACE seconds: a tab switch, the window closed, the phone locked; moving from one
# viewer page to the next does not count, the new page says it is here before the grace runs out), or the quiet minutes
# with no new press. Both the hold and the minutes are settings (viewer/settings.json `answers_hold`,
# `answers_quiet_minutes`), changed on the Settings page; the timers live here, on the server, so a phone that drops the
# page without a word still has its answers sent. A restart re-arms the quiet timer when something is waiting.
ANSWERS_HOLD_DEFAULT_MINUTES = 5
ANSWERS_AWAY_GRACE = 20
HOLD_MINUTE = float(os.environ.get("BV_HOLD_MINUTE_SECONDS") or 60)    # the tests shorten a minute; nothing else sets it
_hold_lock = threading.Lock()
_hold = {"quiet": None, "away": None, "sendsAt": None, "awayAt": None}


def answers_hold_setting():
    """{on, quietMinutes} read from viewer/settings.json at each call, so a change on the Settings page holds at once.
    On by default; the minutes 1 to 60, 5 by default; never on in a team copy, which sends nothing to a session."""
    d = load_settings(os.path.join(BRAIN, SETTINGS_REL.replace("/", os.sep)))
    on = d.get("answers_hold")
    try:
        mins = int(d.get("answers_quiet_minutes") or ANSWERS_HOLD_DEFAULT_MINUTES)
    except (TypeError, ValueError):
        mins = ANSWERS_HOLD_DEFAULT_MINUTES
    return {"on": (True if on is None else bool(on)) and not PROPOSE, "quietMinutes": max(1, min(60, mins))}


def _hold_clock(seconds):
    return (dt.datetime.now() + dt.timedelta(seconds=seconds)).isoformat(timespec="seconds")


def _hold_timer(which, seconds, why):
    """Starts (or starts over) one of the two timers; the caller holds _hold_lock."""
    t = _hold.get(which)
    if t:
        t.cancel()
    t = threading.Timer(seconds, _hold_fire, args=(why,))
    t.daemon = True
    t.name = "answers-hold-" + which
    t.start()
    _hold[which] = t
    _hold["sendsAt" if which == "quiet" else "awayAt"] = _hold_clock(seconds)


def _hold_stop(which=("quiet", "away")):
    with _hold_lock:
        for k in which:
            t = _hold.get(k)
            if t:
                t.cancel()
            _hold[k] = None
            _hold["sendsAt" if k == "quiet" else "awayAt"] = None


def _hold_fire(why):
    _hold_stop()
    answers_autosend(why)


def answers_hold_arm():
    """The quiet timer, started over: what is held goes after this many minutes with no new press."""
    mins = answers_hold_setting()["quietMinutes"]
    with _hold_lock:
        _hold_timer("quiet", mins * HOLD_MINUTE, "after %d quiet minute%s" % (mins, "" if mins == 1 else "s"))


def answers_to_send():
    return answers_pending()["toSend"]


def answers_away():
    """POST /api/answers/away: a viewer page went out of sight. With something held, it goes in ANSWERS_AWAY_GRACE seconds
    unless a viewer page says it is here first."""
    if PROPOSE or not answers_hold_setting()["on"]:
        return 200, {"ok": True, "held": False}
    n = answers_to_send()
    if n:
        with _hold_lock:
            _hold_timer("away", ANSWERS_AWAY_GRACE, "on leaving the viewer")
    return 200, {"ok": True, "held": True, "toSend": n, "awaySendsAt": _hold["awayAt"]}


def answers_here():
    """POST /api/answers/here: a viewer page is in sight (it loaded, or came back to the front); the away timer stops."""
    _hold_stop(("away",))
    return 200, {"ok": True}


def answers_hold_resume():
    """At start (0.92.0): answers left held by the run before are sent after the quiet minutes, never left waiting."""
    try:
        if not PROPOSE and answers_hold_setting()["on"] and answers_to_send():
            answers_hold_arm()
    except Exception as e:                                         # noqa: BLE001 -- a start never fails over this
        sys.stderr.write("answers hold resume failed: %s: %s\n" % (type(e).__name__, e))


# ---- the settings a person changes in the viewer (0.92.0, the Settings page) ----
# GET /api/settings and PUT /api/settings read and write the keys below in viewer/settings.json, the user layer, and
# nothing else: the other keys (owner, the prep horizon, the forge root...) are kept as they are, byte for byte in value.
SETTINGS_EDITABLE = {
    "answers_hold": ("whether an answer, done, hold or note pressed in the viewer waits to be sent to the main session "
                     "(the Send answers press, leaving the viewer, or the quiet minutes) instead of going at once; on by default"),
    "answers_quiet_minutes": "how many minutes with no new press before held answers go to the main session on their own, 1 to 60; 5 by default",
}


def settings_read():
    s = answers_hold_setting()
    return {"answers": {"hold": s["on"], "quietMinutes": s["quietMinutes"], "default": ANSWERS_HOLD_DEFAULT_MINUTES,
                        "teamCopy": bool(PROPOSE)}, "path": SETTINGS_REL}


def settings_write(data):
    """PUT /api/settings {answers_hold?: bool, answers_quiet_minutes?: 1..60} -> (code, body)."""
    if PROPOSE:
        return 403, {"error": "a team copy sends no answers to a session, so it has nothing to hold"}
    if not isinstance(data, dict) or not data:
        return 400, {"error": "send the settings to change, as {answers_hold: true or false, answers_quiet_minutes: 1 to 60}"}
    bad = [k for k in data if k not in SETTINGS_EDITABLE]
    if bad:
        return 400, {"error": "not a setting this page changes: %s" % ", ".join(sorted(bad))}
    if "answers_hold" in data and not isinstance(data["answers_hold"], bool):
        return 400, {"error": "answers_hold is true or false"}
    if "answers_quiet_minutes" in data:
        m = data["answers_quiet_minutes"]
        if isinstance(m, bool) or not isinstance(m, int) or not 1 <= m <= 60:
            return 400, {"error": "answers_quiet_minutes is a whole number of minutes from 1 to 60"}
    ap = os.path.join(BRAIN, SETTINGS_REL.replace("/", os.sep))
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            cur = json.load(f, object_pairs_hook=collections.OrderedDict)
        if not isinstance(cur, dict):
            cur = collections.OrderedDict()
    except FileNotFoundError:
        cur = collections.OrderedDict()
    except Exception as e:                                         # noqa: BLE001
        return 409, {"error": "viewer/settings.json does not read as JSON (%s); fix it by hand first" % e}
    was = answers_hold_setting()
    keys = cur.get("_keys") if isinstance(cur.get("_keys"), dict) else None
    if keys is not None:
        for k in data:
            keys.setdefault(k, SETTINGS_EDITABLE[k])
    for k, v in data.items():
        cur[k] = v
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    tmp = ap + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, ap)
    SETTINGS.update(data)
    now = answers_hold_setting()
    log_line("%s -- answers %s, sent after %d quiet minute%s (the Settings page)"
             % (SETTINGS_REL, "held until sent" if now["on"] else "sent at each press", now["quietMinutes"],
                "" if now["quietMinutes"] == 1 else "s"))
    # what is waiting follows the new setting: the hold turned off sends it now, the minutes changed start over
    if was["on"] and not now["on"]:
        _hold_stop()
        threading.Thread(target=answers_autosend, args=("when the hold was turned off",), name="answers-autosend", daemon=True).start()
    elif now["on"] and (answers_to_send() and (not was["on"] or was["quietMinutes"] != now["quietMinutes"])):
        answers_hold_arm()
    return 200, {"ok": True, "settings": settings_read()}


# ---- a way back from every press, for the rest of the day (0.71.0, the Today direction rule 3, viewer T-0308 item 2) ----
# Since 0.65.0 every answer, done, hold and note press reaches the session the moment it is made, so a mis-press had no way
# back. Now each of those presses, on whichever page made it (PUT /api/tasks, POST /api/reply, POST /api/today/tasks/action,
# POST /api/today/waiting/action), first keeps the item as it stood in a journal for the day, viewer/undo/<day>.json in the
# user layer. GET /api/today/undo lists the day's presses; POST /api/today/undo takes one back: the item is put back the way
# it stood before that press (and before every later press on it today) through tasks.py's own verbs -- `reopen` clears a
# done, a hold or an answer; `answer` puts back an earlier answer; `block` and `hold` put back what a reopen clears; `note`
# puts back the note -- and the tasks an answer freed are blocked on the question again. The undo is then written to
# context/answers-inbox.md as a batch of its own, `- <project> · undo · <id> · <what was reverted> · "<sentence>"`, so the
# session that read the press reads its undo too. The day's file is the whole reach: at midnight a new file starts and the
# presses before it are final. A change of answer is no verb of its own: it is a second answer press, journaled like the first.
UNDO_DIR_REL = USER_REL + "/undo"
UNDO_FIELDS = ("mark", "note", "until", "blocked", "answer", "answered", "done", "steps")
UNDO_ACTIONS = {"answer": "answered", "done": "done", "hold": "held", "note": "note", "reopen": "reopened", "steps": "step"}   # 0.86.0: a tick
UNDO_ROUTES = {"/api/today/undo"}
_undo_lock = threading.Lock()


def _undo_path(day=None):
    return os.path.join(BRAIN, UNDO_DIR_REL.replace("/", os.sep), "%s.json" % (day or ledger.today()))


def undo_journal(day=None):
    """The day's presses as kept: {day, presses: [{n, at, route, action, project, ledger, id, said, before, undone}]}."""
    day = day or ledger.today()
    d = _json_read(_undo_path(day)) or {}
    if d.get("day") != day or not isinstance(d.get("presses"), list):
        d = {"day": day, "presses": []}
    return d


def _undo_find(path, iid):
    parsed = ledger.parse(ledger.read(path))
    return parsed, next((x for x in parsed["items"] if x["id"] == str(iid or "").strip()), None)


def undo_before(path, iid):
    """The item as it stands before a press, with the tasks it holds blocked (an answer frees them). None when unreadable."""
    try:
        parsed, it = _undo_find(path, iid)
    except Exception:                                              # noqa: BLE001 -- no snapshot, no undo; the press still runs
        return None
    if it is None:
        return None
    snap = {k: it.get(k) for k in UNDO_FIELDS}
    snap["kind"] = it["kind"]
    snap["holds"] = [x["id"] for x in parsed["items"] if x["kind"] == "task" and x["mark"] == "-" and (x.get("blocked") or "") == it["id"]]
    return snap


def undo_record(rel, iid, action, before, route, said=""):
    """One press kept in the day's journal. -> its number, or None when there is nothing to keep (a team copy, no snapshot)."""
    if PROPOSE or before is None or action not in UNDO_ACTIONS:
        return None
    holon = next((h["id"] for h in registry().get("holons", []) if h.get("tasks") == rel), rel.split("/")[0])
    with _undo_lock:
        j = undo_journal()
        n = max([int(x.get("n") or 0) for x in j["presses"]] or [0]) + 1
        j["presses"].append({"n": n, "at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "route": route,
                             "action": UNDO_ACTIONS[action], "project": holon, "ledger": rel, "id": str(iid),
                             "said": " ".join(str(said or "").split())[:200], "before": before, "undone": None})
        _json_write(_undo_path(), j)
    return n


def undo_list():
    """GET /api/today/undo: the day's presses, newest first, each with the item as it reads now (its first sentence, its
    kind, its presses for a change of answer). An undone press stays listed, marked, so the day reads in order."""
    j = undo_journal()
    cache, rows = {}, []
    for p in j["presses"]:
        it = _ledger_row(p.get("ledger"), p.get("id"), cache)
        rows.append({"n": p["n"], "at": p.get("at"), "action": p.get("action"), "project": p.get("project"),
                     "ledger": p.get("ledger"), "id": p.get("id"), "said": p.get("said") or "",
                     "undone": p.get("undone"), "kind": (it or {}).get("kind") or p.get("before", {}).get("kind"),
                     "text": _first_sentence((it or {}).get("text") or ""), "fullText": (it or {}).get("text") or "",
                     "mark": (it or {}).get("mark"), "answer": (it or {}).get("answer"),
                     "options": (it or {}).get("options"), "links": (it or {}).get("links") or []})
    rows.sort(key=lambda r: -int(r["n"]))
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "day": j["day"], "presses": rows,
            "open": sum(1 for r in rows if not r["undone"])}


def _undo_revert(path, rel, iid, before):
    """Put one item back as `before` describes it, through tasks.py's verbs. -> the words of what was taken back."""
    day = ledger.today()
    words = []
    act = lambda verb, **a: ledger.apply(path, rel, verb, agent="brain-viewer", id=iid, **a)
    _p, cur = _undo_find(path, iid)
    if cur is None:
        raise ledger.LedgerError("the item is not on its ledger any more")
    bm, cm = before.get("mark"), cur["mark"]
    if cur["kind"] == "question":
        if bm == "?" and cm == "a":
            act("reopen")
            words.append("the answer %s cleared, the question is open again" % _undo_q(cur.get("answer")))
        elif bm == "a" and (cm != "a" or (cur.get("answer") or "") != (before.get("answer") or "")):
            act("answer", text=before.get("answer") or "", by=OWNER)
            words.append("the earlier answer %s put back" % _undo_q(before.get("answer")))
    else:
        if bm == "x":
            if cm != "x":
                act("done")
                words.append("closed again")
        else:
            moved = (cm != bm or (cur.get("until") or "") != (before.get("until") or "")
                     or (cur.get("blocked") or "") != (before.get("blocked") or ""))
            if moved:
                if cm == "x" or cm == "-" or cur.get("until"):
                    act("reopen")
                    words.append("open again" if cm == "x" else "back from hold" if cur.get("until") else "unblocked")
                if bm == "-" and before.get("blocked"):
                    act("block", by=before["blocked"])
                    words.append("blocked again as it was")
                if bm == " " and before.get("until") and before["until"] > day:
                    act("hold", until=before["until"])
                    words.append("on hold until %s again" % before["until"])
    _p, cur = _undo_find(path, iid)
    if cur is not None and (cur.get("note") or "") != (before.get("note") or ""):
        act("note", note=before.get("note") or "")
        words.append("the note put back as it was" if before.get("note") else "the note taken off")
    # 0.86.0: the steps as they stood, ticks included (a tick press is the usual case; a set from the chat is not a press)
    if cur is not None and ledger.steps_field(cur.get("steps") or []) != ledger.steps_field(before.get("steps") or []):
        act("steps", steps=ledger.steps_field(before.get("steps") or []))
        words.append("the steps put back as they were" if before.get("steps") else "the steps taken off")
    freed = 0
    for tid in before.get("holds") or []:
        parsed, t = _undo_find(path, tid)
        if t is not None and t["kind"] == "task" and t["mark"] == " " and not t.get("blocked"):
            ledger.apply(path, rel, "block", agent="brain-viewer", id=tid, by=iid)
            freed += 1
    if freed:
        words.append("%d task%s it had freed blocked on it again" % (freed, "" if freed == 1 else "s"))
    return words or ["nothing had changed since"]


def _undo_q(text):
    t = " ".join(str(text or "").split()).replace('"', "'")
    return '"%s"' % (t if len(t) <= 80 else t[:77].rsplit(" ", 1)[0] + " ...")


def undo_apply(n=None, which=None, iid=None):
    """POST /api/today/undo {n} or {ledger, id} -> (code, body). With n, that press and every later one on the same item
    today; with ledger + id, every press on that item today. Refused for a press from another day (there is none in the
    file) and for one already undone."""
    if PROPOSE:
        return 403, {"error": "a team copy does not change the owner's ledgers"}
    hold = answers_hold_setting()["on"]
    with _answers_lock:
        if not hold:
            _answers_submit_locked()                               # what was pressed before the undo goes out first, in order
        with _undo_lock:
            j = undo_journal()
            live = [p for p in j["presses"] if not p.get("undone")]
            if n is not None:
                try:
                    n = int(n)
                except (TypeError, ValueError):
                    return 400, {"error": "n is a press number"}
                hit = next((p for p in j["presses"] if int(p.get("n") or 0) == n), None)
                if hit is None:
                    return 404, {"error": "there is no such press today; the presses of another day are final"}
                if hit.get("undone"):
                    return 409, {"error": "that press was already undone at %s" % hit["undone"][11:]}
            else:
                want = str(which or "").replace("\\", "/").strip()
                h = next((h for h in registry().get("holons", []) if h.get("tasks") and want in (h["id"], h["tasks"])), None)
                rel = h["tasks"] if h else want
                same = [p for p in live if p.get("ledger") == rel and p.get("id") == str(iid or "").strip()]
                if not same:
                    return 404, {"error": "nothing pressed on that item today is left to undo"}
                hit = min(same, key=lambda p: int(p["n"]))
            rel, item = hit["ledger"], hit["id"]
            later = [p for p in live if p.get("ledger") == rel and p.get("id") == item and int(p["n"]) >= int(hit["n"])]
            path = os.path.join(BRAIN, rel.replace("/", os.sep))
            try:
                words = _undo_revert(path, rel, item, hit.get("before") or {})
            except ledger.LedgerError as e:
                return 400, {"error": str(e)}
            stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            for p in later:
                p["undone"] = stamp
            _json_write(_undo_path(), j)
        # the undo's own ledger lines are read here and stand for themselves in the batch, so the next press's batch does
        # not send them again as a reopen or a note; anything else pressed meanwhile goes out in the same batch
        body, (cur_min, cur_lines) = answers_read()
        touched = {item} | set((hit.get("before") or {}).get("holds") or [])     # the item and the tasks it re-blocked
        others = [r for r in body["items"] if not (r["ledger"] == rel and r["id"] in touched)]
        _p, now_it = _undo_find(path, item)
        what = "%s %s taken back: %s" % (" and ".join(sorted({p["action"] for p in later})), hit["at"][11:], "; ".join(words))
        line = '- %s · undo · %s · %s · "%s"' % (hit["project"], item, what, _first_sentence((now_it or {}).get("text") or ""))
        if hold:
            # 0.92.0: nothing goes now. A press that was never sent is simply taken back, with nothing to tell the
            # session; one already sent leaves its undo line set aside for the next send, ahead of what waits beside it
            # the journal stamps a press to the minute; a press in the same minute as the last send counts as sent
            last = str(answers_state().get("lastSubmitAt") or "").replace("T", " ")[:16]
            unsent = not last or str(hit.get("at") or "").replace("T", " ")[:16] > last
            keep = ([] if unsent else [line]) + answers_batch_lines(others, stamp)[1:]
            _answers_hold_keep(keep, 0 if unsent else 1, len(others), stamp, cur_min, cur_lines)
            log_line("%s -- %s (%s %s, %s)" % (ANSWERS_INBOX_REL, "a press taken back before it was sent" if unsent
                     else "an undo held for the next send", hit["project"], item, stamp))
        else:
            lines = [_batch_head(stamp, 1, len(others)), line] + answers_batch_lines(others, stamp)[1:]
            _inbox_append(lines)
            _answers_cursor_move(dt.datetime.now(), stamp, 1 + len(others), cur_min, cur_lines)
            log_line("%s -- an undo sent to the main session (%s %s, %s)" % (ANSWERS_INBOX_REL, hit["project"], item, stamp))
    if hold and answers_to_send():
        answers_hold_arm()
    return 200, {"ok": True, "undone": [int(p["n"]) for p in later], "what": "; ".join(words),
                 "batch": None if hold else stamp, "held": hold, "message": "Taken back: %s." % "; ".join(words)}


# ---- waiting on others (0.71.0, the Today direction rule 2) ----
# The card holds only what another person moves next: an open task blocked by an item someone else owes (a question
# to them, or a task of theirs), a task blocked or held with a person named in its words, and a question put to someone
# else. Never an item that is the owner's own to do, and never Claude's (that is not a person to nudge). Each row says
# who and since when (the blocker's own day, the newest day in the note, or the item's own), with a nudge (a note on the
# item) and a drop (closed with a reason). Derived at read time from the ledgers; stored nowhere.
_WAIT_VERB = re.compile(r"\b(?:waiting on|waits on|wait for|waiting for|until|hears? from|heard from|reply from|answer from|"
                        r"asked|ask|ping|chase|from|on)\s+(@?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)")
_WAIT_SKIP = {"claude", "the", "this", "that", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
              "today", "tomorrow", "january", "february", "march", "april", "may", "june", "july", "august", "september",
              "october", "november", "december", "pf", "replit", "git", "the app"}


def _wait_people():
    """{first name lower -> display name} for every people/ card, and the owner's own spellings to leave out."""
    out = {}
    for spelling, slug in card_name_index().items():
        first = slug.split("-")[0]
        if first and first not in out:
            out[first] = " ".join(w.capitalize() for w in slug.split("-")[:2])
    return out


def _wait_owner_words():
    me = OWNER.lstrip("@").lower()
    return {me, me.split("-")[0], "zak", "zakary", "me", "claude", "you"}


def _wait_named(text, people):
    """The first person a sentence names as the one being waited on: an @handle that is not the owner or Claude, a card's
    first name, or a capitalised name after a waiting phrase. None when it names nobody."""
    s = str(text or "")
    mine = _wait_owner_words()
    for h in re.findall(r"@([a-z][\w-]*)", s):
        if h.lower() not in mine:
            return people.get(h.lower().split("-")[0]) or h.capitalize()
    for w in re.findall(r"\b([A-Z][a-z]{2,})\b", s):
        if w.lower() in people and w.lower() not in mine:
            return people[w.lower()]
    for m in _WAIT_VERB.finditer(s):
        nm = m.group(1).lstrip("@")
        if nm.lower() not in _WAIT_SKIP and nm.split()[0].lower() not in mine and nm.split()[0].lower() not in _WAIT_SKIP:
            return nm
    return None


def _who_word(owner, people):
    h = str(owner or "").lstrip("@").lower()
    return people.get(h.split("-")[0]) or h.replace("-", " ").title()


def waiting_others_api():
    """GET /api/today/waiting -> {count, rows:[{project, projectName, ledger, id, kind, text, who, since, why, note}]},
    oldest wait first."""
    today = ledger.today()
    people = _wait_people()
    mine = {OWNER, "@claude"}
    rows = []
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        ap = os.path.join(BRAIN, h["tasks"].replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            items = ledger.parse(ledger.read(ap))["items"]
        except Exception:                                          # noqa: BLE001
            continue
        byid = {x["id"]: x for x in items}
        for it in items:
            who = since = why = None
            if it["kind"] == "question":
                if it["mark"] == "?" and it.get("to") and it["to"] not in mine:
                    who, since, why = _who_word(it["to"], people), it["created"], "their answer"
            elif it["mark"] in (" ", "-") and it.get("owner") in mine:
                blk = str(it.get("blocked") or "")
                refs = re.findall(r"\b[TQ]-\d{4}\b", blk)
                for ref in refs:
                    b = byid.get(ref)
                    if not b or b["mark"] in ("x", "a"):
                        continue
                    tgt = b.get("to") if b["kind"] == "question" else b.get("owner")
                    if tgt and tgt not in mine:
                        who, since = _who_word(tgt, people), b["created"]
                        why = "their answer" if b["kind"] == "question" else "their part"
                        break
                if who is None and blk and not refs:
                    nm = _wait_named(blk, people)
                    if nm:
                        who, since, why = nm, it["created"], "blocked on them"
                if who is None and ledger.is_held(it):
                    nm = _wait_named(it.get("note"), people)
                    if nm:
                        days = re.findall(r"\d{4}-\d{2}-\d{2}", str(it.get("note") or ""))
                        who, since, why = nm, (max(days) if days else it["created"]), "held for them"
            if who:
                rows.append({"project": h["id"], "projectName": ledger_label(h), "ledger": h["tasks"], "id": it["id"],
                             "kind": it["kind"], "text": it["text"], "who": who, "since": since, "why": why,
                             "note": it.get("note") or "", "until": it.get("until"),
                             "days": days_between(since, today) if since else None})
    rows.sort(key=lambda r: (r["since"] or "", r["id"]))
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "today": today, "count": len(rows), "rows": rows}


def waiting_act(which, iid, action, text=""):
    """POST /api/today/waiting/action {ledger, id, action: nudge|drop, text?} -> (code, body). A nudge is a note on the
    item (`nudged <who> (viewer, <day>)`, the old note kept before it); a drop closes it with the reason written first:
    a task is noted and done, a question to someone else is answered `dropped: <reason>`. Both are presses: journaled for
    undo and sent to the session like any other."""
    if action not in ("nudge", "drop"):
        return 400, {"error": "a waiting row is nudged or dropped, nothing else"}
    if PROPOSE:
        return 403, {"error": "a team copy does not change the owner's items: send a request instead"}
    want = str(which or "").replace("\\", "/").strip()
    hit = next((h for h in registry().get("holons", []) if h.get("tasks") and want in (h["id"], h["tasks"])), None)
    if not hit:
        return 400, {"error": "no registered ledger answers to %r" % want}
    rel = hit["tasks"]; path = os.path.join(BRAIN, rel.replace("/", os.sep))
    row = next((r for r in waiting_others_api()["rows"] if r["ledger"] == rel and r["id"] == str(iid or "").strip()), None)
    if row is None:
        return 409, {"error": "that item is not waiting on anyone any more; the page was out of date"}
    day = ledger.today()
    reason = " ".join(str(text or "").split())
    try:
        _p, it = _undo_find(path, row["id"])
        was = (it.get("note") or "").strip()
        before = undo_before(path, row["id"])
        if action == "nudge":
            line = ("%s; " % was if was else "") + "nudged %s (viewer, %s)%s" % (row["who"], day, (": " + reason) if reason else "")
            ledger.apply(path, rel, "note", agent="brain-viewer", id=row["id"], note=line)
            n = undo_record(rel, row["id"], "note", before, "/api/today/waiting/action", "nudged " + row["who"])
            return 200, {"ok": True, "undo": n, "message": "A nudge to %s is noted on it." % row["who"]}
        why = reason or "no longer waited on"
        if row["kind"] == "question":
            ledger.apply(path, rel, "answer", agent="brain-viewer", id=row["id"], text="dropped: %s" % why, by=OWNER)
            n = undo_record(rel, row["id"], "answer", before, "/api/today/waiting/action", "dropped: " + why)
        else:
            line = ("%s; " % was if was else "") + "dropped (viewer, %s): %s" % (day, why)
            ledger.apply(path, rel, "note", agent="brain-viewer", id=row["id"], note=line)
            ledger.apply(path, rel, "done", agent="brain-viewer", id=row["id"])     # done clears a block or a hold with it
            n = undo_record(rel, row["id"], "done", before, "/api/today/waiting/action", "dropped: " + why)
    except ledger.LedgerError as e:
        return 400, {"error": str(e)}
    return 200, {"ok": True, "undo": n, "message": "Dropped, with the reason written on it."}


# ---- the Now band's source (0.71.0, the Today direction rule 1) ----
# The page sends the thread or project the person last opened; this answers which items belong to it, so the page can
# lead with them. A thread's items are the ones its subject file gathers across the ledgers; a project's are its ledger's.
def today_now(thread=None, project=None):
    if thread:
        rel = norm(thread)
        if rel and is_subject_rel(rel):
            try:
                sub = thread_subject(rel)
                rows, _held = thread_gather(sub, thread_ledgers())
            except Exception:                                      # noqa: BLE001 -- no band rather than a broken page
                return None
            return {"kind": "thread", "name": sub["name"], "href": "/thread?subject=" + urllib.parse.quote(rel),
                    "keys": ["%s/%s" % (r["project"], r["id"]) for r in rows]}
        return None
    if project:
        h = next((h for h in registry().get("holons", []) if h.get("tasks") and h["id"] == project), None)
        if not h:
            return None
        ap = os.path.join(BRAIN, h["tasks"].replace("/", os.sep))
        try:
            items = ledger.parse(ledger.read(ap))["items"] if os.path.isfile(ap) else []
        except Exception:                                          # noqa: BLE001
            return None
        return {"kind": "project", "name": ledger_label(h), "href": "/projects?id=" + urllib.parse.quote(h["id"]),
                "keys": ["%s/%s" % (h["id"], x["id"]) for x in items if x["mark"] in (" ", "-", "?")]}
    return None


# ---- what is new since the owner last looked (0.81.0, the Today direction, amendment 2 of 2026-10-14) ----
# "Yours to do" opens with what changed for the owner since the previous visit: an item filed for him, a question of his
# answered, an item noted, one handed to him, one come back to him (reopened, freed by an answer, back from a hold), or
# one otherwise changed. A VISIT is the Today page opening: the page's load POSTs /api/today/visit once, and the times of
# this visit and the one before it are kept per brain in viewer/today-visits.json (the user layer, beside the layouts).
# Two openings inside ten minutes are one visit, so a reload keeps the marks; a re-read after a press GETs, which records
# nothing. With no visit recorded yet, "since" is the start of today.
# The change times come from the log: every write tasks.py makes leaves one line
# `[day HH:MM] [agent] MODIFIED -- <ledger> -- <id> <what>`, read here to the minute. A line the viewer itself wrote is
# the owner's own press and marks nothing, nor does an answer given by the owner. An item the log never names falls back
# to its own dates (created, answered), which mark it only when the whole day is after "since".
TODAY_VISITS_REL = USER_REL + "/today-visits.json"
TODAY_VISIT_GAP = 600                      # seconds: two openings inside ten minutes are one visit
VIEWER_AGENT = "brain-viewer"              # the agent every press in the viewer logs as (tasks.py through ledger.apply)
NEW_KINDS = ("filed", "reassigned", "returned", "answered", "noted", "changed")     # the strongest reason names the mark
_visit_lock = threading.Lock()
_changes = {"sig": None, "idx": {}}
_CHANGE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] \[([^\]]+)\] [A-Z]+ -- (\S+) -- ([TQ]-\d{4}) (.*)$")


def _change_kind(rest):
    """(kind, who) for the words after the id on one tasks.py log line. kind None for a write that takes the item off the
    owner's list (done, blocked, held): those are not news on a list of things to do."""
    r = str(rest or "").strip()
    if r.startswith(("added for ", "asked of ")):
        return "filed", None
    if r.startswith("answered by "):
        return "answered", r[len("answered by "):].split(":", 1)[0].strip()
    if r.startswith("keep in mind:"):
        return "noted", None
    m = re.match(r"reassigned (\S+) → (\S+?):", r)
    if m:
        return "reassigned", m.group(2)
    if r.startswith(("reopened", "back from hold")):
        return "returned", None
    if r.startswith(("done:", "blocked:", "on hold until ")):
        return None, None
    return "changed", None


def _log_changes():
    """{(ledger rel, id): [(stamp 'YYYY-MM-DDTHH:MM', agent, kind, who)]} from context/log.md, cached on its time and size.
    An answer that freed tasks names them on its own line ("(unblocked T-0004)"): each of those came back at that minute."""
    ap = os.path.join(BRAIN, LOG_REL.replace("/", os.sep))
    try:
        st = os.stat(ap)
    except OSError:
        return {}
    sig = (st.st_mtime, st.st_size)
    if _changes["sig"] == sig:
        return _changes["idx"]
    idx = {}
    try:
        with open(ap, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _CHANGE_RE.match(line.rstrip("\r\n"))
                if not m:
                    continue
                day, hm, agent, rel, iid, rest = m.groups()
                stamp, rel = "%sT%s" % (day, hm), rel.replace("\\", "/")
                kind, who = _change_kind(rest)
                idx.setdefault((rel, iid), []).append((stamp, agent, kind, who))
                if kind == "answered":
                    fr = re.search(r"\(unblocked ([^)]*)\)\s*$", rest)
                    for t in re.findall(r"\bT-\d{4}\b", fr.group(1) if fr else ""):
                        idx.setdefault((rel, t), []).append((stamp, agent, "returned", None))
    except OSError:
        return {}
    _changes.update(sig=sig, idx=idx)
    return idx


def today_marks(since):
    """{"<holon>/<id>": {why, at, by?}}: the owner's items with a change after `since` (ISO local time). Open tasks of his,
    open questions to him, and the answered questions he asked or was asked (`why` answered only). `why` is the strongest
    reason (NEW_KINDS order), `at` the newest change ('YYYY-MM-DDTHH:MM')."""
    if not since:
        return {}
    cut, today = str(since)[:16], ledger.today()
    after_day = lambda d: bool(d) and (str(d)[:10] + "T00:00:00") >= str(since)     # the whole day is after `since`
    idx = _log_changes()
    out = {}
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        ap = os.path.join(BRAIN, h["tasks"].replace("/", os.sep))
        if not os.path.isfile(ap):
            continue
        try:
            items = ledger.parse(ledger.read(ap))["items"]
        except Exception:                                          # noqa: BLE001 -- a ledger that will not parse marks nothing
            continue
        rel = h["tasks"].replace("\\", "/")
        for it in items:
            mark, to_me = it["mark"], (it.get("to") or OWNER) == OWNER
            if it["kind"] == "task":
                if mark != " " or it.get("owner") != OWNER:
                    continue
            elif mark == "?":
                if not to_me:
                    continue
            elif mark == "a":
                if not (to_me or it.get("owner") == OWNER):
                    continue
            else:
                continue
            evs, rows = [], idx.get((rel, it["id"]))
            for stamp, agent, kind, who in rows or ():
                if not kind or agent == VIEWER_AGENT or stamp <= cut:
                    continue
                if kind == "answered" and str(who or "").lower() == OWNER.lower():
                    continue                                       # his own answer, written down for him
                if kind == "reassigned" and who != OWNER:
                    continue
                evs.append((kind, stamp, who))
            if not rows:                                           # a line written by hand: its own dates, by the day
                if after_day(it.get("created")):
                    evs.append(("filed", it["created"] + "T00:00", None))
                if mark == "a" and after_day(it.get("answered")):
                    evs.append(("answered", it["answered"] + "T00:00", None))
            u = it.get("until")
            if it["kind"] == "task" and u and u <= today and after_day(u):
                evs.append(("returned", u + "T00:00", None))       # a hold that ended since: back by the clock
            if mark == "a":
                evs = [e for e in evs if e[0] == "answered"]
            if not evs:
                continue
            row = {"why": min(evs, key=lambda e: NEW_KINDS.index(e[0]))[0], "at": max(e[1] for e in evs)}
            by = next((e[2] for e in evs if e[0] == "answered" and e[2]), None)
            if by:
                row["by"] = by
            out["%s/%s" % (h["id"], it["id"])] = row
    return out


def _visit_path():
    return os.path.join(BRAIN, TODAY_VISITS_REL.replace("/", os.sep))


TODAY_PICK_REL = "context/today-pick.json"   # agent-written by skills/today-pick/pick.py (0.85.0)


def today_pick_api():
    """GET /api/today/pick (0.85.0, the Today direction's amendment 3 rule 1): the one to three items a session or the
    evening run picked for the top of Today, each with why. `current` is true only when the pick is for today (`for`,
    else the day it was written) and holds an item; otherwise the page ranks its own. The items are passed through as written (holon, id, why), at most
    three, an item with no holon or id dropped; the page matches them to the owner's open items, so a closed one is
    simply not drawn. Nothing is written."""
    ap = os.path.join(BRAIN, TODAY_PICK_REL.replace("/", os.sep))
    out = {"file": TODAY_PICK_REL, "exists": os.path.isfile(ap), "today": ledger.today(), "writtenAt": None, "by": None,
           "current": False, "items": [], "writtenBy": "skills/today-pick/pick.py"}
    if not out["exists"]:
        return out
    d = _json_read(ap)
    if not isinstance(d, dict):
        out["error"] = "%s could not be read" % TODAY_PICK_REL
        return out
    items = []
    for it in d.get("items") or []:
        if isinstance(it, dict) and it.get("holon") and it.get("id"):
            items.append({"holon": str(it["holon"]), "id": str(it["id"]), "why": str(it.get("why") or "")})
    # `for` is the day the pick is for: the day it was written, or the next morning when the evening run wrote it
    day = str(d.get("for") or d.get("writtenAt") or "")[:10]
    out.update(writtenAt=d.get("writtenAt"), by=d.get("by"), items=items[:3], **{"for": day or None})
    out["current"] = bool(items) and day == out["today"]
    return out


def today_visit(record=False, now=None):
    """GET /api/today/visit (record False) and POST (record True) -> the visit, the time "since", and the marks.
    {since, sinceKind: visit|today, current, previous, recorded, gapMinutes, marks, count}. A POST more than ten minutes
    after the last opening starts a new visit and the old one becomes `previous`; inside ten minutes it only moves the
    current visit's `last`, so `since` (the previous visit's last opening) does not move."""
    now = now or dt.datetime.now()
    stamp = now.isoformat(timespec="seconds")
    with _visit_lock:
        ap = _visit_path()
        st = _json_read(ap) or {}
        cur = st.get("current") if isinstance(st.get("current"), dict) else None
        prev = st.get("previous") if isinstance(st.get("previous"), dict) else None
        if record:
            same = False
            if cur and cur.get("last"):
                try:
                    gap = (now - dt.datetime.fromisoformat(str(cur["last"]))).total_seconds()
                    same = -TODAY_VISIT_GAP < gap < TODAY_VISIT_GAP
                except ValueError:
                    same = False
            if same:
                cur = dict(cur, last=stamp, openings=int(cur.get("openings") or 1) + 1)
            else:
                prev, cur = cur, {"start": stamp, "last": stamp, "openings": 1}
            try:
                _json_write(ap, {"_about": "The Today page's visits in this brain, written by the page's load "
                                           "(POST /api/today/visit). Two openings inside ten minutes are one visit; "
                                           "what changed after the previous visit's last opening is marked new.",
                                 "current": cur, "previous": prev})
            except OSError as e:
                return {"error": "the visit could not be kept: %s" % e}
    since = str(prev.get("last") or prev.get("start") or "") if prev else ""
    kind = "visit" if since else "today"
    if not since:
        since = ledger.today() + "T00:00:00"
    marks = today_marks(since)
    return {"_servedAt": stamp, "since": since, "sinceKind": kind, "current": cur, "previous": prev, "recorded": bool(record),
            "gapMinutes": TODAY_VISIT_GAP // 60, "marks": marks, "count": len(marks)}



# ---- Changed since you last looked (0.91.0, 2026-10-22) ----
# The morning after a night's work shipped a viewer release and the overnight runs wrote their reports, none of it had a
# way in from Today, so it stayed invisible until the owner went looking ("this is an important thing that might happen
# again"). GET /api/whats-new gives Today's band and the header what they need: the viewer's VERSION, the version this
# person last marked seen (viewer/whats-new-seen.json, the user layer beside today-visits.json), the newest two entries of
# the viewer's what's-new page read from its markdown, and the notes the development, night and engineer runs wrote since
# the previous Today visit (the same "since" the From band and New since you last looked read), a delivery note first.
# POST /api/whats-new/seen keeps VERSION as seen, with the time. A team copy answers too: the page is the same file where
# the copy holds it, and the runs' folders do not ship, so its overnight list is always empty.
WHATS_NEW_SEEN_REL = USER_REL + "/whats-new-seen.json"
VIEWER_WHATS_NEW_REL = "brain-viewer-holon/brain-viewer-whats-new.md"
# (folder, kind): the development run's delivery note (the first row) leads, then every note by its date, newest first
OVERNIGHT_DIRS = (("deliverables/brain-dev", "delivery"), ("deliverables/night-agent", "audit"),
                  ("deliverables/brain-engineer", "engineer"))
WN_ENTRIES = 2
WN_LINES = 6
OVERNIGHT_CAP = 5
_WNV_HEAD_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})(?:\s*\([^)]*\))?\s*(?:[-–—:]\s*)?(.*?)\s*$")
_WNV_VER_RE = re.compile(r"\s*\((\d+\.\d+\.\d+)\)\s*$")
_WNV_WHERE_RE = re.compile(r"^\**\s*where to see it\s*:?\s*\**\s*:?\s*", re.I)
_WNV_LEAD_RE = re.compile(r"^\*\*(.+?)\*\*")
_FILE_DAY_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_wn_seen_lock = threading.Lock()


def md_plain(s):
    """One line of markdown as the words it shows: links by their words, a wikilink by its label (else its file's name),
    no emphasis marks or backticks, one space between words."""
    s = str(s or "")
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[\[([^|\]]+)\|([^\]]*)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", lambda m: m.group(1).split("#")[0].rsplit("/", 1)[-1].rsplit(".", 1)[0], s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<![\w_])_(?!\s)([^_]+?)_(?![\w_])", r"\1", s)
    s = re.sub(r"<!--.*?-->", "", s)
    return " ".join(s.split())


def _wn_lead(body):
    """A line's opening sentence for the short list: its bold lead when that is a sentence ("**In a copy** the..." is
    not), else its first sentence when the line runs long; None when the whole line is short enough to stand."""
    lm = _WNV_LEAD_RE.match(body)
    if lm and lm.group(1).rstrip().endswith((".", "!", "?")):
        return md_plain(lm.group(1))
    plain = md_plain(body)
    if len(plain) <= 160:
        return None
    m = re.search(r"[.!?](?=\s+[A-Z])", plain)
    return plain[:m.end()] if m and m.end() < len(plain) else None


def viewer_whats_new_entries(n=WN_ENTRIES):
    """The newest n entries of the viewer's what's-new page: [{date, title, version, lines, leads, more, where}]. An entry
    is a `## <date> - <title> (<x.y.z>)` heading and what follows it up to the next heading or rule; its lines are its
    top-level bullets as plain words, at most six, `more` counting the rest; `leads` is each line's bold opening sentence
    (None when it has none); `where` is its "Where to see it" line, which is not one of the lines."""
    ap = os.path.join(BRAIN, VIEWER_WHATS_NEW_REL.replace("/", os.sep))
    try:
        with open(ap, "r", encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
    except OSError:
        return []
    out, cur = [], None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            if cur:
                out.append(cur)
                cur = None
                if len(out) >= n:
                    break
            m = _WNV_HEAD_RE.match(line)
            if not m:
                continue
            title, ver = m.group(2), None
            vm = _WNV_VER_RE.search(title)
            if vm:
                ver, title = vm.group(1), title[:vm.start()].rstrip()
            cur = {"date": m.group(1), "title": md_plain(title), "version": ver, "lines": [], "leads": [], "more": 0, "where": ""}
            continue
        if cur is None:
            continue
        if line.strip() == "---" or line.startswith("# "):
            out.append(cur)
            cur = None
            if len(out) >= n:
                break
            continue
        if not line.startswith(("- ", "* ")):
            continue                                   # the Why line, a sub-bullet, a blank: not one of the entry's lines
        body = line[2:].strip()
        wm = _WNV_WHERE_RE.match(body)
        if wm:
            cur["where"] = md_plain(body[wm.end():])
            continue
        if len(cur["lines"]) >= WN_LINES:
            cur["more"] += 1
            continue
        cur["lines"].append(md_plain(body))
        cur["leads"].append(_wn_lead(body))
    if cur and len(out) < n:
        out.append(cur)
    return out[:n]


def whats_new_seen():
    """{version, at} the person last marked seen; empty strings when nothing is kept yet."""
    d = _json_read(os.path.join(BRAIN, WHATS_NEW_SEEN_REL.replace("/", os.sep))) or {}
    return {"version": str(d.get("version") or ""), "at": str(d.get("at") or "")}


def whats_new_state():
    """What every page's header needs (injected as window.BV_WHATSNEW): the version, the one seen, the page to open."""
    has = os.path.isfile(os.path.join(BRAIN, VIEWER_WHATS_NEW_REL.replace("/", os.sep)))
    return {"version": VERSION, "seen": whats_new_seen()["version"], "path": VIEWER_WHATS_NEW_REL if has else None}


def _file_title(ap, fallback):
    try:
        with open(ap, "r", encoding="utf-8-sig", errors="replace") as f:
            for k, line in enumerate(f):
                if line.startswith("# "):
                    return md_plain(line[2:]) or fallback
                if k > 40:
                    break
    except OSError:
        pass
    return fallback


def overnight_files(since):
    """The notes the runs wrote since `since` (a local ISO time): ([{title, path, when, kind}], how many more), the
    development run's delivery notes first, then newest first, at most five. A file counts by the date in its name: a day
    after since's, or since's own day and written after since. A team copy holds none of these folders: always empty."""
    if PROPOSE or not since:
        return [], 0
    day, rows = str(since)[:10], []
    for k, (rel, kind) in enumerate(OVERNIGHT_DIRS):
        folder = os.path.join(BRAIN, rel.replace("/", os.sep))
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for fn in names:
            m = _FILE_DAY_RE.search(fn)
            if not m or not fn.lower().endswith(".md"):
                continue
            ap = os.path.join(folder, fn)
            try:
                mt = dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")
            except OSError:
                continue
            fday = m.group(1)
            if fday < day or (fday == day and mt <= since):
                continue
            rows.append((k, fday, mt, {"title": _file_title(ap, fn[:-3]), "path": rel + "/" + fn, "when": mt, "kind": kind}))
    rows.sort(key=lambda r: (r[0] == 0, r[1], r[2]), reverse=True)     # a delivery note first, then the newest
    return [r[3] for r in rows[:OVERNIGHT_CAP]], max(0, len(rows) - OVERNIGHT_CAP)


def whats_new_api():
    """GET /api/whats-new: {version, seen, seenAt, seenToday, path, entries, overnight, overnightMore, since}."""
    seen = whats_new_seen()
    since = today_visit(record=False).get("since") or ""
    files, more = overnight_files(since)
    st = whats_new_state()
    return {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "version": VERSION, "seen": seen["version"],
            "seenAt": seen["at"] or None, "seenToday": bool(seen["at"]) and seen["at"][:10] == ledger.today(),
            "path": st["path"], "entries": viewer_whats_new_entries() if st["path"] else [], "since": since,
            "overnight": files, "overnightMore": more}


def whats_new_mark_seen():
    """POST /api/whats-new/seen: the running VERSION is kept as seen, with the time; answers as the GET does."""
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    with _wn_seen_lock:
        try:
            _json_write(os.path.join(BRAIN, WHATS_NEW_SEEN_REL.replace("/", os.sep)),
                        {"_about": "The viewer version this person last marked seen on Today's Changed since you last "
                                   "looked band (POST /api/whats-new/seen). The header's dot beside what's new shows "
                                   "while the running version is another one.", "version": VERSION, "at": stamp})
        except OSError as e:
            return 500, {"error": "the seen mark could not be kept: %s" % e}
    return 200, dict(whats_new_api(), ok=True)

# ---- Clear answered questions: the question sweep, run from a press (0.60.0, 2026-10-05; renamed 0.60.1) ----
# The owner asked for a press that checks whether any question or task waiting on him has been answered or cleared
# somewhere else since it was asked. The work is skills/question-sweep/sweep.py, its own component; this server only
# starts it (detached, so it outlives a viewer restart), reads the status file it writes into the user layer, and
# refuses a second run while one is going. With no runner in this copy, every route says so plainly.
SWEEP_SCRIPT = os.path.join(CODE, "skills", "question-sweep", "sweep.py")
SWEEP_DIR_REL = USER_REL + "/sweep"
_sweep = {"proc": None, "startedAt": None, "scope": None}
_sweep_lock = threading.Lock()


def _sweep_paths():
    d = os.path.join(BRAIN, SWEEP_DIR_REL.replace("/", os.sep))
    return d, os.path.join(d, "status.json"), os.path.join(d, "last-run.log")


def _pid_alive(pid):
    """Is a process with this id running? On Windows asked of the kernel (os.kill there TERMINATES, it does not probe)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5        # access denied: it exists, it is just not ours
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259          # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _tail(ap, n=5):
    try:
        with open(ap, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 16384))
            data = f.read().decode("utf-8", "replace")
    except OSError:
        return []
    return [l.rstrip("\r") for l in data.split("\n") if l.strip()][-n:]


def _hhmm(iso):
    m = re.search(r"(?:T| )(\d{2}:\d{2})", str(iso or ""))
    return m.group(1) if m else str(iso or "an unknown time")


def sweep_status():
    """GET /api/sweep/status: the runner's status file as it stands, plus the last five lines of its output, with what
    this server knows laid over it -- a run it started that has not written its file yet reads as running, and one that
    ended without saying how reads as failed with its exit code. {state: idle} when no check has run here;
    {state: missing} when the runner is not in this copy."""
    if not os.path.isfile(SWEEP_SCRIPT):
        return {"state": "missing", "error": "the check is not installed yet: skills/question-sweep/sweep.py is not in this copy"}
    d, sp, lp = _sweep_paths()
    st = None
    if os.path.isfile(sp):
        for _ in range(3):                    # the runner may be mid-write; it swaps the file, but be patient once or twice
            st = _json_read(sp)
            if st is not None:
                break
            time.sleep(0.1)
        if st is None:
            st = {"state": "unknown", "error": "the check's status file could not be read"}
    else:
        st = {"state": "idle"}
    st = dict(st)
    proc = _sweep["proc"]
    fpid = str(st.get("pid") or "")
    ours = proc is not None and fpid == str(proc.pid)
    # a file written by a LATER run this server did not start (one started from the command line) is that run's word
    newer = proc is not None and not ours and str(st.get("startedAt") or "")[:19] >= str(_sweep["startedAt"] or "")[:19]
    if proc is not None and not newer:
        rc = proc.poll()
        if rc is None:
            if st.get("state") != "running" or not ours:
                st.update(state="running", startedAt=_sweep["startedAt"], scope=_sweep["scope"], pid=proc.pid)
        elif not ours or st.get("state") in ("running", "unknown", "idle"):
            st.update(state="refused" if rc == 2 else "failed", pid=proc.pid, startedAt=_sweep["startedAt"], scope=_sweep["scope"],
                      error=("the check stopped before it wrote how it ended (exit %d); its last lines are below" % rc))
    elif st.get("state") == "running" and ((fpid and not _pid_alive(fpid)) or
                                          (not fpid and os.path.isfile(sp) and time.time() - os.path.getmtime(sp) > 3 * 3600)):
        st.update(state="failed", error="the last check stopped without finishing: its process is gone")
    st["log"] = _tail(lp)
    # which items a sweep has been through, by "<project>/<id>" (0.65.0): Today keeps an intake item older than fourteen
    # days out of its run-through until it shows up here (skills/question-sweep/sweep.py record_seen)
    seen = _json_read(os.path.join(d, "seen.json"))
    st["seen"] = seen if isinstance(seen, dict) else {}
    rep = norm(str(st.get("report") or ""))
    if rep:
        st["reportHref"] = "/reader?path=" + urllib.parse.quote(rep)
    return st


def sweep_run(project=None):
    """POST /api/sweep/run -> (code, body). One run at a time: refused while this server's own run is alive or the status
    file says running with a live process behind it. The runner is started detached (its own process group, no window),
    in the brain root, BRAIN_ROOT set, its output to viewer/sweep/last-run.log."""
    if PROPOSE:
        return 403, {"ok": False, "error": "a team copy does not run the owner's checks"}
    if not os.path.isfile(SWEEP_SCRIPT):
        return 501, {"ok": False, "state": "missing", "error": "the check is not installed yet: skills/question-sweep/sweep.py is not in this copy"}
    proj = str(project or "").strip() or None
    if proj and not any(h.get("id") == proj and h.get("tasks") for h in registry().get("holons", [])):
        return 400, {"ok": False, "error": "no registered ledger is called %r" % proj}
    with _sweep_lock:
        st = sweep_status()
        if st.get("state") == "running":
            return 409, {"ok": False, "error": "a check is already running since %s" % _hhmm(st.get("startedAt"))}
        d, sp, lp = _sweep_paths()
        os.makedirs(d, exist_ok=True)
        args = [sys.executable, "-u", SWEEP_SCRIPT] + (["--project", proj] if proj else [])
        kw = {"creationflags": 0x00000200 | 0x08000000} if os.name == "nt" else {"start_new_session": True}   # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        started = dt.datetime.now().isoformat(timespec="seconds")
        try:
            with open(lp, "w", encoding="utf-8") as logf:
                proc = subprocess.Popen(args, cwd=BRAIN, stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.STDOUT,
                                        env=dict(os.environ, BRAIN_ROOT=BRAIN, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8"),
                                        close_fds=True, **kw)
        except Exception as e:                                     # noqa: BLE001
            return 500, {"ok": False, "error": "the check could not start: %s" % e}
        _sweep.update(proc=proc, startedAt=started, scope=proj or "every ledger")
    return 200, {"ok": True, "startedAt": started, "pid": proc.pid, "scope": proj or "every ledger"}



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
PENDING_NOTE = "Approving makes it a task in the app; rejecting removes it."
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


def pending_approve_all(conv):
    """POST /api/pending/approve-all {conversation}: every item the app holds for review on that one call, approved
    through pending_act -- the same rehearse-then-write route a single press uses, one item at a time -- and it STOPS at
    the first refusal, saying how far it got (0.65.0: the run-through on Today offers it as one press per call). The
    items are read from the app again first, never from the page, so the press approves what is waiting now."""
    cid = str(conv or "").strip()
    if not cid:
        return 400, {"error": "no call named"}
    if PROPOSE:
        return 403, {"error": "a team copy does not write to the PF App"}
    row = pending_api(force=True)
    if row.get("error"):
        return 502, {"error": "the app could not be read: %s" % row["error"]}
    g = next((c for c in row.get("conversations") or [] if c["id"] == cid), None)
    if not g:
        return 404, {"error": "the app holds nothing for review on that call any more"}
    ids = [i["id"] for i in g["items"] if i.get("id")]
    done = 0
    for iid in ids:
        code, out = pending_act(iid, "approve")
        if code >= 300:
            return code, {"ok": False, "done": done, "total": len(ids), "conversation": g["title"],
                          "error": "stopped after %d of %d: %s" % (done, len(ids), out.get("error") or code)}
        done += 1
    return 200, {"ok": True, "done": done, "total": len(ids), "conversation": g["title"],
                 "message": "%d approved in the app" % done}


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
            groups[h["id"]] = {"project": h["id"], "name": ledger_label(h), "path": h["tasks"], "items": []}
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
                           "note": r.get("note"), "steps": r.get("steps") or [], "milestone": r.get("milestone"), "tags": r.get("tags") or [],
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
        before = undo_before(path, it["id"])     # 0.71.0: the press can be undone for the rest of the day
        ledger.apply(path, rel, action, agent="brain-viewer", id=it["id"],
                     note="%s in the viewer, %s" % (action, ledger.today()),
                     until=None)                 # no date: the tool's own three days (T-0108)
        n = undo_record(rel, it["id"], action, before, "/api/today/tasks/action")
    except ledger.LedgerError as e:
        return 400, {"error": str(e)}
    return 200, {"ok": True, "id": it["id"], "ledger": rel, "project": hit["id"], "action": action, "undo": n,
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


# ---- a call, or a block (0.59.1, 2026-10-05) ----
# The owner, 10/05, after the recap reported a therapy appointment as having no prep: "therapy should never be assumed
# to have a prep." An event is a CALL only when someone besides the owner is on the invite and its title names none of
# the personal blocks in the `no_prep_titles` setting. Anything else is a block: it still shows on the calendar with its
# time and title, and nothing about a prep (none matched, no "no prep" line, no write button; auto_prep passes it in
# silence).
NO_PREP_TITLES = ["therapy"]


def is_call(title, who):
    """True when the event is a call that can carry a prep: a person other than the owner on it, and a title that is
    not a personal block (`no_prep_titles` in the settings, matched as a lowercase substring)."""
    t = str(title or "").lower()
    words = SETTINGS.get("no_prep_titles", NO_PREP_TITLES)
    if any(str(w).strip().lower() in t for w in (words or []) if str(w).strip()):
        return False
    return any(not w.get("self") for w in who or [])


def group_members():
    """{group id -> set of member slugs} from the declared call threads, which the prep matcher needs to know that a
    call whose attendees are exactly a thread's members is that thread's call."""
    return {str(g.get("id") or ""): set(str(m) for m in (g.get("members") or []))
            for g in (load_groups().get("groups") or []) if g.get("id")}


def name_slug(name):
    """An attendee's name as a prep file key: first-last, lowercase, hyphens ("Sam Rivera" -> "sam-rivera")."""
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
    matched prep's people is dropped for that event (2026-09-21 -- the team thread, two co-founders, is a subset of the
    four-way call's attendees, so the four-way was matching the team prep as well as its own).

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
    day it was first set on; a team call moved from 9/28 to 9/29 is the case."""
    out = list(by_day.get(day) or [])
    orig = str((e or {}).get("originalDate") or "")[:10]
    if orig and orig != day:
        out += [p for p in (by_day.get(orig) or []) if p not in out]
    return out


def prep_rows(hits):
    """A matched prep as the pages read it: where it is, which call it is keyed to, and what it says it is for."""
    # `state` (0.65.0): ready, skeleton or held, so Today draws a skeleton as a skeleton rather than "prep ready"
    return [{"path": p["path"], "key": p["key"], "call": p["call"], "purpose": p["purpose"], "state": prep_state(p["path"])} for p in hits]


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
    by_day = {}
    for p in preps():
        by_day.setdefault(p["call"], []).append(p)
    gmembers = group_members()
    if raw is None:
        row["prepCalls"] = prep_only_calls(today, by_day.get(today) or [], [], gmembers)
        row["prepOnly"] = len(row["prepCalls"])
        return row
    for e in raw:
        if not isinstance(e, dict):
            continue
        who = event_slugs([a.get("name") if isinstance(a, dict) else a for a in (e.get("attendees") or [])])
        call = is_call(e.get("title"), who)
        hits = preps_for_event(event_match_keys(who), event_day_preps(e, row["for"] or today, by_day), gmembers) if call else []
        ev = {"title": str(e.get("title") or "(untitled)"), "start": str(e.get("start") or ""),
              "end": str(e.get("end") or ""), "organizer": str(e.get("organizer") or "") or None,
              "people": who, "noCard": [w["name"] for w in who if not w["slug"] and not w["self"]],
              "call": call, "preps": prep_rows(hits)}
        ev.update(event_links(e))
        row["events"].append(ev)
    row["events"].sort(key=lambda e: (e["start"], e["title"]))
    row["count"] = len(row["events"])
    row["calls"] = sum(1 for e in row["events"] if e["call"])
    row["withPrep"] = sum(1 for e in row["events"] if e["preps"])
    # 0.70.0 (the navigation direction, rule 4, viewer T-0318): a draft prep dated today with no calendar event is a call
    # too, drawn apart in `prepCalls` so the readers that place events on a clock never meet one with no time
    row["prepCalls"] = prep_only_calls(today, by_day.get(today) or [], row["events"] if (row["for"] or today) == today else [], gmembers)
    row["prepOnly"] = len(row["prepCalls"])
    # 0.85.0 (amendment 3 rule 2): a call already held carries what came out of it, and when no call is left today the
    # next one on the week file is named with its prep, so Today's lead card is the call as on the day
    if not row["stale"]:
        call_outcomes(row["events"], today)
        row["nextLater"] = next_later_call(today, by_day, gmembers)
    return row


def call_outcomes(events, today, now=None):
    """0.85.0: each call of today that has ended gets `outcome` when a transcript that landed today is its recording:
    {title, transcript, report, path, kind: report | transcript}, `path` being what the press opens (the intake report
    when one exists, else the transcript). A transcript is the call's when its file name carries the first names of the
    call's other people (two of them, or the one when only one other person was on it) and it landed after the call
    began. Derived at read time; nothing is written."""
    now = now or dt.datetime.now()
    try:
        landed = landed_api(today).get("landed") or []
    except Exception:                                         # noqa: BLE001
        landed = []
    hm = lambda s: (lambda m: int(m.group(1)) * 60 + int(m.group(2)) if m else None)(re.search(r"T(\d{2}):(\d{2})", str(s or "")))
    mins = now.hour * 60 + now.minute
    for e in events:
        e.pop("outcome", None)
        en, st = hm(e.get("end")), hm(e.get("start"))
        if not e.get("call") or en is None or en > mins or str(e.get("start") or "")[:10] != today:
            continue
        firsts = set()
        for w in e.get("people") or []:
            if w.get("self"):
                continue
            f = re.split(r"[^a-z0-9]+", str(w.get("name") or "").strip().lower())
            if f and f[0] and len(f[0]) >= 3:
                firsts.add(f[0])
        if not firsts:
            continue
        need = min(2, len(firsts))
        best = None
        for r in landed:
            words = set(re.split(r"[^a-z0-9]+", str(r.get("stem") or "").lower()))
            hit = len(firsts & words)
            at = str(r.get("mtime") or "")
            if hit < need or (st is not None and hm(at.replace(" ", "T")) is not None and hm(at.replace(" ", "T")) < st):
                continue
            if best is None or (hit, at) > best[0]:
                best = ((hit, at), r)
        if not best:
            continue
        r = best[1]
        files = sorted(r.get("files") or [], key=lambda f: (f.get("ext") not in ("txt", "md"), f.get("path")))
        tr = files[0]["path"] if files else None
        e["outcome"] = {"title": r.get("title") or r.get("stem"), "transcript": tr, "report": r.get("report"),
                        "path": r.get("report") or tr, "kind": "report" if r.get("report") else "transcript"}
    return events


def next_later_call(today, by_day, gmembers):
    """0.85.0: the first call after today on the week file (context/week-calendar.json, the recap's and the evening run's
    seven-day read), with its people and its prep, or None. A block is not a call (is_call)."""
    wk, _ = read_calendar_file(CALENDAR_WEEK_REL)
    if not isinstance(wk, dict):
        return None
    evs = []
    for e in wk.get("events") or []:
        if not isinstance(e, dict):
            continue
        d = str(e.get("date") or "")[:10] or str(e.get("start") or "")[:10]
        if d > today and "T" in str(e.get("start") or ""):
            evs.append((str(e.get("start")), d, e))
    for start, d, e in sorted(evs, key=lambda x: x[0]):
        who = event_slugs([a.get("name") if isinstance(a, dict) else a for a in (e.get("attendees") or [])])
        if not is_call(e.get("title"), who):
            continue
        hits = preps_for_event(event_match_keys(who), event_day_preps(e, d, by_day), gmembers)
        ev = {"title": str(e.get("title") or "(untitled)"), "start": start, "end": str(e.get("end") or ""), "date": d,
              "organizer": str(e.get("organizer") or "") or None, "people": who, "call": True, "preps": prep_rows(hits)}
        ev.update(event_links(e))
        return ev
    return None


def prep_only_calls(today, day_preps, events, gmembers):
    """0.70.0 (rule 4): the calls a prep says are on today that no calendar event carries. A prep counts when its
    frontmatter `call:` is today and its `status:` is draft; it is left out when a calendar event already holds it, or
    when its people are all on one of today's calendar calls (the most-specific matcher may have dropped it for a closer
    prep, and the same people on the same day are the same call). Derived at read time; nothing is written to the
    calendar files. Its time is left to the owner: `start` and `end` stay empty and `notOnCalendar` says why."""
    held = set()
    on_cal = []
    for e in events or []:
        for pr in e.get("preps") or []:
            held.add(pr.get("path"))
        if e.get("call"):
            on_cal.append(event_match_keys(e.get("people") or []))
    out = []
    for p in day_preps:
        if p.get("call") != today or str(p.get("status") or "").strip().lower() != "draft" or p["path"] in held:
            continue
        k = p["key"]
        members = set((gmembers or {}).get(k) or (k.split("+") if "+" in k else [k])) | set(p.get("participants") or [])
        if any(members and members <= keys for keys in on_cal):
            continue
        who = []
        for m in sorted(members):
            rel, ap = card_path(m)
            who.append({"name": card_display_name(m), "slug": m if ap else None, "card": rel if ap else None, "self": False})
        title = p.get("purpose") or ""
        names = ", ".join(w["name"] for w in who) or k
        out.append({"title": "Call with %s" % names, "start": "", "end": "", "organizer": None, "people": who,
                    "noCard": [w["name"] for w in who if not w["slug"]], "call": True, "notOnCalendar": True,
                    "purpose": clip(title, 140), "preps": prep_rows([p]), "join": None, "calendarLink": None})
    return out


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
                    "decide" if bare.startswith("decide before") else
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
           "questions": [], "points": [], "notes": None, "decide": None,
           "format": fm.get("format") or ("v3" if any(s["kind"] == "questions" for s in sections) else "v2")}
    for s in sections:
        md_text = "\n".join(l for _, l in s["lines"]).strip()
        row = {"title": s["title"], "kind": s["kind"], "line": s["start"]}
        if s["kind"] == "due":
            out["due"] = {"title": s["title"], "md": md_text}
            continue
        if s["kind"] == "decide":                 # 0.67.0: Decide before, drawn first on the call screen
            out["decide"] = {"title": s["title"], "md": md_text}
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
    if not is_call(ev.get("title"), ev.get("people") or []):
        raise ValueError("this is a block on the calendar, not a call; it never carries a prep")
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
                      "intro": parsed["intro"], "due": parsed["due"], "decide": parsed["decide"], "questions": parsed["questions"],
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


# ---- the survey page (0.78.0, 2026-10-13) ----
# The owner, answering on 10/13 the question that carried a survey, asked for what he had expected to exist already: a
# question of this kind should take him to a page he can press through, and its kind should be a tag on the ledger item
# so that page is one press from the card. Until then a survey was a markdown file edited line by line in the Reader.
# So a question tagged `survey` draws one press, Take the survey (BV.survey in viewer-common.js, on Today, the thread
# page and the workspace), which opens /survey?path=<the item's first linked .md>&q=<ledger>:<id>. The page reads
# GET /api/survey, writes each press and each note back at once through POST /api/survey/answer, and its Finish
# answers that question through PUT /api/tasks like any other answer.
# THE FILE IS THE RECORD. The answers live on the survey's own Answer lines: the file the Reader opens, and the file
# skills/patterns/patterns.py reads a survey's answers from (its item heading and its Answer rule are the ones used here).
# The shape, read generically so that any survey written in it works:
#     # <title>
#     > <the intro: a blockquote, as many lines as it takes>
#     <a line giving the default for an item left blank>
#     ### <N>. <title>
#     <the statement: a paragraph or more>
#     Options: <a> · <b> · <c>        (an item with no Options line is answered in its own words, the note alone)
#     Answer: <choice>  |  Answer: <choice>. <note>  |  Answer: <note>  |  Answer:
# A heading between items that is not an item names the items under it (`section`). An answer a hand ran onto the lines
# under its Answer line is read as one, as patterns.py reads it, and written back as one line.
# A WRITE TOUCHES ONE ITEM'S ANSWER LINE AND NOTHING ELSE, through the Reader's own steps (_put_api_file): writable() is
# the gate, the file's line endings and any byte-order mark are kept byte for byte, a team copy proposes the change
# instead of writing it, and the write is logged: one MODIFIED line per survey per ten minutes, as the call screen
# logs its ticks, so a survey pressed through is one line in the log, not twenty-four.
SURVEY_ITEM_RE = re.compile(r"^###\s+(\d+)\.\s*(.*)$")         # an item's heading, read as patterns.py reads it
SURVEY_HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")
SURVEY_OPTIONS_RE = re.compile(r"^options\s*:\s*(.*)$", re.I)
SURVEY_ANSWER_RE = re.compile(r"^answer\s*:(.*)$", re.I)
SURVEY_RULE_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
SURVEY_DEFAULT_RE = re.compile(r"^default\b|\bleft blank\b|\bif blank\b", re.I)
SURVEY_NOTE_MAX = 2000                # characters: the note box is one line
SURVEY_LOG_EVERY = 600                # seconds: one MODIFIED line per survey per ten minutes
_survey_logged = {}
_survey_lock = threading.Lock()       # a press and a note leaving its box can land together: one read-and-write at a time


def survey_abs(rel, write=False):
    """(absolute path, brain-relative path, None) for a survey file the page may read (with write, write), else
    (None, None, the reason). A .md inside the brain only: no '..', no drive, no leading slash, nothing in archive/ or a
    dot folder, never a key file, its real location inside the brain; a write also passes the Reader's gate, writable()."""
    r = norm(rel)
    if not r:
        return None, None, "not a path inside the brain"
    if not r.lower().endswith(".md"):
        return None, None, "a survey is a markdown file (.md)"
    ap = write_abs(r) if write else read_abs(r)
    if not ap:
        return None, None, ("not a file the viewer writes: %s" % reader_write_rule(r)[1]) if write else "not a file the viewer reads"
    root = os.path.normcase(os.path.realpath(BRAIN)).rstrip(os.sep) + os.sep
    if not os.path.normcase(os.path.realpath(ap)).startswith(root):
        return None, None, "not a path inside the brain"
    return ap, r, None


def survey_options(words):
    """`agree · partly · no` -> ["agree", "partly", "no"]: split on the middle dot, a bullet or a bar, else on commas,
    'or' and spaced slashes; each option without bold, backticks or a closing stop."""
    words = (words or "").strip()
    if not words:
        return []
    parts = (re.split(r"\s*[·•|]\s*", words) if re.search(r"[·•|]", words)
             else re.split(r"\s*,\s*(?:or\s+)?|\s+or\s+|\s+/\s+", words))
    out = []
    for p in parts:
        p = p.strip().strip("*_`").strip().rstrip(".;:").strip()
        if p and p.lower() not in {o.lower() for o in out}:
            out.append(p)
    return out


def survey_read_answer(words, options):
    """An Answer line's words -> (choice, note). The choice is one of the item's options when the words open with it, on
    its own or followed by . , ; : or a spaced dash and then the note; otherwise there is no choice and the words are the
    note. The option comes back in the Options line's own spelling, whatever case the Answer line used."""
    a = " ".join(str(words or "").split())
    if not a:
        return "", ""
    m = re.match(r"^\*\*([^*]+)\*\*(.*)$", a)          # a choice a hand wrote in bold, the way the intro writes the options
    if m:
        a = m.group(1).strip() + m.group(2)
    for o in sorted(options, key=len, reverse=True):
        if a.lower() == o.lower():
            return o, ""
        if a.lower().startswith(o.lower()):
            m = re.match(r"^(?:\s*[.,;:]|\s+[-–—])\s*(.*)$", a[len(o):])
            if m:
                return o, m.group(1).strip()
    return "", a


def survey_parse(text):
    """A survey file's text -> {title, intro, default, items}. Each item: n, title, section, statement, options, choice,
    note, answer (the words of its Answer line, run-on lines joined) and at / span: the 0-based index of its Answer line
    in text.split("\\n") and how many lines the answer takes (None and 0 for an item with no Answer line)."""
    flat = [l.rstrip("\r") for l in text.split("\n")]
    title, pre, items, cur, section, i = "", [], [], None, "", 0
    while i < len(flat):
        s = flat[i].strip()
        m = SURVEY_ITEM_RE.match(s)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2).strip(), "section": section, "body": [], "options": [],
                   "answer": "", "at": None, "span": 0}
            items.append(cur)
            section, i = "", i + 1
            continue
        h = SURVEY_HEAD_RE.match(s)
        if h and (cur is None or len(h.group(1)) <= 3):
            if len(h.group(1)) == 1 and not title and not items:
                title = h.group(2).strip()
            elif items:
                section = h.group(2).strip()          # a heading between items names the items under it
            cur, i = None, i + 1
            continue
        if cur is None:
            if not items:
                pre.append(s)                         # before the first item: the intro and the default line
            i += 1
            continue
        om, am = SURVEY_OPTIONS_RE.match(s), SURVEY_ANSWER_RE.match(s)
        if om and not cur["options"]:
            cur["options"] = survey_options(om.group(1))
        elif am and cur["at"] is None:
            words, j = am.group(1).strip(), i + 1
            while j < len(flat) and flat[j].strip() and not flat[j].lstrip().startswith("#") and not SURVEY_RULE_RE.match(flat[j].strip()):
                words += " " + flat[j].strip()        # an answer run onto the lines under it, read as patterns.py reads it
                j += 1
            cur.update(answer=words.strip(), at=i, span=j - i)
            i = j
            continue
        else:
            cur["body"].append(flat[i])
        i += 1
    quote, paras, para = [], [], []
    for s in pre + [""]:
        if s.startswith(">"):
            quote.append(re.sub(r"^>\s?", "", s))
            continue
        if s:
            para.append(s)
            continue
        if para:
            paras.append(" ".join(para))
            para = []
        if quote and quote[-1]:
            quote.append("")
    k = next((x for x, p in enumerate(paras) if SURVEY_DEFAULT_RE.search(p)), None)
    default = paras[k] if k is not None else ""
    intro = "\n\n".join(([("\n".join(quote)).strip()] if "".join(quote).strip() else []) + [p for x, p in enumerate(paras) if x != k])

    def statement(body):
        b = [l for l in body if not SURVEY_RULE_RE.match(l.strip())]
        while b and not b[0].strip():
            b.pop(0)
        while b and not b[-1].strip():
            b.pop()
        return "\n".join(b)
    out = []
    for it in items:
        choice, note = survey_read_answer(it["answer"], it["options"])
        out.append({"n": it["n"], "title": it["title"], "section": it["section"], "statement": statement(it["body"]),
                    "options": it["options"], "choice": choice, "note": note, "answer": it["answer"],
                    "at": it["at"], "span": it["span"]})
    return {"title": title, "intro": intro, "default": default, "items": out}


def survey_read(ap):
    """(text, bom) of a survey file: its bytes as UTF-8, a byte-order mark set aside so a write can put it back."""
    with open(ap, "rb") as f:
        raw = f.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    return (raw[3:] if bom else raw).decode("utf-8"), bom


def survey_api(rel):
    """GET /api/survey?path=<brain .md>: (code, body) -- the survey read for its page (the shape is in the banner above).
    An item's `line` is its Answer line's number in the file, 1-based, for the Reader."""
    ap, r, why = survey_abs(rel)
    if not ap:
        return 403, {"error": why, "path": str(rel or "")}
    if not os.path.isfile(ap):
        return 404, {"error": "no survey at %s" % r, "path": r}
    try:
        text, _bom = survey_read(ap)
    except UnicodeDecodeError:
        return 400, {"error": "%s is not UTF-8 text" % r, "path": r}
    s = survey_parse(text)
    items = [dict({k: it[k] for k in ("n", "title", "section", "statement", "options", "choice", "note", "answer")},
                  answered=bool(it["answer"]), line=(it["at"] + 1) if it["at"] is not None else None) for it in s["items"]]
    leaf = re.sub(r"[-_]+", " ", os.path.splitext(os.path.basename(r))[0]).strip()
    can = bool(write_abs(r))
    return 200, {"path": r, "title": s["title"] or leaf, "intro": s["intro"], "default": s["default"], "items": items,
                 "total": len(items), "answered": sum(1 for x in items if x["answered"]), "canWrite": can,
                 "writeReason": "" if can else reader_write_rule(r)[1],
                 "mode": "propose" if PROPOSE else "write", "reader": "/reader?path=" + urllib.parse.quote(r),
                 "mtime": dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds"),
                 "_servedAt": dt.datetime.now().isoformat(timespec="seconds")}


def survey_log(rel):
    """One MODIFIED line per survey per ten minutes (the call screen's rule): a survey pressed through is one log line."""
    now = time.time()
    if now - _survey_logged.get(rel, 0) < SURVEY_LOG_EVERY:
        return "not logged: %s was logged under ten minutes ago" % rel
    _survey_logged[rel] = now
    return log_line("%s -- survey answers saved on the survey page (/survey)" % rel)


def survey_answer(data):
    """POST /api/survey/answer {path, n, choice, note}: (code, body). Item n's Answer line becomes `Answer: <choice>`,
    `Answer: <choice>. <note>` or `Answer: <note>` (`Answer:` when both are empty), keeping the line's own indent, keyword
    and line ending; every other byte of the file is written back as it was read. A choice must be one of the item's
    options (any case; the Options line's spelling is written); a note alone is allowed."""
    ap, r, why = survey_abs(str(data.get("path") or ""), write=True)
    if not ap:
        return 403, {"error": why}
    if not os.path.isfile(ap):
        return 404, {"error": "no survey at %s" % r}
    try:
        n = int(str(data.get("n")).strip())
    except (TypeError, ValueError):
        return 400, {"error": "n must be the item's number"}
    choice = " ".join(str(data.get("choice") or "").split())
    note = " ".join(str(data.get("note") or "").split())
    if len(note) > SURVEY_NOTE_MAX:
        return 400, {"error": "the note is over %d characters; it is one line" % SURVEY_NOTE_MAX}
    with _survey_lock:
        try:
            text, bom = survey_read(ap)
        except UnicodeDecodeError:
            return 400, {"error": "%s is not UTF-8 text" % r}
        hits = [it for it in survey_parse(text)["items"] if it["n"] == n]
        if not hits:
            return 404, {"error": "no item %d in %s" % (n, r)}
        if len(hits) > 1:
            return 409, {"error": "two items in %s are numbered %d; number them apart in the Reader first" % (r, n)}
        it = hits[0]
        if it["at"] is None:
            return 409, {"error": "item %d has no Answer: line in the file" % n}
        if choice:
            canon = next((o for o in it["options"] if o.lower() == choice.lower()), None)
            if canon is None:
                return 400, {"error": ("%s is not one of item %d's options (%s)" % (choice, n, ", ".join(it["options"])))
                             if it["options"] else "item %d has no options: it is answered in your own words, the note alone" % n}
            choice = canon
        value = (choice + (". " + note if note else "")) if choice else note
        lines = text.split("\n")
        old = lines[it["at"]]
        m = re.match(r"^(\s*)(answer\s*:)", old.rstrip("\r"), re.I)
        new = m.group(1) + m.group(2) + (" " + value if value else "") + ("\r" if old.endswith("\r") else "")
        same = lines[it["at"]:it["at"] + it["span"]] == [new]
        lines[it["at"]:it["at"] + it["span"]] = [new]
        out = "\n".join(lines)
        after = survey_parse(out)["items"]
        said = dict(path=r, n=n, choice=choice, note=note, line=new.rstrip("\r"),
                    answered=sum(1 for x in after if x["answer"]), total=len(after))
        if same:
            return 200, dict(said, ok=True, unchanged=True, log="unchanged: nothing written")
        if PROPOSE:
            req = propose("file", r, {"content": out}, note="survey item %d answered on the survey page" % n)
            return 202, dict(said, proposed=True, request=req, kind="file", target=r)
        with open(ap, "wb") as f:
            f.write((b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8"))
    return 200, dict(said, ok=True, log=survey_log(r))


# ---- the sharing checklist (0.87.0, 2026-10-21) ----
# The owner asked for a checklist to tick off when he shares the brain with one person, and for ticking a people card's
# parts in or out section by section. /share draws one person's copy as ticks. What goes is never decided here: GET
# /api/share asks the team-copy export itself (skills/team-brain/export.py, loaded by path, so its tier rules, its people
# tier and its held-back list are read and never restated) what it would send, then marks what the owner unticked. The
# writes are three, each narrow and logged (rules 4, amended 2026-10-21): a folder, file or dashboard piece held back for
# that person goes into the export's share file (skills/team-brain/share-<member>.json); a whole card goes into the
# held-back list every copy reads (skills/team-brain/people-held-back.json); a section of a card is the [private] mark on
# its heading in the card itself, which the export already drops whole. A tick goes out with the next send. A team copy
# has no sharing of its own: everything here answers 403 there.
SHARE_EXPORT_REL = "skills/team-brain/export.py"
SHARE_DEFAULT_MEMBER = "dani"            # the export's own default member; status.json names the member it last sent to
SHARE_WHY_MAX = 300
_share_lock = threading.Lock()
_SHARE_HEAD_RE = re.compile(r"^(#{2,3})\s+(.*?)\s*$")
_SHARE_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_SHARE_PRIVATE_RE = re.compile(r"\s*\[private\]", re.I)


def share_export():
    """The team-copy export as a fresh module (its held-back list is cached per run), or None in a brain without one."""
    for root in (BRAIN, CODE):
        p = os.path.join(root, *SHARE_EXPORT_REL.split("/"))
        if os.path.isfile(p):
            import importlib.util
            spec = importlib.util.spec_from_file_location("team_export_for_share", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def share_member(q, ex):
    m = ((q.get("member") or [""])[0] if isinstance(q, dict) and isinstance(q.get("member"), list) else (q or {}).get("member", "")) or ""
    m = re.sub(r"[^a-z0-9-]", "", str(m).lower())
    if not m:
        try:
            m = json.loads(open(os.path.join(BRAIN, TEAM_STATUS_REL.replace("/", os.sep)), encoding="utf-8").read()).get("member") or ""
        except (OSError, ValueError):
            m = ""
    return re.sub(r"[^a-z0-9-]", "", str(m).lower()) or SHARE_DEFAULT_MEMBER


def share_card_sections(text):
    """A card's ## and ### headings outside code fences: {line, level, text, private, inherited}. inherited: inside a
    fold whose heading is marked [private], so it stays out with it and has no tick of its own."""
    out, fence, held_at = [], False, None
    for i, line in enumerate(text.split("\n")):
        if _SHARE_FENCE_RE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        m = _SHARE_HEAD_RE.match(line.rstrip("\r"))
        if not m:
            continue
        level, raw = len(m.group(1)), m.group(2)
        if held_at is not None and level <= held_at:
            held_at = None
        private = bool(_SHARE_PRIVATE_RE.search(raw))
        out.append({"line": i, "level": level, "text": _SHARE_PRIVATE_RE.sub("", raw).strip(), "private": private,
                    "inherited": held_at is not None})
        if private and held_at is None:
            held_at = level
    return out


def share_api(q):
    """GET /api/share: one person's copy as the checklist draws it."""
    if PROPOSE:
        return 403, {"error": "A team copy has no sharing of its own; sharing is set from the owner's brain"}
    ex = share_export()
    if ex is None:
        return 200, {"available": False, "why": "This brain has no team-copy export (%s), so there is no copy to share." % SHARE_EXPORT_REL}
    member = share_member(q, ex)
    reg = ex.load_registry()
    rows = ex.holon_rows(reg)
    sel = ex.select_content(rows)
    pr = ex.people_rules()
    held, held_err = {}, None
    try:
        held = ex.share_held(member)
    except (OSError, ValueError) as e:
        held_err = "the share file cannot be read (%s): the export stops until it is fixed or removed" % type(e).__name__
    names = {h["id"]: h.get("name") or h["id"] for h in reg.get("holons", [])}
    paths = {h["id"]: h["path"].replace("\\", "/") for h in reg.get("holons", [])}
    groups = {}
    for rel, hid in sorted(sel.items()):
        if rel.startswith("people/"):
            continue
        g = groups.setdefault(hid, {"id": hid, "name": "Mentee dashboard pieces" if hid == "mentee-dashboard" else names.get(hid, hid),
                                    "path": None if hid == "mentee-dashboard" else paths.get(hid), "files": []})
        g["files"].append({"path": rel, "held": ex.held_by(rel, held), "why": held.get(ex.held_by(rel, held) or "", "")})
    folders = []
    for g in groups.values():
        key = g["path"]
        g["held"] = bool(key and key in held)
        g["why"] = held.get(key, "") if key else ""
        g["going"] = sum(1 for f in g["files"] if not f["held"])
        folders.append(g)
    folders.sort(key=lambda g: (g["id"] == "mentee-dashboard", (g["path"] or "~").lower()))
    cards, named = [], pr.get("named")
    pdir = os.path.join(BRAIN, "people")
    for fn in sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []:
        if not fn.endswith(".md"):
            continue
        rel = "people/" + fn
        try:
            text = open(os.path.join(pdir, fn), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        title = next((l[2:].strip() for l in text.split("\n") if l.startswith("# ")), fn[:-3].replace("-", " ").title())
        never = bool(named and named.search(fn[:-3]))
        member_hold = ex.held_by(rel, held)
        cards.append({"path": rel, "name": title, "goes": rel in sel and not member_hold, "never": never,
                      "why": pr["held_back"].get(rel, "") or (held.get(member_hold, "") if member_hold else ""),
                      "heldFor": "this copy" if member_hold else ("every copy" if rel in pr["held_back"] else ""),
                      "sections": [] if never else share_card_sections(text)})
    private = sorted(({"path": p, "name": names.get(hid, hid), "tier": tier} for p, tier, hid in rows if tier != "team"),
                     key=lambda r: r["path"])
    try:
        st = json.loads(open(os.path.join(BRAIN, TEAM_STATUS_REL.replace("/", os.sep)), encoding="utf-8").read())
    except (OSError, ValueError):
        st = {}
    sh = ex.share_path(member)
    return 200, {"available": True, "member": member, "display": ex.display_name(member),
                 "lastSent": (st.get("last_export") or {}).get("at") if st.get("member", member) == member else None,
                 "shareFile": os.path.relpath(str(sh), BRAIN).replace(os.sep, "/"), "heldFile": ex.PEOPLE_HELD_BACK_REL,
                 "heldError": held_err, "peopleError": None if pr.get("ok") else pr.get("error"),
                 "folders": folders, "cards": cards, "private": private,
                 "counts": {"files": sum(g["going"] for g in folders if not g["held"]),
                            "cards": sum(1 for c in cards if c["goes"]), "cardsHeld": sum(1 for c in cards if not c["goes"])}}


def _share_write_json(path, d):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def share_set(data):
    """POST /api/share {member, path, go, why}: one tick on a folder, file, dashboard piece or whole card."""
    if PROPOSE:
        return 403, {"error": "A team copy has no sharing of its own"}
    ex = share_export()
    if ex is None:
        return 404, {"error": "This brain has no team-copy export"}
    member = share_member(data, ex)
    rel = (norm(str(data.get("path") or "")) or "").strip()
    go = bool(data.get("go"))
    why = re.sub(r"\s+", " ", str(data.get("why") or "")).strip()[:SHARE_WHY_MAX] or (
        "unticked on the sharing page, %s" % dt.date.today().isoformat())
    if not rel:
        return 400, {"error": "no path named"}
    with _share_lock:
        # checked without the full selection (a walk of the brain, seconds): a card is a people/*.md file; anything else
        # must be what the tier rules send, by its own tier, as a team holon's path, or as a dashboard piece
        rows = ex.holon_rows(ex.load_registry())
        is_card = rel.startswith("people/") and rel.endswith(".md") and "/" not in rel[len("people/"):]
        if is_card:
            if not os.path.isfile(os.path.join(BRAIN, rel.replace("/", os.sep))):
                return 404, {"error": "no card %s" % rel}
            named = ex.people_rules().get("named")
            if named and named.search(rel[len("people/"):-3]):
                return 400, {"error": "This person never crosses to any copy; the card has no tick"}
            hp = os.path.join(BRAIN, ex.PEOPLE_HELD_BACK_REL.replace("/", os.sep))
            try:
                d = json.loads(open(hp, encoding="utf-8").read())
            except (OSError, ValueError) as e:
                return 409, {"error": "the held-back list cannot be read (%s); nothing changed" % type(e).__name__}
            hb = d.setdefault("held_back", {})
            if go:
                hb.pop(rel, None)
            else:
                hb[rel] = why
            d["_updated"] = dt.date.today().isoformat()
            _share_write_json(hp, d)
            said = "%s -- %s %s on the sharing page (/share): %s" % (
                ex.PEOPLE_HELD_BACK_REL, "sent" if go else "held back", rel, "it goes to every copy again" if go else why)
        else:
            team_paths = {p for p, tier, _h in rows if tier == "team"}
            pieces = set()
            mp = os.path.join(BRAIN, ex.MANIFEST_REL.replace("/", os.sep))
            if os.path.isfile(mp):
                try:
                    pieces = set(ex.manifest_paths(json.loads(open(mp, encoding="utf-8").read())))
                except (OSError, ValueError):
                    pieces = set()
            sent = rel in team_paths or rel in pieces or (
                "/" in rel and not rel.startswith(("skills/", "people/")) and ex.tier_of(rel, rows)[0] == "team"
                and os.path.isfile(os.path.join(BRAIN, rel.replace("/", os.sep))))
            if not sent:
                return 400, {"error": "%s is not something this copy is sent; ticks are for what the tier rules send" % rel}
            sp = str(ex.share_path(member))
            try:
                d = json.loads(open(sp, encoding="utf-8").read()) if os.path.isfile(sp) else {}
            except (OSError, ValueError) as e:
                return 409, {"error": "the share file cannot be read (%s); nothing changed" % type(e).__name__}
            hb = d.setdefault("held_back", {})
            if go:
                above = next((k for k in hb if k != rel and k.endswith("/") and rel.startswith(k)), None)
                if above:
                    return 409, {"error": "the folder %s is held back; tick the folder first" % above}
                hb.pop(rel, None)
            else:
                hb[rel] = why
            d.setdefault("_what", "What the team-copy export would send to this member's copy and the owner unticked on "
                                  "the viewer's sharing page (/share). Each entry: a file or a folder (ending in /), and why.")
            d["member"], d["_updated"] = member, dt.date.today().isoformat()
            _share_write_json(sp, d)
            said = "%s -- %s %s for %s on the sharing page (/share)%s" % (
                os.path.relpath(sp, BRAIN).replace(os.sep, "/"), "sent" if go else "held back", rel, member, "" if go else ": " + why)
        logged = log_line(said)
    return 200, {"ok": True, "member": member, "path": rel, "go": go, "why": "" if go else why, "log": logged}


def share_section(data):
    """POST /api/share/section {path, line, text, private}: a card's section in or out, as [private] on its heading."""
    if PROPOSE:
        return 403, {"error": "A team copy has no sharing of its own"}
    rel = norm(str(data.get("path") or "")) or ""
    if not (rel.startswith("people/") and rel.endswith(".md") and "/" not in rel[len("people/"):]):
        return 400, {"error": "a section mark is for a people card"}
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    try:
        line_no = int(data.get("line"))
    except (TypeError, ValueError):
        return 400, {"error": "no line named"}
    want = str(data.get("text") or "").strip()
    private = bool(data.get("private"))
    with _share_lock:
        try:
            raw = open(ap, "rb").read()
        except OSError:
            return 404, {"error": "no card %s" % rel}
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
        nl = "\r\n" if "\r\n" in text else "\n"
        lines = text.split(nl)
        sec = next((s for s in share_card_sections(text.replace("\r\n", "\n")) if s["line"] == line_no), None)
        if sec is None or sec["text"] != want:
            return 409, {"error": "the card changed since the page read it; reload the page"}
        if sec["inherited"]:
            return 409, {"error": "this section sits inside one already kept out; untick or tick that one"}
        head = lines[line_no]
        if private and not sec["private"]:
            lines[line_no] = head.rstrip() + " [private]"
        elif not private and sec["private"]:
            lines[line_no] = _SHARE_PRIVATE_RE.sub("", head).rstrip()
        else:
            return 200, {"ok": True, "unchanged": True, "sections": share_card_sections(text.replace("\r\n", "\n"))}
        out = nl.join(lines)
        with open(ap, "wb") as f:
            f.write((b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8"))
        logged = log_line("%s -- the section \"%s\" %s on the sharing page (/share)" % (
            rel, want, "marked [private]: it stays out of every copy" if private else "unmarked: it goes again"))
    return 200, {"ok": True, "log": logged, "sections": share_card_sections(out.replace("\r\n", "\n"))}


# ---- the From band on a member's Today (0.88.0, 2026-10-21) ----
# The owner asked for a section on the member's Today that holds what comes to her from his side, drawn cleanly so she
# can answer where it is. In a team copy Today opens on it: her own items (the questions addressed to her, the tasks she
# owns) with the queue's own presses, each carrying a line on where her last press on it stands; the files new since her
# last look and the notes written for her, both read from the copy's what's-new page; one press that sends what she
# saved. GET /api/from-owner reads it all; POST /api/requests/send runs the copy's send (the steps of send-requests: add
# the requests folder, commit it, push it). A press goes through the request path: saved here -> waiting (committed,
# not on GitHub) -> sent (on GitHub) -> landed (the export brought the item back closed, skills/team-brain/pull.py
# having put her answer on it). Copy only: the owner's own brain answers 403.
FROM_LANDED_DAYS = 14
FROM_FILES_CAP = 20
_WN_HEAD_RE = re.compile(r"^## Export of (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) UTC")
_WN_PATH_RE = re.compile(r"^- `([^`]+)`\s*$")
_WN_LINK_RE = re.compile(r"^- \[\[([^|\]]+)\|([^\]]*)\]\]\s*$")   # a file by its title (the export since 2026-10-21)
_WN_PIECE_RE = re.compile(r'^- (.+?), on the dashboard(?: under "([^"]*)")?\s*$')
_WN_MORE_RE = re.compile(r"^- and (\d+) more files?\s*$")
_send_lock = threading.Lock()


def _copy_git(args, timeout=30):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")      # never wait on a password prompt nobody can see
    return subprocess.run(["git", "-C", BRAIN, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, env=env)


def from_request_states():
    """{request rel: saved | waiting | sent} for the member's request files, from the copy's own git."""
    folder = "%s/%s" % (REQUESTS_REL, MEMBER)
    ap = os.path.join(BRAIN, folder.replace("/", os.sep))
    files = sorted("%s/%s" % (folder, f) for f in os.listdir(ap) if f.endswith(".json")) if os.path.isdir(ap) else []
    if not files:
        return {}
    if not os.path.isdir(os.path.join(BRAIN, ".git")):
        return {f: "saved" for f in files}
    try:
        dirty = {l[3:].strip().strip('"') for l in _copy_git(["status", "--porcelain", "--untracked-files=all", "--", folder]).stdout.splitlines() if l}
        lg = _copy_git(["log", "@{u}..HEAD", "--name-only", "--format=", "--", folder])
        ahead = set(lg.stdout.split()) if lg.returncode == 0 else None     # None: no upstream known, so nothing counts as sent
    except (OSError, subprocess.SubprocessError):
        return {f: "saved" for f in files}
    return {f: ("saved" if f in dirty else "waiting" if ahead is None or f in ahead else "sent") for f in files}


def from_whats_new(since):
    """The copy's what's-new page as sections: {when, isNew, lead, requests, note, files: [{title, path}], more}; newest
    first. A file line is a backticked path (exports before 2026-10-21), a dashboard piece by its title, or a file by its
    title as [[path|title]]; the lead is the export's own sentences before the note; requests are the receipts (2026-10-22)."""
    ap = os.path.join(BRAIN, WHATS_NEW_REL)
    if not os.path.isfile(ap):
        return []
    try:
        text = open(ap, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    titles = {}
    try:
        man = json.loads(open(os.path.join(BRAIN, "context", "mentee-content-manifest.json"), encoding="utf-8").read())
        for stage in man.get("stages", []) if isinstance(man, dict) else []:
            for pc in stage.get("pieces", []):
                if pc.get("title") and pc.get("path"):
                    titles[pc["title"]] = pc["path"]
    except (OSError, ValueError):
        pass
    out = []
    for chunk in re.split(r"(?m)^(?=## Export of )", text):
        lines = chunk.split("\n")
        m = _WN_HEAD_RE.match(lines[0])
        if not m:
            continue
        when = "%sT%s:00Z" % (m.group(1), m.group(2))
        note, files, more, part, in_note = [], [], 0, "", False
        lead, requests = [], []      # the export's own sentences on what arrived, and the receipts for her requests (2026-10-22)
        for line in lines[1:]:
            s = line.strip()
            if s.startswith("**Your requests**"):
                in_note, part = False, "requests"
                continue
            if s.startswith("**How to use what arrived**"):
                in_note, part = True, "note"
                continue
            if s.startswith("**New since") or s.startswith("**Changed since") or s.startswith("**Removed"):
                in_note, part = False, "removed" if s.startswith("**Removed") else "list"
                continue
            if in_note:
                note.append(line)
                continue
            if part == "requests":
                if s.startswith("- "):
                    requests.append(re.sub(r"\s*<!--.*?-->\s*$", "", s[2:]).strip())
                    continue
                if not s:
                    continue
                part = ""            # the receipts ended; the export's lead sentences follow them
            if part == "":
                if s and not s.startswith("No file changed") and not s.startswith("This page starts"):
                    lead.append(s)
                continue
            if part != "list":
                continue
            pm, lm, dm, mm = _WN_PATH_RE.match(s), _WN_LINK_RE.match(s), _WN_PIECE_RE.match(s), _WN_MORE_RE.match(s)
            if pm:
                files.append({"title": pm.group(1).rsplit("/", 1)[-1], "path": pm.group(1)})
            elif lm:
                files.append({"title": lm.group(2).strip() or lm.group(1).rsplit("/", 1)[-1], "path": lm.group(1)})
            elif dm:
                files.append({"title": dm.group(1), "path": titles.get(dm.group(1)), "stage": dm.group(2)})
            elif mm:
                more += int(mm.group(1))
        local = when
        try:
            local = dt.datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone().replace(tzinfo=None).isoformat(timespec="seconds")
        except ValueError:
            pass
        out.append({"when": when, "isNew": bool(since) and local > since, "note": "\n".join(note).strip(),
                    "lead": " ".join(lead), "requests": requests,
                    "files": files[:FROM_FILES_CAP], "more": more + max(0, len(files) - FROM_FILES_CAP)})
    if out and not any(x["isNew"] for x in out) and not since:
        out[0]["isNew"] = True
    return out


def from_owner_api(q=None):
    """GET /api/from-owner: what the member's Today draws in the From band."""
    if not PROPOSE:
        return 403, {"error": "the From band is a team copy's: it holds what reaches the member from the owner's side"}
    team = load_team() or TEAM or {}
    states = from_request_states()
    since = today_visit(record=False).get("since") or ""
    paths = {}
    for h in registry().get("holons", []):
        if h.get("tasks"):
            paths[h["tasks"].replace("\\", "/")] = h["id"]
    items, landed, cutoff = {}, [], (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=FROM_LANDED_DAYS)).isoformat()
    ledgers = {}
    for rel, state in sorted(states.items()):
        try:
            req = json.loads(open(os.path.join(BRAIN, rel.replace("/", os.sep)), encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        pl = req.get("payload") or {}
        iid = str((pl.get("args") or {}).get("id") or "")
        project = paths.get((req.get("target") or "").replace("\\", "/"))
        if req.get("kind") != "tasks" or not iid or not project:
            continue
        row = {"file": rel, "state": state, "action": pl.get("action"), "at": req.get("at")}
        items["%s/%s" % (project, iid)] = row                  # sorted by name, so the newest press on an item wins
        if project not in ledgers:
            try:
                led = os.path.join(BRAIN, req["target"].replace("/", os.sep))
                ledgers[project] = {it["id"]: it for it in ledger.parse(ledger.read(led))["items"]}
            except Exception:
                ledgers[project] = {}
        it = ledgers[project].get(iid)
        if it and it.get("mark") in ("x", "a") and (req.get("at") or "") >= cutoff:
            landed.append(dict(row, project=project, id=iid, text=it.get("text") or ""))
    seen, uniq = set(), []
    for r in reversed(landed):
        k = (r["project"], r["id"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    sections = from_whats_new(since)
    return 200, {"from": team.get("from") or None, "member": MEMBER, "since": since, "items": items, "landed": uniq,
                 "unsent": sum(1 for s in states.values() if s != "sent"), "saved": sum(1 for s in states.values() if s == "saved"),
                 "git": os.path.isdir(os.path.join(BRAIN, ".git")), "sections": sections}


def requests_send():
    """POST /api/requests/send: the copy's send, the steps send-requests runs: add the requests folder, commit, push."""
    if not PROPOSE:
        return 403, {"error": "only a team copy sends requests"}
    if not os.path.isdir(os.path.join(BRAIN, ".git")):
        return 409, {"error": "this copy is not a git folder, so it cannot send; ask for the copy to be set up again"}
    folder = "%s/%s" % (REQUESTS_REL, MEMBER)
    with _send_lock:
        try:
            _copy_git(["add", "--", REQUESTS_REL])
            staged = _copy_git(["diff", "--cached", "--name-only", "--", REQUESTS_REL]).stdout.split()
            if staged:
                c = _copy_git(["commit", "-q", "-m", "requests %s (sent from the viewer)" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                               "--", REQUESTS_REL])
                if c.returncode != 0:
                    return 500, {"error": "the commit failed: " + ((c.stderr or c.stdout).strip().splitlines() or ["no message"])[-1]}
            waiting = _copy_git(["log", "@{u}..HEAD", "--name-only", "--format=", "--", folder]).stdout.split()
            if not waiting:
                return 200, {"ok": True, "sent": 0, "said": "Nothing waiting to send."}
            # GitHub first (2026-10-22, brain-central T-0212): an export pushed after her last pull would make GitHub refuse
            # the push, so the newest export is brought in under her commits; a change not committed is set aside for it
            pr = _copy_git(["pull", "--rebase", "--autostash", "-q"], timeout=90)
            if pr.returncode != 0:
                err = (pr.stderr or pr.stdout) or ""
                _copy_git(["rebase", "--abort"])
                if "CONFLICT" in err or "could not apply" in err or "conflict" in err.lower():
                    owner = (load_team() or {}).get("from") or "the brain's owner"
                    return 409, {"error": "Not sent. Your copy is behind GitHub, and the newest export clashes with a change "
                                          "committed in this folder. Your requests are saved here; tell %s, and once the clash is "
                                          "cleared, press send again." % owner}
                last = (err.strip().splitlines() or ["no message"])[-1]
                return 502, {"error": "not sent: GitHub could not be read first (%s). Your requests are saved here and go "
                                      "the next time a send works." % last[:200]}
            p = _copy_git(["push", "-q"], timeout=90)
        except subprocess.TimeoutExpired:
            return 504, {"error": "the send took too long and was stopped; your requests are saved here, try again"}
        except OSError as e:
            return 500, {"error": "git could not run: %s" % e}
    if p.returncode != 0:
        last = ((p.stderr or p.stdout).strip().splitlines() or ["no message"])[-1]
        return 502, {"error": "not sent: %s. Your requests are saved here and go the next time a send works; "
                              "double-click send-requests in your brain folder to see the whole message." % last[:200]}
    log_line("%s -- %d request%s sent from the viewer's From band (git push)" % (folder, len(set(waiting)), "" if len(set(waiting)) == 1 else "s"), action="SYNCED")
    return 200, {"ok": True, "sent": len(set(waiting)), "said": "Sent."}


# ---- the friction cards on Today (0.80.0, 2026-10-14, the Patterns agent's Phase 2) ----
# The owner answered on 10/05 how the friction predictions reach him: as cards on Today, at most three open at a time,
# each quoting the instance, naming the pattern it resembles with its rule written out, and offering three answers:
# annoying, not annoying, or a comment. The cards live in the person's record (how-<first>-works/, the Patterns agent's
# holon), one open card per friction record, opened by `skills/patterns/patterns.py card` and never by this server.
# GET /api/friction reads them through the tool's own cards_json(); POST /api/friction/answer writes his press through
# the tool's card_press(), the way a ledger press goes through tasks.py: the tool is the only writer of a record, and
# its clock and its log line are the tool's. The press then reaches the session like every other press, as a batch of
# its own in context/answers-inbox.md. A team copy carries no record of the owner: it draws none and writes none.
try:
    sys.path.insert(0, os.path.join(CODE, "skills", "patterns"))
    import patterns as patterns_tool  # noqa: E402
except Exception as _pe:              # noqa: BLE001 -- a code copy without the Patterns skill draws no friction cards
    patterns_tool, _PATTERNS_ERR = None, str(_pe)
else:
    _PATTERNS_ERR = None
_friction_lock = threading.Lock()
FRICTION_NOTE_MAX = 2000              # characters, as the survey's note box


def friction_api():
    """GET /api/friction: (code, body) -- {cards: [{record, title, instance, rule, opened, days, path, reader}], max}."""
    if PROPOSE:
        return 200, {"cards": [], "max": 0, "why": "a team copy carries no record of the owner"}
    if patterns_tool is None:
        return 200, {"cards": [], "max": 0, "why": "the Patterns skill is not in this code copy (%s)" % _PATTERNS_ERR}
    try:
        cards = patterns_tool.cards_json()
    except Exception as e:                                         # noqa: BLE001 -- a record that does not parse
        return 500, {"error": "the record could not be read: %s" % e, "cards": [], "max": 0}
    for c in cards:
        c["reader"] = "/reader?path=" + urllib.parse.quote(c["path"])
    return 200, {"cards": cards, "max": patterns_tool.CARD_MAX, "holon": patterns_tool.HOLON,
                 "_servedAt": dt.datetime.now().isoformat(timespec="seconds")}


def friction_to_inbox(out):
    """His press, sent to the session as its own batch (the undo route's way): what was pressed before it goes first."""
    with _answers_lock:
        _answers_submit_locked()
        body, (cur_min, cur_lines) = answers_read()
        others = body["items"]
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        line = '- %s record-%d · friction card · %s %s · "%s"%s' % (
            patterns_tool.HOLON, out["record"], out["press"].replace("-", " "), stamp[11:],
            _first_sentence(out.get("title") or ""), (" · note: %s" % out["note"]) if out.get("note") else "")
        lines = ["## Batch %s (1 friction press%s)" % (stamp, (", %d answer%s" % (len(others), "" if len(others) == 1
                                                                                 else "s")) if others else "")]
        lines.append(line)
        lines += answers_batch_lines(others, stamp)[1:]
        _inbox_append(lines)
        _answers_cursor_move(dt.datetime.now(), stamp, 1 + len(others), cur_min, cur_lines)
    return stamp


def friction_answer(data):
    """POST /api/friction/answer {record, press: annoying|not-annoying|comment, note}: (code, body). The press is
    written into the record through skills/patterns/patterns.py (card_press), then sent to the session."""
    if PROPOSE:
        return 403, {"error": "a team copy does not write the owner's record"}
    if patterns_tool is None:
        return 501, {"error": "the Patterns skill is not in this code copy"}
    try:
        rid = int(str(data.get("record")).strip())
    except (TypeError, ValueError):
        return 400, {"error": "record must be the record's number"}
    note = " ".join(str(data.get("note") or "").split())
    if len(note) > FRICTION_NOTE_MAX:
        return 400, {"error": "the comment is over %d characters" % FRICTION_NOTE_MAX}
    with _friction_lock:
        try:
            out = patterns_tool.card_press(rid, data.get("press"), note)
        except patterns_tool.NoCard as e:
            return 409, {"error": str(e)}
        except patterns_tool.Fail as e:
            return (404 if str(e).startswith("no record") else 400), {"error": str(e)}
    try:
        batch = friction_to_inbox(out)
    except Exception as e:                                         # noqa: BLE001 -- the press is written; a failed send never undoes it
        sys.stderr.write("friction press not sent to the inbox: %s: %s\n" % (type(e).__name__, e))
        batch = None
    said = {"annoying": "Marked annoying", "not-annoying": "Marked not annoying", "comment": "Comment written"}
    return 200, dict(out, ok=True, batch=batch, message="%s on %s; written into the record of how you work." % (
        said.get(out["press"], "Written"), out["title"]))


# A transcript is intaken when the import-checkup report for it exists (the runbook's retained artifact, and the reason
# the report folder sits next to the raws). The app mirror names the same call differently from the raw, so an exact
# stem match is tried first and a same-day report sharing a name word is accepted second, marked as the weaker match
# rather than quietly presented as the strong one.
TRANSCRIPT_EXT = {".txt", ".md", ".json", ".vtt", ".srt"}


# a transcript's filename read as a title (0.65.0, Appendix B of the review): "zak-john-dani-team-call-2026-10-06" is
# "Team call: Sam, Ana". The kind of call is the first kind word found in the name; the names around it are people,
# two words joined when the brain has a card under that slug (nathan-story, owen-koenigs), first names otherwise.
TRANSCRIPT_KINDS = (("placement-call", "Placement call"), ("team-call", "Team call"), ("four-way", "Four-way call"),
                    ("interview", "Interview"), ("checkin", "Check-in"), ("check-in", "Check-in"), ("followup", "Follow-up"),
                    ("follow-up", "Follow-up"), ("meeting", "Meeting"), ("intro", "Intro call"), ("call", "Call"))


def transcript_title(stem):
    s = re.sub(r"[-_ ]?\d{4}-\d{2}-\d{2}.*$", "", str(stem or "")).strip("-_ ").lower()
    s = re.sub(r"^zak-", "", s)
    kind = None
    for k, word in TRANSCRIPT_KINDS:
        m = re.search(r"(^|-)%s($|-)" % re.escape(k), s)
        if m:
            kind, s = word, (s[:m.start()] + "-" + s[m.end():]).strip("-")
            break
    toks = [t for t in s.split("-") if t and t != "zak"]
    names, i = [], 0
    while i < len(toks):
        two = "-".join(toks[i:i + 2])
        if i + 1 < len(toks) and os.path.isfile(os.path.join(BRAIN, "people", two + ".md")):
            names.append(" ".join(w.capitalize() for w in toks[i:i + 2])); i += 2
        else:
            names.append(toks[i].capitalize()); i += 1
    if kind and names:
        return "%s: %s" % (kind, ", ".join(names))
    return kind or (", ".join(names) if names else str(stem or ""))


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
    for r in rows:
        r["title"] = transcript_title(r["stem"])
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
        call = is_call(e.get("title"), who)
        dp = event_day_preps(e, day, by_day) if call else []
        hits = preps_for_event(event_match_keys(who), dp, gmembers) if dp else []
        out["events"].append({"date": day, "start": start, "end": str(e.get("end") or ""),
                              "title": str(e.get("title") or "(untitled)"),
                              "organizer": str(e.get("organizer") or "") or None,
                              "attendees": [{"name": w["name"]} for w in who],
                              "people": who, "call": call, "preps": prep_rows(hits), **event_links(e)})
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


load_part('part_studio.py')   # 0.68.0: the image studio, in its own file


def render_page(route):
    """One page of the app as it is served (0.68.0: the templating in one place). The file PAGES names for the route (a
    team copy's home stays the mentee dashboard), with the mode and the owner injected before </head> so the team strip
    renders synchronously (viewer-common.js reads window.BV_MODE), and the member's look in the head before first paint."""
    page = PAGES[route]
    if route in HOME_ROUTES and PROPOSE:
        page = "mentee-dashboard.html"      # a team copy has no chat: its home stays the dashboard
    with open(os.path.join(HERE, page), "r", encoding="utf-8") as f:
        html = f.read()
    # 0.91.0: window.BV_WHATSNEW carries the header's what's new link and its dot; BV_ROUTES stays last before </script>
    html = html.replace("</head>", "<script>window.BV_MODE=%s;window.BV_OWNER=%s;window.BV_WHATSNEW=%s;window.BV_ROUTES=%s;</script>\n</head>"
                        % (json.dumps(mode_info(), ensure_ascii=False).replace("</", "<\\/"), json.dumps(OWNER),
                           json.dumps(whats_new_state(), ensure_ascii=False).replace("</", "<\\/"),
                           json.dumps(route_titles(), ensure_ascii=False).replace("</", "<\\/")), 1)
    return look_head(html)


# ---- links drawn as links (0.89.0, 2026-10-21) ----
# The owner, on a review item whose link sat at the bottom as a chip named after its file, and whose route opened in the
# side drawer: a route in an item is a page of this app and is a real link that navigates; a document opens in the
# drawer; every link reads as the title of what it opens. route_titles() gives the page every route the app answers
# with its page's own <title> (window.BV_ROUTES), so the code that draws a link knows a route from a slash in a sentence
# and names it without a list kept by hand. GET /api/titles names the documents: frontmatter title, else first heading.
_ROUTE_TITLES = None
_TITLE_RE = re.compile(r"<title>([^<]*)</title>", re.I)
_doc_titles = {}


def route_titles():
    global _ROUTE_TITLES
    if _ROUTE_TITLES is None:
        out = {}
        for route, page in PAGES.items():
            if route in ("/index.html",):
                continue
            try:
                with open(os.path.join(HERE, page), "r", encoding="utf-8") as f:
                    m = _TITLE_RE.search(f.read(4000))
                out[route] = (m.group(1).strip() if m else route.strip("/")) or "Today"
            except OSError:
                continue
        for route, target in REDIRECTS.items() if isinstance(globals().get("REDIRECTS"), dict) else []:
            base = str(target).split("?")[0].split("#")[0]
            if route not in out and base in out:
                out[route] = out[base]
        _ROUTE_TITLES = out
    return _ROUTE_TITLES


def doc_title(rel):
    """A document's title: its frontmatter title, else its first # heading, else None. Cached on the file's mtime."""
    ap = read_abs(rel)
    if not ap or not os.path.isfile(ap):
        return None
    try:
        mt = os.path.getmtime(ap)
    except OSError:
        return None
    hit = _doc_titles.get(rel)
    if hit and hit[0] == mt:
        return hit[1]
    title = None
    if rel.lower().endswith(".md"):
        try:
            with open(ap, "r", encoding="utf-8-sig", errors="replace") as f:
                head = f.read(6000)
        except OSError:
            head = ""
        fm, body = split_fm(head)
        if isinstance(fm, dict) and str(fm.get("title") or "").strip():
            title = str(fm["title"]).strip()
        else:
            for line in body if isinstance(body, list) else str(body).split("\n"):
                if line.startswith("# "):
                    title = re.sub(r"[*_`]|\[\[|\]\]", "", line[2:]).strip()
                    break
    if title and len(title) > 90:
        title = title[:88].rsplit(" ", 1)[0] + "…"
    _doc_titles[rel] = (mt, title)
    return title


def titles_api(q):
    """GET /api/titles?path=a&path=b -> {"titles": {path: title or null}}; read-gated like every broad read."""
    paths = [x for x in (q.get("path") or []) if x][:100]
    return 200, {"titles": {x: doc_title(x) for x in paths}}


# ---- Claude's reply on the card (0.93.0, 2026-10-26) ----
# Every press the owner makes in the viewer reaches the session as a batch in context/answers-inbox.md, and the session
# marks the batch taken in with one line under it, `processed: <day time> · <clause>`. That clause is Claude's reply to
# the press. Until 0.93.0 it lived in that file alone, and the reply to a note he wrote on a card reached him, when it
# did, appended into his own note (10/21: "How am I supposed to read this response? This looks bad. This just looks
# like the same thread"). Now the card draws it under his words as Claude's reply, apart from what he wrote, and this
# is where it is read: the inbox parsed once per change (its size and time, and the day), the note, answered and done
# lines of the last REPLIES_DAYS keyed by "<project>/<id>" with the batch's clause beside each, newest first. A step
# tick, a hold and an undo carry no reply worth drawing. Nothing is written, and a team copy, which holds no owner's
# inbox, gets {}.
REPLIES_DAYS = 30
REPLIES_PRESSES = ("note", "answered", "done")
_REP_BATCH = re.compile(r"^## Batch (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) ")
_REP_LINE = re.compile(r'^- (\S+) ([TQ]-\d{4}) · (?:task|question) · ([a-z]+)(?: (\d{2}:\d{2}))? · "(.*)$')
_REP_DONE = re.compile(r"^processed: (\d{4}-\d{2}-\d{2} \d{2}:\d{2})(?: · (.*))?$")
_rep_cache = {"key": None, "map": {}}


def replies_api():
    """GET /api/replies -> {"<project>/<id>": [{at, press, yours, replyAt, reply}, ...]}, newest first; {} in a team copy."""
    if PROPOSE:
        return {}
    ap = os.path.join(BRAIN, ANSWERS_INBOX_REL.replace("/", os.sep))
    try:
        st = os.stat(ap)
    except OSError:
        return {}
    today = ledger.today()
    key = (st.st_mtime_ns, st.st_size, today)
    if _rep_cache["key"] == key:
        return _rep_cache["map"]
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            lines = f.read().replace("\r\n", "\n").split("\n")
    except OSError:
        return {}
    try:
        since = (dt.date.fromisoformat(today) - dt.timedelta(days=REPLIES_DAYS)).isoformat()
    except ValueError:
        since = (dt.date.today() - dt.timedelta(days=REPLIES_DAYS)).isoformat()
    out, batch, entries = {}, None, []

    def flush(reply_at, reply):
        for e in entries:
            if reply:
                e.update(replyAt=reply_at, reply=reply)
                out.setdefault(e["project"] + "/" + e["id"], []).append(e)
    for line in lines:
        m = _REP_BATCH.match(line)
        if m:
            entries, batch = [], m.group(1)
            continue
        if not batch or batch[:10] < since:
            continue
        m = _REP_LINE.match(line)
        if m:
            project, iid, press, at, rest = m.groups()
            if press not in REPLIES_PRESSES:
                continue
            # the item's words are quoted; what he wrote follows the last `" · <press>: ` (his words may hold quotes too)
            k = rest.rfind('" · ')
            tail = rest[k + 4:] if k >= 0 else ""
            yours = tail.split(": ", 1)[1] if ": " in tail else ""
            entries.append({"project": project, "id": iid, "at": "%s %s" % (batch[:10], at or batch[11:]),
                            "press": press, "yours": yours.strip()})
            continue
        m = _REP_DONE.match(line)
        if m:
            flush(m.group(1), (m.group(2) or "").strip())
            entries = []
    for v in out.values():
        v.sort(key=lambda e: (e.get("replyAt") or "", e["at"]), reverse=True)
    _rep_cache.update(key=key, map=out)
    return out


_FALLTHROUGH = object()   # a route handler that did not answer: try the next matching route (0.68.0)


class H(BaseHTTPRequestHandler):
    server_version = "brain-viewer/" + VERSION

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if getattr(self, "_autosend", False) and 200 <= code < 300:
            self._autosend = False
            answers_autosend_soon()
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
        body = None
        try:
            for h in route_handlers("GET", u.path):
                if h(self, u, q, body) is not _FALLTHROUGH:
                    return
            return self._send(404, {"error": "no such route"})
        except Exception as e:
            return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

    def _get_redirect_routes(self, u, q, body):
        # GET every route in REDIRECT_ROUTES
        # 0.66.0: a folded page's old route goes to where its work lives now (fold_redirect); 0.64.0 began this
        # with /work, which sends an item on a thread to its thread page, focused on it
        to = fold_redirect(u.path, q)
        if to:
            self.send_response(302)
            self.send_header("Location", to)
            # 0.70.0 (the navigation direction, rule 6): the landing page says where the old address went, once per browser
            # session (viewer-common.js MOVED); a cookie carries which old address it was, so no destination URL changes
            self.send_header("Set-Cookie", "bv_moved=%s; Path=/; Max-Age=120; SameSite=Lax" % u.path.strip("/"))
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        return _FALLTHROUGH

    def _get_pages(self, u, q, body):
        # GET every route in PAGES
        return self._send(200, render_page(u.path), "text/html; charset=utf-8")

    def _get_api_routes(self, u, q, body):
        # GET /api/routes (0.68.0): the route table as data, so a drawing of what runs can be derived from what is served
        rows = route_list()
        return self._send(200, {"_servedAt": dt.datetime.now().isoformat(timespec="seconds"), "count": len(rows),
                                "pages": sorted(PAGES), "redirects": list(REDIRECT_ROUTES), "routes": rows})

    def _get_raw(self, u, q, body):
        # GET /raw/*
        # the preview page's frame (0.61.0): a brain file's bytes as they sit, static types only (raw_abs)
        ap = raw_abs(urllib.parse.unquote(u.path[len("/raw/"):]))
        if not ap:
            return self._send(403, {"error": "not served raw: a static web file inside the brain (html, css, js, a picture, a font), no dot folders, no key files"})
        with open(ap, "rb") as f:
            return self._send(200, f.read(), RAW_TYPES[os.path.splitext(ap)[1].lower()])
        return _FALLTHROUGH

    def _get_api_mtime(self, u, q, body):
        # GET /api/mtime
        # when a brain file last changed, for the preview page's reload (0.61.0)
        code, out = mtime_api(q.get("path", [""])[0])
        return self._send(code, out)

    def _get_api_artifacts(self, u, q, body):
        # GET /api/artifacts
        # the artifacts page and Today's "Built, to look at" band (0.76.0): every built thing by its name, newest first
        try:
            lim = int((q.get("limit") or ["0"])[0] or 0)
        except ValueError:
            lim = 0
        if (q.get("fresh") or [""])[0]:
            # 0.77.2: Today's band asks only for what is new and still in play (built_to_look_at)
            t0 = time.time()
            rows = built_to_look_at(artifacts_list(None)["artifacts"])
            return self._send(200, {"count": len(rows), "artifacts": rows[:lim] if lim > 0 else rows,
                                    "ms": int((time.time() - t0) * 1000)})
        return self._send(200, artifacts_list(lim if lim > 0 else None))

    def _get_api_usage(self, u, q, body):
        # GET /api/usage
        # the Usage page (0.84.0): the days, the top turns of a day and of the week, the sessions, one session's timeline
        code, out = usage_api(q)
        return self._send(code, out)

    def _get_api_titles(self, u, q, body):
        # GET /api/titles?path=...
        # links drawn as links (0.89.0): each document link reads as the title of what it opens
        code, out = titles_api(q)
        return self._send(code, out)

    def _get_api_replies(self, u, q, body):
        # GET /api/replies
        # Claude's reply on the card (0.93.0): what the session wrote when it took in a press, keyed by item
        return self._send(200, {"replies": replies_api()})

    def _get_api_from_owner(self, u, q, body):
        # GET /api/from-owner
        # the From band on a member's Today (0.88.0): her items' request states, what landed, the what's-new sections
        code, out = from_owner_api(q)
        return self._send(code, out)

    def _get_api_share(self, u, q, body):
        # GET /api/share?member=
        # the sharing checklist (0.87.0): one person's copy as ticks, from the team-copy export's own selection
        code, out = share_api(q)
        return self._send(code, out)

    def _get_api_preview_pages(self, u, q, body):
        # GET /api/preview/pages
        # the preview page's picker (0.61.0): every .html it offers, by folder, newest first
        return self._send(200, preview_pages())

    def _get_api_work(self, u, q, body):
        # GET /api/work
        # the Workspace (0.63.0): one ledger item with everything needed to answer or do it
        code, out = work_bundle(q.get("item", [""])[0], (q.get("scope") or ["all"])[0])
        return self._send(code, out)

    def _get_api_brief_status(self, u, q, body):
        # GET /api/brief/status
        code, out = brief_status(q.get("item", [""])[0])
        return self._send(code, out)

    def _get_api_thread(self, u, q, body):
        # GET /api/thread
        # one thread page (0.62.0): a subject file joined with every ledger item on it, its files and its next call
        code, out = thread_api(q.get("subject", [""])[0])
        return self._send(code, out)

    def _get_api_threads(self, u, q, body):
        # GET /api/threads
        # the threads index (0.62.0): every subject file, one row each, newest dated line first
        return self._send(200, threads_api((q.get("person") or [None])[0]))

    def _post_api_threads_new(self, u, q, body):
        # POST /api/threads/new
        # 0.69.0: the first thread of a fresh brain (and any new one): one subject file, exclusive create, logged
        data = json.loads(body or "{}")
        rel, err = new_thread(data.get("name"), data.get("about"))
        if err:
            return self._send(400, {"error": err})
        if PROPOSE:
            return self._send(202, {"proposed": True, "request": rel, "kind": "file"})
        return self._send(200, {"ok": True, "path": rel, "href": "/thread?subject=" + urllib.parse.quote(rel)})

    def _get_api_in_progress(self, u, q, body):
        # GET /api/in-progress
        # the home widget In progress (0.61.0): context/in-progress.json resolved, plus the other recent work
        return self._send(200, in_progress_api())

    def _get_api_answers_pending(self, u, q, body):
        # GET /api/answers/pending
        # the outbox (0.60.0): the owner's presses in the viewer since the last send, read back off the log
        return self._send(200, answers_pending())

    def _get_api_settings(self, u, q, body):
        # GET /api/settings (0.92.0): the settings the Settings page changes, as they stand
        return self._send(200, settings_read())

    def _put_api_settings(self, u, q, body):
        # PUT /api/settings (0.92.0): {answers_hold?, answers_quiet_minutes?} into viewer/settings.json, the rest kept
        try:
            data = json.loads(body or "{}")
        except ValueError:
            return self._send(400, {"error": "the body is not JSON"})
        code, out = settings_write(data)
        return self._send(code, out)

    def _post_api_answers_away(self, u, q, body):
        # POST /api/answers/away (0.92.0): a viewer page went out of sight; held answers go after the grace unless one comes back
        code, out = answers_away()
        return self._send(code, out)

    def _post_api_answers_here(self, u, q, body):
        # POST /api/answers/here (0.92.0): a viewer page is in sight; the away timer stops
        code, out = answers_here()
        return self._send(code, out)

    def _get_api_sweep_status(self, u, q, body):
        # GET /api/sweep/status
        # Clear answered questions (0.60.0): the question sweep's status file, the tail of its output, what this server started
        return self._send(200, sweep_status())

    def _get_api_health(self, u, q, body):
        # GET /api/health
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

    def _get_api_search(self, u, q, body):
        # GET /api/search
        # file search (2026-09-17, T-0158): by name and by text over the live files, capped at 50
        try:
            lim = max(1, min(SEARCH_MAX, int((q.get("limit") or [str(SEARCH_MAX)])[0])))
        except ValueError:
            lim = SEARCH_MAX
        return self._send(200, search_api(q.get("q", [""])[0], lim))

    def _get_api_files(self, u, q, body):
        # GET /api/files
        # the Files page (0.52.0, T-0259): every file in the brain but .git, node_modules, __pycache__ and the keys
        g = lambda k: (q.get(k) or [""])[0]
        return self._send(200, files_api(g("folder"), g("type"), g("q"), g("sort") or "modified", g("order")))

    def _get_api_file_raw(self, u, q, body):
        # GET /api/file-raw
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

    def _get_api_mode(self, u, q, body):
        # GET /api/mode
        return self._send(200, mode_info())

    def _get_api_studio(self, u, q, body):
        # GET /api/studio/*
        # the image studio (T-0235): providers, jobs and the prompts of a markdown file; 403 in a team copy
        code, out = studio_api("GET", u.path, q, None)
        return self._send(code, out)

    def _get_api_looks(self, u, q, body):
        # GET /api/looks
        # the looks folder, which IS the registry, and this member's active look (T-0208)
        return self._send(200, looks_api())

    def _get_api_widgets(self, u, q, body):
        # GET /api/widgets
        # the home page's registry: the *.js files in skills/brain-viewer/widgets/, which IS the registry
        reg = widget_registry()
        return self._send(200, {"folder": "skills/brain-viewer/" + WIDGETS_DIR, "userFolder": USER_WIDGETS_REL + "/",
                                "contract": WIDGET_CONTRACT, "count": len(reg), "widgets": reg,
                                "_servedAt": dt.datetime.now().isoformat(timespec="seconds")})

    def _get_api_home_layout(self, u, q, body):
        # GET /api/home/layout
        # which widgets are on, in what order, at what size -- per member, in a file, so it survives the browser
        return self._send(200, home_layout_api())

    def _get_api_help(self, u, q, body):
        # GET /api/help
        # what each page of this app is for, in plain words: the "?" panel reads it
        return self._send(200, help_api())

    def _get_api_calendar_week(self, u, q, body):
        # GET /api/calendar/week
        # the next seven days as the session start wrote them: what the home page's dial draws past today
        return self._send(200, calendar_week_api())

    def _get_api_call(self, u, q, body):
        # GET /api/call
        # the call screen's one read (0.47.0): the event, its people with their cards, the prep in its parts
        if PROPOSE:
            return self._send(403, {"error": "call preps and people cards are not part of a team copy"})
        code, out = call_api(q.get("prep", [""])[0] or None, q.get("date", [""])[0] or None, q.get("start", [""])[0] or None)
        return self._send(code, out)

    def _get_api_survey(self, u, q, body):
        # GET /api/survey
        # the survey page's one read (0.78.0): the file's title, intro and items, each with its options and its answer
        code, out = survey_api(q.get("path", [""])[0])
        return self._send(code, out)

    def _get_api_friction(self, u, q, body):
        # GET /api/friction
        # the friction cards Today draws (0.80.0): at most three open, read through skills/patterns/patterns.py
        code, out = friction_api()
        return self._send(code, out)

    def _get_api_moved(self, u, q, body):
        # GET /api/moved
        # the tail of the brain's log, parsed: what moved since a moment, newest first; one writer with agent=,
        # a window of days back with days= (0.38.0, the moon)
        return self._send(200, moved_api(q.get("since", [""])[0], (q.get("limit") or [MOVED_DEFAULT])[0],
                                         q.get("agent", [""])[0], q.get("days", [""])[0]))

    def _get_api_system(self, u, q, body):
        # GET /api/system
        # the lamps (0.38.0): every part of this brain that runs on its own, and when it last ran
        return self._send(200, system_api())

    def _get_api_events(self, u, q, body):
        # GET /api/events
        # the live wire (0.38.0): context/log.md as it is written, one event per line, until the page goes away
        return events_stream(self)

    def _get_api_mantras(self, u, q, body):
        # GET /api/mantras
        # the line under the date (0.38.0): the pool the owner builds over time, in file order
        return self._send(200, mantras_api())

    def _get_api_requests(self, u, q, body):
        # GET /api/requests
        return self._send(200, requests_api())

    def _get_api_exchange(self, u, q, body):
        # GET /api/exchange
        if PROPOSE:
            return self._send(403, {"error": "an exchange is between two owners' own machines; a team copy has none"})
        return self._send(200, exchange_state())

    def _get_favicon_ico(self, u, q, body):
        # GET /favicon.ico
        # every page declares /static/sun-favicon.png, and the browser asks for this anyway: answering it with the
        # same file is the difference between a console with one permanent error in it and a clean one (T-0065)
        return self._get_static(u._replace(path="/static/sun-favicon.png"), q, body)

    def _get_static(self, u, q, body):
        # GET /static/*
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
        return _FALLTHROUGH

    def _get_api_manifest(self, u, q, body):
        # GET /api/manifest
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

    def _get_api_file(self, u, q, body):
        # GET /api/file
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

    def _get_api_image(self, u, q, body):
        # GET /api/image
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
        return _FALLTHROUGH

    def _get_api_canvas(self, u, q, body):
        # GET /api/canvas
        ap = read_abs(q.get("path", [""])[0])
        if not ap or not ap.endswith(".canvas") or not os.path.isfile(ap):
            return self._send(404, {"error": "canvas not found"})
        with open(ap, "r", encoding="utf-8-sig") as f:
            return self._send(200, json.load(f))
        return _FALLTHROUGH

    def _get_api_canvases(self, u, q, body):
        # GET /api/canvases
        return self._send(200, {"canvases": canvases(), "root": ARCH_REL})

    def _get_api_forge_states(self, u, q, body):
        # GET /api/forge/states
        # 0.67.0: the part states alone (not built / building / working / quiet), for the Forge's read mode
        row, err = live_api(q.get("path", [""])[0])
        if err:
            return self._send(404, {"error": err})
        return self._send(200, {"path": row["path"], "days": row["days"], "counts": row["counts"]["states"],
                                "nodes": {k: {"state": v.get("state"), "stateBy": v.get("stateBy") or [],
                                              "target": v["binding"].get("target"), "kind": v["binding"].get("kind")}
                                          for k, v in row["nodes"].items()}})

    def _get_api_forge_scratch(self, u, q, body):
        # GET /api/forge/scratch
        # 0.67.0: the scratch family for the Forge's picker, kept apart from the drawings /api/canvases lists
        return self._send(200, scratch_canvases())

    def _get_api_forge(self, u, q, body):
        # GET /api/forge
        # the Forge (2026-09-09, T-0041): one read for the design surface -- the drawing, its .forge.json sibling, the write scope
        row, err = forge_api(q.get("path", [""])[0])
        return self._send(404 if err else 200, {"error": err} if err else row)

    def _get_api_forge_fields(self, u, q, body):
        # GET /api/forge/fields
        # the mouth's shelf (2026-09-10, T-0091): the loose fields one cell can ship, read from the real records
        # behind it at request time. The drawing carries a pointer; the field list is never stored in it.
        row, err = forge_fields_api(q.get("path", [""])[0], q.get("node", [""])[0])
        return self._send(404 if err else 200, {"error": err} if err else row)

    def _get_api_live(self, u, q, body):
        # GET /api/live
        # the live maps (2026-09-09, T-0042): every node of a canvas bound to the real thing it stands for, lit by the last 14 days of evidence
        row, err = live_api(q.get("path", [""])[0])
        return self._send(404 if err else 200, {"error": err} if err else row)

    def _get_api_adapter(self, u, q, body):
        # GET /api/adapter
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

    def _get_api_adapters(self, u, q, body):
        # GET /api/adapters
        # the registry (2026-09-18, viewer Q-0024): WHICH boundaries exist is a file now,
        # skills/brain-viewer/adapters.json, so an `**Adapter · <name>**` head dropped on any
        # canvas binds by name without a code change
        if adapters is None:
            return self._send(200, {"adapters": [], "rows": [], "error": _ADAPTER_ERR})
        return self._send(200, adapters.list_adapters(BRAIN))

    def _get_api_maps(self, u, q, body):
        # GET /api/maps
        # the maps picker: the canvases that are maps, by purpose, from skills/brain-viewer/maps-manifest.json, each with its live counts
        # 0.69.0: ?counts=0 is the fast list the Forge's picker paints from first; the counts follow from the full call
        return self._send(200, maps_api(counts=(q.get("counts") or ["1"])[0] not in ("0", "no", "false")))

    def _get_api_holons(self, u, q, body):
        # GET /api/holons
        return self._send(200, holons_api())

    def _get_api_status(self, u, q, body):
        # GET /api/status
        return self._send(200, status_api())

    def _get_api_projects(self, u, q, body):
        # GET /api/projects
        return self._send(200, projects_api())

    def _get_api_findings(self, u, q, body):
        # GET /api/findings
        # the findings queue (2026-09-17, piece 5): every open item carrying a #source: tag, across every ledger
        return self._send(200, findings_api(q.get("source", [""])[0], q.get("project", [""])[0], q.get("owner", [""])[0]))

    def _get_api_review(self, u, q, body):
        # GET /api/review
        # the rating surface (2026-09-17, T-0166): the cards waiting to be rated, the counter, and the rule the
        # cards were built by -- so the page never has to describe the rule in its own words
        return self._send(200, review_api())

    def _get_api_today_tasks(self, u, q, body):
        # GET /api/today/tasks
        # the Today page's third block (2026-09-18, T-0185, layout A): every open task of the owner's across the
        # ledgers regardless of date, grouped by project. `?app=1` answers with the review-queue count ALONE --
        # the foot line -- so a slow call to the PF App never holds up the list above it.
        if (q.get("app", [""])[0] or "") in ("1", "yes", "true"):
            return self._send(200, {"app": app_suggested()})
        out = today_tasks_api()
        # 0.71.0, the Now band: ?thread=<subject file> or ?project=<holon id>, the page the person last opened
        out["now"] = today_now((q.get("thread") or [""])[0] or None, (q.get("project") or [""])[0] or None)
        return self._send(200, out)

    def _get_api_today_undo(self, u, q, body):
        # GET /api/today/undo
        # 0.71.0: the day's presses, newest first, each with the item as it reads now; an undone one stays, marked
        return self._send(200, undo_list())

    def _get_api_today_waiting(self, u, q, body):
        # GET /api/today/waiting
        # 0.71.0: what another person moves next (the Today direction rule 2), oldest wait first
        return self._send(200, waiting_others_api())

    def _get_api_today_visit(self, u, q, body):
        # GET /api/today/visit
        # 0.81.0: the marks of what is new since the previous visit, read without recording an opening (a re-read)
        return self._send(200, today_visit(False))

    def _get_api_today_pick(self, u, q, body):
        # GET /api/today/pick
        # 0.85.0: the agent's pick, the first band on Today (context/today-pick.json, written by skills/today-pick/pick.py)
        return self._send(200, today_pick_api())

    def _post_api_today_visit(self, u, q, body):
        # POST /api/today/visit
        # 0.81.0: the Today page opened: kept in viewer/today-visits.json (ten minutes is one visit), then the marks
        out = today_visit(True)
        return self._send(500 if out.get("error") else 200, out)

    def _get_api_whats_new(self, u, q, body):
        # GET /api/whats-new
        # 0.91.0: Today's Changed since you last looked band: the viewer's version and the one seen, the newest two
        # entries of the what's-new page, and the notes the runs wrote since the previous visit
        return self._send(200, whats_new_api())

    def _post_api_whats_new_seen(self, u, q, body):
        # POST /api/whats-new/seen
        # 0.91.0: the running version is kept as seen (viewer/whats-new-seen.json), so the band folds and the dot goes
        code, out = whats_new_mark_seen()
        return self._send(code, out)

    def _post_api_today_undo(self, u, q, body):
        # POST /api/today/undo
        # 0.71.0: {n} takes back that press and every later one on its item today; {ledger, id} every press on the item today
        data = json.loads(body or "{}") or {}
        code, out = undo_apply(data.get("n"), data.get("ledger") or data.get("project"), data.get("id"))
        return self._send(code, out)

    def _post_api_today_waiting_action(self, u, q, body):
        # POST /api/today/waiting/action
        # 0.71.0: {ledger, id, action: nudge|drop, text?} on a row of the waiting card
        data = json.loads(body or "{}") or {}
        code, out = waiting_act(data.get("ledger") or data.get("project"), data.get("id"), str(data.get("action") or ""), data.get("text"))
        return self._send(code, out)

    def _get_api_pending(self, u, q, body):
        # GET /api/pending /api/calls /api/landed
        # the Today page's three outside halves (2026-09-16, T-0150): what the app holds for review, today's
        # calls with their preps, and what landed in the transcript folders. Read at request time, stored nowhere.
        if u.path == "/api/landed":
            return self._send(200, landed_api())
        if PROPOSE:
            return self._send(403, {"error": "not part of a team copy: the app proxy is off here, and people/ and the preps do not travel"})
        return self._send(200, pending_api() if u.path == "/api/pending" else calls_api())

    def _get_api_badges(self, u, q, body):
        # GET /api/badges
        # the notification counts: open items waiting on the owner, per person and per project. Read by every panel's nav
        # and, next, by the bubbles home (ideas E16). people/ is absent in a team copy, so `people` is simply empty there.
        return self._send(200, badges_api())

    def _get_api_waiting(self, u, q, body):
        # GET /api/waiting
        # what the home page pins on top: the same open-for-the-owner rows, grouped by project (2026-09-09, the filtering rule)
        return self._send(200, waiting_api())

    def _get_api_quests(self, u, q, body):
        # GET /api/quests
        # the quest log (2026-09-09, step 2c): what is waiting to be tested, and the timeline of what is done
        return self._send(200, quests_api())

    def _get_api_stages(self, u, q, body):
        # GET /api/stages
        # the stage line (2026-09-09, T-0064): the Straight-line milestone read back as an ordered build order
        return self._send(200, stages_api())

    def _get_api_docasks(self, u, q, body):
        # GET /api/docasks
        # the section asks on one document (2026-09-09, the Reader): open ledger items linking it, with their heading fragments
        return self._send(200, doc_asks(q.get("path", [""])[0]))

    def _get_api_notes(self, u, q, body):
        # GET /api/notes
        # what the notepad has written, newest first: the panel lists them so a note can be reached again (T-0074)
        try:
            n = max(1, min(50, int((q.get("limit") or ["8"])[0])))
        except ValueError:
            n = 8
        return self._send(200, notes_api(n))

    def _get_api_note(self, u, q, body):
        # GET /api/note
        # ONE note, opened to be edited (2026-09-16, T-0146): the header lines, the body, the pictures under it
        row = note_read(q.get("path", [""])[0])
        if not row:
            return self._send(404, {"error": "no such note in %s/" % CAPTURE_REL})
        return self._send(200, row)

    def _get_api_glossary(self, u, q, body):
        # GET /api/glossary
        # the vocabulary (2026-09-09, step 2): parsed from the markdown seed on every call, so the owner's edit is live
        # on the next reload. Every page reads it for the hover definitions; /glossary renders it whole.
        return self._send(200, glossary_api())

    def _get_api_graph(self, u, q, body):
        # GET /api/graph
        # the bubbles (2026-09-09, ideas E14 + E16): one graph joined at read time; a team copy gets projects, documents and the copy itself
        return self._send(200, graph_api())

    def _get_api_chats(self, u, q, body):
        # GET /api/chats /api/chat
        # chat runs on the owner's machine and account (rules §4, 2026-09-09): a team copy has no chat at all
        if PROPOSE:
            return self._send(403, {"error": "Chat runs on the owner's machine; in a team copy, use your own Claude Code in this folder"})
        if u.path == "/api/chats":
            return self._send(200, chats_api())
        row, err = chat_api((q.get("id") or [""])[0].strip())
        return self._send(404 if err else 200, {"error": err} if err else row)

    def _get_api_agents(self, u, q, body):
        # GET /api/agents /api/session
        # Read-only, and this machine only: the transcripts are private to it and never travel with a team copy.
        if PROPOSE:
            return self._send(403, {"error": "the Agents panel is not available in a team copy: session transcripts stay on the machine that ran them"})
        if u.path == "/api/agents":
            return self._send(200, agents_api())
        # one session read back, read-only: what a double-click on a bubble opens (2026-09-10, T-0117)
        row, err = session_view((q.get("id") or [""])[0].strip())
        return self._send(404 if err else 200, {"error": err} if err else row)

    def _get_api_people(self, u, q, body):
        # GET /api/people /api/person /api/preps /api/groups /api/people/week
        # 0.87.1: a team copy holds people cards since the export's people tier (2026-10-21), so these read there too, and
        # each finds only what the copy holds: the cards, the ledgers' open items about a person; no preps, call threads or
        # calls, which never travel (preps() and the groups answer empty when their files are absent). Writes stay requests.
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

    def _get_api_circle(self, u, q, body):
        # GET /api/circle (0.73.0): both circle files; ?through=<slug> only the rows that card holds and its opportunities
        if PROPOSE:
            return self._send(403, {"error": "the circle is not part of a team copy"})
        if ((q.get("view") or [""])[0] or "").strip() == "opportunities":
            return self._send(200, circle_opps_api())     # 0.74.0: the opportunities page and the home instrument
        return self._send(200, circle_api(((q.get("through") or [""])[0] or "").strip() or None))

    def _get_api_resolve(self, u, q, body):
        # GET /api/resolve
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

    def _get_api_app(self, u, q, body):
        # GET /api/app/*
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
        return _FALLTHROUGH

    def do_PUT(self):
        u = urllib.parse.urlparse(self.path)
        self._autosend = u.path in ANSWERS_AUTOSEND_ROUTES
        q = urllib.parse.parse_qs(u.query)
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8")
        self._clen = n
        try:
            for h in route_handlers("PUT", u.path):
                if h(self, u, q, body) is not _FALLTHROUGH:
                    return
            return self._send(404, {"error": "no such route"})
        except json.JSONDecodeError as e:
            return self._send(400, {"error": "not valid JSON: %s" % e})
        except Exception as e:
            return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

    def _put_api_manifest(self, u, q, body):
        # PUT /api/manifest
        data = json.loads(body)
        if PROPOSE:
            req = propose("manifest", MANIFEST_REL, {"manifest": data})
            return self._send(202, {"proposed": True, "request": req, "kind": "manifest", "target": MANIFEST_REL})
        ap = os.path.join(BRAIN, MANIFEST_REL.replace("/", os.sep))
        with open(ap, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2); f.write("\n")
        return self._send(200, {"ok": True, "path": MANIFEST_REL})

    def _put_api_file(self, u, q, body):
        # PUT /api/file
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

    def _put_api_notepad(self, u, q, body):
        # PUT /api/notepad
        n = self._clen
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

    def _put_api_home_layout(self, u, q, body):
        # PUT /api/home/layout
        # the home page's own layout, saved for whoever this copy belongs to. It says nothing about the brain, so
        # it is written in place in a team copy too (each copy holds its own member's file, never the owner's).
        res = home_layout_write(json.loads(body or "{}"))
        return self._send(400 if res.get("error") else 200, res)

    def _put_api_tasks(self, u, q, body):
        # PUT /api/tasks
        data = json.loads(body)
        proj = (q.get("project") or [data.get("project", "")])[0]
        args = dict(text=data.get("text"), owner=data.get("owner"), to=data.get("to"), frm=data.get("from"),
                    due=data.get("due") or None, milestone=data.get("milestone") or None,
                    links=[l for l in (data.get("links") or []) if l], tags=[x for x in (data.get("tags") or []) if x],
                    people=[p for p in (data.get("people") or []) if p],   # who the item concerns (validated against people/ by tasks.py)
                    id=data.get("id"), by=data.get("by"), reason=data.get("reason"),
                    until=data.get("until"),                                # hold: the day the task comes back (T-0108)
                    note=data.get("note"),                                  # the "keep in mind" line an item can carry (step 2c)
                    steps=data.get("steps"), tick=data.get("tick"), untick=data.get("untick"),   # 0.86.0: the steps on a task, and one tick
                    source=data.get("source"))                              # who filed it: the home prompt box files as home-prompt (0.42.0, T-0227)
        try:
            path, rel = ledger.resolve(proj)
            if PROPOSE:
                # exactly what would have gone to ledger.apply(path, rel, action, **args); pull.py replays it on the canonical ledger
                action = data.get("action", "")
                if action not in ("add", "ask", "done", "reopen", "block", "answer", "people", "link", "hold", "steps"):
                    raise ledger.LedgerError("unknown action %r" % action)
                req = propose("tasks", rel, {"action": action, "args": {k: v for k, v in args.items() if v not in (None, [], "")}})
                return self._send(202, {"proposed": True, "request": req, "kind": "tasks", "target": rel, "project": proj})
            # 0.71.0: an answer, done, hold, note or reopen keeps the item as it stood, so the press can be undone today
            act_name = data.get("action", "")
            before = undo_before(path, data.get("id")) if act_name in UNDO_ACTIONS and data.get("id") else None
            iid = ledger.apply(path, rel, act_name, agent="brain-viewer", **args)
            said = data.get("text") or data.get("note") or data.get("until") or ""
            if act_name == "steps" and (data.get("tick") or data.get("untick")):
                said = "step %s %s" % (data.get("tick") or data.get("untick"), "ticked" if data.get("tick") else "unticked")
            n = undo_record(rel, iid, act_name, before, "/api/tasks", said)
        except ledger.LedgerError as e:
            return self._send(400, {"error": str(e)})
        return self._send(200, {"ok": True, "id": iid, "project": proj, "path": rel, "undo": n})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        self._autosend = u.path in ANSWERS_AUTOSEND_ROUTES
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8")
        self._clen = n
        q = urllib.parse.parse_qs(u.query)
        try:
            for h in route_handlers("POST", u.path):
                if h(self, u, q, body) is not _FALLTHROUGH:
                    return
            return self._send(404, {"error": "no such route"})
        except json.JSONDecodeError as e:
            return self._send(400, {"error": "not valid JSON: %s" % e})
        except Exception as e:
            return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

    def _post_api_studio(self, u, q, body):
        # POST /api/studio/*
        # the image studio (T-0235): generate, edit, candidate; 403 in a team copy, 502 with one line on a provider failure
        code, out = studio_api("POST", u.path, {}, body)
        return self._send(code, out)

    def _post_api_looks(self, u, q, body):
        # POST /api/looks
        n = self._clen
        # T-0208: {"name", "css", "replace"?, "activate"?} imports a look into looks/; {"active": name} picks one
        if n > LOOK_MAX_BYTES * 2 + 2000:
            return self._send(413, {"error": "a look may be at most %d bytes" % LOOK_MAX_BYTES})
        res = look_import(json.loads(body or "{}"))
        return self._send(400 if res.get("error") else 200, res)

    def _post_api_pending_action(self, u, q, body):
        # POST /api/pending/action
        # one press on an item of the review queue (2026-09-18, T-0017): {id, action: approve|reject}. It goes
        # to the app twice -- ?dryRun=1 first, then for real -- and a real write leaves one SYNCED line.
        data = json.loads(body or "{}")
        code, out = pending_act(data.get("id"), str(data.get("action") or ""))
        return self._send(code, out)

    def _post_api_pending_approve_all(self, u, q, body):
        # POST /api/pending/approve-all
        # approve all, one call of the review queue (0.65.0): pending_act per item, stopping at the first refusal
        data = json.loads(body or "{}")
        code, out = pending_approve_all(data.get("conversation"))
        return self._send(code, out)

    def _post_api_answers_submit(self, u, q, body):
        # POST /api/answers/submit
        # the send press (0.60.0; one floating button since 0.60.1): one batch into context/answers-inbox.md, composed here from the log, never
        # from the page; {ok: false, count: 0} and nothing written when nothing is pending
        try:
            data = json.loads(body or "{}") or {}
        except ValueError:
            data = {}
        code, out = answers_submit("by the Send answers press" if isinstance(data, dict) and data.get("press") else None)
        return self._send(code, out)

    def _post_api_brief_run(self, u, q, body):
        # POST /api/brief/run
        # Brief me / Refresh on the Workspace (0.63.0): skills/item-brief/brief.py started detached, one per item
        data = json.loads(body or "{}") or {}
        code, out = brief_run(data.get("item"), data.get("presses"))
        return self._send(code, out)

    def _post_api_sweep_run(self, u, q, body):
        # POST /api/sweep/run
        # Clear answered questions (0.60.0): start the question sweep detached, one run at a time
        code, out = sweep_run((json.loads(body or "{}") or {}).get("project"))
        return self._send(code, out)

    def _post_api_today_tasks_action(self, u, q, body):
        # POST /api/today/tasks/action
        # one press on a row of the Today page's open-tasks block: {ledger, id, action: done|hold}. The item is
        # read off the file again before anything is written, and tasks.py does the write and its own log line.
        data = json.loads(body or "{}")
        code, out = today_task_act(data.get("ledger") or data.get("project"), data.get("id"), str(data.get("action") or ""))
        return self._send(code, out)

    def _post_api_widgets_broken(self, u, q, body):
        # POST /api/widgets/broken
        # a home tile broke (T-0217): {id, error, where, stack}. Kept in memory for the widgets lamp, and one
        # finding on the brain-viewer ledger, keyed by widget and error so a repeat lands on the open item.
        code, out = widget_broken(json.loads(body or "{}"))
        return self._send(code, out)

    def _post_api_mantras(self, u, q, body):
        # POST /api/mantras
        # one line added to the pool under the date (0.38.0): {text, author, source}. A team copy proposes it.
        data = json.loads(body or "{}")
        out = mantra_add(data)
        return self._send(400 if out.get("error") else 200, out)

    def _post_api_call_tick(self, u, q, body):
        # POST /api/call/tick /api/call/notes
        # the call screen's two writes (0.47.0): a question ticked, the notes section saved, both into the prep
        data = json.loads(body or "{}")
        code, out = call_tick(data) if u.path.endswith("/tick") else call_notes(data)
        return self._send(code, out)

    def _post_api_survey_answer(self, u, q, body):
        # POST /api/survey/answer
        # the survey page's one write (0.78.0): one item's Answer line, through the Reader's own gate and steps
        try:
            data = json.loads(body or "{}")
        except ValueError:
            return self._send(400, {"error": "the body is not JSON"})
        code, out = survey_answer(data if isinstance(data, dict) else {})
        return self._send(code, out)

    def _post_api_requests_send(self, u, q, body):
        # POST /api/requests/send
        # the From band's send (0.88.0): the copy's requests folder added, committed and pushed, as send-requests does
        code, out = requests_send()
        return self._send(code, out)

    def _post_api_share(self, u, q, body):
        # POST /api/share {member, path, go, why} and POST /api/share/section {path, line, text, private}
        # the sharing checklist's two writes (0.87.0): a tick on a folder, file, piece or card; a card section's mark
        try:
            data = json.loads(body or "{}")
        except ValueError:
            return self._send(400, {"error": "the body is not JSON"})
        data = data if isinstance(data, dict) else {}
        code, out = share_section(data) if u.path.endswith("/section") else share_set(data)
        return self._send(code, out)

    def _post_api_friction_answer(self, u, q, body):
        # POST /api/friction/answer
        # his press on a friction card (0.80.0): written into the record through skills/patterns/patterns.py, then sent
        try:
            data = json.loads(body or "{}")
        except ValueError:
            return self._send(400, {"error": "the body is not JSON"})
        code, out = friction_answer(data if isinstance(data, dict) else {})
        return self._send(code, out)

    def _post_api_circle_edit(self, u, q, body):
        # POST /api/circle/edit (0.73.0): a circle row's what, an opportunity's stage or next; one log line each
        if PROPOSE:
            return self._send(403, {"error": "the circle is not part of a team copy"})
        code, out = circle_edit(json.loads(body or "{}"))
        return self._send(code, out)

    def _post_api_prep(self, u, q, body):
        # POST /api/prep
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

    def _post_api_chat_send(self, u, q, body):
        # POST /api/chat/send /api/chat/stop /api/chat/adopt
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

    def _post_api_exchange_pull(self, u, q, body):
        # POST /api/exchange/pull
        # the inbox's one action (2026-09-16, T-0171): fast-forward the configured exchanges and report what
        # arrived. skills/exchange/pull.py does the work; nothing is applied to the brain either way.
        if PROPOSE:
            return self._send(403, {"error": "an exchange is between two owners' own machines; a team copy has none"})
        code, out = exchange_pull((json.loads(body or "{}") or {}).get("exchange"))
        return self._send(code, out)

    def _post_api_forge_new(self, u, q, body):
        # POST /api/forge/new
        # the Forge's picker (2026-09-09, T-0041): a new machine = one canvas with one empty cell, in a family folder
        data = json.loads(body or "{}")
        rel, err = forge_new(data.get("family"), data.get("name"))
        if err:
            return self._send(400, {"error": err})
        if PROPOSE:
            return self._send(202, {"proposed": True, "request": rel, "kind": "file"})
        return self._send(200, {"ok": True, "path": rel})

    def _post_api_forge_delete(self, u, q, body):
        # POST /api/forge/delete
        # 0.67.0: delete a one-cell drawing that was never edited (the scratch family's test drawings, mostly)
        data = json.loads(body or "{}")
        rel, err = forge_delete(data.get("path"))
        if err:
            return self._send(400, {"error": err})
        return self._send(200, {"ok": True, "path": rel})

    def _post_api_live_bindings(self, u, q, body):
        # POST /api/live/bindings
        # the live maps' one write (2026-09-09, T-0042): "save bindings" copies the resolved bindings into the sibling .forge.json.
        # The server resolves them itself; the page sends only the canvas path, so nothing a page sends shapes the file.
        data = json.loads(body or "{}")
        row, err = live_save_bindings(data.get("path"))
        if err:
            return self._send(404 if err == "canvas not found" else 403, {"error": err})
        return self._send(202 if row.get("proposed") else 200, row)

    def _post_api_notepad(self, u, q, body):
        # POST /api/notepad
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

    def _post_api_paste(self, u, q, body):
        # POST /api/paste
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
        where = {"chat": "chat", "item-note": "note on an item"}.get(str(data.get("kind") or ""), "notepad")   # 0.90.0: T-0354
        note = log_line("%s -- picture pasted in the %s (brain-viewer, %d bytes)" % (rel, where, len(blob)), action="CREATED")
        return self._send(200, {"ok": True, "path": rel, "bytes": len(blob),
                                "url": "/api/image?path=" + urllib.parse.quote(rel), "log": note})

    def _post_api_attach(self, u, q, body):
        # POST /api/attach
        # a picture attached to a question or an answer (2026-09-22, T-0219): kept next to the item's ledger
        # and linked onto the item through tasks.py (attach_save), which writes the one log line itself.
        if PROPOSE:
            return self._send(403, {"error": "a team copy cannot add files to the brain: send the picture to the owner instead"})
        data = json.loads(body or "{}")
        code, out = attach_save(data.get("ledger") or data.get("project"), data.get("item") or data.get("id"),
                                data.get("name"), data.get("data"))
        return self._send(code, out)

    def _post_api_reply(self, u, q, body):
        # POST /api/reply
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
            before = undo_before(path, iid)                            # 0.71.0: a note can be taken back today
            ledger.apply(path, rel, "note", agent="brain-viewer", id=iid, note=line)
            n = undo_record(rel, it["id"], "note", before, "/api/reply", text)
        except ledger.LedgerError as e:
            return self._send(400, {"error": str(e)})
        return self._send(200, {"ok": True, "id": iid, "project": proj, "path": rel, "note": line, "undo": n})

    def _post_api_review(self, u, q, body):
        # POST /api/review
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

    def _post_api_note(self, u, q, body):
        # POST /api/note
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

# ---- the route table (0.68.0, the review's finding 8) ----
# do_GET, do_PUT and do_POST were one if-chain each (69 branches in GET alone). Each branch is now a method of H, and this
# table says which path reaches which, in the order the chain tested them: a handler that runs off its end without
# answering returns _FALLTHROUGH and the next route that matches the path is tried, exactly as the chain fell through.
# "exact" rows are looked up in a dict; "prefix" rows match by startswith. The order of the rows is the order of the chain.
ROUTE_ROWS = [
    ('GET', "exact", ('/api/routes',), H._get_api_routes),
    ('GET', "exact", tuple(REDIRECT_ROUTES), H._get_redirect_routes),
    ('GET', "exact", tuple(PAGES), H._get_pages),
    ('GET', "prefix", '/raw/', H._get_raw),
    ('GET', "exact", ('/api/mtime',), H._get_api_mtime),
    ('GET', "exact", ('/api/preview/pages',), H._get_api_preview_pages),
    ('GET', "exact", ('/api/artifacts',), H._get_api_artifacts),
    ('GET', "exact", ('/api/usage',), H._get_api_usage),
    ('GET', "exact", ('/api/share',), H._get_api_share),
    ('GET', "exact", ('/api/from-owner',), H._get_api_from_owner),
    ('GET', "exact", ('/api/titles',), H._get_api_titles),
    ('GET', "exact", ('/api/replies',), H._get_api_replies),
    ('GET', "exact", ('/api/work',), H._get_api_work),
    ('GET', "exact", ('/api/brief/status',), H._get_api_brief_status),
    ('GET', "exact", ('/api/thread',), H._get_api_thread),
    ('GET', "exact", ('/api/threads',), H._get_api_threads),
    ('GET', "exact", ('/api/in-progress',), H._get_api_in_progress),
    ('GET', "exact", ('/api/answers/pending',), H._get_api_answers_pending),
    ('GET', "exact", ('/api/settings',), H._get_api_settings),
    ('GET', "exact", ('/api/sweep/status',), H._get_api_sweep_status),
    ('GET', "exact", ('/api/health',), H._get_api_health),
    ('GET', "exact", ('/api/search',), H._get_api_search),
    ('GET', "exact", ('/api/files',), H._get_api_files),
    ('GET', "exact", ('/api/file-raw',), H._get_api_file_raw),
    ('GET', "exact", ('/api/mode',), H._get_api_mode),
    ('GET', "prefix", '/api/studio/', H._get_api_studio),
    ('GET', "exact", ('/api/looks',), H._get_api_looks),
    ('GET', "exact", ('/api/widgets',), H._get_api_widgets),
    ('GET', "exact", ('/api/home/layout',), H._get_api_home_layout),
    ('GET', "exact", ('/api/help',), H._get_api_help),
    ('GET', "exact", ('/api/calendar/week',), H._get_api_calendar_week),
    ('GET', "exact", ('/api/call',), H._get_api_call),
    ('GET', "exact", ('/api/survey',), H._get_api_survey),
    ('GET', "exact", ('/api/friction',), H._get_api_friction),
    ('GET', "exact", ('/api/moved',), H._get_api_moved),
    ('GET', "exact", ('/api/system',), H._get_api_system),
    ('GET', "exact", ('/api/events',), H._get_api_events),
    ('GET', "exact", ('/api/mantras',), H._get_api_mantras),
    ('GET', "exact", ('/api/requests',), H._get_api_requests),
    ('GET', "exact", ('/api/exchange',), H._get_api_exchange),
    ('GET', "exact", ('/favicon.ico',), H._get_favicon_ico),
    ('GET', "prefix", '/static/', H._get_static),
    ('GET', "exact", ('/api/manifest',), H._get_api_manifest),
    ('GET', "exact", ('/api/file',), H._get_api_file),
    ('GET', "exact", ('/api/image',), H._get_api_image),
    ('GET', "exact", ('/api/canvas',), H._get_api_canvas),
    ('GET', "exact", ('/api/canvases',), H._get_api_canvases),
    ('GET', "exact", ('/api/forge/states',), H._get_api_forge_states),
    ('GET', "exact", ('/api/forge/scratch',), H._get_api_forge_scratch),
    ('GET', "exact", ('/api/forge',), H._get_api_forge),
    ('GET', "exact", ('/api/forge/fields',), H._get_api_forge_fields),
    ('GET', "exact", ('/api/live',), H._get_api_live),
    ('GET', "exact", ('/api/adapter',), H._get_api_adapter),
    ('GET', "exact", ('/api/adapters',), H._get_api_adapters),
    ('GET', "exact", ('/api/maps',), H._get_api_maps),
    ('GET', "exact", ('/api/holons',), H._get_api_holons),
    ('GET', "exact", ('/api/status',), H._get_api_status),
    ('GET', "exact", ('/api/projects',), H._get_api_projects),
    ('GET', "exact", ('/api/findings',), H._get_api_findings),
    ('GET', "exact", ('/api/review',), H._get_api_review),
    ('GET', "exact", ('/api/today/tasks',), H._get_api_today_tasks),
    ('GET', "exact", ('/api/today/undo',), H._get_api_today_undo),
    ('GET', "exact", ('/api/today/waiting',), H._get_api_today_waiting),
    ('GET', "exact", ('/api/today/visit',), H._get_api_today_visit),
    ('GET', "exact", ('/api/today/pick',), H._get_api_today_pick),
    ('GET', "exact", ('/api/whats-new',), H._get_api_whats_new),
    ('GET', "exact", ('/api/pending', '/api/calls', '/api/landed'), H._get_api_pending),
    ('GET', "exact", ('/api/badges',), H._get_api_badges),
    ('GET', "exact", ('/api/waiting',), H._get_api_waiting),
    ('GET', "exact", ('/api/quests',), H._get_api_quests),
    ('GET', "exact", ('/api/stages',), H._get_api_stages),
    ('GET', "exact", ('/api/docasks',), H._get_api_docasks),
    ('GET', "exact", ('/api/notes',), H._get_api_notes),
    ('GET', "exact", ('/api/note',), H._get_api_note),
    ('GET', "exact", ('/api/glossary',), H._get_api_glossary),
    ('GET', "exact", ('/api/graph',), H._get_api_graph),
    ('GET', "exact", ('/api/chats', '/api/chat'), H._get_api_chats),
    ('GET', "exact", ('/api/agents', '/api/session'), H._get_api_agents),
    ('GET', "exact", ('/api/people', '/api/person', '/api/preps', '/api/groups', '/api/people/week'), H._get_api_people),
    ('GET', "exact", ('/api/circle',), H._get_api_circle),
    ('GET', "exact", ('/api/resolve',), H._get_api_resolve),
    ('GET', "prefix", '/api/app/', H._get_api_app),
    ('PUT', "exact", ('/api/manifest',), H._put_api_manifest),
    ('PUT', "exact", ('/api/file',), H._put_api_file),
    ('PUT', "exact", ('/api/notepad',), H._put_api_notepad),
    ('PUT', "exact", ('/api/home/layout',), H._put_api_home_layout),
    ('PUT', "exact", ('/api/tasks',), H._put_api_tasks),
    ('PUT', "exact", ('/api/settings',), H._put_api_settings),
    ('POST', "prefix", '/api/studio/', H._post_api_studio),
    ('POST', "exact", ('/api/looks',), H._post_api_looks),
    ('POST', "exact", ('/api/pending/action',), H._post_api_pending_action),
    ('POST', "exact", ('/api/pending/approve-all',), H._post_api_pending_approve_all),
    ('POST', "exact", ('/api/answers/submit',), H._post_api_answers_submit),
    ('POST', "exact", ('/api/answers/away',), H._post_api_answers_away),
    ('POST', "exact", ('/api/answers/here',), H._post_api_answers_here),
    ('POST', "exact", ('/api/brief/run',), H._post_api_brief_run),
    ('POST', "exact", ('/api/sweep/run',), H._post_api_sweep_run),
    ('POST', "exact", ('/api/today/tasks/action',), H._post_api_today_tasks_action),
    ('POST', "exact", ('/api/today/undo',), H._post_api_today_undo),
    ('POST', "exact", ('/api/today/waiting/action',), H._post_api_today_waiting_action),
    ('POST', "exact", ('/api/today/visit',), H._post_api_today_visit),
    ('POST', "exact", ('/api/whats-new/seen',), H._post_api_whats_new_seen),
    ('POST', "exact", ('/api/widgets/broken',), H._post_api_widgets_broken),
    ('POST', "exact", ('/api/mantras',), H._post_api_mantras),
    ('POST', "exact", ('/api/call/tick', '/api/call/notes'), H._post_api_call_tick),
    ('POST', "exact", ('/api/survey/answer',), H._post_api_survey_answer),
    ('POST', "exact", ('/api/share', '/api/share/section'), H._post_api_share),
    ('POST', "exact", ('/api/requests/send',), H._post_api_requests_send),
    ('POST', "exact", ('/api/friction/answer',), H._post_api_friction_answer),
    ('POST', "exact", ('/api/circle/edit',), H._post_api_circle_edit),
    ('POST', "exact", ('/api/prep',), H._post_api_prep),
    ('POST', "exact", ('/api/chat/send', '/api/chat/stop', '/api/chat/adopt'), H._post_api_chat_send),
    ('POST', "exact", ('/api/exchange/pull',), H._post_api_exchange_pull),
    ('POST', "exact", ('/api/forge/new',), H._post_api_forge_new),
    ('POST', "exact", ('/api/threads/new',), H._post_api_threads_new),
    ('POST', "exact", ('/api/forge/delete',), H._post_api_forge_delete),
    ('POST', "exact", ('/api/live/bindings',), H._post_api_live_bindings),
    ('POST', "exact", ('/api/notepad',), H._post_api_notepad),
    ('POST', "exact", ('/api/paste',), H._post_api_paste),
    ('POST', "exact", ('/api/attach',), H._post_api_attach),
    ('POST', "exact", ('/api/reply',), H._post_api_reply),
    ('POST', "exact", ('/api/review',), H._post_api_review),
    ('POST', "exact", ('/api/note',), H._post_api_note),
]
ROUTES = {}          # verb -> {"exact": {path: [(order, handler)]}, "prefix": [(order, prefix, handler)]}
for _i, (_verb, _kind, _value, _fn) in enumerate(ROUTE_ROWS):
    _t = ROUTES.setdefault(_verb, {"exact": {}, "prefix": []})
    if _kind == "exact":
        for _p in _value:
            _t["exact"].setdefault(_p, []).append((_i, _fn))
    else:
        _t["prefix"].append((_i, _value, _fn))


def route_handlers(verb, path):
    """The handlers whose route matches this path, in the chain's order."""
    t = ROUTES.get(verb) or {"exact": {}, "prefix": []}
    hits = list(t["exact"].get(path, ())) + [(i, fn) for i, p, fn in t["prefix"] if path.startswith(p)]
    return [fn for _i, fn in sorted(hits, key=lambda x: x[0])]


def route_list():
    """Every route the server answers, as data: [{verb, path, match, handler}] in the chain's order (GET /api/routes)."""
    out = []
    for verb, kind, value, fn in ROUTE_ROWS:
        for p in (value if kind == "exact" else (value,)):
            out.append({"verb": verb, "path": p, "match": kind, "handler": fn.__name__})
    return out



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
    ap.add_argument("--init", action="store_true", help="create, in that brain folder, whatever the viewer needs to boot (registry, manifests, settings, forge root + example drawing, log, a first ledger), then start the viewer on --port. Never overwrites a file that is already there. When the port already answers (your own viewer on 8765), the folder is still filled in and nothing is started")
    ap.add_argument("--supervise", action="store_true", help="run the server as a child and restart it whenever it exits non-zero (2, 4, 8, 15, 30, 60 seconds, reset after ten minutes up). Every exit and restart is recorded in %s" % CRASH_REL)
    args = ap.parse_args()
    global ARGS
    ARGS = args
    if args.supervise:
        return supervise([a for a in sys.argv[1:] if a != "--supervise"])
    if args.init:
        # 0.90.0: the folder is filled in before the port is looked at, so --init makes a brain while another viewer runs
        # (it used to stop at the probe below and create nothing whenever 8765 answered)
        init_brain()
    if port_answers(args.port, args.host):
        # never a second server on a port that answers (Windows would let it bind, and the stale one keeps answering)
        sys.stderr.write("port %s already answers: a viewer is running there, so this one did not start%s\n"
                         % (args.port, "; the brain folder above is filled in, so start it on a free port with --port" if args.init else ""))
        return 0
    if not args.init and not os.path.isdir(BRAIN):
        sys.stderr.write("no such brain folder: %s\nCreate it, or run again with --init to fill it in.\n" % BRAIN)
        return 2
    # 0.68.0: bind before anything else is written, exclusively; a port another process holds ends this start in one line
    try:
        srv = ExclusiveServer((args.host, args.port), H)
    except OSError as e:
        sys.stderr.write("port %s is held by another process (%s); this viewer did not start\n" % (args.port, e.strerror or e))
        return 3
    # the chat's default model is checked against the installed CLI once, in the background, so a refused id falls back to
    # opus with a note instead of failing a turn (2026-09-17, T-0187)
    threading.Thread(target=probe_models_once, daemon=True).start()
    global PREV_RUN
    PREV_RUN = prev_run()             # read BEFORE this run writes its own START line
    install_exit_recorders()          # T-0181: no exit without a line in the crash log
    ensure_user_layer()               # 0.48.0: viewer/ exists before the first request reads it
    threading.Thread(target=answers_hold_resume, name="answers-hold-resume", daemon=True).start()   # 0.92.0
    write_status()
    mode = ("PROPOSE MODE: team copy of member %s, every save becomes a request under %s/%s/" % (MEMBER, REQUESTS_REL, MEMBER)) if PROPOSE else "normal mode"
    print("Brain Viewer v%s -- today http://127.0.0.1:%d/  home (the board) /home  chat /chat  projects /projects  people /people  mentee content /mentee  threads /threads  from Claude /from-claude  forge /forge  files /files  (brain: %s%s; %s; claude %s)  Ctrl+C to stop"
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
