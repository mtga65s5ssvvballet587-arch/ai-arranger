#!/usr/bin/env python3
"""Look inside a MuseScore file without opening MuseScore.

    python3 inspect_score.py SCORE.mscz info                  # parts, bars, key, rehearsal marks
    python3 inspect_score.py SCORE.mscz bars 12-15 [--staves Top,3rd]
    python3 inspect_score.py SCORE.mscz texts                 # every text: staff, bar, kind, text
    python3 inspect_score.py SCORE.mscz marks                 # dynamics, articulations, breaths, tempo, hairpins

`bars` prints one line per staff and bar: pitch:length(16ths) with ~ for a tie and (lyric), r:length for rests,
[Kind:text] for annotations; x for unpitched (drum) notes.
"""
import sys, argparse, collections, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, length, text_of, lyric, tie, pitch_name, parse_bars, parse_staves

TEXTS = {"StaffText", "SystemText", "RehearsalMark", "Tempo", "Expression", "InstrumentChange", "Fingering", "Sticking",
         "PlayTechAnnotation", "Marker", "Jump"}


def bar_line(s, si, bar):
    out = []
    for k, v in enumerate(s.measure(si, bar).findall("voice")):
        if k: out.append("|")
        for e in v:
            if e.tag == "Rest": out.append(f"r:{length(e)}")
            elif e.tag == "Chord":
                n = e.find("Note"); ly = lyric(e)
                p = "x" if s.is_percussion(si) else "+".join(pitch_name(int(x.findtext("pitch"))) for x in e.findall("Note"))
                out.append(f"{p}:{length(e)}{'~' if tie(n, 'next') is not None else ''}{f'({ly})' if ly else ''}")
            elif e.tag == "Dynamic": out.append(f"[Dynamic:{e.findtext('subtype')}]")
            elif e.tag in TEXTS: out.append(f"[{e.tag}:{text_of(e)}]")
    return " ".join(out)


def all_texts(s):
    rows = []
    for si in range(len(s.staves)):
        for b, t, e, v in s.events(si):
            if e.tag in TEXTS: rows.append((si, b, t, e.tag, text_of(e).replace("\n", " / ")))
    for vb in s.sc.iter("VBox"):
        for t in vb.findall("Text"): rows.append((0, 0, 0, "Frame:" + (t.findtext("style") or ""), text_of(t)))
    return rows


def all_marks(s):
    """[(staff, bar, kind)] for dynamics, articulations (Above/Below ignored), breaths, tempo, hairpins, fermatas."""
    rows = []
    for si in range(len(s.staves)):
        for b, t, e, v in s.events(si):
            if e.tag == "Dynamic": rows.append((si, b, t, "dynamic " + (e.findtext("subtype") or "")))
            elif e.tag == "Breath": rows.append((si, b, t, "breath"))
            elif e.tag == "Tempo": rows.append((si, b, t, "tempo " + text_of(e)))
            elif e.tag == "Spanner" and e.get("type") not in ("Tie",) and e.find("next") is not None:
                rows.append((si, b, t, "start " + e.get("type")))
            elif e.tag == "Chord":
                for a in e.findall("Articulation"):
                    rows.append((si, b, t, (a.findtext("subtype") or "").replace("Above", "").replace("Below", "")))
                for sp in e.findall("Spanner"):
                    if sp.get("type") == "Slur" and sp.find("next") is not None: rows.append((si, b, t, "start Slur"))
            elif e.tag == "Fermata": rows.append((si, b, t, "fermata"))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("score"); ap.add_argument("what", choices=["info", "bars", "texts", "marks"])
    ap.add_argument("range", nargs="?"); ap.add_argument("--staves")
    a = ap.parse_args(); s = Score(a.score); names = s.short_names()
    if a.what == "info":
        print("title:", s.title()); print("bars:", s.nbars, "| key (fifths):", s.key_fifths())
        for i, n in enumerate(s.staff_names()): print(f"staff {i}: {n}{'  (percussion)' if s.is_percussion(i) else ''}")
        print("rehearsal marks:", ", ".join(f"{b} {t}" for b, t in s.marks()))
        odd = [b for b, n in enumerate(s.bar_lengths(), 1) if n != s.bar_lengths()[1]]
        if odd: print("bars of another length:", odd)
    elif a.what == "bars":
        bars = sorted(parse_bars(a.range, s.nbars)); sts = parse_staves(a.staves, s) if a.staves else range(len(s.staves))
        for b in bars:
            for si in sts: print(f"{b:4d} {names[si]:6s} {bar_line(s, si, b)}")
    elif a.what == "texts":
        for si, b, t, k, x in all_texts(s): print(f"{names[si]}\t{b}\t{t}\t{k}\t{x}")
    else:
        for si, b, t, k in all_marks(s): print(f"{names[si]}\t{b}\t{t}\t{k}")


if __name__ == "__main__":
    main()
