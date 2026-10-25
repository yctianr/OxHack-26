# 04 · Modelling plan

Three outputs, in priority order. Each has its own validation; don't ship an output you can't test.

1. **P(spill on day d+h)** for every overflow, h = 0, 1, 2 days. Labels are observed (EDM start/stop).
2. **Duration**: expected spill-hours, with a range. Labels are observed.
3. **Volume**, Oxford STW only: estimated ML with a wide range. **Not observed anywhere.** Validate indirectly.

Why chance works without volume: the model only needs to learn *when* inflow crosses capacity, and that crossing is labelled every day. Yes/no labels can't fix the *scale*: doubling all inflows and the capacity gives the same spill days but twice the volume. Durations add some magnitude information, and daily treated-flow data (TDV) adds real units at Oxford STW.

---

## Target and cleaning

- **Site-day table:**
  - `y = 1` if any Start–Stop interval overlaps day d (Europe/London calendar day).
  - `hours` = overlap hours that day.
  - `event_hours` = total length of the event that started that day.
- **Offline periods → missing**, not dry. Drop site-days with < 90% monitor uptime (mirrors the EA's `edmOperationPercent`).
- Merge events separated by < 15 min (sensor chatter). Drop zero-length pairs. Cap open-ended Starts at the next Offline or Start.
- **Sanity check:** per-site annual hours must match the EA return (Oxford STW 2025: 590 h vs 590.5 h). Counts won't match, because the EA uses the 12-24 rule.
- **Localise** API datetimes as Europe/London before converting to UTC.

## Features (known at forecast time; no leakage)

- **Rain:**
  - Daily totals at lags 0–3 and the max 1-h intensity.
  - **Antecedent precipitation index** API_k(t) = k·API_k(t−1) + R(t), with k ∈ {0.85, 0.95}.
  - For h > 0, use *forecast* rain: archived NWP forecasts (e.g. Open-Meteo's historical-forecast API; check its terms), so the backtest only uses what was knowable at the time.
- **Groundwater / wetness state:**
  - Cherwell at Oxford 1490TH level and flow.
  - Kings Mill 1491TH.
  - Thames flow at Farmoor 1100TH.
  - Each as a level relative to its own percentiles, plus 7- and 14-day changes, plus a **slow component** (14-day rolling minimum).
  - Oxford borehole SP50_72 level and its 14-day change.
  - The Thames lock headwater gauges (Osney, Iffley) are held within about ±0.15 m; low value.
- **Season:** day-of-year sin/cos (an evapotranspiration proxy).
- **Static per site:** asset type, PE, `highSpillOperationalReview` tag. **Hold the GW tag out of training** if you use it for validation.

## 1. Probability models

| # | Model | Notes |
| --- | --- | --- |
| 1 | **Persistence**: P(today) = whether it spilled yesterday (calibrated) | Hard to beat at h = 0 for groundwater sites; quant judges expect it |
| 2 | **Rain threshold**: spill if R(t) > X, X tuned per site on training data only | Output the empirical frequency above and below X |
| 3 | **Physical bucket model**, per site | Equation below; about 7 parameters, maximum Bernoulli likelihood (`scipy.optimize`) |
| 4 | **LightGBM**, pooled across sites | Site ID + static covariates. Monotone (+) constraints on rain and wetness. Isotonic calibration on a held-out year. |

Bucket model:

```
Q_t      = P·G·r  +  a·max(0, h_t − h0)  +  Σ_{j=0..3} b_j·R_{t−j}
           (foul)    (infiltration)          (rain runoff)
P(spill) = σ((Q_t − C) / s)
```

- `h_t` is the wetness state (Cherwell level or flow, slow component), `h0` is the threshold at which infiltration starts, `C` is effective capacity (FFT plus tank), and `s` is a smoothness scale.
- **At Oxford STW, fit Q_t to TDV first, on dry and non-spill days, then fit only C and s on spills.** This two-stage identification gives real units and powers the volume estimate.
- Optional: a discrete-time hazard model (logistic on days since last spill + features).

## 2. Duration (all sites)

- **Hurdle decomposition:** E[hours_d] = P(spill_d) × E[hours_d | spill_d].
- **Conditional part:**
  - LightGBM quantile regression (τ = 0.1, 0.5, 0.9) on spill days only, or gamma / log-normal GLM.
  - Same features plus *event state* (already spilling yesterday? hours spilled so far in this event).
- **Expected finding:** groundwater-driven spills run for days, rain-driven ones for hours. Plot event-duration distributions by GW-tag. That's a figure judges will like.
- **Metrics:** pinball loss / CRPS vs a "site median duration" baseline, and interval coverage (does the 80% interval hold about 80%?).

## 3. Volume (Oxford STW only)

Nobody measures spill volume. Southern Water told Havant council its overflows "generally do not have flow meters" and its volumes are estimates ([source](https://havant.moderngov.co.uk/documents/s48769/SWA%20Answers%20to%20Questions%20Raised%20on%2020%20Feb%202023.pdf)). The EA returns hold counts and hours only. The method below makes volume **identifiable** at Oxford STW.

1. **Dry and non-spill days: inflow = treated flow (TDV).** Fit the bucket inflow model Q_t (foul + infiltration + rain) to TDV on those days. The coefficients are now in real ML/day.
   - Check the foul term against the EA recipe: DWF ≈ Q80 of TDV, and PG ≈ 235,046 × about 0.13–0.15 m³/day.
   - Dry-day infiltration = TDV − PG − E. Plot it against Cherwell level or flow: **the strongest single evidence slide**.
2. **Spill days: does TDV plateau?** If treated flow saturates at a ceiling on spill days, that ceiling is the effective full-treatment capacity. Treat it as **the first thing to check**.
3. **Estimated spill volume ≈ Σ over spill days (Q̂_t − TDV_t) − storm-tank volume per event.**
   - Tank volume comes from the permit if found; otherwise use a prior range from the EA rule of ≥ 68 L/head (235,046 × 68 L ≈ 16,000 m³ as an upper-end guide).
   - Treat tank refill and drain-down as returning to treatment within 1–2 days.
4. **Uncertainty:** bootstrap the inflow-model residuals by week, propagate them through, and report a 10–90% range per event and per year.
5. **Indirect validation, all on held-out years:**
   - The volume model's implied spill days must match observed spill days. If it predicts positive excess on non-spill days, it's wrong.
   - Estimated excess should rank-correlate with observed event duration.
   - The annual total should be the same order as any company estimate you can find for comparable works.
6. **Label:** "model estimate, not measured", with a range. State the extrapolation: on spill days, Q̂ is used outside the range it was fitted on.

## Evaluation (all outputs)

- **Split by time, never at random.**
  - Rolling origin by hydrological year (Oct–Sep): train 22/23 → test 23/24 (wet); train 22–24 → test 24/25 (dry).
  - Then a **live forward test on 19–24 Oct 2026**.
  - Report wet and dry separately. 2025 was dry (EA: 35% fewer spills nationally), which flatters "no spill" models.
- **Probability:**
  - Brier score and Brier skill vs climatology *and* vs persistence, plus log loss.
  - **Reliability diagram** (10 bins) **with bin counts**, ECE, and a sharpness histogram.
  - PR-AUC rather than ROC-AUC (summer spills are rare).
- **Uncertainty:** block bootstrap by week for skill-score CIs.
- **Pre-registered hypotheses** (state them before running):
  - (a) The bucket model wins at GW-tagged sites.
  - (b) The rain rule is competitive at flashy urban CSOs and in dry years.
  - (c) The fitted infiltration share ranks the 12 GW-tagged sites above the rest; report AUC.
- **Swim flag:** score against E. coli > 900 cfu/100 ml in May–Sep samples (about 20 per season), vs the EA STP flag. Report counts honestly.

## Unexplained-spill detector

- Flag spills with model P < 2%, rain ≤ 0.25 mm on days t and t−1 (Thames Water's own dry-day definition), and no wetness rise.
- Rank them by surprise, −log p.
- The EA treats dry-weather operation as unsatisfactory, so this has regulatory meaning.
- Call them "leads to check", never "illegal". Top of the Poops already does a rain-based version; ours is model-based and calibrated.

## Population and foul flow

- G is about 133 L/head/day (Thames Water WRMP, 2030). Return-to-sewer of about 95% is an industry convention (not verified).
- Trade effluent E = annual billing ÷ 303 days (not public, so fold it into a fitted constant).
- Growth: scale PG by ONS 2022-based projections.
- Diurnal patterns only matter at sub-daily resolution; skip them.
