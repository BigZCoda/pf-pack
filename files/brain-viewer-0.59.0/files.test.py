#!/usr/bin/env python3
"""files.test.py -- the claims the Files page (0.52.0, T-0259) rests on, checked against a fixture brain.

  python skills/brain-viewer/files.test.py

1. THE SKIPPED FOLDERS NEVER APPEAR. A file under .git/, node_modules/ or __pycache__, at any depth, is not in the
   listing, and every other file of the fixture is.
2. THE KEY FILES NEVER APPEAR. The five at the root (APIZZLE.txt, PF App API.txt, Onboarding API.txt, pfk_key.txt,
   deepseek_key.txt), the provider keys, and any *_key.txt anywhere are not listed and not served.
3. THE SORT AND THE FILTERS WORK. Newest modified first by default; a column sorts ascending and reverses; size sorts
   largest first; ?folder= keeps a folder and what is under it (and "." the root's own files); ?type= keeps one chip,
   jpeg counting as jpg and an unlisted extension as other; ?q= is a case-insensitive substring of the path. The last
   log line naming a path rides on its row.
4. THE RAW ROUTE STAYS IN THE BRAIN. GET /api/file-raw serves a listed file as a download and answers 403 to a path
   that climbs out, an absolute path, a drive path, a skipped folder or a key file. Run against a live handler on a
   free port, over the fixture brain.

Exit 0 when all of them hold; 1 with the failure named otherwise.
"""

import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import serve  # noqa: E402

FAILS = []


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(what)


FIXTURE = {
    # path: (bytes, mtime offset in seconds back from now)
    "readme.md": (b"# root\n", 50),
    "index.md": (b"# index\n", 4000),
    "people/ann-lee.md": (b"# Ann\n" * 10, 10),
    "people/old/bob.md": (b"# Bob\n", 90000),
    "design/board.PNG": (b"\x89PNG" + b"0" * 500, 300),
    "design/photo.jpeg": (b"\xff\xd8" + b"0" * 2000, 86400 * 10),
    "deliverables/sheet.xlsx": (b"PK" + b"0" * 5000, 600),
    "deliverables/deck.key": (b"x", 700),
    "skills/tool/run.py": (b"print(1)\n", 800),
    "skills/tool/__pycache__/run.cpython-314.pyc": (b"\x00", 5),
    "skills/tool/node_modules/lib/index.js": (b"x", 5),
    "node_modules/top/index.js": (b"x", 5),
    ".git/config": (b"[core]\n", 5),
    ".git/objects/ab/cdef": (b"x", 5),
    "archive/2026/old.md": (b"# old\n", 86400 * 40),
    "APIZZLE.txt": (b"secret", 5),
    "PF App API.txt": (b"secret", 5),
    "Onboarding API.txt": (b"secret", 5),
    "pfk_key.txt": (b"secret", 5),
    "deepseek_key.txt": (b"secret", 5),
    "openai_key.txt": (b"secret", 5),
    "projects/nested/some_key.txt": (b"secret", 5),
    "context/log.md": (b"", 1),
}
LOG = ("[2026-09-01 10:00] [builder] CREATED -- people/ann-lee.md -- first\n"
       "[2026-09-02 11:00] [claude-code] MODIFIED -- people/ann-lee.md -- second, and design/board.PNG too\n"
       "not a log line people/old/bob.md\n")
KEYS = {"APIZZLE.txt", "PF App API.txt", "Onboarding API.txt", "pfk_key.txt", "deepseek_key.txt", "openai_key.txt",
        "projects/nested/some_key.txt"}
SKIPPED = {"skills/tool/__pycache__/run.cpython-314.pyc", "skills/tool/node_modules/lib/index.js",
           "node_modules/top/index.js", ".git/config", ".git/objects/ab/cdef"}


def build(tmp):
    now = time.time()
    for rel, (body, back) in FIXTURE.items():
        ap = os.path.join(tmp, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(ap), exist_ok=True)
        with open(ap, "wb") as f:
            f.write(LOG.encode("utf-8") if rel == "context/log.md" else body)
        os.utime(ap, (now - back, now - back))


def paths(rows):
    return [r["path"] for r in rows]


def get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", path)
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, dict(r.getheaders()), body


