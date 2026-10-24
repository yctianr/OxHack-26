"""Water balance for a sewage works, hourly, every term in m3. Fitted to measured treated flow; never sees spill labels.

    inflow    = foul + infiltration + runoff                        (m3/h)
    foul      = F * daily pattern                                   people + trade; +/-30% over the day, peak at noon
    runoff    = 10 * A * rain routed through a store of tau_f hours  1 mm on 1 ha = 10 m3; tau_f = 1-12 h (sewer travel)
    infiltration (two ways to drive it, chosen per works by treated-flow fit):
      "soil"  : rain fills a soil-moisture deficit (emptied by evaporation, capped at Dmax mm); rain beyond
                field capacity recharges a groundwater store G (drains over tau_g days); infiltration = k * G
      "river" : infiltration = k * max(0, Farmoor flow - q0)        measured river flow as the wetness signal
    treated   = min(inflow, C) + storm-tank pump-back               C = measured busiest-day treated flow (p99)
    fit       : daily treated flow; days at the plateau are censored (they say only "inflow was at least this")
    tank      : excess above C fills a tank of V m3 (V = 2 h at C, the usual design rule); returned when inflow < C
    spill     = inflow above S, once the tank is full. S is the ONE number fitted to spill records (training only):
                the inflow at which the overflow starts. S/C < 1 means it spills before reaching full treatment.

Probabilities come from inflow uncertainty, not from a fitted curve: the treated-flow residuals on days below
capacity give a daily multiplicative error (sigma, lag-1 rho), simulated as AR(1) noise."""
import os
import numpy as np
import pandas as pd
from numba import njit
from scipy.optimize import least_squares

TANK_HOURS = 2.0
SPIN_DAYS = 60                    # discard the first two months of each run (states start from a warm-up year)
CENSOR_AT = 0.9                   # treated flow >= 90% of its 99th percentile = works at capacity (censored)
TAU_FAST_MAX = float(os.environ.get("WB_TAU_FAST_MAX", 12))   # h; daily data cannot resolve it
DIURNAL_AMP, DIURNAL_PEAK_H = 0.3, 12   # foul-flow pattern; daily data can't identify it, so it is a fixed prior


@njit(cache=True)
def simulate(rain, pet, wet, shape, mode, F, A, tau_f, k, p1, p2, C, V, S, mult):
    """One hourly run. mode 0: p1 = tau_g (days), p2 = Dmax (mm). mode 1: p1 = q0 (m3/s), p2 unused.
    C = treatment capacity (caps treated flow); S = inflow at which the overflow starts (tank, then spill).
    Returns treated, spill, inflow (m3/h)."""
    n = rain.shape[0]
    treated, spill, inflow = np.empty(n), np.empty(n), np.empty(n)
    af = np.exp(-1.0 / tau_f)
    ag = np.exp(-1.0 / (p1 * 24.0)) if mode == 0 else 0.0
    routed, D, G, tank = 0.0, (0.5 * p2 if mode == 0 else 0.0), 0.0, 0.0
    for t in range(n):
        routed = af * routed + (1.0 - af) * rain[t]
        if mode == 0:
            D += pet[t] * (1.0 - D / p2) - rain[t]
            rech = 0.0
            if D < 0.0:
                rech, D = -D, 0.0
            elif D > p2:
                D = p2
            G = ag * G + rech
            infil = k * G
        else:
            infil = k * max(0.0, wet[t] - p1)
        q = (F * shape[t] + infil + 10.0 * A * routed) * mult[t]
        inflow[t] = q
        if q > S:
            ex = q - S
            room = V - tank
            if ex <= room:
                tank += ex
                spill[t] = 0.0
            else:
                tank = V
                spill[t] = ex - room
            treated[t] = min(q, C)
        else:
            back = min(tank, max(0.0, C - q))
            tank -= back
            treated[t] = min(q, C) + back
            spill[t] = 0.0
    return treated, spill, inflow


class Works:
    """Hourly drivers for one works, with a warm-up year prepended so stores start in a sensible state."""

    def __init__(self, rain, pet_h, wet_h, local_day, local_hour, n_warm=8760):
        self.n_warm = n_warm
        self.rain = np.r_[rain[:n_warm], rain]
        self.pet = np.r_[pet_h[:n_warm], pet_h]
        self.wet = np.r_[wet_h[:n_warm], wet_h]
        shape = 1 + DIURNAL_AMP * np.cos(2 * np.pi * (local_hour - DIURNAL_PEAK_H) / 24)
        self.shape = np.r_[shape[:n_warm], shape]
        self.day = local_day                                    # local calendar day of each real hour (codes)
        self.ones = np.ones(len(self.rain))

    def run(self, mode, th, V=None, mult=None, S=None):
        F, A, tau_f, k, p1, p2, C = th
        V = TANK_HOURS * C if V is None else V
        S = C if S is None else S
        tr, sp, q = simulate(self.rain, self.pet, self.wet, self.shape, mode, F, A, tau_f, k, p1, p2, C, V, S,
                             self.ones if mult is None else mult)
        w = self.n_warm
        return tr[w:], sp[w:], q[w:]


def daily_sum(v, day, nday):
    return np.bincount(day, weights=v, minlength=nday)


