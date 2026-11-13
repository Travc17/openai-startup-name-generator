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

## 2026-11-11 (night): diagnosis result + MODEL_LAB test "role swings for small roles" PRE-REGISTRATION
* Diagnosis (OFF model, 2024-26, 536 games): counting active zero-snap backups as 0 (nflverse weekly roster status)
  moves depth coverage closer but not all the way: depth targets under-p10/p50/p90 8.8/44.3/84.9 -> 9.5/46.4/86.0;
  rec_yds 9.1/46.4/86.4 -> 9.8/47.7/87.2; carries 11.0/47.5/82.7 -> 13.7/52.1/84.9; rush_yds 9.8/49.4/85.5 ->
  11.3/54.2/87.4. Leaders unchanged (about 9/48/89-90). So: about a third of the gap was scoring; the rest is real
  under-dispersion for small roles (receivers: thin high side; backup RB carries: thin on both sides).
* Scoring from now on counts active zero-snap players as 0 (`--zero-snaps`).
* Feature: multiplicative role swing for small roles, mean-preserving: share x exp(sigma z - sigma^2/2) for players
  with expected target share < 0.10 (targets) or carry share < 0.30 (carries); leaders' larger shares untouched.
  Switch `Config.role_noise_sigma` (None = OFF, bit-identical; separate random stream).
* Grid (fixed now): sigma in {0.25, 0.40, 0.55}. Selection rule (fixed now): on 2024 weeks 4-18 ONLY, the sigma with
  the lowest mean % CRPS change over targets, rec, rec_yds, rush_att, rush_yds (all tiers pooled). Judged on 2025 weeks
  4-18 + 2026 weeks 4-9 only.
* Hypothesis and sign: depth tier CRPS down and depth under-p90 up toward 90 (receivers), depth carries p10/p90 toward
  10/90; leaders within +-0.1% (not touched except through teammates' volume).
* Bar: as before (target stat t <= -2 on 2025-26, no stat worse t >= +2, coverage within 3 points, regression passes).

## 2026-11-11 (night): role-swing RESULT — FAILED (left OFF)
* Selection on 2024 (pre-registered rule): sigma 0.25 (mean -0.02%; 0.40 -0.01%; 0.55 +0.20%).
* Judged on 2025-26: no stat better at t <= -2 (best: depth carries -0.27%, t=-1.8); nothing worse at t >= +2
  (pass_cmp +0.13%, t=+1.8). Depth targets p90 85.6 -> 86.0. Fails the bar. Larger sigma hurt targets (t=+2.6, +4.3).
* Diagnosis: backup carries p90 79.0% when a starter sat out vs 85.5% when all played. The lab bench has no
  next-man-up for missing starters (live reports do), so it overstates the backup-RB problem. Receivers' p90 ~86%
  either way: real, unexplained so far.
* What changed in production: nothing (all three switches OFF; regression No drift).
* Next: fix the test bench first (mirror production rosters with known outs), re-measure, then a new hypothesis for
  backup receivers. Ledger rows updated.

## 2026-11-11 (late): lab bench v2 + re-measure PRE-REGISTRATION
* Bench v2 (`lab/bench_v2.py`): rosters from the live `nfl.roster_for` (usage leaders, depth-chart adds, recent-snap
  players, next-man-up for outs, return multipliers, route-role) with each game's real inactive list (nflverse weekly
  roster status != ACT, known before kickoff); scores every rostered RB/WR/TE who was ACTIVE (0 if no snaps) and the
  starting QBs. Bug found while building it and fixed: in a replay, the depth-chart backstop could add a rookie whose
  only history is the replayed game (crash); now requires history before the game. Live behavior unchanged.
* Re-measure (descriptive): OFF calibration by tier, 2024 wks 4-18, 2025 wks 4-18, 2026 wks 4-9.
* Confirmatory re-judgement, no re-selection: n25 (role_noise_sigma 0.25, chosen on 2024 earlier) and ee (early exit,
  measured rates) on 2025-26 under bench v2, same bar as before.

## 2026-11-12 (early): bench v2 RESULT + combination PRE-REGISTRATION
* Re-measure: on live rosters the OFF model's depth tier stays under-dispersed (targets p10/p50/p90 8.8/44.6/84.5;
  carries 14.0/53.9/85.2); leaders and QBs about calibrated.
* Confirmatory re-judgement on 2025-26 (bench v2): BOTH PASS the bar.
  ee (early exit, measured rates): targets -0.15% (t=-2.6), rec -0.20% (t=-3.3), rec_yds -0.16% (t=-2.7), rush_att
  -0.22% (t=-2.3); nothing worse at t >= +2. n25 (role swing 0.25): rush_att -0.37% (t=-4.4), rush_yds -0.28%
  (t=-3.3); nothing worse at t >= +2. Bench v1 had failed both: v1 graded backups against rosters live reports never use.
