#!/usr/bin/env python3
"""Write note and rest values by fixed rules (how the rhythm is spelled, never what sounds), optionally with a
breathing plan (rests cut out of long notes + breath marks) from breaths.py.

    python3 respell.py IN.mscz OUT.mscz [--plan breaths.json]

Rules (4/4, unit = 16th):
 - the middle of the bar stays visible: a note crossing beat 3 is tied there, except whole / dotted half from beat 1
   and half / dotted half from beat 2;
 - inside a half bar: half, dotted quarter (on the beat or after an 8th), quarter (on the beat or as 8th-quarter-8th),
   8th; as soon as a 16th position is involved every beat is shown (tie at the beat);
 - rests are never syncopated: whole-bar rest for an empty bar, half rest only on beat 1 / 3, quarter rest only on a
   beat, no dotted quarter rests, two 8th rests on one beat become a quarter rest;
 - notes tied inside a bar are first merged, then written again by these rules (ties across the barline are kept).
Bars with tuplets / several voices and percussion staves are left as they are. Check with render.py --midi that
the sound did not change (only a planned cut shortens a note, by an 8th).
"""
import sys, os, copy, json, argparse, collections, xml.etree.ElementTree as ET
from fractions import Fraction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, length, NAME
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--plan", help="breaths.json from breaths.py")
A = ap.parse_args()
PLAN = json.load(open(A.plan)) if A.plan else dict(cut=[], breath=[])
CUT = {(a, b) for a, b in PLAN["cut"]}; BREATH = {(a, b) for a, b in PLAN["breath"]}; done = collections.Counter()
SC = Score(A.src); root = SC.root; staves = SC.staves; SUNG = SC.sung_staves()

