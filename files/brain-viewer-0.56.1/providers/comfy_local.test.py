"""comfy_local.test.py -- the claims comfy_local.py makes, checked (2026-09-25, viewer 0.51.0).

Run from anywhere: python skills/brain-viewer/providers/comfy_local.test.py [--no-render]

Offline (a fake ComfyUI plays every route, a fake clock runs the 600 seconds instantly):
 1. the module loads, is listed by serve.py's loader as "comfy", and names its model "Local: Flux Krea (ComfyUI)" with
    edits false and WIDTHxHEIGHT sizes
 2. the template fills: every {{placeholder}} replaced, numbers as numbers, the prompt with "Avoid: ..." appended
 3. a run is object_info x3 (the preflight), POST /prompt with {prompt, client_id}, GET /history until the entry, GET /view;
    it returns (png bytes, "png", meta) with the prompt id, model file, seed, steps and elapsed seconds; n=2 is two runs
    on seed and seed+1
 4. the failures say what to do in one line: ComfyUI down (names the URL and how to start it), the GGUF node missing, a
    model file ComfyUI does not list, a refused graph (names the node), a run that fails (names the node and the
    exception), a run past 600 seconds (withdrawn with POST /queue delete and /interrupt)
 5. references are refused with NotImplementedError; COMFY_URL beats comfy_url.txt, which beats the default
 5b the edit (0.51.1, image to image): preflight, a multipart POST /upload/image (type input, subfolder brain-studio,
    overwrite true), the img2img graph with the uploaded name, the source's aspect at about 1 megapixel in multiples of
    16, denoise 0.65 by default or the strength sent; meta carries the denoise, the source and its size; a mask, a
    strength outside 0..1 and a non-picture are refused; a transparent source is flattened onto Paper first
Live (only when ComfyUI answers):
 6. every node of both templates is a class the server has, every input a template sets is one the class takes, every
    required input is set, and every fixed choice (sampler, scheduler, upscale method, crop) is one the server lists
 7. the four model files are listed by their loaders; when one is not, the render is skipped and says which
 8. the render (skipped with --no-render): the palette's sun, 1024x1024, through the studio's own save path -- the running
    viewer's POST /api/studio/generate when it lists the comfy provider ready, else serve.studio_run in this process -- so
    it lands in deliverables/studio/<job>/ with its sidecar and job.md line and shows in the studio's history. The VRAM
    peak is sampled from /system_stats once a second while it runs.
 9. the edit render (skipped with --no-render; --edit-only skips 8 and runs this alone): the sun mark filed 9/23 through
    POST /api/studio/edit at strength 0.6, into the same job folder, a 1136x928 PNG whose sidecar says kind edit and
    names the source, the strength and the denoise
"""
import io
import json
import os
import re
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, VIEWER)

import comfy_local as C  # noqa: E402

FAILS = []
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c63f8cfc0f01f0005000201a1e6c5d80000000049454e44ae426082")
FILES = C.MODELS[0]["files"]
VIEWER_URL = "http://127.0.0.1:8765"
JOB = "local-flux-first-render"
# The palette's names and hexes, said together as design/pf-brand-palette.md asks.
SUN_PROMPT = ("A woodcut-style sun with a serene face, its rays alternating straight and wavy, printed as a single-color "
              "relief print in Old Gold (#c9a24a) on a flat Paper (#f4ecdd) background, warm cream unbleached paper. "
              "No text, no border. The sun centered in the square.")
SUN_NEGATIVE = "text, letters, border, frame, a second ink color, gradients, photographic texture"
# The edit check (viewer 0.51.1): the sun mark filed 9/23, Old Gold on Paper, redrawn at strength 0.6.
EDIT_SOURCE = "deliverables/studio/genius-booth/references/pf-sun-mark-on-paper-2026-09-23.png"
EDIT_PROMPT = ("The same sun with a calm face and straight rays, redrawn as a flat two-color woodcut illustration: carved "
               "relief-print linework in Old Gold (#c9a24a) on a solid flat Paper (#f4ecdd) background. No border, no frame, "
               "no signature, no text, no watermark.")
EDIT_NEGATIVE = "border, frame, signature, text, letters, watermark, gradients"


