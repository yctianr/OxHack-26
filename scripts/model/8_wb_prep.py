"""Water-balance inputs: match each spill-monitored works to its daily treated flow (TDV) and its ORIC capacity row.

Only overflows at a sewage works with a TDV column are kept; network overflows (no flow measured) are dropped.
Writes data/interim/wb_works.csv (one row per works: capacity, population, infiltration allowance) and
data/interim/wb_tdv.pkl (daily treated volume, m3/day, one column per permit). Also audits each works' flow
data against its spill record (the verdict column) and fetches daily evaporation from Open-Meteo if missing."""
import os
import re
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from common import INT, RAW, TZ, load, rain_for

# spill-site name -> TDV / ORIC name, where normalising alone doesn't match
TDV_NAME = {"CLANFIELD": "CLANFIELD MARSH", "CHARLTON ON OTMOOR": "CHARLTON OTMOOR",
            "MIDDLETON STONEY": "MIDDLETON STONY", "WESTON ON THE GREEN STW": "WESTON ON THE GREEN"}
ORIC_NAME = {"BECKLEY": "CONSTABLE S PIECE BECKLEY", "WESTON ON THE GREEN STW": "WESTON ON THE GREEN"}
NOT_WORKS = {"TEMP.2220", "CSSC.2317"}   # Weston-on-the-Green network CSO; Stanford-in-the-Vale (no unambiguous TDV)


def norm(s):
    s = re.sub(r"\(OXON\)|\*+|\bSTW\b|\(\d\)|\b\d\b|STW\d", " ", str(s).upper())
    return " ".join(re.sub(r"[^A-Z ]", " ", s).split())


ET0 = os.path.join(RAW, "openmeteo", "et0_oxford_daily.csv")
if not os.path.exists(ET0):   # daily FAO reference evaporation at Oxford, for the soil-moisture store in wb.py
    import urllib.request
    url = ("https://archive-api.open-meteo.com/v1/archive?latitude=51.75&longitude=-1.26&start_date=2022-01-01"
           "&end_date=2026-10-22&daily=et0_fao_evapotranspiration,precipitation_sum&timezone=Europe%2FLondon&format=csv")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    open(ET0, "wb").write(urllib.request.urlopen(req, timeout=60).read())

sites = pd.read_csv(os.path.join(INT, "sites61.csv"))

# ---- TDV: one series per works, names normalised across years (Abingdon has two outlets: summed) ----
tdv = {}
for yr in range(2019, 2026):
    d = pd.read_excel(os.path.join(RAW, "tdv", f"tdv{yr}.xlsx"), sheet_name=1, index_col=0, na_values="NaN")
    d.index = pd.to_datetime(d.index, errors="coerce")
    d = d[d.index.notna()].apply(pd.to_numeric, errors="coerce")
    for key, cols in d.T.groupby(lambda c: norm(c)).groups.items():
        v = d[list(cols)].sum(axis=1, min_count=len(cols))
        tdv.setdefault(key, []).append(v)
tdv = {k: pd.concat(v).sort_index() for k, v in tdv.items()}

# ---- ORIC "Required capacities": installed FFT, max infiltration, per-capita flow, population (all l/s) ----
o = pd.read_excel(os.path.join(RAW, "oric_fft.xlsx"), sheet_name="Required capacities", header=None).iloc[5:]
o = o[pd.to_numeric(o[3], errors="coerce").notna()]
oric = pd.DataFrame({"key": o[1].map(norm), "fft_ls": o[3].astype(float), "imax_ls": pd.to_numeric(o[6], errors="coerce"),
                     "g_ls": pd.to_numeric(o[7], errors="coerce"), "pe": pd.to_numeric(o[8], errors="coerce"),
                     "e_ls": pd.to_numeric(o[9], errors="coerce"), "req_ls": pd.to_numeric(o[10], errors="coerce")})
oric = oric.drop_duplicates("key").set_index("key")

