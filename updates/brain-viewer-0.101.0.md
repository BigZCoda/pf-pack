# Brain Viewer 0.101.0 (2026-10-30)

A link to a file opens the file itself. A web page or a PDF shows framed in the side panel with open in a new tab; a Word file reads as its words, a spreadsheet, a CSV and a slide deck as tables and slides, a folder as its files; a file that is not on this computer says so and offers where it may have gone, and a kind the viewer can't draw offers its download. Every link opens a file the same way: a link on a card, a name in an item's words, a step's open press, the thread page and the Files page. On a phone the side panel is the whole screen. Nothing to do after updating.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
