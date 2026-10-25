# 11 · System review: first principles, from the data up

Written Sat 24 Oct 2026, ~23:30 BST, after an audit of every input and an independent code review. **Where this disagrees with docs/10, this wins.** Scripts: `scripts/model/` (run in order 1 → 7; shared code in `common.py`). Pre-audit exploration is kept in `scripts/archive/` only as the record behind the rejected variants in §4.2.

**Verdict.** The earlier work compared models before auditing the data, scored "forecasts" with rain that hadn't fallen yet, and claimed parity with gradient boosting more strongly than the evidence allows. Rebuilt from a cleaned data layer, with an evaluation that separates explaining from forecasting, the core conclusion survives in a more honest form:

- A **3-input physical model** (river flow, a rain store, a capacity threshold) explains spills as well as gradient boosting on average. Each wins one test year, by significant but small margins.
- As a **forecast**, it beats persistence significantly and ties an information-matched gradient-boosting model.
- Its weak point is the **onset of a spill** when no rain forecast is used. Fetching rain forecasts is the next step.

---

## 0. Principles, and where we stood

| # | Principle | Before | Now |
| --- | --- | --- | --- |
| P1 | Define the decision and target before modelling | Partly: "P(spill)" without separating explain from forecast | Two tasks, scored separately (§5) |
| P2 | Audit data and reconcile it with an independent source before modelling | **Not done** | Done: Thames Water's own EDM annual return, gauge cross-checks (§2) |
| P3 | Features use only information available at prediction time | **Violated**: same-day rain in "forecasts"; flow covered the next 9 h | Causal flow alignment; forecasts cut rain at 00:00 (§3) |
| P4 | Simplest physically motivated structure; complexity must earn its place out of sample | Mostly | Kept; additions tested with block-bootstrap CIs (§4) |
| P5 | Strong, information-matched baselines | Persistence under-used; GBM given less information than our model | Persistence is the forecast baseline; GBM matched per task (§5) |
| P6 | Honest uncertainty | Site-level resampling only; design chosen on test folds | Weekly block bootstrap; selection caveat stated; design frozen (§7) |
| P7 | Explainable: parameters in physical units, meaning validated externally | Claimed, not checked | Site cards in m³/s and mm; claimed meanings tested against an external label (§4.3) |
| P8 | Report failures as plainly as successes | Partly | §6 lists every corrected claim |

---

## 1. Layer 0 — questions and targets

| Use | Question | Target | Information allowed | Metric |
| --- | --- | --- | --- | --- |
| **Explain** (volume, what-ifs, "why did it spill") | Given the weather that fell, does the model reproduce when and how long each overflow spilled? | Any spill on day d; spill-hours per day | Observed rain and flow; **no** observed spill state | Brier, AUC, spill-hours MAE and bias |
| **Forecast** (swim card, live map) | Standing at 00:00, will it spill today? | Any spill on day d | Rain to 00:00 (later: forecast rain), published flow, current spill state | Brier vs persistence; **onset days** separately |

What-ifs must use the Explain model, because "spilling at midnight" is an outcome, not a lever.

---

## 2. Layer 1 — data audit and fixes (`3_audit.py`, `4_build_clean.py`)

