# providers/ : the image studio's generators

**What is in here.** One Python file per image service the studio page (`/studio`) can call. The folder is the registry, the same way `widgets/` and `looks/` are: serve.py imports every `*.py` here that does not start with `_`, and a file dropped in appears in `GET /api/studio/providers` with no other change. Built 2026-09-22 for a ledger item.

| File | Service | Key file at the brain root |
|---|---|---|
| `openai_image.py` | OpenAI images: `gpt-image-2`, `gpt-image-2.5-sunburst`, `gpt-image-2.5-flare` | `openai_key.txt` |
| `gemini_image.py` | Google Gemini, the Nano Banana family: `gemini-3.1-flash-image`, `gemini-3-pro-image`, `gemini-3.1-flash-lite-image`, `gemini-2.5-flash-image` | `gemini_key.txt` |

Imagen is not here: Google's docs say it is shut down in the Gemini API (read 2026-09-22). Each file's header names the doc pages its model ids came from and the date they were read.

**fal.ai** (`fal_image.py`, key file `fal_key.txt`, added 2026-09-22). fal is a host that runs many image models behind one account, so one key reaches FLUX.2 [pro] (the default), Recraft V3 (designed output, vector styles, a colour palette, and an SVG model that runs Recraft's vectorizer), Ideogram V3 (words in the image), Nano Banana Pro and gpt-image-2, all billed to the fal balance with no Google or OpenAI key. Its API is a queue, not one call: the provider submits to `queue.fal.run/<endpoint>`, polls the status URL every 1 to 3 seconds for at most 180 seconds (then cancels and reports the last thing fal said), fetches the result, and downloads each picture from the URL fal returns, without the key. `generate()` takes an optional `palette` of hex strings for Recraft and Ideogram; the studio's brief may pass it, the page does not yet.

**Local: Flux Krea (ComfyUI)** (`comfy_local.py`, no key file, added 2026-09-25, viewer 0.51.0). FLUX.1 Krea [dev] in 4 bits (GGUF) on the GPU of the machine running ComfyUI, so there is no key and no bill. ComfyUI 0.37.0 lives in its own folder with its own venv (which folder: `COMFY_DIR` in the environment, else `comfy_dir` in `viewer/settings.json`, else `<home>/Documents/ComfyUI/ComfyUI`; it feeds only the start hint the studio shows when ComfyUI is down) and the city96 ComfyUI-GGUF node; start it with `.venv\Scripts\python.exe main.py --port 8188` from that folder. The graph is a file, `comfy_workflows/flux-krea-gguf.json`, in ComfyUI's API (prompt) format with `{{placeholders}}` the provider fills (prompt, width, height, seed, steps, guidance, and the four model files unet, t5, clip_l, vae); the loader imports only the `.py` files at this folder's top, so the workflows folder is data. Where ComfyUI is: `COMFY_URL` in the environment, else the first line of `comfy_url.txt` at the brain root (an address, not a secret; there so the Mac could host the GPU over the LAN), else `http://127.0.0.1:8188`. `ready()` asks ComfyUI itself, so the studio shows the provider off with the reason when ComfyUI is not running or a model file is not in its models folder. `generate()` also takes `seed`, `steps` and `guidance` (the page does not send them yet; the defaults are a random seed, 20 and 3.5); n pictures are n runs one after another on seed, seed+1. **Its edit is image to image** (viewer 0.51.1, the second graph `comfy_workflows/flux-krea-gguf-img2img.json`): the source is uploaded to ComfyUI through `POST /upload/image` (multipart, into `ComfyUI/input/brain-studio/`, named by the source's filename and a hash of its bytes), scaled to the render size (its own aspect at about one megapixel, both sides a multiple of 16), encoded with the VAE, and redrawn from the prompt at a `strength`, the sampler's denoise, default 0.65: below 0.5 keeps the drawing, 0.55 to 0.75 restyles it, above 0.8 forgets it. `POST /api/studio/edit` takes `strength` and `seed`; the page sends neither yet, so an edit from the page runs at 0.65 on a random seed. A source with a transparent ground is flattened onto Paper (#f4ecdd) first, with Pillow, because ComfyUI would read its bare color channels. No mask. What it cannot do: no references, no masked edit, no transparent ground (the VAE decodes three channels), and no negative prompt (Flux runs at cfg 1.0), so Leave out is appended as `Avoid: ...` (the edit route passes it to an edit that names `negative`, this one). Its checks: `python skills/brain-viewer/providers/comfy_local.test.py` (offline against a fake ComfyUI, then both templates against the live server's `/object_info`, one render and one edit into `deliverables/studio/local-flux-first-render/`; `--no-render` skips both, `--edit-only` runs the edit alone).

## What a provider is

A module that exposes:

- `ID`, `NAME`, `KEY_FILE`, and `MODELS`: a list of `{id, name, sizes or aspects, edits, notes}` (extra fields such as `qualities`, `imageSizes`, `maxReferences` are passed through to the page).
- `ready()` returns `(True, "")`, or `(False, reason)` where the reason says what to do, e.g. "create openai_key.txt at the brain root, one line, the key alone".
- `generate(prompt, model, n, size_or_aspect, negative=None, references=None)` returns a list of `(bytes, ext, meta)`. `references` arrive as image bytes; the server reads them from the brain paths the page sent.
- `edit(image_bytes, prompt, model, mask=None)` returns the same shape, or raises `NotImplementedError` with a plain reason when the model cannot do it. The server also sends `strength` and `seed` when the request carries them, to a function that names them or takes `**kwargs`, and `negative` and `source` (the brain path of the picture) only to an edit that names them.
- A failure raises an exception whose message is one line with no key in it. The server answers 502 with that line.

## How to add one

1. Copy the smaller of the two files, rename it `<service>_image.py`, and change `ID`, `NAME`, `KEY_FILE`, `MODELS` and the two calls.
2. Take the model ids from the service's own docs, and write the URLs and the date into the header.
3. Add the new key filename to `.gitignore`, to `NEVER_READ` in `serve.py`, to `FORBIDDEN_LITERAL` and `CODE_LITERAL_OK` in `skills/team-brain/export.py`, to `FORBIDDEN_LITERAL` in `skills/assemble-brain/assemble-brain.py`, and to `CREDENTIALS` in `skills/librarian-sweep/sweep-scan.py`.
4. Prefer the standard library (`urllib`). If a service really needs its SDK, import it inside the function, and have `ready()` return `(False, "pip install <package>")` when the import fails, so serve.py still starts without it. Both current providers use the standard library only, so there is nothing to install.

## The key-file rule

A key lives in one file at the brain root, one line, the key alone. It is git-ignored, never served by the viewer, never exported to a team copy, and read by the provider at call time. A provider never prints, logs, returns or writes a key; error text is scrubbed of it before it leaves the module. A team copy has no keys, so every studio route answers 403 there.

## Negative prompts

Neither API takes a separate negative field reliably, so the provider appends the list to the prompt as `Avoid: ...`. The sidecar keeps the prompt and the negative list apart, as they were typed.

## What does NOT belong here

Generated pictures (they land in `deliverables/studio/<job>/`), key files, and anything that is not a provider. A helper shared by several providers would start with `_` so the loader skips it. A provider's own data (the ComfyUI graphs in `comfy_workflows/`) goes in a subfolder, which the loader never imports; a provider's checks end in `.test.py`, which it skips too.
