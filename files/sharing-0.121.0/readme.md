# skills/sharing/ : sharing between brains (the register, round one)

**Created 2026-11-09** on the owner's yes that day to the sharing design: one sharing system for any two people who use the viewer, and for team brains, easy to make or attach, with each brain knowing what is shared with whom. The design, its thread and its ledger item live in the maintainer brain.

This is the spec of the sharing component. It is built in five rounds; this file says what exists after each, and is amended at the end of every round.

## The words

- **Shared space:** a place two or more people hold together. Two people are a **pair**; three or more are a **team brain**. One mechanism.
- **Carrier:** what moves a space's content between its people's computers. `team-copy` is the team copy on GitHub (`skills/team-brain/`, `skills/team-sync/`), the only carrier in round one. `service` is the database service (Supabase), from round two.
- What crosses is a **render**; one crossing is a **delivery**, stamped with its **provenance**; a card section arrives through the **proposal gate**. These are the brain's frozen words and nothing here renames them.

## What is in here

| file | what | authority |
|---|---|---|
| `share.py` | the register: who this brain shares with and what. Read by the viewer, the ledger tool, the session recap and any agent | authoritative for the register |
| `service.py` | the service adapter: `LocalService` (a folder standing in for the service) and `SupabaseService` (HTTPS), one interface | authoritative for how the service is spoken to |
| `gate.py` | what never crosses into a space, and the cleaning of what does; `KEY_FILES`, the one list of key files | authoritative for the gate |
| `engine.py` | the sync: sends what this brain shares, takes in what others share, carries what each person did back to the original | authoritative for the sync |
| `kinds.py` | the kinds beyond a task and a question: files, threads, drawings, card sections, messages, whole projects | authoritative for those kinds |
| `mailbox.py` | a mailbox per person and one send to many, for a brain that runs a program | authoritative for mailboxes |
| `move_copy.py` | the move of a member's team copy onto the service: it prints a plan and changes nothing; its apply step has never been run | tool |
| `service.json` | where the service is (public values only; empty means not set up) | config |
| `sharing-service.test.py` | round two's test: three scratch brains, a stand-in service, a stand-in HTTP server | test |
| `readme.md` | this spec | authoritative |

Shipped with the viewer (a dependency in `skills/brain-viewer/release.py`), so it travels under the viewer's version to every brain.

## The register (round one, viewer 0.109.0)

Every space this brain is attached to is one folder under `shared/`:

```
shared/
  readme.md            what the folder is
  .contract.json       nothing private is ever written into a space
  riley/
    space.json         the stamp, contract shared-space/1
    readme.md          who sees what is in this folder
```

**The stamp, `space.json`** (contract `shared-space/1`):

| key | what |
|---|---|
| `contract` | `shared-space/1` |
| `name` | the space's short name, the same as its folder: the partner's for a pair, the team's for a team brain |
| `label` | the name a person reads |
| `kind` | `pair` or `team` |
| `me` | this brain's own person, bare (`sam`) |
| `members` | each `{name, card, role}`: the card is the people card's slug in THIS brain, or null; role `maker` or `member` |
| `carrier` | `team-copy` or `service` |
| `carrier_member` | for `team-copy`: the member name `skills/team-brain` knows (`riley`) |
| `sent` | the brain-relative file that lists what this brain put in front of the space. For `team-copy` it is the file the export already reads, `skills/team-brain/shared-with-<member>.json`, so nothing is kept twice |
| `page` | the viewer address that shows what the space holds |
| `joined`, `state` | when this brain attached; `attached` |

A brain that has a team copy and no `shared/` folder yet still answers: `share.py` derives the space from `skills/team-brain/status.json` and marks it `registered: false`. `share.py init` writes it down (the folder, the stamp, the readme, and the registry rows `shared` and `shared-<name>`, type `space`).

**The registry.** `context/holon-registry.json` gains the type `space`. A space's row keeps `sharing: private`: what crosses into a space is decided by the Share press and the gate, never by a tier. The export therefore never sends `shared/` anywhere.

## The computed facet `shared`

Who a ledger item is shared with is a **computed** facet (frozen vocabulary: population mode computed). It is read from the register at every read and is never written on the item's line, because the line itself crosses: written there, it would tell one partner who else an item is shared with. `share.py shared_index()` is the read; `tasks.py list --json` carries `shared` and `shared_with` on every item, the text list shows `shared:<names>`, and `list --shared-with <name>` filters ([[skills/brain-tasks/readme.md]], The facets).

## Using it

```
python skills/sharing/share.py list        # every space this brain is attached to
python skills/sharing/share.py status      # one line: who, what is on their Today, when it last went (the recap's line)
python skills/sharing/share.py shared      # every task and thread shared, and with whom
python skills/sharing/share.py verify      # CLEAN, or each discrepancy named (exit 1)
python skills/sharing/share.py init        # write down a space found unregistered
```