def main():
    tmp = tempfile.mkdtemp(prefix="bv-files-test-")
    old = serve.BRAIN
    try:
        build(tmp)
        serve.BRAIN = tmp
        serve._FILES_LOG["key"] = None
        out = serve.files_api()
        listed = set(paths(out["items"]))
        expected = set(FIXTURE) - KEYS - SKIPPED

        # 1. the skipped folders
        check(not (listed & SKIPPED), "no file under .git, node_modules or __pycache__ is listed", str(sorted(listed & SKIPPED)))
        check(not any(p.startswith(".git/") or "/node_modules/" in "/" + p or "__pycache__" in p for p in listed),
              "no listed path passes through a skipped folder at any depth")
        check(listed == expected, "every other fixture file is listed (archive/ included)",
              "missing %s, extra %s" % (sorted(expected - listed), sorted(listed - expected)))

        # 2. the key files
        check(not (listed & KEYS), "no key file is listed", str(sorted(listed & KEYS)))
        check(all(not serve.files_abs(k) for k in KEYS), "files_abs refuses every key file")

        # 3. sort and filters, on the fixture listing
        rows = serve.files_walk()
        default = paths(out["items"])
        mods = [r["modified"] for r in out["items"]]
        check(mods == sorted(mods, reverse=True) and default[0] == "context/log.md", "the default order is newest modified first", default[0])
        by_name = paths(serve.files_sort(rows, "name"))
        check(by_name == sorted(by_name, key=lambda p: (p.rsplit("/", 1)[-1].lower(), p.lower())), "name sorts A to Z")
        check(paths(serve.files_sort(rows, "name", True)) == list(reversed(paths(serve.files_sort(rows, "name")))),
              "a second press reverses the name sort")
        sizes = [r["size"] for r in serve.files_sort(rows, "size")]
        check(sizes == sorted(sizes, reverse=True) and serve.files_sort(rows, "size")[0]["path"] == "deliverables/sheet.xlsx",
              "size sorts largest first")
        oldest = serve.files_api(sort="modified", order="asc")["items"][0]["path"]
        check(oldest == "archive/2026/old.md", "modified ascending puts the oldest first", oldest)
        folders = [r["folder"].lower() for r in serve.files_sort(rows, "folder")]
        check(folders == sorted(folders), "folder sorts A to Z")

        ppl = set(paths(serve.files_filter(rows, folder="people")))
        check(ppl == {"people/ann-lee.md", "people/old/bob.md"}, "?folder=people keeps the folder and what is under it", str(sorted(ppl)))
        check(set(paths(serve.files_filter(rows, folder="peo"))) == set(), "?folder= matches whole folder names, not a prefix of one")
        root = set(paths(serve.files_filter(rows, folder=".")))
        check(root == {"readme.md", "index.md"}, "?folder=. keeps the root's own files only", str(sorted(root)))
        check(set(paths(serve.files_filter(rows, ftype="jpg"))) == {"design/photo.jpeg"}, "?type=jpg counts .jpeg")
        check(set(paths(serve.files_filter(rows, ftype="png"))) == {"design/board.PNG"}, "?type=png is case-blind on the extension")
        check("deliverables/deck.key" in paths(serve.files_filter(rows, ftype="other")), "an unlisted extension is type other")
        check(set(paths(serve.files_filter(rows, ftype="md", q="ANN"))) == {"people/ann-lee.md"}, "?q= is a case-blind path substring, and it combines with ?type=")
        api = serve.files_api(folder="design", ftype="png")
        check(api["count"] == 1 and api["total"] == len(expected), "the API applies the filters and still says the total", "%s of %s" % (api["count"], api["total"]))

        ann = next(r for r in rows if r["path"] == "people/ann-lee.md")
        check(ann["last"] == {"at": "2026-09-02 11:00", "agent": "claude-code", "action": "MODIFIED"}, "the newest log line naming a path rides on its row", str(ann["last"]))
        bob = next(r for r in rows if r["path"] == "people/old/bob.md")
        check(bob["last"] is None, "a line that is not a log line names nothing")
        check(all(set(r) >= {"path", "name", "folder", "extension", "size", "modified", "last"} for r in rows), "every row carries the seven fields")

        # 4. the raw route, against a live handler on the fixture brain
        srv = serve.ThreadingHTTPServer(("127.0.0.1", 0), serve.H)
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            q = lambda p: "/api/file-raw?path=" + urllib.parse.quote(p)
            st, hd, body = get(port, q("deliverables/sheet.xlsx"))
            check(st == 200 and body == FIXTURE["deliverables/sheet.xlsx"][0] and "attachment" in hd.get("Content-Disposition", ""),
                  "a listed file comes back whole, as a download", str(st))
            outside = os.path.join(os.path.dirname(tmp), "bv-files-outside.txt")
            with open(outside, "w") as f:
                f.write("outside")
            try:
                for bad in ("../bv-files-outside.txt", "people/../../bv-files-outside.txt", outside, outside.replace("\\", "/"),
                            "/etc/passwd", "C:/Windows/win.ini", "..\\bv-files-outside.txt"):
                    st, _, body = get(port, q(bad))
                    check(st == 403 and b"outside" not in body, "the raw route refuses %s" % bad, str(st))
            finally:
                os.remove(outside)
            for bad in (".git/config", "node_modules/top/index.js", "APIZZLE.txt", "projects/nested/some_key.txt"):
                st, _, _ = get(port, q(bad))
                check(st == 403, "the raw route refuses %s" % bad, str(st))
            st, _, body = get(port, "/api/files?type=md&q=ann")
            j = json.loads(body)
            check(st == 200 and paths(j["items"]) == ["people/ann-lee.md"], "GET /api/files answers with the filters applied", str(st))
            st, _, body = get(port, "/files")
            check(st == 200 and b"<title>Files</title>" in body, "GET /files returns the page", str(st))
        finally:
            srv.shutdown()
            srv.server_close()
    finally:
        serve.BRAIN = old
        serve._FILES_LOG["key"] = None
        shutil.rmtree(tmp, ignore_errors=True)

    # the help entry and the nav entry
    with open(os.path.join(HERE, "help.json"), encoding="utf-8") as f:
        check("/files" in json.load(f)["pages"], "help.json has an entry for /files")
    with open(os.path.join(HERE, "viewer-common.js"), encoding="utf-8") as f:
        check('key: "files", href: "/files"' in f.read(), "the nav carries files")

    print("\n%s" % ("all hold" if not FAILS else "%d failed: %s" % (len(FAILS), "; ".join(FAILS))))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
