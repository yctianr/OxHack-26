# Spillcast

Forecasting sewage spills from storm overflows around Oxford, quantifying them (rain vs volumn of sewage), and predicting the concentration and spread of sewage in the rivers nearby and turning the forecasts into decisions of where to improve sewage systems.

Built for **OxHack 2026**, targeting the HRT prize "Best Use of Data for Predictions and Decision Making". Deadline Sun 25 Oct 2026, 16:00 GMT.

**Start here: [docs/13-handover.md](docs/13-handover.md)** (state, decisions, next steps, gotchas), then [docs/12](docs/12-data-guide.md) (data), [docs/11](docs/11-system-review.md) (audited results) and [docs/10](docs/10-model-v2-plan.md) (plan and decision log)

## Run the website

The site needs no data download and no Python packages: everything it shows is pre-built in `web/`.

```bash
python3 -m http.server 8000 -d web
```

Then open <http://localhost:8000>.

- **Use the server, not a double-click.** Opening `web/index.html` straight from the file system fails, because browsers block a page on `file://` from loading its data files.
- **You need an internet connection.** The page loads deck.gl, Chart.js and fonts from CDNs.
- **It opens on "Inspect works"**, the regulator watchlist: which works spill while treating below their permitted flow, or when the weather doesn't explain it. The **"Spills by day"** tab has the daily forecast views. Add `#day` to the URL to open on that tab.
- **To host it**, upload the `web/` folder to any static host, for example by dragging it onto <https://app.netlify.com/drop>.

The models themselves need the data in `data/`, which is not in git (about 460 MB; see [Rebuild everything](#rebuild-everything)).

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
  13-handover.md            START HERE: state, decisions, next steps, gotchas
  12-data-guide.md          every dataset: raw vs cleaned, what was fixed, how to rebuild
  11-system-review.md       first-principles review: data audit, corrected evaluation, explainability
  10-model-v2-plan.md       CURRENT PLAN: decision log, bathtub model, volume, placement, 3D river map
  sources.md
  img/oxford_relief.png     real EA LIDAR terrain of Oxford (20 m)
scripts/
  model/                    statistical model, run in order: 1 gauges, 2 sites, 3 audit, 4 clean data, 5 evaluate, 6 site cards, 7 volume
                            water balance (works with treated-flow data): 8 prep + flow audit, 9 fit, 10 evaluate; wb.py is the model
  web/                      builds web/data/*.json and web/watchlist/data.json (see scripts/web/README.md)
  archive/                  pre-audit exploration (superseded; record behind docs/11 §4.2)
  fetch_data.py             Thames Water alerts/status, EA Hydrology, EA LIDAR DTM (stdlib only)
  terrain/                  pure-Python GeoTIFF reader + hillshade renderer
web/                        the website (static): index.html + pre-built data; serve this folder
prototype/                  dummy-data UI prototype (python prototype/build.py → index.html)
data/raw/, data/interim/    fetched and cleaned data (git-ignored)
```

## Rebuild everything

Only needed to change the models or refresh the data. Run from the repo root, in a virtual environment (system Python has no pandas):

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
source .venv/bin/activate

# 1. fetch (about 15 min)
python scripts/fetch_data.py thames-alerts && python scripts/fetch_data.py events
python scripts/fetch_data.py hydrology --preset all --since 2022-01-01
python scripts/fetch_data.py dtm --res 20

# 2. download by hand (links in docs/12, "Rebuilding the data"):
#    Thames Water daily treated volumes  -> data/raw/tdv/tdv{YEAR}.xlsx           (2019-2025)
#    Thames Water EDM annual returns      -> data/raw/annual_returns/tw_edm_{YEAR}.xlsx
#    ORIC capacity sheet                  -> data/raw/oric_fft.xlsx
#    OS Open Rivers GeoPackage            -> data/raw/os_open_rivers/oprvrs_gb.gpkg

# 3. statistical model
for s in 1_fetch_gauges 2_sites 3_audit 4_build_clean 5_evaluate 6_site_cards 7_volume_oxford; do python scripts/model/$s.py; done

# 4. water balance (8 also downloads daily evaporation from Open-Meteo)
for s in 8_wb_prep 9_wb_fit 10_wb_evaluate; do python scripts/model/$s.py; done

# 5. website data (extra packages: pip install pyproj rasterio pillow)
for s in rivers terrain texture data build_stats watchlist; do python scripts/web/$s.py; done
```

## Data licences

- EA data: Open Government Licence. Attribute "© Environment Agency copyright and/or database right".
- Thames Water open data: [their terms](https://data.thameswater.co.uk/s/terms-of-service), which are not the OGL. Check them before redistributing raw data.
- OS Open Rivers: Contains OS data © Crown copyright.
- OpenStreetMap: © OpenStreetMap contributors (ODbL).
