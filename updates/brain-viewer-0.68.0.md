# Brain Viewer 0.68.0 (2026-10-07)

Viewer 0.68.0: Today is the landing page and the one queue; the menu folds; stable question ids so answers flow back into preps; the day drawing derived; the chat picker; the exclusive port bind and all fifteen tests on scratch folders.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
