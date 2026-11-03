"""Pull big-book NFL player prop lines from The Odds API (the-odds-api.com, v4) into the
bet finder's quotes format (venue,player,stat,line,side,price,captured_at).

Key: read from the ODDS_API_KEY environment variable and sent as the `apiKey` query parameter.
If the variable is not set, the request goes out without it (in case the environment's network
secret is injected for api.the-odds-api.com); a 401 then means the key is not reaching the API.

Cost (their billing): credits = markets x regions per event call. The events list and the
sports list do not use credits. The remaining balance prints after every call.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
# Odds API market key -> our stat. TD/INT markets are left out on purpose (not calibration-checked).
MARKETS = {"player_pass_yds": "pass_yds", "player_pass_attempts": "pass_att", "player_pass_completions": "pass_cmp",
           "player_rush_yds": "rush_yds", "player_rush_attempts": "rush_att", "player_receptions": "rec",
           "player_reception_yds": "rec_yds", "player_rush_reception_yds": "rec_rush_yds"}
ALT = {f"{k}_alternate": v for k, v in MARKETS.items() if k not in ("player_pass_attempts", "player_pass_completions",
                                                                       "player_rush_attempts")}
BOOKS = "draftkings,fanduel,betmgm,williamhill_us,fanatics"     # williamhill_us = Caesars
TEAMS = {"ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
         "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
         "DAL": "Dallas Cowboys", "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
         "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
         "LAC": "Los Angeles Chargers", "LA": "Los Angeles Rams", "LAR": "Los Angeles Rams", "LV": "Las Vegas Raiders",
         "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings", "NE": "New England Patriots", "NO": "New Orleans Saints",
         "NYG": "New York Giants", "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
         "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans",
         "WAS": "Washington Commanders"}


def _get(url: str, params: dict) -> tuple[object, dict]:
    key = os.environ.get("ODDS_API_KEY")
    if key:
        params = {**params, "apiKey": key}
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    try:
        with urllib.request.urlopen(full, timeout=60) as r:
            hdr = {k.lower(): v for k, v in r.headers.items()}
            return json.load(r), hdr
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise SystemExit(f"The Odds API answered {e.code}: {body}"
                         + ("\n401 = no valid key reached the API (ODDS_API_KEY not set in this session?)" if e.code == 401 else ""))


def credits(hdr: dict) -> str:
    return f"credits used {hdr.get('x-requests-used', '?')}, remaining {hdr.get('x-requests-remaining', '?')}" \
           f" (this call {hdr.get('x-requests-last', '?')})"


def find_event(away: str, home: str) -> dict:
    events, _ = _get(f"{BASE}/events", {})
    a, h = TEAMS[away.upper()], TEAMS[home.upper()]
    for e in events:
        if e["home_team"] == h and e["away_team"] == a:
            return e
    raise SystemExit(f"No upcoming event {a} at {h} in The Odds API list ({len(events)} NFL events listed).")


def fetch(away: str, home: str, alt: bool = False, books: str = BOOKS, game_lines: bool = True) -> tuple[list[dict], dict, str]:
    """Quotes for one game: player props (+ alternates if alt) and, optionally, spread/total."""
    ev = find_event(away, home)
    mk = dict(MARKETS, **(ALT if alt else {}))
    keys = list(mk) + (["spreads", "totals"] if game_lines else [])
    data, hdr = _get(f"{BASE}/events/{ev['id']}/odds",
                     {"bookmakers": books, "markets": ",".join(keys), "oddsFormat": "american"})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return parse(data, mk, now), hdr, ev["commence_time"]


def parse(data: dict, mk: dict, captured_at: str) -> list[dict]:
    rows = []
    for b in data.get("bookmakers", []):
        for m in b.get("markets", []):
            k = m["key"]
            for o in m.get("outcomes", []):
                if k in ("spreads", "totals"):
                    rows.append({"venue": b["title"], "player": o["name"], "stat": k, "line": o.get("point"),
                                 "side": "over" if o["name"] == "Over" else ("under" if o["name"] == "Under" else "team"),
                                 "price": o["price"], "captured_at": captured_at})
                    continue
                if k not in mk or o.get("point") is None:
                    continue
                side = o["name"].lower()
                if side not in ("over", "under"):
                    continue
                rows.append({"venue": b["title"] + (" alt" if k.endswith("_alternate") else ""), "player": o["description"],
                             "stat": mk[k], "line": o["point"], "side": side, "price": o["price"], "captured_at": captured_at})
    return rows


def save(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["venue", "player", "stat", "line", "side", "price", "captured_at"])
        w.writeheader()
        w.writerows(rows)
