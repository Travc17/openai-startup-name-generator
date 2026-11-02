"""Receiving yards projection by Monte Carlo simulation.

How one game is simulated:
  1. Team targets   ~ Normal(team_mu, TEAM_SD), team_mu blends the offense's recent
                      volume with how many targets the defense usually faces.
  2. Player share   ~ Beta around a recency weighted, shrunk target share.
  3. Player targets ~ Binomial(team targets, share).
  4. Yards per target are resampled from the player's own recent targets (zeros for
     incompletions included), mixed with a league pool for his position so small
     samples get pulled toward normal, then scaled by an opponent factor.
Everything uses only games BEFORE the one being projected.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Config:
    half_life_games: float = 6.0      # recency decay for share and yards per target
    season_carryover: float = 0.7     # extra weight multiplier per season boundary
    max_games: int = 24               # player history window
    share_prior_games: float = 2.0    # pseudo games pulling share toward position average
    share_concentration: float = 45.0 # Beta concentration, game to game role variance
    ypt_prior_targets: float = 60.0   # pseudo targets from the league pool
    opp_shrink_targets: float = 300.0 # targets before trusting a defense's YPT fully
    team_sd: float = 6.5              # sd of team targets in a game
    team_window: int = 12             # team games for volume averages
    league_pool_size: int = 6000      # most recent league targets per position
    n_sims: int = 20000


POS_GROUP = {"WR": "WR", "TE": "TE", "RB": "RB", "FB": "RB"}


def _decay_weights(keys: np.ndarray, cfg: Config) -> np.ndarray:
    """keys sorted oldest to newest; weight by games ago and season changes."""
    n = len(keys)
    games_ago = np.arange(n)[::-1]
    w = 0.5 ** (games_ago / cfg.half_life_games)
    seasons = keys // 100
    seasons_back = seasons.max() - seasons
    return w * cfg.season_carryover ** seasons_back


class ReceivingModel:
    def __init__(self, targets: pd.DataFrame, pgames: pd.DataFrame, tgames: pd.DataFrame,
                 positions: dict[str, str], cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.t = targets.sort_values("key").reset_index(drop=True)
        self.pg = pgames.sort_values("key").reset_index(drop=True)
        self.tg = tgames.sort_values("key").reset_index(drop=True)
        self.pos = positions
        self.t["pos"] = self.t.receiver_player_id.map(lambda p: POS_GROUP.get(self.pos.get(p, "WR"), "WR"))
        self.pg["pos"] = self.pg.receiver_player_id.map(lambda p: POS_GROUP.get(self.pos.get(p, "WR"), "WR"))
        # Pre index for speed
        self._t_by_player = {k: v for k, v in self.t.groupby("receiver_player_id")}
        self._pg_by_player = {k: v for k, v in self.pg.groupby("receiver_player_id")}
        self._tg_off = {k: v for k, v in self.tg.groupby("posteam")}
        self._tg_def = {k: v for k, v in self.tg.groupby("defteam")}
        self._pool = {pos: (g.key.to_numpy(), g.yards.to_numpy()) for pos, g in self.t.groupby("pos")}
        self._t_keys = self.t.key.to_numpy()
        self._t_yards = self.t.yards.to_numpy()

    # ---------- components ----------
    def _league_pool(self, pos: str, key: int) -> np.ndarray:
        keys, yards = self._pool.get(pos, self._pool["WR"])
        end = np.searchsorted(keys, key, side="left")
        return yards[max(0, end - self.cfg.league_pool_size):end]

    def _league_ypt(self, key: int) -> float:
        end = np.searchsorted(self._t_keys, key, side="left")
        return float(self._t_yards[max(0, end - 20000):end].mean())

    def _position_share_prior(self, pos: str, key: int) -> float:
        g = self.pg[(self.pg.pos == pos) & (self.pg.key < key) & (self.pg.key >= key - 200)]
        g = g[g.targets >= 3]  # regulars only, the players we'd bet on
        return float(g.share.mean()) if len(g) else 0.15

    def team_targets_mu(self, team: str, opp: str, key: int) -> float:
        off = self._tg_off[team]
        off = off[off.key < key].tail(self.cfg.team_window)
        de = self._tg_def[opp]
        de = de[de.key < key].tail(self.cfg.team_window)
        league = self.tg[(self.tg.key < key)].tail(32 * 8).targets.mean()
        off_mu = np.average(off.targets, weights=_decay_weights(off.key.to_numpy(), self.cfg)) if len(off) else league
        def_mu = np.average(de.targets, weights=_decay_weights(de.key.to_numpy(), self.cfg)) if len(de) else league
        return float(off_mu * (def_mu / league) ** 0.5)

    def opp_factor(self, opp: str, key: int) -> tuple[float, float]:
        de = self._tg_def[opp]
        de = de[de.key < key].tail(self.cfg.team_window)
        if de.empty:
            return 1.0, 0.0
        n = de.targets.sum()
        ypt_allowed = de.yards.sum() / n
        raw = ypt_allowed / self._league_ypt(key)
        w = n / (n + self.cfg.opp_shrink_targets)
        return float(1 + w * (raw - 1)), float(raw)

    # ---------- main ----------
    def project(self, player_id: str, team: str, opp: str, key: int,
                share_mult: float = 1.0, team_targets_override: float | None = None,
                n_sims: int | None = None, seed: int | None = 7) -> dict:
        cfg = self.cfg
        n_sims = n_sims or cfg.n_sims
        rng = np.random.default_rng(seed)
        pos = POS_GROUP.get(self.pos.get(player_id, "WR"), "WR")

        hist = self._pg_by_player.get(player_id)
        if hist is None:
            raise ValueError("No target history for this player.")
        hist = hist[hist.key < key].tail(cfg.max_games)
        if hist.empty:
            raise ValueError("No games before this week for this player.")
        w = _decay_weights(hist.key.to_numpy(), cfg)

        prior_share = self._position_share_prior(pos, key)
        share_mu = (np.sum(w * hist.share) + cfg.share_prior_games * prior_share) / (w.sum() + cfg.share_prior_games)
        share_mu = float(np.clip(share_mu * share_mult, 0.01, 0.6))

        team_mu = team_targets_override or self.team_targets_mu(team, opp, key)
        opp_mult, opp_raw = self.opp_factor(opp, key)

        # Per target yards pool: player's own recent targets + league pool for position
        pt = self._t_by_player[player_id]
        pt = pt[pt.key.isin(hist.key)]
        game_w = dict(zip(hist.key, w))
        own_y = pt.yards.to_numpy()
        own_w = pt.key.map(game_w).to_numpy()
        league_y = self._league_pool(pos, key)
        league_w = np.full(len(league_y), cfg.ypt_prior_targets / max(len(league_y), 1))
        pool_y = np.concatenate([own_y, league_y])
        pool_p = np.concatenate([own_w, league_w])
        pool_p = pool_p / pool_p.sum()

        team_t = np.clip(np.rint(rng.normal(team_mu, cfg.team_sd, n_sims)), 8, 70).astype(int)
        c = cfg.share_concentration
        shares = rng.beta(share_mu * c, (1 - share_mu) * c, n_sims)
        tgts = rng.binomial(team_t, shares)
        max_t = int(tgts.max()) if tgts.max() > 0 else 1
        draws = rng.choice(pool_y, size=(n_sims, max_t), p=pool_p)
        mask = np.arange(max_t)[None, :] < tgts[:, None]
        yards = (draws * mask).sum(axis=1) * opp_mult

        return {
            "sims": yards,
            "targets": tgts,
            "share_mu": share_mu,
            "team_targets_mu": team_mu,
            "opp_mult": opp_mult,
            "opp_raw": opp_raw,
            "own_ypt": float(np.average(own_y, weights=own_w)) if len(own_y) else float("nan"),
            "pool_ypt": float((pool_y * pool_p).sum()),
            "games_used": int(len(hist)),
            "pos": pos,
        }


def prob_over(sims: np.ndarray, line: float) -> float:
    return float((sims > line).mean())
