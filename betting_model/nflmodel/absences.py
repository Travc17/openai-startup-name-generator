"""How do targets and carries really move when a key player sits?

For every team game where a regular (in 2+ of the team's last 3 games, with a
real role) is missing, compare each remaining regular's ACTUAL share that game
to his PROJECTED share (model inputs, no adjustment). That tells us how much of
the vacated share teammates really absorb.

The adjustment tested is a partial version of proportional redistribution:
    boosted share = projected share * (1 + k * (1 / (1 - vacated share) - 1))
k = 0 means no bump, k = 1 means teammates absorb it all in proportion.
k is fitted separately for targets and carries, and for first games missed vs
continuing absences (when the player has already been out, his teammates'
recent shares partly reflect it already, so a full bump double counts).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .game import GameModel, Player

ABSENCE_FILE = Path(__file__).with_name("absences.json")
ROLE = {"t": ("targets", "t_share", 0.12), "c": ("rush_att", "c_share", 0.25)}


def collect(model: GameModel, seasons: list[int], min_week: int = 4) -> pd.DataFrame:
    rows = []
    tg = model.tg[(model.tg.key // 100).isin(seasons) & (model.tg.key % 100 >= min_week)]
    for g in tg.itertuples(index=False):
        team, opp, key = g.posteam, g.defteam, g.key
        prev_keys = sorted(model.tg[(model.tg.posteam == team) & (model.tg.key < key)].key.unique())[-3:]
        if len(prev_keys) < 3:
            continue
        hist = model.pg[(model.pg.posteam == team) & model.pg.key.isin(prev_keys)]
        agg = hist.groupby("pid").agg(n=("key", "size"), t=("t_share", "mean"), c=("c_share", "mean"),
                                      last=("key", "max"))
        regulars = agg[(agg.n >= 2) & ((agg.t >= 0.12) | (agg.c >= 0.25))]
        played = set(model.pg[(model.pg.game_id == g.game_id) & (model.pg.posteam == team)].pid)
        missing = [p for p in regulars.index if p not in played]
        present = [p for p in regulars.index if p in played]
        if not present:
            continue
        actual = model.pg[(model.pg.game_id == g.game_id)].set_index("pid")
        inputs = {}
        for p in present + missing:
            try:
                inputs[p] = model.player_inputs(Player(p, team), opp, key)
            except ValueError:
                pass
        for kind, (cnt, share_col, _) in ROLE.items():
            sk = "t_share" if kind == "t" else "c_share"
            vac = sum(inputs[p][sk] for p in missing if p in inputs)
            first = any(regulars.loc[p, "last"] == prev_keys[-1] for p in missing)
            team_total = g.targets if kind == "t" else g.rushes
            for p in present:
                if p not in inputs or inputs[p][sk] < 0.05:
                    continue
                rows.append({"key": key, "team": team, "kind": kind, "pid": p,
                             "pos": inputs[p]["pos"], "pred": inputs[p][sk], "vacated": vac,
                             "first_miss": bool(first) if vac > 0 else None,
                             "actual": actual.loc[p, cnt] / max(team_total, 1), "team_total": team_total})
    return pd.DataFrame(rows)


def fit(df: pd.DataFrame) -> dict:
    """Least squares k per (kind, first_miss), weighting by team volume."""
    out = {}
    base = df[df.vacated == 0]
    for kind in ("t", "c"):
        b = base[base.kind == kind]
        # calibration with nobody missing (should be ~1.0)
        out[f"{kind}_baseline_ratio"] = round(float((b.actual * b.team_total).sum() / (b.pred * b.team_total).sum()), 4)
        for first in (True, False):
            d = df[(df.kind == kind) & (df.vacated > 0.05) & (df.first_miss == first)]
            if len(d) < 50:
                continue
            boost = 1 / (1 - d.vacated.clip(upper=0.6)) - 1
            # actual = pred * (1 + k * boost) -> (actual - pred) = k * pred * boost
            x, y, w = d.pred * boost, d.actual - d.pred * out[f"{kind}_baseline_ratio"], d.team_total
            k = float((w * x * y).sum() / (w * x * x).sum())
            out[f"{kind}_{'first' if first else 'continuing'}_k"] = round(k, 3)
            out[f"{kind}_{'first' if first else 'continuing'}_n"] = int(len(d))
            for name, kk in (("none", 0.0), ("proportional", 1.0), ("fitted", k)):
                pred = d.pred * out[f"{kind}_baseline_ratio"] * (1 + kk * boost)
                out[f"{kind}_{'first' if first else 'continuing'}_ratio_{name}"] = round(
                    float((d.actual * w).sum() / (pred * w).sum()), 3)
    return out


def save(params: dict, seasons: list[int]) -> None:
    ABSENCE_FILE.write_text(json.dumps({"fitted_on_seasons": seasons, **params}, indent=2) + "\n")


def load() -> dict:
    return json.loads(ABSENCE_FILE.read_text()) if ABSENCE_FILE.exists() else {}
