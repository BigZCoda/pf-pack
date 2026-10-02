# Ferryman 1.3.1 — every call carries a User-Agent; the brain root is found, not written in (2026-10-02)

**From 1.3.0.** Full replacement files at
`https://github.com/BigZCoda/pf-pack/tree/main/files/ferryman-1.3.1/` — or apply the changes below to your copies, preserving any LOCAL ADAPTATION blocks and your own filled-in folder table. `pipeline-verify.py`, `transcript-intake-runbook.md`, `ferryman-adapter-contract.md` and `ferryman-rules.md` are unchanged in this release.

**Apply to:** `skills/ferryman/pull.py` (required), `skills/ferryman/push.py` (required), `skills/ferryman/ferryman-skill.md`. Merge — do not blind-replace anything you've adapted.

## 1. FIX (required) — the first call to the app fails with 403 for every new brain

The PF App sits behind Cloudflare. Since 2026-09-24 its edge answers `403` with the body `error code: 1010` to any request that carries no `User-Agent` header, before the request reaches the app. Python's `urllib` sends none, and the 1.3.0 scripts did not add one, so a fresh brain's first `pull.py` (and every `push.py`) fails with a message that looks like a bad token. The token is fine.

Apply: in every `urllib.request.Request(...)` call in `pull.py` (one) and `push.py` (two: the POST helper and the tags GET), add the header as the first key:
```python
headers={"User-Agent": "prospectforge-brain-ferryman/1.0", "Authorization": f"Bearer {...}", ...}
```
Any new script, hook or one-off probe you write against the app does the same.

Confirm with a status run, which is read-only:
```
python skills/ferryman/pull.py
```
A 1.3.1 run reports the app's transcripts against your mirror instead of a 403.

## 2. NEW — `BRAIN_ROOT` overrides the brain root

Both scripts found the brain as the folder two levels above themselves. They still do, and now `BRAIN_ROOT` in the environment overrides it (useful when you run the script from a copy outside the brain). Apply: add `import os` and make the line
```python
BRAIN = Path(os.environ.get("BRAIN_ROOT") or Path(__file__).resolve().parents[2])
```
If your copy still carries a path written for one machine (`BRAIN = Path(r"C:\...")`), this line replaces it.

## 3. Smaller merges

- `ferryman-skill.md`: the 1.3.1 note at the top; frontmatter `version: 1.3.1`.
- `push.py` docstring: the 1.3.1 block above the 1.3.0 one.

Bump the skill frontmatter to `1.3.1` + the matching row in `skills/skill-registry.md`; log the update.
