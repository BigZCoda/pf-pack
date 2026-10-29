#!/usr/bin/env python
"""part_usage.py -- what used the plan: every turn on this computer, priced, for a day and for the week (viewer 0.84.0).

  python skills/brain-viewer/part_usage.py                          the days, today's top turns, the week's, the sessions
  python skills/brain-viewer/part_usage.py --session 4f04bf4f       ...and that session's turns today, in order
  python skills/brain-viewer/part_usage.py --day 2026-10-14 --days 7 --session <id prefix>
  python skills/brain-viewer/part_usage.py --json                   what GET /api/usage answers, as JSON

The server imports this module (GET /api/usage, the /usage page); run alone it prints the same numbers for the terminal,
so the page and the terminal can be compared line for line.

WHERE IT READS. The local Claude Code transcripts under ~/.claude/projects of the machine it runs on: every project folder,
each session's <id>.jsonl and its subagents' files (<id>/subagents/**/agent-*.jsonl). A team copy or a mentee's brain shows
its own owner's usage and nothing of any other computer. Nothing is written anywhere. A per-file cache keyed by size and
modification time keeps what was read; a transcript only grows, so a file that grew is read from where the last read
stopped, and a reload reads only what was appended.

THE MEASURE. Plan usage is not published per token, so each reply is priced at the API's list price for its model (the
claude-api skill's table, cached 2026-10-06), a proxy for what drains the plan's limits: "API $ equivalent". A cache
write costs 1.25 times the input price for the 5-minute cache and 2 times for the 1-hour cache (usage.cache_creation's
two counts; without that breakdown, cache_creation_input_tokens at 1.25). A model the table does not name costs 0.

THE RULES (each one was a wrong number before it was fixed):
  1. A reply is counted once across ALL files, by message.id: one reply is written as up to nine lines with the same id
     and usage, and a forked session (a side chat) copies its parent's lines verbatim into its own file. A file's own
     lines are counted before the lines it copied, so the original always wins.
  2. A turn is keyed by the line's own sessionId, never the file name: copied lines keep the parent's sessionId.
  3. A turn is everything one prompt set off. The user line carrying a promptId and a non-null turnOrigin starts it;
     the replies after it belong to it (they carry no promptId; the last one is carried forward).
  4. Subagents belong to the turn that launched them: only the first line of <session>/subagents/**/agent-*.jsonl
     carries the parent turn's promptId, and every reply in that file goes to that turn, counted as the workers' share.
  5. A turn, with all its subagents, is bucketed at its start, in local time (a turn can run past midnight).
  6. Who started it, from turnOrigin: human = you, task_notification = background wake, peer = another session,
     sdk = session brief, system = app event; scheduled, or a prompt that opens with <scheduled-task, = scheduled.
  7. What it was: the first 100 characters of the prompt, markup reduced to its label (a task notification is
     "background task finished", a scheduled task "scheduled: <name>", a command message its /command); no more of it.
  8. Titles from <session folder>/custom-title.json (customTitle), else the transcript's own custom-title line, shown
     as written ("New session" when it says so); a project folder is labelled by its name less this machine's
     <home>-Documents- prefix.
  9. Context size of a turn = the largest input + cache read + cache write of its main-thread replies. With the idle
     time before the turn, it is what explains an expensive wake: a session left idle past the cache's life writes its
     whole context to the cache again on the next prompt.
"""
import argparse
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
import json
import os
import re
import sys
import threading
import time

UNIT = "API $ equivalent, a proxy for plan usage"
PRICES_FROM = "the claude-api skill's price table, cached 2026-10-06"
# $ per million tokens: (the word in the model id, the name, input, output, cache read)
PRICES = (("fable", "Fable 5.1", 10.00, 50.00, 0.25),
          ("opus", "Opus 5.5", 4.00, 20.00, 0.20),
          ("sonnet", "Sonnet 5.5", 2.00, 10.00, 0.20),
          ("haiku", "Haiku 5.5", 0.10, 0.50, 0.01))
WRITE_5M, WRITE_1H = 1.25, 2.0          # a cache write, as a multiple of the input price
WHO = {"human": "you", "task_notification": "background wake", "peer": "another session", "sdk": "session brief",
       "system": "app event", "scheduled": "scheduled"}
