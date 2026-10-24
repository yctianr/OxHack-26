"""Fetch 15-min rain and daily mean flow for EA gauges around Oxford into data/raw/gauges/."""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from common import RAW

OUT = os.path.join(RAW, "gauges")
H = "https://environment.data.gov.uk/hydrology"
RAIN = ["256230TP", "254336TP", "263541TP", "261021TP", "259110TP", "264254TP", "253861TP", "254829TP", "261923TP", "274178TP"]
FLOW = ["1490TH", "1489TH", "8afc6e20-b0bd-4b79-bf65-345dac8cafee_1290TH", "1100TH", "1980TH", "1790TH", "1800TH", "1289TH", "1995TH", "1090_w1TH"]


def get(url):
    for k in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            print("retry", e, file=sys.stderr); time.sleep(3 * (k + 1))
    raise RuntimeError(url)


def measure(ref, prop, period, stat=None):
    q = {"station": ref} if "-" in ref else {"station.stationReference": ref, "observedProperty": prop}
    ids = [i["@id"].rsplit("/", 1)[-1] for i in get(f"{H}/id/measures.json?{urllib.parse.urlencode(q)}")["items"]]
    want = "-flow-m-86400-" if prop == "waterFlow" else "-t-900-"
    ids = [i for i in ids if want in i]
    return ids[0] if ids else None


def readings(mid, since="2022-01-01"):
    rows, off = [], 0
    while True:
        d = get(f"{H}/id/measures/{mid}/readings.json?min-date={since}&_limit=200000&_offset={off}")["items"]
        rows += [(i["dateTime"], i.get("value"), i.get("quality")) for i in d]
        if len(d) < 200000:
            return rows
        off += 200000


os.makedirs(OUT, exist_ok=True)
for kind, refs, prop, period, stat in [("rain", RAIN, "rainfall", "15min", None), ("flow", FLOW, "waterFlow", "daily", "mean")]:
    for ref in refs:
        mid = measure(ref, prop, period, stat)
        if not mid:
            print(f"{kind} {ref}: no measure"); continue
        rows = readings(mid)
        with open(f"{OUT}/{kind}_{ref.rsplit('_', 1)[-1] if '-' in ref else ref}.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["dateTime", "value", "quality"]); w.writerows(rows)
        print(f"{kind} {ref}: {mid} {len(rows)} rows, {rows[0][0] if rows else '-'} -> {rows[-1][0] if rows else '-'}")