def opaque_png(w, h, rgb=(201, 162, 74), alpha=None):
    """A w x h PNG of one color, stdlib only: RGB (color type 2), or RGBA (type 6) when alpha is given."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    px = bytes(rgb) + (bytes([alpha]) if alpha is not None else b"")
    rows = b"".join(b"\x00" + px * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6 if alpha is not None else 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(what)


class FakeResponse:
    def __init__(self, body, ctype="application/json"):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.headers = {"Content-Type": ctype}

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def loader_info(unet=True, gguf_node=True):
    return {"UnetLoaderGGUF": {"UnetLoaderGGUF": {"input": {"required": {"unet_name": [[FILES["unet"]] if unet else []]}}}}
            if gguf_node else {},
            "DualCLIPLoader": {"DualCLIPLoader": {"input": {"required": {
                "clip_name1": [[FILES["clip_l"], FILES["t5"]]], "clip_name2": [[FILES["clip_l"], FILES["t5"]]],
                "type": [["flux"]]}}}},
            "VAELoader": {"VAELoader": {"input": {"required": {"vae_name": ["COMBO", {"options": [FILES["vae"]]}]}}}}}


def fake_comfy(history_seq=None, refuse=None, unet=True, gguf_node=True):
    """A urlopen that plays ComfyUI. history_seq: the answers to GET /history, the last one repeating."""
    seen = []
    infos = loader_info(unet, gguf_node)
    state = {"n": 0}

    def urlopen(req, timeout=None):
        url, method = req.full_url, req.get_method()
        path = url.split("8188", 1)[-1]
        multipart = (req.headers.get("Content-type") or "").startswith("multipart/form-data")
        body = req.data if multipart else (json.loads(req.data.decode("utf-8")) if req.data else None)
        seen.append({"method": method, "path": path, "body": body, "ctype": req.headers.get("Content-type") or ""})
        if path == "/upload/image":
            fname = re.search(rb'name="image"; filename="([^"]+)"', body or b"")
            return FakeResponse({"name": fname.group(1).decode() if fname else "", "subfolder": "brain-studio",
                                 "type": "input"})
        if path.startswith("/object_info/"):
            return FakeResponse(infos.get(path[len("/object_info/"):], {}))
        if path == "/prompt":
            if refuse:
                raise urllib.error.HTTPError(url, 400, "Bad Request", {}, io.BytesIO(json.dumps(refuse).encode("utf-8")))
            state["n"] += 1
            return FakeResponse({"prompt_id": "pid-%d" % state["n"], "number": state["n"], "node_errors": {}})
        if path.startswith("/history/"):
            pid = path[len("/history/"):]
            seq = history_seq or [{}, {"@": {"outputs": {"10": {"images": [{"filename": "brain-studio_00001_.png",
                                                                             "subfolder": "", "type": "output"}]}},
                                         "status": {"status_str": "success", "completed": True, "messages": []}}}]
            k = sum(1 for s in seen if s["path"] == path) - 1
            ans = seq[min(k, len(seq) - 1)]
            return FakeResponse({pid: ans["@"]} if "@" in ans else ans)
        if path.startswith("/view?"):
            return FakeResponse(PNG, "image/png")
        if path == "/queue" and method == "GET":
            return FakeResponse({"queue_running": [[1, "pid-1", {}, {}, []]], "queue_pending": []})
        if path in ("/queue", "/interrupt"):
            return FakeResponse(b"")
        raise AssertionError("unplayed route %s %s" % (method, path))
    return urlopen, seen


def offline():
    import serve  # noqa: E402  (the viewer's loader; importing it starts nothing)
    provs = serve.studio_providers()
    mod = provs.get("comfy")
    check(mod is not None and not isinstance(mod, tuple), "1 serve.py's loader lists the comfy provider",
          repr(mod[1]) if isinstance(mod, tuple) else "")
    m = C.MODELS[0]
    check(m["name"] == "Local: Flux Krea (ComfyUI)" and m["edits"] is True and m.get("masks") is False
          and m["sizes"][0] == "1024x1024" and all("x" in s for s in m["sizes"]),
          "1 the model is 'Local: Flux Krea (ComfyUI)', edits true (image to image, no mask), WIDTHxHEIGHT sizes")
    rows = {r["id"]: r for r in serve.studio_providers_api()["providers"]}
    check(any(mm.get("edits") for mm in (rows.get("comfy") or {}).get("models", [])),
          "1 the providers listing the studio page reads offers the local model to the edit control (edits true)")

    tpl = C._template(m)
    vals = dict(FILES, prompt="a sun", width=1024, height=768, seed=5, steps=20, guidance=3.5)
    g = C._fill(tpl, vals)
    flat = json.dumps(g)
    check("{{" not in flat and g["7"]["inputs"]["width"] == 1024 and g["5"]["inputs"]["guidance"] == 3.5
          and g["8"]["inputs"]["seed"] == 5 and g["1"]["inputs"]["unet_name"] == FILES["unet"],
          "2 the template fills every placeholder, numbers as numbers")
    check(C._full_prompt("a sun", ["text", "border"]) == "a sun\n\nAvoid: text, border", "2 the negative is appended as Avoid:")
    try:
        C._fill({"x": "{{nope}}"}, vals)
        check(False, "2 an unknown placeholder is an error")
    except C.ProviderError:
        check(True, "2 an unknown placeholder is an error")
    etpl = C._template(m, "editWorkflow")
    eg = C._fill(etpl, dict(vals, denoise=0.55, image="brain-studio/sun-abc.png"))
    classes = {v["class_type"] for v in eg.values()}
    check("{{" not in json.dumps(eg) and eg["8"]["inputs"]["denoise"] == 0.55 and eg["8"]["inputs"]["latent_image"] == ["12", 0]
          and eg["12"]["class_type"] == "VAEEncode" and eg["12"]["inputs"]["pixels"] == ["11", 0]
          and eg["11"]["inputs"]["image"] == ["7", 0] and eg["7"]["inputs"]["image"] == "brain-studio/sun-abc.png"
          and eg["11"]["inputs"]["width"] == 1024 and "EmptySD3LatentImage" not in classes,
          "2 the img2img template fills: LoadImage -> ImageScale -> VAEEncode -> KSampler at the denoise, no empty latent")
    check(C._fit(3401, 2610, 1024 * 1024) == (1168, 896) and C._fit(1536, 512, 1536 * 512) == (1536, 512)
          and all(v % 16 == 0 for v in C._fit(1360, 1402, 1024 * 1024)) and C._fit(6144, 1024, 1024 * 1024) == (2048, 336),
          "2 the render size keeps the source's aspect at about the pixel budget, both sides a multiple of 16",
          "%s %s" % (C._fit(3401, 2610, 1024 * 1024), C._fit(1360, 1402, 1024 * 1024)))

    saved = (urllib.request.urlopen, C._sleep, C._clock, os.environ.get("COMFY_URL"))
    clock = [0.0]
    C._sleep = lambda s: clock.__setitem__(0, clock[0] + s)
    C._clock = lambda: clock[0]
    os.environ["COMFY_URL"] = "http://127.0.0.1:8188"
    try:
        urllib.request.urlopen, seen = fake_comfy()
        got = C.generate("a sun", "flux-krea-dev", 1, "1024x1024", negative="text", seed=42)
        steps = [(s["method"], s["path"].split("?")[0]) for s in seen]
        check(steps == [("GET", "/object_info/UnetLoaderGGUF"), ("GET", "/object_info/DualCLIPLoader"),
                        ("GET", "/object_info/VAELoader"), ("POST", "/prompt"), ("GET", "/history/pid-1"),
                        ("GET", "/history/pid-1"), ("GET", "/view")],
              "3 a run is the preflight, POST /prompt, /history until the entry, /view", str(steps))
        post = next(s["body"] for s in seen if s["path"] == "/prompt")
        check(set(post) == {"prompt", "client_id"} and len(post["client_id"]) == 32
              and post["prompt"]["4"]["inputs"]["text"] == "a sun\n\nAvoid: text" and post["prompt"]["8"]["inputs"]["seed"] == 42,
              "3 the body is {prompt, client_id}, the prompt carries Avoid:, the seed is the one asked for")
        view = next(s["path"] for s in seen if s["path"].startswith("/view"))
        check("filename=brain-studio_00001_.png" in view and "type=output" in view and "subfolder=" in view,
              "3 the picture is fetched by filename, subfolder and type", view)
        meta = got[0][2] if got else {}
        check(len(got) == 1 and got[0][0] == PNG and got[0][1] == "png" and meta.get("prompt_id") == "pid-1"
              and meta.get("model_file") == FILES["unet"] and meta.get("seed") == 42 and meta.get("steps") == 20
              and "elapsed_s" in meta, "3 it returns (bytes, png, meta) with prompt id, model file, seed, steps, seconds",
              json.dumps(meta)[:200])
        urllib.request.urlopen, seen = fake_comfy()
        got = C.generate("two", "flux-krea-dev", 2, None, seed=7)
        seeds = [s["body"]["prompt"]["8"]["inputs"]["seed"] for s in seen if s["path"] == "/prompt"]
        check(len(got) == 2 and seeds == [7, 8] and got[0][2]["width"] == 1024, "3 n=2 is two runs on seed and seed+1", str(seeds))

        def fails(what, fn, *needles):
            try:
                fn()
                check(False, what, "no error")
            except (C.ProviderError, NotImplementedError) as e:
                msg = str(e)
                check(all(n in msg for n in needles) and "\n" not in msg, what, msg[:160])

        urllib.request.urlopen, _ = fake_comfy(gguf_node=False)
        fails("4 the GGUF node missing names ComfyUI-GGUF", lambda: C.generate("x", "flux-krea-dev", 1, None), "ComfyUI-GGUF")
        urllib.request.urlopen, _ = fake_comfy(unet=False)
        ok, reason = C.ready()
        check(ok is False and FILES["unet"] in reason and "models/diffusion_models/" in reason,
              "4 a model ComfyUI does not list makes ready() false, naming the file and folder", reason[:160])
        urllib.request.urlopen, _ = fake_comfy(refuse={"error": {"type": "prompt_outputs_failed_validation",
                                                                 "message": "Prompt outputs failed validation", "details": ""},
                                                       "node_errors": {"8": {"class_type": "KSampler", "errors": [
                                                           {"message": "Value not in list", "details": "sampler_name: 'x'"}]}}})
        fails("4 a refused graph names the node", lambda: C.generate("x", "flux-krea-dev", 1, None),
              "failed validation", "node 8 KSampler", "Value not in list")
        err = {"@": {"outputs": {}, "status": {"status_str": "error", "completed": False, "messages": [
            ["execution_start", {}], ["execution_error", {"node_id": "8", "node_type": "KSampler",
                                                          "exception_type": "torch.OutOfMemoryError",
                                                          "exception_message": "CUDA out of memory"}]]}}}
        urllib.request.urlopen, _ = fake_comfy(history_seq=[{}, err])
        fails("4 a failed run names the node and the exception", lambda: C.generate("x", "flux-krea-dev", 1, None),
              "node 8 (KSampler)", "OutOfMemoryError")
        clock[0] = 0.0
        urllib.request.urlopen, seen = fake_comfy(history_seq=[{}])
        fails("4 a run past 600 seconds is withdrawn and says where it stood",
              lambda: C.generate("x", "flux-krea-dev", 1, None), "600 seconds", "still running", "withdrawn")
        check([s["path"] for s in seen if s["method"] == "POST"][-2:] == ["/queue", "/interrupt"]
              and seen[-2]["body"] == {"delete": ["pid-1"]} and seen[-1]["body"] == {"prompt_id": "pid-1"},
              "4 the withdrawal is POST /queue delete, then POST /interrupt")
        fails("5 references are refused", lambda: C.generate("x", "flux-krea-dev", 1, None, references=[PNG]), "no reference")

        # 5b the edit route, image to image
        src = opaque_png(472, 388)
        urllib.request.urlopen, seen = fake_comfy()
        got = C.edit(src, "the same sun, woodcut", "flux-krea-dev", negative="frame, text", seed=9,
                     source="deliverables/studio/x/sun.png")
        steps = [(s["method"], s["path"].split("?")[0]) for s in seen]
        check(steps == [("GET", "/object_info/UnetLoaderGGUF"), ("GET", "/object_info/DualCLIPLoader"),
                        ("GET", "/object_info/VAELoader"), ("POST", "/upload/image"), ("POST", "/prompt"),
                        ("GET", "/history/pid-1"), ("GET", "/history/pid-1"), ("GET", "/view")],
              "5b an edit is the preflight, POST /upload/image, POST /prompt, /history until the entry, /view", str(steps))
        up = next(s for s in seen if s["path"] == "/upload/image")
        fields = dict(re.findall(rb'name="(type|subfolder|overwrite)"\r\n\r\n([^\r]*)\r\n', up["body"]))
        check(up["ctype"].startswith("multipart/form-data; boundary=") and fields == {b"type": b"input", b"subfolder": b"brain-studio",
                                                                                       b"overwrite": b"true"}
              and src in up["body"] and b'filename="sun-' in up["body"],
              "5b the upload is multipart: the bytes as image, type input, subfolder brain-studio, overwrite true, named by the source",
              str(fields))
        g = next(s["body"]["prompt"] for s in seen if s["path"] == "/prompt")
        check(g["8"]["inputs"]["denoise"] == 0.65 and g["7"]["inputs"]["image"].startswith("brain-studio/sun-")
              and (g["11"]["inputs"]["width"], g["11"]["inputs"]["height"]) == (1136, 928)
              and g["4"]["inputs"]["text"] == "the same sun, woodcut\n\nAvoid: frame, text" and g["8"]["inputs"]["seed"] == 9,
              "5b the graph loads the uploaded name, scales to the source's aspect (472x388 -> 1136x928), denoise 0.65 by default",
              json.dumps({k: g[k]["inputs"] for k in ("7", "11")})[:200])
        meta = got[0][2] if got else {}
        check(len(got) == 1 and got[0][0] == PNG and got[0][1] == "png" and meta.get("denoise") == 0.65
              and meta.get("source") == "deliverables/studio/x/sun.png" and meta.get("source_size") == "472x388"
              and meta.get("workflow") == "flux-krea-gguf-img2img.json" and meta.get("seed") == 9,
              "5b it returns (bytes, png, meta) with the denoise, the source and its size", json.dumps(meta)[:200])
        urllib.request.urlopen, seen = fake_comfy()
        C.edit(src, "x", "flux-krea-dev", strength=0.55)
        g = next(s["body"]["prompt"] for s in seen if s["path"] == "/prompt")
        check(g["8"]["inputs"]["denoise"] == 0.55, "5b strength 0.55 is the KSampler's denoise 0.55")
        fails("5b a mask is refused", lambda: C.edit(src, "x", "flux-krea-dev", mask=PNG), "no mask")
        fails("5b a strength outside 0..1 is refused", lambda: C.edit(src, "x", "flux-krea-dev", strength=1.5), "strength")
        fails("5b a source that is not a picture is refused", lambda: C.edit(b"not an image", "x", "flux-krea-dev"),
              "not a PNG, JPEG or WebP")
        try:
            import PIL  # noqa: F401
            urllib.request.urlopen, seen = fake_comfy()
            got = C.edit(opaque_png(64, 48, alpha=0), "x", "flux-krea-dev")      # fully transparent RGBA
            up = next(s for s in seen if s["path"] == "/upload/image")["body"]
            blob = up[up.index(b"\r\n\r\n\x89PNG") + 4:]
            from PIL import Image
            px = Image.open(io.BytesIO(blob)).getpixel((0, 0))
            check(got[0][2].get("flattened_on") == C.GROUND and blob[25:26] == b"\x02" and px == (244, 236, 221),
                  "5b a transparent source is flattened onto Paper before the upload (RGB, color type 2)")
        except ImportError:
            print("skip the flatten check: no Pillow")
    finally:
        urllib.request.urlopen, C._sleep, C._clock = saved[:3]
        if saved[3] is None:
            os.environ.pop("COMFY_URL", None)
        else:
            os.environ["COMFY_URL"] = saved[3]

    # 4 down, for real: a port nothing listens on
    env = os.environ.get("COMFY_URL")
    os.environ["COMFY_URL"] = "http://127.0.0.1:1"
    try:
        ok, reason = C.ready()
        check(ok is False and "ComfyUI is not running at http://127.0.0.1:1" in reason and "main.py --port 8188" in reason,
              "4 ComfyUI down: ready() says where and how to start it", reason[:160])
    finally:
        if env is None:
            os.environ.pop("COMFY_URL", None)
        else:
            os.environ["COMFY_URL"] = env

    # 5 where ComfyUI is
    brain, env = C.BRAIN, os.environ.pop("COMFY_URL", None)
    tmp = tempfile.mkdtemp(prefix="comfy-url-test-")
    try:
        C.BRAIN = tmp
        a = C._url()
        with open(os.path.join(tmp, C.URL_FILE), "w", encoding="utf-8") as f:
            f.write("192.168.4.63:8188/\n")
        b = C._url()
        os.environ["COMFY_URL"] = "http://10.0.0.2:8188"
        c = C._url()
        check(a == "http://127.0.0.1:8188" and b == "http://192.168.4.63:8188" and c == "http://10.0.0.2:8188",
              "5 COMFY_URL beats comfy_url.txt, which beats the default", "%s | %s | %s" % (a, b, c))
    finally:
        C.BRAIN = brain
        os.environ.pop("COMFY_URL", None)
        if env is not None:
            os.environ["COMFY_URL"] = env
        try:
            os.remove(os.path.join(tmp, C.URL_FILE))
            os.rmdir(tmp)
        except OSError:
            pass


def get_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def live(render):
    base = C._url()
    try:
        get_json(base + "/system_stats", timeout=3)
    except Exception:
        print("skip live checks and the render: ComfyUI is not running at %s" % base)
        return
    infos = {}
    for which in ("workflow", "editWorkflow"):
        tpl = C._template(C.MODELS[0], which)
        problems = []
        for nid, node in sorted(tpl.items(), key=lambda kv: int(kv[0])):
            cls = node.get("class_type")
            info = infos.setdefault(cls, get_json(base + "/object_info/" + cls).get(cls))
            if not info:
                problems.append("node %s: the server has no class %s" % (nid, cls))
                continue
            takes = dict((info.get("input") or {}).get("required") or {})
            takes.update((info.get("input") or {}).get("optional") or {})
            for name in node.get("inputs") or {}:
                if name not in takes:
                    problems.append("node %s %s: no input named %s" % (nid, cls, name))
            for name in ((info.get("input") or {}).get("required") or {}):
                if name not in (node.get("inputs") or {}):
                    problems.append("node %s %s: required input %s is not set" % (nid, cls, name))
            for name, val in (node.get("inputs") or {}).items():       # a fixed choice must be one the server lists
                spec = takes.get(name) or [None]
                opts = spec[0] if isinstance(spec[0], list) else (spec[1].get("options") if spec[0] == "COMBO" and len(spec) > 1 else None)
                if opts and isinstance(val, str) and not val.startswith("{{") and val not in opts and cls != "LoadImage":
                    problems.append("node %s %s: %s=%r is not one of the server's choices" % (nid, cls, name, val))
        check(not problems, "6 every %s node and input is one the server's object_info names (%d nodes)"
              % (C.MODELS[0][which], len(tpl)), "; ".join(problems))
    ok, reason = C.ready()
    check(True, "7 model files: %s" % ("all four listed" if ok else reason))
    if not ok:
        print("skip the render: %s" % reason)
        return
    if not render:
        print("skip the render: --no-render")
        return

    if "--edit-only" not in sys.argv:
        render_text(base)
    render_edit(base)


def studio_post(route, body):
    """(code, answer, via): the running viewer's POST /api/studio/<route> when it lists comfy ready, else serve.studio_run."""
    via = "the running viewer"
    try:
        rows = get_json(VIEWER_URL + "/api/studio/providers", timeout=10).get("providers", [])
        if not any(p.get("id") == "comfy" and p.get("ready") for p in rows):
            raise RuntimeError("the viewer does not list comfy ready")
        req = urllib.request.Request(VIEWER_URL + "/api/studio/" + route, method="POST",
                                     data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=C.POLL_CEILING + 120) as r:
                code, out = r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            code, out = e.code, json.loads(e.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, RuntimeError, OSError) as e:
        via = "serve.studio_run in this process (%s)" % e
        import serve
        code, out = serve.studio_run(route, body)
    return code, out, via


