# Handoff (2026-11-03): open items for the next session

Read this, `CLAUDE.md`, `PROJECTION_PROMPT.md`, `BETFINDER_PROMPT.md`, and `EDGE_PROMPT.md` first.
Run `git pull origin claude/robinhood-trading-mcp-qo26do` before anything else.

## State
* Bankroll $2,257.22 (1 bet settled: +$257.22, closing-line value −1.7c). `python nfl.py log summary`.
* Two-stage pipeline built: projections (`report --proj`) then bet finder (`nfl.py price`), odds feed
  `nfl.py odds AWAY HOME --out ...` (The Odds API, key in env var `ODDS_API_KEY`). The live odds pull
  has NOT run yet: first job is to test it.

## Next game: JAX at BAL, week 9, Thursday 2026-11-05
* Projections: `projections/2026_wk09_JAX_at_BAL.json` (made 2026-11-03, published report settings).
* Robinhood board (Yes prices only): `markets/2026_wk09_JAX_at_BAL_open.csv`. News with sources:
  `news/2026_wk09_JAX_at_BAL.json` (Lamar Jackson and Tyler Huntley out, Joe Fagnano starts).
* Published report: https://claude.ai/artifact/GURncLCo67PbWAK5rQD5Nv (read it with the Artifact
  tool before republishing).
* First test: `python nfl.py odds JAX BAL --out markets/2026_wk09_JAX_at_BAL_books_open.csv`, then
  `python nfl.py price --proj projections/2026_wk09_JAX_at_BAL.json --quotes markets/2026_wk09_JAX_at_BAL_books_open.csv --board markets/2026_wk09_JAX_at_BAL_open.csv`.
  Report how many lines came back with both sides priced and the credits left.
* Bets under consideration (from the Robinhood-only analysis, re-check against book lines first):
  No on Bhayshul Tuten 3+ catches ($110, only if No costs 74c or less) and No on Justice Hill 20+ rush
  yds ($110, only if No costs 71c or less). Travis has not sent No-side prices yet.
* Blind spots for this game: Brian Thomas Jr. (coach-driven role cut), all BAL pass catchers (third-string
  QB), Josh Cameron, Ja'Kobi Lane, Nick Boerkircher, Joe Fagnano; Henry and Hill receiving only.
* Paper log has 3 Thomas Jr. rows logged before the blind-spot override; leave them (never hand-edit).

## After the game
1. Settle any model bets in `bets.csv` with closing prices; `python nfl.py picks grade`.
2. Grade EVERY rung on the saved board and every book quote (EDGE_PROMPT.md data capture step 4):
   first real test of H1/H2 (No vs Yes, longshot bias). One game: weak evidence, report it as such.
3. Write the review in `reviews/`.

## Waiting on Travis
* Approval of the proposed rule: real-money bets only on "BOTH AGREE" (model and books agree).
* Canva carousel DAHZ4XCn3BY (https://canva.link/9irp6wkayeavxk3): fixes were staged in an edit
  transaction in the previous session; if that expired, redo the fixes and ask before committing.
* Offered, not yet approved: logging Travis's own hit-rate parlays (tagged), a break-even floor for
  hit-rate parlays, a defensive-injury matchup test, "coach-driven role cuts" as a playbook blind spot.
