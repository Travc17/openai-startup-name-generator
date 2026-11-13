"""Rerun the exact 25,000-game simulation behind a saved projections file.

The projections file stores every manual input (meta.adjustments) plus the market spread and total,
so the same seed (7) and inputs give back the same 25,000 simulated games. `check()` proves it by
comparing medians against the saved file before anything downstream uses the draws.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import nfl  # noqa: E402
from nflmodel import projections, scores  # noqa: E402
from nflmodel.game import Player  # noqa: E402


def rerun(proj_path: str) -> dict:
    proj = projections.load(proj_path)
    meta, adj = proj["meta"], proj["meta"].get("adjustments", {})
    away, home = proj["game"].split("@")
    key = int(proj["key"])
    n_sims = int(adj.get("sims") or proj["sims"])

    model = nfl.build_model()
    a = argparse.Namespace(team_a=home, team_b=away, home=home, away=away, season=key // 100, week=key % 100,
                           out=adj.get("out") or [], mult=adj.get("mult") or [], catch=adj.get("catch") or [],
                           players=None, qb=adj.get("qb_override") or [], wind=meta.get("wind"))
    saved_pids = {v["pid"] for v in proj["players"].values()}
    roster = nfl.roster_for(model, a, key, [])
    have = {p.pid for p in roster}
    qbs = {t: model.qbm.starter(t, key) for t in (home, away)}
    for spec in a.qb:
        t, n = spec.split("=", 1)
        qbs[t.upper()] = nfl.lookup(model, n)[0]
    # players named with --players at report time are not stored; add any saved player the roster lacks
    # keep the projections file's player order: a set here reorders 2+ --players adds and shifts the draws
    # (BUF at MIN 2026-11-09 final pass: Sherfield + Shavers replay mismatch)
    extra = [v["pid"] for v in proj["players"].values() if v["pid"] not in have and v["pid"] not in qbs.values()]
    if extra:
        roster = nfl.roster_for(model, a, key, extra)
    for t, q in qbs.items():
        if q and q in model._pg_by and q not in [p.pid for p in roster]:
            roster.append(Player(q, t))

    fav, spread, total = meta.get("fav"), meta.get("spread"), meta.get("total")
    margin_home = (spread if fav == home else -spread) if (fav and spread is not None) else None
    sim = model.simulate(home, away, key, roster, n_sims=n_sims, seed=7, exp_margin_a=margin_home,
                         qbs=qbs, wind=meta.get("wind"), rain=bool(meta.get("rain")))
    gs = None
    if fav and spread is not None and total is not None:
        g, _ = scores.load_games(sorted({key // 100 - i for i in range(5)}))
        resid = scores.market_residuals(g, key // 100 + 1)
        gs = scores.market_simulate(spread if fav == home else -spread, total, resid, n=n_sims)
    return {"proj": proj, "home": home, "away": away, "key": key, "sim": sim, "score": gs, "model": model,
            "names": {pid: nfl.name_of(pid) for pid in sim["players"]}}


def check(run: dict) -> list[str]:
    """Saved median vs rerun median for every saved player stat. Returns mismatch lines (empty = exact)."""
    bad = []
    by_pid = {pid: s for pid, s in run["sim"]["players"].items()}
    for name, pl in run["proj"]["players"].items():
        s = by_pid.get(pl["pid"])
        if s is None:
            bad.append(f"{name}: missing from rerun")
            continue
        for st, lad in pl["stats"].items():
            if st not in s:
                continue
            saved = [round(x, 1) for x in lad["q"]]
            now = [round(float(np.percentile(np.asarray(s[st], float), q)), 1) for q in (10, 25, 50, 75, 90)]
            if lad.get("mean") is not None and abs(float(np.mean(s[st])) - lad["mean"]) > 0.01 or saved != now:
                bad.append(f"{name} {st}: saved mean {lad.get('mean')} q {saved} vs rerun mean {np.mean(s[st]):.2f} q {now}")
    return bad


if __name__ == "__main__":
    r = rerun(sys.argv[1])
    bad = check(r)
    print("Rerun matches saved projections exactly." if not bad else "MISMATCH:\n" + "\n".join(bad))
