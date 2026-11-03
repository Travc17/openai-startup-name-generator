"""PFF-based receiver features (all computed from games BEFORE the projected one).

1. YPRR      : expected yards = shrunk yards-per-route-run x expected routes; blended with the model's yards.
2. Alignment : defense yards-per-route allowed to slot-primary vs wide-primary receivers, mixed by the
               player's slot rate.
3. Coverage  : defense man-coverage share (from routes run against it), player's per-route targets and
               yards vs man and vs zone; compared with the league-average mix.
Returns (share_mult, yds_mult) per feature.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DATA_DIR


def _ids():
    pl = pd.read_parquet(DATA_DIR / "players.parquet", columns=["gsis_id", "pff_id"]).dropna()
    pl["pff_id"] = pl.pff_id.astype(float).astype(int)
    return pl


class PFFFeatures:
    def __init__(self, pg, route_role):
        pl = _ids()
        teams = pg[["pid", "key", "posteam", "defteam"]].drop_duplicates(["pid", "key"])
        rs = pd.read_parquet(DATA_DIR / "pff" / "receiving_weekly.parquet").merge(pl, left_on="player_id", right_on="pff_id")
        rs["key"] = rs.season * 100 + rs.week
        rs = rs.merge(teams, left_on=["gsis_id", "key"], right_on=["pid", "key"])
        rs["slot"] = (rs.slot_rate.fillna(0) / 100).clip(0, 1)
        self.rs = rs.sort_values("key")
        sc = pd.read_parquet(DATA_DIR / "pff" / "scheme_weekly.parquet").merge(pl, left_on="player_id", right_on="pff_id")
        sc["key"] = sc.season * 100 + sc.week
        sc = sc.merge(teams, left_on=["gsis_id", "key"], right_on=["pid", "key"])
        self.sc = sc.sort_values("key")
        self.rr = route_role
        self._rs_by = {k: v for k, v in self.rs.groupby("gsis_id")}
        self._sc_by = {k: v for k, v in self.sc.groupby("gsis_id")}
        self._rs_def = {k: v for k, v in self.rs.groupby("defteam")}
        self._sc_def = {k: v for k, v in self.sc.groupby("defteam")}

    # 1 ----------------------------------------------------------------
    def yprr(self, pid, team, key, model_mean_yds, k=80):
        h = self._rs_by.get(pid)
        if h is None or model_mean_yds <= 0:
            return 1.0
        h = h[h.key < key]
        if len(h) < 3:
            return 1.0
        lg = self.rs[(self.rs.key < key) & (self.rs.key >= key - 200)]
        lg_y = lg.yards.sum() / max(lg.routes.sum(), 1)
        hh = h.tail(30)
        y = (hh.yards.sum() + k * lg_y) / (hh.routes.sum() + k)
        rx = self.rr.x[(self.rr.x.gsis_id == pid) & (self.rr.x.key < key)].tail(3)
        t = self.rr.team[(self.rr.team.posteam == team) & (self.rr.team.key < key)].tail(8)
        if rx.empty or t.empty:
            return 1.0
        exp_routes = np.average(rx.rp, weights=np.arange(1, len(rx) + 1)) * t.dropbacks.mean()
        return float(np.clip((0.5 * y * exp_routes + 0.5 * model_mean_yds) / model_mean_yds, 0.6, 1.6))

    # 2 ----------------------------------------------------------------
    def alignment(self, pid, opp, key, k=400):
        h = self._rs_by.get(pid)
        d = self._rs_def.get(opp)
        if h is None or d is None:
            return 1.0
        h = h[h.key < key].tail(12)
        d = d[d.key < key]
        d = d[d.key.isin(sorted(d.key.unique())[-12:])]
        if h.empty or d.empty:
            return 1.0
        lg = self.rs[(self.rs.key < key) & (self.rs.key >= key - 200)]
        out = {}
        for name, mask_fn in (("slot", lambda x: x.slot >= 0.6), ("wide", lambda x: x.slot <= 0.3)):
            dd, ll = d[mask_fn(d)], lg[mask_fn(lg)]
            lg_y = ll.yards.sum() / max(ll.routes.sum(), 1)
            n = dd.routes.sum()
            raw = (dd.yards.sum() / n) / lg_y if n else 1.0
            out[name] = 1 + n / (n + k) * (raw - 1)
        s = float(np.average(h.slot, weights=h.routes.clip(lower=1)))
        return float(s * out["slot"] + (1 - s) * out["wide"])

    # 3 ----------------------------------------------------------------
    def coverage(self, pid, opp, key, k_def=600, k_p=40):
        h = self._sc_by.get(pid)
        d = self._sc_def.get(opp)
        if h is None or d is None:
            return 1.0, 1.0
        h = h[h.key < key].tail(30)
        d = d[d.key < key]
        d = d[d.key.isin(sorted(d.key.unique())[-12:])]
        lg = self.sc[(self.sc.key < key) & (self.sc.key >= key - 200)]
        if h.empty or lg.empty:
            return 1.0, 1.0
        m_lg = lg.man_routes.sum() / max((lg.man_routes + lg.zone_routes).sum(), 1)
        n = (d.man_routes + d.zone_routes).sum()
        m_def = (d.man_routes.sum() + k_def * m_lg) / (n + k_def)
        tot_r = (h.man_routes + h.zone_routes).sum()
        if tot_r < 40:
            return 1.0, 1.0
        tprr_all = (h.man_targets + h.zone_targets).sum() / tot_r
        yprr_all = (h.man_yards + h.zone_yards).sum() / tot_r
        tp, yp = {}, {}
        for c in ("man", "zone"):
            r = h[f"{c}_routes"].sum()
            tp[c] = (h[f"{c}_targets"].sum() + k_p * tprr_all) / (r + k_p)
            yp[c] = (h[f"{c}_yards"].sum() + k_p * yprr_all) / (r + k_p)
        mix = lambda m, x: m * x["man"] + (1 - m) * x["zone"]
        sm = mix(m_def, tp) / mix(m_lg, tp)
        ym_total = mix(m_def, yp) / mix(m_lg, yp)
        return float(sm), float(ym_total / sm)  # yards per target multiplier = yards mult / share mult
