"""Evaluate the water balance (9_wb_fit.py) against the statistical core on exactly the same held-out site-days.

Explain task only (observed weather, no observed spill state), the same rows as 5_evaluate.py's eval_predictions.
  wb   = water balance + one fitted number (where the overflow starts)
  wb1  = water balance alone, spilling assumed to start at the measured capacity (no spill records at all)
  core = the 4-parameter logistic core; gbm = gradient boosting with the same information
Also: daily treated flow on the test years, and whether fitted quantities match ORIC's published ones."""
import os
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from common import FOLDS, INT

E = pd.read_pickle(os.path.join(INT, "eval_predictions.pkl"))
D = pd.read_pickle(os.path.join(INT, "wb_predictions.pkl"))
Fl = pd.read_pickle(os.path.join(INT, "wb_flow.pkl"))
P = pd.read_csv(os.path.join(INT, "wb_params.csv"))
W = pd.read_csv(os.path.join(INT, "wb_works.csv")).set_index("permit")
M = E.merge(D, on=["site", "fold", "date"])
M["verdict"] = M.site.map(W.verdict)
M["week"] = (M.date - M.date.min()).dt.days // 7
MODELS = ["clim", "wb1_p", "wb_p", "core_explain", "gbm_explain"]
rng = np.random.default_rng(0)
pd.set_option("display.width", 200)


def brier(g, c):
    return float(((g[c] - g.y) ** 2).mean())


def boot_diff(g, a, b, n=1000):
    """Weekly block bootstrap (same weeks for every site) of Brier(a) - Brier(b)."""
    d = ((g[a] - g.y) ** 2 - (g[b] - g.y) ** 2).groupby(g.week).agg(["sum", "count"])
    wk = d.index.values
    s = [d.loc[pick, "sum"].sum() / d.loc[pick, "count"].sum() for pick in (rng.choice(wk, len(wk)) for _ in range(n))]
    return np.quantile(s, [.025, .975])


print(f"Sites in both evaluations: {M.site.nunique()} works  ({M.groupby('fold').site.nunique().to_dict()} per fold)\n")
print("== Explain: Brier over all valid site-days (lower is better); skill vs climatology in brackets")
for fold, g in M.groupby("fold"):
    c = brier(g, "clim")
    row = "  ".join(f"{m.replace('_explain', '').replace('_p', '')} {brier(g, m):.4f} ({1 - brier(g, m) / c:+.2f})" for m in MODELS)
    lo, hi = boot_diff(g, "wb_p", "core_explain")
    lo1, hi1 = boot_diff(g, "wb_p", "gbm_explain")
    print(f"  fold {fold}: {row}\n           wb - core {brier(g, 'wb_p') - brier(g, 'core_explain'):+.4f} [{lo:+.4f}, {hi:+.4f}]"
          f"   wb - gbm {brier(g, 'wb_p') - brier(g, 'gbm_explain'):+.4f} [{lo1:+.4f}, {hi1:+.4f}]")

print("\n== Median per-site AUC (sites with >= 5 test spill-days)")
auc = M.groupby(["fold", "site"]).filter(lambda g: g.y.sum() >= 5 and (1 - g.y).sum() >= 5).groupby(["fold", "site"]).apply(
    lambda g: pd.Series({m: roc_auc_score(g.y, g[m]) for m in ["wb1_p", "wb_p", "core_explain", "gbm_explain"]}))
print(auc.groupby("fold").median().round(3).to_string())

print("\n== Spill-hours per site over each test year (site-years with > 24 observed hours): the old model's weak point")
H = M.groupby(["fold", "site"]).agg(obs=("h", "sum"), wb=("wb_hours", "sum"), wb1=("wb1_hours", "sum"), core=("core_hours", "sum"))
H = H[H.obs > 24]
for c in ["wb", "wb1", "core"]:
    e = H[c] / H.obs - 1
    print(f"  {c:5s} median |error| {e.abs().median():5.0%}   within +/-25%: {(e.abs() <= .25).mean():4.0%}   median bias {e.median():+5.0%}   pooled {H[c].sum() / H.obs.sum() - 1:+5.0%}")
print(f"  ({len(H)} site-years)")

print("\n== Calibration (both folds pooled): mean forecast vs observed frequency")
for m in ["wb_p", "core_explain"]:
    b = pd.cut(M[m], [-.01, .05, .2, .4, .6, .8, .95, 1.01])
    t = M.groupby(b, observed=True).agg(n=("y", "size"), forecast=(m, "mean"), observed=("y", "mean"))
    print(f"  {m}:  " + "  ".join(f"{r.forecast:.2f}->{r.observed:.2f} (n={r.n})" for r in t.itertuples()))

print("\n== By flow-data verdict (pooled over folds): Brier")
print(M.groupby("verdict").apply(lambda g: pd.Series({"site_days": len(g), "works": g.site.nunique(),
      **{m: brier(g, m) for m in ["clim", "wb1_p", "wb_p", "core_explain"]}})).round(4).to_string())

print("\n== Treated flow on the test years (daily, the quantity the water balance is fitted to)")
for fold, (t0, t1) in FOLDS.items():
    x = Fl[(Fl.fold == fold) & (Fl.date >= t0) & (Fl.date < t1) & Fl.tdv.notna()]
    e = (np.log(x.sim) - np.log(x.tdv)).groupby(x.site).median()
    a = (np.log(x.sim) - np.log(x.tdv)).abs().groupby(x.site).median()
    print(f"  fold {fold}: per-works median |error| {a.median():.0%} (p90 {a.quantile(.9):.0%}); median bias {e.median():+.0%}")

print("\n== Do the fitted numbers mean what they claim? Fitted (from treated flow only) vs ORIC's published values, fold B")
B = P[P.fold == "B"]
for name, f, o in (("foul flow (people + trade)", "foul_m3d", "oric_foul_m3d"), ("capacity (busiest-day treated)", "cap_m3d", "oric_cap_m3d"),
                   ("peak infiltration (p95) vs max allowance", "peak_infil_m3d", "oric_imax_m3d")):
    ok = B[o] > 0
    r = B.loc[ok, f] / B.loc[ok, o]
    print(f"  {name:42s} ratio median {r.median():.2f}  IQR {r.quantile(.25):.2f}-{r.quantile(.75):.2f}  log-corr {np.corrcoef(np.log(B.loc[ok, f]), np.log(B.loc[ok, o]))[0, 1]:.3f}  (n={ok.sum()})")
print(f"  spill start / capacity: median {B.spill_start_frac.median():.2f}, IQR {B.spill_start_frac.quantile(.25):.2f}-{B.spill_start_frac.quantile(.75):.2f}")
print(f"  infiltration driver chosen by treated-flow fit: {B['mode'].value_counts().to_dict()}")
M.to_pickle(os.path.join(INT, "wb_eval_rows.pkl"))
