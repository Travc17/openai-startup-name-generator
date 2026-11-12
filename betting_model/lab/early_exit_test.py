"""Model lab 2026-11-11: paired OFF/ON test of Config.early_exit (pre-registered in reviews/improve_log.md).

    nice -n 19 python lab/early_exit_test.py --season 2024 --weeks 4-18 --out <scratch>/ee2024.parquet
    python lab/early_exit_test.py --score <scratch>/ee2024.parquet <scratch>/ee2025.parquet <scratch>/ee2026.parquet

Same scoring loop as lab/pff_batch1.py (production model: route-role blend, real starting QB, closing spread) plus the
production depth rule (every RB/WR/TE with snaps in the team's last 2 games), scored on players who played. Every
variant of a game uses the same seed, so CRPS differences are paired.
"""
from __future__ import annotations
import argparse, sys, zlib
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import nfl  # noqa: E402
from nflmodel import data  # noqa: E402
from nflmodel.backtest import crps  # noqa: E402
from nflmodel.game import Player  # noqa: E402
VARIANTS = {"off": {}, "on": {"early_exit": True}, "on15": {"early_exit": True, "early_exit_scale": 1.5}}
SHARE = {"off": {}, "c10": {"share_conc_ref": 0.10}, "c20": {"share_conc_ref": 0.20}, "c30": {"share_conc_ref": 0.30}}
OFFONLY = {"off": {}}
NOISE = {"off": {}, "n25": {"role_noise_sigma": 0.25}, "n40": {"role_noise_sigma": 0.40}, "n55": {"role_noise_sigma": 0.55}}
DEFAULTS = {"early_exit": False, "early_exit_scale": 1.0, "share_conc_ref": None, "role_noise_sigma": None}
STATS = ["targets", "rec", "rec_yds", "rush_att", "rush_yds", "pass_att", "pass_cmp", "pass_yds"]


def _u(*parts) -> float:
    return zlib.crc32("|".join(map(str, parts)).encode()) / 2 ** 32


