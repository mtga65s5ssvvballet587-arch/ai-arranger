#!/usr/bin/env python3
"""Rename things without touching the music: title, lyric sequences, any text, part names, tempo marks.

    python3 relabel.py IN.mscz OUT.mscz [--title "Song A=Song B"] [--lyrics "ラ,ラ,A=ラ,ラ,B"]
                       [--text "old=new"] [--parts "Top Anna,2nd Ben,..."] [--tempo-first-only]

--title  OLD=NEW  the work title and every text that contains it (title frame, comments)
--lyrics A,B,C=X,Y,Z  every run of consecutive syllables A B C (first lyric line, each staff) becomes X Y Z
         (same number of syllables; repeat the option for several runs)
--text   OLD=NEW  inside every text (staff / system texts, comments, frame texts)
--parts  long names of the parts in score order (the first word becomes the short name)
--tempo-first-only  remove every tempo mark after bar 1 (back to one tempo for the whole song)
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, text_of


def replace_in(el, old, new):
    n = 0
    for e in el.iter():
        for a in ("text", "tail"):
            v = getattr(e, a)
            if v and old in v: setattr(e, a, v.replace(old, new)); n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--title"); ap.add_argument("--lyrics", action="append", default=[])
    ap.add_argument("--text", action="append", default=[]); ap.add_argument("--parts"); ap.add_argument("--tempo-first-only", action="store_true")
    a = ap.parse_args(); s = Score(a.src); log = []
    if a.title:
        old, new = a.title.split("=", 1); n = 0
        for mt in s.sc.iter("metaTag"):
            if mt.get("name") == "workTitle" and mt.text and old in mt.text: mt.text = mt.text.replace(old, new); n += 1
        for t in s.sc.iter("text"): n += replace_in(t, old, new)
        log.append(f"title {old} -> {new}: {n}")
    for spec in a.lyrics:
        old, new = [x.split(",") for x in spec.split("=", 1)]; assert len(old) == len(new), "same number of syllables"
        n = 0
        for si in range(len(s.staves)):
            hist = []
            for b, t, c, v in s.events(si):
                if c.tag != "Chord": continue
                ly = next((l for l in c.findall("Lyrics") if int(l.findtext("no") or 0) == 0), None)
                if ly is None: continue
                hist.append(ly)
                if [text_of(l) for l in hist[-len(old):]] == old:
                    for l, w in zip(hist[-len(old):], new):
                        tx = l.find("text")
                        for e in list(tx): tx.remove(e)
                        tx.text = w
                    n += 1
        log.append(f"lyrics {' '.join(old)} -> {' '.join(new)}: {n}")
    for spec in a.text:
        old, new = spec.split("=", 1); n = sum(replace_in(t, old, new) for t in s.sc.iter("text")); log.append(f"text {old} -> {new}: {n}")
    if a.parts:
        names = [x.strip() for x in a.parts.split(",")]
        for p, nm in zip(s.parts, names):
            ins = p.find("Instrument")
            for tag, val in (("longName", nm), ("shortName", nm.split()[0]), ("trackName", nm)):
                e = ins.find(tag)
                if e is None: e = __import__("xml.etree.ElementTree", fromlist=["x"]).SubElement(ins, tag)
                e.text = val
            if p.find("trackName") is not None: p.find("trackName").text = nm
        log.append(f"parts: {', '.join(names)}")
    if a.tempo_first_only:
        n = 0
        for si in range(len(s.staves)):
            for b, t, e, v in list(s.events(si)):
                if e.tag == "Tempo" and b > 1: v.remove(e); n += 1
        log.append(f"tempo marks removed after bar 1: {n}")
    s.save(a.dst); print("\n".join(log))


if __name__ == "__main__":
    main()
