#!/usr/bin/env python3
"""adapter.py — the Forge's adapter level, generated (2026-09-18, viewer Q-0022).

One adapter is a boundary the brain calls across. Its PORTS are the routes on the other
side, read from that system's own machine-readable inventory; its CABLES are what calls
them on the brain side and what they reach on the app side. Nothing here is drawn by
hand and nothing here is stored in a canvas: the whole layer is computed per request
from four files that already exist, so the picture cannot lag the app the way the
hand-drawn Ferryman map did.

  the registry    skills/brain-viewer/adapters.json     (which boundaries exist, and their hand-written ports)
  the inventory   pf-app-holon/pf-app-api-catalog.json  (the app describing itself, GET /api/v1)
  the callers     skills/**/*.py and skills/**/*.md     (who names a path)
  when it ran     context/log.md                        (the Ferryman's own lines)
  is it broken    pf-app-holon/pf-app-agent-status.json (the component rounds' probes) + the log

Second pass, 2026-09-18, viewer Q-0024 ("The port groups can also be manually added as well, but yes,
I think that that works"): which adapters exist is a FILE now, `skills/brain-viewer/adapters.json`, not
a dict in this module — one row per boundary with its name, its catalog (or null, when the system does
not describe itself), its base URL, its twin and its `manualGroups`. A manual group's ports are merged
with the catalog's and carry `source: "manual"`, so the sheet draws them dotted and a hand-written claim
is never mistaken for the app's own word. Every port also carries a `tier` — personal, admin or hollow —
which is what the sheet orders a group by and what the compact in-a-cell form counts.

Two readers, one generator: `adapter_api()` answers GET /api/adapter in serve.py, and
`write_twin()` writes the same JSON as markdown to pf-app-holon/pf-app-adapter-<name>.md
so an agent can grep what the picture shows. They cannot disagree because the markdown is
rendered from the JSON. brain-lint L18 fails the run when the twin's header date and the
catalog's _fetchedAt differ, which is the one way the two could come apart.

Design: deliverables/ferryman-adapter-level-design-2026-09-18.md
"""

import datetime as dt
import json
import os
import re

STALE_DAYS = 7                 # past this the adapter carries a clock: the picture is a snapshot
LOG_DAYS = 14                  # how far back the health scan and lastRan read
SCAN_EXT = (".py", ".md")

REGISTRY_REL = "skills/brain-viewer/adapters.json"   # WHICH adapters exist (Q-0024); this file holds only their defaults

# The operational detail a registry row does not carry: which folders to scan for callers, the
# brain-side mirror per resource, which log lines could be this adapter's. Keyed by the same name
# as the registry row. A registry name with no row here still works -- the host and the prefix are
# read off its `base` and the scan defaults to skills/ -- it simply has no mirrors and no log match.
ADAPTERS = {
    "ferryman": {
        "name": "ferryman",
        "label": "Ferryman",
        "app": "PF App",
        "appHref": "https://app.prospectforge.us",
        "host": "app.prospectforge.us",
        "prefix": "/api/v1",
        "base": "https://app.prospectforge.us/api/v1",
        "catalog": "pf-app-holon/pf-app-api-catalog.json",
        "probes": "pf-app-holon/pf-app-agent-status.json",
        "twin": "pf-app-holon/pf-app-adapter-ferryman.md",
        "scan": ("skills",),
        "runner": "skills/ferryman/pull.py",
        "refresh": "python skills/ferryman/pull.py --pull",
        # the brain-side copy of a resource, per resource prefix. A resource with no row here
        # has no mirror, which is the visible form of "read across the boundary, never kept".
        "mirrors": {
            "(root)": "pf-app-holon/pf-app-api-catalog.json",
            "profile": "pf-app-holon/pf-app-profile-me.json",
            "tasks": "pf-app-holon/pf-app-tasks.json",
            "contacts": "pf-app-holon/pf-app-contacts.json",
            "projects": "pf-app-holon/pf-app-projects.json",
            "presets": "pf-app-holon/pf-app-presets.json",
            "context-documents": "pf-app-holon/pf-app-context-documents.json",
            "transcripts": "pf-app-holon/transcripts/",
        },
        # which log lines can carry evidence for this adapter at all
        "logAgents": ("ferryman", "pf-app-agent"),
        "logText": r"pull\.py|push\.py|\bferryman\b|rounds-check|pf-app-agent|app\.prospectforge",
    },
}

# ---------------------------------------------------------------- the registry (Q-0024)

_registry_cache = {}
_BASE_RE = re.compile(r"^(?:https?://)?([^/]+)(/.*)?$")


def _derive(base):
    """host and prefix off a base URL, so a registry row needs neither spelled out."""
    m = _BASE_RE.match(str(base or "").strip())
    if not m:
        return "", "/api/v1"
    host = m.group(1)
    prefix = (m.group(2) or "").rstrip("/")
    return host, (prefix or "/api/v1")


