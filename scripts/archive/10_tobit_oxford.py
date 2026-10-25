"""Volume model at Oxford STW: ordinary fit on non-spill days vs censored (Tobit) fit using spill days as lower bounds.
Train Nov 2022 - Sep 2024, test Oct 2024 - Dec 2025 (TDV ends Dec 2025)."""
import os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
os.makedirs(os.path.join(_ROOT, "data", "interim"), exist_ok=True)
os.chdir(os.path.join(_ROOT, "data", "interim"))  # intermediate tables are read and written here

import warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm, spearmanr
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
R = os.path.join(_ROOT, "data") + "/"
tdv = pd.concat([pd.read_excel(R + f"raw/tdv/tdv{y}.xlsx", sheet_name=1, na_values="NaN", index_col=0)
                 .filter(regex="^OXFORD STW").iloc[:, 0] for y in (2022, 2023, 2024, 2025)])
tdv.index = pd.to_datetime(tdv.index)
tdv = pd.to_numeric(tdv, errors="coerce")
d = pd.read_csv(R + "interim/oxford_day.csv", index_col=0, parse_dates=True).join(tdv.rename("tdv"), how="inner")
a = np.exp(-1 / 2.0)
F = np.zeros(len(d)); x = 0
for i, r in enumerate(d.rain.fillna(0).values):
    x = a * x + (1 - a) * r * 2; F[i] = x
d["F"], d["lq"] = F, np.log(d.thames_q)
d = d.dropna(subset=["tdv", "lq"])
d = d[d.tdv > 0]
FFT = 1040 * 86.4
X = np.column_stack([np.ones(len(d)), d.lq, d.F])
ly, cens = np.log(d.tdv.values), (d.spill_h.values >= 1)      # spill day: inflow >= TDV
tr = np.asarray(d.index < "2024-10-01")
te = ~tr

# 1) ordinary least squares on non-spill days only
o = tr & ~cens
b_ols = np.linalg.lstsq(X[o], ly[o], rcond=None)[0]
s_ols = np.std(ly[o] - X[o] @ b_ols)

# 2) Tobit: density on non-spill days, survival on spill days
def nll(th):
    b, s = th[:3], np.exp(th[3])
    mu = X[tr] @ b
    return -(np.sum(norm.logpdf(ly[tr][~cens[tr]], mu[~cens[tr]], s)) + np.sum(norm.logsf(ly[tr][cens[tr]], mu[cens[tr]], s)))
th = minimize(nll, np.r_[b_ols, np.log(s_ols)], method="Nelder-Mead", options={"maxiter": 20000, "xatol": 1e-6, "fatol": 1e-6}).x
b_tob, s_tob = th[:3], np.exp(th[3])

rng = np.random.default_rng(0)
for name, b, s in [("OLS on non-spill days", b_ols, s_ols), ("Tobit (censored)", b_tob, s_tob)]:
    mu = X @ b
    yspill = d.y.values[te]
    print(f"\n{name}: coefs {np.round(b, 3)}, sigma {s:.3f}")
    print(f"  test: AUC of (mu - log FFT) for spill days {roc_auc_score(yspill, mu[te] - np.log(FFT)):.3f}; "
          f"median Q_hat/FFT on spill days {np.median(np.exp(mu[te][yspill == 1]) / FFT):.2f}, non-spill {np.median(np.exp(mu[te][yspill == 0]) / FFT):.2f}")
    # expected excess E[max(0, I - TDV)] on spill days with lognormal I truncated to I >= TDV
    vols = []
    for _ in range(300):
        I = np.exp(mu + rng.normal(0, s, len(mu)))
        I = np.where(cens, np.maximum(I, d.tdv.values), I)
        vols.append(pd.Series(np.where(cens, I - d.tdv.values, 0), d.index).groupby(d.index.year).sum() / 1e3)
    v = pd.concat(vols, axis=1)
    print("  spill volume ML/yr (10/50/90%):", {y: tuple(np.round(v.loc[y].quantile([.1, .5, .9]).values)) for y in v.index})
    ev_ex = pd.Series(np.where(cens, np.exp(mu) - d.tdv.values, 0), d.index)[te]
    print(f"  Spearman(daily modelled excess, observed spill hours) on test spill days: "
          f"{spearmanr(ev_ex[d.y.values[te] == 1], d.spill_h.values[te][d.y.values[te] == 1])[0]:.2f}")
print("\nspill hours/yr:", d.groupby(d.index.year).spill_h.sum().round(0).to_dict())
