"""Paired score of one bench v2 variant against production, per season and pooled, plus the QB-change slice.

    python lab/score_vs_prod.py qvc8 <bench parquet files...>

QB-change slice: team-games whose starting QB (most attempts) differs from that team's starter in its previous game,
or whose starter started under half of the team's earlier games that season (the games a QB-volume feature targets).
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from nflmodel import data  # noqa: E402

v, files = sys.argv[1], sys.argv[2:]
d = pd.concat([pd.read_parquet(f) for f in files])
key = ["season", "game_id", "pid", "stat"]
base = d[d.variant == "prod"].set_index(key)
on = d[d.variant == v].set_index(key)
j = base[["crps", "pit", "tier", "pos"]].join(on[["crps", "pit"]], rsuffix="_on", how="inner").reset_index()

# QB-change team-games from play by play; map each scored player to his team via the bench's pid -> posteam per game
chg = set()
team_of = {}
for s in sorted(j.season.unique()):
    p = pd.read_parquet(data.DATA_DIR / f"pbp_{s}.parquet", columns=["game_id", "week", "season_type", "posteam", "passer_player_id",
                                                                     "receiver_player_id", "rusher_player_id", "pass_attempt"])
    p = p[(p.season_type == "REG") & p.posteam.notna()]
    st = p[p.pass_attempt == 1].groupby(["game_id", "posteam"]).passer_player_id.agg(lambda x: x.value_counts().idxmax()).reset_index()
    st["week"] = st.game_id.str.split("_").str[1].astype(int)
    for t, g in st.sort_values("week").groupby("posteam"):
        prev = []
        for r in g.itertuples():
            if prev and (r.passer_player_id != prev[-1] or sum(q == r.passer_player_id for q in prev) < 0.5 * len(prev)):
                chg.add((r.game_id, t))
            prev.append(r.passer_player_id)
    for col in ("passer_player_id", "receiver_player_id", "rusher_player_id"):
        x = p[p[col].notna()][["game_id", "posteam", col]].drop_duplicates()
        team_of.update({(a, b): c for a, c, b in x.itertuples(index=False)})
j["team"] = [team_of.get((g, pid)) for g, pid in zip(j.game_id, j.pid)]
j["qbchg"] = [(g, t) in chg for g, t in zip(j.game_id, j.team)]

rows = []
for scope, x0 in [("pooled", j)] + [(str(s), j[j.season == s]) for s in sorted(j.season.unique())] + [("QB-change games", j[j.qbchg])]:
    for st in ["targets", "rec", "rec_yds", "rush_att", "rush_yds", "pass_att", "pass_cmp", "pass_yds"]:
        x = x0[x0.stat == st]
        if len(x) < 30:
            continue
        diff = x.crps_on - x.crps
        sd = diff.std(ddof=1)
        rows.append({"scope": scope, "stat": st, "n": len(x), "pct": 100 * (x.crps_on.mean() / x.crps.mean() - 1),
                     "t": diff.mean() / (sd / np.sqrt(len(diff))) if sd > 0 else 0.0,
                     "cov_prod": "/".join(f"{100 * (x.pit < q).mean():.1f}" for q in (.1, .5, .9)),
                     "cov_on": "/".join(f"{100 * (x.pit_on < q).mean():.1f}" for q in (.1, .5, .9))})
R = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(R.round(3).to_string(index=False))
print(f"\nQB-change team-games in sample: {len({(g, t) for g, t in zip(j[j.qbchg].game_id, j[j.qbchg].team)})}")
