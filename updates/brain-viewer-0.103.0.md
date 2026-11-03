# Brain Viewer 0.103.0 (2026-11-03)

Step boards in the Forge, and a file dropped on any page. A process can be drawn as steps in order, each step a markdown file that lists its documents, its video and its form; the drawing redraws itself from those files every time it opens, so attaching a document to a step is one line in that step's file. A step's form, written as numbered questions tagged with the kind of answer and whether it is required, opens as a page of its own from Open the form, and its questions can be copied as data for a survey or a web page; boards show in the Forge's list of drawings and open in read mode. A file dropped on any page is kept with what that page is about. Drag a file onto a page, or use the file press in the notepad, and a small panel says what it goes with: on a call's page the call and the people on it, on a thread's page the thread, on an item that item, on a card that person. Say what it is for if you like and press Add: it goes to the main agent with your next Send, and the agent works out what it is. The Send press now takes a note for everything it sends: right-click it, or hold it on a phone. Both have a setting on the Settings page. Nothing to do after updating.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
