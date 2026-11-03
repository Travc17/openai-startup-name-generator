"""Walk forward backtest of the joint game model (every projection uses only prior games).

No free historical prop lines exist, so this measures CALIBRATION, the property
alternate lines and parlays depend on:

  1. Alternate line calibration, per stat. For each player game we set three
     half point lines at the model's own 25th, 50th, and 75th percentiles and
     compare the model's P(over) to how often the over actually hit.
  2. Parlay correlation. For every pair of players in the same game, "both go
     over their median line" is scored three ways:
       * independent : multiplying single legs (how naive parlay math works)
       * engine      : the simulation's shared volume structure only
       * copula      : engine plus correlations fitted on OTHER seasons
     and compared to how often it actually happened.

`fit_copula` learns pair correlations from the normal scores of each player's
actual result inside his own predicted distribution (randomized PIT). Fit on
training seasons, then evaluate on held out seasons.
"""
from __future__ import annotations

import copy
import json
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import norm

from .game import COPULA_FILE, GameModel, Player, apply_copula, main_kind, main_stat, pair_kind


def _half(x: float) -> float:
    return float(np.floor(x)) + 0.5


def _pit_z(sims: np.ndarray, actual: float, rng: np.random.Generator) -> float:
    u = (sims < actual).mean() + rng.uniform() * (sims == actual).mean()
    return float(norm.ppf(np.clip(u, 1e-4, 1 - 1e-4)))


def crps(sims: np.ndarray, y: float) -> float:
    """Continuous ranked probability score: error of the whole predicted distribution
    (lower is better). Equals absolute error when the prediction is a single number."""
    x = np.sort(sims[:2000])
    n = len(x)
    return float(np.abs(x - y).mean() - (2 * np.arange(1, n + 1) - n - 1) @ x / n ** 2)


def run(model: GameModel, seasons: list[int], rho: dict[str, float] | None = None, min_week: int = 4,
        n_sims: int = 4000, limit_games: int | None = None, seed: int = 11,
        truth: GameModel | None = None, adjust=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """truth: model whose game table defines who played and their actual stats (use the
    snap count version so every configuration is graded on the same games).
    adjust: optional fn(model, Player, game_id, key) -> Player, e.g. depth chart multipliers."""
    rng = np.random.default_rng(seed)
    truth = truth or model
    games = model.tg[(model.tg.key // 100).isin(seasons) & (model.tg.key % 100 >= min_week)]
    games = games.drop_duplicates("game_id")
    marg, pairs = [], []
    for gi, g in enumerate(games.itertuples(index=False)):
        if limit_games and gi >= limit_games:
            break
        actual = truth.pg[truth.pg.game_id == g.game_id].set_index("pid")
        roster = []
        for team in (g.posteam, g.defteam):
            for pid in truth.usage_leaders(team, g.key, min_targets=5, min_carries=8):
                if pid in actual.index and pid in model._pg_by:  # played (inactives are known pregame)
                    pl = Player(pid, team)
                    roster.append(adjust(model, pl, g.game_id, g.key) if adjust else pl)
        if len(roster) < 2:
            continue
        try:
            sim = model.simulate(g.posteam, g.defteam, g.key, roster, n_sims=n_sims, seed=int(rng.integers(1e9)), rho={})
        except (ValueError, KeyError):
            continue
        sim_c = apply_copula(copy.deepcopy(sim), rho, rng) if rho else None

        legs = []
        for p in roster:
            s, info, a = sim["players"][p.pid], sim["info"][p.pid], actual.loc[p.pid]
            kinds = (["rec", "rec_yds"] if info["t_share"] >= 0.12 else []) + \
                    (["rush_att", "rush_yds"] if info["c_share"] >= 0.25 else [])
            for stat in kinds:
                for q in (0.25, 0.5, 0.75):
                    line = _half(np.quantile(s[stat], q))
                    marg.append({"stat": stat, "q": q, "p_over": float((s[stat] > line).mean()),
                                 "hit": float(a[stat] > line),
                                 "crps": crps(s[stat], a[stat]) if q == 0.5 else np.nan})
            if not kinds:
                continue
            kind = main_kind(s)
            stat = main_stat(kind)
            line = _half(np.median(s[stat]))
            legs.append({"p": p, "kind": kind, "line": line, "stat": stat,
                         "over": s[stat] > line,
                         "over_c": (sim_c["players"][p.pid][stat] > line) if sim_c else None,
                         "hit": float(a[stat] > line), "z": _pit_z(s[stat], a[stat], rng)})
        for l1, l2 in combinations(legs, 2):
            row = {"kind": pair_kind(l1["p"].team, l1["kind"], l2["p"].team, l2["kind"]),
                   "independent": float(l1["over"].mean() * l2["over"].mean()),
                   "engine": float((l1["over"] & l2["over"]).mean()),
                   "actual": l1["hit"] * l2["hit"], "z1": l1["z"], "z2": l2["z"]}
            if sim_c:
                row["copula"] = float((l1["over_c"] & l2["over_c"]).mean())
            pairs.append(row)
    return pd.DataFrame(marg), pd.DataFrame(pairs)


def fit_copula(pairs: pd.DataFrame, seasons: list[int], min_n: int = 100) -> dict[str, float]:
    rho = {}
    for kind, g in pairs.groupby("kind"):
        if len(g) >= min_n:
            r = np.corrcoef(g.z1, g.z2)[0, 1]
            rho[kind] = round(float(r), 4)
    COPULA_FILE.write_text(json.dumps({"fitted_on_seasons": seasons, "n_pairs": len(pairs),
                                       "rho": rho}, indent=2) + "\n")
    return rho


def report(marg: pd.DataFrame, pairs: pd.DataFrame) -> str:
    out = ["ALTERNATE LINE CALIBRATION (model P(over) vs actual over rate)",
           f"{'stat':>9} {'line at':>8} {'n':>6} {'model':>7} {'actual':>7}"]
    for (stat, q), g in marg.groupby(["stat", "q"]):
        out.append(f"{stat:>9} {'q' + str(int(q * 100)):>8} {len(g):>6} {g.p_over.mean():>7.1%} {g.hit.mean():>7.1%}")
    sc = marg.dropna(subset=["crps"]).groupby("stat").crps.mean()
    out.append("\nCRPS, whole distribution error (lower is better): " + ", ".join(f"{k} {v:.3f}" for k, v in sc.items()))
    cols = ["independent", "engine"] + (["copula"] if "copula" in pairs else [])
    out.append("\nPARLAY CORRELATION CHECK (both players over their median line)")
    out.append(f"{'pair type':>16} {'n':>6} " + " ".join(f"{c:>11}" for c in cols) + f" {'actual':>8}")
    for kind, g in pairs.groupby("kind"):
        if len(g) < 100:
            continue
        out.append(f"{kind:>16} {len(g):>6} " + " ".join(f"{g[c].mean():>11.1%}" for c in cols) + f" {g.actual.mean():>8.1%}")
    out.append("  Brier (lower is better): " + ", ".join(
        f"{c} {((pairs[c] - pairs.actual) ** 2).mean():.5f}" for c in cols))
    return "\n".join(out)
