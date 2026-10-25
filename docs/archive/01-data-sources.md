# 01 · Data sources

Everything here was called live on **24 Oct 2026** unless marked otherwise. No source needs an API key. The one gap is treatment capacity and storm-tank sizes, which are not in any open feed.

## Overflow events

| Source | Endpoint | Key fields | History | Access / limits |
| --- | --- | --- | --- | --- |
| **Thames Water alerts** (event log) | `https://api.thameswater.co.uk/opendata/v2/discharge/alerts` | locationName, permitNumber, locationGridRef, x, y (EPSG:27700), receivingWaterCourse, alertType (`Start`, `Stop`, `Offline start`, `Offline stop`), datetime | About 153.5k rows. Earliest about 9 May 2022; **Oxford STW from 24 Nov 2022** | No key. `limit` ≤ 1000, `offset`, newest first. Filters `locationName=` and `permitNumber=` work; date and `uniqueId=` filters are ignored. **No CORS.** Datetimes are naive UK local time. |
| **Thames Water status** | `…/opendata/v2/discharge/status` | Adds uniqueId (`TWLxxxxx`), alertStatus, statusChanged, alertPast48Hours, mostRecentDischargeAlertStart/Stop | Snapshot of 573 monitors (17:00 on 24 Oct: 521 not discharging, 31 offline, 21 discharging) | Same |
| **Stream: Thames Water Storm Overflow Activity** | `services2.arcgis.com/g6o32ZDQ33GpCIu3/arcgis/rest/services/Thames_Water_Storm_Overflow_Activity_(Production)_view/FeatureServer/0` | Id, Status, StatusStart, LatestEventStart/End, Latitude/Longitude, ReceivingWaterCourse, LastUpdated | Current state only | CC BY 4.0. Use it as a backup feed. |
| **EA start/stop detailed EDM data** | [data.gov.uk 39ba1e24](https://www.data.gov.uk/dataset/39ba1e24-69ca-4031-badf-e02649b74a7b/event-duration-monitoring-storm-overflow-start-stop-detailed-data) | Every activation start/stop, one spreadsheet per company per year (zip) | 2024, 2025, 2026 to August (files updated 22 Oct 2026) | OGL. "Not subject to formal verification". Only source for other companies. |
| **EA EDM annual return 2025** | `services3.arcgis.com/Bb8lfThdhugyc4G3/arcgis/rest/services/Event_Duration_Monitoring_Storm_Overflows_2025/FeatureServer/0` | permitReferenceEA, siteNameWASC, assetType, bathingWater, countedSpills (12-24 method), totalDurationAllSpillsHrs, edmOperationPercent, **highSpillOperationalReview**, treatmentType, Eastings/Northings | One layer per year; the annual returns run 2016–2025 | ArcGIS REST `query`, `f=json` |

`highSpillOperationalReview` labels for Thames Water in 2025:

| Label | Sites |
| --- | --- |
| High spill threshold not met | 465 |
| Performance - GW inundation | 41 |
| Not asset maintenance - Hydraulic capacity | 30 |
| Performance - Asset configuration | 26 |
| Performance - SW Infiltration | 12 |

**The "GW inundation" tag is a free external validation label** for the groundwater term. Twelve tagged sites are near Oxford: Bampton, Charlton-on-Otmoor, Church Hanborough, Combe, Haddenham, Islip, Little Milton, Standlake, Stanton Harcourt, Uffington, Wheatley and Witney.

## Weather, rivers, groundwater (Environment Agency)

| Source | Endpoint | Notes |
| --- | --- | --- |
| Rain, real-time 15 min | `environment.data.gov.uk/flood-monitoring/id/stations/256230TP/readings?since=…` | Osney Lock gauge. Rolling about 28 days. Use this for the live forecast. |
| Rain, long history | Hydrology `…/measures/5086b349-e04b-4f8e-b8f1-fa92b21078d0_256230TP-rainfall-t-86400-mm-qualified/readings` (daily) and `…-t-900-…` (15 min) | Since 1985. **Daily = 09:00–09:00 water day, lagging about 2 days.** Nearby gauges: Eynsham, Wheatley, Abingdon. |
| Groundwater | Hydrology `ca3d0164-ee1d-444e-bc6c-04d600498b61-gw-logged-i-subdaily-mAOD-qualified` | Oxford borehole SP50_72: Corallian, 9.29 m deep, ground datum 63.34 mAOD. **58.835 mAOD at 07:00 on 24 Oct.** Logged since Nov 2001. Horspath `c5ce6e05-…` read 62.99. |
| River level / flow (daily) | Hydrology `…-level-max-86400-m-qualified` and `…-flow-…-m3s-qualified`; IDs in `scripts/fetch_data.py` | Cherwell at Oxford 1490TH (level + flow), Kings Mill 1491TH, Farmoor 1100TH (Thames flow), Sandford 1502TH, Osney 1303TH, Godstow 1302TH, Iffley 1501TH, Islip Weir 1489TH (flow) |
| Gauge datums | `flood-monitoring/id/stations/{id}/stageScale` | Godstow 58.076, Osney 56.509, Iffley 54.617, Sandford 53.709, Cherwell Botanic 50.0, Kings Mill 54.0 mAOD. Typical ranges: Osney −0.15…+0.12 m (lock-held); Cherwell Botanic 4.8…6.19 m |
| Bathing water | `environment.data.gov.uk/doc/bathing-water.json` → Wolvercote Mill Stream `ukj1402-11946` | Designated 2022. **2025 classification: Poor.** Has an STP risk prediction during the season. Latest sample 23 Sep 2026: E. coli 300, enterococci 170 cfu/100 ml. The per-sample URL works; the list endpoint path is still an open question. |

## Flow and population

- **Thames Water daily treated volume (TDV)**, 2019–2025, Excel per year: <https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data>.
  - Works under 50 m³/day are excluded.
  - **The site blocks scripts, so download it by hand.**
  - TDV is *treated* flow, not spilled flow.
- **EA DWF method** ([gov.uk](https://www.gov.uk/government/publications/calculating-dry-weather-flow-dwf-at-waste-water-treatment-works/calculating-dry-weather-flow-dwf-at-waste-water-treatment-works)): DWF = PG + I + E; DWF ≈ **Q80 of daily TDV** (the 73rd lowest of 365).
- **Thames Water FFT methodology** ([DWMP28 PDF](https://www.thameswater.co.uk/media-library/os3lcdg4/treatment-works-compliance-fft.pdf)):
  - FFT = 3PG + 3E + Imax at works with storm tanks; in practice about 2.5–2.7 × DWF.
  - Imax = 98th percentile of dry-day (≤ 0.25 mm) infiltration, rising 0.5% per year.
  - Trade effluent E = annual billing ÷ 303 working days.
  - Formula A = DWF + 1360P + 2E.
  - Per-capita water use G: 133 L/head/day in 2030, falling to 110 in 2045 (Thames Water WRMP).
- **EA permit rules** ([gov.uk](https://www.gov.uk/government/publications/water-companies-environmental-permits-for-storm-overflows-and-emergency-overflows/water-companies-environmental-permits-for-storm-overflows-and-emergency-overflows)):
  - Storm tanks must hold at least 68 L per head served, or 2 h at the maximum flow to the tanks.
  - Overflows operating in dry weather are "unsatisfactory".
- **Population:** ONS 2022-based subnational projections (not checked here). Oxford STW serves a population equivalent of 235,046 (GISMP).

## Capacity and storm tanks (not open)

Options, best first:

1. Parse FFT and storm-tank volume from the EA permit PDFs on the [public register](https://environment.data.gov.uk/public-register).
2. Use the Oxford Rivers Improvement Campaign's EIR-sourced FFT estimates for 181 works ([Thames21](https://www.thames21.org.uk/2025/07/new-research-reveals-over-half-of-thames-waters-sewage-works-struggling-to-meet-demand/)).
3. Fit capacity as a latent parameter. For Oxford STW, read it off the TDV plateau on spill days if one exists.

## Geography

| Layer | Source | Notes |
| --- | --- | --- |
| Terrain, 1 m | EA LIDAR Composite DTM 2022 WCS `environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs`, coverage `13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m` | `GetCoverage&subset=E(440000,462000)&subset=N(198000,216000)&SCALEFACTOR=0.05` returns all of Oxford at 20 m in about 4 s (6.3 MB float32 GeoTIFF, 49.8–171.5 m) |
| Surface (buildings, trees) | DSM WCS, coverage `df4e3ec3-315e-48aa-aaaf-b5ae74d7b2bb__Lidar_Composite_Elevation_FZ_DSM_1m` | DSM − DTM = object height |
| Terrain tiles for web maps | `s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png` | UK zooms 10–15 use EA LIDAR at 2 m ([joerd](https://github.com/tilezen/joerd/blob/master/docs/data-sources.md)). CORS open. |
| Flood zones | `environment.data.gov.uk/spatialdata/flood-map-for-planning-flood-zones/ogc/features/v1/collections/Flood_Zones_2_3_Rivers_and_Sea/items?bbox=…` | 143 polygons in central Oxford. Also Recorded Flood Outlines. CORS open. |
| Rivers | OS Open Rivers via `api.os.uk/downloads/v1/products/OpenRivers` | Edition 2026-04. Links digitised in flow direction. |
| Basemap | OpenFreeMap styles (`tiles.openfreemap.org/styles/liberty`) | No key; OSM buildings |
| Oxford STW catchment | [tillahoffmann/wastewater-catchment-areas](https://github.com/tillahoffmann/wastewater-catchment-areas) | EIR-sourced. "OXFORD STW" = `UKENTH_TWU_TP000159`. Copyright Thames Water; label it indicative. |
| Downstream river traces now | sewagemap `d1kmd884co9q6x.cloudfront.net/downstream_impact/thames/thames_now_incl_48hrs.geojson` | From POOPy (GPL-3.0). CORS open, updated hourly. Cache it and credit it. |

## Join keys

- Join the Thames Water API to the EA returns on `permitNumber` = `permitReferenceEA`. Oxford STW = `TEMP.2827`.
- Convert x/y (EPSG:27700) with pyproj.
- **Rain:** the nearest one or two gauges by distance.
- **Groundwater / river:** the nearest gauge **on the same river system**. Cherwell sites use 1490TH/1491TH; Thames sites use flow at Farmoor or Sandford. Use the borehole in the same aquifer, not simply the closest one.

## Counting definitions

| Source | Oxford STW 2024 | Oxford STW 2025 |
| --- | --- | --- |
| Raw API Start/Stop pairs | 75 events / 2,940 h | 38 events / 590 h |
| EA 12-24 counted spills (also in the GISMP) | 162 / 3,198.3 h | 43 / 590.5 h |

Hours agree; counts don't. Model **P(any spill per day)** and **hours**.
