"""Hourly 'bathtub' variants for Oxford STW: does hourly structure predict spill duration better than the daily hurdle?
p_t = sigmoid(b0 + b1*log(Thames flow, yesterday) + b2*F_t), F_t = rain through a linear reservoir with time constant tau.
Optional storage: spill only once cumulative excess within an episode exceeds a tank volume (in the model's units)."""
import os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
RAW = os.path.join(_ROOT, "data", "raw") + "/"
os.makedirs(os.path.join(_ROOT, "data", "interim"), exist_ok=True)
os.chdir(os.path.join(_ROOT, "data", "interim"))  # intermediate tables are read and written here

import warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.signal import lfilter
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")

h = pd.read_csv("oxford_hourly.csv", index_col=0, parse_dates=True)
d = pd.read_csv("oxford_day.csv", index_col=0, parse_dates=True)
# yesterday's daily mean Thames flow, held constant through the (local) day, as the slow wetness state
lq = np.log(d.thames_q).shift(1)
loc = h.index.tz_convert("Europe/London").tz_localize(None).normalize()
h["lq"] = lq.reindex(loc).values
h = h.dropna(subset=["lq"])
train = (h.index < "2024-10-01") & h["mask"].values
test = (h.index >= "2024-10-01") & h["mask"].values
y, R, LQ = h.spill.values, h.rain.values, h.lq.values


def reservoir(rain, tau):
    a = np.exp(-1 / tau)
    return lfilter([1 - a], [1, -a], rain) * tau   # mm-equivalent stored in the fast store


def fit(tau):
    F = reservoir(R, tau)
    X = np.column_stack([np.ones(len(y)), LQ, F])
    mu, sd = X[train, 1:].mean(0), X[train, 1:].std(0)
    Z = X.copy(); Z[:, 1:] = (X[:, 1:] - mu) / sd
    nll = lambda b: np.sum(np.logaddexp(0, Z[train] @ b) - y[train] * (Z[train] @ b))
    b = minimize(nll, np.zeros(3), method="BFGS").x
    return nll(b), 1 / (1 + np.exp(-Z @ b)), b


res = {tau: fit(tau) for tau in (3, 6, 12, 24, 48, 96)}
for tau, (nll, p, b) in res.items():
    print(f"tau {tau:3d} h: train nll {nll:9.0f}  test hourly AUC {roc_auc_score(y[test], p[test]):.3f}")
tau = min(res, key=lambda t: res[t][0])
p = res[tau][1]
print("chosen tau (by train likelihood):", tau)

# Daily spill-hours from summing hourly probabilities, test period only
hh = pd.DataFrame({"obs": np.where(test, y, np.nan), "pred": np.where(test, p, np.nan)}, index=h.index)
day = hh.tz_convert("Europe/London").resample("D").sum(min_count=1).dropna()
day = day[day.index >= pd.Timestamp("2024-10-01", tz="Europe/London")]
print(f"\nhourly model -> daily hours: MAE {np.mean(np.abs(day.pred - day.obs)):.2f} h, Spearman {spearmanr(day.pred, day.obs)[0]:.2f}")
dy = (day.obs > 0).astype(int); pday = 1 - hh.pred.tz_convert("Europe/London").resample("D").apply(lambda s: np.prod(1 - s.dropna().values) if s.notna().any() else np.nan).reindex(day.index)
m = day.resample("MS").sum()
print(f"monthly corr {np.corrcoef(m.obs, m.pred)[0, 1]:.3f}  total obs {m.obs.sum():.0f} pred {m.pred.sum():.0f}")

# Events: predicted episodes from thresholded hourly p, compare durations of matched events
ev = pd.read_csv("oxford_events.csv", parse_dates=["start", "stop"])
ev = ev[ev.start >= "2024-10-01"]
pred_dur = [hh.pred[s:e + pd.Timedelta("12h")].sum() for s, e in zip(ev.start, ev.stop)]
print(f"test events {len(ev)}: Spearman(obs duration, model expected hours over event window) {spearmanr(ev.hours, pred_dur)[0]:.2f}")
