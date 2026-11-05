"""Model lab batch 1 (2026-11-05): paired OFF/ON test of the PFF matchup switches in nflmodel/pff_matchups.py.

Same scoring loop as regression_check.py (production model: route-role blend, real starting QB, closing spread for
game script, calibration ON). Every variant of a game uses the same seed, so CRPS differences are paired.

    nice -n 19 python lab/pff_batch1.py --season 2023 --weeks 6-18 --variants off --out fit2023.parquet
    python lab/pff_batch1.py --fit fit2023.parquet          # writes nflmodel/pff_matchups.json (2023 slopes)
    nice -n 19 python lab/pff_batch1.py --season 2024 --weeks 4-18 --out s2024.parquet
    python lab/pff_batch1.py --score s2024.parquet s2025.parquet [--score2 s2026.parquet]
Needs the PFF facets cached in data/pff/ (gitignored, never committed).
"""
from __future__ import annotations

import argparse
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import nfl  # noqa: E402
from nflmodel import data  # noqa: E402
from nflmodel.backtest import crps  # noqa: E402
from nflmodel.game import Player  # noqa: E402
from nflmodel.pff_matchups import COEF_FILE, PFFMatchups  # noqa: E402

SWITCH = {"pass_pro": "pff_pass_pro", "run_block": "pff_run_block", "rb_eff": "pff_rb_eff",
          "coverage": "pff_coverage", "missing_def": "pff_missing_def"}
# F1 with an a priori slope (pressure arithmetic, chosen before any 2024-26 run; see README)
PRIOR = {"pass_pro_prior": ("pff_pass_pro", "pass_pro", {"b_ypt": -0.04, "b_cmp": -0.05})}
ALL = ["off"] + list(SWITCH) + list(PRIOR)
STATS = ["targets", "rec", "rec_yds", "rush_att", "rush_yds", "pass_att", "pass_cmp", "pass_yds"]


def _u(*parts) -> float:
    return zlib.crc32("|".join(map(str, parts)).encode()) / 2 ** 32


