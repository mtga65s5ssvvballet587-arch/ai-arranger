#!/usr/bin/env python3
"""Lead rotation by pure re-assignment: whole bars of one staff's line are sung by another staff. No note changes
pitch or is re-voiced; only who sings what.

    python3 swap.py IN.mscz OUT.mscz plan.json [--melody Top] [--lead-labels]

plan.json: [{"from": 14, "to": 20, "take": {"2nd": "Top", "Top": "2nd"}},      # 2nd sings Top's line, Top sings 2nd's
            {"from": 22, "to": 26, "take": {"4th": "Top", "Top": "3rd", "3rd": "4th"}}]
Rehearsal marks, tempo, key and time signatures stay on their staff. Where the melody (--melody, the staff that
had the tune) changes singer across a tie, the leaving singer's tie ends at the barline and the tied-over note becomes
a rest for the new singer (reported: the only note lengths that change). --lead-labels writes "Lead" where the
singer of the melody changes. Check ranges afterwards (inspect_score.py bars): a line keeps its pitches.
"""
import sys, os, json, argparse, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, parse_staves, tie, make_text, first_event_index

KEEP = {"RehearsalMark", "Tempo", "KeySig", "TimeSig", "Clef"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("plan"); ap.add_argument("--melody", default="0")
    ap.add_argument("--lead-labels", action="store_true")
    a = ap.parse_args(); s = Score(a.src); mel = parse_staves(a.melody, s)[0]
    plan = [(p["from"], p["to"], {parse_staves(k, s)[0]: parse_staves(v, s)[0] for k, v in p["take"].items()}) for p in json.load(open(a.plan))]
    for b0, b1, perm in plan:
        for bar in range(b0, b1 + 1):
            vs = {i: s.voice(i, bar) for i in set(perm) | set(perm.values())}
            content = {i: [c for c in v if c.tag not in KEEP] for i, v in vs.items()}
            for i, v in vs.items():
                for c in content[i]: v.remove(c)
            for d, src in perm.items(): vs[d].extend(content[src])
    lead = {}
    for b0, b1, perm in plan:
        for bar in range(b0, b1 + 1): lead[bar] = next((d for d, x in perm.items() if x == mel), mel)
    for bar in range(1, s.nbars):
        k, k2 = lead.get(bar, mel), lead.get(bar + 1, mel)
        if k == k2: continue
        cut = False
        for ch in s.voice(k, bar).findall("Chord"):
            for n in ch.findall("Note"):
                sp = tie(n, "next")
                if sp is not None and sp.find("next/location/measures") is not None: n.remove(sp); cut = True
        if cut:
            v = s.voice(k2, bar + 1); first = next(c for c in v if c.tag in ("Chord", "Rest"))
            if first.tag == "Chord" and first.find("Lyrics") is None:
                r = ET.Element("Rest"); ET.SubElement(r, "durationType").text = first.findtext("durationType")
                i = list(v).index(first); v.remove(first); v.insert(i, r)
                print(f"tie cut at bar {bar}|{bar + 1}: the tied-over note becomes a rest")
            else: print(f"WARNING bar {bar}|{bar + 1}: tie removed, the next note was kept")
    if a.lead_labels:
        prev = None
        for bar in range(1, s.nbars + 1):
            cur = lead.get(bar, mel); v = s.voice(cur, bar)
            if cur != prev and any(c.tag == "Chord" for c in v): v.insert(first_event_index(v), make_text("StaffText", "Lead")); prev = cur
    s.save(a.dst); print(len(plan), "blocks re-assigned")


if __name__ == "__main__":
    main()
