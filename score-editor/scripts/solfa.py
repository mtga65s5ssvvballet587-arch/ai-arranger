#!/usr/bin/env python3
"""Movable-do syllables (ド レ ミ ...) as a second lyric line under the singers' notes.

    python3 solfa.py IN.mscz OUT.mscz [--tonic Gb] [--line 2]

The tonic comes from the key signature (major key: 6 flats -> Gb = ド); --tonic overrides it (e.g. a minor song
sung on la: give the relative major). The syllable follows the written spelling, so it matches what the singer
reads: A natural in Gb major = レ♯, F flat = シ♭. Run spelling.py first if the score has double flats.
Not written: notes tied from the previous note, notes with cross noteheads (rap, spoken), percussion.
"""
import sys, os, argparse, collections, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, tied_in

BASE = {0: "ド", 1: "ソ", 2: "レ", 3: "ラ", 4: "ミ", 5: "シ", -1: "ファ"}         # fifths from the tonic
TPC = {n: i for i, n in enumerate("Fbb Cbb Gbb Dbb Abb Ebb Bbb Fb Cb Gb Db Ab Eb Bb F C G D A E B F# C# G# D# A# E# B#".split(), -1)}


def syl(tpc, tonic):
    f = tpc - tonic; acc = ""
    while f > 5: f -= 7; acc += "♯"
    while f < -1: f += 7; acc += "♭"
    return BASE[f] + acc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--tonic"); ap.add_argument("--line", type=int, default=2)
    a = ap.parse_args(); s = Score(a.src)
    tonic = TPC[a.tonic] if a.tonic else 14 + s.key_fifths()
    cnt = collections.Counter(); chrom = collections.Counter()
    for si in s.sung_staves():
        for b, t, c, v in s.events(si):
            if c.tag != "Chord": continue
            nt = c.find("Note")
            if nt.findtext("head") == "cross" or tied_in(c): continue
            x = syl(int(nt.findtext("tpc")), tonic)
            if "♯" in x or "♭" in x: chrom[x] += 1
            ly = ET.Element("Lyrics"); ET.SubElement(ly, "no").text = str(a.line - 1); ET.SubElement(ly, "text").text = x
            c.insert(list(c).index(nt), ly); cnt[si] += 1
    s.save(a.dst); print("syllables per staff:", dict(cnt), "| outside the scale:", dict(chrom))


if __name__ == "__main__":
    main()
