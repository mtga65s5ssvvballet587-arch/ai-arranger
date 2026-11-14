#!/usr/bin/env python3
"""Direction comments (the arranger's intent, how to sing) as system texts above the top staff.

    python3 comments.py IN.mscz OUT.mscz comments.json [--size 10]

comments.json: [{"bar": 12, "mark": "S-4", "text": "【狙い】...\n【歌い方】..."},
                {"bar": 20, "text": "【ここ】20〜23小節: ..."}]
"mark" (optional) is checked against the rehearsal mark of that bar, so a comment never lands on the wrong section
after bars were added or removed. One system text per entry, at the bar's first note or rest; it is printed on
every part and on the full score. Keep each line short: a long line at the end of a system runs off the page.
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, text_of, make_text, first_event_index


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("comments"); ap.add_argument("--size", type=float, default=10)
    a = ap.parse_args(); s = Score(a.src); n = 0
    for c in json.load(open(a.comments)):
        v = s.voice(0, int(c["bar"])); rm = v.find("RehearsalMark")
        have = text_of(rm) if rm is not None else None
        if "mark" in c and c["mark"] != have: sys.exit(f"bar {c['bar']}: expected mark {c['mark']!r}, the score has {have!r}")
        v.insert(first_event_index(v), make_text("SystemText", c["text"], size=a.size)); n += 1
    s.save(a.dst); print(n, "comments written")


if __name__ == "__main__":
    main()
