#!/usr/bin/env python3
"""Learn arranging habits from a corpus of vocal scores (MusicXML .mxl/.musicxml/.xml, or .mscz via MuseScore).

    $ACAP_PY corpus_stats.py CORPUS_DIR OUT_DIR [--csv PDMX.csv] [--limit N]

Reads every score under CORPUS_DIR with a plain XML parser (no score code is run), splits it into vocal lines
(part x staff x voice), orders them high to low and measures, per corpus group:
- ranges: each line's 5th / median / 95th percentile pitch, by its position in the stack (top ... bass);
- spacing: the vertical intervals between neighbouring lines at every 8th, and how many pitch classes sound;
- texture per bar: how many lines sing, how often they move together (homorhythm), pads (long notes),
  rhythmic comp (4+ onsets with repeated pitches), unison/octaves;
- the bass: its onset patterns on a 16th grid (4/4 bars) and its leaps;
- melody: which line sings the words while the others sing vocables, and how many bars a lead keeps the tune;
- vocables: the syllables background lines sing ("oo", "doo", "dm" ...);
- energy arc: lines singing and onsets per bar along the song (10 slices).
With --csv (the PDMX metadata), scores are grouped as "pop" (pop/rock/soul/soundtrack/jazz genres or a cappella
keywords such as Pentatonix, beatbox, barbershop) or "classical"; otherwise everything is one group.
Writes OUT_DIR/stats.json (numbers for the engine) and OUT_DIR/report.md (for people).
"""
import argparse, collections, csv, json, math, os, re, statistics, sys, zipfile
import xml.etree.ElementTree as ET

STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NOT_VOICE = re.compile(r"piano|pno|organ|guitar|gtr|keyboard|accomp|rehearsal|harp|violin|cello|flute|synth|bass guitar|"
                       r"e\.?bass|strings|drum set|drumset|trumpet|sax|clarinet", re.I)
PERC = re.compile(r"\bvp\b|beat ?box|perc|vocal perc|drum|kick|snare", re.I)
VOCABLES = set("""oo ooh oooh ah aah ahh oh ohh mm mmm hm hmm m n nn ng la da dah ba bah bm bum dm dum doo do du dun
dn doom dmm jen jeh jah ya yah wa wah wo woo wee ooo uu u a o e i mmh hmmm bow bowm dow dum dit dat dot ta tah
pa pah ma mah na nah ne doh dooh doot dl dle dee di dlee bop ba-dum shoo shoop sha shoo-bop vm vum zm ning nin ni
lu loo lo"""
                .split())
VOCABLE_RE = re.compile(r"^(b|d|j|m|n|w|y|t|p|z|sh|ch|v|g|k|l|h|dj|bw|dw)?(o+|a+|u+|e+|i+|ah+|oh+|ow|aw|ai|ay|um|un|"
                        r"m+|n+|ng|ung|oon|oom|ooh|dle|dl|ee|ing|in)h?$")
POP_GENRES = ("pop", "rock", "rbfunksoul", "soundtrack", "jazz", "hiphop", "country", "comedy", "electronic")
POP_WORDS = ("pentatonix", "beatbox", "acapella", "a cappella", "a capella", "acappella", "voiceplay", "barbershop",
             "vocal percussion")


WORDS = set("a i e me to too low no so go do' know new now how we you be he she the by my why see say day may way "
            "lay lie die tie bye high hi hey ho hoo who woe ye yo mine wine shine one".split())


def is_vocable(syl):
    s = re.sub(r"[^a-z]", "", syl.lower())
    return bool(s) and s not in WORDS and (s in VOCABLES or bool(VOCABLE_RE.match(s)))


# ----------------------------------------------------------------------------- reading
def load_xml(path):
    if path.endswith(".mxl"):
        z = zipfile.ZipFile(path)
        names = [n for n in z.namelist() if n.endswith((".xml", ".musicxml")) and not n.startswith("META-INF")]
        try:  # the container names the root file
            c = ET.fromstring(z.read("META-INF/container.xml"))
            rf = c.find(".//{*}rootfile")
            if rf is not None and rf.get("full-path") in z.namelist():
                names = [rf.get("full-path")]
        except KeyError:
            pass
        return ET.fromstring(z.read(names[0]))
    return ET.parse(path).getroot()


