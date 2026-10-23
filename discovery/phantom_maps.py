"""Case-study maps for the phantom-homes finding (Greenville / Dixie 2021, Cohasset / Park 2024).

Grey outlines: Overture footprints (release 2026-08-19.0). Points: CAL FIRE DINS structures —
red = destroyed but still drawn with a pre-fire source date (phantom), black = destroyed and
not drawn, green = not destroyed. Run after discovery/phantom_homes.py.
"""
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PTS = ROOT / "discovery/out/phantom_points.parquet"
BUILDINGS = ROOT / "data/raw/reference/northern-ca/northern-ca-overture-buildings.parquet"
FIG = ROOT / "writeup/figures"
CASES = [("Dixie", "Greenville", "Greenville, Plumas County — Dixie Fire (Aug 2021)"),
         ("Park", "Cohasset", "Cohasset, Butte County — Park Fire (Jul 2024)")]
# Greenville's DINS points spread along Indian Valley; frame the town itself.
FRAMES = {"Greenville": (-120.962, 40.128, -120.928, 40.162)}


def draw(ax, con, pts, incident, place, title):
    p = pts[(pts["incident"] == incident) & (pts["place"] == place)]
    if place in FRAMES:
        x0, y0, x1, y1 = FRAMES[place]
    else:
        x0, x1 = p["lon"].quantile([0.02, 0.98])
        y0, y1 = p["lat"].quantile([0.02, 0.98])
        pad = 0.003
        x0, x1, y0, y1 = x0 - pad, x1 + pad, y0 - pad, y1 + pad
    b = con.sql(f"""
        SELECT ST_AsWKB(geometry) AS wkb FROM '{BUILDINGS.as_posix()}'
        WHERE bbox.xmin <= {x1} AND bbox.xmax >= {x0} AND bbox.ymin <= {y1} AND bbox.ymax >= {y0}
    """).df()
    for g in shapely.from_wkb(b["wkb"].map(bytes)):
        for poly in getattr(g, "geoms", [g]):
            xs, ys = poly.exterior.xy
            ax.plot(xs, ys, color="#9aa3ab", lw=0.4)
    sel = pts[pts["lon"].between(x0, x1) & pts["lat"].between(y0, y1) & (pts["incident"] == incident)]
    groups = [
        (~sel["destroyed"], "#27ae60", 6, "not destroyed"),
        (sel["destroyed"] & ~sel["matched"], "#222222", 6, "destroyed, no footprint within 10 m"),
        (sel["destroyed"] & sel["matched"] & ~sel["phantom"], "#f39c12", 7,
         "destroyed, footprint dated after the fire or undated (not counted)"),
        (sel["phantom"], "#d62728", 9, "destroyed, still drawn with a pre-fire source (phantom)"),
    ]
    for m, c, s, lab in groups:
        ax.scatter(sel.loc[m, "lon"], sel.loc[m, "lat"], s=s, c=c, label=f"{lab} ({int(m.sum())})", lw=0)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))  # metric-looking lon/lat aspect
    ax.set_title(title, fontsize=8)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.legend(loc="lower left", fontsize=6, frameon=True)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    pts = pd.read_parquet(PTS)
    con = duckdb.connect()
    con.sql("LOAD spatial; SET enable_progress_bar=false;")
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.4), dpi=170)
    for ax, (incident, place, title) in zip(axes, CASES):
        draw(ax, con, pts, incident, place, title)
    fig.suptitle("Phantom homes: Overture footprints over CAL FIRE damage inspections", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "phantom_case_maps.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
