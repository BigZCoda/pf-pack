# Brain Viewer 0.59.0 (2026-10-02)

The home board's horizon milestones and the flow ring now read from files in your brain (context/horizon.json and context/flow.json) instead of being written into the widgets; with no file they say so and draw nothing. Project labels and order, hidden people and the studio prompt are now viewer settings in viewer/settings.json. No shipped file quotes the owner or carries a personal line, and the release gate fails on either from now on. The call page's word-highlight pattern is fixed. The picture viewer zooms. Today shows one queue of what is yours across every ledger. Cards no longer show raw source or key tags. To update, say check for updates in Claude Code and accept the brain-viewer component.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
