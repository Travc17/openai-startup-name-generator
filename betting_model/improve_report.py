"""Evidence for the improvement loop (IMPROVE_PROMPT.md): what the grades say, across every graded game, and which
lesson is next in the test queue. Reads only saved files plus (with --league) a fresh live-model panel.

    python improve_report.py                 # cumulative scorecard + ledger triage -> reviews/improve_report.md
    python improve_report.py --league        # also the live model on EVERY 2026 game to date (the big sample)

Graded games are few (about 130 predictions a week): they CHOOSE what to test. Only the 2024-25 + 2026 backtests
(MODEL_LAB_PROMPT.md bar) decide what ships.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REV = HERE / "reviews"
CLOSED = {"fixed", "closed", "no_change", "rule_holds"}


def t_vs(x: pd.Series, mu: float) -> float:
    x = x.dropna()
    return float((x.mean() - mu) / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def wilson(k: int, n: int) -> str:
    if not n:
        return "n/a"
    p, z = k / n, 1.96
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{p:.0%} ({k}/{n}; 95% {c - h:.0%} to {c + h:.0%})"


def scorecard(g: pd.DataFrame) -> list[str]:
    games = g.game.nunique()
    ab = g[g.grade.isin(["A", "B"])]
    L = [f"## Graded games: {games} ({', '.join(sorted(g.game.str.replace('2026_', '').unique()))})", "",
         "| Grade | Inside 80% range | Below | Above |", "|---|---|---|---|"]
    for gr in ("A", "B", "C"):
        d = g[g.grade == gr]
        L.append(f"| {gr} | {wilson(int(d.inside.sum()), len(d))} | {int((d.side == 'below').sum())} | {int((d.side == 'above').sum())} |")
    clean = ab[~ab.injury.fillna("").str.contains("did not return") & ~ab.early_exit.fillna(False).astype(bool)]
    L.append(f"| A+B | {wilson(int(ab.inside.sum()), len(ab))} | {int((ab.side == 'below').sum())} | {int((ab.side == 'above').sum())} |")
    L.append(f"| A+B, no in-game exits | {wilson(int(clean.inside.sum()), len(clean))} | | |")
    L += ["", "Calibrated = about 80%. Act only when the whole 95% interval sits outside 70 to 90% AND the league panel agrees.", "",
          "## By stat (A+B): bias and accuracy vs the book", "",
          "| Stat | n | Inside | Mean PIT (t vs 0.50) | Model miss | Book miss | Best miss | Model closer |", "|---|---|---|---|---|---|---|---|"]
    for st, d in ab.groupby("stat"):
        b = d[d.book.notna()]
        L.append(f"| {st} | {len(d)} | {d.inside.mean():.0%} | {d.pit.mean():.2f} ({t_vs(d.pit, 0.5):+.1f}) | {d.err_model.mean():.1f} | "
                 f"{b.err_book.mean() if len(b) else float('nan'):.1f} | {b.err_best.mean() if len(b) else float('nan'):.1f} | "
                 f"{int((b.err_model < b.err_book).sum())}/{len(b)} |")
    b = ab[ab.book.notna()]
    lr = b[b.lean_right.notna()].assign(lean_right=lambda x: x.lean_right.astype(str).str.lower().eq("true"))
    L += ["", "## The betting-relevant check (direction vs the book)", ""]
    for side in ("under", "over"):
        d = lr[lr.lean == side]
        L.append(f"* Model {side} the book: result on the model's side {wilson(int(d.lean_right.sum()), len(d))}")
    L.append(f"* Mean miss: model {b.err_model.mean():.2f}, book {b.err_book.mean():.2f}, best (20/80) {b.err_best.mean():.2f} (n={len(b)})")
    L += ["", "## Where the misses come from (A+B outside the range)", "", "| Slice | Misses | Rows | Miss rate |", "|---|---|---|---|"]
    sl = {"in-game exit (hurt, no return, or out early)": ab.injury.fillna("").str.contains("did not return") | ab.early_exit.fillna(False).astype(bool),
          "QB stats": ab.stat.str.startswith("pass"), "rushing": ab.stat.str.startswith("rush"), "receiving": ab.stat.isin(["rec", "rec_yds", "targets"]),
          "blowout game (final margin 17+)": ab.game.map(lambda x: x in BLOWOUTS)}
    for k, m in sl.items():
        d = ab[m]
        L.append(f"| {k} | {int((~d.inside).sum())} | {len(d)} | {(~d.inside).mean() if len(d) else float('nan'):.0%} |")
    return L


BLOWOUTS: set = set()


def league_panel(season: int, weeks: list[int]) -> list[str]:
    import nfl
    import regression_check as rc
    raw = rc.run(season, weeks, sims=1000, m=nfl.build_model(), raw=True)
    base = json.loads(rc.BASELINE.read_text())["stats"] if rc.BASELINE.exists() else {}
    L = ["", f"## Live model on every {season} game, weeks {weeks[0]}-{weeks[-1]} (real QBs, closing spread, players who played)", "",
         "The big sample: this, not the graded games, says whether ranges or medians drifted.", "",
         "| Stat | n | under p10 | under p50 | under p90 | CRPS | baseline p10/p50/p90, CRPS |", "|---|---|---|---|---|---|---|"]
    for st, d in raw.groupby("stat", sort=False):
        b = base.get(st, {})
        L.append(f"| {st} | {len(d)} | {(d.pit < .1).mean():.1%} | {(d.pit < .5).mean():.1%} | {(d.pit < .9).mean():.1%} | {d.crps.mean():.3f} | "
                 f"{b.get('cov10', '?')}/{b.get('cov50', '?')}/{b.get('cov90', '?')}, {b.get('crps', '?')} |")
    L += ["", "Flag a stat when a coverage number is 5+ points off 10/50/90 here with n >= 300 (and in the baseline sample too:",
          "then it is a model property, not a 2026 drift)."]
    return L


def triage(Lg: pd.DataFrame) -> list[str]:
    L = ["", "## Lessons ledger triage", "", "| Rank | Lesson | Games | Category | Status | Next |", "|---|---|---|---|---|---|"]
    open_ = Lg[~Lg.status.isin(CLOSED)].copy()
    open_["ready"] = (open_.games >= 3) | open_.category.isin(["bug", "known_gap"]) & (open_.games >= 3)
    open_["score"] = open_.games * np.where(open_.category.isin(["known_gap", "pattern", "blind_spot_confirmed"]), 1.0, 0.5)
    open_ = open_.sort_values(["ready", "score"], ascending=False)
    for i, r in enumerate(open_.itertuples(), 1):
        need = "READY for MODEL_LAB" if r.ready else f"needs {max(0, 3 - int(r.games))} more game(s)"
        L.append(f"| {i} | {r.lesson[:90]} | {r.games} | {r.category} | {r.status} | {need} |")
    done = Lg[Lg.status.isin(CLOSED)]
    L += ["", f"Closed or fixed: {len(done)} ({', '.join(done.lesson.str[:40])})"]
    return L


def main(a) -> int:
    g = pd.read_csv(REV / "grades_log.csv")
    g = g[~g.resim.astype(str).str.lower().eq("true")]
    # blowouts from the graded games' finals (play by play)
    from nflmodel import data
    pb = pd.read_parquet(data.DATA_DIR / f"pbp_{a.season}.parquet", columns=["game_id", "week", "home_team", "away_team", "home_score", "away_score"]).drop_duplicates("game_id")
    for gm in g.game.unique():
        wk, rest = int(gm.split("_")[1][2:]), gm.split("_", 2)[2]
        away, home = rest.split("_at_")
        r = pb[(pb.week == wk) & (pb.home_team == home) & (pb.away_team == away)]
        if len(r) and abs(int(r.home_score.iloc[0]) - int(r.away_score.iloc[0])) >= 17:
            BLOWOUTS.add(gm)
    L = [f"# Improvement report ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
         "Graded games CHOOSE what to test; only the MODEL_LAB backtest (2024-25 weeks 4+ and 2026 to date) decides what ships.", ""]
    L += scorecard(g)
    if a.league:
        weeks = sorted(pb.week.unique().tolist())
        L += league_panel(a.season, weeks)
    L += triage(pd.read_csv(REV / "lessons.csv"))
    txt = "\n".join(L) + "\n"
    (REV / "improve_report.md").write_text(txt)
    print(txt)
    print("saved -> reviews/improve_report.md")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--league", action="store_true", help="also run the live model on every game of the season to date")
    sys.exit(main(ap.parse_args()))
