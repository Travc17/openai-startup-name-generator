"""Download and shape nflverse play-by-play data into per-target and per-game tables."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
PLAYERS_URL = "https://github.com/nflverse/nflverse-data/releases/download/players/players.parquet"
SNAPS_URL = "https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{season}.parquet"
DEPTH_URL = "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_{season}.parquet"
SKILL = ["WR", "TE", "RB", "FB", "QB"]

PBP_COLS = [
    "season", "season_type", "week", "game_id", "game_date", "posteam", "defteam",
    "play_type", "pass_attempt", "sack", "two_point_attempt",
    "receiver_player_id", "receiver_player_name", "receiving_yards", "air_yards",
    "complete_pass", "pass_location", "rush_attempt", "rusher_player_id", "rusher_player_name", "rushing_yards",
]


def _download(url: str, dest: Path, refresh: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not refresh:
        return dest
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, dest)
    return dest


def ensure_data(seasons: list[int], refresh_seasons: list[int] | None = None) -> None:
    refresh_seasons = set(refresh_seasons or [])
    for s in seasons:
        r = s in refresh_seasons
        _download(PBP_URL.format(season=s), DATA_DIR / f"pbp_{s}.parquet", refresh=r)
        _download(SNAPS_URL.format(season=s), DATA_DIR / f"snap_counts_{s}.parquet", refresh=r)
        _download(DEPTH_URL.format(season=s), DATA_DIR / f"depth_charts_{s}.parquet", refresh=r)
    _download(PLAYERS_URL, DATA_DIR / "players.parquet", refresh=bool(refresh_seasons))


def load_targets(seasons: list[int]) -> pd.DataFrame:
    """One row per targeted regular season pass (no sacks, no 2pt tries, no nullified plays)."""
    frames = []
    for s in seasons:
        d = pd.read_parquet(DATA_DIR / f"pbp_{s}.parquet", columns=PBP_COLS)
        d = d[
            (d.season_type == "REG")
            & (d.play_type == "pass")
            & (d.pass_attempt == 1)
            & (d.sack != 1)
            & (d.two_point_attempt != 1)
            & d.receiver_player_id.notna()
        ]
        frames.append(d)
    t = pd.concat(frames, ignore_index=True)
    t["yards"] = t.receiving_yards.fillna(0.0)
    t["complete"] = t.complete_pass.fillna(0).astype(int)
    depth = np.where(t.air_yards.isna(), "na", np.where(t.air_yards >= 10, "deep", "short"))
    t["zone"] = np.where(t.pass_location.isna(), "na", t.pass_location.astype(str) + "_" + depth)
    t["key"] = t.season * 100 + t.week  # chronological game key
    return t[["season", "week", "key", "game_id", "game_date", "posteam", "defteam",
              "receiver_player_id", "receiver_player_name", "yards", "complete", "air_yards", "zone"]]


def load_rushes(seasons: list[int]) -> pd.DataFrame:
    """One row per regular season designed run or QB scramble (no kneels, no 2pt tries)."""
    frames = []
    for s in seasons:
        d = pd.read_parquet(DATA_DIR / f"pbp_{s}.parquet", columns=PBP_COLS)
        d = d[
            (d.season_type == "REG")
            & (d.play_type == "run")
            & (d.rush_attempt == 1)
            & (d.two_point_attempt != 1)
            & d.rusher_player_id.notna()
        ]
        frames.append(d)
    r = pd.concat(frames, ignore_index=True)
    r["yards"] = r.rushing_yards.fillna(0.0)
    r["key"] = r.season * 100 + r.week
    return r[["season", "week", "key", "game_id", "posteam", "defteam",
              "rusher_player_id", "rusher_player_name", "yards"]]


def load_positions() -> dict[str, str]:
    p = pd.read_parquet(DATA_DIR / "players.parquet", columns=["gsis_id", "position"])
    return dict(zip(p.gsis_id, p.position.fillna("WR")))


def load_players() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "players.parquet", columns=["gsis_id", "display_name", "position", "latest_team"])


def load_snaps(seasons: list[int]) -> pd.DataFrame:
    """Offensive snaps for skill players, keyed by gsis_id. Lets us add games where a
    player was on the field but never got a target or carry (play by play omits them)."""
    s = pd.concat([pd.read_parquet(DATA_DIR / f"snap_counts_{y}.parquet") for y in seasons], ignore_index=True)
    s = s[(s.game_type == "REG") & s.position.isin(SKILL) & (s.offense_snaps > 0)]
    ids = pd.read_parquet(DATA_DIR / "players.parquet", columns=["gsis_id", "pfr_id"]).dropna()
    s = s.merge(ids, left_on="pfr_player_id", right_on="pfr_id")
    return s[["game_id", "team", "gsis_id", "offense_snaps", "offense_pct"]]


def game_dates(seasons: list[int]) -> pd.DataFrame:
    frames = [pd.read_parquet(DATA_DIR / f"pbp_{y}.parquet", columns=["game_id", "season", "week", "game_date", "home_team", "away_team"])
              .drop_duplicates("game_id") for y in seasons]
    return pd.concat(frames, ignore_index=True)


STARTERS = {"WR": 3, "TE": 1, "RB": 1, "FB": 0, "QB": 1}


def load_depth(seasons: list[int]) -> pd.DataFrame:
    """Depth chart rank for skill players at each team game, using only the chart
    published on or before game day. Two nflverse formats are normalized:
      * through 2024: weekly charts with depth_team (1 = starter)
      * 2025 on: daily ESPN snapshots with pos_rank within position
    Output: game_id, team, gsis_id, pos, rank, starter."""
    games = game_dates(seasons)
    out = []
    for y in seasons:
        d = pd.read_parquet(DATA_DIR / f"depth_charts_{y}.parquet")
        g = games[games.season == y]
        if "dt" in d.columns:  # daily snapshots
            d = d[d.pos_abb.isin(SKILL) & d.gsis_id.notna()].copy()
            d["date"] = d.dt.str[:10]
            snaps = sorted(d.date.unique())
            for r in g.itertuples(index=False):
                prior = [x for x in snaps if x <= r.game_date]
                if not prior:
                    continue
                snap = d[d.date == prior[-1]]
                for team in (r.home_team, r.away_team):
                    t = snap[snap.team == team].drop_duplicates(["gsis_id", "pos_abb"])
                    for row in t.itertuples(index=False):
                        out.append((r.game_id, team, row.gsis_id, row.pos_abb, int(row.pos_rank)))
        else:  # weekly
            d = d[(d.game_type == "REG") & (d.formation == "Offense") & d.position.isin(SKILL) & d.gsis_id.notna()]
            d = d.assign(rank=pd.to_numeric(d.depth_team, errors="coerce")).dropna(subset=["rank"])
            d = d.sort_values("rank").drop_duplicates(["club_code", "week", "gsis_id"])
            m = d.merge(pd.concat([g.assign(team=g.home_team), g.assign(team=g.away_team)]),
                        left_on=["club_code", "week"], right_on=["team", "week"])
            # weekly format lists every WR slot as rank 1 for starters, so rank = depth_team
            out += list(zip(m.game_id, m.team, m.gsis_id, m.position, m["rank"].astype(int)))
    df = pd.DataFrame(out, columns=["game_id", "team", "gsis_id", "pos", "rank"]).drop_duplicates(["game_id", "team", "gsis_id"])
    new_format = df.game_id.str[:4].astype(int) >= 2025
    df["starter"] = [r <= STARTERS.get(p, 1) if nf else r == 1 for r, p, nf in zip(df["rank"], df.pos, new_format)]
    return df


def load_passes(seasons: list[int]) -> pd.DataFrame:
    """Every regular season pass attempt (targeted or not; no sacks, spikes, or 2pt tries), with passer."""
    cols = ["season", "season_type", "week", "game_id", "posteam", "defteam", "play_type", "pass_attempt", "sack",
            "two_point_attempt", "passer_player_id", "receiver_player_id", "complete_pass", "passing_yards",
            "pass_touchdown", "interception"]
    frames = []
    for s in seasons:
        try:
            d = pd.read_parquet(DATA_DIR / f"pbp_{s}.parquet", columns=cols)
        except FileNotFoundError:
            continue
        d = d[(d.season_type == "REG") & (d.play_type == "pass") & (d.pass_attempt == 1) & (d.sack != 1)
              & (d.two_point_attempt != 1) & d.passer_player_id.notna()]
        frames.append(d)
    p = pd.concat(frames, ignore_index=True)
    p["key"] = p.season * 100 + p.week
    p["targeted"] = p.receiver_player_id.notna().astype(int)
    p["yards"] = p.passing_yards.fillna(0.0)
    p["complete"] = p.complete_pass.fillna(0).astype(int)
    p["td"] = p.pass_touchdown.fillna(0).astype(int)
    p["int"] = p.interception.fillna(0).astype(int)
    return p[["key", "game_id", "posteam", "defteam", "passer_player_id", "receiver_player_id", "targeted",
              "complete", "yards", "td", "int"]].sort_values("key").reset_index(drop=True)
