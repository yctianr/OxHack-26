"""Spill volume at Oxford STW from daily treated flow (TDV), on the audited data layer. Order-of-magnitude only.

Inflow model (daily, log scale):  log I_d = a0 + a1*log(Farmoor flow) + a2*F_d + e,  e ~ N(0, s^2)
  - no spill that day       : TDV = I              (exact observation)
  - any spill that day (y>0): I >= TDV              (censored; Tobit likelihood)
Spill volume on a spill day = E[I - TDV | I >= TDV], drawn from the truncated conditional distribution.
Uncertainty: weekly block bootstrap refits of (a, s), then truncated draws. Train Nov 2022 - Sep 2024; the
test check is how well modelled inflow separates spill from non-spill days after Sep 2024.
Known gaps (docs/archive/11-system-review.md §7): storm-tank fill and pump-back are not modelled; FFT is not used as a lower bound.
Superseded by the physics water balance (docs/02-physical-model.md), which models the storm tank."""
import os
import warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm, spearmanr, truncnorm
from sklearn.metrics import roc_auc_score
from common import FLOW, RAW, TZ, load, rain_for, store
warnings.filterwarnings("ignore")
inp, lab, si, names = load()
P = "TEMP.2827"
FFT = 1040 * 86.4                                          # ORIC installed FFT, l/s -> m3/day

y, m = lab[P]
loc = inp.index.tz_convert(TZ).tz_localize(None).normalize()
h = pd.DataFrame({"y": np.where(m, y, np.nan), "m": m, "F": store(rain_for(inp, si, P), 48), "lq": inp[FLOW].values}, index=loc)
d = h.groupby(level=0).agg(spill_h=("y", "sum"), valid=("m", "mean"), F=("F", "mean"), lq=("lq", "mean"))
tdv = pd.concat([pd.read_excel(os.path.join(RAW, "tdv", f"tdv{yr}.xlsx"), sheet_name=1, na_values="NaN", index_col=0)
                 .filter(regex="^OXFORD STW").iloc[:, 0] for yr in (2022, 2023, 2024, 2025)])
tdv.index = pd.to_datetime(tdv.index)
d = d.join(pd.to_numeric(tdv, errors="coerce").rename("tdv"), how="inner")
d = d[(d.valid >= 0.9) & (d.tdv > 0)].dropna(subset=["lq", "tdv"])
X = np.column_stack([np.ones(len(d)), d.lq, d.F])
ly, cens = np.log(d.tdv.values), (d.spill_h.values > 0)
tr = np.asarray(d.index < "2024-10-01")
week = np.asarray((d.index - d.index[0]).days // 7)


def fit(rows):
    Xr, lr, cr = X[rows], ly[rows], cens[rows]
    b0 = np.linalg.lstsq(Xr[~cr], lr[~cr], rcond=None)[0]
    def nll(th):
        mu, s = Xr @ th[:3], np.exp(th[3])
        return -(norm.logpdf(lr[~cr], mu[~cr], s).sum() + norm.logsf(lr[cr], mu[cr], s).sum())
    th = minimize(nll, np.r_[b0, np.log(np.std(lr[~cr] - Xr[~cr] @ b0))], method="Nelder-Mead",
                  options={"maxiter": 20000, "xatol": 1e-7, "fatol": 1e-7}).x
    return th[:3], np.exp(th[3])


b, s = fit(tr)
mu = X @ b
te = ~tr
print(f"Oxford STW, {len(d)} days ({cens.sum()} spill days). Inflow coefs {np.round(b, 3)}, sigma {s:.3f}")
print(f"test (Oct 2024 on): AUC of modelled inflow - FFT for spill days {roc_auc_score(cens[te], mu[te] - np.log(FFT)):.3f}; "
      f"median modelled inflow / FFT on spill days {np.median(np.exp(mu[te][cens[te]]) / FFT):.2f}")

rng = np.random.default_rng(0)
wk = np.unique(week[tr])
vols = []
for _ in range(200):
    pick = np.concatenate([np.flatnonzero(tr & (week == w)) for w in rng.choice(wk, len(wk))])
    bb, ss = fit(pick)
    mub = X @ bb
    a = (ly[cens] - mub[cens]) / ss                         # truncate below at observed TDV
    draw = truncnorm.rvs(a, np.inf, loc=mub[cens], scale=ss, random_state=rng)
    v = pd.Series(0.0, d.index)
    v[cens] = np.exp(draw) - d.tdv.values[cens]
    vols.append(v.groupby(d.index.year).sum() / 1e3)
V = pd.concat(vols, axis=1)
ex = np.exp(mu) - d.tdv.values
print(f"Spearman(modelled excess, observed spill-hours) on test spill days: {spearmanr(ex[te & cens], d.spill_h.values[te & cens])[0]:.2f}")
print("estimated spill volume, ML per calendar year (10% / 50% / 90%), with observed spill-hours:")
hrs = d.spill_h.groupby(d.index.year).sum()
for yr in V.index:
    q = V.loc[yr].quantile([.1, .5, .9]).round(0).values
    print(f"  {yr}: {q[0]:6.0f} / {q[1]:6.0f} / {q[2]:6.0f}   ({hrs[yr]:.0f} spill-hours)")