def strip_ns(root):
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def read_score(path):
    """-> dict(bars=[(start, length_q, beats, beat_type)], lines=[dict(name, perc, notes=[(on, dur, pitch, lyric)])])"""
    root = strip_ns(load_xml(path))
    if root.tag != "score-partwise":
        return None
    names = {}
    for sp in root.iter("score-part"):
        pn = (sp.findtext("part-name") or "").strip()
        inst = " ".join((si.findtext("instrument-name") or "") for si in sp.iter("score-instrument"))
        unp = sp.find(".//midi-unpitched") is not None or sp.findtext(".//midi-channel") == "10"
        names[sp.get("id")] = (pn or inst, inst, unp)
    bars, lines = None, []
    for part in root.iter("part"):
        pname, inst, unp = names.get(part.get("id"), ("", "", False))
        streams = collections.defaultdict(list)  # (staff, voice) -> notes
        div, beats, btype, start = 1, 4, 4, 0.0
        mybars = []
        for m in part.iter("measure"):
            pos, mx = 0.0, 0.0
            last_on = 0.0
            for el in m:
                if el.tag == "attributes":
                    d = el.findtext("divisions")
                    if d: div = float(d)
                    t = el.find("time")
                    if t is not None and t.findtext("beats"):
                        try: beats, btype = int(t.findtext("beats").split("+")[0]), int(t.findtext("beat-type"))
                        except ValueError: pass
                elif el.tag == "backup":
                    pos -= float(el.findtext("duration") or 0) / div
                elif el.tag == "forward":
                    pos += float(el.findtext("duration") or 0) / div; mx = max(mx, pos)
                elif el.tag == "note":
                    if el.find("grace") is not None or el.find("cue") is not None:
                        continue
                    dur = float(el.findtext("duration") or 0) / div
                    chord = el.find("chord") is not None
                    on = last_on if chord else pos
                    if not chord:
                        last_on = pos; pos += dur; mx = max(mx, pos)
                    key = (el.findtext("staff") or "1", el.findtext("voice") or "1")
                    if el.find("rest") is not None:
                        continue
                    p = el.find("pitch")
                    if p is not None:
                        pitch = (int(p.findtext("octave")) + 1) * 12 + STEP[p.findtext("step")] + \
                            int(round(float(p.findtext("alter") or 0)))
                    elif el.find("unpitched") is not None:
                        pitch = -1
                    else:
                        continue
                    lyr = el.find("lyric")
                    text = "".join(t.text or "" for t in lyr.findall("text")).strip() if lyr is not None else ""
                    ties = [t.get("type") for t in el.findall("tie")]
                    streams[key].append([start + on, dur, pitch, text, "stop" in ties, chord])
            length = mx if mx > 0 else beats * 4.0 / btype
            mybars.append((start, length, beats, btype))
            start += length
        if bars is None or len(mybars) > len(bars):
            bars = mybars
        perc = unp or bool(PERC.search(pname + " " + inst))
        if not perc and NOT_VOICE.search(pname) and not re.search(r"voice|vox|vocal|solo|lead|sop|alto|ten|bar|bass\b",
                                                                    pname, re.I):
            continue
        for key, notes in streams.items():
            notes.sort(key=lambda n: (n[0], -n[2]))
            merged = []
            for n in notes:
                if n[5] and merged and abs(merged[-1][0] - n[0]) < 1e-6:
                    continue  # chord inside one line: keep its top note
                if n[4] and merged and merged[-1][2] == n[2] and abs(merged[-1][0] + merged[-1][1] - n[0]) < 1e-3:
                    merged[-1][1] += n[1]; continue
                merged.append(n)
            if len(merged) >= 8:
                lines.append(dict(name=pname, perc=perc or all(n[2] < 0 for n in merged),
                                  notes=[(n[0], n[1], n[2], n[3]) for n in merged]))
    if not bars or not lines:
        return None
    return dict(bars=bars, lines=lines)


# ----------------------------------------------------------------------------- measuring
def pct(xs, q):
    xs = sorted(xs)
    if not xs: return None
    k = (len(xs) - 1) * q
    return xs[int(k)] + (xs[min(int(k) + 1, len(xs) - 1)] - xs[int(k)]) * (k - int(k))


