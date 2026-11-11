"""fal_image.py -- the fal.ai provider for the Brain Viewer's image studio (brain-viewer T-0235).

fal.ai hosts many image models behind one key and one queue API, so this one file reaches Flux, Recraft, Ideogram,
Google's Nano Banana Pro and OpenAI's gpt-image-2. Added 2026-09-22 on the owner's ask for a general image provider
with access to many models; the print backdrop is why Recraft is here.

Sources, read 2026-09-22 (model ids and parameters come from these pages, not from memory):
  https://fal.ai/docs/model-apis/model-endpoints/queue            (queue.fal.run submit, status, result, cancel;
                                                                 "Authorization: Key <key>"; IN_QUEUE, IN_PROGRESS,
                                                                 COMPLETED; error + error_type on a failed request)
  https://fal.ai/models/fal-ai/flux-2-pro/api                     (fal-ai/flux-2-pro: image_size, output_format, seed;
                                                                 no num_images)
  https://fal.ai/models/fal-ai/flux-2-pro/edit/api                (fal-ai/flux-2-pro/edit: image_urls, data URIs accepted)
  https://fal.ai/models/fal-ai/recraft/v3/text-to-image/api       (fal-ai/recraft/v3/text-to-image: style enum incl.
                                                                 vector_illustration/*, colors [{r,g,b}], style_id)
  https://fal.ai/models/fal-ai/recraft/v3/image-to-image/api      (fal-ai/recraft/v3/image-to-image: image_url, strength,
                                                                 style, colors, negative_prompt)
  https://fal.ai/models/fal-ai/recraft/vectorize/api              (fal-ai/recraft/vectorize: image_url in, image/svg+xml out)
  https://fal.ai/models/fal-ai/ideogram/v3/api                    (fal-ai/ideogram/v3: rendering_speed, style, num_images,
                                                                 negative_prompt, color_palette {members:[{rgb, color_weight}]},
                                                                 image_urls as style references; lists /edit and /remix)
  https://fal.ai/models/fal-ai/ideogram/v3/edit/api               (fal-ai/ideogram/v3/edit: image_url + mask_url + prompt;
                                                                 the docs do not say which mask colour is repainted)
  https://fal.ai/models/fal-ai/nano-banana-pro/api                (fal-ai/nano-banana-pro: num_images, aspect_ratio,
                                                                 resolution 1K/2K/4K; edit at fal-ai/nano-banana-pro/edit)
  https://fal.ai/models/openai/gpt-image-2/api                    (openai/gpt-image-2: image_size, quality, num_images,
                                                                 background; billed to the fal key, no OpenAI key)
  https://fal.ai/models/openai/gpt-image-2/edit/api               (openai/gpt-image-2/edit: image_urls up to 16, mask_url)

The queue shape: POST https://queue.fal.run/<endpoint> with the JSON input answers {request_id, status_url,
response_url, cancel_url}; GET status_url until status is COMPLETED (polled every 1 to 3 seconds, 180 seconds at
most, then the request is cancelled and the last thing fal said is the error); GET response_url gives
{images: [{url, content_type, ...}]}. The pictures are URLs on fal's file host; they are downloaded here WITHOUT the
key and returned as (bytes, ext, meta) with the request id, the model and the endpoint in meta.

Stdlib only (urllib), so nothing has to be installed. The key is one line in fal_key.txt at the brain root; it is
read at call time, sent only in the Authorization header to queue.fal.run, and never logged, returned or written.
Negative prompts: Ideogram and Recraft image-to-image take negative_prompt; the rest get "Avoid: ..." appended.
Palette: generate(..., palette=["#0b1d3a", "#f2c14e"]) sends the colours to Recraft (colors) and Ideogram
(color_palette.members). The studio's brief may pass it; the page does not send it yet, so it is optional.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

ID = "fal"
NAME = "fal.ai"
KEY_FILE = "fal_key.txt"
QUEUE = "https://queue.fal.run/"
TIMEOUT = 60            # one HTTP call; the whole wait is POLL_CEILING
POLL_CEILING = 180      # seconds from submit to result
BRAIN = os.environ.get("BRAIN_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_clock = time.monotonic   # replaced by the test to run the 180 seconds instantly
_sleep = time.sleep

SIZES = ["square_hd", "square", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
ASPECTS = ["auto", "21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4", "2:3", "9:16"]

# id is the studio's short name; endpoint and editEndpoint are fal's ids. numImages: the endpoint takes num_images,
# otherwise n pictures are n requests. palette: the endpoint takes colours from generate(palette=[...]).
MODELS = [
    {"id": "flux-2-pro", "name": "FLUX.2 [pro]", "endpoint": "fal-ai/flux-2-pro", "editEndpoint": "fal-ai/flux-2-pro/edit",
     "sizes": SIZES, "edits": True, "numImages": False,
     "notes": "The default: strong general pictures; edits and references by instruction, no mask. "
              "A custom WIDTHxHEIGHT size also works."},
    {"id": "recraft-v3", "name": "Recraft V3", "endpoint": "fal-ai/recraft/v3/text-to-image",
     "editEndpoint": "fal-ai/recraft/v3/image-to-image", "sizes": SIZES, "edits": True, "numImages": False, "palette": True,
     "notes": "Designed output: styles such as vector_illustration/* and digital_illustration/*, and a colour palette; "
              "edits are image-to-image, no mask."},
    {"id": "recraft-v3-svg", "name": "Recraft V3, vector (SVG)", "endpoint": "fal-ai/recraft/v3/text-to-image",
     "vectorize": "fal-ai/recraft/vectorize", "sizes": SIZES, "edits": True, "numImages": False, "palette": True,
     "notes": "Vector for print: a vector_illustration picture turned into an SVG by Recraft's vectorizer; "
              "as an edit it vectorizes the picture given, and the prompt is not used."},
    {"id": "ideogram-v3", "name": "Ideogram V3", "endpoint": "fal-ai/ideogram/v3", "editEndpoint": "fal-ai/ideogram/v3/edit",
     "remixEndpoint": "fal-ai/ideogram/v3/remix", "sizes": SIZES, "edits": True, "numImages": True, "palette": True,
     "notes": "Words in the image: the one to use when the picture must carry legible text; masked edits "
              "(the docs do not say which mask colour is repainted) or a remix without a mask."},
    {"id": "nano-banana-pro", "name": "Nano Banana Pro (Gemini 3 Pro Image, via fal)", "endpoint": "fal-ai/nano-banana-pro",
     "editEndpoint": "fal-ai/nano-banana-pro/edit", "aspects": ASPECTS, "imageSizes": ["1K", "2K", "4K"],
     "edits": True, "numImages": True, "maxReferences": 14,
     "notes": "Google's Pro image model on the fal key; edits by instruction, no mask."},
    {"id": "gpt-image-2", "name": "GPT Image 2 (via fal)", "endpoint": "openai/gpt-image-2", "editEndpoint": "openai/gpt-image-2/edit",
     "sizes": ["auto"] + SIZES, "qualities": ["auto", "low", "medium", "high"], "edits": True, "numImages": True,
     "maxReferences": 16,
     "notes": "OpenAI's model on the fal key, no OpenAI key needed; edits with an optional mask."},
]

_FAL_KEY_SHAPE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}:[0-9a-fA-F]{16,}")
EXT = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/webp": "webp", "image/svg+xml": "svg"}


class ProviderError(Exception):
    """A refusal or failure from fal, already cut to one line with no key in it."""


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


def _spec(model):
    return next((m for m in MODELS if m["id"] == model), MODELS[0])


def _scrub(text, key):
    text = " ".join(str(text or "").split())
    if key:
        text = text.replace(key, "[key]")
    return _FAL_KEY_SHAPE.sub("[key]", text)[:300]


def _full_prompt(prompt, negative):
    prompt = (prompt or "").strip()
    neg = _neg(negative)
    return prompt + ("\n\nAvoid: " + neg if neg else "")


def _neg(negative):
    neg = negative if isinstance(negative, str) else ", ".join(str(x) for x in (negative or []))
    return (neg or "").strip()


def _mime(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _data_uri(data):
    return "data:%s;base64,%s" % (_mime(data), base64.b64encode(data).decode("ascii"))


def _rgb(hexcolor):
    h = str(hexcolor or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ProviderError("palette colours are hex strings like #0b1d3a, not %r" % hexcolor)
    return {"r": int(h[0:2], 16), "g": int(h[2:4], 16), "b": int(h[4:6], 16)}


def _size(value, allow_auto=False):
    """A fal image_size: one of the named sizes, "auto" where the endpoint takes it, or {width, height} from WxH."""
    if not value:
        return None
    v = str(value).strip()
    if v in SIZES or (allow_auto and v == "auto"):
        return v
    m = re.fullmatch(r"(\d{2,5})\s*[xX]\s*(\d{2,5})", v)
    if m:
        return {"width": int(m.group(1)), "height": int(m.group(2))}
    return None


def _http(method, url, key=None, payload=None):
    """(bytes, content type) of one call. The key goes only to queue.fal.run, never to the file host."""
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if key and url.startswith(QUEUE):
        headers["Authorization"] = "Key " + key
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ctype = ""
            try:
                ctype = r.headers.get("Content-Type") or ""
            except Exception:
                pass
            return r.read(), ctype
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8", "replace"))
            msg = _detail(body) or json.dumps(body)
        except Exception:
            msg = str(e)
        raise ProviderError(_scrub("fal %s: %s" % (e.code, msg), key))
    except ProviderError:
        raise
    except Exception as e:
        raise ProviderError(_scrub("fal unreachable: %s" % e, key))


def _detail(body):
    if not isinstance(body, dict):
        return ""
    d = body.get("detail") or body.get("error") or body.get("message")
    if isinstance(d, list):
        return "; ".join(str(x.get("msg") or x) if isinstance(x, dict) else str(x) for x in d)
    return str(d or "")


def _json(method, url, key, payload=None):
    raw, _ = _http(method, url, key, payload)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        raise ProviderError("fal answered with something that is not JSON from %s" % url.split("?")[0])


def _run(key, endpoint, payload):
    """Submit to the queue, poll the status, fetch the result. -> (result dict, request id)."""
    sub = _json("POST", QUEUE + endpoint, key, payload)
    rid = str(sub.get("request_id") or "")
    if not rid:
        raise ProviderError(_scrub("fal did not queue the request: %s" % (_detail(sub) or json.dumps(sub)), key))
    base = QUEUE + endpoint + "/requests/" + rid
    status_url = sub.get("status_url") or base + "/status"
    response_url = sub.get("response_url") or base
    cancel_url = sub.get("cancel_url") or base + "/cancel"
    start = _clock()
    wait, last, said = 1.0, "IN_QUEUE", ""
    while True:
        st = _json("GET", status_url + ("&" if "?" in status_url else "?") + "logs=1", key)
        last = str(st.get("status") or last)
        logs = [l.get("message") for l in (st.get("logs") or []) if isinstance(l, dict) and l.get("message")]
        if logs:
            said = str(logs[-1])
        if st.get("queue_position") is not None and last == "IN_QUEUE":
            said = said or "queue position %s" % st.get("queue_position")
        if last == "COMPLETED":
            if st.get("error"):
                raise ProviderError(_scrub("fal %s failed: %s%s" % (endpoint, st["error"],
                                                                   " (%s)" % st["error_type"] if st.get("error_type") else ""), key))
            break
        if _clock() - start >= POLL_CEILING:
            try:
                _http("PUT", cancel_url, key)
            except Exception:
                pass
            raise ProviderError(_scrub("fal %s request %s did not finish in %d seconds; last status %s%s"
                                       % (endpoint, rid, POLL_CEILING, last, "; fal said: " + said if said else ""), key))
        _sleep(wait)
        wait = min(3.0, wait + 0.5)
    res = _json("GET", response_url, key)
    if isinstance(res, dict) and isinstance(res.get("response"), dict) and "images" not in res and "image" not in res:
        res = res["response"]
    return res, rid


def _files(res):
    """Every picture in a result: images[] or a single image."""
    got = []
    if isinstance(res.get("images"), list):
        got = [f for f in res["images"] if isinstance(f, dict) and f.get("url")]
    elif isinstance(res.get("image"), dict) and res["image"].get("url"):
        got = [res["image"]]
    return got


def _download(f, key):
    url = str(f.get("url"))
    if url.startswith("data:"):
        head, _, b64 = url.partition(",")
        ctype = head[5:].split(";")[0]
        return base64.b64decode(b64), ctype
    raw, ctype = _http("GET", url, None)          # no key to the file host
    return raw, (f.get("content_type") or ctype or "").split(";")[0].strip()


def _ext(ctype, url):
    if ctype in EXT:
        return EXT[ctype]
    tail = os.path.splitext(str(url).split("?")[0])[1].lower().lstrip(".")
    return {"jpeg": "jpg"}.get(tail, tail) if tail in ("png", "jpg", "jpeg", "webp", "svg") else "png"


def _collect(res, rid, key, meta_base, limit=None):
    files = _files(res)
    if not files:
        raise ProviderError(_scrub("fal answered with no image" + (": " + _detail(res) if _detail(res) else ""), key))
    out = []
    for f in files[:limit] if limit else files:
        raw, ctype = _download(f, key)
        meta = dict(meta_base, request_id=rid)
        for k in ("width", "height"):
            if f.get(k):
                meta[k] = f[k]
        if res.get("seed") is not None:
            meta["seed"] = res["seed"]
        if res.get("description"):
            meta["text"] = str(res["description"])[:500]
        out.append((raw, _ext(ctype, f.get("url")), meta))
    return out


def _vectorize(key, spec, picture_url, meta_base):
    res, rid = _run(key, spec["vectorize"], {"image_url": picture_url})
    return _collect(res, rid, key, dict(meta_base, vectorized_by=spec["vectorize"]))


def generate(prompt, model, n, size_or_aspect, negative=None, references=None, palette=None, style=None,
             quality=None, image_size=None, **_other):
    """size_or_aspect: a fal size name (landscape_16_9), WIDTHxHEIGHT, or for Nano Banana Pro an aspect ratio.
    references: image bytes, sent as data URIs. palette: optional hex strings for Recraft and Ideogram.
    style: optional Recraft style (e.g. vector_illustration/bold_stroke) or Ideogram style (DESIGN)."""
    key = _key()
    if not key:
        raise ProviderError(ready()[1])
    spec = _spec(model)
    n = max(1, min(4, int(n or 1)))
    refs = [r for r in (references or []) if r]
    colors = [_rgb(c) for c in (palette or [])] if palette else []
    meta = {"model": spec["id"], "endpoint": spec["endpoint"]}
    payload = {}
    endpoint = spec["endpoint"]
    mid = spec["id"]
    text = _full_prompt(prompt, negative)

    if mid == "flux-2-pro":
        payload = {"prompt": text, "output_format": "png"}
        if refs:
            endpoint = spec["editEndpoint"]
            payload["image_urls"] = [_data_uri(r) for r in refs]
        sz = _size(size_or_aspect, allow_auto=bool(refs))
    elif mid in ("recraft-v3", "recraft-v3-svg"):
        payload = {"prompt": text}
        if style or mid == "recraft-v3-svg":
            payload["style"] = style or "vector_illustration"
        if colors:
            payload["colors"] = colors
        if refs:
            if mid == "recraft-v3-svg":
                raise NotImplementedError("the SVG model takes no references; make the picture with recraft-v3, then vectorize it as an edit")
            endpoint = spec["editEndpoint"]
            payload = {"prompt": (prompt or "").strip(), "image_url": _data_uri(refs[0])}
            if _neg(negative):
                payload["negative_prompt"] = _neg(negative)
            if style:
                payload["style"] = style
            if colors:
                payload["colors"] = colors
            meta["references_used"] = 1
        sz = _size(size_or_aspect)
    elif mid == "ideogram-v3":
        payload = {"prompt": (prompt or "").strip(), "num_images": n}
        if _neg(negative):
            payload["negative_prompt"] = _neg(negative)
        if style:
            payload["style"] = style
        if colors:
            payload["color_palette"] = {"members": [{"rgb": c, "color_weight": 0.5} for c in colors]}
        if refs:
            payload["image_urls"] = [_data_uri(r) for r in refs]
        sz = _size(size_or_aspect)
    elif mid == "nano-banana-pro":
        payload = {"prompt": text, "num_images": n, "output_format": "png"}
        if size_or_aspect in ASPECTS:
            payload["aspect_ratio"] = size_or_aspect
        if image_size in ("1K", "2K", "4K"):
            payload["resolution"] = image_size
        if refs:
            endpoint = spec["editEndpoint"]
            payload["image_urls"] = [_data_uri(r) for r in refs]
        sz = None
    else:   # gpt-image-2
        payload = {"prompt": text, "num_images": n, "output_format": "png"}
        if quality in ("auto", "low", "medium", "high"):
            payload["quality"] = quality
        if refs:
            endpoint = spec["editEndpoint"]
            payload["image_urls"] = [_data_uri(r) for r in refs]
        sz = _size(size_or_aspect, allow_auto=True)
    if sz:
        payload["image_size"] = sz
    meta["endpoint"] = endpoint

    calls = 1 if spec.get("numImages") else n
    out = []
    for _ in range(calls):
        res, rid = _run(key, endpoint, payload)
        if spec.get("vectorize"):
            f = _files(res)
            if f and str(f[0].get("content_type") or "").startswith("image/svg"):
                out.extend(_collect(res, rid, key, meta, limit=1))
            elif f:
                out.extend(_vectorize(key, spec, f[0]["url"], dict(meta, source_request_id=rid)))
            else:
                raise ProviderError("fal answered with no image")
        else:
            out.extend(_collect(res, rid, key, meta, limit=None if spec.get("numImages") else 1))
    return out[:n]


def edit(image_bytes, prompt, model, mask=None, size_or_aspect=None, quality=None, image_size=None, style=None, **_other):
    """mask: PNG bytes the size of the image. Only gpt-image-2 and Ideogram take one; the others edit by instruction."""
    key = _key()
    if not key:
        raise ProviderError(ready()[1])
    spec = _spec(model)
    mid = spec["id"]
    text = (prompt or "").strip()
    src = _data_uri(image_bytes)
    meta = {"model": mid, "masked": bool(mask)}
    if mask and mid not in ("gpt-image-2", "ideogram-v3"):
        raise NotImplementedError("%s edits by instruction and takes no mask; describe the part to change in the prompt" % spec["name"])
    if mid == "recraft-v3-svg":
        return _vectorize(key, spec, src, dict(meta, endpoint=spec["vectorize"], prompt_used=False))
    if mid == "flux-2-pro":
        endpoint, payload = spec["editEndpoint"], {"prompt": text, "image_urls": [src], "output_format": "png"}
        sz = _size(size_or_aspect, allow_auto=True)
    elif mid == "recraft-v3":
        endpoint, payload = spec["editEndpoint"], {"prompt": text, "image_url": src}
        if style:
            payload["style"] = style
        sz = _size(size_or_aspect)
    elif mid == "ideogram-v3":
        if mask:
            endpoint, payload = spec["editEndpoint"], {"prompt": text, "image_url": src, "mask_url": _data_uri(mask)}
        else:
            endpoint, payload = spec["remixEndpoint"], {"prompt": text, "image_url": src}
        sz = None
    elif mid == "nano-banana-pro":
        endpoint, payload = spec["editEndpoint"], {"prompt": text, "image_urls": [src], "output_format": "png"}
        if size_or_aspect in ASPECTS:
            payload["aspect_ratio"] = size_or_aspect
        if image_size in ("1K", "2K", "4K"):
            payload["resolution"] = image_size
        sz = None
    else:   # gpt-image-2
        endpoint, payload = spec["editEndpoint"], {"prompt": text, "image_urls": [src], "output_format": "png"}
        if mask:
            payload["mask_url"] = _data_uri(mask)
        if quality in ("auto", "low", "medium", "high"):
            payload["quality"] = quality
        sz = _size(size_or_aspect, allow_auto=True)
    if sz:
        payload["image_size"] = sz
    if spec.get("numImages"):
        payload["num_images"] = 1
    meta["endpoint"] = endpoint
    res, rid = _run(key, endpoint, payload)
    return _collect(res, rid, key, meta, limit=1)
