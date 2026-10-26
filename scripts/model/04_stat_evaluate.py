"""Principled evaluation on the audited data layer (03_clean.py). Two tasks, never mixed:

  EXPLAIN  - given the weather that actually fell (observed rain for day d), how well does the model reproduce
             spills? This is what volume estimates and infrastructure what-ifs rely on. No observed spill state.
  FORECAST - standing at 00:00 UTC on day d: rain only up to 00:00 (the fast store then decays), flow already
             published, and the overflow's current state (spilling at midnight, hours spilled yesterday).
             Lower bound: no rain forecast. Persistence is the baseline to beat; onset days are scored separately.

Protocol: rolling origin (fold A: train to 2024-09-30, test WY2025; fold B: train to 2025-09-30, test to the end).
Sites are included on TRAINING data only. Primary metric: Brier score over all valid site-days, with 95% CIs from a
weekly block bootstrap that resamples the same weeks for every site (sites share storms, so site-level resampling
understates uncertainty). Comparators get the same information as the model they are compared with."""

import os
import warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from common import FLOW, FOLDS, INT, TAUS, cut_at_midnight, lin, load, logit_fit, rain_for, store
warnings.filterwarnings("ignore")
inp, lab, si, names = load()
idx = inp.index
day = np.asarray((idx - idx[0]).days)
hod = idx.hour.values
ND = day.max() + 1
dates = pd.date_range(idx[0].normalize(), periods=ND, freq="D")
W = inp[FLOW].values                       # Thames at Farmoor, causally aligned in 03_clean.py


def daily(v, how):
    return getattr(pd.Series(v).groupby(day), how)().reindex(range(ND)).values


rows = []
for p, (y, m) in lab.items():
    R = rain_for(inp, si, p)
    vd = daily(m.astype(float), "mean") >= 0.9
    yd = (daily(np.where(m, y, 0), "max") > 0).astype(float)
    hd = daily(np.where(m, y, 0), "sum")
    yend = daily(np.where(m, (y > 0).astype(float), 0), "last")
    mid, hprev = np.r_[0, yend[:-1]], np.r_[0, hd[:-1]]                       # state known at 00:00 of day d
    vprev = np.r_[False, vd[:-1]]
    for fold, (t0, t1) in FOLDS.items():
        tr_h = m & (idx < t0)
        dtr = vd & vprev & (dates < t0)
        dte = vd & vprev & (dates >= t0) & (dates < t1)
        if (y[tr_h] > 0).sum() < 48 or yd[dtr].sum() < 10 or dte.sum() < 100:   # training-only inclusion
            continue
        out = pd.DataFrame({"site": p, "fold": fold, "date": dates[dte], "y": yd[dte], "h": hd[dte],
                            "mid": mid[dte], "clim": yd[dtr].mean()})
        # --- physics core (hourly): z = b0 + b1*flow + b2*store_tau(rain) [+ hinge on flow] ---
        for name, hinge in (("core", False), ("core_hinge", True)):
            best = None
            for tau in TAUS:
                F = store(R, tau)
                for q in ((None, .3, .5, .7) if hinge else (None,)):
                    Wx = W if q is None else np.maximum(0, W - np.quantile(W[tr_h], q))
                    fit = logit_fit(np.column_stack([Wx, F])[tr_h], y[tr_h])
                    if best is None or fit[3] < best[0][3]:
                        best = (fit, tau, Wx)
            fit, tau, Wx = best
            # EXPLAIN: observed rain
            z = lin(fit, np.column_stack([Wx, store(R, tau)]))
            zmax = daily(z, "max")
            cal = logit_fit(zmax[dtr, None], yd[dtr])
            out[f"{name}_explain"] = 1 / (1 + np.exp(-lin(cal, zmax[dte, None])))
            out[f"{name}_hours"] = daily(np.where(m, 1 / (1 + np.exp(-z)), 0), "sum")[dte]
            # FORECAST: rain cut at 00:00, plus state
            zf = lin(fit, np.column_stack([Wx, cut_at_midnight(store(R, tau), tau, hod)]))
            Xf = np.column_stack([daily(zf, "max"), mid, hprev])
            calf = logit_fit(Xf[dtr], yd[dtr])
            out[f"{name}_forecast"] = 1 / (1 + np.exp(-lin(calf, Xf[dte])))
            if name == "core":
                out["tau"], out["b_flow"], out["b_rain"] = tau, fit[0][1], fit[0][2]
        # persistence baseline: state only
        Xp = np.column_stack([mid, hprev])
        out["persistence"] = 1 / (1 + np.exp(-lin(logit_fit(Xp[dtr], yd[dtr]), Xp[dte])))
        # daily features for the matched gradient-boosting comparators
        rd = daily(R, "sum")
        out["f_rain_today"], out["f_rmax_today"] = rd[dte], daily(R, "max")[dte]
        for n in (1, 3, 7, 14, 30):
            out[f"f_rain_prev{n}"] = pd.Series(rd).shift(1).rolling(n, min_periods=1).sum().values[dte]
        for c in [c for c in inp.columns if c.startswith("lflow_") and inp[c].isna().mean() < .2]:
            out[f"f_{c}"] = daily(inp[c].values, "first")[dte]
        out["f_doy_s"], out["f_doy_c"] = np.sin(2 * np.pi * dates[dte].dayofyear / 365.25), np.cos(2 * np.pi * dates[dte].dayofyear / 365.25)
        out["f_hprev"] = hprev[dte]
        rows.append(out)
        # training rows for GBM (same construction on training days)
        tr = pd.DataFrame({"site": p, "fold": fold, "date": dates[dtr], "y": yd[dtr], "mid": mid[dtr], "f_hprev": hprev[dtr],
                           "f_rain_today": rd[dtr], "f_rmax_today": daily(R, "max")[dtr]})
        for n in (1, 3, 7, 14, 30):
            tr[f"f_rain_prev{n}"] = pd.Series(rd).shift(1).rolling(n, min_periods=1).sum().values[dtr]
        for c in [c for c in inp.columns if c.startswith("lflow_") and inp[c].isna().mean() < .2]:
            tr[f"f_{c}"] = daily(inp[c].values, "first")[dtr]
        tr["f_doy_s"], tr["f_doy_c"] = np.sin(2 * np.pi * dates[dtr].dayofyear / 365.25), np.cos(2 * np.pi * dates[dtr].dayofyear / 365.25)
        rows.append(tr.assign(_train=True))
