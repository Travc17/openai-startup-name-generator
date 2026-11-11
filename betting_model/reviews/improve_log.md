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
