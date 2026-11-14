---
name: score-editor
description: Edit an existing MuseScore score (.mscz, MuseScore 3 or 4) that a group sings or plays from, without opening MuseScore, and prepare it for rehearsal. Readable layout (a new line at every rehearsal mark, 4 bars per line); note and rest values written by fixed rules; breath marks and short rests where nobody can breathe; dynamics, crescendos and accents checked against what MuseScore actually plays; the arranger's intent per section as comments; someone's own notes collected from a file they edited and copied to every repeat of the passage; movable-do syllables; double flats fixed; title, lyrics, part names and tempo marks renamed; scat syllables made uniform; rap or spoken notes shown with cross noteheads and muted; lead rotation by swapping whole bars between singers; a practice plan in Excel (contents, schedule, one sheet of notes per section). Use it whenever the user hands over an .mscz and asks to change how it is written, to add marks or comments, to make it easier to read or rehearse, or sends back a file they wrote in.
argument-hint: "<score.mscz> [what to change]"
---

# Score editor: change how a score is written, prepare it for rehearsal

The user's score is the material; the music in it is theirs. **Change only what was asked, and prove it:** every
tool that should not change the sound is checked with MIDI (`velocity.py`, or `render.py` + a comparison), and every
hand-off ends with `compare_scores.py` between what you received and what you send.

```bash
E=${CLAUDE_SKILL_DIR}/scripts            # these tools (python3, no venv needed except openpyxl for the plan)
W=work/<song>                            # a work folder OUTSIDE the repository (scores and lyrics are copyrighted)
```
MuseScore is needed only to export (PDF, MIDI): `render.py` finds `mscore4`/`mscore`/`mscore3` or `$ACAP_MSCORE`
(no window: it sets `QT_QPA_PLATFORM=offscreen`). MuseScore 3.2 cannot open files saved by 3.6: prefer MuseScore 4.
Files stay in MuseScore 3 format (3.02), so both MuseScore 3.6 and 4 open them.

## 0. Look before you touch
```bash
python3 $E/inspect_score.py $W/in.mscz info              # parts, bars, key, rehearsal marks, odd-length bars
python3 $E/inspect_score.py $W/in.mscz bars 12-15 --staves Top,3rd   # pitch:16ths(lyric), r:16ths, [texts]
python3 $E/inspect_score.py $W/in.mscz texts             # every text, with staff and bar
```
Staves are named by the first word of the part name ("Top Anna" -> `Top`) or by number (0 = top staff).
Bars are MuseScore's bar numbers. Lengths are in 16ths (4/4 bar = 16).

## 1. The user sends back a file they wrote in
Always first: `python3 $E/compare_scores.py SENT.mscz THEIRS.mscz`. It lists their notes (texts), changed notes,
lyrics, tempo and marks (line breaks and above/below flips are ignored). Several files: compare each with the
version it came from (`inspect_score.py texts` + the file names tell which). Report everything you found before
merging, including what you did NOT find if they say "I wrote more" (look in every upload, PDF annotations too).
Then take their edits over, and their written notes with
`memos.py THEIRS.mscz OUT.mscz --original SENT.mscz`: each note becomes `【メモ】...` above the top staff at the same
beat, and is copied to every bar that repeats the passage (same pitches and rhythm on the staff it was written on,
and the same in the bar before or after): `【メモ】（63小節と同じ）...`. A note on one part keeps the part:
`【メモ（3rd）】`. MC lines and shouts stay where they are.

## 2. What to use for what

