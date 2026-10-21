# Brain Viewer 0.87.1 (2026-10-21)

From 0.68.0 to 0.87.1. Today opens on the day: Up first (the one to three things picked for you), In progress (the projects you are working in), what is new since you last looked, and one list you can finish; a thread is a workspace with the thing in progress first and the progress on the side; Artifacts has a place to press; every opportunity is on one page by stage and a person's card says who they can reach; a survey and a side-by-side choice open on pages of their own; a task carries tickable steps; the words of the ledger are in the glossary; a Sharing page shows a team member's copy as ticks for folders, files and people cards; and in a team copy the People page lists and opens the shared cards, read only. Also: every page measured under a first-paint budget, every press has a way back, old addresses say where things moved, and the viewer no longer carries the owner's brain inside its code.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
