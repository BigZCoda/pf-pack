# Brain Viewer 0.88.0 (2026-10-21)

0.88.0, on top of 0.87.1 released earlier today. In a team member's copy, Today is back in the menu and opens on the From band, named after the brain's owner: the questions and new files from the owner's side, drawn so the member can act on them where they are, with the answer, done and note presses writing requests that travel back to the owner, and a line after each press saying where the request really is (sent, waiting, landed). The propose box's button reads Send in a copy and says the same.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
