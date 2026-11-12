#!/usr/bin/env python3
"""safety_commit.test.py -- the safety commit refuses a file GitHub will refuse, by name, before committing
(brain-central T-0097, 2026-10-21; the 10/01 run committed a 141 MB zip and every push failed until 10/02).

Each test builds a scratch brain in a temp folder: a git repo whose .gitignore holds the key files, a log with no ROUNDS
line today, a copy of safety_commit.py, and a stand-in log.py that records what would have been logged. A file over
95 MB is refused, named with its size on stdout and, on a real run, in a FLAGGED log line, and nothing is committed; a
file over 50 MB is named and committed. No remote is set, so nothing is ever pushed, and the brain's own repo and log
are not touched.

    python skills/brain-log/safety_commit.test.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MB = 1024 * 1024
KEY_FILES = ["APIZZLE.txt", "PF App API.txt", "Onboarding API.txt", "pfk_key.txt", "deepseek_key.txt", "Claude SetupToken.txt", "hf_key.txt", "typeform_key.txt", "tally_key.txt",
             "viewer/sharing-signin.json"]
STUB_LOG = 'import sys\nwith open(__file__ + ".lines", "a", encoding="utf-8") as f:\n    f.write(" | ".join(sys.argv[1:]) + "\\n")\n'


class ScratchBrain(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="safety-commit-test-")
        os.makedirs(os.path.join(self.root, "skills", "brain-log"))
        os.makedirs(os.path.join(self.root, "context"))
        shutil.copy(os.path.join(HERE, "safety_commit.py"), os.path.join(self.root, "skills", "brain-log"))
        self.write("skills/brain-log/log.py", STUB_LOG)
        self.write(".gitignore", "\n".join(KEY_FILES + ["skills/brain-log/log.py.lines", "__pycache__/"]) + "\n")
        self.write("context/log.md", "# log\n[2026-01-01 09:00] [claude-code] MODIFIED -- a.md -- an old line\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "start")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def sized(self, rel, mb):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.truncate(int(mb * MB))

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com"] + list(args),
                              cwd=self.root, capture_output=True, text=True, check=True).stdout

    def commits(self):
        return int(self.git("rev-list", "--count", "HEAD").strip())

    def logged(self):
        p = os.path.join(self.root, "skills", "brain-log", "log.py.lines")
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as f:
            return f.read().splitlines()

    def run_it(self, *args):
        return subprocess.run([sys.executable, os.path.join(self.root, "skills", "brain-log", "safety_commit.py")] + list(args),
                              cwd=self.root, capture_output=True, text=True)


class TheSizeGuard(ScratchBrain):

    def test_a_dry_run_refuses_a_100_mb_file_by_name(self):
        self.sized("deliverables/studio/print-package.zip", 100)
        self.write("notes.md", "a small change\n")
        r = self.run_it("--dry-run")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("REFUSED", r.stdout)
        self.assertIn("deliverables/studio/print-package.zip (100.0 MB)", r.stdout)
        self.assertNotIn("DRY RUN, would commit", r.stdout)
        self.assertEqual((self.commits(), self.logged()), (1, []))

    def test_a_real_run_refuses_logs_the_file_and_commits_nothing(self):
        self.sized("deliverables/studio/print-package.zip", 141)
        r = self.run_it()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self.commits(), 1)
        lines = self.logged()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--action | FLAGGED", lines[0])
        self.assertIn("--text | deliverables/studio/print-package.zip -- safety commit REFUSED: 141.0 MB", lines[0])
        self.assertEqual(self.git("status", "--porcelain").strip(), "?? deliverables/")   # nothing staged

    def test_a_big_file_inside_a_new_folder_is_found(self):
        # git status folds an untracked folder into one line; the guard lists every file singly
        self.sized("new-folder/deeper/video.mp4", 96)
        r = self.run_it("--dry-run")
        self.assertEqual(r.returncode, 2)
        self.assertIn("new-folder/deeper/video.mp4 (96.0 MB)", r.stdout)

    def test_a_tracked_file_that_grew_over_the_guard_is_refused(self):
        self.write("data/export.json", "{}\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "small export")
        self.sized("data/export.json", 99)
        r = self.run_it("--dry-run")
        self.assertEqual(r.returncode, 2)
        self.assertIn("data/export.json (99.0 MB)", r.stdout)

    def test_a_file_over_50_mb_is_named_and_still_committed(self):
        self.sized("deliverables/recording.m4a", 60)
        r = self.run_it("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("WARNING, deliverables/recording.m4a is 60.0 MB", r.stdout)
        self.assertIn("DRY RUN, would commit 1 changed paths", r.stdout)

    def test_an_ignored_big_file_is_not_counted(self):
        self.write(".gitignore", "\n".join(KEY_FILES + ["skills/brain-log/log.py.lines", "*.zip"]) + "\n")
        self.sized("deliverables/studio/print-package.zip", 141)
        r = self.run_it("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("DRY RUN, would commit 1 changed paths", r.stdout)   # the .gitignore change only

    def test_a_deleted_file_is_not_sized(self):
        self.write("old.md", "x\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "old")
        os.remove(os.path.join(self.root, "old.md"))
        r = self.run_it("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("(1 deletions)", r.stdout)


class TheBackupSwitch(ScratchBrain):
    """The push obeys the viewer's switch (2026-11-11): off, the night's commit stays on the computer. A bare repository
    in the temp folder stands in for GitHub; nothing leaves the computer."""

    def setUp(self):
        super().setUp()
        self.origin = self.root + "-origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.origin], check=True, capture_output=True)
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.com")
        self.git("remote", "add", "origin", self.origin)
        self.git("push", "-q", "origin", "main")

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.origin, ignore_errors=True)

    def pushed(self):
        there = subprocess.run(["git", "--git-dir", self.origin, "rev-parse", "main"], capture_output=True, text=True).stdout.strip()
        return there == self.git("rev-parse", "HEAD").strip()

    def test_with_no_setting_the_commit_is_pushed_as_before(self):
        self.write("notes.md", "a change\n")
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("committed and pushed", r.stdout)
        self.assertEqual((self.commits(), self.pushed()), (2, True))

    def test_switched_off_the_commit_stays_on_the_computer(self):
        self.write("viewer/settings.json", '{"nightly_backup": false}\n')
        self.write("notes.md", "a change\n")
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("on this computer; not pushed: the nightly backup to GitHub is off in the viewer's Settings", r.stdout)
        self.assertEqual((self.commits(), self.pushed()), (2, False))
        self.assertTrue(any("kept on this computer, not pushed" in l for l in self.logged()), self.logged())
        self.assertEqual(self.git("status", "--porcelain").strip(), "", "everything is committed all the same")

    def test_switched_on_again_the_next_night_pushes_both_commits(self):
        self.write("viewer/settings.json", '{"nightly_backup": false}\n')
        self.write("notes.md", "one\n")
        self.assertEqual(self.run_it().returncode, 0)
        self.write("viewer/settings.json", '{"nightly_backup": true}\n')
        self.write("notes.md", "two\n")
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.commits(), self.pushed()), (3, True))

    def test_a_settings_file_that_does_not_read_keeps_the_commit_on_the_computer(self):
        self.write("viewer/settings.json", "{ not json\n")
        self.write("notes.md", "a change\n")
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("not pushed: viewer/settings.json does not read", r.stdout)
        self.assertEqual((self.commits(), self.pushed()), (2, False))

    def test_a_dry_run_says_which_it_would_do(self):
        self.write("notes.md", "a change\n")
        self.assertIn("and push origin main", self.run_it("--dry-run").stdout)
        self.write("viewer/settings.json", '{"nightly_backup": false}\n')
        self.assertIn("and keep it on this computer", self.run_it("--dry-run").stdout)
        self.assertEqual(self.commits(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
