"""Run the heavy analysis models on Replicate's GPUs (analyze.py --remote replicate).

The API token is read from REPLICATE_API_TOKEN. In a Claude Code cloud session the network proxy injects the saved
credential into requests to api.replicate.com, so the variable may hold a placeholder there.
Files are uploaded with the Files API (they are kept by Replicate for a limited time; see replicate.com/docs).
Models (latest versions, looked up at run time):
- stems: ryan5453/demucs (htdemucs; htdemucs_ft is not offered there)
- words: victor-upmeet/whisperx (align_output=True gives word timestamps)
"""
import json, os, subprocess, sys, time, urllib.error, urllib.request

API = "https://api.replicate.com/v1"
DEMUCS = "ryan5453/demucs"
WHISPERX = "victor-upmeet/whisperx"


def _headers():
    return {"Authorization": f"Bearer {os.environ.get('REPLICATE_API_TOKEN', 'proxy-injected')}",
            "Content-Type": "application/json", "User-Agent": "ai-arranger"}


def _req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers=_headers())
    try:
        with urllib.request.urlopen(r, timeout=120) as f:
            return json.load(f)
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:400]
        hint = {401: "the API token is missing or wrong", 402: "no billing / credit on the Replicate account "
                "(replicate.com/account/billing)", 429: "rate limited, retry in a minute"}.get(e.code, "")
        raise SystemExit(f"replicate {method} {url}: HTTP {e.code} {hint}\n{msg}")


def upload(path):
    """Upload a local file -> a URL the models can read."""
    tok = os.environ.get("REPLICATE_API_TOKEN", "proxy-injected")
    out = subprocess.run(["curl", "-sS", "-f", "-m", "600", "-X", "POST", f"{API}/files",
                          "-H", f"Authorization: Bearer {tok}", "-F", f"content=@{path}"],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"replicate upload failed: {out.stderr[-500:]}")
    return json.loads(out.stdout)["urls"]["get"]


def version(model):
    return _req("GET", f"{API}/models/{model}")["latest_version"]["id"]


def run(model, inp, poll=3, timeout=3600):
    p = _req("POST", f"{API}/predictions", {"version": version(model), "input": inp})
    t0 = time.time()
    while p["status"] not in ("succeeded", "failed", "canceled"):
        if time.time() - t0 > timeout:
            raise SystemExit(f"replicate {model}: timed out ({p['id']})")
        time.sleep(poll)
        p = _req("GET", p["urls"]["get"])
    if p["status"] != "succeeded":
        raise SystemExit(f"replicate {model} {p['status']}: {str(p.get('error'))[:500]}\n{(p.get('logs') or '')[-1500:]}")
    m = p.get("metrics") or {}
    print(f"  replicate {model}: {p['status']} in {m.get('predict_time', '?')} s of GPU time", flush=True)
    return p["output"]


def download(url, path):
    r = urllib.request.Request(url, headers={"User-Agent": "ai-arranger"})
    with urllib.request.urlopen(r, timeout=600) as f, open(path, "wb") as o:
        o.write(f.read())


def stems(audio_wav, out_paths, tmpdir):
    """Demucs 4 stems -> out_paths {name: wav path}, resampled/trimmed to match audio_wav."""
    os.makedirs(tmpdir, exist_ok=True)
    flac = os.path.join(tmpdir, "audio.flac")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", audio_wav, flac], check=True)
    out = run(DEMUCS, {"audio": upload(flac), "model": "htdemucs", "format": "wav", "shifts": 2})
    for name, path in out_paths.items():
        raw = os.path.join(tmpdir, f"{name}_raw.wav")
        download(out[name], raw)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", raw, "-ar", "44100", "-ac", "2", path], check=True)


def words(vocals_wav, tmpdir, language=None):
    """WhisperX with alignment -> ([[start, end, word], ...], language)."""
    os.makedirs(tmpdir, exist_ok=True)
    flac = os.path.join(tmpdir, "vocals.flac")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", vocals_wav, "-ac", "1", "-ar", "16000", flac], check=True)
    inp = {"audio_file": upload(flac), "align_output": True, "batch_size": 16, "temperature": 0}
    if language: inp["language"] = language
    out = run(WHISPERX, inp)
    ws = []
    for s in out["segments"]:
        for w in s.get("words") or []:
            if "start" in w and "end" in w:
                ws.append([round(w["start"], 3), round(w["end"], 3), w["word"].strip()])
    return ws, out.get("detected_language")


if __name__ == "__main__":
    print(_req("GET", f"{API}/account")["username"])
