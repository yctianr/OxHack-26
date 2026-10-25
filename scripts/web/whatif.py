"""Rainfall what-if for the scenario page (web/scenario.html). Writes web/data/whatif.json.

Refits the fold-B Explain core exactly as scripts/model/5_evaluate.py does, then exports what the page needs to move one
site's day under a different 24-hour rainfall:
  z_d = logit(P spill on day d) = c0 + c1*max_t z_t,   z_t = b0 + b1*log(flow) + b2*F_tau(t)
For a scenario total R' (spread evenly over the day), the page shifts the actual logit by
  c1*b2*(G(R') - G(R)),   G(R) = max over the day of the store, starting from F0 with even rain R
so the slider at the rain that actually fell gives back the published Explain chance. A what-if, read as relative change.
Run from the repo root after 4_build_clean.py."""
import json
import os
import sys
import warnings
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from common import FLOW, FOLDS, TAUS, lin, load, logit_fit, rain_for, store
warnings.filterwarnings("ignore")
inp, lab, si, names = load()
idx = inp.index
day = np.asarray((idx - idx[0]).days)
ND = day.max() + 1
dates = pd.date_range(idx[0].normalize(), periods=ND, freq="D")
pos = {d: i for i, d in enumerate(dates.strftime("%Y-%m-%d"))}
W = inp[FLOW].values
t0, t1 = FOLDS["B"]
O = json.load(open("web/data/outfalls.json"))
want = {s["id"] for s in O["sites"] if s.get("pe")}
TE = pd.read_pickle("data/interim/eval_predictions.pkl")
TE = TE[TE.fold == "B"]


def daily(v, how):
    return getattr(pd.Series(v).groupby(day), how)().reindex(range(ND)).values


out, err = {}, []
for p, (y, m) in lab.items():
    if p not in want:
        continue
    R = rain_for(inp, si, p)
    vd = daily(m.astype(float), "mean") >= 0.9
    yd = (daily(np.where(m, y, 0), "max") > 0).astype(float)
    dtr = vd & np.r_[False, vd[:-1]] & (dates < t0)
    tr_h = m & (idx < t0)
    best = None
    for tau in TAUS:
        fit = logit_fit(np.column_stack([W, store(R, tau)])[tr_h], y[tr_h])
        if best is None or fit[3] < best[0][3]:
            best = (fit, tau)
    fit, tau = best
    F = store(R, tau)
    zmax = daily(lin(fit, np.column_stack([W, F])), "max")
    cal = logit_fit(zmax[dtr, None], yd[dtr])
    zd = lin(cal, zmax[:, None])
    b2 = fit[0][2] / fit[2][1]                      # per mm of store
    c1 = cal[0][1] / cal[2][0]                      # per unit of max hourly z
    F0 = np.r_[0, daily(F, "last")[:-1]]            # store at the end of the previous day
    rd = daily(R, "sum")
    di = [pos[d] for d in O["dates"]]
    ref = TE[TE.site == p].set_index("date").core_explain
    chk = 1 / (1 + np.exp(-zd[[pos[d] for d in pd.DatetimeIndex(ref.index).strftime("%Y-%m-%d")]]))
    err.append(np.max(np.abs(chk - ref.values)))
    out[p] = dict(tau=int(tau), k=round(float(c1 * b2), 4),
                  z=[round(float(v), 2) for v in zd[di]], f0=[round(float(v), 1) for v in F0[di]],
                  r=[round(float(v), 1) for v in rd[di]])
print(f"{len(out)} sites; max |P - published Explain| = {max(err):.2e}")
json.dump(dict(dates=O["dates"], sites=out), open("web/data/whatif.json", "w"), separators=(",", ":"))
