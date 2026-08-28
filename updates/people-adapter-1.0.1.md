# People-Adapter 1.0.1 — facet registry update: career-arc (2026-08-28)

**From 1.0.0.** `people.py` is unchanged. This release updates only the facet registry.

**Apply to:** `people/facets.json` in this brain. Merge — keep any facets or packs you've registered locally.

## The change

In `base_facets`, ADD one optional facet if not already present (after `contexts`):

```json
"career-arc": "optional, kebab-case sequence of career stages in rough chronological order (senior/partner/mentor cards mainly)"
```

Then bump the registry's top-level `"version"` by one, and update the people-adapter row in `skills/skill-registry.md` to `1.0.1`; log the update.

## Why (one paragraph, for the curious)

The verifier (`people.py --verify`) flags any frontmatter key not listed in the registry — that's schema-drift protection working as designed. `career-arc` proved useful on senior/mentor cards in the reference brain, so it joins the base registry; without this update, a card that uses it fails your verifier even though the data is sound.
