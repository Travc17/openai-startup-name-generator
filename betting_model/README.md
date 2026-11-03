# NFL player prop model (v2)

Joint game simulation for **receptions, receiving yards, rushing attempts,
rushing yards, and rush + rec yards**. Prices every main and alternate line,
prices same game parlays from one shared simulation, ranks alt line parlays,
applies the bankroll rules, and logs bets with closing line value.
Built on free nflverse play by play (2022 to current).

## Setup

```
cd betting_model
pip install -r requirements.txt
python nfl.py update          # downloads play by play into data/
```

## Commands

```
# Every key player in a game (injured players removed, their share redistributed)
python nfl.py game SEA CHI --week 8 --out "Rashid Shaheed"

# One player, priced lines (American odds or Robinhood cents like 53c)
python nfl.py project "Jaxon Smith-Njigba" --opp CHI --week 8 \
    --line rec_yds:99.5:-113:-113 --line rec:7.5:+110:-130

# Price a specific parlay
python nfl.py parlay SEA CHI --week 8 \
    --leg "Jaxon Smith-Njigba:rec_yds:over:89.5" \
    --leg "D'Andre Swift:rush_yds:under:59.5" --price +200

# Alt line ladders above and below each main line + best parlays
python nfl.py build SEA CHI --week 8 \
    --main "Jaxon Smith-Njigba:rec_yds:99.5" --main "Jaxon Smith-Njigba:rec:7.5" \
    --main "D'Andre Swift:rush_yds:59.5" --legs 2 [--cross-player-only]

# Backtest (optionally refit parlay correlations on other seasons first)
python nfl.py backtest --seasons 2024 2025 --fit 2022 2023

# Bet log
python nfl.py log add "JSN o99.5 rec yds" --price -113 --stake 50 --prob 0.577
python nfl.py log settle 1 win --close -125
python nfl.py log summary
```

Stats: `targets`, `rec`, `rec_yds`, `rush_att`, `rush_yds`, `rec_rush_yds`.
News: `--out NAME` (ruled out), `--mult "NAME=1.10"` (role change).

## How one game is simulated (20,000 times)

1. **Team volume**: both teams' targets and rushes drawn together. Correlations
   come from 2022+ data: a team that throws more runs less (−0.35), and one
   team's rushing moves opposite the other's (−0.48), which is game script.
2. **Shares**: recency weighted target and carry shares, shrunk toward position averages.
3. **Split**: teammates draw sequentially from what's left, so they compete for the same pie.
4. **Outcomes**: every target is resampled as a (caught, yards) pair from the
   player's own recent targets mixed with a league pool, so receptions and yards
   stay consistent with each other. Same for carries. Opponent adjusted.
5. **Cross player correlation**: a Gaussian copula fitted on real outcomes
   (`nflmodel/copula.json`). Player marginals are untouched.

## Backtest (walk forward, held out 2024 and 2025)

Alt line calibration (model P(over) vs actual), lines set at the model's own percentiles:

| stat | 25th pct line | median line | 75th pct line |
|---|---|---|---|
| receptions | 66% vs 69% | 42% vs 43% | 20% vs 20% |
| receiving yards | 75% vs 77% | 50% vs 52% | 25% vs 26% |
| rush attempts | 71% vs 71% | 46% vs 49% | 22% vs 27% |
| rushing yards | 75% vs 73% | 50% vs 53% | 25% vs 28% |

Overs hit 1 to 4 points more often than predicted. Part of that is a test
artifact (players who played but got zero touches are missing from play by play).

**Parlay correlations (the important finding):** different players in the same
game are nearly independent in real outcomes. Fitted on 2022 to 2025 (17,255 pairs):

| pair | correlation |
|---|---|
| opposing RBs (rush yds) | −0.15 |
| same team WR + RB | −0.03 |
| same team WR + WR | +0.02 |
| opposing WRs | +0.02 |

On held out seasons the copula matched reality about as well as independence did.
So multi player parlays carry little hidden correlation edge. The large real
correlation is **within one player** (receptions with yards), which the
simulation captures and sportsbooks also price.

## Injuries: how much share teammates really absorb

`--out NAME` removes a player and boosts teammates by
`1 + k * (1 / (1 - vacated share) - 1)`, with k fitted on every 2022 to 2025
game where a regular sat (`nflmodel/absences.json`):

| | k | n | actual/predicted: no bump | full proportional | fitted |
|---|---|---|---|---|---|
| targets, first game missed | 0.29 | 1,643 | 1.08 | 0.87 | 1.01 |
| targets, continuing absence | 0.41 | 731 | 1.07 | 0.89 | 0.99 |
| carries, first game missed | 0.27 | 183 | 1.19 | 0.71 | 1.01 |
| carries, continuing absence | 0.36 | 87 | 1.23 | 0.71 | 0.97 |

Full proportional redistribution overshoots by 11 to 29%: backups and game plan
changes soak up most vacated looks. k fitted on 2022 and 2023 alone gave
0.27/0.40/0.23 and held up on 2024 and 2025 (lowest error of the three methods).

## Context data (v3)

| Feature | Data | Backtest result | Status |
|---|---|---|---|
| Zero touch games | nflverse snap counts | Backups and QB rushing error down 2 to 7% | ON |
| Usage tiered share prior | learned from prior seasons only | Backups now calibrated (median line hit 47 to 53%, was 34 to 43%); starters unchanged | ON |
| Depth chart role changes | nflverse daily depth charts (game day snapshot) | Promoted: targets x1.12, carries x1.15. Demoted: x0.82. Fitted 2022 to 2024, held on 2025 (x1.22 / x0.77) | ON |
| Defense by position (WR/TE/RB) | play by play | Slightly WORSE (rec yds CRPS 18.19 vs 18.15) | OFF (`pos_defense=True` to test) |

## Honest limits

* No historical prop lines: calibration is tested, profit is not. Closing line
  value on live bets (`log summary`) is the real test.
* Three way backfields where a player returns from IR are still weak: a back with
  no games in the last 3 is not auto included unless he's a depth chart starter.
* No QB passing props, touchdowns, game lines, weather, coverage, or route data yet. NFL only.
