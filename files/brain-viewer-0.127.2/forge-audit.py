#!/usr/bin/env python3
"""The Forge's layers-and-lines check, run on every drawing the Forge lists (T-0434, 2026-11-11).

What it checks is written in brain-viewer-holon/design-directions/forge-layers-and-lines-2026-11-11.md and measured by
forgeAudit() inside skills/brain-viewer/forge.html: no line through a cell, a store or a loose box it does not connect,
no line drawn as its two ends, no word on a part or on another word, no loose box on a cell or its name, no page box
over the fitted drawing, and the same for the words the pointer brings back on every part.

How: Chrome (or Edge) headless opens /forge?path=<drawing>&mode=live&audit=1 at each size, the page writes its answer
into <pre id="forge-audit">, and --dump-dom hands it back. The viewer must be running (127.0.0.1:8765 by default).
Nothing is written anywhere: the page is read-only in live mode and the browser profile is a throwaway folder.

    python skills/brain-viewer/forge-audit.py                 every drawing, desktop and phone
    python skills/brain-viewer/forge-audit.py --path <canvas> one drawing
    python skills/brain-viewer/forge-audit.py --json          the answers as JSON

Exit 0 when every drawing is clean, 1 when any is not, 2 when it could not run.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "maps-manifest.json"
SIZES = {"desktop": (1900, 940), "phone": (390, 844)}
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium", "chromium-browser",
]


def find_browser() -> str | None:
    for b in BROWSERS:
        if os.path.isabs(b) and os.path.exists(b):
            return b
        found = shutil.which(b)
        if found:
            return found
    return None


def drawings() -> list[str]:
    out: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            p = o.get("path")
            if isinstance(p, str) and p.endswith(".canvas") and p not in out:
                out.append(p)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(json.loads(MANIFEST.read_text(encoding="utf-8")))
    return out


def audit(browser: str, base: str, path: str, size: tuple[int, int], profile: str) -> dict:
    url = f"{base}/forge?path={quote(path, safe='/')}&mode=live&audit=1"
    cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
           f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=15000", "--dump-dom", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        return {"path": path, "error": "the browser did not answer in two minutes"}
    # the element the page appends last, after the body (the page's own source names it in a comment too)
    found = re.findall(r'<pre id="forge-audit" hidden[^>]*>(\{.*?\})</pre>', r.stdout, re.S)
    if not found:
        return {"path": path, "error": "the page never wrote its check (did the drawing open?)"}
    try:
        return json.loads(html.unescape(found[-1]))
    except json.JSONDecodeError as e:
        return {"path": path, "error": f"unreadable answer: {e}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--path", help="one drawing, as the manifest names it")
    ap.add_argument("--size", choices=sorted(SIZES), help="one size only")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    browser = find_browser()
    if not browser:
        print("no Chrome or Edge found; this check needs one", file=sys.stderr)
        return 2
    try:
        urllib.request.urlopen(a.base + "/", timeout=4).read(1)
    except Exception:
        print(f"the viewer is not answering at {a.base}; start it first", file=sys.stderr)
        return 2
    paths = [a.path] if a.path else drawings()
    sizes = {a.size: SIZES[a.size]} if a.size else SIZES
    results = []
    with tempfile.TemporaryDirectory(prefix="forge-audit-") as profile:
        for p in paths:
            for name, size in sizes.items():
                res = audit(browser, a.base, p, size, profile)
                res["size"] = name
                results.append(res)
                if not a.json:
                    faults = [*res.get("lines", []), *res.get("words", []), *res.get("boxes", []), *res.get("page", []), *res.get("hover", [])]
                    if res.get("error"):
                        print(f"ERROR  {name:7} {p}: {res['error']}")
                    elif faults:
                        print(f"FAULT  {name:7} {p}: {len(faults)}")
                        for f in faults[:8]:
                            print(f"         - {f}")
                        if len(faults) > 8:
                            print(f"         - and {len(faults) - 8} more")
                    else:
                        print(f"ok     {name:7} {p} (at {round(res.get('scale', 0) * 100)}%, {res.get('chips', 0)} words lifted onto chips on hover)")
    if a.json:
        print(json.dumps(results, indent=1))
    bad = [r for r in results if r.get("error") or not r.get("ok")]
    if not a.json:
        print(f"\n{len(results) - len(bad)} of {len(results)} clean")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
