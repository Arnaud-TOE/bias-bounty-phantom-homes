# Best Bias Discovery — phantom homes in recent burn scars

Wildfire-destroyed structures that Overture (release 2026-08-19.0) still draws as standing
buildings, measured against CAL FIRE's structure-by-structure damage inspections (DINS).

```bash
python -I discovery/reproduce.py      # checks external-file SHA-256, then runs every step (~2 min)
```

| Script | Output |
|---|---|
| `phantom_homes.py` | `out/phantom_points.parquet`, `out/phantom_summary.csv`, `out/phantom_excess.csv`, `out/phantom_by_{year,fire,place,tract}.csv`, `../writeup/figures/phantom_by_year.png` |
| `phantom_maps.py` | `../writeup/figures/phantom_case_maps.png` (Greenville / Dixie 2021, Cohasset / Park 2024) |
| `cms_nursing_homes.py` | `out/cms_nursing_homes.parquet` (annex: CMS nursing homes vs Overture places) |
| `exposure.py` | `out/phantom_exposure.csv` (SVI and tribal contrasts, within-fire models), `out/cms_by_{whp,svi}_quartile.csv` |
| `dins_footprints.py` | first exploratory pass (superseded by `phantom_homes.py`, kept for the record) |

External data and checksums: `external/SOURCES.md`. These files are used only here; the scored
leaderboard pipeline, published separately after 31 October, never reads them.
