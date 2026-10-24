"""Explainability check: do the bathtub's parameters mean what we say they mean?
Wet-ground share = b_wet^2 / (b_wet^2 + b_rain^2) on standardised inputs (fold B fit, clean data, core model W1).
External test: Thames Water's own 2025 EDM annual return tags sites 'GW inundation' (groundwater). The model never
sees this tag. If the share is physical, it should rank tagged sites above the rest."""
import os
import glob
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
INT, RAW = os.path.join(_ROOT, "data", "interim"), os.path.join(_ROOT, "data", "raw")

f = max(glob.glob(os.path.join(INT, "exp_*W1*.pkl")), key=os.path.getmtime)
r = pd.read_pickle(f)
r = r[r.variant.str.startswith("W1")]
r["b_wet"], r["b_rain"] = r.coefs.map(lambda b: b[1]), r.coefs.map(lambda b: b[2])
r["wet_share"] = r.b_wet ** 2 / (r.b_wet ** 2 + r.b_rain ** 2)

ar = pd.read_excel(os.path.join(RAW, "annual_returns", "tw_edm_2025.xlsx"), sheet_name=0, header=5)
ar.columns = [" ".join(str(c).split()) for c in ar.columns]
pcol = [c for c in ar.columns if c.startswith("EA Permit Reference")][0]
hcols = [c for c in ar.columns if c.startswith("High Spill Frequency")]
ar["tag"] = ar[hcols].astype(str).agg(" | ".join, axis=1)
tag = ar.groupby(pcol).tag.first()
for fold, g in r.groupby("fold"):
    g = g.assign(tag=g.site.map(tag).fillna(""), gw=lambda d: d.tag.str.contains("GW inundation", case=False).astype(int))
    print(f"fold {fold}: {len(g)} sites, {g.gw.sum()} tagged 'GW inundation' by Thames Water")
    if 0 < g.gw.sum() < len(g):
        print(f"  AUC of model wet-ground share for the GW tag: {roc_auc_score(g.gw, g.wet_share):.2f}")
        print(f"  median wet-ground share: tagged {g[g.gw == 1].wet_share.median():.2f}, untagged {g[g.gw == 0].wet_share.median():.2f}")
    print(f"  median rain time constant tau: tagged {g[g.gw == 1].tau.median():.0f} h, untagged {g[g.gw == 0].tau.median():.0f} h")
names = pd.read_csv(os.path.join(INT, "sites61.csv")).set_index("permitNumber").locationName
g = r[r.fold == "B"].assign(name=lambda d: d.site.map(names), tag=lambda d: d.site.map(tag).fillna("").str.slice(0, 40))
print("\nper-site card (fold B):")
print(g.sort_values("wet_share", ascending=False)[["name", "wet_share", "tau", "auc", "bss", "tag"]].round(2).to_string(index=False))

# A label-only signature, no model: share of a site's spill-hours that fall in episodes longer than 72 h
# (episodes = spills merged across gaps < 6 h). Groundwater-fed systems should spill in long unbroken episodes.
lab = pd.read_pickle(os.path.join(INT, "labels_clean.pkl"))
sig = {}
for p, (y, m) in lab.items():
    on = (y > 0) & m
    runs, cur, gap = [], 0, 0
    for v in on:
        if v:
            cur += 1 + gap if cur else 1; gap = 0
        elif cur:
            gap += 1
            if gap > 6:
                runs.append(cur); cur, gap = 0, 0
    if cur:
        runs.append(cur)
    runs = np.array(runs)
    sig[p] = runs[runs > 72].sum() / runs.sum() if runs.sum() > 100 else np.nan
s = pd.Series(sig, name="long_share").dropna().to_frame()
s["gw"] = s.index.map(tag).fillna("").str.contains("GW inundation", case=False).astype(int)
s = s.join(r[r.fold == "B"].set_index("site").wet_share)
print(f"\nlabel-only signature (share of spill-hours in > 72 h episodes): {len(s)} sites, {s.gw.sum()} GW-tagged")
print(f"  AUC for the GW tag: {roc_auc_score(s.gw, s.long_share):.2f}; median tagged {s[s.gw == 1].long_share.median():.2f} vs untagged {s[s.gw == 0].long_share.median():.2f}")
ok = s.dropna()
print(f"  rank correlation with the model's wet-ground share: {ok.long_share.corr(ok.wet_share, method='spearman'):.2f}")
