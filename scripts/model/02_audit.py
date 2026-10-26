"""Data-quality audit, bottom layer first: spill labels, rain gauges, river flow, treated flow.
Prints a report and writes audit_reconciliation.csv (used by 03_clean.py to mask unreliable site-years).
Needs data/raw/annual_returns/tw_edm_{2024,2025}.xlsx (Thames Water EDM annual returns)."""
import os
import warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
from common import INT, RAW, TZ
sites = pd.read_csv(os.path.join(INT, "sites61.csv"))
P61 = set(sites.permitNumber)
pd.set_option("display.width", 220, "display.max_columns", 30)

print("=" * 100, "\nA. SPILL LABELS (Thames Water alerts -> events)\n")
al = pd.read_csv(os.path.join(RAW, "thames_alerts.csv"))
al = al[al.permitNumber.isin(P61)].copy()
al["t"] = pd.to_datetime(al.datetime)
al = al.sort_values(["permitNumber", "locationName", "t", "alertType"])
print("alerts for the 61 sites:", len(al), al.alertType.value_counts().to_dict())
print("duplicate rows:", al.duplicated(["permitNumber", "locationName", "alertType", "datetime"]).sum())
print("permits with >1 locationName:", al.groupby("permitNumber").locationName.nunique().gt(1).sum())

# sequence state machine: what follows what?
seq = {}
for (_, _), g in al.groupby(["permitNumber", "locationName"]):
    k = g.alertType.tolist()
    for a, b in zip(k, k[1:]):
        seq[(a, b)] = seq.get((a, b), 0) + 1
print("\ntransition counts (prev -> next):")
for (a, b), n in sorted(seq.items(), key=lambda x: -x[1]):
    flag = "" if (a, b) in {("Start", "Stop"), ("Stop", "Start"), ("Offline start", "Offline stop"), ("Offline stop", "Start"),
                             ("Stop", "Offline start"), ("Offline stop", "Offline start")} else "   <-- anomaly"
    print(f"  {a:14s} -> {b:14s} {n:6d}{flag}")

ev = pd.read_csv(os.path.join(RAW, "events.csv"))
ev = ev[ev.permitNumber.isin(P61)].copy()
ev["start"], ev["stop"] = pd.to_datetime(ev.start), pd.to_datetime(ev.stop)
print(f"\nevents: {len(ev)}; open (no stop): {ev.stop.isna().sum()}; zero-length: {(ev.hours == 0).sum()}; "
      f"negative: {(ev.hours < 0).sum()}; > 7 days: {(ev.hours > 168).sum()}; > 30 days: {(ev.hours > 720).sum()}")
print("longest events:\n", ev.nlargest(6, "hours")[["locationName", "start", "stop", "hours"]].to_string(index=False))
# overlapping events within a site
ov = 0
for _, g in ev.dropna(subset=["stop"]).sort_values("start").groupby("permitNumber"):
    ov += (g.start.values[1:] < g.stop.values[:-1]).sum()
print("overlapping events within a site:", ov)
# short blips
print(f"events < 15 min: {(ev.hours < 0.25).sum()} ({(ev.hours < 0.25).mean():.1%}); gaps < 1 h between consecutive events: ", end="")
g_ = ev.dropna(subset=["stop"]).sort_values(["permitNumber", "start"])
gap = (g_.groupby("permitNumber").start.shift(-1) - g_.stop).dt.total_seconds() / 3600
print(f"{(gap < 1).sum()} ({(gap < 1).mean():.1%})")
# DST ambiguity: times in the repeated hour on fall-back days
amb = ev.start.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT").isna().sum()
print("event starts in an ambiguous/non-existent DST hour (dropped by tz_localize NaT):", amb)

# hour rounding: floor(start) .. ceil(stop) inflates spill-hours
e2 = ev.dropna(subset=["stop"])
rounded = ((e2.stop.dt.ceil("h") - e2.start.dt.floor("h")).dt.total_seconds() / 3600).sum()
print(f"exact spill-hours {e2.hours.sum():,.0f} vs hourly-binary labels {rounded:,.0f} (+{rounded / e2.hours.sum() - 1:.0%})")

