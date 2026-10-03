#!/usr/bin/env python3
"""review.test.py -- the /review rating surface's server side, in a scratch brain (viewer T-0200, T-0189).

  python skills/brain-viewer/review.test.py

Nothing here touches the live brain: BRAIN_ROOT points at a temp folder holding one registry, one ledger and one
log before serve.py (and the ledger tool it imports) is loaded, so every rating, undo and log line lands there.

Claims:
1. The evidence rule (T-0189). A closure card cites only a task closed STRICTLY AFTER the test's day and sharing a
   link narrower than the project's spec file: a same-day close is not evidence, and a shared link to the spec alone
   is not a topical match. A test whose only support is those two is not a card; it is counted as untested.
2. Undo a first rating (T-0200). Rating a closure good checks it off; {undo} inside the minute reopens it, writes an
   `undone` line to the ratings file and a `rating undone` line on the item, and the card is back on the board and
   out of the fold. The counter no longer counts the undone rating.
3. Undo an off. The rewrite task the off filed is closed as withdrawn, and the card is back.
4. Undo a change. A change made from the fold is changed back, not erased: the fold shows the old verdict again.
5. Undo is refused when there is nothing to undo, and when the rating is older than the window.

Exit 0 when all hold; 1 with the failure named otherwise.
"""

import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="review-test-")
os.environ["BRAIN_ROOT"] = TMP
FAILS = []


