"""Out-of-sample comparison of minimal models for Oxford STW: P(spill day) and daily spill-hours.
Train: water years 2023-2024 (to 30 Sep 2024). Test: 1 Oct 2024 -> 24 Oct 2026 (includes dry 2025)."""
import os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
RAW = os.path.join(_ROOT, "data", "raw") + "/"
os.makedirs(os.path.join(_ROOT, "data", "interim"), exist_ok=True)
os.chdir(os.path.join(_ROOT, "data", "interim"))  # intermediate tables are read and written here

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score, average_precision_score

d = pd.read_csv("oxford_day.csv", index_col=0, parse_dates=True)
d["logq1"] = np.log(d.thames_q.shift(1))          # yesterday's mean flow: known at forecast time
d["cher1"] = d.cher_lvl.shift(1)
d["gw1"] = d.gw.shift(1)
d["y1"] = d.y.shift(1)
d["h1"] = d.spill_h.shift(1)
d["rain1"] = d.rain.shift(1)
d["rain2"] = d.rain.shift(2)
for k in (0.9, 0.97, 0.99):                        # rain-only wetness state (antecedent precipitation index)
    api = np.zeros(len(d)); x = 0
    for i, r in enumerate(d.rain.fillna(0).values):
        api[i] = x; x = k * x + r                  # state before today's rain
    d[f"api{k}"] = api
doy = d.index.dayofyear
d["sin"], d["cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
d = d.dropna(subset=["logq1", "y1", "rain1", "rain2", "cher1"])
tr, te = d[d.index < "2024-10-01"], d[d.index >= "2024-10-01"]
print(f"train {len(tr)} days ({tr.y.mean():.2f} spill), test {len(te)} days ({te.y.mean():.2f} spill)")


def logit_fit(X, y):
    X = np.column_stack([np.ones(len(X)), X])
    mu, sd = X[:, 1:].mean(0), X[:, 1:].std(0) + 1e-9
    Z = X.copy(); Z[:, 1:] = (X[:, 1:] - mu) / sd
    nll = lambda b: np.sum(np.logaddexp(0, Z @ b) - y * (Z @ b)) + 1e-3 * b @ b
    b = minimize(nll, np.zeros(Z.shape[1]), method="BFGS").x
    return lambda Xn: 1 / (1 + np.exp(-(np.column_stack([np.ones(len(Xn)), (Xn - mu) / sd]) @ b)))


def score(name, p, y=te.y.values):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    brier = np.mean((p - y) ** 2); clim = np.mean((tr.y.mean() - y) ** 2)
    ll = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
    auc = roc_auc_score(y, p) if 0 < p.std() else 0.5
    print(f"{name:42s} Brier {brier:.3f}  BSS {1 - brier / clim:+.2f}  logloss {ll:.3f}  AUC {auc:.3f}  PR-AUC {average_precision_score(y, p):.3f}")


print("\n--- P(spill on day d), features known by end of day d-1 except today's rain ---")
score("climatology", np.full(len(te), tr.y.mean()))
score("persistence (calibrated)", te.y1.map(tr.groupby("y1").y.mean()).values)
specs = {
    "rain today + 2 lags": ["rain", "rain1", "rain2"],
    "rain + API k=0.97 (rain only)": ["rain", "rain1", "api0.97", "sin", "cos"],
    "log Thames flow yesterday only (1 var)": ["logq1"],
    "log Thames flow + rain today (2 vars)": ["logq1", "rain"],
    "log Thames flow + rain + rain lag": ["logq1", "rain", "rain1"],
    "Cherwell level + rain": ["cher1", "rain"],
    "flow + rain + persistence": ["logq1", "rain", "y1"],
}
P = {}
for name, cols in specs.items():
    f = logit_fit(tr[cols].values, tr.y.values)
    P[name] = f(te[cols].values)
    score(name, P[name])

# threshold rule on flow: interpretability check
qs = np.exp(tr.logq1)
best = max(np.quantile(qs, np.linspace(.3, .95, 66)), key=lambda c: np.mean((qs > c) == tr.y))
acc = np.mean((np.exp(te.logq1) > best) == te.y)
print(f"\nrule 'spill if Thames@Farmoor yesterday > {best:.1f} m3/s': test accuracy {acc:.3f} (base rate {1 - te.y.mean():.3f})")

print("\n--- daily spill-hours (hurdle: P x E[hours | spill]) ---")
cols = ["logq1", "rain", "rain1"]
sp = tr[tr.y == 1]
# conditional fraction of day spilling: fractional logit on spill days
X = np.column_stack([np.ones(len(sp)), sp[cols].values]); frac = (sp.spill_h / 24).clip(1e-3, 1 - 1e-3).values
mu, sd = X[:, 1:].mean(0), X[:, 1:].std(0)
Z = X.copy(); Z[:, 1:] = (X[:, 1:] - mu) / sd
b = minimize(lambda b: -np.sum(frac * -np.logaddexp(0, -Z @ b) + (1 - frac) * -np.logaddexp(0, Z @ b)), np.zeros(Z.shape[1])).x
cond = lambda D: 24 / (1 + np.exp(-(np.column_stack([np.ones(len(D)), (D[cols].values - mu) / sd]) @ b)))
pred_h = P["log Thames flow + rain + rain lag"] * cond(te)
obs = te.spill_h.values
for name, ph in [("site mean hours", np.full(len(te), tr.spill_h.mean())),
                 ("persistence (yesterday's hours)", te.h1.values),
                 ("hurdle: flow + rain (5+4 params)", pred_h)]:
    print(f"{name:42s} MAE {np.mean(np.abs(ph - obs)):.2f} h   Spearman {spearmanr(ph, obs)[0]:.2f}")
m = te.assign(p=pred_h).resample("MS")[["spill_h", "p"]].sum()
print("monthly spill-hours, test: corr", np.corrcoef(m.spill_h, m.p)[0, 1].round(3),
      " total obs", int(m.spill_h.sum()), "pred", int(m.p.sum()))
print(m.round(0).astype(int).T.to_string())
