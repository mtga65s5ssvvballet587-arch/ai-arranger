#!/usr/bin/env python3
"""Practice plan workbook (Excel) from a score: a contents sheet, the rehearsal schedule, and one sheet of notes per
section. The notes are read from the score itself, so they match the PDF bar for bar.

    python3 practice_plan.py SCORE.mscz plan.xlsx plan.json

From the score: sections (rehearsal marks + "extra_sections"), the lead (staff texts "Lead"), the section comment
(system text 【狙い】... / 【歌い方】... at the section's first bar), other system texts (comments, 【メモ】),
dynamics, crescendos, accents, breath marks, MC lines (「...」), shouts ((...)) and other staff texts.
plan.json (all optional except steps):
{
  "title": "曲名 練習プラン", "source": "元にした楽譜の説明", "start": "13:00", "total_minutes": 120,
  "extra_sections": [{"bar": 95, "name": "S-2(後半)"}],             # sections without a rehearsal mark
  "rename": {"64": "intro(間奏)"},                                  # sheet names by first bar (must be unique)
  "lead": {"S-1(後半)": "2nd → 4th → Top"},                          # when the "Lead" texts do not say it all
  "steps": [{"minutes": 15, "title": "イントロ系", "sections": ["Intro", "intro(間奏)"], "who": "全員",
             "aim": "...", "how": "...", "check": "..."}],
  "tips": ["..."],
  "notes": [{"bar": 24, "staff": "2nd", "kind": "休符で区切り", "text": "..."}]   # rows the marks do not say
}
Then: python3 <xlsx skill>/scripts/recalc.py plan.xlsx  (the times are formulas).
"""
import sys, os, re, json, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from msx import Score, text_of, lyric
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment

F = "Arial"
H1 = Font(name=F, size=16, bold=True); H2 = Font(name=F, size=12, bold=True); B = Font(name=F, size=10); BB = Font(name=F, size=10, bold=True)
HEAD = Font(name=F, size=10, bold=True, color="FFFFFF"); LINK = Font(name=F, size=10, color="0563C1", underline="single")
INPUT = Font(name=F, size=10, color="0000FF"); EX = Font(name=F, size=10, italic=True, color="808080")
HFILL = PatternFill("solid", fgColor="44546A"); LFILL = PatternFill("solid", fgColor="F2F2F2"); YFILL = PatternFill("solid", fgColor="FFF2CC")
thin = Side(style="thin", color="BFBFBF"); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
WRAP = Alignment(wrap_text=True, vertical="top"); CEN = Alignment(horizontal="center", vertical="top", wrap_text=True)
ORDER = ["ポイント", "メモ", "リード", "強弱", "クレッシェンド", "アクセント", "休符で区切り", "ブレス", "MC", "掛け声", "指示"]
KIND_FILL = {"リード": "DDEBF7", "強弱": "E2EFDA", "クレッシェンド": "E2EFDA", "ブレス": "FCE4D6", "休符で区切り": "FCE4D6",
             "アクセント": "FFF2CC", "MC": "EDEDED", "掛け声": "EDEDED", "メモ": "FFF2CC"}


def header(ws, r, cols):
    for c, t in enumerate(cols, 1):
        x = ws.cell(r, c, t); x.font = HEAD; x.fill = HFILL; x.alignment = CEN; x.border = BOX