def check(ok, what, detail=""):
    print(("ok   " if ok else "FAIL ") + what + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILS.append(what)


def day(n):
    return (dt.date.today() - dt.timedelta(days=n)).isoformat()


SPEC = "scratch-holon/scratch-spec.md"


def seed():
    os.makedirs(os.path.join(TMP, "context"))
    os.makedirs(os.path.join(TMP, "scratch-holon"))
    with io.open(os.path.join(TMP, "context", "holon-registry.json"), "w", encoding="utf-8") as f:
        json.dump({"holons": [{"id": "scratch-holon", "name": "Scratch", "path": "scratch-holon/",
                               "spec": SPEC, "tasks": "scratch-holon/scratch-tasks.md"}]}, f)
    with io.open(os.path.join(TMP, "context", "log.md"), "w", encoding="utf-8") as f:
        f.write("# Brain Operations Log\n> Append-only.\n\n")
    with io.open(os.path.join(TMP, SPEC), "w", encoding="utf-8") as f:
        f.write("# Scratch spec\n")
    t0, t1, t2 = day(20), day(12), day(10)
    lines = [
        "# Scratch -- tasks and questions",
        "> A scratch ledger for review.test.py.",
        "",
        "## Inbox",
        # three tests, all 20 days old
        "- [ ] T-0001 %s @zak · Open /alpha and check it draws · #test · → /alpha · → %s" % (t0, SPEC),
        "- [ ] T-0002 %s @zak · Open /beta and check it draws · #test · → /beta · → %s" % (t0, SPEC),
        "- [ ] T-0003 %s @zak · Open /gamma and check it draws · #test · → /gamma · → %s" % (t0, SPEC),
        "- [ ] T-0004 %s @zak · Open /delta and check it draws · #test · → /delta · → %s" % (t0, SPEC),
        # evidence for T-0001: closed later, on its route -> counts
        "- [x] T-0010 %s @claude · Rebuilt /alpha · done:%s · → /alpha · → %s" % (t1, t1, SPEC),
        # for T-0002: closed later but shares only the spec link -> not topical
        "- [x] T-0011 %s @claude · Rebuilt something else · done:%s · → %s" % (t1, t1, SPEC),
        # for T-0002: on its route but closed the SAME DAY the test was written -> not after
        "- [x] T-0012 %s @claude · Built /beta · done:%s · → /beta" % (t0, t0),
        # evidence for T-0003 and T-0004: later, on the route
        "- [x] T-0013 %s @claude · Rebuilt /gamma · done:%s · → /gamma" % (t2, t2),
        "- [x] T-0014 %s @claude · Rebuilt /delta · done:%s · → /delta" % (t2, t2),
        "",
    ]
    with io.open(os.path.join(TMP, "scratch-holon", "scratch-tasks.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    seed()
    sys.path.insert(0, HERE)
    import serve  # noqa: E402  -- loaded only now, so BRAIN (and the ledger tool's BRAIN) is the scratch folder
    assert os.path.normcase(os.path.abspath(serve.BRAIN)) == os.path.normcase(os.path.abspath(TMP)), serve.BRAIN

    # --- 1. the evidence rule --------------------------------------------------------------
    cards, waiting, untested = serve.review_cards()
    by = {c["id"]: c for c in cards}
    check("T-0001" in by and [e["id"] for e in by["T-0001"]["evidence"]] == ["T-0010"],
          "a task closed after the test, on its route, is evidence", by.get("T-0001", {}).get("evidence"))
    check("T-0002" not in by, "a same-day close and a shared spec link are not evidence: no card",
          by.get("T-0002", {}).get("evidence"))
    check(untested == 1, "…and that test is counted as untested", untested)
    ev1 = by.get("T-0001", {}).get("evidence") or [{}]
    check(ev1[0].get("link") == "/alpha", "the evidence cites the narrow link, never the spec", ev1[0].get("link"))

    # --- 2. undo a first rating ------------------------------------------------------------
    rec = serve.review_post("scratch-holon:T-0001", "good", "")
    check(rec and rec["closed"], "rating a closure good checks it off")
    check("scratch-holon:T-0001" in {r["cardId"] for r in serve.review_fold()}, "…and it sits in the fold")
    good_before = serve.review_counter().get("closure", {}).get("good")
    u = serve.review_undo("scratch-holon:T-0001")
    check(u and u["verdict"] == "undone" and u["reopened"], "undo reopens it and writes an undone line", u)
    it = serve.ledger.find(serve.ledger.parse(serve.ledger.read(os.path.join(TMP, "scratch-holon", "scratch-tasks.md"))), "T-0001")
    check(it["mark"] == " " and "rating undone" in (it.get("note") or ""), "the item is open with a rating-undone line", it.get("note"))
    check("scratch-holon:T-0001" in {c["cardId"] for c in serve.review_cards()[0]}, "the card is back on the board")
    check("scratch-holon:T-0001" not in {r["cardId"] for r in serve.review_fold()}, "…and out of the fold")
    check(serve.review_counter().get("closure", {}).get("good", 0) == good_before - 1, "the counter no longer counts it",
          serve.review_counter())
    check(serve.review_undo("scratch-holon:T-0001") is None, "a second undo finds nothing to undo")

    # --- 3. undo an off --------------------------------------------------------------------
    off = serve.review_post("scratch-holon:T-0003", "off", "steps are stale")
    rid = off.get("retestId")
    check(bool(rid) and off.get("retest") == "filed", "an off files a rewrite task", off.get("retest"))
    u = serve.review_undo("scratch-holon:T-0003")
    rt = serve.ledger.find(serve.ledger.parse(serve.ledger.read(os.path.join(TMP, "scratch-holon", "scratch-tasks.md"))), rid)
    check(u and u.get("withdrew") == rid and rt["mark"] == "x" and "withdrawn" in (rt.get("note") or ""),
          "undo closes that rewrite task as withdrawn", rt)
    check("scratch-holon:T-0003" in {c["cardId"] for c in serve.review_cards()[0]}, "the card is back on the board")

    # --- 4. undo a change ------------------------------------------------------------------
    serve.review_post("scratch-holon:T-0004", "wrong", "")
    ch = serve.review_post("scratch-holon:T-0004", "good", "")
    check(ch and ch.get("changedFrom") == "wrong", "a change from the fold is a change")
    u = serve.review_undo("scratch-holon:T-0004")
    row = next((r for r in serve.review_fold() if r["cardId"] == "scratch-holon:T-0004"), {})
    check(u and u.get("undone") == "good" and row.get("verdict") == "wrong", "undo changes it back to what it was", row.get("verdict"))

    # --- 5. refusals -----------------------------------------------------------------------
    check(serve.review_undo("scratch-holon:T-0002") is None, "nothing to undo on a card never rated")
    # age the newest rating past the window by rewriting the scratch ratings file's last line
    d = serve.review_dir()
    leaf = sorted(x for x in os.listdir(d) if x.endswith(".jsonl"))[-1]
    with io.open(os.path.join(d, leaf), encoding="utf-8") as f:
        L = f.read().splitlines()
    last = json.loads(L[-1])
    last["at"] = (dt.datetime.now().astimezone() - dt.timedelta(minutes=5)).isoformat(timespec="seconds")
    L[-1] = json.dumps(last)
    with io.open(os.path.join(d, leaf), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    try:
        serve.review_undo("scratch-holon:T-0004")
        check(False, "an undo older than the window is refused")
    except serve.ledger.LedgerError:
        check(True, "an undo older than the window is refused")

    print("-" * 72)
    print("review.test: " + ("all checks pass" if not FAILS else "%d FAILED: %s" % (len(FAILS), "; ".join(FAILS))))
    return 1 if FAILS else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(code)
