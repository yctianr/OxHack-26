# The model

Spillcast has two models. The **physics water balance** is the main one: it is never fitted to spill records, so it can judge whether a works spills when it shouldn't. The **statistical model** is the backup, used where physics can't run or can't answer ([below](#statistical-backup)).

## Physics water balance

The main model simulates each sewage treatment works hour by hour as plumbing. Water arrives from homes, hard surfaces, saturated ground and groundwater. The works treats up to its capacity, a storm tank holds the excess, and only what the tank can't hold spills to the river.

It is fitted to each works' measured **daily treated flow**, never to its spill records. Every fitted number is in physical units and is checked against published figures. It runs at 52 works around Oxford: every works with a usable treated-flow record.

Code: `scripts/model/wb.py` (the model), `06_wb_prep.py` (inputs and flow audit), `07_wb_fit.py` (fitting), `08_wb_evaluate.py` (scoring), `09_forecast.py` (forecast), `tanks.csv` (sourced storm-tank volumes), `scripts/web/physics.py` (export for the website).

### How it works

```
 Rain (EA) ───────┬──► hard surfaces (A) ───────────────────────────┐
                  ├──► soil moisture D ──► runoff once wet (As) ─────┤
 Evaporation ─────┘          │ surplus                               │
 (Open-Meteo)                ▼                                       ├──► SEWER INFLOW ──► works treats up to C ──► treated effluent
 River flow (EA) ┄┄┄┄┄┄► groundwater G ──► infiltration ────────────┤        │                                   (measured daily: TDV)
                                                                     │        └─► excess ─► storm tank V ─► full ─► SPILL to river
 Population, trade (ORIC) ──► foul flow F ──────────────────────────┘                    ◄── pumped back ──┘      (logged by EDM)
```

### Each hour, step by step

All flows in m³ per hour. **Bold** symbols are fitted per works; everything else is data or fixed.

1. **Foul flow**, sewage from homes and businesses: `foul = F × (1 + 0.3·cos(2π(h − 12)/24))`, a ±30% daily cycle peaking at noon (h = local hour). Daily totals can't reveal the cycle, so its shape is fixed. Data: ORIC sheet (population, flow per person, trade flow) sets F's starting value and bounds.
2. **Soil moisture**, how wet the ground is: `D ← D + PET·(1 − D/Dmax) − rain`, kept between 0 and **Dmax**; `wet = 1 − D/Dmax`. Rain fills the soil, evaporation (PET) empties it, more slowly as it dries. Rain that falls on saturated soil (D = 0) is surplus, which recharges groundwater. Data: EA rain; Open-Meteo reference evaporation (daily, spread over the hours).
3. **Runoff**, rain that reaches the sewers: rain is smoothed over **τf** hours (sewer travel time), then `runoff = 10 × (A + As·wet) × smoothed rain` (1 mm on 1 ha = 10 m³). **A** is hard surface that always drains; **As** is permeable land that drains only as it saturates, so the same storm sends far more water in a wet winter than after a dry summer.
4. **Infiltration**, groundwater leaking into the pipes. Two versions; the one that matches treated flow better is kept per works:
   - *Groundwater store* (34 of 52 works): surplus rain fills a store **G** that drains over **τg** days; `infiltration = k·G`.
   - *River flow* (18 of 52 works): `infiltration = k·max(0, Q − q0)`, with Q the Thames flow at Farmoor (EA, m³/s) as a measure of how high groundwater is.
