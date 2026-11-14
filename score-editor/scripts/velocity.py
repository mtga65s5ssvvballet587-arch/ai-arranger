#!/usr/bin/env python3
"""What will MuseScore actually play?  Average note velocity per section and staff, from the score's own MIDI.

    python3 velocity.py SCORE.mscz [--sections "95:S-2 (2),99:S-3 (2)"]

Sections = the rehearsal marks (+ extra starts given with --sections). Warnings:
  - a section where the lead (the staff with the latest "Lead" text) is quieter than a backing staff;
  - velocities at the top (124+): a hairpin that never meets a dynamic keeps climbing;
  - percussion that never changes while the voices do.
Muted notes (play off, e.g. rap) are not in the MIDI, so they show as "-".
"""
import sys, os, re, struct, argparse, tempfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, text_of
from render import export


def midi_notes(path):
    """[[(tick, velocity, pitch), ...] per track] and ticks per quarter, from a standard MIDI file."""
    d = open(path, "rb").read(); tpq = struct.unpack(">H", d[12:14])[0]; i = 14; tracks = []
    while i < len(d):
        ln = struct.unpack(">I", d[i + 4:i + 8])[0]; tr = d[i + 8:i + 8 + ln]; i += 8 + ln
        t = 0; j = 0; run = 0; out = []
        def vlq():
            nonlocal j
            v = 0
            while True:
                b = tr[j]; j += 1; v = (v << 7) | (b & 0x7F)
                if b < 0x80: return v
        while j < len(tr):
            t += vlq(); st = tr[j]
            if st >= 0x80: j += 1; run = st
            else: st = run
            if st == 0xFF: j += 1; n = vlq(); j += n
            elif st in (0xF0, 0xF7): n = vlq(); j += n
            else:
                hi = st & 0xF0; k = 1 if hi in (0xC0, 0xD0) else 2; data = tr[j:j + k]; j += k
                if hi == 0x90 and data[1] > 0: out.append((t, data[1], data[0]))
        tracks.append(out)
    return tracks, tpq


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("score"); ap.add_argument("--sections", default="")
    a = ap.parse_args(); s = Score(a.score); names = s.short_names()
    starts = dict(s.marks())
    for x in filter(None, a.sections.split(",")): b, n = x.split(":", 1); starts[int(b)] = n
    if 1 not in starts and min(starts, default=2) > 1: starts[1] = "(start)"
    bars = sorted(starts); bar0 = s.bar_starts()
    with tempfile.TemporaryDirectory() as td:
        mid = export(a.score, os.path.join(td, "x.mid")); tracks, tpq = midi_notes(mid)
    tracks = [t for t in tracks if t][:len(s.staves)]
    tick_bar = lambda t: max(i for i, b in enumerate(bar0) if b <= t * 4 / tpq) + 1
    lead = {}; cur = None
    for b in range(1, s.nbars + 1):
        for si in s.sung_staves():
            if any(e.tag == "StaffText" and "Lead" in text_of(e) for e in s.voice(si, b)): cur = si
        lead[b] = cur
    print(f"{'section':16s}" + "".join(f"{n:>7s}" for n in names[:len(tracks)]))
    warn = []; perc = [i for i in range(len(tracks)) if s.is_percussion(i)]; pv = collections.defaultdict(set)
    for k, b0 in enumerate(bars):
        b1 = bars[k + 1] - 1 if k + 1 < len(bars) else s.nbars
        row = []
        for ti, tr in enumerate(tracks):
            v = [vel for t, vel, _ in tr if b0 <= tick_bar(t) <= b1]; row.append(round(sum(v) / len(v)) if v else None)
            if v and max(v) >= 124: warn.append(f"bar {b0}-{b1} {names[ti]}: reaches {max(v)}, the top of the range (ff + accent, or a hairpin going past ff)")
            if ti in perc and v: pv[ti].add(round(sum(v) / len(v)))
        print(f"{(str(b0) + ' ' + starts[b0])[:16]:16s}" + "".join(f"{(x if x is not None else '-'):>7}" for x in row))
        # lead vs backing, bar by bar (only bars where both sing): a backing staff louder by 8+ in 2+ bars
        louder = collections.Counter()
        for b in range(b0, b1 + 1):
            ld = lead.get(b)
            if ld is None or ld >= len(tracks): continue
            avg = {}
            for ti in s.sung_staves():
                if ti >= len(tracks): continue
                v = [vel for t, vel, _ in tracks[ti] if tick_bar(t) == b]
                if v: avg[ti] = sum(v) / len(v)
            if ld not in avg: continue
            for ti, x in avg.items():
                if ti != ld and x >= avg[ld] + 8: louder[(ld, ti)] += 1
        for (ld, ti), n in louder.items():
            if n >= 2: warn.append(f"{starts[b0]} (bars {b0}-{b1}): lead {names[ld]} quieter than {names[ti]} in {n} bars")
    print(f"{'':16s}(lead = staff with the latest 'Lead' text)")
    for ti, vs in pv.items():
        if len(vs) == 1: warn.append(f"{names[ti]}: same velocity everywhere - give the percussion dynamics too (express.py drums_follow)")
    print("\n".join(["", "warnings:"] + warn) if warn else "\nno warning")


if __name__ == "__main__":
    main()
