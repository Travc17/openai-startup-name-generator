# NFL player prop model (v2)

Joint game simulation for **receptions, receiving yards, rushing attempts,
rushing yards, and rush + rec yards**. Prices every main and alternate line,
prices same game parlays from one shared simulation, ranks alt line parlays,
applies the bankroll rules, and logs bets with closing line value.
Built on free nflverse play by play (2022 to current).

## Setup

```
cd betting_model
pip install -r requirements.txt
python nfl.py update          # downloads play by play into data/
```

## Commands

```
# Every key player in a game (injured players removed, their share redistributed)
python nfl.py game SEA CHI --week 8 --out "Rashid Shaheed"

# One player, priced lines (American odds or Robinhood cents like 53c)
python nfl.py project "Jaxon Smith-Njigba" --opp CHI --week 8 \
    --line rec_yds:99.5:-113:-113 --line rec:7.5:+110:-130

# Price a specific parlay
python nfl.py parlay SEA CHI --week 8 \
    --leg "Jaxon Smith-Njigba:rec_yds:over:89.5" \
    --leg "D'Andre Swift:rush_yds:under:59.5" --price +200

# Alt line ladders above and below each main line + best parlays
python nfl.py build SEA CHI --week 8 \
    --main "Jaxon Smith-Njigba:rec_yds:99.5" --main "Jaxon Smith-Njigba:rec:7.5" \
    --main "D'Andre Swift:rush_yds:59.5" --legs 2 [--cross-player-only]

# Backtest (optionally refit parlay correlations on other seasons first)
python nfl.py backtest --seasons 2024 2025 --fit 2022 2023

# Bet log
python nfl.py log add "JSN o99.5 rec yds" --price -113 --stake 50 --prob 0.577
python nfl.py log settle 1 win --close -125
python nfl.py log summary
```

Stats: `targets`, `rec`, `rec_yds`, `rush_att`, `rush_yds`, `rec_rush_yds`.
News: `--out NAME` (ruled out), `--mult "NAME=1.10"` (role change).

## How one game is simulated (20,000 times)

1. **Team volume**: both teams' targets and rushes drawn together. Correlations
   come from 2022+ data: a team that throws more runs less (−0.35), and one
   team's rushing moves opposite the other's (−0.48), which is game script.
2. **Shares**: recency weighted target and carry shares, shrunk toward position averages.
3. **Split**: teammates draw sequentially from what's left, so they compete for the same pie.
4. **Outcomes**: every target is resampled as a (caught, yards) pair from the
   player's own recent targets mixed with a league pool, so receptions and yards
   stay consistent with each other. Same for carries. Opponent adjusted.
5. **Cross player correlation**: a Gaussian copula fitted on real outcomes
   (`nflmodel/copula.json`). Player marginals are untouched.

## Backtest (walk forward, held out 2024 and 2025)

Alt line calibration (model P(over) vs actual), lines set at the model's own percentiles:

| stat | 25th pct line | median line | 75th pct line |
|---|---|---|---|
| receptions | 66% vs 69% | 42% vs 43% | 20% vs 20% |
| receiving yards | 75% vs 77% | 50% vs 52% | 25% vs 26% |
| rush attempts | 71% vs 71% | 46% vs 49% | 22% vs 27% |
| rushing yards | 75% vs 73% | 50% vs 53% | 25% vs 28% |

Overs hit 1 to 4 points more often than predicted. Part of that is a test
artifact (players who played but got zero touches are missing from play by play).

**Parlay correlations (the important finding):** different players in the same
game are nearly independent in real outcomes. Fitted on 2022 to 2025 (17,255 pairs):

| pair | correlation |
|---|---|
| opposing RBs (rush yds) | −0.15 |
| same team WR + RB | −0.03 |
| same team WR + WR | +0.02 |
| opposing WRs | +0.02 |

On held out seasons the copula matched reality about as well as independence did.
So multi player parlays carry little hidden correlation edge. The large real
correlation is **within one player** (receptions with yards), which the
simulation captures and sportsbooks also price.

## Injuries: how much share teammates really absorb

