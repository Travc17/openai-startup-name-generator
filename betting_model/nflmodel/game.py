"""Joint game simulation for player props: receptions, receiving yards, rushing.

Why joint: parlay legs from the same game are correlated. A pass heavy game
script lifts every receiver on the trailing team and hurts their running back.
Teammates split a fixed pie of targets, so one WR's big night takes looks from
another. Pricing a parlay by multiplying single leg odds ignores all of that.

One simulated game:
  1. Team volume. Draw [team A targets, team A rushes, team B targets, team B
     rushes] together from a multivariate normal. The correlation matrix and
     standard deviations are estimated from 2022+ game data, so game script
     effects (trailing teams throw more, leading teams run more) come from data.
  2. Shares. Each player's target share and carry share is a recency weighted,
     shrunk average, with Beta noise for game to game role variance.
  3. Split. Teammates draw targets/carries sequentially from what's left of the
     team total, so teammates are correctly negatively correlated.
  4. Outcomes. Each target is resampled as a (caught, yards) pair from the
     player's own recent targets mixed with a league pool for his position;
     each carry likewise. Yards are scaled by the opponent's yards allowed
     per target / per carry, shrunk toward league average.
Only games BEFORE the projected week are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

STATS = ("targets", "rec", "rec_yds", "rush_att", "rush_yds", "rec_rush_yds")
STAT_LABEL = {"targets": "targets", "rec": "receptions", "rec_yds": "receiving yards",
              "rush_att": "rush attempts", "rush_yds": "rushing yards",
              "rec_rush_yds": "rush + rec yards"}
POS_GROUP = {"WR": "WR", "TE": "TE", "RB": "RB", "FB": "RB", "QB": "QB"}


@dataclass
class Config:
    half_life_games: float = 6.0
    season_carryover: float = 0.7
    max_games: int = 24
    share_prior_games: float = 2.0
    target_concentration: float = 45.0
    carry_concentration: float = 30.0
    ypt_prior_targets: float = 60.0
    ypc_prior_carries: float = 80.0
    opp_shrink_targets: float = 300.0
    opp_shrink_carries: float = 250.0
    team_window: int = 12
    league_pool_size: int = 6000
    n_sims: int = 20000
    # Defense vs position lever (adjusts, never replaces, the team defense factor). Paired backtest
    # 2024-25: no version beat noise; pos_ypt_long was neutral (-0.00%), so it is the default.
    def_mode: str = "pos_ypt_long"    # team | pos_ypt | pos_ypt_long | pos_volume | zone | zone_volume
    # Carry share uses heavier current-season weighting (backtest 2024-25 wks 6+: rush attempts error -0.86%, t=-2.42).
    # Target share keeps the longer history: more recency did NOT help receivers (rec/rec yds flat or worse).
    share_carryover: float | None = 0.4
    share_half_life: float | None = 4.0
    adot_prior: bool = False   # league pool matched to the player's target depth (catch rate/yds prior)
    recent_targets: bool = False     # target share uses the same recency weights as carry share
    recent_all: bool = False         # every input (shares, catch rate, yards pools) uses the carry-share recency weights
    continuity_seasons: int = 2      # prior seasons that must match (team, primary QB, head coach) to keep the long role
    t_carryover_break: float | None = None   # target-share weight on prior seasons when team, QB or head coach changed (None = off)
    vol_walkforward: bool = True   # team-volume correlation/SD fit only on games before the one projected
    calibrate: bool = True     # per-stat calibration maps (calibration.json); backtests turn this off
    prior_mode: str = "tiered"        # share prior: "tiered" by recent usage, "all", or "regulars"
    # PFF matchup features (model lab 2026-11-05, nflmodel/pff_matchups.py; need model.pffm attached). All OFF:
    # see README "Model review" for each paired test before turning any on.
    pff_pass_pro: bool = False      # F1 offense pressures allowed x defense pressure rate -> yds/target, completions
    pff_run_block: bool = False     # F2 run-block grade vs run-defense grade -> RB yards per carry
    pff_rb_eff: bool = False        # F3 RB yards after contact per attempt -> RB yards per carry
    pff_coverage: bool = False      # F4 defense coverage grade by defender group -> receiver yards per target
    pff_missing_def: bool = False   # F5 missing regular defenders x PFF grade -> opponent pass/rush yards
    # Model lab 2026-11-11: a RB/WR/TE may leave the game hurt (rates fit on 2019-23, nflmodel/early_exit.json);
    # backups later in the allocation absorb his volume. OFF is bit-identical to the old model.
    early_exit: bool = True   # ON 2026-11-12: bench v2 paired test 2025-26 targets -0.15% (t=-2.6), rec -0.20% (t=-3.3), rec_yds -0.16% (t=-2.7), rush_att -0.22% (t=-2.3)
    early_exit_scale: float = 1.0
    # Model lab 2026-11-11: wider role uncertainty for small shares: beta concentration x min(1, share / s0), floor 2.
    share_conc_ref: float | None = None   # s0; None = OFF (bit-identical)
    # Model lab 2026-11-11: mean-preserving role swing for small roles (share x lognormal) below these shares.
    # ON 2026-11-12 for CARRIES only (role_noise_t = 0): bench v2 vs early exit, 2025-26 rush_att -0.23% (t=-2.9), rush_yds -0.20% (t=-2.6)
    role_noise_sigma: float | None = 0.25
    role_noise_t: float = 0.0
    role_noise_c: float = 0.30


_EE = None


def _early_exit() -> dict:
    global _EE
    if _EE is None:
        import json as _json
        from pathlib import Path as _P
        _EE = _json.loads(_P(__file__).with_name("early_exit.json").read_text())
    return _EE


def decay_weights(keys: np.ndarray, cfg: Config) -> np.ndarray:
    n = len(keys)
    w = 0.5 ** (np.arange(n)[::-1] / cfg.half_life_games)
    seasons = keys // 100
    return w * cfg.season_carryover ** (seasons.max() - seasons)


@dataclass
class Player:
    pid: str
    team: str
    share_mult: float = 1.0   # manual target share adjustment for news
    carry_mult: float = 1.0   # manual carry share adjustment for news
    catch_rate: float | None = None  # manual catch-rate override (e.g. a deep threat's real rate)
    yds_mult: float = 1.0            # receiving-yards multiplier (e.g. coverage matchup)
    ypc_mult: float = 1.0            # rushing yards-per-carry multiplier (1.0 = no change)


class GameModel:
    def __init__(self, targets: pd.DataFrame, rushes: pd.DataFrame, positions: dict[str, str],
                 cfg: Config | None = None, snaps: pd.DataFrame | None = None, pos_defense: bool = False,
                 depth: pd.DataFrame | None = None):
        """snaps: add games played with zero touches (from snap counts).
        pos_defense: opponent adjustment by receiver position (WR/TE/RB) instead of one team number.
        depth: normalized depth charts (data.load_depth) for role change adjustments."""
        self.cfg = cfg or Config()
        self.pos_defense = pos_defense
        self.depth = depth
        self.pos = positions
        grp = lambda pid: POS_GROUP.get(self.pos.get(pid, "WR"), "WR")
        t = targets.sort_values("key").reset_index(drop=True)
        r = rushes.sort_values("key").reset_index(drop=True)
        t["pos"] = t.receiver_player_id.map(grp)
        r["pos"] = r.rusher_player_id.map(grp)
        self.t, self.r = t, r

        # Team game table: targets and rushes by offense, yards allowed by defense
        tt = t.groupby(["key", "game_id", "posteam", "defteam"]).agg(targets=("yards", "size"), rec_yds=("yards", "sum"))
        rr = r.groupby(["key", "game_id", "posteam", "defteam"]).agg(rushes=("yards", "size"), rush_yds=("yards", "sum"))
        self.tg = tt.join(rr, how="outer").fillna(0).reset_index().sort_values("key")

        # Player game table: one row per player per game with any target or carry
        pt = t.groupby(["key", "game_id", "posteam", "receiver_player_id"]).agg(
            targets=("yards", "size"), rec=("complete", "sum"), rec_yds=("yards", "sum"))
        pt.index = pt.index.set_names("pid", level=3)
        pr = r.groupby(["key", "game_id", "posteam", "rusher_player_id"]).agg(
            rush_att=("yards", "size"), rush_yds=("yards", "sum"))
        pr.index = pr.index.set_names("pid", level=3)
        pg = pt.join(pr, how="outer").fillna(0).reset_index()
        if snaps is not None:
            z = snaps.rename(columns={"team": "posteam", "gsis_id": "pid"})[["game_id", "posteam", "pid", "offense_pct"]]
            pg = pg.merge(z, on=["game_id", "posteam", "pid"], how="outer")
            keymap = self.tg.drop_duplicates("game_id").set_index("game_id").key
            pg["key"] = pg.game_id.map(keymap)
            pg = pg.dropna(subset=["key"])
            pg["key"] = pg.key.astype(int)
            for c in ("targets", "rec", "rec_yds", "rush_att", "rush_yds"):
                pg[c] = pg[c].fillna(0)
        pg = pg.merge(self.tg[["game_id", "posteam", "defteam", "targets", "rushes"]].rename(
            columns={"targets": "team_targets", "rushes": "team_rushes"}), on=["game_id", "posteam"])
        pg["t_share"] = pg.targets / pg.team_targets.clip(lower=1)
        pg["c_share"] = pg.rush_att / pg.team_rushes.clip(lower=1)
        pg["pos"] = pg.pid.map(grp)
        self.pg = pg.sort_values("key").reset_index(drop=True)

        self._pg_by = {k: v for k, v in self.pg.groupby("pid")}
        self._t_by = {k: v for k, v in t.groupby("receiver_player_id")}
        self._r_by = {k: v for k, v in r.groupby("rusher_player_id")}
        self._tg_off = {k: v for k, v in self.tg.groupby("posteam")}
        self._tg_def = {k: v for k, v in self.tg.groupby("defteam")}
        self._tpool = {p: (g.key.to_numpy(), g.complete.to_numpy(), g.yards.to_numpy()) for p, g in t.groupby("pos")}
        self.ADOT_BINS = np.array([-100, 0, 5, 10, 15, 20, 1000])
        self._tpool_ab = {p: np.clip(np.digitize(g.air_yards.fillna(5).to_numpy(), self.ADOT_BINS) - 1, 0, 5) for p, g in t.groupby("pos")}
        self._rpool = {p: (g.key.to_numpy(), g.yards.to_numpy()) for p, g in r.groupby("pos")}
        self._tdp = {k: v for k, v in t.groupby(["key", "defteam", "pos"]).agg(
            n=("yards", "size"), yds=("yards", "sum"), comp=("complete", "sum")).reset_index().groupby("defteam")}
        tz = t[t.zone != "na"]
        self._tdz = {k: v for k, v in tz.groupby(["key", "defteam", "zone"]).agg(
            n=("yards", "size"), yds=("yards", "sum")).reset_index().groupby("defteam")}
        self._zone_league = tz.groupby(["key", "zone"]).agg(n=("yards", "size"), yds=("yards", "sum")).reset_index()
        self._pos_league = t.groupby(["key", "pos"]).agg(n=("yards", "size"), yds=("yards", "sum")).reset_index()
        self._tz_by = {k: v for k, v in tz.groupby("receiver_player_id")}
        self.vol_corr, self.vol_sd = self._volume_covariance()
        self._vol_cache = {}
        self._cont_cache = {}

    # ---------------- volume structure ----------------
    def _vol_params(self, key: int) -> tuple[np.ndarray, np.ndarray]:
        """Walk-forward volume correlation/SD: fit only on games before `key` (no look-ahead)."""
        if not self.cfg.vol_walkforward:
            return self.vol_corr, self.vol_sd
        if key not in self._vol_cache:
            prior = self.tg[self.tg.key < key]
            self._vol_cache[key] = self._volume_covariance(prior) if prior.game_id.nunique() >= 250 else (self.vol_corr, self.vol_sd)
        return self._vol_cache[key]

    def _volume_covariance(self, tg: pd.DataFrame | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Correlation of [A targets, A rushes, B targets, B rushes] residuals within games."""
        g = (self.tg if tg is None else tg).copy()
        g["season"] = g.key // 100
        for c in ("targets", "rushes"):
            g[c + "_res"] = g[c] - g.groupby(["season", "posteam"])[c].transform("mean")
        pairs = g.merge(g, on="game_id", suffixes=("_a", "_b"))
        pairs = pairs[pairs.posteam_a != pairs.posteam_b]  # both orderings, symmetric
        m = pairs[["targets_res_a", "rushes_res_a", "targets_res_b", "rushes_res_b"]].to_numpy()
        return np.corrcoef(m.T), m.std(axis=0)

    def _team_mu(self, team: str, opp: str, key: int, col: str) -> float:
        off = self._tg_off[team]
        off = off[off.key < key].tail(self.cfg.team_window)
        de = self._tg_def[opp]
        de = de[de.key < key].tail(self.cfg.team_window)
        league = self.tg[self.tg.key < key].tail(32 * 8)[col].mean()
        o = np.average(off[col], weights=decay_weights(off.key.to_numpy(), self.cfg)) if len(off) else league
        d = np.average(de[col], weights=decay_weights(de.key.to_numpy(), self.cfg)) if len(de) else league
        return float(o * (d / league) ** 0.5)

    def _opp_mult(self, opp: str, key: int, kind: str) -> float:
        de = self._tg_def[opp]
        de = de[de.key < key].tail(self.cfg.team_window)
        recent = self.tg[self.tg.key < key].tail(32 * 16)
        if kind == "rec":
            n, y, ly, shrink = de.targets.sum(), de.rec_yds.sum(), recent.rec_yds.sum() / recent.targets.sum(), self.cfg.opp_shrink_targets
        else:
            n, y, ly, shrink = de.rushes.sum(), de.rush_yds.sum(), recent.rush_yds.sum() / recent.rushes.sum(), self.cfg.opp_shrink_carries
        if n == 0:
            return 1.0
        return float(1 + n / (n + shrink) * ((y / n) / ly - 1))

    def _def_keys(self, opp: str, key: int, window: int) -> pd.Series:
        k = self._tg_def[opp]
        return k[k.key < key].tail(window).key

    def defense_adjust(self, pid: str, opp: str, key: int, pos: str, team_factor: float) -> tuple[float, float]:
        """(yards multiplier, target share multiplier) for this receiver vs this defense, per cfg.def_mode."""
        mode = self.cfg.def_mode
        if self.pos_defense and mode == "team":
            mode = "pos_ypt"
        ymult, smult = team_factor, 1.0
        if mode in ("pos_ypt", "pos_ypt_long", "pos_full"):
            ymult = self._opp_mult_pos(opp, key, pos, team_factor, long=(mode != "pos_ypt"))
        if mode in ("zone", "zone_volume"):
            ymult = self._zone_mult(pid, opp, key, team_factor)
        if mode in ("pos_volume", "zone_volume"):
            smult = self._volume_mult(opp, key, pos)
        return ymult, smult

    def _catch_mult(self, opp: str, key: int, pos: str, shrink: float = 300.0) -> float:
        """Catch rate this defense allows to the position vs league, full season window, shrunk."""
        keys = self._def_keys(opp, key, 17)
        d = self._tdp[opp]
        d = d[d.key.isin(keys) & (d.pos == pos)]
        n = d.n.sum()
        if n == 0:
            return 1.0
        lk, lc, _ = self._tpool.get(pos, self._tpool["WR"])
        end = np.searchsorted(lk, key, side="left")
        league = lc[max(0, end - self.cfg.league_pool_size):end].mean()
        return float(1 + n / (n + shrink) * ((d.comp.sum() / n) / league - 1))

    def _volume_mult(self, opp: str, key: int, pos: str) -> float:
        """Share of targets this defense allows to the position vs league norm."""
        keys = self._def_keys(opp, key, 17)
        d = self._tdp[opp]
        d = d[d.key.isin(keys)]
        n_all = d.n.sum()
        if n_all == 0:
            return 1.0
        def_share = d[d.pos == pos].n.sum() / n_all
        L = self._pos_league[(self._pos_league.key < key) & (self._pos_league.key >= key - 100)]
        lg_share = L[L.pos == pos].n.sum() / max(L.n.sum(), 1)
        if lg_share == 0:
            return 1.0
        w = n_all / (n_all + 600.0)
        return float(1 + w * (def_share / lg_share - 1))

    def _zone_mult(self, pid: str, opp: str, key: int, team_factor: float) -> float:
        """Player's target mix by field zone (left/middle/right x short/deep) times the
        defense's yards per target allowed in each zone vs league."""
        own = self._tz_by.get(pid)
        if own is None:
            return team_factor
        own = own[own.key < key].tail(150)
        if len(own) < 10:
            return team_factor
        mix = own.zone.value_counts(normalize=True)
        keys = self._def_keys(opp, key, self.cfg.team_window)
        d = self._tdz.get(opp)
        d = d[d.key.isin(keys)].groupby("zone").sum(numeric_only=True)
        L = self._zone_league[(self._zone_league.key < key) & (self._zone_league.key >= key - 100)].groupby("zone").sum(numeric_only=True)
        total = 0.0
        for z, share in mix.items():
            if z in d.index and z in L.index and L.loc[z, "n"] > 0:
                n = d.loc[z, "n"]
                raw = (d.loc[z, "yds"] / n) / (L.loc[z, "yds"] / L.loc[z, "n"])
                total += share * (1 + n / (n + 100.0) * (raw - 1))
            else:
                total += share
        return float(total)

    def _opp_mult_pos(self, opp: str, key: int, pos: str, team_factor: float, long: bool = False) -> float:
        """Yards per target allowed to this position group, shrunk toward the team factor."""
        keys = self._def_keys(opp, key, 17 if long else self.cfg.team_window)
        d = self._tdp[opp]
        d = d[d.key.isin(keys) & (d.pos == pos)]
        n = d.n.sum()
        if n == 0:
            return team_factor
        lk, _, ly = self._tpool.get(pos, self._tpool["WR"])
        end = np.searchsorted(lk, key, side="left")
        league = ly[max(0, end - self.cfg.league_pool_size):end].mean()
        raw = (d.yds.sum() / n) / league
        return float(team_factor + n / (n + (400.0 if long else 150.0)) * (raw - team_factor))

    @lru_cache(maxsize=4096)
    def _share_prior(self, pos: str, season: int) -> tuple[float, float]:
        g = self.pg[(self.pg.pos == pos) & (self.pg.key // 100 >= season - 2) & (self.pg.key // 100 < season)]
        if g.empty:
            g = self.pg[self.pg.pos == pos]
        if self.cfg.prior_mode == "all":  # every game the position was on the field
            reg_t, reg_c = g.t_share.mean(), g.c_share.mean()
        else:  # starters only (original)
            reg_t = g[g.targets >= 3].t_share.mean()
            reg_c = g[g.rush_att >= 5].c_share.mean() if pos in ("RB", "QB") else g.c_share.mean()
        return float(np.nan_to_num(reg_t, nan=0.1)), float(np.nan_to_num(reg_c, nan=0.02))

    T_BINS = np.array([0, .02, .05, .08, .11, .14, .18, .22, .27, .33, 1.01])
    C_BINS = np.array([0, .02, .05, .10, .20, .30, .40, .50, .60, .70, 1.01])

    @lru_cache(maxsize=256)
    def _tier_table(self, pos: str, season: int) -> tuple[np.ndarray, np.ndarray]:
        """What players at this position with a given recent share (last 4 games)
        actually got next game, learned only from seasons BEFORE `season`."""
        g = self.pg[self.pg.pos == pos].sort_values(["pid", "key"])
        out = []
        for col, bins in (("t_share", self.T_BINS), ("c_share", self.C_BINS)):
            trail = g.groupby("pid")[col].transform(lambda x: x.shift(1).rolling(4, min_periods=2).mean())
            ok = trail.notna() & (g.key // 100 < season) & (g.key // 100 >= season - 3)
            b = np.clip(np.digitize(trail[ok], bins) - 1, 0, len(bins) - 2)
            means = pd.Series(g.loc[ok, col].to_numpy()).groupby(b).mean()
            mids = (bins[:-1] + bins[1:]) / 2
            out.append(np.array([means.get(i, mids[i]) for i in range(len(bins) - 1)]))
        return out[0], out[1]

    def _tiered_prior(self, pos: str, key: int, hist: pd.DataFrame) -> tuple[float, float]:
        tt, tc = self._tier_table(pos, key // 100)
        rec = hist.tail(4)
        bt = int(np.clip(np.digitize(rec.t_share.mean(), self.T_BINS) - 1, 0, len(tt) - 1))
        bc = int(np.clip(np.digitize(rec.c_share.mean(), self.C_BINS) - 1, 0, len(tc) - 1))
        return float(tt[bt]), float(tc[bc])

    # ---------------- player inputs ----------------
    def continuity(self, pid: str, team: str, key: int, hist: pd.DataFrame) -> bool:
        """True when the player's past role should carry over: for each of the last `continuity_seasons` prior
        seasons he played for this team, with the same primary QB and the same head coach as now. Fewer prior
        seasons than required counts as a break (not a long stint). No prior-season games at all: True."""
        season = key // 100
        prev_seasons = sorted({int(x) for x in hist.key // 100 if x < season})
        if not prev_seasons:
            return True
        need = self.cfg.continuity_seasons
        if len(prev_seasons) < need:
            return False
        coach = getattr(self, "coach", None)
        qbm = getattr(self, "qbm", None)
        now_coach = now_qb = None
        if coach is not None:
            c = coach[(coach.team == team) & (coach.key // 100 == season) & (coach.key <= key)]
            now_coach = c.coach.iloc[-1] if len(c) else None
        if qbm is not None and (tp := qbm._by_team.get(team)) is not None:
            n = tp[(tp.key // 100 == season) & (tp.key < key)]
            now_qb = n.passer_player_id.mode().iloc[0] if len(n) else None
        for s_ in prev_seasons[-need:]:
            rows = hist[hist.key // 100 == s_]
            if rows.posteam.mode().iloc[0] != team:
                return False
            if now_coach is not None:
                c = coach[(coach.team == team) & (coach.key // 100 == s_)]
                if len(c) and c.coach.mode().iloc[0] != now_coach:
                    return False
            if now_qb is not None:
                ck = ("qb", team, s_)
                if ck not in self._cont_cache:
                    t = qbm._by_team[team]
                    t = t[t.key // 100 == s_]
                    self._cont_cache[ck] = t.passer_player_id.mode().iloc[0] if len(t) else None
                if self._cont_cache[ck] is not None and self._cont_cache[ck] != now_qb:
                    return False
        return True

    def player_inputs(self, p: Player, opp: str, key: int) -> dict:
        cfg = self.cfg
        hist = self._pg_by.get(p.pid)
        if hist is None or (hist := hist[hist.key < key].tail(cfg.max_games)).empty:
            raise ValueError(f"No history before this week for {p.pid}")
        w = decay_weights(hist.key.to_numpy(), cfg)   # efficiency weights (per-target outcome pools)
        ws = w
        if cfg.share_carryover is not None or cfg.share_half_life is not None:
            from dataclasses import replace
            ws = decay_weights(hist.key.to_numpy(), replace(cfg, season_carryover=cfg.share_carryover or cfg.season_carryover,
                                                            half_life_games=cfg.share_half_life or cfg.half_life_games))
        if cfg.recent_all:
            w = ws
        pos = POS_GROUP.get(self.pos.get(p.pid, "WR"), "WR")
        if cfg.prior_mode == "tiered":
            prior_t, prior_c = self._tiered_prior(pos, key, hist)
        else:
            prior_t, prior_c = self._share_prior(pos, key // 100)
        k = cfg.share_prior_games
        wt = ws if cfg.recent_targets else w
        if cfg.t_carryover_break is not None and not self.continuity(p.pid, p.team, key, hist):
            from dataclasses import replace
            wt = decay_weights(hist.key.to_numpy(), replace(cfg, season_carryover=cfg.t_carryover_break))
        t_share = (np.sum(wt * hist.t_share) + k * prior_t) / (wt.sum() + k) * p.share_mult
        c_share = (np.sum(ws * hist.c_share) + k * prior_c) / (ws.sum() + k) * p.carry_mult
        gw = dict(zip(hist.key, w))

        def pool(own: pd.DataFrame | None, league_keys, cols, prior_n):
            own = own[own.key.isin(hist.key)] if own is not None else None
            end = np.searchsorted(league_keys, key, side="left")
            sl = slice(max(0, end - cfg.league_pool_size), end)
            league_cols = [c[sl] for c in cols]
            own_cols = [own[c].to_numpy() for c in (["complete", "yards"] if len(cols) == 2 else ["yards"])] if own is not None and len(own) else [np.array([])] * len(cols)
            own_w = own.key.map(gw).to_numpy() if own is not None and len(own) else np.array([])
            n_l = max(len(league_cols[0]), 1)
            probs = np.concatenate([own_w, np.full(len(league_cols[0]), prior_n / n_l)])
            vals = [np.concatenate([o, l]) for o, l in zip(own_cols, league_cols)]
            return vals, probs / probs.sum()

        tk, tc, ty = self._tpool.get(pos, self._tpool["WR"])
        (pool_c, pool_ty), pool_tp = pool(self._t_by.get(p.pid), tk, (tc, ty), cfg.ypt_prior_targets)
        own_t = self._t_by.get(p.pid)
        if cfg.adot_prior and own_t is not None:
            own_t = own_t[own_t.key.isin(hist.key)]
            if len(own_t) >= 5:
                # Reweight the league part of the pool so its target-depth mix matches this player's
                ab_all = self._tpool_ab.get(pos, self._tpool_ab["WR"])
                end = np.searchsorted(tk, key, side="left")
                lab = ab_all[max(0, end - cfg.league_pool_size):end]
                own_b = np.clip(np.digitize(own_t.air_yards.fillna(5).to_numpy(), self.ADOT_BINS) - 1, 0, 5)
                own_w = own_t.key.map(gw).to_numpy()
                mix = np.bincount(own_b, weights=own_w, minlength=6) + 0.5
                mix = mix / mix.sum()
                cnt = np.bincount(lab, minlength=6).astype(float)
                n_own = len(own_t)
                lw = (mix / np.maximum(cnt, 1))[lab]
                lw = lw / lw.sum() * cfg.ypt_prior_targets
                ow = pool_tp[:n_own] * 0 + own_w
                probs = np.concatenate([ow, lw])
                pool_tp = probs / probs.sum()
        rk, ry = self._rpool.get(pos, self._rpool["RB"])
        (pool_ry,), pool_rp = pool(self._r_by.get(p.pid), rk, (ry,), cfg.ypc_prior_carries)
        return {
            "pos": pos, "games": len(hist),
            "t_share": float(np.clip(t_share, 0.0, 0.6)), "c_share": float(np.clip(c_share, 0.0, 0.9)),
            "pool_c": pool_c, "pool_ty": pool_ty, "pool_tp": pool_tp,
            "pool_ry": pool_ry, "pool_rp": pool_rp,
            "ypt": float((pool_ty * pool_tp).sum()), "catch": float((pool_c * pool_tp).sum()),
            "ypc": float((pool_ry * pool_rp).sum()),
            "recent": hist.tail(8)[["targets", "rec", "rec_yds", "rush_att", "rush_yds"]],
        }

    # ---------------- simulation ----------------
    def simulate(self, team_a: str, team_b: str, key: int, players: list[Player],
                 n_sims: int | None = None, seed: int | None = 7,
                 rho: dict[str, float] | None = None, exp_margin_a: float | None = None,
                 qbs: dict | None = None, qb_adjust: bool = True, wind: float | None = None) -> dict:
        """rho: pair correlations for the copula. None loads the fitted file, {} turns it off.
        qbs: {team: qb gsis id}; with a QB model attached, adds the QB line and the QB quality adjustment."""
        cfg = self.cfg
        n = n_sims or cfg.n_sims
        rng = np.random.default_rng(seed)
        ex_rng = np.random.default_rng(None if seed is None else seed + 1_000_003)   # early-exit draws only
        sw_rng = np.random.default_rng(None if seed is None else seed + 2_000_029)   # role-swing draws only (own stream since 2026-11-12)
        ee = _early_exit() if cfg.early_exit else None
        teams = (team_a, team_b)
        opp_of = {team_a: team_b, team_b: team_a}

        mu = np.array([self._team_mu(team_a, team_b, key, "targets"), self._team_mu(team_a, team_b, key, "rushes"),
                       self._team_mu(team_b, team_a, key, "targets"), self._team_mu(team_b, team_a, key, "rushes")])
        if exp_margin_a is not None:
            # Game script from the market spread (2022-25 fit, 2,174 team-games): favorites run more.
            # Per point of expected margin: +0.13 rushes, -0.02 targets.
            mu = mu + np.array([-0.02, 0.13, 0.02, -0.13]) * exp_margin_a
        wfx = {"ypa_r": 0.0, "att_r": 0.0, "rush_r": 0.0}
        if wind is not None and wind > 8:
            import json as _json
            from pathlib import Path as _P
            wf = _P(__file__).with_name("weather.json")
            if wf.exists():
                per = _json.loads(wf.read_text())["per_mph_above_8"]
                wfx = {k: v * (wind - 8) for k, v in per.items()}
                mu = mu * np.array([1 + wfx["att_r"], 1 + wfx["rush_r"], 1 + wfx["att_r"], 1 + wfx["rush_r"]])
        vcorr, vsd = self._vol_params(key)
        z = rng.multivariate_normal(np.zeros(4), vcorr, size=n)
        vol = np.clip(np.rint(mu + z * vsd), 5, 80).astype(int)
        team_vol = {team_a: (vol[:, 0], vol[:, 1]), team_b: (vol[:, 2], vol[:, 3])}

        out, info = {}, {}
        for team in teams:
            opp = opp_of[team]
            rec_mult, rush_mult = self._opp_mult(opp, key, "rec"), self._opp_mult(opp, key, "rush")
            rec_mult *= 1 + wfx["ypa_r"]   # wind lowers yards per pass
            pffm = getattr(self, "pffm", None)
            pf = pffm.mults(cfg, team, opp, key) if pffm is not None else None
            if pf is not None:
                rec_mult *= pf["ypt"]
                rush_mult *= pf["rush"]
            left_t, left_c = team_vol[team][0].copy(), team_vol[team][1].copy()
            share_left_t, share_left_c = np.ones(n), np.ones(n)
            qbm = getattr(self, "qbm", None)
            qb = (qbs or {}).get(team) if qbm is not None else None
            if qb is None and qbm is not None and qbs is not None:
                qb = qbm.starter(team, key)
            qy_mult, qc_mult = 1.0, 1.0
            if qb is not None and qb_adjust:
                qy_mult, qc_mult, _ = qbm.adjustment(qb, team, key)
            if pf is not None:
                qc_mult *= pf["cmp"]
            team_rec, team_yds, listed = np.zeros(n), np.zeros(n), []
            for p in [p for p in players if p.team == team]:
                inp = self.player_inputs(p, opp, key)
                p_rec_mult, vol_mult = self.defense_adjust(p.pid, opp, key, inp["pos"], rec_mult)
                p_rec_mult *= p.yds_mult
                if pf is not None:
                    p_rec_mult *= pf["cov"].get(inp["pos"], 1.0)
                inp["t_share"] = float(np.clip(inp["t_share"] * vol_mult, 0.0, 0.6))
                kt, kc = cfg.target_concentration, cfg.carry_concentration
                if cfg.share_conc_ref:
                    kt = max(kt * min(1.0, inp["t_share"] / cfg.share_conc_ref), 2.0)
                    kc = max(kc * min(1.0, inp["c_share"] / cfg.share_conc_ref), 2.0)
                st = rng.beta(max(inp["t_share"], 1e-3) * kt,
                              max(1 - inp["t_share"], 1e-3) * kt, n) if inp["t_share"] > 0.002 else np.zeros(n)
                sc = rng.beta(max(inp["c_share"], 1e-3) * kc,
                              max(1 - inp["c_share"], 1e-3) * kc, n) if inp["c_share"] > 0.002 else np.zeros(n)
                if cfg.role_noise_sigma:
                    sg = cfg.role_noise_sigma
                    if 0.002 < inp["t_share"] < cfg.role_noise_t:
                        st = np.clip(st * np.exp(sg * sw_rng.standard_normal(n) - sg * sg / 2), 0.0, 0.95)
                    if 0.002 < inp["c_share"] < cfg.role_noise_c:
                        sc = np.clip(sc * np.exp(sg * sw_rng.standard_normal(n) - sg * sg / 2), 0.0, 0.95)
                frac = 1.0
                if ee is not None and inp["pos"] in ("RB", "WR", "TE"):
                    hit = ex_rng.random(n) < ee["p"].get(inp["pos"], 0.0) * cfg.early_exit_scale
                    frac = np.where(hit, ex_rng.choice(ee["played_quantiles"], n), 1.0)
                # share_left still drops by the full share below, so later players absorb an exited player's volume
                tg = rng.binomial(left_t, np.clip(st * frac / share_left_t, 0, 1))
                ca = rng.binomial(left_c, np.clip(sc * frac / share_left_c, 0, 1))
                left_t -= tg; left_c -= ca
                share_left_t = np.maximum(share_left_t - st, 0.05)
                share_left_c = np.maximum(share_left_c - sc, 0.05)

                mt = max(int(tg.max()), 1)
                idx = rng.choice(len(inp["pool_ty"]), size=(n, mt), p=inp["pool_tp"])
                m = np.arange(mt)[None, :] < tg[:, None]
                rec = (inp["pool_c"][idx] * m).sum(1)
                if self.cfg.def_mode == "pos_full":
                    cm = self._catch_mult(opp, key, inp["pos"])
                    if cm < 1:
                        rec = rng.binomial(rec.astype(int), cm)
                    else:
                        cr = max(inp["catch"], 0.05)
                        extra_p = min((cm - 1) * cr / max(1 - cr, 0.05), 1.0)
                        rec = rec + rng.binomial((tg - rec).astype(int), extra_p)
                rec_yds = (inp["pool_ty"][idx] * m).sum(1) * p_rec_mult
                if qc_mult != 1.0 or qy_mult != 1.0:
                    rec, rec_yds = self._apply_qb(rng, rec, rec_yds, tg, inp["catch"], qc_mult, qy_mult)
                if p.catch_rate is not None and inp["catch"] > 0:
                    keep = min(p.catch_rate / inp["catch"], 1.0)
                    rec_new = rng.binomial(rec.astype(int), keep)
                    rec_yds = np.where(rec > 0, rec_yds * rec_new / np.maximum(rec, 1), rec_yds)
                    rec = rec_new
                mc = max(int(ca.max()), 1)
                idx = rng.choice(len(inp["pool_ry"]), size=(n, mc), p=inp["pool_rp"])
                m = np.arange(mc)[None, :] < ca[:, None]
                p_rush_mult = rush_mult * p.ypc_mult
                if pf is not None and inp["pos"] == "RB":
                    p_rush_mult *= pf["rb_ypc"] * pffm.rb_eff_mult(cfg, p.pid, key)
                rush_yds = (inp["pool_ry"][idx] * m).sum(1) * p_rush_mult

                out[p.pid] = {"targets": tg, "rec": rec, "rec_yds": rec_yds,
                              "rush_att": ca, "rush_yds": rush_yds, "rec_rush_yds": rec_yds + rush_yds}
                team_rec = team_rec + rec; team_yds = team_yds + rec_yds; listed.append(p.pid)
                info[p.pid] = {**{k: v for k, v in inp.items() if not k.startswith("pool")},
                               "team": team, "opp": opp, "rec_mult": p_rec_mult, "rush_mult": p_rush_mult}
            if qb is not None:
                # Targets to receivers not simulated individually, from the team's recent targets to them
                rc_, ry_ = qbm.rest_pool(team, key, set(listed))
                lk, lc_, ly_ = self._tpool["WR"]
                end = np.searchsorted(lk, key, side="left")
                pool_c = np.concatenate([rc_, lc_[max(0, end - 3000):end]])
                pool_y = np.concatenate([ry_, ly_[max(0, end - 3000):end]])
                w = np.concatenate([np.ones(len(rc_)), np.full(min(end, 3000), 40.0 / max(min(end, 3000), 1))])
                w = w / w.sum()
                rest = np.maximum(left_t, 0)
                mr = max(int(rest.max()), 1)
                idx = rng.choice(len(pool_y), size=(n, mr), p=w)
                m = np.arange(mr)[None, :] < rest[:, None]
                r_rec = (pool_c[idx] * m).sum(1)
                r_yds = (pool_y[idx] * m).sum(1) * rec_mult
                if qc_mult != 1.0 or qy_mult != 1.0:
                    r_rec, r_yds = self._apply_qb(rng, r_rec, r_yds, rest, float(pool_c @ w), qc_mult, qy_mult)
                td_rate, int_rate, untargeted = qbm.rates(qb, team, key)
                att = team_vol[team][0] + rng.poisson(untargeted, n)
                cmp_ = team_rec + r_rec
                pyds = team_yds + r_yds
                qline = {"pass_att": att, "pass_cmp": cmp_, "pass_yds": pyds,
                         "pass_td": rng.poisson(td_rate * np.maximum(pyds, 0)),
                         "int": rng.poisson(int_rate * att)}
                if qb in out:
                    out[qb].update(qline)
                else:
                    z0 = np.zeros(n)
                    out[qb] = {"targets": z0, "rec": z0, "rec_yds": z0, "rush_att": z0, "rush_yds": z0, "rec_rush_yds": z0, **qline}
                    info[qb] = {"pos": "QB", "team": team, "opp": opp, "t_share": 0.0, "c_share": 0.0,
                                "rec_mult": 1.0, "rush_mult": rush_mult}
                info[qb].update({"qb_yds_mult": qy_mult, "qb_cmp_mult": qc_mult, "td_per_yd": td_rate, "int_rate": int_rate})
        res = {"players": out, "info": info,
               "team_mu": {team_a: (mu[0], mu[1]), team_b: (mu[2], mu[3])}}
        if self.cfg.calibrate:
            from . import calibration as _cal
            maps = _cal.load()
            if maps:
                for pid_ in out:
                    _cal.apply(out[pid_], maps, rng)
        if qbs is not None:
            return res   # keep the natural joint structure: QB lines are sums of the same simulated targets
        return apply_copula(res, load_copula() if rho is None else rho, rng)

    @staticmethod
    def _apply_qb(rng, rec, rec_yds, targets, catch, qc_mult, qy_mult):
        """Scale completions (thin or add from incompletions) and yards per target for the QB throwing."""
        rec = rec.astype(int)
        if qc_mult < 1:
            new = rng.binomial(rec, qc_mult)
        else:
            cr = min(max(catch, 0.05), 0.95)
            extra = min((qc_mult - 1) * cr / (1 - cr), 1.0)
            new = rec + rng.binomial(np.maximum(targets.astype(int) - rec, 0), extra)
        return new, rec_yds * qy_mult

    # ---------------- helpers ----------------
    def usage_leaders(self, team: str, key: int, min_targets: float = 4.0, min_carries: float = 6.0,
                      lookback: int = 3) -> list[str]:
        """Players whose recent usage makes them prop candidates (needs 2+ of last `lookback` team games)."""
        tk = sorted(self.tg[(self.tg.posteam == team) & (self.tg.key < key)].key.unique())[-lookback:]
        g = self.pg[(self.pg.posteam == team) & self.pg.key.isin(tk)]
        agg = g.groupby("pid").agg(n=("key", "size"), t=("targets", "mean"), c=("rush_att", "mean"))
        agg = agg[(agg.n >= 2) & ((agg.t >= min_targets) | (agg.c >= min_carries))]
        return agg.sort_values("t", ascending=False).index.tolist()

    def active_players(self, team: str, key: int, lookback: int = 2) -> list[str]:
        """Every RB/WR/TE who played offensive snaps (snap counts or a touch) for this team in any of its
        last `lookback` games before `key` and has not since played for another team. The sim gives each
        one his own share, so depth players fill volume the leaders never had instead of being dropped."""
        tk = sorted(self.tg[(self.tg.posteam == team) & (self.tg.key < key)].key.unique())[-lookback:]
        g = self.pg[(self.pg.posteam == team) & self.pg.key.isin(tk) & self.pg.pos.isin(("RB", "WR", "TE"))]
        g = g[(g.offense_pct.fillna(0) > 0) | (g.targets > 0) | (g.rush_att > 0)]
        out = []
        for pid in g.sort_values("t_share", ascending=False).pid.unique():
            h = self._pg_by.get(pid)
            if h is not None and h[h.key < key].iloc[-1].posteam == team:
                out.append(pid)
        return out


def american(p: float) -> str:
    """Fair American odds for probability p."""
    if p <= 0 or p >= 1:
        return "n/a"
    return f"{-100 * p / (1 - p):+.0f}" if p >= 0.5 else f"{100 * (1 - p) / p:+.0f}"


# ---------------- correlation (Gaussian copula) ----------------
COPULA_FILE = __import__("pathlib").Path(__file__).with_name("copula.json")


def main_kind(sims: dict) -> str:
    """'rec' or 'rush': whichever yardage the player mostly produces."""
    return "rec" if np.mean(sims["rec_yds"]) >= np.mean(sims["rush_yds"]) else "rush"


def main_stat(kind: str) -> str:
    return "rec_yds" if kind == "rec" else "rush_yds"


def pair_kind(team1: str, kind1: str, team2: str, kind2: str) -> str:
    a, b = sorted([kind1, kind2])
    return f"{'same' if team1 == team2 else 'opp'}:{a}-{b}"


def load_copula() -> dict[str, float]:
    import json
    return json.loads(COPULA_FILE.read_text())["rho"] if COPULA_FILE.exists() else {}


def apply_copula(sim: dict, rho: dict[str, float], rng: np.random.Generator) -> dict:
    """Reorder each player's simulated games (all stats together, so each player's
    own distribution is untouched) so players' main yardage stats carry the rank
    correlation measured from real games (Iman-Conover style reordering)."""
    pids = list(sim["players"])
    if len(pids) < 2 or not rho:
        return sim
    kinds = {p: main_kind(sim["players"][p]) for p in pids}
    k = len(pids)
    C = np.eye(k)
    for i in range(k):
        for j in range(i + 1, k):
            pk = pair_kind(sim["info"][pids[i]]["team"], kinds[pids[i]], sim["info"][pids[j]]["team"], kinds[pids[j]])
            C[i, j] = C[j, i] = rho.get(pk, 0.0)
    # nearest positive definite, if needed
    w, v = np.linalg.eigh(C)
    if w.min() < 1e-6:
        C = v @ np.diag(np.clip(w, 1e-6, None)) @ v.T
        d = np.sqrt(np.diag(C)); C = C / np.outer(d, d)
    n = len(next(iter(sim["players"].values()))["rec"])
    Z = rng.multivariate_normal(np.zeros(k), C, size=n)
    for j, p in enumerate(pids):
        s = sim["players"][p]
        key = s[main_stat(kinds[p])] + rng.uniform(0, 1e-6, n)  # break ties randomly
        sorted_rows = np.argsort(key)                 # this player's sims, worst to best
        target_rank = np.argsort(np.argsort(Z[:, j]))  # rank each new row should hold
        new_order = sorted_rows[target_rank]
        sim["players"][p] = {stat: arr[new_order] for stat, arr in s.items()}
    sim["copula"] = True
    return sim