def load_registry(root, force=False):
    """skills/brain-viewer/adapters.json merged over the defaults above. -> ({name: cfg}, error).

    The FILE decides which adapters exist. A row's fields win; the defaults fill in the parts a
    human should not have to type (the scan roots, the mirrors, the log pattern). When the file is
    missing or unreadable the built-in defaults still answer, and the error says so rather than
    leaving the Forge with no adapters and no reason.
    """
    ap = os.path.join(root, REGISTRY_REL.replace("/", os.sep))
    key = os.path.getmtime(ap) if os.path.isfile(ap) else None
    hit = _registry_cache.get(root)
    if hit and hit[0] == key and not force:
        return hit[1], hit[2]
    rows, err = [], None
    if key is None:
        err = "no adapter registry at %s -- the built-in defaults are answering" % REGISTRY_REL
    else:
        try:
            with open(ap, "r", encoding="utf-8-sig") as f:
                doc = json.load(f)
            rows = list(doc.get("adapters") or [])
        except Exception as e:                       # noqa: BLE001
            err = "adapter registry unreadable (%s: %s) -- the built-in defaults are answering" % (type(e).__name__, e)
    out = {}
    for name, base_cfg in ADAPTERS.items():
        out[name] = dict(base_cfg)
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip().lower()
        if not name:
            continue
        cfg = dict(out.get(name) or {})
        base = row.get("base") or cfg.get("base") or ""
        host, prefix = _derive(base)
        cfg.setdefault("scan", ("skills",))
        cfg["name"] = name
        cfg["base"] = base
        cfg["host"] = cfg.get("host") or host
        cfg["prefix"] = cfg.get("prefix") or prefix
        cfg["label"] = row.get("label") or cfg.get("label") or name.replace("-", " ").title()
        for k in ("app", "appHref", "twin", "runner", "refresh"):
            if row.get(k):
                cfg[k] = row[k]
        cfg.setdefault("app", cfg["label"])
        cfg.setdefault("twin", "pf-app-holon/pf-app-adapter-%s.md" % name)
        # `catalog` is the one field a row may set to null on purpose: the system does not describe itself
        if "catalog" in row:
            cfg["catalog"] = row["catalog"]
        cfg["manualGroups"] = row.get("manualGroups") or []
        cfg["registryRow"] = True
        out[name] = cfg
    for name, cfg in out.items():
        cfg.setdefault("manualGroups", [])
        cfg.setdefault("registryRow", False)
    _registry_cache[root] = (key, out, err)
    return out, err


def list_adapters(root):
    """GET /api/adapters: one light row per registered boundary, no catalog read."""
    reg, err = load_registry(root)
    rows = []
    for name in sorted(reg):
        cfg = reg[name]
        cat = cfg.get("catalog")
        rows.append({"name": name, "label": cfg.get("label") or name, "app": cfg.get("app"),
                     "base": cfg.get("base"), "catalog": cat,
                     "catalogExists": bool(cat) and os.path.isfile(os.path.join(root, str(cat).replace("/", os.sep))),
                     "twin": cfg.get("twin"),
                     "twinExists": os.path.isfile(os.path.join(root, str(cfg.get("twin") or "").replace("/", os.sep))),
                     "manualGroups": len(cfg.get("manualGroups") or []),
                     "manualPorts": sum(len(g.get("ports") or []) for g in (cfg.get("manualGroups") or []) if isinstance(g, dict)),
                     "fromRegistry": cfg.get("registryRow", False)})
    return {"adapters": [r["name"] for r in rows], "rows": rows, "registry": REGISTRY_REL, "error": err}


# ---------------------------------------------------------------- paths

PARAM_RE = re.compile(r"(?<=/)(?::[A-Za-z_]\w*|\{[^/{}]+\})")
# a quoted string that looks like an API path: "/contacts", "/transcripts/{tid}/markdown", f"{BASE}/tasks"
QUOTED_RE = re.compile(r"""(?:f?)["']((?:\{BASE\}|\{base\})?/[A-Za-z][^"'\s]*)["']""")
URL_RE = re.compile(r"https?://[^\s\"'`)\]]+")


def norm_path(p, prefix="/api/v1"):
    """A path as the catalog spells it: absolute, prefixed, every parameter segment `:id`.

    /contacts -> /api/v1/contacts ; /api/v1/transcripts/{tid} -> /api/v1/transcripts/:id ;
    https://app.prospectforge.us/api/v1/tasks?x=1 -> /api/v1/tasks
    """
    s = str(p or "").strip()
    s = s.split("?")[0].split("#")[0]
    s = s.replace("{BASE}", "").replace("{base}", "")
    if s.startswith("http"):
        i = s.find(prefix)
        s = s[i:] if i >= 0 else ""
    if not s:
        return ""
    if not s.startswith(prefix):
        s = prefix + ("" if s.startswith("/") else "/") + s
    # a placeholder is prose, not a path: `/api/v1/...` in a doc means "and the rest", and reading it
    # as a route put a drift row on the first page that described the drift rows
    if ".." in s or "<" in s or "*" in s:
        return ""
    s = PARAM_RE.sub(":id", s)
    # a brace still standing after the parameter pass is a half-read f-string, not a route:
    # `f"{BASE}/candidates/{c['id']}/download"` is cut at the inner quote and arrives as
    # `/candidates/{c[`, which drew a red port for a path no app was ever asked for
    if "{" in s or "}" in s:
        return ""
    if len(s) > len(prefix) + 1:
        s = s.rstrip("/")
    # a path at the end of an English sentence keeps the sentence's full stop, and the catalog has
    # no route ending in one: without this, prose naming a real route became a red drift row
    s = s.rstrip(".,;:!?")
    return s


def resource_of(path, prefix="/api/v1"):
    """The group a port belongs to: the first segment after the prefix, or `(root)`."""
    tail = str(path or "")[len(prefix):].strip("/")
    return tail.split("/")[0] if tail else "(root)"


# ---------------------------------------------------------------- the inventory

_catalog_cache = {}


