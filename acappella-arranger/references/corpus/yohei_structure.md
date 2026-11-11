# How the songs are built (score_story.py)

roles: W words, w words in the lead's rhythm, P pad, C comp, M moving vocables, - rest

## Word harmony (background voices singing the words)
| section | bars | 0 voices | 1 | 2 | 3+ |
|---|---|---|---|---|---|
| intro | 117 | 74% | 5% | 19% | 3% |
| A | 265 | 64% | 10% | 10% | 17% |
| B | 128 | 53% | 9% | 23% | 16% |
| chorus | 222 | 41% | 17% | 18% | 23% |
| last chorus | 41 | 32% | 0% | 46% | 22% |
| bridge | 68 | 46% | 26% | 12% | 16% |
| interlude | 42 | 76% | 12% | 0% | 12% |
| outro | 62 | 53% | 6% | 32% | 8% |
| other | 160 | 51% | 8% | 26% | 14% |

Share of lead bars with word harmony, by bar of the 4-bar phrase: bar 1: 61%, bar 2: 55%, bar 3: 54%, bar 4: 58%

## What the background voices do, per section type
| section | W/w words | P pad | C comp | M moving | - rest |
|---|---|---|---|---|---|
| intro | 15% | 6% | 18% | 40% | 22% |
| A | 27% | 6% | 10% | 26% | 31% |
| B | 36% | 23% | 3% | 35% | 4% |
| chorus | 42% | 10% | 12% | 30% | 6% |
| last chorus | 59% | 18% | 3% | 12% | 9% |
| bridge | 33% | 10% | 13% | 28% | 16% |
| interlude | 14% | 22% | 2% | 39% | 23% |
| outro | 28% | 2% | 7% | 48% | 15% |
| other | 35% | 11% | 6% | 26% | 22% |

## The bar before a section change (vs the three bars before it) and the downbeat after

**into intro** (9 changes)
- VP fill (pattern changes): 78%
- VP busier: 22%
- backgrounds mostly M -> M: 22%
- backgrounds mostly C -> C: 22%
- VP busier in the new section: 22%

**into A** (43 changes)
- VP fill (pattern changes): 56%
- voices enter on the downbeat: 33%
- voices leave on the downbeat: 26%
- backgrounds mostly M -> M: 16%
- backgrounds mostly w -> -: 14%
- VP drops out / stops: 14%

**into B** (14 changes)
- VP fill (pattern changes): 64%
- backgrounds mostly w -> W: 21%
- VP busier: 21%
- backgrounds mostly P -> M: 14%
- long notes (hold / swell): 14%
- backgrounds mostly w -> P: 14%
- backgrounds mostly M -> M: 14%

**into chorus** (29 changes)
- VP fill (pattern changes): 83%
- backgrounds mostly M -> M: 21%
- VP busier: 17%
- backgrounds mostly w -> M: 17%
- VP drops out / stops: 14%
- backgrounds mostly w -> w: 14%

**into last chorus** (6 changes)
- VP fill (pattern changes): 83%
- backgrounds mostly w -> w: 67%
- voices enter on the downbeat: 50%
- long notes (hold / swell): 33%
- backgrounds mostly P -> w: 17%
- VP busier: 17%
- backgrounds mostly M -> w: 17%

**into bridge** (8 changes)
- VP fill (pattern changes): 38%
- voices enter on the downbeat: 38%
- VP drops out / stops: 12%
- all voices sing the words: 12%
- voices leave on the downbeat: 12%
- backgrounds mostly w -> -: 12%
- backgrounds mostly - -> P: 12%
- backgrounds mostly M -> P: 12%
- backgrounds mostly M -> C: 12%
- VP thinner / out in the new section: 12%
- backgrounds mostly M -> M: 12%
- VP busier: 12%
- VP busier in the new section: 12%
- backgrounds mostly C -> M: 12%
- break (2+ voices drop): 12%
- backgrounds mostly w -> P: 12%
- backgrounds mostly w -> w: 12%

**into interlude** (8 changes)
- VP fill (pattern changes): 88%
- voices enter on the downbeat: 38%
- voices leave on the downbeat: 38%
- backgrounds mostly M -> -: 25%
- VP drops out / stops: 12%
- break (2+ voices drop): 12%
- backgrounds mostly - -> W: 12%
- VP thinner / out in the new section: 12%
- backgrounds mostly - -> -: 12%
- all voices sing the words: 12%
- VP busier in the new section: 12%
- backgrounds mostly w -> P: 12%
- VP busier: 12%
- backgrounds mostly P -> P: 12%
- backgrounds mostly P -> M: 12%
- backgrounds mostly w -> C: 12%

