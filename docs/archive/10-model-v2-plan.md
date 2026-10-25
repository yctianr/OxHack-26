# 10 · Model v2: duration, volume, placement and the 3D river map

> **Read [docs/11-system-review.md](11-system-review.md) first** for the audited data and corrected results. This file keeps the plan and decision log; where they disagree, docs/11 wins.

Written Sat 24 Oct 2026, 22:00 BST. **This supersedes parts of docs/04, 05 and 06** where they conflict (volume scope, 3D, costs). Decisions are logged in [§1](#1-decision-log) so they can be changed deliberately; the evidence behind them is in docs/11.

**One sentence:** one small, physical "bathtub" model per overflow — wet ground plus recent rain against a capacity line — gives the hourly chance of spilling, how long spills last and (at 15 works with flow data) how much spills; the same model replays four years of weather under each intervention to find where £ cuts the most harm, and a 3D map shows the result as sewage glowing down Oxford's rivers.

---

## 1. Decision log

Change a decision by editing its row (status → `changed`, date, why) and following the "touches" column. Don't silently edit downstream sections.

| ID | Decision | Chosen | Alternatives considered | Why | Touches |
| --- | --- | --- | --- | --- | --- |
| D1 | Core model | **Hourly bathtub per overflow** (§3.1): log Thames flow + one rain store, 4 params, plus 2-param daily calibration | Daily hurdle (logistic × hours); gradient boosting as main | One structure gives chance, duration, volume and what-ifs. Explains spills as well as gradient boosting on average (each wins one test year); ties it as a forecast (docs/11 §5) | everything |
| D2 | Wetness signal | **Revised 24 Oct on evidence: Thames at Farmoor for every site.** Was: nearest gauge on the same river | Per-site best gauge + ERA5 soil moisture; slow local rain store; boreholes | Per-site gauge choice gave no gain and swung yearly bias ±16%; soil moisture hurt; a modelled slow store did worse than measured flow (docs/11 §4.2). It measures seasonal catchment wetness, not groundwater | §3.1 |
| D3 | Volume scope | **~15 works with TDV + ORIC FFT**, censored regression | Oxford STW only; all 61 with formula FFT | TDV covers every Thames works > 50 m³/d (verified in the 2024/2025 files); ORIC gives installed FFT for 351 works | §3.2, §3.4, map width |
| D4 | 3D map | **Glowing rivers on LIDAR terrain** (deck.gl) | + extruded "curtain"; kernel-density heatmap; hex columns | Nothing painted off-river; colour carries magnitude; % sewage along the network appears to be unmapped (no prior map found) | §5 |
| D5 | Harm metric | **Spill volume ÷ Q30 river flow × receptor weight**, toggle to spill-hours vs 10/yr | 10/yr target count; spill-hours only | SOEP precedent for dilution; toggle covers the 46 sites without volume | §3.3, §3.4 |
| D6 | Levers | **Storage, sealing, FFT, SuDS** — each moves exactly one bathtub parameter | — | Interpretable: bigger bath, smaller leak, bigger drain, smaller tap | §3.4 |
| D7 | Area | **61 overflows within 25 km of (452000, 206000)** | Oxford city (~10); all 573 Thames | Includes the upstream works that drive Port Meadow; 49–52 have enough training data to evaluate (docs/11 §5) | data prep, map |
| D8 | Optimiser coverage (open) | **15 volume works get the full optimiser; the other 46 get sealing/SuDS what-ifs in spill-hours only** | SOEP curves at CSOs with V from formula A | No volume scale at CSOs; avoids inventing m³ | §3.4 |
| D9 | Rain input | **Inverse-distance mix of the 2 nearest audited EA 15-min gauges** | Osney for all; nearest gauge; ERA5 | Better than Osney-only on both folds; ERA5 worse (docs/11 §4.2) | §3.1 |
| D10 | Forecast mode | **Add 2 state terms: spilling at midnight, hours spilled yesterday** (forecasts only, never what-ifs) | State only (persistence); none | Beats persistence by 0.0025 Brier with CIs clear of zero; ties information-matched gradient boosting (docs/11 §5) | §3.1, swim card |
| D11 | Volume fit | **Censored (Tobit) regression on daily treated flow, truncated conditional draws, weekly bootstrap refits** | Least squares on non-spill days | Oxford STW 2024 ≈ 2,200 ML (1,800–2,500); storm tanks not yet modelled, so order of magnitude only (docs/11 §5, §7) | §3.2 |
| D12 | Adopted from the plan review | Hard-surface hectares check on β; capacity-unit ranking before £; swim risk bands vs bathing-water standards; wildlife via SOEP dilution bands; never-cut core | — | See [§3.5](#35-adopted-from-the-plan-review) | §3.3–3.5, §6 |
| — | Tested and rejected | Hinge on wetness, slow local store, season term, recency weighting, recalibration on recent data, second fast store, soil moisture, ERA5 rain | — | Inside noise or worse out of sample (docs/11 §4.2) | — |

Earlier decisions still standing (from the v1 handover, since removed): daily P(spill) as a headline output, wording ("unexplained", never "illegal"), no pipes, frozen-snapshot demo.

**Repo state (Sat 22:15):** all Thames Water alerts pulled (153,783 rows, Apr 2022 →; `fetch_data.py` now retries the empty pages the API returns under rate limiting, which used to stop it at 98k), plus events, status and every hydrology preset. `data/raw/` also holds TDV 2019–2025 (`tdv/`; direct links on the Thames Water page work with a browser user agent), ORIC FFT (`oric_fft.xlsx`) and OS Open Rivers (`os_open_rivers/`). The [plan review](09-plan-review.md) points are covered here: time step (hourly, §3.1), CSOs without capacity (dimensionless C, D8), Port Meadow upstream sources (§3.3), thin bacteria data (swim output stays assumption-driven).

---

## 2. Evidence

Moved to [docs/11-system-review.md](11-system-review.md) §2–6. The first-pass results that used to be here were scored on pre-audit labels with same-day rain, so they are not repeated.

---

## 3. Model

### 3.1 Layer 1 — the bathtub (all 61 overflows, hourly)

```
WetGround_t  = log Thames flow at Farmoor (1100TH), yesterday's daily mean    (D2)
RecentRain_t = linear reservoir of hourly rain:  F_t = a·F_{t−1} + (1−a)·τ·R_t,  a = exp(−1/τ)
Inflow_t     = DWF + α·max(0, WetGround_t − W0) + β·RecentRain_t
P(spill_t)   = σ((Inflow_t − C) / s)
```

- **Parameters per site:** α, W0, β, τ, s (C fixed: = FFT at works with flow data, = 1 elsewhere, which makes the units dimensionless there). Constrain α, β ≥ 0.
- **Fit:** Bernoulli likelihood on hourly on/off EDM labels, offline hours masked. Grid τ ∈ {3, 6, 12, 24, 48, 96, 168} h, optimise the rest with L-BFGS-B.
- **Partial pooling** for sites with few events: add λ·‖θ_i − θ_group‖² with groups = {GW-tagged, not}. λ chosen on the validation year.
- **Outputs:** hourly P → expected daily spill-hours (Σ P), P(any spill that day) = 1 − Π(1 − P), point event durations (runs of Inflow > C), and 10–90% ranges from a weekly block bootstrap of the fit.
- **Daily probability:** P(any spill on day d) = σ(c0 + c1 · max_t z_t), fitted on training days (2 params). Summing hourly P gives spill-hours; Π(1 − P) overstates the daily chance because hours are correlated.
- **Forecast mode** (D10) adds two state terms to that daily logistic: spilling at midnight, and hours spilled yesterday. It is **not** used for what-ifs, which must stay physical.
- **Rain** (D9): inverse-distance mix of the 2 nearest of 10 EA 15-min gauges (Osney, Eynsham, Wheatley, Abingdon, Bicester, Benson, Worsham, Chipping Norton, Aylesbury, Stokenchurch; `scripts/model/1_fetch_gauges.py`). Forecast rain for h > 0: Open-Meteo hourly, with its historical-forecast archive for an honest backtest.
- **Flow gauges fetched** (daily mean): Farmoor 1100TH, Cherwell 1490TH, Islip 1489TH, Evenlode Cassington 1290TH, Thame Wheatley 1980TH, Ock Abingdon 1790TH, Thames Sutton Courtenay 1800TH, Glyme Woodstock 1289TH, Ewelme 1995TH. Windrush Newbridge closed in 2023. Only Farmoor is used (D2); the rest feed the ceiling model and the river-flow scaling in §3.3.

### 3.2 Layer 2 — volume (~15 works with TDV)

Same Inflow equation, now in m³/day, fitted to treated flow:

```
TDV_d = min(Inflow_d, FFT_d) + ε        ε ~ N(0, σ²) on log scale
non-spill days:  TDV observed = Inflow           (likelihood: density)
spill days:      Inflow ≥ TDV                    (likelihood: survival function)  ← censored / Tobit
```

- **DWF** = Q80 of TDV (the EA definition; Oxford 2024 ≈ 52,800 m³/d). **FFT** = ORIC installed value, checked against the plateau on ≥ 20 h spill days; when they disagree (Witney, Standlake, Church Hanborough exceed ORIC by up to 45%), fit FFT within [ORIC, 1.5 × ORIC] and report it.
- **Censored fit (D11)**: `scripts/model/7_volume_oxford.py`. Results and remaining gaps in docs/11 §5 and §7.
- The volume estimate moves several-fold with the fitting method, so the published range must include **structural** uncertainty (method choice), not only the bootstrap.
- Fit **jointly** with the hourly on/off likelihood from 3.1, so timing and units agree. Daily excess → hours in proportion to hourly (Inflow_t − C).
- **Storm tank:** the first V m³ of each episode is stored and returned to treatment when Inflow < FFT. Oxford ≈ 6,831 m³ (tender snippet, unverified); elsewhere the permit rule ≥ 68 L/head as a prior range.
- **Spill volume** = Σ max(0, Inflow − FFT) − tank capture. 10–90% range from bootstrap + ±8% meter error + tank prior.
- **Checks:** (1) AUC of (Inflow − FFT) for spill days without using labels; (2) excess vs observed duration rank correlation; (3) annual total under the ORIC shortfall bound (required − installed FFT) × spill-hours.
- **Works:** Oxford, Witney, Standlake, Church Hanborough, Islip, Wheatley, Cassington, Bicester, Abingdon (sum 2 columns), Didcot, Woodstock, Stanton Harcourt, Culham, Carterton, Benson (names change between years; normalise). Not in TDV: Kidlington, Eynsham (probably drain to Oxford/Cassington).
- **Label everywhere:** "model estimate, not measured".

### 3.3 Layer 3 — where it goes (river propagation and harm)

- **Network:** OS Open Rivers `watercourse_link` (in `data/raw/os_open_rivers/`, about 528 links in the box). Reverse links with `flow_direction = 'in opposite direction'`; drop `form = 'canal'`; split load equally at bifurcations (braided Thames, mill streams).
- **Snap** each overflow to the nearest link within 250 m whose `watercourse_name` matches `receivingWaterCourse` where possible; log mismatches.
- **% sewage in the river** on each link and day = Σ upstream spill volume ÷ (river flow × 86,400). River flow = nearest gauge on that river × (upstream length ratio). No decay: volume is conserved.
- **Port Meadow / E. coli**: the same walk with die-off exp(−ln10 · t / T90), T90 ≈ 10 h, t = length ÷ 0.4 m/s (both assumptions, on screen).
- **Harm per overflow** (D5) = annual spill volume ÷ Q30 at the outfall × receptor weight (3 bathing water or within 24 h upstream of one; 2 SSSI/SAC — Port Meadow is part of Oxford Meadows SAC; 1 other). Toggle: spill-hours × weight, for all 61.

### 3.4 Layer 4 — placement

Replay hourly weather Oct 2022 → Oct 2026 through the fitted bathtubs with one parameter changed:

| Lever | Parameter change | Cost (central, range) | Basis |
| --- | --- | --- | --- |
| Storage +V m³ | Tank V in Layer 2 | £2,000/m³ (1,850–2,935) | Ofwat PR24 FD |
| Sealing fraction x of high-risk sewers | α × (1 − e·x), e ∈ [0.2, 0.6] | £175k/km (100–250k); length = 6.3 m/PE × 49% high-risk | Southern/SWW evidence; Oxford GISMP (1,485 km, 231 km high-risk) |
| FFT +q l/s | C + q | £100k per l/s (Witney £16m / 159 l/s) | Thames Water Witney scheme |
| SuDS −A ha hard surface | β × (1 − A/A_total), A_total from β in m³/mm | £1.25m/ha (1.0–1.5m) | SOEP |

- For each site build a benefit curve (harm avoided per year vs £), take its **upper concave envelope**, fund greedily by marginal harm-per-£, then confirm with an exact multiple-choice knapsack (15 sites × ~30 options: trivial DP). Greedy is optimal for separable concave curves; dilution harm is additive across sites.
- **Outputs:** the £ → harm-avoided frontier; a ranked table (site, lever, size, £, spill-hours avoided, m³ avoided, harm avoided, £ per unit harm); wet-year (WY2024) vs dry-year (WY2025) robustness.
- **Headline comparison:** simulate **Thames Water's plan** (Oxford FFT 1,040 → 1,434 l/s + tanks 6,831 → 18,167 m³ for > £270m by 2032; Witney 240 → 399 l/s, done 2026; Cassington 2028) and show what the same budget buys under our allocation.
- **Expected story (to test, not assume):** at wet-ground sites, storage fills on day one of a multi-day episode, so sealing and FFT should beat tanks. SOEP curves assume rain-driven spills and would miss this.
- Witney's 2026 FFT upgrade sits inside the test window: model it as a step change in C and check the residuals around it.

### 3.5 Adopted from the plan review

From [docs/09-plan-review.md](09-plan-review.md) (D12). Its other points were already covered, and two did not survive checking: groundwater boreholes as the main signal (weakest signal in our data), and "storm discharge volumes" on the Thames Water page (only spill durations and treated volume are published there).

1. **β as hard-surface area.** β converts mm of rain into m³ at works with TDV. Express it as effective hectares (β ÷ 10 per mm) and check it against the urban area mapped in each works' catchment (OSM buildings + roads within the indicative catchment). A free sanity check, and it gives the SuDS lever a physical basis.
2. **Rank by spill-hours avoided per unit of capacity first, £ second.** Show "+1,000 m³ storage / +10% FFT / −20% infiltration buys X spill-hours" per works, which does not depend on cost assumptions. Then show the £ frontier as the second view.
3. **Swim output as risk bands, never "safe".** Convert % sewage at Port Meadow to an E. coli estimate with an assumed storm-sewage concentration (on screen), compare with the inland bathing-water standards (Excellent ≤ 500, Good ≤ 1,000 cfu/100 ml E. coli as 95th percentiles; Sufficient ≤ 900 as 90th), and label it a risk level driven by assumptions. About 20 samples a year allow a sanity check, not calibration.
4. **Wildlife: one closing section, no model.** Use SOEP's dilution-to-status bands on numbers we already compute: spill ÷ Q30 ≤ 0.10 High, ≤ 0.15 Good, ≤ 0.20 Moderate, ≤ 0.30 Poor, > 0.30 Bad. Mention ammonia, low oxygen and fish kills qualitatively.
5. **A complete core that is never cut:** clean data, the backtest table, the bathtub, and the capacity comparison, frozen by mid-morning before map polish.

---

## 4. Validation (pre-registered)

Hold-out: WY2025 (dry) and WY2026 to date, reported separately, plus the live 19–24 Oct 2026 event. Never split randomly.

| Output | Metric | Baselines | Target |
| --- | --- | --- | --- |
| P(spill day) | Brier skill, log loss, AUC, PR-AUC, reliability with bin counts | climatology, persistence, **information-matched gradient boosting** | Explain and Forecast scored separately; Forecast must beat persistence (met), onset days reported separately. Results: docs/11 §5 |
| Spill-hours | daily MAE, total and per-site yearly bias | site mean, persistence | Per-site yearly spill-hours are the weak point (median error 35%); report what-ifs as relative change. Results: docs/11 §5 |
| Event duration | Spearman, 80% interval coverage, tail vs Weibull (Lipp & Dobson β ≈ 0.26 for Thames) | site median | Spearman ≥ 0.6; coverage 75–85% |
| Volume | label-free AUC; plateau; shortfall bound | — | AUC ≥ 0.95; inside the bound |
| D2 check | correlation of the rain-only slow store with river flow | — | report it |

Fixes tried for the probability drift (docs/11 §4.2): local rain helped; hinge, recency weighting and recalibration on recent data did not. Still to try: let C step at known upgrades (Witney 2026, Islip 2023).

---

## 5. 3D river map (D4)

Pure **deck.gl 9.4.0** (`https://cdn.jsdelivr.net/npm/deck.gl@9.4.0/dist.min.js` exports everything needed). deck.gl layers don't drape onto MapLibre terrain, so bake heights in Python.

| Layer | deck.gl | Encoding |
| --- | --- | --- |
| Terrain | `TerrainLayer`, local Terrarium PNG from the EA 20 m DTM (fallback AWS Terrarium tiles, CORS open) | dark, ≤ 2× exaggeration, stated |
| Rivers | `PathLayer`, `[lon, lat, z + 4 m]` from the DTM | **colour = % sewage** (log scale, one sequential hue); **width = load** m³/day |
| Flow | `TripsLayer` | particles timed by travel time; day slider + play |
| Outfalls | `ScatterplotLayer` | ring by P(spill) bin (5 bins from docs/06) |
| Recommendations | `ScatterplotLayer` / `IconLayer` | distinct hue; size = harm avoided per £m; click → ranked panel |
| Labels | `TextLayer` | rivers, works |

Controls: day slider (last 60 days + 3-day forecast + named storms), 2D/3D toggle, **before/after toggle** (load arrays with the optimised portfolio; `transitions` so rivers visibly cool), camera presets (overview, city, Port Meadow, Cherwell), legend with units, tooltips with numbers and ranges. Set `loadOptions: {terrain: {worker: false}}` for artifact hosting.

The supporting views from docs/06 stay, below the map: overflow × day matrix, reliability diagram, the £ frontier.

---

## 6. Build order (code freeze Sun 14:00)

With two people, split modelling (A) and product (B) from the start; B can work from a stub JSON.

| When | A: modelling | B: product | Done when |
| --- | --- | --- | --- |
| Sat 22:30 – 00:30 | `sites.py` registry for the 61 sites (permit, x/y, gauge, TDV column, ORIC FFT, PE); fetch extra rain + flow gauges; TDV 2022–23 | `prep_rivers.py`: graph, snapping, densify, bake z; `make_heightmap.py` | site-hour table; river GeoJSON with z |
| 00:30 – 01:30 | `bathtub.py` fit + backtest harness, all sites | deck.gl shell: terrain + rivers + stub data | metrics table vs today's numbers |
| 01:30 – 06:30 | sleep (clocks go back at 02:00: +1 h) | sleep | |
| 06:30 – 09:00 | calibration fixes; LightGBM ceiling; duration intervals | TripsLayer, slider, outfalls, legend | skill table + reliability |
| 09:00 – 10:30 | `volume.py` Tobit, 15 works, ranges | propagation → per-link daily % sewage | volume table with checks |
| 10:30 – 12:30 | `placement.py`: levers, curves, greedy + DP, TW plan | recommendations layer, before/after, frontier chart | frontier + ranked table on the page |
| 12:30 – 13:30 | live 19–24 Oct test; export JSON snapshot | camera presets, polish, frozen snapshot default | demo runs offline |
| 14:00 | **freeze** | | |

**Never cut (§3.5):** data, backtest table, bathtub, capacity comparison.

**Cut order if behind:** SuDS lever → TripsLayer particles → CSO what-ifs (D8) → forecast mode h > 0. Never cut: backtest table, volume ranges, the honest labels.

**Files**

```
src/spillcast/sites.py       61-site registry and gauge assignment
src/spillcast/prep.py        site-hour and site-day tables (Europe/London, offline masked)
src/spillcast/bathtub.py     fit / simulate / what-if
src/spillcast/volume.py      censored inflow fit, tank, ranges
src/spillcast/backtest.py    metrics, reliability, figures
src/spillcast/rivers.py      OS Open Rivers graph, propagation, harm
src/spillcast/placement.py   levers, costs, envelopes, greedy + DP
src/spillcast/export.py      web/data/*.json snapshot
web/index.html               deck.gl map + supporting charts
```

---

## 7. Risks

1. **Calibration drift wet → dry year.** Already visible (skill 0.45). Recalibrate per site; report wet and dry separately.
2. **FFT disagreement** (TDV exceeds ORIC at small works): fit FFT within a bound; show both.
3. **Volume is unvalidated against measured spills** — nobody measures it (Defra, Dec 2025). Label-free checks + ranges only.
4. **Sealing effectiveness is uncertain** (20–60%); show the lever's range on the frontier, not a point.
5. **Snapping errors** on Oxford's braided channels: check every snapped outfall by eye against the sewagemap trace.
6. **Thames Water terms**: the Thames API is not OGL; ship derived numbers, not raw dumps.
7. **TDV column names change between years** (e.g. `ABINGDON STW2` vs `ABINGDON STW (2)`; `DATE` vs `Date`; sheet names differ). Normalise before joining. All of 2019–2025 is in `data/raw/tdv/`.

## Sources added in this round

- ORIC FFT dataset: https://oxfordrivers.ceh.ac.uk/data/ORIC_Thames_Sewage_Works_Capacity_Final.xlsx
- TDV: https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data
- SOEP: https://assets.publishing.service.gov.uk/media/6182bad4e90e07197867ecd4/storm-overflows-evidence-project.pdf
- Thames Water site plans (Oxford > £270m, 2032): https://www.thameswater.co.uk/about-us/performance/river-health/frequently-asked-questions/information-about-specific-sites
- Oxford STW report (FFT 1,040 → 1,434 l/s): https://www.thameswater.co.uk/media-library/l52df1pb/oxford-stw-report.pdf
- Thames Water PR24 overflow method: https://www.thameswater.co.uk/media-library/ijdgc5al/tms-dd-104-pr24-winep-ec-supporting-evidence-storm-overflow-assessment-methodology.pdf
- SOAF 2025: https://www.gov.uk/government/publications/storm-overflow-assessment-framework-2025/storm-overflow-assessment-framework-2025
- WWCompose (npj Clean Water 2026): https://doi.org/10.1038/s41545-026-00630-2
- Lipp & Dobson, spill duration scaling: https://eartharxiv.org/repository/object/11110/download/20250/
- Hammond et al. 2021: https://nora.nerc.ac.uk/id/eprint/529883/1/N529883JA.pdf
- HydroWASTE (dilution along rivers): https://essd.copernicus.org/articles/14/559/2022/
- deck.gl terrain extension limits: https://deck.gl/docs/api-reference/extensions/terrain-extension
- OS Open Rivers download: https://api.os.uk/downloads/v1/products/OpenRivers/downloads?area=GB&format=GeoPackage&redirect
