# Suno → MP3 → (user listens) → arrangement

For a song that does not exist yet as a recording: have Suno make it, let the user listen, and only then run the usual pipeline.

```bash
C=${CLAUDE_SKILL_DIR}/scripts
A=$PWD/arrangements/<song>
export SUNO_API_KEY=...        # sunoapi.org key (cloud session: request_credential for host apibox.erweima.ai)
```

1. **Generate** (candidates only, nothing is analysed yet):
   `python3 $C/suno_fetch.py generate $A --style "bossa nova, warm female vocal" [--lyrics lyrics.txt] [--title T] [--instrumental] [--duration 120]`
   - With `--lyrics` the API runs in custom mode and sings the text as written; without it, `--prompt`/`--style` describe the song.
   - It polls until done and saves `$A/suno/candidates/1.mp3`, `2.mp3` (Suno returns two takes).
2. **Stop and ask the user to listen.** Give the candidate paths and durations. Do not analyse, build or render before an answer.
3. **Approve or retry**:
   - OK: `python3 $C/suno_fetch.py approve $A N [--name song]` copies the take to `$A/song.mp3` (and the lyrics to `$A/lyrics.txt`) and writes `$A/suno/APPROVED`.
   - Not OK: `suno_fetch.py reject $A`, adjust style/lyrics, generate again.
4. **Then run straight through** (the user asked for no further stops): `analyze.py $A/song.mp3 $A/work --lyrics $A/lyrics.txt` (SKILL.md §1), then the style skill the user chose (`acappella-arranger` or `south-american-arranger`), build, render, QA.
   - Only ask when the brief is open (which style / voicing).

Notes:
- Suno output is a finished mix with no click, so check the bar map (`barmap.py`) as for any record.
- Suno has no official API; sunoapi.org is a third-party service. Check its terms and the licence of the generated music before publishing arrangements.

## Re-making your own recording (`cover`)
`suno_fetch.py cover $A --audio my.mp3 --style "a cappella, five-part harmony, beatbox"` uploads the file to the provider's temporary host (deleted after 3 days) and calls `upload-cover`. Same candidates, listen, approve flow as above.
- Only for recordings you own. Suno checks the audio against its catalogue and fails the task (`GENERATE_AUDIO_FAILED: This audio matches an existing recording`) for released music. Do not work around that; use the local pipeline (SKILL.md §1) instead.
- Cloud sessions need a credential for both hosts: `apibox.erweima.ai` and `sunoapiorg.redpandaai.co`.
