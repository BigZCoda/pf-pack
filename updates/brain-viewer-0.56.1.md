# Brain Viewer 0.56.1 (2026-10-02)

Everything since 0.48.0. Numbered lists count again and a question opens the file it points at (0.48.1). The chat stands alone, pictures drop onto the notepad, and a call's prep shows before its card exists (0.49.0). A card can be tested beside the review page and a rating taken back (0.50.0). Transcript line numbers no longer show anywhere, and the call screen has a must tag (0.50.1); the maps draw the systems not built yet (0.50.2). The image studio can draw on a local graphics card through ComfyUI and redraw a picture you give it (0.51.0, 0.51.1); where ComfyUI is installed is a setting, comfy_dir in viewer/settings.json. A Files page lists every file in the brain in one table (0.52.0). A document link opens in the drawer beside the page on every page (0.53.0), and the Reader shows a document as one page with an outline (0.54.0). Every call to the PF App sends a User-Agent, so the first app read no longer fails with 403. References to tasks and questions read as chips that open a preview in place, and the Questions card has room (0.55.0); three Reader leaks closed (0.55.1). The projects page is one list with the ledgers as filters and what waits on you first, questions with named choices answer with one press, and the ask box is back; the People page opens on this week's calls and who you talk to weekly (0.56.0). Update with python skills/update/install-component.py brain-viewer (or /update); stop a running viewer first.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
