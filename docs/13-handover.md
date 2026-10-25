# 13 · Handover — Spillcast (OxHack 2026)

Written Sat 24 Oct 2026, 23:00 BST. **Deadline: Sun 25 Oct, 16:00 GMT.** Clocks go back at 02:00 tonight (01:00–02:00 happens twice), so 16:00 GMT is 16:00 on the clock. **Code freeze 14:00, submit 15:30.**

## What we're building

**Spillcast** models sewage spills from the 61 storm overflows within 25 km of Oxford: the chance of a spill today, how long spills last, an estimated volume at works with flow data, and where infrastructure (storage, sewer sealing, treatment capacity, SuDS) would cut the most harm per £. The headline visual is a 3D map of sewage glowing down Oxford's rivers. Target prize: **HRT "Best Use of Data for Predictions and Decision Making"** — quant judges, so honest backtests, calibrated probabilities and strong baselines matter more than polish.

## Read in this order

1. **This file.**
2. [`docs/12-data-guide.md`](12-data-guide.md) — every dataset, raw vs cleaned, what was fixed, how to rebuild.
3. [`docs/11-system-review.md`](11-system-review.md) — the audited, corrected results. **Overrides docs/10 wherever they disagree.**
4. [`docs/10-model-v2-plan.md`](10-model-v2-plan.md) — the plan and the decision log (D1–D12): model layers, volume, placement, 3D map, build order.
5. Team docs: [`docs/09-plan-review.md`](09-plan-review.md) (a teammate's review of the v1 plan) and `docs/10-list-of-discharge-points` (a teammate's list of ~22 overflows).
6. Background research: docs/01–08 (v1; data sources, prior work, Oxford specifics, costs, visuals).

## State right now

**Done**
- **All data pulled and audited.** 153,783 spill alerts (Apr 2022 →), 10 rain and 10 flow gauges, Thames Water treated volume 2019–25, official annual returns 2023–25, ORIC capacity sheet, OS Open Rivers, LIDAR. See docs/12.
- **Clean data layer** (`scripts/model/4_build_clean.py`): exact-minute spill labels, 13 broken site-years excluded, faulty rain readings replaced from neighbours, river flow dated so it never sees the future. Oxford STW spill-hours now match Thames Water's official totals (3,200 vs 3,198 h in 2024; 590 vs 590.5 h in 2025).
- **Model + honest evaluation** (`5_evaluate.py`), two tasks scored separately:

  | Task | Physics model (3 inputs, 4 params) | Compared with |
  | --- | --- | --- |
  | **Explain** (given the rain that fell) | Brier 0.050 / 0.045, AUC 0.97–0.98 | Gradient boosting: each wins one test year |
  | **Forecast** (standing at 00:00, no rain forecast yet) | Brier 0.032 / 0.029, skill 0.70–0.74, well calibrated | **Beats persistence** (CI clear of zero); ties gradient boosting |
  | Spill onsets | AUC 0.89–0.90 (persistence 0.60) | Only ~15% caught confidently without a rain forecast |
  | **Yearly spill-hours per site** | **Weak: median error 35%** | Pooled totals fine (+2–5%) because errors cancel |

