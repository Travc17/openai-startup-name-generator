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
# Approved by Travis 2026-11-05 after the 2025/2026 closing-line tests (reviews/hist_2026_model_vs_market.md):
MIN_EDGE = 0.10      # model edge after fee; 2-10% edges were about break-even (the model is overconfident)
STAKE_FRAC = 0.05    # 5% of the CURRENT bankroll per bet (about half Kelly on the MEASURED edge, not the stated one)


def rule_ok(side: str, stat: str, pos: str | None = None) -> tuple[bool, str]:
    """Direction rules (CLAUDE.md 2026-11-05): unders only (NO on a rung); low-rung overs only through the floor
    check (FLOOR_PROMPT.md / floor_legs.py), never auto-staked; no QB passing-yards unders; no QB rushing props."""
    if pos == "QB" and stat in ("rush_yds", "rush_att", "rec_rush_yds"):
        return False, "no QB rushing props"
    under = side in ("no", "under")
    if not under:
        return False, "over: floor check only"
    if stat == "pass_yds":
        return False, "no QB pass-yds unders"
    return True, ""


def stake(p_win: float, price: Price, bankroll: float = 2000, min_bet: float = 50,
          max_bet: float | None = None, kelly_frac: float | None = None, min_edge: float = MIN_EDGE,
          big_edge: float | None = None, frac: float = STAKE_FRAC) -> tuple[float, str]:
    """Apply the bankroll rules. Edge = model probability minus breakeven probability (fee included).
    Stake = 5% of the CURRENT bankroll (min $50, max 10%); the 10% per-game cap is applied in plan_game.
    kelly_frac and big_edge are accepted for old callers and ignored (quarter Kelly retired 2026-11-05)."""
    if max_bet is None:
        max_bet = round(bankroll * MAX_BET_FRAC / 5) * 5
    min_bet = min(min_bet, max_bet)
    edge = p_win - price.breakeven
    if edge < min_edge:
        return 0.0, f"PASS (edge {edge:+.1%} below {min_edge:.0%})"
    amt = max(min_bet, min(max_bet, round(bankroll * frac / 5) * 5))
    return float(amt), f"BET {frac:.0%} of bankroll (edge {edge:+.1%})"


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
