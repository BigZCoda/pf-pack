#!/usr/bin/env python3
"""adapter.test.py — the adapter generator's three claims, checked against the live brain.

  python skills/brain-viewer/adapter.test.py

1. The BASE-relative pass works. `push.py` never writes the string `/api/v1/transcripts/import`
   anywhere — it writes `_post("/transcripts/import", …)` against a BASE that ends in the
   prefix. A plain grep for the prefix misses it, which is exactly why that port read as
   called by nobody before this pass existed. The resolver must find it, at push.py's real line.
2. Nothing is invented. Every path the resolver returns either matches a catalog route or
   appears as a drift row: no third outcome, so a port drawn hollow is hollow because nothing
   calls it and not because the resolver dropped the caller on the floor.
3. The twin cannot disagree with the catalog. Its header date is the catalog's `_fetchedAt`,
   which is the one thing brain-lint L18 enforces on every rounds.
4. The registry (2026-09-18, viewer Q-0024) answers for both adapters: the file decides which
   exist, a hand-written port group is merged and marked `source: manual` so it can never pass
   for the app's own word, an adapter with no catalog still answers from its manual groups
   alone, and every group comes back in tier order — personal token, admin key, hollow last —
   because that order is what the sheet draws down its rail.

Exit 0 when all four hold; 1 with the failure named otherwise.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
BRAIN = os.environ.get("BRAIN_ROOT") or os.path.dirname(os.path.dirname(HERE))

import adapter  # noqa: E402

FAILS = []


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  — " + detail) if detail else ""))
    if not ok:
        FAILS.append(what)


def main():
    reg, reg_err = adapter.load_registry(BRAIN)
    check(not reg_err, "the adapter registry reads", reg_err or adapter.REGISTRY_REL)
    cfg = reg["ferryman"]

    # --- 1. the BASE-relative pass -------------------------------------------------
    hits = adapter.resolve_callers(BRAIN, cfg)
    want = "/api/v1/transcripts/import"
    rows = hits.get(want) or []
    push = [r for r in rows if r["file"].endswith("skills/ferryman/push.py")]
    check(bool(push), "push.py's /transcripts/import is found through BASE",
          ", ".join("%s:%d" % (r["file"], r["line"]) for r in push) or
          "not found; %d other caller(s) of that path" % len(rows))
    check(any(r["method"] == "POST" for r in push),
          "…and its method reads as POST from the calling line",
          ", ".join(str(r["method"]) for r in push))

    # the second shape: a literal path in a skill doc
    contacts = hits.get("/api/v1/contacts") or []
    check(any(r["file"].endswith(".md") for r in contacts),
          "a literal path in a skill doc is a caller too",
          ", ".join(sorted(set(r["file"] for r in contacts))[:3]))

    # another service's versioned API is not this one's
    scout = [r for p, rs in hits.items() for r in rs if "ai-tools-scout" in r["file"]]
    check(not scout, "a third-party /api/v1 URL is not counted as a call to this app",
          ", ".join("%s:%d" % (r["file"], r["line"]) for r in scout))

    # --- 2. every resolved path lands somewhere -------------------------------------
    a, err = adapter.adapter_api("ferryman", BRAIN)
    if err:
        check(False, "the adapter answers", err)
        return 1
    ports = [p for g in a["groups"] for p in g["ports"]]
    known = set(p["path"] for p in ports)
    drifted = set(d["path"] for d in a["drift"])
    on_a_port = set()
    for p in ports:
        for c in p["callers"]:
            on_a_port.add((c["file"], c["line"]))
    lost = []
    for path, rows in hits.items():
        for r in rows:
            if path in known:
                if (r["file"], r["line"]) not in on_a_port:
                    lost.append("%s:%d %s (matched a route, reached no port)" % (r["file"], r["line"], path))
            elif path in drifted:
                continue
            elif not r.get("weak"):
                lost.append("%s:%d %s (matched nothing and is not drift)" % (r["file"], r["line"], path))
    check(not lost, "every resolved path matches a catalog route or lands in drift",
          "; ".join(lost[:4]))
    check(all(d["path"] not in known for d in a["drift"]),
          "no drift row names a path the catalog does list")

    # --- 3. the twin's header is the catalog's stamp --------------------------------
    rel, counts, changed = adapter.write_twin("ferryman", BRAIN)
    header = adapter.twin_header_date(BRAIN, rel)
    check(header == a["fetchedAt"],
          "the twin's header date equals the catalog's _fetchedAt",
          "twin %r vs catalog %r" % (header, a["fetchedAt"]))
    body_ap = os.path.join(BRAIN, rel.replace("/", os.sep))
    body = open(body_ap, "r", encoding="utf-8").read()
    check("machine-written" in body.lower() and "do not edit" in body.lower(),
          "the twin says machine-written, do not edit")
    check(body.count("\n## ") >= len(a["groups"]),
          "one section per resource group, plus drift",
          "%d headings for %d groups" % (body.count("\n## "), len(a["groups"])))

    # --- 4. the registry, the manual groups and the tier order (Q-0024) ---------------
    listing = adapter.list_adapters(BRAIN)
    check("ferryman" in listing["adapters"] and "onboarding" in listing["adapters"],
          "the registry file names both adapters", ", ".join(listing["adapters"]))
    check(all(r["fromRegistry"] for r in listing["rows"]),
          "every adapter the generator answers for came from the file, not from a dict in the code")

    b, berr = adapter.adapter_api("onboarding", BRAIN)
    if berr:
        check(False, "an adapter with no catalog answers from its manual groups alone", berr)
    else:
        mports = [p for g in b["groups"] for p in g["ports"]]
        check(b["noCatalog"] and len(mports) == b["counts"]["manual"] == 5,
              "an adapter with no catalog answers from its manual groups alone",
              "noCatalog=%s, %d ports, %d manual" % (b["noCatalog"], len(mports), b["counts"]["manual"]))
        check(all(p["source"] == "manual" for p in mports),
              "every hand-written port is marked source: manual, so it never passes for the app's own word")
        check(not b["stale"], "a boundary that does not describe itself is not drawn as a stale one")
        # the query string is the only thing telling three of these five apart
        check(len(set(p["key"] for p in mports)) == 5,
              "a manual path keeps its query string, so /candidates?format=summary is not /candidates?id=",
              ", ".join(p["path"] for p in mports))
        try:
            adapter.write_twin("onboarding", BRAIN)
            check(False, "no twin is written for an adapter with no catalog")
        except ValueError:
            check(True, "no twin is written for an adapter with no catalog")

    order = adapter.TIER_ORDER
    bad = []
    for g in a["groups"]:
        seq = [order.get(p["tier"], 3) for p in g["ports"]]
        if seq != sorted(seq):
            bad.append("%s: %s" % (g["resource"], " ".join(p["tier"] for p in g["ports"])))
    check(not bad, "every group comes back personal token, then admin key, then hollow", "; ".join(bad[:3]))
    check(sum(a["counts"]["tiers"].values()) == a["counts"]["ports"],
          "every port has exactly one tier", str(a["counts"]["tiers"]))

    print("-" * 72)
    print("ports %(ports)d in %(groups)d groups · %(callable)d callable · %(hollow)d hollow · "
          "%(drift)d drift · %(failing)d failing" % a["counts"])
    if FAILS:
        print("adapter.test: %d FAILED — %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("adapter.test: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
