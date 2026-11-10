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
