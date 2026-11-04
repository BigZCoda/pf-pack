#!/usr/bin/env python3
"""board.py -- step boards from the terminal: draw them, check them, link a file to a step, hand a form to an agent.

  python skills/brain-viewer/board.py list                          every board under the Forge's root
  python skills/brain-viewer/board.py draw [<board>]                redraw one board's drawing (every board when none is named)
  python skills/brain-viewer/board.py check [<board>]               what a board's files say that the drawing cannot use; exit 1 on any
  python skills/brain-viewer/board.py link <step.md> <file> [--video] [--note "what it is for"]
                                                                    add a file under the step's ## Files (## Video with --video), redraw
  python skills/brain-viewer/board.py form <step.md> --json         the step's form as data: questions, types, options, required
  python skills/brain-viewer/board.py form <step.md> --html <out>   the same form as one self-contained web page

<board> is the board file (<slug>-board.md), its drawing (<slug>.canvas) or its folder. The reading, the drawing and the
form parser are part_board.py, the code the viewer itself runs, so the terminal and the Forge never disagree. The contract
is step-boards-contract.md beside this file.
"""

import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("BRAIN_HEADLESS_CHILD", "1")
import serve  # noqa: E402

BRAIN = serve.BRAIN


def rel_of(p):
    ap = os.path.abspath(p if os.path.isabs(p) else os.path.join(BRAIN, p))
    return os.path.relpath(ap, BRAIN).replace(os.sep, "/")


def boards():
    out = []
    root = os.path.join(BRAIN, serve.FORGE_ROOT.replace("/", os.sep))
    for r, dirs, files in os.walk(root):
        for fn in sorted(files):
            if fn.endswith(serve.BOARD_SUFFIX):
                out.append(rel_of(os.path.join(r, fn)))
    return sorted(out)


def board_arg(a):
    rel = rel_of(a)
    if rel.endswith(serve.BOARD_SUFFIX):
        return rel
    if rel.endswith(".canvas"):
        b = serve.board_of(rel)
        if b:
            return b
    ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    if os.path.isdir(ap):
        found = [f for f in os.listdir(ap) if f.endswith(serve.BOARD_SUFFIX)]
        if len(found) == 1:
            return rel.rstrip("/") + "/" + found[0]
    sys.exit("no board file at %s (a board is <slug>-board.md, its <slug>.canvas or its folder)" % a)


def board_for_step(step_rel):
    folder = os.path.join(BRAIN, os.path.dirname(step_rel).replace("/", os.sep))
    found = [f for f in os.listdir(folder) if f.endswith(serve.BOARD_SUFFIX)]
    return (os.path.dirname(step_rel) + "/" + found[0]) if len(found) == 1 else None