def saved(rel):
    """(sidecar dict, width, height, png header ok, absolute path) of a picture the studio filed."""
    import serve
    ap = os.path.join(serve.BRAIN, rel.replace("/", os.sep))
    with open(os.path.splitext(ap)[0] + ".json", "r", encoding="utf-8") as f:
        side = json.load(f)
    with open(ap, "rb") as f:
        head = f.read(24)
    return side, int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big"), head[:8] == b"\x89PNG\r\n\x1a\n", ap


def render_text(base):
    peak = {"used": 0, "total": 0, "stop": False}

    def sample():
        while not peak["stop"]:
            try:
                d = get_json(base + "/system_stats", timeout=3)["devices"][0]
                peak["total"] = d["vram_total"]
                peak["used"] = max(peak["used"], d["vram_total"] - d["vram_free"])
            except Exception:
                pass
            time.sleep(1)
    t = threading.Thread(target=sample, daemon=True)
    t.start()
    body = {"provider": "comfy", "model": "flux-krea-dev", "prompt": SUN_PROMPT, "negative": SUN_NEGATIVE,
            "size": "1024x1024", "n": 1, "job": JOB, "project": "brain-viewer-holon"}
    t0 = time.time()
    code, out, via = studio_post("generate", body)
    peak["stop"] = True
    secs = round(time.time() - t0, 1)
    imgs = out.get("images") or []
    check(code == 200 and len(imgs) == 1 and imgs[0]["path"].startswith("deliverables/studio/%s/" % JOB),
          "8 the render lands in the studio's job folder, through %s" % via.split(" (")[0],
          out.get("error") or (imgs[0]["path"] if imgs else ""))
    if code != 200 or not imgs:
        return
    side, w, h, png, ap = saved(imgs[0]["path"])
    meta = side.get("meta") or {}
    check(png and (w, h) == (1024, 1024), "8 the picture is a 1024x1024 PNG", "%dx%d" % (w, h))
    check(side.get("provider") == "comfy" and side.get("negative") == SUN_NEGATIVE and meta.get("prompt_id")
          and meta.get("model_file") == FILES["unet"], "8 the sidecar keeps the prompt, the negative and the run's meta")
    jm = os.path.join(os.path.dirname(ap), "job.md")
    check(os.path.isfile(jm) and "comfy | flux-krea-dev" in open(jm, encoding="utf-8").read(), "8 job.md has the run's line")
    print("render: %s, %.1f s in ComfyUI (seed %s, %s steps), %.1f s end to end, %d bytes; VRAM peak sampled %.2f of %.2f GB"
          % (imgs[0]["path"], meta.get("elapsed_s") or 0, meta.get("seed"), meta.get("steps"), secs, os.path.getsize(ap),
             peak["used"] / 2 ** 30, peak["total"] / 2 ** 30))


