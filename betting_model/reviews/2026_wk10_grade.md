# Grades: 2026 week 10

Graded 2026-11-13 05:47 UTC from the saved pre-kickoff files (no reruns). Actuals: nflverse play by play.

## Scores

| Game | Predicted | Actual | Win chance | Winner | Margin miss: model / line | Total miss: model / line |
|---|---|---|---|---|---|---|
| WAS at NYG | WAS 20, NYG 21 | WAS 24, NYG 21 | WAS 42% | wrong | 4 / 4.5 | 4 / 4.5 |

## In-game injuries and early exits (play-by-play text; confirm each with a news link)

* WAS at NYG: Rachaad White (WAS RB): injured Q4 06:21, returned; early exit, no injury note: Devin Singletary (last touch Q1 12:15)

Rows for a player injured in-game who did not return are graded as usual (the model does not simulate it) and
also shown without them below, so an injury does not hide a real model miss.

SNAP COUNTS NOT POSTED for 2026_wk10_WAS_at_NYG: players who played without a touch are missing (not graded as 0).
Regrade after nflverse posts snap counts (usually 1 to 2 days).


## Inside the 80% range (about 80% = calibrated)

| Grade | Inside | Below range | Above range |
|---|---|---|---|
| A | 89% (16/18) | 0 | 2 |
| B | 81% (13/16) | 2 | 1 |
| C | 75% (6/8) | 0 | 2 |
| A+B | 85% (29/34) | 2 | 3 |
| A+B without players hurt or out early | 90% (27/30) | 0 | 3 |

## By stat (A and B grades; mean PIT 0.50 = no bias, above = model too LOW, below = too HIGH)

| Stat | n | Inside 80% | Mean PIT | Actual minus median (median of rows) | Model miss | Book miss | Best miss |
|---|---|---|---|---|---|---|---|
| pass_att | 2 | 100% | 0.66 | +3.5 | 3.5 | 4.5 | 4.3 |
| pass_cmp | 2 | 100% | 0.71 | +3.0 | 3.0 | 4.5 | 4.2 |
| pass_yds | 2 | 100% | 0.76 | +51.7 | 51.7 | 69.0 | 65.5 |
| rec | 10 | 90% | 0.54 | +0.0 | 1.2 | 1.4 | 1.4 |
| rec_yds | 10 | 80% | 0.58 | +7.6 | 26.3 | 25.1 | 25.3 |
| rush_att | 4 | 75% | 0.55 | +2.5 | 4.5 | 1.8 | 2.3 |
| rush_yds | 4 | 75% | 0.49 | +7.2 | 16.8 | 10.5 | 11.5 |

## Model vs book vs best estimate (A and B rows with a book line)

* Mean miss: model 14.01, book 13.82, best (20/80) 13.83 (n=34).
* Closest to the result: model 16, book 18, tie 0.
* Model under the book: actual landed on the model's side 21% (3/14).
* Model over the book: actual landed on the model's side 65% (13/20).

## Biggest misses (outside the 80% range, A and B, farthest first)

| Game | Player | Stat | Median | 80% range | Book | Actual | PIT | In-game |
|---|---|---|---|---|---|---|---|---|
| WAS_at_NYG | Devin Singletary | rush_att | 10 | 5 to 16 | 5.5 | 1 | 0.01 | last touch Q1 12:15 |
| WAS_at_NYG | Devin Singletary | rush_yds | 34.4 | 10.1 to 73.8 | 19.5 | 3 | 0.03 | last touch Q1 12:15 |
| WAS_at_NYG | Isaiah Likely | rec_yds | 48.9 | 13.5 to 99.9 | 46.5 | 127 | 0.97 |  |
| WAS_at_NYG | Cam Skattebo | rec_yds | 8.8 | 0 to 36.3 | 7.5 | 44 | 0.94 |  |
| WAS_at_NYG | Isaiah Likely | rec | 5 | 2 to 8 | 4.5 | 9 | 0.93 |  |

Predicted but no stat line (inactive or no snaps; check the news file): 2026_wk10_WAS_at_NYG: Gregory Desrosiers rush_att, Gregory Desrosiers rush_yds, Van Jefferson rec, Van Jefferson rec_yds
