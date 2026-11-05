"""Pull historical CLOSING player prop lines from The Odds API for one season (approved by Travis 2026-11-05).

    python hist_props.py 2025                 # regular season, 5 markets, about 13,700 credits
    python hist_props.py 2025 --flatten-only  # rebuild the parquet from saved raw files

Cost (measured 2026-11-05): historical event list 1 credit per call; historical event odds 10 credits per market per
region (5 markets, region us = 50 per game). Closing = the snapshot 10 minutes before the listed kickoff.
Raw JSON goes to data/odds_hist/<season>/ (gitignored) and is flattened to data/odds_hist/props_<season>.parquet.
Resumable: games already saved are skipped. Stops if a call costs more than expected or credits fall below --floor.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nflmodel.odds_api import TEAMS  # noqa: E402

HIST = "https://api.the-odds-api.com/v4/historical/sports/americanfootball_nfl"
MARKETS = {"player_receptions": "rec", "player_reception_yds": "rec_yds", "player_rush_yds": "rush_yds",
           "player_rush_attempts": "rush_att", "player_pass_yds": "pass_yds"}
NV = {"LA": "LAR"}  # nflverse abbreviation -> TEAMS key where they differ


def get(url, params):
    key = os.environ.get("ODDS_API_KEY")
    full = url + "?" + urllib.parse.urlencode({**params, **({"apiKey": key} if key else {})})
    for i in range(4):
        try:
            with urllib.request.urlopen(full, timeout=60) as r:
                return json.load(r), {k.lower(): v for k, v in r.headers.items()}
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < 3:
                time.sleep(2 ** (i + 1)); continue
            raise SystemExit(f"Odds API {e.code}: {e.read().decode(errors='replace')[:300]}")
        except urllib.error.URLError:
            if i < 3:
                time.sleep(2 ** (i + 1)); continue
            raise


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def team_name(abbr):
    return TEAMS[NV.get(abbr, abbr)] if NV.get(abbr, abbr) in TEAMS else TEAMS[abbr]


def schedule(season):
    p = pd.read_parquet(HERE / "data" / f"pbp_{season}.parquet",
                        columns=["game_id", "week", "season_type", "home_team", "away_team", "game_date"])
    g = p[p.season_type == "REG"].drop_duplicates("game_id").copy()
    g["home"] = g.home_team.map(team_name)
    g["away"] = g.away_team.map(team_name)
    g["date"] = pd.to_datetime(g.game_date)
    return g.sort_values(["week", "date"]).reset_index(drop=True)


def find_events(g, out, log):
    """Odds API event ids for every game, from one historical event list per week (1 credit each)."""
    path = out / "events.json"
    ev = json.loads(path.read_text()) if path.exists() else {}
    for wk, games in g.groupby("week"):
        todo = games[~games.game_id.isin(ev)]
        if todo.empty:
            continue
        for snap in sorted({d - timedelta(days=1) for d in todo.date} | {todo.date.min() - timedelta(days=2)}):
            todo = games[~games.game_id.isin(ev)]
            if todo.empty:
                break
            data, hdr = get(f"{HIST}/events", {"date": iso(snap.replace(hour=12, tzinfo=timezone.utc))})
            for e in data.get("data", []):
                ct = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
                for r in todo.itertuples():
                    if e["home_team"] == r.home and e["away_team"] == r.away and abs((ct.date() - r.date.date()).days) <= 1:
                        ev[r.game_id] = {"id": e["id"], "commence": e["commence_time"], "home": r.home, "away": r.away, "week": int(wk)}
            log(f"week {wk}: events matched {games.game_id.isin(ev).sum()}/{len(games)} | credits left {hdr.get('x-requests-remaining')}")
        path.write_text(json.dumps(ev, indent=1))
    return ev


def pull(season, floor, max_cost):
    out = HERE / "data" / "odds_hist" / str(season)
    out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "pull.log", "a")
    def log(msg):
        line = f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}"
        print(line, flush=True); logf.write(line + "\n"); logf.flush()
    g = schedule(season)
    ev = find_events(g, out, log)
    missing = [gid for gid in g.game_id if gid not in ev]
    if missing:
        log(f"no Odds API event for {len(missing)} games: {missing[:10]}")
    done = 0
    for gid in g.game_id:
        if gid not in ev or (out / f"{gid}.json").exists():
            continue
        e = ev[gid]
        close = datetime.fromisoformat(e["commence"].replace("Z", "+00:00")) - timedelta(minutes=10)
        data, hdr = get(f"{HIST}/events/{e['id']}/odds",
                        {"date": iso(close), "regions": "us", "markets": ",".join(MARKETS), "oddsFormat": "american"})
        (out / f"{gid}.json").write_text(json.dumps(data))
        done += 1
        cost, left = int(hdr.get("x-requests-last", 0)), int(hdr.get("x-requests-remaining", 0))
        if done % 10 == 0 or cost > max_cost:
            log(f"{done} games pulled (last {gid}, cost {cost}) | credits left {left}")
        if cost > max_cost:
            log(f"STOP: a call cost {cost} credits (expected <= {max_cost})"); break
        if left < floor:
            log(f"STOP: credits left {left} below floor {floor}"); break
        time.sleep(0.3)
    log(f"pull finished: {done} new games this run")


def flatten(season):
    out = HERE / "data" / "odds_hist" / str(season)
    ev = json.loads((out / "events.json").read_text())
    rows = []
    for gid, e in ev.items():
        f = out / f"{gid}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        snap = d.get("timestamp")
        for b in d.get("data", {}).get("bookmakers", []):
            for m in b.get("markets", []):
                if m["key"] not in MARKETS:
                    continue
                for o in m.get("outcomes", []):
                    if o.get("point") is None or o["name"].lower() not in ("over", "under"):
                        continue
                    rows.append({"game_id": gid, "week": e["week"], "commence": e["commence"], "snapshot": snap,
                                 "book": b["key"], "book_update": m.get("last_update"), "player": o.get("description"),
                                 "stat": MARKETS[m["key"]], "line": o["point"], "side": o["name"].lower(), "price": o["price"]})
    df = pd.DataFrame(rows)
    df.to_parquet(out.parent / f"props_{season}.parquet")
    n_games = df.game_id.nunique() if len(df) else 0
    print(f"{len(df)} quotes, {n_games} games, {df.player.nunique() if len(df) else 0} players -> data/odds_hist/props_{season}.parquet")
    if len(df):
        print(df.groupby("stat").agg(quotes=("price", "size"), games=("game_id", "nunique"), books=("book", "nunique")).to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("season", type=int)
    ap.add_argument("--floor", type=int, default=5000, help="stop when credits left fall below this")
    ap.add_argument("--max-cost", type=int, default=50, help="stop if one game call costs more than this")
    ap.add_argument("--flatten-only", action="store_true")
    a = ap.parse_args()
    if not a.flatten_only:
        pull(a.season, a.floor, a.max_cost)
    flatten(a.season)
