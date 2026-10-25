# 02 · Physical model: a water balance of each works (main model)

Spillcast's main model simulates each sewage treatment works hour by hour as plumbing. Water arrives from homes, hard surfaces, saturated ground and groundwater. The works treats up to its capacity, a storm tank holds the excess, and only what the tank can't hold spills to the river.

It is fitted to each works' measured **daily treated flow**, never to its spill records. Every fitted number is in physical units and is checked against published figures. It runs at 52 works around Oxford: every works with a usable treated-flow record.

Code: `scripts/model/wb.py` (the model), `8_wb_prep.py` (inputs and flow audit), `9_wb_fit.py` (fitting), `10_wb_evaluate.py` (scoring), `scripts/model/tanks.csv` (sourced storm-tank volumes), `scripts/web/physics.py` (export for the website).

## How it works

```
 Rain (EA) ───────┬──► hard surfaces (A) ───────────────────────────┐
                  ├──► soil moisture D ──► runoff once wet (As) ─────┤
 Evaporation ─────┘          │ surplus                               │
 (Open-Meteo)                ▼                                       ├──► SEWER INFLOW ──► works treats up to C ──► treated effluent
 River flow (EA) ┄┄┄┄┄┄► groundwater G ──► infiltration ────────────┤        │                                   (measured daily: TDV)
                                                                     │        └─► excess ─► storm tank V ─► full ─► SPILL to river
 Population, trade (ORIC) ──► foul flow F ──────────────────────────┘                    ◄── pumped back ──┘      (logged by EDM)
```

