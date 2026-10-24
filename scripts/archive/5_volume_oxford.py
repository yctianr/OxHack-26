"""Feasibility of the volume method at Oxford STW with TDV 2024-2025.
1. Inflow model fitted on non-spill days: TDV = exp(b0 + b1*log Thames flow + b2*F48), F48 = rain fast store (daily).
2. Plateau check: TDV on spill days vs FFT 1040 l/s (ORIC).
3. Spill volume = sum over spill days of max(0, Q_hat - TDV), with day-block bootstrap of residuals."""
import os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
RAW = os.path.join(_ROOT, "data", "raw") + "/"
os.makedirs(os.path.join(_ROOT, "data", "interim"), exist_ok=True)
os.chdir(os.path.join(_ROOT, "data", "interim"))  # intermediate tables are read and written here

import warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

tdv = pd.concat([pd.read_excel(RAW + f"tdv/tdv{y}.xlsx", sheet_name=1, na_values="NaN", index_col=0)["OXFORD STW"]
                 for y in (2024, 2025)])
tdv.index = pd.to_datetime(tdv.index)
d = pd.read_csv("oxford_day.csv", index_col=0, parse_dates=True)
d = d.join(tdv.rename("tdv"), how="inner").dropna(subset=["tdv", "thames_q"])
a = np.exp(-1 / 2.0)                               # 48 h store ~ 2 days
F = np.zeros(len(d)); x = 0
for i, r in enumerate(d.rain.fillna(0).values):
    x = a * x + (1 - a) * r * 2; F[i] = x
d["F"] = F
FFT = 1040 * 86.4                                  # l/s -> m3/day
print(f"days {len(d)}; FFT = {FFT:.0f} m3/d")
print("TDV/FFT on spill days  : quantiles", (d.tdv[d.y == 1] / FFT).quantile([.1, .5, .9, .99]).round(3).to_dict())
print("TDV/FFT on dry days    : quantiles", (d.tdv[d.y == 0] / FFT).quantile([.1, .5, .9, .99]).round(3).to_dict())
print("dry weather flow (Q80 of TDV, 2024):", round(d.tdv[d.index.year == 2024].quantile(0.2)), "m3/d")

fit = d[(d.y == 0) & (d.spill_h == 0)]
X = lambda D: np.column_stack([np.ones(len(D)), np.log(D.thames_q), D.F])
b, *_ = np.linalg.lstsq(X(fit), np.log(fit.tdv), rcond=None)
res = np.log(fit.tdv) - X(fit) @ b
print(f"inflow model on {len(fit)} non-spill days: R2 {1 - res.var() / np.log(fit.tdv).var():.2f}, "
      f"resid sd {res.std():.3f} (log)")
# check: does the model predict Q_hat > FFT on spill days and < FFT on non-spill days?
qhat = np.exp(X(d) @ b)
print(f"Q_hat > FFT: on spill days {np.mean(qhat[d.y == 1] > FFT):.2f}, on non-spill days {np.mean(qhat[d.y == 0] > FFT):.2f}")
from sklearn.metrics import roc_auc_score
print(f"AUC of (Q_hat - FFT) for spill days: {roc_auc_score(d.y, qhat - FFT):.3f}  (model never saw spill labels)")

rng = np.random.default_rng(0)
sp = d.y == 1
vols = []
for _ in range(500):
    e = rng.choice(res.values, len(d))
    q = np.exp(X(d) @ b + e)
    vols.append(pd.Series(np.where(sp, np.maximum(0, q - d.tdv), 0), d.index).groupby(d.index.year).sum() / 1e3)
v = pd.concat(vols, axis=1)
print("\nestimated spill volume (ML/yr) 10/50/90%:")
print(v.quantile([.1, .5, .9], axis=1).T.round(0).to_string())
print("spill hours/yr:", d.spill_h.groupby(d.index.year).sum().round(0).to_dict())
