"""Fetch Spillcast's raw data into data/raw/ (stdlib only, no API keys).

Usage:
  python scripts/fetch.py alerts     # all Thames Water spill-monitor start/stop alerts (~154 pages, ~10 min)
  python scripts/fetch.py events     # pair alerts into spills (events.csv) and monitor outages (offline.csv)
  python scripts/fetch.py status     # current status of all ~573 Thames Water monitors (locations)
  python scripts/fetch.py gauges     # 15-min rain and daily mean flow at 10 + 10 EA gauges around Oxford
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")
TW = "https://api.thameswater.co.uk/opendata/v2/discharge"
HYDRO = "https://environment.data.gov.uk/hydrology"
RAIN = ["256230TP", "254336TP", "263541TP", "261021TP", "259110TP", "264254TP", "253861TP", "254829TP", "261923TP", "274178TP"]
FLOW = ["1490TH", "1489TH", "8afc6e20-b0bd-4b79-bf65-345dac8cafee_1290TH", "1100TH", "1980TH", "1790TH", "1800TH", "1289TH", "1995TH", "1090_w1TH"]


def get_json(url, tries=5):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001 - retry any network error
            if k == tries - 1:
                raise
            print(f"  retry {k + 1} after {e}", file=sys.stderr)
            time.sleep(3 * (k + 1))


def write_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {os.path.relpath(path)}")


def alerts():
    """Newest first; `limit` max 1000, `offset` paginates."""
    rows, off, page = [], 0, 0
    while True:
        q = {"limit": 1000, "offset": off}
        # Under rate limiting the API can answer 200 with an empty page mid-history, so retry
        # an empty page a few times before treating it as the end.
        for k in range(5):
            items = get_json(f"{TW}/alerts?{urllib.parse.urlencode(q)}").get("items", [])
            if items or not off:
                break
            print(f"  empty page at offset {off}, retry {k + 1}", file=sys.stderr)
            time.sleep(5 * (k + 1))
        rows += items
        page += 1
        print(f"  page {page}: {len(items)} rows (oldest {items[-1]['datetime'] if items else '-'})", file=sys.stderr)
        if len(items) < 1000:
            break
        off += 1000
        time.sleep(0.5)  # stay under the API's rate limit (429s seen at 0.25 s)
    fields = ["locationName", "permitNumber", "locationGridRef", "x", "y", "receivingWaterCourse", "alertType", "datetime"]
    # New alerts arriving mid-fetch shift the newest-first offsets and repeat rows; drop the repeats.
    seen = set()
    rows = [r for r in rows if not (tuple(r.get(k) for k in fields) in seen or seen.add(tuple(r.get(k) for k in fields)))]
    write_csv(os.path.join(RAW, "thames_alerts.csv"), rows, fields)


def status():
    d = get_json(f"{TW}/status")
    fields = ["uniqueId", "locationName", "permitNumber", "locationGridRef", "x", "y", "receivingWaterCourse",
              "alertStatus", "statusChanged", "alertPast48Hours", "mostRecentDischargeAlertStart", "mostRecentDischargeAlertStop"]
    write_csv(os.path.join(RAW, "thames_status.csv"), d["items"], fields)


def events():
    """Pair Start/Stop per site. Offline periods are kept separately as missing data, not dry days.
    Note: API datetimes are naive UK local time (BST/GMT) - localise as Europe/London before UTC maths."""
    with open(os.path.join(RAW, "thames_alerts.csv")) as f:
        rows = sorted(csv.DictReader(f), key=lambda r: (r["permitNumber"], r["locationName"], r["datetime"]))
    spills, offline, open_start, open_off = [], [], {}, {}
    for r in rows:
        key = (r["permitNumber"], r["locationName"])
        t = r["datetime"]
        kind = r["alertType"]
        if kind == "Start":
            open_start[key] = t
        elif kind == "Stop" and key in open_start:
            s = open_start.pop(key)
            hrs = (datetime.fromisoformat(t) - datetime.fromisoformat(s)).total_seconds() / 3600
            spills.append({"permitNumber": key[0], "locationName": key[1], "x": r["x"], "y": r["y"],
                           "start": s, "stop": t, "hours": round(hrs, 3)})
        elif kind == "Offline start":
            open_off[key] = t
        elif kind == "Offline stop" and key in open_off:
            offline.append({"permitNumber": key[0], "locationName": key[1], "start": open_off.pop(key), "stop": t})
    for key, s in open_start.items():  # still spilling at download time
        spills.append({"permitNumber": key[0], "locationName": key[1], "x": "", "y": "", "start": s, "stop": "", "hours": ""})
    write_csv(os.path.join(RAW, "events.csv"), spills, ["permitNumber", "locationName", "x", "y", "start", "stop", "hours"])
    write_csv(os.path.join(RAW, "offline.csv"), offline, ["permitNumber", "locationName", "start", "stop"])


def gauges():
    """EA Hydrology API: 15-minute rain and daily mean flow since 2022 -> data/raw/gauges/{rain,flow}_<ref>.csv."""
    def measure(ref, prop):
        q = {"station": ref} if "-" in ref else {"station.stationReference": ref, "observedProperty": prop}
        ids = [i["@id"].rsplit("/", 1)[-1] for i in get_json(f"{HYDRO}/id/measures.json?{urllib.parse.urlencode(q)}")["items"]]
        want = "-flow-m-86400-" if prop == "waterFlow" else "-t-900-"
        ids = [i for i in ids if want in i]
        return ids[0] if ids else None

    def readings(mid, since="2022-01-01"):
        out, off = [], 0
        while True:
            d = get_json(f"{HYDRO}/id/measures/{mid}/readings.json?min-date={since}&_limit=200000&_offset={off}")["items"]
            out += [(i["dateTime"], i.get("value"), i.get("quality")) for i in d]
            if len(d) < 200000:
                return out
            off += 200000

    out_dir = os.path.join(RAW, "gauges")
    os.makedirs(out_dir, exist_ok=True)
    for kind, refs, prop in [("rain", RAIN, "rainfall"), ("flow", FLOW, "waterFlow")]:
        for ref in refs:
            mid = measure(ref, prop)
            if not mid:
                print(f"{kind} {ref}: no measure")
                continue
            rows = readings(mid)
            with open(os.path.join(out_dir, f"{kind}_{ref.rsplit('_', 1)[-1] if '-' in ref else ref}.csv"), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["dateTime", "value", "quality"])
                w.writerows(rows)
            print(f"{kind} {ref}: {mid} {len(rows)} rows, {rows[0][0] if rows else '-'} -> {rows[-1][0] if rows else '-'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["alerts", "events", "status", "gauges"])
    {"alerts": alerts, "events": events, "status": status, "gauges": gauges}[ap.parse_args().cmd]()
