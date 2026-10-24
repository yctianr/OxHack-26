# Handover — Spillcast (OxHack 2026)

Written Sat 24 Oct 2026, ~21:30 BST. **Deadline: Sun 25 Oct 2026, 16:00 GMT.** Clocks go back at 02:00 tonight, so 16:00 GMT is 16:00 UK clock time and 01:00–02:00 happens twice.

## What we're building

**Spillcast** forecasts sewage spills from storm overflows around Oxford (Thames, Cherwell, Windrush) and explains them. Target prize: **HRT "Best Use of Data for Predictions and Decision Making"**. The judges are quant researchers, so the priorities are real data, honest out-of-sample testing, calibrated probabilities, strong baselines, and clear decisions.

The team decided on 24 Oct to **model**, not just visualise. The outputs, in priority order:

| # | Output | Scope | Can it be validated? |
| --- | --- | --- | --- |
| 1 | **P(spill on day d+h)**, h = 0, 1, 2 | Every overflow (about 20–30 around Oxford) | Yes. EDM start/stop gives yes/no labels per site-day |
| 2 | **Spill duration** (expected hours, with a quantile range) | Every overflow | Yes. EDM durations are observed |
| 3 | **Spill volume** (estimated ML, wide range) | **Oxford STW only** (TEMP.2827), because it is the only site with daily treated-flow data | Only indirectly. Nobody measures spill volume; see [docs/04](docs/04-modelling-plan.md#3-volume-oxford-stw-only) |
| 4 | Decisions: Port Meadow swim flag, storage vs sealing £ per spill-hour, "unexplained" spills | — | Partly. The swim flag can be scored against E. coli samples |

## State right now

- **Research: done.** It is all in `docs/`; start with the index in [README.md](README.md).
- **Data access: verified live and scripted** in [`scripts/fetch_data.py`](scripts/fetch_data.py). Stdlib only, no keys; each subcommand was tested on 24 Oct.
- **Prototype UI: dummy data only**, in `prototype/`.
  - Run `python prototype/build.py`, then open `prototype/index.html`.
  - It has a 3D deck.gl map, a flow decomposition chart, a reliability diagram, a swim flag, storage vs sealing curves and an anomaly table.
  - **Superseded by the design research:** go flat-first. See [docs/06](docs/06-website-and-visuals.md).
- **Terrain:** real EA LIDAR DTM for Oxford, fetched and rendered ([docs/img/oxford_relief.png](docs/img/oxford_relief.png)).
- **No model code yet.** That is the next session's job.

## Do these next, in order

1. **Pull all data** (about 10 min):
   ```bash
   python scripts/fetch_data.py thames-alerts          # ~154 pages, all Thames Water sites, May 2022 → now
   python scripts/fetch_data.py events                 # pair Start/Stop → data/raw/events.csv + offline.csv
   python scripts/fetch_data.py thames-status          # site list with uniqueId, x/y
   python scripts/fetch_data.py hydrology --preset all --since 2022-01-01
   ```
   Also download **by hand in a browser**, because the site blocks scripts:
   - Thames Water daily treated volume (TDV) Excel files, 2019–2025, from <https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data>.
   - The EA EDM annual return 2025, from its FeatureServer (see docs/01), for the site metadata and the `highSpillOperationalReview` labels.
2. **Build the site-day table** in [docs/04 §Target](docs/04-modelling-plan.md#target-and-cleaning). Mark offline periods as missing, not dry. Check that per-site annual hours match the EA return (Oxford STW 2025: 590.5 h in both).
3. **Baselines first:** persistence and a "rain > X mm" rule, scored with a rolling-origin backtest by hydrological year (Oct–Sep).
4. **Bucket model** per site, then **LightGBM** pooled across sites. Calibrate with isotonic regression on a held-out year.
5. **Duration** (hurdle / quantile model) for all sites; **volume** for Oxford STW using TDV.
6. **Live forward test** on 19–24 Oct 2026: about 63 mm of rain fell at Osney, 16 local overflows spilled, and Oxford STW spilled 13:30–21:45 on 23 Oct.
7. **Website**, flat-first, following the 7-section layout in docs/06. Use a GitHub Action to refresh the JSON, because the Thames Water API sends no CORS header.

Time plan: [docs/08-build-plan.md](docs/08-build-plan.md). Code freeze 14:00, submit 15:30.

## Decisions already made (don't re-litigate)

- **Daily resolution**, target = any spill that day. Rain forecasts, groundwater and the 12-24 counting rule all line up with daily data.
- **Groundwater signal: Cherwell gauges (1490TH, 1491TH) and Cherwell/Thames flow, not the Thames lock headwater gauges.**
  - Osney's typical range is −0.15 to +0.12 m, because the lock holds the level.
  - The Oxford borehole SP50_72 (Corallian, 9 m deep) is a secondary, slow regional index.
  - Thames Water's own Oxford plan (GISMP) says the catchment is Oxford Clay, not a principal aquifer. Groundwater reaches the sewers through river gravels tied to river level.
- **Wording:** "unexplained / dry-weather spills" and "leads to check", **never "illegal"**. EDM data are unverified activations.
- **Pitch angle:** forecasting with calibrated per-site probabilities plus a groundwater term.
  - Top of the Poops already labels days "more sewage than the rain explains", so anomaly detection alone is not new.
- **Volume:** an estimate for Oxford STW only, labelled "model estimate, not measured", with a range.
- **Visuals:**
  - **Cut** the 3D extruded columns and any kernel-density heatmap.
  - Lead with a swim decision card ("about 4 in 10"), an **overflow × day matrix**, and a flat map on real hillshade with rivers coloured downstream of each overflow.
  - 3D terrain is for one storytelling view only.
- **Pipes are not shown.** The sewer network is not open. Show the catchment, pumping stations, downstream traces and a schematic instead.

## Gotchas found the hard way

- **Thames Water API**
  - v2, `https://api.thameswater.co.uk/opendata/v2/discharge/{status,alerts}`. **No key needed** right now; v1 returned 504.
  - `limit` ≤ 1000 with `offset` pagination, newest first.
  - `locationName=` and `permitNumber=` filters work; date filters and `uniqueId=` are **silently ignored**.
  - Datetimes are **naive UK local time**: localise them as Europe/London.
  - **No CORS header**, so browsers can't call it directly.
- **History:** the earliest alert overall is about 9 May 2022. **Oxford STW's history starts 24 Nov 2022.** The EA start/stop files only cover 2024 → Aug 2026.
- **Counts differ by definition.**
  - Raw Start/Stop pairs for Oxford STW give 75 events / 2,940 h (2024) and 38 / 590 h (2025).
  - The EA 12-24 counting method gives 162 / 3,198 h (2024) and 43 / 590.5 h (2025).
  - Model **hours or P(any spill per day)**, and state the definition.
- **Hydrology daily rain** (`-t-86400-`) is a **09:00–09:00 water day** and lags about 2 days.
  - For the live forecast, use the flood-monitoring 15-min feed for gauge 256230TP and sum it yourself.
- **Hydrology API:** use `min-date` and `_limit`/`_offset`. Daily `level-max-86400` measures exist for every gauge (IDs in `fetch_data.py`).
- **Stage → mAOD:** add the gauge datum from `flood-monitoring/id/stations/{id}/stageScale`.
  - Datums: Godstow 58.076, Osney 56.509, Iffley 54.617, Sandford 53.709, Cherwell Botanic 50.0, Kings Mill 54.0.
- **Do not use** a county-council map server that appears to expose Thames Water's internal sewer records with no licence. It's deliberately not linked anywhere in this repo.

## Open questions

- Does treated flow (TDV) at Oxford STW plateau on spill days? If yes, that plateau gives the effective full-treatment capacity and makes the volume model identifiable. Check this first when you have the TDV file.
- What are the FFT and storm tank size in Oxford STW's permit? These are on the EA public register; Thames Water's open data doesn't include them.
- Does the bucket model actually beat LightGBM at groundwater-tagged sites? Pre-register that hypothesis and report it either way.
- Port Meadow risk mostly comes from upstream works (Cassington, Eynsham, Witney/Windrush). Only Cassington is formally linked to the bathing water. Confirm the upstream set.

## Links

- Research brief and "Website & visuals" tab (claude.ai doc, private to the owner): https://claude.ai/artifact/AK3Sppr7ikgc2M8AFm3fjc
- Dummy-data prototype (private artifact): https://claude.ai/artifact/HfWwFX2zdUXmh9MQR3evQ3
- Everything in those is also in `docs/` here.
