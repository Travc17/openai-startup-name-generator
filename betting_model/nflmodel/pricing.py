"""Prices, edges, and bet sizing.

Accepts American odds (-113, +166) or prediction market contract prices
in cents (53c), the way Robinhood quotes event contracts.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Price:
    raw: str
    breakeven: float      # win probability needed to break even
    net_odds: float       # profit per $1 risked if it wins


def parse_price(s: str, fee_per_contract: float = 0.0) -> Price:
    s = s.strip().lower()
    if s.endswith("c"):
        cost = float(s[:-1]) / 100 + fee_per_contract
        return Price(s, cost, (1 - cost) / cost)
    a = float(s)
    if a < 0:
        return Price(s, -a / (-a + 100), 100 / -a)
    return Price(s, 100 / (a + 100), a / 100)


def no_vig(p_over: Price, p_under: Price) -> float:
    """Market's fair probability for the over after removing the house cut."""
    total = p_over.breakeven + p_under.breakeven
    return p_over.breakeven / total


def ev_per_dollar(p_win: float, price: Price) -> float:
    return p_win * price.net_odds - (1 - p_win)


def stake(p_win: float, price: Price, bankroll: float = 2000, min_bet: float = 50,
          max_bet: float = 250, kelly_frac: float = 0.25, min_edge: float = 0.02,
          big_edge: float = 0.04) -> tuple[float, str]:
    """Apply the bankroll rules. Edge = model probability minus breakeven probability."""
    edge = p_win - price.breakeven
    if edge < min_edge:
        return 0.0, f"PASS (edge {edge:+.1%} below {min_edge:.0%})"
    if edge < big_edge:
        return min_bet, f"BET minimum (edge {edge:+.1%})"
    k = (p_win * price.net_odds - (1 - p_win)) / price.net_odds
    amt = max(min_bet, min(max_bet, round(bankroll * k * kelly_frac / 5) * 5))
    return float(amt), f"BET quarter Kelly (edge {edge:+.1%}, full Kelly {k:.1%})"
