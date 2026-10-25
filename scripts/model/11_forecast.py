"""7-day spill forecast from the physics water balance, with the weather forecast's own uncertainty.

Each works runs on from the end of the observed data (common.DATA_END) with the fold-B parameters from 9_wb_fit.py:
  rain        ECMWF IFS 0.25° ensemble (51 members) from Open-Meteo, hourly, at each EA rain gauge, mixed per works
              exactly as the observed rain is (its two nearest gauges)
  evaporation Open-Meteo daily FAO reference evaporation forecast at Oxford, spread over the hours
  river flow  Thames at Farmoor held at its last observed value (it moves slowly; used by river-driven works only)
  state       soil, groundwater, routed rain and storm tank at the end of the observed data (deterministic run)
For every member, 4 runs with the works' daily inflow error (AR(1), as in the hindcast): 204 runs per works.
Spilling starts only at capacity with a full storm tank; no spill record is used.
Writes data/interim/wb_forecast.pkl (works x day: chance of a spill, spill-hours, m3, mean rain) and
data/interim/wb_forecast_drivers.json (ensemble-mean hourly rain per gauge, evaporation, flow, local hour, and each
works' start-of-day state under ensemble-mean rain, for the website's rain slider). Run after 9_wb_fit.py."""
import importlib.util
import json
import os
import urllib.request
import numpy as np
import pandas as pd
from common import DATA_END, INT
import wb

DAYS, DRAWS = 7, 4
spec = importlib.util.spec_from_file_location("wbfit", os.path.join(os.path.dirname(os.path.abspath(__file__)), "9_wb_fit.py"))
wbfit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wbfit)
inp, lab, si, ldays, local_day, udays, utc_day, pet_h, wet_h = wbfit.drivers()
lhour = inp.index.tz_convert("Europe/London").hour.values
P = pd.read_csv(os.path.join(INT, "wb_params.csv")).query("fold == 'B'").set_index("permit")
start = pd.Timestamp(DATA_END, tz="UTC") + pd.Timedelta(hours=1)
hrs = pd.date_range(start, periods=24 * DAYS, freq="h", tz="UTC")
d0, d1 = str(hrs[0].date()), str(hrs[-1].date())
gauges = sorted(c[5:] for c in inp.columns if c.startswith("rain_"))
loc = {(i.get("stationReference") or i["notation"].split("_")[-1]): (i["lat"], i["long"])    # gauge id (256230TP) -> location
       for i in json.load(open(os.path.join(INT, "st_rainfall.json")))["items"] if "lat" in i}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=120))


# ensemble rain at every gauge: (gauge, member, hour), mm per hour
lat, lon = ",".join(str(loc[g][0]) for g in gauges), ",".join(str(loc[g][1]) for g in gauges)
ens = get(f"https://ensemble-api.open-meteo.com/v1/ensemble?latitude={lat}&longitude={lon}&hourly=precipitation"
          f"&models=ecmwf_ifs025&start_date={d0}&end_date={d1}&timezone=GMT")
ens = ens if isinstance(ens, list) else [ens]
R = []
for e in ens:
    h = e["hourly"]
    t = pd.to_datetime(h["time"]).tz_localize("UTC")
    cols = [k for k in h if k.startswith("precipitation")]
    m = pd.DataFrame({k: h[k] for k in cols}, index=t).reindex(hrs).astype(float)
    R.append(np.nan_to_num(m.values.T))                                  # members x hours
R = np.stack(R)
issued = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC")
et = get(f"https://api.open-meteo.com/v1/forecast?latitude=51.75&longitude=-1.26&daily=et0_fao_evapotranspiration"
         f"&start_date={d0}&end_date={(hrs[-1] + pd.Timedelta(days=1)).date()}&timezone=Europe%2FLondon")
et = pd.Series(et["daily"]["et0_fao_evapotranspiration"], index=pd.to_datetime(et["daily"]["time"])).astype(float)
fl = hrs.tz_convert("Europe/London")
pet_f = et.reindex(fl.tz_localize(None).normalize()).ffill().bfill().values / 24.0
wet_f = np.full(len(hrs), wet_h[-1])
lh_f = fl.hour.values
day_f = (hrs - hrs[0]).days

