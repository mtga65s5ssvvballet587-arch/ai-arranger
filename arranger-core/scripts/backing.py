"""Backing-only arrangements (no solo line): the group's backgrounds, bass and VP for a song whose melody (and its
harmony) the singers write themselves. Built on the analysis drafts (W/draft.py), so the chords, the bass line and
the drums come from the record, section by section:

    from engine import *
    import backing as BK
    BK.load(W, seed=3)                                    # draft chords / bass / instrument top line + corpus stats
    BK.lineup(top="T1", mid="A", low="Br")                # optional: rename / re-range the three background voices
    BK.part("Intro", 1, 4, energy=0.1, key="Bb")          # recording bars 1-4
    BK.part("Verse 1", 25, 40, energy=0.3, key="F")
    BK.part("Riff", 5, 24, energy=0.5, hook=True)         # the instrument hook on the top voice
    ...
    BK.ending()                                           # fermata + crash on the last bar

What each part gets (energy 0 quiet .. 1 full):
- bass: the recorded bass line (draft BASS, octave-fitted to the bass range); the chord roots where the draft is empty;
- VP: the recorded kick / snare (vp() copies W/drumgrid.json), hats by energy, rim in quiet parts; nothing where the
  record has no drums;
- backgrounds (the trio), per 2-bar phrase, a role drawn from the corpus statistics (corpus_style.py):
  pad (long vowels) / comp (short syllables on a rhythm pattern) / hook (the instrument's top line, top voice) —
  low energy favours pads, high energy comp; `hook=True` puts the record's instrument line on the top voice.
  Backgrounds stay out of the solo's way: no words, and below energy 0.4 only pads.
"""
import os, re, runpy
import engine as E
import corpus_style as CS

W = None
D = {}
TRIO = ["T1", "A", "Br"]
VP_ON = True          # False: no vocal-percussion part (the singers write their own)
SYL_LONG = None


def load(work, seed=0, group="pop"):
    global W, D
    W = work
    D = runpy.run_path(os.path.join(work, "draft.py"))
    CS.load(group, seed=seed)
    return D


CHART = None


def chords(a, b):
    """Chord rows for recording bars a..b: W/chart_chords.json (a chord chart lined up by chart_align.py) when it
    exists, else the draft's chord guesses."""
    global CHART
    if CHART is None:
        import json
        p = os.path.join(W, "chart_chords.json")
        CHART = {int(k): v for k, v in json.load(open(p)).items()} if os.path.exists(p) else {}
    out = []
    prev = ["C"]
    for n in range(a, b + 1):
        row = list(CHART.get(n) or D.get("CHORDS", {}).get(n) or prev)
        if len(row) == 2 and row[0] == row[1]: row = row[:1]
        out.append(row); prev = row
    return out


def _fit_bars(bars, rng):
    ps = [e["midi"] for b in bars for e in b if e["midi"] is not None]
    if not ps: return bars
    lo, hi = rng; k = 0
    while min(ps) + k < lo: k += 12
    while max(ps) + k > hi and min(ps) + k - 12 >= lo: k -= 12
    return E.shift(bars, k) if k else bars


def fold(bars, rng, start=None):
    """Each note moved by octaves into rng, as close as possible to the previous note (a jumpy synth or bass line
    becomes a singable one with the same pitch classes)."""
    lo, hi = rng; prev = start if start is not None else (lo + hi) // 2
    out = []
    for b in bars:
        nb = []
        for e in b:
            e = dict(e)
            if e["midi"] is not None:
                c = [p for p in range(lo, hi + 1) if p % 12 == e["midi"] % 12]
                if c:
                    e["midi"] = min(c, key=lambda p: abs(p - prev)); prev = e["midi"]
            nb.append(e)
        out.append(nb)
    for i, b in enumerate(out):          # ties survive only between equal pitches
        for j, e in enumerate(b):
            nxt = b[j + 1] if j + 1 < len(b) else (out[i + 1][0] if i + 1 < len(out) and out[i + 1] else None)
            if e.get("tie_out") and (nxt is None or nxt["midi"] != e["midi"]): e["tie_out"] = False
            if nxt is not None and nxt.get("tie_in") and nxt["midi"] != e["midi"]: nxt["tie_in"] = False
    return out


