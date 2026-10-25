"""Clean the EA EDM storm overflow annual returns (2020-2025) down to our Oxford overflows.

Reads the raw xlsx files in edm_datasets/<year>/ and writes one tidy table with consistent
names and units to edm_datasets/oxford/:
  edm_oxford_2020_2025.csv   one row per overflow per year (long format)
  edm_oxford_<year>.csv      the same, split by year
  edm_oxford_sites.csv       one row per overflow, spills and hours by year side by side

Usage:
  python scripts/clean_edm.py

Only the columns the project uses are written (see `order` in main): spill count, hours and
average length with monitor uptime; join keys (permit, works name); location, river and Port
Meadow flags for the swim heatmap; high-spill reasons and improvements for the capacity ranking.
Everything else stays in the raw xlsx files.

Only the overflows in SITES are kept. Each is found by matching its name (EA or operational)
among Thames Water overflows within 35 x 35 km of Carfax, then kept for every year it appears,
even when it was renamed or re-permitted.

Traps handled (see the EA dataset README in each year folder):
  - header row moves: row 1 (2020), 2 (2021-2024), 6 (2025); 2024+ has Unique ID first
  - duration: decimal hours to 2023; hh:mm:ss from 2024, read as timedelta, and in 2025
    values under 24 h come through as datetime.time
  - EDM uptime: fraction 0-1 in 2020 and 2022, percent 0-100 otherwise -> always percent
  - missing values: blank, 'N/A', '#N/A'
  - 2020 has no NGR: located by joining its permit number to later years
  - permits and IDs change between years (many TEMP.xxxx permits were reissued around 2023-24),
    so overflows are matched across years by outlet location instead -> site_id
"""
import argparse
import datetime as dt
import glob
import os
import re

import openpyxl
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
EDM = os.path.join(ROOT, "edm_datasets")
OUT = os.path.join(EDM, "oxford")
YEARS = range(2020, 2026)
CARFAX = (451300, 206200)  # OSGB36 easting, northing
PORT_MEADOW = "wolvercote"
MISSING = {"", "n/a", "#n/a", "na", "none", "not applicable", "-", "permit applied for"}
SAME_SITE_M = 100  # outlets this close (same asset type) are treated as one overflow across years
SEARCH_HALF_M = 17500  # only look for SITES within this distance (E and N) of Carfax

# Overflows to keep: label -> regex on the site name, lower-cased with hyphens as spaces, or
# "permit:<ref>" where names are ambiguous. Each must match exactly one overflow; anchors stop
# "oxford" hitting Woodstock Road Oxford etc.
SITES = {
    "Charlton-on-Otmoor": r"^charlton on otmoor",
    "Horton-cum-Studley": r"^horton cum studley",
    "Forest Hill": r"^forest hill",
    "Beckley": r"^beckley stw|^constable's piece",  # EA name is Constable's Piece WWTW
    "Islip": r"^islip",
    "Wheatley": r"^wheatley",
    "Oxford": r"^oxford \(sandford\)|^oxford stw",
    "Littlemore Low Level": r"^littlemore low level",
    "Tubney": r"^tubney",
    "Appleton": r"^appleton",
    "The Willows, North Hinksey Lane": r"^the willows",
    "West Way, Botley (Syphon)": r"^west way",
    "Standlake": r"^standlake",
    "Stanton Harcourt": r"^stanton harcourt",
    "South Leigh": r"^south leigh",
    "Cassington": r"^cassington",
    "Church Hanborough": r"^church hanborough",
    "Combe": r"^combe",
    "Woodstock": r"^woodstock (?:stw|wwtw|sewage|wastewater)",
    "Bletchingdon": r"^bletchingdon",
    "Weston-on-the-Green STW": r"^weston on the green (?:stw|wwtw)(?!.*pump)",
    "Weston-on-the-Green": r"^weston on the green.*pump",  # pumping station by the works
    "Culham": r"^culham",
    # Abingdon Main No.1 pumping station is also called "Abingdon STW" by Thames Water in 2023
    "Abingdon": "permit:CTCR.1804",
}