WORDS_MAX = 100
TOP = 10
DAYS_MAX = 62
IDLE_NOTE = 300                         # seconds: a gap shorter than the 5-minute cache's life is not idle
ROOT = None                             # tests point this at a scratch folder; None = ~/.claude/projects


def default_root():
    return ROOT or os.path.join(os.path.expanduser("~"), ".claude", "projects")


# ---- the price of one reply ---------------------------------------------------------------------------------------------
def price(model):
    m = (model or "").lower()
    for key, _name, pin, pout, pread in PRICES:
        if key in m:
            return pin, pout, pread
    return None


def _num(src, key):
    v = src.get(key)
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def reply_parts(model, u):
    """-> (input $, cache write $, cache read $, output $, input tok, cache write tok, cache read tok, output tok)."""
    ti, tr, to = _num(u, "input_tokens"), _num(u, "cache_read_input_tokens"), _num(u, "output_tokens")
    cc = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else {}
    w5, w1 = _num(cc, "ephemeral_5m_input_tokens"), _num(cc, "ephemeral_1h_input_tokens")
    whole = _num(u, "cache_creation_input_tokens")
    if not cc or (w5 + w1 == 0 and whole):      # no breakdown: the whole write at the 5-minute rate
        w5, w1 = whole, 0
    tw = max(whole, w5 + w1)
    p = price(model)
    if not p:
        return 0.0, 0.0, 0.0, 0.0, ti, tw, tr, to
    pin, pout, pread = p
    return (ti * pin / 1e6, (w5 * WRITE_5M + w1 * WRITE_1H) * pin / 1e6, tr * pread / 1e6, to * pout / 1e6, ti, tw, tr, to)


# ---- what a turn was, in its first words --------------------------------------------------------------------------------
_TAG = re.compile(r"</?[A-Za-z][\w-]*(?:\s[^>]*)?>")


def clip(s, n=WORDS_MAX):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n].rstrip() + "…"


def prompt_text(content):
    """A prompt's text: a plain string, or the text blocks of a list joined."""
    if isinstance(content, list):
        return "\n".join(b.get("text") or "" for b in content if isinstance(b, dict) and b.get("type") == "text")
    return str(content or "")


def first_words(content):
    """Rule 7: the prompt's first 100 characters, its markup reduced to a label."""
    s = prompt_text(content).strip()
    if not s and isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "image" for b in content):
        return "[picture]"
    m = re.match(r'<scheduled-task\b[^>]*?\bname="([^"]*)"', s)
    if m:
        return clip("scheduled: " + m.group(1))
    if s.startswith("<task-notification"):
        summ = re.search(r"<summary>(.*?)</summary>", s, re.S)
        what = ""
        if summ:
            q = re.search(r'"(.+?)"', summ.group(1))        # the task's own name, between its quotes
            what = (q.group(1) if q else summ.group(1)).strip()
        return clip("background task finished" + (": " + what if what else ""))
    if s.startswith(("<command-message", "<command-name")):
        m = re.search(r"<command-name>\s*(/?[^<\s]+)\s*</command-name>", s)
        if m:
            args = re.search(r"<command-args>(.*?)</command-args>", s, re.S)
            cmd = m.group(1) if m.group(1).startswith("/") else "/" + m.group(1)
            return clip(cmd + (" " + args.group(1) if args and args.group(1).strip() else ""))
    body = re.sub(r"<system-reminder>.*?</system-reminder>", " ", s, flags=re.S)
    if not body.strip():                                    # a notice that is nothing but a reminder: read the reminder
        body = re.sub(r"</?system-reminder>", " ", s)
    body = re.sub(r"^\s*Another Claude session sent a message:\s*", "", body)
    m = re.search(r"<agent-message\b[^>]*>(.*?)(?:</agent-message>|$)", body, re.S)
    if m:
        inner = m.group(1)
        if "[Subagent hand-back]" in inner:
            k = inner.find("The report follows:")
            inner = inner[k + len("The report follows:"):] if k >= 0 else inner.replace("[Subagent hand-back]", "")
            body = "a worker's report: " + inner
        else:
            body = "message from a worker: " + inner
    else:
        m = re.search(r"<cross-session-message\b([^>]*)>(.*?)(?:</cross-session-message>|$)", body, re.S)
        if m:
            nm = re.search(r'from-name="([^"]*)"', m.group(1))
            body = ('from "%s": ' % nm.group(1) if nm and nm.group(1) else "from another session: ") + m.group(2)
    body = re.sub(r"<pasted_content\b[^>]*>", " [pasted] ", body)
    body = _TAG.sub(" ", body)                              # any other tag goes; the words inside it stay
    body = re.sub(r"\s*\(local_[0-9a-f-]{8,}\)", "", body)  # a session's internal id in the app's own notices
    return clip(body)


