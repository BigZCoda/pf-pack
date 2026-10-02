#!/usr/bin/env python
"""project.py -- the mechanical half of the mentee-project skill: a project's folder, ledger, step tasks and report line.

The thinking half is the four prompts in prompts/, run by Claude per mentee-project-skill.md. This script does only the
parts that must come out the same every time: where the files go, which ledger items exist, which step is open, and the
one log line per run that shows the framework is being used. Every ledger write goes through skills/brain-tasks/tasks.py
and every log line through skills/brain-log/log.py; neither tool takes a date, so no date is ever typed.

USAGE (from the brain root; python3 on a Mac)
  python skills/mentee-project/project.py start  --name "Danger Coffee CPG dashboard" [--slug danger-coffee-dashboard]
  python skills/mentee-project/project.py status <slug>
  python skills/mentee-project/project.py finish <slug> <step> [--partial] [--status PASS|ITERATE|DRAFT|PARTIAL|COMPLETE]
  python skills/mentee-project/project.py conversation <slug> --who "Jane Doe (IT)"
  python skills/mentee-project/project.py landed <slug> --who "Jane Doe (IT)" --transcript transcripts/<file>
  python skills/mentee-project/project.py ask <slug> --to @it --text "..." [--step confines]
  python skills/mentee-project/project.py log <slug> <step> --text "what this run did" [--action MODIFIED]
Steps, in order: purpose, interviews, confines, outfitter.

WHAT EACH VERB WRITES
  start         projects/<slug>/ with readme.md and interviews.md; the ledger projects/<slug>/<slug>-tasks.md (tasks.py
                init); the four step tasks (purpose open, the other three blocked "after <previous step>"); a row in
                context/holon-registry.json so the Brain Viewer's /projects shows the ledger; one CREATED report line.
  finish        checks the step's result file exists, marks the step task done with the file as its result link, reopens
                the next step, one report line. --partial (a register still waiting on conversations, an Outfitter run
                forced early) keeps the task open, sets its note, and logs MODIFIED.
  conversation  one task per planned conversation, owned by @me, tagged #conversation, keyed so status can count it.
  landed        marks a conversation task done with its transcript as the result link, and adds the link to interviews.md.
  ask           a question on the ledger addressed to the stakeholder who can answer it (@principal, @daily-user, @it,
                @tester, or their own @name). Never a program staff member.
  log           a report line for a run that changed no ledger state (a gate refusal, a re-run).
  status        the four steps, the conversations landed out of planned, the open questions. Writes nothing.

THE REPORTER. Every verb that writes appends one line to context/log.md as agent `mentee-project`, naming the project and
the step ("<slug>: purpose written"). The PF App is NOT written: this brain's ferryman push.py sends transcripts and has
no task route, so the log line is the record (see readme.md). The token file is only checked for existence, never read.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.environ.get("BRAIN_ROOT") or os.path.dirname(os.path.dirname(HERE))
TASKS_PY = os.path.join(BRAIN, "skills", "brain-tasks", "tasks.py")
LOG_PY = os.path.join(BRAIN, "skills", "brain-log", "log.py")
REGISTRY = os.path.join(BRAIN, "context", "holon-registry.json")
TOKEN_FILE = os.path.join(BRAIN, "PF App API.txt")   # where this brain's ferryman push.py looks; existence only
AGENT = "mentee-project"

STEPS = ["purpose", "interviews", "confines", "outfitter"]
STEP_TEXT = {
    "purpose": "Purpose: write the draft purpose and run the purpose check",
    "interviews": "Interviews: plan who to talk to and file one task per conversation",
    "confines": "Confines: build the constraint register from the landed transcripts",
    "outfitter": "Outfitter: pick the tech stack once the conversations have landed",
}
STEP_FILE = {
    "purpose": "{slug}-purpose.md",
    "interviews": "{slug}-interview-plan.md",
    "confines": "{slug}-constraint-register.md",
    "outfitter": "{slug}-stack.md",
}
STEP_PROMPT = {
    "purpose": "skills/mentee-project/prompts/mentee-project-purpose-prompt.md",
    "interviews": "skills/mentee-project/prompts/mentee-project-interviews-prompt.md",
    "confines": "skills/mentee-project/prompts/mentee-project-confines-prompt.md",
    "outfitter": "skills/mentee-project/prompts/mentee-project-outfitter-prompt.md",
}
STEP_DONE_PHRASE = {
    "purpose": "purpose written",
    "interviews": "interview plan written",
    "confines": "constraint register written",
    "outfitter": "stack picked",
}


class Fail(Exception):
    pass


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    if not s:
        raise Fail("the project name has no letters or digits to make a folder name from")
    return s[:60].strip("-")


def rel_ledger(slug):
    return "projects/%s/%s-tasks.md" % (slug, slug)


def rel_dir(slug):
    return "projects/%s" % slug


def key_for(slug, *parts):
    return ":".join(["mentee-project", slug] + [re.sub(r"[^A-Za-z0-9_.-]+", "-", p).strip("-").lower() for p in parts])


def env():
    e = dict(os.environ, BRAIN_ROOT=BRAIN, PYTHONIOENCODING="utf-8")
    return e


def run(script, args):
    r = subprocess.run([sys.executable, script] + args, cwd=BRAIN, env=env(), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0:
        raise Fail("%s %s failed: %s" % (os.path.basename(script), args[0], (r.stderr or r.stdout).strip()))
    return r.stdout.strip()


def tasks(*args):
    return run(TASKS_PY, list(args) + ["--agent", AGENT])


def items_by_key(slug, key):
    out = run(TASKS_PY, ["list", "--file", rel_ledger(slug), "--key", key, "--json"])
    data = json.loads(out)
    return data[0].get("items", []) if data else []


def all_items(slug):
    out = run(TASKS_PY, ["list", "--file", rel_ledger(slug), "--json"])
    data = json.loads(out)
    return data[0].get("items", []) if data else []


def step_item(slug, step):
    hits = items_by_key(slug, key_for(slug, step))
    if not hits:
        raise Fail("no %s task on %s (was the project started with project.py start?)" % (step, rel_ledger(slug)))
    return hits[0]


def need_project(slug):
    if not os.path.isfile(os.path.join(BRAIN, rel_ledger(slug).replace("/", os.sep))):
        raise Fail("no project %r: %s does not exist (start it with: project.py start --name \"...\")" % (slug, rel_ledger(slug)))


def app_line():
    if not os.path.isfile(TOKEN_FILE):
        return "PF App: no token file in this brain; the log line is the record."
    return "PF App: not written; this brain's ferryman push.py sends transcripts only and has no task route, so the log line is the record."


def report(slug, step, action, phrase):
    """THE REPORTER: one line in context/log.md per run, through log.py (the clock is read there, never here)."""
    target = "%s/%s" % (rel_dir(slug), STEP_FILE[step].format(slug=slug)) if step in STEP_FILE else rel_ledger(slug)
    text = "%s -- %s: %s" % (target, slug, phrase)
    run(LOG_PY, ["--append", "--agent", AGENT, "--action", action, "--text", text])
    print("logged: %s %s" % (action, text))
    print(app_line())


# ---------------- verbs ----------------

README = """# {name}

