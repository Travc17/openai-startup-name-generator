# Handoff (2026-11-03, session 2): open items for the next session

Working branch: `claude/robinhood-trading-mcp-qo26do` (see CLAUDE.md "Session start").
Read this, `CLAUDE.md`, `PROJECTION_PROMPT.md`, `BETFINDER_PROMPT.md`, and `EDGE_PROMPT.md` first.

## State
* Bankroll $2,257.22 (1 bet settled: +$257.22, closing-line value −1.7c). `python nfl.py log summary`.
* Two-stage pipeline built: projections (`report --proj`) then bet finder (`nfl.py price`).
* Odds feed TESTED 2026-11-03 20:05 UTC (`nfl.py odds`): works.
  * Main lines: 188 quotes, 4 books (DraftKings, FanDuel, BetMGM, Fanatics; Caesars not posting this
    game), 94 of 94 lines with both sides priced, 10 credits.
  * `--alt`: 1,052 quotes, 8 books, 15 credits. Alt lines are Over only, so `price` cannot use them
    for the market check (needs both sides). See "Known issues".
  * Credits: 51 used, 19,949 left (account quota is 20,000, not the 500 free plan BETFINDER_PROMPT.md assumes).

## Next game: JAX at BAL, week 9, Thursday 2026-11-05 8:15 PM ET
* Projections: `projections/2026_wk09_JAX_at_BAL.json` (made 2026-11-03 19:28 UTC).
* Robinhood board (Yes prices only): `markets/2026_wk09_JAX_at_BAL_open.csv`. News with sources:
  `news/2026_wk09_JAX_at_BAL.json` (Lamar Jackson and Tyler Huntley out, Joe Fagnano starts).
* Book captures (open): `markets/2026_wk09_JAX_at_BAL_books_open.csv`, `..._books_open_alt.csv`,
  `..._gamelines.csv`. Priced: `markets/2026_wk09_JAX_at_BAL_priced_open.csv`, `..._priced_open_alt.csv`.
* Published report: https://claude.ai/artifact/GURncLCo67PbWAK5rQD5Nv (read it with the Artifact
  tool before republishing).

### Bet finder result (main lines, 2026-11-03)
* BOTH AGREE: 0. Market only: 0. Model vs market: 33 (paper only). Blind spot: 61. Pass: 306.
* All 33 model vs market rows are UNDERS on main lines, model 4 to 21 points above the books' no-vig
  (biggest: Justice Hill rush yds under 13.5, model 73.7% vs books 49.9%). Same direction on every
  line = likely model bias on this game, not 33 edges. Log it for H4; one game is weak evidence.
* Robinhood Yes rungs with a two-sided book price at the same number: 18 of 242. None beats the
  books (best market edge −0.6% after the 2c fee).

### Bets under consideration (Robinhood No; need Travis's No-side prices)
Hand check against book alt ladders (Over only, so the books' numbers include their cut and the
real Over chance is a little lower):
| Rung | RH Yes | Books / Kalshi Over | Model Over | No price where model AND books agree (2%+ after 2c fee) | Model-only limit (handoff v1) |
|---|---|---|---|---|---|
| Justice Hill 20+ rush yds | 46c | DK 35.6%, FD 37.3%, Kalshi 38.0% | 17.5% | ≤ 58c | ≤ 71c |
| Bhayshul Tuten 3+ catches | 52c | Fanatics 42.6% (one book) | 21.5% | ≤ 53c | ≤ 74c |
* Between the two columns the books say no: model vs market, paper only (BETFINDER_PROMPT.md).
* Robinhood board was captured from screenshots on 11/3 (time unknown); books at 20:05 UTC. Re-check
  the Robinhood Yes and No prices before acting.
* Blind spots for this game: Brian Thomas Jr. (coach-driven role cut), all BAL pass catchers (third-string
  QB), Josh Cameron, Ja'Kobi Lane, Boerkircher, Joe Fagnano; Henry and Hill receiving only.
* Paper log has 3 Thomas Jr. rows logged before the blind-spot override; leave them (never hand-edit).

### Known issues found in the test (not fixed; ask Travis before changing code)
1. `price` treats any `book` row on the Robinhood board as a bettable venue: "Sports Gambling Podcast
   (11/3)" produced the only "model only" row (Lawrence pass att under 31.5, −107). Not a sportsbook.
2. Alt lines are one-sided, so `price` gives no market check on Robinhood ladder rungs. Fix idea:
   remove an estimated alt-line cut, or use Kalshi (two-sided ladders, region `us_ex`) as the market.
3. Name mismatch: books list "Nate Boerkircher", the Robinhood board and this file said "Nick".
   Projections have no Boerkircher and no Josh Cuevas, and no Lawrence rush attempts (30 rows "no projection").
4. BETFINDER_PROMPT.md lists Caesars and a 500-credit free plan; neither matches this account.

## Open items, in order
1. Get No-side prices for the two rungs above from Travis; apply the table.
2. Game day: re-pull books (`nfl.py odds JAX BAL --out markets/2026_wk09_JAX_at_BAL_books_close.csv`)
   and a Robinhood close board within 1 hour of kickoff (EDGE_PROMPT.md data capture).
3. Decide with Travis on known issues 1 and 2.

## After the game
1. Settle any model bets in `bets.csv` with closing prices; `python nfl.py picks grade`.
2. Grade EVERY rung on the saved board and every book quote (EDGE_PROMPT.md data capture step 4):
   first real test of H1/H2 (No vs Yes, longshot bias). One game: weak evidence, report it as such.
3. Write the review in `reviews/`.

## Waiting on Travis
* No-side prices for Hill 20+ rush yds and Tuten 3+ catches.
* Approval of the proposed rule: real-money bets only on "BOTH AGREE" (model and books agree).
* Canva carousel DAHZ4XCn3BY (https://canva.link/9irp6wkayeavxk3): fixes were staged in an edit
  transaction in the previous session; if that expired, redo the fixes and ask before committing.
* Offered, not yet approved: logging Travis's own hit-rate parlays (tagged), a break-even floor for
  hit-rate parlays, a defensive-injury matchup test, "coach-driven role cuts" as a playbook blind spot.
