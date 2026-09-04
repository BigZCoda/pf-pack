# Ferryman Adapter Contract — generalizing the Ferryman to any API
**Created:** 2026-07-01 | **Status:** DESIGN (this is future item #12: one engine + per-holon adapters)
**Source:** reverse-engineering of pull.py + push.py + ferryman-rules.md, session 2026-07-01
**Answers:** "If I had a completely new brain and wanted to hook up an app to my Claude, how does the Ferryman adapt? Do we ship plugins, or can it adapt on its own?"

---

## The one-sentence answer

The Ferryman splits cleanly into a **generic engine** (already ~built) and a **per-app adapter** (today hardcoded into pull.py/push.py as PF App assumptions). A new API can be hooked up if it meets a small **API-side contract**, and the adapter itself is mostly **auto-derivable by an agent reading the API's discovery/OpenAPI surface** — except for a short list of *semantic* decisions that always need a human or an agent-written rules file. So the model is: **the Ferryman writes its own plugin on first contact, then a human approves the semantic half.**

---

## 1. What is already generic (the engine)

These survive pointing at any API unchanged:

- **Mirror-diff loop:** list-with-updatedAt → diff against ids read out of mirrored files → fetch changed → deterministic overwrite. Identity lives INSIDE the file (rename-safe), never in the filename.
- **Idempotency:** run twice = same state.
- **STATUS/dry-run-first** on both directions (pull STATUS writes nothing; push defaults to /validate).
- **Two-file mirror shape:** opaque body (.txt/.md) + structured metadata (.json).
- **Snapshot pattern** for list resources without updatedAt (full overwrite + .cache/ raw response as the diff baseline).
- **Volume guard + backlog file** for bounded runs.
- **Append-only audit log** (context/log.md lines) as the change manifest the dispatcher consumes.
- **Dedup delegation:** id-less creates trigger SERVER-side dedup which flags (possible_duplicate) and never auto-merges.
- **Error discipline:** never fake a pull on auth/network failure.

## 2. What is hardcoded today (= what an adapter must supply)

Every one of these is a PF-App-specific assumption baked into pull.py/push.py:

1. Base URL (`https://app.prospectforge.us/api/v1`)
2. Token source (`PF App API.txt` line 1, brain root) + Bearer scheme
3. Local paths: holon dir (`pf-app-holon/`), transcripts out dir, `.cache/`, log target
4. Resource map: list endpoint per resource (incl. the `/transcripts/tags` misnaming quirk), detail endpoints, snapshot endpoints (`/profile/me`, `/tasks`, `/contacts`, `/projects`, `/presets`, `/context-documents`)
5. Response envelope keys (`data.transcripts`, `data.transcript or data`, `contextDocuments`)
6. Field names/semantics: `id`, `updatedAt`, `body`, `title`, `date`, `participants`, `conversationType`, `folders[]`, `aiSummary`, `keyInsights`
7. Slug recipe: `<first-non-self-participant>-<type>-<date>` with the inhabitant's name configured as self, plus the Correction #28 `pf-app-` collision prefix
8. Push payload contract: field names, `source` enum (otter|zoom|manual, `manual` forced), conversationType vocabulary, the Interviews folder UUID burned into push.py
9. Push candidacy heuristics: stopword list, INTERNAL people names, skip regex, filename-derived title/date/type
10. Validate-then-commit path pair (`/import/validate` vs `/import`)
11. Markdown-with-sections mapping (`## Summary`→aiSummary etc.) — documented in ferryman-rules.md, not yet in code
12. Upsert semantics (id→upsert, no-id→create+dedup, last-write-wins by updatedAt)
13. Read/write capability matrix (which resources Ferryman is ALLOWED to write) — lives only in prose

## 3. API-side contract — what the OTHER side must expose

For the Ferryman to adapt to a new app, the app's API needs, per resource:

**Required (hard floor):**
- **List endpoint** returning `[{id, updatedAt, ...}]` — a stable unique id + a monotone ISO-8601 updatedAt IS the entire diff engine. No updatedAt → that resource degrades to snapshot-diff mode.
- **Get-by-id** returning the full record, with a designated body field separable from metadata.
- **Header-injectable auth** (Bearer or equivalent).

**Required for push (write lane):**
- **Import/upsert endpoint** that (a) upserts when id supplied, (b) runs server-side dedup on id-less creates and returns a possible-duplicate flag rather than silently merging, (c) has a validate sibling (or `?dryRun=1`).
- **Read-what-you-wrote symmetry:** every field the import accepts must come back on the read endpoint (PF App currently violates this with `contentKind` — known follow-up).

**Required for auto-adaptation (this is the key one):**
- **A discovery surface:** either a `GET /api/v1` root that describes callable endpoints (PF App has `callableByYou`) or an OpenAPI spec. This is what lets an agent derive the adapter instead of a human writing it.

**Nice-to-have:** changefeed endpoint (PF App now has `/changefeed` — live-verified 2026-07-01), scope-tiered tokens, approval queues on writes, pagination declared in the spec (the current engine does NOT paginate — a paginated list would silently mirror page 1 only until fixed).

## 4. Adapter file spec — what a per-holon plugin declares

One machine-readable file per holon (proposal: `<holon>/ferryman-adapter.json` — the generalization of today's prose ferryman-rules.md):

```json
{
  "app": "pf-app",
  "base_url": "https://app.prospectforge.us/api/v1",
  "auth": { "scheme": "bearer", "token_file": "PF App API.txt", "line": 1 },
  "holon_dir": "pf-app-holon",
  "log_target": "context/log.md",
  "discovery": { "path": "/", "trust": "live-over-cache" },
  "resources": {
    "transcripts": {
      "kind": "primary",
      "list": "/transcripts/tags", "detail": "/transcripts/{id}",
      "envelope": { "list": "transcripts", "detail": "transcript|<root>" },
      "fields": { "id": "id", "updated": "updatedAt", "body": "body",
                   "title": "title", "date": "date", "people": "participants" },
      "writable": true,
      "push": {
        "validate": "/transcripts/import/validate", "commit": "/transcripts/import",
        "upsert_by_id": true, "dedup_on_create": "server-flags-never-merges",
        "enums": { "source": ["otter", "zoom", "manual"] },
        "markdown_sections": { "## Summary": "aiSummary", "## Action Items": "actionItems[]" }
      },
      "slug": { "recipe": "first-other-participant + type + date",
                 "self_names": ["<your-first-name>", "<your-last-name>"], "collision_prefix": "pf-app-" }
    },
    "tasks":  { "kind": "snapshot", "list": "/tasks", "writable": false },
    "contacts": { "kind": "snapshot", "list": "/contacts", "writable": false }
  },
  "guards": { "new_per_run": 12, "backlog": "transcripts/pull-backlog.md" }
}
```

Engine reads the adapter; NOTHING app-specific stays in engine code.

## 5. Auto-discoverable vs always-human

**An agent CAN derive from discovery/OpenAPI alone:** base URL, paths, methods, auth scheme, envelope keys, field names, presence of id/updatedAt, required enums, validate endpoints, pagination style.

**Always needs a human/agent-WRITTEN semantic layer (the "plugin" half):**
- Which resource is the **primary** (mirrored, body-bearing, dispatcher-firing) thing vs a snapshot
- Which field is the opaque body
- Slug recipe + who "self" is
- The **capability matrix** (writable yes/no) — this is GOVERNANCE, not schema. The PF API physically has task/profile write endpoints; the Ferryman deliberately never calls them. A schema can't tell you that.
- Markdown-section semantics, dedup stopwords, "already present" heuristics

**So: plugins yes, but self-writing plugins.** First-contact flow: agent hits discovery → drafts `ferryman-adapter.json` with everything in the auto column filled → presents the semantic-layer questions to the user as a short checklist ("which resource is primary? what may I write? who is self?") → human approves → engine runs STATUS as smoke test → adapter is live. New app onboarding becomes a ~10-minute review instead of a build.

## 6. Migration path from today

1. **#12a — extract the adapter:** move the 13 hardcoded items from pull.py/push.py into `pf-app-holon/ferryman-adapter.json`; engine becomes `ferryman.py <adapter> [status|pull|push]`. Behavior identical, files identical. This is a pure refactor and the single highest-leverage step.
2. **#12b — harden the engine** for generality: pagination support, declared timestamp format, retry/backoff, envelope from adapter not guessing.
3. **#12c — first-contact wizard:** the discovery→draft-adapter→checklist flow above, as a skill (`/ferryman-adopt <base-url>`).
4. **#12d — frontmatter-first push:** stop deriving push payloads from FILENAMES; read title/date/type/participants from file frontmatter, fall back to filename regex. Required before any second app.

## 7. Known risks to carry into the build

- String-compared `updatedAt` assumes ISO-8601; declare format per adapter.
- No pagination (silent page-1-only mirror on paginated APIs).
- Some hosts' bot protection blocks curl/PowerShell; engine stays Python urllib but can't assume every host tolerates it.
- Filename-collision handling (the collision prefix) belongs in the adapter, not the engine — globally-unique leaf filenames are the house hygiene rule.
- ferryman-rules.md prose (capability matrix, markdown mapping, v2 peer-processor rules) must become adapter fields or it gets lost in generalization.
