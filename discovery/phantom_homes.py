"""Phantom homes: wildfire-destroyed structures still drawn as standing buildings in Overture.

Inputs
  - CAL FIRE Damage Inspection (DINS) points: ground truth of what burned (external, see
    discovery/external/SOURCES.md).
  - Overture buildings, release 2026-08-19.0, northern-ca extract (challenge data).
  - Challenge strata (tract population, SVI, tribal overlap, wildfire hazard).

Definition (conservative)
  A destroyed DINS structure is a *phantom* when an Overture footprint lies within R metres
  (main R = 10 m; sensitivity 0 / 5 / 20 m) AND that footprint's source date (Microsoft
  imagery date or OpenStreetMap last-edit date) is known and earlier than the fire's start
  date. A footprint dated after the fire may be a rebuilt home, so it is never counted.

Controls
  - "No Damage" structures of the same fires: how often a standing structure is matched.
  - Placebo: every destroyed point shifted 60 m in a seeded random direction; the match rate
    there is the chance of hitting an unrelated footprint.

Outputs: discovery/out/phantom_*.csv|parquet, writeup/figures/phantom_*.png
Run:     python -I discovery/phantom_homes.py      (about 2 minutes)
"""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DINS = ROOT / "discovery/external/raw/calfire_dins/dins.csv"
REGION = "northern-ca"
TRACTS = ROOT / f"data/raw/strata/{REGION}/{REGION}-census-tracts.parquet"
STRATA = ROOT / f"data/raw/strata/{REGION}/{REGION}-strata-tract-table.parquet"
ACS = ROOT / f"data/raw/reference/{REGION}/{REGION}-census-acs-housing.parquet"
BUILDINGS = ROOT / f"data/raw/reference/{REGION}/{REGION}-overture-buildings.parquet"
OUT = ROOT / "discovery/out"
FIG = ROOT / "writeup/figures"
UNKNOWN_DATE = pd.Timestamp("2000-01-01")
RADII = (0, 5, 10, 20)
MAIN_R = 10
SEED = 20261017


def load_dins() -> pd.DataFrame:
    cols = {"GLOBALID": "gid", "* Damage": "damage", "* Structure Type": "stype",
            "Structure Category": "scat", "# Units in Structure (if multi unit)": "units",
            "* Incident Name": "incident", "Incident Start Date": "start", "County": "county",
            "* City": "city", "Community": "community", "Latitude": "lat", "Longitude": "lon"}
    d = pd.read_csv(DINS, dtype=str, usecols=list(cols)).rename(columns=cols)
    for c in ("lat", "lon", "units"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["lat", "lon"])
    d["start"] = pd.to_datetime(d["start"], errors="coerce", format="mixed")
    d["place"] = d["city"].fillna(d["community"]).str.strip().str.title()
    d["destroyed"] = d["damage"].str.startswith("Destroyed")
    d["residential"] = d["scat"].fillna("").str.contains("Residence|Residential", case=False)
    d["units"] = np.where(d["residential"], d["units"].fillna(1).clip(lower=1), 0)
    return d


def nearest_footprints(con, pts: pd.DataFrame, max_m: float = 25.0) -> pd.DataFrame:
    """Nearest Overture footprint within max_m metres of each point (CA Albers, EPSG:3310)."""
    con.register("pts_df", pts[["pid", "lon", "lat"]])
    deg = max_m / 80000  # generous degree buffer at ~40 N
    return con.sql(f"""
        WITH p AS (
            SELECT pid, ST_Point(lon, lat) AS g,
                   ST_Transform(ST_Point(lon, lat), 'EPSG:4326', 'EPSG:3310', always_xy := true) AS g3
            FROM pts_df),
        c AS (
            SELECT p.pid, b.src, b.upd,
                   ST_Distance(p.g3, ST_Transform(b.geometry, 'EPSG:4326', 'EPSG:3310', always_xy := true)) AS dist_m
            FROM p JOIN bld b ON ST_Intersects(b.geometry, ST_Buffer(p.g, {deg}))
        )
        SELECT pid, arg_min(src, dist_m) AS src, arg_min(upd, dist_m) AS upd, min(dist_m) AS dist_m
        FROM c WHERE dist_m <= {max_m} GROUP BY pid
    """).df()


def classify(df: pd.DataFrame, r: float) -> pd.Series:
    upd = pd.to_datetime(df["upd"], errors="coerce", utc=True).dt.tz_localize(None)
    known = upd.notna() & (upd != UNKNOWN_DATE)
    return df["dist_m"].le(r) & known & (upd < df["start"])