| Source | Finding | Fix |
| --- | --- | --- |
| Spill events vs Thames Water's EDM annual return | Median site agrees to 0.1%; 75% (2024) and 87% (2025) of sites within ±5%. **13 site-years badly wrong**: Didcot, Charlton-on-Otmoor, Middleton Stoney and Weston PS have hundreds to thousands of reported hours but no alerts in the feed; Chalgrove 7% of reported hours; Islip 2×; Chinnor, Grendon, Cholsey off > 25% | Mask those site-years as unreliable (`site_quality.csv`) |
| Hour labels | Rounding each spill out to whole hours inflated spill-hours by 8% (174k → 188k) | Fractional hourly labels (exact minutes). Check: Oxford STW now 3,200 h (2024) and 590 h (2025) vs Thames Water's 3,198 h and 590.5 h |
| Event chatter | 16% of events < 15 min; 42% of gaps < 1 h | Irrelevant for hourly labels; merge gaps < 1 h for any event-level statistic |
| Monitoring start | Masked from a site's first spill, which drops genuine dry periods | Start at the site's first alert of any kind |
| Alert pairing | 22 anomalous transitions in 34k (repeated Start, orphan Stop, offline during a spill); 2 events in the DST fall-back hour dropped | Negligible; DST times kept (read as GMT). Fix the pairing in the real pipeline |
| Rain gauges | "Suspect" flags on 43–57% of readings at some gauges; Benson read 557 mm in 2024 vs ~950 mm nearby and its Suspect readings average 0.004 vs 0.019 mm/15 min (blocked gauge); missing rain was read as zero | Suspect → missing; gauge-days far from the neighbours' median → missing; infill from the other gauges scaled by long-run ratio; nothing read as zero |
| River flow | Daily means are stamped 09:00 and cover 09:00–09:00 the next day, so "yesterday's flow" saw up to 9 h ahead (the review confirmed it with a lead-lag test) | A value is used only 12 h after its window ends |
| Treated flow (TDV) | Oxford columns consistent 2019–25, < 1% missing; maximum exceeds the ORIC capacity in 2021 (1.23×) and 2023–25 (1.01–1.08×); "Suspect" marked only by cell colour (not read) | Fit capacity within a bound; read cell colours in the real pipeline |
| Flow gauges | Woodstock 54% Suspect, Islip 32%; Windrush closed 2023 | Only Farmoor (95% Good) is used by the model |

---

## 3. Layer 2 — features and timing rules

- **Flow:** log daily mean at Farmoor, usable 12 h after its water day ends (`FLOW_LAG_H`).
- **Rain:** inverse-distance mix of the 2 nearest audited gauges. Explain uses the full hour-by-hour series. Forecast uses the store's value at 00:00, then lets it decay.
- **State (forecast only):** spilling in the last hour of yesterday; hours spilled yesterday.
- **No** two-sided interpolation or whole-series medians: those use the future.

---

## 4. Layer 3 — model structure

### 4.1 From first principles

Sewer inflow = foul flow (roughly constant day to day) + infiltration (slow; tracks how wet the catchment is) + rain-derived inflow (fast; rain through a short store). An overflow spills when inflow exceeds pass-forward capacity plus storage. The model is the smallest version of that:

```
z_t = b0 + b1·log(Farmoor flow) + b2·F_τ(t)        F_τ = rain store (mm), time constant τ
P(spilling in hour t) = σ(z_t)                      threshold-crossing ("bathtub") model
P(any spill on day d) = σ(c0 + c1·max_t z_t)        2-parameter daily calibration
```

Four fitted parameters per site (b0, b1, b2, τ), plus two for daily calibration.

### 4.2 What was tested, and why each was kept or dropped (clean data, block-bootstrap CIs)

| Addition | Result | Decision |
| --- | --- | --- |
| Local rain (2 gauges, inverse-distance weighted) instead of Osney only | Better on both folds | **Keep** |
| Hinge on flow | A +0.0002 [−0.0002, +0.0008]; B −0.0008 [−0.0019, +0.0001] | Drop: doesn't earn its parameter |
| Slow local rain store (weeks), with or without evaporation | Worse: A Brier 0.0531 → 0.0634; replacing Farmoor with it 0.0865 | Drop: a measured river state beats a modelled one |
| Per-site choice among 9 flow gauges + ERA5 soil moisture | No gain; yearly bias swings ±16% | Drop |
| ERA5 reanalysis rain | Worse than gauges (partly a 1 h timing offset) | Drop |
| Season term, recency weighting, recalibration on recent data, second fast store | Inside noise | Drop |

### 4.3 Explainability, and what the parameters actually mean

