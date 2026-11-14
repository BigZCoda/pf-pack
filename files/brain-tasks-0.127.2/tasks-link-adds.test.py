#!/usr/bin/env python3
"""tasks-link-adds.test.py -- `link` and `done --link` ADD to an item's links unless --replace is passed (2026-10-21,
brain-viewer T-0356).

Until 10/21 every `link` call replaced the whole set, so a link set in a second call silently dropped the first (the
team-copy review item lost its Sharing link that way). The check the item names: link twice, both links stay; link
--replace, one stays. Around it: a call that adds nothing writes nothing and logs nothing, `--replace` alone clears,
`link` with nothing to add is refused, on a done item the given link leads (the timeline reads the first link as the
result), `done --link` keeps the links the item had with the result first, and `done --link --replace` keeps only the
result.

Every test builds its own scratch brain in a temp folder (a holon registry naming one ledger, the ledger, a log) and runs
the real tasks.py as a subprocess with BRAIN_ROOT pointing there, so no brain file is touched.

    python skills/brain-tasks/tasks-link-adds.test.py
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
LEDGER_REL = "test-holon/test-holon-tasks.md"

LEDGER = textwrap.dedent("""\
    # Test holon — tasks and questions
    > scratch ledger for tasks-link-adds.test.py

    ## Inbox
    - [ ] T-0001 2026-10-21 @claude · Write the review page for the team copy · → deliverables/source.md
    - [ ] T-0002 2026-10-21 @claude · An item with no links yet
    - [x] T-0003 2026-10-20 @claude · Build the sharing checklist · done:2026-10-20 · → deliverables/built.md
    """)


class LinkAdds(unittest.TestCase):

    def setUp(self):
        self.brain = tempfile.mkdtemp(prefix="tasks-link-adds-")
        for d in ("context", "test-holon", "deliverables"):
            os.makedirs(os.path.join(self.brain, d), exist_ok=True)
        self.put("context/holon-registry.json", json.dumps({"holons": [
            {"id": "test-holon", "name": "Test holon", "path": "test-holon/", "tasks": LEDGER_REL}]}))
        self.put("context/log.md", "# Log\n")
        self.put(LEDGER_REL, LEDGER)
        for f in ("source", "built", "review", "sharing", "result"):
            self.put("deliverables/%s.md" % f, "# %s\n" % f)

    def tearDown(self):
        shutil.rmtree(self.brain, ignore_errors=True)

    def put(self, rel, text):
        with open(os.path.join(self.brain, rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def raw(self, rel=LEDGER_REL):
        with open(os.path.join(self.brain, rel), encoding="utf-8") as f:
            return f.read()

    def links(self, iid):
        line = next(l for l in self.raw().splitlines() if (" %s " % iid) in l)
        return re.findall(r" · → ([^·]+?)(?= · |$)", line)

    def run_tasks(self, *args, ok=True):
        r = subprocess.run([sys.executable, TASKS_PY] + list(args), cwd=self.brain, capture_output=True, text=True,
                           timeout=120, env=dict(os.environ, BRAIN_ROOT=self.brain))
        if ok:
            self.assertEqual(r.returncode, 0, "tasks.py %s failed: %s %s" % (" ".join(args), r.stdout, r.stderr))
        return r

    def link(self, iid, *links, replace=False, ok=True):
        args = ["link", iid, "--project", "test-holon"]
        for l in links:
            args += ["--link", l]
        if replace:
            args.append("--replace")
        return self.run_tasks(*args, ok=ok)

    # --- the check the item names ---------------------------------------------------------------------------------

    def test_link_twice_both_links_stay(self):
        self.link("T-0002", "deliverables/review.md")
        self.link("T-0002", "/share")
        self.assertEqual(self.links("T-0002"), ["deliverables/review.md", "/share"])

    def test_link_replace_one_stays(self):
        self.link("T-0002", "deliverables/review.md")
        self.link("T-0002", "/share")
        r = self.link("T-0002", "deliverables/sharing.md", replace=True)
        self.assertEqual(self.links("T-0002"), ["deliverables/sharing.md"])
        self.assertIn("T-0002 link", r.stdout)

    # --- around it ------------------------------------------------------------------------------------------------

    def test_an_open_item_keeps_its_link_first_and_the_new_one_follows(self):
        self.link("T-0001", "deliverables/review.md")
        self.assertEqual(self.links("T-0001"), ["deliverables/source.md", "deliverables/review.md"])
        self.assertIn("T-0001 link added: deliverables/review.md", self.raw("context/log.md"))

    def test_a_link_already_there_writes_nothing_and_logs_nothing(self):
        before, log_before = self.raw(), self.raw("context/log.md")
        r = self.link("T-0001", "deliverables/source.md")
        self.assertEqual(self.raw(), before)
        self.assertEqual(self.raw("context/log.md"), log_before, "a link that added nothing still logged a line")
        self.assertRegex(r.stdout, r"(?m)^T-0001 link$")          # the line item-brief's brief.py matches stays exact
        self.assertIn("T-0001 already carries every link given; nothing written", r.stdout)

    def test_passing_the_whole_list_again_plus_one_is_what_the_old_callers_do(self):
        # serve.py's picture attach and item-brief's brief.py read the item's links and pass them all plus the new one
        self.link("T-0001", "deliverables/source.md", "deliverables/review.md")
        self.assertEqual(self.links("T-0001"), ["deliverables/source.md", "deliverables/review.md"])

    def test_replace_with_no_link_clears(self):
        self.link("T-0001", replace=True)
        self.assertEqual(self.links("T-0001"), [])
        self.assertIn("T-0001 links cleared (was deliverables/source.md)", self.raw("context/log.md"))

    def test_link_with_nothing_to_add_is_refused(self):
        r = self.link("T-0001", ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--replace with no --link clears them", r.stdout + r.stderr)
        self.assertEqual(self.links("T-0001"), ["deliverables/source.md"])

    def test_on_a_done_item_the_given_link_leads(self):
        self.link("T-0003", "/share")
        self.assertEqual(self.links("T-0003"), ["/share", "deliverables/built.md"])

    def test_done_link_keeps_what_the_item_had_with_the_result_first(self):
        self.run_tasks("done", "T-0001", "--project", "test-holon", "--link", "deliverables/result.md")
        self.assertEqual(self.links("T-0001"), ["deliverables/result.md", "deliverables/source.md"])
        self.assertIn("- [x] T-0001", self.raw())

    def test_done_link_replace_keeps_only_the_result(self):
        self.run_tasks("done", "T-0001", "--project", "test-holon", "--link", "deliverables/result.md", "--replace")
        self.assertEqual(self.links("T-0001"), ["deliverables/result.md"])

    def test_done_replace_without_a_link_is_refused(self):
        r = self.run_tasks("done", "T-0001", "--project", "test-holon", "--replace", ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("- [ ] T-0001", self.raw(), "a refused done still closed the item")

    def test_done_without_link_keeps_the_links(self):
        self.run_tasks("done", "T-0001", "--project", "test-holon")
        self.assertEqual(self.links("T-0001"), ["deliverables/source.md"])

    def test_the_module_call_the_viewer_makes_adds_too(self):
        # serve.py calls apply() in process; replace is a keyword the module takes as well as the CLI
        code = ("import os, sys; sys.path.insert(0, %r); import importlib.util as u; "
                "s = u.spec_from_file_location('t', %r); t = u.module_from_spec(s); s.loader.exec_module(t); "
                "p, rel = t.resolve('test-holon'); t.apply(p, rel, 'link', id='T-0002', links=['/a']); "
                "t.apply(p, rel, 'link', id='T-0002', links=['/b']); t.apply(p, rel, 'link', id='T-0003', links=['/c'], replace=True)"
                % (HERE, TASKS_PY))
        r = subprocess.run([sys.executable, "-c", code], cwd=self.brain, capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, BRAIN_ROOT=self.brain))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.links("T-0002"), ["/a", "/b"])
        self.assertEqual(self.links("T-0003"), ["/c"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
