"""PENTATONIX-STYLE TEMPLATE (5 singers, optionally 6). Runs as is, with no recording:
    python3 ${CLAUDE_SKILL_DIR}/../arranger-core/scripts/build.py pentatonix.py OUT --png

Lineup (references/styles.md, card 2): countertenor, woman (alto), baritone, very low bass, beatbox.
- The lead passes between the three upper voices at section changes (s["lead"] tells QA/renders who has the tune).
- The upper trio sings tight harmony under or around the lead; the bass and the VP form the rhythm section.
- VP density is the energy control: rim click in verses, 8ths, then 16th hats + crash in choruses.

To arrange a real song from a recording:
1. Run analyze.py and write song.py (see SKILL.md, steps 2-3), then `import song as S` below.
2. Replace the demo MEL/LYR/CH with S.V1, S.V1_LYR, S.V1_CH ... and set `first` to the recording bar of each
   section (instead of None), so vp() copies the record's drums and QA can compare against the record.
3. Build with `--work $A/work` so the aligned renders and QA find the analysis.

The demo tune is "Twinkle, Twinkle, Little Star" (public domain).
"""
from engine import *

SIXTH = None   # None = the 5-voice lineup; "T2" = add a 6th singer (an extra tenor in the trio's harmony)

# ---------------------------------------------------------------- lineup (rename/extend before setup())
VOICE_INFO["T1"] = ("Countertenor", "CT", ("G", 2, -1), (55, 77), -30, 76)   # high, light top voice
VOICE_INFO["A"] = ("Alto", "A", ("G", 2, 0), (53, 74), -10, 76)              # the woman's voice: lead or harmony
VOICE_INFO["Br"] = ("Baritone", "Bar", ("G", 2, -1), (45, 69), 15, 76)       # baritone with a high top
VOICE_INFO["B"] = ("Bass", "B", ("F", 4, 0), (31, 55), 0, 92)                # basso profondo, down to G1
TRIO = ["T1", "A", "Br"] + ([SIXTH] if SIXTH else [])
setup(voices=TRIO + ["B", "VP"], title="Twinkle, Twinkle (Pentatonix-style demo)", composer="Traditional",
      arranger="a cappella arr.", name="pentatonix_demo",
      ranges={v: VOICE_INFO[v][3] for v in TRIO + ["B"]})


def lead(sec, voice):
    """Give the tune of the section to one of the upper voices and tell QA/renders who has it."""
    put(sec, voice, sec["mel"])
    sec["lead"] = {i: (voice, 0) for i in range(sec["nbars"])}


def others(voice):
    return [v for v in TRIO if v != voice]


BASS_PUSH = [(1, 0, 6), (1, 6, 2), (2, 8, 6), (2, 14, 2)]     # root . . 8th | 2nd chord . . 8th
BASS_HALF = [(1, 0, 8), (2, 8, 8)]

# demo material: verse (bars 1-4) and chorus (bars 5-8) of the tune
V_CH = [["C"], ["F", "C"], ["F", "C"], ["G", "C"]]
V_MEL = ["C4:4 C4:4 G4:4 G4:4", "A4:4 A4:4 G4:8", "F4:4 F4:4 E4:4 E4:4", "D4:4 D4:4 C4:8"]
V_LYR = ["Twin- -kle twin- -kle", "lit- -tle star", "how I won- -der", "what you are"]
C_CH = [["C", "F"], ["C", "G"], ["C", "F"], ["C", "G"]]
C_MEL = ["G4:4 G4:4 F4:4 F4:4", "E4:4 E4:4 D4:8", "G4:4 G4:4 F4:4 F4:4", "E4:4 E4:4 D4:8"]
C_LYR = ["Up a- -bove the", "world so high", "like a dia- -mond", "in the sky"]

# ================================================================= INTRO: bass + beatbox alone (a "drop" texture)
s = section("Intro", "C", None, [["C"], ["F", "G"]], tempo=96)
put_bass(s, BASS_PUSH, dyn="mf", text="bass, very low")              # 'doom' on long notes, 'dm' on short ones
vp(s, hats="8", groove=dict(K="X.....X...X.....", S="....X.......X..."))
put_pad(s, TRIO, "Mm", R(), local=[1], dyn="p", text="swell")

# ================================================================= VERSE: the baritone has the tune
s = section("Verse", "C", None, V_CH, V_MEL, V_LYR)
lead(s, "Br"); s["text"][("Br", 0)] = "lead"; s["dyn"][("Br", 0)] = "mf"
put_pad(s, others("Br"), "Oo", R(T1=(64, 74), A=(57, 67)), dyn="p", text="pads")
put_bass(s, BASS_HALF, dyn="mf")
vp(s, hats=None, rim=True)

# ================================================================= CHORUS: the countertenor takes the tune, duet with the alto
s = section("Chorus", "C", None, C_CH, C_MEL, C_LYR)
lead(s, "T1"); s["text"][("T1", 0)] = "lead"; s["dyn"][("T1", 0)] = "f"
put(s, "A", harm(s["mel"], s, -1, R()["A"]), text="duet, 3rd below", dyn="f")
put_comp(s, ["Br"] + ([SIXTH] if SIXTH else []), "off8", "jen", R(Br=(52, 62)), text="keys offbeats", dyn="mf")
put_bass(s, BASS_PUSH, dyn="f")
vp(s, hats="16", crash=(0,), groove=dict(K="X.......X.X.....", S="....X.......X..."))

# ================================================================= FINAL VERSE: the alto has the tune, everyone in
s = section("Final", "C", None, V_CH, V_MEL, V_LYR)
lead(s, "A"); s["text"][("A", 0)] = "lead"; s["dyn"][("A", 0)] = "f"
put_block(s, ["T1"], harm(s["mel"], s, +1, R()["T1"]), local=range(3), text="3rd above", dyn="mf")
put_pad(s, ["Br"] + ([SIXTH] if SIXTH else []), "Ah", R(Br=(50, 60)), local=range(3), dyn="mf")
put_bass(s, BASS_PUSH, local=range(3), dyn="f")
vp(s, hats="8", local=range(3))
# last bar: wide final chord with a fermata and a crash
final = {"T1": "r:8 E5:8", "A": "D4:4 D4:4 C4:8", "Br": "r:8 G3:8", "B": "r:8 C2:8"}
if SIXTH: final[SIXTH] = "r:8 C4:8"
for v, t in final.items():
    if v == "A": continue                      # the alto keeps the tune's last bar
    put(s, v, [None, None, None, parse_line([t], [("Ah" if v != "B" else "Doom")])[0]], local=[3])
fermata_last(s)
s["parts"]["VP"][3] = vp_bar({8: "B/Ksh"})
