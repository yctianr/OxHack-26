"""River water quality for the website's river page (web/river.html). Writes web/data/quality.json.

E. coli and ammonia while a spill passes, every 100 m of river downstream of each sewage works, for every day of the
website (the held-out test year and the physics model's 7-day forecast). The page does the arithmetic per day:

    C(segment, day) = background + sum over works upstream of  c0 · r / (Q + r) · exp(-k · t)

  r   the works' spill rate (m3/s) on a spill day: its typical rate in the physics water balance (total modelled spill
      volume / modelled spill-hours, fold B). A day is a spill day if the monitor recorded one (past days), or if the
      physics model gives it a 50%+ chance (forecast days, and past days with no usable monitor record).
  Q   river flow at the segment that day (m3/s): on a gauged river, its nearest EA gauge; elsewhere the gauges' median
      runoff per km2 that day times the segment's catchment area, estimated from the river length upstream.
  t   travel time from the works (h) at a constant velocity; k first-order decay (E. coli faster in summer); c0 source.
Fully mixed across the river, steady over the spill. Parameters and their sources are in PARAMS below.
Network and pumping-station overflows have no treated-flow data, so no spill rate: they are shown but add nothing.
Run from the repo root after data.py and physics.py (needs data/interim/web_links.pkl from rivers.py)."""
import json
import math
import pickle
from collections import defaultdict, deque
import numpy as np
import pandas as pd
from pyproj import Transformer

PARAMS = dict(
    ecoli_source=1.5e6,      # cfu/100 mL in storm overflow discharge
    ammonia_source=4.0,      # mg/L NH4-N in storm overflow discharge (derived, see SOURCES)
    ecoli_k_winter=0.5,      # per day, first-order die-off, Oct-Mar
    ecoli_k_summer=1.1,      # per day, Apr-Sep
    ammonia_k=0.3,           # per day, nitrification
    ecoli_bg=100.0,          # cfu/100 mL, river background without spills
    ammonia_bg=0.04,         # mg/L N, river background
    velocity=0.5,            # m/s, travel speed at the high flows when spills happen
    swim_ok=235.0, swim_bad=235.0,        # cfu/100 mL: dangerous from 235 (one level: no "take care" band)
    fish_ok=0.5, fish_bad=0.5,            # mg/L N total ammonia: harmful from 0.5
    max_km=40.0, step_m=100.0, min_flow=0.005)
SOURCES = {
    "ecoli_source": "Passerat et al. 2011, Water Research 45:893 (Seine CSO): 'The CSO contained 1.5 x 10^6 E. coli per 100 mL on average'; range 4.6-7.3 log10 (Wang et al. 2026). https://pubmed.ncbi.nlm.nih.gov/20934197/",
    "ammonia_source": "Derived: crude sewage ~39 mg N/L (GOV.UK, septic tank and package treatment plants: typical concentrations) diluted ~10x by runoff in storm overflows (Passerat et al. 2011: 89% of CSO discharge was surface runoff). No measured UK value found.",
    "ecoli_k": "Servais et al. 2007, HESS 11:1581: 45e-3 per hour at 20 C, temperature dependent; Seine 0.19-0.81 per day. Winter 0.5, summer 1.1 per day. https://hess.copernicus.org/articles/11/1581/2007/",
    "ammonia_k": "Judgement within Pauer & Auer 2009 (nitrification velocity 0.14-0.97 m/day, i.e. ~0.1-1 per day for 1 m depth). https://digitalcommons.mtu.edu/michigantech-p/6309",
    "ammonia_bg": "Bowes et al. 2018, ESSD 10:1637, Table 3: Cherwell 0.031, Thames at Swinford 0.039 mg N/L. https://essd.copernicus.org/articles/10/1637/2018/",
    "ecoli_bg": "Servais et al. 2007: around 100 per 100 mL in streams draining cultivated or wooded land (around 1000 for pasture). https://hess.copernicus.org/articles/11/1581/2007/",
    "swim": "Set by the team: dangerous from 235 E. coli per 100 mL, the US EPA 1986 single-sample maximum for designated beach areas (Ambient Water Quality Criteria for Bacteria). For comparison, England's inland bathing standards are Excellent 500, Good 1000 (95th percentile).",
    "fish": "Set by the team: harmful from 0.5 mg N/L total ammonia, between the WFD High (0.3) and Good (0.6) boundaries for lowland high-alkalinity rivers (WFD Standards Directions 2015, Sch 3 Table 7).",
    "velocity": "EA time-of-travel database (Guymer, Warwick): most traces 0.05-0.5 m/s, rising with discharge; spills happen at high flow. https://www2.warwick.ac.uk/fac/sci/eng/research/grouplist/water/events/britcouncildyetracing/2_mixing_in_rivers.pdf",
}
P = PARAMS
t2ll = Transformer.from_crs(27700, 4326, always_xy=True)

