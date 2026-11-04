# Brain Viewer 0.107.0 (2026-11-03)

Modulators on step boards, any single task shared, and past chats in the search. On a step board every line a step's file declares is drawn as a facet on its cell, coloured by its family, with a switch between facets on the rim and boxes outside it, a legend that filters, and a key the board does not know drawn grey as new. Share now works on any task, also one on a list the other copy never holds: that one task goes across alone, its words, steps and note, made again at every export, never its list, its id, its tags, its people or a link to a file the other side does not have; a private task or a question is refused with the reason in one line. The search at the top also finds your past conversations on the Chat page. Nothing to do after updating.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
