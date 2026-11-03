# Handoff (2026-11-03, session 2, 20:35 UTC): open items for the next session

Working branch: `claude/robinhood-trading-mcp-qo26do` (see CLAUDE.md "Session start"). This session's
commits are on `claude/tender-faraday-offel8` (fast-forward of the working branch); Travis has not yet
chosen how they reach master (PR #1 is open from the working branch).
Read this, `CLAUDE.md`, `PROJECTION_PROMPT.md`, `BETFINDER_PROMPT.md`, and `EDGE_PROMPT.md` first.

## State
* Bankroll $2,257.22 (1 bet settled: +$257.22, closing-line value −1.7c). `python nfl.py log summary`.
* VENUE IS KALSHI (Travis, 2026-11-03). Robinhood is dropped; fee assumed 2c/contract until a real fill.
* MODEL CHANGE (Travis asked): the sim now includes every RB/WR/TE with offensive snaps in his team's last 2
  games (`GameModel.active_players`, `roster_for`; `--leaders-only` restores the old roster) and the
  projections file keeps every player the sim used. A/B 2025 wks 6-13 (116 games, 3,652 paired leader rows):
  leaders unchanged (every stat |change| < 0.1%, |t| < 1.1). The 320 depth players' upper tails are too thin
  (<p90 coverage 82-84%, should be 90%: in-game injuries to starters are not simulated), so every player added
  by the rule is an automatic blind spot (shown, never bet). Next model task: calibrate depth-player tails.
  Regression check after the change: No drift.
* Container setup fixed and written into CLAUDE.md step 2 (2019-21 play by play, 2024-25 PFF). After it:
  `regression_check.py` = No drift (n=508, every stat within 0.6% CRPS of baseline).
* Odds feed tested: main lines 94/94 two-sided from 4 books (Caesars not posting); `--alt` 1,052 quotes
  from 8 books. Kalshi ladders pulled by hand into quotes format (494 quotes). Credits left: 19,942
  (quota 20,000, not the 500 free plan BETFINDER_PROMPT.md assumes).

## JAX at BAL, week 9, Thursday 2026-11-05 8:15 PM ET
* Projections RE-RUN 2026-11-03 20:22 UTC at the current consensus (JAX −10, total 40.5; the first run
  used −8.5 / 43.5). Same adjustments as before; news file +3 items (Tuten not seen at Tuesday practice,
  Hill limited Monday with a groin injury, Loop/Moody); blind spot name fixed to Nate Boerkircher.
  Sim score JAX 25, BAL 16; JAX wins 79%.
* Captures in `markets/`: `_open.csv` (Robinhood, Yes only, 11/3 screenshots), `_books_open*.csv`
  (20:05 UTC), `_kalshi_open.csv` (20:25 UTC), priced `_priced_open_v2.csv` (all venues).
* Report HTML not republished and no Canva made this session. Re-running `report --board` would log
  paper picks again (JAX@BAL rows already logged): use `--no-log` or check `picks_log.csv` first.

### Bet finder result (v2: books main + alt, Kalshi, Robinhood)
* BOTH AGREE 0, market only 0. Model only 30 (all Kalshi Nos), model vs market 30 (all unders).
* Every model pick is an UNDER, and every one fails a conservative book check (1 − books' alt Over
  probability, which includes their cut): best is Tuten under 69.5 rush yds at −3.2 points. The model
  leans under on this whole game; treat it as model bias until H4 says otherwise. Paper only.
* Robinhood's stale Yes board is mostly at or below the market (median −2c vs Kalshi/books), except
  Justice Hill rushing rungs (+6 to +8c) and Josh Cameron (blind spot).

### Bet (Kalshi): none
* Projections re-run 20:37 UTC with the full roster (27 players); priced v3 (`_priced_open_v3.csv`):
  0 BOTH AGREE, 0 market only, 0 model picks on an Over. Every Kalshi No the model likes costs more than the
  books' floor (e.g. Hill 20+ No 66c + 2c fee vs books ≤ 62%). Pass unless prices move.
* The earlier conditional Robinhood bet is void (venue change).

### Graphics (`graphics/2026_wk09_JAX_at_BAL/`)
* `JAX_at_BAL_box_score.pptx/.pdf` (3 slides, all 27 simulated players) and
  `JAX_at_BAL_book_vs_kalshi_vs_model.pptx/.pdf` (18 slides: 42 main lines, 455 alternate rungs inside each
  player's simulated range). Built only from `box.csv`, `main_lines.csv`, `ladders.csv` by `build_data.py` and
  `build_pptx.py`. Kalshi asks of 95c+ shown as "-" (no real offer).
* NOT yet in Canva: upload to www.canva.com was denied by the environment's network policy (403). Once
  Travis allows www.canva.com: Canva create-upload-url, POST each .pptx, then read-design and check numbers.

## Open items, in order
1. Upload the two decks to Canva once www.canva.com is allowed (see Graphics).
2. Game day: re-pull books and Kalshi within 1 hour of kickoff (EDGE_PROMPT.md close capture), re-run price.
3. Known issues below.

### Known issues (not fixed; ask Travis before changing code)
1. `price` treats any `book` row on the Robinhood board as a bettable venue ("Sports Gambling Podcast").
2. Alt lines are Over only, so `price` gives no market number on ladder rungs. This session used
   1 − alt Over as a conservative floor by hand; worth building in, plus Kalshi as an execution venue
   (Kalshi prices must be in cents in the quotes CSV; Odds API gives American odds).
3. `update` does not fetch what the model needs on a fresh container (CLAUDE.md step 2 workaround).
4. BETFINDER_PROMPT.md lists Caesars and a 500-credit free plan; neither matches this account.

## After the game
1. Settle any model bets in `bets.csv` with closing prices; `python nfl.py picks grade`.
2. Grade EVERY rung and book/Kalshi quote (EDGE_PROMPT.md data capture step 4): first real test of
   H1/H2/H3 and the all-unders lean. One game: weak evidence, report it as such.
3. Write the review in `reviews/`.

## Waiting on Travis
* Allow www.canva.com in the environment's network settings so the two decks can be uploaded to Canva.
* How this branch's commits reach master (into PR #1, stacked PR, or a second PR).
* Approval of the proposed rule: real-money bets only on "BOTH AGREE" (model and books agree).
* Canva carousel DAHZ4XCn3BY (https://canva.link/9irp6wkayeavxk3): fixes were staged in an edit
  transaction in an earlier session; if that expired, redo the fixes and ask before committing.
* Offered, not yet approved: logging Travis's own hit-rate parlays (tagged), a break-even floor for
  hit-rate parlays, a defensive-injury matchup test, "coach-driven role cuts" as a playbook blind spot.