O = json.load(open("web/data/outfalls.json"))
PH = json.load(open("web/data/physics.json"))
dates, nobs = PH["dates"], len(O["dates"])
links = [l for l in pickle.load(open("data/interim/web_links.pkl", "rb")) if l["form"] == "inlandRiver"]
for k, l in enumerate(links):
    l["k"] = k

# ---- network: downstream links (bridging small gaps, as data.py does) and river length upstream ----
by_start = defaultdict(list)
for l in links:
    by_start[l["sn"]].append(l["k"])
down = {l["k"]: list(by_start[l["en"]]) for l in links}
starts = np.array([l["pts"][0] for l in links])
for l in links:
    if not down[l["k"]]:
        ex, ey = l["pts"][-1]
        d = np.hypot(starts[:, 0] - ex, starts[:, 1] - ey)
        for j in np.argsort(d)[:3]:
            if d[j] < 250 and j != l["k"]:
                down[l["k"]] = [int(j)]
                break
up = defaultdict(list)
for a, bs in down.items():
    for b in bs:
        up[b].append(a)
uplen = {}
for l in links:
    seen, q, tot = {l["k"]}, deque([l["k"]]), 0.0
    while q:
        x = q.popleft()
        tot += links[x]["len"]
        for y in up[x]:
            if y not in seen:
                seen.add(y)
                q.append(y)
    uplen[l["k"]] = tot / 1000

# ---- 100 m segments ----
seg_xy, seg_link, seg_off, link_segs = [], [], [], defaultdict(list)
for l in links:
    pts = np.array(l["pts"], dtype=float)
    cum = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    n = max(1, int(math.ceil(cum[-1] / P["step_m"])))
    edges = np.linspace(0, cum[-1], n + 1)
    ex, ey = np.interp(edges, cum, pts[:, 0]), np.interp(edges, cum, pts[:, 1])
    lon, lat = t2ll.transform(ex, ey)
    for i in range(n):
        link_segs[l["k"]].append(len(seg_xy))
        seg_xy.append([round(lon[i], 5), round(lat[i], 5), round(lon[i + 1], 5), round(lat[i + 1], 5)])
        seg_link.append(l["k"])
        seg_off.append((edges[i] + edges[i + 1]) / 2)
names = sorted({l["name"] or "" for l in links})
seg_name = [names.index(links[k]["name"] or "") for k in seg_link]

# ---- river flow: gauges, and runoff per km2 for ungauged streams ----
st = {(i.get("stationReference") or i["notation"].split("_")[-1]): i for i in json.load(open("data/interim/st_waterFlow.json"))["items"]}
GAUGES = {"1100TH": "River Thames", "1800TH": "River Thames", "1490TH": "River Cherwell", "1489TH": "River Cherwell",
          "1290TH": "River Evenlode", "1980TH": "River Thame", "1790TH": "River Ock", "1289TH": "River Glyme", "1995TH": None}
didx = pd.DatetimeIndex(dates)
flow, area, gxy = {}, {}, {}
ll2b = Transformer.from_crs(4326, 27700, always_xy=True)
for g in GAUGES:
    f = pd.read_csv(f"data/raw/gauges/flow_{g}.csv", parse_dates=["dateTime"])
    s = f.set_index(f.dateTime.dt.normalize()).value.astype(float)
    s = s[~s.index.duplicated()]
    flow[g] = s.reindex(didx).ffill().bfill().values               # held at the last reading on days without one
    area[g] = float(st[g]["catchmentArea"])
    gxy[g] = ll2b.transform(st[g]["long"], st[g]["lat"])
qspec = np.median(np.stack([flow[g] / area[g] for g in GAUGES]), axis=0)   # m3/s per km2, each day
mid = np.array([[np.mean(l["pts"], axis=0)[0], np.mean(l["pts"], axis=0)[1]] for l in links])


def nearest_link(x, y, name=None):
    cand = [l["k"] for l in links if name is None or l["name"] == name]
    d = [np.min(np.hypot(*(np.array(links[k]["pts"]) - [x, y]).T)) for k in cand]
    return cand[int(np.argmin(d))], float(np.min(d))


# catchment area per km of upstream river, from the small gauged catchments wholly inside the map
dens = []
for g in ("1289TH", "1995TH", "1790TH"):
    k, _ = nearest_link(*gxy[g], GAUGES[g])
    dens.append(area[g] / max(uplen[k], 1))
