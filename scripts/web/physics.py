"""The physics-only water balance, packed for the website. Writes web/data/physics.json.

Physics only: spilling starts at the works' measured capacity once its storm tank is full (wb1_* in 9_wb_fit.py), so no
spill record shapes these numbers. Fold B parameters, held-out test year (1 Oct 2025 to 22 Oct 2026).
Per works: daily chance of a spill, spill-hours and spill volume (the 200-run ensemble from 9_wb_fit.py), the fitted
parameters, and the state of its stores at the start of each day (soil deficit, groundwater, routed rain, tank).
Shared: hourly rain at each gauge, evaporation, Thames flow at Farmoor and local hour for each day, so the page can
rerun one day of the model with different rain (scenario.html). The check at the end reruns that one-day version here
at the rain that fell and compares it with the full ensemble.
Also the river-glow scale: on each day every river link gets (spill volume from the works upstream) divided by its
upstream river length, a stand-in for dilution; K and S99 are the median and 99th percentile of the non-zero values.
Run from the repo root after 9_wb_fit.py and data.py."""
import importlib.util
import json
import os
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "scripts/model")
import wb
spec = importlib.util.spec_from_file_location("wbfit", "scripts/model/9_wb_fit.py")
wbfit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wbfit)

O = json.load(open("web/data/outfalls.json"))
RV = json.load(open("web/data/rivers.json"))
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


def states(prm, rain):
    """Deterministic hourly run (no inflow error) from a warm-up year; returns D, G, routed, tank before each real hour."""
    n_warm = 8760
    r = np.r_[rain[:n_warm], rain]
    pet, wet = np.r_[pet_h[:n_warm], pet_h], np.r_[wet_h[:n_warm], wet_h]
    shape = 1 + wb.DIURNAL_AMP * np.cos(2 * np.pi * (np.r_[lhour[:n_warm], lhour] - wb.DIURNAL_PEAK_H) / 24)
    F, A, tf, k, p1, p2, C, As, V, mode = (prm[x] for x in ("F", "A", "tf", "k", "p1", "p2", "C", "As", "V", "mode"))
    af = np.exp(-1 / tf)
    ag = np.exp(-1 / (p1 * 24)) if mode == 0 else 0.0
    routed, Dd, G, tank = 0.0, 0.5 * p2, 0.0, 0.0
    out = np.empty((len(rain), 4))
    for t in range(len(r)):
        if t >= n_warm:
            out[t - n_warm] = Dd, G, routed, tank
        routed = af * routed + (1 - af) * r[t]
        Dd += pet[t] * (1 - Dd / p2) - r[t]
        rech = 0.0
        if Dd < 0:
            rech, Dd = -Dd, 0.0
        elif Dd > p2:
            Dd = p2
        if mode == 0:
            G = ag * G + rech
            infil = k * G
        else:
            infil = k * max(0.0, wet[t] - p1)
        q = F * shape[t] + infil + 10 * (A + As * (1 - Dd / p2)) * routed
        if q > C:
            tank = min(V, tank + q - C)
        else:
            tank -= min(tank, C - q)
    return out


def one_day(prm, s0, rain, pet, wet, lh, n=200, seed=0):
    """The page's version: one UTC day from its start state, inflow error drawn once per run. Returns p, hours, m3."""
    F, A, tf, k, p1, p2, C, As, V, mode, sig = (prm[x] for x in ("F", "A", "tf", "k", "p1", "p2", "C", "As", "V", "mode", "sig"))
    af, ag = np.exp(-1 / tf), (np.exp(-1 / (p1 * 24)) if mode == 0 else 0.0)
    e = np.random.default_rng(seed).standard_normal(n) * sig
    spilled, hrs, vol = 0, 0.0, 0.0
    for j in range(n):
        Dd, G, routed, tank = s0
        mult = np.exp(e[j] - sig ** 2 / 2)
        on = False
        for t in range(len(rain)):
            routed = af * routed + (1 - af) * rain[t]
            Dd += pet[t] * (1 - Dd / p2) - rain[t]
            rech = 0.0
            if Dd < 0:
                rech, Dd = -Dd, 0.0
            elif Dd > p2:
                Dd = p2
            if mode == 0:
                G = ag * G + rech
                infil = k * G
            else:
                infil = k * max(0.0, wet[t] - p1)
            q = (F * (1 + wb.DIURNAL_AMP * np.cos(2 * np.pi * (lh[t] - wb.DIURNAL_PEAK_H) / 24)) + infil
                 + 10 * (A + As * (1 - Dd / p2)) * routed) * mult
            if q > C:
                ex = q - C
                if ex <= V - tank:
                    tank += ex
                else:
                    sp = ex - (V - tank)
                    tank = V
                    if sp > 1e-6:
                        on, hrs, vol = True, hrs + 1, vol + sp
            else:
                tank -= min(tank, C - q)
        spilled += on
    return spilled / n, hrs / n, vol / n


