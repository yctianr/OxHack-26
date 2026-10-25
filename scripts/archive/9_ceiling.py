"""Accuracy ceiling: pooled gradient boosting with every input, daily, same folds/days as the bathtub backtest.
If it barely beats the 4-parameter bathtub, the remaining error is in the data, not the model structure."""
import os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
os.makedirs(os.path.join(_ROOT, "data", "interim"), exist_ok=True)
os.chdir(os.path.join(_ROOT, "data", "interim"))  # intermediate tables are read and written here

import warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
I = os.path.join(_ROOT, "data", "interim") + "/"
inp = pd.read_pickle(I + "inputs_hourly.pkl")
lab = pd.read_pickle(I + "labels_hourly.pkl")
si = pd.read_csv(I + "site_inputs.csv").set_index("permit")
FOLDS = {"A": ("2024-10-01", "2025-10-01"), "B": ("2025-10-01", "2026-10-23")}
flows = [c for c in inp.columns if c.startswith("lflow_") and inp[c].isna().mean() < 0.2]
dkey = inp.index.normalize()
dflow = inp[flows].groupby(dkey).mean()
SITES = [p for p in lab if lab[p][0][lab[p][1]].sum() > 100]
frames = []
for k, p in enumerate(SITES):
    y, m = lab[p]
    a, b = inp[f"rain_{si.loc[p, 'rain1']}"], inp[f"rain_{si.loc[p, 'rain2']}"]
    w1, w2 = 1 / si.loc[p, "d1"] ** 2, 1 / si.loc[p, "d2"] ** 2
    R = ((w1 * a.fillna(b) + w2 * b.fillna(a)) / (w1 + w2)).fillna(0)
    g = pd.DataFrame({"y": np.where(m, y, 0), "m": m.astype(float), "R": R.values}, index=inp.index).groupby(dkey)
    d = pd.DataFrame({"y": g.y.max(), "valid": g.m.mean() >= 0.9, "rain": g.R.sum(), "rmax": g.R.max()})
    for n in (1, 3, 7, 14, 30):
        d[f"rain_prev{n}"] = d.rain.shift(1).rolling(n).sum()
    d = d.join(dflow)
    c = f"{si.loc[p, 'cell']}"
    d["sm100"] = inp[f"sm100_{c}"].groupby(dkey).mean()
    d["sm28"] = inp[f"sm28_{c}"].groupby(dkey).mean()
    d["doy_s"], d["doy_c"] = np.sin(2 * np.pi * d.index.dayofyear / 365.25), np.cos(2 * np.pi * d.index.dayofyear / 365.25)
    d["site"] = k
    d["y_prev"] = d.y.shift(1)
    d["permit"] = p
    frames.append(d)
D = pd.concat(frames)
feats = [c for c in D.columns if c not in ("y", "valid", "permit", "y_prev")]
rows = []
for fold, (t0, t1) in FOLDS.items():
    t0z, t1z = pd.Timestamp(t0, tz="UTC"), pd.Timestamp(t1, tz="UTC")
    for use_prev in (False, True):
        F = feats + (["y_prev"] if use_prev else [])
        tr = D[D.valid & (D.index < t0z)]
        te = D[D.valid & (D.index >= t0z) & (D.index < t1z)]
        clf = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                             categorical_features=[F.index("site")], random_state=0)
        clf.fit(tr[F], tr.y)
        te = te.assign(p=clf.predict_proba(te[F])[:, 1])
        clim = tr.groupby("permit").y.mean()
        for p, g in te.groupby("permit"):
            if g.y.sum() < 3 or (tr.permit == p).sum() == 0:
                continue
            br = np.mean((g.p - g.y) ** 2)
            rows.append(dict(fold=fold, prev=use_prev, site=p, auc=roc_auc_score(g.y, g.p), brier=br,
                             bss=1 - br / np.mean((clim[p] - g.y) ** 2)))
r = pd.DataFrame(rows)
print(r.groupby(["prev", "fold"]).agg(n=("auc", "size"), auc=("auc", "median"), bss=("bss", "median"), pooled_brier=("brier", "mean")).round(4))

# which inputs carry gradient boosting's edge? drop groups and refit on fold B (no persistence)
t0z, t1z = pd.Timestamp("2025-10-01", tz="UTC"), pd.Timestamp("2026-10-23", tz="UTC")
groups = {"other flows": [f for f in flows if f != "lflow_1100TH"], "soil moisture": ["sm100", "sm28"],
          "long rain sums (7-30 d)": ["rain_prev7", "rain_prev14", "rain_prev30"], "season": ["doy_s", "doy_c"],
          "rain intensity": ["rmax"]}
tr = D[D.valid & (D.index < t0z)]; te = D[D.valid & (D.index >= t0z) & (D.index < t1z)]
for gname, drop in [("none", [])] + list(groups.items()):
    F = [f for f in feats if f not in drop]
    clf = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                         categorical_features=[F.index("site")], random_state=0).fit(tr[F], tr.y)
    print(f"drop {gname:24s} fold B pooled Brier {np.mean((clf.predict_proba(te[F])[:, 1] - te.y) ** 2):.4f}")
