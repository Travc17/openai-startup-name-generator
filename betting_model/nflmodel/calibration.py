"""Per-stat calibration map (quantile recalibration).

From walk-forward backtests we know, for each stat, how often the actual result fell below the
model's u-quantile: G(u). A calibrated sample keeps each simulated value's rank u but replaces it
with the model's quantile at G^-1(u). Monotone per stat, so the joint (parlay) structure of the
simulated games is preserved.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

CAL_FILE = Path(__file__).with_name("calibration.json")
GRID = np.linspace(0, 1, 21)


def fit(pits_by_stat: dict[str, np.ndarray], smooth: float = 0.5) -> dict:
    out = {}
    for st, p in pits_by_stat.items():
        p = np.asarray(p)
        g = np.array([(p <= u).mean() for u in GRID])
        g = smooth * g + (1 - smooth) * GRID          # shrink toward identity (no change)
        g = np.maximum.accumulate(g); g[0], g[-1] = 0.0, 1.0
        out[st] = g.round(4).tolist()
    return out


def g_inv(gvals, v):
    """Inverse of the calibration curve (G(u) -> u)."""
    return np.interp(v, gvals, GRID)


def apply(sims: dict, cal: dict, rng=None) -> dict:
    """Recalibrate each stat array in a player's sims dict in place (rank preserving)."""
    for st, gvals in cal.items():
        if st not in sims:
            continue
        x = np.asarray(sims[st], dtype=float)
        n = len(x)
        order = np.argsort(x + (rng.uniform(0, 1e-6, n) if rng is not None else 0), kind="stable")
        u = (np.arange(n) + 0.5) / n
        new_levels = g_inv(np.asarray(gvals), u)
        srt = np.sort(x)
        newvals = np.interp(new_levels * (n - 1), np.arange(n), srt)
        if st in ("targets", "rec", "rush_att", "pass_att", "pass_cmp", "pass_td", "int"):
            newvals = np.rint(newvals)
        out = np.empty(n); out[order] = newvals
        sims[st] = out
    return sims


def save(cal: dict, seasons) -> None:
    CAL_FILE.write_text(json.dumps({"fitted_on_seasons": list(seasons), "maps": cal}, indent=1) + "\n")


def load() -> dict:
    return json.loads(CAL_FILE.read_text())["maps"] if CAL_FILE.exists() else {}