class Acc:
    def __init__(self):
        self.n_scores = 0
        self.n_lines = collections.Counter()
        self.range = collections.defaultdict(list)      # "k/n" -> [p5, p50, p95]
        self.gaps = collections.defaultdict(collections.Counter)   # "top-2nd" ... -> interval counter
        self.pcs = collections.Counter()                 # (n sounding, n pitch classes)
        self.texture = collections.Counter()
        self.line_role = collections.Counter()           # each (background line, bar)
        self.active_frac = collections.Counter()
        self.bass_rhythm = collections.Counter()
        self.bass_leap = collections.Counter()
        self.mel_int = collections.defaultdict(collections.Counter)
        self.vocables = collections.Counter()
        self.lead_pos = collections.Counter()
        self.lead_run = []
        self.arc_active = [[] for _ in range(10)]
        self.arc_onsets = [[] for _ in range(10)]
        self.vp_scores = 0
        self.vp_rhythm = collections.Counter()
        self.bg_rhythm = collections.Counter()           # 16th grid of a background (not top, not bass) line-bar
        self.syl_len = collections.defaultdict(collections.Counter)   # 'bass short' / 'bg long' ... -> syllable
        self.bass_above = collections.Counter()          # pitch classes above the bass at each 8th (semitones)
        self.parallel = collections.Counter()


def pos_name(k, n):
    if k == 0: return "top"
    if k == n - 1: return "bass"
    return f"inner{k}"


def sounding(line, t):
    """pitch sounding at time t (bisect would be faster; lines are short)"""
    for on, dur, p, _ in line["idx"]:
        if on <= t + 1e-6 < on + dur:
            return p
        if on > t + 1e-6:
            break
    return None


