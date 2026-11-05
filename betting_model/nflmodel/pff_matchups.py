"""PFF matchup features (model lab batch 1, 2026-11-05). Every switch defaults OFF in `Config`.

All features use only games BEFORE the projected one (key = season*100 + week). Team-game aggregates come from
PFF weekly facets cached in data/pff/<facet>/ (gitignored, licensed: never committed). Slopes live in
pff_matchups.json and were fit on 2023 weeks 6-18 only (residuals of the production model), so 2024-26 are
scored out of sample. Shrinkage constants were chosen before any scored run.

F1 pass_pro  : offense pressures allowed per dropback x defense pressures per opponent dropback (log5 odds),
               -> team yards per target and QB completion multipliers.
F2 run_block : offense run-block grade (OL+TE) minus defense run-defense grade -> RB yards per carry.
F3 rb_eff    : RB yards after contact per attempt (shrunk) -> RB yards per carry.
F4 coverage  : defense coverage grade by defender group (WR<-CB, TE<-S+LB, RB<-LB) -> receiver yards per target.
F5 missing_def: regular defenders (>=50% snaps, last 4 games) absent from the projected game, x their shrunk
               grade above replacement -> opponent pass and rush yards multipliers.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import DATA_DIR

COEF_FILE = Path(__file__).with_name("pff_matchups.json")
PFF = DATA_DIR / "pff"
WINDOW = 12          # team-games of history (same as Config.team_window)
K_DROPBACKS = 200.0  # F1 shrink (dropbacks)
K_GAMES = 4.0        # F2/F4 shrink (team-games)
K_RB_ATT = 80.0      # F3 shrink (attempts; same as Config.ypc_prior_carries)
REPL_GRADE = 60.0    # F5 replacement-level PFF defense grade


def _facet(slug: str) -> pd.DataFrame:
    rows = []
    for f in glob.glob(str(PFF / slug / "*.json")):
        s, w = Path(f).stem.split("_w")
        for r in json.loads(Path(f).read_text()):
            r["season"], r["week"] = int(s), int(w)
            rows.append(r)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["key"] = df.season * 100 + df.week
    return df


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


class PFFMatchups:
    def __init__(self, model, seasons=(2023, 2024, 2025, 2026), coef_key: str = "coef"):
        """coef_key: "coef" = slopes fit on 2023 (primary test); "coef_2023_24" = refit on 2023-24 (secondary)."""
        self.m = model
        self.coef = json.loads(COEF_FILE.read_text()).get(coef_key, {}) if COEF_FILE.exists() else {}
        tg = model.tg[(model.tg.key // 100).isin(seasons)][["key", "game_id", "posteam", "defteam"]].drop_duplicates(["key", "posteam"])
        self.tg = tg
        # PFF team code -> nflverse code, from receivers in the model's player-game table
        pl = pd.read_parquet(DATA_DIR / "players.parquet", columns=["gsis_id", "pff_id"]).dropna()
        pl["pff_id"] = pl.pff_id.astype(float).astype(int)
        rs = pd.read_parquet(PFF / "receiving_weekly.parquet")[["player_id", "team_name", "season", "week"]]
        rs["key"] = rs.season * 100 + rs.week
        rs = rs.merge(pl, left_on="player_id", right_on="pff_id").merge(
            model.pg[["pid", "key", "posteam"]], left_on=["gsis_id", "key"], right_on=["pid", "key"])
        self.team_map = rs.groupby("team_name").posteam.agg(lambda x: x.mode().iloc[0]).to_dict()
        self.pl = pl
        # dropbacks per team-game (play by play)
        frames = []
        for y in seasons:
            f = DATA_DIR / f"pbp_{y}.parquet"
            if f.exists():
                d = pd.read_parquet(f, columns=["season", "week", "season_type", "posteam", "qb_dropback"])
                d = d[(d.season_type == "REG") & (d.qb_dropback == 1)]
                frames.append(d.groupby(["season", "week", "posteam"]).size().rename("dropbacks").reset_index())
        db = pd.concat(frames)
        db["key"] = db.season * 100 + db.week
        self.db = db[["key", "posteam", "dropbacks"]]
        self._build()

    def _team(self, df):
        df = df.copy()
        df["nfl_team"] = df.team_name.map(self.team_map)
        return df.dropna(subset=["nfl_team"])

    def _build(self):
        tg = self.tg
        # F1 ----------------------------------------------------------
        pb = self._team(_facet("offense__pass_blocking"))
        pr = self._team(_facet("defense__pass_rush"))
        off = pb.groupby(["key", "nfl_team"]).pressures_allowed.sum().rename("p_allowed").reset_index()
        off = off.merge(self.db, left_on=["key", "nfl_team"], right_on=["key", "posteam"])[["key", "nfl_team", "p_allowed", "dropbacks"]]
        de = pr.groupby(["key", "nfl_team"]).total_pressures.sum().rename("p_made").reset_index()
        de = de.merge(tg[["key", "posteam", "defteam"]], left_on=["key", "nfl_team"], right_on=["key", "defteam"])
        de = de.merge(self.db, on=["key", "posteam"])[["key", "nfl_team", "p_made", "dropbacks"]]
        self.f1_off = {k: v.sort_values("key") for k, v in off.groupby("nfl_team")}
        self.f1_def = {k: v.sort_values("key") for k, v in de.groupby("nfl_team")}
        self.f1_off_all, self.f1_def_all = off, de
        # F2 ----------------------------------------------------------
        rb = self._team(_facet("offense__run_blocking"))
        ds = self._team(_facet("defense__summary"))
        self.ds = ds
        rb = rb[rb.position.isin(["T", "G", "C", "TE"]) & (rb.snap_counts_run_block > 0) & rb.grades_run_block.notna()]
        rb["wg"] = rb.grades_run_block * rb.snap_counts_run_block
        o2 = rb.groupby(["key", "nfl_team"]).agg(wg=("wg", "sum"), w=("snap_counts_run_block", "sum")).reset_index()
        o2["g"] = o2.wg / o2.w
        d2 = ds[(ds.snap_counts_run_defense > 0) & ds.grades_run_defense.notna()].copy()
        d2["wg"] = d2.grades_run_defense * d2.snap_counts_run_defense
        d2 = d2.groupby(["key", "nfl_team"]).agg(wg=("wg", "sum"), w=("snap_counts_run_defense", "sum")).reset_index()
        d2["g"] = d2.wg / d2.w
        self.f2_off = {k: v.sort_values("key") for k, v in o2.groupby("nfl_team")}
        self.f2_def = {k: v.sort_values("key") for k, v in d2.groupby("nfl_team")}
        self.f2_off_all, self.f2_def_all = o2, d2
        # F3 ----------------------------------------------------------
        ru = _facet("rushing__summary")
        ru = ru[ru.position == "HB"].merge(self.pl, left_on="player_id", right_on="pff_id")
        self.f3 = ru[["gsis_id", "key", "attempts", "yards_after_contact", "yards"]].sort_values("key")
        self.f3_by = {k: v for k, v in self.f3.groupby("gsis_id")}
        # F4 ----------------------------------------------------------
        c = ds[(ds.snap_counts_coverage > 0) & ds.grades_coverage_defense.notna()].copy()
        c["wg"] = c.grades_coverage_defense * c.snap_counts_coverage
        groups = {"WR": ["CB"], "TE": ["S", "LB"], "RB": ["LB"]}
        self.f4 = {}
        for pos, dpos in groups.items():
            g = c[c.position.isin(dpos)].groupby(["key", "nfl_team"]).agg(wg=("wg", "sum"), w=("snap_counts_coverage", "sum")).reset_index()
            g["g"] = g.wg / g.w
            self.f4[pos] = ({k: v.sort_values("key") for k, v in g.groupby("nfl_team")}, g)
        # F5 ----------------------------------------------------------
        d5 = ds[ds.snap_counts_defense.fillna(0) > 0][["key", "nfl_team", "player_id", "snap_counts_defense", "grades_defense"]].copy()
        d5["team_snaps"] = d5.groupby(["key", "nfl_team"]).snap_counts_defense.transform("max")
        d5["share"] = d5.snap_counts_defense / d5.team_snaps
        self.f5 = d5
        self.f5_by = {k: v for k, v in d5.groupby("nfl_team")}
        self.f5_pl = {k: v.sort_values("key") for k, v in d5.groupby("player_id")}

    # ---------------- raw features (x) ----------------
    @staticmethod
    def _prior(d, key, n=WINDOW):
        return d[d.key < key].tail(n) if d is not None else None

    def x_pass_pro(self, team, opp, key):
        lo = self.f1_off_all[(self.f1_off_all.key < key) & (self.f1_off_all.key >= key - 200)]
        ld = self.f1_def_all[(self.f1_def_all.key < key) & (self.f1_def_all.key >= key - 200)]
        if lo.empty or ld.empty:
            return 0.0
        lg_o, lg_d = lo.p_allowed.sum() / lo.dropbacks.sum(), ld.p_made.sum() / ld.dropbacks.sum()
        o, d = self._prior(self.f1_off.get(team), key), self._prior(self.f1_def.get(opp), key)
        ro = (o.p_allowed.sum() + K_DROPBACKS * lg_o) / (o.dropbacks.sum() + K_DROPBACKS) if o is not None else lg_o
        rd = (d.p_made.sum() + K_DROPBACKS * lg_d) / (d.dropbacks.sum() + K_DROPBACKS) if d is not None else lg_d
        return float(_logit(ro) - _logit(lg_o) + _logit(rd) - _logit(lg_d))

    @staticmethod
    def _shrunk_grade(d, allg, key):
        lg = allg[(allg.key < key) & (allg.key >= key - 200)]
        if lg.empty:
            return None, None
        lgv = float(lg.wg.sum() / lg.w.sum())
        if d is None:
            return lgv, lgv
        d = d[d.key < key].tail(WINDOW)
        return float((d.g.sum() + K_GAMES * lgv) / (len(d) + K_GAMES)), lgv

    def x_run_block(self, team, opp, key):
        o, lo = self._shrunk_grade(self.f2_off.get(team), self.f2_off_all, key)
        d, ld = self._shrunk_grade(self.f2_def.get(opp), self.f2_def_all, key)
        if o is None or d is None:
            return 0.0
        return float((o - lo) - (d - ld))

    def x_rb_eff(self, pid, key):
        lg = self.f3[(self.f3.key < key) & (self.f3.key >= key - 200)]
        if lg.empty or lg.attempts.sum() == 0:
            return 0.0
        lgv = lg.yards_after_contact.sum() / lg.attempts.sum()
        h = self.f3_by.get(pid)
        if h is None:
            return 0.0
        h = h[h.key < key].tail(30)
        return float((h.yards_after_contact.sum() + K_RB_ATT * lgv) / (h.attempts.sum() + K_RB_ATT) - lgv)

    def x_coverage(self, opp, key, pos):
        by, allg = self.f4.get(pos, self.f4["WR"])
        g, lg = self._shrunk_grade(by.get(opp), allg, key)
        return 0.0 if g is None else float(g - lg)

    def x_missing_def(self, opp, key):
        """Snap-share-weighted grade above replacement of regulars missing from this game (needs the game's PFF
        participation, i.e. who played: known pregame from inactives, same convention as the backtests)."""
        d = self.f5_by.get(opp)
        if d is None:
            return 0.0
        now = d[d.key == key]
        prior_keys = sorted(d[d.key < key].key.unique())[-4:]
        if now.empty or len(prior_keys) < 2:
            return 0.0
        p = d[d.key.isin(prior_keys)]
        share = p.groupby("player_id").share.sum() / len(prior_keys)
        regulars = share[share >= 0.5]
        missing = [pid for pid in regulars.index if pid not in set(now.player_id)]
        tot = 0.0
        for pid in missing:
            h = self.f5_pl[pid]
            h = h[h.key < key].tail(16)
            w = h.snap_counts_defense
            g = (float((h.grades_defense.fillna(REPL_GRADE) * w).sum()) + 200 * REPL_GRADE) / (float(w.sum()) + 200)
            tot += regulars[pid] * (g - REPL_GRADE) / 10.0
        return float(tot)

    # ---------------- multipliers ----------------
    def mults(self, cfg, team, opp, key) -> dict:
        """Team-level multipliers for `team`'s offense vs `opp` under the Config switches (all 1.0 when OFF)."""
        c = self.coef
        out = {"ypt": 1.0, "cmp": 1.0, "rb_ypc": 1.0, "rush": 1.0, "cov": {}}
        if cfg.pff_pass_pro and "pass_pro" in c:
            x = self.x_pass_pro(team, opp, key)
            out["ypt"] *= float(np.exp(c["pass_pro"]["b_ypt"] * x))
            out["cmp"] *= float(np.exp(c["pass_pro"]["b_cmp"] * x))
        if cfg.pff_run_block and "run_block" in c:
            out["rb_ypc"] *= float(np.exp(c["run_block"]["b"] * self.x_run_block(team, opp, key)))
        if cfg.pff_coverage and "coverage" in c:
            out["cov"] = {pos: float(np.exp(c["coverage"]["b"] * self.x_coverage(opp, key, pos))) for pos in ("WR", "TE", "RB")}
        if cfg.pff_missing_def and "missing_def" in c:
            x = self.x_missing_def(opp, key)
            out["ypt"] *= float(np.exp(c["missing_def"]["b_ypt"] * x))
            out["rush"] *= float(np.exp(c["missing_def"]["b_ypc"] * x))
        return out

    def rb_eff_mult(self, cfg, pid, key) -> float:
        if not (cfg.pff_rb_eff and "rb_eff" in self.coef):
            return 1.0
        return float(np.exp(self.coef["rb_eff"]["b"] * self.x_rb_eff(pid, key)))
