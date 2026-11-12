# Brain Viewer 0.121.0 (2026-11-12)

The guide to your brain now comes with the viewer: a start page, a day with your brain with what to say to Claude at each point, your brain part by part, and a short presentation of what it can do. Today opens it from one line near the top until you press got it, and from How your brain works at the foot of the page after that. Also since 0.114.0: in a Forge drawing, lines no longer pass through cells they do not connect and words no longer sit on each other; dropping an Output on a cell selects it; and the pages for a second agent working beside Claude, drawn only on a computer set up for one.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