def who_of(origin):
    """Rule 6. The parse sets origin "scheduled" for a prompt that opens with <scheduled-task, whatever its turnOrigin."""
    if not origin:
        return "unknown"
    return WHO.get(origin, str(origin).replace("_", " "))


# ---- labels -------------------------------------------------------------------------------------------------------------
def project_label(folder):
    """A project folder by its name less this machine's <home>-Documents- prefix (the home folder as Claude Code spells
    a path: every character that is not a letter or a digit becomes -)."""
    home = re.sub(r"[^A-Za-z0-9]", "-", os.path.expanduser("~"))
    name = folder
    for pre in (home + "-Documents-", home + "-OneDrive-Documents-", home + "-"):
        if folder.startswith(pre) and len(folder) > len(pre):
            name = folder[len(pre):]
            break
    else:
        if folder == home:
            return "home folder"
    name = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "…", name).strip("-")
    return name or folder


def model_name(mid):
    """claude-opus-5-5 -> Opus 5.5; an id with a date stamp keeps its version only."""
    m = re.sub(r"^claude-", "", str(mid or ""))
    m = re.sub(r"-\d{8}$", "", m)
    parts = m.split("-")
    if len(parts) >= 2 and parts[0].isalpha() and all(p.isdigit() for p in parts[1:]):
        return parts[0].capitalize() + " " + ".".join(parts[1:])
    return m


def tokens_k(n):
    n = int(n or 0)
    if n >= 1_000_000:
        return "%.1fM" % (n / 1e6)
    if n >= 1000:
        return "%dK" % round(n / 1000)
    return str(n)