`--out NAME` removes a player and boosts teammates by
`1 + k * (1 / (1 - vacated share) - 1)`, with k fitted on every 2022 to 2025
game where a regular sat (`nflmodel/absences.json`):

| | k | n | actual/predicted: no bump | full proportional | fitted |
|---|---|---|---|---|---|
| targets, first game missed | 0.29 | 1,643 | 1.08 | 0.87 | 1.01 |
| targets, continuing absence | 0.41 | 731 | 1.07 | 0.89 | 0.99 |
| carries, first game missed | 0.27 | 183 | 1.19 | 0.71 | 1.01 |
| carries, continuing absence | 0.36 | 87 | 1.23 | 0.71 | 0.97 |

Full proportional redistribution overshoots by 11 to 29%: backups and game plan
changes soak up most vacated looks. k fitted on 2022 and 2023 alone gave
0.27/0.40/0.23 and held up on 2024 and 2025 (lowest error of the three methods).

## Context data (v3)

| Feature | Data | Backtest result | Status |
|---|---|---|---|
| Zero touch games | nflverse snap counts | Backups and QB rushing error down 2 to 7% | ON |
| Usage tiered share prior | learned from prior seasons only | Backups now calibrated (median line hit 47 to 53%, was 34 to 43%); starters unchanged | ON |
| Depth chart role changes | nflverse daily depth charts (game day snapshot) | Promoted: targets x1.12, carries x1.15. Demoted: x0.82. Fitted 2022 to 2024, held on 2025 (x1.22 / x0.77) | ON |
| Return from long absence (IR, ACL) | 2022-25, 128 return games | Game 1 back: targets x0.73, carries x0.72; game 2: x0.90. Held on both 2022-23 and 2024-25 | ON (auto) |
| Defense vs position lever | play by play | Paired test, 2,223 player games 2024-25: 5 versions (yds/target 12 game & full season, target volume, field zones, zones+volume) all within noise (abs t < 2). Full season yds/target was neutral | ON as a lever (`--defense` to switch) |

## Game lines: spreads and totals (tested against REAL closing lines)

Protocol: tune on 2023-2024 only, then run the locked 2025-2026 test ONCE. Target: 54.4%+ (2 pts over 52.4% break even).

| Model | Locked test 2025-26 | Verdict |
|---|---|---|
| Spreads, best version (pass/rush split + points) | ATS 38.6% when it disagreed 2+ pts (n=166); margin error 10.58 vs market 9.67 | FAILS. Do not bet model spreads. |
| Totals, QB-specific ratings + pass/rush split | Locked 2025-26: O/U 55.4% at 2+ (n=166) | Looked promising, then FAILED the wider test below |

Wider walk-forward totals test (2019-21 warmup, coefficients fit only on prior seasons):

| Season | O/U at 2+ pt disagreement | Note |
|---|---|---|
| 2022 | 42.8% (n=138) | clean out of sample |
| 2023 | 47.5% (n=122) | mostly clean |
| 2024 | 58.6% (n=111) | tuning season, not independent |
| 2025 | 53.8% (n=130) | locked |
| 2026 | 50.0% (n=42) | locked |
| **All 5** | **50.3% on 543 bets, -21.8 units** | **No edge. Totals model shelved.** |

`gameline` prices any line by simulating around the big-book consensus (held out calibration within 1-2 pts on alt spreads).
Defense vs position: six versions tested (yards, volume, zones, catch rate allowed), none beat noise. Kept as a light visible lever.

## QB layer
QB passing lines are the sum of every simulated target (listed receivers + the rest of the team), so a QB's
yards, completions, and his receivers always agree. QB quality (yards per target and completion rate vs league,
blended toward league for veterans and toward a measured backup level otherwise) scales his receivers.
Backtest 2024-25 (886 QB starts): pass yds error 59.2 vs 59.6 for the QB's own recent average; P10/P50/P90
coverage 11%/51%/92%. QB adjustment: completions -0.97% (t=-2.6), pass yds -0.96% (t=-1.7), receiver yards in
QB-change games -1.10% (t=-1.67), unchanged otherwise. Limits: prior is an average backup (too generous for
third-string QBs); TD/INT lines not calibration-checked yet.

