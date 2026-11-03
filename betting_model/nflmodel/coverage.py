"""Coverage matchups (man vs zone) from nflverse participation data (FTN, published after each season).

For a receiver vs a defense:
  m      = defense's man-coverage rate on recent dropbacks (shrunk to league)
  share  = player's share of team targets on man plays vs zone plays (shrunk to his overall share)
  ypt    = player's yards per target vs man and vs zone (shrunk to his overall ypt)
Multipliers compare the expected mix against THIS defense to the league-average mix he usually sees.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DATA_DIR


def load(seasons):
    rows = []
    for y in seasons:
        try:
            pa = pd.read_parquet(DATA_DIR / f"pbp_participation_{y}.parquet",
                                 columns=["nflverse_game_id", "play_id", "defense_man_zone_type"])
        except FileNotFoundError:
            continue
        pb = pd.read_parquet(DATA_DIR / f"pbp_{y}.parquet", columns=["game_id", "play_id", "season", "week", "season_type", "posteam",
                                                                     "defteam", "play_type", "pass_attempt", "receiver_player_id", "receiving_yards", "two_point_attempt"])
        pb = pb[(pb.season_type == "REG") & (pb.play_type == "pass") & (pb.pass_attempt == 1) & (pb.two_point_attempt != 1)]
        m = pb.merge(pa.rename(columns={"nflverse_game_id": "game_id"}), on=["game_id", "play_id"])
        m = m[m.defense_man_zone_type.isin(["MAN_COVERAGE", "ZONE_COVERAGE"])]
        m["man"] = (m.defense_man_zone_type == "MAN_COVERAGE").astype(int)
        m["yards"] = m.receiving_yards.fillna(0)
        m["key"] = m.season * 100 + m.week
        rows.append(m[["game_id", "key", "posteam", "defteam", "receiver_player_id", "man", "yards"]])
    return pd.concat(rows, ignore_index=True).sort_values("key")


class Coverage:
    def __init__(self, plays: pd.DataFrame):
        self.p = plays
        self._def = {k: v for k, v in plays.groupby("defteam")}
        self._rec = {k: v for k, v in plays[plays.receiver_player_id.notna()].groupby("receiver_player_id")}
        self._team = {k: v for k, v in plays.groupby("posteam")}

    def multipliers(self, pid, team, opp, key, k_def=150, k_share=25, k_ypt=40):
        lg = self.p[(self.p.key < key) & (self.p.key >= key - 200)]
        if lg.empty or opp not in self._def:
            return 1.0, 1.0
        m_lg = lg.man.mean()
        d = self._def[opp]; d = d[d.key < key].tail(600)
        n = len(d)
        m_def = (d.man.sum() + k_def * m_lg) / (n + k_def)
        r = self._rec.get(pid)
        tp = self._team.get(team)
        if r is None or tp is None:
            return 1.0, 1.0
        r = r[r.key < key].tail(150)
        tp = tp[tp.key < key]
        tp = tp[tp.key.isin(r.key.unique())]
        if len(r) < 15 or tp.empty:
            return 1.0, 1.0
        sh_all = len(r) / len(tp)
        out = {}
        for flag in (1, 0):
            rr, tt = r[r.man == flag], tp[tp.man == flag]
            share = (len(rr) + k_share * sh_all) / (len(tt) + k_share) if len(tt) else sh_all
            ypt_all = r.yards.mean()
            ypt = (rr.yards.sum() + k_ypt * ypt_all) / (len(rr) + k_ypt)
            out[flag] = (share, ypt)
        def mix(m):
            s = m * out[1][0] + (1 - m) * out[0][0]
            y = (m * out[1][0] * out[1][1] + (1 - m) * out[0][0] * out[0][1]) / max(s, 1e-9)
            return s, y
        s_def, y_def = mix(m_def)
        s_lg, y_lg = mix(m_lg)
        return float(s_def / s_lg), float(y_def / y_lg)
