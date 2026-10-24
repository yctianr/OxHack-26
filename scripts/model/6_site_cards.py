"""Explainable site cards from the bathtub core, in plain units (fit on all data to 2025-09-30, audited layer).
  - flow trigger : Farmoor flow at which the hourly spill chance reaches 50% with an empty rain store
  - rain trigger : mm in the rain store needed for a 50% chance at median winter flow
  - tau          : how long rain keeps counting (h)
  - long-episode share : share of spill-hours in unbroken episodes > 72 h (label-only groundwater signature)
Meaning check against an external label: Thames Water's 2025 EDM annual return tags sites 'GW inundation'.
The model never sees the tag. Writes site_cards.csv."""
import os
import warnings
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from common import FLOW, INT, RAW, episodes, fit_core, load, rain_for, raw_coefs
warnings.filterwarnings("ignore")
inp, lab, si, names = load()
idx = inp.index
W = inp[FLOW].values
t0 = "2025-10-01"
qmed_winter = np.exp(np.nanmedian(W[idx.month.isin([12, 1, 2]) & (idx < t0)]))

ar = pd.read_excel(os.path.join(RAW, "annual_returns", "tw_edm_2025.xlsx"), sheet_name=0, header=5)
ar.columns = [" ".join(str(c).split()) for c in ar.columns]
pcol = [c for c in ar.columns if c.startswith("EA Permit Reference")][0]
tag = ar.groupby(pcol)[[c for c in ar.columns if c.startswith("High Spill Frequency")]].first().astype(str).agg(" | ".join, axis=1)

cards = []
for p, (y, m) in lab.items():
    tr = m & (idx < t0)
    if (y[tr] > 0).sum() < 48:
        continue
    (fit, tau) = fit_core(W, rain_for(inp, si, p), (tr, y[tr]))
    b0, b1, b2 = raw_coefs(fit)
    runs = episodes((y > 0) & m)
    cards.append(dict(permit=p, site=names.get(p, p), tau_h=tau,
                      flow_trigger_m3s=np.exp(-b0 / b1) if b1 > 0 else np.inf,
                      rain_trigger_mm=max(0.0, -(b0 + b1 * np.log(qmed_winter)) / b2) if b2 > 0 else np.inf,
                      long_episode_share=runs[runs > 72].sum() / max(runs.sum(), 1),
                      wet_share=fit[0][1] ** 2 / (fit[0][1] ** 2 + fit[0][2] ** 2),
                      spill_h_per_yr=y[tr].sum() / (tr.sum() / 8766),
                      gw_tag=int("GW inundation" in tag.get(p, ""))))
c = pd.DataFrame(cards).sort_values("spill_h_per_yr", ascending=False)
pd.set_option("display.width", 200)
print(f"median winter Farmoor flow (reference): {qmed_winter:.1f} m3/s")
print(c.drop(columns=["permit"]).round({"flow_trigger_m3s": 1, "rain_trigger_mm": 1, "long_episode_share": 2,
                                        "wet_share": 2, "spill_h_per_yr": 0}).to_string(index=False))
print(f"\nmeaning check vs Thames Water 'GW inundation' tag ({c.gw_tag.sum()} of {len(c)} sites tagged):")
for col, what in (("wet_share", "model wet-ground share (flow vs rain weight)"), ("long_episode_share", "long-episode share (label-only)")):
    print(f"  AUC {roc_auc_score(c.gw_tag, c[col]):.2f}  {what}")
c.to_csv(os.path.join(INT, "site_cards.csv"), index=False)
