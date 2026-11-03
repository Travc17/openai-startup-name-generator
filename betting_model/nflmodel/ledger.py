"""Bet log with closing line value tracking. Stored as bets.csv next to this package."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from .pricing import parse_price

LEDGER = Path(__file__).resolve().parent.parent / "bets.csv"
FIELDS = ["id", "date", "sport", "bet", "price_taken", "stake", "model_prob",
          "closing_price", "result", "pnl", "notes"]


def _read() -> list[dict]:
    if not LEDGER.exists():
        return []
    with LEDGER.open() as f:
        return list(csv.DictReader(f))


def _write(rows: list[dict]) -> None:
    with LEDGER.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def add(bet: str, price: str, stake: float, model_prob: float | None, sport: str = "NFL", notes: str = "") -> int:
    rows = _read()
    new_id = max([int(r["id"]) for r in rows] or [0]) + 1
    rows.append({"id": new_id, "date": date.today().isoformat(), "sport": sport, "bet": bet,
                 "price_taken": price, "stake": stake, "model_prob": "" if model_prob is None else f"{model_prob:.4f}",
                 "closing_price": "", "result": "", "pnl": "", "notes": notes})
    _write(rows)
    return new_id


def settle(bet_id: int, result: str, closing_price: str | None = None) -> dict:
    """result: win, loss, or push."""
    rows = _read()
    for r in rows:
        if int(r["id"]) == bet_id:
            p = parse_price(r["price_taken"])
            s = float(r["stake"])
            r["result"] = result
            r["pnl"] = f"{(s * p.net_odds) if result == 'win' else (-s if result == 'loss' else 0):.2f}"
            if closing_price:
                r["closing_price"] = closing_price
            _write(rows)
            return r
    raise KeyError(f"No bet with id {bet_id}")


def summary(bankroll_start: float = 2000) -> str:
    rows = _read()
    if not rows:
        return "No bets logged yet."
    settled = [r for r in rows if r["result"]]
    pnl = sum(float(r["pnl"]) for r in settled)
    risked = sum(float(r["stake"]) for r in settled)
    clv = [parse_price(r["closing_price"]).breakeven - parse_price(r["price_taken"]).breakeven
           for r in rows if r["closing_price"]]
    lines = [
        f"Bets logged: {len(rows)}  settled: {len(settled)}",
        f"Profit/loss: ${pnl:+.2f} on ${risked:.2f} risked  (ROI {pnl / risked:+.1%})" if risked else "Profit/loss: none settled",
        f"Bankroll: ${bankroll_start + pnl:,.2f}",
    ]
    if clv:
        beat = sum(c > 0 for c in clv)
        lines.append(f"Closing line value: beat the close on {beat}/{len(clv)} bets, "
                     f"avg {sum(clv) / len(clv):+.1%} implied probability")
    if len(rows) >= 50 and clv and sum(clv) / len(clv) <= 0:
        lines.append("50+ bets and NOT beating the close on average: no demonstrated edge. Recommend stopping.")
    if bankroll_start + pnl <= 1000:
        lines.append("Bankroll at or below $1,000: STOP per the rules.")
    return "\n".join(lines)


def current_bankroll(start: float = 2000) -> float:
    return start + sum(float(r["pnl"]) for r in _read() if r["result"])
