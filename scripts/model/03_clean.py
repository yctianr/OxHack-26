"""Clean data layer (fixes from 02_audit.py). Writes inputs_clean.pkl, labels_clean.pkl, site_quality.csv, site_inputs.csv.

Labels  - fractional hourly spill (exact minutes, no floor/ceil inflation); DST-ambiguous times kept (read as GMT);
          monitoring starts at the site's first alert of any kind; site-years whose spill-hours disagree with the
          Thames Water EDM annual return by > 25% (or annual return > 5 h but feed empty) are masked as unreliable.
Rain    - 15-min -> hourly; readings flagged Suspect are treated as missing; gauge-days that disagree grossly with the other gauges' median are set missing
          (under-catch: < 25% of median when median > 4 mm; spurious: > 4x median and > 20 mm); missing hours are
          infilled from the other gauges, scaled by each gauge's long-run ratio. Missing rain is never read as zero.
Flow    - EA daily means cover a 09:00-09:00 (GMT) water day stamped at its start. A value becomes usable only
          FLOW_LAG_H hours after its water day ends, so no hour ever sees flow from its own future."""
import glob
import json
import os
import sys
import numpy as np
import pandas as pd
from common import DATA_END, INT, RAW, TZ
FLOW_LAG_H = int(sys.argv[1]) if len(sys.argv) > 1 else 12
idx = pd.date_range("2022-04-01", DATA_END, freq="1h", tz="UTC")
sites = pd.read_csv(os.path.join(INT, "sites61.csv"))

# ---------------- rain ----------------
H = {}
for f in sorted(glob.glob(os.path.join(RAW, "gauges", "rain_*.csv"))):
    r = pd.read_csv(f, parse_dates=["dateTime"])
    r.loc[r.quality.isin(["Suspect", "Missing"]), "value"] = np.nan        # Suspect readings under-catch at some gauges
    s = r.set_index(pd.to_datetime(r.dateTime, utc=True)).value.where(lambda v: v >= 0)
    H[os.path.basename(f)[5:-4]] = s.resample("1h").sum(min_count=4).reindex(idx)   # need all four 15-min readings
H = pd.DataFrame(H)
Dd = H.resample("D").sum(min_count=24)
qc = pd.DataFrame(False, Dd.index, Dd.columns)
for g in Dd:
    med = Dd.drop(columns=g).median(axis=1)
    qc[g] = ((Dd[g] < 0.25 * med) & (med > 4)) | ((Dd[g] > 4 * med) & (Dd[g] > 20))
bad_h = qc.reindex(H.index.floor("D")).set_axis(H.index)
Hq = H.mask(bad_h)
ratio = {g: Hq[g].sum() / Hq.drop(columns=g).median(axis=1)[Hq[g].notna()].sum() for g in Hq}
infill = Hq.copy()
for g in Hq:
    est = Hq.drop(columns=g).median(axis=1) * ratio[g]
    infill[g] = Hq[g].fillna(est)
print("rain QC: gauge-days flagged", qc.sum().to_dict())
print("rain: hours infilled", (Hq.isna() & infill.notna()).sum().to_dict(), "| still missing", infill.isna().sum().sum())

# ---------------- flow ----------------
inp = pd.DataFrame(index=idx)
for g in infill:
    inp[f"rain_{g}"] = infill[g]
for f in sorted(glob.glob(os.path.join(RAW, "gauges", "flow_*.csv"))):
    ref = os.path.basename(f)[5:-4]
    r = pd.read_csv(f, parse_dates=["dateTime"])
    r = r[r.quality != "Missing"].dropna(subset=["value"])
    start = pd.to_datetime(r.dateTime).dt.tz_localize("UTC")            # 09:00 GMT, start of the water day
    usable = start + pd.Timedelta(hours=24 + FLOW_LAG_H)                  # end of water day + publication lag
    s = pd.Series(np.log(r.value.clip(lower=1e-3)).values, index=usable).sort_index()
    s = s[~s.index.duplicated()]
    inp[f"lflow_{ref}"] = s.reindex(idx, method="ffill", tolerance=pd.Timedelta("8D"))
