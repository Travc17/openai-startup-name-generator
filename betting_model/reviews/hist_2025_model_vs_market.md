# Model vs closing lines, 2025 weeks 4-18

7686 player props matched (221 games). Raw sims (4000 per game), no calibration map.
Caveat: some fitted constants used 2022-25 data, so this is partly in-sample for the model (favors the model).

## Accuracy (lower is better)

| Stat | n | Median abs error: model | closing line | Brier: model | model calibrated | market | Log loss: model | market |
|---|---|---|---|---|---|---|---|---|
| pass_yds | 293 | 61.46 | 57.66 | 0.2727 | 0.2722 | 0.2497 | 0.7415 | 0.6925 |
| rec | 2742 | 1.45 | 1.44 | 0.2566 | 0.2572 | 0.2446 | 0.7133 | 0.6824 |
| rec_yds | 2405 | 18.96 | 18.32 | 0.2573 | 0.2574 | 0.2498 | 0.7115 | 0.6926 |
| rush_att | 1105 | 3.21 | 2.97 | 0.2555 | 0.2534 | 0.2482 | 0.7313 | 0.6895 |
| rush_yds | 1141 | 18.55 | 17.65 | 0.2668 | 0.2638 | 0.2497 | 0.7399 | 0.6930 |
| ALL | 7686 | 12.00 | 11.49 | 0.2588 | 0.2583 | 0.2477 | 0.7204 | 0.6886 |

## When model and market disagree (model P(over) minus market's)

| Gap | n | Over hit rate | Model said | Market said |
|---|---|---|---|---|
| -1.00 to -0.15 | 1939 | 42.8% | 25.6% | 49.9% |
| -0.15 to -0.05 | 2282 | 44.7% | 39.7% | 49.4% |
| -0.05 to +0.05 | 2147 | 47.6% | 49.3% | 49.6% |
| +0.05 to +0.15 | 1000 | 47.6% | 58.5% | 49.5% |
| +0.15 to +1.00 | 318 | 48.4% | 70.6% | 48.6% |

## Blend (weight on the MODEL fit on weeks 4-11, scored on weeks 12-18)

* Probability blend: model weight 0.20. Held-out Brier: model 0.2555, market 0.2467, blend 0.2449.
* Median blend: model weight 0.10. Held-out median abs error: model 11.88, line 11.51, blend 11.49.

## Paper bets: model edge >= 2% vs the best book price (flat 1 unit, no Kalshi fee)

| Group | Bets | Win % | ROI |
|---|---|---|---|
| ALL | 5905 | 53.8% | +3.0% |
| pass_yds over | 116 | 47.4% | -10.0% |
| pass_yds under | 79 | 36.7% | -30.3% |
| rec over | 573 | 45.4% | -8.9% |
| rec under | 1600 | 55.1% | +5.9% |
| rec_yds over | 441 | 48.3% | -8.0% |
| rec_yds under | 1284 | 56.5% | +7.5% |
| rush_att over | 175 | 44.6% | -11.8% |
| rush_att under | 767 | 61.0% | +15.8% |
| rush_yds over | 176 | 54.0% | +2.9% |
| rush_yds under | 694 | 53.2% | +0.7% |
| edge 2-5% | 1254 | 50.8% | -3.6% |
| edge 5-10% | 1679 | 52.4% | +0.7% |
| edge 10%+ | 2972 | 55.8% | +7.2% |

## Model skill vs the plain "unders hit more" bias (bootstrap by game, 2,000 resamples)

| Bet rule | Price | n | Win % | ROI | 95% CI |
|---|---|---|---|---|---|
| Every under, blind | best of 8 books | 7,686 | 54.4% | +3.4% | +1.0% to +6.0% |
| Model under, edge >= 2% | best of 8 books | 4,424 | 55.9% | +6.6% | +3.3% to +10.1% |
| Model under, edge >= 10% | best of 8 books | 2,464 | 57.4% | +9.9% | +5.6% to +14.4% |
| Model under, edge >= 2%, weeks 4-11 | best of 8 books | 2,226 | 55.4% | +6.2% | +1.5% to +10.9% |
| Model under, edge >= 2%, weeks 12-18 | best of 8 books | 2,198 | 56.4% | +7.1% | +2.0% to +12.1% |
| Every under, blind | no-vig + 2c (Kalshi proxy) | 7,686 | 54.4% | +3.9% | +1.2% to +6.5% |
| Model under, edge >= 2% | no-vig + 2c | 4,459 | 56.1% | +7.3% | +3.7% to +10.5% |
| Model under, edge >= 10% | no-vig + 2c | 2,522 | 57.8% | +10.8% | +6.6% to +15.0% |
| pass_yds under, edge >= 2% | no-vig + 2c | 85 | 36.5% | -29.9% | -48.9% to -9.8% |
| rec under, edge >= 2% | no-vig + 2c | 1,569 | 55.5% | +5.8% | +0.8% to +10.8% |
| rec_yds under, edge >= 2% | no-vig + 2c | 1,326 | 56.3% | +8.2% | +2.7% to +13.3% |
| rush_att under, edge >= 2% | no-vig + 2c | 770 | 61.4% | +17.6% | +10.9% to +24.0% |
| rush_yds under, edge >= 2% | no-vig + 2c | 709 | 53.5% | +2.2% | -4.3% to +8.6% |

Reading (2026-11-05):
* As a predictor, the closing line beats the model on every stat (median error and Brier). The model is too
  confident. A blend of 20% model / 80% market beat the market alone on held-out weeks (Brier 0.2449 vs 0.2467).
* As a bet filter, the model's UNDERS beat blind unders by about 3 to 7 points of ROI, in both halves of the season.
  Its OVERS lost (rec -8.9%, rec_yds -8.0%, rush_att -11.8%, pass_yds -10.0% at best book price).
* Limits: one season; some constants were fit on 2022-25 (partly in-sample); "best of 8 books" is line shopping
  Travis does not have; the Kalshi proxy assumes Kalshi trades near the books' no-vig price. Subgroup results (by
  stat) were chosen after looking: confirm on 2024 and on 2026 weeks 1-8 (fully out of sample) before any rule change.
