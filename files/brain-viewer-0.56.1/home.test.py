#!/usr/bin/env python3
"""home.test.py -- the nine claims the home board rests on, checked without starting a server.

  python skills/brain-viewer/home.test.py

1. THE FOLDER IS THE REGISTRY, so a file's name and the id it registers must be the same word.
   The server lists skills/brain-viewer/widgets/*.js and calls the filename stem the id; the page
   draws whatever the file registered under ITS id. A file that disagrees with its own name is
   listed by the server and never drawn, silently, which is the one failure this design can have.
   Every file registers exactly once, and that id equals its stem.

2. The default board is the eleven named in HOME_ORDER, in order, on (0.39.0): masthead, mantra,
   next, deck, chat, decide, people, horizon, moved, flow, system; everything else in the folder
   comes back off, so edit mode can add it and nothing in the folder is invisible. The plain command
   line came off that board with the chat and waits in the add list, and so does the blank Space.
   The seven the first board carried (calls, alerts, waiting, tasks, talk, recent, pages) are gone
   from the folder, and so is the red strip (wrong), which the lamps replaced. The sundial and the
   constellation are still files, off.

3. The layout validator refuses what would break the page: an id no file in the folder answers to,
   a size that is not one of the column spans, a row height that is not one or two, and settings
   that are not an object. A size saved under 0.36 as S, M or L is not refused, it is turned into
   the span it meant, and a board saved before 0.39.0 with no row height at all gets the one its
   file declares, which is how the deck comes back two rows tall. Beside the widgets the layout
   carries the palette (0.40.0), where the add panel was left: four numbers, x, y, w and h, or
   nothing at all. Anything else is refused rather than written, because a panel restored at a
   place that is not a number is a panel nobody can find.

4. help.json answers for every route the server serves. The question mark on a page reads its own
   route out of that file, so a route with no entry is a button that opens an empty panel.

5. GET /api/system answers with the eight parts of this brain that run on their own, each with a
   state the page has a lamp color for. The eighth is the widgets lamp (T-0217): not a part that runs
   on a rhythm but the board watching its own tiles, red while any tile broke in the last hour.

6. The mantra pool parses, and the day's pick is the same answer every time for a fixed date, which
   is the whole claim the line under the date makes.

7. People wears one of TWO forms, graph and list (0.40.0), and the ring it used to draw is gone from
   the file. The form is a setting saved with the board, so a name the file does not answer to would
   be kept by the server and then drawn as nothing; the page falls back to graph for anything it does
   not know, and this checks the two names the page knows are the two names it declares.

8. THE LOOKS FOLDER IS THE REGISTRY too (T-0208). Every file in looks/ is one :root block of custom
   properties; default.css sets exactly the 33 tokens viewer-tokens.css used to hold, and every other
   look only known names; /api/looks lists them; a widget row may carry a `style` of four keys
   (accent, scale, box, font) and nothing else; the member's look survives a board save and a reset.

9. EVERY WIDGET HOLDS IN THE HARNESS, AND A BREAK IS CAUGHT (T-0217). widgets/harness.py --all mounts
   each file in jsdom against the captured fixtures and must pass for all of them. POST
   /api/widgets/broken refuses an id no file answers to, files ONE finding for a new widget and error
   and lands a repeat of it on that open item, and the widgets lamp goes red while a break is recent.
   The ledger half runs against a stand-in for tasks.py, so the test writes nothing to a real ledger.

Exit 0 when all of them hold; 1 with the failure named otherwise.
"""

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import serve  # noqa: E402

FAILS = []


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(what)


REGISTER_RE = re.compile(r"BV\.widgets\.register\(\s*\{")
ID_RE = re.compile(r'\bid:\s*"([^"]+)"')


def widget_files():
    folder = os.path.join(HERE, serve.WIDGETS_DIR)
    return sorted(n for n in os.listdir(folder) if n.endswith(".js")) if os.path.isdir(folder) else []


def claim_one():
    files = widget_files()
    check(bool(files), "the widgets folder holds widget files", "%d files" % len(files))
    bad = []
    for name in files:
        with io.open(os.path.join(HERE, serve.WIDGETS_DIR, name), encoding="utf-8") as f:
            text = f.read()
        calls = REGISTER_RE.findall(text)
        ids = ID_RE.findall(text)
        stem = name[:-3]
        if len(calls) != 1:
            bad.append("%s registers %d times" % (name, len(calls)))
        elif not ids:
            bad.append("%s registers no id" % name)
        elif ids[0] != stem:
            bad.append("%s registers id %r" % (name, ids[0]))
    check(not bad, "every widget file registers exactly one id equal to its filename", "; ".join(bad[:4]))

    reg = serve.widget_registry()
    check(len(reg) == len(files), "the server's registry lists every file", "%d of %d" % (len(reg), len(files)))
    check(all(w["id"] + ".js" == w["file"] for w in reg), "the server takes the id from the filename")
    nosrc = [w["id"] for w in reg if not w["source"]]
    check(not nosrc, "every widget declares what it reads", ", ".join(nosrc[:4]))
    return reg