* Combination (MODEL_LAB rule 4, after singles pass): "both" = ee + n25, fixed settings, bench v2, judged on 2025-26
  (2024 reported). Ship rule (fixed now): ship "both" if it passes the bar AND is not worse than the better single on
  any stat at t >= +2 (paired vs that single); otherwise ship the singles that pass, ee first.

## 2026-11-12: combination RESULT and SHIP
* "both" (ee + n25) vs off 2025-26 passes (rush_att -0.42% t=-3.9, rush_yds -0.24% t=-2.3, rec_yds -0.12% t=-2.1) but
  vs ee it is worse on receptions (+0.13%, t=+2.4): fails the pre-registered combination rule. SHIPPED: early exit
  alone (Config.early_exit = True). Regression baseline refreshed in the same commit (changes under 1%, no drift flags).
* Next (pre-registered below): ee + role swing on CARRIES ONLY (swings never helped receiving).

## 2026-11-12: "ee + carry-only role swing" PRE-REGISTRATION (before any run)
* Variant ee_c25: early_exit ON (production now) + role_noise_sigma 0.25 applied to carries only (role_noise_t = 0, so
  targets untouched). Settings fixed (sigma chosen on 2024 earlier). Bench v2. Baseline for the test = production (ee).
* Judged on 2025-26 vs ee: ship if rush_att or rush_yds better at t <= -2 and no stat worse at t >= +2 (vs ee).

## 2026-11-12: "ee + carry-only role swing" RESULT — FAILED (stays OFF)
* vs ee (production), 2025-26: rush_att -0.26% (t=-2.9), rush_yds -0.33% (t=-4.0), receiving within +-0.05%, but
  pass_cmp +0.20% (t=+2.7). Pooled 2024-26 same picture (pass_cmp +0.15%, t=+2.6). Fails "no stat worse at t >= +2".
* Likely test artifact: role-swing draws and early-exit draws share one random stream, so turning swings on reshuffles
  which receivers exit; QB completions lose their pairing. Not shipping on a "likely". Next test: separate stream,
  same settings, same rule.
* Production after tonight: early exit ON (shipped), every other lab switch OFF. Regression baseline = early exit ON.

## 2026-11-12 (evening): clean re-test PRE-REGISTRATION — carry-only role swing on its own random stream
* Change to the switch only: role-swing draws use their own stream (`sw_rng`), so turning swings on no longer
  reshuffles early-exit draws. Swings OFF = bit-identical (regression No drift before the run).
* Variant ee_c25 (early exit ON + role_noise_sigma 0.25 on carries only, role_noise_t 0), bench v2, run in the SAME
  job as its baseline "ee" (production) so both use identical data. Settings fixed (sigma chosen on 2024 earlier).
* Judged on 2025 weeks 4-18 + 2026 weeks 4-9 vs ee: ship if rush_att or rush_yds better at t <= -2 AND no stat worse
  at t >= +2; 2024 and pooled 2024-26 reported. If it ships: Config role_noise_sigma = 0.25, role_noise_t = 0.0,
  regression baseline refreshed in the same commit.

## 2026-11-12 (evening): clean re-test RESULT — PASSED, SHIPPED
* ee_c25 vs ee (production), bench v2, same job: 2025-26 rush_att -0.23% (t=-2.9), rush_yds -0.20% (t=-2.6); receiving
  +0.02 to +0.07% (t <= +1.3); pass_cmp +0.07% (t=+1.1). Passes the pre-registered rule. 2024: rush_att -0.21% (t=-2.0).
  Pooled 2024-26: rush_att -0.22% (t=-3.5), rush_yds -0.13% (t=-2.1), pass_cmp +0.11% (t=+1.96, under the line; watch).
* SHIPPED: Config.role_noise_sigma = 0.25, role_noise_t = 0.0 (carries only). Regression baseline refreshed (all moves
  <= 0.2%, no drift flags).
* Production now: early exit ON + carry-only role swing ON. Backup RB carries 2025-26 depth p90 85.6 -> 86.3,
  median 54.0 -> 52.9 (closer to 50). Open: backup receivers' high side (~86%); QB completions on the weekly watch.

## 2026-11-12 (night): MODEL_LAB test "team pass volume follows the starting QB" PRE-REGISTRATION (before any run)
* Trigger: WAS@NYG pass 1, McCarthy median 34 att / 256 yds vs book 30 / 210.5; NYG targets with McCarthy 27, 27 vs a
  team window average of 32.0 (Winston games 52, 43). Scenario (not the record): full McCarthy volume gives 29 / 215.
