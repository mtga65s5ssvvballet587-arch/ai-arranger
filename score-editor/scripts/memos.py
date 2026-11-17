#!/usr/bin/env python3
"""Bring someone's own notes into the direction style, and copy each note to the bars that repeat it.

    python3 memos.py EDITED.mscz OUT.mscz --original SENT.mscz [--label 【メモ】] [--no-repeats]

Their notes = the staff texts of EDITED that the version you sent them (--original) does not have; MC lines (「...」),
shouts ((...)) and the words in --keep are never notes (an MC line they rewrote stays an MC line). Notes written on
--general (default: the staff with most notes) are for everyone; the others carry the part: 【メモ（3rd）】.
Each note becomes a system text "【メモ】..." above the top staff at the same beat (part-specific: "【メモ（3rd）】..." when written on a staff other than the one most notes are on).
A repeat = a bar where the staff the note was written on has the same pitches and rhythm (lyrics ignored) AND so
does the bar before or after; the copy says where it comes from: "【メモ】（63小節と同じ）...".
Repeats are looked up in --original (the shape before their edits), so a bar they changed still finds its repeats.
--spread-edits: what they changed by hand in the notes of a bar (a rest joined, a rhythm, a syllable) and a
crescendo they added are copied to the repeats of that bar too, when the repeat is still as it was sent
(the level is written again where a copied crescendo ends, so the playback comes back down).
Run compare_scores.py first to see everything they changed.
"""
import sys, os, copy, argparse, collections
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, length, text_of, make_text, insert_at, first_event_index, lyric, tie, tied_in
VEL = dict(pp=33, p=49, mp=64, mf=80, f=96, ff=112, fff=126)


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
    ap.add_argument("--spread-edits", action="store_true")
    ap.add_argument("--general", help="staff whose notes are meant for everyone (no part label); default: the staff with most notes")
    a = ap.parse_args(); s = Score(a.src); names = s.short_names()
    sent = collections.Counter()
    if a.original:
        o = Score(a.original)
        for si in o.sung_staves():
            for b, t, e, v in o.events(si):
                if e.tag == "StaffText": sent[(si, b, text_of(e))] += 1
    keep = [k.strip() for k in a.keep.split(",") if k.strip()]
    rep = Score(a.original) if a.original else s           # repeats are found in the shape before the edits
    found = []
    for si in s.sung_staves():
        for b, t, e, v in list(s.events(si)):
            if e.tag != "StaffText": continue
            x = text_of(e)
            if a.original and sent[(si, b, x)] > 0: sent[(si, b, x)] -= 1; continue
            if not x or x[0] in "「(（" or any(x.startswith(k) for k in keep): continue     # MC lines, shouts, labels
            found.append((si, b, t, x)); v.remove(e)
    common = collections.Counter(f[0] for f in found).most_common(1)[0][0] if found else None
    if a.general: from msx import parse_staves; common = parse_staves(a.general, s)[0]
    for si, b, t, x in found:
        lines = [l.strip() for l in x.replace("。", "。\n").splitlines() if l.strip()]
        lab = a.label if si == common else a.label.replace("】", f"（{names[si]}）】")
        insert_at(s.voice(0, b), t, make_text("SystemText", lab + "\n".join(lines), size=a.size)); print(f"bar {b}: {lab}{' '.join(lines)}")
        if a.no_repeats: continue
        for rb in repeats_of(rep, si, b):
            insert_at(s.voice(0, rb), t, make_text("SystemText", f"{lab}（{b}小節と同じ）\n" + "\n".join(lines), size=a.size))
            print(f"   also bar {rb} (repeats bar {b})")
    if a.spread_edits:
        if not a.original: sys.exit("--spread-edits needs --original")
        spread(s, rep)
    s.save(a.dst); print(len(found), "notes")


NOTE_TAGS = {"Chord", "Rest", "Tuplet", "endTuplet", "Beam"}


def shape(sc, si, b):
    """What is sung in a bar: (rest | pitches, length, tied on, lyric) for every chord / rest, no annotation."""
    out = []
    for v in sc.measure(si, b).findall("voice"):
        for e in v:
            if e.tag == "Rest": out.append(("r", length(e)))
            elif e.tag == "Chord":
                ns = e.findall("Note")
                out.append((tuple(n.findtext("pitch") for n in ns), length(e),
                            any(tie(n, "next") is not None for n in ns), lyric(e)))
    return tuple(out)


def hairpins(sc, si, b):
    return [e for e in sc.voice(si, b) if e.tag == "Spanner" and e.get("type") == "HairPin" and e.find("next") is not None]


def spread(s, o):
    """Copy hand edits of a bar (notes, and crescendo hairpins they added) to that bar's untouched repeats.
    All edits are found first, against the score as they sent it, then applied."""
    names = s.short_names(); n = 0; edits = []
    for si in s.sung_staves():
        for b in range(1, s.nbars + 1):
            nb_, ob_ = shape(s, si, b), shape(o, si, b)
            hp_new = hairpins(s, si, b)[len(hairpins(o, si, b)):]
            if nb_ == ob_ and not hp_new: continue
            reps = [rb for rb in repeats_of(o, si, b) if shape(s, si, rb) == shape(o, si, rb) and not hairpins(s, si, rb)[len(hairpins(o, si, rb)):]]
            src = [copy.deepcopy(e) for e in s.voice(si, b)]
            ticks = []; t = 0
            for e in s.voice(si, b):
                ticks.append(t)
                if e.tag in ("Chord", "Rest"): t += length(e)
            hp = []
            for h in hp_new:
                i = list(s.voice(si, b)).index(h); k = int(h.findtext("next/location/measures") or 0)
                end = next((copy.deepcopy(e) for e in s.voice(si, b + k) if e.tag == "Spanner" and e.get("type") == "HairPin" and e.find("prev") is not None), None)
                hp.append((ticks[i], copy.deepcopy(h), k, end))
            edits.append((si, b, nb_ != ob_, src, hp, reps))
    for si, b, notes_changed, src, hp, reps in edits:
        for rb in reps:
            v = s.voice(si, rb)
            if notes_changed:
                keep = [(t, e) for bb, t, e, vv in s.events(si, bars={rb}, voice=0) if e.tag not in NOTE_TAGS]
                for e in list(v): v.remove(e)
                for e in src:
                    if e.tag in NOTE_TAGS: v.append(copy.deepcopy(e))
                for t, e in keep: insert_at(v, t, e)
                print(f"   {names[si]} bar {rb}: notes as in bar {b}"); n += 1
            for t, h, k, end in hp:
                insert_at(v, t, copy.deepcopy(h))
                if end is not None and rb + k <= s.nbars:
                    ve = s.voice(si, rb + k); ve.insert(first_event_index(ve), copy.deepcopy(end))
                    level = None                                   # a hairpin must end on a written dynamic
                    for bb in range(1, rb + k):
                        for e in s.voice(si, bb):
                            if e.tag == "Dynamic": level = e.findtext("subtype")
                    c = next((e for e in ve if e.tag == "Chord" and not tied_in(e)), None)
                    if level and c is not None and not any(e.tag == "Dynamic" for e in ve):
                        d = ET.Element("Dynamic"); ET.SubElement(d, "subtype").text = level
                        ET.SubElement(d, "velocity").text = str(VEL.get(level, 80)); ve.insert(list(ve).index(c), d)
                print(f"   {names[si]} bar {rb}: crescendo as in bar {b}"); n += 1
    print(n, "edits spread to repeats")


if __name__ == "__main__":
    main()
