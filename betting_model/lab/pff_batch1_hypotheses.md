# Model lab batch 1: hypotheses written BEFORE any run (2026-11-05 ~21:40 UTC)

Scored sample (all families): production loop of regression_check.py (route blend, real starting QB, closing
spread for game script, calibration ON), 2024-25 weeks 4-18 (main) and 2026 weeks 4-8 (out of sample),
2000 sims per game, same seed per game OFF vs ON. Stats: targets, rec, rec_yds, rush_att, rush_yds, pass_att,
pass_cmp, pass_yds. Paired t on per player-game CRPS difference (ON - OFF).

Constants (slopes) fit on 2023 weeks 6-18 only (team-game or player-game residual regressions); shrinkage
constants chosen a priori below, never tuned on 2024-26.

F1 Pass protection vs pass rush
  Feature: offense pressures allowed per dropback (sum of blockers' pressures_allowed / team dropbacks) and
  defense pressures per opponent dropback (sum total_pressures / opp dropbacks), last 12 team-games, shrunk to
  league with k=200 dropbacks; combined as an odds ratio (log5): x = logit(p_match) - logit(p_league).
  Lever: team yards per target (rec_mult, listed receivers AND the QB's rest-of-team pool) x exp(b_y x) and QB
  completion multiplier x exp(b_c x).
  Expected sign: b_y < 0, b_c < 0. Target stats: rec_yds, pass_yds, pass_cmp, rec. Expect small (|d| < 0.5%).

F2 Run blocking vs run defense
  Feature: offense snap-weighted run-block grade (OL + TE, offense/run_blocking), defense snap-weighted run
  defense grade (defense/summary), last 12 team-games, shrunk with k=4 games; x = (off - lg) - (def - lg).
  Lever: RB yards per carry x exp(b x) (new neutral Player.ypc_mult wiring, applied to RBs only).
  Expected sign: b > 0. Target stat: rush_yds. Expect small.

F3 RB efficiency (PFF rushing/summary)
  Feature: yards after contact per attempt, last 30 player-games, shrunk to league RB rate with k=80 attempts;
  x = yco_shrunk - league. Lever: RB ypc x exp(b x).
  Expected sign: b > 0 (after-contact yards are the more player-owned, stable part of YPC). Target: rush_yds.

F4 Opponent coverage quality by receiver position
  Feature: defense snap-weighted coverage grade (defense/summary grades_coverage_defense, weights
  snap_counts_coverage) by defender group: WR <- CB, TE <- S + LB, RB <- LB; last 12 team-games, shrunk k=4 games.
  Lever: receiver yds_mult x exp(b x).
  Expected sign: b < 0 (better coverage, fewer yards per target). Target: rec_yds (also QB pass_yds).

F5 Missing defenders weighted by grade (only if time)
  Feature: defenders with >= 50% average defensive snap share over the team's last 4 games who do not appear in
  the projected game's PFF defense rows, weighted by snap share x (shrunk grade - 60). Lever: opponent
  rec_mult (pass) and rush_mult. Expected sign: missing good defenders -> more yards for the offense.

Bar (MODEL_LAB_PROMPT rule 3): target stat CRPS improves with t <= -2 on 2024-25 AND 2026; no other stat worse
with t >= +2; P10/P50/P90 coverage within 3 points of 10/50/90 (and not worse than OFF by more than that).

## Addendum after the 2023 fit, BEFORE any 2024-26 run (2026-11-05 ~21:46 UTC)
2023 fit (weeks 6-18, production residuals): pass_pro b_ypt=+0.013 (SE 0.057, sign opposite to hypothesis),
b_cmp=-0.037 (SE 0.032); run_block b=+0.0014/grade pt (SE 0.008); rb_eff b=-0.001 (SE 0.062, ~0);
coverage b=+0.0085/grade pt (SE 0.0061, sign OPPOSITE to hypothesis); missing_def b_ypt=-0.044 (SE 0.036,
opposite), b_ypc=+0.058 (SE 0.045). All |t| < 1.4: one season cannot pin these down.
Pre-committed primary test unchanged: score the 2023-fitted slopes on 2024-25 wk 4+ and 2026 wk 4-8.
Added variant pass_pro_prior (chosen now, from pressure arithmetic, not from any scored data): pressured
attempts complete ~0.15 less often and gain ~1.5 fewer yards per attempt; pressure rate ~0.33 so
dp = 0.22 x per logit unit -> b_cmp = -0.05, b_ypt = -0.04 (incremental effect assumed similar size because
the model's defense factor is yards-based, not pressure-based).
Diagnostic (not a fitted constant): the same residual regressions on the 2024-25 and 2026 OFF rows, to see
whether each feature's association with the production model's errors has the hypothesized sign.

## Secondary test, decided AFTER seeing the primary 2024-26 results (exploratory, not confirmatory)
Primary result: no family passes; the 2023-only slopes were too noisy (all |t| < 1.4). The residual
diagnostic on pooled 2024-25 showed pass_pro b_cmp -0.074 (t -3.7) and b_ypt -0.085 (t -2.5), run_block +0.010
(t +2.1), coverage +0.011 (t +2.4, opposite to hypothesis). Secondary: refit every slope on 2023 wk 6-18 + 2024
wk 4-18 OFF residuals (key coef_2023_24 in pff_matchups.json) and score 2025 wk 4-18 and 2026 wk 4-8 in split
mode. 2023-24 refit: pass_pro b_ypt -0.013 (SE 0.037), b_cmp -0.043 (SE 0.022); run_block +0.0056 (SE 0.0053);
rb_eff +0.011 (SE 0.043); coverage +0.0097 (SE 0.0043); missing_def b_ypt -0.004, b_ypc +0.026.
Caveat: 2025 was inside the pooled 2024-25 diagnostic I looked at, so this is not a clean held-out test.
