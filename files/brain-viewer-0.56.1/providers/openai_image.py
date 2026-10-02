"""openai_image.py -- the OpenAI image provider for the Brain Viewer's image studio (brain-viewer T-0235).

Sources, read 2026-09-22 (model ids and parameters come from these pages, not from memory):
  https://developers.openai.com/api/docs/guides/image-generation   (sizes, quality, n, output_format, edits + mask)
  https://developers.openai.com/api/docs/models/gpt-image-2        (gpt-image-2, default snapshot gpt-image-2-2026-04-21)
  https://developers.openai.com/api/docs/api-reference/images/create  (the model enum, which also lists the gpt-image-2.5 pair)

Endpoints: POST https://api.openai.com/v1/images/generations (JSON) and POST https://api.openai.com/v1/images/edits
(multipart: image[] one or more, mask optional, prompt, model). Both answer data[].b64_json.

Stdlib only (urllib), so nothing has to be installed. The key is one line in openai_key.txt at the brain root; it is
read at call time, sent only in the Authorization header, and never logged, returned or written anywhere.
Negative prompts: the API has no negative field, so the list is appended to the prompt as "Avoid: ...".
"""
import base64
import json
import os
import re
import urllib.error
import urllib.request
import uuid

ID = "openai"
NAME = "OpenAI"
KEY_FILE = "openai_key.txt"
BASE = "https://api.openai.com/v1"
TIMEOUT = 300          # a high-quality image can take a minute or two
BRAIN = os.environ.get("BRAIN_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SIZES = ["auto", "1024x1024", "1536x1024", "1024x1536"]
MODELS = [
    {"id": "gpt-image-2", "name": "GPT Image 2", "sizes": SIZES, "qualities": ["auto", "low", "medium", "high"],
     "edits": True,
     "notes": "The one Zak asked for. Generation and edits (inpainting with a mask). Custom WIDTHxHEIGHT also works: "
              "multiples of 16, ratio between 1:3 and 3:1, at most 3840 per edge."},
    {"id": "gpt-image-2.5-sunburst", "name": "GPT Image 2.5 Sunburst", "sizes": SIZES,
     "qualities": ["auto", "low", "medium", "high", "xhigh", "max"], "edits": True,
     "notes": "Newer, listed as OpenAI's most capable image model; best where editing precision matters."},
    {"id": "gpt-image-2.5-flare", "name": "GPT Image 2.5 Flare", "sizes": SIZES,
     "qualities": ["auto", "low", "medium", "high", "xhigh", "max"], "edits": True,
     "notes": "Newer, the fast everyday model."},
]


class ProviderError(Exception):
    """A refusal or failure from the API, already cut to one line with no key in it."""


def _key_path():
    return os.path.join(BRAIN, KEY_FILE)


def _key():
    try:
        with open(_key_path(), "r", encoding="utf-8-sig") as f:
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
    return re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "[key]", text)[:300]


def _call(req, key):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8", "replace"))
            msg = (body.get("error") or {}).get("message") or json.dumps(body)
        except Exception:
            msg = str(e)
        raise ProviderError(_scrub("OpenAI %s: %s" % (e.code, msg), key))
    except Exception as e:
        raise ProviderError(_scrub("OpenAI unreachable: %s" % e, key))


def _images(resp, fmt, meta_base):
    out = []
    for d in resp.get("data") or []:
        b64 = d.get("b64_json")
        if not b64:
            continue
        meta = dict(meta_base)
        if d.get("revised_prompt"):
            meta["revised_prompt"] = d["revised_prompt"]
        for k in ("usage", "quality", "size", "background"):
            if resp.get(k) is not None:
                meta[k] = resp[k]
        out.append((base64.b64decode(b64), fmt, meta))
    if not out:
        raise ProviderError("OpenAI answered with no image")
    return out


def _multipart(fields, files):
    """fields: [(name, value)], files: [(name, filename, bytes, mime)] -> (body, content type)."""
    boundary = "----bvstudio" + uuid.uuid4().hex
    parts = []
    for name, value in fields:
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, name, value)).encode("utf-8"))
    for name, filename, data, mime in files:
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
                      % (boundary, name, filename, mime)).encode("utf-8") + data + b"\r\n")
    parts.append(("--%s--\r\n" % boundary).encode("utf-8"))
    return b"".join(parts), "multipart/form-data; boundary=" + boundary


def _mime(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return "image/png", "png"


def _edits(key, model, prompt, images, mask, n, size, quality):
    fields = [("model", model), ("prompt", prompt), ("n", str(n)), ("output_format", "png")]
    if size and size != "auto":
        fields.append(("size", size))
    if quality and quality != "auto":
        fields.append(("quality", quality))
    files = []
    field = "image[]" if len(images) > 1 else "image"
    for i, data in enumerate(images):
        mime, ext = _mime(data)
        files.append((field, "image-%d.%s" % (i + 1, ext), data, mime))
    if mask:
        files.append(("mask", "mask.png", mask, "image/png"))
    body, ctype = _multipart(fields, files)
    req = urllib.request.Request(BASE + "/images/edits", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": ctype})
    return _call(req, key)


def generate(prompt, model, n, size_or_aspect, negative=None, references=None, quality=None):
    """references: a list of image bytes. With references the call goes to /images/edits, which takes them as inputs."""
    key = _key()
    if not key:
        raise ProviderError(ready()[1])
    model = _model(model)
    n = max(1, min(4, int(n or 1)))
    text = _full_prompt(prompt, negative)
    meta = {"endpoint": "edits" if references else "generations"}
    if references:
        resp = _edits(key, model, text, list(references), None, n, size_or_aspect, quality)
    else:
        payload = {"model": model, "prompt": text, "n": n, "output_format": "png"}
        if size_or_aspect:
            payload["size"] = size_or_aspect
        if quality:
            payload["quality"] = quality
        req = urllib.request.Request(BASE + "/images/generations", data=json.dumps(payload).encode("utf-8"), method="POST",
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        resp = _call(req, key)
    return _images(resp, "png", meta)


def edit(image_bytes, prompt, model, mask=None, size_or_aspect=None, quality=None):
    """mask: PNG bytes with an alpha channel, the same size as the image; transparent pixels are the part to repaint."""
    key = _key()
    if not key:
        raise ProviderError(ready()[1])
    model = _model(model)
    if not next((m for m in MODELS if m["id"] == model), {}).get("edits"):
        raise NotImplementedError("%s does not take edits" % model)
    resp = _edits(key, model, (prompt or "").strip(), [image_bytes], mask, 1, size_or_aspect, quality)
    return _images(resp, "png", {"endpoint": "edits", "masked": bool(mask)})
