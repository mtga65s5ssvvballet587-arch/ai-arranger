"""Arranging choices drawn from corpus statistics (acappella-arranger/references/corpus/pdmx_stats.json) instead of
one fixed pattern per section. Use on top of the engine:

    from engine import *
    import corpus_style as CS
    CS.load("pop", seed=7)
    plan = CS.lead_plan(sec, ["T1", "A", "Br"])       # who sings the tune, phrase by phrase
    CS.backgrounds(sec, plan, ["T1", "A", "Br"], energy=0.6, ranges=...)
    CS.bass(sec, energy=0.6)
    CS.drums(sec, energy=0.6)

What comes from the numbers (pop group, 434 scores):
- background roles per phrase: moving line 53%, pad 27%, rhythmic comp 19%, shifted by `energy` (0 quiet .. 1 full);
- block chords under the lead (homorhythm) on ~35% of phrases;
- background syllables weighted as the corpus sings them (da, dm, dah, doo, ba ... for short notes; oo, ah, oh, mm
  for long ones);
- bass onset patterns: the corpus' most common 4/4 bass rhythms, sparse ones at low energy, busy ones at high;
- lead handover: runs of 2 / 4 / 8 bars (corpus median 2, quartiles 1-7), always on phrase boundaries;
- VP: backbeat grooves weighted by the corpus, denser with energy.
Everything is seeded, so a build is reproducible; change the seed to hear another draw.
"""
import json, os, random
import engine as E

HERE = os.path.dirname(os.path.abspath(__file__))
STATS_PATH = os.path.join(HERE, "..", "..", "acappella-arranger", "references", "corpus", "pdmx_stats.json")
S = {}
RNG = random.Random(0)
LONG_SYL = ("oo", "ah", "oh", "ooh", "mm")
SHORT_SYL = ("da", "dm", "dah", "doo", "ba", "dum", "du", "bum", "doh", "bah", "dat", "dn")


def load(group="pop", seed=0, path=STATS_PATH):
    global S
    S = json.load(open(path))["groups"][group]
    RNG.seed(seed)
    return S


def _pick(weights):
    items = [(k, w) for k, w in weights.items() if w > 0]
    tot = sum(w for _, w in items)
    x = RNG.random() * tot
    for k, w in items:
        x -= w
        if x <= 0: return k
    return items[-1][0]


def syllable(long=False):
    voc = S.get("vocables", {})
    pool = LONG_SYL if long else SHORT_SYL
    w = {k: voc.get(k, 0.002) for k in pool}
    s = _pick(w)
    return s.capitalize() if long else s


def full(sec, v):
    """A voice's bars over the whole section, rests where nothing is written yet."""
    return [b if b else E.rest_bar() for b in sec["parts"].get(v, [None] * sec["nbars"])]


def phrases(sec, size=2):
    n = sec["nbars"]
    return [list(range(i, min(n, i + size))) for i in range(0, n, size)]


# ------------------------------------------------------------------------------------------------ lead
def lead_plan(sec, voices, start=None, phrase=2):
    """-> list of (bar indices, voice). Run lengths 2/4/8 bars weighted from the corpus quartiles (half the runs
    <= 2 bars, a quarter 3-7, a quarter longer), cut at the section end; the lead never stays when it changes."""
    lr = S.get("lead_run_bars", {"p25": 1, "median": 2, "p75": 7})
    w = {phrase: 0.5, 2 * phrase: 0.25, 4 * phrase: 0.25} if lr.get("median", 2) <= 2 else {2 * phrase: .5, 4 * phrase: .5}
    plan, i, cur = [], 0, start or RNG.choice(voices)
    while i < sec["nbars"]:
        n = min(_pick(w), sec["nbars"] - i)
        plan.append((list(range(i, i + n)), cur))
        i += n
        cur = RNG.choice([v for v in voices if v != cur])
    return plan


def sing_lead(sec, plan, ranges):
    """Write the tune into the planned voices, moved by octaves into each singer's range."""
    for bars, v in plan:
        lo, hi = ranges[v]
        ps = [e["midi"] for b in bars for e in sec["mel"][b] if e["midi"] is not None]
        k = 0
        if ps:
            while max(ps) + k > hi and min(ps) + k - 12 >= lo - 2: k -= 12
            while min(ps) + k < lo and max(ps) + k + 12 <= hi + 2: k += 12
        E.put(sec, v, E.shift(sec["mel"], k) if k else sec["mel"], local=bars, text="lead")
        sec.setdefault("lead", {}).update({b: (v, 0) for b in bars})


# ------------------------------------------------------------------------------------------------ backgrounds
def role_weights(energy):
    lr = S.get("line_role", {})
    mv = lr.get("moving line", .53); pad = lr.get("pad (half-bar+ notes)", .27)
    comp = lr.get("rhythmic comp (4+ onsets, 1-2 pitches)", .19)
    # quiet sections lean on pads, full ones on comp: scale around the corpus mean
    return {"moving": mv, "pad": pad * (1.6 - 1.2 * energy), "comp": comp * (0.4 + 1.6 * energy)}


