# 12 · Data guide: what we downloaded, what we fixed, what the model uses

Written Sun 25 Oct 2026, ~00:30 BST. Plain-language guide to every dataset in `data/`. The code that produces each file is named next to it. None of the data is in git (`data/` is git-ignored; Thames Water's terms are not an open licence); the [last section](#rebuilding-the-data) shows how to rebuild it.

## The short version

We use three kinds of information, all free and public:

1. **When sewage overflows spilled** — Thames Water's spill monitors, which log a start and stop time each time an overflow discharges.
2. **The weather and the rivers** — rain gauges and river-flow gauges run by the Environment Agency.
3. **How much sewage the works treated** — Thames Water's daily treated-volume figures and a published list of each works' treatment capacity.

We checked all of it before modelling. Most of it is good, but we found and fixed real problems: some spill monitors' records disagree badly with Thames Water's own official totals, some rain gauges were blocked for months, and river-flow values were dated in a way that let the model peek a few hours into the future. The cleaned versions live in `data/interim/`.

```
 RAW DATA (data/raw)                       CHECKS (3_audit.py)             CLEAN DATA (data/interim)
 ───────────────────                       ──────────────────              ─────────────────────────
 Spill alerts (Thames Water) ──┐           compare with official totals    labels_clean.pkl
 Official annual spill totals ─┼─────────► flag broken site-years ───────► site_quality.csv
 Rain gauges (EA, 10) ─────────┼─────────► spot blocked / faulty gauges ─► inputs_clean.pkl  ──► model
 River flow gauges (EA, 10) ───┼─────────► fix the dating of daily flow ─┘ site_inputs.csv
 Treated volume, capacity ─────┘           (built by 4_build_clean.py)     sites61.csv
```

---

## Part 1 — Raw data

Everything here is exactly as downloaded, in `data/raw/`.

### 1.1 Spill alerts — *when overflows spilled*

| | |
| --- | --- |
| **What it is** | Every alert from Thames Water's spill monitors (called EDM, "event duration monitoring"): a **Start** when an overflow begins discharging, a **Stop** when it ends, and **Offline start / stop** when the monitor isn't working |
| **Source** | Thames Water open data API, `api.thameswater.co.uk/opendata/v2/discharge/alerts` (no key needed) |
| **Files** | `thames_alerts.csv` (all alerts) → paired by `scripts/fetch_data.py events` into `events.csv` (one row per spill) and `offline.csv` (one row per monitor outage) |
| **Coverage** | 1 Apr 2022 → 24 Oct 2026; 544 overflows across the Thames Water region |
| **Size** | 153,783 alerts → 74,435 spills (30 still running at download) and 2,438 outages |
| **Columns** | site name, permit number (the ID that links to other datasets), grid reference, receiving river, alert type, date-time |
| **Watch out for** | Times are UK local clock time with no time zone (they jump at the clock changes). Monitors can be triggered by things other than sewage (Thames Water: "even the movement of a weed"), so a "spill" is a monitor activation, not a confirmed discharge |

### 1.2 Overflow list — *where the overflows are*

| | |
| --- | --- |
| **What it is** | A snapshot of all 573 Thames Water spill monitors: name, permit number, location, receiving river, current status |
| **Source / file** | Thames Water API `/discharge/status` → `thames_status.csv` |
| **Used for** | Locations. We model the **61 overflows within 25 km of central Oxford** |

### 1.3 Official annual spill totals — *the independent check*

| | |
| --- | --- |
| **What it is** | Thames Water's official yearly return to the regulator: total spill hours per overflow, how much of the year the monitor worked, and whether the site is under review for high spilling (with a reason, e.g. "GW inundation" = groundwater) |
| **Source** | Thames Water storm discharge data page (Excel), downloaded by hand |
| **Files** | `annual_returns/tw_edm_2023.xlsx`, `tw_edm_2024.xlsx`, `tw_edm_2025.xlsx` (2024 and 2025 are used) |
| **Used for** | Checking our spill hours site by site, and testing whether the model's "groundwater" signal means what we think |

### 1.4 Rain — *how much rain fell, every 15 minutes*

| | |
| --- | --- |
| **What it is** | Rainfall every 15 minutes at 10 Environment Agency gauges around Oxford |
| **Source** | EA Hydrology API (open licence) |
| **Files** | `gauges/rain_<gauge ID>.csv` — about 168,700 readings each, 2 Jan 2022 → 24 Oct 2026 |
| **Gauges** | Osney Lock (256230TP), Eynsham (254336TP), Wheatley (263541TP), Abingdon (261021TP), Bicester (259110TP), Benson (264254TP), Worsham (253861TP), Chipping Norton (254829TP), Aylesbury (261923TP), Stokenchurch (274178TP) |
| **Watch out for** | Each reading has a quality flag. Some gauges flag a lot of readings **"Suspect"**: Worsham 57%, Osney 43%. At some gauges Suspect readings are far too low (blocked gauge) |

### 1.5 River flow — *how full the rivers are, daily*

| | |
| --- | --- |
| **What it is** | Daily average river flow (m³ per second) at 10 EA gauges |
| **Source** | EA Hydrology API (open licence) |
| **Files** | `gauges/flow_<gauge ID>.csv` — about 1,750 days each, 2 Jan 2022 → 23 Oct 2026 |
| **Gauges** | **Thames at Farmoor (1100TH) — the one the model uses**; Cherwell at Oxford (1490TH), Ray/Cherwell at Islip (1489TH), Evenlode at Cassington (1290TH), Thame at Wheatley (1980TH), Ock at Abingdon (1790TH), Thames at Sutton Courtenay (1800TH), Glyme at Woodstock (1289TH), Ewelme Brook (1995TH), Windrush at Newbridge (1090_w1TH, closed Oct 2023) |
| **Watch out for** | A "daily" value dated 2 Jan covers **09:00 on 2 Jan to 09:00 on 3 Jan**. Quality varies: Farmoor 95% "Good"; Glyme at Woodstock 54% "Suspect" |

### 1.6 Treated volume — *how much sewage each works treated, daily*

| | |
| --- | --- |
| **What it is** | Total volume treated per day (m³) at every Thames Water sewage works treating over 50 m³/day ("TDV", total daily volume). This is what was **treated**, not what spilled |
| **Source** | Thames Water storm discharge data page (Excel, one file per year), downloaded by hand |
| **Files** | `tdv/tdv2019.xlsx` … `tdv2025.xlsx` (277–299 works per year) |
| **Used for** | Estimating spill volume at Oxford STW (2022–2025) |
| **Watch out for** | Column names change between years (e.g. `ABINGDON STW2` vs `ABINGDON STW (2)`); "Suspect" values are marked only by cell colour |

### 1.7 Treatment capacity — *how much each works can treat*

| | |
| --- | --- |
| **What it is** | For 351 Thames Water works: installed capacity ("flow to full treatment", FFT, in litres per second) and the capacity they should have under the regulator's formula |
| **Source** | Oxford Rivers Improvement Campaign / UKCEH, from a Thames Water information request (June 2024) |
| **File** | `oric_fft.xlsx` |
| **Used for** | Oxford STW's capacity (1,040 l/s) in the volume estimate |

### 1.8 Downloaded but not used by the current model

| Data | File(s) | Why it's here |
| --- | --- | --- |
| ERA5-Land soil moisture and ERA5 rain (Open-Meteo, 26 grid cells) | `openmeteo/era5land_*.csv` | Tested as alternatives; both did worse than the gauges, so dropped |
| Early single-gauge downloads (Osney daily rain, Oxford and Horspath boreholes, Cherwell / Kings Mill / Osney / Sandford levels) | `hydro_*.csv` | First exploration; the borehole turned out to be the weakest signal |
| Oxford-only alerts | `thames_alerts_oxford.csv` | First exploration; superseded by the full download |
| OS Open Rivers (river network) | `os_open_rivers/oprvrs_gb.gpkg` | For tracing spills downstream on the 3D map (not built yet) |
| LIDAR terrain (20 m, 100 m) | `oxford_dtm_20m.tif`, `oxford_dtm_100m.tif` | Terrain for the 3D map |

---

## Part 2 — What the checks found (`scripts/model/3_audit.py`)

| Data | What we found | What we did |
| --- | --- | --- |
| **Spill alerts vs official totals** | For a typical site our hours match Thames Water's official total to within 0.1% (75% of sites within ±5% in 2024, 87% in 2025). But **13 site-years are badly wrong**: four sites (Didcot, Charlton-on-Otmoor, Middleton Stoney, Weston-on-the-Green pumping station) have official hours but **no alerts at all** in the feed; Chalgrove's feed has 7% of its official hours; Islip's has double | Those 13 site-years are excluded |
| **Spill alerts: chatter** | 16% of spills last under 15 minutes; 42% of gaps between spills are under an hour | Doesn't affect hourly data; merged for any count of "events" |
| **Spill alerts: very long spills** | 155 spills over a week, 14 over a month (longest: South Leigh, 54 days in 2026) | Kept — groundwater-fed works genuinely spill for weeks |
| **Spill alerts: pairing** | 22 odd sequences in 34,000 alerts for our 61 sites (e.g. two Starts in a row) | Too few to matter; noted |
| **Rain** | Suspect readings at some gauges far too low; Benson read 557 mm in 2024 when its neighbours read ~950 mm; missing rain was being treated as "no rain" | Suspect → missing; days far from the neighbouring gauges → missing; gaps filled from the other gauges |
| **River flow** | Each daily value covers 09:00 to 09:00 the next day, so using "yesterday's" value let the model see up to 9 hours into the future | Each value only used 12 hours after its 24-hour window ends |
| **Treated volume** | Oxford's column is complete (< 1% missing every year); its peak exceeds the published capacity in some years (up to 1.23×) | Capacity treated as approximate |

---

## Part 3 — Clean data

Built by `scripts/model/4_build_clean.py` into `data/interim/`. **This is what the model reads.**

| File | What's in it | How it was made | Size |
| --- | --- | --- | --- |
| `sites61.csv` | The 61 overflows we model: permit number, name, grid location, latitude/longitude | `2_sites.py`, from the alert locations | 61 rows |
| `labels_clean.pkl` | For each overflow, hour by hour (1 Apr 2022 → 22 Oct 2026): **what fraction of the hour it was spilling** (0 to 1) and **whether that hour is trustworthy** (monitor working, site-year not broken) | From `events.csv` and `offline.csv`, using exact minutes | 61 sites × 39,984 hours |
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

### Outputs of the model (also in `data/interim/`)

| File | What's in it | Made by |
| --- | --- | --- |
| `eval_predictions.pkl` | Every test day for every site: what happened, and what each model predicted | `5_evaluate.py` |
| `site_cards.csv` | Per overflow, in plain units: the river flow that triggers a spill with no rain, the rain that triggers it on a typical winter day, how long rain keeps counting, and the groundwater signature | `6_site_cards.py` |

Other files in `data/interim/` (`inputs_hourly.pkl`, `labels_hourly*.pkl`, `exp_*.pkl`, `oxford_*.csv`, `multisite.csv`, `out_*.pkl`) come from the archived first-pass scripts in `scripts/archive/`. They use the uncleaned data and can be deleted.

---

## Rebuilding the data

From the repo root, after `pip install -r requirements.txt`:

```bash
python scripts/fetch_data.py thames-alerts      # ~10 min; all spill alerts
python scripts/fetch_data.py events             # pair alerts into spills and outages
python scripts/fetch_data.py thames-status      # overflow list
python scripts/model/1_fetch_gauges.py          # 10 rain + 10 flow gauges
python scripts/model/2_sites.py                 # the 61 sites and EA station lists
# by hand: TDV files -> data/raw/tdv/tdvYEAR.xlsx, annual returns -> data/raw/annual_returns/tw_edm_YEAR.xlsx,
#          ORIC capacity sheet -> data/raw/oric_fft.xlsx
python scripts/model/3_audit.py                 # checks; writes audit_reconciliation.csv
python scripts/model/4_build_clean.py           # clean data layer
```

Links for the hand downloads: Thames Water [storm discharge and flow data](https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data) (TDV and annual returns; direct file links work with a browser user agent) and [ORIC capacity sheet](https://oxfordrivers.ceh.ac.uk/data/ORIC_Thames_Sewage_Works_Capacity_Final.xlsx).

## Licences

- Environment Agency data: Open Government Licence — credit "© Environment Agency copyright and/or database right".
- Ordnance Survey Open Rivers: Open Government Licence — "Contains OS data © Crown copyright".
- Open-Meteo: CC BY 4.0.
- Thames Water data: [Thames Water's own terms](https://data.thameswater.co.uk/s/terms-of-service), not an open licence — publish derived results, not the raw files.
- ORIC capacity sheet: licence not yet checked.

## Glossary

| Term | Meaning |
| --- | --- |
| **Storm overflow** | A relief point where a sewer or sewage works discharges diluted sewage into a river when it is overloaded |
| **STW / WWTW** | Sewage (wastewater) treatment works |
| **CSO** | Combined sewer overflow — an overflow out in the sewer network rather than at a works |
| **EDM** | Event duration monitoring: the sensor that logs when an overflow starts and stops |
| **Permit number** | The Environment Agency's ID for each discharge (e.g. Oxford STW = TEMP.2827); the key that joins datasets |
| **TDV** | Total daily volume treated at a works (m³/day) |
| **FFT** | Flow to full treatment: the most a works can fully treat; above it, sewage goes to storm tanks and then overflows |
| **Water day** | The EA's day for river flow: 09:00 to 09:00 |
| **"Suspect" flag** | The EA's marker that a reading may be wrong |
| **Site-year** | One overflow's record for one calendar year |
