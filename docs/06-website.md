# 06 · Website

A static site in `web/`: two pages over one 3D map of the rivers and works around Oxford. Everything it shows is pre-built and committed, so it runs without the data or Python.

## Run and host

```bash
python3 -m http.server 8000 -d web      # then open http://localhost:8000
```

- **Use the server, not a double-click:** browsers block `file://` pages from loading their data files.
- **It needs internet:** deck.gl 9.4.0, Chart.js 4.4.1 and fonts load from CDNs.
- **To host:** upload `web/` to any static host, e.g. drag it onto <https://app.netlify.com/drop>.
- **Testing without a browser window** (this machine has no Node): headless Chrome works.

  ```bash
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --use-angle=swiftshader \
    --enable-unsafe-swiftshader --virtual-time-budget=20000 --screenshot=shot.png http://localhost:8000/
  ```

## Pages

### `index.html`: the main page (dark theme)

| Tab | What it shows | Model |
| --- | --- | --- |
| **Inspect works** (default) | The regulator watchlist: works coloured by lead strength; an evidence file per works with findings, treated flow vs permitted flow, lowest-treatment dates, unexplained spill dates, Thames Water's stated reason, estimated spill volume, storm tank, records to request, "Copy case summary" | [04-watchlist.md](04-watchlist.md) |
| **Spills by day** (`#day`) | A day slider over the test year. Views: *What happened* (monitors), *Physics model* (default), *Statistical backup*, *Statistical forecast*. Card per overflow, top-10 list, a scores table of both models, the physics model's calibration | [02](02-physical-model.md), [03](03-statistical-model.md) |

### `scenario.html`: rain scenarios (light theme)

Layout and controls follow Keira's `UI-first-draft.html`, with the 3D map in place of the 2D sketch.

- **Day slider:** opens on 16 Jan 2026, a storm day in the test year.
- **River sewage glow toggle**, with counts of overflows likely to spill, unlikely, and recorded by monitors.
- **Overflow list and card:** chance of a spill (physics model, or the statistical backup where there is no treated-flow data), what the monitor recorded, spill volume and hours, the statistical model's chance, storm tank and its source, and the works' test-year total.
- **Rainfall slider:** starts at the rain measured at that overflow that day. Moving it reruns that day of the physics model in the browser from the works' start-of-day state (soil, groundwater, storm tank), with the day's hourly rain pattern scaled to the new total. At the measured rain it reproduces the full model (median difference in daily chance 0.000). For overflows on the backup it moves the statistical model's rain store instead.

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