`--json` on `list`, `status` and `shared`. `--brain <folder>` or `BRAIN_ROOT` points a run at another brain.

**The verifier** (`verify`) checks: every stamp reads and carries the contract; a space's name is its folder's; it has two or more members and this brain's own person among them; its readme exists; its registry row exists; a team-copy space's member is the one `skills/team-brain/status.json` names; every shared task is still on its list and every shared thread is still a file; a space a team copy implies has been written down.

## In the viewer (0.109.0)

- **The Share press** on a task and under a thread's name reads who a press can go to from `GET /api/shared/items` (`partners`, one view per person or team). One person: `share with <name>`, one press, as since 0.98.0. Two or more: `share`, which opens the people in place, each a press of their own, and `close` folds them back. `POST /api/shared/item` takes `with`, the space's name.
- **Settings, Sharing:** who this brain shares with, one row each (`GET /api/sharing/state`): the name as a link to the card, what is on their Today from here, when it last went, and a link to the page that shows what they get.
- A space takes a press only when its carrier can move it. In round one that is the team copy; a space carried by the service is listed in Settings and takes no press until round two.
- Tests: `skills/brain-viewer/sharing.test.py`, `skills/brain-tasks/tasks-shared.test.py`.

## Round two: the service and a second brain (built 2026-11-09, package A)

Everything below the viewer: pure Python, standard library only. The viewer's pages and presses come after.

**Where things live.** The service's address is `service.json`, or a brain's own `sharing_service` setting in `viewer/settings.json` (`{"carrier": "local", "root": "<folder>"}` selects the stand-in). The sign-in is `viewer/sharing-signin.json`: a key file, never printed, logged or sent anywhere but the service. A space the service carries is `shared/<name>/` with:

| file | what |
|---|---|
| `space.json` | the stamp, with `carrier: service` and the new keys below |
| `sent.json` | what this brain shared into it: `{items: [{project, ledger, id, at, thing}], threads: []}` |
| `<name>-tasks.md` | the space's own list, a real ledger (`tasks.py init`), the `tasks` of registry row `shared-<name>`: what the others shared, and what was made in the space |
| `.sync/` | `state.json` (per thing its version, the local item it maps to, the body last applied) and `lock`; never sent, kept out of git by `shared/.gitignore` |

**The stamp's new keys** (carrier `service`): `space_id`, `list`, `state` (`attached` or `detached`), `left` (a date, once detached), and on each member `display`, `user_id`, `left`, and `invited` while the invitation is open.

**The verbs** (`share.py`, `--json` on each, none prints a token):

```
signin --email E [--code C]       send the code; then sign in with it
signout | whoami
invite --email E --name N [--card C] [--team T]   a pair space and its invitation (the code is shown once)
invites | accept [--invite ID | --code C]
detach --space S                  leave; each side keeps a frozen copy of what the other shared
team --name N --label L           a team brain with this person as its maker
share | takeback --space S --project P --id I
sync [--on-purpose]
client --on | --off [--client NAME --date YYYY-MM-DD]
```

**What crosses.** One task or question at a time, as a render through the gate: its words, steps and note (paths, links and ids read as plain words), its state and days, its choices and answer, the list's short name, and whether it is the reader's to do. Never its id, its list's file, its tags, its people or its links. What the other person does to it (a tick, a reply, done, reopen, an answer) comes back as an act and is applied to the original with their name; done and reopen only on a task that is theirs to do, an answer only to a question asked of them; anything else is refused and their copy is put back at the next sync. A task made in the space belongs to nobody's brain: any member changes it against the version they last saw, and when two people change the same words between syncs one is kept and the other is named to the person, never dropped.

**The gate** refuses a line marked `[private]`, a token or key shape anywhere on it, a list whose registry row says `sharing: employer`, words naming someone on the held-back list (an unreadable list refuses everything), and a list in a personal folder (`sharing_personal`, default `thoughts/` and `questions/`, plus `astrology/`, `characters/`, `profiles/` when they exist) or at the brain root.

**An employer's computer.** Everything a person reads says employer ("My employer owns this computer" in Settings), because the person at the keyboard is a mentee or a client and the page is theirs; the settings keys and the CLI verb keep the older word. `client_computer: true` in `viewer/settings.json` holds only what this brain shares OUT (2026-11-11, T-0022): signing in, accepting, taking in what others share, replies, answers, messages and tasks made in a space all run. Every share verb refuses with one line until `client_agreed` (`{client, date}`) is set; with both, a Share press shares, and later changes to what was shared go on a press (`sync --on-purpose`).

