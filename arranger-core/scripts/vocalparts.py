#!/usr/bin/env python3
"""Split a vocal ensemble recording into voice lines (soprano / alto / tenor / bass pitch tracks and notes).

    $ACAP_PY vocalparts.py AUDIO OUTDIR [--models DIR] [--voas cnn] [--min-note 0.12] [--bpm 96]

Chain (Helena Cuesta's models, MIT licence, run here in PyTorch from their saved Keras weights):
1. Late/Deep multi-F0 CNN (Cuesta, McFee & Gomez, ISMIR 2020): HCQT magnitude + phase differentials ->
   pitch salience (360 bins, 20 cents, C1..C7, 11.6 ms frames): every pitch sung at each moment.
2. Voice assignment, two ways:
   - order (default): the k strongest pitches of each frame, kept in pitch order and followed by continuity; any
     ranges, any number of voices (--voices T1,A,Br,B). Voices that cross are swapped back into pitch order.
   - voas: VoasCNN (Cuesta & Gomez, TISMIR 2022), four salience maps for S, A, T, B. Trained on choirs: it mislabels
     voices outside SATB ranges (a bass below ~A2 comes out as the soprano), so it does not suit a very low bass.
3. Here: each voice's F0 track -> notes (median-filtered, rounded to semitones, short blips merged).
Outputs in OUTDIR: multif0.csv (time, all pitches), voices.csv (time, S, A, T, B in Hz, 0 = silent),
notes_<V>.csv (start, end, midi), voices.mid (one track per voice), voices.png (piano roll), salience.npy.

The models were trained on SATB choirs and synthetic quartets. On pop a cappella, run it on the backing-vocal stem
(karaoke split) so the lead is not one of the four voices, and check the result by ear (audition.py): reverb,
doubled parts and more than four voices all make the assignment less reliable.
Models: `git clone https://github.com/helenacuesta/multif0-estimation-polyvocals` and
`.../voas-vocal-quartets` into --models (default ~/.cache/acappella/cuesta); setup.sh does it.
"""
import argparse, csv, json, os, sys
import numpy as np

MODELS = os.path.expanduser(os.environ.get("ACAP_CUESTA", "~/.cache/acappella/cuesta"))
SR, HOP, FMIN, BPO, N_OCT, HARM = 22050, 256, 32.7, 60, 6, (1, 2, 3, 4, 5)
VOICES = ("S", "A", "T", "B")
VOAS_THRESH = {"cnn": (0.23, 0.17, 0.15, 0.17)}


