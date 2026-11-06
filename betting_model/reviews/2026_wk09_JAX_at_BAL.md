# Review: JAX 33 at BAL 10, week 9 2026 (TNF, 2026-11-05)

Graded from the ESPN final box score (Travis's screenshots; `reviews/2026_wk09_JAX_at_BAL_actuals.json`). nflverse data
is not in yet: rerun `simcast/export.py` and `nfl.py picks grade` after the next `update` to confirm.

## Model bankroll
| Bet | Result | P&L | CLV |
|---|---|---|---|
| #2 parlay NO Henry 80+ / NO Hill 20+ rush (41.5c, $49.60) | LOSS: Henry 57 (won), Hill 85 on 9 carries incl. a 65-yd TD | -$49.60 | -1.2 pts (taken 43.9c incl. fee, close ~42.7c) |
| #3 NO Strange 40+ rec yds (55c, $50.85) | Cashed out at 93c 10:36 PM (Strange finished 2-22) | +$32.43 (holding: +$39.15) | +3.0 pts |
| #4 NO Washington 60+ rec yds (recommended, NOT placed) | Would have LOST: 61 yds on 2 catches, one a 50-yd TD | n/a | n/a |
Bankroll $2,257.22 -> $2,240.05. Lifetime 3 bets settled: +$240.05; CLV average 0.0 pts (1 of 3 beat the close).

## Predictions (median game JAX 25, BAL 16; JAX win 77%)
* Winner right; margin 9 predicted vs 23 actual; total 41 vs 43.
* Scorecard: 44 of 54 inside the 80% range (81%; 80% expected). Grade A 9/9, B 6/6, C 29/39 (74%).
* Accuracy vs the books on 41 props with a book line (mean abs error): model 12.40, book line 12.23, best estimate
  12.23. Same order as the 2025-26 history (line slightly better; the blend matches the line).
* Floor/ceiling legs marked ADD: 7 of 7 hit (avg price 81c, avg blend 87%). Expected about 6 of 7.
* Close-board rungs with edge >= 10% (model-only): 5 of 12 won, but they are only about 4 independent outcomes (Hill
  rushing, Washington yards, Washington catches, Tuten receiving): 2 won, 2 lost.

## Misses, classified (see POSTGAME_PROMPT.md: classify, count, do not overreact)
| Miss | Class | Action |
|---|---|---|
| Hill 85 rush yds (65 on one run) | Variance (single play) + usage | Log. The yards are one play; the usage is below |
| Hill 9 carries (pred 2, range 0-6), Abdullah 7 (pred 2) | Pattern to watch: RB2/RB3 carry spike (rookie QB, run-heavy BAL; JAX starter Tuten playing hurt, 2.4 ypc) | Lessons ledger, count 1. Test only at 3+ |
| Fagnano 10/18, 60 yds, 2 INT (pred 18/28, 164) | Known blind spot confirmed (undrafted rookie QB; prior = average backup) | Rule worked: BAL pass catchers were kept out of bets. Adds evidence for the backup-QB prior test |
| Flowers 6 rec yds (pred 54) | Same blind spot (his QB) | None |
| Washington 61 (one 50-yd TD), Boerkircher 61 (one 52-yd catch) | Variance (single play) | None |
| Tuten 12-29 (pred 16-60) | Inside range; played hurt in a 3-way split | Log with the RB2 spike item |

## What held
Henry 17-57 (pred 16-60), Lawrence 242 yds (pred 234), Meyers/Washington/Strange inside their ranges, every A and B
grade inside. The blind-spot rule avoided the worst miss of the night (BAL passing).
