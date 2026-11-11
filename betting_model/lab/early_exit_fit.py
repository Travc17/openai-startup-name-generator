"""Early-exit rates for the sim (model lab 2026-11-11). Fit ONLY on 2019-2023 play by play (scored seasons: 2024-26).

An exit = the play-by-play text says "<TEAM>-<#>-<Name> was injured during the play" and no later "has returned to the
game" note for that player in the same game. Rate = exits / player-games with an offensive touch, by position.
Exit time = share of the game already played at the injury (from game_seconds_remaining). Writes nflmodel/early_exit.json.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from nflmodel import data  # noqa: E402
INJ = re.compile(r"([A-Z]{2,3})-\d+-([A-Z][A-Za-z.'\- ]*?) was injured during the play")
BACK = re.compile(r"([A-Z]{2,3})-\d+-([A-Z][A-Za-z.'\- ]*?) has returned to the game")
SEASONS = range(2019, 2024)
pos_map = data.load_positions()
rows, pg_count = [], {"RB": 0, "WR": 0, "TE": 0}
for y in SEASONS:
    pb = pd.read_parquet(data.DATA_DIR / f"pbp_{y}.parquet", columns=["game_id", "season_type", "posteam", "desc", "game_seconds_remaining",
                                                                       "rusher_player_name", "rusher_player_id", "receiver_player_name", "receiver_player_id"])
    pb = pb[pb.season_type == "REG"]
    t = pd.concat([pb[["game_id", "posteam", "rusher_player_name", "rusher_player_id"]].set_axis(["game_id", "team", "name", "pid"], axis=1),
                   pb[["game_id", "posteam", "receiver_player_name", "receiver_player_id"]].set_axis(["game_id", "team", "name", "pid"], axis=1)]).dropna()
    pgames = t.drop_duplicates(["game_id", "pid"]).assign(pos=lambda d: d.pid.map(pos_map))
    for p in pg_count:
        pg_count[p] += int((pgames.pos == p).sum())
    names = pgames.set_index(["game_id", "team", "name"])
    for gid, g in pb.groupby("game_id"):
        hurt, back = {}, set()
        for r in g[g.desc.str.contains("injured during the play|has returned", na=False)].itertuples():
            for tm, nm in INJ.findall(r.desc):
                hurt.setdefault((tm, nm.strip()), r.game_seconds_remaining)
            for tm, nm in BACK.findall(r.desc):
                back.add((tm, nm.strip()))
        for (tm, nm), gsr in hurt.items():
            if (tm, nm) in back:
                continue
            k = (gid, tm, nm)
            if k in names.index:
                pos = names.loc[k].pos
                pos = pos.iloc[0] if isinstance(pos, pd.Series) else pos
                if pos in pg_count:
                    rows.append((y, pos, float(np.clip(1 - gsr / 3600, 0, 1))))
d = pd.DataFrame(rows, columns=["season", "pos", "played"])
out = {"fit_seasons": [min(SEASONS), max(SEASONS)], "definition": __doc__.strip().split("\n")[2],
       "p": {p: round(float((d.pos == p).sum() / pg_count[p]), 4) for p in pg_count},
       "n_exits": {p: int((d.pos == p).sum()) for p in pg_count}, "player_games": pg_count,
       "played_quantiles": [round(float(q), 3) for q in np.quantile(d.played, np.linspace(0.025, 0.975, 20))]}
Path(HERE / "nflmodel" / "early_exit.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
