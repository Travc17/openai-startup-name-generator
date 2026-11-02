"""Walk forward backtest: project every qualifying player game using only prior data.

There are no free historical prop lines, so this tests CALIBRATION, not profit:
  * Quantile coverage: actual yards should land below the model's 10th / 25th /
    50th / 75th / 90th percentile about 10 / 25 / 50 / 75 / 90% of the time.
    This is what makes alternate line probabilities trustworthy.
  * Proxy line: a stand in for the book's line (the player's recency weighted
    average, rounded to .5). We score P(over) with Brier score vs a coin flip.
Beating the proxy is necessary, not sufficient. Real books set sharper lines.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .model import ReceivingModel, _decay_weights

QS = [0.10, 0.25, 0.50, 0.75, 0.90]


def run(model: ReceivingModel, seasons: list[int], min_week: int = 4,
        min_recent_targets: float = 5.0, n_sims: int = 4000, limit: int | None = None) -> pd.DataFrame:
    pg = model.pg
    cand = pg[pg.season.isin(seasons) & (pg.week >= min_week)]
    rows = []
    for r in cand.itertuples(index=False):
        hist = model._pg_by_player[r.receiver_player_id]
        hist = hist[hist.key < r.key].tail(3)
        if len(hist) < 3 or hist.targets.mean() < min_recent_targets:
            continue
        try:
            out = model.project(r.receiver_player_id, r.posteam, r.defteam, r.key, n_sims=n_sims, seed=None)
        except (ValueError, KeyError):
            continue
        sims = out["sims"]
        h6 = model._pg_by_player[r.receiver_player_id]
        h6 = h6[h6.key < r.key].tail(8)
        proxy = round(np.average(h6.yards, weights=_decay_weights(h6.key.to_numpy(), model.cfg)) * 2) / 2
        proxy = np.floor(proxy) + 0.5  # always a half line, no pushes
        rows.append({
            "season": r.season, "week": r.week, "player_id": r.receiver_player_id,
            "team": r.posteam, "opp": r.defteam, "actual": r.yards,
            "median": float(np.median(sims)), "mean": float(sims.mean()),
            **{f"q{int(q*100)}": float(np.quantile(sims, q)) for q in QS},
            "proxy_line": proxy, "p_over_proxy": float((sims > proxy).mean()),
            "naive_mean": float(h6.yards.mean()),
        })
        if limit and len(rows) >= limit:
            break
    return pd.DataFrame(rows)


def report(df: pd.DataFrame) -> str:
    out = [f"Player games tested: {len(df)}"]
    out.append("\nQuantile coverage (target vs actual share of games below model quantile):")
    for q in QS:
        cov = (df.actual < df[f"q{int(q*100)}"]).mean()
        out.append(f"  {int(q*100):>3}th pct: target {q:.0%}  actual {cov:.1%}")
    hit = (df.actual > df.proxy_line).astype(float)
    brier_model = ((df.p_over_proxy - hit) ** 2).mean()
    brier_coin = ((0.5 - hit) ** 2).mean()
    out.append(f"\nProxy line over rate: {hit.mean():.1%}")
    out.append(f"Brier score  model {brier_model:.4f}  vs coin flip {brier_coin:.4f}  "
               f"(lower is better, skill {1 - brier_model / brier_coin:+.2%})")
    out.append("\nCalibration of P(over proxy):")
    bins = pd.cut(df.p_over_proxy, [0, .3, .4, .45, .5, .55, .6, .7, 1])
    cal = df.assign(hit=hit).groupby(bins, observed=True).agg(n=("hit", "size"), predicted=("p_over_proxy", "mean"), actual=("hit", "mean"))
    for b, r in cal.iterrows():
        out.append(f"  {str(b):>12}  n={int(r.n):>5}  predicted {r.predicted:.1%}  actual {r.actual:.1%}")
    mae_m = (df["median"] - df.actual).abs().mean()
    mae_n = (df.naive_mean - df.actual).abs().mean()
    out.append(f"\nMedian abs error  model median {mae_m:.1f} yds  vs naive recent mean {mae_n:.1f} yds")
    return "\n".join(out)
