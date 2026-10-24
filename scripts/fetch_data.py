"""Fetch Spillcast's raw data into data/raw/ (stdlib only).

Usage:
  python scripts/fetch_data.py thames-alerts              # all Thames Water start/stop alerts (~154 pages)
  python scripts/fetch_data.py thames-alerts --name Oxford
  python scripts/fetch_data.py thames-status              # current status of all ~573 monitors
  python scripts/fetch_data.py events                     # pair alerts into events -> data/raw/events.csv
  python scripts/fetch_data.py hydrology --preset all --since 2022-01-01
  python scripts/fetch_data.py dtm --res 20               # EA LIDAR DTM for the Oxford box (GeoTIFF)

All endpoints below were verified live on 24 Oct 2026 and need no API key.
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

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
TW = "https://api.thameswater.co.uk/opendata/v2/discharge"
HYDRO = "https://environment.data.gov.uk/hydrology/id/measures"
DTM_WCS = "https://environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs"
DTM_COVERAGE = "13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m"

# Hydrology API measure IDs (daily series where available). Stage gauges are in m above
# station datum; add the datum (flood-monitoring /stageScale) to get mAOD.
HYDRO_PRESETS = {
    "rain_osney_daily": "5086b349-e04b-4f8e-b8f1-fa92b21078d0_256230TP-rainfall-t-86400-mm-qualified",
    "rain_osney_15min": "5086b349-e04b-4f8e-b8f1-fa92b21078d0_256230TP-rainfall-t-900-mm-qualified",
    "gw_oxford_SP50_72": "ca3d0164-ee1d-444e-bc6c-04d600498b61-gw-logged-i-subdaily-mAOD-qualified",
    "gw_horspath": "c5ce6e05-0356-40ac-bcdc-166b65bd914a-gw-logged-i-subdaily-mAOD-qualified",
    # Cherwell gauges move ~1.4 m; the Thames lock headwater gauges are held within ~0.3 m.
    "level_cherwell_oxford_1490TH_max": "839866a2-80ca-42a8-a695-8e6d6b165fa6-level-max-86400-m-qualified",
    "flow_cherwell_oxford_1490TH_min": "839866a2-80ca-42a8-a695-8e6d6b165fa6-flow-min-86400-m3s-qualified",
    "level_kings_mill_1491TH_max": "a2d56f20-689b-4d3f-ab13-5e7c4baf2772-level-max-86400-m-qualified",
    "flow_thames_farmoor_1100TH_mean": "6b80bd1c-6c19-4c26-875d-108bf8ef1a84-flow-m-86400-m3s-qualified",
    "level_sandford_1502TH_max": "95404e71-1291-4fb9-b372-bec75cd3d040-level-max-86400-m-qualified",
    "level_osney_1303TH_max": "5086b349-e04b-4f8e-b8f1-fa92b21078d0-level-max-86400-m-qualified",
}


def get_json(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001 - retry any network error
            if k == tries - 1:
                raise
            print(f"  retry {k + 1} after {e}", file=sys.stderr)
            time.sleep(2 * (k + 1))


def write_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {os.path.relpath(path)}")


def thames_alerts(name=None, max_pages=None):
    """Newest first; `limit` max 1000, `offset` paginates. Filters that work: locationName, permitNumber."""
    rows, off, page = [], 0, 0
    while True:
        q = {"limit": 1000, "offset": off}
        if name:
            q["locationName"] = name
        d = get_json(f"{TW}/alerts?{urllib.parse.urlencode(q)}")
        items = d.get("items", [])
        rows += items
        page += 1
        print(f"  page {page}: {len(items)} rows (oldest {items[-1]['datetime'] if items else '-'})", file=sys.stderr)
        if len(items) < 1000 or (max_pages and page >= max_pages):
            break
        off += 1000
        time.sleep(0.25)  # stay well under the ~5 req/s limit reported by third parties
    fields = ["locationName", "permitNumber", "locationGridRef", "x", "y", "receivingWaterCourse", "alertType", "datetime"]
    suffix = f"_{name.lower().replace(' ', '_')}" if name else ""
    write_csv(os.path.join(RAW, f"thames_alerts{suffix}.csv"), rows, fields)


def thames_status():
    d = get_json(f"{TW}/status")
    fields = ["uniqueId", "locationName", "permitNumber", "locationGridRef", "x", "y", "receivingWaterCourse",
              "alertStatus", "statusChanged", "alertPast48Hours", "mostRecentDischargeAlertStart", "mostRecentDischargeAlertStop"]
    write_csv(os.path.join(RAW, "thames_status.csv"), d["items"], fields)


def pair_events(src=None):
    """Pair Start/Stop per site. Offline periods are kept separately as missing data, not dry days.
    Note: API datetimes are naive UK local time (BST/GMT) - localise as Europe/London before UTC maths."""
    src = src or os.path.join(RAW, "thames_alerts.csv")
    with open(src) as f:
        alerts = sorted(csv.DictReader(f), key=lambda r: (r["permitNumber"], r["locationName"], r["datetime"]))
    events, offline, open_start, open_off = [], [], {}, {}
    for r in alerts:
        key = (r["permitNumber"], r["locationName"])
        t = r["datetime"]
        kind = r["alertType"]
        if kind == "Start":
            open_start[key] = t
        elif kind == "Stop" and key in open_start:
            s = open_start.pop(key)
            hrs = (datetime.fromisoformat(t) - datetime.fromisoformat(s)).total_seconds() / 3600
            events.append({"permitNumber": key[0], "locationName": key[1], "x": r["x"], "y": r["y"],
                           "start": s, "stop": t, "hours": round(hrs, 3)})
        elif kind == "Offline start":
            open_off[key] = t
        elif kind == "Offline stop" and key in open_off:
            offline.append({"permitNumber": key[0], "locationName": key[1], "start": open_off.pop(key), "stop": t})
    for key, s in open_start.items():  # still spilling at download time
        events.append({"permitNumber": key[0], "locationName": key[1], "x": "", "y": "", "start": s, "stop": "", "hours": ""})
    write_csv(os.path.join(RAW, "events.csv"), events, ["permitNumber", "locationName", "x", "y", "start", "stop", "hours"])
    write_csv(os.path.join(RAW, "offline.csv"), offline, ["permitNumber", "locationName", "start", "stop"])


def hydrology(measure, label, since):
    rows, off = [], 0
    while True:
        q = {"min-date": since, "_limit": 100000, "_offset": off}
        d = get_json(f"{HYDRO}/{measure}/readings.json?{urllib.parse.urlencode(q)}")
        items = d.get("items", [])
        rows += [{"dateTime": i.get("dateTime"), "date": i.get("date"), "value": i.get("value"),
                  "quality": i.get("quality")} for i in items]
        if len(items) < 100000:
            break
        off += 100000
    write_csv(os.path.join(RAW, f"hydro_{label}.csv"), rows, ["dateTime", "date", "value", "quality"])


def dtm(res, e0=440000, e1=462000, n0=198000, n1=216000):
    """EA LIDAR Composite DTM 2022 via WCS. res in metres (1 m native). Float32 GeoTIFF, EPSG:27700."""
    q = (f"service=WCS&version=2.0.1&request=GetCoverage&CoverageId={DTM_COVERAGE}&format=image/tiff"
         f"&subset=E({e0},{e1})&subset=N({n0},{n1})&SCALEFACTOR={1 / res}")
    out = os.path.join(RAW, f"oxford_dtm_{res}m.tif")
    os.makedirs(RAW, exist_ok=True)
    urllib.request.urlretrieve(f"{DTM_WCS}?{q}", out)
    print(f"wrote {os.path.getsize(out) / 1e6:.1f} MB -> {os.path.relpath(out)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["thames-alerts", "thames-status", "events", "hydrology", "dtm"])
    ap.add_argument("--name", help="Thames Water locationName filter, e.g. Oxford")
    ap.add_argument("--max-pages", type=int)
    ap.add_argument("--src", help="alerts CSV to pair (default data/raw/thames_alerts.csv)")
    ap.add_argument("--preset", help="hydrology preset name, or 'all'")
    ap.add_argument("--measure", help="raw Hydrology measure id")
    ap.add_argument("--since", default="2022-01-01")
    ap.add_argument("--res", type=int, default=20)
    a = ap.parse_args()
    if a.cmd == "thames-alerts":
        thames_alerts(a.name, a.max_pages)
    elif a.cmd == "thames-status":
        thames_status()
    elif a.cmd == "events":
        pair_events(a.src)
    elif a.cmd == "hydrology":
        if a.measure:
            hydrology(a.measure, a.measure[:12], a.since)
        else:
            for label, m in HYDRO_PRESETS.items():
                if a.preset in ("all", label):
                    hydrology(m, label, a.since)
    elif a.cmd == "dtm":
        dtm(a.res)
