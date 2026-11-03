"""Game score model: spread, total, team totals, moneyline.

Team strength comes from opponent adjusted efficiency (EPA per play and
points per drive style scoring), recency weighted, so a defense's quality is
built in as the matchup: home expected offense = home offense + away defense
allowed, and vice versa.

    expected home margin = a + b * (home side strength - away side strength)
    expected total       = c + d * (home side strength + away side strength)

Coefficients are fitted walk forward (only seasons before the one predicted).
The score distribution is simulated with the model's historical residual
spread, and graded against REAL closing spreads and totals from nflverse.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import DATA_DIR

COLS = ["season", "season_type", "week", "game_id", "home_team", "away_team", "posteam", "defteam",
        "play_type", "epa", "success", "home_score", "away_score", "result", "total", "spread_line", "total_line"]


def load_games(seasons: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games, team_games). team_games has offensive EPA/play, success, points per game."""
    frames = [pd.read_parquet(DATA_DIR / f"pbp_{y}.parquet", columns=COLS) for y in seasons]
    d = pd.concat(frames, ignore_index=True)
    d = d[d.season_type == "REG"]
    games = d.drop_duplicates("game_id")[["game_id", "season", "week", "home_team", "away_team", "home_score",
                                          "away_score", "result", "total", "spread_line", "total_line"]].copy()
    games["key"] = games.season * 100 + games.week
    plays = d[d.play_type.isin(["pass", "run"]) & d.epa.notna()]
    tg = plays.groupby(["game_id", "posteam", "defteam"]).agg(epa=("epa", "mean"), sr=("success", "mean"),
                                                               n=("epa", "size")).reset_index()
    pts = pd.concat([games.assign(team=games.home_team, pts=games.home_score),
                     games.assign(team=games.away_team, pts=games.away_score)])[["game_id", "team", "pts"]]
    tg = tg.merge(pts, left_on=["game_id", "posteam"], right_on=["game_id", "team"]).drop(columns="team")
    tg = tg.merge(games[["game_id", "key"]], on="game_id")
    return games.sort_values("key").reset_index(drop=True), tg.sort_values("key").reset_index(drop=True)


@dataclass
class RatingConfig:
    half_life: float = 8.0
    season_carryover: float = 0.6
    max_games: int = 30


