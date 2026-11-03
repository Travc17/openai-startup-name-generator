"""Route-based role from PFF weekly receiving data (routes run per player).

Expected target share = recent route participation (routes / team dropbacks, last 3 games)
                        x targets per route run (longer history, shrunk to position mean)
                        / team targets per dropback.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DATA_DIR


def load(model_pg_seasons):
    df = pd.read_parquet(DATA_DIR / "pff" / "receiving_weekly.parquet")
    pl = pd.read_parquet(DATA_DIR / "players.parquet", columns=["gsis_id", "pff_id"]).dropna()
    pl["pff_id"] = pl.pff_id.astype(float).astype(int)
    df = df.merge(pl, left_on="player_id", right_on="pff_id")
    df["key"] = df.season * 100 + df.week
    frames = []
    for y in model_pg_seasons:
        d = pd.read_parquet(DATA_DIR / f"pbp_{y}.parquet", columns=["season", "week", "season_type", "posteam", "qb_dropback", "play_type", "pass_attempt", "receiver_player_id", "two_point_attempt"])
        d = d[d.season_type == "REG"]
        db = d[d.qb_dropback == 1].groupby(["season", "week", "posteam"]).size().rename("dropbacks")
        tg = d[(d.play_type == "pass") & (d.pass_attempt == 1) & d.receiver_player_id.notna() & (d.two_point_attempt != 1)].groupby(["season", "week", "posteam"]).size().rename("team_targets")
        frames.append(pd.concat([db, tg], axis=1).reset_index())
    team = pd.concat(frames)
    # a player's team that week = the team whose games he appears in; use nflverse player games for that
    return df[["gsis_id", "key", "season", "week", "routes", "targets", "position"]], team


class RouteRole:
    def __init__(self, pff, team, pg):
        pg = pg[["pid", "key", "posteam"]].drop_duplicates(["pid", "key"])
        x = pff.merge(pg, left_on=["gsis_id", "key"], right_on=["pid", "key"])
        team["key"] = team.season * 100 + team.week
        x = x.merge(team[["key", "posteam", "dropbacks", "team_targets"]], on=["key", "posteam"])
        x["rp"] = (x.routes / x.dropbacks).clip(0, 1.1)
        self.x = x.sort_values("key")
        self._by = {k: v for k, v in self.x.groupby("gsis_id")}
        self.team = team

    def expected_share(self, pid, team, key, pos, k_routes=60):
        h = self._by.get(pid)
        if h is None:
            return None
        h = h[h.key < key]
        if len(h) < 2:
            return None
        rp = np.average(h.tail(3).rp, weights=np.arange(1, len(h.tail(3)) + 1))
        hh = h.tail(30)
        lg = self.x[(self.x.key < key) & (self.x.key >= key - 200) & (self.x.position == pos)]
        lg_tprr = lg.targets.sum() / max(lg.routes.sum(), 1)
        tprr = (hh.targets.sum() + k_routes * lg_tprr) / (hh.routes.sum() + k_routes)
        t = self.team[(self.team.posteam == team) & (self.team.key < key)].tail(8)
        ratio = t.team_targets.sum() / max(t.dropbacks.sum(), 1)
        return float(rp * tprr / max(ratio, 0.3))   # player targets per team target = (routes/dropback * targets/route) / (team targets/dropback)


def refresh_pff(season: int, weeks: range = range(1, 19)) -> int:
    """Pull PFF weekly receiving summaries for a season via api.pff.com (key injected by the environment)."""
    import json, time, urllib.request
    out_dir = DATA_DIR / "pff"
    out_dir.mkdir(exist_ok=True)
    rows, n = [], 0
    for w in weeks:
        url = f"https://api.pff.com/v1/facet/receiving/summary?league=nfl&season={season}&week={w}"
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                d = json.load(r).get("receiving_summary", [])
        except Exception:
            continue
        if not d:
            continue
        (out_dir / f"rs_{season}_w{w}.json").write_text(json.dumps({"receiving_summary": d}))
        n += 1
        time.sleep(0.4)
    import glob
    allrows = []
    for f in glob.glob(str(out_dir / "rs_*.json")):
        s_, w_ = f.rsplit("/", 1)[1][3:-5].split("_w")
        for r in json.load(open(f))["receiving_summary"]:
            allrows.append({**{k: r.get(k) for k in ("player", "player_id", "team_name", "position", "routes", "route_rate", "pass_plays",
                                                    "targets", "receptions", "yards", "yprr", "slot_rate", "avg_depth_of_target")},
                            "season": int(s_), "week": int(w_)})
    pd.DataFrame(allrows).to_parquet(out_dir / "receiving_weekly.parquet")
    return n
