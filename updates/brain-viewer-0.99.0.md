# Brain Viewer 0.99.0 (2026-10-29)

The channel between the owner's brain and the copy of the person he shares with. Today carries Messages with <member>, open when something waits on you: a box to write, the threads of the last thirty days, each message saying whose words it is (you, your agent, them, their agent). When one side is away, its agent answers what the other asks from the shared files only, handed to it in its prompt, with every tool off and no other file it could open, or passes it to its person (in the owner's brain also a task, closed by his reply). A message sent while a computer is off waits in the shared repository and is answered once it is back on: the viewer checks a minute after start, when a message is written, and every ten minutes (channel_minutes, 0 off), the owner's side only in the brain the viewer is installed in. The copy's export keeps the channel and ships it; the merge never lands a message in the owner's brain.

**How to apply.** This is a folder component: it is replaced whole, never merged. Stop the viewer if it is running, then run

```
python skills/update/install-component.py brain-viewer
```

and start it again with `python skills/brain-viewer/serve.py`. What you made for the viewer (settings, board layouts, looks, widgets) lives in `viewer/` and is not touched. `--check` on the same command says what is installed and what is published.