5. **Treatment, storm tank, spill.** Inflow = foul + infiltration + runoff.
   - **Capacity C**, the most the works treats in a storm, is the 95th percentile of its own daily treated flow on training days. Measured, not fitted.
   - Above C, the excess fills the **storm tank V**. Once the tank is full, the rest **spills**. When inflow drops, the tank is pumped back for treatment.
   - V is the volume a source states for that works ([data.md §1.10](data.md#110-storm-tank-volumes-how-much-each-works-can-hold-back): Oxford, Witney, Church Hanborough, Carterton, Bampton) and otherwise the design rule of 2 hours at capacity.
   - Spilling starts only when the works is at capacity and its tank is full, as the permit requires. Nothing about where spilling starts is learned from spill records.

#### What is fitted (fold B, median and interquartile range)

| Parameter | Meaning | Allowed range | Fitted |
| --- | --- | --- | --- |
| F | Foul flow | 0.2–5× ORIC's figure | 163 L/person/day; 1.17× ORIC |
| Dmax | Soil-moisture capacity | 20–300 mm | 123 mm (49–182) |
| A | Hard surface draining to the sewer | from 0.01 ha | ~0.01 ha: at its floor at most works |
| As | Land that drains when saturated | up to 50,000 ha | 4.7 ha (2.6–16) |
| τf | Sewer travel time | 1–12 h | 12 h: at its cap at most works |
| k, τg | Groundwater store | τg 3–365 days | τg 44 days (11–84) |
| k, q0 | River-driven infiltration | q0 up to 4× median flow | q0 0.28 m³/s, far below normal flow |
| C | Capacity (measured) | — | 1.07× published permitted flow |

Two parameters sit at their bounds, and that is informative: on daily data nearly all storm water looks like wet-ground runoff (A at its floor), and sewer travel time can't be resolved (τf at its cap). Capping τf at 3 h or 1.5 h made the model worse (skill 0.47 → 0.39 → 0.34 in fold B), so the 12 h fit stands.

### Data

| Data | Publisher | Resolution and period | What it drives |
| --- | --- | --- | --- |
| Rainfall, 10 gauges | Environment Agency, [Hydrology API](https://environment.data.gov.uk/hydrology/) | 15-minute, 2022 → 24 Oct 2026; two nearest gauges per works | Soil, runoff, groundwater |
| Thames flow at Farmoor (1100TH) | Environment Agency, Hydrology API | Daily mean, used only after it is published | River-driven infiltration |
| Reference evaporation | [Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api) (ERA5) | Daily, central Oxford | Soil drying |
| Treated volume (TDV) | Thames Water, [storm discharge and flow data](https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data) | Daily m³, 2019–2025 | What it is fitted to; capacity; error size |
| Capacity sheet (FFT, population, trade, max infiltration) | [ORIC / UKCEH](https://oxfordrivers.ceh.ac.uk/data/ORIC_Thames_Sewage_Works_Capacity_Final.xlsx), from a Thames Water information request | One row per works | Foul-flow starting value; independent checks |
| Storm-tank volumes | `scripts/model/tanks.csv` (tender notice, Hammond et al. 2021, Parliament evidence) | 5 works | Tank size |
| Spill alerts (EDM) | Thames Water open data API | Start and stop times | Scoring only |

Cleaning (Suspect rain dropped, gaps filled; meter faults in treated flow removed; the flow-data audit) is in [data.md](data.md).

### Fitting

1. **Training days:** every day with a treated-volume reading before the fold's cut-off (30 Sep 2024 for fold A, 30 Sep 2025 for fold B), after a warm-up year and 60 days of spin-up. At least 300 days.
2. **Matched quantity:** log of simulated daily treated flow against log of the measured value, so a 10% miss counts the same at every size of works. Robust least squares from several starting points, both infiltration versions.
3. **Days at capacity are censored.** At 90%+ of capacity the meter can't show more than the works treated, so the day only says "inflow was at least this much"; the fit is penalised only if simulated inflow falls short.
4. **Result:** median error 8% on training days, 12% on days it never saw (fold B).

### From one run to a chance of spilling

The chance of a spill comes from 200 runs per works with realistic errors in inflow. The error's size (typically 13%) and day-to-day persistence (correlation 0.78) come from the fit's misses on days below capacity. Each day's outputs: chance of any spill (share of runs that spill), expected spill-hours, and expected spill volume in m³.

### Checks: do the fitted numbers mean what they say?

Fitted only to treated flow, the model lands within about 20% of independent published figures.

| Quantity | Model (fold A / B) | Independent figure |
| --- | --- | --- |
| Foul flow per person | 156 / 163 L/person/day | 1.17× ORIC's population-based figure (fold B) |
| Capacity vs published permitted flow (FFT) | 1.04 / 1.07× | ORIC sheet |
| Capacity vs treated flow on all-day spill days | within ~6% | Thames Water TDV and EDM |
| Peak infiltration vs Thames Water's maximum infiltration allowance | median 1.05 / 1.07× (48 works); rank correlation 0.58 / 0.55 after dividing by capacity | ORIC sheet |
| 2-hour tank rule vs real tanks | 2,067 vs 2,201 (Witney), 422 vs 359 (Church Hanborough), 828 vs 900 (Carterton), 160 vs 173 (Bampton) m³ | [data.md §1.10](data.md#110-storm-tank-volumes-how-much-each-works-can-hold-back); the model now uses the real volumes |

### How well it predicts

Same held-out works and days for every row (fold B: Oct 2025 – 24 Oct 2026; fold A in brackets).

| Model | Brier | Skill vs climatology | Median AUC per works |
| --- | --- | --- | --- |
| **Physics water balance** (never sees a spill record) | 0.061 (0.076) | 0.47 (0.33) | 0.96 (0.90) |
| Statistical model, given the rain that fell | 0.048 (0.052) | 0.58 (0.54) | 0.98 (0.97) |
| Statistical forecast, knows if spilling at midnight | 0.030 (0.034) | 0.74 (0.70) | 0.97 (0.95) |
| Same as yesterday | 0.032 (0.036) | 0.72 (0.68) | 0.90 (0.86) |

- Physics ranks spill days almost as well as a model fitted to spill records, without ever seeing one. That is the strongest evidence the plumbing is right.
- **Spill-hours are undercounted by 27%** (median per works-year; typical error 58%). Daily treated flow stops rising at capacity, so the model never sees how far inflow overshot, and that overshoot sets how long a spill lasts.
- Errors run both ways per works: Witney's spill-hours are about 2.6× too high, Oxford's about 2.7× too low.

### Live test: the 23–24 Oct storm

Scored after the fact on two days neither model had seen, with the rain that fell (physics: 49 works; statistical: 52 overflows).

| Day | Monitors | Physics: expected spills / caught at ≥50% / false alarms | Statistical: same | Statistical forecast (no rain forecast) |
| --- | --- | --- | --- | --- |
| 23 Oct, the storm | 16 spilled, 116 h | 16.2 / 10 of 16 / 5 | 11.3 / 8 of 16 / 1 | 2.6 expected; caught 1 of 16 |
| 24 Oct, the day after | 3 spilled, 15 h | 12.0 / 3 of 3 / 8 | 15.2 / 3 of 3 / 12 | 7.4 expected; caught 1 of 3 |

- **On the storm day the physics model got the total right** (16.2 expected, 16 spilled) and caught more spills than the statistical model.
- **It missed Oxford** (8 h spilled, 0% chance): Oxford's spill-hours run about 2.7× under the model in general.
- **The day after, it kept works spilling that had stopped** (103 model spill-hours vs 15): the storm tanks and saturated ground drain faster in reality than in the model.
- **Without rain, a forecast is blind to storms:** the midnight statistical forecast caught 1 of 16. That is why the physics forecast below runs on forecast rain.

### Forecast

`scripts/model/09_forecast.py` runs every works 7 days past the end of the observed data:

- **Rain:** all 51 members of the ECMWF IFS 0.25° ensemble ([Open-Meteo ensemble API](https://open-meteo.com/en/docs/ensemble-api)), hourly, at each EA rain gauge, mixed per works exactly as the observed rain is.
- **Evaporation:** Open-Meteo's daily FAO reference evaporation forecast for Oxford.
- **River flow:** Thames at Farmoor held at its last reading (only the 18 river-driven works use it).
- **Starting state:** each works' soil, groundwater, routed rain and storm tank at the end of the observed data.
- **Runs:** 4 inflow-error runs per rain member, 204 per works. The chance of a spill is the share that spill; spill-hours and volume are their means. So the chance carries both the weather uncertainty and the model's own.

The first forecast (issued 25 Oct, 10:45 UTC) has 13 works likely to spill today as they drain after the storm, 2 on 26 and 27 Oct, and none from 29 Oct on a mostly dry week. It hasn't been scored yet: the 25–31 Oct monitor records will be the first true forecast test. The river map shows it as the last 7 days of its day slider; [the README](../README.md#rebuild) says how to refresh it.

### Spill volume

Each works' daily spill volume (m³) is the ensemble mean of water spilled beyond a full tank. Test-year total: about 2.2 million m³ across 52 works (largest: Bicester, Witney, Oxford, Wantage). It is the model's weakest output: no public data measures spill volume, and volume depends on exactly the overshoot that daily data can't see. Use it to **rank works**, not as an amount. The river map uses it, divided by spill-hours, as each works' spill rate for [water quality](water-quality.md).

### Why no learned "spill start"

An earlier version learned, per works, the inflow at which spilling starts, by matching spill records. It improved scores (skill 0.59 in fold B) but was rejected:

- It absorbs every error at once (missing peaks, tank size, missed rain, faulty monitors), so it means nothing physical. Didcot, whose monitor sends no alerts, got the lowest allowed value and "spilled" 92% of the year.
- It hides what the watchlist looks for: a works that really spills early just gets a low threshold.
- It made volumes arbitrary (Oxford 0.30 vs 1.58 million m³ a year).

`07_wb_fit.py` still computes it (`wb_*` columns) as a diagnostic; nothing in Spillcast uses it. The physics-only outputs are the `wb1_*` columns.

### Design choices

- **Capacity is the 95th percentile of the works' own treated flow,** not the published permitted flow (off by 13% typically) or the 99th percentile (18% high).
- **Storm tanks:** a sourced volume where one exists (`tanks.csv`), else 2 hours at capacity.
- **No knob tuned to spill records.** Any new parameter needs a physical source.
- **Spill volumes rank works; they are not amounts.** No public data measures them.

### Limits

| Limit | Effect | Fix |
| --- | --- | --- |
| Treated flow is daily and stops at capacity | Spill-hours undercounted; hard surface and travel time unidentifiable | Operators' 15-minute flow (MON4), by information request |
| Storm tanks sourced at 5 of 52 works | Elsewhere a design rule (within 6–18% where checked) | EIR request to Thames Water for all permits |
| Treated flow is measured at the outlet | Outlet losses blur the inflow | Inlet flow (MON4) |
| Rain from two gauges, evaporation from one point | Local storms missed | Radar rainfall |
| It fits whatever the meter reports | At the 7 works whose flow data is marked "check", a faulty meter and real under-treatment look the same | Inspect the meter: that is what the watchlist asks for |
| Works only | 8 of 61 overflows (pumping stations, network) outside it; the statistical backup covers them | Sewer-network flow data |
| Treated volume published to Dec 2025 | 2026 fit can't be checked against treated flow | Thames Water's 2026 file |

## Statistical backup

The statistical model covers what physics can't:

- **Overflows with no treated-flow data** (pumping stations and network overflows), where the water balance has nothing to fit to.
- **A second opinion.** A spill day counts as unexplained only if *both* models gave it under 5% chance ([watchlist.md](watchlist.md)).
- **A next-day forecast without a rain forecast.** Standing at midnight, it knows whether the overflow is already spilling.

It predicts spill days slightly better than physics (skill 0.58 vs 0.47) because it is fitted to spill records. For the same reason it is the wrong tool for judging whether a works spills when it shouldn't: it learns each works' habits, including bad ones.

Code: `scripts/model/04_stat_evaluate.py` and `05_site_cards.py`, shared code in `common.py`.

### Structure

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

### Two tasks, never mixed

- **Explain:** given the rain that fell, how likely was a spill? Used for the unexplained-spill test.
- **Forecast:** standing at 00:00 with no rain forecast.

### Results

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

The physics model is compared with this one on the same days [above](#how-well-it-predicts).

### Site cards (`05_site_cards.py`)

Each fit in plain units: the Farmoor flow that triggers a spill with no rain, the rain that triggers one at median winter flow, τ, and the wet-ground share. Examples: Standlake spills on wet ground alone through most winters (flow trigger 34 m³/s); Oxford STW needs 118 m³/s or about 11 mm of stored rain; Thame is rain-driven.

**Checked against an independent label:** the wet-ground share separates Thames Water's "GW inundation" sites only weakly (AUC 0.57), so Farmoor flow measures seasonal wetness, not groundwater. A label-only signature, the share of spill-hours in unbroken episodes over 72 h, does better (AUC 0.80).

### Tried and dropped

| Addition | Result |
| --- | --- |
| Hinge on flow | Inside noise both years |
| Slow local rain store instead of Farmoor flow | Worse (Brier 0.053 → 0.063) |
| Per-site choice among 9 flow gauges, ERA5 soil moisture | No gain |
| ERA5 reanalysis rain | Worse than gauges |
| Season term, recency weighting, recalibration, a second fast store | Inside noise |
