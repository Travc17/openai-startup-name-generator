# Handoff (2026-11-03, session 2, 20:35 UTC): open items for the next session

Working branch: `claude/tender-faraday-offel8` (all work through 2026-11-05; it is a fast-forward of
`claude/robinhood-trading-mcp-qo26do`, which is now behind). Travis has not yet chosen how it reaches master
(PR #1 is open from the older branch). Game day: run `betting_model/GAMEDAY_PROMPT.md`.
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
5. `nfl.py parlay` calls `simulate` without spread/total (no game script), without the QB starters, and with
   default sims, so its parlay odds do not match the projections. JAX@BAL parlays were priced by replaying
   the report's sim (`markets/2026_wk09_JAX_at_BAL_parlays_v3.csv`; replay matched saved projections
   exactly). Fix: make `cmd_parlay` take --fav/--spread/--total/--qb and seed 7 like `report`.
6. QB rushing (rush_yds for QBs) is not in the regression check or any backtest. Proposed (not approved):
   treat it like TD/INT, no bets until checked. Lawrence 15+ rush No was skipped for this reason.

### Bet recommendation in the new format (2026-11-03 ~21:00 UTC, not placed)
* Single: Kalshi NO Justice Hill 20+ rush yds at <= 66c, $155 (model 82.7%; books ~63.5%).
* Parlay: Kalshi NO Derrick Henry 75+ rush yds + NO Parker Washington 60+ rec yds. Sim hit 41.8%
  (legs 66.8% x 63.0%, correlation x0.99); leg asks multiply to 27c (cost 29% with fee); books ~21%;
  pay at most 37c. $65. Plan total $220 of the $225 cap. Real Kalshi combo quote still needed.

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

## SimCast (2026-11-03)
* Merged from `claude/brave-ptolemy-0vv9wd`. Fixed for the full roster: `typical.py` scores only players with
  a real role (rank of the chosen game 491 -> 49); leftover volume labeled "Other <TEAM> receivers".
* JAX@BAL (20:37 UTC projections) published to https://claude.ai/artifact/Bx8jZgufz7Amfk5FgysjRh (v2):
  final JAX 25, BAL 16, 138 plays; headless check: plays to final, no script errors. Per-game step is CLAUDE.md 5c.
