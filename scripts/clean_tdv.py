"""Clean the Thames Water daily treated volume (TDV) files (2019-2025) down to our Oxford works.

Reads the raw xlsx files in tdv_datasets/raw/ and writes one tidy table with consistent names
and flags to tdv_datasets/oxford/:
  tdv_oxford_2019_2025.csv   one row per works meter per day (long format)
  tdv_oxford_<year>.csv      the same, split by year
  tdv_oxford_daily.csv       one row per works per day, meters summed (what the models use)
  tdv_oxford_sites.csv       one row per works: meters, gap counts, per-year DWF (Q80) and max

Every file has the same works names and column layout whatever year it came from, and no
blank cells: days with no reading and days Thames Water flagged suspect are dropped (the sites
file still counts them). Every kept value has a `quality` of good or implausible (meter fault,
see below). Filter on quality == "good" for modelling.

Usage:
  python scripts/clean_edm.py   # first: site_id comes from edm_datasets/oxford/edm_oxford_sites.csv
  python scripts/clean_tdv.py

Only the works in SITES are kept, labelled with the same site_label and site_id as the EDM
cleaner so the two tables join directly. TDV is per treatment works, so the three network
overflows (The Willows, West Way, Littlemore Low Level) have no TDV, and nor does Tubney.
Weston-on-the-Green TDV is the works, not its pumping station overflow.

Traps handled (see the Readme sheet in each file):
  - data sheet name changes every year; header 'Date' or 'DATE'; column order shuffles in 2025
  - works names drift: 'BLETCHINGTON' (2020), 'APPLETON' without STW (2021), 'CHARLTON OTMOOR ***
    STW' (2022-23, 2025), 'CASSINGTON' and 'CHURCH HANBOROUGH' without STW (2024)
  - Abingdon has two meters, named A/B, (2), 2, STW2, STW 2 or STW (2) depending on the year
  - missing values: the text 'NaN' or a blank cell
  - suspect values are marked only by cell fill: orange FFC000 to 2023, red FF0000 from 2024.
    The colour is read from the Readme key, so a new year with a new colour still works.
  - 2019 Readme says 'm3', later years 'm3/d': both are daily totals, medians line up
  - runs of zeros and near-zeros are meter faults (South Leigh Aug 2021 - Jun 2022, Church
    Hanborough spring 2020, Abingdon meter 1 Jan 2021), and weeks at ~20x the usual flow are not
    real either (Islip Nov-Dec 2025). Both are kept with quality 'implausible'.
"""
import argparse
import glob
import os
import re

import openpyxl
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
TDV = os.path.join(ROOT, "tdv_datasets")
RAW = os.path.join(TDV, "raw")
OUT = os.path.join(TDV, "oxford")
EDM_SITES = os.path.join(ROOT, "edm_datasets", "oxford", "edm_oxford_sites.csv")
LOW = 0.1    # below this fraction of the works' median for the year -> implausible
HIGH = 10    # above this multiple of the works' median for the year -> implausible

# EDM site_label -> regex on the TDV column name (upper-cased, '*' removed, spaces collapsed).
# Each must match exactly one column per year, except Abingdon (two meters).
SITES = {
    "Charlton-on-Otmoor": r"^CHARLTON OTMOOR STW$",
    "Horton-cum-Studley": r"^HORTON CUM STUDLEY STW$",
    "Forest Hill": r"^FOREST HILL STW$",
    "Beckley": r"^BECKLEY STW$",
    "Islip": r"^ISLIP STW$",
    "Wheatley": r"^WHEATLEY STW$",
    "Oxford": r"^OXFORD STW$",
    "Appleton": r"^APPLETON( STW)?$",
    "Standlake": r"^STANDLAKE STW$",
    "Stanton Harcourt": r"^STANTON HARCOURT STW$",
    "South Leigh": r"^SOUTH LEIGH STW$",
    "Cassington": r"^CASSINGTON( STW)?$",
    "Church Hanborough": r"^CHURCH HANBOROUGH( STW)?$",
    "Combe": r"^COMBE STW$",
    "Woodstock": r"^WOODSTOCK STW$",
    "Bletchingdon": r"^BLETCHING[DT]ON STW$",
    "Weston-on-the-Green STW": r"^WESTON ON THE GREEN STW$",
    "Culham": r"^CULHAM STW$",
    "Abingdon": r"^ABINGDON",
}
# Abingdon's second meter: 'ABINGDON (2) STW', 'ABINGDON STW B', 'ABINGDON STW2', '... 2', '... (2)'
SECOND_METER = r"\(2\)|STW ?2$|STW B$"


def norm(s):
    return re.sub(r"\s+", " ", str(s or "").replace("*", "")).strip().upper()


def suspect_colour(wb):
    """Fill colour the Readme key gives for 'Suspect'."""
    for row in wb.worksheets[0].iter_rows():
        for c in row:
            if norm(c.value) == "SUSPECT":
                return c.fill.fgColor.rgb
    raise SystemExit("no 'Suspect' entry in Readme")