def analyze(score, acc):
    voc = [l for l in score["lines"] if not l["perc"]]
    perc = [l for l in score["lines"] if l["perc"]]
    if len(voc) < 3:
        return False
    for l in voc:
        l["med"] = statistics.median(n[2] for n in l["notes"])
        l["idx"] = l["notes"]
    voc.sort(key=lambda l: -l["med"])
    n = len(voc)
    acc.n_scores += 1
    acc.n_lines[n] += 1
    for k, l in enumerate(voc):
        ps = [p for _, d, p, _ in l["notes"] for _ in range(max(1, int(d * 2)))]  # weighted by length
        acc.range[f"{pos_name(k, n)}/{n}"].append([pct(ps, .05), pct(ps, .5), pct(ps, .95)])
        prev = None
        for on, d, p, _ in l["notes"]:
            if prev is not None:
                acc.mel_int[pos_name(k, n) if pos_name(k, n) != "top" else "top"][min(abs(p - prev), 13)] += 1
            prev = p
    # vertical sonorities on an 8th grid
    end = score["bars"][-1][0] + score["bars"][-1][1]
    t, prev_v = 0.0, None
    while t < end:
        v = [sounding(l, t) for l in voc]
        if sum(x is not None for x in v) >= 3:
            s = [x for x in v if x is not None]
            acc.pcs[(len(s), len({x % 12 for x in s}))] += 1
            if v[-1] is not None:
                acc.bass_above[tuple(sorted({(x - v[-1]) % 12 for x in v[:-1] if x is not None}))] += 1
            for k in range(n - 1):
                a, b = v[k], v[k + 1]
                if a is not None and b is not None:
                    key = "bass-next" if k + 1 == n - 1 else f"{k}-{k + 1}"
                    acc.gaps[key][min(a - b, 24)] += 1
            if prev_v:  # parallel perfect intervals between moving pairs
                for i in range(n):
                    for j in range(i + 1, n):
                        a0, b0, a1, b1 = prev_v[i], prev_v[j], v[i], v[j]
                        if None in (a0, b0, a1, b1) or a0 == a1 or b0 == b1:
                            continue
                        i0, i1 = (a0 - b0) % 12, (a1 - b1) % 12
                        if i0 == i1 and i0 in (0, 7) and (a1 - a0) * (b1 - b0) > 0:
                            acc.parallel["p5" if i0 == 7 else "p8"] += 1
                        acc.parallel["moving pairs"] += 1
        prev_v = v
        t += 0.5
    # bars
    bars = score["bars"]
    nb = len(bars)
    lead_prev, run = None, 0
    for bi, (b0, blen, beats, btype) in enumerate(bars):
        b1 = b0 + blen
        per = []
        for k, l in enumerate(voc):
            ns = [x for x in l["notes"] if b0 - 1e-6 <= x[0] < b1 - 1e-6]
            sounding_any = ns or sounding(l, b0) is not None
            per.append((k, ns, sounding_any))
        active = [k for k, ns, s in per if s]
        acc.active_frac[f"{len(active)}/{n}"] += 1
        onsets_total = sum(len(ns) for _, ns, _ in per)
        sl = min(9, int(10 * bi / max(1, nb)))
        acc.arc_active[sl].append(len(active) / n)
        acc.arc_onsets[sl].append(onsets_total / max(1, len(active)) / max(blen, 1e-6) * 4)
        sets = [frozenset(round(x[0] - b0, 3) for x in ns) for _, ns, _ in per if ns]
        if len(active) <= 1:
            acc.texture["solo/1 line"] += 1
        else:
            common = collections.Counter(sets).most_common(1)[0][1] if sets else 0
            pcs = {x[2] % 12 for _, ns, _ in per for x in ns}
            if sets and len(pcs) == 1:
                acc.texture["unison/octaves"] += 1
            elif sets and common >= 0.75 * len(active):
                acc.texture["homorhythm (block chords)"] += 1
            else:
                acc.texture["independent lines"] += 1
            for k, ns, _ in per:
                if not ns or k == 0: continue
                if all(x[1] >= blen / 2 - 1e-6 for x in ns):
                    acc.line_role["pad (half-bar+ notes)"] += 1
                elif len(ns) >= 4 and len({x[2] for x in ns}) <= 2:
                    acc.line_role["rhythmic comp (4+ onsets, 1-2 pitches)"] += 1
                else:
                    acc.line_role["moving line"] += 1
        # bass rhythm (4/4 only)
        if (beats, btype) == (4, 4) and abs(blen - 4) < 1e-6:
            ns = per[-1][1]
            if ns:
                grid = ["."] * 16
                for x in ns:
                    g = int(round((x[0] - b0) * 4))
                    if 0 <= g < 16: grid[g] = "X"
                acc.bass_rhythm["".join(grid)] += 1
            for l in perc:
                ns = [x for x in l["notes"] if b0 - 1e-6 <= x[0] < b1 - 1e-6]
                if ns:
                    grid = ["."] * 16
                    for x in ns:
                        g = int(round((x[0] - b0) * 4))
                        if 0 <= g < 16: grid[g] = "X"
                    acc.vp_rhythm["".join(grid)] += 1
        # who sings the words
        words = []
        for k, ns, _ in per:
            syl = [x[3] for x in ns if x[3]]
            if not syl: continue
            vc = sum(is_vocable(s) for s in syl)
            if vc < len(syl) / 2:
                words.append(k)
            else:
                for s in syl:
                    if is_vocable(s): acc.vocables[re.sub(r"[^a-z]", "", s.lower())] += 1
                who = "bass" if k == n - 1 else "bg"
                for x in ns:
                    if x[3] and is_vocable(x[3]):
                        ln = "short" if x[1] <= 0.5 else ("mid" if x[1] < 2 else "long")
                        acc.syl_len[f"{who} {ln}"][re.sub(r"[^a-z]", "", x[3].lower())] += 1
                if 0 < k < n - 1 and (beats, btype) == (4, 4) and abs(blen - 4) < 1e-6 and len(ns) >= 2:
                    grid = ["."] * 16
                    for x in ns:
                        g = int(round((x[0] - b0) * 4))
                        if 0 <= g < 16: grid[g] = "X"
                    acc.bg_rhythm["".join(grid)] += 1
        lead = None
        if len(words) == 1 and len(active) >= 2:
            lead = words[0]
            acc.lead_pos[pos_name(lead, n)] += 1
        elif len(words) >= 2:
            acc.lead_pos["several lines sing the words"] += 1
        elif not words and len(active) >= 2:
            acc.lead_pos["no words (vocables only / no lyrics)"] += 1
        if lead is None:            # a bar with no single lead (rest, tutti words, vocables) keeps the run going
            continue
        if lead == lead_prev:
            run += 1
        else:
            if lead_prev is not None and run: acc.lead_run.append(run)
            run = 1
        lead_prev = lead
    if lead_prev is not None and run: acc.lead_run.append(run)
    bn = voc[-1]["notes"]
    for a, b in zip(bn, bn[1:]):
        acc.bass_leap[min(abs(b[2] - a[2]), 13)] += 1
    if perc:
        acc.vp_scores += 1
    return True


# ----------------------------------------------------------------------------- reporting
def name(p):
    return ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"][int(round(p)) % 12] + str(int(round(p)) // 12 - 1)