def read_catalog(root, cfg):
    """The catalog file, cached by its mtime — the one thing on this page the app writes itself.

    `catalog: null` in the registry is not an error: it is a boundary that does not describe
    itself, and its ports come from `manualGroups` alone. An empty catalog comes back instead,
    so every reader below stays one code path.
    """
    rel = cfg.get("catalog")
    if not rel:
        return {"endpoints": [], "callableByYou": [], "_fetchedAt": "", "_noCatalog": True}, None
    ap = os.path.join(root, rel.replace("/", os.sep))
    if not os.path.isfile(ap):
        return None, "catalog missing: %s" % rel
    key = os.path.getmtime(ap)
    hit = _catalog_cache.get(rel)
    if hit and hit[0] == key:
        return hit[1], None
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception as e:
        return None, "catalog unreadable (%s: %s)" % (type(e).__name__, e)
    _catalog_cache[rel] = (key, d)
    return d, None


def catalog_ports(cat, cfg):
    """The catalog's endpoints as ports, deduped on (method, path), plus the synthetic root.

    The root (`GET /api/v1`) is not in `endpoints` because it IS the endpoints: it is the
    call pull.py makes to write the catalog, so it belongs on the picture like any other.
    A path listed twice under two auth kinds (projects is) keeps the weaker requirement,
    because `callableByYou` decides the drawn state anyway.
    """
    prefix = cfg["prefix"]
    if cat.get("_noCatalog"):
        return []                  # nothing describes itself here; manual_ports() is the whole inventory
    callable_set = set()
    for c in cat.get("callableByYou") or []:
        if isinstance(c, str):
            bits = c.split(None, 1)
            if len(bits) == 2:
                callable_set.add("%s %s" % (bits[0].upper(), norm_path(bits[1], prefix)))
        elif isinstance(c, dict) and c.get("method") and c.get("path"):
            callable_set.add("%s %s" % (c["method"].upper(), norm_path(c["path"], prefix)))
    rows, seen = [], {}
    eps = list(cat.get("endpoints") or [])
    eps.insert(0, {"method": "GET", "path": prefix, "auth": "personal-token", "scopes": [],
                   "purpose": "The app describing itself: every route, who may call it, and which "
                              "of them this token can. What pull.py writes the catalog mirror from."})
    # the root is callable by the personal token by proof, not by listing: the catalog in hand was
    # fetched with it (callerTokenKind says which), and the catalog never lists itself
    if str(cat.get("callerTokenKind") or "") == "personal-token":
        callable_set.add("GET " + prefix)
    for e in eps:
        m = str(e.get("method") or "GET").upper()
        p = norm_path(e.get("path"), prefix)
        if not p:
            continue
        key = "%s %s" % (m, p)
        if key in seen:
            row = seen[key]
            if e.get("auth") == "personal-token":
                row["auth"] = "personal-token"
            if e.get("purpose") and not row.get("purpose"):
                row["purpose"] = e["purpose"]
            continue
        row = {"method": m, "path": p, "key": key, "resource": resource_of(p, prefix),
               "auth": e.get("auth") or "", "scopes": list(e.get("scopes") or []),
               "purpose": (e.get("purpose") or "").strip(),
               "callable": key in callable_set, "source": "catalog"}
        seen[key] = row
        rows.append(row)
    return rows


# ---------------------------------------------------------------- hand-written ports (Q-0024)

def manual_ports(cfg):
    """The registry's `manualGroups` as ports, marked `source: "manual"`.

    The owner asked on 2026-09-18 that port groups can also be added by hand. A manual port is a
    claim a person made, not the app's own word, so it is marked and the sheet draws it dotted.
    Its path is kept EXACTLY as written — query strings included, which is how the onboarding
    pull distinguishes its three calls to `/candidates` — so it is never normalised away.
    """
    prefix = cfg["prefix"]
    rows = []
    for g in (cfg.get("manualGroups") or []):
        if not isinstance(g, dict):
            continue
        res = str(g.get("resource") or "").strip() or "(manual)"
        for e in (g.get("ports") or []):
            if not isinstance(e, dict):
                continue
            m = str(e.get("method") or "GET").upper()
            raw = str(e.get("path") or "").strip()
            if not raw:
                continue
            p = raw if raw.startswith(prefix) else prefix + ("" if raw.startswith("/") else "/") + raw
            callers = []
            for c in (e.get("callers") or []):
                if isinstance(c, str):
                    callers.append({"skill": c, "file": None, "line": None})
                elif isinstance(c, dict) and c.get("skill"):
                    callers.append({"skill": c["skill"], "file": c.get("file"), "line": c.get("line")})
            rows.append({"method": m, "path": p, "key": "%s %s" % (m, p), "resource": res,
                         "auth": e.get("auth") or "personal-token", "scopes": list(e.get("scopes") or []),
                         "purpose": (e.get("purpose") or "").strip(),
                         "callable": e.get("auth") != "admin-key", "source": "manual",
                         "manualCallers": callers})
    return rows


TIER_ORDER = {"personal": 0, "admin": 1, "hollow": 2}


def tier_of(port):
    """The three words the sheet orders a group by and the in-a-cell form counts as arcs.

    Nothing calls it -> hollow, whatever the token could do. Otherwise the token decides:
    personal when the `pf_tok_` the brain holds may call it, admin when only the key may.
    """
    if not port.get("callers"):
        return "hollow"
    return "personal" if port.get("callable") else "admin"


