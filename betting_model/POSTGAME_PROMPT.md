# Post-game prompt: grade everything, learn slowly (Travis, 2026-11-05)

For a whole week's accuracy use GRADE_PROMPT.md (`grade_week.py`); this prompt settles one game's bets.

Say: "Run the post-game review for AWAY at HOME" (or `/nfl-game AWAY HOME grade`). Attach the final box score and
your fill/sell screenshots if the game ended tonight; otherwise run `python nfl.py update` first and use the data.

The rule of this prompt: ONE GAME CHANGES NOTHING. A 60% bet loses 40% of the time. The model changes only when a
pattern repeats across games AND a backtest on past seasons proves the fix (MODEL_LAB_PROMPT.md bar).

---

## 1. Settle the bankroll (exact, from receipts)
* `python nfl.py log settle <id> win|loss|push --close <closing price incl. fee>`; a bet sold early:
  `... cashout --pnl <sale credit minus total cost>`. Note in `bets.csv` what decided it (the play, the player line).
* Closing line value for every bet (taken vs close). After 50 bets CLV is the verdict on the edge, not the P&L.
* Travis's own bets are not the model's: never log them; mention them only if he asks.

## 2. Grade every prediction (not just the bets)
* Scorecard: share of predictions inside the 80% range, by grade (A, B, C). About 80% is calibrated. Above 90% or
  below 70% over 5+ games means the ranges are too wide or too narrow.
* Median error: model vs book line vs best estimate (20/80) on every prop with a book line.
* Every bet the finder flagged at close (edge >= 10%), counted by INDEPENDENT outcome (five rungs on one player are
  one outcome), floor/ceiling legs, and any recommended-but-not-placed bet.
* Score: winner, margin, total vs the prediction and the closing line.
Save `reviews/<game>_scorecard.csv` and `reviews/<game>_actuals.json` (or confirm from nflverse after `update`).

## 3. Classify every miss (outside the 80% range, or a lost bet)
| Class | Test | Action |
|---|---|---|
| Variance | One play explains it (a 65-yd run, a 50-yd catch), or the result sits inside the model's tail | None |
| In-game exit | The player or a teammate left hurt or was pulled (play-by-play injury note, last touch before halftime, news link) | None now; count it in the ledger (MODEL_LAB test queued) |
| Known blind spot confirmed | A CLAUDE.md blind spot (rookie QB, committee, depth player) | None; note that the rule kept it out of bets (or did not) |
| Signal we had and did not use | The news or market showed it before kickoff (with the link) | Process fix in the prompts, not the model |
| Pattern to watch | A model error with a plausible cause (usage, QB quality, injury) | Add or update a row in `reviews/lessons.csv` |
| Bug | Wrong player, wrong join, number that cannot be right | Fix now, with a regression check |

## 4. Update the lessons ledger (`reviews/lessons.csv`), never the model directly
* Same lesson seen again: add the game, raise `games`, keep the evidence specific (player, predicted, actual, range).
* A lesson becomes a MODEL_LAB test only at 3 or more games (or 2 games plus support in the 2025-26 closing-line
  data). It becomes a model change only if the test passes the MODEL_LAB bar on held-out seasons.
* A betting-rule change needs 2 or more seasons of closing-line data behind it AND Travis's approval. Never change
  stakes or the edge threshold because of one night's P&L.

## 5. Grade yourself (Travis asked for this every game)
Three grades, each with one line of evidence:
* Process: rules followed, final pass done after inactives, every number sourced, mistakes caught before a bet.
* Predictions: scorecard and median error vs the book line.
* Bets: result and CLV. A good bet can lose and a bad bet can win: grade the price and the process, then the result.
Then: the one thing to do differently next game (a process fix), and what NOT to change yet (with the count it needs).

## 6. Record
Write `reviews/<season>_wk<NN>_<AWAY>_at_<HOME>.md`, update the SizzleSims scorecard after the data lands
(`python simcast/export.py projections/<file>.json --books markets/<file>_books_close.csv`, build, publish), run
`python nfl.py picks grade`, update HANDOFF.md, commit and push.
