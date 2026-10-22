# Brain Viewer 0.91.0 (2026-10-22)

Changed since you last looked: a band at the top of Today, under the pick, whenever the viewer changed since you last looked (the newest entry's lines, a press into the full page, a Seen press), and the same band naming what landed overnight (a run's delivery note, the night review's audit, the engineer's run); a permanent what's-new link under the header's more fold with a dot while unread.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
