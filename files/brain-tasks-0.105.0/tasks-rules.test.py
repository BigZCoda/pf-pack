#!/usr/bin/env python3
"""tasks-rules.test.py -- the readme is what the tool reads (2026-10-16): an undefined tag, an owner outside the readme's
owner table, and a milestone the ledger does not have (without --new-milestone) are refused; what the tables allow is
written.

Every test builds its own scratch brain in a temp folder: a holon registry naming one ledger, the ledger (one task, one
milestone), one people/ card, a context/log.md. The real tasks.py runs as a subprocess with BRAIN_ROOT pointing at the
scratch brain, and reads the real readme beside it (the tables travel with the code), so no brain file is touched.

    python3 skills/brain-tasks/tasks-rules.test.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PY = os.path.join(HERE, "tasks.py")
README = os.path.join(HERE, "readme.md")
LEDGER_REL = "test-holon/test-holon-tasks.md"

LEDGER = textwrap.dedent("""\
    # Test holon — tasks and questions
    > scratch ledger for tasks-rules.test.py

    ## Inbox
    - [ ] T-0001 2026-10-16 @claude · Something already filed

    ## Milestone — Design
    - [ ] T-0002 2026-10-16 @claude · Something under Design
    """)


def readme_table(name):
    """The first-cell tokens of the readme's `Tag` or `Owner` table, read here independently of tasks.py."""
    with open(README, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    out, cur = [], False
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            cur = False
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cur:
            cur = cells[0].strip("*` ").lower() == name
            continue
        if set(cells[0]) <= set("-: "):
            continue
        out += re.findall(r"`([^`]+)`", cells[0])
    return out


class TheReadmeIsWhatTheToolReads(unittest.TestCase):

    def setUp(self):
        self.brain = tempfile.mkdtemp(prefix="tasks-rules-")
        for d in ("context", "test-holon", "people"):
            os.makedirs(os.path.join(self.brain, d), exist_ok=True)
        self.put("context/holon-registry.json", json.dumps({"holons": [
            {"id": "test-holon", "name": "Test holon", "path": "test-holon/", "tasks": LEDGER_REL}]}))
        self.put("context/log.md", "# Log\n")
        self.put(LEDGER_REL, LEDGER)
        self.put("people/ana-reyes.md", "# Ana Reyes\n")

    def tearDown(self):
        shutil.rmtree(self.brain, ignore_errors=True)

    def put(self, rel, text):
        with open(os.path.join(self.brain, rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def raw(self, rel):
        with open(os.path.join(self.brain, rel), encoding="utf-8") as f:
            return f.read()

    def run_tasks(self, *args):
        return subprocess.run([sys.executable, TASKS_PY] + list(args), cwd=self.brain, capture_output=True, text=True,
                              encoding="utf-8", timeout=120, env=dict(os.environ, BRAIN_ROOT=self.brain))

    def ok(self, *args):
        r = self.run_tasks(*args)
        self.assertEqual(r.returncode, 0, "tasks.py %s failed: %s %s" % (" ".join(args), r.stdout, r.stderr))
        return r.stdout

    def refused(self, needle, *args):
        r = self.run_tasks(*args)
        self.assertNotEqual(r.returncode, 0, "tasks.py %s was accepted: %s" % (" ".join(args), r.stdout))
        self.assertIn(needle, r.stderr, "the refusal did not say %r: %s" % (needle, r.stderr))
        return r.stderr

    # ---- tags

    def test_the_readme_tag_table_is_read_and_every_tag_in_it_is_accepted(self):
        toks = readme_table("tag")
        self.assertIn("future", toks)
        self.assertIn("test-*", toks)
        plain = [t for t in toks if "*" not in t and "<" not in t]
        self.assertGreaterEqual(len(plain), 5, plain)
        for t in plain:
            self.ok("add", "--project", "test-holon", "--owner", "@claude", "--text", "A %s item" % t, "--tag", t)
        self.assertIn("#test-0.31", self.ok("add", "--project", "test-holon", "--owner", "@claude", "--text", "Prefix", "--tag", "test-0.31")
                      and self.raw(LEDGER_REL))

    def test_an_undefined_tag_is_refused_on_add_ask_and_tag(self):
        err = self.refused("not a tag the readme defines", "add", "--project", "test-holon", "--owner", "@claude", "--text", "x", "--tag", "draft")
        self.assertIn("future", err)                         # the refusal names what is allowed
        self.refused("not a tag the readme defines", "ask", "--project", "test-holon", "--to", "@claude", "--text", "Is it? Yes moves it.", "--tag", "draft")
        self.refused("not a tag the readme defines", "tag", "T-0001", "--project", "test-holon", "--tag", "draft")
        self.refused("not a tag the readme defines", "tag", "T-0001", "--project", "test-holon", "--tag", "research")   # retired 2026-10-16
        self.assertNotIn("#draft", self.raw(LEDGER_REL))

    def test_a_retired_tag_can_still_be_taken_off(self):
        self.put(LEDGER_REL, LEDGER.replace("Something already filed", "Something already filed · #research"))
        self.ok("tag", "T-0001", "--project", "test-holon", "--tag", "research", "--remove")
        self.assertNotIn("#research", self.raw(LEDGER_REL))

    def test_source_and_key_go_through_their_own_flags(self):
        self.refused("written with --source", "add", "--project", "test-holon", "--owner", "@claude", "--text", "x", "--tag", "source:lint")
        self.refused("written with --key", "add", "--project", "test-holon", "--owner", "@claude", "--text", "x", "--tag", "key:L12")

    # ---- owners

    def test_the_owner_table_the_owner_setting_a_card_and_a_team_owner_are_accepted(self):
        for o in ("@zak", "@claude", "@me", "@dani", "@ana-reyes"):
            self.ok("add", "--project", "test-holon", "--owner", o, "--text", "For %s" % o)
        self.assertIn("@dani", readme_table("owner"))

    def test_an_owner_outside_the_table_is_refused_on_add_ask_and_reassign(self):
        self.refused("not an owner this brain knows", "add", "--project", "test-holon", "--owner", "@bob", "--text", "x")
        self.refused("not an owner this brain knows", "add", "--project", "test-holon", "--owner", "@ana-reye", "--text", "x")   # no such card
        self.refused("--to @bob", "ask", "--project", "test-holon", "--to", "@bob", "--text", "Is it? Yes moves it.")
        self.refused("--from @bob", "ask", "--project", "test-holon", "--to", "@claude", "--from", "@bob", "--text", "Is it? Yes moves it.")
        self.refused("not an owner this brain knows", "reassign", "T-0001", "--project", "test-holon", "--owner", "@bob")
        self.assertNotIn("@bob", self.raw(LEDGER_REL))
        self.ok("reassign", "T-0001", "--project", "test-holon", "--owner", "@ana-reyes")
        self.assertIn("T-0001 2026-10-16 @ana-reyes", self.raw(LEDGER_REL))

    # ---- milestones

    def test_a_milestone_the_ledger_has_is_accepted_and_one_it_lacks_is_refused_unless_new(self):
        self.ok("add", "--project", "test-holon", "--owner", "@claude", "--text", "Under Design", "--milestone", "Design")
        err = self.refused("no milestone 'Baord'", "add", "--project", "test-holon", "--owner", "@claude", "--text", "x", "--milestone", "Baord")
        self.assertIn("Design", err)                          # the refusal lists the ledger's headings
        self.assertIn("--new-milestone", err)
        self.assertNotIn("## Milestone — Baord", self.raw(LEDGER_REL))
        self.ok("ask", "--project", "test-holon", "--to", "@claude", "--text", "New heading? Yes starts it.", "--milestone", "The board", "--new-milestone")
        self.assertIn("## Milestone — The board", self.raw(LEDGER_REL))
        self.ok("add", "--project", "test-holon", "--owner", "@claude", "--text", "Inbox is always fine", "--milestone", "Inbox")
        self.ok("add", "--project", "test-holon", "--owner", "@claude", "--text", "No milestone is always fine")


if __name__ == "__main__":
    unittest.main(verbosity=2)