def fit_works(wk, tdv_d, fit_days, nday, ref, V=None):
    """Fit both infiltration modes to daily treated flow on fit_days (bool, per local day); return the better one.
    ref: dict with foul (m3/h), cap (m3/h, prior centre), q_med (median Farmoor flow)."""
    obs = np.log(tdv_d[fit_days])
    plateau = np.nanquantile(tdv_d[fit_days], 0.99)              # busiest-day treated flow (m3/day)
    capped = tdv_d[fit_days] >= CENSOR_AT * plateau                # at the plateau: inflow >= obs
    C_fix = np.log(plateau / 24.0)                                 # capacity is measured, not fitted
    best = None
    for mode in (0, 1):
        if mode == 0:   # F, A, tau_f, k, tau_g, Dmax, C
            lo = [0.2 * ref["foul"], 0.01, 1, 0, 3, 20, 0.4 * ref["cap"]]
            hi = [5 * ref["foul"], 5e4, TAU_FAST_MAX, 50 * ref["foul"], 365, 300, 3 * ref["cap"]]
            starts = [[ref["foul"], 5, 4, ref["foul"] / 30, g, 100, ref["cap"]] for g in (20, 60, 150)]
        else:           # F, A, tau_f, k, q0, -, C
            lo = [0.2 * ref["foul"], 0.01, 1, 0, 0, 0.5, 0.4 * ref["cap"]]
            hi = [5 * ref["foul"], 5e4, TAU_FAST_MAX, 20 * ref["foul"], 4 * ref["q_med"], 1, 3 * ref["cap"]]
            starts = [[ref["foul"], 5, 4, ref["foul"] / ref["q_med"], q, 0.75, ref["cap"]]
                      for q in (0.3 * ref["q_med"], ref["q_med"])]
        lo, hi = np.log(np.maximum(lo, 1e-6)), np.log(np.array(hi, float))
        lo, hi = lo[:6], hi[:6]

        def resid(x):
            tr, _, q = wk.run(mode, np.exp(np.r_[x, C_fix]), V)
            e = np.log(np.maximum(daily_sum(tr, wk.day, nday)[fit_days], 1e-6)) - obs
            e_in = np.log(np.maximum(daily_sum(q, wk.day, nday)[fit_days], 1e-6)) - obs
            return np.where(capped, np.minimum(e_in, 0.0), e)      # censored days: only penalise too little inflow

        for s in starts:
            x0 = np.clip(np.log(np.maximum(s[:6], 1e-6)), lo + 1e-3, hi - 1e-3)
            r = least_squares(resid, x0, bounds=(lo, hi), loss="soft_l1", f_scale=0.1, diff_step=1e-2, max_nfev=300)
            cost = np.median(np.abs(r.fun))
            if best is None or cost < best[0]:
                best = (cost, mode, np.exp(np.r_[r.x, C_fix]))
    return best   # (median |log error| on fit days, mode, params)


def noise_model(wk, mode, th, tdv_d, fit_days, nday, V=None):
    """Robust residual sigma and lag-1 rho of log treated flow on fit days when the works was below 90% of capacity."""
    tr = wk.run(mode, th, V)[0]
    sim = daily_sum(tr, wk.day, nday)
    hours = np.bincount(wk.day, minlength=nday)
    ok = fit_days & (sim < 0.9 * th[6] * hours)
    e = pd.Series(np.where(ok, np.log(tdv_d) - np.log(np.maximum(sim, 1e-6)), np.nan))
    e = e - e.median()
    sigma = 1.4826 * np.nanmedian(np.abs(e))                       # robust: a few bad meter days don't inflate it
    rho = e.clip(-3 * sigma, 3 * sigma).autocorr(1)
    return float(sigma), float(np.clip(rho if np.isfinite(rho) else 0.0, 0, 0.99))


def ensemble(wk, mode, th, sigma, rho, nday, n=200, V=None, seed=0, S=None):
    """Monte Carlo runs with AR(1) daily multiplicative inflow error. Returns spill (n, hours) in m3/h."""
    rng = np.random.default_rng(seed)
    nh = len(wk.rain)
    day_all = np.r_[np.zeros(wk.n_warm, np.int64), wk.day]
    out = np.empty((n, nh - wk.n_warm))
    for i in range(n):
        z = rng.standard_normal(nday)
        e = np.empty(nday)
        e[0] = z[0] * sigma
        for d in range(1, nday):
            e[d] = rho * e[d - 1] + np.sqrt(1 - rho ** 2) * sigma * z[d]
        mult = np.exp(e[day_all] - sigma ** 2 / 2)
        out[i] = wk.run(mode, th, V, mult, S)[1]
    return out


def fit_threshold(wk, mode, th, sigma, rho, nday, utc_day, nud, y_day, train_ud, V=None, grid=None):
    """Stage 2: the overflow's start point S, as a fraction of capacity C, by training Brier on daily any-spill."""
    grid = np.round(np.arange(0.3, 1.51, 0.025), 3) if grid is None else grid
    best = None
    for f in grid:
        on = ensemble(wk, mode, th, sigma, rho, nday, n=60, V=V, S=f * th[6]) > 1e-6
        p = np.stack([np.bincount(utc_day, weights=o, minlength=nud) > 0 for o in on]).mean(0)
        b = np.mean((p[train_ud] - y_day[train_ud]) ** 2)
        if best is None or b < best[0]:
            best = (b, f)
    return best[1]
