# pf-pack — ProspectForge skill-version manifest

Version manifest + update prompts for skills shipped inside ProspectForge user brains.

**How it works:** every PF brain includes an `/update` skill that fetches `pf-pack-manifest.json`,
compares versions against the brain's local skill registry, and (on the user's yes) applies the
linked update prompt from `updates/`. Updates are prompts the user's own agent applies with
judgment — never file overwrites. Full design: the PF brain-export plan (internal).

**Folder components (2026-09-23).** One exception to "prompts, not overwrites": a manifest entry carrying
`"update": "replace-folder"` and an `installRoot` is an application that is the same for everyone, installed and
replaced WHOLE by `skills/update/install-component.py` (update 1.1.0). The Brain Viewer (`brain-viewer`, installed at
`skills/brain-viewer/`) is the first. Its files sit under `files/brain-viewer-<version>/` like every other component's,
each listed in `files[]` with its sha256; what a person makes for it lives in their brain's `viewer/`, which no update
writes. It is released by `skills/brain-viewer/release.py` in the maintainer brain, which runs the viewer's tests,
copies the component here, bumps the manifest and commits; pushing stays a separate step.

**Publishing an update (Zak):**
1. Write the update prompt as `updates/{skill}-{new-version}.md` (what to change and why).
2. Bump that skill's `version` + `changelog` in `pf-pack-manifest.json`, set `promptUrl` to the raw URL of the prompt file.
3. Commit + push. Every brain's next `/update` sees it.

This repo contains version numbers, update prompts and the component files the assembler and the updater install — no user data, no tokens.
