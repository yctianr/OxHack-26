# Spillcast

**Which sewage works should the Environment Agency inspect first?** Spillcast models every Thames Water treatment works within 25 km of Oxford with a physics water balance, fitted only to the flow each works treated, and flags the works that spill when the physics says they shouldn't.

Built for **OxHack 2026** (HRT prize: "Best Use of Data for Predictions and Decision Making").

**Start here: [docs/01-overview.md](docs/01-overview.md)**, then [docs/09-handover.md](docs/09-handover.md) for the current state and next steps.

## Run the website

Everything the site shows is pre-built in `web/`: no data download or Python packages needed.

```bash
python3 -m http.server 8000 -d web      # then open http://localhost:8000
```

- **Use the server, not a double-click:** browsers block `file://` pages from loading their data.
- **It needs internet** for the map and chart libraries.
- **`index.html`** opens on the regulator watchlist ("Inspect works"); "Spills by day" (`#day`) shows both models day by day. **`scenario.html`** lets you change the rain at any overflow and reruns the physics model in the browser.
- **To host it**, upload `web/` to any static host (e.g. <https://app.netlify.com/drop>).

More: [docs/06-website.md](docs/06-website.md).

## Repo layout

```
docs/                 01 overview · 02 physical model (main) · 03 statistical model (backup) · 04 watchlist
                      05 data · 06 website · 07 Oxford context · 08 prior work · 09 handover · sources · archive/
scripts/model/        1–7 data, cleaning and the statistical model; 8–10 and wb.py the physics water balance;
                      tanks.csv sourced storm-tank volumes; common.py shared code
scripts/web/          builds web/data/*.json and web/watchlist/data.json (order in scripts/web/README.md)
scripts/fetch_data.py Thames Water alerts and status, EA Hydrology, EA LIDAR (stdlib only)
scripts/archive/      pre-audit exploration (superseded)
web/                  the website (static): index.html, scenario.html and pre-built data
UI-first-draft.html   Keira's 2D design that scenario.html follows
prototype/            early dummy-data UI prototype
edm_datasets/, tdv_datasets/, Rainfall Data/   teammates' downloads and cleaning (cross-checks; the pipeline doesn't read them)
data/raw/, data/interim/                        fetched and cleaned data (git-ignored, ~460 MB)
```

## Rebuild everything

Only needed to change the models or refresh the data. From the repo root:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && source .venv/bin/activate

# 1. fetch (about 15 min)
python scripts/fetch_data.py thames-alerts && python scripts/fetch_data.py events && python scripts/fetch_data.py thames-status
python scripts/fetch_data.py dtm --res 20
# 2. download by hand (links in docs/05-data.md, "Rebuilding the data"): Thames Water treated volumes and annual returns,
#    the ORIC capacity sheet, OS Open Rivers
# 3. clean data and the statistical backup
for s in 1_fetch_gauges 2_sites 3_audit 4_build_clean 5_evaluate 6_site_cards; do python scripts/model/$s.py; done
# 4. physics water balance (8 also downloads daily evaporation from Open-Meteo)
for s in 8_wb_prep 9_wb_fit 10_wb_evaluate 11_forecast; do python scripts/model/$s.py; done
# 5. website data (extra packages: pip install pyproj rasterio pillow)
for s in rivers terrain texture data physics whatif build_stats watchlist; do python scripts/web/$s.py; done
```

## Refresh the forecast

The site's last 7 days are a physics forecast made when the data was last built. To bring it up to date: set `DATA_END` in `scripts/model/common.py` to the last full hour of yesterday (UTC), then

```bash
python scripts/fetch_data.py thames-alerts && python scripts/fetch_data.py events && python scripts/model/1_fetch_gauges.py
for s in 3_audit 4_build_clean 5_evaluate 6_site_cards 8_wb_prep 9_wb_fit 10_wb_evaluate 11_forecast; do python scripts/model/$s.py; done
for s in data whatif watchlist physics build_stats; do python scripts/web/$s.py; done
```

About 25 minutes in all, most of it the alert download. More: [docs/02-physical-model.md](docs/02-physical-model.md#forecast).

## Data licences

EA, OS Open Rivers and Find a Tender data: Open Government Licence. Open-Meteo: CC BY 4.0. Thames Water data: [their terms](https://data.thameswater.co.uk/s/terms-of-service), not an open licence. ORIC capacity sheet: not yet checked. Details: [docs/05-data.md](docs/05-data.md#licences-and-what-we-publish).