rows, states = [], {}
rng = np.random.default_rng(0)
for p, row in P.iterrows():
    prm = wb.params_of(row)
    a, b, d1_, d2_ = si.loc[p, ["rain1", "rain2", "d1", "d2"]]
    w1 = (1 / d1_ ** 2) / (1 / d1_ ** 2 + 1 / d2_ ** 2)
    _, s_end = wb.hourly_states(prm, w1 * inp[f"rain_{a}"].values + (1 - w1) * inp[f"rain_{b}"].values, pet_h, wet_h, lhour)
    rain_m = w1 * R[gauges.index(a)] + (1 - w1) * R[gauges.index(b)]    # members x hours
    sig, rho = prm["sig"], prm["rho"]
    spill = np.zeros((rain_m.shape[0] * DRAWS, len(hrs)))
    j = 0
    for m in range(rain_m.shape[0]):
        for _ in range(DRAWS):
            e = np.empty(DAYS)
            e[0] = rng.standard_normal() * sig
            for d in range(1, DAYS):
                e[d] = rho * e[d - 1] + np.sqrt(1 - rho ** 2) * sig * rng.standard_normal()
            mult = np.exp(e - sig ** 2 / 2)
            s = list(s_end)
            for t in range(len(hrs)):
                spill[j, t] = wb.step(prm, s, rain_m[m, t], pet_f[t], wet_f[t], lh_f[t], mult[day_f[t]])
            j += 1
    on = spill > 1e-6
    # start-of-day states under ensemble-mean rain, for the page's one-day rerun
    s, sod = list(s_end), []
    mean_rain = rain_m.mean(0)
    for t in range(len(hrs)):
        if t % 24 == 0:
            sod.append([float(f"{x:.5g}") for x in s])
        wb.step(prm, s, mean_rain[t], pet_f[t], wet_f[t], lh_f[t])
    states[p] = sod
    for d in range(DAYS):
        h = slice(24 * d, 24 * d + 24)
        rows.append(dict(site=p, date=str((hrs[0] + pd.Timedelta(days=d)).date()), p=float(on[:, h].any(1).mean()),
                         hours=float(on[:, h].sum(1).mean()), vol_m3=float(spill[:, h].sum(1).mean()),
                         rain_mm=float(rain_m[:, h].sum(1).mean()), rain_p90=float(np.quantile(rain_m[:, h].sum(1), 0.9))))
F = pd.DataFrame(rows)
F.to_pickle(os.path.join(INT, "wb_forecast.pkl"))
drv = dict(issued=issued, model="ECMWF IFS 0.25° ensemble via Open-Meteo", members=int(R.shape[1]),
           dates=[str((hrs[0] + pd.Timedelta(days=d)).date()) for d in range(DAYS)], gauges=gauges,
           rain=[[[round(float(x), 2) for x in R[g].mean(0)[24 * d:24 * d + 24]] for d in range(DAYS)] for g in range(len(gauges))],
           pet=[[round(float(x), 4) for x in pet_f[24 * d:24 * d + 24]] for d in range(DAYS)],
           wet=[[round(float(x), 3) for x in wet_f[24 * d:24 * d + 24]] for d in range(DAYS)],
           lh=[[int(x) for x in lh_f[24 * d:24 * d + 24]] for d in range(DAYS)], states=states)
json.dump(drv, open(os.path.join(INT, "wb_forecast_drivers.json"), "w"))
print(f"issued {issued}; {R.shape[1]} members; {F.site.nunique()} works x {DAYS} days")
print(F.pivot_table(index="date", values=["p", "rain_mm"], aggfunc={"p": lambda x: (x >= 0.5).sum(), "rain_mm": "mean"})
      .rename(columns={"p": "works likely to spill", "rain_mm": "mean rain (mm)"}).round(1).to_string())