def claim_two(reg):
    rows = serve.home_default(reg)
    on = [r["id"] for r in rows if r["on"]]
    check(on == list(serve.HOME_ORDER), "the default board is the eleven, in order", " ".join(on))
    check(len(rows) == len(reg), "every widget in the folder is in the default layout",
          "%d rows for %d files" % (len(rows), len(reg)))
    files_now = {w["id"] for w in reg}
    check({"chat", "people", "space"} <= files_now,
          "the chat, the people ring and the blank space are files in the folder")
    check({"chat", "people"} <= set(on), "the chat and the people ring are on the default board")
    check("command" not in on and "space" not in on,
          "the plain command line and the blank space are off the default board")
    by = {w["id"]: w for w in reg}
    check(by.get("deck", {}).get("rows") == 2, "the deck declares itself two rows tall",
          str(by.get("deck", {}).get("rows")))
    check(all(r["rows"] in serve.HOME_ROWS for r in rows), "every default row height is one or two")
    check([r["rows"] for r in rows if r["id"] == "deck"] == [2], "the deck starts two rows tall")
    off = [r["id"] for r in rows if not r["on"]]
    check(not (set(on) & set(off)), "no widget is both on and off")
    check(all(r["size"] in serve.HOME_SIZES for r in rows), "every default size is one of the column spans")
    check(all(r["collapsed"] is False for r in rows), "nothing starts folded")
    check(all(r["expanded"] is False for r in rows), "nothing starts opened out")
    check(all(r["settings"] == {} for r in rows), "nothing starts with a setting on it")
    gone = sorted({"calls", "alerts", "waiting", "tasks", "talk", "recent", "pages", "wrong"} & {r["id"] for r in rows})
    check(not gone, "the widgets the first board carried, and the red strip, are out of the folder", " ".join(gone))
    files = {w["id"] for w in reg}
    check({"dial", "minimap"} <= files, "the sundial and the constellation are still in the folder")
    off_ids = {r["id"] for r in rows if not r["on"]}
    check({"dial", "minimap", "tally"} <= off_ids, "the sundial, the constellation and the tally start off the board")
    return rows


