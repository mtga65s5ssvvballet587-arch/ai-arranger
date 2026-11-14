#!/usr/bin/env python3
"""Export a score with MuseScore (no window needed): PDF, MIDI, MusicXML, PNG, or a MuseScore 3 .mscz.

    python3 render.py SCORE.mscz out.pdf [out.mid ...]

MuseScore is found in $ACAP_MSCORE, then mscore4 / mscore / musescore4 / musescore / mscore3 on the PATH.
MuseScore 4 is preferred: MuseScore 3.2 (Ubuntu's package) cannot open files saved by 3.6.
"""
import os, sys, shutil, subprocess

CANDIDATES = ["mscore4", "mscore", "musescore4", "musescore", "MuseScore4", "mscore3", "musescore3"]


def mscore():
    exe = os.environ.get("ACAP_MSCORE") or next((shutil.which(c) for c in CANDIDATES if shutil.which(c)), None)
    if not exe: sys.exit("MuseScore not found: install MuseScore 4 or set ACAP_MSCORE=/path/to/mscore")
    return exe


def export(src, dst):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", MU_QT_QPA_PLATFORM="offscreen")
    r = subprocess.run([mscore(), "-o", dst, src], env=env, capture_output=True, text=True, timeout=600)
    if not os.path.exists(dst): sys.exit(f"export failed: {dst}\n{r.stderr[-2000:]}")
    return dst


if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(__doc__)
    for d in sys.argv[2:]: print("written", export(sys.argv[1], d))
