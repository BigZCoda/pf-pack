# People-Adapter 1.0.0 — the people-card component (NEW, 2026-07-20)

Your brain's `people/` folder becomes a contracted component: cards carry three layers — **frontmatter facets** (queryable fields), **prose** (your candid depth, never machine-parsed), and **dated folds** (the append-only journal every transcript adds to).

## Install
1. Copy from `https://github.com/BigZCoda/pf-pack/tree/main/files/people-adapter-1.0.0/`:
   - `people.py` → `skills/people-adapter/people.py`
   - `facets.json` → `people/facets.json` (the facet registry — base facets only: category, status, skills, contexts, orgs, location, first-met, last-fold, links)
2. Add a row to `skills/skill-registry.md`: people-adapter 1.0.0.

## How it behaves
- `python skills/people-adapter/people.py --list` — every card's facets as JSON.
- `--get <slug> --tier shareable` — a card stripped to its shareable sections (candid notes and `[private]` lines never leave). This render is what card-sharing will use when that app feature exists.
- `--verify` — checks facets are registered (unknown frontmatter keys are flagged), categories valid, fold dates well-formed.
- **Your cards NEVER push to the app.** They are brain-side only — that's what keeps your candid working notes about your mentor and colleagues safe.
- Transcript-processor 1.2.0's People fold maintains cards and their facets automatically from every call. Modules you install later may register additional facets in `facets.json` (a facet-fill pass backfills them from your existing cards — never fabricating).

Log the install in `context/log.md`.