- **Site cards** (`6_site_cards.py`) turn each fit into plain units:
  - **Flow trigger:** the Farmoor flow at which the hourly spill chance reaches 50% with no stored rain.
  - **Rain trigger:** mm in the store needed at median winter flow (40 m³/s).
  - **τ:** how long rain keeps counting.
  - Examples:
    - Standlake: flow trigger 34 m³/s, rain trigger 0 mm. It spills on wet ground alone through most winters.
    - Oxford STW: 118 m³/s or about 11 mm over ~4 days.
    - Thame: flow trigger 957 m³/s, effectively never reached. Rain-driven.
- **Checked against an independent label.** Thames Water's annual return tags 14 of the 54 modelled sites "GW inundation" (groundwater).
  - The model's wet-ground share separates them only weakly (AUC 0.57). **Farmoor flow measures seasonal catchment wetness, not groundwater**, and must be described that way.
  - A label-only signature does much better (AUC 0.80): the share of spill-hours in unbroken episodes > 72 h. It goes on the site card as the groundwater indicator.
- **Consequence for the what-ifs:** "sealing" acts on b1, which mixes infiltration with saturated-ground runoff. Show it with a wide range and say so.

---

## 5. Layer 4 — evaluation, corrected (`5_evaluate.py`)

Sites are included on training data only (49 in fold A, 52 in fold B). Brier is over all valid site-days; 95% CIs come from a weekly block bootstrap. Fold A tests the dry WY2025; fold B tests Oct 2025 → 22 Oct 2026.

| Task | Model | Fold A Brier (skill) | Fold B Brier (skill) | Median site AUC (A / B) |
| --- | --- | --- | --- | --- |
| Explain | Climatology | 0.1079 | 0.1095 | — |
| Explain | **Physics core** | **0.0496 (+0.54)** | 0.0454 (+0.58) | 0.970 / 0.977 |
| Explain | GBM, same information | 0.0538 (+0.50) | **0.0425 (+0.61)** | 0.972 / 0.979 |
| Explain | core − GBM | **−0.0042 [−0.0070, −0.0017]** | **+0.0030 [+0.0005, +0.0060]** | each wins one year |
| Forecast | Persistence (state only) | 0.0347 (+0.68) | 0.0313 (+0.71) | 0.840 / 0.900 |
| Forecast | **Physics core + state** | **0.0322 (+0.70)** | **0.0287 (+0.74)** | 0.952 / 0.970 |
| Forecast | GBM, same information | 0.0324 | 0.0288 | 0.946 / 0.964 |
| Forecast | core − persistence | **−0.0025 [−0.0036, −0.0013]** | **−0.0026 [−0.0042, −0.0009]** | |
| Forecast | core − GBM | −0.0002 [−0.0017, +0.0014] | −0.0001 [−0.0014, +0.0011] | tie |
| Onset days | Persistence | 0.0344 | 0.0319 | 0.59 / 0.62 |
| Onset days | **Physics core forecast** | **0.0318** | **0.0291** | **0.89 / 0.90** |

- **Spill-hours (Explain):** daily MAE 1.46 / 1.43 h; total bias +2% / +5%; median per-site bias −5% / −6%.
- **Calibration (both folds pooled):** Forecast is well calibrated in every bin (e.g. 0.27 forecast vs 0.28 observed; 0.99 vs 0.98). Explain is calibrated up to 0.9 but overconfident at the top (0.96 forecast vs 0.89 observed).
- **Per site:** Explain skill p10 / median / p90 = +0.16 / +0.54 / +0.73. Negative at 7 of 101 site-folds, mostly sites with almost no test-year spills (Long Crendon, Cassington, Dorchester), where climatology is near-perfect.
- **By season:** summer is nearly spill-free and easy. In winter, Explain Brier is 0.091 / 0.082 vs climatology 0.160 / 0.172. Forecast is 0.058 / 0.051 vs persistence 0.060 / 0.054, a small winter gain.
- **Annual totals per site are the weak point.**
  - Across 90 site-years with > 24 spill-hours, Explain's yearly spill-hours have a **median error of 35%**; only 37% are within ±25%. Spill-day counts are off by a median of 11 of 42 days (27%).
  - Pooled totals look fine (+2% / +5%) only because site errors cancel.
  - Oxford STW in fold B: 1,659 h predicted vs 1,012 h observed (+64%).
  - Consequence: what-ifs should be reported as **relative change under the same model** (Δ%, with ranges), not absolute spill-hours. Year-to-year shifts in each site's threshold (asset changes, refits) are the first thing to investigate.