## PFF routes (paid data)
Route participation (routes / team dropbacks, last 3 games) x targets per route run, blended 50/50 with
the target-share history. Backtest 2024-25 weeks 4+, 3,515 player games: targets -0.93% (t=-3.35),
receptions -0.60% (t=-2.43), receiving yards -0.20% (n.s.). Route-based share alone was not better.

## PFF features tested and left OFF (2024-25 weeks 4+, 3,534 player games, vs model with routes)
| Feature | Receptions | Receiving yards | Targets |
|---|---|---|---|
| Yards per route run (efficiency) | +0.00% | +0.05% (t=+0.29) | +0.00% |
| Slot vs wide vs defense | +0.00% | **+0.70% WORSE (t=+3.98)** | +0.00% |
| Man/zone per route (PFF, incl. 2026) | -0.04% (t=-0.67) | +0.05% | -0.05% (t=-0.88) |

## PFF matchup features, model lab batch 1 (2026-11-05): all five families FAILED, all switches OFF
Code: `nflmodel/pff_matchups.py` (features, only games before the projected one), switches `Config.pff_pass_pro`,
`pff_run_block`, `pff_rb_eff`, `pff_coverage`, `pff_missing_def` (default OFF; they need `model.pffm =
PFFMatchups(model)`), new neutral `Player.ypc_mult` (1.0 = no change; regression check identical before and after).
Harness: `lab/pff_batch1.py` = the `regression_check.py` scoring loop (route blend, real starting QB, closing spread,
calibration ON), 2,000 sims, same seed OFF and ON. Slopes: fit on 2023 weeks 6-18 residuals of the production model
(`pff_matchups.json` key `coef`), so 2024-26 are out of sample; shrinkage constants were set before any scored run
(k = 200 dropbacks, 4 team-games, 80 RB attempts; 12-game window). Facets pulled to `data/pff/<facet>/` (2023-26).
Hypotheses and signs were written before each run (pressure, better coverage and better run defense cut yards).

| Feature (lever) | 2023 slope (SE) | 2024-25 wk 4+, % CRPS (t) | 2026 wk 4-8, % CRPS (t) | max coverage move | Verdict |
|---|---|---|---|---|---|
| Pass pro x pass rush, log5 pressure odds (team yds/target + QB completion rate) | ypt +0.013 (0.057), cmp -0.037 (0.032) | rec -0.05 (-1.69); rec yds -0.01 (-0.85); QB cmp -0.17 (-1.44); QB yds +0.02 (+0.63) | rec **+0.18 (+2.36)**; rec yds +0.05 (+0.94); QB cmp +0.40 (+1.58); QB yds -0.30 (-2.95) | 1.4 pts | OFF |
| Same, a priori slope (ypt -0.04, cmp -0.05) | n/a | rec -0.07 (-1.87); rec yds **-0.06 (-2.77)**; QB cmp -0.20 (-1.30); QB yds -0.12 (-1.53) | rec **+0.20 (+2.25)**; rec yds +0.11 (+1.80); QB cmp +0.59 (+1.73); QB yds +0.19 (+0.93) | 1.4 pts | OFF |
| Run-block grade (OL+TE) minus run-defense grade (RB ypc) | +0.0014/pt (0.0080) | rush yds +0.00 (+0.12) | rush yds +0.02 (+0.57) | 0.5 pts | OFF |
| RB yards after contact/att, shrunk (RB ypc) | -0.001 (0.062) | rush yds +0.00 (+0.42) | rush yds -0.00 (-0.38) | 0.5 pts | OFF |
| Coverage grade: WR<-CB, TE<-S+LB, RB<-LB (receiver yds) | **+0.0085/pt (0.0061)** | rec yds +0.01 (+0.16); QB yds -0.15 (-1.40) | rec yds -0.07 (-0.61); QB yds -0.46 (-1.45) | 0.7 pts | OFF |
| Missing regulars (>=50% snaps) x grade above 60 (opp. pass and rush yds) | ypt -0.044 (0.036), ypc +0.058 (0.045) | rec yds +0.02 (+1.01); rush yds -0.00 (-0.02); QB yds -0.03 (-0.23) | rec yds +0.09 (+1.75); rush yds +0.26 (+1.37); QB yds +0.27 (+1.06) | 1.0 pts | OFF |

