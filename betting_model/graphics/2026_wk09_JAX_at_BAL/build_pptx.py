"""Two editable decks for Canva import, built only from box.csv / main_lines.csv / ladders.csv."""
import math, sys
import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

D = sys.argv[1]                     # folder with the CSVs; decks are written here
MADE, BOOKS_AT, KALSHI_AT = "2026-11-03 20:37 UTC", "20:05 UTC", "20:25 UTC"
NAVY, PANEL, ROW2, TEAL, WHITE, MUTED, CORAL, GOLD = (RGBColor(0x0F, 0x1B, 0x2D), RGBColor(0x17, 0x27, 0x3E), RGBColor(0x1D, 0x30, 0x4B),
    RGBColor(0x2E, 0xC4, 0xB6), RGBColor(0xF2, 0xF5, 0xF8), RGBColor(0x9A, 0xA8, 0xB8), RGBColor(0xFF, 0x7A, 0x7A), RGBColor(0xF4, 0xC4, 0x30))
FONT = "Inter"
FOOT = "Simulation projections, not guarantees. Bet responsibly. 21+. 1-800-GAMBLER."
BOOK = {"DraftKings": "DK", "FanDuel": "FD", "BetMGM": "MGM", "Fanatics": "FAN", "theScore Bet": "ESPN", "Hard Rock Bet": "HR",
        "BetRivers": "BR", "Caesars": "CZR", "William Hill": "CZR"}


def deck():
    p = Presentation(); p.slide_width, p.slide_height = Inches(13.333), Inches(7.5); return p


def slide(p, title, sub=None):
    s = p.slides.add_slide(p.slide_layouts[6])
    s.background.fill.solid(); s.background.fill.fore_color.rgb = NAVY
    text(s, 0.45, 0.25, 12.4, 0.6, title, 26, WHITE, bold=True)
    if sub:
        text(s, 0.45, 0.8, 12.4, 0.4, sub, 13, TEAL)
    text(s, 0.45, 7.05, 12.4, 0.3, FOOT, 10, MUTED)
    return s


def text(s, x, y, w, h, t, size, color, bold=False, align=PP_ALIGN.LEFT):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True
    lines = t.split("\n")
    for i, ln in enumerate(lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        r = para.add_run(); r.text = ln; r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color; r.font.name = FONT
    return tb


def table(s, x, y, w, col_w, rows, header, size=11, row_h=0.32, colors=None):
    """rows: list of lists of str. colors: optional list (per row) of per-cell RGB or None."""
    n, m = len(rows) + 1, len(header)
    gt = s.shapes.add_table(n, m, Inches(x), Inches(y), Inches(w), Inches(row_h * n)).table
    tot = sum(col_w)
    for j, cw in enumerate(col_w):
        gt.columns[j].width = Inches(w * cw / tot)
    for i in range(n):
        gt.rows[i].height = Inches(row_h)
        for j in range(m):
            c = gt.cell(i, j); c.margin_left = c.margin_right = Inches(0.05); c.margin_top = c.margin_bottom = Inches(0.01)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid(); c.fill.fore_color.rgb = TEAL if i == 0 else (PANEL if i % 2 else ROW2)
            val = header[j] if i == 0 else rows[i - 1][j]
            tf = c.text_frame; tf.text = ""; para = tf.paragraphs[0]
            para.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            r = para.add_run(); r.text = str(val); r.font.size = Pt(size); r.font.name = FONT
            r.font.bold = i == 0
            col = NAVY if i == 0 else WHITE
            if i and colors and colors[i - 1] and colors[i - 1][j] is not None:
                col = colors[i - 1][j]
            r.font.color.rgb = col
    return gt


def f0(x):
    return "0" if pd.isna(x) else f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}"


def kc(x):
    """Kalshi ask in cents; 95c+ is no real offer on a thin contract, shown as '-'."""
    return "-" if pd.isna(x) or x >= 95 else f0(x)


def pct(x):
    if pd.isna(x): return "-"
    return "<1%" if x < 1 else (">99%" if x > 99 else f"{x:.0f}%")


