# Week 8 2026 CHI at SEA: re-sim with the 2026-11-03 tools vs the actual box score

Run 2026-11-03 (after the game; inputs limited to what was known at kickoff). 25,000 sims, seed 7.
* Lines: closing SEA -3, total 46.5 (nflverse `spread_line`/`total_line`). No pre-game settings were saved for
  the original run, so they were rebuilt: `--out` = roster players with zero snaps in the game (inactives are
  public 90 minutes before kickoff): Shaheed, E. Wilson, Monangai, Velus Jones Jr., Arroyo, Kmet.
* Tools: full roster (every RB/WR/TE with snaps in the last 2 games), route role, QB layer, 2019-21 pbp and
  2024-25 PFF restored. Data: `2026_wk08_CHI_at_SEA_resim_vs_actual.csv`.

## Result
* Score: model SEA 25, CHI 22 (SEA wins 63%; centered on the market line). Actual CHI 34, SEA 17.
* 64 player-stats with a real role (avg >= 1): 5 outside the sims' 10-90% range = 8% (expected 20%).
  Median percentile of actuals 54 (50 = unbiased). Above p90: 4, below p10: 1.
* Volume ran above the model: targets 65 actual vs 54 sim average; pass attempts 68 vs 63.
  Rush yards ran below: 147 actual vs 203 sim average.

## Original run (review, 20,000 sims) vs this re-sim, percentile of the actual
| Player | Stat | Actual | Original median (pct) | Re-sim median (pct) |
|---|---|---|---|---|
| Smith-Njigba | rec / yds | 6 / 118 | 7 / 105 (38 / 58) | 7 / 113 (34 / 54) |
| Horton | targets | 6 | 1 (98) | 2 (97) |
| Barner | rec | 2 | 3 (34) | 3 (28) |
| Kupp | rec yds | 7 | 27 (19) | 38 (12) |
| Charbonnet | carries | 6 | 7 (35) | 14 (5) |
| Price | carries | 10 | 5 (90) | 10 (47) |
| E. Wilson | carries | 0 | 10 (0) | out |
| Loveland | rec / yds | 7 / 65 | 4 / 37 (84 / 83) | 4 / 38 (84 / 81) |
| Burden | rec | 7 | 4 (89) | 4 (89) |
| Odunze | rec yds | 87 | 35 (92) | 41 (90) |
| Swift | carries / yds | 27 / 69 | 15 / 54 (98 / 70) | 15 / 54 (98 / 69) |
| R. Johnson | rush yds | 17 | 13 (61) | 14 (58) |

## Read (one game: weak evidence)
1. The biggest fix came from the inactive list, not the new roster rule: with Wilson out, Price's carries were
   right (10 vs 10). His share went too heavily to Charbonnet instead (14 projected, 6 actual).
2. Distributions were wide enough (8% outside 10-90). Misses were the blowout script (Swift 27 carries) and
   next-man-up targets (Horton), both already known gaps.
3. Relevant to all-unders bets: CHI's top three receivers all finished above their medians and team targets
   beat the sim by 11. Rush yards finished below. Track whether this repeats before trusting receiving unders.
