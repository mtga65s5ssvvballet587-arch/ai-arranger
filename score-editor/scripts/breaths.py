#!/usr/bin/env python3
"""Decide where the singers breathe; writes a plan that respell.py applies (--plan).

    python3 breaths.py SCORE.mscz breaths.json [--places places.json] [--no-cut Bass] [--report]

Automatic rule, for every stretch of notes without a rest (ties joined):
  - longer than 4 bars: an 8th rest is cut out of the end of a note (a quarter or longer), recursively until no
    stretch is longer than 4 bars;
  - longer than 2 bars: one breath mark (comma) after a note, no rest;
  - rap (most notes with cross noteheads): commas only, at the 2-bar line ends counted from the rehearsal mark.
  Best place = end of a long note, on a barline, at a 2- / 4-bar phrase end counted from the rehearsal mark.
`--places` = places chosen by hand (at word ends), JSON list of
    {"staff": "2nd", "bar": 24, "after": "ね", "kind": "cut" | "breath"}     ("after" may be omitted: last note)
  A staff that has hand-chosen places is not planned automatically (except its rap stretches).
`--no-cut` = staves that keep their note shapes: planned like the others, but only the commas are kept (no
  shortened note), e.g. the bass line.
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, length, lyric, tie, parse_staves


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("score"); ap.add_argument("out"); ap.add_argument("--places"); ap.add_argument("--no-cut", default="")
    a = ap.parse_args(); s = Score(a.score); names = s.short_names()
    bar0 = s.bar_starts(); marks = [b - 1 for b, _ in s.marks()]
    bar_of = lambda x: max(i for i, b in enumerate(bar0) if b <= x)
    nocut = set(parse_staves(a.no_cut, s)) if a.no_cut else set()
    manual = {}
    for p in json.load(open(a.places)) if a.places else []:
        si = parse_staves(str(p["staff"]), s)[0]; manual.setdefault(si, []).append((p["kind"], int(p["bar"]), p.get("after")))

    def phrase_bonus(e):
        b = bar_of(e)
        if bar0[b] != e: return 1 if (e - bar0[b]) % 8 == 0 else 0
        sec = max([mk for mk in marks if mk <= b - 1], default=0); k = b - sec
        return 2 + (k % 2 == 0) + (k % 4 == 0) + 2 * (b in marks)

    plan = dict(cut=[], breath=[])
    for si in s.sung_staves():
        notes = []; t = 0; tied = False; runs = []; run = None
        for m in s.staves[si].findall("Measure"):
            for k in m.find("voice"):
                if k.tag == "Chord":
                    nt = k.find("Note"); n_ = length(k)
                    if tied and notes and notes[-1][1] == t: notes[-1][1] = t + n_
                    else:
                        notes.append([t, t + n_, nt.findtext("head") == "cross", lyric(k) or ""])
                        if run is None: run = [len(notes) - 1, None]
                    tied = tie(nt, "next") is not None; t += n_
                elif k.tag == "Rest":
                    if run: run[1] = len(notes); runs.append(run); run = None
                    t += length(k); tied = False
        if run: run[1] = len(notes); runs.append(run)

        def best(seg, margin):
            c = [(phrase_bonus(x[1]) + (3 if x[1] - x[0] >= 8 else 2 if x[1] - x[0] >= 4 else 0), -abs(x[1] - (seg[0][0] + seg[-1][1]) / 2), i)
                 for i, x in enumerate(seg[:-1]) if x[1] - x[0] >= 4 and x[1] - seg[0][0] >= margin and seg[-1][1] - x[1] >= margin]
            return max(c)[2] if c else None

        def split(seg, limit, margin, kind):
            if seg[-1][1] - seg[0][0] <= limit: return [seg]
            i = best(seg, margin)
            if i is None: return [seg]
            x = seg[i]; b = bar_of(x[1] - 1) + 1
            print(f"  {names[si]:5s} {kind:6s} bar {b} beat {(x[1] - 1 - bar0[b - 1]) // 4 + 1} after '{x[3]}'")
            plan[kind].append([si, x[1]])
            if kind == "breath": return [seg]
            return split(seg[:i + 1], limit, margin, kind) + split(seg[i + 1:], limit, margin, kind)

        for kind, bar, syl in manual.get(si, []):
            c = [x for x in notes if bar0[bar - 1] <= x[0] < (bar0[bar] if bar < len(bar0) else 10 ** 9) and (syl is None or x[3] == syl)]
            if not c: print(f"  WARNING {names[si]} bar {bar}: no note '{syl}'"); continue
            x = c[-1]; plan[kind].append([si, x[1]]); print(f"  {names[si]:5s} {kind:6s} bar {bar} after '{x[3]}' (by hand)")
        for r0, r1 in runs:
            seg = notes[r0:r1]; rap = sum(x[2] for x in seg) > len(seg) / 2
            if si in manual and not rap: continue
            if seg[-1][1] - seg[0][0] <= 32: continue
            if rap:
                for x in seg[:-1]:
                    bb = bar_of(x[1])
                    if bar0[bb] == x[1] and (bb - max([mk for mk in marks if mk <= bb], default=0)) % 2 == 0:
                        plan["breath"].append([si, x[1]]); print(f"  {names[si]:5s} breath before bar {bb + 1} (rap line end)")
                continue
            ncut = len(plan["cut"])
            for part in split(seg, 64, 24, "cut"):
                split(part, 32, 12, "breath")
            if si in nocut: del plan["cut"][ncut:]       # the note shapes stay: only the commas are kept
    plan["breath"] = sorted({tuple(x) for x in plan["breath"]}); plan["cut"] = sorted({tuple(x) for x in plan["cut"]})
    json.dump(plan, open(a.out, "w")); print(len(plan["cut"]), "rests cut,", len(plan["breath"]), "breath marks ->", a.out)


if __name__ == "__main__":
    main()
