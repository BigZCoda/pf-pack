#!/usr/bin/env python3
"""studio.test.py -- the image studio's back half (brain-viewer T-0235), checked with no network and no paid API.

  python skills/brain-viewer/studio.test.py

The server is imported, pointed at a throwaway brain folder, and given a FAKE provider that answers with a 1x1 PNG.
The real provider files are loaded too, but only asked whether they are ready (with no key file they are not).
A throwaway HTTP server on a free port checks that the handler actually routes /api/studio/* to the studio code.

Claims:
 1. the provider folder loads: openai and gemini are listed, and with no key file each says ready false with
    "create <key file> at the brain root, one line, the key alone"
 2. a generate run writes <yyyymmdd-hhmmss>-<provider>-<model>-<n>.<ext> in deliverables/studio/<job>/, a sidecar
    beside each with the named fields and candidate false, and one job.md line for the run
 3. the negative list reaches the provider apart from the prompt, and n outside 1..4 is refused
 4. an edit writes one picture whose sidecar names its source; a provider failure is a 502 with one line and no key
 5. the candidate flag flips in the sidecar, and the jobs listing counts it
 6. the prompts of the booth deliverable come back as four blocks, each titled by its heading
 7. in a team copy every studio route answers 403
 8. the handler routes GET and POST /api/studio/* (and /studio is a page with a help entry)
 9. fal.ai (added 2026-09-22): the module loads with its models, says how to fix a missing fal_key.txt, and against a
    FAKE urlopen runs submit, poll, result, download into (bytes, ext, meta) with the request id and model in meta,
    sends the key only to queue.fal.run, turns a palette into Recraft colours, and gives fal's last word on a timeout

Exit 0 when all hold; 1 with the failures named.
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import types
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import serve  # noqa: E402

FAILS = []
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c63f8cfc0f01f0005000201a1e6c5d80000000049454e44ae426082")
FAKE_KEY = "sk-fake_test_fixture_not_a_key"


def check(ok, what, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", what, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(what)


def fake_provider():
    m = types.ModuleType("bv_provider_fake")
    m.ID, m.NAME, m.KEY_FILE = "fake", "Fake", "fake_key.txt"
    m.MODELS = [{"id": "fake-img-1", "name": "Fake 1", "sizes": ["1024x1024"], "edits": True, "notes": "test"}]
    m.calls = []

    def ready():
        return True, ""

    def generate(prompt, model, n, size_or_aspect, negative=None, references=None):
        m.calls.append({"prompt": prompt, "negative": negative, "n": n, "refs": len(references or [])})
        if prompt == "boom":
            raise RuntimeError("upstream said no\nsecond line with %s in it" % FAKE_KEY)
        return [(PNG, "png", {"fake": True}) for _ in range(n)]

    def edit(image_bytes, prompt, model, mask=None):
        m.calls.append({"edit": True, "bytes": len(image_bytes), "mask": mask is not None})
        return [(PNG, "png", {})]

    m.ready, m.generate, m.edit = ready, generate, edit
    return m


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


def fake_fal(status_seq, files):
    """A urlopen that plays fal: submit, status (from status_seq, the last one repeating), result, the file host."""
    seen = []
    seq = list(status_seq)

    def urlopen(req, timeout=None):
        url, method = req.full_url, req.get_method()
        seen.append({"method": method, "url": url, "auth": req.get_header("Authorization"),
                     "body": json.loads(req.data.decode("utf-8")) if req.data else None})
        if url.startswith("https://files.fal.test/"):
            return FakeResponse(PNG, "image/png")
        if method == "POST":
            b = "https://queue.fal.run/%s/requests/req-123" % url[len("https://queue.fal.run/"):]
            return FakeResponse({"request_id": "req-123", "status_url": b + "/status", "response_url": b,
                                 "cancel_url": b + "/cancel", "queue_position": 2})
        if method == "PUT":
            return FakeResponse({"status": "CANCELLATION_REQUESTED"})
        if "/status" in url:
            return FakeResponse(seq.pop(0) if len(seq) > 1 else seq[0])
        return FakeResponse({"images": files, "seed": 7})
    return urlopen, seen


def fal_checks(fal):
    check(fal is not None and not isinstance(fal, tuple), "the fal provider loads from providers/fal_image.py",
          repr(fal[1]) if isinstance(fal, tuple) else "")
    if fal is None or isinstance(fal, tuple):
        return
    ids = [m["id"] for m in fal.MODELS]
    check({"flux-2-pro", "recraft-v3", "recraft-v3-svg", "ideogram-v3", "nano-banana-pro", "gpt-image-2"} <= set(ids)
          and ids[0] == "flux-2-pro" and all(m.get("notes") and "edits" in m and m.get("endpoint") for m in fal.MODELS),
          "fal lists its models, Flux first, each with an endpoint, edits and notes", " ".join(ids))
    ok, reason = fal.ready()
    check(ok is False and reason == "create fal_key.txt at the brain root, one line, the key alone",
          "fal is not ready without fal_key.txt, and says how to fix it", reason)
    key = "0123abcd-0000-4000-8000-00000000abcd:0123456789abcdef0123456789abcdef"
    saved = (fal._key, urllib.request.urlopen, fal._sleep, fal._clock)
    clock = [0.0]
    fal._key = lambda: key
    fal._sleep = lambda sec: clock.__setitem__(0, clock[0] + sec)
    fal._clock = lambda: clock[0]
    try:
        files = [{"url": "https://files.fal.test/a.png", "content_type": "image/png", "width": 1, "height": 1}]
        urlopen, seen = fake_fal([{"status": "IN_QUEUE", "queue_position": 1}, {"status": "IN_PROGRESS"},
                                  {"status": "COMPLETED"}], files)
        urllib.request.urlopen = urlopen
        got = fal.generate("an orrery", "flux-2-pro", 1, "landscape_16_9", negative=["neon"])
        steps = [(c["method"], c["url"].split("?")[0].replace("https://queue.fal.run/fal-ai/flux-2-pro", "Q")) for c in seen]
        check(steps == [("POST", "Q"), ("GET", "Q/requests/req-123/status"), ("GET", "Q/requests/req-123/status"),
                        ("GET", "Q/requests/req-123/status"), ("GET", "Q/requests/req-123"),
                        ("GET", "https://files.fal.test/a.png")],
              "fal runs submit, poll until COMPLETED, result, download", str(steps))
        check(len(got) == 1 and got[0][0] == PNG and got[0][1] == "png" and got[0][2].get("request_id") == "req-123"
              and got[0][2].get("model") == "flux-2-pro" and got[0][2].get("endpoint") == "fal-ai/flux-2-pro",
              "fal returns (bytes, ext, meta) with the request id, model and endpoint", str(got[0][1:] if got else None))
        check(all(c["auth"] == "Key " + key for c in seen if c["url"].startswith("https://queue.fal.run/"))
              and all(c["auth"] is None for c in seen if c["url"].startswith("https://files.fal.test/")),
              "the key goes as Key <key> to the queue and never to the file host")
        body = seen[0]["body"]
        check(body.get("image_size") == "landscape_16_9" and "Avoid: neon" in body.get("prompt", ""),
              "the size and the negative list reach the Flux request")

        urlopen, seen = fake_fal([{"status": "COMPLETED"}], files)
        urllib.request.urlopen = urlopen
        fal.generate("a booth backdrop", "recraft-v3", 1, "square_hd", palette=["#1a2b3c", "fff"],
                     style="vector_illustration/bold_stroke")
        rb = seen[0]["body"]
        check(seen[0]["url"] == "https://queue.fal.run/fal-ai/recraft/v3/text-to-image"
              and rb.get("colors") == [{"r": 26, "g": 43, "b": 60}, {"r": 255, "g": 255, "b": 255}]
              and rb.get("style") == "vector_illustration/bold_stroke",
              "a palette of hex strings becomes Recraft's colors, and the style passes through", json.dumps(rb)[:160])
        urlopen, seen = fake_fal([{"status": "COMPLETED"}], files)
        urllib.request.urlopen = urlopen
        fal.generate("no palette", "recraft-v3", 1, None)
        check("colors" not in seen[0]["body"], "the palette is optional")

        try:
            fal.edit(PNG, "change the sky", "flux-2-pro", mask=PNG)
            check(False, "a mask on a model that takes none raises NotImplementedError")
        except NotImplementedError as e:
            check("no mask" in str(e), "a mask on a model that takes none raises NotImplementedError", str(e))

        clock[0] = 0.0
        urlopen, seen = fake_fal([{"status": "IN_QUEUE", "queue_position": 9,
                                   "logs": [{"message": "waiting for a GPU"}]}], files)
        urllib.request.urlopen = urlopen
        try:
            fal.generate("slow", "flux-2-pro", 1, None)
            check(False, "a request past 180 seconds fails with fal's last word")
        except Exception as e:
            msg = str(e)
            check("180 seconds" in msg and "IN_QUEUE" in msg and "waiting for a GPU" in msg and key not in msg,
                  "a request past 180 seconds fails with fal's last word", msg)
            check(any(c["method"] == "PUT" and c["url"].endswith("/cancel") for c in seen),
                  "and the queued request is cancelled")
    finally:
        fal._key, urllib.request.urlopen, fal._sleep, fal._clock = saved


def main():
    real_brain = serve.BRAIN
    tmp = tempfile.mkdtemp(prefix="bv-studio-test-")
    booth = "deliverables/genius-booth-backdrop-directions-2026-09-22.md"
    try:
        os.makedirs(os.path.join(tmp, "deliverables"))
        src = os.path.join(real_brain, booth.replace("/", os.sep))
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(tmp, booth.replace("/", os.sep)))
        serve.BRAIN = tmp
        fake = fake_provider()
        serve.STUDIO_TEST_PROVIDERS["fake"] = fake

        # 1
        rows = {r["id"]: r for r in serve.studio_providers_api()["providers"]}
        check({"openai", "gemini", "fake"} <= set(rows), "the providers folder is the registry", " ".join(sorted(rows)))
        for pid, key in (("openai", "openai_key.txt"), ("gemini", "gemini_key.txt")):
            r = rows.get(pid, {})
            check(r.get("ready") is False and r.get("reason") == "create %s at the brain root, one line, the key alone" % key,
                  "%s is not ready without %s, and says how to fix it" % (pid, key), r.get("reason", ""))
            check(bool(r.get("models")) and all("edits" in mm and "notes" in mm for mm in r["models"]),
                  "%s lists its models with edits and notes" % pid)
        check("gpt-image-2" in [mm["id"] for mm in rows.get("openai", {}).get("models", [])], "gpt-image-2 is wired")
        for k in ("openai_key.txt", "gemini_key.txt", "fal_key.txt"):
            check(k in serve.NEVER_READ, "%s is never served" % k)

        # 2
        code, out = serve.studio_api("POST", "/api/studio/generate", {}, json.dumps(
            {"provider": "fake", "model": "fake-img-1", "prompt": "an orrery, engraved", "negative": "photo, neon",
             "n": 2, "job": "Genius Booth!", "project": "pf-build"}))
        check(code == 200, "generate answers 200", "%s %s" % (code, out.get("error", "")))
        imgs = out.get("images") or []
        check(out.get("job") == "genius-booth" and len(imgs) == 2, "the job is slugged and two pictures come back", str(out.get("job")))
        name_re = re.compile(r"^deliverables/studio/genius-booth/\d{8}-\d{6}-fake-fake-img-1-[12]\.png$")
        check(all(name_re.match(i["path"]) for i in imgs), "the files are named <stamp>-<provider>-<model>-<n>.<ext>",
              " ".join(i["path"] for i in imgs))
        check(all(i["url"].startswith("/api/image?path=deliverables/studio/") for i in imgs), "each picture is served by /api/image")
        check(all(os.path.isfile(os.path.join(tmp, i["path"])) for i in imgs), "the pictures are on disk")
        side = {}
        if imgs:
            with io.open(os.path.join(tmp, imgs[0]["sidecar"]), encoding="utf-8") as f:
                side = json.load(f)
        want = {"prompt", "negative", "provider", "model", "size", "references", "createdAt", "candidate"}
        check(want <= set(side) and side.get("candidate") is False and side.get("negative") == "photo, neon"
              and side.get("prompt") == "an orrery, engraved", "the sidecar holds the named fields, candidate false",
              " ".join(sorted(set(side))))
        img_path = serve.image_abs(imgs[0]["path"]) if imgs else None
        check(bool(img_path) and os.path.isfile(img_path), "/api/image's rule accepts deliverables/studio/")
        jm = os.path.join(tmp, "deliverables", "studio", "genius-booth", "job.md")
        lines = [l for l in io.open(jm, encoding="utf-8").read().splitlines() if l.startswith("- ")] if os.path.isfile(jm) else []
        check(len(lines) == 1 and "| fake | fake-img-1 | 2 images | an orrery, engraved" in lines[0], "job.md has one line for the run",
              lines[0] if lines else "no job.md")

        # 3
        last = fake.calls[-1] if fake.calls else {}
        check(last.get("negative") == "photo, neon" and last.get("prompt") == "an orrery, engraved",
              "the negative list reaches the provider apart from the prompt")
        code5, _ = serve.studio_api("POST", "/api/studio/generate", {}, json.dumps(
            {"provider": "fake", "model": "fake-img-1", "prompt": "x", "n": 5, "job": "j"}))
        code0, _ = serve.studio_api("POST", "/api/studio/generate", {}, json.dumps(
            {"provider": "fake", "model": "fake-img-1", "prompt": "x", "n": 0, "job": "j"}))
        check(code5 == 400 and code0 == 400, "n outside 1..4 is refused")
        coder, outr = serve.studio_api("POST", "/api/studio/generate", {}, json.dumps(
            {"provider": "fake", "model": "fake-img-1", "prompt": "x", "job": "j", "references": [imgs[0]["path"]]}))
        check(coder == 200 and fake.calls[-1].get("refs") == 1, "a reference path reaches the provider as bytes")
        codeb, _ = serve.studio_api("POST", "/api/studio/generate", {}, json.dumps(
            {"provider": "fake", "model": "fake-img-1", "prompt": "x", "job": "j", "references": ["APIZZLE.txt"]}))
        check(codeb == 400, "a reference that is not an image in the brain is refused")

        # 4
        code, eout = serve.studio_api("POST", "/api/studio/edit", {}, json.dumps(
            {"provider": "fake", "model": "fake-img-1", "image": imgs[0]["path"], "prompt": "make it brass", "job": "genius-booth"}))
        eimg = (eout.get("images") or [{}])[0]
        eside = {}
        if eimg.get("sidecar"):
            with io.open(os.path.join(tmp, eimg["sidecar"]), encoding="utf-8") as f:
                eside = json.load(f)
        check(code == 200 and eside.get("source") == imgs[0]["path"] and eside.get("kind") == "edit",
              "an edit writes one picture whose sidecar names its source")
        code, bout = serve.studio_api("POST", "/api/studio/generate", {}, json.dumps(
            {"provider": "fake", "model": "fake-img-1", "prompt": "boom", "job": "genius-booth"}))
        msg = bout.get("error", "")
        check(code == 502 and "\n" not in msg and FAKE_KEY not in msg and "upstream said no" in msg,
              "a provider failure is a 502 with one line and no key", msg)
        code, _ = serve.studio_api("POST", "/api/studio/generate", {}, json.dumps({"provider": "openai", "prompt": "x", "job": "j"}))
        check(code == 400, "a provider with no key is refused before any call")

        # 5
        code, cout = serve.studio_api("POST", "/api/studio/candidate", {}, json.dumps({"path": imgs[0]["path"], "candidate": True}))
        with io.open(os.path.join(tmp, imgs[0]["sidecar"]), encoding="utf-8") as f:
            flipped = json.load(f).get("candidate")
        check(code == 200 and flipped is True, "the candidate flag flips to true in the sidecar")
        code, jout = serve.studio_api("GET", "/api/studio/jobs", {}, None)
        jobs = {j["slug"]: j for j in jout.get("jobs", [])}
        gb = jobs.get("genius-booth", {})
        check(code == 200 and gb.get("count") == 3 and gb.get("candidates") == 1 and bool(gb.get("latest")),
              "the jobs listing counts pictures and candidates", "count %s candidates %s" % (gb.get("count"), gb.get("candidates")))
        check(all({"path", "url", "provider", "model", "prompt", "createdAt", "sidecar"} <= set(i) for i in gb.get("images", [])),
              "each listed picture carries the contract's fields")
        serve.studio_api("POST", "/api/studio/candidate", {}, json.dumps({"path": imgs[0]["path"], "candidate": False}))
        with io.open(os.path.join(tmp, imgs[0]["sidecar"]), encoding="utf-8") as f:
            check(json.load(f).get("candidate") is False, "and back to false")
        code, _ = serve.studio_api("POST", "/api/studio/candidate", {}, json.dumps({"path": "people/x.png", "candidate": True}))
        check(code == 400, "a path outside deliverables/studio/ is refused")

        # 6
        code, pout = serve.studio_api("GET", "/api/studio/prompts", {"path": [booth]}, None)
        ps = pout.get("prompts") or []
        check(code == 200 and len(ps) == 4, "the booth deliverable gives four prompt blocks", str(len(ps)))
        check([p["title"].split(":")[0] for p in ps] == ["Prompt 1", "Prompt 2", "Prompt 3", "Prompt 4"]
              and all(p["text"].strip() for p in ps), "each is titled by the heading above it", " / ".join(p["title"] for p in ps))

        # 8 (before 7, while this copy is the owner's)
        srv = serve.ThreadingHTTPServer(("127.0.0.1", 0), serve.H)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/studio/providers" % port, timeout=10) as r:
                got = json.loads(r.read().decode("utf-8"))
            check(any(p["id"] == "openai" for p in got.get("providers", [])), "GET /api/studio/providers is routed")
            req = urllib.request.Request("http://127.0.0.1:%d/api/studio/candidate" % port, method="POST",
                                         data=json.dumps({"path": imgs[0]["path"], "candidate": True}).encode("utf-8"))
            with urllib.request.urlopen(req, timeout=10) as r:
                check(json.loads(r.read().decode("utf-8")).get("candidate") is True, "POST /api/studio/candidate is routed")
        finally:
            srv.shutdown()
        check(serve.PAGES.get("/studio") == "studio.html", "/studio is a page route")
        with io.open(os.path.join(HERE, "help.json"), encoding="utf-8-sig") as f:
            check("/studio" in (json.load(f).get("pages") or {}), "help.json has a /studio entry")

        # 7
        saved = (serve.PROPOSE, serve.MEMBER)
        serve.PROPOSE, serve.MEMBER = True, "dani"
        try:
            codes = [serve.studio_api(m, p, {}, "{}")[0] for m, p in
                     (("GET", "/api/studio/providers"), ("GET", "/api/studio/jobs"), ("GET", "/api/studio/prompts"),
                      ("POST", "/api/studio/generate"), ("POST", "/api/studio/edit"), ("POST", "/api/studio/candidate"))]
        finally:
            serve.PROPOSE, serve.MEMBER = saved
        check(codes == [403] * 6, "a team copy gets 403 on every studio route", str(codes))
    finally:
        serve.BRAIN = real_brain
        serve.STUDIO_TEST_PROVIDERS.pop("fake", None)
        shutil.rmtree(tmp, ignore_errors=True)

    # 9
    fal_checks(serve.studio_providers().get("fal"))

    print("\n%d failed" % len(FAILS) if FAILS else "\nall studio claims hold")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
