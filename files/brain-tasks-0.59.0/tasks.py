#!/usr/bin/env python
"""tasks.py -- the project ledger: tasks and questions, one file per project, named by the holon registry.

WHY (asked for by the owner on 2026-09-04): a task list Claude writes to, one project file each, where tasks pass
between Claude and the user so the work is collaborative, and questions that need answers show up in the viewer with
their files linked, easy to answer, while the same agent keeps working on whatever it can until a question is
answered. Brain-side first; the viewer's Projects panel second; the PF App
merge third. The ledger is a declaration the viewer renders (derived never drawn); progress is counted at read time,
never stored.

THE FILE (one item per line, grouped under "## Milestone — <name>" headings; "## Inbox" is the default group):
  - [ ] T-0007 2026-09-04 @zak · Get the cover's title font link · due:2026-09-06 · #design · → brain-viewer-holon/design-directions/references/
  - [x] T-0003 2026-09-04 @claude · Build the Holons panel · done:2026-09-04
  - [-] T-0009 2026-09-04 @claude · Restyle to the exact title face · blocked:Q-0002
  - [?] Q-0002 2026-09-04 @claude → @zak · Which title face: the cover's exact one, or keep Grenze Gotisch? · → skills/brain-viewer/viewer-tokens.css
  - [a] Q-0001 2026-09-04 @claude → @zak · May the viewer check boxes in this file? · answer:2026-09-04 yes, logged, same write path
  - [?] Q-0011 2026-09-09 @claude → @zak · Does Collin's placement wait on the training layer? · people:collin-green · → people/collin-green.md
  - [ ] T-0108 2026-09-10 @zak · Put this down for a few days · until:2026-09-13
States: [ ] open · [x] done · [-] blocked · [?] question open · [a] question answered.
ON HOLD (2026-09-10: the owner asked to put tasks on hold for a few days rather than check them off). An
open task may carry `until:YYYY-MM-DD`: it is still open and still owed, it simply leaves the lists that ask for it now
(the home's Waiting on you, /projects, /people, the quest log) until that date, then comes back on its own. `hold` writes
the field (three days by default, `--until` for a date), `reopen` clears it, `done` clears it with everything else, and
`list` leaves held items out unless `--held` is passed. A held item is not blocked: nothing is waiting on anyone else.
A DAY ON AN ITEM (2026-09-16, T-0150). `due:YYYY-MM-DD` is what the Brain Viewer's Today page reads into "Due today or
earlier", and it was the one field with no verb behind it: a due date could only be set at birth, on `add`. `today` puts
one on an item that already exists -- the clock's own day with no argument, another day with `--due YYYY-MM-DD`, and
`--due none` (or `clear`) takes the day back off -- and `ask` now accepts `--due` so a question can be owed by a day the
same way a task is. It works on a task or a question, open or not; it does not change state, so a day on a done item is
a record, not a reopen. There is still no argument that accepts "today" as a literal: the clock is read at write time.
Segments split on " · ". Segment 0 = state, id, created date, owner (questions add "→ @to"). Segment 1 = the text.
Every later segment is one of: key:value (due, done, blocked, unblocked, until, answer, app, people, note, repeats), "→ link" (a path, a route, or a [[wikilink]]), "#tag".
`note:` is one line to keep in mind while doing the item; `→ link` on a DONE item is the result -- what it built -- and the Brain Viewer's timeline is those links read back.

FINDINGS (2026-09-17, piece 1 of deliverables/findings-routing-design-2026-09-17.md). The brain has six producers of
findings -- the night agent, brain-lint, the dispatcher, Extended Rounds, holon handoffs, the two inboxes -- and until
today none of them wrote to the ledgers, so the same finding was raised five nights running with nothing recording that
it had been raised before. The rule: every finding becomes a ledger item at birth, and a REPEAT is a note on the open
item, never a second item. Three things carry it, all built on machinery that already existed:
  `--source <slug>`  on add / ask -> the tag `#source:<slug>`: WHO found it (night-agent-86, brain-lint, dispatcher,
                     handoff, extended-rounds-2026-10). A plain slug: letters, digits, `-`, `_`; no `#`, no spaces.
  `--key <value>`    on add / ask -> the tag `#key:<value>`: the PRODUCER'S OWN stable id for the finding, so the next
                     run recognises its own work (`L12:people/kyle-collins.md`, `R3:librarian`, `obs41`). Same rule plus
                     `/`, `:` and `.`. The match key is the producer's to choose and is meant to be conservative: when
                     in doubt it files a new item rather than repeating the wrong one.
  `repeat`           -> `repeats:N` on the item plus one dated line appended to its `note:`. `note` REPLACES the line
                     (it is one thing to keep in mind); `repeat` appends after " | ", so the history of a standing
                     finding reads in order on the item itself.
`list --source <prefix>` (prefix, so `--source night-agent` finds every run) and `list --key <value>` (exact) filter,
and `list --json` carries `source`, `key` and `repeats` on every item so the viewer's Findings view reads them without
re-parsing tags. `route <path>` answers WHICH LEDGER a finding belongs on -- the holon in the registry whose `path` is
the longest prefix of the file the finding names, brain-central when nothing matches -- so the six producers do not each
reimplement the mapping. Routing is read-only: it writes nothing and logs nothing.

A CALL-SCOPED ITEM (2026-09-18, viewer T-0192). The owner asked that what concerns one person's call stay out of the
day's tasks and sit inside that call's prep, unless it needs clarifying sooner, and that this hold for every call.
An item may carry `#call:<person-slug>`: it is still open and still owed, it simply
belongs in that person's NEXT CALL PREP rather than on the Brain Viewer's Today page, which leaves it out and says how
many are waiting in their preps. `--call <slug>` writes it on `add` / `ask`, the new `tag` verb puts it on an item that
already exists, and `list --call <slug>` is what the call prep's Carried block reads. The slug is a people/ card, one
person, validated the way `people:` is -- a group call has no single slug and stays untagged.

A TAG ON AN ITEM THAT EXISTS (2026-09-18). Every tag could be written at birth and never afterwards, so re-scoping an
item meant hand-editing a ledger line. `tag <id> --tag <value>` adds one if it is absent, `--remove` takes one off, and
`--call <slug>` is the same verb with the slug validated into `call:<slug>`. Nothing else on the line moves.

PEOPLE (2026-09-09: the owner asked that every question go to the specific place it belongs). An item may carry the people it concerns: `people:<slug>,<slug>`, each one a card in `people/` (validated on write;
no card, no tag -- the card is the truth about who exists, Correction #42). That is what routes a question to the person
it is about: the Brain Viewer's People panel shows a person's open questions and open @zak tasks first, and answers them
there. `--people` sets the field on `add` / `ask` and on the `people` action; `list --people <slug>` filters by it.
DATES COME FROM THE CLOCK AT WRITE TIME. There is no argument that accepts one (the log.py lesson).
Answering a question un-blocks every item that carries blocked:<that Q id>.

USAGE
  python skills/brain-tasks/tasks.py init   --project <holon-id> --name "Brain Viewer"      # create the file the registry names
  python skills/brain-tasks/tasks.py add    --project <holon-id> --owner @zak --text "..." [--due YYYY-MM-DD] [--milestone "Design"] [--link <path>]... [--tag design]... [--people slug,slug] [--note "keep in mind..."] [--source brain-lint] [--key "L12:people/x.md"] [--call <slug>]
  python skills/brain-tasks/tasks.py ask    --project <holon-id> --to @zak --text "..." [--from @claude] [--due YYYY-MM-DD] [--milestone ...] [--link ...]... [--tag ...]... [--people slug,slug] [--note "..."] [--source ...] [--key ...] [--call <slug>]
  python skills/brain-tasks/tasks.py people --project <holon-id> T-0003 --people john-kissell,dani-plumb   # set who an existing item concerns ("" clears it)
  python skills/brain-tasks/tasks.py tag    --project <holon-id> T-0053 --call collin-green    # this is raised on Collin's next call: off the Today page, into his call prep
  python skills/brain-tasks/tasks.py tag    --project <holon-id> T-0053 --tag design [--remove]   # put a plain #tag on an item that exists, or take one off
  python skills/brain-tasks/tasks.py done   --project <holon-id> T-0003 [T-0004 ...] [--link <what it built>]
  python skills/brain-tasks/tasks.py link   --project <holon-id> T-0003 --link /glossary                  # set or replace the RESULT link (the timeline reads it)
  python skills/brain-tasks/tasks.py note   --project <holon-id> T-0050 --note "what to watch while testing this"  # set the keep-in-mind line on an item that exists
  python skills/brain-tasks/tasks.py retext --project <holon-id> T-0050 --text "the item, said again"             # rewrite ONLY the words of an item; its id, date, owner and every field stay
  python skills/brain-tasks/tasks.py reassign --project <holon-id> T-0144 --owner @claude [--reason "why it moved"]  # move a TASK between owners; id, date, state and every field stay (a question is not reassignable)
  python skills/brain-tasks/tasks.py today  --project <holon-id> T-0150 [--due YYYY-MM-DD | --due none]  # put a day on an item: today by default, another day with --due, cleared with --due none
  python skills/brain-tasks/tasks.py hold   --project <holon-id> T-0108 [--until YYYY-MM-DD]   # put an open task down for a few days (default 3); it returns on its own
  python skills/brain-tasks/tasks.py reopen --project <holon-id> T-0003                        # also the way back from a hold
  python skills/brain-tasks/tasks.py block  --project <holon-id> T-0009 (--by Q-0002 | --reason "...")
  python skills/brain-tasks/tasks.py answer --project <holon-id> Q-0002 --text "..." [--by @zak]
  python skills/brain-tasks/tasks.py repeat <id> --source night-agent-86 [--text "what it looks like this time"]   # a finding raised again: repeats:N + a dated line on the note
  python skills/brain-tasks/tasks.py repeat --key "L12:people/x.md" --source brain-lint [--text "..."]  # ...found by the producer's own key instead (exit 3 = no open item, exit 4 = more than one)
  python skills/brain-tasks/tasks.py route  <brain-relative path> [--json]                    # which ledger a finding about that file belongs on: "<holon-id>\t<ledger file>". Read-only
  python skills/brain-tasks/tasks.py list   [--project <holon-id>] [--open] [--owner @zak] [--questions] [--people <slug>] [--call <slug>] [--source <prefix>] [--key <value>] [--held] [--json]   # no --project = every registered ledger
  python skills/brain-tasks/tasks.py check  [--project <holon-id>]                            # every registered ledger; exit 2 on a broken line
--project resolves through context/holon-registry.json (the holon's "tasks" field); --file <brain-relative path> bypasses it.
Every mutating call appends one MODIFIED line to context/log.md via log.py (agent = --agent, default brain-tasks).
The viewer's server imports this module and calls apply(); it never writes the file by hand.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# CODE = the folder this tool ships in (<code>/skills/brain-tasks/tasks.py); BRAIN = the folder whose ledgers it writes.
# They are the same until someone points the viewer at another brain, which is what BRAIN_ROOT says (serve.py sets it
# from --brain before it imports this module, and log.py reads the same variable). Independent of the working directory.
CODE = os.path.dirname(os.path.dirname(HERE))
BRAIN = os.environ.get("BRAIN_ROOT") or CODE
REGISTRY = os.path.join(BRAIN, "context", "holon-registry.json")
LOG_PY = os.path.join(CODE, "skills", "brain-log", "log.py")   # the tool travels with the code; it logs into BRAIN's own log (BRAIN_ROOT, below)
PEOPLE_DIR = os.path.join(BRAIN, "people")
# 0.48.0 of the viewer: the settings live in the brain's user layer, viewer/settings.json; the legacy place inside the
# viewer's code folder is still read for a brain the viewer has not been started on since the split.
VIEWER_SETTINGS = os.path.join(BRAIN, "viewer", "settings.json")
LEGACY_SETTINGS = os.path.join(BRAIN, "skills", "brain-viewer", "viewer-settings.json")
CODE_SETTINGS = os.path.join(CODE, "skills", "brain-viewer", "viewer-settings.json")
DEFAULT_OWNER = "@me"   # a brain with no `owner` setting answers to @me, never to one particular person


def owner_me():
    """The @name this brain treats as "me": viewer-settings.json's `owner` key, the same one the viewer reads -- the
    brain's own settings file first, the code copy's as the fallback. It is the DEFAULT and the label only -- an item's
    owner line stores whatever @name it was given, so a ledger written before the setting changed keeps reading exactly
    as it was written."""
    for ap in (VIEWER_SETTINGS, LEGACY_SETTINGS, CODE_SETTINGS):
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                o = str(json.load(f).get("owner") or "").strip()
            if o:
                return "@" + o.lstrip("@")
        except Exception:
            continue
    return DEFAULT_OWNER


OWNER = owner_me()
SEP = " · "
STATES = {" ": "open", "x": "done", "-": "blocked", "?": "question", "a": "answered"}
ITEM_RE = re.compile(r"^- \[( |x|-|\?|a)\] ([TQ]-\d{4}) (\d{4}-\d{2}-\d{2}) (@[\w:.-]+)(?: → (@[\w:.-]+))?(?: · (.*))?$")
HEAD_RE = re.compile(r"^## (?:Milestone — )?(.+?)\s*$")
FIELD_KEYS = ("due", "done", "blocked", "unblocked", "until", "answer", "app", "people", "note", "repeats")
HOLD_DAYS = 3          # a few days (2026-09-10) when `hold` is given no date
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,60}$")
# A FINDING'S TWO TAGS (2026-09-17). `source:` is who found it, `key:` is that producer's own stable id for the finding.
# Both ride the tag segment that already existed, so no ledger line changes shape. A tag may not carry a space (the
# parser would stop reading it as a tag) nor a `#` (it is the tag marker), which is what these refuse.
SOURCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,60}$")
KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./:-]{0,120}$")
SOURCE_TAG, KEY_TAG = "source:", "key:"
# A CALL-SCOPED ITEM (2026-09-18, viewer T-0192). The owner asked that what concerns one person's call stay out of the
# day's tasks and sit inside that call's prep, unless it needs clarifying sooner, for every call. The tag `#call:<person-slug>` is what says so: the item is still open and
# still owed, it simply belongs in that person's next call prep rather than on the Today page. It rides the tag segment
# that already existed, so no ledger line changes shape, and the slug is a people/ card like `people:` is.
CALL_TAG = "call:"
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./:-]{0,120}$")
DEFAULT_LEDGER = ("brain-central", "context/brain-central-tasks.md")   # where a finding lands when no holon path claims it


class LedgerError(Exception):
    pass


def today():
    return dt.date.today().isoformat()


def registry():
    with io.open(REGISTRY, encoding="utf-8-sig") as f:
        return json.load(f)


def ledgers():
    """[(holon id, name, brain-relative ledger path)] for every holon whose registry row names a `tasks` file."""
    return [(h["id"], h.get("name", h["id"]), h["tasks"]) for h in registry().get("holons", []) if h.get("tasks")]


def resolve(project=None, file=None):
    """-> (absolute path, brain-relative path)."""
    if file:
        rel = file.replace("\\", "/")
        return os.path.join(BRAIN, rel.replace("/", os.sep)), rel
    for hid, _name, rel in ledgers():
        if hid == project:
            return os.path.join(BRAIN, rel.replace("/", os.sep)), rel
    raise LedgerError("holon %r has no `tasks` field in context/holon-registry.json (add one, or pass --file)" % project)


def norm_owner(o):
    o = (o or "").strip()
    if not o:
        raise LedgerError("an owner is required (%s, @claude, a contact)" % OWNER)
    return o if o.startswith("@") else "@" + o


def clean(text):
    return " ".join(str(text or "").split()).replace(SEP, ", ")


LINE_REF_RE = re.compile(r"(?<!lint )\bL\d{2,4}\b")   # 2026-09-25: a transcript line ref is evidence for --link, never words he reads


def warn_line_refs(*texts):
    """A WARN, never a refusal: text or note carrying a transcript line reference outside a <!-- --> comment."""
    hit = next((m for m in (LINE_REF_RE.search(re.sub(r"<!--.*?-->", "", str(t), flags=re.S)) for t in texts if t) if m), None)
    if hit:
        sys.stderr.write("WARN: '%s' in --text/--note is a transcript line reference; the evidence goes in --link "
                         "(skills/brain-tasks/readme.md, How agents use it, 2026-09-25)\n" % hit.group(0))


# 2026-10-02, correction #98 (the owner's words are in zak-corrections-log.md; the card that caused it said "correction #93"
# and a bare item id, which no reader could follow). A card is read cold, days later; whatever it references is written out in
# a clause AND linked. These are HEURISTICS that report, never refuse: `check` counts the open items addressed to @zak
# that break the rule, and add / ask / retext print a WARN.
CORR_REF_RE = re.compile(r"(?:\bcorrections?\s+#?|(?<![\w#&])#)(\d{1,3})\b(?!\d)", re.I)
ITEM_ID_RE = re.compile(r"\b[TQ]-\d{4}\b")
EFFORT_RE = re.compile(r"\beffort\s*:|\bhalf an? (?:day|hour)\b|\b(?:an|one|two|three|a few|about an?|about \d+|~\s*\d+|\d+(?:\.\d+)?)\s*(?:-\s*\d+\s*)?"
                       r"(?:minutes?|mins?|hours?|hrs?|days?)(?: of (?:work|edits?|build(?:ing)?))?\b(?=[^.]*\b(?:effort|takes?|to build|of edits|of work)\b)"
                       r"|\b(?:takes?|about|roughly|~)\s*\d+\s*(?:minutes?|mins?|hours?|hrs?)\b", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.?!])\s+")


def _sentence_of(text, pos):
    start = 0
    for m in _SENT_SPLIT.finditer(text):
        if m.end() > pos:
            return text[start:m.start()], pos - start
        start = m.end()
    return text[start:], pos - start


def cold_reasons(text, links=()):
    """Why a cold reader could not follow this item's words. Empty list = fine. Heuristic (2026-10-02, correction #98).
    - a correction number (#93, correction 93) is fine only when a link goes to the corrections file AND a clause follows
      it at once: '(', ':', ', which', ' that', ' on ', ' about ', ' says'.
    - an item id (T-0074, Q-0015) is fine only as '<a described thing of 4+ words> (ledger ID)' or 'ID (<3+ words>)'.
      Used inline as a noun ('per T-0074', 'blocked on Q-0015', 'brain-central T-0074') it is bare.
    - a time estimate ('Effort: an hour', 'half a day') is flagged; one is written only when quoted from a thing that ran."""
    t = re.sub(r"<!--.*?-->", "", str(text or ""), flags=re.S)
    out = []
    linked_corr = any(("corrections-log" in l or "zak-brain.md" in l) for l in (links or ()))
    for m in CORR_REF_RE.finditer(t):
        after = t[m.end():m.end() + 10]
        clause = re.match(r"\s*(?:\(|:|,\s*which|\s+that\b|\s+on\b|\s+about\b|\s+says\b|,\s*the\b)", after, re.I)
        if not (linked_corr and clause):
            out.append("bare correction %s" % m.group(0).strip())
    for m in ITEM_ID_RE.finditer(t):
        sent, at = _sentence_of(t, m.start())
        before, after = sent[:at], sent[at + len(m.group(0)):]
        wrapped = re.search(r"\(\s*(?:[\w-]+\s+)?$", before) and re.match(r"\s*\)", after)
        described_before = wrapped and len(re.findall(r"[A-Za-z]{2,}", re.sub(r"\([^()]*$", "", before))) >= 4
        described_after = re.match(r"\s*\(([^()]*)\)", after) and len(re.findall(r"[A-Za-z]{2,}", re.match(r"\s*\(([^()]*)\)", after).group(1))) >= 3
        if not (described_before or described_after):
            out.append("bare id %s" % m.group(0))
    m = EFFORT_RE.search(t)
    if m:
        out.append("time estimate '%s'" % m.group(0).strip())
    return out


def warn_cold(text, links=()):
    """A WARN, never a refusal (2026-10-02, correction #98)."""
    r = cold_reasons(text, links)
    if r:
        sys.stderr.write("WARN: a cold reader cannot follow this item: %s. Write each reference out in a clause and --link "
                         "the file that holds it; state the ask first (skills/brain-tasks/readme.md, How agents use it, 2026-10-02)\n"
                         % "; ".join(r))


def addressed_to_zak_open(it):
    """Open items the owner is meant to read and act on: open or blocked tasks the owner holds, open questions to the owner."""
    if it["kind"] == "question":
        return it["mark"] == "?" and (it.get("to") or "").lower() == "@zak"
    return it["mark"] in (" ", "-") and (it.get("owner") or "").lower() == "@zak"


def known_people():
    """The slugs that have a card in people/. The cards are the truth about who exists (Correction #42); an item may only
    carry someone who has one, so a typo becomes a refusal instead of a person nobody can open."""
    try:
        return {fn[:-3] for fn in os.listdir(PEOPLE_DIR) if fn.endswith(".md") and fn != "readme.md"}
    except OSError:
        return set()


def norm_people(value):
    """--people "a,b" (or a list of either) -> a deduped, validated list of people/ slugs, order kept."""
    if value in (None, "", []):
        return []
    out = []
    for chunk in (value if isinstance(value, (list, tuple)) else [value]):
        for s in str(chunk).split(","):
            s = s.strip().lower()
            if not s:
                continue
            if not SLUG_RE.match(s):
                raise LedgerError("%r is not a people/ slug (lowercase, hyphens, the card's filename without .md)" % s)
            if s not in out:
                out.append(s)
    known = known_people()
    missing = [s for s in out if s not in known] if known else []
    if missing:
        raise LedgerError("no card in people/ for: %s -- add the card first, or fix the slug" % ", ".join(missing))
    return out


def norm_source(value, required=True):
    """--source -> the slug stored as the `#source:<slug>` tag: WHO found this (2026-09-17). Plain: letters, digits, `-`
    and `_`. A `#` or a space is refused because both break the tag segment -- the design doc's own `night-agent#86`
    is exactly the value this catches, and the producer writes `night-agent-86` instead."""
    s = str(value or "").strip()
    if not s:
        if required:
            raise LedgerError("--source is required (who found it: night-agent-86, brain-lint, dispatcher, handoff, extended-rounds-2026-10)")
        return None
    if not SOURCE_RE.match(s):
        raise LedgerError("--source wants a plain slug -- letters, digits, - and _, no '#' and no spaces -- not %r" % s)
    return s


def norm_key(value, required=True):
    """--key -> the value stored as the `#key:<value>` tag: the PRODUCER'S stable id for a finding, so its next run can
    recognise its own work and `repeat` it instead of filing a second item. Source's rule plus `/`, `:` and `.`, which
    is what lets a key name the file it is about (`L12:people/kyle-collins.md`, `R3:librarian`, `obs41`)."""
    s = str(value or "").strip()
    if not s:
        if required:
            raise LedgerError("--key is required (the producer's own id for the finding, e.g. L12:people/kyle-collins.md)")
        return None
    if not KEY_RE.match(s):
        raise LedgerError("--key wants the producer's id -- letters, digits and - _ . / : -- no '#' and no spaces -- not %r" % s)
    return s


def norm_call(value, required=True):
    """--call -> the people/ slug stored as the `#call:<slug>` tag: this item is raised on THAT PERSON'S next call, so it
    belongs in their call prep and not on the Today page (2026-09-18, viewer T-0192). One person, validated against
    people/ exactly the way `people:` is -- no card, no tag -- because the call prep is keyed by the slug."""
    s = str(value or "").strip().lower()
    if not s:
        if required:
            raise LedgerError("--call wants the people/ slug whose call this is raised on (e.g. --call collin-green)")
        return None
    got = norm_people(s)
    if len(got) != 1:
        raise LedgerError("--call names ONE person's call, not %d (a group call has no single slug; leave it untagged)" % len(got))
    return got[0]


def norm_tag(value):
    """One #tag value as it is stored on the line (no leading '#'). A space or a '#' is refused: the parser reads a tag
    as a single segment starting with '#', so either would split the line into something else."""
    s = str(value or "").strip().lstrip("#")
    if not s:
        raise LedgerError("--tag is required (the tag to add or remove, without the '#')")
    if not TAG_RE.match(s):
        raise LedgerError("--tag wants a plain tag -- letters, digits and - _ . / : -- no '#' and no spaces -- not %r" % value)
    return s


def norm_tags(tags, source=None, key=None, call=None):
    """The #tag list for a new item: the finding tags first (source:, then key:), then the call tag, then whatever --tag
    gave, deduped and order kept. Validation happens here, so a malformed source never reaches a ledger line."""
    out = []
    for t in ([SOURCE_TAG + norm_source(source) if source not in (None, "") else None,
               KEY_TAG + norm_key(key) if key not in (None, "") else None,
               CALL_TAG + norm_call(call) if call not in (None, "") else None]
              + [" ".join(str(t).split()) for t in (tags or [])]):
        if t and t not in out:
            out.append(t)
    return out


def norm_rel(path_):
    """A brain-relative path, said one way: forward slashes, no leading ./ or /."""
    p = str(path_ or "").replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def route(path_):
    """WHICH LEDGER a finding about this file belongs on -> (holon id, brain-relative ledger path). The holon in
    context/holon-registry.json that names a `tasks` file and whose `path` is the LONGEST prefix of the given path wins;
    nothing matching is brain-central. Exposed as `tasks.py route <path>` so the night agent, brain-lint, the dispatcher
    and the handoff writer do not each reimplement the same ten lines (findings-routing design, 2026-09-17, piece 1).
    Read-only: it touches no file and writes no log line."""
    p = norm_rel(path_)
    best_len, best = -1, None
    for h in registry().get("holons", []):
        if not h.get("tasks"):
            continue
        hp = norm_rel(h.get("path")).rstrip("/")
        if not hp:
            continue
        if p == hp or p.startswith(hp + "/"):
            if len(hp) > best_len:
                best_len, best = len(hp), h
    if best:
        return best["id"], norm_rel(best["tasks"])
    for h in registry().get("holons", []):
        if h.get("id") == DEFAULT_LEDGER[0] and h.get("tasks"):
            return h["id"], norm_rel(h["tasks"])
    return DEFAULT_LEDGER


def open_by_key(key, project=None, file=None):
    """[(holon id, brain-relative path, absolute path, item)] for every OPEN item carrying `#key:<key>`. "Open" is the
    same set `list --open` shows: a task not done, or a question not answered. Scoped to one ledger when --project or
    --file says so, every registered ledger otherwise -- a producer's key is meant to be unique across the brain."""
    targets = [(project, file)] if (project or file) else [(hid, None) for hid, _n, _r in ledgers()]
    hits = []
    for proj, fil in targets:
        path, rel = resolve(proj, fil)
        if not os.path.isfile(path):
            continue
        for it in parse(read(path))["items"]:
            if it.get("key") == key and it["mark"] in " -?":
                hits.append((proj, rel, path, it))
    return hits


def norm_links(value):
    """--link "..." (repeatable) -> the item's `→ link` list, in the order given. A link is stored VERBATIM -- a route the
    viewer navigates to ("/glossary", "/reader?path=..."), a brain-relative path, or a [[wikilink]] -- so nothing is
    resolved here. The one refusal is a link carrying the segment separator, which would split the line into two fields."""
    out = []
    for l in (value if isinstance(value, (list, tuple)) else [value]) if value not in (None, "", []) else []:
        l = " ".join(str(l).split())
        if not l:
            continue
        if SEP.strip() in l and SEP in l:
            raise LedgerError("a link may not contain %r (it separates the fields on the line): %s" % (SEP, l))
        if l not in out:
            out.append(l)
    return out


# ---------------- parse ----------------

def parse_item(line, n, group):
    m = ITEM_RE.match(line)
    if not m:
        return None
    st, iid, created, owner, to, rest = m.groups()
    it = {"state": STATES[st], "mark": st, "id": iid, "kind": "question" if iid.startswith("Q") else "task",
          "created": created, "owner": owner, "to": to, "text": "", "due": None, "done": None, "blocked": None,
          "unblocked": None, "until": None, "answer": None, "answered": None, "app": None, "note": None, "people": [], "links": [], "tags": [],
          "repeats": None, "source": None, "key": None, "call": None, "milestone": group, "line": n}
    segs = rest.split(SEP) if rest else []
    if segs:
        it["text"] = segs[0].strip()
    for s in segs[1:]:
        s = s.strip()
        if not s:
            continue
        if s.startswith("→ "):
            it["links"].append(s[2:].strip()); continue
        if s.startswith("#") and " " not in s:
            it["tags"].append(s[1:]); continue
        k, colon, v = s.partition(":")
        if colon and k in FIELD_KEYS:
            v = v.strip()
            if k == "answer":
                d, _, txt = v.partition(" ")
                it["answered"], it["answer"] = d, txt.strip()
            elif k == "people":
                it["people"] = [s.strip().lower() for s in v.split(",") if s.strip()]
            else:
                it[k] = v
            continue
        it["text"] = (it["text"] + SEP + s) if it["text"] else s    # a stray segment stays with the text
    # The two finding tags, lifted to top-level fields so the viewer and every producer read them without re-parsing
    # tags (2026-09-17). They are STILL tags on the line -- nothing here writes -- so `retext`, `done`, `reassign` and
    # every other verb that rewrites through fields_of() carry them along the way they already carried `#design`.
    it["source"] = next((t[len(SOURCE_TAG):] for t in it["tags"] if t.startswith(SOURCE_TAG)), None)
    it["key"] = next((t[len(KEY_TAG):] for t in it["tags"] if t.startswith(KEY_TAG)), None)
    # the call this item is raised on, lifted the same way (2026-09-18, T-0192): the Brain Viewer's Today page leaves a
    # call-scoped item out and the person's call prep carries it, and both read this field rather than re-parsing tags.
    it["call"] = next((t[len(CALL_TAG):] for t in it["tags"] if t.startswith(CALL_TAG)), None)
    return it


def parse(text):
    lines = text.replace("\r\n", "\n").split("\n")
    groups, order, errors, header = {}, [], [], []
    cur = None
    for n, line in enumerate(lines, 1):
        h = HEAD_RE.match(line)
        if h:
            cur = h.group(1).strip()
            if cur not in groups:
                groups[cur] = []; order.append(cur)
            continue
        if line.startswith("- ["):
            g = cur or "Inbox"
            it = parse_item(line, n, g)
            if not it:
                errors.append("line %d does not parse as an item: %s" % (n, line[:120])); continue
            if g not in groups:
                groups[g] = []; order.append(g)
            groups[g].append(it)
        elif cur is None:
            header.append(line)
    items = [it for g in order for it in groups[g]]
    ids = [it["id"] for it in items]
    for d in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append("duplicate id %s" % d)
    for it in items:
        if it["kind"] == "question" and it["mark"] not in "?a":
            errors.append("%s: a Q id with a task state [%s]" % (it["id"], it["mark"]))
        if it["kind"] == "task" and it["mark"] in "?a":
            errors.append("%s: a T id with a question state [%s]" % (it["id"], it["mark"]))
        for k in ("created", "due", "done", "until", "answered"):
            if it.get(k):
                try:
                    dt.date.fromisoformat(it[k])
                except ValueError:
                    errors.append("%s: bad %s date %r" % (it["id"], k, it[k]))
        # repeats:N -> an int, 0 when the segment is absent (2026-09-17). Normalised here rather than in parse_item so a
        # non-number is a FORMAT ERROR the way a bad date is, instead of a count that silently reads as none.
        r = it.get("repeats")
        if r in (None, ""):
            it["repeats"] = 0
        elif str(r).strip().isdigit():
            it["repeats"] = int(str(r).strip())
        else:
            errors.append("%s: bad repeats %r (it counts times raised, so a whole number)" % (it["id"], r))
            it["repeats"] = 0
    return {"header": header, "order": order, "groups": groups, "items": items, "errors": errors, "lines": lines}


def is_held(it, ref_date=None):
    """True while an open task is on hold: it carries an `until:` date that has not arrived. On the day itself it is back.
    A done, blocked or question item is never held -- hold is only ever "not now, and not because of anyone else"."""
    return bool(it.get("mark") == " " and it.get("kind") != "question" and it.get("until") and it["until"] > (ref_date or today()))


def summary(parsed, ref_date=None):
    """Counts for a progress view. Derived at read time, never stored."""
    ref = ref_date or today()
    tasks = [i for i in parsed["items"] if i["kind"] == "task"]
    qs = [i for i in parsed["items"] if i["kind"] == "question"]
    by_owner = {}
    for i in tasks:
        b = by_owner.setdefault(i["owner"], {"open": 0, "done": 0, "blocked": 0, "held": 0})
        b["open" if i["mark"] == " " else "done" if i["mark"] == "x" else "blocked"] += 1
        if is_held(i, ref):
            b["held"] += 1          # counted inside `open` as well: a held task is still open, it is just not asked for today
    return {"tasks": len(tasks), "open": sum(1 for i in tasks if i["mark"] == " "), "done": sum(1 for i in tasks if i["mark"] == "x"),
            "blocked": sum(1 for i in tasks if i["mark"] == "-"),
            "held": sum(1 for i in tasks if is_held(i, ref)),
            "overdue": sum(1 for i in tasks if i["mark"] == " " and i["due"] and i["due"] < ref),
            "questions_open": sum(1 for i in qs if i["mark"] == "?"), "questions_answered": sum(1 for i in qs if i["mark"] == "a"),
            "by_owner": by_owner}


# ---------------- read / write ----------------

def read(path):
    if not os.path.isfile(path):
        raise LedgerError("no ledger file at %s (run: tasks.py init --project <id> --name \"...\")" % path)
    with io.open(path, encoding="utf-8-sig") as f:
        return f.read()


def write(path, lines):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines).rstrip("\n") + "\n")


