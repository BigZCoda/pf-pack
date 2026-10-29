# Brain Viewer 0.96.0 (2026-10-28)

A member's copy becomes her own brain sharing with the owner's: a save is a save, a file from the owner's brain is shared both ways, a file of hers is hers until Share. Also: a press lands on what it shows; the glossary is a chapter of the manual; From Claude without the rating cards; the chat page without the bubbles.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
