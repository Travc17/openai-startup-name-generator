"""Layer 2 + 3: market prices and the bet finder. Venue-agnostic.

Reads a projections file (projections.py) and quotes from ANY venue, then answers two separate
questions for every quote:

  edge_model  = model probability   - what the quote costs (price + that venue's fee)
  edge_market = big-book no-vig prob - what the quote costs

The big-book no-vig probability ("market") comes only from books that post BOTH sides of the
same line; it is the average across those books. No model is involved in it.

Quotes CSV (one row per side per venue):
    venue,player,stat,line,side,price,captured_at
    DraftKings,Zay Flowers,rec_yds,45.5,over,-115,2026-11-05T18:00
    DraftKings,Zay Flowers,rec_yds,45.5,under,-105,2026-11-05T18:00
    Robinhood,Zay Flowers,rec_yds,50,yes,48,2026-11-05T18:05     # "50+" rung, Yes at 48c
    Robinhood,Zay Flowers,rec_yds,50,no,55,2026-11-05T18:05      # "50+" rung, No at 55c

Prediction-market rungs ("x+", yes/no) are converted to OVER/UNDER (x - 0.5), so every venue
lands on the same scale. Prices: American odds (-115, +120) or cents (48 or 48c) for
prediction markets. Fees per contract by venue: VENUE_FEE (Robinhood 2c, seen on bet #1);
sportsbooks carry their cut inside the odds.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict

from . import projections
from .pricing import parse_price

VENUE_FEE = {"robinhood": 0.02}
NO_BET_STATS = {"pass_td", "int"}          # not calibration-checked yet (CLAUDE.md): never a bet


def name_key(n: str) -> str:
    """Same player across venues: 'Brian Thomas Jr.' = 'Brian Thomas Jr' = 'brian thomas'."""
    n = re.sub(r"[.'’,]", "", n.lower())
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    return " ".join(n.split())
CENT_VENUES = {"robinhood", "kalshi", "polymarket"}


def _norm(q: dict, fees: dict) -> dict | None:
    venue = q["venue"].strip()
    v = venue.lower()
    side = q["side"].strip().lower()
    line = float(q["line"])
    raw = str(q["price"]).strip()
    if not raw:
        return None
    rung = None
    if side in ("yes", "no"):                       # "x+" rung -> over/under x - 0.5 (model still uses P(stat >= x))
        rung, line, side = line, line - 0.5, ("over" if side == "yes" else "under")
    if v in CENT_VENUES and not raw.lower().endswith("c"):
        raw += "c"
    pr = parse_price(raw, fees.get(v, 0.0) if raw.lower().endswith("c") else 0.0)
    return {"venue": venue, "player": q["player"].strip(), "stat": q["stat"].strip(), "line": line, "rung": rung, "side": side,
            "price": raw, "cost": pr.breakeven, "net_odds": pr.net_odds, "captured_at": q.get("captured_at", "")}


def load_quotes(path: str, fees: dict | None = None) -> list[dict]:
    fees = {**VENUE_FEE, **(fees or {})}
    with open(path) as f:
        return [n for n in (_norm(r, fees) for r in csv.DictReader(f)) if n]


def from_board(board: list[dict], fees: dict | None = None, captured_at: str = "") -> list[dict]:
    """The report's board CSV (kind,name,stat,line,price,price2,book) as venue quotes."""
    fees = {**VENUE_FEE, **(fees or {})}
    rows = []
    for r in board:
        kind = r["kind"].lower()
        if kind == "prop":
            for side, col in (("yes", "price"), ("no", "price2")):
                if r.get(col, "").strip():
                    rows.append({"venue": "Robinhood", "player": r["name"], "stat": r["stat"], "line": r["line"],
                                 "side": side, "price": r[col], "captured_at": captured_at})
        elif kind == "book":
            for side, col in (("over", "price"), ("under", "price2")):
                if r.get(col, "").strip():
                    rows.append({"venue": r.get("book", "") or "book", "player": r["name"], "stat": r["stat"],
                                 "line": r["line"], "side": side, "price": r[col], "captured_at": captured_at})
    return [n for n in (_norm(q, fees) for q in rows) if n]