def render_edit(base):
    """9 one image-to-image run through the studio's edit route: the palette's sun mark on Paper at strength 0.6."""
    import serve
    if not os.path.isfile(os.path.join(serve.BRAIN, EDIT_SOURCE.replace("/", os.sep))):
        print("skip the edit render: %s is not in this brain" % EDIT_SOURCE)
        return
    body = {"provider": "comfy", "model": "flux-krea-dev", "image": EDIT_SOURCE, "prompt": EDIT_PROMPT,
            "negative": EDIT_NEGATIVE, "strength": 0.6, "job": JOB}
    t0 = time.time()
    code, out, via = studio_post("edit", body)
    secs = round(time.time() - t0, 1)
    imgs = out.get("images") or []
    check(code == 200 and len(imgs) == 1 and imgs[0]["path"].startswith("deliverables/studio/%s/" % JOB),
          "9 the edit lands in the studio's job folder, through %s" % via.split(" (")[0],
          out.get("error") or (imgs[0]["path"] if imgs else ""))
    if code != 200 or not imgs:
        return
    side, w, h, png, ap = saved(imgs[0]["path"])
    meta = side.get("meta") or {}
    check(png and (w, h) == (1136, 928), "9 the edit is a PNG at the source's aspect (472x388 -> 1136x928)", "%dx%d" % (w, h))
    check(side.get("kind") == "edit" and side.get("source") == EDIT_SOURCE and meta.get("denoise") == 0.6
          and meta.get("source") == EDIT_SOURCE and meta.get("workflow") == "flux-krea-gguf-img2img.json"
          and side.get("options", {}).get("strength") == 0.6,
          "9 the sidecar names the source, the kind edit, the strength and the denoise 0.6", json.dumps(meta)[:200])
    print("edit render: %s, %.1f s in ComfyUI (seed %s, denoise %s), %.1f s end to end"
          % (imgs[0]["path"], meta.get("elapsed_s") or 0, meta.get("seed"), meta.get("denoise"), secs))


def main():
    offline()
    live("--no-render" not in sys.argv)
    print("\n%d failed" % len(FAILS) if FAILS else "\nall comfy_local claims hold")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