def read_year(path):
    year = int(os.path.basename(path)[:4])
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    suspect = suspect_colour(wb)
    ws = wb.worksheets[1]
    rows = list(ws.iter_rows())
    headers = [norm(c.value) for c in rows[0]]
    if headers[0] != "DATE":
        raise SystemExit(f"{path}: first column is {headers[0]!r}, not Date")

    cols = {}  # column index -> (site_label, meter)
    for label, pattern in SITES.items():
        hit = [i for i, h in enumerate(headers) if re.search(pattern, h)]
        if len(hit) != (2 if label == "Abingdon" else 1):
            raise SystemExit(f"{year} {label!r} matched {[headers[i] for i in hit]}")
        for i in hit:
            meter = 2 if label == "Abingdon" and re.search(SECOND_METER, headers[i]) else 1
            cols[i] = (label, meter)
    if sorted(m for l, m in cols.values() if l == "Abingdon") != [1, 2]:
        raise SystemExit(f"{year}: could not tell the two Abingdon meters apart")

    out = []
    for r in rows[1:]:
        date = r[0].value
        if date is None:
            continue
        for i, (label, meter) in cols.items():
            c = r[i]
            v = c.value
            missing = v is None or (isinstance(v, str) and v.strip().lower() in ("nan", ""))
            flagged = c.fill is not None and c.fill.fill_type and c.fill.fgColor.rgb == suspect
            out.append({
                "site_label": label, "meter": meter,
                "date": pd.Timestamp(date).normalize(), "year": year,
                "tdv_m3": None if missing else float(v),
                "quality": "missing" if missing else "suspect" if flagged else "good",
            })
    df = pd.DataFrame(out)
    if df["date"].dt.year.ne(year).any() or df.duplicated(["site_label", "meter", "date"]).any():
        raise SystemExit(f"{path}: dates outside {year} or repeated")
    return df


def main():
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args()

    df = pd.concat([read_year(p) for p in sorted(glob.glob(os.path.join(RAW, "*.xlsx")))],
                   ignore_index=True)

    edm = pd.read_csv(EDM_SITES).set_index("site_label")
    df.insert(0, "site_id", df["site_label"].map(edm["site_id"]))
    df["permit_ref"] = df["site_label"].map(edm["permit_ref"])
    if df["site_id"].isna().any():
        raise SystemExit(f"no EDM site for {df.loc[df['site_id'].isna(), 'site_label'].unique()}")

    # Meter faults: judged against the median of good values for that meter in that year.
    good = df["tdv_m3"].where(df["quality"] == "good")
    median = good.groupby([df["site_label"], df["meter"], df["year"]]).transform("median")
    implausible = (df["tdv_m3"] < LOW * median) | (df["tdv_m3"] > HIGH * median)
    df.loc[(df["quality"] == "good") & implausible, "quality"] = "implausible"
    counts = df.groupby("site_label")["quality"].value_counts().unstack(fill_value=0)

    # Drop days with no value or a suspect one, and use one name per works whatever the year
    # called it.
    df = df[~df["quality"].isin(["missing", "suspect"])].copy()
    df["works_name"] = df["site_label"].map(lambda l: l if l.endswith("STW") else f"{l} STW")

    order = ["site_id", "site_label", "works_name", "permit_ref", "meter", "date", "year", "tdv_m3",
             "quality"]
    df = df[order].sort_values(["site_id", "meter", "date"])

    # Works total per day: Abingdon's two meters summed, kept only when both have a value; the
    # day takes the worse quality of the two.
    rank = {"good": 0, "implausible": 1}
    keys = ["site_id", "site_label", "works_name", "permit_ref", "date", "year"]
    daily = df.assign(rank=df["quality"].map(rank)).groupby(keys).agg(
        tdv_m3=("tdv_m3", "sum"), rank=("rank", "max"), meters=("meter", "size")).reset_index()
    full = daily["meters"] == daily["site_label"].map(df.groupby("site_label")["meter"].nunique())
    daily = daily[full].drop(columns="meters")
    daily["quality"] = daily.pop("rank").map({v: k for k, v in rank.items()})
    daily["tdv_m3"] = daily["tdv_m3"].round(2)
    daily = daily.sort_values(["site_id", "date"])

    # Per works and year, from good days only: DWF ~ Q80 (value exceeded on 80% of days, EA
    # method) and the max (for the plateau check).
    ok = daily[daily["quality"] == "good"]
    per_year = ok.groupby(["site_label", "year"])["tdv_m3"].agg(
        dwf_q80_m3=lambda s: s.quantile(0.2), max_m3="max", good_days="count").round(0)
    wide = per_year.unstack("year")
    wide.columns = [f"{v}_{y}" for v, y in wide.columns]
    info = df.groupby("site_label")[["site_id", "works_name", "permit_ref"]].first()
    info["meters"] = df.groupby("site_label")["meter"].nunique()
    for q in ("missing", "suspect", "implausible"):
        info[f"{q}_days"] = counts.get(q, 0)
    info = info.join(edm[["distance_km"]])
    sites = info.join(wide).reset_index().set_index("site_id").sort_values("distance_km")

    outputs = {"tdv_oxford_2019_2025.csv": df, "tdv_oxford_daily.csv": daily}
    outputs.update({f"tdv_oxford_{y}.csv": g for y, g in df.groupby("year")})
    for name, table in [*outputs.items(), ("tdv_oxford_sites.csv", sites)]:
        if table.isna().any().any():
            raise SystemExit(f"{name} would have blank cells: {table.columns[table.isna().any()].tolist()}")

    os.makedirs(OUT, exist_ok=True)
    for name, table in outputs.items():
        table.to_csv(os.path.join(OUT, name), index=False, date_format="%Y-%m-%d")
    sites.to_csv(os.path.join(OUT, "tdv_oxford_sites.csv"))

    print(f"{len(df)} meter-days, {len(daily)} works-days, {len(sites)} works -> "
          f"{os.path.relpath(OUT, ROOT)}/")
    print(daily.groupby("year")["quality"].value_counts().unstack(fill_value=0).to_string())

if __name__ == "__main__":
    main()
