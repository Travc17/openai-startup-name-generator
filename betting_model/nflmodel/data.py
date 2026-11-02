"""Download and shape nflverse play-by-play data into per-target and per-game tables."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
PLAYERS_URL = "https://github.com/nflverse/nflverse-data/releases/download/players/players.parquet"

PBP_COLS = [
    "season", "season_type", "week", "game_id", "game_date", "posteam", "defteam",
    "play_type", "pass_attempt", "sack", "two_point_attempt",
    "receiver_player_id", "receiver_player_name", "receiving_yards", "air_yards",
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
        _download(PBP_URL.format(season=s), DATA_DIR / f"pbp_{s}.parquet", refresh=s in refresh_seasons)
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
    t["key"] = t.season * 100 + t.week  # chronological game key
    return t[["season", "week", "key", "game_id", "game_date", "posteam", "defteam",
              "receiver_player_id", "receiver_player_name", "yards", "air_yards"]]


def load_positions() -> dict[str, str]:
    p = pd.read_parquet(DATA_DIR / "players.parquet", columns=["gsis_id", "position"])
    return dict(zip(p.gsis_id, p.position.fillna("WR")))


def load_players() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "players.parquet", columns=["gsis_id", "display_name", "position", "latest_team"])


def player_games(t: pd.DataFrame) -> pd.DataFrame:
    """Per player per game: targets, yards, and the team's total targets that game."""
    team = t.groupby(["game_id", "posteam"]).size().rename("team_targets")
    pg = (t.groupby(["season", "week", "key", "game_id", "posteam", "defteam", "receiver_player_id"])
            .agg(targets=("yards", "size"), yards=("yards", "sum"))
            .reset_index())
    pg = pg.join(team, on=["game_id", "posteam"])
    pg["share"] = pg.targets / pg.team_targets
    return pg


def team_games(t: pd.DataFrame) -> pd.DataFrame:
    """Per team per game: targets thrown (offense) and yards on those targets."""
    return (t.groupby(["season", "week", "key", "game_id", "posteam", "defteam"])
              .agg(targets=("yards", "size"), yards=("yards", "sum"))
              .reset_index())
