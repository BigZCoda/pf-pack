# pf-pack — ProspectForge skill-version manifest

Version manifest + update prompts for skills shipped inside ProspectForge user brains.

**How it works:** every PF brain includes an `/update` skill that fetches `pf-pack-manifest.json`,
compares versions against the brain's local skill registry, and (on the user's yes) applies the
linked update prompt from `updates/`. Updates are prompts the user's own agent applies with
judgment — never file overwrites. Full design: the PF brain-export plan (internal).

**Publishing an update (Zak):**
1. Write the update prompt as `updates/{skill}-{new-version}.md` (what to change and why).
2. Bump that skill's `version` + `changelog` in `pf-pack-manifest.json`, set `promptUrl` to the raw URL of the prompt file.
3. Commit + push. Every brain's next `/update` sees it.

This repo contains version numbers and update prompts only — no user data, no tokens, no full skill bodies.