print(f"flow: usable {FLOW_LAG_H} h after the water day ends; missing share",
      inp.filter(like="lflow_").isna().mean().round(3).to_dict())

# ---------------- labels ----------------
def to_utc(s):
    t = pd.to_datetime(s)
    return t.dt.tz_localize(TZ, ambiguous=np.zeros(len(t), bool), nonexistent="shift_forward").dt.tz_convert("UTC")


al = pd.read_csv(os.path.join(RAW, "thames_alerts.csv"))
first_alert = al.groupby("permitNumber").datetime.min()
ev = pd.read_csv(os.path.join(RAW, "events.csv")).dropna(subset=["stop"])
off = pd.read_csv(os.path.join(RAW, "offline.csv")).dropna()
rec = pd.read_csv(os.path.join(INT, "audit_reconciliation.csv"))
bad_years = rec[((rec.ratio - 1).abs() > 0.25) | ((rec.ours == 0) & (rec.ar_hours > 5))]
t_h = idx.asi8 // 3_600_000_000_000                                      # hours since epoch
labels, quality = {}, []
for p in sites.permitNumber:
    e = ev[ev.permitNumber == p]
    y = np.zeros(len(idx), np.float32)
    for s_, t_ in zip(to_utc(e.start), to_utc(e.stop)):
        a, b = s_.value / 3.6e12, t_.value / 3.6e12                      # fractional hours since epoch
        for h in range(int(np.floor(a)), int(np.ceil(b))):
            i = h - t_h[0]
            if 0 <= i < len(idx):
                y[i] += max(0.0, min(b, h + 1) - max(a, h))
    y = np.clip(y, 0, 1)
    m = np.ones(len(idx), bool)
    for s_, t_ in zip(to_utc(off[off.permitNumber == p].start), to_utc(off[off.permitNumber == p].stop)):
        m[idx.searchsorted(s_.floor("h")):idx.searchsorted(t_.ceil("h"))] = False
    if p in first_alert:
        m &= idx >= to_utc(pd.Series([first_alert[p]])).iloc[0].floor("h")
    else:
        m[:] = False
    yrs = bad_years[bad_years.permit == p].year.tolist()
    for yr in yrs:
        m &= ~((idx >= pd.Timestamp(f"{yr}-01-01", tz=TZ)) & (idx < pd.Timestamp(f"{yr + 1}-01-01", tz=TZ)))
    labels[p] = (y, m)
    quality.append(dict(permit=p, name=sites.set_index("permitNumber").locationName[p], masked_years=yrs,
                        monitored_share=round(m.mean(), 3), spill_hours=round(float(y[m].sum()), 1)))
q = pd.DataFrame(quality)
print(f"labels: total spill-hours {sum(float(v[0].sum()) for v in labels.values()):,.0f} (exact); "
      f"site-years masked as unreliable: {sum(len(x) for x in q.masked_years)}")
print(q[q.masked_years.str.len() > 0].to_string(index=False))

inp.to_pickle(os.path.join(INT, "inputs_clean.pkl"))
pd.to_pickle(labels, os.path.join(INT, "labels_clean.pkl"))
q.to_csv(os.path.join(INT, "site_quality.csv"), index=False)

# ---------------- rain gauge assignment: the two nearest audited gauges per site ----------------
xy = {}
for s_ in json.load(open(os.path.join(INT, "st_rainfall.json")))["items"]:
    xy[s_.get("stationReference") or s_.get("notation")] = (s_.get("easting"), s_.get("northing"))
rows = []
for _, s_ in sites.iterrows():
    d = sorted((np.hypot(xy[g][0] - s_.x, xy[g][1] - s_.y), g) for g in infill.columns if g in xy)
    rows.append(dict(permit=s_.permitNumber, name=s_.locationName, rain1=d[0][1], d1=d[0][0], rain2=d[1][1], d2=d[1][0]))
pd.DataFrame(rows).to_csv(os.path.join(INT, "site_inputs.csv"), index=False)
