#!/usr/bin/env python3
"""tasks-steps.test.py -- the steps on a task (2026-10-16, viewer 0.86.0): what its owner does to finish it, written and
read by tasks.py. `steps <id> --set "one | two"` replaces the list, `--tick N` and `--untick N` mark one step, `steps <id>`
prints them; the segment is `steps:[ ] one | [x] two`; the tool refuses more than twelve steps, a step over 200
characters, an id with no clause, a question, and a tick that is not a step.

Every test builds its own scratch brain in a temp folder (a holon registry naming one ledger, the ledger, a log) and runs
the real tasks.py as a subprocess with BRAIN_ROOT pointing there, so no brain file is touched.

    python3 skills/brain-tasks/tasks-steps.test.py
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

LEDGER = textwrap.dedent("""\
    # Test holon — tasks and questions
    > scratch ledger for tasks-steps.test.py

    ## Inbox
    - [ ] T-0001 2026-10-16 @zak · Give Dani your part of the cost list · note:Due today. Reply to her email.
    - [ ] T-0002 2026-10-16 @zak · Hang the sign
    - [?] Q-0001 2026-10-16 @claude → @zak · Is the sign ready, yes or no? A yes closes the hanging task.
    - [ ] T-0003 2026-10-16 @zak · Written by hand with steps · steps:first by hand | [x] second by hand | third by hand
    """)


class TheStepsOnATask(unittest.TestCase):

    def setUp(self):
        self.brain = tempfile.mkdtemp(prefix="tasks-steps-")
        for d in ("context", "test-holon"):
            os.makedirs(os.path.join(self.brain, d), exist_ok=True)
        self.put("context/holon-registry.json", json.dumps({"holons": [
            {"id": "test-holon", "name": "Test holon", "path": "test-holon/", "tasks": LEDGER_REL}]}))
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

    def line(self, iid):
        return next(l for l in self.raw().splitlines() if (" %s " % iid) in l)

    def run_tasks(self, *args):
        return subprocess.run([sys.executable, TASKS_PY] + list(args), cwd=self.brain, capture_output=True, text=True,
                              encoding="utf-8", timeout=120, env=dict(os.environ, BRAIN_ROOT=self.brain, PYTHONIOENCODING="utf-8"))

    def ok(self, *args):
        r = self.run_tasks(*args)
        self.assertEqual(r.returncode, 0, "tasks.py %s failed: %s %s" % (" ".join(args), r.stdout, r.stderr))
        return r.stdout

    def refused(self, needle, *args):
        r = self.run_tasks(*args)
        self.assertNotEqual(r.returncode, 0, "tasks.py %s was accepted: %s" % (" ".join(args), r.stdout))
        self.assertIn(needle, r.stderr, "the refusal did not say %r: %s" % (needle, r.stderr))
        return r.stderr

    def steps(self, iid, *more):
        return self.ok("steps", iid, "--project", "test-holon", *more)

    # ---- the segment, written and read

    def test_set_writes_the_segment_and_the_print_reads_it_back(self):
        self.steps("T-0001", "--set", "Look up the Anthropic bill at console.anthropic.com, Billing | Send Dani the monthly number | Tell her the host is a placeholder")
        self.assertIn("· steps:[ ] Look up the Anthropic bill at console.anthropic.com, Billing | [ ] Send Dani the monthly number | [ ] Tell her the host is a placeholder", self.line("T-0001"))
        self.assertIn("· note:Due today. Reply to her email.", self.line("T-0001"))      # the note is untouched
        out = self.steps("T-0001")
        self.assertIn("T-0001 · 3 steps, 0 of 3 ticked", out)
        self.assertIn("[ ] 1. Look up the Anthropic bill", out)
        self.assertIn("[ ] 3. Tell her the host is a placeholder", out)
        self.assertIn("T-0002 · no steps", self.steps("T-0002"))

    def test_tick_and_untick_mark_one_step_and_refuse_a_mark_already_there(self):
        self.steps("T-0001", "--set", "one | two | three")
        self.steps("T-0001", "--tick", "2")
        self.assertIn("steps:[ ] one | [x] two | [ ] three", self.line("T-0001"))
        self.assertIn("1 of 3 ticked", self.steps("T-0001"))
        self.assertIn("T-0001 step 2 of 3 ticked: two", self.raw("context/log.md"))
        self.refused("already ticked", "steps", "T-0001", "--project", "test-holon", "--tick", "2")
        self.steps("T-0001", "--untick", "2")
        self.assertIn("steps:[ ] one | [ ] two | [ ] three", self.line("T-0001"))
        self.refused("already unticked", "steps", "T-0001", "--project", "test-holon", "--untick", "2")
        self.steps("T-0001", "--tick", "1")
        self.steps("T-0001", "--tick", "3")
        self.assertIn("2 of 3 ticked", self.steps("T-0001"))

    def test_a_tick_that_is_not_a_step_is_refused(self):
        self.refused("has no steps to tick", "steps", "T-0002", "--project", "test-holon", "--tick", "1")
        self.steps("T-0001", "--set", "one | two")
        self.refused("there is no step 3", "steps", "T-0001", "--project", "test-holon", "--tick", "3")
        self.refused("there is no step 0", "steps", "T-0001", "--project", "test-holon", "--tick", "0")
        self.refused("wants the step's number", "steps", "T-0001", "--project", "test-holon", "--tick", "two")

    def test_a_question_takes_no_steps(self):
        self.refused("is a question; steps belong to a task", "steps", "Q-0001", "--project", "test-holon", "--set", "one | two")
        self.assertNotIn("steps:", self.line("Q-0001"))

    # ---- the refusals on --set

    def test_more_than_twelve_steps_are_refused_and_twelve_are_written(self):
        self.refused("at most 12, not 13", "steps", "T-0001", "--project", "test-holon", "--set", " | ".join("step %d" % n for n in range(1, 14)))
        self.assertNotIn("steps:", self.line("T-0001"))
        self.steps("T-0001", "--set", " | ".join("step %d" % n for n in range(1, 13)))
        self.assertIn("12 steps, 0 of 12 ticked", self.steps("T-0001"))

    def test_a_step_over_200_characters_is_refused(self):
        long = "x" * 201
        err = self.refused("201 characters", "steps", "T-0001", "--project", "test-holon", "--set", "fine | " + long)
        self.assertIn("step 2", err)
        self.steps("T-0001", "--set", "fine | " + "y" * 200)
        self.assertIn("2 steps", self.steps("T-0001"))

    def test_an_id_with_no_clause_is_refused_and_an_id_with_its_clause_is_not(self):
        err = self.refused("an id with no clause", "steps", "T-0001", "--project", "test-holon", "--set", "Hang the sign | T-0002")
        self.assertIn("step 2", err)
        self.steps("T-0001", "--set", "Hang the sign | Close the sign task (T-0002) once it is up")
        self.assertIn("[ ] Close the sign task (T-0002) once it is up", self.line("T-0001"))

    def test_steps_with_no_flag_prints_and_writes_nothing(self):
        before = self.raw()
        self.steps("T-0001")
        self.assertEqual(before, self.raw())
        self.assertNotIn("T-0001", self.raw("context/log.md"))

    def test_an_empty_set_clears_the_list(self):
        self.steps("T-0001", "--set", "one | two")
        self.steps("T-0001", "--set", "")
        self.assertNotIn("steps:", self.line("T-0001"))
        self.assertIn("steps set: (cleared)", self.raw("context/log.md"))

    # ---- the field survives the other verbs, and reads as a list

    def test_the_steps_ride_through_retext_note_done_and_json(self):
        self.steps("T-0001", "--set", "one | two")
        self.steps("T-0001", "--tick", "1")
        self.ok("retext", "T-0001", "--project", "test-holon", "--text", "Give Dani the cost list")
        self.ok("note", "T-0001", "--project", "test-holon", "--note", "one line only")
        self.assertIn("· note:one line only · steps:[x] one | [ ] two", self.line("T-0001"))
        self.ok("done", "T-0001", "--project", "test-holon")
        self.assertIn("steps:[x] one | [ ] two", self.line("T-0001"))
        out = json.loads(self.ok("list", "--project", "test-holon", "--json"))
        it = next(i for i in out[0]["items"] if i["id"] == "T-0001")
        self.assertEqual(it["steps"], [{"text": "one", "done": True}, {"text": "two", "done": False}])
        self.assertIsNone(next(i for i in out[0]["items"] if i["id"] == "T-0002")["steps"])

    def test_a_line_written_by_hand_without_marks_reads_as_unticked_and_check_passes(self):
        out = self.steps("T-0003")
        self.assertIn("3 steps, 1 of 3 ticked", out)
        self.assertIn("[ ] 1. first by hand", out)
        self.assertIn("[x] 2. second by hand", out)
        self.ok("check", "--project", "test-holon")
        self.steps("T-0003", "--tick", "3")
        self.assertIn("steps:[ ] first by hand | [x] second by hand | [x] third by hand", self.line("T-0003"))
        self.assertIn("steps:2 of 3 ticked", self.ok("list", "--project", "test-holon"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
