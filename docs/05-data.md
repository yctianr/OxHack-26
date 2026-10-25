# 05 · Data: what we use, where it comes from, and what each part of Spillcast reads

Updated Sun 25 Oct 2026. Plain-language guide to every dataset behind Spillcast. The script that produces each file is named next to it. The raw and cleaned data are **not in git** (`data/` is git-ignored, ~460 MB, and Thames Water's terms are not an open licence); the [rebuild section](#rebuilding-the-data) shows how to get it back. The website's own data (`web/data/`, `web/watchlist/`) **is** in git, so the site runs without any of this.

## The short version

Everything comes from free, public sources:

1. **When overflows spilled:** Thames Water's spill monitors (start and stop times), checked against Thames Water's official yearly totals.
2. **The weather and the rivers:** Environment Agency rain gauges (every 15 minutes) and river-flow gauges (daily), plus daily evaporation from Open-Meteo.
3. **What each sewage works treated and is permitted to treat:** Thames Water's daily treated volumes, and the Oxford Rivers Improvement Campaign's sheet of each works' permitted flow (FFT).
4. **The map:** OS Open Rivers for the river network, and EA LIDAR plus open terrain tiles for the 3D ground.

We checked all of it before modelling. Most of it is good, but we found and fixed real problems: some spill monitors' records disagree badly with Thames Water's own totals, some rain gauges were blocked for months, river-flow values were dated so that the model could peek hours ahead, and some works' treated-flow records have meter faults. The cleaned versions live in `data/interim/`.

```
 RAW (data/raw)                  CHECK + CLEAN                     MODELS                              WEBSITE (web/, in git)
 ──────────────                  ─────────────                     ──────                              ──────────────────────
 Treated volume (TW) ─────┐
 Permitted flow (ORIC) ───┤
 Evaporation (Open-Meteo) ┼──► 8_wb_prep.py ─────────────────► PHYSICS MODEL, main (9, 10) ──┬──► physics.json, watchlist/data.json,
 Storm tanks (tanks.csv) ─┤      wb_works, wb_tdv                 water balance per works       │    stats.json
 Rain gauges (EA, 10) ────┤                                                                     │
 Flow gauges (EA, 10) ────┼──► 3_audit.py, 4_build_clean.py ──► statistical backup (5, 6) ─────┴──► outfalls.json, whatif.json
 Spill alerts (TW) ───────┤      labels_clean, inputs_clean
 Annual spill totals (TW) ┘
 OS Open Rivers, LIDAR, terrain tiles ──► scripts/web/rivers, terrain, texture ──────────────────────► rivers.json, elevation.png,
                                                                                                       terrain.jpg (3D map)
```

Rain and river flow are cleaned once (`4_build_clean.py`) and used by both models. Spill records are scored against by both, but only the statistical backup is fitted to them.

## Which data feeds which part

| Dataset | Physics model (main) | Statistical backup | Watchlist | Website |
| --- | --- | --- | --- | --- |
| Treated volume (1.6) | what it is fitted to; capacity; error size | | treated flow on all-day spill days (Test A) | "Inspect works" chart |
| Permitted flow, ORIC (1.7) | starting value and bounds for foul flow; independent checks | | the 80% screen (Test A) | FFT in the evidence file |
| Storm-tank volumes (1.10) | tank size at 5 works (2 h at capacity elsewhere) | | | tank and its source on each card |
| Evaporation (1.8) | soil-moisture store | | | in-browser rain what-if |
| Rain gauges (1.4) | yes, two nearest gauges per works | yes, same two gauges | | rain sliders |
| River flow, Farmoor (1.5) | river-driven infiltration (18 of 52 works) | how wet the catchment is | | in-browser rain what-if |
| Other 9 flow gauges (1.5) | | only the gradient-boosting comparison | | |
| Spill alerts (1.1) | scoring only, never fitted | labels it learns from | spill hours per day; unexplained days (Test B) | "What happened" view |
| Overflow list (1.2) | | locations | | marker positions |
| Annual returns (1.3) | | data check; groundwater check | asset type, Thames Water's stated reason, investigation status | names, rivers, overflow types |
| OS Open Rivers, LIDAR, terrain tiles (1.9) | | | river route of each lead | rivers, terrain, flow paths, river glow |

---

## Part 1 · Raw data

Everything here is exactly as downloaded, in `data/raw/`.

### 1.1 Spill alerts: *when overflows spilled*

| | |
| --- | --- |
| **What it is** | Every alert from Thames Water's spill monitors (EDM, "event duration monitoring"): a **Start** when an overflow begins discharging, a **Stop** when it ends, and **Offline start / stop** when the monitor isn't working |
| **Source** | Thames Water open data API, `api.thameswater.co.uk/opendata/v2/discharge/alerts` (no key needed) |
| **Files** | `thames_alerts.csv` (all alerts) → paired by `scripts/fetch_data.py events` into `events.csv` (one row per spill) and `offline.csv` (one row per monitor outage) |
| **Coverage** | 1 Apr 2022 → 24 Oct 2026; 544 overflows across the Thames Water region |
| **Size** | 153,783 alerts → 74,435 spills (30 still running at download) and 2,438 outages |
| **Columns** | site name, permit number (the ID that links to other datasets), grid reference, receiving river, alert type, date-time |
| **Watch out for** | Times are UK local clock time with no time zone (they jump at the clock changes). Monitors can be triggered by things other than sewage (Thames Water: "even the movement of a weed"), so a "spill" is a monitor activation, not a confirmed discharge |

### 1.2 Overflow list: *where the overflows are*

| | |
| --- | --- |
| **What it is** | A snapshot of all 573 Thames Water spill monitors: name, permit number, location, receiving river, current status |
| **Source / file** | Thames Water API `/discharge/status` → `thames_status.csv` |
| **Used for** | Locations. We cover the **61 overflows within 25 km of central Oxford** (`sites61.csv`): 54 at sewage works, 4 at pumping stations, 2 in the sewer network, 1 unknown |

### 1.3 Official annual spill returns: *the independent check, and Thames Water's own explanations*

| | |
| --- | --- |
| **What it is** | Thames Water's official yearly return to the regulator, one row per overflow: total spill hours and count, how much of the year the monitor worked, overflow type (storm tank at a works, inlet overflow, pumping station, network), and for high-spilling sites the stated reason, investigation activity and improvement activity |
| **Source** | Thames Water [storm discharge and flow data](https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data) page (Excel), downloaded by hand |
| **Files** | `annual_returns/tw_edm_2023.xlsx`, `tw_edm_2024.xlsx`, `tw_edm_2025.xlsx` (Thames Water-only sheets, headers on row 6) |
| **Used for** | Checking our spill hours site by site (2024, 2025); testing whether the model's "groundwater" signal matches Thames Water's "GW inundation" tag; site names, receiving rivers and overflow types on the map; the watchlist's "Thames Water's stated reason and investigation status" (2025) |

### 1.4 Rain: *how much rain fell, every 15 minutes*

| | |
| --- | --- |
| **What it is** | Rainfall every 15 minutes at 10 Environment Agency gauges around Oxford |
| **Source** | EA Hydrology API (open licence), fetched by `scripts/model/1_fetch_gauges.py` |
| **Files** | `gauges/rain_<gauge ID>.csv`, about 168,700 readings each, 2 Jan 2022 → 24 Oct 2026 |
| **Gauges** | Osney Lock (256230TP), Eynsham (254336TP), Wheatley (263541TP), Abingdon (261021TP), Bicester (259110TP), Benson (264254TP), Worsham (253861TP), Chipping Norton (254829TP), Aylesbury (261923TP), Stokenchurch (274178TP) |
| **How it's used** | Each overflow gets an inverse-distance mix of its two nearest gauges (`site_inputs.csv`). Both models and the rain scenarios page use this same mix |
| **Watch out for** | Each reading has a quality flag. Some gauges flag a lot of readings **"Suspect"**: Worsham 57%, Osney 43%. At some gauges Suspect readings are far too low (blocked gauge) |

### 1.5 River flow: *how full the rivers are, daily*

| | |
| --- | --- |
| **What it is** | Daily average river flow (m³ per second) at 10 EA gauges |
| **Source** | EA Hydrology API (open licence), fetched by `1_fetch_gauges.py` |
| **Files** | `gauges/flow_<gauge ID>.csv`, about 1,750 days each, 2 Jan 2022 → 23 Oct 2026 |
| **Gauges** | **Thames at Farmoor (1100TH): the one both models use**, as a measure of how wet the catchment is. The other nine (Cherwell at Oxford 1490TH, Ray/Cherwell at Islip 1489TH, Evenlode at Cassington 1290TH, Thame at Wheatley 1980TH, Ock at Abingdon 1790TH, Thames at Sutton Courtenay 1800TH, Glyme at Woodstock 1289TH, Ewelme Brook 1995TH, Windrush at Newbridge 1090_w1TH, closed Oct 2023) are only offered to the gradient-boosting comparison |
| **Watch out for** | A "daily" value dated 2 Jan covers **09:00 on 2 Jan to 09:00 on 3 Jan** (the EA "water day"). Quality varies: Farmoor 95% "Good"; Glyme at Woodstock 54% "Suspect" |

### 1.6 Treated volume: *how much sewage each works treated, daily*

| | |
| --- | --- |
| **What it is** | Total volume treated per day (m³) at every Thames Water sewage works treating over 50 m³/day ("TDV", total daily volume). This is what was **treated**, measured at the outlet, not what spilled |
| **Source** | Thames Water storm discharge and flow data page (Excel, one file per year), downloaded by hand |
| **Files** | `tdv/tdv2019.xlsx` … `tdv2025.xlsx` (277–299 works per year; 2026 not yet published) |
| **Used for** | The water balance is fitted to it (2019–2025). The watchlist compares it with each works' permitted flow on all-day spill days (Apr 2022 → Dec 2025). The website uses the 2024 mean as each works' size when weighting the river glow. Oxford STW's spill-volume estimate (`7_volume_oxford.py`) |
| **Watch out for** | Column names change between years (e.g. `ABINGDON STW2` vs `ABINGDON STW (2)`; Abingdon has two outlets, which we sum). "Suspect" values are marked only by cell colour. Some meters log runs of zeros or impossible spikes (Carterton: 28 million m³ in a day) |

### 1.7 Permitted flow (FFT) and capacity: *how much each works should treat*

| | |
| --- | --- |
| **What it is** | For 351 Thames Water works, sheet "Required capacities": permitted flow to full treatment (FFT, litres per second), maximum infiltration allowance, flow per person, population equivalent, trade flow, and the FFT the works should have under the regulator's formula |
| **Source** | Oxford Rivers Improvement Campaign / UKCEH, from a Thames Water information request (June 2024): [ORIC capacity sheet](https://oxfordrivers.ceh.ac.uk/data/ORIC_Thames_Sewage_Works_Capacity_Final.xlsx) |
| **File** | `oric_fft.xlsx` |
| **Used for** | The watchlist's permit screen (treated flow under 80% of FFT on all-day spill days); FFT and population in each works' evidence file; the water balance's foul-flow and infiltration checks; Oxford STW's capacity (1,040 L/s) in the volume estimate |
| **Watch out for** | Two works have no published FFT (Tackley, Worminghall). The water balance doesn't use FFT as its capacity: it uses the 95th percentile of each works' own treated flow, because published FFT is off by 13% typically. **Licence not yet checked** (see Licences) |

### 1.8 Evaporation: *how fast the ground dries out*

| | |
| --- | --- |
| **What it is** | Daily FAO reference evapotranspiration (and rain) at one point in central Oxford (51.75 N, 1.26 W), 1 Jan 2022 → 22 Oct 2026 |
| **Source** | Open-Meteo historical weather API (ERA5 reanalysis), fetched automatically by `8_wb_prep.py` if the file is missing |
| **File** | `openmeteo/et0_oxford_daily.csv` |
| **Used for** | The water balance's soil-moisture store, which decides when ground is saturated and starts running off into the sewers. Only the evaporation column is used; rain comes from the EA gauges |

### 1.8b Weather forecast: *the next 7 days*

| | |
| --- | --- |
| **What it is** | Hourly precipitation from all 51 members of the ECMWF IFS 0.25° ensemble at each of the 10 EA gauge locations; daily FAO reference evaporation for Oxford |
| **Source** | Open-Meteo [ensemble API](https://open-meteo.com/en/docs/ensemble-api) and [forecast API](https://open-meteo.com/en/docs), fetched live by `scripts/model/11_forecast.py` (CC BY 4.0; ECMWF open data, CC BY 4.0) |
| **Used for** | The physics model's 7-day forecast ([02-physical-model.md](02-physical-model.md#forecast)); not stored in `data/raw` |

### 1.9 Map data: *rivers and terrain for the 3D map*

| Data | Source | File | Used for |
| --- | --- | --- | --- |
| **OS Open Rivers** | Ordnance Survey (open licence), GeoPackage for Great Britain | `os_open_rivers/oprvrs_gb.gpkg` (113 MB) | The river network: each overflow is snapped to its river and traced downstream, giving the glowing routes, the particles and each lead's "spills enter … then …" route |
| **EA LIDAR terrain (DTM 2022)** | EA LIDAR Composite DTM via WCS, `scripts/fetch_data.py dtm` | `oxford_dtm_20m.tif` (central 22 × 18 km) | Fine terrain around Oxford, blended into the coarser tiles |
| **Terrain tiles** | Mapzen / AWS open terrain tiles (Terrarium format, zoom 12), fetched by `scripts/web/terrain.py` | cached in `data/raw/terrarium/` | Terrain for the rest of the map box |

### 1.10 Storm-tank volumes: *how much each works can hold back*

The physics model needs each works' storm-tank volume. No dataset gives it in bulk, so `scripts/model/tanks.csv` holds every volume a source states, with the source and a quote; elsewhere the model uses the design rule of 2 hours at capacity.

| Works | Tank (m³) | Model's 2 h rule (m³) | Source |
| --- | --- | --- | --- |
| Oxford | 6,831 (18,167 tendered) | — | [Find a Tender notice 2024/S 000-031739](https://www.find-tender.service.gov.uk/Notice/031739-2024), Thames Water, Oct 2024 |
| Witney | 2,201 actual (permit 1,728) | 2,067 | [Hammond et al. 2021](https://doi.org/10.1038/s41545-021-00108-3), Table 1, "WWTP2" |
| Church Hanborough | 359 actual (permit 364) | 422 | Hammond et al. 2021, Table 1, "WWTP1" |
| Carterton | 900 | 828 | [Written evidence WQR0020](https://committees.parliament.uk/writtenevidence/22257/html/) to the Environmental Audit Committee, Feb 2021 |
| Bampton | 173 | 160 | Same, Table 3 |

- Hammond et al. keep the works anonymous; WWTP1/2 are identified by their stated permitted flows (50.52 and 240 L/s), which match Church Hanborough and Witney exactly.
- The two Witney sources disagree: WQR0020 gives 1,728 m³ as "actual", which equals 2 h at 240 L/s, so it is probably the permitted figure. Witney's 2026 upgrade may have changed it.
- Where checked, the 2-hour rule is within 6–18% of the real tank.
- **Not usable:** the EA's "Consented Discharges to Controlled Waters with Conditions" has no tank field, and its licence forbids publishing. The route to the other 48 works is an Environmental Information Regulations request to Thames Water, which is how both sources above got theirs.

### 1.11 Downloaded but not used

| Data | File(s) | Why it's here |
| --- | --- | --- |
| ERA5-Land soil moisture and ERA5 rain (Open-Meteo, 26 grid cells) | `openmeteo/era5land_*.csv` | Tested as alternatives to the gauges; both did worse, so dropped |
| Early single-gauge downloads (Osney daily rain, Oxford and Horspath boreholes, Cherwell / Kings Mill / Osney / Sandford levels) | `hydro_*.csv` | First exploration; the borehole turned out to be the weakest signal |
| Oxford-only alerts | `thames_alerts_oxford.csv` | First exploration; superseded by the full download |
| LIDAR at 100 m | `oxford_dtm_100m.tif` | Superseded by the 20 m file |

### 1.12 Teammates' datasets in git (not read by the pipeline)

These are committed in the repo, outside `data/`, with their own cleaning scripts. Nothing in `scripts/model/` or `scripts/web/` reads them, so they serve as cross-checks, not inputs.

| Folder | What it is | Cleaning script |
| --- | --- | --- |
| `edm_datasets/` | EA annual EDM returns for all companies, 2020–2025, and an Oxford extract (`oxford/`) | `scripts/clean_edm.py` |
| `tdv_datasets/` | The same Thames Water TDV files as 1.6 (`raw/`), and an Oxford extract with meter-fault flags (`oxford/`) | `scripts/clean_tdv.py` |
| `Rainfall Data/` | Daily qualified rainfall at Abingdon, Eynsham, Osney Lock and Wheatley | none |

Their file names differ from what our scripts expect (`data/raw/tdv/tdv{YEAR}.xlsx`, and `data/raw/annual_returns/tw_edm_{YEAR}.xlsx`, a Thames Water-only sheet), so copying them across needs renaming. The daily rainfall comes from the same EA gauges as 1.4, which we use at 15 minutes.

---

## Part 2 · What the checks found

### 2.1 Spills, rain and river flow (`scripts/model/3_audit.py`)

| Data | What we found | What we did |
| --- | --- | --- |
| **Spill alerts vs official totals** | For a typical site our hours match Thames Water's official total to within 0.1% (75% of sites within ±5% in 2024, 87% in 2025). But **13 site-years are badly wrong**: four sites (Didcot, Charlton-on-Otmoor, Middleton Stoney, Weston-on-the-Green pumping station) have official hours but **no alerts at all** in the feed; Chalgrove's feed has 7% of its official hours; Islip's has double | Those 13 site-years are excluded |
| **Spill alerts: chatter** | 16% of spills last under 15 minutes; 42% of gaps between spills are under an hour | Doesn't affect hourly data; merged for any count of "events" |
| **Spill alerts: very long spills** | 155 spills over a week, 14 over a month (longest: South Leigh, 54 days in 2026) | Kept: groundwater-fed works genuinely spill for weeks |
| **Spill alerts: pairing** | 22 odd sequences in 34,000 alerts for our 61 sites (e.g. two Starts in a row) | Too few to matter; noted |
| **Rain** | Suspect readings at some gauges far too low; Benson read 557 mm in 2024 when its neighbours read ~950 mm; missing rain was being treated as "no rain" | Suspect → missing; days far from the neighbouring gauges → missing; gaps filled from the other gauges |
| **River flow** | Each daily value covers 09:00 to 09:00 the next day, so using "yesterday's" value let the model see up to 9 hours into the future | Each value only used 12 hours after its 24-hour window ends |

### 2.2 Treated flow (`scripts/model/8_wb_prep.py`)

Each spill-monitored works is matched to its treated-volume column and its ORIC row by name (with a few hand fixes, e.g. Middleton Stoney is "MIDDLETON STONY" in the TDV files). Zeros and days above 10× the works' median are treated as missing. Then each works' flow record is checked against its spill record. Spill records are used here only to judge the data, never to fit the water balance.

| Verdict | Works | Meaning |
| --- | --- | --- |
| Good | 40 | Passes every check |
| Groundwater-led | 3 (Cholsey, Dorchester, South Moreton) | Flow follows groundwater, not rain |
| No published capacity | 2 (Tackley, Worminghall) | No FFT; capacity taken from the flow itself |
| **Check** | 7 (Appleton, Bletchingdon, Chadlington, Drayton, Middle Barton, Shabbington, Watlington) | Over 30% of days spilling 12+ hours show treated flow under 80% of capacity: a meter problem or a works not treating what it should. **Four of these are strong watchlist leads**, so the data question and the lead are the same question |
| Dropped | 1 (Middleton Stoney) | Flow data for only 26% of days |
| No treated-flow data | 8 sites | Pumping stations (Bucknell, Littlemore Low Level, Manor Farm), network overflows (The Willows, West Way, Weston-on-the-Green network overflow), Tubney, and Stanford-in-the-Vale (no unambiguous treated-volume column). Not in the water balance or the watchlist |

Oxford's treated-volume column is complete (< 1% missing every year); its peak exceeds the published FFT in some years (up to 1.23×), one reason published FFT is treated as approximate.

---

## Part 3 · Clean data and model outputs

All in `data/interim/` (not in git).

### 3.1 Clean data layer (`scripts/model/4_build_clean.py`): **what the models read**

| File | What's in it | How it was made | Size |
| --- | --- | --- | --- |
| `sites61.csv` | The 61 overflows: permit number, name, grid location, latitude/longitude | `2_sites.py`, from the alert locations | 61 rows |
| `labels_clean.pkl` | For each overflow, hour by hour (1 Apr 2022 → 24 Oct 2026, UTC): **what fraction of the hour it was spilling** (0 to 1) and **whether that hour is trustworthy** (monitor working, site-year not broken) | From `events.csv` and `offline.csv`, using exact minutes | 61 sites × 39,984 hours |
| `inputs_clean.pkl` | Hour by hour: rain at each of the 10 gauges (checked and gap-filled) and the log of river flow at each flow gauge (as known at that hour) | From the gauge files | 39,984 hours × 20 columns |
| `site_inputs.csv` | Which two rain gauges each overflow uses, and how far away they are | Nearest two gauges | 61 rows |
| `site_quality.csv` | Per overflow: which years were excluded, what share of time is trustworthy, total spill hours | From the audit | 61 rows |
| `audit_reconciliation.csv` | Per overflow and year: official spill hours vs ours, and the ratio | `3_audit.py` | 114 rows |
| `st_rainfall.json`, `st_waterFlow.json` | EA station lists (gauge locations) | `2_sites.py` | — |

**Before and after cleaning, in numbers**

| | Before | After |
| --- | --- | --- |
| Total spill-hours, 61 sites | 187,653 (each spill rounded out to whole hours) | **173,940** (exact minutes) |
| Oxford STW spill-hours, 2024 / 2025 | — | **3,200 / 590**, vs Thames Water's official 3,198 / 590.5 |
| Site-years we trust | all | all except 13 |
| Rain gauge-days removed as faulty | 0 | 47 (plus all Suspect readings) |
| Rain hours filled from neighbouring gauges | 0 (missing read as zero) | from 0.2% (Wheatley) to 55% (Worsham) of hours; Osney 41% |
| Hours where flow "knew the future" | up to 9 every morning | none |

### 3.2 Water-balance inputs (`8_wb_prep.py`)

| File | What's in it | Size |
| --- | --- | --- |
| `wb_works.csv` | One row per works: FFT, maximum infiltration, foul flow, population, required FFT (all from ORIC), treated-flow coverage, and the audit verdict (2.2) | 53 works |
| `wb_tdv.pkl` | Daily treated volume (m³/day), one column per works, faults removed | 1 Jan 2019 → 31 Dec 2025 × 53 |

### 3.3 Model outputs

| File | What's in it | Made by |
| --- | --- | --- |
| `eval_predictions.pkl` | Every test day for every overflow: what happened, and what each model predicted (Explain, Forecast, persistence, gradient boosting), for both folds | `5_evaluate.py` |
| `site_cards.csv` | Per overflow, in plain units: the river flow that triggers a spill with no rain, the rain that triggers it on a typical winter day, how long rain keeps counting, and the groundwater signature | `6_site_cards.py` |
| `wb_params.csv` | Water balance fitted per works and fold, in physical units: foul flow, peak infiltration, hard and saturated runoff areas, capacity, storm-tank volume, spill start; ORIC's figures alongside for comparison | `9_wb_fit.py` |
| `wb_predictions.pkl`, `wb_flow.pkl` | Water balance per day: chance of a spill, spill-hours and volume; simulated vs measured treated flow | `9_wb_fit.py` |
| `wb_eval_rows.pkl` | Physics and statistical model side by side on the same held-out days (the watchlist's "unexplained spill" test reads this) | `10_wb_evaluate.py` |
| `wb_*_abl_*` | Ablation runs (capacity quantile, wet-ground runoff, tank size, pump-back) | `9_wb_fit.py` with `WB_*` switches |
| `web_links.pkl`, `web_elev.npy`, `web_grid.json` | River links in the map box; blended terrain grid | `scripts/web/rivers.py`, `terrain.py` |

Other files in `data/interim/` (`inputs_hourly.pkl`, `labels_hourly*.pkl`, `exp_*.pkl`, `oxford_*.csv`, `multisite.csv`, `out_*.pkl`) come from the archived first-pass scripts in `scripts/archive/`. They use the uncleaned data and can be deleted.

### 3.4 Website data (`web/`, **in git**)

| File | What's in it | Made by |
| --- | --- | --- |
| `web/data/outfalls.json` | The 61 overflows: location, type, receiving river, downstream river links, flow path; daily Explain / Forecast chance, monitor result and spill-hours over the test year (1 Oct 2025 → 22 Oct 2026) | `scripts/web/data.py` |
| `web/data/rivers.json` | River links with names, heights and which overflows are upstream | `data.py` |
| `web/data/physics.json` | Physics model per works: daily chance, spill-hours and volume (test year); fitted parameters; start-of-day states; hourly rain, evaporation and river flow, so the page can rerun a day with different rain; river-glow scale | `physics.py` |
| `web/data/stats.json` | Scores of both models on the same held-out days; physics calibration | `build_stats.py` |
| `web/data/whatif.json` | Per overflow and day: the statistical backup's rain response | `whatif.py` |
| `web/data/elevation.png`, `terrain.jpg` | 3D terrain (heights encoded as colours) and its shaded texture | `terrain.py`, `texture.py` |
| `web/watchlist/data.json` | The regulator watchlist: per works, the lead level, findings, dates, Thames Water's stated reason and investigation status, and **daily treated flow and spill-hours, Apr 2022 → Dec 2025** | `watchlist.py` |

---

## Rebuilding the data

From the repo root, after `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (the map scripts also need `pip install pyproj rasterio pillow`):

```bash
# 1. Downloads
python scripts/fetch_data.py thames-alerts      # ~10 min; all spill alerts
python scripts/fetch_data.py events             # pair alerts into spills and outages
python scripts/fetch_data.py thames-status      # overflow list
python scripts/model/1_fetch_gauges.py          # 10 rain + 10 flow gauges
python scripts/fetch_data.py dtm --res 20       # EA LIDAR for the 3D map
# by hand: TDV files -> data/raw/tdv/tdvYEAR.xlsx, annual returns -> data/raw/annual_returns/tw_edm_YEAR.xlsx,
#          ORIC capacity sheet -> data/raw/oric_fft.xlsx, OS Open Rivers GeoPackage -> data/raw/os_open_rivers/oprvrs_gb.gpkg

# 2. Clean data and the statistical model
python scripts/model/2_sites.py                 # the 61 sites and EA station lists
python scripts/model/3_audit.py                 # checks; writes audit_reconciliation.csv
python scripts/model/4_build_clean.py           # clean data layer
python scripts/model/5_evaluate.py              # backtest -> eval_predictions.pkl
python scripts/model/6_site_cards.py            # site cards

# 3. Water balance (evaporation is fetched here if missing)
python scripts/model/8_wb_prep.py
python scripts/model/9_wb_fit.py                # ~75 s on 8 processes
python scripts/model/10_wb_evaluate.py

# 4. Website data
python scripts/web/rivers.py
python scripts/web/terrain.py                   # fetches terrain tiles if not cached
python scripts/web/texture.py
python scripts/web/data.py
python scripts/web/build_stats.py
python scripts/web/watchlist.py
python scripts/web/whatif.py
python scripts/web/physics.py
```

Order matters: `watchlist.py` and `build_stats.py` need `10_wb_evaluate.py`; `whatif.py` and `physics.py` need `data.py`. Hand downloads: Thames Water [storm discharge and flow data](https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data) (TDV and annual returns; direct file links work with a browser user agent), the [ORIC capacity sheet](https://oxfordrivers.ceh.ac.uk/data/ORIC_Thames_Sewage_Works_Capacity_Final.xlsx), and [OS Open Rivers](https://osdatahub.os.uk/downloads/open/OpenRivers).

**One end date:** `DATA_END` in `scripts/model/common.py` (now 2026-10-24 23:00 UTC) sets the last hour of observed data for `4_build_clean.py`, the fold B test window and the evaporation download in `8_wb_prep.py`. Move it and rerun to extend everything; the forecast (`11_forecast.py`) starts the hour after it.

## Licences and what we publish

| Source | Licence | Credit |
| --- | --- | --- |
| Environment Agency (rain, flow, LIDAR) | Open Government Licence | "© Environment Agency copyright and/or database right" |
| Ordnance Survey Open Rivers | Open Government Licence | "Contains OS data © Crown copyright and database right" |
| Open-Meteo (evaporation) | CC BY 4.0 | "Weather data by Open-Meteo.com" |
| Terrain tiles (Mapzen / AWS) | Open; attribution to the underlying sources | "Terrain tiles from Mapzen / AWS" |
| Thames Water (alerts, annual returns, TDV) | [Thames Water's own terms](https://data.thameswater.co.uk/s/terms-of-service), not an open licence | Publish derived results, not the raw files |
| ORIC capacity sheet | **Not yet checked** | Oxford Rivers Improvement Campaign / UKCEH |
| Tank volumes (1.10) | Find a Tender: Open Government Licence; Hammond et al.: open access (CC BY); WQR0020: Open Parliament Licence | Cite each source |

What the public website republishes, worth checking before it goes live:
- **Thames Water:** `web/watchlist/data.json` contains each works' **daily treated flow** (converted to L/s) and daily spill-hours, which are close to the raw files; `outfalls.json` contains daily monitor results. Thames Water publishes all of this itself, but it is more than a "derived result". If in doubt, cut the watchlist chart to spill days only.
- **ORIC:** FFT and population per works appear in the watchlist. Check the licence before publicising.

## Glossary

| Term | Meaning |
| --- | --- |
| **Storm overflow** | A relief point where a sewer or sewage works discharges diluted sewage into a river when it is overloaded |
| **STW / WwTW** | Sewage (wastewater) treatment works |
| **CSO** | Combined sewer overflow: an overflow out in the sewer network rather than at a works |
| **EDM** | Event duration monitoring: the sensor that logs when an overflow starts and stops |
| **Permit number** | The Environment Agency's ID for each discharge (e.g. Oxford STW = TEMP.2827); the key that joins datasets |
| **TDV** | Total daily volume treated at a works (m³/day), measured at the outlet |
| **FFT** | Flow to full treatment: the flow a works is permitted to and must treat before it may spill. Compliance: 95% of readings above 92% of FFT while spilling |
| **MON3 / MON4** | The operator's overflow monitor and its 15-minute FFT flow monitor; the records that settle a watchlist lead |
| **Population equivalent (PE)** | Size of a works in "people's worth" of sewage |
| **Water day** | The EA's day for river flow: 09:00 to 09:00 |
| **"Suspect" flag** | The EA's marker that a reading may be wrong |
| **Site-year** | One overflow's record for one calendar year |
| **Fold A / B** | The two held-out test periods: A = Oct 2024 → Sep 2025, B = Oct 2025 → 24 Oct 2026 |
