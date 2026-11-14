#!/usr/bin/env python3
"""Do two scores play the same notes?  Compares MuseScore's own MIDI export: onset and pitch per staff
(lengths: see compare_scores.py).

    python3 same_sound.py BEFORE.mscz AFTER.mscz [--velocity]

Use it after every change that must not change the music (layout, respell, spelling, comments, memos, relabel,
solfa). --velocity also compares velocities (expected to differ after express.py). Exit code 1 if they differ.
"""
import sys, os, tempfile, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import export
from velocity import midi_notes

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--velocity", action="store_true")
    x = ap.parse_args(); res = []
    with tempfile.TemporaryDirectory() as td:
        for i, p in enumerate((x.a, x.b)):
            tr, tpq = midi_notes(export(p, os.path.join(td, f"{i}.mid")))
            res.append([sorted((t * 4 // tpq, n) + ((v,) if x.velocity else ()) for t, v, n in track) for track in tr if track])
    A, B = res; bad = 0
    for k in range(max(len(A), len(B))):
        a, b = (A[k] if k < len(A) else []), (B[k] if k < len(B) else [])
        if a != b:
            bad += 1; sa, sb = set(a), set(b)
            print(f"track {k}: {len(a)} vs {len(b)} notes; only before {sorted(sa - sb)[:6]} only after {sorted(sb - sa)[:6]} (tick in 16ths, pitch)")
    print("same notes" + (" and velocities" if x.velocity else "") if not bad else f"{bad} tracks differ"); sys.exit(1 if bad else 0)
