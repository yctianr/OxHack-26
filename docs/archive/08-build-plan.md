# 08 · Build plan to Sun 25 Oct, 16:00 GMT

All times are UK clock time. The clocks go back at 02:00, so 01:00–02:00 happens twice and you gain an hour. **Code freeze 14:00; submit by 15:30.**

With two or more people, split from 07:30 into **modelling** (bucket → duration → volume → evaluation) and **product** (website → decision UI → story).

| Time | Work | Done when |
| --- | --- | --- |
| Sat 21:30 – 00:30 | Pull and clean all data (`scripts/fetch_data.py`); download TDV and the EA return by hand | One table per source; site-day table built; per-site annual hours match the EA return |
| 23:30 – 01:30 | Persistence + rain-threshold baselines and the rolling-origin backtest harness | Every later model has a number to beat |
| 01:30 – 06:30 | Sleep | — |
| 06:30 – 09:30 | Bucket model per site; at Oxford STW, fit inflow to TDV and check for a plateau | Rain vs infiltration decomposition for Oxford STW |
| 07:30 – 10:30 | LightGBM + isotonic calibration | Reliability diagram + Brier skill table |
| 09:30 – 11:00 | Duration model (hurdle + quantiles); volume estimate with bootstrap range (Oxford STW) | Duration interval coverage; volume range per event |
| 08:30 – 12:00 | Website: decision card, matrix heatmap, flat map with real terrain and downstream rivers (2D first) | Runs from a static JSON snapshot |
| 11:00 – 13:00 | Decision layer: swim flag vs EA flag, storage vs sealing, anomaly list | Shown on the site |
| 13:00 – 13:30 | Live forward test on 19–24 Oct | Scored and on screen |
| 14:00 | **Code freeze** | Demo runs offline from the snapshot |
| 13:30 – 15:30 | Devpost write-up + 2-min video | Pitch: forecasting + calibration + groundwater; honest limits |
| 15:30 | **Submit** (30 min buffer) | — |
| 16:00 | Deadline | — |

**Simplest version that still impresses quant judges:**

- 20–30 sites, 4 models, a reliability diagram, and a Brier skill table by site group.
- The Oxford STW rain-vs-infiltration decomposition.
- Duration intervals.
- The live test on this week's event.
- A swim card.
- Volume, the 3D story and particle animation are bonuses.
