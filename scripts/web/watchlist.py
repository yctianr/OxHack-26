"""Regulator watchlist: which treatment works spill when the evidence says they shouldn't. Writes web/watchlist/data.json.

Two independent lines of evidence per works, both "leads to check", never findings of a breach:
  A. Spilling while treating below the permit. Permits require a works to keep treating its flow to full treatment
     (FFT) while it discharges; compliance is judged as 95% of flow readings above 92% of FFT. On days a works spilled
     for 20+ hours its treatment should have run at FFT all day, so a daily treated flow below 92% of FFT is a lead.
     Daily treated flow is measured at the outlet and averaged over the day, so leads use a wider margin: days below
     80% of FFT (SCREEN_SHARE). Days below 92% are reported as context.
  B. Spills the weather doesn't explain. Test years only (Oct 2024 - Oct 2026): days the monitor recorded 1+ hour of
     spilling while both the statistical model and the physics-only water balance (spilling starts at capacity, no
     spill records used) gave under 5% chance from the rain and wetness.
Context from Thames Water's own 2025 EDM return: asset type, stated reason for high spilling, investigation and
improvement activity. Run from the repo root after scripts/model/8_wb_prep.py, 9_wb_fit.py and 10_wb_evaluate.py."""
import json
import os
import numpy as np
import pandas as pd

INT, RAW, OUT = "data/interim", "data/raw", "web/watchlist"
TZ = "Europe/London"
PERMIT_SHARE = 0.92            # permit compliance: flow above 92% of FFT while discharging
SCREEN_SHARE = 0.80            # lead threshold: margin for outlet metering and daily averaging
ALL_DAY_H = 20                 # a day spilling at least this long had its storm tanks in use all day
UNEXPLAINED_P = 0.05

W = pd.read_csv(os.path.join(INT, "wb_works.csv")).set_index("permit")
T = pd.read_pickle(os.path.join(INT, "wb_tdv.pkl"))
lab = pd.read_pickle(os.path.join(INT, "labels_clean.pkl"))
inp = pd.read_pickle(os.path.join(INT, "inputs_clean.pkl"))
si = pd.read_csv(os.path.join(INT, "site_inputs.csv")).set_index("permit")
M = pd.read_pickle(os.path.join(INT, "wb_eval_rows.pkl"))
sites = pd.read_csv(os.path.join(INT, "sites61.csv")).set_index("permitNumber")

ar = pd.read_excel(os.path.join(RAW, "annual_returns", "tw_edm_2025.xlsx"), sheet_name=0, header=5)
ar.columns = [" ".join(str(c).split()) for c in ar.columns]
ar = ar.drop_duplicates("EA Permit Reference (EA Consents Database)").set_index("EA Permit Reference (EA Consents Database)")


def col(name):
    return next(c for c in ar.columns if c.startswith(name))


loc = inp.index.tz_convert(TZ).tz_localize(None).normalize()
days = pd.date_range("2022-04-01", "2025-12-31", freq="D")


def rain_for(p):
    a, b = inp[f"rain_{si.loc[p, 'rain1']}"].values, inp[f"rain_{si.loc[p, 'rain2']}"].values
    w1, w2 = 1 / si.loc[p, "d1"] ** 2, 1 / si.loc[p, "d2"] ** 2
    return (w1 * a + w2 * b) / (w1 + w2)


def clean(v):
    return None if v is None or (isinstance(v, float) and not np.isfinite(v)) else v