def fmt(mark, iid, created, owner, to, text, fields):
    head = "- [%s] %s %s %s" % (mark, iid, created, owner) + (" → %s" % to if to else "")
    return SEP.join([head, clean(text)] + [f for f in fields if f])


def norm_due(v):
    """A day, checked before it can reach a ledger line (2026-09-16, T-0150). `add --due` never validated, so a typo
    landed in the file and the viewer compared it as a string forever after. There is deliberately no "today" keyword:
    the `today` verb reads the clock itself, in the call that writes."""
    s = str(v or "").strip()
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        raise LedgerError("--due wants a date as YYYY-MM-DD, not %r" % s)


def fields_of(it, **override):
    d = dict(it); d.update(override)
    out = ["%s:%s" % (k, d[k]) for k in ("due", "done", "blocked", "unblocked", "until", "app", "repeats") if d.get(k)]
    if d.get("note"):
        out.append("note:%s" % clean(d["note"]))          # one line to keep in mind while doing this item; the viewer shows it under the item
    if d.get("people"):
        out.append("people:%s" % ",".join(d["people"]))
    if d.get("answered"):
        out.append("answer:%s %s" % (d["answered"], clean(d.get("answer"))))
    out += ["#%s" % t for t in d.get("tags") or []]
    out += ["→ %s" % l for l in d.get("links") or []]
    return out


