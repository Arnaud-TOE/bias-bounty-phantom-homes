"""Are Medicare/Medicaid nursing homes visible in Overture places, and where are they missing?

Every CMS-certified nursing home (Provider Information, Sep 2026) geocoded inside a scored
tract is matched to Overture places (challenge extract) within 250 m: any place whose
category is a care-facility category, or whose name shares most of its tokens with the
CMS provider name. Results are broken down by the challenge strata.

External data: CMS Nursing Home Provider Information (discovery/external/SOURCES.md).
Bias Discovery only; nothing here is read by the scored pipeline.
"""
import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CMS = ROOT / "discovery/external/raw/cms_nh/NH_ProviderInfo_Sep2026_3.csv"
OUT = ROOT / "discovery/out"
REGIONS = ["south-central-tx", "maricopa-az", "eastern-ok", "northern-ca", "eastern-wa"]
CARE = ("skilled_nursing", "retirement_home", "assisted_living_facility", "nursing_home",
        "rehabilitation_center", "hospice", "home_health_care", "senior_citizen_services",
        "memory_care", "health_and_medical", "medical_center", "hospital")
STOP = {"the", "of", "and", "at", "center", "centre", "llc", "inc", "nursing", "rehabilitation",
        "rehab", "healthcare", "health", "care", "home", "living", "skilled", "facility", "senior"}


def tokens(name: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (name or "").lower()) if t not in STOP and len(t) > 2}


def main():
    OUT.mkdir(exist_ok=True)
    c = pd.read_csv(CMS, dtype=str)
    c = c.rename(columns={"CMS Certification Number (CCN)": "ccn", "Provider Name": "name",
                          "Number of Certified Beds": "beds", "Urban": "cms_urban",
                          "Latitude": "lat", "Longitude": "lon", "State": "state"})
    c["lat"] = pd.to_numeric(c["lat"], errors="coerce")
    c["lon"] = pd.to_numeric(c["lon"], errors="coerce")
    c["beds"] = pd.to_numeric(c["beds"], errors="coerce")
    c = c.dropna(subset=["lat", "lon"])[["ccn", "name", "beds", "cms_urban", "state", "lat", "lon"]]

    con = duckdb.connect()
    con.sql("LOAD spatial; SET enable_progress_bar=false;")
    con.register("cms", c)
    rows = []
    for r in REGIONS:
        tr = (ROOT / f"data/raw/strata/{r}/{r}-census-tracts.parquet").as_posix()
        po = (ROOT / f"data/raw/reference/{r}/{r}-overture-pois.parquet").as_posix()
        nh = con.sql(f"""
            SELECT c.*, t.GEOID, '{r}' AS region FROM cms c
            JOIN '{tr}' t ON ST_Contains(t.geometry, ST_Point(c.lon, c.lat))
        """).df()
        if nh.empty:
            continue
        con.register("nh", nh)
        cand = con.sql(f"""
            SELECT n.ccn, p.names.primary AS pname, p.categories.primary AS pcat,
                   sqrt(power((ST_X(p.geometry) - n.lon) * cos(radians(n.lat)) * 111320, 2)
                        + power((ST_Y(p.geometry) - n.lat) * 110540, 2)) AS dist_m
            FROM nh n JOIN '{po}' p
              ON p.bbox.xmin BETWEEN n.lon - 0.004 AND n.lon + 0.004
             AND p.bbox.ymin BETWEEN n.lat - 0.003 AND n.lat + 0.003
        """).df()
        cand = cand[cand["dist_m"] <= 250]
        nh_tok = dict(zip(nh["ccn"], nh["name"].map(tokens)))

        def name_match(row):
            a, b = nh_tok.get(row["ccn"], set()), tokens(row["pname"])
            return bool(a) and len(a & b) / len(a) >= 0.5

        cand["name_match"] = cand.apply(name_match, axis=1)
        cand["care_cat"] = cand["pcat"].isin(CARE)
        agg = cand.groupby("ccn").agg(
            any_name=("name_match", "max"),
            any_care=("care_cat", "max"),
            near_name_m=("dist_m", lambda d: d[cand.loc[d.index, "name_match"]].min()),
        ).reset_index()
        rows.append(nh.merge(agg, on="ccn", how="left"))
    res = pd.concat(rows, ignore_index=True)
    res[["any_name", "any_care"]] = res[["any_name", "any_care"]].fillna(False).astype(bool)
    res["found"] = res["any_name"]
    res.to_parquet(OUT / "cms_nursing_homes.parquet", index=False)
    return res


if __name__ == "__main__":
    r = main()
    print(len(r), "CMS nursing homes in scored tracts")
    print(r.groupby("region")[["found", "any_care"]].mean().round(3).assign(n=r.groupby("region").size()).to_string())
    print(r.groupby("cms_urban")[["found", "any_care"]].mean().round(3).assign(n=r.groupby("cms_urban").size()).to_string())
