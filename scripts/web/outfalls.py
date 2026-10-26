"""The 61 overflows for the website, with what their monitors recorded each day of the test year. Writes web/data/outfalls.json.

Per overflow: name, overflow type and receiving river (Thames Water's 2025 EDM annual return), location, and for each
day of the held-out test year (fold B) whether its monitor recorded a spill and for how many hours (None = no usable
record). Read by quality.py and physics.py (the days) and by model.html (the backtest).
Run from the repo root after scripts/model/04_stat_evaluate.py."""
import json
import numpy as np
import pandas as pd
from pyproj import Transformer

t2ll = Transformer.from_crs(27700, 4326, always_xy=True)
s = pd.read_csv("data/interim/sites61.csv")
ar = pd.read_excel("data/raw/annual_returns/tw_edm_2025.xlsx", sheet_name=0, header=5)
ar.columns = [" ".join(str(c).split()) for c in ar.columns]
pc = "EA Permit Reference (EA Consents Database)"
ar = ar.drop_duplicates(pc).set_index(pc)
TE = pd.read_pickle("data/interim/eval_predictions.pkl")
B = TE[TE.fold == "B"]
dates = sorted(B.date.unique())
di = {d: i for i, d in enumerate(dates)}

TYPE = {"Storm tank at WwTW": "works", "Storm tank at WwTW - with treatment": "works", "Inlet SO at WwTW": "works",
        "Inlet SO at WwTW - with treatment": "works", "Storm discharge at pumping station": "pumping",
        "SO on sewer network": "network"}
sites = []
for _, r in s.iterrows():
    p = r.permitNumber
    a = ar.loc[p] if p in ar.index else None
    if a is not None:
        t = TYPE.get(a["Storm Discharge Asset Type"], "works")
    else:
        t = "works" if r.locationName in ("Little Milton", "Tetsworth", "Weston-On-The-Green STW") else "unknown"
    water = str(a["Receiving Water / Environment (common name) (EA Consents Database)"]).title() if a is not None else ""
    name = str(a["Site Name (WaSC operational) [optional]"]) if a is not None else r.locationName
    if p == "TEMP.3002":
        name = "Weston-on-the-Green STW (2)"
    lon, lat = t2ll.transform(r.x, r.y)
    rec = dict(id=p, name=name.replace("XX (Bucknell) SPS", "Bucknell SPS"), place=r.locationName, type=t, water=water,
               lon=round(lon, 5), lat=round(lat, 5))
    b = B[B.site == p]
    if len(b):
        def daily(col, nd):
            v = [None] * len(dates)
            for d, x in zip(b.date, b[col]):
                v[di[d]] = round(float(x), nd)
            return v
        rec["obs"], rec["hours"] = daily("y", 0), daily("h", 1)
    sites.append(rec)

json.dump(dict(dates=[pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates], sites=sites),
          open("web/data/outfalls.json", "w"), separators=(",", ":"))
print(f"{len(sites)} overflows, {sum('obs' in x for x in sites)} with monitor records; {len(dates)} days")
