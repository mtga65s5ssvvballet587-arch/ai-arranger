#!/usr/bin/env python3
"""Read how an a cappella score is built along the song: one line per bar with what every part does, cut at the
rehearsal marks, plus counts of the arranger's moves at section changes.

    $ACAP_PY score_story.py SCORE.musicxml [SCORE2.musicxml ...] [--out DIR] [--names names.json]

Per bar (vocal parts in score order, the last one is the bass; percussion staves apart):
  roles  W = sings real words, w = words in the lead's rhythm (word harmony, "字ハモ"), P = pad (notes >= half a bar),
         C = comp (4+ attacks on 1-2 pitches), M = moving line on vocables, - = rests
  bass / VP = 16th grid of attacks ('X'), VP also with its number of attacks
Summary over all scores given (written to DIR/summary.md and DIR/summary.json):
  - word harmony by section type and by position in the 4-bar phrase;
  - the bar before a rehearsal mark vs the three bars before it: VP fill (pattern change, attack count), break
    (voices dropping out), everyone in one rhythm (a hit), lead alone;
  - the first bar of a section vs the bar before: voices entering / leaving, role changes;
  - most common VP fill grids and grooves, bass grids per section type.
"""
import argparse, collections, json, os, re, sys
import xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import corpus_stats as C

JP = re.compile(r"[぀-ヿ一-鿿]")
JP_VOC = re.compile(r"^[ウうアあオおフふハはラらルるンんーっッ〜~!！]+$")


def is_word(s):
    if not s: return False
    if JP.search(s): return not JP_VOC.match(s)
    return not C.is_vocable(s) and len(re.sub(r"[^A-Za-z]", "", s)) >= 2


def kind(mark):
    m = mark.lower()
    for k, pat in (("last chorus", r"ラスサビ|落ちサビ|大サビ"), ("chorus", r"サビ|chorus"), ("intro", r"イントロ|intro"),
                   ("outro", r"アウトロ|outro"), ("interlude", r"間奏|interlude"), ("bridge", r"cメロ|dメロ|bridge"),
                   ("B", r"bメロ|^b[-－ー\d ]|^b$"), ("A", r"aメロ|^a[-－ー\d ]|^a$")):
        if re.search(pat, m): return k
    return "other"


def marks_of(path):
    r = C.strip_ns(C.load_xml(path)); out = {}
    for p in r.iter("part"):
        for i, m in enumerate(p.findall("measure")):
            for d in m.iter("rehearsal"):
                if d.text and d.text.strip(): out.setdefault(i, d.text.strip())
    return out


def grid(ns, b0):
    g = ["."] * 16
    for x in ns:
        k = int(round((x[0] - b0) * 4))
        if 0 <= k < 16: g[k] = "X"
    return "".join(g)