def run(season: int, weeks: list[int], variants: list[str], sims: int, split: bool = False,
        coef_key: str = "coef") -> pd.DataFrame:
    m = nfl.build_model()
    m.pffm = PFFMatchups(m, coef_key=coef_key)
    fitted = dict(m.pffm.coef)
    assert fitted or variants == ["off"], "no pff_matchups.json: run --fit first"
    gi_ = pd.read_parquet(data.DATA_DIR / f"pbp_{season}.parquet",
                          columns=["game_id", "home_team", "spread_line"]).drop_duplicates("game_id").set_index("game_id")
    P = m.qbm.p
    starter = (P[P.key // 100 == season].groupby(["game_id", "posteam", "passer_player_id"]).size().rename("att")
               .reset_index().sort_values("att").drop_duplicates(["game_id", "posteam"], keep="last")
               .set_index(["game_id", "posteam"]).passer_player_id)
    qb_act = P.groupby(["game_id", "passer_player_id"]).agg(
        pass_att=("yards", "size"), pass_cmp=("complete", "sum"), pass_yds=("yards", "sum"))
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
        roster = []
        for t in opp:
            for pid in m.usage_leaders(t, g.key, min_targets=3, min_carries=6):
                if pid not in act.index:
                    continue
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
        X = {t: {"x_pp": m.pffm.x_pass_pro(t, opp[t], g.key), "x_rb": m.pffm.x_run_block(t, opp[t], g.key),
                 "x_md": m.pffm.x_missing_def(opp[t], g.key),
                 **{f"x_cov_{p}": m.pffm.x_coverage(opp[t], g.key, p) for p in ("WR", "TE", "RB")}} for t in opp}
        seed = zlib.crc32(g.game_id.encode()) % 2 ** 31
        for v in variants:
            for sw in SWITCH.values():
                setattr(m.cfg, sw, False)
            m.pffm.coef = dict(fitted)
            if v in PRIOR:
                sw, fam, c = PRIOR[v]
                setattr(m.cfg, sw, True)
                m.pffm.coef[fam] = {**fitted[fam], **c}
            elif v != "off":
                setattr(m.cfg, SWITCH[v], True)
            # split=True: simulate twice (each team first once) and keep only the first team's rows, so a lever on
            # one team cannot shift the random stream of the rows being compared (tighter pairing, same marginals)
            orders = [(g.posteam, g.defteam, em)] + ([(g.defteam, g.posteam, None if em is None else -em)] if split else [])
            sims_out = []
            try:
                for ta, tb, e in orders:
                    sims_out.append((ta, m.simulate(ta, tb, g.key, roster, n_sims=sims, seed=seed, exp_margin_a=e, qbs=qbs)))
            except (ValueError, KeyError):
                break
            for ta, sim in sims_out:
                for pid, s in sim["players"].items():
                    info = sim["info"][pid]
                    t = info["team"]
                    if split and t != ta:
                        continue
                    base = {"variant": v, "game_id": g.game_id, "key": g.key, "team": t, "pid": pid, "pos": info["pos"],
                            **X[t], "x_eff": m.pffm.x_rb_eff(pid, g.key) if info["pos"] == "RB" else 0.0}
                    stats = []
                    if "pass_yds" in s and (g.game_id, pid) in qb_act.index:
                        stats += [(st, float(qb_act.loc[(g.game_id, pid), st])) for st in ("pass_att", "pass_cmp", "pass_yds")]
                    if pid in act.index:
                        stats += [(st, float(act.loc[pid, st])) for st in
                                  (["targets", "rec", "rec_yds"] if info["t_share"] >= 0.06 else []) +
                                  (["rush_att", "rush_yds"] if info["c_share"] >= 0.15 else [])]
                    for st, y in stats:
                        x = np.asarray(s[st], dtype=float)
                        u = _u(g.game_id, pid, st)
                        rows.append({**base, "stat": st, "y": y, "mean": float(x.mean()), "crps": crps(x, y),
                                     "pit": float((x < y).mean() + u * (x == y).mean())})
        for sw in SWITCH.values():
            setattr(m.cfg, sw, False)
    return pd.DataFrame(rows)


# ---------------- fit (2023 only) ----------------
def _wls(x, r, w):
    X = np.column_stack([np.ones(len(x)), x])
    W = w / w.sum()
    beta = np.linalg.solve(X.T @ (X * W[:, None]), X.T @ (W * r))
    res = r - X @ beta
    cov = np.linalg.inv(X.T @ (X * w[:, None])) * (w * res ** 2).sum() / (len(x) - 2)
    return float(beta[1]), float(np.sqrt(cov[1, 1])), len(x)


def fit(path: str) -> dict:
    d = pd.read_parquet(path)
    d = d[d.variant == "off"]
    wide = d.pivot_table(index=["game_id", "pid"], columns="stat", values=["y", "mean"])
    xs = d.drop_duplicates(["game_id", "pid"]).set_index(["game_id", "pid"])[
        ["pos", "x_pp", "x_rb", "x_md", "x_eff", "x_cov_WR", "x_cov_TE", "x_cov_RB"]]
    W = pd.concat([wide["y"].add_prefix("y_"), wide["mean"].add_prefix("m_"), xs], axis=1)
    clip = lambda r: np.clip(r, -1.0, 2.0)   # a priori winsorizing of relative residuals
    out = {}
    q = W.dropna(subset=["y_pass_att"])
    q = q[q.y_pass_att > 0]
    r_ypa = clip((q.y_pass_yds / q.y_pass_att) / (q.m_pass_yds / q.m_pass_att) - 1)
    r_cmp = clip((q.y_pass_cmp / q.y_pass_att) / (q.m_pass_cmp / q.m_pass_att) - 1)
    by, sy, n = _wls(q.x_pp.to_numpy(), r_ypa.to_numpy(), q.y_pass_att.to_numpy())
    bc, sc, _ = _wls(q.x_pp.to_numpy(), r_cmp.to_numpy(), q.y_pass_att.to_numpy())
    out["pass_pro"] = {"b_ypt": by, "se_ypt": sy, "b_cmp": bc, "se_cmp": sc, "n": n, "unit": "logit pressure rate"}
    rb = W[(W.pos == "RB")].dropna(subset=["y_rush_att"])
    rb = rb[(rb.y_rush_att > 0) & (rb.m_rush_att > 0)]
    r_ypc = clip((rb.y_rush_yds / rb.y_rush_att) / (rb.m_rush_yds / rb.m_rush_att) - 1)
    b, s, n = _wls(rb.x_rb.to_numpy(), r_ypc.to_numpy(), rb.y_rush_att.to_numpy())
    out["run_block"] = {"b": b, "se": s, "n": n, "unit": "PFF grade points"}
    b, s, n = _wls(rb.x_eff.to_numpy(), r_ypc.to_numpy(), rb.y_rush_att.to_numpy())
    out["rb_eff"] = {"b": b, "se": s, "n": n, "unit": "yards after contact per attempt"}
    rc = W.dropna(subset=["y_targets"])
    rc = rc[(rc.y_targets > 0) & (rc.m_targets > 0) & (rc.m_rec_yds > 0)]
    xc = np.where(rc.pos == "TE", rc.x_cov_TE, np.where(rc.pos == "RB", rc.x_cov_RB, rc.x_cov_WR))
    r_ypt = clip((rc.y_rec_yds / rc.y_targets) / (rc.m_rec_yds / rc.m_targets) - 1)
    b, s, n = _wls(xc, r_ypt.to_numpy(), rc.y_targets.to_numpy())
    out["coverage"] = {"b": b, "se": s, "n": n, "unit": "PFF coverage grade points"}
    by, sy, n = _wls(q.x_md.to_numpy(), r_ypa.to_numpy(), q.y_pass_att.to_numpy())
    bc, sc, n2 = _wls(rb.x_md.to_numpy(), r_ypc.to_numpy(), rb.y_rush_att.to_numpy())
    out["missing_def"] = {"b_ypt": by, "se_ypt": sy, "b_ypc": bc, "se_ypc": sc, "n_qb": n, "n_rb": n2,
                          "unit": "snap share x (grade - 60)/10"}
    return out


# ---------------- paired score ----------------
def score(paths: list[str]) -> pd.DataFrame:
    d = pd.concat([pd.read_parquet(p) for p in paths])
    off = d[d.variant == "off"].set_index(["game_id", "pid", "stat"])
    out = []
    for v in [v for v in d.variant.unique() if v != "off"]:
        on = d[d.variant == v].set_index(["game_id", "pid", "stat"])
        j = off[["crps", "pit"]].join(on[["crps", "pit"]], rsuffix="_on", how="inner")
        for st in STATS:
            x = j.xs(st, level="stat") if st in j.index.get_level_values("stat") else None
            if x is None or x.empty:
                continue
            diff = x.crps_on - x.crps
            sd = diff.std(ddof=1)
            t = diff.mean() / (sd / np.sqrt(len(diff))) if sd > 0 else 0.0
            out.append({"variant": v, "stat": st, "n": len(x), "crps_off": x.crps.mean(), "crps_on": x.crps_on.mean(),
                        "pct": 100 * (x.crps_on.mean() / x.crps.mean() - 1), "t": t,
                        "cov_off": "/".join(f"{100 * (x.pit < q).mean():.1f}" for q in (.1, .5, .9)),
                        "cov_on": "/".join(f"{100 * (x.pit_on < q).mean():.1f}" for q in (.1, .5, .9))})
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--weeks", default="4-18")
    ap.add_argument("--variants", default=",".join(ALL))
    ap.add_argument("--sims", type=int, default=2000)
    ap.add_argument("--out")
    ap.add_argument("--fit")
    ap.add_argument("--score", nargs="+")
    ap.add_argument("--split", action="store_true", help="each team simulated first once; keep only first-team rows")
    ap.add_argument("--coef-key", default="coef", help='"coef" (2023 fit) or "coef_2023_24" (secondary refit)')
    ap.add_argument("--fit-key", default="coef", help="key --fit writes into pff_matchups.json")
    ap.add_argument("--fit-label", default="2023 weeks 6-18")
    a = ap.parse_args()
    if a.fit:
        coef = fit(a.fit)
        cur = json.loads(COEF_FILE.read_text()) if COEF_FILE.exists() else {}
        cur[a.fit_key] = coef
        cur[a.fit_key.replace("coef", "fitted_on")] = f"{a.fit_label} (production-model residuals, lab/pff_batch1.py --fit)"
        COEF_FILE.write_text(json.dumps(cur, indent=1) + "\n")
        print(json.dumps(coef, indent=1))
        return
    if a.score:
        pd.set_option("display.width", 200)
        print(score(a.score).to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        return
    lo, hi = map(int, a.weeks.split("-"))
    df = run(a.season, list(range(lo, hi + 1)), a.variants.split(","), a.sims, a.split, a.coef_key)
    df.to_parquet(a.out)
    print(f"{a.season} wk {a.weeks}: {df.game_id.nunique()} games, {len(df)} rows -> {a.out}")


if __name__ == "__main__":
    main()
