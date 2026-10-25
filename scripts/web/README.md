# Spillcast website

**To view the site you don't need anything here.** The built data is already committed in `web/`. From the repo root:

    python3 -m http.server 8000 -d web      # then open http://localhost:8000/scenario.html

Open it through the server, not by double-clicking `web/scenario.html`: browsers block a `file://` page from loading its data.
The page loads deck.gl 9.4.0, Chart.js 4.4.1 and its fonts from CDNs, so it needs an internet connection.
To host it, upload the `web/` folder to any static host (Netlify Drop, GitHub Pages, Cloudflare Pages).

## Rebuilding the site's data

Only needed after the models or data change. It needs the full `data/` folder (see the main README) and
`pip install pyproj rasterio pillow` on top of requirements.txt. Run from the repo root, in order:

    python scripts/web/rivers.py      # OS Open Rivers links in the map box -> data/interim/web_links.pkl
    python scripts/web/terrain.py     # Terrarium tiles (AWS) + EA LIDAR 20 m blend -> web/data/elevation.png
    python scripts/web/texture.py     # hillshade texture -> web/data/terrain.jpg
    python scripts/web/data.py        # outfalls.json (sites, statistical chances, monitor results, downstream links, flow paths) + rivers.json
    python scripts/web/physics.py     # physics.json: physics model per works (test year + 7-day forecast), states and drivers for the in-browser rerun, glow scale (after 9_wb_fit.py, 11_forecast.py, data.py)
    python scripts/web/whatif.py      # whatif.json: statistical backup's rain response (after data.py)
    python scripts/web/build_stats.py # stats.json: both models scored on the same held-out days (after 5 and 9)
    python scripts/web/watchlist.py   # watchlist/data.json: the regulator watchlist (after scripts/model/8, 9, 10)
    python scripts/web/quality.py     # quality.json: E. coli and ammonia every 100 m for river.html (after physics.py)

The river glow is the physics model's spill volume per km of river upstream: a relative index, not water quality.
Watchlist leads are reasons to look, not findings of a breach; the method and thresholds are at the top of
`watchlist.py` and on the page. Pages and data files: docs/06-website.md.
