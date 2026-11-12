# brain-hooks 0.1.0 — a session that starts knowing where your brain stands (2026-11-12)

**New component.** The files are at `https://github.com/BigZCoda/pf-pack/tree/main/files/brain-hooks-0.1.0/`.

**Apply.** Install it as a folder component: `python skills/update/install-component.py brain-hooks` (on a Mac, `python3`). Then register its hooks and commands: `python skills/brain-hooks/install.py`. That writes the hooks into `.claude/settings.json` and three commands into `.claude/commands/`, keeping anything already there that the person added, and never touching `.claude/settings.local.json`. Add the row to `skills/skill-registry.md` and log the update.

**What it changes.** Until now a session in this brain waited for the first message before reading anything. From the next session on:
- The last session, the standing reminders, the open work and any unread presses from the viewer are in front of Claude before the first reply, and Claude opens with the short recap.
- The viewer is checked and started if it is silent, and it keeps running after the session ends.
- The log is checked after every write, so a line out of order is caught at once.
- When the last-session file is more than four hours old at the end of a session, a reminder says to close the day.
- Before a long conversation is compacted, the files changed in the last two hours are noted in the log.
- Three commands: `/start-session` (the recap), `/update` (check for updates) and `/done-for-today` (close the day).

**Confirm it worked.** `python skills/brain-hooks/hooks.py --check` lists what each hook found; the next session opens with the recap.