def rewrite(parsed, it, mark=None, **override):
    # owner and to come from it2, not it, so `reassign` can move an item between owners through the one write path
    it2 = dict(it); it2.update(override)
    parsed["lines"][it["line"] - 1] = fmt(mark or it["mark"], it["id"], it["created"], it2["owner"], it2["to"], it2["text"], fields_of(it2))


def next_id(parsed, prefix):
    nums = [int(i["id"][2:]) for i in parsed["items"] if i["id"].startswith(prefix)]
    return "%s-%04d" % (prefix, (max(nums) + 1) if nums else 1)


def insert(parsed, group, line):
    """Append a line at the end of a group's block (before its trailing blank lines); create the heading if missing."""
    lines = parsed["lines"]; group = (group or "Inbox").strip()
    idx = next((i for i, l in enumerate(lines) if HEAD_RE.match(l) and HEAD_RE.match(l).group(1).strip() == group), None)
    if idx is None:
        while lines and lines[-1].strip() == "":
            lines.pop()
        lines += ["", "## %s" % (group if group == "Inbox" else "Milestone — " + group), line]
        return
    end = next((j for j in range(idx + 1, len(lines)) if HEAD_RE.match(lines[j])), len(lines))
    k = end
    while k > idx + 1 and lines[k - 1].strip() == "":
        k -= 1
    lines.insert(k, line)


