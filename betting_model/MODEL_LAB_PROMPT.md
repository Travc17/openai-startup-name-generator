# Model lab prompt: the most accurate prediction and sim model our data can support (Travis, 2026-11-05)

Say: "Run the model lab" (whole loop) or "Run the model lab on <feature family>" (one batch, e.g. "PFF blocking").
Goal: accuracy, proven with data. "Use all usable data" means every source gets TESTED; only winners get turned on.
History says why: of the 4 PFF features tested before 2026-11-05, 1 helped (routes), 2 did nothing, and 1 (slot vs
wide alignment) made receiving yards 0.7% WORSE (t=+3.98). Adding data without a test can make the model worse.

---

## Rules (non negotiable)
1. Freeze: never change the production model on a game day after the afternoon pass, or between a placed bet and its
   game. Lab work happens in a separate git worktree or behind `Config` switches that default OFF.
2. No leakage: every feature uses only games BEFORE the one projected; fitted constants come from earlier seasons
   than the ones scored. Say which seasons were fit and which were scored.
3. The bar to turn something ON: paired test vs current production, same games, same seeds, 2024-25 weeks 4+ AND
   2026 to date; the target stat improves with t <= -2; no other stat gets worse with t >= +2; P10/P50/P90 coverage
   stays within 3 points of 10/50/90; `regression_check.py` passes (stat rows + "No drift.") and its baseline is
   refreshed in the same commit.
4. One feature family per batch. Combinations only after the singles pass.
5. Every test, passed or failed, goes in README "Model review" with n, % change and t. Failed switches stay in
   `Config` (OFF) so the result can be reproduced.
6. Licensing: PFF data stays in `betting_model/data/` (gitignored), never committed, never posted or shared outside the model's outputs.
   Only model outputs (projections) leave the machine. Keys live in the environment, never in chat or the repo.
7. Goal is accuracy (Travis 2026-11-05: predictions are for himself and friends, no X). Two numbers per player:
   the MODEL median (independent of prop prices, used for every bet, so it can disagree with the market) and the
   BEST ESTIMATE (model blended with the closing line at the weight that tested most accurate on held-out games;
   approved 2026-11-05). The best estimate is never used to find bets: it already contains the price.
8. Credits and money: ask Travis before spending more than 1,000 Odds API credits in one batch.

## 1. Inventory: every tool and data source (update `MODEL_INVENTORY.md` each run)
For each source: what it has, seasons, freshness, cost, and status (USED / TESTED-OFF / UNTESTED).
Known on 2026-11-05:
* nflverse (free): play by play 2019-26 (USED), snap counts (USED), depth charts (USED), players and IDs incl.
  pff_id (USED). Not yet loaded: Next Gen Stats (separation, cushion, air yards, rushing yards over expected, time to
  throw, CPOE), participation (personnel, defenders in the box, coverage shell), FTN charting, injuries, schedules
  (rest days, roof, surface, temperature, wind, referee), officials, PFR advanced stats.
* PFF API (paid; confirmed reachable 2026-11-05): receiving/summary (USED: routes; YPRR and slot TESTED-OFF),
  receiving/scheme (man/zone TESTED-OFF), passing/summary, passing/pressure, passing/depth, rushing/summary,
  offense/blocking, offense/pass_blocking, offense/run_blocking, defense/summary, defense/pass_rush,
  defense/coverage (all UNTESTED).
* The Odds API (19,900 credits on 2026-11-05): live books + Kalshi (USED for prices). HISTORICAL odds endpoint works
  (confirmed 2026-11-05, 1 credit per event list). Historical props cost about 10 credits per market per game:
  one season of 5 prop markets is roughly 13,000 credits. This is the only way to measure the model against
  closing lines before 50 real bets.
* Our own records: `projections/`, `picks_log.csv`, `bets.csv`, `markets/` captures, SizzleSims scorecards, floor-leg
  CSVs, reviews. Small samples: use them to grade, not to fit.
* WebSearch for news (USED). Weather comes from play by play and schedules (wind TESTED-ON for QB pass yards).