def claim_three(reg, rows):
    good, err = serve.home_validate(rows, reg)
    check(err is None and good is not None, "the default layout passes its own validator", err or "")

    _, err = serve.home_validate([{"id": "no-such-widget", "on": True, "size": "S"}], reg)
    check(bool(err) and "no-such-widget" in err, "an unknown widget id is refused", err or "it was accepted")

    _, err = serve.home_validate([{"id": reg[0]["id"], "on": True, "size": "XL"}], reg)
    check(bool(err) and "XL" in err, "a size that is not a column span is refused", err or "it was accepted")

    old, err = serve.home_validate([{"id": reg[0]["id"], "on": True, "size": "M"}], reg)
    check(err is None and old and old[0]["size"] == "6", "a size saved as S, M or L becomes its span",
          err or (old[0]["size"] if old else ""))

    # ---- how many rows tall (0.39.0) ----
    tall, err = serve.home_validate([{"id": "deck", "on": True, "size": "4", "rows": 2}], reg)
    check(err is None and tall and tall[0]["rows"] == 2, "a widget may say it stands two rows tall",
          err or str(tall[0]["rows"] if tall else ""))

    for bad in (3, 0, "tall"):
        _, err = serve.home_validate([{"id": "deck", "on": True, "size": "4", "rows": bad}], reg)
        check(bool(err), "a row height that is not one or two is refused (%r)" % (bad,),
              err or "it was accepted")

    pre, err = serve.home_validate([{"id": "deck", "on": True, "size": "4"}], reg)
    check(err is None and pre and pre[0]["rows"] == 2,
          "a board saved before row heights existed gets the one the file declares",
          err or str(pre[0]["rows"] if pre else ""))

    flat, err = serve.home_validate([{"id": "moved", "on": True, "size": "6"}], reg)
    check(err is None and flat and flat[0]["rows"] == 1, "everything else is one row tall",
          err or str(flat[0]["rows"] if flat else ""))

    _, err = serve.home_validate([{"id": reg[0]["id"]}, {"id": reg[0]["id"]}], reg)
    check(bool(err), "the same widget named twice is refused", err or "it was accepted")

    _, err = serve.home_validate({"id": "dial"}, reg)
    check(bool(err), "something that is not a list is refused", err or "it was accepted")

    # a SAVED board naming a widget whose file has since been deleted keeps the rest of the arrangement
    kept, err = serve.home_validate([{"id": "gone-with-its-file", "on": True, "size": "12"},
                                     {"id": "deck", "on": True, "size": "6"}], reg, drop_missing=True)
    on_ids = [r["id"] for r in (kept or []) if r["on"]]
    check(err is None and on_ids == ["deck"], "a saved board survives a widget file being deleted",
          err or " ".join(on_ids))

    # ---- an instrument's own settings (0.38.0) ----
    kept, err = serve.home_validate([{"id": "masthead", "on": True, "size": "12",
                                      "settings": {"view": "project", "project": "pf-build"}}], reg)
    check(err is None and kept and kept[0]["settings"].get("view") == "project",
          "an object of settings is kept as it was given", err or json.dumps(kept[0]["settings"] if kept else {}))

    # the horizon wears one of two forms and the board remembers which (0.39.0)
    for f in ("numerals", "road"):
        kept, err = serve.home_validate([{"id": "horizon", "on": True, "size": "4", "settings": {"form": f}}], reg)
        check(err is None and kept and kept[0]["settings"].get("form") == f,
              "the horizon keeps the form it was set to (%s)" % f, err or "")

    for bad in (["view"], "view", 7):
        _, err = serve.home_validate([{"id": "masthead", "on": True, "size": "12", "settings": bad}], reg)
        check(bool(err), "settings that are not an object are refused (%s)" % type(bad).__name__,
              err or "it was accepted")

    none, err = serve.home_validate([{"id": "masthead", "on": True, "size": "12"}], reg)
    check(err is None and none and none[0]["settings"] == {}, "a row with no settings gets an empty object",
          err or "")

    _, err = serve.home_validate([{"id": "masthead", "on": True, "size": "12",
                                   "settings": {"long": "x" * (serve.HOME_SETTINGS_CHARS + 10)}}], reg)
    check(bool(err), "settings too long to be a preference are refused", err or "it was accepted")

    # ---- where the add panel was left (0.40.0) ----
    good, err = serve.home_palette({"x": 210, "y": 96, "w": 220, "h": 340})
    check(err is None and good == {"x": 210.0, "y": 96.0, "w": 220.0, "h": 340.0},
          "a palette of four numbers is kept as it was given", err or json.dumps(good))

    none, err = serve.home_palette(None)
    check(err is None and none is None, "a board with no palette on it is not a failure", err or "")

    for bad in ({"x": 1, "y": 2, "w": 3}, {"x": "1", "y": 2, "w": 3, "h": 4}, [1, 2, 3, 4], "210,96",
                {"x": 1, "y": 2, "w": float("nan"), "h": 4}, {"x": 1, "y": 2, "w": 0, "h": 4}):
        _, err = serve.home_palette(bad)
        check(bool(err), "a palette that is not four real sizes is refused (%s)" % json.dumps(bad, default=str),
              err or "it was accepted")

    # a layout saved before a file was added still gets that file back, off, so nothing is invisible
    short, err = serve.home_validate([{"id": "dial", "on": True, "size": "8", "collapsed": False}], reg)
    check(err is None and short is not None and len(short) == len(reg),
          "a short layout is filled out with the rest of the folder, off",
          err or ("%d rows" % (len(short) if short else 0)))
    if short:
        check(all(not r["on"] for r in short[1:]), "the widgets it did not name come back off")


def claim_four():
    path = os.path.join(HERE, "help.json")
    check(os.path.isfile(path), "help.json is there", serve.HELP_REL)
    with io.open(path, encoding="utf-8-sig") as f:
        doc = json.load(f)
    pages = doc.get("pages") or {}
    missing = [r for r in sorted(serve.PAGES) if r not in pages]
    check(not missing, "help.json has an entry for every route the server serves", " ".join(missing))
    empty = [r for r, e in sorted(pages.items()) if not str((e or {}).get("what") or "").strip()]
    check(not empty, "every entry says what the page is", " ".join(empty))
    badparts = []
    for route, e in sorted(pages.items()):
        for p in (e or {}).get("parts") or []:
            if not str(p.get("name") or "").strip() or not str(p.get("line") or "").strip():
                badparts.append(route)
    check(not badparts, "every part named has a name and a line", " ".join(sorted(set(badparts))[:4]))
    dashed = [r for r, e in sorted(pages.items()) if "—" in json.dumps(e, ensure_ascii=False)]
    check(not dashed, "no em dashes in the help text", " ".join(dashed[:4]))
    return pages


SYSTEM_IDS = ["calendar", "week", "pfapp", "night", "librarian", "git", "viewer", "widgets"]
LAMP_STATES = {"lit", "dim", "red"}


def claim_five():
    j = serve.system_api()
    ids = [l["id"] for l in j.get("lamps") or []]
    check(ids == SYSTEM_IDS, "the lamps are the eight parts that run on their own, in order", " ".join(ids))
    bad = [l["id"] for l in j.get("lamps") or [] if l.get("state") not in LAMP_STATES]
    check(not bad, "every lamp carries a state the page has a color for", " ".join(bad))
    nocad = [l["id"] for l in j.get("lamps") or [] if l.get("cadence") not in serve.SYSTEM_WINDOW]
    check(not nocad, "every lamp says how often its part is meant to run", " ".join(nocad))
    nodetail = [l["id"] for l in j.get("lamps") or [] if not str(l.get("detail") or "").strip()]
    check(not nodetail, "every lamp says something about its last run", " ".join(nodetail))
    dashed = [l["id"] for l in j.get("lamps") or [] if "—" in json.dumps(l, ensure_ascii=False)]
    check(not dashed, "no em dashes in what a lamp says", " ".join(dashed))