density = float(np.median(dens))
gauge_list = list(GAUGES)
link_ref = {}
for l in links:
    on = [g for g, rv in GAUGES.items() if rv and rv == l["name"]]
    if on:   # gauged river: its nearest gauge
        link_ref[l["k"]] = gauge_list.index(min(on, key=lambda g: math.hypot(mid[l["k"]][0] - gxy[g][0], mid[l["k"]][1] - gxy[g][1])))
    else:
        link_ref[l["k"]] = -1
seg_ref = [link_ref[k] for k in seg_link]
seg_area = [round(uplen[k] * density, 2) for k in seg_link]

# ---- each works: where it enters the river, and the travel time to every segment downstream ----
sites = pd.read_csv("data/interim/sites61.csv").set_index("permitNumber")
D = pd.read_pickle("data/interim/wb_predictions.pkl")
B = D[D.fold == "B"]
cap = pd.read_csv("data/interim/wb_params.csv").query("fold == 'B'").set_index("permit").cap_m3d
rate = (B.groupby("site").wb1_vol_m3.sum() / B.groupby("site").wb1_hours.sum() / 3600).replace([np.inf], np.nan)
ratio = float((rate / (cap / 86400)).median())
works = []
for s in O["sites"]:
    w = PH["works"].get(s["id"])
    x, y = sites.loc[s["id"], ["x", "y"]]
    rec = dict(id=s["id"], name=s["name"], lon=s["lon"], lat=s["lat"], type=s["type"], water=s["water"])
    # where it enters the river: the closest point on the nearest river link (for the dotted connector on the map)
    ke, _ = nearest_link(x, y)
    pe = np.array(links[ke]["pts"], dtype=float)
    a_, b_ = pe[:-1], pe[1:]
    ab = b_ - a_
    tq = np.clip(((x - a_[:, 0]) * ab[:, 0] + (y - a_[:, 1]) * ab[:, 1]) / np.maximum((ab ** 2).sum(1), 1e-9), 0, 1)
    proj = a_ + tq[:, None] * ab
    i_ = int(np.argmin(np.hypot(proj[:, 0] - x, proj[:, 1] - y)))
    elon, elat = t2ll.transform(*proj[i_])
    rec["entry"] = [round(elon, 5), round(elat, 5)]
    if w:
        r = rate.get(s["id"])
        r = float(r) if r is not None and np.isfinite(r) and r > 0 else ratio * cap[s["id"]] / 86400
        obs, hrs = s.get("obs") or [], s.get("hours") or []
        spill, hours, src = [], [], []
        for d in range(len(dates)):
            o = obs[d] if d < len(obs) else None
            if d < nobs and o is not None:
                spill.append(int(o > 0)); hours.append(round(float(hrs[d] or 0), 1)); src.append(0)   # monitor
            else:
                spill.append(int(w["p"][d] >= 0.5)); hours.append(round(float(w["h"][d]), 1)); src.append(1)  # model
        k0, _ = nearest_link(x, y)
        pts = np.array(links[k0]["pts"])
        cum = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
        snap = cum[int(np.argmin(np.hypot(*(pts - [x, y]).T)))]
        seg, tt = [], []
        best = {}
        q = deque([(k0, -snap)])                                      # (link, distance at the link's start)
        while q:
            k, d0 = q.popleft()
            if k in best and best[k] <= d0:
                continue
            best[k] = d0
            for j in link_segs[k]:
                dist = d0 + seg_off[j]
                if 0 <= dist <= P["max_km"] * 1000:
                    seg.append(j); tt.append(round(dist / P["velocity"] / 3600, 1))
            if d0 + links[k]["len"] <= P["max_km"] * 1000:
                for nk in down[k]:
                    q.append((nk, d0 + links[k]["len"]))
        o_ = np.argsort(tt)
        rec.update(rate=round(r, 4), spill=spill, hours=hours, src=src, p=w["p"], vol=w["v"],
                   seg=[int(seg[i]) for i in o_], t=[tt[i] for i in o_])
    works.append(rec)

out = dict(dates=dates, nobs=nobs, issued=(PH.get("forecast") or {}).get("issued"), params=P, sources=SOURCES,
           gauges=gauge_list, flow=[[round(float(v), 3) for v in flow[g]] for g in gauge_list],
           qspec=[round(float(v), 6) for v in qspec], names=names,
           seg=dict(xy=seg_xy, name=seg_name, ref=seg_ref, area=seg_area), works=works)
json.dump(out, open("web/data/quality.json", "w"), separators=(",", ":"))
n_aff = len({j for w in works for j in w.get("seg", [])})
print(f"{len(seg_xy)} segments of 100 m; {n_aff} downstream of a works; {sum('seg' in w for w in works)} works with a spill rate; "
      f"catchment density {density:.2f} km2 per river km; typical spill rate / capacity {ratio:.2f}")