works, check = {}, []
for p, g in D.groupby("site"):
    g = g.set_index("day").reindex(dates)
    r = P.loc[p]
    mode = 0 if r["mode"] == "soil" else 1
    prm = dict(mode=mode, F=r.foul_m3d / 24, A=r.area_ha, tf=r.tau_fast_h, k=r.k, p1=r.tau_g_d if mode == 0 else r.q0_m3s,
               p2=r.dmax_mm, C=r.cap_m3d / 24, As=r.area_sat_ha, V=r.tank_m3, sig=r.sigma)
    a, b, d1, d2 = si.loc[p, ["rain1", "rain2", "d1", "d2"]]
    w1 = (1 / d1 ** 2) / (1 / d1 ** 2 + 1 / d2 ** 2)
    rain = w1 * inp[f"rain_{a}"].values + (1 - w1) * inp[f"rain_{b}"].values
    S = states(prm, rain)
    works[p] = dict(p=[round(float(x), 3) for x in g.wb1_p], h=[round(float(x), 1) for x in g.wb1_hours],
                    v=[int(round(x)) for x in g.wb1_vol_m3], cap_m3d=int(round(r.cap_m3d)), tank_m3=int(round(r.tank_m3)),
                    tank_src=f"source: {TANKS.cite[p]}" if p in TANKS.index else "assumed: 2 hours at capacity",
                    prm={k_: (int(v) if k_ == "mode" else float(f"{v:.6g}")) for k_, v in prm.items()},
                    g=[gauges.index(a), gauges.index(b), round(float(w1), 4)],
                    s=[[float(f"{x:.5g}") for x in S[hours[d][0]]] for d in dates])
    for d in dates[::29]:                                   # spot-check the page's one-day version
        h = hours[d]
        pj, hj, vj = one_day(prm, S[h[0]], rain[h], pet_h[h], wet_h[h], lhour[h])
        check.append((p, d, works[p]["p"][dates.index(d)], pj, works[p]["v"][dates.index(d)], vj))

drv = dict(gauges=gauges,
           rain=[[[round(float(inp[f"rain_{gg}"].values[i]), 2) for i in hours[d]] for d in dates] for gg in gauges],
           pet=[[round(float(pet_h[i]), 4) for i in hours[d]] for d in dates],
           wet=[[round(float(wet_h[i]), 3) for i in hours[d]] for d in dates],
           lh=[[int(lhour[i]) for i in hours[d]] for d in dates])

# river-glow scale over link-days
ix = {s["id"]: i for i, s in enumerate(O["sites"])}
V = np.zeros((len(O["sites"]), len(dates)))
for p, w in works.items():
    V[ix[p]] = w["v"]
vals = np.concatenate([(V[r["u"]].sum(0) / max(r["L"], 2)) for r in RV if r["u"]])
vals = vals[vals > 0]
scale = dict(K=float(np.quantile(vals, 0.5)), S99=float(np.quantile(vals, 0.99)))
json.dump(dict(dates=dates, scale=scale, drivers=drv, works=works), open("web/data/physics.json", "w"), separators=(",", ":"))

c = pd.DataFrame(check, columns=["site", "date", "p_ens", "p_day", "v_ens", "v_day"])
print(f"{len(works)} works; {os.path.getsize('web/data/physics.json') / 1e6:.2f} MB; glow scale K={scale['K']:.1f} S99={scale['S99']:.1f}")
print(f"one-day version vs full ensemble, {len(c)} site-days: |dp| median {np.median(abs(c.p_ens - c.p_day)):.3f}, "
      f"p90 {np.quantile(abs(c.p_ens - c.p_day), .9):.3f}; volume correlation {np.corrcoef(c.v_ens, c.v_day)[0, 1]:.3f}")
