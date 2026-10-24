"""Does the minimal daily model (log Thames flow yesterday + rain today + rain yesterday) generalise across
overflows within 25 km of Oxford? Per-site logistic, train WY2023-24, test Oct 2024 -> Oct 2026.
Quick check only: Osney rain and Farmoor flow for every site."""
import os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
RAW = os.path.join(_ROOT, "data", "raw") + "/"
os.makedirs(os.path.join(_ROOT, "data", "interim"), exist_ok=True)
os.chdir(os.path.join(_ROOT, "data", "interim"))  # intermediate tables are read and written here

import warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
TZ = "Europe/London"

ev = pd.read_csv(RAW + "events.csv")
off = pd.read_csv(RAW + "offline.csv")
ev = ev[(np.hypot(ev.x - 452000, ev.y - 206000) < 25000) & ev.stop.notna()]
d = pd.read_csv("oxford_day.csv", index_col=0, parse_dates=True)[["rain", "thames_q"]]
d["lq1"], d["rain1"] = np.log(d.thames_q).shift(1), d.rain.shift(1)
days = pd.date_range("2022-06-01", "2026-10-23")
rows = []
for (permit, name), g in ev.groupby(["permitNumber", "locationName"]):
    hrs = pd.Series(0.0, days)
    for s, e in zip(pd.to_datetime(g.start), pd.to_datetime(g.stop)):
        for dd in pd.date_range(s.normalize(), e.normalize()):
            if dd in hrs.index:
                lo, hi = max(s, dd), min(e, dd + pd.Timedelta("1D"))
                hrs[dd] += max(0, (hi - lo).total_seconds() / 3600)
    ok = pd.Series(True, days)
    for s, e in off[off.permitNumber == permit][["start", "stop"]].dropna().values:
        ok[pd.Timestamp(s).normalize():pd.Timestamp(e).normalize()] = False
    first = pd.to_datetime(g.start).min().normalize()
    t = d.reindex(days).assign(h=hrs, y=(hrs > 0).astype(int))[ok & (days >= first)].dropna()
    tr, te = t[t.index < "2024-10-01"], t[t.index >= "2024-10-01"]
    if tr.y.sum() < 5 or te.y.sum() < 3:
        rows.append((name, permit, len(g), round(hrs.sum()), np.nan, np.nan, np.nan)); continue
    cols = ["lq1", "rain", "rain1"]
    mu, sd = tr[cols].mean(), tr[cols].std()
    Z = lambda D: np.column_stack([np.ones(len(D)), ((D[cols] - mu) / sd).values])
    nll = lambda b: np.sum(np.logaddexp(0, Z(tr) @ b) - tr.y.values * (Z(tr) @ b)) + 1e-2 * b @ b
    b = minimize(nll, np.zeros(4), method="BFGS").x
    p = 1 / (1 + np.exp(-Z(te) @ b))
    brier = np.mean((p - te.y) ** 2); clim = np.mean((tr.y.mean() - te.y) ** 2)
    rows.append((name, permit, len(g), round(hrs.sum()), roc_auc_score(te.y, p), 1 - brier / clim,
                 b[1] / (abs(b[2]) + 1e-9)))
r = pd.DataFrame(rows, columns=["site", "permit", "events", "hours", "AUC", "BSS", "flow/rain weight"])
r = r.sort_values("hours", ascending=False)
pd.set_option("display.width", 200)
print(r.round(2).to_string(index=False))
v = r.dropna()
print(f"\n{len(r)} sites within 25 km; {len(v)} with enough events. AUC median {v.AUC.median():.3f} "
      f"(IQR {v.AUC.quantile(.25):.3f}-{v.AUC.quantile(.75):.3f}); BSS median {v.BSS.median():.2f}")
r.to_csv("multisite.csv", index=False)
