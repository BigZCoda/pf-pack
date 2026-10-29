# Brain Viewer 0.97.0 (2026-10-29)

A call's transcript comes in from its page. On a call's page, once the call has ended, The transcript sits right under the call's name: add the transcript takes the plain-text file Gemini makes (or one dropped on the box), files it against that call and its date, and shows what happened and what the drop step printed; once a transcript is filed, run the import chain asks the session to read the call in. Today's card for a call that ended with nothing in the brain carries the same press. A transcript a session pulls from Gemini's email shows on the same page, marked pulled from Gemini. A guest speaking under a display name no card carries is matched to the call prep's one other participant.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
