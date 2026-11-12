# skills/brain-hooks/ — what a brain does on its own when a session opens and closes

**What's in here.** The hooks and commands every brain built from the kit carries, so a session starts knowing where things stand without anyone typing it. Made 2026-11-12, when the owner asked why a new brain had no start-session and which hooks a mentee should have ("Lets get it going... It should be accessible to them").

| Hook | When it runs | What it does |
|---|---|---|
| `hooks.py session-start` | a session opens or resumes | Puts the last session, the standing reminders, the open work and any unread viewer presses in front of Claude, and asks it to open with the recap. A brain not set up yet is told to run SETUP.md. |
| `hooks.py viewer` | a session opens or resumes | Checks the viewer at http://127.0.0.1:8765 and starts it if it is silent, detached so it keeps running after the session ends. |
| `hooks.py log-check` | after a write, when Claude stops, when the session ends | Runs the log tool's check, so a line written out of order is caught at once. Clean is silent. |
| `hooks.py session-end` | the session ends | Reminds the person to say "I'm done for today" when the last-session file is more than four hours old. |
| `hooks.py precompact` | before the conversation is compacted | Writes a line to the log naming the files changed in the last two hours, so the work in motion can be picked up. |

| Command | What it does |
|---|---|
| `/start-session` | The recap from CLAUDE.md's boot sequence, with the viewer's presses read first. |
| `/update` | Checks for updates and installs them on the person's yes (`skills/update/update-skill.md`). |
| `/done-for-today` | Writes the session into `context/active-session.md`, then offers commit and push. |

**How they get registered.** `install.py` writes the hooks into `.claude/settings.json` and the commands into `.claude/commands/`, keeping anything the person added there, and never touching `.claude/settings.local.json`. The assembler runs it when a brain is built; after this folder updates, run `python skills/brain-hooks/install.py` again. `python skills/brain-hooks/hooks.py --check` says what each hook would do on this computer.

**What stays out on purpose.** The owner's own hooks that only work in the maintainer's brain: the onboarding app poll and the folder-contract write gate. The Starter brain page in the viewer (`/starter`) lists every hook and command the owner has and a starter brain does not.

**Authority.** This folder is a kit component, replaced whole by an update. Change it in the maintainer's brain and release it; never edit it in a mentee's brain.

**Last touched.** 2026-11-12 (0.1.0, created).
