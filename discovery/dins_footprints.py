"""Are wildfire-destroyed structures still drawn on the map?

For every CAL FIRE DINS inspection point inside the northern-ca study region, find the
Overture building footprint (challenge extract, release 2026-08-19.0) that contains it or
lies within 10 m, and record that footprint's source and source date. Structures inspected
as "No Damage" are the control: they tell how often a real, standing structure is matched.

External data: CAL FIRE DINS (discovery/external/SOURCES.md). Bias Discovery only; nothing
here is read by the scored pipeline.
"""
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DINS = ROOT / "discovery/external/raw/calfire_dins/dins.csv"
TRACTS = ROOT / "data/raw/strata/northern-ca/northern-ca-census-tracts.parquet"
BUILDINGS = ROOT / "data/raw/reference/northern-ca/northern-ca-overture-buildings.parquet"
OUT = ROOT / "discovery/out"


def load_dins() -> pd.DataFrame:
    cols = {"GLOBALID": "gid", "* Damage": "damage", "* Structure Type": "stype",
            "Structure Category": "scat", "* Incident Name": "incident",
            "Incident Start Date": "start", "County": "county", "Latitude": "lat", "Longitude": "lon"}
    d = pd.read_csv(DINS, dtype=str, usecols=list(cols)).rename(columns=cols)
    d["lat"] = pd.to_numeric(d["lat"], errors="coerce")
    d["lon"] = pd.to_numeric(d["lon"], errors="coerce")
    d = d.dropna(subset=["lat", "lon"])
    d["start"] = pd.to_datetime(d["start"], errors="coerce", format="mixed")
    return d


def main():
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect()
    con.sql("LOAD spatial; SET enable_progress_bar=false;")
    con.register("dins", load_dins())
    con.sql(f"""
        CREATE TABLE pts AS
        SELECT d.*, t.GEOID, ST_Point(d.lon, d.lat) AS g
        FROM dins d JOIN '{TRACTS.as_posix()}' t ON ST_Contains(t.geometry, ST_Point(d.lon, d.lat))
    """)
    # ~10 m search radius in degrees at 40 N (lat 9e-5, lon 1.2e-4); containment first.
    con.sql(f"""
        CREATE TABLE b AS
        SELECT id, sources[1].dataset AS src, sources[1].update_time AS upd, geometry
        FROM '{BUILDINGS.as_posix()}'
        WHERE bbox.xmin <= (SELECT max(lon) FROM pts) + 0.01 AND bbox.xmax >= (SELECT min(lon) FROM pts) - 0.01
          AND bbox.ymin <= (SELECT max(lat) FROM pts) + 0.01 AND bbox.ymax >= (SELECT min(lat) FROM pts) - 0.01
    """)
    m = con.sql("""
        SELECT p.gid, any_value(b.src) AS src, any_value(b.upd) AS upd,
               max(CASE WHEN ST_Contains(b.geometry, p.g) THEN 1 ELSE 0 END) AS inside
        FROM pts p JOIN b ON ST_Intersects(b.geometry, ST_Buffer(p.g, 0.00011))
        GROUP BY p.gid
    """).df()
    pts = con.sql("SELECT gid, damage, stype, scat, incident, start, county, lat, lon, GEOID FROM pts").df()
    res = pts.merge(m, on="gid", how="left")
    res["matched"] = res["src"].notna()
    res["upd_date"] = pd.to_datetime(res["upd"], errors="coerce", utc=True).dt.tz_localize(None)
    res.to_parquet(OUT / "dins_footprints.parquet", index=False)
    return res


if __name__ == "__main__":
    r = main()
    r["destroyed"] = r["damage"].str.startswith("Destroyed")
    r["year"] = r["start"].dt.year
    print(r.groupby(["destroyed"])["matched"].agg(["mean", "size"]).round(3).to_string())
    top = r[r["incident"].isin(r["incident"].value_counts().head(12).index)]
    print(top.groupby(["incident", "year", "destroyed"])["matched"].agg(["mean", "size"]).round(3).to_string())
