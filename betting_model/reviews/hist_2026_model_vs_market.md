# Model vs closing lines, 2026 weeks 1-8

3420 player props matched (107 games). Raw sims (4000 per game), no calibration map.
Out of sample: the fitted constants used 2022-25 data only (raw sims; the calibrated column uses a map fit on 2024-26).

## Accuracy (lower is better)

| Stat | n | Median abs error: model | closing line | Brier: model | model calibrated | market | Log loss: model | market |
|---|---|---|---|---|---|---|---|---|
| pass_yds | 160 | 61.28 | 57.15 | 0.2644 | 0.2644 | 0.2502 | 0.7246 | 0.6936 |
| rec | 1322 | 1.60 | 1.59 | 0.2591 | 0.2588 | 0.2453 | 0.7185 | 0.6838 |
| rec_yds | 1033 | 21.35 | 20.42 | 0.2655 | 0.2646 | 0.2504 | 0.7282 | 0.6939 |
| rush_att | 376 | 3.72 | 3.28 | 0.2524 | 0.2507 | 0.2495 | 0.7313 | 0.6921 |
| rush_yds | 529 | 17.95 | 16.50 | 0.2619 | 0.2601 | 0.2503 | 0.7255 | 0.6937 |
| ALL | 3420 | 13.12 | 12.37 | 0.2610 | 0.2601 | 0.2483 | 0.7242 | 0.6897 |

## When model and market disagree (model P(over) minus market's)

| Gap | n | Over hit rate | Model said | Market said |
|---|---|---|---|---|
| -1.00 to -0.15 | 827 | 42.3% | 26.4% | 49.8% |
| -0.15 to -0.05 | 1007 | 48.3% | 39.6% | 49.4% |
| -0.05 to +0.05 | 912 | 48.7% | 49.2% | 49.4% |
| +0.05 to +0.15 | 503 | 50.1% | 58.6% | 49.4% |
| +0.15 to +1.00 | 171 | 44.4% | 70.4% | 49.2% |

## Blend (weight on the MODEL fit on weeks 1-4, scored on weeks 5-8)

* Probability blend: model weight 0.25. Held-out Brier: model 0.2602, market 0.2461, blend 0.2457.
* Median blend: model weight 0.20. Held-out median abs error: model 13.33, line 12.48, blend 12.52.
* Fixed blend from an earlier season (model weight 0.20), all rows: Brier model 0.2610, market 0.2483, blend 0.2474.

## Paper bets: model edge >= 2% vs the best book price (flat 1 unit, no Kalshi fee)

| Group | Bets | Win % | ROI |
|---|---|---|---|
| ALL | 2637 | 52.8% | +0.9% |
| pass_yds over | 58 | 51.7% | -1.9% |
| pass_yds under | 56 | 44.6% | -15.5% |
| rec over | 284 | 52.8% | +5.8% |
| rec under | 756 | 52.8% | +0.3% |
| rec_yds over | 201 | 46.3% | -11.9% |
| rec_yds under | 538 | 50.0% | -4.9% |
| rush_att over | 80 | 48.8% | -7.2% |
| rush_att under | 243 | 64.6% | +22.0% |
| rush_yds over | 122 | 45.1% | -12.6% |
| rush_yds under | 299 | 58.5% | +10.9% |
| edge 2-5% | 543 | 50.5% | -4.1% |
| edge 5-10% | 785 | 51.3% | -2.2% |
| edge 10%+ | 1309 | 54.6% | +4.9% |

## Unders and overs at a Kalshi-like price (no-vig + 2c fee), bootstrap by game

Weeks 1-8:

| Rule (Kalshi proxy: no-vig + 2c) | n | Win % | ROI | 95% CI |
|---|---|---|---|---|
| Every under, blind | 3,420 | 53.0% | +0.9% | -2.6% to +4.6% |
| Model under, edge >= 2% | 1,935 | 54.3% | +3.7% | -1.3% to +8.7% |
| Model under, edge >= 10% | 1,086 | 57.0% | +9.3% | +2.4% to +16.0% |
| Model under, edge >= 2%, no pass yds | 1,875 | 54.7% | +4.3% | -0.4% to +9.1% |
| pass_yds under, edge >= 2% | 60 | 43.3% | -16.6% | -42.0% to +8.1% |
| rec under, edge >= 2% | 759 | 52.8% | -0.0% | -7.8% to +7.2% |
| rec_yds under, edge >= 2% | 564 | 50.4% | -3.0% | -10.2% to +4.3% |
| rush_att under, edge >= 2% | 245 | 65.3% | +24.6% | +13.8% to +34.9% |
| rush_yds under, edge >= 2% | 307 | 58.6% | +12.4% | +1.3% to +23.1% |
| Model OVER, edge >= 2% | 764 | 49.1% | -4.4% | -13.0% to +3.7% |

Weeks 4-8:

| Rule (Kalshi proxy: no-vig + 2c) | n | Win % | ROI | 95% CI |
|---|---|---|---|---|
| Every under, blind | 2,302 | 53.7% | +2.0% | -2.3% to +6.2% |
| Model under, edge >= 2% | 1,290 | 54.8% | +4.2% | -1.8% to +10.3% |
| Model under, edge >= 10% | 715 | 58.6% | +12.2% | +4.6% to +20.0% |
| Model under, edge >= 2%, no pass yds | 1,251 | 55.3% | +5.2% | -0.8% to +11.4% |
| pass_yds under, edge >= 2% | 39 | 38.5% | -26.0% | -55.2% to +4.1% |
| rec under, edge >= 2% | 507 | 53.1% | -0.1% | -8.8% to +9.4% |
| rec_yds under, edge >= 2% | 379 | 51.2% | -1.5% | -10.2% to +7.5% |
| rush_att under, edge >= 2% | 159 | 67.9% | +28.4% | +15.7% to +40.5% |
| rush_yds under, edge >= 2% | 206 | 58.7% | +12.4% | +0.0% to +24.8% |
| Model OVER, edge >= 2% | 514 | 47.5% | -7.7% | -17.8% to +1.9% |

## What held up in BOTH seasons (2025 partly in-sample, 2026 fully out of sample)
* The closing line is more accurate than the model on every stat. A 20% model / 80% market probability blend,
  with the weight fit on 2025, still beat the market alone on 2026 (Brier 0.2474 vs 0.2483): small but real.
* Model UNDERS with edge >= 10%: +10.8% (2025) and +9.3% (2026, CI +2.4% to +16.0%).
* Model unders with edge 2-10%: about break-even. The model's stated edges are inflated (it is overconfident).
* Model OVERS lost both seasons (-6.8% and -4.4%). QB pass-yards unders lost both seasons (small samples).
* Rush-attempts unders were the strongest group both seasons (+17.6%, +24.6%). Receptions and receiving-yards unders
  were profitable in 2025 but flat in 2026: do not build a rule on them.
