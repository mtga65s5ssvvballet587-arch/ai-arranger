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
SYL_LONG = None


def load(work, seed=0, group="pop"):
    global W, D
    W = work
    D = runpy.run_path(os.path.join(work, "draft.py"))
    CS.load(group, seed=seed)
    return D


def chords(a, b):
    out = []
    prev = ["C"]
    for n in range(a, b + 1):
        row = list(D.get("CHORDS", {}).get(n) or prev)
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
    for bar in out:
        for e in bar:
            if e["midi"] is not None and not e["tie_in"]:
                e["lyr"] = "doom" if e["dur"] >= 4 else "dm"
    return out


def hook_bars(a, b, rng):
    toks = [_clean_tokens(D.get("OTHER_TOP", {}).get(n)) for n in range(a, b + 1)]
    bars = fold(E.parse_line(toks), (rng[0] + 5, rng[1] - 3), E.LAST.get(TRIO[0]))   # middle of the range
    return E.relyric(bars, E.flute)


def part(name, a, b, energy=0.5, key="C", hook=False, vp=True, bass=True, tempo=None, phrase=2, crash=None):
    """One section of the record (recording bars a..b) with backing only."""
    rows = chords(a, b)
    s = E.section(name, key, a, rows, tempo=tempo)
    rng = {v: E.VOICE_INFO[v][3] for v in TRIO + ["B"]}
    RT = E.R(**rng)
    dyn = "pp" if energy < .2 else "p" if energy < .4 else "mp" if energy < .6 else "mf" if energy < .8 else "f"
    if bass:
        E.put(s, "B", bass_bars(s, a, b, rng["B"]), text="bass (record's line)" if a == 1 or energy >= .3 else None,
              dyn=dyn)
    if vp:
        hats = None if energy < .3 else ("8" if energy < .75 else "16")
        E.vp(s, hats=hats, rim=energy < .45, crash=crash if crash is not None else ((0,) if energy >= .7 else ()))
    hk = hook_bars(a, b, rng[TRIO[0]]) if hook else None
    first = True
    for ph in CS.phrases(s, phrase):
        voices = TRIO[1:] if hook else TRIO
        if hook:
            E.put(s, TRIO[0], hk, local=ph, text="hook (synth line, 'doo-dl')" if first else None,
                  dyn=dyn if first else None)
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
    sec["parts"].setdefault("VP", [None] * sec["nbars"])[-1] = E.vp_bar({0: "B/Ksh"})