# ---------------------------------------------------------------- who calls what

def _skip_dir(name):
    return name in (".git", "__pycache__", ".cache", "node_modules", ".venv", "venv") or name.startswith(".")


# the generator and its test name paths in order to describe them; counting them as callers would
# draw a cable from the picture to itself
SCAN_NEVER = ("skills/brain-viewer/adapter.py", "skills/brain-viewer/adapter.test.py")


def scan_files(root, cfg):
    out = []
    for top in cfg.get("scan") or ("skills",):
        base = os.path.join(root, top.replace("/", os.sep))
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
            for fn in filenames:
                if not fn.lower().endswith(SCAN_EXT):
                    continue
                ap = os.path.join(dirpath, fn)
                if os.path.relpath(ap, root).replace(os.sep, "/") in SCAN_NEVER:
                    continue
                out.append(ap)
    return sorted(out)


METHOD_HINTS = (("DELETE", r"\bdelete\b|_delete\b"), ("PATCH", r"\bpatch\b|_patch\b"),
                ("PUT", r"\bput\b|_put\b"), ("POST", r"\bpost\b|_post\b"), ("GET", r"\bget\b|_get\b"))
# a line that is making a call rather than listing a prefix. rounds-check.py's domain table is
# a tuple of prefixes in a file that also defines BASE; without this, ("/mentee", "/checkin")
# read as two calls to two routes that do not exist, and the picture grew four false drift rows.
CALL_LINE_RE = re.compile(r"BASE|_get\(|_post\(|_patch\(|_put\(|_delete\(|http_json|urlopen|"
                          r"Request\(|requests\.|fetch\(|curl|\bGET\b|\bPOST\b|\bPATCH\b|\bPUT\b|\bDELETE\b")
# The bare prefix is named by every file that defines a base URL or strips one, which is not a
# call to the catalog route. Only these shapes are: `_get(BASE)`, `http_json(BASE + "/")`,
# and a doc writing `GET /api/v1` with nothing after it.
ROOT_CALL_RE = re.compile(r"(?:_get|_post|http_json|urlopen|fetch)\s*\(\s*\w*BASE\s*[,)+]"
                          r"|\bGET\s+(?:https?://\S+?)?/api/v\d\b(?![/\w])")


def _method_hint(line):
    low = line.lower()
    for m, pat in METHOD_HINTS:
        if re.search(pat, low):
            return m
    return None


def _in_foreign_url(line, at, host):
    """True when the match sits inside a URL pointing somewhere else — another service's
    versioned API reads exactly like this one's (the tools scout calls one)."""
    for u in URL_RE.finditer(line):
        if u.start() <= at < u.end():
            return host not in u.group(0)
    return False


def resolve_callers(root, cfg):
    """Every place in the brain that names one of this adapter's paths.

    Two shapes, because a grep for `/api/v1/` finds only one of them:
      1. the literal path, anywhere (`GET /api/v1/contacts` in a skill doc, a URL in a script)
      2. a path RELATIVE to a `BASE` that ends in the adapter's prefix — how both Ferryman
         scripts are written (`_post("/transcripts/import", …)`, `f"{BASE}/transcripts/tags"`),
         which is why the 2026-08 greps reported those routes as called by nobody.
    The variable must be named exactly BASE: serve.py's APP_BASE and probe.py's DEFAULT_BASE
    are not it, and treating them as it would make every quoted path in a 5,800-line web
    server a call to the PF App.
    -> {normalised path: [{skill, file, line, method, text}]}
    """
    prefix, host = cfg["prefix"], cfg.get("host") or ""
    base_re = re.compile(r"^\s*BASE\s*=\s*[\"'][^\"']*%s/?[\"']" % re.escape(prefix), re.M)
    literal_re = re.compile(re.escape(prefix) + r"(?:/[A-Za-z0-9_\-.:{}]+)*")
    hits = {}
    for ap in scan_files(root, cfg):
        rel = os.path.relpath(ap, root).replace(os.sep, "/")
        try:
            with open(ap, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        if prefix not in text and "BASE" not in text:
            continue
        base_file = bool(base_re.search(text))
        skill = rel.split("/")[1] if rel.startswith("skills/") and "/" in rel[7:] else rel.split("/")[0]
        for n, line in enumerate(text.splitlines(), 1):
            if "adapter:ignore" in line:
                continue
            found = []          # (path string, weak) — weak = a bare literal on a line that is not calling
            for m in literal_re.finditer(line):
                if _in_foreign_url(line, m.start(), host):
                    continue
                found.append((m.group(0), False))
            if base_file:
                is_call = bool(CALL_LINE_RE.search(line))
                for m in QUOTED_RE.finditer(line):
                    s = m.group(1)
                    if s.startswith(prefix) or s.startswith("{"):
                        found.append((s, False))
                    elif re.match(r"^/[a-z][a-z0-9\-]*(?:/[\w\-.:{}]+)*$", s):
                        found.append((s, not is_call))
            for raw, weak in found:
                p = norm_path(raw, prefix)
                if not p:
                    continue
                if p == prefix and not ROOT_CALL_RE.search(line):
                    continue      # a base URL being defined or a prefix being stripped, not a call
                hits.setdefault(p, []).append({"skill": skill, "file": rel, "line": n,
                                               "method": _method_hint(line), "weak": weak,
                                               "text": line.strip()[:160]})
    return hits


# ---------------------------------------------------------------- the log: when it last ran

LOG_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})\]\s+\[([^\]]+)\]\s+(\S+)\s+(.*)$")


