#!/usr/bin/env python3
"""Plain spelling: double flats / double sharps in the singers' staves become the plain enharmonic note
(Bbb -> A, Abb -> G, Ebb -> D, F## -> G ...). The stored accidental signs of those staves are dropped, so MuseScore
draws them again from the new spelling (naturals included). The sound does not change.

    python3 spelling.py IN.mscz OUT.mscz
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score

NAMES = "Fbb Cbb Gbb Dbb Abb Ebb Bbb Fb Cb Gb Db Ab Eb Bb F C G D A E B F# C# G# D# A# E# B# F## C## G## D## A## E## B##".split()
nm = lambda t: NAMES[t + 1]

if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    s = Score(sys.argv[1]); cnt = collections.Counter()
    for si in s.sung_staves():
        for nt in s.staves[si].iter("Note"):
            t = int(nt.findtext("tpc")); n = t
            if t <= 5: n = t + 12
            elif t >= 27: n = t - 12
            if n != t: nt.find("tpc").text = str(n); cnt[f"{nm(t)}->{nm(n)}"] += 1
            for x in nt.findall("Accidental"): nt.remove(x)
    s.save(sys.argv[2]); print(dict(cnt) or "nothing to change")