def pick(day, n):
    """The day's line, exactly as widgets/mantra.js picks it: the date's own characters, modulo the pool."""
    if not n:
        return 0
    h = 0
    for ch in day:
        h = (h * 31 + ord(ch)) % (2 ** 32)
    return h % n


def claim_six():
    j = serve.mantras_api()
    check(j.get("exists"), "the mantra pool is there", serve.MANTRAS_REL)
    items = j.get("items") or []
    check(len(items) >= 20, "the pool has lines in it", "%d lines" % len(items))
    noauthor = [i["text"][:40] for i in items if not i.get("author")]
    check(not noauthor, "every line says who said it", "; ".join(noauthor[:3]))
    longest = max((len(i["text"].split()) for i in items), default=0)
    check(longest <= 25, "no line is longer than twenty five words", "%d words" % longest)
    dashed = [i["text"][:40] for i in items if "—" in i["text"]]
    check(not dashed, "no em dashes in the pool", "; ".join(dashed[:3]))
    first = pick("2026-09-21", len(items))
    check(all(pick("2026-09-21", len(items)) == first for _ in range(5)),
          "the day's pick is the same answer every time", "line %d" % (first + 1))
    turns = len({pick(d, len(items)) for d in ("2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24")})
    check(turns > 1, "the pick moves with the date", "%d different lines over four days" % turns)


# ---- claim 7: the two forms People wears (0.40.0) ----
FORMS_RE = re.compile(r"const FORMS = \[(.*?)\];", re.S)
HUBS_RE = re.compile(r"const HUBS = \[(.*?)\];", re.S)
NAME_RE = re.compile(r'\["([a-z]+)"')


def claim_seven():
    with io.open(os.path.join(HERE, serve.WIDGETS_DIR, "people.js"), encoding="utf-8") as f:
        text = f.read()
    m = FORMS_RE.search(text)
    forms = NAME_RE.findall(m.group(1)) if m else []
    check(forms == ["graph", "list"], "People declares the two forms it draws, the graph first",
          " ".join(forms) or "none")
    for name in ("graph", "list"):
        check(name in forms, "the %s form is one People answers to" % name)
    check("ring" not in forms, "the ring is not one of its forms any more", " ".join(forms))
    # not a bare word search: half the file's strings are Strings. A form is a quoted name, so that is what is checked
    check('"ring"' not in text, "no name in the file answers to the ring any more")
    check('api.settings().form) ? api.settings().form : "graph"' in text,
          "a form the file does not answer to falls back to the graph")
    kept, err = serve.home_validate([{"id": "people", "on": True, "size": "4",
                                      "settings": {"form": "graph", "hub": "sun"}}], None)
    check(err is None and kept and kept[0]["settings"].get("form") == "graph",
          "a board keeps the form People was left in", err or "")
    # 2026-09-22: the middle is the sun, full stop. No list of marks, no Saturn, no Venus, and one sun drawn
    h = HUBS_RE.search(text)
    check(h is None and "saturn" not in text.lower() and "venus" not in text.lower() and "function paintHubMark" in text,
          "the middle wears one mark, the sun, and no other", "a HUBS list is still declared" if h else "")
    check("graph-physics.js" in text, "it draws with the one physics, not a second engine")


DEFAULT_TOKENS = [
    "--font-title", "--font-display", "--font-ui", "--font-mono", "--size-ui", "--lh-ui",
    "--bg", "--surface", "--ink", "--ink-soft", "--muted", "--rule", "--rule-soft", "--code",
    "--accent", "--accent-deep", "--selected", "--hover",
    "--done", "--done-tint", "--open", "--open-tint", "--blocked", "--blocked-tint",
    "--mouth", "--mouth-tint", "--mind", "--danger", "--danger-tint",
    "--radius", "--radius-lg", "--shadow", "--frame",
]


