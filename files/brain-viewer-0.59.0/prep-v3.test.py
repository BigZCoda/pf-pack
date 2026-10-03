#!/usr/bin/env python3
"""prep-v3.test.py — the People panel's prep skeleton, checked against the live brain (viewer T-0203).

  python skills/brain-viewer/prep-v3.test.py

The skeleton writes the v3 shape defined in skills/call-prep/call-prep-format.md (2026-09-21). Four claims:

1. The subject files route. `pf-calls-mike-bledsoe` finds the Mike subject by its `threads:` line, and a person
   no subject carries finds none — the routing is the subject file's own frontmatter, never a guess from the name.
   The "finds none" half runs in a scratch brain (a synthetic card, a scratch subjects folder holding one subject that
   names someone else), so it never depends on which live subject file names which person (T-0237).
2. The six sections come out in the format's order, with Questions first and Context last, and no v2 section
   ("4. Bring", "Watch for") survives anywhere in the file.
3. The questions are the subject's own open questions, addressed to the person the subject named, at most five
   per subject, with a comment saying how many stayed behind. A question marked `_not this call_` is not on it.
4. A call with no subject file says so in one heading, naming the folder and the format file, instead of
   inventing an agenda. Also in the scratch brain, on the synthetic person.

Nothing is written into deliverables/call-prep/: the writer is called with `dest=` into a temp folder, which
also skips its log line. No existing prep and no subject file is read for anything but its text.

Exit 0 when all four hold; 1 with the failure named otherwise.
"""

import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
BRAIN = os.environ.get("BRAIN_ROOT") or os.path.dirname(os.path.dirname(HERE))

import serve  # noqa: E402

GROUP = "pf-calls-mike-bledsoe"
SUBJECT = "projects/pf-build/subjects/mike-bledsoe-audit-partnership.md"
# The empty-Questions path runs on a synthetic person in a scratch brain (T-0237): the live person this used to name
# (collin-green) was later carried by a real subject file, and the check went stale. Same pattern as call.test.py claim 6.
NO_SUBJECT_SLUG = "zed-nosubject"
OTHER_SLUG = "yara-subjected"             # the one person the scratch subject names, so the folder is not empty


def scratch_brain(tmp):
    """A brain with two cards and one subject file that names only OTHER_SLUG. Returns its root."""
    root = os.path.join(tmp, "brain")
    os.makedirs(os.path.join(root, "people"))
    os.makedirs(os.path.join(root, "projects", "scratch", "subjects"))
    os.makedirs(os.path.join(root, "deliverables", "call-prep"))
    for slug, name in ((NO_SUBJECT_SLUG, "Zed Nosubject"), (OTHER_SLUG, "Yara Subjected")):
        with open(os.path.join(root, "people", slug + ".md"), "w", encoding="utf-8") as f:
            f.write("# %s\n\n## Role & Relationship\nSynthetic, for prep-v3.test.py.\n\n## Flags\n- a flag\n" % name)
    with open(os.path.join(root, "projects", "scratch", "subjects", "yara-matter.md"), "w", encoding="utf-8") as f:
        f.write("---\nsubject: Yara's matter\npeople: [%s]\nthreads: [scratch-thread]\nstatus: open\n---\n"
                "# Yara's matter\n\n## Open questions\n\n- **Yara:** Does this route only to Yara?\n" % OTHER_SLUG)
    return root
ORDER = ["## Questions", "## Points per person", "## Decide before, and the close",
         "## Your notes", "## Since last time", "## Context"]
FAILS = []


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  — " + detail) if detail else ""))
    if not ok:
        FAILS.append(what)


def write(tmp, name, **kw):
    dest = os.path.join(tmp, name)
    rel, existed = serve.make_prep(dest=dest, **kw)
    with open(dest, "r", encoding="utf-8") as f:
        return f.read()


