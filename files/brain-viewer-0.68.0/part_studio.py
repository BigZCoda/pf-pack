"""part_studio.py -- a part of serve.py (0.68.0, the review's finding 8: the three biggest sections of the server in files of their own).

What it holds: the image studio: providers, runs, candidates, jobs, prompts and the honest-refusal record (GET/POST /api/studio/*).

It is not imported as a module of its own. serve.py loads it with load_part() at the point where this code used to sit,
into serve.py's own namespace, so every name here is still serve.<name>: the tests that point serve.BRAIN at a scratch
folder reach it, derive_day.py's serve.live_binding() still answers, and nothing here imports anything serve.py has not.
Run serve.py, never this file.
"""

# ---- the image studio (2026-09-22, brain-viewer T-0235) ----
# The owner chose GPT image 2 and Gemini as the first two services. THE FOLDER IS THE REGISTRY:
# every *.py in skills/brain-viewer/providers/ not starting with "_" is one image service (providers/readme.md has the
# contract). They are imported here at request time, so serve.py starts whatever a provider needs; a provider that fails
# to import is listed with ready false and the import error as its reason. Each reads its own key file at the brain
# root (openai_key.txt, gemini_key.txt: in NEVER_READ, git-ignored, never exported). Pictures land in
# deliverables/studio/<job>/ with a sidecar .json beside each and a job.md that keeps the history in one line per run.
# A team copy has no keys and no studio: every route answers 403 there.
# 0.51.0 (2026-09-25): providers/comfy_local.py joined, the first provider with no key: FLUX.1 Krea on the local GPU
# through ComfyUI. Its ready() asks ComfyUI itself (is it up, is every model file listed), so it costs one short local
# call per providers listing; its graph lives in providers/comfy_workflows/, a folder this loader never imports.
# 0.51.1 (2026-09-25): the local provider edits too, as image to image (comfy_workflows/flux-krea-gguf-img2img.json);
# an edit request may carry strength (the denoise) and seed, and its Leave out and source path reach an edit that
# names negative and source, so the local edit keeps its Avoid: clause and names its source in the sidecar meta.
PROVIDERS_DIR = "providers"
STUDIO_REL = "deliverables/studio"
STUDIO_MAX_N = 4
STUDIO_TEST_PROVIDERS = {}        # id -> module; studio.test.py puts a fake provider here so no test reaches a paid API
_STUDIO_MODS = {}                 # path -> (mtime, module | Exception)
_STUDIO_LOCK = threading.Lock()


def _studio_load(path):
    import importlib.util
    mt = os.path.getmtime(path)
    hit = _STUDIO_MODS.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        spec = importlib.util.spec_from_file_location("bv_provider_" + os.path.splitext(os.path.basename(path))[0], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:          # a missing package or a syntax error: listed, not fatal
        mod = e
    _STUDIO_MODS[path] = (mt, mod)
    return mod


def studio_providers():
    """{id: module | (stem, Exception)} for every provider file, plus any injected by a test."""
    out = {}
    folder = os.path.join(HERE, PROVIDERS_DIR)
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".py") or fn.startswith("_") or fn.endswith(".test.py"):
                continue
            mod = _studio_load(os.path.join(folder, fn))
            if isinstance(mod, Exception):
                out[fn[:-3]] = (fn[:-3], mod)
            else:
                out[str(getattr(mod, "ID", fn[:-3]))] = mod
    out.update(STUDIO_TEST_PROVIDERS)
    for mod in out.values():
        if not isinstance(mod, tuple):
            mod.BRAIN = BRAIN          # the key file is read at the root of the brain this server reads
    return out


def _studio_ready(mod):
    try:
        ok, reason = mod.ready()
        return bool(ok), str(reason or "")
    except Exception as e:
        return False, _studio_line(e)


# ---- the honest studio (0.67.0; the 10/06 review, finding 7): a provider whose key file exists but whose last call was
# refused for money (402) or for rate (429) reports NOT READY, with the refusal in words, instead of "ready" because a file
# is there. Recorded per provider in viewer/studio-refusals.json (this machine's own state, git-ignored): a 429 lapses
# after an hour, a 402 stays until a run succeeds or the owner presses "try it again" (POST /api/studio/clear).
STUDIO_REFUSALS_REL = "viewer/studio-refusals.json"
STUDIO_429_SECONDS = 3600
REFUSAL_RE = re.compile(r"\b(402|429)\b|payment required|insufficient (?:balance|credit|funds|quota)|billing|exhausted|"
                        r"quota|rate.?limit|too many requests", re.I)


