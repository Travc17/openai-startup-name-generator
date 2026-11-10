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

## Update 2026-11-10 (GRADE_PROMPT rerun after snap counts posted)
* Snap counts posted for all 14 Sunday games; regrade unchanged for A+B (90/101 inside); C now 69/85 with zero-touch players counted.
* League panel now 14 games (TB@CHI added): receiving under-p50 45 to 49%, p90 93%; calibrated.
* Gesicki early exit (CIN@ATL): injury news not found.
* Process miss: five depth skill players were simulated but inactive (no snaps). Fixed: INACTIVE CHECK in the report and a
  SIM_PROMPT final-pass rule. Ledger row added.
* BUF@MIN (MNF) not in nflverse yet. Preliminary: BUF 23, MIN 6 (predicted BUF 25, MIN 22; BUF 62%: winner right). Wentz
  8 of 25 (model median 18 of 28, 183 yds; book 218.5); Allen 21 of 31, 234 yds (model 178, book 230.5); Cook 31 for 107
  (model 90, book 84.5). Full grade and the scenario test after the data posts.

## Update 2026-11-10 9:40 AM ET: BUF@MIN graded (all 5 games final)
* BUF 23, MIN 6 (pred BUF 25, MIN 22; BUF 62%): winner right; total miss 18 (line 16.5). Winners 4 of 5 for the week.
* BUF@MIN A+B inside 22/26 (85%); model beat the book here: mean miss 11.5 vs 12.7, closer on 15 of 26.
* Week (5 games): A+B 88% inside (112/127), 90% without in-game exits; mean miss model 15.4, book 14.9, best 15.0 (n=122);
  model under the book: result on the model's side 63% (50/79); over: 52% (22/42).
* QB lines vs official box: Allen 21/31 234 matches ESPN; Wentz 8/24 81 in nflverse vs 8 of 25 reported (one attempt).
* In-game: Jefferson injured Q1, returned. Wentz pulled late for Brosmer (counted in the early-exit ledger row).
* Correction: the preliminary note said Travis's 5-leg MIN legs almost certainly missed; all five legs hit (Jefferson 58,
  Cook 107, Shakir 53, Hockenson 33, Addison 28). The note ignored Brosmer's relief passing.
* Scenario test (reviews/2026_wk09_BUF_at_MIN_scenario_test.csv): scenario A slightly better than official on 16 legs
  (15.30 vs 16.04 mean miss; Brier 0.1574 vs 0.1596). One game: watch, no change.