def log_files(root, days=LOG_DAYS):
    """The live log plus the rotated months the `days` window reaches into. The log rotates monthly
    into archive/ledgers/YYYY-MM/log-YYYY-MM.md (2026-09-18, structure-pass Batch 2), so a 14-day
    window crossing a month boundary has to read two files or lastRan goes blank on the 1st."""
    out = []
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()[:7]
    base = os.path.join(root, "archive", "ledgers")
    if os.path.isdir(base):
        try:
            names = sorted(os.listdir(base))
        except OSError:
            names = []
        for name in names:
            if re.fullmatch(r"\d{4}-\d{2}", name) and name >= since:
                path = os.path.join(base, name, "log-%s.md" % name)
                if os.path.isfile(path):
                    out.append(path)
    live = os.path.join(root, "context", "log.md")
    if os.path.isfile(live):
        out.append(live)
    return out


def log_rows(root, days=LOG_DAYS):
    files = log_files(root, days)
    if not files:
        return []
    lines = []
    for ap in files:
        try:
            with open(ap, "r", encoding="utf-8", errors="replace") as f:
                lines.extend(f.read().splitlines())
        except OSError:
            continue
    out = []
    for ln in lines:
        m = LOG_RE.match(ln.strip())
        if not m:
            continue
        out.append({"date": m.group(1), "at": "%s %s" % (m.group(1), m.group(2)),
                    "agent": m.group(3).strip(), "action": m.group(4).strip(),
                    "text": m.group(5).strip(), "low": ln.lower()})
    return out


def adapter_log_rows(rows, cfg):
    pat = re.compile(cfg.get("logText") or r"$^", re.I)
    agents = set(cfg.get("logAgents") or ())
    return [r for r in rows if r["agent"] in agents or pat.search(r["low"])]


def last_ran(rows, cfg, resources):
    """The newest line that names each resource. Per RESOURCE, not per route — today's
    Ferryman lines name the snapshot files they refreshed, never the path they called.
    pull.py and push.py now write a `path=` token, so the next build can be per route."""
    out = {}
    for res in resources:
        tokens = [res]
        mir = (cfg.get("mirrors") or {}).get(res)
        if mir:
            tokens.append(mir.rstrip("/").split("/")[-1])
        if res == "transcripts":
            tokens += ["ingested", "import"]
        if res == "(root)":
            tokens = ["api-catalog", "catalog"]
        pat = re.compile("|".join(re.escape(t.lower()) for t in tokens if t))
        hit = None
        for r in rows:
            if pat.search(r["low"]):
                hit = r
        out[res] = {"at": hit["at"], "agent": hit["agent"], "action": hit["action"],
                    "text": hit["text"][:160]} if hit else None
    return out


# ---------------------------------------------------------------- health

def read_probes(root, cfg):
    """Per-route probe results the PF App agent's component rounds recorded, when it has run
    since the recording was added (rounds-check.py writes `probes`). Absent is not failing."""
    rel = cfg.get("probes")
    if not rel:
        return {}, None
    ap = os.path.join(root, rel.replace("/", os.sep))
    if not os.path.isfile(ap):
        return {}, None
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:
        return {}, None
    probes = d.get("probes") or {}
    out = {}
    for k, v in probes.items():
        bits = str(k).split(None, 1)
        if len(bits) != 2 or not isinstance(v, dict):
            continue
        out["%s %s" % (bits[0].upper(), norm_path(bits[1], cfg["prefix"]))] = v
    return out, d.get("_generatedAt")


# A 4xx/5xx only counts as a failure when the line SAYS it was one. "(404 not visible, 403
# visible but not owned)" in a commit note is a route's documented behaviour, and reading every
# three-digit number as an outage marked two healthy ports red on the first run.
STATUS_RE = re.compile(r"(?:HTTP|status|code|returned|failed(?:\s+with)?|error|->|→)\s*[:=]?\s*([45]\d\d)\b", re.I)


def log_health(rows, cfg, ports):
    """A route named in a log line beside a reported 4xx or 5xx is failing until a later line
    names it without one. Evidence, never a guess: the line itself is carried into the card,
    and a clean later mention clears the state rather than asserting health."""
    prefix = cfg["prefix"]
    cutoff = (dt.date.today() - dt.timedelta(days=LOG_DAYS)).isoformat()
    by_path = {}
    for p in ports:
        by_path.setdefault(p["path"], []).append(p)
    out = {}
    for r in rows:
        if r["date"] < cutoff:
            continue
        for m in re.finditer(re.escape(prefix) + r"(?:/[A-Za-z0-9_\-.:{}]+)*", r["text"]):
            path = norm_path(m.group(0), prefix)
            if path not in by_path:
                continue
            bad = STATUS_RE.search(r["text"])
            for p in by_path[path]:
                if bad:
                    out[p["key"]] = {"state": "failing", "code": int(bad.group(1)),
                                     "at": r["at"], "via": "log", "finding": r["text"][:160]}
                else:
                    out.pop(p["key"], None)
    return out


def port_health(port, probes, from_log):
    """One port's health: the probe wins (it is a call actually made), the log fills the rest."""
    pr = probes.get(port["key"])
    if isinstance(pr, dict) and pr.get("code") is not None:
        try:
            code = int(pr["code"])
        except (TypeError, ValueError):
            code = None
        state = "unknown" if code is None else ("ok" if 200 <= code < 400 else "failing")
        return {"state": state, "code": code, "at": pr.get("at"), "via": "probe",
                "finding": pr.get("finding") or pr.get("error")}
    row = from_log.get(port["key"])
    if row:
        return dict(row)
    return {"state": "unknown", "code": None, "at": None, "via": None, "finding": None}