def studio_refusals():
    try:
        with open(os.path.join(BRAIN, STUDIO_REFUSALS_REL.replace("/", os.sep)), "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def studio_refusal_write(pid, row):
    d = studio_refusals()
    if row is None:
        if pid not in d:
            return
        d.pop(pid, None)
    else:
        d[pid] = row
    ap = os.path.join(BRAIN, STUDIO_REFUSALS_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")


def studio_refusal(pid):
    """The refusal that still stands for a provider, or None (a 429 older than an hour has lapsed)."""
    r = studio_refusals().get(pid)
    if not r:
        return None
    if str(r.get("code")) == "429" and not r.get("lasting"):
        try:
            if time.time() - dt.datetime.fromisoformat(r["at"]).timestamp() > STUDIO_429_SECONDS:
                return None
        except Exception:                                         # noqa: BLE001
            return None
    return r


def studio_refusal_record(pid, message):
    m = REFUSAL_RE.search(message or "")
    if not m:
        return None
    low = (message or "").lower()
    code = "429" if ("429" in low or "rate" in low or "too many" in low) and "402" not in low else "402"
    # a 429 that is about money (OpenAI's insufficient_quota, "check your plan and billing") stays like a 402
    lasting = code == "402" or bool(re.search(r"quota|billing|credit|insufficient|payment", low))
    row = {"code": code, "lasting": lasting, "at": dt.datetime.now().isoformat(timespec="seconds"),
           "message": _studio_line(message)[:200]}
    studio_refusal_write(pid, row)
    return row


def studio_ready_honest(pid, mod):
    """ready() as the provider file says it, then the last refusal on top of it."""
    ok, reason = _studio_ready(mod)
    if not ok:
        return ok, reason, None
    r = studio_refusal(pid)
    if r:
        what = ("refused for payment (%s)" % r["code"]) if r.get("lasting") or r["code"] == "402" else "refused for rate (429), for the next hour"
        return False, "its last call was %s on %s: %s" % (what, r["at"][:16].replace("T", " "), r["message"]), r
    return True, reason, None


def _studio_line(e):
    """A provider's message cut to one line, with anything shaped like a key taken out."""
    text = " ".join(str(e or e.__class__.__name__).split())
    text = re.sub(r"sk-[A-Za-z0-9_\-]{8,}|AIza[A-Za-z0-9_\-]{20,}", "[key]", text)
    return text[:300]


def studio_providers_api():
    rows = []
    for pid, mod in studio_providers().items():
        if isinstance(mod, tuple):
            err = mod[1]
            missing = getattr(err, "name", None) if isinstance(err, ImportError) else None
            rows.append({"id": pid, "name": pid, "ready": False, "keyFile": None, "models": [],
                         "reason": ("pip install %s" % missing) if missing else "the provider file did not load: " + _studio_line(err)})
            continue
        ok, reason, refused = studio_ready_honest(pid, mod)
        rows.append({"id": pid, "name": str(getattr(mod, "NAME", pid)), "ready": ok, "reason": reason, "refused": refused,
                     "keyFile": getattr(mod, "KEY_FILE", None), "models": list(getattr(mod, "MODELS", []) or [])})
    return {"providers": rows, "folder": "skills/brain-viewer/%s/" % PROVIDERS_DIR, "root": STUDIO_REL + "/"}


def _studio_slug(s, cap=60):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")[:cap].strip("-")


class StudioBadInput(Exception):
    """A request the server refuses before any provider is called (400)."""


def _studio_image_bytes(rel, what):
    ap = image_abs(rel)
    if not ap or not os.path.isfile(ap):
        raise StudioBadInput("%s is not an image in the brain: %s" % (what, rel))
    with open(ap, "rb") as f:
        return f.read()


def _studio_row(rel, side):
    return {"path": rel, "url": "/api/image?path=" + urllib.parse.quote(rel), "provider": side.get("provider"),
            "model": side.get("model"), "prompt": side.get("prompt"), "createdAt": side.get("createdAt"),
            "sidecar": os.path.splitext(rel)[0] + ".json", "candidate": bool(side.get("candidate")),
            "kind": side.get("kind", "generate")}


def _studio_call(fn, *args, **kw):
    """Call a provider with the options it declares: quality or image_size go only to a function that names them."""
    import inspect
    try:
        params = inspect.signature(fn).parameters
        if not any(p.kind == p.VAR_KEYWORD for p in params.values()):
            kw = {k: v for k, v in kw.items() if k in params or k in ("mask", "negative", "references")}
    except (TypeError, ValueError):
        pass
    return fn(*args, **kw)


def _studio_names(fn, name):
    """True when a provider function declares the parameter by name (a **kwargs catch-all does not count)."""
    import inspect
    try:
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def studio_run(kind, data):
    """POST /api/studio/generate and /api/studio/edit -> (code, answer). Writes the pictures, their sidecars, the job.md
    line and one CREATED log line per run."""
    data = data if isinstance(data, dict) else {}
    provs = studio_providers()
    pid = str(data.get("provider") or "")
    mod = provs.get(pid)
    if mod is None:
        return 400, {"error": "no provider named %r; the ones there are: %s" % (pid, ", ".join(sorted(provs)) or "none")}
    if isinstance(mod, tuple):
        return 400, {"error": "the %s provider did not load: %s" % (pid, _studio_line(mod[1])), "ready": False}
    ok, reason = _studio_ready(mod)
    if not ok:
        return 400, {"error": reason, "ready": False}
    models = [m.get("id") for m in (getattr(mod, "MODELS", []) or [])]
    model = str(data.get("model") or (models[0] if models else ""))
    if models and model not in models:
        return 400, {"error": "%s has no model %r; it has %s" % (pid, model, ", ".join(models))}
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        return 400, {"error": "the prompt is empty"}
    job = _studio_slug(data.get("job")) or "untitled"
    negative = data.get("negative") or None
    size = data.get("size") or None
    extra = {}
    if data.get("quality"):
        extra["quality"] = str(data["quality"])
    if data.get("imageSize"):
        extra["image_size"] = str(data["imageSize"])
    # 0.51.1: an image-to-image edit's strength (0 < s <= 1) and a fixed seed, sent to a provider that names them
    if data.get("strength") not in (None, ""):
        try:
            extra["strength"] = float(data["strength"])
        except (TypeError, ValueError):
            extra["strength"] = -1.0
        if not 0 < extra["strength"] <= 1:
            return 400, {"error": "strength is a number above 0 and at most 1"}
    if data.get("seed") not in (None, ""):
        try:
            extra["seed"] = int(data["seed"])
        except (TypeError, ValueError):
            return 400, {"error": "seed is a whole number"}
    try:
        if kind == "edit":
            src = str(data.get("image") or "")
            img = _studio_image_bytes(src, "the image")
            mask_rel = str(data.get("mask") or "") or None
            mask = _studio_image_bytes(mask_rel, "the mask") if mask_rel else None
            refs, n = [], 1
            # the Leave out list and the source's path go only to an edit that names them (the local provider does)
            named = {k: v for k, v in (("negative", negative), ("source", src)) if v and _studio_names(mod.edit, k)}
            got = _studio_call(mod.edit, img, prompt, model, mask=mask, **dict(extra, **named))
        else:
            src = mask_rel = None
            try:
                n = 2 if data.get("n") in (None, "") else int(data.get("n"))
            except (TypeError, ValueError):
                return 400, {"error": "n is a number from 1 to %d" % STUDIO_MAX_N}
            if not 1 <= n <= STUDIO_MAX_N:
                return 400, {"error": "n is a number from 1 to %d" % STUDIO_MAX_N}
            refs = [str(r) for r in (data.get("references") or []) if str(r).strip()]
            ref_bytes = [_studio_image_bytes(r, "a reference") for r in refs]
            got = _studio_call(mod.generate, prompt, model, n, size, negative=negative, references=ref_bytes or None, **extra)
    except StudioBadInput as e:
        return 400, {"error": str(e)}
    except NotImplementedError as e:
        return 400, {"error": _studio_line(e) or "%s cannot do that" % model}
    except Exception as e:
        refused = studio_refusal_record(pid, str(e))           # 0.67.0: a 402 or 429 makes the provider not ready
        return 502, {"error": _studio_line(e), "provider": pid, "refused": refused}
    if not got:
        return 502, {"error": "%s answered with no picture" % pid, "provider": pid}
    studio_refusal_write(pid, None)                            # a run that worked clears any refusal on record
    now = dt.datetime.now().astimezone()
    stamp, created = now.strftime("%Y%m%d-%H%M%S"), now.isoformat(timespec="seconds")
    folder_rel = "%s/%s" % (STUDIO_REL, job)
    folder = os.path.join(BRAIN, folder_rel.replace("/", os.sep))
    mshort = _studio_slug(model, 40) or "model"
    images = []
    with _STUDIO_LOCK:
        os.makedirs(folder, exist_ok=True)
        i = 0
        for item in got:
            blob, ext, meta = (list(item) + [None, None])[:3]
            ext = _studio_slug(ext or "png", 5) or "png"
            if ext == "jpeg":
                ext = "jpg"
            i += 1
            name = "%s-%s-%s-%d" % (stamp, _studio_slug(pid, 20), mshort, i)
            while os.path.exists(os.path.join(folder, name + "." + ext)):
                i += 1
                name = "%s-%s-%s-%d" % (stamp, _studio_slug(pid, 20), mshort, i)
            rel = "%s/%s.%s" % (folder_rel, name, ext)
            with open(os.path.join(folder, name + "." + ext), "wb") as f:
                f.write(blob)
            side = {"prompt": prompt, "negative": negative, "provider": pid, "model": model, "size": size,
                    "references": refs, "createdAt": created, "candidate": False, "kind": kind, "job": job,
                    "project": data.get("project") or None}
            if kind == "edit":
                side["source"] = src
                side["mask"] = mask_rel
            if extra:
                side["options"] = extra
            if isinstance(meta, dict) and meta:
                side["meta"] = meta
            with open(os.path.join(folder, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(side, f, ensure_ascii=False, indent=2)
            images.append(_studio_row(rel, side))
        jm = os.path.join(folder, "job.md")
        fresh = not os.path.isfile(jm)
        with open(jm, "a", encoding="utf-8", newline="\n") as f:
            if fresh:
                f.write("# Studio job: %s\n\nOne line per run: when, provider, model, how many pictures, the prompt's first 80 characters.\n\n" % job)
            f.write("- %s | %s | %s | %d %s | %s%s\n" % (created, pid, model, len(images), "edit" if kind == "edit" else "images",
                                                       " ".join(prompt.split())[:80], "" if len(prompt) <= 80 else "..."))
    log_line("%s/ -- image studio %s: %d picture%s from %s %s" % (folder_rel, kind, len(images), "" if len(images) == 1 else "s", pid, model),
             action="CREATED")
    return 200, {"job": job, "folder": folder_rel + "/", "images": images}


def _studio_sidecar(rel):
    rel = norm(rel)
    if not rel or not rel.startswith(STUDIO_REL + "/") or os.path.splitext(rel)[1].lower() not in IMAGE_EXT:
        return None, None
    ap = os.path.join(BRAIN, (os.path.splitext(rel)[0] + ".json").replace("/", os.sep))
    return rel, ap


def studio_candidate(data):
    data = data if isinstance(data, dict) else {}
    rel, ap = _studio_sidecar(str(data.get("path") or ""))
    if not rel:
        return 400, {"error": "not a studio picture: the path must be an image under %s/" % STUDIO_REL}
    if not os.path.isfile(ap):
        return 404, {"error": "no sidecar beside %s" % rel}
    if not isinstance(data.get("candidate"), bool):
        return 400, {"error": "candidate is true or false"}
    with _STUDIO_LOCK:
        with open(ap, "r", encoding="utf-8-sig") as f:
            side = json.load(f)
        side["candidate"] = data["candidate"]
        with open(ap, "w", encoding="utf-8") as f:
            json.dump(side, f, ensure_ascii=False, indent=2)
    return 200, {"path": rel, "candidate": side["candidate"], "image": _studio_row(rel, side)}


def studio_jobs():
    root = os.path.join(BRAIN, STUDIO_REL.replace("/", os.sep))
    jobs = []
    if os.path.isdir(root):
        for slug in sorted(os.listdir(root)):
            folder = os.path.join(root, slug)
            if not os.path.isdir(folder):
                continue
            imgs = []
            for fn in os.listdir(folder):
                if os.path.splitext(fn)[1].lower() not in IMAGE_EXT:
                    continue
                rel = "%s/%s/%s" % (STUDIO_REL, slug, fn)
                side = {}
                sp = os.path.join(folder, os.path.splitext(fn)[0] + ".json")
                try:
                    with open(sp, "r", encoding="utf-8-sig") as f:
                        side = json.load(f)
                except Exception:
                    side = {"createdAt": dt.datetime.fromtimestamp(os.path.getmtime(os.path.join(folder, fn))).astimezone().isoformat(timespec="seconds")}
                imgs.append(_studio_row(rel, side))
            imgs.sort(key=lambda r: (str(r.get("createdAt") or ""), r["path"]), reverse=True)
            jobs.append({"slug": slug, "count": len(imgs), "latest": imgs[0]["createdAt"] if imgs else None,
                         "candidates": sum(1 for r in imgs if r["candidate"]), "images": imgs,
                         "history": "%s/%s/job.md" % (STUDIO_REL, slug) if os.path.isfile(os.path.join(folder, "job.md")) else None})
    jobs.sort(key=lambda j: str(j["latest"] or ""), reverse=True)
    return {"jobs": jobs, "root": STUDIO_REL + "/"}


FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def studio_prompts(rel):
    """GET /api/studio/prompts?path=<.md>: every fenced code block of that file, titled by the nearest heading above it."""
    ap = read_abs(rel)
    if not ap or not ap.lower().endswith(".md"):
        return 400, {"error": "the path must be a markdown file in the brain"}
    if not os.path.isfile(ap):
        return 404, {"error": "no such file: %s" % rel}
    with open(ap, "r", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    out, title, fence, buf, start = [], "", None, [], 0
    for no, line in enumerate(lines, 1):
        if fence:
            if line.strip().startswith(fence) and not line.strip()[len(fence):].strip():
                out.append({"title": title, "text": "\n".join(buf).strip("\n"), "line": start, "lang": lang})
                fence, buf = None, []
            else:
                buf.append(line)
            continue
        m = FENCE_RE.match(line)
        if m:
            fence, buf, start, lang = m.group(1), [], no, line.strip()[len(m.group(1)):].strip()
            continue
        h = HEADING_RE.match(line)
        if h:
            title = h.group(2)
    return 200, {"path": norm(rel), "prompts": out}


def studio_api(method, path, q, body):
    """Every /api/studio/* route -> (code, answer), or None when the path is not one of them."""
    if not path.startswith("/api/studio/"):
        return None
    if PROPOSE:
        return 403, {"error": "the image studio runs on the owner's machine only; a team copy has no provider keys"}
    try:
        if method == "GET":
            if path == "/api/studio/providers":
                return 200, studio_providers_api()
            if path == "/api/studio/jobs":
                return 200, studio_jobs()
            if path == "/api/studio/prompts":
                return studio_prompts(q.get("path", [""])[0])
            return 404, {"error": "no studio route %s" % path}
        data = json.loads(body or "{}")
        if path == "/api/studio/generate":
            return studio_run("generate", data)
        if path == "/api/studio/edit":
            return studio_run("edit", data)
        if path == "/api/studio/candidate":
            return studio_candidate(data)
        if path == "/api/studio/clear":
            # 0.67.0: "try it again" -- the owner says the account is paid now; the next run records whatever it meets
            pid = str(data.get("provider") or "")
            if pid not in studio_providers():
                return 400, {"error": "no provider named %r" % pid}
            studio_refusal_write(pid, None)
            return 200, {"ok": True, "provider": pid}
        return 404, {"error": "no studio route %s" % path}
    except json.JSONDecodeError:
        return 400, {"error": "the body is not JSON"}
