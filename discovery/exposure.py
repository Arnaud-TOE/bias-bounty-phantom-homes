"""Who is exposed: vulnerability and tribal contrasts for phantoms, and the nursing-home annex.

Reads the outputs of phantom_homes.py and cms_nursing_homes.py plus the challenge strata, and
writes discovery/out/phantom_exposure.csv and discovery/out/cms_by_{whp,svi}_quartile.csv.

- Shares of destroyed structures and phantoms (2020-2025 fires) in high-SVI tracts
  (SVI >= 0.75) against the share of the region's tracts.
- Within-fire linear probability models, one per contrast (phantom ~ high SVI + fire fixed
  effects; phantom ~ tract touching a tribal statistical or legal area + fire fixed effects),
  standard errors clustered by tract. "Touching" means the strata name an AIANNH area for the
  tract (aiannh_name), which is broader than tribal_any.
- CMS nursing homes found in Overture by quartile of USFS wildfire hazard potential and of SVI,
  quartiles taken over the nursing homes themselves.

Run: python -I discovery/exposure.py
"""
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "discovery/out"
REGIONS = ["south-central-tx", "maricopa-az", "eastern-ok", "northern-ca", "eastern-wa"]


def strata(region: str) -> pd.DataFrame:
    st = pd.read_parquet(ROOT / f"data/raw/strata/{region}/{region}-strata-tract-table.parquet",
                         columns=["GEOID", "svi_overall", "aiannh_name", "usfs_WHP_mean"])
    st["GEOID"] = st["GEOID"].astype(str)
    sub = pd.read_csv(ROOT / f"data/raw/reference/{region}/{region}-sample-submission.csv", dtype={"GEOID": str})
    return sub[["GEOID"]].merge(st, on="GEOID", how="left")


def phantoms() -> pd.DataFrame:
    st = strata("northern-ca")
    pts = pd.read_parquet(OUT / "phantom_points.parquet")
    d = pts[pts["recent"] & pts["destroyed"]].merge(st, on="GEOID", how="left")
    d["svi_high"] = (d["svi_overall"] >= 0.75).astype(float)
    d["tribal"] = d["aiannh_name"].notna().astype(float)
    d["phantom_f"] = d["phantom"].astype(float)
    region_high = (st["svi_overall"] >= 0.75).mean()
    clusters = {"cov_type": "cluster", "cov_kwds": {"groups": pd.factorize(d["GEOID"])[0]}}
    m_svi = smf.ols("phantom_f ~ svi_high + C(incident)", data=d).fit(**clusters)
    m_tr = smf.ols("phantom_f ~ tribal + C(incident)", data=d).fit(**clusters)
    row = {
        "region_tracts_svi_high": region_high,
        "destroyed_in_svi_high": d["svi_high"].mean(),
        "phantoms_in_svi_high": d.loc[d["phantom"], "svi_high"].mean(),
        "phantoms_svi_high_ratio_to_region": d.loc[d["phantom"], "svi_high"].mean() / region_high,
        "lpm_svi_high_coef": m_svi.params["svi_high"], "lpm_svi_high_p": m_svi.pvalues["svi_high"],
        "lpm_tribal_coef": m_tr.params["tribal"], "lpm_tribal_p": m_tr.pvalues["tribal"],
        "lpm_n": int(m_svi.nobs), "tribal_tracts_with_destroyed": int(d.loc[d["tribal"] > 0, "GEOID"].nunique()),
    }
    out = pd.DataFrame([row])
    out.to_csv(OUT / "phantom_exposure.csv", index=False)
    return out


def nursing_homes() -> pd.DataFrame:
    nh = pd.read_parquet(OUT / "cms_nursing_homes.parquet")
    st = pd.concat([strata(r) for r in REGIONS], ignore_index=True)
    x = nh.merge(st[["GEOID", "usfs_WHP_mean", "svi_overall"]], on="GEOID", how="left")
    outs = []
    for col, name in [("usfs_WHP_mean", "whp"), ("svi_overall", "svi")]:
        q = pd.qcut(x[col].rank(method="first"), 4, labels=[1, 2, 3, 4])
        out = x.groupby(q, observed=True).agg(n=("ccn", "size"), found=("found", "mean")).reset_index()
        out = out.rename(columns={col: f"{name}_q"})
        out.to_csv(OUT / f"cms_by_{name}_quartile.csv", index=False)
        outs.append(out)
    return pd.concat(outs, axis=1)


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print(phantoms().round(4).T.to_string())
    print(nursing_homes().round(3).to_string())