**What's in here.** The working folder for this project: its ledger, one file per framework step as each is written, and the
list of conversations with links to their transcripts. Started with the mentee-project skill
([[skills/mentee-project/mentee-project-skill.md]]).
**Authoritative or derivative.** Authoritative for this project's purpose, plan, constraints and stack. Transcripts stay in
`transcripts/` and are linked from [[{slug}-interviews.md]], never copied here.
**When to read.** Any work on this project. The ledger ([[{slug}-tasks.md]]) shows which step is open.
**What does NOT belong.** Copies of transcripts, keys or tokens, other projects' files.

## Steps
| Step | Result file | Prompt |
|---|---|---|
| Purpose | [[{slug}-purpose.md]] | [[skills/mentee-project/prompts/mentee-project-purpose-prompt.md]] |
| Interviews | [[{slug}-interview-plan.md]] | [[skills/mentee-project/prompts/mentee-project-interviews-prompt.md]] |
| Confines | [[{slug}-constraint-register.md]] | [[skills/mentee-project/prompts/mentee-project-confines-prompt.md]] |
| Outfitter | [[{slug}-stack.md]] | [[skills/mentee-project/prompts/mentee-project-outfitter-prompt.md]] |

## Pointers
(Things this project uses that live outside the brain: repositories, shared drives, dashboards. One line each: where, what for.)
"""

INTERVIEWS = """# {name}: conversations

One line per planned conversation, filled in by the interview step and by `project.py landed` as each transcript arrives.
The transcript itself stays in `transcripts/`; this file only links it.

