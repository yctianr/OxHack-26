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

Layout and controls follow Keira's `UI-first-draft.html`, with the 3D map in place of the 2D sketch.

- **Day slider:** the test year, then 7 forecast days marked "forecast"; opens on today. On forecast days the chance comes from the physics model run on every member of the ECMWF ensemble rain forecast; monitors and the statistical model have nothing yet.
- **River sewage glow toggle**, with counts of overflows likely to spill, unlikely, and recorded by monitors.
- **Overflow list and card:** chance of a spill (physics model, or the statistical backup where there is no treated-flow data), what the monitor recorded, spill volume and hours, the statistical model's chance, storm tank and its source, and the works' test-year total.
- **Rainfall slider:** starts at the rain measured at that overflow that day (on forecast days, the ensemble-mean forecast, with the 1-in-10 high case quoted). Moving it reruns that day of the physics model in the browser from the works' start-of-day state (soil, groundwater, storm tank), with the day's hourly rain pattern scaled to the new total. At the measured rain it reproduces the full model (median difference in daily chance 0.000). For overflows on the backup it moves the statistical model's rain store instead.

### `river.html`: rivers, swimming and fish (light theme)

A clean 2D map (Esri Light Gray basemap, deck.gl) of the river network and the 61 discharge points, red where spilling that day. Two toggleable heatmaps: E. coli (yellow to dark red) and ammonia (purple, drawn as a core inside the E. coli band when both are on). One day slider runs over the test year and the 7-day forecast, with ‹ › to step a day; it opens on today. Hovering on a river gives E. coli, ammonia and "safe for swimmers / safe for fish" for that 100 m; hovering on a discharge point gives its spill that day. Method and sources: [10-water-quality.md](10-water-quality.md).

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