def run(season: int, weeks: list[int], sims: int, zero_snaps: bool = False) -> pd.DataFrame:
    m = nfl.build_model()
    ros = None
    if zero_snaps:   # nflverse weekly rosters: ACT = active for the game; ACT with no snaps counts as 0, not dropped
        r = pd.read_parquet(data.DATA_DIR / f"roster_weekly_{season}.parquet", columns=["week", "team", "gsis_id", "status"])
        ros = set(map(tuple, r[r.status == "ACT"][["week", "team", "gsis_id"]].to_numpy()))
    gi_ = pd.read_parquet(data.DATA_DIR / f"pbp_{season}.parquet", columns=["game_id", "home_team", "spread_line"]).drop_duplicates("game_id").set_index("game_id")
    P = m.qbm.p
    starter = (P[P.key // 100 == season].groupby(["game_id", "posteam", "passer_player_id"]).size().rename("att").reset_index()
               .sort_values("att").drop_duplicates(["game_id", "posteam"], keep="last").set_index(["game_id", "posteam"]).passer_player_id)
    qb_act = P.groupby(["game_id", "passer_player_id"]).agg(pass_att=("yards", "size"), pass_cmp=("complete", "sum"), pass_yds=("yards", "sum"))
    games = m.tg[(m.tg.key // 100 == season) & (m.tg.key % 100).isin(weeks)].drop_duplicates("game_id")
    rows = []
    for g in games.itertuples(index=False):
        if g.game_id not in gi_.index:
            continue
        G = gi_.loc[g.game_id]
        act = m.pg[m.pg.game_id == g.game_id].set_index("pid")
        opp = {g.posteam: g.defteam, g.defteam: g.posteam}
        qbs = {t: starter.get((g.game_id, t)) for t in opp}
        if any(v is None for v in qbs.values()):
            continue
        roster, tier = [], {}
        for t in opp:
            leaders = [pid for pid in m.usage_leaders(t, g.key, min_targets=3, min_carries=6) if pid in act.index]
            depth = [pid for pid in m.active_players(t, g.key) if pid not in leaders and pid not in qbs.values()
                     and (pid in act.index or (ros is not None and (g.key % 100, t, pid) in ros))]
            for pid in leaders + depth:
                tier[pid] = "leader" if pid in leaders else "depth"
                rm = 1.0
                try:
                    inp = m.player_inputs(Player(pid, t), opp[t], g.key)
                    es = m.route_role.expected_share(pid, t, g.key, inp["pos"]) if m.route_role else None
                    if es is not None and inp["t_share"] > 0.01:
                        rm = float(np.clip((0.5 * es + 0.5 * inp["t_share"]) / inp["t_share"], 0.4, 2.5))
                except ValueError:
                    pass
                roster.append(Player(pid, t, share_mult=rm))
        em = None if pd.isna(G.spread_line) else (G.spread_line if g.posteam == G.home_team else -G.spread_line)
        seed = zlib.crc32(g.game_id.encode()) % 2 ** 31
        for v, over in VARIANTS.items():
            for k_, v_ in {**DEFAULTS, **over}.items():
                setattr(m.cfg, k_, v_)
            try:
                sim = m.simulate(g.posteam, g.defteam, g.key, roster, n_sims=sims, seed=seed, exp_margin_a=em, qbs=qbs)
            except (ValueError, KeyError):
                break
            for pid, s in sim["players"].items():
                info = sim["info"][pid]
                stats = []
                if "pass_yds" in s and (g.game_id, pid) in qb_act.index:
                    stats += [(st, float(qb_act.loc[(g.game_id, pid), st])) for st in ("pass_att", "pass_cmp", "pass_yds")]
                if pid in tier and (pid in act.index or ros is not None):
                    stats += [(st, float(act.loc[pid, st]) if pid in act.index else 0.0) for st in
                              (["targets", "rec", "rec_yds"] if info["t_share"] >= 0.06 or tier[pid] == "depth" else []) +
                              (["rush_att", "rush_yds"] if info["c_share"] >= 0.15 or (tier[pid] == "depth" and info["pos"] == "RB") else [])]
                for st, y in stats:
                    x = np.asarray(s[st], dtype=float)
                    rows.append({"variant": v, "season": season, "game_id": g.game_id, "pid": pid, "pos": info["pos"],
                                 "tier": "qb" if st.startswith("pass") else tier.get(pid, "leader"), "stat": st, "y": y,
                                 "crps": crps(x, y), "pit": float((x < y).mean() + _u(g.game_id, pid, st) * (x == y).mean())})
        for k_, v_ in DEFAULTS.items():
            setattr(m.cfg, k_, v_)
    return pd.DataFrame(rows)


def score(paths: list[str]) -> pd.DataFrame:
    d = pd.concat([pd.read_parquet(p) for p in paths])
    key = ["season", "game_id", "pid", "stat"]
    off = d[d.variant == "off"].set_index(key)
    out = []
    for v in [v for v in VARIANTS if v != "off"]:
        on = d[d.variant == v].set_index(key)
        j = off[["crps", "pit", "tier"]].join(on[["crps", "pit"]], rsuffix="_on", how="inner")
        for st in STATS:
            for tr in ("all", "leader", "depth", "qb"):
                x = j[j.index.get_level_values("stat") == st]
                if tr != "all":
                    x = x[x.tier == tr]
                if len(x) < 30:
                    continue
                diff = x.crps_on - x.crps
                sd = diff.std(ddof=1)
                out.append({"variant": v, "stat": st, "tier": tr, "n": len(x), "pct": 100 * (x.crps_on.mean() / x.crps.mean() - 1),
                            "t": diff.mean() / (sd / np.sqrt(len(diff))) if sd > 0 else 0.0,
                            "cov_off": "/".join(f"{100 * (x.pit < q).mean():.1f}" for q in (.1, .5, .9)),
                            "cov_on": "/".join(f"{100 * (x.pit_on < q).mean():.1f}" for q in (.1, .5, .9))})
    return pd.DataFrame(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--weeks", default="4-18")
    ap.add_argument("--sims", type=int, default=2000)
    ap.add_argument("--out")
    ap.add_argument("--score", nargs="+")
    ap.add_argument("--family", default="early_exit", choices=["early_exit", "share", "off", "noise"])
    ap.add_argument("--zero-snaps", action="store_true")
    a = ap.parse_args()
    if a.family != "early_exit":
        VARIANTS.clear(); VARIANTS.update({"share": SHARE, "off": OFFONLY, "noise": NOISE}[a.family])
    if a.score:
        r = score(a.score)
        pd.set_option("display.width", 200)
        print(r.round(3).to_string(index=False))
    else:
        lo, hi = map(int, a.weeks.split("-"))
        df = run(a.season, list(range(lo, hi + 1)), a.sims, a.zero_snaps)
        df.to_parquet(a.out)
        print(f"{a.season}: {df.game_id.nunique()} games, {len(df)} rows -> {a.out}")
