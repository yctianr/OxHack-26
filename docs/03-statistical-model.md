# 03 · Statistical model (backup)

The statistical model is Spillcast's **backup**. The [physics water balance](02-physical-model.md) is the main model; the statistical model is used where physics can't run or can't answer:

- **Overflows with no treated-flow data** (pumping stations and network overflows), where the water balance has nothing to fit to.
- **Forecasting.** Standing at midnight, it uses whether the overflow is already spilling, which the physics model doesn't.
- **A second opinion.** A spill day counts as unexplained only if *both* models gave it under 5% chance ([04-watchlist.md](04-watchlist.md)).

It predicts spill days slightly better than physics (skill 0.58 vs 0.47 in the latest test year) because it is fitted to spill records. That same fact makes it the wrong tool for judging whether a works spills when it shouldn't: it learns each works' habits, including bad ones.

Code: `scripts/model/1–7`, shared code in `common.py`. Full audit history: [archive/11-system-review.md](archive/11-system-review.md).

## Structure

One small logistic model per overflow, a "bathtub": it spills when recent rain on top of an already wet catchment pushes it past a threshold.

```
z_t = b0 + b1·log(Thames flow at Farmoor) + b2·F_τ(t)    F_τ = rain through a linear store (mm), time constant τ
P(spilling in hour t)   = σ(z_t)
P(any spill on day d)   = σ(c0 + c1·max_t z_t)            daily calibration
```

Four fitted parameters per overflow (b0, b1, b2, and τ chosen from 6, 12, 24, 48, 96 h) plus two for the daily calibration. Fitted by logistic regression on fractional hourly labels (exact minutes spilled), training hours only.

| Input | Source | Timing rule |
| --- | --- | --- |
| Rain | EA rain gauges, 15-minute, inverse-distance mix of the two nearest | Explain: all of the day's rain. Forecast: rain up to 00:00, then the store decays |
| Catchment wetness | EA flow, Thames at Farmoor (1100TH), log daily mean | Used only 12 h after its 09:00–09:00 day ends (it otherwise sees up to 9 h ahead) |
| Spill labels | Thames Water EDM alerts, cleaned against the annual returns | 13 broken site-years masked |
| State (forecast only) | Spilling at midnight; hours spilled yesterday | Known at 00:00 |

## Two tasks, never mixed

- **Explain:** given the rain that fell, how likely was a spill? Used for the unexplained-spill test and as the backup on the map.
- **Forecast:** standing at 00:00 with no rain forecast. This is the website's "Statistical forecast" view.

## Results

Rolling-origin folds: A trains to 30 Sep 2024 and tests Oct 2024–Sep 2025; B trains to 30 Sep 2025 and tests Oct 2025–22 Oct 2026. Overflows included on training data only (49 in A, 52 in B). Confidence intervals from a weekly block bootstrap.

| Task | Model | Brier A (skill) | Brier B (skill) | Median site AUC A / B |
| --- | --- | --- | --- | --- |
| Explain | Climatology | 0.108 | 0.110 | — |
| Explain | Statistical model | 0.050 (+0.54) | 0.045 (+0.58) | 0.970 / 0.977 |
| Explain | Gradient boosting, same information | 0.054 (+0.50) | 0.043 (+0.61) | 0.972 / 0.979 |
| Forecast | Same as yesterday | 0.035 (+0.68) | 0.031 (+0.71) | 0.840 / 0.900 |
| Forecast | Statistical model + state | 0.032 (+0.70) | 0.029 (+0.74) | 0.952 / 0.970 |
| Forecast | Gradient boosting, same information | 0.032 | 0.029 | 0.946 / 0.964 |

- **Explain vs gradient boosting:** each wins one year by a small, significant margin. **Forecast:** beats "same as yesterday" by 0.0025 Brier (significant) and ties gradient boosting.
- **Onset days** (not spilling at midnight): AUC 0.89–0.90, but without a rain forecast only 14–15% of spill days get a chance above 50%. With the rain that actually fell, 49–57% do: a rain forecast is worth up to that gap.
- **Yearly spill-hours per site are weak:** median error 35%; pooled totals look fine (+2% / +5%) only because site errors cancel.
- **Calibration:** the forecast is well calibrated in every bin; Explain is overconfident above 0.9 (0.96 said vs 0.89 observed).

The physics model is compared with this one on the same days in [02-physical-model.md](02-physical-model.md#how-well-it-predicts).

## Site cards (`6_site_cards.py`)

Each fit in plain units: the Farmoor flow that triggers a spill with no rain, the rain that triggers one at median winter flow, τ, and the wet-ground share. Examples: Standlake spills on wet ground alone through most winters (flow trigger 34 m³/s); Oxford STW needs 118 m³/s or about 11 mm of stored rain; Thame is rain-driven.

**Checked against an independent label:** the wet-ground share separates Thames Water's "GW inundation" sites only weakly (AUC 0.57), so Farmoor flow measures seasonal wetness, not groundwater. A label-only signature, the share of spill-hours in unbroken episodes over 72 h, does better (AUC 0.80).

## Tried and dropped

| Addition | Result |
| --- | --- |
| Hinge on flow | Inside noise both years |
| Slow local rain store instead of Farmoor flow | Worse (Brier 0.053 → 0.063) |
| Per-site choice among 9 flow gauges, ERA5 soil moisture | No gain |
| ERA5 reanalysis rain | Worse than gauges |
| Season term, recency weighting, recalibration, a second fast store | Inside noise |

## Corrected earlier claims

Earlier figures (archive/10) used same-day rain in "forecasts", flow that saw 9 h ahead, and an unmatched gradient-boosting comparison. The numbers above replace them. The Oxford-only volume model (`7_volume_oxford.py`) is superseded by the physics model's volumes.