def find(parsed, iid):
    for it in parsed["items"]:
        if it["id"] == iid:
            return it
    raise LedgerError("no item %s in this ledger" % iid)


def log_line(agent, text):
    # BRAIN_ROOT so a ledger outside the canonical brain (a team copy, a scratch tree) logs into ITS OWN context/log.md
    # instead of log.py's hard-coded default. Verified 2026-09-09: without it, three scratch writes landed in the owner's log.
    try:
        subprocess.run([sys.executable, LOG_PY, "--append", "--agent", agent, "--action", "MODIFIED", "--text", text],
                       cwd=BRAIN, capture_output=True, text=True, timeout=30, env=dict(os.environ, BRAIN_ROOT=BRAIN))
    except Exception as e:
        sys.stderr.write("log.py failed: %s\n" % e)


def apply(path, rel, action, agent="brain-tasks", **a):
    """One structured mutation on a ledger. Returns the id touched. Used by the CLI and by the viewer's server."""
    parsed = parse(read(path))
    if parsed["errors"]:
        raise LedgerError("ledger has format errors; fix them first:\n  " + "\n  ".join(parsed["errors"]))
    d = today()
    if action in ("add", "ask", "note", "retext", "answer", "repeat"):
        warn_line_refs(a.get("text"), a.get("note"))
    if action in ("add", "ask"):
        warn_cold(a.get("text"), norm_links(a.get("links")))
    if action == "add":
        if not clean(a.get("text")):
            raise LedgerError("--text is required")
        iid = next_id(parsed, "T"); owner = norm_owner(a.get("owner") or "@claude"); who = norm_people(a.get("people"))
        fields = ((["due:%s" % norm_due(a["due"])] if a.get("due") else []) + (["note:%s" % clean(a["note"])] if clean(a.get("note")) else [])
                  + (["people:%s" % ",".join(who)] if who else [])
                  + ["#%s" % t for t in norm_tags(a.get("tags"), a.get("source"), a.get("key"), a.get("call"))] + ["→ %s" % l for l in norm_links(a.get("links"))])
        insert(parsed, a.get("milestone"), fmt(" ", iid, d, owner, None, a["text"], fields))
        note = "%s -- %s added for %s: %s%s%s" % (rel, iid, owner, clean(a["text"])[:90], (" (about %s)" % ", ".join(who)) if who else "",
                                                  (" [found by %s]" % a["source"]) if a.get("source") else "")
    elif action == "ask":
        if not clean(a.get("text")):
            raise LedgerError("--text is required")
        iid = next_id(parsed, "Q"); frm = norm_owner(a.get("frm") or "@claude"); to = norm_owner(a.get("to") or OWNER)
        who = norm_people(a.get("people"))
        # --due on a question (2026-09-16, T-0150): a question can be owed by a day the way a task is, and the Today
        # page reads that day into "Due today or earlier" alongside the tasks.
        fields = ((["due:%s" % norm_due(a["due"])] if a.get("due") else [])
                  + (["note:%s" % clean(a["note"])] if clean(a.get("note")) else []) + (["people:%s" % ",".join(who)] if who else [])
                  + ["#%s" % t for t in norm_tags(a.get("tags"), a.get("source"), a.get("key"), a.get("call"))] + ["→ %s" % l for l in norm_links(a.get("links"))])
        insert(parsed, a.get("milestone"), fmt("?", iid, d, frm, to, a["text"], fields))
        note = "%s -- %s asked of %s by %s: %s%s%s" % (rel, iid, to, frm, clean(a["text"])[:90], (" (about %s)" % ", ".join(who)) if who else "",
                                                       (" [found by %s]" % a["source"]) if a.get("source") else "")
    elif action in ("done", "reopen", "block", "answer", "people", "link", "note", "retext", "hold", "today", "reassign", "repeat", "tag"):
        it = find(parsed, a["id"]); iid = it["id"]
        if action == "repeat":
            # THE SAME FINDING, RAISED AGAIN (2026-09-17). The survey's headline defect: one finding was raised five
            # nights running and nothing on the item recorded that it had been raised before, so each night read as the
            # first. A repeat is never a second item -- it is a count and a dated line on the one that is already open.
            # `note` REPLACES the keep-in-mind line, by design (it is one thing to keep in mind), so this APPENDS after
            # " | " instead: the history of a standing finding reads in order, on the item, without a second file.
            src = norm_source(a.get("source"))
            n = int(it.get("repeats") or 0) + 1
            said = "repeat %d (%s, %s)" % (n, src, d)
            more = clean(a.get("text"))
            if more:
                said += ": " + more
            prev = clean(it.get("note"))
            rewrite(parsed, it, repeats=n, note=(prev + " | " + said) if prev else said)
            res = a.get("result")
            if isinstance(res, dict):
                res["repeats"] = n          # so the caller can print "<id> repeat N" without re-reading the file
            note = "%s -- %s repeat %d from %s: %s%s" % (rel, iid, n, src, it["text"][:80], (" -- %s" % more[:60]) if more else "")
        elif action == "tag":
            # ONE TAG ON AN ITEM THAT EXISTS (2026-09-18, viewer T-0192). Every tag could be written at birth and never
            # afterwards, so re-scoping an item meant hand-editing a ledger line -- the one thing this tool exists to
            # prevent. `tag <id> --tag <value>` adds it if it is not already there, `--remove` takes it off, and
            # `--call <slug>` is the same verb with the people/ slug validated into `call:<slug>`. Nothing else on the
            # line moves: the id, the date, the owner, the state and every field are carried by rewrite() as always.
            want = ([CALL_TAG + norm_call(a["call"])] if a.get("call") not in (None, "") else []) + [norm_tag(t) for t in (a.get("tags") or [])]
            if not want:
                raise LedgerError("--tag (or --call) is required: the tag to add, or to take off with --remove")
            tags = list(it.get("tags") or [])
            gone, added = [], []
            for t in want:
                if a.get("remove"):
                    if t in tags:
                        tags.remove(t); gone.append(t)
                elif t not in tags:
                    tags.append(t); added.append(t)
            if not gone and not added:
                raise LedgerError("%s already reads exactly that (%s %s)" % (iid, "without" if a.get("remove") else "with", ", ".join("#" + t for t in want)))
            rewrite(parsed, it, tags=tags)
            note = "%s -- %s %s %s: %s" % (rel, iid, "untagged" if gone else "tagged",
                                           ", ".join("#" + t for t in (gone or added)), it["text"][:70])
        elif action == "people":
            # who this item concerns: replaces the field outright (an empty --people clears it). Validated against people/.
            who = norm_people(a.get("people"))
            rewrite(parsed, it, people=who)
            note = "%s -- %s now carries %s" % (rel, iid, ("people: " + ", ".join(who)) if who else "no people")
        elif action == "note":
            # the keep-in-mind line on an item that already exists (an empty --note clears it); `add` / `ask` set it at birth
            txt = clean(a.get("note") or a.get("text"))
            rewrite(parsed, it, note=txt or None)
            note = "%s -- %s keep in mind: %s" % (rel, iid, txt[:80] if txt else "(cleared)")
        elif action == "retext":
            # THE WORDS OF AN ITEM, rewritten in place (2026-09-09). Everything else on the line -- id, created date,
            # owner, due, note, people, tags, links, state -- is kept exactly as it was; only segment 1 changes. It
            # exists because an item's text can go stale (a route parenthetical the viewer now renders as a link) and
            # the alternative was hand-editing a ledger line, which is what this tool exists to prevent.
            txt = clean(a.get("text"))
            warn_cold(txt, it["links"])    # correction #98: with the item's own links, so a linked correction is seen
            if not txt:
                raise LedgerError("--text is required (the item's new words)")
            was = it["text"]
            if txt == was:
                raise LedgerError("%s already reads exactly that" % iid)
            rewrite(parsed, it, text=txt)
            note = "%s -- %s retexted: %s" % (rel, iid, txt[:90])
        elif action == "reassign":
            # THE OWNER OF A TASK, moved in place (2026-09-15, T-0148): a queue change is one tool call instead of a hand
            # edit. Only segment 0's owner changes -- the id, the created date, the state and every field stay -- so the
            # line keeps its shape and its history. A question is not reassignable: its owner is who ASKED it, and its
            # `→ @to` is who owes the answer; moving either would rewrite who said what.
            if it["kind"] != "task":
                raise LedgerError("%s is a question; reassign moves a task between owners, and a question's owner is who asked it" % iid)
            new_owner = norm_owner(a.get("owner"))
            if new_owner == it["owner"]:
                raise LedgerError("%s already belongs to %s" % (iid, new_owner))
            was = it["owner"]
            why = clean(a.get("reason") or a.get("note") or a.get("text"))
            rewrite(parsed, it, owner=new_owner)
            note = "%s -- %s reassigned %s → %s: %s%s" % (rel, iid, was, new_owner, it["text"][:80], (" (%s)" % why[:80]) if why else "")
        elif action == "link":
            # THE RESULT LINK (2026-09-09): what an item points at, replaced outright. On a done step that is what it
            # BUILT -- a route (/glossary) or a file -- and the viewer's timeline is nothing but those links read back.
            links = norm_links(a.get("links"))
            rewrite(parsed, it, links=links)
            note = "%s -- %s points at %s" % (rel, iid, ", ".join(links) if links else "nothing (link cleared)")
        elif action == "today":
            # THE DAY AN ITEM IS OWED BY (2026-09-16, T-0150). The Today page's "Due today or earlier" reads `due:`, and
            # until now that field could only be written at birth -- so the section had nothing to show for anything
            # already on a ledger. The day with no argument is the CLOCK's, read here, in the call that writes; --due
            # names another day and --due none takes the day back off. A question takes a day as readily as a task.
            raw = a.get("due")
            raw = raw.strip() if isinstance(raw, str) else raw
            if raw in ("none", "clear", "no", "-", ""):
                if not it.get("due"):
                    raise LedgerError("%s carries no day already" % iid)
                was = it["due"]
                rewrite(parsed, it, due=None)
                note = "%s -- %s no longer due (was %s): %s" % (rel, iid, was, it["text"][:80])
            else:
                day = norm_due(raw) if raw else d
                if it.get("due") == day:
                    raise LedgerError("%s is already due %s" % (iid, day))
                rewrite(parsed, it, due=day)
                note = "%s -- %s due %s%s: %s" % (rel, iid, day, " (today)" if day == d else "", it["text"][:80])
        elif action == "hold":
            # ON HOLD, not done and not blocked (2026-09-10, T-0108): an open task the owner is not doing now, with the day it
            # comes back written on it. The default is three days; the date is checked here so a typo cannot reach the file.
            if it["kind"] != "task":
                raise LedgerError("%s is a question; a question is answered, not held" % iid)
            if it["mark"] != " ":
                raise LedgerError("%s is %s -- only an open task can be put on hold" % (iid, it["state"]))
            u = (a.get("until") or "").strip() if isinstance(a.get("until"), str) else ""
            if u:
                try:
                    day = dt.date.fromisoformat(u)
                except ValueError:
                    raise LedgerError("--until wants a date as YYYY-MM-DD, not %r" % u)
                if day.isoformat() <= d:
                    raise LedgerError("%s is not in the future (it is %s today); a hold has to end on a later day" % (day.isoformat(), d))
            else:
                day = dt.date.fromisoformat(d) + dt.timedelta(days=HOLD_DAYS)
            rewrite(parsed, it, until=day.isoformat())
            note = "%s -- %s on hold until %s: %s" % (rel, iid, day.isoformat(), it["text"][:80])
        elif action == "done":
            if it["kind"] != "task":
                raise LedgerError("%s is a question; answer it instead" % iid)
            links = norm_links(a.get("links"))
            rewrite(parsed, it, mark="x", done=d, blocked=None, until=None, **({"links": links} if links else {}))
            note = "%s -- %s done: %s%s" % (rel, iid, it["text"][:90], (" → %s" % ", ".join(links)) if links else "")
        elif action == "reopen":
            # also the way back from a hold: the `until:` date goes with everything else that said "not now"
            was_held = it.get("until")
            rewrite(parsed, it, mark=" " if it["kind"] == "task" else "?", done=None, blocked=None, until=None, answered=None, answer=None)
            note = "%s -- %s %s" % (rel, iid, ("back from hold (was until %s)" % was_held) if was_held and it["mark"] == " " else "reopened")
        elif action == "block":
            if it["kind"] != "task":
                raise LedgerError("%s is a question" % iid)
            rewrite(parsed, it, mark="-", blocked=clean(a.get("by") or a.get("reason") or "unspecified"))
            note = "%s -- %s blocked: %s" % (rel, iid, clean(a.get("by") or a.get("reason") or "unspecified")[:60])
        else:
            if it["kind"] != "question":
                raise LedgerError("%s is not a question" % iid)
            if not clean(a.get("text")):
                raise LedgerError("--text (the answer) is required")
            rewrite(parsed, it, mark="a", answered=d, answer=a["text"])
            freed = []
            for other in parsed["items"]:
                if other["kind"] == "task" and other["mark"] == "-" and other["blocked"] == iid:
                    rewrite(parsed, other, mark=" ", blocked=None, unblocked=iid); freed.append(other["id"])
            note = "%s -- %s answered by %s: %s%s" % (rel, iid, norm_owner(a.get("by") or it["to"] or OWNER), clean(a["text"])[:80],
                                                   (" (unblocked %s)" % ", ".join(freed)) if freed else "")
    else:
        raise LedgerError("unknown action %r" % action)
    write(path, parsed["lines"])
    log_line(agent, note)
    return iid