n: 2024-25 = 448 games, 5,096 player-games (3,794 receiver, 1,324 rusher, 896 QB starts); 2026 = 73 games, 846
player-games (632 / 206 / 146). Coverage move = largest change in any P10/P50/P90 share, ON vs OFF (all within 3).
Numbers above are "split" runs: each team simulated first once, keeping only that team's rows, so a lever on one
team cannot reshuffle the random draws of the other (see "surprises"). The pre-registered single-call runs gave the
same verdicts (e.g. a priori pass pro: QB yds -0.17% t=-1.91 in 2024-25, +0.39% t=+1.70 in 2026).
Secondary, exploratory (decided after seeing the above, slopes refit on 2023-24 `coef_2023_24`, scored 2025 and 2026):
pass pro QB cmp -0.45% (t=-2.38), rec yds -0.06% (t=-2.17) in 2025 but rec +0.19% (t=+2.39) worse in 2026; run block
+0.05% / +0.09%; RB YACo +0.03% / +0.01%; coverage QB yds -0.19% (t=-1.16) / -0.51% (t=-1.42); missing defenders ~0.
No family passes the bar in either test.

Surprises and leads:
* Coverage grades point the WRONG way, consistently: defenses with better prior PFF coverage grades allow MORE yards
  per target than the model expects (residual slope +0.0085, +0.0110, +0.0103, +0.0127 per grade point in 2023, 2024,
  2025, 2026). Likely the model's yards-allowed defense factor over-trusts recent results (good defenses regress to
  the mean more than its shrinkage assumes). Next test: heavier `opp_shrink_targets` / position-defense shrink.
* Pressure lowers completions vs the model in every season (residual slope -0.037, -0.045, -0.096, -0.015) and yards
  per attempt in 2024-25, but the size swings by season and 2026 (146 QB starts) got worse with any slope. Model
  completions ran 3.6% high in 2025 and 1.4% low in 2026, so a downward lever helps one and hurts the other.
* Random-stream artifact in single-call paired tests: one team's lever changes a Poisson/binomial draw, which
  reshuffles every later draw in the game, so stats the lever cannot touch show |t| > 2 by chance (single-call
  coverage run: rush att t=+2.27 in 2024-25, targets t=+2.31 in 2026). Split runs remove it for team-level levers;
  completion levers (binomial) still reshuffle draws within the team.
* `pff_missing_def` reads who played in the projected game from PFF rows (same convention as the backtests, which
  assume inactives are known); live use would need the inactive list mapped to PFF ids.

## Model review (2026-11-03): every test, passed and failed

