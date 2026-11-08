"""Generate a song with Suno (through sunoapi.org), save the MP3s as candidates, and promote the one the user approves.

The human gate sits between `generate` and `approve`: nothing is analysed or arranged until the user has listened.

usage:
  suno_fetch.py generate A --style "bossa nova, female vocal" [--lyrics lyrics.txt | --prompt "idea"] [--title T]
                           [--instrumental] [--model V6] [--duration 120] [--negative "..."] [--timeout 600]
  suno_fetch.py cover    A --audio my.mp3 --style "a cappella, five-part harmony, beatbox" [--lyrics f.txt] [--title T]
                           [--audio-weight 0.6] [--instrumental] [--model V6]   # re-make YOUR OWN recording in another style
  suno_fetch.py status   A                  # list candidates and whether one is approved
  suno_fetch.py approve  A N [--name song]  # copy candidate N to A/<name>.mp3 (+ lyrics.txt), mark A/suno/APPROVED
  suno_fetch.py reject   A                  # clear the candidates so the next `generate` starts clean

A is the per-song folder (arrangements/<song>). Layout written:
  A/suno/candidates/1.mp3, 2.mp3 ... + meta.json (task id, params, titles, durations)
  A/suno/APPROVED       (json: which candidate, when) -- the arranging pipeline starts only when it exists

`cover` uploads the audio to the provider's temporary file host (SUNO_UPLOAD_BASE, default https://sunoapiorg.redpandaai.co,
deleted after 3 days), then calls /api/v1/generate/upload-cover (always custom mode; source audio up to 8 min).
Only use it on recordings you own or have the rights to.

Auth: env SUNO_API_KEY (Bearer). Optional SUNO_API_BASE (default https://apibox.erweima.ai).
Custom mode is used when --lyrics is given (the lyrics are sung as written); otherwise --prompt/--style describe the song.
Stdlib only.
"""
import argparse, json, os, shutil, sys, time, urllib.request, urllib.error, datetime

BASE = os.environ.get("SUNO_API_BASE", "https://apibox.erweima.ai").rstrip("/")
UPLOAD_BASE = os.environ.get("SUNO_UPLOAD_BASE", "https://sunoapiorg.redpandaai.co").rstrip("/")
FAILED = {"CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR"}


def die(msg):
    raise SystemExit(f"suno_fetch: {msg}")


def api(method, path, body=None):
    key = os.environ.get("SUNO_API_KEY")
    if not key:
        die("SUNO_API_KEY is not set")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "ai-arranger/suno_fetch"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        die(f"HTTP {e.code} on {path}: {e.read()[:300]!r}")
    except urllib.error.URLError as e:
        die(f"network error on {path}: {e.reason}")
    if out.get("code") != 200:
        die(f"API error {out.get('code')}: {out.get('msg')}")
    return out["data"]


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-arranger/suno_fetch"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".part", "wb") as f:
        shutil.copyfileobj(r, f)
    if os.path.getsize(dest + ".part") < 10_000:
        os.remove(dest + ".part"); die(f"download of {url} is too small to be an MP3")
    os.replace(dest + ".part", dest)


def paths(A):
    S = os.path.join(os.path.abspath(A), "suno")
    return S, os.path.join(S, "candidates"), os.path.join(S, "APPROVED")