| The user asks (examples) | Tool |
|---|---|
| 4小節ごと・リハーサルマークごとに見やすく / PDFにして | `layout.py IN OUT --bars 4` then `render.py OUT out.pdf`; look at the pages |
| 音価の書き方を直して / ちゃんとしたルールで | `respell.py IN OUT` (rules in [references/notation-rules.md](references/notation-rules.md)) |
| 休符がない所を区切って、ブレスを入れて | `breaths.py IN plan.json [--places places.json] [--no-cut Bass]` then `respell.py IN OUT --plan plan.json` |
| 強弱・アクセントを入れて | write an expression plan, `express.py IN OUT plan.json`, then **`velocity.py OUT`** |
| セクションの意図をコメントで | `comments.py IN OUT comments.json` (`【狙い】` / `【歌い方】`, and `【ここ】` per 4-bar line) |
| 私が書き込んだ注意点を入れて | `compare_scores.py` then `memos.py` (§1) |
| 移動ドを書いた版 | `spelling.py` (double flats) then `solfa.py`; a separate version without comments |
| ダブルフラットを直して | `spelling.py IN OUT` |
| タイトル/歌詞/パート名を変えて, テンポは戻して | `relabel.py IN OUT --title A=B --lyrics "ラ,ラ,A=ラ,ラ,B" --parts "..." --tempo-first-only` |
| スキャットを tu / lu に揃えて | `scat.py IN OUT unify --bars ... --start tu --follow lu [--fixed 2=Fu] [--keep 5=uh]` |
| 歌詞のない音にスキャットを | `scat.py IN OUT fill --bars ... --short ta --run ra --long uh [--whole fu]` |
| ラップの所は音を鳴らさない・✕の符頭に | `mute.py IN OUT --staves 3rd --bars 69-86` |
| リード回し（パートの組み替えだけ） | `swap.py IN OUT plan.json --lead-labels` |
| 練習案をExcelで | `practice_plan.py SCORE plan.xlsx plan.json`, then the xlsx skill's `recalc.py` |

Japanese phrasings and what they turned out to mean: [references/requests-ja.md](references/requests-ja.md).

## 3. Order when several changes are asked
1. their edits (§1); 2. content: `swap.py`, `scat.py`, `mute.py`, `relabel.py`; 3. `respell.py` (+ breaths);
4. `express.py` + `velocity.py`; 5. `comments.py`, `memos.py`; 6. `layout.py`; 7. `render.py` PDF + look;
8. side versions from the same file: `spelling.py` + `solfa.py` (movable do), `practice_plan.py`.
Keep each step's output (`in.mscz` -> `respelled.mscz` -> ...): later requests often start from a middle step
("the expression version, but without comments").

## 4. Checks that are not optional
- **Sound unchanged** where it must be: `python3 $E/velocity.py OUT.mscz` prints the velocities MuseScore plays;
  for layout / spelling / respell / comments, also compare the MIDI note lists of before and after (`render.py` to
  `.mid`). `respell.py` with a plan shortens exactly the planned notes, by an 8th.
- **Playback of dynamics**: MuseScore plays p 49 / mp 64 / mf 80 / f 96 / ff 112 and a hairpin raises the level
  until the next dynamic. `express.py` writes the level again where every hairpin ends; `velocity.py` warns when a
  lead is quieter than a backing staff, when notes hit 127, and when percussion never changes (give it the
  bass's dynamics: `"drums_follow": "Bass"`).
- **Look at the PDF** (`pdftoppm -r 70`): comments at the end of a line run off the page (break them), a long rap
  bar does not fit 4 to a line (`layout.py` makes those lines 2 bars), a 2/4 bar before a mark stays at the end of
  the previous line.
- `compare_scores.py RECEIVED OUT` before sending: the list must be exactly what was asked.

## 5. Pitfalls met on real scores
- Imported scores spell notes with double flats (Bbb for A): fix with `spelling.py` before movable do, or the
  syllables follow the odd spelling.
- A capital letter sung as a word (a group name like `B`) is not scat: `scat.py` treats only lower-case latin syllables as scat.
- A staff text the arranger wrote ("だんだん大きく", "Solo") is not the user's note: give `memos.py --original`.
- A tempo mark someone added to try a slower tempo (`♩=165` in the middle) changes the playback for the rest of the
  song: point it out; `relabel.py --tempo-first-only` takes it back out when asked.
- A "Lead" text is the only source for who leads: when a section passes the lead without one, say it in the plan's
  `"lead"` override.
- Never write the user's names, lyrics or scores into the repository: plans and comments with lyrics live in the
  work folder; only tools and generic examples are committed.

Examples of every JSON file: [examples/](examples/).