* 2026-11-12 PM game score BLEND (model's own margin/total + closing line; weight fit 2022-24, judged 2025-26): weight
  0.00 on margin, 0.05 on total; 2025-26 margin RMSE 12.19 both, total 13.22 vs 13.21 (t=+0.72); winners right 63.5%
  model vs 66.5% line. FAILED: the closing line stays the score, winner and total of record.

* 2026-11-12 PM QB CAREER pass volume (Config.qb_volume_mode='career', k=8 fixed, OFF): ratio of his teams' targets in his
  starts (any team, this season and last) to each team-season mean. 536 games, paired: pooled targets -0.07% (t=-1.18), rec
  -0.07% (t=-1.23), QB stats |t|<0.4. FAILED. QB-change games: right direction, not significant; production's pass_att median
  is too high there (58% below, n=267): next test target.

* 2026-11-12 QB-specific team pass volume (Config.qb_volume_k, OFF): offense targets blended toward the starting QB's
  starts for the team. 2024 (selection): every k made QB stats worse (k=2 pass_att +1.41%, k=4 +0.81%, k=8 +0.36%); k=8
  chosen. 2025-26 vs production: targets -0.14% (t=-1.98), rec -0.12% (t=-1.75), QB stats -0.1 to -0.2% (|t|<1). FAILED
  (no stat at t<=-2). A new QB's first starts are mostly noise for team volume. Trigger was WAS@NYG (McCarthy).

* 2026-11-12 SHIPPED carry-only role swing (Config.role_noise_sigma 0.25, role_noise_t 0: mean-preserving lognormal
  swing on carry shares under 0.30), after giving it its own random stream. Bench v2 vs early exit (production),
  2025-26: rush_att -0.23% (t=-2.9), rush_yds -0.20% (t=-2.6), nothing worse at t>=+2 (pass_cmp +0.07%, t=+1.1).
  Pooled 2024-26: rush_att -0.22% (t=-3.5), rush_yds -0.13% (t=-2.1), pass_cmp +0.11% (t=+1.96, watch). The earlier
  failure (pass_cmp t=+2.7) was mostly shared-stream reshuffling of early-exit draws. Regression baseline refreshed.

* 2026-11-12 Early exit + carry-only role swing (role_noise_sigma 0.25, role_noise_t 0): vs production (early exit),
  2025-26 rush_att -0.26% (t=-2.9), rush_yds -0.33% (t=-4.0) but pass_cmp +0.20% (t=+2.7). FAILED the pre-registered rule;
  stays OFF. Likely artifact: the swing draws share the early-exit random stream, so exits are reshuffled across
  receivers and pairing breaks for QB lines. Re-test with a separate stream is queued.

* 2026-11-12 SHIPPED early exit (Config.early_exit ON) after the lab bench was rebuilt on live rosters (lab/bench_v2.py:
  nfl.roster_for with real inactives from nflverse weekly rosters, next-man-up, zero-snap actives scored as 0). Bench v2,
  2025-26 (judged): targets -0.15% (t=-2.6), rec -0.20% (t=-3.3), rec_yds -0.16% (t=-2.7), rush_att -0.22% (t=-2.3), nothing
  worse at t>=+2; pooled 2024-26 also passes (rec -0.13%, t=-3.0). Role swing sigma 0.25 also passed alone (rush_att -0.37%,
  t=-4.4) but the combination lost early exit's receiving gain (rec +0.13% vs ee, t=+2.4), so per the pre-registered rule
  only early exit shipped. Bench v1 had failed both: it graded backups against rosters live reports never use.
  Regression baseline refreshed. Projections saved before 2026-11-12 used early exit OFF (replays of them differ).

* 2026-11-11 Small-role share uncertainty: (a) lower beta concentration for small shares (Config.share_conc_ref)
  ABANDONED after a smoke test: it piles small shares near zero (median falls). (b) Mean-preserving lognormal role
  swing for t_share < 0.10 / c_share < 0.30 (Config.role_noise_sigma, sigma chosen on 2024 = 0.25): 2025-26 depth
  carries -0.27% (t=-1.8), nothing at t<=-2, pass_cmp +0.13% (t=+1.8); larger sigma hurt targets (t=+2.6/+4.3).
  FAILED, OFF. Diagnosis: a third of the depth gap was scoring (zero-snap actives dropped); backup-RB gap sits
  mostly in games with a starter out (the backtest bench lacks production's next-man-up). Details:
  reviews/lab_2026-11-11_role_noise.md

* 2026-11-11 Early exit (Config.early_exit, OFF): RB/WR/TE leave hurt at 2019-23 rates (RB 2.9%, WR 4.2%, TE 2.7%),
  backups absorb. Paired test 2024-26 (536 games, ~16.7k rows per variant): measured rates rec_yds +0.08% (t=+2.0),
  pass_cmp +0.11% (t=+2.0), nothing better at t<=-2; x1.5 rates helped depth targets/rec (-0.14%, t=-2.4) but hurt
  leaders' targets/rec (+0.24%, t=+3.4). FAILED. Depth p90 coverage barely moved (84.9 -> 85.4): the thin depth tails
  have another cause. Details: reviews/lab_2026-11-11_early_exit.md

Full-season walk-forward run of the live model (routes + QB layer + game script), weeks 4+, real starting QBs,
closing spread for game script. Median absolute error, model vs naive (player's last 8 games average):

| season | targets | receptions | rec yds | rush att | rush yds |
|---|---|---|---|---|---|
| 2024 | 2.17 vs 2.20 | 1.65 vs 1.70 | 22.43 vs 22.90 | 3.97 vs 4.04 | 24.56 vs 25.53 |
| 2025 | 2.05 vs 2.15 | 1.58 vs 1.67 | 21.77 vs 22.62 | 3.91 vs 4.11 | 24.79 vs 25.92 |
| 2026 (wk 4-9) | 2.17 vs 2.17 (tie) | 1.68 vs 1.72 | 23.69 vs 24.52 | 4.25 vs 4.58 | 26.95 vs 29.21 |

QB lines, 1,028 starts 2024-26, share of results under the model's P10 / P50 / P90 (calibrated = 10 / 50 / 90):
pass yds 11.5 / 50.0 / 91.8, completions 13.1 / 50.9 / 89.4, attempts 15.6 / 54.2 / 88.6 (attempts run high:
likely starters leaving games early, which the sim does not model), INT 12.0 / 51.8 / 91.0.
TDs: 1+ TD model 73.7% vs actual 77.8%, 2+ 42.1% vs 45.8%, 3+ 20.0% vs 18.0%. **TD lines are biased (too few
TDs at the low end): still no TD bets.** INT 1+ 49.7% vs 48.4%: close, but no INT bets until a held-out test.

| Change | Test | Result | Status |
|---|---|---|---|
| Next man up by position (vacated share goes mostly to the same position) | held out, squared error vs single-k bump | targets -1.6% (n=623, better in 100% of bootstraps); carries -4.4% (n=75, 86%) | ON |
| No bump once a player has missed 2+ straight games | his absence is already in teammates' recent shares | avoids double count (Monangai case) | ON |
| Per-stat calibration maps (rank-preserving quantile remap, shrunk 50% to identity) | fit on 2024, scored on 2025-26 | Brier lower on every stat (total -0.14%); full shrink (no 50%) was worse (+0.03%) | ON |
| Wind (outdoor, per mph above 8) | fit 2019-23, scored 2024-26 games with 10+ mph | QB pass yds -3.71% (t=-2.90), rec yds -0.26% (n.s.), rush yds -0.02% (n.s.) | ON (`--wind MPH`) |
| Draft-capital prior for backup QBs | held out | 0.2071 to 0.2065, below the bar | OFF |
| Team-volume correlation/SD fit only on prior games (leakage fix) | paired CRPS, 2024-26, same seeds | every stat within 0.2%, no abs t >= 2 | ON (removes look-ahead, no cost) |
| Combo price discount (ticket vs product of legs) | 0.93 to 0.99 on the two Robinhood tickets seen | not enough evidence | parlays now priced with no discount (conservative) |
| PFF pass protection x pass rush (`pff_pass_pro`, lab 2026-11-05) | paired CRPS, 2023-fit slopes, 2024-25 wk 4+ (3,794 receiver / 896 QB games) and 2026 wk 4-8 (632 / 146) | 2024-25: rec -0.05% (t=-1.69), QB cmp -0.17% (t=-1.44); 2026: rec **+0.18% (t=+2.36) worse**, QB yds -0.30% (t=-2.95) | OFF (fails: no target-stat gain in both periods, rec worse in 2026) |
| Same, slope set a priori from pressure arithmetic (b_cmp -0.05, b_ypt -0.04) | same games | 2024-25: rec yds -0.06% (t=-2.77), rec -0.07% (t=-1.87); 2026: rec **+0.20% (t=+2.25) worse**, QB cmp +0.59% (t=+1.73) | OFF (helps 2024-25, hurts 2026) |
| Same, slopes refit on 2023-24 (secondary, exploratory) | scored 2025 wk 4+ and 2026 | 2025: QB cmp -0.45% (t=-2.38), rec yds -0.06% (t=-2.17); 2026: rec **+0.19% (t=+2.39) worse** | OFF (same 2025-good / 2026-bad split) |
| PFF run blocking vs run defense grades (`pff_run_block`, RB ypc) | 1,324 / 206 RB games | rush yds +0.00% (t=+0.12) / +0.02% (t=+0.57); refit 2023-24: +0.05% / +0.09% | OFF (neutral) |
| PFF RB yards after contact per attempt (`pff_rb_eff`, RB ypc) | same | rush yds +0.00% (t=+0.42) / -0.00% (t=-0.38); 2023 slope ~0 | OFF (neutral) |
| PFF coverage grade by defender group (`pff_coverage`, receiver yds) | 3,794 / 632 receiver games | rec yds +0.01% (t=+0.16) / -0.07% (t=-0.61); QB yds -0.15% (t=-1.40) / -0.46% (t=-1.45) | OFF (n.s.; slope sign is the OPPOSITE of the hypothesis, see below) |
| PFF missing regular defenders x grade (`pff_missing_def`) | 5,096 / 846 player games | rec yds +0.02% (t=+1.01) / +0.09% (t=+1.75); rush yds -0.00% / +0.26% (t=+1.37) | OFF (neutral to slightly worse) |

Leakage audit of fitted constants: `absences.json`, `depth.json`, `returns.json`, `copula.json` and the
game-script slope were fit on 2022-25, so 2024-25 backtests are partly in-sample for those few constants;
2026 is fully out of sample and shows the same pattern. `weather.json` (2019-23) and the calibration test
(fit 2024, score 2025-26) are clean. The production calibration map is refit on 2024-26.

Pick-level paper test (Monday CHI@SEA, 15 qualifying picks, logged AFTER the game, so hindsight only and
correlated, one game): 4 of 15 won (26.7%) vs 38.9% expected, flat ROI -28.4%. Moved to
`reviews/2026_wk08_CHI_at_SEA_retro_picks.csv`. It proves nothing either way; the real record starts now.

## Current-year weighting for receivers (tested 2026-11-03, all OFF)
Question: should projections lean on this season instead of past seasons? Carries already do (prior seasons x0.4,
4-game half-life: tested better). For receivers, paired CRPS on 2024-26 weeks 4+ (4,920 player-games, same seeds;
+ means worse):

| Version | Targets | Receptions | Rec yds |
|---|---|---|---|
| Prior seasons x0.3 only when team, QB or head coach changed vs last season | +0.01% (t=+0.2) | -0.01% | -0.01% |
| Same, but 2 straight seasons of continuity required ("long stint") | +0.05% (t=+0.8) | +0.04% | +0.05% |
| Current year only (x0.0) when 1-season continuity breaks | +0.05% (t=+0.5) | -0.02% | +0.01% |
| Current year only when 2-season continuity breaks | +0.19% (t=+1.7) | +0.11% | +0.11% |
| All receivers: prior seasons x0.4 | +0.09% (t=+1.6) | +0.04% | -0.01% |
| All receivers: weighted exactly like carries | +0.12% (t=+1.4) | +0.08% | +0.02% |
| Everything (shares, catch rate, yards) weighted like carries | +0.10% | **+0.17% (t=+2.0)** | **+0.21% (t=+2.6)** |

Where the continuity rule moved a projection by 1+ target (347-442 player-games) it was slightly better
(targets -0.7%, t=-1.9), not enough to ship. With the current weights, this season already carries about two
thirds of a receiver's target-share weight by week 9. Receiver roles that dip tend to bounce back (36-game
segment test). Coach-driven role cuts are handled case by case (blind spot or a documented `--mult`), not by a
global rule. Switches kept in `Config`: `t_carryover_break`, `continuity_seasons`, `recent_targets`, `recent_all`.

## Per-game exposure cap (approved 2026-11-03)
Every bet on one game is correlated (same game script, same QB), so the 10% cap is on the game, not each bet.
`report` builds a "Bet plan": up to 3 bets by expected profit, no player+stat repeated, stakes scaled down
together to fit 10% of current bankroll (never below $50; the weakest bet is dropped if the minimums alone
break the cap). Example at $2,257 (cap $225): $85 + $75 + $50 = $210 fits; at $1,500 (cap $150) the third
bet is dropped and the other two scale to $75 + $70.

## Paper-trading record and regression check
* `report` writes every qualifying pick (stake > 0) to `picks_log.csv` with a UTC timestamp, price, fee and
  model probability. It refuses to log a game that is already in the play by play (no hindsight rows).
* `python nfl.py picks close --game JAX@BAL --label "Zay Flowers 5+ catches" --price 0.43` records the last price
  before kickoff; `picks summary` then reports closing line value (the fastest honest signal of edge).
* `python nfl.py picks grade` settles open picks from the data (a player with no snaps, or a QB with no
  attempts, voids the pick); `python nfl.py picks summary` prints hit rate vs expected and flat-stake ROI.
* `python regression_check.py` re-runs the live model on 2025 weeks 10-13 (fixed seeds, about 30 seconds)
  and flags any stat whose CRPS worsens by more than 2% or whose P10/P50/P90 coverage moves more than
  5 points from `regression_baseline.json`. Run it after every code change and every `update`.

## Honest limits

* No historical prop lines: calibration is tested, profit is not. Closing line value on live bets
  (`log summary`) and the timestamped paper log are the real tests. One real bet so far (CLV -1.7 pts of implied probability).
* Three way backfields where a player returns from IR are still weak: a back with no games in the last
  3 is not auto included unless he's a depth chart starter.
* Third-string / undrafted QBs: the prior is an average backup, so they and their pass catchers stay blind spots.
* No TD, INT, kicker or defense props. Starters leaving a game early (injury, blowout benching) is not simulated.
* NFL only.

## Model vs the books' closing lines (2026-11-05; `hist_props.py`, `hist_compare.py`)
Closing props for 2025 (271 games, 8 books) and 2026 weeks 1-8 (121 games), 5 markets, scored against the live
model's walk-forward raw sims. Details: `reviews/hist_2025_model_vs_market.md`, `reviews/hist_2026_model_vs_market.md`.

| Test | 2025 wk 4-18 (partly in-sample) | 2026 wk 1-8 (out of sample) |
|---|---|---|
| Brier, model vs market (lower is better) | 0.2588 vs 0.2477 | 0.2610 vs 0.2483 |
| 20% model / 80% market blend, Brier | 0.2449 held out (wk 12-18) | 0.2474 (weight fit on 2025) |
| Model unders, edge >= 10%, Kalshi-like price | +10.8% (n=2,522) | +9.3% (n=1,086, CI +2.4% to +16.0%) |
| Model unders, edge >= 2% | +7.3% | +3.7% (CI -1.3% to +8.7%) |
| Model overs, edge >= 2% | -6.8% | -4.4% |
| Blind unders | +3.9% | +0.9% |
The market is the better predictor; the model adds a little as a blend and finds value only in strong unders.

## Two-stage pipeline (2026-11-03)
* **Stage 1, projections** (`nflmodel/projections.py`, `report --proj`): every player's distribution
  saved as P(stat >= k) on a half-unit grid, plus mean and 10/25/50/75/90th percentiles, game meta,
  blind-spot flags, and every manual adjustment. No prices. Checked against the report on JAX@BAL wk9:
  230 rungs, largest difference 0.00004 (rounding).
* **Stage 2, bet finder** (`nflmodel/market.py`, `nfl.py price`): quotes from any venue (American odds
  or cents + per-venue fee). Big-book no-vig probability averaged over books quoting both sides of the
  same line. Each quote gets a model edge, a market edge, and a verdict (BOTH AGREE, market only,
  model only, model vs market, blind spot, pass). Robinhood "x+" rungs map to over/under x - 0.5.
* **Whole-number fix for book lines**: results are whole numbers, so over 45.5 = 46 or more. Book rows
  in the report used P(sim > 45.5), while rungs used P(sim >= 46) (the convention the calibration maps
  were fit on). Continuous yard sims made those differ by about 1 point (Tuten rush yds 59.5: 49.8% vs
  48.6%). Book rows now use P(sim >= 46). Count stats were unaffected. Regression check: no drift.
* **Odds feed** (`nflmodel/odds_api.py`, `nfl.py odds AWAY HOME --out quotes.csv`): The Odds API v4,
  five US books, props in the bet finder's quotes format, game lines in a separate file. Player names
  match across venues by a normalized key ("Brian Thomas Jr." = "Brian Thomas Jr"). TD/INT quotes are
  labeled "not calibrated" and never bet.

