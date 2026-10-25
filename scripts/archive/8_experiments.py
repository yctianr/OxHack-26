"""Which ingredients make the hourly bathtub more accurate? Rolling-origin backtest over all eligible sites.
Fold A: train to 2024-09-30, test WY2025 (dry).  Fold B: train to 2025-09-30, test 2025-10-01 -> 2026-10-22.
Hourly model: z_t = b0 + b1*W_t (+hinge) + b2*F_t(tau) (+season);  daily P(any spill) = Platt(max_t z_t);  daily hours = sum p_t."""
import os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
os.makedirs(os.path.join(_ROOT, "data", "interim"), exist_ok=True)
os.chdir(os.path.join(_ROOT, "data", "interim"))  # intermediate tables are read and written here

import sys, warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.signal import lfilter
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
I = os.path.join(_ROOT, "data", "interim") + "/"
CLEAN = os.environ.get("DATA") == "clean"          # DATA=clean -> audited data layer from 12_build_clean.py
inp = pd.read_pickle(I + ("inputs_clean.pkl" if CLEAN else "inputs_hourly.pkl"))
lab = pd.read_pickle(I + ("labels_clean.pkl" if CLEAN else "labels_hourly.pkl"))
si = pd.read_csv(I + "site_inputs.csv").set_index("permit")
idx = inp.index
day = (idx - idx[0]).days
ndays = day.max() + 1
dates = pd.date_range(idx[0].normalize(), periods=ndays, freq="D")
doy = idx.dayofyear.values
SIN, COS = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
# typical lowland-England potential evaporation, mm/day by month (FAO-56 order of magnitude), spread evenly over hours
PET_MONTH = np.array([0.4, 0.7, 1.3, 2.2, 3.0, 3.4, 3.4, 2.8, 1.9, 1.0, 0.5, 0.3])
PET_H = PET_MONTH[idx.month.values - 1] / 24
FOLDS = {"A": ("2024-10-01", "2025-10-01"), "B": ("2025-10-01", "2026-10-23")}
TAUS = (6, 12, 24, 48, 96)
FLOWS = [c for c in inp.columns if c.startswith("lflow_") and inp[c].isna().mean() < 0.2]


def fill(a):
    s = pd.Series(a).interpolate(limit=72).fillna(0 if np.nanmean(a) == 0 else np.nanmedian(a))
    return s.values


def store(rain, tau):
    a = np.exp(-1 / tau)
    return lfilter([1 - a], [1, -a], np.nan_to_num(rain)) * tau


def logit(X, y, w=None, lam=1e-3, prior=None):
    w = np.ones(len(y)) if w is None else w
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.column_stack([np.ones(len(X)), (X - mu) / sd])
    pr = np.zeros(Z.shape[1]) if prior is None else prior
    def f(b):
        z = Z @ b
        l = np.sum(w * (np.logaddexp(0, z) - y * z)) / w.sum() * len(y) + lam * np.sum((b[1:] - pr[1:]) ** 2) * len(y) / 1000
        g = Z.T @ (w * (1 / (1 + np.exp(-z)) - y)) / w.sum() * len(y)
        g[1:] += 2 * lam * (b[1:] - pr[1:]) * len(y) / 1000
        return l, g
    b = minimize(f, np.zeros(Z.shape[1]), jac=True, method="L-BFGS-B").x
    return b, mu, sd, f(b)[0]


def predict(b, mu, sd, X):
    return np.column_stack([np.ones(len(X)), (X - mu) / sd]) @ b


def daily(v, how):
    s = pd.Series(v).groupby(day)
    return getattr(s, how)().reindex(range(ndays)).values


