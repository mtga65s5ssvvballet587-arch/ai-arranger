#!/usr/bin/env python3
"""Scat syllables by one rule, so a section is easy to remember.

    # notes without a syllable get one by their sounding length (ties included):
    python3 scat.py IN.mscz OUT.mscz fill --bars 2-11 --staves Top,3rd,4th --short tu --run lu --long uh [--whole fu]
    # existing scat syllables (latin letters) are written again with two syllables only:
    python3 scat.py IN.mscz OUT.mscz unify --bars 16-23,64-67 --staves Top,2nd,3rd,4th --start tu --follow lu
                    [--fixed 2=Fu] [--keep 5=uh]

fill:  8th or shorter -> --short (--run when it follows a note directly), quarter or longer -> --long,
       a whole bar or longer -> --whole. Notes tied from the previous note and notes with a syllable are left alone.
unify: scat = a syllable in lower-case latin letters (B, So, Fu are left alone).
       --start after a rest, a word (Japanese / real words) or a long note (half or longer); --follow when the note
       follows another note directly. Words are never changed. Exceptions:
       --fixed BAR=SYL  every scat note of that bar gets SYL;
       --keep BAR=SYL   notes already sung on SYL in that bar keep it (and the note tied into that bar).
Nothing but syllables changes; check with compare_scores.py.
"""
import sys, os, re, argparse, collections, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, length, lyric, tied_in, tied_out, parse_bars, parse_staves

SCAT = re.compile(r"^[a-z]+$")          # lower-case latin = scat; "B", "So", "Fu" are words / deliberate choices


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("mode", choices=["fill", "unify"])
    ap.add_argument("--bars", required=True); ap.add_argument("--staves")
    for k, d in (("short", "ta"), ("run", "ra"), ("long", "uh"), ("whole", None), ("start", "tu"), ("follow", "lu")):
        ap.add_argument("--" + k, default=d)
    ap.add_argument("--fixed", action="append", default=[]); ap.add_argument("--keep", action="append", default=[])
    a = ap.parse_args(); s = Score(a.src); bars = parse_bars(a.bars, s.nbars); sts = parse_staves(a.staves, s)
    fixed = {int(x.split("=")[0]): x.split("=")[1] for x in a.fixed}; keep = {int(x.split("=")[0]): x.split("=")[1] for x in a.keep}
    cnt = collections.Counter()
    for si in sts:
        if a.mode == "fill":
            ev = [(b, e) for b, t, e, v in s.events(si, bars=bars, voice=0) if e.tag in ("Chord", "Rest")]
            for k, (b, c) in enumerate(ev):
                if c.tag != "Chord" or tied_in(c) or c.find("Lyrics") is not None: continue
                L, j = length(c), k
                while ev[j][1].tag == "Chord" and tied_out(ev[j][1]) and j + 1 < len(ev): j += 1; L += length(ev[j][1])
                after_note = k > 0 and ev[k - 1][1].tag == "Chord"
                syl = (a.whole if a.whole and L >= 16 else a.long) if L >= 4 else (a.run if after_note else a.short)
                ly = ET.Element("Lyrics"); ET.SubElement(ly, "text").text = syl
                c.insert(list(c).index(c.find("Note")), ly); cnt[syl] += 1
        else:
            for run in _runs(sorted(bars)):
                prev = False
                for b, t, c, v in s.events(si, bars=set(run), voice=0):
                    if c.tag == "Rest": prev = False; continue
                    if c.tag != "Chord": continue
                    w = lyric(c); ly = next((l for l in c.findall("Lyrics") if int(l.findtext("no") or 0) == 0), None)
                    if w and SCAT.match(w):
                        new = a.follow if prev else a.start
                        if b in fixed: new = fixed[b]
                        if (b in keep and w == keep[b]) or (b + 1 in keep and w == keep[b + 1] and tied_out(c)): new = w
                        if new != w:
                            tx = ly.find("text")
                            for e in list(tx): tx.remove(e)
                            tx.text = new; cnt[f"{w}->{new}"] += 1
                        prev = True
                    elif w: prev = False
                    else: prev = True
                    if c.findtext("durationType") in ("half", "whole"): prev = False
    s.save(a.dst); print(dict(cnt) or "nothing to change")


def _runs(bars):
    out = []
    for b in bars:
        if out and b == out[-1][-1] + 1: out[-1].append(b)
        else: out.append([b])
    return out


if __name__ == "__main__":
    main()
