"""part_chat.py -- a part of serve.py (0.68.0, the review's finding 8: the three biggest sections of the server in files of their own).

What it holds: the chat: every conversation a real Claude Code session, its effort and sign-in, what every turn carries, sessions read back and adopted (/api/chat*, /api/chats, /api/agents, /api/session).

It is not imported as a module of its own. serve.py loads it with load_part() at the point where this code used to sit,
into serve.py's own namespace, so every name here is still serve.<name>: the tests that point serve.BRAIN at a scratch
folder reach it, derive_day.py's serve.live_binding() still answers, and nothing here imports anything serve.py has not.
Run serve.py, never this file.
"""

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
        # by 2.1.284 the bundle lives one level deeper, <version>/<build hash>/claude.exe (2026-10-06: without this
        # pattern the finder fell back to PATH's 2.1.121 and the chat refused fable)
        cands += glob.glob(os.path.join(appdata, "Claude", "claude-code", "*", "*", "claude.exe"))
    best = (None, None)
    for c in cands:
        v = cli_version_of(c)
        if v and (best[1] is None or tuple(int(x) for x in v.split(".")) > tuple(int(x) for x in best[1].split("."))):
            best = (c, v)
    return best


CLAUDE_BIN, CLI_VERSION = find_claude()


def setup_token():
    """The one-year token from 'claude setup-token', kept in the local-only file 'Claude SetupToken.txt' at the brain root
    (2026-10-06). The chat's child authenticates with it and never depends on the terminal's /login, whose refresh cycle
    signed every headless caller out from 9/25 to 10/02 and again by 10/06 (T-0279). Absent file: the child falls back to
    the terminal sign-in as before. The value is never logged, printed or sent to a page."""
    try:
        with open(os.path.join(BRAIN, "Claude SetupToken.txt"), encoding="utf-8") as f:
            tok = f.read().strip()
        return tok or None
    except OSError:
        return None


# ---- the chat's effort and its sign-in, shown on the page (0.67.0; the 10/06 review, finding 7; T-0279, T-0306) ----
CHAT_EFFORTS = ("low", "medium", "high", "xhigh", "max")   # claude --effort; none named = the CLI's own default
_cli_flags = {"effort": None}
_chat_auth = {"at": None, "error": None, "ok_at": None}    # the last turn's sign-in outcome, kept in memory only
AUTH_ERR_RE = re.compile(r"authenticat|oauth|not logged in|log ?in again|invalid api key|401", re.I)


def cli_has_effort():
    """Does the installed claude take --effort? Asked of its own --help once, the first time a page wants to know."""
    if _cli_flags["effort"] is None:
        ok = False
        if CLAUDE_BIN:
            try:
                r = subprocess.run([CLAUDE_BIN, "--help"], capture_output=True, text=True, timeout=20, env=headless_env())
                ok = "--effort" in (r.stdout or "")
            except Exception:                                     # noqa: BLE001
                ok = False
        _cli_flags["effort"] = ok
    return _cli_flags["effort"]


def chat_token_state():
    """What the chat signs in with, in words, with nothing of the token itself: the setup token file and its age (the token
    is good for a year from claude setup-token), or the terminal sign-in, plus the last sign-in failure a turn met."""
    ap = os.path.join(BRAIN, "Claude SetupToken.txt")
    row = {"source": "terminal sign-in", "file": None, "days": None, "expires": None, "lastError": _chat_auth["error"],
           "lastErrorAt": _chat_auth["at"], "lastOkAt": _chat_auth["ok_at"]}
    if setup_token():
        made = dt.datetime.fromtimestamp(os.path.getmtime(ap))
        row.update(source="setup token", file="Claude SetupToken.txt", days=(dt.datetime.now() - made).days,
                   expires=(made + dt.timedelta(days=365)).date().isoformat())
    if _chat_auth["error"] and (not _chat_auth["ok_at"] or _chat_auth["ok_at"] < _chat_auth["at"]):
        row["state"] = "signed out"
        row["fix"] = ("run claude setup-token in a terminal and put its output in Claude SetupToken.txt at the brain root"
                      if row["source"] == "setup token" else "run claude auth login in a terminal")
    else:
        row["state"] = "signed in" if row["source"] == "setup token" or _chat_auth["ok_at"] else "not checked yet"
    return row


def headless_env(**extra):
    """The environment for a child claude -p: its own session on this machine's own sign-in. A parent Claude Code
    session's variables (the session id, the host's proxy URL, CLAUDECODE), which the server inherits when the
    SessionStart hook starts it, are not passed down; the setup token is, when the file exists. Same shape as
    skills/question-sweep/sweep.py child_env."""
    env = dict(os.environ)
    hosted = "CLAUDECODE" in env or "CLAUDE_CODE_ENTRYPOINT" in env
    for k in list(env):
        if k == "CLAUDECODE" or k.startswith("CLAUDE_CODE_") or k in ("CLAUDE_PID", "CLAUDE_EFFORT", "CLAUDE_AGENT_SDK_VERSION")                 or k.startswith("CLAUDE_PREVIEW_") or (hosted and k == "ANTHROPIC_BASE_URL"):
            env.pop(k, None)
    tok = setup_token()
    if tok:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = tok
    env["BRAIN_HEADLESS_CHILD"] = "1"   # the SessionStart hook viewer-start.sh leaves at once in a child so marked (T-0309)
    env.update(extra)
    return env


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
    env = headless_env(ANTHROPIC_BASE_URL="http://127.0.0.1:1")
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
        out.append({"id": h["id"], "name": h.get("name") or h["id"], "short": ledger_label(h), "path": (path + "/") if path else "", "ledger": h["tasks"],
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
            "default_model": chat_default_model(), "context": chat_context_weight(),
            # 0.67.0: the effort picker and the sign-in line on the chat page and the home tile
            "efforts": list(CHAT_EFFORTS) if cli_has_effort() else [], "token": chat_token_state()}


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
    effort = str(data.get("effort") or "").strip().lower() or None          # 0.67.0: the effort picker
    if effort and effort not in CHAT_EFFORTS:
        return h._send(400, {"error": "effort must be one of: %s" % ", ".join(CHAT_EFFORTS)})
    if effort and not cli_has_effort():
        effort = None                                  # an older CLI: the turn runs at its default rather than failing
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
    if effort:
        args += ["--effort", effort]
    args += ["--resume", sid] if resume else ["--session-id", sid]
    try:
        proc = subprocess.Popen(args, cwd=BRAIN, env=headless_env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    # 0.67.0: the sign-in outcome of this turn, for the line on the chat page (T-0279)
    said = "".join(err_tail) + " " + str((result or {}).get("result") or "")
    if (result is None or (result or {}).get("is_error")) and AUTH_ERR_RE.search(said):
        _chat_auth.update(at=dt.datetime.now().isoformat(timespec="seconds"), error=clip(said.strip(), 200))
    elif result is not None and not result.get("is_error"):
        _chat_auth.update(ok_at=dt.datetime.now().isoformat(timespec="seconds"))
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
    if effort:
        rec["effort"] = effort
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