def init(path, rel, hid, name, agent="brain-tasks"):
    if os.path.isfile(path):
        raise LedgerError("%s already exists" % rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write(path, ["# %s — tasks and questions" % name,
                 "> The project ledger for holon `%s`. One item per line, written by `skills/brain-tasks/tasks.py` (dates from the clock) or by hand in the same shape. Format: [[skills/brain-tasks/readme.md]]. Rendered by the Brain Viewer at `/projects`, where boxes get checked and questions get answered. Created %s." % (hid, today()),
                 "", "## Inbox", ""])
    log_line(agent, "%s -- ledger created for holon %s" % (rel, hid))


# ---------------- CLI ----------------

def keeps(i, a):
    """The findings filters, shared by the printed list and --json (2026-09-17). `--source` is a PREFIX, so
    `--source night-agent` finds every run's items at once; `--key` is exact, because a key names one finding."""
    src, key = getattr(a, "source", None), getattr(a, "key", None)
    call = getattr(a, "call", None)
    if src and not (i.get("source") or "").startswith(src):
        return False
    if key and (i.get("key") or "") != key:
        return False
    # --call <slug> is exact: the items raised on that person's next call (2026-09-18, T-0192), which is what the call
    # prep's Carried block reads. A bare `--call` with no value means every call-scoped item, whoever the call is with.
    if call is not None:
        want = str(call).strip().lower()
        if want and (i.get("call") or "") != want:
            return False
        if not want and not i.get("call"):
            return False
    return True


def print_list(rel, p, a):
    """One ledger as `list` prints it: the header line, then the items under their milestone headings."""
    s = summary(p)
    who = [w for chunk in a.people for w in str(chunk).split(",") if w.strip()]   # on `list`, --people filters
    print("%s -- %d tasks: %d open, %d done, %d blocked, %d overdue%s · %d questions open"
          % (rel, s["tasks"], s["open"], s["done"], s["blocked"], s["overdue"],
             " (%d on hold%s)" % (s["held"], ", shown" if a.held else ", left out") if s["held"] else "", s["questions_open"]))
    for g in p["order"]:
        # a task on hold is left out unless --held: it is open, it is simply not being asked for today (T-0108)
        rows = [i for i in p["groups"][g] if (not a.open or i["mark"] in " -?") and (not a.owner or i["owner"] == norm_owner(a.owner) or i["to"] == norm_owner(a.owner)) and (not a.questions or i["kind"] == "question") and (not who or any(w.strip().lower() in i["people"] for w in who)) and (a.held or not is_held(i)) and keeps(i, a)]
        if not rows:
            continue
        print("\n## %s" % g)
        for i in rows:
            extra = " ".join(x for x in ["due:" + i["due"] if i["due"] else "", "blocked:" + i["blocked"] if i["blocked"] else "", "on hold until " + i["until"] if is_held(i) else "", ("people:" + ",".join(i["people"])) if i["people"] else "", ("call:" + i["call"]) if i.get("call") else "", ("source:" + i["source"]) if i.get("source") else "", "repeats:%d" % i["repeats"] if i.get("repeats") else "", ("answer: " + i["answer"]) if i["answer"] else ""] if x)
            print("  [%s] %s %s %s%s  %s  %s" % (i["mark"], i["id"], i["created"], i["owner"], (" → " + i["to"]) if i["to"] else "", i["text"], extra))
    if p["errors"]:
        print("\nFORMAT ERRORS:\n  " + "\n  ".join(p["errors"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="the project ledger: tasks and questions per project")
    ap.add_argument("action", choices=["init", "add", "ask", "done", "reopen", "block", "answer", "people", "link", "note", "retext", "reassign", "hold", "today", "repeat", "tag", "route", "list", "check"])
    ap.add_argument("ids", nargs="*", help="item ids for done / reopen / block / answer / people / link / note / retext / reassign / hold / today / repeat / tag; the path for route")
    ap.add_argument("--project"); ap.add_argument("--file")
    ap.add_argument("--name"); ap.add_argument("--text")
    ap.add_argument("--owner", help="on add, who the new task is for; on reassign, the owner it moves to (%s, @claude, any @name); on list, the owner to filter by" % OWNER)
    ap.add_argument("--to"); ap.add_argument("--from", dest="frm")
    ap.add_argument("--by"); ap.add_argument("--reason", help="on block, why; on reassign, why it moved (it goes in the log line, not on the item)")
    ap.add_argument("--due", help="on add / ask, the day the new item is owed by; on today, the day to put on an item that exists (default: the clock's own day) -- `none` takes the day back off")
    ap.add_argument("--milestone")
    ap.add_argument("--until", help="on hold: the day the task comes back (YYYY-MM-DD); default is %d days out" % HOLD_DAYS)
    ap.add_argument("--held", action="store_true", help="on list: include the tasks on hold (they are left out by default)")
    ap.add_argument("--link", action="append", default=[],
                    help="a → link: on add / ask the file it lives in; on done / link the RESULT -- what the item built (a route like /glossary, or a path). On done and link it replaces what was there")
    ap.add_argument("--note", help="one line to keep in mind while doing this item; the viewer shows it under the item")
    ap.add_argument("--tag", action="append", default=[],
                    help="on add / ask, a #tag for the new item; on tag, the tag to put on (or take off) an item that exists")
    ap.add_argument("--call", nargs="?", const="", default=None,
                    help="the people/ slug whose next call this item is raised on: stored as the #call: tag on add / ask / tag, so the Today page leaves it out and that person's call prep carries it; on list, the slug to filter by (bare --call = every call-scoped item)")
    ap.add_argument("--remove", action="store_true", help="on tag: take the tag off instead of putting it on")
    ap.add_argument("--people", action="append", default=[],
                    help="the people/ slugs this item concerns, comma-separated (on add / ask / people); on list, the slug to filter by")
    ap.add_argument("--source", help="who found it (night-agent-86, brain-lint, dispatcher, handoff): stored as the #source: tag on add / ask, required on repeat; on list, a PREFIX to filter by")
    ap.add_argument("--key", help="the producer's own stable id for a finding (L12:people/x.md, obs41): stored as the #key: tag on add / ask; on repeat, finds the one open item carrying it; on list, an exact filter")
    ap.add_argument("--open", action="store_true"); ap.add_argument("--questions", action="store_true"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--agent", default="brain-tasks")
    ap.add_argument("--verbose", action="store_true", help="on check: print each item a cold reader cannot follow, with why (correction #98)")
    a = ap.parse_args(argv)
    try:
        if a.action == "route":
            # WHICH LEDGER a finding about this file belongs on (2026-09-17). Read-only by design: no write, no log
            # line, so a producer may call it once per finding without leaving a trail of its own bookkeeping.
            if not a.ids:
                raise LedgerError("route wants a brain-relative path (e.g. route people/kyle-collins.md)")
            hid, rel = route(a.ids[0])
            print(json.dumps({"holon": hid, "file": rel}, ensure_ascii=False) if a.json else "%s\t%s" % (hid, rel))
            return
        if a.action == "check":
            targets = [(a.project, None)] if a.project else [(hid, None) for hid, _n, _r in ledgers()]
            if a.file:
                targets = [(None, a.file)]
            bad = 0
            for proj, fil in targets:
                path, rel = resolve(proj, fil)
                if not os.path.isfile(path):
                    print("MISSING  %s (registry names it, no file)" % rel); bad += 1; continue
                p = parse(read(path)); s = summary(p)
                if p["errors"]:
                    bad += 1; print("BROKEN   %s" % rel)
                    for e in p["errors"]:
                        print("   " + e)
                else:
                    print("OK       %s -- %d tasks (%d open, %d done, %d blocked, %d overdue%s), %d questions open"
                          % (rel, s["tasks"], s["open"], s["done"], s["blocked"], s["overdue"],
                             ", %d on hold" % s["held"] if s["held"] else "", s["questions_open"]))
                    # correction #98 (2026-10-02): reported, never a failure -- the exit code is unchanged
                    cold = [(i["id"], cold_reasons(i["text"], i["links"])) for i in p["items"] if addressed_to_zak_open(i)]
                    cold = [(iid, r) for iid, r in cold if r]
                    if cold:
                        print("   COLD   %d open item(s) addressed to @zak a cold reader cannot follow (correction #98): %s"
                              % (len(cold), ", ".join(iid for iid, _r in cold)))
                        if a.verbose:
                            for iid, r in cold:
                                print("      %s  %s" % (iid, "; ".join(r)))
            sys.exit(2 if bad else 0)
        if a.action == "list":
            # EVERY REGISTERED LEDGER when neither --project nor --file is given (2026-09-17). The boot recap's own
            # command -- CLAUDE.md section 5B step 6, `list --open --owner @zak` with no project -- answered "holon
            # None has no `tasks` field" until today. The registry is read the way `check` reads it: one target per
            # holon row that names a `tasks` file. One ledger prints exactly as it always did; several print one after
            # another under their own headers, and --json returns one object per ledger.
            targets = [(a.project, a.file)] if (a.project or a.file) else [(hid, None) for hid, _n, _r in ledgers()]
            if not targets:
                raise LedgerError("no holon in context/holon-registry.json names a `tasks` file (add one, or pass --file)")
            out, first = [], True
            for proj, fil in targets:
                path, rel = resolve(proj, fil)
                if not os.path.isfile(path):
                    if a.json:
                        out.append({"project": proj, "file": rel, "missing": True})
                    else:
                        print(("" if first else "\n") + "MISSING  %s (the registry names it, no file)" % rel)
                        first = False
                    continue
                p = parse(read(path))
                if a.json:
                    # --source / --key narrow the JSON too (2026-09-17): a producer asking "is my finding already
                    # filed?" wants its own items back, not the ledger. Items and groups are sliced together so they
                    # agree; `summary` stays the WHOLE ledger's counts, as it always was. The older filters
                    # (--open, --owner, --questions, --people, --held) still shape the printed list only -- unchanged.
                    q = {k: v for k, v in p.items() if k != "lines"}
                    if a.source or a.key:
                        q["items"] = [i for i in q["items"] if keeps(i, a)]
                        q["groups"] = {g: [i for i in rows if keeps(i, a)] for g, rows in q["groups"].items()}
                    out.append({"project": proj, "file": rel} | q | {"summary": summary(p)})
                    continue
                if not first:
                    print("")
                first = False
                print_list(rel, p, a)
            if a.json:
                print(json.dumps(out, ensure_ascii=False, indent=1))
            return
        if a.action == "repeat":
            # An id names the item; --key finds it instead, which is how a producer that does not remember ids (a cron,
            # a lint run) reaches the item it filed last time. Exit 3 = nothing open under that key, so the caller files
            # a NEW item; exit 4 = more than one, which means the key is not unique and a human has to say which.
            src = norm_source(a.source)
            if a.ids:
                if len(a.ids) > 1:
                    raise LedgerError("repeat takes one item id (a repeat is one finding raised again)")
                path, rel = resolve(a.project, a.file); iid = a.ids[0]
            else:
                k = norm_key(a.key)
                hits = open_by_key(k, a.project, a.file)
                if not hits:
                    sys.stderr.write("no open item with key %s\n" % k); sys.exit(3)
                if len(hits) > 1:
                    sys.stderr.write("key %s is on %d open items: %s\n"
                                     % (k, len(hits), ", ".join("%s (%s)" % (h[3]["id"], h[1]) for h in hits)))
                    sys.exit(4)
                _proj, rel, path, it = hits[0]; iid = it["id"]
            res = {}
            apply(path, rel, "repeat", agent=a.agent, id=iid, source=src, text=a.text, result=res)
            print("%s repeat %d" % (iid, res.get("repeats", 0)))
            return
        path, rel = resolve(a.project, a.file)
        if a.action == "init":
            init(path, rel, a.project or rel, a.name or a.project or rel, a.agent); print("created %s" % rel); return
        if a.action in ("add", "ask"):
            iid = apply(path, rel, a.action, agent=a.agent, text=a.text, owner=a.owner, to=a.to, frm=a.frm, due=a.due, milestone=a.milestone, links=a.link, tags=a.tag, people=a.people, note=a.note, source=a.source, key=a.key, call=a.call)
            print("%s %s" % (iid, "added" if a.action == "add" else "asked")); return
        if not a.ids:
            raise LedgerError("give at least one item id")
        for iid in a.ids:
            apply(path, rel, a.action, agent=a.agent, id=iid, text=a.text, owner=a.owner, by=a.by, reason=a.reason, people=a.people, links=a.link, note=a.note, until=a.until, due=a.due, tags=a.tag, call=a.call, remove=a.remove)
            print("%s %s" % (iid, a.action))
    except LedgerError as e:
        sys.exit("tasks.py: %s" % e)


if __name__ == "__main__":
    main()