# ------------------------------------------------------------------------------------- Keras config -> torch
def load_keras(path):
    """Rebuild a functional Keras model (Conv2D / BatchNormalization / Concatenate / squeeze) as a torch module.
    Only numbers are read from the file (h5py); no pickled code is executed."""
    import h5py, torch, torch.nn.functional as F
    f = h5py.File(path, "r")
    cfg = json.loads(f.attrs["model_config"])["config"]
    W = f["model_weights"] if "model_weights" in f else f

    def weights(name):
        g = W[name]
        names = [n.decode() if isinstance(n, bytes) else n for n in g.attrs["weight_names"]]
        return {n.split("/")[-1].split(":")[0]: torch.tensor(np.array(g[n])) for n in names}

    layers = []
    for L in cfg["layers"]:
        c, cls = L["config"], L["class_name"]
        ins = [x[0] for x in L["inbound_nodes"][0]] if L["inbound_nodes"] else []
        p = None
        if cls == "Conv2D":
            w = weights(L["name"]); kh, kw = c["kernel_size"]
            p = dict(k=w["kernel"].permute(3, 2, 0, 1).contiguous(), b=w["bias"], kh=kh, kw=kw, act=c["activation"])
        elif cls == "BatchNormalization":
            w = weights(L["name"])
            p = dict(scale=w["gamma"] / torch.sqrt(w["moving_variance"] + c["epsilon"]), mean=w["moving_mean"], beta=w["beta"])
        layers.append((L["name"], cls, ins, p))
    inputs = [x[0] for x in cfg["input_layers"]]
    outputs = [x[0] for x in cfg["output_layers"]]

    def run(*xs):
        """xs: NCHW tensors (one per model input) -> list of (N, H, W) outputs"""
        t = dict(zip(inputs, xs))
        for name, cls, ins, p in layers:
            if cls == "InputLayer": continue
            x = [t[i] for i in ins]
            if cls == "Conv2D":
                ph, pw = p["kh"] - 1, p["kw"] - 1      # TF 'same': the extra pixel goes after
                y = F.conv2d(F.pad(x[0], (pw // 2, pw - pw // 2, ph // 2, ph - ph // 2)), p["k"], p["b"])
                y = torch.relu(y) if p["act"] == "relu" else torch.sigmoid(y) if p["act"] == "sigmoid" else y
            elif cls == "BatchNormalization":
                y = (x[0] - p["mean"][None, :, None, None]) * p["scale"][None, :, None, None] + p["beta"][None, :, None, None]
            elif cls == "Concatenate":
                y = torch.cat(x, 1)
            else:                                    # Lambda / TensorFlowOpLayer: squeeze of the channel axis
                y = x[0]
            t[name] = y
        return [t[o][:, 0] if t[o].dim() == 4 else t[o] for o in outputs]
    return run


# ------------------------------------------------------------------------------------- features (as pumpp 0.6)
def hcqt(y):
    import librosa
    n_frames = int(librosa.time_to_frames(len(y) / SR, sr=SR, hop_length=HOP))
    mag, dph = [], []
    for h in HARM:
        C = librosa.cqt(y=y, sr=SR, hop_length=HOP, fmin=FMIN * h, n_bins=N_OCT * BPO, bins_per_octave=BPO)
        C = librosa.util.fix_length(C, size=n_frames, axis=-1)
        m, ph = librosa.magphase(C)
        mag.append(librosa.amplitude_to_db(m, ref=np.max))
        a = np.angle(ph)
        d = np.empty_like(a); d[:, 0] = a[:, 0]; d[:, 1:] = np.diff(np.unwrap(a, axis=1), axis=1)
        dph.append(d)
    return np.asarray(mag, np.float32), np.asarray(dph, np.float32)      # (5, 360, T)


def freq_grid():
    return FMIN * 2.0 ** (np.arange(N_OCT * BPO) / BPO)


def salience(mag, dph, model, chunk=1500, pad=24):
    import torch
    T = mag.shape[-1]; out = np.zeros((360, T), np.float32)
    with torch.no_grad():
        for s in range(0, T, chunk):
            a, b = max(0, s - pad), min(T, s + chunk + pad)
            y = model(torch.from_numpy(mag[None, :, :, a:b]), torch.from_numpy(dph[None, :, :, a:b]))[0][0].numpy()
            out[:, s:min(T, s + chunk)] = y[:, s - a:s - a + min(chunk, T - s)]
    return out


def voas(sal, model, patch=128):
    import torch
    T = sal.shape[1]; n = -(-T // patch)
    x = np.zeros((n, 1, 360, patch), np.float32)
    for i in range(n):
        seg = sal[:, i * patch:(i + 1) * patch]; x[i, 0, :, :seg.shape[1]] = seg
    with torch.no_grad():
        ys = model(torch.from_numpy(x))
    return [np.hstack(list(y.numpy()))[:, :T] for y in ys]                  # 4 x (360, T)


def peaks_mf0(sal, thresh=0.5):
    from scipy.signal import argrelmax
    fr = freq_grid(); pk = np.zeros_like(sal)
    i = argrelmax(sal, axis=0); pk[i] = sal[i]
    return [fr[np.where(pk[:, t] >= thresh)[0]] for t in range(sal.shape[1])]


def assign_order(sal, k, thresh=0.5, hold=8):
    """Voice assignment without a model: at each frame the salience peaks (strongest first, at most k) are sorted
    high to low and matched to the k voices in order (voices don't cross), each peak going to the voice whose
    recent pitch is closest (dynamic programming over order-preserving matches). A voice that loses its peak keeps
    silent; its last pitch is remembered for `hold` frames. -> k F0 tracks (Hz, 0 = silent), high to low."""
    from scipy.signal import argrelmax
    fr = freq_grid(); T = sal.shape[1]
    out = np.zeros((k, T)); last = [None] * k; age = [10 ** 9] * k
    pk = np.zeros_like(sal); i = argrelmax(sal, axis=0); pk[i] = sal[i]
    default = np.linspace(72, 40, k)                     # where voices sit before they first sing (MIDI)
    for t in range(T):
        idx = np.where(pk[:, t] >= thresh)[0]
        idx = idx[np.argsort(-pk[idx, t])][:k]
        if not len(idx):
            age = [a + 1 for a in age]; continue
        ps = sorted((69 + 12 * np.log2(fr[j] / 440), fr[j]) for j in idx)[::-1]   # high to low
        ref = [last[v] if last[v] is not None and age[v] <= hold else default[v] for v in range(k)]
        n = len(ps)
        # D[a][b]: best cost matching the first a peaks to the first b voices (order kept)
        INF = 1e9; D = np.full((n + 1, k + 1), INF); D[0, :] = 0; B = {}
        for a in range(1, n + 1):
            for b in range(a, k + 1):
                skip = D[a, b - 1]; take = D[a - 1, b - 1] + abs(ps[a - 1][0] - ref[b - 1])
                D[a, b], B[a, b] = (take, 1) if take <= skip else (skip, 0)
        a, b = n, k
        while a > 0:
            if B[a, b]:
                out[b - 1, t] = ps[a - 1][1]; last[b - 1] = ps[a - 1][0]; age[b - 1] = 0; a -= 1
            b -= 1
        for v in range(k):
            if out[v, t] == 0: age[v] += 1
    return list(out)


def argmax_f0(m, thresh):
    fr = freq_grid(); k = m.argmax(0); v = m[k, np.arange(m.shape[1])]
    return np.where((v >= thresh) & (k > 0), fr[k], 0.0)


# ------------------------------------------------------------------------------------- F0 track -> notes
def to_notes(f0, min_note=0.12):
    from scipy.ndimage import median_filter
    dt = HOP / SR
    midi = np.where(f0 > 0, 69 + 12 * np.log2(np.maximum(f0, 1e-6) / 440.0), 0)
    midi = median_filter(np.round(midi), size=7, mode="nearest")
    notes, cur = [], None
    for t, m in enumerate(midi):
        if cur and m == cur[2]:
            cur[1] = t + 1; continue
        if cur: notes.append(cur)
        cur = [t, t + 1, m] if m > 0 else None
    if cur: notes.append(cur)
    keep = []
    for n in notes:                      # a blip shorter than min_note joins its neighbour or goes
        if (n[1] - n[0]) * dt >= min_note:
            if keep and keep[-1][2] == n[2] and n[0] - keep[-1][1] <= 3: keep[-1][1] = n[1]
            else: keep.append(n)
    return [(round(a * dt, 3), round(b * dt, 3), int(m)) for a, b, m in keep]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio"); ap.add_argument("out")
    ap.add_argument("--models", default=MODELS)
    ap.add_argument("--assign", default="order", choices=["order", "voas"],
                    help="order: k voices kept in pitch order, any ranges (default; works with a very low bass); "
                         "voas: the VoasCNN model (SATB choirs in standard ranges only)")
    ap.add_argument("--voices", default="S,A,T,B", help="names of the voices high to low (order mode), e.g. T1,A,Br,B")
    ap.add_argument("--voas", default="cnn", choices=["cnn"])
    ap.add_argument("--thresh", type=float, default=0.5, help="multi-F0 peak threshold (paper: 0.5)")
    ap.add_argument("--min-note", type=float, default=0.12)
    a = ap.parse_args()
    import librosa, torch
    torch.set_num_threads(os.cpu_count() or 4)
    os.makedirs(a.out, exist_ok=True)
    mf0_path = os.path.join(a.models, "multif0-estimation-polyvocals", "models", "exp3multif0.pkl")
    va_path = os.path.join(a.models, "voas-vocal-quartets", "models", f"voas_{a.voas}.h5")
    names = tuple(a.voices.split(",")) if a.assign == "order" else VOICES
    for p in (mf0_path, va_path) if a.assign == "voas" else (mf0_path,):
        if not os.path.exists(p): sys.exit(f"missing model {p}: see the header of this script")
    y, _ = librosa.load(a.audio, sr=SR, mono=True)
    print(f"{len(y) / SR:.1f} s of audio: HCQT ...", file=sys.stderr)
    mag, dph = hcqt(y)
    print("multi-F0 (Late/Deep) ...", file=sys.stderr)
    sal = salience(mag, dph, load_keras(mf0_path))
    np.save(os.path.join(a.out, "salience.npy"), sal)
    times = np.arange(sal.shape[1]) * HOP / SR
    with open(os.path.join(a.out, "multif0.csv"), "w", newline="") as f:
        w = csv.writer(f)
        for t, fs in zip(times, peaks_mf0(sal, a.thresh)): w.writerow([round(t, 4)] + [round(x, 2) for x in fs])
    if a.assign == "voas":
        print("voice assignment (VoasCNN) ...", file=sys.stderr)
        maps = voas(sal, load_keras(va_path))
        f0s = [argmax_f0(m, th) for m, th in zip(maps, VOAS_THRESH[a.voas])]
    else:
        print(f"voice assignment (pitch order, {len(names)} voices) ...", file=sys.stderr)
        f0s = assign_order(sal, len(names), a.thresh)
    with open(os.path.join(a.out, "voices.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["time"] + list(names))
        for i, t in enumerate(times): w.writerow([round(t, 4)] + [round(x[i], 2) for x in f0s])
    import pretty_midi
    pm = pretty_midi.PrettyMIDI()
    summary = {}
    for v, f0 in zip(names, f0s):
        notes = to_notes(f0, a.min_note)
        with open(os.path.join(a.out, f"notes_{v}.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["start", "end", "midi"]); w.writerows(notes)
        inst = pretty_midi.Instrument(program=52, name=v)
        inst.notes = [pretty_midi.Note(80, m, s, e) for s, e, m in notes]
        pm.instruments.append(inst)
        ms = [m for _, _, m in notes]
        summary[v] = dict(notes=len(notes), voiced=round(float((f0 > 0).mean()), 3),
                          range=[librosa.midi_to_note(min(ms)), librosa.midi_to_note(max(ms))] if ms else None)
    pm.write(os.path.join(a.out, "voices.mid"))
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(min(60, 4 + len(y) / SR / 2), 6))
        ax.imshow(sal, origin="lower", aspect="auto", cmap="Greys", extent=[0, times[-1], 24, 24 + 72])
        for v, f0, col in zip(names, f0s, ("tab:red", "tab:orange", "tab:green", "tab:blue", "tab:purple", "tab:brown")):
            m = np.where(f0 > 0, 69 + 12 * np.log2(np.maximum(f0, 1e-6) / 440), np.nan)
            ax.plot(times, m, ".", ms=1.5, color=col, label=v)
        ax.set_ylim(28, 84); ax.set_xlabel("s"); ax.set_ylabel("MIDI"); ax.legend(loc="upper right")
        fig.tight_layout(); fig.savefig(os.path.join(a.out, "voices.png"), dpi=80); plt.close(fig)
    except Exception as e:
        print("no piano roll:", e, file=sys.stderr)
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
