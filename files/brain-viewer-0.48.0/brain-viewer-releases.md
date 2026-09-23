# Brain Viewer releases

What each released version of the component changed, newest first. Written by release.py.

## 0.48.0 (2026-09-23)

The viewer is now a pf-pack component, replaced whole on update, and what you make lives outside it. Your settings, board layouts, looks and widgets live in viewer/ at the brain root, which no update touches; on first start the viewer creates that folder and copies in any settings, layouts and looks it finds from before. You can write your own widgets in viewer/widgets/: each declares contract: 1, loads after the viewer's own, and cannot take the name of one the viewer ships. A brain with no holon registry or content manifest now shows empty pages instead of errors, and the owner defaults to @me until viewer/settings.json names you. Install or update with python skills/update/install-component.py brain-viewer (or /update).

