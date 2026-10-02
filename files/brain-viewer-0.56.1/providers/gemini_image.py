"""gemini_image.py -- the Google Gemini image provider for the Brain Viewer's image studio (brain-viewer T-0235).

Sources, read 2026-09-22 (model ids and parameters come from these pages, not from memory):
  https://ai.google.dev/gemini-api/docs/image-generation   (the Nano Banana family, aspect ratios, image sizes,
                                                             reference limits, the Interactions API request and response)
  https://ai.google.dev/gemini-api/docs/imagen             (says Imagen is SHUT DOWN in the Gemini API; so no Imagen here)

Endpoint: POST https://generativelanguage.googleapis.com/v1beta/interactions with the x-goog-api-key header and
  {"model", "input": [{"type": "text", "text"}, {"type": "image", "mime_type", "data": <base64>}...],
   "response_format": {"type": "image", "aspect_ratio": "16:9", "image_size": "2K"}}
The answer carries the picture as base64 (`output_image.data`, or inside `steps[].content[]`); the reader below walks
the whole answer for any image part so a small change of shape does not lose the picture. One call makes one picture,
so n pictures are n calls. References and edits are the same call: the images go in `input` beside the text.

Stdlib only (urllib), so nothing has to be installed. The key is one line in gemini_key.txt at the brain root; it is
read at call time, sent only in the header, and never logged, returned or written anywhere.
Negative prompts: the API has no negative field, so the list is appended to the prompt as "Avoid: ...".
"""
import base64
import json
import os
import re
import urllib.error
import urllib.request

ID = "gemini"
NAME = "Google Gemini"
KEY_FILE = "gemini_key.txt"
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
TIMEOUT = 300
BRAIN = os.environ.get("BRAIN_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ASPECTS = ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
MODELS = [
    # Pro first, so it is the default (Zak, 2026-09-25: the test sun on Flash came out "all weird" next to the
    # references he made in the Gemini app, which renders with the Pro model; Flash stays as the cheap draft).
    {"id": "gemini-3-pro-image", "name": "Nano Banana Pro (Gemini 3 Pro Image)", "aspects": ASPECTS,
     "imageSizes": ["1K", "2K", "4K"], "edits": True, "maxReferences": 11,
     "notes": "The default since 2026-09-25: the Pro model, 1K to 4K, the one the Gemini app renders with. Up to 6 object pictures and 5 character pictures."},
    {"id": "gemini-3.1-flash-image", "name": "Nano Banana (Gemini 3.1 Flash Image)", "aspects": ASPECTS,
     "imageSizes": ["512px", "1K", "2K", "4K"], "edits": True, "maxReferences": 14,
     "notes": "The cheap draft, about a third of Pro's price. Up to 10 object pictures, 4 character pictures and 3 style references."},
    {"id": "gemini-3.1-flash-lite-image", "name": "Nano Banana Lite (Gemini 3.1 Flash Lite Image)", "aspects": ASPECTS,
     "imageSizes": ["1K"], "edits": True, "maxReferences": 14,
     "notes": "The cheapest and fastest; 1K only."},
    {"id": "gemini-2.5-flash-image", "name": "Nano Banana 2.5 (legacy)", "aspects": ASPECTS,
     "imageSizes": ["1K"], "edits": True,
     "notes": "The first Nano Banana, marked legacy in the docs."},
]


class ProviderError(Exception):
    """A refusal or failure from the API, already cut to one line with no key in it."""


def _key():
    try:
        with open(os.path.join(BRAIN, KEY_FILE), "r", encoding="utf-8-sig") as f:
            return f.read().strip().splitlines()[0].strip()
    except (OSError, IndexError):
        return ""


def ready():
    if not _key():
        return False, "create %s at the brain root, one line, the key alone" % KEY_FILE
    return True, ""


def _model(model):
    ids = [m["id"] for m in MODELS]
    return model if model in ids else ids[0]


def _full_prompt(prompt, negative):
    prompt = (prompt or "").strip()
    neg = negative if isinstance(negative, str) else ", ".join(str(x) for x in (negative or []))
    neg = (neg or "").strip()
    return prompt + ("\n\nAvoid: " + neg if neg else "")


def _scrub(text, key):
    text = " ".join(str(text or "").split())
    if key:
        text = text.replace(key, "[key]")
    return re.sub(r"AIza[A-Za-z0-9_\-]{20,}", "[key]", text)[:300]


def _mime(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def _find_images(node, out, texts):
    """Every image part anywhere in the answer, in order: {data, mime_type|mimeType} with an image type."""
    if isinstance(node, dict):
        mime = node.get("mime_type") or node.get("mimeType") or ""
        data = node.get("data")
        if isinstance(data, str) and (str(mime).startswith("image/") or node.get("type") == "image") and len(data) > 64:
            out.append((data, mime or "image/png"))
            return
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            texts.append(node["text"])
        for v in node.values():
            _find_images(v, out, texts)
    elif isinstance(node, list):
        for v in node:
            _find_images(v, out, texts)


def _one(key, model, text, images, aspect, image_size):
    parts = [{"type": "text", "text": text}]
    for data in images or []:
        parts.append({"type": "image", "mime_type": _mime(data), "data": base64.b64encode(data).decode("ascii")})
    payload = {"model": model, "input": parts}
    fmt = {"type": "image"}
    if aspect:
        fmt["aspect_ratio"] = aspect
    if image_size:
        fmt["image_size"] = image_size
    if len(fmt) > 1:
        payload["response_format"] = fmt
    req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8", "replace"))
            msg = (body.get("error") or {}).get("message") or json.dumps(body)
        except Exception:
            msg = str(e)
        raise ProviderError(_scrub("Gemini %s: %s" % (e.code, msg), key))
    except Exception as e:
        raise ProviderError(_scrub("Gemini unreachable: %s" % e, key))
    found, texts = [], []
    _find_images(resp, found, texts)
    if not found:
        said = " ".join(t.strip() for t in texts if t.strip())
        raise ProviderError(_scrub("Gemini answered with no image" + (": " + said if said else ""), key))
    out = []
    for data, mime in found:
        meta = {"endpoint": "interactions"}
        if texts:
            meta["text"] = " ".join(t.strip() for t in texts)[:500]
        out.append((base64.b64decode(data), EXT.get(mime, "png"), meta))
    return out


def generate(prompt, model, n, size_or_aspect, negative=None, references=None, image_size=None):
    """size_or_aspect is an aspect ratio ("16:9"); references a list of image bytes sent beside the text."""
    key = _key()
    if not key:
        raise ProviderError(ready()[1])
    model = _model(model)
    n = max(1, min(4, int(n or 1)))
    aspect = size_or_aspect if size_or_aspect in ASPECTS else None
    text = _full_prompt(prompt, negative)
    out = []
    for _ in range(n):
        out.extend(_one(key, model, text, references, aspect, image_size)[:1])
    return out


def edit(image_bytes, prompt, model, mask=None, size_or_aspect=None, image_size=None):
    """An edit is an instruction beside the picture. Gemini takes no mask: name the part to change in the prompt."""
    key = _key()
    if not key:
        raise ProviderError(ready()[1])
    if mask:
        raise NotImplementedError("Gemini edits by instruction and takes no mask; describe the part to change in the prompt")
    model = _model(model)
    aspect = size_or_aspect if size_or_aspect in ASPECTS else None
    return _one(key, model, (prompt or "").strip(), [image_bytes], aspect, image_size)[:1]
