"""Exploratory analysis of Oxford STW (TEMP.2827) spills vs rain and wetness, to inform model design."""
import os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
RAW = os.path.join(_ROOT, "data", "raw") + "/"
os.makedirs(os.path.join(_ROOT, "data", "interim"), exist_ok=True)
os.chdir(os.path.join(_ROOT, "data", "interim"))  # intermediate tables are read and written here

import numpy as np
import pandas as pd

TZ = "Europe/London"

# --- rain, 15 min -> hourly (UTC) ---
r = pd.read_csv(RAW + "hydro_rain_osney_15min.csv", parse_dates=["dateTime"])
print("rain quality:", r.groupby("quality")["value"].agg(["count", "mean", "max"]).round(3).to_string())
r = r.set_index("dateTime")["value"].clip(lower=0)
r.index = r.index.tz_localize("UTC")  # hydrology API returns UTC
rain_h = r.resample("1h").sum(min_count=1)
print("rain hours missing:", rain_h.isna().mean().round(4), "annual mm:", (rain_h.resample("YE").sum()).round(0).to_dict())
rain_h = rain_h.fillna(0)

# --- Oxford spills from alerts -> events (localise naive UK time) ---
a = pd.read_csv(RAW + "thames_alerts_oxford.csv")
a = a[a.permitNumber == "TEMP.2827"].copy()
a["t"] = pd.to_datetime(a.datetime).dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")
a = a.dropna(subset=["t"]).sort_values("t")
ev, off, s, o = [], [], None, None
for _, x in a.iterrows():
    if x.alertType == "Start":
        s = x.t
    elif x.alertType == "Stop" and s is not None:
        ev.append((s, x.t)); s = None
    elif x.alertType == "Offline start":
        o = x.t
    elif x.alertType == "Offline stop" and o is not None:
        off.append((o, x.t)); o = None
ev = pd.DataFrame(ev, columns=["start", "stop"])
ev["hours"] = (ev.stop - ev.start).dt.total_seconds() / 3600
print(f"\nOxford events: {len(ev)}; total hours {ev.hours.sum():.0f}")
print("duration quantiles (h):", ev.hours.quantile([.1, .25, .5, .75, .9, .99]).round(1).to_dict())
gaps = (ev.start.shift(-1) - ev.stop).dt.total_seconds() / 3600
print("gap to next event < 6 h:", (gaps < 6).mean().round(2), "< 24 h:", (gaps < 24).mean().round(2))
print("hours by water year:", ev.groupby(ev.start.dt.tz_convert(TZ).apply(lambda t: t.year + (t.month >= 10))).hours.agg(["count", "sum"]).round(0).to_dict())

# --- hourly on/off series with offline mask ---
idx = pd.date_range("2022-11-24", "2026-10-24 20:00", freq="1h", tz="UTC")
spill = pd.Series(0.0, idx)
for s_, e_ in zip(ev.start, ev.stop):
    spill[s_.floor("h"):e_.ceil("h") - pd.Timedelta("1h")] = 1
mask = pd.Series(True, idx)
for s_, e_ in off:
    mask[s_.floor("h"):e_.ceil("h")] = False
rain_h = rain_h.reindex(idx).fillna(0)
print(f"hourly: {spill[mask].mean():.3f} spill fraction; {(~mask).mean():.3f} offline")

# --- daily table ---
day = pd.DataFrame({"spill_h": spill[mask].tz_convert(TZ).resample("D").sum(),
                    "rain": rain_h.tz_convert(TZ).resample("D").sum()})
day["y"] = (day.spill_h > 0).astype(int)
day.index = day.index.tz_localize(None)
def daily(f, col):
    d = pd.read_csv(RAW + f, parse_dates=["date"]).groupby("date")["value"].mean()
    day[col] = d.reindex(day.index).interpolate(limit=5)
daily("hydro_level_cherwell_oxford_1490TH_max.csv", "cher_lvl")
daily("hydro_flow_thames_farmoor_1100TH_mean.csv", "thames_q")
daily("hydro_gw_oxford_SP50_72.csv", "gw")
day = day.dropna(subset=["spill_h"])
print("\nspill-day rate:", day.y.mean().round(3), "n days", len(day))

# spill-hours vs drivers, binned
for c in ["rain", "cher_lvl", "thames_q", "gw"]:
    q = pd.qcut(day[c].rank(method="first"), 5, labels=False)
    print(c, "quintile -> P(spill), mean hours:",
          day.groupby(q).agg(p=("y", "mean"), h=("spill_h", "mean")).round(2).values.tolist())

# event duration vs wetness at start
ev["d"] = ev.start.dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
ev = ev.join(day[["thames_q", "cher_lvl", "gw"]], on="d")
ev["rain48"] = [rain_h[s_ - pd.Timedelta("48h"):s_].sum() for s_ in ev.start]
ev["rain_during"] = [rain_h[s_:e_].sum() for s_, e_ in zip(ev.start, ev.stop)]
print("\nSpearman with log event hours:",
      ev[["hours", "thames_q", "cher_lvl", "gw", "rain48", "rain_during"]].corr("spearman")["hours"].round(2).to_dict())
ev.to_csv("oxford_events.csv", index=False)
day.to_csv("oxford_day.csv")
pd.DataFrame({"rain": rain_h, "spill": spill, "mask": mask}).to_csv("oxford_hourly.csv")
