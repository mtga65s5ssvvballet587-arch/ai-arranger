# How the songs are built (score_story.py)

roles: W words, w words in the lead's rhythm, P pad, C comp, M moving vocables, - rest

## Word harmony (background voices singing the words)
| section | bars | 0 voices | 1 | 2 | 3+ |
|---|---|---|---|---|---|
| intro | 80 | 76% | 8% | 16% | 0% |
| A | 199 | 66% | 7% | 9% | 18% |
| B | 96 | 48% | 11% | 26% | 15% |
| chorus | 132 | 55% | 10% | 20% | 14% |
| last chorus | 33 | 36% | 0% | 52% | 12% |
| bridge | 60 | 48% | 27% | 8% | 17% |
| interlude | 38 | 79% | 8% | 0% | 13% |
| outro | 52 | 62% | 6% | 31% | 2% |
| other | 159 | 51% | 8% | 26% | 14% |

Share of lead bars with word harmony, by bar of the 4-bar phrase: bar 1: 60%, bar 2: 54%, bar 3: 53%, bar 4: 52%

## What the background voices do, per section type
| section | W/w words | P pad | C comp | M moving | - rest |
|---|---|---|---|---|---|
| intro | 12% | 8% | 16% | 48% | 17% |
| A | 27% | 4% | 13% | 31% | 25% |
| B | 39% | 23% | 4% | 31% | 3% |
| chorus | 32% | 10% | 14% | 39% | 5% |
| last chorus | 53% | 23% | 2% | 10% | 11% |
| bridge | 31% | 8% | 15% | 30% | 16% |
| interlude | 14% | 24% | 0% | 37% | 25% |
| outro | 21% | 1% | 5% | 55% | 18% |
| other | 36% | 11% | 6% | 27% | 21% |

## The bar before a section change (vs the three bars before it) and the downbeat after

**into intro** (7 changes)
- VP fill (pattern changes): 86%
- VP busier: 29%
- backgrounds mostly M -> M: 29%
- backgrounds mostly C -> C: 29%
- backgrounds mostly w -> C: 14%
- backgrounds mostly P -> M: 14%
- voices enter on the downbeat: 14%
- VP busier in the new section: 14%
- backgrounds mostly - -> C: 14%

**into A** (34 changes)
- VP fill (pattern changes): 53%
- voices leave on the downbeat: 29%
- voices enter on the downbeat: 24%
- backgrounds mostly M -> M: 21%
- backgrounds mostly M -> C: 15%
- backgrounds mostly w -> -: 15%

**into B** (10 changes)
- VP fill (pattern changes): 70%
- backgrounds mostly w -> W: 30%
- backgrounds mostly w -> P: 20%

**into chorus** (25 changes)
- VP fill (pattern changes): 84%
- backgrounds mostly M -> M: 24%
- VP busier: 20%
- backgrounds mostly w -> M: 20%

**into last chorus** (5 changes)
- VP fill (pattern changes): 80%
- backgrounds mostly w -> w: 80%
- voices enter on the downbeat: 60%
- long notes (hold / swell): 40%
- backgrounds mostly P -> w: 20%

**into bridge** (7 changes)
- VP fill (pattern changes): 43%
- voices enter on the downbeat: 43%
- VP drops out / stops: 14%
- all voices sing the words: 14%
- voices leave on the downbeat: 14%
- backgrounds mostly w -> -: 14%
- backgrounds mostly - -> P: 14%
- backgrounds mostly M -> P: 14%
- backgrounds mostly M -> C: 14%
- VP thinner / out in the new section: 14%
- backgrounds mostly M -> M: 14%
- VP busier: 14%
- VP busier in the new section: 14%
- backgrounds mostly C -> M: 14%
- break (2+ voices drop): 14%
- backgrounds mostly w -> P: 14%

**into interlude** (7 changes)
- VP fill (pattern changes): 100%
- voices enter on the downbeat: 43%
- voices leave on the downbeat: 43%
- backgrounds mostly M -> -: 29%
- VP drops out / stops: 14%
- break (2+ voices drop): 14%
- backgrounds mostly - -> W: 14%
- VP thinner / out in the new section: 14%
- backgrounds mostly - -> -: 14%
- all voices sing the words: 14%
- VP busier in the new section: 14%
- backgrounds mostly w -> P: 14%
- VP busier: 14%
- backgrounds mostly P -> P: 14%
- backgrounds mostly P -> M: 14%

