#!/usr/bin/env python3
"""What did someone change by hand?  Compares an edited score with the version it came from.

    python3 compare_scores.py ORIGINAL.mscz EDITED.mscz [--json out.json]

Reports, bar by bar and staff by staff:
  - notes / rests / lyrics that differ (pitch, length, tie, lyric);
  - texts added, removed or changed (staff texts, system texts, tempo, rehearsal marks, frame texts);
  - marks added or removed (dynamics, articulations, breaths, hairpins, slurs, tempo).
Ignored on purpose: line / page breaks, and an articulation that only flipped above <-> below (MuseScore does that by
itself when it saves). Use it before merging someone's notes (memos.py) so nothing they wrote is lost.
"""
import sys, os, json, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score
from inspect_score import bar_line, all_texts, all_marks


def compare(a, b):
    out = dict(notes=[], texts_added=[], texts_removed=[], marks_added=[], marks_removed=[])
    na, nb = a.short_names(), b.short_names()
    strip = lambda x: " ".join(w for w in x.split() if not w.startswith("[") and not w.endswith("]") and ":" in w or w == "|")
    for si in range(min(len(a.staves), len(b.staves))):
        for bar in range(1, min(a.nbars, b.nbars) + 1):
            la, lb = strip(bar_line(a, si, bar)), strip(bar_line(b, si, bar))
            if la != lb: out["notes"].append(dict(staff=nb[si], bar=bar, before=la, after=lb))
    ta = collections.Counter((x[0], x[1], x[3], x[4]) for x in all_texts(a))
    tb = collections.Counter((x[0], x[1], x[3], x[4]) for x in all_texts(b))
    for k in sorted(tb - ta): out["texts_added"].append(dict(staff=nb[k[0]], bar=k[1], kind=k[2], text=k[3]))
    for k in sorted(ta - tb): out["texts_removed"].append(dict(staff=na[k[0]], bar=k[1], kind=k[2], text=k[3]))
    ma = collections.Counter((x[0], x[1], x[3]) for x in all_marks(a)); mb = collections.Counter((x[0], x[1], x[3]) for x in all_marks(b))
    for k in sorted(mb - ma): out["marks_added"].append(dict(staff=nb[k[0]], bar=k[1], mark=k[2]))
    for k in sorted(ma - mb): out["marks_removed"].append(dict(staff=na[k[0]], bar=k[1], mark=k[2]))
    if a.title() != b.title(): out["title"] = [a.title(), b.title()]
    if a.nbars != b.nbars: out["bars"] = [a.nbars, b.nbars]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original"); ap.add_argument("edited"); ap.add_argument("--json")
    a = ap.parse_args(); r = compare(Score(a.original), Score(a.edited))
    if a.json: json.dump(r, open(a.json, "w"), ensure_ascii=False, indent=1)
    for k in ("title", "bars"):
        if k in r: print(f"{k}: {r[k][0]} -> {r[k][1]}")
    for x in r["texts_added"]: print(f"text added    bar {x['bar']:3d} {x['staff']:5s} {x['kind']}: {x['text']}")
    for x in r["texts_removed"]: print(f"text removed  bar {x['bar']:3d} {x['staff']:5s} {x['kind']}: {x['text']}")
    for x in r["notes"]: print(f"notes changed bar {x['bar']:3d} {x['staff']:5s}\n    before: {x['before']}\n    after:  {x['after']}")
    for x in r["marks_added"]: print(f"mark added    bar {x['bar']:3d} {x['staff']:5s} {x['mark']}")
    for x in r["marks_removed"]: print(f"mark removed  bar {x['bar']:3d} {x['staff']:5s} {x['mark']}")
    n = sum(len(v) for k, v in r.items() if isinstance(v, list))
    print(f"{n} differences" if n else "no difference (layout and above/below flips ignored)")


if __name__ == "__main__":
    main()