def in_beat(s, e): return [(s, e - s)]
def note_spell(s, e, L):
    n = e - s
    if L == 16:
        if (s == 0 and n in (16, 12)) or (s == 4 and n in (8, 12)): return [(s, n)]
        if s < 8 < e: return note_spell(s, 8, L) + note_spell(8, e, L)
    if s % 2 or e % 2:
        b = (s // 4 + 1) * 4
        return in_beat(s, b) + note_spell(b, e, L) if e > b else in_beat(s, e)
    r = s % 8
    if (n == 8 and r == 0) or (n == 6 and r in (0, 2)) or (n == 4 and r in (0, 2, 4)) or n == 2: return [(s, n)]
    b = (s // 4 + 1) * 4
    return note_spell(s, b, L) + note_spell(b, e, L)
def rest_spell(s, e, L):
    if s == 0 and e == L: return [(0, "measure")]
    out = []
    while s < e:
        if s % 8 == 0 and e - s >= 8: out.append((s, 8)); s += 8; continue
        b = min(e, (s // 4 + 1) * 4); r, n = s % 4, b - s
        if r == 0 and n in (4, 3, 2, 1): out.append((s, n))
        elif r == 1 and n == 3: out += [(s, 1), (s + 1, 2)]
        elif r == 1 and n == 2: out += [(s, 1), (s + 1, 1)]
        else: out.append((s, n))
        s = b
    return out

def tie(nt, kind): return next((sp for sp in nt.findall("Spanner") if sp.get("type") == "Tie" and sp.find(kind) is not None), None)
def set_dur(e, n):
    for t in ("durationType", "dots", "duration"):
        for k in e.findall(t): e.remove(k)
    if n == "measure": return
    nm, d = NAME[n]
    ET.SubElement(e, "x"); e.remove(e[-1])
    k = ET.Element("durationType"); k.text = nm; e.insert(0, k)
    if d: k = ET.Element("dots"); k.text = str(d); e.insert(0, k)

changed = collections.Counter(); total = 0
for si in SUNG:
    st = staves[si]
    flat = []                                   # (measure index, tick, chord element, tied to the next chord)
    B = 0                                       # absolute tick of the bar start
    for mi, m in enumerate(st.findall("Measure")):
        B0 = B; B += sum(length(k) for k in m.find("voice") if k.tag in ("Chord", "Rest"))
        vs = m.findall("voice")
        v = vs[0]; kids = list(v)
        if len(vs) != 1 or any(k.tag in ("Tuplet", "endTuplet", "location") for k in kids):
            t = 0
            for k in kids:
                if k.tag == "Chord": flat.append([mi, t, k, any(tie(nt, "next") is not None for nt in k.findall("Note"))])
                if k.tag in ("Chord", "Rest"): t += length(k)
            continue
        # 1. read: annotations by tick, segments (merged tied notes, merged rests)
        ann = collections.defaultdict(list); segs = []; t = 0
        for k in kids:
            if k.tag not in ("Chord", "Rest"): ann[t].append(k); continue
            n = length(k)
            if k.tag == "Rest":
                if segs and segs[-1]["el"] is None and t not in ann: segs[-1]["n"] += n
                else: segs.append(dict(s=t, n=n, el=None))
            else:
                nts = k.findall("Note"); p = segs[-1] if segs else None
                simple = all(c.tag in ("durationType", "dots", "Note") for c in k) and t not in ann
                if p and p["el"] is not None and p["out"] and simple and all(tie(x, "prev") is not None for x in nts) \
                        and [x.findtext("pitch") for x in nts] == [x.findtext("pitch") for x in p["el"].findall("Note")]:
                    p["n"] += n; p["out"] = all(tie(x, "next") is not None for x in nts)
                else:
                    segs.append(dict(s=t, n=n, el=k, out=bool(nts) and all(tie(x, "next") is not None for x in nts)))
            t += n
        L = t; total += 1
        # 1b. breathing plan: an 8th rest cut out of the end of a note, breath marks (commas) after a note
        for i, sg in enumerate(list(segs)):
            end = B0 + sg["s"] + sg["n"]
            if sg["el"] is not None and not sg["out"] and (si, end) in CUT:
                done["cut"] += 1
                if sg["n"] > 2: sg["n"] -= 2; segs.insert(segs.index(sg) + 1, dict(s=sg["s"] + sg["n"], n=2, el=None))
                else:
                    sg["el"] = None
                    if flat and flat[-1][3] and flat[-1][0] == mi - 1: flat[-1][3] = False
            if sg["el"] is not None and not sg["out"] and (si, end) in BREATH:
                done["breath"] += 1; br = ET.Element("Breath"); ET.SubElement(br, "symbol").text = "breathMarkComma"; ann[sg["s"] + sg["n"]].append(br)
        mg = []
        for sg in segs:
            if mg and mg[-1]["el"] is None and sg["el"] is None and sg["s"] not in ann: mg[-1]["n"] += sg["n"]
            else: mg.append(sg)
        segs = mg
        old = [(k.tag, length(k)) for k in kids if k.tag in ("Chord", "Rest")]
        # 2. write again
        for k in kids: v.remove(k)
        new = []
        for sg in segs:
            cuts = [sg["s"]] + [a for a in sorted(ann) if sg["s"] < a < sg["s"] + sg["n"]] + [sg["s"] + sg["n"]]
            pieces = []
            for a, b in zip(cuts, cuts[1:]):
                pieces += rest_spell(a, b, L) if sg["el"] is None else note_spell(a, b, L)
            for i, (s, n) in enumerate(pieces):
                for a in ann.pop(s, []): v.append(a)
                if sg["el"] is None:
                    e = ET.SubElement(v, "Rest"); set_dur(e, 4 if n == "measure" else n)
                    if n == "measure":
                        e.find("durationType").text = "measure"; ET.SubElement(e, "duration").text = f"{Fraction(L, 16).numerator * (16 // Fraction(L, 16).denominator) // (16 // Fraction(L, 16).denominator)}/{Fraction(L, 16).denominator}" if L != 16 else "4/4"
                    new.append(("Rest", L if n == "measure" else n))
                else:
                    if i == 0: e = sg["el"]
                    else:
                        e = ET.Element("Chord")
                        for nt in sg["el"].findall("Note"):
                            c = copy.deepcopy(nt)
                            for k in list(c):
                                if k.tag in ("Accidental", "Spanner"): c.remove(k)
                            e.append(c)
                    for nt in e.findall("Note"):
                        for sp in [sp for sp in nt.findall("Spanner") if sp.get("type") == "Tie"]: nt.remove(sp)
                    set_dur(e, n); v.append(e)
                    flat.append([mi, s, e, True if i < len(pieces) - 1 else sg["out"]]); new.append(("Chord", n))
        for a in sorted(ann):
            for k in ann[a]: v.append(k)
        if new != old: changed[si] += 1
    # 3. ties, written again from the flat list
    def loc(dm, dt):
        l = ET.Element("location")
        if dm: ET.SubElement(l, "measures").text = str(dm)
        if dt: ET.SubElement(l, "fractions").text = str(Fraction(dt, 16)) if Fraction(dt, 16).denominator != 1 else f"{Fraction(dt, 16).numerator}/1"
        return l
    for a, b in zip(flat, flat[1:]):
        for nt in a[2].findall("Note"):
            for sp in [sp for sp in nt.findall("Spanner") if sp.get("type") == "Tie" and sp.find("next") is not None]: nt.remove(sp)
        for nt in b[2].findall("Note"):
            for sp in [sp for sp in nt.findall("Spanner") if sp.get("type") == "Tie" and sp.find("prev") is not None]: nt.remove(sp)
    for a, b in zip(flat, flat[1:]):
        if not a[3]: continue
        for nt in a[2].findall("Note"):
            tg = [x for x in b[2].findall("Note") if x.findtext("pitch") == nt.findtext("pitch")]
            if not tg: continue
            sp = ET.Element("Spanner", type="Tie"); ET.SubElement(sp, "Tie"); ET.SubElement(sp, "next").append(loc(b[0] - a[0], b[1] - a[1])); nt.insert(0, sp)
            sp = ET.Element("Spanner", type="Tie"); ET.SubElement(sp, "prev").append(loc(a[0] - b[0], a[1] - b[1])); tg[0].insert(0, sp)
print("plan applied:", dict(done), "of", len(CUT), "cuts and", len(BREATH), "breaths")
print("bars re-spelled per staff:", dict(changed), "of", total)
SC.save(A.dst)
