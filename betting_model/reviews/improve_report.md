# Improvement report (2026-11-10 14:36 UTC)

Graded games CHOOSE what to test; only the MODEL_LAB backtest (2024-25 weeks 4+ and 2026 to date) decides what ships.

## Graded games: 5 (wk09_BUF_at_MIN, wk09_CIN_at_ATL, wk09_DAL_at_IND, wk09_GB_at_NE, wk09_JAX_at_BAL)

| Grade | Inside 80% range | Below | Above |
|---|---|---|---|
| A | 88% (64/73; 95% 78% to 93%) | 3 | 6 |
| B | 89% (48/54; 95% 78% to 95%) | 3 | 3 |
| C | 83% (85/103; 95% 74% to 89%) | 7 | 11 |
| A+B | 88% (112/127; 95% 81% to 93%) | 6 | 9 |
| A+B, no in-game exits | 90% (103/115; 95% 83% to 94%) | | |

Calibrated = about 80%. Act only when the whole 95% interval sits outside 70 to 90% AND the league panel agrees.

## By stat (A+B): bias and accuracy vs the book

| Stat | n | Inside | Mean PIT (t vs 0.50) | Model miss | Book miss | Best miss | Model closer |
|---|---|---|---|---|---|---|---|
| pass_att | 9 | 100% | 0.47 (-0.4) | 4.3 | 4.1 | 4.1 | 5/9 |
| pass_cmp | 9 | 89% | 0.45 (-0.7) | 2.8 | 2.4 | 2.5 | 3/9 |
| pass_yds | 9 | 78% | 0.54 (+0.4) | 64.1 | 53.8 | 55.9 | 3/9 |
| rec | 38 | 97% | 0.52 (+0.6) | 1.3 | 1.5 | 1.5 | 22/36 |
| rec_yds | 38 | 84% | 0.54 (+1.0) | 23.8 | 25.6 | 25.3 | 19/36 |
| rush_att | 12 | 67% | 0.47 (-0.3) | 4.7 | 4.7 | 4.7 | 3/11 |
| rush_yds | 12 | 92% | 0.46 (-0.4) | 19.9 | 20.9 | 20.7 | 8/12 |

## The betting-relevant check (direction vs the book)

* Model under the book: result on the model's side 63% (50/79; 95% 52% to 73%)
* Model over the book: result on the model's side 52% (22/42; 95% 38% to 67%)
* Mean miss: model 15.43, book 14.93, best (20/80) 14.96 (n=122)

## Where the misses come from (A+B outside the range)

| Slice | Misses | Rows | Miss rate |
|---|---|---|---|
| in-game exit (hurt, no return, or out early) | 3 | 12 | 25% |
| QB stats | 3 | 27 | 11% |
| rushing | 5 | 24 | 21% |
| receiving | 7 | 76 | 9% |
| blowout game (final margin 17+) | 14 | 97 | 14% |

## Live model on every 2026 game, weeks 1-9 (real QBs, closing spread, players who played)

The big sample: this, not the graded games, says whether ranges or medians drifted.

| Stat | n | under p10 | under p50 | under p90 | CRPS | baseline p10/p50/p90, CRPS |
|---|---|---|---|---|---|---|
| targets | 1100 | 9.0% | 49.0% | 90.4% | 1.483 | 7.1/49.6/91.3, 1.4235 |
| rec | 1100 | 10.4% | 50.6% | 90.5% | 1.160 | 9.4/48.4/91.3, 1.1216 |
| rec_yds | 1100 | 10.8% | 50.5% | 89.4% | 15.942 | 11.2/49.2/90.6, 15.1864 |
| pass_att | 272 | 8.8% | 47.8% | 88.6% | 4.525 | 11.9/55.1/89.8, 4.7987 |
| pass_cmp | 272 | 9.9% | 47.8% | 90.4% | 3.173 | 12.7/64.4/91.5, 3.5242 |
| pass_yds | 272 | 11.8% | 47.4% | 92.3% | 41.370 | 7.6/58.5/96.6, 40.6228 |
| rush_att | 366 | 13.4% | 47.3% | 89.3% | 3.034 | 12.6/40.4/83.1, 3.2432 |
| rush_yds | 366 | 13.1% | 53.3% | 88.8% | 17.947 | 9.8/42.6/85.8, 18.9021 |

Flag a stat when a coverage number is 5+ points off 10/50/90 here with n >= 300 (and in the baseline sample too:
then it is a model property, not a 2026 drift).

## Lessons ledger triage

| Rank | Lesson | Games | Category | Status | Next |
|---|---|---|---|---|---|
| 1 | Starters leaving early (blowouts and in-game injuries) are not simulated; backups' upper t | 4 | known_gap | test_queued | READY for MODEL_LAB |
| 2 | Backup QBs (third-string and veteran backups) land far below the QB-layer prior | 2 | blind_spot_confirmed | watch | needs 1 more game(s) |
| 3 | Depth-add TE with a real snap share projected too low | 1 | pattern | watch | needs 2 more game(s) |
| 4 | Scenario inputs: zone fit + QB-specific target split (untested) | 1 | pattern | watch | needs 2 more game(s) |

Closed or fixed: 5 (Rush-yds unders on a change-of-pace back, Replay after update does not match saved, Player activated off IR / first game bac, Depth-chart backstop counted inactive pl, Depth skill players on the inactive list)