- **The onset gap:**
  - 71% of spill-days were already spilling at midnight, which is why persistence is strong.
  - On onset days with no rain forecast, only 14–15% of spill-days get P > 0.5. With the rain that actually fell, 49–57% do.
  - **A rain forecast is worth up to that difference.** Fetch the Open-Meteo historical-forecast archive and score with real forecast rain.

---

## 6. Corrected claims

| Earlier claim (docs/10) | Corrected |
| --- | --- |
| "Oxford STW AUC 0.975 out of sample"; "median AUC 0.958 across 61 sites" | Explain-mode figures: same-day observed rain and slightly leaky flow. Not forecasts |
| "The 4-parameter model is at the data's ceiling / matches gradient boosting" | Explain: each wins one year, both significant. Forecast: tie. The boosting model was also untuned then |
| "Forecast mode beats gradient boosting with persistence" | Unequal comparison (we had more state). Matched: tie. It beats persistence by 0.0025 Brier, significantly |
| "Hinge rejected" | It was rejected on the wrong comparison. On clean data it's inside noise; still not adopted |
| "Inflow model never saw spill labels; AUC 0.969" (volume) | False: it was fitted on days chosen as non-spill, and scored in-sample |
| Volume 10–90% ranges | Residual noise only, wrong sampling. **Fixed** in `7_volume_oxford.py`: truncated conditional draws, weekly bootstrap refits, censoring on y > 0. Oxford STW 2024 ≈ 2,200 ML (1,800–2,500), 2025 ≈ 300 ML (220–370). Test-period check: modelled inflow separates spill days with AUC 0.98; excess vs spill-hours Spearman 0.44. Storm tanks still unmodelled, so **order of magnitude only** |
| "Fixes the dry-year spill-hours bias" | The baseline was already −2%; with exact labels the bias is +2% / +5% |
| Daily P = 1 − Π(1 − P_hourly) | Removed: hours are correlated |
| "50 sites" | 49 / 51 then; 49 / 52 now (inclusion on training data only) |
| Wet-ground share = groundwater | Not supported (AUC 0.57); use the episode signature (0.80) |

---

## 7. What happens next, in order

1. **Freeze the design** (this document). From now on the untouched test is data arriving after 22 Oct 2026, including the 23–24 Oct spills. No more variant selection on folds A/B.
2. **Forecast rain:** fetch Open-Meteo historical forecasts for the gauge locations and rescore Forecast on onset days. Report both the no-rain and forecast-rain results.
3. **Volume** (conditional draws, weekly bootstrap and y > 0 censoring are done):
   - Use FFT as the lower bound on days spilling ≥ 20 h.
   - Model storm-tank fill and pump-back explicitly, or exclude the day after each spill from the "exact" set.
   - Extend from Oxford STW to the other ~14 works with TDV.
   - Publish volume as order of magnitude with these bands.
4. **Production pipeline:** turn `4_build_clean.py` into `src/spillcast/prep.py` with the audit as automated checks that fail loudly: reconciliation within ±25% or mask, rain QC counts, flow alignment test, label-hours equal exact minutes.
5. Then placement and the 3D map as in docs/10, using the Explain model for every what-if.

Thanks to the independent review (24 Oct, 23:00), which found the same-day rain issue, the persistence result, the unequal GBM comparison and the volume sampling error.
