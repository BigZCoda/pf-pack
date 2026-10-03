#!/usr/bin/env python3
"""split.test.py -- the claims the bedrock / user-layer split (0.48.0) rests on, checked on a scratch brain, no server.

  python skills/brain-viewer/split.test.py

1. A brain with the LEGACY files inside the code folder has them copied into viewer/ on first start: settings, every
   home-layout-<member>.json, every look that is not a core look. Nothing is deleted, nothing in viewer/ overwritten.
2. A brain with nothing gets viewer/ with a default settings file whose owner is not this brain's owner.
3. Widgets: the core folder first, then viewer/widgets/. A user file under a core id is listed as user-<id>, with the
   conflict and no url, so it is never loaded; a user file under its own id is listed with origin user.
4. Looks: a user look is listed from viewer/looks/ with origin user; a user file under a core look's name is refused.
5. Every core widget declares contract: 1, and the page implements BV.contract = 1 and refuses the rest.
6. The team export ships neither skills/brain-viewer/ nor viewer/.
7. A brain with no registry and no content manifest reads as empty, not as an error.
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import serve  # noqa: E402

FAILS = []


def check(ok, what, detail=""):
    print("%s %s%s" % ("ok  " if ok else "FAIL", what, ("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILS.append(what)


def write(root, rel, text):
    ap = os.path.join(root, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with io.open(ap, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def with_brain(root):
    serve.BRAIN = root


def main():
    real = serve.BRAIN
    tmp = tempfile.mkdtemp(prefix="bv-split-")
    try:
        # 1. legacy seeding
        a = os.path.join(tmp, "legacy")
        write(a, "skills/brain-viewer/viewer-settings.json", json.dumps({"owner": "@sam", "forge_root": "canvases"}))
        write(a, "skills/brain-viewer/home-layout-sam.json", json.dumps({"schema": serve.HOME_SCHEMA, "member": "sam", "widgets": []}))
        write(a, "skills/brain-viewer/looks/night.css", ":root { --bg: #111111; }\n")
        write(a, "skills/brain-viewer/looks/paper.css", ":root { --bg: #eeeeee; }\n")
        write(a, "viewer/layouts/kept.json", "{}")
        with_brain(a)
        made = serve.ensure_user_layer(quiet=True)
        ex = lambda rel: os.path.isfile(os.path.join(a, rel.replace("/", os.sep)))
        check(ex("viewer/settings.json") and json.load(io.open(os.path.join(a, "viewer", "settings.json")))["owner"] == "@sam",
              "legacy settings are copied into viewer/settings.json", made)
        check(ex("viewer/layouts/sam.json"), "a legacy home-layout-<member>.json lands in viewer/layouts/<member>.json", made)
        check(ex("viewer/looks/night.css") and not ex("viewer/looks/paper.css"), "a legacy look is copied, a core look name is not", made)
        check(ex("skills/brain-viewer/viewer-settings.json") and ex("skills/brain-viewer/home-layout-sam.json"), "nothing legacy is deleted")
        check(io.open(os.path.join(a, "viewer", "layouts", "kept.json")).read() == "{}", "nothing already in viewer/ is overwritten")
        check(ex("viewer/readme.md") and ex("viewer/widgets/readme.md"), "the user layer gets its two readmes")
        again = serve.ensure_user_layer(quiet=True)
        check(again == [], "a second start creates nothing", again)

        # 2. empty brain
        b = os.path.join(tmp, "empty")
        os.makedirs(b)
        with_brain(b)
        serve.ensure_user_layer(quiet=True)
        s = json.load(io.open(os.path.join(b, "viewer", "settings.json"), encoding="utf-8"))
        check(all(os.path.isdir(os.path.join(b, "viewer", d)) for d in ("layouts", "looks", "widgets")), "an empty brain gets viewer/ and its three folders")
        check(s.get("_schema") == "brain-viewer-settings/1" and "_keys" in s, "an empty brain gets a default settings file with its keys explained")

        # 3. widgets
        write(b, "viewer/widgets/decide.js", 'BV.widgets.register({\n  id: "decide", contract: 1, title: "Mine", mount() {} });\n')
        write(b, "viewer/widgets/mine.js", 'BV.widgets.register({\n  id: "mine", contract: 1, title: "Mine", mount() {} });\n')
        reg = {w["id"]: w for w in serve.widget_registry()}
        check(reg.get("decide", {}).get("origin") == "core", "a core id stays the core widget")
        u = reg.get("user-decide", {})
        check(u.get("conflict") == "id taken by a core widget" and u.get("url") is None and u.get("origin") == "user",
              "a user file under a core id is listed as user-<id> with the conflict and never loaded", u)
        m = reg.get("mine", {})
        check(m.get("origin") == "user" and m.get("url") == "/static/user-widgets/mine.js" and m.get("path") == "viewer/widgets/mine.js"
              and m.get("contract") == 1, "a user widget is listed with origin user, its url and its contract", m)

        # 4. looks
        write(b, "viewer/looks/night.css", "/* Night */\n:root { --bg: #111111; }\n")
        write(b, "viewer/looks/paper.css", ":root { --bg: #eeeeee; }\n")
        looks = serve.look_registry()
        night = next((r for r in looks if r["name"] == "night"), {})
        check(night.get("origin") == "user" and night.get("ok"), "a user look is listed from viewer/looks/ and parses", night)
        clash = next((r for r in looks if r["name"].startswith("paper (")), {})
        check(clash and not clash.get("ok") and "core look" in (clash.get("error") or ""), "a user look under a core name is refused", clash)
        check(serve.look_abs("paper").startswith(os.path.join(HERE, "looks")), "a core look name always resolves to the core file")
        out = serve.look_import({"name": "paper", "css": ":root { --bg: #000; }"})
        check("error" in out, "importing under a core look's name is refused", out)

        # 7. empty declarations
        check(serve.registry().get("holons") == [] and serve.manifest().get("stages") == [],
              "no registry and no content manifest read as empty, not as an error")
    finally:
        serve.BRAIN = real
        shutil.rmtree(tmp, ignore_errors=True)

    # 5. the contract number
    folder = os.path.join(HERE, "widgets")
    missing = [n for n in sorted(os.listdir(folder)) if n.endswith(".js")
               and "contract: 1" not in io.open(os.path.join(folder, n), encoding="utf-8").read(serve.WIDGET_HEAD)]
    check(not missing, "every core widget declares contract: 1 in its register call", missing)
    html = io.open(os.path.join(HERE, "home.html"), encoding="utf-8").read()
    check("BV.contract = 1;" in html and "written for a newer viewer" in html and "id taken by a core widget" in html,
          "home.html sets BV.contract = 1 and refuses a widget with no number, a higher one, or a core id")
    check(serve.WIDGET_CONTRACT == 1, "the server's contract number is the page's")

    # 6. the export
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "team-brain"))
    import importlib
    export = importlib.import_module("export")
    check("skills/brain-viewer" not in export.CODE_DIRS, "the team export no longer ships skills/brain-viewer/")
    check("viewer/" in export.MEMBER_OWNED, "the team export neither writes nor removes viewer/ in the copy")

    print("-" * 72)
    if FAILS:
        print("split.test: %d FAILED -- %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("split.test: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
