"""Rain test (pre-registered 2026-11-12): 2024-26 rain games, production+wind vs production+wind+rain, paired seeds."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "lab"))
import bench_v2
RAIN = r"rain|shower|drizzle|storm|thunder"
def rain_games(season):
    p = pd.read_parquet(HERE / f"data/pbp_{season}.parquet", columns=["game_id", "season_type", "roof", "weather", "wind"]).drop_duplicates("game_id")
    p = p[(p.season_type == "REG") & p.roof.isin(["outdoors", "open"])]
    w = p.weather.fillna("")
    r = p[w.str.contains(RAIN, case=False, regex=True) & ~w.str.contains("snow", case=False)]
    return {g: {"rain": True, "wind": (float(x) if pd.notna(x) else None)} for g, x in zip(r.game_id, r.wind)}
if __name__ == "__main__":
    season, out = int(sys.argv[1]), sys.argv[2]
    W = rain_games(season)
    loso = len(sys.argv) > 3 and sys.argv[3] == "--loso"
    variants = {k: dict(bench_v2.ALL[k]) for k in ("prodw", "rainw")}
    if loso:                                            # constants fit on every OTHER season 2019-26
        import rain_fit
        rp = rain_fit.fit([s for s in range(2019, 2027) if s != season])
        variants["rainw"]["rain_override"] = rp
        print(f"{season}: LOSO rain constants {rp}")
    d = bench_v2.run(season, list(range(1, 19)), 2000, variants, only=set(W), weather=W)
    d.to_parquet(out); print(f"{season}: {len(W)} rain games, {d.game_id.nunique()} benched, {len(d)} rows -> {out}")
