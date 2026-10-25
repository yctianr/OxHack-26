# 07 · Risks and corrections

## Corrections to the original brief

| Original assumption | What we found (24 Oct 2026) |
| --- | --- |
| The Thames Water API needs a client_id/secret | v2 answered with **no credentials**. Keep a key as a fallback. v1 returned 504. |
| History from Apr 2022 | Earliest alert overall is about 9 May 2022; **Oxford STW from 24 Nov 2022**. The EA start/stop files cover only 2024 → Aug 2026. |
| Use the Oxford borehole for groundwater | The GISMP uses river gauges, because the catchment is clay with gravels tied to the river. **And the Thames lock gauges barely move** (Osney typical −0.15…+0.12 m), so use the **Cherwell gauges and river flow**. |
| "Spills" = 162 in 2024 | That is the EA 12-24 count. Raw pairs give 75 events; hours roughly agree (2,940 vs 3,198). Define your target. |
| Test on dry 2025 only | That flatters "no spill" models. Add the wet 2023/24 fold and the live Oct 2026 event. |
| Predict "illegal discharges" | EDM data are unverified activations. Say "unexplained / dry-weather spills". Top of the Poops already does rain-based anomaly labels. |
| 137.7 L/head/day | Plausible; cite Thames Water's WRMP figure instead (133 L/h/d in 2030). |
| Volume can't be modelled | It can at **Oxford STW** with TDV, as an indirectly validated estimate (see 04 §3). Nobody measures spill volume, the companies included. |
| Show pipes | Not open data. Show the catchment, pumping stations, downstream traces and a schematic. |
| A 3D map with columns | Research says flat-first: matrix heatmap + 2D map; 3D only as a story shot. |

## Risks and mitigations

1. **Rain and wetness are collinear.** Use a *slow* wetness component (14-day minimum, high-k API) for infiltration, and keep rain lags separate. Show the decomposition only where the bucket model wins out of sample.
2. **Few events per site in a test year.** Pool sites in the GBM, report skill by site *group*, and give bootstrap CIs.
3. **TDV may need a manual download.** The site blocks scripts; budget 15 min. Without TDV, drop the two-stage fit and volume.
4. **Data volume and rate limits.** About 154 calls for all Thames Water alerts: fetch once and cache. Use daily Hydrology measures, not 15-min data back to 2001.
5. **Licence.** The Thames Water API has its own terms, not the OGL. Check them before publishing raw data in a public repo. **This repo keeps `data/raw/` git-ignored.**
6. **Map work eats the night.** Timebox it to 3 h, with a 2D fallback by midday.
7. **Clocks go back at 02:00 on 25 Oct.** API times are naive local time, so localise them as Europe/London.
8. **Live API changes during judging.** Demo from a frozen snapshot.
9. **Volume overclaiming.** Always show a range and "model estimate, not measured".
