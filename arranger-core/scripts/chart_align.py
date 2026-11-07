#!/usr/bin/env python3
"""Line a chord chart (the chords of a song in order, e.g. typed from ChordWiki / U-FRET) up with the recording.

    $ACAP_PY chart_align.py W chart.txt [--per beat|half]  -> W/chart_chords.json, printed bar table

chart.txt: chord symbols in song order, whitespace separated; '[Section]' lines and '|' are ignored, '#' starts a
comment; N.C. = no chord. Symbols as on Japanese chord sites: CbM7, Dbm7, Cm7-5, Gbaug/C, Db7/Cb, Bbm7/Eb ...
How: per beat, the chroma of the accompaniment (+ bass) and the bass pitch class; each chart chord gets a template.
A left-to-right dynamic programme gives every chord a run of whole beats (at least one), in order, maximising the
template match (+ a bonus when the recorded bass is the chord's bass), with free silence before and after.
The chart decides WHICH chords, the recording decides WHEN. backing.py uses W/chart_chords.json when it exists.
"""
import argparse, json, os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import engine as E
from acap import Bars, stem


def norm(sym):
    """Chart spelling -> engine spelling."""
    s = sym.replace("M7", "maj7").replace("m7-5", "m7b5").replace("(b5)", "b5").replace("△7", "maj7")
    s = re.sub(r"^([A-G][#b]?)maj7", r"\1maj7", s)
    return s


def parse_chart(path):
    out = []
    for line in open(path, encoding="utf8"):
        line = line.split("#")[0]
        if line.strip().startswith("["): continue
        for t in line.replace("|", " ").split():
            out.append("N.C." if t.upper() in ("N.C.", "NC", "N.C") else norm(t))
    return out


def template(sym):
    if sym == "N.C.": return None, None
    c = E.chord(sym)
    v = np.zeros(12)
    for p in c["tones"]: v[p] = 1.0
    v[c["root"]] += 0.3
    return v / np.linalg.norm(v), c["bass"]


def align(W, chart, cell=2, bass=1.0, nc=0.45, off=0, miss=0.5, tone=0.0):
    """-> (mean score, cells [(beat index, bar, beat)], labels [chart index or None per cell])"""
    import librosa
    B = Bars(W); SR, HOP = 22050, 512
    yo = librosa.load(stem(W, "other"), sr=SR)[0]; yb = librosa.load(stem(W, "bass"), sr=SR)[0]
    ch = librosa.feature.chroma_cqt(y=yo + 0.5 * yb, sr=SR, hop_length=HOP)
    bc = librosa.feature.chroma_cqt(y=yb, sr=SR, hop_length=HOP)
    nb = B.L // E.BEAT
    beats = [(n, k) for n in B.numbers for k in range(nb)]
    bt = [B.t(n, k * E.BEAT) for n, k in beats] + [B.t(B.numbers[-1], B.L)]
    cells, X, BP = [], [], []
    for i in range(off, len(beats) - cell + 1, cell):
        s_ = slice(int(bt[i] * SR / HOP), int(bt[i + cell] * SR / HOP) + 1)
        x = ch[:, s_].mean(1); X.append(x / (np.linalg.norm(x) + 1e-9)); BP.append(int(np.argmax(bc[:, s_].mean(1))))
        cells.append((i,) + beats[i])
    X = np.array(X); J, T = len(chart), len(cells); S = np.zeros((J, T))
    for j, sym in enumerate(chart):
        v, bs = template(sym)
        tones = E.chord(sym)["tones"] if v is not None else set()
        S[j] = nc if v is None else X @ v + np.array([bass if bp == bs else (tone if bp in tones else -bass * miss)
                                                     for bp in BP])
    D = np.full((J + 2, T + 1), -1e9); D[0, 0] = 0; bk = np.zeros((J + 2, T + 1), np.int8)
    for t in range(1, T + 1):                      # 0 = before the chart, 1..J = chord j-1, J+1 = after
        D[0, t] = D[0, t - 1] + .2
        mv, st = D[:J, t - 1], D[1:J + 1, t - 1]
        take = mv >= st
        D[1:J + 1, t] = np.where(take, mv, st) + S[:, t - 1]; bk[1:J + 1, t] = take
        D[J + 1, t], bk[J + 1, t] = (D[J, t - 1] + .2, 1) if D[J, t - 1] >= D[J + 1, t - 1] else (D[J + 1, t - 1] + .2, 0)
    j = J + 1 if D[J + 1, T] >= D[J, T] else J; lab = [None] * T
    for t in range(T, 0, -1):
        if 1 <= j <= J: lab[t - 1] = j - 1
        if bk[j, t]: j -= 1
    sc = float(np.mean([S[l, t] for t, l in enumerate(lab) if l is not None and chart[l] != "N.C."]))
    return sc, cells, lab


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("W"); ap.add_argument("chart")
    ap.add_argument("--cell", type=int, default=2, help="beats per cell: chords change only on cell lines (2 = half bars)")
    ap.add_argument("--bass", type=float, default=1.0, help="bonus when the recorded bass is the chord's bass (-half if not)")
    ap.add_argument("--nc", type=float, default=0.45, help="score of N.C. per cell")
    a = ap.parse_args()
    chart = parse_chart(a.chart); W = a.W; B = Bars(W)
    res = [(align(W, chart, a.cell, a.bass, a.nc, off), off) for off in range(a.cell)]
    for (sc, _, _), off in res: print(f"grid offset {off} beat(s): mean score {sc:.3f}")
    (sc, cells, lab), off = max(res, key=lambda r: r[0][0])
    if off: print(f"WARNING: the chart fits better {off} beat(s) after the bar lines: check bar 1 (barmap.py --anchor)")
    rows, last = {}, next((c for c in chart if c != "N.C."), "C")
    for (i, n, k), l in zip(cells, lab):
        sym = chart[l] if l is not None else None
        if sym and sym != "N.C.": last = sym
        rows.setdefault(n, []).append(last)
    for n in B.numbers:
        r = rows.get(n) or [last]
        rows[n] = r[:1] if len(set(r)) == 1 else r
    json.dump({str(k): v for k, v in rows.items()}, open(os.path.join(W, "chart_chords.json"), "w"), ensure_ascii=False)
    print(f"{len(chart)} chart chords on {len(cells)} cells of {a.cell} beats -> {W}/chart_chords.json")
    for n in B.numbers:
        print(f"b{n:<4} " + " ".join(f"{x:9s}" for x in rows[n]))


if __name__ == "__main__":
    main()
