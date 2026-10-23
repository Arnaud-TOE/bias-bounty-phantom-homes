# External sources (Best Bias Discovery only)

These files are used **only** by the Bias Discovery analysis in `discovery/`. They are never
read by the scored pipeline (`src/bbx/`), whose I/O guard refuses anything outside the
permitted challenge layers. Raw files live in `discovery/external/raw/` (not committed);
re-download with the URLs below and check the SHA-256.

| File | Source | URL | Retrieved (UTC) | SHA-256 | Licence |
|---|---|---|---|---|---|
| `raw/cms_nh/NH_ProviderInfo_Sep2026_3.csv` | CMS Provider Data Catalog, "Nursing Home Provider Information" (dataset 4pq5-n9py, modified 2026-09-30) | https://data.cms.gov/provider-data/sites/default/files/resources/4b708f7ece9ed1ef3060686c5546ddf1_1790792149/NH_ProviderInfo_Sep2026_3.csv | 2026-10-17T16:16Z | `378d76a43f89c132e6796ea97530a004beabd2b0aa6516833c5734fd99d1e2b0` | US Government work, public (accessLevel: public) |
| `raw/calfire_dins/dins.csv` | CAL FIRE Damage Inspection (DINS) Data, California Natural Resources Agency open data (metadata modified 2026-10-12) | https://gis.data.cnra.ca.gov/api/download/v1/items/994d3dc4569640caadbbc3198d5a3da1/csv?layers=0 | 2026-10-17T16:16Z | `af01e965145420695504db3385782c6879dee00dc66586feec8a6bfc0938404f` | Creative Commons Attribution |

Catalogue pages: https://data.cms.gov/provider-data/dataset/4pq5-n9py ·
https://data.ca.gov/dataset/cal-fire-damage-inspection-dins-data
