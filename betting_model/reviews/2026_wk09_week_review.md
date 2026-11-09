# Week 9 review (graded 2026-11-09, GRADE_PROMPT.md; numbers in 2026_wk09_grade.md)

## Result
* Games projected: JAX@BAL, CIN@ATL, DAL@IND, GB@NE. Winners 3 of 4 (GB@NE wrong: GB 45, NE 27 vs predicted GB 21, NE 24).
* A+B predictions inside the 80% range: 89% (90/101); 91% without players hurt or out early. Slightly wide; 4 games
  is under the 5-game bar. GB@NE alone: A 11/16.
* League panel (all 13 graded week 9 games, live model): calibrated (receiving under-p50 46 to 50%, p90 92 to 93%).
* Model vs book: mean miss model 16.5, book 15.6, best estimate 15.7 (n=96). Book more accurate; 20/80 holds.
  Model under the book: actual on the model's side 61% (35/57). Model over: 50% (19/38).

## In-game exits (model does not simulate these)
* Josh Jacobs: broken finger in Q1 (LaFleur postgame): https://www.thebiglead.com/josh-jacobs-hand-injury-update-status-vs-patriots/
  4 carries, 5 yds vs median 14 / 49. Kaleb Johnson (not in the sims) took 14 carries for 68.
* Rhamondre Stevenson: knee, ruled out in Q3: https://www.patspulpit.com/new-england-patriots-injuries/143532/rhamondre-stevenson-injury-patriots-rb-ruled-out-of-packers-game-with-knee-injury
  6 carries vs median 15.
* Jake Ferguson (DAL TE): injured Q3, did not return (play-by-play); news link not found.
* Mike Gesicki (CIN TE): last touch Q2 0:45, no injury note; not checked.

## Misses by class
| Class | Misses | Action |
|---|---|---|
| In-game exit | Jacobs rush att/yds, Stevenson rush att, Kaleb Johnson's carries | Ledger row at 3 games: MODEL_LAB test queued |
| Signal we had and did not use | Hollins active off IR, written "not modeled" (wrong: weeks 1-4 usage) | Fixed: ROSTER CHECK in the report |
| Bug | Kaleb Johnson skipped (RB4 behind inactive Lloyd) | Fixed: depth rank skips ruled-out players |
| Variance (game script, GB up big) | Golden 10-164, Watson 171, Love 372, Kraft 1 yd; Lamb 195 (DAL@IND); Chase 155 (CIN@ATL) | None |

## Code changed (bugs only; regression_check No drift 2026-11-09)
* `nfl.py roster_check`, depth rank among active players, game-day depth chart in replays.
* `grade_week.py` (new): grades saved files, in-game injuries from play-by-play, league panel, SizzleSims scorecards.

## Not changed (and the count each needs)
* Range width (89% inside): needs 5+ games above 90%.
* Rushing bias (mean PIT 0.43 to 0.45, n=11): needs 5+ games at 0.40 or less.
* Early-exit simulation: at 3 games, so it is a MODEL_LAB test now; ships only if it passes the bar.

## Self-grade
* Process: C. Final pass after inactives and every number sourced, but I left an active receiver out with a wrong
  note and missed a depth-chart back; wind forecast not found.
* Predictions: B. 89% inside on A+B, league-wide calibrated; the book beat the model on mean miss (as tested).
* Bets: no model bets on the Sunday games (none placed); week total is the two JAX@BAL bets (net -17.17).