"""


def add_registry_row(slug, name):
    row = {"id": slug, "name": name, "type": "family", "path": rel_dir(slug) + "/",
           "description": "Project started with the mentee-project skill; its ledger shows the open framework step.",
           "tasks": rel_ledger(slug), "sharing": "private", "stamped": False, "parent": None, "children": []}
    if os.path.isfile(REGISTRY):
        with open(REGISTRY, encoding="utf-8-sig") as f:
            reg = json.load(f)
    else:
        reg = {"_schema": "holon-registry v1",
               "_note": "The folders and files this brain treats as units of work. The Brain Viewer's /projects renders the ledger a row names in its `tasks` field.",
               "holons": []}
    hol = reg.setdefault("holons", [])
    if any(h.get("id") == slug for h in hol):
        return "registry already has %s" % slug
    hol.append(row)
    with open(REGISTRY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return "registry row added: %s" % slug


def cmd_start(a):
    name = " ".join((a.name or "").split())
    if not name:
        raise Fail("--name is required")
    slug = slugify(a.slug or name)
    d = os.path.join(BRAIN, rel_dir(slug).replace("/", os.sep))
    if os.path.exists(os.path.join(BRAIN, rel_ledger(slug).replace("/", os.sep))):
        raise Fail("project %s already exists (%s); run: project.py status %s" % (slug, rel_ledger(slug), slug))
    os.makedirs(d, exist_ok=True)
    for fn, body in (("readme.md", README), ("%s-interviews.md" % slug, INTERVIEWS)):
        p = os.path.join(d, fn)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(body.format(name=name, slug=slug))
    reg = add_registry_row(slug, name)   # first, so init can name the ledger after its holon id
    run(TASKS_PY, ["init", "--project", slug, "--name", name, "--agent", AGENT])
    ids = {}
    for s in STEPS:
        out = tasks("add", "--file", rel_ledger(slug), "--owner", "@me", "--milestone", "Framework",
                    "--text", STEP_TEXT[s], "--key", key_for(slug, s), "--tag", "step",
                    "--link", STEP_PROMPT[s])
        ids[s] = out.split()[0]
    for prev, s in zip(STEPS, STEPS[1:]):
        tasks("block", "--file", rel_ledger(slug), ids[s], "--reason", "after %s" % prev)
    print("created %s/ (readme.md, %s-interviews.md) and %s" % (rel_dir(slug), slug, rel_ledger(slug)))
    print("steps: " + ", ".join("%s %s" % (ids[s], s) for s in STEPS) + " -- purpose is open")
    print(reg)
    report(slug, None, "CREATED", "project started, purpose step open")
    print("slug: %s" % slug)


def cmd_finish(a):
    slug, step = a.slug, a.step
    need_project(slug)
    result = "%s/%s" % (rel_dir(slug), STEP_FILE[step].format(slug=slug))
    if not os.path.isfile(os.path.join(BRAIN, result.replace("/", os.sep))):
        raise Fail("%s does not exist yet: write the step's result there first, then finish it" % result)
    it = step_item(slug, step)
    status = (" (%s)" % a.status.upper()) if a.status else ""
    if a.partial:
        tasks("note", "--file", rel_ledger(slug), it["id"], "--note", "%s on file%s; re-run when more lands" % (result.split("/")[-1], status))
        tasks("link", "--file", rel_ledger(slug), it["id"], "--link", result)
        report(slug, step, "MODIFIED", "%s (partial%s)" % (STEP_DONE_PHRASE[step], (", " + a.status.upper()) if a.status and a.status.upper() != "PARTIAL" else ""))
        return
    was_done = it.get("mark") == "x"
    if was_done:
        tasks("link", "--file", rel_ledger(slug), it["id"], "--link", result)
    else:
        tasks("done", "--file", rel_ledger(slug), it["id"], "--link", result)
    i = STEPS.index(step)
    if i + 1 < len(STEPS):
        nxt = step_item(slug, STEPS[i + 1])
        if nxt.get("mark") == "-":
            tasks("reopen", "--file", rel_ledger(slug), nxt["id"])
            print("next: %s %s is open" % (nxt["id"], STEPS[i + 1]))
        else:
            print("next: %s %s was already %s" % (nxt["id"], STEPS[i + 1], nxt.get("state")))
    else:
        print("the four framework steps are done for %s" % slug)
    report(slug, step, "MODIFIED" if was_done else "CREATED", "%s%s%s" % (STEP_DONE_PHRASE[step], status, " (re-run)" if was_done else ""))


def cmd_conversation(a):
    need_project(slug := a.slug)
    who = " ".join((a.who or "").split())
    if not who:
        raise Fail("--who is required, e.g. \"Jane Doe (IT)\"")
    k = key_for(slug, "conv", who)
    if items_by_key(slug, k):
        raise Fail("a conversation task for %r already exists" % who)
    out = tasks("add", "--file", rel_ledger(slug), "--owner", "@me", "--milestone", "Conversations",
                "--text", "Talk to %s, record it, save the transcript to transcripts/" % who,
                "--key", k, "--tag", "conversation")
    print(out)
    report(slug, "interviews", "MODIFIED", "conversation planned with %s" % who)


def cmd_landed(a):
    need_project(slug := a.slug)
    who = " ".join((a.who or "").split())
    tr = (a.transcript or "").replace("\\", "/")
    if not os.path.isfile(os.path.join(BRAIN, tr.replace("/", os.sep))):
        raise Fail("no transcript at %s" % tr)
    hits = items_by_key(slug, key_for(slug, "conv", who))
    if not hits:
        raise Fail("no conversation task for %r (file it with: project.py conversation %s --who \"%s\")" % (who, slug, who))
    tasks("done", "--file", rel_ledger(slug), hits[0]["id"], "--link", tr)
    p = os.path.join(BRAIN, rel_dir(slug).replace("/", os.sep), "%s-interviews.md" % slug)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write("- %s: [[%s]]\n" % (who, tr))
    report(slug, "interviews", "MODIFIED", "conversation landed with %s" % who)


def cmd_ask(a):
    need_project(slug := a.slug)
    to = (a.to or "").strip()
    if not re.match(r"^@?[\w.-]+$", to):
        raise Fail("--to is one @name or role (@principal, @daily-user, @it, @tester, @jane-doe)")
    args = ["ask", "--file", rel_ledger(slug), "--from", "@claude", "--to", to, "--text", a.text]
    if a.step:
        args += ["--tag", "step-%s" % a.step]
    out = tasks(*args)
    print(out)
    report(slug, a.step, "MODIFIED", "question filed for %s" % (to if to.startswith("@") else "@" + to))


def cmd_log(a):
    need_project(a.slug)
    report(a.slug, a.step, a.action, " ".join(a.text.split()))


def cmd_status(a):
    need_project(slug := a.slug)
    items = all_items(slug)
    by_key = {i.get("key"): i for i in items if i.get("key")}
    print("%s -- %s" % (slug, rel_ledger(slug)))
    for s in STEPS:
        it = by_key.get(key_for(slug, s))
        f = "%s/%s" % (rel_dir(slug), STEP_FILE[s].format(slug=slug))
        has = os.path.isfile(os.path.join(BRAIN, f.replace("/", os.sep)))
        print("  %-10s %-8s %s %s" % (s, it.get("state") if it else "missing", it.get("id") if it else "", "-> " + f if has else ""))
    conv = [i for i in items if "conversation" in (i.get("tags") or [])]
    print("  conversations: %d of %d landed" % (sum(1 for i in conv if i.get("mark") == "x"), len(conv)))
    qs = [i for i in items if i.get("kind") == "question" and i.get("mark") == "?"]
    for q in qs:
        print("  open question %s -> %s: %s" % (q["id"], q.get("to"), q.get("text")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("start"); p.add_argument("--name", required=True); p.add_argument("--slug")
    p = sub.add_parser("status"); p.add_argument("slug")
    p = sub.add_parser("finish"); p.add_argument("slug"); p.add_argument("step", choices=STEPS)
    p.add_argument("--partial", action="store_true"); p.add_argument("--status")
    p = sub.add_parser("conversation"); p.add_argument("slug"); p.add_argument("--who", required=True)
    p = sub.add_parser("landed"); p.add_argument("slug"); p.add_argument("--who", required=True); p.add_argument("--transcript", required=True)
    p = sub.add_parser("ask"); p.add_argument("slug"); p.add_argument("--to", required=True); p.add_argument("--text", required=True)
    p.add_argument("--step", choices=STEPS)
    p = sub.add_parser("log"); p.add_argument("slug"); p.add_argument("step", choices=STEPS)
    p.add_argument("--text", required=True); p.add_argument("--action", default="MODIFIED", choices=["CREATED", "MODIFIED"])
    a = ap.parse_args(argv)
    try:
        {"start": cmd_start, "status": cmd_status, "finish": cmd_finish, "conversation": cmd_conversation,
         "landed": cmd_landed, "ask": cmd_ask, "log": cmd_log}[a.verb](a)
    except Fail as e:
        sys.exit("project.py: %s" % e)


if __name__ == "__main__":
    main()
