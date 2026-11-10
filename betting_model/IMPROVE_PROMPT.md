# Improvement loop prompt: turn the grades into a better model without fitting noise (Travis, 2026-11-10)

Say: "Run the improvement loop" (weekly, after "Grade the week") or `/nfl-game improve`.

The rule: GRADES CHOOSE, BACKTESTS DECIDE. A week of graded predictions is about 130 rows: enough to point at a
question, far too few to tune anything (week 9's "ranges too wide" was 88% with a 95% interval of 81 to 93%, while
1,700 lines on every 2026 game said calibrated). A change ships only when the MODEL_LAB_PROMPT.md bar passes on
2024-25 weeks 4+ AND 2026 to date. One change per week. Never on a game day after the afternoon pass, never between a
placed bet and its game.

---

## 1. Evidence (read it all before deciding anything)
* CLAUDE.md "Session start", `python nfl.py update`, `python regression_check.py` (stat rows AND "No drift.").
* The week is graded (GRADE_PROMPT.md, `reviews/grades_log.csv` current, snap counts posted).
* `python improve_report.py --league` -> `reviews/improve_report.md`:
  a. Graded coverage by grade with 95% intervals; b. by-stat bias (mean PIT and its t) and model vs book vs best;
  c. direction vs the book (the betting edge, with intervals); d. where the misses come from (slices);
  e. the live model on EVERY 2026 game to date (the big sample); f. the ledger triage queue.

## 2. Classify each signal, then act only where the threshold is met
| Signal | Threshold | Action |
|---|---|---|
| Bug (wrong player, broken join, roster rule, replay) | any | Fix now; `regression_check.py` must stay "No drift."; ledger row "fixed" |
| Process miss (we had the signal, did not use it) | any | Add an automatic check to the report (like ROSTER CHECK, INACTIVE CHECK) plus a prompt line; prove it fires on the game that exposed it |
| Ledger pattern | 3+ games, or 2 plus closing-line support | ONE MODEL_LAB test (section 3) |
| Range width | graded 95% interval wholly outside 70-90% over 5+ games AND league panel coverage 5+ points off with n >= 300 | recalibration test (per-stat calibration maps, walk-forward) |
| Median bias by stat | league panel under-p50 outside 45-55% with n >= 300 AND graded mean PIT t beyond +-2 | bias test for that stat |
| Model vs book vs best | best estimate worse than the book line over 2+ weeks, n >= 200 | retest the 20/80 weight on closing-line history; Travis approves any change |
| Betting edge (under-side hit rate, CLV) | report every week | betting rules change only with 2+ seasons of closing lines AND Travis's approval, never from this prompt |
Below a threshold: write the count still needed in the reply and do nothing else.

## 3. Run ONE test per week (MODEL_LAB_PROMPT.md section 5 is the procedure)
1. Pick: any open bug first; then a range or bias flag if one fired; then the top READY row of the ledger queue.
2. Write BEFORE running: hypothesis, expected sign, target stats, the slice that should improve most, the bar.
3. Build behind a `Config` switch (default OFF), in a worktree; paired backtest, same games and seeds, 2024-25
   weeks 4+ and 2026 to date; report n, % change in CRPS, paired t, P10/P50/P90 coverage per stat.
4. Sanity only, not evidence: rescore the graded games that raised the question with the switch ON. If the switch
   passes the bar but makes those games worse, say so and look for a bug before shipping.
5. Pass: turn ON, refresh `regression_baseline.json` in the same commit, README "Model review", ledger "fixed
   (shipped)". Fail: leave OFF, ledger "tested, failed" with n, % and t. Either way the result is kept.

## 4. Build evidence cheaply between tests
* Run every untested idea as a SCENARIO beside the prediction of record, never inside it
  (`lab/scenario_<game>.py` pattern: same sims, extra levers, saved to `analysis/`). Grade it with the week
  (`reviews/<game>_scenario_test.csv`); each game adds a ledger count. 3 consistent games = a MODEL_LAB test.
* Ideas worth a scenario: QB-specific target splits, zone fit vs coverage, backup-QB discount, game-script
  extremes, anything Travis asks "what if" about.

## 5. Process audit (every week)
* For every bug or process-miss row from the last 2 weeks: is its check in the code, and did it run this week?
* Any new kind of miss in this week's grade: add a check or a prompt line now, not next week.
* Prompts still match the code: flags, file names, credits left, the working branch.

## 6. Record and reply
* Append to `reviews/improve_log.md`: date; evidence in three lines; the decision and why; the test (hypothesis,
  n, % change, t, coverage, shipped or not); what is next with counts. Update HANDOFF.md; commit; push.
* Reply for a phone: the uncomfortable result first; what got better (numbers), what was tested and rejected, the
  queue with counts still needed. [Certain] / [Likely] / [Guessing]. Never write " - ".

## Guardrails
* Never tune on graded games; never fit a constant on the seasons it is scored on; one feature family per batch.
* Over 1,000 Odds API credits in one batch: ask Travis first. PFF data stays in `data/`, never committed or shared.
* If the evidence says the model is fine, the right output is "no change this week" plus the counts needed.
