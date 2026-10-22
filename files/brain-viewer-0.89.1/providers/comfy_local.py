"""comfy_local.py -- the local provider for the Brain Viewer's image studio: FLUX.1 Krea [dev] on a GPU in the house, through ComfyUI.

Added 2026-09-25 (viewer 0.51.0), the day ComfyUI 0.37.0 went in at <home>\\Documents\\ComfyUI\\ComfyUI with its own
venv (torch 2.14 cu130, RTX 4060 Laptop, 8 GB). No key and no bill: the pictures are made on the machine that runs ComfyUI.
The graph is a file, not code: comfy_workflows/flux-krea-gguf.json, in ComfyUI's API (prompt) format, with {{placeholders}}
this module fills: prompt, width, height, seed, steps, guidance, and the four model filenames unet, t5, clip_l, vae. Every
class name and input name in it was checked against the running server's own /object_info on 2026-09-25, and
comfy_local.test.py checks them again on every run.

Sources, read 2026-09-25 in the installed ComfyUI's own server.py and execution.py (0.37.0), not from memory:
  POST /prompt                 {"prompt": <graph>, "client_id": <uuid>} -> {prompt_id, number, node_errors}; a graph that
                               fails validation answers 400 {error: {type, message, details}, node_errors: {<id>: {errors,
                               class_type}}}
  GET  /history/<prompt_id>    {} until the run ends, then {<prompt_id>: {prompt, outputs: {<node id>: {images: [{filename,
                               subfolder, type}]}}, status: {status_str: success | error, completed, messages: [[event,
                               data]]}}}; a failure is the execution_error message (node_id, node_type, exception_type,
                               exception_message), an interrupt is execution_interrupted
  GET  /view?filename=&subfolder=&type=output    the picture's bytes
  GET  /object_info/<Class>    one node's inputs, {} when the node is not installed; a loader's filename input is the list
                               of files ComfyUI sees in its models folder (a download still running is a .part, not listed)
  GET  /queue                  {queue_running, queue_pending}: where a slow run stands, for the timeout message
  POST /queue {"delete": [id]} and POST /interrupt {"prompt_id": id}: how a run past the ceiling is withdrawn
  ComfyUI-GGUF (github.com/city96/ComfyUI-GGUF): UnetLoaderGGUF, one input, unet_name, from models/diffusion_models.
Added for the edit route (viewer 0.51.1, 2026-09-25), read the same way in server.py and nodes.py:
  POST /upload/image           multipart/form-data: image (the file, with a filename), type=input, subfolder,
                               overwrite=true -> {name, subfolder, type}; the file lands in ComfyUI/input/<subfolder>/
                               and LoadImage takes it as "<subfolder>/<name>" (its VALIDATE_INPUTS checks the file
                               exists, so the name need not be in the list /object_info/LoadImage shows)
  LoadImage (image) -> IMAGE, MASK; ImageScale (image, upscale_method, width, height, crop); VAEEncode (pixels, vae)

Where ComfyUI is: COMFY_URL in the environment, else the first line of comfy_url.txt at the brain root, else
http://127.0.0.1:8188. The file is there so the Mac could host the GPU later over the LAN; it holds an address, not a secret.

What Flux cannot do, said here so the studio never pretends:
  - No negative prompt. Flux dev is guidance-distilled and runs at cfg 1.0, where the sampler ignores the negative; the graph
    feeds KSampler a zeroed conditioning only because the input is required. "Leave out" is appended as "Avoid: ...", the
    way fal_image.py does it for the models with no negative field.
  - No transparent background. The VAE decodes three channels, so every picture has a ground. Ask for a flat ground and cut
    it out afterwards; nothing here fakes an alpha channel.
  - No references, and no masked edit. generate() refuses references. edit() is image to image, not an instruction edit:
    the source is scaled to the render size, encoded, and redrawn from the prompt at a strength (KSampler denoise,
    default 0.65; below 0.5 keeps the drawing, 0.55 to 0.75 restyles it, above 0.8 forgets it). A mask is refused.
    A source with a transparent ground is flattened onto a ground first (default Paper, #f4ecdd, the palette's print
    cream), because ComfyUI would read its bare color channels; that step needs Pillow, which the viewer's Python has.

The edit graph is comfy_workflows/flux-krea-gguf-img2img.json: LoadImage -> ImageScale (lanczos, center crop) ->
VAEEncode -> the same conditioning, KSampler (denoise {{denoise}}), decode and save as the text graph. One edit: upload the
source (named by its own filename and a hash of its bytes, so the same source is one file in ComfyUI/input/brain-studio/),
fill the graph, then the same run as generate().

One run: fill the graph, POST it, poll /history every second for at most 600 seconds (then withdraw it and say where it
stood), read the SaveImage node's file from the history entry, GET it from /view, and return [(bytes, "png", meta)] with the
prompt id, the model file, the seed, the steps, the guidance, the size and the elapsed seconds in meta. n pictures are n
runs one after another on seed, seed+1, ...: one 1024 picture at a time is what 8 GB holds. ComfyUI keeps its own copy in
ComfyUI/output/brain-studio_*.png (an edit's in brain-studio-edit_*.png, its source in ComfyUI/input/brain-studio/); this
module writes nothing in the brain, the server files the picture in deliverables/studio/<job>/.
Stdlib only (urllib), nothing to install; Pillow is imported only to flatten a transparent edit source.
"""
import copy
import hashlib
import io
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ID = "comfy"
NAME = "Local (ComfyUI)"
KEY_FILE = None                 # nothing to keep secret: the GPU is ours
URL_FILE = "comfy_url.txt"      # optional, at the brain root: one line, e.g. http://192.168.4.63:8188
DEFAULT_URL = "http://127.0.0.1:8188"
TIMEOUT = 30                    # one HTTP call; the whole wait is POLL_CEILING
PING_TIMEOUT = 3                # ready() runs on every load of the studio page
POLL_CEILING = 600              # seconds from submit to picture, queue wait included
POLL_EVERY = 1.0
UPLOAD_SUBFOLDER = "brain-studio"   # ComfyUI/input/brain-studio/: where an edit's source is uploaded
DEFAULT_STRENGTH = 0.65             # the edit's KSampler denoise when none is sent
GROUND = "#f4ecdd"                  # Paper (design/pf-brand-palette.md): a transparent source is flattened onto it
MIME = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}
HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS = os.path.join(HERE, "comfy_workflows")
BRAIN = os.environ.get("BRAIN_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def comfy_dir():
    """Where ComfyUI is installed, used only for the start hint (2026-10-02: a setting, so the shipped code names no
    user): COMFY_DIR in the environment, else `comfy_dir` in viewer/settings.json at the brain root, else
    <home>/Documents/ComfyUI/ComfyUI."""
    d = (os.environ.get("COMFY_DIR") or "").strip().strip('"')
    if not d:
        try:
            with open(os.path.join(BRAIN, "viewer", "settings.json"), "r", encoding="utf-8-sig") as f:
                d = str(json.load(f).get("comfy_dir") or "").strip()
        except Exception:
            d = ""
    return d or os.path.join(os.path.expanduser("~"), "Documents", "ComfyUI", "ComfyUI")


START_HINT = "cd %s and run %s main.py --port 8188" % (comfy_dir(), os.path.join(".venv", "Scripts", "python.exe"))

_clock = time.monotonic         # replaced by the test to run the 600 seconds instantly
_sleep = time.sleep

# Flux wants both sides a multiple of 16 (the VAE's 8 times the 2x2 patch); these are the usual ~1 megapixel shapes.
SIZES = ["1024x1024", "1152x896", "896x1152", "1216x832", "832x1216", "1344x768", "768x1344"]

# The loader that lists each model file, its input, and the models/ folder the file belongs in.
LOADERS = {"unet": ("UnetLoaderGGUF", "unet_name", "diffusion_models"),
           "t5": ("DualCLIPLoader", "clip_name1", "text_encoders"),
           "clip_l": ("DualCLIPLoader", "clip_name2", "text_encoders"),
           "vae": ("VAELoader", "vae_name", "vae")}

MODELS = [
    {"id": "flux-krea-dev", "name": "Local: Flux Krea (ComfyUI)", "workflow": "flux-krea-gguf.json",
     "editWorkflow": "flux-krea-gguf-img2img.json",
     "files": {"unet": "flux1-krea-dev-Q4_K_M.gguf", "t5": "t5xxl_fp8_e4m3fn_scaled.safetensors",
               "clip_l": "clip_l.safetensors", "vae": "ae.safetensors"},
     "steps": 20, "guidance": 3.5, "sizes": SIZES, "edits": True, "masks": False, "strength": DEFAULT_STRENGTH,
     "local": True,
     "notes": "On the GPU at home, no key and no bill: FLUX.1 Krea [dev] in 4 bits, 20 steps, one picture at a time. "
              "Edit is image to image: the whole picture is redrawn from the prompt at strength 0.65 (0.55 to 0.75 "
              "restyles, below 0.5 keeps the drawing), no mask. No references, no transparent ground; Leave out is sent "
              "as Avoid:, Flux has no negative prompt."},
]


class ProviderError(Exception):
    """A refusal or failure from ComfyUI, already cut to one line."""


def _line(text):
    return " ".join(str(text or "").split())[:300]


def _url():
    """The ComfyUI base URL: COMFY_URL, else comfy_url.txt at the brain root, else 127.0.0.1:8188. No trailing slash."""
    url = (os.environ.get("COMFY_URL") or "").strip()
    if not url:
        try:
            with open(os.path.join(BRAIN, URL_FILE), "r", encoding="utf-8-sig") as f:
                url = (f.read().strip().splitlines() or [""])[0].strip()
        except OSError:
            url = ""
    url = url or DEFAULT_URL
    if not re.match(r"^https?://", url, re.I):
        url = "http://" + url
    return url.rstrip("/")


def _down(base):
    return ProviderError("ComfyUI is not running at %s; start it with: %s" % (base, START_HINT))


def _http(method, base, path, payload=None, timeout=TIMEOUT, body=None, content_type=None):
    """(bytes, content type) of one call to ComfyUI. payload is sent as JSON; body as raw bytes of content_type."""
    data, headers = None, {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif body is not None:
        data = body
        headers["Content-Type"] = content_type or "application/octet-stream"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = ""
            try:
                ctype = r.headers.get("Content-Type") or ""
            except Exception:
                pass
            return r.read(), ctype
    except urllib.error.HTTPError as e:
        raw = b""
        try:
            raw = e.read()
        except Exception:
            pass
        raise ProviderError(_line("ComfyUI %s on %s: %s" % (e.code, path.split("?")[0], _refusal(raw) or e.reason)))
    except (TimeoutError, OSError) as e:          # URLError is an OSError: refused, unreachable, timed out
        reason = getattr(e, "reason", e)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason):
            raise ProviderError("ComfyUI at %s did not answer %s in %d seconds" % (base, path.split("?")[0], timeout))
        raise _down(base)


def _json(method, base, path, payload=None, timeout=TIMEOUT):
    raw, _ = _http(method, base, path, payload, timeout)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        raise ProviderError("ComfyUI answered %s with something that is not JSON" % path.split("?")[0])


def _refusal(raw):
    """One line from a POST /prompt refusal: the error, then each node's first error."""
    try:
        body = json.loads(raw.decode("utf-8", "replace")) if isinstance(raw, bytes) else raw
    except Exception:
        return _line(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
    if not isinstance(body, dict):
        return _line(body)
    parts = []
    err = body.get("error")
    if isinstance(err, dict):
        parts.append(" ".join(x for x in (str(err.get("message") or ""), str(err.get("details") or "")) if x))
    elif err:
        parts.append(str(err))
    for nid, ne in sorted((body.get("node_errors") or {}).items()):
        first = ((ne or {}).get("errors") or [{}])[0]
        parts.append("node %s %s: %s%s" % (nid, (ne or {}).get("class_type", ""), first.get("message", ""),
                                           " (%s)" % first["details"] if first.get("details") else ""))
    return _line("; ".join(p for p in parts if p))


def _spec(model):
    return next((m for m in MODELS if m["id"] == model), MODELS[0])


def _choices(info, cls, name):
    """The filenames a loader offers: the list form, or the COMBO form with options."""
    spec = (((info.get(cls) or {}).get("input") or {}).get("required") or {}).get(name) or [[]]
    first = spec[0]
    if isinstance(first, list):
        return first
    if first == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
        return list(spec[1].get("options") or [])
    return []


def _preflight(spec, base, timeout=TIMEOUT):
    """Raise the first thing that stops a run: ComfyUI down, the GGUF node missing, or a model file ComfyUI does not list."""
    infos = {}
    for role, (cls, name, folder) in LOADERS.items():
        if cls not in infos:
            infos[cls] = _json("GET", base, "/object_info/" + cls, timeout=timeout)
        if cls not in infos[cls]:
            if cls == "UnetLoaderGGUF":
                raise ProviderError("ComfyUI at %s has no UnetLoaderGGUF node: install city96/ComfyUI-GGUF into custom_nodes/ "
                                    "and restart ComfyUI" % base)
            raise ProviderError("ComfyUI at %s has no %s node" % (base, cls))
        want = spec["files"][role]
        have = _choices(infos[cls], cls, name)
        if want not in have:
            raise ProviderError(_line("%s is not in ComfyUI's models/%s/ at %s (a download still running is a .part, which "
                                      "ComfyUI does not list); it sees: %s" % (want, folder, base, ", ".join(have) or "nothing")))


def ready():
    try:
        _preflight(MODELS[0], _url(), timeout=PING_TIMEOUT)
    except ProviderError as e:
        return False, str(e)
    return True, ""


def _template(spec, which="workflow"):
    """The graph file a model names: "workflow" (text to image) or "editWorkflow" (image to image)."""
    path = os.path.join(WORKFLOWS, spec[which])
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise ProviderError(_line("the workflow template %s did not load: %s" % (spec[which], e)))


def _fill(node, values):
    """The graph with every "{{name}}" string replaced by its typed value; an unknown placeholder is an error."""
    if isinstance(node, dict):
        return {k: _fill(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [_fill(v, values) for v in node]
    if isinstance(node, str):
        m = re.fullmatch(r"\{\{(\w+)\}\}", node)
        if m:
            if m.group(1) not in values:
                raise ProviderError("the workflow template asks for {{%s}}, which this provider does not fill" % m.group(1))
            return values[m.group(1)]
    return node


def _full_prompt(prompt, negative):
    prompt = (prompt or "").strip()
    neg = negative if isinstance(negative, str) else ", ".join(str(x) for x in (negative or []))
    neg = (neg or "").strip()
    return prompt + ("\n\nAvoid: " + neg if neg else "")


def _size(value):
    """(width, height) from WIDTHxHEIGHT, each rounded down to a multiple of 16 and kept within 256..2048."""
    if not value:
        return 1024, 1024
    m = re.fullmatch(r"\s*(\d{2,5})\s*[xX*]\s*(\d{2,5})\s*", str(value))
    if not m:
        raise ProviderError("a local size is WIDTHxHEIGHT, e.g. 1024x1024, not %r" % value)
    return tuple(max(256, min(2048, int(v) // 16 * 16)) for v in m.groups())


def _exec_error(status):
    """One line from a failed run's status messages."""
    for ev, data in reversed([m for m in (status.get("messages") or []) if isinstance(m, list) and len(m) == 2]):
        data = data if isinstance(data, dict) else {}
        if ev == "execution_error":
            return "node %s (%s): %s: %s" % (data.get("node_id"), data.get("node_type"), data.get("exception_type", "error"),
                                            data.get("exception_message", ""))
        if ev == "execution_interrupted":
            return "interrupted in node %s (%s)" % (data.get("node_id"), data.get("node_type"))
    return "status %s" % (status.get("status_str") or "unknown")


def _where(base, pid):
    """Where a slow run stands: running, waiting behind n, or gone from the queue."""
    try:
        q = _json("GET", base, "/queue", timeout=5)
    except ProviderError:
        return "the queue did not answer"
    if any(isinstance(i, list) and len(i) > 1 and i[1] == pid for i in q.get("queue_running") or []):
        return "still running"
    pending = sorted((i for i in q.get("queue_pending") or [] if isinstance(i, list) and len(i) > 1), key=lambda i: i[0])
    ids = [i[1] for i in pending]
    if pid in ids:
        return "still waiting, %d ahead of it" % (ids.index(pid) + len(q.get("queue_running") or []))
    return "not in the queue"


def _run(base, graph):
    """Queue one graph, wait for it, fetch its picture. -> (png bytes, prompt id, ComfyUI's filename, seconds)."""
    start = _clock()
    sub = _json("POST", base, "/prompt", {"prompt": graph, "client_id": uuid.uuid4().hex})
    pid = str(sub.get("prompt_id") or "")
    if not pid:
        raise ProviderError(_line("ComfyUI did not queue the graph: %s" % (_refusal(sub) or json.dumps(sub))))
    if sub.get("node_errors"):
        raise ProviderError(_line("ComfyUI queued the graph with node errors: %s" % _refusal({"node_errors": sub["node_errors"]})))
    save_ids = [k for k, v in graph.items() if isinstance(v, dict) and v.get("class_type") == "SaveImage"]
    while True:
        hist = _json("GET", base, "/history/" + urllib.parse.quote(pid))
        entry = hist.get(pid) if isinstance(hist, dict) else None
        if entry:
            status = entry.get("status") or {}
            if status.get("status_str") == "error":
                raise ProviderError(_line("ComfyUI run %s failed in %s" % (pid, _exec_error(status))))
            if status.get("completed") or entry.get("outputs"):
                break
        if _clock() - start >= POLL_CEILING:
            where = _where(base, pid)
            for path, body in (("/queue", {"delete": [pid]}), ("/interrupt", {"prompt_id": pid})):
                try:
                    _http("POST", base, path, body, timeout=5)
                except ProviderError:
                    pass
            raise ProviderError("ComfyUI run %s did not finish in %d seconds (%s); it was withdrawn" % (pid, POLL_CEILING, where))
        _sleep(POLL_EVERY)
    outputs = entry.get("outputs") or {}
    files = []
    for nid in save_ids + [k for k in outputs if k not in save_ids]:
        files += [f for f in (outputs.get(nid) or {}).get("images") or [] if isinstance(f, dict) and f.get("filename")]
    if not files:
        raise ProviderError("ComfyUI finished run %s with no picture in its outputs" % pid)
    f = files[0]
    q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder") or "", "type": f.get("type") or "output"})
    raw, _ = _http("GET", base, "/view?" + q)
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ProviderError("ComfyUI's /view answered %s with something that is not a PNG" % f["filename"])
    return raw, pid, f["filename"], round(_clock() - start, 1)


def generate(prompt, model, n, size_or_aspect, negative=None, references=None, seed=None, steps=None, guidance=None, **_other):
    """size_or_aspect: WIDTHxHEIGHT (default 1024x1024). seed: the first picture's seed, random when None; picture i uses
    seed + i. steps and guidance: the model's defaults (20, 3.5) when None. references: refused, the graph is text to image."""
    spec = _spec(model)
    if references:
        raise NotImplementedError("the local Flux Krea graph is text to image and takes no reference pictures; "
                                  "use a fal or OpenAI model to work from references")
    n = max(1, min(4, int(n or 1)))
    width, height = _size(size_or_aspect)
    steps = max(1, min(100, int(steps or spec["steps"])))
    guidance = float(spec["guidance"] if guidance in (None, "") else guidance)
    seed = int(seed) if seed not in (None, "") else random.randint(0, 2 ** 32 - 1)
    base = _url()
    _preflight(spec, base)
    template = _template(spec)
    text = _full_prompt(prompt, negative)
    out = []
    for i in range(n):
        values = {"prompt": text, "width": width, "height": height, "seed": seed + i, "steps": steps, "guidance": guidance}
        values.update(spec["files"])
        raw, pid, fname, secs = _run(base, _fill(copy.deepcopy(template), values))
        out.append((raw, "png", {"model": spec["id"], "model_file": spec["files"]["unet"], "prompt_id": pid,
                                 "seed": seed + i, "steps": steps, "guidance": guidance, "width": width, "height": height,
                                 "elapsed_s": secs, "workflow": spec["workflow"], "comfy_url": base, "comfy_file": fname}))
    return out


def _probe(data):
    """(width, height, ext, has_alpha) from a PNG, JPEG or WebP header, stdlib only."""
    data = bytes(data or b"")
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        w, h = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        alpha = data[25:26] in (b"\x04", b"\x06")
        i = 8
        while not alpha and i + 8 <= len(data):
            n, kind = int.from_bytes(data[i:i + 4], "big"), data[i + 4:i + 8]
            if kind in (b"IDAT", b"IEND"):
                break
            alpha = kind == b"tRNS"
            i += 12 + n
        return w, h, "png", alpha
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01, 0xFF) or 0xD0 <= marker <= 0xD7:
                i += 1 if marker == 0xFF else 2
                continue
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big"), "jpg", False
            i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
        raise ProviderError("the source JPEG has no frame header, so its size cannot be read")
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X":
            return (1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little"), "webp",
                    bool(data[20] & 0x10))
        if kind == b"VP8L":
            b = data[21:25]
            return (1 + (((b[1] & 0x3F) << 8) | b[0]), 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6)),
                    "webp", bool((b[3] >> 4) & 1))
        if kind == b"VP8 ":
            return (int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF,
                    "webp", False)
    raise ProviderError("the source is not a PNG, JPEG or WebP picture")


def _rgb(hexcolor):
    h = str(hexcolor or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ProviderError("a ground is a hex color like #f4ecdd, not %r" % hexcolor)
    return tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))


def _flatten(data, ground):
    """The source with its transparent ground filled with the ground color, as PNG bytes. Needs Pillow."""
    try:
        from PIL import Image
    except ImportError:
        raise ProviderError("the source has a transparent ground, which ComfyUI would read as its bare color channels; "
                            "flatten it onto a ground first, or pip install pillow so this provider does it")
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:
        raise ProviderError(_line("the source picture did not decode: %s" % e))
    flat = Image.new("RGBA", im.size, _rgb(ground) + (255,))
    flat.alpha_composite(im.convert("RGBA"))
    out = io.BytesIO()
    flat.convert("RGB").save(out, "PNG")
    return out.getvalue()


def _fit(w, h, area):
    """The render size for a w x h source: its aspect, about `area` pixels, both sides a multiple of 16 in 256..2048.
    A long side past 2048 scales both sides down together, so a wide strip keeps its aspect instead of being cropped."""
    aspect = float(w) / float(h)
    fw, fh = (area * aspect) ** 0.5, (area / aspect) ** 0.5
    k = min(1.0, 2048.0 / max(fw, fh))
    return tuple(max(256, min(2048, int(round(v * k / 16.0)) * 16)) for v in (fw, fh))


def _upload(base, data, ext, source=None):
    """POST /upload/image as multipart -> the name LoadImage takes, "<subfolder>/<name>". The file is named by the
    source's own filename and a hash of the bytes, so the same source uploaded twice is one file (overwrite=true)."""
    stem = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(os.path.basename(str(source or "")))[0].lower()).strip("-")[:40]
    name = "%s-%s.%s" % (stem or "source", hashlib.sha256(data).hexdigest()[:12], ext)
    boundary = "----brainstudio" + uuid.uuid4().hex
    parts = [("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, k, v)).encode("utf-8")
             for k, v in (("type", "input"), ("subfolder", UPLOAD_SUBFOLDER), ("overwrite", "true"))]
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
                  % (boundary, name, MIME.get(ext, "application/octet-stream"))).encode("utf-8") + data + b"\r\n")
    parts.append(("--%s--\r\n" % boundary).encode("utf-8"))
    raw, _ = _http("POST", base, "/upload/image", body=b"".join(parts),
                   content_type="multipart/form-data; boundary=" + boundary)
    try:
        ans = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ProviderError("ComfyUI answered /upload/image with something that is not JSON")
    got = str(ans.get("name") or "")
    if not got:
        raise ProviderError(_line("ComfyUI did not file the uploaded source: %s" % json.dumps(ans)))
    sub = str(ans.get("subfolder") or "").strip("/")
    return sub + "/" + got if sub else got


def edit(image_bytes, prompt, model, mask=None, strength=None, negative=None, seed=None, steps=None, guidance=None,
         size_or_aspect=None, ground=None, source=None, **_other):
    """Image to image. The source (PNG, JPEG or WebP bytes) is uploaded to ComfyUI, scaled to the render size (its own
    aspect, about the pixels of size_or_aspect, default 1024x1024, both sides a multiple of 16), encoded, and redrawn
    from the prompt at strength, the KSampler denoise (default 0.65). mask: refused, the whole picture is redrawn.
    A transparent source is flattened onto ground (default Paper, #f4ecdd) first. source: the brain path, kept in meta.
    -> [(png bytes, "png", meta)] with the denoise and the source in meta."""
    spec = _spec(model)
    if mask:
        raise NotImplementedError("the local Flux Krea edit redraws the whole picture at a strength and takes no mask; "
                                  "describe the change in the prompt, or use gpt-image-2 or Ideogram for a masked edit")
    if not spec.get("editWorkflow"):
        raise NotImplementedError("%s has no image-to-image graph" % spec["name"])
    if not image_bytes:
        raise ProviderError("the edit has no source picture")
    try:
        strength = DEFAULT_STRENGTH if strength in (None, "") else float(strength)
    except (TypeError, ValueError):
        raise ProviderError("strength is a number above 0 and at most 1, not %r" % strength)
    if not 0 < strength <= 1:
        raise ProviderError("strength is a number above 0 and at most 1 (0.55 to 0.75 restyles), not %r" % strength)
    denoise = round(strength, 3)
    src_w, src_h, ext, alpha = _probe(image_bytes)
    flattened = None
    if alpha:
        flattened = ground or GROUND
        image_bytes, ext = _flatten(image_bytes, flattened), "png"
    bw, bh = _size(size_or_aspect)
    width, height = _fit(src_w, src_h, bw * bh)
    steps = max(1, min(100, int(steps or spec["steps"])))
    guidance = float(spec["guidance"] if guidance in (None, "") else guidance)
    seed = int(seed) if seed not in (None, "") else random.randint(0, 2 ** 32 - 1)
    base = _url()
    _preflight(spec, base)
    template = _template(spec, "editWorkflow")
    name = _upload(base, image_bytes, ext, source)
    values = {"prompt": _full_prompt(prompt, negative), "width": width, "height": height, "seed": seed, "steps": steps,
              "guidance": guidance, "denoise": denoise, "image": name}
    values.update(spec["files"])
    raw, pid, fname, secs = _run(base, _fill(copy.deepcopy(template), values))
    meta = {"model": spec["id"], "model_file": spec["files"]["unet"], "prompt_id": pid, "seed": seed, "steps": steps,
            "guidance": guidance, "denoise": denoise, "width": width, "height": height, "elapsed_s": secs,
            "workflow": spec["editWorkflow"], "comfy_url": base, "comfy_file": fname, "comfy_input": name,
            "source": source or name, "source_size": "%dx%d" % (src_w, src_h)}
    if flattened:
        meta["flattened_on"] = flattened
    return [(raw, "png", meta)]