D = pd.concat(rows, ignore_index=True)
D["_train"] = D["_train"].fillna(False).astype(bool)
TE = D[~D._train].copy()

# matched gradient boosting: EXPLAIN gets today's rain, no state; FORECAST gets state, no rain after 00:00
base = [c for c in D.columns if c.startswith("f_") and c not in ("f_rain_today", "f_rmax_today", "f_hprev")]
for fold in FOLDS:
    tr, te = D[D._train & (D.fold == fold)], TE.fold == fold
    for name, feats in (("gbm_explain", base + ["f_rain_today", "f_rmax_today"]), ("gbm_forecast", base + ["mid", "f_hprev"])):
        cats = pd.Categorical(D.site).categories
        Xtr = tr[feats].assign(site=pd.Categorical(tr.site, cats).codes)
        Xte = TE.loc[te, feats].assign(site=pd.Categorical(TE.loc[te, "site"], cats).codes)
        clf = HistGradientBoostingClassifier(max_iter=600, learning_rate=0.04, max_leaf_nodes=31, l2_regularization=1.0,
                                             early_stopping=True, validation_fraction=0.15, n_iter_no_change=30,
                                             categorical_features=[Xtr.columns.get_loc("site")], random_state=0)
        TE.loc[te, name] = clf.fit(Xtr, tr.y).predict_proba(Xte)[:, 1]
TE.to_pickle(os.path.join(INT, "eval_predictions.pkl"))

# ---------------- metrics ----------------
TE["week"] = (TE.date - TE.date.min()).dt.days // 7
rng = np.random.default_rng(0)


def brier(d, col):
    return np.mean((d[col] - d.y) ** 2)


def boot_diff(d, a, b, n=1000):
    """Brier(a) - Brier(b) with a weekly block bootstrap (same weeks for all sites)."""
    se = ((d[a] - d.y) ** 2 - (d[b] - d.y) ** 2).groupby(d.week).agg(["sum", "count"])
    w = se.index.values
    stats = []
    for _ in range(n):
        s = se.loc[rng.choice(w, len(w))]
        stats.append(s["sum"].sum() / s["count"].sum())
    return np.mean((d[a] - d.y) ** 2 - (d[b] - d.y) ** 2), np.percentile(stats, [2.5, 97.5])


def report(d, cols, label):
    print(f"\n{label}: {d.site.nunique()} sites, {len(d):,} site-days, spill rate {d.y.mean():.3f}")
    clim = np.mean((d.clim - d.y) ** 2)
    for c in cols:
        aucs = [roc_auc_score(g.y, g[c]) for _, g in d.groupby("site") if 0 < g.y.mean() < 1]
        print(f"  {c:20s} Brier {brier(d, c):.4f}  skill vs climatology {1 - brier(d, c) / clim:+.2f}  median site AUC {np.median(aucs):.3f}")


for fold, d in TE.groupby("fold"):
    print("=" * 100, f"\nFOLD {fold}")
    report(d, ["clim", "core_explain", "core_hinge_explain", "gbm_explain"], "EXPLAIN (observed rain), all days")
    for a, b in (("core_explain", "gbm_explain"), ("core_hinge_explain", "core_explain")):
        m_, ci = boot_diff(d, a, b); print(f"    {a} - {b}: {m_:+.4f}  95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]")
    report(d, ["clim", "persistence", "core_forecast", "core_hinge_forecast", "gbm_forecast"], "FORECAST (rain to 00:00 + state), all days")
    for a, b in (("core_forecast", "persistence"), ("core_forecast", "gbm_forecast")):
        m_, ci = boot_diff(d, a, b); print(f"    {a} - {b}: {m_:+.4f}  95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]")
    on = d[d.mid == 0]
    report(on, ["clim", "persistence", "core_forecast", "gbm_forecast", "core_explain", "gbm_explain"], "ONSET days only (not spilling at midnight)")
    for a, b in (("core_forecast", "persistence"), ("core_explain", "core_forecast")):
        m_, ci = boot_diff(on, a, b); print(f"    {a} - {b}: {m_:+.4f}  95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]")
    ph = d.groupby("site").agg(obs=("h", "sum"), pred=("core_hours", "sum"))
    print(f"  EXPLAIN spill-hours: daily MAE {np.mean(np.abs(d.core_hours - d.h)):.2f} h; total bias {d.core_hours.sum() / d.h.sum() - 1:+.1%}; "
          f"per-site bias median {(ph.pred / ph.obs.replace(0, np.nan) - 1).median():+.1%}")
