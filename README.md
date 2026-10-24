# Spillcast

Forecasting sewage spills from storm overflows around Oxford, explaining them (rain vs groundwater), and turning the forecasts into decisions: is it safe to swim at Port Meadow, do bigger storm tanks or sealed sewers buy more, and which spills does the weather not explain.

Built for **OxHack 2026**, targeting the HRT prize "Best Use of Data for Predictions and Decision Making". Deadline Sun 25 Oct 2026, 16:00 GMT.

**Start here: [docs/11-system-review.md](docs/11-system-review.md)** (audited data, corrected results), then [docs/10-model-v2-plan.md](docs/10-model-v2-plan.md) (plan and decision log)

## Repo layout

```
docs/
  01-data-sources.md        verified endpoints, fields, history, access, join keys
  02-prior-work.md          academic, company and campaigner work; our gap
  03-oxford.md              Oxford overflows, Port Meadow, groundwater indicators, this week's event
  04-modelling-plan.md      probability, duration and volume models; features; evaluation
  05-decisions-and-costs.md swim flag, storage vs sealing (£), anomalies, targets
  06-website-and-visuals.md terrain + water levels, heatmap vs map, pipes and flows, page layout, stack
  07-risks-and-corrections.md
  08-build-plan.md          hour-by-hour to the deadline (v1)
  09-plan-review.md         review of the v1 plan
  11-system-review.md       first-principles review: data audit, corrected evaluation, explainability
  10-model-v2-plan.md       CURRENT PLAN: decision log, bathtub model, volume, placement, 3D river map
  sources.md
  img/oxford_relief.png     real EA LIDAR terrain of Oxford (20 m)
scripts/
  model/                    the pipeline, run in order: 1 gauges, 2 sites, 3 audit, 4 clean data, 5 evaluate, 6 site cards, 7 volume
  archive/                  pre-audit exploration (superseded; record behind docs/11 §4.2)
  fetch_data.py             Thames Water alerts/status, EA Hydrology, EA LIDAR DTM (stdlib only)
  terrain/                  pure-Python GeoTIFF reader + hillshade renderer
prototype/                  dummy-data UI prototype (python prototype/build.py → index.html)
data/raw/                   fetched data (git-ignored)
```

## Quick start

```bash
python scripts/fetch_data.py thames-alerts && python scripts/fetch_data.py events
python scripts/fetch_data.py hydrology --preset all --since 2022-01-01
python scripts/fetch_data.py dtm --res 20

# model pipeline (pip install -r requirements.txt). Put Thames Water's TDV files in data/raw/tdv/tdv{YEAR}.xlsx and
# EDM annual returns in data/raw/annual_returns/tw_edm_{YEAR}.xlsx (links on the Thames Water storm discharge page)
for s in 1_fetch_gauges 2_sites 3_audit 4_build_clean 5_evaluate 6_site_cards 7_volume_oxford; do python scripts/model/$s.py; done
```

## Data licences

- EA data: Open Government Licence. Attribute "© Environment Agency copyright and/or database right".
- Thames Water open data: [their terms](https://data.thameswater.co.uk/s/terms-of-service), which are not the OGL. Check them before redistributing raw data.
- OS Open Rivers: Contains OS data © Crown copyright.
- OpenStreetMap: © OpenStreetMap contributors (ODbL).
