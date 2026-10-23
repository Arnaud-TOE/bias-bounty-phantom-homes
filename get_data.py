"""Fetch the inputs of the phantom-homes discovery and check every SHA-256.

    python -I get_data.py
"""
import gzip
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUCKET = "https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
CHALLENGE = {'strata/south-central-tx/south-central-tx-census-tracts.parquet': '7d64db287ed13d979197338e5d3702ba9f7ec4d1c563aff955bf6fe6bda6fc82', 'strata/maricopa-az/maricopa-az-census-tracts.parquet': 'be3be05b7fcf77773d43a4d9b8ef18af44d1bdc840fd215b31329ad2b0bcfedd', 'strata/eastern-ok/eastern-ok-census-tracts.parquet': 'cffccf214028d124747de44fce3edff9acce0a43bf0efcf62727cb7cd7d57623', 'strata/northern-ca/northern-ca-census-tracts.parquet': '910e21ff039000dff13779051cd5d1ef62c0ea183ebdd7ff4170942fe5fb877d', 'strata/eastern-wa/eastern-wa-census-tracts.parquet': '428ae8c2bcc8537493deea86c518bb91a5407c182916577ac7089b52dc752c16', 'strata/south-central-tx/south-central-tx-strata-tract-table.parquet': '55589565024414f244ccbcadcc45a90860a3840ec9d8a4bdfa8a126c2128a354', 'strata/maricopa-az/maricopa-az-strata-tract-table.parquet': 'f19ec2f5afd400827b2420a81916bdec95b08772badd85fdb250149c334a5fcd', 'strata/eastern-ok/eastern-ok-strata-tract-table.parquet': 'e82862b9d9db436410ad47df466e133df94df6328f6a138d5bd871b491ba0d54', 'strata/northern-ca/northern-ca-strata-tract-table.parquet': '7fc19dce5ca76ee94eb2006d9bd51bed71d5bfbcdf3ef756605e0998df940243', 'strata/eastern-wa/eastern-wa-strata-tract-table.parquet': '997de038b4d2cab2129c8502c48aab1edc4016981a2ef0556d63ca1518cac737', 'reference/south-central-tx/south-central-tx-overture-pois.parquet': '08728fee580c90179188b1cdf89818e080c64acd1a16958f5fa00d17aac3c6a9', 'reference/maricopa-az/maricopa-az-overture-pois.parquet': '9729146f70026f98d68cc47008cf679dd450e3378680c70090351572f8c3315f', 'reference/eastern-ok/eastern-ok-overture-pois.parquet': '1ab300aec153e52c781defaa1986ea3144950f557ed1894b14237a8d8e016290', 'reference/northern-ca/northern-ca-overture-pois.parquet': '6318deb41156116c002f2bf0222e37b0ba758c1707fbf573da13afd32a482d6a', 'reference/eastern-wa/eastern-wa-overture-pois.parquet': '3babc61314e84203ce786a03258bd23b8635ac1a2c7a3db0d39914a8a2ac5a74', 'reference/south-central-tx/south-central-tx-sample-submission.csv': 'afa59c0eb30c40be25ce82098f144447591b79cb9692e669b2f2fe7b7b1ee58e', 'reference/maricopa-az/maricopa-az-sample-submission.csv': '1640b801d56ab308e68c65583b88cfb9e1555b05a6d0b922eaba22ac09960a31', 'reference/eastern-ok/eastern-ok-sample-submission.csv': '56cb40fba4008d646bc63c62c91e211871459224b3de8b3a886ff813803fd0d4', 'reference/northern-ca/northern-ca-sample-submission.csv': 'f38017b5284667b80b451685fd146388c108e1b30308301289c7a96ecfe60902', 'reference/eastern-wa/eastern-wa-sample-submission.csv': '0e0155d5a5e8ef39dc857c8268669b5fb498d7ac40f0ded782482c67ae5efefc', 'reference/northern-ca/northern-ca-census-acs-housing.parquet': '39720c19a40df65843ff2f8da2f543af80abf0bf097f89cadce68d4b015cccca', 'reference/northern-ca/northern-ca-overture-buildings.parquet': '00a4058f4771a54e167dbbd495c281f1549e768acc55ae2b64124e6278e68945'}
EXTERNAL = {'discovery/external/calfire_dins.csv.gz': ('discovery/external/raw/calfire_dins/dins.csv', 'af01e965145420695504db3385782c6879dee00dc66586feec8a6bfc0938404f'), 'discovery/external/cms_nh.csv.gz': ('discovery/external/raw/cms_nh/NH_ProviderInfo_Sep2026_3.csv', '378d76a43f89c132e6796ea97530a004beabd2b0aa6516833c5734fd99d1e2b0')}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    for rel, digest in CHALLENGE.items():
        dest = ROOT / "data" / "raw" / rel
        if not (dest.exists() and sha256(dest) == digest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            print("downloading", rel, flush=True)
            # The bucket's CDN refuses urllib's default User-Agent.
            req = urllib.request.Request(f"{BUCKET}/{rel}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as r, open(dest, "wb") as out:
                shutil.copyfileobj(r, out, 1 << 22)
        if sha256(dest) != digest:
            print("checksum mismatch for", rel)
            return 1
    for packed, (target, digest) in EXTERNAL.items():
        dest = ROOT / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(ROOT / packed, "rb") as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)
        if sha256(dest) != digest:
            print("checksum mismatch for", target)
            return 1
    print("all inputs present and verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
