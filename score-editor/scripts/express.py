#!/usr/bin/env python3
"""Dynamics, crescendo hairpins and articulations from a plan (JSON); the notes are not touched.

    python3 express.py IN.mscz OUT.mscz plan.json
    python3 velocity.py OUT.mscz          # then ALWAYS check what MuseScore will play

plan.json (staves by name as the score shows them - "Top", "2nd", ... - or by number; "all" = every sung staff):
{
  "dynamics":  {"2": {"Top": "mp", "3rd": "mp"}, "12": {"Top": "f", "2nd": "mf"}},   # bar -> staff -> p..ff
  "crescendo": [{"from": 46, "to": 47, "staves": "all"}],          # hairpin over bars from..to, ends at to+1
  "staccato":  {"syllables": ["ta", "ra", "tu"], "max_length": 2},  # short scat notes sung short
  "accents":   [{"bar": 12, "staves": ["2nd"], "lyric": "pa"},      # which notes of the bar:
                {"bar": 20, "staves": "all", "after_rest": true, "lyrics": ["ta", "la"]},
                {"bar": 31, "staves": ["2nd"], "first": true},      #   lyric / lyrics / after_rest / first,
                {"bar": 63, "staves": ["Top"]}],                    #   nothing = every note (not tied into)
  "tenuto":    [ ... same form ... ],
  "drums_follow": "Bass"                                          # percussion staves get that staff's dynamics
}
Playback: MuseScore plays a dynamic as a velocity (p 49, mp 64, mf 80, f 96, ff 112) and a hairpin raises it until
the next dynamic. So a hairpin always ends on a written dynamic: where the plan has none for that staff, the level
it had before is written again (also when the hairpin ends on rests: at the staff's next note).
"""
import sys, os, json, argparse, collections, xml.etree.ElementTree as ET
from fractions import Fraction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, length, lyric, tied_in, tied_out, parse_staves, first_event_index

VEL = dict(pp=33, p=49, mp=64, mf=80, f=96, ff=112, fff=126)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("plan")
    a = ap.parse_args(); s = Score(a.src); P = json.load(open(a.plan)); nb = s.nbars
    sung = s.sung_staves()
    st = lambda spec: sung if spec in (None, "all") else parse_staves(",".join(map(str, spec)) if isinstance(spec, list) else str(spec), s)
    V = lambda si, bar: s.voice(si, bar)
    DYN = {int(b): {st(k)[0]: v for k, v in d.items()} for b, d in P.get("dynamics", {}).items()}
    CRESC = [(c["from"], c["to"], st(c.get("staves"))) for c in P.get("crescendo", [])]
    sc = P.get("staccato", {}); STACC = set(sc.get("syllables", [])); SMAX = sc.get("max_length", 2)
    cnt = collections.Counter()

    def artic(c, sym):
        if any(x.findtext("subtype") == sym for x in c.findall("Articulation")): return
        x = ET.Element("Articulation"); ET.SubElement(x, "subtype").text = sym
        c.insert(list(c).index(c.find("Note")), x); cnt[sym] += 1

    def after_rest(v, c):
        k = list(v); i = k.index(c); p = [x for x in k[:i] if x.tag in ("Chord", "Rest")]
        return not p or p[-1].tag == "Rest"

    def matches(rule, v, c):
        if "lyric" in rule and lyric(c) != rule["lyric"]: return False
        if "lyrics" in rule and lyric(c) not in rule["lyrics"]: return False
        if rule.get("after_rest") and not after_rest(v, c): return False
        if rule.get("first") and c is not [x for x in v if x.tag == "Chord"][0]: return False
        return True

    for si in sung:
        for bar in range(1, nb + 1):
            for c in V(si, bar).findall("Chord"):
                if lyric(c) in STACC and length(c) <= SMAX and not tied_out(c): artic(c, "articStaccatoAbove")
    for key, sym in (("accents", "articAccentAbove"), ("tenuto", "articTenutoAbove")):
        for rule in P.get(key, []):
            for si in st(rule.get("staves")):
                v = V(si, rule["bar"])
                for c in v.findall("Chord"):
                    if not tied_in(c) and matches(rule, v, c): artic(c, sym)

    def first_chord(si, bar, upto):
        for b in range(bar, upto + 1):
            v = V(si, b); t = 0
            for c in v:
                if c.tag == "Chord" and not tied_in(c): return b, v, c, t
                if c.tag in ("Chord", "Rest"): t += length(c)
        return None

    def dynamic(d):
        e = ET.Element("Dynamic"); ET.SubElement(e, "subtype").text = d; ET.SubElement(e, "velocity").text = str(VEL[d]); return e

    cur = {}; stale = set()
    HP_END = {(si, b + 1) for a_, b, sts in CRESC for si in sts if b + 1 <= nb}
    BARS = sorted(set(DYN) | {bb for _, bb in HP_END})
    for bar in BARS:
        nxt = min([b for b in BARS if b > bar], default=nb + 1)
        for si in sung:
            d = DYN.get(bar, {}).get(si); forced = (si, bar) in HP_END or si in stale
            if d is None and forced: d = cur.get(si)
            if d is None: continue
            f = first_chord(si, bar, min(bar + 3, nxt - 1, nb))
            if not f:
                if forced: stale.add(si)
                continue
            if cur.get(si) == d and not forced: continue
            stale.discard(si)
            b, v, c, t = f; v.insert(list(v).index(c), dynamic(d)); cur[si] = d; cnt["dynamic " + d] += 1
    follow = P.get("drums_follow")
    if follow is not None:
        fs = st(follow)[0]
        for ps in [i for i in range(len(s.staves)) if s.is_percussion(i)]:
            for bar in sorted(DYN):
                d = DYN[bar].get(fs)
                if d: v = V(ps, bar); v.insert(first_event_index(v), dynamic(d)); cnt["percussion " + d] += 1
    for a_, b, sts in CRESC:
        for si in sts:
            f = first_chord(si, a_, b)
            if not f or b + 1 > nb: continue
            sb, v, c, t = f

            def loc(sign):
                l = ET.Element("location"); ET.SubElement(l, "measures").text = str(sign * (b + 1 - sb))
                if t: ET.SubElement(l, "fractions").text = str(Fraction(-sign * t, 16))
                return l
            h = ET.Element("Spanner", type="HairPin"); ET.SubElement(ET.SubElement(h, "HairPin"), "subtype").text = "0"
            ET.SubElement(h, "next").append(loc(1)); v.insert(list(v).index(c), h)
            e = ET.Element("Spanner", type="HairPin"); ET.SubElement(e, "prev").append(loc(-1))
            v2 = V(si, b + 1); k = list(v2); v2.insert(next(i for i, x in enumerate(k) if x.tag in ("Chord", "Rest")), e); cnt["crescendo"] += 1
    print(dict(cnt)); s.save(a.dst)


if __name__ == "__main__":
    main()