def upload(path):
    """multipart upload to the provider's file host; returns a temporary download URL."""
    key = os.environ.get("SUNO_API_KEY")
    if not key: die("SUNO_API_KEY is not set")
    name = os.path.basename(path); bd = "----acap" + str(int(time.time() * 1000))
    parts = [f'--{bd}\r\nContent-Disposition: form-data; name="uploadPath"\r\n\r\nacap\r\n'.encode(),
             f'--{bd}\r\nContent-Disposition: form-data; name="fileName"\r\n\r\n{name}\r\n'.encode(),
             f'--{bd}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode(),
             open(path, "rb").read(), f"\r\n--{bd}--\r\n".encode()]
    req = urllib.request.Request(UPLOAD_BASE + "/api/file-stream-upload", data=b"".join(parts), method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={bd}", "User-Agent": "ai-arranger/suno_fetch"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r: out = json.load(r)
    except urllib.error.HTTPError as e:
        die(f"upload HTTP {e.code}: {e.read()[:300]!r}")
    except urllib.error.URLError as e:
        die(f"upload network error: {e.reason}")
    d = out.get("data") or {}
    url = d.get("downloadUrl") or d.get("fileUrl")
    if not out.get("success", out.get("code") == 200) or not url: die(f"upload failed: {out}")
    return url


def run_task(a, path, body):
    S, C, _ = paths(a.A)
    task = api("POST", path, body)["taskId"]
    print(f"task {task} submitted, polling...", flush=True)
    t0 = time.time(); last = None
    while True:
        d = api("GET", f"/api/v1/generate/record-info?taskId={task}")
        st = d.get("status")
        if st != last:
            print(f"  [{int(time.time() - t0):4d}s] {st}", flush=True); last = st
        if st == "SUCCESS": break
        if st in FAILED: die(f"generation failed: {st} {d.get('errorMessage') or ''}")
        if time.time() - t0 > a.timeout: die(f"timed out after {a.timeout}s (task {task})")
        time.sleep(a.interval)
    tracks = (d.get("response") or {}).get("sunoData") or []
    if not tracks: die("task succeeded but returned no tracks")
    shutil.rmtree(C, ignore_errors=True); os.makedirs(C)
    meta = {"task": task, "params": {k: v for k, v in body.items() if k != "callBackUrl"}, "tracks": []}
    for i, t in enumerate(tracks, 1):
        url = t.get("audio_url") or t.get("source_audio_url")
        if not url: print(f"  candidate {i}: no audio URL yet, skipped"); continue
        dest = os.path.join(C, f"{i}.mp3"); download(url, dest)
        meta["tracks"].append({"n": i, "id": t.get("id"), "title": t.get("title"), "duration": t.get("duration"),
                               "tags": t.get("tags"), "file": dest})
    json.dump(meta, open(os.path.join(S, "meta.json"), "w"), indent=1, ensure_ascii=False)
    print("\nCandidates ready for listening (NOT approved yet):")
    for t in meta["tracks"]:
        print(f"  {t['n']}: {t['file']}  {t.get('duration') or '?'}s  {t.get('title') or ''}")
    print(f"\nNext: listen, then `suno_fetch.py approve {a.A} N` (or `reject` and generate again).")


def check_free(a):
    S, _, _ = paths(a.A)
    if os.path.exists(os.path.join(S, "APPROVED")):
        die("a candidate is already approved; run `reject` first to start over")


def cmd_generate(a):
    check_free(a)
    lyrics = open(a.lyrics, encoding="utf-8").read().strip() if a.lyrics else None
    if not (lyrics or a.style or a.prompt):
        die("give at least --style, --prompt or --lyrics")
    custom = bool(lyrics)
    body = {"customMode": custom, "instrumental": a.instrumental, "model": a.model, "callBackUrl": a.callback}
    if custom:
        body["lyrics"] = lyrics
        body["style"] = a.style or ""
        body["title"] = (a.title or "Untitled")[:80]
        if a.negative: body["negativeTags"] = a.negative
        if a.duration: body["duration"] = a.duration
    else:
        body["prompt"] = a.prompt or a.style
        if a.style: body["style"] = a.style
    run_task(a, "/api/v1/generate", body)


def cmd_cover(a):
    check_free(a)
    if not os.path.isfile(a.audio): die(f"no such file: {a.audio}")
    lyrics = open(a.lyrics, encoding="utf-8").read().strip() if a.lyrics else None
    url = upload(a.audio); print(f"uploaded -> {url}", flush=True)
    body = {"uploadUrl": url, "instrumental": a.instrumental, "model": a.model, "callBackUrl": a.callback,
            "style": a.style or "", "title": (a.title or os.path.splitext(os.path.basename(a.audio))[0])[:80]}
    if lyrics: body["lyrics"] = lyrics
    if a.audio_weight is not None: body["audioWeight"] = a.audio_weight
    if a.negative: body["negativeTags"] = a.negative
    if a.duration: body["duration"] = a.duration
    run_task(a, "/api/v1/generate/upload-cover", body)


def cmd_status(a):
    S, C, AP = paths(a.A)
    m = os.path.join(S, "meta.json")
    if not os.path.exists(m): print("no candidates"); return
    meta = json.load(open(m))
    print(f"task {meta['task']}")
    for t in meta["tracks"]: print(f"  {t['n']}: {t['file']}  {t.get('duration')}s  {t.get('title') or ''}")
    print("APPROVED:", open(AP).read() if os.path.exists(AP) else "no")


def cmd_approve(a):
    S, C, AP = paths(a.A)
    src = os.path.join(C, f"{a.N}.mp3")
    if not os.path.exists(src): die(f"no candidate {a.N} in {C}")
    A = os.path.abspath(a.A); dest = os.path.join(A, f"{a.name}.mp3")
    shutil.copyfile(src, dest)
    m = os.path.join(S, "meta.json")
    meta = json.load(open(m)) if os.path.exists(m) else {}
    lyr = (meta.get("params") or {}).get("lyrics")
    if lyr and not os.path.exists(os.path.join(A, "lyrics.txt")):
        open(os.path.join(A, "lyrics.txt"), "w", encoding="utf-8").write(lyr + "\n")
    json.dump({"candidate": a.N, "mp3": dest, "task": meta.get("task"),
               "at": datetime.datetime.now().isoformat(timespec="seconds")}, open(AP, "w"))
    print(f"approved candidate {a.N} -> {dest}")
    print(f"Next: analyze.py {dest} {A}/work" + (f" --lyrics {A}/lyrics.txt" if lyr else ""))


def cmd_reject(a):
    S, C, AP = paths(a.A)
    shutil.rmtree(C, ignore_errors=True)
    for f in (AP, os.path.join(S, "meta.json")):
        if os.path.exists(f): os.remove(f)
    print("candidates cleared")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("A")
    g.add_argument("--style"); g.add_argument("--prompt"); g.add_argument("--lyrics"); g.add_argument("--title")
    g.add_argument("--instrumental", action="store_true"); g.add_argument("--model", default="V6")
    g.add_argument("--duration", type=int); g.add_argument("--negative")
    g.add_argument("--callback", default="https://example.com/unused", help="required by the API; polling is used instead")
    g.add_argument("--timeout", type=int, default=600); g.add_argument("--interval", type=int, default=10)
    c = sub.add_parser("cover"); c.add_argument("A"); c.add_argument("--audio", required=True)
    c.add_argument("--style"); c.add_argument("--lyrics"); c.add_argument("--title"); c.add_argument("--negative")
    c.add_argument("--instrumental", action="store_true"); c.add_argument("--model", default="V6")
    c.add_argument("--audio-weight", type=float, help="0-1, how closely to follow the source audio"); c.add_argument("--duration", type=int)
    c.add_argument("--callback", default="https://example.com/unused"); c.add_argument("--timeout", type=int, default=900)
    c.add_argument("--interval", type=int, default=10)
    s = sub.add_parser("status"); s.add_argument("A")
    p = sub.add_parser("approve"); p.add_argument("A"); p.add_argument("N", type=int); p.add_argument("--name", default="song")
    r = sub.add_parser("reject"); r.add_argument("A")
    a = ap.parse_args()
    {"generate": cmd_generate, "cover": cmd_cover, "status": cmd_status, "approve": cmd_approve, "reject": cmd_reject}[a.cmd](a)


if __name__ == "__main__":
    main()
