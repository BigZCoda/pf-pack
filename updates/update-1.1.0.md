# Update 1.1.0 — folder components (2026-09-23)

**From 1.0.0.** Two files: `skills/update/update-skill.md` (new section "Folder components", one safety-rail line widened) and the new `skills/update/install-component.py`. Both are at `https://github.com/BigZCoda/pf-pack/tree/main/files/update-1.1.0/`.

**Apply.** Add `skills/update/install-component.py` from that folder as it is. In `update-skill.md`, add the "Folder components" section before "Procedure" and widen the safety rail to allow the files a folder component's `keepBeforeReplace` copies into its user layer; keep your own `MANIFEST_URL` line as it is. Then bump the frontmatter to `1.1.0` and the matching row in `skills/skill-registry.md`, and log the update.

**What it changes.** Until now every pack skill was updated by a prompt the agent merges into the local file. A folder component is an application that is the same for everyone: its manifest entry says `"update": "replace-folder"` and names an `installRoot`, and it is replaced whole by `python skills/update/install-component.py <component>`. What a person makes for it lives outside that folder (for the Brain Viewer, `viewer/`), so nothing of theirs is lost. `--check` reports installed and published versions without changing anything.

**Confirm it worked.** `python skills/update/install-component.py brain-viewer --check` prints one line naming the installed and the published version.