COMP_BY_ENERGY = [(0.0, ["half", "back"]), (0.4, ["off8", "back", "push"]), (0.7, ["push", "off8", "tres", "bell"])]


def backgrounds(sec, plan, trio, ranges, energy=0.5, phrase=2, words_block=None):
    """Fill the trio's non-lead voices phrase by phrase with a role drawn from the corpus weights:
    pad (long vowels), comp (short corpus syllables on a pattern), moving (block chords under the lead with the lead's
    words: homorhythm, drawn with the corpus' 35%) or a 3rd/6th line under the lead on a short syllable."""
    lead_of = {b: v for bars, v in plan for b in bars}
    tex = S.get("texture", {})
    p_block = tex.get("homorhythm (block chords)", .35) if words_block is None else words_block
    for ph in phrases(sec, phrase):
        lead = lead_of[ph[0]]
        others = [v for v in trio if v != lead]
        role = _pick(role_weights(energy))
        if role == "moving" and RNG.random() < p_block / max(1e-6, role_weights(energy)["moving"]):
            # block chords under the lead: the others take the tune's rhythm and words
            stack = sorted([lead] + others, key=lambda v: -sum(ranges[v]))
            if stack[0] == lead:
                top = full(sec, lead)
                E.put_block(sec, stack, top, local=ph, text="block, with the words")
                continue
            role = "moving"
        if role == "pad":
            syl = syllable(long=True)
            E.put_pad(sec, others, syl, ranges, local=ph, text=f"pad ({syl})")
        elif role == "comp":
            opts = [p for e0, ps in COMP_BY_ENERGY if energy >= e0 for p in ps][-4:]
            pat = RNG.choice(opts)
            syl = syllable()
            E.put_comp(sec, others, pat, syl, ranges, local=ph, text=f"{syl} ({pat})")
        else:
            # one counter line a 3rd under the lead on a short syllable, the other holds a pad
            syl = syllable()
            up = sum(ranges[others[0]]) > sum(ranges[lead])     # a higher singer harmonises above the lead
            line = E.harm(E.relyric(full(sec, lead), lambda e, i: syl), sec, 1 if up else -1, ranges[others[0]])
            E.put(sec, others[0], line, local=ph, text=f"3rd {'above' if up else 'under'} the lead ({syl})")
            if len(others) > 1:
                ls = syllable(long=True)
                E.put_pad(sec, others[1:], ls, ranges, local=ph, text=f"pad ({ls})")


# ------------------------------------------------------------------------------------------------ bass and VP
def _grid_to_pattern(grid, n_chords):
    ons = [i for i, c in enumerate(grid) if c == "X"]
    pat = []
    for j, s in enumerate(ons):
        nxt = ons[j + 1] if j + 1 < len(ons) else 16
        d = nxt - s
        if d > 2 and d % 2 and d != 3: d -= 1
        sel = 1 + s * n_chords // 16          # the chord sounding under this onset
        pat.append((sel, s, d))
    return pat


def bass_patterns(energy, k=3):
    """The corpus' bass rhythms ranked by frequency, filtered by how busy they are for this energy."""
    br = S.get("bass_rhythm_4_4", {})
    want = 1 + round(energy * 6)                     # onsets per bar: 1 (quiet) .. 7 (full)
    cands = {g: w for g, w in br.items() if g[0] == "X" and abs(g.count("X") - want) <= 1}
    if not cands: cands = {"X.......X.......": 1}
    return cands


def bass(sec, energy=0.5, local=None, change_every=4, voice="B", rng=None, text=True):
    """Bass bar patterns drawn from the corpus (a new draw every `change_every` bars, so it grooves rather than
    wanders)."""
    pats = bass_patterns(energy)
    cur = None
    for bi in range(sec["nbars"]):
        if local is not None and bi not in local: continue
        if cur is None or bi % change_every == 0:
            cur = _pick(pats)
        pattern = _grid_to_pattern(cur, len(sec["chords"][bi]))
        E.put_bass(sec, pattern, local=[bi], voice=voice, rng=rng,
                   text=("bass" if text and bi == 0 else None))


def drums(sec, energy=0.5, local=None, crash=()):
    """VP: kick/snare from the corpus' grooves (backbeat first), hats denser with energy, rim in quiet sections."""
    vr = S.get("vp_rhythm_4_4", {})
    snare = "....X.......X..."
    kicks = {g: w for g, w in vr.items() if g.startswith("X") and g.count("X") <= 4} or {"X.......X.......": 1}
    kick = _pick(kicks) if energy > 0.3 else "X.......X......."
    hats = None if energy < 0.3 else ("8" if energy < 0.75 else "16")
    E.vp(sec, hats=hats, rim=energy < 0.45, crash=crash, local=local, groove=dict(K=kick, S=snare))