def cell(ws, r, c, v, font=B, al=WRAP, fill=None):
    x = ws.cell(r, c, v); x.font = font; x.alignment = al; x.border = BOX
    if fill: x.fill = fill
    return x


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("score"); ap.add_argument("xlsx"); ap.add_argument("plan")
    a = ap.parse_args(); s = Score(a.score); P = json.load(open(a.plan)); full = s.staff_names(); short = s.short_names()
    # sections
    starts = dict(s.marks())
    for x in P.get("extra_sections", []): starts[int(x["bar"])] = x["name"]
    for b, n in P.get("rename", {}).items(): starts[int(b)] = n
    bars = sorted(starts); seen = collections.Counter(); SECS = []
    for k, b0 in enumerate(bars):
        b1 = bars[k + 1] - 1 if k + 1 < len(bars) else s.nbars
        nm = starts[b0]; seen[nm] += 1
        if seen[nm] > 1: nm = f"{nm}({seen[nm]})"
        SECS.append(dict(name=nm, a=b0, b=b1))
    by_name = {x["name"]: x for x in SECS}
    # marks per bar
    dyn = collections.defaultdict(list); hp = collections.defaultdict(set); br = collections.defaultdict(list)
    acc = collections.defaultdict(set); stx = collections.defaultdict(list); systx = collections.defaultdict(list); lead_at = {}
    for si in range(len(s.staves)):
        last = ""
        for b, t, e, v in s.events(si):
            if e.tag == "Dynamic": dyn[b].append((si, e.findtext("subtype")))
            elif e.tag == "Spanner" and e.get("type") == "HairPin" and e.find("HairPin") is not None: hp[b].add(si)
            elif e.tag == "Breath": br[b].append((si, last))
            elif e.tag == "StaffText":
                x = text_of(e); stx[b].append((si, x))
                if "Lead" in x: lead_at[b] = si
            elif e.tag == "SystemText": systx[b].append(text_of(e))
            elif e.tag == "Chord":
                ly = lyric(e)
                if ly: last = ly
                elif not any(t_ is not None for t_ in [x.find('Spanner[@type="Tie"]/prev') for x in e.findall('Note')]): last = ""
                if any((x.findtext("subtype") or "").startswith("articAccent") for x in e.findall("Articulation")): acc[b].add(si)
    who = lambda ids: "・".join(short[i] for i in sorted(ids))
    extra = collections.defaultdict(list)
    for n in P.get("notes", []):
        st = n.get("staff"); w = full[short.index(st)] if st in short else (st or "全員")
        extra[int(n["bar"])].append((int(n["bar"]), w, n.get("kind", "ポイント"), n["text"]))

    def rows_of(sec):
        rows = []
        for bar in range(sec["a"], sec["b"] + 1):
            for x in systx.get(bar, []):
                if bar == sec["a"] and x.startswith("【狙い】"): continue
                rows.append((bar, "全員", "メモ" if x.startswith("【メモ") else "ポイント", re.sub(r"^【ここ】", "", x).replace("\n", " ")))
            if dyn.get(bar):
                g = collections.defaultdict(list)
                for si, d in dyn[bar]: g[d].append(si)
                rows.append((bar, "パート別（右の通り）", "強弱", "　".join(f"{d}：{who(v)}" for d, v in g.items())))
            if hp.get(bar): rows.append((bar, who(hp[bar]), "クレッシェンド", "次の小節へ向けて大きく（到達点で強弱を書き直してあります）"))
            for si, last in br.get(bar, []):
                rows.append((bar, full[si], "ブレス", f"「{last}」（の伸ばし）のあとで吸う" if last and re.search(r"[^\x00-\x7f]", last) else "この位置で素早く吸う"))
            if acc.get(bar): rows.append((bar, who(acc[bar]), "アクセント", "キメ。全員で縦を揃える"))
            for si, t in stx.get(bar, []):
                if "Lead" in t: rows.append((bar, full[si], "リード", "ここからリード" if t == "Lead" else t))
                elif t.startswith("「") or t.startswith("(MC)"): rows.append((bar, full[si], "MC", t))
                elif t.startswith("(") or t.startswith("（"): rows.append((bar, full[si], "掛け声", t))
                elif t: rows.append((bar, full[si], "指示", t))
            rows += extra.get(bar, [])
        return sorted(rows, key=lambda r: (r[0], ORDER.index(r[2]) if r[2] in ORDER else 99))

    def lead_of(sec):
        cur = None
        for b in range(1, sec["a"] + 1):
            if b in lead_at: cur = lead_at[b]
        chain = [cur] if cur is not None and not any(sec["a"] <= b <= sec["b"] and b == sec["a"] for b in lead_at) else []
        for b in range(sec["a"], sec["b"] + 1):
            if b in lead_at and (not chain or chain[-1] != lead_at[b]): chain.append(lead_at[b])
        return " → ".join(full[i] for i in chain if i is not None) or "—"

    STEPS = P["steps"]; step_of = {}
    for i, st in enumerate(STEPS, 1):
        for k in st.get("sections", []):
            if k not in by_name: sys.exit(f"step {i}: no section {k!r} (sections: {', '.join(by_name)})")
            step_of[k] = i
    wb = Workbook(); toc = wb.active; toc.title = "目次"
    toc["A1"] = P.get("title") or f"{s.title()} 練習プラン"; toc["A1"].font = H1
    toc["A2"] = P.get("source", "小節番号・記号は楽譜と同じです。"); toc["A2"].font = B
    header(toc, 4, ["シート", "内容", "小節", "練習の順番"])
    rows = [("練習スケジュール", "練習の順番と時間配分", "", "")] + [(x["name"], f"{x['name']} の注意事項", f"{x['a']}〜{x['b']}", f"{step_of[x['name']]}番目" if x["name"] in step_of else "") for x in SECS]
    for i, (sh, what, bb, step) in enumerate(rows, 5):
        x = cell(toc, i, 1, sh, LINK); x.hyperlink = f"#'{sh}'!A1"; cell(toc, i, 2, what); cell(toc, i, 3, bb, al=CEN); cell(toc, i, 4, step, al=CEN)
    r = 5 + len(rows) + 1; toc.cell(r, 1, "使い方").font = H2
    for k, t in enumerate(["シート名をクリックすると、そのシートに飛びます。各シートの A1 に「目次へ戻る」があります。",
                           "練習スケジュールの「開始時刻」（黄色のセル）を変えると、全体の時刻が自動で変わります。",
                           "青い文字のセル（各ステップの分数）を変えると、開始・終了時刻と合計が計算し直されます。",
                           "各セクションの「済」「メモ」列（黄色）は自由に書き込んでください。最初のシートに記入例があります。",
                           "表の色：青＝リード、緑＝強弱、オレンジ＝ブレス・休符、黄＝アクセント・メモ、灰＝MC・掛け声。"], 1):
        toc.cell(r + k, 1, f"{k}. {t}").font = B
    for c, w in zip("ABCD", [22, 48, 12, 12]): toc.column_dimensions[c].width = w
    total = P.get("total_minutes", sum(x["minutes"] for x in STEPS))
    ws = wb.create_sheet("練習スケジュール")
    ws["A1"] = "← 目次へ戻る"; ws["A1"].font = LINK; ws["A1"].hyperlink = "#'目次'!A1"
    ws["A2"] = f"練習スケジュール（{total}分）"; ws["A2"].font = H1; ws["A3"] = "開始時刻"; ws["A3"].font = BB
    h, m = map(int, P.get("start", "13:00").split(":"))
    ws["B3"] = (h * 60 + m) / 1440; ws["B3"].number_format = "h:mm"; ws["B3"].font = INPUT; ws["B3"].fill = YFILL; ws["B3"].border = BOX
    ws["B3"].comment = Comment("実際の開始時刻に書き換えてください。", "Claude")
    header(ws, 5, ["順番", "開始", "分", "終了", "練習内容", "セクション（シート）", "小節", "参加", "ねらい", "進め方", "チェックポイント", "済", "メモ"])
    for i, st in enumerate(STEPS, 1):
        r = 5 + i; keys = st.get("sections", [])
        cell(ws, r, 1, i, al=CEN)
        x = cell(ws, r, 2, "=$B$3" if i == 1 else f"=D{r - 1}", al=CEN); x.number_format = "h:mm"
        x = cell(ws, r, 3, st["minutes"], INPUT, CEN); x.number_format = "0"
        x = cell(ws, r, 4, f"=B{r}+C{r}/1440", al=CEN); x.number_format = "h:mm"
        cell(ws, r, 5, st["title"], BB)
        x = cell(ws, r, 6, "、".join(keys) if keys else "—", LINK if keys else B)
        if keys: x.hyperlink = f"#'{keys[0]}'!A1"
        cell(ws, r, 7, "、".join(f"{by_name[k]['a']}〜{by_name[k]['b']}" for k in keys) if keys else "—")
        for c, k in zip(range(8, 12), ("who", "aim", "how", "check")): cell(ws, r, c, st.get(k, ""))
        cell(ws, r, 12, "", al=CEN, fill=YFILL); cell(ws, r, 13, "", fill=YFILL)
        if not keys and "休" in st["title"]:
            for c in range(1, 14): ws.cell(r, c).fill = LFILL
    rt = 6 + len(STEPS)
    cell(ws, rt, 5, "合計", BB); x = cell(ws, rt, 3, f"=SUM(C6:C{rt - 1})", BB, CEN); x.number_format = "0"
    x = cell(ws, rt, 4, f"=D{rt - 1}", BB, CEN); x.number_format = "h:mm"
    cell(ws, rt, 6, f'=IF(C{rt}={total},"予定どおり（{total}分）","予定との差："&TEXT(C{rt}-{total},"+0;-0")&"分")')
    if P.get("tips"):
        ws.cell(rt + 2, 1, "進め方のコツ").font = H2
        for k, t in enumerate(P["tips"], 1): ws.cell(rt + 2 + k, 1, f"{k}. {t}").font = B
    for c, w in zip("ABCDEFGHIJKLM", [6, 8, 6, 8, 18, 22, 16, 16, 28, 36, 36, 5, 24]): ws.column_dimensions[c].width = w
    ws.freeze_panes = "A6"
    for n, sec in enumerate(SECS):
        sh = wb.create_sheet(sec["name"])
        sh["A1"] = "← 目次へ戻る"; sh["A1"].font = LINK; sh["A1"].hyperlink = "#'目次'!A1"
        sh["A2"] = f"{sec['name']}（{sec['a']}〜{sec['b']}小節）"; sh["A2"].font = H1
        aim = how = ""
        for x in systx.get(sec["a"], []):
            mm = re.match(r"【狙い】(.*)\n【歌い方】(.*)", x, re.S)
            if mm: aim, how = mm.group(1).strip(), mm.group(2).strip()
        st = step_of.get(sec["name"])
        info = [("狙い", aim), ("歌い方", how), ("リード", P.get("lead", {}).get(sec["name"]) or lead_of(sec)),
                ("練習の順番", f"{st}番目：{STEPS[st - 1]['title']}（{STEPS[st - 1]['minutes']}分）" if st else "")]
        for i, (k, v) in enumerate(info, 4):
            cell(sh, i, 1, k, BB, fill=LFILL); sh.merge_cells(start_row=i, start_column=2, end_row=i, end_column=6); cell(sh, i, 2, v)
            for c in range(3, 7): sh.cell(i, c).border = BOX
            sh.row_dimensions[i].height = 30 if len(v) > 40 else 18
        x = sh.cell(8, 1, "練習スケジュールへ →"); x.font = LINK; x.hyperlink = "#'練習スケジュール'!A1"
        sh.cell(10, 1, "注意事項").font = H2; header(sh, 11, ["小節", "パート", "種類", "内容", "済", "メモ"])
        for i, (bar, w, kind, t) in enumerate(rows_of(sec), 12):
            f = PatternFill("solid", fgColor=KIND_FILL.get(kind, "FFFFFF"))
            cell(sh, i, 1, bar, al=CEN); cell(sh, i, 2, w); cell(sh, i, 3, kind, al=CEN, fill=f); cell(sh, i, 4, t)
            cell(sh, i, 5, "", al=CEN, fill=YFILL); cell(sh, i, 6, "", fill=YFILL)
        if n == 0: sh.cell(12, 6, "例：3回目で揃った。次回は135から").font = EX
        for c, w in zip("ABCDEF", [12, 26, 14, 60, 5, 30]): sh.column_dimensions[c].width = w
        sh.freeze_panes = "A12"
    for w in wb.worksheets:
        w.sheet_view.showGridLines = False
        w.page_setup.orientation = "landscape"; w.page_setup.fitToWidth = 1; w.page_setup.fitToHeight = 0; w.sheet_properties.pageSetUpPr.fitToPage = True
    wb.save(a.xlsx); print("sheets:", len(wb.worksheets), "| sections:", ", ".join(x["name"] for x in SECS))


if __name__ == "__main__":
    main()