**into outro** (7 changes)
- VP fill (pattern changes): 43%
- backgrounds mostly w -> M: 29%
- VP busier: 14%
- backgrounds mostly M -> M: 14%
- backgrounds mostly M -> C: 14%
- backgrounds mostly w -> C: 14%
- backgrounds mostly M -> w: 14%
- break (2+ voices drop): 14%
- voices enter on the downbeat: 14%
- VP thinner / out in the new section: 14%
- backgrounds mostly M -> W: 14%

**into other** (17 changes)
- VP fill (pattern changes): 71%
- voices enter on the downbeat: 29%
- long notes (hold / swell): 24%
- backgrounds mostly - -> -: 18%
- backgrounds mostly P -> w: 18%
- VP busier: 18%

## VP fill grids in the bar before a section change (top 12)
- `X.XXX.X.X.X.X.X.` x6
- `X.........X.X.X.` x5
- `X.X.X.X.X.X.X.X.` x4
- `X.X.X.X.X.......` x4
- `X.X.X.X...X.X.X.` x4
- `X.X.X.X.X.XXXXXX` x3
- `X...X...X.X.XXXX` x3
- `X.X.X.X.X.XXXXX.` x3
- `..........X.X.X.` x2
- `XXXXX.XXXXX.XXXX` x2
- `XXXXX.X.XXX.XXX.` x2
- `..X.X.X.XXXXXXXX` x2

## VP grooves per section type (top 3)
- intro: `X.X.X.X.X.X.X.X.` x34, `X...X.X.X.X.X.X.` x8, `X.XXX.X.X.X.X.XX` x6
- A: `X.X.X.X.X.X.X.X.` x89, `X.XXX.X.X.X.X.XX` x16, `X...X.X.X.X.X.X.` x15
- B: `X.X.X.X.X.X.X.X.` x36, `X...X.X.X.X.X.X.` x14, `X.X.X.X...X.X.X.` x13
- chorus: `X.X.X.X.X.X.X.X.` x79, `X...X.X.X.X.X.X.` x30, `X.XXX.X.X.X.X.XX` x11
- last chorus: `X.X.X.X.X.X.X.X.` x16, `X.XXX.XXXXX.XXXX` x4, `X...X.X.X.X.X.X.` x3
- bridge: `X.X.X.X.X.X.X.X.` x37, `X...X.X.X.X.X.X.` x8, `X.X.X.X.X.X.X...` x4
- interlude: `..X.X.X.X.X.X.X.` x11, `X.XXXXXXXXXXXXXX` x6, `X.X.X.X.X.XXX.X.` x5
- outro: `X.X.X.X.X.X.X.X.` x24, `X.XXX.X.X.X.X.XX` x6, `X...X.X.X.X.X.X.` x5
- other: `X.X.X.X.X.X.X.X.` x49, `X...X.X.X.X.X.X.` x27, `X..XX.X.XXX.X.XX` x17

## Bass grids per section type (top 3)
- intro: `..X.X.X.X.X.X.X.` x10, `X.....X.....X.X.` x9, `X.X.X.....X.X.X.` x8
- A: `X.....X.....X.X.` x21, `X..X..X...X.X..X` x14, `..X..X..X..X..X.` x14
- B: `X.....X.....X.X.` x13, `X.X.X.X.X.X.X.X.` x13, `..X.X.X.X.X.X.X.` x13
- chorus: `X.X.X.X.X.X.X.X.` x29, `X.....X...X...X.` x16, `..X.X...X.X.X.X.` x14
- last chorus: `X.....X...X...X.` x8, `X..X..X...X.X.X.` x7, `..X.X...X.X.X.X.` x7
- bridge: `X...X.X.....X...` x12, `..X.X.X.X.X...X.` x8, `............X.X.` x5
- interlude: `X.....X.....X.X.` x13, `..X.X.X.X.X.X.X.` x9, `X...X...X..X..X.` x6
- outro: `..X.X.X.X.X.X.X.` x8, `X.X.X.....X.X.X.` x7, `X..X..XX..X.X.X.` x6
- other: `X.X.XX.X.X.X.XX.` x15, `X...X.....X.X.X.` x14, `X..X..X..X..X.X.` x14