**Mailboxes (2026-11-11, `mailbox.py`).** A mailbox is one small team space between the people who run a program (its admins) and ONE person in it; its short name starts `mailbox-`, so nothing new is needed on the service. Who is an admin is a setting of the brain: `sharing_admin: true`, `sharing_org` (the name the person reads on their side), `sharing_admins` (`[{name, email}]`, the other admins, invited into every mailbox; an admin's brain accepts such an invitation with no press, `auto_join`). `make(brain, email, name)` makes one and invites the person; `boxes(brain)` lists them; `send(brain, kind, ref, to=None)` puts a COPY of a task or a question on each chosen mailbox's own list, the person's to do or to answer (its words pass the gate first; the same send twice adds nothing), and shares a file, a thread or a drawing into each the usual way. `to` is None for every mailbox or a list of space names. The viewer: `POST /api/sharing/mailbox`, `POST /api/sharing/send`, the Mailboxes section in Settings, Send to mailboxes in the Share box. Tests: `sharing-mailbox.test.py`, and `sharing-mailbox-viewer.test.py` in the viewer's folder.

**A copy of someone else's brain does not share through the service.** A folder with `team-brain.json` at its root is a copy (a team member's). The viewer answers 403 with "Sharing is turned on from a person's own brain, not from a copy" on every route under `/api/sharing/` there, lists no spaces and runs no sync (`COPY` in `skills/brain-viewer/serve.py`). The engine itself has no such check: the rule lives in the viewer. Why it was built so: each export rewrites the copy's registry, the member's sync would commit `shared/` into the team repository, and accepting would write a card that flows back to the owner's brain.

