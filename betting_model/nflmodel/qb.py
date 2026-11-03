"""QB layer: who is throwing changes every receiver's catch rate and yards per target,
and the QB's own line (attempts, completions, yards, TDs, INTs) is summed from the
same simulated targets as his receivers.

QB quality = his yards per targeted attempt and completion rate, relative to league, blended
toward a prior: league level for experienced QBs (800+ attempts since 2019), backup level
(measured from real low-experience starts) otherwise. The adjustment applied to a team's
receivers = QB quality / the quality of the passing the team's recent targets came from.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class QBModel:
    def __init__(self, passes: pd.DataFrame, k_eff: float = 150.0, window: int = 400):
        self.p = passes
        self.k_eff, self.window = k_eff, window
        self._by_qb = {k: v for k, v in passes.groupby("passer_player_id")}
        self._by_team = {k: v for k, v in passes.groupby("posteam")}
        tg = passes[passes.targeted == 1]
        self._tg_keys = tg.key.to_numpy()
        self._tg_yards = tg.yards.to_numpy()
        self._tg_comp = tg.complete.to_numpy()
        self.backup_rel = self._fit_backup_prior()

    def _league(self, key):
        end = np.searchsorted(self._tg_keys, key, side="left")
        sl = slice(max(0, end - 20000), end)
        return float(self._tg_yards[sl].mean()), float(self._tg_comp[sl].mean())

    def _fit_backup_prior(self):
        """Average yards-per-target and completion rate (vs league) of starts by QBs with < 300 prior attempts."""
        g = self.p[self.p.targeted == 1].groupby(["game_id", "posteam", "passer_player_id"]).agg(
            n=("yards", "size"), yds=("yards", "sum"), comp=("complete", "sum"), key=("key", "first")).reset_index()
        g = g.sort_values("n").drop_duplicates(["game_id", "posteam"], keep="last")
        rel_y, rel_c = [], []
        for r in g.itertuples(index=False):
            prior = self._by_qb[r.passer_player_id]
            if (prior.key < r.key).sum() < 300 and r.key // 100 >= 2020:
                ly, lc = self._league(r.key)
                rel_y.append((r.yds / r.n) / ly); rel_c.append((r.comp / r.n) / lc)
        return (float(np.mean(rel_y)), float(np.mean(rel_c))) if rel_y else (0.9, 0.95)

    def quality(self, qb, key):
        """(yards-per-target rel. to league, completion rel. to league, attempts used) for a QB."""
        ly, lc = self._league(key)
        h = self._by_qb.get(qb)
        h = h[(h.key < key)] if h is not None else None
        career = 0 if h is None else len(h)
        prior_y, prior_c = (1.0, 1.0) if career >= 800 else self.backup_rel
        if h is None or h.empty:
            return prior_y, prior_c, 0
        t = h[h.targeted == 1].tail(self.window)
        n = len(t)
        ry = (t.yards.mean() / ly) if n else prior_y
        rc = (t.complete.mean() / lc) if n else prior_c
        k = self.k_eff
        return (n * ry + k * prior_y) / (n + k), (n * rc + k * prior_c) / (n + k), n

    def team_recent_quality(self, team, key, games=17):
        """Quality of the passing the team's recent targets came from (what receiver pools mostly reflect)."""
        ly, lc = self._league(key)
        t = self._by_team.get(team)
        t = t[(t.key < key) & (t.targeted == 1)]
        keys = sorted(t.key.unique())[-games:]
        t = t[t.key.isin(keys)]
        if t.empty:
            return 1.0, 1.0
        # weight each passer by his own (shrunk) quality, by share of these targets
        ry = rc = 0.0
        for q, g in t.groupby("passer_player_id"):
            qy, qc, _ = self.quality(q, key)
            w = len(g) / len(t)
            ry += w * qy; rc += w * qc
        return ry, rc

    def adjustment(self, qb, team, key):
        qy, qc, n = self.quality(qb, key)
        ty, tc = self.team_recent_quality(team, key)
        return float(np.clip(qy / ty, 0.6, 1.4)), float(np.clip(qc / tc, 0.75, 1.25)), n

    def rates(self, qb, team, key, k_td=1500.0, k_int=400.0):
        """TD per passing yard and INT per attempt (shrunk to league), untargeted attempts per game (team)."""
        lg = self.p[(self.p.key < key) & (self.p.key >= key - 200)]
        lg_td = lg.td.sum() / max(lg.yards.sum(), 1)
        lg_int = lg["int"].sum() / max(len(lg), 1)
        h = self._by_qb.get(qb)
        h = h[h.key < key].tail(600) if h is not None else lg.iloc[0:0]
        td = (h.td.sum() + k_td * lg_td) / (h.yards.sum() + k_td)
        it = (h["int"].sum() + k_int * lg_int) / (len(h) + k_int)
        t = self._by_team.get(team)
        t = t[t.key < key]
        keys = sorted(t.key.unique())[-8:]
        t = t[t.key.isin(keys)]
        untargeted = float((1 - t.targeted).sum() / max(len(keys), 1))
        return float(td), float(it), untargeted

    def rest_pool(self, team, key, exclude, games=8):
        """(complete, yards) outcomes of the team's recent targets to receivers NOT individually simulated."""
        t = self._by_team.get(team)
        t = t[(t.key < key) & (t.targeted == 1)]
        keys = sorted(t.key.unique())[-games:]
        t = t[t.key.isin(keys) & ~t.receiver_player_id.isin(exclude)]
        return t.complete.to_numpy(), t.yards.to_numpy()

    def starter(self, team, key):
        """Most recent game's main passer for the team (default projection starter)."""
        t = self._by_team.get(team)
        t = t[t.key < key]
        if t.empty:
            return None
        last = t[t.key == t.key.max()]
        return last.passer_player_id.value_counts().index[0]