def main():
    OUT.mkdir(exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.sql("LOAD spatial; SET enable_progress_bar=false;")

    d = load_dins()
    con.register("dins", d)
    pts = con.sql(f"""
        SELECT d.*, t.GEOID FROM dins d
        JOIN '{TRACTS.as_posix()}' t ON ST_Contains(t.geometry, ST_Point(d.lon, d.lat))
    """).df()
    pts["pid"] = np.arange(len(pts))
    lo, la = pts["lon"], pts["lat"]
    con.sql(f"""
        CREATE TABLE bld AS
        SELECT sources[1].dataset AS src, sources[1].update_time AS upd, geometry
        FROM '{BUILDINGS.as_posix()}'
        WHERE bbox.xmin <= {lo.max() + 0.01} AND bbox.xmax >= {lo.min() - 0.01}
          AND bbox.ymin <= {la.max() + 0.01} AND bbox.ymax >= {la.min() - 0.01}
    """)

    near = nearest_footprints(con, pts)
    res = pts.merge(near, on="pid", how="left")
    res["year"] = res["start"].dt.year
    res["recent"] = res["year"].between(2020, 2025)
    for r in RADII:
        res[f"stale_{r}m"] = classify(res, r)
    res["phantom"] = res["destroyed"] & res[f"stale_{MAIN_R}m"]
    res["matched"] = res["dist_m"].le(MAIN_R)

    # Placebo: shift destroyed points 60 m in a seeded random direction.
    rng = np.random.default_rng(SEED)
    dest = res[res["destroyed"]].copy()
    ang = rng.uniform(0, 2 * np.pi, len(dest))
    dest["lat"] = dest["lat"] + 60 * np.sin(ang) / 110540
    dest["lon"] = dest["lon"] + 60 * np.cos(ang) / (111320 * np.cos(np.radians(dest["lat"])))
    plac = nearest_footprints(con, dest[["pid", "lon", "lat"]])
    dest = dest[["pid", "start", "recent"]].merge(plac, on="pid", how="left")
    dest["placebo_stale"] = classify(dest, MAIN_R)
    res = res.merge(dest[["pid", "placebo_stale"]], on="pid", how="left")

    res.drop(columns=["start"]).assign(start=res["start"].astype(str)).to_parquet(
        OUT / "phantom_points.parquet", index=False)
    summary = summarise(res, dest)
    summary["excess"] = excess_over_placebo(res)
    tracts = per_tract(con, res)
    figures(res)
    return summary, tracts


def excess_over_placebo(res: pd.DataFrame, n_boot: int = 2000) -> pd.DataFrame:
    """Phantom share minus placebo share for 2020-2025 fires, with a fire-clustered bootstrap.

    The placebo share is the rate at which a point 60 m away from a destroyed structure meets a
    pre-fire footprint by chance, so the difference is the control-adjusted phantom rate.
    """
    d = res[res["recent"] & res["destroyed"]]
    g = d.groupby("incident").agg(n=("pid", "size"), ph=("phantom", "sum"), pl=("placebo_stale", "sum"))
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(g), (n_boot, len(g)))
    n, ph, pl = (g[c].to_numpy(float)[idx].sum(axis=1) for c in ("n", "ph", "pl"))
    boot = (ph - pl) / n
    point = (g["ph"].sum() - g["pl"].sum()) / g["n"].sum()
    lo, hi = np.percentile(boot, [2.5, 97.5])
    out = pd.DataFrame([{
        "fires": len(g), "destroyed": int(g["n"].sum()),
        "phantom_share": g["ph"].sum() / g["n"].sum(), "placebo_share": g["pl"].sum() / g["n"].sum(),
        "excess_share": point, "excess_ci_low": lo, "excess_ci_high": hi,
        "excess_structures": point * g["n"].sum(),
        "phantoms_osm": int(d.loc[d["phantom"], "src"].eq("OpenStreetMap").sum()),
        "phantoms_microsoft": int(d.loc[d["phantom"], "src"].eq("Microsoft ML Buildings").sum()),
    }])
    out.to_csv(OUT / "phantom_excess.csv", index=False)
    return out