**Where tests run (2026-11-11).** On invented stand-in brains in a scratch folder with the stand-in service on disk (`sharing_service: {carrier: local, root}` in each stand-in's settings, `SHARING_OFFLINE=1`), never on a real brain and never against a viewer on 8765 or 8766. A brain whose settings say `real_brain: true` refuses every sharing verb of a test run in one line. On 2026-11-10 a check ran with a real brain as one side: its test person's card rode a team export, and its presses landed in the real answers inbox.

**What holds after the review (2026-11-09).** A reply or an answer passes the gate on the writer's side before it is sent, and again at the home, which refuses one holding a key shape or a private mark and empties its words on the service (`mark_act(..., scrub=True)`). Every name, label and body from the service is cleaned where it arrives; each member's address is the one the service verified (`email` on a stamp member, `from_email` on an invitation, `Email:` on a minimal card). A sign-in is used only at the address it was made at, over https, and no redirect is followed. An act is marked with one of a fixed set of results; when this brain's list cannot be written it is left for the next sync. The sync state is written after every thing and every act, an item made from someone else's thing carries `key: space:<thing id>` so a second try adopts it, and applied act ids are kept so nothing is applied twice. A detach or take back that cannot reach the service changes nothing. A settings file that does not read turns sharing off. Each stamp carries a random `salt` that a thing's key is hashed with. A pair is two particular people: once it has had two, nobody else joins it and a person who left does not come back.

**And after the second review.** The gate never takes back something already shared: a later change it refuses stays here (`held` in the sync state; `status` says "1 change held back") while the other person keeps the earlier words, and only the take back press or the item leaving its list removes a thing. Whose a thing is goes by the service's user id (`for_user`, `home_user` in the body), never a short name. A stamp records `me_user` and is synced only by that sign-in; it is detached only when the person's own membership row says they left (`my_memberships`). A lost sync state is rebuilt from `sent.json`'s thing ids, the `space:<thing id>` key on the list, and the `origin` a thing made in the space carries. A copy is finished before its baseline is recorded, so a half-made copy never sends an act. A join whose answer was lost is finished at the next invites, accept or sync. A card is linked to an existing one only when this side picked it or it holds the member's verified address; otherwise it is named `<name>-<address part>`.

**Not yet.** `SupabaseService` has been tested only against a stand-in server, not a real project.

## Round three: everything else that can be shared (the engine, 2026-11-10)

Built in `kinds.py`; the engine re-exports each name as its own, and those names are what the viewer calls.

| kind | what goes | where it lands on the other computer |
|---|---|---|
| file | a text file (`.md .txt .json .csv .html .css .js .py`, up to 400 KB), cleaned line by line | `shared/<space>/files/` |
| thread | the subject file, its frontmatter less `people`, `match`, `canonical`, `depends`, `progress`, and the open items that link it | `shared/<space>/threads/`, in the space's project |
| drawing | the `.canvas` and its `.forge.json` twin, never rewritten | `shared/<space>/drawings/` |
| card section | one `##` or `###` fold of a people card | a proposal, taken into a card or left |
| message | a few words | `shared/<space>/messages.jsonl` |

**The gate for whole texts** (`gate.render_text`, `render_drawing`, `render_section`) refuses a key file, a key shape, a personal folder, an employer's project, a transcript, a whole people card, a file over 400 KB and anything that is not text; it drops a line marked `[private]`, a `[private]` heading's whole fold and a line naming a held-back person, and cleans the rest as the item gate does. A drawing with a path on this computer anywhere is refused, with the line it is on.

**The other person's edit** comes home as one `edit` act, gated on their side. It is saved under `shared/<space>/proposed/` and asked about on the space's list ("<Name> changed "<title>". Take the change?"); *Take it* merges it onto the original with `git merge-file` against the version last sent, and a clash leaves the original with the proposed file beside it. `set_auto_take` takes a clean merge without asking. A file already on the other computer with other content is never overwritten: the incoming one is written beside it.

**Functions:** `share_file`, `share_thread`, `share_drawing`, `share_card_section`, `take_back_thing`, `proposals`, `take_section`, `leave_section`, `send_message`, `messages`, `mark_read`, `set_auto_take`, `space_view`, and `move_here` from round two. `sent.json` gains `files`, `threads`, `drawings` and `sections`; `status()` rows gain `unread`, `here`, `host_name` and `held`.

**Verbs:** `share-file`, `share-thread`, `share-drawing` (`--path`), `share-section` (`--card --heading`), `takeback-thing` (`--kind --key`), `proposals`, `take-section`, `leave-section` (`--id`), `message` (`--text`), `messages`, `space`, `auto-take` (`--on`/`--off`), `move-here`. Test: `sharing-kinds.test.py`.

## Round four: a whole project into a space, and the team copy's move (the engine, 2026-11-10)

- `share_project(brain, space, project)` -> `{ok, line, counts}` marks the project's registry row `sharing: space:<name>` (its old value kept on the stamp) and shares, through the gate, every open task and question on its list, every subject file whose `project` is it, and every text file under its folder; each check after shares what is new on it. On the other side its items sit under a heading of their own on the space's list. An employer's project is refused. `unshare_project(...)` stops, takes all of it back and puts the row back as it was.
- `move_copy.py plan --member <name> --copy <folder>` reads, and writes nothing: file by file, what a member's team copy holds against what the space would hold of the brain's team-tier projects, every difference named, the last line `CLEAN` or the count. `apply` shares the team-tier projects into the member's space and leaves the copy exactly as it is; it runs only with `--both-present`, with the owner and the member there. It has never been run by a builder. Test: `sharing-project.test.py`, on scratch brains and a scratch copy.

## What never crosses

For a space the service carries, `gate.py` decides (above). For the team copy, unchanged since round one: the team export's gate (`skills/team-brain/export.py`) decides, and the press refuses in one line what stays home (a task marked `[private]`, a token-shaped value, a person who never crosses, a question on a list that stays home). In round two the gate moves into this folder so every brain has it, with one key-file list where there are five copies today.

## The rounds

1. **The picker and the register** (built 2026-11-09, viewer 0.109.0): everything above.
2. **The service, and a second brain:** sign in from Settings, add a share partner, accept, detach; share a task and a question with a second brain; what they do comes back with their name; a space's own list; the gate in this folder; the switch that keeps sharing off on an employer's computer until the employer agrees in writing.
3. **Everything else that can be shared:** a file, a thread, a drawing, a card section through its proposal, a folder; messages per space.
4. **Team brains, and the team copy's move:** three or more people, a whole project into a space, the member's copy moved onto the service with a file-by-file check, its GitHub files kept as well.
5. **Mentees:** the update notice in the viewer, a space between the maintainer and each mentee, the manual's sharing chapter.

Decided by the owner on 2026-11-09: Supabase holds the spaces; on a client's laptop (one owned by the company a mentee works for; the viewer's own words say employer since 11/10) sharing stays off until the client agrees in writing; when two people stop sharing each keeps a frozen copy of what the other shared. Open: whether a space replaces the mailbox repository for mentees, which only sets round five.

## What does NOT belong here

A space's content (it lives in `shared/<name>/` and, from round two, on the service). The team export's tier rules (`skills/team-brain/`). A second copy of the gate once it has moved here. A sign-in, a token or a key: those stay in the viewer's own folder, which never syncs, never exports and never reaches a page.

**Last touched:** 2026-11-09 (round two, package A: the service adapter, the gate, the sync engine, the new verbs and their test) · 2026-11-09 (created with round one: the register, `share.py`, the computed `shared` facet, the Share press naming who, the Sharing group in Settings; viewer 0.109.0). Operated by the viewer, the ledger tool and Claude.
