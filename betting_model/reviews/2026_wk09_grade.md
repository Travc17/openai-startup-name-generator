# Grades: 2026 week 9

Graded 2026-11-09 05:13 UTC from the saved pre-kickoff files (no reruns). Actuals: nflverse play by play.

## Scores

| Game | Predicted | Actual | Win chance | Winner | Margin miss: model / line | Total miss: model / line |
|---|---|---|---|---|---|---|
| CIN at ATL | CIN 28, ATL 25 | CIN 34, ATL 17 | CIN 60% | right | 14 / 14.0 | 2 / 1.0 |
| DAL at IND | DAL 28, IND 24 | DAL 27, IND 23 | DAL 64% | right | 0 / 0.5 | 2 / 1.5 |
| GB at NE | GB 21, NE 24 | GB 45, NE 27 | GB 37% | wrong | 21 / 21.0 | 27 / 27.5 |
| JAX at BAL | JAX 25, BAL 16 | JAX 33, BAL 10 | JAX 77% | right | 14 / 13.5 | 2 / 3.0 |

## In-game injuries and early exits (play-by-play text; confirm each with a news link)

* CIN at ATL: early exit, no injury note: Mike Gesicki (last touch Q2 00:45)
* DAL at IND: Jake Ferguson (DAL TE): injured Q3 03:23, did not return
* GB at NE: Cameron Latu (NE TE): injured Q3 04:10, returned; Rhamondre Stevenson (NE RB): injured Q3 03:29, did not return; early exit, no injury note: Josh Jacobs (last touch Q1 08:41)

Rows for a player injured in-game who did not return are graded as usual (the model does not simulate it) and
also shown without them below, so an injury does not hide a real model miss.

SNAP COUNTS NOT POSTED for 2026_wk09_CIN_at_ATL, 2026_wk09_DAL_at_IND, 2026_wk09_GB_at_NE: players who played without a touch are missing (not graded as 0).
Regrade after nflverse posts snap counts (usually 1 to 2 days).


## Inside the 80% range (about 80% = calibrated)

| Grade | Inside | Below range | Above range |
|---|---|---|---|
| A | 87% (48/55) | 1 | 6 |
| B | 91% (42/46) | 3 | 1 |
| C | 80% (65/81) | 5 | 11 |
| A+B | 89% (90/101) | 4 | 7 |
| A+B without players hurt or out early | 91% (81/89) | 1 | 7 |

## By stat (A and B grades; mean PIT 0.50 = no bias, above = model too LOW, below = too HIGH)

| Stat | n | Inside 80% | Mean PIT | Actual minus median (median of rows) | Model miss | Book miss | Best miss |
|---|---|---|---|---|---|---|---|
| pass_att | 7 | 100% | 0.45 | +0.0 | 4.3 | 4.1 | 4.1 |
| pass_cmp | 7 | 100% | 0.46 | -1.0 | 1.6 | 1.1 | 1.2 |
| pass_yds | 7 | 86% | 0.57 | +7.9 | 59.8 | 49.1 | 51.2 |
| rec | 29 | 97% | 0.54 | +0.0 | 1.4 | 1.7 | 1.7 |
| rec_yds | 29 | 83% | 0.54 | +1.9 | 28.3 | 29.6 | 29.6 |
| rush_att | 11 | 73% | 0.43 | +1.0 | 4.1 | 3.9 | 3.9 |
| rush_yds | 11 | 91% | 0.45 | -3.1 | 20.2 | 20.7 | 20.6 |

## Model vs book vs best estimate (A and B rows with a book line)

* Mean miss: model 16.51, book 15.55, best (20/80) 15.69 (n=96).
* Closest to the result: model 48, book 47, tie 1.
* Model under the book: actual landed on the model's side 61% (35/57).
* Model over the book: actual landed on the model's side 50% (19/38).

## Biggest misses (outside the 80% range, A and B, farthest first)

| Game | Player | Stat | Median | 80% range | Book | Actual | PIT | In-game |
|---|---|---|---|---|---|---|---|---|
| GB_at_NE | Josh Jacobs | rush_yds | 49 | 18.6 to 91.1 | 49.5 | 5 | 0.01 | last touch Q1 08:41 |
| GB_at_NE | Matthew Golden | rec_yds | 55.2 | 14.8 to 116.4 | 68.5 | 164 | 0.98 |  |
| GB_at_NE | Josh Jacobs | rush_att | 14 | 7 to 21 | 15.5 | 4 | 0.02 | last touch Q1 08:41 |
| GB_at_NE | Christian Watson | rec_yds | 56.2 | 11.8 to 125.2 | 68.5 | 171 | 0.97 |  |
| DAL_at_IND | CeeDee Lamb | rec_yds | 80.8 | 29.4 to 152.2 | 85.5 | 195 | 0.97 |  |
| GB_at_NE | Matthew Golden | rec | 4 | 2 to 8 | 5.5 | 10 | 0.97 |  |
| GB_at_NE | Rhamondre Stevenson | rush_att | 15 | 8 to 22 | 14.5 | 6 | 0.04 | injured Q3 03:29, did not return |
| GB_at_NE | Tucker Kraft | rec_yds | 37 | 7.8 to 82.8 | 45.5 | 1 | 0.05 |  |
| CIN_at_ATL | Samaje Perine | rush_att | 5 | 2 to 10 | 5.5 | 11 | 0.93 |  |
| GB_at_NE | Jordan Love | pass_yds | 252.6 | 158.6 to 357.2 | 271.5 | 372 | 0.93 |  |
| CIN_at_ATL | Ja'Marr Chase | rec_yds | 83.3 | 30.9 to 152.3 | 77.5 | 155 | 0.91 |  |

Predicted but no stat line (inactive or no snaps; check the news file): 2026_wk09_CIN_at_ATL: Tahj Brooks rush_att, Tahj Brooks rush_yds, Erick All rec, Erick All rec_yds; 2026_wk09_DAL_at_IND: DJ Giddens rush_att, DJ Giddens rush_yds, Malik Davis rush_att, Malik Davis rush_yds; 2026_wk09_GB_at_NE: Bo Melton rec, Bo Melton rec_yds, Jonnu Smith rec, Jonnu Smith rec_yds; 2026_wk09_JAX_at_BAL: Rasheen Ali rush_att, Rasheen Ali rush_yds, Rasheen Ali rec, Rasheen Ali rec_yds

## Every game of 2026 week 9 (live model, real starting QBs, closing spread, players who played)

Calibrated reads 10 / 50 / 90. Baseline = regression sample (2025 weeks 10-13).

| Stat | n | under p10 | under p50 | under p90 | baseline p10 / p50 / p90 |
|---|---|---|---|---|---|
| targets | 115 | 8% | 48% | 93% | 7.1 / 49.6 / 91.3 |
| rec | 115 | 8% | 50% | 92% | 9.4 / 48.4 / 91.3 |
| rec_yds | 115 | 10% | 46% | 93% | 11.2 / 49.2 / 90.6 |
| rush_att | 35 | 11% | 43% | 91% | 12.6 / 40.4 / 83.1 |
| rush_yds | 35 | 6% | 46% | 100% | 9.8 / 42.6 / 85.8 |
| pass_att | 26 | 8% | 54% | 100% | 11.9 / 55.1 / 89.8 |
| pass_cmp | 26 | 12% | 62% | 100% | 12.7 / 64.4 / 91.5 |
| pass_yds | 26 | 8% | 58% | 92% | 7.6 / 58.5 / 96.6 |

under p50 above 50% = results came in BELOW the model's median more often than they should (model high);
below 50% = model low. One week of about 14 games moves these by several points on noise alone.
