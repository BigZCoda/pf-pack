# Brain Viewer 0.114.0 (2026-11-11)

Sharing between brains. Turn sharing on in Settings with your email and a code, add a share partner, and share a task, a question, a file, a thread, a drawing, a section of a people card or a whole project from one Share box. What others share with you is on Today under Shared with you and on the new Shared page; there are team brains and messages too. Nothing is shared and nothing is sent until you turn sharing on, and it needs an invitation from someone who already shares. On a computer your employer owns, what is shared with you still arrives and you can answer it; sharing something of your own waits for their written yes. A brain that runs a program can keep a mailbox for each person in it and send a copy of a task, a question or a file to every mailbox or only the ones ticked. A brain that saves itself to its own GitHub repository each night says so once on Today, and Settings has the switch that turns the sending off. Also new: a step board can hold another board as one closed cell that opens on a double-click, a thread page shows the tasks needed for completion and makes frees and waiting-on entries pressable, and the ? press draws a page's pieces. Nothing to do after updating.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
