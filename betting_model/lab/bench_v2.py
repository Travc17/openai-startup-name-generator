"""Lab bench v2 (2026-11-11): backtests that build every game's roster the way a live report does.

Bench v1 (lab/pff_batch1.py, lab/early_exit_test.py) simulated usage leaders who played: no inactive list, no
next-man-up bump for a starter who sat out, and zero-snap actives dropped. That misstated backups (README Model review
2026-11-11). v2 calls nfl.roster_for (the live code path: usage leaders, depth-chart adds, every skill player with recent
snaps, next-man-up for outs, return multipliers, route-role) with the game's real inactive list from nflverse weekly
rosters (status != ACT = out, known before kickoff), and scores every rostered player who was ACTIVE (0 if no snaps).

    nice -n 19 python lab/bench_v2.py --season 2025 --weeks 4-18 --variants off,n25 --out <scratch>/b2_2025.parquet
    python lab/bench_v2.py --score <files...>
"""
from __future__ import annotations
import argparse, contextlib, io, sys, zlib
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "lab"))
import nfl  # noqa: E402
from nflmodel import data  # noqa: E402
from nflmodel.backtest import crps  # noqa: E402
from nflmodel.game import Player  # noqa: E402
from early_exit_test import score  # noqa: E402  (same paired scoring)
ALL = {"off": {}, "n25": {"role_noise_sigma": 0.25}, "ee": {"early_exit": True}, "both": {"early_exit": True, "role_noise_sigma": 0.25}}
DEFAULTS = {"early_exit": False, "early_exit_scale": 1.0, "share_conc_ref": None, "role_noise_sigma": None}


def _u(*parts) -> float:
    return zlib.crc32("|".join(map(str, parts)).encode()) / 2 ** 32


def run(season: int, weeks: list[int], sims: int, variants: dict) -> pd.DataFrame:
    m = nfl.build_model()
    gi_ = pd.read_parquet(data.DATA_DIR / f"pbp_{season}.parquet", columns=["game_id", "home_team", "away_team", "spread_line"]).drop_duplicates("game_id").set_index("game_id")
    wr = pd.read_parquet(data.DATA_DIR / f"roster_weekly_{season}.parquet", columns=["week", "team", "gsis_id", "status"])
    active = set(map(tuple, wr[wr.status == "ACT"][["week", "team", "gsis_id"]].to_numpy()))
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
        home, away, wk = G.home_team, G.away_team, g.key % 100
        act = m.pg[m.pg.game_id == g.game_id].set_index("pid")
        qbs = {t: starter.get((g.game_id, t)) for t in (home, away)}
        if any(v is None for v in qbs.values()):
            continue
        cand = {t: set(m.usage_leaders(t, g.key)) | set(m.active_players(t, g.key)) for t in (home, away)}
        outs = {pid for t in cand for pid in cand[t] if (wk, t, pid) not in active}
        a = argparse.Namespace(team_a=home, team_b=away, home=home, away=away, out=[], out_pids=outs, mult=[], catch=[],
                               players=None, qb=[], wind=None, date=None, leaders_only=False)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                roster = nfl.roster_for(m, a, g.key, [])
        except (SystemExit, ValueError, KeyError):
            continue
        leaders = {t: set(m.usage_leaders(t, g.key, min_targets=3, min_carries=6)) for t in (home, away)}
        em = None if pd.isna(G.spread_line) else float(G.spread_line)   # nflverse spread_line = expected home margin
        seed = zlib.crc32(g.game_id.encode()) % 2 ** 31
        for v, over in variants.items():
            for k_, v_ in {**DEFAULTS, **over}.items():
                setattr(m.cfg, k_, v_)
            try:
                sim = m.simulate(home, away, g.key, roster, n_sims=sims, seed=seed, exp_margin_a=em, qbs=qbs)
            except (ValueError, KeyError):
                break
            for pid, s in sim["players"].items():
                info = sim["info"][pid]
                t = info["team"]
                stats = []
                if "pass_yds" in s and (g.game_id, pid) in qb_act.index:
                    stats += [(st, float(qb_act.loc[(g.game_id, pid), st]), "qb") for st in ("pass_att", "pass_cmp", "pass_yds")]
                elif info["pos"] in ("RB", "WR", "TE") and (wk, t, pid) in active:
                    tier = "leader" if pid in leaders.get(t, ()) else "depth"
                    sl = (["targets", "rec", "rec_yds"] if info["t_share"] >= 0.06 or tier == "depth" else []) + \
                         (["rush_att", "rush_yds"] if info["c_share"] >= 0.15 or (tier == "depth" and info["pos"] == "RB") else [])
                    stats += [(st, float(act.loc[pid, st]) if pid in act.index else 0.0, tier) for st in sl]
                for st, y, tier in stats:
                    x = np.asarray(s[st], dtype=float)
                    rows.append({"variant": v, "season": season, "game_id": g.game_id, "pid": pid, "pos": info["pos"], "tier": tier,
                                 "stat": st, "y": y, "crps": crps(x, y), "pit": float((x < y).mean() + _u(g.game_id, pid, st) * (x == y).mean())})
        for k_, v_ in DEFAULTS.items():
            setattr(m.cfg, k_, v_)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--weeks", default="4-18")
    ap.add_argument("--sims", type=int, default=1500)
    ap.add_argument("--variants", default="off")
    ap.add_argument("--out")
    ap.add_argument("--score", nargs="+")
    a = ap.parse_args()
    if a.score:
        import early_exit_test as eet
        d = pd.concat([pd.read_parquet(p) for p in a.score])
        eet.VARIANTS.clear(); eet.VARIANTS.update({v: {} for v in d.variant.unique()})
        pd.set_option("display.width", 200)
        print(score(a.score).round(3).to_string(index=False))
    else:
        lo, hi = map(int, a.weeks.split("-"))
        df = run(a.season, list(range(lo, hi + 1)), a.sims, {v: ALL[v] for v in a.variants.split(",")})
        df.to_parquet(a.out)
        print(f"{a.season}: {df.game_id.nunique()} games, {len(df)} rows -> {a.out}")
