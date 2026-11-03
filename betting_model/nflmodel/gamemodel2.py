"""Game model v2 experiments: pass/rush split, QB-specific ratings, tunable recency.
Strict protocol: tune on validation seasons only, then score the locked test set once."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DATA_DIR

COLS = ["season", "season_type", "week", "game_id", "home_team", "away_team", "posteam", "defteam", "play_type",
        "epa", "qb_dropback", "passer_player_id", "home_score", "away_score", "result", "total", "spread_line", "total_line"]


def load(seasons):
    d = pd.concat([pd.read_parquet(DATA_DIR / f"pbp_{y}.parquet", columns=COLS) for y in seasons], ignore_index=True)
    d = d[(d.season_type == "REG") & d.epa.notna() & d.play_type.isin(["pass", "run"])]
    games = d.drop_duplicates("game_id")[["game_id", "season", "week", "home_team", "away_team", "home_score",
                                          "away_score", "result", "total", "spread_line", "total_line"]].copy()
    games["key"] = games.season * 100 + games.week
    d["is_pass"] = d.qb_dropback == 1
    tg = d.groupby(["game_id", "posteam", "defteam"]).apply(lambda x: pd.Series({
        "pass_epa": x.loc[x.is_pass, "epa"].mean(), "rush_epa": x.loc[~x.is_pass, "epa"].mean(),
        "n_pass": x.is_pass.sum(), "n_rush": (~x.is_pass).sum()}), include_groups=False).reset_index()
    qb = d[d.is_pass & d.passer_player_id.notna()].groupby(["game_id", "posteam", "passer_player_id"]).epa.agg(["mean", "size"]).reset_index()
    starter = qb.sort_values("size").drop_duplicates(["game_id", "posteam"], keep="last")
    tg = tg.merge(starter.rename(columns={"passer_player_id": "qb", "mean": "qb_epa", "size": "qb_n"}), on=["game_id", "posteam"], how="left")
    pts = pd.concat([games.assign(team=games.home_team, pts=games.home_score), games.assign(team=games.away_team, pts=games.away_score)])
    tg = tg.merge(pts[["game_id", "team", "pts"]], left_on=["game_id", "posteam"], right_on=["game_id", "team"]).drop(columns="team")
    tg = tg.merge(games[["game_id", "key"]], on="game_id")
    return games.sort_values("key").reset_index(drop=True), tg.sort_values("key").reset_index(drop=True)


def build(games, tg, hl=8.0, carry=0.6, qb_mode=False, qb_hl=12.0, qb_prior=-0.05, qb_k=4.0, starters=None):
    """Sequential pregame ratings (opponent adjusted). Returns games with feature columns."""
    METRICS = ["pass", "rush", "pts"]
    hist = {}      # team -> list of (key, side, metric dict)
    qbh = {}       # qb -> list of (key, adjusted dropback epa)
    lg_pts = 22.0

    def team_rating(team, key):
        h = [x for x in hist.get(team, []) if x[0] < key][-60:]
        out = {}
        for side in ("off", "def"):
            hh = [x for x in h if x[1] == side]
            if not hh:
                out.update({f"{side}_{m}": 0.0 for m in METRICS}); continue
            keys = np.array([x[0] for x in hh])
            w = 0.5 ** (np.arange(len(hh))[::-1] / hl) * carry ** (keys.max() // 100 - keys // 100)
            s = w.sum() / (w.sum() + 3.0)
            for m in METRICS:
                v = np.array([x[2][m] for x in hh]); ok = ~np.isnan(v)
                out[f"{side}_{m}"] = float(s * (w[ok] @ v[ok]) / w[ok].sum()) if ok.any() else 0.0
        return out

    def qb_rating(q, key):
        h = [x for x in qbh.get(q, []) if x[0] < key][-40:]
        if not h:
            return qb_prior
        keys = np.array([x[0] for x in h]); v = np.array([x[1] for x in h])
        w = 0.5 ** (np.arange(len(h))[::-1] / qb_hl) * carry ** (keys.max() // 100 - keys // 100)
        return float((w @ v + qb_k * qb_prior) / (w.sum() + qb_k))

    by_game = {g: v for g, v in tg.groupby("game_id")}
    feats = []
    for g in games.itertuples(index=False):
        R = {g.home_team: team_rating(g.home_team, g.key), g.away_team: team_rating(g.away_team, g.key)}
        rows = by_game.get(g.game_id)
        qbs = dict((starters or {}).get(g.game_id, {}))
        if rows is not None:
            for r in rows.itertuples(index=False):
                qbs[r.posteam] = r.qb if isinstance(r.qb, str) else None
        f = {"game_id": g.game_id}
        for side, team, opp in (("h", g.home_team, g.away_team), ("a", g.away_team, g.home_team)):
            o, d = R[team], R[opp]
            pass_off = o["off_pass"]
            if qb_mode and qbs.get(team):
                pass_off = qb_rating(qbs[team], g.key)   # starting QB's own dropback rating (starter known pregame)
            f[f"{side}_pass"] = pass_off + d["def_pass"]
            f[f"{side}_rush"] = o["off_rush"] + d["def_rush"]
            f[f"{side}_pts"] = o["off_pts"] + d["def_pts"]
        feats.append(f)
        if rows is None:
            continue
        for r in rows.itertuples(index=False):
            o, d = R[r.posteam], R[r.defteam]
            hist.setdefault(r.posteam, []).append((g.key, "off", {"pass": r.pass_epa - d["def_pass"], "rush": r.rush_epa - d["def_rush"], "pts": r.pts - lg_pts - d["def_pts"]}))
            hist.setdefault(r.defteam, []).append((g.key, "def", {"pass": r.pass_epa - o["off_pass"], "rush": r.rush_epa - o["off_rush"], "pts": r.pts - lg_pts - o["off_pts"]}))
            if isinstance(r.qb, str) and r.qb_n >= 10:
                qbh.setdefault(r.qb, []).append((g.key, r.qb_epa - d["def_pass"]))
    F = pd.DataFrame(feats)
    out = games.merge(F, on="game_id")
    for m in ("pass", "rush", "pts"):
        out[f"m_{m}"] = out[f"h_{m}"] - out[f"a_{m}"]
        out[f"t_{m}"] = out[f"h_{m}"] + out[f"a_{m}"]
    return out


def evaluate(df, train_mask, test_mask, cols_m, cols_t):
    tr, te = df[train_mask & df.result.notna()], df[test_mask & df.result.notna()]
    Xm = np.column_stack([np.ones(len(tr)), tr[cols_m]]); bm, *_ = np.linalg.lstsq(Xm, tr.result, rcond=None)
    Xt = np.column_stack([np.ones(len(tr)), tr[cols_t]]); bt, *_ = np.linalg.lstsq(Xt, tr.total, rcond=None)
    pm = np.column_stack([np.ones(len(te)), te[cols_m]]) @ bm
    pt = np.column_stack([np.ones(len(te)), te[cols_t]]) @ bt
    def ats(pred, line, actual, thr):
        diff = pred - line; ok = (np.abs(diff) >= thr) & (actual != line)
        return float((np.sign(diff[ok]) == np.sign((actual - line)[ok])).mean()), int(ok.sum())
    return {"mae_m": float(np.abs(pm - te.result).mean()), "mae_mkt": float(np.abs(te.spread_line - te.result).mean()),
            "mae_t": float(np.abs(pt - te.total).mean()), "mae_tmkt": float(np.abs(te.total_line - te.total).mean()),
            **{f"ats{t}": ats(pm, te.spread_line.to_numpy(), te.result.to_numpy(), t) for t in (0, 2, 3)},
            **{f"ou{t}": ats(pt, te.total_line.to_numpy(), te.total.to_numpy(), t) for t in (0, 2, 3)}}