- **Explainable site cards** (`6_site_cards.py`): per overflow, the river flow that triggers a spill with no rain, the rain that triggers it on a typical winter day, how long rain counts, and a groundwater signature (AUC 0.80 against Thames Water's own "GW inundation" tag).
- **Volume** (`7_volume_oxford.py`): Oxford STW only so far; 2024 ≈ 2,200 ML (1,800–2,500), 2025 ≈ 300 ML. Storm tanks not modelled — **order of magnitude only**.

**Not started:** forecast rain, volume at the other ~14 works, river propagation and harm, placement optimiser, the 3D map, the website, the write-up.

## The model in one paragraph

Each overflow is a "bathtub": `z = b0 + b1·log(Thames flow at Farmoor) + b2·(rain store)`, where the rain store is rain from the two nearest gauges fed through a linear reservoir (time constant τ = 6–96 h, chosen per site). The chance of spilling in an hour is σ(z); the daily chance comes from the day's peak z through a 2-parameter calibration. Forecasts add two state inputs (spilling at midnight, hours spilled yesterday). Everything is in `scripts/model/common.py`.

## Decisions already made (don't re-litigate without new evidence)

- **One Farmoor flow gauge for every site** as the wetness signal. Per-site gauge choice, soil moisture, boreholes and a modelled slow store all did worse. It measures *seasonal catchment wetness*, not groundwater — say it that way.
- **Rain = inverse-distance mix of the 2 nearest audited EA gauges.** ERA5 was worse.
- **Explain and Forecast are separate.** What-ifs and volume use Explain only (no observed spill state); the swim card / live map uses Forecast.
- **What-ifs are reported as relative change** (Δ% spill-hours with a range), never absolute hours — per-site yearly totals are the model's weak point.
- **Volume:** ~15 works with treated-flow data, censored regression, always labelled "model estimate, not measured", order of magnitude.
- **3D map:** glowing rivers on LIDAR terrain (colour = estimated % sewage in the flow); nothing painted off-river. deck.gl 9.4.0, heights baked in Python.
- **Harm** = spill volume ÷ typical river flow × receptor weight (bathing water 3, protected site 2, other 1), with a spill-hours toggle.
- **Levers:** storage, sewer sealing, treatment capacity, SuDS — each moves one model parameter.
- **Wording:** "unexplained / dry-weather spills", "leads to check", never "illegal". Spill monitors indicate, they don't confirm.
- **Rejected after testing:** wetness hinge, season term, recency weighting, recalibration on recent data, second fast rain store, slow local store, soil moisture, ERA5 rain (docs/11 §4.2).

## Do these next, in order

| When | Modelling | Product |
| --- | --- | --- |
| Sat 23:00 → sleep | — | — |
| Sun 07:00–09:00 | **Forecast rain**: fetch Open-Meteo historical forecasts for the gauge locations, rescore Forecast on onset days. **Live test**: extend the data to 24 Oct (see gotchas) and score the 23–24 Oct spills untouched | `prep_rivers.py`: OS Open Rivers graph, snap the 61 outfalls, densify, bake heights from the DTM; terrain heightmap PNG |
| 09:00–11:00 | **Volume**: FFT as lower bound on all-day spill days; handle storm-tank pump-back; extend to the ~14 other works with TDV | deck.gl page: terrain + rivers + outfalls from a stub JSON |
| 11:00–12:30 | **Placement**: replay weather through the Explain model under each lever; relative Δ spill-hours (all sites) and Δ volume (works); greedy allocation; compare with Thames Water's plan (> £270m at Oxford STW, 2032) | Propagation → per-river-segment % sewage; day slider, before/after toggle, site cards in tooltips |
| 12:30–13:30 | Export a frozen JSON snapshot | Swim card (risk level, never "safe"), reliability chart, polish |
| 14:00 | **Code freeze** | |
| 14:00–15:30 | Write-up + 2-min video: forecasting + calibration + honest limits | |

**Never cut:** clean data, the evaluation table, the bathtub model, relative what-ifs. **Cut first if behind:** SuDS lever, particles on the map, volume beyond Oxford STW.

## Open questions for the team

- **Site list:** `docs/10-list-of-discharge-points` names ~22 overflows; the pipeline models all 61 within 25 km. If 22 is the chosen subset, filter in `scripts/model/2_sites.py`.
- **Doc numbering:** there are two `docs/10-*` files (the plan and the discharge-points list). Renumber one if it confuses people.
- **ORIC capacity sheet licence** not checked — check before publishing derived capacity numbers.
- Does treated flow plateau at capacity on all-day spill days at the other works? (Oxford: median 0.96× capacity; 36% of all-day spill days were below 92% of capacity — a lead to check, not an accusation.)

## Gotchas found the hard way

- **Setup:** system Python has no pandas. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (`.venv/` is git-ignored). Run scripts from the repo root: `python scripts/model/5_evaluate.py`.
- **Data isn't in git.** Rebuild with the commands in docs/12 (≈ 15 min plus three hand downloads).
- **Hard-coded end date:** `4_build_clean.py` builds hours up to **2026-10-22 23:00** and `common.py` fold B ends 2026-10-23. Move both forward to score the 23–24 Oct storm, after re-running `fetch_data.py thames-alerts`, `events` and `1_fetch_gauges.py`.
- **Thames Water API:** returns *empty pages* mid-history when rate limiting (now retried in `fetch_data.py`); `limit` ≤ 1000; date filters are ignored; times are naive UK local time; no CORS header (the website needs a scheduled job to refresh JSON).
- **EA daily flow** is a 09:00–09:00 "water day" stamped at its start — `4_build_clean.py` handles it; don't re-derive "yesterday's flow" naively.
- **EA rain "Suspect" flags** can mean a blocked gauge (Benson 2024). Treated as missing.
- **Thames Water Excel files:** TDV column names change by year (`DATE`/`Date`, `ABINGDON STW2`/`ABINGDON STW (2)`); annual-return headers sit on row 1 (2024) or row 5 (2025); durations come as `timedelta` values over 24 h. Direct file links work with a browser user agent.
- **Evenlode at Cassington** flow has a GUID station ID (`8afc6e20-…_1290TH`), not the plain reference.
- **Open-Meteo** returns 429 if you hammer it; batch 6 locations per call. ERA5 precipitation is a previous-hour sum (1 h offset from gauges).
- **Same-day rain is not a forecast.** Any new score must say which task (Explain or Forecast) it is, and use only information available at the time.

## Links

- Research brief (claude.ai doc, private to the owner): https://claude.ai/artifact/AK3Sppr7ikgc2M8AFm3fjc
- Dummy-data UI prototype: `prototype/` (`python prototype/build.py`); superseded by the 3D river design in docs/10 §5.
