# Spillcast

Forecasting sewage spills from storm overflows around Oxford, explaining them (rain vs groundwater), and turning the forecasts into decisions: is it safe to swim at Port Meadow, do bigger storm tanks or sealed sewers buy more, and which spills does the weather not explain.

Built for **OxHack 2026**, targeting the HRT prize "Best Use of Data for Predictions and Decision Making". Deadline Sun 25 Oct 2026, 16:00 GMT.

**Start here: [HANDOVER.md](HANDOVER.md)**

## Repo layout

```
HANDOVER.md                 state, decisions, next steps, gotchas
docs/
  01-data-sources.md        verified endpoints, fields, history, access, join keys
  02-prior-work.md          academic, company and campaigner work; our gap
  03-oxford.md              Oxford overflows, Port Meadow, groundwater indicators, this week's event
  04-modelling-plan.md      probability, duration and volume models; features; evaluation
  05-decisions-and-costs.md swim flag, storage vs sealing (£), anomalies, targets
  06-website-and-visuals.md terrain + water levels, heatmap vs map, pipes and flows, page layout, stack
  07-risks-and-corrections.md
  08-build-plan.md          hour-by-hour to the deadline
  sources.md
  img/oxford_relief.png     real EA LIDAR terrain of Oxford (20 m)
scripts/
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
```

## Data licences

- EA data: Open Government Licence. Attribute "© Environment Agency copyright and/or database right".
- Thames Water open data: [their terms](https://data.thameswater.co.uk/s/terms-of-service), which are not the OGL. Check them before redistributing raw data.
- OS Open Rivers: Contains OS data © Crown copyright.
- OpenStreetMap: © OpenStreetMap contributors (ODbL).
