# NFL receiving yards prop model (v1)

Data driven projections for NFL receiving yards props, built on free nflverse
play by play data. Prices every main and alternate line, applies the bankroll
rules, and logs bets with closing line value.

## Setup

```
cd betting_model
pip install -r requirements.txt
python nfl.py update          # downloads 2022 to 2026 play by play into data/
```

## Use

```
# Project a player and price lines (American odds or Robinhood cents)
python nfl.py project "Jaxon Smith-Njigba" --opp CHI --week 8 \
    --line 89.5:-153 --line 99.5:-113:-113 --line 119.5:+166

# Robinhood contract prices, with an optional per contract fee
python nfl.py project "Puka Nacua" --opp SF --line 74.5:52c:50c --fee 0.01

# News adjustment: teammate out, bump target share 8%
python nfl.py project "Tory Horton" --opp CHI --share-mult 1.08 --line 30.5:-115

# Walk forward backtest
python nfl.py backtest --seasons 2024 2025

# Bet log and closing line value
python nfl.py log add "JSN o99.5 rec yds" --price -113 --stake 50 --prob 0.55
python nfl.py log settle 1 win --close -125
python nfl.py log summary
```

## How it works

Each game is simulated 20,000 times:

1. **Team targets**: the offense's recent target volume, adjusted by how many
   targets the opponent usually faces.
2. **Target share**: recency weighted (6 game half life, prior seasons
   discounted), shrunk toward the position average.
3. **Player targets**: binomial draw from team targets and share.
4. **Yards per target**: resampled from the player's own recent targets
   (incompletions count as zero), mixed with a league pool for his position,
   scaled by the opponent's yards per target allowed (shrunk toward average).

The result is a full distribution, so every alternate line gets its own probability.

## Bankroll rules (built in)

* Bet only when model probability beats the break even probability by 2%+.
* $50 below a 4% edge. Above 4%, quarter Kelly, capped at $250.

## Backtest (2024 and 2025, 2,100 player games, walk forward)

| Model percentile | Target | Actual |
|---|---|---|
| 10th | 10% | 8.1% |
| 25th | 25% | 22.6% |
| 50th | 50% | 47.9% |
| 75th | 75% | 74.0% |
| 90th | 90% | 90.3% |

Brier skill vs a coin flip on a proxy line: **+5.2%**. Median absolute error 26.1
yards vs 27.1 for a naive recent average.

## Honest limits

* **No real historical prop lines.** The backtest proves calibration, not
  profit. Real books set sharper lines than the proxy. The only true test is
  closing line value on live bets (`log summary`).
* **News is manual.** Injuries, inactives, and role changes need `--share-mult`.
* **Receiving yards only.** No rushing, passing, receptions, TDs, game lines, or NBA yet.
* **Games with zero targets are missing** from share history (play by play only
  records targets), which slightly inflates share for part time players.
* Weather, coverage scheme (man vs zone), and route data are not in v1.