def summarise(acc):
    def dist(counter, top=None, keyfmt=str):
        tot = sum(counter.values()) or 1
        items = counter.most_common(top) if top else sorted(counter.items())
        return {keyfmt(k): round(v / tot, 4) for k, v in items}
    rng = {}
    for k, v in acc.range.items():
        if len(v) >= 5:
            rng[k] = dict(n=len(v), low=round(statistics.median(x[0] for x in v), 1),
                          median=round(statistics.median(x[1] for x in v), 1),
                          high=round(statistics.median(x[2] for x in v), 1))
    runs = acc.lead_run
    return dict(
        n_scores=acc.n_scores, lines_per_score=dict(sorted(acc.n_lines.items())),
        ranges=rng,
        spacing={k: dist(c) for k, c in acc.gaps.items()},
        pitch_classes={f"{a} lines/{b} pcs": v for (a, b), v in sorted(acc.pcs.items())},
        texture=dist(acc.texture), line_role=dist(acc.line_role), lines_active=dist(acc.active_frac, 15),
        bass_rhythm_4_4=dist(acc.bass_rhythm, 25), bass_leaps=dist(acc.bass_leap),
        melodic_intervals={k: dist(c) for k, c in acc.mel_int.items()},
        parallels=dict(acc.parallel),
        vocables=dist(acc.vocables, 40), lead=dist(acc.lead_pos),
        lead_run_bars=dict(median=statistics.median(runs) if runs else None,
                           p25=pct(runs, .25), p75=pct(runs, .75), n=len(runs)),
        energy_arc=dict(lines_active=[round(statistics.mean(x), 3) if x else None for x in acc.arc_active],
                        onsets_per_4beats_per_line=[round(statistics.mean(x), 2) if x else None for x in acc.arc_onsets]),
        vp_scores=acc.vp_scores, vp_rhythm_4_4=dist(acc.vp_rhythm, 20),
        bg_rhythm_4_4=dist(acc.bg_rhythm, 40),
        syllables_by_length={k: dist(c, 12) for k, c in sorted(acc.syl_len.items())},
        voicing_above_bass=dist(acc.bass_above, 30, keyfmt=lambda t: " ".join(map(str, t))))