def market_probs(quotes: list[dict]) -> dict:
    """No-vig over probability per (player, stat, line): average over books quoting both sides."""
    by = defaultdict(dict)
    for q in quotes:
        if q["venue"].lower() in CENT_VENUES:
            continue                                  # the market reference is sportsbooks only
        by[(name_key(q["player"]), q["stat"], q["line"], q["venue"])][q["side"]] = q["cost"]
    agg = defaultdict(list)
    for (pl, st, ln, _), s in by.items():
        if "over" in s and "under" in s:
            agg[(pl, st, ln)].append(s["over"] / (s["over"] + s["under"]))
    return {k: (sum(v) / len(v), len(v)) for k, v in agg.items()}


def find(proj: dict, quotes: list[dict], min_edge: float = 0.02) -> list[dict]:
    mk = market_probs(quotes)
    players = {name_key(n): (n, v) for n, v in proj["players"].items()}
    out = []
    for q in quotes:
        pname, pl = players.get(name_key(q["player"]), (None, None))
        st = pl["stats"].get(q["stat"]) if pl else None
        if st is None:
            win, push = None, 0.0
        elif q["rung"] is not None:
            win, push = projections.ge(st, q["rung"]), 0.0      # same rule as the report: P(stat >= x)
        else:
            win, push = projections.p_over(st, q["line"])
        # a push refunds the stake, so compare the no-push probability with the breakeven
        p_model = None if win is None else (win if q["side"] == "over" else 1 - win - push) / max(1 - push, 1e-9)
        m = mk.get((name_key(q["player"]), q["stat"], q["line"]))
        p_mkt = None if m is None else (m[0] if q["side"] == "over" else 1 - m[0])
        row = {**q, "p_model": p_model, "p_market": p_mkt, "books": m[1] if m else 0,
               "edge_model": None if p_model is None else p_model - q["cost"],
               "edge_market": None if p_mkt is None else p_mkt - q["cost"]}
        row["verdict"] = verdict(row, min_edge)
        bl = pl.get("blind") if pl else None             # blind spots stay out of bets (CLAUDE.md)
        if row["verdict"] not in ("pass", "no projection"):
            if bl and (bl == "all" or q["stat"] in bl):
                row["verdict"] = "blind spot"
            elif q["stat"] in NO_BET_STATS:
                row["verdict"] = "not calibrated"
        row["proj_name"] = pname
        out.append(row)
    best = {}
    for r in out:                                     # best price for each exact bet across venues
        k = (name_key(r["player"]), r["stat"], r["line"], r["side"])
        if k not in best or r["cost"] < best[k]["cost"]:
            best[k] = r
    for r in out:
        r["best_price"] = best[(name_key(r["player"]), r["stat"], r["line"], r["side"])] is r
    return sort_rows(out)


RANK = {"BOTH AGREE": 0, "market only": 1, "model only": 2, "model vs market": 3, "blind spot": 4,
        "not calibrated": 5, "pass": 6, "no projection": 7}


def sort_rows(rows: list[dict]) -> list[dict]:
    """Bets first (both agree, then books-only, then model-only), then everything else; best edge first."""
    return sorted(rows, key=lambda r: (RANK.get(r["verdict"], 9), -(r["edge_model"] if r["edge_model"] is not None else -9)))


def verdict(r: dict, min_edge: float) -> str:
    em, ek = r["edge_model"], r["edge_market"]
    if em is None:
        return "no projection"
    if ek is None:
        return "model only" if em >= min_edge else "pass"
    if em >= min_edge and ek >= min_edge:
        return "BOTH AGREE"
    if ek >= min_edge:
        return "market only"
    if em >= min_edge:
        return "model vs market"                      # the model disagrees with the books: the test case for H4
    return "pass"


def table(rows: list[dict], top: int = 40) -> str:
    f = lambda x: "  n/a" if x is None else f"{x * 100:5.1f}"
    out = [f"{'verdict':<16}{'venue':<14}{'bet':<44}{'price':>7}{'cost':>7}{'model':>7}{'mkt':>7}{'edge M':>8}{'edge K':>8}"]
    for r in rows[:top]:
        bet = f"{r['player']} {r['stat']} {r['side']} {r['line']:g}"
        out.append(f"{r['verdict']:<16}{r['venue'][:13]:<14}{bet[:43]:<44}{r['price']:>7}{r['cost'] * 100:7.1f}"
                   f"{f(r['p_model']):>7}{f(r['p_market']):>7}{f(r['edge_model']):>8}{f(r['edge_market']):>8}")
    n = defaultdict(int)
    for r in rows:
        n[r["verdict"]] += 1
    out.append("counts: " + ", ".join(f"{k} {v}" for k, v in sorted(n.items())))
    return "\n".join(out)