## 2. Scoreboard first (before any new feature)
Score the current production model on 2024-25 weeks 4+ and 2026 to date: CRPS, median absolute error and P10/P50/
P90 coverage for targets, receptions, rec yds, carries, rush yds, QB attempts, completions, yards; team points vs
the closing spread and total. Beside it: the naive baseline (player's last 8 games) and, once historical props are
pulled, the MARKET: the closing line used as a median prediction, and its no-vig probabilities. Beating the market
is the bar that matters for betting; beating naive is the floor.

## 3. Error audit: find what the model does not know
Slice the residuals (actual minus median, and PIT) by: position and role tier, QB change, spread bucket (game
script), weather, home/away, rest days and short week, opponent defense quality, OL and defensive starters missing,
rookies, first game back from injury, blowouts (starters pulled), team pace. Rank slices by size x consistency
across seasons. The top slices choose the next features. This is the reverse engineering: the slices where the
market or the results know something the model does not.

## 4. Candidate features (test in this order unless the audit says otherwise)
| Family | Hypothesis | Lever in the sim |
|---|---|---|
| Pass protection vs pass rush (PFF pass_blocking x opponent pass_rush) | pressure cuts QB yards and completions | receivers' yds/catch multipliers via the QB layer |
| Run blocking vs run defense (PFF run_blocking x defense/summary run grades) | blocking moves yards per carry | RB yards per carry multiplier |
| RB rushing (PFF yards after contact, elusive rating; NGS rush yards over expected) | true efficiency beats raw YPC | RB yards per carry prior |
| Opponent coverage by position (PFF coverage grades) | coverage quality moves catch rate and yards | receiver yds/catch multipliers |
| Missing defenders weighted by PFF grade (snaps lost x grade) | tests defensive injuries properly | opponent defense factor |
| Missing OL weighted by PFF grade | same, for the offense | QB and RB multipliers |
| Receiver route grade, aDOT, separation (PFF, NGS) | earned role predicts future targets | target share prior |
| Pace and neutral pass rate (play by play) | volume | team plays and pass rate |
| Schedule spot (rest, short week, travel, roof, surface, temperature, rain) | small volume or efficiency effects | team volume or efficiency |
| Structural: starters leaving early (injury, blowout) | QB attempts run high (known bias) | sim structure |
| Structural: TD calibration (too few TDs at the low end) | known bias | TD model |
Each row: write the hypothesis and the expected sign BEFORE running it.

## 5. Test loop (per feature)
1. Pull the data (cache in `data/`, gitignored for PFF), build the feature with only prior games, add a `Config`
   switch (default OFF) and, if needed, a neutral multiplier field on `Player` (default 1.0, no behavior change).
2. Paired backtest (`nflmodel/backtest.run` with the switch OFF and ON, same seeds, same games): % change in CRPS per
   stat with a paired t, coverage, and the sign vs the hypothesis.
3. Pass the bar (rule 3): turn ON, refresh the regression baseline, update README. Fail: leave OFF, record it.
4. Tune at most one shrinkage constant per feature, chosen on 2024 and scored on 2025-26 (no tuning on the scored
   seasons).

## 6. Historical closing lines (ask Travis first: credit cost)
Pull closing prop lines for one season (receptions, rec yds, rush yds, rush att, pass yds: about 13,000 credits) or
a sample (e.g. 60 games, about 3,000 credits). Then:
* Accuracy: model median vs closing line as predictors of the result (MAE, CRPS of each).
* Disagreement test: when the model and the line differ by 10% or more, who was closer, and how often.
* Paper profit: apply the real bet rules (2% edge after fee, Kalshi-style pricing from no-vig) and report hit rate,
  ROI and how it varies by stat. This answers "does an edge exist" before 50 real bets do.
* Blend (the best estimate, approved): weight w on the closing line, fit on one season, scored on the next; report
  the error of model, market and blend side by side.

## 7. Report (Travis reads it on his phone)
First line: did accuracy improve, by how much, on which stats (or "no change"). Then the scoreboard before and
after, a table of every test (feature, n, % change, t, ON/OFF), what turned on, what is next, credits used.
Commit code and README (never PFF data), push, update HANDOFF.md and `MODEL_INVENTORY.md`.
