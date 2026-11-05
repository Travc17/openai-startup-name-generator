"""Model vs the books' CLOSING lines on a past season (MODEL_LAB_PROMPT.md sections 2 and 6).

    python hist_compare.py 2025 [--weeks 4-18] [--sims 4000] [--out reviews/hist_2025_model_vs_market.md]

Needs data/odds_hist/props_<season>.parquet (hist_props.py). For every player prop with a closing line:
* the model's walk-forward sims (live model, real starting QBs, closing spread for game script, route-role blend,
  RAW sims, no calibration map: the map was fit on seasons that include 2025),
* the books' consensus line (median across books) and no-vig P(over) at that line,
* the actual result.
Scores: median error (model median vs line), Brier and log loss of P(over), a model+market blend (weight fit on the
first half of the weeks, scored on the second), and a paper test of the bet rule (2% edge vs the best book price).
Caveat printed with the results: some fitted constants (absences, depth, returns, copula, game-script slope) used
2022-25 data, so 2025 is partly in-sample for those.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nfl  # noqa: E402
from nflmodel import calibration, data  # noqa: E402
from nflmodel.game import Player  # noqa: E402
from nflmodel.market import name_key  # noqa: E402

QB_STATS = {"pass_yds"}


def implied(a):
    a = np.asarray(a, float)
    return np.where(a < 0, -a / (-a + 100), 100 / (a + 100))


def payout(a):  # profit per 1 unit staked when it wins
    a = np.asarray(a, float)
    return np.where(a < 0, 100 / -a, a / 100)


def market_table(season):
    q = pd.read_parquet(HERE / "data" / "odds_hist" / f"props_{season}.parquet")
    q["k"] = q.player.map(name_key)
    rows = []
    for (gid, k, st), d in q.groupby(["game_id", "k", "stat"]):
        line = float(np.median(d.line))
        at = d[d.line == line]
        nv = []
        for _, b in at.groupby("book"):
            o, u = b[b.side == "over"].price, b[b.side == "under"].price
            if len(o) and len(u):
                io, iu = implied(o.iloc[0]), implied(u.iloc[0])
                nv.append(io / (io + iu))
        if not nv:
            continue
        ov, un = at[at.side == "over"].price, at[at.side == "under"].price
        rows.append({"game_id": gid, "week": int(d.week.iloc[0]), "k": k, "player": d.player.iloc[0], "stat": st,
                     "line": line, "p_mkt": float(np.mean(nv)), "n_books": len(nv),
                     "best_over": float(ov.max()) if len(ov) else np.nan, "best_under": float(un.max()) if len(un) else np.nan})
    return pd.DataFrame(rows)


def run_sims(m, season, weeks, sims, mk):
    gi_ = pd.read_parquet(data.DATA_DIR / f"pbp_{season}.parquet",
                          columns=["game_id", "home_team", "spread_line"]).drop_duplicates("game_id").set_index("game_id")
    P = m.qbm.p
    starter = (P[P.key // 100 == season].groupby(["game_id", "posteam", "passer_player_id"]).size().rename("att")
               .reset_index().sort_values("att").drop_duplicates(["game_id", "posteam"], keep="last")
               .set_index(["game_id", "posteam"]).passer_player_id)
    qb_act = P.groupby(["game_id", "passer_player_id"]).agg(pass_yds=("yards", "sum"))
    pl = data.load_players()[["gsis_id", "display_name"]].dropna()
    nm = dict(zip(pl.gsis_id, pl.display_name.map(name_key)))
    games = m.tg[(m.tg.key // 100 == season) & (m.tg.key % 100).isin(weeks)].drop_duplicates("game_id")
    games = games[games.game_id.isin(set(mk.game_id))]
    out = []
    for gi, g in enumerate(games.itertuples(index=False)):
        if g.game_id not in gi_.index:
            continue
        G = gi_.loc[g.game_id]
        act = m.pg[m.pg.game_id == g.game_id].set_index("pid")
        opp = {g.posteam: g.defteam, g.defteam: g.posteam}
        qbs = {t: starter.get((g.game_id, t)) for t in opp}
        if any(v is None for v in qbs.values()):
            continue
        want = set(mk[mk.game_id == g.game_id].k)
        roster, seen = [], set()
        for t in opp:
            cands = list(m.usage_leaders(t, g.key, min_targets=3, min_carries=6))
            cands += [p for p in act.index if nm.get(p) in want and act.loc[p, "posteam"] == t]   # market players who played
            for pid in cands:
                if pid in seen or pid not in act.index or pid not in m._pg_by:
                    continue
                seen.add(pid)
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
            sim = m.simulate(g.posteam, g.defteam, g.key, roster, n_sims=sims, seed=7000 + gi, exp_margin_a=em, qbs=qbs)
        except (ValueError, KeyError):
            continue
        for pid, s in sim["players"].items():
            k = nm.get(pid)
            if k not in want:
                continue
            for st, v in s.items():
                if st in QB_STATS:
                    if (g.game_id, pid) not in qb_act.index:
                        continue
                    y = float(qb_act.loc[(g.game_id, pid), st])
                elif st in ("rec", "rec_yds", "rush_yds", "rush_att") and pid in act.index:
                    y = float(act.loc[pid, st])
                else:
                    continue
                out.append({"game_id": g.game_id, "k": k, "stat": st, "sims": np.asarray(v, float), "y": y})
        if gi % 25 == 0:
            print(f"  simulated {gi + 1}/{len(games)} games", flush=True)
    return out


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def logloss(p, y):
    p = np.clip(p, 0.01, 0.99)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def main(a):
    w0, w1 = (int(x) for x in a.weeks.split("-"))
    weeks = range(w0, w1 + 1)
    mk = market_table(a.season)
    mk = mk[mk.week.isin(weeks)]
    m = nfl.build_model()
    S = pd.DataFrame(run_sims(m, a.season, weeks, a.sims, mk))
    df = mk.merge(S, on=["game_id", "k", "stat"])
    df["med"] = df.sims.map(np.median)
    df["p_mod"] = [float((s > ln).mean()) for s, ln in zip(df.sims, df.line)]
    cal = calibration.load()                                   # production map (fit on 2024-26: in-sample here)
    csims = [calibration.apply({st: s.copy()}, cal)[st] for s, st in zip(df.sims, df.stat)]
    df["p_cal"] = [float((s > ln).mean()) for s, ln in zip(csims, df.line)]
    df["over"] = (df.y > df.line).astype(float)
    df = df[df.y != df.line]                                  # pushes (whole-number lines) dropped
    lines = [f"# Model vs closing lines, {a.season} weeks {w0}-{w1}", "",
             f"{len(df)} player props matched ({df.game_id.nunique()} games). Raw sims ({a.sims} per game), no calibration map.",
             "Caveat: some fitted constants used 2022-25 data, so this is partly in-sample for the model (favors the model).", "",
             "## Accuracy (lower is better)", "",
             "| Stat | n | Median abs error: model | closing line | Brier: model | model calibrated | market | Log loss: model | market |",
             "|---|---|---|---|---|---|---|---|---|"]
    for st, d in list(df.groupby("stat")) + [("ALL", df)]:
        lines.append(f"| {st} | {len(d)} | {np.mean(np.abs(d.med - d.y)):.2f} | {np.mean(np.abs(d.line - d.y)):.2f} | "
                     f"{brier(d.p_mod, d.over):.4f} | {brier(d.p_cal, d.over):.4f} | {brier(d.p_mkt, d.over):.4f} | "
                     f"{logloss(d.p_mod, d.over):.4f} | {logloss(d.p_mkt, d.over):.4f} |")
    # where the model and the market disagree most, who was right?
    df["gap"] = df.p_mod - df.p_mkt
    lines += ["", "## When model and market disagree (model P(over) minus market's)", "",
              "| Gap | n | Over hit rate | Model said | Market said |", "|---|---|---|---|---|"]
    for lo, hi in ((-1, -.15), (-.15, -.05), (-.05, .05), (.05, .15), (.15, 1)):
        d = df[(df.gap >= lo) & (df.gap < hi)]
        if len(d):
            lines.append(f"| {lo:+.2f} to {hi:+.2f} | {len(d)} | {d.over.mean():.1%} | {d.p_mod.mean():.1%} | {d.p_mkt.mean():.1%} |")
    # blend: fit weight on the first half of the weeks, score on the second half
    mid = (w0 + w1) // 2
    fit, test = df[df.week <= mid], df[df.week > mid]
    ws = np.linspace(0, 1, 21)
    w_best = ws[int(np.argmin([brier(w * fit.p_mod + (1 - w) * fit.p_mkt, fit.over) for w in ws]))]
    wm = ws[int(np.argmin([np.mean(np.abs(w * fit.med + (1 - w) * fit.line - fit.y)) for w in ws]))]
    lines += ["", f"## Blend (weight on the MODEL fit on weeks {w0}-{mid}, scored on weeks {mid + 1}-{w1})", "",
              f"* Probability blend: model weight {w_best:.2f}. Held-out Brier: model {brier(test.p_mod, test.over):.4f}, "
              f"market {brier(test.p_mkt, test.over):.4f}, blend {brier(w_best * test.p_mod + (1 - w_best) * test.p_mkt, test.over):.4f}.",
              f"* Median blend: model weight {wm:.2f}. Held-out median abs error: model {np.mean(np.abs(test.med - test.y)):.2f}, "
              f"line {np.mean(np.abs(test.line - test.y)):.2f}, blend {np.mean(np.abs(wm * test.med + (1 - wm) * test.line - test.y)):.2f}."]
    # paper bets: model edge >= min_edge vs the best book price on that side at the consensus line
    bets = []
    for r in df.itertuples():
        for side, p, price, win in (("over", r.p_mod, r.best_over, r.over), ("under", 1 - r.p_mod, r.best_under, 1 - r.over)):
            if np.isnan(price):
                continue
            edge = p - float(implied(price))
            if edge >= a.min_edge:
                bets.append({"stat": r.stat, "side": side, "edge": edge, "win": win, "profit": float(payout(price)) if win else -1.0,
                             "mkt_agrees": (r.p_mkt > 0.5) == (side == "over")})
    B = pd.DataFrame(bets)
    lines += ["", f"## Paper bets: model edge >= {a.min_edge:.0%} vs the best book price (flat 1 unit, no Kalshi fee)", ""]
    if B.empty:
        lines.append("No bets qualified.")
    else:
        lines += ["| Group | Bets | Win % | ROI |", "|---|---|---|---|"]
        for lab, d in [("ALL", B)] + [(f"{s} {sd}", d) for (s, sd), d in B.groupby(["stat", "side"])] + \
                      [("edge 2-5%", B[B.edge < .05]), ("edge 5-10%", B[(B.edge >= .05) & (B.edge < .10)]), ("edge 10%+", B[B.edge >= .10])]:
            if len(d):
                lines.append(f"| {lab} | {len(d)} | {d.win.mean():.1%} | {d.profit.sum() / len(d):+.1%} |")
    txt = "\n".join(lines) + "\n"
    print(txt)
    if a.out:
        Path(a.out).write_text(txt)
        print(f"saved -> {a.out}")
    keep = df.drop(columns=["sims"])
    keep.to_parquet(HERE / "data" / "odds_hist" / f"compare_{a.season}.parquet")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("season", type=int)
    ap.add_argument("--weeks", default="4-18")
    ap.add_argument("--sims", type=int, default=4000)
    ap.add_argument("--min-edge", type=float, default=0.02)
    ap.add_argument("--out")
    main(ap.parse_args())
