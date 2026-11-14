# What users asked, and what it meant

Real requests from a vocal group arranging a song together (Japanese, often typed on a phone, sometimes cut off).
When a request is ambiguous, ask once with the options below; when it is cut off ("84", "あと、"), ask what follows.

| Request | Meant | Done with |
|---|---|---|
| 4小節ごとに飲みやすい(読みやすい)PDF楽譜にして / 各リハーサルマークごと 4小節ごと | layout, then PDF | `layout.py`, `render.py` |
| 音価の書き方とかだけ直して / ちゃんとしたルールに基づいて | values only, sound unchanged | `respell.py`, `same_sound.py` |
| 休符がない部分を任意の休符で切って、ブレスを任意の箇所に | rests cut + commas | `breaths.py`, `respell.py --plan` |
| bassは音の形を一部例外を入れたくない | no cut on the bass, commas allowed | `breaths.py --no-cut Bass` |
| 強弱とか、おすすめの内容でいれて、別のバージョンで / どういう観点か教えて | a separate expression version + the reasons | `express.py`, `velocity.py` |
| mscz は強弱記号で音量が変わるので考慮して | check playback velocities | `velocity.py` |
| セクションの意図を全部のリハーサルマークごとにコメントで | comments per mark | `comments.py` |
| 4小節ごとに分けた版も | (ambiguous) comments per 4-bar line, or the 4-bar layout: ask or do the first and mention the second | `comments.py`, `layout.py` |
| ここに私が直接書き込んだ注意点がないか確認して、ディレクション入りに書いて | find their notes and edits, merge | `compare_scores.py`, `memos.py` |
| uh の強弱とかメモしてなかった？ | they remember more notes: search every upload (mscz texts, PDF annotations) and say what was found and not found | `inspect_score.py texts` |
| メモが繰り返しの箇所に該当するなら、ほかの繰り返し箇所にも展開 | copy notes to repeats | `memos.py` (default) |
| 移動ドを書いたバージョン（コメントなし） | movable do on a clean version | `spelling.py`, `solfa.py` |
| ダブルフラットなどの書き方も直した版 | plain spelling | `spelling.py` |
| (曲名の一部の文字)にしましょう | (ambiguous) title + lyric, or transpose to C: ask | `relabel.py` / transposition in MuseScore |
| (歌詞の別の箇所)も同じ文字に / テンポは戻そう | lyric run + remove added tempo marks | `relabel.py --lyrics ... --tempo-first-only` |
| 一律 tu tululu 系統に揃えて / 例外として2小節目 Fu | unify scat with exceptions | `scat.py unify --fixed/--keep` |
| ラップの部分だけ音を鳴らさない仕掛け / ✕の符頭に | mute + cross heads | `mute.py` |
| リード回しを入れて、アレンジは変えないで、純粋なパートの組み替え | swap whole bars | `swap.py` |
| 練習案をexcelにまとめて、目次とセクションごとの注意事項をシート別に | practice plan workbook | `practice_plan.py` |