# reconciliation with Thames Water's own EDM annual return
print("\nreconciliation with the Thames Water EDM annual return (calendar year, total spill hours):")
rows = []
for y, hdr in ((2024, 1), (2025, 5)):
    ar = pd.read_excel(os.path.join(RAW, "annual_returns", f"tw_edm_{y}.xlsx"), sheet_name=0, header=hdr)
    ar.columns = [" ".join(str(c).split()) for c in ar.columns]
    pcol = [c for c in ar.columns if c.startswith("EA Permit Reference")][0]
    dcol = [c for c in ar.columns if c.startswith("Total Duration")][0]
    ocol = [c for c in ar.columns if c.startswith("EDM Operation - % of reporting")][0]
    def hrs(v):
        import datetime as dt
        if pd.isna(v):
            return np.nan
        if isinstance(v, dt.timedelta):
            return v.total_seconds() / 3600
        if isinstance(v, dt.datetime):      # Excel durations > 24 h stored as dates from 1899-12-30
            return (v - dt.datetime(1899, 12, 30)).total_seconds() / 3600
        if hasattr(v, "hour"):
            return v.hour + v.minute / 60 + v.second / 3600
        if isinstance(v, pd.Timedelta):
            return v.total_seconds() / 3600
        s = str(v)
        if ":" in s:
            h, m, *sec = s.split(":"); return int(float(h)) + int(m) / 60
        try:
            return float(v) * 24      # Excel day fraction
        except ValueError:
            return np.nan
    ar = ar[ar[pcol].isin(P61)]
    lo, hi = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 1}-01-01")
    for _, r in ar.iterrows():
        e = e2[e2.permitNumber == r[pcol]]
        ours = ((e.stop.clip(lo, hi) - e.start.clip(lo, hi)).dt.total_seconds() / 3600).clip(lower=0).sum()
        rows.append(dict(year=y, permit=r[pcol], site=r.iloc[2], ar_hours=hrs(r[dcol]), ours=ours, edm_op=r[ocol]))
rec = pd.DataFrame(rows).groupby(["year", "permit", "site"], as_index=False).agg(ar_hours=("ar_hours", "sum"), ours=("ours", "max"), edm_op=("edm_op", "min"))
rec["ratio"] = rec.ours / rec.ar_hours.replace(0, np.nan)
for y, g in rec.groupby("year"):
    gg = g.dropna(subset=["ratio"])
    print(f"  {y}: {len(g)} sites matched; total AR {g.ar_hours.sum():,.0f} h vs ours {g.ours.sum():,.0f} h; "
          f"per-site ratio median {gg.ratio.median():.3f}, within ±5%: {(gg.ratio.sub(1).abs() <= .05).mean():.0%}, "
          f"off by >25%: {(gg.ratio.sub(1).abs() > .25).sum()}")
bad = rec[(rec.ratio.sub(1).abs() > .25) | ((rec.ar_hours == 0) & (rec.ours > 5))]
print("  worst mismatches:\n", bad.sort_values("ratio").to_string(index=False))
rec.to_csv(os.path.join(INT, "audit_reconciliation.csv"), index=False)

print("\n" + "=" * 100, "\nB. RAIN GAUGES (EA 15-min)\n")
R = {}
for f in sorted(os.listdir(os.path.join(RAW, "gauges"))):
    if f.startswith("rain_"):
        r = pd.read_csv(os.path.join(RAW, "gauges", f), parse_dates=["dateTime"])
        ref = f[5:-4]
        q = r.quality.value_counts(normalize=True)
        R[ref] = r.set_index("dateTime").value
        print(f"  {ref}: n={len(r)}, missing {r.value.isna().mean():.2%}, suspect {q.get('Suspect', 0):.1%}, "
              f"negative {(r.value < 0).sum()}, max 15-min {r.value.max():.1f} mm, "
              f"suspect mean {r.value[r.quality == 'Suspect'].mean():.3f} vs good {r.value[r.quality == 'Good'].mean():.3f}")
D = pd.DataFrame({k: v.clip(lower=0).resample("D").sum(min_count=80) for k, v in R.items()})
print("\n  annual totals (mm):\n", D.resample("YE").sum().round(0).astype(int).to_string())
C = D.corr()
print("\n  daily correlation with the median of the other gauges:")
for k in D:
    others = D.drop(columns=k).median(axis=1)
    print(f"    {k}: r={D[k].corr(others):.3f}, ratio to others' median {D[k].sum() / others[D[k].notna()].sum():.2f}")

print("\n" + "=" * 100, "\nC. RIVER FLOW (EA daily mean)\n")
for f in sorted(os.listdir(os.path.join(RAW, "gauges"))):
    if f.startswith("flow_"):
        r = pd.read_csv(os.path.join(RAW, "gauges", f), parse_dates=["dateTime"])
        print(f"  {f[5:-4]}: days {len(r)}, first {r.dateTime.min():%Y-%m-%d}, last {r.dateTime.max():%Y-%m-%d %H:%M}, "
              f"time-of-day stamps {sorted(r.dateTime.dt.strftime('%H:%M').unique())[:3]}, quality {r.quality.value_counts().to_dict()}")

print("\n" + "=" * 100, "\nD. TREATED FLOW (Thames Water TDV)\n")
for y in range(2019, 2026):
    t = pd.read_excel(os.path.join(RAW, "tdv", f"tdv{y}.xlsx"), sheet_name=1, na_values="NaN", index_col=0)
    ox = [c for c in t.columns if str(c).upper().startswith("OXFORD")]
    s = pd.to_numeric(t[ox[0]], errors="coerce") if ox else pd.Series(dtype=float)
    print(f"  {y}: {t.shape[1]} works, Oxford column {ox}, Oxford missing {s.isna().mean():.1%}, "
          f"median {s.median():,.0f} m3/d, max {s.max():,.0f} (= {s.max() / 89856:.2f} x ORIC FFT)")
