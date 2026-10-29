# Brain Viewer 0.98.0 (2026-10-29)

A task or a thread can be put in front of the person this brain shares a copy with. A task on a list their copy holds carries share with <member> in its presses on Today, the thread page and the workspace, and a thread page whose file goes to them carries the same press under its name. The press puts it on the From band of their Today, under Shared with you, at their next sync: the task read only as it stands on their copy of its list, the thread as one press to its page. Once shared, the card says so with stop sharing. Nothing new crosses: a task on a list that stays home, a task marked private, and a thread whose file is held back draw no press. The owner's sync now runs only from the brain the viewer is installed in. Also in this version (0.97.1): the Manual's chapter list sits inside its card.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
