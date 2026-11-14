#!/usr/bin/env python3
"""Notes that are spoken, not sung (rap, shouts): cross noteheads and no sound on playback; or the way back.

    python3 mute.py IN.mscz OUT.mscz --staves 3rd --bars 69-86 [--unmute] [--head cross|normal]

The written pitch stays (a contour to follow); MuseScore's "play" switch of each note is turned off.
"""
import sys, os, argparse, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, parse_bars, parse_staves

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--staves", required=True); ap.add_argument("--bars", required=True)
    ap.add_argument("--unmute", action="store_true"); ap.add_argument("--head")
    a = ap.parse_args(); s = Score(a.src); n = 0
    head = a.head or ("normal" if a.unmute else "cross")
    for si in parse_staves(a.staves, s):
        for b, t, c, v in s.events(si, bars=parse_bars(a.bars, s.nbars)):
            if c.tag != "Chord": continue
            for nt in c.findall("Note"):
                for tag in ("head", "play"):
                    for x in nt.findall(tag): nt.remove(x)
                if head != "normal": ET.SubElement(nt, "head").text = head
                if not a.unmute: ET.SubElement(nt, "play").text = "0"
                n += 1
    s.save(a.dst); print(n, "notes", "unmuted" if a.unmute else "muted", "| head:", head)