def main():
    tmp = tempfile.mkdtemp(prefix="prep-v3-test-")
    try:
        # --- 1. routing ----------------------------------------------------------------
        subs = serve.subjects_for(GROUP, ["mike-bledsoe", "john-kissell", "dani-plumb"], True)
        check(any(s["rel"] == SUBJECT for s in subs),
              "the Mike subject routes to %s by its threads line" % GROUP,
              ", ".join(s["rel"] for s in subs) or "no subject matched")
        mike = next((s for s in subs if s["rel"] == SUBJECT), None)
        check(bool(mike and mike["questions"]), "the subject's open questions parse",
              "%d question(s)" % len(mike["questions"]) if mike else "subject not found")
        check(bool(mike and mike["answered"]), "its answered lines parse with dates",
              "%d answered, %d dated" % (len(mike["answered"]), sum(1 for a in mike["answered"] if a["date"])) if mike else "")
        check(not any(re.search(r"_not this call", q["text"], re.I) for q in (mike["questions"] if mike else [])),
              "a question marked _not this call_ is not carried")

        # --- 2. the sections, in the format's order -------------------------------------
        text = write(tmp, "group.md", group=GROUP, call_date="2026-09-28", purpose="the tier menu and the trial audit")
        at = [text.find(h) for h in ORDER]
        check(all(i >= 0 for i in at), "all six v3 sections are written",
              ", ".join(h for h, i in zip(ORDER, at) if i < 0) or "")
        check(at == sorted(at), "…and in the format's order", " ".join(str(i) for i in at))
        check("format: v3" in text and re.search(r"^subjects: \[.*mike-bledsoe-audit-partnership.*\]$", text, re.M) is not None,
              "the frontmatter carries format: v3 and the subjects it was built from")
        v2 = [h for h in ("## 4. Bring", "## 5. Watch for", "## 1. Who and why", "## 7. Your notes") if h in text]
        check(not v2, "no v2 section survives", ", ".join(v2))

        # --- 3. the questions ------------------------------------------------------------
        head = "### %s" % mike["name"] if mike else "### (missing)"
        check(head in text, "Questions carries one h3 per subject, named by the subject", head)
        qs = text[text.index("## Questions"):text.index("## Points per person")]
        lines = [l for l in qs.split("\n") if re.match(r"^- \*\*[^*]+:\*\* \S", l)]
        check(1 <= len(lines) <= serve.SUBJECT_QUESTION_CAP,
              "at most five questions, each addressed to a named person", "%d written" % len(lines))
        first = (mike["questions"][0] if mike and mike["questions"] else {"who": "", "text": ""})
        check(any(first["text"][:60] in l and first["who"] in l for l in lines),
              "the first question comes from the subject file, who and all",
              (lines[0][:100] if lines else "no question line"))
        left = len(mike["questions"]) - len(lines) if mike else 0
        check(re.search(r"<!-- \d+ of \d+ open questions in %s" % re.escape(SUBJECT), qs) is not None,
              "a comment says how many of the subject's questions were left behind", "%d left" % left)
        check("#call:" not in qs and not re.search(r"\b[TQ]-\d{4}\b", qs),
              "no ledger ids and no facts in the Questions section (owner, 9/21)")
        for name in ("Mike Bledsoe", "John Kissell", "Dani Plumb"):
            check(("### %s" % name) in text, "Points per person has a heading for %s" % name)

        # --- 1b + 4. a synthetic person no subject carries, in a scratch brain (T-0237) -------
        live = serve.BRAIN
        try:
            serve.BRAIN = scratch_brain(tmp)
            found = serve.subjects_for(OTHER_SLUG, [OTHER_SLUG], False)
            check([s["slug"] for s in found] == ["yara-matter"],
                  "the scratch subject routes to the person it names (the folder is read)",
                  ", ".join(s["rel"] for s in found) or "none")
            none = serve.subjects_for(NO_SUBJECT_SLUG, [NO_SUBJECT_SLUG], False)
            check(not none, "a person no subject file carries finds none",
                  "%s: %s" % (NO_SUBJECT_SLUG, ", ".join(s["rel"] for s in none)))
            solo = write(tmp, "solo.md", slug=NO_SUBJECT_SLUG, call_date="2026-09-28")
            check("### (no subject file yet)" in solo, "a call with no subject says so in one heading", NO_SUBJECT_SLUG)
            check("projects/<project>/subjects/" in solo and "skills/call-prep/call-prep-format.md" in solo,
                  "…and names the folder and the format file")
            at2 = [solo.find(h) for h in ORDER]
            check(all(i >= 0 for i in at2) and at2 == sorted(at2), "the six sections are still there, in order")
        finally:
            serve.BRAIN = live

        # nothing was written where preps live
        stray = [p for p in os.listdir(os.path.join(BRAIN, "deliverables", "call-prep"))
                 if p.endswith("2026-09-28.md")]
        check(not stray, "no prep was written into deliverables/call-prep/", ", ".join(stray))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("-" * 72)
    if FAILS:
        print("prep-v3.test: %d FAILED — %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("prep-v3.test: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