rows, series = [], {}
for _, s in sites.iterrows():
    n = norm(s.locationName)
    key, okey = TDV_NAME.get(n, n), ORIC_NAME.get(n, n)
    if s.permitNumber in NOT_WORKS or key not in tdv or okey not in oric.index:
        continue
    v = tdv[key]
    v = v[~v.index.duplicated()]
    v = v.where((v > 0) & (v < 10 * v.median()))           # zeros and impossible spikes (Carterton: 28 million m3)
    series[s.permitNumber] = v
    r = oric.loc[okey]
    rows.append(dict(permit=s.permitNumber, site=s.locationName, key=key, fft_ls=r.fft_ls, imax_ls=r.imax_ls,
                     foul_ls=r.pe * r.g_ls + r.e_ls, pe=r.pe, req_ls=r.req_ls,
                     tdv_days=int(v.loc["2022-04-01":].notna().sum()),
                     tdv_p99_m3d=v.loc["2022-04-01":].quantile(.99),
                     tdv_p99_over_fft=v.loc["2022-04-01":].quantile(.99) / (r.fft_ls * 86.4) if r.fft_ls > 0 else np.nan))
W = pd.DataFrame(rows)
T = pd.DataFrame(series).loc["2019-01-01":]

# ---- audit: is each works' treated flow a real meter that sees the same water as its spill monitor? ----
# Spill labels are used here only to audit the data, never to fit the water balance.
inp, lab, si, _ = load()
loc = inp.index.tz_convert(TZ).tz_localize(None).normalize()
Ta = T.loc["2022-04-01":"2025-12-31"]
audit = []
for _, w in W.iterrows():
    r = pd.Series(rain_for(inp, si, w.permit), index=loc).groupby(level=0).sum()
    y, m = lab[w.permit]
    sh = pd.Series(np.where(m, y, np.nan), index=loc).groupby(level=0).sum(min_count=1)
    d = pd.DataFrame({"q": Ta[w.permit], "r3": r.rolling(3).sum(), "r7": r.rolling(7).sum(), "sh": sh}).dropna(subset=["q"])
    dry = d[d.r7 < 2]
    cap = w.fft_ls * 86.4 if w.fft_ls > 0 else w.tdv_p99_m3d
    sp = d[d.sh >= 12].q                                           # days spilling >= 12 h
    a = dict(coverage=len(d) / len(Ta), rain_rho=spearmanr(d.q, d.r3, nan_policy="omit")[0],
             winter_over_summer_dry=dry[dry.index.month.isin([1, 2, 3])].q.median() / dry[dry.index.month.isin([7, 8, 9])].q.median(),
             n_spill_days=len(sp), spill_flow_over_fft=sp.median() / cap if len(sp) >= 10 else np.nan,
             spill_days_below_80pct=(sp < .8 * cap).mean() if len(sp) >= 10 else np.nan)
    if a["coverage"] < .5:
        v = "drop: too little flow data"
    elif a["spill_days_below_80pct"] > .3:
        v = "check: spills while treating well below capacity"
    elif w.fft_ls == 0:
        v = "ok: no published capacity (fitted from flow)"
    elif a["rain_rho"] < .2:
        v = "ok: groundwater-dominated (flow tracks groundwater, not rain)"
    else:
        v = "good"
    audit.append(dict(a, verdict=v))
W = pd.concat([W, pd.DataFrame(audit)], axis=1)
W.to_csv(os.path.join(INT, "wb_works.csv"), index=False)
T.to_pickle(os.path.join(INT, "wb_tdv.pkl"))
dropped = sites[~sites.permitNumber.isin(W.permit)].locationName.tolist()
pd.set_option("display.width", 220)
print(W[["site", "fft_ls", "coverage", "rain_rho", "winter_over_summer_dry", "n_spill_days", "spill_flow_over_fft",
         "spill_days_below_80pct", "verdict"]].sort_values(["verdict", "site"]).round(2).to_string(index=False))
print(f"\n{W.verdict.value_counts().to_string()}")
print(f"\n{len(W)} works matched; {len(dropped)} sites have no treated-flow data (network overflows or no match): {dropped}")
