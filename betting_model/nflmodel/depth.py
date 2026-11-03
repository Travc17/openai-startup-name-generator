"""Depth chart role changes.

The share model learns roles from past games, so it lags when a player is
promoted to starter (or demoted) on the depth chart. This measures, from real
games, how a player's ACTUAL share compares to the model's projection when his
starter status changed since the team's previous game:

    promoted : not a starter last game, starter now
    demoted  : starter last game, not now
    same     : no change (baseline, should be ~1.0)

Fitted multipliers (actual / projected) are applied to target and carry share.
Depth charts come only from the chart published on or before game day.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .game import GameModel, Player

DEPTH_FILE = Path(__file__).with_name("depth.json")


def status_table(model: GameModel, depth: pd.DataFrame) -> pd.DataFrame:
    """Starter status now and at the team's previous game, per player game."""
    d = depth.merge(model.tg[["game_id", "posteam", "key"]].drop_duplicates(),
                    left_on=["game_id", "team"], right_on=["game_id", "posteam"])
    d = d.sort_values(["team", "key"])
    prev_key = {}
    for team, g in model.tg.sort_values("key").groupby("posteam"):
        ks = g.key.unique()
        prev_key.update({(team, k): p for p, k in zip(ks[:-1], ks[1:])})
    d["prev_key"] = [prev_key.get((t, k)) for t, k in zip(d.team, d.key)]
    prev = d[["team", "key", "gsis_id", "starter"]].rename(columns={"key": "prev_key", "starter": "was_starter"})
    d = d.merge(prev, on=["team", "prev_key", "gsis_id"], how="left")
    d["was_starter"] = d.was_starter.fillna(False).astype(bool)
    d["change"] = np.select([d.starter & ~d.was_starter, ~d.starter & d.was_starter], ["promoted", "demoted"], "same")
    return d


def collect(model: GameModel, depth: pd.DataFrame, seasons: list[int], same_sample: int = 3000,
            seed: int = 5) -> pd.DataFrame:
    st = status_table(model, depth)
    st = st[(st.key // 100).isin(seasons) & (st.key % 100 >= 3)]
    st = st[st.pos.isin(["WR", "TE", "RB"])]
    changed = st[st.change != "same"]
    same = st[st.change == "same"].sample(min(same_sample, (st.change == "same").sum()), random_state=seed)
    rows = []
    for r in pd.concat([changed, same]).itertuples(index=False):
        act = model.pg[(model.pg.game_id == r.game_id) & (model.pg.pid == r.gsis_id)]
        if act.empty:
            continue  # inactive or did not play
        a = act.iloc[0]
        try:
            inp = model.player_inputs(Player(r.gsis_id, r.team), a.defteam, int(r.key))
        except (ValueError, KeyError):
            continue
        rows.append({"season": int(r.key // 100), "pos": r.pos, "change": r.change,
                     "pred_t": inp["t_share"], "act_t": a.t_share, "team_t": a.team_targets,
                     "pred_c": inp["c_share"], "act_c": a.c_share, "team_c": a.team_rushes})
    return pd.DataFrame(rows)


def fit(df: pd.DataFrame, min_n: int = 40) -> dict:
    """Volume weighted actual/projected share ratio by change type (and RB carries separately)."""
    out = {}
    for change, g in df.groupby("change"):
        out[f"t_{change}"] = round(float((g.act_t * g.team_t).sum() / (g.pred_t * g.team_t).sum()), 3)
        out[f"t_{change}_n"] = int(len(g))
        rb = g[g.pos == "RB"]
        if len(rb) >= min_n:
            out[f"c_{change}"] = round(float((rb.act_c * rb.team_c).sum() / (rb.pred_c * rb.team_c).sum()), 3)
            out[f"c_{change}_n"] = int(len(rb))
    return out


def save(params: dict, seasons: list[int]) -> None:
    DEPTH_FILE.write_text(json.dumps({"fitted_on_seasons": seasons, **params}, indent=2) + "\n")


def load() -> dict:
    return json.loads(DEPTH_FILE.read_text()) if DEPTH_FILE.exists() else {}


def multipliers(params: dict, change: str) -> tuple[float, float]:
    """Share multipliers relative to an unchanged role (so baseline drift cancels)."""
    if change == "same" or not params:
        return 1.0, 1.0
    t = params.get(f"t_{change}", 1.0) / params.get("t_same", 1.0)
    c = params.get(f"c_{change}", 1.0) / params.get("c_same", 1.0)
    return t, c


def current_status(depth_raw: pd.DataFrame, team: str, date: str, prev_date: str) -> dict[str, tuple[bool, bool, int, str]]:
    """Live lookup from daily snapshots: {gsis_id: (starter_now, starter_prev, rank, pos)}."""
    from .data import STARTERS, SKILL
    d = depth_raw[(depth_raw.team == team) & depth_raw.pos_abb.isin(SKILL) & depth_raw.gsis_id.notna()].copy()
    d["date"] = d.dt.str[:10]

    def snap(on):
        dates = sorted(x for x in d.date.unique() if x <= on)
        if not dates:
            return {}
        s = d[d.date == dates[-1]].drop_duplicates("gsis_id")
        return {r.gsis_id: (r.pos_rank <= STARTERS.get(r.pos_abb, 1), int(r.pos_rank), r.pos_abb) for r in s.itertuples()}
    now, prev = snap(date), snap(prev_date)
    return {g: (v[0], prev.get(g, (False,))[0], v[1], v[2]) for g, v in now.items()}
