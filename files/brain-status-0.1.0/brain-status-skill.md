---
name: brain-status
version: 0.1.0
description: >-
  One read of a brain's state: every pack component's installed version against the published pf-pack manifest,
  skills the manifest does not know, files changed or added inside folder components, which features are switched on
  (token, ledgers, registry, survey, hooks, viewer, setup), the last pull and push, the inbox, and log activity.
  Writes context/brain-status.json and prints a short summary. Use on "check my brain", "what version am I on",
  "is anything out of date", at rounds, and at a mentee's session start.
---

# brain-status: what this brain has, what version it runs, what is switched on

> **Version:** 0.1.0 (2026-10-01) | **Runs in:** any brain built from brain-shell plus pf-pack components (a mentee's), and in Zak's.
> Standard library Python 3.10+, Windows and Mac. Nothing in it needs a key.

## Run it

From the brain root (on a Mac, `python3`):

```
python skills/brain-status/status.py
```

It writes `context/brain-status.json`, appends one log line (agent `brain-status`, action `LINTED`) through `skills/brain-log/log.py`, and prints a summary of about ten lines: components behind, components available but not installed, extras, customizations count, features on and off, last pull and push, inbox count, log activity.

Options: `--json` (print the JSON too), `--offline` (no network; the cached manifest is used if there is one), `--manifest <path-or-url>` (a local pf-pack checkout's `pf-pack-manifest.json`, or another URL), `--brain <folder>` (check another brain **read-only**: nothing is written into it, no JSON, no cache, no log line), `--out <file>` (where the JSON goes; with `--brain`, nowhere unless given).

**The line rounds and a session start call:** `python skills/brain-status/status.py` and report the summary it prints. Read nothing else to answer "what version am I on".

**Worked when:** the last printed line says `wrote .../context/brain-status.json` and the log has a new `[brain-status] LINTED` line.

## Triggers

- "check my brain", "what version am I on", "is anything out of date", "what's switched on"
- Zak's rounds (the step that runs the audits) and a mentee's session start, with the line above.
- Before `/update`, to see what it would find. This skill only reads; `/update` applies.

## What the JSON means

| Key | What it holds |
|---|---|
| `_generatedAt`, `_generatedBy` | the clock when it ran, and the script and version that wrote it |
| `brain` | the brain's root folder name |
| `owner` | the name on CLAUDE.md's `**Inhabitant:**` line; a brain without that line falls back to `viewer/settings.json`'s `owner`; else `uninhabited` |
| `maintainerCopy` | true when `skills/brain-viewer/release.py` exists: the brain the components are released from, where local-newer is expected |
| `manifestSource` | `network:<url>`, `file:<path>`, `cache:... (fetched <when>)`, or `unavailable` |
| `manifestUpdatedAt` | the manifest's own `updatedAt`, null without one |
| `components[]` | one row per manifest entry: `present`, `installed` and `installedFrom` (component.json, the spec's `version:` frontmatter, or the registry line, in that order), `manifest`, `updateAvailable` (true, false, or null when either side is unknown), `kind` (`skill` or `folder`). A `-mentee` suffix compares as its base version. Without a manifest, every local skill with a version is listed with nulls |
| `extras[]` | skill folders the manifest does not know, with their version if any (in a mentee brain today: brain-survey, mentee-project) |
| `customizations[]` | per folder component (`update: replace-folder`): `added` (files inside its installRoot the manifest does not list), `changed` (listed files whose sha256 differs, path only; a CRLF copy of an LF release counts as the same), `missing`. Computed only when a manifest is available. A folder component is replaced whole on update, so anything here is lost by design when it updates |
| `features` | `tokenFile` (presence of `PF App API.txt` at the root, never its contents, plus a count of other key files), `ledgers` (count and paths: the registry's `tasks` entries plus any `*-tasks.md` in the ledger shape), `registry` (`context/holon-registry.json`), `survey` (`inbox/survey-*.md`, where brain-survey writes), `hooks` (`.claude/settings.json` in the brain), `viewer` (installed, version from its component.json, and `answersOn8765`: a 1-second socket connect, no request), `setupComplete` (SETUP.md's `SETUP COMPLETE` header; null without a SETUP.md), `lastPull` (newest `[ferryman] PULL` line), `lastPush` (newest `[ferryman] SYNCED` line pushing to the PF App), `lastGitPush`, `inbox` (count and names, readme.md excluded) |
| `activity` | log lines in the last 7 and 30 days (rotated months under `archive/ledgers/` included), the last line's date, and the last three distinct agents |

`answersOn8765` is a property of the machine, not the brain: if any viewer is running on this computer it reads true, whichever brain is checked.

## Where it is read

PF reads `context/brain-status.json` from the mentee's repository today (it is committed with the rest of the brain). It is meant to become a block on that mentee's people card and a panel in a future dashboard; both read the same file, so the file's keys are the contract and change only with a version bump here.

## Safety rails

- Read-only except three writes in its own brain: `context/brain-status.json`, `context/.pack-manifest-cache.json` after a successful fetch, and one log line. `--brain` writes none of them.
- One network call: a GET of the manifest. Never a call to the PF App, never a write to the viewer.
- Token and key files are checked by name only.
