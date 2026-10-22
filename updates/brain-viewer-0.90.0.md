# Brain Viewer 0.90.0 (2026-10-22)

Pictures in a note, a one-line header on the phone, a thread kept to its own pieces, and for a team copy: the From band reads the newer what's-new page (what became of your requests, the sentences on what arrived, each file by its title) and the send press brings in GitHub before it pushes, saying Not sent and why when the newest export clashes with a change committed in the folder.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
