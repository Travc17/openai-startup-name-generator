"""Layer 1: projections only. No prices, no venues.

The model's output for one game, saved as a file any pricing layer can read:
for every player and stat, the mean, the 10/25/50/75/90th percentiles, and the chance of
reaching every value on a half-yard grid ("ge": P(stat >= k)).

    over 64.5 (a book line)        = ge[65]   (results are whole numbers: over 64.5 = 65 or more)
    "65+" (a Robinhood rung)       = ge[65]
    over 64 (whole-number line)    = win ge[65], push ge[64] - ge[65]

Nothing here knows about Robinhood, DraftKings, or fees; see market.py for that.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np

STATS = ("targets", "rec", "rec_yds", "rush_att", "rush_yds", "rec_rush_yds")
QB_STATS = ("pass_att", "pass_cmp", "pass_yds", "pass_td", "int", "rush_yds")


def _ladder(v: np.ndarray) -> dict:
    lo = np.floor(v.min() * 2) / 2
    hi = np.ceil(v.max() * 2) / 2
    ge = {}
    for k in np.arange(lo, hi + 0.5, 0.5):
        p = float((v >= k).mean())
        if p >= 0.9995 and ge:          # still certain: keep only the last such point
            ge.clear()
        ge[f"{k:g}"] = round(p, 4)
        if p <= 0.0005:
            break
    return {"mean": round(float(v.mean()), 2),
            "q": [round(float(np.percentile(v, q)), 1) for q in (10, 25, 50, 75, 90)], "ge": ge}


def export(sim: dict, name_of, home: str, away: str, key: int, meta: dict | None = None) -> dict:
    out = {"game": f"{away}@{home}", "key": int(key), "made_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "sims": int(len(next(iter(sim["players"].values()))["targets"])), "meta": meta or {}, "players": {}}
    for pid, s in sim["players"].items():
        info = sim["info"][pid]
        if "pass_yds" in s:
            stats = QB_STATS
        else:
            stats = [st for st in STATS
                     if (st in ("targets", "rec", "rec_yds") and s["targets"].mean() >= 0.8)
                     or (st in ("rush_att", "rush_yds") and s["rush_att"].mean() >= 1.5)
                     or (st == "rec_rush_yds" and (s["targets"].mean() >= 0.8 or s["rush_att"].mean() >= 1.5))]
        if not stats:
            continue
        out["players"][name_of(pid)] = {"pid": pid, "team": info["team"], "pos": info.get("pos", "QB"),
                                        "stats": {st: _ladder(np.asarray(s[st], dtype=float)) for st in stats if st in s}}
    return out


def save(proj: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(proj, f, separators=(",", ":"))


def load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def ge(stat: dict, k: float) -> float:
    """P(stat >= k) from a saved ladder (k on the half grid; off-grid k rounds up to the grid)."""
    g = stat["ge"]
    k2 = np.ceil(k * 2) / 2
    key = f"{k2:g}"
    if key in g:
        return g[key]
    ks = sorted(float(x) for x in g)
    return 1.0 if k2 < ks[0] else 0.0


def p_over(stat: dict, line: float) -> tuple[float, float]:
    """(win, push) for OVER a book line. Results are whole numbers, so over 64.5 means 65 or more:
    the same P(stat >= 65) the report uses for a "65+" rung (and the calibration maps were fit on).
    Half lines never push; over 64 wins at 65+ and pushes at exactly 64."""
    if float(line).is_integer():
        win = ge(stat, line + 1)
        return win, ge(stat, line) - win
    return ge(stat, np.ceil(line)), 0.0