# Clean column name -> header prefix(es) as they appear in the raw files (whitespace-collapsed,
# lower-cased). The first prefix that matches a header wins.
COLUMNS = {
    "unique_id": ["unique id"],
    "old_unique_id": ["old format unique id"],
    "company": ["water company name"],
    "site_name": ["site name (ea consents database)", "site name"],
    "site_name_wasc": ["site name (wasc operational)"],
    "permit_ref": ["ea permit reference", "permit no."],
    "wasc_permit_ref": ["wasc supplementary permit ref"],
    "activity_ref": ["activity reference"],
    "asset_type": ["storm discharge asset type"],
    "outlet_ngr": ["outlet discharge ngr"],
    "wfd_waterbody_id": ["wfd waterbody id"],
    "wfd_catchment": ["wfd waterbody catchment name"],
    "receiving_water": ["receiving water"],
    "bathing_water": ["bathing water", "bathing beach"],
    "treatment_method": ["treatment method"],
    "edm_commissioned": ["initial edm commission date"],
    "data_start_year": ["data start"],
    "spill_hours": ["total duration"],
    "spill_count": ["counted spills"],
    "long_term_avg_spills": ["long-term average spill count"],
    "edm_uptime_pct": ["edm operation - % of reporting period", "% of reporting period edm operational"],
    "edm_downtime_reason": ["edm operation - reporting % - primary reason"],
    "edm_action": ["edm operation - action taken"],
    "high_spill_reason": ["high spill frequency - operational review - primary reason",
                          "high spill frequency - operational review - single year reason"],
    "high_spill_reason_long_term": ["high spill frequency - operational review - long-term"],
    "investigation": ["investigation activity"],
    "improvement": ["improvement activity"],
}


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def clean_str(v):
    if v is None:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return None if s.lower() in MISSING else s


def hours(v):
    """Spill duration in hours, whatever form the year stored it in."""
    if isinstance(v, dt.timedelta):
        return v.total_seconds() / 3600
    if isinstance(v, dt.time):
        return v.hour + v.minute / 60 + v.second / 3600
    if isinstance(v, (int, float)):
        return float(v)
    return None