def run(p, fold, rain="osney", wet="farmoor", hinge=False, season=False, half_life=None, platt_recent=False,
        persist=False, prior=None, lam=1e-3, two_store=False, recal_int=False, slow=None, noflow=False):
    y, m = lab[p]
    t0, t1 = FOLDS[fold]
    tr = m & (idx < t0)
    te = m & (idx >= t0) & (idx < t1)
    if y[tr].sum() < 24 or y[te].sum() < 6 or (y[tr] > 0).sum() < 24:
        return None
    r = {"osney": inp["rain_256230TP"].values, "near": inp[f"rain_{si.loc[p, 'rain1']}"].values, "idw": None,
         "era5": inp[f"era5rain_{si.loc[p, 'cell']}"].values if rain == "era5" else None}
    if rain == "idw":
        a, b_ = inp[f"rain_{si.loc[p, 'rain1']}"].values, inp[f"rain_{si.loc[p, 'rain2']}"].values
        w1, w2 = 1 / si.loc[p, "d1"] ** 2, 1 / si.loc[p, "d2"] ** 2
        R = np.where(np.isnan(a), b_, np.where(np.isnan(b_), a, (w1 * a + w2 * b_) / (w1 + w2)))
    else:
        R = r[rain]
    R = np.nan_to_num(R)
    if wet == "best":     # pick wetness source by training likelihood (training data only)
        cands = FLOWS + [f"sm100_{si.loc[p, 'cell']}", f"sm28_{si.loc[p, 'cell']}"]
        F48 = store(R, 48)
        wet = min(cands, key=lambda c: logit(np.column_stack([fill(inp[c].values), F48])[tr], y[tr])[3])
    Wcol = {"farmoor": "lflow_1100TH", "none": None}.get(wet, wet)
    W = fill(inp[Wcol].values) if Wcol else np.zeros(len(idx))
    wts = None
    if half_life:
        age = (pd.Timestamp(t0, tz="UTC") - idx).days.values
        wts = np.where(tr, 0.5 ** (np.clip(age, 0, None) / half_life), 0)[tr]
    if noflow:
        Wcol, W = None, np.zeros(len(idx))
    # slow, site-local store: weeks-long memory of rain (minus a fixed monthly evaporation climatology if slow="eff")
    Reff = np.maximum(0, R - PET_H) if slow == "eff" else R
    slows = [None] if slow is None else [store(Reff, ts) / ts for ts in (168, 336, 720, 1440)]
    best = None
    for tau, (si_, S) in [(t_, s_) for t_ in TAUS for s_ in enumerate(slows)]:
        F = store(R, tau)
        for W0q in ((None, 0.3, 0.5, 0.7) if hinge else (None,)):
            Wx = W if W0q is None else np.maximum(0, W - np.quantile(W[tr], W0q))
            cols = [Wx, F] + ([S] if S is not None else []) + ([store(R, 6)] if two_store and tau > 6 else []) + ([SIN, COS] if season else [])
            if Wcol is None:
                cols = cols[1:]
            X = np.column_stack(cols)
            pr = None if prior is None else np.r_[prior[fold], np.zeros(max(0, X.shape[1] + 1 - len(prior[fold])))][:X.shape[1] + 1]
            fit = logit(X[tr], y[tr], wts, lam=lam, prior=pr)
            if best is None or fit[3] < best[0]:
                best = (fit[3], tau, W0q, X, fit, None if S is None else si_)
    _, tau, W0q, X, (b, mu, sd, _), slow_i = best
    z = predict(b, mu, sd, X)
    p_h = 1 / (1 + np.exp(-z))
    # daily
    valid = daily(m.astype(float), "mean") >= 0.9
    yd = (daily(np.where(m, y, 0), "max") > 0).astype(float)    # any spill that day (labels may be fractional)
    hd = daily(np.where(m, y, 0), "sum")
    zmax = daily(z, "max")
    hpred = daily(np.where(m, p_h, 0), "sum")
    dtr = valid & (dates < t0)
    dte = valid & (dates >= t0) & (dates < t1)
    if platt_recent:
        dtr = dtr & (dates >= pd.Timestamp(t0, tz="UTC") - pd.Timedelta("365D"))
    yend = pd.Series(np.where(m, y, 0)).groupby(day).last().reindex(range(ndays)).fillna(0).values   # spilling at the end of the day
    hprev = np.r_[0, hd[:-1]]
    pers = {False: [], True: [np.r_[0, yd[:-1]]], "end": [np.r_[0, yend[:-1]]], "end+hours": [np.r_[0, yend[:-1]], hprev]}[persist]
    feats = np.column_stack([zmax] + pers)
    cb, cmu, csd, _ = logit(feats[dtr], yd[dtr])
    if recal_int:   # recalibration-in-the-large: refit only the intercept on the last 12 months of training
        rec = dtr & (dates >= pd.Timestamp(t0, tz="UTC") - pd.Timedelta("365D"))
        zc = predict(cb, cmu, csd, feats[rec])
        off_ = minimize(lambda a: np.sum(np.logaddexp(0, zc + a) - yd[rec] * (zc + a)), [0.0]).x[0]
        cb = cb.copy(); cb[0] += off_
    pd_ = 1 / (1 + np.exp(-predict(cb, cmu, csd, feats)))
    yt, pt = yd[dte], np.clip(pd_[dte], 1e-4, 1 - 1e-4)
    clim = yd[valid & (dates < t0)].mean()
    brier = np.mean((pt - yt) ** 2)
    return dict(site=p, fold=fold, auc=roc_auc_score(yt, pt) if 0 < yt.mean() < 1 else np.nan,
                bss=1 - brier / np.mean((clim - yt) ** 2), brier=brier,
                ll=-np.mean(yt * np.log(pt) + (1 - yt) * np.log(1 - pt)),
                mae_h=np.mean(np.abs(hpred[dte] - hd[dte])), bias=(hpred[dte].sum() - hd[dte].sum()) / max(hd[dte].sum(), 1),
                tau=tau, w0=W0q, wet=Wcol, coefs=b, tau_slow=None if slow_i is None else (168, 336, 720, 1440)[slow_i])


