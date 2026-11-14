# Corpus statistics (PDMX)

Arranging habits measured on 4,466 vocal scores from [PDMX](https://zenodo.org/records/15571083)
(public-domain / CC0 MusicXML from MuseScore; scores with a `license_conflict` and duplicates removed).
Grouped into **pop** (434 scores: pop/rock/soul/soundtrack/jazz genres, or a cappella keywords such as
Pentatonix, beatbox, barbershop) and **classical** (4,032, mostly choral).

- `pdmx_report.md`: the numbers for people (ranges, spacing, texture, bass rhythms, vocables, lead handover, energy arc).
- `pdmx_stats.json`: the same numbers for the engine.

Only statistics are kept here, not the scores. Some pop "public domain" uploads are covers of songs still under
copyright, so the scores themselves are not redistributed.

## Regenerate
```bash
mkdir -p /opt/pdmx && cd /opt/pdmx
curl -fsSL -o PDMX.csv https://zenodo.org/api/records/15571083/files/PDMX.csv/content
curl -fsSL -o mxl.tar.gz https://zenodo.org/api/records/15571083/files/mxl.tar.gz/content   # 1.9 GB
# pick the vocal scores (4-8 voice parts, or a cappella / choir keywords) into cand_paths.txt, then:
mkdir -p corpus && tar xzf mxl.tar.gz -C corpus -T cand_paths.txt
$ACAP_PY -I arranger-core/scripts/corpus_stats.py corpus OUT --csv PDMX.csv
```
`corpus_stats.py` also works on any folder of your own `.mxl` / `.musicxml` files (one group, no `--csv`).

## Caveats
- Lines are ordered by median pitch, so "top" is the highest line, not necessarily the melody.
- "Lead" = the only line singing words in a bar while 2+ lines sound; tutti-word bars are counted apart.
- Very few PDMX scores write the vocal percussion as a staff (35 in the pop group), so beatbox patterns still come
  from the recording's drums.
