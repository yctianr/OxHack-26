# 06 · Website

A static site in `web/`: one page over a 3D map of the rivers and works around Oxford. Everything it shows is pre-built and committed, so it runs without the data or Python.

## Run and host

```bash
python3 -m http.server 8000 -d web      # then open http://localhost:8000/scenario.html
```

- **Use the server, not a double-click:** browsers block `file://` pages from loading their data files.
- **It needs internet:** deck.gl 9.4.0, Chart.js 4.4.1 and fonts load from CDNs.
- **To host:** upload `web/` to any static host, e.g. drag it onto <https://app.netlify.com/drop>.
- **Testing without a browser window** (this machine has no Node): headless Chrome works.

  ```bash
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --use-angle=swiftshader \
    --enable-unsafe-swiftshader --virtual-time-budget=20000 --screenshot=shot.png http://localhost:8000/scenario.html
  ```

## Pages

### `scenario.html`: rain scenarios (light theme)

Layout and controls follow Keira's first 2D UI draft, with the 3D map in place of the 2D sketch.

- **Day slider:** the test year, then 7 forecast days marked "forecast"; opens on today. On forecast days the chance comes from the physics model run on every member of the ECMWF ensemble rain forecast; monitors and the statistical model have nothing yet.
- **River sewage glow toggle**, with counts of overflows likely to spill, unlikely, and recorded by monitors.
- **Overflow list and card:** chance of a spill (physics model, or the statistical backup where there is no treated-flow data), what the monitor recorded, spill volume and hours, the statistical model's chance, storm tank and its source, and the works' test-year total.
- **Rainfall slider:** starts at the rain measured at that overflow that day (on forecast days, the ensemble-mean forecast, with the 1-in-10 high case quoted). Moving it reruns that day of the physics model in the browser from the works' start-of-day state (soil, groundwater, storm tank), with the day's hourly rain pattern scaled to the new total. At the measured rain it reproduces the full model (median difference in daily chance 0.000). For overflows on the backup it moves the statistical model's rain store instead.

### `model.html`: how the model works

Linked from the map's "How the model works" button. The water balance as a diagram, the pipeline from data to advice, and the backtest on days the model never saw: works spilling each day (monitors vs the model's expected number), skill against baselines, a reliability diagram, per-works accuracy, the 23–24 Oct live test, fitted values against published figures, the river-quality method and the data sources.

### `river.html`: rivers, swimming and fish (light theme)

A clean 2D map (Esri Light Gray basemap, deck.gl) of the river network and the 52 sewage works with flow data (the 9 overflows without it are left off), with dotted lines to the river each one empties into. Two toggleable heatmaps colour the river within 40 km downstream of a works (the rest, with no works upstream, stays pale blue and reads "not assessed" on hover): E. coli (green where safe to swim, amber, then red) and ammonia (green where safe for fish, then purple; drawn as a core inside the E. coli band when both are on). One day slider runs over the test year and the 7-day forecast, with ‹ › to step a day; it opens on today. A histogram above it shows how many works spilled each day (monitors, then the forecast in blue-grey), so wet spells stand out. Hover on a river for E. coli, ammonia and "safe for swimmers / safe for fish"; hover on a discharge point for its spill that day.

A sidebar counts the works spilling on the chosen day and ranks them by volume (past days: monitor hours × the works' modelled spill rate; forecast: the physics forecast; scenario: your run); clicking one flies the map to it.

A **Rivers to avoid** button opens a right sidebar summarising the 7 forecast days: every river with a stretch not safe to swim in (E. coli from 235 per 100 mL) or harmful to fish (ammonia from 0.5 mg/L), with a day-by-day strip, "Avoid Sun–Wed", the peak level, the longest unsafe length and the works responsible; rivers with the most unsafe days come first, and clicking one flies there on its first unsafe day. Unnamed streams are named after the works just upstream. It always uses the official forecast, not your what-if changes.

Two modes:
- **Real data:** monitors on past days, the physics forecast on forecast days.
- **What if:** every works is rerun in the browser with the physics model for the chosen day, from its soil, groundwater and storm-tank state that morning. A rainfall slider sets the day's rain everywhere ("As it fell" restores it). Clicking a discharge point opens a card to change its storm-tank volume and treatment capacity, with that day's chance of a spill, spill-hours and volume as built vs with your change; the rivers update. Changes persist across days until reset, so you can step through a wet spell with a bigger tank.

Method and sources: [10-water-quality.md](10-water-quality.md).

## River glow

Each works' daily spill volume from the physics model, summed down the river network and divided by the river length upstream as a stand-in for dilution, on a log scale (median and 99th percentile of the non-zero values set the ends). Pumping stations and network overflows add nothing: they have no treated-flow data. It is a relative index, not water quality.

## Data files

| File | Built by | Contents |
| --- | --- | --- |
| `web/data/outfalls.json` | `scripts/web/data.py` | 61 overflows: location, type, receiving river, downstream links, flow path; daily statistical chances and monitor results, test year |
| `web/data/rivers.json` | `data.py` | River links with names, heights and the overflows upstream |
| `web/data/physics.json` | `scripts/web/physics.py` | Physics model per works: daily chance, spill-hours and volume; fitted parameters; start-of-day states; hourly rain, evaporation and river flow for the in-browser rerun; glow scale |
| `web/data/whatif.json` | `scripts/web/whatif.py` | Statistical model's rain response per overflow and day (backup slider) |
| `web/data/stats.json` | `scripts/web/build_stats.py` | Scores for both models on the same held-out days; calibration |
| `web/data/elevation.png`, `terrain.jpg` | `terrain.py`, `texture.py` | 3D terrain and its shaded texture |
| `web/watchlist/data.json` | `scripts/web/watchlist.py` | The watchlist, per works |

Rebuild order: [scripts/web/README.md](../scripts/web/README.md).
