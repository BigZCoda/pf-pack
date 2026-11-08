# Brain Viewer 0.108.1 (2026-11-07)

Starting a project works again, and leads get their own fold on People. The ledger tool now accepts the labels and roles the project tool writes (the step and conversation labels; the roles principal, daily user, IT and tester), so a new project's four steps are filed instead of leaving an empty list, and a project can put questions to its people by role. The glossary gains Project step and Planned conversation. On People, a Leads fold below Candidates holds every card filed as a lead.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
