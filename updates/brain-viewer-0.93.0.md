# Brain Viewer 0.93.0 (2026-10-26)

Your answers wait until you send them: a Send press at the bottom right of every page, answers going on their own when you leave the viewer or after five quiet minutes, and a Settings page where the hold is set (0.92.0). The rules for an easy viewer in one place and the first build against them (0.93.0): on a task's steps the box is the only tick and a step that names a place carries an open press; Claude's reply to a note, an answer or a done press is drawn under the item's note apart from your words, the newest first and the older ones folded; on a thread page the other open questions stand under Working on and the next takes the answered one's place; a project's name on the In progress strip opens its own work; the Projects page answers questions and acts on tasks; notes from the notepad ride the send.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
