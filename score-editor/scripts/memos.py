#!/usr/bin/env python3
"""Bring someone's own notes into the direction style, and copy each note to the bars that repeat it.

    python3 memos.py EDITED.mscz OUT.mscz --original SENT.mscz [--label 【メモ】] [--no-repeats]

Their notes = the staff texts of EDITED that the version you sent them (--original) does not have. Without
--original, a guess: every staff text except MC lines (「...」), shouts ((...)) and the words in --keep.
Each note becomes a system text "【メモ】..." above the top staff at the same beat (part-specific: "【メモ（3rd）】..." when written on a staff other than the one most notes are on).
A repeat = a bar where the staff the note was written on has the same pitches and rhythm (lyrics ignored) AND so
does the bar before or after; the copy says where it comes from: "【メモ】（63小節と同じ）...".
Run compare_scores.py first to see everything they changed (notes, tempo, dynamics are not touched here).
"""
import sys, os, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, length, text_of, make_text, insert_at


def signatures(s, si):
    out = []
    for m in s.staves[si].findall("Measure"):
        sig = []
        for v in m.findall("voice"):
            for e in v:
                if e.tag == "Chord": sig.append((tuple(sorted(n.findtext("pitch") for n in e.findall("Note"))), length(e)))
                elif e.tag == "Rest": sig.append(("r", length(e)))
        out.append(tuple(sig))
    return out


def repeats_of(s, si, bar):
    S = signatures(s, si); n = len(S); b = bar - 1
    if all(x[0] == "r" for x in S[b]): return []
    return [o + 1 for o in range(n) if o != b and S[o] == S[b] and
            ((b > 0 and o > 0 and S[o - 1] == S[b - 1]) or (b + 1 < n and o + 1 < n and S[o + 1] == S[b + 1]))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--keep", default="Lead,Solo,Rap,(MC)")
    ap.add_argument("--label", default="【メモ】"); ap.add_argument("--no-repeats", action="store_true")
    ap.add_argument("--size", type=float, default=10); ap.add_argument("--original")
    a = ap.parse_args(); s = Score(a.src); names = s.short_names()
    sent = collections.Counter()
    if a.original:
        o = Score(a.original)
        for si in o.sung_staves():
            for b, t, e, v in o.events(si):
                if e.tag == "StaffText": sent[(si, b, text_of(e))] += 1
    keep = [k.strip() for k in a.keep.split(",") if k.strip()]
    found = []
    for si in s.sung_staves():
        for b, t, e, v in list(s.events(si)):
            if e.tag != "StaffText": continue
            x = text_of(e)
            if a.original:
                if sent[(si, b, x)] > 0: sent[(si, b, x)] -= 1; continue
            elif not x or x[0] in "「(（" or any(x.startswith(k) for k in keep): continue
            found.append((si, b, t, x)); v.remove(e)
    common = collections.Counter(f[0] for f in found).most_common(1)[0][0] if found else None
    for si, b, t, x in found:
        lines = [l.strip() for l in x.replace("。", "。\n").splitlines() if l.strip()]
        lab = a.label if si == common else a.label.replace("】", f"（{names[si]}）】")
        insert_at(s.voice(0, b), t, make_text("SystemText", lab + "\n".join(lines), size=a.size)); print(f"bar {b}: {lab}{' '.join(lines)}")
        if a.no_repeats: continue
        for rb in repeats_of(s, si, b):
            insert_at(s.voice(0, rb), t, make_text("SystemText", f"{lab}（{b}小節と同じ）\n" + "\n".join(lines), size=a.size))
            print(f"   also bar {rb} (repeats bar {b})")
    s.save(a.dst); print(len(found), "notes")


if __name__ == "__main__":
    main()
