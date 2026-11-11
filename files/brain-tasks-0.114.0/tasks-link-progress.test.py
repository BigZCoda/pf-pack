#!/usr/bin/env python3
"""tasks-link-progress.test.py -- a link set on a ledger item lands on the in-progress record (brain-central T-0136).

Every test builds its own scratch brain in a temp folder: a holon registry naming one ledger, the ledger (two open
tasks), context/in-progress.json with one project whose items name "test-holon T-0001" and "test-holon Q-0001", a
context/log.md, and a few files under deliverables/. The real tasks.py runs as a subprocess with BRAIN_ROOT pointing
at the scratch brain, so the real progress.py and log.py do the writes there and no brain file is touched.

    python3 skills/brain-tasks/tasks-link-progress.test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PY = os.path.join(HERE, "tasks.py")
LEDGER_REL = "test-holon/test-holon-tasks.md"
ADDED = "file added to in-progress"

LEDGER = textwrap.dedent("""\
    # Test holon — tasks and questions
    > scratch ledger for tasks-link-progress.test.py

    ## Inbox
    - [ ] T-0001 2026-10-07 @claude · Write the problem prompts doc for the test thread
    - [ ] T-0002 2026-10-07 @claude · Something no project names
    """)

PROGRESS = {
    "_about": "scratch",
    "projects": [{
        "id": "test-thread", "name": "Test thread", "since": "2026-10-07T10:00:00", "lastActivity": "2026-10-07T10:00:00",
        "files": [{"path": "deliverables/already.md", "added": "2026-10-07T10:00:00", "by": "claude-code"}],
        "items": ["test-holon T-0001", "test-holon Q-0001"], "note": ""}],
    "done": [],
}


class LinkLandsOnProgress(unittest.TestCase):

    def setUp(self):
        self.brain = tempfile.mkdtemp(prefix="tasks-link-progress-")
        for d in ("context", "test-holon", "deliverables/folder"):
            os.makedirs(os.path.join(self.brain, d), exist_ok=True)
        self.put("context/holon-registry.json", json.dumps({"holons": [
            {"id": "test-holon", "name": "Test holon", "path": "test-holon/", "tasks": LEDGER_REL}]}))
        self.put("context/log.md", "# Log\n")
        self.put(LEDGER_REL, LEDGER)
        self.put("context/in-progress.json", json.dumps(PROGRESS, indent=1) + "\n")
        for f in ("already", "a-doc", "b-doc", "c-doc", "d-doc", "e-doc"):
            self.put("deliverables/%s.md" % f, "# %s\n" % f)

    def tearDown(self):
        shutil.rmtree(self.brain, ignore_errors=True)

    def put(self, rel, text):
        with open(os.path.join(self.brain, rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def raw(self, rel):
        with open(os.path.join(self.brain, rel), encoding="utf-8") as f:
            return f.read()

    def files(self):
        return [x["path"] for x in json.loads(self.raw("context/in-progress.json"))["projects"][0]["files"]]

    def run_tasks(self, *args):
        r = subprocess.run([sys.executable, TASKS_PY] + list(args), cwd=self.brain, capture_output=True, text=True,
                           timeout=120, env=dict(os.environ, BRAIN_ROOT=self.brain))
        self.assertEqual(r.returncode, 0, "tasks.py %s failed: %s %s" % (" ".join(args), r.stdout, r.stderr))
        return r.stdout

    def test_link_lands_once_and_a_second_link_does_not_duplicate(self):
        args = ["link", "T-0001", "--project", "test-holon", "--link", "deliverables/a-doc.md", "--link", "/glossary",
                "--link", "deliverables/missing.md", "--link", "deliverables/folder/", "--link", "deliverables/already.md",
                "--link", "[[deliverables/b-doc]]"]
        out = self.run_tasks(*args)
        self.assertIn("T-0001 link", out)
        self.assertEqual(self.files(), ["deliverables/already.md", "deliverables/a-doc.md", "deliverables/b-doc.md"])
        self.assertEqual(out.count(ADDED), 2, out)
        self.assertIn("T-0001 file added to in-progress Test thread: deliverables/a-doc.md", out)
        self.assertIn("in-progress] MODIFIED -- context/in-progress.json", self.raw("context/log.md"))
        before = self.raw("context/in-progress.json")
        out = self.run_tasks(*args)
        self.assertEqual(out.count(ADDED), 0, out)
        self.assertEqual(self.files().count("deliverables/a-doc.md"), 1)
        self.assertEqual(self.raw("context/in-progress.json"), before, "a repeat link rewrote the record")

    def test_done_link_through_file_resolves_the_holon(self):
        out = self.run_tasks("done", "T-0001", "--file", LEDGER_REL, "--link", "deliverables/c-doc.md")
        self.assertIn("T-0001 file added to in-progress Test thread: deliverables/c-doc.md", out)
        self.assertIn("deliverables/c-doc.md", self.files())
        self.assertIn("- [x] T-0001", self.raw(LEDGER_REL))

    def test_ask_link_lands_on_the_new_question(self):
        out = self.run_tasks("ask", "--project", "test-holon", "--to", "@claude", "--text", "Is the doc current?",
                             "--link", "deliverables/d-doc.md")
        self.assertIn("Q-0001 asked", out)
        self.assertIn("deliverables/d-doc.md", self.files())

    def test_an_item_no_project_names_changes_nothing(self):
        before = self.raw("context/in-progress.json")
        out = self.run_tasks("link", "T-0002", "--project", "test-holon", "--link", "deliverables/e-doc.md")
        self.assertNotIn(ADDED, out)
        self.assertEqual(self.raw("context/in-progress.json"), before)
        self.assertIn("→ deliverables/e-doc.md", self.raw(LEDGER_REL))

    def test_the_ledger_write_leaves_no_temp_file(self):
        self.run_tasks("link", "T-0001", "--project", "test-holon", "--link", "deliverables/a-doc.md")
        for d in ("test-holon", "context"):
            left = [f for f in os.listdir(os.path.join(self.brain, d)) if f.endswith(".tmp")]
            self.assertEqual(left, [], "temp files left in %s: %s" % (d, left))
        self.assertIn("T-0001", self.raw(LEDGER_REL))


if __name__ == "__main__":
    unittest.main(verbosity=2)
