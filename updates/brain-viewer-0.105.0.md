# Brain Viewer 0.105.0 (2026-11-03)

What was sent to you, in every mode. A page of its own, sent to you, lists what the other side of an exchange sent, not opened first, with the count in the menu and a band at the top of Today while something waits; the viewer brings it in when it starts, with each sync of a copy that is its member's own brain, and when the page opens. One press opens an item where it is: a video plays on the page, a document opens beside it, a web page or a PDF opens in a new tab, anything else downloads; bring into my folder stays the second press, in that kind of copy too. Select and archive on Sent to you and on Artifacts, which now puts first what an open item or a coming call's prep links. Until this version a copy that is its member's own brain never showed the pull press, so nothing sent could be opened there. Nothing to do after updating.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
