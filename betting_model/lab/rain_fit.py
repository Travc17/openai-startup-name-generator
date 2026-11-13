"""Fit the rain effect on 2019-23 outdoor games (pre-registered 2026-11-12; see reviews/improve_log.md)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent.parent
RAIN = r"rain|shower|drizzle|storm|thunder"
def team_games(seasons):
    out = []
    for s in seasons:
        p = pd.read_parquet(HERE / f"data/pbp_{s}.parquet", columns=["game_id", "season", "season_type", "roof", "weather", "wind",
                                                                    "posteam", "pass_attempt", "rush_attempt", "passing_yards", "sack", "play_type"])
        p = p[(p.season_type == "REG") & p.roof.isin(["outdoors", "open"]) & p.posteam.notna()]
        p["passing_yards"] = p.passing_yards.fillna(0)
        g = p.groupby(["game_id", "season", "posteam"]).agg(att=("pass_attempt", "sum"), rush=("rush_attempt", "sum"),
                                                              pyds=("passing_yards", "sum"), weather=("weather", "first"), wind=("wind", "first")).reset_index()
        out.append(g)
    G = pd.concat(out)
    G["rain"] = G.weather.fillna("").str.contains(RAIN, case=False, regex=True) & ~G.weather.fillna("").str.contains("snow", case=False)
    return G
def fit(seasons):
    G = team_games(seasons)
    per = json.loads((HERE / "nflmodel/weather.json").read_text())["per_mph_above_8"]
    G["ypa"] = G.pyds / G.att.clip(lower=1)
    res = {}
    for col, lev in (("att", "att_r"), ("rush", "rush_r"), ("ypa", "ypa_r")):
        tot = G.groupby(["season", "posteam"])[col].transform("sum"); n = G.groupby(["season", "posteam"])[col].transform("size")
        loo = (tot - G[col]) / (n - 1)                                  # team-season mean of its OTHER outdoor games
        ratio = G[col] / loo
        wfx = 1 + per[lev] * (G.wind.fillna(0) - 8).clip(lower=0)       # remove the tested wind effect
        r = ratio / wfx
        res[lev] = float(r[G.rain].mean() / r[~G.rain].mean() - 1)
        se = float(r[G.rain].std(ddof=1) / np.sqrt(G.rain.sum()))
        print(f"{lev}: {res[lev]:+.3f} (rain team-games {int(G.rain.sum())}, se {se:.3f})")
    return res
if __name__ == "__main__":
    r = fit(range(2019, 2024))
    w = json.loads((HERE / "nflmodel/weather.json").read_text())
    w["rain"] = {**{k: round(v, 4) for k, v in r.items()}, "fitted_on_seasons": list(range(2019, 2024)), "status": "pre-registered test 2026-11-12"}
    (HERE / "nflmodel/weather.json").write_text(json.dumps(w, indent=1))
    print("saved rain block to nflmodel/weather.json")