**into outro** (6 changes)
- VP fill (pattern changes): 50%
- backgrounds mostly w -> M: 33%
- VP busier: 17%
- backgrounds mostly M -> M: 17%
- backgrounds mostly M -> C: 17%
- backgrounds mostly w -> C: 17%
- backgrounds mostly M -> w: 17%
- break (2+ voices drop): 17%
- voices enter on the downbeat: 17%
- VP thinner / out in the new section: 17%

**into other** (17 changes)
- VP fill (pattern changes): 71%
- voices enter on the downbeat: 29%
- long notes (hold / swell): 24%
- backgrounds mostly - -> -: 18%
- backgrounds mostly P -> w: 18%
- VP busier: 18%

## VP fill grids in the bar before a section change (top 12)
- `X.XXX.X.X.X.X.X.` x6
- `X.X.X.X.X.......` x4
- `X.X.X.X...X.X.X.` x4
- `X.X.X.X.X.XXXXXX` x3
- `X...X...X.X.XXXX` x3
- `X.X.X.X.X.XXXXX.` x3
- `X.........X.X.X.` x3
- `X.X.X.X.X.X.X.X.` x2
- `XXXXX.XXXXX.XXXX` x2
- `XXXXX.X.XXX.XXX.` x2
- `..X.X.X.XXXXXXXX` x2
- `XXX..X..X.XXX.X.` x2

## VP grooves per section type (top 3)
- intro: `X.X.X.X.X.X.X.X.` x27, `X...X.X.X.X.X.X.` x7, `X.XXX.X.X.X.X.XX` x6
- A: `X.X.X.X.X.X.X.X.` x55, `X.XXX.X.X.X.X.XX` x16, `X...X.X.X.X.X.X.` x12
- B: `X.X.X.X.X.X.X.X.` x24, `X.X.X.X...X.X.X.` x13, `X...X.X.X.X.X.X.` x12
- chorus: `X.X.X.X.X.X.X.X.` x41, `X...X.X.X.X.X.X.` x15, `X.XXX.X.X.X.X.XX` x11
- last chorus: `X.X.X.X.X.X.X.X.` x11, `X.XXX.XXXXX.XXXX` x4, `X...X.X.X.X.X.X.` x3
- bridge: `X.X.X.X.X.X.X.X.` x35, `X...X.X.X.X.X.X.` x8, `X.X.X.X.X.X.X...` x4
- interlude: `..X.X.X.X.X.X.X.` x7, `X.XXXXXXXXXXXXXX` x6, `X.X.X.X.X.XXX.X.` x5
- outro: `X.X.X.X.X.X.X.X.` x24, `X.XXX.X.X.X.X.XX` x6, `X...X.X.X.X.X.X.` x5
- other: `X.X.X.X.X.X.X.X.` x49, `X...X.X.X.X.X.X.` x27, `X..XX.X.XXX.X.XX` x17

## Bass grids per section type (top 3)
- intro: `X.X.X.....X.X.X.` x8, `X.....X.....X.X.` x8, `X..X..X...X.X..X` x7
- A: `X.....X.....X.X.` x21, `X..X..X...X.X..X` x14, `..X..X..X..X..X.` x14
- B: `X...X.X...X.X...` x12, `X..X..X...X...X.` x12, `X.....X.....X.X.` x11
- chorus: `X..X..X..XXXX.XX` x12, `X.....X...X...X.` x12, `X.....X...X...XX` x12
- last chorus: `X.....X...X...X.` x8, `X..X..X...X.X.X.` x7, `X.....X...X...XX` x6
- bridge: `X...X.X.....X...` x12, `..X.X.X.X.X...X.` x8, `X.....X.....X...` x4
- interlude: `X.....X.....X.X.` x13, `X...X...X..X..X.` x6, `..X.X.X.X.X.X.X.` x6
- outro: `X.X.X.....X.X.X.` x7, `X..X..XX..X.X.X.` x6, `..X..X..X..X..X.` x5
- other: `X.X.XX.X.X.X.XX.` x15, `X...X.....X.X.X.` x14, `X..X..X..X..X.X.` x14