def duration(sec):
    sec = int(sec or 0)
    if sec >= 2 * 86400:
        return "%d days" % (sec // 86400)
    h, m = sec // 3600, (sec % 3600) // 60
    if h:
        return "%d h %d min" % (h, m) if m else "%d h" % h
    return "%d min" % max(1, m)


def why(t):
    """Where most of a turn's cost went, in words: its workers, writing its context to the cache (and how long the
    session had been idle), re-reading its context call after call, its output, or new input."""
    total = t["main"] + t["sub"]
    if total <= 0:
        return ""
    parts = {"workers": t["sub"], "write": t["cw"], "read": t["cr"], "output": t["co"], "input": t["ci"]}
    k, v = max(parts.items(), key=lambda kv: kv[1])
    pct = int(round(100 * v / total))
    if k == "workers":
        n = len(t["agents"])
        return "%d%% was its %s" % (pct, "worker" if n == 1 else "%d workers" % n if n else "workers")
    if k == "write":
        idle = t.get("idle")
        whole = t["ctx"] and t["tw"] >= 0.6 * t["ctx"]
        if idle is not None and idle >= IDLE_NOTE and whole:
            return "%d%% was writing its whole %s context to the cache again, after %s idle" % (pct, tokens_k(t["ctx"]), duration(idle))
        return "%d%% was writing %s tokens to the cache" % (pct, tokens_k(t["tw"]))
    if k == "read":
        return "%d%% was %d call%s, each re-reading up to %s of context" % (pct, t["calls"], "" if t["calls"] == 1 else "s", tokens_k(t["ctx"]))
    if k == "output":
        return "%d%% was %s tokens of output" % (pct, tokens_k(t["to"]))
    return "%d%% was %s tokens of new input" % (pct, tokens_k(t["ti"]))


# ---- the scan -----------------------------------------------------------------------------------------------------------
def _epoch(ts):
    try:
        return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


class _File:
    __slots__ = ("path", "kind", "project", "fsid", "agent", "size", "mtime", "offset", "pid", "first", "title", "starts", "replies")

    def __init__(self, path, kind, project, fsid, agent):
        self.path, self.kind, self.project, self.fsid, self.agent = path, kind, project, fsid, agent
        self.size, self.mtime, self.offset = -1, -1.0, 0
        self.pid = None              # main: the last turn-starting promptId; carried forward over the replies
        self.first = False           # sub: the first line was read, and self.pid is the launching turn's promptId
        self.title = None            # main: the transcript's own last custom-title line
        self.starts = []             # (sid, pid, epoch, origin, words, own)
        self.replies = []            # (mid, sid, pid, epoch, model, ci, cw, cr, co, ti, tw, tr, to, own, sub)


class Scanner:
    """One per root. refresh() reads what changed since the last call; assemble() builds the turns from what was read."""

    def __init__(self, root):
        self.root = root
        self.files = {}
        self.titles = {}             # custom-title.json path -> (mtime, title)
        self.lock = threading.Lock()

    def walk(self):
        """-> [(path, kind, project folder, session id of the file, agent name, stat)]: every <id>.jsonl in a project
        folder, and every agent-*.jsonl under <id>/subagents/ at any depth (a workflow's agents sit one folder lower)."""
        out = []
        try:
            projects = [e for e in os.scandir(self.root) if e.is_dir(follow_symlinks=False)]
        except OSError:
            return out
        for p in projects:
            try:
                entries = list(os.scandir(p.path))
            except OSError:
                continue
            for e in entries:
                if e.name.endswith(".jsonl") and e.is_file(follow_symlinks=False):
                    out.append((e.path, "main", p.name, e.name[:-6], None, e.stat()))
                elif e.is_dir(follow_symlinks=False):
                    sub = os.path.join(e.path, "subagents")
                    if not os.path.isdir(sub):
                        continue
                    stack = [sub]
                    while stack:
                        d = stack.pop()
                        try:
                            kids = list(os.scandir(d))
                        except OSError:
                            continue
                        for k in kids:
                            if k.is_dir(follow_symlinks=False):
                                stack.append(k.path)
                            elif k.name.startswith("agent-") and k.name.endswith(".jsonl"):
                                out.append((k.path, "sub", p.name, e.name, k.name[:-6], k.stat()))
        return out

    def _read(self, f, st):
        """Read the complete lines appended since f.offset (from 0 for a new, shrunk or rewritten file)."""
        start = f.offset
        with open(f.path, "rb") as fh:
            if start:
                fh.seek(start - 1)
                if fh.read(1) != b"\n":                      # not where the last read stopped: read it whole again
                    f.__init__(f.path, f.kind, f.project, f.fsid, f.agent)
                    start = 0
            fh.seek(start)
            data = fh.read(max(0, st.st_size - start))
        cut = data.rfind(b"\n")
        data = data[:cut + 1] if cut >= 0 else b""
        f.offset = start + len(data)
        f.size, f.mtime = st.st_size, st.st_mtime
        sub = f.kind == "sub"
        for raw in data.split(b"\n"):
            if not raw:
                continue
            if sub and not f.first:
                pass                                         # rule 4: a subagent's first line names the launching turn
            elif b'"usage"' not in raw and b'"turnOrigin"' not in raw and b'"custom-title"' not in raw:
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            if sub and not f.first:
                f.first, f.pid = True, d.get("promptId")
            kind = d.get("type")
            if kind == "custom-title":
                if not sub and d.get("customTitle"):
                    f.title = d.get("customTitle")
                continue
            sid = d.get("sessionId") or f.fsid
            own = sid == f.fsid
            if kind == "user" and d.get("turnOrigin") and not sub:        # rule 3: a prompt starts a turn
                f.pid = d.get("promptId") or f.pid
                content = (d.get("message") or {}).get("content")
                origin = d.get("turnOrigin")
                if prompt_text(content).lstrip().startswith("<scheduled-task"):
                    origin = "scheduled"
                f.starts.append((sid, f.pid, _epoch(d.get("timestamp")), origin, first_words(content), own))
                continue
            if kind != "assistant":
                continue
            m = d.get("message") or {}
            u = m.get("usage")
            if not isinstance(u, dict):
                continue
            ts = _epoch(d.get("timestamp"))
            if ts is None:
                continue
            model = m.get("model") or ""
            parts = reply_parts(model, u)
            pid = d.get("promptId") or f.pid
            f.replies.append((m.get("id"), sid, pid, ts, model) + parts + (own, sub or bool(d.get("isSidechain"))))
        return len(data)

    def refresh(self, since):
        """Read every file changed at or after `since` (epoch) that changed since the last read. -> the files in play and
        what the read cost."""
        t0 = time.perf_counter()
        live, read, nbytes, nread = [], 0, 0, 0
        paths = set()
        for path, kind, project, fsid, agent, st in self.walk():
            paths.add(path)
            if st.st_mtime < since:
                continue
            f = self.files.get(path)
            if f is None or st.st_size < f.offset or (st.st_size == f.size and st.st_mtime != f.mtime):
                f = self.files[path] = _File(path, kind, project, fsid, agent)
            if f.size != st.st_size or f.mtime != st.st_mtime:
                nread += self._read(f, st)
                read += 1
            live.append(f)
            nbytes += st.st_size
        for gone in [p for p in self.files if p not in paths]:
            del self.files[gone]
        return live, {"files": len(live), "bytes": nbytes, "read": read, "readBytes": nread,
                      "ms": int((time.perf_counter() - t0) * 1000)}

    def title_of(self, project, sid, fallback):
        ap = os.path.join(self.root, project, sid, "custom-title.json")
        try:
            mt = os.stat(ap).st_mtime
        except OSError:
            return fallback
        hit = self.titles.get(ap)
        if hit and hit[0] == mt:
            return hit[1] or fallback
        try:
            with open(ap, "r", encoding="utf-8-sig") as fh:
                title = (json.load(fh) or {}).get("customTitle")
        except (OSError, ValueError, AttributeError):
            title = None
        self.titles[ap] = (mt, title)
        return title or fallback


def _new_turn(sid, pid, start, origin, words):
    return {"sid": sid, "pid": pid, "start": start, "origin": origin, "words": words, "main": 0.0, "sub": 0.0,
            "ci": 0.0, "cw": 0.0, "cr": 0.0, "co": 0.0, "ti": 0, "tw": 0, "tr": 0, "to": 0, "calls": 0, "ctx": 0,
            "end": start, "models": set(), "smodels": set(), "agents": set(), "found": origin is not None}


def assemble(files):
    """The turns, from the files in play: rules 1 to 4 and 9. A file's own lines go first (rule 1)."""
    turns = {}
    for own_pass in (True, False):
        for f in files:
            for sid, pid, ts, origin, words, own in f.starts:
                if own is not own_pass or ts is None:
                    continue
                t = turns.get((sid, pid))
                if t is None:
                    turns[(sid, pid)] = _new_turn(sid, pid, ts, origin, words)
    seen = set()
    for own_pass in (True, False):
        for f in files:
            for r in f.replies:
                mid, sid, pid, ts, model, ci, cw, cr, co, ti, tw, tr, to, own, sub = r
                if own is not own_pass:
                    continue
                if mid:
                    if mid in seen:
                        continue
                    seen.add(mid)
                t = turns.get((sid, pid))
                if t is None:                                # no prompt line found for it: a turn of its own, unnamed
                    t = turns[(sid, pid)] = _new_turn(sid, pid, ts, None, "")
                if not t["found"] and ts < t["start"]:
                    t["start"] = ts
                cost = ci + cw + cr + co
                name = model if model and not model.startswith("<") else ""
                if sub:
                    t["sub"] += cost
                    if f.agent:
                        t["agents"].add(f.agent)
                    if name:
                        t["smodels"].add(name)
                    continue
                t["main"] += cost
                t["ci"] += ci; t["cw"] += cw; t["cr"] += cr; t["co"] += co
                t["ti"] += ti; t["tw"] += tw; t["tr"] += tr; t["to"] += to
                t["calls"] += 1
                t["ctx"] = max(t["ctx"], ti + tr + tw)
                t["end"] = max(t["end"], ts)
                if name:
                    t["models"].add(name)
    # the idle time before each turn: from the end of the session's turn before it (its main thread's last reply)
    by_sid = {}
    for t in turns.values():
        by_sid.setdefault(t["sid"], []).append(t)
    for rows in by_sid.values():
        rows.sort(key=lambda t: t["start"])
        prev = None
        for t in rows:
            t["idle"] = max(0.0, t["start"] - prev) if prev is not None else None
            prev = max(prev, t["end"]) if prev is not None else t["end"]
    return turns


# ---- the report ---------------------------------------------------------------------------------------------------------
_SCANNERS = {}
_SCANNERS_LOCK = threading.Lock()


def scanner(root=None):
    root = os.path.abspath(root or default_root())
    with _SCANNERS_LOCK:
        s = _SCANNERS.get(root)
        if s is None:
            s = _SCANNERS[root] = Scanner(root)
    return s


def _local(ts):
    return dt.datetime.fromtimestamp(ts).astimezone()


def _r(x):
    return round(x + 0.0, 4)


def _c(x):
    """A $ figure to the cent, half up, so the page and the terminal print the same digits (a float printed with %.2f
    and the same float shown by a browser can round a half cent apart)."""
    return float(Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def report(days=7, day=None, session=None, root=None, top=TOP, now=None):
    """What GET /api/usage answers. `days` ending today; `day` (YYYY-MM-DD, inside them) picks the day the top list and
    a timeline are for, today by default; `session` (an id or the start of one) adds that session's turns on that day."""
    now = (now or dt.datetime.now()).astimezone()
    today = now.date()
    try:
        days = max(1, min(int(days), DAYS_MAX))
    except (TypeError, ValueError):
        raise ValueError("days must be a whole number")
    first_day = today - dt.timedelta(days=days - 1)
    since = dt.datetime.combine(first_day, dt.time.min).astimezone().timestamp()
    if day:
        try:
            picked = dt.date.fromisoformat(str(day))
        except ValueError:
            raise ValueError("day must be YYYY-MM-DD")
        if not first_day <= picked <= today:
            raise ValueError("%s is not one of the %d days (%s to %s)" % (picked, days, first_day, today))
    else:
        picked = today
    sc = scanner(root)
    with sc.lock:
        files, scan = sc.refresh(since)
        turns = assemble(files)
        projects, titles = {}, {}
        for f in files:                                       # a session's project and title from its own transcript
            if f.kind == "main":
                projects.setdefault(f.fsid, f.project)
                if f.title:
                    titles[f.fsid] = f.title
        for f in files:                                       # a session whose own transcript is not in play
            projects.setdefault(f.fsid, f.project)
        title_for = {}

        def info(sid):
            if sid not in title_for:
                folder = projects.get(sid, "")
                title_for[sid] = (sc.title_of(folder, sid, titles.get(sid)) if folder else titles.get(sid), project_label(folder) if folder else "")
            return title_for[sid]

        # a reply with no prompt line found and no cost (a synthetic placeholder) is not a turn anyone started
        window = [t for t in turns.values() if t["start"] >= since and (t["found"] or t["main"] + t["sub"] > 0)]
        for t in window:
            t["day"] = _local(t["start"]).date()
            t["total"] = t["main"] + t["sub"]
        def row(t):
            title, project = info(t["sid"])
            st = _local(t["start"])
            return {"session": t["sid"], "short": t["sid"][:8], "title": title, "project": project,
                    "start": st.isoformat(timespec="seconds"), "day": st.date().isoformat(), "time": st.strftime("%H:%M"),
                    "total": _c(t["total"]), "main": _c(t["main"]), "sub": _c(t["sub"]),
                    "subShare": int(round(100 * t["sub"] / t["total"])) if t["total"] else 0,
                    "calls": t["calls"], "ctx": t["ctx"], "who": who_of(t["origin"]), "origin": t["origin"],
                    "words": t["words"], "models": sorted({model_name(m) for m in t["models"]}), "subModels": sorted({model_name(m) for m in t["smodels"]}),
                    "subagents": len(t["agents"]), "why": why(t),
                    "idleMin": int(t["idle"] // 60) if t.get("idle") is not None else None,
                    "parts": {"input": _r(t["ci"]), "cacheWrite": _r(t["cw"]), "cacheRead": _r(t["cr"]), "output": _r(t["co"]),
                              "workers": _r(t["sub"])},
                    "tokens": {"input": t["ti"], "cacheWrite": t["tw"], "cacheRead": t["tr"], "output": t["to"]}}

        rank = lambda rows: sorted(rows, key=lambda t: (-t["total"], -t["start"]))
        daylist = []
        for i in range(days):
            d = first_day + dt.timedelta(days=i)
            rows = [t for t in window if t["day"] == d]
            daylist.append({"day": d.isoformat(), "label": "%s %d/%d" % (d.strftime("%a"), d.month, d.day),
                            "weekday": d.strftime("%A"), "today": d == today,
                            "total": _c(sum(t["total"] for t in rows)), "sub": _c(sum(t["sub"] for t in rows)), "turns": len(rows)})
        on_day = [t for t in window if t["day"] == picked]
        sessions = {}
        for t in window:
            s = sessions.setdefault(t["sid"], {"total": 0.0, "sub": 0.0, "turns": 0, "first": t["start"], "last": t["start"],
                                               "dayTotal": 0.0, "dayTurns": 0, "models": set()})
            s["total"] += t["total"]; s["sub"] += t["sub"]; s["turns"] += 1
            s["first"] = min(s["first"], t["start"]); s["last"] = max(s["last"], t["start"])
            s["models"] |= t["models"]
            if t["day"] == picked:
                s["dayTotal"] += t["total"]; s["dayTurns"] += 1
        srows = []
        for sid, s in sorted(sessions.items(), key=lambda kv: (-kv[1]["total"], -kv[1]["last"])):
            title, project = info(sid)
            srows.append({"id": sid, "short": sid[:8], "title": title, "project": project, "total": _c(s["total"]),
                          "sub": _c(s["sub"]), "subShare": int(round(100 * s["sub"] / s["total"])) if s["total"] else 0,
                          "turns": s["turns"], "dayTotal": _c(s["dayTotal"]), "dayTurns": s["dayTurns"],
                          "first": _local(s["first"]).isoformat(timespec="seconds"),
                          "last": _local(s["last"]).isoformat(timespec="seconds"), "models": sorted({model_name(m) for m in s["models"]})})
        bywho = {}
        for t in window:
            k = who_of(t["origin"])
            bywho[k] = bywho.get(k, 0.0) + t["total"]
        out = {"unit": UNIT, "pricesFrom": PRICES_FROM,
               "prices": [{"model": name, "match": key, "input": pin, "output": pout, "cacheRead": pread,
                           "cacheWrite5m": round(pin * WRITE_5M, 4), "cacheWrite1h": round(pin * WRITE_1H, 4)}
                          for key, name, pin, pout, pread in PRICES],
               "now": now.isoformat(timespec="seconds"), "today": today.isoformat(), "day": picked.isoformat(),
               "days": daylist, "total": _c(sum(t["total"] for t in window)), "turns": len(window),
               "dayTotal": _c(sum(t["total"] for t in on_day)), "dayTurns": len(on_day),
               "top": {"day": [row(t) for t in rank(on_day)[:top]], "week": [row(t) for t in rank(window)[:top]]},
               "sessions": srows,
               "byWho": [{"who": k, "total": _c(v)} for k, v in sorted(bywho.items(), key=lambda kv: -kv[1])],
               "timeline": None, "scan": scan}
        if session:
            want = str(session).strip()
            hits = sorted({sid for sid in sessions if sid.startswith(want)}) or sorted({t["sid"] for t in turns.values() if t["sid"].startswith(want)})
            if len(hits) > 1:
                raise ValueError("more than one session starts with %s: %s" % (want, ", ".join(h[:12] for h in hits[:5])))
            if not hits:
                out["timeline"] = {"session": want, "error": "no session starting with %s ran in these %d days" % (want, days), "turns": [], "days": []}
            else:
                sid = hits[0]
                title, project = info(sid)
                mine = [t for t in window if t["sid"] == sid]
                rows = sorted((t for t in mine if t["day"] == picked), key=lambda t: t["start"])
                ran = {}
                for t in mine:
                    r = ran.setdefault(t["day"].isoformat(), [0.0, 0])
                    r[0] += t["total"]; r[1] += 1
                out["timeline"] = {"session": sid, "short": sid[:8], "title": title, "project": project, "day": picked.isoformat(),
                                   "total": _c(sum(t["total"] for t in rows)), "turns": [row(t) for t in rows],
                                   "days": [{"day": k, "total": _c(v[0]), "turns": v[1]} for k, v in sorted(ran.items())]}
    return out


# ---- the terminal -------------------------------------------------------------------------------------------------------
def _label(r):
    return "%s / %s (%s)" % (r.get("project") or "?", r.get("title") or "untitled", r.get("short") or r.get("session", "")[:8])


def _models(r):
    main = "/".join(r.get("models") or []) or "-"
    return main + ("  workers " + "/".join(r["subModels"]) if r.get("subModels") else "")


def _top(title, rows):
    print("\n" + title)
    if not rows:
        print("  (none)")
    for r in rows:
        print("  %8.2f  %s %s  %-15s workers %3d%%  %s  %s" % (r["total"], dt.date.fromisoformat(r["day"]).strftime("%a"), r["time"],
                                                               r["who"], r["subShare"], _label(r), _models(r)))
        print("            \"%s\"" % r["words"])
        if r.get("why"):
            print("            %s" % r["why"])


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="the turns that used the most, priced at API rates (a proxy for plan usage)")
    ap.add_argument("--days", type=int, default=7, help="the days to read, ending today (default 7)")
    ap.add_argument("--day", help="the day the top list and the timeline are for, YYYY-MM-DD (default today)")
    ap.add_argument("--session", help="a session id, or the start of one: its turns on that day, in order")
    ap.add_argument("--root", help="the transcripts folder (default ~/.claude/projects)")
    ap.add_argument("--json", action="store_true", help="print what GET /api/usage answers")
    a = ap.parse_args(argv)
    try:
        out = report(days=a.days, day=a.day, session=a.session, root=a.root)
    except ValueError as e:
        print("part_usage: %s" % e, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    s = out["scan"]
    print("read %d files, %.0f MB, in %.1f s (%d read this time); %d turns in %d days. %s."
          % (s["files"], s["bytes"] / 1e6, s["ms"] / 1000.0, s["read"], out["turns"], len(out["days"]), UNIT))
    print("\nBY DAY ($):")
    for d in out["days"]:
        print("  %-10s %9.2f  %4d turns%s" % (d["label"], d["total"], d["turns"], "   today" if d["today"] else ""))
    print("  %-10s %9.2f  %4d turns" % ("all", out["total"], out["turns"]))
    picked = dt.date.fromisoformat(out["day"])
    _top("TOP TURNS, %s %d/%d:" % (picked.strftime("%a"), picked.month, picked.day), out["top"]["day"])
    _top("TOP TURNS, THE %d DAYS:" % len(out["days"]), out["top"]["week"])
    print("\nSESSIONS, THE %d DAYS:" % len(out["days"]))
    for r in out["sessions"][:12]:
        print("  %8.2f  %4d turns  workers %3d%%  %s" % (r["total"], r["turns"], r["subShare"], _label(r)))
    if len(out["sessions"]) > 12:
        print("  ... and %d more" % (len(out["sessions"]) - 12))
    tl = out.get("timeline")
    if tl:
        print("\nTIMELINE, %s, %s:" % (tl.get("short") or tl["session"], out["day"]))
        if tl.get("error"):
            print("  " + tl["error"])
        for r in tl["turns"]:
            idle = (" after %s idle" % duration(r["idleMin"] * 60)) if (r.get("idleMin") or 0) * 60 >= IDLE_NOTE else ""
            print("  %s  %7.2f  main %7.2f (%3d calls, context up to %5s)  workers %6.2f  %-15s%s" % (
                r["time"], r["total"], r["main"], r["calls"], tokens_k(r["ctx"]), r["sub"], r["who"], idle))
            print("         \"%s\"" % r["words"][:90])
        if not tl["turns"] and tl.get("days"):
            print("  none that day; it ran on " + ", ".join("%s ($%.2f)" % (d["day"], d["total"]) for d in tl["days"]))
    print("\nBY WHO STARTED IT:")
    for r in out["byWho"]:
        print("  %8.2f  %s" % (r["total"], r["who"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
