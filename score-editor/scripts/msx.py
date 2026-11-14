"""Small library for editing MuseScore files (.mscz / .mscx, format 3.02 written by MuseScore 3.6 and read by 4).

    from msx import Score
    s = Score("in.mscz")
    for bar, tick, el in s.events(staff=0): ...
    s.save("out.mscz")

Everything works on the XML tree; nothing is laid out here (MuseScore does that when it opens the file).
Units: ticks are 16ths (a 4/4 bar = 16). Bars and staves are counted as MuseScore shows them: bar 1 = first measure,
staff 0 = top staff.
"""
import os, re, copy, zipfile, xml.etree.ElementTree as ET
from fractions import Fraction

DUR = {"whole": 16, "half": 8, "quarter": 4, "eighth": 2, "16th": 1}
NAME = {16: ("whole", 0), 12: ("half", 1), 8: ("half", 0), 6: ("quarter", 1), 4: ("quarter", 0), 3: ("eighth", 1),
        2: ("eighth", 0), 1: ("16th", 0)}
PITCH = "C Db D Eb E F Gb G Ab A Bb B".split()


def length(e):
    """Length of a Chord / Rest in 16ths (a whole-bar rest gives the bar length)."""
    t = e.findtext("durationType")
    if t == "measure": return int(Fraction(e.findtext("duration")) * 16)
    n = DUR[t]; d = int(e.findtext("dots") or 0)
    return n + (n // 2 if d >= 1 else 0) + (n // 4 if d >= 2 else 0)


def set_length(e, n):
    """Write a length in 16ths (one of NAME's keys) as durationType + dots."""
    for t in ("durationType", "dots", "duration"):
        for k in e.findall(t): e.remove(k)
    nm, d = NAME[n]
    k = ET.Element("durationType"); k.text = nm; e.insert(0, k)
    if d: k = ET.Element("dots"); k.text = str(d); e.insert(0, k)


def text_of(e):
    """Plain text of an element with a <text> child (font tags removed)."""
    t = e.find("text") if e.find("text") is not None else e
    return "".join(t.itertext()).strip()


def make_text(tag, text, size=None, below=False):
    """A StaffText / SystemText / ... element; `size` sets the font size of the whole text."""
    e = ET.Element(tag)
    if below: ET.SubElement(e, "placement").text = "below"
    t = ET.SubElement(e, "text")
    if size: f = ET.SubElement(t, "font", size=str(size)); f.tail = text
    else: t.text = text
    return e


def lyric(chord, no=0):
    """Lyric text of a chord on verse `no` (0 = first line), or None."""
    for l in chord.findall("Lyrics"):
        if int(l.findtext("no") or 0) == no: return text_of(l)
    return None


def tie(note, kind):
    """The Tie spanner of a note going 'next' or coming from 'prev', or None."""
    return next((sp for sp in note.findall("Spanner") if sp.get("type") == "Tie" and sp.find(kind) is not None), None)


def tied_in(chord): return any(tie(n, "prev") is not None for n in chord.findall("Note"))
def tied_out(chord): return any(tie(n, "next") is not None for n in chord.findall("Note"))
def pitch_name(p): return f"{PITCH[p % 12]}{p // 12 - 1}"


def first_event_index(voice):
    """Index in the voice of the first Chord / Rest / Tuplet: annotations are inserted before it."""
    k = list(voice)
    return next((i for i, x in enumerate(k) if x.tag in ("Chord", "Rest", "Tuplet")), len(k))


def insert_at(voice, tick, el):
    """Insert an annotation (text, dynamic...) at a tick of the voice; falls back to the bar start when no
    chord / rest starts exactly there."""
    t = 0
    for i, x in enumerate(list(voice)):
        if x.tag in ("Chord", "Rest"):
            if t == tick: voice.insert(i, el); return tick
            if t > tick: break
            t += length(x)
    voice.insert(first_event_index(voice), el); return 0


class Score:
    def __init__(self, path):
        self.path = path
        if path.endswith(".mscx"):
            raw = open(path, encoding="utf8").read(); self.zip = None; self.name = os.path.basename(path)
        else:
            self.zip = zipfile.ZipFile(path); self.name = next(m for m in self.zip.namelist() if m.endswith(".mscx"))
            raw = self.zip.read(self.name).decode("utf8")
        self.head = raw[:raw.index("<museScore")]
        self.root = ET.fromstring(raw[raw.index("<museScore"):])
        self.sc = self.root.find("Score")
        self.staves = self.sc.findall("Staff")
        self.parts = self.sc.findall("Part")

    # ---- structure -------------------------------------------------------------------------------------------
    @property
    def nbars(self): return len(self.staves[0].findall("Measure"))

    def measure(self, si, bar): return self.staves[si].findall("Measure")[bar - 1]

    def voice(self, si, bar, k=0):
        vs = self.measure(si, bar).findall("voice")
        return vs[k] if k < len(vs) else None

    def staff_names(self):
        """Long names of the staves (one per staff, from its part)."""
        out = []
        for p in self.parts:
            nm = p.findtext("Instrument/longName") or p.findtext("trackName") or ""
            out += [nm.strip()] * len(p.findall("Staff"))
        return out

    def short_names(self):
        """'Top Anna' -> 'Top' : the first word of each staff name."""
        return [(n.split() or ["?"])[0] for n in self.staff_names()]

    def is_percussion(self, si):
        sid = self.staves[si].get("id")
        for p in self.parts:
            for st in p.findall("Staff"):
                if st.get("id") == sid:
                    g = st.find("StaffType")
                    return (g is not None and g.get("group") == "percussion") or p.findtext("Instrument/useDrumset") == "1"
        return False

    def sung_staves(self): return [i for i in range(len(self.staves)) if not self.is_percussion(i)]

    def bar_lengths(self):
        return [sum(length(x) for x in m.find("voice") if x.tag in ("Chord", "Rest")) for m in self.staves[0].findall("Measure")]

    def bar_starts(self):
        out, t = [], 0
        for n in self.bar_lengths(): out.append(t); t += n
        return out

    def marks(self):
        """[(bar, rehearsal mark text)] in score order."""
        out = []
        for b, m in enumerate(self.staves[0].findall("Measure"), 1):
            for e in m.iter("RehearsalMark"): out.append((b, text_of(e)))
        return out

    def key_fifths(self):
        """Key signature of the first staff as a number of sharps (+) / flats (-)."""
        k = next(self.staves[0].iter("KeySig"), None)
        if k is None: return 0
        return int(k.findtext("concertKey") or k.findtext("accidental") or 0)

    def title(self):
        for mt in self.sc.iter("metaTag"):
            if mt.get("name") == "workTitle" and mt.text: return mt.text
        return ""

    # ---- iteration ---------------------------------------------------------------------------------------------
    def events(self, si, bars=None, voice=None):
        """Yield (bar, tick in bar, element, voice element) for every element of the staff."""
        for b, m in enumerate(self.staves[si].findall("Measure"), 1):
            if bars and b not in bars: continue
            for k, v in enumerate(m.findall("voice")):
                if voice is not None and k != voice: continue
                t = 0
                for e in list(v):
                    yield b, t, e, v
                    if e.tag in ("Chord", "Rest"): t += length(e)

    # ---- output -----------------------------------------------------------------------------------------------
    def tostring(self): return self.head + ET.tostring(self.root, encoding="unicode")

    def save(self, path, raw=None):
        """Write .mscz (thumbnail dropped: it no longer matches) or .mscx. `raw` overrides the XML text."""
        data = raw if raw is not None else self.tostring()
        if path.endswith(".mscx") or self.zip is None and not path.endswith(".mscz"):
            open(path, "w", encoding="utf8").write(data); return
        zo = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)
        if self.zip is None:
            zo.writestr("META-INF/container.xml", CONTAINER.format(self.name)); zo.writestr(self.name, data)
        else:
            for it in self.zip.infolist():
                if it.filename.startswith("Thumbnails/"): continue
                zo.writestr(it, data.encode("utf8") if it.filename == self.name else self.zip.read(it.filename))
        zo.close()


CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container><rootfiles><rootfile full-path="{}"/></rootfiles></container>
"""


def parse_bars(spec, nbars):
    """'12-15,20' -> {12,13,14,15,20}; empty -> all bars."""
    if not spec: return set(range(1, nbars + 1))
    out = set()
    for part in str(spec).split(","):
        if "-" in part: a, b = part.split("-"); out |= set(range(int(a), int(b) + 1))
        elif part.strip(): out.add(int(part))
    return out


def parse_staves(spec, score):
    """'0,2' or names ('Top,3rd') -> staff indexes; empty -> the sung staves."""
    if not spec: return score.sung_staves()
    names = score.short_names(); out = []
    for p in str(spec).split(","):
        p = p.strip()
        out.append(int(p) if p.lstrip("-").isdigit() else next(i for i, n in enumerate(names) if n.lower() == p.lower()))
    return out
