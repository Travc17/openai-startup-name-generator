"""Kalshi player-prop ladders for one NFL game, as bet-finder quotes (cents, yes/no on each "x+" rung).

    python kalshi_quotes.py JAX BAL --out markets/<file>_kalshi_<open|midday|close>.csv

Asks of 98c+ or 2c- are dropped (no real offer). Uses The Odds API (key in ODDS_API_KEY; about 7 credits).
"""
import argparse, csv, datetime, json, os, urllib.request

API = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
MK = {"player_pass_yds_alternate": "pass_yds", "player_pass_attempts_alternate": "pass_att",
      "player_pass_completions_alternate": "pass_cmp", "player_rush_yds_alternate": "rush_yds",
      "player_reception_yds_alternate": "rec_yds", "player_receptions_alternate": "rec",
      "player_rush_reception_yds_alternate": "rec_rush_yds"}
CITY = {"ARI": "Arizona", "ATL": "Atlanta", "BAL": "Baltimore", "BUF": "Buffalo", "CAR": "Carolina", "CHI": "Chicago",
        "CIN": "Cincinnati", "CLE": "Cleveland", "DAL": "Dallas", "DEN": "Denver", "DET": "Detroit", "GB": "Green Bay",
        "HOU": "Houston", "IND": "Indianapolis", "JAX": "Jacksonville", "KC": "Kansas City", "LV": "Las Vegas",
        "LAC": "Chargers", "LAR": "Rams", "LA": "Rams", "MIA": "Miami", "MIN": "Minnesota", "NE": "New England",
        "NO": "New Orleans", "NYG": "Giants", "NYJ": "Jets", "PHI": "Philadelphia", "PIT": "Pittsburgh",
        "SF": "San Francisco", "SEA": "Seattle", "TB": "Tampa Bay", "TEN": "Tennessee", "WAS": "Washington"}


def get(url):
    with urllib.request.urlopen(url) as r:
        return json.load(r), r.headers.get("x-requests-last"), r.headers.get("x-requests-remaining")


def main(a, h, out):
    key = os.environ["ODDS_API_KEY"]
    ev, _, _ = get(f"{API}/events?apiKey={key}")
    ev = next(e for e in ev if CITY.get(a, a).lower() in e["away_team"].lower() and CITY.get(h, h).lower() in e["home_team"].lower())
    d, used, left = get(f"{API}/events/{ev['id']}/odds?apiKey={key}&bookmakers=kalshi&markets={','.join(MK)}&oddsFormat=american")
    imp = lambda p: 100 / (p + 100) if p > 0 else -p / (-p + 100)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    rows = []
    for b in d.get("bookmakers", []):
        for m in b["markets"]:
            for o in m["outcomes"]:
                c = round(imp(o["price"]) * 100)
                if 2 < c < 98:
                    rows.append({"venue": "Kalshi", "player": o["description"], "stat": MK[m["key"]], "line": o["point"] + 0.5,
                                 "side": "yes" if o["name"] == "Over" else "no", "price": c, "captured_at": now})
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["venue", "player", "stat", "line", "side", "price", "captured_at"])
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} Kalshi quotes -> {out}; credits used {used}, left {left}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("away"); ap.add_argument("home"); ap.add_argument("--out", required=True)
    x = ap.parse_args(); main(x.away.upper(), x.home.upper(), x.out)
