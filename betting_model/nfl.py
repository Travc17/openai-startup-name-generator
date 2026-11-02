#!/usr/bin/env python3
"""NFL receiving yards prop model.

  python nfl.py update                         refresh current season data
  python nfl.py project "Jaxon Smith-Njigba" --opp CHI --line 99.5:-113:-113 --line 89.5:-153
  python nfl.py backtest --seasons 2024 2025
  python nfl.py log add "JSN o99.5 rec yds" --price 53c --stake 50 --prob 0.58
  python nfl.py log settle 1 win --close 58c
  python nfl.py log summary

Line format: LINE:OVER_PRICE[:UNDER_PRICE]. Prices are American odds (-113)
or Robinhood style contract prices in cents (53c).
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

from nflmodel import backtest, data, ledger
from nflmodel.model import Config, ReceivingModel, prob_over
from nflmodel.pricing import ev_per_dollar, no_vig, parse_price, stake

CURRENT_SEASON = 2026
HISTORY = [2022, 2023, 2024, 2025, 2026]


def build(seasons=HISTORY) -> ReceivingModel:
    data.ensure_data(seasons)
    t = data.load_targets(seasons)
    return ReceivingModel(t, data.player_games(t), data.team_games(t), data.load_positions(), Config())


def find_player(model: ReceivingModel, name: str) -> tuple[str, str]:
    players = data.load_players()
    hits = players[players.display_name.str.lower() == name.lower()]
    if hits.empty:
        hits = players[players.display_name.str.lower().str.contains(name.lower(), regex=False, na=False)]
    hits = hits[hits.gsis_id.isin(model._pg_by_player.keys())]
    if hits.empty:
        sys.exit(f"No player with targets matching '{name}'.")
    if len(hits) > 1:
        sys.exit("Several matches, be more specific: " + ", ".join(hits.display_name))
    return hits.iloc[0].gsis_id, hits.iloc[0].display_name


def cmd_project(a):
    model = build()
    pid, name = find_player(model, a.player)
    hist = model._pg_by_player[pid]
    team = a.team or hist.iloc[-1].posteam
    key = a.season * 100 + a.week if a.week else int(hist.key.max()) + 1
    out = model.project(pid, team, a.opp, key, share_mult=a.share_mult, team_targets_override=a.team_targets)
    sims = out["sims"]
    q = np.quantile(sims, [0.1, 0.25, 0.5, 0.75, 0.9])
    recent = hist[hist.key < key].tail(8)

    print(f"\n{name} ({out['pos']}, {team}) vs {a.opp}   [{out['games_used']} games of history]")
    print("Recent games (yards/targets): " + ", ".join(f"{int(y)}/{int(t)}" for y, t in zip(recent.yards, recent.targets)))
    print(f"Inputs: target share {out['share_mu']:.1%}  team targets {out['team_targets_mu']:.1f}  "
          f"his yds/target {out['own_ypt']:.1f} (shrunk {out['pool_ypt']:.1f})  "
          f"opponent factor x{out['opp_mult']:.3f} (raw x{out['opp_raw']:.3f})")
    print(f"Projected targets: median {np.median(out['targets']):.0f}, mean {out['targets'].mean():.1f}")
    print(f"Projected yards:   10th {q[0]:.0f} | 25th {q[1]:.0f} | MEDIAN {q[2]:.0f} | 75th {q[3]:.0f} | 90th {q[4]:.0f}   mean {sims.mean():.0f}")

    if a.line:
        print(f"\n{'line':>7} {'P(over)':>8} {'price':>7} {'b/e':>6} {'edge':>7} {'EV/$':>7} {'no-vig mkt':>10}  decision")
    for spec in a.line or []:
        parts = spec.split(":")
        line = float(parts[0])
        p_o = prob_over(sims, line)
        over = parse_price(parts[1], a.fee) if len(parts) > 1 else None
        under = parse_price(parts[2], a.fee) if len(parts) > 2 else None
        mkt = f"{no_vig(over, under):.1%}" if over and under else ""
        for side, p, pr in (("over", p_o, over), ("under", 1 - p_o, under)):
            if pr is None:
                if side == "over":
                    print(f"{line:>7} {p_o:>8.1%}   (no price given)")
                continue
            amt, why = stake(p, pr, bankroll=a.bankroll)
            label = f"{side[0].upper()}{line}"
            print(f"{label:>7} {p:>8.1%} {pr.raw:>7} {pr.breakeven:>6.1%} {p - pr.breakeven:>+7.1%} "
                  f"{ev_per_dollar(p, pr):>+7.1%} {mkt if side == 'over' else '':>10}  "
                  f"{('$%d ' % amt) if amt else ''}{why}")
    print("\nModel covers receiving yards only. Injuries/role news are NOT automatic: "
          "use --share-mult (e.g. 1.08 when a teammate is out).")


def cmd_backtest(a):
    model = build()
    df = backtest.run(model, a.seasons, n_sims=a.sims, limit=a.limit)
    print(backtest.report(df))
    if a.out:
        df.to_csv(a.out, index=False)


def cmd_update(a):
    data.ensure_data(HISTORY, refresh_seasons=[CURRENT_SEASON])
    print(f"Refreshed {CURRENT_SEASON} play by play and player list.")


def cmd_log(a):
    if a.action == "add":
        i = ledger.add(a.bet, a.price, a.stake, a.prob, a.sport, a.notes or "")
        print(f"Logged bet #{i}")
    elif a.action == "settle":
        r = ledger.settle(int(a.bet), a.result, a.close)
        print(f"Settled #{r['id']}: {r['result']} {r['pnl']}")
    print(ledger.summary(a.bankroll))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("project")
    pr.add_argument("player")
    pr.add_argument("--opp", required=True, help="Opponent abbreviation, e.g. CHI")
    pr.add_argument("--team")
    pr.add_argument("--season", type=int, default=CURRENT_SEASON)
    pr.add_argument("--week", type=int, help="Week being projected (default: next game)")
    pr.add_argument("--line", action="append", help="LINE:OVER[:UNDER], e.g. 99.5:-113:-113 or 99.5:53c:49c")
    pr.add_argument("--share-mult", type=float, default=1.0, help="Manual target share adjustment for news")
    pr.add_argument("--team-targets", type=float, help="Override projected team targets")
    pr.add_argument("--fee", type=float, default=0.0, help="Fee per $1 contract (Robinhood), e.g. 0.01")
    pr.add_argument("--bankroll", type=float, default=2000)
    pr.set_defaults(func=cmd_project)

    bt = sub.add_parser("backtest")
    bt.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025])
    bt.add_argument("--sims", type=int, default=4000)
    bt.add_argument("--limit", type=int)
    bt.add_argument("--out")
    bt.set_defaults(func=cmd_backtest)

    up = sub.add_parser("update")
    up.set_defaults(func=cmd_update)

    lg = sub.add_parser("log")
    lg.add_argument("action", choices=["add", "settle", "summary"])
    lg.add_argument("bet", nargs="?", help="Bet description (add) or bet id (settle)")
    lg.add_argument("result", nargs="?", choices=["win", "loss", "push"])
    lg.add_argument("--price")
    lg.add_argument("--stake", type=float, default=50)
    lg.add_argument("--prob", type=float)
    lg.add_argument("--close", help="Closing price, for closing line value")
    lg.add_argument("--sport", default="NFL")
    lg.add_argument("--notes")
    lg.add_argument("--bankroll", type=float, default=2000)
    lg.set_defaults(func=cmd_log)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
