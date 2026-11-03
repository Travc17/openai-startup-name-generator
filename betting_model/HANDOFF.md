# Handoff (2026-11-03, session 2, 20:35 UTC): open items for the next session

Working branch: `claude/robinhood-trading-mcp-qo26do` (see CLAUDE.md "Session start"). This session's
commits are on `claude/tender-faraday-offel8` (fast-forward of the working branch); Travis has not yet
chosen how they reach master (PR #1 is open from the working branch).
Read this, `CLAUDE.md`, `PROJECTION_PROMPT.md`, `BETFINDER_PROMPT.md`, and `EDGE_PROMPT.md` first.

## State
* Bankroll $2,257.22 (1 bet settled: +$257.22, closing-line value −1.7c). `python nfl.py log summary`.
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

### Recommended bet (conditional, not placed)
* Robinhood **No on Justice Hill 20+ rush yds**, only if No costs **58c or less** (books/Kalshi say Yes
  is 35.6-38%, so No ≥ 62%; minus 2c fee and 2% edge). Model No 82.7%.
* Stake: rules give quarter Kelly on the model edge = $320, capped at $225.72 (10% per game).
  Recommended $50 instead because the model's edge here is not trusted (see above). Travis decides.
* If Kalshi's No (66c at 20:25 UTC) is what Robinhood shows now, there is no bet.
* Check Robinhood's contract rule for a player who does not play (Hill: groin, limited Monday).

## Open items, in order
1. Travis: live Robinhood No prices for Hill 20+ rush yds (and the other Hill rungs).
2. Game day: re-pull books and Kalshi, Robinhood close board within 1 hour of kickoff (EDGE_PROMPT.md).
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
* Robinhood No prices for Hill; whether to stake $50 or the rule's $225.72.
* How this branch's commits reach master (into PR #1, stacked PR, or a second PR).
* Approval of the proposed rule: real-money bets only on "BOTH AGREE" (model and books agree).
* Canva carousel DAHZ4XCn3BY (https://canva.link/9irp6wkayeavxk3): fixes were staged in an edit
  transaction in an earlier session; if that expired, redo the fixes and ask before committing.
* Offered, not yet approved: logging Travis's own hit-rate parlays (tagged), a break-even floor for
  hit-rate parlays, a defensive-injury matchup test, "coach-driven role cuts" as a playbook blind spot.