def claim_eight(reg):
    """8. THE LOOKS FOLDER IS THE REGISTRY (T-0208). Every file in looks/ is one :root block of custom properties and
    nothing else; default.css sets exactly the 33 tokens that were in viewer-tokens.css; every other look sets only
    known names; /api/looks lists them; viewer-tokens.css no longer sets any; a page is served with the looks in its
    head; a widget row carries a `style` of four keys and the validator refuses anything else; the look is kept in the
    member's layout file across a board save and a reset."""
    import tempfile
    folder = os.path.join(HERE, serve.LOOKS_DIR)
    files = sorted(n for n in os.listdir(folder) if n.endswith(".css")) if os.path.isdir(folder) else []
    check("default.css" in files and len(files) >= 2, "the looks folder holds default.css and at least one other look", " ".join(files))
    parsed = {}
    for name in files:
        with io.open(os.path.join(folder, name), encoding="utf-8") as f:
            tokens, _imports, err = serve.look_parse(f.read())
        check(not err, "%s parses as a :root block of custom properties only" % name, err or "%d tokens" % len(tokens))
        parsed[name[:-4]] = tokens or {}
    d = parsed.get("default", {})
    check(list(d) == DEFAULT_TOKENS, "default.css defines exactly the 33 tokens viewer-tokens.css had, in order",
          "%d tokens" % len(d) if list(d) == DEFAULT_TOKENS else
          "%d: %s" % (len(d), " ".join(sorted(set(d) ^ set(DEFAULT_TOKENS))) or "same names, other order"))
    for name, tokens in parsed.items():
        if name == "default":
            continue
        unknown = [k for k in tokens if k not in DEFAULT_TOKENS]
        check(not unknown, "%s sets only known tokens" % name, " ".join(unknown) or "%d of %d" % (len(tokens), len(DEFAULT_TOKENS)))
    check(len(parsed.get("paper", {})) == len(DEFAULT_TOKENS), "paper.css, the second look, sets all 33")
    with io.open(os.path.join(HERE, "viewer-tokens.css"), encoding="utf-8") as f:
        shared = re.sub(r"/\*.*?\*/", "", f.read(), flags=re.S)
    left = [t for t in DEFAULT_TOKENS if re.search(r"(?<![\w-])%s\s*:" % re.escape(t), shared)]
    check(not left, "viewer-tokens.css sets none of the tokens any more (it only reads them)", " ".join(left))
    api = serve.looks_api()
    names = [l["name"] for l in api["looks"]]
    check(names[:1] == ["default"] and sorted(names) == sorted(parsed), "/api/looks lists every file in the folder, default first", " ".join(names))
    check(all(l["ok"] for l in api["looks"]), "every listed look is usable", "; ".join("%s: %s" % (l["name"], l["error"]) for l in api["looks"] if not l["ok"]))
    check(api["tokens"] == DEFAULT_TOKENS, "/api/looks names the 33 tokens a look may set")
    check(all(l["description"] for l in api["looks"]), "every look says what it is in its leading comment")
    for bad, why in [(":root { color: red; }", "a plain property"), (".x { --bg: #fff; }", "a selector other than :root"),
                     (":root { --bg: url(http://x/y.png); }", "a value that loads something"),
                     ('@import url("https://evil.example/x.css");\n:root { --bg: #fff; }', "an @import that is not Google Fonts"),
                     (":root { --bg: #fff; } :root { --ink: #000; }", "two blocks")]:
        _t, _i, err = serve.look_parse(bad)
        check(bool(err), "a look is refused for %s" % why, err or "accepted")
    res = serve.look_import({"name": "x", "css": ":root { --not-a-token: 1px; }"})
    check(bool(res.get("error")), "an import setting an unknown token is refused", res.get("error") or "accepted")
    res = serve.look_import({"name": "default", "css": ":root { --bg: #fff; }"})
    check(bool(res.get("error")), "an import never replaces default.css", res.get("error") or "accepted")
    html = serve.look_head('<head>\n<link rel="stylesheet" href="/static/viewer-tokens.css">\n</head>')
    check(html.index("/static/looks/default.css") < html.index("/static/viewer-tokens.css") and "window.BV_LOOK" in html,
          "a page is served with looks/default.css in its head ahead of the shared stylesheet, and BV_LOOK set")
    # the per-tile style rides in the layout
    first = reg[0]["id"]
    good = {"accent": "#b24a2c", "scale": "l", "box": "card", "font": "display"}
    rows, err = serve.home_validate([{"id": first, "size": "4", "style": good}], reg)
    check(not err and rows[0].get("style") == good, "the layout accepts a widget entry carrying a style with the four keys", err or "")
    rows, err = serve.home_validate([{"id": first, "size": "4"}], reg)
    check(not err and "style" not in rows[0], "a row with no style is written exactly as before, with no style key")
    for bad in [{"accent": "red"}, {"scale": "xl"}, {"box": "shadow"}, {"font": "comic"}, {"color": "#fff"}, "card"]:
        _r, err = serve.home_validate([{"id": first, "size": "4", "style": bad}], reg)
        check(bool(err), "a style of %s is refused" % json.dumps(bad), err or "accepted")
    # the look is the member's: a board save and a reset both keep it (run against a throwaway brain folder)
    keep = serve.BRAIN
    tmp = tempfile.mkdtemp(prefix="bv-look-test-")
    try:
        serve.BRAIN = tmp
        check(serve.look_active() == "default", "with no layout file the look is default")
        res = serve.look_set_active("paper")
        check(res.get("ok") and serve.look_active() == "paper", "picking a look saves it in the member's layout file", json.dumps(res))
        lay = serve.home_layout_api()
        check(lay.get("look") == "paper" and not lay.get("error") and not lay.get("saved"),
              "a layout file holding only the look reads as the default board, not as a broken one", str(lay.get("error")))
        res = serve.home_layout_write({"widgets": [{"id": first, "size": "4", "style": good}]})
        check(res.get("ok") and serve.look_active() == "paper", "saving the board keeps the look", str(res.get("error")))
        res = serve.home_layout_write({"reset": True})
        check(serve.look_active() == "paper", "resetting the board keeps the look")
        check(bool(serve.look_set_active("no-such-look").get("error")), "a look that is not in the folder is refused")
    finally:
        serve.BRAIN = keep
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def claim_nine(reg):
    import subprocess
    harness = os.path.join(HERE, serve.WIDGETS_DIR, "harness.py")
    p = subprocess.run([sys.executable, harness, "--all"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    out = p.stdout.decode("utf-8", "replace").strip().splitlines()
    last = out[-1] if out else "no output"
    failing = [l for l in out if l.startswith("FAIL")]
    check(p.returncode == 0, "every widget holds in the harness (widgets/harness.py --all)",
          last + ("; " + "; ".join(failing[:3]) if failing else ""))
    code, _out = serve.widget_broken({"id": "../serve", "error": "x"})
    check(code == 400, "a break for an id no widget file answers to is refused", str(code))

    class FakeLedger(object):
        """tasks.py's three calls, held in memory: the test must not file a finding on the real ledger."""
        LedgerError = serve.ledger.LedgerError

        def __init__(self):
            self.items, self.calls = [], []

        def resolve(self, project=None, file=None):
            return "fake-path", "brain-viewer-holon/brain-viewer-tasks.md"

        def open_by_key(self, key, project=None, file=None):
            return [(None, file, "fake-path", it) for it in self.items if it["key"] == key]

        def apply(self, path, rel, action, agent="", **a):
            self.calls.append(action)
            if action == "add":
                self.items.append({"id": "T-9%03d" % len(self.items), "key": a.get("key")})
                return self.items[-1]["id"]
            return a.get("id")

    real, fake = serve.ledger, FakeLedger()
    keep_breaks, keep_quiet = dict(serve.WIDGET_BREAKS), serve.WIDGET_BREAK_QUIET
    serve.ledger = fake
    try:
        serve.WIDGET_BREAKS.clear()
        lamp = serve._widgets_lamp()
        check(lamp["state"] == "lit", "the widgets lamp is lit when nothing has broken", lamp["detail"])
        wid = sorted(w["id"] for w in reg)[0]
        _c, a1 = serve.widget_broken({"id": wid, "error": "TypeError: x is undefined\n    at mount", "where": "mount"})
        serve.WIDGET_BREAK_QUIET = 0          # past the quiet hour, so the second report reaches the ledger
        _c, a2 = serve.widget_broken({"id": wid, "error": "TypeError: x is undefined", "where": "refresh"})
        check(a1.get("result") == "filed" and a2.get("result") == "repeated" and a1.get("item") == a2.get("item")
              and fake.calls == ["add", "repeat"] and len(fake.items) == 1,
              "the same widget and error files one finding, and a repeat lands on that open item",
              "%s then %s, calls %s" % (a1.get("result"), a2.get("result"), fake.calls))
        serve.WIDGET_BREAK_QUIET = 3600
        _c, a3 = serve.widget_broken({"id": wid, "error": "TypeError: x is undefined", "where": "refresh"})
        check(a3.get("result") == "held" and fake.calls == ["add", "repeat"],
              "inside the quiet hour a reload of a broken board writes nothing more", str(a3.get("result")))
        lamp = serve._widgets_lamp()
        check(lamp["state"] == "red" and wid in lamp.get("broken", []),
              "the widgets lamp goes red while a break is recent", lamp["detail"])
        sysl = [l for l in serve.system_api()["lamps"] if l["id"] == "widgets"]
        check(bool(sysl) and sysl[0]["state"] == "red", "GET /api/system carries the red widgets lamp")
    finally:
        serve.ledger = real
        serve.WIDGET_BREAK_QUIET = keep_quiet
        serve.WIDGET_BREAKS.clear()
        serve.WIDGET_BREAKS.update(keep_breaks)


# ---- claim 10: rules on a widget are settings, not code (T-0214) ----
# The declared filters of decide, moved and people are read by running each file under node with a stand-in register,
# the add list's own function is lifted out of home.html and run on a layout carrying a view, and the validator is
# driven against a throwaway brain folder so no real layout is written.
FILTER_WIDGETS = {"decide": ["project", "owner", "due", "tag", "people", "source", "sort"],
                  "moved": ["agent", "days", "project"], "people": ["max", "project"]}
ADD_ENTRIES_RE = re.compile(r"^function addEntries\(.*?^\}$", re.S | re.M)


def node_json(script):
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        return None, "node is not on the PATH"
    p = subprocess.run([node, "-e", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if p.returncode:
        return None, p.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or "node failed"
    return json.loads(p.stdout.decode("utf-8")), None


def claim_ten(reg):
    import shutil
    import tempfile
    folder = os.path.join(HERE, serve.WIDGETS_DIR)
    for wid, keys in FILTER_WIDGETS.items():
        script = ("const vm=require('vm'),fs=require('fs');const out=[];"
                  "const box={BV:{widgets:{register:w=>out.push(w)}},window:{},document:{},console};"
                  "vm.runInNewContext(fs.readFileSync(%s,'utf8'),box);"
                  "process.stdout.write(JSON.stringify(out.map(w=>w.filters||null)))") % json.dumps(os.path.join(folder, wid + ".js"))
        got, err = node_json(script)
        filters = (got or [None])[0] or []
        check(not err and [f.get("key") for f in filters] == keys, "%s declares the filters %s" % (wid, ", ".join(keys)),
              str(err or " ".join(str(f.get("key")) for f in filters)))
        bad = [f.get("key") for f in filters if not (f.get("key") and f.get("label") and f.get("kind") in ("pick", "text", "range"))]
        check(not bad, "every filter %s declares has a key, a label and a kind" % wid, " ".join(map(str, bad)))
        picks = [f.get("key") for f in filters if f.get("kind") == "pick" and not (isinstance(f.get("options"), (list, str, dict)))]
        check(not picks, "every pick %s declares says where its options come from" % wid, " ".join(map(str, picks)))
    decide = {"project": "pf-build", "owner": "*", "due": "week", "tag": "later", "people": "mike-bledsoe",
              "source": "zak", "sort": "project"}
    rows, err = serve.home_validate([{"id": "decide", "size": "4", "settings": decide, "view": "Mike, this week"}], reg)
    check(not err and rows[0]["settings"] == decide, "a settings object carrying every Decide filter validates", err or "")
    check(not err and rows[0].get("view") == "Mike, this week", "a row keeps the name of the view it was placed from")
    rows, err = serve.home_validate([{"id": "decide", "size": "4"}], reg)
    check(not err and "view" not in rows[0], "a row with no view is written exactly as before")
    view = {"id": "decide", "name": "This week's Mike items",
            "settings": {"project": "pf-build", "people": "mike-bledsoe", "due": "week"}}
    for bad, why in [([{"id": "decide", "settings": {}}], "a view with no name"),
                     ([dict(view, id="no-such-widget")], "a view of a widget no file answers to"),
                     ([view, dict(view)], "two views of one name"),
                     ([dict(view, settings=["x"])], "a view whose settings are not an object"),
                     ({"x": 1}, "views that are not a list")]:
        _v, err = serve.home_views(bad, reg)
        check(bool(err), "the layout refuses %s" % why, err or "accepted")
    keep = serve.BRAIN
    tmp = tempfile.mkdtemp(prefix="bv-views-test-")
    try:
        serve.BRAIN = tmp
        res = serve.home_layout_write({"widgets": [{"id": "decide", "size": "4", "settings": view["settings"]}], "views": [view]})
        check(res.get("ok") and serve.home_layout_api().get("views") == [view], "a layout with a view round-trips",
              str(res.get("error") or serve.home_layout_api().get("views")))
        res = serve.home_layout_write({"widgets": [{"id": "decide", "size": "4"}]})
        check(res.get("ok") and serve.home_layout_api().get("views") == [view], "a save that does not name the views keeps them")
        serve.home_layout_write({"reset": True})
        lay = serve.home_layout_api()
        check(lay.get("views") == [view] and not lay.get("error"), "resetting the board keeps the views", str(lay.get("error")))
        serve.home_layout_write({"widgets": [{"id": "decide", "size": "4"}], "views": []})
        check(serve.home_layout_api().get("views") == [], "a save naming no views clears them")
    finally:
        serve.BRAIN = keep
        shutil.rmtree(tmp, ignore_errors=True)
    with io.open(os.path.join(HERE, "home.html"), encoding="utf-8") as f:
        m = ADD_ENTRIES_RE.search(f.read())
    check(bool(m), "home.html builds the add list with one function, addEntries")
    if m:
        script = (m.group(0) + ";const reg=new Map([['decide',{title:'Decide',source:'s'}],['moved',{title:'Moved',source:'s'}]]);"
                  "process.stdout.write(JSON.stringify(addEntries([{id:'decide',on:true},{id:'moved',on:false}],%s,reg)))"
                  % json.dumps([view, {"id": "gone", "name": "x", "settings": {}}]))
        got, err = node_json(script)
        got = got or []
        check(not err and [(e["kind"], e["id"], e["title"], e["sub"]) for e in got]
              == [("widget", "moved", "Moved", ""), ("view", "decide", view["name"], "Decide")],
              "the add list offers a widget off the board and each view as its own entry, titled by its name",
              str(err or got))


def main():
    print("the widgets folder and the registry")
    reg = claim_one()
    print("\nthe default board")
    rows = claim_two(reg)
    print("\nthe layout validator")
    claim_three(reg, rows)
    print("\nthe help entries")
    pages = claim_four()
    print("\nthe lamps")
    claim_five()
    print("\nthe mantra pool")
    claim_six()
    print("\nthe forms People wears")
    claim_seven()
    print("\nthe looks, and a tile's own style")
    claim_eight(reg)
    print("\nthe widget harness, and a break caught")
    claim_nine(reg)
    print("\nrules on a widget are settings, and named views")
    claim_ten(reg)

    print("-" * 72)
    print("%d widgets (%d on by default) - %d help entries for %d routes"
          % (len(reg), sum(1 for r in rows if r["on"]), len(pages), len(serve.PAGES)))
    if FAILS:
        print("home.test: %d FAILED -- %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("home.test: all checks pass")
    return 0


# ---- the Answer deck declares its filters (T-0225) ----
# The deck reads /api/waiting, which takes no parameters, so its filters run in the widget; these checks load the
# file in a sandbox and drive its own ordering function. With no filter set the order is the one it always drew.
DECK_FILTER_KEYS = ["project", "kind", "people", "source", "sort"]


def claim_deck_filters(reg):
    folder = os.path.join(HERE, serve.WIDGETS_DIR)
    waiting = {"groups": [
        {"project": "pf-build", "name": "PF", "questions": [
            {"id": "Q-0001", "kind": "question", "created": "2026-09-01", "people": ["mike-bledsoe"], "source": "call"},
            {"id": "Q-0002", "kind": "question", "created": "2026-09-05", "people": [], "source": None}],
         "tasks": [{"id": "T-0001", "kind": "task", "created": "2026-09-03", "due": "2026-09-20", "people": ["mike-bledsoe"]}]},
        {"project": "brain-viewer", "name": "Viewer", "questions": [
            {"id": "Q-0003", "kind": "question", "created": "2026-09-03", "people": [], "source": "night-agent"}],
         "tasks": [{"id": "T-0002", "kind": "task", "created": "2026-09-09", "due": "2026-09-10", "people": []}]}]}
    cases = [({}, ["Q-0002", "Q-0003", "Q-0001"]),
             ({"kind": "tasks"}, ["T-0002", "T-0001"]),
             ({"kind": "both", "sort": "oldest"}, ["Q-0001", "Q-0003", "T-0001", "Q-0002", "T-0002"]),
             ({"kind": "both", "sort": "due"}, ["T-0002", "T-0001", "Q-0002", "Q-0003", "Q-0001"]),
             ({"project": "pf-build", "kind": "both"}, ["Q-0002", "T-0001", "Q-0001"]),
             ({"people": "mike-bledsoe", "kind": "both"}, ["T-0001", "Q-0001"]),
             ({"source": "night-agent"}, ["Q-0003"])]
    script = ("const vm=require('vm'),fs=require('fs');const out=[];"
              "const box={BV:{widgets:{register:w=>out.push(w)}},window:{},document:{},console};"
              "vm.runInNewContext(fs.readFileSync(%s,'utf8'),box);const w=out[0],W=%s;"
              "process.stdout.write(JSON.stringify({filters:(w.filters||[]).map(f=>[f.key,f.kind,f.default==null?null:f.default]),"
              "plain:w._test.rules({}).plain,orders:%s.map(c=>w._test.questions(W,null,c).map(r=>r.id))}))") % (
        json.dumps(os.path.join(folder, "deck.js")), json.dumps(waiting), json.dumps([c for c, _ in cases]))
    got, err = node_json(script)
    got = got or {}
    check(not err and [f[0] for f in got.get("filters", [])] == DECK_FILTER_KEYS,
          "deck declares the filters %s" % ", ".join(DECK_FILTER_KEYS), str(err or got.get("filters")))
    check(all(f[1] == "pick" for f in got.get("filters", [])), "every deck filter is a pick")
    check(got.get("plain") is True, "the deck with no settings reads as unfiltered")
    rows, err2 = serve.home_validate([{"id": "deck", "size": "4", "settings": {"kind": "both", "sort": "due"}}], reg) if reg else serve.home_validate([{"id": "deck", "size": "4", "settings": {"kind": "both", "sort": "due"}}])
    check(not err2 and rows[0]["settings"] == {"kind": "both", "sort": "due"}, "a settings object carrying deck filters validates", err2 or "")
    for (conf, want), have in zip(cases, got.get("orders") or [[]] * len(cases)):
        check(have == want, "the deck with %s draws %s" % (json.dumps(conf) if conf else "no filters", " ".join(want)), " ".join(have))


_main_before_deck = main


def main():
    print("\nthe Answer deck's filters")
    claim_deck_filters(None)
    return _main_before_deck()


if __name__ == "__main__":
    sys.exit(main())