def _clean_tokens(tok):
    """draft tokens -> engine tokens summing to one bar (16ths); bad bars become a rest."""
    if not tok: return f"r:{E.BAR}"
    try:
        E.parse_line([tok]); return tok
    except Exception:
        return f"r:{E.BAR}"


def bass_bars(sec, a, b, rng):
    """Recorded bass line for bars a..b; bars without a draft get the chord roots on half notes."""
    toks = [_clean_tokens(D.get("BASS", {}).get(n)) for n in range(a, b + 1)]
    bars = E.parse_line(toks)
    # fill empty bars (the draft is empty where the bass is silent or unclear) with roots
    roots, _ = E.bass_pat(sec, [(1, 0, 8), (2, 8, 8)], rng, E.LAST.get("B", 40))
    out = []
    for bi, bar in enumerate(bars):
        if all(e["midi"] is None for e in bar) and D.get("BASS", {}).get(a + bi) is None:
            out.append(roots[bi])
        else:
            out.append(bar)
    out = fold(_fit_bars(out, rng), rng, E.LAST.get("B"))
    if CHART:          # keep the recorded rhythm, sing the chart chord's bass note
        prev = E.LAST.get("B", sum(rng) // 2)
        for bi, bar in enumerate(out):
            for e in bar:
                if e["midi"] is None: continue
                if e["tie_in"]: e["midi"] = prev; continue
                c = E.chord_for(sec, bi, e)
                if e["midi"] % 12 != c["bass"]:
                    cand = [p for p in range(rng[0], rng[1] + 1) if p % 12 == c["bass"]]
                    e["midi"] = min(cand, key=lambda p: abs(p - prev) + (2 if p > rng[1] - 4 else 0))
                prev = e["midi"]
        for bar in out:            # drop ties that no longer join equal pitches
            for j in range(len(bar) - 1):
                if bar[j].get("tie_out") and bar[j + 1]["midi"] != bar[j]["midi"]:
                    bar[j]["tie_out"] = False; bar[j + 1]["tie_in"] = False
    BSYL = {}                      # one bass syllable per note length inside a section
    for bar in out:
        for e in bar:
            if e["midi"] is not None and not e["tie_in"]:
                e["lyr"] = BSYL.setdefault("s" if e["dur"] <= 2 else "m" if e["dur"] < 8 else "l",
                                           CS.syllable(who="bass", dur=e["dur"])) if CS.S.get("syllables_by_length") else \
                    ("doom" if e["dur"] >= 4 else "dm")
    return out


def hook_bars(a, b, rng):
    toks = [_clean_tokens(D.get("OTHER_TOP", {}).get(n)) for n in range(a, b + 1)]
    bars = fold(E.parse_line(toks), (rng[0] + 5, rng[1] - 3), E.LAST.get(TRIO[0]))   # middle of the range
    return E.relyric(bars, E.flute)


# ------------------------------------------------------------------------------------------------ record voicing
# The idea of Lam, Lo & Chau, "Automated Pop-to-A Cappella Score Generation" (AIMC 2025): transcribe the record's
# accompaniment to a keyboard-like score first, then give its notes to the voices. Here step 1 is NNLS multi-pitch on
# the accompaniment stem per 8th (acap.nnls_pitches), step 2 is rule-based voice leading instead of their model.
GRID = None
GRID_FILE = None     # a grid made elsewhere (e.g. a piano cover lined up with the record): {bar: [[pitches, onset] x 8]}


def record_grid(stem_name="other", lo=48, hi=84, thr=0.3, div=8):
    """{bar: [(pitches high-first, onset strength) per 8th]} from the accompaniment stem, cached in W."""
    global GRID
    import json, numpy as np
    path = GRID_FILE or os.path.join(W, f"grid_{stem_name}.json")
    if GRID is None and os.path.exists(path):
        GRID = {int(k): v for k, v in json.load(open(path)).items()}
    if GRID is not None: return GRID
    import librosa
    from acap import Bars, cqt, harmonic_dict, nnls_pitches, tuning, stem
    B = Bars(W); SR, HOP = 22050, 256
    y = librosa.load(stem(W, stem_name), sr=SR)[0]
    C = cqt(y, SR, HOP, 36, 72, tuning(W)); cands = list(range(lo, hi + 1)); Dm = harmonic_dict(cands, 36, C.shape[0])
    fl = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    fl = fl / (np.percentile(fl, 99) + 1e-9); g = C.max()
    GRID = {}
    for n in B.numbers:
        row = []
        for k in range(div):
            t0, t1 = B.t(n, k * B.L / div), B.t(n, (k + 1) * B.L / div)
            f0, f1 = int(t0 * SR / HOP) + 1, max(int(t1 * SR / HOP), int(t0 * SR / HOP) + 2)
            x = np.median(C[:, f0:f1], 1)
            ps = nnls_pitches(Dm, cands, x, thr)[::-1] if x.max() > 0.03 * g else []
            row.append([ps, float(fl[max(0, f0 - 2):f0 + 2].max()) if f0 < len(fl) else 0.0])
        GRID[n] = row
    json.dump(GRID, open(path, "w"))
    return GRID


def _voice_slot(pcs, voices, ranges, prev):
    """Place up to len(voices) pitch classes (most important first) on the voices, high to low, close to prev."""
    import itertools
    pcs = list(dict.fromkeys(pcs))
    sets = []
    for drop in range(0, max(1, len(pcs) - 1)):            # try the most important pcs first, then drop rubbing ones
        for sub in itertools.combinations(pcs[:len(voices) + drop], min(len(voices), len(pcs))):
            sets.append(list(sub))
        if sets: break
    cands = []
    for sub in sets:
        sub = list(sub)
        while len(sub) < len(voices): sub.append(sub[len(sub) % max(1, len(sub))] if sub else 0)
        cands += list(set(itertools.permutations(sub)))
    # also: the first two pcs doubled (avoids a root/7th semitone pair in 3 voices)
    if len(pcs) >= 2 and len(voices) == 3:
        cands += list(set(itertools.permutations([pcs[0], pcs[1], pcs[0]])))
    best = None
    for perm in set(cands):
        opts = []
        for v, pc in zip(voices, perm):
            lo, hi = ranges[v]; ref = prev.get(v, (lo + hi) // 2)
            opts.append(sorted([p for p in range(lo, hi + 1) if p % 12 == pc], key=lambda q: abs(q - ref))[:2])
        for combo in itertools.product(*opts):
            if any(combo[i] < combo[i + 1] for i in range(len(combo) - 1)): continue      # no crossing
            cost = sum(abs(p - prev.get(v, p)) for p, v in zip(combo, voices))
            cost += sum(4 for p, v in zip(combo, voices) if p > ranges[v][1] - 3)      # tessitura: not at the top
            cost += sum(25 for i in range(len(combo)) for j in range(i + 1, len(combo)) if (combo[i] - combo[j]) % 12 in (1, 11))
            cost += sum(3 for i in range(len(combo) - 1) if combo[i] == combo[i + 1])
            if best is None or cost < best[0]: best = (cost, combo)
    return dict(zip(voices, best[1])) if best else None


def record_bars(sec, a, b, voices, ranges, energy):
    """Voices that sing the record's accompaniment: per 8th the sounding pitch classes (chord tones of the section
    chord first), voiced smoothly; a new attack where the record attacks or the harmony changes, else held."""
    import collections
    G = record_grid(); prev = {v: E.LAST.get(v, sum(ranges[v]) // 2) for v in voices}
    out = {v: [] for v in voices}; cur = None
    span = 4 if energy < .35 else 2 if energy < .6 else 1        # 8ths per harmonic step: quiet parts move less
    for bi, n in enumerate(range(a, b + 1)):
        bars = {v: [] for v in voices}
        row = G.get(n, [[[], 0]] * 8)
        for k, (ps, onset) in enumerate(row):
            g0 = k - k % span
            if k % span:                                              # inside a step: hold
                for v in voices: bars[v][-1]["dur"] += 2
                continue
            cnt = collections.Counter(p % 12 for q, _ in row[g0:g0 + span] for p in q)
            ps = [pc for pc, _ in cnt.most_common()]
            onset = max(o for _, o in row[g0:g0 + span])
            c = E.chord_at(sec, bi, k * 2)
            pcs = [p % 12 for p in ps]
            order = [x for x in pcs if x in c["tones"]]
            if CHART:      # a chord chart is the truth: only its chord tones, 3rd and 7th first
                ess = [x for x in (c["third"], c["sev"]) if x is not None]
                order = list(dict.fromkeys(ess + order + [(c["root"] + 7) % 12, c["root"]]))
                order = [x for x in order if x in c["tones"]]
            else:
                order += [x for x in pcs if x not in c["tones"]]
            if len(set(order)) < 2:                                   # little or nothing played: the chord
                order = order + [c["third"], (c["root"] + 7) % 12, c["root"]] + ([c["sev"]] if c["sev"] is not None else [])
            order = [x for x in order if x is not None]
            V = _voice_slot(order, voices, ranges, prev) or prev
            attack = cur is None or any(V[v] != cur[v] for v in voices) or (onset > 0.5 and energy >= .5)
            for v in voices:
                if attack or not bars[v]:
                    bars[v].append(E.ev(k * 2, 2, V[v], "", tie_in=(not attack and k == 0 and cur is not None)))
                else:
                    bars[v][-1]["dur"] += 2
            cur = V; prev = dict(V)
        for v in voices: out[v].append(bars[v])
    for v in voices:                                                   # ties across bars + syllables
        for i in range(1, len(out[v])):
            f = out[v][i][0]
            if f.get("tie_in"): out[v][i - 1][-1]["tie_out"] = True
        long_syl, short_syl = CS.syllable(long=True), CS.syllable()
        for bar in out[v]:
            for e in bar:
                if not e["tie_in"]: e["lyr"] = long_syl if e["dur"] >= 6 else short_syl
    return out


# ------------------------------------------------------------------------------------------------ the record's rhythm
ENV = None


def accent_pattern(a, b, stem_name="other", hi=0.8, lo=0.3):
    """Where the record's accompaniment accents fall in bars a..b: the mean z-score of its attack strength per 16th
    -> 16-char string ('X' strong, 'x' accent, '.' none). Robust when the instruments play on every 16th."""
    global ENV
    import numpy as np, librosa
    from acap import Bars, stem
    B = Bars(W); SR, H = 22050, 128
    if ENV is None:
        y, _ = librosa.load(stem(W, stem_name), sr=SR)
        C = np.abs(librosa.cqt(y, sr=SR, hop_length=H, fmin=librosa.note_to_hz("C3"), n_bins=60))
        e = librosa.onset.onset_strength(S=librosa.amplitude_to_db(C), sr=SR, hop_length=H, lag=2)
        ENV = (e, np.arange(len(e)) * H / SR)
    e, t = ENV; M = []
    for n in range(a, b + 1):
        row = np.array([e[(t >= B.t(n, k - 0.3)) & (t < B.t(n, k + 0.3))].max(initial=0) for k in range(16)])
        M.append((row - row.mean()) / (row.std() + 1e-9))
    p = np.mean(M, 0)
    return "".join("X" if v > hi else ("x" if v > lo else ".") for v in p)


def rhythm_bars(sec, a, b, voices, ranges, pattern, push=True):
    """Background chords on the record's rhythm: an attack on each 'X'/'x' of `pattern`, held to the next attack
    (short attacks staccato 'dn', long ones 'dah'); an attack on the bar's last 8th takes the next bar's chord
    (the push). Pitch classes: chart chord tones, the record's/cover's sounding notes first."""
    G = record_grid(); prev = {v: E.LAST.get(v, sum(ranges[v]) // 2) for v in voices}
    SYLS = {}                                  # one syllable per note length inside a section
    hits = [k for k, c in enumerate(pattern) if c in "Xx"] or [0]
    out = {v: [] for v in voices}
    for bi, n in enumerate(range(a, b + 1)):
        bars = {v: [] for v in voices}; t = 0
        for j, st in enumerate(hits):
            en = hits[j + 1] if j + 1 < len(hits) else E.BAR
            if st > t:
                for v in voices: bars[v].append(E.ev(t, st - t))
            nxt = push and st >= E.BAR - 2 and bi + 1 < sec["nbars"]
            c = E.chord_at(sec, bi + 1, 0) if nxt else E.chord_at(sec, bi, st)
            ps = [p % 12 for p in (G.get(n + (1 if nxt else 0)) or G.get(n, [[[], 0]] * 8))[min(7, (0 if nxt else st) // 2)][0]]
            ess = [x for x in (c["third"], c["sev"]) if x is not None]
            order = [x for x in dict.fromkeys(ess + [x for x in ps if x in c["tones"]] + [(c["root"] + 7) % 12, c["root"]])
                     if x in c["tones"]]
            V = _voice_slot(order, voices, ranges, prev) or prev
            d = en - st
            syl = SYLS.setdefault(min(d, 8), CS.syllable(dur=d)) if CS.S.get("syllables_by_length") else \
                ("dn" if d <= 2 else ("dah" if d <= 4 else "Ah"))
            for v in voices:
                bars[v].append(E.ev(st, d, V[v], syl, art="staccato" if d <= 2 else None))
            prev = dict(V); t = en
        for v in voices: out[v].append(bars[v])
    return out


def part(name, a, b, energy=0.5, key="C", hook=False, vp=True, bass=True, tempo=None, phrase=2, crash=None,
         record=True, rhythm=None):
    """One section of the record (recording bars a..b) with backing only."""
    rows = chords(a, b)
    s = E.section(name, key, a, rows, tempo=tempo)
    rng = {v: E.VOICE_INFO[v][3] for v in TRIO + ["B"]}
    RT = E.R(**rng)
    dyn = "pp" if energy < .2 else "p" if energy < .4 else "mp" if energy < .6 else "mf" if energy < .8 else "f"
    if bass:
        E.put(s, "B", bass_bars(s, a, b, rng["B"]), text="bass (record's line)" if a == 1 or energy >= .3 else None,
              dyn=dyn)
    if vp and VP_ON:
        hats = None if energy < .3 else ("8" if energy < .75 else "16")
        E.vp(s, hats=hats, rim=energy < .45, crash=crash if crash is not None else ((0,) if energy >= .7 else ()))
    hk = hook_bars(a, b, rng[TRIO[0]]) if hook else None
    first = True
    if rhythm == "record":
        rhythm = accent_pattern(a, b)
    elif rhythm == "style":                    # a rhythm the loaded style itself writes for backgrounds
        rhythm = CS.bg_pattern(energy)
    if rhythm:
        rec = rhythm_bars(s, a, b, TRIO[1:] if hook else TRIO, RT, rhythm)
        s["text"][(TRIO[1] if hook else TRIO[0], 0)] = f"record's rhythm {rhythm[:4]} {rhythm[4:8]} {rhythm[8:12]} {rhythm[12:]}"
        record = True
    else:
        rec = record_bars(s, a, b, TRIO[1:] if hook else TRIO, RT, energy) if record else None
    for ph in CS.phrases(s, phrase):
        voices = TRIO[1:] if hook else TRIO
        if hook:
            E.put(s, TRIO[0], hk, local=ph, text="hook (synth line, 'doo-dl')" if first else None,
                  dyn=dyn if first else None)
        if record:
            for v in voices:
                E.put(s, v, rec[v], local=ph, text=None if (rhythm or not first) else "the record's keys/synth",
                      dyn=dyn if first else None)
            first = False
            continue
        if energy < .4:
            role = "pad"
        else:
            w = CS.role_weights(energy); w.pop("moving", None)
            role = CS._pick(w)
        if role == "pad":
            syl = CS.syllable(long=True)
            E.put_pad(s, voices, syl, RT, local=ph, text=f"pad '{syl}'", dyn=dyn if first else None)
        else:
            opts = [p for e0, ps in CS.COMP_BY_ENERGY if energy >= e0 for p in ps][-4:]
            pat = CS.RNG.choice(opts); syl = CS.syllable()
            E.put_comp(s, voices, pat, syl, RT, local=ph, text=f"'{syl}' ({pat})", dyn=dyn if first else None)
        first = False
    return s


def ending(sec=None):
    sec = sec or E.SECS[-1]
    E.fermata_last(sec)
    if not VP_ON: return
    sec["parts"].setdefault("VP", [None] * sec["nbars"])[-1] = E.vp_bar({0: "B/Ksh"})


# ------------------------------------------------------------------------------------------------ word harmony (字ハモ)
def word_harmony(sec, kind, lead="L", voices=None, prob=None, phrase=2):
    """Background voices sing the lead's words in the lead's rhythm, in block harmony under it, on some phrases of the
    section. How often comes from the loaded style's structure table (the owner's late scores: A 34%, B 52%, chorus
    45%, last chorus 64% of bars) unless `prob` is given; phrases where the lead rests are left alone. `kind`:
    intro / A / B / chorus / last chorus / bridge / interlude / outro."""
    voices = voices or TRIO
    if prob is None:
        prob = CS.S.get("structure", {}).get(kind, {}).get("word_harmony", 0.0)
    mel = [b if b else E.rest_bar() for b in sec["parts"].get(lead, [None] * sec["nbars"])]
    stack = E.block(mel, sec, len(voices))            # [lead, v1, v2, v3] close position under the lead
    done = []
    ok = [ph for ph in CS.phrases(sec, phrase)
          if sum(1 for i in ph for e in mel[i] if e["midi"] is not None and e["lyr"]) >= 2]
    chosen = CS.RNG.sample(ok, min(len(ok), round(prob * len(ok))))      # a fixed share, not a coin per phrase
    for ph in sorted(chosen):
        ph = [i for i in ph if any(e["midi"] is not None for e in mel[i])]     # bars where the lead rests keep their backing
        if not ph: continue
        for v, bars in zip(voices, stack[1:]):
            lo, hi = E.VOICE_INFO[v][3]
            ps = [e["midi"] for i in ph for e in bars[i] if e["midi"] is not None]
            k = 0
            while ps and max(ps) + k > hi: k -= 12
            while ps and min(ps) + k < lo: k += 12
            out = [[dict(e, midi=None if e["midi"] is None else E.fit(e["midi"] + k, (lo, hi))) for e in b] for b in bars]
            E.put(sec, v, out, local=ph, text="words (字ハモ)" if not done else None)
        done.append(ph)
    return done


# ------------------------------------------------------------------------------------------------ moves from the owner's late scores
def thin_verse(sec, voices=None, share=0.5):
    """A verse that starts thin: the backgrounds rest for the first `share` of the section (lead + bass only), as in
    the owner's 花占い / シル・ヴ・プレジデント first verses (31% of background bars rest in A sections)."""
    voices = voices or TRIO
    n = int(round(sec["nbars"] * share))
    for v in voices:
        P = sec["parts"].setdefault(v, [None] * sec["nbars"])
        for i in range(n): P[i] = E.rest_bar()
        for key in [k for k in list(sec["text"]) + list(sec["dyn"]) if k[0] == v and k[1] < n]:
            sec["text"].pop(key, None); sec["dyn"].pop(key, None)
    return list(range(n))


def phrase_end_words(sec, lead="L", voices=None, every=4, skip=()):
    """Word harmony only on the last two bars of each `every`-bar phrase (where the owner's verses put it)."""
    voices = voices or TRIO
    mel = [b if b else E.rest_bar() for b in sec["parts"].get(lead, [None] * sec["nbars"])]
    stack = E.block(mel, sec, len(voices)); done = []
    for s in range(every - 2, sec["nbars"] - 1, every):
        ph = [s, s + 1]
        if any(i in skip for i in ph): continue
        if sum(1 for i in ph for e in mel[i] if e["midi"] is not None and e["lyr"]) < 2: continue
        for v, bars in zip(voices, stack[1:]):
            lo, hi = E.VOICE_INFO[v][3]
            out = [[dict(e, midi=None if e["midi"] is None else E.fit(e["midi"], (lo, hi))) for e in b] for b in bars]
            E.put(sec, v, out, local=ph, text="words (字ハモ)" if not done else None)
        done.append(ph)
    return done


def bass_push(sec, voice="B"):
    """The bass comes in an 8th early: where a bar starts with a new bass note, that note is attacked on the last 8th
    of the bar before and tied over the bar line (the push that runs through the owner's 花占い choruses)."""
    P = sec["parts"].get(voice); n = 0
    if not P: return 0
    for i in range(1, sec["nbars"]):
        cur, prev = P[i], P[i - 1]
        if not cur or not prev: continue
        first, last = cur[0], prev[-1]
        if first["midi"] is None or first["tie_in"] or first["start"] != 0: continue
        if last["start"] + last["dur"] != E.BAR or last["dur"] < 2: continue
        if last["midi"] == first["midi"]: continue                      # same note: nothing to push
        if last["dur"] == 2:
            if last["midi"] is not None: continue                       # a short note there already: leave it
            prev.pop()                                                  # an 8th rest: the push takes its place
        else:
            last["dur"] -= 2; last["tie_out"] = False
        prev.append(E.ev(E.BAR - 2, 2, first["midi"], first["lyr"], tie_out=True))
        first["tie_in"] = True; first["lyr"] = ""; n += 1
    return n


def kime(sec, pattern="X...X...X...X...", bar=-1, voices=None, bass="B"):
    """A hit: backgrounds and bass in one rhythm on one bar (default the section's last bar, quarter notes), the way
    the owner's choruses end before the next section."""
    voices = voices or TRIO
    bi = bar % sec["nbars"]; a = sec["first"]; b = a + sec["nbars"] - 1
    rng = {v: E.VOICE_INFO[v][3] for v in voices + [bass]}
    rb = rhythm_bars(sec, a, b, voices, E.R(**rng), pattern, push=False)
    for v in voices:
        for e in rb[v][bi]:
            if e["midi"] is not None: e["lyr"] = "pa"; e["art"] = "staccato" if e["dur"] <= 4 else None
        E.put(sec, v, rb[v], local=[bi], text="キメ" if v == voices[0] else None)
    pat = CS._grid_to_pattern(pattern, len(sec["chords"][bi]))
    bb, _ = E.bass_pat(sec, pat, rng[bass], E.LAST.get(bass, sum(rng[bass]) // 2), syl="dm")
    E.put(sec, bass, bb, local=[bi])
    for v in voices + [bass]:                       # no tie from the bar before into the hit
        P = sec["parts"][v]
        if bi > 0 and P[bi - 1]: P[bi - 1][-1]["tie_out"] = False
        if P[bi]: P[bi][0]["tie_in"] = False
