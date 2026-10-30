# Brain Viewer 0.100.0 (2026-10-30)

The search at the top of every page now finds threads, tasks and questions, and people before files, ranked by how well each one fits, and takes filter words such as thread:, task:, is:open, for:me, in: and since:7d; click into the empty box to see them. Nothing to do after updating.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