# ---------------------------------------------------------------- the answer

def mirror_of(root, cfg, resource):
    rel = (cfg.get("mirrors") or {}).get(resource)
    if not rel:
        return {"path": None, "exists": False, "mtime": None, "folder": False}
    ap = os.path.join(root, rel.rstrip("/").replace("/", os.sep))
    folder = rel.endswith("/")
    exists = os.path.isdir(ap) if folder else os.path.isfile(ap)
    mtime = None
    if exists:
        if folder:
            newest = 0
            for fn in os.listdir(ap)[:4000]:
                try:
                    newest = max(newest, os.path.getmtime(os.path.join(ap, fn)))
                except OSError:
                    pass
            mtime = dt.datetime.fromtimestamp(newest).isoformat(timespec="seconds") if newest else None
        else:
            mtime = dt.datetime.fromtimestamp(os.path.getmtime(ap)).isoformat(timespec="seconds")
    return {"path": rel, "exists": exists, "mtime": mtime, "folder": folder}


def adapter_api(name, root):
    """GET /api/adapter?name=: the whole generated layer for one adapter. (answer, error)"""
    reg, reg_err = load_registry(root)
    cfg = reg.get(str(name or "").strip().lower())
    if not cfg:
        return None, "no adapter named %r (the registry %s knows: %s)" % (name, REGISTRY_REL, ", ".join(sorted(reg)))
    cat, err = read_catalog(root, cfg)
    if err:
        return None, err
    prefix = cfg["prefix"]
    ports = catalog_ports(cat, cfg)
    manual = manual_ports(cfg)
    ports.extend(manual)
    hits = resolve_callers(root, cfg)
    known = set(p["path"] for p in ports)

    # a caller lands on the port whose method its line implies; with no hint it lands on every
    # port sharing the path, because "contacts is called here" is true of all of them
    for p in ports:
        # a manual port names its callers in the registry, because a hand-written path with a query
        # string is not what the resolver looks for in a script
        p["callers"] = list(p.pop("manualCallers", []) or [])
    by_path = {}
    for p in ports:
        by_path.setdefault(p["path"], []).append(p)
    # a manual port is spelled with its query string, because that is the only thing telling the
    # onboarding pull's three calls to /candidates apart; a caller found in a script has the query
    # stripped. Matching on the bare path puts that caller on every manual port that shares it,
    # rather than drawing the pull's own calls as drift against the ports written for them.
    manual_bare = {}
    for p in ports:
        if p.get("source") == "manual" and "?" in p["path"]:
            manual_bare.setdefault(p["path"].split("?")[0], []).append(p)
    drift = []
    for path, rows in sorted(hits.items()):
        if path not in known and path in manual_bare:
            for r in rows:
                for p in manual_bare[path]:
                    if not any(c.get("file") == r["file"] and c.get("line") == r["line"] for c in p["callers"]):
                        p["callers"].append({"skill": r["skill"], "file": r["file"], "line": r["line"]})
            continue
        if path not in known:
            # a WEAK hit (a bare quoted path on a line that is not making a call) matching nothing
            # is a prefix in a table, not a claim about the app: dropped, never drawn red
            for r in rows:
                if r.get("weak"):
                    continue
                drift.append({"skill": r["skill"], "file": r["file"], "line": r["line"],
                              "path": path, "resource": resource_of(path, prefix), "text": r["text"]})
            continue
        # A weak hit whose path IS a real route stays a caller. pull.py's snapshot table
        # (`"/profile/me": "pf-app-profile-me.json"`) is a dict of paths it then GETs in a
        # loop, and dropping it drew six live routes hollow. The design's stated risk is the
        # missed caller, so a string naming a real route counts and carries its file:line.
        for r in rows:
            targets = [p for p in by_path[path] if r["method"] and p["method"] == r["method"]]
            for p in (targets or by_path[path]):
                if not any(c["file"] == r["file"] and c["line"] == r["line"] for c in p["callers"]):
                    p["callers"].append({"skill": r["skill"], "file": r["file"], "line": r["line"]})

    rows = adapter_log_rows(log_rows(root), cfg)
    resources = []
    for p in ports:
        if p["resource"] not in resources:
            resources.append(p["resource"])
    ran = last_ran(rows, cfg, resources)
    probes, probes_at = read_probes(root, cfg)
    from_log = log_health(rows, cfg, ports)

    groups = []
    for res in resources:
        rp = [p for p in ports if p["resource"] == res]
        mir = mirror_of(root, cfg, res)
        out = []
        for p in rp:
            row = {"method": p["method"], "path": p["path"], "key": p["key"], "auth": p["auth"],
                   "scopes": p["scopes"], "purpose": p["purpose"], "callable": p["callable"],
                   "source": p.get("source") or "catalog",
                   "callers": p["callers"], "lastRan": ran.get(res), "mirror": mir,
                   "health": port_health(p, probes, from_log)}
            row["tier"] = tier_of(row)
            out.append(row)
        # within a group: personal token first, admin key next, the ports nothing calls last. The
        # sheet draws them in this order and the compact in-a-cell form counts the same three arcs.
        out.sort(key=lambda r: TIER_ORDER.get(r["tier"], 3))
        groups.append({"resource": res, "ports": out, "mirror": mir, "lastRan": ran.get(res),
                       "count": len(out),
                       "callable": sum(1 for p in out if p["callable"]),
                       "hollow": sum(1 for p in out if not p["callers"]),
                       "manual": sum(1 for p in out if p["source"] == "manual"),
                       "tiers": {t: sum(1 for p in out if p["tier"] == t) for t in ("personal", "admin", "hollow")},
                       "failing": sum(1 for p in out if p["health"]["state"] == "failing"),
                       "drift": sum(1 for d in drift if d["resource"] == res)})

    no_catalog = bool(cat.get("_noCatalog"))
    fetched = str(cat.get("_fetchedAt") or "")
    stale, age = False, None
    try:
        when = dt.datetime.fromisoformat(fetched.replace("Z", "+00:00"))
        age = round((dt.datetime.now(dt.timezone.utc) - when).total_seconds() / 86400.0, 1)
        stale = age > STALE_DAYS
    except Exception:
        # no catalog is not a stale catalog: there is nothing to have pulled, and a clock on it
        # would read as "somebody forgot" instead of "this system does not describe itself"
        stale = (not fetched) and not no_catalog
    all_ports = [p for g in groups for p in g["ports"]]
    skills = sorted(set(c["skill"] for p in all_ports for c in p["callers"]))
    counts = {"groups": len(groups), "ports": len(all_ports),
              "callable": sum(1 for p in all_ports if p["callable"]),
              "adminKey": sum(1 for p in all_ports if not p["callable"]),
              "hollow": sum(1 for p in all_ports if not p["callers"]),
              "wired": sum(1 for p in all_ports if p["callers"]),
              "manual": sum(1 for p in all_ports if p["source"] == "manual"),
              "tiers": {t: sum(1 for p in all_ports if p["tier"] == t) for t in ("personal", "admin", "hollow")},
              "failing": sum(1 for p in all_ports if p["health"]["state"] == "failing"),
              "drift": len(drift), "callers": len(skills), "mirrors": sum(1 for g in groups if g["mirror"]["exists"])}
    twin_rel = cfg.get("twin") or ""
    return {"name": cfg["name"], "label": cfg["label"], "app": cfg["app"], "appHref": cfg.get("appHref"),
            "base": cfg["base"], "prefix": prefix, "catalog": cfg.get("catalog"), "twin": twin_rel,
            "twinExists": bool(twin_rel) and os.path.isfile(os.path.join(root, twin_rel.replace("/", os.sep))),
            "noCatalog": no_catalog, "registry": REGISTRY_REL, "registryError": reg_err,
            "manualGroups": [str(g.get("resource") or "") for g in (cfg.get("manualGroups") or []) if isinstance(g, dict)],
            "fetchedAt": fetched, "ageDays": age, "stale": stale, "staleDays": STALE_DAYS,
            "refresh": cfg.get("refresh"), "runner": cfg.get("runner"),
            "generatedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "probesAt": probes_at, "probeCount": len(probes), "logDays": LOG_DAYS,
            "lastRanNote": "per resource, not per route: the Ferryman's log lines name the snapshot "
                           "files a pull refreshed, not the path it called. pull.py and push.py now "
                           "write a path= token, so the next build can be per route.",
            "groups": groups, "drift": drift, "skills": skills, "counts": counts}, None