# ======================= deck 1: box score =======================
box = pd.read_csv(f"{D}/box.csv")
p = deck()
s = slide(p, "JAX at BAL  |  Week 9  |  Projected box score", "Thursday Nov 5, 8:15 PM ET  |  25,000 simulated games")
text(s, 0.45, 1.7, 12.4, 1.3, "JAX 25   BAL 16", 72, WHITE, bold=True, align=PP_ALIGN.CENTER)
text(s, 0.45, 3.2, 12.4, 0.5, "JAX wins 79% of sims  |  Big books: JAX -10, total 40.5", 20, TEAL, align=PP_ALIGN.CENTER)
text(s, 1.5, 4.2, 10.3, 2.2,
     "How to read: every number is the MEDIAN of 25,000 simulated games (half the sims above, half below).\n"
     "Avg = average across sims, useful for depth players whose median is 0.\n"
     "10-90% = range covering the middle 80% of sims.\n"
     "† = model blind spot: projected and shown, never bet (backup QB passing game, coach role cuts, depth players).\n"
     f"Every skill player with offensive snaps in his team's last 2 games is simulated. Lamar Jackson and Tyler Huntley out.\n"
     f"Projections made {MADE}.", 14, MUTED)
for team, opp in (("JAX", "BAL"), ("BAL", "JAX")):
    t = box[box.team == team]
    q = t[t.pos == "QB"].iloc[0]
    s = slide(p, f"{team} projected box score (median of 25,000 sims)",
              f"QB {q.player}{' †' if isinstance(q.blind, str) and q.blind else ''}: {f0(q.pass_cmp)}/{f0(q.pass_att)}, "
              f"{f0(q.pass_yds)} pass yds (10-90%: {f0(q.pass_yds_10)}-{f0(q.pass_yds_90)}), {f0(q.pass_td)} TD, {f0(q.int)} INT, "
              f"{f0(q.rush_yds)} rush yds")
    rows, cols = [], []
    for r in t[t.pos != "QB"].itertuples():
        mark = " †" if isinstance(r.blind, str) and r.blind else ""
        rows.append([f"{r.player}{mark}", r.pos, f0(r.targets), f0(r.rec), f0(r.rec_yds), f0(r.rush_att), f0(r.rush_yds),
                     f0(r.rec_rush_yds), f"{r.rec_rush_yds_mean:.1f}", f"{f0(r.tot_10)}-{f0(r.tot_90)}"])
        cols.append([MUTED if mark else None] + [None] * 9)
    rh = min(0.4, 5.6 / (len(rows) + 1))
    table(s, 0.45, 1.3, 12.4, [3.2, 0.7, 0.9, 0.8, 1.0, 0.9, 1.0, 1.2, 1.2, 1.5], rows,
          ["Player", "Pos", "Targets", "Rec", "Rec yds", "Carries", "Rush yds", "Total yds", "Avg total", "10-90% total"],
          size=13 if len(rows) <= 12 else 12, row_h=rh, colors=cols)
p.save(f"{D}/JAX_at_BAL_box_score.pptx")

# ======================= deck 2: lines =======================
ml = pd.read_csv(f"{D}/main_lines.csv")
lad = pd.read_csv(f"{D}/ladders.csv")
p = deck()
s = slide(p, "JAX at BAL  |  Book vs Kalshi vs model", "Main lines, then every alternate rung inside each player's simulated range")
text(s, 0.6, 1.5, 12.1, 4.6,
     "Main lines: the most common big-book line, median odds across books, and the books' Over % with their cut removed.\n"
     "Kalshi: Yes / No price in cents at the same number (x+ means x or more; a book line of 64.5 = Kalshi 65+).\n"
     "Model: median of 25,000 sims, and the share of sims that go over the line.  Model minus books: positive = model likes the Over.\n\n"
     "Ladders: for every rung posted by Kalshi or a book between the player's lowest and highest simulated result:\n"
     "model % = share of sims at or above the rung; Kalshi Yes / No in cents; best book alternate Over price (book).\n"
     "Book alternate prices include the book's cut. Kalshi prices are asks before Kalshi's fee; '-' = no real offer (ask 95c+).\n"
     "† = model blind spot (shown, never bet).\n\n"
     f"Captured: books {BOOKS_AT}, Kalshi {KALSHI_AT}, projections {MADE} (Nov 3). Prices move; re-check before betting.",
     15, WHITE)
