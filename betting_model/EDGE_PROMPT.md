# Edge search prompt

Paste into a session (or say: "Run the edge search in betting_model/EDGE_PROMPT.md").

---

You are testing WHERE money can be made on Robinhood NFL prop contracts, not whether the model is
accurate. Accuracy (CRPS, calibration) is already tested in `README.md`. Profit is a different
question: a perfectly calibrated model still loses if it buys the wrong price.

Read `CLAUDE.md`, `README.md`, `bets.csv`, `picks_log.csv`, `markets/`, and `reviews/` first.

## What is known (as of 2026-11-03)
* Real record: 1 bet (CHI@SEA combo, +$257.22, CLV −1.7c). One bet proves nothing.
* Captured Robinhood boards: 1 (JAX@BAL wk9, 242 Yes prices, almost no No prices). No board has
  been graded against results yet. There is NO price history, so there is no profitability backtest.
  Every "edge" so far is model probability vs price, not results vs price.
* Fee: 2c per contract (bet #1 receipt). As a share of stake that is 22% at an 11c ticket, 6.8% at
  30c, 4.1% at 50c, 2.3% at 85c (JAX@BAL board). Break-even hit rate = price + 2c.
* Outside evidence (prediction markets, not Robinhood props specifically):
  favorite-longshot bias and a YES "optimism tax" on Kalshi (cheap YES contracts lose most; NO
  beats YES at the same price). Sources: CESifo "Makers and Takers" (2026), CEPR VoxEU column,
  jbecker.dev prediction-market microstructure, arXiv 2607.14430.
* Public prop accounts (ETR, PropsBot, BettingPros, X accounts) use projection vs line. Records
  are self-reported or unaudited, survivorship-biased, and taken at sportsbook prices (−110 with
  line shopping), not Robinhood prices. Treat as hypotheses, not proof.

## Rules for this search
* No result counts until it is graded on games whose prices were captured BEFORE kickoff.
* Cluster by game when computing confidence (rungs on one game move together). Report the 95%
  interval, not just the average.
* Report every hypothesis that fails. If nothing survives, say so in the first line.
* Never change the betting rules in `CLAUDE.md` without Travis's approval.

## Data capture (do this every game, starting now; nothing below is testable without it)
1. Save every board to `markets/<season>_wk<NN>_<AWAY>_at_<HOME>_<open|close>.csv`
   (columns as the report board: `kind,name,stat,line,price,price2,book`, plus a `captured_at`
   timestamp). Capture twice: when the board posts and within 1 hour of kickoff.
2. Get BOTH sides: Yes ask and No ask for every rung (screenshot both, or the order book).
   Assuming No = 100 − Yes overstates No edges by 1-3c.
3. Big-book lines for every player with a Robinhood ladder (DraftKings/FanDuel/BetMGM line and
   both prices), same two times. Without these, H3 and H4 cannot be run.
4. After the game, grade EVERY rung (not just our bets) into `markets/graded.csv`:
   game, player, stat, rung, side, price, model_p, book_novig_p, hit.
5. Historical prop odds: price out SportsGameOdds and OddsPapi (both claim historical player props;
   The Odds API has props only live). If one is affordable, backfill 2024-25 big-book prop lines.

## Hypotheses (test in this order; each has a kill rule)
H1. **YES optimism tax.** Buying No beats buying Yes at the same price on Robinhood props.
    Test: realized ROI after fee by price bucket, Yes vs No. Survives if No ROI > 0 and the 95%
    interval excludes 0 over at least 10 graded games. Kill if No ROI ≤ Yes ROI.
H2. **Longshot bias.** Rungs priced under 20c hit less often than their price.
    Same data. If true, never buy cheap Yes and never build cheap Yes tickets.
H3. **Robinhood vs big books.** When Robinhood's main-line price differs from the big-book no-vig
    probability by 5+ points, the big book is closer to the result (Brier score).
    If true, the edge needs no model: buy the side the big book favors.
H4. **Does the model add information beyond the big book?** Fit p = w·model + (1−w)·book_novig on
    graded props (logistic, walk-forward). If w is near 0, the model is a presentation tool and
    the bets should come from H1-H3. If w is clearly above 0, blend before pricing.
H5. **Same-game correlation.** Robinhood combo tickets priced near the product of leg prices while
    the legs are positively correlated (QB yards + his WR's yards, RB rush yards + team win).
    Test: capture every combo quote vs its leg prices; compare to the sim's joint probability.
H6. **Unders.** Big-book main lines go under more than 52.4% of the time (skewed stats: median below
    mean). Test on captured big-book lines; if the history is bought, test 2024-25 first.
H7. **News speed.** Robinhood prices lag injury news by minutes to hours vs big books.
    Test: open vs close captures around inactives; measure how far Robinhood moved vs the books.
H8. **Hit-rate alt-line parlays (Travis's tickets).** Log every one with price paid and result.
    A ticket that hits 30% at 30c + 2c fee loses 6% per ticket. Survives only if realized ROI > 0
    after 30+ tickets. Hit rate alone is never the test.

## Model work that matters for money (after data capture is running)
1. TD and INT calibration (opens anytime-TD markets, currently blocked).
2. Draft-capital prior for backup QBs (removes a standing blind spot).
3. Defensive injuries in matchups (test, ship only at |t| ≥ 2).
4. Coach-driven role cuts as a flagged blind spot (Thomas Jr. wk9 case).

## Deliverable after each 10 graded games
A one-page table: hypothesis, games, contracts, ROI, 95% interval, verdict (alive / dead / not enough
data), and the single change to the betting rules it supports, sent to Travis for approval.
