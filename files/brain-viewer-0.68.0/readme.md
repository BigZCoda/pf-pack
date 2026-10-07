# The Brain Viewer

A local app that shows your brain folder in the browser: a home board of widgets, the day, your projects and their tasks and questions, a page per piece of work that runs across them where any one item can be worked on with its brief, files and history, the people you work with, a reader for any markdown file, the drawings and maps, and a preview of any web page in the brain or on a local server at phone and desktop widths. It runs on your own computer at http://127.0.0.1:8765 and nothing leaves the machine.

## Set it up with Claude Code

Open Claude Code in your brain folder and paste:

> set up the viewer

Claude reads this file and does the steps below one at a time, telling you what each one showed. The steps are here in full so you can also follow them yourself.

## The steps

1. **Check Python.** Run `python --version` (on a Mac, `python3 --version`).
   It worked when it prints `Python 3.` followed by a number of 10 or more. If it is missing, install Python 3 from python.org and run the check again.

2. **Check the viewer is installed.** Look for the file `skills/brain-viewer/component.json` in your brain folder.
   It worked when the file is there and its `version` line names a version. If it is missing, run `python skills/update/install-component.py brain-viewer`; it worked when its last line starts with `installed brain-viewer`.

3. **Start it.** From the brain folder run `python skills/brain-viewer/serve.py`.
   It worked when the window prints a line starting `Brain Viewer v` with the version and the address. Leave that window open: closing it stops the viewer.

4. **Open it.** Go to http://127.0.0.1:8765 in your browser.
   It worked when the Today page shows the date at the top and the list of what is waiting on you under it. The home board of widgets is at http://127.0.0.1:8765/home.

5. **Check your own folder was made.** On its first start the viewer creates `viewer/` in your brain folder, with `settings.json`, `layouts/`, `looks/` and `widgets/` inside it.
   It worked when `viewer/settings.json` exists.

6. **Tell it who you are.** Open `viewer/settings.json` and set `owner` to your handle, for example `"owner": "@sam"`. Stop the viewer (Ctrl+C in its window) and start it again as in step 3.
   It worked when the Today page (http://127.0.0.1:8765/today) counts the questions addressed to that handle.

7. **Give it a project to show, if you have none yet.** If `context/holon-registry.json` does not exist in your brain folder, stop the viewer and run `python skills/brain-viewer/serve.py --init`, which creates the registry and a first project ledger and never overwrites a file that exists.
   It worked when the Projects page (http://127.0.0.1:8765/projects) lists one project.

## Updating it

Ask Claude Code to run `/update`. It compares your viewer with the published version and, when you say yes, stops the viewer, replaces `skills/brain-viewer/` with the new version, and starts it again. To see where you stand without changing anything, run `python skills/update/install-component.py brain-viewer --check`.

An update replaces the whole `skills/brain-viewer/` folder. Do not keep your own changes there: they are lost at the next update.

## What is yours

Everything you make in the viewer lives in `viewer/` in your brain folder, which an update never touches:

- `viewer/settings.json`: your settings, each one explained in the file's `_keys`.
- `viewer/layouts/`: your home board, saved when you arrange it in edit mode.
- `viewer/looks/`: looks you wrote or imported (a look is one file of colors and fonts; `skills/brain-viewer/looks/readme.md` explains them).
- `viewer/widgets/`: widgets you wrote. How to write one is in `skills/brain-viewer/widgets/readme.md` and `curriculum.md`; a widget declares `contract: 1` and must not reuse the name of a widget the viewer ships.

The full rules for widgets, looks and what an update may touch are in `brain-viewer-plugin-contract.md`, beside this file.

## Testing a widget

The widget harness mounts one widget in a real page without a browser. Once, in `skills/brain-viewer/`, run `npm install` (it needs Node.js), then with the viewer running, `python skills/brain-viewer/widgets/harness.py --capture` to record the answers your own viewer gives. After that, `python skills/brain-viewer/widgets/harness.py viewer/widgets/<your file>.js` says whether your widget holds.
It worked when the last line says the widget holds.

## If something is wrong

Read the last lines the viewer's window printed. `http://127.0.0.1:8765/api/health` answers with the version and the last time the viewer stopped, and why.
