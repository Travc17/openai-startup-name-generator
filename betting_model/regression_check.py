"""Regression check: re-run the LIVE model on a fixed sample of past games and flag drift.

Sample: 2025 weeks 10-13 (every game), real starting QBs, closing spread for game script,
route-role blend as in reports. Scores each stat by CRPS and by how often the actual result
landed under the model's 10th / 50th / 90th percentile (a calibrated model reads 10 / 50 / 90).

    python regression_check.py            # compare with regression_baseline.json, exit 1 on drift
    python regression_check.py --save     # write a new baseline (only after a change was tested and shipped)

Drift flags: CRPS worse by more than 2% on a stat, or any coverage number moved by more than
5 points from the baseline. This catches broken data joins and silent code changes; it is not
an edge test (the calibration maps were fit on seasons that include this sample).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nfl  # noqa: E402
from nflmodel import data  # noqa: E402
from nflmodel.backtest import crps  # noqa: E402
from nflmodel.game import Player  # noqa: E402

BASELINE = HERE / "regression_baseline.json"
SEASON, WEEKS, SIMS = 2025, range(10, 14), 2000
CRPS_TOL, COV_TOL = 0.02, 5.0


def run(season: int = SEASON, weeks=WEEKS, sims: int = SIMS, m=None, raw: bool = False):
    """Per-stat CRPS and coverage on the sample (raw=True also returns every (stat, actual, crps, pit) row)."""
    m = m or nfl.build_model()
    gi_ = pd.read_parquet(data.DATA_DIR / f"pbp_{season}.parquet",
                          columns=["game_id", "home_team", "spread_line"]).drop_duplicates("game_id").set_index("game_id")
    P = m.qbm.p
    starter = (P[P.key // 100 == season].groupby(["game_id", "posteam", "passer_player_id"]).size().rename("att")
               .reset_index().sort_values("att").drop_duplicates(["game_id", "posteam"], keep="last")
               .set_index(["game_id", "posteam"]).passer_player_id)
    qb_act = P.groupby(["game_id", "passer_player_id"]).agg(
        pass_att=("yards", "size"), pass_cmp=("complete", "sum"), pass_yds=("yards", "sum"))
    rng = np.random.default_rng(5)
    games = m.tg[(m.tg.key // 100 == season) & (m.tg.key % 100).isin(weeks)].drop_duplicates("game_id")
    rows = []
    for gi, g in enumerate(games.itertuples(index=False)):
        if g.game_id not in gi_.index:
            continue
        G = gi_.loc[g.game_id]
        act = m.pg[m.pg.game_id == g.game_id].set_index("pid")
        opp = {g.posteam: g.defteam, g.defteam: g.posteam}
        qbs = {t: starter.get((g.game_id, t)) for t in opp}
        if any(v is None for v in qbs.values()):
            continue
        roster = []
        for t in opp:
            for pid in m.usage_leaders(t, g.key, min_targets=3, min_carries=6):
                if pid not in act.index:
                    continue            # sample = players who actually played (same rule as the backtests)
                rm = 1.0
                try:
                    inp = m.player_inputs(Player(pid, t), opp[t], g.key)
                    es = m.route_role.expected_share(pid, t, g.key, inp["pos"]) if m.route_role else None
                    if es is not None and inp["t_share"] > 0.01:
                        rm = float(np.clip((0.5 * es + 0.5 * inp["t_share"]) / inp["t_share"], 0.4, 2.5))
                except ValueError:
                    pass
                roster.append(Player(pid, t, share_mult=rm))
        em = None if pd.isna(G.spread_line) else (G.spread_line if g.posteam == G.home_team else -G.spread_line)
        try:
            sim = m.simulate(g.posteam, g.defteam, g.key, roster, n_sims=sims, seed=3000 + gi, exp_margin_a=em, qbs=qbs)
        except (ValueError, KeyError):
            continue
        for pid, s in sim["players"].items():
            info = sim["info"][pid]
            if "pass_yds" in s and (g.game_id, pid) in qb_act.index:
                for st in ("pass_att", "pass_cmp", "pass_yds"):
                    rows.append((st, float(qb_act.loc[(g.game_id, pid), st]), s[st]))
            if pid not in act.index:
                continue
            stats = (["targets", "rec", "rec_yds"] if info["t_share"] >= 0.06 else []) + \
                    (["rush_att", "rush_yds"] if info["c_share"] >= 0.15 else [])
            for st in stats:
                rows.append((st, float(act.loc[pid, st]), s[st]))
    if raw:
        rows = [(st, y, float(crps(v, y)), float((v < y).mean() + rng.uniform() * (v == y).mean())) for st, y, v in rows]
        return pd.DataFrame(rows, columns=["stat", "y", "crps", "pit"])
    out = {}
    for st in dict.fromkeys(r[0] for r in rows):
        R = [(y, v) for s_, y, v in rows if s_ == st]
        pit = np.array([(v < y).mean() + rng.uniform() * (v == y).mean() for y, v in R])
        out[st] = {"n": len(R), "crps": round(float(np.mean([crps(v, y) for y, v in R])), 4),
                   "cov10": round(float((pit < .1).mean() * 100), 1), "cov50": round(float((pit < .5).mean() * 100), 1),
                   "cov90": round(float((pit < .9).mean() * 100), 1)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    cur = run()
    print(f"Regression sample {SEASON} weeks {WEEKS.start}-{WEEKS.stop - 1}, {SIMS} sims per game")
    print(f"{'stat':<9}{'n':>5}{'CRPS':>9}{'<p10':>7}{'<p50':>7}{'<p90':>7}   vs baseline")
    base = json.loads(BASELINE.read_text())["stats"] if BASELINE.exists() else {}
    flags = 0
    for st, r in cur.items():
        note = ""
        b = base.get(st)
        if b:
            d = r["crps"] / b["crps"] - 1
            moved = max(abs(r[k] - b[k]) for k in ("cov10", "cov50", "cov90"))
            bad = d > CRPS_TOL or moved > COV_TOL
            flags += bad
            note = f"CRPS {d:+.1%}, max coverage move {moved:.1f} pts" + ("   <-- DRIFT" if bad else "")
        print(f"{st:<9}{r['n']:>5}{r['crps']:>9.3f}{r['cov10']:>7.1f}{r['cov50']:>7.1f}{r['cov90']:>7.1f}   {note}")
    if a.save:
        BASELINE.write_text(json.dumps({"season": SEASON, "weeks": list(WEEKS), "sims": SIMS, "stats": cur}, indent=1) + "\n")
        print(f"Saved baseline to {BASELINE.name}")
        return 0
    if not base:
        print("No baseline yet: run with --save once the current model is the one you trust.")
        return 0
    print("DRIFT FOUND: check data joins and recent code changes before publishing picks." if flags else "No drift.")
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main())