def number(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = clean_str(v)
    m = re.match(r"^-?\d+(\.\d+)?", s or "")
    return float(m.group()) if m else None


def ngr_to_en(ngr):
    """OS grid reference like 'SP5420002201' or 'SP 50351 08414' -> (easting, northing) in m."""
    s = re.sub(r"\s+", "", str(ngr or "")).upper()
    m = re.fullmatch(r"([HJNOST][A-HJ-Z])(\d+)", s)
    if not m or len(m.group(2)) % 2:
        return None, None
    letters, digits = m.groups()
    i1, i2 = ("ABCDEFGHJKLMNOPQRSTUVWXYZ".index(c) for c in letters)
    e100 = ((i1 - 2) % 5) * 5 + i2 % 5
    n100 = (19 - (i1 // 5) * 5) - i2 // 5
    half = len(digits) // 2
    scale = 10 ** (5 - half)
    return e100 * 100000 + int(digits[:half]) * scale, n100 * 100000 + int(digits[half:]) * scale


def site_ids(df):
    """Stable overflow ID across years. Rows are linked when they share a permit or their outlets
    are within SAME_SITE_M metres; asset type is ignored because it was relabelled between years
    for many works. A group that would hold two rows from one year (two overflows at one site) is
    re-linked with a 20 m radius, and only if that still clashes is it split by asset type."""
    rows = df.reset_index(drop=True)
    asset = rows["asset_type"].fillna("").str.replace(" - with treatment", "")

    def link(idx, metres):
        parent = {i: i for i in idx}

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for k, i in enumerate(idx):
            for j in idx[:k]:
                a, b = rows.iloc[i], rows.iloc[j]
                same_permit = a["permit_ref"] is not None and a["permit_ref"] == b["permit_ref"]
                near = (pd.notna(a["easting"]) and pd.notna(b["easting"])
                        and abs(a["easting"] - b["easting"]) <= metres
                        and abs(a["northing"] - b["northing"]) <= metres)
                if same_permit or near:
                    parent[find(i)] = find(j)
        return {i: find(i) for i in idx}

    def clashing(key):
        dup = key.groupby([key, rows["year"]]).transform("size") > 1
        return dup.groupby(key).transform("any")

    key = pd.Series(link(list(range(len(rows))), SAME_SITE_M)).astype(str)
    bad = clashing(key)
    if bad.any():
        tight = link(list(key[bad].index), 20)
        key[bad] = key[bad] + "." + pd.Series(tight).astype(str)
        bad = clashing(key)
        key[bad] = key[bad] + "|" + asset[bad]
    if clashing(key).any():
        raise SystemExit("site_id still merges two overflows in one year")

    # Number sites by distance from Carfax so OX001 is the most central.
    first = rows.assign(key=key).groupby("key")["distance_km"].min().sort_values(na_position="last")
    names = {k: f"OX{i + 1:03d}" for i, k in enumerate(first.index)}
    return pd.Series(key.map(names).values, index=df.index)


def keep_sites(df):
    """Keep every year of each overflow in SITES; label it; fail loudly on 0 or >1 matches."""
    names = (df["site_name"].fillna("") + "\n" + df["site_name_wasc"].fillna("")).str.lower()
    names = names.str.replace("-", " ").str.replace(r"[ \t]+", " ", regex=True)
    labels = {}
    for label, pattern in SITES.items():
        if pattern.startswith("permit:"):
            match = df["permit_ref"] == pattern.removeprefix("permit:")
        else:
            match = names.str.contains(pattern, regex=True, flags=re.M)
        hit = df.loc[match, "site_id"].unique()
        if len(hit) != 1:
            found = df[df["site_id"].isin(hit)].groupby("site_id")["site_name"].last().to_dict()
            raise SystemExit(f"{label!r} matched {len(hit)} overflows: {found}")
        if hit[0] in labels:
            raise SystemExit(f"{label!r} and {labels[hit[0]]!r} matched the same overflow {hit[0]}")
        labels[hit[0]] = label
    out = df[df["site_id"].isin(labels)].copy()
    out.insert(0, "site_label", out["site_id"].map(labels))
    return out


def year_file(year):
    if year == 2020:
        return os.path.join(EDM, "2020", "EAv EDM Return Thames Water Annual 2020.xlsx")
    return glob.glob(os.path.join(EDM, str(year), "*all water and sewerage companies.xlsx"))[0]


def read_year(year):
    wb = openpyxl.load_workbook(year_file(year), read_only=True, data_only=True)
    ws = next(w for w in wb.worksheets if year == 2020 or w.title.startswith("Thames"))
    rows = list(ws.iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows)
              if any(norm(c) in ("water company name", "unique id") for c in r))
    headers = [norm(c) for c in rows[hi]]
    idx = {}
    for name, prefixes in COLUMNS.items():
        for p in prefixes:
            hit = [i for i, h in enumerate(headers) if h.startswith(p) and i not in idx.values()]
            if hit:
                idx[name] = hit[0]
                break
    out = []
    for r in rows[hi + 1:]:
        if not any(c is not None for c in r):
            continue
        rec = {"year": year}
        for name in COLUMNS:
            v = r[idx[name]] if name in idx and idx[name] < len(r) else None
            if name == "spill_hours":
                rec[name] = hours(v)
            elif name in ("spill_count", "long_term_avg_spills", "edm_uptime_pct", "data_start_year"):
                rec[name] = number(v)
            else:
                rec[name] = clean_str(v)
        out.append(rec)
    df = pd.DataFrame(out)
    if year in (2020, 2022):  # these years store uptime as a 0-1 fraction
        df["edm_uptime_pct"] *= 100
    return df


def main():
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args()

    df = pd.concat([read_year(y) for y in YEARS], ignore_index=True)
    df = df[df["company"].fillna("").str.lower().str.startswith("thames")].copy()

    # Tidy categories that differ only by case/spelling between years.
    df["asset_type"] = df["asset_type"].str.replace("WWTW", "WwTW")
    df.loc[df["year"] == 2023, "old_unique_id"] = df.loc[df["year"] == 2023, "unique_id"]
    df.loc[df["year"] == 2023, "unique_id"] = None

    en = df["outlet_ngr"].map(ngr_to_en)
    df["easting"] = [e for e, _ in en]
    df["northing"] = [n for _, n in en]

    # 2020 has no NGR or IDs: borrow them from the latest later year with the same permit,
    # but only where that permit maps to a single location (some permits cover several outlets).
    later = df[(df["year"] > 2020) & df["permit_ref"].notna() & df["easting"].notna()]
    spread = later.groupby("permit_ref").agg(de=("easting", lambda s: s.max() - s.min()),
                                             dn=("northing", lambda s: s.max() - s.min()))
    single = spread[(spread["de"] <= SAME_SITE_M) & (spread["dn"] <= SAME_SITE_M)].index
    lookup = (later[later["permit_ref"].isin(single)].sort_values("year")
              .groupby("permit_ref").last())
    borrow = ["easting", "northing", "outlet_ngr", "unique_id", "asset_type", "wfd_waterbody_id",
              "wfd_catchment", "receiving_water"]
    m2020 = (df["year"] == 2020) & df["permit_ref"].isin(lookup.index)
    for c in borrow:
        df.loc[m2020, c] = df.loc[m2020, "permit_ref"].map(lookup[c])
    df["location_from_later_year"] = m2020

    # Carry the 2024+ Unique ID back to 2021-2023 rows via the old-format ID, then via permit.
    old_to_new = df.dropna(subset=["unique_id", "old_unique_id"]).set_index("old_unique_id")["unique_id"]
    old_to_new = old_to_new[~old_to_new.index.duplicated()]
    need = df["unique_id"].isna() & df["old_unique_id"].notna()
    df.loc[need, "unique_id"] = df.loc[need, "old_unique_id"].map(old_to_new)

    df["distance_km"] = ((df["easting"] - CARFAX[0]) ** 2 + (df["northing"] - CARFAX[1]) ** 2) ** 0.5 / 1000
    in_search = ((df["easting"] - CARFAX[0]).abs() <= SEARCH_HALF_M) & ((df["northing"] - CARFAX[1]).abs() <= SEARCH_HALF_M)
    df["bathing_water"] = df["bathing_water"].where(df["bathing_water"] != "0")  # 2021 placeholder
    df["port_meadow_tagged"] = df["bathing_water"].fillna("").str.lower().str.contains(PORT_MEADOW)

    ox = df[in_search].copy()
    ox["site_name"] = ox["site_name"].fillna(ox["site_name_wasc"])
    ox["site_id"] = site_ids(ox)
    ox = keep_sites(ox)
    # EA tags 8 upstream works to Port Meadow in 2022-24 but only Cassington in 2025, so also
    # flag every year of any overflow that was ever tagged.
    ox["port_meadow_source"] = ox.groupby("site_id")["port_meadow_tagged"].transform("any")
    ids_per_site = ox.groupby("site_id")["unique_id"].nunique()
    one_id = ox["site_id"].map(ids_per_site) == 1
    ox.loc[one_id, "unique_id"] = ox.loc[one_id].groupby("site_id")["unique_id"].transform("last")
    ox["edm_uptime_low"] = ox["edm_uptime_pct"] < 90
    ox["avg_spill_hours"] = (ox["spill_hours"] / ox["spill_count"].where(ox["spill_count"] > 0)).round(2)
    ox["spill_hours"] = ox["spill_hours"].round(2)
    ox["distance_km"] = ox["distance_km"].round(2)
    ox["spill_count"] = ox["spill_count"].astype("Int64")
    ox["data_start_year"] = ox["data_start_year"].astype("Int64")
    ox["easting"] = ox["easting"].astype("Int64")
    ox["northing"] = ox["northing"].astype("Int64")

    # Only what the project uses: spill targets and their reliability, join keys (permit for the
    # Thames Water alerts/TDV/permits, works name for TDV), location and river for the swim
    # heatmap, and the capacity-related reasons and upgrades for the investment ranking.
    order = ["site_id", "site_label", "year", "permit_ref", "unique_id", "site_name", "site_name_wasc",
             "asset_type", "spill_count", "spill_hours", "avg_spill_hours", "edm_uptime_pct",
             "edm_uptime_low", "long_term_avg_spills", "data_start_year", "easting", "northing",
             "distance_km", "receiving_water", "wfd_catchment", "port_meadow_tagged",
             "port_meadow_source", "high_spill_reason", "high_spill_reason_long_term", "improvement"]
    ox = ox[order].sort_values(["site_id", "year"])

    os.makedirs(OUT, exist_ok=True)
    ox.to_csv(os.path.join(OUT, "edm_oxford_2020_2025.csv"), index=False)
    for y, g in ox.groupby("year"):
        g.to_csv(os.path.join(OUT, f"edm_oxford_{y}.csv"), index=False)

    wide = ox.pivot_table(index="site_id", columns="year", values=["spill_count", "spill_hours"],
                          aggfunc="first")
    wide.columns = [f"{v}_{y}" for v, y in wide.columns]
    info = (ox.groupby("site_id")
            [["site_label", "site_name", "site_name_wasc", "unique_id", "permit_ref", "asset_type", "receiving_water",
              "wfd_catchment", "easting", "northing", "distance_km", "port_meadow_source",
              "high_spill_reason_long_term"]].last())
    info["permits_all_years"] = ox.groupby("site_id")["permit_ref"].agg(
        lambda s: " | ".join(dict.fromkeys(s.dropna())))
    sites = info.join(wide).sort_values("distance_km")
    sites.to_csv(os.path.join(OUT, "edm_oxford_sites.csv"))

    print(f"{len(ox)} overflow-years, {len(sites)} overflows -> {os.path.relpath(OUT, ROOT)}/")
    print(ox.groupby("year").agg(overflows=("site_name", "size"), spills=("spill_count", "sum"),
                                 hours=("spill_hours", "sum")).round(0).to_string())


if __name__ == "__main__":
    main()
