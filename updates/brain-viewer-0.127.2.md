# Brain Viewer 0.127.2 (2026-11-13)

Why: the guide that came with your viewer explained its buttons and left out what your brain is for, and the viewer kept running after you closed Claude with no plain way to stop it. What changes for you: the guide (the line near the top of Today) now starts with what your brain is for and how it helps you move forward, then a day with it, then how it holds your work. To close the viewer, open Settings and press Stop the viewer; it comes back the next time you start Claude in your brain. Also: on Today's timeline, two calls close together no longer write over each other; on a card a link to a thread, a task or a page sits in an oval while a file stays underlined text; and the Forge's list opens in a few seconds however many drawings you have. After the update, reload any viewer page you have open.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