def md_group(g, s):
    out = [f"## {g}: {s['n_scores']} scores", "", f"Lines per score: {s['lines_per_score']}", "",
           "### Ranges (median over scores of each line's 5% / 50% / 95% pitch)", "| line / lines | scores | low | median | high |",
           "|---|---|---|---|---|"]
    order = lambda w: 0 if w == "top" else 99 if w == "bass" else int(w[5:])
    for k in sorted(s["ranges"], key=lambda k: (int(k.split("/")[1]), order(k.split("/")[0]))):
        r = s["ranges"][k]
        out.append(f"| {k} | {r['n']} | {name(r['low'])} | {name(r['median'])} | {name(r['high'])} |")
    out += ["", "### Spacing between neighbouring lines (semitones, share of 8ths)"]
    for k in sorted(s["spacing"]):
        d = s["spacing"][k]; top = sorted(d.items(), key=lambda kv: -kv[1])[:6]
        within8 = sum(v for i, v in d.items() if 0 <= int(i) <= 12)
        out.append(f"- **{k}**: most common {', '.join(f'{i} ({v:.0%})' for i, v in top)}; within an octave {within8:.0%}")
    out += ["", "### Texture per bar"] + [f"- {k}: {v:.1%}" for k, v in s["texture"].items()]
    out += ["", "### What the lines under the top line do (per line and bar)"] + \
        [f"- {k}: {v:.1%}" for k, v in s["line_role"].items()]
    out += ["", "### Who sings the words"] + [f"- {k}: {v:.1%}" for k, v in sorted(s["lead"].items(), key=lambda kv: -kv[1])]
    lr = s["lead_run_bars"]
    out += [f"- a lead keeps the tune for a median of {lr['median']} lead bars before another line takes it (quartiles {lr['p25']}-{lr['p75']}, {lr['n']} runs)"]
    out += ["", "### Bass onsets in 4/4 bars (16th grid, top 12)"] + \
        [f"- `{k}` {v:.1%}" for k, v in list(s["bass_rhythm_4_4"].items())[:12]]
    leaps = s["bass_leaps"]
    out += [f"- bass motion: repeat {leaps.get('0', 0):.0%}, step (1-2) {leaps.get('1', 0) + leaps.get('2', 0):.0%}, "
            f"4th/5th {leaps.get('5', 0) + leaps.get('7', 0):.0%}, octave {leaps.get('12', 0):.0%}"]
    out += ["", "### Background vocables (top 25)", ", ".join(f"{k} {v:.0%}" for k, v in list(s["vocables"].items())[:25])]
    out += ["", "### Syllables by note length (short <= 8th, mid < half note, long)"] + \
        [f"- {k}: " + ", ".join(f"{a} {b:.0%}" for a, b in list(d.items())[:8]) for k, d in s.get("syllables_by_length", {}).items()]
    out += ["", "### Background line rhythms in 4/4 bars (16th grid, top 15)"] + \
        [f"- `{k}` {v:.1%}" for k, v in list(s.get("bg_rhythm_4_4", {}).items())[:15]]
    out += ["", "### Chord shapes: pitch classes sung above the bass (semitones over the bass, top 12)"] + \
        [f"- `{k}` {v:.1%}" for k, v in list(s.get("voicing_above_bass", {}).items())[:12]]
    p = s["parallels"]
    if p.get("moving pairs"):
        out += ["", f"### Parallel 5ths/8ves: {p.get('p5', 0) / p['moving pairs']:.2%} / {p.get('p8', 0) / p['moving pairs']:.2%} of moving pairs"]
    ea = s["energy_arc"]
    out += ["", "### Energy along the song (10 slices)", "| slice | " + " | ".join(str(i + 1) for i in range(10)) + " |",
            "|---|" + "---|" * 10, "| share of lines singing | " + " | ".join(f"{x:.0%}" if x is not None else "" for x in ea["lines_active"]) + " |",
            "| onsets per bar per line | " + " | ".join(f"{x:.1f}" if x is not None else "" for x in ea["onsets_per_4beats_per_line"]) + " |"]
    if s["vp_scores"]:
        out += ["", f"### Vocal percussion: {s['vp_scores']} scores with a percussion line"] + \
            [f"- `{k}` {v:.1%}" for k, v in list(s["vp_rhythm_4_4"].items())[:10]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus"); ap.add_argument("out")
    ap.add_argument("--csv", help="PDMX.csv: group scores into pop / classical")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    groups = {}
    if a.csv:
        csv.field_size_limit(10 ** 8)
        for r in csv.DictReader(open(a.csv, newline="", encoding="utf8")):
            text = " ".join(r[k] for k in ("title", "tags", "subtitle", "groups")).lower()
            pop = any(g in r["genres"] for g in POP_GENRES) or any(w in text for w in POP_WORDS)
            groups[os.path.basename(r["mxl"])] = ("pop" if pop else "classical", r["title"])
    files = sorted(os.path.join(d, f) for d, _, fs in os.walk(a.corpus) for f in fs
                   if f.endswith((".mxl", ".musicxml", ".xml")))
    if a.limit: files = files[:a.limit]
    accs = collections.defaultdict(Acc)
    per_score, bad = [], 0
    for i, f in enumerate(files):
        g, title = groups.get(os.path.basename(f), ("all", os.path.basename(f)))
        try:
            sc = read_score(f)
            if sc and analyze(sc, accs[g]):
                analyze(sc, accs["(all)"]) if a.csv else None
                per_score.append(dict(file=f, group=g, title=title, lines=len([l for l in sc["lines"] if not l["perc"]]),
                                      perc=any(l["perc"] for l in sc["lines"]), bars=len(sc["bars"])))
            else:
                bad += 1
        except Exception as e:
            bad += 1
        if (i + 1) % 500 == 0:
            print(f"{i + 1}/{len(files)}", file=sys.stderr)
    os.makedirs(a.out, exist_ok=True)
    stats = {g: summarise(acc) for g, acc in accs.items()}
    json.dump(dict(groups=stats, scores=per_score, unreadable=bad), open(os.path.join(a.out, "stats.json"), "w"),
              ensure_ascii=False, indent=1)
    md = [f"# Corpus statistics: {len(per_score)} scores read, {bad} skipped (unreadable or fewer than 3 vocal lines)", ""]
    for g in sorted(stats, key=lambda g: (g == "(all)", g)):
        md.append(md_group(g, stats[g]))
    open(os.path.join(a.out, "report.md"), "w").write("\n".join(md))
    print(f"read {len(per_score)} scores, skipped {bad} -> {a.out}/stats.json, report.md")


if __name__ == "__main__":
    main()
