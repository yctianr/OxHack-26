"""Build an hourly table per overflow (61 sites within 25 km): spill on/off, offline mask, and candidate inputs.
Output: data/interim/hourly/<permit>.parquet-like CSV.gz and a shared inputs table."""
import os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
os.makedirs(os.path.join(_ROOT, "data", "interim"), exist_ok=True)
os.chdir(os.path.join(_ROOT, "data", "interim"))  # intermediate tables are read and written here

import glob, os
import numpy as np
import pandas as pd

R = os.path.join(_ROOT, "data") + "/"
OUT = R + "interim/"
TZ = "Europe/London"
idx = pd.date_range("2022-04-01", "2026-10-22 23:00", freq="1h", tz="UTC")

# ---- shared inputs ----
inp = pd.DataFrame(index=idx)
gauge_xy = {}
import json
for prop in ("rainfall", "waterFlow"):
    for s in json.load(open(f"st_{prop}.json"))["items"]:
        gauge_xy[s.get("stationReference") or s.get("notation")] = (s.get("easting"), s.get("northing"))
gauge_xy["1290TH"] = (444853, 209919)
for f in sorted(glob.glob(R + "raw/gauges/rain_*.csv")):
    ref = f.split("rain_")[1][:-4]
    r = pd.read_csv(f, parse_dates=["dateTime"])
    r = r.set_index(pd.to_datetime(r.dateTime, utc=True))["value"].clip(lower=0, upper=50)
    h = r.resample("1h").sum(min_count=1).reindex(idx)
    inp[f"rain_{ref}"] = h
for f in sorted(glob.glob(R + "raw/gauges/flow_*.csv")):
    ref = f.split("flow_")[1][:-4]
    r = pd.read_csv(f, parse_dates=["dateTime"])
    d = r.assign(date=pd.to_datetime(r.dateTime).dt.tz_localize(None).dt.normalize()).groupby("date")["value"].mean()
    d = np.log(d.clip(lower=1e-3)).shift(1)                       # yesterday's mean: known at forecast time
    loc = idx.tz_convert(TZ).tz_localize(None).normalize()
    inp[f"lflow_{ref}"] = d.reindex(loc).interpolate(limit=7).values
for f in sorted(glob.glob(R + "raw/openmeteo/era5land_*.csv")):
    c = f.split("era5land_")[1][:-4]
    o = pd.read_csv(f, parse_dates=["time"]).set_index("time")
    o.index = o.index.tz_localize("UTC")
    o = o.reindex(idx)
    inp[f"era5rain_{c}"] = o.precipitation
    inp[f"sm100_{c}"] = o.soil_moisture_28_to_100cm.shift(24)       # lag a day
    inp[f"sm28_{c}"] = o.soil_moisture_7_to_28cm.shift(24)
print("inputs:", inp.shape, "missing share by col (top):", inp.isna().mean().sort_values().tail(5).round(3).to_dict())
inp.to_pickle(OUT + "inputs_hourly.pkl")

# ---- labels ----
sites = pd.read_csv("sites61.csv")
ev = pd.read_csv(R + "raw/events.csv")
off = pd.read_csv(R + "raw/offline.csv")
loc = lambda s: pd.to_datetime(s).dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")
def clean(e):
    """Label cleaning: merge spills separated by < 1 h, then drop spills shorter than 15 min (monitor chatter)."""
    iv = sorted(zip(pd.to_datetime(e.start), pd.to_datetime(e.stop)))
    out = []
    for s_, t_ in iv:
        if out and (s_ - out[-1][1]) < pd.Timedelta("1h"):
            out[-1][1] = max(out[-1][1], t_)
        else:
            out.append([s_, t_])
    out = [(s_, t_) for s_, t_ in out if t_ - s_ >= pd.Timedelta("15min")]
    return pd.DataFrame(out, columns=["start", "stop"]).astype(str)


lab, lab_clean = {}, {}
for p in sites.permitNumber:
  e0 = ev[(ev.permitNumber == p) & ev.stop.notna()]
  for e, store_ in ((e0, lab), (clean(e0), lab_clean)):
    y = np.zeros(len(idx), dtype=np.int8)
    m = np.ones(len(idx), dtype=bool)
    for s_, t_ in zip(loc(e.start), loc(e.stop)):
        if pd.isna(s_) or pd.isna(t_):
            continue
        i0, i1 = idx.searchsorted(s_.floor("h")), idx.searchsorted(t_.ceil("h"))
        y[i0:i1] = 1
    o = off[off.permitNumber == p].dropna()
    for s_, t_ in zip(loc(o.start), loc(o.stop)):
        if pd.isna(s_) or pd.isna(t_):
            continue
        m[idx.searchsorted(s_.floor("h")):idx.searchsorted(t_.ceil("h"))] = False
    first = loc(ev[ev.permitNumber == p].start).min()
    m &= idx >= first.floor("h") if pd.notna(first) else False
    store_[p] = (y, m)
pd.to_pickle(lab, OUT + "labels_hourly.pkl")
pd.to_pickle(lab_clean, OUT + "labels_hourly_clean.pkl")
print("label hours raw vs clean:", sum(v[0].sum() for v in lab.values()), sum(v[0].sum() for v in lab_clean.values()))

# nearest gauges per site
def near(prefix, x, y, k):
    refs = [c.split("_", 1)[1] for c in inp.columns if c.startswith(prefix + "_")]
    refs = [r for r in refs if r in gauge_xy and gauge_xy[r][0]]
    d = sorted((np.hypot(gauge_xy[r][0] - x, gauge_xy[r][1] - y), r) for r in refs)
    return d[:k]
rows = []
for _, s in sites.iterrows():
    rn = near("rain", s.x, s.y, 2)
    rows.append(dict(permit=s.permitNumber, name=s.locationName, rain1=rn[0][1], d1=rn[0][0], rain2=rn[1][1], d2=rn[1][0],
                     cell=s.cell.replace(",", "_")))
pd.DataFrame(rows).to_csv(OUT + "site_inputs.csv", index=False)
print(pd.DataFrame(rows).head())
