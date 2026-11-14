#!/usr/bin/env python3
"""Readable layout: a new system at every rehearsal mark and every N bars inside a section (layout only).

    python3 layout.py IN.mscz OUT.mscz [--bars 4] [--spatium 1.5] [--dense 12] [--keep-style]

- old line / page breaks are removed, then a line break ends every system;
- a bar that carries `--dense` or more lyric syllables on one staff (double-time rap...) is too wide for N bars per
  line: such a section gets 2 bars per system;
- a short bar (another time signature, e.g. a 2/4 bar) just before a rehearsal mark stays at the end of the system
  before it, so the next section still starts a system;
- page A4 portrait, staff size `--spatium` (1.5 fits 6 staves x 4 bars), bar numbers at every system
  (`--keep-style` leaves the page style alone).
Notes, lyrics and marks are not touched.
"""
import sys, os, re, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, lyric

BR = "\n        <LayoutBreak>\n          <subtype>line</subtype>\n          </LayoutBreak>"
BRK = re.compile(r"\s*<LayoutBreak>\s*<subtype>\w+</subtype>\s*</LayoutBreak>")
STYLE = """<Style>
      <harmonyPlay>0</harmonyPlay>
      <Spatium>{sp}</Spatium>
      <pageWidth>8.2677</pageWidth>
      <pageHeight>11.6929</pageHeight>
      <pagePrintableWidth>7.5</pagePrintableWidth>
      <pageEvenLeftMargin>0.35</pageEvenLeftMargin>
      <pageOddLeftMargin>0.35</pageOddLeftMargin>
      <pageEvenTopMargin>0.4</pageEvenTopMargin>
      <pageEvenBottomMargin>0.4</pageEvenBottomMargin>
      <pageOddTopMargin>0.4</pageOddTopMargin>
      <pageOddBottomMargin>0.4</pageOddBottomMargin>
      <staffDistance>3.2</staffDistance>
      <minMeasureWidth>6</minMeasureWidth>
      <lastSystemFillLimit>0</lastSystemFillLimit>
      <akkoladeDistance>5.5</akkoladeDistance>
      <minSystemDistance>6.5</minSystemDistance>
      <maxSystemDistance>9</maxSystemDistance>
      <showMeasureNumbers>1</showMeasureNumbers>
      <measureNumberSystem>1</measureNumberSystem>
      </Style>"""


def system_ends(s, per, dense_min):
    n = s.nbars; marks = {b for b, _ in s.marks()}; lens = s.bar_lengths(); full = max(set(lens), key=lens.count)
    dense = {b for b in range(1, n + 1)
             if max(sum(1 for c in s.voice(si, b).findall("Chord") if lyric(c)) for si in s.sung_staves()) >= dense_min}
    starts = {1} | marks
    sec = 1
    for b in range(1, n + 1):
        if b in marks: sec = b
        if (b - sec) % per == 0: starts.add(b)
    # a short bar right before a mark stays with the system before it
    for b in list(starts):
        if b + 1 in marks and lens[b - 1] != full and b not in marks and b - 1 >= 1: starts.discard(b)
    ends = sorted({b - 1 for b in starts if b > 1})
    # 2 bars per system inside systems that contain 2+ dense bars
    out = set(); first = 1
    for e in ends + [n]:
        bars = list(range(first, e + 1))
        if len(bars) > 2 and sum(b in dense for b in bars) >= 2:
            out |= {b for b in bars[1:-1:2]}
        if e < n: out.add(e)
        first = e + 1
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--bars", type=int, default=4)
    ap.add_argument("--spatium", type=float, default=1.5); ap.add_argument("--dense", type=int, default=12)
    ap.add_argument("--keep-style", action="store_true")
    a = ap.parse_args(); s = Score(a.src); ends = set(system_ends(s, a.bars, a.dense))
    raw = BRK.sub("", s.tostring())
    m = re.search(r'<Staff id="1">\s*(?=<VBox>|<Measure)', raw)
    st = [x.start() for x in re.finditer(r'<Staff id="1">', raw)]
    i0 = max(st); i1 = raw.index('<Staff id="2">', i0) if '<Staff id="2">' in raw[i0:] else len(raw)
    parts = re.split(r"(?=<Measure[ >])", raw[i0:i1]); assert len(parts) - 1 == s.nbars, (len(parts), s.nbars)
    for b in ends: parts[b] = re.sub(r"(<Measure[^>]*>)", lambda x: x.group(1) + BR, parts[b], count=1)
    raw = raw[:i0] + "".join(parts) + raw[i1:]
    if not a.keep_style: raw = re.sub(r"<Style>.*?</Style>", STYLE.format(sp=a.spatium), raw, count=1, flags=re.S)
    s.save(a.dst, raw=s.head + raw[len(s.head):] if raw.startswith(s.head) else raw)
    print(f"{len(ends)} system breaks, {a.bars} bars per system, staff size {a.spatium}")


if __name__ == "__main__":
    main()