def cmd_link(step_rel, target, video, note):
    """Add `- [[<target>]] · <note>` under the step's ## Files (or ## Video), making the section when it is missing."""
    ap = os.path.join(BRAIN, step_rel.replace("/", os.sep))
    t_rel = rel_of(target) if os.path.exists(target) or os.path.exists(os.path.join(BRAIN, target)) else target.replace("\\", "/")
    if not os.path.exists(os.path.join(BRAIN, t_rel.replace("/", os.sep))):
        sys.exit("not found: %s" % target)
    with open(ap, "r", encoding="utf-8") as f:
        text = f.read()
    head = "## Video" if video else "## Files"
    line = "- [[%s]]%s" % (t_rel, (" · " + note.strip()) if note and note.strip() else "")
    if "[[%s]]" % t_rel in text:
        print("already linked: %s" % t_rel)
        return False
    lines = text.split("\n")
    at = next((i for i, l in enumerate(lines) if l.strip().lower() == head.lower()), None)
    if at is None:
        form_at = next((i for i, l in enumerate(lines) if re.match(r"^##\s+Form\b", l)), len(lines))
        block = [head, "", line, ""]
        if form_at > 0 and lines[form_at - 1].strip():
            block.insert(0, "")
        lines[form_at:form_at] = block
    else:
        end = at + 1
        while end < len(lines) and not lines[end].startswith("## "):
            end += 1
        last = end
        while last > at + 1 and not lines[last - 1].strip():
            last -= 1
        if video:   # a slot line (no link) is the place the video was waiting for: the file replaces it
            for i in range(at + 1, end):
                if re.match(r"^\s*[-*+]\s", lines[i]) and "[[" not in lines[i] and "](" not in lines[i]:
                    lines[i] = line
                    break
            else:
                lines.insert(last, line)
        else:
            lines.insert(last, line)
    with open(ap, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    serve.log_line("step board: %s linked to %s%s" % (t_rel, step_rel, " as its video" if video else ""))
    print("linked %s to %s" % (t_rel, step_rel))
    return True


FORM_CSS = """*{box-sizing:border-box}body{margin:0;background:#f7f5f0;color:#222;font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:720px;margin:0 auto;padding:32px 16px 64px}h1{font-size:28px;line-height:1.2;margin:0 0 12px}
.intro p{margin:.5em 0;color:#444}.section{margin:28px 0 6px;font-weight:700;font-size:15px;letter-spacing:.02em}
.q{background:#fff;border:1px solid #ddd8cc;border-radius:10px;padding:16px 18px;margin:12px 0}
.q label.t{display:block;font-weight:600;margin:0 0 6px}.q .req{color:#b4532a}.q .opt{color:#888;font-weight:400;font-size:13px;margin-left:6px}
.q .help{color:#666;font-size:14px;margin:0 0 8px}input[type=text],input[type=email],input[type=tel],input[type=number],input[type=date],input[type=url],textarea{width:100%;padding:9px 11px;border:1px solid #cfc8b8;border-radius:7px;font:inherit;background:#fff}
textarea{min-height:110px}.choices label{display:block;padding:4px 0}.scale{display:flex;gap:8px;flex-wrap:wrap}.scale label{border:1px solid #cfc8b8;border-radius:7px;padding:6px 12px}
button{margin-top:22px;padding:11px 26px;border:0;border-radius:8px;background:#1f3a5f;color:#fff;font:inherit;font-weight:600}.outro{margin-top:18px;color:#444}"""


def inline_md(s):
    s = html.escape(s or "")
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", s)


def form_html(data):
    """A form's data -> one self-contained page: plain HTML inputs, no script, no outside file. The <form> has no action;
    whoever publishes it sets where the answers go."""
    f = data["form"]
    seen_q = False
    out = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
           "<title>%s</title><style>%s</style></head><body><main>" % (html.escape(f["title"]), FORM_CSS),
           "<h1>%s</h1><form method=\"post\">" % html.escape(f["title"])]
    for b in f["blocks"]:
        if b["kind"] == "text":
            cls = "outro" if seen_q else "intro"
            out.append("<div class=\"%s\">%s</div>" % (cls, "".join("<p>%s</p>" % inline_md(p) for p in b["md"].split("\n") if p.strip())))
        elif b["kind"] == "section":
            out.append("<div class=\"section\">%s</div>" % inline_md(b["text"]))
        else:
            seen_q = True
            q, name = b, b["id"]
            req = " required" if q["required"] else ""
            mark = "<span class=\"req\"> *</span>" if q["required"] else "<span class=\"opt\">Optional</span>" if q["required"] is False else ""
            out.append("<div class=\"q\"><label class=\"t\" for=\"%s\">%s%s</label>" % (name, inline_md(q["text"]), mark))
            if q["help"]:
                out.append("<p class=\"help\">%s</p>" % inline_md(q["help"]))
            t = q["type"]
            if t in ("choice", "yesno", "multi"):
                kind = "checkbox" if t == "multi" else "radio"
                out.append("<div class=\"choices\">%s</div>" % "".join(
                    "<label><input type=\"%s\" name=\"%s\" value=\"%s\"%s> %s</label>" % (kind, name, html.escape(o), req if kind == "radio" else "", inline_md(o))
                    for o in q["options"]))
            elif t == "scale":
                out.append("<div class=\"scale\">%s</div>" % "".join(
                    "<label><input type=\"radio\" name=\"%s\" value=\"%d\"%s> %d</label>" % (name, n, req, n) for n in range(q["min"], q["max"] + 1)))
            elif t == "long":
                out.append("<textarea id=\"%s\" name=\"%s\"%s></textarea>" % (name, name, req))
            else:
                it = {"email": "email", "phone": "tel", "number": "number", "date": "date", "url": "url"}.get(t, "text")
                out.append("<input type=\"%s\" id=\"%s\" name=\"%s\"%s>" % (it, name, name, req))
            out.append("</div>")
    out.append("<button type=\"submit\">Send</button></form></main></body></html>")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="step boards: draw, check, link, form")
    ap.add_argument("cmd", choices=["list", "draw", "check", "link", "form"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--video", action="store_true", help="on link: the file is the step's video")
    ap.add_argument("--note", default="", help="on link: what the file is for, one short line")
    ap.add_argument("--json", action="store_true", help="on form: print the form as JSON")
    ap.add_argument("--html", default="", help="on form: write the form as a web page to this path")
    a = ap.parse_args()

    if a.cmd == "list":
        for b in boards():
            d = serve.board_read(b)
            n = len(d["steps"]) if d["kind"] != "funnels" else sum(len(l["steps"]) for l in d["lanes"]) + (1 if d["end"] else 0)
            print("%-70s %-8s %2d steps  %s" % (b, d["kind"], n, d["title"]))
        return 0
    if a.cmd in ("draw", "check"):
        targets = [board_arg(x) for x in a.args] or boards()
        bad = 0
        for b in targets:
            if a.cmd == "draw":
                changed, canvas, d = serve.board_draw(b)
                print("%s %s" % ("REDRAWN  " if changed else "unchanged", canvas))
            else:
                d = serve.board_read(b)
                print("%s: %s" % (b, "clean" if not d["problems"] else "%d to fix" % len(d["problems"])))
            for p in d["problems"]:
                print("    %s" % p)
            bad += len(d["problems"])
        return 1 if (a.cmd == "check" and bad) else 0
    if a.cmd == "link":
        if len(a.args) != 2:
            sys.exit("link takes <step.md> <file>")
        step = rel_of(a.args[0])
        cmd_link(step, a.args[1], a.video, a.note)
        b = board_for_step(step)
        if b:
            changed, canvas, _ = serve.board_draw(b)
            print("%s %s" % ("REDRAWN  " if changed else "unchanged", canvas))
        return 0
    if a.cmd == "form":
        if len(a.args) != 1:
            sys.exit("form takes <step.md>")
        code, data = serve.form_api(rel_of(a.args[0]))
        if code != 200:
            sys.exit(data.get("error", "no form"))
        if a.html:
            with open(a.html, "w", encoding="utf-8", newline="\n") as f:
                f.write(form_html(data))
            print("wrote %s (%d questions)" % (a.html, len(data["form"]["questions"])))
        if a.json or not a.html:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
