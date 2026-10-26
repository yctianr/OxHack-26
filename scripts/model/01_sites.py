"""Site registry: the 61 overflows within 25 km of Oxford (lat/lon included) and the EA station lists.
Run after `python scripts/fetch.py alerts && python scripts/fetch.py events`."""
import math
import os
import urllib.request
import numpy as np
import pandas as pd
from common import INT, RAW

os.makedirs(INT, exist_ok=True)
for prop in ("rainfall", "waterFlow"):
    url = f"https://environment.data.gov.uk/hydrology/id/stations.json?observedProperty={prop}&lat=51.76&long=-1.26&dist=40&_limit=200"
    urllib.request.urlretrieve(url, os.path.join(INT, f"st_{prop}.json"))


def osgb_to_wgs(E, N):
    """OSGB36 grid -> lat/lon (Ordnance Survey inverse projection) plus a rough datum shift; ~10 m accuracy."""
    a, b = 6377563.396, 6356256.909; F0 = 0.9996012717; lat0, lon0 = math.radians(49), math.radians(-2); N0, E0 = -100000, 400000
    e2 = 1 - (b * b) / (a * a); n = (a - b) / (a + b); lat = lat0; M = 0
    while N - N0 - M >= 0.00001:
        lat = (N - N0 - M) / (a * F0) + lat
        Ma = (1 + n + 1.25 * n ** 2 + 1.25 * n ** 3) * (lat - lat0)
        Mb = (3 * n + 3 * n ** 2 + 21 / 8 * n ** 3) * math.sin(lat - lat0) * math.cos(lat + lat0)
        Mc = (15 / 8 * n ** 2 + 15 / 8 * n ** 3) * math.sin(2 * (lat - lat0)) * math.cos(2 * (lat + lat0))
        Md = 35 / 24 * n ** 3 * math.sin(3 * (lat - lat0)) * math.cos(3 * (lat + lat0))
        M = b * F0 * (Ma - Mb + Mc - Md)
    nu = a * F0 / math.sqrt(1 - e2 * math.sin(lat) ** 2); rho = a * F0 * (1 - e2) / (1 - e2 * math.sin(lat) ** 2) ** 1.5
    eta2 = nu / rho - 1; t = math.tan(lat); sec = 1 / math.cos(lat); dE = E - E0
    VII = t / (2 * rho * nu); VIII = t / (24 * rho * nu ** 3) * (5 + 3 * t * t + eta2 - 9 * t * t * eta2)
    IX = t / (720 * rho * nu ** 5) * (61 + 90 * t * t + 45 * t ** 4)
    X = sec / nu; XI = sec / (6 * nu ** 3) * (nu / rho + 2 * t * t); XII = sec / (120 * nu ** 5) * (5 + 28 * t * t + 24 * t ** 4)
    XIIA = sec / (5040 * nu ** 7) * (61 + 662 * t * t + 1320 * t ** 4 + 720 * t ** 6)
    la = lat - VII * dE ** 2 + VIII * dE ** 4 - IX * dE ** 6
    lo = lon0 + X * dE - XI * dE ** 3 + XII * dE ** 5 - XIIA * dE ** 7
    return math.degrees(la) + 0.0005, math.degrees(lo) - 0.0015


ev = pd.read_csv(os.path.join(RAW, "events.csv"))
s = ev.dropna(subset=["x"]).groupby(["permitNumber", "locationName"])[["x", "y"]].first().reset_index()
s = s[np.hypot(s.x - 452000, s.y - 206000) < 25000].copy()
s[["lat", "lon"]] = [osgb_to_wgs(e, n) for e, n in zip(s.x, s.y)]
s.to_csv(os.path.join(INT, "sites61.csv"), index=False)
print(len(s), "sites ->", os.path.join(INT, "sites61.csv"))