def summarise(res: pd.DataFrame, plac: pd.DataFrame) -> dict:
    out = {}
    for period, mask in {"<=2019": ~res["recent"] & res["year"].notna(), "2020-2025": res["recent"]}.items():
        dd = res[mask & res["destroyed"]]
        nd = res[mask & ~res["destroyed"]]
        row = {"destroyed": len(dd), "standing_control": len(nd),
               "control_matched_10m": nd["matched"].mean()}
        for r in RADII:
            row[f"phantom_share_{r}m"] = dd[f"stale_{r}m"].mean()
        row["phantoms_10m"] = int(dd[f"stale_{MAIN_R}m"].sum())
        row["phantom_units_10m"] = float(dd.loc[dd[f"stale_{MAIN_R}m"], "units"].sum())
        pm = plac["recent"] if period == "2020-2025" else ~plac["recent"]
        row["placebo_stale_share_10m"] = plac.loc[pm, "placebo_stale"].mean()
        out[period] = row
    s = pd.DataFrame(out).T
    s.to_csv(OUT / "phantom_summary.csv")
    by_fire = (res[res["destroyed"]].groupby(["incident", "year"])
               .agg(destroyed=("pid", "size"), phantoms=("phantom", "sum"),
                    phantom_units=("units", lambda u: u[res.loc[u.index, "phantom"]].sum()))
               .query("destroyed >= 50").sort_values("phantoms", ascending=False))
    by_fire["phantom_share"] = by_fire["phantoms"] / by_fire["destroyed"]
    by_fire.to_csv(OUT / "phantom_by_fire.csv")
    by_year = (res[res["destroyed"] & res["year"].notna()].groupby("year")
               .agg(destroyed=("pid", "size"), phantoms=("phantom", "sum")))
    by_year["phantom_share"] = by_year["phantoms"] / by_year["destroyed"]
    by_year.to_csv(OUT / "phantom_by_year.csv")
    by_place = (res[res["destroyed"] & res["recent"]].groupby(["incident", "place"])
                .agg(destroyed=("pid", "size"), phantoms=("phantom", "sum"),
                     phantom_units=("units", lambda u: u[res.loc[u.index, "phantom"]].sum()))
                .query("phantoms >= 10").sort_values("phantoms", ascending=False))
    by_place.to_csv(OUT / "phantom_by_place.csv")
    return {"summary": s, "by_fire": by_fire, "by_year": by_year, "by_place": by_place}


def per_tract(con, res: pd.DataFrame) -> pd.DataFrame:
    # usfs_BuildingCount_sum (USFS Wildfire Risk to Communities, 2nd edition, 2022 conditions) is
    # read here only to compare an exposure product with the phantoms; the scored pipeline never
    # uses it (decision D2).
    st = pd.read_parquet(STRATA, columns=["GEOID", "pop_total", "pct_urban", "svi_overall",
                                          "tribal_any", "aiannh_name", "usfs_WHP_mean",
                                          "usfs_BuildingCount_sum"])
    hu = pd.read_parquet(ACS, columns=["GEOID", "housing_units"])
    ov = con.sql(f"""
        SELECT t.GEOID, count(*) AS overture_buildings
        FROM '{TRACTS.as_posix()}' t
        JOIN '{BUILDINGS.as_posix()}' b ON ST_Contains(t.geometry, ST_Centroid(b.geometry))
        GROUP BY 1
    """).df()
    rec = res[res["recent"] & res["destroyed"]]
    t = (rec.groupby("GEOID").agg(destroyed_2020_25=("pid", "size"), phantoms=("phantom", "sum"),
                                  phantom_units=("units", lambda u: u[rec.loc[u.index, "phantom"]].sum()),
                                  fires=("incident", lambda x: ", ".join(sorted(set(x)))))
         .reset_index().merge(st, on="GEOID", how="left").merge(hu, on="GEOID", how="left")
         .merge(ov, on="GEOID", how="left"))
    t["phantom_share"] = t["phantoms"] / t["destroyed_2020_25"]
    t["phantom_share_of_overture"] = t["phantoms"] / t["overture_buildings"]
    t = t.sort_values("phantoms", ascending=False)
    t.to_csv(OUT / "phantom_by_tract.csv", index=False)
    return t


def figures(res: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_year = (res[res["destroyed"] & res["year"].between(2013, 2025)].groupby("year")
               .agg(destroyed=("pid", "size"), phantoms=("phantom", "sum")))
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=150)
    share = 100 * by_year["phantoms"] / by_year["destroyed"]
    colors = ["#c0392b" if y >= 2020 else "#7f8c8d" for y in by_year.index]
    ax.bar(by_year.index.astype(int), share, color=colors)
    for y, s, n in zip(by_year.index.astype(int), share, by_year["destroyed"]):
        ax.text(y, s + 1, f"n={n:,}", ha="center", fontsize=6.5, color="#333")
    ax.set_ylabel("% of destroyed structures\nstill drawn (pre-fire source)")
    ax.set_xlabel("Fire year (CAL FIRE DINS, northern-ca study region)")
    ax.set_title("Phantom homes: destroyed structures still mapped in Overture 2026-08-19.0", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "phantom_by_year.png")
    plt.close(fig)


if __name__ == "__main__":
    out, tracts = main()
    pd.set_option("display.width", 200)
    print(out["summary"].round(4).to_string())
    print(out["excess"].round(4).to_string())
    print(out["by_fire"].head(12).round(3).to_string())
    print(out["by_place"].head(15).to_string())
    print(tracts.head(15)[["GEOID", "phantoms", "destroyed_2020_25", "phantom_units", "fires",
                           "svi_overall", "pct_urban", "tribal_any", "aiannh_name"]].to_string())
