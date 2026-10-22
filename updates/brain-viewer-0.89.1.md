# Brain Viewer 0.89.1 (2026-10-21)

0.89.1, on top of 0.88.0 released earlier today. A link written in an item's words, as a path with a label or a markdown link, is drawn as a link on those words; a page route written in the words or in the item's link list is a real page link that navigates, while a document keeps opening beside the page; the bottom row of every card draws all of the item's links, each by the title of what it opens; and the glossary no longer underlines everyday words inside an item.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
