"""The physics water balance, packed for the website. Writes web/data/physics.json.

Physics only: spilling starts at the works' measured capacity once its storm tank is full (wb1_* in 07_wb_fit.py), so no
spill record shapes these numbers. Fold B parameters; the website's days are the held-out test year (outfalls.json),
followed by the 7-day forecast from scripts/model/09_forecast.py when it has been run.
Per works: daily chance of a spill, spill-hours and spill volume (the ensembles from 07_wb_fit.py and 09_forecast.py), the
fitted parameters, and the state of its stores at the start of each day (soil deficit, groundwater, routed rain, tank).
Shared: hourly rain at each gauge (ensemble mean on forecast days), evaporation, Thames flow at Farmoor and local hour
for each day, so the river map's What-if mode can rerun one day of the model with different rain, storm tank or
capacity (web/index.html). The check at the end reruns that one-day version here at the rain that fell and compares it
with the full ensemble.
Run from the repo root after 07_wb_fit.py, 09_forecast.py and outfalls.py."""
import importlib.util
import json
import os
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "scripts/model")
import wb
spec = importlib.util.spec_from_file_location("wbfit", "scripts/model/07_wb_fit.py")
wbfit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wbfit)

O = json.load(open("web/data/outfalls.json"))
dates = O["dates"]
D = pd.read_pickle("data/interim/wb_predictions.pkl")
D = D[D.fold == "B"].assign(day=lambda d: pd.DatetimeIndex(d.date).strftime("%Y-%m-%d"))
P = pd.read_csv("data/interim/wb_params.csv").query("fold == 'B'").set_index("permit")
TANKS = pd.read_csv("scripts/model/tanks.csv").set_index("permit")
inp, lab, si, ldays, local_day, udays, utc_day, pet_h, wet_h = wbfit.drivers()
idx = inp.index
lhour = idx.tz_convert("Europe/London").hour.values
utc = np.asarray(idx.strftime("%Y-%m-%d"))
hours = {d: np.flatnonzero(utc == d) for d in dates}                       # the 24 UTC hours of each day
gauges = sorted(c[5:] for c in inp.columns if c.startswith("rain_"))
FC = os.path.exists("data/interim/wb_forecast.pkl")
if FC:
    F = pd.read_pickle("data/interim/wb_forecast.pkl")
    FD = json.load(open("data/interim/wb_forecast_drivers.json"))
    assert FD["gauges"] == gauges and pd.Timestamp(FD["dates"][0]) == pd.Timestamp(dates[-1]) + pd.Timedelta(days=1), \
        "forecast doesn't follow the observed days: rerun 09_forecast.py"


def one_day(prm, s0, rain, pet, wet, lh, n=200, seed=0):
    """The page's version: one UTC day from its start state, inflow error drawn once per run. Returns p, hours, m3."""
    e = np.random.default_rng(seed).standard_normal(n) * prm["sig"]
    spilled, hrs, vol = 0, 0.0, 0.0
    for j in range(n):
        s, mult, on = list(s0), np.exp(e[j] - prm["sig"] ** 2 / 2), False
        for t in range(len(rain)):
            sp = wb.step(prm, s, rain[t], pet[t], wet[t], lh[t], mult)
            if sp > 1e-6:
                on, hrs, vol = True, hrs + 1, vol + sp
        spilled += on
    return spilled / n, hrs / n, vol / n


works, check = {}, []
for p, g in D.groupby("site"):
    g = g.set_index("day").reindex(dates)
    r = P.loc[p]
    prm = wb.params_of(r)
    a, b, d1, d2 = si.loc[p, ["rain1", "rain2", "d1", "d2"]]
    w1 = (1 / d1 ** 2) / (1 / d1 ** 2 + 1 / d2 ** 2)
    rain = w1 * inp[f"rain_{a}"].values + (1 - w1) * inp[f"rain_{b}"].values
    S, _ = wb.hourly_states(prm, rain, pet_h, wet_h, lhour)
    w = dict(p=[round(float(x), 3) for x in g.wb1_p], h=[round(float(x), 1) for x in g.wb1_hours],
             v=[int(round(x)) for x in g.wb1_vol_m3], cap_m3d=int(round(r.cap_m3d)), tank_m3=int(round(r.tank_m3)),
             tank_src=f"source: {TANKS.cite[p]}" if p in TANKS.index else "assumed: 2 hours at capacity",
             prm={k_: (int(v) if k_ == "mode" else float(f"{v:.6g}")) for k_, v in prm.items()},
             g=[gauges.index(a), gauges.index(b), round(float(w1), 4)],
             s=[[float(f"{x:.5g}") for x in S[hours[d][0]]] for d in dates])
    if FC:
        f = F[F.site == p].set_index("date").reindex(FD["dates"])
        w["p"] += [round(float(x), 3) for x in f.p]
        w["h"] += [round(float(x), 1) for x in f.hours]
        w["v"] += [int(round(x)) for x in f.vol_m3]
        w["rain_p90"] = [round(float(x), 1) for x in f.rain_p90]
        w["s"] += FD["states"][p]
    works[p] = w
    for d in dates[::29]:                                   # spot-check the page's one-day version
        h = hours[d]
        pj, hj, vj = one_day(prm, S[h[0]], rain[h], pet_h[h], wet_h[h], lhour[h])
        check.append((p, d, w["p"][dates.index(d)], pj, w["v"][dates.index(d)], vj))

drv = dict(gauges=gauges,
           rain=[[[round(float(inp[f"rain_{gg}"].values[i]), 2) for i in hours[d]] for d in dates] for gg in gauges],
           pet=[[round(float(pet_h[i]), 4) for i in hours[d]] for d in dates],
           wet=[[round(float(wet_h[i]), 3) for i in hours[d]] for d in dates],
           lh=[[int(lhour[i]) for i in hours[d]] for d in dates])
forecast = None
if FC:
    for gi in range(len(gauges)):
        drv["rain"][gi] += FD["rain"][gi]
    for k in ("pet", "wet", "lh"):
        drv[k] += FD[k]
    forecast = dict(start=len(dates), issued=FD["issued"], model=FD["model"], members=FD["members"])

all_dates = dates + (FD["dates"] if FC else [])
json.dump(dict(dates=all_dates, forecast=forecast, drivers=drv, works=works),
          open("web/data/physics.json", "w"), separators=(",", ":"))

c = pd.DataFrame(check, columns=["site", "date", "p_ens", "p_day", "v_ens", "v_day"])
print(f"{len(works)} works; {len(dates)} observed days + {len(all_dates) - len(dates)} forecast; "
      f"{os.path.getsize('web/data/physics.json') / 1e6:.2f} MB")
print(f"one-day version vs full ensemble, {len(c)} site-days: |dp| median {np.median(abs(c.p_ens - c.p_day)):.3f}, "
      f"p90 {np.quantile(abs(c.p_ens - c.p_day), .9):.3f}; volume correlation {np.corrcoef(c.v_ens, c.v_day)[0, 1]:.3f}")
