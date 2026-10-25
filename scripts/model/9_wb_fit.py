"""Fit the water balance (wb.py) at every works with usable treated flow, for both evaluation folds.

Stage 1 is fitted to daily treated flow (TDV) before each fold's cut-off, with no spill labels. Stage 2 fits one
number from training-period spill records: the inflow at which the overflow starts, as a fraction of capacity.
For every UTC day it then simulates an ensemble and writes P(any spill), expected spill-hours and spill volume,
for the full model (wb_*) and for stage 1 alone with spilling assumed to start at capacity (wb1_*)
(data/interim/wb_predictions.pkl), simulated vs measured daily treated flow (wb_flow.pkl), plus fitted parameters in physical units (data/interim/wb_params.csv).
Usage: python scripts/model/9_wb_fit.py [permit ...]   (default: all works not marked "drop")"""
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from common import FOLDS, INT, RAW, TZ, load, rain_for
import wb
warnings.filterwarnings("ignore")

# storm-tank volumes stated by a source (tanks.csv: Find a Tender, Hammond et al. 2021, Parliament evidence); elsewhere V = 2 h at capacity
TANKS = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tanks.csv")).set_index("permit").tank_m3.astype(float).to_dict()


def drivers():
    inp, lab, si, names = load()
    idx = inp.index
    loc = idx.tz_convert(TZ).tz_localize(None).normalize()
    ldays = pd.DatetimeIndex(np.unique(loc))
    local_day = np.searchsorted(ldays, loc)
    utc_dates = idx.normalize()
    udays = pd.DatetimeIndex(np.unique(utc_dates))
    utc_day = np.searchsorted(udays, utc_dates)
    et = pd.read_csv(os.path.join(RAW, "openmeteo", "et0_oxford_daily.csv"), skiprows=3, index_col=0, parse_dates=True).iloc[:, 0]
    pet_h = et.reindex(loc).ffill().bfill().values / 24.0
    wet_h = np.exp(pd.Series(inp["lflow_1100TH"].values).ffill().bfill().values)
    return inp, lab, si, ldays, local_day, udays, utc_day, pet_h, wet_h