rows, cols = [], []
for r in ml.itertuples():
    mark = " †" if r.blind else ""
    lean = "" if pd.isna(r.lean) else f"{r.lean:+.0f}"
    ky, kn = kc(r.kalshi_yes), kc(r.kalshi_no)
    kal = "-" if pd.isna(r.kalshi_rung) else f"{f0(r.kalshi_rung)}+: {ky + 'c' if ky != '-' else '-'} / {kn + 'c' if kn != '-' else '-'}"
    rows.append([f"{r.player}{mark}", r.stat, f0(r.book_line), f"{int(r.book_over):+d} / {int(r.book_under):+d}", f"{r.book_over_pct:.0f}%", kal,
                 "not simulated" if not r.simulated else f0(r.model_median), "-" if pd.isna(r.model_over_pct) else f"{r.model_over_pct:.0f}%", lean])
    lc = None if pd.isna(r.lean) else (TEAL if r.lean > 0 else CORAL if r.lean < 0 else None)
    cols.append([MUTED if mark else None] + [None] * 7 + [lc])
per = 14
for i in range(0, len(rows), per):
    s = slide(p, f"Main lines: books vs Kalshi vs model ({i // per + 1}/{math.ceil(len(rows) / per)})",
              f"Books {BOOKS_AT}, Kalshi {KALSHI_AT}  |  Model minus books in points: teal = model higher, coral = model lower")
    table(s, 0.45, 1.3, 12.4, [2.6, 1.4, 0.9, 1.5, 1.1, 1.9, 1.2, 1.1, 1.0], rows[i:i + per],
          ["Player", "Stat", "Book line", "Book O / U", "Books Over %", "Kalshi Yes / No", "Model median", "Model Over %", "Model - books"],
          size=12, row_h=0.38, colors=cols[i:i + per])

# ladder chunks: <= 18 rungs per column, <= 4 columns per slide, a player's columns kept together
CH = 18
chunks = []
for (team, player, stat), g in lad.groupby(["team", "player", "stat"], sort=False):
    g = g.sort_values("rung")
    k = math.ceil(len(g) / CH)
    for c in range(k):
        part = g.iloc[c * CH:(c + 1) * CH]
        chunks.append((team, player, stat, f"{player}{' †' if part.blind.iloc[0] else ''}", f"{stat}{f' ({c + 1}/{k})' if k > 1 else ''}", part))
order = {t: i for i, t in enumerate(["JAX", "BAL"])}
chunks.sort(key=lambda c: (order[c[0]], c[1]))
slides, cur, cur_player_cols = [], [], 0
by_player = {}
for c in chunks:
    by_player.setdefault((c[0], c[1]), []).append(c)
for _, cs in by_player.items():
    if len(cur) + len(cs) > 4 and cur:
        slides.append(cur); cur = []
    while len(cs) > 4:
        slides.append(cs[:4]); cs = cs[4:]
    cur += cs
if cur:
    slides.append(cur)
for si, sl in enumerate(slides):
    names = list(dict.fromkeys(c[1] for c in sl))
    s = slide(p, "Alternate ladders: " + ", ".join(names), f"Model % at or above each rung  |  Kalshi Yes / No (cents)  |  best book alternate Over  ({si + 1}/{len(slides)})")
    for j, (team, player, stat, head, sub, part) in enumerate(sl):
        x = 0.35 + j * 3.18
        text(s, x, 1.2, 3.1, 0.35, head, 12, WHITE, bold=True)
        text(s, x, 1.5, 3.1, 0.3, f"{team}  |  {sub}", 11, TEAL)
        rows, cols = [], []
        for r in part.itertuples():
            ky, kn = kc(r.kalshi_yes), kc(r.kalshi_no)
            kal = "-" if ky == "-" and kn == "-" else f"{ky} / {kn}"
            bk = "-" if pd.isna(r.book_best) else f"{int(r.book_best):+d} {BOOK.get(r.book_best_name, r.book_best_name)}"
            rows.append([f"{f0(r.rung)}+", pct(r.model_pct), kal, bk])
            cols.append(None)
        table(s, x, 1.85, 3.05, [0.75, 0.75, 0.95, 1.1], rows, ["Rung", "Model", "Kalshi Y/N", "Best book"],
              size=10, row_h=0.27, colors=cols)
p.save(f"{D}/JAX_at_BAL_book_vs_kalshi_vs_model.pptx")
print("box slides", 3, "| lines slides", 1 + math.ceil(len(ml) / per) + len(slides))