* Renamed SizzleSims (Travis). Now the MEDIAN game (`export.py --mode median`, default): players at exact medians,
  QB = sum of receivers (JAX 14/24 157 vs Lawrence's own median 19/29 234; BAL 15/25 123 vs 18/28 164), no
  placeholder rows. Page opens at 90 seconds, Clean feed removed, both box scores side by side. Published v3.
* Fixed the QB vs receivers gap (Travis): QB line = his median (Lawrence 19/29 234, Fagnano 18/28 164); receivers at
  one common percentile (JAX ~59-63rd, BAL ~58-61st) so they add up exactly. Proof it is not a model bug: in each sim
  QB and receivers agree (median gap 5 yds, 0 cmp); median of the receivers' TOTAL is 227 vs QB 234 (BAL 167 vs 164);
  only the SUM of individual medians (157) falls short. Published v4.
* Predictions panel (each player's own median, 80% range, A/B/C grade) + scorecard for played games. CHI@SEA re-sim
  added (`projections/2026_wk08_CHI_at_SEA_resim.json`, meta.resim = true, made after the game with pre-game inputs):
  44 of 46 inside the 80% range (A 18/18, B 8/10, C 18/18); misses Swift 27 carries, Charbonnet 6. Score missed
  (pred SEA 25-22, actual CHI 34-17). One game: watch whether coverage stays above 80% (ranges too wide). Published v5.
* Proposed next (not built): X prediction card image per game, scorecard post after each game, season tracker,
  model-vs-book-line comparison (needs book captures for every game).
* Sent-as-file fix: phone/email/chat previews open HTML without running scripts, so the page was a blank shell
  (0 table rows). `build_page.py` now runs `simcast/snapshot.js` (Playwright) to bake the newest game's final into
  the file; with scripts off it shows the final, box scores, predictions and play by play plus an "open in Chrome or
  Safari" note; with scripts on it plays as before. Newest game opens first. Published v6.
* X: SizzleSims link is shared "anyone with the link" (Travis set it). Clip tool `simcast/clip.py` (+ `record_clip.js`):
  gameplay recorded at 1080x1920, end cards spliced as stills (recorder drops frames on static screens). JAX@BAL clip
  1:51.6 sent to Travis (not in git).
* Look (Travis): Kentucky blue page background (#0033a0), green field, team colors on the bug and end zones, black
  panels with white text, white buttons. Play-by-play list removed (one-line caption stays); the box score sits in
  its place and follows the team with the ball (both teams at the final). QB line removed from the score bug.
  Published v8; X clip re-recorded (1:50) and sent.
* X clip is now LANDSCAPE broadcast (`simcast/record_broadcast.js`, page `#broadcast` mode): team-color stadium glows,
  midfield SizzleSims logo, confetti on scores, live side box scores, 10 s full final box score, original soundtrack
  (`simcast/sound.py`; crowd +5-6 dB on TDs, +1-3 dB on FGs; -16.2 LUFS). JAX@BAL clip 1:48 sent. Canva hosts and
  licensed music were not usable (Canva download hosts blocked by the network policy; music rights). Page v9.
* Score sound changed to fireworks (Travis 2026-11-04: crowd roar too much); crowd cheer kept only at the final whistle.
* Look: blue with depth (white stadium-light haze -> Kentucky blue -> deep navy, faint diagonal light streaks) and neon edges (blue on bug/field/caption, team color on side panels); page cards get a soft neon edge. Page v10; clip re-recorded 1:49.

## Game day 2026-11-05: afternoon pass done (16:10 UTC); FINAL pass after inactives (~6:45 PM ET)
* Captures: `markets/*_books_midday.csv` (9 books, 123 two-sided lines), `*_kalshi_midday.csv` (new tool
  `kalshi_quotes.py`), `*_priced_midday.csv`. Projections re-run at JAX -10 / 39.5 (total down from 40.5).
  `/tmp`-only Tuten-out scenario: Rodriguez 11 car / 43 yds; Henry, Hill, Washington, Meyers, Strange unchanged.
* News: Tuten questionable, no practice all week (27/27 Coen-era such players sat); market prices him out (books
  pulled his line; Kalshi Rodriguez 30+ 60c -> 87c). Hill full practice, off report. Fagnano starts, Huntley IR.
  JAX: Walker (DE) questionable, A. Johnson cleared, Meyers no designation. BAL: Wiggins (CB) questionable, Hawkins
  (S) out, Roquan/Andrews cleared. Weather mild, wind ~7 mph (no --wind).
* Matchup (2026 to date): JAX run D #1 (58 RB rush yds/g allowed); BAL WR D #28 (178/g), BAL TE D #11.
* No leg passes the books' check (all -4 to -8). Model + matchup agree on Henry and Hill rushing unders.
* Afternoon recommendation (not placed): parlay NO Henry 80+ rush + NO Hill 20+ rush (sim hit 60.0%, lift 1.01,
  ~41c if priced as product, max 55c) replacing bet #2 (Washington leg dropped: BAL WR D #28, CB/S injuries);
  single NO Strange 40+ rec yds at <=55c (model 61.9%, cost 57%). Rule stakes $160 + $60 = $220; recommended $50
  each (model-only). JAX RB props held until inactives.
* FINAL pass: inactives (Tuten), Hill/Henry/Walker status, weather, re-pull books + Kalshi (close), re-run price,
  SizzleSims export/build/publish + clip, final recommendation, then log fills.
* PLACED (Travis, ~11:20 AM ET, on ROBINHOOD, not Kalshi): bet #2 parlay NO Henry 80+ / NO Hill 20+ rush, 113 contracts,
  fill 41.5c, cost $49.60 (~2.4c/contract fees), pays $113; bet #3 NO Strange 40+ rec yds, 90 contracts at 55c, cost
  $50.85 (1.5c/contract), pays $90. Logged in bets.csv with exact fills. $100.45 at risk; bankroll $2,257.22 until settled.
* Observed fees (first real prediction-market fills since bet #1): single 1.5c/contract at 55c, 2-leg combo ~2.4c/contract.
  CLAUDE.md still assumes 2c flat; proposed (needs Travis's OK): 1.5c singles, 2.5c combos. Venue question open: the
  rules say Kalshi, the fills are Robinhood (prices matched Kalshi's quotes today).
* Final pass: record closing prices for #2 and #3 (Kalshi quotes as the proxy for Robinhood's close), then grade after.

## Floor and ceiling legs (2026-11-05, Travis's idea; FLOOR_PROMPT.md + `floor_legs.py`)
* Midday run saved to `markets/2026_wk09_JAX_at_BAL_floor_legs_midday.csv` (24 candidates). Qualifying (model-only,
  books not checked): Meyers 20+ rec yds (7/7, blend .859 vs 77c), Meyers 25+ (6/7), Lawrence 175+ pass yds (7/7,
  barely: +.012). Rodriguez NO 60+ rush (7/7, 53c) is SKIPPED: Tuten questionable, so the sample is stale.
* Adding any of them LOWERS the parlay's return per dollar (base Henry80/Hill20: 60.0% / 43.4c cost = 1.38x;
  + Meyers 20+: 45.7% / 33.9c = 1.35x; + Lawrence 175+: 1.26x). Not added to bet #2 (already placed).
* After the game: grade every row of the floor CSV (did 7/7 rungs hit more often than sim and price?). One game is
  noise; keep logging until about 50 graded rungs before drawing a conclusion.

## Full sim, afternoon pass (2026-11-05 21:28 UTC, SIM_PROMPT.md)
* Data through week 8 (pbp, snaps, PFF routes w8); regression check printed stat rows and "No drift."
* Line: consensus JAX -9.5 (3 of 5 books; DK/BetMGM -10), total 39.5 (`markets/*_books_afternoon*`). Nothing moved
  10% or more vs the midday projections.
* Median game: JAX 25, BAL 16; JAX win 77.4%. Lawrence 19/29 234; Fagnano 18/28 164; Henry 16-60; Tuten 16-60.
* Tuten-out scenario (scratchpad only): Rodriguez 7-26 -> 11-43, Abdullah 2-5 -> 4-11; Lawrence rush yds median
  1.9 -> 10.3 (looks like a model quirk: vacated RB carries partly going to the QB; QB rushing is untested anyway).
* 80%-range check vs last 4 games: Strange is the outlier. Model median 3 rec / 31 yds; last 4 games 7/95, 7/68,
  5/44, 2/55 (all 40+). That is the main risk to bet #3 (NO Strange 40+).
* Noted, not modeled: Travon Walker (JAX DE) and Nate Wiggins (BAL CB) questionable, Hawkins (BAL S) out, Vega Ioane
  (BAL OL) returning, Moody (K) elevated, rain 17% at kickoff rising to 35-40% after 9 PM, wind 2-5 mph.
* SizzleSims republished (version 11). FINAL pass after inactives (~6:50 PM ET): rerun with real inactives, clip.
* Skill `/nfl-game AWAY HOME [sim|bets|floor|final|grade|full]` (`.claude/skills/nfl-game/SKILL.md`) chains SIM_PROMPT,
  GAMEDAY_PROMPT, FLOOR_PROMPT and the after-game grading. Loads in sessions started after this commit.

## Model lab (2026-11-05, MODEL_LAB_PROMPT.md)
* Batch 1 (PFF pass pro vs pass rush, run blocking vs run D, RB efficiency, coverage grades, missing defenders)
  running in a separate git worktree, every switch OFF. Production model FROZEN for tonight's final pass.
  Review its results after the game; turn on only what passes the bar, refresh the regression baseline.
* Confirmed 2026-11-05: PFF facets reachable (passing, pressure, depth, rushing, blocking, pass/run blocking,
  defense, pass rush, coverage). Odds API historical endpoint works (1 credit per event list).
* Waiting on Travis: OK to spend credits on historical closing props (one season of 5 markets ~13,000 of 19,900;
  a 60-game sample ~3,000), and whether X predictions may blend market lines (product B).
* Travis 2026-11-05: "forget X", accuracy for himself and friends. Video clips dropped (only on request); SizzleSims
  page stays. Market blend for a "best estimate" approved (MODEL_LAB_PROMPT rule 7); bets still use the model only.
* Historical props measured 2026-11-05: 10 credits per market per game (1 test call: 7 books, 178 rec-yds outcomes).
  Full 2025 season, 5 markets = about 13,700 credits (he has 19,899 on what looks like the $30/month 20K plan).
  Waiting on his go before pulling.

## Historical closing lines, 2025 (pulled 2026-11-05; `hist_props.py`, `hist_compare.py`)
* 271 games, 126,607 quotes, 8 books, 13,438 credits (6,461 left). Raw data in data/odds_hist (gitignored).
* Results: `reviews/hist_2025_model_vs_market.md`. Closing line more accurate than the model on every stat; model
  UNDERS with edge beat blind unders by ~3-7 pts ROI in both halves; model OVERS lost; pass yds unders lost.
* Proposed (needs Travis's OK, after confirming on 2026 wk1-8 and/or 2024): unders only; no pass yds unders; the
  "best estimate" = 80% market / 20% model probability. 2026 wk1-8 (~6,000 credits) is the clean out-of-sample test.
* 2026 wk1-8 pulled (121 games, ~6,000 credits; about 320 left: enough for tonight's close capture, then thin until
  the reset). Out-of-sample results confirm: market more accurate; 20/80 blend slightly better than market; model
  unders with edge >= 10% profitable both seasons; overs and pass-yds unders lose. See README and reviews/hist_2026*.
* PROPOSED rule change (needs Travis's OK, CLAUDE.md not edited): unders only; edge >= 10% vs Kalshi price + fee;
  no QB pass-yds unders; flat $50 stakes until the live record confirms (stated edges are inflated); predictions show
  the 20/80 best estimate beside the model median.

## New bet rules APPROVED by Travis (2026-11-05 ~5:10 PM ET), now in CLAUDE.md
* Alt rungs only (never book main lines); unders only; exception: low-rung overs BELOW the book's main line when
  matchup and season hit rate are strong (FLOOR_PROMPT checks), labeled "low-rung over (untested)"; edge >= 10%
  after fee; flat $50 stakes; no QB pass-yds unders; predictions show the 20/80 best estimate.
* `floor_legs.py --books <books CSV>` enforces "over below the book line" and "no QB pass-yds unders"; parlay max price
  now uses a 10% edge (`--min-edge`).
* DONE in code (2026-11-05 ~5:40 PM ET; regression check no drift): 10% min edge, 5% stakes under the 10% game cap
  (Travis chose 5% over flat $50), unders only + "low-rung over: floor check" + no QB pass-yds unders + no QB rushing
  in `market.find`/report (picks_log follows the same rules), game lines never staked, SizzleSims best estimate
  (`export.py --books`).
* OPEN: next credit cycle: pull historical ALT-line markets for 2026 (~4 markets x 121 games x 10 = ~4,800 credits): the
     rules above were tested on main lines only, and Travis bets alt lines.

## Model lab batch 1 result (merged 2026-11-05, every switch OFF; tonight's sims replay identically)
* PFF pass pro vs pass rush, run block vs run D, RB yards after contact, coverage grades, missing defenders x grade:
  NONE passed. Pass pro helped 2024-25 slightly but made receptions worse in 2026 (t=+2.36). README has the table.
* Lead for batch 2: better prior PFF coverage grades go with MORE yards allowed than the model expects, every season
  (2023-26). Likely the defense factor is under-shrunk: test heavier `opp_shrink_targets` / position-defense shrink.
* Method note: single-call paired tests can show chance t > 2 on stats a feature cannot touch (random draws
  reshuffle); use `lab/pff_batch1.py --split` for team-level levers. Earlier ad-hoc PFF tests may carry that noise.

## FINAL PASS done (2026-11-05 ~7:00 PM ET; projections 23:57 UTC; credits left 301)
* Official: Tuten and Travon Walker ACTIVE; JAX inactives C.J. Williams, Huzzie, Silmon-Craig, W. Williams (none
  projected). Ravens inactives not found before the reply; Henry, Hill, Andrews presumed active (no news otherwise).
* Close: JAX -9.5, total 40. Captures: `markets/*_books_close*`, `*_kalshi_close.csv`, `*_quotes_close.csv`,
  `*_priced_close.csv`, `*_floor_legs_close.csv`. No median moved 10%+ vs the afternoon. Median game JAX 25, BAL 16.
* CLOSING PRICES for settlement (`nfl.py log settle <id> <result> --close ...`): bet #2 legs NO Henry 80+ 61c, NO Hill
  20+ 66c (product 40.3c vs 41.5c fill; no combo quote); bet #3 NO Strange 40+ 58c (filled 55c: +3c).
* Recommended bet #4 (not placed unless Travis fills): Kalshi NO Parker Washington 60+ rec yds, price limit 51c (close
  47c), model 63.4%, edge +14.4%, stake $115 (5%; game total $215 of the $225 cap). Model-only: books' line 62.5.
* Fix made in the final pass: rush+rec yds props now inherit a player's receiving blind spot (market.find, report).

## RESULT JAX 33, BAL 10 (graded 2026-11-05 ~11:45 PM ET from ESPN screenshots; review in reviews/)
* Bet #2 LOST (Hill 9-85 incl. 65-yd TD; Henry 57 leg won): -$49.60. Bet #3 cashed out at 93c: +$32.43. Recommended #4
  (Washington NO 60+) not placed; would have lost (61 yds, one 50-yd TD). Bankroll $2,240.05. CLV avg 0.0 (1 of 3).
* Scorecard 44/54 inside 80% (81%); A 9/9, B 6/6, C 29/39. Model vs line vs best MAE 12.40 / 12.23 / 12.23. Floor legs 7/7.
* New: POSTGAME_PROMPT.md (classify misses, lessons ledger `reviews/lessons.csv`, 3-game rule before any model test),
  `nfl.py log settle <id> cashout --pnl X`.
* OPEN after nflverse posts the game: `nfl.py update`, re-export SizzleSims with actuals (scorecard), `picks grade`,
  confirm the screenshot actuals (zeros for players not in ESPN's tables).
* Scheduled: post-game review for JAX@BAL fires 2026-11-06 8:30 AM ET (trigger trig_014rNuvXn8hxsDuW4tNPGZ45); it
  reschedules itself +3h if nflverse has not posted the game yet.
* POST-GAME REVIEW DONE (2026-11-06 8:30 AM ET): actuals confirmed vs nflverse; SizzleSims scorecard published (40/50,
  80%); picks_log graded (3 Nov-3 BTJ overs, 0/3); RB2 carry spike reclassified as blowout garbage time (known gap);
  process fix: flag backup-RB rushing unders when |spread| >= 9.5. OPEN BUG: export replay mismatch after update
  (possible look-ahead in a week-N projection), see reviews/lessons.csv.
* Travis (2026-11-05, personal, not the model): hard stop if his own betting money falls below $10,000. Flag it whenever
  he sends personal bets; suggested daily cap about $3,000 (the distance to that floor).

## CIN at ATL, week 9 (Madrid, Sun 2026-11-08 9:30 AM ET) — afternoon pass done Fri 2026-11-06 ~3:30 PM ET
* Open line CIN -3, total 52.5 (`markets/2026_wk09_CIN_at_ATL_books_open*`). Outs: Brian Robinson Jr. (3rd game, no
  bump), Zachariah Branch (first game, 5% of targets vacated). Blind: Zaccheaus (next man up) + auto depth adds.
* Median game CIN 28, ATL 25 (CIN wins 60%). Burrow 27/38 298; Penix 18/29 217; Chase 7-83 (median), Higgins 5-78,
  London 5-68, Bijan 18-88. Flags: Higgins (157/148/155 in 3 of last 4) and Burrow (428, 462) recent games sit above
  the model's 80% ranges; Dotson recent yards too (87, 95). Avoid their unders unless the edge is large.
* Final pass scheduled Sun 8:10 AM ET (trigger trig_01DCJusgncNN8MhZm6czbLWN). kalshi_quotes.py now maps all teams.
* PRELIMINARY BETS (Fri 2026-11-06 ~11:15 PM ET; captures `markets/2026_wk09_CIN_at_ATL_*_prelim*`; line unchanged
  CIN -3 / 52.5; credits 269): single NO Drake London 6+ catches (Kalshi 47c, limit 48c, model 60.0%, books 46%);
  parlay NO Penix 33+ attempts + NO Penix 20+ completions (sim 57.1%, lift 1.32; max 44c, needs Travis's combo
  quote). Stakes $110 each ($220 of the $224 cap). Both bets are one thesis: ATL passing volume stays low.
  Skipped: Pitts unders (CIN allows the 2nd most to TEs, rank 31; his target share up 0.14 -> 0.19).
  Travis's own favorite (Brown 3+ / Chase 5+ / Higgins 4+ catches at ~32c): sim 46.2% (+11.8 pts at 32c) but the legs
  cost 76c x 84c x 81c = 51.7c on Kalshi, so 32c needs checking; not a model bet (Brown's matchup fails the floor rule).
  Recheck everything at the Sunday 8:10 AM final pass.
* FINAL PASS done (Sun 2026-11-08 8:30 AM ET): close CIN -3, total 52; no median moved 10%+; official skill-player
  inactives not indexed (Dugger only), books posted props for every key player. Captures `*_close*` (credits 247).
  FINAL BETS (not placed unless Travis fills): single NO Drake London 6+ catches (Kalshi 45c, limit 47c, model 59.9%,
  books 45.5%); parlay NO Penix 33+ attempts + NO Penix 20+ completions (sim 57.1%, legs 54c x 46c, max 44c; needs
  his combo quote). $110 each. Skipped: Pitts unders (CIN rank 31 vs TE, role up), Bijan 120+ rush+rec under (CIN rank
  22 vs RB, carry share up 0.67 -> 0.71), Higgins/Burrow/Dotson unders (recent games above range).

## DAL at IND, week 9 (Sun 2026-11-08 1:00 PM ET) — final pass ~11:20 AM ET (inactives not yet posted)
* Close DAL -4.5, total 51.5. Turpin out (3rd game, no bump). Pickens (hamstring) and Ferguson (ankle) questionable:
  books posted Pickens props, none for Ferguson. Blind: Malik Davis (IR return committee), Goodson, Giddens, James
  Mitchell + auto depth adds. Median DAL 28, IND 24 (DAL 64.5%).
* Scenarios: Ferguson out moves nothing 10%+; Pickens out raises Lamb 7+ catches 0.383 -> 0.497 and Flournoy 4+
  0.416 -> 0.498 (kills those under edges).
* BETS (only if Pickens is ACTIVE; recheck trigger 11:42 AM ET): single NO CeeDee Lamb 7+ catches (49c, limit 49c,
  model 61.7%, books 48.6%); parlay NO Lamb 90+ rec yds + NO Ryan Flournoy 4+ catches (sim 38.9%, legs 53c x 46c,
  max 26c). $110 each. Skipped: Daniel Jones 200+ pass yds low-rung over (+13 but only 4/8 season games at 200+).
* 11:45 AM ET RECHECK: Pickens INACTIVE (also Schoonmaker, Porter Jr., Overshown; IND: Mallory, Haulcy). Ferguson active.
  DAL bets CANCELLED (Lamb/Flournoy unders lose their edge without Pickens). Rerun with Pickens/Schoonmaker/Mallory out,
  Flournoy and Mingo blind (next man up). Fresh Kalshi quotes (`*_kalshi_inactives.csv`): no under clears 10%. Only a
  labeled low-rung over remains: Daniel Jones 125+ pass yds (78c, model 94.0%, 7 of 8 games, DAL rank 23 vs QBs).

## GB at NE, week 9 (Sun 2026-11-08 4:25 PM ET): no-price analysis (ANALYZE_PROMPT.md, new)
* Travis asked for sims + alt-line hit rates + matchups only: no Kalshi, no props, no edges, no bets. 10,000 sims
  after inactives (NE: A.J. Brown, TreVeyon Henderson out; GB: MarShawn Lloyd, Josh Whyle out), NE -3 / 44.5.
  Sim score GB 21, NE 25; GB wins 37%. Files: `news/`, `projections/`, `analysis/2026_wk09_GB_at_NE.md`.
* New tool `analyze_game.py` (ladders at 80/70/60/50%, matchups with role filter) and `analyze` mode in the
  nfl-game skill. Odds API: 2 credits (spread/total only), about 216 left.
* Best matchups: Golden and Watson receiving (NE allows 1.08x league to WRs), Jacobs receiving (1.10x).
  Toughest: Henry (0.80x), Douglas (0.87x), Maye passing (0.88x, rank 5).
* Not done: SizzleSims page for this game (only on request), no grading yet.
* UPDATE ~4:00 PM ET: Travis asked for the normal SizzleSims run. Projections rerun at 25,000 sims (overwrote the
  10k file before kickoff), Mack Hollins added (`--players`, blind spot: active off IR, missing from the model's
  roster; DK posts 2.5 rec / 34.5 yds). Book main lines pulled after the sims (`markets/..._books_close.csv`,
  10 credits, 206 left), consensus unchanged NE -3 / 44.5. Wind forecast not found (no `--wind`). SizzleSims
  exported with `--books` (Best estimate on 35 of 50 predictions), published (artifact version 20). Score GB 21,
  NE 24, GB 37%.
* Process gap to fix: the roster rule misses a WR returning from IR who the books expect to play (Hollins).
  SIM_PROMPT 2k says to check this; analyze runs should too. Candidate code fix: add active IR returns that
  books post props for. Not changed yet.

## Week 9 graded (2026-11-09 ~12:30 AM ET, GRADE_PROMPT.md + grade_week.py, new)
* All 4 week 9 games graded from saved files: A+B 89% inside the 80% range (90/101), winners 3 of 4. League panel
  (13 games) calibrated. Book beat the model on mean miss (15.6 vs 16.5); best estimate 15.7. Review:
  `reviews/2026_wk09_week_review.md`; numbers `reviews/2026_wk09_grade.md`; every row `reviews/grades_log.csv`.
* GB@NE in-game exits: Jacobs (finger, Q1), Stevenson (knee, Q3). Process miss: Hollins left out (news said
  active). Bug: Kaleb Johnson skipped by the depth rule (RB4 behind inactive Lloyd).
* Code (bugs only, regression_check No drift): `roster_check` (ROSTER CHECK lines in every report),
  depth rank among players not ruled out, replays use the game-day depth chart. Replay mismatch closed: NOT
  look-ahead (week 9 rows change nothing); data revisions. SizzleSims v21 has every scorecard.
* OPEN, in order: (1) regrade week 9 after nflverse snap counts post (`python grade_week.py --week 9 --league
  --simcast`, rebuild, publish); (2) MODEL_LAB test: early-exit simulation (ledger row 0); (3) historical alt-line pull.

## BUF at MIN, MNF week 9 (Mon 2026-11-09 8:15 PM ET): pass 1 of 3 done (~12:25 AM ET)
* SIM_PROMPT pass 1, 25,000 sims: BUF 24, MIN 21, BUF wins 60%. Consensus BUF -3, total 44 (5 books 05:17 UTC).
  `--qb "MIN=Carson Wentz"` (Murray out, hamstring); out: Murray, Claiborne, Jauan Jennings, Josh Palmer.
  Blind: Aaron Jones rushing, Jordan Mason (committee after Mason's IR return; Jones knee). Zero ROSTER CHECK lines.
* Sanity flag with stated reason: Allen median 17/26, 176 yds (season median 31 att, 253 yds) because MIN allows
  180 rec yds/game (league 233) and 27.4 targets (31.4). Book 234; best estimate 222.
* Books (open, read only after the sims): `markets/2026_wk09_BUF_at_MIN_books_open*.csv`, 10 credits, 196 left.
  SizzleSims v22 with best estimate. Regression check No drift.
* Scheduled: pass 2 at 12:30 PM ET (trig_01QLNEYzfJbDek41doMHy8Z5), pass 3 at 6:55 PM ET after inactives
  (trig_01KJzyFuZZSGMByH1js12wZv). Pending: practice-squad elevations (MIN WR, DeeJay Dallas), Murray "test the leg".
