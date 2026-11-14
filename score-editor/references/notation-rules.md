# Notation rules used by the tools

Why fixed rules: a group reads the same page at the same time. When values, breaths and dynamics follow one rule,
everyone reads the arranger's intent the same way, and a new member learns the rule once.

## Note and rest values (`respell.py`, 4/4, unit = a 16th)
- **The middle of the bar stays visible.** A note crossing beat 3 is tied there. Exceptions: a whole note or a
  dotted half from beat 1, a half or dotted half from beat 2 (they read at a glance).
- **Inside half a bar:** half note, dotted quarter (on the beat or after an 8th), quarter (on the beat, or the
  8th-quarter-8th syncopation), 8th.
- **16ths:** as soon as a 16th position is involved, every beat is shown (tie at the beat).
- **Rests are never syncopated:** a whole-bar rest for an empty bar; a half rest only on beat 1 or 3; a quarter rest
  only on a beat; no dotted quarter rest; two 8th rests on one beat become a quarter rest.
- Notes tied inside a bar are merged first, then written again by these rules. Ties across the barline stay.
- Bars with tuplets or two voices, and percussion staves, are left alone.
- Taste point: 8th tied to 8th from an off-beat (half-bar) becomes a quarter (8th-quarter-8th). Some groups want the
  tie to show the push: say so and keep those bars.

## Breaths (`breaths.py` + `respell.py --plan`)
- A stretch with no rest longer than **4 bars**: an 8th rest is cut out of the end of a note (quarter or longer),
  again until no stretch is longer than 4 bars.
- **2-4 bars:** one breath mark (comma), the note keeps its length.
- **Rap** (cross noteheads): commas only, at the end of each 2-bar line.
- Best place: end of a long note, on a barline, at a 2- or 4-bar phrase end counted from the rehearsal mark. For
  sung words, choose the places by hand at word ends (`--places`) and let the rule do the bass and the rap.
- Lines that should be sung in one breath (one held phrase) get no mark. A bass line whose shape must not change:
  `--no-cut Bass` (commas only).

## Dynamics and playback (`express.py`, `velocity.py`)
- **The lead is always one step above the backing** (lead f / backing mf; lead mf / backing mp or p). Write a new
  dynamic where the lead changes singer.
- **One peak:** ff only in the last chorus; the first chorus stays f ("8 割").
- **Hairpins only into a louder section**, over its last 1-2 bars, and always ending on a written dynamic.
- **Percussion** follows the bass's dynamics, or it stays at velocity 80 while the voices move from 50 to 120.
- MuseScore plays p 49 / mp 64 / mf 80 / f 96 / ff 112; a hairpin raises the velocity until the next dynamic; an
  accent adds to it (ff + accent reaches 127). Check with `velocity.py` after every change.

## Articulations
- **Staccato** on every short scat note (an 8th or less: ta, ra, pa, la, tu, da): same length for everyone.
- **Accent** only on the hits the whole group lands together (a pa, the hook word, the off-beat hits, a shouted
  word). Too many accents read as none.
- **Tenuto** on held notes that support a moving line (oh under a sung hook).

## Comments (`comments.py`)
- One per rehearsal mark: `【狙い】` (what the section is for) and `【歌い方】` (how to sing it), plus `【ここ】` for a
  4-bar line that needs one sentence. They are the arranger's reading: invite the user to rewrite them.
- Someone's own notes become `【メモ】` (`memos.py`), copied to repeats with `（N小節と同じ）`.
- Keep lines short; break a long one after 。 (a comment at the end of a line runs off the page).

## Scat (`scat.py`)
- One family per section so it is easy to remember: e.g. intro all `tu` / `lu` (tu after a rest or a long note, lu
  when the note follows another note), MC under talking `uh` / `tu` / `lu`, rap backing `ta` / `ra` / `uh` / `fu`.
- Exceptions are written as such (`--fixed 2=Fu`, `--keep 5=uh`), never by editing one note by hand.

## Layout (`layout.py`)
- A new line at every rehearsal mark, then every 4 bars; double-time rap bars 2 per line; a short (2/4) bar before
  a mark stays at the end of the previous line; A4 portrait, staff size 1.5 for 6 staves, bar number on every line.