def ratings(games: pd.DataFrame, tg: pd.DataFrame, cfg: RatingConfig | None = None) -> pd.DataFrame:
    """Pregame, opponent adjusted ratings for both teams of every game.
    off = EPA/play the offense generates, def = EPA/play the defense allows (higher = worse),
    each adjusted for the opponent's pregame rating. Same for points (offp/defp)."""
    cfg = cfg or RatingConfig()
    hist: dict[str, list] = {}   # team -> list of (key, off_adj, def_adj, offp_adj, defp_adj)
    lg = {"epa": 0.0, "pts": 22.0}

    def rate(team, key):
        h = [x for x in hist.get(team, []) if x[0] < key][-cfg.max_games:]
        if not h:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        keys = np.array([x[0] for x in h])
        w = 0.5 ** (np.arange(len(h))[::-1] / cfg.half_life) * cfg.season_carryover ** (keys.max() // 100 - keys // 100)
        arr = np.array([x[1:] for x in h])
        shrink = w.sum() / (w.sum() + 3.0)  # 3 pseudo games of league average
        return (*(shrink * (w @ arr) / w.sum()), float(w.sum()))

    out = []
    by_game = {g: v for g, v in tg.groupby("game_id")}
    for g in games.itertuples(index=False):
        rh, ra = rate(g.home_team, g.key), rate(g.away_team, g.key)
        out.append({"game_id": g.game_id, "h_off": rh[0], "h_def": rh[1], "h_offp": rh[2], "h_defp": rh[3], "h_w": rh[4],
                    "a_off": ra[0], "a_def": ra[1], "a_offp": ra[2], "a_defp": ra[3], "a_w": ra[4]})
        rows = by_game.get(g.game_id)
        if rows is None:
            continue
        pre = {g.home_team: rh, g.away_team: ra}
        for r in rows.itertuples(index=False):
            o, dfn = pre[r.posteam], pre[r.defteam]
            # offense value adjusted for the defense it faced, defense value adjusted for the offense it faced
            hist.setdefault(r.posteam, []).append([g.key, r.epa - dfn[1], 0.0, r.pts - lg["pts"] - dfn[3], 0.0])
            hist.setdefault(r.defteam, []).append([g.key, 0.0, r.epa - o[0], 0.0, r.pts - lg["pts"] - o[2]])
    # each team game appended two rows (one as offense, one as defense): merge them per key
    return games.merge(pd.DataFrame(out), on="game_id")


def features(r: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=r.index)
    h_exp = r.h_off + r.a_def          # home offense vs away defense
    a_exp = r.a_off + r.h_def
    hp_exp = r.h_offp + r.a_defp
    ap_exp = r.a_offp + r.h_defp
    f["m_epa"], f["m_pts"] = h_exp - a_exp, hp_exp - ap_exp
    f["t_epa"], f["t_pts"] = h_exp + a_exp, hp_exp + ap_exp
    return f


def fit(r: pd.DataFrame, train: pd.Series) -> dict:
    f = features(r)
    X = np.column_stack([np.ones(train.sum()), f.loc[train, ["m_epa", "m_pts"]]])
    bm, *_ = np.linalg.lstsq(X, r.loc[train, "result"], rcond=None)
    Xt = np.column_stack([np.ones(train.sum()), f.loc[train, ["t_epa", "t_pts"]]])
    bt, *_ = np.linalg.lstsq(Xt, r.loc[train, "total"], rcond=None)
    pm, pt = X @ bm, Xt @ bt
    resid_m, resid_t = r.loc[train, "result"] - pm, r.loc[train, "total"] - pt
    return {"bm": bm, "bt": bt, "sd_m": float(resid_m.std()), "sd_t": float(resid_t.std()),
            "rho": float(np.corrcoef(resid_m, resid_t)[0, 1])}


def predict(r: pd.DataFrame, params: dict) -> pd.DataFrame:
    f = features(r)
    out = r.copy()
    out["pred_margin"] = params["bm"][0] + f[["m_epa", "m_pts"]].to_numpy() @ params["bm"][1:]
    out["pred_total"] = params["bt"][0] + f[["t_epa", "t_pts"]].to_numpy() @ params["bt"][1:]
    return out


def simulate(pred_margin: float, pred_total: float, params: dict, n: int = 25000, seed: int = 7) -> dict:
    """Integer home/away scores from correlated normal margin and total."""
    rng = np.random.default_rng(seed)
    cov = [[params["sd_m"] ** 2, params["rho"] * params["sd_m"] * params["sd_t"]],
           [params["rho"] * params["sd_m"] * params["sd_t"], params["sd_t"] ** 2]]
    m, t = rng.multivariate_normal([pred_margin, pred_total], cov, n).T
    home = np.clip(np.rint((t + m) / 2), 0, None)
    away = np.clip(np.rint((t - m) / 2), 0, None)
    return {"home": home, "away": away, "margin": home - away, "total": home + away}


# ---------------- market anchored distribution ----------------
def market_residuals(games: pd.DataFrame, max_season: int) -> np.ndarray:
    """Joint (margin, total) misses vs the closing line from completed games before max_season."""
    g = games[(games.season < max_season) & games.result.notna() & games.spread_line.notna() & games.total_line.notna()]
    return np.column_stack([g.result - g.spread_line, g.total - g.total_line])


def market_simulate(spread_line: float, total_line: float, resid: np.ndarray, n: int = 25000, seed: int = 7) -> dict:
    """spread_line = expected HOME margin (nflverse convention: home -3 favorite => +3).
    Resample real (margin, total) misses around the market's numbers, then snap to whole points."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(resid), n)
    m = np.rint(spread_line + resid[idx, 0] + rng.uniform(-0.25, 0.25, n))
    t = np.rint(total_line + resid[idx, 1] + rng.uniform(-0.25, 0.25, n))
    t = np.maximum(t, np.abs(m))
    t = np.where((t + m) % 2 == 1, t + 1, t)  # home and away scores must be whole numbers
    home, away = (t + m) / 2, (t - m) / 2
    return {"home": home, "away": away, "margin": m, "total": t}
