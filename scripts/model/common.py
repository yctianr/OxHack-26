"""Shared pieces of the Spillcast model: paths, the audited data layer, and the bathtub building blocks.

z_t = b0 + b1*log(Farmoor flow) + b2*F_tau(t)      F_tau = rain through a linear store, in mm
P(spilling in hour t) = sigmoid(z_t);  P(any spill on day d) = sigmoid(c0 + c1*max_t z_t)"""
import os
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.signal import lfilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
INT = os.path.join(ROOT, "data", "interim")
TZ = "Europe/London"
FOLDS = {"A": ("2024-10-01", "2025-10-01"), "B": ("2025-10-01", "2026-10-23")}   # test windows (train = before)
TAUS = (6, 12, 24, 48, 96)                                                        # rain store time constants, h
FLOW = "lflow_1100TH"                                                             # Thames at Farmoor


def load():
    """Audited inputs (hourly, UTC), fractional labels {permit: (y, mask)}, per-site rain gauges, site names."""
    inp = pd.read_pickle(os.path.join(INT, "inputs_clean.pkl"))
    lab = pd.read_pickle(os.path.join(INT, "labels_clean.pkl"))
    si = pd.read_csv(os.path.join(INT, "site_inputs.csv")).set_index("permit")
    names = pd.read_csv(os.path.join(INT, "sites61.csv")).set_index("permitNumber").locationName
    return inp, lab, si, names


def rain_for(inp, si, p):
    """Inverse-distance mix of the site's two nearest audited gauges (mm per hour)."""
    a, b = inp[f"rain_{si.loc[p, 'rain1']}"].values, inp[f"rain_{si.loc[p, 'rain2']}"].values
    w1, w2 = 1 / si.loc[p, "d1"] ** 2, 1 / si.loc[p, "d2"] ** 2
    return (w1 * a + w2 * b) / (w1 + w2)


def store(r, tau):
    """Linear reservoir: exponentially weighted rain over ~tau hours, in mm."""
    a = np.exp(-1 / tau)
    return lfilter([1 - a], [1, -a], r) * tau


def cut_at_midnight(F, tau, hod):
    """Forecast version of a store: its value at 00:00 UTC, then pure decay through the day (no later rain)."""
    start = np.flatnonzero(hod == 0)
    F0 = np.repeat(F[np.maximum(start - 1, 0)], np.diff(np.r_[start, len(F)]))
    F0 = np.r_[np.full(start[0], F[0]), F0][: len(F)]
    return F0 * np.exp(-(hod + 1) / tau)


def logit_fit(X, y):
    """Logistic regression on standardised inputs with a tiny ridge; y may be fractional. Returns (b, mu, sd, nll)."""
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.column_stack([np.ones(len(X)), (X - mu) / sd])

    def f(b):
        z = Z @ b
        return (np.sum(np.logaddexp(0, z) - y * z) + 1e-3 * b[1:] @ b[1:],
                Z.T @ (1 / (1 + np.exp(-z)) - y) + 2e-3 * np.r_[0, b[1:]])
    b = minimize(f, np.zeros(Z.shape[1]), jac=True, method="L-BFGS-B").x
    return b, mu, sd, f(b)[0]


def lin(fit, X):
    b, mu, sd, _ = fit
    return np.column_stack([np.ones(len(X)), (X - mu) / sd]) @ b


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def fit_core(W, R, train):
    """Bathtub core: choose tau by training likelihood. Returns (fit, tau)."""
    best = None
    for tau in TAUS:
        fit = logit_fit(np.column_stack([W, store(R, tau)])[train[0]], train[1])
        if best is None or fit[3] < best[0][3]:
            best = (fit, tau)
    return best


def raw_coefs(fit):
    """Standardised coefficients -> plain units: z = b0 + b1*log(flow) + b2*F_mm."""
    b, mu, sd, _ = fit
    b1, b2 = b[1] / sd[0], b[2] / sd[1]
    return b[0] - b1 * mu[0] - b2 * mu[1], b1, b2


def episodes(on, max_gap=6):
    """Lengths (h) of spill episodes: runs of spilling hours merged across gaps <= max_gap hours."""
    runs, cur, gap = [], 0, 0
    for v in on:
        if v:
            cur, gap = (cur + 1 + gap if cur else 1), 0
        elif cur:
            gap += 1
            if gap > max_gap:
                runs.append(cur)
                cur, gap = 0, 0
    return np.array(runs + ([cur] if cur else []))
