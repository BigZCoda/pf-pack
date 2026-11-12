#!/usr/bin/env python3
"""tasks-judge-text.test.py -- a card that asks the owner to judge a text shows the text in quotes (2026-10-21,
brain-central T-0184).

On 10/15 a card asked the owner whether "this one-sentence purpose" fit what a client wanted, and ran the sentence on into
the question and the background; he answered that he could not see where the sentence was at all. The re-posed card put
the purpose in quotes after a lead that named it, and he answered it. The rule is in readme.md (How agents use it, the
cold-reader rules, rule 7); the tool prints a WARN, never a refusal, when an item addressed to the owner names such a text
in its ask and carries no quoted passage of four words or more, and `check` counts it among the COLD items.

Every test builds its own scratch brain in a temp folder (a holon registry naming one ledger, the ledger, a log, and a
viewer settings file naming the owner) and runs the real tasks.py as a subprocess with BRAIN_ROOT pointing there, so no
brain file is touched.

    python skills/brain-tasks/tasks-judge-text.test.py
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
WARN = "WARN: it asks the owner to judge"

# the 10/15 card as it was asked, and as it was re-posed (both answered; the second one he could answer)
BEFORE = ("Does this one-sentence purpose for the client's onboarding system fit what the client wants, as a strawman to "
          "react against before part 2 of the interview? A qualified hire gives their details once, in one conversation, "
          "and signs every form in one envelope. A yes puts it in front of the client on the next call.")
AFTER = ("Is this the right direction for fixing how the client onboards new staff, as a draft to test in part 2 of the "
         "interview? The draft purpose, in one sentence: \"A new hire gives their details once, in one conversation, and "
         "signs every form in one envelope.\" Your answer decides what the next call tests.")

LEDGER = textwrap.dedent("""\
    # Test holon — tasks and questions
    > scratch ledger for tasks-judge-text.test.py

    ## Inbox
    - [?] Q-0001 2026-10-21 @claude → @zak · Is this the right direction for the welcome page, yes or no? A yes means it is built next.
    """)


class AJudgedTextStandsInQuotes(unittest.TestCase):

    def setUp(self):
        self.brain = tempfile.mkdtemp(prefix="tasks-judge-text-")
        for d in ("context", "test-holon", "viewer"):
            os.makedirs(os.path.join(self.brain, d), exist_ok=True)
        self.put("context/holon-registry.json", json.dumps({"holons": [
            {"id": "test-holon", "name": "Test holon", "path": "test-holon/", "tasks": LEDGER_REL}]}))
        self.put("viewer/settings.json", json.dumps({"owner": "zak"}))
        self.put("context/log.md", "# Log\n")
        self.put(LEDGER_REL, LEDGER)

    def tearDown(self):
        shutil.rmtree(self.brain, ignore_errors=True)

    def put(self, rel, text):
        with open(os.path.join(self.brain, rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def raw(self, rel=LEDGER_REL):
        with open(os.path.join(self.brain, rel), encoding="utf-8") as f:
            return f.read()

    def run_tasks(self, *args):
        r = subprocess.run([sys.executable, TASKS_PY] + list(args), cwd=self.brain, capture_output=True, text=True,
                           timeout=120, env=dict(os.environ, BRAIN_ROOT=self.brain))
        self.assertEqual(r.returncode, 0, "tasks.py %s failed: %s %s" % (" ".join(args), r.stdout, r.stderr))
        return r

    def test_the_card_as_it_was_asked_on_10_15_is_warned_and_still_filed(self):
        r = self.run_tasks("ask", "--project", "test-holon", "--to", "@zak", "--text", BEFORE, "--options", "it fits | change it")
        self.assertIn(WARN + " 'this one-sentence purpose'", r.stderr)
        self.assertIn("in quotes as their own passage", r.stderr)
        self.assertIn("a defining clause", r.stderr)
        self.assertIn("Q-0002 asked", r.stdout)
        self.assertIn("Q-0002", self.raw(), "a WARN is not a refusal: the question is filed")

    def test_the_card_as_it_was_re_posed_is_not_warned(self):
        r = self.run_tasks("ask", "--project", "test-holon", "--to", "@zak", "--text", AFTER, "--options", "it fits | change it")
        self.assertNotIn(WARN, r.stderr)

    def test_a_question_to_claude_is_not_his_to_read(self):
        r = self.run_tasks("ask", "--project", "test-holon", "--to", "@claude", "--text", BEFORE)
        self.assertNotIn(WARN, r.stderr)

    def test_a_task_for_the_owner_is_checked_and_one_for_claude_is_not(self):
        text = "Read the draft purpose for the client's onboarding system and say whether it fits what the client asked for."
        self.assertIn(WARN + " 'the draft purpose'", self.run_tasks("add", "--project", "test-holon", "--owner", "@zak", "--text", text).stderr)
        self.assertNotIn(WARN, self.run_tasks("add", "--project", "test-holon", "--owner", "@claude", "--text", text).stderr)

    def test_retext_into_the_bad_shape_is_warned(self):
        r = self.run_tasks("retext", "Q-0001", "--project", "test-holon", "--text", BEFORE)
        self.assertIn(WARN, r.stderr)

    def test_a_line_on_a_drawing_is_not_a_text_to_judge(self):
        text = "Open the onboarding drawing and drag a part across a line; that line should route around the part. Say if it does."
        self.assertNotIn(WARN, self.run_tasks("add", "--project", "test-holon", "--owner", "@zak", "--text", text).stderr)

    def test_check_counts_an_open_one_among_the_cold_items(self):
        self.run_tasks("ask", "--project", "test-holon", "--to", "@zak", "--text", BEFORE, "--options", "it fits | change it")
        r = subprocess.run([sys.executable, TASKS_PY, "check", "--project", "test-holon", "--verbose"], cwd=self.brain,
                           capture_output=True, text=True, timeout=120, env=dict(os.environ, BRAIN_ROOT=self.brain))
        out = r.stdout + r.stderr
        self.assertIn("COLD", out)
        self.assertIn("Q-0002", out)
        self.assertIn("this one-sentence purpose", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