def story(path):
    sc = C.read_score(path)
    if not sc: return None
    voc = [l for l in sc["lines"] if not l["perc"]]; perc = [l for l in sc["lines"] if l["perc"]]
    marks = marks_of(path); bars = []; cur = ("", "other")
    for bi, (b0, blen, beats, btype) in enumerate(sc["bars"]):
        if bi in marks: cur = (marks[bi], kind(marks[bi]))
        per = [[n for n in l["notes"] if b0 - 1e-6 <= n[0] < b0 + blen - 1e-6] for l in voc]
        held = [any(n[0] < b0 - 1e-6 and n[0] + n[1] > b0 + 1e-6 for n in l["notes"]) for l in voc]
        words = [sum(is_word(n[3]) for n in ns) for ns in per]
        lead = max(range(len(voc)), key=lambda k: (words[k], -k)) if any(words) else None
        lg = grid(per[lead], b0) if lead is not None else None
        roles = []
        for k, ns in enumerate(per):
            if not ns: roles.append("P" if held[k] else "-"); continue
            g = grid(ns, b0)
            if words[k] >= max(1, len(ns) // 2):
                same = lead is not None and k != lead and sum(a == b == "X" for a, b in zip(g, lg)) >= 0.7 * g.count("X")
                roles.append("W" if k == lead else ("w" if same else "W"))
            elif all(n[1] >= blen / 2 - 1e-6 for n in ns): roles.append("P")
            elif len(ns) >= 4 and len({n[2] for n in ns}) <= 2: roles.append("C")
            else: roles.append("M")
        pv = [n for l in perc for n in l["notes"] if b0 - 1e-6 <= n[0] < b0 + blen - 1e-6]
        bars.append(dict(bar=bi + 1, mark=marks.get(bi), kind=cur[1], roles="".join(roles), lead=lead,
                         bass=grid(per[-1], b0) if per else "", vp=grid(pv, b0), vp_n=len({round(n[0], 3) for n in pv}),
                         on=[len(ns) for ns in per], four=(beats, btype) == (4, 4)))
    return dict(parts=[l["name"] for l in voc], bars=bars)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scores", nargs="+"); ap.add_argument("--out", default="story"); ap.add_argument("--names")
    a = ap.parse_args()
    names = json.load(open(a.names)) if a.names else {}
    os.makedirs(a.out, exist_ok=True)
    A = collections.defaultdict(collections.Counter); fills = collections.Counter(); grooves = collections.Counter()
    bassg = collections.defaultdict(collections.Counter); md = []
    for path in a.scores:
        st = story(path)
        if not st: continue
        title = names.get(os.path.basename(path), os.path.basename(path)); B = st["bars"]
        md.append(f"\n## {title}  ({len(B)} bars; parts: {', '.join(st['parts'])})\n```")
        for b in B:
            if b["mark"]: md.append(f"--- {b['mark']}  [{b['kind']}]")
            md.append(f"{b['bar']:4d} {b['roles']:8s} bass {b['bass']}  vp {b['vp']} ({b['vp_n']})")
        md.append("```")
        starts = [i for i, b in enumerate(B) if b["mark"]]
        for i, b in enumerate(B):
            k = b["kind"]; bg = b["roles"][:-1]
            lead = b["lead"]
            others = [r for j, r in enumerate(bg) if j != lead]
            A[f"bars {k}"]["n"] += 1
            nw = sum(r in "Ww" for r in others) if lead is not None else 0
            A[f"word harmony {k}"][min(nw, 3)] += 1
            for r in others: A[f"roles {k}"][r] += 1
            A[f"active {k}"][sum(r != "-" for r in b["roles"])] += 1
            if b["four"] and b["bass"].count("X"): bassg[k][b["bass"]] += 1
            sec0 = max([s for s in starts if s <= i], default=0)
            if nw: A["word harmony at phrase bar (1-4)"][(i - sec0) % 4 + 1] += 1
            if lead is not None: A["lead bars at phrase bar (1-4)"][(i - sec0) % 4 + 1] += 1
        for s in starts:
            if s < 4: continue
            pre, ref, nxt = B[s - 1], B[s - 4:s - 1], B[s]
            key = f"into {nxt['kind']}"
            A[key]["n"] += 1
            common = collections.Counter(r["vp"] for r in ref).most_common(1)[0][0]
            refn = sum(r["vp_n"] for r in ref) / 3
            if pre["vp"] != common and pre["vp_n"]:
                A[key]["VP fill (pattern changes)"] += 1; fills[pre["vp"]] += 1
            if pre["vp_n"] > refn * 1.25: A[key]["VP busier"] += 1
            if pre["vp_n"] < refn * 0.5: A[key]["VP drops out / stops"] += 1
            act = lambda b: sum(r != "-" for r in b["roles"])
            if act(pre) <= max(r_ for r_ in map(act, ref)) - 2: A[key]["break (2+ voices drop)"] += 1
            g = [x for x in [pre["roles"]] ]
            if len(set(pre["roles"][:-1]) - {"-"}) == 1 and act(pre) >= 3 and pre["roles"][0] in "Ww": A[key]["all voices sing the words"] += 1
            if pre["roles"].count("P") >= 2 and sum(r.count("P") for r in map(lambda r: r["roles"], ref)) / 3 < 1.5: A[key]["long notes (hold / swell)"] += 1
            if act(nxt) > act(pre): A[key]["voices enter on the downbeat"] += 1
            if act(nxt) < act(pre): A[key]["voices leave on the downbeat"] += 1
            if nxt["vp_n"] > pre["vp_n"] * 1.25 and nxt["vp_n"] > refn * 1.25: A[key]["VP busier in the new section"] += 1
            if nxt["vp_n"] < refn * 0.5: A[key]["VP thinner / out in the new section"] += 1
            pr, nr = collections.Counter(ref[-1]["roles"][:-1]), collections.Counter(nxt["roles"][:-1])
            A[key][f"backgrounds mostly {pr.most_common(1)[0][0]} -> {nr.most_common(1)[0][0]}"] += 1
        for b in B:
            if b["four"] and b["vp_n"]: grooves[(b["kind"], b["vp"])] += 1
    open(os.path.join(a.out, "timeline.md"), "w").write("\n".join(md))
    out = ["# How the songs are built (score_story.py)", "",
           "roles: W words, w words in the lead's rhythm, P pad, C comp, M moving vocables, - rest", ""]
    kinds = ["intro", "A", "B", "chorus", "last chorus", "bridge", "interlude", "outro", "other"]
    out += ["## Word harmony (background voices singing the words)", "| section | bars | 0 voices | 1 | 2 | 3+ |", "|---|---|---|---|---|---|"]
    for k in kinds:
        c = A[f"word harmony {k}"]; n = sum(c.values())
        if n: out.append(f"| {k} | {n} | " + " | ".join(f"{c[i] / n:.0%}" for i in range(4)) + " |")
    c, l = A["word harmony at phrase bar (1-4)"], A["lead bars at phrase bar (1-4)"]
    out += ["", "Share of lead bars with word harmony, by bar of the 4-bar phrase: " +
            ", ".join(f"bar {i}: {c[i] / max(1, l[i]):.0%}" for i in range(1, 5)), ""]
    out += ["## What the background voices do, per section type", "| section | W/w words | P pad | C comp | M moving | - rest |", "|---|---|---|---|---|---|"]
    for k in kinds:
        c = A[f"roles {k}"]; n = sum(c.values())
        if n: out.append(f"| {k} | {(c['W'] + c['w']) / n:.0%} | {c['P'] / n:.0%} | {c['C'] / n:.0%} | {c['M'] / n:.0%} | {c['-'] / n:.0%} |")
    out += ["", "## The bar before a section change (vs the three bars before it) and the downbeat after"]
    for k in kinds:
        c = A[f"into {k}"]; n = c["n"]
        if not n: continue
        out.append(f"\n**into {k}** ({n} changes)")
        for name, v in sorted(c.items(), key=lambda kv: -kv[1]):
            if name != "n" and v / n >= 0.12: out.append(f"- {name}: {v / n:.0%}")
    out += ["", "## VP fill grids in the bar before a section change (top 12)"] + [f"- `{g}` x{v}" for g, v in fills.most_common(12)]
    out += ["", "## VP grooves per section type (top 3)"]
    for k in kinds:
        g = [(p, v) for (kk, p), v in grooves.items() if kk == k]
        if g: out.append(f"- {k}: " + ", ".join(f"`{p}` x{v}" for p, v in sorted(g, key=lambda x: -x[1])[:3]))
    out += ["", "## Bass grids per section type (top 3)"]
    for k in kinds:
        if bassg[k]: out.append(f"- {k}: " + ", ".join(f"`{p}` x{v}" for p, v in bassg[k].most_common(3)))
    open(os.path.join(a.out, "summary.md"), "w").write("\n".join(out) + "\n")
    json.dump({k: dict(v) for k, v in A.items()}, open(os.path.join(a.out, "summary.json"), "w"), ensure_ascii=False, indent=1,
              default=str)
    print("\n".join(out))


if __name__ == "__main__":
    main()