out = []
for p, w in W.iterrows():
    y, m = lab[p]
    hrs = pd.Series(np.where(m, y, 0.0), index=loc).groupby(level=0).sum()
    ok = pd.Series(m.astype(float), index=loc).groupby(level=0).mean() >= 0.9
    hrs = hrs.where(ok).reindex(days)
    rain = pd.Series(np.nan_to_num(rain_for(p)), index=loc).groupby(level=0).sum().reindex(days)
    q = T[p].reindex(days) / 86.4                                       # m3/day -> mean L/s over the day
    fft = float(w.fft_ls) if w.fft_ls > 0 else None

    # A: all-day spill days treating below 92% of the permitted flow
    allday = (hrs >= ALL_DAY_H) & q.notna()
    a_n = int(allday.sum())
    below = allday & (q < PERMIT_SHARE * fft) if fft else allday & False
    well_below = allday & (q < SCREEN_SHARE * fft) if fft else allday & False
    # B: spill days the weather doesn't explain (out-of-sample test years)
    e = M[M.site == p]
    unexp = e[(e.h >= 1) & (e.core_explain < UNEXPLAINED_P) & (e.wb1_p < UNEXPLAINED_P)]
    spill_days_test = int((e.h >= 1).sum())

    r = ar.loc[p] if p in ar.index else None
    yearly = {str(yr): round(float(hrs[hrs.index.year == yr].sum())) for yr in (2023, 2024, 2025)}
    score = int(well_below.sum()) + len(unexp)
    share = well_below.sum() / a_n if a_n else 0.0
    if w.verdict.startswith("drop"):
        level = "insufficient"
    elif (a_n >= 10 and share >= 0.3) or len(unexp) >= 10:
        level = "strong"
    elif well_below.sum() >= 5 or len(unexp) >= 3:
        level = "moderate"
    else:
        level = "low"
    out.append(dict(
        id=p, name=str(r["Site Name (WaSC operational) [optional]"]) if r is not None else w.site, place=w.site,
        lon=None, lat=None,
        water=str(r[col("Receiving Water")]).title() if r is not None else None,
        catchment=str(r[col("WFD Waterbody Catchment Name")]) if r is not None else None,
        asset=str(r["Storm Discharge Asset Type"]) if r is not None else None,
        tw_reason=str(r[col("High Spill Frequency - Operational Review - Single year reason")]) if r is not None else None,
        tw_reason_lt=str(r[col("High Spill Frequency - Operational Review - Long-term average reason")]) if r is not None else None,
        tw_investigation=str(r["Investigation activity for the reporting period"]) if r is not None else None,
        tw_improvement=str(r["Improvement activity for the reporting period"]) if r is not None else None,
        spills_2025=clean(float(r["Counted spills using 12-24h count method"])) if r is not None else None,
        fft_ls=fft, required_ls=clean(round(float(w.req_ls), 1)), population=round(float(w.pe)),
        data_check=w.verdict,
        allday_days=a_n, below_permit_days=int(below.sum()), well_below_days=int(well_below.sum()),
        well_below_share=round(float(share), 3),
        median_allday_pct_fft=clean(round(float((q[allday] / fft).median() * 100))) if fft and a_n else None,
        unexplained_days=len(unexp), spill_days_test=spill_days_test,
        unexplained_dates=[d.strftime("%Y-%m-%d") for d in unexp.date],
        spill_hours=yearly, score=score, level=level,
        series=dict(q=[None if not np.isfinite(v) else round(float(v), 1) for v in q.values],
                    h=[None if not np.isfinite(v) else round(float(v), 1) for v in hrs.values],
                    r=[round(float(v), 1) for v in rain.values])))
    s = sites.loc[p]
    out[-1]["lon"], out[-1]["lat"] = round(float(s.lon), 5), round(float(s.lat), 5)

out.sort(key=lambda d: ({"strong": 0, "moderate": 1, "low": 2, "insufficient": 3}[d["level"]], -d["score"]))
os.makedirs(OUT, exist_ok=True)
meta = dict(days=[d.strftime("%Y-%m-%d") for d in days], permit_share=PERMIT_SHARE, screen_share=SCREEN_SHARE, all_day_h=ALL_DAY_H,
            unexplained_p=UNEXPLAINED_P, test_window=["2024-10-01", "2026-10-22"],
            totals=dict(works=len(out), strong=sum(d["level"] == "strong" for d in out),
                        moderate=sum(d["level"] == "moderate" for d in out),
                        below_permit_days=sum(d["below_permit_days"] for d in out),
                        well_below_days=sum(d["well_below_days"] for d in out),
                        allday_days=sum(d["allday_days"] for d in out),
                        unexplained_days=sum(d["unexplained_days"] for d in out),
                        no_investigation=sum((d["tw_investigation"] or "").startswith("No investigation") and d["level"] in ("strong", "moderate") for d in out)))
# main rivers for the locator map (from scripts/web/data.py output), every 3rd vertex
rivers = [dict(n=r["n"], p=[[q[0], q[1]] for q in r["p"][::3] + [r["p"][-1]]]) for r in json.load(open("web/data/rivers.json")) if r["m"]]
json.dump(dict(meta=meta, works=out, rivers=rivers), open(os.path.join(OUT, "data.json"), "w"), separators=(",", ":"))
pd.set_option("display.width", 220)
print(pd.DataFrame(out)[["name", "level", "score", "allday_days", "well_below_days", "below_permit_days", "median_allday_pct_fft", "unexplained_days",
                         "spill_days_test", "tw_reason", "tw_investigation"]].to_string(index=False))
print(meta["totals"], f"{os.path.getsize(os.path.join(OUT, 'data.json')) / 1e6:.2f} MB")
