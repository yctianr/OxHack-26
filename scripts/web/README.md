# Spillcast web map

Run from the repo root (needs `pip install pyproj rasterio pillow` on top of requirements.txt), in order:

    python scripts/web/rivers.py      # OS Open Rivers links in the map box -> data/interim/web_links.pkl
    python scripts/web/terrain.py     # Terrarium tiles (AWS) + EA LIDAR 20 m blend -> web/data/elevation.png
    python scripts/web/texture.py     # hillshade texture -> web/data/terrain.jpg
    python scripts/web/data.py        # outfalls.json (sites, daily Explain/Forecast/observed, downstream links, flow paths) + rivers.json
    python scripts/web/build_stats.py # stats.json (scores, calibration)

Then serve `web/` with any static server (`python -m http.server -d web`) or drag it into Netlify / GitHub Pages.
The page loads deck.gl 9.4.0 and Chart.js 4.4.1 from CDNs. River glow is a relative index, not a measured % sewage.