## Each hour, step by step

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
   - V is the volume a source states for that works ([05-data.md §1.10](05-data.md#110-storm-tank-volumes-how-much-each-works-can-hold-back): Oxford, Witney, Church Hanborough, Carterton, Bampton) and otherwise the design rule of 2 hours at capacity.
   - Spilling starts only when the works is at capacity and its tank is full, as the permit requires. Nothing about where spilling starts is learned from spill records.

### What is fitted (fold B, median and interquartile range)

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

## Data

| Data | Publisher | Resolution and period | What it drives |
| --- | --- | --- | --- |
| Rainfall, 10 gauges | Environment Agency, [Hydrology API](https://environment.data.gov.uk/hydrology/) (OGL) | 15-minute, 2022 → 24 Oct 2026; two nearest gauges per works | Soil, runoff, groundwater |
| Thames flow at Farmoor (1100TH) | Environment Agency, Hydrology API (OGL) | Daily mean, used only after it is published | River-driven infiltration |
| Reference evaporation | [Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api) (ERA5, CC BY 4.0) | Daily, central Oxford | Soil drying |
| Treated volume (TDV) | Thames Water, [storm discharge and flow data](https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data) | Daily m³, 2019–2025 | What it is fitted to; capacity; error size |
| Capacity sheet (FFT, population, trade, max infiltration) | [ORIC / UKCEH](https://oxfordrivers.ceh.ac.uk/data/ORIC_Thames_Sewage_Works_Capacity_Final.xlsx), from a Thames Water information request | One row per works | Foul-flow starting value; independent checks |
| Storm-tank volumes | `scripts/model/tanks.csv` (tender notice, Hammond et al. 2021, Parliament evidence) | 5 works | Tank size |
| Spill alerts (EDM) | Thames Water open data API | Start and stop times | Scoring only |

Cleaning (Suspect rain dropped, gaps filled; meter faults in treated flow removed; the flow-data audit) is in [05-data.md](05-data.md).

## Fitting

1. **Training days:** every day with a treated-volume reading before the fold's cut-off (30 Sep 2024 for fold A, 30 Sep 2025 for fold B), after a warm-up year and 60 days of spin-up. At least 300 days.
2. **Matched quantity:** log of simulated daily treated flow against log of the measured value, so a 10% miss counts the same at every size of works. Robust least squares from several starting points, both infiltration versions.
3. **Days at capacity are censored.** At 90%+ of capacity the meter can't show more than the works treated, so the day only says "inflow was at least this much"; the fit is penalised only if simulated inflow falls short.
4. **Result:** median error 8% on training days, 12% on days it never saw (fold B).

## From one run to a chance of spilling

The chance of a spill comes from 200 runs per works with realistic errors in inflow. The error's size (typically 13%) and day-to-day persistence (correlation 0.78) come from the fit's misses on days below capacity. Each day's outputs: chance of any spill (share of runs that spill), expected spill-hours, and expected spill volume in m³.

## Checks: do the fitted numbers mean what they say?

Fitted only to treated flow, the model lands within about 20% of independent published figures.

| Quantity | Model (fold A / B) | Independent figure |
| --- | --- | --- |
| Foul flow per person | 156 / 163 L/person/day | 1.17× ORIC's population-based figure (fold B) |
| Capacity vs published permitted flow (FFT) | 1.04 / 1.07× | ORIC sheet |
| Capacity vs treated flow on all-day spill days | within ~6% | Thames Water TDV and EDM |
| Peak infiltration vs Thames Water's maximum infiltration allowance | median 1.05 / 1.07× (48 works); rank correlation 0.58 / 0.55 after dividing by capacity | ORIC sheet |
| 2-hour tank rule vs real tanks | 2,067 vs 2,201 (Witney), 422 vs 359 (Church Hanborough), 828 vs 900 (Carterton), 160 vs 173 (Bampton) m³ | [05-data.md §1.10](05-data.md#110-storm-tank-volumes-how-much-each-works-can-hold-back); the model now uses the real volumes |

## How well it predicts

Same held-out works and days for every row (fold B: Oct 2025 – 22 Oct 2026; fold A in brackets).

| Model | Brier | Skill vs climatology | Median AUC per works |
| --- | --- | --- | --- |
| **Physics water balance** (never sees a spill record) | 0.061 (0.076) | 0.47 (0.33) | 0.96 (0.91) |
| Statistical model, given the rain that fell | 0.047 (0.052) | 0.59 (0.54) | 0.98 (0.97) |
| Statistical forecast, knows if spilling at midnight | 0.029 (0.034) | 0.75 (0.70) | 0.98 (0.95) |
| Same as yesterday | 0.032 (0.036) | 0.72 (0.68) | 0.90 (0.86) |

- Physics ranks spill days almost as well as a model fitted to spill records, without ever seeing one. That is the strongest evidence the plumbing is right.
- **Spill-hours are undercounted by 30%** (median per works-year; typical error 58%). Daily treated flow stops rising at capacity, so the model never sees how far inflow overshot, and that overshoot sets how long a spill lasts.
- Errors run both ways per works: Witney's spill-hours are about 2.6× too high, Oxford's about 2.7× too low.

## Spill volume

Each works' daily spill volume (m³) is the ensemble mean of water spilled beyond a full tank. Test-year total: about 2.2 million m³ across 52 works (largest: Bicester, Witney, Oxford, Wantage). It is the model's weakest output: no public data measures spill volume, and volume depends on exactly the overshoot that daily data can't see. Use it to **rank works**, not as an amount. The website shows it per works and uses it for the river glow ([06-website.md](06-website.md)).

## Why no learned "spill start"

An earlier version learned, per works, the inflow at which spilling starts, by matching spill records. It improved scores (skill 0.59 in fold B) but was rejected:

- It absorbs every error at once (missing peaks, tank size, missed rain, faulty monitors), so it means nothing physical. Didcot, whose monitor sends no alerts, got the lowest allowed value and "spilled" 92% of the year.
- It hides what the watchlist looks for: a works that really spills early just gets a low threshold.
- It made volumes arbitrary (Oxford 0.30 vs 1.58 million m³ a year).

`9_wb_fit.py` still computes it (`wb_*` columns) as a diagnostic; nothing in Spillcast uses it. The physics-only outputs are the `wb1_*` columns.

## Limits

| Limit | Effect | Fix |
| --- | --- | --- |
| Treated flow is daily and stops at capacity | Spill-hours undercounted; hard surface and travel time unidentifiable | Operators' 15-minute flow (MON4), by information request |
| Storm tanks sourced at 5 of 52 works | Elsewhere a design rule (within 6–18% where checked) | EIR request to Thames Water for all permits |
| Treated flow is measured at the outlet | Outlet losses blur the inflow | Inlet flow (MON4) |
| Rain from two gauges, evaporation from one point | Local storms missed | Radar rainfall |
| It fits whatever the meter reports | At the 7 works whose flow data is marked "check", a faulty meter and real under-treatment look the same | Inspect the meter: that is what the watchlist asks for |
| Works only | 8 of 61 overflows (pumping stations, network) outside it; the statistical backup covers them | Sewer-network flow data |
| Treated volume published to Dec 2025 | 2026 fit can't be checked against treated flow | Thames Water's 2026 file |
