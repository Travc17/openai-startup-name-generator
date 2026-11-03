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


MAX_BET_FRAC = 0.10  # single bet cap: 10% of current bankroll


def stake(p_win: float, price: Price, bankroll: float = 2000, min_bet: float = 50,
          max_bet: float | None = None, kelly_frac: float = 0.25, min_edge: float = 0.02,
          big_edge: float = 0.04) -> tuple[float, str]:
    """Apply the bankroll rules. Edge = model probability minus breakeven probability.
    Cap defaults to 10% of the CURRENT bankroll, so it grows and shrinks with results."""
    if max_bet is None:
        max_bet = round(bankroll * MAX_BET_FRAC / 5) * 5
    min_bet = min(min_bet, max_bet)
    edge = p_win - price.breakeven
    if edge < min_edge:
        return 0.0, f"PASS (edge {edge:+.1%} below {min_edge:.0%})"
    if edge < big_edge:
        return min_bet, f"BET minimum (edge {edge:+.1%})"
    k = (p_win * price.net_odds - (1 - p_win)) / price.net_odds
    amt = max(min_bet, min(max_bet, round(bankroll * k * kelly_frac / 5) * 5))
    return float(amt), f"BET quarter Kelly (edge {edge:+.1%}, full Kelly {k:.1%})"


GAME_CAP_FRAC = 0.10  # ALL bets on one game combined: 10% of current bankroll (approved 2026-11-03)


def plan_game(cands: list[dict], bankroll: float, max_bets: int = 3, min_bet: float = 50,
              cap_frac: float = GAME_CAP_FRAC) -> dict:
    """Pick the bets for one game and fit them under the per-game cap.

    cands: dicts with label, kind, p (model prob), cost (price + fee), stake (single-bet Kelly stake),
    and legs: [(pid, stat), ...] (empty for game lines). Bets are taken best expected profit first,
    skipping any bet that repeats a player+stat already in the plan (that is the same bet twice).
    If the stakes add up to more than the cap they are scaled down together (to $5 steps, never
    below the minimum); if the minimums alone break the cap, the weakest bet is dropped."""
    cap = round(bankroll * cap_frac / 5) * 5
    ev = lambda c: c["stake"] * (c["p"] / c["cost"] - 1)
    chosen, used = [], set()
    for c in sorted((c for c in cands if c["stake"]), key=ev, reverse=True):
        legs = {tuple(l) for l in c.get("legs", [])}
        if legs & used:
            continue
        chosen.append(dict(c))
        used |= legs
        if len(chosen) == max_bets:
            break
    while chosen:
        total = sum(c["stake"] for c in chosen)
        if total <= cap:
            break
        scaled = [max(min_bet, (c["stake"] * cap / total) // 5 * 5) for c in chosen]
        if sum(scaled) <= cap:
            for c, st in zip(chosen, scaled):
                c["stake"] = float(st)
            break
        chosen.pop()  # minimums alone exceed the cap: drop the weakest bet and retry
    for c in chosen:
        c["ev"] = ev(c)
    return {"cap": cap, "bets": chosen, "total": sum(c["stake"] for c in chosen)}