SITES = [p for p in lab if lab[p][0][lab[p][1]].sum() > 100]
print(f"{'clean' if CLEAN else 'original'} data: {len(SITES)} sites with > 100 spill-hours")
VARIANTS = {
    "V0 baseline: Farmoor flow + Osney rain": {},
    "V1 nearest rain gauge": dict(rain="near"),
    "V2 IDW of 2 gauges": dict(rain="idw"),
    "V3 ERA5-Land rain": dict(rain="era5"),
    "V4 rain only (no wetness)": dict(wet="none"),
    "V5 best wetness source per site": dict(wet="best"),
    "V6 V5 + hinge": dict(wet="best", hinge=True),
    "V7 V5 + season": dict(wet="best", season=True),
    "V8 V5 + recency weight (1 yr half-life)": dict(wet="best", half_life=365),
    "V9 V5 + Platt on last 12 months": dict(wet="best", platt_recent=True),
    "V10 V5 + persistence (nowcast)": dict(wet="best", persist=True),
    "V11 V5 + second fast store (6 h)": dict(wet="best", two_store=True),
    "V12 V5 + intercept refit on last 12 months": dict(wet="best", recal_int=True),
    "V13 V5 + nearest rain": dict(wet="best", rain="near"),
    "V14 V5 + nearest rain + intercept refit": dict(wet="best", rain="near", recal_int=True),
    "V15 V14 + hinge": dict(wet="best", rain="near", recal_int=True, hinge=True),
    "W1 IDW rain + Farmoor (chosen physics core)": dict(rain="idw"),
    "W2 W1 + spilled yesterday": dict(rain="idw", persist=True),
    "W3 W1 + spilling at midnight": dict(rain="idw", persist="end"),
    "W4 W1 + spilling at midnight + hours yesterday": dict(rain="idw", persist="end+hours"),
    "W5 W1 + hinge": dict(rain="idw", hinge=True),
    "W6 W1 + slow local store (rain)": dict(rain="idw", slow="raw"),
    "W7 W1 + slow local store (rain - evaporation)": dict(rain="idw", slow="eff"),
    "W8 slow local store (rain - evap) instead of Farmoor": dict(rain="idw", slow="eff", noflow=True),
    "W9 W7 + midnight state + hours yesterday": dict(rain="idw", slow="eff", persist="end+hours"),
}
if len(sys.argv) > 1:
    VARIANTS = {k: v for k, v in VARIANTS.items() if k.split()[0] in sys.argv[1].split(",")}
rows = []
for name, kw in VARIANTS.items():
    for p in SITES:
        for fold in FOLDS:
            r = run(p, fold, **kw)
            if r:
                rows.append(dict(variant=name, **r))
    sub = pd.DataFrame([r for r in rows if r["variant"] == name])
    g = sub.groupby("fold")
    print(f"{name:42s} n={len(sub):3d} | " + " | ".join(
        f"{f}: AUC {x.auc.median():.3f} BSS {x.bss.median():+.2f} (pooled Brier {x.brier.mean():.4f}) MAEh {x.mae_h.median():.2f} bias {x.bias.median():+.0%}"
        for f, x in g), flush=True)
pd.DataFrame(rows).to_pickle(I + f"exp_{sys.argv[1] if len(sys.argv) > 1 else 'all'}.pkl")
