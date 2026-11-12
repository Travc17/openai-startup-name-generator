# Improvement log (IMPROVE_PROMPT.md)

## 2026-11-10: first run (evidence only; test not started)
* Evidence: 5 graded games, A+B 88% inside (95% 81 to 93%): not a range problem. Live model on every 2026 game
  (weeks 1-9; 1,100 receiving, 272 QB, 366 rushing lines): calibrated (receiving 9-11 / 49-51 / 89-90; QB pass yds
  12 / 47 / 92; rushing 13 / 47-53 / 89). Direction vs book: model-under side right 63% (95% 52 to 73%, n=79).
  Model miss 15.4 vs book 14.9 vs best 15.0.
* Misses concentrate in in-game exits (25% miss rate, 12 rows) and blowouts (14%, 97 rows).
* Decision: no calibration or bias change (thresholds not met). Next test = ledger #1, "starters leaving early not
  simulated" (4 games, READY): simulate an early-exit chance per starter (rate from 2024-25 play-by-play injury
  notes: 0.16 skill players per team-game leave hurt; plus blowout pulls), volume to teammates. Hypothesis: backups'
  upper tails and starters' lower tails improve; rush_att and rec_yds CRPS down for depth players; leaders' medians
  barely move. Not started: waiting on Travis to run the loop.
* Watch: backup-QB discount (2 games, needs 1), depth-add TE (1, needs 2), scenario zone/QB split (1, needs 2).

## 2026-11-11: MODEL_LAB test "early exit" PRE-REGISTRATION (written before any scored run)
* Feature: each RB/WR/TE may leave the game hurt in a simulated game. Rate by position fit on 2019-2023 play by play
  only (nflmodel/early_exit.json: RB 2.9%, WR 4.2%, TE 2.7% per player-game; exit time = share of game played, median
  0.53). The exiting player keeps targets/carries for the share he played; later players in the allocation (mostly
  backups) absorb the rest. Switch `Config.early_exit` (default OFF; OFF is bit-identical). QB exits not modeled.
* Variants (fixed now): on = measured rates; on15 = rates x1.5 (injury notes miss some exits; blowout pulls).
* Scored: 2024 weeks 4-18, 2025 weeks 4-18, 2026 weeks 4-9; leaders AND depth players (production roster rule)
  who played; 2,000 sims, same seed per game for every variant (paired).
* Hypothesis and expected sign: CRPS falls (better) for rush_att, rush_yds, targets, rec, rec_yds; largest for depth
  players' upper tails (under-p90 coverage moves from about 83% toward 90%) and starters' lower tails (under-p10 moves
  toward 10%). Leaders' medians move less than 2%. Expected size: small (a 3% event).
* Bar (MODEL_LAB rule 3): a target stat improves with t <= -2 on the pooled seasons; no stat worse with t >= +2;
  coverage stays within 3 points of 10/50/90; regression_check passes and its baseline is refreshed if shipped.

## 2026-11-11: early-exit RESULT — FAILED (left OFF; code kept for reproduction)
* 536 games, paired. Measured rates: no stat better at t <= -2; rec_yds +0.08% (t=+2.0) and pass_cmp +0.11% (t=+2.0)
  worse. Rates x1.5: depth players' targets and receptions better (-0.14%, t=-2.4) but leaders worse (targets +0.24%,
  t=+3.4; receptions +0.23%, t=+3.5; rec_yds +0.19%, t=+2.9). Fails "no other stat worse with t >= +2".
* Why: a 3 to 4% event spreads every player's distribution a little; leaders pay more than backups gain. Depth upper
  tails stay thin (targets p90 coverage 84.9% OFF, 85.4% ON; carries 82.7% -> 83.5%): exits are not the main cause.
* New lead from the same backtest (n=5,753 depth target rows, 1,416 depth carry rows): depth players' p90 coverage
  83-85% vs 90%. Hypothesis for the next test: share uncertainty for small-share players is too tight (one beta
  concentration for everyone). Ledger row added; it is backtest-sized evidence, so it is READY.
* Graded-game sanity check not needed (no ship). Regression baseline unchanged.

## 2026-11-11 (evening): MODEL_LAB test "share uncertainty for small roles" PRE-REGISTRATION (before any run)
* Travis asked to run it now (overrides the one-test-per-week pace; the bar is unchanged).
* Feature: the per-game share draw (beta) uses concentration x min(1, share / s0) for targets and carries, floor 2:
  players with shares below s0 get wider role uncertainty; players above s0 are unchanged. Switch
  `Config.share_conc_ref = s0` (None = OFF, bit-identical).
* Grid (fixed now): s0 in {0.10, 0.20, 0.30}. Selection rule (fixed now): choose on 2024 weeks 4-18 ONLY, the s0 with
  the lowest mean of the % CRPS changes over targets, rec, rec_yds, rush_att, rush_yds (all tiers pooled). The chosen
  s0 is judged on 2025 weeks 4-18 + 2026 weeks 4-9 (never used to choose). Other grid values are reported, not used.
* Hypothesis and sign: depth players' CRPS falls and their under-p90 coverage rises from about 83-85% toward 90% (all
  five stats); leaders change little for s0 = 0.10 and widen (risk of getting worse) as s0 grows.
* Bar: a target stat better at t <= -2 on 2025-26; no stat worse at t >= +2; coverage within 3 points of 10/50/90;
  regression_check passes, baseline refreshed in the same commit if shipped.
* Known caveat: scoring uses players who played (inactive or zero-snap backups drop out), which pushes actuals up for
  depth players; the same caveat applies OFF and ON, so the paired comparison is fair, but some of the gap may be this.

## 2026-11-11 (evening): share-uncertainty variant ABANDONED before any scored run
* Smoke test (2026 week 9, 300 sims) showed the design pushes the wrong way: lowering the beta concentration for
  small shares piles probability near zero (median drops, p90 does not rise). Depth targets under-p50 42% -> 38/33%.
  This is a property of the beta at small means, not noise. No scored run made; nothing chosen.
* Diagnosis before redesign: is the depth gap (median too low, p90 85%) real or a scoring artifact? The harness drops
  backups who were active but played 0 snaps (no snap row), which pushes depth actuals up. Rescoring OFF with
  nflverse weekly roster status (ACT with no snaps = 0): runs started 2026-11-11 ~7:40 PM ET.
