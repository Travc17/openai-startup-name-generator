# Tight ranges prompt: prediction, tight windows, confidence, and every context factor (Travis, 2026-11-15)

Say: "Run the ranges for AWAY at HOME" (or `/nfl-game AWAY HOME ranges`). Uses the latest pass for the game; run a
pass first (SIM_PROMPT.md) if the last one is older than the latest injury report or inactives.

What it answers, for every skill player with a real role (grades A and B; depth and blind-spot players skipped):
* WHERE HE LANDS: the prediction of record (best estimate = 20% model + 80% book main line; model median where no line).
* TIGHT WINDOWS: 50% and 70% central windows from the same 25,000 sims as the record.
* CONFIDENCE: how often that kind of window actually held in the backtest (`nflmodel/window_calibration.json`,
  43,489 production-model predictions, 2024-26, real inactives). A tighter window always means lower confidence:
  no window can be both tight and 85-90% sure for one game.
* RATING and RANK: High (held at or above the stated rate), Medium (2-3 points short; rushing misses run low),
  Low (lighter roles; misses run high). Ranked by confidence, then by tightness relative to the prediction.
* CONTEXT LANDING (Travis: "don't pull them out"): the record moved by every context factor, each shown with its weight:
  matchup (yards allowed to his position vs league, half weight), role trend (last 4 games' share vs season, half weight),
  history vs this opponent (shrunk n / (n + 6) games), home/away split (shrunk n / (n + 8) games). Plus snaps last 4,
  target and carry share, route trend (PFF, numbers console only), scheme (PFF pressure, coverage, run blocking: needs
  the defensive facets in data/pff; say "not loaded" if missing), weather and home/away.

## Rules
* The context landing is a SCENARIO, never the prediction of record. Each factor tested on its own as noise or is already
  in the sims (README "Model review": defense vs position 6 versions, man/zone coverage, home field through the spread).
  It is graded every week beside the record (after the game: actuals from `grade_week.py` vs `analysis/<game>_ranges.csv`:
  record miss vs context miss, and whether "lean up/down" was right). Three consistent weeks of the context landing
  beating the record = a MODEL_LAB test (IMPROVE_PROMPT.md). Until then the record stands.
* Wind and rain are tested and already inside the sims when the pass used `--wind` / `--rain`.
* PFF data is licensed: route and grade NUMBERS go to the chat reply only; the saved files carry qualitative labels.
* Windows and confidence are about where a player lands, not bets. A bet needs one rung's hit rate vs its price
  (BESTBETS_PROMPT.md).

## Run
```
cd betting_model
python ranges.py projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json --out analysis/<season>_wk<NN>_<AWAY>_at_<HOME>_ranges.md
```
It replays the saved sims exactly (stops on any mismatch) and writes the .md (ranked table + context) and a .csv
(graded after the game).

## Reply (phone)
First line: record score, winner and total, and the pass it comes from. Then:
1. The ranked table: player, stat, prediction, 50% window (confidence), 70% window (confidence), rating, context
   landing, lean.
2. MATCHUPS (Travis 2026-11-15: "I want more matchup context in your replies"): for each defense, what it allows
   to WRs, TEs, RB receiving, RB rushing and QB passing: yards per game and rank (1 = fewest), per target / carry
   vs league, last 4 games vs season (softer or tighter lately), TOUGH / SOFT; key defensive and line absences.
   Then the trends to know: which matchups line up with a rising or falling role.
3. The three biggest context leans (up or down) with the factors behind them, each labeled untested.
4. Status-sensitive players (questionable) and what moves if they sit.
Tags [Certain] / [Likely] / [Guessing]. Never write " - ".

## Save
Commit `analysis/<game>_ranges.{md,csv}`, `ranges.py` changes and HANDOFF.md; push.
