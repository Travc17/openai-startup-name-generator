"""First games back from a long absence (e.g. IR, ACL).

The share model projects a returning player from his pre-injury role. This
measures, from real returns, how his ACTUAL share compares to that projection
in his 1st and 2nd games back after missing `min_missed` or more team games.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .game import GameModel, Player

RETURN_FILE = Path(__file__).with_name("returns.json")


def collect(model: GameModel, seasons: list[int], min_missed: int = 4) -> pd.DataFrame:
    team_keys = {t: np.sort(g.key.unique()) for t, g in model.tg.groupby("posteam")}
    rows = []
    for pid, h in model._pg_by.items():
        h = h.sort_values("key")
        keys, teams = h.key.to_numpy(), h.posteam.to_numpy()
        for i in range(1, len(h)):
            tk = team_keys[teams[i]]
            missed = int(((tk > keys[i - 1]) & (tk < keys[i])).sum())
            if missed < min_missed or keys[i] // 100 not in seasons:
                continue
            for j, nth in ((i, 1), (i + 1, 2)):
                if j >= len(h) or (nth == 2 and keys[j] // 100 != keys[i] // 100):
                    continue
                r = h.iloc[j]
                try:
                    inp = model.player_inputs(Player(pid, r.posteam), r.defteam, int(r.key))
                except (ValueError, KeyError):
                    continue
                if inp["t_share"] < 0.10 and inp["c_share"] < 0.20:
                    continue  # had no real role before the absence
                rows.append({"pid": pid, "pos": inp["pos"], "nth": nth, "missed": missed,
                             "pred_t": inp["t_share"], "act_t": r.t_share, "team_t": r.team_targets,
                             "pred_c": inp["c_share"], "act_c": r.c_share, "team_c": r.team_rushes})
    return pd.DataFrame(rows)


def fit(df: pd.DataFrame) -> dict:
    out = {}
    for nth, g in df.groupby("nth"):
        gt = g[g.pred_t >= 0.10]
        gc = g[g.pred_c >= 0.20]
        out[f"t_game{nth}"] = round(float((gt.act_t * gt.team_t).sum() / (gt.pred_t * gt.team_t).sum()), 3)
        out[f"t_game{nth}_n"] = int(len(gt))
        out[f"c_game{nth}"] = round(float((gc.act_c * gc.team_c).sum() / (gc.pred_c * gc.team_c).sum()), 3)
        out[f"c_game{nth}_n"] = int(len(gc))
    return out


def save(params: dict, seasons: list[int]) -> None:
    RETURN_FILE.write_text(json.dumps({"fitted_on_seasons": seasons, **params}, indent=2) + "\n")


def load() -> dict:
    return json.loads(RETURN_FILE.read_text()) if RETURN_FILE.exists() else {}