def run_one(permit):
    inp, lab, si, ldays, local_day, udays, utc_day, pet_h, wet_h = drivers()
    W = pd.read_csv(os.path.join(INT, "wb_works.csv")).set_index("permit")
    T = pd.read_pickle(os.path.join(INT, "wb_tdv.pkl"))
    w = W.loc[permit]
    rain = np.nan_to_num(rain_for(inp, si, permit))
    wk = wb.Works(rain, pet_h, wet_h, local_day, inp.index.tz_convert(TZ).hour.values)
    nday, nud = len(ldays), len(udays)
    tdv_d = T[permit].reindex(ldays).values
    ref = dict(foul=w.foul_ls * 3.6, cap=(w.fft_ls if w.fft_ls > 0 else w.tdv_p99_m3d / 86.4) * 3.6,
               q_med=float(np.median(wet_h)))
    V = TANKS.get(permit) if "WB_TANK_H" not in os.environ else None
    y, m = lab[permit]
    valid_ud = np.bincount(utc_day, weights=m.astype(float), minlength=len(udays)) / np.bincount(utc_day) >= 0.9
    y_ud = (np.bincount(utc_day, weights=np.where(m, y, 0) > 0, minlength=len(udays)) > 0).astype(float)
    params, preds, flows = [], [], []
    for fold, (t0, t1) in FOLDS.items():
        fit_days = np.isfinite(tdv_d) & (np.arange(nday) >= wb.SPIN_DAYS) & (ldays < t0)
        if fit_days.sum() < 300:
            continue
        cost, mode, th = wb.fit_works(wk, tdv_d, fit_days, nday, ref, V)
        sigma, rho = wb.noise_model(wk, mode, th, tdv_d, fit_days, nday, V)
        tr, sp, q = wk.run(mode, th, V)
        sim_d = wb.daily_sum(tr, wk.day, nday)
        test_days = np.isfinite(tdv_d) & (ldays >= t0) & (ldays < t1)
        test_err = np.median(np.abs(np.log(sim_d[test_days]) - np.log(tdv_d[test_days]))) if test_days.sum() >= 30 else np.nan
        # stage 2: the one spill-record number, fitted on training days only
        train_ud = valid_ud & (udays < t0) & (np.arange(nud) >= wb.SPIN_DAYS)
        s_frac = wb.fit_threshold(wk, mode, th, sigma, rho, nday, utc_day, nud, y_ud, train_ud, V=V)
        out = {}
        for tag, S in (("wb", s_frac * th[6]), ("wb1", th[6])):            # wb1 = stage 1 only (spill at capacity)
            ens = wb.ensemble(wk, mode, th, sigma, rho, nday, V=V, S=S)      # (n, hours) spill m3/h
            on = ens > 1e-6
            cnt = np.stack([np.bincount(utc_day, weights=o, minlength=nud) for o in on])
            out[f"{tag}_p"], out[f"{tag}_hours"] = (cnt > 0).mean(0), cnt.mean(0)
            out[f"{tag}_vol_m3"] = np.bincount(utc_day, weights=ens.mean(0), minlength=nud)
        F, A, tau_f, k, p1, p2, C, As = th
        params.append(dict(permit=permit, site=w.site, fold=fold, mode=["soil", "river"][mode], fit_err=cost,
                           test_err=test_err, sigma=sigma, rho=rho, foul_m3d=F * 24, oric_foul_m3d=w.foul_ls * 86.4,
                           area_ha=A, area_sat_ha=As, tau_fast_h=tau_f, k=k, tau_g_d=p1 if mode == 0 else np.nan,
                           dmax_mm=p2, q0_m3s=p1 if mode == 1 else np.nan,
                           cap_m3d=C * 24, oric_cap_m3d=w.fft_ls * 86.4, tank_m3=V if V else wb.TANK_HOURS * C,
                           peak_infil_m3d=np.nan, oric_imax_m3d=w.imax_ls * 86.4, spill_start_frac=s_frac,
                           verdict=w.verdict))
        inf_d = wb.daily_sum(wk.run(mode, th, V, parts=True)[3], wk.day, nday)
        params[-1]["peak_infil_m3d"] = float(np.nanquantile(inf_d[ldays < t0], 0.95))
        params[-1]["summer_infil_m3d"] = float(np.median(inf_d[(ldays < t0) & ldays.month.isin([7, 8])]))
        preds.append(pd.DataFrame({"site": permit, "fold": fold, "date": udays, **out}))
        flows.append(pd.DataFrame({"site": permit, "fold": fold, "date": ldays, "tdv": tdv_d, "sim": sim_d,
                                   "train": fit_days}))
    return params, preds, flows


if __name__ == "__main__":
    W = pd.read_csv(os.path.join(INT, "wb_works.csv"))
    todo = sys.argv[1:] or W.loc[~W.verdict.str.startswith("drop"), "permit"].tolist()
    with ProcessPoolExecutor(max_workers=min(8, len(todo))) as ex:
        res = list(ex.map(run_one, todo))
    P = pd.DataFrame([r for ps, _, _ in res for r in ps])
    D = pd.concat([d for _, ds, _ in res for d in ds], ignore_index=True)
    Fl = pd.concat([d for _, _, fs in res for d in fs], ignore_index=True)
    tag = os.environ.get("WB_OUT", "" if not sys.argv[1:] else "_subset")    # suffix for experiment runs
    P.to_csv(os.path.join(INT, f"wb_params{tag}.csv"), index=False)
    D.to_pickle(os.path.join(INT, f"wb_predictions{tag}.pkl"))
    Fl.to_pickle(os.path.join(INT, f"wb_flow{tag}.pkl"))
    pd.set_option("display.width", 250)
    cols = ["site", "fold", "mode", "fit_err", "test_err", "sigma", "foul_m3d", "oric_foul_m3d", "area_ha", "area_sat_ha", "tau_fast_h",
            "tau_g_d", "dmax_mm", "q0_m3s", "cap_m3d", "oric_cap_m3d", "peak_infil_m3d", "oric_imax_m3d", "summer_infil_m3d", "spill_start_frac"]
    print(P[cols].round(2).to_string(index=False))