* Feature: offense target mean = (n x mean targets in this QB's starts for the team + k x team weighted mean) / (n + k)
  over the team window; n = his starts there; n = 0 -> unchanged. Switch `Config.qb_volume_k` (None = OFF,
  bit-identical; regression No drift before the run). Starting QB = the game's real starter (known before kickoff).
* Grid (fixed now): k in {2, 4, 8}, all on top of production (early exit + carry swings). Selection rule (fixed now): on
  2024 weeks 4-18 ONLY, the k with the lowest mean % CRPS change over pass_att, pass_cmp, pass_yds, targets, rec,
  rec_yds. Judged on 2025 weeks 4-18 + 2026 weeks 4-9 vs production, bench v2.
* Hypothesis and sign: pass_att and pass_cmp CRPS down (largest in games after a QB change), receivers' targets down
  slightly; rushing unchanged. Bar: a target stat better at t <= -2 on 2025-26, no stat worse at t >= +2, coverage
  within 3 points, regression passes. If it passes before 12:30 PM ET it applies to WAS@NYG pass 2.

## 2026-11-12 (night): QB-specific volume RESULT — FAILED (stays OFF)
* Selection 2024: k=2 mean +0.56%, k=4 +0.26%, k=8 +0.04% (QB attempts worse at every k: +1.41 / +0.81 / +0.36%). k=8.
* Judged 2025-26 vs production: targets -0.14% (t=-1.98), rec -0.12% (t=-1.75), rec_yds -0.10% (t=-1.5), QB stats
  |t| < 1, nothing worse. Misses the bar. Even shipped, k=8 moves NYG volume only 3% (factor 0.969).
* Lesson: a new starter's first 2-3 games say little about team pass volume in general. For WAS@NYG the official
  stays at 34 att; the scenario (29 att) and the best estimate (about 31) are shown beside it, not instead of it.

## 2026-11-12 (5:30 PM ET): PRE-REGISTRATION: QB CAREER pass volume (Config.qb_volume_mode = "career")
* Why: Travis asked to correct the McCarthy gap. New evidence the team-only test could not see: McCarthy 10 MIN 2025
  starts 29.3 att vs Wentz 39.6 on the same team; NYG 2026 McCarthy 32 (2) vs Winston 40.6 (5). The failed test used only
  starts for the CURRENT team (n=2).
* Hypothesis: a team's target volume follows the starting QB's career volume ratio. For each start of QB q in the current
  and previous season (any team, games before the predicted game), ratio = team targets that game / that team-season's
  mean targets over games before the predicted game; r = mean ratio; factor = (n r + k) / (n + k), k = 8 FIXED in
  advance (no grid, no fitting), applied to the team target mean (QB lines are summed from targets).
* Expected sign: CRPS down for pass_att, pass_cmp, pass_yds, targets, rec, rec_yds; biggest in QB-change games.
* Data: bench v2, 2024 and 2025 weeks 4-18, 2026 weeks 4-9, 2,000 sims, paired seeds, variant vs production.
* Bar (MODEL_LAB): pooled 2024-26 at least one target stat improves at t <= -2; no stat worse at t >= +2 pooled or in any
  single season; coverage within 3 points. k is not fit, so all three seasons are scored. Pass = ON before the final pass;
  fail = OFF and the 20/80 best estimate stays the only tested correction.
* RESULT (5:15 PM ET): FAILED, stays OFF. Bench v2, 536 games, paired vs production:
  pooled targets -0.07% (t=-1.18), rec -0.07% (t=-1.23), rec_yds -0.06% (t=-1.15), pass_att -0.02% (t=-0.07),
  pass_yds +0.10% (t=+0.38). Only 2024 rec reached t=-2.06 (one season; the bar is pooled). Nothing worse at t>=+2.
  QB-change slice (267 team-games): right direction, not significant: pass_att -0.88% (t=-0.92), targets -0.30% (t=-1.74),
  rec_yds -0.26% (t=-1.76). McCarthy factor would have been 0.946 (33 -> ~31 att).
* REAL BIAS FOUND (not a fix): in QB-change games production's pass_att median is too high: 58.4% of results land below
  it (n=267, z=2.8); 56.6% with the career switch. Next test (pre-register on 2024-25, judge on 2026 + new weeks): a
  QB-change attempts shift. Not tonight: fitting it on these games and scoring them is the mistake the bar exists for.

## 2026-11-12 (5:45 PM ET): PRE-REGISTRATION: game score blend (model's own projection + consensus)
* Why: Travis: "project score, winner and total better; I don't just want a consensus."
* Method: nflmodel/scores.py walk-forward (ratings + coefficients fit only on prior seasons; 2019-21 warmup).
  blend margin = w x model margin + (1 - w) x closing spread; blend total = v x model total + (1 - v) x closing total.
  w, v chosen on 2022-24 (grid 0 to 1 by 0.05, minimize squared error), then judged ONCE on 2025-26.
* Bar: on 2025-26 the blend beats the closing line on squared error with paired t <= -2 (margin or total), and is not
  worse on the other. Pass: the blend becomes the score, winner and total of record (Travis approves before it ships).
  Fail: consensus stays; record the numbers.
* RESULT (5:50 PM ET): FAILED. Selection 2022-24 (815 games) chose margin weight 0.00 and total weight 0.05: the model
  adds nothing to the closing line. Test 2025-26 (408 games): margin RMSE line 12.19 = blend 12.19, model alone 12.85;
  total RMSE line 13.21, blend 13.22 (t=+0.72), model 13.65; winner right: line 66.5%, model 63.5%. Consensus stays the
  score, winner and total of record. Next idea only if new information exists that the line lacks at kickoff.

## 2026-11-12 (night): PRE-REGISTRATION: rain (Travis: "We need to add rain to model")
* Data: nflverse play by play `weather` text at kickoff, outdoor/open-roof regular-season games; rain = rain, shower,
  drizzle, storm or thunder in the text (snow kept out). 2019-23: 74 rain games (fit); 2024-26: 26 rain games (test).
* Fit (2019-23 only): per team-game, pass attempts, rushes and yards per attempt divided by that team's season mean in
  its other outdoor games; rain effect = mean rain-game ratio / mean dry-game ratio - 1, net of the tested wind effect
  for games above 8 mph. Same three levers and code path as wind (`weather.json`): att_r, rush_r, ypa_r. Applied when
  the report gets `--rain` (forecast rain at kickoff).
* Test: bench v2 (real inactives), the 26 rain games of 2024-26, production vs production + rain, paired seeds.
* Expected sign: fewer pass attempts and yards, more rushes. Targets: pass_yds, pass_att, rec_yds.
* Bar: a target stat improves at t <= -2 in the rain games; no stat worse at t >= +2. Pass = ON (`--rain`), fail = OFF.
  Small sample warning: 26 games, about 52 QB rows; a real but small effect may not reach the bar.
* FIT (2019-23, 144 rain team-games): pass attempts -5.2% (se 2.1), rushes +5.9% (se 2.5), yards per pass -9.9% (se 2.0).
* RESULT (25 held-out rain games 2024-26, prod+wind vs +rain, paired): pass_yds -2.62% (t=-0.55; under-median 64% -> 50%),
  pass_att +1.68% (t=+0.61), rec_yds -1.29% (t=-1.58), rec -0.93% (t=-2.11, not a named target), rush_yds +1.44%
  (t=+1.30). FAILED the pre-registered bar (no NAMED target at t <= -2) but nothing worse at t >= +2 and every receiving
  stat moved the right way. Stays OFF (`--rain` exists, unused). Next: a bigger test, each season 2019-26 scored with
  rain constants fit on the OTHER seasons (about 100 rain games; needs 2019-23 weekly rosters for bench v2).

## 2026-11-12 (night): PRE-REGISTRATION: rain, bigger test (leave one season out), declared AFTER the 25-game test
* Each test season s in 2022-26 is scored with rain constants fit on every OTHER season 2019-26 (same fit code,
  `lab/rain_fit.py`), so no season is scored with constants that saw it. Bench v2 needs model history, so 2019-21 are
  fit-only. Rain games scored: 2022 15, 2023 18, 2024 6, 2025 11, 2026 9 (about 59).
* Arms: production + actual wind vs + rain (paired seeds). Bar unchanged: a named target (pass_yds, pass_att,
  rec_yds) improves at t <= -2 pooled; no stat worse at t >= +2. Pass: `--rain` ON for forecast rain at kickoff.
* RESULT (bigger test, 54 rain games 2022-26, each season scored with constants fit on the others): PASSED.
  rec_yds -1.44% (t=-2.60), rec -0.66% (t=-2.40), pass_yds -6.02% (t=-1.93; under-median 69% -> 53%), pass_cmp -2.52%
  (t=-1.61), nothing worse at t >= +2 (rush_yds +0.90%, t=+1.41). Better in 4 of 5 seasons (2025 +1.3%). SHIPPED:
  `--rain` for outdoor games with rain forecast at kickoff (50%+); constants refit on 2019-26 in weather.json.
  WAS@NYG (heavy rain, locked before this shipped): rain scenario saved in analysis/ and graded with the week.