# ---------------------------------------------------------------- the markdown twin

def _age(mtime):
    if not mtime:
        return "—"
    try:
        then = dt.datetime.fromisoformat(mtime)
    except Exception:
        return mtime
    d = (dt.datetime.now() - then).total_seconds() / 86400.0
    return "%s (%.1fd)" % (mtime[:10], d)


def _cell(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ").strip() or "—"


def twin_markdown(a):
    """The same answer as markdown: one table per resource group, then the drift table."""
    c = a["counts"]
    L = []
    L.append("<!-- adapter: %s · catalog _fetchedAt: %s -->" % (a["name"], a["fetchedAt"]))
    L.append("# The %s adapter, port by port" % a["label"])
    L.append("")
    L.append("> **Machine-written, do not edit.** Generated by `skills/brain-viewer/adapter.py` from "
             "`%s` — the %s describing itself. Rewritten on every Ferryman pull and by "
             "`GET /api/adapter?name=%s`. The Forge draws the same JSON as the adapter's ports; "
             "this file is that picture for an agent to grep." % (a["catalog"], a["app"], a["name"]))
    L.append(">")
    # No "written at" stamp on purpose: it would make the file dirty on every pull even when
    # nothing about the app changed, and the file's own mtime already records when it was written.
    L.append("> catalog `_fetchedAt`: %s%s" %
             (a["fetchedAt"] or "(none)",
              "" if a["ageDays"] is None else
              " — the catalog is a snapshot%s" % (", and this one is STALE: run `%s`" % a["refresh"] if a["stale"] else "")))
    L.append(">")
    L.append("> %d ports in %d resource groups · %d callable by the personal token, %d need the admin key · "
             "%d called by no skill (hollow) · %d drift rows · %d groups with a brain-side mirror%s"
             % (c["ports"], c["groups"], c["callable"], c["adminKey"], c["hollow"], c["drift"], c["mirrors"],
                (" · %d hand-written (manual) ports from the registry" % c["manual"]) if c.get("manual") else ""))
    L.append("")
    L.append("**How to read a row.** *who may call it* is the app's own answer for the token that "
             "fetched the catalog (personal `pf_tok_`), not a guess. *callers* is every place under "
             "`skills/` that names the path, literally or through a `BASE` ending in `%s`; an empty "
             "cell means the route exists in the app and nothing in the brain calls it. *last ran* is "
             "%s" % (a["prefix"], a["lastRanNote"]))
    L.append("")
    for g in a["groups"]:
        m = g["mirror"]
        L.append("## %s — %d port%s" % (g["resource"], g["count"], "" if g["count"] == 1 else "s"))
        L.append("")
        L.append("Mirror: %s · last ran: %s" % (
            ("`%s`, %s" % (m["path"], _age(m["mtime"]))) if m["exists"] else
            ("`%s` — missing" % m["path"] if m["path"] else "none (read across the boundary, never kept)"),
            ("%s (%s %s)" % (g["lastRan"]["at"], g["lastRan"]["agent"], g["lastRan"]["action"])) if g["lastRan"] else "nothing in the log"))
        L.append("")
        L.append("| method | path | who may call it | purpose | callers | health |")
        L.append("|---|---|---|---|---|---|")
        for p in g["ports"]:
            cs = p["callers"]
            callers = ", ".join(("`%s:%s`" % (x["file"], x["line"])) if x.get("file") else ("`%s`" % x["skill"])
                                for x in cs[:8]) or "—"
            if len(cs) > 8:
                callers += " +%d more" % (len(cs) - 8)
            h = p["health"]
            hs = "—" if h["state"] == "unknown" else ("%s %s%s" % (h["state"], h["code"] or "", (" " + h["at"]) if h["at"] else "")).strip()
            L.append("| %s | `%s`%s | %s | %s | %s | %s |" % (
                p["method"], p["path"], " *(manual)*" if p.get("source") == "manual" else "",
                "personal token" if p["callable"] else "admin key" + (" (%s)" % ", ".join(p["scopes"]) if p["scopes"] else ""),
                _cell(p["purpose"]), callers, hs))
        L.append("")
    L.append("## Drift — a skill calls a path the catalog does not list")
    L.append("")
    if a["drift"]:
        L.append("| skill | file:line | path |")
        L.append("|---|---|---|")
        for d in a["drift"]:
            L.append("| %s | `%s:%d` | `%s` |" % (d["skill"], d["file"], d["line"], d["path"]))
        L.append("")
        L.append("A drift row is a claim the app does not back: either the catalog is behind the app "
                 "(re-pull, then check `rounds-check.py` C2) or the caller is wrong. The 2026-08-07 "
                 "deliverable that carried six wrong API claims would have been six rows here.")
    else:
        L.append("None. Every path named under `skills/` resolves to a route the catalog lists.")
    L.append("")
    L.append("## Callers, by skill")
    L.append("")
    L.append(", ".join("`%s`" % s for s in a["skills"]) or "none")
    L.append("")
    return "\n".join(L) + "\n"


def write_twin(name, root):
    """Rewrite pf-app-holon/pf-app-adapter-<name>.md from the same JSON the API answers with.
    -> (relative path, counts) or raises. Called by GET /api/adapter and by the Ferryman pull."""
    a, err = adapter_api(name, root)
    if err:
        raise ValueError(err)
    if a.get("noCatalog"):
        # a twin is the catalog's answer rendered as markdown. With no catalog there is nothing to
        # render that the registry file does not already say in full, and writing one would put a
        # machine-written file in a holon with no machine behind it.
        raise ValueError("%s has no catalog (registry %s): its ports are the hand-written groups, "
                         "and no twin is written until the app describes itself" % (a["name"], REGISTRY_REL))
    rel = a["twin"]
    ap = os.path.join(root, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    body = twin_markdown(a)
    old = None
    if os.path.isfile(ap):
        try:
            with open(ap, "r", encoding="utf-8") as f:
                old = f.read()
        except OSError:
            old = None
    if old != body:
        with open(ap, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
    return rel, a["counts"], old != body


def twin_header_date(root, rel):
    """The `_fetchedAt` the twin's header claims, for brain-lint L18. None when absent."""
    ap = os.path.join(root, rel.replace("/", os.sep))
    if not os.path.isfile(ap):
        return None
    try:
        with open(ap, "r", encoding="utf-8-sig") as f:
            head = "".join(f.readline() for _ in range(10))
    except OSError:
        return None
    m = re.search(r"_fetchedAt`?\s*[:=]\s*`?([0-9][0-9T:+\-.Z]*)", head)
    return m.group(1).strip() if m else None


if __name__ == "__main__":
    import sys
    brain = os.environ.get("BRAIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isfile(os.path.join(brain, "CLAUDE.md")):
        brain = os.path.dirname(brain)
    if "--list" in sys.argv:
        print(json.dumps(list_adapters(brain), indent=1, ensure_ascii=False))
        sys.exit(0)
    which = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "ferryman"
    ans, e = adapter_api(which, brain)
    if e:
        print("error: %s" % e)
        sys.exit(1)
    if "--json" in sys.argv:
        print(json.dumps(ans, indent=1, ensure_ascii=False))
    else:
        print("%s: %s" % (ans["label"], ans["counts"]))
        if ans.get("noCatalog"):
            print("no catalog: %d hand-written port(s) from %s; no twin written" % (ans["counts"]["manual"], REGISTRY_REL))
        else:
            rel, counts, changed = write_twin(which, brain)
            print("twin %s (%s)" % (rel, "rewritten" if changed else "unchanged"))
