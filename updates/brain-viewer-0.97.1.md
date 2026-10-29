# Brain Viewer 0.97.1 (2026-10-29)

The Manual's chapter list sits inside its card. The list on the left of the Manual has the same margin inside its frame as the other cards, so the first chapter and the line under the list no longer touch the frame; a long list scrolls inside the card and the card stops above the notepad press. On a phone, Contents unfolds with the same margins.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
